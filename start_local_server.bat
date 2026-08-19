@echo off
echo Starting Danger Alert ML Server...
echo.
echo Server will run at: http://localhost:8000
echo.
echo To use from APK:
echo 1. Find your local IP: ipconfig
echo 2. Update DEFAULT_PREDICT_URL in useDangerSoundMonitor.ts
echo 3. Make sure phone and PC are on same WiFi
echo.
python server_hf.py
pause
