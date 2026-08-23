package com.danger.alert;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.location.Address;
import android.location.Geocoder;
import android.net.Uri;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewParent;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationServices;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;

public class HelpAlertActivity extends AppCompatActivity {

    private LinearLayout rootLayout;
    private String senderName = "";
    private String dangerType = "unknown";
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
                "HelpAlert:wake"
        );
        wakeLock.acquire(120000);

        String title = getIntent().getStringExtra("title");
        String body = getIntent().getStringExtra("body");
        senderName = getIntent().getStringExtra("senderName");
        dangerType = getIntent().getStringExtra("dangerType");
        if (dangerType == null || dangerType.isEmpty()) dangerType = "unknown";

        String action = getIntent().getStringExtra("action");
        if ("received".equals(action)) {
            String senderName = getIntent().getStringExtra("senderName");
            String dangerType = getIntent().getStringExtra("dangerType");
            String alertMsg = getIntent().getStringExtra("alertMsg");
            String locationName = getIntent().getStringExtra("locationName");
            String senderPhone = getIntent().getStringExtra("senderPhone");
            if (dangerType != null && "TROUBLE".equalsIgnoreCase(dangerType)) {
                buildReceivedManualUI(senderName, alertMsg, locationName, senderPhone);
            } else {
                buildReceivedDangerUI(dangerType, alertMsg, locationName, senderPhone);
            }
            playAlertSound();
            return;
        }

        if (title == null) title = new NotificationStrings(this).helpAlertDefaultTitle();
        if (body == null) body = new NotificationStrings(this).helpAlertDefaultBody();

        buildUI(title, body);
        playAlertSound();
    }

    private void buildReceivedDangerUI(String dangerType, String alertMsg, String locationName, String senderPhone) {
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

        TextView titleView = new TextView(this);
        String type = dangerType != null && !dangerType.isEmpty() ? dangerType : "unknown";
        titleView.setText(ns.displayDangerType(type));
        titleView.setTextColor(Color.WHITE);
        titleView.setTextSize(28);
        titleView.setGravity(Gravity.CENTER);
        titleView.setPadding(0, 30, 0, 10);
        rootLayout.addView(titleView);

        TextView msgView = new TextView(this);
        msgView.setText(alertMsg != null ? alertMsg : "");
        msgView.setTextColor(Color.WHITE);
        msgView.setTextSize(18);
        msgView.setGravity(Gravity.CENTER);
        msgView.setPadding(0, 10, 0, 40);
        rootLayout.addView(msgView);

        Button phoneBtn = new Button(this);
        if (senderPhone != null && !senderPhone.isEmpty()) {
            phoneBtn.setText(senderPhone);
        } else {
            phoneBtn.setText("Phone number");
        }
        phoneBtn.setTextColor(Color.WHITE);
        phoneBtn.setBackgroundResource(R.drawable.button_ripple);
        phoneBtn.setPadding(24, 24, 24, 24);
        phoneBtn.setGravity(Gravity.CENTER);
        phoneBtn.setClickable(true);
        phoneBtn.setFocusable(true);
        LinearLayout.LayoutParams phoneLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        phoneBtn.setLayoutParams(phoneLP);
        phoneBtn.setOnTouchListener(new View.OnTouchListener() {
            private float downX, downY;
            private long downTime;
            @Override
            public boolean onTouch(View v, MotionEvent event) {
                if (event.getAction() == MotionEvent.ACTION_DOWN) {
                    downX = event.getX();
                    downY = event.getY();
                    downTime = System.currentTimeMillis();
                    ViewParent parent = v.getParent();
                    if (parent != null) parent.requestDisallowInterceptTouchEvent(true);
                    return true;
                } else if (event.getAction() == MotionEvent.ACTION_UP) {
                    float upX = event.getX();
                    float upY = event.getY();
                    long upTime = System.currentTimeMillis();
                    if (Math.abs(upX - downX) < 20 && Math.abs(upY - downY) < 20 && (upTime - downTime) < 300) {
                        String number = phoneBtn.getText().toString().trim();
                        Log.d("HelpAlertActivity", "Phone button tapped, number=" + number);
                        stopAlertSound();
                        if (!number.isEmpty() && !"Phone number".equalsIgnoreCase(number)) {
                            Intent dialIntent = new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(number)));
                            dialIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            Log.d("HelpAlertActivity", "Opening dialer chooser for " + number);
                            startActivity(Intent.createChooser(dialIntent, "Open with"));
                        } else {
                            Log.w("HelpAlertActivity", "Phone number empty or placeholder");
                        }
                        finish();
                    }
                    ViewParent parent = v.getParent();
                    if (parent != null) parent.requestDisallowInterceptTouchEvent(false);
                    return true;
                }
                return false;
            }
        });
        rootLayout.addView(phoneBtn);

        String loc = locationName != null && !locationName.isEmpty() ? locationName : ns.locationUnavailableDefault();
        Button locBtn = new Button(this);
        locBtn.setText(ns.locationLabel() + " : " + loc);
        locBtn.setTextColor(Color.WHITE);
        locBtn.setBackgroundResource(R.drawable.button_ripple);
        locBtn.setTextSize(18);
        locBtn.setGravity(Gravity.CENTER);
        locBtn.setPadding(24, 24, 24, 24);
        locBtn.setClickable(true);
        locBtn.setFocusable(true);
        LinearLayout.LayoutParams locLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        locBtn.setLayoutParams(locLP);
        locBtn.setOnTouchListener(new View.OnTouchListener() {
            private float downX, downY;
            private long downTime;
            @Override
            public boolean onTouch(View v, MotionEvent event) {
                if (event.getAction() == MotionEvent.ACTION_DOWN) {
                    downX = event.getX();
                    downY = event.getY();
                    downTime = System.currentTimeMillis();
                    ViewParent parent = v.getParent();
                    if (parent != null) parent.requestDisallowInterceptTouchEvent(true);
                    return true;
                } else if (event.getAction() == MotionEvent.ACTION_UP) {
                    float upX = event.getX();
                    float upY = event.getY();
                    long upTime = System.currentTimeMillis();
                    if (Math.abs(upX - downX) < 20 && Math.abs(upY - downY) < 20 && (upTime - downTime) < 300) {
                        stopAlertSound();
                        openMap(locationName, null);
                        finish();
                    }
                    ViewParent parent = v.getParent();
                    if (parent != null) parent.requestDisallowInterceptTouchEvent(false);
                    return true;
                }
                return false;
            }
        });
        rootLayout.addView(locBtn);

        Button closeBtn = new Button(this);
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

    private void buildReceivedManualUI(String senderName, String alertMsg, String locationName, String senderPhone) {
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

        TextView titleView = new TextView(this);
        titleView.setText("Danger : TROUBLE");
        titleView.setTextColor(Color.WHITE);
        titleView.setTextSize(28);
        titleView.setGravity(Gravity.CENTER);
        titleView.setPadding(0, 30, 0, 10);
        rootLayout.addView(titleView);

        TextView msgView = new TextView(this);
        msgView.setText(alertMsg != null ? alertMsg : "");
        msgView.setTextColor(Color.WHITE);
        msgView.setTextSize(18);
        msgView.setGravity(Gravity.CENTER);
        msgView.setPadding(0, 10, 0, 20);
        rootLayout.addView(msgView);

        Button phoneBtn = new Button(this);
        if (senderPhone != null && !senderPhone.isEmpty()) {
            phoneBtn.setText(senderPhone);
        } else {
            phoneBtn.setText("Phone number");
        }
        phoneBtn.setTextColor(Color.WHITE);
        phoneBtn.setBackgroundResource(R.drawable.button_ripple);
        phoneBtn.setPadding(24, 24, 24, 24);
        phoneBtn.setGravity(Gravity.CENTER);
        phoneBtn.setClickable(true);
        phoneBtn.setFocusable(true);
        LinearLayout.LayoutParams phoneLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        phoneBtn.setLayoutParams(phoneLP);
        phoneBtn.setOnTouchListener(new View.OnTouchListener() {
            private float downX, downY;
            private long downTime;
            @Override
            public boolean onTouch(View v, MotionEvent event) {
                if (event.getAction() == MotionEvent.ACTION_DOWN) {
                    downX = event.getX();
                    downY = event.getY();
                    downTime = System.currentTimeMillis();
                    ViewParent parent = v.getParent();
                    if (parent != null) parent.requestDisallowInterceptTouchEvent(true);
                    return true;
                } else if (event.getAction() == MotionEvent.ACTION_UP) {
                    float upX = event.getX();
                    float upY = event.getY();
                    long upTime = System.currentTimeMillis();
                    if (Math.abs(upX - downX) < 20 && Math.abs(upY - downY) < 20 && (upTime - downTime) < 300) {
                        String number = phoneBtn.getText().toString().trim();
                        Log.d("HelpAlertActivity", "Phone button tapped, number=" + number);
                        stopAlertSound();
                        if (!number.isEmpty() && !"Phone number".equalsIgnoreCase(number)) {
                            Intent dialIntent = new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(number)));
                            dialIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            Log.d("HelpAlertActivity", "Opening dialer chooser for " + number);
                            startActivity(Intent.createChooser(dialIntent, "Open with"));
                        } else {
                            Log.w("HelpAlertActivity", "Phone number empty or placeholder");
                        }
                        finish();
                    }
                    ViewParent parent = v.getParent();
                    if (parent != null) parent.requestDisallowInterceptTouchEvent(false);
                    return true;
                }
                return false;
            }
        });
        rootLayout.addView(phoneBtn);

        String loc = locationName != null && !locationName.isEmpty() ? locationName : ns.locationUnavailableDefault();
        Button locBtn = new Button(this);
        locBtn.setText(ns.locationLabel() + " : " + loc);
        locBtn.setTextColor(Color.WHITE);
        locBtn.setBackgroundResource(R.drawable.button_ripple);
        locBtn.setTextSize(18);
        locBtn.setGravity(Gravity.CENTER);
        locBtn.setPadding(24, 24, 24, 24);
        locBtn.setClickable(true);
        locBtn.setFocusable(true);
        LinearLayout.LayoutParams locLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        locBtn.setLayoutParams(locLP);
        locBtn.setOnTouchListener(new View.OnTouchListener() {
            private float downX, downY;
            private long downTime;
            @Override
            public boolean onTouch(View v, MotionEvent event) {
                if (event.getAction() == MotionEvent.ACTION_DOWN) {
                    downX = event.getX();
                    downY = event.getY();
                    downTime = System.currentTimeMillis();
                    ViewParent parent = v.getParent();
                    if (parent != null) parent.requestDisallowInterceptTouchEvent(true);
                    return true;
                } else if (event.getAction() == MotionEvent.ACTION_UP) {
                    float upX = event.getX();
                    float upY = event.getY();
                    long upTime = System.currentTimeMillis();
                    if (Math.abs(upX - downX) < 20 && Math.abs(upY - downY) < 20 && (upTime - downTime) < 300) {
                        stopAlertSound();
                        openMap(locationName, null);
                        finish();
                    }
                    ViewParent parent = v.getParent();
                    if (parent != null) parent.requestDisallowInterceptTouchEvent(false);
                    return true;
                }
                return false;
            }
        });
        rootLayout.addView(locBtn);

        Button closeBtn = new Button(this);
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

    private void buildUI(String title, String body) {
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

        TextView titleView = new TextView(this);
        titleView.setText(title);
        titleView.setTextColor(Color.WHITE);
        titleView.setTextSize(26);
        titleView.setGravity(Gravity.CENTER);
        titleView.setPadding(0, 30, 0, 10);
        rootLayout.addView(titleView);

        TextView bodyView = new TextView(this);
        bodyView.setText(body);
        bodyView.setTextColor(Color.parseColor("#FCA5A5"));
        bodyView.setTextSize(18);
        bodyView.setGravity(Gravity.CENTER);
        bodyView.setPadding(0, 20, 0, 40);
        rootLayout.addView(bodyView);

        Button okBtn = new Button(this);
        okBtn.setText(ns.imOk());
        okBtn.setTextSize(20);
        okBtn.setBackgroundColor(Color.parseColor("#16A34A"));
        okBtn.setTextColor(Color.WHITE);
        okBtn.setPadding(40, 40, 40, 40);
        LinearLayout.LayoutParams okLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
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
        helpBtn.setPadding(40, 40, 40, 40);
        LinearLayout.LayoutParams helpLP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        helpLP.setMargins(0, 0, 0, 10);
        helpBtn.setLayoutParams(helpLP);
        helpBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                stopAlertSound();
                finish();
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
                    NotificationStrings nsTimeout = new NotificationStrings(HelpAlertActivity.this);
                    doSendHelp(0, 0, nsTimeout.locationUnavailable("timeout"));
                }
            }
        }, 5000);

        FusedLocationProviderClient client = LocationServices.getFusedLocationProviderClient(this);

        if (androidx.core.app.ActivityCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_FINE_LOCATION)
                != android.content.pm.PackageManager.PERMISSION_GRANTED &&
            androidx.core.app.ActivityCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_COARSE_LOCATION)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            done[0] = true;
            NotificationStrings nsPerm = new NotificationStrings(this);
            doSendHelp(0, 0, nsPerm.locationUnavailable("no permission"));
            return;
        }

        client.getLastLocation().addOnSuccessListener(this, new com.google.android.gms.tasks.OnSuccessListener<android.location.Location>() {
            @Override
            public void onSuccess(android.location.Location location) {
                if (done[0]) return;
                done[0] = true;
                if (location != null) {
                    double lat = location.getLatitude();
                    double lng = location.getLongitude();
                    String name = getLocationName(lat, lng);
                    doSendHelp(lat, lng, name);
                } else {
                    NotificationStrings nsLoc = new NotificationStrings(HelpAlertActivity.this);
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
        NotificationStrings ns = new NotificationStrings(this);
        showResult(ns.sendingHelpRequest());

        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    String apiKey = getFirebaseApiKey();
                    String projectId = getFirebaseProjectId();
                    String currentUserId = getCurrentUserId();

                    if (apiKey == null || projectId == null || currentUserId == null || currentUserId.isEmpty()) {
                        NotificationStrings nsErr = new NotificationStrings(HelpAlertActivity.this);
                        showResult(nsErr.failed("Firebase not configured.\nuserId=" + currentUserId));
                        return;
                    }

                    String userName = senderName != null && !senderName.isEmpty() ? senderName : "Unknown User";

                    String accessToken = getSharedPreferences("capacitor", MODE_PRIVATE)
                            .getString("firebase_auth_token", "");
                    if (accessToken.isEmpty()) {
                        try {
                            accessToken = FcmHelper.getAccessToken(HelpAlertActivity.this);
                        } catch (Exception e) {
                            NotificationStrings nsErr = new NotificationStrings(HelpAlertActivity.this);
                            showResult(nsErr.failed("Auth token failed: " + e.getMessage()));
                            return;
                        }
                    }

                    String senderPhone = getSharedPreferences("capacitor", MODE_PRIVATE)
                            .getString("current_user_phone", "");
                    if (senderPhone.isEmpty()) {
                        try {
                            String senderDoc = httpGetWithAuth("https://firestore.googleapis.com/v1/projects/"
                                    + projectId + "/databases/(default)/documents/users/" + currentUserId, accessToken);
                            if (senderDoc != null && senderDoc.contains("stringValue")) {
                                JSONObject senderObj = new JSONObject(senderDoc);
                                JSONObject senderFields = senderObj.optJSONObject("fields");
                                if (senderFields != null) {
                                    JSONObject phoneObj = senderFields.optJSONObject("phone");
                                    if (phoneObj != null) senderPhone = phoneObj.optString("stringValue", "");
                                }
                            }
                        } catch (Exception e) {
                            Log.w("HelpAlertActivity", "Failed to get sender phone: " + e.getMessage());
                        }
                    }

                    String alertMsg = userName + " " + ns.needsHelp() + "!\n"
                            + ns.pushTitle(dangerType) + "\n"
                            + ns.locationLabel() + ": " + locationName;
                    if (lat != 0) {
                        alertMsg += String.format(Locale.getDefault(), " (%.4f, %.4f)", lat, lng);
                    }
                    if (senderPhone != null && !senderPhone.isEmpty()) {
                        alertMsg += "\n" + ns.locationLabel() + ": " + senderPhone;
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

                    String fcmAccessToken = accessToken;
                    if (fcmAccessToken.startsWith("ey")) {
                        try {
                            fcmAccessToken = FcmHelper.getAccessToken(HelpAlertActivity.this);
                        } catch (Exception e) {
                            Log.e("HelpAlertActivity", "getAccessToken failed", e);
                        }
                    }

                    String queryBody = "{\"structuredQuery\":{\"from\":[{\"collectionId\":\"group_members\"}],"
                            + "\"where\":{\"fieldFilter\":{\"field\":{\"fieldPath\":\"groupId\"},"
                            + "\"op\":\"EQUAL\","
                            + "\"value\":{\"stringValue\":\"" + currentUserId + "\"}}},"
                            + "\"limit\":100}}";
                    String membersUrl = "https://firestore.googleapis.com/v1/projects/"
                            + projectId + "/databases/(default)/documents:runQuery";
                    String membersJson = httpPostWithAuth(membersUrl, queryBody, fcmAccessToken);

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
                                    fcmAccessToken);
                            String fcmToken = null;
                            if (memberDoc != null && memberDoc.contains("stringValue")) {
                                JSONObject memberDocObj = new JSONObject(memberDoc);
                                JSONObject memberFields = memberDocObj.optJSONObject("fields");
                                if (memberFields != null) {
                                    JSONObject fcmObj = memberFields.optJSONObject("fcmToken");
                                    if (fcmObj != null) fcmToken = fcmObj.optString("stringValue", "");
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
                                Log.e("HelpAlertActivity", "FCM push failed", fcmErr);
                            }
                        }
                    }

                    try {
                        saveHelpMessage(fcmAccessToken, projectId, currentUserId, userName, dangerType, alertMsg, lat, lng, locationName, memberUids);
                        helpSaveStatus = "HelpHistory: saved to Firestore";
                    } catch (Exception e) {
                        helpSaveStatus = "HelpHistory: save failed - " + e.getMessage();
                    }

                    String debugInfo = "\n[Debug] Members: " + parsedCount
                            + " | Empty tokens: " + emptyTokens
                            + " | FCM sent: " + fcmSent
                            + "\nYour token: " + (savedFcm.isEmpty() ? "NONE" : savedFcm.substring(0, Math.min(20, savedFcm.length())) + "...")
                            + "\nMember0 token: " + debugMemberToken
                            + (fcmFailed > 0 ? "\nFCM Error(" + fcmFailed + "): " : "")
                            + (fcmFailed == 0 ? "" : "\nAccessToken Error: ");

                    if (fcmSent > 0) {
                        showResult(ns.pushSentTo(fcmSent));
                    } else if (parsedCount > 0 && emptyTokens > 0) {
                        showResult(ns.foundMembersNoTokens(parsedCount) + debugInfo + "\n" + helpSaveStatus);
                    } else if (parsedCount > 0 && fcmFailed > 0) {
                        showResult(ns.foundMembersPushFailed(parsedCount) + debugInfo + "\n" + helpSaveStatus);
                    } else {
                        showResult(ns.noTrustedMembers() + debugInfo + "\n" + helpSaveStatus);
                    }

                } catch (Exception e) {
                    NotificationStrings nsCatch = new NotificationStrings(HelpAlertActivity.this);
                    showResult(nsCatch.failed(e.getMessage()));
                }
            }
        }).start();
    }

    private void showResult(final String message) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                rootLayout.removeAllViews();

                TextView check = new TextView(HelpAlertActivity.this);
                check.setText("\u2714");
                check.setTextSize(48);
                check.setGravity(Gravity.CENTER);
                rootLayout.addView(check);

                TextView txt = new TextView(HelpAlertActivity.this);
                txt.setText(message);
                txt.setTextColor(Color.WHITE);
                txt.setTextSize(16);
                txt.setGravity(Gravity.CENTER);
                txt.setPadding(0, 20, 0, 40);
                rootLayout.addView(txt);

                Button closeBtn = new Button(HelpAlertActivity.this);
                NotificationStrings nsClose = new NotificationStrings(HelpAlertActivity.this);
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

    private void saveHelpMessage(String accessToken, String projectId, String currentUserId, String userName, String dangerType, String alertMsg, double lat, double lng, String locationName, java.util.List<String> receiverIds) throws Exception {
        if (accessToken == null || accessToken.isEmpty()) {
            Log.w("HelpAlertActivity", "saveHelpMessage skipped: empty accessToken");
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

        Log.i("HelpAlertActivity", "saveHelpMessage POST url=" + url);
        String helpSaveResult = httpPostWithAuth(url, body, accessToken);
        Log.i("HelpAlertActivity", "saveHelpMessage result=" + (helpSaveResult != null ? helpSaveResult.substring(0, Math.min(200, helpSaveResult.length())) : "null"));
    }

    private String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "");
    }

    private void openMap(String locationName, String alertMsg) {
        String query = locationName != null && !locationName.isEmpty() ? locationName : "";

        if (alertMsg != null) {
            int lastParen = alertMsg.lastIndexOf('(');
            if (lastParen >= 0) {
                int closeParen = alertMsg.indexOf(')', lastParen);
                if (closeParen > lastParen) {
                    String coords = alertMsg.substring(lastParen + 1, closeParen);
                    String[] parts = coords.split(",");
                    if (parts.length == 2) {
                        try {
                            double lat = Double.parseDouble(parts[0].trim());
                            double lng = Double.parseDouble(parts[1].trim());
                            String geoUri = "geo:" + lat + "," + lng;
                            if (!query.isEmpty()) geoUri += "?q=" + Uri.encode(query);
                            Intent mapIntent = new Intent(Intent.ACTION_VIEW, Uri.parse(geoUri));
                            mapIntent.setPackage("com.google.android.apps.maps");
                            if (mapIntent.resolveActivity(getPackageManager()) != null) {
                                startActivity(mapIntent);
                                return;
                            }
                        } catch (NumberFormatException e) {
                        }
                    }
                }
            }
        }

        if (!query.isEmpty()) {
            String geoUri = "geo:0,0?q=" + Uri.encode(query);
            Intent geoIntent = new Intent(Intent.ACTION_VIEW, Uri.parse(geoUri));
            startActivity(Intent.createChooser(geoIntent, "Open with"));
            return;
        }

        Log.w("HelpAlertActivity", "No app can handle map intent for query: " + query);
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
            Log.w("HelpAlertActivity", "playAlertSound failed", e);
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
        super.onDestroy();
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
            Log.w("HelpAlertActivity", "HTTP " + code + " for " + urlStr + " body=" + err);
            throw new Exception("HTTP " + code + " body=" + err);
        }
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
}
