package tech.ironlabs.arisei.engine

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class OrganizerTest {

    @Test
    fun `planning touches nothing`() {
        val box = Sandbox()
        box.file("report.pdf"); box.file("song.mp3")
        val before = box.tree()
        val plan = box.organizer().plan(box.root)
        assertEquals(listOf("PDFs", "Music"), plan.items.sortedBy { it.name }.map { it.destDir })
        assertEquals(before, box.tree())
        assertFalse(box.journalFile.exists())
    }

    @Test
    fun `run then undo restores everything and prunes empty folders`() {
        val box = Sandbox()
        box.file("report.pdf"); box.file("song.mp3"); box.file("Assignment 1 - calculus.pdf")
        val before = box.tree()
        val organizer = box.organizer()
        val result = organizer.execute(organizer.plan(box.root))
        assertEquals(3, result.moved)
        assertTrue(File(box.root, "Calculus/Assignment 1/PDFs/Assignment 1 - calculus.pdf").isFile)

        val undo = organizer.undo(result.run.id)
        assertEquals(3, undo.moved)
        assertEquals(before, box.tree())
        assertEquals(listOf("Download"), box.base.listFiles()!!.filter { it.name == "Download" }.map { it.name })
        assertTrue(box.root.listFiles()!!.all { it.isFile }, "category folders removed")
        assertTrue(organizer.let { MoveJournal(box.journalFile).run(result.run.id)!! }.moves.all { it.state == MoveState.UNDONE })
    }

    @Test
    fun `dedup never overwrites`() {
        val box = Sandbox()
        box.file("PDFs/dup.pdf", "old"); box.file("dup.pdf", "new")
        val organizer = box.organizer()
        organizer.execute(organizer.plan(box.root))
        assertEquals("old", File(box.root, "PDFs/dup.pdf").readText())
        assertEquals("new", File(box.root, "PDFs/dup (1).pdf").readText())
    }

    @Test
    fun `undo keeps a newer file at the original path`() {
        val box = Sandbox()
        box.file("photo.jpg", "sorted")
        val organizer = box.organizer()
        val run = organizer.execute(organizer.plan(box.root)).run
        box.file("photo.jpg", "newer download")
        organizer.undo(run.id)
        assertEquals("newer download", File(box.root, "photo.jpg").readText())
        assertEquals("sorted", File(box.root, "photo (1).jpg").readText())
    }

    @Test
    fun `undo a single file`() {
        val box = Sandbox()
        box.file("a.pdf"); box.file("b.pdf")
        val organizer = box.organizer()
        val run = organizer.execute(organizer.plan(box.root)).run
        val a = run.moves.first { it.spec.src == "a.pdf" }.spec.id
        organizer.undo(run.id, setOf(a))
        assertEquals(setOf("a.pdf", "PDFs/b.pdf"), box.tree().keys)
        // The rest of the run can still be undone later.
        organizer.undo(run.id)
        assertEquals(setOf("a.pdf", "b.pdf"), box.tree().keys)
    }

    @Test
    fun `plan overrides and exclusions`() {
        val box = Sandbox()
        box.file("mystery"); box.file("keep.pdf")
        val organizer = box.organizer()
        val plan = organizer.plan(box.root).override("mystery", "Notes").exclude("keep.pdf")
        assertFalse(plan.items.first { it.name == "mystery" }.goesToReview)
        organizer.execute(plan)
        assertEquals(setOf("Notes/mystery", "keep.pdf"), box.tree().keys)
    }

    @Test
    fun `review choice is learned and its undo retracts it`() {
        val box = Sandbox()
        val learning = LearningStore(box.data, Rules.bundled)
        box.file("mystery")
        val organizer = box.organizer(learning = learning)
        organizer.execute(organizer.plan(box.root))
        assertEquals(setOf("__Review__/mystery"), box.tree().keys)
        assertEquals(0, learning.totalEvents(), "review quarantine is not a label")

        val choice = organizer.moveTo(box.root, "__Review__/mystery", "Documents", predicted = "Others", confidence = 0.1)
        assertEquals(setOf("Documents/mystery"), box.tree().keys)
        assertEquals(listOf("Documents"), learning.events().map { it.confirmed })
        assertTrue(learning.events().single().corrected)

        organizer.undo(choice.run.id)
        assertEquals(setOf("__Review__/mystery"), box.tree().keys)
        assertEquals(0, learning.totalEvents())
    }

    @Test
    fun `protected and missing folders are refused`() {
        val box = Sandbox()
        val organizer = box.organizer()
        assertFailsWith<ProtectedFolderException> { organizer.plan(box.base) }
        assertFailsWith<ProtectedFolderException> { organizer.plan(File("/")) }
        assertFailsWith<FolderNotFoundException> { organizer.plan(File(box.root, "nope")) }
    }

    @Test
    fun `stop part-way aborts cleanly and is undoable`() {
        val box = Sandbox()
        (1..5).forEach { box.file("f$it.pdf") }
        val organizer = box.organizer()
        var seen = 0
        val result = organizer.execute(organizer.plan(box.root), progress = { done, _ -> seen = done }, cancelled = { seen >= 2 })
        assertTrue(result.aborted)
        assertEquals(2, result.moved)
        assertEquals(RunState.ABORTED, result.run.state)
        organizer.undo(result.run.id)
        assertEquals((1..5).map { "f$it.pdf" }.toSet(), box.tree().keys)
    }

    @Test
    fun `copy fallback when rename is refused`() {
        val box = Sandbox()
        box.file("clip.mp4", "video bytes")
        val organizer = box.organizer(fs = FaultyFileSystem(crashAt = Int.MAX_VALUE, refuseRename = true))
        val r = organizer.execute(organizer.plan(box.root))
        assertEquals(1, r.moved)
        assertEquals(mapOf("Videos/clip.mp4" to "video bytes"), box.tree())
    }

    @Test
    fun `relocated folder can still be undone`() {
        val box = Sandbox()
        box.file("a.pdf")
        val organizer = box.organizer()
        val run = organizer.execute(organizer.plan(box.root)).run
        val moved = File(box.base, "Moved")
        assertTrue(box.root.renameTo(moved))
        organizer.relocate(run.id, moved)
        organizer.undo(run.id)
        assertTrue(File(moved, "a.pdf").isFile)
    }

    @Test
    fun `torn trailing journal line is ignored`() {
        val box = Sandbox()
        box.file("a.pdf")
        val organizer = box.organizer()
        organizer.execute(organizer.plan(box.root))
        box.journalFile.appendText("{\"type\":\"move\",\"run\":1,\"mo")
        assertEquals(1, MoveJournal(box.journalFile).runs().size)
    }
}
