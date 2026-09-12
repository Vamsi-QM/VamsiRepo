package com.vamsi.companion;

import android.accessibilityservice.AccessibilityService;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.TextUtils;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class VamsiAccessibilityService extends AccessibilityService {
    private static final int MAX_STEPS = 36;
    private static final long STEP_DELAY_MS = 650;

    private static VamsiAccessibilityService connectedService;
    private static PendingWhatsAppSend pendingSend;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean stepScheduled = false;

    static boolean isEnabled(Context context) {
        String enabled = Settings.Secure.getString(
                context.getContentResolver(),
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        );
        if (enabled == null) return false;
        String expected = new ComponentName(context, VamsiAccessibilityService.class).flattenToString().toLowerCase(Locale.ROOT);
        return enabled.toLowerCase(Locale.ROOT).contains(expected);
    }

    static boolean startWhatsAppSend(Context context, String targetName, String message, int whatsappSlot, String selectedPackage) {
        if (!isEnabled(context) || targetName == null || targetName.trim().isEmpty() || message == null || message.trim().isEmpty()) {
            return false;
        }
        pendingSend = new PendingWhatsAppSend(targetName.trim(), message.trim(), whatsappSlot, selectedPackage == null ? "" : selectedPackage.trim());
        try {
            if (whatsappSlot == 2 && pendingSend.packageName.isEmpty()) {
                Intent chooserBase = new Intent(Intent.ACTION_SEND);
                chooserBase.setType("text/plain");
                chooserBase.putExtra(Intent.EXTRA_TEXT, " ");
                Intent chooser = Intent.createChooser(chooserBase, "Choose WhatsApp 2");
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(chooser);
                Toast.makeText(context, "Pick cloned WhatsApp. I will continue after it opens.", Toast.LENGTH_LONG).show();
            } else {
                String packageName = pendingSend.packageName.isEmpty() ? "com.whatsapp" : pendingSend.packageName;
                PackageManager pm = context.getPackageManager();
                Intent launch = pm.getLaunchIntentForPackage(packageName);
                if (launch == null) {
                    Intent view = new Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/"));
                    view.setPackage(packageName);
                    launch = view;
                }
                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(launch);
                Toast.makeText(context, "Opening WhatsApp to message " + pendingSend.targetName, Toast.LENGTH_SHORT).show();
            }
            VamsiAccessibilityService service = connectedService;
            if (service != null) service.scheduleStep(900);
            return true;
        } catch (Exception error) {
            pendingSend = null;
            Toast.makeText(context, "Could not open WhatsApp for automation", Toast.LENGTH_SHORT).show();
            return false;
        }
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        connectedService = this;
        scheduleStep(500);
    }

    @Override
    public void onDestroy() {
        if (connectedService == this) connectedService = null;
        super.onDestroy();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (pendingSend != null) scheduleStep(350);
    }

    @Override
    public void onInterrupt() {
        fail("WhatsApp operator was interrupted.");
    }

    private void scheduleStep(long delayMs) {
        if (stepScheduled) return;
        stepScheduled = true;
        handler.postDelayed(() -> {
            stepScheduled = false;
            runStep();
        }, delayMs);
    }

    private void runStep() {
        PendingWhatsAppSend job = pendingSend;
        if (job == null) return;
        job.steps++;
        if (job.steps > MAX_STEPS) {
            fail("I could not finish the WhatsApp send. Please check the screen and send manually.");
            return;
        }

        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) {
            scheduleStep(STEP_DELAY_MS);
            return;
        }

        try {
            String pkg = root.getPackageName() == null ? "" : root.getPackageName().toString().toLowerCase(Locale.ROOT);
            String rootText = collectText(root).toLowerCase(Locale.ROOT);

            if (!pkg.contains("whatsapp") && !rootText.contains("whatsapp")) {
                scheduleStep(STEP_DELAY_MS);
                return;
            }

            switch (job.stage) {
                case 0:
                    if (openSearch(root)) {
                        job.stage = 1;
                        scheduleStep(STEP_DELAY_MS);
                    } else {
                        job.searchMisses++;
                        if (job.searchMisses == 4 || job.searchMisses == 8) {
                            performGlobalAction(GLOBAL_ACTION_BACK);
                        }
                        scheduleStep(STEP_DELAY_MS);
                    }
                    break;
                case 1:
                    if (setSearchText(root, job.targetName)) {
                        job.stage = 2;
                        scheduleStep(1100);
                    } else {
                        scheduleStep(STEP_DELAY_MS);
                    }
                    break;
                case 2:
                    if (openContact(root, job.targetName)) {
                        job.stage = 3;
                        scheduleStep(1100);
                    } else {
                        scheduleStep(STEP_DELAY_MS);
                    }
                    break;
                case 3:
                    if (setMessageText(root, job.message)) {
                        job.stage = 4;
                        scheduleStep(STEP_DELAY_MS);
                    } else {
                        scheduleStep(STEP_DELAY_MS);
                    }
                    break;
                case 4:
                    if (tapSend(root)) {
                        Toast.makeText(this, "Sent WhatsApp message to " + job.targetName, Toast.LENGTH_LONG).show();
                        pendingSend = null;
                    } else {
                        scheduleStep(STEP_DELAY_MS);
                    }
                    break;
                default:
                    fail("WhatsApp operator reached an unknown step.");
            }
        } finally {
            root.recycle();
        }
    }

    private boolean openSearch(AccessibilityNodeInfo root) {
        AccessibilityNodeInfo node = findNode(root, "search", true, false);
        if (node == null) node = findByViewIdSuffix(root, "menuitem_search");
        if (node == null) node = findByViewIdSuffix(root, "search");
        return clickNode(node);
    }

    private boolean setSearchText(AccessibilityNodeInfo root, String text) {
        AccessibilityNodeInfo edit = findEditable(root, true);
        if (edit == null) edit = findByViewIdSuffix(root, "search_src_text");
        return setText(edit, text);
    }

    private boolean openContact(AccessibilityNodeInfo root, String targetName) {
        AccessibilityNodeInfo exact = findNode(root, targetName, false, true);
        if (exact != null && clickNode(exact)) return true;
        AccessibilityNodeInfo fuzzy = findNode(root, targetName, false, false);
        return clickNode(fuzzy);
    }

    private boolean setMessageText(AccessibilityNodeInfo root, String text) {
        List<AccessibilityNodeInfo> edits = new ArrayList<>();
        collectEditable(root, edits);
        AccessibilityNodeInfo best = null;
        for (AccessibilityNodeInfo node : edits) {
            String viewId = node.getViewIdResourceName() == null ? "" : node.getViewIdResourceName().toLowerCase(Locale.ROOT);
            String hint = node.getHintText() == null ? "" : node.getHintText().toString().toLowerCase(Locale.ROOT);
            String nodeText = node.getText() == null ? "" : node.getText().toString().toLowerCase(Locale.ROOT);
            if (viewId.contains("entry") || hint.contains("message") || nodeText.contains("message")) {
                best = node;
            }
        }
        if (best == null && !edits.isEmpty()) best = edits.get(edits.size() - 1);
        return setText(best, text);
    }

    private boolean tapSend(AccessibilityNodeInfo root) {
        AccessibilityNodeInfo node = findNode(root, "send", true, false);
        if (node == null) node = findByViewIdSuffix(root, "send");
        return clickNode(node);
    }

    private AccessibilityNodeInfo findNode(AccessibilityNodeInfo node, String needle, boolean includeDescription, boolean exact) {
        if (node == null || needle == null) return null;
        String target = normalize(needle);
        String text = normalize(node.getText() == null ? "" : node.getText().toString());
        String desc = normalize(node.getContentDescription() == null ? "" : node.getContentDescription().toString());
        boolean textMatch = exact ? text.equals(target) : (!target.isEmpty() && text.contains(target));
        boolean descMatch = includeDescription && (exact ? desc.equals(target) : (!target.isEmpty() && desc.contains(target)));
        if (textMatch || descMatch) return AccessibilityNodeInfo.obtain(node);
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            AccessibilityNodeInfo found = findNode(child, needle, includeDescription, exact);
            if (child != null) child.recycle();
            if (found != null) return found;
        }
        return null;
    }

    private AccessibilityNodeInfo findByViewIdSuffix(AccessibilityNodeInfo node, String suffix) {
        if (node == null || suffix == null) return null;
        String id = node.getViewIdResourceName();
        if (id != null && id.toLowerCase(Locale.ROOT).endsWith(suffix.toLowerCase(Locale.ROOT))) {
            return AccessibilityNodeInfo.obtain(node);
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            AccessibilityNodeInfo found = findByViewIdSuffix(child, suffix);
            if (child != null) child.recycle();
            if (found != null) return found;
        }
        return null;
    }

    private AccessibilityNodeInfo findEditable(AccessibilityNodeInfo root, boolean preferFocused) {
        List<AccessibilityNodeInfo> edits = new ArrayList<>();
        collectEditable(root, edits);
        if (preferFocused) {
            for (AccessibilityNodeInfo node : edits) {
                if (node.isFocused()) return node;
            }
        }
        return edits.isEmpty() ? null : edits.get(0);
    }

    private void collectEditable(AccessibilityNodeInfo node, List<AccessibilityNodeInfo> out) {
        if (node == null) return;
        if (node.isEditable() || "android.widget.EditText".contentEquals(node.getClassName())) {
            out.add(AccessibilityNodeInfo.obtain(node));
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            collectEditable(child, out);
            if (child != null) child.recycle();
        }
    }

    private boolean setText(AccessibilityNodeInfo node, String text) {
        if (node == null || text == null) return false;
        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        boolean ok = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
        if (!ok) {
            node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            ok = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
        }
        node.recycle();
        return ok;
    }

    private boolean clickNode(AccessibilityNodeInfo node) {
        if (node == null) return false;
        AccessibilityNodeInfo current = node;
        while (current != null) {
            if (current.isClickable() && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                if (current != node) current.recycle();
                node.recycle();
                return true;
            }
            AccessibilityNodeInfo parent = current.getParent();
            if (current != node) current.recycle();
            current = parent;
        }
        node.recycle();
        return false;
    }

    private String collectText(AccessibilityNodeInfo node) {
        StringBuilder sb = new StringBuilder();
        appendText(node, sb);
        return sb.toString();
    }

    private void appendText(AccessibilityNodeInfo node, StringBuilder sb) {
        if (node == null) return;
        CharSequence text = node.getText();
        CharSequence desc = node.getContentDescription();
        if (!TextUtils.isEmpty(text)) sb.append(' ').append(text);
        if (!TextUtils.isEmpty(desc)) sb.append(' ').append(desc);
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            appendText(child, sb);
            if (child != null) child.recycle();
        }
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT).replaceAll("\\s+", " ");
    }

    private void fail(String message) {
        pendingSend = null;
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    private static class PendingWhatsAppSend {
        final String targetName;
        final String message;
        final int whatsappSlot;
        final String packageName;
        int stage = 0;
        int steps = 0;
        int searchMisses = 0;

        PendingWhatsAppSend(String targetName, String message, int whatsappSlot, String packageName) {
            this.targetName = targetName;
            this.message = message;
            this.whatsappSlot = whatsappSlot;
            this.packageName = packageName;
        }
    }
}
