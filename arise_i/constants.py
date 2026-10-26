"""File and folder names shared by every ARISE-I module."""

from pathlib import Path

# Per target folder
LOG_MANIFEST = ".arise-i-log.json"    # undo history
LOG_FILE = "arise-i.log"              # plain-text audit log
CONFIG_FILENAME = "arise-i.config.yaml"
REVIEW_FOLDER = "__Review__"          # low-confidence quarantine

# Per user
APP_DIR = Path.home() / ".arise-i"
