# Vamsi Companion - Phase 2

A local laptop prototype: real Qwen2.5-1.5B text conversation, persistent SQLite notes, a browser voice interface, spoken replies, and memory controls. Python, model, runtime and data live in D:\VamsiCompanion.

## Start
In PowerShell:

```powershell
cd D:\VamsiCompanion
.\scripts\start.ps1
```

Open http://127.0.0.1:8765. Keep the terminal open; Ctrl+C stops it. If an older server is already running, stop that server first so you use the reviewed code.

## Try
- `Say hello in one short sentence.` (real local model)
- `Save a note: my project is called Vamsi Companion.`
- `What is my project called?`
- `Find notes: project`
- Click **New chat** and ask again, or restart the server and ask again.
- Click **Talk**, allow microphone permission in Chrome or Edge, speak a note command, correct the transcription if needed, then click **Send**.
- Leave **Speak replies** on to hear answers, and click **Stop voice** to interrupt spoken output.
- Use the **Memory** panel to view, search, edit, and delete saved notes.

Notes are in `data\companion.db`. New chat resets conversation context, not notes. Conversation messages are bounded in memory and are not permanent memories.

## Reliability design
Explicit `Save a note: ...` and `Remember ...` commands preserve your exact note text and call storage directly. `Find notes: ...` and supported personal questions search storage directly. This routing intentionally works even if the model is unavailable. It is ordinary application code, not evidence that the model has learned a new skill.

Other conversation uses the real local model. It may propose a read tool; arbitrary model-proposed writes require an explicit save command. Note confirmation and search responses are rendered from actual tool results, with note IDs; the model does not rewrite them. Unrecognized phrasing may need the explicit commands above. English routing is the current tested scope.

Separate browser conversations use separate contexts. Requests are serialized for this single-user CPU prototype. Same request ID retries are cached during a server session, conflicting reuse is rejected, and exact note content/title duplicates are prevented in storage. Conversation IDs expire after server restart; click New chat. Request caching is bounded and not a durable transaction journal.

Model inference runs in a persistent subprocess. A timed-out inference worker is terminated and can be restarted on the next request. Inference context is bounded by message history and the model's tokenizer. Long individual messages can be rejected by the model context limit; the app reports the error.

## Verification
```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\run_e2e.py
```
The E2E test creates unique data under `cache\acceptance`, exercises actual model inference and a unique stored fact across server restart, and verifies that the everyday database is unchanged.

Phase 2 voice uses the browser's built-in speech recognition and speech synthesis. Manual voice testing is required because microphone permission and installed browser voices are controlled by Windows and the browser. Text chat and memory controls continue to work if voice input or output is unavailable.

## Setup / dependencies
Existing installation is ready. To reproduce: `.\scripts\setup.ps1` (internet required for dependencies and model). `requirements.lock` records the installed versions; setup installs the CPU wheel then this lock. Runtime and data remain local; no paid API or automatic cloud fallback. Fresh installation was not rerun during review to avoid an unnecessary model download. All paths are configured through `.env` or environment variables; see `.env.example`.

## Phase 2 acceptance checklist
- Start the app and open it in Chrome or Edge.
- Click **Talk**, allow the microphone, and say `Save a note: my project is called Vamsi Companion.`
- Correct the transcription if needed, then click **Send**.
- Confirm the reply is spoken aloud when **Speak replies** is checked.
- Click **Stop voice** while it is speaking and confirm audio stops.
- Click **New chat**, then ask by voice or text: `What is my project called?`
- Edit one saved note in the **Memory** panel, refresh/search memory, then delete a test note.

## Limits
This is still a laptop prototype, not the phone friend yet. Observed cold model replies were 8-15 seconds; direct note operations around 0.02 seconds. Browser voice quality depends on Chrome/Edge, microphone permission, Windows voices, and internet/browser speech service behavior. Small-model conversation can be inaccurate. Search is keyword-based, not semantic. Saving uses explicit commands; unrestricted conversational memory and perfect model honesty are not guaranteed. No Android app, phone actions, self-development, authentication for remote access, or internet search yet. Keep it on localhost.
