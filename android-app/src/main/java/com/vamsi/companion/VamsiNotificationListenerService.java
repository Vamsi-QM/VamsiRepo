package com.vamsi.companion;

import android.app.Notification;
import android.app.PendingIntent;
import android.app.RemoteInput;
import android.content.Intent;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

public class VamsiNotificationListenerService extends NotificationListenerService {
    private static final int MAX_NOTIFICATIONS = 50;
    private static final List<NotificationEntry> RECENT = new ArrayList<>();
    private static VamsiNotificationListenerService connectedService;

    @Override
    public void onListenerConnected() {
        connectedService = this;
        StatusBarNotification[] active = getActiveNotifications();
        if (active == null) return;
        synchronized (RECENT) {
            RECENT.clear();
            for (StatusBarNotification sbn : active) {
                addLocked(fromStatusBarNotification(sbn));
            }
        }
    }

    @Override
    public void onListenerDisconnected() {
        connectedService = null;
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        NotificationEntry entry = fromStatusBarNotification(sbn);
        synchronized (RECENT) {
            Iterator<NotificationEntry> iterator = RECENT.iterator();
            while (iterator.hasNext()) {
                NotificationEntry existing = iterator.next();
                if (existing.key.equals(entry.key)) {
                    iterator.remove();
                    break;
                }
            }
            addLocked(entry);
        }
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {
        if (sbn == null) return;
        synchronized (RECENT) {
            Iterator<NotificationEntry> iterator = RECENT.iterator();
            while (iterator.hasNext()) {
                if (iterator.next().key.equals(sbn.getKey())) {
                    iterator.remove();
                    break;
                }
            }
        }
    }

    public static String readRecent(String actionJson) {
        String appFilter = "";
        int limit = 5;
        try {
            JSONObject action = new JSONObject(actionJson == null ? "{}" : actionJson);
            appFilter = action.optString("app", "").toLowerCase();
            limit = Math.max(1, Math.min(10, action.optInt("limit", 5)));
        } catch (Exception ignored) { }

        JSONArray items = new JSONArray();
        synchronized (RECENT) {
            for (NotificationEntry entry : RECENT) {
                if (items.length() >= limit) break;
                if (entry.isEmpty()) continue;
                if ("whatsapp".equals(appFilter) && !entry.packageName.startsWith("com.whatsapp")) continue;
                if ("youtube".equals(appFilter) && !"com.google.android.youtube".equals(entry.packageName)) continue;
                if ("chrome".equals(appFilter) && !"com.android.chrome".equals(entry.packageName)) continue;
                items.put(entry.toJson());
            }
        }

        JSONObject result = new JSONObject();
        try {
            result.put("ok", true);
            result.put("items", items);
            result.put("count", items.length());
        } catch (Exception ignored) { }
        return result.toString();
    }

    public static String replyToRecent(String actionJson) {
        String appFilter = "whatsapp";
        String replyText = "";
        int targetIndex = 0;
        String targetName = "";
        try {
            JSONObject action = new JSONObject(actionJson == null ? "{}" : actionJson);
            appFilter = action.optString("app", "whatsapp").toLowerCase();
            replyText = action.optString("text", "").trim();
            targetIndex = action.optInt("target_index", 0);
            targetName = normalizeName(action.optString("target_name", ""));
        } catch (Exception ignored) { }

        JSONObject result = new JSONObject();
        if (replyText.isEmpty()) {
            return errorJson("Reply text was empty.");
        }
        if (connectedService == null) {
            return errorJson("Notification service is not connected yet. Reopen Vamsi Companion or wait for a new notification.");
        }

        synchronized (RECENT) {
            int visibleIndex = 0;
            for (NotificationEntry entry : RECENT) {
                if (entry.isEmpty()) continue;
                if ("whatsapp".equals(appFilter) && !entry.packageName.startsWith("com.whatsapp")) continue;
                visibleIndex++;
                if (targetIndex > 0 && visibleIndex != targetIndex) continue;
                if (!targetName.isEmpty() && !entry.matchesTargetName(targetName)) continue;
                ReplyAction replyAction = entry.findReplyAction();
                if (replyAction == null) {
                    if (targetIndex > 0 || !targetName.isEmpty()) {
                        return errorJson("That notification does not have a quick-reply action.");
                    }
                    continue;
                }
                try {
                    Intent fillInIntent = new Intent();
                    Bundle results = new Bundle();
                    for (RemoteInput remoteInput : replyAction.remoteInputs) {
                        results.putCharSequence(remoteInput.getResultKey(), replyText);
                    }
                    RemoteInput.addResultsToIntent(replyAction.remoteInputs, fillInIntent, results);
                    replyAction.pendingIntent.send(connectedService, 0, fillInIntent);
                    result.put("ok", true);
                    result.put("app", appLabel(entry.packageName));
                    result.put("title", entry.title);
                    result.put("text", replyText);
                    result.put("target_index", visibleIndex);
                    return result.toString();
                } catch (PendingIntent.CanceledException error) {
                    return errorJson("That notification reply action expired. Ask them to send a new message and try again.");
                } catch (Exception error) {
                    return errorJson("Android could not send the reply through that notification.");
                }
            }
        }
        if (targetIndex > 0) {
            return errorJson("I could not find notification number " + targetIndex + ".");
        }
        if (!targetName.isEmpty()) {
            return errorJson("I could not find a recent WhatsApp notification from " + targetName + ".");
        }
        if ("whatsapp".equals(appFilter)) {
            return errorJson("I found no recent WhatsApp notification with a quick-reply action.");
        }
        return errorJson("I found no recent notification with a quick-reply action.");
    }

    private static NotificationEntry fromStatusBarNotification(StatusBarNotification sbn) {
        String title = "";
        String text = "";
        String bigText = "";
        if (sbn != null && sbn.getNotification() != null) {
            Bundle extras = sbn.getNotification().extras;
            if (extras != null) {
                title = clean(extras.getCharSequence(Notification.EXTRA_TITLE));
                text = clean(extras.getCharSequence(Notification.EXTRA_TEXT));
                bigText = clean(extras.getCharSequence(Notification.EXTRA_BIG_TEXT));
                if (bigText.length() > text.length()) text = bigText;
            }
        }
        String packageName = sbn == null ? "" : sbn.getPackageName();
        String key = sbn == null ? String.valueOf(System.currentTimeMillis()) : sbn.getKey();
        long postedAt = sbn == null ? System.currentTimeMillis() : sbn.getPostTime();
        Notification.Action[] actions = sbn == null || sbn.getNotification() == null ? null : sbn.getNotification().actions;
        return new NotificationEntry(key, packageName, title, text, postedAt, actions);
    }

    private static void addLocked(NotificationEntry entry) {
        if (entry == null || entry.packageName.equals("com.vamsi.companion")) return;
        RECENT.add(0, entry);
        while (RECENT.size() > MAX_NOTIFICATIONS) {
            RECENT.remove(RECENT.size() - 1);
        }
    }

    private static String clean(CharSequence value) {
        if (value == null) return "";
        return value.toString().replaceAll("\\s+", " ").trim();
    }

    private static class NotificationEntry {
        final String key;
        final String packageName;
        final String title;
        final String text;
        final long postedAt;
        final Notification.Action[] actions;

        NotificationEntry(String key, String packageName, String title, String text, long postedAt, Notification.Action[] actions) {
            this.key = key == null ? "" : key;
            this.packageName = packageName == null ? "" : packageName;
            this.title = title == null ? "" : title;
            this.text = text == null ? "" : text;
            this.postedAt = postedAt;
            this.actions = actions;
        }

        boolean isEmpty() {
            return title.isEmpty() && text.isEmpty();
        }

        JSONObject toJson() {
            JSONObject obj = new JSONObject();
            try {
                obj.put("package", packageName);
                obj.put("app", appLabel(packageName));
                obj.put("title", title);
                obj.put("text", text);
                obj.put("posted_at", postedAt);
                obj.put("can_reply", findReplyAction() != null);
            } catch (Exception ignored) { }
            return obj;
        }

        ReplyAction findReplyAction() {
            if (actions == null) return null;
            for (Notification.Action action : actions) {
                if (action == null || action.actionIntent == null) continue;
                RemoteInput[] remoteInputs = action.getRemoteInputs();
                if (remoteInputs == null || remoteInputs.length == 0) continue;
                return new ReplyAction(action.actionIntent, remoteInputs);
            }
            return null;
        }

        boolean matchesTargetName(String targetName) {
            if (targetName == null || targetName.isEmpty()) return false;
            String haystack = normalizeName(title + " " + text);
            return haystack.contains(targetName);
        }
    }

    private static class ReplyAction {
        final PendingIntent pendingIntent;
        final RemoteInput[] remoteInputs;

        ReplyAction(PendingIntent pendingIntent, RemoteInput[] remoteInputs) {
            this.pendingIntent = pendingIntent;
            this.remoteInputs = remoteInputs;
        }
    }

    private static String errorJson(String message) {
        JSONObject result = new JSONObject();
        try {
            result.put("ok", false);
            result.put("error", message);
        } catch (Exception ignored) { }
        return result.toString();
    }

    private static String normalizeName(String value) {
        if (value == null) return "";
        return value
                .toLowerCase()
                .replaceAll("[\"'“”‘’]", "")
                .replaceAll("[^a-z0-9]+", " ")
                .trim();
    }

    private static String appLabel(String packageName) {
        if (packageName == null) return "Unknown";
        if (packageName.startsWith("com.whatsapp")) return packageName.equals("com.whatsapp.w4b") ? "WhatsApp Business" : "WhatsApp";
        if (packageName.equals("com.google.android.youtube")) return "YouTube";
        if (packageName.equals("com.android.chrome")) return "Chrome";
        if (packageName.equals("com.google.android.gm")) return "Gmail";
        if (packageName.equals("com.google.android.apps.messaging")) return "Messages";
        return packageName;
    }
}
