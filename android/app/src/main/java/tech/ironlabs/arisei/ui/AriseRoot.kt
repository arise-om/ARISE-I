package tech.ironlabs.arisei.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.isCtrlPressed
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.data.SortMode
import tech.ironlabs.arisei.data.WatchedFolder
import tech.ironlabs.arisei.platform.Permissions
import tech.ironlabs.arisei.repository
import tech.ironlabs.arisei.ui.components.AutoSortSheet
import tech.ironlabs.arisei.ui.components.FolderPickerDialog
import tech.ironlabs.arisei.ui.screens.HistoryScreen
import tech.ironlabs.arisei.ui.screens.HomeScreen
import tech.ironlabs.arisei.ui.screens.OnboardingScreen
import tech.ironlabs.arisei.ui.screens.PlanScreen
import tech.ironlabs.arisei.ui.screens.ReviewScreen
import tech.ironlabs.arisei.ui.screens.RunDetailScreen
import tech.ironlabs.arisei.ui.screens.SettingsScreen
import tech.ironlabs.arisei.ui.screens.rememberAccessRequester
import tech.ironlabs.arisei.ui.theme.AriseTokens
import tech.ironlabs.arisei.ui.theme.LocalReduceMotion

enum class Tab(val label: Int, val icon: ImageVector) {
    HOME(R.string.nav_home, Icons.Outlined.Home),
    REVIEW(R.string.nav_review, Icons.Outlined.Inbox),
    HISTORY(R.string.nav_history, Icons.Outlined.History),
    SETTINGS(R.string.nav_settings, Icons.Outlined.Settings),
}

@Composable
fun AriseRoot(vm: AriseViewModel, requestedTab: Tab?, onTabConsumed: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val snackbarHost = remember { SnackbarHostState() }
    var tab by rememberSaveable { mutableStateOf(Tab.HOME) }
    var openRunId by rememberSaveable { mutableStateOf<Long?>(null) }
    var autoSortFor by remember { mutableStateOf<WatchedFolder?>(null) }
    var addingFolder by remember { mutableStateOf(false) }
    val requestAccess = rememberAccessRequester { vm.refresh() }
    val notificationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    val undoLabel = stringResource(R.string.action_undo)
    val retryLabel = stringResource(R.string.action_retry)
    val reduce = LocalReduceMotion.current

    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.refresh() }
    LaunchedEffect(requestedTab) {
        if (requestedTab != null) { tab = requestedTab; openRunId = null; onTabConsumed() }
    }
    LaunchedEffect(Unit) {
        vm.snackbar.collect { snack ->
            val action = when {
                snack.undoRun != null -> undoLabel
                snack.retry -> retryLabel
                else -> null
            }
            val result = snackbarHost.showSnackbar(
                snack.message, actionLabel = action,
                duration = if (action != null) SnackbarDuration.Long else SnackbarDuration.Short,
            )
            if (result == SnackbarResult.ActionPerformed) {
                val run = snack.undoRun
                if (run != null) vm.undo(run) else if (snack.retry) vm.startPlan()
            }
        }
    }

    if (!state.settings.onboardingDone) {
        OnboardingScreen(
            hasAccess = state.hasAccess,
            defaultFolder = AriseViewModel.defaultFolder,
            onRequestAccess = requestAccess,
            onFinish = vm::completeOnboarding,
            onSkip = vm::skipOnboarding,
        )
        return
    }

    val plan = state.plan
    if (plan != null) {
        BackHandler { vm.closePlan() }
        PlanScreen(
            ui = plan, categories = state.categories,
            onClose = vm::closePlan, onToggle = vm::setIncluded, onOverride = vm::overrideCategory,
            onRun = vm::runPlan, onStop = vm::stopRun, onRetry = vm::startPlan,
        )
        return
    }

    val openRun = openRunId?.let { id -> state.runs.firstOrNull { it.id == id } }
    if (openRun != null) {
        BackHandler { openRunId = null }
        RunDetailScreen(
            run = openRun, onBack = { openRunId = null },
            onUndo = { ids -> vm.undo(openRun.id, ids) },
            onRelocate = { dir -> vm.relocate(openRun.id, dir) },
        )
        return
    }

    val pickAutoSort: (WatchedFolder) -> Unit = { autoSortFor = it }
    val wide = LocalConfiguration.current.screenWidthDp >= 600
    val reviewCount = state.review.size

    @Composable
    fun TabIcon(t: Tab) {
        if (t == Tab.REVIEW && reviewCount > 0) {
            BadgedBox(badge = {
                Badge { Text(if (reviewCount > 99) stringResource(R.string.badge_overflow) else reviewCount.toString()) }
            }) { Icon(t.icon, null) }
        } else {
            Icon(t.icon, null)
        }
    }

    @Composable
    fun Content(padding: PaddingValues) {
        AnimatedContent(
            targetState = tab,
            transitionSpec = {
                val d = if (reduce) 0 else AriseTokens.Motion.SCREEN
                fadeIn(tween(d)) togetherWith fadeOut(tween(d))
            },
            label = "tab",
        ) { t ->
            when (t) {
                Tab.HOME -> HomeScreen(
                    state = state, contentPadding = padding,
                    onSelectFolder = vm::selectFolder, onAddFolder = { addingFolder = true },
                    onAutoSort = pickAutoSort, onOrganize = vm::startPlan,
                    onOpenRun = { openRunId = it.id }, onSeeHistory = { tab = Tab.HISTORY },
                    onRequestAccess = requestAccess, onDismissRecovered = vm::dismissRecovered,
                )
                Tab.REVIEW -> ReviewScreen(
                    items = state.review,
                    categoriesFor = { folder -> context.repository.categoriesFor(java.io.File(folder)) },
                    contentPadding = padding,
                    onAccept = vm::accept, onSnooze = vm::snooze, onAcceptAll = vm::acceptAll,
                )
                Tab.HISTORY -> HistoryScreen(state.runs, padding, onOpen = { openRunId = it.id })
                Tab.SETTINGS -> SettingsScreen(
                    state = state, contentPadding = padding,
                    onAutoSort = pickAutoSort, onThreshold = vm::setThreshold, onPreviewThreshold = vm::previewThreshold,
                    onRemoveFolder = vm::removeFolder, onTheme = vm::setTheme, onDynamicColor = vm::setDynamicColor,
                    onReduceMotion = vm::setReduceMotion, onRetrain = vm::retrain, onResetLearning = vm::resetLearning,
                )
            }
        }
    }

    // Ctrl+Z anywhere undoes the most recent run, like the desktop shortcut.
    val keys = Modifier.onPreviewKeyEvent { e ->
        if (e.type == KeyEventType.KeyDown && e.isCtrlPressed && e.key == Key.Z) {
            state.runs.firstOrNull { it.isUndoable }?.let { vm.undo(it.id) }
            true
        } else false
    }

    if (wide) {
        Row(Modifier.fillMaxSize().then(keys)) {
            NavigationRail(containerColor = MaterialTheme.colorScheme.surfaceContainerLow) {
                Tab.entries.forEach { t ->
                    NavigationRailItem(
                        selected = tab == t, onClick = { tab = t },
                        icon = { TabIcon(t) }, label = { Text(stringResource(t.label)) },
                    )
                }
            }
            Scaffold(snackbarHost = { SnackbarHost(snackbarHost) }) { padding -> Content(padding) }
        }
    } else {
        Scaffold(
            modifier = keys,
            snackbarHost = { SnackbarHost(snackbarHost) },
            bottomBar = {
                NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainerLow) {
                    Tab.entries.forEach { t ->
                        NavigationBarItem(
                            selected = tab == t, onClick = { tab = t },
                            icon = { TabIcon(t) }, label = { Text(stringResource(t.label)) },
                        )
                    }
                }
            },
        ) { padding -> Box(Modifier.fillMaxSize()) { Content(padding) } }
    }

    autoSortFor?.let { folder ->
        AutoSortSheet(
            current = state.settings.folders.firstOrNull { it.path == folder.path }?.mode ?: folder.mode,
            onDismiss = { autoSortFor = null },
            onPick = { mode ->
                vm.setMode(folder.path, mode)
                autoSortFor = null
                if (mode != SortMode.OFF && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                    !Permissions.canNotify(context)
                ) {
                    notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
            },
        )
    }
    if (addingFolder) {
        FolderPickerDialog(onDismiss = { addingFolder = false }, onPick = { vm.addFolder(it); addingFolder = false })
    }
}
