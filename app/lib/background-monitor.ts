import { registerPlugin, PluginListenerHandle } from '@capacitor/core';

export interface BackgroundMonitorPlugin {
  startMonitoring(options: { apiUrl: string }): Promise<{ running: boolean }>;
  stopMonitoring(): Promise<{ running: boolean }>;
  isRunning(): Promise<{ running: boolean }>;
  saveFirebaseConfig(options: { apiKey: string; projectId: string; userId: string; authToken: string; phone: string; fcmToken: string; serverKey: string; clientEmail: string; privateKey: string; displayName: string }): Promise<{ saved: boolean }>;
  saveTrustedMembers(options: { members: string }): Promise<{ saved: boolean }>;
  sendTrustedAlert(options: { dangerType: string; confidence: number; alertMsg: string; members: string }): Promise<{ sent: number; total: number }>;
  sendEmergencyAlert(options: { dangerType: string; confidence: number; alertMsg: string }): Promise<{ sent: number; total: number }>;
  fetchFcmToken(options: { userId: string }): Promise<{ fcmToken: string }>;
  setLanguage(options: { lang: string }): Promise<{ saved: boolean }>;
  getPendingNavigate(): Promise<{ route: string }>;
  addListener(eventName: 'monitoringStateChanged', listenerFunc: (data: { running: boolean }) => void): Promise<PluginListenerHandle>;
}

const BackgroundMonitor = registerPlugin<BackgroundMonitorPlugin>('BackgroundMonitor');

export default BackgroundMonitor;
