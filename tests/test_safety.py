"""
tests/test_safety.py
--------------------
Files and folders ARISE-I must never touch, and config discovery.

Covers v2.1 fixes: desktop.ini / config / in-progress downloads were being
moved, drive roots and the home folder were accepted by the CLI, a file path
as target crashed, and a config placed in the target folder was ignored.
"""

import logging
import os
import subprocess
from pathlib import Path

import pytest

from file_organizer import (
    CONFIG_FILENAME,
    DEFAULT_CATEGORIES,
    is_protected_dir,
    load_categories,
    organize_folder,
    skip_reason,
)


@pytest.fixture(autouse=True)
def reset_logger():
    logger = logging.getLogger("arise_i")
    yield
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


class TestSkipRules:

    @pytest.mark.parametrize("name", [
        "desktop.ini", "Desktop.INI", "Thumbs.db",          # OS metadata
        CONFIG_FILENAME,                                     # our own config
        "movie.mp4.crdownload", "big.iso.part",              # browser downloads
        "file.zip.download", "setup.exe.opdownload", "x.tmp",
        "~$report.docx",                                     # Office lock file
    ])
    def test_protected_files_stay_in_place(self, tmp_path, name):
        (tmp_path / name).write_text("x")
        (tmp_path / "real.pdf").write_text("x")

        organize_folder(str(tmp_path), dry_run=False)

        assert (tmp_path / name).exists(), f"{name} must not be moved"
        assert (tmp_path / "PDFs" / "real.pdf").exists()

    def test_skip_reason_none_for_normal_file(self, tmp_path):
        f = tmp_path / "holiday.jpg"
        f.write_text("x")
        assert skip_reason(f) is None

    @pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
    def test_windows_hidden_attribute_respected(self, tmp_path):
        f = tmp_path / "secret.pdf"
        f.write_text("x")
        subprocess.run(["attrib", "+h", str(f)], check=True)
        try:
            organize_folder(str(tmp_path), dry_run=False)
            assert f.exists()
        finally:
            subprocess.run(["attrib", "-h", str(f)], check=False)


class TestTargetValidation:

    def test_home_folder_is_protected(self):
        assert is_protected_dir(Path.home())

    def test_drive_root_is_protected(self, tmp_path):
        assert is_protected_dir(Path(tmp_path.anchor))

    def test_regular_folder_is_not_protected(self, tmp_path):
        assert not is_protected_dir(tmp_path)

    def test_organize_refuses_home_folder(self):
        messages: list[str] = []
        stats = organize_folder(str(Path.home()), dry_run=True, log_callback=messages.append)
        assert stats.total_files() == 0
        assert any("Refusing" in m for m in messages)

    def test_file_path_as_target_is_reported_not_crashing(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x")
        messages: list[str] = []
        stats = organize_folder(str(f), log_callback=messages.append)
        assert stats.total_files() == 0
        assert any("Not a folder" in m for m in messages)
        assert f.exists()


class TestConfigDiscovery:

    def test_config_in_target_folder_is_used(self, tmp_path, monkeypatch):
        (tmp_path / CONFIG_FILENAME).write_text("Work:\n  - .pdf\n")
        monkeypatch.chdir(tmp_path.parent)
        assert load_categories(None, tmp_path) == {"Work": [".pdf"]}

    def test_target_config_beats_cwd_config(self, tmp_path, monkeypatch):
        target, cwd = tmp_path / "target", tmp_path / "cwd"
        target.mkdir(); cwd.mkdir()
        (target / CONFIG_FILENAME).write_text("Target:\n  - .pdf\n")
        (cwd / CONFIG_FILENAME).write_text("Cwd:\n  - .pdf\n")
        monkeypatch.chdir(cwd)
        assert list(load_categories(None, target)) == ["Target"]

    def test_falls_back_to_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert load_categories(None, tmp_path) is DEFAULT_CATEGORIES

    def test_extensions_are_normalized(self, tmp_path):
        cfg = tmp_path / CONFIG_FILENAME
        cfg.write_text("Docs: PDF\nPics:\n  - .JPG\n  - png\nBroken: 42\n")
        assert load_categories(cfg) == {"Docs": [".pdf"], "Pics": [".jpg", ".png"]}

    def test_config_drives_the_organizer(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text("Work:\n  - .pdf\n")
        (tmp_path / "plan.pdf").write_text("x")
        organize_folder(str(tmp_path), categories=load_categories(None, tmp_path))
        assert (tmp_path / "Work" / "plan.pdf").exists()
        assert (tmp_path / CONFIG_FILENAME).exists()


class TestCli:

    @pytest.fixture(autouse=True)
    def no_boot_delay(self, monkeypatch):
        monkeypatch.setattr("file_organizer.boot_sequence", lambda dry_run=False: None)

    def test_dry_run_exit_code_and_no_moves(self, tmp_path):
        from file_organizer import main
        (tmp_path / "a.pdf").write_text("x")
        assert main(["--path", str(tmp_path), "--dry-run"]) == 0
        assert (tmp_path / "a.pdf").exists()

    def test_live_run_then_undo(self, tmp_path):
        from file_organizer import main
        (tmp_path / "a.pdf").write_text("x")
        assert main(["--path", str(tmp_path)]) == 0
        assert (tmp_path / "PDFs" / "a.pdf").exists()
        assert main(["--path", str(tmp_path), "--undo"]) == 0
        assert (tmp_path / "a.pdf").exists()
