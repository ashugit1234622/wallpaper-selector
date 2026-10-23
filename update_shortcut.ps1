# Script to update the Desktop shortcut with the latest committed code
$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
Write-Host "Updating Login Wallpaper Selector from: $ProjectDir" -ForegroundColor Cyan

# 1. Ensure editable install is up to date
Write-Host "[1/2] Updating package installation..." -ForegroundColor Yellow
python -m pip install -e "$ProjectDir"

# 2. Locate pythonw.exe
$Pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $Pythonw) {
    $PythonCmd = (Get-Command python).Source
    $PythonDir = Split-Path $PythonCmd -Parent
    $Pythonw = Join-Path $PythonDir "pythonw.exe"
}

if (-not (Test-Path $Pythonw)) {
    Write-Error "Could not locate pythonw.exe at '$Pythonw'"
    exit 1
}

# 3. Create / update shortcuts
Write-Host "[2/2] Updating shortcuts..." -ForegroundColor Yellow
$WshShell = New-Object -ComObject WScript.Shell
$DesktopDir = [Environment]::GetFolderPath('Desktop')
$DesktopShortcutPath = Join-Path $DesktopDir "Login Wallpaper Selector.lnk"
$ProjectShortcutPath = Join-Path $ProjectDir "Login Wallpaper Selector.lnk"
$IconPath = Join-Path $ProjectDir "assets\icon.ico"

foreach ($scPath in @($DesktopShortcutPath, $ProjectShortcutPath)) {
    $shortcut = $WshShell.CreateShortcut($scPath)
    $shortcut.TargetPath = $Pythonw
    $shortcut.Arguments = "-m login_wallpaper_selector"
    $shortcut.WorkingDirectory = $ProjectDir
    if (Test-Path $IconPath) {
        $shortcut.IconLocation = "$IconPath,0"
    }
    $shortcut.Save()
    Write-Host "  Updated shortcut: $scPath" -ForegroundColor Green
}

Write-Host "Shortcut updated successfully to launch the latest code!" -ForegroundColor Green
