# =============================================================================
#  GraphTerm installer — turns the wrapper shell into an installed
#  Windows 11 desktop app (Start Menu entry + optional desktop shortcut,
#  proper AppUserModelID so the taskbar groups under its own icon).
#
#  Usage (PowerShell, as the current user — no admin rights required):
#      powershell -ExecutionPolicy Bypass -File .\install.ps1
#      powershell -ExecutionPolicy Bypass -File .\install.ps1 -NoDesktopIcon
#      powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
# =============================================================================

[CmdletBinding()]
param(
    [switch]$NoDesktopIcon
)

$ErrorActionPreference = 'Stop'

$AppName    = 'GraphTerm'
$AppId      = 'MicrosoftResearch.GraphRAG.GraphTerm'   # Application User Model ID
$Version    = '1.0.0'
$SrcDir     = $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$VenvDir    = Join-Path $InstallDir 'venv'
$PythonDir  = Join-Path $InstallDir 'python'

Write-Host "== $AppName v$Version installer ==" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Find (or bootstrap) a Python 3.10+ interpreter.
# ---------------------------------------------------------------------------
function Find-Python {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $p = (& py -3.12 -c "import sys;print(sys.executable)") 2>$null
            if ($p) { $candidates += $p.Trim() }
            $p = (& py -3 -c "import sys;print(sys.executable)") 2>$null
            if ($p) { $candidates += $p.Trim() }
        } catch {}
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += (Get-Command python).Source
    }
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $ver = & $c -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $major, $minor = $ver.Split('.') | ForEach-Object { [int]$_ }
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                    return $c
                }
            }
        }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host "Python 3.10+ was not found. Downloading and installing Python silently via winget..." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
        $python = Find-Python
    }
    if (-not $python) {
        throw @"
Python 3.10 or newer is required but was not found (and silent install failed).
Please install it from https://www.python.org/downloads/ (check "Add python.exe
to PATH"), then re-run this script.
"@
    }
}
Write-Host "Using Python: $python" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. Copy application files to %LOCALAPPDATA%\GraphTerm.
# ---------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
foreach ($f in 'graphrag_wrapper.py', 'graphrag_wrapper.cmd', 'graphterm.pyw', 'graphterm.ico', 'README.md') {
    $src = Join-Path $SrcDir $f
    if (Test-Path $src) {
        Copy-Item $src -Destination $InstallDir -Force
    }
}
Write-Host "Installed app files to $InstallDir" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. Create a managed venv and install graphrag into it.
# ---------------------------------------------------------------------------
if (-not (Test-Path (Join-Path $VenvDir 'Scripts\python.exe'))) {
    Write-Host "Creating managed virtual environment (this can take a minute)..." -ForegroundColor Yellow
    & $python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed." }
}
$venvPy = Join-Path $VenvDir 'Scripts\python.exe'

Write-Host "Installing/updating the 'graphrag' package inside the managed venv..." -ForegroundColor Yellow
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install graphrag
if ($LASTEXITCODE -ne 0) { throw "pip install graphrag failed. Check your network connection." }
Write-Host "Managed environment ready: $VenvDir" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4. Create Start Menu (+ optional Desktop) shortcuts with an AUMID so
#    Windows 11 treats GraphTerm as a real desktop app.
# ---------------------------------------------------------------------------
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$iconPath = Join-Path $InstallDir 'graphterm.ico'
if (-not (Test-Path $iconPath)) { $iconPath = $pythonw }

$shell = New-Object -ComObject WScript.Shell
$lnkName = "$AppName.lnk"

$startMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$paths = @((Join-Path $startMenuDir $lnkName))
if (-not $NoDesktopIcon) {
    $desktop = ([Environment]::GetFolderPath('Desktop'))
    $paths += (Join-Path $desktop $lnkName)
}

foreach ($lnk in $paths) {
    $sc = $shell.CreateShortcut($lnk)
    $sc.TargetPath       = $pythonw
    $sc.Arguments        = "`"$InstallDir\graphterm.pyw`""
    $sc.WorkingDirectory = $InstallDir
    $sc.IconLocation     = "$iconPath,0"
    $sc.Description      = 'GraphRAG command shell (GraphTerm)'
    $sc.Save()
    Write-Host "Created shortcut: $lnk" -ForegroundColor Green
}

# Register the AUMID + pin-friendly metadata in the registry so Windows 11
# shows a clean, grouped app identity (notifications/taskbar jump lists).
$regPath = "HKCU:\Software\Classes\AppUserModelId\$AppId"
New-Item -Path $regPath -Force | Out-Null
New-ItemProperty -Path $regPath -Name 'DisplayName' -Value $AppName -PropertyType String -Force | Out-Null
New-ItemProperty -Path $regPath -Name 'IconUri' -Value $iconPath -PropertyType ExpandString -Force | Out-Null

# Also surface it under Add/Remove Programs for a proper "installed app" feel.
$unreg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId"
New-Item -Path $unreg -Force | Out-Null
New-ItemProperty -Path $unreg -Name 'DisplayName'    -Value "$AppName (GraphRAG shell)" -PropertyType String -Force | Out-Null
New-ItemProperty -Path $unreg -Name 'DisplayVersion' -Value $Version -PropertyType String -Force | Out-Null
New-ItemProperty -Path $unreg -Name 'Publisher'      -Value 'Local install' -PropertyType String -Force | Out-Null
New-ItemProperty -Path $unreg -Name 'InstallLocation'-Value $InstallDir -PropertyType String -Force | Out-Null
New-ItemProperty -Path $unreg -Name 'UninstallString' -Value "powershell -ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`"" -PropertyType String -Force | Out-Null
Copy-Item (Join-Path $SrcDir 'uninstall.ps1') -Destination $InstallDir -Force -ErrorAction SilentlyContinue

Write-Host ''
Write-Host "✔ $AppName is installed. Launch it from the Start Menu (search '$AppName')," -ForegroundColor Green
Write-Host "  from the desktop icon, or run:`n    `"$pythonw`" `"$InstallDir\graphterm.pyw`"" -ForegroundColor Green
