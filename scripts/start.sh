#!/bin/bash
# ARISE-I launcher for Linux/macOS: starts the app, installing it first if needed.

if [[ "$OSTYPE" == "darwin"* ]]; then
    GUI="$HOME/Library/Application Support/ARISE-I/venv/bin/arise-i-gui"
else
    GUI="${XDG_DATA_HOME:-$HOME/.local/share}/arise-i/venv/bin/arise-i-gui"
fi

if [ ! -x "$GUI" ]; then
    echo "ARISE-I is not installed yet. Running the installer..."
    echo ""
    bash "$(dirname "$0")/install.sh" || exit 1
fi
exec "$GUI" "$@"
