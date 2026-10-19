@echo off
setlocal
echo Stopping Stream Attendance server on port 6767...
set "FOUND=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":6767" ^| findstr "LISTENING"') do (
    set "FOUND=1"
    taskkill /PID %%a /F >nul 2>&1
)
echo Done.
