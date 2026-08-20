@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Prelude Opus Session Server

set "PY_CMD="
py -3 -c "import sys" >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD python -c "import sys" >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
  echo Python 3.11+ 이 필요합니다.
  echo https://www.python.org/downloads/
  echo 설치할 때 "Add python.exe to PATH" 를 체크하세요.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 처음 실행입니다. 가상환경을 만듭니다...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo 가상환경을 만들지 못했습니다.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
echo 패키지를 확인합니다. 처음이면 조금 걸립니다...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo pip install 에 실패했습니다.
  pause
  exit /b 1
)

if not exist "data" mkdir "data"

echo.
echo 서버를 켭니다. 이 창을 닫으면 서버가 꺼집니다.
echo 잠시 후 브라우저가 http://127.0.0.1:8080 으로 열립니다.
echo.

start "dashboard" /min cmd /c ""%~dp0open-dashboard.bat""
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080

echo.
echo 서버가 종료되었습니다.
pause
