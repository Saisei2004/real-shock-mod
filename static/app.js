const $ = (id) => document.getElementById(id);

const fields = {
  deviceName: $("deviceName"),
  connDot: $("connDot"),
  connText: $("connText"),
  bpm: $("bpm"),
  state: $("state"),
  stateDetail: $("stateDetail"),
  rmssd: $("rmssd"),
  sdnn: $("sdnn"),
  pnn50: $("pnn50"),
  battery: $("battery"),
  lastSeen: $("lastSeen"),
  rrLatest: $("rrLatest"),
  contact: $("contact"),
  model: $("model"),
  firmware: $("firmware"),
  address: $("address"),
  samples: $("samples"),
  raw: $("raw"),
  recordingName: $("recordingName"),
  startRecording: $("startRecording"),
  stopRecording: $("stopRecording"),
  recordingStatus: $("recordingStatus"),
  recordingProgress: $("recordingProgress"),
  recordingSaved: $("recordingSaved"),
  detectPrimary: $("detectPrimary"),
  detectReasons: $("detectReasons"),
  startleScore: $("startleScore"),
  fearScore: $("fearScore"),
  movementScore: $("movementScore"),
  startleBar: $("startleBar"),
  fearBar: $("fearBar"),
  movementBar: $("movementBar"),
  mainBioBpm: $("mainBioBpm"),
  mainBioSub: $("mainBioSub"),
  mainGameHp: $("mainGameHp"),
  mainGameSub: $("mainGameSub"),
  activeCommand: $("activeCommand"),
  activeCommandDetail: $("activeCommandDetail"),
  hpFill: $("hpFill"),
  gameStatus: $("gameStatus"),
  gameHp: $("gameHp"),
  gameBridge: $("gameBridge"),
  commandLog: $("commandLog"),
  esp32Status: $("esp32Status"),
  debugDamage: $("debugDamage"),
  debugDeath: $("debugDeath"),
  debugStartle: $("debugStartle"),
  debugFaltering: $("debugFaltering"),
  debugNone: $("debugNone"),
  debugMode: $("debugMode"),
  lowOutputMode: $("lowOutputMode"),
  englishMode: $("englishMode"),
};

const hrCanvas = $("hrChart");
const rrCanvas = $("rrChart");
let currentLanguage = "ja";

const translations = {
  ja: {
    activeCommand: "ACTIVE COMMAND",
    battery: "Battery",
    booting: "起動中",
    bpm: "bpm",
    browserConnected: "ブラウザ接続済み",
    collectingRr: "RR interval を集めています。",
    commandLog: "Command Log",
    contact: "Contact",
    debugMax: "Debug max Lv3",
    detection: "Detection",
    deviceWaiting: "H6M を待機中",
    disabled: "disabled",
    englishUi: "English UI",
    falteringState: "ふらつき",
    fearMetric: "警戒/緊張",
    gameBooting: "RE9起動中 / ブリッジ更新待ち",
    gameConnectedHp: "RE9接続中 / プレイヤーHP取得中",
    gameConnectedSearch: "RE9接続中 / プレイヤー探索中",
    gameNotRunning: "RE9未起動",
    lowOutput: "低出力 Lv10",
    measuring: "計測中",
    movementMetric: "姿勢/体動",
    none: "なし",
    normalState: "通常",
    notRecording: "未録画",
    reconnecting: "再接続中",
    recordingActive: "を録画中",
    recordingNamePlaceholder: "保存名",
    saved: "保存済み",
    samples: "Samples",
    settingsFailed: "settings failed",
    start: "Start",
    startFailed: "開始できませんでした",
    startleMetric: "びっくり",
    stop: "Stop",
    stopFailed: "停止できませんでした",
    waiting: "待機中",
    waitingGame: "ゲーム監視を待機中",
    waitingRe9: "RE9監視を待機中",
  },
  en: {
    activeCommand: "ACTIVE COMMAND",
    battery: "Battery",
    booting: "Booting",
    bpm: "bpm",
    browserConnected: "Browser connected",
    collectingRr: "Collecting RR intervals.",
    commandLog: "Command Log",
    contact: "Contact",
    debugMax: "Debug max Lv3",
    detection: "Detection",
    deviceWaiting: "Waiting for H6M",
    disabled: "disabled",
    englishUi: "English UI",
    falteringState: "Faltering",
    fearMetric: "Fear/Tension",
    gameBooting: "RE9 running / waiting for bridge",
    gameConnectedHp: "RE9 connected / reading player HP",
    gameConnectedSearch: "RE9 connected / searching player",
    gameNotRunning: "RE9 not running",
    lowOutput: "Low output Lv10",
    measuring: "Measuring",
    movementMetric: "Posture/Motion",
    none: "None",
    normalState: "Normal",
    notRecording: "Not recording",
    reconnecting: "Reconnecting",
    recordingActive: "recording",
    recordingNamePlaceholder: "Recording name",
    saved: "Saved",
    samples: "Samples",
    settingsFailed: "settings failed",
    start: "Start",
    startFailed: "Could not start",
    startleMetric: "Startle",
    stop: "Stop",
    stopFailed: "Could not stop",
    waiting: "Waiting",
    waitingGame: "Waiting for game monitor",
    waitingRe9: "Waiting for RE9 monitor",
  },
};

const commandLabels = {
  ja: {
    none: "なし",
    faltering: "ふらつき",
    startle: "びっくり",
    damage: "ダメージ",
    death: "死亡",
  },
  en: {
    none: "None",
    faltering: "Faltering",
    startle: "Startle",
    damage: "Damage",
    death: "Death",
  },
};

const knownText = {
  en: {
    "なし": "None",
    "ふらつき": "Faltering",
    "びっくり": "Startle",
    "ダメージ": "Damage",
    "死亡": "Death",
    "安定": "Stable",
    "平常": "Normal",
    "計測中": "Measuring",
    "起動中": "Booting",
    "接触不安定": "Weak contact",
    "負荷高め": "High load",
    "落ち着き": "Calm",
    "やや負荷": "Slight load",
  },
};

function t(key) {
  return translations[currentLanguage]?.[key] || translations.ja[key] || key;
}

function localizeKnown(value) {
  if (value === null || value === undefined) return value;
  return knownText[currentLanguage]?.[value] || value;
}

function labelForCommand(kind, fallback) {
  return commandLabels[currentLanguage]?.[kind] || localizeKnown(fallback) || kind || t("none");
}

function applyTranslations() {
  document.documentElement.lang = currentLanguage;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
}

function fmt(value, suffix = "", digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return `--${suffix}`;
  return `${Number(value).toFixed(digits)}${suffix}`;
}

function setStatus(status, message) {
  fields.connDot.className = `dot ${status || "neutral"}`;
  fields.connText.textContent = localizeKnown(message) || status || t("waiting");
}

function setState(state) {
  const tone = state?.tone || "neutral";
  fields.state.className = `state ${tone}`;
  fields.state.textContent = localizeKnown(state?.label) || t("measuring");
  fields.stateDetail.textContent = currentLanguage === "en"
    ? t("collectingRr")
    : state?.detail || t("collectingRr");
}

function drawChart(canvas, points, options) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  ctx.fillStyle = "#050807";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(134, 240, 168, 0.16)";
  ctx.lineWidth = 1;
  for (let i = 1; i < 5; i += 1) {
    const y = (height / 5) * i;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  for (let i = 1; i < 7; i += 1) {
    const x = (width / 7) * i;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }

  if (!points || points.length < 2) {
    ctx.fillStyle = "#53605a";
    ctx.font = "14px Segoe UI, sans-serif";
    ctx.fillText("NO SIGNAL", 18, 32);
    return;
  }

  const values = points.map((p) => p.v);
  const minValue = options.min ?? Math.min(...values);
  const maxValue = options.max ?? Math.max(...values);
  const pad = Math.max(1, (maxValue - minValue) * 0.12);
  const yMin = minValue - pad;
  const yMax = maxValue + pad;
  const tMin = points[0].t;
  const tMax = points[points.length - 1].t;
  const tSpan = Math.max(1, tMax - tMin);

  ctx.strokeStyle = options.color;
  ctx.lineWidth = 2.5;
  ctx.shadowColor = options.color;
  ctx.shadowBlur = 10;
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = ((point.t - tMin) / tSpan) * (width - 44) + 22;
    const y = height - 24 - ((point.v - yMin) / (yMax - yMin)) * (height - 48);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.shadowBlur = 0;

  ctx.fillStyle = "#85918b";
  ctx.font = "12px Segoe UI, sans-serif";
  ctx.fillText(`${Math.round(yMax)}${options.unit}`, 14, 20);
  ctx.fillText(`${Math.round(yMin)}${options.unit}`, 14, height - 9);
}

function update(data) {
  const device = data.device || {};
  const info = device.info || {};
  const measurement = data.measurement || {};
  const hrv = data.hrv || {};

  setStatus(data.status, data.message);
  setState(data.state);

  fields.deviceName.textContent = device.name || t("deviceWaiting");
  fields.bpm.textContent = measurement.bpm ?? "--";
  fields.rmssd.textContent = fmt(hrv.rmssd_ms, " ms");
  fields.sdnn.textContent = fmt(hrv.sdnn_ms, " ms");
  fields.pnn50.textContent = fmt(hrv.pnn50_percent, " %");
  fields.battery.textContent = measurement.battery_percent === null || measurement.battery_percent === undefined
    ? "-- %"
    : `${measurement.battery_percent} %`;
  fields.lastSeen.textContent = measurement.last_seen || "--";
  fields.rrLatest.textContent = measurement.rr_ms?.length
    ? `${measurement.rr_ms.map((v) => Number(v).toFixed(1)).join(" / ")} ms`
    : "-- ms";
  fields.contact.textContent = measurement.contact_detected === null || measurement.contact_detected === undefined
    ? "--"
    : measurement.contact_detected ? "Detected" : "Weak";
  fields.model.textContent = info.model || "--";
  fields.firmware.textContent = info.firmware || "--";
  fields.address.textContent = device.address || device.target_address || "--";
  fields.samples.textContent = `${hrv.rr_count || 0} RR`;
  fields.raw.textContent = measurement.last_raw_hex || "--";
  updateMainBio(measurement, hrv);
  updateDetection(data.detection);
  updateRecording(data.recording);
  updateSettings(data.settings);
  updateGame(data.game, data.commands, data.esp32);

  drawChart(hrCanvas, data.history?.hr || [], { color: "#86f0a8", unit: " bpm" });
  drawChart(rrCanvas, data.history?.rr || [], { color: "#7aa9d6", unit: " ms" });
}

function updateSettings(settings) {
  const language = settings?.ui_language === "en" ? "en" : "ja";
  if (language !== currentLanguage) {
    currentLanguage = language;
    applyTranslations();
  }
  if (fields.englishMode) {
    const enabled = language === "en";
    if (fields.englishMode.checked !== enabled) {
      fields.englishMode.checked = enabled;
    }
  }
  if (fields.debugMode) {
    const enabled = Boolean(settings?.debug_mode);
    if (fields.debugMode.checked !== enabled) {
      fields.debugMode.checked = enabled;
    }
  }
  if (fields.lowOutputMode) {
    const enabled = Boolean(settings?.low_output_mode);
    if (fields.lowOutputMode.checked !== enabled) {
      fields.lowOutputMode.checked = enabled;
    }
  }
}

function updateMainBio(measurement, hrv) {
  fields.mainBioBpm.textContent = measurement.bpm === null || measurement.bpm === undefined
    ? "-- bpm"
    : `${measurement.bpm} bpm`;
  const rr = measurement.rr_ms?.length ? `${Number(measurement.rr_ms[0]).toFixed(0)}ms` : "--";
  fields.mainBioSub.textContent = `RMSSD ${fmt(hrv.rmssd_ms, "ms", 0)} / RR ${rr}`;
}

function scoreText(value) {
  const score = Math.max(0, Math.min(100, Number(value || 0)));
  return `${Math.round(score)}%`;
}

function updateDetection(detection) {
  const tone = detection?.tone || "neutral";
  fields.detectPrimary.className = tone;
  const confidence = detection?.confidence ?? 0;
  fields.detectPrimary.textContent = detection?.primary
    ? `${localizeKnown(detection.primary)} ${scoreText(confidence)}`
    : t("measuring");
  fields.detectReasons.textContent = currentLanguage === "en"
    ? t("collectingRr")
    : detection?.reasons?.length
    ? detection.reasons.join(" / ")
    : t("collectingRr");

  const startle = detection?.startle_score || 0;
  const fear = detection?.fear_tension_score || 0;
  const movement = detection?.movement_score || 0;
  fields.startleScore.textContent = scoreText(startle);
  fields.fearScore.textContent = scoreText(fear);
  fields.movementScore.textContent = scoreText(movement);
  fields.startleBar.style.width = `${Math.max(0, Math.min(100, startle))}%`;
  fields.fearBar.style.width = `${Math.max(0, Math.min(100, fear))}%`;
  fields.movementBar.style.width = `${Math.max(0, Math.min(100, movement))}%`;
}

function updateRecording(recording) {
  const active = Boolean(recording?.active);
  fields.recordingName.disabled = active;
  fields.startRecording.disabled = active;
  fields.stopRecording.disabled = !active;

  if (active) {
    const elapsed = Number(recording.elapsed_seconds || 0);
    fields.recordingProgress.style.width = "100%";
    fields.recordingStatus.textContent = currentLanguage === "en"
      ? `${recording.name} ${t("recordingActive")} / ${Math.floor(elapsed)}s / ${recording.samples || 0} samples`
      : `${recording.name} ${t("recordingActive")} / ${Math.floor(elapsed)} 秒 / ${recording.samples || 0} samples`;
    fields.recordingSaved.textContent = "";
    return;
  }

  fields.recordingProgress.style.width = "0%";
  fields.recordingStatus.textContent = t("notRecording");
  if (recording?.saved) {
    fields.recordingSaved.textContent = `${t("saved")}: ${recording.saved.csv} / ${recording.saved.sample_count} samples`;
  }
}

function updateGame(game, commands, esp32) {
  const status = game || {};
  const gameInfo = status.game || {};
  const bridge = status.bridge || {};
  const player = status.player || {};
  const active = commands?.active || { kind: "none", label: t("none"), source: "--", payload: {} };
  const running = Boolean(gameInfo.running);
  const fresh = Boolean(bridge.fresh);

  if (running && fresh && player.found) {
    fields.gameStatus.textContent = t("gameConnectedHp");
  } else if (running && fresh) {
    fields.gameStatus.textContent = t("gameConnectedSearch");
  } else if (running) {
    fields.gameStatus.textContent = t("gameBooting");
  } else {
    fields.gameStatus.textContent = t("gameNotRunning");
  }

  const hp = player.hp;
  const maxHp = player.max_hp;
  const hpPercent = player.hp_percent;
  fields.gameHp.textContent = hp === null || hp === undefined
    ? "--"
    : `${fmt(hp, "", 0)} / ${fmt(maxHp, "", 0)} (${fmt(hpPercent, "%", 0)})`;
  fields.mainGameHp.textContent = hp === null || hp === undefined
    ? "HP --"
    : `HP ${fmt(hpPercent, "%", 0)}`;
  fields.hpFill.style.width = hpPercent === null || hpPercent === undefined
    ? "0%"
    : `${Math.max(0, Math.min(100, Number(hpPercent)))}%`;
  const faltering = player.faltering_low_hp ? t("falteringState") : t("normalState");
  fields.mainGameSub.textContent = `${fields.gameStatus.textContent} / ${faltering}`;
  fields.gameBridge.textContent = bridge.fresh
    ? `fresh ${fmt(bridge.age_seconds, "s", 1)}`
    : bridge.present ? `stale ${fmt(bridge.age_seconds, "s", 1)}` : "not found";

  const recent = commands?.recent || [];
  fields.activeCommand.className = active.kind || "none";
  fields.activeCommand.textContent = labelForCommand(active.kind, active.label);
  const output = esp32?.last_sent?.output;
  const outputText = output
    ? ` / Lv${output.intensity} ${fmt((output.duration_ms || 0) / 1000, "s", 1)}`
    : "";
  fields.activeCommandDetail.textContent = `${active.kind || "none"} / ${active.source || "--"}${outputText}`;
  document.body.classList.remove("command-none", "command-faltering", "command-startle", "command-damage", "command-death");
  document.body.classList.add(`command-${active.kind || "none"}`);
  fields.commandLog.textContent = recent.length
    ? recent.slice(0, 3).map((event) => `${labelForCommand(event.kind, event.label)}@${event.source}`).join(" / ")
    : "--";
  if (esp32?.enabled) {
    const last = esp32.last_sent?.kind ? ` / ${esp32.last_sent.kind}` : "";
    const transport = esp32.transport ? `${esp32.transport}:` : "";
    const serial = esp32.serial_port ? ` ${esp32.serial_port}` : "";
    const ble = esp32.ble_name || esp32.ble_address ? ` ${esp32.ble_name || esp32.ble_address}` : "";
    fields.esp32Status.textContent = `${transport}${esp32.status || "waiting"}${last}${serial}${ble}`;
  } else {
    fields.esp32Status.textContent = t("disabled");
  }
}

async function startRecording() {
  const name = fields.recordingName.value.trim() || new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
  fields.recordingName.value = name;
  const response = await fetch("/api/recording/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    fields.recordingSaved.textContent = `${t("startFailed")}: ${await response.text()}`;
  }
}

async function stopRecording() {
  const response = await fetch("/api/recording/stop", { method: "POST" });
  if (!response.ok) {
    fields.recordingSaved.textContent = `${t("stopFailed")}: ${await response.text()}`;
  }
}

async function sendDebugCommand(kind) {
  const response = await fetch(`/api/debug/command/${kind}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: "manual debug button" }),
  });
  if (!response.ok) {
    fields.commandLog.textContent = `debug failed: ${await response.text()}`;
  }
}

async function updateRuntimeSettings(payload) {
  const response = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    fields.commandLog.textContent = `${t("settingsFailed")}: ${await response.text()}`;
  }
}

async function setDebugMode(enabled) {
  await updateRuntimeSettings({ debug_mode: enabled });
}

async function setLowOutputMode(enabled) {
  await updateRuntimeSettings({ low_output_mode: enabled });
}

async function setEnglishMode(enabled) {
  await updateRuntimeSettings({ ui_language: enabled ? "en" : "ja" });
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws`);

  ws.addEventListener("open", () => setStatus("connected", t("browserConnected")));
  ws.addEventListener("message", (event) => {
    try {
      update(JSON.parse(event.data));
    } catch (error) {
      console.error(error);
    }
  });
  ws.addEventListener("close", () => {
    setStatus("waiting", t("reconnecting"));
    setTimeout(connect, 1500);
  });
  ws.addEventListener("error", () => {
    ws.close();
  });
}

function makeHistory(seedBpm, seedRr, stress = 0) {
  const now = Date.now() / 1000;
  const hr = [];
  const rr = [];
  for (let index = 0; index < 60; index += 1) {
    const phase = index / 5;
    const eventShape = Math.max(0, 1 - Math.abs(index - 43) / 8) * stress;
    hr.push({
      t: now - (60 - index),
      v: seedBpm + Math.sin(phase) * 2.8 + eventShape * 16,
    });
    rr.push({
      t: now - (60 - index),
      v: seedRr + Math.cos(phase * 0.9) * 18 - eventShape * 95,
    });
  }
  return { hr, rr };
}

function demoSnapshot(kind) {
  const commandMap = {
    normal: { kind: "none", label: "なし", priority: 0, source: "idle", hp: 92, bpm: 72, rr: 832, startle: 8, fear: 18, movement: 6, tone: "calm" },
    startle: { kind: "startle", label: "びっくり", priority: 2, source: "h6-detector", hp: 88, bpm: 101, rr: 604, startle: 86, fear: 48, movement: 22, tone: "hot" },
    damage: { kind: "damage", label: "ダメージ", priority: 3, source: "re9-bridge", hp: 42, bpm: 96, rr: 632, startle: 64, fear: 58, movement: 18, tone: "hot" },
    faltering: { kind: "faltering", label: "ふらつき", priority: 1, source: "re9-bridge", hp: 14.8, bpm: 88, rr: 686, startle: 26, fear: 71, movement: 12, tone: "warn" },
    death: { kind: "death", label: "死亡", priority: 4, source: "re9-bridge", hp: 0, bpm: 104, rr: 578, startle: 78, fear: 83, movement: 24, tone: "hot" },
  };
  const demo = commandMap[kind] || commandMap.normal;
  const history = makeHistory(demo.bpm, demo.rr, Math.max(demo.startle, demo.fear) / 100);
  const active = {
    kind: demo.kind,
    label: demo.label,
    source: demo.source,
    priority: demo.priority,
    payload: {
      hp: demo.hp,
      max_hp: 100,
      hp_percent: demo.hp,
      damage_count: demo.kind === "damage" ? 7 : 6,
    },
  };

  return {
    status: "connected",
    message: "READMEデモ表示 / 疑似データ",
    state: {
      label: demo.kind === "none" ? "安定" : demo.label,
      tone: demo.tone,
      detail: demo.kind === "none" ? "RR interval は落ち着いています。" : "コマンド優先度エンジンが反応しています。",
    },
    device: {
      name: "COOSPO H6 Heart Rate Monitor",
      address: "DEMO:H6:README",
      info: { model: "H6", firmware: "demo" },
    },
    measurement: {
      bpm: demo.bpm,
      rr_ms: [demo.rr, demo.rr + 18, demo.rr - 11],
      battery_percent: 91,
      last_seen: "demo",
      contact_detected: true,
      last_raw_hex: "10 5f 6c 02",
    },
    hrv: {
      rmssd_ms: demo.kind === "none" ? 56 : 28,
      sdnn_ms: demo.kind === "none" ? 61 : 35,
      pnn50_percent: demo.kind === "none" ? 34 : 9,
      rr_count: 420,
    },
    detection: {
      primary: demo.kind === "none" ? "平常" : demo.label,
      tone: demo.tone,
      confidence: Math.max(demo.startle, demo.fear),
      startle_score: demo.startle,
      fear_tension_score: demo.fear,
      movement_score: demo.movement,
      reasons: demo.kind === "none"
        ? ["baseline stable", "RR variance normal"]
        : ["RR interval short drop", "BPM delayed rise", "3秒追跡で確定"],
    },
    recording: { active: false, saved: null },
    game: {
      game: { running: true },
      bridge: { present: true, fresh: true, age_seconds: 0.2 },
      player: {
        found: true,
        hp: demo.hp,
        max_hp: 100,
        hp_percent: demo.hp,
        faltering_low_hp: demo.kind === "faltering",
        low_hp_stage: demo.kind === "faltering" ? "danger" : "fine",
        faltering_elapsed_seconds: demo.kind === "faltering" ? 8 : 0,
        faltering_intensity: demo.kind === "faltering" ? 5 : null,
      },
    },
    commands: {
      active,
      recent: demo.kind === "none" ? [] : [active, { ...active, kind: "none", label: "なし", source: "idle" }],
    },
    esp32: {
      enabled: true,
      status: "sent",
      last_sent: {
        kind: demo.kind,
        label: demo.label,
        output: demo.kind === "none"
          ? { intensity: 0, duration_ms: 0 }
          : { intensity: demo.kind === "death" ? 15 : demo.kind === "faltering" ? 5 : demo.kind === "damage" ? 10 : 8, duration_ms: demo.kind === "death" ? 10000 : 3000 },
      },
    },
    history,
  };
}

function runDemoMode(kind) {
  update(demoSnapshot(kind));
  setInterval(() => update(demoSnapshot(kind)), 1600);
}

fields.startRecording.addEventListener("click", () => {
  startRecording().catch((error) => {
    fields.recordingSaved.textContent = `${t("startFailed")}: ${error}`;
  });
});

fields.stopRecording.addEventListener("click", () => {
  stopRecording().catch((error) => {
    fields.recordingSaved.textContent = `${t("stopFailed")}: ${error}`;
  });
});

fields.debugDamage.addEventListener("click", () => {
  sendDebugCommand("damage").catch((error) => {
    fields.commandLog.textContent = `debug failed: ${error}`;
  });
});

fields.debugDeath.addEventListener("click", () => {
  sendDebugCommand("death").catch((error) => {
    fields.commandLog.textContent = `debug failed: ${error}`;
  });
});

fields.debugStartle.addEventListener("click", () => {
  sendDebugCommand("startle").catch((error) => {
    fields.commandLog.textContent = `debug failed: ${error}`;
  });
});

fields.debugFaltering.addEventListener("click", () => {
  sendDebugCommand("faltering").catch((error) => {
    fields.commandLog.textContent = `debug failed: ${error}`;
  });
});

fields.debugNone.addEventListener("click", () => {
  sendDebugCommand("none").catch((error) => {
    fields.commandLog.textContent = `debug failed: ${error}`;
  });
});

fields.debugMode.addEventListener("change", () => {
  setDebugMode(fields.debugMode.checked).catch((error) => {
    fields.commandLog.textContent = `${t("settingsFailed")}: ${error}`;
  });
});

fields.lowOutputMode.addEventListener("change", () => {
  setLowOutputMode(fields.lowOutputMode.checked).catch((error) => {
    fields.commandLog.textContent = `${t("settingsFailed")}: ${error}`;
  });
});

fields.englishMode.addEventListener("change", () => {
  setEnglishMode(fields.englishMode.checked).catch((error) => {
    fields.commandLog.textContent = `${t("settingsFailed")}: ${error}`;
  });
});

const demoKind = new URLSearchParams(window.location.search).get("demo");
applyTranslations();
if (demoKind) {
  runDemoMode(demoKind);
} else {
  connect();
}
