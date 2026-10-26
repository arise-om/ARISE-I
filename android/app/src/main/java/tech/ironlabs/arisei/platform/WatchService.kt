package tech.ironlabs.arisei.platform

import android.annotation.SuppressLint
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.FileObserver
import android.os.IBinder
import android.util.Log
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import tech.ironlabs.arisei.data.WatchedFolder
import tech.ironlabs.arisei.repository
import java.io.File
import java.util.concurrent.ConcurrentHashMap

/**
 * "Instantly" auto-sort: a foreground service with a FileObserver per folder.
 * Events are debounced per folder (2 s, like the desktop watcher), then
 * [AutoSorter] waits for the files to settle before moving them.
 */
class WatchService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val observers = mutableListOf<FileObserver>()
    private val pending = ConcurrentHashMap<String, MutableSet<String>>()
    private val debounce = ConcurrentHashMap<String, Job>()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val settings = repository.settings
        startInForeground(settings.value.liveFolders)
        scope.launch {
            settings.settings.collectLatest { s ->
                val live = s.liveFolders
                if (live.isEmpty()) { stopSelf(); return@collectLatest }
                startInForeground(live)
                watch(live)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    // Type 0 below API 34 means "use the manifest type", which lint cannot tell.
    @SuppressLint("WrongConstant")
    private fun startInForeground(folders: List<WatchedFolder>) {
        val names = folders.joinToString(", ") { it.displayName }
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
        } else 0
        ServiceCompat.startForeground(this, Notifier.ID_WATCHING, Notifier.watching(this, names), type)
    }

    private fun watch(folders: List<WatchedFolder>) {
        observers.forEach { it.stopWatching() }
        observers.clear()
        for (folder in folders) {
            if (!folder.dir.isDirectory) continue
            val observer = observerFor(folder.dir) { name -> onEvent(folder, name) }
            observer.startWatching()
            observers += observer
        }
    }

    private fun onEvent(folder: WatchedFolder, name: String?) {
        if (name == null) return
        pending.getOrPut(folder.path) { ConcurrentHashMap.newKeySet() }.add(name)
        debounce[folder.path]?.cancel()
        debounce[folder.path] = scope.launch {
            delay(DEBOUNCE_MS)
            val names = pending.remove(folder.path)?.toSet().orEmpty()
            // Re-read the folder in case its settings changed while we waited.
            val current = repository.settings.value.folders.firstOrNull { it.path == folder.path } ?: return@launch
            runCatching { AutoSorter.sort(this@WatchService, current, names) }
                .onFailure { Log.w(TAG, "auto-sort failed for ${folder.path}", it) }
        }
    }

    override fun onDestroy() {
        observers.forEach { it.stopWatching() }
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val TAG = "WatchService"
        private const val DEBOUNCE_MS = 2_000L
        private const val MASK = FileObserver.CLOSE_WRITE or FileObserver.MOVED_TO

        fun start(context: Context) {
            // Android 12+ refuses to start a foreground service from the background
            // (e.g. when WorkManager woke the process); the periodic worker covers it.
            runCatching { ContextCompat.startForegroundService(context, Intent(context, WatchService::class.java)) }
                .onFailure { Log.i(TAG, "watcher not started: ${it.message}") }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, WatchService::class.java))
        }

        private fun observerFor(dir: File, handler: (String?) -> Unit): FileObserver =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                object : FileObserver(dir, MASK) {
                    override fun onEvent(event: Int, path: String?) = handler(path)
                }
            } else {
                @Suppress("DEPRECATION")
                object : FileObserver(dir.path, MASK) {
                    override fun onEvent(event: Int, path: String?) = handler(path)
                }
            }
    }
}
