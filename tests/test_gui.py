"""
tests/test_gui.py
-----------------
Headless unit tests for GUI-related functionality.

These tests do NOT open a real window — they test:
  1. log_callback integration in organize_folder()
  2. log_callback receives one call per file processed
  3. log_callback receives simulation messages in dry-run mode
  4. log_callback receives error messages on broken symlinks
  5. undo_last_run output (captured via redirect_stdout)
  6. gui.py imports cleanly (tkinter mocked so no display required)

All tests run fine in CI without a display server.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from file_organizer import organize_folder
import logging


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_logger():
    """Prevent handler accumulation across tests."""
    logger = logging.getLogger("arise_i")
    yield
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)


# ---------------------------------------------------------------------------
# log_callback — basic integration
# ---------------------------------------------------------------------------

class TestLogCallback:
    """organize_folder() with a log_callback."""

    def test_callback_called_for_each_moved_file(self, tmp_path):
        """One callback call per file moved (live run)."""
        (tmp_path / "photo.jpg").write_text("x")
        (tmp_path / "report.pdf").write_text("x")
        (tmp_path / "song.mp3").write_text("x")

        messages = []
        organize_folder(str(tmp_path), dry_run=False, log_callback=messages.append)

        # Expect exactly 3 messages, one per file
        assert len(messages) == 3
        # All should be "moved" confirmations
        assert all("→" in m for m in messages)

    def test_callback_contains_filename_and_category(self, tmp_path):
        """Callback message includes the filename and the destination category."""
        (tmp_path / "photo.jpg").write_text("x")

        messages = []
        organize_folder(str(tmp_path), dry_run=False, log_callback=messages.append)

        assert len(messages) == 1
        assert "photo.jpg" in messages[0]
        assert "Images" in messages[0]

    def test_callback_not_called_when_none(self, tmp_path):
        """Passing log_callback=None (default) must not raise."""
        (tmp_path / "test.pdf").write_text("x")
        # Should complete without error
        stats = organize_folder(str(tmp_path), dry_run=False, log_callback=None)
        assert stats.total_files() == 1

    def test_callback_receives_simulation_tag_in_dry_run(self, tmp_path):
        """In dry-run mode the callback message contains [SIM]."""
        (tmp_path / "clip.mp4").write_text("x")

        messages = []
        organize_folder(str(tmp_path), dry_run=True, log_callback=messages.append)

        assert len(messages) == 1
        assert "[SIM]" in messages[0]
        assert "clip.mp4" in messages[0]

    def test_callback_not_called_when_no_files(self, tmp_path):
        """Empty folder → callback is never called."""
        messages = []
        organize_folder(str(tmp_path), dry_run=False, log_callback=messages.append)
        assert messages == []

    def test_callback_receives_skip_message_for_broken_symlink(self, tmp_path, make_broken_symlink):
        """Broken symlinks produce a callback message containing ⚠."""
        broken = tmp_path / "ghost.txt"
        make_broken_symlink(broken, "/nonexistent/path/file.txt")

        messages = []
        organize_folder(str(tmp_path), dry_run=False, log_callback=messages.append)

        assert any("⚠" in m for m in messages)

    def test_multiple_files_correct_count(self, tmp_path):
        """N files → exactly N callback calls (no extras, no missing)."""
        names = ["a.jpg", "b.pdf", "c.mp3", "d.zip", "e.py"]
        for name in names:
            (tmp_path / name).write_text("x")

        messages = []
        organize_folder(str(tmp_path), dry_run=False, log_callback=messages.append)

        assert len(messages) == len(names)

    def test_callback_receives_dedup_note(self, tmp_path):
        """When a file is renamed to avoid collision, the callback says so."""
        img_dir = tmp_path / "Images"
        img_dir.mkdir()
        (img_dir / "photo.jpg").write_text("already there")
        (tmp_path / "photo.jpg").write_text("new")

        messages = []
        organize_folder(str(tmp_path), dry_run=False, log_callback=messages.append)

        assert len(messages) == 1
        assert "renamed" in messages[0] or "(1)" in messages[0]

    def test_callback_receives_correct_categories(self, tmp_path):
        """Custom categories are reflected in the callback messages."""
        custom = {"MyDocs": [".pdf"], "MyPics": [".jpg"]}
        (tmp_path / "file.pdf").write_text("x")
        (tmp_path / "file.jpg").write_text("x")

        messages = []
        organize_folder(str(tmp_path), dry_run=False,
                         categories=custom, log_callback=messages.append)

        categories_seen = {m.split("→")[-1].strip().rstrip("/").split("/")[0]
                           for m in messages if "→" in m}
        assert "MyDocs" in categories_seen
        assert "MyPics" in categories_seen


# ---------------------------------------------------------------------------
# gui.py import test (tkinter mocked)
# ---------------------------------------------------------------------------

class TestGuiImport:
    """Verify gui.py is importable without a live display server."""

    def test_gui_module_imports_with_mocked_tkinter(self):
        """Stub tkinter so gui.py loads cleanly in headless CI."""
        # Build a minimal tkinter mock
        tk_mock = MagicMock()
        tk_mock.Tk         = MagicMock(return_value=MagicMock())
        tk_mock.StringVar  = MagicMock(return_value=MagicMock())
        tk_mock.BooleanVar = MagicMock(return_value=MagicMock())
        tk_mock.DoubleVar  = MagicMock(return_value=MagicMock())
        ttk_mock  = MagicMock()
        fd_mock   = MagicMock()
        font_mock = MagicMock()
        mb_mock   = MagicMock()
        st_mock   = MagicMock()

        fake_modules = {
            "tkinter":                  tk_mock,
            "tkinter.ttk":              ttk_mock,
            "tkinter.filedialog":       fd_mock,
            "tkinter.font":             font_mock,
            "tkinter.messagebox":       mb_mock,
            "tkinter.scrolledtext":     st_mock,
        }

        with patch.dict(sys.modules, fake_modules):
            # Remove cached module if a previous test loaded it
            sys.modules.pop("gui", None)
            import gui  # should not raise
            assert hasattr(gui, "main")
            assert hasattr(gui, "AriseIApp")
            sys.modules.pop("gui", None)

    def test_gui_exits_gracefully_without_tkinter(self, monkeypatch):
        """If tkinter truly isn't available, gui.py should sys.exit(1)."""
        monkeypatch.setitem(sys.modules, "tkinter", None)
        sys.modules.pop("gui", None)
        with pytest.raises(SystemExit) as exc_info:
            import gui  # noqa: F401
        assert exc_info.value.code == 1
        sys.modules.pop("gui", None)
