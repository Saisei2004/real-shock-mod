# RE:AL SHOCK MOD セットアップ

このページは、RE:AL SHOCK MODを別PCでも迷わず入れるための導入手順です。

English setup guide: [SETUP.en.md](SETUP.en.md)

## 1. 必要なものを入れる

PowerShellを開いて、まずGitとPythonを入れます。

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.14 -e
```

手動で入れる場合:

| リンク | 何か |
|---|---|
| [Git for Windows](https://git-scm.com/download/win) | `git clone` するために必要 |
| [Python 3.14+](https://www.python.org/downloads/windows/) | RE:AL SHOCK MODのローカルサーバーを動かす |
| [REFramework Releases](https://github.com/praydog/REFramework/releases) | バイオハザード側の状態を読むMOD基盤 |

## 2. リポジトリを取得する

好きなフォルダで実行します。

```powershell
git clone https://github.com/Saisei2004/real-shock-mod.git
cd real-shock-mod
```

Gitを使わない場合はこちら:

[Download ZIP](https://github.com/Saisei2004/real-shock-mod/archive/refs/heads/main.zip)

ZIPで落とした場合は、展開したフォルダでPowerShellを開いてください。

## 3. インストールする

```powershell
.\Install-RE-AL-SHOCK-MOD.cmd
```

これで以下をまとめて行います。

- Python仮想環境の作成
- Python依存パッケージの導入
- REFramework Lua Bridgeの配置
- デスクトップショートカットの作成

## 4. REFrameworkも入れる場合

まだREFrameworkを入れていないPCでは、こちらを使います。

```powershell
.\scripts\Install-RealShockMod.ps1 -InstallRe9Bridge -InstallREFramework -IUnderstandGameMayBeAffected
```

Lua Bridgeだけ入れたい場合:

```powershell
.\scripts\Install-Re9Bridge.ps1 -InstallLua
```

状態確認だけしたい場合:

```powershell
.\scripts\Install-Re9Bridge.ps1
```

## 5. ESP32へ送るURLを設定する

ESP32へコマンドを送る場合は、起動前にURLを指定します。

```powershell
$env:REAL_SHOCK_ESP32_URL = "http://192.168.0.50/command"
```

設定できる主な環境変数:

```powershell
$env:REAL_SHOCK_PORT = "8765"
$env:REAL_SHOCK_H6_ADDRESS = ""
$env:REAL_SHOCK_H6_NAME_PREFIX = "H6"
$env:REAL_SHOCK_ESP32_URL = "http://192.168.0.50/command"
$env:REAL_SHOCK_ESP32_TIMEOUT = "2.0"
```

| 変数 | 説明 |
|---|---|
| `REAL_SHOCK_PORT` | ローカルサーバーのポート |
| `REAL_SHOCK_H6_ADDRESS` | BLEアドレス指定。空なら自動検出 |
| `REAL_SHOCK_H6_NAME_PREFIX` | 心拍センサ名の先頭 |
| `REAL_SHOCK_ESP32_URL` | ESP32へ送るHTTP URL |
| `REAL_SHOCK_ESP32_TIMEOUT` | ESP32送信タイムアウト秒 |

## 6. 起動する

```powershell
.\Start-RE-AL-SHOCK-MOD.cmd
```

または:

```powershell
.\scripts\Start-RealShockMod.ps1
```

起動後にブラウザで開きます。

```text
http://127.0.0.1:8765/
```

## 7. README用デモUIを開く

実機や心拍センサがなくても、疑似データでUIを確認できます。

```text
http://127.0.0.1:8765/?demo=damage
```

使えるデモ値:

```text
normal
startle
damage
faltering
death
```

## 8. 対象ゲームリンク

| リンク | 内容 |
|---|---|
| [Steam購入ページ](https://store.steampowered.com/app/3764200/Resident_Evil_Requiem/) | Steam版 BIOHAZARD requiem / Resident Evil Requiem |
| [CAPCOM公式ページ](https://www.residentevil.com/requiem/ja-jp/) | バイオハザード レクイエム / Resident Evil Requiem 公式ページ |
