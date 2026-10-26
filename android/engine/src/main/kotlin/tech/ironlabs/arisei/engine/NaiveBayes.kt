package tech.ironlabs.arisei.engine

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.sqrt

/** Port of `classifier._extract_text_features`: extension ×3, then stem tokens. */
object Features {
    private val splitter = Regex("[^a-zA-Z0-9]+")

    fun of(fileName: String): String {
        val parts = mutableListOf<String>()
        val ext = FileNames.suffix(fileName).lowercase().removePrefix(".")
        if (ext.isNotEmpty()) repeat(3) { parts += ext }
        FileNames.stem(fileName).lowercase().split(splitter).filterTo(parts) { it.length > 1 }
        return parts.joinToString(" ")
    }
}

/**
 * The desktop ML layer — sklearn's `TfidfVectorizer(ngram_range=(1, 2),
 * sublinear_tf=True)` feeding `MultinomialNB(alpha)` — reimplemented without
 * a dependency so the APK stays small.  Serialised as JSON.
 */
@Serializable
class NaiveBayesModel(
    val vocabulary: List<String>,
    val idf: DoubleArray,
    val classes: List<String>,
    val classLogPrior: DoubleArray,
    /** classes × vocabulary, row-major. */
    val featureLogProb: DoubleArray,
    val trainedOn: Int,
    val trainedAt: String,
) {
    @kotlinx.serialization.Transient
    private val index: Map<String, Int> = vocabulary.withIndex().associate { it.value to it.index }

    /** Class probabilities for [features] (a [Features.of] string), best first. */
    fun predict(features: String): List<Pair<String, Double>> {
        val x = vectorize(features, index, idf)
        val n = vocabulary.size
        val jll = DoubleArray(classes.size) { c ->
            var s = classLogPrior[c]
            for ((j, v) in x) s += v * featureLogProb[c * n + j]
            s
        }
        val max = jll.max()
        val exps = jll.map { exp(it - max) }
        val total = exps.sum()
        return classes.indices.map { classes[it] to exps[it] / total }.sortedByDescending { it.second }
    }

    fun toJson(): String = json.encodeToString(serializer(), this)

    companion object {
        private val json = Json { ignoreUnknownKeys = true }
        private val tokenPattern = Regex("\\b\\w\\w+\\b")

        fun fromJson(text: String): NaiveBayesModel = json.decodeFromString(serializer(), text)

        /** sklearn's default analyzer: lowercase, `(?u)\b\w\w+\b`, then 1- and 2-grams. */
        fun analyze(text: String): List<String> {
            val tokens = tokenPattern.findAll(text.lowercase()).map { it.value }.toList()
            return tokens + tokens.zipWithNext { a, b -> "$a $b" }
        }

        private fun vectorize(text: String, index: Map<String, Int>, idf: DoubleArray): Map<Int, Double> {
            val counts = HashMap<Int, Int>()
            for (term in analyze(text)) index[term]?.let { counts[it] = (counts[it] ?: 0) + 1 }
            val weighted = counts.mapValues { (j, tf) -> (1 + ln(tf.toDouble())) * idf[j] }
            val norm = sqrt(weighted.values.sumOf { it * it })
            return if (norm == 0.0) weighted else weighted.mapValues { it.value / norm }
        }

        fun train(
            samples: List<Pair<String, String>>,
            alpha: Double,
            maxFeatures: Int,
            trainedAt: String,
        ): NaiveBayesModel {
            val docs = samples.map { analyze(it.first) }
            // Vocabulary: the max_features most frequent terms across the corpus.
            val totals = HashMap<String, Int>()
            val docFreq = HashMap<String, Int>()
            for (doc in docs) {
                doc.forEach { totals[it] = (totals[it] ?: 0) + 1 }
                doc.toSet().forEach { docFreq[it] = (docFreq[it] ?: 0) + 1 }
            }
            val vocabulary = totals.entries
                .sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key })
                .take(maxFeatures).map { it.key }.sorted()
            val index = vocabulary.withIndex().associate { it.value to it.index }
            val n = samples.size
            // smooth_idf=True: ln((1 + n) / (1 + df)) + 1
            val idf = DoubleArray(vocabulary.size) { ln((1.0 + n) / (1.0 + docFreq.getValue(vocabulary[it]))) + 1 }

            val classes = samples.map { it.second }.distinct().sorted()
            val featureCount = Array(classes.size) { DoubleArray(vocabulary.size) }
            val classCount = IntArray(classes.size)
            samples.forEach { (text, label) ->
                val c = classes.indexOf(label)
                classCount[c]++
                vectorize(text, index, idf).forEach { (j, v) -> featureCount[c][j] += v }
            }
            val featureLogProb = DoubleArray(classes.size * vocabulary.size)
            for (c in classes.indices) {
                val denom = ln(featureCount[c].sum() + alpha * vocabulary.size)
                for (j in vocabulary.indices) {
                    featureLogProb[c * vocabulary.size + j] = ln(featureCount[c][j] + alpha) - denom
                }
            }
            val prior = DoubleArray(classes.size) { ln(classCount[it].toDouble() / n) }
            return NaiveBayesModel(vocabulary, idf, classes, prior, featureLogProb, n, trainedAt)
        }
    }
}
