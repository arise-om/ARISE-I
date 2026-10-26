package tech.ironlabs.arisei.platform

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.graphics.drawable.Icon
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import androidx.core.app.NotificationManagerCompat
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.data.SortMode
import tech.ironlabs.arisei.repository

/** Re-arms auto-sort after a reboot or an app update. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            Scheduler.sync(context, context.repository.settings.value)
        }
    }
}

/** Undo / Pause buttons on notifications. */
class NotificationActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            ACTION_UNDO -> {
                val runId = intent.getLongExtra(EXTRA_RUN, -1)
                if (runId >= 0) {
                    Scheduler.undo(context, runId)
                    NotificationManagerCompat.from(context).cancel(runId.toInt() + 100)
                }
            }
            ACTION_PAUSE -> {
                val settings = context.repository.settings
                settings.update { s -> s.copy(folders = s.folders.map { it.copy(mode = SortMode.OFF) }) }
                Scheduler.sync(context, settings.value)
            }
        }
    }

    companion object {
        private const val ACTION_UNDO = "tech.ironlabs.arisei.UNDO"
        private const val ACTION_PAUSE = "tech.ironlabs.arisei.PAUSE"
        private const val EXTRA_RUN = "run"

        fun undoIntent(context: Context, runId: Long): PendingIntent = PendingIntent.getBroadcast(
            context, runId.toInt(),
            Intent(context, NotificationActionReceiver::class.java).setAction(ACTION_UNDO).putExtra(EXTRA_RUN, runId),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        fun pauseIntent(context: Context): PendingIntent = PendingIntent.getBroadcast(
            context, 0,
            Intent(context, NotificationActionReceiver::class.java).setAction(ACTION_PAUSE),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
    }
}

/** Quick Settings tile: one tap pauses or resumes auto-sort for every folder. */
class AutoSortTileService : TileService() {
    override fun onStartListening() {
        super.onStartListening()
        render()
    }

    override fun onClick() {
        super.onClick()
        val settings = repository.settings
        settings.update { s ->
            val next = if (s.anyAutoSort) SortMode.OFF else s.lastActiveMode
            s.copy(folders = s.folders.map { it.copy(mode = next) })
        }
        Scheduler.sync(this, settings.value)
        render()
    }

    private fun render() {
        val tile = qsTile ?: return
        val s = repository.settings.value
        val active = s.folders.count { it.mode != SortMode.OFF }
        tile.state = when {
            s.folders.isEmpty() -> Tile.STATE_UNAVAILABLE
            active > 0 -> Tile.STATE_ACTIVE
            else -> Tile.STATE_INACTIVE
        }
        tile.icon = Icon.createWithResource(this, R.drawable.ic_tile)
        tile.label = getString(R.string.tile_label)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
            tile.subtitle = if (active > 0) getString(R.string.tile_subtitle_on, active) else getString(R.string.tile_subtitle_off)
        }
        tile.updateTile()
    }
}
