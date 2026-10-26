package tech.ironlabs.arisei.platform

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import tech.ironlabs.arisei.MainActivity
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.engine.SkipRules
import tech.ironlabs.arisei.repository

/**
 * 2×1 home-screen widget: "Download · 23 loose files" + Organize.  The button
 * opens the Plan, never sorts blind, so the safety step is kept.
 */
class OrganizeWidget : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        val pending = goAsync()
        Thread {
            try { render(context, manager, ids) } finally { pending.finish() }
        }.start()
    }

    companion object {
        /** Re-render every placed widget (call after runs and settings changes; any thread). */
        fun refresh(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, OrganizeWidget::class.java))
            if (ids.isNotEmpty()) render(context, manager, ids)
        }

        private fun render(context: Context, manager: AppWidgetManager, ids: IntArray) {
            val repo = context.repository
            val folder = repo.settings.value.current
            val views = RemoteViews(context.packageName, R.layout.widget_organize)
            if (folder == null) {
                views.setTextViewText(R.id.widget_folder, context.getString(R.string.app_name))
                views.setTextViewText(R.id.widget_hint, context.getString(R.string.widget_no_folder))
            } else {
                val skip = SkipRules(repo.rules)
                val loose = if (Permissions.hasFileAccess(context)) {
                    folder.dir.listFiles()?.count { it.isFile && skip.reason(it.name) == null } ?: 0
                } else 0
                views.setTextViewText(R.id.widget_folder, folder.displayName)
                views.setTextViewText(
                    R.id.widget_hint,
                    if (loose == 0) context.getString(R.string.folder_hint_tidy)
                    else context.resources.getQuantityString(R.plurals.folder_hint_loose, loose, loose),
                )
            }
            val open = PendingIntent.getActivity(
                context, 7,
                Intent(context, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                    .putExtra(MainActivity.EXTRA_ACTION, MainActivity.ACTION_ORGANIZE),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            views.setOnClickPendingIntent(R.id.widget_organize, open)
            views.setOnClickPendingIntent(R.id.widget_root, open)
            manager.updateAppWidget(ids, views)
        }
    }
}
