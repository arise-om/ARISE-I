package tech.ironlabs.arisei.engine

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class LearningTest {
    private val rules = Rules.bundled

    @Test
    fun `features match the desktop extractor`() {
        assertEquals("pdf pdf pdf lab report chem", Features.of("Lab_Report-chem.pdf"))
        assertEquals("notes", Features.of("a notes"))
    }

    @Test
    fun `naive bayes learns a user's naming habit`() {
        val samples = (1..10).flatMap {
            listOf(Features.of("scan_$it.xyz") to "Documents", Features.of("clip_$it.xyz") to "Videos")
        }
        val model = NaiveBayesModel.train(samples, alpha = 0.5, maxFeatures = 8000, trainedAt = "now")
        assertEquals("Documents", model.predict(Features.of("scan_99.xyz")).first().first)
        assertEquals("Videos", model.predict(Features.of("clip_42.xyz")).first().first)
        val roundTrip = NaiveBayesModel.fromJson(model.toJson())
        assertEquals(model.predict("scan xyz"), roundTrip.predict("scan xyz"))
    }

    @Test
    fun `corrections retrain the classifier`() {
        val dir = File(Sandbox().data, "learn")
        val store = LearningStore(dir, rules)
        assertFalse(SmartClassifier(rules).classify("scan_7.xyz").category == "Documents")
        repeat(25) {
            store.record("scan_$it.xyz", rules.reviewFolder, "Documents", 0.1, "review")
            store.record("clip_$it.xyz", rules.reviewFolder, "Videos", 0.1, "review")
        }
        assertTrue(store.retrain())
        assertNotNull(store.model)
        val c = SmartClassifier(rules, model = store.model)
        assertEquals("Documents", c.classify("scan_7.xyz").category)
        assertEquals("ml_model", c.classify("scan_7.xyz").layer)
        // A fresh store loads the persisted model.
        assertNotNull(LearningStore(dir, rules).model)
        assertEquals(1.0, store.correctionRate())
    }

    @Test
    fun `review folder is never a label and retractions drop events`() {
        val store = LearningStore(Sandbox().data, rules)
        store.record("x.pdf", "PDFs", rules.reviewFolder, 0.5, "extension")
        assertEquals(0, store.totalEvents())
        store.record("y.pdf", "PDFs", "PDFs", 0.9, "extension", ref = "1:0")
        store.record("z.pdf", "PDFs", "PDFs", 0.9, "extension", ref = "1:1")
        store.retract("1:0")
        assertEquals(listOf("z.pdf"), store.events().map { it.filename })
    }

    @Test
    fun `health check flags stale review files and missing folders`() {
        val box = Sandbox()
        val stale = box.file("__Review__/old.bin")
        stale.setLastModified(System.currentTimeMillis() - HealthChecker.STALE_REVIEW_MS - 1000)
        box.file("__Review__/fresh.bin")
        val checker = HealthChecker(rules, box.organizer(), learning = null)
        val issues = checker.check(listOf(box.root, File(box.base, "gone")))
        assertTrue(HealthIssue.StaleReview(box.root, listOf("old.bin")) in issues)
        assertTrue(HealthIssue.FolderMissing(File(box.base, "gone")) in issues)
    }
}
