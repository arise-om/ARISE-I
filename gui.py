"""
ARISE-I — GUI Wrapper
---------------------
Autonomous File Organization Unit: Desktop Interface.
Built by Om // Ironlabs.tech

A beautiful, Apple-style minimalist GUI that makes file organization effortless.
Clean design, intuitive controls, and smart defaults for a seamless experience.

Launch:
    python gui.py          # Linux / macOS / Windows
    python3 gui.py         # Linux if 'python' isn't on PATH

Requirements:
    pip install pyyaml watchdog   # core deps
    sudo apt install python3-tk   # Ubuntu/Debian only
    # macOS / Windows: tkinter ships with Python by default
"""

import queue
import sys
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Python version guard — must be 3.10+
# ---------------------------------------------------------------------------

if sys.version_info < (3, 10):
    print(
        f"\n[ARISE-I] ✗  Python 3.10+ is required.\n"
        f"           You are running Python {sys.version_info.major}.{sys.version_info.minor}.\n"
        f"           Please upgrade Python and try again.\n"
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# tkinter availability check
# ---------------------------------------------------------------------------

try:
    import tkinter as tk
    from tkinter import filedialog, font as tkfont, messagebox, scrolledtext, ttk
except ImportError:
    print(
        "\n[ARISE-I] ✗  tkinter is not installed.\n"
        "           Ubuntu/Debian:  sudo apt install python3-tk\n"
        "           macOS/Windows:  reinstall Python from python.org (check 'tcl/tk' option)\n"
        "           Then re-run:    python gui.py\n"
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Core imports
# ---------------------------------------------------------------------------

from file_organizer import (
    Stats,
    load_categories,
    organize_folder,
    undo_last_run,
)

APP_VERSION = "1.3.0"

# watchdog is optional — only required for Watch mode.
# file_watcher now sets WATCHDOG_AVAILABLE safely (no sys.exit at import time).
try:
    from file_watcher import WATCHDOG_AVAILABLE, AriseIEventHandler
except Exception:  # pragma: no cover — edge case where file_watcher itself breaks
    WATCHDOG_AVAILABLE = False
    AriseIEventHandler  = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Palette  (Apple-style light theme)
# ---------------------------------------------------------------------------

BG          = "#f5f5f7"   # Apple light gray background
SURFACE     = "#ffffff"   # pure white for cards
BORDER      = "#e5e5e7"   # subtle border
ACCENT      = "#007AFF"   # Apple blue — primary accent
ACCENT_DIM  = "#0056b3"   # darker blue — secondary / hover
GREEN       = "#34C759"   # Apple green
YELLOW      = "#FFD60A"   # Apple yellow
RED         = "#FF3B30"   # Apple red
FG          = "#1d1d1f"   # Apple dark text
FG_DIM      = "#86868b"   # Apple gray text
FONT_FAMILY = "SF Pro Display"  # Apple system font


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _font(size: int = 10, weight: str = "normal") -> tuple:
    """Return font tuple with fallbacks for different platforms."""
    if sys.platform == "darwin":
        return ("SF Pro Display", size, weight)
    elif sys.platform == "win32":
        return ("Segoe UI", size, weight)
    else:
        return ("Ubuntu", size, weight)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class AriseIApp(tk.Tk):
    """The ARISE-I desktop application window."""

    # -----------------------------------------------------------------
    # Initialisation
    # -----------------------------------------------------------------

    def __init__(self):
        super().__init__()

        self.title("ARISE-I")
        self.geometry("700x500")
        self.minsize(600, 400)
        self.configure(bg=BG)
        self.resizable(True, True)

        # App icon (drawn programmatically — no .ico file needed)
        self._set_icon()

        # State
        self._watch_thread: threading.Thread | None = None
        self._watch_stop   = threading.Event()
        self._log_queue: queue.Queue = queue.Queue()
        self._watching     = False

        # Default target: ~/Downloads — create it if it doesn't exist on this PC
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        self._target_var   = tk.StringVar(value=str(downloads))
        self._dry_run_var  = tk.BooleanVar(value=False)
        self._debounce_var = tk.DoubleVar(value=2.0)
        self._auto_sort_var = tk.BooleanVar(value=False)

        # Build UI
        self._build_styles()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Emit a startup banner
        self._log("Welcome to ARISE-I", "hdr")
        self._log("Your personal file organizer", "dim")
        if not WATCHDOG_AVAILABLE:
            self._log(
                "⚠  Auto-sort requires watchdog (pip install watchdog)",
                "sim",
            )

        # Start polling the log queue
        self._poll_log_queue()

        # Add keyboard shortcuts
        self._setup_keyboard_shortcuts()

    # -----------------------------------------------------------------
    # Icon (no external files required)
    # -----------------------------------------------------------------

    def _set_icon(self) -> None:
        try:
            icon = tk.PhotoImage(width=32, height=32)
            # Simple "A" shape in Apple blue on white bg
            for y in range(32):
                for x in range(32):
                    if (y >= 8 and y <= 24 and x >= 12 and x <= 20) or \
                       (y >= 8 and y <= 24 and x >= 8 and x <= 12 and (x-8) == (y-8)) or \
                       (y >= 8 and y <= 24 and x >= 20 and x <= 24 and (24-x) == (y-8)):
                        icon.put("#007AFF", (x, y))
                    else:
                        icon.put("#ffffff", (x, y))
            self.iconphoto(True, icon)
        except Exception:
            pass  # Non-fatal — icon is cosmetic only

    # -----------------------------------------------------------------
    # ttk Styles (Apple-style light theme)
    # -----------------------------------------------------------------

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        # General
        style.configure(".", background=BG, foreground=FG,
                         font=_font(10), borderwidth=0)

        # Frames
        style.configure("Card.TFrame", background=SURFACE, relief="flat")
        style.configure("Sep.TFrame",  background=BORDER)

        # Labels
        style.configure("Title.TLabel",   background=BG,      foreground=FG,
                         font=_font(24, "bold"))
        style.configure("Sub.TLabel",     background=BG,      foreground=FG_DIM,
                         font=_font(12))
        style.configure("Card.TLabel",    background=SURFACE, foreground=FG,
                         font=_font(11))
        style.configure("CardDim.TLabel", background=SURFACE, foreground=FG_DIM,
                         font=_font(10))

        # Entry
        style.configure("Apple.TEntry",
                         fieldbackground=BG, foreground=FG,
                         insertcolor=ACCENT, bordercolor=BORDER,
                         relief="flat", padding=12, font=_font(11))

        # Buttons
        style.configure("Primary.TButton",
                         background=ACCENT,    foreground="white",
                         font=_font(11, "bold"), padding=(20, 10),
                         relief="flat")
        style.map("Primary.TButton",
                  background=[("active", ACCENT_DIM), ("disabled", BORDER)],
                  foreground=[("disabled", FG_DIM)])

        style.configure("Secondary.TButton",
                         background=SURFACE,   foreground=FG,
                         font=_font(11),       padding=(20, 10),
                         relief="flat", borderwidth=1)
        style.map("Secondary.TButton",
                  background=[("active", BG)])

        style.configure("Danger.TButton",
                         background=RED,  foreground="white",
                         font=_font(11, "bold"), padding=(20, 10),
                         relief="flat")
        style.map("Danger.TButton",
                  background=[("active", "#c93d34")])

        # Checkbutton
        style.configure("Apple.TCheckbutton",
                         background=SURFACE, foreground=FG,
                         font=_font(11))
        style.map("Apple.TCheckbutton",
                  background=[("active", SURFACE)])

        # Spinbox label
        style.configure("Dim.TLabel", background=SURFACE, foreground=FG_DIM,
                         font=_font(10))

    # -----------------------------------------------------------------
    # UI Layout
    # -----------------------------------------------------------------

    def _build_ui(self) -> None:
        # ── Header ────────────────────────────────────────────────────
        header = tk.Frame(self, bg=BG, pady=30)
        header.pack(fill="x")

        tk.Label(header, text="ARISE-I", font=_font(32, "bold"),
                 fg=FG, bg=BG).pack(pady=(0, 8))
        tk.Label(header, text="A calmer Downloads folder, in one click.",
                 font=_font(13), fg=FG_DIM, bg=BG).pack()

        # ── Main Action Button ────────────────────────────────────────
        main_frame = tk.Frame(self, bg=BG, padx=40, pady=20)
        main_frame.pack(fill="both", expand=True)

        # Big primary button
        self._sort_btn = tk.Button(
            main_frame,
            text="✨  Organize Now",
            font=_font(14, "bold"), fg="white", bg=ACCENT,
            activebackground=ACCENT_DIM, activeforeground="white",
            relief="flat", bd=0, padx=40, pady=15,
            cursor="hand2", command=self._sort_now,
        )
        self._sort_btn.pack(pady=(20, 10))

        tk.Label(
            main_frame,
            text="Files stay on your computer. Nothing is deleted, and every run can be undone.",
            font=_font(10), fg=FG_DIM, bg=BG,
        ).pack(pady=(0, 8))

        # Secondary actions in a row
        secondary_frame = tk.Frame(main_frame, bg=BG)
        secondary_frame.pack(pady=10)

        # Auto-sort toggle
        self._auto_check = tk.Checkbutton(
            secondary_frame,
            text="Auto-sort new files",
            variable=self._auto_sort_var,
            font=_font(11), fg=FG, bg=BG,
            selectcolor=ACCENT, activebackground=BG,
            activeforeground="white", relief="flat", bd=0, cursor="hand2",
            command=self._toggle_auto_sort
        )
        self._auto_check.pack(side="left", padx=10)

        # Folder selector
        folder_frame = tk.Frame(secondary_frame, bg=BG)
        folder_frame.pack(side="left", padx=10)

        tk.Label(folder_frame, text="📁", font=_font(12), fg=FG_DIM, bg=BG).pack(side="left")
        path_entry = tk.Entry(folder_frame, textvariable=self._target_var,
                               font=_font(11), bg=BG, fg=FG,
                               insertbackground=ACCENT, relief="flat",
                               bd=0, highlightthickness=0,
                               width=30)
        path_entry.pack(side="left", padx=5)
        
        browse_btn = tk.Button(folder_frame, text="Change",
                                font=_font(10), fg=ACCENT, bg=BG,
                                activebackground=BG, activeforeground=ACCENT_DIM,
                                relief="flat", bd=0, padx=8, pady=5,
                                cursor="hand2",
                                command=self._browse)
        browse_btn.pack(side="left")

        self._preview_btn = tk.Button(
            main_frame,
            text="Preview changes first",
            font=_font(10), fg=ACCENT, bg=BG,
            activebackground=BG, activeforeground=ACCENT_DIM,
            relief="flat", bd=0, padx=12, pady=6,
            cursor="hand2", command=self._preview,
        )
        self._preview_btn.pack(pady=(2, 0))

        # Undo button (subtle)
        self._undo_btn = tk.Button(
            main_frame,
            text="↩  Undo Last",
            font=_font(10), fg=FG_DIM, bg=BG,
            activebackground=BG, activeforeground=FG,
            relief="flat", bd=0, padx=15, pady=8,
            cursor="hand2", command=self._undo,
        )
        self._undo_btn.pack(pady=5)

        # Help button
        help_btn = tk.Button(
            main_frame,
            text="⌨  Shortcuts",
            font=_font(9), fg=FG_DIM, bg=BG,
            activebackground=BG, activeforeground=ACCENT,
            relief="flat", bd=0, padx=10, pady=5,
            cursor="hand2", command=self._show_help,
        )
        help_btn.pack(pady=5)

        # ── Simple Status ───────────────────────────────────────────────
        self._status_label = tk.Label(
            main_frame,
            text="Ready to organize",
            font=_font(10), fg=FG_DIM, bg=BG,
        )
        self._status_label.pack(pady=(20, 0))

        tk.Label(
            main_frame, text=f"ARISE-I {APP_VERSION}  •  Built by Ironlabs",
            font=_font(9), fg=FG_DIM, bg=BG,
        ).pack(pady=(6, 0))

        # ── Minimal Log (collapsible) ──────────────────────────────────
        log_frame = tk.Frame(main_frame, bg=BG)
        log_frame.pack(fill="both", expand=True, pady=(20, 0))

        self._log_text = tk.Text(
            log_frame,
            bg=BG, fg=FG_DIM, font=_font(9),
            relief="flat", bd=0,
            state="disabled",
            wrap="word",
            highlightthickness=0,
            padx=0, pady=0,
            height=6,
        )
        self._log_text.pack(fill="both", expand=True)

        # Configure colour tags for the log
        self._log_text.tag_configure("ok",  foreground=GREEN)
        self._log_text.tag_configure("sim", foreground=YELLOW)
        self._log_text.tag_configure("err", foreground=RED)
        self._log_text.tag_configure("dim", foreground=FG_DIM)
        self._log_text.tag_configure("hdr", foreground=ACCENT,
                                      font=_font(9, "bold"))

    def _setup_keyboard_shortcuts(self) -> None:
        """Add keyboard shortcuts for power users."""
        # Ctrl/Cmd + O: Organize
        self.bind('<Control-o>', lambda e: self._sort_now())
        self.bind('<Command-o>', lambda e: self._sort_now())
        
        # Ctrl/Cmd + Z: Undo
        self.bind('<Control-z>', lambda e: self._undo())
        self.bind('<Command-z>', lambda e: self._undo())
        
        # Ctrl/Cmd + Q: Quit
        self.bind('<Control-q>', lambda e: self.quit())
        self.bind('<Command-q>', lambda e: self.quit())
        
        # Ctrl/Cmd + B: Browse folder
        self.bind('<Control-b>', lambda e: self._browse())
        self.bind('<Command-b>', lambda e: self._browse())
        
        # Ctrl/Cmd + L: Clear log
        self.bind('<Control-l>', lambda e: self._clear_log())
        self.bind('<Command-l>', lambda e: self._clear_log())

    # -----------------------------------------------------------------
    # Log helpers
    # -----------------------------------------------------------------

    def _poll_log_queue(self) -> None:
        """Drain the log queue into the Text widget. Runs on the main thread."""
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg == "__DONE__":
                    self._set_buttons_enabled(True)
                    self._set_status("Ready.")
                    continue
                if msg == "__WATCH_DONE__":
                    continue
                # Tag selection
                if msg.startswith("✓"):
                    tag = "ok"
                elif msg.startswith("[SIM]"):
                    tag = "sim"
                elif msg.startswith("✗") or msg.startswith("⚠"):
                    tag = "err"
                elif msg.startswith("──") or msg.startswith("ARISE-I"):
                    tag = "hdr"
                else:
                    tag = ""
                self._log(msg, tag)
        except queue.Empty:
            pass
        self.after(50, self._poll_log_queue)

    def _log(self, message: str, tag: str = "") -> None:
        """Append a line to the log text widget (must be called from main thread)."""
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _log_separator(self) -> None:
        self._log("─" * 52, "dim")

    def _show_help(self) -> None:
        """Show keyboard shortcuts help dialog."""
        help_text = """Keyboard Shortcuts:

Ctrl/Cmd + O   Organize files
Ctrl/Cmd + Z   Undo last organization
Ctrl/Cmd + B   Browse folder
Ctrl/Cmd + L   Clear log
Ctrl/Cmd + Q   Quit application

Tips:
• Enable auto-sort to automatically organize new files
• Click 'Change' to organize a different folder
• Use 'Undo Last' to reverse any organization
• Files are never deleted, only organized
"""
        messagebox.showinfo("Keyboard Shortcuts", help_text)

    def _set_status(self, text: str) -> None:
        self._status_label.configure(text=text)

    # -----------------------------------------------------------------
    # Log queue polling (thread-safe bridge)
    # -----------------------------------------------------------------

    def _enqueue_log(self, message: str) -> None:
        """Called from worker threads — safe to call from any thread."""
        self._log_queue.put(message)



    # -----------------------------------------------------------------
    # Button: Browse
    # -----------------------------------------------------------------

    def _browse(self) -> None:
        if self._watching:
            messagebox.showinfo(
                "Auto-sort is running",
                "Turn off Auto-sort before choosing a different folder.",
                parent=self,
            )
            return
        folder = filedialog.askdirectory(
            title="Select folder to organize",
            initialdir=self._target_var.get(),
        )
        if folder:
            self._target_var.set(folder)
            self._log(f"Folder changed to: {Path(folder).name}", "dim")

    def _toggle_auto_sort(self) -> None:
        if self._auto_sort_var.get():
            if not WATCHDOG_AVAILABLE:
                self._log("⚠  Auto-sort requires watchdog (pip install watchdog)", "err")
                self._auto_sort_var.set(False)
                return
            self._start_watch()
        else:
            self._stop_watch()

    # -----------------------------------------------------------------
    # Button: Sort Now
    # -----------------------------------------------------------------

    def _preview(self) -> None:
        """Show the user what ARISE-I would do without moving any files."""
        self._run_organization(dry_run=True)

    def _sort_now(self) -> None:
        """Confirm a live organization run before moving the user's files."""
        target = self._target_var.get().strip()
        if target and not messagebox.askyesno(
            "Organize this folder?",
            "ARISE-I will sort the files in:\n\n"
            f"{Path(target).expanduser()}\n\n"
            "No files will be deleted, and you can undo this run afterwards.",
            parent=self,
        ):
            return
        self._run_organization(dry_run=False)

    def _run_organization(self, dry_run: bool) -> None:
        target = self._target_var.get().strip()
        if not target:
            messagebox.showerror("No folder selected",
                                 "Please select a folder to organize.")
            return
        
        target_path = Path(target).expanduser()
        if not target_path.exists():
            messagebox.showerror("Folder not found",
                                 f"The folder does not exist:\n{target}")
            return

        if not target_path.is_dir():
            messagebox.showerror("Not a folder",
                                 f"The path is not a folder:\n{target}")
            return

        # A file organizer should never be pointed at a whole user account or
        # filesystem by accident. Downloads and other subfolders remain safe.
        if target_path == target_path.anchor or target_path == Path.home().resolve():
            messagebox.showerror(
                "Choose a specific folder",
                "For your safety, ARISE-I cannot organize your entire home folder "
                "or the whole drive. Choose Downloads, Desktop, or another specific folder.",
                parent=self,
            )
            return

        self._set_buttons_enabled(False)
        self._set_status("Previewing changes…" if dry_run else "Organizing…")
        self._log("🔎  Previewing changes" if dry_run else "✨  Starting organization", "hdr")

        def _worker():
            try:
                categories = load_categories(None)
                stats: Stats = organize_folder(
                    target,
                    dry_run=dry_run,
                    categories=categories,
                    log_callback=self._enqueue_log,
                )
                # Summary lines
                action = "would be organized" if dry_run else "organized"
                self._log_queue.put(f"✓  Done! {stats.total_files()} file(s) {action}")
                if stats.skipped:
                    self._log_queue.put(f"   {stats.skipped} skipped")
                if stats.errors:
                    self._log_queue.put(f"   {stats.errors} error(s)")
            except Exception as e:
                self._log_queue.put(f"✗  Error: {str(e)}")
                self._log_queue.put("   Please check the folder and try again")
            finally:
                # Re-enable from main thread via queue sentinel
                self._log_queue.put("__DONE__")

        threading.Thread(target=_worker, daemon=True).start()

    # -----------------------------------------------------------------
    # Auto-sort / Watch functionality
    # -----------------------------------------------------------------

    def _start_watch(self) -> None:
        if not WATCHDOG_AVAILABLE:
            messagebox.showerror(
                "watchdog not installed",
                "Auto-sort requires the watchdog package.\n\n"
                "Run this in your terminal:\n"
                "    pip install watchdog",
            )
            return

        target = self._target_var.get().strip()
        if not target or not Path(target).expanduser().exists():
            messagebox.showerror("Folder not found",
                                 f"The folder does not exist:\n{target}")
            return

        self._watching = True
        self._watch_stop.clear()
        self._sort_btn.configure(state="disabled")
        self._set_status(f"Auto-sorting {Path(target).name}…")
        self._log("🔄  Auto-sort enabled", "hdr")

        debounce   = self._debounce_var.get()
        # Validate debounce value
        if debounce < 0.1:
            debounce = 0.1
            self._debounce_var.set(debounce)
        elif debounce > 300.0:
            debounce = 300.0
            self._debounce_var.set(debounce)
        dry_run    = self._dry_run_var.get()
        categories = load_categories(None)

        def _worker():
            # Use the already-imported Observer (safe because we checked
            # WATCHDOG_AVAILABLE before entering this branch)
            from watchdog.observers import Observer as _Observer
            from file_watcher import AriseIEventHandler

            # Override the handler's _run_organizer to use log_callback
            class _GUIHandler(AriseIEventHandler):
                def _run_organizer(inner_self):
                    self._log_queue.put("📁  New files detected, organizing…")
                    cats = load_categories(None)
                    s = organize_folder(
                        str(inner_self.target_dir),
                        dry_run=inner_self.dry_run,
                        categories=cats,
                        log_callback=self._enqueue_log,
                    )
                    self._log_queue.put(f"✓  {s.total_files()} file(s) organized")

            from pathlib import Path as _Path
            handler  = _GUIHandler(
                target_dir=_Path(target).expanduser().resolve(),
                debounce=debounce,
                dry_run=dry_run,
                categories=categories,
            )
            observer = _Observer()
            observer.schedule(handler, str(handler.target_dir), recursive=False)
            observer.start()

            import time
            while not self._watch_stop.is_set():
                time.sleep(0.5)

            try:
                handler._timer.cancel()
            except Exception:  # pragma: no cover
                pass
            observer.stop()
            if observer.is_alive():
                observer.join(timeout=5)
            self._log_queue.put("🛑  Auto-sort stopped")
            self._log_queue.put("__WATCH_DONE__")

        self._watch_thread = threading.Thread(target=_worker, daemon=True)
        self._watch_thread.start()

    def _stop_watch(self) -> None:
        self._watch_stop.set()
        self._watching = False
        self._sort_btn.configure(state="normal")
        self._set_status("Ready to organize")

    def _on_close(self) -> None:
        """Stop the file observer before closing the desktop app."""
        if self._watching:
            self._stop_watch()
        self.destroy()

    # -----------------------------------------------------------------
    # Button: Undo
    # -----------------------------------------------------------------

    def _undo(self) -> None:
        target = self._target_var.get().strip()
        if not target:
            messagebox.showerror("No folder selected",
                                 "Please select a folder to undo.")
            return

        target_path = Path(target).expanduser()
        if not target_path.exists():
            messagebox.showerror("Folder not found",
                                 f"The folder does not exist:\n{target}")
            return

        self._set_buttons_enabled(False)
        self._set_status("Undoing last organization…")
        self._log("↩  Undoing last organization", "hdr")

        def _worker():
            try:
                # Capture stdout-ish output for the GUI log
                # (undo_last_run prints to stdout; we redirect via a simple shim)
                import io, contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    undo_last_run(target)
                output = buf.getvalue()
                for line in output.splitlines():
                    stripped = line.strip()
                    if stripped:
                        self._log_queue.put(stripped)
            except Exception as e:
                self._log_queue.put(f"✗  Error: {str(e)}")
                self._log_queue.put("   Could not undo. Check the folder history.")
            finally:
                self._log_queue.put("__DONE__")

        threading.Thread(target=_worker, daemon=True).start()

    # -----------------------------------------------------------------
    # Queue sentinel handling (re-enable buttons after job finishes)
    # -----------------------------------------------------------------

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._sort_btn.configure(state=state)
        self._preview_btn.configure(state=state)
        self._undo_btn.configure(state=state)
        # Only disable auto-check when organization is in progress
        if not self._watching:
            self._auto_check.configure(state=state)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = AriseIApp()
    app.mainloop()


if __name__ == "__main__":
    main()
