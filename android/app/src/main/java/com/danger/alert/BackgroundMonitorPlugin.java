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

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import android.location.Address;
import android.location.Geocoder;
import android.location.Location;
import android.location.LocationManager;
import android.os.Build;
import android.util.Log;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationServices;

@CapacitorPlugin(name = "BackgroundMonitor")
public class BackgroundMonitorPlugin extends Plugin {

    private static final String TAG = "BackgroundMonitor";
    private static BackgroundMonitorPlugin instance;

    @Override
    public void load() {
        instance = this;
    }

    public static void notifyStateChange(boolean running) {
        if (instance != null) {
            JSObject data = new JSObject();
            data.put("running", running);
            instance.notifyListeners("monitoringStateChanged", data);
            Log.i(TAG, "Notified JS: monitoringStateChanged running=" + running);
        }
    }

    @PluginMethod
    public void startMonitoring(PluginCall call) {
        String apiUrl = call.getString("apiUrl", "https://danger-alert-to-trusted.onrender.com");

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
        String displayName = call.getString("displayName", "");

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
        editor.putString("user_display_name", displayName);
        editor.apply();

        if (!userId.isEmpty()) {
            new Thread(() -> {
                String pendingToken = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                        .getString("pending_fcm_token", null);
                if (pendingToken != null && !pendingToken.isEmpty()) {
                    try {
                        com.danger.alert.MainActivity.saveTokenToFirestore(userId, pendingToken);
                    } catch (Exception e) {
                        Log.e(TAG, "Failed to save pending FCM token to Firestore", e);
                    }
                    SharedPreferences.Editor ed = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE).edit();
                    ed.putString("fcm_token", pendingToken);
                    ed.remove("pending_fcm_token");
                    ed.apply();
                    Log.i(TAG, "Saved pending FCM token to Firestore for user: " + userId);
                } else {
                    Log.i(TAG, "No pending token, fetching fresh token for user: " + userId);
                    try {
                        com.google.firebase.messaging.FirebaseMessaging.getInstance().getToken()
                                .addOnCompleteListener(task -> {
                                    if (task.isSuccessful() && task.getResult() != null) {
                                        String token = task.getResult();
                                        Log.i(TAG, "Fresh FCM token: " + token.substring(0, Math.min(40, token.length())));
                                        try {
                                            com.danger.alert.MainActivity.saveTokenToFirestore(userId, token);
                                        } catch (Exception e) {
                                            Log.e(TAG, "Failed to save fresh FCM token to Firestore", e);
                                        }
                                        SharedPreferences.Editor ed = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE).edit();
                                        ed.putString("fcm_token", token);
                                        ed.apply();
                                    } else {
                                        Log.e(TAG, "Failed to get fresh FCM token", task.getException());
                                    }
                                });
                    } catch (Exception e) {
                        Log.e(TAG, "Failed to fetch FCM token", e);
                    }
                }
            }).start();
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

        new Thread(() -> {
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
                            NotificationStrings ns = new NotificationStrings(getContext());
                            FcmHelper.sendPush(accessToken, fcmToken,
                                    ns.pushTitle(dangerType), alertMsg);
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
        }).start();
    }

    @PluginMethod
    public void sendEmergencyAlert(PluginCall call) {
        String dangerType = call.getString("dangerType", "trouble");
        double confidence = call.getDouble("confidence", 1.0);
        String alertMsg = call.getString("alertMsg", "Emergency alert: trouble detected");
        String currentUserId = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .getString("current_user_id", null);
        String projectId = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .getString("firebase_project_id", null);
        final String[] userNameHolder = new String[] { getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .getString("user_display_name", "") };
        final String[] userPhoneHolder = new String[] { getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .getString("current_user_phone", "") };

        if (currentUserId == null || currentUserId.isEmpty() || projectId == null || projectId.isEmpty()) {
            call.reject("Missing Firebase config");
            return;
        }

        new Thread(() -> {
            try {
                String accessToken = FcmHelper.getAccessToken(getContext());

                if (userNameHolder[0] == null || userNameHolder[0].isEmpty()) {
                    try {
                        String userDoc = httpGet("https://firestore.googleapis.com/v1/projects/" + projectId + "/databases/(default)/documents/users/" + currentUserId, accessToken);
                        if (userDoc != null && userDoc.contains("stringValue")) {
                            org.json.JSONObject userDocObj = new org.json.JSONObject(userDoc);
                            org.json.JSONObject userFields = userDocObj.optJSONObject("fields");
                            if (userFields != null) {
                                org.json.JSONObject nameObj = userFields.optJSONObject("name");
                                if (nameObj != null) userNameHolder[0] = nameObj.optString("stringValue", "");
                            }
                        }
                    } catch (Exception e) {
                        Log.w(TAG, "Failed to get user name from Firestore: " + e.getMessage());
                    }
                }

                if (userPhoneHolder[0] == null || userPhoneHolder[0].isEmpty()) {
                    try {
                        String userDoc = httpGet("https://firestore.googleapis.com/v1/projects/" + projectId + "/databases/(default)/documents/users/" + currentUserId, accessToken);
                        if (userDoc != null && userDoc.contains("stringValue")) {
                            org.json.JSONObject userDocObj = new org.json.JSONObject(userDoc);
                            org.json.JSONObject userFields = userDocObj.optJSONObject("fields");
                            if (userFields != null) {
                                org.json.JSONObject phoneObj = userFields.optJSONObject("phone");
                                if (phoneObj != null) userPhoneHolder[0] = phoneObj.optString("stringValue", "");
                            }
                        }
                    } catch (Exception e) {
                        Log.w(TAG, "Failed to get user phone from Firestore: " + e.getMessage());
                    }
                }

                final double[] lat = {0};
                final double[] lng = {0};
                final String[] locationName = {""};

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    if (getContext().checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION) == android.content.pm.PackageManager.PERMISSION_GRANTED ||
                        getContext().checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION) == android.content.pm.PackageManager.PERMISSION_GRANTED) {

                        FusedLocationProviderClient client = LocationServices.getFusedLocationProviderClient(getContext());
                        final CountDownLatch latch = new CountDownLatch(1);
                        final boolean[] done = {false};

                        client.getLastLocation().addOnCompleteListener(task -> {
                            if (!done[0]) {
                                done[0] = true;
                                if (task.isSuccessful() && task.getResult() != null) {
                                    Location loc = task.getResult();
                                    lat[0] = loc.getLatitude();
                                    lng[0] = loc.getLongitude();
                                    locationName[0] = String.format(Locale.getDefault(), "%.4f, %.4f", lat[0], lng[0]);
                                    try {
                                        Geocoder geo = new Geocoder(getContext(), Locale.getDefault());
                                        List<Address> addrs = geo.getFromLocation(lat[0], lng[0], 1);
                                        if (addrs != null && !addrs.isEmpty()) {
                                            Address a = addrs.get(0);
                                            StringBuilder sb = new StringBuilder();
                                            for (int i = 0; i <= Math.min(a.getMaxAddressLineIndex(), 2); i++) {
                                                if (sb.length() > 0) sb.append(", ");
                                                sb.append(a.getAddressLine(i));
                                            }
                                            locationName[0] = sb.toString();
                                        }
                                    } catch (Exception e) {
                                        Log.w(TAG, "Geocoder failed", e);
                                    }
                                }
                                latch.countDown();
                            }
                        });

                        try {
                            latch.await(3, TimeUnit.SECONDS);
                        } catch (Exception e) {
                            Log.w(TAG, "Location fetch timeout", e);
                        }
                    }
                }

                String queryBody = "{\"structuredQuery\":{\"from\":[{\"collectionId\":\"group_members\"}],"
                        + "\"where\":{\"fieldFilter\":{\"field\":{\"fieldPath\":\"groupId\"},"
                        + "\"op\":\"EQUAL\","
                        + "\"value\":{\"stringValue\":\"" + currentUserId + "\"}}},"
                        + "\"limit\":100}}";
                String membersUrl = "https://firestore.googleapis.com/v1/projects/" + projectId + "/databases/(default)/documents:runQuery";
                String membersJson = httpPost(membersUrl, queryBody, accessToken);

                java.util.ArrayList<String> memberUids = new java.util.ArrayList<>();
                java.util.ArrayList<String> memberTokens = new java.util.ArrayList<>();
                int parsedCount = 0;

                if (membersJson != null && membersJson.contains("document")) {
                    org.json.JSONArray docsArray = new org.json.JSONArray(membersJson);
                    parsedCount = docsArray.length();

                    for (int i = 0; i < docsArray.length(); i++) {
                        org.json.JSONObject docWrapper = docsArray.getJSONObject(i);
                        org.json.JSONObject docObj = docWrapper.optJSONObject("document");
                        if (docObj == null) continue;
                        org.json.JSONObject fields = docObj.optJSONObject("fields");
                        if (fields == null) continue;

                        org.json.JSONObject userIdField = fields.optJSONObject("userId");
                        String memberUid = userIdField != null ? userIdField.optString("stringValue", "") : "";
                        if (memberUid.isEmpty()) continue;
                        memberUids.add(memberUid);

                        String memberDoc = httpGet("https://firestore.googleapis.com/v1/projects/" + projectId + "/databases/(default)/documents/users/" + memberUid, accessToken);
                        String fcmToken = null;
                        if (memberDoc != null && memberDoc.contains("stringValue")) {
                            org.json.JSONObject memberDocObj = new org.json.JSONObject(memberDoc);
                            org.json.JSONObject memberFields = memberDocObj.optJSONObject("fields");
                            if (memberFields != null) {
                                org.json.JSONObject fcmObj = memberFields.optJSONObject("fcmToken");
                                if (fcmObj != null) fcmToken = fcmObj.optString("stringValue", "");
                            }
                        }
                        if (fcmToken == null || fcmToken.isEmpty()) continue;
                        memberTokens.add(fcmToken.trim().replaceAll("\\s+", ""));
                    }
                }

                int sent = 0;
                NotificationStrings nsEmergency = new NotificationStrings(getContext());
                String notificationBody = (userNameHolder[0] != null && !userNameHolder[0].isEmpty()
                        ? nsEmergency.needsHelpWithName(userNameHolder[0])
                        : nsEmergency.needsHelp());
                String effectiveAlertMsg = notificationBody;
                if (lat[0] != 0 || lng[0] != 0) {
                    notificationBody += "\n" + nsEmergency.locationLabel() + ": " + locationName[0];
                }
                for (String token : memberTokens) {
                    try {
                        FcmHelper.sendPush(accessToken, token, nsEmergency.pushTitle(dangerType), notificationBody, userNameHolder[0], dangerType, locationName[0], effectiveAlertMsg, userPhoneHolder[0]);
                        sent++;
                    } catch (Exception e) {
                        Log.w(TAG, "FCM failed for token " + token, e);
                    }
                }

                org.json.JSONArray idsArray = new org.json.JSONArray();
                for (String id : memberUids) {
                    idsArray.put(new org.json.JSONObject("{\"stringValue\":\"" + id + "\"}"));
                }

                org.json.JSONObject valuesObj = new org.json.JSONObject();
                valuesObj.put("values", idsArray);

                org.json.JSONObject arrayValueObj = new org.json.JSONObject();
                arrayValueObj.put("arrayValue", valuesObj);

                org.json.JSONObject fields = new org.json.JSONObject();
                fields.put("senderId", new org.json.JSONObject("{\"stringValue\":\"" + currentUserId + "\"}"));
                fields.put("senderName", new org.json.JSONObject("{\"stringValue\":\"" + (userNameHolder[0] != null ? userNameHolder[0].replace("\"", "\\\"") : "") + "\"}"));
                if (userPhoneHolder[0] != null && !userPhoneHolder[0].isEmpty()) {
                    fields.put("senderPhone", new org.json.JSONObject("{\"stringValue\":\"" + userPhoneHolder[0].replace("\"", "\\\"") + "\"}"));
                }
                fields.put("receiverIds", arrayValueObj);
                fields.put("dangerType", new org.json.JSONObject("{\"stringValue\":\"" + dangerType.toLowerCase() + "\"}"));
                fields.put("alertMsg", new org.json.JSONObject("{\"stringValue\":\"" + alertMsg.replace("\"", "\\\"") + "\"}"));
                if (lat[0] != 0 || lng[0] != 0) {
                    fields.put("lat", new org.json.JSONObject("{\"doubleValue\":" + lat[0] + "}"));
                    fields.put("lng", new org.json.JSONObject("{\"doubleValue\":" + lng[0] + "}"));
                    if (locationName[0] != null && !locationName[0].isEmpty()) {
                        fields.put("locationName", new org.json.JSONObject("{\"stringValue\":\"" + locationName[0] + "\"}"));
                    }
                }
                java.util.Date now = new java.util.Date();
                java.text.SimpleDateFormat sdf = new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US);
                sdf.setTimeZone(java.util.TimeZone.getTimeZone("UTC"));
                String timestamp = sdf.format(now);
                fields.put("createdAt", new org.json.JSONObject("{\"timestampValue\":\"" + timestamp + "\"}"));

                String body = "{\"fields\":" + fields.toString() + "}";
                String url = "https://firestore.googleapis.com/v1/projects/" + projectId + "/databases/(default)/documents/help_history";
                httpPost(url, body, accessToken);

                JSObject result = new JSObject();
                result.put("sent", sent);
                result.put("total", memberTokens.size());
                call.resolve(result);
            } catch (Exception e) {
                Log.e(TAG, "sendEmergencyAlert failed", e);
                call.reject("Failed to send emergency alert: " + e.getMessage());
            }
        }).start();
    }

    private String httpPost(String urlStr, String body, String bearerToken) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(urlStr).openConnection();
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/json");
        if (bearerToken != null && !bearerToken.isEmpty()) {
            c.setRequestProperty("Authorization", "Bearer " + bearerToken);
        }
        c.setDoOutput(true);
        OutputStream os = c.getOutputStream();
        os.write(body.getBytes(StandardCharsets.UTF_8));
        os.close();
        int code = c.getResponseCode();
        if (code >= 200 && code < 300) {
            BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
            r.close();
            return sb.toString();
        } else {
            BufferedReader r = new BufferedReader(new InputStreamReader(c.getErrorStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
            r.close();
            String err = sb.toString();
            throw new Exception("HTTP " + code + " body=" + err);
        }
    }

    private String httpGet(String urlStr, String bearerToken) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(urlStr).openConnection();
        c.setRequestMethod("GET");
        if (bearerToken != null && !bearerToken.isEmpty()) {
            c.setRequestProperty("Authorization", "Bearer " + bearerToken);
        }
        int code = c.getResponseCode();
        if (code >= 200 && code < 300) {
            BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
            r.close();
            return sb.toString();
        } else {
            BufferedReader r = new BufferedReader(new InputStreamReader(c.getErrorStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
            r.close();
            String err = sb.toString();
            throw new Exception("HTTP " + code + " body=" + err);
        }
    }

    @PluginMethod
    public void setLanguage(PluginCall call) {
        String lang = call.getString("lang", "en");
        getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .edit()
                .putString("app_lang", lang)
                .apply();
        JSObject result = new JSObject();
        result.put("saved", true);
        call.resolve(result);
    }

    @PluginMethod
    public void isRunning(PluginCall call) {
        boolean running = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE)
                .getBoolean("monitoring_running", false);
        JSObject result = new JSObject();
        result.put("running", running);
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

    @PluginMethod
    public void getPendingNavigate(PluginCall call) {
        android.content.SharedPreferences prefs = getContext().getSharedPreferences("capacitor", android.content.Context.MODE_PRIVATE);
        String route = prefs.getString("pending_navigate_to", "");
        if (route != null && !route.isEmpty()) {
            prefs.edit().remove("pending_navigate_to").apply();
            Log.i(TAG, "getPendingNavigate: " + route);
        }
        JSObject result = new JSObject();
        result.put("route", route != null ? route : "");
        call.resolve(result);
    }
}
