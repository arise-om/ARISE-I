package tech.ironlabs.arisei.engine

import org.snakeyaml.engine.v2.api.Load
import org.snakeyaml.engine.v2.api.LoadSettings
import java.io.File

/** `arise-i.config.yaml` in the target folder — same format as the desktop app. */
object CategoryConfig {
    const val FILE_NAME = "arise-i.config.yaml"

    /** Custom categories for [folder], or null to use the defaults. */
    fun load(folder: File): Map<String, List<String>>? {
        val file = File(folder, FILE_NAME)
        if (!file.isFile) return null
        return runCatching { parse(file.readText(Charsets.UTF_8)) }.getOrNull()
    }

    /** Port of `_normalize_categories`: single string allowed, dots optional. */
    fun parse(yaml: String): Map<String, List<String>>? {
        val data = Load(LoadSettings.builder().build()).loadFromString(yaml) as? Map<*, *> ?: return null
        val out = LinkedHashMap<String, List<String>>()
        for ((name, raw) in data) {
            val exts = when (raw) {
                is String -> listOf(raw)
                is List<*> -> raw
                else -> continue
            }
            val cleaned = exts.filterIsInstance<String>().map { it.trim().lowercase() }.filter { it.isNotEmpty() }
                .map { if (it.startsWith(".")) it else ".$it" }
            if (cleaned.isNotEmpty()) out[name.toString()] = cleaned
        }
        return out.ifEmpty { null }
    }
}
