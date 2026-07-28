"""
tests/conftest.py
-----------------
Shared pytest configuration for the ARISE-I test suite.

Ensures the project root is on sys.path so that imports like
``from file_organizer import ...`` work regardless of how pytest is invoked
(from the project root, from the tests/ subdirectory, or in CI).
"""

import sys
from pathlib import Path

# Insert the project root (one level above this file) at the front of the path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
