@echo off
setlocal EnableDelayedExpansion
title ARISE-I Installer
REM ARISE-I source installer for Windows.
REM Most people should use the ARISE-I-Setup installer from GitHub Releases.

echo ========================================
echo       ARISE-I Source Installer
echo ========================================
echo.

REM ----------------------------------------
REM 1. Python 3.10+
REM ----------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/windows/
    echo and tick "Add python.exe to PATH" in the installer.
    goto :finish_error
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.10 or newer is required.
    python --version
    goto :finish_error
)
for /f "delims=" %%v in ('python --version') do echo [OK] %%v

REM ----------------------------------------
REM 2. Private virtual environment
REM ----------------------------------------
REM ARISE-I gets its own venv so it never changes your global Python packages.
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
set "INSTALL_ROOT=%LOCALAPPDATA%\ARISE-I"
set "VENV_DIR=%INSTALL_ROOT%\venv"

echo [INFO] Installing into "%INSTALL_ROOT%"...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create a virtual environment.
        goto :finish_error
    )
)
set "VPY=%VENV_DIR%\Scripts\python.exe"

"%VPY%" -m pip install --upgrade pip -q
if errorlevel 1 (
    echo [ERROR] Could not update pip in the virtual environment.
    goto :finish_error
)

REM ----------------------------------------
REM 3. AI extras (optional)
REM ----------------------------------------
echo.
echo AI Smart-Classification (optional)
echo   Byte-level type detection and a local model that learns from your
echo   corrections. Adds about 60 MB (scikit-learn + filetype).
set "AI_ANSWER=N"
set /p "AI_ANSWER=  Install AI extras? [y/N] "
set "TARGET=%PROJECT_DIR%"
if /i "!AI_ANSWER!"=="y"   set "TARGET=%PROJECT_DIR%[ai]"
if /i "!AI_ANSWER!"=="yes" set "TARGET=%PROJECT_DIR%[ai]"

echo.
echo [INFO] Installing ARISE-I...
"%VPY%" -m pip install "!TARGET!" -q
if errorlevel 1 (
    echo [ERROR] Installation failed. See the messages above.
    goto :finish_error
)

set "GUI_EXE=%VENV_DIR%\Scripts\arise-i-gui.exe"
if not exist "%GUI_EXE%" (
    echo [ERROR] GUI launcher was not created: "%GUI_EXE%"
    goto :finish_error
)
echo [OK] ARISE-I installed.

REM ----------------------------------------
REM 4. Desktop and Start-menu shortcuts
REM ----------------------------------------
set "ARISE_GUI=%GUI_EXE%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference = 'Stop';" ^
 "$ws = New-Object -ComObject WScript.Shell;" ^
 "foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {" ^
 "  if ([string]::IsNullOrWhiteSpace($dir)) { continue };" ^
 "  $s = $ws.CreateShortcut((Join-Path $dir 'ARISE-I.lnk'));" ^
 "  $s.TargetPath = $env:ARISE_GUI;" ^
 "  $s.WorkingDirectory = $env:USERPROFILE;" ^
 "  $s.Description = 'ARISE-I File Organizer';" ^
 "  $s.Save() }"
if errorlevel 1 (
    echo [WARNING] Could not create shortcuts. Launch ARISE-I with:
    echo   "%GUI_EXE%"
) else (
    echo [OK] Desktop and Start-menu shortcuts created.
)

echo.
echo ========================================
echo       Installation complete
echo ========================================
echo.
echo   GUI:  double-click the ARISE-I shortcut, or run scripts\start.bat
echo   CLI:  "%VENV_DIR%\Scripts\arise-i.exe" --help
echo.
echo Tip: click Preview first to see what would move.
echo.
pause
endlocal
exit /b 0

:finish_error
echo.
echo ========================================
echo       Installation incomplete
echo ========================================
echo Review the error messages above.
echo.
pause
endlocal
exit /b 1
