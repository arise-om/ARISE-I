"""
tests/test_theme.py
-------------------
Every text colour the GUI draws meets WCAG AA (4.5:1) on the surfaces it is
drawn on, in both themes.  Hover tints are transient and not covered.
"""

import pytest

pytest.importorskip("tkinter")

from arise_i.gui.theme import ON_ACCENT, RECOLOR_KEYS, THEMES  # noqa: E402

AA = 4.5

# (text key, background key) pairs that actually occur in app.py / onboarding.py
TEXT_ON_SURFACE = [
    ("FG", "BG"), ("FG", "SURFACE"), ("FG", "SIDEBAR"), ("FG", "ACCENT_SOFT"),
    ("FG_DIM", "BG"), ("FG_DIM", "SURFACE"), ("FG_DIM", "SIDEBAR"),
    ("ACCENT", "BG"), ("ACCENT", "SURFACE"), ("ACCENT", "ACCENT_SOFT"), ("ACCENT", "SIDEBAR"),
    ("GREEN", "BG"), ("GREEN", "SURFACE"),
    ("YELLOW", "BG"), ("YELLOW", "SURFACE"),
    ("RED", "BG"), ("RED", "SURFACE"),
    ("BG", "FG"),  # toasts and tooltips are inverted
]

FILLS_UNDER_WHITE = ["ACCENT_FILL", "ACCENT_D"]


def _luminance(color: str) -> float:
    c = color.lstrip("#")
    channels = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("theme", sorted(THEMES))
@pytest.mark.parametrize("fg, bg", TEXT_ON_SURFACE)
def test_text_contrast(theme, fg, bg):
    p = THEMES[theme]
    assert contrast(p[fg], p[bg]) >= AA, f"{theme}: {fg} on {bg}"


@pytest.mark.parametrize("theme", sorted(THEMES))
@pytest.mark.parametrize("bg", FILLS_UNDER_WHITE)
def test_white_text_on_accent_fills(theme, bg):
    assert ON_ACCENT == "white"
    assert contrast("#ffffff", THEMES[theme][bg]) >= AA


def test_themes_define_the_same_keys():
    light, dark = THEMES["light"], THEMES["dark"]
    assert set(light) == set(dark)
    assert set(RECOLOR_KEYS) <= set(light)
