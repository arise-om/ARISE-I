package tech.ironlabs.arisei.engine

import java.io.File
import java.nio.file.Files

/** A throwaway folder layout: the folder being organised plus app-private data. */
class Sandbox {
    val base: File = Files.createTempDirectory("arise-test").toFile()
    val root = File(base, "Download").apply { mkdirs() }
    val data = File(base, "data").apply { mkdirs() }
    val journalFile = File(data, "journal.jsonl")

    fun file(rel: String, content: String = rel): File =
        File(root, rel).apply { parentFile.mkdirs(); writeText(content) }

    /** Every file under [root] as relative path → content. */
    fun tree(): Map<String, String> = root.walkTopDown().filter { it.isFile }
        .associate { it.relativeTo(root).invariantSeparatorsPath to it.readText() }

    fun organizer(
        fs: FileSystem = JvmFileSystem,
        learning: LearningStore? = null,
        journal: MoveJournal = MoveJournal(journalFile),
    ) = Organizer(Rules.bundled, journal, fs, learning, protectedDirs = setOf(base), sleeper = {})
}

/** Simulates the process being killed mid-operation: an Error, so no `catch (e: Exception)` swallows it. */
class Crash : Error("simulated process kill")

/**
 * Delegates to the real disk but "kills the process" before the N-th
 * mutating call.  [refuseRename] forces the copy fallback path.
 */
class FaultyFileSystem(
    private val crashAt: Int,
    private val refuseRename: Boolean = false,
) : FileSystem by JvmFileSystem {
    var ops = 0
        private set

    private fun isCrashPoint() = ops++ == crashAt
    private fun tick() { if (isCrashPoint()) throw Crash() }

    override fun mkdirs(dir: File): Boolean { tick(); return JvmFileSystem.mkdirs(dir) }
    override fun rename(src: File, dst: File): Boolean {
        tick()
        if (refuseRename && !src.name.endsWith(SkipRules.PART_SUFFIX)) return false
        return JvmFileSystem.rename(src, dst)
    }
    override fun copy(src: File, dst: File) {
        // Die half-way through writing the copy, leaving a torn file behind.
        if (isCrashPoint()) { dst.writeText(src.readText().take(1)); throw Crash() }
        JvmFileSystem.copy(src, dst)
    }
    override fun delete(f: File): Boolean { tick(); return JvmFileSystem.delete(f) }
}
