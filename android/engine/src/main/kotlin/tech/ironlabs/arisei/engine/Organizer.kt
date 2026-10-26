package tech.ironlabs.arisei.engine

import java.io.File
import java.io.IOException
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/** One file in a [Plan], and where it will go. */
data class PlanItem(
    val name: String,
    val size: Long,
    val result: ClassificationResult,
    /** Folder relative to the root, e.g. "PDFs" or "Calculus/Assignment 1/PDFs". */
    val destDir: String,
    /** Category shown in stats and chips (the review folder for quarantined files). */
    val category: String,
    val included: Boolean = true,
    /** True when the user picked the category in the Plan screen. */
    val overridden: Boolean = false,
) {
    val goesToReview get() = result.layer == "review_fallback" && !overridden
}

data class SkippedItem(val name: String, val reason: SkipReason)

/** What a run would do.  Nothing touches the disk until [Organizer.execute]. */
data class Plan(val root: File, val items: List<PlanItem>, val skipped: List<SkippedItem>) {
    val included get() = items.filter { it.included }
    val folderCount get() = included.map { it.destDir }.distinct().size
    val totalBytes get() = included.sumOf { it.size }

    fun exclude(name: String, excluded: Boolean = true) =
        copy(items = items.map { if (it.name == name) it.copy(included = !excluded) else it })

    /** The user chose a folder for [name] in the Plan screen. */
    fun override(name: String, category: String) = copy(
        items = items.map {
            if (it.name != name) it
            else it.copy(category = category, destDir = FileNames.sanitizeCategory(category), overridden = true)
        },
    )
}

data class RunResult(
    val run: RunView,
    /** Absolute paths whose contents changed — feed these to the media scanner. */
    val touchedPaths: List<String>,
    val aborted: Boolean = false,
    val abortReason: String? = null,
) {
    val moved get() = run.count(MoveState.MOVED)
    val failed get() = run.count(MoveState.FAILED)
    val skipped get() = run.count(MoveState.SKIPPED)
}

data class RecoveryReport(val runId: Long, val moved: Int, val restored: Int, val failed: Int)

class ProtectedFolderException(val folder: File) :
    IllegalArgumentException("Refusing to organise a protected folder: $folder")

class FolderNotFoundException(val folder: File) : IOException("Folder not found: $folder")

/**
 * Plans, executes and undoes runs through the [MoveJournal].  Every public
 * operation holds a per-folder lock (process-wide, shared by all instances),
 * so manual runs, auto-sort and undo never interleave on one folder.
 */
class Organizer(
    private val rules: Rules,
    private val journal: MoveJournal,
    private val fs: FileSystem = JvmFileSystem,
    private val learning: LearningStore? = null,
    /** Folders that must never be organised (storage root, "/" …). */
    private val protectedDirs: Set<File> = emptySet(),
    private val sleeper: (Long) -> Unit = Thread::sleep,
) {
    private val skipRules = SkipRules(rules)

    private fun <T> locked(root: File, block: () -> T): T =
        locks.computeIfAbsent(root.absolutePath) { ReentrantLock() }.withLock(block)

    fun isProtected(root: File): Boolean {
        val abs = root.absoluteFile.normalize()
        return abs.parentFile == null || protectedDirs.any { it.absoluteFile.normalize() == abs }
    }

    fun classifier(threshold: Double = rules.confidenceThreshold) =
        SmartClassifier(rules, threshold, learning?.model)

    /** Scan [root] and classify every loose file.  Read-only. */
    fun plan(root: File, threshold: Double = rules.confidenceThreshold, only: Set<String>? = null): Plan {
        if (isProtected(root)) throw ProtectedFolderException(root)
        val entries = fs.list(root) ?: throw FolderNotFoundException(root)
        val classifier = classifier(threshold)
        val items = mutableListOf<PlanItem>()
        val skipped = mutableListOf<SkippedItem>()
        for (f in entries.sortedBy { it.name.lowercase() }) {
            if (only != null && f.name !in only) continue
            val reason = skipRules.reason(f.name)
            if (reason != null) {
                if (reason != SkipReason.OWN) skipped += SkippedItem(f.name, reason)
                continue
            }
            if (!fs.isFile(f)) continue
            val result = classifier.classify(f.name, fs.head(f, MimeDetector.HEAD_BYTES))
            items += place(f.name, fs.size(f), result)
        }
        return Plan(root, items, skipped)
    }

    /** Destination folder for a result — port of the organiser's assignment nesting. */
    private fun place(name: String, size: Long, r: ClassificationResult): PlanItem {
        val category = FileNames.sanitizeCategory(r.category)
        val a = r.assignment
        return when {
            a != null && a.subject != null -> PlanItem(
                name, size, r,
                listOf(a.subject, a.folderName, category).joinToString("/") { FileNames.sanitizeCategory(it) },
                category,
            )
            a != null -> PlanItem(name, size, r, rules.reviewFolder, rules.reviewFolder)
            else -> PlanItem(name, size, r, category, category)
        }
    }

    /** Run [plan].  [cancelled] is checked between files; stopping early is safe. */
    fun execute(
        plan: Plan,
        kind: RunKind = RunKind.MANUAL,
        progress: (done: Int, total: Int) -> Unit = { _, _ -> },
        cancelled: () -> Boolean = { false },
    ): RunResult = locked(plan.root) {
        recoverLocked(plan.root)
        val reserved = HashSet<String>()
        val specs = plan.included.mapIndexed { i, item ->
            val dst = uniqueDestination(File(plan.root, item.destDir), item.name, reserved)
            MoveSpec(
                id = i, src = item.name, dst = dst.relativeTo(plan.root).path, size = item.size,
                category = item.category, confidence = item.result.confidence,
                layer = if (item.overridden) "user" else item.result.layer,
            )
        }
        runMoves(kind, plan.root, specs, reverts = null, progress, cancelled) { spec, runId ->
            // Review moves are not ground truth; the label arrives on resolve.
            if (spec.category != rules.reviewFolder) {
                learning?.record(File(spec.src).name, spec.category, spec.category, spec.confidence, spec.layer, "$runId:${spec.id}")
            }
        }
    }

    /**
     * Put files from [runId] back.  [moveIds] limits it to some files.
     * Never overwrites: a file now occupying the original path keeps it and
     * the restored one gets a " (1)" suffix.  Review choices undone here are
     * retracted from the learning log.
     */
    fun undo(runId: Long, moveIds: Set<Int>? = null): RunResult {
        val run = journal.run(runId) ?: throw IllegalArgumentException("No run $runId")
        return locked(run.rootDir) {
            recoverLocked(run.rootDir)
            val current = journal.run(runId)!!
            val reserved = HashSet<String>()
            val specs = current.moves
                .filter { it.state == MoveState.MOVED && (moveIds == null || it.spec.id in moveIds) }
                .asReversed()
                .mapIndexed { i, m ->
                    val original = File(current.rootDir, m.spec.src)
                    val back = uniqueDestination(original.parentFile, original.name, reserved)
                    MoveSpec(
                        id = i, src = m.spec.dst, dst = back.relativeTo(current.rootDir).path,
                        size = m.spec.size, category = m.spec.category, layer = "undo", revertsMove = m.spec.id,
                    )
                }
            runMoves(RunKind.UNDO, current.rootDir, specs, reverts = runId) { spec, _ ->
                removeEmptyParents(File(current.rootDir, spec.src).parentFile, current.rootDir)
                // An undone sort or Review choice is no longer a label to learn from.
                learning?.retract("$runId:${spec.revertsMove}")
            }
        }
    }

    /**
     * The user decided where a file goes — from the Review Queue (it lives in
     * the review folder) or anywhere else under [root].  Recorded as a REVIEW
     * run, so the choice can be undone, and fed to the learning store.
     */
    fun moveTo(root: File, relPath: String, category: String, predicted: String?, confidence: Double = 0.0): RunResult =
        locked(root) {
            recoverLocked(root)
            val src = File(root, relPath)
            val dst = uniqueDestination(File(root, FileNames.sanitizeCategory(category)), src.name, HashSet())
            val spec = MoveSpec(
                id = 0, src = relPath, dst = dst.relativeTo(root).path, size = fs.size(src),
                category = category, confidence = confidence, layer = "review", predicted = predicted,
            )
            runMoves(RunKind.REVIEW, root, listOf(spec), reverts = null) { s, runId ->
                learning?.record(src.name, s.predicted ?: rules.reviewFolder, category, confidence, "review", "$runId:${s.id}")
                removeEmptyParents(src.parentFile, root)
            }
        }

    /** Re-root a run whose folder the user moved, so its undo works again. */
    fun relocate(runId: Long, newRoot: File) = journal.relocate(runId, newRoot)

    /** Finish any run a crash interrupted.  Safe to call at any time. */
    fun recover(): List<RecoveryReport> =
        journal.incomplete().map { it.rootDir }.distinct().flatMap { root -> locked(root) { recoverLocked(root) } }

    private fun recoverLocked(root: File): List<RecoveryReport> =
        journal.incomplete().filter { it.rootDir == root && fs.isDirectory(root) }.map { run ->
            var moved = 0; var restored = 0; var failed = 0
            for (m in run.moves.filter { !it.state.isTerminal }) {
                val src = File(root, m.spec.src)
                val dst = File(root, m.spec.dst)
                val part = File(dst.path + SkipRules.PART_SUFFIX)
                if (fs.exists(part)) fs.delete(part)
                val srcThere = fs.exists(src)
                val dstThere = fs.exists(dst)
                when {
                    !srcThere && dstThere -> { journal.mark(run.id, m.spec.id, MoveState.MOVED); moved++ }
                    srcThere && dstThere && m.state == MoveState.IN_FLIGHT -> {
                        // Copy fallback finished but the source was never deleted:
                        // the source is intact, so drop the copy.
                        fs.delete(dst)
                        journal.mark(run.id, m.spec.id, MoveState.SKIPPED, "interrupted")
                        restored++
                    }
                    srcThere -> { journal.mark(run.id, m.spec.id, MoveState.SKIPPED, "interrupted"); restored++ }
                    else -> { journal.mark(run.id, m.spec.id, MoveState.FAILED, "file missing"); failed++ }
                }
            }
            journal.end(run.id, RunState.RECOVERED)
            RecoveryReport(run.id, moved, restored, failed)
        }

    private fun runMoves(
        kind: RunKind,
        root: File,
        specs: List<MoveSpec>,
        reverts: Long?,
        progress: (Int, Int) -> Unit = { _, _ -> },
        cancelled: () -> Boolean = { false },
        onMoved: (MoveSpec, Long) -> Unit,
    ): RunResult {
        val runId = journal.begin(kind, root, specs, reverts)
        val touched = mutableListOf<String>()
        var abortReason: String? = null
        for ((done, spec) in specs.withIndex()) {
            if (cancelled()) { abortReason = "cancelled"; break }
            val src = File(root, spec.src)
            val dst = File(root, spec.dst)
            when {
                !fs.exists(src) -> journal.mark(runId, spec.id, MoveState.SKIPPED, "source gone")
                fs.exists(dst) -> journal.mark(runId, spec.id, MoveState.FAILED, "destination exists")
                else -> {
                    journal.mark(runId, spec.id, MoveState.IN_FLIGHT)
                    val error = moveWithRetry(src, dst)
                    if (error == null) {
                        journal.mark(runId, spec.id, MoveState.MOVED)
                        touched += src.path; touched += dst.path
                        // Learning and folder pruning are best-effort; the move itself stands.
                        try { onMoved(spec, runId) } catch (e: Exception) { }
                    } else {
                        journal.mark(runId, spec.id, MoveState.FAILED, error)
                        if (error.startsWith(NO_SPACE)) { abortReason = error; break }
                    }
                }
            }
            progress(done + 1, specs.size)
        }
        journal.end(runId, if (abortReason == null) RunState.COMMITTED else RunState.ABORTED)
        return RunResult(journal.run(runId)!!, touched, abortReason != null, abortReason)
    }

    /** Returns null on success or an error message. */
    private fun moveWithRetry(src: File, dst: File): String? {
        var last: String? = null
        for (delay in RETRY_DELAYS_MS) {
            if (delay > 0) sleeper(delay)
            try {
                moveOnce(src, dst)
                return null
            } catch (e: IOException) {
                last = e.message ?: e.javaClass.simpleName
                if (isNoSpace(e) || !fs.exists(src)) break
            }
        }
        return if (last != null && last.contains("space", ignoreCase = true)) "$NO_SPACE: $last" else last
    }

    private fun moveOnce(src: File, dst: File) {
        val parent = dst.parentFile
        if (!fs.mkdirs(parent)) throw IOException("Cannot create folder ${parent.name}")
        if (fs.rename(src, dst)) return
        // Cross-volume or refused rename: copy, verify, swap in atomically, then delete.
        val part = File(dst.path + SkipRules.PART_SUFFIX)
        try {
            fs.copy(src, part)
            if (fs.size(part) != fs.size(src) || fs.fingerprint(part) != fs.fingerprint(src)) {
                throw IOException("Copy verification failed")
            }
            if (!fs.rename(part, dst)) throw IOException("Cannot finish copy of ${src.name}")
        } catch (e: IOException) {
            fs.delete(part)
            throw e
        }
        if (!fs.delete(src)) {
            fs.delete(dst)
            throw IOException("Cannot remove original ${src.name}")
        }
    }

    private fun isNoSpace(e: IOException) =
        e.message?.let { it.contains("ENOSPC") || it.contains("No space", ignoreCase = true) } == true

    /** Port of `get_unique_destination`: "photo.jpg" → "photo (1).jpg" → … */
    fun uniqueDestination(dir: File, name: String, reserved: MutableSet<String>): File {
        fun free(f: File) = !fs.exists(f) && reserved.add(f.path)
        File(dir, name).let { if (free(it)) return it }
        val stem = FileNames.stem(name)
        val suffix = FileNames.suffix(name)
        for (n in 1..1000) File(dir, "$stem ($n)$suffix").let { if (free(it)) return it }
        throw IOException("Cannot generate unique filename for $name")
    }

    /** Port of `_remove_empty_parents`: prune empty folders up to (not incl.) [stopAt]. */
    private fun removeEmptyParents(start: File?, stopAt: File) {
        var folder = start ?: return
        val stop = stopAt.absoluteFile.normalize()
        if (!folder.absoluteFile.normalize().startsWith(stop)) return
        while (folder.absoluteFile.normalize() != stop) {
            val children = fs.list(folder) ?: return
            if (children.isNotEmpty() || !fs.delete(folder)) return
            folder = folder.parentFile ?: return
        }
    }

    companion object {
        private val locks = ConcurrentHashMap<String, ReentrantLock>()
        val RETRY_DELAYS_MS = longArrayOf(0, 200, 800, 2000)
        const val NO_SPACE = "No space left"
    }
}
