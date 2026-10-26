package tech.ironlabs.arisei.engine

/**
 * Filename helpers that reproduce Python's `pathlib` and `str` semantics, so
 * a name is split and cased exactly as the desktop engine would.
 */
object FileNames {

    /** `Path(name).suffix`: last ".ext", or "" for ".hidden", "name." and "..". */
    fun suffix(name: String): String {
        val i = name.lastIndexOf('.')
        return if (i > 0 && i < name.length - 1) name.substring(i) else ""
    }

    /** `Path(name).stem`. */
    fun stem(name: String): String = name.substring(0, name.length - suffix(name).length)

    /** Python `str.title()`: upper-case each cased run's first letter, lower the rest. */
    fun titleCase(text: String): String {
        val out = StringBuilder(text.length)
        var previousCased = false
        var i = 0
        while (i < text.length) {
            val cp = text.codePointAt(i)
            val cased = Character.isUpperCase(cp) || Character.isLowerCase(cp) ||
                Character.isTitleCase(cp)
            out.appendCodePoint(
                when {
                    !cased -> cp
                    previousCased -> Character.toLowerCase(cp)
                    else -> Character.toTitleCase(cp)
                },
            )
            previousCased = cased
            i += Character.charCount(cp)
        }
        return out.toString()
    }

    /** Python `str.strip(chars)`. */
    fun strip(text: String, chars: String): String = text.trim { it in chars }

    private val unsafeChars = Regex("[<>:\"/\\\\|?*\\x00-\\x1f]")

    /** Port of `file_organizer._sanitize_category_name` — no traversal, never empty. */
    fun sanitizeCategory(name: String): String {
        val cleaned = strip(name.replace(unsafeChars, "").replace("..", ""), ". ")
        return cleaned.ifEmpty { "Others" }
    }
}
