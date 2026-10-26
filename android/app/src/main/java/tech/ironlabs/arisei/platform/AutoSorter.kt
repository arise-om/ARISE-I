package tech.ironlabs.arisei.platform

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import tech.ironlabs.arisei.data.WatchedFolder
import tech.ironlabs.arisei.engine.RunKind
import tech.ironlabs.arisei.engine.SkipRules
import tech.ironlabs.arisei.repository
import java.io.File

/** Shared by the periodic worker and the live watcher: sort a folder's settled files. */
object AutoSorter {
    /** A file must be untouched this long before auto-sort moves it. */
    private const val SETTLE_MS = 3_000L

    suspend fun sort(context: Context, folder: WatchedFolder, candidates: Set<String>? = null) {
        if (!Permissions.hasFileAccess(context)) {
            Notifier.accessRevoked(context)
            return
        }
        val repo = context.repository
        val names = settled(folder.dir, candidates, SkipRules(repo.rules))
        if (names.isEmpty()) return
        val plan = runCatching { repo.plan(folder, only = names) }.getOrNull() ?: return
        if (plan.included.isEmpty()) return
        val result = repo.execute(plan, RunKind.AUTO)
        Notifier.sorted(context, result, repo.rules.reviewFolder)
    }

    /** Names whose size and mtime held still for a second and are older than [SETTLE_MS]. */
    private suspend fun settled(dir: File, candidates: Set<String>?, skip: SkipRules): Set<String> {
        fun snapshot() = dir.listFiles().orEmpty()
            .filter { it.isFile && skip.reason(it.name) == null && (candidates == null || it.name in candidates) }
            .associate { it.name to (it.length() to it.lastModified()) }

        val first = withContext(Dispatchers.IO) { snapshot() }
        if (first.isEmpty()) return emptySet()
        delay(1_000)
        val second = withContext(Dispatchers.IO) { snapshot() }
        val now = System.currentTimeMillis()
        return second.filter { (name, stat) -> first[name] == stat && now - stat.second > SETTLE_MS }.keys
    }
}
