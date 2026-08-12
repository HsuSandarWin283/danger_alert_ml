package com.danger.alert;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.PowerManager;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class HelpAlertActivity extends AppCompatActivity {

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
                "HelpAlert:wake"
        );
        wakeLock.acquire(120000);

        String title = getIntent().getStringExtra("title");
        String body = getIntent().getStringExtra("body");

        NotificationStrings ns = new NotificationStrings(this);
        if (title == null) title = ns.helpAlertDefaultTitle();
        if (body == null) body = ns.helpAlertDefaultBody();

        buildUI(title, body);
    }

    private void buildUI(String title, String body) {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(80, 160, 80, 80);
        root.setBackgroundColor(Color.parseColor("#DC2626"));

        TextView icon = new TextView(this);
        icon.setText("\u26A0\uFE0F");
        icon.setTextSize(60);
        icon.setGravity(Gravity.CENTER);
        root.addView(icon);

        NotificationStrings ns = new NotificationStrings(this);

        TextView titleView = new TextView(this);
        titleView.setText(title);
        titleView.setTextColor(Color.WHITE);
        titleView.setTextSize(26);
        titleView.setGravity(Gravity.CENTER);
        titleView.setPadding(0, 30, 0, 10);
        root.addView(titleView);

        TextView bodyView = new TextView(this);
        bodyView.setText(body);
        bodyView.setTextColor(Color.parseColor("#FCA5A5"));
        bodyView.setTextSize(18);
        bodyView.setGravity(Gravity.CENTER);
        bodyView.setPadding(0, 20, 0, 40);
        root.addView(bodyView);

        Button okBtn = new Button(this);
        okBtn.setText(ns.close());
        okBtn.setTextSize(20);
        okBtn.setBackgroundColor(Color.WHITE);
        okBtn.setTextColor(Color.parseColor("#DC2626"));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 160);
        lp.setMargins(0, 0, 0, 10);
        okBtn.setLayoutParams(lp);
        okBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                finish();
            }
        });
        root.addView(okBtn);

        scrollView.addView(root);
        setContentView(scrollView);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
    }
}
