package com.vamsi.companion;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.Base64;
import android.view.Gravity;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final String PREFS = "vamsi_companion";
    private static final String KEY_URL = "backend_url";
    private static final int REQ_AUDIO = 44;
    private static final int REQ_SPEECH = 45;
    private static final int SAMPLE_RATE = 16000;

    private SharedPreferences prefs;
    private LinearLayout root;
    private EditText urlInput;
    private TextView status;
    private WebView webView;
    private PermissionRequest pendingMicRequest;
    private SpeechRecognizer speechRecognizer;
    private boolean nativeListening = false;
    private boolean pendingNativeVoiceStart = false;
    private boolean pendingRecorderStart = false;
    private volatile boolean recording = false;
    private AudioRecord audioRecord;
    private Thread recorderThread;
    private ByteArrayOutputStream recordedPcm;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        showConnectScreen();
    }

    private void showConnectScreen() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 32, 32, 32);
        root.setGravity(Gravity.CENTER_VERTICAL);
        root.setBackgroundColor(0xff101418);

        TextView title = new TextView(this);
        title.setText("Vamsi Companion");
        title.setTextColor(0xffe8edf2);
        title.setTextSize(24);

        TextView help = new TextView(this);
        help.setText("Paste your paired URL from the laptop or ngrok, then connect.");
        help.setTextColor(0xffa8b3bf);
        help.setTextSize(15);
        help.setPadding(0, 12, 0, 16);

        urlInput = new EditText(this);
        urlInput.setSingleLine(false);
        urlInput.setMinLines(2);
        urlInput.setTextColor(0xffe8edf2);
        urlInput.setHintTextColor(0xff7f8b96);
        urlInput.setHint("https://your-ngrok-url/?pair=...");
        urlInput.setText(prefs.getString(KEY_URL, ""));

        Button connect = new Button(this);
        connect.setText("Connect");
        connect.setOnClickListener(v -> connectToUrl(urlInput.getText().toString()));

        status = new TextView(this);
        status.setTextColor(0xffa8b3bf);
        status.setPadding(0, 16, 0, 0);

        root.addView(title);
        root.addView(help);
        root.addView(urlInput);
        root.addView(connect);
        root.addView(status);
        setContentView(root);
    }

    private void connectToUrl(String rawUrl) {
        String url = normalizeUrl(rawUrl);
        if (url.isEmpty()) {
            status.setText("Enter the paired URL first.");
            return;
        }
        prefs.edit().putString(KEY_URL, url).apply();
        showWebView(url);
    }

    private String normalizeUrl(String rawUrl) {
        String url = rawUrl == null ? "" : rawUrl.trim();
        if (url.isEmpty()) return "";
        if (!url.startsWith("http://") && !url.startsWith("https://")) url = "https://" + url;
        Uri uri = Uri.parse(url);
        if (uri.getHost() == null) return "";
        return url;
    }

    private void showWebView(String url) {
        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setDatabaseEnabled(true);
        webView.addJavascriptInterface(new VoiceBridge(), "VamsiAndroidVoice");
        webView.addJavascriptInterface(new PhoneBridge(), "VamsiAndroidPhone");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && request.isForMainFrame()) {
                    showConnectScreen();
                    status.setText("Could not reach backend. Check ngrok/laptop server and try again.");
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) return;
                for (String resource : request.getResources()) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) {
                        if (hasAudioPermission()) {
                            request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                        } else {
                            pendingMicRequest = request;
                            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
                        }
                        return;
                    }
                }
                request.deny();
            }
        });

        setContentView(webView);
        webView.loadUrl(url);
    }

    private boolean hasAudioPermission() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.M
                || checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestAudioPermissionForNativeVoice() {
        pendingNativeVoiceStart = true;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
        }
    }

    private void requestAudioPermissionForRecorder() {
        pendingRecorderStart = true;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_AUDIO) {
            boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
            if (pendingMicRequest != null) {
                if (granted) pendingMicRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                else pendingMicRequest.deny();
                pendingMicRequest = null;
            }
            if (pendingNativeVoiceStart) {
                pendingNativeVoiceStart = false;
                if (granted) startNativeVoiceRecognition();
                else emitVoiceEvent("error", "", "Microphone permission was denied.");
            }
            if (pendingRecorderStart) {
                pendingRecorderStart = false;
                if (granted) startNativeRecorder();
                else emitVoiceEvent("recording_error", "", "Microphone permission was denied.");
            }
        }
    }

    private void startNativeVoiceRecognition() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            startSpeechIntentRecognition();
            return;
        }
        if (!hasAudioPermission()) {
            requestAudioPermissionForNativeVoice();
            return;
        }
        stopNativeVoiceRecognition();
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle params) { nativeListening = true; emitVoiceEvent("start", "", ""); }
            @Override public void onBeginningOfSpeech() { emitVoiceEvent("speech_start", "", ""); }
            @Override public void onRmsChanged(float rmsdB) { }
            @Override public void onBufferReceived(byte[] buffer) { }
            @Override public void onEndOfSpeech() { nativeListening = false; emitVoiceEvent("speech_end", "", ""); }
            @Override public void onError(int error) { nativeListening = false; emitVoiceEvent("error", "", speechErrorMessage(error)); destroySpeechRecognizer(); }
            @Override public void onResults(Bundle results) {
                nativeListening = false;
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                String text = matches != null && !matches.isEmpty() ? matches.get(0) : "";
                emitVoiceEvent("result", text, "");
                destroySpeechRecognizer();
            }
            @Override public void onPartialResults(Bundle partialResults) {
                ArrayList<String> matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                String text = matches != null && !matches.isEmpty() ? matches.get(0) : "";
                emitVoiceEvent("partial", text, "");
            }
            @Override public void onEvent(int eventType, Bundle params) { }
        });
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        speechRecognizer.startListening(intent);
    }

    private boolean canStartSpeechIntentRecognition() {
        Intent intent = buildSpeechIntent();
        return intent.resolveActivity(getPackageManager()) != null;
    }

    private Intent buildSpeechIntent() {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to Vamsi Companion");
        return intent;
    }

    private void startSpeechIntentRecognition() {
        Intent intent = buildSpeechIntent();
        try {
            nativeListening = true;
            emitVoiceEvent("start", "", "");
            startActivityForResult(intent, REQ_SPEECH);
        } catch (ActivityNotFoundException error) {
            nativeListening = false;
            emitVoiceEvent("error", "", "Android speech recognition is not available on this phone.");
        }
    }

    private void stopNativeVoiceRecognition() {
        if (speechRecognizer != null) {
            if (nativeListening) speechRecognizer.stopListening();
            else destroySpeechRecognizer();
        }
        nativeListening = false;
    }

    private void cancelNativeVoiceRecognition() {
        if (speechRecognizer != null) {
            speechRecognizer.cancel();
            destroySpeechRecognizer();
        }
        nativeListening = false;
        emitVoiceEvent("stopped", "", "");
    }

    private void destroySpeechRecognizer() {
        if (speechRecognizer != null) {
            speechRecognizer.destroy();
            speechRecognizer = null;
        }
    }

    private void startNativeRecorder() {
        if (!hasAudioPermission()) {
            requestAudioPermissionForRecorder();
            return;
        }
        if (recording) return;
        int minBuffer = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
        );
        if (minBuffer <= 0) {
            emitVoiceEvent("recording_error", "", "Android microphone buffer could not start.");
            return;
        }
        int bufferSize = Math.max(minBuffer, SAMPLE_RATE);
        try {
            audioRecord = new AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    bufferSize
            );
            if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
                releaseAudioRecord();
                emitVoiceEvent("recording_error", "", "Android microphone could not initialize.");
                return;
            }
            recordedPcm = new ByteArrayOutputStream();
            recording = true;
            audioRecord.startRecording();
            emitVoiceEvent("recording_start", "", "");
            recorderThread = new Thread(() -> recordLoop(bufferSize), "VamsiVoiceRecorder");
            recorderThread.start();
        } catch (SecurityException | IllegalStateException error) {
            recording = false;
            releaseAudioRecord();
            emitVoiceEvent("recording_error", "", "Could not start Android microphone recording.");
        }
    }

    private void recordLoop(int bufferSize) {
        byte[] buffer = new byte[bufferSize];
        while (recording && audioRecord != null) {
            int read = audioRecord.read(buffer, 0, buffer.length);
            if (read > 0 && recordedPcm != null) {
                recordedPcm.write(buffer, 0, read);
            }
        }
    }

    private void stopNativeRecorder() {
        if (!recording && audioRecord == null) return;
        recording = false;
        try {
            if (audioRecord != null) audioRecord.stop();
        } catch (IllegalStateException ignored) { }
        if (recorderThread != null) {
            try { recorderThread.join(1000); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
            recorderThread = null;
        }
        byte[] pcm = recordedPcm == null ? new byte[0] : recordedPcm.toByteArray();
        recordedPcm = null;
        releaseAudioRecord();
        if (pcm.length < SAMPLE_RATE / 2) {
            emitVoiceEvent("recording_error", "", "Recording was too short. Hold Talk, speak, then stop.");
            return;
        }
        byte[] wav;
        try {
            wav = pcmToWav(pcm, SAMPLE_RATE);
        } catch (IOException error) {
            emitVoiceEvent("recording_error", "", "Could not prepare recorded audio.");
            return;
        }
        String base64 = Base64.encodeToString(wav, Base64.NO_WRAP);
        emitVoiceEvent("recording_result", base64, "");
    }

    private void cancelNativeRecorder() {
        recording = false;
        try {
            if (audioRecord != null) audioRecord.stop();
        } catch (IllegalStateException ignored) { }
        releaseAudioRecord();
        recordedPcm = null;
        emitVoiceEvent("stopped", "", "");
    }

    private void releaseAudioRecord() {
        if (audioRecord != null) {
            audioRecord.release();
            audioRecord = null;
        }
    }

    private byte[] pcmToWav(byte[] pcm, int sampleRate) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int dataLength = pcm.length;
        int byteRate = sampleRate * 2;
        writeAscii(out, "RIFF");
        writeInt(out, 36 + dataLength);
        writeAscii(out, "WAVE");
        writeAscii(out, "fmt ");
        writeInt(out, 16);
        writeShort(out, (short) 1);
        writeShort(out, (short) 1);
        writeInt(out, sampleRate);
        writeInt(out, byteRate);
        writeShort(out, (short) 2);
        writeShort(out, (short) 16);
        writeAscii(out, "data");
        writeInt(out, dataLength);
        out.write(pcm);
        return out.toByteArray();
    }

    private void writeAscii(ByteArrayOutputStream out, String text) throws IOException {
        out.write(text.getBytes("US-ASCII"));
    }

    private void writeInt(ByteArrayOutputStream out, int value) throws IOException {
        out.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(value).array());
    }

    private void writeShort(ByteArrayOutputStream out, short value) throws IOException {
        out.write(ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort(value).array());
    }

    private void emitVoiceEvent(String type, String text, String error) {
        if (webView == null) return;
        String script = "window.receiveAndroidVoiceEvent && window.receiveAndroidVoiceEvent("
                + JSONObject.quote(type) + ","
                + JSONObject.quote(text == null ? "" : text) + ","
                + JSONObject.quote(error == null ? "" : error) + ");";
        runOnUiThread(() -> webView.evaluateJavascript(script, null));
    }

    private String speechErrorMessage(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO: return "Audio recording error.";
            case SpeechRecognizer.ERROR_CLIENT: return "Speech recognition client error.";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS: return "Microphone permission is missing.";
            case SpeechRecognizer.ERROR_NETWORK:
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT: return "Speech recognition network error.";
            case SpeechRecognizer.ERROR_NO_MATCH: return "No speech was captured. Try again closer to the phone mic.";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY: return "Speech recognizer is busy. Try again.";
            case SpeechRecognizer.ERROR_SERVER: return "Speech recognition server error.";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT: return "No speech heard. Try again.";
            default: return "Speech recognition failed.";
        }
    }


    public class PhoneBridge {
        @JavascriptInterface
        public boolean openApp(String actionJson) {
            try {
                JSONObject action = new JSONObject(actionJson == null ? "{}" : actionJson);
                String label = action.optString("label", "app");
                String intentName = action.optString("intent", "launch");
                JSONArray packages = action.optJSONArray("packages");

                Intent intent = null;
                if ("settings".equals(intentName)) {
                    intent = new Intent(Settings.ACTION_SETTINGS);
                } else if ("dialer".equals(intentName)) {
                    intent = new Intent(Intent.ACTION_DIAL);
                }
                if (intent != null && intent.resolveActivity(getPackageManager()) != null) {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    launchIntent(intent, label);
                    return true;
                }

                if (packages != null) {
                    for (int i = 0; i < packages.length(); i++) {
                        String packageName = packages.optString(i, "");
                        if (packageName.isEmpty()) continue;
                        Intent launchIntent = getPackageManager().getLaunchIntentForPackage(packageName);
                        if (launchIntent != null) {
                            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            launchIntent(launchIntent, label);
                            return true;
                        }
                    }
                }
                showToast(label + " is not installed or cannot be opened");
                return false;
            } catch (Exception error) {
                showToast("Could not open app");
                return false;
            }
        }
    }

    private void launchIntent(Intent intent, String label) {
        runOnUiThread(() -> {
            startActivity(intent);
            Toast.makeText(MainActivity.this, "Opening " + label, Toast.LENGTH_SHORT).show();
        });
    }

    private void showToast(String message) {
        runOnUiThread(() -> Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show());
    }

    public class VoiceBridge {
        @JavascriptInterface
        public boolean isAvailable() {
            return SpeechRecognizer.isRecognitionAvailable(MainActivity.this) || canStartSpeechIntentRecognition();
        }

        @JavascriptInterface
        public boolean canRecordAudio() {
            return true;
        }

        @JavascriptInterface
        public void startListening() {
            runOnUiThread(() -> {
                if (!hasAudioPermission()) {
                    requestAudioPermissionForNativeVoice();
                    return;
                }
                startNativeVoiceRecognition();
            });
        }

        @JavascriptInterface
        public void cancelListening() {
            runOnUiThread(() -> cancelNativeVoiceRecognition());
        }

        @JavascriptInterface
        public void startRecording() {
            runOnUiThread(() -> startNativeRecorder());
        }

        @JavascriptInterface
        public void stopRecording() {
            runOnUiThread(() -> stopNativeRecorder());
        }

        @JavascriptInterface
        public void cancelRecording() {
            runOnUiThread(() -> cancelNativeRecorder());
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_SPEECH) {
            nativeListening = false;
            if (resultCode == RESULT_OK && data != null) {
                ArrayList<String> matches = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
                String text = matches != null && !matches.isEmpty() ? matches.get(0) : "";
                emitVoiceEvent("result", text, "");
            } else {
                emitVoiceEvent("error", "", "No speech was captured. Try again.");
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        showConnectScreen();
    }

    @Override
    protected void onDestroy() {
        cancelNativeRecorder();
        destroySpeechRecognizer();
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
