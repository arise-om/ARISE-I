"""
tests/test_mapping.py
---------------------
Tests for extension → category mapping logic.
"""

import pytest
from arise_i.core.organizer import build_extension_map, DEFAULT_CATEGORIES


@pytest.fixture
def ext_map():
    """Build the default extension map once per test."""
    return build_extension_map(DEFAULT_CATEGORIES)


class TestExtensionMapping:
    """Verify that known extensions resolve to the correct category."""

    @pytest.mark.parametrize("ext,expected", [
        # Images
        (".jpg",  "Images"),
        (".jpeg", "Images"),
        (".png",  "Images"),
        (".gif",  "Images"),
        (".webp", "Images"),
        (".svg",  "Images"),
        # Documents
        (".docx", "Documents"),
        (".txt",  "Documents"),
        (".md",   "Documents"),
        # PDFs
        (".pdf",  "PDFs"),
        # Spreadsheets
        (".xlsx", "Spreadsheets"),
        (".csv",  "Spreadsheets"),
        # Presentations
        (".pptx", "Presentations"),
        # Videos
        (".mp4",  "Videos"),
        (".mkv",  "Videos"),
        (".avi",  "Videos"),
        # Music
        (".mp3",  "Music"),
        (".flac", "Music"),
        (".wav",  "Music"),
        # Archives
        (".zip",  "Archives"),
        (".rar",  "Archives"),
        (".tar",  "Archives"),
        (".gz",   "Archives"),
        # Code
        (".py",   "Code"),
        (".js",   "Code"),
        (".html", "Code"),
        (".css",  "Code"),
        # Installers
        (".exe",  "Installers"),
        (".dmg",  "Installers"),
        (".apk",  "Installers"),
    ])
    def test_known_extension(self, ext_map, ext, expected):
        assert ext_map.get(ext) == expected

    def test_unknown_extension_returns_none(self, ext_map):
        """Unknown extensions are not in the map; callers use 'Others' as default."""
        assert ext_map.get(".xyz") is None
        assert ext_map.get(".abc") is None

    def test_case_insensitive_lookup(self, ext_map):
        """All keys in the map are lower-cased during build — test the build."""
        # The map always stores lower-case keys
        assert ".jpg" in ext_map
        assert ".JPG" not in ext_map  # uppercase key was never inserted

    def test_no_duplicate_extensions_across_categories(self):
        """Each extension should map to exactly one category."""
        seen: dict[str, str] = {}
        for category, exts in DEFAULT_CATEGORIES.items():
            for ext in exts:
                lower = ext.lower()
                assert lower not in seen, (
                    f"Extension {lower!r} appears in both "
                    f"{seen[lower]!r} and {category!r}"
                )
                seen[lower] = category

    def test_custom_categories_override(self):
        """build_extension_map works correctly with custom user-defined categories."""
        custom = {"MyStuff": [".xyz", ".abc"]}
        m = build_extension_map(custom)
        assert m[".xyz"] == "MyStuff"
        assert m[".abc"] == "MyStuff"
        assert ".jpg" not in m  # defaults are NOT merged in by build_extension_map
