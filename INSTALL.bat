@echo off
setlocal
title 5HVLED Stream Attendance Installer
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
if errorlevel 1 (
    echo.
    echo Installation did not finish successfully.
    pause
)
