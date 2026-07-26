package com.danger.alert;

import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.util.Log;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import org.json.JSONObject;

@CapacitorPlugin(name = "BackgroundMonitor")
public class BackgroundMonitorPlugin extends Plugin {

    private static final String TAG = "BackgroundMonitor";

    @PluginMethod
    public void startMonitoring(PluginCall call) {
        String apiUrl = call.getString("apiUrl", "https://danger-alert-ml.onrender.com");

        Intent intent = new Intent(getContext(), MonitoringService.class);
        intent.setAction(MonitoringService.ACTION_START);
        intent.putExtra(MonitoringService.EXTRA_API_URL, apiUrl);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getContext().startForegroundService(intent);
        } else {
            getContext().startService(intent);
        }

        JSObject result = new JSObject();
        result.put("running", true);
        call.resolve(result);
    }

    @PluginMethod
    public void stopMonitoring(PluginCall call) {
        Intent intent = new Intent(getContext(), MonitoringService.class);
        intent.setAction(MonitoringService.ACTION_STOP);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getContext().startForegroundService(intent);
        } else {
            getContext().startService(intent);
        }

        JSObject result = new JSObject();
        result.put("running", false);
        call.resolve(result);
    }

    @PluginMethod
    public void saveFirebaseConfig(PluginCall call) {
        String apiKey = call.getString("apiKey", "");
        String projectId = call.getString("projectId", "");
        String userId = call.getString("userId", "");
        String authToken = call.getString("authToken", "");
        String phone = call.getString("phone", "");
        String fcmToken = call.getString("fcmToken", "");
        String serverKey = call.getString("serverKey", "");
        String clientEmail = call.getString("clientEmail", "");
        String privateKey = call.getString("privateKey", "");

        SharedPreferences.Editor editor = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE).edit();
        editor.putString("firebase_api_key", apiKey);
        editor.putString("firebase_project_id", projectId);
        editor.putString("current_user_id", userId);
        editor.putString("firebase_auth_token", authToken);
        editor.putString("current_user_phone", phone);
        editor.putString("fcm_token", fcmToken);
        editor.putString("fcm_server_key", serverKey);
        editor.putString("fcm_client_email", clientEmail);
        editor.putString("fcm_private_key", privateKey);
        editor.apply();

        if (!userId.isEmpty()) {
            String pendingToken = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                    .getString("pending_fcm_token", null);
            if (pendingToken != null && !pendingToken.isEmpty()) {
                com.danger.alert.MainActivity.saveTokenToFirestore(userId, pendingToken);
                editor.putString("fcm_token", pendingToken);
                editor.remove("pending_fcm_token");
                editor.apply();
                Log.i(TAG, "Saved pending FCM token to Firestore for user: " + userId);
            } else {
                Log.i(TAG, "No pending token, fetching fresh token for user: " + userId);
                com.google.firebase.messaging.FirebaseMessaging.getInstance().getToken()
                        .addOnCompleteListener(task -> {
                            if (task.isSuccessful() && task.getResult() != null) {
                                String token = task.getResult();
                                Log.i(TAG, "Fresh FCM token: " + token.substring(0, Math.min(40, token.length())));
                                com.danger.alert.MainActivity.saveTokenToFirestore(userId, token);
                                editor.putString("fcm_token", token);
                                editor.apply();
                            } else {
                                Log.e(TAG, "Failed to get fresh FCM token", task.getException());
                            }
                        });
            }
        }

        JSObject result = new JSObject();
        result.put("saved", true);
        call.resolve(result);
    }

    @PluginMethod
    public void saveTrustedMembers(PluginCall call) {
        String membersJson = call.getString("members", "[]");
        Log.i(TAG, "Saving trusted members: " + membersJson);
        getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .edit()
                .putString("trusted_members", membersJson)
                .apply();
        JSObject result = new JSObject();
        result.put("saved", true);
        call.resolve(result);
    }

    @PluginMethod
    public void sendTrustedAlert(PluginCall call) {
        String dangerType = call.getString("dangerType", "unknown");
        double confidence = call.getDouble("confidence", 0.0);
        String alertMsg = call.getString("alertMsg", "");
        String clientEmail = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .getString("fcm_client_email", null);
        String privateKey = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .getString("fcm_private_key", null);

        try {
            JSArray membersArray = call.getArray("members");
            String accessToken = FcmHelper.getAccessToken(getContext());

            int sent = 0;
            if (membersArray != null) {
                for (int i = 0; i < membersArray.length(); i++) {
                    JSONObject member = membersArray.getJSONObject(i);
                    String fcmToken = member.getString("fcmToken");
                    if (fcmToken == null || fcmToken.isEmpty()) continue;
                    try {
                        FcmHelper.sendPush(accessToken, fcmToken,
                                "DANGER: " + dangerType.toUpperCase(), alertMsg);
                        sent++;
                    } catch (Exception e) {
                        Log.w(TAG, "FCM failed for member " + i, e);
                    }
                }
            }

            JSObject result = new JSObject();
            result.put("sent", sent);
            result.put("total", membersArray != null ? membersArray.length() : 0);
            call.resolve(result);
        } catch (Exception e) {
            Log.e(TAG, "sendTrustedAlert failed", e);
            call.reject("Failed to send alert: " + e.getMessage());
        }
    }

    @PluginMethod
    public void isRunning(PluginCall call) {
        JSObject result = new JSObject();
        result.put("running", true);
        call.resolve(result);
    }

    @PluginMethod
    public void fetchFcmToken(PluginCall call) {
        String userId = call.getString("userId", "");
        Log.i(TAG, "fetchFcmToken called for userId: " + userId);

        try {
            com.google.firebase.messaging.FirebaseMessaging.getInstance().getToken()
                    .addOnCompleteListener(task -> {
                        if (!task.isSuccessful()) {
                            Exception e = task.getException();
                            String errMsg = e != null ? e.getMessage() : "unknown error";
                            Log.e(TAG, "FCM token fetch failed: " + errMsg, e);
                            call.reject("FCM token fetch failed: " + errMsg);
                            return;
                        }
                        String token = task.getResult();
                        Log.i(TAG, "FCM token obtained: " + (token != null ? token.substring(0, Math.min(30, token.length())) + "..." : "null"));

                        if (token != null && !userId.isEmpty()) {
                            String authToken = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                                    .getString("firebase_auth_token", null);
                            String apiKey = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                                    .getString("firebase_api_key", "");
                            String projectId = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                                    .getString("firebase_project_id", "");

                            if (authToken != null && !authToken.isEmpty() && !apiKey.isEmpty() && !projectId.isEmpty()) {
                                String url = "https://firestore.googleapis.com/v1/projects/"
                                        + projectId + "/databases/(default)/documents/users/" + userId + "?key=" + apiKey;
                                String body = "{\"fields\":{\"fcmToken\":{\"stringValue\":\"" + token + "\"}}}";
                                try {
                                    java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();
                                    c.setRequestMethod("PATCH");
                                    c.setRequestProperty("Content-Type", "application/json");
                                    c.setRequestProperty("Authorization", "Bearer " + authToken);
                                    c.setDoOutput(true);
                                    java.io.OutputStream os = c.getOutputStream();
                                    os.write(body.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                                    os.close();
                                    int code = c.getResponseCode();
                                    Log.i(TAG, "Firestore REST write: " + code);
                                    if (code >= 200 && code < 300) {
                                        getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                                                .edit().putString("fcm_token", token).apply();
                                    }
                                } catch (Exception e) {
                                    Log.e(TAG, "Firestore REST write failed", e);
                                }
                            } else {
                                Log.w(TAG, "No auth token or apiKey, saving locally only");
                                getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                                        .edit().putString("fcm_token", token).apply();
                            }
                        }

                        JSObject result = new JSObject();
                        result.put("fcmToken", token != null ? token : "");
                        call.resolve(result);
                    });
        } catch (Exception e) {
            Log.e(TAG, "fetchFcmToken exception", e);
            call.reject("Exception: " + e.getMessage());
        }
    }
}
