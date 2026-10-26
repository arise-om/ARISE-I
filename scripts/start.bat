@echo off
REM ARISE-I launcher for Windows: starts the app, installing it first if needed.

set "GUI_EXE=%LOCALAPPDATA%\ARISE-I\venv\Scripts\arise-i-gui.exe"

if not exist "%GUI_EXE%" (
    echo ARISE-I is not installed yet. Running the installer...
    echo.
    call "%~dp0install.bat"
)
if exist "%GUI_EXE%" start "" "%GUI_EXE%"
