package tech.ironlabs.arisei.ui.screens

import android.text.format.DateFormat
import android.text.format.DateUtils
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Undo
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Bolt
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.outlined.TravelExplore
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.engine.MoveState
import tech.ironlabs.arisei.engine.MoveView
import tech.ironlabs.arisei.engine.RunKind
import tech.ironlabs.arisei.engine.RunState
import tech.ironlabs.arisei.engine.RunView
import tech.ironlabs.arisei.ui.components.AriseCard
import tech.ironlabs.arisei.ui.components.CategoryAvatar
import tech.ironlabs.arisei.ui.components.EmptyState
import tech.ironlabs.arisei.ui.components.FolderPickerDialog
import tech.ironlabs.arisei.ui.theme.LocalAriseColors
import java.io.File
import java.util.Calendar

/** Runs grouped by day; undo runs are folded into the runs they undid. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun HistoryScreen(runs: List<RunView>, contentPadding: PaddingValues, onOpen: (RunView) -> Unit) {
    val visible = runs.filter { it.kind != RunKind.UNDO && it.moves.isNotEmpty() }
    if (visible.isEmpty()) {
        Box(Modifier.fillMaxSize().padding(contentPadding)) {
            EmptyState(
                Icons.Outlined.History, stringResource(R.string.history_empty_title),
                stringResource(R.string.history_empty_body), Modifier.align(Alignment.Center),
            )
        }
        return
    }
    val today = stringResource(R.string.today)
    val yesterday = stringResource(R.string.yesterday)
    val context = LocalContext.current
    val byDay = visible.groupBy { dayLabel(it.startedAt, today, yesterday, context) }
    LazyColumn(
        contentPadding = PaddingValues(16.dp, contentPadding.calculateTopPadding() + 8.dp, 16.dp, contentPadding.calculateBottomPadding() + 24.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item { Text(stringResource(R.string.history_title), style = MaterialTheme.typography.headlineMedium) }
        byDay.forEach { (day, dayRuns) ->
            stickyHeader(key = "d:$day") {
                Surface(color = MaterialTheme.colorScheme.surface, modifier = Modifier.fillMaxWidth()) {
                    Text(
                        day, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 6.dp),
                    )
                }
            }
            items(dayRuns, key = { it.id }) { run -> RunRow(run, onClick = { onOpen(run) }) }
        }
    }
}

private fun dayLabel(ms: Long, today: String, yesterday: String, context: android.content.Context): String {
    val day = Calendar.getInstance().apply { timeInMillis = ms }
    val now = Calendar.getInstance()
    fun same(a: Calendar, b: Calendar) = a.get(Calendar.YEAR) == b.get(Calendar.YEAR) && a.get(Calendar.DAY_OF_YEAR) == b.get(Calendar.DAY_OF_YEAR)
    if (same(day, now)) return today
    now.add(Calendar.DAY_OF_YEAR, -1)
    if (same(day, now)) return yesterday
    return DateUtils.formatDateTime(context, ms, DateUtils.FORMAT_SHOW_DATE or DateUtils.FORMAT_SHOW_WEEKDAY)
}

@Composable
private fun kindLabel(kind: RunKind) = stringResource(
    when (kind) {
        RunKind.MANUAL -> R.string.kind_manual
        RunKind.AUTO -> R.string.kind_auto
        RunKind.REVIEW -> R.string.kind_review
        RunKind.UNDO -> R.string.kind_undo
    },
)

private fun kindIcon(kind: RunKind): ImageVector = when (kind) {
    RunKind.MANUAL -> Icons.Outlined.AutoAwesome
    RunKind.AUTO -> Icons.Outlined.Bolt
    RunKind.REVIEW -> Icons.Outlined.Inbox
    RunKind.UNDO -> Icons.AutoMirrored.Outlined.Undo
}

/** Status chip text and colour for a run. */
@Composable
private fun runStatus(run: RunView): Pair<String, Color> {
    val colors = LocalAriseColors.current
    val moved = run.count(MoveState.MOVED)
    val undone = run.count(MoveState.UNDONE)
    val failed = run.count(MoveState.FAILED)
    return when {
        run.state == RunState.RECOVERED -> stringResource(R.string.status_interrupted) to colors.warningText
        undone > 0 && moved == 0 -> stringResource(R.string.status_undone) to MaterialTheme.colorScheme.onSurfaceVariant
        undone > 0 -> stringResource(R.string.status_partly_undone) to MaterialTheme.colorScheme.onSurfaceVariant
        failed > 0 -> pluralStringResource(R.plurals.status_failed, failed, failed) to MaterialTheme.colorScheme.error
        run.state == RunState.ABORTED -> stringResource(R.string.status_stopped) to colors.warningText
        else -> stringResource(R.string.status_done) to colors.successText
    }
}

@Composable
fun RunRow(run: RunView, onClick: () -> Unit) {
    val context = LocalContext.current
    val (status, statusColor) = runStatus(run)
    val time = DateFormat.getTimeFormat(context).format(java.util.Date(run.startedAt))
    AriseCard(Modifier.clickable(onClick = onClick)) {
        ListItem(
            leadingContent = { Icon(kindIcon(run.kind), null, tint = MaterialTheme.colorScheme.primary) },
            headlineContent = { Text("${kindLabel(run.kind)} · ${pluralStringResource(R.plurals.file_count, run.moves.size, run.moves.size)}") },
            supportingContent = { Text("$time · ${File(run.root).name}", maxLines = 1, overflow = TextOverflow.Ellipsis) },
            trailingContent = { Text(status, style = MaterialTheme.typography.labelLarge, color = statusColor) },
            colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest),
        )
    }
}

/** Every file in a run, with per-file and whole-run undo. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RunDetailScreen(
    run: RunView,
    onBack: () -> Unit,
    onUndo: (Set<Int>?) -> Unit,
    onRelocate: (File) -> Unit,
) {
    var confirming by remember { mutableStateOf(false) }
    var locating by remember { mutableStateOf(false) }
    val undoable = run.moves.filter { it.state == MoveState.MOVED }
    val folderMissing = !run.rootDir.isDirectory

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.run_detail_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, stringResource(R.string.action_cancel)) }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface),
            )
        },
        bottomBar = {
            if (run.isUndoable && !folderMissing) {
                Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest, shadowElevation = 8.dp) {
                    Button(
                        onClick = { confirming = true },
                        modifier = Modifier.fillMaxWidth().padding(16.dp).height(52.dp),
                    ) {
                        Icon(Icons.AutoMirrored.Outlined.Undo, null)
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.action_undo_run))
                    }
                }
            }
        },
    ) { padding ->
        LazyColumn(contentPadding = padding) {
            item {
                Column(Modifier.padding(16.dp)) {
                    Text(
                        "${kindLabel(run.kind)} · ${DateUtils.getRelativeTimeSpanString(run.startedAt)}",
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Text(run.root, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            if (folderMissing) {
                item {
                    AriseCard(Modifier.padding(horizontal = 16.dp)) {
                        Column(Modifier.padding(16.dp)) {
                            Text(stringResource(R.string.folder_moved_title), style = MaterialTheme.typography.titleMedium)
                            Text(stringResource(R.string.folder_moved_body, run.rootDir.name), style = MaterialTheme.typography.bodyMedium)
                            Spacer(Modifier.height(8.dp))
                            OutlinedButton(onClick = { locating = true }) {
                                Icon(Icons.Outlined.TravelExplore, null)
                                Spacer(Modifier.width(6.dp))
                                Text(stringResource(R.string.action_locate))
                            }
                        }
                    }
                }
            }
            items(run.moves, key = { it.spec.id }) { move ->
                MoveRow(move, canUndo = move.state == MoveState.MOVED && !folderMissing, onUndo = { onUndo(setOf(move.spec.id)) })
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
        }
    }

    if (confirming) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            title = { Text(stringResource(R.string.undo_run_confirm_title, undoable.size)) },
            text = { Text(stringResource(R.string.undo_run_confirm_body)) },
            confirmButton = {
                TextButton(onClick = { confirming = false; onUndo(null) }) { Text(stringResource(R.string.action_put_back)) }
            },
            dismissButton = { TextButton(onClick = { confirming = false }) { Text(stringResource(R.string.action_keep)) } },
        )
    }
    if (locating) FolderPickerDialog(onDismiss = { locating = false }, onPick = { locating = false; onRelocate(it) })
}

@Composable
private fun MoveRow(move: MoveView, canUndo: Boolean, onUndo: () -> Unit) {
    val colors = LocalAriseColors.current
    val (label, color) = when (move.state) {
        MoveState.MOVED -> stringResource(R.string.state_moved) to colors.successText
        MoveState.UNDONE -> stringResource(R.string.state_undone) to MaterialTheme.colorScheme.onSurfaceVariant
        MoveState.FAILED -> stringResource(R.string.state_failed) to MaterialTheme.colorScheme.error
        MoveState.SKIPPED -> stringResource(R.string.state_skipped) to MaterialTheme.colorScheme.onSurfaceVariant
        MoveState.PLANNED, MoveState.IN_FLIGHT -> stringResource(R.string.state_pending) to MaterialTheme.colorScheme.onSurfaceVariant
    }
    ListItem(
        leadingContent = { CategoryAvatar(move.spec.category) },
        headlineContent = { Text(File(move.spec.src).name, maxLines = 2, overflow = TextOverflow.Ellipsis) },
        supportingContent = {
            Column {
                Text("→ ${File(move.spec.dst).parent ?: ""}", maxLines = 1, overflow = TextOverflow.Ellipsis)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(label, color = color, style = MaterialTheme.typography.labelMedium)
                    move.error?.let { Text(" · $it", style = MaterialTheme.typography.labelMedium, maxLines = 1) }
                }
            }
        },
        trailingContent = if (canUndo) {
            { IconButton(onClick = onUndo) { Icon(Icons.AutoMirrored.Outlined.Undo, stringResource(R.string.action_undo)) } }
        } else null,
    )
}
