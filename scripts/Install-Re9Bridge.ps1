param(
    [switch]$InstallLua,
    [switch]$InstallREFramework,
    [switch]$IUnderstandGameMayBeAffected,
    [switch]$AllowWhileGameRunning,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Get-SteamRoots {
    $roots = New-Object System.Collections.Generic.List[string]
    $default = "C:\Program Files (x86)\Steam"
    if (Test-Path -LiteralPath $default) { $roots.Add($default) }

    $libraryFile = Join-Path $default "steamapps\libraryfolders.vdf"
    if (Test-Path -LiteralPath $libraryFile) {
        $text = Get-Content -LiteralPath $libraryFile -Raw
        [regex]::Matches($text, '"path"\s+"([^"]+)"') | ForEach-Object {
            $path = $_.Groups[1].Value.Replace("\\", "\")
            if ((Test-Path -LiteralPath $path) -and -not $roots.Contains($path)) {
                $roots.Add($path)
            }
        }
    }
    return $roots
}

function Find-Re9GameDir {
    foreach ($root in Get-SteamRoots) {
        $manifest = Join-Path $root "steamapps\appmanifest_3764200.acf"
        if (-not (Test-Path -LiteralPath $manifest)) { continue }
        $text = Get-Content -LiteralPath $manifest -Raw
        $match = [regex]::Match($text, '"installdir"\s+"([^"]+)"')
        if (-not $match.Success) { continue }
        $gameDir = Join-Path (Join-Path $root "steamapps\common") $match.Groups[1].Value
        if (Test-Path -LiteralPath (Join-Path $gameDir "re9.exe")) {
            return $gameDir
        }
    }
    throw "Resident Evil Requiem install folder was not found."
}

function Install-ReFrameworkDll {
    param([string]$GameDir)

    if (-not $IUnderstandGameMayBeAffected) {
        throw "REFramework installs dinput8.dll into the game folder. Re-run with -IUnderstandGameMayBeAffected if you explicitly want that."
    }

    $dllPath = Join-Path $GameDir "dinput8.dll"
    if ((Test-Path -LiteralPath $dllPath) -and -not $Force) {
        Write-Host "dinput8.dll already exists. Use -Force to replace it."
        return
    }

    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/praydog/REFramework-nightly/releases/latest" -Headers @{ "User-Agent" = "real-shock-mod" }
    $asset = $release.assets | Where-Object { $_.name -eq "REFramework.zip" } | Select-Object -First 1
    if ($null -eq $asset) {
        $asset = $release.assets | Where-Object { $_.name -eq "RE9.zip" } | Select-Object -First 1
    }
    if ($null -eq $asset) {
        throw "Could not find REFramework.zip or RE9.zip in latest REFramework-nightly release."
    }

    $tmp = Join-Path $env:TEMP ("real-shock-reframework-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $zip = Join-Path $tmp $asset.name
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -Headers @{ "User-Agent" = "real-shock-mod" }
    Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force

    $downloadedDll = Get-ChildItem -LiteralPath $tmp -Filter "dinput8.dll" -Recurse | Select-Object -First 1
    if ($null -eq $downloadedDll) {
        throw "Downloaded REFramework archive did not contain dinput8.dll."
    }

    if (Test-Path -LiteralPath $dllPath) {
        $backup = Join-Path $GameDir ("dinput8.dll.backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        Copy-Item -LiteralPath $dllPath -Destination $backup
        Write-Host "Backed up existing dinput8.dll to $backup"
    }
    Copy-Item -LiteralPath $downloadedDll.FullName -Destination $dllPath -Force
    Write-Host "Installed REFramework dinput8.dll from $($asset.name)."
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$gameDir = Find-Re9GameDir
$autorunDir = Join-Path $gameDir "reframework\autorun"
$dataDir = Join-Path $gameDir "reframework\data"

$gameProcess = Get-Process -Name "re9" -ErrorAction SilentlyContinue
if (($InstallLua -or $InstallREFramework) -and $null -ne $gameProcess -and -not $AllowWhileGameRunning) {
    throw "re9.exe is running. Close the game before installing files, or re-run with -AllowWhileGameRunning if you deliberately want to modify files while the game is open."
}

if ($InstallREFramework) {
    Install-ReFrameworkDll -GameDir $gameDir
}

if ($InstallLua) {
    New-Item -ItemType Directory -Path $autorunDir -Force | Out-Null
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
    $sourceLua = Join-Path $repoRoot "reframework\re9_hp_web_bridge.lua"
    $targetLua = Join-Path $autorunDir "re9_hp_web_bridge.lua"
    Copy-Item -LiteralPath $sourceLua -Destination $targetLua -Force
    Write-Host "Installed RE:AL SHOCK Lua bridge: $targetLua"

    $sourceConfig = Join-Path $repoRoot "reframework\re9_hp_web_config.example.json"
    $targetConfig = Join-Path $dataDir "re9_hp_web_config.json"
    if (-not (Test-Path -LiteralPath $targetConfig)) {
        Copy-Item -LiteralPath $sourceConfig -Destination $targetConfig
        Write-Host "Installed default bridge config: $targetConfig"
    }
}

$dllPath = Join-Path $gameDir "dinput8.dll"
$luaPath = Join-Path $autorunDir "re9_hp_web_bridge.lua"
Write-Host "Game folder: $gameDir"
Write-Host "REFramework dinput8.dll installed: $(Test-Path -LiteralPath $dllPath)"
Write-Host "HP Lua bridge installed: $(Test-Path -LiteralPath $luaPath)"
if (-not $InstallLua -and -not $InstallREFramework) {
    Write-Host "No changes made. Use -InstallLua for the Lua bridge, and -InstallREFramework -IUnderstandGameMayBeAffected only when REFramework is not installed yet."
}
