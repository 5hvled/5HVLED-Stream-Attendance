@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:6767/api/status' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    start "" wscript.exe "%~dp0start_hidden.vbs"
    for /L %%i in (1,1,20) do (
        powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:6767/api/status' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"
        if not errorlevel 1 goto :SERVER_READY
        timeout /t 1 /nobreak >nul
    )
    exit /b 1
)

:SERVER_READY
powershell -NoProfile -Command ^
  "$r = Invoke-RestMethod -Uri 'http://127.0.0.1:6767/api/stream/start' -Method Get; $r | ConvertTo-Json -Compress"

start "" "http://127.0.0.1:6767"
exit /b 0
