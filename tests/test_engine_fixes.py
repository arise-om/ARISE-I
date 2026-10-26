"""
tests/test_engine_fixes.py
--------------------------
Regression tests for engine bugs fixed in the v2.2 cleanup: heuristic false
positives, assignment-subject parsing, Windows device names, interrupted and
overlapping runs, undo history that could get stuck, and nested Review folders.
"""

import json
import logging
import threading
from pathlib import Path

import pytest

from arise_i.constants import REVIEW_FOLDER
from arise_i.core import organizer
from arise_i.core.assignment import parse_assignment
from arise_i.core.classifier import SmartClassifier
from arise_i.core.organizer import (
    DEFAULT_CATEGORIES,
    LOG_MANIFEST,
    get_unique_destination,
    organize_folder,
    undo_last_run,
)
from arise_i.core.paths import sanitize_folder_name


@pytest.fixture(autouse=True)
def reset_logger():
    logger = logging.getLogger("arise_i")
    yield
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


@pytest.fixture
def clf():
    return SmartClassifier(DEFAULT_CATEGORIES, model_path=Path("missing.pkl"))


# ── Classifier heuristics ───────────────────────────────────────────────────

class TestHeuristicWordBoundaries:

    @pytest.mark.parametrize("name", ["blog_post.xyz", "ghost.xyz", "keynote.xyz",
                                      "denotes_v2.dat", "foreground.xyz"])
    def test_substrings_inside_words_do_not_match(self, clf, name):
        assert clf._by_heuristics(Path(name)).category == "Others"

    @pytest.mark.parametrize("name, category", [
        ("lecture_notes.xyz", "Documents"),
        ("my-cv.xyz", "Documents"),
        ("Invoices_2024.xyz", "Documents"),
        ("game OST.xyz", "Music"),
        ("Screenshot_2024-01-01.xyz", "Images"),
    ])
    def test_whole_words_still_match(self, clf, name, category):
        assert clf._by_heuristics(Path(name)).category == category


# ── Assignment parsing ───────────────────────────────────────────────────────

class TestAssignmentSubject:

    def test_copy_suffix_is_not_part_of_the_subject(self):
        info = parse_assignment(Path("Lab 2 - Bio (1).pdf"))
        assert info.subject == "Bio"

    def test_subject_first_copy_suffix(self):
        info = parse_assignment(Path("Math - Assignment 4 (2).pdf"))
        assert (info.subject, info.number) == ("Math", 4)

    def test_second_separator_ends_the_subject(self):
        info = parse_assignment(Path("Assignment 1 - Calculus - Solutions.pdf"))
        assert info.subject == "Calculus"

    def test_hyphenated_subject_is_kept(self):
        assert parse_assignment(Path("Lab3 - Bio-Chem.docx")).subject == "Bio-Chem"

    def test_no_subject_with_copy_suffix(self):
        info = parse_assignment(Path("Assignment 1 (1).pdf"))
        assert info is not None and info.subject is None

    def test_low_confidence_assignment_is_not_nested(self, tmp_path):
        (tmp_path / "Assignment 1 - Calculus.pdf").write_text("x")
        organize_folder(str(tmp_path), confidence_threshold=0.99)
        assert (tmp_path / REVIEW_FOLDER / "Assignment 1 - Calculus.pdf").exists()
        assert not (tmp_path / "Calculus").exists()


# ── Folder names ─────────────────────────────────────────────────────────────

class TestSanitizeFolderName:

    @pytest.mark.parametrize("name", ["CON", "con", "Nul", "COM1", "lpt9", "aux.txt"])
    def test_windows_device_names_are_suffixed(self, name):
        assert sanitize_folder_name(name) == name + "_"

    def test_ordinary_names_untouched(self):
        assert sanitize_folder_name("Console") == "Console"

    def test_empty_returns_fallback(self):
        assert sanitize_folder_name("../..", fallback="Others") == "Others"

    def test_assignment_subject_con_gets_a_valid_folder(self, tmp_path):
        (tmp_path / "Assignment 1 - Con.pdf").write_text("x")
        organize_folder(str(tmp_path))
        assert (tmp_path / "Con_" / "Assignment 1" / "PDFs" / "Assignment 1 - Con.pdf").exists()


class TestUniqueDestinationGlobChars:

    @pytest.mark.parametrize("name", ["data[1].csv", "what?.txt", "star*.md"])
    def test_glob_metacharacters_in_names(self, tmp_path, name):
        try:
            (tmp_path / name).write_text("x")
        except OSError:
            pytest.skip("filename not allowed on this OS")
        dest = get_unique_destination(tmp_path, name)
        assert dest.name == f"{Path(name).stem} (1){Path(name).suffix}"


# ── Interrupted and overlapping runs ─────────────────────────────────────────

def _manifest(folder: Path) -> list:
    return json.loads((folder / LOG_MANIFEST).read_text())


class TestInterruptedRun:

    def test_unexpected_error_on_one_file_does_not_abort_the_run(self, tmp_path, monkeypatch):
        for name in ("a.jpg", "b.pdf", "c.txt"):
            (tmp_path / name).write_text(name)
        real = organizer._organize_item

        def flaky(item, *args, **kwargs):
            if item.name == "b.pdf":
                raise RuntimeError("boom")
            return real(item, *args, **kwargs)

        monkeypatch.setattr(organizer, "_organize_item", flaky)
        stats = organize_folder(str(tmp_path))

        assert stats.errors == 1
        assert (tmp_path / "b.pdf").exists()
        assert (tmp_path / "Images" / "a.jpg").exists()
        assert len(_manifest(tmp_path)[0]["moves"]) == 2

    def test_interrupt_still_records_files_already_moved(self, tmp_path, monkeypatch):
        for name in ("a.jpg", "b.pdf"):
            (tmp_path / name).write_text(name)
        real = organizer._organize_item

        def interrupted(item, *args, **kwargs):
            if item.name == "b.pdf":
                raise KeyboardInterrupt
            return real(item, *args, **kwargs)

        monkeypatch.setattr(organizer, "_organize_item", interrupted)
        with pytest.raises(KeyboardInterrupt):
            organize_folder(str(tmp_path))

        moves = _manifest(tmp_path)[0]["moves"]
        assert [Path(m["src"]).name for m in moves] == ["a.jpg"]
        undo_last_run(str(tmp_path))
        assert (tmp_path / "a.jpg").exists()


class TestOverlappingRuns:

    def test_parallel_runs_never_lose_a_file(self, tmp_path):
        names = [f"photo{i}.jpg" for i in range(60)]
        for name in names:
            (tmp_path / name).write_text(name)
        # Same names already sorted, so every move needs a "(1)" de-dup name
        (tmp_path / "Images").mkdir()
        for name in names:
            (tmp_path / "Images" / name).write_text("old")

        threads = [threading.Thread(target=organize_folder, args=(str(tmp_path),))
                   for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        sorted_files = list((tmp_path / "Images").iterdir())
        assert len(sorted_files) == 2 * len(names)
        assert sum(len(run["moves"]) for run in _manifest(tmp_path)) == len(names)


# ── Undo history ─────────────────────────────────────────────────────────────

class TestUndoNothingLeft:

    def test_run_with_no_files_left_is_dropped(self, tmp_path):
        (tmp_path / "old.pdf").write_text("old")
        organize_folder(str(tmp_path))                       # run 1
        (tmp_path / "new.jpg").write_text("new")
        organize_folder(str(tmp_path))                       # run 2
        (tmp_path / "Images" / "new.jpg").unlink()           # user deleted it

        assert undo_last_run(str(tmp_path)) == (0, 1)
        assert len(_manifest(tmp_path)) == 1                 # run 2 dropped

        assert undo_last_run(str(tmp_path)) == (1, 0)        # run 1 reachable
        assert (tmp_path / "old.pdf").exists()


# ── Watcher ──────────────────────────────────────────────────────────────────

def test_watch_folder_refuses_home(capsys):
    pytest.importorskip("watchdog")
    from arise_i.core.watcher import watch_folder

    watch_folder(str(Path.home()))  # returns immediately instead of blocking
    assert "Refusing to watch" in capsys.readouterr().out
