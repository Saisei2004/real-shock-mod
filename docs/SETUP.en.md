# RE:AL SHOCK MOD Setup

This page is the copy-paste setup guide for installing RE:AL SHOCK MOD on another PC.

Japanese setup guide: [SETUP.md](SETUP.md)

## 1. Install Required Tools

Open PowerShell and install Git and Python.

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.14 -e
```

Manual download links:

| Link | What it is |
|---|---|
| [Git for Windows](https://git-scm.com/download/win) | Required for `git clone` |
| [Python 3.14+](https://www.python.org/downloads/windows/) | Runs the local RE:AL SHOCK MOD server |
| [REFramework Releases](https://github.com/praydog/REFramework/releases) | Mod framework used to read the game state |

## 2. Clone The Repository

Run this in any folder where you want the project.

```powershell
git clone https://github.com/Saisei2004/real-shock-mod.git
cd real-shock-mod
```

Without Git:

[Download ZIP](https://github.com/Saisei2004/real-shock-mod/archive/refs/heads/main.zip)

If you use ZIP, extract it and open PowerShell in the extracted folder.

## 3. Install

```powershell
.\Install-RE-AL-SHOCK-MOD.cmd
```

This does the following:

- Creates a Python virtual environment
- Installs Python dependencies
- Installs the REFramework Lua Bridge
- Creates a desktop shortcut

## 4. Install REFramework Too

If REFramework is not installed yet, use this command.

```powershell
.\scripts\Install-RealShockMod.ps1 -InstallRe9Bridge -InstallREFramework -IUnderstandGameMayBeAffected
```

Install only the Lua Bridge:

```powershell
.\scripts\Install-Re9Bridge.ps1 -InstallLua
```

Check bridge status only:

```powershell
.\scripts\Install-Re9Bridge.ps1
```

## 5. Configure ESP32 BLE

This revision auto-discovers the ESP32 over BLE. The ESP32 advertises as `RealShockESP32`, and the PC connects to it when the system starts.

```powershell
$env:REAL_SHOCK_ESP32_TRANSPORT = "ble"
$env:REAL_SHOCK_ESP32_BLE_NAME = "RealShockESP32"
```

macOS / zsh:

```bash
export REAL_SHOCK_ESP32_TRANSPORT=ble
export REAL_SHOCK_ESP32_BLE_NAME=RealShockESP32
```

Main environment variables:

```powershell
$env:REAL_SHOCK_PORT = "8765"
$env:REAL_SHOCK_H6_ADDRESS = ""
$env:REAL_SHOCK_H6_NAME_PREFIX = "H6"
$env:REAL_SHOCK_ESP32_TRANSPORT = "ble"
$env:REAL_SHOCK_ESP32_BLE_NAME = "RealShockESP32"
$env:REAL_SHOCK_ESP32_BLE_SCAN_SECONDS = "6.0"
$env:REAL_SHOCK_ESP32_TIMEOUT = "2.0"
```

| Variable | Meaning |
|---|---|
| `REAL_SHOCK_PORT` | Local server port |
| `REAL_SHOCK_H6_ADDRESS` | BLE address. Leave empty for auto-detect |
| `REAL_SHOCK_H6_NAME_PREFIX` | Heart-rate sensor name prefix |
| `REAL_SHOCK_ESP32_TRANSPORT` | `ble` / `serial` / `http`. Default: `ble` |
| `REAL_SHOCK_ESP32_BLE_NAME` | BLE name used for ESP32 auto-discovery |
| `REAL_SHOCK_ESP32_BLE_SCAN_SECONDS` | ESP32 scan time |
| `REAL_SHOCK_ESP32_TIMEOUT` | ESP32 send timeout in seconds |

USB serial is still available as a debug fallback. Use `REAL_SHOCK_ESP32_TRANSPORT=serial` plus `REAL_SHOCK_ESP32_SERIAL_PORT`. HTTP mode is used only when `REAL_SHOCK_ESP32_TRANSPORT=http` and `REAL_SHOCK_ESP32_URL` are set.

## 6. Launch

```powershell
.\Start-RE-AL-SHOCK-MOD.cmd
```

Or:

```powershell
.\scripts\Start-RealShockMod.ps1
```

Open this in the browser:

```text
http://127.0.0.1:8765/
```

## 7. Open Demo UI

You can preview the UI with pseudo-data even without the game or heart-rate sensor.

```text
http://127.0.0.1:8765/?demo=damage
```

Available demo values:

```text
normal
startle
damage
faltering
death
```

## 8. Target Game Links

| Link | What it is |
|---|---|
| [Steam store page](https://store.steampowered.com/app/3764200/Resident_Evil_Requiem/) | Steam version of BIOHAZARD Requiem / Resident Evil Requiem |
| [CAPCOM official page](https://www.residentevil.com/requiem/) | Official page for BIOHAZARD Requiem / Resident Evil Requiem |
