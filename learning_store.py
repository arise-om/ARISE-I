"""
ARISE-I — Learning Store
-------------------------
Autonomous File Organization Unit: Adaptive Learning Engine.
Built by Om // Ironlabs.tech

Records every classification decision and user correction, then
periodically retrains the local sklearn model so ARISE-I gets
smarter the more it's used.

Storage layout (~/.arise-i/):
    feedback.jsonl  — append-only event log (one JSON object per line)
    model.pkl       — pickled sklearn Pipeline (TF-IDF + MultinomialNB)
    model_meta.json — human-readable model stats (accuracy, sample count)

All processing is 100 % local — no data ever leaves the machine.
"""

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("arise_i.learning")

# ── Optional: sklearn ─────────────────────────────────────────────────────────
try:
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_score
    import pickle
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────
_ARISE_DIR      = Path.home() / ".arise-i"
FEEDBACK_FILE   = _ARISE_DIR / "feedback.jsonl"
MODEL_FILE      = _ARISE_DIR / "model.pkl"
MODEL_META_FILE = _ARISE_DIR / "model_meta.json"

MIN_SAMPLES       = 20    # minimum events before enabling the ML layer
RETRAIN_THRESHOLD = 50    # new events per session before triggering retrain
MIN_CLASS_SAMPLES = 2     # minimum samples per class for NB to be valid


class LearningStore:
    """Manages the user-feedback log and model retraining lifecycle.

    Usage
    -----
    store = LearningStore(on_retrain=classifier.reload_model)

    # After every successful sort:
    store.record(path, predicted="Documents", confirmed="Documents",
                 confidence=0.92, layer="extension")

    # After a user correction in the Review tab:
    store.record(path, predicted="__Review__", confirmed="PDFs",
                 confidence=0.42, layer="review_fallback")
    """

    def __init__(
        self,
        feedback_file: Path = FEEDBACK_FILE,
        model_file: Path = MODEL_FILE,
        retrain_threshold: int = RETRAIN_THRESHOLD,
        on_retrain: Optional[Callable] = None,
    ) -> None:
        self._feedback_file   = feedback_file
        self._model_file      = model_file
        self._retrain_threshold = retrain_threshold
        self._on_retrain      = on_retrain
        self._session_events  = 0
        _ARISE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def record(
        self,
        path: Path,
        predicted: str,
        confirmed: str,
        confidence: float,
        layer: str,
    ) -> None:
        """Persist a classification event (correct or user-corrected).

        Parameters
        ----------
        path      : the file that was classified
        predicted : ARISE-I's predicted category
        confirmed : the actual correct category (user-confirmed)
        confidence: model confidence at classification time
        layer     : classifier layer that made the decision
        """
        from classifier import _extract_text_features  # avoid circular at module level

        event: dict = {
            "ts":         datetime.now().isoformat(timespec="seconds"),
            "filename":   path.name,
            "extension":  path.suffix.lower(),
            "features":   _extract_text_features(path),
            "predicted":  predicted,
            "confirmed":  confirmed,
            "confidence": round(confidence, 4),
            "layer":      layer,
            "corrected":  predicted != confirmed,
        }

        try:
            with open(self._feedback_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event) + "\n")
        except Exception as exc:
            logger.warning("Could not write feedback event: %s", exc)
            return

        self._session_events += 1

        # Auto-retrain when threshold is hit
        if _SKLEARN_AVAILABLE:
            total = self.total_events()
            if total >= MIN_SAMPLES and self._session_events >= self._retrain_threshold:
                logger.info("Auto-retrain triggered (%d session events)", self._session_events)
                self.retrain()
                self._session_events = 0

    def retrain(self, force: bool = False) -> bool:
        """Retrain the sklearn model from the full feedback log.

        Parameters
        ----------
        force : bypass the MIN_SAMPLES guard (used by tests / CLI)

        Returns True on success, False otherwise.
        """
        if not _SKLEARN_AVAILABLE:
            logger.info("scikit-learn not available — skipping retrain.")
            return False

        events = self._load_all_events()
        if not force and len(events) < MIN_SAMPLES:
            logger.info("Too few samples (%d) — skipping retrain.", len(events))
            return False

        # Use confirmed labels as ground-truth
        texts  = [e["features"] for e in events]
        labels = [e["confirmed"] for e in events]

        # Filter classes with too few samples for NB
        counts = Counter(labels)
        valid  = {cls for cls, n in counts.items() if n >= MIN_CLASS_SAMPLES}
        pairs  = [(t, l) for t, l in zip(texts, labels) if l in valid]

        if not pairs:
            logger.info("No valid class pairs found — skipping retrain.")
            return False

        texts_f, labels_f = zip(*pairs)

        try:
            pipeline = Pipeline([
                ("tfidf", TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=8000,
                    sublinear_tf=True,
                )),
                ("clf", MultinomialNB(alpha=0.5)),
            ])
            pipeline.fit(list(texts_f), list(labels_f))

            # Quick cross-val accuracy estimate (3-fold, silent if too few samples)
            accuracy: Optional[float] = None
            if len(pairs) >= 30:
                try:
                    scores   = cross_val_score(pipeline, list(texts_f), list(labels_f),
                                               cv=3, scoring="accuracy")
                    accuracy = float(scores.mean())
                except Exception:
                    pass

            model_data = {
                "pipeline":   pipeline,
                "labels":     sorted(set(labels_f)),
                "trained_on": len(pairs),
                "accuracy":   accuracy,
                "timestamp":  datetime.now().isoformat(timespec="seconds"),
            }

            # Atomic write
            tmp = self._model_file.with_suffix(".tmp")
            with open(tmp, "wb") as fh:
                pickle.dump(model_data, fh)
            tmp.replace(self._model_file)

            # Write human-readable meta
            meta = {k: v for k, v in model_data.items() if k != "pipeline"}
            with open(MODEL_META_FILE, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=2)

            logger.info(
                "Model retrained: %d samples, %d classes, accuracy=%.2f",
                len(pairs), len(model_data["labels"]), accuracy or 0.0,
            )

            if self._on_retrain:
                self._on_retrain()

            return True

        except Exception as exc:
            logger.error("Retrain failed: %s", exc)
            return False

    # ── Stats ─────────────────────────────────────────────────────────────────

    def total_events(self) -> int:
        """Count lines in the feedback log."""
        if not self._feedback_file.exists():
            return 0
        try:
            with open(self._feedback_file, "r", encoding="utf-8") as fh:
                return sum(1 for _ in fh)
        except Exception:
            return 0

    def correction_rate(self) -> float:
        """Fraction of events where ARISE-I predicted wrong (0.0–1.0)."""
        events = self._load_all_events()
        if not events:
            return 0.0
        corrected = sum(1 for e in events if e.get("corrected", False))
        return corrected / len(events)

    def model_meta(self) -> dict:
        """Return the model_meta.json dict, or empty dict if not trained yet."""
        if not MODEL_META_FILE.exists():
            return {}
        try:
            with open(MODEL_META_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load_all_events(self) -> list[dict]:
        if not self._feedback_file.exists():
            return []
        events: list[dict] = []
        try:
            with open(self._feedback_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            logger.warning("Could not read feedback log: %s", exc)
        return events
