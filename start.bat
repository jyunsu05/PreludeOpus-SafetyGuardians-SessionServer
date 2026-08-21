@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Prelude Opus Session Server

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-port.ps1"
if %errorlevel%==0 (
  echo Server already running. Opening the dashboard.
  echo http://127.0.0.1:8080
  start "" "http://127.0.0.1:8080"
  pause
  exit /b 0
)
if %errorlevel%==2 (
  echo Port 8080 is in use by another program.
  echo Close that program, or use the existing server window.
  pause
  exit /b 1
)

set "PY_CMD="
py -3 -c "import sys" >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD python -c "import sys" >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
  echo Python 3.11+ is required.
  echo https://www.python.org/downloads/
  echo Check Add python.exe to PATH when installing.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First run: creating virtualenv...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtualenv.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
echo Checking packages...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)

if not exist "data" mkdir "data"

echo.
echo Starting server. Close this window to stop it.
echo Dashboard: http://127.0.0.1:8080
echo.

start "dashboard" /min "%~dp0open-dashboard.bat"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080

echo.
echo Server stopped.
pause
