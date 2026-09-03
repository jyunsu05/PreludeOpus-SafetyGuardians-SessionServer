@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "data\sessions.db" (
  echo No data\sessions.db yet. Play a session first.
  pause
  exit /b 1
)

set "PY_CMD="
py -3 -c "import sys" >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD python -c "import sys" >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
  echo Python 3.11+ is required.
  pause
  exit /b 1
)

%PY_CMD% -m app.backup_db
if errorlevel 1 (
  echo Backup failed.
  pause
  exit /b 1
)
echo Backup completed and integrity checked.
pause
