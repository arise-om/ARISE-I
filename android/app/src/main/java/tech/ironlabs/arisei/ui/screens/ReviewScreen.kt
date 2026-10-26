package tech.ironlabs.arisei.ui.screens

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import android.text.format.Formatter
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.DoneAll
import androidx.compose.material.icons.outlined.DriveFileMove
import androidx.compose.material.icons.outlined.Snooze
import androidx.compose.material.icons.outlined.TaskAlt
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.SuggestionChipDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.isCtrlPressed
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.data.ReviewItem
import tech.ironlabs.arisei.ui.components.AriseCard
import tech.ironlabs.arisei.ui.components.CategoryAvatar
import tech.ironlabs.arisei.ui.components.CategorySheet
import tech.ironlabs.arisei.ui.components.EmptyState
import tech.ironlabs.arisei.ui.theme.LocalAriseColors
import java.io.File

/**
 * Files ARISE-I wasn't sure about.  Swipe right accepts the best guess,
 * swipe left snoozes for a week, long-press selects several.  Every action
 * shows an Undo snackbar; a hardware keyboard gets J/K, Enter, 1–3.
 */
@OptIn(ExperimentalFoundationApi::class, ExperimentalLayoutApi::class)
@Composable
fun ReviewScreen(
    items: List<ReviewItem>,
    categoriesFor: (String) -> List<String>,
    contentPadding: PaddingValues,
    onAccept: (ReviewItem, String) -> Unit,
    onSnooze: (ReviewItem) -> Unit,
    onAcceptAll: (List<ReviewItem>, String?) -> Unit,
) {
    var selected by remember { mutableStateOf(setOf<String>()) }
    var choosing by remember { mutableStateOf<List<ReviewItem>?>(null) }
    var focusIndex by remember { mutableIntStateOf(0) }
    val haptics = LocalHapticFeedback.current
    val focus = remember { FocusRequester() }
    val listState = rememberLazyListState()
    fun key(item: ReviewItem) = File(item.folder, item.relPath).path

    if (items.isEmpty()) {
        Box(Modifier.fillMaxSize().padding(contentPadding)) {
            EmptyState(
                Icons.Outlined.TaskAlt, stringResource(R.string.review_empty_title),
                stringResource(R.string.review_empty_body), Modifier.align(Alignment.Center),
            )
        }
        return
    }
    LaunchedEffect(items.size) { focusIndex = focusIndex.coerceIn(0, items.lastIndex) }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }

    Column(Modifier.fillMaxSize().padding(top = contentPadding.calculateTopPadding())) {
        if (selected.isEmpty()) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(stringResource(R.string.review_title), style = MaterialTheme.typography.headlineMedium)
                Text(
                    stringResource(R.string.review_hint), style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            val chosen = items.filter { key(it) in selected }
            SelectionBar(
                count = chosen.size,
                onClear = { selected = emptySet() },
                onAcceptAll = { onAcceptAll(chosen, null); selected = emptySet() },
                onMoveAll = { choosing = chosen },
            )
        }
        LazyColumn(
            state = listState,
            contentPadding = PaddingValues(16.dp, 8.dp, 16.dp, contentPadding.calculateBottomPadding() + 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.onPreviewKeyEvent { e ->
                if (e.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                val current = items.getOrNull(focusIndex) ?: return@onPreviewKeyEvent false
                when {
                    e.key == Key.J -> { focusIndex = (focusIndex + 1).coerceAtMost(items.lastIndex); true }
                    e.key == Key.K -> { focusIndex = (focusIndex - 1).coerceAtLeast(0); true }
                    e.key == Key.Enter -> { current.suggestions.firstOrNull()?.let { onAccept(current, it.first) }; true }
                    e.key == Key.One || e.key == Key.Two || e.key == Key.Three -> {
                        val i = when (e.key) { Key.One -> 0; Key.Two -> 1; else -> 2 }
                        current.suggestions.getOrNull(i)?.let { onAccept(current, it.first) }; true
                    }
                    e.key == Key.N -> { onSnooze(current); true }
                    e.key == Key.Z && e.isCtrlPressed -> false // handled by the snackbar's Undo
                    else -> false
                }
            }.focusRequester(focus).focusable(),
        ) {
            items(items, key = { key(it) }) { item ->
                val index = items.indexOf(item)
                ReviewCard(
                    item = item,
                    focused = index == focusIndex,
                    selecting = selected.isNotEmpty(),
                    selected = key(item) in selected,
                    onToggleSelect = {
                        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                        selected = if (key(item) in selected) selected - key(item) else selected + key(item)
                    },
                    onAccept = { onAccept(item, it) },
                    onSnooze = { onSnooze(item) },
                    onChoose = { choosing = listOf(item) },
                    onThreshold = { haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove) },
                )
            }
        }
    }
    LaunchedEffect(focusIndex) { if (items.isNotEmpty()) listState.animateScrollToItem(focusIndex) }

    choosing?.let { batch ->
        val first = batch.first()
        CategorySheet(
            title = if (batch.size == 1) first.name else stringResource(R.string.review_move_all),
            categories = categoriesFor(first.folder),
            suggestions = if (batch.size == 1) first.suggestions else emptyList(),
            onDismiss = { choosing = null },
            onPick = { category ->
                if (batch.size == 1) onAccept(first, category) else onAcceptAll(batch, category)
                choosing = null
                selected = emptySet()
            },
        )
    }
}

@Composable
private fun SelectionBar(count: Int, onClear: () -> Unit, onAcceptAll: () -> Unit, onMoveAll: () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.primaryContainer) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onClear) { Icon(Icons.Outlined.Close, stringResource(R.string.action_clear_selection)) }
            Text(
                pluralStringResource(R.plurals.review_selected, count, count),
                style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f),
            )
            TextButton(onClick = onAcceptAll) {
                Icon(Icons.Outlined.DoneAll, null)
                Spacer(Modifier.width(4.dp))
                Text(stringResource(R.string.review_accept_all))
            }
            IconButton(onClick = onMoveAll) { Icon(Icons.Outlined.DriveFileMove, stringResource(R.string.review_move_all)) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class, ExperimentalLayoutApi::class)
@Composable
private fun ReviewCard(
    item: ReviewItem,
    focused: Boolean,
    selecting: Boolean,
    selected: Boolean,
    onToggleSelect: () -> Unit,
    onAccept: (String) -> Unit,
    onSnooze: () -> Unit,
    onChoose: () -> Unit,
    onThreshold: () -> Unit,
) {
    val context = LocalContext.current
    val best = item.suggestions.firstOrNull()
    val colors = LocalAriseColors.current
    val acceptLabel = best?.let { stringResource(R.string.review_swipe_accept, it.first) }
    val snoozeLabel = stringResource(R.string.review_swipe_snooze)
    val chooseLabel = stringResource(R.string.review_choose)
    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            when (value) {
                SwipeToDismissBoxValue.StartToEnd -> { best?.let { onAccept(it.first) }; best != null }
                SwipeToDismissBoxValue.EndToStart -> { onSnooze(); true }
                SwipeToDismissBoxValue.Settled -> false
            }
        },
        positionalThreshold = { distance -> distance * 0.35f },
    )
    LaunchedEffect(dismissState.targetValue) {
        if (dismissState.targetValue != SwipeToDismissBoxValue.Settled) onThreshold()
    }
    val days = ((System.currentTimeMillis() - item.waitingSinceMs) / 86_400_000L).toInt()

    SwipeToDismissBox(
        state = dismissState,
        enableDismissFromStartToEnd = best != null && !selecting,
        enableDismissFromEndToStart = !selecting,
        backgroundContent = {
            val toRight = dismissState.dismissDirection == SwipeToDismissBoxValue.StartToEnd
            Row(
                Modifier.fillMaxSize().clip(MaterialTheme.shapes.medium)
                    .background(if (toRight) colors.success.copy(alpha = 0.22f) else MaterialTheme.colorScheme.surfaceContainerHighest)
                    .padding(horizontal = 24.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = if (toRight) Arrangement.Start else Arrangement.End,
            ) {
                Icon(if (toRight) Icons.Outlined.CheckCircle else Icons.Outlined.Snooze, null)
                Spacer(Modifier.width(8.dp))
                Text(if (toRight) acceptLabel.orEmpty() else snoozeLabel, style = MaterialTheme.typography.titleMedium)
            }
        },
    ) {
        AriseCard(
            Modifier
                .then(if (focused) Modifier.border(2.dp, colors.brandAccent, MaterialTheme.shapes.medium) else Modifier)
                .combinedClickable(onClick = { if (selecting) onToggleSelect() else onChoose() }, onLongClick = onToggleSelect)
                .semantics {
                    customActions = listOfNotNull(
                        acceptLabel?.let { label -> CustomAccessibilityAction(label) { best?.let { onAccept(it.first) }; true } },
                        CustomAccessibilityAction(chooseLabel) { onChoose(); true },
                        CustomAccessibilityAction(snoozeLabel) { onSnooze(); true },
                    )
                },
        ) {
            Column(Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (selecting) Checkbox(checked = selected, onCheckedChange = { onToggleSelect() })
                    Thumbnail(item)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(item.name, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        Text(
                            Formatter.formatShortFileSize(context, item.size) +
                                if (days >= 1) " · " + pluralStringResource(R.plurals.review_waiting, days, days) else "",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (days >= 7) colors.warningText else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                Spacer(Modifier.size(12.dp))
                Text(
                    stringResource(R.string.review_best_guesses), style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    item.suggestions.forEachIndexed { i, (category, confidence) ->
                        SuggestionChip(
                            onClick = { onAccept(category) },
                            label = { Text("$category · ${(confidence * 100).toInt()}%") },
                            icon = if (i == 0) { { Icon(Icons.Outlined.CheckCircle, null, Modifier.size(16.dp)) } } else null,
                            colors = if (i == 0) {
                                SuggestionChipDefaults.suggestionChipColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
                            } else SuggestionChipDefaults.suggestionChipColors(),
                        )
                    }
                    AssistChip(onClick = onChoose, label = { Text(stringResource(R.string.review_more_folders)) })
                }
            }
        }
    }
}

/** Image or first-PDF-page preview, else the category icon. */
@Composable
private fun Thumbnail(item: ReviewItem) {
    val file = remember(item) { File(item.folder, item.relPath) }
    val isPdf = item.name.endsWith(".pdf", ignoreCase = true)
    val bitmap by produceState<Bitmap?>(null, file) {
        value = withContext(Dispatchers.IO) {
            runCatching { if (isPdf) pdfPage(file) else if (item.isImage) decodeSampled(file, 160) else null }.getOrNull()
        }
    }
    val image = bitmap
    if (image != null) {
        Image(
            image.asImageBitmap(), contentDescription = null, contentScale = ContentScale.Crop,
            modifier = Modifier.size(56.dp).clip(MaterialTheme.shapes.small),
        )
    } else {
        CategoryAvatar(item.predicted ?: "Others")
    }
}

private fun decodeSampled(file: File, target: Int): Bitmap? {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(file.path, bounds)
    if (bounds.outWidth <= 0) return null
    var sample = 1
    while (bounds.outWidth / (sample * 2) >= target && bounds.outHeight / (sample * 2) >= target) sample *= 2
    return BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = sample })
}

private fun pdfPage(file: File): Bitmap? {
    ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { fd ->
        PdfRenderer(fd).use { renderer ->
            if (renderer.pageCount == 0) return null
            renderer.openPage(0).use { page ->
                val scale = 160f / maxOf(page.width, page.height)
                val bmp = Bitmap.createBitmap(
                    (page.width * scale).toInt().coerceAtLeast(1), (page.height * scale).toInt().coerceAtLeast(1),
                    Bitmap.Config.ARGB_8888,
                )
                bmp.eraseColor(android.graphics.Color.WHITE)
                page.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                return bmp
            }
        }
    }
}
