"""
ARISE-I — Health Monitor
-------------------------
Autonomous File Organization Unit: Self-Healing Daemon.
Built by Om // Ironlabs.tech

Runs as a background thread and periodically checks the health of the
ARISE-I installation, automatically correcting recoverable issues.

Health checks performed every 60 seconds:
  1. Manifest integrity  — corrupt JSON is backed up and reset
  2. Disk space          — warns (once) when target drive < 500 MB free
  3. Orphan review files — files in __Review__/ older than 7 days are flagged once
  4. Model drift         — high correction rate triggers a retrain, but only
                           when new feedback has arrived since the last one

Events are surfaced to the GUI via a shared queue (same mechanism as the
activity log) so the user sees live health alerts without polling.
"""

import json
import logging
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from arise_i.constants import APP_DIR, LOG_MANIFEST, REVIEW_FOLDER

logger = logging.getLogger("arise_i.health")

# ── Tunables ─────────────────────────────────────────────────────────────────
CHECK_INTERVAL_S      = 60          # seconds between health scans
DISK_WARN_BYTES       = 500 * 1024 * 1024   # 500 MB
ORPHAN_MAX_DAYS       = 7           # days before Review files are flagged as stale
DRIFT_WARN_RATE       = 0.30        # correction rate above which to warn
DRIFT_MIN_NEW_EVENTS  = 10          # fresh feedback needed before another drift retrain
HEALTH_FILE           = APP_DIR / "health.json"

# ── Sentinel messages understood by the GUI log parser ────────────────────────
MSG_HEALTH_WARN   = "__HEALTH_WARN__"
MSG_HEALTH_RETRAIN = "__HEALTH_RETRAIN__"


class HealthMonitor:
    """Background self-healing monitor.

    Parameters
    ----------
    target_dir    : the folder being organized (for disk-space and orphan checks)
    log_queue     : a queue.Queue shared with the GUI (None = log only)
    learning_store: optional LearningStore to trigger retraining
    classifier    : optional SmartClassifier to reload after retrain
    """

    def __init__(
        self,
        target_dir: Optional[Path] = None,
        log_queue=None,
        learning_store=None,
        classifier=None,
    ) -> None:
        self._target_dir     = target_dir
        self._queue          = log_queue
        self._learning_store = learning_store
        self._classifier     = classifier
        self._stop_event     = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_status: dict = {}
        # Alert de-duplication: each condition is reported once, not every cycle
        self._disk_warned           = False
        self._orphans_reported: set[str] = set()
        self._drift_retrain_at: Optional[int] = None  # event count at last retrain

    def set_target_dir(self, target_dir: Optional[Path]) -> None:
        """Point the disk/orphan checks at a newly selected folder."""
        self._target_dir = target_dir
        self._disk_warned = False
        self._orphans_reported.clear()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background monitor thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name="arise-i-health", daemon=True
        )
        self._thread.start()
        logger.info("HealthMonitor started.")

    def stop(self) -> None:
        """Signal the monitor to stop and wait briefly for clean exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("HealthMonitor stopped.")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_checks()
            except Exception as exc:
                logger.error("HealthMonitor check cycle failed: %s", exc)
            self._stop_event.wait(timeout=CHECK_INTERVAL_S)

    def _run_checks(self) -> None:
        status: dict = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "checks": {},
        }

        # 1. Manifest integrity
        status["checks"]["manifest"] = self._check_manifest()

        # 2. Disk space
        if self._target_dir:
            status["checks"]["disk"] = self._check_disk(self._target_dir)

        # 3. Orphan review files
        if self._target_dir:
            status["checks"]["orphans"] = self._check_orphans()

        # 4. Model drift
        status["checks"]["drift"] = self._check_drift()

        self._last_status = status
        self._persist_status(status)

    # ── Individual checks ─────────────────────────────────────────────────────

    def _check_manifest(self) -> dict:
        """Validate all known ARISE-I manifests are readable JSON."""
        issues: list[str] = []

        # Manifests live in each organised folder, next to the sorted files.
        candidates: list[Path] = []
        if self._target_dir and (self._target_dir / LOG_MANIFEST).exists():
            candidates.append(self._target_dir / LOG_MANIFEST)

        for mf in candidates:
            try:
                with open(mf, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, list):
                    raise ValueError("not a list")
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                backup = mf.with_suffix(f".bak.{int(time.time())}")
                try:
                    shutil.copy2(mf, backup)
                    mf.write_text("[]", encoding="utf-8")
                    msg = f"⚕  Manifest corrupted ({mf.name}) — backed up, reset. ({exc})"
                    self._emit(msg, warn=True)
                    issues.append(str(mf))
                    logger.warning("Corrupt manifest reset: %s → %s", mf, backup)
                except Exception as repair_exc:
                    logger.error("Could not repair manifest %s: %s", mf, repair_exc)

        return {"ok": len(issues) == 0, "repaired": issues}

    def _check_disk(self, path: Path) -> dict:
        """Warn if free disk space on the target volume drops below threshold."""
        try:
            usage = shutil.disk_usage(path)
            free  = usage.free
            ok    = free >= DISK_WARN_BYTES
            if not ok and not self._disk_warned:
                gb = free / (1024 ** 3)
                self._emit(
                    f"⚠  Low disk space: {gb:.2f} GB free on {path} — free up space "
                    f"before organizing large files.",
                    warn=True,
                )
            self._disk_warned = not ok
            return {"ok": ok, "free_bytes": free}
        except Exception as exc:
            logger.warning("Disk check failed: %s", exc)
            return {"ok": True, "error": str(exc)}

    def _check_orphans(self) -> dict:
        """Remind the user (once per file) about files stuck in __Review__/."""
        if self._target_dir is None:
            return {"ok": True, "waiting": 0}

        review_dir = self._target_dir / REVIEW_FOLDER
        if not review_dir.exists():
            return {"ok": True, "waiting": 0}

        cutoff = datetime.now() - timedelta(days=ORPHAN_MAX_DAYS)
        waiting = 0

        for item in review_dir.iterdir():
            if item.is_file():
                try:
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    if mtime < cutoff:
                        waiting += 1
                        if item.name not in self._orphans_reported:
                            self._orphans_reported.add(item.name)
                            self._emit(
                                f"♻  {item.name} has waited in Review for "
                                f">{ORPHAN_MAX_DAYS}d — open the Review Queue to file it.",
                                warn=False,
                            )
                except Exception:
                    pass

        return {"ok": True, "waiting": waiting}

    def _check_drift(self) -> dict:
        """Detect model drift: high user correction rate → trigger retrain."""
        if self._learning_store is None:
            return {"ok": True, "rate": 0.0}

        try:
            rate  = self._learning_store.correction_rate()
            total = self._learning_store.total_events()
            # Retraining only helps once a meaningful amount of new feedback
            # has arrived since the last drift retrain; otherwise the model
            # would be rebuilt (and the alert shown) almost every cycle.
            has_new_data = (self._drift_retrain_at is None
                            or total >= self._drift_retrain_at + DRIFT_MIN_NEW_EVENTS)
            if total >= 30 and rate >= DRIFT_WARN_RATE and has_new_data:
                self._drift_retrain_at = total
                self._emit(
                    f"🧠  Model drift detected ({rate:.0%} correction rate) — triggering retrain…",
                    warn=True,
                )
                if self._queue:
                    self._queue.put(MSG_HEALTH_RETRAIN)
                # Retrain in the monitor thread (non-blocking w.r.t. GUI)
                threading.Thread(
                    target=self._do_retrain, daemon=True, name="arise-i-retrain"
                ).start()
            return {"ok": rate < DRIFT_WARN_RATE, "rate": round(rate, 4), "events": total}
        except Exception as exc:
            logger.warning("Drift check failed: %s", exc)
            return {"ok": True, "error": str(exc)}

    def _do_retrain(self) -> None:
        """Run model retrain off the main health thread."""
        if self._learning_store is None:
            return
        try:
            if self._learning_store.retrain():
                # Shared classifiers also pick up the new model.pkl by mtime
                if self._classifier is not None:
                    self._classifier.reload_model()
                self._emit("🧠  Model retrained successfully — classifier updated.", warn=False)
        except Exception as exc:
            logger.error("Retrain in health monitor failed: %s", exc)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _emit(self, message: str, warn: bool = False) -> None:
        """Send a message to the GUI queue if available, else just log."""
        if self._queue:
            self._queue.put(message)
        if warn:
            logger.warning(message)
        else:
            logger.info(message)

    def _persist_status(self, status: dict) -> None:
        try:
            HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = HEALTH_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(status, fh, indent=2)
            tmp.replace(HEALTH_FILE)
        except Exception as exc:
            logger.debug("Could not persist health status: %s", exc)

    def last_status(self) -> dict:
        """Return the most recent health check result."""
        if self._last_status:
            return self._last_status
        if HEALTH_FILE.exists():
            try:
                with open(HEALTH_FILE, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                pass
        return {}
