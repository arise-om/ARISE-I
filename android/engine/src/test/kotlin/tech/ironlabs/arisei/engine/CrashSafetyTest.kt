package tech.ironlabs.arisei.engine

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Kill the "process" before every single disk operation of a run (and of
 * its undo), restart, and check that no file was lost or duplicated, no
 * temp copy is left, and the run can still be fully undone.
 */
class CrashSafetyTest {
    private val names = listOf("a.pdf", "b.jpg", "c.mp3", "d.zip", "Assignment 2 - physics.docx")

    private fun seed(box: Sandbox) = names.forEach { box.file(it, "content of $it") }

    private fun assertIntact(box: Sandbox, context: String) {
        val contents = box.tree().values.sorted()
        assertEquals(names.map { "content of $it" }.sorted(), contents, "lost or duplicated files ($context)")
        assertTrue(box.tree().keys.none { it.endsWith(SkipRules.PART_SUFFIX) }, "temp copy left ($context)")
    }

    private fun crashThenRecover(refuseRename: Boolean, crashInUndo: Boolean) {
        var crashAt = 0
        while (true) {
            val box = Sandbox()
            seed(box)
            val faulty = FaultyFileSystem(if (crashInUndo) Int.MAX_VALUE else crashAt, refuseRename)
            val organizer = box.organizer(fs = faulty)
            var crashed = false
            try {
                val run = organizer.execute(organizer.plan(box.root))
                if (crashInUndo) {
                    val undoFs = FaultyFileSystem(crashAt, refuseRename)
                    box.organizer(fs = undoFs, journal = MoveJournal(box.journalFile)).undo(run.run.id)
                }
            } catch (e: Crash) {
                crashed = true
            }

            // "Restart": fresh journal from disk, real file system.
            val restarted = box.organizer()
            restarted.recover()
            val context = "crashAt=$crashAt refuseRename=$refuseRename undo=$crashInUndo"
            assertIntact(box, context)
            val journal = MoveJournal(box.journalFile)
            assertTrue(journal.incomplete().isEmpty(), "incomplete run after recovery ($context)")

            // Everything still moved can be put back.
            journal.runs().filter { it.isUndoable }.asReversed().forEach { restarted.undo(it.id) }
            assertEquals(names.toSet(), box.tree().keys, "undo after recovery ($context)")

            if (!crashed) break
            crashAt++
            if (crashAt > 500) fail("runaway")
        }
        assertTrue(crashAt > names.size, "crash points were exercised")
    }

    @Test fun `crash during rename moves`() = crashThenRecover(refuseRename = false, crashInUndo = false)

    @Test fun `crash during copy fallback moves`() = crashThenRecover(refuseRename = true, crashInUndo = false)

    @Test fun `crash during undo`() = crashThenRecover(refuseRename = false, crashInUndo = true)

    @Test fun `crash during copy fallback undo`() = crashThenRecover(refuseRename = true, crashInUndo = true)
}
