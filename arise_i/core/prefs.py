"""
ARISE-I — Preferences Manager
------------------------------
Autonomous File Organization Unit: User Preferences.
Built by Om Deshmukh // Ironlabs.tech

Persists user settings between sessions to ~/.arise-i/prefs.json.

Keys used by the GUI:
    onboarding_done  : bool   — True after first-run wizard completes
    last_folder      : str    — Last folder the user organised
    debounce         : float  — Auto-sort debounce seconds
    window_geometry  : str    — Last window geometry string (e.g. "860x600+100+50")
    theme            : str    — "light" or "dark" (toggled from the GUI header)
    animations       : bool   — False = reduced motion (View → Animations)
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path

from arise_i.constants import APP_DIR

logger = logging.getLogger("arise_i.prefs")

# ~/.arise-i/prefs.json
PREFS_DIR: Path  = APP_DIR
PREFS_FILE: Path = PREFS_DIR / "prefs.json"

_DEFAULTS: dict = {
    "onboarding_done": False,
    "last_folder":     str(Path.home() / "Downloads"),
    "debounce":        2.0,
    "window_geometry": "",
    "theme":           "light",
    "animations":      True,
}

# Serialises read-modify-write updates from the GUI and its worker threads
_LOCK = threading.RLock()


def _valid(key: str, value) -> bool:
    """True if *value* has the type the app expects for a known *key*."""
    default = _DEFAULTS.get(key)
    if default is None:
        return True  # unknown keys are kept as-is
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


def load_prefs() -> dict:
    """Load preferences from disk, merging with defaults for any missing keys.

    Never raises — returns defaults on any error so the app always starts.
    """
    prefs = dict(_DEFAULTS)
    if PREFS_FILE.exists():
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for key, value in data.items():
                    if _valid(key, value):
                        prefs[key] = value
                    else:
                        logger.warning("Ignoring invalid pref %s=%r", key, value)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load prefs: %s — using defaults.", exc)
    return prefs


def save_prefs(data: dict) -> None:
    """Persist *data* to ~/.arise-i/prefs.json atomically.

    Creates the directory if it doesn't exist.
    Never raises — a failed save is logged but never crashes the app.
    """
    tmp = None
    try:
        with _LOCK:
            PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=PREFS_FILE.parent, prefix=".prefs-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, PREFS_FILE)
            tmp = None
    except Exception as exc:
        logger.warning("Could not save prefs: %s", exc)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def set_pref(key: str, value) -> None:
    """Update a single preference key and save immediately."""
    with _LOCK:
        prefs = load_prefs()
        prefs[key] = value
        save_prefs(prefs)


def get_pref(key: str, default=None):
    """Read a single preference key."""
    return load_prefs().get(key, default)
