param(
    [switch]$RemoveREFramework,
    [switch]$RemoveData,
    [switch]$AllowWhileGameRunning
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

$gameDir = Find-Re9GameDir
$gameProcess = Get-Process -Name "re9" -ErrorAction SilentlyContinue
if ($null -ne $gameProcess -and -not $AllowWhileGameRunning) {
    throw "re9.exe is running. Close the game before removing files, or re-run with -AllowWhileGameRunning if you deliberately want to modify files while the game is open."
}

$lua = Join-Path $gameDir "reframework\autorun\re9_hp_web_bridge.lua"
if (Test-Path -LiteralPath $lua) {
    Remove-Item -LiteralPath $lua -Force
    Write-Host "Removed Lua bridge: $lua"
}

$probe = Join-Path $gameDir "reframework\autorun\re9_hp_type_probe.lua"
if (Test-Path -LiteralPath $probe) {
    Remove-Item -LiteralPath $probe -Force
    Write-Host "Removed type probe: $probe"
}

$liveProbe = Join-Path $gameDir "reframework\autorun\re9_hp_live_probe.lua"
if (Test-Path -LiteralPath $liveProbe) {
    Remove-Item -LiteralPath $liveProbe -Force
    Write-Host "Removed live probe: $liveProbe"
}

$damageSelfTest = Join-Path $gameDir "reframework\autorun\re9_hp_damage_selftest.lua"
if (Test-Path -LiteralPath $damageSelfTest) {
    Remove-Item -LiteralPath $damageSelfTest -Force
    Write-Host "Removed damage self-test: $damageSelfTest"
}

if ($RemoveREFramework) {
    $dll = Join-Path $gameDir "dinput8.dll"
    if (Test-Path -LiteralPath $dll) {
        Remove-Item -LiteralPath $dll -Force
        Write-Host "Removed REFramework loader: $dll"
    }
}

if ($RemoveData) {
    $dataDir = Join-Path $gameDir "reframework\data"
    foreach ($name in @("re9_hp_web_status.json", "re9_hp_web_config.json", "re9_hp_type_probe.json", "re9_hp_live_probe.json", "re9_hp_damage_selftest.json")) {
        $path = Join-Path $dataDir $name
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force
            Write-Host "Removed data file: $path"
        }
    }
}

Write-Host "Done."
