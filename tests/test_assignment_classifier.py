"""
tests/test_assignment_classifier.py
------------------------------------
Tests for the arise_i.core.assignment module: filename pattern parsing,
metadata extraction, and edge-case handling.
"""

import pytest
from pathlib import Path

from arise_i.core.assignment import AssignmentInfo, parse_assignment


# ── Unit tests for parse_assignment ──────────────────────────────────────────

class TestParseAssignmentTypeFirst:
    """Patterns: '<Type> <N> - <Subject>'"""

    @pytest.mark.parametrize("filename,expected_subject,expected_type,expected_num", [
        ("Assignment 1 - Calculus.pdf",          "Calculus",       "Assignment", 1),
        ("Assignment2 - Linear Algebra.docx",    "Linear Algebra", "Assignment", 2),
        ("Assignment 10 - History.txt",          "History",        "Assignment", 10),
        ("Lab 3 - Biology.pdf",                  "Biology",        "Lab",        3),
        ("Lab Report 2 - Chemistry.pdf",         "Chemistry",      "Lab Report", 2),
        ("Project 1 - Physics.zip",              "Physics",        "Project",    1),
    ])
    def test_type_first_patterns(self, filename, expected_subject, expected_type, expected_num):
        info = parse_assignment(Path(filename))
        assert info is not None, f"Expected match for {filename!r}"
        assert info.subject == expected_subject
        assert info.assignment_type == expected_type
        assert info.number == expected_num
        assert info.confidence == 0.95


class TestParseAssignmentSubjectFirst:
    """Patterns: '<Subject> - <Type> <N>'"""

    @pytest.mark.parametrize("filename,expected_subject,expected_type,expected_num", [
        ("Math - Assignment 4.pdf",              "Math",           "Assignment", 4),
        ("Chemistry - Lab 5.docx",               "Chemistry",      "Lab",        5),
        ("Physics - Project 3.py",               "Physics",        "Project",    3),
        ("Organic Chemistry - Lab Report 1.pdf", "Organic Chemistry", "Lab Report", 1),
    ])
    def test_subject_first_patterns(self, filename, expected_subject, expected_type, expected_num):
        info = parse_assignment(Path(filename))
        assert info is not None, f"Expected match for {filename!r}"
        assert info.subject == expected_subject
        assert info.assignment_type == expected_type
        assert info.number == expected_num
        assert info.confidence == 0.93


class TestParseAssignmentNoSubject:
    """Patterns: '<Type> <N>' (no subject → subject is None)"""

    @pytest.mark.parametrize("filename,expected_type,expected_num", [
        ("Assignment 1.pdf",     "Assignment", 1),
        ("Lab 3.docx",           "Lab",        3),
        ("Project 7.zip",        "Project",    7),
        ("Lab Report 2.pdf",     "Lab Report", 2),
    ])
    def test_no_subject_patterns(self, filename, expected_type, expected_num):
        info = parse_assignment(Path(filename))
        assert info is not None, f"Expected match for {filename!r}"
        assert info.subject is None
        assert info.assignment_type == expected_type
        assert info.number == expected_num
        assert info.confidence == 0.80


class TestParseAssignmentCaseInsensitive:
    """All patterns should be case-insensitive."""

    @pytest.mark.parametrize("filename", [
        "ASSIGNMENT 1 - MATH.pdf",
        "assignment 1 - math.pdf",
        "Assignment 1 - Math.pdf",
        "LAB 2 - PHYSICS.pdf",
        "lab report 1 - chemistry.pdf",
        "PROJECT 3 - CS.zip",
    ])
    def test_case_insensitive(self, filename):
        info = parse_assignment(Path(filename))
        assert info is not None, f"Expected case-insensitive match for {filename!r}"


class TestParseAssignmentNonMatching:
    """Files that should NOT match any assignment pattern."""

    @pytest.mark.parametrize("filename", [
        "photo.jpg",
        "resume.pdf",
        "meeting_notes.docx",
        "budget_2025.xlsx",
        "main.py",
        "homework 1 - math.pdf",       # 'homework' not a supported keyword
        "test 3 - biology.pdf",         # 'test' not a supported keyword
        "quiz 2 - history.pdf",         # 'quiz' not a supported keyword
        "notes_chapter_3.txt",          # no assignment keyword
        "lecture_slides.pptx",          # no assignment keyword
    ])
    def test_non_assignment_returns_none(self, filename):
        assert parse_assignment(Path(filename)) is None


class TestAssignmentInfoProperties:
    """Test AssignmentInfo dataclass properties."""

    def test_folder_name(self):
        info = AssignmentInfo(
            subject="Math", assignment_type="Assignment", number=3, confidence=0.95
        )
        assert info.folder_name == "Assignment 3"

    def test_folder_name_lab_report(self):
        info = AssignmentInfo(
            subject="Chemistry", assignment_type="Lab Report", number=1, confidence=0.95
        )
        assert info.folder_name == "Lab Report 1"

    def test_confidence_ordering(self):
        """Type-first > subject-first > no-subject."""
        info_type_first = parse_assignment(Path("Assignment 1 - Math.pdf"))
        info_subj_first = parse_assignment(Path("Math - Assignment 1.pdf"))
        info_no_subject = parse_assignment(Path("Assignment 1.pdf"))

        assert info_type_first is not None
        assert info_subj_first is not None
        assert info_no_subject is not None
        assert info_type_first.confidence > info_subj_first.confidence > info_no_subject.confidence

    def test_subject_title_case_normalization(self):
        """Subjects should be Title Cased."""
        info = parse_assignment(Path("assignment 1 - organic chemistry.pdf"))
        assert info is not None
        assert info.subject == "Organic Chemistry"

    def test_type_title_case_normalization(self):
        """Types should be Title Cased."""
        info = parse_assignment(Path("lab report 2 - chemistry.pdf"))
        assert info is not None
        assert info.assignment_type == "Lab Report"


class TestParseAssignmentEdgeCases:
    """Edge cases and boundary conditions."""

    def test_en_dash_separator(self):
        """Supports en-dash as separator."""
        info = parse_assignment(Path("Assignment 1 \u2013 Calculus.pdf"))
        assert info is not None
        assert info.subject == "Calculus"

    def test_em_dash_separator(self):
        """Supports em-dash as separator."""
        info = parse_assignment(Path("Assignment 1 \u2014 Calculus.pdf"))
        assert info is not None
        assert info.subject == "Calculus"

    def test_no_space_between_type_and_number(self):
        """e.g. 'Assignment2 - Calculus.pdf'"""
        info = parse_assignment(Path("Assignment2 - Calculus.pdf"))
        assert info is not None
        assert info.number == 2
        assert info.subject == "Calculus"

    def test_large_assignment_number(self):
        info = parse_assignment(Path("Assignment 99 - Math.pdf"))
        assert info is not None
        assert info.number == 99

    def test_lab_report_before_lab(self):
        """'Lab Report' should match before 'Lab' (longest match first)."""
        info = parse_assignment(Path("Lab Report 1 - Chemistry.pdf"))
        assert info is not None
        assert info.assignment_type == "Lab Report"
        assert info.number == 1


class TestOrganizeAssignmentsIntegration:
    """Integration tests verifying end-to-end folder structuring and undo."""

    def test_assignments_nested_folders(self, tmp_path):
        from arise_i.core.organizer import organize_folder

        (tmp_path / "Assignment 1 - Calculus.pdf").write_text("calc 1")
        (tmp_path / "Assignment 2 - Calculus.docx").write_text("calc 2")
        (tmp_path / "Lab 3 - Biology.pdf").write_text("bio 3")
        (tmp_path / "Math - Assignment 4.pdf").write_text("math 4")
        (tmp_path / "Project 2 - Physics.zip").write_text("phys 2")
        (tmp_path / "Assignment 1.pdf").write_text("no subject")
        (tmp_path / "regular_report.pdf").write_text("regular")

        organize_folder(str(tmp_path), dry_run=False)

        # Subject / Assignment N / FileType
        assert (tmp_path / "Calculus" / "Assignment 1" / "PDFs" / "Assignment 1 - Calculus.pdf").exists()
        assert (tmp_path / "Calculus" / "Assignment 2" / "Documents" / "Assignment 2 - Calculus.docx").exists()
        assert (tmp_path / "Biology" / "Lab 3" / "PDFs" / "Lab 3 - Biology.pdf").exists()
        assert (tmp_path / "Math" / "Assignment 4" / "PDFs" / "Math - Assignment 4.pdf").exists()
        assert (tmp_path / "Physics" / "Project 2" / "Archives" / "Project 2 - Physics.zip").exists()

        # No subject -> __Review__
        assert (tmp_path / "__Review__" / "Assignment 1.pdf").exists()

        # Non-assignment -> standard category
        assert (tmp_path / "PDFs" / "regular_report.pdf").exists()

    def test_assignments_undo(self, tmp_path):
        from arise_i.core.organizer import organize_folder, undo_last_run

        test_file = tmp_path / "Assignment 1 - Calculus.pdf"
        test_file.write_text("calc 1 content")

        organize_folder(str(tmp_path), dry_run=False)
        moved_file = tmp_path / "Calculus" / "Assignment 1" / "PDFs" / "Assignment 1 - Calculus.pdf"
        assert moved_file.exists()
        assert not test_file.exists()

        # Undo
        undo_last_run(str(tmp_path))
        assert test_file.exists()
        assert test_file.read_text() == "calc 1 content"

