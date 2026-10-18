
@echo off
setlocal
title ARISE-I Installer

echo ========================================
echo       ARISE-I Source Installer
echo ========================================
echo.

REM ----------------------------------------
REM 1. Check Python installation
REM ----------------------------------------
echo [INFO] Checking Python installation...

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo Install Python 3.10 or newer:
    echo https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

python --version
echo.

REM ----------------------------------------
REM 2. Check Python version
REM ----------------------------------------
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.10 or newer is required.
    pause
    exit /b 1
)

echo [OK] Python version is supported.
echo.

REM ----------------------------------------
REM 3. Check pip
REM ----------------------------------------
echo [INFO] Checking pip...

python -m pip --version
if errorlevel 1 (
    echo [WARNING] pip is unavailable. Attempting repair...
    python -m ensurepip --upgrade
    if errorlevel 1 (
        echo [ERROR] Could not initialize pip.
        pause
        exit /b 1
    )
)

echo.

REM ----------------------------------------
REM 4. Install ARISE-I and dependencies
REM ----------------------------------------
echo [INFO] Installing ARISE-I and dependencies...

pushd "%~dp0"
if errorlevel 1 (
    echo [ERROR] Could not open the project directory.
    pause
    exit /b 1
)

python -m pip install .
if errorlevel 1 (
    echo [ERROR] Installation failed.
    popd
    pause
    exit /b 1
)

popd

echo.
echo [OK] ARISE-I installed successfully.
echo.

REM ----------------------------------------
REM 5. Locate the active Python Scripts directory
REM ----------------------------------------
echo [INFO] Locating the GUI launcher...

for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path('scripts'))"') do set "SCRIPTS_DIR=%%i"

if not defined SCRIPTS_DIR (
    echo [ERROR] Could not determine the Scripts directory.
    goto :finish_error
)

set "GUI_EXE=%SCRIPTS_DIR%\arise-i-gui.exe"

REM ----------------------------------------
REM 6. Repair installation if launcher is missing
REM ----------------------------------------
if not exist "%GUI_EXE%" (
    echo [WARNING] GUI launcher not found.
    echo [INFO] Reinstalling ARISE-I...

    pushd "%~dp0"
    python -m pip install --force-reinstall .
    set "INSTALL_RESULT=%errorlevel%"
    popd

    if not "%INSTALL_RESULT%"=="0" (
        echo [ERROR] Reinstallation failed.
        goto :finish_error
    )
)

if not exist "%GUI_EXE%" (
    echo [ERROR] GUI launcher was not created.
    echo Expected: "%GUI_EXE%"
    goto :finish_error
)

echo [OK] GUI launcher found:
echo "%GUI_EXE%"
echo.

REM ----------------------------------------
REM 7. Create and verify desktop shortcut
REM ----------------------------------------
echo [INFO] Detecting the actual Windows Desktop...

set "ARISE_GUI=%GUI_EXE%"
set "ARISE_WORKDIR=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference = 'Stop';" ^
 "$desktop = [Environment]::GetFolderPath('Desktop');" ^
 "if ([string]::IsNullOrWhiteSpace($desktop)) { throw 'Windows Desktop path could not be determined.' };" ^
 "if (!(Test-Path -LiteralPath $desktop)) { New-Item -ItemType Directory -Path $desktop -Force | Out-Null };" ^
 "$target = $env:ARISE_GUI;" ^
 "if (!(Test-Path -LiteralPath $target)) { throw ('GUI executable not found: ' + $target) };" ^
 "$link = Join-Path $desktop 'ARISE-I.lnk';" ^
 "$ws = New-Object -ComObject WScript.Shell;" ^
 "$shortcut = $ws.CreateShortcut($link);" ^
 "$shortcut.TargetPath = $target;" ^
 "$shortcut.WorkingDirectory = $env:ARISE_WORKDIR;" ^
 "$shortcut.Description = 'ARISE-I File Organizer';" ^
 "$shortcut.Save();" ^
 "if (!(Test-Path -LiteralPath $link)) { throw ('Shortcut creation failed: ' + $link) };" ^
 "Write-Output '[OK] Desktop shortcut created and verified:';" ^
 "Write-Output $link;"

if errorlevel 1 (
    echo [ERROR] Could not create the desktop shortcut.
    echo.
    echo GUI executable:
    echo "%GUI_EXE%"
    echo.
    echo You can launch the GUI directly using that executable.
    goto :finish_error
)

echo.
echo [OK] Desktop shortcut created.
echo.

REM ----------------------------------------
REM 8. Installation complete
REM ----------------------------------------
echo ========================================
echo       Installation Completed
echo ========================================
echo.
echo Launch ARISE-I using the desktop shortcut.
echo.
echo CLI help:
echo   arise-i --help
echo.
echo IMPORTANT:
echo Test on a sample folder first.
echo Preview file changes before organizing.
echo.
pause
endlocal
exit /b 0

:finish_error
echo.
echo ========================================
echo       Installation Incomplete
echo ========================================
echo.
echo Review the error messages above.
echo.
pause
endlocal
exit /b 1
