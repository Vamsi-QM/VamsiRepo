package com.vamsi.companion;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.view.Gravity;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.PermissionRequest;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final String PREFS = "vamsi_companion";
    private static final String KEY_URL = "backend_url";
    private static final int REQ_AUDIO = 44;

    private SharedPreferences prefs;
    private LinearLayout root;
    private EditText urlInput;
    private TextView status;
    private WebView webView;
    private PermissionRequest pendingMicRequest;
    private SpeechRecognizer speechRecognizer;
    private boolean nativeListening = false;
    private boolean pendingNativeVoiceStart = false;

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
        if (url.isEmpty()) {
            return "";
        }
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "https://" + url;
        }
        Uri uri = Uri.parse(url);
        if (uri.getHost() == null) {
            return "";
        }
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
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) {
                    return;
                }
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

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_AUDIO) {
            boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
            if (pendingMicRequest != null) {
                if (granted) {
                    pendingMicRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                } else {
                    pendingMicRequest.deny();
                }
                pendingMicRequest = null;
            }
            if (pendingNativeVoiceStart) {
                pendingNativeVoiceStart = false;
                if (granted) {
                    startNativeVoiceRecognition();
                } else {
                    emitVoiceEvent("error", "", "Microphone permission was denied.");
                }
            }
        }
    }

    private void startNativeVoiceRecognition() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            emitVoiceEvent("error", "", "Android speech recognition is not available on this phone.");
            return;
        }
        if (!hasAudioPermission()) {
            requestAudioPermissionForNativeVoice();
            return;
        }
        stopNativeVoiceRecognition();
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle params) {
                nativeListening = true;
                emitVoiceEvent("start", "", "");
            }
            @Override public void onBeginningOfSpeech() {
                emitVoiceEvent("speech_start", "", "");
            }
            @Override public void onRmsChanged(float rmsdB) { }
            @Override public void onBufferReceived(byte[] buffer) { }
            @Override public void onEndOfSpeech() {
                nativeListening = false;
                emitVoiceEvent("speech_end", "", "");
            }
            @Override public void onError(int error) {
                nativeListening = false;
                String message = speechErrorMessage(error);
                emitVoiceEvent("error", "", message);
                destroySpeechRecognizer();
            }
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

    private void stopNativeVoiceRecognition() {
        if (speechRecognizer != null) {
            if (nativeListening) {
                speechRecognizer.stopListening();
            } else {
                destroySpeechRecognizer();
            }
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

    private void emitVoiceEvent(String type, String text, String error) {
        if (webView == null) {
            return;
        }
        String script = "window.receiveAndroidVoiceEvent && window.receiveAndroidVoiceEvent("
                + JSONObject.quote(type) + ","
                + JSONObject.quote(text == null ? "" : text) + ","
                + JSONObject.quote(error == null ? "" : error) + ");";
        runOnUiThread(() -> webView.evaluateJavascript(script, null));
    }

    private String speechErrorMessage(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO:
                return "Audio recording error.";
            case SpeechRecognizer.ERROR_CLIENT:
                return "Speech recognition client error.";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                return "Microphone permission is missing.";
            case SpeechRecognizer.ERROR_NETWORK:
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:
                return "Speech recognition network error.";
            case SpeechRecognizer.ERROR_NO_MATCH:
                return "No speech was captured. Try again closer to the phone mic.";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
                return "Speech recognizer is busy. Try again.";
            case SpeechRecognizer.ERROR_SERVER:
                return "Speech recognition server error.";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
                return "No speech heard. Try again.";
            default:
                return "Speech recognition failed.";
        }
    }

    public class VoiceBridge {
        @JavascriptInterface
        public boolean isAvailable() {
            return SpeechRecognizer.isRecognitionAvailable(MainActivity.this);
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
        public void stopListening() {
            runOnUiThread(() -> stopNativeVoiceRecognition());
        }

        @JavascriptInterface
        public void cancelListening() {
            runOnUiThread(() -> cancelNativeVoiceRecognition());
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
        destroySpeechRecognizer();
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
