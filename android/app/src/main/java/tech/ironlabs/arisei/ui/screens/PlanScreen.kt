package tech.ironlabs.arisei.ui.screens

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.FolderOff
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.engine.PlanItem
import tech.ironlabs.arisei.engine.Rules
import tech.ironlabs.arisei.engine.SkipReason
import tech.ironlabs.arisei.ui.PlanError
import tech.ironlabs.arisei.ui.PlanUi
import tech.ironlabs.arisei.ui.components.CategoryAvatar
import tech.ironlabs.arisei.ui.components.CategorySheet
import tech.ironlabs.arisei.ui.components.ConfidenceChip
import tech.ironlabs.arisei.ui.components.EmptyState
import tech.ironlabs.arisei.ui.components.displayCategory
import tech.ironlabs.arisei.ui.theme.LocalAriseColors

/** Every pending move, grouped by destination — nothing moves until the user says so. */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun PlanScreen(
    ui: PlanUi,
    categories: List<String>,
    onClose: () -> Unit,
    onToggle: (String, Boolean) -> Unit,
    onOverride: (String, String) -> Unit,
    onRun: () -> Unit,
    onStop: () -> Unit,
    onRetry: () -> Unit,
) {
    val rules = Rules.bundled
    val reviewLabel = stringResource(R.string.nav_review)
    var editing by remember { mutableStateOf<PlanItem?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.plan_title) + " · " + ui.folder.displayName) },
                navigationIcon = {
                    if (!ui.running) IconButton(onClick = onClose) { Icon(Icons.Outlined.Close, stringResource(R.string.action_cancel)) }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface),
            )
        },
        bottomBar = {
            val plan = ui.plan
            if (plan != null && plan.items.isNotEmpty()) {
                PlanBottomBar(
                    count = plan.included.size, folders = plan.folderCount,
                    running = ui.running, done = ui.done, total = ui.total,
                    onRun = onRun, onStop = onStop,
                )
            }
        },
    ) { padding ->
        val plan = ui.plan
        when {
            ui.error == PlanError.PROTECTED -> EmptyState(
                Icons.Outlined.Lock, stringResource(R.string.folder_hint_protected), "", Modifier.padding(padding),
            )
            ui.error != null -> EmptyState(
                Icons.Outlined.FolderOff, stringResource(R.string.folder_hint_missing), ui.folder.path,
                Modifier.padding(padding), stringResource(R.string.action_check_again), onRetry,
            )
            plan == null -> Column(
                Modifier.fillMaxSize().padding(padding), horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                CircularProgressIndicator()
                Spacer(Modifier.height(16.dp))
                Text(stringResource(R.string.plan_scanning, ui.folder.displayName))
            }
            plan.items.isEmpty() -> EmptyState(
                Icons.Outlined.Inventory2, stringResource(R.string.plan_empty_title),
                stringResource(R.string.plan_empty_body), Modifier.padding(padding),
                stringResource(R.string.action_check_again), onRetry,
            )
            else -> {
                val groups = plan.items.groupBy { it.destDir }
                    .entries.sortedWith(compareBy({ it.key == rules.reviewFolder }, { it.key.lowercase() }))
                LazyColumn(contentPadding = PaddingValues(bottom = 16.dp), modifier = Modifier.padding(padding)) {
                    groups.forEach { (dest, items) ->
                        stickyHeader(key = "h:$dest") {
                            GroupHeader(
                                if (dest == rules.reviewFolder) stringResource(R.string.plan_going_to_review)
                                else displayCategory(dest, reviewLabel),
                                items.count { it.included },
                            )
                        }
                        if (dest == rules.reviewFolder) {
                            item(key = "note") {
                                Text(
                                    stringResource(R.string.plan_review_note), style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                                )
                            }
                        }
                        items(items, key = { "i:${it.name}" }) { item ->
                            PlanRow(
                                item, rules, reviewLabel, enabled = !ui.running,
                                onToggle = { onToggle(item.name, it) }, onClick = { editing = item },
                            )
                        }
                    }
                    if (plan.skipped.isNotEmpty()) {
                        stickyHeader(key = "skipped") { GroupHeader(stringResource(R.string.plan_skipped), plan.skipped.size) }
                        items(plan.skipped, key = { "s:${it.name}" }) { s ->
                            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                                Text(s.name, Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(skipLabel(s.reason), style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }

    editing?.let { item ->
        CategorySheet(
            title = item.name,
            categories = categories,
            suggestions = (listOf(item.result.category to item.result.confidence) + item.result.alternatives)
                .filter { it.first != rules.reviewFolder },
            onDismiss = { editing = null },
            onPick = { onOverride(item.name, it); editing = null },
        )
    }
}

@Composable
private fun skipLabel(reason: SkipReason) = stringResource(
    when (reason) {
        SkipReason.HIDDEN, SkipReason.OWN -> R.string.skip_hidden
        SkipReason.SYSTEM -> R.string.skip_system
        SkipReason.LOCK -> R.string.skip_lock
        SkipReason.PARTIAL -> R.string.skip_partial
    },
)

@Composable
private fun GroupHeader(title: String, count: Int) {
    Surface(color = MaterialTheme.colorScheme.surface) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("$title · $count", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun PlanRow(
    item: PlanItem,
    rules: Rules,
    reviewLabel: String,
    enabled: Boolean,
    onToggle: (Boolean) -> Unit,
    onClick: () -> Unit,
) {
    val badge = item.result.badge(rules)
    val dest = displayCategory(item.destDir, reviewLabel)
    val description = stringResource(
        R.string.row_description, item.name, dest, badge.name.lowercase(), (item.result.confidence * 100).toInt(),
    )
    val includeLabel = stringResource(R.string.plan_include, item.name)
    Row(
        Modifier.fillMaxWidth()
            .clickable(enabled = enabled, onClick = onClick)
            .background(MaterialTheme.colorScheme.surfaceContainerLowest)
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(
            checked = item.included, onCheckedChange = onToggle, enabled = enabled,
            modifier = Modifier.semantics { contentDescription = includeLabel },
        )
        CategoryAvatar(if (item.destDir == rules.reviewFolder) rules.reviewFolder else item.category)
        Spacer(Modifier.width(12.dp))
        Column(
            Modifier.weight(1f).clearAndSetSemantics { contentDescription = description },
        ) {
            Text(
                item.name, style = MaterialTheme.typography.bodyLarge, maxLines = 2, overflow = TextOverflow.Ellipsis,
                color = if (item.included) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "→ $dest", style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f, fill = false),
                )
                Spacer(Modifier.width(8.dp))
                if (!item.overridden) ConfidenceChip(badge, item.result.confidence)
            }
        }
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable
private fun PlanBottomBar(
    count: Int,
    folders: Int,
    running: Boolean,
    done: Int,
    total: Int,
    onRun: () -> Unit,
    onStop: () -> Unit,
) {
    Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest, shadowElevation = 8.dp) {
        Column(Modifier.navigationBarsPadding().padding(16.dp)) {
            if (running) {
                val progress = if (total == 0) 0f else done.toFloat() / total
                LinearProgressIndicator(
                    progress = { progress }, color = LocalAriseColors.current.brandAccent,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        stringResource(R.string.plan_progress, done, total),
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.weight(1f).semantics { liveRegion = LiveRegionMode.Polite },
                    )
                    OutlinedButton(onClick = onStop) { Text(stringResource(R.string.action_stop)) }
                }
            } else {
                Text(
                    pluralStringResource(R.plurals.plan_summary, count, count, pluralStringResource(R.plurals.plan_folders, folders, folders)),
                    style = MaterialTheme.typography.titleMedium,
                )
                Spacer(Modifier.height(8.dp))
                Button(onClick = onRun, enabled = count > 0, modifier = Modifier.fillMaxWidth().height(52.dp)) {
                    Text(pluralStringResource(R.plurals.plan_organize, count, count))
                }
                Box(Modifier.fillMaxWidth().padding(top = 8.dp), contentAlignment = Alignment.Center) {
                    Text(
                        stringResource(R.string.plan_footer), style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
