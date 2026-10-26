package tech.ironlabs.arisei.engine

/**
 * Layer-2 MIME detection: magic bytes first (the Android stand-in for the
 * desktop's optional `filetype` package), then the exported extension table
 * (the stand-in for `mimetypes.guess_type`).
 */
class MimeDetector(private val byExtension: Map<String, String>) {

    fun detect(fileName: String, head: ByteArray?): String? =
        head?.let(::sniff) ?: byExtension[FileNames.suffix(fileName).lowercase()]

    fun sniff(b: ByteArray): String? {
        fun at(offset: Int, vararg sig: Int) =
            b.size >= offset + sig.size && sig.indices.all { (b[offset + it].toInt() and 0xFF) == sig[it] }
        fun ascii(offset: Int, s: String) = at(offset, *s.map { it.code }.toIntArray())

        return when {
            ascii(0, "%PDF") -> "application/pdf"
            at(0, 0x89, 0x50, 0x4E, 0x47) -> "image/png"
            at(0, 0xFF, 0xD8, 0xFF) -> "image/jpeg"
            ascii(0, "GIF8") -> "image/gif"
            ascii(0, "RIFF") && ascii(8, "WEBP") -> "image/webp"
            ascii(0, "RIFF") && ascii(8, "WAVE") -> "audio/wav"
            ascii(0, "RIFF") && ascii(8, "AVI ") -> "video/x-msvideo"
            ascii(4, "ftyp") && (ascii(8, "heic") || ascii(8, "heix") || ascii(8, "mif1")) -> "image/heic"
            ascii(4, "ftyp") && ascii(8, "avif") -> "image/avif"
            ascii(4, "ftyp") && ascii(8, "M4A") -> "audio/mp4"
            ascii(4, "ftyp") && ascii(8, "qt") -> "video/quicktime"
            ascii(4, "ftyp") -> "video/mp4"
            at(0, 0x1A, 0x45, 0xDF, 0xA3) -> "video/x-matroska"
            ascii(0, "ID3") || at(0, 0xFF, 0xFB) || at(0, 0xFF, 0xF3) -> "audio/mpeg"
            ascii(0, "fLaC") -> "audio/flac"
            ascii(0, "OggS") -> "audio/ogg"
            ascii(0, "BM") && b.size >= 14 -> "image/bmp"
            at(0, 0x49, 0x49, 0x2A, 0x00) || at(0, 0x4D, 0x4D, 0x00, 0x2A) -> "image/tiff"
            ascii(0, "PK") && at(2, 0x03, 0x04) -> "application/zip"
            ascii(0, "Rar!") -> "application/x-rar-compressed"
            at(0, 0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C) -> "application/x-7z-compressed"
            at(0, 0x1F, 0x8B) -> "application/gzip"
            ascii(0, "BZh") -> "application/x-bzip2"
            at(0, 0xFD, 0x37, 0x7A, 0x58, 0x5A, 0x00) -> "application/x-xz"
            ascii(0, "MZ") -> "application/x-msdownload"
            ascii(0, "wOFF") -> "font/woff"
            ascii(0, "wOF2") -> "font/woff2"
            ascii(0, "OTTO") -> "font/otf"
            else -> null
        }
    }

    companion object {
        /** Bytes of each file read for sniffing. */
        const val HEAD_BYTES = 16
    }
}
