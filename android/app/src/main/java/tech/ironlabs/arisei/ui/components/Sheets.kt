package tech.ironlabs.arisei.ui.components

import android.os.Environment
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Bolt
import androidx.compose.material.icons.outlined.CreateNewFolder
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.data.SortMode
import java.io.File

/** Pick a destination category, or type a new folder name. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CategorySheet(
    title: String,
    categories: List<String>,
    suggestions: List<Pair<String, Double>> = emptyList(),
    onDismiss: () -> Unit,
    onPick: (String) -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var creating by remember { mutableStateOf(false) }
    val reviewLabel = stringResource(R.string.nav_review)
    val shown = (suggestions.map { it.first } + categories).distinct()
        .filter { it != "__Review__" && it.contains(query.trim(), ignoreCase = true) }

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.navigationBarsPadding().padding(bottom = 16.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(horizontal = 24.dp))
            OutlinedTextField(
                value = query, onValueChange = { query = it }, singleLine = true,
                leadingIcon = { Icon(Icons.Outlined.Search, null) },
                placeholder = { Text(stringResource(R.string.plan_search_folders)) },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 12.dp),
            )
            LazyColumn(Modifier.heightIn(max = 420.dp)) {
                items(shown, key = { it }) { category ->
                    val confidence = suggestions.firstOrNull { it.first == category }?.second
                    ListItem(
                        headlineContent = { Text(displayCategory(category, reviewLabel)) },
                        leadingContent = { CategoryAvatar(category) },
                        trailingContent = if (confidence != null) {
                            { Text("${(confidence * 100).toInt()}%", style = MaterialTheme.typography.labelLarge) }
                        } else null,
                        colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                        modifier = Modifier.clickable { onPick(category) },
                    )
                }
                item {
                    ListItem(
                        headlineContent = { Text(stringResource(R.string.plan_new_folder)) },
                        leadingContent = { Icon(Icons.Outlined.CreateNewFolder, null) },
                        colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                        modifier = Modifier.clickable { creating = true },
                    )
                }
            }
        }
    }

    if (creating) {
        var name by remember { mutableStateOf(query.trim()) }
        AlertDialog(
            onDismissRequest = { creating = false },
            title = { Text(stringResource(R.string.plan_new_folder)) },
            text = { OutlinedTextField(value = name, onValueChange = { name = it }, singleLine = true) },
            confirmButton = {
                TextButton(enabled = name.isNotBlank(), onClick = { creating = false; onPick(name.trim()) }) {
                    Text(stringResource(R.string.action_create))
                }
            },
            dismissButton = { TextButton(onClick = { creating = false }) { Text(stringResource(R.string.action_cancel)) } },
        )
    }
}

/** Every 15 minutes vs Instantly, explained in the user's terms. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutoSortSheet(current: SortMode, onDismiss: () -> Unit, onPick: (SortMode) -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.navigationBarsPadding().padding(horizontal = 24.dp).padding(bottom = 24.dp).selectableGroup()) {
            Text(stringResource(R.string.autosort_sheet_title), style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.size(12.dp))
            listOf(
                Triple(SortMode.OFF, stringResource(R.string.autosort_off), null),
                Triple(SortMode.PERIODIC, stringResource(R.string.autosort_periodic), stringResource(R.string.autosort_sheet_periodic_body)),
                Triple(SortMode.LIVE, stringResource(R.string.autosort_live), stringResource(R.string.autosort_sheet_live_body)),
            ).forEach { (mode, label, body) ->
                Row(
                    Modifier.fillMaxWidth()
                        .selectable(selected = mode == current, role = Role.RadioButton, onClick = { onPick(mode) })
                        .padding(vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RadioButton(selected = mode == current, onClick = null)
                    Spacer(Modifier.size(12.dp))
                    Icon(
                        when (mode) { SortMode.LIVE -> Icons.Outlined.Bolt; else -> Icons.Outlined.Schedule },
                        null, tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.size(12.dp))
                    Column {
                        Text(label, style = MaterialTheme.typography.titleMedium)
                        body?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
            }
            Spacer(Modifier.size(8.dp))
            Text(
                stringResource(R.string.autosort_sheet_note), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * In-app folder browser.  With All files access we can list any folder, which
 * also sidesteps the system picker's refusal to hand out Download itself.
 */
@Composable
fun FolderPickerDialog(onDismiss: () -> Unit, onPick: (File) -> Unit) {
    val storageRoot = remember { Environment.getExternalStorageDirectory() }
    var current by remember { mutableStateOf(storageRoot) }
    val children = remember(current) {
        current.listFiles()?.filter { it.isDirectory && !it.name.startsWith(".") && it.name != "Android" }
            ?.sortedBy { it.name.lowercase() }.orEmpty()
    }
    val atRoot = current == storageRoot
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (!atRoot) {
                    IconButton(onClick = { current = current.parentFile ?: storageRoot }) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, stringResource(R.string.action_cancel))
                    }
                }
                Text(
                    if (atRoot) stringResource(R.string.folder_add) else current.name,
                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
            }
        },
        text = {
            Column {
                HorizontalDivider()
                LazyColumn(Modifier.heightIn(max = 360.dp), verticalArrangement = Arrangement.spacedBy(0.dp)) {
                    items(children, key = { it.path }) { dir ->
                        ListItem(
                            headlineContent = { Text(dir.name) },
                            leadingContent = { Icon(Icons.Outlined.Folder, null) },
                            colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh),
                            modifier = Modifier.clickable { current = dir },
                        )
                    }
                }
            }
        },
        confirmButton = {
            // The storage root itself is protected; pick a folder inside it.
            TextButton(enabled = !atRoot, onClick = { onPick(current) }) { Text(stringResource(R.string.action_continue)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.action_cancel)) } },
    )
}
