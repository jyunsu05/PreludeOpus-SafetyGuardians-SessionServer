@echo off
setlocal EnableExtensions
rem Waits until the local server is up, then opens the dashboard.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "for ($i=0; $i -lt 40; $i++) { try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/health' -UseBasicParsing -TimeoutSec 1; if ($r.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8080'; exit 0 } } catch {} ; Start-Sleep -Seconds 1 }; exit 1"
