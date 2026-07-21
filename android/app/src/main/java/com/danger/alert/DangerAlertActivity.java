package com.danger.alert;

import android.Manifest;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.location.Address;
import android.location.Geocoder;
import android.location.Location;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.os.PowerManager;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

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

    private static final int LOCATION_PERMISSION_REQUEST = 200;
    private CountDownTimer timer;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private String dangerType = "unknown";
    private double confidence = 0;
    private LinearLayout rootLayout;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON |
                WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON |
                WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD |
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
        );

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

        buildUI();
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

        TextView title = new TextView(this);
        title.setText("Danger Detected!");
        title.setTextColor(Color.WHITE);
        title.setTextSize(28);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 30, 0, 10);
        rootLayout.addView(title);

        TextView message = new TextView(this);
        message.setText("I found " + dangerType.toUpperCase() + " sound near you.\nAre you OK?");
        message.setTextColor(Color.WHITE);
        message.setTextSize(20);
        message.setGravity(Gravity.CENTER);
        message.setPadding(0, 10, 0, 10);
        rootLayout.addView(message);

        final TextView timerView = new TextView(this);
        timerView.setTextColor(Color.parseColor("#FCA5A5"));
        timerView.setTextSize(16);
        timerView.setGravity(Gravity.CENTER);
        timerView.setPadding(0, 10, 0, 40);
        rootLayout.addView(timerView);

        Button okBtn = new Button(this);
        okBtn.setText("I'm OK");
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
                finish();
            }
        });
        rootLayout.addView(okBtn);

        Button helpBtn = new Button(this);
        helpBtn.setText("I'm NOT OK - Send Help");
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
                onSendHelp();
            }
        });
        rootLayout.addView(helpBtn);

        setContentView(rootLayout);

        timer = new CountDownTimer(120000, 1000) {
            @Override
            public void onTick(long millisUntilFinished) {
                long mins = millisUntilFinished / 60000;
                long secs = (millisUntilFinished % 60000) / 1000;
                timerView.setText(String.format("Auto-send help in %02d:%02d", mins, secs));
            }

            @Override
            public void onFinish() {
                onSendHelp();
            }
        }.start();
    }

    private void onSendHelp() {
        if (timer != null) timer.cancel();

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.ACCESS_FINE_LOCATION},
                    LOCATION_PERMISSION_REQUEST);
            return;
        }
        sendHelpWithLocation();
    }

    private void sendHelpWithLocation() {
        FusedLocationProviderClient client = LocationServices.getFusedLocationProviderClient(this);

        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            doSendHelp(0, 0, "Location unavailable");
            return;
        }

        client.getLastLocation().addOnSuccessListener(this, new com.google.android.gms.tasks.OnSuccessListener<Location>() {
            @Override
            public void onSuccess(Location location) {
                if (location != null) {
                    double lat = location.getLatitude();
                    double lng = location.getLongitude();
                    String name = getLocationName(lat, lng);
                    doSendHelp(lat, lng, name);
                } else {
                    doSendHelp(0, 0, "Location unavailable");
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
        msg.setText("Sending help request...");

        executor.execute(new Runnable() {
            @Override
            public void run() {
                try {
                    String apiKey = getFirebaseApiKey();
                    String projectId = getFirebaseProjectId();
                    String currentUserId = getCurrentUserId();

                    if (apiKey == null || projectId == null || currentUserId == null) {
                        showResult("Failed: not configured");
                        return;
                    }

                    String userDoc = httpGet("https://firestore.googleapis.com/v1/projects/"
                            + projectId + "/databases/(default)/documents/users/"
                            + currentUserId + "?key=" + apiKey);
                    String userName = "Unknown User";
                    if (userDoc != null && userDoc.contains("\"name\"")) {
                        String n = userDoc.replaceAll(".*\"name\"\\s*:\\s*\"([^\"]+)\".*", "$1");
                        if (!n.equals(userDoc)) userName = n;
                    }

                    String alertMsg = userName + " needs help!\n"
                            + "Danger: " + dangerType.toUpperCase() + " detected\n"
                            + "Location: " + locationName;
                    if (lat != 0) {
                        alertMsg += String.format(Locale.getDefault(), " (%.4f, %.4f)", lat, lng);
                    }

                    String membersUrl = "https://firestore.googleapis.com/v1/projects/"
                            + projectId + "/databases/(default)/documents/group_members?key=" + apiKey
                            + "&structuredQuery.where.fieldFilter.field.fieldPath=groupId"
                            + "&structuredQuery.where.fieldFilter.value.stringValue=" + currentUserId
                            + "&structuredQuery.where.fieldFilter.op=EQUAL";
                    String membersJson = httpGet(membersUrl);

                    int sent = 0;
                    if (membersJson != null && membersJson.contains("documents")) {
                        String[] docs = membersJson.split("\"userId\"\\s*:\\s*\"");
                        for (int i = 1; i < docs.length; i++) {
                            String uid = docs[i].replaceAll("[\"\\s,}].*", "").trim();
                            if (uid.isEmpty() || uid.equals(currentUserId)) continue;
                            String body = "{\"fields\":{"
                                    + "\"alertMessage\":{\"stringValue\":\"" + escapeJson(alertMsg) + "\"},"
                                    + "\"senderId\":{\"stringValue\":\"" + currentUserId + "\"},"
                                    + "\"senderName\":{\"stringValue\":\"" + escapeJson(userName) + "\"},"
                                    + "\"locationName\":{\"stringValue\":\"" + escapeJson(locationName) + "\"},"
                                    + "\"latitude\":{\"doubleValue\":" + lat + "},"
                                    + "\"longitude\":{\"doubleValue\":" + lng + "},"
                                    + "\"dangerType\":{\"stringValue\":\"" + dangerType + "\"},"
                                    + "\"timestamp\":{\"timestampValue\":\"" + java.time.Instant.now() + "\"},"
                                    + "\"read\":{\"booleanValue\":false}}}";
                            httpPost("https://firestore.googleapis.com/v1/projects/"
                                    + projectId + "/databases/(default)/documents/alerts/"
                                    + uid + "/notifications?key=" + apiKey, body);
                            sent++;
                        }
                    }

                    if (sent > 0) {
                        showResult("Help sent to " + sent + " member" + (sent > 1 ? "s" : "") + "!\n\n" + alertMsg);
                    } else {
                        showResult("No trusted group members found.\nAdd members in Trusted Group settings.");
                    }

                } catch (Exception e) {
                    showResult("Failed: " + e.getMessage());
                }
            }
        });
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
                closeBtn.setText("Close");
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

    private String httpGet(String urlStr) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(urlStr).openConnection();
        c.setRequestMethod("GET");
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

    private void httpPost(String urlStr, String body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(urlStr).openConnection();
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/json");
        c.setDoOutput(true);
        OutputStream os = c.getOutputStream();
        os.write(body.getBytes(StandardCharsets.UTF_8));
        os.close();
        c.getResponseCode();
    }

    private String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "");
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == LOCATION_PERMISSION_REQUEST) {
            sendHelpWithLocation();
        }
    }

    @Override
    protected void onDestroy() {
        if (timer != null) timer.cancel();
        super.onDestroy();
    }
}
