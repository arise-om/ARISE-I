# Changelog

All notable changes to ARISE-I are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [2.2.0] — 2026-10-26

### 🧹 Reorganisation, audit fixes and UI polish

### Changed
- **Package layout**: the modules now live in an `arise_i` package
  (`arise_i/core` engine, `arise_i/gui` app, shared names in
  `arise_i/constants.py`, version in `arise_i/__init__.py`).  The
  `arise-i` / `arise-i-gui` commands are unchanged; `python -m arise_i` is new.
  Install and start scripts moved to `scripts/`, packaging files to `packaging/`.
- **Colours meet WCAG AA** in both themes (accent text, white on buttons and
  amber hints were 3.0–4.0:1); a test now enforces it.
- **HiDPI**: Windows DPI awareness, and sizes scale with the screen.  Fonts use
  the platform's UI font instead of assuming Ubuntu / naming SF Pro.
- Heuristic filename rules match whole words only, and assignment subjects
  ignore ` (1)` copy suffixes and trailing ` - extra` text.
- Auto-retrain runs in the background instead of pausing a sort, and a drift
  retrain waits for 10 new feedback events.
- Docs rewritten against the current app; internal planning docs,
  `docs/QUICKSTART.md` (merged into the README) and `requirements-dev.txt` removed.

### Added
- Review decisions are recorded for Undo.
- Status-bar progress ("Organizing… 12 / 40 files") and error states; a
  "Nothing to sort" page; keyboard focus rings; a themed shortcuts dialog.
- `packaging/arise-i.spec` and `arise-i-gui --self-test`, run on every release build.
- `install.bat` installs into its own virtual environment and offers the AI extras.

### Fixed
- **Overlapping runs could overwrite files** (Organize vs Auto-Sort, or a
  watcher timer firing during a long sort) — runs are now serialised.
- **An interrupted run lost its undo record**; one bad file no longer aborts a run.
- **Undo could get stuck** on a run whose files were all deleted, blocking older runs.
- Low-confidence assignment files were nested as `Subject/Assignment N/__Review__`.
- Windows device names (`CON`, `NUL`, …) as subjects or plugin results made
  folder creation fail.
- GUI: turning Auto-Sort off and on quickly left two watchers running; "Undo
  complete" was shown even after errors; one failing refresh stopped all log
  updates; an empty folder field showed the working directory's history;
  Ctrl+D/B/E in the path field also edited the text; Cmd+Q on macOS skipped
  saving preferences; confidence badges were never coloured.
- First-run wizard: "grab failed" on Linux, finishing with a missing folder,
  clipped bottom edge, keyboard-unreachable "Skip for now".
- Release builds shipped without scikit-learn/filetype; `install.bat`'s repair
  step always reported failure; `pip install arise-i[ai]` hints pointed at a
  package that isn't on PyPI.
- Preferences with the wrong value type crashed the app; concurrent updates
  could be lost.

### 🎨 UI / UX refresh (merged after 2.1.0)

### Changed
- **New layout**: a sidebar menu (Activity, History, Last Run, Review Queue)
  replaces the top tab bar, with a sliding active-page indicator and a badge
  counting files waiting in Review.  Each page has a title, a one-line
  description and its own header actions (Clear log, Refresh, …).
- **Folder field** now spans the full width and keeps the folder name in view;
  a live hint below it shows how many loose files are ready to sort, or warns
  when the folder is missing or protected.  Preview / Organize Now / Undo sit
  right beneath it.
- **Last Run** shows count-up summary tiles (files, categories, skipped,
  errors) and a full-width per-category bar chart; after a Preview it offers
  "Organize these files" directly.
- **History** cards show relative time ("5 min ago"), category chips and which
  run is undoable.  **Review Queue** cards show type, size and one-click
  suggestion chips beside the full category dropdown.
- **Auto-Sort** uses an animated on/off switch and a "breathing" status dot
  instead of a checkbox and blinking text.
- **First-run wizard** follows the saved theme, validates the folder, fits its
  content (the "Let's Go" button was cut off) and supports Enter / Esc.
- Restyled cards, borders, scrollbars and dropdowns; higher-contrast text
  colours in light mode.

### Added
- **Menu bar** — File (Choose / Open Folder, Preview, Organize, Undo, Quit),
  View (pages, Dark Mode, Animations) and Help (Keyboard Shortcuts, About).
- **Shortcuts**: Ctrl+P preview, Ctrl+E open folder, Ctrl+D dark mode,
  Ctrl+1…4 switch page, F1 shortcut list.
- **Animations**: window fade in/out, page slide-in, theme-switch dim, hover
  colour fades, indeterminate progress strip during runs, and corner toast
  notifications for finished runs, undo and Review moves.  View → Animations
  turns them off (reduced motion), saved as the `animations` pref.
- Tooltips on toolbar buttons, mouse-wheel scrolling in History and Review,
  and the window size/position is remembered (`window_geometry` pref).
- Shared theme module (now `arise_i/gui/theme.py`) — palettes, fonts, colour
  maths, animation engine and the toggle switch, used by the main window and
  the first-run wizard.

### Fixed
- Keyboard shortcuts could start a run while another run or Auto-Sort was
  active; they now show a hint instead.

---

## [2.1.0] — 2026-10-18

### 🛠 Reliability release — fixes from a full audit

### Fixed
- **Auto-Sort never fired on new files** with watchdog ≥ 4: every event carries
  `dest_path=""`, so created/modified events resolved to the CWD and were
  dropped.  The watcher now falls back to `src_path`.
- **Files that must not move were moved**: `desktop.ini`/`Thumbs.db`, Windows
  hidden/system files, Office `~$` lock files, `arise-i.config.yaml`, and
  in-progress downloads (`.crdownload`, `.part`, …) — moving the latter
  corrupted active downloads.  Shared `skip_reason()` used by organizer and watcher.
- **Undo could overwrite data**: a file re-downloaded to the original path was
  clobbered.  Undo now restores as `name (1).ext`, keeps failed moves in the
  manifest for retry, and removes category folders it left empty.
- **Review Queue overwrote files** with the same name in the chosen category,
  and only offered the first six categories.  Now uses unique names, classifier
  suggestions, and a dropdown of every category.
- **Learning loop**: files quarantined to `__Review__/` were logged as
  `confirmed="__Review__"`, teaching the model a fake category.  These rows are
  no longer written and are ignored at retrain; one-class models are refused.
- **Retrained models were never used in-session** — the shared classifier now
  reloads `model.pkl` when it changes and applies threshold changes.
- **Health monitor** re-ran the same retrain and re-sent the same alerts every
  60 s; drift retrain now needs new feedback, and alerts are de-duplicated.
- **Config discovery** ignored `arise-i.config.yaml` in the target folder
  (contrary to the README); malformed entries are now normalised.
- **Dark mode** left dark text on dark cards; colours are now remapped per role.
- GUI: undo asks for confirmation (Ctrl+Z was instant), Tk is no longer
  touched from worker threads, plugins and learning now apply to GUI runs,
  Undo/Preview are locked during Auto-Sort, Ctrl+Q saves prefs.
- CLI refuses drive roots and the home folder (GUI already did); a file path as
  target no longer crashes; `arise-i` now returns proper exit codes.
- Packaging: `assignment_classifier` was missing from `py-modules`, so
  installed builds silently lost assignment sorting.
- CI lint never ran (ruff rejected the unknown `W503` selector and `|| true`
  hid it).  Lint config moved to `pyproject.toml` and is now blocking.
- Installer version was stuck at 1.3.0; the release workflow now passes the tag.

### Added
- Extensions: `.jfif .avif .ico .m4v .opus .wma .tgz .ipynb .msix .pkg .appimage .iso`
- `arise-i --version`; `undo_last_run(..., log_callback=)` returns `(restored, failed)`
- 43 regression tests (classifier, learning store and health monitor had none);
  the suite runs against an isolated home so a local `model.pkl` can't skew results

---

## [2.0.0] — 2026-08-08

### 🚀 Major Release — AI-Powered Classification Engine

This release transforms ARISE-I from a rule-based sorter into an adaptive,
self-healing AI system that learns from your corrections.

### Added

#### AI Classification Engine (`classifier.py`)
- **4-layer SmartClassifier**: extension map → MIME sniff → filename heuristics → local ML model
- **Confidence scoring** on every decision: `[HIGH 92%]` / `[MED 71%]` / `[LOW 34%]`
- **`ClassificationResult`** dataclass: `{category, confidence, badge, layer, alternatives}`
- **MIME-type sniffing**: byte-level detection via `filetype` (optional), falls back to `mimetypes.guess_type()`
- **Filename heuristics**: 11 regex patterns (screenshots, invoices, resumes, soundtracks, etc.)
- **ML model layer** (optional, requires `scikit-learn`): TF-IDF + Multinomial Naive Bayes trained locally on user feedback
- **`__Review__/` quarantine**: files with confidence < 0.75 go here instead of being silently misfiled
- Optional AI extras: `pip install arise-i[ai]`

#### Adaptive Learning (`learning_store.py`)
- **Append-only `feedback.jsonl`** log — every classification decision recorded
- **Auto-retrain** after 50 new session events (configurable threshold)
- **`correction_rate()`** — tracks how often ARISE-I is wrong
- **`model_meta.json`** — human-readable accuracy stats after each retrain
- Atomic write pattern (`.tmp` → rename) — survives crashes without corruption

#### Self-Healing Daemon (`health_monitor.py`)
- **Manifest integrity check** — auto-backs-up and resets corrupt JSON logs
- **Disk space guard** — warns when target volume has < 500 MB free
- **Orphan re-review** — files in `__Review__/` older than 7 days are flagged
- **Model drift detection** — correction rate ≥ 30% triggers auto-retrain
- **Health status** persisted to `~/.arise-i/health.json` for inspection
- Runs every 60 seconds as a background daemon thread

#### GUI — Dark Mode + Review Queue (`gui.py`)
- **Dark / Light theme toggle** (☀️/🌙) in the header — persisted in prefs
- **`_THEMES` colour palette system** — all UI tokens update atomically on switch
- **Review Queue tab** (4th tab) — scrollable list of low-confidence files
  - Per-file card: filename, extension, file size
  - One-click category assignment buttons
  - Every confirmation feeds the LearningStore for future model improvement
- **Confidence badges** colour-coded in Activity Log: `[HIGH]` = green, `[LOW]` = yellow
- `HealthMonitor` started on app launch, stopped cleanly on close
- `learning_store` piped into Organize Now worker thread

#### File Watcher Hardening (`file_watcher.py`)
- **Exponential-backoff restart loop** (up to 5 restarts) if watchdog observer crashes
- `learning_store` parameter threaded through to daemon sort
- Backoff starts at 2s, doubles per failure, capped at 60s

#### Installer
- `install.sh`: interactive AI extras prompt (`[y/N]`) — detects non-TTY environments
- Non-interactive CI environments auto-skip and print the manual install command

### Changed
- **`organize_folder()`** signature: added `confidence_threshold` (default 0.75) and `learning_store` params
- **`file_organizer.py`** log output: every line now includes `[BADGE conf%]` suffix
- **Review moves** shown with ⚠ icon (yellow) instead of ✓ (green)
- **`pyproject.toml`** version bumped to `2.0.0`
- **`pyproject.toml`** adds `[ai]` optional-dependency group: `scikit-learn>=1.3`, `filetype>=1.2`
- **`pyproject.toml`** `py-modules` extended: `classifier`, `learning_store`, `health_monitor`
- **`README.md`** completely rewritten for v2.0 with AI engine documentation

### Fixed
- GUI module docstring incorrectly stated v1.4.0
- Trailing comma in `_on_model_retrained()` (harmless, but noisy)
- Test `test_no_extension_file_goes_to_others` updated to accept `__Review__/` as the correct AI-era destination for extensionless files

---

## [1.4.0] — 2026-07-31

### 🖥️ GUI Dashboard Release

### Added
- **Two-panel Tkinter dashboard**: controls on the left, activity on the right
- **Activity Log tab**: live timestamped log feed with colour-coded messages
- **History tab**: scrollable list of past runs with per-category breakdown
- **Last Run card**: visual bar chart of files organized per category
- **Onboarding wizard**: first-launch modal to set the target folder
- **Pulsing daemon indicator**: animated dot in Auto-sort status
- **Persistent preferences**: `~/.arise-i/prefs.json` (last folder, debounce)
- **GUI launcher** (`arise-i-gui`) for the dashboard

### Changed
- App version constant introduced as `APP_VERSION`
- Logo panel in sidebar

### Fixed
- Shebang mismatch in pip-generated entry points (used system Python instead of venv)
- `install.sh`: replaced pip entry-point generation with explicit shell-delegate wrappers

---

## [1.3.0] — 2026-07-28

### Added
- Plugin system (`plugin_loader.py`): drop `.py` files into `~/.arise-i/plugins/`
- `ClassifierPlugin` protocol: `def classify(path: Path) -> str | None`
- Plugin loading isolated per file: a plugin that fails to import or raises is skipped
- Plugin errors logged without crashing the organizer

---

## [1.2.0] — 2026-07-25

### Added
- `--watch` / daemon mode via `watchdog` library
- Debounce timer (default 2s) before triggering sort after file events
- Hidden file filtering (`.dotfiles` never moved)
- Broken symlink detection and graceful skip

### Fixed
- Unhandled YAML `ParserError` when config file is malformed → now caught and logged

---

## [1.1.0] — 2026-07-23

### Added
- `arise-i.config.yaml` support for custom category → extension mapping
- `load_categories()` with YAML merge and validation
- `--dry-run` flag (preview without moving)
- `--undo` flag (restore last run from manifest)
- JSON undo manifest (`.arise-i-log.json`) with atomic write

---

## [1.0.0] — 2026-07-18

### Added
- `pyproject.toml` packaging (`setuptools`)
- `arise-i` and `arise-i-gui` console entry points
- `install.sh` / `install.bat` source installers
- Virtual-environment isolation
- `Stats` class for per-category move counts and sizes
- Deduplication: `photo.jpg` → `photo (1).jpg` on collision
- Color terminal output (ANSI codes via `Color` helper)
- Structured logging to `arise-i.log` in the target folder

---

## [0.1.0] — 2026-07-15 (MARK-I prototype)

- Initial file mover script
- Extension map hard-coded in Python dict
- No packaging, no GUI, no undo
