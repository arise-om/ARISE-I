package tech.ironlabs.arisei.engine

import java.util.regex.Pattern

/** Port of `classifier.ClassificationResult`. */
data class ClassificationResult(
    val category: String,
    val confidence: Double,
    /** extension · mime · heuristic · assignment · ml_model · review_fallback */
    val layer: String,
    val alternatives: List<Pair<String, Double>> = emptyList(),
    val assignment: AssignmentInfo? = null,
) {
    fun badge(rules: Rules): Badge = when {
        confidence >= rules.badge.high -> Badge.HIGH
        confidence >= rules.badge.med -> Badge.MED
        else -> Badge.LOW
    }
}

enum class Badge { HIGH, MED, LOW }

/**
 * Port of `classifier.SmartClassifier`: every layer votes, the most confident
 * wins, and anything under the threshold is quarantined in Review rather than
 * silently misfiled.
 */
class SmartClassifier(
    private val rules: Rules,
    val threshold: Double = rules.confidenceThreshold,
    private val model: NaiveBayesModel? = null,
) {
    private val categories = rules.categories
    private val fallback = rules.fallbackCategory
    private val review = rules.reviewFolder
    private val conf = rules.layerConfidence
    private val extMap: Map<String, String> = buildMap {
        categories.forEach { (cat, exts) -> exts.forEach { put(it.lowercase(), cat) } }
    }
    private val mime = MimeDetector(rules.mimeByExtension)
    private val heuristics = rules.heuristics.map {
        val flags = if ('i' in it.flags) AssignmentParser.PY_IGNORECASE else AssignmentParser.PY_DEFAULT
        Triple(Pattern.compile(it.pattern, flags), it.category, it.confidence)
    }
    private val assignments = AssignmentParser(rules)

    /** Classify by name; [head] (first bytes of the file) enables magic-byte sniffing. */
    fun classify(fileName: String, head: ByteArray? = null): ClassificationResult {
        val assignment = assignments.parse(fileName)
        val results = mutableListOf(byExtension(fileName), byMime(fileName, head), byHeuristics(fileName))

        if (assignment != null) {
            // Category is the file-type folder so the organiser can build
            // Subject / Assignment N / <file-type>/.
            val ext = byExtension(fileName)
            val fileType = if (ext.confidence > 0.5) ext.category else fallback
            results += ClassificationResult(fileType, assignment.confidence, "assignment", assignment = assignment)
        }
        model?.let { results += byModel(it, fileName) }

        // maxBy keeps the first of equal maxima, like Python's max().
        val best = results.maxBy { it.confidence }
        val winner = if (assignment != null && best.assignment == null) best.copy(assignment = assignment) else best

        val seen = mutableSetOf(winner.category)
        val alts = results.sortedByDescending { it.confidence }
            .filter { seen.add(it.category) }
            .map { it.category to it.confidence }

        if (winner.confidence < threshold) {
            return ClassificationResult(
                category = review,
                confidence = winner.confidence,
                layer = "review_fallback",
                alternatives = listOf(winner.category to winner.confidence) + alts.take(2),
                assignment = assignment,
            )
        }
        return winner.copy(alternatives = alts.take(3))
    }

    private fun known(cat: String) = if (cat in categories) cat else fallback

    private fun byExtension(name: String): ClassificationResult {
        val cat = extMap[FileNames.suffix(name).lowercase()]
        return if (cat != null && FileNames.suffix(name).isNotEmpty()) {
            ClassificationResult(cat, conf.extensionHit, "extension")
        } else {
            ClassificationResult(fallback, conf.extensionMiss, "extension")
        }
    }

    private fun byMime(name: String, head: ByteArray?): ClassificationResult {
        val type = mime.detect(name, head) ?: return ClassificationResult(fallback, conf.mimeMiss, "mime")
        rules.mimeExact[type]?.let { return ClassificationResult(known(it), conf.mimeExact, "mime") }
        rules.mimePrefix.firstOrNull { type.startsWith(it.prefix) }?.let {
            return ClassificationResult(known(it.category), it.confidence, "mime")
        }
        return ClassificationResult(fallback, conf.mimeMiss, "mime")
    }

    private fun byHeuristics(name: String): ClassificationResult {
        heuristics.firstOrNull { it.first.matcher(name).find() }?.let { (_, cat, c) ->
            return ClassificationResult(known(cat), c, "heuristic")
        }
        return ClassificationResult(fallback, conf.heuristicMiss, "heuristic")
    }

    private fun byModel(model: NaiveBayesModel, name: String): ClassificationResult {
        val proba = model.predict(Features.of(name))
        val (cat, p) = proba.first()
        // A config change can drop a category the model learned.
        if (cat == review || cat !in categories) return ClassificationResult(fallback, conf.modelMiss, "ml_model")
        return ClassificationResult(cat, p, "ml_model", alternatives = proba.drop(1).take(3))
    }
}
