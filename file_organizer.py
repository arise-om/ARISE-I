"""
ARISE-I
------
Autonomous File Organization Unit.
Built by Om // Ironlabs.tech

A polished Python CLI tool that automatically sorts files in a folder
(like Downloads) into category folders based on file type.

Usage:
    python file_organizer.py --dry-run              # preview only, moves nothing
    python file_organizer.py                         # actually organizes ~/Downloads
    python file_organizer.py --path "/path/to/dir"  # custom folder
    python file_organizer.py --undo                  # reverse the last run
    python file_organizer.py --config my.config.yaml # custom category mappings
    python file_organizer.py --watch                 # daemon: sort files as they arrive
    python file_organizer.py --watch --debounce 3    # watch with custom debounce (seconds)
"""

import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Python version guard — must be 3.10+ (match-statement syntax; union type hints)
# ---------------------------------------------------------------------------

if sys.version_info < (3, 10):  # pragma: no cover
    print(
        f"\n[ARISE-I] ✗  Python 3.10+ is required.\n"
        f"           You are running Python {sys.version_info.major}.{sys.version_info.minor}.\n"
        f"           Please upgrade Python and try again.\n"
    )
    sys.exit(1)

import yaml  # PyYAML — only external dependency


# Keep ARISE-I's file logging isolated from an application's root logger.
logger = logging.getLogger("arise_i")

try:
    from plugin_loader import ClassifierPlugin, classify_with_plugins, load_plugins
    _PLUGINS_AVAILABLE = True
except ImportError:  # pragma: no cover — only missing during isolated unit tests
    _PLUGINS_AVAILABLE = False
    ClassifierPlugin = None  # type: ignore[assignment,misc]
    def classify_with_plugins(path, plugins): return None  # type: ignore[misc]
    def load_plugins(plugin_dir=None): return []  # type: ignore[misc]

try:
    from classifier import SmartClassifier, get_classifier
    _CLASSIFIER_AVAILABLE = True
except ImportError:
    _CLASSIFIER_AVAILABLE = False
    SmartClassifier = None   # type: ignore[assignment,misc]
    get_classifier  = None   # type: ignore[assignment,misc]

try:
    from learning_store import LearningStore
    _LEARNING_AVAILABLE = True
except ImportError:
    _LEARNING_AVAILABLE = False
    LearningStore = None     # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Terminal colour helpers
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    """Return True only when stdout is a real interactive terminal.

    Automatically disabled when output is piped, redirected, or run in CI —
    preventing garbled escape codes in logs and scripts.
    """
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class Color:
    """ANSI colour codes, auto-disabled when stdout isn't a TTY."""
    _on = _supports_color()

    CYAN   = "\033[96m"  if _on else ""
    GREEN  = "\033[92m"  if _on else ""
    YELLOW = "\033[93m"  if _on else ""
    RED    = "\033[91m"  if _on else ""
    BOLD   = "\033[1m"   if _on else ""
    DIM    = "\033[2m"   if _on else ""
    RESET  = "\033[0m"   if _on else ""

    @staticmethod
    def strip(text: str) -> str:
        """Remove all ANSI codes from a string (for plain-text log files)."""
        import re
        return re.sub(r"\033\[[0-9;]*m", "", text)


# Enable ANSI on Windows cmd.exe if needed
if os.name == "nt":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Non-fatal if ctypes fails


# ---------------------------------------------------------------------------
# Banner & boot sequence
# ---------------------------------------------------------------------------

BANNER = r"""
   __  __     _    ____  _  __      ___
  |  \/  |   / \  |  _ \| |/ /     |_ _|
  | |\/| |  / _ \ | |_) | ' /       | |
  | |  | | / ___ \|  _ <| . \       | |
  |_|  |_|/_/   \_\_| \_\_|\_\     |___|

        A U T O N O M O U S   F I L E
           O R G A N I Z A T I O N   U N I T
"""


def boot_sequence(dry_run: bool = False) -> None:
    """Print a short JARVIS-style startup sequence before the run begins."""
    print(f"{Color.CYAN}{Color.BOLD}{BANNER}{Color.RESET}")
    mode_label = (
        f"{Color.YELLOW}[SIMULATION MODE — no files will be moved]{Color.RESET}"
        if dry_run
        else f"{Color.GREEN}[LIVE MODE]{Color.RESET}"
    )
    steps = [
        "Initializing ARISE-I core systems...",
        "Calibrating file classification matrix...",
        f"Systems online. Running in {mode_label}",
    ]
    for step in steps:
        print(f"{Color.YELLOW}>> {step}{Color.RESET}")
        time.sleep(0.35)
    print()


# ---------------------------------------------------------------------------
# Built-in category → extension mappings (the fallback defaults)
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Images":        [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".heic"],
    "Documents":     [".doc", ".docx", ".txt", ".rtf", ".odt", ".md"],
    "PDFs":          [".pdf"],
    "Spreadsheets":  [".xls", ".xlsx", ".csv", ".ods"],
    "Presentations": [".ppt", ".pptx", ".odp"],
    "Videos":        [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "Music":         [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Archives":      [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    "Code":          [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs",
                      ".sh", ".json", ".yaml", ".yml", ".toml", ".xml", ".rb", ".php"],
    "Installers":    [".exe", ".msi", ".dmg", ".apk", ".deb", ".rpm"],
    "Fonts":         [".ttf", ".otf", ".woff", ".woff2"],
    "Ebooks":        [".epub", ".mobi", ".azw3"],
}


# ---------------------------------------------------------------------------
# Config file loader
# ---------------------------------------------------------------------------

def load_categories(config_path: Path | None) -> dict[str, list[str]]:
    """Load category→extension mappings from a YAML config file.

    Falls back to DEFAULT_CATEGORIES if no config file is found or the
    path given doesn't exist.  The config format is:

        Images:
          - .jpg
          - .png
        MyCustomFolder:
          - .xyz

    Any category defined in the config **fully replaces** the defaults.
    To merge with defaults, the user should copy the defaults into their config.
    """
    if config_path is None:
        # Auto-detect in CWD with absolute path resolution
        auto = Path.cwd() / "arise-i.config.yaml"
        auto = auto.resolve()  # Resolve symlinks
        if auto.exists():
            config_path = auto

    if config_path and config_path.exists():
        # Resolve to absolute path to prevent symlink issues
        config_path = config_path.resolve()
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError, PermissionError) as exc:
            print(
                f"{Color.YELLOW}>> Warning: config file could not be loaded ({exc}); "
                f"using built-in defaults.{Color.RESET}\n"
            )
            return DEFAULT_CATEGORIES

        if isinstance(data, dict):
            print(
                f"{Color.CYAN}>> Config loaded from: {config_path}{Color.RESET}\n"
            )
            return data
        else:
            print(
                f"{Color.YELLOW}>> Warning: config file malformed (expected a YAML mapping); "
                f"using built-in defaults.{Color.RESET}\n"
            )

    return DEFAULT_CATEGORIES


# ---------------------------------------------------------------------------
# Extension → category fast-lookup map
# ---------------------------------------------------------------------------

def _sanitize_category_name(name: str) -> str:
    """Sanitize category names to prevent path traversal and injection.
    
    Removes dangerous characters and path traversal sequences like '..'
    to ensure category names are safe for path construction.
    """
    import re
    # Remove path traversal sequences and dangerous characters
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    name = name.replace('..', '')
    name = name.strip('. ')
    # Ensure name is not empty after sanitization
    return name if name else "Others"

def build_extension_map(categories: dict[str, list[str]]) -> dict[str, str]:
    """Flip {folder: [ext, ext, ...]} into {ext: folder} for O(1) lookup."""
    ext_map: dict[str, str] = {}
    for folder, extensions in categories.items():
        safe_folder = _sanitize_category_name(folder)
        for ext in extensions:
            ext_map[ext.lower()] = safe_folder
    return ext_map


# ---------------------------------------------------------------------------
# Duplicate-safe destination path
# ---------------------------------------------------------------------------

def get_unique_destination(dest_folder: Path, filename: str) -> Path:
    """Return a path that won't overwrite an existing file.

    If ``photo.jpg`` already exists in ``dest_folder``, this returns
    ``photo (1).jpg``, then ``photo (2).jpg``, and so on.  Nothing is
    ever silently clobbered.
    
    Performance: Caches existing filenames in the destination folder to avoid
    repeated filesystem checks for large file sets.
    """
    dest_path = dest_folder / filename
    if not dest_path.exists():
        return dest_path

    stem, suffix = Path(filename).stem, Path(filename).suffix
    
    # Cache existing filenames for performance with large file sets
    try:
        existing_files = {f.stem for f in dest_folder.glob(f"{stem}*{suffix}")}
    except OSError:
        # Fallback to individual checks if glob fails
        existing_files = set()
    
    counter = 1
    MAX_ATTEMPTS = 1000
    while counter <= MAX_ATTEMPTS:
        candidate_name = f"{stem} ({counter}){suffix}"
        candidate_stem = f"{stem} ({counter})"
        if candidate_stem not in existing_files:
            dest_path = dest_folder / candidate_name
            # Double-check existence to be safe
            if not dest_path.exists():
                return dest_path
        counter += 1
    raise RuntimeError(f"Cannot generate unique filename after {MAX_ATTEMPTS} attempts")


# ---------------------------------------------------------------------------
# Persistent run log (JSON manifest for undo)
# ---------------------------------------------------------------------------

LOG_MANIFEST = ".arise-i-log.json"


def _load_manifest(target_dir: Path) -> list[dict]:
    """Load the full history manifest from disk (list of run entries)."""
    manifest_path = target_dir / LOG_MANIFEST
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                # Validate each entry has required fields
                valid_data = []
                for entry in data:
                    if isinstance(entry, dict) and "timestamp" in entry and "moves" in entry:
                        if isinstance(entry["moves"], list):
                            valid_data.append(entry)
                        else:
                            logger.warning("Invalid manifest entry with non-list moves - skipping")
                    else:
                        logger.warning("Invalid manifest entry structure - skipping")
                return valid_data
            else:
                logger.warning("Manifest is not a list - returning empty history")
                return []
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load manifest: %s - returning empty history", exc)
            return []
    return []


def _save_manifest(target_dir: Path, history: list[dict]) -> None:
    """Persist the updated manifest to disk using atomic file operations."""
    manifest_path = target_dir / LOG_MANIFEST
    temp_path = manifest_path.with_suffix('.tmp')
    
    try:
        # Write to temporary file first
        with open(temp_path, "w", encoding="utf-8") as fh:
            json.dump(history, fh, indent=2, default=str)
            fh.flush()  # Ensure data is written to disk
            os.fsync(fh.fileno())  # Force write to disk
        
        # Atomic rename - this is atomic on POSIX systems and reasonably safe on Windows
        temp_path.replace(manifest_path)
        
    except Exception as exc:
        logger.error("Failed to save manifest: %s", exc)
        # Clean up temp file if it exists
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise


def _record_run(target_dir: Path, moves: list[dict]) -> None:
    """Append a new run entry to the JSON manifest.

    Each entry looks like:
        {
          "timestamp": "2025-01-01T12:00:00",
          "moves": [
              {"src": "/original/path.jpg", "dest": "/Images/path.jpg"},
              ...
          ]
        }
    """
    if not moves:
        return  # nothing to record
    history = _load_manifest(target_dir)
    history.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "moves": moves,
        }
    )
    try:
        _save_manifest(target_dir, history)
    except Exception as exc:
        logger.error("Failed to record run in manifest: %s", exc)
        print(f"  {Color.YELLOW}⚠ Warning: Could not record run in manifest.{Color.RESET}")


# ---------------------------------------------------------------------------
# Plain-text audit log
# ---------------------------------------------------------------------------

# Files ARISE-I generates itself — never move these during a scan
_OWN_FILES = {"arise-i.log", LOG_MANIFEST}


def _setup_file_logger(target_dir: Path, dry_run: bool = False) -> logging.Logger:
    """Configure a logger that appends timestamped entries to arise-i.log.

    In dry-run mode a NullHandler is used so no log file is created on disk.
    """
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # A NullHandler prevents dry-run messages leaking to the root logger while
    # ensuring a preview never creates a log file.
    if not any(isinstance(handler, logging.NullHandler) for handler in logger.handlers):
        logger.addHandler(logging.NullHandler())

    # Only one ARISE-I file handler is active at a time.  This prevents a
    # later run against another folder from writing into the previous folder's
    # audit log, and removes live logging entirely for dry runs.
    for handler in logger.handlers[:]:
        if getattr(handler, "_arise_i_file_handler", False):
            logger.removeHandler(handler)
            handler.close()

    if not dry_run:
        log_file = target_dir / "arise-i.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler._arise_i_file_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
    return logger


# ---------------------------------------------------------------------------
# Stats tracker
# ---------------------------------------------------------------------------

class Stats:
    """Accumulate per-category file counts and total byte sizes."""

    def __init__(self) -> None:
        # {category: {"count": int, "bytes": int}}
        self._data: dict[str, dict[str, int]] = {}
        self.skipped: int = 0    # files skipped due to errors / broken symlinks
        self.errors:  int = 0    # files that raised an exception during move

    def record(self, category: str, size_bytes: int) -> None:
        bucket = self._data.setdefault(category, {"count": 0, "bytes": 0})
        bucket["count"] += 1
        bucket["bytes"] += size_bytes

    def total_files(self) -> int:
        return sum(v["count"] for v in self._data.values())

    def total_bytes(self) -> int:
        return sum(v["bytes"] for v in self._data.values())

    def print_summary(self) -> None:
        """Print a JARVIS-style diagnostics table."""
        if not self._data:
            print(f"{Color.YELLOW}>> No files were processed.{Color.RESET}")
            return

        # Sort categories by file count descending
        sorted_cats = sorted(
            self._data.items(), key=lambda kv: kv[1]["count"], reverse=True
        )

        # Column widths
        cat_w   = max(len(cat) for cat, _ in sorted_cats)
        count_w = 7
        size_w  = 12

        # Total inner width: 2 (indent) + cat_w + 2 + count_w + 2 + size_w
        inner_w = cat_w + count_w + size_w + 10

        # All three horizontal rules share the same width
        border = f"{Color.DIM}{'─' * inner_w}{Color.RESET}"

        # Top header — padded to match the dynamic inner width
        header_label = "─ ARISE-I MISSION DEBRIEF "
        header_fill  = "─" * max(0, inner_w - len(header_label) - 2)  # -2 for ┌ and ┐
        print(f"\n{Color.CYAN}{Color.BOLD}┌{header_label}{header_fill}┐{Color.RESET}")
        print(border)
        print(
            f"  {Color.BOLD}{'Category':<{cat_w}}  {'Files':>{count_w}}  {'Total Size':>{size_w}}{Color.RESET}"
        )
        print(border)

        for cat, data in sorted_cats:
            count = data["count"]
            size  = _human_size(data["bytes"])
            print(
                f"  {Color.GREEN}{cat:<{cat_w}}{Color.RESET}"
                f"  {count:>{count_w}}"
                f"  {size:>{size_w}}"
            )

        print(border)
        print(
            f"  {Color.BOLD}{'TOTAL':<{cat_w}}{Color.RESET}"
            f"  {self.total_files():>{count_w}}"
            f"  {_human_size(self.total_bytes()):>{size_w}}"
        )
        if self.skipped:
            print(f"\n  {Color.YELLOW}\u26a0  {self.skipped} file(s) skipped (broken symlinks){Color.RESET}")
        if self.errors:
            print(f"  {Color.RED}\u2717  {self.errors} file(s) failed to move (check arise-i.log){Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}└{'─' * inner_w}┘{Color.RESET}")


def _human_size(num_bytes: int) -> str:
    """Convert bytes to human-readable string (KB, MB, GB)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024  # type: ignore[assignment]
    return f"{num_bytes:.1f} PB"


# ---------------------------------------------------------------------------
# Core: organize a folder
# ---------------------------------------------------------------------------

def organize_folder(
    target_dir: str,
    dry_run: bool = False,
    categories: dict[str, list[str]] | None = None,
    log_callback=None,
    plugins: "list | None" = None,
    confidence_threshold: float = 0.75,
    learning_store=None,
) -> Stats:
    """Scan *target_dir* and move files into category sub-folders.

    Parameters
    ----------
    target_dir : str
        Path to the folder to organise.
    dry_run : bool
        When True, print what *would* happen but move nothing.
    categories : dict, optional
        Category → extension mapping.  Defaults to ``DEFAULT_CATEGORIES``.
    log_callback : callable(str), optional
        If provided, called with a plain-text message for every file event
        (relocation, simulation, skip, error).  Used by the GUI to populate
        the live log feed.  No-op when None — all CLI behaviour unchanged.
    plugins : list, optional
        Pre-loaded classifier plugin callables (from ``plugin_loader.load_plugins``).
        Each plugin is tried in order before falling back to the extension map.
        Pass ``None`` (default) to skip all plugin logic.

    Returns
    -------
    Stats
        A Stats object carrying per-category counts and sizes, useful for
        testing as well as the printed summary.
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES

    target_path = Path(target_dir).expanduser().resolve()

    if not target_path.exists():
        print(f"{Color.RED}✗ Folder not found: {target_path}{Color.RESET}")
        return Stats()

    logger = _setup_file_logger(target_path, dry_run=dry_run)
    run_mode = "DRY-RUN" if dry_run else "LIVE"
    logger.info("=" * 60)
    logger.info("ARISE-I run started | mode=%s | target=%s", run_mode, target_path)

    ext_map = build_extension_map(categories)
    stats   = Stats()
    moves: list[dict] = []  # populated only during live runs (for undo log)

    # Instantiate AI classifier (falls back gracefully if classifier.py absent)
    _smart: SmartClassifier | None = None
    if _CLASSIFIER_AVAILABLE and get_classifier is not None:
        try:
            _smart = get_classifier(categories, confidence_threshold)
        except Exception as _exc:
            logger.warning("SmartClassifier init failed (%s) — using ext_map fallback.", _exc)

    print(f"{Color.CYAN}ARISE-I >> Target acquired: {target_path}{Color.RESET}\n")

    # Sort entries for deterministic, reproducible output across runs
    # Use case-insensitive sorting but cache the lowercase names for performance
    items = sorted(target_path.iterdir(), key=lambda p: p.name.lower())

    for item in items:
        # Skip ARISE-I's own metadata/log files so they never get relocated
        if item.name in _OWN_FILES:
            continue

        # Hidden files are commonly application settings, OS metadata, or
        # developer configuration. Moving them is surprising and can break a
        # user's environment, so ARISE-I leaves them exactly where they are.
        if item.name.startswith("."):
            logger.info("Skipped hidden file: %s", item.name)
            continue

        # --- Skip directories (including ones ARISE-I already created) -------
        if item.is_dir():
            continue

        # --- Skip broken symlinks (symlink exists, target doesn't) ----------
        if item.is_symlink() and not item.exists():
            msg = f"Skipped broken symlink: {item.name}"
            print(f"  {Color.YELLOW}⚠  {msg}{Color.RESET}")
            logger.warning(msg)
            if log_callback:
                log_callback(f"⚠  {msg}")
            stats.skipped += 1
            continue

        # --- Determine category ---------------------------------------------
        # Priority: plugins → SmartClassifier (AI) → ext_map fallback
        plugin_category: str | None = None
        if plugins:
            plugin_category = classify_with_plugins(item, plugins)

        # AI classification path
        _confidence = 1.0
        _badge      = "PLUGIN"
        _layer      = "plugin"
        if plugin_category:
            raw_category = plugin_category
        elif _smart is not None:
            _result      = _smart.classify(item)
            raw_category = _result.category
            _confidence  = _result.confidence
            _badge       = _result.badge
            _layer       = _result.layer
        else:
            # Legacy ext_map fallback (no classifier.py)
            ext          = item.suffix.lower()
            raw_category = ext_map.get(ext, "Others")
            _badge       = "EXT"
            _layer       = "extension"

        category = _sanitize_category_name(raw_category)

        # Try to get file size (safe — file may be 0 bytes or unreadable)
        try:
            size_bytes = item.stat().st_size
        except OSError:
            size_bytes = 0

        dest_folder = target_path / category
        dest_path   = get_unique_destination(dest_folder, item.name)

        if dry_run:
            dedup_note = (
                f" → renamed to {dest_path.name}"
                if dest_path.name != item.name
                else ""
            )
            print(
                f"  {Color.YELLOW}[SIMULATION]{Color.RESET} "
                f"{item.name}  {Color.DIM}→{Color.RESET}  "
                f"{Color.CYAN}{category}/{Color.RESET}{dedup_note}"
                f"  {Color.DIM}[{_badge} {_confidence:.0%}]{Color.RESET}"
            )
            logger.info("[DRY-RUN] Would move: %s -> %s/ (conf=%.2f layer=%s)",
                        item.name, category, _confidence, _layer)
            if log_callback:
                log_callback(f"[SIM]  {item.name}  →  {category}/{dedup_note}  [{_badge} {_confidence:.0%}]")
            stats.record(category, size_bytes)
            continue

        # --- Live run: actually move the file --------------------------------
        try:
            dest_folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(dest_path))

            dedup_note = (
                f" (renamed: {dest_path.name})"
                if dest_path.name != item.name
                else ""
            )
            # Colour-code uncertain (Review) moves differently
            _is_review = (category == SmartClassifier.REVIEW_FOLDER
                          if SmartClassifier else False)
            _color = Color.YELLOW if _is_review else Color.GREEN
            _icon  = "⚠" if _is_review else "✓"
            print(
                f"  {_color}{_icon} Relocated:{Color.RESET} "
                f"{item.name}  →  {Color.CYAN}{category}/{Color.RESET}"
                f"  {Color.DIM}[{_badge} {_confidence:.0%}]{dedup_note}{Color.RESET}"
            )
            logger.info("Moved: %s -> %s (conf=%.2f layer=%s)",
                        item, dest_path, _confidence, _layer)
            if log_callback:
                log_callback(f"{_icon}  {item.name}  →  {category}/{dedup_note}  [{_badge} {_confidence:.0%}]")
            stats.record(category, size_bytes)

            # Record the move for undo support
            moves.append({"src": str(item), "dest": str(dest_path),
                          "confidence": _confidence, "layer": _layer})

            # Feed learning store (non-blocking — errors are logged, never raised)
            if learning_store is not None:
                try:
                    learning_store.record(
                        path=item,
                        predicted=category,
                        confirmed=category,   # will be corrected via Review tab
                        confidence=_confidence,
                        layer=_layer,
                    )
                except Exception as _le:
                    logger.debug("Learning store record failed: %s", _le)

        except PermissionError as exc:
            msg = f"Permission denied — skipped {item.name}: {exc}"
            print(f"  {Color.RED}✗ {msg}{Color.RESET}")
            logger.error(msg)
            if log_callback:
                log_callback(f"✗  {msg}")
            stats.errors += 1

        except OSError as exc:
            msg = f"OS error moving {item.name}: {exc}"
            print(f"  {Color.RED}✗ {msg}{Color.RESET}")
            logger.error(msg)
            if log_callback:
                log_callback(f"✗  {msg}")
            stats.errors += 1

    # --- Persist undo manifest (live runs only) ----------------------------
    if not dry_run and moves:
        _record_run(target_path, moves)
        logger.info("Undo manifest updated: %d move(s) logged.", len(moves))

    logger.info(
        "Run complete | moved=%d | skipped=%d | errors=%d",
        stats.total_files(), stats.skipped, stats.errors,
    )

    return stats


# ---------------------------------------------------------------------------
# Undo: reverse the last run
# ---------------------------------------------------------------------------

def undo_last_run(target_dir: str) -> None:
    """Read the most recent run from the JSON manifest and reverse every move.

    Files are moved back to their original locations.  If the original
    location no longer exists (e.g. the parent folder was deleted), the
    error is reported and the remaining files continue to be restored.
    """
    target_path = Path(target_dir).expanduser().resolve()
    history     = _load_manifest(target_path)

    if not history:
        print(
            f"{Color.YELLOW}>> No ARISE-I run history found in {target_path}.{Color.RESET}\n"
            f"{Color.DIM}   (expected: {target_path / LOG_MANIFEST}){Color.RESET}"
        )
        return

    last_run  = history[-1]
    timestamp = last_run.get("timestamp", "unknown time")
    moves     = last_run.get("moves", [])

    print(
        f"{Color.CYAN}ARISE-I >> Initiating rollback of run from {timestamp}.{Color.RESET}\n"
        f"{Color.DIM}          {len(moves)} file(s) to restore.{Color.RESET}\n"
    )

    logger   = _setup_file_logger(target_path)
    logger.info("UNDO started for run timestamp=%s", timestamp)

    restored = 0
    failed   = 0

    # Reverse the list so that any deduplication counters unwind correctly
    for move in reversed(moves):
        src  = Path(move["src"])   # where the file originally was
        dest = Path(move["dest"])  # where ARISE-I moved it to

        if not dest.exists():
            msg = f"Cannot restore — file no longer at destination: {dest}"
            print(f"  {Color.RED}✗ {msg}{Color.RESET}")
            logger.error(msg)
            failed += 1
            continue

        try:
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(src))
            print(
                f"  {Color.GREEN}✓ Restored:{Color.RESET} "
                f"{dest.name}  →  {src.parent}/"
            )
            logger.info("Restored: %s -> %s", dest, src)
            restored += 1

        except OSError as exc:
            msg = f"Error restoring {dest.name}: {exc}"
            print(f"  {Color.RED}✗ {msg}{Color.RESET}")
            logger.error(msg)
            failed += 1

    # Remove this run entry from history now that it's been undone
    if restored > 0:
        history.pop()
        try:
            _save_manifest(target_path, history)
        except Exception as exc:
            logger.error("Failed to update manifest after undo: %s", exc)
            print(f"  {Color.YELLOW}⚠ Warning: Could not update manifest after undo.{Color.RESET}")

    print(
        f"\n{Color.CYAN}{Color.BOLD}"
        f"ARISE-I >> Rollback complete.  "
        f"{restored} restored, {failed} failed."
        f"{Color.RESET}"
    )
    logger.info("UNDO complete | restored=%d | failed=%d", restored, failed)



# ---------------------------------------------------------------------------
# Named entry point (used by pyproject.toml [project.scripts])
# ---------------------------------------------------------------------------

def _cli_main() -> None:  # pragma: no cover
    """Entry point registered as the `arise-i` console script."""
    # Re-use the if __name__ == "__main__" block by importing this function
    # and calling it from the installed `arise-i` script.
    import runpy
    runpy.run_module("file_organizer", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ARISE-I: Autonomous File Organization Unit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python file_organizer.py --dry-run              # safe preview
  python file_organizer.py --path ~/Downloads     # organise Downloads
  python file_organizer.py --undo                 # reverse the last run
  python file_organizer.py --config my.yaml       # custom category map
  python file_organizer.py --watch                # daemon: watch & sort live
  python file_organizer.py --watch --dry-run      # daemon: watch & preview
  python file_organizer.py --watch --debounce 5   # wait 5s of quiet before sorting
        """,
    )
    parser.add_argument(
        "--path", default="~/Downloads",
        help="Folder to organise or watch (default: ~/Downloads)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would happen without moving any files (default-safe)",
    )
    parser.add_argument(
        "--undo", action="store_true",
        help="Reverse the most recent ARISE-I run in the target folder",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Run as a daemon: watch --path and sort files as they arrive",
    )
    parser.add_argument(
        "--debounce", type=float, default=2.0,
        help="Seconds of FS quiet before triggering a sort in watch mode (default: 2.0)",
    )
    parser.add_argument(
        "--config", default=None, type=Path,
        help="Path to a arise-i.config.yaml file for custom category mappings",
    )
    args = parser.parse_args()

    boot_sequence(dry_run=args.dry_run)

    # Load plugins once — shared across all modes
    active_plugins = load_plugins() if _PLUGINS_AVAILABLE else []
    if active_plugins:
        print(
            f"{Color.CYAN}>> {len(active_plugins)} classifier plugin(s) active.{Color.RESET}\n"
        )

    if args.watch:
        # Import lazily so watchdog is only required when --watch is used
        from file_watcher import WATCHDOG_AVAILABLE as _WD_OK, watch_folder
        if not _WD_OK:
            print(
                f"{Color.RED}✗ watchdog is required for --watch mode.\n"
                f"  Run:  pip install watchdog{Color.RESET}"
            )
            sys.exit(1)
        categories = load_categories(args.config)
        watch_folder(
            target_dir=args.path,
            debounce=args.debounce,
            dry_run=args.dry_run,
            categories=categories,
            plugins=active_plugins,
        )
    elif args.undo:
        undo_last_run(args.path)
    else:
        categories = load_categories(args.config)
        stats      = organize_folder(
            args.path,
            dry_run=args.dry_run,
            categories=categories,
            plugins=active_plugins,
        )
        stats.print_summary()

        if args.dry_run:
            print(
                f"\n{Color.YELLOW}>> Simulation complete — "
                f"zero filesystem changes made.{Color.RESET}"
            )
        else:
            print(
                f"\n{Color.GREEN}>> Run logged.  "
                f"Use --undo to reverse this operation.{Color.RESET}"
            )
