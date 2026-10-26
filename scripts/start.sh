#!/bin/bash
# ARISE-I Quick Start Launcher
# Simply run this script to launch ARISE-I

# Check if ARISE-I is installed
if command -v arise-i-gui &> /dev/null; then
    arise-i-gui
else
    echo "ARISE-I is not installed yet. Running installer..."
    echo ""
    bash "$(dirname "$0")/install.sh"
fi