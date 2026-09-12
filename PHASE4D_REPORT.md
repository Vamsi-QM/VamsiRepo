# Phase 4D Report - Direct WhatsApp Message Flow

Phase 4D adds a direct WhatsApp compose flow for cases where there is no notification to reply to.

## Implemented
- Deterministic parser for direct WhatsApp message commands.
- Backend `direct_whatsapp` action returned before model inference.
- Web UI forwards the action to the Android wrapper and reports what happened.
- Android wrapper opens a `wa.me` chat when a phone number is provided.
- Android wrapper opens WhatsApp share/compose when a contact name or no number is provided.
- WhatsApp selector support detects installed WhatsApp-like apps and maps `WhatsApp 1` / `WhatsApp 2` to the phone's actual packages.

## Supported commands now
- `Which WhatsApps are installed?`
- `Open WhatsApp 1`
- `Open WhatsApp 2`
- `Send WhatsApp 1 to 9876543210: I am driving`
- `Send WhatsApp 2 to Mom: I am driving`
- `Send WhatsApp to 9876543210: I am driving`
- `Message 9876543210 on WhatsApp: I am driving`
- `Send WhatsApp to Mom: I am driving`
- `WhatsApp message with I am driving`

## Completion test
1. Reinstall or rerun the Android app from Android Studio because Phase 4D changes native Android code.
2. Restart the backend with `D:\VamsiCompanion\scripts\start_phone.ps1` and connect with the paired ngrok URL.
3. Ask `Which WhatsApps are installed?` and note which app is slot 1 and slot 2.
4. Test opening each one with `Open WhatsApp 1` and `Open WhatsApp 2`.
5. Test a selected WhatsApp message: `Send WhatsApp 1 to 9876543210: I am driving` using a real test number.
6. Confirm the selected WhatsApp opens that chat with the message prepared.
7. Test the clone/second app if detected: `Send WhatsApp 2 to Mom: I am driving`.
8. Confirm the selected WhatsApp opens compose/share so you can choose the contact and send.

## Verification
```powershell
D:\VamsiCompanion\.venv\Scripts\python.exe -m py_compile D:\VamsiCompanion\app\phone_actions.py D:\VamsiCompanion\app\web\server.py
node --check D:\VamsiCompanion\app\web\static\app.js
javac -cp C:\Users\Ravipati-Vamsidhar\AppData\Local\Android\Sdk\platforms\android-36\android.jar -d $env:TEMP D:\VamsiCompanion\android-app\src\main\java\com\vamsi\companion\MainActivity.java D:\VamsiCompanion\android-app\src\main\java\com\vamsi\companion\VamsiNotificationListenerService.java
D:\VamsiCompanion\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Latest automated result:
- Android Java compile passed with the existing deprecated API note.
- Browser script syntax check passed.
- 97 Python tests passed.

## Known limits
- Phone-number messaging opens the selected WhatsApp chat with the message prepared; WhatsApp may still require the final send tap.
- Contact-name messaging cannot directly select a WhatsApp contact without Accessibility automation or a saved number mapping. It opens the selected WhatsApp compose/share flow with the message.
- Full auto-send to a named contact without a notification belongs to a later Accessibility-based phase.
- No Git push has been done for this phase yet. Push after manual phone confirmation.


## WhatsApp selector update
- `Which WhatsApps are installed?` lists detected WhatsApp apps by slot.
- `WhatsApp 1` prefers the normal `com.whatsapp` package when installed.
- `WhatsApp 2` maps to the next detected WhatsApp-like launcher app, such as a clone app on Realme.
- If the clone package is hidden by Android, the list will show only the normal WhatsApp and slot 2 will report unavailable.


## Clone chooser fallback update
- If Android detects only normal WhatsApp, the UI now shows `2. WhatsApp 2 chooser fallback`.
- `Open WhatsApp 2` opens an Android chooser instead of failing.
- `Send WhatsApp 2 to Mom: ...` opens a chooser/share flow so you can pick the hidden cloned WhatsApp manually.
- This is needed on Realme because App Clone can hide the clone package from normal package detection.
