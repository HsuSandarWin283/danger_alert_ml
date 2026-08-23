"""
COLAB TRAINING SCRIPT FOR BINARY DANGER GATE
Run this in Google Colab (CPU or GPU).
"""

# 1. Check environment
import torch
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
else:
    print("WARNING: GPU is NOT available - training will use CPU")

# 2. Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# 3. Copy project to Colab workspace
!cp -r "/content/drive/MyDrive/danger_alert_ml/" "/content/danger_alert_ml/"

# 4. Install dependencies
!apt-get update -qq
!apt-get install -y ffmpeg

!pip install -q librosa>=0.10.0 numpy>=1.24.0 scikit-learn>=1.3.0 matplotlib pandas scipy

# 5. Verify dataset
from pathlib import Path
DATASET_DIR = Path("/content/danger_alert_ml/app/dataset")
for folder in ["Gunshot", "Scream", "Accident"]:
    files = list((DATASET_DIR / folder).rglob("*"))
    audio_files = [f for f in files if f.suffix.lower() in [".wav", ".mp3", ".m4a", ".flac", ".ogg"]]
    print(folder, len(audio_files))

ESC50_DIR = Path("/content/danger_alert_ml/app/database/ESC-50-master")
print("ESC-50 exists:", ESC50_DIR.exists())

# 6. Train binary gate
%cd /content/danger_alert_ml/app/ml
!python train_binary_gate.py

# 7. Download trained model back to Drive
from google.colab import files
import os, shutil

OUTPUT_DIR = Path("/content/danger_alert_ml/app/ml")
DRIVE_DIR = Path("/content/drive/MyDrive/danger_alert_ml/app/ml")

DRIVE_DIR.mkdir(parents=True, exist_ok=True)

for fname in ["danger_gate_model.pth", "gate_classes.pkl", "gate_scaler_info.pkl", "gate_thresholds.json", "gate_training_report.txt"]:
    src = OUTPUT_DIR / fname
    dst = DRIVE_DIR / fname
    if src.exists():
        shutil.copy2(src, dst)
        print(f"Copied {fname} to Drive")
    else:
        print(f"NOT FOUND: {fname}")

# 8. Also download locally for immediate use
for fname in ["danger_gate_model.pth", "gate_classes.pkl", "gate_scaler_info.pkl", "gate_thresholds.json"]:
    src = OUTPUT_DIR / fname
    if src.exists():
        files.download(str(src))
    else:
        print("NOT FOUND for download:", fname)
