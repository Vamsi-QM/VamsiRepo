# Android App Report

This is the native Android wrapper for Phase 3.

## Implemented
- Simple Android app module under `android-app`.
- Stores the paired backend URL in Android SharedPreferences.
- Loads Vamsi Companion in a WebView.
- Enables JavaScript and local storage for the existing web UI.
- Requests microphone permission and grants WebView audio capture for push-to-talk.
- Allows both `https://...ngrok.../?pair=...` and local `http://10.x.x.x:8765/?pair=...` URLs.
- Shows a connect screen again if the backend cannot be reached.

## Manual Install Flow
1. Build the debug APK with `scripts\build_android.ps1` or open the project in Android Studio and build the `android-app` module.
2. Copy or install `android-app/build/outputs/apk/debug/android-app-debug.apk` on the Realme phone.
3. Start the laptop backend with `scripts\start_phone.ps1`.
4. Start ngrok if using remote HTTPS.
5. Open the app and paste the full paired URL.
6. Tap **Connect**.
7. Allow microphone permission.

## Verification
- `MainActivity.java` compile-check passed against Android API 36 using `javac`.
- Full Gradle APK build is currently blocked on this machine by a Java/Gradle loopback error before project compilation: `java.io.IOException: Unable to establish loopback connection`.
- The project is ready to open in Android Studio, which can use the installed Android SDK at `C:\Users\Ravipati-Vamsidhar\AppData\Local\Android\Sdk`.

## Known Limits
- This wrapper still uses the existing browser UI inside WebView.
- APK generation still needs a successful Gradle/Android Studio build.
- Phone notifications, WhatsApp reply, opening apps, and call control are Phase 4.
- Wake word and background driving mode are later phases.
