"""
tests/test_dedup.py
-------------------
Tests for get_unique_destination — duplicate filename resolution.
"""

from arise_i.core.organizer import get_unique_destination


class TestDeduplication:
    """Verify that get_unique_destination never overwrites existing files."""

    def test_no_conflict_returns_original_name(self, tmp_path):
        """When no file exists at destination, the original name is returned."""
        dest = get_unique_destination(tmp_path, "photo.jpg")
        assert dest == tmp_path / "photo.jpg"

    def test_first_conflict_gets_counter_1(self, tmp_path):
        """If photo.jpg exists, the next safe name is photo (1).jpg."""
        (tmp_path / "photo.jpg").touch()
        dest = get_unique_destination(tmp_path, "photo.jpg")
        assert dest == tmp_path / "photo (1).jpg"

    def test_counter_increments_through_existing_files(self, tmp_path):
        """If (1) and (2) already exist, the function returns (3)."""
        (tmp_path / "photo.jpg").touch()
        (tmp_path / "photo (1).jpg").touch()
        (tmp_path / "photo (2).jpg").touch()
        dest = get_unique_destination(tmp_path, "photo.jpg")
        assert dest == tmp_path / "photo (3).jpg"

    def test_no_extension_file_dedup(self, tmp_path):
        """Files with no extension also deduplicate correctly."""
        (tmp_path / "README").touch()
        dest = get_unique_destination(tmp_path, "README")
        assert dest == tmp_path / "README (1)"

    def test_different_extension_no_conflict(self, tmp_path):
        """photo.png should not conflict with photo.jpg."""
        (tmp_path / "photo.jpg").touch()
        dest = get_unique_destination(tmp_path, "photo.png")
        assert dest == tmp_path / "photo.png"

    def test_empty_folder_always_original(self, tmp_path):
        """In an empty folder every file gets its original name."""
        for name in ["a.txt", "b.pdf", "c.mp3"]:
            dest = get_unique_destination(tmp_path, name)
            assert dest.name == name
