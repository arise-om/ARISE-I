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
pytest tests/ -v
```

---

## Project Structure

```
ARISE-I/
├── classifier.py        AI classification engine (4-layer)
├── learning_store.py    Feedback log + model retraining
├── health_monitor.py    Self-healing background daemon
├── file_organizer.py    Core sort orchestrator
├── file_watcher.py      Auto-sort watchdog daemon
├── gui.py               Tkinter dashboard
├── plugin_loader.py     Plugin sandbox system
├── prefs.py             Preference read/write
├── onboarding.py        First-run wizard
├── tests/               pytest test suite
│   ├── test_organizer.py
│   ├── test_real_run.py
│   ├── test_watcher.py
│   └── ...
├── install.sh           Linux/macOS installer
├── install.bat          Windows installer
├── pyproject.toml       Package metadata
├── CHANGELOG.md         Release history
└── PRODUCT_VISION.md    Roadmap and architecture docs
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
python gui.py

# Run the CLI
python file_organizer.py --help
```

---

## Running Tests

```bash
# Full test suite
pytest tests/ -v

# With coverage report
pytest tests/ --cov=. --cov-report=term-missing

# A specific test file
pytest tests/test_real_run.py -v

# Watch mode (requires pytest-watch)
ptw tests/
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
- [ ] All 120+ existing tests still pass
- [ ] CHANGELOG.md updated
- [ ] Public functions have docstrings
- [ ] No hardcoded paths (use `Path.home()` / constants)
- [ ] Optional deps handled with `try/except ImportError`

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

All optional features (sklearn, filetype, watchdog) must degrade
gracefully when the dependency is absent:

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

---

## Adding Features

### New Classifier Layer

Add a new layer method to `SmartClassifier` in `classifier.py`:

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
    self._by_extension(path),
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

Add a `_check_<name>()` method to `HealthMonitor` and call it from `_run_checks()`:

```python
def _check_my_thing(self) -> dict:
    # return {"ok": True/False, ...}
    pass
```

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
