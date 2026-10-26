package tech.ironlabs.arisei.engine

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class EngineUnitTest {
    private val rules = Rules.bundled

    @Test
    fun `suffix and stem follow pathlib`() {
        assertEquals(".gz" to "archive.tar", FileNames.suffix("archive.tar.gz") to FileNames.stem("archive.tar.gz"))
        assertEquals("" to ".hidden", FileNames.suffix(".hidden") to FileNames.stem(".hidden"))
        assertEquals("" to "backup.", FileNames.suffix("backup.") to FileNames.stem("backup."))
        assertEquals(".b" to ".a", FileNames.suffix(".a.b") to FileNames.stem(".a.b"))
    }

    @Test
    fun `title case matches python str title`() {
        assertEquals("Économie 3D X-Ray O'Neil", FileNames.titleCase("économie 3d x-ray o'neil"))
        assertEquals("Lab Report", FileNames.titleCase("LAB REPORT"))
    }

    @Test
    fun `category names cannot escape the folder`() {
        assertEquals("etcpasswd", FileNames.sanitizeCategory("../etc/passwd"))
        assertEquals("Others", FileNames.sanitizeCategory(" .. "))
    }

    @Test
    fun `skip rules`() {
        val skip = SkipRules(rules)
        assertEquals(SkipReason.HIDDEN, skip.reason(".pending-1700000000-photo.jpg"))
        assertEquals(SkipReason.SYSTEM, skip.reason("DESKTOP.INI"))
        assertEquals(SkipReason.LOCK, skip.reason("~\$budget.xlsx"))
        assertEquals(SkipReason.PARTIAL, skip.reason("movie.mkv.crdownload"))
        assertEquals(SkipReason.PARTIAL, skip.reason("photo.jpg.arise-part"))
        assertEquals(SkipReason.OWN, skip.reason("arise-i.config.yaml"))
        assertNull(skip.reason("photo.jpg"))
    }

    @Test
    fun `assignment parsing`() {
        val p = AssignmentParser(rules)
        assertEquals(AssignmentInfo("Calculus", "Assignment", 1, 0.95), p.parse("Assignment 1 - calculus.pdf"))
        assertEquals(AssignmentInfo("Math", "Assignment", 4, 0.93), p.parse("Math - Assignment 4.docx"))
        assertEquals(AssignmentInfo(null, "Lab", 5, 0.80), p.parse("lab 5"))
        assertNull(p.parse("holiday photos.jpg"))
    }

    @Test
    fun `magic bytes beat an unknown extension`() {
        val c = SmartClassifier(rules)
        val pdf = "%PDF-1.7".toByteArray()
        assertEquals("PDFs", c.classify("download.bin", pdf).category)
        assertEquals(rules.reviewFolder, c.classify("download.bin", null).category)
    }

    @Test
    fun `badges and alternatives`() {
        val r = SmartClassifier(rules).classify("mystery")
        assertEquals(rules.reviewFolder, r.category)
        assertEquals(Badge.LOW, r.badge(rules))
        assertEquals("Others", r.alternatives.first().first)
        assertEquals(Badge.HIGH, SmartClassifier(rules).classify("a.pdf").badge(rules))
    }

    @Test
    fun `yaml categories normalise like the desktop`() {
        val parsed = CategoryConfig.parse(
            """
            Work:
              - docx
              - .PDF
            Single: mp4
            Broken: 42
            """.trimIndent(),
        )
        assertEquals(mapOf("Work" to listOf(".docx", ".pdf"), "Single" to listOf(".mp4")), parsed)
        assertNull(CategoryConfig.parse("- just\n- a list"))
    }
}
