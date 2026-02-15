const MAX_CONTEXT_LINES = 4;
const REALTIME_MODE = "realtime";

const els = {
  projectName: document.getElementById("projectName"),
  sourceLang: document.getElementById("sourceLang"),
  targetLang: document.getElementById("targetLang"),
  conversationContext: document.getElementById("conversationContext"),
  mode: document.getElementById("mode"),
  installBtn: document.getElementById("installBtn"),
  startBtn: document.getElementById("startBtn"),
  stopBtn: document.getElementById("stopBtn"),
  status: document.getElementById("status"),
  liveCaption: document.getElementById("liveCaption"),
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
let deferredInstallPrompt = null;

let rtcPeerConnection = null;
let rtcDataChannel = null;
let rtcPartialTranscript = "";
let rtcLastEndedAtMs = 0;
let realtimeTextQueue = [];
let realtimeTextQueueActive = false;

function setStatus(msg) {
  els.status.textContent = msg;
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
  if (mode === "latency") {
    return 5000;
  }
  if (mode === "accuracy") {
    return 12000;
  }
  return 8000;
}

function isRealtimeMode(mode) {
  return mode === REALTIME_MODE;
}

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

async function postSegment(segment) {
  const formData = new FormData();
  formData.set("session_id", sessionId);
  formData.set("segment_id", segment.segmentId);
  formData.set("started_at_ms", String(segment.startedAtMs));
  formData.set("ended_at_ms", String(segment.endedAtMs));
  formData.set("source_lang_hint", els.sourceLang.value.trim());
  formData.set("target_lang", els.targetLang.value.trim() || "en");
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
      prior_context_json: recentTranslations.slice(-MAX_CONTEXT_LINES),
      source_lang_hint: els.sourceLang.value.trim() || "auto",
      target_lang: els.targetLang.value.trim() || "en",
      conversation_context: (els.conversationContext.value || "").trim(),
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`translate failed ${response.status}: ${text}`);
  }

  return response.json();
}

async function drainRealtimeTextQueue() {
  if (realtimeTextQueueActive) {
    return;
  }

  realtimeTextQueueActive = true;
  while (realtimeTextQueue.length) {
    const next = realtimeTextQueue.shift();
    try {
      const translated = await postTranslatedText(next);

      recentTranslations.push(translated.translation_en);
      recentTranslations = recentTranslations.slice(-MAX_CONTEXT_LINES);

      els.liveCaption.textContent = translated.translation_en || "...";
      addLogEntry({
        startedAtMs: next.startedAtMs,
        translation: translated.translation_en,
        transcript: next.transcript,
      });
      setStatus(`Live realtime | translation latency ${translated.latency_ms}ms`);
    } catch (translateError) {
      console.error(translateError);
      setStatus(`Realtime translate error: ${translateError.message}`);
    }
  }
  realtimeTextQueueActive = false;
}

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

      els.liveCaption.textContent = result.translation_en || "...";
      els.liveTranscript.textContent = result.transcript_src || "";
      addLogEntry({
        startedAtMs: next.startedAtMs,
        translation: result.translation_en,
        transcript: result.transcript_src,
      });

      setStatus(
        `Live | queue ${requestQueue.length} | segment latency ${result.latency_ms}ms`,
      );
    } catch (error) {
      console.error(error);
      setStatus(`Error: ${error.message}`);
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
  chunkStopTimer = setTimeout(() => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  }, currentChunkMs);
}

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
        }
        return;
      }

      if (eventType === "conversation.item.input_audio_transcription.completed") {
        const finalText = (payload?.transcript || "").trim();
        rtcPartialTranscript = "";
        if (!finalText) {
          return;
        }

        const endedAtMs = relMs(Date.now());
        const startedAtMs = rtcLastEndedAtMs;
        rtcLastEndedAtMs = endedAtMs;

        els.liveTranscript.textContent = finalText;

        realtimeTextQueue.push({
          segmentId: makeSegmentId(),
          transcript: finalText,
          startedAtMs: Math.max(0, startedAtMs),
          endedAtMs: Math.max(endedAtMs, startedAtMs + 1),
        });
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
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  if (!mediaStream.getAudioTracks().length) {
    throw new Error("No audio track available for realtime mode");
  }

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
      source_lang_hint: els.sourceLang.value.trim() || "auto",
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`realtime connect failed ${response.status}: ${text}`);
  }

  const payload = await response.json();
  await rtcPeerConnection.setRemoteDescription({
    type: "answer",
    sdp: payload.answer_sdp,
  });

  captureActive = true;
}

async function startAudioCapture(mode) {
  if (isRealtimeMode(mode)) {
    await startRealtimeCapture();
    return;
  }

  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

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
  if (chunkStopTimer) {
    clearTimeout(chunkStopTimer);
    chunkStopTimer = null;
  }

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
        source_lang_hint: els.sourceLang.value.trim() || "auto",
        target_lang: els.targetLang.value.trim() || "en",
        mode: els.mode.value.trim() || "balanced",
      }),
    });

    if (!response.ok) {
      throw new Error(`session start failed (${response.status})`);
    }

    const payload = await response.json();
    sessionId = payload.session_id;
    activeMode = els.mode.value.trim() || "balanced";
    currentChunkMs = chunkMsForMode(activeMode);
    sessionStartEpochMs = Date.now();
    lastChunkEndedAtMs = 0;
    rtcLastEndedAtMs = 0;
    rtcPartialTranscript = "";
    segmentCounter = 0;
    requestQueue = [];
    recentTranslations = [];
    realtimeTextQueue = [];
    realtimeTextQueueActive = false;
    els.logList.innerHTML = "";

    await startAudioCapture(activeMode);

    setRunningState(true);
    setExportState(true);
    if (isRealtimeMode(activeMode)) {
      setStatus(`Live session ${sessionId.slice(0, 8)}... realtime WebRTC`);
    } else {
      setStatus(
        `Live session ${sessionId.slice(0, 8)}... chunk ${(currentChunkMs / 1000).toFixed(1)}s`,
      );
    }
    els.liveCaption.textContent = "Listening...";
    els.liveTranscript.textContent = "";
  } catch (error) {
    console.error(error);
    setStatus(`Failed to start: ${error.message}`);
    await stopAudioCapture();
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
  } catch (error) {
    console.error(error);
    setStatus(`Failed to end cleanly: ${error.message}`);
  }

  setRunningState(false);
}

function openExport(format) {
  if (!sessionId) {
    return;
  }
  window.open(`/v1/session/${sessionId}/export?format=${format}`, "_blank");
}

els.startBtn.addEventListener("click", startSession);
els.stopBtn.addEventListener("click", stopSession);
els.exportJsonBtn.addEventListener("click", () => openExport("json"));
els.exportCsvBtn.addEventListener("click", () => openExport("csv"));
els.exportSrtBtn.addEventListener("click", () => openExport("srt"));
if (els.installBtn) {
  els.installBtn.addEventListener("click", installApp);
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

setRunningState(false);
setExportState(false);
updateInstallButton();
registerServiceWorker();
