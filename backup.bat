@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "data\sessions.db" (
  echo No data\sessions.db yet. Play a session first.
  pause
  exit /b 1
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
if not exist "backups" mkdir "backups"
xcopy /E /I /Y "data" "backups\data-%STAMP%" >nul
echo Copied data to backups\data-%STAMP%
pause
