package com.vamsi.companion;

import android.app.Notification;
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

    @Override
    public void onListenerConnected() {
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
        return new NotificationEntry(key, packageName, title, text, postedAt);
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

        NotificationEntry(String key, String packageName, String title, String text, long postedAt) {
            this.key = key == null ? "" : key;
            this.packageName = packageName == null ? "" : packageName;
            this.title = title == null ? "" : title;
            this.text = text == null ? "" : text;
            this.postedAt = postedAt;
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
            } catch (Exception ignored) { }
            return obj;
        }
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