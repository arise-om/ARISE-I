# Changelog

All notable changes to ARISE-I are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versioning follows [Semantic Versioning](https://semver.org/).

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
- **`--gui` flag**: launches the dashboard from the CLI

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
- Sandboxed plugin execution (restricted builtins via `exec`)
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
