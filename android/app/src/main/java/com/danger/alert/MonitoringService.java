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
import android.os.IBinder;
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
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

import org.json.JSONObject;

public class MonitoringService extends Service {
    private static final String TAG = "MonitoringService";
    private static final String CHANNEL_ID = "danger_monitoring";
    private static final String ALERT_CHANNEL_ID = "danger_alert";
    private static final int NOTIFICATION_ID = 1001;
    private static final int ALERT_NOTIFICATION_ID = 2001;
    private static final int SAMPLE_RATE = 22050;
    private static final int DURATION_SECONDS = 5;
    private static final String DEFAULT_API_URL = "https://danger-alert-ml.onrender.com";

    private AudioRecord audioRecord;
    private AtomicBoolean isRecording = new AtomicBoolean(false);
    private ExecutorService executor;
    private String apiUrl;
    private int bufferSize;

    public static final String ACTION_START = "com.danger.alert.START_MONITORING";
    public static final String ACTION_STOP = "com.danger.alert.STOP_MONITORING";
    public static final String EXTRA_API_URL = "api_url";

    @Override
    public void onCreate() {
        super.onCreate();
        executor = Executors.newSingleThreadExecutor();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopMonitoring();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return START_NOT_STICKY;
        }

        apiUrl = intent != null ? intent.getStringExtra(EXTRA_API_URL) : DEFAULT_API_URL;
        if (apiUrl == null || apiUrl.isEmpty()) {
            apiUrl = DEFAULT_API_URL;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
                Log.w(TAG, "POST_NOTIFICATIONS permission not granted, starting foreground anyway");
            }
        }

        Notification notification = buildNotification("Monitoring for danger sounds...");
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
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Danger Sound Monitoring",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Shows when danger sound monitoring is active");
            channel.setSound(null, null);

            NotificationChannel alertChannel = new NotificationChannel(
                    ALERT_CHANNEL_ID,
                    "Danger Alerts",
                    NotificationManager.IMPORTANCE_HIGH
            );
            alertChannel.setDescription("Critical danger sound alerts");
            alertChannel.enableVibration(true);
            alertChannel.setVibrationPattern(new long[]{0, 500, 200, 500});
            alertChannel.enableLights(true);
            alertChannel.setLightColor(Color.RED);

            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(channel);
                manager.createNotificationChannel(alertChannel);
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

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Danger Alert")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentIntent(pendingIntent)
                .addAction(android.R.drawable.ic_media_pause, "Stop", stopPendingIntent)
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
            updateNotification("Microphone permission denied");
            return;
        }

        if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
            Log.e(TAG, "AudioRecord failed to initialize");
            updateNotification("Audio recording unavailable");
            return;
        }

        isRecording.set(true);
        audioRecord.startRecording();
        Log.i(TAG, "Monitoring started");
        updateNotification("Listening for danger sounds...");

        executor.execute(this::recordingLoop);
    }

    private void recordingLoop() {
        int samplesPerChunk = SAMPLE_RATE * DURATION_SECONDS;
        short[] audioBuffer = new short[samplesPerChunk];

        while (isRecording.get()) {
            int totalRead = 0;
            while (totalRead < samplesPerChunk && isRecording.get()) {
                int remaining = samplesPerChunk - totalRead;
                int read = audioRecord.read(audioBuffer, totalRead, remaining);
                if (read > 0) {
                    totalRead += read;
                } else {
                    break;
                }
            }

            if (totalRead < samplesPerChunk || !isRecording.get()) {
                continue;
            }

            double rms = calculateRms(audioBuffer, totalRead);
            if (rms < 0.003) {
                continue;
            }

            try {
                byte[] wavData = createWav(audioBuffer, totalRead, SAMPLE_RATE);
                String result = sendToApi(wavData);
                if (result != null) {
                    handleResult(result, rms);
                }
            } catch (Exception e) {
                Log.e(TAG, "Error processing audio chunk", e);
            }
        }
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
        try {
            String boundary = "----FormBoundary" + System.currentTimeMillis();
            URL url = new URL(apiUrl + "/predict");

            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(15000);
            conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);

            DataOutputStream dos = new DataOutputStream(conn.getOutputStream());
            dos.writeBytes("--" + boundary + "\r\n");
            dos.writeBytes("Content-Disposition: form-data; name=\"file\"; filename=\"monitor.wav\"\r\n");
            dos.writeBytes("Content-Type: audio/wav\r\n\r\n");
            dos.write(wavData);
            dos.writeBytes("\r\n--" + boundary + "--\r\n");
            dos.flush();
            dos.close();

            int code = conn.getResponseCode();
            if (code == 200) {
                byte[] responseBytes = conn.getInputStream().readAllBytes();
                return new String(responseBytes);
            } else {
                Log.w(TAG, "API returned status: " + code);
            }
        } catch (Exception e) {
            Log.e(TAG, "API request failed", e);
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

            if (!prediction.equals("normal") && confidence >= 0.6) {
                Log.i(TAG, "Danger detected: " + prediction + " (" + confidence + ")");

                Intent alertIntent = new Intent(this, DangerAlertActivity.class);
                alertIntent.putExtra("danger_type", prediction);
                alertIntent.putExtra("confidence", confidence);
                alertIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);

                PendingIntent contentPending = PendingIntent.getActivity(
                        this, 0, alertIntent,
                        PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE
                );

                NotificationCompat.Builder alertBuilder = new NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
                        .setContentTitle("DANGER: " + prediction.toUpperCase() + " detected!")
                        .setContentText("Are you OK?")
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
            }
        } catch (Exception e) {
            Log.e(TAG, "Error parsing result", e);
        }
    }

    private void stopMonitoring() {
        isRecording.set(false);
        if (audioRecord != null) {
            try {
                audioRecord.stop();
                audioRecord.release();
            } catch (Exception e) {
                Log.e(TAG, "Error stopping AudioRecord", e);
            }
            audioRecord = null;
        }
        Log.i(TAG, "Monitoring stopped");
    }

    @Override
    public void onDestroy() {
        stopMonitoring();
        if (executor != null) {
            executor.shutdownNow();
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
