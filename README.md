# Vamsi Companion - Phase 4E

A local laptop-backed companion prototype: real Qwen2.5-1.5B text conversation, persistent SQLite notes, browser voice, spoken replies, memory controls, paired phone access, Android app opening, read-only phone notification summaries, controlled WhatsApp notification replies, and direct WhatsApp compose flows, plus a first WhatsApp Accessibility operator for contact-name sending. Python, model, runtime and data live in D:\VamsiCompanion.

## Start
In PowerShell:

```powershell
cd D:\VamsiCompanion
.\scripts\start.ps1
```

Open http://127.0.0.1:8765. Keep the terminal open; Ctrl+C stops it. If an older server is already running, stop that server first so you use the reviewed code.

## Start For Phone
In PowerShell:

```powershell
cd D:\VamsiCompanion
.\scripts\start_phone.ps1
```

The terminal prints a phone URL like:

```text
http://192.168.x.x:8765/?pair=...
```

Open that exact URL in Chrome on the Realme phone while the phone and laptop are on the same Wi-Fi. The pairing token is saved in the phone browser after the first open. If Windows Firewall asks, allow private-network access for this local Python server.

## Try
- `Say hello in one short sentence.` (real local model)
- `Save a note: my project is called Vamsi Companion.`
- `What is my project called?`
- `Find notes: project`
- Click **New chat** and ask again, or restart the server and ask again.
- Click **Talk**, allow microphone permission in Chrome or Edge, speak a note command, correct the transcription if needed, then click **Send**.
- Leave **Speak replies** on to hear answers, and click **Stop voice** to interrupt spoken output.
- Use the **Memory** panel to view, search, edit, and delete saved notes.
- In phone mode, save a note from the Realme browser or Android wrapper, then retrieve it from the laptop browser.
- In the Android wrapper, try `Open WhatsApp`, `Open YouTube`, `Open Chrome`, `Open Google`, `Open Phone`, `Open Settings`, or `Open Play Store`.
- After enabling Android Notification Access for Vamsi Companion, try `Any notifications bro?` or `Read latest WhatsApp message`.
- After a fresh WhatsApp notification arrives, prefer targeted replies like `Reply to 2: I am driving` or `Reply to Mom: I am driving`.
- When there is no notification, ask `Which WhatsApps are installed?`, then try `Send WhatsApp 1 to Mom: I am driving`. Enable Accessibility if Android asks. For hidden clone WhatsApp, `Send WhatsApp 2 to Mom: I am driving` may still require manually choosing the clone first.

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

Phone app voice uses a native Android recorder and sends WAV audio to the laptop backend for Vosk transcription. Phase 4 phone actions are handled deterministically before the model: supported open-app commands return a structured action, notification-read commands return a read-only phone action, reply commands return a controlled notification reply action, and the Android wrapper executes those actions through native bridges. It can also try Android speech recognition when available. If phone voice transcription is unavailable, run `scripts\setup_voice.ps1` once. Restart the backend after setup. Phase 2 voice uses the browser's built-in speech recognition and speech synthesis. Manual voice testing is required because microphone permission and installed browser voices are controlled by Windows and the browser. Text chat and memory controls continue to work if voice input or output is unavailable.

Phase 3A phone access uses the same browser UI from the Realme phone over home Wi-Fi. API calls require the pairing token printed by `scripts\start_phone.ps1`. Retry protection from earlier phases still applies through request IDs. Phase 4 app actions are only executed by the Android wrapper after the backend returns a supported phone action. Notification reading and notification replies require Android Notification Access to be enabled manually for Vamsi Companion.

## Native Android Wrapper
The repo includes a first native Android wrapper in `android-app`. It stores your paired URL, opens Vamsi Companion in a WebView, and asks for microphone permission so the existing Talk button can work inside the app.

Build:

```powershell
cd D:\VamsiCompanion
.\scripts\build_android.ps1
```

APK path after a successful build:

```text
D:\VamsiCompanion\android-app\build\outputs\apk\debug\android-app-debug.apk
```

If the script fails with a Java/Gradle loopback error, open `D:\VamsiCompanion` in Android Studio and build the `android-app` module from there.

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

## Phase 3A acceptance checklist
- Start with `.\scripts\start_phone.ps1`.
- Open the printed pairing URL on the Realme phone.
- Confirm the status shows `phone paired`.
- Send `Save a note: my phone can reach Vamsi Companion.`
- Open the laptop browser and ask `What is my phone note?`
- Turn Wi-Fi off on the phone briefly and confirm the browser reports a connection problem instead of duplicating an action.
- Turn Wi-Fi back on, refresh, and retrieve the saved note again.


## Phase 4A acceptance checklist
- Start with `.\scripts\start_phone.ps1` and your current ngrok tunnel.
- Reinstall or rerun the Android app from Android Studio because native bridge code changed.
- Paste the paired ngrok URL in the Android app and tap **Connect**.
- Send `Open WhatsApp` from the phone text box and confirm WhatsApp opens.
- Return to Vamsi Companion and send `Open YouTube`, `Open Settings`, and `Open Play Store`.
- Try one unsupported app name and confirm the assistant reports the supported list.
- After text works, repeat one command with **Talk**.

## Phase 4B acceptance checklist
- Reinstall or rerun the Android app from Android Studio because this phase adds a native notification listener.
- Start the backend with `.\scripts\start_phone.ps1` and connect through your current paired ngrok URL.
- Send `Any notifications bro?` from the Android app.
- If Android settings opens, enable **Vamsi Companion notifications** under Notification Access, then return to the app.
- Ask someone to send a WhatsApp message or create a visible notification.
- Send `Read latest WhatsApp message` and confirm the assistant shows and speaks the latest matching notification.
- Try `Who messaged me?` by Talk or keyboard voice after text works.

## Phase 4C acceptance checklist
- Reinstall or rerun the Android app from Android Studio because this phase changes native notification reply code.
- Start the backend with `.\scripts\start_phone.ps1` and connect through your current paired ngrok URL.
- Keep Android Notification Access enabled for Vamsi Companion.
- Ask someone to send a fresh WhatsApp message so a live notification appears.
- Send `Read latest WhatsApp message` and confirm Vamsi Companion can see it.
- Send `Reply to 2: I am driving` using the number shown in the notification list, or `Reply to Mom: I am driving` using the sender name.
- Open WhatsApp and confirm the reply was sent, or confirm Vamsi Companion honestly reports that quick reply is unavailable.

## Phase 4D acceptance checklist
- Reinstall or rerun the Android app from Android Studio because this phase changes native WhatsApp intent code.
- Start the backend with `.\scripts\start_phone.ps1` and connect through your paired ngrok URL.
- Ask `Which WhatsApps are installed?` and note slot 1/2. If only one WhatsApp is listed, slot 2 uses chooser fallback for hidden clone apps.
- Test `Open WhatsApp 1` and `Open WhatsApp 2`.
- Test `Send WhatsApp 1 to 9876543210: I am driving` with a real test number.
- Confirm the selected WhatsApp opens the number chat with the message prepared.
- Test `Send WhatsApp 2 to Mom: I am driving` if slot 2 is detected.
- Confirm the selected WhatsApp opens compose/share with the message and lets you choose/send.

## Phase 4E accessibility operator checklist
- Reinstall or rerun the Android app from Android Studio because this phase adds `Vamsi Companion operator` as an Accessibility Service.
- Start the backend with `.\scripts\start_phone.ps1` and connect through your paired ngrok URL.
- Send `Send WhatsApp 1 to Mom: I am driving` from the Android app.
- If Android settings opens, go to Accessibility and enable **Vamsi Companion operator**, then return to the app and send the command again.
- Watch the phone: it should open WhatsApp, tap Search, type `Mom`, open the matching chat, type the message, and press Send.
- If you use `Send WhatsApp 2 to Mom: I am driving` and Realme hides the clone app, manually pick the cloned WhatsApp from the chooser; the operator will then try to continue inside the opened WhatsApp screen.
- Confirm in WhatsApp that the message reached the intended contact. If the operator stops, use the screen state and toast message to identify which step failed.

## Limits
This is still a laptop-backed prototype, not the final Android friend yet. Observed cold model replies were 8-15 seconds; direct note operations around 0.02 seconds. Browser voice quality depends on Chrome/Edge, microphone permission, Windows voices, and internet/browser speech service behavior. Phone access works through the Realme browser and now has a first native WebView wrapper source. Small-model conversation can be inaccurate. Search is keyword-based, not semantic. Saving uses explicit commands; unrestricted conversational memory and perfect model honesty are not guaranteed. Caller announcement, call controls, app installation, self-development, remote internet access, and internet search are not implemented yet. Contact-name WhatsApp sending uses Android Accessibility and depends on the visible WhatsApp UI, so WhatsApp layout or Realme clone behaviour can still require follow-up fixes. Use phone access only on a trusted private Wi-Fi network or private ngrok URL.


