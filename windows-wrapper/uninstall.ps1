# =============================================================================
#  GraphTerm uninstaller — removes shortcuts, registry entries and the
#  per-user install under %LOCALAPPDATA%\GraphTerm.
#
#  Usage:  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
# =============================================================================

$ErrorActionPreference = 'Stop'

$AppName    = 'GraphTerm'
$AppId      = 'MicrosoftResearch.GraphRAG.GraphTerm'
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName

Write-Host "== Uninstalling $AppName ==" -ForegroundColor Cyan

# Shortcuts
$lnkName = "$AppName.lnk"
$desktop = [Environment]::GetFolderPath('Desktop')
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
foreach ($p in @((Join-Path $desktop $lnkName), (Join-Path $startMenu $lnkName))) {
    if (Test-Path $p) { Remove-Item $p -Force; Write-Host "Removed $p" }
}

# Registry entries
foreach ($rk in @("HKCU:\Software\Classes\AppUserModelId\$AppId",
                  "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId")) {
    if (Test-Path $rk) { Remove-Item $rk -Recurse -Force; Write-Host "Removed $rk" }
}

# Installed files + managed venv
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
    Write-Host "Removed $InstallDir"
}

Write-Host "✔ $AppName has been uninstalled." -ForegroundColor Green
