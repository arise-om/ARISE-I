package tech.ironlabs.arisei.engine

import java.util.regex.Pattern

/** Port of `assignment_classifier.AssignmentInfo`. */
data class AssignmentInfo(
    /** e.g. "Calculus"; null sends the file to Review. */
    val subject: String?,
    /** "Assignment", "Lab", "Lab Report" or "Project". */
    val type: String,
    val number: Int,
    val confidence: Double,
) {
    val folderName: String get() = "$type $number"
}

/** Port of `assignment_classifier.parse_assignment`, patterns from the exported rules. */
class AssignmentParser(rules: Rules) {
    private val spec = rules.assignment
    private val typeFirst = spec.typeFirst.map(::compile)
    private val subjectFirst = spec.subjectFirst.map(::compile)
    private val noSubject = spec.noSubject.map(::compile)

    fun parse(fileName: String): AssignmentInfo? {
        val stem = FileNames.stem(fileName).trim()
        match(typeFirst, stem)?.let { m ->
            return AssignmentInfo(subject(m), type(m), m.group("num").toInt(), conf("type_first"))
        }
        match(subjectFirst, stem)?.let { m ->
            return AssignmentInfo(subject(m), type(m), m.group("num").toInt(), conf("subject_first"))
        }
        match(noSubject, stem)?.let { m ->
            return AssignmentInfo(null, type(m), m.group("num").toInt(), conf("no_subject"))
        }
        return null
    }

    // Python's re.match anchors at the start only, i.e. Matcher.lookingAt().
    private fun match(patterns: List<Pattern>, stem: String) =
        patterns.firstNotNullOfOrNull { p -> p.matcher(stem).takeIf { it.lookingAt() } }

    private fun subject(m: java.util.regex.Matcher): String? =
        FileNames.strip(m.group("subject"), spec.subjectStrip)
            .takeIf { it.isNotEmpty() }
            ?.let(FileNames::titleCase)

    private fun type(m: java.util.regex.Matcher) = FileNames.titleCase(m.group("type").trim())

    private fun conf(key: String) = spec.confidence.getValue(key)

    private fun compile(pattern: String): Pattern = Pattern.compile(pattern, PY_IGNORECASE)

    internal companion object {
        /** Python 3 `re.I` on str patterns: Unicode-aware case folding and classes. */
        const val PY_IGNORECASE =
            Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or Pattern.UNICODE_CHARACTER_CLASS
        const val PY_DEFAULT = Pattern.UNICODE_CHARACTER_CLASS
    }
}
