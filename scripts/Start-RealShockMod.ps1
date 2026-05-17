$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venv = Join-Path $repoRoot ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$requirements = Join-Path $repoRoot "requirements.txt"
$app = Join-Path $repoRoot "h6_monitor_server.py"
$port = if ($env:REAL_SHOCK_PORT) { [int]$env:REAL_SHOCK_PORT } else { 8765 }

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv $venv
}

Write-Host "Installing/updating dependencies..."
& $python -m pip install --disable-pip-version-check -r $requirements

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    Write-Host "RE:AL SHOCK MOD is already running on port $port."
    Start-Process "http://127.0.0.1:$port/"
    exit 0
}

Write-Host "Starting RE:AL SHOCK MOD..."
& $python $app --port $port --open-browser
