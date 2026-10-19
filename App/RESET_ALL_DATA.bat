@echo off
setlocal
cd /d "%~dp0"
title Reset Stream Attendance Data

echo =====================================================
echo  RESET ALL ATTENDANCE + CREDITS DATA
 echo =====================================================
echo.
echo This deletes attendance.db and all current credits data.
echo It DOES NOT remove the app, settings, or Streamer.bot setup.
echo.
set /p CONFIRM=Type RESET to continue: 
if /I not "%CONFIRM%"=="RESET" (
    echo Cancelled.
    pause
    exit /b 0
)

call "%~dp0stop_server.bat"
if exist "attendance.db" del /Q "attendance.db"
if exist "credits-data" rmdir /S /Q "credits-data"
if exist "end-credits.txt" del /Q "end-credits.txt"
mkdir "credits-data" >nul 2>&1
for %%F in (attendees followers subs donors) do type nul > "credits-data\%%F.txt"
>"end-credits.txt" echo THANK YOU FOR WATCHING

echo.
echo Data reset complete.
start "" wscript.exe "%~dp0start_hidden.vbs"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:6767"
pause
