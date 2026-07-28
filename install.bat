@echo off
REM ARISE-I source installer for Windows.
REM Customers should use the standalone ARISE-I Setup .exe from GitHub Releases.

echo ========================================
echo    ARISE-I Source Installer
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo 🐍 Python is installed
python --version
echo.

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
python -c "import sys; raise SystemExit(sys.version_info ^< (3, 10))"
if %errorlevel% neq 0 (
    echo ❌ Python 3.10+ is required. Current version: %PYTHON_VERSION%
    pause
    exit /b 1
)
echo ✅ Python version: %PYTHON_VERSION%
echo.

REM Install Python dependencies for this Windows user (no administrator needed)
echo 📦 Installing Python dependencies...
python -m pip install --user pyyaml watchdog -q
echo ✅ Dependencies installed
echo.

REM Install ARISE-I
echo 🔧 Installing ARISE-I...
pushd "%~dp0"
python -m pip install --user . -q
popd
echo ✅ ARISE-I installed
echo.

REM Create desktop shortcut
echo 🖥️  Creating desktop shortcut...
set SCRIPT=%TEMP%\create_shortcut.vbs
for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user'))"') do set "SCRIPTS_DIR=%%i"

echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = "%USERPROFILE%\Desktop\ARISE-I.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%SCRIPTS_DIR%\arise-i-gui.exe" >> %SCRIPT%
echo oLink.Description = "Organize your files automatically" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%

cscript /nologo %SCRIPT%
del %SCRIPT%

echo ✅ Desktop shortcut created
echo.

echo ✨ Installation complete!
echo.
echo 🎉 ARISE-I is now installed and ready to use!
echo.
echo 📖 Quick Start:
echo    • GUI:     Double-click the ARISE-I shortcut on your desktop
echo    • CLI:     Type 'arise-i --help' in command prompt
echo.
echo 💡 First time? Just double-click the desktop shortcut and click 'Preview changes first'!
echo.
pause
