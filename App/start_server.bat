@echo off
setlocal
cd /d "%~dp0"
title Stream Attendance Server

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo ERROR: The app is not installed yet.
    echo Run the main INSTALL.bat from the package first.
    echo.
    pause
    exit /b 1
)

echo ==========================================
echo  STREAM ATTENDANCE SERVER
echo  Dashboard: http://127.0.0.1:6767
echo ==========================================
echo.
start "" "http://127.0.0.1:6767"
".venv\Scripts\python.exe" app.py
pause
