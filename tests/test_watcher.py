"""
tests/test_watcher.py
---------------------
Unit tests for file_watcher — AriseIEventHandler and _DebounceTimer.

Strategy
--------
* No real filesystem events are fired; we construct synthetic watchdog
  event objects and call handler methods directly.
* organize_folder() is patched with unittest.mock so tests are fast
  and fully isolated from the real organiser logic.
* _DebounceTimer is tested independently of the observer.
"""

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# We import from the project root (no package install needed).
from file_watcher import (
    AriseIEventHandler,
    _DebounceTimer,
    watch_folder,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic watchdog events
# ---------------------------------------------------------------------------

def _file_event(src_path: str, is_directory: bool = False, dest_path: str | None = None):
    """Build a minimal object that looks like a watchdog FileSystemEvent."""
    ev = SimpleNamespace(
        src_path=src_path,
        is_directory=is_directory,
    )
    if dest_path is not None:
        ev.dest_path = dest_path
    return ev


def _wait_for(predicate, timeout: float = 5.0, interval: float = 0.01) -> bool:
    """Poll *predicate* until it returns truthy or *timeout* seconds pass."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


# ---------------------------------------------------------------------------
# _DebounceTimer tests
# ---------------------------------------------------------------------------

class TestDebounceTimer:

    def test_callback_fires_after_delay(self):
        """Callback is called once after the delay expires."""
        fired = threading.Event()
        timer = _DebounceTimer(delay=0.05, callback=fired.set)
        timer.trigger()
        assert fired.wait(timeout=0.5), "callback should fire within 500 ms"

    def test_reset_extends_window(self):
        """A second trigger() call before the delay resets the countdown."""
        fired = threading.Event()
        call_count = {"n": 0}

        def cb():
            call_count["n"] += 1
            fired.set()

        timer = _DebounceTimer(delay=0.2, callback=cb)
        timer.trigger()
        time.sleep(0.05)
        timer.trigger()
        # Leave a generous margin before the second deadline so this remains
        # deterministic on loaded CI runners and slower operating systems.
        assert not fired.wait(timeout=0.1), "callback must not have fired yet"
        assert fired.wait(timeout=0.5), "callback should fire after the reset window"
        assert call_count["n"] == 1, "callback should fire exactly once"

    def test_cancel_prevents_fire(self):
        """Cancelling before the delay suppresses the callback."""
        fired = threading.Event()
        timer = _DebounceTimer(delay=0.1, callback=fired.set)
        timer.trigger()
        timer.cancel()
        assert not fired.wait(timeout=0.3), "callback should NOT fire after cancel"

    def test_multiple_triggers_fire_once(self):
        """Rapid successive triggers produce exactly one callback call."""
        call_count = {"n": 0}

        def cb():
            call_count["n"] += 1

        # Triggers are sent back-to-back against a wide window so a runner
        # that oversleeps can't split the burst into two quiet periods.
        timer = _DebounceTimer(delay=0.5, callback=cb)
        for _ in range(10):
            timer.trigger()
        assert _wait_for(lambda: call_count["n"] >= 1), "callback never fired"
        time.sleep(0.6)  # longer than the window: any stray second fire lands
        assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# AriseIEventHandler — ignore-rule tests (no organizer calls expected)
# ---------------------------------------------------------------------------

class TestAriseIEventHandlerFiltering:
    """Verify that irrelevant events never trigger the organizer."""

    @pytest.fixture
    def handler(self, tmp_path):
        with patch("file_watcher.organize_folder") as mock_org:
            h = AriseIEventHandler(
                target_dir=tmp_path,
                debounce=0.05,  # short debounce so tests run fast
            )
            h._mock_org = mock_org
            yield h
        h._timer.cancel()

    def test_directory_event_ignored(self, handler, tmp_path):
        ev = _file_event(str(tmp_path / "SomeFolder"), is_directory=True)
        handler.on_created(ev)
        time.sleep(0.2)
        handler._mock_org.assert_not_called()

    def test_hidden_file_ignored(self, handler, tmp_path):
        ev = _file_event(str(tmp_path / ".DS_Store"))
        handler.on_created(ev)
        time.sleep(0.2)
        handler._mock_org.assert_not_called()

    def test_own_log_file_ignored(self, handler, tmp_path):
        ev = _file_event(str(tmp_path / "arise-i.log"))
        handler.on_created(ev)
        time.sleep(0.2)
        handler._mock_org.assert_not_called()

    def test_own_manifest_file_ignored(self, handler, tmp_path):
        ev = _file_event(str(tmp_path / ".arise-i-log.json"))
        handler.on_created(ev)
        time.sleep(0.2)
        handler._mock_org.assert_not_called()

    def test_file_in_subdirectory_ignored(self, handler, tmp_path):
        """Events from inside a subfolder (e.g. Images/) must not trigger."""
        subdir = tmp_path / "Images"
        subdir.mkdir()
        ev = _file_event(str(subdir / "photo.jpg"))
        handler.on_created(ev)
        time.sleep(0.2)
        handler._mock_org.assert_not_called()


# ---------------------------------------------------------------------------
# AriseIEventHandler — trigger tests (organizer SHOULD be called)
# ---------------------------------------------------------------------------

class TestAriseIEventHandlerTrigger:
    """Verify that valid file events do trigger organize_folder."""

    @pytest.fixture
    def handler_and_mock(self, tmp_path):
        with patch("file_watcher.organize_folder", return_value=MagicMock()) as mock_org:
            h = AriseIEventHandler(
                target_dir=tmp_path,
                debounce=0.05,
            )
            yield h, mock_org, tmp_path
        h._timer.cancel()

    def test_new_file_triggers_organizer(self, handler_and_mock):
        handler, mock_org, tmp_path = handler_and_mock
        ev = _file_event(str(tmp_path / "report.pdf"))
        handler.on_created(ev)
        time.sleep(0.3)
        mock_org.assert_called_once()

    def test_modified_file_triggers_organizer(self, handler_and_mock):
        handler, mock_org, tmp_path = handler_and_mock
        ev = _file_event(str(tmp_path / "song.mp3"))
        handler.on_modified(ev)
        time.sleep(0.3)
        mock_org.assert_called_once()

    def test_moved_file_uses_dest_path(self, handler_and_mock):
        """on_moved should use dest_path (the new location) not src_path."""
        handler, mock_org, tmp_path = handler_and_mock
        ev = _file_event(
            src_path="/tmp/browser_temp.crdownload",
            dest_path=str(tmp_path / "movie.mp4"),
        )
        handler.on_moved(ev)
        time.sleep(0.3)
        mock_org.assert_called_once()

    def test_real_watchdog_created_event_triggers_organizer(self, handler_and_mock):
        """Regression: watchdog >= 4 sets dest_path="" on non-move events.

        The SimpleNamespace events above lack dest_path entirely, which hid
        a bug where every real created/modified event was silently ignored.
        """
        events = pytest.importorskip("watchdog.events")
        handler, mock_org, tmp_path = handler_and_mock
        handler.on_created(events.FileCreatedEvent(str(tmp_path / "report.pdf")))
        time.sleep(0.3)
        mock_org.assert_called_once()

    def test_real_watchdog_modified_event_triggers_organizer(self, handler_and_mock):
        events = pytest.importorskip("watchdog.events")
        handler, mock_org, tmp_path = handler_and_mock
        handler.on_modified(events.FileModifiedEvent(str(tmp_path / "song.mp3")))
        time.sleep(0.3)
        mock_org.assert_called_once()

    def test_in_progress_download_does_not_trigger(self, handler_and_mock):
        events = pytest.importorskip("watchdog.events")
        handler, mock_org, tmp_path = handler_and_mock
        handler.on_modified(events.FileModifiedEvent(str(tmp_path / "movie.mp4.crdownload")))
        time.sleep(0.3)
        mock_org.assert_not_called()

    def test_rapid_events_trigger_organizer_once(self, tmp_path):
        """Ten rapid events in the debounce window → exactly one sort run."""
        # Own handler with a wide window, events sent back-to-back: the 50 ms
        # fixture window plus per-event sleeps flaked when a runner overslept.
        with patch("file_watcher.organize_folder", return_value=MagicMock()) as mock_org:
            handler = AriseIEventHandler(target_dir=tmp_path, debounce=0.5)
            try:
                for i in range(10):
                    handler.on_created(_file_event(str(tmp_path / f"file_{i}.jpg")))
                assert _wait_for(lambda: mock_org.call_count >= 1), "organizer never ran"
                time.sleep(0.6)  # longer than the window: any stray second sort lands
                mock_org.assert_called_once()
            finally:
                handler._timer.cancel()

    def test_two_separate_bursts_trigger_organizer_twice(self, handler_and_mock):
        """Events separated by more than the debounce window → two sorts."""
        handler, mock_org, tmp_path = handler_and_mock
        # First burst — wait for its sort before starting the second, so the
        # bursts are separated by construction rather than by sleep timing.
        handler.on_created(_file_event(str(tmp_path / "a.jpg")))
        assert _wait_for(lambda: mock_org.call_count >= 1), "first sort never ran"
        assert mock_org.call_count == 1
        # Second burst
        handler.on_created(_file_event(str(tmp_path / "b.pdf")))
        assert _wait_for(lambda: mock_org.call_count >= 2), "second sort never ran"
        time.sleep(0.2)   # past the 0.05s debounce: any stray extra sort lands
        assert mock_org.call_count == 2

    def test_organizer_called_with_correct_path(self, handler_and_mock):
        """organize_folder is called with str(target_dir)."""
        handler, mock_org, tmp_path = handler_and_mock
        handler.on_created(_file_event(str(tmp_path / "doc.docx")))
        time.sleep(0.3)
        args, kwargs = mock_org.call_args
        assert args[0] == str(tmp_path)

    def test_dry_run_passed_to_organizer(self, tmp_path):
        """When dry_run=True, organize_folder is called with dry_run=True."""
        with patch("file_watcher.organize_folder", return_value=MagicMock()) as mock_org:
            handler = AriseIEventHandler(
                target_dir=tmp_path,
                debounce=0.05,
                dry_run=True,
            )
            handler.on_created(_file_event(str(tmp_path / "img.png")))
            time.sleep(0.3)
            handler._timer.cancel()

        _, kwargs = mock_org.call_args
        assert kwargs.get("dry_run") is True

    def test_custom_categories_passed_to_organizer(self, tmp_path):
        """Custom categories dict is forwarded to organize_folder."""
        custom = {"Stuff": [".xyz"]}
        with patch("file_watcher.organize_folder", return_value=MagicMock()) as mock_org:
            handler = AriseIEventHandler(
                target_dir=tmp_path,
                debounce=0.05,
                categories=custom,
            )
            handler.on_created(_file_event(str(tmp_path / "item.xyz")))
            time.sleep(0.3)
            handler._timer.cancel()

        _, kwargs = mock_org.call_args
        assert kwargs.get("categories") == custom


# ---------------------------------------------------------------------------
# watch_folder() — missing folder guard
# ---------------------------------------------------------------------------

class TestWatchFolder:

    def test_watch_folder_missing_path_returns_early(self, tmp_path, capsys):
        """watch_folder should print an error and return if path doesn't exist."""
        missing = str(tmp_path / "does_not_exist")
        watch_folder(missing)
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "✗" in captured.out
