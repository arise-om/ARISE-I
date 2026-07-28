"""
tests/test_plugins.py
---------------------
Unit tests for the ARISE-I Plugin Architecture (Roadmap item 3).

Tests cover:
  - load_plugins() with a real temp plugin directory
  - classify_with_plugins() first-match, abstain, and error-handling behaviour
  - Integration with organize_folder() via the plugins= parameter
  - Graceful degradation: broken plugins never crash ARISE-I
  - Ordering guarantee: plugins fire in alphabetical filename order
"""

import logging
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from plugin_loader import (
    PLUGIN_DIR,
    _load_single_plugin,
    classify_with_plugins,
    load_plugins,
)
from file_organizer import organize_folder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_logger():
    """Prevent handler accumulation across tests."""
    logger = logging.getLogger("arise_i")
    yield
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)


def _write_plugin(directory: Path, filename: str, code: str) -> Path:
    """Write a plugin file and return its path."""
    p = directory / filename
    p.write_text(textwrap.dedent(code), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_plugins() — discovery
# ---------------------------------------------------------------------------

class TestLoadPlugins:

    def test_empty_dir_returns_empty_list(self, tmp_path):
        """An empty plugin directory yields no plugins."""
        plugins = load_plugins(tmp_path)
        assert plugins == []

    def test_nonexistent_dir_returns_empty_list(self, tmp_path):
        """A missing plugin directory is handled gracefully."""
        plugins = load_plugins(tmp_path / "does_not_exist")
        assert plugins == []

    def test_single_valid_plugin_loaded(self, tmp_path):
        """One valid plugin file → one callable returned."""
        _write_plugin(tmp_path, "my_plugin.py", """
            def classify(path):
                return "CustomFolder"
        """)
        plugins = load_plugins(tmp_path)
        assert len(plugins) == 1
        assert callable(plugins[0])

    def test_plugins_loaded_alphabetically(self, tmp_path):
        """Plugins load in sorted filename order."""
        _write_plugin(tmp_path, "02_second.py", """
            def classify(path):
                return "B"
        """)
        _write_plugin(tmp_path, "01_first.py", """
            def classify(path):
                return "A"
        """)
        plugins = load_plugins(tmp_path)
        # The first plugin returns "A", the second "B"
        dummy = tmp_path / "file.txt"
        dummy.touch()
        assert plugins[0](dummy) == "A"
        assert plugins[1](dummy) == "B"

    def test_underscore_files_skipped(self, tmp_path):
        """Files starting with _ (like __init__.py) are not loaded."""
        _write_plugin(tmp_path, "__init__.py", """
            def classify(path):
                return "ShouldNotLoad"
        """)
        plugins = load_plugins(tmp_path)
        assert plugins == []

    def test_non_python_files_ignored(self, tmp_path):
        """Non-.py files are not loaded."""
        (tmp_path / "notes.txt").write_text("not a plugin")
        plugins = load_plugins(tmp_path)
        assert plugins == []

    def test_plugin_missing_classify_skipped(self, tmp_path):
        """A .py file with no classify() callable is gracefully skipped."""
        _write_plugin(tmp_path, "bad_plugin.py", """
            def not_classify(path):
                return "Nope"
        """)
        plugins = load_plugins(tmp_path)
        assert plugins == []

    def test_plugin_with_syntax_error_skipped(self, tmp_path):
        """A plugin that fails to import is skipped without crashing."""
        _write_plugin(tmp_path, "broken.py", """
            def classify(path)  # missing colon — SyntaxError
                return "X"
        """)
        plugins = load_plugins(tmp_path)
        assert plugins == []

    def test_mixed_valid_and_broken_plugins(self, tmp_path):
        """Broken plugins are skipped; valid ones still load."""
        _write_plugin(tmp_path, "01_good.py", """
            def classify(path):
                return "Good"
        """)
        _write_plugin(tmp_path, "02_broken.py", """
            def classify(path  # syntax error
                return "Bad"
        """)
        plugins = load_plugins(tmp_path)
        assert len(plugins) == 1


# ---------------------------------------------------------------------------
# _load_single_plugin() — unit
# ---------------------------------------------------------------------------

class TestLoadSinglePlugin:

    def test_returns_callable(self, tmp_path):
        p = _write_plugin(tmp_path, "p.py", """
            def classify(path):
                return "X"
        """)
        fn = _load_single_plugin(p)
        assert callable(fn)

    def test_returns_none_for_import_error(self, tmp_path):
        p = _write_plugin(tmp_path, "p.py", """
            import nonexistent_module_xyz
            def classify(path):
                return "X"
        """)
        result = _load_single_plugin(p)
        assert result is None

    def test_returns_none_without_classify(self, tmp_path):
        p = _write_plugin(tmp_path, "p.py", """
            x = 42
        """)
        result = _load_single_plugin(p)
        assert result is None


# ---------------------------------------------------------------------------
# classify_with_plugins() — classification logic
# ---------------------------------------------------------------------------

class TestClassifyWithPlugins:

    def test_no_plugins_returns_none(self, tmp_path):
        f = tmp_path / "file.pdf"
        f.touch()
        assert classify_with_plugins(f, []) is None

    def test_first_match_wins(self, tmp_path):
        """The first plugin to return a non-None string wins."""
        f = tmp_path / "file.pdf"
        f.touch()
        plugins = [
            lambda path: "First",
            lambda path: "Second",
        ]
        assert classify_with_plugins(f, plugins) == "First"

    def test_abstaining_plugins_pass_through(self, tmp_path):
        """Plugins returning None are skipped."""
        f = tmp_path / "file.pdf"
        f.touch()
        plugins = [
            lambda path: None,
            lambda path: None,
            lambda path: "Last",
        ]
        assert classify_with_plugins(f, plugins) == "Last"

    def test_all_plugins_abstain_returns_none(self, tmp_path):
        f = tmp_path / "file.pdf"
        f.touch()
        plugins = [lambda path: None, lambda path: None]
        assert classify_with_plugins(f, plugins) is None

    def test_empty_string_is_treated_as_abstain(self, tmp_path):
        """Plugins returning empty or whitespace-only strings are ignored."""
        f = tmp_path / "file.pdf"
        f.touch()
        plugins = [
            lambda path: "",
            lambda path: "   ",
            lambda path: "ValidFolder",
        ]
        assert classify_with_plugins(f, plugins) == "ValidFolder"

    def test_plugin_exception_is_caught(self, tmp_path):
        """A plugin that raises is caught; the next plugin is tried."""
        f = tmp_path / "file.pdf"
        f.touch()

        def crashing_plugin(path):
            raise RuntimeError("simulated plugin crash")

        plugins = [crashing_plugin, lambda path: "SafeFolder"]
        assert classify_with_plugins(f, plugins) == "SafeFolder"

    def test_result_is_stripped(self, tmp_path):
        """Category names returned by plugins are stripped of whitespace."""
        f = tmp_path / "file.pdf"
        f.touch()
        plugins = [lambda path: "  WorkFiles  "]
        assert classify_with_plugins(f, plugins) == "WorkFiles"


# ---------------------------------------------------------------------------
# Integration: plugins + organize_folder()
# ---------------------------------------------------------------------------

class TestPluginIntegration:

    def test_plugin_overrides_extension_map(self, tmp_path):
        """A plugin can send a .jpg to a custom folder instead of 'Images'."""
        (tmp_path / "photo.jpg").write_text("x")

        # Plugin: all .jpg files → "MyPhotos"
        plugins = [
            lambda path: "MyPhotos" if path.suffix.lower() == ".jpg" else None
        ]
        organize_folder(str(tmp_path), dry_run=False, plugins=plugins)

        assert (tmp_path / "MyPhotos" / "photo.jpg").exists()
        assert not (tmp_path / "Images" / "photo.jpg").exists()

    def test_plugin_abstain_falls_back_to_extension_map(self, tmp_path):
        """When a plugin returns None, the extension map is used."""
        (tmp_path / "report.pdf").write_text("x")

        # Plugin that never matches anything
        plugins = [lambda path: None]
        organize_folder(str(tmp_path), dry_run=False, plugins=plugins)

        # Should land in PDFs/ via the extension map
        assert (tmp_path / "PDFs" / "report.pdf").exists()

    def test_no_plugins_behaves_identically(self, tmp_path):
        """Passing plugins=None or plugins=[] gives the same result as before."""
        (tmp_path / "song.mp3").write_text("x")
        organize_folder(str(tmp_path), dry_run=False, plugins=None)
        assert (tmp_path / "Music" / "song.mp3").exists()

    def test_plugin_applies_during_dry_run(self, tmp_path):
        """Plugins are evaluated even in dry-run mode (no files moved)."""
        (tmp_path / "photo.jpg").write_text("x")

        plugins = [lambda path: "MyPhotos" if path.suffix.lower() == ".jpg" else None]
        stats = organize_folder(str(tmp_path), dry_run=True, plugins=plugins)

        # File must still be at original location
        assert (tmp_path / "photo.jpg").exists()
        # Stats should reflect the plugin-assigned category
        assert "MyPhotos" in stats._data

    def test_multiple_files_different_plugins(self, tmp_path):
        """Different plugins can handle different file types."""
        (tmp_path / "photo.jpg").write_text("x")
        (tmp_path / "report.pdf").write_text("x")

        def by_type(path):
            if path.suffix == ".jpg":
                return "Snapshots"
            if path.suffix == ".pdf":
                return "Reports"
            return None

        organize_folder(str(tmp_path), dry_run=False, plugins=[by_type])

        assert (tmp_path / "Snapshots" / "photo.jpg").exists()
        assert (tmp_path / "Reports"   / "report.pdf").exists()

    def test_plugin_loaded_from_real_plugin_dir(self, tmp_path):
        """End-to-end: load_plugins() then pass to organize_folder()."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        _write_plugin(plugin_dir, "01_video.py", """
            def classify(path):
                if path.suffix.lower() == '.mp4':
                    return 'StreamedVideos'
                return None
        """)

        plugins = load_plugins(plugin_dir)
        assert len(plugins) == 1

        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (sandbox / "clip.mp4").write_text("x")

        organize_folder(str(sandbox), dry_run=False, plugins=plugins)

        assert (sandbox / "StreamedVideos" / "clip.mp4").exists()
        assert not (sandbox / "Videos" / "clip.mp4").exists()

    def test_default_plugin_dir_is_home_dot_arise_i(self):
        """PLUGIN_DIR should point to ~/.arise-i/plugins by default."""
        assert PLUGIN_DIR == Path.home() / ".arise-i" / "plugins"
