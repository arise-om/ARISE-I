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

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from prefs import get_pref, save_prefs, load_prefs

# ---------------------------------------------------------------------------
# Colour palette (matches gui.py)
# ---------------------------------------------------------------------------

BG         = "#f5f5f7"
SURFACE    = "#ffffff"
ACCENT     = "#007AFF"
ACCENT_DIM = "#0056b3"
FG         = "#1d1d1f"
FG_DIM     = "#86868b"
GREEN      = "#34C759"
BORDER     = "#e5e5e7"


def _font(size: int = 10, weight: str = "normal") -> tuple:
    if sys.platform == "darwin":
        return ("SF Pro Display", size, weight)
    elif sys.platform == "win32":
        return ("Segoe UI", size, weight)
    else:
        return ("Ubuntu", size, weight)


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

        self.title("Welcome to ARISE-I")
        self.geometry("560x540")
        self.resizable(False, False)
        self.configure(bg=BG)

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Close = skip onboarding (don't block forever)
        self.protocol("WM_DELETE_WINDOW", self._skip)

        self._folder_var = tk.StringVar(value=self.confirmed_folder)
        self._build()

    # ------------------------------------------------------------------ #
    # Build UI                                                             #
    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        # ── Hero section ──────────────────────────────────────────────
        hero = tk.Frame(self, bg=ACCENT)
        hero.pack(fill="x")

        tk.Label(
            hero, text="ARISE-I",
            font=_font(36, "bold"), fg="white", bg=ACCENT,
        ).pack(pady=(28, 4))

        tk.Label(
            hero, text="Your personal file organizer",
            font=_font(13), fg="white", bg=ACCENT, padx=20,
        ).pack(pady=(0, 24))

        # ── Feature cards ─────────────────────────────────────────────
        cards_frame = tk.Frame(self, bg=BG, padx=32)
        cards_frame.pack(fill="x", pady=20)

        for row_idx in range(0, len(_FEATURES), 2):
            row = tk.Frame(cards_frame, bg=BG)
            row.pack(fill="x", pady=4)
            for col_idx in range(2):
                fi = row_idx + col_idx
                if fi >= len(_FEATURES):
                    break
                emoji, title, desc = _FEATURES[fi]
                card = tk.Frame(row, bg=SURFACE, padx=12, pady=10)
                card.pack(side="left", expand=True, fill="both", padx=(0, 8) if col_idx == 0 else (8, 0))
                tk.Label(card, text=emoji, font=_font(18), bg=SURFACE).pack(anchor="w")
                tk.Label(card, text=title, font=_font(11, "bold"), fg=FG, bg=SURFACE).pack(anchor="w")
                tk.Label(card, text=desc, font=_font(9), fg=FG_DIM, bg=SURFACE,
                         wraplength=180, justify="left").pack(anchor="w")

        # ── Folder picker ─────────────────────────────────────────────
        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x", padx=32)

        picker_frame = tk.Frame(self, bg=BG, padx=32, pady=16)
        picker_frame.pack(fill="x")

        tk.Label(picker_frame, text="Choose a folder to organize:",
                 font=_font(11, "bold"), fg=FG, bg=BG).pack(anchor="w")
        tk.Label(picker_frame, text="ARISE-I will use this as its default.",
                 font=_font(9), fg=FG_DIM, bg=BG).pack(anchor="w", pady=(2, 10))

        entry_row = tk.Frame(picker_frame, bg=BG)
        entry_row.pack(fill="x")

        self._folder_entry = tk.Entry(
            entry_row,
            textvariable=self._folder_var,
            font=_font(10), bg=SURFACE, fg=FG,
            insertbackground=ACCENT, relief="flat",
            bd=0, highlightthickness=1,
            highlightcolor=ACCENT, highlightbackground=BORDER,
            readonlybackground=SURFACE,
        )
        self._folder_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        tk.Button(
            entry_row, text="Browse",
            font=_font(10), fg=ACCENT, bg=BG,
            activebackground=BG, activeforeground=ACCENT_DIM,
            relief="flat", bd=0, padx=10, pady=6,
            cursor="hand2", command=self._browse,
        ).pack(side="left")

        # ── CTA button ────────────────────────────────────────────────
        cta_frame = tk.Frame(self, bg=BG, padx=32, pady=12)
        cta_frame.pack(fill="x")

        tk.Button(
            cta_frame,
            text="Let's Go  →",
            font=_font(13, "bold"), fg="white", bg=ACCENT,
            activebackground=ACCENT_DIM, activeforeground="white",
            relief="flat", bd=0, padx=40, pady=12,
            cursor="hand2", command=self._complete,
        ).pack(expand=True)

        tk.Label(
            cta_frame,
            text="Your files never leave your computer. Nothing is deleted.",
            font=_font(9), fg=FG_DIM, bg=BG,
        ).pack(pady=(8, 0))

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
