"""
ARISE-I — Watch-Folder Module
-----------------------------
Autonomous File Organization Unit: Daemon Mode.
Built by Om // Ironlabs.tech

Provides a persistent file-system watcher that automatically calls
organize_folder() whenever a new file settles in the watched directory.
A debounce timer prevents sorting files that are still being written
(e.g. a download in progress).

Usage (standalone):
    python file_watcher.py --path ~/Downloads
    python file_watcher.py --path ~/Downloads --debounce 3.5
    python file_watcher.py --path ~/Downloads --dry-run

Or invoked via the main CLI:
    python file_organizer.py --watch --path ~/Downloads

Requires:
    pip install watchdog
"""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    from watchdog.observers import Observer
    WATCHDOG_AVAILABLE = True
except ImportError:
    # watchdog is optional — only required for --watch / Watch button.
    # We raise here so callers (gui.py, file_organizer.py) can catch it
    # gracefully rather than the whole program dying.
    WATCHDOG_AVAILABLE = False
    # Provide stub base-classes so type-checking passes even without watchdog
    class FileSystemEventHandler:  # type: ignore[no-redef]
        pass
    class FileSystemEvent:  # type: ignore[no-redef]
        pass
    class Observer:  # type: ignore[no-redef]
        pass

from file_organizer import (
    Color,
    Stats,
    boot_sequence,
    load_categories,
    organize_folder,
    skip_reason,
)

try:
    from plugin_loader import ClassifierPlugin
except ImportError:  # pragma: no cover
    ClassifierPlugin = None  # type: ignore[assignment,misc]

try:
    from learning_store import LearningStore as _LS
except ImportError:
    _LS = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DEBOUNCE: float = 2.0   # seconds of FS quiet before sorting triggers


# ---------------------------------------------------------------------------
# Debounce helper
# ---------------------------------------------------------------------------

class _DebounceTimer:
    """One-shot timer that resets on each call; fires callback after quiet."""

    def __init__(self, delay: float, callback) -> None:
        self._delay    = delay
        self._callback = callback
        self._timer: threading.Timer | None = None
        self._lock  = threading.Lock()
        self._generation = 0

    def _fire(self, generation: int) -> None:
        """Run only if this timer is still the active debounce generation."""
        with self._lock:
            if generation != self._generation:
                return
            self._timer = None
        self._callback()

    def trigger(self) -> None:
        """Reset the countdown window — call this on every FS event."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._generation += 1
            self._timer = threading.Timer(
                self._delay, self._fire, args=(self._generation,)
            )
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        """Cancel any pending fire (called on shutdown)."""
        with self._lock:
            self._generation += 1
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------

class AriseIEventHandler(FileSystemEventHandler):
    """Watchdog handler that debounces FS events and calls organize_folder.

    Parameters
    ----------
    target_dir : Path
        The directory being watched.
    debounce : float
        Seconds to wait after the last event before sorting.
    dry_run : bool
        When True, pass dry_run=True to organize_folder (nothing moves).
    categories : dict, optional
        Category → extension map (None = use DEFAULT_CATEGORIES).
    """

    def __init__(
        self,
        target_dir: Path,
        debounce: float = DEFAULT_DEBOUNCE,
        dry_run: bool = False,
        categories: dict | None = None,
        plugins: "list | None" = None,
        learning_store=None,
    ) -> None:
        super().__init__()
        self.target_dir     = target_dir
        self.dry_run        = dry_run
        self.categories     = categories
        self.plugins        = plugins or []
        self._learning_store = learning_store
        self._timer         = _DebounceTimer(debounce, self._run_organizer)

    # ------------------------------------------------------------------
    # Watchdog callbacks
    # ------------------------------------------------------------------

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        # A file moved into the watched dir (e.g. browser completing a DL)
        self._handle(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle(self, event: FileSystemEvent) -> None:
        """Filter irrelevant events and reset the debounce timer."""
        # watchdog >= 4 gives *every* event a dest_path, set to "" unless the
        # event is a move — so fall back to src_path when it's empty.
        raw = getattr(event, "dest_path", "") or event.src_path
        path = Path(os.fsdecode(raw))

        # Ignore directories
        if event.is_directory:
            return

        # Ignore ARISE-I's own files, hidden/system files and in-progress
        # downloads (.crdownload, .part, …) — same rules as the organiser
        if skip_reason(path) is not None:
            return

        # Ignore files that aren't directly inside the target dir
        # (guards against events from subdirectories watchdog might emit)
        if path.parent.resolve() != self.target_dir.resolve():
            return

        print(
            f"  {Color.YELLOW}» Event detected:{Color.RESET} "
            f"{path.name}  {Color.DIM}— debounce reset{Color.RESET}"
        )
        self._timer.trigger()

    def _run_organizer(self) -> None:
        """Called by the debounce timer after the quiet window expires."""
        print(f"\n{Color.CYAN}ARISE-I » Quiet window expired — triggering sort...{Color.RESET}\n")
        kwargs: dict = {"dry_run": self.dry_run}
        if self.categories is not None:
            kwargs["categories"] = self.categories
        if self.plugins:
            kwargs["plugins"] = self.plugins
        if self._learning_store is not None:
            kwargs["learning_store"] = self._learning_store
        stats: Stats = organize_folder(str(self.target_dir), **kwargs)
        stats.print_summary()
        print(
            f"\n{Color.GREEN}ARISE-I » Sort complete.  Watching for new files...{Color.RESET}\n"
        )


# ---------------------------------------------------------------------------
# Public API — watch_folder()
# ---------------------------------------------------------------------------

def watch_folder(
    target_dir: str,
    debounce: float = DEFAULT_DEBOUNCE,
    dry_run: bool = False,
    categories: dict | None = None,
    plugins: "list | None" = None,
    learning_store=None,
    max_restarts: int = 5,
) -> None:
    """Start a blocking watch-loop over *target_dir*.

    The observer is wrapped in an exponential-backoff restart loop so a
    crashed watchdog thread is automatically recovered (up to max_restarts
    times before giving up).

    Blocks indefinitely until the user presses Ctrl-C.
    """
    target_path = Path(target_dir).expanduser().resolve()

    if not target_path.exists():
        print(f"{Color.RED}✗ Folder not found: {target_path}{Color.RESET}")
        return
    if not target_path.is_dir():
        print(f"{Color.RED}✗ Path is not a directory: {target_path}{Color.RESET}")
        return

    mode_note = (
        f"{Color.YELLOW}[SIMULATION — files will NOT be moved]{Color.RESET}"
        if dry_run
        else f"{Color.GREEN}[LIVE MODE]{Color.RESET}"
    )
    print(
        f"{Color.CYAN}{Color.BOLD}ARISE-I » Watch-Folder Daemon Active{Color.RESET}\n"
        f"  Watching : {Color.BOLD}{target_path}{Color.RESET}\n"
        f"  Debounce : {debounce}s\n"
        f"  Mode     : {mode_note}\n"
        f"\n{Color.DIM}Press Ctrl-C to stop.{Color.RESET}\n"
    )

    restart_count = 0
    backoff       = 2.0   # seconds; doubles on each restart

    while restart_count <= max_restarts:
        handler = AriseIEventHandler(
            target_dir=target_path,
            debounce=debounce,
            dry_run=dry_run,
            categories=categories,
            plugins=plugins,
            learning_store=learning_store,
        )
        observer = Observer()
        observer.schedule(handler, str(target_path), recursive=False)
        observer.start()

        try:
            while observer.is_alive():
                time.sleep(0.5)
            # Observer died unexpectedly
            raise RuntimeError("watchdog observer exited unexpectedly")
        except KeyboardInterrupt:
            print(f"\n{Color.YELLOW}ARISE-I » Shutdown signal received.  Stopping...{Color.RESET}")
            handler._timer.cancel()
            observer.stop()
            if observer.is_alive():
                observer.join()
            print(f"{Color.CYAN}ARISE-I » Daemon offline.{Color.RESET}")
            return
        except Exception as exc:
            handler._timer.cancel()
            observer.stop()
            if observer.is_alive():
                observer.join(timeout=5)
            restart_count += 1
            if restart_count > max_restarts:
                print(
                    f"{Color.RED}ARISE-I » Watch daemon failed after "
                    f"{max_restarts} restarts ({exc}).  Giving up.{Color.RESET}"
                )
                return
            print(
                f"{Color.YELLOW}ARISE-I » Observer crashed ({exc}). "
                f"Restarting in {backoff:.0f}s "
                f"({restart_count}/{max_restarts})...{Color.RESET}"
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not WATCHDOG_AVAILABLE:
        print(
            "\n[ARISE-I] ✗  watchdog is not installed.\n"
            "           Run:  pip install watchdog\n"
            "           Then re-run ARISE-I watch mode.\n"
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="ARISE-I Watch-Folder Daemon — sorts files as they arrive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python file_watcher.py                           # watch ~/Downloads (live)
  python file_watcher.py --dry-run                 # preview only
  python file_watcher.py --path ~/Desktop          # custom folder
  python file_watcher.py --debounce 5              # wait 5s of quiet
  python file_watcher.py --config my.config.yaml   # custom categories
        """,
    )
    parser.add_argument(
        "--path", default="~/Downloads",
        help="Folder to watch (default: ~/Downloads)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would happen without moving anything",
    )
    parser.add_argument(
        "--debounce", type=float, default=DEFAULT_DEBOUNCE,
        help=f"Seconds of FS quiet before triggering sort (default: {DEFAULT_DEBOUNCE})",
    )
    parser.add_argument(
        "--config", default=None, type=Path,
        help="Path to a arise-i.config.yaml for custom category mappings",
    )
    args = parser.parse_args()

    boot_sequence(dry_run=args.dry_run)
    categories = load_categories(args.config, args.path)
    watch_folder(
        target_dir=args.path,
        debounce=args.debounce,
        dry_run=args.dry_run,
        categories=categories,
    )
