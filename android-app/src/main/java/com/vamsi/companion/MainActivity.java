package com.vamsi.companion;

import android.Manifest;
import android.app.Activity;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
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

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_AUDIO && pendingMicRequest != null) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                pendingMicRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                pendingMicRequest.deny();
            }
            pendingMicRequest = null;
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
}
