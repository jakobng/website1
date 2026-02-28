const MAX_CONTEXT_LINES = 4;
const REALTIME_MODE = "realtime";
const REALTIME_PREVIEW_MIN_INTERVAL_MS = 1500;
const REALTIME_PREVIEW_MIN_CHARS = 18;

const VAD_SILENCE_THRESHOLD = 0.012;
const VAD_SILENCE_DURATION_MS = 650;
const VAD_MIN_CHUNK_MS = 3000;
const VAD_MAX_CHUNK_BALANCED = 12000;
const VAD_MAX_CHUNK_LATENCY = 8000;

const OFFLINE_DB_NAME = "ft-offline";
const OFFLINE_DB_VERSION = 1;
const OFFLINE_STORE = "pending-segments";
const HEALTH_CHECK_INTERVAL_MS = 15000;

const els = {
  projectName: document.getElementById("projectName"),
  sourceLang: document.getElementById("sourceLang"),
  targetLang: document.getElementById("targetLang"),
  conversationMode: document.getElementById("conversationMode"),
  conversationContext: document.getElementById("conversationContext"),
  mode: document.getElementById("mode"),
  settingsToggle: document.getElementById("settingsToggle"),
  settingsPanel: document.getElementById("settingsPanel"),
  swapDirectionBtn: document.getElementById("swapDirectionBtn"),
  audioDevice: document.getElementById("audioDevice"),
  ttsEnabled: document.getElementById("ttsEnabled"),
  autoExport: document.getElementById("autoExport"),
  installBtn: document.getElementById("installBtn"),
  startBtn: document.getElementById("startBtn"),
  stopBtn: document.getElementById("stopBtn"),
  status: document.getElementById("status"),
  connDot: document.getElementById("connDot"),
  levelBar: document.getElementById("levelBar"),
  fontDown: document.getElementById("fontDown"),
  fontUp: document.getElementById("fontUp"),
  captionStage: document.getElementById("captionStage"),
  liveCaption: document.getElementById("liveCaption"),
  liveCaptionMirror: document.getElementById("liveCaptionMirror"),
  liveTranscript: document.getElementById("liveTranscript"),
  logList: document.getElementById("logList"),
  exportJsonBtn: document.getElementById("exportJsonBtn"),
  exportCsvBtn: document.getElementById("exportCsvBtn"),
  exportSrtBtn: document.getElementById("exportSrtBtn"),
};

let mediaRecorder;
let mediaStream;
let recorderOptions = {};
let chunkStopTimer;
let captureActive = false;
let sessionId = null;
let sessionStartEpochMs = 0;
let segmentCounter = 0;
let requestQueue = [];
let queueActive = false;
let recentTranslations = [];
let lastChunkEndedAtMs = 0;
let currentChunkMs = 10000;
let activeMode = "balanced";
let activeConversationMode = "single";
let directionSwapped = false;
let deferredInstallPrompt = null;

let rtcPeerConnection = null;
let rtcDataChannel = null;
let rtcPartialTranscript = "";
let rtcLastEndedAtMs = 0;
let rtcCurrentSegmentId = null;
let rtcCurrentSegmentStartMs = 0;
let rtcLastPreviewAtMs = 0;
let rtcLastPreviewTranscript = "";
let realtimeTextQueue = [];
let realtimeTextQueueActive = false;

let audioContext = null;
let analyserNode = null;
let levelAnimFrame = null;
let wakeLockSentinel = null;
let captionFontScale = parseFloat(localStorage.getItem("ft-font-scale") || "1.0");
let connectionHealthy = true;
let healthCheckInterval = null;
let vadCheckInterval = null;
let vadSilenceStartMs = 0;
let chunkStartedAtMs = 0;
let offlineDB = null;

// ── Utility ──────────────────────────────────────────────────────────

function setStatus(msg) {
  els.status.textContent = msg;
}

function setConnHealth(healthy) {
  connectionHealthy = healthy;
  if (els.connDot) {
    els.connDot.className = healthy ? "conn-dot conn-ok" : "conn-dot conn-bad";
  }
}

function setRunningState(running) {
  els.startBtn.disabled = running;
  els.stopBtn.disabled = !running;
}

function setExportState(enabled) {
  els.exportJsonBtn.disabled = !enabled;
  els.exportCsvBtn.disabled = !enabled;
  els.exportSrtBtn.disabled = !enabled;
}

function isStandaloneMode() {
  if (window.matchMedia("(display-mode: standalone)").matches) {
    return true;
  }
  return window.navigator.standalone === true;
}

function updateInstallButton() {
  if (!els.installBtn) {
    return;
  }
  const canInstall = Boolean(deferredInstallPrompt) && !isStandaloneMode();
  els.installBtn.hidden = !canInstall;
  els.installBtn.disabled = !canInstall;
}

async function installApp() {
  if (!deferredInstallPrompt) {
    return;
  }
  const promptEvent = deferredInstallPrompt;
  deferredInstallPrompt = null;
  promptEvent.prompt();
  try {
    await promptEvent.userChoice;
  } finally {
    updateInstallButton();
  }
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  try {
    await navigator.serviceWorker.register("/sw.js");
  } catch (error) {
    console.warn("service worker registration failed", error);
  }
}

function makeSegmentId() {
  segmentCounter += 1;
  return `seg-${segmentCounter.toString().padStart(4, "0")}`;
}

function relMs(nowMs) {
  return Math.max(0, nowMs - sessionStartEpochMs);
}

function guessExtension(mimeType) {
  if (!mimeType) {
    return "webm";
  }
  if (mimeType.includes("ogg")) {
    return "ogg";
  }
  if (mimeType.includes("wav")) {
    return "wav";
  }
  if (mimeType.includes("mp4")) {
    return "m4a";
  }
  return "webm";
}

function chunkMsForMode(mode) {
  return mode === "latency" ? VAD_MAX_CHUNK_LATENCY : VAD_MAX_CHUNK_BALANCED;
}

function isRealtimeMode(mode) {
  return mode === REALTIME_MODE;
}


function getLanguageLabel(code) {
  const normalized = (code || "").trim().toLowerCase();
  const sourceOpt = [...els.sourceLang.options].find((o) => o.value === normalized);
  if (sourceOpt) {
    return sourceOpt.textContent;
  }
  if (!normalized || normalized === "auto") {
    return "Auto detect";
  }
  return normalized;
}

function getDirectionLanguages() {
  const source = els.sourceLang.value.trim() || "auto";
  const target = els.targetLang.value.trim() || "en";
  if (activeConversationMode === "two-way" && directionSwapped) {
    return { sourceLang: target, targetLang: source };
  }
  return { sourceLang: source, targetLang: target };
}

function updateDirectionButton() {
  if (!els.swapDirectionBtn) {
    return;
  }
  const source = els.sourceLang.value.trim() || "auto";
  const target = els.targetLang.value.trim() || "en";
  const canToggle = activeConversationMode === "two-way";
  els.swapDirectionBtn.disabled = !canToggle;
  if (!canToggle) {
    els.swapDirectionBtn.textContent = "Switch Speaker (disabled in one-way mode)";
    return;
  }
  const from = directionSwapped ? getLanguageLabel(target) : getLanguageLabel(source);
  const to = directionSwapped ? getLanguageLabel(source) : getLanguageLabel(target);
  els.swapDirectionBtn.textContent = `Switch Speaker (${from} → ${to})`;
}

function toggleSettingsPanel() {
  if (!els.settingsPanel || !els.settingsToggle) {
    return;
  }
  const opening = els.settingsPanel.classList.contains("settings-collapsed");
  els.settingsPanel.classList.toggle("settings-collapsed", !opening);
  els.settingsPanel.classList.toggle("settings-open", opening);
  els.settingsToggle.textContent = opening ? "Hide Settings" : "Show Settings";
  els.settingsToggle.setAttribute("aria-expanded", opening ? "true" : "false");
}


function setLiveCaptionText(text) {
  if (els.liveCaption) {
    els.liveCaption.textContent = text;
  }
  if (els.liveCaptionMirror) {
    els.liveCaptionMirror.textContent = text;
  }
}

function updateConversationLayout() {
  if (!els.captionStage) {
    return;
  }
  if (activeConversationMode === "two-way") {
    els.captionStage.classList.add("caption-stage-two-way");
  } else {
    els.captionStage.classList.remove("caption-stage-two-way");
  }
}

// ── Audio Device Selection ───────────────────────────────────────────

async function enumerateAudioDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) {
    return;
  }
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter((d) => d.kind === "audioinput");
    const currentValue = els.audioDevice.value;
    els.audioDevice.innerHTML = '<option value="">Default microphone (system selected)</option>';
    audioInputs.forEach((device) => {
      const opt = document.createElement("option");
      opt.value = device.deviceId;
      opt.textContent =
        device.label || `Microphone ${device.deviceId.slice(0, 8)} (unnamed device)`;
      els.audioDevice.appendChild(opt);
    });
    if (
      currentValue &&
      [...els.audioDevice.options].some((o) => o.value === currentValue)
    ) {
      els.audioDevice.value = currentValue;
    }
  } catch (err) {
    console.warn("Failed to enumerate audio devices", err);
  }
}

function isExternalMic(deviceId) {
  if (!deviceId) {
    return false;
  }
  const opt = [...els.audioDevice.options].find((o) => o.value === deviceId);
  if (!opt) {
    return false;
  }
  const label = opt.textContent.toLowerCase();
  return /rode|wireless|usb|external|line.in|audio.interface/i.test(label);
}

function getAudioConstraints() {
  const deviceId = els.audioDevice.value;
  const external = isExternalMic(deviceId);
  const constraints = {
    echoCancellation: !external,
    noiseSuppression: !external,
    autoGainControl: !external,
  };
  if (deviceId) {
    constraints.deviceId = { exact: deviceId };
  }
  return constraints;
}

// ── Audio Level Meter ────────────────────────────────────────────────

function startLevelMeter(stream) {
  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = 256;
    source.connect(analyserNode);

    const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
    function updateLevel() {
      if (!analyserNode) {
        return;
      }
      analyserNode.getByteTimeDomainData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        const v = (dataArray[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / dataArray.length);
      const pct = Math.min(100, rms * 300);
      if (els.levelBar) {
        els.levelBar.style.width = `${pct}%`;
        els.levelBar.className =
          pct > 60
            ? "level-bar level-hot"
            : pct > 20
              ? "level-bar level-warm"
              : "level-bar";
      }
      levelAnimFrame = requestAnimationFrame(updateLevel);
    }
    updateLevel();
  } catch (err) {
    console.warn("Level meter unavailable", err);
  }
}

function stopLevelMeter() {
  if (levelAnimFrame) {
    cancelAnimationFrame(levelAnimFrame);
    levelAnimFrame = null;
  }
  if (audioContext) {
    audioContext.close().catch(() => {});
    audioContext = null;
    analyserNode = null;
  }
  if (els.levelBar) {
    els.levelBar.style.width = "0%";
  }
}

function getCurrentRMS() {
  if (!analyserNode) {
    return 0;
  }
  const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
  analyserNode.getByteTimeDomainData(dataArray);
  let sum = 0;
  for (let i = 0; i < dataArray.length; i++) {
    const v = (dataArray[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / dataArray.length);
}

// ── Wake Lock ────────────────────────────────────────────────────────

async function acquireWakeLock() {
  if (!("wakeLock" in navigator)) {
    return;
  }
  try {
    wakeLockSentinel = await navigator.wakeLock.request("screen");
    wakeLockSentinel.addEventListener("release", () => {
      wakeLockSentinel = null;
      if (captureActive) {
        acquireWakeLock();
      }
    });
  } catch (err) {
    console.warn("Wake lock failed", err);
  }
}

async function releaseWakeLock() {
  if (wakeLockSentinel) {
    try {
      await wakeLockSentinel.release();
    } catch {
      /* already released */
    }
    wakeLockSentinel = null;
  }
}

// ── Connection Health ────────────────────────────────────────────────

async function checkHealth() {
  try {
    const response = await fetch("/health", {
      signal: AbortSignal.timeout(5000),
    });
    setConnHealth(response.ok);
  } catch {
    setConnHealth(false);
  }
}

function startHealthCheck() {
  checkHealth();
  healthCheckInterval = setInterval(checkHealth, HEALTH_CHECK_INTERVAL_MS);
}

function stopHealthCheck() {
  if (healthCheckInterval) {
    clearInterval(healthCheckInterval);
    healthCheckInterval = null;
  }
}

// ── Offline Buffering (IndexedDB) ───────────────────────────────────

function openOfflineDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(OFFLINE_STORE)) {
        db.createObjectStore(OFFLINE_STORE, {
          keyPath: "id",
          autoIncrement: true,
        });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function storeOfflineSegment(segment) {
  try {
    if (!offlineDB) {
      offlineDB = await openOfflineDB();
    }
    const tx = offlineDB.transaction(OFFLINE_STORE, "readwrite");
    const arrayBuffer = await segment.blob.arrayBuffer();
    tx.objectStore(OFFLINE_STORE).add({
      segmentId: segment.segmentId,
      startedAtMs: segment.startedAtMs,
      endedAtMs: segment.endedAtMs,
      audioBuffer: arrayBuffer,
      mimeType: segment.blob.type || "audio/webm",
      sessionId: sessionId,
      sourceLang: getDirectionLanguages().sourceLang,
      targetLang: getDirectionLanguages().targetLang,
      priorContext: recentTranslations.slice(-MAX_CONTEXT_LINES),
      conversationContext: (els.conversationContext.value || "").trim(),
    });
    await new Promise((resolve, reject) => {
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.error("Failed to store offline segment", err);
  }
}

async function drainOfflineSegments() {
  try {
    if (!offlineDB) {
      offlineDB = await openOfflineDB();
    }
    const tx = offlineDB.transaction(OFFLINE_STORE, "readonly");
    const objectStore = tx.objectStore(OFFLINE_STORE);
    const all = await new Promise((resolve, reject) => {
      const req = objectStore.getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });

    if (!all.length) {
      return;
    }
    setStatus(`Uploading ${all.length} buffered segment(s)...`);

    for (const item of all) {
      try {
        const blob = new Blob([item.audioBuffer], { type: item.mimeType });
        const formData = new FormData();
        formData.set("session_id", item.sessionId);
        formData.set("segment_id", item.segmentId);
        formData.set("started_at_ms", String(item.startedAtMs));
        formData.set("ended_at_ms", String(item.endedAtMs));
        formData.set("source_lang_hint", item.sourceLang);
        formData.set("target_lang", item.targetLang);
        formData.set("prior_context_json", JSON.stringify(item.priorContext));
        formData.set("conversation_context", item.conversationContext);
        const ext = guessExtension(item.mimeType);
        formData.set("audio_file", blob, `${item.segmentId}.${ext}`);

        const response = await fetch("/v1/segment/process", {
          method: "POST",
          body: formData,
        });
        if (response.ok) {
          const delTx = offlineDB.transaction(OFFLINE_STORE, "readwrite");
          delTx.objectStore(OFFLINE_STORE).delete(item.id);
        }
      } catch {
        break;
      }
    }
  } catch (err) {
    console.warn("Failed to drain offline segments", err);
  }
}

// ── TTS ──────────────────────────────────────────────────────────────

function speakTranslation(text) {
  if (!els.ttsEnabled.checked || !window.speechSynthesis) {
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.1;
  utterance.lang = getDirectionLanguages().targetLang;
  window.speechSynthesis.speak(utterance);
}

// ── Font Size ────────────────────────────────────────────────────────

function applyFontScale() {
  const size = `clamp(1rem, ${3.6 * captionFontScale}vw, ${2.1 * captionFontScale}rem)`;
  els.liveCaption.style.fontSize = size;
  localStorage.setItem("ft-font-scale", String(captionFontScale));
}

function adjustFontSize(delta) {
  captionFontScale = Math.max(0.6, Math.min(2.0, captionFontScale + delta));
  applyFontScale();
}

// ── Session Resume ───────────────────────────────────────────────────

function saveSessionState() {
  if (!sessionId) {
    return;
  }
  localStorage.setItem(
    "ft-session",
    JSON.stringify({
      sessionId,
      activeMode,
      sessionStartEpochMs,
      segmentCounter,
      recentTranslations,
    }),
  );
}

function clearSessionState() {
  localStorage.removeItem("ft-session");
}

function checkSessionResume() {
  const saved = localStorage.getItem("ft-session");
  if (!saved) {
    return;
  }
  setTimeout(() => {
    try {
      const state = JSON.parse(saved);
      if (!state.sessionId) {
        return;
      }
      const resume = confirm(
        `A previous session (${state.sessionId.slice(0, 8)}...) was interrupted. Resume it?\n\nPress Cancel to start fresh.`,
      );
      if (resume) {
        sessionId = state.sessionId;
        activeMode = state.activeMode || "balanced";
        sessionStartEpochMs = state.sessionStartEpochMs || Date.now();
        segmentCounter = state.segmentCounter || 0;
        recentTranslations = state.recentTranslations || [];
        currentChunkMs = chunkMsForMode(activeMode);
        setExportState(true);
        setStatus(
          `Resumed session ${sessionId.slice(0, 8)}... Press Start to continue capturing.`,
        );
      } else {
        clearSessionState();
      }
    } catch {
      clearSessionState();
    }
  }, 500);
}

// ── Auto Export ──────────────────────────────────────────────────────

async function autoExportSession() {
  if (!els.autoExport.checked || !sessionId) {
    return;
  }
  try {
    const response = await fetch(
      `/v1/session/${sessionId}/export?format=json`,
    );
    if (!response.ok) {
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `session-${sessionId.slice(0, 8)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    console.warn("Auto-export failed", err);
  }
}

// ── Log Entries ──────────────────────────────────────────────────────

function addLogEntry({ startedAtMs, translation, transcript }) {
  const entry = document.createElement("div");
  entry.className = "log-item";

  const ts = document.createElement("div");
  ts.className = "log-time";
  ts.textContent = `t=${(startedAtMs / 1000).toFixed(1)}s`;

  const en = document.createElement("div");
  en.className = "log-en";
  en.textContent = translation;

  const src = document.createElement("div");
  src.className = "log-src";
  src.textContent = transcript;

  entry.append(ts, en, src);
  els.logList.prepend(entry);
}

// ── Network Requests ─────────────────────────────────────────────────

async function postSegment(segment) {
  const formData = new FormData();
  formData.set("session_id", sessionId);
  formData.set("segment_id", segment.segmentId);
  formData.set("started_at_ms", String(segment.startedAtMs));
  formData.set("ended_at_ms", String(segment.endedAtMs));
  const direction = getDirectionLanguages();
  formData.set("source_lang_hint", direction.sourceLang);
  formData.set("target_lang", direction.targetLang);
  formData.set(
    "prior_context_json",
    JSON.stringify(recentTranslations.slice(-MAX_CONTEXT_LINES)),
  );
  formData.set(
    "conversation_context",
    (els.conversationContext.value || "").trim(),
  );

  const ext = guessExtension(segment.blob.type || "audio/webm");
  formData.set("audio_file", segment.blob, `${segment.segmentId}.${ext}`);

  const response = await fetch("/v1/segment/process", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`segment failed ${response.status}: ${text}`);
  }

  return response.json();
}

async function postTranslatedText({
  segmentId,
  transcript,
  startedAtMs,
  endedAtMs,
  isFinal,
}) {
  const response = await fetch("/v1/text/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      segment_id: segmentId,
      transcript_src: transcript,
      started_at_ms: startedAtMs,
      ended_at_ms: endedAtMs,
      is_final: isFinal,
      prior_context_json: recentTranslations.slice(-MAX_CONTEXT_LINES),
      source_lang_hint: getDirectionLanguages().sourceLang || "auto",
      target_lang: getDirectionLanguages().targetLang || "en",
      conversation_context: (els.conversationContext.value || "").trim(),
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`translate failed ${response.status}: ${text}`);
  }

  return response.json();
}

// ── Realtime Text Queue ──────────────────────────────────────────────

async function drainRealtimeTextQueue() {
  if (realtimeTextQueueActive) {
    return;
  }

  realtimeTextQueueActive = true;
  while (realtimeTextQueue.length) {
    const next = realtimeTextQueue.shift();
    try {
      const translated = await postTranslatedText(next);
      setLiveCaptionText(translated.translation_en || "...");
      if (next.isFinal) {
        recentTranslations.push(translated.translation_en);
        recentTranslations = recentTranslations.slice(-MAX_CONTEXT_LINES);
        addLogEntry({
          startedAtMs: next.startedAtMs,
          translation: translated.translation_en,
          transcript: next.transcript,
        });
        speakTranslation(translated.translation_en);
        saveSessionState();
        setStatus(
          `Live realtime | final translation latency ${translated.latency_ms}ms`,
        );
      } else {
        setStatus(
          `Live realtime | rolling translation latency ${translated.latency_ms}ms`,
        );
      }
    } catch (translateError) {
      console.error(translateError);
      setStatus(`Realtime translate error: ${translateError.message}`);
    }
  }
  realtimeTextQueueActive = false;
}

// ── Chunk Queue ──────────────────────────────────────────────────────

async function drainQueue() {
  if (queueActive) {
    return;
  }

  queueActive = true;
  while (requestQueue.length) {
    const next = requestQueue.shift();
    try {
      const result = await postSegment(next);
      recentTranslations.push(result.translation_en);
      recentTranslations = recentTranslations.slice(-MAX_CONTEXT_LINES);

      setLiveCaptionText(result.translation_en || "...");
      els.liveTranscript.textContent = result.transcript_src || "";
      addLogEntry({
        startedAtMs: next.startedAtMs,
        translation: result.translation_en,
        transcript: result.transcript_src,
      });
      speakTranslation(result.translation_en);
      saveSessionState();

      setStatus(
        `Live | queue ${requestQueue.length} | segment latency ${result.latency_ms}ms`,
      );
    } catch (error) {
      if (!navigator.onLine) {
        setStatus("Offline - buffering segment locally");
        await storeOfflineSegment(next);
      } else {
        console.error(error);
        setStatus(`Error: ${error.message}`);
      }
    }
  }
  queueActive = false;
}

function enqueueChunk(blob) {
  if (!sessionId || !blob || blob.size === 0) {
    return;
  }

  const endedAtMs = relMs(Date.now());
  const startedAtMs = lastChunkEndedAtMs;
  lastChunkEndedAtMs = endedAtMs;

  requestQueue.push({
    segmentId: makeSegmentId(),
    startedAtMs: Math.max(0, startedAtMs),
    endedAtMs: Math.max(endedAtMs, startedAtMs + 1),
    blob,
  });

  drainQueue();
}

// ── VAD-based Chunking ───────────────────────────────────────────────

function startVadMonitor() {
  chunkStartedAtMs = Date.now();
  vadSilenceStartMs = 0;
  const maxMs = chunkMsForMode(activeMode);

  vadCheckInterval = setInterval(() => {
    const elapsed = Date.now() - chunkStartedAtMs;
    const rms = getCurrentRMS();
    const isSilent = rms < VAD_SILENCE_THRESHOLD;

    if (isSilent) {
      if (!vadSilenceStartMs) {
        vadSilenceStartMs = Date.now();
      }
      const silenceDuration = Date.now() - vadSilenceStartMs;
      if (elapsed >= VAD_MIN_CHUNK_MS && silenceDuration >= VAD_SILENCE_DURATION_MS) {
        stopCurrentChunk();
        return;
      }
    } else {
      vadSilenceStartMs = 0;
    }

    if (elapsed >= maxMs) {
      stopCurrentChunk();
    }
  }, 80);
}

function stopVadMonitor() {
  if (vadCheckInterval) {
    clearInterval(vadCheckInterval);
    vadCheckInterval = null;
  }
}

function stopCurrentChunk() {
  stopVadMonitor();
  if (chunkStopTimer) {
    clearTimeout(chunkStopTimer);
    chunkStopTimer = null;
  }
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
}

function startChunkedRecorderCycle() {
  if (!captureActive || !mediaStream) {
    return;
  }

  mediaRecorder = new MediaRecorder(mediaStream, recorderOptions);
  const parts = [];

  mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      parts.push(event.data);
    }
  };

  mediaRecorder.onerror = (event) => {
    setStatus(`Recorder error: ${event.error?.message || "unknown"}`);
  };

  mediaRecorder.onstop = () => {
    stopVadMonitor();
    if (parts.length > 0) {
      const mimeType =
        mediaRecorder?.mimeType || parts[0].type || "audio/webm";
      const blob = new Blob(parts, { type: mimeType });
      enqueueChunk(blob);
    }

    if (captureActive) {
      startChunkedRecorderCycle();
    }
  };

  mediaRecorder.start();

  if (analyserNode) {
    startVadMonitor();
  } else {
    chunkStopTimer = setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
      }
    }, chunkMsForMode(activeMode));
  }
}

// ── Realtime (WebRTC) ────────────────────────────────────────────────

function configureRtcDataChannel(dataChannel) {
  dataChannel.onmessage = async (event) => {
    try {
      const payload = JSON.parse(event.data);
      const eventType = payload?.type || "";

      if (eventType === "conversation.item.input_audio_transcription.delta") {
        const delta = payload?.delta || "";
        if (delta) {
          rtcPartialTranscript += delta;
          els.liveTranscript.textContent = rtcPartialTranscript;

          const nowMs = relMs(Date.now());
          const sinceLastPreview = nowMs - rtcLastPreviewAtMs;
          const transcriptChanged =
            rtcPartialTranscript !== rtcLastPreviewTranscript;
          if (
            transcriptChanged &&
            rtcPartialTranscript.trim().length >= REALTIME_PREVIEW_MIN_CHARS &&
            sinceLastPreview >= REALTIME_PREVIEW_MIN_INTERVAL_MS &&
            rtcCurrentSegmentId
          ) {
            rtcLastPreviewAtMs = nowMs;
            rtcLastPreviewTranscript = rtcPartialTranscript;
            realtimeTextQueue.push({
              segmentId: rtcCurrentSegmentId,
              transcript: rtcPartialTranscript,
              startedAtMs: rtcCurrentSegmentStartMs,
              endedAtMs: Math.max(nowMs, rtcCurrentSegmentStartMs + 1),
              isFinal: false,
            });
            drainRealtimeTextQueue();
          }
        }
        return;
      }

      if (
        eventType ===
        "conversation.item.input_audio_transcription.completed"
      ) {
        const finalText = (payload?.transcript || "").trim();
        rtcPartialTranscript = "";
        if (!finalText) {
          return;
        }

        const endedAtMs = relMs(Date.now());
        const startedAtMs = rtcCurrentSegmentStartMs;
        rtcLastEndedAtMs = endedAtMs;

        els.liveTranscript.textContent = finalText;

        if (!rtcCurrentSegmentId) {
          rtcCurrentSegmentId = makeSegmentId();
        }
        realtimeTextQueue.push({
          segmentId: rtcCurrentSegmentId,
          transcript: finalText,
          startedAtMs: Math.max(0, startedAtMs),
          endedAtMs: Math.max(endedAtMs, startedAtMs + 1),
          isFinal: true,
        });
        rtcCurrentSegmentStartMs = endedAtMs;
        rtcCurrentSegmentId = makeSegmentId();
        rtcLastPreviewTranscript = "";
        rtcLastPreviewAtMs = endedAtMs;
        drainRealtimeTextQueue();
        return;
      }

      if (eventType === "error") {
        const message =
          payload?.error?.message || payload?.message || "Realtime error";
        setStatus(`Realtime error: ${message}`);
      }
    } catch (parseError) {
      console.error(parseError);
    }
  };

  dataChannel.onopen = () => {
    setStatus("Realtime connected. Listening...");
  };

  dataChannel.onclose = () => {
    if (captureActive) {
      setStatus("Realtime connection closed.");
    }
  };
}

function waitForIceGatheringComplete(peerConnection, timeoutMs = 1500) {
  if (peerConnection.iceGatheringState === "complete") {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) {
        return;
      }
      settled = true;
      peerConnection.removeEventListener(
        "icegatheringstatechange",
        onStateChange,
      );
      resolve();
    };
    const onStateChange = () => {
      if (peerConnection.iceGatheringState === "complete") {
        finish();
      }
    };
    peerConnection.addEventListener("icegatheringstatechange", onStateChange);
    setTimeout(finish, timeoutMs);
  });
}

async function startRealtimeCapture() {
  if (!window.RTCPeerConnection) {
    throw new Error("Browser does not support WebRTC realtime mode");
  }

  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: getAudioConstraints(),
  });

  if (!mediaStream.getAudioTracks().length) {
    throw new Error("No audio track available for realtime mode");
  }

  startLevelMeter(mediaStream);

  rtcPeerConnection = new RTCPeerConnection();
  mediaStream.getTracks().forEach((track) => {
    rtcPeerConnection.addTrack(track, mediaStream);
  });

  rtcDataChannel = rtcPeerConnection.createDataChannel("oai-events");
  configureRtcDataChannel(rtcDataChannel);

  rtcPeerConnection.ondatachannel = (event) => {
    configureRtcDataChannel(event.channel);
  };

  const offer = await rtcPeerConnection.createOffer();
  await rtcPeerConnection.setLocalDescription(offer);
  await waitForIceGatheringComplete(rtcPeerConnection);

  const localOfferSdp = rtcPeerConnection.localDescription?.sdp || "";
  if (!localOfferSdp.trim() || !localOfferSdp.includes("m=audio")) {
    throw new Error("Failed to build a valid realtime audio offer");
  }

  const response = await fetch("/v1/realtime/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      offer_sdp: localOfferSdp,
      source_lang_hint: getDirectionLanguages().sourceLang || "auto",
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`realtime connect failed ${response.status}: ${text}`);
  }

  const answerSdp = await response.text();
  if (!answerSdp.includes("v=0") || !answerSdp.includes("m=audio")) {
    throw new Error(`realtime answer invalid: ${answerSdp.slice(0, 180)}`);
  }
  await rtcPeerConnection.setRemoteDescription({
    type: "answer",
    sdp: answerSdp,
  });

  captureActive = true;
  rtcCurrentSegmentStartMs = rtcLastEndedAtMs;
  if (!rtcCurrentSegmentId) {
    rtcCurrentSegmentId = makeSegmentId();
  }
}

// ── Audio Capture Start/Stop ─────────────────────────────────────────

async function startAudioCapture(mode) {
  if (isRealtimeMode(mode)) {
    await startRealtimeCapture();
    return;
  }

  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: getAudioConstraints(),
  });

  startLevelMeter(mediaStream);

  const supportedMimeTypes = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
  ];

  recorderOptions = {};
  for (const mimeType of supportedMimeTypes) {
    if (MediaRecorder.isTypeSupported(mimeType)) {
      recorderOptions.mimeType = mimeType;
      break;
    }
  }

  captureActive = true;
  startChunkedRecorderCycle();
}

async function stopAudioCapture() {
  captureActive = false;
  stopVadMonitor();
  if (chunkStopTimer) {
    clearTimeout(chunkStopTimer);
    chunkStopTimer = null;
  }

  stopLevelMeter();

  if (rtcDataChannel) {
    rtcDataChannel.close();
    rtcDataChannel = null;
  }

  if (rtcPeerConnection) {
    rtcPeerConnection.getSenders().forEach((sender) => {
      if (sender.track) {
        sender.track.stop();
      }
    });
    rtcPeerConnection.close();
    rtcPeerConnection = null;
  }

  if (!mediaRecorder) {
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
    return;
  }

  const recorder = mediaRecorder;
  const stopPromise =
    recorder.state === "inactive"
      ? Promise.resolve()
      : new Promise((resolve) => {
          recorder.addEventListener("stop", resolve, { once: true });
        });

  if (recorder.state !== "inactive") {
    recorder.stop();
  }

  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
  }

  await Promise.race([
    stopPromise,
    new Promise((resolve) => setTimeout(resolve, 1000)),
  ]);

  mediaRecorder = null;
  mediaStream = null;
  recorderOptions = {};
}

// ── Session Lifecycle ────────────────────────────────────────────────

async function startSession() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("This browser does not support microphone capture.");
    return;
  }

  setStatus("Starting session...");
  try {
    const response = await fetch("/v1/session/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_name: els.projectName.value.trim() || "untitled-shoot",
        source_lang_hint: getDirectionLanguages().sourceLang || "auto",
        target_lang: getDirectionLanguages().targetLang || "en",
        mode: els.mode.value.trim() || "balanced",
      }),
    });

    if (!response.ok) {
      throw new Error(`session start failed (${response.status})`);
    }

    const payload = await response.json();
    sessionId = payload.session_id;
    activeMode = els.mode.value.trim() || "balanced";
    activeConversationMode = els.conversationMode.value.trim() || "single";
    directionSwapped = false;
    updateDirectionButton();
    updateConversationLayout();
    currentChunkMs = chunkMsForMode(activeMode);
    sessionStartEpochMs = Date.now();
    lastChunkEndedAtMs = 0;
    rtcLastEndedAtMs = 0;
    rtcPartialTranscript = "";
    rtcCurrentSegmentId = null;
    rtcCurrentSegmentStartMs = 0;
    rtcLastPreviewAtMs = 0;
    rtcLastPreviewTranscript = "";
    segmentCounter = 0;
    requestQueue = [];
    recentTranslations = [];
    realtimeTextQueue = [];
    realtimeTextQueueActive = false;
    els.logList.innerHTML = "";

    await startAudioCapture(activeMode);
    await acquireWakeLock();
    saveSessionState();
    startHealthCheck();

    setRunningState(true);
    setExportState(true);
    if (isRealtimeMode(activeMode)) {
      setStatus(`Live session ${sessionId.slice(0, 8)}... fast mode`);
    } else {
      setStatus(
        `Live session ${sessionId.slice(0, 8)}... VAD chunking (max ${(currentChunkMs / 1000).toFixed(0)}s)`,
      );
    }
    const direction = getDirectionLanguages();
    setLiveCaptionText(`Listening (${getLanguageLabel(direction.sourceLang)} → ${getLanguageLabel(direction.targetLang)})...`);
    els.liveTranscript.textContent = "";
  } catch (error) {
    console.error(error);
    setStatus(`Failed to start: ${error.message}`);
    await stopAudioCapture();
    await releaseWakeLock();
    sessionId = null;
    setRunningState(false);
  }
}

async function stopSession() {
  if (!sessionId) {
    return;
  }

  setStatus("Stopping session...");

  await stopAudioCapture();
  await releaseWakeLock();
  stopHealthCheck();

  while (
    queueActive ||
    requestQueue.length ||
    realtimeTextQueueActive ||
    realtimeTextQueue.length
  ) {
    await new Promise((resolve) => setTimeout(resolve, 150));
  }

  try {
    const response = await fetch("/v1/session/end", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });

    if (!response.ok) {
      throw new Error(`session end failed (${response.status})`);
    }

    const payload = await response.json();
    setStatus(
      `Ended | duration ${(payload.duration_ms / 1000).toFixed(1)}s | segments ${payload.segments_count}`,
    );

    await autoExportSession();
  } catch (error) {
    console.error(error);
    setStatus(`Failed to end cleanly: ${error.message}`);
  }

  clearSessionState();
  setRunningState(false);
}

function openExport(format) {
  if (!sessionId) {
    return;
  }
  window.open(`/v1/session/${sessionId}/export?format=${format}`, "_blank");
}



function swapConversationDirection() {
  if (activeConversationMode !== "two-way") {
    return;
  }
  directionSwapped = !directionSwapped;
  updateDirectionButton();
  const direction = getDirectionLanguages();
  setStatus(`Direction switched: ${getLanguageLabel(direction.sourceLang)} → ${getLanguageLabel(direction.targetLang)}`);
}
// ── Event Listeners ──────────────────────────────────────────────────

els.startBtn.addEventListener("click", startSession);
els.stopBtn.addEventListener("click", stopSession);
els.exportJsonBtn.addEventListener("click", () => openExport("json"));
els.exportCsvBtn.addEventListener("click", () => openExport("csv"));
els.exportSrtBtn.addEventListener("click", () => openExport("srt"));
if (els.installBtn) {
  els.installBtn.addEventListener("click", installApp);
}
if (els.settingsToggle) {
  els.settingsToggle.addEventListener("click", toggleSettingsPanel);
}
if (els.conversationMode) {
  els.conversationMode.addEventListener("change", () => {
    activeConversationMode = els.conversationMode.value.trim() || "single";
    directionSwapped = false;
    updateDirectionButton();
    updateConversationLayout();
  });
}
if (els.sourceLang) {
  els.sourceLang.addEventListener("change", updateDirectionButton);
}
if (els.targetLang) {
  els.targetLang.addEventListener("input", updateDirectionButton);
}
if (els.swapDirectionBtn) {
  els.swapDirectionBtn.addEventListener("click", swapConversationDirection);
}
if (els.fontDown) {
  els.fontDown.addEventListener("click", () => adjustFontSize(-0.15));
}
if (els.fontUp) {
  els.fontUp.addEventListener("click", () => adjustFontSize(0.15));
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  updateInstallButton();
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  updateInstallButton();
  setStatus("Installed. You can launch from your Android home screen.");
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && captureActive) {
    acquireWakeLock();
  }
});

if (navigator.mediaDevices) {
  navigator.mediaDevices.addEventListener("devicechange", enumerateAudioDevices);
}

window.addEventListener("online", () => {
  setConnHealth(true);
  drainOfflineSegments();
});

window.addEventListener("offline", () => {
  setConnHealth(false);
});

// ── Init ─────────────────────────────────────────────────────────────

setRunningState(false);
setExportState(false);
updateInstallButton();
applyFontScale();
registerServiceWorker();
enumerateAudioDevices();
checkSessionResume();
updateDirectionButton();
updateConversationLayout();

(async () => {
  try {
    const tempStream = await navigator.mediaDevices.getUserMedia({
      audio: true,
    });
    tempStream.getTracks().forEach((t) => t.stop());
    await enumerateAudioDevices();
  } catch {
    /* permission denied or unavailable - device list will show generic labels */
  }
})();
