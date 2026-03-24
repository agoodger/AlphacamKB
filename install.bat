@echo off
setlocal enabledelayedexpansion
title Alphacam Knowledge Base - Installer
cd /d "%~dp0"

echo.
echo  ============================================
echo   Alphacam Knowledge Base - Installation
echo  ============================================
echo.

:: -------------------------------------------
:: Step 1: Check Python
:: -------------------------------------------
echo  [1/3] Checking for Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo.
    echo  Please install Python 3.10 or later:
    echo    1. Go to https://www.python.org/downloads/
    echo    2. Download the latest Python installer
    echo    3. IMPORTANT: Tick "Add Python to PATH" on the first screen
    echo    4. Click "Install Now"
    echo    5. Re-run this installer after Python is installed
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo         Found: %PYVER%

:: -------------------------------------------
:: Step 2: Verify required files
:: -------------------------------------------
echo  [2/3] Verifying application files...

set MISSING=0
if not exist "%~dp0db_server.py" (
    echo         MISSING: db_server.py
    set MISSING=1
)
if not exist "%~dp0knowledge_base.db" (
    echo         MISSING: knowledge_base.db
    set MISSING=1
)
if not exist "%~dp0ui\index.html" (
    echo         MISSING: ui\index.html
    set MISSING=1
)
if not exist "%~dp0kb_images" (
    echo         MISSING: kb_images folder
    set MISSING=1
)

if %MISSING%==1 (
    echo.
    echo  ERROR: Required files are missing. Please ensure the full
    echo  application folder was copied correctly.
    echo.
    pause
    exit /b 1
)

echo         All files present.

:: -------------------------------------------
:: Step 3: Create Desktop shortcut
:: -------------------------------------------
echo  [3/3] Creating Desktop shortcut...

set SHORTCUT_NAME=Alphacam Knowledge Base
set LAUNCH_PATH=%~dp0launch.bat

:: Find all candidate Desktop folders
set DESKTOP_COUNT=0

:: Check standard Desktop
if exist "%USERPROFILE%\Desktop" (
    set /a DESKTOP_COUNT+=1
    set "DESKTOP_1=%USERPROFILE%\Desktop"
    set "DESKTOP_LABEL_1=%USERPROFILE%\Desktop"
)

:: Check OneDrive Desktop locations
for /d %%D in ("%USERPROFILE%\OneDrive*") do (
    if exist "%%D\Desktop" (
        set /a DESKTOP_COUNT+=1
        set "DESKTOP_!DESKTOP_COUNT!=%%D\Desktop"
        set "DESKTOP_LABEL_!DESKTOP_COUNT!=%%D\Desktop"
    )
)

if %DESKTOP_COUNT%==0 (
    echo.
    echo  Could not find a Desktop folder automatically.
    echo  Please enter the full path to your Desktop folder:
    set /p "DESKTOP_PATH=  > "
) else if %DESKTOP_COUNT%==1 (
    set "DESKTOP_PATH=%DESKTOP_1%"
    echo         Using: %DESKTOP_1%
) else (
    echo.
    echo  Multiple Desktop folders found:
    echo.
    for /l %%N in (1,1,%DESKTOP_COUNT%) do (
        echo    %%N^) !DESKTOP_LABEL_%%N!
    )
    echo.
    set /p "DESKTOP_CHOICE=  Which Desktop? Enter number [1-%DESKTOP_COUNT%]: "
    call set "DESKTOP_PATH=%%DESKTOP_!DESKTOP_CHOICE!%%"
)

if not exist "%DESKTOP_PATH%" (
    echo.
    echo  ERROR: Desktop path not found: %DESKTOP_PATH%
    echo         You can manually create a shortcut pointing to: %LAUNCH_PATH%
    echo.
    pause
    exit /b 1
)

:: Use PowerShell to create a proper .lnk shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut(\"%DESKTOP_PATH%\%SHORTCUT_NAME%.lnk\"); $sc.TargetPath = \"%LAUNCH_PATH%\"; $sc.WorkingDirectory = \"%~dp0\"; $sc.Description = \"Launch Alphacam Knowledge Base\"; $sc.IconLocation = \"shell32.dll,14\"; $sc.Save()"

if %errorlevel%==0 (
    echo         Shortcut created on Desktop.
) else (
    echo         Could not create shortcut automatically.
    echo         You can manually create one pointing to: %LAUNCH_PATH%
)

:: -------------------------------------------
:: Done
:: -------------------------------------------
echo.
echo  ============================================
echo   Installation Complete!
echo  ============================================
echo.
echo   Double-click "Alphacam Knowledge Base" on
echo   your Desktop to start the application.
echo.
echo   The browser will open automatically to
echo   http://localhost:8080
echo.
pause
