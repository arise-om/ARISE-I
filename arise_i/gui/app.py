"""ARISE-I v2.1.0 — GUI (AI-Powered Dashboard)"""

import math
import os
import queue
import re
import shutil
import subprocess
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

from arise_i import __version__
from arise_i.constants import REVIEW_FOLDER
from arise_i.core.classifier import get_classifier
from arise_i.core.health import HealthMonitor
from arise_i.core.learning import LearningStore
from arise_i.core.organizer import (
    Stats,
    _load_manifest,
    get_unique_destination,
    is_protected_dir,
    load_categories,
    organize_folder,
    record_moves,
    skip_reason,
    undo_last_run,
)
from arise_i.core.prefs import load_prefs, save_prefs, set_pref
from arise_i.gui import onboarding
from arise_i.gui.theme import RECOLOR_KEYS as _RECOLOR_KEYS
from arise_i.gui.theme import THEMES as _THEMES
from arise_i.gui.theme import ON_ACCENT, ON_ACCENT_DISABLED, Animator, ToggleSwitch
from arise_i.gui.theme import ease_in_out, mix, scaled, to_hex
from arise_i.gui.theme import font as _font

from arise_i.core.plugins import load_plugins
from arise_i.core.watcher import WATCHDOG_AVAILABLE

APP_VERSION = __version__

# Live palette — updated in place on a theme switch, so every lookup made at
# event time (hover, redraws, new cards) sees the current theme.
_P: dict[str, str] = dict(_THEMES["light"])

_COLOR_OPTIONS = ("bg", "fg", "activebackground", "activeforeground",
                  "highlightbackground", "highlightcolor", "insertbackground",
                  "disabledforeground", "selectbackground", "selectforeground",
                  "readonlybackground")

_MOD = "Command" if sys.platform == "darwin" else "Control"
_MOD_LABEL = "Cmd" if sys.platform == "darwin" else "Ctrl"

# (id, label, icon, subtitle)
_PAGES = [
    ("log",     "Activity",     "☰",  "Live feed of everything ARISE-I does"),
    ("history", "History",      "🕘", "Past runs in this folder, newest first"),
    ("stats",   "Last Run",     "📊", "Results of the most recent preview or organize"),
    ("review",  "Review Queue", "⚑",  "Low-confidence files waiting for your decision"),
]

_CATEGORY_ICONS = {
    "Images": "🖼", "Documents": "📄", "PDFs": "📕", "Videos": "🎬",
    "Music": "🎵", "Audio": "🎵", "Archives": "🗜", "Code": "💻",
    "Installers": "📦", "Spreadsheets": "📊", "Presentations": "📽",
    "Fonts": "🔤", "Ebooks": "📚", "Others": "📁", REVIEW_FOLDER: "⚑",
}

_SHORTCUTS = [
    (f"{_MOD_LABEL}+O", "Organize now"),
    (f"{_MOD_LABEL}+P", "Preview changes"),
    (f"{_MOD_LABEL}+Z", "Undo last run"),
    (f"{_MOD_LABEL}+B", "Choose folder"),
    (f"{_MOD_LABEL}+E", "Open folder in file manager"),
    (f"{_MOD_LABEL}+1…4", "Switch page"),
    (f"{_MOD_LABEL}+D", "Toggle dark mode"),
    (f"{_MOD_LABEL}+Q", "Quit"),
]

_GEOMETRY_RE = re.compile(r"^\d+x\d+([+-]-?\d+[+-]-?\d+)?$")


def _cat_icon(cat: str) -> str:
    return _CATEGORY_ICONS.get(cat, "📁")


def _relative_time(ts: str) -> str:
    try:
        then = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return ts
    secs = (datetime.now() - then).total_seconds()
    if secs < 60:        return "Just now"
    if secs < 3600:      return f"{int(secs // 60)} min ago"
    if secs < 86400:     return f"{int(secs // 3600)} h ago"
    if secs < 7 * 86400: return f"{int(secs // 86400)} d ago"
    return then.strftime("%d %b %Y")


class AriseIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ARISE-I")
        prefs = load_prefs()
        geom = str(prefs.get("window_geometry") or "")
        self.geometry(geom if _GEOMETRY_RE.match(geom) else "1080x700")
        self.minsize(900, 600)

        # Load theme before building UI
        theme = prefs.get("theme", "light")
        self._theme = theme if theme in _THEMES else "light"
        self._apply_theme(self._theme, init=True)
        self._animations = bool(prefs.get("animations", True))
        self._anim = Animator(self, enabled=lambda: self._animations)
        self.configure(bg=_P["BG"])
        self.resizable(True, True)
        self._set_icon()

        # State
        self._watch_stop   = threading.Event()
        self._log_queue    = queue.Queue()
        self._watching     = False
        self._pulse_active = False
        self._pulse_id     = None
        self._busy         = False
        self._closing      = False
        self._hint_token   = 0
        self._loose_count  = 0    # from the last folder scan, for run progress
        self._run_label    = ""
        self._run_done     = 0
        self._hint_job     = None
        self._prog_job     = None
        self._prog_phase   = 0.0
        self._toast_widget = None
        self._toast_job    = None
        self._indicator_y  = None
        self._theme_hooks: list[tuple[tk.Misc, object]] = []
        self._scroll_canvases: set = set()

        # Prefs
        self._target_var   = tk.StringVar(value=prefs.get("last_folder", str(Path.home()/"Downloads")))
        self._debounce_var = tk.DoubleVar(value=prefs.get("debounce", 2.0))
        self._auto_sort_var= tk.BooleanVar(value=False)
        self._dark_var     = tk.BooleanVar(value=self._theme == "dark")
        self._anim_var     = tk.BooleanVar(value=self._animations)

        # AI subsystems (optional — graceful degradation)
        self._learning_store = None
        self._health_monitor = None
        self._init_ai_subsystems()

        # User classifier plugins (~/.arise-i/plugins) — same as the CLI
        try:
            self._plugins = load_plugins()
        except Exception:
            self._plugins = []

        # Keep the health monitor pointed at whatever folder is selected
        self._target_var.trace_add("write", lambda *_: self._on_target_changed())

        self._style = ttk.Style(self)
        self._style_ttk()
        self._build_menu()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_shortcuts()
        self.bind_all("<MouseWheel>", self._on_wheel, add="+")
        self.bind_all("<Button-4>", self._on_wheel, add="+")
        self.bind_all("<Button-5>", self._on_wheel, add="+")

        self._fade_in()
        self.after(200, self._run_onboarding)

        self._log("Welcome to ARISE-I", "hdr")
        self._log("Your personal AI-powered file organizer — v" + APP_VERSION, "dim")
        if not WATCHDOG_AVAILABLE:
            self._log("⚠  Auto-sort needs: pip install watchdog", "warn")
        self._refresh_folder_hint()
        self._poll_log_queue()

    def _init_ai_subsystems(self) -> None:
        try:
            self._learning_store = LearningStore(on_retrain=self._on_model_retrained)
        except Exception:
            self._learning_store = None
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
        # The shared classifier reloads model.pkl on its next run
        self._log_queue.put("🧠  ML model retrained — classifier updated.")

    def _on_target_changed(self) -> None:
        if self._health_monitor is not None:
            raw = self._target_var.get().strip()
            self._health_monitor.set_target_dir(Path(raw).expanduser() if raw else None)
        if self._hint_job:
            self.after_cancel(self._hint_job)
        self._hint_job = self.after(250, self._refresh_folder_hint)

    def _current_target(self) -> Path | None:
        """The selected folder as an absolute path, or None if the field is empty.

        ``Path("")`` resolves to the working directory, which would make
        History and Review show some unrelated folder's data.
        """
        raw = self._target_var.get().strip()
        return Path(raw).expanduser().resolve() if raw else None

    def _set_icon(self):
        try:
            icon = tk.PhotoImage(width=32, height=32)
            for y in range(32):
                for x in range(32):
                    if (8<=y<=24 and 12<=x<=20) or \
                       (8<=y<=24 and 8<=x<=12 and (x-8)==(y-8)) or \
                       (8<=y<=24 and 20<=x<=24 and (24-x)==(y-8)):
                        icon.put(_THEMES["light"]["ACCENT_FILL"], (x, y))
                    else:
                        icon.put("#ffffff", (x, y))
            self.iconphoto(True, icon)
        except Exception:
            pass

    # ------------------------------------------------------------------ Theme

    def _apply_theme(self, name: str, init: bool = False) -> None:
        """Switch the live palette to 'dark' or 'light' and re-draw."""
        old = dict(_P)
        new = _THEMES.get(name, _THEMES["light"])
        _P.clear()
        _P.update(new)
        self._theme = name
        if not init:
            set_pref("theme", name)
            self._recolor_widgets(old, new)

    def _recolor_widgets(self, old: dict[str, str], new: dict[str, str]) -> None:
        """Swap every palette colour on every widget from *old* to *new*.

        Each widget keeps its role (a card stays SURFACE, dim text stays
        FG_DIM) because colours are mapped key-for-key, so text never ends
        up dark-on-dark the way a blanket bg=BG repaint left it.
        """
        mapping = {old[k].lower(): new[k] for k in _RECOLOR_KEYS}

        def _visit(widget):
            for opt in _COLOR_OPTIONS:
                try:
                    current = str(widget.cget(opt)).lower()
                except tk.TclError:
                    continue
                if current in mapping:
                    try:
                        widget.configure(**{opt: mapping[current]})
                    except tk.TclError:
                        pass
            for child in widget.winfo_children():
                _visit(child)

        _visit(self)
        self._tag_log_colors()
        self._style_ttk()
        self._run_theme_hooks()
        # Combobox drop-down lists only read their colours when created
        if self._active_tab.get() == "review":
            self._refresh_review()

    def _on_theme(self, owner: tk.Misc, fn) -> None:
        """Re-run *fn* after every theme switch while *owner* exists."""
        self._theme_hooks.append((owner, fn))

    def _run_theme_hooks(self) -> None:
        alive = []
        for owner, fn in self._theme_hooks:
            try:
                if owner.winfo_exists():
                    fn()
                    alive.append((owner, fn))
            except tk.TclError:
                pass
        self._theme_hooks = alive

    def _toggle_theme(self) -> None:
        new = "dark" if self._theme == "light" else "light"

        def _swap():
            self._apply_theme(new)
            self._dark_var.set(new == "dark")
            self._theme_btn.configure(text="🌙" if new == "dark" else "☀️")
            self._anim.run("win-alpha", 200, lambda t: self._set_alpha(0.55 + 0.45 * t))

        # Dip the window, swap colours while it's dim, then bring it back
        self._anim.run("win-alpha", 110, lambda t: self._set_alpha(1 - 0.45 * t),
                       done=_swap, ease=ease_in_out)

    def _toggle_animations(self) -> None:
        self._animations = bool(self._anim_var.get())
        set_pref("animations", self._animations)
        self._toast("Animations on" if self._animations else "Animations off — reduced motion")

    def _set_alpha(self, value: float) -> None:
        try:
            self.attributes("-alpha", max(0.0, min(1.0, value)))
        except tk.TclError:
            pass

    def _fade_in(self) -> None:
        self._set_alpha(0.0)
        self._anim.run("win-alpha", 280, self._set_alpha)

    def _style_ttk(self) -> None:
        s = self._style
        try:
            s.theme_use("clam")
        except tk.TclError:
            return
        thumb = mix(_P["BORDER"], _P["FG_DIM"], 0.35)
        s.layout("Arise.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        s.configure("Arise.Vertical.TScrollbar", background=thumb,
                    troughcolor=_P["SURFACE"], bordercolor=_P["SURFACE"],
                    lightcolor=thumb, darkcolor=thumb, arrowsize=9, gripcount=0)
        s.map("Arise.Vertical.TScrollbar",
              background=[("active", _P["FG_DIM"])],
              lightcolor=[("active", _P["FG_DIM"])], darkcolor=[("active", _P["FG_DIM"])])
        s.configure("TCombobox", fieldbackground=_P["SURFACE"], background=_P["SURFACE"],
                    foreground=_P["FG"], arrowcolor=_P["FG_DIM"], bordercolor=_P["BORDER"],
                    lightcolor=_P["SURFACE"], darkcolor=_P["SURFACE"], padding=4)
        s.map("TCombobox",
              fieldbackground=[("readonly", _P["SURFACE"])],
              foreground=[("readonly", _P["FG"])],
              selectbackground=[("readonly", _P["SURFACE"])],
              selectforeground=[("readonly", _P["FG"])],
              bordercolor=[("focus", _P["ACCENT"]), ("hover", _P["FG_DIM"])])
        self.option_add("*TCombobox*Listbox.background", _P["SURFACE"])
        self.option_add("*TCombobox*Listbox.foreground", _P["FG"])
        self.option_add("*TCombobox*Listbox.selectBackground", _P["ACCENT_FILL"])
        self.option_add("*TCombobox*Listbox.selectForeground", ON_ACCENT)
        self.option_add("*TCombobox*Listbox.font", _font(10))

    # ------------------------------------------------------------------ Micro-interactions

    def _tween(self, widget: tk.Misc, opt: str, target: str, ms: int = 140) -> None:
        try:
            start = to_hex(widget, str(widget.cget(opt)))
        except tk.TclError:
            return
        self._anim.run(f"{widget}:{opt}", ms,
                       lambda t: widget.configure(**{opt: mix(start, target, t)}))

    def _hover(self, widget: tk.Misc, base: str, hover: str,
               fg: str | None = None, fg_hover: str | None = None) -> None:
        """Smoothly tint *widget* between palette keys on mouse over."""
        def _enter(_e):
            if str(widget.cget("state")) == "disabled":
                return
            self._tween(widget, "bg", _P[hover])
            if fg_hover: widget.configure(fg=_P.get(fg_hover, fg_hover))

        def _leave(_e):
            if str(widget.cget("state")) == "disabled":
                return
            self._tween(widget, "bg", _P[base])
            if fg: widget.configure(fg=_P.get(fg, fg))

        widget.bind("<Enter>", _enter, add="+")
        widget.bind("<Leave>", _leave, add="+")

    def _card_hover(self, card: tk.Frame) -> None:
        """Highlight a card's border while the pointer is anywhere inside it."""
        def _enter(_e):
            card.configure(highlightbackground=_P["ACCENT"])

        def _leave(e):
            under = self.winfo_containing(e.x_root, e.y_root)
            if under is not None and str(under).startswith(str(card)):
                return
            card.configure(highlightbackground=_P["BORDER"])

        card.bind("<Enter>", _enter, add="+")
        card.bind("<Leave>", _leave, add="+")

    def _tooltip(self, widget: tk.Misc, text: str) -> None:
        state: dict = {"job": None, "tip": None}

        def _show():
            tip = tk.Toplevel(self)
            tip.wm_overrideredirect(True)
            try: tip.attributes("-topmost", True)
            except tk.TclError: pass
            tk.Label(tip, text=text, font=_font(9), fg=_P["BG"], bg=_P["FG"],
                     padx=8, pady=4).pack()
            tip.update_idletasks()
            x = widget.winfo_rootx() + widget.winfo_width() // 2 - tip.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() + 6
            tip.geometry(f"+{x}+{y}")
            state["tip"] = tip

        def _hide(_e=None):
            if state["job"]:
                self.after_cancel(state["job"]); state["job"] = None
            if state["tip"] is not None:
                state["tip"].destroy(); state["tip"] = None

        def _schedule(_e):
            _hide()
            state["job"] = self.after(550, _show)

        widget.bind("<Enter>", _schedule, add="+")
        widget.bind("<Leave>", _hide, add="+")
        widget.bind("<ButtonPress>", _hide, add="+")

    def _button(self, parent, text, command, kind="secondary", bg_key="SURFACE",
                size=10, padx=14, pady=7) -> tk.Button:
        """Primary (filled accent), secondary (outlined) or ghost (text) button."""
        if kind == "primary":
            b = tk.Button(parent, text=text, command=command, font=_font(size, "bold"),
                          fg=ON_ACCENT, bg=_P["ACCENT_FILL"], activebackground=_P["ACCENT_D"],
                          activeforeground=ON_ACCENT, disabledforeground=ON_ACCENT_DISABLED,
                          relief="flat", bd=0, padx=padx, pady=pady, cursor="hand2",
                          highlightthickness=2, highlightbackground=_P["ACCENT_FILL"],
                          highlightcolor=_P["FG"])
            self._hover(b, "ACCENT_FILL", "ACCENT_D")
        elif kind == "secondary":
            b = tk.Button(parent, text=text, command=command, font=_font(size),
                          fg=_P["FG"], bg=_P["SURFACE"], activebackground=_P["HOVER"],
                          activeforeground=_P["FG"], disabledforeground=_P["FG_DIM"],
                          relief="flat", bd=0, padx=padx, pady=pady, cursor="hand2",
                          highlightthickness=1, highlightbackground=_P["BORDER"],
                          highlightcolor=_P["ACCENT"])
            self._hover(b, "SURFACE", "HOVER")
        else:
            b = tk.Button(parent, text=text, command=command, font=_font(size),
                          fg=_P["ACCENT"], bg=_P[bg_key], activebackground=_P["HOVER"],
                          activeforeground=_P["ACCENT"], disabledforeground=_P["FG_DIM"],
                          relief="flat", bd=0, padx=padx, pady=pady, cursor="hand2",
                          highlightthickness=1, highlightbackground=_P[bg_key],
                          highlightcolor=_P["ACCENT"])
            self._hover(b, bg_key, "HOVER")
        return b

    def _scroll_area(self, parent) -> tuple[tk.Canvas, tk.Frame]:
        """A vertically scrollable frame (canvas + slim scrollbar + wheel)."""
        canvas = tk.Canvas(parent, bg=_P["BG"], highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                            style="Arise.Vertical.TScrollbar")
        def _set(first, last):
            # Only show the scrollbar when there is something to scroll
            if float(first) <= 0.0 and float(last) >= 1.0:
                bar.pack_forget()
            elif not bar.winfo_ismapped():
                bar.pack(side="right", fill="y", padx=(6, 0), before=canvas)
            bar.set(first, last)

        canvas.configure(yscrollcommand=_set)
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=_P["BG"])
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        self._scroll_canvases.add(canvas)
        return canvas, inner

    def _on_wheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget in self._scroll_canvases:
                if widget.yview() == (0.0, 1.0):
                    return
                if getattr(event, "num", None) == 4:   step = -1
                elif getattr(event, "num", None) == 5: step = 1
                elif sys.platform == "darwin":         step = -event.delta
                else:                                  step = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
                widget.yview_scroll(step * 2, "units")
                return
            widget = widget.master

    def _empty_state(self, parent, icon: str, title: str, subtitle: str,
                     action: tuple[str, object] | None = None) -> None:
        box = tk.Frame(parent, bg=_P["BG"])
        box.pack(expand=True, pady=60)
        tk.Label(box, text=icon, font=_font(34), fg=_P["FG_DIM"], bg=_P["BG"]).pack()
        tk.Label(box, text=title, font=_font(14, "bold"), fg=_P["FG"], bg=_P["BG"]).pack(pady=(8, 2))
        tk.Label(box, text=subtitle, font=_font(10), fg=_P["FG_DIM"], bg=_P["BG"],
                 wraplength=scaled(self, 420), justify="center").pack()
        if action:
            self._button(box, action[0], action[1], kind="primary").pack(pady=(16, 0))

    # ------------------------------------------------------------------ Toast

    def _toast(self, text: str, kind: str = "info") -> None:
        """Slide a small notification up from the bottom-right corner."""
        if self._closing:
            return
        if self._toast_job:
            self.after_cancel(self._toast_job); self._toast_job = None
        if self._toast_widget is not None:
            self._toast_widget.destroy()
        dot = {"ok": "GREEN", "warn": "YELLOW", "err": "RED"}.get(kind, "ACCENT")
        toast = tk.Frame(self, bg=_P["FG"], padx=14, pady=10)
        tk.Label(toast, text="●", font=_font(10), fg=_P[dot], bg=_P["FG"]).pack(side="left", padx=(0, 8))
        tk.Label(toast, text=text, font=_font(10), fg=_P["BG"], bg=_P["FG"],
                 wraplength=scaled(self, 380), justify="left").pack(side="left")
        self._toast_widget = toast
        rest, hidden = -48, 60
        toast.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=hidden)
        toast.lift()
        self._anim.run("toast", 260, lambda t: toast.place_configure(y=int(hidden + (rest - hidden) * t)))

        def _dismiss():
            self._toast_job = None
            self._anim.run("toast", 220,
                           lambda t: toast.place_configure(y=int(rest + (hidden - rest) * t)),
                           done=toast.destroy, ease=ease_in_out)
        self._toast_job = self.after(3200, _dismiss)

    # ------------------------------------------------------------------ Menu

    def _build_menu(self):
        bar = tk.Menu(self)
        m_file = tk.Menu(bar, tearoff=0)
        m_file.add_command(label="Choose Folder…", accelerator=f"{_MOD_LABEL}+B", command=self._browse)
        m_file.add_command(label="Open Folder", accelerator=f"{_MOD_LABEL}+E", command=self._open_folder)
        m_file.add_separator()
        m_file.add_command(label="Preview Changes", accelerator=f"{_MOD_LABEL}+P", command=self._preview)
        m_file.add_command(label="Organize Now", accelerator=f"{_MOD_LABEL}+O", command=self._sort_now)
        m_file.add_command(label="Undo Last Run", accelerator=f"{_MOD_LABEL}+Z", command=self._undo)
        m_file.add_separator()
        m_file.add_command(label="Quit", accelerator=f"{_MOD_LABEL}+Q", command=self._on_close)
        bar.add_cascade(label="File", menu=m_file)

        m_view = tk.Menu(bar, tearoff=0)
        for i, (page_id, label, _icon, _sub) in enumerate(_PAGES, start=1):
            m_view.add_command(label=label, accelerator=f"{_MOD_LABEL}+{i}",
                               command=lambda p=page_id: self._switch_tab(p))
        m_view.add_separator()
        m_view.add_checkbutton(label="Dark Mode", accelerator=f"{_MOD_LABEL}+D",
                               variable=self._dark_var, command=self._toggle_theme)
        m_view.add_checkbutton(label="Animations", variable=self._anim_var,
                               command=self._toggle_animations)
        bar.add_cascade(label="View", menu=m_view)

        m_help = tk.Menu(bar, tearoff=0)
        m_help.add_command(label="Keyboard Shortcuts", accelerator="F1", command=self._show_shortcuts)
        m_help.add_command(label="About ARISE-I", command=self._show_about)
        bar.add_cascade(label="Help", menu=m_help)

        self.config(menu=bar)
        self._menu_file = m_file

    def _show_shortcuts(self):
        """Small themed dialog; keys and actions line up in a real grid."""
        win = tk.Toplevel(self, bg=_P["SURFACE"], padx=24, pady=20)
        win.title("Keyboard shortcuts")
        win.resizable(False, False)
        win.transient(self)
        tk.Label(win, text="Keyboard shortcuts", font=_font(13, "bold"), fg=_P["FG"],
                 bg=_P["SURFACE"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        for r, (keys, action) in enumerate(_SHORTCUTS + [("F1", "Show this list")], start=1):
            tk.Label(win, text=keys, font=_font(10, "bold"), fg=_P["FG"], bg=_P["BG"],
                     padx=8, pady=2).grid(row=r, column=0, sticky="w", pady=3)
            tk.Label(win, text=action, font=_font(10), fg=_P["FG_DIM"],
                     bg=_P["SURFACE"]).grid(row=r, column=1, sticky="w", padx=(16, 0))
        close = self._button(win, "Close", win.destroy, kind="primary", padx=18, pady=6)
        close.grid(row=len(_SHORTCUTS) + 2, column=0, columnspan=2, sticky="e", pady=(16, 0))
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Return>", lambda e: win.destroy())
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - win.winfo_reqheight()) // 3
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        close.focus_set()

    def _show_about(self):
        messagebox.showinfo(
            "About ARISE-I",
            f"ARISE-I v{APP_VERSION}\nAI-powered file organizer\n\n"
            "100% local — your files never leave this computer.\nIronlabs.tech",
            parent=self)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        P = _P
        # ── Sidebar ──────────────────────────────────────────────────────────
        side = tk.Frame(self, bg=P["SIDEBAR"], width=scaled(self, 250))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(self, bg=P["BORDER"], width=1).pack(side="left", fill="y")

        brand = tk.Frame(side, bg=P["SIDEBAR"], padx=18, pady=20)
        brand.pack(fill="x")
        m = scaled(self, 38)
        mark = tk.Canvas(brand, width=m, height=m, bg=P["SIDEBAR"], highlightthickness=0)
        mark.pack(side="left")

        def _draw_mark():
            mark.delete("all")
            mark.create_oval(1, 1, m - 1, m - 1, fill=_P["ACCENT_FILL"], width=0)
            mark.create_text(m / 2, m / 2, text="A", fill=ON_ACCENT, font=_font(15, "bold"))
        _draw_mark()
        self._on_theme(mark, _draw_mark)

        names = tk.Frame(brand, bg=P["SIDEBAR"])
        names.pack(side="left", padx=(10, 0))
        tk.Label(names, text="ARISE-I", font=_font(15, "bold"),
                 fg=P["FG"], bg=P["SIDEBAR"]).pack(anchor="w")
        tk.Label(names, text="AI file organizer", font=_font(9),
                 fg=P["FG_DIM"], bg=P["SIDEBAR"]).pack(anchor="w")

        self._theme_btn = tk.Button(
            brand, text="🌙" if self._theme == "dark" else "☀️", font=_font(12),
            fg=P["FG_DIM"], bg=P["SIDEBAR"], activebackground=P["HOVER"],
            activeforeground=P["FG"], relief="flat", bd=0, padx=6, pady=2,
            cursor="hand2", command=self._toggle_theme,
            highlightthickness=1, highlightbackground=P["SIDEBAR"], highlightcolor=P["ACCENT"])
        self._theme_btn.pack(side="right")
        self._hover(self._theme_btn, "SIDEBAR", "HOVER")
        self._tooltip(self._theme_btn, f"Dark mode  ({_MOD_LABEL}+D)")

        tk.Label(side, text="MENU", font=_font(8, "bold"), fg=P["FG_DIM"],
                 bg=P["SIDEBAR"], padx=24).pack(anchor="w", pady=(4, 6))

        nav = tk.Frame(side, bg=P["SIDEBAR"], padx=12)
        nav.pack(fill="x")
        self._nav_items: dict[str, tuple] = {}
        for page_id, label, icon, _sub in _PAGES:
            item = tk.Frame(nav, bg=P["SIDEBAR"], cursor="hand2")
            item.pack(fill="x", pady=1)
            ic = tk.Label(item, text=icon, font=_font(11), width=2,
                          fg=P["FG_DIM"], bg=P["SIDEBAR"], cursor="hand2")
            ic.pack(side="left", padx=(12, 8), pady=9)
            lb = tk.Label(item, text=label, font=_font(10), fg=P["FG"],
                          bg=P["SIDEBAR"], cursor="hand2")
            lb.pack(side="left")
            badge = tk.Label(item, text="", font=_font(8, "bold"), fg=ON_ACCENT,
                             bg=P["ACCENT_FILL"], padx=7, pady=0, cursor="hand2")
            parts = (item, ic, lb, badge)
            for w in parts:
                w.bind("<Button-1>", lambda e, p=page_id: self._switch_tab(p))
                w.bind("<Enter>", lambda e, p=page_id: self._nav_hover(p, True))
                w.bind("<Leave>", lambda e, p=page_id: self._nav_hover(p, False))
            self._nav_items[page_id] = parts
        self._nav_indicator = tk.Frame(nav, bg=P["ACCENT"], width=3)
        nav.bind("<Configure>", lambda e: self._place_indicator(animate=False))

        # Version footer + Auto-sort card (bottom of sidebar)
        tk.Label(side, text=f"v{APP_VERSION}  ·  100% local  ·  Ironlabs.tech",
                 font=_font(8), fg=P["FG_DIM"], bg=P["SIDEBAR"]).pack(side="bottom", pady=(8, 14))

        auto_card = tk.Frame(side, bg=P["SURFACE"], padx=14, pady=12,
                             highlightthickness=1, highlightbackground=P["BORDER"])
        auto_card.pack(side="bottom", fill="x", padx=12)
        auto_top = tk.Frame(auto_card, bg=P["SURFACE"])
        auto_top.pack(fill="x")
        tk.Label(auto_top, text="Auto-Sort", font=_font(10, "bold"),
                 fg=P["FG"], bg=P["SURFACE"]).pack(side="left")
        self._auto_check = ToggleSwitch(auto_top, self._auto_sort_var,
                                        self._toggle_auto_sort, _P, self._anim)
        self._auto_check.pack(side="right")
        self._on_theme(self._auto_check.canvas, self._auto_check.redraw)

        pulse_row = tk.Frame(auto_card, bg=P["SURFACE"])
        pulse_row.pack(fill="x", pady=(6, 0))
        d = scaled(self, 14)
        self._pulse_dot = tk.Canvas(pulse_row, width=d, height=d, bg=P["SURFACE"],
                                    highlightthickness=0)
        self._pulse_dot.pack(side="left", padx=(0, 6))
        self._pulse_label = tk.Label(pulse_row, text="Off", font=_font(9),
                                     fg=P["FG_DIM"], bg=P["SURFACE"], anchor="w")
        self._pulse_label.pack(side="left", fill="x")
        tk.Label(auto_card, text="Sorts new files the moment they land",
                 font=_font(8), fg=P["FG_DIM"], bg=P["SURFACE"], wraplength=scaled(self, 190),
                 justify="left").pack(anchor="w", pady=(4, 0))
        self._draw_pulse_dot(0.0)
        self._on_theme(self._pulse_dot, lambda: self._draw_pulse_dot(0.0))

        # ── Main area ───────────────────────────────────────────────────────
        main = tk.Frame(self, bg=P["BG"])
        main.pack(side="left", fill="both", expand=True)

        header = tk.Frame(main, bg=P["SURFACE"], padx=26, pady=14)
        header.pack(fill="x")
        titles = tk.Frame(header, bg=P["SURFACE"])
        titles.pack(side="left")
        self._page_title = tk.Label(titles, text="", font=_font(17, "bold"),
                                    fg=P["FG"], bg=P["SURFACE"])
        self._page_title.pack(anchor="w")
        self._page_sub = tk.Label(titles, text="", font=_font(9),
                                  fg=P["FG_DIM"], bg=P["SURFACE"])
        self._page_sub.pack(anchor="w")
        self._header_actions = tk.Frame(header, bg=P["SURFACE"])
        self._header_actions.pack(side="right")
        tk.Frame(main, bg=P["BORDER"], height=1).pack(fill="x")

        # Indeterminate progress strip — animates while a run is in flight
        self._progress = tk.Canvas(main, height=scaled(self, 3), bg=P["BG"],
                                   highlightthickness=0, bd=0)
        self._progress.pack(fill="x")

        # Toolbar: folder field on top, the actions that act on it just below
        folder_row = tk.Frame(main, bg=P["BG"], padx=26)
        folder_row.pack(fill="x", pady=(14, 0))
        toolbar = tk.Frame(main, bg=P["BG"], padx=26)
        toolbar.pack(fill="x", pady=(10, 0))

        self._undo_btn = self._button(toolbar, "↩  Undo", self._undo, kind="ghost", bg_key="BG")
        self._undo_btn.pack(side="right")
        self._tooltip(self._undo_btn, f"Undo the last run  ({_MOD_LABEL}+Z)")
        self._sort_btn = self._button(toolbar, "✨  Organize Now", self._sort_now,
                                      kind="primary", size=10, padx=18, pady=8)
        self._sort_btn.pack(side="right", padx=(8, 4))
        self._tooltip(self._sort_btn, f"Sort every file into folders  ({_MOD_LABEL}+O)")
        self._preview_btn = self._button(toolbar, "🔎  Preview", self._preview,
                                         kind="secondary", padx=14, pady=7)
        self._preview_btn.pack(side="right", padx=(12, 0))
        self._tooltip(self._preview_btn, f"See what would move — nothing is touched  ({_MOD_LABEL}+P)")

        self._folder_hint = tk.Label(toolbar, text="", font=_font(9), fg=P["FG_DIM"],
                                     bg=P["BG"], anchor="w")
        self._folder_hint.pack(side="left", fill="x", expand=True, padx=(2, 0))

        self._folder_box = tk.Frame(folder_row, bg=P["SURFACE"], highlightthickness=1,
                                    highlightbackground=P["BORDER"])
        self._folder_box.pack(fill="x")
        tk.Label(self._folder_box, text="📁", font=_font(11), fg=P["FG_DIM"],
                 bg=P["SURFACE"]).pack(side="left", padx=(10, 4))
        self._path_entry = tk.Entry(self._folder_box, textvariable=self._target_var,
                                    font=_font(10), bg=P["SURFACE"], fg=P["FG"],
                                    insertbackground=P["ACCENT"], relief="flat",
                                    bd=0, highlightthickness=0,
                                    readonlybackground=P["SURFACE"],
                                    selectbackground=P["ACCENT_SOFT"],
                                    selectforeground=P["FG"])
        self._path_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self._path_entry.bind("<FocusIn>", lambda e: self._folder_box.configure(
            highlightbackground=_P["ACCENT"]))
        self._path_entry.bind("<FocusOut>", lambda e: self._commit_typed_folder())
        self._path_entry.bind("<Return>", lambda e: self.focus_set())
        open_btn = self._button(self._folder_box, "↗", self._open_folder, kind="ghost",
                                padx=8, pady=4)
        open_btn.pack(side="right", padx=(0, 4))
        self._tooltip(open_btn, f"Open in file manager  ({_MOD_LABEL}+E)")
        browse_btn = self._button(self._folder_box, "Browse…", self._browse, kind="ghost",
                                  padx=10, pady=4)
        browse_btn.pack(side="right")
        self._tooltip(browse_btn, f"Choose a folder  ({_MOD_LABEL}+B)")

        # Status bar
        status = tk.Frame(main, bg=P["SURFACE"], padx=16, pady=6)
        status.pack(side="bottom", fill="x")
        tk.Frame(main, bg=P["BORDER"], height=1).pack(side="bottom", fill="x")
        self._status_dot = tk.Label(status, text="●", font=_font(9),
                                    fg=P["GREEN"], bg=P["SURFACE"])
        self._status_dot.pack(side="left")
        self._status_bar = tk.Label(status, text="Ready to organize",
                                    font=_font(9), fg=P["FG_DIM"], bg=P["SURFACE"])
        self._status_bar.pack(side="left", padx=(4, 0))
        tk.Label(status, text=f"{_MOD_LABEL}+O organize  ·  {_MOD_LABEL}+P preview  ·  F1 shortcuts",
                 font=_font(8), fg=P["FG_DIM"], bg=P["SURFACE"]).pack(side="right")

        # Pages
        content = tk.Frame(main, bg=P["BG"])
        content.pack(fill="both", expand=True, padx=26, pady=(10, 16))

        self._tab_frames = {}
        self._active_tab = tk.StringVar(value="")

        # Activity log
        log_frame = tk.Frame(content, bg=P["BG"])
        self._tab_frames["log"] = log_frame
        log_card = tk.Frame(log_frame, bg=P["SURFACE"], highlightthickness=1,
                            highlightbackground=P["BORDER"])
        log_card.pack(fill="both", expand=True)
        self._log_text = tk.Text(log_card, bg=P["SURFACE"], fg=P["FG"], font=_font(10),
            relief="flat", bd=0, state="disabled", wrap="word", cursor="arrow",
            highlightthickness=0, padx=18, pady=14, spacing1=3, spacing3=3,
            selectbackground=P["ACCENT_SOFT"], selectforeground=P["FG"])
        log_scroll = ttk.Scrollbar(log_card, orient="vertical", command=self._log_text.yview,
                                   style="Arise.Vertical.TScrollbar")
        self._log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y", padx=(0, 2), pady=2)
        self._log_text.pack(fill="both", expand=True)
        self._tag_log_colors()

        # History
        hist_frame = tk.Frame(content, bg=P["BG"])
        self._tab_frames["history"] = hist_frame
        self._build_history_tab(hist_frame)

        # Last run
        stats_frame = tk.Frame(content, bg=P["BG"])
        self._tab_frames["stats"] = stats_frame
        self._stats_frame_ref = stats_frame
        self._empty_state(stats_frame, "📊", "No runs yet",
                          "Preview a folder to see exactly what ARISE-I would do — nothing moves until you say so.",
                          ("🔎  Preview Changes", self._preview))

        # Review Queue
        review_frame = tk.Frame(content, bg=P["BG"])
        self._tab_frames["review"] = review_frame
        self._build_review_tab(review_frame)

        self._switch_tab("log")

    def _tag_log_colors(self) -> None:
        t = self._log_text
        t.tag_configure("ts",   foreground=_P["FG_DIM"], font=_font(9))
        t.tag_configure("ok",   foreground=_P["GREEN"])
        t.tag_configure("warn", foreground=_P["YELLOW"])
        t.tag_configure("err",  foreground=_P["RED"])
        t.tag_configure("dim",  foreground=_P["FG_DIM"])
        t.tag_configure("hdr",  foreground=_P["ACCENT"], font=_font(10, "bold"))

    # ------------------------------------------------------------------ Navigation

    def _nav_style(self, page_id: str) -> None:
        item, ic, lb, badge = self._nav_items[page_id]
        active = page_id == self._active_tab.get()
        bg = _P["ACCENT_SOFT"] if active else _P["SIDEBAR"]
        for w in (item, ic, lb):
            w.configure(bg=bg)
        ic.configure(fg=_P["ACCENT"] if active else _P["FG_DIM"])
        lb.configure(fg=_P["ACCENT"] if active else _P["FG"],
                     font=_font(10, "bold" if active else "normal"))

    def _nav_hover(self, page_id: str, inside: bool) -> None:
        if page_id == self._active_tab.get():
            return
        item, ic, lb, _badge = self._nav_items[page_id]
        color = _P["HOVER"] if inside else _P["SIDEBAR"]
        for w in (item, ic, lb):
            self._tween(w, "bg", color, ms=110)

    def _place_indicator(self, animate: bool = True) -> None:
        tab = self._active_tab.get()
        if tab not in self._nav_items:
            return
        item = self._nav_items[tab][0]
        y_to, h = item.winfo_y() + 8, max(8, item.winfo_height() - 16)
        y_from = self._indicator_y if (animate and self._indicator_y is not None) else y_to
        self._indicator_y = y_to
        self._nav_indicator.place(x=1, y=y_from, width=3, height=h)
        self._nav_indicator.lift()
        self._anim.run("nav-indicator", 240 if animate else 0,
                       lambda t: self._nav_indicator.place_configure(
                           y=int(y_from + (y_to - y_from) * t)))

    def _set_header_actions(self, tab_id: str) -> None:
        for w in self._header_actions.winfo_children():
            w.destroy()
        actions = {
            "log":     [("Clear log", self._clear_log)],
            "history": [("⟳  Refresh", self._refresh_history)],
            "review":  [("⟳  Refresh", self._refresh_review)],
            "stats":   [("View activity  →", lambda: self._switch_tab("log"))],
        }.get(tab_id, [])
        for text, cmd in actions:
            self._button(self._header_actions, text, cmd, kind="ghost",
                         padx=10, pady=4).pack(side="right", padx=(6, 0))

    def _switch_tab(self, tab_id: str):
        prev = self._active_tab.get()
        for tid, frame in self._tab_frames.items():
            if tid != tab_id:
                frame.place_forget()
        frame = self._tab_frames[tab_id]
        offset = 28 if prev and prev != tab_id else 0
        frame.place(x=offset, y=0, relwidth=1, relheight=1)
        frame.lift()
        if offset:
            self._anim.run("page", 220, lambda t: frame.place_configure(x=int(offset * (1 - t))))
        self._active_tab.set(tab_id)

        for pid in self._nav_items:
            self._nav_style(pid)
        self.update_idletasks()
        self._place_indicator(animate=bool(prev))
        meta = {p[0]: p for p in _PAGES}[tab_id]
        self._page_title.configure(text=meta[1])
        self._page_sub.configure(text=meta[3])
        self._set_header_actions(tab_id)

        if tab_id == "history":
            self._refresh_history()
        if tab_id == "review":
            self._refresh_review()

    # ------------------------------------------------------------------ Folder

    def _refresh_folder_hint(self) -> None:
        """Validate the folder field, then count its files off the UI thread."""
        self._hint_job = None
        self._hint_token += 1
        raw = self._target_var.get().strip()
        path = Path(raw).expanduser() if raw else None
        if not raw:
            self._apply_folder_hint("Choose a folder to organize", "YELLOW", "BORDER")
            self._set_review_badge(0)
        elif not path.is_dir():
            self._apply_folder_hint("⚠  Folder not found — check the path or Browse…", "RED", "RED")
            self._set_review_badge(0)
        elif is_protected_dir(path):
            self._apply_folder_hint(
                "⚠  Pick a subfolder — whole drives and your home folder are off-limits",
                "YELLOW", "BORDER")
            self._set_review_badge(0)
        else:
            token = self._hint_token
            threading.Thread(target=self._scan_folder, args=(path, token),
                             daemon=True, name="arise-i-scan").start()

    def _scan_folder(self, path: Path, token: int) -> None:
        """Worker: count loose files and Review files (slow on network drives)."""
        loose = review = 0
        try:
            with os.scandir(path) as it:
                for entry in it:
                    # Same rules as a run: ARISE-I's own log/manifest, hidden,
                    # system and half-downloaded files are never sorted
                    if entry.is_file() and skip_reason(Path(entry.path)) is None:
                        loose += 1
                        if loose >= 10000:
                            break
        except OSError:
            pass
        try:
            with os.scandir(path / REVIEW_FOLDER) as it:
                review = sum(1 for e in it if not e.name.startswith(".") and e.is_file())
        except OSError:
            pass
        self._log_queue.put(("__HINT__", token, loose, review))

    def _apply_scan(self, token: int, loose: int, review: int) -> None:
        if token != self._hint_token:
            return  # the folder changed while this scan ran
        self._loose_count = loose
        count = f"{loose:,}{'+' if loose >= 10000 else ''}"
        text = (f"{count} loose file{'s' if loose != 1 else ''} ready to sort"
                if loose else "✓  Nothing to sort — this folder is tidy")
        self._apply_folder_hint(text, "FG_DIM", "BORDER")
        self._set_review_badge(review)

    def _apply_folder_hint(self, text: str, color: str, border: str) -> None:
        self._folder_hint.configure(text=text, fg=_P[color])
        if self.focus_get() is not self._path_entry:
            self._folder_box.configure(highlightbackground=_P[border])
            # Long paths: keep the folder name (the end) in view
            self._path_entry.xview_moveto(1.0)
        if not self._busy and not self._watching:
            problem = color in ("RED", "YELLOW")
            self._set_status(text.lstrip("⚠ ") if problem else "Ready to organize",
                             "err" if color == "RED" else "warn" if problem else "ok")

    def _set_review_badge(self, count: int) -> None:
        badge = self._nav_items["review"][3]
        if count:
            badge.configure(text=str(count) if count < 100 else "99+")
            badge.pack(side="right", padx=(0, 10))
        else:
            badge.pack_forget()

    def _commit_typed_folder(self) -> None:
        """Remember a typed folder right away (not only on quit) once it exists."""
        target = self._current_target()
        if target is not None and target.is_dir():
            set_pref("last_folder", self._target_var.get().strip())
        self._refresh_folder_hint()

    def _open_folder(self):
        target = Path(self._target_var.get().strip()).expanduser()
        if not target.is_dir():
            self._toast("Folder not found", "err"); return
        try:
            if sys.platform == "win32":    os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin": subprocess.Popen(["open", str(target)])
            else:                          subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:
            self._toast(f"Could not open folder: {exc}", "err")

    # ------------------------------------------------------------------ History

    def _build_history_tab(self, parent):
        self._hist_canvas, self._hist_container = self._scroll_area(parent)

    def _refresh_history(self):
        for w in self._hist_container.winfo_children():
            w.destroy()
        self._hist_canvas.yview_moveto(0)

        target = self._current_target()
        if target is None:
            self._empty_state(self._hist_container, "📁", "No folder selected",
                              "Choose a folder to see its organize history.",
                              ("Browse…", self._browse))
            return
        history = _load_manifest(target)

        if not history:
            self._empty_state(self._hist_container, "🕘", "No runs recorded yet",
                              "Every organize is logged here, so you can see what moved and undo the latest run.")
            return

        for i, run in enumerate(reversed(history)):
            ts    = run.get("timestamp","unknown")
            moves = run.get("moves", [])
            self._build_history_card(self._hist_container, ts, moves, i)

    def _build_history_card(self, parent, ts, moves, idx):
        P = _P
        card = tk.Frame(parent, bg=P["SURFACE"], padx=18, pady=14,
                        highlightthickness=1, highlightbackground=P["BORDER"])
        card.pack(fill="x", pady=(0, 10))

        top = tk.Frame(card, bg=P["SURFACE"])
        top.pack(fill="x")
        tk.Label(top, text=_relative_time(ts), font=_font(11, "bold"),
                 fg=P["FG"], bg=P["SURFACE"]).pack(side="left")
        tk.Label(top, text=f"   {ts.replace('T', '  ')}", font=_font(9),
                 fg=P["FG_DIM"], bg=P["SURFACE"]).pack(side="left")
        tk.Label(top, text=f"{len(moves)} file{'s' if len(moves) != 1 else ''}",
                 font=_font(9, "bold"), fg=P["ACCENT"], bg=P["ACCENT_SOFT"],
                 padx=10, pady=2).pack(side="right")
        if idx == 0:
            tk.Label(top, text="↩ undoable", font=_font(8), fg=P["GREEN"],
                     bg=P["SURFACE"], padx=8).pack(side="right")

        # Category breakdown as chips
        cats: dict[str,int] = {}
        for m in moves:
            dest = Path(m.get("dest",""))
            cat  = dest.parent.name if dest.parent.name else "Others"
            cats[cat] = cats.get(cat, 0) + 1

        ranked = sorted(cats.items(), key=lambda x: -x[1])
        if ranked:
            chips = tk.Frame(card, bg=P["SURFACE"])
            chips.pack(fill="x", pady=(10, 0))
            for cat, n in ranked[:6]:
                tk.Label(chips, text=f"{_cat_icon(cat)} {cat}  {n}", font=_font(9),
                         fg=P["FG"], bg=P["BG"], padx=8, pady=3).pack(side="left", padx=(0, 6))
            if len(ranked) > 6:
                tk.Label(chips, text=f"+{len(ranked) - 6} more", font=_font(9),
                         fg=P["FG_DIM"], bg=P["SURFACE"]).pack(side="left")
        self._card_hover(card)

    # ------------------------------------------------------------------ Stats card

    def _show_stats_card(self, stats: Stats, dry_run: bool):
        P = _P
        frame = self._stats_frame_ref
        for w in frame.winfo_children():
            w.destroy()

        total = stats.total_files()
        if not total and not stats.errors:
            self._empty_state(frame, "✨", "Nothing to sort",
                              "Every file here is already in its folder. Drop new files in, "
                              "or turn on Auto-Sort to handle them as they arrive.")
            self._switch_tab("stats")
            return
        if dry_run:
            title = "Preview ready"
            sub   = f"{total} file{'s' if total != 1 else ''} would be organized — nothing has moved yet."
        else:
            title = "✅  All organized"
            sub   = f"{total} file{'s' if total != 1 else ''} organized. Changed your mind? Undo anytime ({_MOD_LABEL}+Z)."

        head = tk.Frame(frame, bg=P["BG"])
        head.pack(fill="x")
        texts = tk.Frame(head, bg=P["BG"])
        texts.pack(side="left")
        tk.Label(texts, text=title, font=_font(18, "bold"), fg=P["FG"], bg=P["BG"]).pack(anchor="w")
        tk.Label(texts, text=sub, font=_font(10), fg=P["FG_DIM"], bg=P["BG"]).pack(anchor="w")
        if dry_run and total and not self._watching:
            self._button(head, "✨  Organize these files", self._sort_now,
                         kind="primary", padx=16, pady=8).pack(side="right")

        # KPI tiles with count-up numbers
        tiles = tk.Frame(frame, bg=P["BG"])
        tiles.pack(fill="x", pady=(16, 12))
        kpis = [
            (total, "files" if not dry_run else "files to move", "ACCENT"),
            (len(stats._data), "categories", "FG"),
            (stats.skipped, "skipped", "YELLOW" if stats.skipped else "FG"),
            (stats.errors, "errors", "RED" if stats.errors else "FG"),
        ]
        for col, (value, caption, color) in enumerate(kpis):
            tiles.columnconfigure(col, weight=1, uniform="kpi")
            tile = tk.Frame(tiles, bg=P["SURFACE"], padx=16, pady=12,
                            highlightthickness=1, highlightbackground=P["BORDER"])
            tile.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
            num = tk.Label(tile, text="0", font=_font(22, "bold"), fg=P[color], bg=P["SURFACE"])
            num.pack(anchor="w")
            tk.Label(tile, text=caption, font=_font(9), fg=P["FG_DIM"], bg=P["SURFACE"]).pack(anchor="w")
            self._anim.run(f"kpi{col}", 700,
                           lambda t, n=num, v=value: n.configure(text=f"{round(v * t):,}"))

        if stats._data:
            card = tk.Frame(frame, bg=P["SURFACE"], padx=20, pady=16,
                            highlightthickness=1, highlightbackground=P["BORDER"])
            card.pack(fill="both", expand=True)
            tk.Label(card, text="Breakdown by category", font=_font(11, "bold"),
                     fg=P["FG"], bg=P["SURFACE"]).pack(anchor="w", pady=(0, 10))
            rows = tk.Frame(card, bg=P["SURFACE"])
            rows.pack(fill="x")
            rows.columnconfigure(1, weight=1)

            sorted_cats = sorted(stats._data.items(), key=lambda kv: -kv[1]["count"])
            top_count = max(1, sorted_cats[0][1]["count"])
            shown = sorted_cats[:10]
            for r, (cat, data) in enumerate(shown):
                label = "Review" if cat == REVIEW_FOLDER else cat
                tk.Label(rows, text=f"{_cat_icon(cat)}  {label}", font=_font(10), fg=P["FG"],
                         bg=P["SURFACE"], anchor="w", width=18).grid(row=r, column=0, sticky="w", pady=4)
                bar = tk.Canvas(rows, height=scaled(self, 12), bg=P["SURFACE"],
                                highlightthickness=0, bd=0)
                bar.grid(row=r, column=1, sticky="ew", padx=(8, 12))
                tk.Label(rows, text=str(data["count"]), font=_font(10, "bold"), fg=P["FG"],
                         bg=P["SURFACE"], width=4, anchor="e").grid(row=r, column=2, sticky="e")
                row = {"canvas": bar, "frac": data["count"] / top_count, "prog": 0.0,
                       "color": "YELLOW" if cat == REVIEW_FOLDER else "ACCENT"}
                bar.bind("<Configure>", lambda e, rw=row: self._draw_bar(rw))
                self._on_theme(bar, lambda rw=row: self._draw_bar(rw))

                def _grow(t, rw=row):
                    rw["prog"] = t
                    self._draw_bar(rw)
                # Stagger rows so the chart "fills in" top to bottom
                self.after(60 * r, lambda g=_grow, k=r: self._anim.run(f"bar{k}", 650, g))
            if len(sorted_cats) > len(shown):
                tk.Label(card, text=f"+ {len(sorted_cats) - len(shown)} more categories",
                         font=_font(9), fg=P["FG_DIM"], bg=P["SURFACE"]).pack(anchor="w", pady=(8, 0))

        if stats.errors:
            tk.Label(frame, text=f"⚠  {stats.errors} error(s) — check the Activity page",
                     font=_font(10), fg=P["RED"], bg=P["BG"]).pack(anchor="w", pady=(10, 0))

        self._switch_tab("stats")

    def _draw_bar(self, row: dict) -> None:
        c = row["canvas"]
        try:
            w = c.winfo_width()
        except tk.TclError:
            return
        c.delete("all")
        if w < 12:
            return
        h = c.winfo_height()
        y, thick, pad = h / 2, max(4, h - 2), h / 2
        c.create_line(pad, y, w - pad, y, width=thick, capstyle="round", fill=_P["BG"])
        end = pad + (w - 2 * pad) * row["frac"] * row["prog"]
        if row["prog"] > 0:
            c.create_line(pad, y, max(pad + 0.5, end), y, width=thick, capstyle="round",
                          fill=_P[row["color"]])

    # ------------------------------------------------------------------ Review Queue

    def _build_review_tab(self, parent):
        """Scrollable list of files in __Review__/ that need user confirmation."""
        self._review_canvas, self._review_container = self._scroll_area(parent)

    def _refresh_review(self):
        for w in self._review_container.winfo_children():
            w.destroy()
        self._review_canvas.yview_moveto(0)

        target = self._current_target()
        if target is None:
            self._set_review_badge(0)
            self._empty_state(self._review_container, "📁", "No folder selected",
                              "Choose a folder to review its uncertain files.",
                              ("Browse…", self._browse))
            return
        files: list[Path] = []
        try:
            files = [i for i in sorted((target / REVIEW_FOLDER).iterdir())
                     if i.is_file() and not i.name.startswith(".")]
        except OSError:
            pass  # no Review folder yet, or it can't be read
        self._set_review_badge(len(files))

        if not files:
            self._empty_state(self._review_container, "✅", "All clear",
                              "Every file was classified confidently. Unsure files land here for a one-click decision.")
            return

        banner = tk.Frame(self._review_container, bg=_P["ACCENT_SOFT"], padx=14, pady=10)
        banner.pack(fill="x", pady=(0, 10))
        tk.Label(banner, text=f"⚑  {len(files)} file{'s' if len(files) != 1 else ''} need a decision. "
                              "Pick a suggestion or choose any folder — ARISE-I learns from every choice.",
                 font=_font(10), fg=_P["FG"], bg=_P["ACCENT_SOFT"], justify="left",
                 wraplength=scaled(self, 640)).pack(anchor="w")

        categories = load_categories(None, target)
        choices    = list(categories.keys()) + ["Others"]
        try:
            classifier = get_classifier(categories)
        except Exception:
            classifier = None

        for item in files:
            suggestions = self._suggest_categories(classifier, item, categories)
            self._build_review_card(self._review_container, item, target,
                                    choices, suggestions)

    @staticmethod
    def _suggest_categories(classifier, item: Path, categories: dict) -> list[str]:
        """Up to three likely categories for *item*, best first."""
        if classifier is None:
            return []
        try:
            result = classifier.classify(item)
        except Exception:
            return []
        ranked = [(result.category, result.confidence)] + list(result.alternatives)
        picks: list[str] = []
        for cat, conf in ranked:
            if cat in categories and cat not in picks and conf >= 0.2:
                picks.append(cat)
        return picks[:3]

    def _build_review_card(self, parent, item: Path, target: Path,
                           choices: list[str], suggestions: list[str]):
        P = _P
        card = tk.Frame(parent, bg=P["SURFACE"], padx=16, pady=12,
                        highlightthickness=1, highlightbackground=P["BORDER"])
        card.pack(fill="x", pady=(0, 8))

        top = tk.Frame(card, bg=P["SURFACE"])
        top.pack(fill="x")
        tk.Label(top, text="📄", font=_font(14), fg=P["FG_DIM"], bg=P["SURFACE"]).pack(side="left", padx=(0, 10))
        names = tk.Frame(top, bg=P["SURFACE"])
        names.pack(side="left", fill="x", expand=True)
        tk.Label(names, text=item.name, font=_font(10, "bold"), fg=P["FG"],
                 bg=P["SURFACE"], anchor="w").pack(anchor="w")
        tk.Label(names, text=f"{item.suffix.upper().lstrip('.') or 'No extension'}  ·  {self._human_size(item)}",
                 font=_font(9), fg=P["FG_DIM"], bg=P["SURFACE"]).pack(anchor="w")

        btn_row = tk.Frame(card, bg=P["SURFACE"])
        btn_row.pack(fill="x", pady=(10, 0))
        if suggestions:
            tk.Label(btn_row, text="Suggested:", font=_font(9), fg=P["FG_DIM"],
                     bg=P["SURFACE"]).pack(side="left", padx=(0, 6))
        # One-click buttons for the classifier's best guesses
        for cat in suggestions:
            chip = tk.Button(
                btn_row, text=f"{_cat_icon(cat)} {cat}",
                font=_font(9, "bold"), fg=P["ACCENT"], bg=P["ACCENT_SOFT"],
                activebackground=P["ACCENT_FILL"], activeforeground=ON_ACCENT,
                relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
                command=lambda i=item, c=cat, t=target: self._confirm_category(i, c, t),
            )
            chip.pack(side="left", padx=(0, 6))
            self._hover(chip, "ACCENT_SOFT", "ACCENT_FILL", fg="ACCENT", fg_hover=ON_ACCENT)

        # …plus every category via a dropdown
        move = self._button(btn_row, "Move", None, kind="primary", size=9, padx=12, pady=4)
        move.pack(side="right")
        picked = tk.StringVar(value=suggestions[0] if suggestions else "Others")
        ttk.Combobox(btn_row, textvariable=picked, values=choices,
                     state="readonly", width=16, font=_font(10)).pack(side="right", padx=(8, 6))
        tk.Label(btn_row, text="or move to", font=_font(9), fg=P["FG_DIM"],
                 bg=P["SURFACE"]).pack(side="right")
        move.configure(command=lambda i=item, v=picked, t=target: self._confirm_category(i, v.get(), t))
        self._card_hover(card)

    def _confirm_category(self, item: Path, category: str, target: Path):
        """Move a Review file to the chosen category and record feedback."""
        if self._busy:
            self._toast("Hang on — a run is still in progress", "warn")
            return
        dest_dir  = target / category
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            # Never overwrite a same-named file already in that category
            dest_path = get_unique_destination(dest_dir, item.name)
            shutil.move(str(item), str(dest_path))
            # Logged like a run, so Undo can put the file back in Review
            try:
                record_moves(target, [{"src": str(item), "dest": str(dest_path),
                                       "confidence": 1.0, "layer": "user_review"}])
            except Exception as exc:
                self._log(f"⚠  Could not log this move for undo: {exc}", "warn")
            note = f" (renamed: {dest_path.name})" if dest_path.name != item.name else ""
            self._log(f"✓  Review resolved: {item.name}  →  {category}/{note}  [USER]", "ok")
            self._toast(f"Moved {item.name} → {category}   ·   {_MOD_LABEL}+Z to undo", "ok")
            # Record correction in learning store
            if self._learning_store is not None:
                try:
                    self._learning_store.record(
                        path=dest_path,
                        predicted=REVIEW_FOLDER,
                        confirmed=category,
                        confidence=0.0,
                        layer="user_review",
                    )
                except Exception:
                    pass
            self._refresh_review()
        except Exception as exc:
            self._log(f"✗  Could not move {item.name}: {exc}", "err")
            self._toast(f"Could not move {item.name}", "err")

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

    # ------------------------------------------------------------------ Pulse & progress

    def _draw_pulse_dot(self, glow: float) -> None:
        c = self._pulse_dot
        d = int(c.cget("width"))
        lo, hi = d * 0.25, d * 0.75
        c.delete("all")
        if self._pulse_active:
            c.create_oval(0, 0, d, d, fill=mix(_P["SURFACE"], _P["GREEN"], 0.15 + 0.3 * glow), width=0)
            c.create_oval(lo, lo, hi, hi, fill=_P["GREEN"], width=0)
        else:
            c.create_oval(lo, lo, hi, hi, fill=mix(_P["SURFACE"], _P["FG_DIM"], 0.6), width=0)

    def _start_pulse(self):
        self._pulse_active = True
        self._pulse_t0 = time.perf_counter()
        name = Path(self._target_var.get().strip()).name or "folder"
        self._pulse_label.configure(text=f"Watching {name}", fg=_P["GREEN"])
        self._do_pulse()

    def _do_pulse(self, *_):
        if not self._pulse_active:
            self._draw_pulse_dot(0.0)
            return
        # A slow "breathing" glow rather than an on/off blink
        k = (math.sin((time.perf_counter() - self._pulse_t0) * 2 * math.pi / 1.8) + 1) / 2
        self._draw_pulse_dot(k if self._animations else 1.0)
        self._pulse_id = self.after(50, self._do_pulse)

    def _stop_pulse(self):
        self._pulse_active = False
        if self._pulse_id:
            self.after_cancel(self._pulse_id)
            self._pulse_id = None
        self._pulse_label.configure(text="Off", fg=_P["FG_DIM"])
        self._draw_pulse_dot(0.0)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if self._prog_job:
            self.after_cancel(self._prog_job); self._prog_job = None
        self._progress.delete("all")
        if busy:
            self._prog_phase = 0.0
            self._progress_tick()

    def _progress_tick(self) -> None:
        c = self._progress
        w = c.winfo_width()
        c.delete("all")
        if not self._animations:
            c.create_rectangle(0, 0, w, c.winfo_height(), fill=_P["ACCENT"], width=0)
            return
        self._prog_phase = (self._prog_phase + 0.012) % 1.0
        seg = w * 0.3
        x = -seg + (w + seg) * ease_in_out(self._prog_phase)
        c.create_rectangle(x, 0, x + seg, c.winfo_height(), fill=_P["ACCENT"], width=0)
        self._prog_job = self.after(16, self._progress_tick)

    # ------------------------------------------------------------------ Log

    def _poll_log_queue(self):
        """Drain worker messages on the Tk thread (widgets are not thread-safe)."""
        try:
            while True:
                msg = self._log_queue.get_nowait()
                try:
                    self._handle_message(msg)
                except Exception as exc:  # one bad message must not stop polling
                    self._log(f"✗  Display error: {exc}", "err")
        except queue.Empty:
            pass
        if not self._closing:
            self.after(50, self._poll_log_queue)

    def _handle_message(self, msg) -> None:
        if isinstance(msg, tuple):
            kind = msg[0]
            if kind == "__STATS__":
                stats, dry_run = msg[1], msg[2]
                self._show_stats_card(stats, dry_run)
                n = stats.total_files()
                if stats.errors:
                    self._toast(f"Finished with {stats.errors} error(s) — see Activity", "warn")
                elif dry_run and not n:
                    self._toast("Nothing to move — this folder is already tidy")
                elif dry_run:
                    self._toast(f"Preview ready — {n} file{'s' if n != 1 else ''} would move")
                else:
                    self._toast(f"Done — {n} file{'s' if n != 1 else ''} organized", "ok")
            elif kind == "__UNDO__":
                restored, failed = msg[1], msg[2]
                if restored and not failed:
                    self._toast(f"Undo complete — {restored} file{'s' if restored != 1 else ''} restored", "ok")
                elif restored:
                    self._toast(f"Restored {restored}, {failed} couldn't be restored — see Activity", "warn")
                elif failed:
                    self._toast("Nothing could be restored — see Activity", "err")
                else:
                    self._toast("Nothing to undo in this folder")
            elif kind == "__RUN_FAILED__":
                self._toast(f"Something went wrong: {msg[1]}", "err")
            elif kind == "__HINT__":
                self._apply_scan(msg[1], msg[2], msg[3])
            elif kind == "__WATCH_FAILED__":
                if msg[1] is self._watch_stop and self._watching:  # ignore stale sessions
                    self._auto_sort_var.set(False)
                    self._stop_watch()
                    self._toast("Auto-Sort stopped — see Activity", "err")
            return

        if msg == "__DONE__":
            self._run_label = ""
            self._set_buttons_enabled(True)
            self._set_status("Ready to organize")
            self._refresh_folder_hint()
        elif msg == "__REFRESH_VIEWS__":
            if self._active_tab.get() == "history":
                self._refresh_history()
            elif self._active_tab.get() == "review":
                self._refresh_review()
            self._refresh_folder_hint()
        elif msg == "__HEALTH_RETRAIN__":
            self._log("🧠  Retraining model…", "hdr")
        else:
            self._log(msg, self._tag_for(msg))
            self._count_progress(msg)

    def _count_progress(self, msg: str) -> None:
        """Show "Organizing… 12 / 40" while a manual run reports each file."""
        if not (self._busy and self._run_label and "  →  " in msg):
            return
        self._run_done += 1
        total = max(self._loose_count, self._run_done)
        self._set_status(f"{self._run_label}…  {self._run_done:,} / {total:,} files", "busy")

    @staticmethod
    def _tag_for(msg: str) -> str:
        """Log colour for a plain message, from its leading symbol."""
        if "[HIGH" in msg:
            return "ok"
        if "[LOW" in msg:
            return "warn"
        if msg.startswith(("✓", "✅")):
            return "ok"
        if msg.startswith(("⚠", "[SIM]", "⚡", "♥", "⚕")):
            return "warn"
        if msg.startswith("✗"):
            return "err"
        if msg.startswith(("ARISE-I", "──", "🧠", "⚔️")):
            return "hdr"
        return ""

    def _log(self, message: str, tag: str = ""):
        t = self._log_text
        t.configure(state="normal")
        t.insert("end", datetime.now().strftime("%H:%M:%S") + "   ", "ts")
        t.insert("end", message.strip() + "\n", tag)
        # Keep long auto-sort sessions snappy
        if int(t.index("end-1c").split(".")[0]) > 5000:
            t.delete("1.0", "500.0")
        t.see("end")
        t.configure(state="disabled")

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")
        self._log("Log cleared", "dim")

    def _enqueue_log(self, message: str):
        self._log_queue.put(message)

    def _set_status(self, text: str, kind: str = "ok"):
        """Status-bar text with a coloured dot: ok, busy, warn or err."""
        dot = {"busy": "ACCENT", "warn": "YELLOW", "err": "RED"}.get(kind, "GREEN")
        self._status_bar.configure(text=text, fg=_P["RED"] if kind == "err" else _P["FG_DIM"])
        self._status_dot.configure(fg=_P[dot])

    # ------------------------------------------------------------------ Actions

    def _actions_locked(self) -> bool:
        """True (with a hint) while a run or auto-sort makes actions unsafe."""
        if self._closing:
            return True
        if self._busy:
            self._toast("Hang on — a run is still in progress", "warn"); return True
        if self._watching:
            self._toast("Turn off Auto-Sort first", "warn"); return True
        return False

    def _run_onboarding(self):
        folder = onboarding.run_if_needed(self)
        if folder:
            self._target_var.set(folder)
            self._log(f"Folder set to: {Path(folder).name}", "dim")

    def _browse(self):
        if self._actions_locked():
            return
        folder = filedialog.askdirectory(title="Select folder to organize",
                                          initialdir=self._target_var.get(), parent=self)
        if folder:
            self._target_var.set(folder)
            set_pref("last_folder", folder)
            self._log(f"Folder changed to: {Path(folder).name}", "dim")

    def _preview(self):
        if self._actions_locked(): return
        self._run_organization(dry_run=True)

    def _sort_now(self):
        if self._actions_locked(): return
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
            messagebox.showerror("No folder", "Please select a folder.", parent=self); return
        tp = Path(target).expanduser()
        if not tp.exists():
            messagebox.showerror("Not found", f"Folder not found:\n{target}", parent=self); return
        if not tp.is_dir():
            messagebox.showerror("Not a folder", f"Not a folder:\n{target}", parent=self); return
        if is_protected_dir(tp):
            messagebox.showerror("Safety",
                "Choose a subfolder (Downloads, Desktop, etc.), not a whole drive "
                "or your home folder.",
                parent=self); return

        self._set_buttons_enabled(False)
        (self._preview_btn if dry_run else self._sort_btn).configure(
            text="⏳  Previewing…" if dry_run else "⏳  Organizing…")
        self._run_label = "Previewing" if dry_run else "Organizing"
        self._run_done = 0
        self._set_status(f"{self._run_label}…", "busy")
        self._switch_tab("log")
        self._log("🔎  Previewing changes" if dry_run else "✨  Organizing files", "hdr")

        def _worker():
            try:
                stats = organize_folder(target, dry_run=dry_run,
                    categories=load_categories(None, target),
                    log_callback=self._enqueue_log,
                    plugins=self._plugins,
                    learning_store=None if dry_run else self._learning_store)
                action = "would be organized" if dry_run else "organized"
                self._log_queue.put(f"✓  Done! {stats.total_files()} file(s) {action}")
                if stats.skipped: self._log_queue.put(f"   {stats.skipped} skipped")
                if stats.errors:  self._log_queue.put(f"   {stats.errors} error(s)")
                self._log_queue.put(("__STATS__", stats, dry_run))
            except Exception as e:
                self._log_queue.put(f"✗  Error: {e}")
                self._log_queue.put(("__RUN_FAILED__", str(e)))
            finally:
                self._log_queue.put("__DONE__")

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_auto_sort(self):
        if self._auto_sort_var.get():
            if not WATCHDOG_AVAILABLE:
                self._log("⚠  Auto-sort needs: pip install watchdog", "warn")
                self._toast("Auto-Sort needs: pip install watchdog", "warn")
                self._auto_sort_var.set(False); return
            self._start_watch()
        else:
            self._stop_watch()

    def _start_watch(self):
        if not WATCHDOG_AVAILABLE:
            messagebox.showerror("watchdog missing", "Run: pip install watchdog", parent=self)
            self._auto_sort_var.set(False); return
        target = self._target_var.get().strip()
        if not target or not Path(target).expanduser().is_dir():
            messagebox.showerror("Not found", f"Folder not found:\n{target}", parent=self)
            self._auto_sort_var.set(False); return
        if is_protected_dir(Path(target)):
            messagebox.showerror("Safety",
                "Auto-sort can't watch a whole drive or your home folder.", parent=self)
            self._auto_sort_var.set(False); return

        self._watching = True
        # A fresh Event per session: re-enabling within the old worker's
        # 0.5 s poll must not revive it, so it only ever sees its own event.
        stop = threading.Event()
        self._watch_stop = stop
        # Undo while watching would just get re-sorted by the watcher
        for btn in (self._sort_btn, self._preview_btn, self._undo_btn):
            btn.configure(state="disabled")
        self._path_entry.configure(state="readonly")
        self._set_menu_actions("disabled")
        self._set_status(f"Auto-sorting {Path(target).name}…", "busy")
        self._log("🔄  Auto-sort enabled", "hdr")
        self._toast(f"Auto-Sort is watching {Path(target).name}", "ok")
        self._start_pulse()

        try:
            debounce = max(0.1, min(300.0, float(self._debounce_var.get())))
        except (tk.TclError, ValueError):
            debounce = 2.0
        cats     = load_categories(None, target)

        def _worker():
            from watchdog.observers import Observer as _Obs
            from arise_i.core.watcher import AriseIEventHandler as _H

            class _GUIHandler(_H):
                def _run_organizer(inner):
                    self._log_queue.put("📁  New files — organizing…")
                    try:
                        s = organize_folder(str(inner.target_dir),
                            dry_run=inner.dry_run,
                            categories=load_categories(None, inner.target_dir),
                            log_callback=self._enqueue_log,
                            plugins=self._plugins,
                            learning_store=self._learning_store)
                        self._log_queue.put(f"✓  {s.total_files()} file(s) organized")
                    except Exception as exc:
                        self._log_queue.put(f"✗  Auto-sort run failed: {exc}")
                    self._log_queue.put("__REFRESH_VIEWS__")

            try:
                handler  = _GUIHandler(target_dir=Path(target).expanduser().resolve(),
                                       debounce=debounce, dry_run=False, categories=cats)
                observer = _Obs()
                observer.schedule(handler, str(handler.target_dir), recursive=False)
                observer.start()
            except Exception as exc:
                self._log_queue.put(f"✗  Auto-sort could not start: {exc}")
                self._log_queue.put(("__WATCH_FAILED__", stop))
                return
            while not stop.wait(0.5) and observer.is_alive():
                pass
            try: handler._timer.cancel()
            except Exception: pass
            crashed = not observer.is_alive() and not stop.is_set()
            observer.stop()
            if observer.is_alive(): observer.join(timeout=5)
            if crashed:
                self._log_queue.put("✗  Auto-sort watcher stopped unexpectedly")
                self._log_queue.put(("__WATCH_FAILED__", stop))
                return
            self._log_queue.put("🛑  Auto-sort stopped")

        threading.Thread(target=_worker, daemon=True, name="arise-i-watch").start()

    def _stop_watch(self):
        was_watching = self._watching
        self._watch_stop.set()
        self._watching = False
        for btn in (self._sort_btn, self._preview_btn, self._undo_btn):
            btn.configure(state="normal")
        self._path_entry.configure(state="normal")
        self._set_menu_actions("normal")
        self._set_status("Ready to organize")
        self._stop_pulse()
        if was_watching and not self._closing:
            self._refresh_folder_hint()

    def _undo(self):
        if self._actions_locked(): return
        target = self._target_var.get().strip()
        if not target:
            messagebox.showerror("No folder", "Please select a folder.", parent=self); return
        tp = Path(target).expanduser()
        if not tp.exists():
            messagebox.showerror("Not found", f"Folder not found:\n{target}", parent=self); return
        # Ctrl+Z is global, so it can fire while editing the path field —
        # never move files without an explicit yes.
        if not messagebox.askyesno(
            "Undo last run?",
            f"Move the files from the last ARISE-I run in:\n\n{tp}\n\n"
            "back to where they were?",
            parent=self,
        ):
            return

        self._set_buttons_enabled(False)
        self._set_status("Undoing last run…", "busy")
        self._log("↩  Undoing last organization", "hdr")

        def _worker():
            try:
                restored, failed = undo_last_run(target, log_callback=self._enqueue_log)
                self._log_queue.put(("__UNDO__", restored, failed))
            except Exception as e:
                self._log_queue.put(f"✗  Error: {e}")
                self._log_queue.put(("__RUN_FAILED__", str(e)))
            finally:
                self._log_queue.put("__REFRESH_VIEWS__")
                self._log_queue.put("__DONE__")

        threading.Thread(target=_worker, daemon=True).start()

    def _set_menu_actions(self, state: str) -> None:
        for label in ("Preview Changes", "Organize Now", "Undo Last Run"):
            try:
                self._menu_file.entryconfigure(label, state=state)
            except tk.TclError:
                pass

    def _set_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self._sort_btn.configure(state=state)
        self._preview_btn.configure(state=state)
        self._undo_btn.configure(state=state)
        self._sort_btn.configure(bg=_P["ACCENT_FILL"] if enabled else _P["ACCENT_D"])
        if enabled:
            self._sort_btn.configure(text="✨  Organize Now")
            self._preview_btn.configure(text="🔎  Preview", bg=_P["SURFACE"])
            self._undo_btn.configure(bg=_P["BG"])
        self._set_menu_actions(state)
        self._set_busy(not enabled)
        if not self._watching:
            self._auto_check.configure(state=state)

    def _setup_shortcuts(self):
        binds = {
            "o": self._sort_now, "p": self._preview, "z": self._undo,
            "q": self._on_close, "b": self._browse, "e": self._open_folder,
            "d": self._toggle_theme,
        }
        for key, fn in binds.items():
            for variant in (key, key.upper()):
                seq = f"<{_MOD}-{variant}>"
                handler = lambda e, f=fn: (f(), "break")[1]  # noqa: E731
                self.bind(seq, handler)
                # Entry's own Emacs-style keys (Ctrl+D delete, Ctrl+B/E move…)
                # would otherwise edit the path *and* run the app action.
                self._path_entry.bind(seq, handler)
        for i, (page_id, *_rest) in enumerate(_PAGES, start=1):
            self.bind(f"<{_MOD}-Key-{i}>", lambda e, p=page_id: self._switch_tab(p))
        self.bind("<F1>", lambda e: self._show_shortcuts())
        if sys.platform == "darwin":
            # Cmd+Q / app-menu Quit bypass WM_DELETE_WINDOW on macOS
            self.createcommand("tk::mac::Quit", self._on_close)

    def _on_close(self):
        if self._closing:
            return
        self._closing = True
        for job in (self._toast_job, self._hint_job, self._prog_job, self._pulse_id):
            if job:
                try: self.after_cancel(job)
                except tk.TclError: pass
        if self._watching:
            self._stop_watch()
        if self._health_monitor is not None:
            self._health_monitor.stop()
        prefs = load_prefs()
        prefs["last_folder"] = self._target_var.get()
        try:
            prefs["debounce"] = float(self._debounce_var.get())
        except (tk.TclError, ValueError):
            pass
        prefs["theme"]       = self._theme
        prefs["animations"]  = self._animations
        if self.state() == "normal":
            prefs["window_geometry"] = self.geometry()
        save_prefs(prefs)
        self._anim.run("win-alpha", 140, lambda t: self._set_alpha(1 - t),
                       done=self.destroy, ease=ease_in_out)


def _enable_hidpi() -> None:
    """Ask Windows for real pixels instead of a blurry bitmap-stretched window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # per-monitor aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _self_test() -> int:
    """Report what this build can do, without opening a window (CI smoke test)."""
    from arise_i.core import classifier
    print(f"ARISE-I {__version__}")
    print(f"  watchdog : {'yes' if WATCHDOG_AVAILABLE else 'no'}")
    print(f"  sklearn  : {'yes' if classifier._SKLEARN_AVAILABLE else 'no'}")
    print(f"  filetype : {'yes' if classifier._FILETYPE_AVAILABLE else 'no'}")
    print(f"  tk       : {tk.TkVersion}")
    return 0 if WATCHDOG_AVAILABLE else 1


def main():
    if "--self-test" in sys.argv[1:]:
        sys.exit(_self_test())
    _enable_hidpi()
    app = AriseIApp()
    app.mainloop()

if __name__ == "__main__":
    main()
