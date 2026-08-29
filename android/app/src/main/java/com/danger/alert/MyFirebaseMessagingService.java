package com.danger.alert;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.os.Build;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import com.google.firebase.firestore.FirebaseFirestore;
import com.google.firebase.messaging.FirebaseMessaging;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.HashMap;
import java.util.Map;

public class MyFirebaseMessagingService extends FirebaseMessagingService {
    private static final String TAG = "FCMService";
    private static final String HELP_CHANNEL_ID = "help_messages";
    private static final int HELP_NOTIFICATION_ID = 3001;

    public static void fetchAndSaveToken(Context context) {
        FirebaseMessaging.getInstance().getToken()
                .addOnCompleteListener(task -> {
                    if (!task.isSuccessful()) {
                        Log.w(TAG, "FCM token fetch failed", task.getException());
                        try {
                            Intent offlineIntent = new Intent(context, MonitoringService.class);
                            offlineIntent.setAction(MonitoringService.ACTION_TRIGGER_OFFLINE_ALERT);
                            context.startService(offlineIntent);
                        } catch (Exception e) {
                            Log.w(TAG, "Failed to trigger offline alert", e);
                        }
                        return;
                    }
                    String token = task.getResult();
                    Log.i(TAG, "FCM token: " + token);
                    saveTokenToFirestore(token);
                });
    }

    private static void saveTokenToFirestore(String token) {
        String userId = getActiveUserId();
        if (userId == null || userId.isEmpty()) {
            Log.w(TAG, "No active user ID, saving token locally");
            return;
        }
        try {
            android.content.Context context = com.google.firebase.FirebaseApp.getInstance().getApplicationContext();
            android.content.SharedPreferences prefs = context.getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE);
            String authToken = prefs.getString("firebase_auth_token", "");
            String apiKey = prefs.getString("firebase_api_key", "");
            String projectId = prefs.getString("firebase_project_id", "");
            if (authToken == null || authToken.isEmpty() || apiKey == null || apiKey.isEmpty() || projectId == null || projectId.isEmpty()) {
                Log.w(TAG, "No auth config available for Firestore save");
                return;
            }
            String url = "https://firestore.googleapis.com/v1/projects/" + projectId + "/databases/(default)/documents/users/" + userId + "?key=" + apiKey;
            String body = "{\"fields\":{\"fcmToken\":{\"stringValue\":\"" + token + "\"}}}";
            java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();
            c.setRequestMethod("PATCH");
            c.setRequestProperty("Content-Type", "application/json");
            c.setRequestProperty("Authorization", "Bearer " + authToken);
            c.setDoOutput(true);
            java.io.OutputStream os = c.getOutputStream();
            os.write(body.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            os.close();
            int code = c.getResponseCode();
            if (code >= 200 && code < 300) {
                Log.i(TAG, "FCM token saved to Firestore via REST: " + userId);
            } else {
                Log.e(TAG, "Firestore REST save failed: " + code);
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to save FCM token to Firestore", e);
        }
    }

    private static String getActiveUserId() {
        android.content.SharedPreferences prefs = com.google.firebase.FirebaseApp.getInstance()
                .getApplicationContext()
                .getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE);
        String userId = prefs.getString("current_user_id", "");
        return (userId != null && !userId.isEmpty()) ? userId : null;
    }

    @Override
    public void onNewToken(@NonNull String token) {
        super.onNewToken(token);
        Log.i(TAG, "New FCM token received");
        saveTokenToFirestore(token);
    }

    @Override
    public void onMessageReceived(@NonNull RemoteMessage message) {
        super.onMessageReceived(message);
        Log.i(TAG, "Push received: " + message.getData());

        Map<String, String> data = message.getData();
        String type = data.get("type");

        if ("help_message".equals(type)) {
            String title = data.get("title");
            String body = data.get("body");
            String senderName = data.get("senderName");
            String senderPhone = data.get("senderPhone");
            String dangerType = data.get("dangerType");
            String locationName = data.get("locationName");
            String alertMsg = data.get("alertMsg");
            NotificationStrings ns = new NotificationStrings(this);
            showHelpFullScreen(
                    title != null ? title : ns.helpAlertDefaultTitle(),
                    body != null ? body : ns.helpAlertDefaultBody(),
                    senderName != null ? senderName : "",
                    dangerType != null ? dangerType : "unknown",
                    locationName != null ? locationName : "",
                    alertMsg != null ? alertMsg : "",
                    senderPhone != null ? senderPhone : "");
        }
    }

    private void showHelpFullScreen(String title, String body, String senderName, String dangerType, String locationName, String alertMsg, String senderPhone) {
        createHelpChannel();

        Intent alertIntent = new Intent(this, HelpAlertActivity.class);
        alertIntent.putExtra("title", title);
        alertIntent.putExtra("body", body);
        alertIntent.putExtra("senderName", senderName);
        alertIntent.putExtra("dangerType", dangerType);
        alertIntent.putExtra("locationName", locationName);
        alertIntent.putExtra("alertMsg", alertMsg != null ? alertMsg : body);
        alertIntent.putExtra("senderPhone", senderPhone != null ? senderPhone : "");
        alertIntent.putExtra("action", "received");
        alertIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);

        PendingIntent fullScreenPending = PendingIntent.getActivity(
                this, 1, alertIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE
        );

        PendingIntent contentPending = PendingIntent.getActivity(
                this, 1, alertIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, HELP_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setFullScreenIntent(fullScreenPending, true)
                .setContentIntent(contentPending)
                .setAutoCancel(true)
                .setVibrate(new long[]{0, 500, 200, 500})
                .setLights(Color.RED, 500, 500)
                .setDefaults(android.app.Notification.DEFAULT_VIBRATE | android.app.Notification.DEFAULT_SOUND);

        try {
            NotificationManagerCompat.from(this).notify(HELP_NOTIFICATION_ID, builder.build());
            Log.i(TAG, "Help full-screen notification displayed");

            try {
                startActivity(alertIntent);
            } catch (Exception e) {
                Log.w(TAG, "Cannot start HelpAlertActivity from background", e);
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to show help notification", e);
        }
    }

    private void createHelpChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null && manager.getNotificationChannel(HELP_CHANNEL_ID) == null) {
                NotificationChannel channel = new NotificationChannel(
                        HELP_CHANNEL_ID, "Help Messages",
                        NotificationManager.IMPORTANCE_HIGH);
                channel.setDescription("Help request notifications");
                channel.enableVibration(true);
                channel.setVibrationPattern(new long[]{0, 500, 200, 500});
                channel.enableLights(true);
                channel.setLightColor(Color.RED);
                manager.createNotificationChannel(channel);
            }
        }
    }
}
