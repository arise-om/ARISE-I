package tech.ironlabs.arisei.data

import android.content.Context
import android.media.MediaScannerConnection
import android.os.Environment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.withContext
import tech.ironlabs.arisei.engine.CategoryConfig
import tech.ironlabs.arisei.engine.FolderNotFoundException
import tech.ironlabs.arisei.engine.HealthChecker
import tech.ironlabs.arisei.engine.HealthIssue
import tech.ironlabs.arisei.engine.JvmFileSystem
import tech.ironlabs.arisei.engine.LearningStore
import tech.ironlabs.arisei.engine.ModelStats
import tech.ironlabs.arisei.engine.MoveJournal
import tech.ironlabs.arisei.engine.MoveState
import tech.ironlabs.arisei.engine.Organizer
import tech.ironlabs.arisei.engine.Plan
import tech.ironlabs.arisei.engine.RecoveryReport
import tech.ironlabs.arisei.engine.Rules
import tech.ironlabs.arisei.engine.RunKind
import tech.ironlabs.arisei.engine.RunResult
import tech.ironlabs.arisei.engine.RunView
import tech.ironlabs.arisei.engine.SkipRules
import java.io.File

sealed interface FolderHint {
    data class Loose(val count: Int) : FolderHint
    data object Tidy : FolderHint
    data object Protected : FolderHint
    data object Missing : FolderHint
    data object Unknown : FolderHint
}

/** A file waiting in the Review folder, with ARISE-I's best guesses. */
data class ReviewItem(
    val folder: String,
    val name: String,
    val relPath: String,
    val size: Long,
    val waitingSinceMs: Long,
    /** category → confidence, best first, never the Review folder itself. */
    val suggestions: List<Pair<String, Double>>,
    val predicted: String?,
    val isImage: Boolean,
)

/**
 * Everything the UI and the background workers need, on top of the engine.
 * All disk work runs on [Dispatchers.IO]; the engine's per-folder locks keep
 * workers and the UI from interleaving on one folder.
 */
class AriseRepository(private val context: Context, val settings: SettingsRepository) {
    val rules: Rules = Rules.bundled
    private val dataDir = File(context.filesDir, "engine")
    val journal = MoveJournal(File(dataDir, "journal.jsonl"))
    val learning = LearningStore(File(dataDir, "learning"), rules)
    private val skipRules = SkipRules(rules)

    /** Folders ARISE-I must never organise wholesale. */
    private val protectedDirs: Set<File> = buildSet {
        add(Environment.getExternalStorageDirectory())
        add(File("/storage/emulated/0"))
        add(File("/sdcard"))
    }

    private val changes = MutableSharedFlow<Unit>(extraBufferCapacity = 8)

    /** Emits after every run, undo or Review choice — screens refresh on it. */
    val changed: SharedFlow<Unit> = changes.asSharedFlow()

    fun organizerFor(folder: File): Organizer =
        Organizer(rules.withCategories(CategoryConfig.load(folder)), journal, JvmFileSystem, learning, protectedDirs)

    fun hasCustomCategories(folder: File) = File(folder, CategoryConfig.FILE_NAME).isFile

    suspend fun recover(): List<RecoveryReport> = io { organizerFor(dataDir).recover() }

    suspend fun hint(folder: File): FolderHint = io {
        val organizer = organizerFor(folder)
        when {
            organizer.isProtected(folder) -> FolderHint.Protected
            !folder.isDirectory -> FolderHint.Missing
            else -> {
                val loose = folder.listFiles()?.count { it.isFile && skipRules.reason(it.name) == null } ?: 0
                if (loose == 0) FolderHint.Tidy else FolderHint.Loose(loose)
            }
        }
    }

    suspend fun plan(folder: WatchedFolder, only: Set<String>? = null): Plan =
        io { organizerFor(folder.dir).plan(folder.dir, folder.threshold, only) }

    suspend fun execute(
        plan: Plan,
        kind: RunKind = RunKind.MANUAL,
        progress: (Int, Int) -> Unit = { _, _ -> },
        cancelled: () -> Boolean = { false },
    ): RunResult = io { organizerFor(plan.root).execute(plan, kind, progress, cancelled) }.also(::afterRun)

    suspend fun undo(runId: Long, moveIds: Set<Int>? = null): RunResult {
        val run = journal.run(runId) ?: throw IllegalArgumentException("No run $runId")
        return io { organizerFor(run.rootDir).undo(runId, moveIds) }.also(::afterRun)
    }

    suspend fun moveTo(item: ReviewItem, category: String): RunResult = io {
        val root = File(item.folder)
        val confidence = item.suggestions.firstOrNull { it.first == category }?.second ?: 0.0
        organizerFor(root).moveTo(root, item.relPath, category, item.predicted, confidence)
    }.also(::afterRun)

    fun relocate(runId: Long, newRoot: File) {
        journal.relocate(runId, newRoot)
        changes.tryEmit(Unit)
    }

    private fun afterRun(result: RunResult) {
        if (result.touchedPaths.isNotEmpty()) {
            // Gallery and Files only see moved media once it is rescanned.
            MediaScannerConnection.scanFile(context, result.touchedPaths.toTypedArray(), null, null)
        }
        changes.tryEmit(Unit)
    }

    fun runs(): List<RunView> = journal.runs().asReversed()

    fun categoriesFor(folder: File): List<String> =
        rules.withCategories(CategoryConfig.load(folder)).categories.keys.toList() + rules.fallbackCategory

    suspend fun reviewItems(folders: List<WatchedFolder>, snoozed: Map<String, Long>): List<ReviewItem> = io {
        val now = System.currentTimeMillis()
        // When each file entered Review, from the journal (file mtimes are preserved by moves).
        val entered = HashMap<String, Long>()
        for (run in journal.runs()) for (m in run.moves) {
            if (m.state == MoveState.MOVED && m.spec.dst.startsWith(rules.reviewFolder + "/")) {
                entered[File(run.root, m.spec.dst).path] = run.startedAt
            }
        }
        folders.flatMap { folder ->
            val reviewDir = File(folder.dir, rules.reviewFolder)
            val files = reviewDir.listFiles()?.filter { it.isFile && skipRules.reason(it.name) == null }.orEmpty()
            if (files.isEmpty()) return@flatMap emptyList()
            val classifier = organizerFor(folder.dir).classifier(threshold = 0.0)
            files.filter { (snoozed[it.path] ?: 0L) < now }.map { f ->
                val r = classifier.classify(f.name, JvmFileSystem.head(f, 16))
                val guesses = (listOf(r.category to r.confidence) + r.alternatives)
                    .filter { it.first != rules.reviewFolder && it.second >= 0.2 }
                    .distinctBy { it.first }
                    .take(3)
                ReviewItem(
                    folder = folder.path, name = f.name, relPath = "${rules.reviewFolder}/${f.name}",
                    size = f.length(), waitingSinceMs = entered[f.path] ?: f.lastModified(),
                    suggestions = guesses, predicted = guesses.firstOrNull()?.first,
                    isImage = r.category == "Images" || guesses.any { it.first == "Images" && it.second > 0.8 },
                )
            }
        }.sortedBy { it.waitingSinceMs }
    }

    /** How many of the last [sample] sorted files would land in Review at [threshold]. */
    suspend fun thresholdPreview(folder: WatchedFolder, threshold: Double, sample: Int = 40): Pair<Int, Int> = io {
        val recent = journal.runs().asReversed()
            .filter { it.root == folder.path && it.kind != RunKind.UNDO && it.kind != RunKind.REVIEW }
            .flatMap { run -> run.moves.map { File(it.spec.src).name } }
            .take(sample)
        val classifier = organizerFor(folder.dir).classifier(threshold)
        recent.count { classifier.classify(it).category == rules.reviewFolder } to recent.size
    }

    fun stats(): ModelStats = learning.stats()

    suspend fun retrain(): Boolean = io { learning.retrain(force = true) }

    suspend fun resetLearning() = io { learning.reset() }

    suspend fun health(folders: List<File>): List<HealthIssue> =
        io { HealthChecker(rules, organizerFor(dataDir), learning).check(folders) }

    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) { block() }

    companion object {
        fun isNotFound(e: Throwable) = e is FolderNotFoundException
    }
}
