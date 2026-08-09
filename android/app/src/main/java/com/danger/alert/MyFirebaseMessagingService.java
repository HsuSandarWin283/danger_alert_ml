package com.danger.alert;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
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

    public static void fetchAndSaveToken() {
        FirebaseMessaging.getInstance().getToken()
                .addOnCompleteListener(task -> {
                    if (!task.isSuccessful()) {
                        Log.w(TAG, "FCM token fetch failed", task.getException());
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

        FirebaseFirestore db = FirebaseFirestore.getInstance();
        Map<String, Object> updates = new HashMap<>();
        updates.put("fcmToken", token);

        db.collection("users").document(userId)
                .update(updates)
                .addOnSuccessListener(aVoid -> Log.i(TAG, "FCM token saved to Firestore for user: " + userId))
                .addOnFailureListener(e -> Log.e(TAG, "Failed to save FCM token", e));
    }

    private static String getActiveUserId() {
        return null;
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
        Log.i(TAG, "Push notification received: " + message.getNotification());

        String title = "";
        String body = "";
        if (message.getNotification() != null) {
            title = message.getNotification().getTitle() != null ? message.getNotification().getTitle() : "";
            body = message.getNotification().getBody() != null ? message.getNotification().getBody() : "";
        }

        Map<String, String> data = message.getData();
        String type = data.get("type");

        if ("help_message".equals(type)) {
            showHelpNotification(title, body);
        }
    }

    private void showHelpNotification(String title, String body) {
        createHelpChannel();

        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        intent.putExtra("navigate_to", "/help-history");

        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, HELP_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .setVibrate(new long[]{0, 500, 200, 500})
                .setLights(Color.RED, 500, 500);

        try {
            NotificationManagerCompat.from(this).notify(HELP_NOTIFICATION_ID, builder.build());
            Log.i(TAG, "Help notification displayed");
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
