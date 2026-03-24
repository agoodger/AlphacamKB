@echo off
title Alphacam Knowledge Base
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Please install Python 3.10+ from https://www.python.org/downloads/
    echo  Make sure to tick "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo.
echo  Starting Alphacam Knowledge Base...
echo  Server: http://localhost:8080
echo  Press Ctrl+C to stop the server.
echo.

:: Open browser after a short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8080"

:: Start server (blocks until Ctrl+C)
python db_server.py

pause
