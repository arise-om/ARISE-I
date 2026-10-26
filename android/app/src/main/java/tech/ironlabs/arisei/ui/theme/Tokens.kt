package tech.ironlabs.arisei.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Design tokens — the desktop `ui_theme.py` palettes mapped onto Material 3
 * roles.  Text-bearing roles are darkened where the desktop colour fails
 * WCAG AA (white on #007AFF is ~4:1), so #007AFF survives as [brandAccent]
 * for non-text accents only.
 */
object AriseTokens {
    object Light {
        val primary = Color(0xFF0062CC)
        val onPrimary = Color(0xFFFFFFFF)
        val primaryContainer = Color(0xFFD6E8FF)
        val onPrimaryContainer = Color(0xFF002D62)
        val surface = Color(0xFFF5F5F7)
        val surfaceLowest = Color(0xFFFFFFFF)
        val surfaceLow = Color(0xFFFBFBFD)
        val surfaceContainer = Color(0xFFF0F0F3)
        val surfaceHigh = Color(0xFFFFFFFF)
        val surfaceHighest = Color(0xFFECECF0)
        val onSurface = Color(0xFF1D1D1F)
        val onSurfaceVariant = Color(0xFF6E6E73)
        val outline = Color(0xFFC7C7CC)
        val outlineVariant = Color(0xFFE5E5EA)
        val error = Color(0xFFD70015)
        val brandAccent = Color(0xFF007AFF)
        val success = Color(0xFF248A3D)
        val successText = Color(0xFF1E7A35)
        val warning = Color(0xFFB8860B)
        val warningText = Color(0xFF7A5A00)
    }

    object Dark {
        val primary = Color(0xFF0A84FF)
        val onPrimary = Color(0xFF00162E)
        val primaryContainer = Color(0xFF003A75)
        val onPrimaryContainer = Color(0xFFD6E8FF)
        val surface = Color(0xFF1C1C1E)
        val surfaceLowest = Color(0xFF2C2C2E)
        val surfaceLow = Color(0xFF232325)
        val surfaceContainer = Color(0xFF2C2C2E)
        val surfaceHigh = Color(0xFF3A3A3C)
        val surfaceHighest = Color(0xFF38383B)
        val onSurface = Color(0xFFF2F2F7)
        val onSurfaceVariant = Color(0xFF98989F)
        val outline = Color(0xFF545458)
        val outlineVariant = Color(0xFF3A3A3C)
        val error = Color(0xFFFF453A)
        val brandAccent = Color(0xFF0A84FF)
        val success = Color(0xFF30D158)
        val successText = Color(0xFF30D158)
        val warning = Color(0xFFFFD60A)
        val warningText = Color(0xFFFFD60A)
    }

    /** Motion durations (ms), matched to the desktop `gui.py` animations. */
    object Motion {
        const val SNACK_IN = 260
        const val SNACK_OUT = 220
        const val SCREEN = 220
        const val NAV_INDICATOR = 240
        const val BAR_GROW = 650
        const val BAR_STAGGER = 60
        const val COUNT_UP = 650
        const val PULSE = 1800
        const val SHEET = 300
    }
}
