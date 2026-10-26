package tech.ironlabs.arisei.platform

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import tech.ironlabs.arisei.data.AppSettings
import tech.ironlabs.arisei.data.SortMode
import tech.ironlabs.arisei.repository
import java.util.concurrent.TimeUnit

/** Every 15 minutes: sort folders in "Every 15 minutes" mode (and Live ones, as a safety net). */
class AutoSortWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val repo = applicationContext.repository
        repo.recover()
        repo.settings.value.folders.filter { it.mode != SortMode.OFF }.forEach {
            AutoSorter.sort(applicationContext, it)
        }
        return Result.success()
    }
}

/** The Undo action on a "Sorted N files" notification. */
class UndoWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val runId = inputData.getLong(KEY_RUN, -1)
        if (runId < 0) return Result.failure()
        return runCatching { applicationContext.repository.undo(runId) }
            .fold({ Result.success() }, { Result.failure() })
    }

    companion object { const val KEY_RUN = "run" }
}

/** Every 6 hours: the desktop health monitor's checks, at a phone-friendly pace. */
class HealthWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val repo = applicationContext.repository
        val issues = repo.health(repo.settings.value.folders.map { it.dir })
        Notifier.health(applicationContext, issues)
        return Result.success()
    }
}

object Scheduler {
    private const val AUTO_SORT = "auto-sort"
    private const val HEALTH = "health"

    /** Bring WorkManager and the live watcher in line with [settings]. */
    fun sync(context: Context, settings: AppSettings) {
        val wm = WorkManager.getInstance(context)
        if (settings.anyAutoSort) {
            wm.enqueueUniquePeriodicWork(
                AUTO_SORT, ExistingPeriodicWorkPolicy.KEEP,
                PeriodicWorkRequestBuilder<AutoSortWorker>(15, TimeUnit.MINUTES)
                    .setConstraints(Constraints.Builder().setRequiresBatteryNotLow(true).build())
                    .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.MINUTES)
                    .build(),
            )
        } else {
            wm.cancelUniqueWork(AUTO_SORT)
        }
        if (settings.folders.isNotEmpty()) {
            wm.enqueueUniquePeriodicWork(
                HEALTH, ExistingPeriodicWorkPolicy.KEEP,
                PeriodicWorkRequestBuilder<HealthWorker>(6, TimeUnit.HOURS)
                    .setConstraints(Constraints.Builder().setRequiresBatteryNotLow(true).build())
                    .build(),
            )
        }
        if (settings.liveFolders.isNotEmpty()) WatchService.start(context) else WatchService.stop(context)
    }

    fun undo(context: Context, runId: Long) {
        WorkManager.getInstance(context).enqueueUniqueWork(
            "undo-$runId", ExistingWorkPolicy.KEEP,
            OneTimeWorkRequestBuilder<UndoWorker>()
                .setInputData(workDataOf(UndoWorker.KEY_RUN to runId))
                .build(),
        )
    }
}
