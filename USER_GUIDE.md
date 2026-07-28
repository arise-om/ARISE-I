# ARISE-I User Guide

**Complete guide to using ARISE-I - Your Personal File Organizer**

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Usage](#basic-usage)
3. [Advanced Features](#advanced-features)
4. [Customization](#customization)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)

---

## Getting Started

### Installation

#### Windows
1. Download ARISE-I from GitHub
2. Extract the zip file
3. Double-click `install.bat`
4. Wait for installation to complete
5. Double-click the ARISE-I icon on your desktop

#### macOS
1. Download ARISE-I from GitHub
2. Extract the zip file
3. Open Terminal and navigate to the ARISE-I folder
4. Run: `bash install.sh`
5. Wait for installation to complete
6. Open ARISE-I from Applications

#### Linux
1. Download ARISE-I from GitHub
2. Extract the zip file
3. Open Terminal and navigate to the ARISE-I folder
4. Run: `bash install.sh`
5. Wait for installation to complete
6. Search for "ARISE-I" in your applications menu

### Requirements

- **Python 3.10+** - Required for ARISE-I to run
- **tkinter** - Required for the GUI (usually included with Python)
- **PyYAML** - For configuration file support
- **watchdog** - Optional, required for auto-sort feature

---

## Basic Usage

### First-Time Setup

1. **Launch ARISE-I** - Double-click the desktop icon or run `arise-i-gui`
2. **Select Folder** - ARISE-I defaults to your Downloads folder
3. **Click "Organize Now"** - One click to organize your files
4. **Done!** - Your files are now organized into categories

### Using the Interface

#### Main Button
- **"✨ Organize Now"** - The primary action. Click to organize files in the selected folder

#### Folder Selection
- **Current Folder** - Shows the folder being organized
- **"Change" Button** - Click to select a different folder

#### Auto-Sort
- **"Auto-sort new files" Checkbox** - Enable to automatically organize new files as they arrive
- **Requires** - The `watchdog` package (auto-installed if missing)

#### Undo
- **"↩ Undo Last" Button** - Reverses the last organization operation
- **Safe** - Files are restored to their original locations

#### Activity Log
- **Bottom Panel** - Shows real-time activity and status messages
- **Minimal** - Keeps the interface clean while providing feedback

---

## Advanced Features

### Command Line Interface

For power users who prefer terminal control:

```bash
# Basic organization
arise-i

# Organize specific folder
arise-i --path ~/Desktop

# Preview without making changes
arise-i --dry-run

# Watch folder and auto-sort new files
arise-i --watch

# Watch with custom delay (seconds)
arise-i --watch --debounce 5

# Undo last organization
arise-i --undo

# Use custom configuration
arise-i --config my-config.yaml
```

### Keyboard Shortcuts

Power users can navigate ARISE-I quickly using keyboard shortcuts:

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + O` | Organize files |
| `Ctrl/Cmd + Z` | Undo last organization |
| `Ctrl/Cmd + B` | Browse folder |
| `Ctrl/Cmd + L` | Clear log |
| `Ctrl/Cmd + Q` | Quit application |

*On Mac, use `Cmd` instead of `Ctrl`*

### Auto-Sort Mode

Enable continuous file organization:

1. Check "Auto-sort new files"
2. ARISE-I monitors the selected folder
3. New files are automatically organized as they arrive
4. Perfect for Downloads folders or working directories

**Note:** Auto-sort requires the `watchdog` package, which will be auto-installed if missing.

---

## Customization

### Custom Categories

Create a custom configuration file to define your own categories:

1. Create a file named `arise-i.config.yaml` in the folder you want to organize
2. Add your custom categories:

```yaml
Work:
  - .docx
  - .pdf
  - .xlsx
  - .pptx

Media:
  - .mp4
  - .mkv
  - .mp3
  - .wav

Projects:
  - .py
  - .js
  - .html
  - .css

Personal:
  - .jpg
  - .png
  - .heic
```

3. Run ARISE-I - it will use your custom categories

### Plugin System

Add custom sorting logic with Python plugins:

1. Create the plugins directory: `mkdir -p ~/.arise-i/plugins`
2. Create a Python file in that directory:

```python
# ~/.arise-i/plugins/01_by_year.py
from pathlib import Path
import datetime

def classify(path: Path) -> str | None:
    """Sort image files into Photos-<year> folders."""
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".heic"}:
        return None  # Let other plugins or defaults handle it
    year = datetime.datetime.fromtimestamp(path.stat().st_mtime).year
    return f"Photos-{year}"
```

3. Run ARISE-I - your plugin will be automatically loaded

**Plugin Rules:**
- Plugins are loaded in alphabetical filename order
- Return a string to categorize the file
- Return `None` to let other plugins or defaults handle it
- Plugins that crash are skipped safely

---

## Troubleshooting

### Common Issues

#### ARISE-I won't start

**Problem:** Double-clicking the icon doesn't open ARISE-I

**Solutions:**
- Ensure Python 3.10+ is installed
- Reinstall ARISE-I using the installation script
- Check that tkinter is installed (Linux: `sudo apt install python3-tk`)

#### Auto-sort not working

**Problem:** Auto-sort checkbox is disabled or doesn't work

**Solutions:**
- Install watchdog: `pip install watchdog`
- Restart ARISE-I after installing watchdog
- Check that the selected folder exists and is accessible

#### Files not being organized

**Problem:** Clicking "Organize Now" doesn't move files

**Solutions:**
- Check that you have write permissions for the folder
- Ensure the folder isn't on a read-only filesystem
- Try running as administrator (Windows) or with sudo (Linux/macOS)

#### Error messages in log

**Problem:** Red error messages appear in the activity log

**Solutions:**
- Check the specific error message for details
- Ensure the folder path is valid and accessible
- Try organizing a different folder to isolate the issue

### Getting Help

If you encounter issues not covered here:

1. **Check the log** - The activity log shows detailed error information
2. **Try CLI mode** - Run `arise-i --help` for command-line troubleshooting
3. **Check GitHub** - Visit https://github.com/arise-om/ARISE-I/issues for known issues
4. **Report bugs** - Create a new issue on GitHub with details

---

## FAQ

### Is ARISE-I safe to use?

**Yes!** ARISE-I:
- Never deletes files, only moves them
- Logs every action so you can undo
- Processes everything locally on your computer
- Doesn't upload or transmit any data

### Can ARISE-I delete my files?

**No.** ARISE-I only moves files into organized folders. It never deletes files.

### What if I make a mistake?

**Use the Undo feature:** Click "↩ Undo Last" to reverse the last organization operation. All files are restored to their original locations.

### Can I organize folders other than Downloads?

**Yes!** Click "Change" next to the folder path to select any folder on your computer.

### Does ARISE-I work with network drives?

**Yes, but performance may be slower** due to network latency. ARISE-I works best with local folders.

### Can I run ARISE-I on multiple folders at once?

**Yes** - Launch multiple instances of ARISE-I, each configured for a different folder.

### How does auto-sort work?

**Auto-sort uses file system monitoring** to detect new files and organize them automatically. It requires the `watchdog` package.

### Can I customize the categories?

**Yes!** Create a `arise-i.config.yaml` file with your custom categories (see Customization section).

### Does ARISE-I work with case-sensitive file systems?

**Yes** - ARISE-I handles case-sensitive file systems (like Linux) correctly.

### What happens if ARISE-I crashes while organizing?

**The undo feature** allows you to restore files even if ARISE-I crashes. The operation is logged and can be reversed.

### Can I use ARISE-I on a server?

**Yes** - ARISE-I works on servers via command line interface. GUI is optional.

---

## Tips and Best Practices

### For Best Performance

- **Organize regularly** - Don't let folders get too messy before organizing
- **Use auto-sort** - Enable for frequently-used folders like Downloads
- **Customize categories** - Tailor categories to your specific workflow
- **Use plugins** - Add custom logic for specialized file types

### For Organization Strategies

- **Start with Downloads** - Perfect first folder to organize
- **Organize by project** - Use custom categories for project-specific files
- **Regular maintenance** - Run ARISE-I weekly to keep folders clean
- **Backup first** - While ARISE-I is safe, always backup important files

### For Power Users

- **Use CLI scripts** - Automate ARISE-I in scripts and cron jobs
- **Create plugins** - Add custom sorting logic for your specific needs
- **Use config files** - Different configs for different folder types
- **Monitor logs** - Check `arise-i.log` for detailed operation history

---

## Advanced Topics

### Batch Processing

Organize multiple folders in sequence:

```bash
#!/bin/bash
# Organize multiple folders
arise-i --path ~/Downloads
arise-i --path ~/Desktop
arise-i --path ~/Documents
```

### Scheduled Organization

Use cron (Linux/macOS) or Task Scheduler (Windows) to run ARISE-I automatically:

**Linux/macOS (cron):**
```bash
# Run every day at 2 AM
0 2 * * * arise-i --path ~/Downloads
```

**Windows (Task Scheduler):**
- Create a task to run `arise-i --path ~/Downloads`
- Schedule it to run daily or weekly

### Integration with Other Tools

ARISE-I can be integrated with:
- **Backup scripts** - Organize before backing up
- **Download managers** - Auto-sort completed downloads
- **File sync tools** - Organize before syncing to cloud

---

## Version Information

Current Version: 1.3.0

### Changelog

**v1.3.0** - Apple-style redesign
- Beautiful minimalist interface
- One-click installation
- Auto-sort feature
- Keyboard shortcuts
- Enhanced error handling
- Performance optimizations

**v1.2.0** - Plugin system
- Custom plugin support
- Enhanced configuration options
- Better security features

**v1.1.0** - Watch mode
- Auto-sort functionality
- Real-time file monitoring
- Improved performance

**v1.0.0** - Initial release
- Basic file organization
- CLI interface
- GUI wrapper
- Undo support

---

## Support and Community

### Getting Help

- **GitHub Issues:** https://github.com/arise-om/ARISE-I/issues
- **Documentation:** https://github.com/arise-om/ARISE-I
- **Author:** Om - Robotics & Automation Engineering student, founder of Ironlabs.tech

### Contributing

ARISE-I is open source! Contributions are welcome:
- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

### License

MIT License - See LICENSE file for details

---

**Thank you for using ARISE-I!**

*Made with ❤️ by Ironlabs.tech*