package tech.ironlabs.arisei.engine

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File
import java.io.FileOutputStream
import java.time.Instant

@Serializable
data class FeedbackEvent(
    val ts: String,
    val filename: String,
    val features: String,
    val predicted: String,
    val confirmed: String,
    val confidence: Double,
    val layer: String,
    val corrected: Boolean,
    /** Journal reference ("run:move") so undoing a Review choice can retract it. */
    val ref: String? = null,
    val retracts: String? = null,
)

data class ModelStats(
    val events: Int,
    val correctionRate: Double,
    val trainedOn: Int?,
    val trainedAt: String?,
    val classes: Int,
)

/**
 * Port of `learning_store.LearningStore`: an append-only feedback log plus
 * a retrained [NaiveBayesModel].  Unlike the desktop, a feedback event can be
 * retracted (the user undid the Review choice), and retracted events are
 * never trained on.
 */
class LearningStore(
    dir: File,
    private val rules: Rules,
    private val clock: () -> Instant = Instant::now,
) {
    private val feedbackFile = File(dir, "feedback.jsonl")
    private val modelFile = File(dir, "model.json")
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = false }
    private val learning = rules.learning
    private var sessionEvents = 0

    init { dir.mkdirs() }

    @Volatile
    var model: NaiveBayesModel? = loadModel()
        private set

    private fun loadModel(): NaiveBayesModel? =
        if (!modelFile.exists()) null else runCatching { NaiveBayesModel.fromJson(modelFile.readText()) }.getOrNull()

    /** Record a confirmed label; returns true when this triggered a retrain. */
    @Synchronized
    fun record(
        fileName: String,
        predicted: String,
        confirmed: String,
        confidence: Double,
        layer: String,
        ref: String? = null,
    ): Boolean {
        // The Review quarantine is not a label — the real one arrives on resolve.
        if (confirmed == rules.reviewFolder) return false
        append(
            FeedbackEvent(
                ts = clock().toString(), filename = fileName, features = Features.of(fileName),
                predicted = predicted, confirmed = confirmed, confidence = confidence, layer = layer,
                corrected = predicted != confirmed, ref = ref,
            ),
        )
        sessionEvents++
        if (sessionEvents >= learning.retrainThreshold && totalEvents() >= learning.minSamples) {
            sessionEvents = 0
            return retrain()
        }
        return false
    }

    /** Withdraw the event recorded with [ref] (its Review choice was undone). */
    @Synchronized
    fun retract(ref: String) {
        append(
            FeedbackEvent(
                ts = clock().toString(), filename = "", features = "", predicted = "", confirmed = "",
                confidence = 0.0, layer = "retract", corrected = false, retracts = ref,
            ),
        )
    }

    private fun append(e: FeedbackEvent) {
        FileOutputStream(feedbackFile, true).use {
            it.write((json.encodeToString(FeedbackEvent.serializer(), e) + "\n").toByteArray(Charsets.UTF_8))
        }
    }

    /** Live (non-retracted) events. */
    @Synchronized
    fun events(): List<FeedbackEvent> {
        if (!feedbackFile.exists()) return emptyList()
        val all = feedbackFile.readLines(Charsets.UTF_8).mapNotNull { line ->
            if (line.isBlank()) null
            else runCatching { json.decodeFromString(FeedbackEvent.serializer(), line) }.getOrNull()
        }
        val retracted = all.mapNotNullTo(HashSet()) { it.retracts }
        return all.filter { it.retracts == null && (it.ref == null || it.ref !in retracted) }
    }

    fun totalEvents() = events().size

    fun correctionRate(): Double {
        val events = events()
        return if (events.isEmpty()) 0.0 else events.count { it.corrected }.toDouble() / events.size
    }

    /** Retrain from all live events; [force] skips the minimum-sample guard. */
    @Synchronized
    fun retrain(force: Boolean = false): Boolean {
        val events = events().filter { it.confirmed.isNotEmpty() && it.confirmed != rules.reviewFolder }
        if (!force && events.size < learning.minSamples) return false
        val counts = events.groupingBy { it.confirmed }.eachCount()
        val valid = counts.filterValues { it >= learning.minClassSamples }.keys
        if (valid.size < 2) return false
        val samples = events.filter { it.confirmed in valid }.map { it.features to it.confirmed }
        val trained = NaiveBayesModel.train(samples, learning.alpha, learning.maxFeatures, clock().toString())
        val tmp = File(modelFile.path + ".tmp")
        tmp.writeText(trained.toJson())
        if (!tmp.renameTo(modelFile)) {
            modelFile.delete()
            tmp.renameTo(modelFile)
        }
        model = trained
        return true
    }

    /** Forget everything learned. */
    @Synchronized
    fun reset() {
        feedbackFile.delete()
        modelFile.delete()
        model = null
        sessionEvents = 0
    }

    fun stats(): ModelStats {
        val events = events()
        val m = model
        return ModelStats(
            events = events.size,
            correctionRate = if (events.isEmpty()) 0.0 else events.count { it.corrected }.toDouble() / events.size,
            trainedOn = m?.trainedOn,
            trainedAt = m?.trainedAt,
            classes = m?.classes?.size ?: 0,
        )
    }
}
