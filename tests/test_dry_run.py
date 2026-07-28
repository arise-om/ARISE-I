"""
tests/test_dry_run.py
---------------------
Verifies that --dry-run makes ZERO filesystem changes.
"""

import logging
import pytest
from pathlib import Path
from file_organizer import organize_folder, LOG_MANIFEST


@pytest.fixture(autouse=True)
def reset_logger():
    """Remove all handlers from the arise_i logger between tests to prevent
    handler accumulation across test runs."""
    logger = logging.getLogger("arise_i")
    yield
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def _populate(folder: Path) -> list[str]:
    """Create a standard set of test files; return their names."""
    names = [
        "photo.jpg", "report.pdf", "song.mp3",
        "video.mp4", "archive.zip", "script.py",
        "README",    # no-extension file
    ]
    for name in names:
        (folder / name).touch()
    return names


class TestDryRun:
    """All files remain in their original location after a dry run."""

    def test_no_files_moved(self, tmp_path):
        names = _populate(tmp_path)
        organize_folder(str(tmp_path), dry_run=True)

        # Every original file must still be in the root of tmp_path
        for name in names:
            assert (tmp_path / name).exists(), (
                f"{name} was moved or deleted during a dry-run!"
            )

    def test_no_category_folders_created(self, tmp_path):
        _populate(tmp_path)
        organize_folder(str(tmp_path), dry_run=True)

        # No new sub-folders should have been created
        subdirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        assert subdirs == [], (
            f"Dry-run created unexpected directories: {subdirs}"
        )

    def test_no_manifest_file_created(self, tmp_path):
        """Dry-run must NOT create the undo manifest."""
        _populate(tmp_path)
        organize_folder(str(tmp_path), dry_run=True)
        assert not (tmp_path / LOG_MANIFEST).exists()

    def test_no_log_file_created(self, tmp_path):
        """Dry-run must NOT create arise-i.log on disk."""
        _populate(tmp_path)
        organize_folder(str(tmp_path), dry_run=True)
        assert not (tmp_path / "arise-i.log").exists()

    def test_broken_symlink_skipped(self, tmp_path):
        """Broken symlinks are reported but cause no crash and no file moves."""
        _populate(tmp_path)
        broken = tmp_path / "ghost.txt"
        broken.symlink_to("/nonexistent/path")

        stats = organize_folder(str(tmp_path), dry_run=True)
        assert stats.skipped == 1
        assert broken.is_symlink()  # still there, untouched

    def test_stats_returned_correctly(self, tmp_path):
        """Stats object accurately reflects what *would* be moved."""
        _populate(tmp_path)
        stats = organize_folder(str(tmp_path), dry_run=True)
        assert stats.total_files() == 7
        assert stats.errors == 0
