$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venv = Join-Path $repoRoot ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$requirements = Join-Path $repoRoot "requirements.txt"
$app = Join-Path $repoRoot "h6_monitor_server.py"
$port = if ($env:REAL_SHOCK_PORT) { [int]$env:REAL_SHOCK_PORT } else { 8765 }

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

Write-Host "Installing/updating dependencies..."
& $python -m pip install --upgrade pip
& $python -m pip install --upgrade -r $requirements

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    Write-Host "RE:AL SHOCK MOD is already running on port $port."
    Start-Process "http://127.0.0.1:$port/"
    exit 0
}

Write-Host "Starting RE:AL SHOCK MOD..."
& $python $app --port $port --open-browser
