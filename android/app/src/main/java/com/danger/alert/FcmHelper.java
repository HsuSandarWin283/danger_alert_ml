package com.danger.alert;

import android.content.Context;
import android.util.Base64;
import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;

class FcmHelper {
    private static final String TAG = "FcmHelper";

    static String getAccessToken(Context context) throws Exception {
        String json = readAsset(context, "service-account.json");
        if (json == null || json.isEmpty()) {
            throw new Exception("service-account.json not found");
        }

        JSONObject sa = new JSONObject(json);
        String clientEmail = sa.getString("client_email");
        String privateKeyPem = sa.getString("private_key");

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
                .replace("\"", "")
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s+", "");

        PKCS8EncodedKeySpec keySpec = new PKCS8EncodedKeySpec(
                Base64.decode(cleanKey, Base64.DEFAULT));
        PrivateKey privateKey = KeyFactory.getInstance("RSA").generatePrivate(keySpec);

        Signature sig = Signature.getInstance("SHA256withRSA");
        sig.initSign(privateKey);
        sig.update(signingInput.getBytes());
        String signature = base64Url(sig.sign());

        String jwt = signingInput + "." + signature;
        String tokenBody = "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=" + jwt;
        HttpURLConnection c = (HttpURLConnection) new URL("https://oauth2.googleapis.com/token").openConnection();
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
        c.setConnectTimeout(10000);
        c.setReadTimeout(10000);
        c.setDoOutput(true);
        OutputStream os = c.getOutputStream();
        os.write(tokenBody.getBytes(StandardCharsets.UTF_8));
        os.close();

        int code = c.getResponseCode();
        if (code == 200) {
            BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream()));
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

    private static String readAsset(Context context, String filename) {
        try {
            BufferedReader r = new BufferedReader(new InputStreamReader(context.getAssets().open(filename)));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
            r.close();
            return sb.toString();
        } catch (Exception e) {
            Log.e(TAG, "Failed to read asset: " + filename, e);
            return null;
        }
    }

    static void sendPush(String accessToken, String fcmToken, String title, String body) throws Exception {
        sendPush(accessToken, fcmToken, title, body, null, null, null, null);
    }

    static void sendPush(String accessToken, String fcmToken, String title, String body, String senderName, String dangerType, String locationName) throws Exception {
        sendPush(accessToken, fcmToken, title, body, senderName, dangerType, locationName, null);
    }

    static void sendPush(String accessToken, String fcmToken, String title, String body, String senderName, String dangerType, String locationName, String alertMsg) throws Exception {
        String projectId = "danger-alert-903e5";
        fcmToken = fcmToken.trim().replaceAll("\\s+", "");
        String displayTitle = (senderName != null && !senderName.isEmpty()) ? senderName + " needs help!" : title;
        String effectiveAlertMsg = (alertMsg != null && !alertMsg.isEmpty()) ? alertMsg : body;
        String jsonBody = "{"
                + "\"message\":{"
                + "\"token\":\"" + fcmToken + "\","
                + "\"data\":{"
                + "\"type\":\"help_message\","
                + "\"route\":\"/help-alert\","
                + "\"title\":\"" + escapeJson(displayTitle) + "\","
                + "\"body\":\"" + escapeJson(body) + "\","
                + "\"senderName\":\"" + escapeJson(senderName != null ? senderName : "") + "\","
                + "\"dangerType\":\"" + escapeJson(dangerType != null ? dangerType : "unknown") + "\","
                + "\"locationName\":\"" + escapeJson(locationName != null ? locationName : "") + "\","
                + "\"alertMsg\":\"" + escapeJson(effectiveAlertMsg) + "\""
                + "},"
                + "\"android\":{"
                + "\"priority\":\"high\""
                + "}"
                + "}"
                + "}";

        Log.i(TAG, "FCM send token=" + fcmToken);
        Log.i(TAG, "FCM send body=" + jsonBody);

        URL url = new URL("https://fcm.googleapis.com/v1/projects/" + projectId + "/messages:send");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/json");
        c.setRequestProperty("Authorization", "Bearer " + accessToken);
        c.setConnectTimeout(10000);
        c.setReadTimeout(10000);
        c.setDoOutput(true);
        OutputStream os = c.getOutputStream();
        os.write(jsonBody.getBytes(StandardCharsets.UTF_8));
        os.close();

        int code = c.getResponseCode();
        BufferedReader reader = new BufferedReader(new InputStreamReader(code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream()));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) sb.append(line);
        reader.close();
        String response = sb.toString();
        Log.i(TAG, "FCM v1 response: " + code + " body: " + response.substring(0, Math.min(200, response.length())));
        if (code < 200 || code >= 300) {
            throw new Exception("FCM failed: " + code + " - " + response.substring(0, Math.min(200, response.length())));
        }
    }

    private static String base64Url(byte[] data) {
        return Base64.encodeToString(data, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
    }

    private static String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "");
    }
}
