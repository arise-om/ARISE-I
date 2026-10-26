package tech.ironlabs.arisei.platform

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import tech.ironlabs.arisei.MainActivity
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.engine.HealthIssue
import tech.ironlabs.arisei.engine.MoveState
import tech.ironlabs.arisei.engine.RunResult

object Notifier {
    const val CHANNEL_RESULTS = "results"
    const val CHANNEL_WATCHING = "watching"
    const val CHANNEL_HEALTH = "health"
    const val ID_WATCHING = 1
    private const val ID_HEALTH = 2
    private const val ID_ACCESS = 3

    const val EXTRA_TAB = "tab"
    const val TAB_REVIEW = "review"

    fun createChannels(context: Context) {
        val nm = context.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannels(
            listOf(
                NotificationChannel(CHANNEL_RESULTS, context.getString(R.string.channel_results), NotificationManager.IMPORTANCE_DEFAULT),
                NotificationChannel(CHANNEL_WATCHING, context.getString(R.string.channel_watching), NotificationManager.IMPORTANCE_LOW),
                NotificationChannel(CHANNEL_HEALTH, context.getString(R.string.channel_health), NotificationManager.IMPORTANCE_LOW),
            ),
        )
    }

    private fun openApp(context: Context, tab: String? = null): PendingIntent {
        val intent = Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            .apply { tab?.let { putExtra(EXTRA_TAB, it) } }
        return PendingIntent.getActivity(
            context, tab.hashCode(), intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
    }

    /** "Sorted 12 new files · 2 need a quick look"  [Review] [Undo] */
    fun sorted(context: Context, result: RunResult, reviewFolder: String) {
        if (result.moved == 0 || !Permissions.canNotify(context)) return
        val res = context.resources
        val toReview = result.run.moves.count { it.spec.category == reviewFolder && it.state == MoveState.MOVED }
        val text = buildString {
            append(res.getQuantityString(R.plurals.notif_sorted, result.moved, result.moved))
            if (toReview > 0) append(" · ").append(res.getQuantityString(R.plurals.notif_need_review, toReview, toReview))
        }
        val builder = NotificationCompat.Builder(context, CHANNEL_RESULTS)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(context.getString(R.string.notif_sorted_title))
            .setContentText(text)
            .setContentIntent(openApp(context, if (toReview > 0) TAB_REVIEW else null))
            .setAutoCancel(true)
            .addAction(0, context.getString(R.string.action_undo), NotificationActionReceiver.undoIntent(context, result.run.id))
        if (toReview > 0) builder.addAction(0, context.getString(R.string.action_review), openApp(context, TAB_REVIEW))
        notify(context, result.run.id.toInt() + 100, builder.build())
    }

    fun health(context: Context, issues: List<HealthIssue>) {
        if (!Permissions.canNotify(context)) return
        val text = issues.firstNotNullOfOrNull { issue ->
            when (issue) {
                is HealthIssue.StaleReview -> context.resources.getQuantityString(
                    R.plurals.notif_stale_review, issue.files.size, issue.files.size,
                )
                is HealthIssue.LowSpace -> context.getString(R.string.notif_low_space)
                is HealthIssue.FolderMissing -> context.getString(R.string.notif_folder_missing, issue.folder.name)
                else -> null
            }
        } ?: return
        val tab = if (issues.any { it is HealthIssue.StaleReview }) TAB_REVIEW else null
        notify(
            context, ID_HEALTH,
            NotificationCompat.Builder(context, CHANNEL_HEALTH)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(context.getString(R.string.app_name))
                .setContentText(text)
                .setStyle(NotificationCompat.BigTextStyle().bigText(text))
                .setContentIntent(openApp(context, tab))
                .setAutoCancel(true)
                .build(),
        )
    }

    fun accessRevoked(context: Context) {
        if (!Permissions.canNotify(context)) return
        notify(
            context, ID_ACCESS,
            NotificationCompat.Builder(context, CHANNEL_HEALTH)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(context.getString(R.string.app_name))
                .setContentText(context.getString(R.string.notif_access_revoked))
                .setContentIntent(openApp(context))
                .setAutoCancel(true)
                .build(),
        )
    }

    fun watching(context: Context, folderNames: String): Notification =
        NotificationCompat.Builder(context, CHANNEL_WATCHING)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(context.getString(R.string.app_name))
            .setContentText(context.getString(R.string.notif_watching, folderNames))
            .setContentIntent(openApp(context))
            .setOngoing(true)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .addAction(0, context.getString(R.string.action_pause), NotificationActionReceiver.pauseIntent(context))
            .build()

    // Guarded by Permissions.canNotify, which lint cannot see through.
    @SuppressLint("MissingPermission")
    private fun notify(context: Context, id: Int, notification: Notification) {
        if (Permissions.canNotify(context)) NotificationManagerCompat.from(context).notify(id, notification)
    }
}
