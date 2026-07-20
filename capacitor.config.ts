import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.danger.alert',
  appName: 'Danger Alert',
  webDir: 'out',
  server: {
    androidScheme: 'http',
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: false,
      backgroundColor: '#1a1a2e',
      showSpinner: false,
    },
  },
};

export default config;
