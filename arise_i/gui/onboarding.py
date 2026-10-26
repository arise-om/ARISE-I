"""
ARISE-I — First-Run Onboarding Wizard
--------------------------------------
Autonomous File Organization Unit: Welcome Screen.
Built by Om Deshmukh // Ironlabs.tech

Shown exactly once on first launch (when prefs.onboarding_done is False).
After the user completes it, prefs.onboarding_done is set to True and
the wizard never appears again.

The wizard is a modal Toplevel window that blocks the main GUI until
the user either completes setup or closes it.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from arise_i.core.prefs import get_pref, save_prefs, load_prefs
from arise_i.gui.theme import THEMES, Animator, font as _font


# ---------------------------------------------------------------------------
# Feature card data
# ---------------------------------------------------------------------------

_FEATURES = [
    ("✨", "One-Click Clean", "Sorts all your files into tidy folders instantly."),
    ("👁", "Safe Preview",    "See exactly what will happen before anything moves."),
    ("↩", "Always Undoable", "Every run is logged. Restore files with one click."),
    ("🔄", "Auto-Sort",       "Watch mode sorts new files the moment they land."),
]


# ---------------------------------------------------------------------------
# Onboarding wizard window
# ---------------------------------------------------------------------------

class OnboardingWizard(tk.Toplevel):
    """Modal first-run welcome wizard.

    Call ``show()`` and await ``self.result`` (True = completed, False = skipped).
    The caller should check ``self.confirmed_folder`` for the chosen path.
    """

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)

        self.result: bool = False
        self.confirmed_folder: str = str(Path.home() / "Downloads")
        # Follow the theme the user picked in the main window
        self._p = THEMES.get(get_pref("theme", "light"), THEMES["light"])
        self._anim = Animator(self, enabled=lambda: bool(get_pref("animations", True)))

        self.title("Welcome to ARISE-I")
        self.resizable(False, False)
        self.configure(bg=self._p["BG"])

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Close = skip onboarding (don't block forever)
        self.protocol("WM_DELETE_WINDOW", self._skip)
        self.bind("<Return>", lambda e: self._complete())
        self.bind("<Escape>", lambda e: self._skip())

        self._folder_var = tk.StringVar(value=self.confirmed_folder)
        self._build()
        self._folder_var.trace_add("write", lambda *_: self._validate())
        self._validate()
        self.update_idletasks()
        self._center_on(parent, 600, self.winfo_reqheight())
        self._fade_in()

    def _center_on(self, parent: tk.Misc, w: int, h: int) -> None:
        parent.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        if pw > 1 and ph > 1:
            x = max(0, parent.winfo_rootx() + (pw - w) // 2)
            y = max(0, parent.winfo_rooty() + (ph - h) // 2)
        else:
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _fade_in(self) -> None:
        def _alpha(t):
            try: self.attributes("-alpha", t)
            except tk.TclError: pass
        _alpha(0.0)
        self._anim.run("alpha", 320, _alpha)
        # Let the hero title glide up into place
        self._anim.run("hero", 520, lambda t: self._hero_title.pack_configure(
            pady=(int(44 - 12 * t), 4)))

    def _hover(self, widget: tk.Misc, base: str, hover: str) -> None:
        widget.bind("<Enter>", lambda e: widget.configure(bg=self._p[hover]), add="+")
        widget.bind("<Leave>", lambda e: widget.configure(bg=self._p[base]), add="+")

    # ------------------------------------------------------------------ #
    # Build UI                                                             #
    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        P = self._p
        # ── Hero section ──────────────────────────────────────────────
        hero = tk.Frame(self, bg=P["ACCENT"])
        hero.pack(fill="x")

        self._hero_title = tk.Label(
            hero, text="ARISE-I",
            font=_font(34, "bold"), fg="white", bg=P["ACCENT"],
        )
        self._hero_title.pack(pady=(32, 4))

        tk.Label(
            hero, text="Your personal, AI-powered file organizer",
            font=_font(12), fg="white", bg=P["ACCENT"], padx=20,
        ).pack(pady=(0, 26))

        # ── Feature cards ─────────────────────────────────────────────
        cards_frame = tk.Frame(self, bg=P["BG"], padx=32)
        cards_frame.pack(fill="x", pady=(20, 12))
        cards_frame.columnconfigure(0, weight=1, uniform="card")
        cards_frame.columnconfigure(1, weight=1, uniform="card")

        for fi, (emoji, title, desc) in enumerate(_FEATURES):
            card = tk.Frame(cards_frame, bg=P["SURFACE"], padx=14, pady=12,
                            highlightthickness=1, highlightbackground=P["BORDER"])
            card.grid(row=fi // 2, column=fi % 2, sticky="nsew",
                      padx=(0, 6) if fi % 2 == 0 else (6, 0), pady=6)
            row = tk.Frame(card, bg=P["SURFACE"])
            row.pack(anchor="w")
            tk.Label(row, text=emoji, font=_font(14), fg=P["ACCENT"],
                     bg=P["SURFACE"]).pack(side="left", padx=(0, 8))
            tk.Label(row, text=title, font=_font(11, "bold"), fg=P["FG"],
                     bg=P["SURFACE"]).pack(side="left")
            tk.Label(card, text=desc, font=_font(9), fg=P["FG_DIM"], bg=P["SURFACE"],
                     wraplength=220, justify="left").pack(anchor="w", pady=(4, 0))

        # ── Folder picker ─────────────────────────────────────────────
        picker_frame = tk.Frame(self, bg=P["BG"], padx=32, pady=8)
        picker_frame.pack(fill="x")

        tk.Label(picker_frame, text="Choose a folder to organize",
                 font=_font(11, "bold"), fg=P["FG"], bg=P["BG"]).pack(anchor="w")
        tk.Label(picker_frame, text="Downloads is a great place to start. You can change it anytime.",
                 font=_font(9), fg=P["FG_DIM"], bg=P["BG"]).pack(anchor="w", pady=(2, 8))

        self._entry_box = tk.Frame(picker_frame, bg=P["SURFACE"], highlightthickness=1,
                                   highlightbackground=P["BORDER"])
        self._entry_box.pack(fill="x")
        tk.Label(self._entry_box, text="📁", font=_font(11), fg=P["FG_DIM"],
                 bg=P["SURFACE"]).pack(side="left", padx=(10, 4))
        self._folder_entry = tk.Entry(
            self._entry_box,
            textvariable=self._folder_var,
            font=_font(10), bg=P["SURFACE"], fg=P["FG"],
            insertbackground=P["ACCENT"], relief="flat",
            bd=0, highlightthickness=0,
            readonlybackground=P["SURFACE"],
        )
        self._folder_entry.pack(side="left", fill="x", expand=True, ipady=7)

        browse = tk.Button(
            self._entry_box, text="Browse…",
            font=_font(10), fg=P["ACCENT"], bg=P["SURFACE"],
            activebackground=P["HOVER"], activeforeground=P["ACCENT_D"],
            relief="flat", bd=0, padx=12, pady=4,
            cursor="hand2", command=self._browse,
        )
        browse.pack(side="right", padx=4)
        self._hover(browse, "SURFACE", "HOVER")

        self._folder_hint = tk.Label(picker_frame, text="", font=_font(9),
                                     fg=P["FG_DIM"], bg=P["BG"])
        self._folder_hint.pack(anchor="w", pady=(4, 0))

        # ── CTA button ────────────────────────────────────────────────
        cta_frame = tk.Frame(self, bg=P["BG"], padx=32, pady=10)
        cta_frame.pack(fill="x")

        cta = tk.Button(
            cta_frame,
            text="Let's Go  →",
            font=_font(12, "bold"), fg="white", bg=P["ACCENT"],
            activebackground=P["ACCENT_D"], activeforeground="white",
            relief="flat", bd=0, padx=40, pady=11,
            cursor="hand2", command=self._complete,
        )
        cta.pack(fill="x")
        self._hover(cta, "ACCENT", "ACCENT_D")

        foot = tk.Frame(cta_frame, bg=P["BG"])
        foot.pack(fill="x", pady=(8, 0))
        tk.Label(
            foot,
            text="🔒  Your files never leave your computer. Nothing is deleted.",
            font=_font(9), fg=P["FG_DIM"], bg=P["BG"],
        ).pack(side="left")
        skip = tk.Label(foot, text="Skip for now", font=_font(9, "underline"),
                        fg=P["FG_DIM"], bg=P["BG"], cursor="hand2")
        skip.pack(side="right")
        skip.bind("<Button-1>", lambda e: self._skip())

    def _validate(self) -> None:
        P = self._p
        folder = self._folder_var.get().strip()
        ok = bool(folder) and Path(folder).expanduser().is_dir()
        self._folder_hint.configure(
            text="✓  Folder found" if ok else "⚠  Folder not found — your Downloads folder will be used",
            fg=P["GREEN"] if ok else P["YELLOW"])
        self._entry_box.configure(highlightbackground=P["BORDER"] if ok else P["YELLOW"])

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    def _browse(self) -> None:
        folder = filedialog.askdirectory(
            title="Choose folder to organize",
            initialdir=self._folder_var.get(),
            parent=self,
        )
        if folder:
            self._folder_var.set(folder)

    def _complete(self) -> None:
        folder = self._folder_var.get().strip()
        if folder and Path(folder).expanduser().is_dir():
            self.confirmed_folder = folder
        self.result = True

        # Persist completion
        prefs = load_prefs()
        prefs["onboarding_done"] = True
        prefs["last_folder"] = self.confirmed_folder
        save_prefs(prefs)

        self.grab_release()
        self.destroy()

    def _skip(self) -> None:
        """User closed the window — skip onboarding, don't mark as done."""
        self.result = False
        self.grab_release()
        self.destroy()


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def run_if_needed(parent: tk.Tk) -> str | None:
    """Show the onboarding wizard if this is the first launch.

    Returns
    -------
    str or None
        The confirmed folder path if onboarding completed, else None.
    """
    if get_pref("onboarding_done", False):
        return None  # already done

    wizard = OnboardingWizard(parent)
    parent.wait_window(wizard)

    if wizard.result:
        return wizard.confirmed_folder
    return None
