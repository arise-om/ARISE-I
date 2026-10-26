package tech.ironlabs.arisei.engine

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File
import java.io.FileOutputStream

enum class RunKind { MANUAL, AUTO, REVIEW, UNDO }

enum class RunState { RUNNING, COMMITTED, ABORTED, RECOVERED }

/**
 * Move lifecycle.  UNDONE is never written for a move directly: it is derived
 * when an UNDO run that reverts the move has moved the file back.
 */
enum class MoveState { PLANNED, IN_FLIGHT, MOVED, FAILED, SKIPPED, UNDONE;
    val isTerminal get() = this != PLANNED && this != IN_FLIGHT
}

/** A planned move.  Paths are relative to the run's root so a moved folder can be re-rooted. */
@Serializable
data class MoveSpec(
    val id: Int,
    val src: String,
    val dst: String,
    val size: Long = 0,
    val category: String = "",
    val confidence: Double = 1.0,
    val layer: String = "",
    /** For UNDO runs: the move (in [JournalRecord.Begin.reverts]) this one puts back. */
    val revertsMove: Int? = null,
    /** For REVIEW runs: the category ARISE-I had suggested. */
    val predicted: String? = null,
)

/** One line of the append-only journal file. */
@Serializable
sealed class JournalRecord {
    @Serializable @SerialName("begin")
    data class Begin(
        val run: Long,
        val kind: RunKind,
        val root: String,
        val ts: Long,
        val moves: List<MoveSpec>,
        val reverts: Long? = null,
    ) : JournalRecord()

    @Serializable @SerialName("move")
    data class Move(val run: Long, val move: Int, val state: MoveState, val error: String? = null) : JournalRecord()

    @Serializable @SerialName("end")
    data class End(val run: Long, val state: RunState, val ts: Long) : JournalRecord()

    @Serializable @SerialName("relocate")
    data class Relocate(val run: Long, val root: String) : JournalRecord()
}

data class MoveView(val spec: MoveSpec, val state: MoveState, val error: String?)

data class RunView(
    val id: Long,
    val kind: RunKind,
    val root: String,
    val startedAt: Long,
    val state: RunState,
    val endedAt: Long?,
    val moves: List<MoveView>,
    val reverts: Long?,
) {
    val rootDir get() = File(root)
    fun count(state: MoveState) = moves.count { it.state == state }
    val isUndoable get() = kind != RunKind.UNDO && moves.any { it.state == MoveState.MOVED }
}

/**
 * Write-ahead journal for every move ARISE-I makes (fixes the desktop risk of
 * a crash losing the undo record).
 *
 * Durability: `begin` and `end` are fsynced.  Per-move records are only
 * flushed — after a crash, [Organizer.recover] reconciles any move that is
 * not terminal against the disk, so a lost per-move line costs nothing.
 * A torn last line (crash mid-write) is ignored on replay.
 */
class MoveJournal(private val file: File, private val clock: () -> Long = System::currentTimeMillis) {
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = false }
    private val runs = LinkedHashMap<Long, MutableRun>()
    private var nextRunId = 1L

    private class MutableRun(val begin: JournalRecord.Begin) {
        var root = begin.root
        var state = RunState.RUNNING
        var endedAt: Long? = null
        val moveStates = HashMap<Int, Pair<MoveState, String?>>()
    }

    init {
        file.parentFile?.mkdirs()
        if (file.exists()) file.forEachLine(Charsets.UTF_8) { line ->
            if (line.isBlank()) return@forEachLine
            val record = runCatching { json.decodeFromString(JournalRecord.serializer(), line) }.getOrNull()
            if (record != null) apply(record)
        }
    }

    private fun apply(r: JournalRecord) {
        when (r) {
            is JournalRecord.Begin -> {
                runs[r.run] = MutableRun(r)
                nextRunId = maxOf(nextRunId, r.run + 1)
            }
            is JournalRecord.Move -> runs[r.run]?.moveStates?.put(r.move, r.state to r.error)
            is JournalRecord.End -> runs[r.run]?.let { it.state = r.state; it.endedAt = r.ts }
            is JournalRecord.Relocate -> runs[r.run]?.root = r.root
        }
    }

    @Synchronized
    private fun append(r: JournalRecord, sync: Boolean) {
        FileOutputStream(file, true).use { out ->
            out.write((json.encodeToString(JournalRecord.serializer(), r) + "\n").toByteArray(Charsets.UTF_8))
            out.flush()
            if (sync) out.fd.sync()
        }
        apply(r)
    }

    @Synchronized
    fun begin(kind: RunKind, root: File, moves: List<MoveSpec>, reverts: Long? = null): Long {
        val id = nextRunId++
        append(JournalRecord.Begin(id, kind, root.path, clock(), moves, reverts), sync = true)
        return id
    }

    fun mark(run: Long, move: Int, state: MoveState, error: String? = null) =
        append(JournalRecord.Move(run, move, state, error), sync = false)

    fun end(run: Long, state: RunState) = append(JournalRecord.End(run, state, clock()), sync = true)

    /** Point a run at its folder's new location (the user moved the folder). */
    fun relocate(run: Long, newRoot: File) = append(JournalRecord.Relocate(run, newRoot.path), sync = true)

    @Synchronized
    fun runs(): List<RunView> {
        // Moves an UNDO run has put back show as UNDONE on the original run.
        val undone = HashSet<Pair<Long, Int>>()
        for (r in runs.values) {
            val target = r.begin.reverts ?: continue
            r.begin.moves.forEach { m ->
                if (m.revertsMove != null && r.moveStates[m.id]?.first == MoveState.MOVED) undone += target to m.revertsMove
            }
        }
        return runs.values.map { r ->
            RunView(
                id = r.begin.run, kind = r.begin.kind, root = r.root, startedAt = r.begin.ts,
                state = r.state, endedAt = r.endedAt, reverts = r.begin.reverts,
                moves = r.begin.moves.map { m ->
                    val (state, err) = r.moveStates[m.id] ?: (MoveState.PLANNED to null)
                    val effective = if (state == MoveState.MOVED && (r.begin.run to m.id) in undone) MoveState.UNDONE else state
                    MoveView(m, effective, err)
                },
            )
        }
    }

    fun run(id: Long): RunView? = runs().firstOrNull { it.id == id }

    fun incomplete(): List<RunView> = runs().filter { it.state == RunState.RUNNING }
}
