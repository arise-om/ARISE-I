# Contributing to ARISE-I

Thank you for considering a contribution! ARISE-I is built to be a premium,
privacy-first file organization tool. This guide will help you contribute
in a way that matches the project's quality bar.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Structure](#project-structure)
3. [Development Setup](#development-setup)
4. [Running Tests](#running-tests)
5. [Commit Conventions](#commit-conventions)
6. [Pull Request Process](#pull-request-process)
7. [Code Standards](#code-standards)
8. [Adding Features](#adding-features)
9. [Bug Reports](#bug-reports)

---

## Quick Start

```bash
git clone https://github.com/arise-om/ARISE-I.git
cd ARISE-I
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ai]"
pytest
```

---

## Project Structure

```
ARISE-I/
├── arise_i/
│   ├── __init__.py          __version__ (the only place to bump it)
│   ├── __main__.py          `python -m arise_i` → CLI
│   ├── constants.py         Shared file/folder names (__Review__, manifest, ~/.arise-i)
│   ├── core/
│   │   ├── organizer.py     Scan → classify → move, undo, config, CLI (main)
│   │   ├── classifier.py    4-layer classification engine
│   │   ├── assignment.py    Assignment / lab / project filename parser
│   │   ├── learning.py      Feedback log + model retraining
│   │   ├── health.py        Self-healing background monitor
│   │   ├── watcher.py       Auto-Sort watchdog daemon
│   │   ├── plugins.py       Plugin loader (~/.arise-i/plugins)
│   │   ├── paths.py         Folder-name sanitising
│   │   └── prefs.py         Preference read/write
│   └── gui/
│       ├── app.py           Tkinter dashboard
│       ├── onboarding.py    First-run wizard
│       └── theme.py         Palettes, fonts, scaling, animation, toggle switch
├── tests/                   pytest suite (isolated HOME, see conftest.py)
├── scripts/                 install / start scripts, create_demo_files.py
├── packaging/               arise-i.spec (PyInstaller), ARISE-I.iss (Windows installer)
├── docs/                    USER_GUIDE.md, screenshots
├── pyproject.toml           Package metadata + ruff config
└── CHANGELOG.md             Release history
```

---

## Development Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate.bat       # Windows

# Install package in editable mode with all extras
pip install -e ".[dev,ai]"

# Run the GUI in development
arise-i-gui                        # or: python -m arise_i.gui.app

# Run the CLI
arise-i --help                     # or: python -m arise_i --help

# A harmless folder of sample files to try it on
python scripts/create_demo_files.py --output ./demo_sandbox
arise-i --dry-run --path ./demo_sandbox
```

---

## Running Tests

```bash
# Full test suite (GUI tests need a display: `xvfb-run pytest` on headless Linux)
pytest

# With coverage report
pytest --cov=arise_i --cov-report=term-missing

# A specific test file
pytest tests/test_real_run.py

# Lint
ruff check .
```

All PRs must maintain **100% of existing tests passing**. New features
should include tests.

---

## Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

Types:
  feat      New feature
  fix       Bug fix
  docs      Documentation only
  test      Adding or updating tests
  refactor  Code change without feature/fix
  perf      Performance improvement
  chore     Dependency bumps, tooling
  style     Formatting (no logic change)
```

**Examples:**
```
feat(classifier): add Layer 4 ML model with sklearn NaiveBayes
fix(gui): repair trailing comma in _on_model_retrained
docs(readme): add AI engine architecture diagram
test(classifier): add unit tests for MIME detection layer
chore(deps): bump scikit-learn from 1.3 to 1.5
```

---

## Pull Request Process

1. **Branch** from `main` using `feature/<short-name>` or `fix/<short-name>`
2. **Write or update tests** for your changes
3. **Run the full test suite** — all must pass
4. **Update CHANGELOG.md** under `[Unreleased]`
5. **Open a PR** with a clear description of _why_, not just _what_
6. A maintainer will review within 48 hours

### PR Checklist

- [ ] Tests added / updated
- [ ] All existing tests still pass (`pytest`) and `ruff check .` is clean
- [ ] CHANGELOG.md updated
- [ ] Public functions have docstrings
- [ ] No hardcoded paths or file names (use `arise_i/constants.py`)
- [ ] Optional deps (scikit-learn, filetype) handled with `try/except ImportError`

---

## Code Standards

### No Cloud Policy

ARISE-I is **strictly local-first**. PRs that introduce:
- HTTP calls to external services
- Cloud-based ML APIs (OpenAI, Anthropic, etc.)
- Telemetry or usage analytics
- Any form of data upload

...will be **rejected without review**. This is non-negotiable.

### Graceful Degradation

The optional AI dependencies (scikit-learn, filetype) must degrade
gracefully when absent:

```python
try:
    import some_optional_lib
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

def my_feature():
    if not _AVAILABLE:
        return fallback_result()
    # ... full implementation
```

### Thread Safety

The GUI runs on the main thread. Long operations (sort, retrain, health
checks) must run in daemon threads and communicate results via
`queue.Queue`. Never call Tkinter methods from background threads.

### Atomic Writes

Any file write that could corrupt data on crash must use the
`tmp → rename` pattern:

```python
tmp = target.with_suffix(".tmp")
with open(tmp, "w") as f:
    json.dump(data, f)
tmp.replace(target)  # atomic on POSIX; near-atomic on Windows
```

Anything that moves files or edits the undo manifest must run under
`organizer._RUN_LOCK` (`organize_folder`, `undo_last_run` and
`record_moves` already do).

### Colours and sizes

Use palette keys from `arise_i/gui/theme.py`, never hex values: a theme
switch remaps colours key-for-key. Text on `ACCENT_FILL` uses `ON_ACCENT`.
New text/background pairs belong in `tests/test_theme.py`, which enforces
WCAG AA contrast. Pixel sizes go through `theme.scaled()` so they grow on
HiDPI screens.

---

## Adding Features

### New Classifier Layer

Add a new layer method to `SmartClassifier` in `arise_i/core/classifier.py`:

```python
def _by_my_layer(self, path: Path) -> ClassificationResult:
    # Your logic here
    return ClassificationResult(
        category="SomeCategory",
        confidence=0.80,
        layer="my_layer",
    )
```

Then add it to `classify()`:
```python
results = [
    ext_result,
    self._by_mime(path),
    self._by_heuristics(path),
    self._by_my_layer(path),   # ← add here
]
```

### New Plugin

Drop a `.py` file into `~/.arise-i/plugins/`:

```python
from pathlib import Path

def classify(path: Path) -> str | None:
    """Return a category name, or None to defer to the next layer."""
    if path.suffix.lower() == ".xyz":
        return "MySpecialFolder"
    return None
```

### New Health Check

Add a `_check_<name>()` method to `HealthMonitor` (`arise_i/core/health.py`) and call it from `_run_checks()`:

```python
def _check_my_thing(self) -> dict:
    # return {"ok": True/False, ...}
    pass
```

---

## Releasing

1. Bump `__version__` in `arise_i/__init__.py` — the package, the GUI, the
   macOS bundle and the Windows installer all read it from there.
2. Move the `[Unreleased]` notes in `CHANGELOG.md` under the new version.
3. Commit, then tag and push: `git tag v2.2.0 && git push origin v2.2.0`.
4. The **Build desktop apps** workflow builds Windows (installer), macOS and
   Linux, runs `--self-test` on each, and attaches them to the GitHub Release.

macOS asks users to approve unsigned apps in System Settings, and Windows
SmartScreen warns about new unsigned installers; signing and notarisation
remove both.

---

## Bug Reports

Please include:

1. **OS and Python version** (`python3 --version`, `uname -a`)
2. **ARISE-I version** (shown in the GUI footer, or `arise-i --version`)
3. **What you did** (steps to reproduce)
4. **What you expected**
5. **What actually happened** (include the log from `arise-i.log` in the target folder)
6. **`~/.arise-i/health.json`** contents if the issue is with the daemon

Open issues at: https://github.com/arise-om/ARISE-I/issues

---

**Made with ❤️ by Om Deshmukh · Ironlabs.tech**
