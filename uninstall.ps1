<#
.SYNOPSIS
    Uninstaller for Login Wallpaper Selector.
.DESCRIPTION
    Deregisters login autostart, removes CLI shim, and cleans up.
    Does NOT require administrator privileges.
#>

$ErrorActionPreference = "Continue"

Write-Host "==========================================" -ForegroundColor Yellow
Write-Host " Uninstalling Login Wallpaper Selector     " -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

# 1. Deregister login autostart
Write-Host "[1/3] Removing login startup entry..." -ForegroundColor Yellow
python -m login_wallpaper_selector --uninstall

# 2. Remove CLI launcher shim
Write-Host "[2/3] Removing CLI launcher shim..." -ForegroundColor Yellow
$ShimFile = "$env:LOCALAPPDATA\Microsoft\WindowsApps\login-wallpaper-selector.bat"
if (Test-Path $ShimFile) {
    Remove-Item -Force $ShimFile
    Write-Host "      Removed $ShimFile" -ForegroundColor Green
}

# 3. Clean cache prompt or removal
Write-Host "[3/3] Application uninstalled successfully." -ForegroundColor Green
Write-Host "Note: Cached wallpapers in %LOCALAPPDATA%\LoginWallpaperSelector have been preserved." -ForegroundColor Gray
Write-Host "To remove cached images, manually delete that folder." -ForegroundColor Gray
