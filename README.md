# ARISE-I

**An AI-powered file organizer that gets smarter every time you use it.**

ARISE-I watches your Downloads folder (or any folder) and automatically sorts files into neat categories — using a 4-layer AI engine that learns from your corrections. Everything runs locally; your files and data never leave your machine.

---

## 🆕 What's New in v2.0.0

- **AI Classification Engine** — Multi-layer classifier: extension → MIME → heuristics → local ML model
- **Confidence Scoring** — Every file gets a confidence badge (`[HIGH 92%]` / `[MED 71%]` / `[LOW 34%]`)
- **Review Queue** — Uncertain files go to `__Review__/` instead of being silently mis-sorted; a dedicated tab lets you confirm the right category in one click
- **Adaptive Learning** — Each correction trains a local `scikit-learn` model so ARISE-I improves over time
- **Self-Healing Daemon** — Background health monitor auto-repairs corrupted manifests, detects disk pressure, and auto-retrains when accuracy drifts
- **Dark Mode** — Toggle ☀️/🌙 in the header; preference is saved between sessions
- **Crash-Resistant Watcher** — Auto-sort daemon restarts itself (exponential backoff, up to 5 times) if the watchdog thread crashes

---

## ✨ Core Features

| Feature | Details |
|---|---|
| **One-Click Organization** | Click "Organize Now" — done |
| **Smart Preview** | See exactly what would move before committing |
| **Undo** | Restore everything from the last run, any time |
| **Auto-Sort** | Watches for new files and sorts them as they arrive |
| **AI Classifier** | 4 layers: extension map → MIME sniff → filename heuristics → sklearn ML |
| **Review Queue** | Low-confidence files quarantined for manual review, not silently misfiled |
| **Self-Healing** | Background daemon auto-repairs issues without user action |
| **100 % Local** | No cloud, no API keys, no data egress — ever |

---

## 🚀 Quick Start

### Install from source (Linux / macOS)

```bash
git clone https://github.com/om-ironlabs/ARISE-I.git
cd ARISE-I
bash install.sh
arise-i-gui
```

The installer will ask if you want AI extras (`scikit-learn` + `filetype`). Choose **Y** for full smart-classification with the ML layer.

### Enable AI extras later

```bash
pip install arise-i[ai]
# or
pip install scikit-learn filetype
```

### Windows

```bat
install.bat
start.bat
```

---

## 🧠 How the AI Engine Works

```
File dropped
    │
    ├── Layer 1: Extension map       → conf 0.92  (e.g. .pdf → PDFs)
    ├── Layer 2: MIME type sniff     → conf 0.88  (byte-level via filetype)
    ├── Layer 3: Filename heuristics → conf 0.76–0.88 (regex patterns)
    └── Layer 4: sklearn ML model    → trained on your corrections
               │
               ├── confidence ≥ 0.75  →  Sort to correct folder  ✅
               └── confidence < 0.75  →  __Review__/ tab          ⚠
                                              │
                                         You pick the folder
                                              │
                                         LearningStore.record()
                                              │ (every 50 events)
                                         Model retrains locally
                                              │
                                         Classifier improves 🧠
```

---

## 📂 Categories

| Category | File types |
|---|---|
| Images | `.jpg` `.png` `.gif` `.svg` `.webp` `.heic` … |
| Videos | `.mp4` `.mkv` `.avi` `.mov` `.webm` … |
| Music | `.mp3` `.flac` `.wav` `.aac` `.ogg` … |
| Documents | `.docx` `.txt` `.odt` `.rtf` … |
| PDFs | `.pdf` |
| Spreadsheets | `.xlsx` `.csv` `.ods` … |
| Presentations | `.pptx` `.odp` … |
| Code | `.py` `.js` `.ts` `.html` `.css` `.go` … |
| Archives | `.zip` `.rar` `.7z` `.tar.gz` … |
| Installers | `.exe` `.dmg` `.deb` `.apk` … |
| Ebooks | `.epub` `.mobi` |
| Fonts | `.ttf` `.otf` `.woff` … |
| Others | Everything else |
| **`__Review__/`** | Low-confidence files awaiting your decision |

---

## ⚙️ CLI Usage

```bash
# Organize your Downloads folder
arise-i

# Preview without moving anything
arise-i --dry-run

# Organize a specific folder
arise-i --path ~/Desktop

# Watch a folder and auto-sort new files
arise-i --watch

# Undo the last organization
arise-i --undo
```

---

## 🔌 Custom Categories

Create `arise-i.config.yaml` in the target folder:

```yaml
Work:
  - .docx
  - .pdf
  - .xlsx

Media:
  - .mp4
  - .mkv
  - .mp3

MyScripts:
  - .py
  - .sh
```

---

## 🧩 Plugin System

Drop `.py` files into `~/.arise-i/plugins/` for custom classification logic:

```python
# ~/.arise-i/plugins/01_by_year.py
from pathlib import Path, datetime

def classify(path: Path) -> str | None:
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        return None
    year = datetime.fromtimestamp(path.stat().st_mtime).year
    return f"Photos-{year}"
```

---

## 🛠️ Technical Details

| | |
|---|---|
| **Language** | Python 3.10+ |
| **GUI** | Tkinter (zero extra deps for base UI) |
| **Core deps** | PyYAML, watchdog |
| **AI deps** | scikit-learn, filetype *(optional)* |
| **ML model** | TF-IDF + Multinomial Naive Bayes, trained locally |
| **Storage** | `~/.arise-i/` — feedback log, model pickle, prefs |
| **Privacy** | 100 % local — no network requests, ever |
| **Platforms** | Linux, macOS, Windows |

---

## 🧪 Testing

```bash
pip install pytest
pytest tests/ -v
# 120 tests, all passing
```

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

## 🙋 Author

**Om Deshmukh** — Robotics & Automation Engineering student, founder of [Ironlabs.tech](https://ironlabs.tech)

**Made with ❤️ by Ironlabs.tech**
