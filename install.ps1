<#
.SYNOPSIS
    Single-command per-user installer for Login Wallpaper Selector.
.DESCRIPTION
    Installs Login Wallpaper Selector into the user's environment, creates a CLI shim,
    registers current-user login startup, and performs a health verification check.
    Does NOT require administrator privileges.
#>
param (
    [switch]$SkipAutostart = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Installing Login Wallpaper Selector       " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ProjectDir = $PSScriptRoot

# 1. Verify Python availability
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    Write-Error "Python 3.10+ was not found on your PATH. Please install Python and try again."
    exit 1
}

Write-Host "[1/4] Installing package in editable mode..." -ForegroundColor Yellow
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv pip install --system -e "$ProjectDir"
} else {
    python -m pip install -e "$ProjectDir"
}

# 2. Create CLI shortcut in user WindowsApps folder (included in user PATH by default)
Write-Host "[2/4] Setting up command-line launcher..." -ForegroundColor Yellow
$UserAppsDir = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
if (Test-Path $UserAppsDir) {
    $ShimFile = Join-Path $UserAppsDir "login-wallpaper-selector.bat"
    $BatchContent = @"
@echo off
python -m login_wallpaper_selector %*
"@
    Set-Content -Path $ShimFile -Value $BatchContent -Encoding Ascii
    Write-Host "      Created CLI launcher: $ShimFile" -ForegroundColor Green
}

# 3. Register user login autostart
if (-not $SkipAutostart) {
    Write-Host "[3/4] Registering login startup entry..." -ForegroundColor Yellow
    python -m login_wallpaper_selector --install
} else {
    Write-Host "[3/4] Skipping autostart registration as requested." -ForegroundColor Gray
}

# 4. Create Desktop Shortcut
Write-Host "[4/5] Creating Desktop Shortcut with custom icon..." -ForegroundColor Yellow
python -m login_wallpaper_selector --create-shortcut

# 5. Verify installation
Write-Host "[5/5] Running system verification check..." -ForegroundColor Yellow
python -m login_wallpaper_selector --check

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Installation Successful!" -ForegroundColor Green
Write-Host " The selector will automatically run on each desktop sign-in." -ForegroundColor Green
Write-Host " You can also launch it manually anytime by running:" -ForegroundColor White
Write-Host "   login-wallpaper-selector" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Green
