# Changelog

## 2026-05-29

- Added a CAD / 3D print build-notes page with hardware diagrams, ESP32 wiring notes, and README links.
- Fixed false `damage` events when starting a new game or changing stages by tracking HP context changes from the REFramework bridge.
- Added UI mode switches in the Control panel:
  - `Debug max Lv3`
  - `Low output Lv10`
  - `English UI`
- Added low-output normalization so the normal Lv15 scale can be sent as a max-Lv10 scale.
- Added English UI switching for the dashboard.
- Updated ESP32 button mapping to `A=GPIO33`, `B=GPIO32`, `C=GPIO25`.
- Added an emergency drain tact switch on `GPIO27`; pressing it runs `C x30`.
- Added `switchtest` and `drain` ESP32 debug commands.
- Added `tools/keyboard_button_control.py` for direct A/B/C keyboard control from the PC.
- Updated README files to describe the current BLE/USB serial ESP32 command path instead of the older HTTP-first wording.

## Earlier 2026-05

- Added BLE auto-discovery for `RealShockESP32`.
- Moved repeated A/C button sequences into the ESP32 firmware so the PC can send one event command per output.
- Added ESP32 keepalive status checks to reduce delay after idle periods.
- Added HP transient-zero handling to avoid false events around character changes.
- Added ESP32 cycle debug command for raising to a level, holding, and returning to zero.
