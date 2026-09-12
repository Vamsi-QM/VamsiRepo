# Phase 4C Report - Reply Through Notifications

Phase 4C adds controlled WhatsApp replies through Android notification quick-reply actions. It is designed for driving-style commands where Vamsi Companion replies only if Android exposes a safe notification reply action.

## Implemented
- Deterministic reply command parser before model inference.
- Backend `reply_notification` action returned for supported reply commands.
- Web UI calls the Android bridge and shows whether the reply was actually sent.
- Android notification listener stores recent notifications with their available actions.
- Android quick-reply sender uses `RemoteInput` and the notification `PendingIntent`.
- Honest failure messages when Notification Access is off, the notification expired, or no quick-reply action exists.

## Supported commands now
- `Reply to 2: I am driving`
- `Reply to Mom: I am driving`
- `Reply tell him I am driving`
- `Reply I am driving`
- `Reply him I am driving`
- `Reply to latest WhatsApp: I will call later`
- `Reply to latest WhatsApp message with I will call later`

## Completion test
1. Reinstall or rerun the Android app from Android Studio because Phase 4C changes native Android code.
2. Start the backend with `D:\VamsiCompanion\scripts\start_phone.ps1` and connect through the paired ngrok URL.
3. Make sure Android Notification Access is enabled for Vamsi Companion.
4. Ask someone to send a fresh WhatsApp message so a live notification is visible.
5. In Vamsi Companion, send `Read latest WhatsApp message` and confirm it sees the message.
6. If several people messaged you, use the number shown in the notification list, for example `Reply to 2: I am driving`.
7. Or use a sender name, for example `Reply to Mom: I am driving`.
8. Open WhatsApp and confirm the reply was sent.

Expected result: if the WhatsApp notification includes a quick-reply action, the reply is sent and Vamsi Companion says it was sent. If Android does not provide quick reply for that notification, Vamsi Companion reports that it found no recent WhatsApp notification with a quick-reply action.

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
- 88 Python tests passed.

## Known limits
- Replies depend on Android/WhatsApp exposing a quick-reply action on the notification.
- Old, dismissed, muted, private, or expired notifications may not be replyable.
- This does not open WhatsApp chats and type into the UI. That belongs to a later Accessibility-based phase if we choose to build it.
- Untargeted replies send to the latest matching WhatsApp notification with quick reply. Safer targeted replies can use `Reply to 2: ...` or `Reply to Mom: ...`.
- No Git push has been done for this phase yet. Push after manual phone confirmation.

## Targeted reply update
- `Reply to 2: ...` targets the second notification shown by notification reading.
- `Reply to Mom: ...` targets the latest WhatsApp notification whose title or text contains `Mom`.
- If the chosen notification has no Android quick-reply action, the app reports that instead of sending to another person.
