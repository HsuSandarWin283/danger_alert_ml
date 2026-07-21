import { registerPlugin } from '@capacitor/core';

export interface BackgroundMonitorPlugin {
  startMonitoring(options: { apiUrl: string }): Promise<{ running: boolean }>;
  stopMonitoring(): Promise<{ running: boolean }>;
  isRunning(): Promise<{ running: boolean }>;
}

const BackgroundMonitor = registerPlugin<BackgroundMonitorPlugin>('BackgroundMonitor');

export default BackgroundMonitor;
