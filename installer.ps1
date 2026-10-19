$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "5HVLED Stream Attendance Installer"

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  5HVLED STREAM ATTENDANCE - FRIENDLY INSTALLER" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

$Docs = [Environment]::GetFolderPath('MyDocuments')
$Desktop = [Environment]::GetFolderPath('Desktop')
$Target = Join-Path $Docs '5HVLED-Attendance'
$SourceApp = Join-Path $PSScriptRoot 'App'
$SourceSB = Join-Path $PSScriptRoot 'StreamerBot\5HVLED-Stream-Attendance-All-In-One.sb'
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Write-Utf8NoBom([string]$Path, [string]$Value) { [System.IO.File]::WriteAllText($Path, $Value, $Utf8NoBom) }

$defaultName = 'My Stream'
$defaultHandle = 'streamer'
if (Test-Path (Join-Path $Target 'channel_name.txt')) { $defaultName = (Get-Content (Join-Path $Target 'channel_name.txt') -Raw).Trim() }
if (Test-Path (Join-Path $Target 'channel_handle.txt')) { $defaultHandle = (Get-Content (Join-Path $Target 'channel_handle.txt') -Raw).Trim().TrimStart('@') }

$name = Read-Host "Channel / brand name [$defaultName]"
if ([string]::IsNullOrWhiteSpace($name)) { $name = $defaultName }
$handle = Read-Host "Twitch handle without @ [$defaultHandle]"
if ([string]::IsNullOrWhiteSpace($handle)) { $handle = $defaultHandle }
$handle = $handle.Trim().TrimStart('@')

Write-Host ""
Write-Host "Install folder:" -ForegroundColor Yellow
Write-Host "  $Target"
Write-Host ""

New-Item -ItemType Directory -Force -Path $Target | Out-Null

# Stop old local server before replacing code.
try {
    $lines = netstat -ano | Select-String ':6767' | Select-String 'LISTENING'
    foreach ($line in $lines) {
        $parts = ($line.ToString().Trim() -split '\s+')
        $pidToKill = $parts[-1]
        if ($pidToKill -match '^\d+$') { Stop-Process -Id ([int]$pidToKill) -Force -ErrorAction SilentlyContinue }
    }
} catch {}
Start-Sleep -Milliseconds 500

Write-Host "[1/6] Copying application files..." -ForegroundColor Green
Copy-Item (Join-Path $SourceApp '*') $Target -Recurse -Force
Copy-Item $SourceSB (Join-Path $Target '5HVLED-Stream-Attendance-All-In-One.sb') -Force
Write-Utf8NoBom (Join-Path $Target 'channel_name.txt') $name
Write-Utf8NoBom (Join-Path $Target 'channel_handle.txt') $handle

$credits = Join-Path $Target 'credits-data'
New-Item -ItemType Directory -Force -Path $credits | Out-Null
foreach ($f in @('attendees.txt','followers.txt','subs.txt','donors.txt')) {
    $p = Join-Path $credits $f
    if (-not (Test-Path $p)) { New-Item -ItemType File -Path $p | Out-Null }
}
$endCredits = Join-Path $Target 'end-credits.txt'
if (-not (Test-Path $endCredits)) {
    $initialCredits = (@('THANK YOU FOR WATCHING','','SEE YOU NEXT STREAM',('@'+$handle),'','','','','','','','','','') -join [Environment]::NewLine) + [Environment]::NewLine
    Write-Utf8NoBom $endCredits $initialCredits
}

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) { return @{ Kind='py'; Value='py' } }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @{ Kind='exe'; Value=(Get-Command python).Source } }
    $candidates = @()
    $candidates += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending
    $candidates += Get-ChildItem "$env:ProgramFiles\Python*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending
    if ($candidates.Count -gt 0) { return @{ Kind='exe'; Value=$candidates[0].FullName } }
    return $null
}

Write-Host "[2/6] Checking Python..." -ForegroundColor Green
$py = Find-Python
if (-not $py) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Python was not found. Installing Python 3.14 with winget..." -ForegroundColor Yellow
        & winget install -e --id Python.Python.3.14 --scope user --silent --accept-package-agreements --accept-source-agreements
        Start-Sleep -Seconds 2
        $py = Find-Python
    }
}
if (-not $py) {
    Write-Host ""
    Write-Host "Python could not be installed automatically." -ForegroundColor Red
    Write-Host "Install Python 3.9 or newer, then run INSTALL.bat again."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[3/6] Creating Python environment..." -ForegroundColor Green
$venv = Join-Path $Target '.venv'
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
    if ($py.Kind -eq 'py') { & py -3 -m venv $venv }
    else { & $py.Value -m venv $venv }
}
$venvPython = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $venvPython)) { throw "Could not create the Python virtual environment." }

Write-Host "[4/6] Installing Flask..." -ForegroundColor Green
& $venvPython -m pip install --disable-pip-version-check -q -r (Join-Path $Target 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw "Python package installation failed." }

Write-Host "[5/6] Creating shortcuts..." -ForegroundColor Green
$ws = New-Object -ComObject WScript.Shell
$folderShortcut = $ws.CreateShortcut((Join-Path $Desktop '5HVLED Attendance Folder.lnk'))
$folderShortcut.TargetPath = $Target
$folderShortcut.Save()
$startShortcut = $ws.CreateShortcut((Join-Path $Desktop 'Start Attendance Server.lnk'))
$startShortcut.TargetPath = (Join-Path $Target 'start_server.bat')
$startShortcut.WorkingDirectory = $Target
$startShortcut.Save()
$stopShortcut = $ws.CreateShortcut((Join-Path $Desktop 'Stop Attendance Server.lnk'))
$stopShortcut.TargetPath = (Join-Path $Target 'stop_server.bat')
$stopShortcut.WorkingDirectory = $Target
$stopShortcut.Save()
$dashboardUrl = Join-Path $Desktop 'Attendance Dashboard.url'
"[InternetShortcut]`r`nURL=http://127.0.0.1:6767`r`n" | Set-Content -Path $dashboardUrl -Encoding ASCII

Write-Host "[6/6] Starting server and verifying..." -ForegroundColor Green
Start-Process -FilePath 'wscript.exe' -ArgumentList ('"'+(Join-Path $Target 'start_hidden.vbs')+'"') -WindowStyle Hidden
$ok = $false
for ($i=0; $i -lt 20; $i++) {
    try {
        $r = Invoke-RestMethod -Uri ('http://127.0.0.1:6767/api/status?install=' + [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()) -TimeoutSec 2
        if ($r.ok) { $ok = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if (-not $ok) { throw "The app installed, but the local web server did not start correctly." }

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  INSTALL COMPLETE" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Dashboard: http://127.0.0.1:6767"
Write-Host "Installed to: $Target"
Write-Host "OBS credits file: $endCredits"
Write-Host ""
Write-Host "NEXT STEP:" -ForegroundColor Yellow
Write-Host "Open Streamer.bot -> Import, then import:"
Write-Host "  $Target\5HVLED-Stream-Attendance-All-In-One.sb" -ForegroundColor White
Write-Host ""
Write-Host "After importing, make sure Twitch + OBS are connected in Streamer.bot."
Write-Host "For end credits in OBS: Text (GDI+) -> Read from file -> end-credits.txt"
Write-Host ""
Start-Process 'http://127.0.0.1:6767'
Start-Process explorer.exe -ArgumentList ('/select,"'+(Join-Path $Target '5HVLED-Stream-Attendance-All-In-One.sb')+'"')
Read-Host "Press Enter to close the installer"
