/* iBOX Cloud sidebar panel: live view, memory card recordings, remote control, settings, events.
 * Plain web components, no build step. Video reaches the browser over one WebSocket and is decoded
 * with WebCodecs ("native"); HA's own camera stream (HLS/WebRTC) is the fallback. */

const TEXT = {
  ru: {
    title: "iBOX", connection: "Подключение", online: "В сети", offline: "Не в сети",
    recording: "Запись", recWorking: "Активна", recIdle: "Остановлена",
    ignition: "Зажигание", signal: "Сигнал", temp: "Температура ЦП", card: "Карта памяти", gps: "GPS",
    gpsFix: "Есть сигнал", gpsNoFix: "Нет сигнала", firmware: "Прошивка", on: "Вкл", off: "Выкл",
    tabLive: "Эфир", tabFiles: "Записи", tabRemote: "Пульт", tabSettings: "Настройки", tabEvents: "События",
    quality: "Качество", q720: "720p", q360: "360p", camera: "Камера", front: "Передняя", rear: "Задняя",
    player: "Плеер", modeAuto: "Авто", modeNative: "Нативный", modeHls: "HLS",
    sound: "Звук", fullscreen: "Во весь экран", start: "Смотреть эфир", stop: "Остановить",
    connecting: "Подключение к регистратору…", ended: "Поток завершён", error: "Ошибка",
    noWebCodecs: "Браузер не умеет декодировать это видео (WebCodecs). Переключитесь на HLS.",
    hlsNote: "HLS через камеру Home Assistant: задержка 10–15 с.",
    normal: "Обычные", event: "Защищённые", parking: "Парковка", cloud: "Облако", download: "Скачать",
    condition: "Условия записи", period: "Дата", from: "С", to: "По", apply: "Применить",
    cond: { 0: "Все видео", 3: "G-сенсор во время движения", 4: "Ручная блокировка кнопкой", 2: "G-сенсор в режиме парковки", 1: "Датчик движения в режиме парковки" },
    periods: { today: "Сегодня", yesterday: "Вчера", week: "Неделя", month: "Месяц", "3months": "3 месяца", custom: "Своё" },
    select: "Выбрать", cancel: "Отмена", selectAll: "Выбрать все", selected: (n) => `Выбрано: ${n}`,
    delete: "Удалить", deleteN: (n) => `Удалить (${n})`, confirmDelete: "Точно удалить?",
    deleted: (n) => `Удалено: ${n}`, deletePartly: (n, m) => `Удалено ${n} из ${m}`, deleteFailed: "Не удалось удалить", cloudEmpty: "Записей в облаке за этот период нет.", newest: "Сначала новые", oldest: "Сначала старые",
    refresh: "Обновить", more: "Загрузить ещё", empty: "Записей нет", loading: "Загрузка…",
    playback: "Воспроизведение", close: "Закрыть", speed: "Скорость",
    noPush: "Канал MQTT не подключён — записи и события недоступны.",
    eventsEmpty: "Событий пока нет. Здесь появятся удары, парковка и срабатывания радара.",
    saved: "Сохранено", failed: "Не удалось сохранить",
    evRadar: "Радар", evOther: "Событие",
    evTypes: { parking_activity: "Срабатывание на парковке", parking_recording: "Новая запись на парковке", event_recording: "Новая защищённая запись", cloud_recording: "Новая запись в облаке" },
    nativeOnlyPlayback: "Воспроизведение записей работает только в нативном плеере.",
    devices: "Регистратор",
  },
  en: {
    title: "iBOX", connection: "Connection", online: "Online", offline: "Offline",
    recording: "Recording", recWorking: "Active", recIdle: "Stopped",
    ignition: "Ignition", signal: "Signal", temp: "CPU temperature", card: "Memory card", gps: "GPS",
    gpsFix: "Signal", gpsNoFix: "No signal", firmware: "Firmware", on: "On", off: "Off",
    tabLive: "Live", tabFiles: "Recordings", tabRemote: "Remote", tabSettings: "Settings", tabEvents: "Events",
    quality: "Quality", q720: "720p", q360: "360p", camera: "Camera", front: "Front", rear: "Rear",
    player: "Player", modeAuto: "Auto", modeNative: "Native", modeHls: "HLS",
    sound: "Sound", fullscreen: "Fullscreen", start: "Watch live", stop: "Stop",
    connecting: "Connecting to the dashcam…", ended: "Stream ended", error: "Error",
    noWebCodecs: "This browser cannot decode the video (WebCodecs). Switch to HLS.",
    hlsNote: "HLS through the Home Assistant camera: 10–15 s delay.",
    normal: "Normal", event: "Protected", parking: "Parking", cloud: "Cloud", download: "Download",
    condition: "Recording trigger", period: "Date", from: "From", to: "To", apply: "Apply",
    cond: { 0: "All videos", 3: "G-sensor while driving", 4: "Manual lock button", 2: "G-sensor in parking mode", 1: "Motion sensor in parking mode" },
    periods: { today: "Today", yesterday: "Yesterday", week: "Week", month: "Month", "3months": "3 months", custom: "Custom" },
    select: "Select", cancel: "Cancel", selectAll: "Select all", selected: (n) => `Selected: ${n}`,
    delete: "Delete", deleteN: (n) => `Delete (${n})`, confirmDelete: "Delete for sure?",
    deleted: (n) => `Deleted: ${n}`, deletePartly: (n, m) => `Deleted ${n} of ${m}`, deleteFailed: "Could not delete", cloudEmpty: "No cloud recordings for this period.", newest: "Newest first", oldest: "Oldest first",
    refresh: "Refresh", more: "Load more", empty: "No recordings", loading: "Loading…",
    playback: "Playback", close: "Close", speed: "Speed",
    noPush: "MQTT channel is not connected — recordings and events are unavailable.",
    eventsEmpty: "No events yet. Shocks, parking and radar alerts will show up here.",
    saved: "Saved", failed: "Could not save",
    evRadar: "Radar", evOther: "Event",
    evTypes: { parking_activity: "Parking mode triggered", parking_recording: "New parking recording", event_recording: "New protected recording", cloud_recording: "New cloud recording" },
    nativeOnlyPlayback: "Recordings play only in the native player.",
    devices: "Dashcam",
  },
};

// The "Remote" tab mirrors the app's remote control screen
const REMOTE_IDS = ["radar_mode", "volume", "record_with_audio"];
// Titles clearer than the vendor's
const TITLE_OVERRIDES = {
  video_quality: { ru: "Уровень качества сохраняемого видео", en: "Recorded video quality" },
  volume: { ru: "Громкость оповещений", en: "Alert volume" },
  record_with_audio: { ru: "Запись звука на видео", en: "Record audio with video" },
};
// Options the app's remote control does not offer (still available under "Settings")
const REMOTE_HIDDEN_OPTIONS = { volume: ["6"] };

// Cloud recordings filter, in the app's order: videoType 0 all, 3 driving shock, 4 manual lock,
// 2 parking shock, 1 parking motion
const CLOUD_CONDITIONS = [0, 3, 4, 2, 1];
const CLOUD_PERIODS = ["today", "yesterday", "week", "month", "3months", "custom"];

const ICONS = {
  play: "M8,5.14V19.14L19,12.14L8,5.14Z",
  stop: "M18,18H6V6H18V18Z",
  close: "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
  fullscreen: "M5,5H10V7H7V10H5V5M14,5H19V10H17V7H14V5M17,14H19V19H14V17H17V14M10,17V19H5V14H7V17H10Z",
  volume: "M14,3.23V5.29C16.89,6.15 19,8.83 19,12C19,15.17 16.89,17.84 14,18.7V20.77C18,19.86 21,16.28 21,12C21,7.72 18,4.14 14,3.23M16.5,12C16.5,10.23 15.5,8.71 14,7.97V16C15.5,15.29 16.5,13.76 16.5,12M3,9V15H7L12,20V4L7,9H3Z",
  mute: "M12,4L9.91,6.09L12,8.18M4.27,3L3,4.27L7.73,9H3V15H7L12,20V13.27L16.25,17.53C15.58,18.04 14.83,18.46 14,18.7V20.77C15.38,20.45 16.63,19.82 17.68,18.96L19.73,21L21,19.73L12,10.73M19,12C19,12.94 18.8,13.82 18.46,14.64L19.97,16.15C20.62,14.91 21,13.5 21,12C21,7.72 18,4.14 14,3.23V5.29C16.89,6.15 19,8.83 19,12M16.5,12C16.5,10.23 15.5,8.71 14,7.97V10.18L16.45,12.63C16.5,12.43 16.5,12.21 16.5,12Z",
  refresh: "M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z",
  download: "M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z",
  delete: "M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z",
  check: "M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z",
  cloud: "M6.5,20Q4.22,20 2.61,18.43 1,16.85 1,14.58 1,12.63 2.17,11.1 3.35,9.57 5.25,9.15 5.88,6.85 7.75,5.43 9.63,4 12,4 14.93,4 16.96,6.04 19,8.07 19,11 20.73,11.2 21.86,12.5 23,13.78 23,15.5 23,17.38 21.69,18.69 20.38,20 18.5,20Z",
  lock: "M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z",
};

// Same thresholds as the signal sensor's icon in icons.json (LTE dBm)
const SIGNAL_ICONS = [
  [-90, "M21,4H16V20H21V4M14,9H9V20H14V9M7,14H2V20H7V14Z"],
  [-100, "M19.5,5.5V18.5H17.5V5.5H19.5M21,4H16V20H21V4M14,9H9V20H14V9M7,14H2V20H7V14Z"],
  [-110, "M19.5,5.5V18.5H17.5V5.5H19.5M12.5,10.5V18.5H10.5V10.5H12.5M21,4H16V20H21V4M14,9H9V20H14V9M7,14H2V20H7V14Z"],
  [-Infinity, "M19.5,5.5V18.5H17.5V5.5H19.5M12.5,10.5V18.5H10.5V10.5H12.5M5.5,15.5V18.5H3.5V15.5H5.5M21,4H16V20H21V4M14,9H9V20H14V9M7,14H2V20H7V14Z"],
];
const signalIcon = (dbm) => SIGNAL_ICONS.find(([min]) => dbm >= min)[1];

const svg = (path, size = 24) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><path fill="currentColor" d="${path}"/></svg>`;

// value for <input type="datetime-local" step="1"> in local time
const localInput = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19);

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/* ------------------------------------------------------------------ codecs */

function nalUnits(buf) {
  // Annex-B start codes -> [offset of NAL header, end]
  const out = [];
  let i = 0, start = -1;
  while (i + 3 <= buf.length) {
    if (buf[i] === 0 && buf[i + 1] === 0 && (buf[i + 2] === 1 || (buf[i + 2] === 0 && buf[i + 3] === 1))) {
      const sc = buf[i + 2] === 1 ? 3 : 4;
      if (start >= 0) out.push([start, i]);
      i += sc;
      start = i;
    } else i++;
  }
  if (start >= 0) out.push([start, buf.length]);
  return out;
}

function unescapeRbsp(b) {
  const out = [];
  for (let i = 0; i < b.length; i++) {
    if (i >= 2 && b[i] === 3 && b[i - 1] === 0 && b[i - 2] === 0) continue;
    out.push(b[i]);
  }
  return Uint8Array.from(out);
}

function codecCandidates(codec, data) {
  const hex = (n) => n.toString(16).padStart(2, "0");
  if (codec === 78) {
    for (const [s, e] of nalUnits(data)) {
      if ((data[s] & 0x1f) === 7 && e - s > 4) return [`avc1.${hex(data[s + 1])}${hex(data[s + 2])}${hex(data[s + 3])}`, "avc1.64002a", "avc1.42e01f"];
    }
    return ["avc1.64002a", "avc1.4d401f", "avc1.42e01f"];
  }
  const list = [];
  for (const [s, e] of nalUnits(data)) {
    if (((data[s] >> 1) & 0x3f) !== 33) continue; // SPS
    const sps = unescapeRbsp(data.subarray(s + 2, Math.min(e, s + 40)));
    const ptl = sps.subarray(1);
    const profileSpace = ptl[0] >> 6, tier = (ptl[0] >> 5) & 1, profile = ptl[0] & 0x1f;
    let compat = 0;
    for (let k = 0; k < 4; k++) compat = (compat << 8) | ptl[1 + k];
    let rev = 0;
    for (let k = 0; k < 32; k++) rev |= ((compat >>> k) & 1) << (31 - k);
    const level = ptl[11];
    const space = ["", "A", "B", "C"][profileSpace];
    list.push(`hev1.${space}${profile}.${(rev >>> 0).toString(16)}.${tier ? "H" : "L"}${level}.B0`);
    list.push(`hvc1.${space}${profile}.${(rev >>> 0).toString(16)}.${tier ? "H" : "L"}${level}.B0`);
    break;
  }
  return list.concat(["hev1.1.6.L93.B0", "hev1.1.6.L120.90", "hvc1.1.6.L120.90"]);
}

/* -------------------------------------------------------------- native player */

class NativePlayer {
  /** WebSocket + WebCodecs. `onStatus(state, info)`; states: connecting, streaming, ended, error, unsupported. */
  constructor(hass, devicePath, canvas, onStatus, onStats) {
    this.hass = hass;
    this.path = devicePath;
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onStatus = onStatus;
    this.onStats = onStats;
    this.ws = null;
    this.vdec = null;
    this.adec = null;
    this.audioCtx = null;
    this.muted = true;
    this.audioTime = 0;
    this.waitKey = true;
    this.codecName = "";
    this.stats = { frames: 0, bytes: 0, dropped: 0, w: 0, h: 0, last: performance.now() };
    this.statsTimer = null;
  }

  static supported() {
    return typeof window.VideoDecoder === "function" && typeof window.EncodedVideoChunk === "function";
  }

  async open(firstCommand) {
    this.close();
    if (!NativePlayer.supported()) {
      this.onStatus("unsupported");
      return;
    }
    this.onStatus("connecting");
    let signed;
    try {
      signed = await this.hass.callWS({ type: "auth/sign_path", path: this.path, expires: 3600 });
    } catch (err) {
      this.onStatus("error", { message: err.message || String(err) });
      return;
    }
    const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${signed.path}`;
    const ws = (this.ws = new WebSocket(url));
    ws.binaryType = "arraybuffer";
    ws.onopen = () => ws.send(JSON.stringify(firstCommand));
    ws.onmessage = (ev) => (typeof ev.data === "string" ? this._onText(ev.data) : this._onBinary(ev.data));
    ws.onclose = () => {
      if (this.ws === ws) this.onStatus("ended");
    };
    this.statsTimer = setInterval(() => this._reportStats(), 1000);
  }

  send(cmd) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(cmd));
  }

  close() {
    if (this.ws) {
      const ws = this.ws;
      this.ws = null;
      try { ws.close(); } catch (e) { /* already closed */ }
    }
    clearInterval(this.statsTimer);
    for (const dec of [this.vdec, this.adec]) {
      try { if (dec && dec.state !== "closed") dec.close(); } catch (e) { /* ignore */ }
    }
    this.vdec = this.adec = null;
    this.waitKey = true;
  }

  setMuted(muted) {
    this.muted = muted;
    if (!muted && !this.audioCtx) {
      this.audioCtx = new AudioContext();
      this.audioTime = 0;
    }
    if (this.audioCtx) (muted ? this.audioCtx.suspend() : this.audioCtx.resume());
  }

  _onText(text) {
    let msg;
    try { msg = JSON.parse(text); } catch (e) { return; }
    if (msg.type === "status") this.onStatus(msg.state, msg);
  }

  async _configureVideo(codec, data) {
    for (const c of codecCandidates(codec, data)) {
      const config = { codec: c, optimizeForLatency: true, hardwareAcceleration: "no-preference" };
      try {
        const res = await VideoDecoder.isConfigSupported(config);
        if (!res.supported) continue;
      } catch (e) { continue; }
      this.vdec = new VideoDecoder({
        output: (frame) => this._draw(frame),
        error: (e) => { this.onStatus("error", { message: e.message }); this.vdec = null; this.waitKey = true; },
      });
      this.vdec.configure(config);
      this.codecName = c;
      return true;
    }
    return false;
  }

  _draw(frame) {
    const w = frame.displayWidth, h = frame.displayHeight;
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this.stats.w = w;
    this.stats.h = h;
    this.ctx.drawImage(frame, 0, 0, w, h);
    frame.close();
    this.stats.frames++;
  }

  async _onBinary(buf) {
    const view = new DataView(buf);
    const kind = view.getUint8(0), codec = view.getUint8(1), key = view.getUint8(2) === 1;
    const pts = Number(view.getBigUint64(4, true));
    const data = new Uint8Array(buf, 12);
    this.stats.bytes += buf.byteLength;
    if (kind === 1) {
      if (!this.vdec) {
        if (!key || this._configuring) return;
        this._configuring = true;
        const ok = await this._configureVideo(codec, data);
        this._configuring = false;
        if (!ok) {
          this.close();
          this.onStatus("unsupported");
          return;
        }
      }
      if (this.waitKey && !key) return;
      if (this.vdec.decodeQueueSize > 30) { // falling behind: skip to the next keyframe
        this.stats.dropped++;
        this.waitKey = true;
        return;
      }
      this.waitKey = false;
      try {
        this.vdec.decode(new EncodedVideoChunk({ type: key ? "key" : "delta", timestamp: pts * 1000, data }));
      } catch (e) {
        this.waitKey = true;
      }
    } else if (kind === 2 && !this.muted && this.audioCtx && typeof window.AudioDecoder === "function") {
      if (!this.adec) {
        this.adec = new AudioDecoder({ output: (a) => this._playAudio(a), error: () => { this.adec = null; } });
        this.adec.configure({ codec: "mp4a.40.2", sampleRate: 16000, numberOfChannels: 1 });
      }
      try {
        this.adec.decode(new EncodedAudioChunk({ type: "key", timestamp: pts * 1000, data }));
      } catch (e) { /* skip */ }
    }
  }

  _playAudio(audio) {
    const ctx = this.audioCtx;
    if (!ctx) { audio.close(); return; }
    const buffer = ctx.createBuffer(audio.numberOfChannels, audio.numberOfFrames, audio.sampleRate);
    for (let ch = 0; ch < audio.numberOfChannels; ch++) {
      const plane = new Float32Array(audio.numberOfFrames);
      audio.copyTo(plane, { planeIndex: ch, format: "f32-planar" });
      buffer.copyToChannel(plane, ch);
    }
    audio.close();
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    const now = ctx.currentTime;
    if (this.audioTime < now || this.audioTime > now + 0.6) this.audioTime = now + 0.12; // small jitter buffer
    src.start(this.audioTime);
    this.audioTime += buffer.duration;
  }

  _reportStats() {
    const now = performance.now(), dt = (now - this.stats.last) / 1000;
    const fps = this.stats.frames / dt, kbps = (this.stats.bytes * 8) / dt / 1000;
    this.onStats({ codec: this.codecName, w: this.stats.w, h: this.stats.h, fps, kbps, dropped: this.stats.dropped });
    this.stats.frames = 0;
    this.stats.bytes = 0;
    this.stats.last = now;
  }
}

/* -------------------------------------------------------------------- panel */

class IboxPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = this._load("tab", "live");
    this._mode = this._load("mode", "auto");
    this._device = null; // full state incl. schema
    this._state = null; // live state from the subscription
    this._settingsTab = null;
    this._files = {
      type: 1, channel: 1, sort: 0, items: [], loading: false, done: false, error: "",
      cloud: { cond: 0, period: "week", from: "", to: "", selecting: false, selected: new Set() },
    };
    this._thumbs = {};
    this._player = null;
    this._pbPlayer = null;
    this._muted = true;
    this._toast = "";
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._init();
    if (this._hlsCard) this._hlsCard.hass = hass;
    if (this._menu) this._menu.hass = hass;
  }

  set narrow(v) {
    this._narrow = v;
    if (this._menu) this._menu.narrow = v;
  }

  get t() {
    return (this._hass?.language || "en").startsWith("ru") ? TEXT.ru : TEXT.en;
  }

  get lang() {
    return (this._hass?.language || "en").startsWith("ru") ? "ru" : "en";
  }

  _load(key, def) {
    try { return localStorage.getItem(`ibox-panel-${key}`) || def; } catch (e) { return def; }
  }

  _save(key, value) {
    try { localStorage.setItem(`ibox-panel-${key}`, value); } catch (e) { /* private mode */ }
  }

  disconnectedCallback() {
    this._stopLive();
    this._stopPlayback();
    if (this._unsub) { this._unsub.then((u) => u()); this._unsub = null; }
  }

  connectedCallback() {
    if (this._hass && !this._unsub && this._device) this._subscribe();
  }

  async _init() {
    this._renderShell();
    try {
      const res = await this._hass.callWS({ type: "ibox_cloud/devices" });
      this._device = res.devices[0] || null;
    } catch (e) {
      this._device = null;
    }
    if (!this._device) {
      this.shadowRoot.querySelector(".content").innerHTML = `<div class="card pad">${esc(this.t.error)}</div>`;
      return;
    }
    this._state = this._device;
    this._subscribe();
    this._render();
  }

  _subscribe() {
    this._unsub = this._hass.connection.subscribeMessage(
      (state) => {
        this._state = { ...this._state, ...state };
        this._renderSummary();
        if (this._tab === "remote" || this._tab === "settings") this._refreshValues();
        if (this._tab === "events") this._renderTab();
      },
      { type: "ibox_cloud/subscribe", device_id: this._device.device_id },
    );
  }

  /* ---------------- shell, summary, tabs */

  _renderShell() {
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <span class="menu"></span>
        <div class="main-title"></div>
      </div>
      <div class="summary"></div>
      <div class="tabs"></div>
      <div class="content"><div class="card pad">${esc(this.t.loading)}</div></div>
      <div class="toast" hidden></div>`;
    const menu = document.createElement("ha-menu-button");
    menu.hass = this._hass;
    menu.narrow = this._narrow;
    this._menu = menu;
    this.shadowRoot.querySelector(".menu").appendChild(menu);
  }

  _render() {
    this.shadowRoot.querySelector(".main-title").textContent = this._device.name || this.t.title;
    this._renderSummary();
    const tabs = [["live", this.t.tabLive], ["files", this.t.tabFiles], ["remote", this.t.tabRemote], ["settings", this.t.tabSettings], ["events", this.t.tabEvents]];
    const bar = this.shadowRoot.querySelector(".tabs");
    bar.innerHTML = tabs.map(([id, label]) => `<button class="tab ${id === this._tab ? "active" : ""}" data-tab="${id}">${esc(label)}</button>`).join("");
    bar.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => this._switchTab(b.dataset.tab)));
    this._renderTab();
  }

  _switchTab(tab) {
    if (tab === this._tab) return;
    if (this._tab === "live") this._stopLive();
    if (this._tab === "files") this._stopPlayback();
    this._tab = tab;
    this._save("tab", tab);
    this.shadowRoot.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    this._renderTab();
  }

  _renderSummary() {
    const a = this._state?.attrs || {}, t = this.t;
    const num = (v) => (v === undefined || v === null || v === "" ? null : Number(v));
    const free = num(a.sdcard_freesize), total = num(a.sdcard_totalsize);
    const gb = (b) => (b / 1e9).toFixed(1);
    // the cloud keeps the last reported values after the dashcam goes offline
    const online = a.connection_status === "1", stale = online ? "" : " stale";
    const items = [
      [t.connection.toUpperCase(), online ? t.online : t.offline, online ? "ok" : "bad"],
      [t.recording.toUpperCase(), online && a.record_status === "1" ? t.recWorking : t.recIdle, online && a.record_status === "1" ? "rec" : ""],
      [t.ignition.toUpperCase(), online && a.acc_status === "1" ? t.on : t.off, ""],
      // icon only; the dBm value shows on hover
      num(a.device_signal_quality) !== null
        ? [t.signal.toUpperCase(), "", stale, signalIcon(num(a.device_signal_quality)), `${a.device_signal_quality} ${this.lang === "ru" ? "дБм" : "dBm"}`]
        : [t.signal.toUpperCase(), "—", ""],
      [t.temp.toUpperCase(), num(a.device_temp) !== null ? `${a.device_temp} °C` : "—", (online && num(a.device_temp) >= 85 ? "warn" : "") + stale],
      [t.card.toUpperCase(), free !== null && total ? `${gb(free)} / ${gb(total)} GB` : "—", ""],
      [t.gps.toUpperCase(), online && a.gps_status === "1" ? t.gpsFix : t.gpsNoFix, ""],
      [t.firmware.toUpperCase(), this._device.firmware || "—", ""],
    ];
    this.shadowRoot.querySelector(".summary").innerHTML = items
      .map(([label, value, cls, icon, hint]) => `<div class="stat"><div class="stat-label">${esc(label)}</div><div class="stat-value ${cls}">${icon ? `<span class="stat-icon" title="${esc(hint || "")}">${svg(icon, 22)}</span>` : ""}${esc(value)}</div></div>`)
      .join("");
  }

  _renderTab() {
    const box = this.shadowRoot.querySelector(".content");
    if (this._tab === "live") this._renderLive(box);
    else if (this._tab === "files") this._renderFiles(box);
    else if (this._tab === "remote") this._renderRemote(box);
    else if (this._tab === "settings") this._renderSettings(box);
    else this._renderEvents(box);
  }

  _showToast(text) {
    const el = this.shadowRoot.querySelector(".toast");
    el.textContent = text;
    el.hidden = false;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => (el.hidden = true), 2500);
  }

  /* ---------------- live */

  _renderLive(box) {
    const t = this.t, live = this._state.live || {};
    const seg = (name, options, current) => `<div class="seg" data-name="${name}">${options
      .map(([v, l]) => `<button class="seg-btn ${String(v) === String(current) ? "on" : ""}" data-value="${v}">${esc(l)}</button>`).join("")}</div>`;
    box.innerHTML = `
      <div class="card">
        <div class="player-box">
          <canvas class="video"></canvas>
          <div class="hls" hidden></div>
          <div class="overlay"><button class="big-play" title="${esc(t.start)}">${svg(ICONS.play, 48)}</button><div class="overlay-text"></div></div>
        </div>
        <div class="controls">
          <button class="icon-btn toggle-live" title="${esc(t.start)}">${svg(ICONS.play)}</button>
          <button class="icon-btn mute" title="${esc(t.sound)}">${svg(this._muted ? ICONS.mute : ICONS.volume)}</button>
          <span class="ctl-label">${esc(t.quality)}</span>${seg("quality", [[1, t.q720], [2, t.q360]], live.quality)}
          <span class="ctl-label">${esc(t.camera)}</span>${seg("camera", [[1, t.front], [2, t.rear]], live.camera)}
          <span class="ctl-label">${esc(t.player)}</span>${seg("mode", [["auto", t.modeAuto], ["native", t.modeNative], ["hls", t.modeHls]], this._mode)}
          <span class="spacer"></span>
          <button class="icon-btn full" title="${esc(t.fullscreen)}">${svg(ICONS.fullscreen)}</button>
        </div>
        <div class="statusline"></div>
      </div>`;
    box.querySelector(".big-play").addEventListener("click", () => this._startLive());
    box.querySelector(".toggle-live").addEventListener("click", () => (this._liveOn ? this._stopLive() : this._startLive()));
    box.querySelector(".mute").addEventListener("click", () => {
      this._muted = !this._muted;
      if (this._player) this._player.setMuted(this._muted);
      if (this._hlsCard) this._setHlsMuted(this._muted);
      box.querySelector(".mute").innerHTML = svg(this._muted ? ICONS.mute : ICONS.volume);
    });
    box.querySelector(".full").addEventListener("click", () => {
      const el = box.querySelector(".player-box");
      (document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen?.());
    });
    box.querySelectorAll(".seg").forEach((s) => s.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".seg-btn");
      if (!btn) return;
      s.querySelectorAll(".seg-btn").forEach((b) => b.classList.toggle("on", b === btn));
      this._onLiveOption(s.dataset.name, btn.dataset.value);
    }));
    this._liveOn = false;
  }

  async _onLiveOption(name, value) {
    if (name === "mode") {
      this._mode = value;
      this._save("mode", value);
      if (this._liveOn) { this._stopLive(); this._startLive(); }
      return;
    }
    const res = await this._hass.callWS({ type: "ibox_cloud/live_options", device_id: this._device.device_id, [name]: Number(value) });
    this._state.live = { ...this._state.live, ...res };
  }

  _setOverlay(text, showPlay) {
    const box = this.shadowRoot.querySelector(".content");
    const ov = box.querySelector(".overlay");
    if (!ov) return;
    ov.hidden = !text && !showPlay;
    ov.querySelector(".big-play").hidden = !showPlay;
    ov.querySelector(".overlay-text").textContent = text || "";
  }

  _startLive() {
    const box = this.shadowRoot.querySelector(".content");
    this._liveOn = true;
    box.querySelector(".toggle-live").innerHTML = svg(ICONS.stop);
    const useHls = this._mode === "hls" || (this._mode === "auto" && !NativePlayer.supported());
    if (useHls) return this._startHls();
    box.querySelector(".hls").hidden = true;
    box.querySelector(".video").hidden = false;
    this._player = new NativePlayer(
      this._hass,
      this._state.live.ws_path,
      box.querySelector(".video"),
      (state, info) => this._onLiveStatus(state, info),
      (s) => this._onStats(s),
    );
    this._player.setMuted(this._muted);
    this._player.open({ cmd: "live" });
  }

  _onLiveStatus(state, info) {
    const t = this.t;
    if (state === "connecting") this._setOverlay(t.connecting, false);
    else if (state === "streaming") this._setOverlay("", false);
    else if (state === "unsupported") {
      if (this._mode === "auto") { this._player?.close(); this._player = null; this._startHls(); }
      else this._setOverlay(t.noWebCodecs, false);
    } else if (state === "error") this._setOverlay(`${t.error}: ${info?.message || ""}`, true);
    else if (state === "ended" && this._liveOn) { this._setOverlay(t.ended, true); this._liveOn = false; this._resetLiveButton(); }
  }

  _onStats(s) {
    const line = this.shadowRoot.querySelector(".statusline");
    if (!line) return;
    line.textContent = s.w ? `${s.codec || ""}  ${s.w}×${s.h}  ${s.fps.toFixed(0)} fps  ${(s.kbps / 1000).toFixed(2)} Mbit/s  dropped ${s.dropped}` : "";
  }

  _resetLiveButton() {
    const b = this.shadowRoot.querySelector(".toggle-live");
    if (b) b.innerHTML = svg(ICONS.play);
  }

  async _startHls() {
    const box = this.shadowRoot.querySelector(".content");
    const entity = this._state.live.camera_entity;
    box.querySelector(".video").hidden = true;
    const host = box.querySelector(".hls");
    host.hidden = false;
    host.innerHTML = "";
    this._setOverlay("", false);
    if (!entity) { this._setOverlay(this.t.error, true); return; }
    const helpers = await window.loadCardHelpers();
    const card = await helpers.createCardElement({ type: "picture-entity", entity, camera_view: "live", show_name: false, show_state: false });
    card.hass = this._hass;
    this._hlsCard = card;
    host.appendChild(card);
    this.shadowRoot.querySelector(".statusline").textContent = this.t.hlsNote;
    this._setHlsMuted(this._muted);
  }

  _setHlsMuted(muted) {
    // ha-camera-stream lives deep inside the card; mute its <video> when it appears
    const find = (root) => {
      if (!root) return null;
      const v = root.querySelector?.("video");
      if (v) return v;
      for (const el of root.querySelectorAll?.("*") || []) {
        const r = el.shadowRoot && find(el.shadowRoot);
        if (r) return r;
      }
      return null;
    };
    const apply = () => { const v = find(this._hlsCard?.shadowRoot); if (v) v.muted = muted; return !!v; };
    if (!apply()) setTimeout(apply, 1500);
  }

  _stopLive() {
    this._liveOn = false;
    if (this._player) { this._player.close(); this._player = null; }
    if (this._hlsCard) { this._hlsCard.remove(); this._hlsCard = null; }
    this._resetLiveButton();
    this._setOverlay("", true);
    const line = this.shadowRoot.querySelector(".statusline");
    if (line) line.textContent = "";
  }

  /* ---------------- recordings */

  _renderFiles(box) {
    const t = this.t, f = this._files, c = f.cloud;
    if (!this._state.push) f.type = "cloud"; // the cloud list works without the MQTT channel
    const isCloud = f.type === "cloud";
    const seg = (name, options, current, cls = "") => `<div class="seg ${cls}" data-name="${name}">${options
      .map(([v, l]) => `<button class="seg-btn ${String(v) === String(current) ? "on" : ""}" data-value="${v}">${esc(l)}</button>`).join("")}</div>`;
    box.innerHTML = `
      <div class="card playback" hidden>
        <div class="card-head"><span class="pb-title"></span><button class="icon-btn pb-close" title="${esc(t.close)}">${svg(ICONS.close)}</button></div>
        <div class="player-box"><canvas class="video"></canvas><video class="video clip" controls playsinline hidden></video>
          <div class="overlay"><div class="overlay-text"></div></div></div>
        <div class="controls">
          <button class="icon-btn pb-mute" title="${esc(t.sound)}">${svg(this._muted ? ICONS.mute : ICONS.volume)}</button>
          <span class="spacer"></span>
          <button class="del-btn pb-del" hidden>${svg(ICONS.delete, 20)}<span></span></button>
          <a class="icon-btn pb-dl" title="${esc(t.download)}" hidden>${svg(ICONS.download)}</a>
          <button class="icon-btn pb-full" title="${esc(t.fullscreen)}">${svg(ICONS.fullscreen)}</button>
        </div>
        <div class="statusline pb-status"></div>
      </div>
      <div class="filters">
        ${seg("type", (this._state.push ? [[1, t.normal], [2, t.event], [3, t.parking]] : []).concat([["cloud", t.cloud]]), f.type)}
        ${seg("channel", [[1, t.front], [2, t.rear]], f.channel)}
        ${isCloud ? "" : seg("sort", [[0, t.newest], [1, t.oldest]], f.sort)}
        <button class="icon-btn reload" title="${esc(t.refresh)}">${svg(ICONS.refresh)}</button>
        ${isCloud ? `<span class="spacer"></span><button class="seg-btn select-btn ${c.selecting ? "on" : ""}">${esc(c.selecting ? t.cancel : t.select)}</button>` : ""}
      </div>
      ${isCloud ? `
      <div class="filters">
        <span class="ctl-label">${esc(t.condition)}</span>
        ${seg("cond", CLOUD_CONDITIONS.map((v) => [v, t.cond[v]]), c.cond, "wrap")}
      </div>
      <div class="filters">
        <span class="ctl-label">${esc(t.period)}</span>
        ${seg("period", CLOUD_PERIODS.map((p) => [p, t.periods[p]]), c.period, "wrap")}
        <span class="custom-range" ${c.period === "custom" ? "" : "hidden"}>
          <input type="datetime-local" step="1" class="dt dt-from" value="${esc(c.from)}" aria-label="${esc(t.from)}">
          <span>—</span>
          <input type="datetime-local" step="1" class="dt dt-to" value="${esc(c.to)}" aria-label="${esc(t.to)}">
          <button class="seg-btn apply">${esc(t.apply)}</button>
        </span>
      </div>
      <div class="select-bar" ${c.selecting ? "" : "hidden"}>
        <span class="sel-count"></span>
        <button class="seg-btn sel-all">${esc(t.selectAll)}</button>
        <span class="spacer"></span>
        <button class="del-btn sel-del">${svg(ICONS.delete, 20)}<span></span></button>
      </div>` : ""}
      <div class="grid"></div>
      <div class="more-row"><button class="btn more" hidden>${esc(t.more)}</button><span class="files-note"></span></div>`;
    box.querySelectorAll(".filters .seg").forEach((s) => s.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".seg-btn");
      if (!btn) return;
      s.querySelectorAll(".seg-btn").forEach((b) => b.classList.toggle("on", b === btn));
      const name = s.dataset.name, v = btn.dataset.value;
      if (name === "cond") c.cond = Number(v);
      else if (name === "period") {
        c.period = v;
        if (v === "custom") {
          if (!c.from) { c.from = localInput(new Date(Date.now() - 86400000)); c.to = localInput(new Date()); }
          this._renderFiles(box);
          return;
        }
      } else this._files[name] = v === "cloud" ? v : Number(v);
      if (name === "type") { c.selecting = false; c.selected.clear(); this._files.items = []; this._renderFiles(box); return; }
      this._loadFiles(true);
    }));
    box.querySelector(".reload").addEventListener("click", () => this._loadFiles(true));
    box.querySelector(".more").addEventListener("click", () => this._loadFiles(false));
    box.querySelector(".pb-close").addEventListener("click", () => this._stopPlayback());
    box.querySelector(".pb-mute").addEventListener("click", () => {
      this._muted = !this._muted;
      if (this._pbPlayer) this._pbPlayer.setMuted(this._muted);
      box.querySelector(".pb-mute").innerHTML = svg(this._muted ? ICONS.mute : ICONS.volume);
    });
    box.querySelector(".pb-full").addEventListener("click", () => {
      const el = box.querySelector(".playback .player-box");
      (document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen?.());
    });
    if (isCloud) {
      box.querySelector(".apply").addEventListener("click", () => {
        c.from = box.querySelector(".dt-from").value;
        c.to = box.querySelector(".dt-to").value;
        this._loadFiles(true);
      });
      box.querySelector(".select-btn").addEventListener("click", () => {
        c.selecting = !c.selecting;
        c.selected.clear();
        this._renderFiles(box);
      });
      box.querySelector(".sel-all").addEventListener("click", () => {
        const all = f.items.every((v) => c.selected.has(v.id));
        f.items.forEach((v) => (all ? c.selected.delete(v.id) : c.selected.add(v.id)));
        this._renderGrid();
      });
      this._confirmButton(box.querySelector(".sel-del"), () => (c.selected.size ? t.deleteN(c.selected.size) : ""),
        () => this._deleteCloud([...c.selected]));
    }
    if (f.items.length) { this._renderGrid(); this._loadThumbs(); } else this._loadFiles(true);
  }

  /** Two-step delete button: the first click asks, the second (within 4 s) acts. */
  _confirmButton(btn, label, action) {
    const reset = () => { btn.classList.remove("armed"); btn.querySelector("span").textContent = label(); btn.disabled = !label(); };
    btn._reset = reset;
    reset();
    btn.addEventListener("click", async () => {
      if (!btn.classList.contains("armed")) {
        btn.classList.add("armed");
        btn.querySelector("span").textContent = this.t.confirmDelete;
        clearTimeout(btn._timer);
        btn._timer = setTimeout(reset, 4000);
        return;
      }
      clearTimeout(btn._timer);
      btn.disabled = true;
      await action();
      reset();
    });
  }

  async _deleteCloud(ids) {
    const t = this.t, f = this._files, c = f.cloud;
    if (!ids.length) return;
    try {
      const res = await this._hass.callWS({ type: "ibox_cloud/cloud_delete", device_id: this._device.device_id, ids });
      const gone = new Set(res.deleted);
      if (this._playing && gone.has(this._playing.id)) this._stopPlayback();
      f.items = f.items.filter((v) => !gone.has(v.id));
      gone.forEach((id) => c.selected.delete(id));
      this._showToast(gone.size === ids.length ? t.deleted(gone.size) : t.deletePartly(gone.size, ids.length));
    } catch (e) {
      this._showToast(`${t.deleteFailed}: ${e.message || e}`);
    }
    this._renderGrid();
  }

  _cloudRange() {
    const c = this._files.cloud, now = new Date();
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const sec = (d) => d.getTime() / 1000;
    const monthsAgo = (n) => { const d = new Date(now); d.setMonth(d.getMonth() - n); return sec(d); };
    switch (c.period) {
      case "today": return { start: sec(midnight) };
      case "yesterday": return { start: sec(midnight) - 86400, end: sec(midnight) };
      case "week": return { start: sec(now) - 7 * 86400 };
      case "month": return { start: monthsAgo(1) };
      case "3months": return { start: monthsAgo(3) };
      default: { // custom: both ends inclusive, to the second
        const from = c.from ? new Date(c.from) : null, to = c.to ? new Date(c.to) : null;
        const range = { start: from && !isNaN(from) ? sec(from) : 0 };
        if (to && !isNaN(to)) range.end = sec(to) + 1;
        return range;
      }
    }
  }

  async _loadFiles(reset) {
    const f = this._files;
    if (f.loading) return;
    if (reset) { f.items = []; f.done = false; f.cloud.selected.clear(); }
    f.loading = true;
    f.error = "";
    this._renderGrid();
    try {
      if (f.type === "cloud") {
        const range = this._cloudRange();
        const last = f.items[f.items.length - 1];
        if (last) range.end = last.trigger_time; // next page: older than the last one shown
        const res = await this._hass.callWS({
          type: "ibox_cloud/cloud_videos", device_id: this._device.device_id,
          channel: f.channel, video_type: f.cloud.cond, limit: 30, ...range,
        });
        f.items = f.items.concat(res.videos);
        f.done = res.videos.length < 30;
      } else {
        const res = await this._hass.callWS({
          type: "ibox_cloud/files", device_id: this._device.device_id,
          file_type: f.type, channel: f.channel, sort: f.sort, offset: f.items.length, limit: 20,
        });
        f.items = f.items.concat(res.files);
        f.done = res.files.length < 20;
      }
    } catch (e) {
      f.error = e.message || String(e);
    }
    f.loading = false;
    this._renderGrid();
    this._loadThumbs();
  }

  _fileTime(file) {
    if (file.trigger_time) return new Date(file.trigger_time * 1000).toLocaleString();
    const m = /(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/.exec(file.fileName || "");
    if (m) return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}:${m[6]}`;
    return new Date(file.time).toLocaleString();
  }

  _renderGrid() {
    const box = this.shadowRoot.querySelector(".content");
    const grid = box.querySelector(".grid");
    if (!grid) return;
    const f = this._files, t = this.t, c = f.cloud;
    grid.innerHTML = f.items.map((file, i) => {
      if (file.video_url) {
        const thumb = this._thumbs[file.snapshot_url];
        const picked = c.selecting && c.selected.has(file.id);
        return `<button class="file ${picked ? "picked" : ""}" data-i="${i}">
          <div class="thumb">${thumb ? `<img src="${thumb}" alt="">` : ""}<span class="lock">${svg(ICONS.cloud, 14)}</span>
            ${c.selecting ? `<span class="check">${picked ? svg(ICONS.check, 18) : ""}</span>` : ""}</div>
          <div class="file-time">${esc(this._fileTime(file))}</div>
          <div class="file-meta">${esc(t.cond[file.type] || "")}</div>
        </button>`;
      }
      const thumb = this._thumbs[file.fileName];
      return `<button class="file" data-i="${i}">
        <div class="thumb">${thumb ? `<img src="data:image/jpeg;base64,${thumb}" alt="">` : ""}
          <span class="dur">${Math.round((file.duration || 0) / 1000)} s</span>${file.lock ? `<span class="lock">${svg(ICONS.lock, 14)}</span>` : ""}</div>
        <div class="file-time">${esc(this._fileTime(file))}</div>
        <div class="file-meta">${esc(((file.size || 0) / 1e6).toFixed(1))} MB · ${esc(file.resolution || "")}</div>
      </button>`;
    }).join("");
    grid.querySelectorAll(".file").forEach((b) => b.addEventListener("click", () => {
      const file = f.items[Number(b.dataset.i)];
      if (file.video_url && c.selecting) {
        c.selected.has(file.id) ? c.selected.delete(file.id) : c.selected.add(file.id);
        this._renderGrid();
      } else this._play(file);
    }));
    box.querySelector(".more").hidden = f.done || f.loading || !f.items.length;
    box.querySelector(".files-note").textContent = f.loading ? t.loading : f.error ? `${t.error}: ${f.error}` : f.items.length ? "" : f.type === "cloud" ? t.cloudEmpty : t.empty;
    const count = box.querySelector(".sel-count");
    if (count) count.textContent = t.selected(c.selected.size);
    box.querySelector(".sel-del")?._reset?.();
  }

  async _loadThumbs() {
    if (this._files.type === "cloud") {
      for (const file of this._files.items.filter((v) => !this._thumbs[v.snapshot_url])) {
        try {
          const resp = await this._hass.fetchWithAuth(file.snapshot_url);
          if (!resp.ok) continue;
          this._thumbs[file.snapshot_url] = URL.createObjectURL(await resp.blob());
          this._renderGrid();
        } catch (e) { /* thumbnails are optional */ }
      }
      return;
    }
    const missing = this._files.items.filter((f) => !this._thumbs[f.fileName]).slice(0, 20);
    if (!missing.length) return;
    try {
      const res = await this._hass.callWS({
        type: "ibox_cloud/thumbnails", device_id: this._device.device_id,
        files: missing.map((f) => ({ fileName: f.fileName, pathName: f.pathName || "" })),
      });
      Object.assign(this._thumbs, res.images);
      this._renderGrid();
    } catch (e) { /* thumbnails are optional */ }
  }

  _play(file) {
    const box = this.shadowRoot.querySelector(".content");
    const card = box.querySelector(".playback");
    card.hidden = false;
    card.querySelector(".pb-title").textContent = `${this.t.playback}: ${this._fileTime(file)}`;
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    this._stopPlayback(true);
    this._playing = file;
    const overlay = (text) => { const o = card.querySelector(".overlay"); o.hidden = !text; o.querySelector(".overlay-text").textContent = text || ""; };
    const cloud = Boolean(file.video_url);
    card.querySelector("canvas.video").hidden = cloud;
    card.querySelector(".clip").hidden = !cloud;
    card.querySelector(".pb-mute").hidden = cloud;
    card.querySelector(".pb-dl").hidden = true;
    card.querySelector(".pb-status").textContent = "";
    const del = card.querySelector(".pb-del");
    del.hidden = !cloud;
    if (cloud && !del._reset) this._confirmButton(del, () => this.t.delete, () => this._deleteCloud([this._playing.id]));
    del._reset?.();
    if (cloud) { this._playCloud(card, file, overlay); return; }
    if (!NativePlayer.supported()) { overlay(this.t.nativeOnlyPlayback); return; }
    this._pbPlayer = new NativePlayer(
      this._hass, this._state.live.ws_path, card.querySelector(".video"),
      (state, info) => {
        if (state === "connecting") overlay(this.t.connecting);
        else if (state === "streaming") overlay("");
        else if (state === "unsupported") overlay(this.t.noWebCodecs);
        else if (state === "error") overlay(`${this.t.error}: ${info?.message || ""}`);
        else if (state === "ended") overlay(this.t.ended);
      },
      (s) => {
        const line = card.querySelector(".pb-status");
        if (line) line.textContent = s.w ? `${s.codec || ""}  ${s.w}×${s.h}  ${s.fps.toFixed(0)} fps  ${(s.kbps / 1000).toFixed(2)} Mbit/s` : "";
      },
    );
    this._pbPlayer.setMuted(this._muted);
    this._pbPlayer.open({ cmd: "playback", path: file.pathName, file: file.fileName });
  }

  async _playCloud(card, file, overlay) {
    // fetched whole (~3 MB): the endpoint needs the auth header, which <video src> cannot send
    const token = (this._clipToken = {});
    overlay(this.t.loading);
    try {
      const resp = await this._hass.fetchWithAuth(file.video_url);
      if (!resp.ok) throw new Error((await resp.text()) || resp.status);
      const blob = await resp.blob();
      if (token !== this._clipToken) return;
      this._clipUrl = URL.createObjectURL(blob);
      const video = card.querySelector(".clip");
      video.muted = this._muted;
      video.src = this._clipUrl;
      const dl = card.querySelector(".pb-dl");
      dl.href = this._clipUrl;
      dl.download = `${file.name || file.id}.mp4`;
      dl.hidden = false;
      overlay("");
      video.play().catch(() => {});
    } catch (e) {
      if (token === this._clipToken) overlay(`${this.t.error}: ${e.message || e}`);
    }
  }

  _stopPlayback(keepCard) {
    if (this._pbPlayer) { this._pbPlayer.send({ cmd: "stop" }); this._pbPlayer.close(); this._pbPlayer = null; }
    this._clipToken = null;
    this._playing = null;
    const clip = this.shadowRoot.querySelector(".content .clip");
    if (clip) { clip.pause(); clip.removeAttribute("src"); clip.load(); }
    if (this._clipUrl) { URL.revokeObjectURL(this._clipUrl); this._clipUrl = null; }
    if (!keepCard) {
      const card = this.shadowRoot.querySelector(".content .playback");
      if (card) card.hidden = true;
    }
  }

  /* ---------------- settings & remote */

  _settings() {
    const groups = this._device.schema?.attributes_settings || {};
    return Object.values(groups).flat();
  }

  _label(text) {
    return (text && (text[this.lang] || text.en || text.ru)) || "";
  }

  _optionLabels(item) {
    // the vendor's English labels are often copy-pasted ("Off", "On", "Off"): fall back to Russian
    const values = item.values || {};
    for (const lang of [this.lang, "ru"]) {
      const labels = Object.entries(values).map(([k, v]) => [k, (v && (v[lang] || v.ru)) || k]);
      if (new Set(labels.map((l) => l[1])).size === labels.length) return labels;
    }
    return Object.entries(values).map(([k, v]) => [k, `${this._label(v)} (${k})`]);
  }

  _field(item, big, hidden = []) {
    const attrs = this._state.attrs || {}, value = attrs[item.id];
    const title = esc(this._label(TITLE_OVERRIDES[item.id] || item.title));
    const missing = value === undefined;
    if (item.type === "toggle") {
      return `<label class="field toggle-field ${big ? "big" : ""}" data-id="${item.id}">
        <span class="field-title">${title}</span>
        <span class="switch"><input type="checkbox" data-id="${item.id}" ${value === "1" ? "checked" : ""} ${missing ? "disabled" : ""}><span class="track"></span></span>
      </label>`;
    }
    if (item.type === "select_input") {
      const opts = this._optionLabels(item).filter(([k]) => !hidden.includes(k));
      if (big && opts.length <= 7) {
        const layout = item.id === "radar_mode" ? "lead" : item.id === "volume" ? "row" : "";
        return `<div class="field big" data-id="${item.id}"><span class="field-title">${title}</span>
          <div class="seg wrap ${layout}" data-id="${item.id}">${opts.map(([k, l]) => `<button class="seg-btn ${k === value ? "on" : ""}" data-value="${esc(k)}" ${missing ? "disabled" : ""}>${esc(l)}</button>`).join("")}</div></div>`;
      }
      return `<label class="field" data-id="${item.id}"><span class="field-title">${title}</span>
        <select data-id="${item.id}" ${missing ? "disabled" : ""}>${value !== undefined && !opts.some(([k]) => k === value) ? `<option value="${esc(value)}" selected>${esc(value)}</option>` : ""}
        ${opts.map(([k, l]) => `<option value="${esc(k)}" ${k === value ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></label>`;
    }
    if (item.type === "input") {
      return `<label class="field" data-id="${item.id}"><span class="field-title">${title}</span>
        <input type="text" class="text" data-id="${item.id}" value="${esc(value || "")}" ${missing ? "disabled" : ""}></label>`;
    }
    return "";
  }

  _bindFields(root) {
    root.querySelectorAll("input[type=checkbox][data-id]").forEach((el) =>
      el.addEventListener("change", () => this._write(el.dataset.id, el.checked ? "1" : "0")));
    root.querySelectorAll("select[data-id]").forEach((el) => el.addEventListener("change", () => this._write(el.dataset.id, el.value)));
    root.querySelectorAll("input.text[data-id]").forEach((el) => el.addEventListener("change", () => this._write(el.dataset.id, el.value)));
    root.querySelectorAll(".seg[data-id]").forEach((s) => s.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".seg-btn");
      if (!btn || btn.disabled) return;
      s.querySelectorAll(".seg-btn").forEach((b) => b.classList.toggle("on", b === btn));
      this._write(s.dataset.id, btn.dataset.value);
    }));
  }

  async _write(attr, value) {
    try {
      await this._hass.callWS({ type: "ibox_cloud/set_attr", device_id: this._device.device_id, attr, value });
      this._state.attrs = { ...this._state.attrs, [attr]: value };
      this._showToast(this.t.saved);
    } catch (e) {
      this._showToast(`${this.t.failed}: ${e.message || e}`);
      this._refreshValues();
    }
  }

  _refreshValues() {
    // update values in place so open dropdowns and focus are not lost
    const root = this.shadowRoot.querySelector(".content");
    const attrs = this._state.attrs || {};
    root.querySelectorAll("input[type=checkbox][data-id]").forEach((el) => { el.checked = attrs[el.dataset.id] === "1"; });
    root.querySelectorAll("select[data-id]").forEach((el) => {
      if (el.matches(":focus")) return;
      const v = attrs[el.dataset.id];
      if (v !== undefined) el.value = v;
    });
    root.querySelectorAll(".seg[data-id]").forEach((s) => {
      const v = attrs[s.dataset.id];
      s.querySelectorAll(".seg-btn").forEach((b) => b.classList.toggle("on", b.dataset.value === v));
    });
  }

  _renderRemote(box) {
    const byId = Object.fromEntries(this._settings().map((i) => [i.id, i]));
    const items = REMOTE_IDS.map((id) => byId[id]).filter(Boolean);
    box.innerHTML = `<div class="card pad remote-card">
      <div class="remote">${items.map((i) => this._field(i, true, REMOTE_HIDDEN_OPTIONS[i.id] || [])).join("")}</div></div>`;
    this._bindFields(box);
  }

  _renderSettings(box) {
    const schema = this._device.schema || {};
    const tabs = (schema.tabs_settings || []).filter((tab) => (schema.attributes_settings?.[tab.id] || []).some((i) => i.type !== "function"));
    if (!this._settingsTab || !tabs.some((x) => x.id === this._settingsTab)) this._settingsTab = tabs[0]?.id;
    const items = (schema.attributes_settings?.[this._settingsTab] || []).filter((i) => i.type !== "function");
    const current = tabs.find((x) => x.id === this._settingsTab);
    box.innerHTML = `<div class="settings">
      <div class="card pad sections">${tabs.map((x) => `<button class="chip ${x.id === this._settingsTab ? "on" : ""}" data-tab="${x.id}">${esc(this._label(x.title))}</button>`).join("")}</div>
      <div class="card">
        <div class="card-head"><span>${esc(this._label(current?.title))}</span></div>
        <div class="form">${items.map((i) => `${this._field(i, false)}${i.description ? `<div class="desc">${esc(this._label(i.description))}</div>` : ""}`).join("")}</div>
      </div></div>`;
    box.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => { this._settingsTab = c.dataset.tab; this._renderSettings(box); }));
    this._bindFields(box);
  }

  /* ---------------- events */

  _renderEvents(box) {
    const t = this.t, events = this._state.events || [];
    if (!events.length) { box.innerHTML = `<div class="card pad">${esc(t.eventsEmpty)}</div>`; return; }
    const label = (e) => t.evTypes[e.type] || ((e.type || "").includes("radar") ? t.evRadar : (e.type || t.evOther).split("/").pop());
    box.innerHTML = `<div class="card"><table class="events"><tbody>${events.map((e) => `
      <tr><td class="ev-time">${esc(new Date(e.time * 1000).toLocaleString())}</td>
      <td class="ev-type">${esc(label(e))}</td>
      <td class="ev-data">${esc(JSON.stringify(e.data?.data || e.data || {}).slice(0, 160))}</td></tr>`).join("")}</tbody></table></div>`;
  }
}

const STYLE = `
  :host { display: block; min-height: 100vh; background: var(--primary-background-color); color: var(--primary-text-color);
    font-family: var(--ha-font-family-body, Roboto, sans-serif); }
  .toolbar { display: flex; align-items: center; height: var(--header-height, 56px); padding: 0 12px;
    background: var(--app-header-background-color, var(--primary-background-color)); color: var(--app-header-text-color, var(--primary-text-color));
    border-bottom: var(--app-header-border-bottom, 1px solid var(--divider-color)); box-sizing: border-box; position: sticky; top: 0; z-index: 2; }
  .main-title { margin-left: 8px; font-size: 20px; font-weight: 400; }
  .summary { display: flex; flex-wrap: wrap; gap: 8px 32px; padding: 16px 24px 4px; }
  .stat-label { font-size: 11px; letter-spacing: .04em; color: var(--secondary-text-color); }
  .stat-value { font-size: 18px; margin-top: 2px; }
  .stat-value.ok { color: var(--success-color, #43a047); }
  .stat-value.bad { color: var(--error-color, #db4437); }
  .stat-value.rec { color: var(--error-color, #db4437); }
  .stat-value.warn { color: var(--warning-color, #ffa600); }
  .stat-value.stale { color: var(--disabled-text-color, #9e9e9e); }
  .stat-icon { display: inline-flex; vertical-align: -4px; cursor: help; }
  .tabs { display: flex; gap: 4px; padding: 0 16px; border-bottom: 1px solid var(--divider-color); overflow-x: auto; }
  .tab { background: none; border: 0; color: var(--primary-text-color); padding: 12px 16px; font: inherit; font-size: 14px; cursor: pointer;
    border-bottom: 2px solid transparent; white-space: nowrap; }
  .tab.active { color: var(--primary-color); border-bottom-color: var(--primary-color); }
  .content { padding: 16px; max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
  .card { background: var(--card-background-color, var(--ha-card-background)); border-radius: var(--ha-card-border-radius, 12px);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color)); overflow: hidden; }
  .pad { padding: 16px; }
  .card-head { display: flex; align-items: center; justify-content: space-between; padding: 8px 8px 8px 16px; font-weight: 500; }
  .player-box { position: relative; background: #000; aspect-ratio: 16 / 9; display: flex; align-items: center; justify-content: center; }
  .player-box:fullscreen { aspect-ratio: auto; }
  .video { width: 100%; height: 100%; object-fit: contain; display: block; }
  .video[hidden], .icon-btn[hidden] { display: none; }
  .hls { width: 100%; }
  .overlay { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px;
    color: #fff; text-shadow: 0 1px 3px #000; pointer-events: none; }
  .overlay[hidden] { display: none; }
  .overlay button { pointer-events: auto; }
  .overlay-text { padding: 0 24px; text-align: center; }
  .big-play { width: 72px; height: 72px; border-radius: 50%; border: 0; background: rgba(0,0,0,.55); color: #fff; cursor: pointer; display: flex;
    align-items: center; justify-content: center; }
  .big-play:hover { background: var(--primary-color); }
  .controls, .filters { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 12px; }
  .filters { padding: 0; }
  .ctl-label { font-size: 12px; color: var(--secondary-text-color); margin-left: 8px; }
  .spacer { flex: 1; }
  .icon-btn { width: 40px; height: 40px; border-radius: 50%; border: 0; background: none; color: var(--primary-text-color); cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center; transition: background-color .15s; }
  .icon-btn:hover { background: var(--ha-color-fill-neutral-quiet-hover, rgba(127,127,127,.15)); }
  .seg { display: inline-flex; border: 1px solid var(--divider-color); border-radius: 8px; overflow: hidden; }
  .seg.wrap { flex-wrap: wrap; }
  .seg-btn { border: 0; background: none; color: var(--primary-text-color); padding: 6px 12px; font: inherit; font-size: 13px; cursor: pointer;
    border-right: 1px solid var(--divider-color); transition: background-color .15s; }
  .seg-btn:last-child { border-right: 0; }
  .seg-btn:hover { background: var(--ha-color-fill-neutral-quiet-hover, rgba(127,127,127,.12)); }
  .seg-btn.on { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .seg-btn:disabled { opacity: .5; cursor: default; }
  .statusline { font-family: var(--ha-font-family-code, monospace); font-size: 12px; color: var(--secondary-text-color); padding: 0 16px 10px; min-height: 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
  .file { text-align: left; background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 12px; padding: 0;
    overflow: hidden; cursor: pointer; color: var(--primary-text-color); font: inherit; transition: border-color .15s, transform .15s; }
  .file:hover { border-color: var(--primary-color); }
  .file.picked { border-color: var(--primary-color); box-shadow: 0 0 0 2px var(--primary-color) inset; }
  .check { position: absolute; right: 6px; top: 6px; width: 22px; height: 22px; border-radius: 50%; border: 2px solid #fff;
    background: rgba(0,0,0,.4); color: #fff; display: flex; align-items: center; justify-content: center; box-sizing: border-box; }
  .file.picked .check { background: var(--primary-color); border-color: var(--primary-color); }
  .filters .seg.wrap { border: 0; border-radius: 0; gap: 6px; flex-wrap: wrap; overflow: visible; }
  .filters .seg.wrap .seg-btn { border: 1px solid var(--divider-color); border-radius: 8px; }
  .filters .seg.wrap .seg-btn.on { border-color: var(--primary-color); }
  .filters > .ctl-label:first-child { min-width: 104px; margin-left: 4px; }
  .custom-range { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .custom-range[hidden] { display: none; }
  .dt { height: 32px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color);
    color: var(--primary-text-color); font: inherit; font-size: 13px; padding: 0 8px; color-scheme: light dark; }
  .select-btn, .apply, .sel-all { border: 1px solid var(--divider-color); border-radius: 8px; }
  .select-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 12px;
    background: var(--secondary-background-color, rgba(127,127,127,.1)); }
  .select-bar[hidden] { display: none; }
  .del-btn { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 12px; border-radius: 18px; border: 0;
    background: none; color: var(--error-color, #db4437); font: inherit; font-size: 14px; cursor: pointer; }
  .del-btn:hover { background: rgba(219,68,55,.12); }
  .del-btn.armed { background: var(--error-color, #db4437); color: #fff; }
  .del-btn:disabled { opacity: .4; cursor: default; }
  .del-btn[hidden] { display: none; }
  .thumb { position: relative; aspect-ratio: 16 / 9; background: #111; }
  .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .dur { position: absolute; right: 6px; bottom: 6px; background: rgba(0,0,0,.7); color: #fff; font-size: 12px; padding: 1px 6px; border-radius: 4px; }
  .lock { position: absolute; left: 6px; bottom: 6px; color: #fff; background: rgba(0,0,0,.7); border-radius: 4px; padding: 2px 3px; display: flex; }
  .file-time { padding: 8px 10px 0; font-size: 14px; }
  .file-meta { padding: 2px 10px 10px; font-size: 12px; color: var(--secondary-text-color); }
  .more-row { display: flex; justify-content: center; align-items: center; gap: 12px; min-height: 40px; color: var(--secondary-text-color); }
  .btn { border: 0; border-radius: 9999px; height: 40px; padding: 0 20px; background: var(--primary-color); color: var(--text-primary-color, #fff);
    font: inherit; font-weight: 500; cursor: pointer; }
  .hint { color: var(--secondary-text-color); margin-bottom: 12px; }
  .remote-card { max-width: 760px; }
  .remote { display: flex; flex-direction: column; }
  .field { display: flex; flex-direction: column; gap: 6px; }
  .field.big { display: grid; grid-template-columns: 200px 1fr; align-items: center; gap: 16px; padding: 14px 0;
    border-top: 1px solid var(--divider-color); }
  .field.big .seg { display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); border: 0; gap: 6px; }
  .field.big .seg-btn { border: 1px solid var(--divider-color); border-radius: 8px; height: 36px; }
  .field.big .seg-btn.on { border-color: var(--primary-color); }
  .toggle-field.big { grid-template-columns: 200px auto; justify-content: start; }
  .remote .field.big:first-child { border-top: 0; padding-top: 0; }
  .field.big .seg.lead { grid-template-columns: 1fr 1fr; }
  .field.big .seg.lead .seg-btn:first-child { grid-column: 1 / -1; height: 48px; font-size: 15px; font-weight: 500; }
  .field.big .seg.row { display: flex; flex-wrap: nowrap; gap: 6px; }
  .field.big .seg.row .seg-btn { width: 44px; padding: 0; flex: none; }
  .toggle-field { flex-direction: row; align-items: center; justify-content: space-between; cursor: pointer; }
  .field-title { font-size: 14px; }
  .field select, .field .text { height: 40px; border-radius: 8px 8px 0 0; border: 0; border-bottom: 1px solid var(--secondary-text-color);
    background: var(--ha-color-form-background, rgba(127,127,127,.08)); color: var(--primary-text-color); font: inherit; padding: 0 12px; }
  .switch { position: relative; width: 36px; height: 20px; flex: none; }
  .switch input { opacity: 0; width: 0; height: 0; position: absolute; }
  .track { position: absolute; inset: 0; border-radius: 10px; background: var(--switch-unchecked-track-color, #9e9e9e); transition: background-color .2s; cursor: pointer; }
  .track::after { content: ""; position: absolute; width: 16px; height: 16px; left: 2px; top: 2px; border-radius: 50%; background: #fff; transition: transform .2s; }
  .switch input:checked + .track { background: var(--primary-color); }
  .switch input:checked + .track::after { transform: translateX(16px); }
  .switch input:disabled + .track { opacity: .5; }
  .settings { display: grid; grid-template-columns: 280px 1fr; gap: 16px; align-items: start; }
  .sections { display: flex; flex-direction: column; gap: 2px; padding: 8px; }
  .chip { border: 0; border-radius: 8px; padding: 10px 12px; background: none; color: var(--primary-text-color); font: inherit; font-size: 14px;
    cursor: pointer; text-align: left; }
  .chip:hover { background: var(--ha-color-fill-neutral-quiet-hover, rgba(127,127,127,.12)); }
  .chip.on { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .form { display: flex; flex-direction: column; gap: 14px; padding: 0 16px 16px; }
  .desc { font-size: 12px; color: var(--secondary-text-color); margin-top: -8px; white-space: pre-line; }
  .events { width: 100%; border-collapse: collapse; font-size: 13px; }
  .events td { padding: 8px 12px; border-bottom: 1px solid var(--divider-color); vertical-align: top; }
  .ev-time { white-space: nowrap; color: var(--secondary-text-color); }
  .ev-data { font-family: var(--ha-font-family-code, monospace); font-size: 12px; word-break: break-all; }
  .toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); background: var(--primary-text-color); color: var(--primary-background-color);
    padding: 10px 16px; border-radius: 8px; font-size: 14px; z-index: 10; }
  @media (max-width: 800px) {
    .settings { grid-template-columns: 1fr; }
    .sections { flex-direction: row; flex-wrap: wrap; }
    .field.big, .toggle-field.big { grid-template-columns: 1fr; }
    .summary { gap: 8px 20px; padding: 12px 16px 4px; }
    .content { padding: 12px; }
  }
`;

customElements.define("ibox-panel", IboxPanel);
