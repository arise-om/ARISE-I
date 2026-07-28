# ARISE-I

**A calmer Downloads folder, in one click.**

ARISE-I is a private desktop app that turns a messy folder into neat, categorized collections. Preview changes safely, organize in one click, and undo any run if you change your mind.

Your files stay on your computer. ARISE-I never deletes them.

---

## ✨ Features

- **One-Click Organization** - Just click "Organize Now" and ARISE-I sorts everything automatically
- **Auto-Sort** - Enable auto-sort and ARISE-I watches your folder, organizing new files as they arrive
- **Undo Support** - Made a mistake? Click "Undo Last" to restore everything
- **Smart Categories** - Automatically sorts into 13 categories: Images, Documents, Videos, Music, Code, and more
- **Safe & Secure** - Files are never deleted, only organized. All processing happens on your computer.

---

## 🚀 Quick Start

### Windows (recommended)
1. Download `ARISE-I-Setup-<version>-Windows.exe` from the latest GitHub Release
2. Run the installer and open ARISE-I from the Start menu
3. Click **Preview changes first** or **Organize Now**

### macOS
1. Download `ARISE-I-macOS.zip` from the latest GitHub Release
2. Move `ARISE-I.app` into Applications and open it

### Linux
1. Download and extract `ARISE-I-Linux.tar.gz` from the latest GitHub Release
2. Run `ARISE-I/ARISE-I`

### From source

The `install.sh` and `install.bat` scripts are for contributors and advanced users. They require Python 3.10+.

---

## 📖 What Gets Organized

ARISE-I automatically sorts files into these categories:

| Category | Files |
|----------|-------|
| **Images** | Photos, screenshots, graphics (.jpg, .png, .gif, etc.) |
| **Documents** | Word docs, text files, PDFs (.doc, .docx, .txt, .pdf) |
| **Videos** | Movies, screen recordings (.mp4, .mkv, .avi, etc.) |
| **Music** | Songs, audio files (.mp3, .wav, .flac, etc.) |
| **Code** | Programming files (.py, .js, .html, .css, etc.) |
| **Archives** | ZIP, RAR files (.zip, .rar, .7z, etc.) |
| **Installers** | Application installers (.exe, .dmg, .apk, etc.) |
| **And more** | 13 categories total |

---

## 🎯 How It Works

1. **Scan** - ARISE-I reads every file in your folder
2. **Classify** - Each file is automatically categorized by type
3. **Organize** - Files are moved into neat category folders
4. **Log** - Every move is recorded so you can undo if needed

---

## ⚙️ Advanced Usage

### Command Line Interface

```bash
# Organize your Downloads folder
arise-i

# Preview what would happen (safe mode)
arise-i --dry-run

# Organize a specific folder
arise-i --path ~/Desktop

# Watch a folder and auto-sort new files
arise-i --watch

# Undo the last organization
arise-i --undo
```

### Custom Categories

Create a `arise-i.config.yaml` file to define your own categories:

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

### Plugin System

Add custom sorting logic by dropping Python plugins into `~/.arise-i/plugins/`:

```python
# ~/.arise-i/plugins/01_by_year.py
from pathlib import Path
import datetime

def classify(path: Path) -> str | None:
    """Sort image files into Photos-<year> folders."""
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        return None
    year = datetime.datetime.fromtimestamp(path.stat().st_mtime).year
    return f"Photos-{year}"
```

---

## 🧪 Testing

```bash
pip install pytest
pytest tests/ -v
```

---

## 🛠️ Technical Details

- **Built with:** Python 3.10+
- **Dependencies:** PyYAML, watchdog (optional)
- **Platform:** Windows, macOS, Linux
- **Privacy:** All processing happens locally on your computer

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙋 Author

**Om** — Robotics & Automation Engineering student, founder of [Ironlabs.tech](https://ironlabs.tech)

---

**Made with ❤️ by Ironlabs.tech**
