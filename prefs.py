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
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("arise_i.prefs")

# ~/.arise-i/prefs.json
PREFS_DIR: Path  = Path.home() / ".arise-i"
PREFS_FILE: Path = PREFS_DIR / "prefs.json"

_DEFAULTS: dict = {
    "onboarding_done": False,
    "last_folder":     str(Path.home() / "Downloads"),
    "debounce":        2.0,
    "window_geometry": "",
    "theme":           "light",
}


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
                prefs.update(data)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load prefs: %s — using defaults.", exc)
    return prefs


def save_prefs(data: dict) -> None:
    """Persist *data* to ~/.arise-i/prefs.json atomically.

    Creates the directory if it doesn't exist.
    Never raises — a failed save is logged but never crashes the app.
    """
    try:
        PREFS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = PREFS_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(PREFS_FILE)
    except Exception as exc:
        logger.warning("Could not save prefs: %s", exc)


def set_pref(key: str, value) -> None:
    """Update a single preference key and save immediately."""
    prefs = load_prefs()
    prefs[key] = value
    save_prefs(prefs)


def get_pref(key: str, default=None):
    """Read a single preference key."""
    return load_prefs().get(key, default)
