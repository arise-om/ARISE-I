package tech.ironlabs.arisei.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Bolt
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import tech.ironlabs.arisei.BuildConfig
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.data.SortMode
import tech.ironlabs.arisei.data.ThemeMode
import tech.ironlabs.arisei.data.WatchedFolder
import tech.ironlabs.arisei.ui.UiState
import tech.ironlabs.arisei.ui.components.AriseCard
import tech.ironlabs.arisei.ui.components.SectionTitle
import kotlin.math.roundToInt

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    state: UiState,
    contentPadding: PaddingValues,
    onAutoSort: (WatchedFolder) -> Unit,
    onThreshold: (String, Double) -> Unit,
    onPreviewThreshold: (String, Double) -> Unit,
    onRemoveFolder: (String) -> Unit,
    onTheme: (ThemeMode) -> Unit,
    onDynamicColor: (Boolean) -> Unit,
    onReduceMotion: (Boolean) -> Unit,
    onRetrain: () -> Unit,
    onResetLearning: () -> Unit,
) {
    val s = state.settings
    var confirmReset by remember { mutableStateOf(false) }
    val itemColors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest)

    LazyColumn(
        contentPadding = PaddingValues(16.dp, contentPadding.calculateTopPadding() + 8.dp, 16.dp, contentPadding.calculateBottomPadding() + 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item { Text(stringResource(R.string.settings_title), style = MaterialTheme.typography.headlineMedium) }

        item { SectionTitle(stringResource(R.string.settings_folders)) }
        s.folders.forEach { folder ->
            item(key = folder.path) {
                FolderSettings(folder, state, onAutoSort, onThreshold, onPreviewThreshold, onRemoveFolder)
            }
        }

        item { SectionTitle(stringResource(R.string.settings_appearance)) }
        item {
            AriseCard {
                Column(Modifier.padding(vertical = 8.dp)) {
                    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                        val modes = listOf(
                            ThemeMode.SYSTEM to R.string.theme_system,
                            ThemeMode.LIGHT to R.string.theme_light,
                            ThemeMode.DARK to R.string.theme_dark,
                        )
                        modes.forEachIndexed { i, (mode, label) ->
                            SegmentedButton(
                                selected = s.theme == mode, onClick = { onTheme(mode) },
                                shape = SegmentedButtonDefaults.itemShape(i, modes.size),
                            ) { Text(stringResource(label)) }
                        }
                    }
                    ListItem(
                        headlineContent = { Text(stringResource(R.string.settings_dynamic_color)) },
                        supportingContent = { Text(stringResource(R.string.settings_dynamic_color_body)) },
                        trailingContent = { Switch(checked = s.dynamicColor, onCheckedChange = onDynamicColor) },
                        colors = itemColors,
                    )
                    ListItem(
                        headlineContent = { Text(stringResource(R.string.settings_reduce_motion)) },
                        supportingContent = { Text(stringResource(R.string.settings_reduce_motion_body)) },
                        trailingContent = { Switch(checked = s.reduceMotion, onCheckedChange = onReduceMotion) },
                        colors = itemColors,
                    )
                }
            }
        }

        item { SectionTitle(stringResource(R.string.settings_intelligence)) }
        item {
            val stats = state.stats
            AriseCard {
                Column(Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Psychology, null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.padding(start = 10.dp))
                        Column {
                            Text(
                                stringResource(R.string.settings_learning_stats, stats.events, (stats.correctionRate * 100).roundToInt()),
                                style = MaterialTheme.typography.titleMedium,
                            )
                            Text(
                                stats.trainedOn?.let { stringResource(R.string.settings_model_trained, it) }
                                    ?: stringResource(R.string.settings_model_untrained, 20),
                                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = onRetrain) { Text(stringResource(R.string.action_retrain)) }
                        TextButton(onClick = { confirmReset = true }) {
                            Text(stringResource(R.string.action_reset_learning), color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }
        }

        item { SectionTitle(stringResource(R.string.settings_about)) }
        item {
            Text(
                stringResource(R.string.settings_version, BuildConfig.VERSION_NAME),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

    if (confirmReset) {
        AlertDialog(
            onDismissRequest = { confirmReset = false },
            title = { Text(stringResource(R.string.reset_confirm_title)) },
            text = { Text(stringResource(R.string.reset_confirm_body)) },
            confirmButton = {
                TextButton(onClick = { confirmReset = false; onResetLearning() }) {
                    Text(stringResource(R.string.action_reset), color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(onClick = { confirmReset = false }) { Text(stringResource(R.string.action_cancel)) } },
        )
    }
}

@Composable
private fun FolderSettings(
    folder: WatchedFolder,
    state: UiState,
    onAutoSort: (WatchedFolder) -> Unit,
    onThreshold: (String, Double) -> Unit,
    onPreviewThreshold: (String, Double) -> Unit,
    onRemove: (String) -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    var value by remember(folder.path) { mutableFloatStateOf(folder.threshold.toFloat()) }
    val isCurrent = state.settings.current?.path == folder.path
    LaunchedEffect(folder.path) { if (isCurrent) onPreviewThreshold(folder.path, folder.threshold) }
    val itemColors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest)

    AriseCard {
        Column(Modifier.padding(vertical = 4.dp)) {
            ListItem(
                leadingContent = { Icon(Icons.Outlined.Folder, null) },
                headlineContent = { Text(folder.displayName) },
                supportingContent = { Text(folder.path, maxLines = 1) },
                trailingContent = {
                    IconButton(onClick = { onRemove(folder.path) }) {
                        Icon(Icons.Outlined.DeleteOutline, stringResource(R.string.settings_remove_folder))
                    }
                },
                colors = itemColors,
            )
            ListItem(
                leadingContent = { Icon(if (folder.mode == SortMode.LIVE) Icons.Outlined.Bolt else Icons.Outlined.Schedule, null) },
                headlineContent = { Text(stringResource(R.string.autosort_label)) },
                supportingContent = {
                    Text(
                        stringResource(
                            when (folder.mode) {
                                SortMode.OFF -> R.string.autosort_off
                                SortMode.PERIODIC -> R.string.autosort_periodic
                                SortMode.LIVE -> R.string.autosort_live
                            },
                        ),
                    )
                },
                colors = itemColors,
                modifier = Modifier.clickable { onAutoSort(folder) },
            )
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(
                    "${stringResource(R.string.settings_threshold)}: ${(value * 100).roundToInt()} %",
                    style = MaterialTheme.typography.titleSmall,
                )
                Slider(
                    value = value,
                    onValueChange = {
                        val stepped = (it * 20).roundToInt() / 20f
                        if (stepped != value) haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        value = stepped
                        onPreviewThreshold(folder.path, stepped.toDouble())
                    },
                    onValueChangeFinished = { onThreshold(folder.path, value.toDouble()) },
                    valueRange = 0.5f..0.95f,
                    steps = 8,
                )
                val preview = state.thresholdPreview
                if (isCurrent && preview != null) {
                    Text(
                        stringResource(R.string.settings_threshold_preview, (value * 100).roundToInt(), preview.first, preview.second),
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    stringResource(
                        if (state.customCategories && isCurrent) R.string.settings_categories_custom else R.string.settings_categories_default,
                    ),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }
    }
}
