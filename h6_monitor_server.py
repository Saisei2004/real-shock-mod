import argparse
import asyncio
import csv
import json
import math
import os
import re
import statistics
import subprocess
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web
from bleak import BleakClient, BleakScanner


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
RECORDINGS_DIR = ROOT / "recordings"
RUNTIME_DIR = ROOT / "runtime"

TARGET_ADDRESS = os.environ.get("REAL_SHOCK_H6_ADDRESS", "").strip().upper()
TARGET_ADDRESS_FLAT = TARGET_ADDRESS.replace(":", "").upper()
TARGET_NAME_PREFIX = os.environ.get("REAL_SHOCK_H6_NAME_PREFIX", "H6").strip().upper()
DEFAULT_HOST = os.environ.get("REAL_SHOCK_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("REAL_SHOCK_PORT", "8765"))
ESP32_COMMAND_URL = os.environ.get("REAL_SHOCK_ESP32_URL", "").strip()
ESP32_TIMEOUT_SECONDS = float(os.environ.get("REAL_SHOCK_ESP32_TIMEOUT", "2.0"))

RE9_APPID = "3764200"
RE9_PROCESS_NAMES = {"re9.exe", "re9"}
RE9_STATUS_FILE = "re9_hp_web_status.json"
RE9_COMMAND_LOG = RUNTIME_DIR / "re9_h6_commands.jsonl"
RE9_FALTERING_HP_PERCENT = 16.75

COMMAND_PRIORITY = {
    "none": 0,
    "faltering": 1,
    "startle": 2,
    "damage": 3,
    "death": 4,
}

COMMAND_LABELS = {
    "none": "なし",
    "faltering": "ふらつき",
    "startle": "びっくり",
    "damage": "ダメージ",
    "death": "死亡",
}

COMMAND_DEFAULT_TTL = {
    "damage": 3.0,
    "startle": 3.5,
    "faltering": 1.2,
}

HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"
BODY_SENSOR_LOCATION = "00002a38-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"

PERSONAL_BASELINE = {
    "bpm": 74.8,
    "rr_ms": 800.6,
    "rmssd_ms": 35.9,
    "sdnn_ms": 73.7,
    "pnn50_percent": 12.7,
}
REACTION_TRACK_SECONDS = 3

DEVICE_INFO = {
    "model": "00002a24-0000-1000-8000-00805f9b34fb",
    "serial": "00002a25-0000-1000-8000-00805f9b34fb",
    "hardware": "00002a27-0000-1000-8000-00805f9b34fb",
    "firmware": "00002a26-0000-1000-8000-00805f9b34fb",
    "software": "00002a28-0000-1000-8000-00805f9b34fb",
}


def decode_hr_measurement(data):
    payload = bytes(data)
    if len(payload) < 2:
        return {"error": "too_short", "raw_hex": payload.hex(" ").upper()}

    flags = payload[0]
    offset = 1
    if flags & 0x01:
        if len(payload) < offset + 2:
            return {"error": "incomplete_hr16", "raw_hex": payload.hex(" ").upper()}
        bpm = int.from_bytes(payload[offset:offset + 2], "little")
        offset += 2
    else:
        bpm = payload[offset]
        offset += 1

    energy = None
    if flags & 0x08 and len(payload) >= offset + 2:
        energy = int.from_bytes(payload[offset:offset + 2], "little")
        offset += 2

    rr_ms = []
    if flags & 0x10:
        while len(payload) >= offset + 2:
            raw = int.from_bytes(payload[offset:offset + 2], "little")
            rr_ms.append(raw * 1000 / 1024)
            offset += 2

    contact_supported = bool(flags & 0x04)
    contact_detected = bool(flags & 0x02) if contact_supported else None

    return {
        "bpm": bpm,
        "rr_ms": rr_ms,
        "energy_kj": energy,
        "contact_supported": contact_supported,
        "contact_detected": contact_detected,
        "flags": flags,
        "raw_hex": payload.hex(" ").upper(),
    }


def rmssd(values):
    if len(values) < 2:
        return None
    diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
    return math.sqrt(sum(d * d for d in diffs) / len(diffs))


def sdnn(values):
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def pnn50(values):
    if len(values) < 2:
        return None
    diffs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return 100 * sum(1 for d in diffs if d > 50) / len(diffs)


def rounded(value, digits=1):
    if value is None:
        return None
    return round(value, digits)


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def mean_or_none(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return statistics.mean(values)


def infer_state(bpm, rmssd_value, contact_detected, sample_count):
    if contact_detected is False:
        return {
            "label": "接触不安定",
            "tone": "warn",
            "detail": "ベルトの電極接触が弱い可能性があります。",
        }
    if sample_count < 12 or bpm is None or rmssd_value is None:
        return {
            "label": "計測中",
            "tone": "neutral",
            "detail": "もう少し RR interval を集めています。",
        }
    if bpm >= 105 or rmssd_value < 20:
        return {
            "label": "負荷高め",
            "tone": "hot",
            "detail": "覚醒・運動・緊張・疲労などで自律神経負荷が高いサインです。",
        }
    if bpm <= 82 and rmssd_value >= 45:
        return {
            "label": "落ち着き",
            "tone": "calm",
            "detail": "心拍と HRV からは回復寄りの状態に見えます。",
        }
    if bpm <= 92 and rmssd_value >= 28:
        return {
            "label": "安定",
            "tone": "steady",
            "detail": "大きな負荷サインは少なめです。",
        }
    return {
        "label": "やや負荷",
        "tone": "warm",
        "detail": "緊張・集中・姿勢変化などの影響が出ているかもしれません。",
    }


def _parse_acf_value(text, key):
    match = re.search(rf'"{re.escape(key)}"\s+"([^"]+)"', text)
    return match.group(1) if match else None


def _steam_roots():
    roots = []
    default = Path(r"C:\Program Files (x86)\Steam")
    if default.exists():
        roots.append(default)

    library_file = default / "steamapps" / "libraryfolders.vdf"
    if library_file.exists():
        text = library_file.read_text(encoding="utf-8", errors="ignore")
        for raw in re.findall(r'"path"\s+"([^"]+)"', text):
            path = Path(raw.replace("\\\\", "\\"))
            if path.exists() and path not in roots:
                roots.append(path)
    return roots


def find_re9_game_dir():
    for root in _steam_roots():
        manifest = root / "steamapps" / f"appmanifest_{RE9_APPID}.acf"
        if not manifest.exists():
            continue
        text = manifest.read_text(encoding="utf-8", errors="ignore")
        install_dir = _parse_acf_value(text, "installdir")
        if not install_dir:
            continue
        game_dir = root / "steamapps" / "common" / install_dir
        if (game_dir / "re9.exe").exists():
            return game_dir
    known = Path(r"C:\Program Files (x86)\Steam\steamapps\common\RESIDENT EVIL requiem BIOHAZARD requiem")
    return known if (known / "re9.exe").exists() else None


def re9_status_paths(game_dir):
    paths = []
    if game_dir:
        paths.append(game_dir / "reframework" / "data" / RE9_STATUS_FILE)
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(Path(appdata) / "REFramework" / "data" / RE9_STATUS_FILE)
    return paths


def re9_install_state(game_dir):
    if not game_dir:
        return {
            "reframework_loader": False,
            "lua_bridge": False,
            "clean": True,
        }
    loader = game_dir / "dinput8.dll"
    lua = game_dir / "reframework" / "autorun" / "re9_hp_web_bridge.lua"
    return {
        "reframework_loader": loader.exists(),
        "lua_bridge": lua.exists(),
        "clean": not loader.exists() and not lua.exists(),
        "loader_path": str(loader),
        "lua_path": str(lua),
    }


def find_re9_process():
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=3,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) < 2:
            continue
        name = row[0].strip('"').lower()
        if name in RE9_PROCESS_NAMES:
            try:
                pid = int(row[1].strip('"'))
            except ValueError:
                pid = None
            return {"pid": pid, "name": row[0].strip('"'), "exe": None, "started_at": None}
    return None


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _hp_percent(hp, max_hp, bridge):
    explicit = _num(bridge.get("hp_percent")) if bridge else None
    if explicit is not None:
        return max(0.0, min(100.0, explicit))
    if hp is None or max_hp in (None, 0):
        return None
    return max(0.0, min(100.0, hp / max_hp * 100.0))


class CommandBus:
    def __init__(self, log_path):
        self.log_path = log_path
        self.events = deque(maxlen=200)
        self.sequence = 0
        self.signals = {}
        self.active_command = None

    def issue(self, kind, source, payload=None, ttl=None, force_event=True):
        return self.activate(kind, source, payload=payload, ttl=ttl, force_event=force_event)

    def activate(self, kind, source, payload=None, ttl=None, force_event=False):
        now = time.time()
        if kind not in COMMAND_PRIORITY:
            kind = "none"
        if kind == "none":
            self.signals.clear()
        else:
            if ttl is None:
                ttl = COMMAND_DEFAULT_TTL.get(kind)
            self.signals[kind] = {
                "kind": kind,
                "label": COMMAND_LABELS.get(kind, kind),
                "source": source,
                "payload": payload or {},
                "priority": COMMAND_PRIORITY[kind],
                "updated_at": now,
                "expires_at": now + ttl if ttl else None,
            }
        return self.refresh(now=now, force_event=force_event, requested_kind=kind)

    def deactivate(self, kind, source=None):
        signal = self.signals.get(kind)
        if signal and (source is None or signal.get("source") == source):
            del self.signals[kind]
        return self.refresh()

    def refresh(self, now=None, force_event=False, requested_kind=None):
        now = now or time.time()
        expired = [
            kind for kind, signal in self.signals.items()
            if signal.get("expires_at") is not None and signal["expires_at"] <= now
        ]
        for kind in expired:
            del self.signals[kind]

        if self.signals:
            selected = max(
                self.signals.values(),
                key=lambda signal: (signal["priority"], signal["updated_at"]),
            )
        else:
            selected = {
                "kind": "none",
                "label": COMMAND_LABELS["none"],
                "source": "command-priority",
                "payload": {},
                "priority": COMMAND_PRIORITY["none"],
                "updated_at": now,
                "expires_at": None,
            }

        previous_kind = self.active_command.get("kind") if self.active_command else None
        self.active_command = dict(selected)
        if previous_kind != selected["kind"] or (force_event and selected["kind"] == requested_kind):
            return self._append_event(selected, now)
        return None

    def _append_event(self, command, now):
        now = time.time()
        self.sequence += 1
        event = {
            "id": self.sequence,
            "kind": command["kind"],
            "label": command.get("label") or COMMAND_LABELS.get(command["kind"], command["kind"]),
            "source": command.get("source"),
            "priority": command.get("priority", 0),
            "time": now,
            "iso_time": datetime.now().isoformat(timespec="milliseconds"),
            "payload": command.get("payload") or {},
        }
        self.events.appendleft(event)
        self._write_log(event)
        return event

    def _write_log(self, event):
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def snapshot(self):
        self.refresh()
        return {
            "log_path": str(self.log_path),
            "active": self.active_command,
            "priority_order": ["death", "damage", "startle", "faltering", "none"],
            "signals": list(self.signals.values()),
            "recent": list(self.events),
        }


class ESP32CommandSender:
    def __init__(self, command_bus, url):
        self.command_bus = command_bus
        self.url = url
        self.last_sent_id = 0
        self.latest = {
            "enabled": bool(url),
            "url": url or None,
            "status": "disabled" if not url else "waiting",
            "last_sent": None,
            "last_error": None,
        }

    def snapshot(self):
        return dict(self.latest)

    async def run(self):
        if not self.url:
            return
        timeout = ClientTimeout(total=ESP32_TIMEOUT_SECONDS)
        async with ClientSession(timeout=timeout) as session:
            while True:
                pending = [
                    event for event in reversed(list(self.command_bus.events))
                    if event.get("id", 0) > self.last_sent_id
                ]
                for event in pending:
                    await self._send_event(session, event)
                await asyncio.sleep(0.2)

    async def _send_event(self, session, event):
        payload = {
            "system": "RE:AL SHOCK MOD",
            "command": event.get("kind"),
            "label": event.get("label"),
            "priority": event.get("priority"),
            "source": event.get("source"),
            "issued_at": event.get("iso_time"),
            "payload": event.get("payload") or {},
        }
        try:
            async with session.post(self.url, json=payload) as response:
                text = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}: {text[:160]}")
            self.last_sent_id = event.get("id", self.last_sent_id)
            self.latest.update({
                "enabled": True,
                "status": "sent",
                "last_sent": {
                    "id": event.get("id"),
                    "kind": event.get("kind"),
                    "label": event.get("label"),
                    "iso_time": event.get("iso_time"),
                },
                "last_error": None,
            })
        except Exception as exc:
            self.latest.update({
                "enabled": True,
                "status": "error",
                "last_error": str(exc),
            })


class GameMonitor:
    def __init__(self, command_bus, game_dir=None):
        self.command_bus = command_bus
        self.game_dir = game_dir or find_re9_game_dir()
        self.previous_hp = None
        self.previous_damage_count = 0
        self.death_latched = False
        self.latest = self.empty_snapshot()
        self.on_change = None

    def empty_snapshot(self):
        return {
            "ok": True,
            "game": {
                "appid": RE9_APPID,
                "dir": str(self.game_dir) if self.game_dir else None,
                "process": None,
                "running": False,
                "install": re9_install_state(self.game_dir),
            },
            "bridge": {
                "path": None,
                "present": False,
                "age_seconds": None,
                "fresh": False,
                "version": None,
                "stale_reason": "ゲーム内ブリッジからの新しい更新がありません。",
            },
            "player": {
                "found": False,
                "hp": None,
                "max_hp": None,
                "hp_percent": None,
                "low_hp": False,
                "faltering_low_hp": False,
                "low_hp_stage": None,
                "last_damage": None,
                "damage_count": 0,
                "reader": None,
                "character": None,
            },
            "raw": None,
            "updated_at": None,
        }

    def snapshot(self):
        return json.loads(json.dumps(self.latest, ensure_ascii=False, default=str))

    async def run(self):
        while True:
            changed = self.poll_once()
            if changed and self.on_change:
                await self.on_change()
            await asyncio.sleep(0.25)

    def poll_once(self):
        process = find_re9_process()
        paths = re9_status_paths(self.game_dir)
        selected_path = next((path for path in paths if path.exists()), None)
        bridge = self._load_status(selected_path) if selected_path else None
        now = time.time()
        emitted = False

        bridge_age = None
        bridge_fresh = False
        if selected_path:
            try:
                status_mtime = selected_path.stat().st_mtime
                bridge_age = max(0.0, now - status_mtime)
                bridge_fresh = bridge_age < 2.0
            except OSError:
                bridge_fresh = False

        active_bridge = bridge if bridge_fresh else None
        hp = _num(active_bridge.get("hp")) if active_bridge else None
        max_hp = _num(active_bridge.get("max_hp")) if active_bridge else None
        hp_percent = _hp_percent(hp, max_hp, active_bridge)
        bridge_damage_count = int(_num(active_bridge.get("damage_count")) or 0) if active_bridge else 0
        faltering = bool(active_bridge and active_bridge.get("faltering_low_hp"))
        if hp_percent is not None and hp_percent <= RE9_FALTERING_HP_PERCENT:
            faltering = True

        if active_bridge and bridge_damage_count > self.previous_damage_count:
            amount = _num(active_bridge.get("last_damage"))
            event = self.command_bus.issue("damage", "re9-bridge", {
                "hp": hp,
                "max_hp": max_hp,
                "hp_percent": hp_percent,
                "amount": amount,
                "damage_count": bridge_damage_count,
                "reader": active_bridge.get("reader"),
            }, ttl=3.0)
            emitted = bool(event)
            self.previous_damage_count = bridge_damage_count
        elif hp is not None and self.previous_hp is not None and hp < self.previous_hp:
            event = self.command_bus.issue("damage", "re9-hp-delta", {
                "hp": hp,
                "max_hp": max_hp,
                "hp_percent": hp_percent,
                "amount": round(self.previous_hp - hp, 3),
                "damage_count": bridge_damage_count,
            }, ttl=3.0)
            emitted = bool(event)

        if hp is not None:
            self.previous_hp = hp

        dead = hp is not None and hp <= 0
        if hp_percent is not None and hp_percent <= 0:
            dead = True
        if not active_bridge or hp is None:
            self.death_latched = False
            event = self.command_bus.deactivate("death", source="re9-bridge")
            emitted = emitted or bool(event)
        elif dead:
            event = self.command_bus.issue("death", "re9-bridge", {
                "hp": hp,
                "max_hp": max_hp,
                "hp_percent": hp_percent,
                "damage_count": bridge_damage_count,
            }, ttl=None, force_event=not self.death_latched)
            emitted = emitted or bool(event)
            self.death_latched = True
        elif hp > 0:
            self.death_latched = False
            event = self.command_bus.deactivate("death", source="re9-bridge")
            emitted = emitted or bool(event)

        if faltering and not dead:
            event = self.command_bus.issue("faltering", "re9-bridge", {
                "hp": hp,
                "max_hp": max_hp,
                "hp_percent": hp_percent,
                "threshold_percent": RE9_FALTERING_HP_PERCENT,
                "low_hp_stage": active_bridge.get("low_hp_stage") if active_bridge else None,
            }, ttl=1.2, force_event=False)
            emitted = emitted or bool(event)
        else:
            event = self.command_bus.deactivate("faltering", source="re9-bridge")
            emitted = emitted or bool(event)

        event = self.command_bus.refresh(now=now)
        emitted = emitted or bool(event)

        self.latest = {
            "ok": True,
            "game": {
                "appid": RE9_APPID,
                "dir": str(self.game_dir) if self.game_dir else None,
                "process": process,
                "running": process is not None,
                "install": re9_install_state(self.game_dir),
            },
            "bridge": {
                "path": str(selected_path) if selected_path else None,
                "present": selected_path is not None,
                "age_seconds": bridge_age,
                "fresh": bridge_fresh,
                "version": bridge.get("bridge_version") if bridge else None,
                "stale_reason": None if bridge_fresh else "ゲーム内ブリッジからの新しい更新がありません。",
            },
            "player": {
                "found": bool(active_bridge and active_bridge.get("player_found")),
                "hp": hp,
                "max_hp": max_hp,
                "hp_percent": hp_percent,
                "low_hp": bool(active_bridge and active_bridge.get("low_hp")),
                "faltering_low_hp": faltering,
                "faltering_threshold_percent": RE9_FALTERING_HP_PERCENT,
                "low_hp_stage": active_bridge.get("low_hp_stage") if active_bridge else None,
                "last_damage": _num(active_bridge.get("last_damage")) if active_bridge else None,
                "damage_count": bridge_damage_count,
                "reader": active_bridge.get("reader") if active_bridge else None,
                "character": active_bridge.get("character") if active_bridge else None,
            },
            "raw": bridge,
            "updated_at": now,
        }
        return emitted

    @staticmethod
    def _load_status(path):
        if not path:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


class H6Monitor:
    def __init__(self, command_bus=None, game_monitor=None, command_sender=None):
        self.command_bus = command_bus
        self.game_monitor = game_monitor
        self.command_sender = command_sender
        self.websockets = set()
        self.rr_window = deque(maxlen=180)
        self.hr_history = deque(maxlen=1200)
        self.rr_history = deque(maxlen=1200)
        self.hrv_history = deque(maxlen=1200)
        self.detection_history = deque(maxlen=120)
        self.reaction_tracking = None
        self.reaction_cooldown_until = 0
        self.last_startle_command_at = 0
        self.recording = None
        self.last_saved_recording = None
        self.latest = {
            "type": "snapshot",
            "status": "starting",
            "message": "起動中",
            "device": {
                "target_address": TARGET_ADDRESS,
                "name": None,
                "address": None,
                "rssi": None,
                "mtu": None,
                "info": {},
            },
            "measurement": {
                "bpm": None,
                "rr_ms": [],
                "battery_percent": None,
                "contact_supported": None,
                "contact_detected": None,
                "last_raw_hex": None,
                "last_seen": None,
            },
            "hrv": {
                "rmssd_ms": None,
                "sdnn_ms": None,
                "pnn50_percent": None,
                "rr_count": 0,
            },
            "state": infer_state(None, None, None, 0),
            "history": {"hr": [], "rr": []},
            "recording": self.recording_snapshot(),
            "detection": self.empty_detection(),
        }

    def snapshot_payload(self):
        payload = json.loads(json.dumps(self.latest, ensure_ascii=False, default=str))
        payload["game"] = self.game_monitor.snapshot() if self.game_monitor else None
        payload["commands"] = self.command_bus.snapshot() if self.command_bus else {"recent": []}
        payload["esp32"] = self.command_sender.snapshot() if self.command_sender else {"enabled": False}
        return payload

    def empty_detection(self):
        return {
            "primary": "計測中",
            "tone": "neutral",
            "confidence": 0,
            "startle_score": 0,
            "fear_tension_score": 0,
            "movement_score": 0,
            "arousal_score": 0,
            "features": {},
            "reasons": ["RR interval を集めています。"],
            "history": [],
        }

    def score_detection(self, now, bpm, rr_values, rmssd_value, sdnn_value, pnn50_value, contact_detected):
        if contact_detected is False:
            self.reaction_tracking = None
            return {
                "primary": "接触不安定",
                "tone": "warn",
                "confidence": 20,
                "startle_score": 0,
                "fear_tension_score": 0,
                "movement_score": 0,
                "arousal_score": 0,
                "features": {},
                "reasons": ["ベルト接触が弱いため判定を保留しています。"],
                "history": list(self.detection_history),
            }

        if rmssd_value is not None or sdnn_value is not None or pnn50_value is not None:
            if not self.hrv_history or abs(self.hrv_history[-1]["t"] - now) > 0.05:
                self.hrv_history.append({
                    "t": now,
                    "rmssd": rmssd_value,
                    "sdnn": sdnn_value,
                    "pnn50": pnn50_value,
                })

        recent_hr = [p for p in self.hr_history if p["t"] >= now - 20]
        prev_hr = [p for p in self.hr_history if now - 15 <= p["t"] < now - 5]
        recent_rr = [p for p in self.rr_history if p["t"] >= now - 20]
        prev_rr = [p for p in self.rr_history if now - 15 <= p["t"] < now - 5]
        recent60_hr = [p for p in self.hr_history if p["t"] >= now - 60]
        recent180_hr = [p for p in self.hr_history if p["t"] >= now - 180]
        prior5_hr = [p for p in self.hr_history if now - 330 <= p["t"] < now - 30]
        recent60_rr = [p for p in self.rr_history if p["t"] >= now - 60]
        prior5_rr = [p for p in self.rr_history if now - 330 <= p["t"] < now - 30]
        recent60_hrv = [p for p in self.hrv_history if p["t"] >= now - 60]
        recent180_hrv = [p for p in self.hrv_history if p["t"] >= now - 180]
        prior5_hrv = [p for p in self.hrv_history if now - 330 <= p["t"] < now - 30]

        if len(recent_hr) < 8 or len(recent_rr) < 8 or bpm is None:
            return self.empty_detection()

        latest_rr_mean = mean_or_none(rr_values)
        prev_bpm_mean = mean_or_none([p["v"] for p in prev_hr])
        recent10_bpm_mean = mean_or_none([p["v"] for p in recent_hr if p["t"] >= now - 10])
        recent20_bpm_mean = mean_or_none([p["v"] for p in recent_hr])
        recent60_bpm_mean = mean_or_none([p["v"] for p in recent60_hr])
        recent180_bpm_mean = mean_or_none([p["v"] for p in recent180_hr])
        prior5_bpm_mean = mean_or_none([p["v"] for p in prior5_hr]) or PERSONAL_BASELINE["bpm"]
        prev_rr_mean = mean_or_none([p["v"] for p in prev_rr])
        recent10_rr_mean = mean_or_none([p["v"] for p in recent_rr if p["t"] >= now - 10])
        recent60_rr_mean = mean_or_none([p["v"] for p in recent60_rr])
        prior5_rr_mean = mean_or_none([p["v"] for p in prior5_rr]) or PERSONAL_BASELINE["rr_ms"]
        peak_bpm_10s = max([p["v"] for p in recent_hr if p["t"] >= now - 10], default=bpm)
        prior_rmssd_mean = mean_or_none([p["rmssd"] for p in prior5_hrv]) or PERSONAL_BASELINE["rmssd_ms"]
        prior_pnn50_mean = mean_or_none([p["pnn50"] for p in prior5_hrv]) or PERSONAL_BASELINE["pnn50_percent"]
        recent60_rmssd_mean = mean_or_none([p["rmssd"] for p in recent60_hrv])
        recent60_pnn50_mean = mean_or_none([p["pnn50"] for p in recent60_hrv])
        recent180_rmssd_mean = mean_or_none([p["rmssd"] for p in recent180_hrv])
        recent180_pnn50_mean = mean_or_none([p["pnn50"] for p in recent180_hrv])

        delta_bpm_10s = bpm - prev_bpm_mean if prev_bpm_mean is not None else 0
        delta_rr_ms_10s = prev_rr_mean - latest_rr_mean if prev_rr_mean is not None and latest_rr_mean is not None else 0
        sustained_high_count = sum(1 for p in recent_hr if p["v"] >= PERSONAL_BASELINE["bpm"] + 5)
        sustained_high_seconds = min(20, sustained_high_count)

        rmssd_drop = PERSONAL_BASELINE["rmssd_ms"] - rmssd_value if rmssd_value is not None else 0
        sdnn_drop = PERSONAL_BASELINE["sdnn_ms"] - sdnn_value if sdnn_value is not None else 0
        pnn50_drop = PERSONAL_BASELINE["pnn50_percent"] - pnn50_value if pnn50_value is not None else 0
        rr_shortening = PERSONAL_BASELINE["rr_ms"] - latest_rr_mean if latest_rr_mean is not None else 0

        acute_rr = clamp((delta_rr_ms_10s - 55) / 90)
        acute_hr = clamp((delta_bpm_10s - 6) / 8)
        peak_hr = clamp((peak_bpm_10s - PERSONAL_BASELINE["bpm"] - 7) / 12)
        acute_pair_bonus = 18 if acute_rr > 0.45 and (acute_hr > 0.3 or peak_hr > 0.45) else 0

        startle_score = (
            30 * acute_rr +
            24 * acute_hr +
            16 * peak_hr +
            12 * clamp((rr_shortening - 50) / 105) +
            8 * clamp((rmssd_drop - 6) / 16) +
            acute_pair_bonus
        )

        rr_shock_score = 0
        if peak_bpm_10s >= 86 and delta_rr_ms_10s >= 75:
            rr_shock_score = (
                45 * clamp((delta_rr_ms_10s - 75) / 95) +
                20 * clamp((peak_bpm_10s - (prev_bpm_mean or PERSONAL_BASELINE["bpm"]) - 2) / 8) +
                10 * clamp((rr_shortening - 70) / 110)
            )
        startle_score = max(startle_score, rr_shock_score)

        arousal_score = (
            42 * clamp((rmssd_drop - 5) / 18) +
            30 * clamp((pnn50_drop - 3) / 8) +
            20 * clamp((sdnn_drop - 8) / 28) +
            8 * clamp((bpm - PERSONAL_BASELINE["bpm"]) / 12)
        )
        local_hr_lift = (recent60_bpm_mean - prior5_bpm_mean) if recent60_bpm_mean is not None else 0
        local_rr_shortening = (prior5_rr_mean - recent60_rr_mean) if recent60_rr_mean is not None else 0
        local_rmssd_drop = (prior_rmssd_mean - recent60_rmssd_mean) if recent60_rmssd_mean is not None else 0
        local_pnn50_drop = (prior_pnn50_mean - recent60_pnn50_mean) if recent60_pnn50_mean is not None else 0
        longer_hr_lift = (recent180_bpm_mean - prior5_bpm_mean) if recent180_bpm_mean is not None else 0
        longer_rmssd_drop = (prior_rmssd_mean - recent180_rmssd_mean) if recent180_rmssd_mean is not None else 0
        longer_pnn50_drop = (prior_pnn50_mean - recent180_pnn50_mean) if recent180_pnn50_mean is not None else 0
        recent_startle_density = max([p["startle"] for p in self.detection_history if p["t"] >= now - 120], default=0)

        fear_tension_score = (
            45 * clamp((local_hr_lift - 2) / 7) +
            30 * clamp((local_rr_shortening - 18) / 55) +
            12 * clamp((local_rmssd_drop - 3) / 14) +
            8 * clamp((local_pnn50_drop - 0.8) / 5) +
            12 * clamp((longer_hr_lift - 2) / 6) +
            6 * clamp((recent_startle_density - 55) / 35)
        )

        recent10_rr_shortening = PERSONAL_BASELINE["rr_ms"] - recent10_rr_mean if recent10_rr_mean is not None else 0
        movement_score = (
            42 * clamp((sustained_high_seconds - 8) / 10) +
            26 * clamp((recent20_bpm_mean - PERSONAL_BASELINE["bpm"] - 4) / 9) +
            18 * clamp((recent10_rr_shortening - 45) / 100) +
            14 * clamp((rmssd_drop - 5) / 18)
        )

        # A sustained body-load pattern should reduce "startle" confidence even if it has a sharp onset.
        if movement_score >= 60 and sustained_high_seconds >= 12:
            startle_score *= 0.68
        if acute_rr < 0.35 or (acute_hr < 0.2 and peak_hr < 0.35):
            startle_score = min(startle_score, 52 if rr_shock_score < 62 else rr_shock_score)

        startle_score = int(round(clamp(startle_score, 0, 100)))
        fear_tension_score = int(round(clamp(fear_tension_score, 0, 100)))
        movement_score = int(round(clamp(movement_score, 0, 100)))
        arousal_score = int(round(clamp(arousal_score, 0, 100)))

        reasons = []
        if delta_rr_ms_10s > 35:
            reasons.append(f"RRが直前比で約{round(delta_rr_ms_10s)}ms短縮")
        if delta_bpm_10s > 3:
            reasons.append(f"心拍が直前比で約{round(delta_bpm_10s, 1)}bpm上昇")
        if sustained_high_seconds >= 10:
            reasons.append(f"心拍高めが約{sustained_high_seconds}秒持続")
        if rmssd_drop > 8:
            reasons.append(f"RMSSDが基準より約{round(rmssd_drop, 1)}ms低下")
        if pnn50_drop > 4:
            reasons.append(f"pNN50が基準より約{round(pnn50_drop, 1)}pt低下")
        if local_hr_lift > 3:
            reasons.append(f"直近5分比で心拍が約{round(local_hr_lift, 1)}bpm上昇")
        if local_rmssd_drop > 5:
            reasons.append(f"直近5分比でRMSSDが約{round(local_rmssd_drop, 1)}ms低下")
        if not reasons:
            reasons.append("大きな急変はありません。")

        if startle_score >= 78:
            raw_primary = "びっくり候補"
            raw_tone = "hot"
            raw_confidence = startle_score
        elif fear_tension_score >= 55:
            raw_primary = "警戒/緊張"
            raw_tone = "warm"
            raw_confidence = fear_tension_score
        elif movement_score >= 65 and movement_score >= startle_score - 5:
            raw_primary = "姿勢/体動疑い"
            raw_tone = "warn"
            raw_confidence = movement_score
        elif startle_score >= 68:
            raw_primary = "びっくり候補"
            raw_tone = "hot"
            raw_confidence = startle_score
        elif arousal_score >= 68:
            raw_primary = "覚醒/ワクワク"
            raw_tone = "steady"
            raw_confidence = arousal_score
        elif fear_tension_score >= 35 or startle_score >= 35:
            raw_primary = "軽い反応"
            raw_tone = "steady"
            raw_confidence = max(fear_tension_score, startle_score)
        else:
            raw_primary = "落ち着き"
            raw_tone = "calm"
            raw_confidence = 100 - max(startle_score, fear_tension_score, movement_score, arousal_score)

        primary = raw_primary
        tone = raw_tone
        confidence = raw_confidence
        tracking_remaining = 0
        display_startle_score = startle_score
        display_fear_tension_score = fear_tension_score
        display_movement_score = movement_score

        if self.reaction_tracking:
            tracking = self.reaction_tracking
            tracking["peak_startle"] = max(tracking["peak_startle"], startle_score)
            tracking["peak_movement"] = max(tracking["peak_movement"], movement_score)
            tracking["peak_fear"] = max(tracking["peak_fear"], fear_tension_score)
            tracking["max_sustained_high"] = max(tracking["max_sustained_high"], sustained_high_seconds)
            tracking["last_startle"] = startle_score
            tracking["last_movement"] = movement_score
            elapsed = now - tracking["started_at"]
            tracking_remaining = max(0, REACTION_TRACK_SECONDS - elapsed)
            if elapsed < REACTION_TRACK_SECONDS:
                primary = "反応追跡中"
                tone = "steady"
                confidence = max(tracking["peak_startle"], tracking["peak_movement"], tracking["peak_fear"])
                display_startle_score = tracking["peak_startle"]
                display_fear_tension_score = tracking["peak_fear"]
                display_movement_score = tracking["peak_movement"]
                reasons = [f"びっくり/姿勢変化をあと{math.ceil(tracking_remaining)}秒追跡中"] + reasons[:3]
            else:
                posture_like = (
                    tracking["peak_movement"] >= 65 and tracking["peak_movement"] >= tracking["peak_startle"] - 8
                ) or (
                    tracking["max_sustained_high"] >= 10 and movement_score >= 55
                )
                if tracking["peak_startle"] >= 78:
                    primary = "びっくり候補"
                    tone = "hot"
                    confidence = tracking["peak_startle"]
                    display_startle_score = tracking["peak_startle"]
                    display_fear_tension_score = tracking["peak_fear"]
                    display_movement_score = tracking["peak_movement"]
                    reasons = [f"{REACTION_TRACK_SECONDS}秒追跡後、急反応が体動より強い"] + reasons[:3]
                elif posture_like:
                    primary = "姿勢/体動疑い"
                    tone = "warn"
                    confidence = max(tracking["peak_movement"], movement_score)
                    display_startle_score = tracking["peak_startle"]
                    display_fear_tension_score = tracking["peak_fear"]
                    display_movement_score = max(tracking["peak_movement"], movement_score)
                    reasons = [f"{REACTION_TRACK_SECONDS}秒追跡後、心拍高め/体動寄りの持続を検出"] + reasons[:3]
                elif tracking["peak_startle"] >= 68:
                    primary = "びっくり候補"
                    tone = "hot"
                    confidence = tracking["peak_startle"]
                    display_startle_score = tracking["peak_startle"]
                    display_fear_tension_score = tracking["peak_fear"]
                    display_movement_score = tracking["peak_movement"]
                    reasons = [f"{REACTION_TRACK_SECONDS}秒追跡後、RR急短縮と心拍上昇が一過性に強い"] + reasons[:3]
                else:
                    primary = raw_primary
                    tone = raw_tone
                    confidence = raw_confidence
                self.reaction_tracking = None
                self.reaction_cooldown_until = now + 4
        elif raw_primary == "びっくり候補" and now >= self.reaction_cooldown_until:
            self.reaction_tracking = {
                "started_at": now,
                "peak_startle": startle_score,
                "peak_movement": movement_score,
                "peak_fear": fear_tension_score,
                "max_sustained_high": sustained_high_seconds,
                "last_startle": startle_score,
                "last_movement": movement_score,
            }
            tracking_remaining = REACTION_TRACK_SECONDS
            primary = "反応追跡中"
            tone = "steady"
            confidence = max(startle_score, movement_score, fear_tension_score)
            display_startle_score = startle_score
            display_fear_tension_score = fear_tension_score
            display_movement_score = movement_score
            reasons = [f"びっくり/姿勢変化をあと{REACTION_TRACK_SECONDS}秒追跡中"] + reasons[:3]

        item = {
            "t": now,
            "primary": primary,
            "startle": display_startle_score,
            "fear": display_fear_tension_score,
            "movement": display_movement_score,
        }
        self.detection_history.append(item)

        return {
            "primary": primary,
            "tone": tone,
            "confidence": int(round(confidence)),
            "startle_score": display_startle_score,
            "fear_tension_score": display_fear_tension_score,
            "movement_score": display_movement_score,
            "arousal_score": arousal_score,
            "features": {
                "delta_bpm_10s": rounded(delta_bpm_10s, 2),
                "delta_rr_ms_10s": rounded(delta_rr_ms_10s, 2),
                "latest_rr_mean": rounded(latest_rr_mean, 2),
                "recent10_bpm_mean": rounded(recent10_bpm_mean, 2),
                "recent20_bpm_mean": rounded(recent20_bpm_mean, 2),
                "peak_bpm_10s": rounded(peak_bpm_10s, 2),
                "sustained_high_seconds": sustained_high_seconds,
                "tracking_remaining_seconds": rounded(tracking_remaining, 1),
                "acute_rr": rounded(acute_rr, 2),
                "acute_hr": rounded(acute_hr, 2),
                "rr_shock_score": rounded(rr_shock_score, 2),
                "arousal_score": arousal_score,
                "local_hr_lift_60s_vs_5m": rounded(local_hr_lift, 2),
                "local_rr_shortening_60s_vs_5m": rounded(local_rr_shortening, 2),
                "local_rmssd_drop_60s_vs_5m": rounded(local_rmssd_drop, 2),
                "local_pnn50_drop_60s_vs_5m": rounded(local_pnn50_drop, 2),
                "longer_hr_lift_180s_vs_5m": rounded(longer_hr_lift, 2),
                "longer_rmssd_drop_180s_vs_5m": rounded(longer_rmssd_drop, 2),
                "longer_pnn50_drop_180s_vs_5m": rounded(longer_pnn50_drop, 2),
                "rmssd_drop_from_baseline": rounded(rmssd_drop, 2),
                "sdnn_drop_from_baseline": rounded(sdnn_drop, 2),
                "pnn50_drop_from_baseline": rounded(pnn50_drop, 2),
            },
            "reasons": reasons[:4],
            "history": list(self.detection_history),
        }

    def recording_snapshot(self):
        if not self.recording:
            return {
                "active": False,
                "name": None,
                "elapsed_seconds": 0,
                "remaining_seconds": None,
                "samples": 0,
                "saved": self.last_saved_recording,
            }
        now = time.time()
        elapsed = max(0, now - self.recording["started_at"])
        return {
            "active": True,
            "name": self.recording["name"],
            "elapsed_seconds": round(elapsed, 1),
            "remaining_seconds": None,
            "samples": len(self.recording["samples"]),
            "saved": None,
        }

    def sanitize_name(self, name):
        cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", (name or "").strip())
        cleaned = re.sub(r"\s+", "_", cleaned).strip("._-")
        return cleaned[:80] or "h6_recording"

    async def start_recording(self, name):
        if self.recording:
            raise web.HTTPConflict(text="recording already active")
        now = time.time()
        self.recording = {
            "name": name.strip() or "H6 recording",
            "safe_name": self.sanitize_name(name),
            "started_at": now,
            "started_iso": datetime.now().isoformat(timespec="seconds"),
            "samples": [],
        }
        self.latest["recording"] = self.recording_snapshot()
        await self.broadcast()
        return self.latest["recording"]

    async def stop_recording(self, reason="manual"):
        if not self.recording:
            return {"active": False, "saved": None}
        recording = self.recording
        self.recording = None
        saved = self.save_recording(recording, reason)
        self.last_saved_recording = saved
        self.latest["recording"] = {
            "active": False,
            "name": None,
            "elapsed_seconds": 0,
            "remaining_seconds": None,
            "samples": 0,
            "saved": saved,
        }
        await self.broadcast()
        return self.latest["recording"]

    def save_recording(self, recording, reason):
        RECORDINGS_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{stamp}_{recording['safe_name']}"
        json_path = RECORDINGS_DIR / f"{base}.json"
        csv_path = RECORDINGS_DIR / f"{base}.csv"

        ended_iso = datetime.now().isoformat(timespec="seconds")
        duration_seconds = round(time.time() - recording["started_at"], 3)
        payload = {
            "name": recording["name"],
            "started_at": recording["started_iso"],
            "ended_at": ended_iso,
            "duration_seconds": duration_seconds,
            "stop_reason": reason,
            "device": self.latest["device"],
            "samples": recording["samples"],
        }
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "iso_time",
                    "elapsed_seconds",
                    "bpm",
                    "rr_ms",
                    "rmssd_ms",
                    "sdnn_ms",
                    "pnn50_percent",
                    "contact_detected",
                    "battery_percent",
                    "raw_hex",
                    "detection_primary",
                    "startle_score",
                    "fear_tension_score",
                    "movement_score",
                    "arousal_score",
                ],
            )
            writer.writeheader()
            for sample in recording["samples"]:
                rr_values = sample.get("rr_ms") or []
                writer.writerow({
                    "iso_time": sample.get("iso_time"),
                    "elapsed_seconds": sample.get("elapsed_seconds"),
                    "bpm": sample.get("bpm"),
                    "rr_ms": " ".join(str(v) for v in rr_values),
                    "rmssd_ms": sample.get("rmssd_ms"),
                    "sdnn_ms": sample.get("sdnn_ms"),
                    "pnn50_percent": sample.get("pnn50_percent"),
                    "contact_detected": sample.get("contact_detected"),
                    "battery_percent": sample.get("battery_percent"),
                    "raw_hex": sample.get("raw_hex"),
                    "detection_primary": sample.get("detection_primary"),
                    "startle_score": sample.get("startle_score"),
                    "fear_tension_score": sample.get("fear_tension_score"),
                    "movement_score": sample.get("movement_score"),
                    "arousal_score": sample.get("arousal_score"),
                })

        return {
            "json": str(json_path),
            "csv": str(csv_path),
            "sample_count": len(recording["samples"]),
            "duration_seconds": duration_seconds,
            "ended_at": ended_iso,
            "reason": reason,
        }

    async def broadcast(self):
        self.latest["recording"] = self.recording_snapshot()
        payload = json.dumps(self.snapshot_payload(), ensure_ascii=False)
        stale = []
        for ws in self.websockets:
            try:
                await ws.send_str(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.websockets.discard(ws)

    async def set_status(self, status, message):
        self.latest["status"] = status
        self.latest["message"] = message
        await self.broadcast()

    def _push_measurement(self, decoded):
        now = time.time()
        bpm = decoded.get("bpm")
        rr_values = decoded.get("rr_ms") or []
        contact_detected = decoded.get("contact_detected")

        if bpm is not None:
            self.hr_history.append({"t": now, "v": bpm})
        for rr in rr_values:
            self.rr_window.append(rr)
            self.rr_history.append({"t": now, "v": rr})

        rr_list = list(self.rr_window)
        rmssd_value = rmssd(rr_list)
        sdnn_value = sdnn(rr_list)
        pnn50_value = pnn50(rr_list)

        self.latest["status"] = "live"
        self.latest["message"] = "計測中"
        self.latest["measurement"].update({
            "bpm": bpm,
            "rr_ms": [round(v, 3) for v in rr_values],
            "contact_supported": decoded.get("contact_supported"),
            "contact_detected": contact_detected,
            "last_raw_hex": decoded.get("raw_hex"),
            "last_seen": datetime.now().isoformat(timespec="seconds"),
        })
        self.latest["hrv"] = {
            "rmssd_ms": rounded(rmssd_value, 1),
            "sdnn_ms": rounded(sdnn_value, 1),
            "pnn50_percent": rounded(pnn50_value, 1),
            "rr_count": len(rr_list),
        }
        self.latest["state"] = infer_state(bpm, rmssd_value, contact_detected, len(rr_list))
        self.latest["detection"] = self.score_detection(
            now,
            bpm,
            rr_values,
            rmssd_value,
            sdnn_value,
            pnn50_value,
            contact_detected,
        )
        self.issue_startle_command_if_needed(now, self.latest["detection"], bpm)
        self.latest["history"] = {
            "hr": list(self.hr_history),
            "rr": list(self.rr_history),
        }

        if self.recording:
            self.recording["samples"].append({
                "iso_time": datetime.now().isoformat(timespec="milliseconds"),
                "elapsed_seconds": round(now - self.recording["started_at"], 3),
                "bpm": bpm,
                "rr_ms": [round(v, 3) for v in rr_values],
                "rmssd_ms": self.latest["hrv"]["rmssd_ms"],
                "sdnn_ms": self.latest["hrv"]["sdnn_ms"],
                "pnn50_percent": self.latest["hrv"]["pnn50_percent"],
                "contact_detected": contact_detected,
                "battery_percent": self.latest["measurement"]["battery_percent"],
                "raw_hex": decoded.get("raw_hex"),
                "detection_primary": self.latest["detection"]["primary"],
                "startle_score": self.latest["detection"]["startle_score"],
                "fear_tension_score": self.latest["detection"]["fear_tension_score"],
                "movement_score": self.latest["detection"]["movement_score"],
                "arousal_score": self.latest["detection"].get("arousal_score"),
            })

    def issue_startle_command_if_needed(self, now, detection, bpm):
        if not self.command_bus:
            return
        if detection.get("primary") != "びっくり候補":
            return
        if now - self.last_startle_command_at < 8:
            return
        self.last_startle_command_at = now
        self.command_bus.issue("startle", "h6-heart-detector", {
            "bpm": bpm,
            "confidence": detection.get("confidence"),
            "startle_score": detection.get("startle_score"),
            "fear_tension_score": detection.get("fear_tension_score"),
            "movement_score": detection.get("movement_score"),
            "features": detection.get("features", {}),
            "reasons": detection.get("reasons", []),
        }, ttl=3.5)

    async def handle_hr(self, _sender, data):
        decoded = decode_hr_measurement(data)
        self._push_measurement(decoded)
        await self.broadcast()

    async def handle_battery(self, _sender, data):
        value = bytes(data)[0] if data else None
        self.latest["measurement"]["battery_percent"] = value
        await self.broadcast()

    async def read_static_info(self, client, device):
        self.latest["device"].update({
            "name": device.name,
            "address": device.address,
            "mtu": getattr(client, "mtu_size", None),
        })
        for key, uuid in DEVICE_INFO.items():
            try:
                value = await client.read_gatt_char(uuid)
                self.latest["device"]["info"][key] = bytes(value).decode("ascii", errors="replace")
            except Exception:
                pass
        try:
            value = await client.read_gatt_char(BATTERY_LEVEL)
            self.latest["measurement"]["battery_percent"] = bytes(value)[0]
        except Exception:
            pass
        try:
            location = await client.read_gatt_char(BODY_SENSOR_LOCATION)
            locations = ["Other", "Chest", "Wrist", "Finger", "Hand", "Ear Lobe", "Foot"]
            code = bytes(location)[0]
            self.latest["device"]["info"]["body_sensor_location"] = locations[code] if code < len(locations) else str(code)
        except Exception:
            pass

    async def find_device(self):
        await self.set_status("scanning", "H6M を探しています")
        devices = await BleakScanner.discover(timeout=8, return_adv=True)
        fallback = None
        for key, (device, adv) in devices.items():
            address_flat = key.replace(":", "").upper()
            service_uuids = [s.lower() for s in (adv.service_uuids or [])]
            name = device.name or ""
            if TARGET_ADDRESS_FLAT and address_flat == TARGET_ADDRESS_FLAT:
                self.latest["device"]["rssi"] = adv.rssi
                return device
            if name.upper().startswith(TARGET_NAME_PREFIX) and HR_SERVICE in service_uuids:
                fallback = device
                self.latest["device"]["rssi"] = adv.rssi
        return fallback

    async def run(self):
        while True:
            client = None
            try:
                device = await self.find_device()
                if not device:
                    await self.set_status("waiting", "H6M が見つかりません。ベルトを装着して近づけてください。")
                    await asyncio.sleep(5)
                    continue

                await self.set_status("connecting", f"{device.name or device.address} に接続しています")
                client = BleakClient(device, timeout=20)
                await client.connect()
                await self.read_static_info(client, device)
                await self.set_status("connected", "通知を購読しています")

                loop = asyncio.get_running_loop()
                await client.start_notify(HR_MEASUREMENT, lambda s, d: loop.create_task(self.handle_hr(s, d)))
                try:
                    await client.start_notify(BATTERY_LEVEL, lambda s, d: loop.create_task(self.handle_battery(s, d)))
                except Exception:
                    pass

                await self.set_status("live", "計測中")
                while client.is_connected:
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.set_status("error", f"接続エラー: {exc}")
                await asyncio.sleep(4)
            finally:
                if client and client.is_connected:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass


command_bus = CommandBus(RE9_COMMAND_LOG)
command_sender = ESP32CommandSender(command_bus, ESP32_COMMAND_URL)
game_monitor = GameMonitor(command_bus)
monitor = H6Monitor(command_bus=command_bus, game_monitor=game_monitor, command_sender=command_sender)
game_monitor.on_change = monitor.broadcast


async def index(_request):
    return web.FileResponse(STATIC_DIR / "index.html")


async def snapshot(_request):
    return web.json_response(monitor.snapshot_payload())


async def game_status(_request):
    return web.json_response(game_monitor.snapshot())


async def commands(_request):
    return web.json_response(command_bus.snapshot())


async def esp32_status(_request):
    return web.json_response(command_sender.snapshot())


async def debug_command(request):
    kind = request.match_info.get("kind", "debug")
    debug_kinds = {"none", "faltering", "startle", "damage", "death"}
    if kind not in debug_kinds:
        return web.json_response({"ok": False, "error": "unknown command kind"}, status=400)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    event = command_bus.issue(kind, "debug-api", body, ttl=COMMAND_DEFAULT_TTL.get(kind))
    await monitor.broadcast()
    return web.json_response({
        "ok": True,
        "event": event,
        "active": command_bus.snapshot().get("active"),
        "esp32": command_sender.snapshot(),
    })


async def recording_start(request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    name = str(body.get("name") or "").strip()
    result = await monitor.start_recording(name)
    return web.json_response(result)


async def recording_stop(_request):
    result = await monitor.stop_recording("manual")
    return web.json_response(result)


async def recording_status(_request):
    return web.json_response(monitor.recording_snapshot())


async def websocket(request):
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    monitor.websockets.add(ws)
    await ws.send_str(json.dumps(monitor.snapshot_payload(), ensure_ascii=False))
    try:
        async for _ in ws:
            pass
    finally:
        monitor.websockets.discard(ws)
    return ws


async def on_startup(app):
    app["monitor_task"] = asyncio.create_task(monitor.run())
    app["game_monitor_task"] = asyncio.create_task(game_monitor.run())
    app["esp32_sender_task"] = asyncio.create_task(command_sender.run())


async def on_cleanup(app):
    for task_name in ("monitor_task", "game_monitor_task", "esp32_sender_task"):
        task = app.get(task_name)
        if not task:
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/snapshot", snapshot)
    app.router.add_get("/api/game", game_status)
    app.router.add_get("/api/commands", commands)
    app.router.add_get("/api/esp32", esp32_status)
    app.router.add_post("/api/debug/command/{kind}", debug_command)
    app.router.add_post("/api/recording/start", recording_start)
    app.router.add_post("/api/recording/stop", recording_stop)
    app.router.add_get("/api/recording/status", recording_status)
    app.router.add_get("/ws", websocket)
    app.router.add_static("/static", STATIC_DIR)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def open_browser_later(host, port):
    time.sleep(1.5)
    webbrowser.open(f"http://{host}:{port}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RE:AL SHOCK MOD local dashboard")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()

    if args.open_browser:
        threading.Thread(target=open_browser_later, args=(args.host, args.port), daemon=True).start()
    web.run_app(create_app(), host=args.host, port=args.port)
