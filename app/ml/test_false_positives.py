from __future__ import annotations

import os
import pickle
import random
import time
from pathlib import Path

import librosa
import numpy as np
import torch

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"

SAMPLE_RATE = 22050
DURATION = 3.0
N_MELS = 128
N_FFT = 2048
HOP_LENGTH = 512
IMG_HEIGHT = 128
IMG_WIDTH = 128
TARGET_LENGTH = int(SAMPLE_RATE * DURATION)

MODEL_PATH = ML_DIR / "danger_sound_cnn_model.pth"
CLASSES_PATH = ML_DIR / "cnn_classes.pkl"
SCALER_PATH = ML_DIR / "cnn_scaler_info.pkl"

BG_CATEGORIES = [
    "rain", "wind", "engine", "thunderstorm", "sea_waves",
    "train", "helicopter", "airplane", "insects", "crickets",
    "chirping_birds", "vacuum_cleaner", "washing_machine",
    "crow", "dog", "cat", "footsteps", "clock_tick",
]

DANGER_EXCLUDED_CATEGORIES = {
    "gunshot", "siren", "chainsaw", "fireworks", "crying_baby",
    "glass_breaking", "car_horn",
}

NORMAL_TEST_COUNT = 100


def load_audio(path: Path):
    signal, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True, duration=DURATION, res_type="soxr_hq")
    if len(signal) < TARGET_LENGTH:
        signal = np.pad(signal, (0, TARGET_LENGTH - len(signal)))
    else:
        signal = signal[:TARGET_LENGTH]
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak * 0.95
    return signal


def audio_to_mel(signal: np.ndarray) -> np.ndarray:
    mel = librosa.feature.melspectrogram(
        y=signal, sr=SAMPLE_RATE, n_mels=N_MELS,
        n_fft=N_FFT, hop_length=HOP_LENGTH,
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    mel_db = np.clip(mel_db, -80.0, 0.0)
    from scipy.ndimage import zoom
    zh = IMG_HEIGHT / mel_db.shape[0]
    zw = IMG_WIDTH / mel_db.shape[1]
    resized = zoom(mel_db, (zh, zw), order=1)
    return resized[:IMG_HEIGHT, :IMG_WIDTH].astype(np.float32)


class DangerSoundCNN(torch.nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.features = torch.nn.Sequential(
            torch.nn.Conv2d(1, 32, 3, padding=1), torch.nn.BatchNorm2d(32), torch.nn.ReLU(inplace=True),
            torch.nn.Conv2d(32, 32, 3, padding=1), torch.nn.BatchNorm2d(32), torch.nn.ReLU(inplace=True),
            torch.nn.MaxPool2d(2), torch.nn.Dropout2d(0.1),
            torch.nn.Conv2d(32, 64, 3, padding=1), torch.nn.BatchNorm2d(64), torch.nn.ReLU(inplace=True),
            torch.nn.Conv2d(64, 64, 3, padding=1), torch.nn.BatchNorm2d(64), torch.nn.ReLU(inplace=True),
            torch.nn.MaxPool2d(2), torch.nn.Dropout2d(0.15),
            torch.nn.Conv2d(64, 128, 3, padding=1), torch.nn.BatchNorm2d(128), torch.nn.ReLU(inplace=True),
            torch.nn.Conv2d(128, 128, 3, padding=1), torch.nn.BatchNorm2d(128), torch.nn.ReLU(inplace=True),
            torch.nn.MaxPool2d(2), torch.nn.Dropout2d(0.2),
            torch.nn.Conv2d(128, 256, 3, padding=1), torch.nn.BatchNorm2d(256), torch.nn.ReLU(inplace=True),
            torch.nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = torch.nn.Sequential(
            torch.nn.Linear(256, 256), torch.nn.ReLU(inplace=True), torch.nn.Dropout(0.5),
            torch.nn.Linear(256, 128), torch.nn.ReLU(inplace=True), torch.nn.Dropout(0.3),
            torch.nn.Linear(128, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)


def main():
    print("=" * 60)
    print("FALSE POSITIVE DIAGNOSTIC TEST")
    print("=" * 60)

    # Load model
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    classes = checkpoint["classes"]
    num_classes = len(classes)
    scaler_info = checkpoint["scaler_info"]

    model = DangerSoundCNN(num_classes)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    print(f"Model loaded: {num_classes} classes, {classes}")
    print(f"Scaler: mean={scaler_info['mean']:.4f}, std={scaler_info['std']:.4f}")

    # Load ESC-50 metadata
    by_cat = {}
    with META_FILE.open("r", encoding="utf-8", newline="") as f:
        import csv
        reader = csv.DictReader(f)
        for row in reader:
            by_cat.setdefault(row["category"], []).append(row["filename"])

    # Select normal files
    normal_files = []
    for cat, files in by_cat.items():
        if cat not in DANGER_EXCLUDED_CATEGORIES and cat not in BG_CATEGORIES:
            for fname in files:
                normal_files.append((AUDIO_DIR / fname, cat))
    random.shuffle(normal_files)
    normal_files = normal_files[:NORMAL_TEST_COUNT]

    print(f"\nTesting {len(normal_files)} normal ESC-50 files...")

    results = []
    for path, cat in normal_files:
        try:
            signal = load_audio(path)
            mel = audio_to_mel(signal)
            mel_norm = (mel - scaler_info["mean"]) / scaler_info["std"]
            mel_tensor = torch.tensor(mel_norm, dtype=torch.float32).unsqueeze(0).unsqueeze(0)

            with torch.no_grad():
                logits = model(mel_tensor)
                probs = torch.nn.functional.softmax(logits, dim=1).cpu().numpy()[0]

            pred_idx = int(np.argmax(probs))
            pred_class = classes[pred_idx]
            confidence = float(probs[pred_idx])

            prob_dict = {cls: float(probs[i]) for i, cls in enumerate(classes)}

            results.append({
                "file": path.name,
                "category": cat,
                "prediction": pred_class,
                "confidence": confidence,
                "probabilities": prob_dict,
                "is_false_positive": pred_class != "normal",
            })

            status = "FP" if pred_class != "normal" else "OK"
            print(f"[{status}] {path.name:40s} pred={pred_class:10s} conf={confidence:.4f} "
                  f"acc={prob_dict.get('accident',0):.4f} gun={prob_dict.get('gunshot',0):.4f} "
                  f"norm={prob_dict.get('normal',0):.4f} scr={prob_dict.get('scream',0):.4f}")
        except Exception as e:
            print(f"[ERR] {path.name}: {e}")

    # Summary
    total = len(results)
    false_positives = sum(1 for r in results if r["is_false_positive"])
    fp_rate = false_positives / total if total > 0 else 0

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total normal files tested: {total}")
    print(f"Correctly predicted normal: {total - false_positives}")
    print(f"False positives (danger predicted): {false_positives}")
    print(f"False Positive Rate: {fp_rate:.2%}")

    # Breakdown by predicted class
    fp_by_class = {}
    for r in results:
        if r["is_false_positive"]:
            fp_by_class[r["prediction"]] = fp_by_class.get(r["prediction"], 0) + 1
    print(f"False positive breakdown: {fp_by_class}")

    # Show worst offenders
    print("\nTop 10 highest-confidence false positives:")
    fps = [r for r in results if r["is_false_positive"]]
    fps.sort(key=lambda x: x["confidence"], reverse=True)
    for r in fps[:10]:
        print(f"  {r['file']:40s} pred={r['prediction']:10s} conf={r['confidence']:.4f} "
              f"norm={r['probabilities'].get('normal',0):.4f}")

    # Save results
    import json
    output_path = ML_DIR / "false_positive_report.json"
    with open(output_path, "w") as f:
        json.dump({
            "total_tested": total,
            "false_positives": false_positives,
            "fp_rate": fp_rate,
            "results": results,
        }, f, indent=2)
    print(f"\nDetailed results saved: {output_path}")


if __name__ == "__main__":
    main()
