"""
tests/test_undo.py
------------------
Verifies that --undo accurately reverses the most recent ARISE-I run.
"""

import json
import logging
import pytest
from pathlib import Path
from arise_i.core.organizer import organize_folder, undo_last_run, LOG_MANIFEST


@pytest.fixture(autouse=True)
def reset_logger():
    """Prevent handler accumulation across tests."""
    logger = logging.getLogger("arise_i")
    yield
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def _make_files(folder: Path, names: list[str]) -> None:
    for name in names:
        (folder / name).write_text(f"content: {name}")


class TestUndo:
    """undo_last_run restores every file to its original location."""

    def test_files_restored_after_undo(self, tmp_path):
        names = ["photo.jpg", "report.pdf", "song.mp3"]
        _make_files(tmp_path, names)

        organize_folder(str(tmp_path), dry_run=False)
        # Confirm files were moved
        assert not (tmp_path / "photo.jpg").exists()

        undo_last_run(str(tmp_path))

        # All files should be back at the root
        for name in names:
            assert (tmp_path / name).exists(), f"{name} was not restored by undo"

    def test_file_content_preserved_after_undo(self, tmp_path):
        """Undo must not corrupt file contents."""
        (tmp_path / "notes.txt").write_text("Hello ARISE-I")
        organize_folder(str(tmp_path), dry_run=False)
        undo_last_run(str(tmp_path))
        assert (tmp_path / "notes.txt").read_text() == "Hello ARISE-I"

    def test_manifest_entry_removed_after_undo(self, tmp_path):
        """After undoing, that run's entry is removed from the manifest."""
        _make_files(tmp_path, ["a.jpg"])
        organize_folder(str(tmp_path), dry_run=False)

        undo_last_run(str(tmp_path))

        manifest = json.loads((tmp_path / LOG_MANIFEST).read_text())
        assert manifest == []  # history should now be empty

    def test_undo_when_no_history(self, tmp_path, capsys):
        """undo_last_run with no manifest prints an informative message,
        does not crash, and does not modify the filesystem."""
        undo_last_run(str(tmp_path))
        out = capsys.readouterr().out
        assert "No ARISE-I run history found" in out

    def test_multiple_runs_undo_only_last(self, tmp_path):
        """With two runs in history, undo should only reverse the last one."""
        _make_files(tmp_path, ["first.jpg"])
        organize_folder(str(tmp_path), dry_run=False)
        # first.jpg is now in Images/

        _make_files(tmp_path, ["second.pdf"])
        organize_folder(str(tmp_path), dry_run=False)
        # second.pdf is now in PDFs/

        undo_last_run(str(tmp_path))

        # second.pdf should be restored; first.jpg should still be in Images/
        assert (tmp_path / "second.pdf").exists()
        assert (tmp_path / "Images" / "first.jpg").exists()

        # Manifest should still have one entry (the first run)
        manifest = json.loads((tmp_path / LOG_MANIFEST).read_text())
        assert len(manifest) == 1

    def test_undo_with_deduped_file(self, tmp_path):
        """A file that was renamed during the run is correctly restored."""
        # Pre-populate Images/ so the incoming photo.jpg gets deduplicated
        img_dir = tmp_path / "Images"
        img_dir.mkdir()
        (img_dir / "photo.jpg").write_text("old copy")

        # Now create photo.jpg at root — it will be moved as photo (1).jpg
        (tmp_path / "photo.jpg").write_text("new copy")
        organize_folder(str(tmp_path), dry_run=False)

        assert (img_dir / "photo (1).jpg").exists()
        assert not (tmp_path / "photo.jpg").exists()

        undo_last_run(str(tmp_path))

        # Should be back at root as the original name
        assert (tmp_path / "photo.jpg").read_text() == "new copy"
        # The old copy in Images/ should remain untouched
        assert (img_dir / "photo.jpg").read_text() == "old copy"


class TestUndoSafety:
    """Undo must never destroy data, even when the folder changed since."""

    def test_newer_file_at_original_path_is_not_overwritten(self, tmp_path):
        (tmp_path / "report.pdf").write_text("OLD")
        organize_folder(str(tmp_path), dry_run=False)
        # The same file name is downloaded again before the user undoes
        (tmp_path / "report.pdf").write_text("NEW")

        restored, failed = undo_last_run(str(tmp_path))

        assert (restored, failed) == (1, 0)
        assert (tmp_path / "report.pdf").read_text() == "NEW"
        assert (tmp_path / "report (1).pdf").read_text() == "OLD"

    def test_failed_moves_stay_in_manifest_for_retry(self, tmp_path):
        _make_files(tmp_path, ["a.jpg", "b.pdf"])
        organize_folder(str(tmp_path), dry_run=False)
        (tmp_path / "PDFs" / "b.pdf").unlink()  # user deleted one sorted file

        restored, failed = undo_last_run(str(tmp_path))

        assert (restored, failed) == (1, 1)
        manifest = json.loads((tmp_path / LOG_MANIFEST).read_text())
        assert len(manifest) == 1
        assert [Path(m["src"]).name for m in manifest[0]["moves"]] == ["b.pdf"]

    def test_empty_category_folders_are_removed(self, tmp_path):
        _make_files(tmp_path, ["a.jpg"])
        organize_folder(str(tmp_path), dry_run=False)
        undo_last_run(str(tmp_path))
        assert not (tmp_path / "Images").exists()

    def test_category_folder_with_user_files_is_kept(self, tmp_path):
        _make_files(tmp_path, ["a.jpg"])
        organize_folder(str(tmp_path), dry_run=False)
        (tmp_path / "Images" / "mine.jpg").write_text("user file")
        undo_last_run(str(tmp_path))
        assert (tmp_path / "Images" / "mine.jpg").exists()

    def test_log_callback_receives_progress(self, tmp_path):
        _make_files(tmp_path, ["a.jpg"])
        organize_folder(str(tmp_path), dry_run=False)
        messages: list[str] = []
        undo_last_run(str(tmp_path), log_callback=messages.append)
        assert any(m.startswith("✓  Restored: a.jpg") for m in messages)
        assert any("Rollback complete" in m for m in messages)
