"""
tests/test_prefs.py
-------------------
Preferences survive bad data on disk and concurrent updates.
"""

import json
import threading

import pytest

from arise_i.core import prefs


@pytest.fixture(autouse=True)
def prefs_file(tmp_path, monkeypatch):
    path = tmp_path / "prefs.json"
    monkeypatch.setattr(prefs, "PREFS_FILE", path)
    return path


def test_defaults_when_missing():
    assert prefs.load_prefs()["theme"] == "light"


def test_corrupt_file_falls_back_to_defaults(prefs_file):
    prefs_file.write_text("{not json")
    assert prefs.load_prefs()["debounce"] == 2.0


def test_values_of_the_wrong_type_are_ignored(prefs_file):
    prefs_file.write_text(json.dumps({
        "debounce": "fast", "animations": "yes", "theme": "dark", "window_geometry": 5,
        "custom": [1, 2],
    }))
    loaded = prefs.load_prefs()
    assert loaded["debounce"] == 2.0
    assert loaded["animations"] is True
    assert loaded["theme"] == "dark"
    assert loaded["window_geometry"] == ""
    assert loaded["custom"] == [1, 2]


def test_integer_debounce_is_accepted(prefs_file):
    prefs_file.write_text(json.dumps({"debounce": 3}))
    assert prefs.load_prefs()["debounce"] == 3


def test_concurrent_set_pref_keeps_every_key(prefs_file):
    threads = [threading.Thread(target=prefs.set_pref, args=(f"k{i}", i)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    saved = json.loads(prefs_file.read_text())
    assert all(saved[f"k{i}"] == i for i in range(20))
    assert not list(prefs_file.parent.glob("*.tmp"))
