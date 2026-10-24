<#
.SYNOPSIS
    Builds the production standalone executable and Inno Setup Windows installer (.exe).
.DESCRIPTION
    1. Compiles the application via PyInstaller into dist\DesktopUtilitySuite
    2. Builds the single-file setup installer Desktop-Utility-Suite-v2.0.0-Setup.exe
#>

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Building Desktop Utility Suite v2.0.0 Windows Installer   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$ProjectDir = $PSScriptRoot

# 1. Locate Inno Setup Compiler (ISCC.exe)
$IsccPaths = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$IsccExe = $null
foreach ($path in $IsccPaths) {
    if (Test-Path $path) {
        $IsccExe = $path
        break
    }
}

if (-not $IsccExe) {
    Write-Warning "Inno Setup Compiler (ISCC.exe) not found. Attempting install via winget..."
    winget install --id JRSoftware.InnoSetup -e --source winget --accept-package-agreements --accept-source-agreements
    foreach ($path in $IsccPaths) {
        if (Test-Path $path) {
            $IsccExe = $path
            break
        }
    }
}

if (-not $IsccExe) {
    Write-Error "Could not locate ISCC.exe. Please install Inno Setup 6."
    exit 1
}
Write-Host "[✓] Located Inno Setup Compiler: $IsccExe" -ForegroundColor Green

# 2. Build binaries using PyInstaller
Write-Host "`n[1/2] Compiling Python package with PyInstaller..." -ForegroundColor Yellow
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    pip install pyinstaller
}
pyinstaller "$ProjectDir\desktop_utility_suite.spec" --noconfirm

# 3. Compile Inno Setup installer
Write-Host "`n[2/2] Packaging installer executable with Inno Setup..." -ForegroundColor Yellow
& "$IsccExe" "$ProjectDir\installer.iss"

$InstallerExe = "$ProjectDir\dist_installer\Desktop-Utility-Suite-v2.0.0-Setup.exe"
if (Test-Path $InstallerExe) {
    $SizeMb = [math]::Round((Get-Item $InstallerExe).Length / 1MB, 2)
    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host " BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host " Installer Executable : $InstallerExe" -ForegroundColor Cyan
    Write-Host " File Size            : $SizeMb MB" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Error "Installer build failed. Output file was not found."
    exit 1
}
