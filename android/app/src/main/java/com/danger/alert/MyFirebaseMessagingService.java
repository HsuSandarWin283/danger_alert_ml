package com.danger.alert;

import android.util.Log;

import androidx.annotation.NonNull;

import com.google.firebase.firestore.FirebaseFirestore;
import com.google.firebase.messaging.FirebaseMessaging;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.HashMap;
import java.util.Map;

public class MyFirebaseMessagingService extends FirebaseMessagingService {
    private static final String TAG = "FCMService";

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
    }
}
