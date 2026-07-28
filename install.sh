#!/bin/bash
# ARISE-I source installer for Linux/macOS.
# Customers should use standalone downloads from GitHub Releases when available.

set -e

echo "🚀 ARISE-I Installer"
echo "==================="
echo ""

# Detect operating system
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    echo "❌ Unsupported operating system: $OSTYPE"
    exit 1
fi

echo "🖥️  Detected OS: $OS"
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "🐍 Python version: $PYTHON_VERSION"

# Check if Python version is 3.10+
if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "❌ Python 3.10+ is required. Current version: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python version check passed"
echo ""

# Install tkinter if needed (Linux only)
if [[ "$OS" == "linux" ]]; then
    echo "📦 Checking for tkinter..."
    if ! python3 -c "import tkinter" 2>/dev/null; then
        echo "🔧 Installing tkinter..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update -qq
            sudo apt-get install -y python3-tk
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3-tkinter
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm tk
        else
            echo "⚠️  Could not install tkinter automatically. Please install it manually."
        fi
    else
        echo "✅ tkinter is already installed"
    fi
    echo ""
fi

# Install ARISE-I in its own virtual environment. This works on modern
# Linux distributions that intentionally block system-wide pip installs.
if [[ "$OS" == "macos" ]]; then
    INSTALL_ROOT="$HOME/Library/Application Support/ARISE-I"
else
    INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/arise-i"
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$INSTALL_ROOT/venv"

echo "🔧 Installing ARISE-I in $INSTALL_ROOT..."
if ! python3 -m venv "$VENV_DIR"; then
    echo "❌ Could not create a Python virtual environment."
    echo "   On Ubuntu/Debian, install python3-venv and run this installer again."
    exit 1
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip -q
"$VENV_DIR/bin/python" -m pip install "$SCRIPT_DIR" -q

echo "✅ ARISE-I installed"
echo ""

# Create desktop shortcut (Linux only)
if [[ "$OS" == "linux" ]]; then
    echo "🖥️  Creating desktop shortcut..."
    DESKTOP_FILE="$HOME/.local/share/applications/arise-i.desktop"
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=ARISE-I
Comment=Organize your files automatically
Exec="$VENV_DIR/bin/arise-i-gui"
Icon=folder
Terminal=false
Type=Application
Categories=Utility;FileManager;
EOF
    
    chmod +x "$DESKTOP_FILE"
    echo "✅ Desktop shortcut created"
    echo ""
fi

# Create macOS app (macOS only)
if [[ "$OS" == "macos" ]]; then
    echo "🍎 Creating macOS application..."
    APP_DIR="$HOME/Applications/ARISE-I.app"
    mkdir -p "$APP_DIR/Contents/MacOS"
    mkdir -p "$APP_DIR/Contents/Resources"
    
    cat > "$APP_DIR/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>arise-i-gui</string>
    <key>CFBundleName</key>
    <string>ARISE-I</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>
EOF
    
    echo "#!/bin/bash" > "$APP_DIR/Contents/MacOS/arise-i-gui"
    echo "exec \"$VENV_DIR/bin/arise-i-gui\"" >> "$APP_DIR/Contents/MacOS/arise-i-gui"
    chmod +x "$APP_DIR/Contents/MacOS/arise-i-gui"
    
    echo "✅ macOS application created"
    echo ""
fi

echo "✨ Installation complete!"
echo ""
echo "🎉 ARISE-I is now installed and ready to use!"
echo ""
echo "📖 Quick Start:"
echo "   • GUI:     Run '$VENV_DIR/bin/arise-i-gui' in your terminal"
if [[ "$OS" == "linux" ]]; then
    echo "   • GUI:     Or search for 'ARISE-I' in your applications menu"
elif [[ "$OS" == "macos" ]]; then
    echo "   • GUI:     Or open ARISE-I from your Applications folder"
fi
echo "   • CLI:     Type 'arise-i --help' for command-line options"
echo ""
echo "💡 First time? Just run 'arise-i-gui' and click 'Organize Now'!"
echo ""
