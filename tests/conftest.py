"""
tests/conftest.py
-----------------
Shared pytest configuration for the ARISE-I test suite.

Ensures the project root is on sys.path so that ``import arise_i`` works
even without ``pip install -e .`` (from the project root, from the tests/
subdirectory, or in CI).

It also points the home directory at a throwaway folder *before* any
ARISE-I module is imported, so the suite never reads or writes the real
``~/.arise-i`` (prefs, feedback log, trained model, plugins).  Without this a
developer's own trained model.pkl would silently change classifier results.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

_TEST_HOME = Path(tempfile.mkdtemp(prefix="arise-i-test-home-"))
os.environ["HOME"] = str(_TEST_HOME)
os.environ["USERPROFILE"] = str(_TEST_HOME)

# Insert the project root (one level above this file) at the front of the path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def make_broken_symlink():
    """Create a dangling symlink, or skip where the OS forbids symlinks.

    Windows only allows unprivileged symlinks with Developer Mode enabled.
    """
    def _make(link: Path, target: str = "/nonexistent/path") -> Path:
        try:
            link.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"cannot create symlinks here ({exc.strerror}); "
                        "on Windows enable Developer Mode")
        return link
    return _make
