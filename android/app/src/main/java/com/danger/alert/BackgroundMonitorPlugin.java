package com.danger.alert;

import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "BackgroundMonitor")
public class BackgroundMonitorPlugin extends Plugin {

    @PluginMethod
    public void startMonitoring(PluginCall call) {
        String apiUrl = call.getString("apiUrl", "https://danger-alert-ml.onrender.com");

        Intent intent = new Intent(getContext(), MonitoringService.class);
        intent.setAction(MonitoringService.ACTION_START);
        intent.putExtra(MonitoringService.EXTRA_API_URL, apiUrl);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                getContext().startForegroundService(intent);
            } else {
                getContext().startForegroundService(intent);
            }
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
    public void isRunning(PluginCall call) {
        JSObject result = new JSObject();
        result.put("running", true);
        call.resolve(result);
    }
}
