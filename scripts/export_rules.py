"""
ARISE-I — Rules exporter
-------------------------
Writes the classification rules used by the Python engine to a JSON file
that the Android engine loads at runtime, so both apps sort files the same
way without hand-copied tables drifting apart.

    python scripts/export_rules.py           # (re)write the JSON
    python scripts/export_rules.py --check   # exit 1 if the JSON is stale (CI)

Python-only regex syntax is converted to java.util.regex syntax on the way
out: named groups ``(?P<name>...)`` become ``(?<name>...)``.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import assignment_classifier as ac  # noqa: E402
import classifier as cl  # noqa: E402
import file_organizer as fo  # noqa: E402

OUTPUT = ROOT / "android" / "engine" / "src" / "main" / "resources" / "arise-rules.json"
SCHEMA_VERSION = 1


def _java_regex(pattern: str) -> str:
    return pattern.replace("(?P<", "(?<")


def _flags(pattern) -> str:
    import re
    return "i" if pattern.flags & re.IGNORECASE else ""


# Extension → MIME fallback for Android when byte sniffing finds nothing.
# Curated rather than read from the mimetypes module, whose table changes
# between Python versions and with the host's /etc/mime.types — the export
# must be byte-identical wherever --check runs.
MIME_BY_EXTENSION: dict[str, str] = {
    ".3gp": "video/3gpp", ".7z": "application/x-7z-compressed",
    ".aac": "audio/aac", ".apk": "application/vnd.android.package-archive",
    ".avi": "video/x-msvideo", ".avif": "image/avif", ".bmp": "image/bmp",
    ".bz2": "application/x-bzip2", ".css": "text/css", ".csv": "text/csv",
    ".deb": "application/x-deb", ".dmg": "application/x-apple-diskimage",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".epub": "application/epub+zip", ".exe": "application/x-msdownload",
    ".flac": "audio/flac", ".gif": "image/gif", ".gz": "application/gzip",
    ".heic": "image/heic", ".heif": "image/heif", ".htm": "text/html",
    ".html": "text/html", ".ico": "image/vnd.microsoft.icon", ".jpe": "image/jpeg",
    ".jpeg": "image/jpeg", ".jpg": "image/jpeg", ".js": "text/javascript",
    ".json": "application/json", ".m4a": "audio/mp4", ".mid": "audio/midi",
    ".midi": "audio/midi", ".mjs": "text/javascript", ".mkv": "video/x-matroska",
    ".mobi": "application/x-mobipocket-ebook", ".mov": "video/quicktime",
    ".mp3": "audio/mpeg", ".mp4": "video/mp4", ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg", ".odp": "application/vnd.oasis.opendocument.presentation",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odt": "application/vnd.oasis.opendocument.text", ".oga": "audio/ogg",
    ".ogg": "audio/ogg", ".ogv": "video/ogg", ".opus": "audio/opus",
    ".otf": "font/otf", ".pdf": "application/pdf", ".png": "image/png",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".rar": "application/x-rar-compressed", ".rpm": "application/x-rpm",
    ".svg": "image/svg+xml", ".tar": "application/x-tar", ".tif": "image/tiff",
    ".tiff": "image/tiff", ".ttf": "font/ttf", ".txt": "text/plain",
    ".wav": "audio/wav", ".weba": "audio/webm", ".webm": "video/webm",
    ".webp": "image/webp", ".wma": "audio/x-ms-wma", ".wmv": "video/x-ms-wmv",
    ".woff": "font/woff", ".woff2": "font/woff2", ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xml": "application/xml", ".xz": "application/x-xz", ".zip": "application/zip",
}


def build_rules() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": fo.__version__,
        "review_folder": fo.REVIEW_FOLDER,
        "fallback_category": "Others",
        "confidence_threshold": 0.75,
        "badge": {"high": 0.85, "med": 0.65},
        # Literal confidences from classifier.SmartClassifier's layer methods.
        "layer_confidence": {
            "extension_hit": 0.92,
            "extension_miss": 0.10,
            "mime_exact": 0.88,
            "mime_miss": 0.05,
            "heuristic_miss": 0.05,
            "model_miss": 0.05,
        },
        "categories": fo.DEFAULT_CATEGORIES,
        "mime_exact": dict(sorted(cl._MIME_EXACT.items())),
        "mime_prefix": [
            {"prefix": p, "category": c, "confidence": conf}
            for p, c, conf in cl._MIME_PREFIX
        ],
        "heuristics": [
            {"pattern": _java_regex(p.pattern), "flags": _flags(p),
             "category": c, "confidence": conf}
            for p, c, conf in cl._HEURISTICS
        ],
        "assignment": {
            "types": ac._ASSIGNMENT_TYPES,
            "type_first": [_java_regex(p.pattern) for p in ac._PATTERNS_TYPE_FIRST],
            "subject_first": [_java_regex(p.pattern) for p in ac._PATTERNS_SUBJECT_FIRST],
            "no_subject": [_java_regex(p.pattern) for p in ac._PATTERNS_NO_SUBJECT],
            "confidence": {"type_first": 0.95, "subject_first": 0.93, "no_subject": 0.80},
            "subject_strip": " -–—_.",
        },
        "skip": {
            "own_files": sorted(fo._OWN_FILES),
            "system_files": sorted(fo._SYSTEM_FILES),
            "partial_suffixes": sorted(fo._PARTIAL_SUFFIXES),
        },
        "learning": {
            "min_samples": 20,
            "retrain_threshold": 50,
            "min_class_samples": 2,
            "alpha": 0.5,
            "max_features": 8000,
        },
        "mime_by_extension": dict(sorted(MIME_BY_EXTENSION.items())),
    }


def render() -> str:
    return json.dumps(build_rules(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--check", action="store_true",
                        help="fail if the exported JSON is out of date")
    args = parser.parse_args(argv)

    text = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != text:
            print(f"{OUTPUT.relative_to(ROOT)} is stale — run scripts/export_rules.py",
                  file=sys.stderr)
            return 1
        print("rules up to date")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
