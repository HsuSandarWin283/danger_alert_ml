package com.danger.alert;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.getcapacitor.BridgeActivity;
import com.google.android.gms.common.ConnectionResult;
import com.google.android.gms.common.GoogleApiAvailability;
import com.google.firebase.firestore.FirebaseFirestore;
import com.google.firebase.messaging.FirebaseMessaging;

import java.util.HashMap;
import java.util.Map;

public class MainActivity extends BridgeActivity {
    private static final String TAG = "MainActivity";
    private static final int MAX_RETRIES = 5;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(BackgroundMonitorPlugin.class);
        super.onCreate(savedInstanceState);

        createNotificationChannels();
        handleNavigationIntent(getIntent());

        java.util.List<String> perms = new java.util.ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
                perms.add(android.Manifest.permission.POST_NOTIFICATIONS);
            }
        }
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            perms.add(android.Manifest.permission.ACCESS_FINE_LOCATION);
        }
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_COARSE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            perms.add(android.Manifest.permission.ACCESS_COARSE_LOCATION);
        }
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            perms.add(android.Manifest.permission.RECORD_AUDIO);
        }
        if (!perms.isEmpty()) {
            ActivityCompat.requestPermissions(this, perms.toArray(new String[0]), 100);
        }

        new Handler(Looper.getMainLooper()).postDelayed(this::tryFetchToken, 2000);
    }

    private void createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager == null) return;

            NotificationStrings ns = new NotificationStrings(this);

            NotificationChannel monitoringChannel = new NotificationChannel(
                    "danger_monitoring", ns.channelMonitoringName(),
                    NotificationManager.IMPORTANCE_LOW);
            monitoringChannel.setDescription(ns.channelMonitoringDesc());
            monitoringChannel.setSound(null, null);
            manager.createNotificationChannel(monitoringChannel);

            NotificationChannel alertChannel = new NotificationChannel(
                    "danger_alert", ns.channelAlertsName(),
                    NotificationManager.IMPORTANCE_HIGH);
            alertChannel.setDescription(ns.channelAlertsDesc());
            alertChannel.enableVibration(true);
            alertChannel.setVibrationPattern(new long[]{0, 500, 200, 500});
            alertChannel.enableLights(true);
            alertChannel.setLightColor(Color.RED);
            manager.createNotificationChannel(alertChannel);

            Log.i(TAG, "Notification channels created");
        }
    }

    private void tryFetchToken() {
        tryFetchTokenWithRetry(0);
    }

    private void tryFetchTokenWithRetry(int attempt) {
        int gpsStatus = GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(this);
        if (gpsStatus != ConnectionResult.SUCCESS) {
            String msg = "Google Play Services not available: code=" + gpsStatus;
            Log.e(TAG, msg);
            getSharedPreferences("capacitor", MODE_PRIVATE)
                    .edit().putString("fcm_error", msg).apply();
            if (attempt < MAX_RETRIES) {
                new Handler(Looper.getMainLooper()).postDelayed(
                        () -> tryFetchTokenWithRetry(attempt + 1), 5000);
            }
            return;
        }

        Log.i(TAG, "GPS available, attempt " + (attempt + 1) + " to get FCM token...");
        FirebaseMessaging.getInstance().getToken()
                .addOnCompleteListener(task -> {
                    if (!task.isSuccessful()) {
                        String errMsg = task.getException() != null ? task.getException().getMessage() : "unknown";
                        Log.e(TAG, "FCM attempt " + (attempt + 1) + " failed: " + errMsg);
                        getSharedPreferences("capacitor", MODE_PRIVATE)
                                .edit().putString("fcm_error", "getToken failed: " + errMsg).apply();
                        if (attempt < MAX_RETRIES) {
                            new Handler(Looper.getMainLooper()).postDelayed(
                                    () -> tryFetchTokenWithRetry(attempt + 1), 5000);
                        }
                        return;
                    }
                    String token = task.getResult();
                    if (token == null || token.isEmpty()) {
                        Log.w(TAG, "FCM token empty, attempt " + (attempt + 1));
                        getSharedPreferences("capacitor", MODE_PRIVATE)
                                .edit().putString("fcm_error", "token is null/empty").apply();
                        if (attempt < MAX_RETRIES) {
                            new Handler(Looper.getMainLooper()).postDelayed(
                                    () -> tryFetchTokenWithRetry(attempt + 1), 5000);
                        }
                        return;
                    }
                    Log.i(TAG, "FCM TOKEN OK: " + token.substring(0, Math.min(40, token.length())));
                    getSharedPreferences("capacitor", MODE_PRIVATE)
                            .edit()
                            .putString("pending_fcm_token", token)
                            .remove("fcm_error")
                            .apply();
                });
    }

    public static void saveTokenToFirestore(String userId, String token) {
        FirebaseFirestore db = FirebaseFirestore.getInstance();
        Map<String, Object> updates = new HashMap<>();
        updates.put("fcmToken", token);
        db.collection("users").document(userId)
                .set(updates, com.google.firebase.firestore.SetOptions.merge())
                .addOnSuccessListener(v -> Log.i(TAG, "FCM token saved to Firestore: " + userId))
                .addOnFailureListener(e -> Log.e(TAG, "Firestore save failed", e));
    }

    private String getCurrentUserId() {
        SharedPreferences prefs = getSharedPreferences("capacitor", MODE_PRIVATE);
        String userId = prefs.getString("current_user_id", "");
        return userId != null ? userId : "";
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleNavigationIntent(intent);
    }

    private void handleNavigationIntent(Intent intent) {
        if (intent == null) return;
        String route = null;
        if (intent.hasExtra("navigate_to")) {
            route = intent.getStringExtra("navigate_to");
        } else if (intent.hasExtra("route")) {
            route = intent.getStringExtra("route");
        }
        if (route != null && !route.isEmpty()) {
            Log.i(TAG, "Saving pending navigate_to: " + route);
            getSharedPreferences("capacitor", MODE_PRIVATE)
                    .edit().putString("pending_navigate_to", route).apply();
            intent.removeExtra("navigate_to");
            intent.removeExtra("route");
        }
    }
}
