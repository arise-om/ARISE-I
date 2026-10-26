"""
tests/test_real_run.py
----------------------
Verifies that a live run moves files to the correct category folders.
"""

import json
import logging
import pytest
from pathlib import Path
from arise_i.core.organizer import organize_folder, LOG_MANIFEST


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
        (folder / name).write_text(f"content of {name}")


class TestRealRun:
    """Files land in the right category folders after a live run."""

    def test_files_moved_to_correct_folders(self, tmp_path):
        _make_files(tmp_path, [
            "photo.jpg", "report.pdf", "song.mp3",
            "video.mp4", "archive.zip", "script.py",
        ])
        organize_folder(str(tmp_path), dry_run=False)

        assert (tmp_path / "Images"  / "photo.jpg").exists()
        assert (tmp_path / "PDFs"    / "report.pdf").exists()
        assert (tmp_path / "Music"   / "song.mp3").exists()
        assert (tmp_path / "Videos"  / "video.mp4").exists()
        assert (tmp_path / "Archives"/ "archive.zip").exists()
        assert (tmp_path / "Code"    / "script.py").exists()

    def test_no_extension_file_goes_to_review_or_others(self, tmp_path):
        """Extensionless files have low classifier confidence → __Review__/ or Others."""
        (tmp_path / "README").touch()
        organize_folder(str(tmp_path), dry_run=False)
        # AI classifier routes low-confidence files to __Review__/;
        # fallback (no classifier) routes to Others/
        in_review = (tmp_path / "__Review__" / "README").exists()
        in_others = (tmp_path / "Others"     / "README").exists()
        assert in_review or in_others, "README should land in __Review__/ or Others/"


    def test_hidden_files_are_never_moved(self, tmp_path):
        """Settings and OS metadata must be safe even in a chosen folder."""
        (tmp_path / ".env").write_text("SECRET=value")
        (tmp_path / "photo.jpg").touch()

        organize_folder(str(tmp_path), dry_run=False)

        assert (tmp_path / ".env").exists()
        assert not (tmp_path / "Others" / ".env").exists()
        assert (tmp_path / "Images" / "photo.jpg").exists()

    def test_uppercase_extension_handled(self, tmp_path):
        (tmp_path / "IMAGE.PNG").touch()
        organize_folder(str(tmp_path), dry_run=False)
        assert (tmp_path / "Images" / "IMAGE.PNG").exists()

    def test_non_ascii_filename_handled(self, tmp_path):
        fname = "résumé_français.pdf"
        (tmp_path / fname).touch()
        organize_folder(str(tmp_path), dry_run=False)
        assert (tmp_path / "PDFs" / fname).exists()

    def test_duplicate_file_not_overwritten(self, tmp_path):
        """Two files with the same name land in the same folder without
        either being deleted or clobbered."""
        (tmp_path / "photo.jpg").write_text("original")
        # Pre-populate destination so there's already a conflict
        img_dir = tmp_path / "Images"
        img_dir.mkdir()
        (img_dir / "photo.jpg").write_text("already there")

        (tmp_path / "photo.jpg").write_text("original")  # re-create after mkdir
        organize_folder(str(tmp_path), dry_run=False)

        assert (img_dir / "photo.jpg").read_text() == "already there"
        assert (img_dir / "photo (1).jpg").read_text() == "original"

    def test_manifest_file_written(self, tmp_path):
        _make_files(tmp_path, ["photo.jpg", "song.mp3"])
        organize_folder(str(tmp_path), dry_run=False)

        manifest_path = tmp_path / LOG_MANIFEST
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert isinstance(data, list)
        assert len(data) == 1  # one run recorded
        assert len(data[0]["moves"]) == 2

    def test_log_file_written(self, tmp_path):
        _make_files(tmp_path, ["photo.jpg"])
        organize_folder(str(tmp_path), dry_run=False)
        assert (tmp_path / "arise-i.log").exists()

    def test_live_run_is_logged_after_dry_run(self, tmp_path):
        """A preview must not prevent logging during a later live run."""
        preview_dir = tmp_path / "preview"
        live_dir = tmp_path / "live"
        preview_dir.mkdir()
        live_dir.mkdir()
        (preview_dir / "preview.jpg").touch()
        (live_dir / "live.jpg").touch()

        organize_folder(str(preview_dir), dry_run=True)
        organize_folder(str(live_dir), dry_run=False)

        assert not (preview_dir / "arise-i.log").exists()
        assert (live_dir / "arise-i.log").exists()

    def test_broken_symlink_skipped_in_live_run(self, tmp_path, make_broken_symlink):
        (tmp_path / "real.jpg").touch()
        broken = tmp_path / "ghost.txt"
        make_broken_symlink(broken, "/nonexistent/path")

        stats = organize_folder(str(tmp_path), dry_run=False)
        assert stats.skipped == 1
        assert stats.total_files() == 1  # only the real file was moved

    def test_stats_match_moved_files(self, tmp_path):
        _make_files(tmp_path, ["a.jpg", "b.jpg", "c.pdf"])
        stats = organize_folder(str(tmp_path), dry_run=False)
        assert stats.total_files() == 3
        assert stats._data["Images"]["count"] == 2
        assert stats._data["PDFs"]["count"] == 1

    def test_original_location_empty_after_run(self, tmp_path):
        """After a successful run no regular files remain at the root."""
        _make_files(tmp_path, ["photo.jpg", "song.mp3", "doc.pdf"])
        organize_folder(str(tmp_path), dry_run=False)

        root_files = [
            p for p in tmp_path.iterdir()
            if p.is_file() and p.name not in {LOG_MANIFEST, "arise-i.log"}
        ]
        assert root_files == [], f"Unexpected files remain at root: {root_files}"

    def test_custom_categories_respected(self, tmp_path):
        """Files follow a user-supplied category map, not the built-in defaults."""
        custom = {"MyVideos": [".mp4"], "MyAudio": [".mp3"]}
        _make_files(tmp_path, ["clip.mp4", "beat.mp3"])
        organize_folder(str(tmp_path), dry_run=False, categories=custom)

        assert (tmp_path / "MyVideos" / "clip.mp4").exists()
        assert (tmp_path / "MyAudio"  / "beat.mp3").exists()
        # Built-in folder names should NOT have been used
        assert not (tmp_path / "Videos").exists()
        assert not (tmp_path / "Music").exists()
