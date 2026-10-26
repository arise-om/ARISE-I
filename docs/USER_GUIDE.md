# ARISE-I User Guide

ARISE-I sorts a messy folder — usually Downloads — into tidy category folders,
on your computer only. Nothing is ever deleted, and every run can be undone.

**Contents:** [Install](#install) · [The window](#the-window) ·
[Review Queue](#review-queue) · [Auto-Sort](#auto-sort) ·
[Keyboard shortcuts](#keyboard-shortcuts) · [Command line](#command-line) ·
[Custom categories](#custom-categories) · [Plugins](#plugins) ·
[Troubleshooting](#troubleshooting) · [FAQ](#faq)

---

## Install

### Download (recommended)

Get the latest build from
[GitHub Releases](https://github.com/arise-om/ARISE-I/releases):

| System | File | Then |
|---|---|---|
| Windows | `ARISE-I-Setup-<version>-Windows.exe` | Run the installer |
| macOS | `ARISE-I-macOS.zip` | Unzip and drag **ARISE-I.app** to Applications |
| Linux | `ARISE-I-Linux.tar.gz` | Extract and run `ARISE-I/ARISE-I` |

The first time you open an unsigned build, macOS asks you to approve it in
**System Settings → Privacy & Security**, and Windows SmartScreen may show
**More info → Run anyway**.

### From source

You need Python 3.10 or newer, with tkinter (bundled on Windows and with the
python.org macOS installer; on Linux, e.g. `sudo apt install python3-tk`).

```bash
git clone https://github.com/arise-om/ARISE-I.git
cd ARISE-I
bash scripts/install.sh          # Linux / macOS
scripts\install.bat              # Windows
```

The installer creates a private virtual environment (it never touches your
system Python packages), asks whether to add the optional AI extras, and adds
an app-menu / desktop shortcut. Afterwards `scripts/start.sh` or
`scripts\start.bat` launches the app.

---

## The window

On first launch a short welcome screen asks which folder to organize
(Downloads is suggested). You can change it any time.

| Area | What it does |
|---|---|
| **Folder field** | The folder ARISE-I works on. Type a path or click **Browse…**; **↗** opens it in your file manager. The line below shows how many loose files are ready to sort, or what is wrong with the path. |
| **🔎 Preview** | Shows exactly what would move — nothing is touched. |
| **✨ Organize Now** | Sorts the folder (after a confirmation). |
| **↩ Undo** | Puts the files from the last run (or last Review decision) back where they were. |
| **Activity** | Live log of every file: where it went and how confident ARISE-I was (`HIGH` / `MED` / `LOW`). |
| **History** | Past runs in this folder, newest first, with a per-category summary. |
| **Last Run** | Totals and a per-category chart for the latest preview or run. |
| **Review Queue** | Files ARISE-I wasn't sure about — see below. |
| **Auto-Sort switch** | Sorts new files as soon as they land — see below. |
| **☀️ / 🌙** | Light or dark theme (also **View → Dark Mode**). **View → Animations** turns motion off. |

The status bar at the bottom shows what ARISE-I is doing (with a file count
during a run) and turns yellow or red when the folder needs attention.

### What never moves

Hidden files, `desktop.ini` / `Thumbs.db`, Office `~$` lock files, downloads
still in progress (`.crdownload`, `.part`, `.download`, `.tmp`, …), folders,
and ARISE-I's own `arise-i.log`, `.arise-i-log.json` and
`arise-i.config.yaml`. ARISE-I refuses to organize a whole drive or your home
folder — pick a subfolder such as Downloads or Desktop.

---

## Review Queue

When ARISE-I's confidence is below 75 %, it puts the file in a `__Review__`
folder instead of guessing. The **Review Queue** page lists those files with
one-click suggestions, plus a drop-down of every category.

Each decision moves the file, is logged so **↩ Undo** can reverse it, and
teaches the local model (with the AI extras installed, it retrains itself
after enough corrections).

Assignment files are recognised too: `Assignment 1 - Calculus.pdf` goes to
`Calculus/Assignment 1/PDFs/`. An assignment with no subject
(`Assignment 1.pdf`) waits in Review.

---

## Auto-Sort

Flip the **Auto-Sort** switch and ARISE-I watches the selected folder, sorting
new files once they have stopped changing for a couple of seconds, so
half-finished downloads are left alone. While it runs, Preview, Organize,
Undo and the folder field are locked, because the watcher would immediately
re-sort anything you put back. Turn it off to use them again.

---

## Keyboard shortcuts

Use **Cmd** instead of **Ctrl** on macOS. **F1** shows this list in the app.

| Shortcut | Action |
|---|---|
| Ctrl+O | Organize now |
| Ctrl+P | Preview changes |
| Ctrl+Z | Undo last run |
| Ctrl+B | Choose folder |
| Ctrl+E | Open folder in file manager |
| Ctrl+1 … Ctrl+4 | Activity, History, Last Run, Review Queue |
| Ctrl+D | Toggle dark mode |
| Ctrl+Q | Quit |
| F1 | Keyboard shortcuts |

---

## Command line

```bash
arise-i                          # organize ~/Downloads
arise-i --dry-run                # preview only
arise-i --path ~/Desktop         # another folder
arise-i --undo                   # reverse the last run in --path
arise-i --watch                  # keep watching and sort new files
arise-i --watch --debounce 5     # wait 5 s of quiet before sorting
arise-i --config my.yaml         # custom categories
arise-i --version
```

`python -m arise_i` works the same way. The exit code is non-zero if any file
failed to move (or, for `--undo`, failed to restore), which makes it easy to
use from scripts, `cron` or Task Scheduler:

```bash
# every day at 02:00
0 2 * * * arise-i --path ~/Downloads
```

---

## Custom categories

Put an `arise-i.config.yaml` in the folder you organize (ARISE-I also looks in
the current directory, or pass `--config`). Each category replaces the
built-in set — copy the defaults in if you want to keep them:

```yaml
Work:
  - .docx
  - .pdf
  - xlsx          # the leading dot is optional
Media: [.mp4, .mkv, .mp3]
Scripts: .py      # a single extension is fine too
```

---

## Plugins

A plugin is a Python file in `~/.arise-i/plugins/` with a
`classify(path) -> str | None` function. Plugins run in alphabetical order
before the built-in classifier; the first one to return a folder name wins,
and `None` passes the file on.

```python
# ~/.arise-i/plugins/01_by_year.py
from datetime import datetime
from pathlib import Path

def classify(path: Path) -> str | None:
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".heic"}:
        return None
    return f"Photos-{datetime.fromtimestamp(path.stat().st_mtime).year}"
```

A plugin that raises an error is skipped for that file. Plugins are ordinary
Python code running with your permissions — only install ones you trust.

---

## Troubleshooting

**The app won't start (source install).** Check `python3 -c "import tkinter"`.
On Linux install `python3-tk`; on macOS use the python.org installer or
`brew install python-tk`. Re-run the installer afterwards.

**`arise-i: command not found`.** The installer puts the commands in
`~/.local/bin`; add it to your `PATH` (the installer prints the line to add),
or run `scripts/start.sh`.

**Auto-Sort says it needs watchdog.** It is a regular dependency, so this only
happens in a hand-made environment: `pip install watchdog`, then restart.

**Some files weren't moved.** Look in **Activity** (or `arise-i.log` in the
folder) for the reason — usually a file that another program has open, or a
folder you don't have permission to write to. Close the program and run
again; don't run ARISE-I as administrator / with `sudo`, which would leave
files you can't edit.

**Undo says a file couldn't be restored.** The sorted file was moved or
deleted after the run. Everything else is restored; if you put the file back,
running Undo again retries it.

Still stuck? Open an issue at
<https://github.com/arise-om/ARISE-I/issues> with your OS, `arise-i --version`
and the relevant part of `arise-i.log`.

---

## FAQ

**Can ARISE-I delete my files?** No. It only moves files, never overwrites
one (a clash becomes `photo (1).jpg`), and keeps an undo record.

**Does anything leave my computer?** No. There are no network requests; the
learning data and model live in `~/.arise-i/`.

**What if it crashes mid-run?** Files moved so far are written to the undo
record when the run ends, even if it was interrupted, so Undo still works.

**Does it work on network drives?** Yes, just slower.

**Can it watch several folders?** Run `arise-i --watch --path <folder>` once
per folder. The app watches one folder at a time.
