"use strict";

const chat = document.getElementById("chat");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const send = document.getElementById("send");
const status = document.getElementById("status");
const systemBubble = chat.querySelector(".bubble.system pre");
const transcript = document.getElementById("transcript");
const voiceStatus = document.getElementById("voice-status");
const mic = document.getElementById("mic");
const stopSpeech = document.getElementById("stop-speech");
const spokenReplies = document.getElementById("spoken-replies");
const memoryPanel = document.getElementById("memory-panel");
const memoryList = document.getElementById("memory-list");
const memorySearch = document.getElementById("memory-search");

let conversationId = null;
let busy = false;
let pending = null;
let recognition = null;
let listening = false;
let memoryOpen = true;
let pairingToken = localStorage.getItem("vamsi_pairing_token") || "";
const AndroidVoice = window.VamsiAndroidVoice || null;
let usingAndroidVoice = false;
let recorderState = null;

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const params = new URLSearchParams(window.location.search);
const urlPairingToken = params.get("pair");
if (urlPairingToken) {
  pairingToken = urlPairingToken;
  localStorage.setItem("vamsi_pairing_token", pairingToken);
  params.delete("pair");
  const cleanQuery = params.toString();
  const cleanUrl = window.location.pathname + (cleanQuery ? `?${cleanQuery}` : "");
  window.history.replaceState({}, "", cleanUrl);
}

document.getElementById("toggle-memory").addEventListener("click", () => {
  memoryOpen = !memoryOpen;
  memoryPanel.classList.toggle("closed", !memoryOpen);
});

document.getElementById("refresh-memory").addEventListener("click", () => loadMemory());
memorySearch.addEventListener("input", () => loadMemory(memorySearch.value.trim()));

document.getElementById("new-chat").addEventListener("click", () => {
  if (busy) return;
  stopSpeaking();
  stopListening();
  conversationId = null;
  pending = null;
  chat.replaceChildren();
  addBubble("New conversation. Saved notes are still available.", "system");
});

function addBubble(text, cls, metaText) {
  const div = document.createElement("div");
  div.className = `bubble ${cls}`;
  div.textContent = text;
  if (metaText) {
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = metaText;
    div.appendChild(meta);
  }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function setBusy(nextBusy) {
  busy = nextBusy;
  send.disabled = nextBusy;
  mic.disabled = nextBusy;
  send.textContent = nextBusy ? "Working..." : "Send";
  status.textContent = nextBusy ? "thinking..." : "";
}

async function readJsonResponse(res) {
  const data = await res.json().catch(() => ({ ok: false, error: "invalid server response" }));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || data.reply || "request failed");
  }
  return data;
}

function apiHeaders(extra = {}) {
  return pairingToken ? { ...extra, "X-Vamsi-Pairing-Token": pairingToken } : extra;
}

async function postChat(message) {
  const body = pending && pending.message === message ? pending : {
    message,
    conversation_id: conversationId,
    request_id: crypto.randomUUID(),
  };
  pending = body;
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  const data = await readJsonResponse(res);
  if (data.conversation_id) {
    conversationId = data.conversation_id;
  }
  pending = null;
  return data;
}

async function sendMessage(message) {
  if (!message || busy) return;
  stopSpeaking();
  setBusy(true);
  input.value = "";
  transcript.value = "";
  addBubble(message, "user");
  const thinking = addBubble("", "assistant thinking");
  try {
    const data = await postChat(message);
    thinking.classList.remove("thinking");
    thinking.textContent = data.reply || "(no reply)";
    if (data.tool_calls && data.tool_calls.length) {
      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent = "tools: " + data.tool_calls.map((t) => t.tool).join(", ");
      thinking.appendChild(meta);
      await loadMemory(memorySearch.value.trim());
    }
    status.textContent = (data.seconds ?? 0).toFixed(1) + "s";
    setTimeout(() => (status.textContent = ""), 4000);
    speak(data.reply || "");
  } catch (err) {
    thinking.classList.remove("thinking");
    thinking.classList.add("error");
    thinking.textContent = err.message;
    input.value = message;
  } finally {
    setBusy(false);
    input.focus();
  }
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  await sendMessage(input.value.trim());
});

transcript.addEventListener("input", () => {
  input.value = transcript.value;
});

async function loadMemory(query = "") {
  const suffix = query ? `?q=${encodeURIComponent(query)}` : "";
  memoryList.textContent = "Loading...";
  try {
    const res = await fetch("/api/notes" + suffix, { headers: apiHeaders() });
    const data = await readJsonResponse(res);
    renderMemory(data.notes || []);
  } catch (err) {
    memoryList.textContent = "Could not load memory: " + err.message;
  }
}

function renderMemory(notes) {
  memoryList.replaceChildren();
  if (!notes.length) {
    const empty = document.createElement("p");
    empty.className = "empty-memory";
    empty.textContent = "No saved memories found.";
    memoryList.appendChild(empty);
    return;
  }
  for (const note of notes) {
    const card = document.createElement("article");
    card.className = "memory-card";
    const title = document.createElement("input");
    title.value = note.title || "";
    title.placeholder = "Title";
    title.maxLength = 200;
    const content = document.createElement("textarea");
    content.value = note.content;
    content.rows = 3;
    content.maxLength = 4000;
    const meta = document.createElement("p");
    meta.className = "memory-meta";
    meta.textContent = `note ${note.id} - ${new Date(note.updated_at).toLocaleString()}`;
    const actions = document.createElement("div");
    actions.className = "memory-actions";
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = "Save";
    saveBtn.addEventListener("click", () => updateNote(note.id, title.value, content.value));
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.className = "danger";
    deleteBtn.addEventListener("click", () => deleteNote(note.id));
    actions.append(saveBtn, deleteBtn);
    card.append(title, content, meta, actions);
    memoryList.appendChild(card);
  }
}

async function updateNote(id, title, content) {
  try {
    const res = await fetch(`/api/notes/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ title, content }),
    });
    await readJsonResponse(res);
    status.textContent = "memory updated";
    await loadMemory(memorySearch.value.trim());
  } catch (err) {
    status.textContent = "memory update failed";
    addBubble(err.message, "error");
  }
}

async function deleteNote(id) {
  if (!confirm("Delete this saved memory?")) return;
  try {
    const res = await fetch(`/api/notes/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: apiHeaders(),
    });
    await readJsonResponse(res);
    status.textContent = "memory deleted";
    await loadMemory(memorySearch.value.trim());
  } catch (err) {
    status.textContent = "memory delete failed";
    addBubble(err.message, "error");
  }
}

function startListening() {
  if (AndroidVoice && typeof AndroidVoice.isAvailable === "function" && AndroidVoice.isAvailable()
      && typeof AndroidVoice.startListening === "function") {
    stopSpeaking();
    stopListening();
    usingAndroidVoice = true;
    listening = true;
    mic.classList.add("listening");
    mic.textContent = "Listening...";
    voiceStatus.textContent = "Listening. Speak now.";
    AndroidVoice.startListening();
    return;
  }
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    startAudioRecorderFallback();
    return;
  }
  if (!SpeechRecognition) {
    voiceStatus.textContent = "Speech recognition is not available in this browser. Use Chrome or Edge.";
    return;
  }
  stopSpeaking();
  stopListening();
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = true;
  let finalText = "";
  recognition.onstart = () => {
    listening = true;
    mic.classList.add("listening");
    mic.textContent = "Listening...";
    voiceStatus.textContent = "Listening. Speak now.";
  };
  recognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const text = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalText += text;
      } else {
        interim += text;
      }
    }
    const combined = (finalText + " " + interim).trim();
    transcript.value = combined;
    input.value = combined;
  };
  recognition.onerror = (event) => {
    voiceStatus.textContent = "Voice error: " + event.error + ". Text chat still works.";
    listening = false;
    mic.classList.remove("listening");
    mic.textContent = "Talk";
  };
  recognition.onend = () => {
    listening = false;
    mic.classList.remove("listening");
    mic.textContent = "Talk";
    voiceStatus.textContent = input.value.trim()
      ? "Transcription ready. Edit if needed, then Send."
      : "No speech captured.";
  };
  recognition.start();
}

function stopListening() {
  if (recorderState) {
    stopAudioRecorderFallback();
  } else if (usingAndroidVoice && AndroidVoice && typeof AndroidVoice.cancelListening === "function") {
    AndroidVoice.cancelListening();
  } else if (recognition && listening) {
    recognition.stop();
  }
  usingAndroidVoice = false;
  listening = false;
  mic.classList.remove("listening");
  mic.textContent = "Talk";
}

window.receiveAndroidVoiceEvent = (type, text, error) => {
  if (type === "start" || type === "speech_start") {
    usingAndroidVoice = true;
    listening = true;
    mic.classList.add("listening");
    mic.textContent = "Listening...";
    voiceStatus.textContent = "Listening. Speak now.";
    return;
  }
  if (type === "partial") {
    transcript.value = text || "";
    input.value = text || "";
    voiceStatus.textContent = "Listening. Speak now.";
    return;
  }
  if (type === "result") {
    transcript.value = text || "";
    input.value = text || "";
    usingAndroidVoice = false;
    listening = false;
    mic.classList.remove("listening");
    mic.textContent = "Talk";
    voiceStatus.textContent = input.value.trim()
      ? "Transcription ready. Edit if needed, then Send."
      : "No speech captured.";
    return;
  }
  if (type === "stopped" || type === "speech_end") {
    usingAndroidVoice = false;
    listening = false;
    mic.classList.remove("listening");
    mic.textContent = "Talk";
    if (!input.value.trim()) voiceStatus.textContent = "Voice stopped.";
    return;
  }
  if (type === "error") {
    usingAndroidVoice = false;
    listening = false;
    mic.classList.remove("listening");
    mic.textContent = "Talk";
    const message = error || "Speech recognition failed.";
    voiceStatus.textContent = "Voice error: " + message + " Text chat still works.";
    if (message.toLowerCase().includes("not available") && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      voiceStatus.textContent = "Android speech is unavailable. Starting laptop transcription recorder...";
      startAudioRecorderFallback();
    }
  }
};

async function startAudioRecorderFallback() {
  stopSpeaking();
  if (recorderState || busy) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    const chunks = [];
    processor.onaudioprocess = (event) => {
      chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
    source.connect(processor);
    processor.connect(audioContext.destination);
    recorderState = { stream, audioContext, source, processor, chunks };
    listening = true;
    mic.classList.add("listening");
    mic.textContent = "Stop recording";
    voiceStatus.textContent = "Recording. Speak now, then tap Stop recording.";
  } catch (err) {
    recorderState = null;
    listening = false;
    mic.classList.remove("listening");
    mic.textContent = "Talk";
    voiceStatus.textContent = "Voice recording failed: " + err.message + ". Text chat still works.";
  }
}

async function stopAudioRecorderFallback() {
  const state = recorderState;
  recorderState = null;
  listening = false;
  mic.classList.remove("listening");
  mic.textContent = "Talk";
  if (!state) return;
  try {
    state.processor.disconnect();
    state.source.disconnect();
    state.stream.getTracks().forEach((track) => track.stop());
    await state.audioContext.close();
    voiceStatus.textContent = "Transcribing on laptop...";
    const wav = encodeWav(state.chunks, state.audioContext.sampleRate, 16000);
    const res = await fetch("/api/transcribe", {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "audio/wav" }),
      body: wav,
    });
    const data = await readJsonResponse(res);
    transcript.value = data.text || "";
    input.value = data.text || "";
    voiceStatus.textContent = input.value.trim()
      ? "Transcription ready. Edit if needed, then Send."
      : "No speech captured.";
  } catch (err) {
    voiceStatus.textContent = "Voice transcription failed: " + err.message + " Text chat still works.";
  }
}

function flattenAudio(chunks) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const result = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

function downsample(input, sourceRate, targetRate) {
  if (sourceRate === targetRate) return input;
  const ratio = sourceRate / targetRate;
  const newLength = Math.round(input.length / ratio);
  const output = new Float32Array(newLength);
  for (let i = 0; i < newLength; i += 1) {
    const start = Math.floor(i * ratio);
    const end = Math.min(Math.floor((i + 1) * ratio), input.length);
    let sum = 0;
    for (let j = start; j < end; j += 1) sum += input[j];
    output[i] = sum / Math.max(1, end - start);
  }
  return output;
}

function encodeWav(chunks, sourceRate, targetRate) {
  const samples = downsample(flattenAudio(chunks), sourceRate, targetRate);
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, targetRate, true);
  view.setUint32(28, targetRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([view], { type: "audio/wav" });
}

function writeAscii(view, offset, text) {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}

mic.addEventListener("click", () => {
  if (listening) {
    stopListening();
  } else {
    startListening();
  }
});

function speak(text) {
  if (!spokenReplies.checked || !text || !("speechSynthesis" in window)) return;
  stopSpeaking();
  const clean = text.replace(/\s*tools?:.*$/gim, "").replace(/\n/g, ". ");
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.lang = "en-US";
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.onstart = () => {
    stopSpeech.disabled = false;
    voiceStatus.textContent = "Speaking. Press Stop voice to interrupt.";
  };
  utterance.onend = () => {
    stopSpeech.disabled = true;
    voiceStatus.textContent = "";
  };
  utterance.onerror = () => {
    stopSpeech.disabled = true;
    voiceStatus.textContent = "Speech output failed. Text chat still works.";
  };
  window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  stopSpeech.disabled = true;
}

stopSpeech.addEventListener("click", stopSpeaking);

async function init() {
  try {
    const res = await fetch("/api/health", { headers: apiHeaders() });
    const h = await readJsonResponse(res);
    const phoneStatus = h.phone_access_enabled ? (h.paired ? "phone paired" : "pairing needed") : "local";
    status.textContent = h.model_available ? `model ready - ${phoneStatus}` : `model unavailable - ${phoneStatus}`;
    systemBubble.textContent = h.model_available
      ? "Local companion ready. Try: \"Save a note: my project is called Vamsi Companion.\""
      : "The model file was not found, so responses will report an error. Check MODEL_PATH and .env.";
    voiceStatus.textContent = AndroidVoice && typeof AndroidVoice.isAvailable === "function" && AndroidVoice.isAvailable()
      ? "Android voice ready. Click Talk, speak, correct the text, then send."
      : navigator.mediaDevices && navigator.mediaDevices.getUserMedia
        ? "Voice recorder ready. Click Talk, speak, click Stop recording, then send."
        : SpeechRecognition
          ? "Voice ready. Click Talk, speak, correct the text, then send."
          : "Voice input needs Chrome or Edge speech recognition.";
    await loadMemory();
  } catch (err) {
    status.textContent = "cannot reach backend";
  }
}

init();
