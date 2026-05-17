param(
    [switch]$InstallRe9Bridge,
    [switch]$InstallREFramework,
    [switch]$IUnderstandGameMayBeAffected,
    [switch]$NoShortcut
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venv = Join-Path $repoRoot ".venv"
$python = Join-Path $venv "Scripts\python.exe"

function Get-PreferredPython {
    $versions = @("3.14", "3.13", "3.12", "3.11", "3.10")
    foreach ($version in $versions) {
        $candidate = & py "-$version" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) {
            return $candidate.Trim()
        }
    }

    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "Python was not found. Install Python 3.14+ from https://www.python.org/downloads/windows/ and enable the Python launcher."
}

$basePython = Get-PreferredPython
$baseVersion = & $basePython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"

if (Test-Path -LiteralPath $python) {
    $venvVersion = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($LASTEXITCODE -ne 0 -or $venvVersion -ne $baseVersion) {
        Write-Host "Recreating Python virtual environment for Python $baseVersion..."
        Remove-Item -LiteralPath $venv -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating Python virtual environment with Python $baseVersion..."
    & $basePython -m venv $venv
}

Write-Host "Installing Python dependencies..."
& $python -m pip install --upgrade pip
& $python -m pip install --upgrade -r (Join-Path $repoRoot "requirements.txt")

if ($InstallRe9Bridge) {
    $bridgeArgs = @("-InstallLua")
    if ($InstallREFramework) {
        $bridgeArgs += "-InstallREFramework"
    }
    if ($IUnderstandGameMayBeAffected) {
        $bridgeArgs += "-IUnderstandGameMayBeAffected"
    }
    & (Join-Path $repoRoot "scripts\Install-Re9Bridge.ps1") @bridgeArgs
}

if (-not $NoShortcut) {
    & (Join-Path $repoRoot "scripts\Create-DesktopShortcut.ps1")
}

Write-Host ""
Write-Host "RE:AL SHOCK MOD is ready."
Write-Host "Launch it from the desktop shortcut or run scripts\Start-RealShockMod.ps1."
