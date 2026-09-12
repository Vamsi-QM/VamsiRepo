# Phase 4E Report - WhatsApp Accessibility Operator

## What changed
- Added `VamsiAccessibilityService`, exposed in Android settings as **Vamsi Companion operator**.
- Contact-name WhatsApp commands now use Accessibility when there is no phone number, for example `Send WhatsApp 1 to Mom: I am driving`.
- The Android bridge opens Accessibility settings when permission is missing.
- The web UI reports when the operator starts and explains the permission step.

## Current behaviour
- WhatsApp 1 opens directly through `com.whatsapp`, then the operator tries to search the contact, open the chat, type the message, and press Send.
- WhatsApp 2 still uses chooser fallback when Realme hides the clone app. After the user chooses the cloned WhatsApp, the operator keeps trying to continue on the opened WhatsApp screen.

## Verification
```powershell
javac -cp $androidJar -d $classes android-app\src\main\java\com\vamsi\companion\MainActivity.java android-app\src\main\java\com\vamsi\companion\VamsiNotificationListenerService.java android-app\src\main\java\com\vamsi\companion\VamsiAccessibilityService.java
.\.venv\Scripts\python.exe -m py_compile app\phone_actions.py app\web\server.py
node --check app\web\static\app.js
.\.venv\Scripts\python.exe -m pytest -q
```

Result: Java compile passed, JS syntax passed, Python compile passed, and 97 backend tests passed. Manual Android testing is still required because Accessibility actions depend on the live WhatsApp UI.
