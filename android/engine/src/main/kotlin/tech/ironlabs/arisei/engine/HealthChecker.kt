package tech.ironlabs.arisei.engine

import java.io.File

/** Something the Diagnostics screen or a notification should surface. */
sealed class HealthIssue {
    data class InterruptedRuns(val recovered: List<RecoveryReport>) : HealthIssue()
    data class LowSpace(val folder: File, val freeBytes: Long) : HealthIssue()
    data class StaleReview(val folder: File, val files: List<String>) : HealthIssue()
    data class FolderMissing(val folder: File) : HealthIssue()
    data class Retrained(val correctionRate: Double) : HealthIssue()
}

/**
 * Port of `health_monitor.py`'s checks.  The phone runs them every few hours
 * (not every minute like the desktop daemon) to save battery.
 */
class HealthChecker(
    private val rules: Rules,
    private val organizer: Organizer,
    private val learning: LearningStore?,
    private val fs: FileSystem = JvmFileSystem,
    private val now: () -> Long = System::currentTimeMillis,
) {
    fun check(folders: List<File>): List<HealthIssue> {
        val issues = mutableListOf<HealthIssue>()
        organizer.recover().takeIf { it.isNotEmpty() }?.let { issues += HealthIssue.InterruptedRuns(it) }

        for (folder in folders) {
            if (!fs.isDirectory(folder)) { issues += HealthIssue.FolderMissing(folder); continue }
            val free = fs.freeBytes(folder)
            if (free in 0 until LOW_SPACE_BYTES) issues += HealthIssue.LowSpace(folder, free)
            val review = File(folder, rules.reviewFolder)
            val stale = fs.list(review).orEmpty()
                .filter { fs.isFile(it) && now() - fs.lastModified(it) > STALE_REVIEW_MS }
                .map { it.name }
            if (stale.isNotEmpty()) issues += HealthIssue.StaleReview(folder, stale)
        }

        learning?.let { store ->
            val stats = store.stats()
            val drifting = stats.events >= DRIFT_MIN_EVENTS && stats.correctionRate >= DRIFT_RATE
            val hasNewData = stats.trainedOn == null || stats.events > stats.trainedOn
            if (drifting && hasNewData && store.retrain()) issues += HealthIssue.Retrained(stats.correctionRate)
        }
        return issues
    }

    companion object {
        const val LOW_SPACE_BYTES = 500L * 1024 * 1024
        const val STALE_REVIEW_MS = 7L * 24 * 60 * 60 * 1000
        const val DRIFT_RATE = 0.30
        const val DRIFT_MIN_EVENTS = 30
    }
}
