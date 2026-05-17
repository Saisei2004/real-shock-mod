$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $repoRoot "scripts\Start-RealShockMod.ps1"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "RE AL SHOCK MOD.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$shortcut.WorkingDirectory = $repoRoot
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
$shortcut.Description = "Launch RE:AL SHOCK MOD"
$shortcut.Save()

Write-Host "Created shortcut: $shortcutPath"
