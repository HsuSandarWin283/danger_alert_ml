package com.danger.alert;

import android.Manifest;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.location.Address;
import android.location.Geocoder;
import android.location.Location;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.telephony.SmsManager;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationServices;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class DangerAlertActivity extends AppCompatActivity {

    private static final String TAG = "DangerAlertActivity";
    private static final int LOCATION_PERMISSION_REQUEST = 200;
    private static final int SMS_PERMISSION_REQUEST = 201;
    private CountDownTimer timer;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private String dangerType = "unknown";
    private double confidence = 0;
    private LinearLayout rootLayout;
    private MediaPlayer alertPlayer;
    private final Handler soundHandler = new Handler(Looper.getMainLooper());
    private final Runnable stopSoundRunnable = new Runnable() {
        @Override
        public void run() {
            stopAlertSound();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON |
                        WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON |
                        WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD |
                        WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED |
                        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN |
                        WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
        );

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
        }

        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        PowerManager.WakeLock wakeLock = pm.newWakeLock(
                PowerManager.FULL_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP,
                "DangerAlert:wake"
        );
        wakeLock.acquire(120000);

        dangerType = getIntent().getStringExtra("danger_type");
        confidence = getIntent().getDoubleExtra("confidence", 0);
        if (dangerType == null) dangerType = "unknown";

        String action = getIntent().getStringExtra("action");
        if ("ok".equals(action)) {
            finish();
            return;
        }
        if ("help".equals(action)) {
            buildUI();
            onSendHelp();
            return;
        }
        if ("trouble".equals(action)) {
            String senderName = getIntent().getStringExtra("senderName");
            String alertMsg = getIntent().getStringExtra("alertMsg");
            buildTroubleUI(senderName, alertMsg);
            return;
        }

        buildUI();
        playAlertSound();
    }

    private void buildTroubleUI(String senderName, String alertMsg) {
        rootLayout = new LinearLayout(this);
        rootLayout.setOrientation(LinearLayout.VERTICAL);
        rootLayout.setGravity(Gravity.CENTER_HORIZONTAL);
        rootLayout.setPadding(80, 120, 80, 80);
        rootLayout.setBackgroundColor(Color.parseColor("#DC2626"));

        TextView icon = new TextView(this);
        icon.setText("\u26A0\uFE0F");
        icon.setTextSize(60);
        icon.setGravity(Gravity.CENTER);
        rootLayout.addView(icon);

        TextView titleView = new TextView(this);
        titleView.setText("Danger : TROUBLE");
        titleView.setTextColor(Color.WHITE);
        titleView.setTextSize(28);
        titleView.setGravity(Gravity.CENTER);
        titleView.setPadding(0, 30, 0, 10);
        rootLayout.addView(titleView);

        String name = senderName != null && !senderName.isEmpty() ? senderName : "User";
        TextView troubleView = new TextView(this);
        troubleView.setText(name + " is trouble now");
        troubleView.setTextColor(Color.parseColor("#FCA5A5"));
        troubleView.setTextSize(22);
        troubleView.setGravity(Gravity.CENTER);
        troubleView.setPadding(0, 10, 0, 20);
        rootLayout.addView(troubleView);

        TextView msgView = new TextView(this);
        msgView.setText(alertMsg != null ? alertMsg : "");
        msgView.setTextColor(Color.WHITE);
        msgView.setTextSize(18);
        msgView.setGravity(Gravity.CENTER);
        msgView.setPadding(0, 10, 0, 40);
        rootLayout.addView(msgView);

        Button closeBtn = new Button(this);
        NotificationStrings ns = new NotificationStrings(this);
        closeBtn.setText(ns.close());
        closeBtn.setTextSize(20);
        closeBtn.setBackgroundColor(Color.WHITE);
        closeBtn.setTextColor(Color.parseColor("#DC2626"));
        LinearLayout.LayoutParams closeLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 160);
        closeBtn.setLayoutParams(closeLP);
        closeBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                stopAlertSound();
                finish();
            }
        });
        rootLayout.addView(closeBtn);

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        scrollView.addView(rootLayout);
        setContentView(scrollView);
    }

    private void buildUI() {
        rootLayout = new LinearLayout(this);
        rootLayout.setOrientation(LinearLayout.VERTICAL);
        rootLayout.setGravity(Gravity.CENTER_HORIZONTAL);
        rootLayout.setPadding(80, 120, 80, 80);
        rootLayout.setBackgroundColor(Color.parseColor("#DC2626"));

        TextView icon = new TextView(this);
        icon.setText("\u26A0\uFE0F");
        icon.setTextSize(60);
        icon.setGravity(Gravity.CENTER);
        rootLayout.addView(icon);

        NotificationStrings ns = new NotificationStrings(this);

        TextView title = new TextView(this);
        title.setText(ns.dangerTypeTitle(dangerType));
        title.setTextColor(Color.WHITE);
        title.setTextSize(28);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 30, 0, 10);
        rootLayout.addView(title);

        TextView message = new TextView(this);
        message.setText(ns.dangerSoundFoundNear() + "\n" + ns.areYouOk());
        message.setTextColor(Color.WHITE);
        message.setTextSize(20);
        message.setGravity(Gravity.CENTER);
        message.setPadding(0, 10, 0, 40);
        rootLayout.addView(message);

        Button okBtn = new Button(this);
        okBtn.setText(ns.imOk());
        okBtn.setTextSize(20);
        okBtn.setBackgroundColor(Color.parseColor("#16A34A"));
        okBtn.setTextColor(Color.WHITE);
        LinearLayout.LayoutParams okLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 160);
        okLP.setMargins(0, 0, 0, 24);
        okBtn.setLayoutParams(okLP);
        okBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                stopAlertSound();
                finish();
            }
        });
        rootLayout.addView(okBtn);

        Button helpBtn = new Button(this);
        helpBtn.setText(ns.imNotOkSendHelp());
        helpBtn.setTextSize(20);
        helpBtn.setBackgroundColor(Color.WHITE);
        helpBtn.setTextColor(Color.parseColor("#DC2626"));
        LinearLayout.LayoutParams helpLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 160);
        helpLP.setMargins(0, 0, 0, 10);
        helpBtn.setLayoutParams(helpLP);
        helpBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                stopAlertSound();
                onSendHelp();
            }
        });
        rootLayout.addView(helpBtn);

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        scrollView.addView(rootLayout);
        setContentView(scrollView);
    }

    private void onSendHelp() {
        if (timer != null) timer.cancel();
        NotificationStrings ns = new NotificationStrings(this);
        showResult(ns.sendingHelpRequest());
        sendHelpWithLocation();
    }

    private void sendHelpWithLocation() {
        final boolean[] done = {false};

        new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
            @Override
            public void run() {
                if (!done[0]) {
                    done[0] = true;
                    NotificationStrings nsTimeout = new NotificationStrings(DangerAlertActivity.this);
                    doSendHelp(0, 0, nsTimeout.locationUnavailable("timeout"));
                }
            }
        }, 5000);

        FusedLocationProviderClient client = LocationServices.getFusedLocationProviderClient(this);

        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED &&
            ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            done[0] = true;
            NotificationStrings nsPerm = new NotificationStrings(this);
            doSendHelp(0, 0, nsPerm.locationUnavailable("no permission"));
            return;
        }

        client.getLastLocation().addOnSuccessListener(this, new com.google.android.gms.tasks.OnSuccessListener<Location>() {
            @Override
            public void onSuccess(Location location) {
                if (done[0]) return;
                done[0] = true;
                if (location != null) {
                    double lat = location.getLatitude();
                    double lng = location.getLongitude();
                    String name = getLocationName(lat, lng);
                    doSendHelp(lat, lng, name);
                } else {
                    NotificationStrings nsLoc = new NotificationStrings(DangerAlertActivity.this);
                    doSendHelp(0, 0, nsLoc.locationUnavailableDefault());
                }
            }
        });
    }

    private String getLocationName(double lat, double lng) {
        try {
            Geocoder geo = new Geocoder(this, Locale.getDefault());
            List<Address> addrs = geo.getFromLocation(lat, lng, 1);
            if (addrs != null && !addrs.isEmpty()) {
                Address a = addrs.get(0);
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i <= Math.min(a.getMaxAddressLineIndex(), 2); i++) {
                    if (sb.length() > 0) sb.append(", ");
                    sb.append(a.getAddressLine(i));
                }
                return sb.toString();
            }
        } catch (Exception ignored) {}
        return String.format(Locale.getDefault(), "%.4f, %.4f", lat, lng);
    }

    private void doSendHelp(final double lat, final double lng, final String locationName) {
        TextView msg = (TextView) rootLayout.getChildAt(2);
        NotificationStrings ns = new NotificationStrings(this);
        msg.setText(ns.sendingHelpRequest());

        executor.execute(new Runnable() {
            @Override
            public void run() {
                try {
                    String apiKey = getFirebaseApiKey();
                    String projectId = getFirebaseProjectId();
                    String currentUserId = getCurrentUserId();

                    if (apiKey == null || projectId == null || currentUserId == null || currentUserId.isEmpty()) {
                        NotificationStrings nsErr = new NotificationStrings(DangerAlertActivity.this);
                        showResult(nsErr.failed("Firebase not configured.\nuserId=" + currentUserId));
                        return;
                    }

                    String userName = "Unknown User";
                    String alertMsg = "";
                    String fcmLastErr = "";
                    String senderPhone = "";

                    String authToken = getSharedPreferences("capacitor", MODE_PRIVATE)
                            .getString("firebase_auth_token", "");
                    String accessToken = "";
                    if (!authToken.isEmpty()) {
                        accessToken = authToken;
                        Log.i(TAG, "Using Firebase Auth token");
                    } else {
                        try {
                            accessToken = FcmHelper.getAccessToken(DangerAlertActivity.this);
                            Log.i(TAG, "Using service account token");
                        } catch (Exception e) {
                            fcmLastErr = e.getMessage();
                            Log.e(TAG, "getAccessToken failed", e);
                        }
                    }

                    if (!accessToken.isEmpty()) {
                        String displayName = getSharedPreferences("capacitor", MODE_PRIVATE)
                                .getString("user_display_name", "");
                        senderPhone = getSharedPreferences("capacitor", MODE_PRIVATE)
                                .getString("current_user_phone", "");
                        if (displayName != null && !displayName.isEmpty()) {
                            userName = displayName;
                        } else {
                            try {
                                String senderDoc = httpGetWithAuth("https://firestore.googleapis.com/v1/projects/"
                                        + projectId + "/databases/(default)/documents/users/" + currentUserId, accessToken);
                                if (senderDoc != null && senderDoc.contains("stringValue")) {
                                    JSONObject senderObj = new JSONObject(senderDoc);
                                    JSONObject senderFields = senderObj.optJSONObject("fields");
                                    if (senderFields != null) {
                                        JSONObject nameObj = senderFields.optJSONObject("name");
                                        if (nameObj != null) userName = nameObj.optString("stringValue", "Unknown User");
                                        JSONObject phoneObj = senderFields.optJSONObject("phone");
                                        if (phoneObj != null) senderPhone = phoneObj.optString("stringValue", "");
                                    }
                                }
                            } catch (Exception e) {
                                Log.w(TAG, "Failed to get user name: " + e.getMessage());
                            }
                        }
                    }

                    alertMsg = userName + " " + ns.needsHelp() + "!\n"
                            + ns.pushTitle(dangerType) + "\n"
                            + ns.locationLabel() + ": " + locationName;
                    if (lat != 0) {
                        alertMsg += String.format(Locale.getDefault(), " (%.4f, %.4f)", lat, lng);
                    }

                    String savedFcm = getSharedPreferences("capacitor", MODE_PRIVATE)
                            .getString("fcm_token", "");

                    int fcmSent = 0;
                    int fcmFailed = 0;
                    int parsedCount = 0;
                    int emptyTokens = 0;
                    String debugMemberToken = "N/A";

                    java.util.ArrayList<String> memberUids = new java.util.ArrayList<>();
                    String helpSaveStatus = "HelpHistory: pending";

                    if (!accessToken.isEmpty()) {
                        String queryBody = "{\"structuredQuery\":{\"from\":[{\"collectionId\":\"group_members\"}],"
                                + "\"where\":{\"fieldFilter\":{\"field\":{\"fieldPath\":\"groupId\"},"
                                + "\"op\":\"EQUAL\","
                                + "\"value\":{\"stringValue\":\"" + currentUserId + "\"}}},"
                                + "\"limit\":100}}";
                        String membersUrl = "https://firestore.googleapis.com/v1/projects/"
                                + projectId + "/databases/(default)/documents:runQuery";
                        String membersJson = httpPostWithAuth(membersUrl, queryBody, accessToken);

                        String fcmAccessToken = accessToken;
                        if (fcmAccessToken.startsWith("ey")) {
                            try {
                                String saToken = FcmHelper.getAccessToken(DangerAlertActivity.this);
                                fcmAccessToken = saToken;
                            } catch (Exception e) {
                                fcmLastErr = "getAccessToken: " + e.getMessage();
                            }
                        }

                        if (membersJson != null && membersJson.contains("document")) {
                            JSONArray docsArray = new JSONArray(membersJson);
                            parsedCount = docsArray.length();

                            for (int i = 0; i < docsArray.length(); i++) {
                                JSONObject docWrapper = docsArray.getJSONObject(i);
                                JSONObject docObj = docWrapper.optJSONObject("document");
                                if (docObj == null) continue;
                                JSONObject fields = docObj.optJSONObject("fields");
                                if (fields == null) continue;

                                JSONObject userIdField = fields.optJSONObject("userId");
                                String memberUid = userIdField != null ? userIdField.optString("stringValue", "") : "";
                                if (memberUid.isEmpty()) continue;
                                memberUids.add(memberUid);

                                String memberDoc = httpGetWithAuth("https://firestore.googleapis.com/v1/projects/"
                                        + projectId + "/databases/(default)/documents/users/" + memberUid,
                                        accessToken);
                                String fcmToken = null;
                                String memberName = "member";
                                if (memberDoc != null && memberDoc.contains("stringValue")) {
                                    JSONObject memberDocObj = new JSONObject(memberDoc);
                                    JSONObject memberFields = memberDocObj.optJSONObject("fields");
                                    if (memberFields != null) {
                                        JSONObject fcmObj = memberFields.optJSONObject("fcmToken");
                                        if (fcmObj != null) fcmToken = fcmObj.optString("stringValue", "");
                                        JSONObject nameObj = memberFields.optJSONObject("name");
                                        if (nameObj != null) memberName = nameObj.optString("stringValue", "member");
                                    }
                                }

                                if (debugMemberToken.equals("N/A") && fcmToken != null && !fcmToken.isEmpty()) debugMemberToken = fcmToken;

                                if (fcmToken == null || fcmToken.isEmpty()) { emptyTokens++; continue; }
                                fcmToken = fcmToken.trim().replaceAll("\\s+", "");
                                try {
                                    FcmHelper.sendPush(fcmAccessToken, fcmToken,
                                            ns.pushTitle(dangerType), alertMsg, userName, dangerType, locationName, null, senderPhone);
                                    fcmSent++;
                                } catch (Exception fcmErr) {
                                    fcmFailed++;
                                    fcmLastErr = fcmErr.getMessage();
                                    Log.e(TAG, "FCM push failed", fcmErr);
                                }
                            }
                        }
                    }

                    String helpAccessToken = accessToken;
                    if (helpAccessToken == null || helpAccessToken.isEmpty() || helpAccessToken.startsWith("ey")) {
                        try {
                            helpAccessToken = FcmHelper.getAccessToken(DangerAlertActivity.this);
                        } catch (Exception e) {
                            helpAccessToken = accessToken;
                        }
                    }

                    Log.i(TAG, "help save token prefix=" + (helpAccessToken != null ? helpAccessToken.substring(0, Math.min(20, helpAccessToken.length())) : "null"));

                    try {
                        saveHelpMessage(helpAccessToken, projectId, currentUserId, userName, dangerType, alertMsg, lat, lng, locationName, memberUids);
                        helpSaveStatus = "HelpHistory: saved to Firestore";
                    } catch (Exception e) {
                        helpSaveStatus = "HelpHistory: save failed - " + e.getMessage();
                    }

                    String debugInfo = "\n[Debug] Members: " + parsedCount
                            + " | Empty tokens: " + emptyTokens
                            + " | FCM sent: " + fcmSent
                            + "\nYour token: " + (savedFcm.isEmpty() ? "NONE" : savedFcm.substring(0, Math.min(20, savedFcm.length())) + "...")
                            + "\nMember0 token: " + debugMemberToken
                            + (fcmFailed > 0 ? "\nFCM Error(" + fcmFailed + "): " + fcmLastErr : "")
                            + (fcmLastErr.isEmpty() || fcmFailed > 0 ? "" : "\nAccessToken Error: " + fcmLastErr);

                    if (fcmSent > 0) {
                        // showResult("Push notification sent to " + fcmSent + " member!" + debugInfo + "\n" + helpSaveStatus);
                        showResult(ns.pushSentTo(fcmSent));
                    } else if (parsedCount > 0 && emptyTokens > 0) {
                        showResult(ns.foundMembersNoTokens(parsedCount) + debugInfo + "\n" + helpSaveStatus);
                    } else if (parsedCount > 0 && fcmFailed > 0) {
                        showResult(ns.foundMembersPushFailed(parsedCount) + debugInfo + "\n" + helpSaveStatus);
                    } else {
                        showResult(ns.noTrustedMembers() + debugInfo + "\n" + helpSaveStatus);
                    }

                } catch (Exception e) {
                    NotificationStrings nsCatch = new NotificationStrings(DangerAlertActivity.this);
                    showResult(nsCatch.failed(e.getMessage()));
                }
            }
        });
    }

    private String getFirebaseServerKey() {
        return getSharedPreferences("capacitor", MODE_PRIVATE).getString("fcm_server_key", null);
    }

    private String getFirebaseClientEmail() {
        return getSharedPreferences("capacitor", MODE_PRIVATE).getString("fcm_client_email", null);
    }

    private String getFirebasePrivateKey() {
        return getSharedPreferences("capacitor", MODE_PRIVATE).getString("fcm_private_key", null);
    }

    private String getFcmAccessToken() throws Exception {
        String clientEmail = getFirebaseClientEmail();
        String privateKeyPem = getFirebasePrivateKey();
        if (clientEmail == null || privateKeyPem == null || clientEmail.isEmpty() || privateKeyPem.isEmpty()) {
            throw new Exception("Service account not configured");
        }

        long now = System.currentTimeMillis() / 1000;
        String header = base64Url("{\"alg\":\"RS256\",\"typ\":\"JWT\"}".getBytes());
        String payload = base64Url(("{\"iss\":\"" + clientEmail + "\","
                + "\"scope\":\"https://www.googleapis.com/auth/cloud-platform\","
                + "\"aud\":\"https://oauth2.googleapis.com/token\","
                + "\"iat\":" + now + ","
                + "\"exp\":" + (now + 3600) + "}").getBytes());
        String signingInput = header + "." + payload;

        String cleanKey = privateKeyPem
                .replace("\\n", "\n")
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s+", "");

        java.security.spec.PKCS8EncodedKeySpec keySpec = new java.security.spec.PKCS8EncodedKeySpec(
                android.util.Base64.decode(cleanKey, android.util.Base64.DEFAULT));
        java.security.KeyFactory kf = java.security.KeyFactory.getInstance("RSA");
        java.security.PrivateKey privateKey = kf.generatePrivate(keySpec);

        java.security.Signature sig = java.security.Signature.getInstance("SHA256withRSA");
        sig.initSign(privateKey);
        sig.update(signingInput.getBytes());
        String signature = base64Url(sig.sign());

        String jwt = signingInput + "." + signature;

        String tokenBody = "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=" + jwt;
        java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL("https://oauth2.googleapis.com/token").openConnection();
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
        c.setDoOutput(true);
        java.io.OutputStream os = c.getOutputStream();
        os.write(tokenBody.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        os.close();

        int code = c.getResponseCode();
        if (code == 200) {
            java.io.BufferedReader r = new java.io.BufferedReader(new java.io.InputStreamReader(c.getInputStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
            r.close();
            String response = sb.toString();
            String token = response.replaceAll(".*\"access_token\"\\s*:\\s*\"([^\"]+)\".*", "$1");
            if (!token.equals(response)) return token;
        }
        throw new Exception("Failed to get access token: " + code);
    }

    private String extractFirestoreString(String json, String field) {
        String pattern = "\"" + field + "\":{\"stringValue\":\"";
        int idx = json.indexOf(pattern);
        if (idx < 0) return null;
        int valStart = idx + pattern.length();
        int valEnd = valStart;
        while (valEnd < json.length() && json.charAt(valEnd) != '"') {
            if (json.charAt(valEnd) == '\\') valEnd++;
            valEnd++;
        }
        return json.substring(valStart, valEnd);
    }

    private String base64Url(byte[] data) {
        return android.util.Base64.encodeToString(data, android.util.Base64.URL_SAFE | android.util.Base64.NO_WRAP | android.util.Base64.NO_PADDING);
    }

    private void sendFcmPush(String fcmToken, String title, String body) throws Exception {
        String projectId = getFirebaseProjectId();
        String serverKey = getFirebaseServerKey();
        if (projectId == null || serverKey == null) {
            throw new Exception("FCM not configured");
        }

        String jsonBody = "{"
                + "\"to\":\"" + fcmToken + "\","
                + "\"notification\":{"
                + "\"title\":\"" + escapeJson(title) + "\","
                + "\"body\":\"" + escapeJson(body) + "\""
                + "},"
                + "\"priority\":\"high\""
                + "}";

        URL url = new URL("https://fcm.googleapis.com/fcm/send");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/json");
        c.setRequestProperty("Authorization", "key=" + serverKey);
        c.setConnectTimeout(10000);
        c.setReadTimeout(10000);
        c.setDoOutput(true);
        OutputStream os = c.getOutputStream();
        os.write(jsonBody.getBytes(StandardCharsets.UTF_8));
        os.close();

        int code = c.getResponseCode();
        Log.i(TAG, "FCM v1 response: " + code);
    }

    private String httpGet(String urlStr) throws Exception {
        return httpGetWithAuth(urlStr, null);
    }

    private String httpGetWithAuth(String urlStr, String bearerToken) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(urlStr).openConnection();
        c.setRequestMethod("GET");
        c.setConnectTimeout(10000);
        c.setReadTimeout(10000);
        if (bearerToken != null && !bearerToken.isEmpty()) {
            c.setRequestProperty("Authorization", "Bearer " + bearerToken);
        }
        if (c.getResponseCode() == 200) {
            BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
            r.close();
            return sb.toString();
        }
        return null;
    }

    private String httpPost(String urlStr, String body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(urlStr).openConnection();
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/json");
        String token = getFirebaseAuthToken();
        if (token != null && !token.isEmpty()) {
            c.setRequestProperty("Authorization", "Bearer " + token);
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
        }
        return null;
    }

    private String httpPostWithAuth(String urlStr, String body, String bearerToken) throws Exception {
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
            Log.w(TAG, "HTTP " + code + " for " + urlStr + " body=" + err);
            throw new Exception("HTTP " + code + " for " + urlStr + " body=" + err);
        }
    }

    private void showResult(final String message) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                rootLayout.removeAllViews();

                TextView check = new TextView(DangerAlertActivity.this);
                check.setText("\u2714");
                check.setTextSize(48);
                check.setGravity(Gravity.CENTER);
                rootLayout.addView(check);

                TextView txt = new TextView(DangerAlertActivity.this);
                txt.setText(message);
                txt.setTextColor(Color.WHITE);
                txt.setTextSize(16);
                txt.setGravity(Gravity.CENTER);
                txt.setPadding(0, 20, 0, 40);
                rootLayout.addView(txt);

                Button closeBtn = new Button(DangerAlertActivity.this);
                NotificationStrings nsClose = new NotificationStrings(DangerAlertActivity.this);
                closeBtn.setText(nsClose.close());
                closeBtn.setTextSize(18);
                closeBtn.setBackgroundColor(Color.WHITE);
                closeBtn.setTextColor(Color.parseColor("#DC2626"));
                closeBtn.setOnClickListener(new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        finish();
                    }
                });
                rootLayout.addView(closeBtn);
            }
        });
    }

    private String getFirebaseApiKey() {
        return getSharedPreferences("capacitor", MODE_PRIVATE).getString("firebase_api_key", null);
    }

    private String getFirebaseProjectId() {
        return getSharedPreferences("capacitor", MODE_PRIVATE).getString("firebase_project_id", null);
    }

    private String getCurrentUserId() {
        return getSharedPreferences("capacitor", MODE_PRIVATE).getString("current_user_id", null);
    }

    private String getFirebaseAuthToken() {
        return getSharedPreferences("capacitor", MODE_PRIVATE).getString("firebase_auth_token", null);
    }

    private void saveHelpMessage(String accessToken, String projectId, String currentUserId, String userName, String dangerType, String alertMsg, double lat, double lng, String locationName, java.util.List<String> receiverIds) throws Exception {
        if (accessToken == null || accessToken.isEmpty()) {
            Log.w(TAG, "saveHelpMessage skipped: empty accessToken");
            return;
        }

        org.json.JSONArray idsArray = new org.json.JSONArray();
        for (String id : receiverIds) {
            idsArray.put(new org.json.JSONObject("{\"stringValue\":\"" + id + "\"}"));
        }

        org.json.JSONObject valuesObj = new org.json.JSONObject();
        valuesObj.put("values", idsArray);

        org.json.JSONObject arrayValueObj = new org.json.JSONObject();
        arrayValueObj.put("arrayValue", valuesObj);

        org.json.JSONObject fields = new org.json.JSONObject();
        fields.put("senderId", new org.json.JSONObject("{\"stringValue\":\"" + currentUserId + "\"}"));
        fields.put("senderName", new org.json.JSONObject("{\"stringValue\":\"" + escapeJson(userName) + "\"}"));
        String senderPhone = getSharedPreferences("capacitor", MODE_PRIVATE).getString("current_user_phone", "");
        if (senderPhone != null && !senderPhone.isEmpty()) {
            fields.put("senderPhone", new org.json.JSONObject("{\"stringValue\":\"" + escapeJson(senderPhone) + "\"}"));
        }
        fields.put("receiverIds", arrayValueObj);
        fields.put("dangerType", new org.json.JSONObject("{\"stringValue\":\"" + escapeJson(dangerType.toLowerCase()) + "\"}"));
        fields.put("alertMsg", new org.json.JSONObject("{\"stringValue\":\"" + escapeJson(alertMsg) + "\"}"));
        if (lat != 0) fields.put("lat", new org.json.JSONObject("{\"doubleValue\":" + lat + "}"));
        if (lng != 0) fields.put("lng", new org.json.JSONObject("{\"doubleValue\":" + lng + "}"));
        if (locationName != null && !locationName.isEmpty()) {
            fields.put("locationName", new org.json.JSONObject("{\"stringValue\":\"" + escapeJson(locationName) + "\"}"));
        }

        java.util.Date now = new java.util.Date();
        java.text.SimpleDateFormat sdf = new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US);
        sdf.setTimeZone(java.util.TimeZone.getTimeZone("UTC"));
        String timestamp = sdf.format(now);
        fields.put("createdAt", new org.json.JSONObject("{\"timestampValue\":\"" + timestamp + "\"}"));

        String body = "{\"fields\":" + fields.toString() + "}";
        String url = "https://firestore.googleapis.com/v1/projects/"
                + projectId + "/databases/(default)/documents/help_history";

        Log.i(TAG, "saveHelpMessage POST url=" + url);
        String helpSaveResult = httpPostWithAuth(url, body, accessToken);
        Log.i(TAG, "saveHelpMessage result=" + (helpSaveResult != null ? helpSaveResult.substring(0, Math.min(200, helpSaveResult.length())) : "null"));
    }

    private void playAlertSound() {
        stopAlertSound();
        try {
            Uri soundUri = null;
            int soundResId = getResources().getIdentifier("alert", "raw", getPackageName());
            if (soundResId != 0) {
                soundUri = Uri.parse("android.resource://" + getPackageName() + "/" + soundResId);
            }
            if (soundUri == null) {
                soundUri = Settings.System.DEFAULT_NOTIFICATION_URI;
            }
            if (soundUri != null) {
                alertPlayer = MediaPlayer.create(this, soundUri);
                if (alertPlayer != null) {
                    alertPlayer.setLooping(true);
                    alertPlayer.start();
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "playAlertSound failed", e);
        }
    }

    private void stopAlertSound() {
        soundHandler.removeCallbacks(stopSoundRunnable);
        if (alertPlayer != null) {
            try {
                alertPlayer.stop();
            } catch (Exception ignored) {
            }
            alertPlayer.release();
            alertPlayer = null;
        }
    }

    @Override
    protected void onDestroy() {
        stopAlertSound();
        if (timer != null) timer.cancel();
        super.onDestroy();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == LOCATION_PERMISSION_REQUEST) {
            sendHelpWithLocation();
        }
    }

    private String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "");
    }
}
