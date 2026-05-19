# RE:AL SHOCK MOD

RE:AL SHOCK MOD is a local RE9 + H6 heart-rate monitor bridge for an **LED test device** driven by an ESP32.

This revision is not for real electric stimulation hardware. The ESP32 presses three test-device buttons and maps game/biometric events to LED intensity and duration.

## Device Assumptions

- `GPIO23=A`, `GPIO22=B`, `GPIO19=C`
- A: intensity up
- B: mode change
- C: intensity down
- Initial device level is treated as `-1`; pressing A once moves it to `0`
- If level `0` remains for about 15 seconds, the device is treated as powered off
- If level `0` has been idle for 13+ seconds, the ESP32 presses C once before the next output, then presses A `target + 1` times
- On every fresh startup, the ESP32 presses B twice to enter mode 3
- Maximum intensity is `15`

## Priority

```text
death > damage > startle > faltering > none
```

`faltering` keeps updating its elapsed timer even when a higher-priority event is active.

## Output Rules

### none

Return the LED test device to level `0` or below.

### damage

| Remaining HP | Intensity | Duration |
|---:|---:|---:|
| 0 - 16.75% | 14 | 4.0s |
| - 33.5% | 12 | 3.5s |
| - 50.25% | 10 | 3.0s |
| - 67% | 8 | 2.5s |
| - 83.75% | 6 | 2.0s |
| - 100% | 4 | 1.0s |

### faltering

Starts when the game reports Danger. The bridge prefers the game vital stage and `get_BottomOfVitalDanger` over a fixed percentage.

Intensity starts at `3` for the first 3 seconds. It then increases by 1 after 2 more seconds, then after 3 more seconds, then after 4 more seconds, up to `10`.

### death

Intensity `15` for 10 seconds.

### startle

Random intensity `5 - 15`, random duration `1 - 4 seconds`.

## Setup

```bash
python -m pip install -r requirements.txt
export REAL_SHOCK_ESP32_SERIAL_PORT=/dev/cu.usbserial-120
python h6_monitor_server.py --open-browser
```

## ESP32 Firmware

Arduino sketch:

```text
esp32/real_shock_led_controller/real_shock_led_controller.ino
```

Serial commands:

```text
status
none
level 8
button A
event damage 14 4000 1
event death 15 10000 2
```

Debug tool:

```bash
python tools/esp32_debug.py status
python tools/esp32_debug.py fire 10 3
python tools/esp32_debug.py event damage 14 4000 1
python tools/esp32_debug.py none
```

## Safety Boundary

This repository targets an LED test device only. Do not use it to build, control, or operate equipment that applies electric stimulation to people or animals.
