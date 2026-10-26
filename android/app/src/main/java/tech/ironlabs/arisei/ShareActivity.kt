package tech.ironlabs.arisei

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.widget.Toast
import tech.ironlabs.arisei.data.SettingsRepository
import tech.ironlabs.arisei.engine.FileNames
import tech.ironlabs.arisei.engine.SkipRules
import tech.ironlabs.arisei.platform.Permissions
import java.io.File

/**
 * "Share → Sort with ARISE-I": saves the shared files into the current folder
 * and opens the Plan for just those files, so the user sees where they'd go.
 */
class ShareActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Recreated (e.g. rotation) after the copy already started: don't save twice.
        if (savedInstanceState != null) { finish(); return }
        val uris = sharedUris(intent)
        if (uris.isEmpty() || !Permissions.hasFileAccess(this)) {
            // No access yet: the main screen explains and asks for it.
            startActivity(Intent(this, MainActivity::class.java))
            finish()
            return
        }
        val settings = repository.settings
        if (settings.value.current == null) settings.addFolder(SettingsRepository.downloads)
        val folder = settings.value.current!!.dir

        Thread {
            val saved = uris.mapNotNull { save(it, folder) }
            runOnUiThread {
                if (saved.isEmpty()) {
                    Toast.makeText(this, R.string.share_failed, Toast.LENGTH_LONG).show()
                } else {
                    Toast.makeText(
                        this, resources.getQuantityString(R.plurals.share_saved, saved.size, saved.size), Toast.LENGTH_SHORT,
                    ).show()
                    startActivity(
                        Intent(this, MainActivity::class.java)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                            .putExtra(MainActivity.EXTRA_ACTION, MainActivity.ACTION_ORGANIZE)
                            .putExtra(MainActivity.EXTRA_ONLY, saved.toTypedArray()),
                    )
                }
                finish()
            }
        }.start()
    }

    private fun sharedUris(intent: Intent): List<Uri> = when (intent.action) {
        Intent.ACTION_SEND -> listOfNotNull(
            if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
            else @Suppress("DEPRECATION") intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM),
        )
        Intent.ACTION_SEND_MULTIPLE ->
            (if (Build.VERSION.SDK_INT >= 33) intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
            else @Suppress("DEPRECATION") intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)).orEmpty()
        else -> emptyList()
    }

    /** Copy [uri] into [folder] under a unique name; returns the name, or null on failure. */
    private fun save(uri: Uri, folder: File): String? = runCatching {
        val name = displayName(uri)
        val target = repository.organizerFor(folder).uniqueDestination(folder, name, HashSet())
        // Write under the in-flight suffix so auto-sort never grabs a half-copied file.
        val part = File(target.path + SkipRules.PART_SUFFIX)
        contentResolver.openInputStream(uri)!!.use { input ->
            part.outputStream().use { out -> input.copyTo(out); out.fd.sync() }
        }
        check(part.renameTo(target)) { "rename failed" }
        target.name
    }.getOrNull()

    private fun displayName(uri: Uri): String {
        val queried = runCatching {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) c.getString(0) else null
            }
        }.getOrNull()
        // Never trust a path from another app: keep only the last segment.
        val name = File(queried ?: uri.lastPathSegment ?: "").name.trim()
        return if (name.isEmpty() || name.startsWith(".")) "shared-${System.currentTimeMillis()}" +
            FileNames.suffix(name) else name
    }
}
