package tech.ironlabs.arisei.ui.screens

import android.text.format.DateUtils
import android.text.format.Formatter
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.HealthAndSafety
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.data.FolderHint
import tech.ironlabs.arisei.data.SortMode
import tech.ironlabs.arisei.data.WatchedFolder
import tech.ironlabs.arisei.engine.MoveState
import tech.ironlabs.arisei.engine.RecoveryReport
import tech.ironlabs.arisei.engine.RunKind
import tech.ironlabs.arisei.engine.RunView
import tech.ironlabs.arisei.ui.UiState
import tech.ironlabs.arisei.ui.components.AriseCard
import tech.ironlabs.arisei.ui.components.CategoryBars
import tech.ironlabs.arisei.ui.components.EmptyState
import tech.ironlabs.arisei.ui.components.KpiTile
import tech.ironlabs.arisei.ui.components.PulseDot
import tech.ironlabs.arisei.ui.components.SectionTitle
import tech.ironlabs.arisei.ui.theme.LocalAriseColors

@Composable
fun HomeScreen(
    state: UiState,
    contentPadding: PaddingValues,
    onSelectFolder: (String) -> Unit,
    onAddFolder: () -> Unit,
    onAutoSort: (WatchedFolder) -> Unit,
    onOrganize: () -> Unit,
    onOpenRun: (RunView) -> Unit,
    onSeeHistory: () -> Unit,
    onRequestAccess: () -> Unit,
    onDismissRecovered: () -> Unit,
) {
    val folder = state.settings.current
    val folderRuns = state.runs.filter { it.root == folder?.path && it.kind != RunKind.UNDO }
    val lastRun = folderRuns.firstOrNull { it.kind == RunKind.MANUAL || it.kind == RunKind.AUTO }
    val reviewFolder = "__Review__"

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 16.dp, end = 16.dp,
            top = contentPadding.calculateTopPadding() + 8.dp,
            bottom = contentPadding.calculateBottomPadding() + 24.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Column(Modifier.padding(top = 8.dp, bottom = 4.dp)) {
                Text(stringResource(R.string.home_title), style = MaterialTheme.typography.headlineMedium)
                Text(
                    stringResource(R.string.home_subtitle), style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (!state.hasAccess) {
            item { PermissionCard(onRequestAccess) }
        }
        if (state.recovered.isNotEmpty()) {
            item { RecoveredCard(state.recovered, onDismissRecovered) }
        }
        item {
            FolderSwitcher(state.settings.folders, folder?.path, onSelectFolder, onAddFolder)
        }
        if (folder != null) {
            item { FolderCard(folder, state.hint, onAutoSort = { onAutoSort(folder) }) }
            item {
                Button(
                    onClick = onOrganize,
                    enabled = state.hasAccess && state.hint !is FolderHint.Protected && state.hint !is FolderHint.Missing,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                ) {
                    Icon(Icons.Outlined.AutoAwesome, null)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.action_organize), style = MaterialTheme.typography.titleMedium)
                }
            }
            if (lastRun != null) {
                item { LastRunCard(lastRun, reviewFolder, onClick = { onOpenRun(lastRun) }) }
            } else {
                item {
                    EmptyState(
                        Icons.Outlined.Inventory2, stringResource(R.string.home_empty_title),
                        stringResource(R.string.home_empty_body),
                    )
                }
            }
            if (folderRuns.isNotEmpty()) {
                item {
                    SectionTitle(stringResource(R.string.recent_activity)) {
                        TextButton(onClick = onSeeHistory) { Text(stringResource(R.string.see_all)) }
                    }
                }
                items(folderRuns.take(5), key = { it.id }) { run -> RunRow(run, onClick = { onOpenRun(run) }) }
            }
        }
    }
}

@Composable
private fun FolderSwitcher(
    folders: List<WatchedFolder>,
    selected: String?,
    onSelect: (String) -> Unit,
    onAdd: () -> Unit,
) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(folders, key = { it.path }) { f ->
            FilterChip(
                selected = f.path == selected,
                onClick = { onSelect(f.path) },
                label = { Text(f.displayName) },
                leadingIcon = { Icon(Icons.Outlined.Folder, null, Modifier.size(18.dp)) },
            )
        }
        item {
            AssistChip(
                onClick = onAdd,
                label = { Text(stringResource(R.string.folder_add)) },
                leadingIcon = { Icon(Icons.Outlined.Add, null, Modifier.size(18.dp)) },
            )
        }
    }
}

@Composable
private fun FolderCard(folder: WatchedFolder, hint: FolderHint, onAutoSort: () -> Unit) {
    val colors = LocalAriseColors.current
    AriseCard {
        Column(Modifier.padding(16.dp)) {
            Text(folder.displayName, style = MaterialTheme.typography.titleLarge)
            Text(
                folder.path, style = MaterialTheme.typography.bodySmall, maxLines = 1,
                overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(10.dp))
            val (text, color) = when (hint) {
                is FolderHint.Loose -> pluralStringResource(R.plurals.folder_hint_loose, hint.count, hint.count) to
                    MaterialTheme.colorScheme.onSurface
                FolderHint.Tidy -> "✓ " + stringResource(R.string.folder_hint_tidy) to colors.successText
                FolderHint.Protected -> stringResource(R.string.folder_hint_protected) to colors.warningText
                FolderHint.Missing -> stringResource(R.string.folder_hint_missing) to MaterialTheme.colorScheme.error
                FolderHint.Unknown -> "" to MaterialTheme.colorScheme.onSurface
            }
            if (text.isNotEmpty()) {
                Text(
                    text, style = MaterialTheme.typography.bodyLarge, color = color,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
            Spacer(Modifier.height(12.dp))
            Row(
                Modifier.fillMaxWidth().clickable(onClick = onAutoSort).padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                PulseDot(active = folder.mode != SortMode.OFF)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.autosort_label), style = MaterialTheme.typography.titleMedium)
                    val modeLabel = when (folder.mode) {
                        SortMode.OFF -> stringResource(R.string.autosort_off)
                        SortMode.PERIODIC -> stringResource(R.string.autosort_periodic)
                        SortMode.LIVE -> stringResource(R.string.autosort_live)
                    }
                    Text(
                        if (folder.mode == SortMode.OFF) modeLabel
                        else stringResource(R.string.autosort_watching, folder.displayName, modeLabel),
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(checked = folder.mode != SortMode.OFF, onCheckedChange = { onAutoSort() })
            }
        }
    }
}

@Composable
private fun LastRunCard(run: RunView, reviewFolder: String, onClick: () -> Unit) {
    val context = LocalContext.current
    val moved = run.moves.filter { it.state == MoveState.MOVED }
    val toReview = moved.count { it.spec.category == reviewFolder }
    val bytes = moved.sumOf { it.spec.size }
    val counts = moved.filter { it.spec.category != reviewFolder }
        .groupingBy { it.spec.category }.eachCount().entries
        .sortedByDescending { it.value }.take(10).map { it.key to it.value }
    val narrow = LocalConfiguration.current.fontScale > 1.5f

    AriseCard(Modifier.clickable(onClick = onClick)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.last_run), style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                Text(
                    DateUtils.getRelativeTimeSpanString(run.startedAt).toString(),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            val tiles = listOf(
                Kpi(stringResource(R.string.kpi_moved), moved.size - toReview),
                Kpi(stringResource(R.string.kpi_review), toReview),
                Kpi(stringResource(R.string.kpi_failed), run.count(MoveState.FAILED)),
                Kpi(stringResource(R.string.kpi_space), (bytes / 1024).toInt()) { kb ->
                    Formatter.formatShortFileSize(context, kb * 1024L)
                },
            )
            // 2×2 grid; one column at very large font sizes.
            if (narrow) {
                tiles.forEach { KpiTile(it.label, it.value, Modifier.fillMaxWidth(), it.format) }
            } else {
                tiles.chunked(2).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        row.forEach { KpiTile(it.label, it.value, Modifier.weight(1f), it.format) }
                    }
                }
            }
            if (counts.isNotEmpty()) CategoryBars(counts)
        }
    }
}

private data class Kpi(val label: String, val value: Int, val format: (Int) -> String = { it.toString() })

@Composable
private fun PermissionCard(onRequestAccess: () -> Unit) {
    AriseCard {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Lock, null, tint = MaterialTheme.colorScheme.error)
                Spacer(Modifier.width(10.dp))
                Text(stringResource(R.string.perm_denied_title), style = MaterialTheme.typography.titleMedium)
            }
            Spacer(Modifier.height(6.dp))
            Text(stringResource(R.string.perm_denied_body), style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(12.dp))
            Button(onClick = onRequestAccess) { Text(stringResource(R.string.action_allow_access)) }
        }
    }
}

@Composable
private fun RecoveredCard(reports: List<RecoveryReport>, onDismiss: () -> Unit) {
    val restored = reports.sumOf { it.restored }
    AriseCard {
        ListItem(
            headlineContent = { Text(stringResource(R.string.recovered_title)) },
            supportingContent = { Text(pluralStringResource(R.plurals.recovered_body, restored, restored)) },
            leadingContent = { Icon(Icons.Outlined.HealthAndSafety, null, tint = LocalAriseColors.current.success) },
            trailingContent = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.action_dismiss)) } },
            colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest),
        )
    }
}
