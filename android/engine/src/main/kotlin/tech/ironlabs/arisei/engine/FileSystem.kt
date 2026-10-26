package tech.ironlabs.arisei.engine

import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.util.zip.CRC32

/**
 * Every disk operation the organiser performs.  Production uses [JvmFileSystem];
 * tests inject faults (a "process kill" after N operations) to prove the
 * journal never loses or duplicates a file.
 */
interface FileSystem {
    fun list(dir: File): List<File>?
    fun isFile(f: File): Boolean
    fun isDirectory(f: File): Boolean
    fun exists(f: File): Boolean
    fun size(f: File): Long
    fun lastModified(f: File): Long
    fun mkdirs(dir: File): Boolean
    /** Atomic same-volume rename; false when the platform refuses (e.g. cross-volume). */
    fun rename(src: File, dst: File): Boolean
    /** Copy [src] to [dst] and fsync it; throws on failure. */
    fun copy(src: File, dst: File)
    fun delete(f: File): Boolean
    fun freeBytes(dir: File): Long
    fun head(f: File, n: Int): ByteArray?
    /** CRC32 of the first and last 64 KiB — a cheap identity check for copies. */
    fun fingerprint(f: File): Long
}

object JvmFileSystem : FileSystem {
    override fun list(dir: File) = dir.listFiles()?.toList()
    override fun isFile(f: File) = f.isFile
    override fun isDirectory(f: File) = f.isDirectory
    override fun exists(f: File) = f.exists()
    override fun size(f: File) = f.length()
    override fun lastModified(f: File) = f.lastModified()
    override fun mkdirs(dir: File) = dir.isDirectory || dir.mkdirs()
    override fun rename(src: File, dst: File) = !dst.exists() && src.renameTo(dst)
    override fun delete(f: File) = f.delete()
    override fun freeBytes(dir: File) = dir.usableSpace

    override fun copy(src: File, dst: File) {
        FileInputStream(src).use { input ->
            FileOutputStream(dst).use { output ->
                input.copyTo(output, 1 shl 16)
                output.fd.sync()
            }
        }
    }

    override fun head(f: File, n: Int): ByteArray? = try {
        FileInputStream(f).use { s ->
            val buf = ByteArray(n)
            val read = s.read(buf)
            if (read <= 0) null else buf.copyOf(read)
        }
    } catch (e: IOException) {
        null
    }

    override fun fingerprint(f: File): Long {
        val crc = CRC32()
        val chunk = 1 shl 16
        java.io.RandomAccessFile(f, "r").use { raf ->
            val len = raf.length()
            val buf = ByteArray(chunk)
            val first = raf.read(buf, 0, minOf(chunk.toLong(), len).toInt())
            if (first > 0) crc.update(buf, 0, first)
            if (len > chunk) {
                raf.seek(maxOf(chunk.toLong(), len - chunk))
                val last = raf.read(buf)
                if (last > 0) crc.update(buf, 0, last)
            }
            crc.update(len.toString().toByteArray())
        }
        return crc.value
    }
}
