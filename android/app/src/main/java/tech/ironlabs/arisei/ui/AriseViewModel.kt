package tech.ironlabs.arisei.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.data.AppSettings
import tech.ironlabs.arisei.data.FolderHint
import tech.ironlabs.arisei.data.ReviewItem
import tech.ironlabs.arisei.data.SettingsRepository
import tech.ironlabs.arisei.data.SortMode
import tech.ironlabs.arisei.data.ThemeMode
import tech.ironlabs.arisei.data.WatchedFolder
import tech.ironlabs.arisei.engine.FolderNotFoundException
import tech.ironlabs.arisei.engine.ModelStats
import tech.ironlabs.arisei.engine.Plan
import tech.ironlabs.arisei.engine.ProtectedFolderException
import tech.ironlabs.arisei.engine.RecoveryReport
import tech.ironlabs.arisei.engine.RunResult
import tech.ironlabs.arisei.engine.RunView
import tech.ironlabs.arisei.platform.Permissions
import tech.ironlabs.arisei.platform.Scheduler
import tech.ironlabs.arisei.repository
import java.io.File

/** The Plan screen: scanning → reviewing the plan → running. */
data class PlanUi(
    val folder: WatchedFolder,
    val plan: Plan? = null,
    val error: PlanError? = null,
    val running: Boolean = false,
    val done: Int = 0,
    val total: Int = 0,
)

enum class PlanError { PROTECTED, MISSING, OTHER }

data class UiState(
    val settings: AppSettings,
    val hasAccess: Boolean = false,
    val hint: FolderHint = FolderHint.Unknown,
    val runs: List<RunView> = emptyList(),
    val review: List<ReviewItem> = emptyList(),
    val plan: PlanUi? = null,
    val recovered: List<RecoveryReport> = emptyList(),
    val stats: ModelStats = ModelStats(0, 0.0, null, null, 0),
    val thresholdPreview: Pair<Int, Int>? = null,
    val customCategories: Boolean = false,
    val categories: List<String> = emptyList(),
)

/** One-shot messages; [undoRun] adds an Undo action to the snackbar. */
data class Snack(val message: String, val undoRun: Long? = null, val retry: Boolean = false)

class AriseViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = app.repository
    private val settings: SettingsRepository = repo.settings
    private val _state = MutableStateFlow(UiState(settings.value))
    val state: StateFlow<UiState> = _state.asStateFlow()
    private val snacks = Channel<Snack>(Channel.BUFFERED)
    val snackbar = snacks.receiveAsFlow()

    private var runJob: Job? = null
    @Volatile private var stopRequested = false

    init {
        viewModelScope.launch { settings.settings.collect { s -> _state.update { it.copy(settings = s) }; refresh() } }
        viewModelScope.launch { repo.changed.collect { refresh() } }
        viewModelScope.launch {
            val recovered = repo.recover().filter { it.moved + it.restored + it.failed > 0 }
            if (recovered.isNotEmpty()) _state.update { it.copy(recovered = recovered) }
        }
    }

    private fun str(id: Int, vararg args: Any) = getApplication<Application>().getString(id, *args)
    private fun plural(id: Int, n: Int) = getApplication<Application>().resources.getQuantityString(id, n, n)

    /** Re-read everything cheap: access, folder hint, runs, review queue, stats. */
    fun refresh() {
        viewModelScope.launch {
            val s = settings.value
            val access = Permissions.hasFileAccess(getApplication())
            val folder = s.current
            val hint = if (folder != null && access) repo.hint(folder.dir) else FolderHint.Unknown
            val review = if (access) repo.reviewItems(s.folders, s.snoozed) else emptyList()
            _state.update {
                it.copy(
                    hasAccess = access, hint = hint, runs = repo.runs(), review = review, stats = repo.stats(),
                    customCategories = folder?.let { f -> repo.hasCustomCategories(f.dir) } ?: false,
                    categories = folder?.let { f -> repo.categoriesFor(f.dir) } ?: emptyList(),
                )
            }
        }
    }

    // ── Folders & settings ──────────────────────────────────────────────────

    fun selectFolder(path: String) = settings.update { it.copy(selected = path) }

    fun addFolder(dir: File) = settings.addFolder(dir)

    fun removeFolder(path: String) {
        settings.removeFolder(path)
        Scheduler.sync(getApplication(), settings.value)
    }

    fun setMode(path: String, mode: SortMode) {
        settings.updateFolder(path) { it.copy(mode = mode) }
        Scheduler.sync(getApplication(), settings.value)
    }

    fun setThreshold(path: String, threshold: Double) {
        settings.updateFolder(path) { it.copy(threshold = threshold) }
        previewThreshold(path, threshold)
    }

    fun previewThreshold(path: String, threshold: Double) {
        val folder = settings.value.folders.firstOrNull { it.path == path } ?: return
        viewModelScope.launch {
            val preview = repo.thresholdPreview(folder, threshold)
            _state.update { it.copy(thresholdPreview = preview.takeIf { p -> p.second > 0 }) }
        }
    }

    fun setTheme(mode: ThemeMode) = settings.update { it.copy(theme = mode) }
    fun setDynamicColor(on: Boolean) = settings.update { it.copy(dynamicColor = on) }
    fun setReduceMotion(on: Boolean) = settings.update { it.copy(reduceMotion = on) }

    fun completeOnboarding(folder: File) {
        settings.addFolder(folder)
        settings.update { it.copy(onboardingDone = true) }
        startPlan()
    }

    fun skipOnboarding() = settings.update { it.copy(onboardingDone = true) }

    fun dismissRecovered() = _state.update { it.copy(recovered = emptyList()) }

    // ── Plan & run ──────────────────────────────────────────────────────────

    fun startPlan() {
        val folder = settings.value.current ?: return
        _state.update { it.copy(plan = PlanUi(folder)) }
        viewModelScope.launch {
            val ui = try {
                PlanUi(folder, plan = repo.plan(folder))
            } catch (e: ProtectedFolderException) {
                PlanUi(folder, error = PlanError.PROTECTED)
            } catch (e: FolderNotFoundException) {
                PlanUi(folder, error = PlanError.MISSING)
            } catch (e: Exception) {
                PlanUi(folder, error = PlanError.OTHER)
            }
            _state.update { if (it.plan?.folder?.path == folder.path) it.copy(plan = ui) else it }
        }
    }

    fun closePlan() {
        if (_state.value.plan?.running == true) return
        _state.update { it.copy(plan = null) }
    }

    private fun editPlan(transform: (Plan) -> Plan) = _state.update { s ->
        val p = s.plan ?: return@update s
        val plan = p.plan ?: return@update s
        if (p.running) s else s.copy(plan = p.copy(plan = transform(plan)))
    }

    fun setIncluded(name: String, included: Boolean) = editPlan { it.exclude(name, excluded = !included) }

    fun overrideCategory(name: String, category: String) = editPlan { it.override(name, category) }

    fun runPlan() {
        val ui = _state.value.plan ?: return
        val plan = ui.plan ?: return
        if (ui.running || plan.included.isEmpty()) return
        stopRequested = false
        _state.update { it.copy(plan = ui.copy(running = true, done = 0, total = plan.included.size)) }
        runJob = viewModelScope.launch {
            val result = runCatching {
                repo.execute(
                    plan,
                    progress = { done, total ->
                        _state.update { s -> s.copy(plan = s.plan?.copy(done = done, total = total)) }
                    },
                    cancelled = { stopRequested },
                )
            }
            _state.update { it.copy(plan = null) }
            result.onSuccess { announce(it) }
                .onFailure { snacks.send(Snack(str(R.string.snack_failed, plan.included.size), retry = true)) }
        }
    }

    fun stopRun() { stopRequested = true }

    private suspend fun announce(result: RunResult) {
        val message = when {
            result.abortReason?.startsWith("No space") == true -> str(R.string.snack_no_space)
            result.failed > 0 -> str(R.string.snack_failed, result.failed)
            else -> plural(R.plurals.snack_sorted, result.moved)
        }
        snacks.send(Snack(message, undoRun = result.run.id.takeIf { result.moved > 0 }))
    }

    // ── Undo ────────────────────────────────────────────────────────────────

    fun undo(runId: Long, moveIds: Set<Int>? = null) {
        viewModelScope.launch {
            runCatching { repo.undo(runId, moveIds) }
                .onSuccess { snacks.send(Snack(str(R.string.snack_undone))) }
                .onFailure { snacks.send(Snack(str(R.string.snack_failed, 1))) }
        }
    }

    fun relocate(runId: Long, newRoot: File) = repo.relocate(runId, newRoot)

    // ── Review ──────────────────────────────────────────────────────────────

    fun accept(item: ReviewItem, category: String) {
        viewModelScope.launch {
            runCatching { repo.moveTo(item, category) }.onSuccess { r ->
                snacks.send(Snack(str(R.string.snack_moved_to, item.name, category), undoRun = r.run.id))
            }
        }
    }

    fun acceptAll(items: List<ReviewItem>, category: String? = null) {
        viewModelScope.launch {
            var moved = 0
            items.forEach { item ->
                val target = category ?: item.suggestions.firstOrNull()?.first ?: return@forEach
                if (runCatching { repo.moveTo(item, target) }.isSuccess) moved++
            }
            snacks.send(Snack(plural(R.plurals.snack_sorted, moved)))
        }
    }

    fun snooze(item: ReviewItem) {
        val path = File(item.folder, item.relPath).path
        settings.update { it.copy(snoozed = it.snoozed + (path to System.currentTimeMillis() + SNOOZE_MS)) }
        viewModelScope.launch { snacks.send(Snack(str(R.string.snack_snoozed))) }
    }

    // ── Learning ────────────────────────────────────────────────────────────

    fun retrain() {
        viewModelScope.launch {
            val ok = repo.retrain()
            snacks.send(Snack(str(if (ok) R.string.retrained else R.string.retrain_not_enough)))
            refresh()
        }
    }

    fun resetLearning() {
        viewModelScope.launch { repo.resetLearning(); refresh() }
    }

    companion object {
        const val SNOOZE_MS = 7L * 24 * 60 * 60 * 1000
        val defaultFolder: File get() = SettingsRepository.downloads
    }
}
