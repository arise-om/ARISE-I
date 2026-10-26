"""
ARISE-I — Assignment Classifier
---------------------------------
Autonomous File Organization Unit: Assignment Detection Engine.
Built by Om // Ironlabs.tech

Detects assignment-type files and extracts structured metadata
(subject, assignment type, assignment number) from filenames.

Supported assignment types: assignment, lab, lab report, project.

Filename patterns recognised (case-insensitive):
    Assignment 1 - Calculus.pdf        → subject="Calculus", type="Assignment", num=1
    Lab 3 - Biology.docx               → subject="Biology",  type="Lab",        num=3
    Lab Report 2 - Chemistry.pdf       → subject="Chemistry", type="Lab Report", num=2
    Project 1 - Physics.zip            → subject="Physics",   type="Project",    num=1
    Math - Assignment 4.pdf            → subject="Math",      type="Assignment", num=4
    Assignment 1.pdf  (no subject)     → subject=None  →  sent to __Review__/
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AssignmentInfo:
    """Parsed assignment metadata from a filename."""

    subject: Optional[str]       # e.g. "Calculus", None if missing
    assignment_type: str         # "Assignment", "Lab", "Lab Report", "Project"
    number: int                  # e.g. 1, 2, 3
    confidence: float            # 0.0–1.0

    @property
    def folder_name(self) -> str:
        """Human-readable folder label, e.g. 'Assignment 1', 'Lab 3'."""
        return f"{self.assignment_type} {self.number}"


# ── Pattern building ─────────────────────────────────────────────────────────
# Keywords ordered longest-first so "lab report" is tried before "lab".

_ASSIGNMENT_TYPES = ["lab report", "assignment", "project", "lab"]

# Pattern group 1: "<Type> <N> - <Subject>"
# e.g. "Assignment 1 - Calculus", "Lab3 - Biology"
_PATTERNS_TYPE_FIRST: list[re.Pattern[str]] = [
    re.compile(
        # A second " - " ends the subject: "… - Calculus - Solutions"
        rf"(?P<type>{kw})\s*(?P<num>\d+)\s*[-–—]\s*(?P<subject>.+?)(?:\s+[-–—]\s+.*)?$",
        re.IGNORECASE,
    )
    for kw in _ASSIGNMENT_TYPES
]

# Pattern group 2: "<Subject> - <Type> <N>"
# e.g. "Math - Assignment 4", "Chemistry - Lab 5"
_PATTERNS_SUBJECT_FIRST: list[re.Pattern[str]] = [
    re.compile(
        rf"(?P<subject>.+?)\s*[-–—]\s*(?P<type>{kw})\s*(?P<num>\d+)",
        re.IGNORECASE,
    )
    for kw in _ASSIGNMENT_TYPES
]

# Pattern group 3: "<Type> <N>" with no subject
# e.g. "Assignment 1", "Lab 3"
_PATTERNS_NO_SUBJECT: list[re.Pattern[str]] = [
    re.compile(
        rf"^(?P<type>{kw})\s*(?P<num>\d+)$",
        re.IGNORECASE,
    )
    for kw in _ASSIGNMENT_TYPES
]


_COPY_SUFFIX = re.compile(r"\s*\(\d+\)$")


# ── Public API ───────────────────────────────────────────────────────────────

def parse_assignment(path: Path) -> Optional[AssignmentInfo]:
    """Attempt to extract assignment metadata from a filename.

    Parameters
    ----------
    path : Path
        File path whose *stem* (filename without extension) is analysed.

    Returns
    -------
    AssignmentInfo | None
        Parsed metadata if the filename matches an assignment pattern,
        otherwise ``None`` (the file is not an assignment).
    """
    # Browsers and ARISE-I itself add " (1)" to duplicate copies; without
    # stripping it, "Lab 2 - Bio (1)" would file under a "Bio (1)" subject.
    stem = _COPY_SUFFIX.sub("", path.stem).strip()

    # Group 1 — type-first patterns (highest confidence: most explicit)
    for pattern in _PATTERNS_TYPE_FIRST:
        m = pattern.match(stem)
        if m:
            return AssignmentInfo(
                subject=_normalize_subject(m.group("subject")),
                assignment_type=_normalize_type(m.group("type")),
                number=int(m.group("num")),
                confidence=0.95,
            )

    # Group 2 — subject-first patterns
    for pattern in _PATTERNS_SUBJECT_FIRST:
        m = pattern.match(stem)
        if m:
            return AssignmentInfo(
                subject=_normalize_subject(m.group("subject")),
                assignment_type=_normalize_type(m.group("type")),
                number=int(m.group("num")),
                confidence=0.93,
            )

    # Group 3 — no-subject patterns (will route to __Review__)
    for pattern in _PATTERNS_NO_SUBJECT:
        m = pattern.match(stem)
        if m:
            return AssignmentInfo(
                subject=None,
                assignment_type=_normalize_type(m.group("type")),
                number=int(m.group("num")),
                confidence=0.80,
            )

    return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_subject(raw: str) -> Optional[str]:
    """Clean and Title Case the subject name.  Returns None if empty."""
    cleaned = raw.strip(" -–—_.")
    if not cleaned:
        return None
    return cleaned.title()


def _normalize_type(raw: str) -> str:
    """Normalize assignment type to Title Case."""
    return raw.strip().title()
