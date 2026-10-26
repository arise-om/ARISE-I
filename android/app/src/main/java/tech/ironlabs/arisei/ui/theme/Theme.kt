package tech.ironlabs.arisei.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import tech.ironlabs.arisei.engine.Badge
import tech.ironlabs.arisei.data.ThemeMode

/** Colours outside the M3 scheme.  Fixed even with dynamic colour, so confidence keeps its meaning. */
@Immutable
data class AriseColors(
    val brandAccent: Color,
    val success: Color,
    val successText: Color,
    val warning: Color,
    val warningText: Color,
    val error: Color,
) {
    fun confidence(badge: Badge) = when (badge) {
        Badge.HIGH -> success
        Badge.MED -> warning
        Badge.LOW -> error
    }
}

val LocalAriseColors = staticCompositionLocalOf {
    with(AriseTokens.Light) { AriseColors(brandAccent, success, successText, warning, warningText, error) }
}

/** True when the user asked for reduced motion (in-app or system animator scale 0). */
val LocalReduceMotion = staticCompositionLocalOf { false }

private val lightScheme = with(AriseTokens.Light) {
    lightColorScheme(
        primary = primary, onPrimary = onPrimary,
        primaryContainer = primaryContainer, onPrimaryContainer = onPrimaryContainer,
        secondary = primary, onSecondary = onPrimary,
        secondaryContainer = primaryContainer, onSecondaryContainer = onPrimaryContainer,
        background = surface, onBackground = onSurface,
        surface = surface, onSurface = onSurface,
        surfaceVariant = surfaceHighest, onSurfaceVariant = onSurfaceVariant,
        surfaceContainerLowest = surfaceLowest, surfaceContainerLow = surfaceLow,
        surfaceContainer = surfaceContainer, surfaceContainerHigh = surfaceHigh,
        surfaceContainerHighest = surfaceHighest,
        outline = outline, outlineVariant = outlineVariant,
        error = error,
    )
}

private val darkScheme = with(AriseTokens.Dark) {
    darkColorScheme(
        primary = primary, onPrimary = onPrimary,
        primaryContainer = primaryContainer, onPrimaryContainer = onPrimaryContainer,
        secondary = primary, onSecondary = onPrimary,
        secondaryContainer = primaryContainer, onSecondaryContainer = onPrimaryContainer,
        background = surface, onBackground = onSurface,
        surface = surface, onSurface = onSurface,
        surfaceVariant = surfaceHighest, onSurfaceVariant = onSurfaceVariant,
        surfaceContainerLowest = surfaceLowest, surfaceContainerLow = surfaceLow,
        surfaceContainer = surfaceContainer, surfaceContainerHigh = surfaceHigh,
        surfaceContainerHighest = surfaceHighest,
        outline = outline, outlineVariant = outlineVariant,
        error = error,
    )
}

private val base = Typography()

/** System sans (no bundled font — keeps the APK small); tabular figures for KPIs. */
val AriseTypography = base.copy(
    displaySmall = base.displaySmall.copy(fontWeight = FontWeight.SemiBold, fontSize = 36.sp, lineHeight = 44.sp,
        fontFeatureSettings = "tnum"),
    titleLarge = base.titleLarge.copy(fontWeight = FontWeight.SemiBold),
    titleMedium = base.titleMedium.copy(fontWeight = FontWeight.Medium),
    labelSmall = base.labelSmall.copy(fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp),
)

val KpiNumberStyle = TextStyle(fontSize = 28.sp, lineHeight = 34.sp, fontWeight = FontWeight.SemiBold,
    fontFeatureSettings = "tnum")

val AriseShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

@Composable
fun AriseTheme(
    themeMode: ThemeMode = ThemeMode.SYSTEM,
    dynamicColor: Boolean = false,
    reduceMotion: Boolean = false,
    content: @Composable () -> Unit,
) {
    val dark = when (themeMode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    val context = LocalContext.current
    val scheme: ColorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        dark -> darkScheme
        else -> lightScheme
    }
    val extra = if (dark) {
        with(AriseTokens.Dark) { AriseColors(brandAccent, success, successText, warning, warningText, error) }
    } else {
        with(AriseTokens.Light) { AriseColors(brandAccent, success, successText, warning, warningText, error) }
    }
    val systemReduced = android.provider.Settings.Global.getFloat(
        context.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f,
    ) == 0f
    CompositionLocalProvider(
        LocalAriseColors provides extra,
        LocalReduceMotion provides (reduceMotion || systemReduced),
    ) {
        MaterialTheme(colorScheme = scheme, typography = AriseTypography, shapes = AriseShapes, content = content)
    }
}
