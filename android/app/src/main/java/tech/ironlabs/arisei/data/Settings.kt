package tech.ironlabs.arisei.data

import android.content.Context
import android.content.SharedPreferences
import android.os.Environment
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.File

enum class SortMode { OFF, PERIODIC, LIVE }

enum class ThemeMode { SYSTEM, LIGHT, DARK }

data class WatchedFolder(val path: String, val mode: SortMode = SortMode.OFF, val threshold: Double = 0.75) {
    val dir get() = File(path)
    val displayName: String get() = dir.name.ifEmpty { path }
}

data class AppSettings(
    val folders: List<WatchedFolder> = emptyList(),
    val selected: String? = null,
    val theme: ThemeMode = ThemeMode.SYSTEM,
    val dynamicColor: Boolean = false,
    val reduceMotion: Boolean = false,
    val onboardingDone: Boolean = false,
    /** Review file path → epoch ms until which "Not now" hides it. */
    val snoozed: Map<String, Long> = emptyMap(),
    /** Mode the Quick Settings tile restores when switched back on. */
    val lastActiveMode: SortMode = SortMode.PERIODIC,
) {
    val current: WatchedFolder? get() = folders.firstOrNull { it.path == selected } ?: folders.firstOrNull()
    val anyAutoSort get() = folders.any { it.mode != SortMode.OFF }
    val liveFolders get() = folders.filter { it.mode == SortMode.LIVE }
}

/** Small, synchronous settings store (SharedPreferences) exposed as a StateFlow. */
class SettingsRepository(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("arise", Context.MODE_PRIVATE)
    private val state = MutableStateFlow(read())
    val settings: StateFlow<AppSettings> = state.asStateFlow()
    val value: AppSettings get() = state.value

    private fun read() = AppSettings(
        folders = prefs.getString(KEY_FOLDERS, null)?.lines()?.mapNotNull(::decodeFolder) ?: emptyList(),
        selected = prefs.getString(KEY_SELECTED, null),
        theme = prefs.getString(KEY_THEME, null)?.let { runCatching { ThemeMode.valueOf(it) }.getOrNull() }
            ?: ThemeMode.SYSTEM,
        dynamicColor = prefs.getBoolean(KEY_DYNAMIC, false),
        reduceMotion = prefs.getBoolean(KEY_REDUCE_MOTION, false),
        onboardingDone = prefs.getBoolean(KEY_ONBOARDED, false),
        snoozed = prefs.getString(KEY_SNOOZED, null)?.lines()?.mapNotNull { line ->
            val (until, path) = line.split('|', limit = 2).takeIf { it.size == 2 } ?: return@mapNotNull null
            until.toLongOrNull()?.let { path to it }
        }?.toMap() ?: emptyMap(),
        lastActiveMode = prefs.getString(KEY_LAST_MODE, null)?.let { runCatching { SortMode.valueOf(it) }.getOrNull() }
            ?.takeIf { it != SortMode.OFF } ?: SortMode.PERIODIC,
    )

    @Synchronized
    fun update(transform: (AppSettings) -> AppSettings) {
        val next = transform(state.value)
        prefs.edit()
            .putString(KEY_FOLDERS, next.folders.joinToString("\n") { "${it.mode}|${it.threshold}|${it.path}" })
            .putString(KEY_SELECTED, next.selected)
            .putString(KEY_THEME, next.theme.name)
            .putBoolean(KEY_DYNAMIC, next.dynamicColor)
            .putBoolean(KEY_REDUCE_MOTION, next.reduceMotion)
            .putBoolean(KEY_ONBOARDED, next.onboardingDone)
            .putString(KEY_SNOOZED, next.snoozed.entries.joinToString("\n") { "${it.value}|${it.key}" })
            .putString(KEY_LAST_MODE, next.lastActiveMode.name)
            .apply()
        state.value = next
    }

    fun updateFolder(path: String, transform: (WatchedFolder) -> WatchedFolder) = update { s ->
        val folders = s.folders.map { if (it.path == path) transform(it) else it }
        val active = folders.firstOrNull { it.path == path }?.mode?.takeIf { it != SortMode.OFF }
        s.copy(folders = folders, lastActiveMode = active ?: s.lastActiveMode)
    }

    fun addFolder(dir: File) = update { s ->
        if (s.folders.any { it.path == dir.path }) s.copy(selected = dir.path)
        else s.copy(folders = s.folders + WatchedFolder(dir.path), selected = dir.path)
    }

    fun removeFolder(path: String) = update { s ->
        val folders = s.folders.filterNot { it.path == path }
        s.copy(folders = folders, selected = if (s.selected == path) folders.firstOrNull()?.path else s.selected)
    }

    private fun decodeFolder(line: String): WatchedFolder? {
        val parts = line.split('|', limit = 3)
        if (parts.size != 3) return null
        val mode = runCatching { SortMode.valueOf(parts[0]) }.getOrNull() ?: return null
        return WatchedFolder(parts[2], mode, parts[1].toDoubleOrNull() ?: 0.75)
    }

    companion object {
        private const val KEY_FOLDERS = "folders"
        private const val KEY_SELECTED = "selected"
        private const val KEY_THEME = "theme"
        private const val KEY_DYNAMIC = "dynamic_color"
        private const val KEY_REDUCE_MOTION = "reduce_motion"
        private const val KEY_ONBOARDED = "onboarding_done"
        private const val KEY_SNOOZED = "snoozed"
        private const val KEY_LAST_MODE = "last_mode"

        @Suppress("DEPRECATION")
        val downloads: File get() = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
    }
}
