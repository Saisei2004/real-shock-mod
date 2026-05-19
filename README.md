# RE:AL SHOCK MOD

RE:AL SHOCK MOD は、RE9 のHP状態と H6 心拍センサーの反応を読み取り、ESP32 につないだ **LEDテストデバイス** を光らせるローカル連携システムです。

この版は実電撃デバイス向けではありません。A/B/C の3ボタンを ESP32 から押すことで、LEDテストデバイスの「威力レベル」と「モード」を再現します。

## 現在の前提

- ESP32 のピンは `GPIO23=A`, `GPIO22=B`, `GPIO19=C`
- A: 威力アップ
- B: モード変更
- C: 威力ダウン
- デバイス起動直後は `-1`、Aを1回押すと `0`
- `0` のまま15秒程度で電源OFF扱いになるため、13秒以上 `0` が続いた後の出力前は C を1回押して `-1` として扱う
- 新しく起動した時は B を2回押してモード3にする
- 最大威力は `15`

## イベント優先度

同時に複数のイベントがある時は、次の順に優先します。

```text
death > damage > startle > faltering > none
```

ただし `faltering` は他イベントに上書きされていても、裏で経過時間を更新し続けます。上位イベントが終わって `faltering` が前面に戻った時は、その時点の経過時間に応じた威力になります。

## 出力ルール

### none

通常状態です。LEDテストデバイスは基本的に `0` 以下へ戻します。

### damage

残りHP割合で威力と持続時間を変えます。

| 残りHP | 威力 | 時間 |
|---:|---:|---:|
| 0 - 16.75% | 14 | 4.0秒 |
| - 33.5% | 12 | 3.5秒 |
| - 50.25% | 10 | 3.0秒 |
| - 67% | 8 | 2.5秒 |
| - 83.75% | 6 | 2.0秒 |
| - 100% | 4 | 1.0秒 |

### faltering

ゲーム側が Danger 状態になったら発動します。固定の 16.75% 判定だけに依存せず、REFramework Bridge の `low_hp_stage == "danger"` または Danger 閾値を優先します。

| Danger 経過 | 威力 |
|---:|---:|
| 0 - 3秒 | 3 |
| その後2秒 | +1 |
| その後3秒 | +1 |
| その後4秒 | +1 |
| 以降も同様 | 最大10 |

### death

威力 `15`、10秒。

### startle

威力 `5 - 15` のランダム、時間 `1 - 4秒` のランダム。

## セットアップ

Python依存関係:

```bash
python -m pip install -r requirements.txt
```

ESP32 はPCにUSB接続し、既定では `/dev/cu.usbserial-120` を使います。別ポートなら環境変数を指定します。

```bash
export REAL_SHOCK_ESP32_SERIAL_PORT=/dev/cu.usbserial-120
```

サーバー起動:

```bash
python h6_monitor_server.py --open-browser
```

ESP32 に送る内容は Web UI の ESP32 行と Active Command 詳細に表示されます。

## ESP32ファーム

Arduinoスケッチ:

```text
esp32/real_shock_led_controller/real_shock_led_controller.ino
```

シリアルコマンド例:

```text
status
none
level 8
button A
event damage 14 4000 1
event death 15 10000 2
```

デバッグツール:

```bash
python tools/esp32_debug.py status
python tools/esp32_debug.py fire 10 3
python tools/esp32_debug.py event damage 14 4000 1
python tools/esp32_debug.py none
```

## REFramework Bridge

`reframework/re9_hp_web_bridge.lua` は、HP、最大HP、HP%、damage_count、Danger/Caution/Fine のステージ情報を `re9_hp_web_status.json` に書き出します。

Danger 判定は、ゲーム側の vital 値や `get_BottomOfVitalDanger` を優先します。閾値が取れない場合のみフォールバック値を使います。

## 注意

このリポジトリはLEDテストデバイス用です。人や動物へ電気刺激を与える装置の製作・制御・運用を目的にしないでください。
