"""ARISE-I v2.0.0 — GUI (AI-Powered Dashboard)"""

import json
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

if sys.version_info < (3, 10):
    print("[ARISE-I] Python 3.10+ required."); sys.exit(1)

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    print("[ARISE-I] tkinter not installed.\n  Ubuntu: sudo apt install python3-tk"); sys.exit(1)

from file_organizer import Stats, load_categories, organize_folder, undo_last_run, _load_manifest
from prefs import get_pref, load_prefs, save_prefs, set_pref
import onboarding

try:
    from file_watcher import WATCHDOG_AVAILABLE, AriseIEventHandler
except Exception:
    WATCHDOG_AVAILABLE = False
    AriseIEventHandler = None

try:
    from health_monitor import HealthMonitor
except ImportError:
    HealthMonitor = None  # type: ignore[assignment,misc]

try:
    from learning_store import LearningStore
except ImportError:
    LearningStore = None  # type: ignore[assignment,misc]

APP_VERSION = "2.0.0"

# ── Colour palettes ───────────────────────────────────────────────────────────
_THEMES: dict[str, dict[str, str]] = {
    "light": {
        "BG":       "#f5f5f7",
        "SURFACE":  "#ffffff",
        "BORDER":   "#e5e5e7",
        "ACCENT":   "#007AFF",
        "ACCENT_D": "#0056b3",
        "GREEN":    "#34C759",
        "YELLOW":   "#FFD60A",
        "RED":      "#FF3B30",
        "FG":       "#1d1d1f",
        "FG_DIM":   "#86868b",
        "PANEL":    "#f0f0f2",
    },
    "dark": {
        "BG":       "#1c1c1e",
        "SURFACE":  "#2c2c2e",
        "BORDER":   "#3a3a3c",
        "ACCENT":   "#0A84FF",
        "ACCENT_D": "#0060df",
        "GREEN":    "#30D158",
        "YELLOW":   "#FFD60A",
        "RED":      "#FF453A",
        "FG":       "#f2f2f7",
        "FG_DIM":   "#8e8e93",
        "PANEL":    "#2c2c2e",
    },
}

# Module-level palette references (updated when theme changes)
_p = _THEMES["light"]
BG         = _p["BG"]
SURFACE    = _p["SURFACE"]
BORDER     = _p["BORDER"]
ACCENT     = _p["ACCENT"]
ACCENT_DIM = _p["ACCENT_D"]
GREEN      = _p["GREEN"]
YELLOW     = _p["YELLOW"]
RED        = _p["RED"]
FG         = _p["FG"]
FG_DIM     = _p["FG_DIM"]
PANEL_BG   = _p["PANEL"]

def _font(size=10, weight="normal"):
    if sys.platform == "darwin":   return ("SF Pro Display", size, weight)
    elif sys.platform == "win32":  return ("Segoe UI", size, weight)
    else:                          return ("Ubuntu", size, weight)


class AriseIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ARISE-I")
        self.geometry("960x620")
        self.minsize(760, 520)

        # Load theme before building UI
        prefs = load_prefs()
        self._theme = prefs.get("theme", "light")
        self._apply_theme(self._theme, init=True)
        self.configure(bg=BG)
        self.resizable(True, True)
        self._set_icon()

        # State
        self._watch_thread = None
        self._watch_stop   = threading.Event()
        self._log_queue    = queue.Queue()
        self._watching     = False
        self._pulse_active = False
        self._pulse_id     = None

        # Prefs
        self._target_var   = tk.StringVar(value=prefs.get("last_folder", str(Path.home()/"Downloads")))
        self._dry_run_var  = tk.BooleanVar(value=False)
        self._debounce_var = tk.DoubleVar(value=prefs.get("debounce", 2.0))
        self._auto_sort_var= tk.BooleanVar(value=False)

        # AI subsystems (optional — graceful degradation)
        self._learning_store = None
        self._health_monitor = None
        self._init_ai_subsystems()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_shortcuts()

        self.after(200, self._run_onboarding)

        self._log("Welcome to ARISE-I", "hdr")
        self._log("Your personal AI-powered file organizer — v" + APP_VERSION, "dim")
        if not WATCHDOG_AVAILABLE:
            self._log("⚠  Auto-sort needs: pip install watchdog", "warn")
        self._poll_log_queue()

    def _init_ai_subsystems(self) -> None:
        if LearningStore is not None:
            try:
                self._learning_store = LearningStore(
                    on_retrain=self._on_model_retrained
                )
            except Exception as exc:
                self._learning_store = None
        if HealthMonitor is not None:
            try:
                target = Path(self._target_var.get()).expanduser().resolve()
                self._health_monitor = HealthMonitor(
                    target_dir=target,
                    log_queue=self._log_queue,
                    learning_store=self._learning_store,
                )
                self._health_monitor.start()
            except Exception:
                self._health_monitor = None

    def _on_model_retrained(self) -> None:
        self._log_queue.put("🧠  ML model retrained — classifier updated.")

    def _set_icon(self):
        try:
            icon = tk.PhotoImage(width=32, height=32)
            for y in range(32):
                for x in range(32):
                    if (8<=y<=24 and 12<=x<=20) or \
                       (8<=y<=24 and 8<=x<=12 and (x-8)==(y-8)) or \
                       (8<=y<=24 and 20<=x<=24 and (24-x)==(y-8)):
                        icon.put("#007AFF",(x,y))
                    else:
                        icon.put("#ffffff",(x,y))
            self.iconphoto(True, icon)
        except Exception:
            pass

    # ------------------------------------------------------------------ Theme

    def _apply_theme(self, name: str, init: bool = False) -> None:
        """Switch the global palette to 'dark' or 'light' and re-draw."""
        global BG, SURFACE, BORDER, ACCENT, ACCENT_DIM, GREEN, YELLOW, RED, FG, FG_DIM, PANEL_BG
        p = _THEMES.get(name, _THEMES["light"])
        BG         = p["BG"]
        SURFACE    = p["SURFACE"]
        BORDER     = p["BORDER"]
        ACCENT     = p["ACCENT"]
        ACCENT_DIM = p["ACCENT_D"]
        GREEN      = p["GREEN"]
        YELLOW     = p["YELLOW"]
        RED        = p["RED"]
        FG         = p["FG"]
        FG_DIM     = p["FG_DIM"]
        PANEL_BG   = p["PANEL"]
        self._theme = name
        if not init:
            set_pref("theme", name)
            # Re-configure root and rebuilt UI
            self.configure(bg=BG)
            self._refresh_theme_colors()

    def _refresh_theme_colors(self) -> None:
        """Walk all widgets and update bg/fg to the current palette."""
        def _recurse(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Frame", "Label"):
                    widget.configure(bg=BG)
                elif cls == "Text":
                    widget.configure(bg=BG, fg=FG)
                elif cls == "Entry":
                    widget.configure(bg=SURFACE, fg=FG, insertbackground=ACCENT)
                elif cls == "Button":
                    try:
                        widget.configure(bg=widget.cget("bg"))
                    except Exception:
                        pass
            except Exception:
                pass
            for child in widget.winfo_children():
                _recurse(child)
        _recurse(self)

    def _toggle_theme(self) -> None:
        new = "dark" if self._theme == "light" else "light"
        self._apply_theme(new)
        icon = "🌙" if new == "dark" else "☀️"
        self._theme_btn.configure(text=icon)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # ── Left panel (controls) ────────────────────────────────────────────
        left = tk.Frame(self, bg=BG, width=320)
        left.pack(side="left", fill="y", padx=0)
        left.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(left, bg=ACCENT, pady=20)
        logo_frame.pack(fill="x")
        logo_row = tk.Frame(logo_frame, bg=ACCENT)
        logo_row.pack()
        tk.Label(logo_row, text="ARISE-I", font=_font(26,"bold"),
                 fg="white", bg=ACCENT).pack(side="left", padx=(0,8))
        icon_char = "🌙" if self._theme == "dark" else "☀️"
        self._theme_btn = tk.Button(
            logo_row, text=icon_char, font=_font(14),
            fg="white", bg=ACCENT, activebackground=ACCENT_DIM,
            activeforeground="white", relief="flat", bd=0,
            cursor="hand2", command=self._toggle_theme,
        )
        self._theme_btn.pack(side="left")
        tk.Label(logo_frame, text="AI File Organization Unit",
                 font=_font(10), fg="white", bg=ACCENT).pack(pady=(2,4))

        # Folder section
        folder_card = tk.Frame(left, bg=SURFACE, padx=16, pady=14)
        folder_card.pack(fill="x", padx=12, pady=(16,0))

        tk.Label(folder_card, text="Target Folder", font=_font(10,"bold"),
                 fg=FG, bg=SURFACE).pack(anchor="w")

        path_row = tk.Frame(folder_card, bg=SURFACE)
        path_row.pack(fill="x", pady=(6,0))

        self._path_entry = tk.Entry(path_row, textvariable=self._target_var,
                                    font=_font(9), bg=BG, fg=FG,
                                    insertbackground=ACCENT, relief="flat",
                                    bd=0, highlightthickness=1,
                                    highlightbackground=BORDER,
                                    highlightcolor=ACCENT)
        self._path_entry.pack(side="left", fill="x", expand=True, ipady=5)

        tk.Button(path_row, text="⋯", font=_font(11,"bold"),
                  fg=ACCENT, bg=SURFACE, relief="flat", bd=0,
                  padx=8, cursor="hand2", command=self._browse).pack(side="left", padx=(4,0))

        # Action buttons
        btns = tk.Frame(left, bg=BG, padx=12)
        btns.pack(fill="x", pady=16)

        self._sort_btn = tk.Button(btns, text="✨  Organize Now",
            font=_font(12,"bold"), fg="white", bg=ACCENT,
            activebackground=ACCENT_DIM, activeforeground="white",
            relief="flat", bd=0, pady=12, cursor="hand2",
            command=self._sort_now)
        self._sort_btn.pack(fill="x", pady=(0,6))

        self._preview_btn = tk.Button(btns, text="🔎  Preview Changes",
            font=_font(11), fg=ACCENT, bg=SURFACE,
            activebackground=BG, activeforeground=ACCENT_DIM,
            relief="flat", bd=0, pady=10, cursor="hand2",
            command=self._preview,
            highlightthickness=1, highlightbackground=BORDER)
        self._preview_btn.pack(fill="x", pady=(0,6))

        self._undo_btn = tk.Button(btns, text="↩  Undo Last Run",
            font=_font(10), fg=FG_DIM, bg=BG,
            activebackground=BG, activeforeground=FG,
            relief="flat", bd=0, pady=8, cursor="hand2",
            command=self._undo)
        self._undo_btn.pack(fill="x")

        # Auto-sort toggle
        sep1 = tk.Frame(left, bg=BORDER, height=1)
        sep1.pack(fill="x", padx=12, pady=(4,12))

        auto_card = tk.Frame(left, bg=SURFACE, padx=16, pady=12)
        auto_card.pack(fill="x", padx=12)

        auto_top = tk.Frame(auto_card, bg=SURFACE)
        auto_top.pack(fill="x")
        tk.Label(auto_top, text="Auto-Sort", font=_font(10,"bold"),
                 fg=FG, bg=SURFACE).pack(side="left")

        self._auto_check = tk.Checkbutton(auto_top, variable=self._auto_sort_var,
            bg=SURFACE, activebackground=SURFACE, relief="flat",
            cursor="hand2", command=self._toggle_auto_sort)
        self._auto_check.pack(side="right")

        # Daemon pulse indicator
        self._pulse_label = tk.Label(auto_card, text="● Idle",
            font=_font(9), fg=FG_DIM, bg=SURFACE)
        self._pulse_label.pack(anchor="w", pady=(4,0))

        tk.Label(auto_card, text="Sorts new files as they arrive",
                 font=_font(9), fg=FG_DIM, bg=SURFACE).pack(anchor="w")

        # Version footer
        tk.Label(left, text=f"v{APP_VERSION}  •  Ironlabs.tech",
                 font=_font(8), fg=FG_DIM, bg=BG).pack(side="bottom", pady=10)

        # ── Divider ──────────────────────────────────────────────────
        div = tk.Frame(self, bg=BORDER, width=1)
        div.pack(side="left", fill="y")

        # ── Right panel (tabs) ───────────────────────────────────────
        right = tk.Frame(self, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # Tab bar (manual)
        tab_bar = tk.Frame(right, bg=SURFACE, pady=0)
        tab_bar.pack(fill="x")

        self._tab_frames = {}
        self._tab_btns   = {}
        self._active_tab = tk.StringVar(value="log")

        for tab_id, tab_label in [("log","Activity Log"), ("history","History"),
                                   ("stats","Last Run"),   ("review","Review Queue")]:
            btn = tk.Button(tab_bar, text=tab_label,
                font=_font(10), fg=FG_DIM, bg=SURFACE,
                relief="flat", bd=0, padx=20, pady=10,
                cursor="hand2",
                command=lambda t=tab_id: self._switch_tab(t))
            btn.pack(side="left")
            self._tab_btns[tab_id] = btn

        sep2 = tk.Frame(right, bg=BORDER, height=1)
        sep2.pack(fill="x")

        content = tk.Frame(right, bg=BG)
        content.pack(fill="both", expand=True)

        # Log tab
        log_frame = tk.Frame(content, bg=BG)
        self._tab_frames["log"] = log_frame

        self._log_text = tk.Text(log_frame, bg=BG, fg=FG_DIM, font=_font(9),
            relief="flat", bd=0, state="disabled", wrap="word",
            highlightthickness=0, padx=16, pady=12)
        log_scroll = tk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True)

        self._log_text.tag_configure("ok",   foreground=GREEN)
        self._log_text.tag_configure("warn", foreground=YELLOW)
        self._log_text.tag_configure("err",  foreground=RED)
        self._log_text.tag_configure("dim",  foreground=FG_DIM)
        self._log_text.tag_configure("hdr",  foreground=ACCENT, font=_font(9,"bold"))

        # History tab
        hist_frame = tk.Frame(content, bg=BG)
        self._tab_frames["history"] = hist_frame
        self._build_history_tab(hist_frame)

        # Stats tab
        stats_frame = tk.Frame(content, bg=BG)
        self._tab_frames["stats"] = stats_frame
        self._stats_frame_ref = stats_frame

        # Review Queue tab
        review_frame = tk.Frame(content, bg=BG)
        self._tab_frames["review"] = review_frame
        self._build_review_tab(review_frame)

        # Status bar
        self._status_bar = tk.Label(right, text="Ready to organize",
            font=_font(9), fg=FG_DIM, bg=SURFACE, pady=6)
        self._status_bar.pack(side="bottom", fill="x")
        tk.Frame(right, bg=BORDER, height=1).pack(side="bottom", fill="x")

        self._switch_tab("log")

    def _switch_tab(self, tab_id: str):
        for tid, frame in self._tab_frames.items():
            frame.pack_forget()
        self._tab_frames[tab_id].pack(fill="both", expand=True)
        for tid, btn in self._tab_btns.items():
            if tid == tab_id:
                btn.configure(fg=ACCENT, font=_font(10,"bold"))
            else:
                btn.configure(fg=FG_DIM, font=_font(10))
        self._active_tab.set(tab_id)
        if tab_id == "history":
            self._refresh_history()
        if tab_id == "review":
            self._refresh_review()

    # ------------------------------------------------------------------ History

    def _build_history_tab(self, parent):
        self._hist_inner = tk.Frame(parent, bg=BG)
        self._hist_inner.pack(fill="both", expand=True)

        self._hist_canvas = tk.Canvas(self._hist_inner, bg=BG,
                                       highlightthickness=0)
        self._hist_scroll = tk.Scrollbar(self._hist_inner,
                                          command=self._hist_canvas.yview)
        self._hist_canvas.configure(yscrollcommand=self._hist_scroll.set)
        self._hist_scroll.pack(side="right", fill="y")
        self._hist_canvas.pack(side="left", fill="both", expand=True)

        self._hist_container = tk.Frame(self._hist_canvas, bg=BG)
        self._hist_canvas_window = self._hist_canvas.create_window(
            (0,0), window=self._hist_container, anchor="nw")
        self._hist_container.bind("<Configure>", lambda e: self._hist_canvas.configure(
            scrollregion=self._hist_canvas.bbox("all")))
        self._hist_canvas.bind("<Configure>", lambda e: self._hist_canvas.itemconfig(
            self._hist_canvas_window, width=e.width))

    def _refresh_history(self):
        for w in self._hist_container.winfo_children():
            w.destroy()

        target = Path(self._target_var.get()).expanduser().resolve()
        history = _load_manifest(target)

        if not history:
            tk.Label(self._hist_container, text="No runs recorded yet.",
                     font=_font(11), fg=FG_DIM, bg=BG, pady=40).pack()
            return

        for i, run in enumerate(reversed(history)):
            ts    = run.get("timestamp","unknown")
            moves = run.get("moves", [])
            self._build_history_card(self._hist_container, ts, moves, i)

    def _build_history_card(self, parent, ts, moves, idx):
        card = tk.Frame(parent, bg=SURFACE, padx=16, pady=12)
        card.pack(fill="x", padx=16, pady=(12,0) if idx==0 else (6,0))

        top = tk.Frame(card, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text=f"📁  Run — {ts}", font=_font(10,"bold"),
                 fg=FG, bg=SURFACE).pack(side="left")
        tk.Label(top, text=f"{len(moves)} files", font=_font(9),
                 fg=FG_DIM, bg=SURFACE).pack(side="right")

        # Category breakdown
        cats: dict[str,int] = {}
        for m in moves:
            dest = Path(m.get("dest",""))
            cat  = dest.parent.name if dest.parent.name else "Others"
            cats[cat] = cats.get(cat, 0) + 1

        summary = "  ·  ".join(f"{c}: {n}" for c,n in
                                sorted(cats.items(), key=lambda x:-x[1])[:4])
        if summary:
            tk.Label(card, text=summary, font=_font(9), fg=FG_DIM, bg=SURFACE).pack(anchor="w",pady=(4,0))

    # ------------------------------------------------------------------ Stats card

    def _show_stats_card(self, stats: Stats, dry_run: bool):
        frame = self._stats_frame_ref
        for w in frame.winfo_children():
            w.destroy()

        action = "would be organized" if dry_run else "organized"
        title  = "Preview Results" if dry_run else "✅  Done!"

        tk.Label(frame, text=title, font=_font(18,"bold"),
                 fg=FG, bg=BG, pady=20).pack()
        tk.Label(frame, text=f"{stats.total_files()} files {action}",
                 font=_font(13), fg=FG_DIM, bg=BG).pack()

        if stats._data:
            table = tk.Frame(frame, bg=SURFACE, padx=20, pady=16)
            table.pack(padx=32, pady=16, fill="x")

            sorted_cats = sorted(stats._data.items(), key=lambda kv:-kv[1]["count"])
            for cat, data in sorted_cats[:8]:
                row = tk.Frame(table, bg=SURFACE)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=cat, font=_font(10), fg=FG,
                         bg=SURFACE, width=18, anchor="w").pack(side="left")
                bar_w = max(4, int(80 * data["count"] / max(1, stats.total_files())))
                bar = tk.Frame(row, bg=ACCENT if not dry_run else YELLOW,
                               height=8, width=bar_w)
                bar.pack(side="left", padx=(8,4))
                bar.pack_propagate(False)
                tk.Label(row, text=str(data["count"]), font=_font(9),
                         fg=FG_DIM, bg=SURFACE).pack(side="left")

        if stats.errors:
            tk.Label(frame, text=f"⚠  {stats.errors} error(s) — check Activity Log",
                     font=_font(10), fg=RED, bg=BG).pack()

        tk.Button(frame, text="Back to Log", font=_font(10), fg=ACCENT,
                  bg=BG, relief="flat", bd=0, padx=12, pady=8,
                  cursor="hand2",
                  command=lambda: self._switch_tab("log")).pack(pady=8)

        self._switch_tab("stats")

    # ------------------------------------------------------------------ Review Queue

    def _build_review_tab(self, parent):
        """Scrollable list of files in __Review__/ that need user confirmation."""
        self._review_inner  = tk.Frame(parent, bg=BG)
        self._review_inner.pack(fill="both", expand=True)

        self._review_canvas = tk.Canvas(self._review_inner, bg=BG, highlightthickness=0)
        self._review_scroll = tk.Scrollbar(self._review_inner,
                                            command=self._review_canvas.yview)
        self._review_canvas.configure(yscrollcommand=self._review_scroll.set)
        self._review_scroll.pack(side="right", fill="y")
        self._review_canvas.pack(side="left", fill="both", expand=True)

        self._review_container = tk.Frame(self._review_canvas, bg=BG)
        self._review_canvas_win = self._review_canvas.create_window(
            (0, 0), window=self._review_container, anchor="nw")
        self._review_container.bind("<Configure>", lambda e:
            self._review_canvas.configure(scrollregion=self._review_canvas.bbox("all")))
        self._review_canvas.bind("<Configure>", lambda e:
            self._review_canvas.itemconfig(self._review_canvas_win, width=e.width))

    def _refresh_review(self):
        for w in self._review_container.winfo_children():
            w.destroy()

        target  = Path(self._target_var.get()).expanduser().resolve()
        rev_dir = target / "__Review__"

        if not rev_dir.exists() or not any(rev_dir.iterdir()):
            tk.Label(self._review_container,
                     text="✅  Nothing in Review — all files classified confidently.",
                     font=_font(11), fg=FG_DIM, bg=BG, pady=40).pack()
            return

        tk.Label(self._review_container,
                 text="These files had low confidence. Confirm the correct folder:",
                 font=_font(10), fg=FG_DIM, bg=BG, padx=16, pady=8).pack(anchor="w")

        for item in sorted(rev_dir.iterdir()):
            if item.is_file() and not item.name.startswith("."):
                self._build_review_card(self._review_container, item, target)

    def _build_review_card(self, parent, item: Path, target: Path):
        card = tk.Frame(parent, bg=SURFACE, padx=14, pady=10)
        card.pack(fill="x", padx=16, pady=(8, 0))

        top = tk.Frame(card, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text=item.name, font=_font(10, "bold"),
                 fg=FG, bg=SURFACE).pack(side="left")
        tk.Label(top, text=f"{item.suffix.upper()} • {self._human_size(item)}",
                 font=_font(9), fg=FG_DIM, bg=SURFACE).pack(side="right")

        # Suggest categories based on extension + common guesses
        cats = list(load_categories(None).keys())[:6]
        btn_row = tk.Frame(card, bg=SURFACE)
        btn_row.pack(fill="x", pady=(6, 0))
        for cat in cats:
            tk.Button(
                btn_row, text=cat,
                font=_font(9), fg=ACCENT, bg=BG,
                relief="flat", bd=0, padx=6, pady=3,
                cursor="hand2",
                command=lambda i=item, c=cat, t=target: self._confirm_category(i, c, t),
            ).pack(side="left", padx=(0, 4))

    def _confirm_category(self, item: Path, category: str, target: Path):
        """Move a Review file to the chosen category and record feedback."""
        import shutil
        dest_dir  = target / category
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / item.name
        try:
            shutil.move(str(item), str(dest_path))
            self._log(f"✓  Review resolved: {item.name}  →  {category}/  [USER]", "ok")
            # Record correction in learning store
            if self._learning_store is not None:
                try:
                    self._learning_store.record(
                        path=item,
                        predicted="__Review__",
                        confirmed=category,
                        confidence=0.0,
                        layer="user_review",
                    )
                except Exception:
                    pass
            self._refresh_review()
        except Exception as exc:
            self._log(f"✗  Could not move {item.name}: {exc}", "err")

    @staticmethod
    def _human_size(path: Path) -> str:
        try:
            b = path.stat().st_size
            for u in ("B","KB","MB","GB"):
                if b < 1024: return f"{b:.0f} {u}"
                b /= 1024
            return f"{b:.1f} GB"
        except Exception:
            return "?"

    # ------------------------------------------------------------------ Pulse

    def _start_pulse(self):
        self._pulse_active = True
        self._do_pulse(True)

    def _do_pulse(self, on: bool):
        if not self._pulse_active:
            self._pulse_label.configure(text="● Idle", fg=FG_DIM)
            return
        self._pulse_label.configure(
            text="● Watching" if on else "○ Watching",
            fg=GREEN if on else FG_DIM)
        self._pulse_id = self.after(700, self._do_pulse, not on)

    def _stop_pulse(self):
        self._pulse_active = False
        if self._pulse_id:
            self.after_cancel(self._pulse_id)
        self._pulse_label.configure(text="● Idle", fg=FG_DIM)

    # ------------------------------------------------------------------ Log

    def _poll_log_queue(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg == "__DONE__":
                    self._set_buttons_enabled(True)
                    self._status_bar.configure(text="Ready.")
                    continue
                if msg == "__WATCH_DONE__":
                    continue
                if msg == "__HEALTH_RETRAIN__":
                    self._log("🧠  Retraining model…", "hdr")
                    continue
                if isinstance(msg, tuple) and msg[0] == "__STATS__":
                    self._show_stats_card(msg[1], msg[2])
                    continue
                # Determine log tag
                tag = "ok"   if msg.startswith("✓") or msg.startswith("✅") else \
                      "warn" if (msg.startswith("⚠") or msg.startswith("[SIM]") or
                                 msg.startswith("⚡") or msg.startswith("♥")) else \
                      "err"  if msg.startswith("✗") else \
                      "hdr"  if (msg.startswith("ARISE-I") or msg.startswith("──")
                                 or msg.startswith("🧠") or msg.startswith("⚔️")) else ""
                # Colour-code confidence badges inline
                if "[HIGH]" in msg:  tag = "ok"
                elif "[LOW]" in msg: tag = "warn"
                ts = datetime.now().strftime("%H:%M:%S")
                self._log(f"[{ts}]  {msg}", tag)
        except queue.Empty:
            pass
        self.after(50, self._poll_log_queue)

    def _log(self, message: str, tag: str = ""):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _enqueue_log(self, message: str):
        self._log_queue.put(message)

    def _set_status(self, text: str):
        self._status_bar.configure(text=text)

    # ------------------------------------------------------------------ Actions

    def _run_onboarding(self):
        folder = onboarding.run_if_needed(self)
        if folder:
            self._target_var.set(folder)
            self._log(f"Folder set to: {Path(folder).name}", "dim")

    def _browse(self):
        if self._watching:
            messagebox.showinfo("Auto-sort running",
                "Turn off Auto-sort before changing folder.", parent=self)
            return
        folder = filedialog.askdirectory(title="Select folder to organize",
                                          initialdir=self._target_var.get())
        if folder:
            self._target_var.set(folder)
            set_pref("last_folder", folder)
            self._log(f"Folder changed to: {Path(folder).name}", "dim")

    def _preview(self):
        self._run_organization(dry_run=True)

    def _sort_now(self):
        target = self._target_var.get().strip()
        if target and not messagebox.askyesno(
            "Organize this folder?",
            f"ARISE-I will sort:\n\n{Path(target).expanduser()}\n\n"
            "Nothing is deleted. You can undo afterwards.",
            parent=self,
        ):
            return
        self._run_organization(dry_run=False)

    def _run_organization(self, dry_run: bool):
        target = self._target_var.get().strip()
        if not target:
            messagebox.showerror("No folder", "Please select a folder."); return
        tp = Path(target).expanduser()
        if not tp.exists():
            messagebox.showerror("Not found", f"Folder not found:\n{target}"); return
        if not tp.is_dir():
            messagebox.showerror("Not a folder", f"Not a folder:\n{target}"); return
        if tp == Path(tp.anchor) or tp == Path.home().resolve():
            messagebox.showerror("Safety",
                "Choose a subfolder (Downloads, Desktop, etc.), not the whole drive.",
                parent=self); return

        self._set_buttons_enabled(False)
        self._set_status("Previewing…" if dry_run else "Organizing…")
        self._switch_tab("log")
        self._log("🔎  Previewing changes" if dry_run else "✨  Organizing files", "hdr")

        def _worker():
            try:
                stats = organize_folder(target, dry_run=dry_run,
                    categories=load_categories(None),
                    log_callback=self._enqueue_log,
                    learning_store=self._learning_store)
                action = "would be organized" if dry_run else "organized"
                self._log_queue.put(f"✓  Done! {stats.total_files()} file(s) {action}")
                if stats.skipped: self._log_queue.put(f"   {stats.skipped} skipped")
                if stats.errors:  self._log_queue.put(f"   {stats.errors} error(s)")
                self._log_queue.put(("__STATS__", stats, dry_run))
            except Exception as e:
                self._log_queue.put(f"✗  Error: {e}")
            finally:
                self._log_queue.put("__DONE__")

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_auto_sort(self):
        if self._auto_sort_var.get():
            if not WATCHDOG_AVAILABLE:
                self._log("⚠  Auto-sort needs: pip install watchdog", "warn")
                self._auto_sort_var.set(False); return
            self._start_watch()
        else:
            self._stop_watch()

    def _start_watch(self):
        if not WATCHDOG_AVAILABLE:
            messagebox.showerror("watchdog missing",
                "Run: pip install watchdog"); return
        target = self._target_var.get().strip()
        if not target or not Path(target).expanduser().exists():
            messagebox.showerror("Not found", f"Folder not found:\n{target}"); return

        self._watching = True
        self._watch_stop.clear()
        self._sort_btn.configure(state="disabled")
        self._set_status(f"Auto-sorting {Path(target).name}…")
        self._log("🔄  Auto-sort enabled", "hdr")
        self._start_pulse()

        debounce = max(0.1, min(300.0, self._debounce_var.get()))
        cats     = load_categories(None)

        def _worker():
            from watchdog.observers import Observer as _Obs
            from file_watcher import AriseIEventHandler as _H

            class _GUIHandler(_H):
                def _run_organizer(inner):
                    self._log_queue.put("📁  New files — organizing…")
                    s = organize_folder(str(inner.target_dir),
                        dry_run=inner.dry_run,
                        categories=load_categories(None),
                        log_callback=self._enqueue_log)
                    self._log_queue.put(f"✓  {s.total_files()} file(s) organized")

            handler  = _GUIHandler(target_dir=Path(target).expanduser().resolve(),
                                   debounce=debounce, dry_run=False, categories=cats)
            observer = _Obs()
            observer.schedule(handler, str(handler.target_dir), recursive=False)
            observer.start()
            while not self._watch_stop.is_set():
                time.sleep(0.5)
            try: handler._timer.cancel()
            except Exception: pass
            observer.stop()
            if observer.is_alive(): observer.join(timeout=5)
            self._log_queue.put("🛑  Auto-sort stopped")
            self._log_queue.put("__WATCH_DONE__")

        self._watch_thread = threading.Thread(target=_worker, daemon=True)
        self._watch_thread.start()

    def _stop_watch(self):
        self._watch_stop.set()
        self._watching = False
        self._sort_btn.configure(state="normal")
        self._set_status("Ready to organize")
        self._stop_pulse()

    def _undo(self):
        target = self._target_var.get().strip()
        if not target:
            messagebox.showerror("No folder", "Please select a folder."); return
        tp = Path(target).expanduser()
        if not tp.exists():
            messagebox.showerror("Not found", f"Folder not found:\n{target}"); return

        self._set_buttons_enabled(False)
        self._set_status("Undoing last run…")
        self._log("↩  Undoing last organization", "hdr")

        def _worker():
            try:
                import io, contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    undo_last_run(target)
                for line in buf.getvalue().splitlines():
                    if line.strip():
                        self._log_queue.put(line.strip())
                self._refresh_history()
            except Exception as e:
                self._log_queue.put(f"✗  Error: {e}")
            finally:
                self._log_queue.put("__DONE__")

        threading.Thread(target=_worker, daemon=True).start()

    def _set_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self._sort_btn.configure(state=state)
        self._preview_btn.configure(state=state)
        self._undo_btn.configure(state=state)
        if not self._watching:
            self._auto_check.configure(state=state)

    def _setup_shortcuts(self):
        for key in ("<Control-o>","<Command-o>"):   self.bind(key, lambda e: self._sort_now())
        for key in ("<Control-z>","<Command-z>"):   self.bind(key, lambda e: self._undo())
        for key in ("<Control-q>","<Command-q>"):   self.bind(key, lambda e: self.quit())
        for key in ("<Control-b>","<Command-b>"):   self.bind(key, lambda e: self._browse())

    def _on_close(self):
        if self._watching:
            self._stop_watch()
        if self._health_monitor is not None:
            self._health_monitor.stop()
        prefs = load_prefs()
        prefs["last_folder"] = self._target_var.get()
        prefs["debounce"]    = self._debounce_var.get()
        prefs["theme"]       = self._theme
        save_prefs(prefs)
        self.destroy()


def main():
    app = AriseIApp()
    app.mainloop()

if __name__ == "__main__":
    main()
