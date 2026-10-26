package tech.ironlabs.arisei.engine

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Classification rules exported from the Python engine by
 * `scripts/export_rules.py`.  Never edit `arise-rules.json` by hand — change
 * the Python tables and re-export, so desktop and Android sort alike.
 */
@Serializable
data class Rules(
    @SerialName("schema_version") val schemaVersion: Int,
    @SerialName("engine_version") val engineVersion: String,
    @SerialName("review_folder") val reviewFolder: String,
    @SerialName("fallback_category") val fallbackCategory: String,
    @SerialName("confidence_threshold") val confidenceThreshold: Double,
    val badge: Badge,
    @SerialName("layer_confidence") val layerConfidence: LayerConfidence,
    val categories: Map<String, List<String>>,
    @SerialName("mime_exact") val mimeExact: Map<String, String>,
    @SerialName("mime_prefix") val mimePrefix: List<MimePrefix>,
    val heuristics: List<Heuristic>,
    val assignment: AssignmentRules,
    val skip: SkipLists,
    val learning: LearningRules,
    @SerialName("mime_by_extension") val mimeByExtension: Map<String, String>,
) {
    @Serializable
    data class Badge(val high: Double, val med: Double)

    @Serializable
    data class LayerConfidence(
        @SerialName("extension_hit") val extensionHit: Double,
        @SerialName("extension_miss") val extensionMiss: Double,
        @SerialName("mime_exact") val mimeExact: Double,
        @SerialName("mime_miss") val mimeMiss: Double,
        @SerialName("heuristic_miss") val heuristicMiss: Double,
        @SerialName("model_miss") val modelMiss: Double,
    )

    @Serializable
    data class MimePrefix(val prefix: String, val category: String, val confidence: Double)

    @Serializable
    data class Heuristic(
        val pattern: String,
        val flags: String,
        val category: String,
        val confidence: Double,
    )

    @Serializable
    data class AssignmentRules(
        val types: List<String>,
        @SerialName("type_first") val typeFirst: List<String>,
        @SerialName("subject_first") val subjectFirst: List<String>,
        @SerialName("no_subject") val noSubject: List<String>,
        val confidence: Map<String, Double>,
        @SerialName("subject_strip") val subjectStrip: String,
    )

    @Serializable
    data class SkipLists(
        @SerialName("own_files") val ownFiles: List<String>,
        @SerialName("system_files") val systemFiles: List<String>,
        @SerialName("partial_suffixes") val partialSuffixes: List<String>,
    )

    @Serializable
    data class LearningRules(
        @SerialName("min_samples") val minSamples: Int,
        @SerialName("retrain_threshold") val retrainThreshold: Int,
        @SerialName("min_class_samples") val minClassSamples: Int,
        val alpha: Double,
        @SerialName("max_features") val maxFeatures: Int,
    )

    /** Same rules with user categories (from `arise-i.config.yaml`) swapped in. */
    fun withCategories(custom: Map<String, List<String>>?): Rules =
        if (custom.isNullOrEmpty()) this else copy(categories = custom)

    companion object {
        const val SUPPORTED_SCHEMA = 1
        private val json = Json { ignoreUnknownKeys = true }

        fun parse(text: String): Rules {
            val rules = json.decodeFromString(serializer(), text)
            require(rules.schemaVersion == SUPPORTED_SCHEMA) {
                "arise-rules.json schema ${rules.schemaVersion} is not supported"
            }
            return rules
        }

        /** Load the rules bundled as a classpath resource (works on JVM and Android). */
        val bundled: Rules by lazy {
            val stream = Rules::class.java.getResourceAsStream("/arise-rules.json")
                ?: error("arise-rules.json missing from the engine resources")
            parse(stream.bufferedReader(Charsets.UTF_8).use { it.readText() })
        }
    }
}
