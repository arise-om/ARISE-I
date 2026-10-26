package tech.ironlabs.arisei.engine

/** Why a file must never be moved — port of `file_organizer.skip_reason`. */
enum class SkipReason { OWN, HIDDEN, SYSTEM, LOCK, PARTIAL }

class SkipRules(rules: Rules) {
    private val own = rules.skip.ownFiles.toSet()
    private val system = rules.skip.systemFiles.toSet()
    private val partial = rules.skip.partialSuffixes.toSet()

    /**
     * Returns null when [name] is sortable.  Android's MediaStore placeholders
     * (`.pending-…`, `.trashed-…`) start with a dot and are covered by HIDDEN.
     */
    fun reason(name: String): SkipReason? = when {
        name in own -> SkipReason.OWN
        name.startsWith(".") -> SkipReason.HIDDEN
        name.lowercase() in system -> SkipReason.SYSTEM
        name.startsWith("~$") -> SkipReason.LOCK
        FileNames.suffix(name).lowercase() in partial -> SkipReason.PARTIAL
        name.endsWith(PART_SUFFIX) -> SkipReason.PARTIAL
        else -> null
    }

    companion object {
        /** Temp name for a copy-fallback move in flight; never sorted itself. */
        const val PART_SUFFIX = ".arise-part"
    }
}
