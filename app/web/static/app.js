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

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

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

async function postChat(message) {
  const body = pending && pending.message === message ? pending : {
    message,
    conversation_id: conversationId,
    request_id: crypto.randomUUID(),
  };
  pending = body;
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
    const res = await fetch("/api/notes" + suffix);
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
      headers: { "Content-Type": "application/json" },
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
    const res = await fetch(`/api/notes/${encodeURIComponent(id)}`, { method: "DELETE" });
    await readJsonResponse(res);
    status.textContent = "memory deleted";
    await loadMemory(memorySearch.value.trim());
  } catch (err) {
    status.textContent = "memory delete failed";
    addBubble(err.message, "error");
  }
}

function startListening() {
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
  if (recognition && listening) {
    recognition.stop();
  }
  listening = false;
  mic.classList.remove("listening");
  mic.textContent = "Talk";
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
    const res = await fetch("/api/health");
    const h = await readJsonResponse(res);
    status.textContent = h.model_available ? "model ready" : "model unavailable";
    systemBubble.textContent = h.model_available
      ? "Local companion ready. Try: \"Save a note: my project is called Vamsi Companion.\""
      : "The model file was not found, so responses will report an error. Check MODEL_PATH and .env.";
    voiceStatus.textContent = SpeechRecognition
      ? "Voice ready. Click Talk, speak, correct the text, then send."
      : "Voice input needs Chrome or Edge speech recognition.";
    await loadMemory();
  } catch (err) {
    status.textContent = "cannot reach backend";
  }
}

init();
