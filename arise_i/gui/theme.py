"""
ARISE-I — Look & Feel
---------------------
Shared palettes, fonts, colour maths and a tiny animation engine used by
the main window (app.py) and the first-run wizard (onboarding.py).

Everything here is plain tkinter — no extra dependencies.
"""

import sys
import time
import tkinter as tk
from typing import Callable

# ── Colour palettes ───────────────────────────────────────────────────────────
# Within one theme every key listed in RECOLOR_KEYS must have a unique value:
# a theme switch maps old colours to new ones value-for-value.
#
# Text colours meet WCAG AA (4.5:1) on the surfaces they are used on — see
# tests/test_theme.py.  ACCENT is the accent for *text* (links, ghost buttons,
# active nav); ACCENT_FILL is the accent behind white text (primary buttons,
# badges), which needs to be darker than an accent that is readable as text.
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "BG":          "#f5f5f7",
        "SURFACE":     "#ffffff",
        "SIDEBAR":     "#fbfbfd",
        "HOVER":       "#ececf0",
        "BORDER":      "#e3e3e8",
        "ACCENT":      "#0062cc",
        "ACCENT_FILL": "#0060c7",
        "ACCENT_D":    "#004c9c",  # pressed / hovered fill
        "ACCENT_SOFT": "#e8f1ff",
        "GREEN":       "#1d7a34",
        "YELLOW":      "#8a6100",  # amber: bright yellow is unreadable on white
        "RED":         "#D70015",
        "FG":          "#1d1d1f",
        "FG_DIM":      "#6e6e73",
    },
    "dark": {
        "BG":          "#1c1c1e",
        "SURFACE":     "#2c2c2e",
        "SIDEBAR":     "#232325",
        "HOVER":       "#38383b",
        "BORDER":      "#3a3a3c",
        "ACCENT":      "#4da3ff",
        "ACCENT_FILL": "#0a6cdf",
        "ACCENT_D":    "#0858b8",
        "ACCENT_SOFT": "#17314f",
        "GREEN":       "#30D158",
        "YELLOW":      "#FFD60A",
        "RED":         "#ff6b61",
        "FG":          "#f2f2f7",
        "FG_DIM":      "#98989f",
    },
}

RECOLOR_KEYS = ("BG", "SURFACE", "SIDEBAR", "HOVER", "BORDER", "ACCENT", "ACCENT_FILL",
                "ACCENT_D", "ACCENT_SOFT", "GREEN", "YELLOW", "RED", "FG", "FG_DIM")

# Text drawn on ACCENT_FILL in both themes.  Deliberately a colour *name*: a
# theme switch remaps hex values, and "#ffffff" is also the light SURFACE.
ON_ACCENT = "white"
ON_ACCENT_DISABLED = "#c9dcf5"


# ── Fonts ─────────────────────────────────────────────────────────────────────

# Preferred UI families on Linux, best first; the first one installed wins.
_LINUX_FAMILIES = ("Inter", "Cantarell", "Ubuntu", "Noto Sans", "DejaVu Sans")
_family: str | None = None


def _ui_family() -> str:
    """The platform's UI font, looked up once a Tk root exists."""
    global _family
    if _family is None:
        if sys.platform == "win32":
            _family = "Segoe UI"
        else:
            try:
                import tkinter.font as tkfont
                installed = set(tkfont.families())
                default = tkfont.nametofont("TkDefaultFont").actual("family")
            except (tk.TclError, RuntimeError):
                return "TkDefaultFont"  # no root yet — don't cache a guess
            # On macOS the default *is* the system font (SF Pro); asking for
            # "SF Pro Display" by name often silently falls back to Helvetica.
            picks = () if sys.platform == "darwin" else _LINUX_FAMILIES
            _family = next((f for f in picks if f in installed), default)
    return _family


def font(size: int = 10, weight: str = "normal") -> tuple:
    return (_ui_family(), size, weight)


def scaled(widget: tk.Misc, px: float) -> int:
    """*px* designed at 96 DPI, converted for this screen (HiDPI-safe)."""
    try:
        factor = widget.winfo_fpixels("1i") / 96.0
    except tk.TclError:
        factor = 1.0
    return max(1, round(px * max(1.0, factor)))


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

    def __init__(self, parent: tk.Misc, variable: tk.BooleanVar,
                 command: Callable[[], None], palette: dict[str, str],
                 animator: Animator, bg_key: str = "SURFACE"):
        self.W, self.H = scaled(parent, 44), scaled(parent, 24)
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
        self._focused = False
        self.canvas.bind("<FocusIn>", lambda e: self._set_focus(True))
        self.canvas.bind("<FocusOut>", lambda e: self._set_focus(False))
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

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self.redraw()

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
        knob = "#ffffff"  # the knob is white in both themes, like the system switch
        if not self._enabled:
            track, knob = mix(track, bg, 0.55), mix(knob, bg, 0.3)
        w, h, r = self.W, self.H, self.H / 2
        k = h / 24  # drawing offsets are designed for a 24 px tall switch
        c.create_oval(0, 0, h, h, fill=track, width=0)
        c.create_oval(w - h, 0, w, h, fill=track, width=0)
        c.create_rectangle(r, 0, w - r, h, fill=track, width=0)
        x = 2 * k + (w - h) * pos
        c.create_oval(x + k, 3 * k, x + h - 3 * k, h - k, fill=mix(track, "#000000", 0.25), width=0)
        c.create_oval(x, 2 * k, x + h - 4 * k, h - 2 * k, fill=knob, width=0)
        if self._focused:  # keyboard focus ring
            c.create_rectangle(1, 1, w - 1, h - 1, outline=p["ACCENT"], width=1)
