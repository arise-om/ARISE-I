"""
ARISE-I — Smart Classifier
---------------------------
Autonomous File Organization Unit: AI Classification Engine.
Built by Om // Ironlabs.tech

Multi-layer file classification with confidence scoring.

Layers (highest priority first):
  1. Extension map       — O(1) lookup, conf 0.92
  2. MIME type sniff     — byte-level or stdlib guess, conf 0.88
  3. Filename heuristics — regex patterns, conf 0.76–0.88
  4. ML model (opt.)     — sklearn NB trained on user feedback

Files with confidence < threshold go to __Review__/ instead of
being silently mis-sorted.  The threshold is configurable (default 0.75).

Optional dependencies (install with:  pip install arise-i[ai]):
    filetype   — byte-level MIME detection (more accurate than stdlib)
    scikit-learn — ML model layer (Layer 4)
"""

import logging
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from arise_i.constants import APP_DIR, REVIEW_FOLDER

logger = logging.getLogger("arise_i.classifier")

# ── Optional: byte-level MIME detection ─────────────────────────────────────
try:
    import filetype as _filetype  # noqa: F401
    _FILETYPE_AVAILABLE = True
except ImportError:
    _FILETYPE_AVAILABLE = False

# ── Optional: ML model layer ─────────────────────────────────────────────────
try:
    import sklearn  # noqa: F401
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


# ── MIME exact-match table ───────────────────────────────────────────────────

_MIME_EXACT: dict[str, str] = {
    "application/pdf":                     "PDFs",
    "application/epub+zip":                "Ebooks",
    "application/x-mobipocket-ebook":      "Ebooks",
    "application/zip":                     "Archives",
    "application/x-rar-compressed":        "Archives",
    "application/x-rar":                   "Archives",
    "application/x-7z-compressed":         "Archives",
    "application/x-tar":                   "Archives",
    "application/gzip":                    "Archives",
    "application/x-bzip2":                 "Archives",
    "application/x-xz":                    "Archives",
    "application/msword":                  "Documents",
    "application/vnd.ms-excel":            "Spreadsheets",
    "application/vnd.ms-powerpoint":       "Presentations",
    "application/json":                    "Code",
    "application/xml":                     "Code",
    "application/javascript":              "Code",
    "application/x-msdownload":            "Installers",
    "application/vnd.android.package-archive": "Installers",
    "application/x-deb":                   "Installers",
    "application/x-rpm":                   "Installers",
    "application/x-apple-diskimage":       "Installers",
}

# (prefix, category, confidence)
_MIME_PREFIX: list[tuple[str, str, float]] = [
    ("image/",           "Images",        0.90),
    ("video/",           "Videos",        0.90),
    ("audio/",           "Music",         0.90),
    ("font/",            "Fonts",         0.88),
    ("application/font", "Fonts",         0.88),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml",
                         "Documents",     0.92),
    ("application/vnd.openxmlformats-officedocument.spreadsheetml",
                         "Spreadsheets",  0.92),
    ("application/vnd.openxmlformats-officedocument.presentationml",
                         "Presentations", 0.92),
    ("application/vnd.oasis.opendocument.text",        "Documents",    0.90),
    ("application/vnd.oasis.opendocument.spreadsheet", "Spreadsheets", 0.90),
    ("text/html",        "Code",          0.78),
    ("text/css",         "Code",          0.78),
    ("text/javascript",  "Code",          0.78),
    ("text/plain",       "Documents",     0.55),  # intentionally low — ambiguous
]

# ── Assignment detection ─────────────────────────────────────────────────────
from arise_i.core.assignment import AssignmentInfo, parse_assignment  # noqa: E402

# ── Filename heuristics ──────────────────────────────────────────────────────

_HEURISTICS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r'screenshot|screen.?cap|screen.?grab', re.I), "Images",     0.82),
    (re.compile(r'\b(IMG|DSC|DCIM|PHOTO)[-_]\d{4,}',   re.I), "Images",     0.80),
    (re.compile(r'wallpaper|background|avatar',          re.I), "Images",     0.78),
    (re.compile(r'invoice|receipt|statement|billing',    re.I), "Documents",  0.84),
    (re.compile(r'resume|curriculum.?vitae|\bcv\b',      re.I), "Documents",  0.88),
    (re.compile(r'lecture|notes?',                        re.I), "Documents",  0.76),
    (re.compile(r'setup[-_ v]\d|installer[-_ ]',         re.I), "Installers", 0.80),
    (re.compile(r'\bebook\b|e-book',                     re.I), "Ebooks",     0.82),
    (re.compile(r'soundtrack|ost\b|playlist|album',      re.I), "Music",      0.78),
    (re.compile(r'tutorial|walkthrough|gameplay|playthrough', re.I), "Videos", 0.76),
    (re.compile(r'\bfonts?\b|typeface',                  re.I), "Fonts",      0.82),
]


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """Outcome of classifying a single file."""

    category:     str
    confidence:   float                              # 0.0 – 1.0
    layer:        str                                # which layer decided
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    assignment_info: "AssignmentInfo | None" = field(default=None)

    @property
    def badge(self) -> str:
        """Human-readable confidence label for the GUI."""
        if self.confidence >= 0.85: return "HIGH"
        if self.confidence >= 0.65: return "MED"
        return "LOW"


# ── Feature extractor for ML ─────────────────────────────────────────────────

def extract_text_features(path: Path) -> str:
    """Produce a text bag-of-words representation of a file path."""
    parts: list[str] = []
    ext = path.suffix.lower().lstrip(".")
    if ext:
        parts.extend([ext] * 3)   # weight extension heavily
    tokens = re.split(r"[^a-zA-Z0-9]+", path.stem.lower())
    parts.extend(t for t in tokens if len(t) > 1)
    return " ".join(parts)


# ── SmartClassifier ──────────────────────────────────────────────────────────

class SmartClassifier:
    """Multi-layer file classifier with confidence scoring.

    Instantiate once per session and reuse.  Falls back gracefully when
    optional packages (filetype, scikit-learn) are not installed.

    Parameters
    ----------
    categories          : dict mapping category names → list of extensions
    confidence_threshold: files below this go to __Review__/ (default 0.75)
    model_path          : override for the pickled ML model location
    """

    REVIEW_FOLDER = REVIEW_FOLDER

    def __init__(
        self,
        categories: dict[str, list[str]],
        confidence_threshold: float = 0.75,
        model_path: Optional[Path] = None,
    ) -> None:
        self.categories            = categories
        self.confidence_threshold  = confidence_threshold
        self._model_path           = model_path or (APP_DIR / "model.pkl")
        self._ext_map              = self._build_ext_map()
        self._ml_pipeline: Optional[object] = None
        self._ml_labels:   list[str]        = []
        self._model_mtime: Optional[float]  = None
        self._load_model()

    # ── setup ────────────────────────────────────────────────────────────────

    def _build_ext_map(self) -> dict[str, str]:
        m: dict[str, str] = {}
        for cat, exts in self.categories.items():
            for ext in exts:
                m[ext.lower()] = cat
        return m

    def _current_model_mtime(self) -> Optional[float]:
        try:
            return self._model_path.stat().st_mtime
        except OSError:
            return None

    def _load_model(self) -> None:
        self._model_mtime = self._current_model_mtime()
        if not _SKLEARN_AVAILABLE or self._model_mtime is None:
            return
        try:
            import pickle as _pickle
            with open(self._model_path, "rb") as fh:
                data = _pickle.load(fh)
            if isinstance(data, dict) and "pipeline" in data:
                self._ml_pipeline = data["pipeline"]
                self._ml_labels   = list(data.get("labels", []))
                logger.info("ML model loaded (%d classes)", len(self._ml_labels))
        except Exception as exc:
            logger.warning("Could not load ML model: %s", exc)

    def reload_model(self) -> None:
        """Hot-reload model after retraining."""
        self._ml_pipeline = None
        self._ml_labels   = []
        self._load_model()

    def model_is_stale(self) -> bool:
        """True when model.pkl changed on disk since it was last loaded."""
        return self._current_model_mtime() != self._model_mtime

    # ── public API ───────────────────────────────────────────────────────────

    def classify(self, path: Path) -> ClassificationResult:
        """Classify *path* through all layers; return the highest-confidence result."""
        # ── Assignment detection (runs alongside other layers) ───────────
        _assignment_info: "AssignmentInfo | None" = parse_assignment(path)

        ext_result = self._by_extension(path)
        results = [
            ext_result,
            self._by_mime(path),
            self._by_heuristics(path),
        ]

        # If an assignment pattern matched, inject a high-confidence result
        # whose *category* is the file-type folder (from extension) so the
        # organiser can build:  Subject / Assignment N / <file-type> /
        if _assignment_info is not None:
            file_type_cat = ext_result.category if ext_result.confidence > 0.5 else "Others"
            results.append(ClassificationResult(
                category=file_type_cat,
                confidence=_assignment_info.confidence,
                layer="assignment",
                assignment_info=_assignment_info,
            ))

        if self._ml_pipeline is not None:
            results.append(self._by_model(path))

        winner = max(results, key=lambda r: r.confidence)

        # Propagate assignment_info to the winner even if the assignment
        # layer didn't have the highest confidence (belt-and-suspenders).
        if _assignment_info is not None and winner.assignment_info is None:
            winner.assignment_info = _assignment_info

        # Build alternatives list (distinct categories, sorted by confidence)
        seen: set[str] = {winner.category}
        alts: list[tuple[str, float]] = []
        for r in sorted(results, key=lambda r: -r.confidence):
            if r.category not in seen:
                alts.append((r.category, r.confidence))
                seen.add(r.category)
        winner.alternatives = alts[:3]

        # Below threshold → quarantine in Review folder
        if winner.confidence < self.confidence_threshold:
            return ClassificationResult(
                category=self.REVIEW_FOLDER,
                confidence=winner.confidence,
                layer="review_fallback",
                alternatives=[(winner.category, winner.confidence)] + alts[:2],
                assignment_info=_assignment_info,
            )

        return winner

    # ── layers ───────────────────────────────────────────────────────────────

    def _by_extension(self, path: Path) -> ClassificationResult:
        ext = path.suffix.lower()
        if ext and ext in self._ext_map:
            return ClassificationResult(
                category=self._ext_map[ext], confidence=0.92, layer="extension"
            )
        return ClassificationResult(category="Others", confidence=0.10, layer="extension")

    def _by_mime(self, path: Path) -> ClassificationResult:
        mime = self._detect_mime(path)
        if not mime:
            return ClassificationResult(category="Others", confidence=0.05, layer="mime")

        if mime in _MIME_EXACT:
            cat = _MIME_EXACT[mime]
            cat = cat if cat in self.categories else "Others"
            return ClassificationResult(category=cat, confidence=0.88, layer="mime")

        for prefix, cat, conf in _MIME_PREFIX:
            if mime.startswith(prefix):
                cat = cat if cat in self.categories else "Others"
                return ClassificationResult(category=cat, confidence=conf, layer="mime")

        return ClassificationResult(category="Others", confidence=0.05, layer="mime")

    def _detect_mime(self, path: Path) -> Optional[str]:
        if _FILETYPE_AVAILABLE:
            try:
                import filetype as _ft
                kind = _ft.guess(str(path))
                if kind:
                    return kind.mime
            except Exception:
                pass
        try:
            mime, _ = mimetypes.guess_type(str(path))
            return mime
        except Exception:
            return None

    def _by_heuristics(self, path: Path) -> ClassificationResult:
        for pattern, cat, conf in _HEURISTICS:
            if pattern.search(path.name):
                cat = cat if cat in self.categories else "Others"
                return ClassificationResult(category=cat, confidence=conf, layer="heuristic")
        return ClassificationResult(category="Others", confidence=0.05, layer="heuristic")

    def _by_model(self, path: Path) -> ClassificationResult:
        if not _SKLEARN_AVAILABLE or self._ml_pipeline is None:
            return ClassificationResult(category="Others", confidence=0.05, layer="ml_model")
        try:
            text  = extract_text_features(path)
            proba = self._ml_pipeline.predict_proba([text])[0]
            best  = int(proba.argmax())
            conf  = float(proba[best])
            cat   = self._ml_labels[best]
            if cat == self.REVIEW_FOLDER or cat not in self.categories:
                # Models trained before v2.1 could learn the Review quarantine
                # as a label, and a config change can remove a category.
                return ClassificationResult(category="Others", confidence=0.05, layer="ml_model")
            alts  = sorted(
                [(self._ml_labels[i], float(proba[i]))
                 for i in range(len(proba)) if i != best],
                key=lambda x: -x[1],
            )[:3]
            return ClassificationResult(
                category=cat, confidence=conf, layer="ml_model", alternatives=alts
            )
        except Exception as exc:
            logger.warning("ML prediction failed: %s", exc)
            return ClassificationResult(category="Others", confidence=0.05, layer="ml_model")


# ── Module-level singleton helper ────────────────────────────────────────────

_singleton: Optional[SmartClassifier] = None


def get_classifier(
    categories: dict[str, list[str]],
    confidence_threshold: float = 0.75,
) -> SmartClassifier:
    """Return a shared SmartClassifier instance (recreated on category change).

    The shared instance picks up a retrained model.pkl automatically, so a
    retrain from the learning store or health monitor takes effect on the
    very next run instead of after an app restart.
    """
    global _singleton
    if _singleton is None or _singleton.categories != categories:
        _singleton = SmartClassifier(
            categories=categories,
            confidence_threshold=confidence_threshold,
        )
    else:
        _singleton.confidence_threshold = confidence_threshold
        if _singleton.model_is_stale():
            _singleton.reload_model()
    return _singleton
