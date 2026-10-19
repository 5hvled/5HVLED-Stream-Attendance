@echo off
setlocal
cd /d "%~dp0"
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do set D=%%d-%%b-%%c
set T=%time::=-%
set T=%T: =0%
set "DEST=%USERPROFILE%\Documents\5HVLED-Attendance-Backups\%D%_%T:~0,8%"
mkdir "%DEST%" >nul 2>&1
if exist "attendance.db" copy /Y "attendance.db" "%DEST%\attendance.db" >nul
if exist "end-credits.txt" copy /Y "end-credits.txt" "%DEST%\end-credits.txt" >nul
if exist "credits-data" xcopy /E /I /Y "credits-data" "%DEST%\credits-data" >nul
if exist "channel_name.txt" copy /Y "channel_name.txt" "%DEST%\channel_name.txt" >nul
if exist "channel_handle.txt" copy /Y "channel_handle.txt" "%DEST%\channel_handle.txt" >nul
echo Backup created:
echo %DEST%
start "" "%DEST%"
pause
