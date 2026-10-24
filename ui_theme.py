"""
ARISE-I — Look & Feel
---------------------
Shared palettes, fonts, colour maths and a tiny animation engine used by
the main window (gui.py) and the first-run wizard (onboarding.py).

Everything here is plain tkinter — no extra dependencies.
"""

import sys
import time
import tkinter as tk
from typing import Callable

# ── Colour palettes ───────────────────────────────────────────────────────────
# Within one theme every key listed in RECOLOR_KEYS must have a unique value:
# a theme switch maps old colours to new ones value-for-value.
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "BG":       "#f5f5f7",
        "SURFACE":  "#ffffff",
        "SIDEBAR":  "#fbfbfd",
        "HOVER":    "#ececf0",
        "BORDER":   "#e3e3e8",
        "ACCENT":   "#007AFF",
        "ACCENT_D": "#0062cc",
        "ACCENT_SOFT": "#e8f1ff",
        "GREEN":    "#248A3D",  # darker than system green: readable on white
        "YELLOW":   "#B8860B",  # amber: bright yellow is unreadable on white
        "RED":      "#D70015",
        "FG":       "#1d1d1f",
        "FG_DIM":   "#6e6e73",
        "PANEL":    "#f0f0f2",
    },
    "dark": {
        "BG":       "#1c1c1e",
        "SURFACE":  "#2c2c2e",
        "SIDEBAR":  "#232325",
        "HOVER":    "#38383b",
        "BORDER":   "#3a3a3c",
        "ACCENT":   "#0A84FF",
        "ACCENT_D": "#0060df",
        "ACCENT_SOFT": "#17314f",
        "GREEN":    "#30D158",
        "YELLOW":   "#FFD60A",
        "RED":      "#FF453A",
        "FG":       "#f2f2f7",
        "FG_DIM":   "#98989f",
        "PANEL":    "#2c2c2e",
    },
}

# PANEL is legacy and shares a value with SURFACE in the dark theme, so it
# would make the old→new mapping ambiguous.
RECOLOR_KEYS = ("BG", "SURFACE", "SIDEBAR", "HOVER", "BORDER", "ACCENT",
                "ACCENT_D", "ACCENT_SOFT", "GREEN", "YELLOW", "RED", "FG", "FG_DIM")


def font(size: int = 10, weight: str = "normal") -> tuple:
    if sys.platform == "darwin":   return ("SF Pro Display", size, weight)
    elif sys.platform == "win32":  return ("Segoe UI", size, weight)
    else:                          return ("Ubuntu", size, weight)


# ── Colour maths ──────────────────────────────────────────────────────────────

def _rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    """Blend hex colour *a* towards *b* by *t* (0 → a, 1 → exactly b)."""
    if t <= 0: return a
    if t >= 1: return b
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#%02x%02x%02x" % (round(ra + (rb - ra) * t),
                              round(ga + (gb - ga) * t),
                              round(ba + (bb - ba) * t))


def to_hex(widget: tk.Misc, color: str) -> str:
    """Resolve any Tk colour name ("white", "SystemButtonFace") to #rrggbb."""
    if color.startswith("#") and len(color) in (4, 7):
        return color
    r, g, b = widget.winfo_rgb(color)
    return "#%02x%02x%02x" % (r >> 8, g >> 8, b >> 8)


# ── Animation ─────────────────────────────────────────────────────────────────

def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


class Animator:
    """Runs keyed, frame-based tweens on the Tk event loop.

    Starting an animation with a key that is already running cancels the old
    one, so rapid hovers or clicks never fight each other. When *enabled*
    returns False (reduced motion), every animation jumps straight to its end.
    """

    FRAME_MS = 15

    def __init__(self, root: tk.Misc, enabled: Callable[[], bool] = lambda: True):
        self._root = root
        self._enabled = enabled
        self._jobs: dict[str, str] = {}

    def run(self, key: str, duration_ms: int, step: Callable[[float], None],
            done: Callable[[], None] | None = None,
            ease: Callable[[float], float] = ease_out) -> None:
        self.cancel(key)
        if duration_ms <= 0 or not self._enabled():
            try: step(1.0)
            except tk.TclError: return
            if done: done()
            return
        start = time.perf_counter()

        def _tick():
            t = min(1.0, (time.perf_counter() - start) * 1000 / duration_ms)
            try:
                step(ease(t))
            except tk.TclError:          # widget destroyed mid-animation
                self._jobs.pop(key, None)
                return
            if t < 1.0:
                self._jobs[key] = self._root.after(self.FRAME_MS, _tick)
            else:
                self._jobs.pop(key, None)
                if done: done()

        _tick()

    def cancel(self, key: str) -> None:
        job = self._jobs.pop(key, None)
        if job:
            try: self._root.after_cancel(job)
            except tk.TclError: pass


# ── Widgets ───────────────────────────────────────────────────────────────────

class ToggleSwitch:
    """An iOS-style on/off switch drawn on a Canvas, bound to a BooleanVar.

    Exposes ``configure(state=...)`` so callers can treat it like the
    Checkbutton it replaces.
    """

    W, H = 44, 24

    def __init__(self, parent: tk.Misc, variable: tk.BooleanVar,
                 command: Callable[[], None], palette: dict[str, str],
                 animator: Animator, bg_key: str = "SURFACE"):
        self._var = variable
        self._command = command
        self._p = palette
        self._anim = animator
        self._bg_key = bg_key
        self._enabled = True
        self._pos = 1.0 if variable.get() else 0.0
        self.canvas = tk.Canvas(parent, width=self.W, height=self.H,
                                bg=palette[bg_key], highlightthickness=0,
                                bd=0, cursor="hand2", takefocus=1)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<space>", self._click)
        self.canvas.bind("<Return>", self._click)
        variable.trace_add("write", lambda *_: self._animate_to(variable.get()))
        self.redraw()

    def pack(self, **kw):
        self.canvas.pack(**kw)

    def configure(self, state: str | None = None, **_kw) -> None:
        if state is not None:
            self._enabled = state != "disabled"
            self.canvas.configure(cursor="hand2" if self._enabled else "arrow")
            self.redraw()

    config = configure

    def _click(self, _event=None):
        if not self._enabled:
            return "break"
        self._var.set(not self._var.get())
        self._command()
        return "break"

    def _animate_to(self, on: bool) -> None:
        start, end = self._pos, 1.0 if on else 0.0

        def _step(t):
            self._pos = start + (end - start) * t
            self.redraw()
        self._anim.run(f"toggle{id(self)}", 180, _step)

    def redraw(self) -> None:
        p, c, pos = self._p, self.canvas, self._pos
        bg = p[self._bg_key]
        c.configure(bg=bg)
        c.delete("all")
        off = mix(p["BORDER"], p["FG_DIM"], 0.35)
        track = mix(off, p["GREEN"], pos)
        knob = "#ffffff"
        if not self._enabled:
            track, knob = mix(track, bg, 0.55), mix(knob, bg, 0.3)
        w, h, r = self.W, self.H, self.H / 2
        c.create_oval(0, 0, h, h, fill=track, width=0)
        c.create_oval(w - h, 0, w, h, fill=track, width=0)
        c.create_rectangle(r, 0, w - r, h, fill=track, width=0)
        x = 2 + (w - h) * pos
        c.create_oval(x + 1, 3, x + h - 3, h - 1, fill=mix(track, "#000000", 0.25), width=0)
        c.create_oval(x, 2, x + h - 4, h - 2, fill=knob, width=0)
