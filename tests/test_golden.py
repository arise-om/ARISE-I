"""
tests/test_golden.py
--------------------
Cross-engine parity: tests/fixtures/classification_golden.json lists file
names and where a live run must leave each one.  The Android engine runs
the same fixture (android/engine ClassifierParityTest), so a rule change
that only lands in one engine fails one of the two suites.

MIME lookups are pinned to the exported table so results don't depend on
the host's /etc/mime.types.  Regenerate expectations after an intentional
rule change with:

    ARISE_REGEN_GOLDEN=1 python -m pytest tests/test_golden.py
"""

import json
import os
import sys
from pathlib import Path

import pytest

from arise_i.core import classifier
from arise_i.core.organizer import LOG_MANIFEST, organize_folder

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from export_rules import MIME_BY_EXTENSION  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "classification_golden.json"


def _pinned_guess_type(path, strict=True):
    suffix = Path(str(path)).suffix.lower()
    return MIME_BY_EXTENSION.get(suffix), None


def test_golden_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(classifier.mimetypes, "guess_type", _pinned_guess_type)
    monkeypatch.setattr(classifier, "_FILETYPE_AVAILABLE", False)
    monkeypatch.setattr(classifier, "_SKLEARN_AVAILABLE", False)
    monkeypatch.setattr(classifier, "_singleton", None)

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for rel in fixture["preexisting"]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("old", encoding="utf-8")
    for case in fixture["cases"]:
        (tmp_path / case["name"]).write_text("x", encoding="utf-8")

    organize_folder(str(tmp_path))

    moved = {
        rel for rel in (p.relative_to(tmp_path).as_posix()
                        for p in tmp_path.rglob("*") if p.is_file())
        # The run's own undo manifest is output, not one of the inputs.
        if rel not in fixture["preexisting"] and rel != LOG_MANIFEST
    }

    if os.environ.get("ARISE_REGEN_GOLDEN"):
        # Dedup renames "dup.pdf" to "dup (1).pdf", hence "renamed_to".
        for case in fixture["cases"]:
            case["expect"] = next(
                (rel for rel in sorted(moved)
                 if rel.rsplit("/", 1)[-1] == case["name"]
                 or rel.rsplit("/", 1)[-1] == case.get("renamed_to")),
                None,
            )
        FIXTURE.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        pytest.skip("golden fixture regenerated")

    expected = sorted(case["expect"] for case in fixture["cases"])
    assert sorted(moved) == expected
