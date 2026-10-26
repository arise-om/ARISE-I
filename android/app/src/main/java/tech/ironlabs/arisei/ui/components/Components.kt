package tech.ironlabs.arisei.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.HelpOutline
import androidx.compose.material.icons.outlined.Android
import androidx.compose.material.icons.outlined.Archive
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Code
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.FontDownload
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.outlined.Movie
import androidx.compose.material.icons.outlined.MusicNote
import androidx.compose.material.icons.outlined.PictureAsPdf
import androidx.compose.material.icons.outlined.RemoveCircleOutline
import androidx.compose.material.icons.outlined.School
import androidx.compose.material.icons.outlined.Slideshow
import androidx.compose.material.icons.outlined.TableChart
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import tech.ironlabs.arisei.engine.Badge
import tech.ironlabs.arisei.ui.theme.AriseTokens
import tech.ironlabs.arisei.ui.theme.KpiNumberStyle
import tech.ironlabs.arisei.ui.theme.LocalAriseColors
import tech.ironlabs.arisei.ui.theme.LocalReduceMotion

/** Icon for a category folder; assignment subjects get a school cap. */
fun categoryIcon(category: String): ImageVector = when (category) {
    "Images" -> Icons.Outlined.Image
    "Videos" -> Icons.Outlined.Movie
    "Music" -> Icons.Outlined.MusicNote
    "Documents" -> Icons.Outlined.Description
    "PDFs" -> Icons.Outlined.PictureAsPdf
    "Spreadsheets" -> Icons.Outlined.TableChart
    "Presentations" -> Icons.Outlined.Slideshow
    "Code" -> Icons.Outlined.Code
    "Archives" -> Icons.Outlined.Archive
    "Installers" -> Icons.Outlined.Android
    "Ebooks" -> Icons.AutoMirrored.Outlined.MenuBook
    "Fonts" -> Icons.Outlined.FontDownload
    "__Review__" -> Icons.Outlined.Inbox
    "Others" -> Icons.Outlined.Folder
    else -> if ("/" in category) Icons.Outlined.School else Icons.Outlined.Folder
}

/** Display name for a folder path ("__Review__" reads as "Review"). */
fun displayCategory(category: String, reviewLabel: String) = if (category == "__Review__") reviewLabel else category

/** "HIGH 92 %" — meaning carried by text and icon shape, not colour alone. */
@Composable
fun ConfidenceChip(badge: Badge, confidence: Double, modifier: Modifier = Modifier) {
    val color = LocalAriseColors.current.confidence(badge)
    val icon = when (badge) {
        Badge.HIGH -> Icons.Outlined.CheckCircle
        Badge.MED -> Icons.Outlined.RemoveCircleOutline
        Badge.LOW -> Icons.AutoMirrored.Outlined.HelpOutline
    }
    Row(
        modifier
            .clip(MaterialTheme.shapes.small)
            .background(color.copy(alpha = 0.14f))
            .padding(horizontal = 6.dp, vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(12.dp))
        Spacer(Modifier.width(3.dp))
        Text(
            "${badge.name} ${(confidence * 100).toInt()}%",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

/** The desktop's "breathing" Auto-Sort dot.  Solid when idle or motion is reduced. */
@Composable
fun PulseDot(active: Boolean, modifier: Modifier = Modifier) {
    val accent = LocalAriseColors.current.brandAccent
    val color = if (active) LocalAriseColors.current.success else MaterialTheme.colorScheme.outline
    val animate = active && !LocalReduceMotion.current
    val phase = if (animate) {
        val transition = rememberInfiniteTransition(label = "pulse")
        transition.animateFloat(
            0f, 1f,
            infiniteRepeatable(tween(AriseTokens.Motion.PULSE, easing = LinearEasing), RepeatMode.Reverse),
            label = "phase",
        ).value
    } else 1f
    Box(modifier.size(14.dp), contentAlignment = Alignment.Center) {
        if (animate) {
            Box(
                Modifier.size(14.dp).scale(1f + 0.25f * phase).clip(CircleShape)
                    .background(accent.copy(alpha = 0.18f * phase)),
            )
        }
        Box(Modifier.size(8.dp).clip(CircleShape).background(color.copy(alpha = 0.35f + 0.65f * phase)))
    }
}

/** A KPI number that counts up (desktop: 700 ms). */
@Composable
fun KpiTile(label: String, value: Int, modifier: Modifier = Modifier, formatted: (Int) -> String = { it.toString() }) {
    val reduce = LocalReduceMotion.current
    val anim = remember(value) { Animatable(if (reduce) value.toFloat() else 0f) }
    LaunchedEffect(value) {
        if (!reduce) anim.animateTo(value.toFloat(), tween(AriseTokens.Motion.COUNT_UP, easing = FastOutSlowInEasing))
    }
    Surface(
        modifier.semantics(mergeDescendants = true) {},
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceContainerLow,
    ) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
            Text(
                formatted(anim.value.toInt()),
                style = KpiNumberStyle,
                color = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.clearAndSetSemantics { contentDescription = "$label: ${formatted(value)}" },
            )
            Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** Animated horizontal bars of files per category (desktop Last Run chart). */
@Composable
fun CategoryBars(counts: List<Pair<String, Int>>, modifier: Modifier = Modifier) {
    val max = counts.maxOfOrNull { it.second }?.coerceAtLeast(1) ?: 1
    val reduce = LocalReduceMotion.current
    val accent = LocalAriseColors.current.brandAccent
    val track = MaterialTheme.colorScheme.surfaceContainerHighest
    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        counts.forEachIndexed { i, (category, count) ->
            val grow = remember(category, count) { Animatable(if (reduce) 1f else 0f) }
            LaunchedEffect(category, count) {
                if (!reduce) {
                    grow.animateTo(
                        1f,
                        tween(AriseTokens.Motion.BAR_GROW, delayMillis = i * AriseTokens.Motion.BAR_STAGGER, easing = FastOutSlowInEasing),
                    )
                }
            }
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.semantics(mergeDescendants = true) { contentDescription = "$category: $count" },
            ) {
                Icon(categoryIcon(category), null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.width(8.dp))
                Text(
                    category, style = MaterialTheme.typography.bodyMedium, maxLines = 1,
                    overflow = TextOverflow.Ellipsis, modifier = Modifier.width(104.dp),
                )
                Box(Modifier.weight(1f).height(8.dp).clip(RoundedCornerShape(4.dp)).background(track)) {
                    Canvas(Modifier.fillMaxSize()) {
                        drawRoundRect(
                            color = accent,
                            size = size.copy(width = size.width * (count.toFloat() / max) * grow.value),
                            cornerRadius = androidx.compose.ui.geometry.CornerRadius(4.dp.toPx()),
                        )
                    }
                }
                Spacer(Modifier.width(8.dp))
                Text(
                    count.toString(), style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier.width(32.dp), textAlign = TextAlign.End,
                )
            }
        }
    }
}

/** What this is + why it's empty + how to start. */
@Composable
fun EmptyState(
    icon: ImageVector,
    title: String,
    body: String,
    modifier: Modifier = Modifier,
    action: String? = null,
    onAction: () -> Unit = {},
) {
    Column(
        modifier.fillMaxWidth().padding(horizontal = 32.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier.size(72.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, null, Modifier.size(36.dp), tint = MaterialTheme.colorScheme.onPrimaryContainer)
        }
        Spacer(Modifier.height(16.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
        Spacer(Modifier.height(6.dp))
        Text(
            body, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (action != null) {
            Spacer(Modifier.height(20.dp))
            FilledTonalButton(onClick = onAction) { Text(action) }
        }
    }
}

/** White card on the grey screen, like the desktop SURFACE panels. */
@Composable
fun AriseCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Card(
        modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) { content() }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier, trailing: @Composable () -> Unit = {}) {
    Row(modifier.fillMaxWidth().padding(top = 8.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(
            text, style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f),
        )
        trailing()
    }
}

/** Leading tile with a category icon. */
@Composable
fun CategoryAvatar(category: String, tint: Color = MaterialTheme.colorScheme.primary) {
    Box(
        Modifier.size(40.dp).clip(RoundedCornerShape(10.dp)).background(tint.copy(alpha = 0.12f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(categoryIcon(category), null, tint = tint, modifier = Modifier.size(22.dp))
    }
}
