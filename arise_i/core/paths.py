"""Folder-name sanitising shared by the organizer and the plugin loader."""

import re

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Device names Windows refuses as file or folder names, with or without an
# extension ("CON", "con.txt", "COM1"...).  Compared case-insensitively.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_folder_name(name: str, fallback: str | None = None) -> str | None:
    """Return *name* made safe to use as a single folder name.

    Strips path separators and other characters no filesystem accepts,
    removes ``..`` traversal, trims dots and spaces, and suffixes Windows
    device names (``Con`` → ``Con_``) so the folder can be created on every
    OS.  Returns *fallback* when nothing usable is left.
    """
    name = _UNSAFE_CHARS.sub("", name)
    name = name.replace("..", "")
    name = name.strip(". ")
    if not name:
        return fallback
    if name.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        name += "_"
    return name
