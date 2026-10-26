"""
create_demo_files.py
--------------------
ARISE-I demo environment generator.

Creates a temporary folder (demo_sandbox/) populated with harmless dummy files
covering every extension that ARISE-I knows about, plus some edge cases
(no-extension file, non-ASCII filename, duplicate, broken symlink).

Run this before recording a demo or running ARISE-I --dry-run in CI:

    python scripts/create_demo_files.py              # creates ./demo_sandbox/
    python scripts/create_demo_files.py --output /tmp/my_demo
"""

import argparse
from pathlib import Path


# All extensions ARISE-I supports, with a descriptive filename for each
DEMO_FILES: list[tuple[str, str]] = [
    # Images
    ("holiday_photo.jpg",           ""),
    ("banner.png",                  ""),
    ("logo.svg",                    ""),
    ("avatar.webp",                 ""),
    # Documents
    ("meeting_notes.docx",          ""),
    ("readme.txt",                  ""),
    ("draft_essay.md",              ""),
    # PDFs
    ("annual_report.pdf",           ""),
    ("resume.pdf",                  ""),
    # Spreadsheets
    ("budget_2025.xlsx",            ""),
    ("sales_data.csv",              ""),
    # Presentations
    ("pitch_deck.pptx",             ""),
    # Videos
    ("tutorial.mp4",                ""),
    ("screen_recording.mkv",        ""),
    # Music
    ("soundtrack.mp3",              ""),
    ("podcast_ep01.wav",            ""),
    # Archives
    ("backup.zip",                  ""),
    ("source_code.tar",             ""),
    # Code
    ("main.py",                     "# demo python file\n"),
    ("index.html",                  "<!-- demo html -->\n"),
    ("styles.css",                  "/* demo css */\n"),
    # Installers
    ("setup.exe",                   ""),
    ("app.apk",                     ""),
    # Fonts
    ("OpenSans.ttf",                ""),
    # Ebooks
    ("hitchhikers_guide.epub",      ""),
    # --- Assignments ---
    ("Assignment 1 - Calculus.pdf",      ""),                     # type-first pattern
    ("Assignment 2 - Calculus.docx",     ""),                     # same subject, different type
    ("Lab 3 - Biology.pdf",             ""),                      # lab pattern
    ("Lab Report 1 - Chemistry.pdf",     ""),                     # lab report pattern
    ("Project 2 - Physics.zip",          ""),                     # project pattern
    ("Math - Assignment 4.pdf",          ""),                     # subject-first pattern
    ("Assignment 1.pdf",                 ""),                     # no subject → __Review__
    # --- Edge cases ---
    ("PHOTO_UPPERCASE.JPG",         ""),                     # uppercase extension
    ("résumé_français.pdf",         ""),                     # non-ASCII filename
    ("report_final.pdf",            ""),                     # duplicate of another .pdf
    ("NO_EXTENSION_FILE",           ""),                     # no extension → Others
    ("photo.jpg",                   ""),                     # first copy
    ("photo.jpg",                   ""),                     # duplicate → dedup test
]


def create_demo_sandbox(output_dir: str) -> Path:
    """Create the demo sandbox folder and populate it with dummy files."""
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    created = 0
    for filename, content in DEMO_FILES:
        dest = out / filename
        # If the file already exists (e.g. the duplicate photo.jpg), skip —
        # ARISE-I's dedup logic will handle the copy that is there.
        if not dest.exists():
            dest.write_text(content, encoding="utf-8")
            created += 1

    # Create a broken symlink to verify ARISE-I skips it gracefully (if OS permits)
    broken = out / "broken_link.txt"
    has_symlink = False
    if not broken.exists() and not broken.is_symlink():
        try:
            broken.symlink_to("/nonexistent/target/path")
            has_symlink = True
        except OSError:
            pass  # Windows without SeCreateSymbolicLinkPrivilege

    # Create an empty subfolder (ARISE-I should skip it)
    (out / "empty_subfolder").mkdir(exist_ok=True)

    symlink_note = "1 broken symlink" if has_symlink else "0 symlinks (OS restricted)"
    print(f"[OK]  Demo sandbox ready: {out}")
    print(f"      {created} files created  |  {symlink_note}  |  1 empty subfolder")
    print("\nNext step:")
    print(f"   arise-i --dry-run --path \"{out}\"")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ARISE-I demo file generator — creates a harmless test sandbox."
    )
    parser.add_argument(
        "--output", default="./demo_sandbox",
        help="Where to create the demo folder (default: ./demo_sandbox)",
    )
    args = parser.parse_args()
    create_demo_sandbox(args.output)
