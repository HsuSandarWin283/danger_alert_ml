package com.danger.alert;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.graphics.Color;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

import androidx.core.app.ActivityCompat;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import org.json.JSONObject;

public class MonitoringService extends Service {
    private static final String TAG = "MonitoringService";
    private static final String TAG_AUDIO = "DangerAudio";
    private static final String TAG_RMS = "DangerRMS";
    private static final String TAG_API = "DangerAPI";
    private static final String TAG_MONITOR = "DangerMonitor";
    private static final String CHANNEL_ID = "danger_monitoring";
    private static final String ALERT_CHANNEL_ID = "danger_alert";
    private static final int NOTIFICATION_ID = 1001;
    private static final int ALERT_NOTIFICATION_ID = 2001;
    private static final int SAMPLE_RATE = 22050;
    private static final int DURATION_SECONDS = 3;
    private static final String DEFAULT_API_URL = "http://192.168.99.112:8000";
    private static final long KEEPALIVE_INTERVAL_MS = 15 * 1000;
    private static final double RMS_THRESHOLD = 0.004;
    private static final double CONFIDENCE_THRESHOLD = 0.88;
    private static final long DUPLICATE_ALERT_MS = 10000;
    private static final long DANGER_COOLDOWN_MS = 3000;
    private static final long ANALYSIS_INTERVAL_MS = 1000;
    private static final java.util.Set<String> DANGER_LABELS = new java.util.HashSet<>(
        java.util.Arrays.asList("accident", "gunshot", "scream")
    );
    public static final String OFFLINE_CHANNEL_ID = "danger_offline";
    public static final int OFFLINE_NOTIFICATION_ID = 2002;
    public static final int OFFLINE_KEEPALIVE_THRESHOLD = 1;

    private AudioRecord audioRecord;
    private AtomicBoolean isRecording = new AtomicBoolean(false);
    private ExecutorService executor;
    private ExecutorService apiExecutor;
    private String apiUrl;
    private int bufferSize;
    private Handler keepaliveHandler;
    private AtomicInteger pendingApiCalls = new AtomicInteger(0);

    private short[] circularBuffer;
    private int circularBufferIndex = 0;
    private long lastAnalysisTime = 0;
    private boolean isDangerState = false;
    private long lastDangerTime = 0;
    private String lastAlertLabel = null;
    private long lastAlertTime = 0;
    private int keepaliveFailures = 0;
    private boolean isOfflineAlerted = false;

    public static final String ACTION_START = "com.danger.alert.START_MONITORING";
    public static final String ACTION_STOP = "com.danger.alert.STOP_MONITORING";
    public static final String ACTION_TRIGGER_OFFLINE_ALERT = "com.danger.alert.TRIGGER_OFFLINE_ALERT";
    public static final String EXTRA_API_URL = "api_url";

    @Override
    public void onCreate() {
        super.onCreate();
        executor = Executors.newSingleThreadExecutor();
        apiExecutor = Executors.newFixedThreadPool(2);
        keepaliveHandler = new Handler(Looper.getMainLooper());
        createNotificationChannel();
        Log.i(TAG_MONITOR, "MonitoringService onCreate");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopMonitoring();
            stopOfflineAlert();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return START_NOT_STICKY;
        }

        if (intent != null && "com.danger.alert.ACTION_DISMISS_OFFLINE_ALERT".equals(intent.getAction())) {
            stopOfflineAlert();
            return START_STICKY;
        }

        if (intent != null && ACTION_TRIGGER_OFFLINE_ALERT.equals(intent.getAction())) {
            triggerOfflineAlert();
            return START_STICKY;
        }

        apiUrl = intent != null ? intent.getStringExtra(EXTRA_API_URL) : DEFAULT_API_URL;
        if (apiUrl == null || apiUrl.isEmpty()) {
            apiUrl = DEFAULT_API_URL;
        }
        Log.i(TAG_MONITOR, "MonitoringService started");
        Log.i(TAG_MONITOR, "API URL: " + apiUrl);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
                Log.w(TAG, "POST_NOTIFICATIONS permission not granted, starting foreground anyway");
            }
        }

        NotificationStrings ns = new NotificationStrings(this);

        Notification notification = buildNotification(ns.monitoringForDangerSounds());
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
        startMonitoring();

        return START_STICKY;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationStrings ns = new NotificationStrings(this);

            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    ns.channelMonitoringName(),
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription(ns.channelMonitoringDesc());
            channel.setSound(null, null);

            NotificationChannel alertChannel = new NotificationChannel(
                    ALERT_CHANNEL_ID,
                    ns.channelAlertsName(),
                    NotificationManager.IMPORTANCE_HIGH
            );
            alertChannel.setDescription(ns.channelAlertsDesc());
            alertChannel.enableVibration(true);
            alertChannel.setVibrationPattern(new long[]{0, 500, 200, 500});
            alertChannel.enableLights(true);
            alertChannel.setLightColor(Color.RED);

            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(channel);
                manager.createNotificationChannel(alertChannel);

                NotificationChannel offlineChannel = new NotificationChannel(
                        OFFLINE_CHANNEL_ID,
                        "Model Offline Alert",
                        NotificationManager.IMPORTANCE_HIGH
                );
                offlineChannel.setDescription("Alert when model server is offline");
                offlineChannel.enableVibration(true);
                offlineChannel.setVibrationPattern(new long[]{0, 500, 200, 500});
                offlineChannel.enableLights(true);
                offlineChannel.setLightColor(Color.RED);
                offlineChannel.setSound(null, null);

                manager.createNotificationChannel(offlineChannel);
            }
        }
    }

    private Notification buildNotification(String text) {
        Intent launchIntent = getPackageManager().getLaunchIntentForPackage(getPackageName());
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Intent stopIntent = new Intent(this, MonitoringService.class);
        stopIntent.setAction(ACTION_STOP);
        PendingIntent stopPendingIntent = PendingIntent.getService(
                this, 0, stopIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        NotificationStrings ns = new NotificationStrings(this);

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(ns.notificationTitle())
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentIntent(pendingIntent)
                .addAction(android.R.drawable.ic_media_pause, ns.stop(), stopPendingIntent)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setCategory(NotificationCompat.CATEGORY_SERVICE)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .build();
    }

    private void updateNotification(String text) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) {
            manager.notify(NOTIFICATION_ID, buildNotification(text));
        }
    }

    private void startMonitoring() {
        if (isRecording.get()) return;

        bufferSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
        );
        bufferSize = Math.max(bufferSize, SAMPLE_RATE * 2);
        Log.i(TAG_AUDIO, "AudioRecord config: sampleRate=" + SAMPLE_RATE
                + " channel=MONO encoding=PCM_16BIT bufferSize=" + bufferSize);

        try {
            audioRecord = new AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    bufferSize
            );
        } catch (SecurityException e) {
            Log.e(TAG, "Microphone permission not granted", e);
            NotificationStrings ns = new NotificationStrings(this);
            updateNotification(ns.micPermissionDenied());
            return;
        }

        if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
            Log.e(TAG_AUDIO, "AudioRecord failed to initialize");
            NotificationStrings ns = new NotificationStrings(this);
            updateNotification(ns.audioUnavailable());
            return;
        }
        Log.i(TAG_AUDIO, "AudioRecord initialized successfully");

        isRecording.set(true);
        audioRecord.startRecording();
        Log.i(TAG_AUDIO, "AudioRecord recording started");
        getSharedPreferences("capacitor", MODE_PRIVATE)
                .edit().putBoolean("monitoring_running", true).apply();
        BackgroundMonitorPlugin.notifyStateChange(true);
        Log.i(TAG, "Monitoring started");
        NotificationStrings ns2 = new NotificationStrings(this);
        updateNotification(ns2.listeningForDangerSounds());

        executor.execute(this::recordingLoop);
        startKeepAlive();
    }

    private void startKeepAlive() {
        keepaliveHandler.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (!isRecording.get()) return;
                apiExecutor.execute(() -> {
                    try {
                        HttpURLConnection c = (HttpURLConnection) new URL(apiUrl + "/health").openConnection();
                        c.setRequestMethod("GET");
                        c.setConnectTimeout(5000);
                        c.setReadTimeout(5000);
                        c.getResponseCode();
                        c.disconnect();
                        Log.d(TAG, "Keep-alive ping OK");

                        if (isOfflineAlerted) {
                            stopOfflineAlert();
                        }
                        keepaliveFailures = 0;
                    } catch (Exception e) {
                        Log.w(TAG, "Keep-alive ping failed", e);
                        keepaliveFailures++;
                        if (keepaliveFailures >= OFFLINE_KEEPALIVE_THRESHOLD && !isOfflineAlerted) {
                            triggerOfflineAlert();
                        }
                    }
                });
                keepaliveHandler.postDelayed(this, KEEPALIVE_INTERVAL_MS);
            }
        }, KEEPALIVE_INTERVAL_MS);
        Log.i(TAG_API, "Keep-alive started interval=" + KEEPALIVE_INTERVAL_MS + "ms");
    }

    private void triggerOfflineAlert() {
        isOfflineAlerted = true;
        NotificationStrings ns = new NotificationStrings(this);

        Intent deleteIntent = new Intent(this, MonitoringService.class);
        deleteIntent.setAction("com.danger.alert.ACTION_DISMISS_OFFLINE_ALERT");
        PendingIntent deletePendingIntent = PendingIntent.getService(
                this, 0, deleteIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Intent launchIntent = getPackageManager().getLaunchIntentForPackage(getPackageName());
        PendingIntent contentPending = PendingIntent.getActivity(
                this, 0, launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, OFFLINE_CHANNEL_ID)
                .setContentTitle(ns.modelOfflineTitle())
                .setContentText(ns.modelOfflineMessage())
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentIntent(contentPending)
                .setDeleteIntent(deletePendingIntent)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_STATUS)
                .setAutoCancel(false);

        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) {
            manager.notify(OFFLINE_NOTIFICATION_ID, builder.build());
        }
    }

    private void stopOfflineAlert() {
        isOfflineAlerted = false;
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) {
            manager.cancel(OFFLINE_NOTIFICATION_ID);
        }
    }

    private void recordingLoop() {
        final int windowSamples = SAMPLE_RATE * DURATION_SECONDS;
        final int readChunkSize = 1024;
        short[] readBuffer = new short[readChunkSize];
        circularBuffer = new short[windowSamples];
        circularBufferIndex = 0;
        lastAnalysisTime = System.currentTimeMillis();

        Log.i(TAG_AUDIO, "Recording loop started. windowSamples=" + windowSamples + " readChunkSize=" + readChunkSize);

        while (isRecording.get()) {
            int read = audioRecord.read(readBuffer, 0, readChunkSize);
            if (read > 0) {
                for (int i = 0; i < read; i++) {
                    circularBuffer[circularBufferIndex] = readBuffer[i];
                    circularBufferIndex = (circularBufferIndex + 1) % windowSamples;
                }
            } else {
                Log.w(TAG_AUDIO, "AudioRecord read failed or stopped, read=" + read);
                break;
            }

            long now = System.currentTimeMillis();
            if (now - lastAnalysisTime >= ANALYSIS_INTERVAL_MS && pendingApiCalls.get() < 2) {
                lastAnalysisTime = now;
                analyzeWindow();
            }
        }
    }

    private void analyzeWindow() {
        final int windowSamples = SAMPLE_RATE * DURATION_SECONDS;
        short[] windowCopy = new short[windowSamples];
        int firstPart = windowSamples - circularBufferIndex;
        System.arraycopy(circularBuffer, circularBufferIndex, windowCopy, 0, firstPart);
        System.arraycopy(circularBuffer, 0, windowCopy, firstPart, circularBufferIndex);

        double rms = calculateRms(windowCopy, windowSamples);
        Log.i(TAG_RMS, "rms=" + String.format("%.6f", rms) + " threshold=" + RMS_THRESHOLD);

        if (rms < RMS_THRESHOLD) {
            Log.i(TAG_RMS, "RMS BELOW threshold -> SKIP prediction");
            if (isDangerState && (System.currentTimeMillis() - lastDangerTime > DANGER_COOLDOWN_MS)) {
                isDangerState = false;
                lastAlertLabel = null;
                Log.i(TAG_MONITOR, "STATE=NORMAL cooldownExpired=true");
            }
            return;
        }

        Log.i(TAG_RMS, "RMS ABOVE threshold -> SEND prediction");

        final short[] chunkCopy = new short[windowSamples];
        System.arraycopy(windowCopy, 0, chunkCopy, 0, windowSamples);
        final double chunkRms = rms;

        pendingApiCalls.incrementAndGet();
        apiExecutor.execute(() -> {
            try {
                if (!isRecording.get()) {
                    Log.i(TAG_API, "Skipping predict because monitoring stopped");
                    return;
                }

                byte[] wavData = createWav(chunkCopy, chunkCopy.length, SAMPLE_RATE);
                Log.i(TAG_AUDIO, "WAV created: samples=" + chunkCopy.length
                        + " duration=" + (chunkCopy.length / (float) SAMPLE_RATE)
                        + " size=" + wavData.length + " bytes");
                Log.i(TAG_API, "POST /predict START url=" + apiUrl + "/predict wavSize=" + wavData.length);
                long t0 = System.currentTimeMillis();
                String result = sendToApi(wavData);
                long elapsed = System.currentTimeMillis() - t0;
                Log.i(TAG_API, "POST /predict END duration=" + elapsed + "ms result=" + result);
                if (result != null) {
                    handleResult(result, chunkRms);
                }
            } catch (Exception e) {
                Log.e(TAG, "Error processing audio window", e);
            } finally {
                pendingApiCalls.decrementAndGet();
            }
        });
    }

    private double calculateRms(short[] samples, int length) {
        double sum = 0;
        for (int i = 0; i < length; i++) {
            double s = samples[i] / 32768.0;
            sum += s * s;
        }
        return Math.sqrt(sum / length);
    }

    private byte[] createWav(short[] samples, int length, int sampleRate) throws IOException {
        int byteRate = sampleRate * 2;
        int dataSize = length * 2;
        int fileSize = 36 + dataSize;

        ByteArrayOutputStream baos = new ByteArrayOutputStream(44 + dataSize);
        DataOutputStream dos = new DataOutputStream(baos);

        dos.writeBytes("RIFF");
        dos.writeInt(Integer.reverseBytes(fileSize));
        dos.writeBytes("WAVE");
        dos.writeBytes("fmt ");
        dos.writeInt(Integer.reverseBytes(16));
        dos.writeShort(Short.reverseBytes((short) 1));
        dos.writeShort(Short.reverseBytes((short) 1));
        dos.writeInt(Integer.reverseBytes(sampleRate));
        dos.writeInt(Integer.reverseBytes(byteRate));
        dos.writeShort(Short.reverseBytes((short) 2));
        dos.writeShort(Short.reverseBytes((short) 16));
        dos.writeBytes("data");
        dos.writeInt(Integer.reverseBytes(dataSize));

        ByteBuffer bb = ByteBuffer.allocate(dataSize).order(ByteOrder.LITTLE_ENDIAN);
        for (int i = 0; i < length; i++) {
            bb.putShort(samples[i]);
        }
        dos.write(bb.array());
        dos.flush();

        return baos.toByteArray();
    }

    private String sendToApi(byte[] wavData) {
        HttpURLConnection conn = null;
        long startTime = System.currentTimeMillis();
        try {
            String boundary = "----FormBoundary" + System.currentTimeMillis();
            URL url = new URL(apiUrl + "/predict");

            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(10000);
            conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);

            Log.i(TAG_API, "POST /predict START url=" + url + " wavSize=" + wavData.length
                    + " connectTimeout=8000 readTimeout=10000");

            DataOutputStream dos = new DataOutputStream(conn.getOutputStream());
            dos.writeBytes("--" + boundary + "\r\n");
            dos.writeBytes("Content-Disposition: form-data; name=\"file\"; filename=\"monitor.wav\"\r\n");
            dos.writeBytes("Content-Type: audio/wav\r\n\r\n");
            dos.write(wavData);
            dos.writeBytes("\r\n--" + boundary + "--\r\n");
            dos.flush();
            dos.close();

            int code = conn.getResponseCode();
            long elapsed = System.currentTimeMillis() - startTime;
            if (code == 200) {
                byte[] responseBytes = conn.getInputStream().readAllBytes();
                String response = new String(responseBytes);
                Log.i(TAG_API, "POST /predict RESPONSE code=200 duration=" + elapsed + "ms response=" + response);
                return response;
            } else {
                Log.w(TAG_API, "POST /predict RESPONSE code=" + code + " duration=" + elapsed + "ms");
            }
        } catch (java.net.SocketTimeoutException e) {
            long elapsed = System.currentTimeMillis() - startTime;
            Log.e(TAG_API, "TIMEOUT after " + elapsed + "ms url=" + apiUrl + "/predict", e);
        } catch (java.net.SocketException e) {
            long elapsed = System.currentTimeMillis() - startTime;
            Log.e(TAG_API, "SOCKET ERROR after " + elapsed + "ms url=" + apiUrl + "/predict", e);
        } catch (Exception e) {
            long elapsed = System.currentTimeMillis() - startTime;
            Log.e(TAG_API, "API request failed after " + elapsed + "ms url=" + apiUrl + "/predict", e);
        } finally {
            if (conn != null) conn.disconnect();
        }
        return null;
    }

    private void handleResult(String json, double rms) {
        try {
            JSONObject obj = new JSONObject(json);
            String prediction = obj.optString("prediction", "unknown");
            double confidence = obj.optDouble("confidence", 0);
            boolean serverIsDanger = obj.optBoolean("is_danger", false);
            String reason = obj.optString("reason", "unknown");
            JSONObject probsObj = obj.optJSONObject("probabilities");
            String probabilities = probsObj != null ? probsObj.toString() : "{}";

            Log.i(TAG_MONITOR, "prediction=" + prediction
                    + " confidence=" + String.format("%.6f", confidence)
                    + " rms=" + String.format("%.6f", rms)
                    + " serverIsDanger=" + serverIsDanger
                    + " reason=" + reason
                    + " probabilities=" + probabilities);

            long now = System.currentTimeMillis();

            Log.i(TAG_MONITOR, "serverIsDanger=" + serverIsDanger + " state=" + (isDangerState ? "DANGER" : "NORMAL"));

            if (serverIsDanger) {
                lastDangerTime = now;

                if (!isDangerState) {
                    boolean isDuplicate = false;
                    if (lastAlertLabel != null && lastAlertLabel.equals(prediction)) {
                        isDuplicate = (now - lastAlertTime) < DUPLICATE_ALERT_MS;
                    }

                    if (!isDuplicate) {
                        isDangerState = true;
                        lastAlertLabel = prediction;
                        lastAlertTime = now;

                        Log.i(TAG_MONITOR, "STATE=DANGER ACTION=TRIGGER_ALERT prediction=" + prediction + " confidence=" + confidence);

                        NotificationStrings ns = new NotificationStrings(this);
                        Intent alertIntent = new Intent(this, DangerAlertActivity.class);
                        alertIntent.putExtra("danger_type", prediction);
                        alertIntent.putExtra("confidence", confidence);
                        alertIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);

                        PendingIntent contentPending = PendingIntent.getActivity(
                                this, 0, alertIntent,
                                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE
                        );

                        NotificationCompat.Builder alertBuilder = new NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
                                .setContentTitle(ns.dangerDetectedTitle(prediction))
                                .setContentText(ns.areYouOk())
                                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                                .setPriority(NotificationCompat.PRIORITY_MAX)
                                .setCategory(NotificationCompat.CATEGORY_ALARM)
                                .setFullScreenIntent(contentPending, true)
                                .setContentIntent(contentPending)
                                .setAutoCancel(true)
                                .setVibrate(new long[]{0, 500, 200, 500})
                                .setLights(Color.RED, 500, 500);

                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                            alertBuilder.setDefaults(Notification.DEFAULT_VIBRATE | Notification.DEFAULT_SOUND);
                        }

                        NotificationManager manager = getSystemService(NotificationManager.class);
                        if (manager != null) {
                            manager.notify(ALERT_NOTIFICATION_ID, alertBuilder.build());
                        }

                        try {
                            startActivity(alertIntent);
                        } catch (Exception e) {
                            Log.w(TAG, "Cannot start activity from background", e);
                        }
                    } else {
                        Log.i(TAG_MONITOR, "STATE=DANGER ACTION=DUPLICATE_SUPPRESSED prediction=" + prediction + " confidence=" + confidence);
                    }
                } else {
                    Log.i(TAG_MONITOR, "STATE=DANGER ACTION=IGNORE prediction=" + prediction + " confidence=" + confidence);
                }
            } else {
                if (isDangerState) {
                    long timeSinceDanger = now - lastDangerTime;
                    if (timeSinceDanger > DANGER_COOLDOWN_MS) {
                        isDangerState = false;
                        lastAlertLabel = null;
                        Log.i(TAG_MONITOR, "STATE=NORMAL cooldownExpired=true");
                    } else {
                        Log.i(TAG_MONITOR, "STATE=DANGER cooldownRemaining=" + (DANGER_COOLDOWN_MS - timeSinceDanger) + "ms");
                    }
                } else {
                    Log.i(TAG_MONITOR, "STATE=NORMAL ACTION=IGNORE prediction=" + prediction + " confidence=" + confidence + " reason=" + reason);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error parsing result", e);
        }
    }

    private void stopMonitoring() {
        Log.i(TAG_MONITOR, "stopMonitoring called");
        isRecording.set(false);
        keepaliveHandler.removeCallbacksAndMessages(null);
        stopOfflineAlert();
        getSharedPreferences("capacitor", MODE_PRIVATE)
                .edit().putBoolean("monitoring_running", false).apply();
        BackgroundMonitorPlugin.notifyStateChange(false);

        if (audioRecord != null) {
            try {
                audioRecord.stop();
            } catch (Exception e) {
                Log.e(TAG, "Error stopping AudioRecord", e);
            }
            try {
                audioRecord.release();
            } catch (Exception e) {
                Log.e(TAG, "Error releasing AudioRecord", e);
            }
            audioRecord = null;
        }

        if (executor != null) {
            executor.shutdownNow();
            executor = Executors.newSingleThreadExecutor();
        }

        if (apiExecutor != null) {
            apiExecutor.shutdownNow();
            apiExecutor = Executors.newFixedThreadPool(2);
        }

        circularBuffer = null;
        circularBufferIndex = 0;
        lastAnalysisTime = 0;
        isDangerState = false;
        lastDangerTime = 0;
        lastAlertLabel = null;
        lastAlertTime = 0;
        Log.i(TAG_MONITOR, "Monitoring stopped");
    }

    @Override
    public void onDestroy() {
        stopMonitoring();
        stopOfflineAlert();
        if (executor != null) {
            executor.shutdownNow();
        }
        if (apiExecutor != null) {
            apiExecutor.shutdownNow();
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
