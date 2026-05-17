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

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.10+ from https://www.python.org/downloads/windows/ and enable 'Add python.exe to PATH'."
}

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv $venv
}

Write-Host "Installing Python dependencies..."
& $python -m pip install --disable-pip-version-check -r (Join-Path $repoRoot "requirements.txt")

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
