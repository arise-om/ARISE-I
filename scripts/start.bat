@echo off
REM ARISE-I Quick Start Launcher for Windows
REM Simply run this script to launch ARISE-I

REM Check whether the launcher exists without starting the GUI.
where arise-i-gui >nul 2>&1
if errorlevel 1 (
    echo ARISE-I is not installed yet. Running installer...
    echo.
    call "%~dp0install.bat"
) else (
    arise-i-gui
)
