from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
import librosa
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mel_cache import (
    SAMPLE_RATE,
    DURATION,
    N_MELS,
    N_FFT,
    HOP_LENGTH,
    IMG_HEIGHT,
    IMG_WIDTH,
    compute_normalization,
    normalize_mel,
    _compute_mel,
)
from phone_augment import (
    _load_raw,
    augment_signal,
    _apply_gain,
    _mix_noise,
)
from train_binary_gate import BinaryDangerGate, evaluate_binary_gate

_FFMPEG_DIR = Path(r"C:\Users\Hsu Sandar Win\AppData\Local\Python\ffmpeg\ffmpeg-9.0-essentials_build\bin")
if _FFMPEG_DIR.exists():
    os.environ["PATH"] = str(_FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
CUSTOM_DATASET_DIR = APP_DIR / "dataset"
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

MODEL_PATH = ML_DIR / "danger_gate_model.pth"
CLASSES_PATH = ML_DIR / "gate_classes.pkl"
SCALER_PATH = ML_DIR / "gate_scaler_info.pkl"
THRESHOLD_JSON = ML_DIR / "gate_thresholds.json"
DEBUG_DIR = ML_DIR / "debug_audio"


def log(msg: str) -> None:
    print(msg, flush=True)


def load_model_and_scaler():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    if not SCALER_PATH.exists():
        raise FileNotFoundError(f"Scaler not found: {SCALER_PATH}")

    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    state_dict = checkpoint["model_state_dict"]
    classes = checkpoint.get("classes", ["non_danger", "danger"])
    scaler = checkpoint.get("scaler_info", None)
    threshold = checkpoint.get("best_threshold", 0.5)

    if scaler is None and SCALER_PATH.exists():
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)

    if threshold == 0.5 and THRESHOLD_JSON.exists():
        try:
            with open(THRESHOLD_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            threshold = data.get("best_threshold", 0.5)
        except Exception:
            pass

    model = BinaryDangerGate()
    model.load_state_dict(state_dict)
    model.eval()

    return model, classes, scaler, threshold


def predict_gate(model, mel: np.ndarray, scaler: dict, threshold: float) -> tuple[float, int]:
    mel_norm = normalize_mel(mel, scaler)
    mel_input = mel_norm.reshape(1, 1, IMG_HEIGHT, IMG_WIDTH)
    mel_tensor = torch.tensor(mel_input, dtype=torch.float32)

    with torch.no_grad():
        logits = model(mel_tensor)
        prob = float(torch.sigmoid(logits).cpu().numpy()[0])

    pred = 1 if prob >= threshold else 0
    return prob, pred


def evaluate_dataset(model, scaler, threshold, mels: np.ndarray, labels: np.ndarray, name: str) -> dict:
    probs = []
    preds = []
    for mel in mels:
        p, pred = predict_gate(model, mel, scaler, threshold)
        probs.append(p)
        preds.append(pred)

    probs = np.array(probs)
    preds = np.array(preds)
    labels = np.array(labels)

    accuracy = np.mean(preds == labels)
    precision = precision_score(labels, preds, zero_division=0)
    recall = recall_score(labels, preds, zero_division=0)
    f1 = f1_score(labels, preds, zero_division=0)
    danger_recall = recall_score(labels, preds, pos_label=1, zero_division=0)
    non_danger_recall = recall_score(labels, preds, pos_label=0, zero_division=0)
    non_danger_fp_rate = np.sum((labels == 0) & (preds == 1)) / max(np.sum(labels == 0), 1)
    fnr = np.sum((labels == 1) & (preds == 0)) / max(np.sum(labels == 1), 1)

    try:
        auc = roc_auc_score(labels, probs)
    except ValueError:
        auc = 0.0

    report = classification_report(labels, preds, target_names=["non_danger", "danger"], digits=4, zero_division=0)
    cm = confusion_matrix(labels, preds)

    log(f"\n=== {name} ===")
    log(f"  Accuracy:  {accuracy:.4f}")
    log(f"  Precision: {precision:.4f}")
    log(f"  Recall:    {recall:.4f}")
    log(f"  F1:        {f1:.4f}")
    log(f"  Danger recall:    {danger_recall:.4f}")
    log(f"  Non-danger recall: {non_danger_recall:.4f}")
    log(f"  Non-danger FPR:   {non_danger_fp_rate:.4f}")
    log(f"  Danger FNR:       {fnr:.4f}")
    log(f"  AUC:      {auc:.4f}")
    log(f"  Confusion Matrix:")
    log(f"    non_danger: {cm[0].tolist()}")
    log(f"    danger:     {cm[1].tolist()}")
    log(f"  Classification Report:")
    log(report)

    return {
        "name": name,
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "danger_recall": float(danger_recall),
        "non_danger_recall": float(non_danger_recall),
        "non_danger_fp_rate": float(non_danger_fp_rate),
        "danger_fnr": float(fnr),
        "auc": float(auc),
        "confusion_matrix": cm.tolist(),
        "report": report,
        "mean_prob_danger": float(np.mean(probs[labels == 1])) if np.any(labels == 1) else 0.0,
        "mean_prob_non_danger": float(np.mean(probs[labels == 0])) if np.any(labels == 0) else 0.0,
    }


def load_esc50_paths() -> list[Path]:
    paths = []
    if not META_FILE.exists():
        return paths
    with META_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            audio_path = AUDIO_DIR / row["filename"]
            if audio_path.exists():
                paths.append(audio_path)
    return paths


def load_custom_paths(folder: str) -> list[Path]:
    folder = CUSTOM_DATASET_DIR / folder
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)


def build_evaluation_set():
    results = {}

    danger_files = load_custom_paths("Gunshot") + load_custom_paths("Scream") + load_custom_paths("Accident")
    non_danger_files = load_esc50_paths()

    phone_danger = []
    phone_non_danger = []
    debug_audio_dir = DEBUG_DIR
    if debug_audio_dir.exists():
        for f in debug_audio_dir.glob("*.wav"):
            phone_non_danger.append(f)
        for f in debug_audio_dir.glob("monitoring-*.wav"):
            phone_non_danger.append(f)

    results["clean_danger"] = {
        "files": danger_files[:50],
        "label": 1,
        "name": "Clean Danger WAV",
    }
    results["clean_non_danger"] = {
        "files": non_danger_files[:100],
        "label": 0,
        "name": "Clean Non-Danger WAV (ESC-50)",
    }

    low_vol_danger = []
    for p in danger_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            low_sig = _apply_gain(sig, gain_range=(0.05, 0.2))
            low_vol_danger.append(low_sig)
    results["low_volume_danger"] = {
        "signals": low_vol_danger,
        "label": 1,
        "name": "Low-Volume Danger (simulated phone mic)",
    }

    noisy_danger = []
    for p in danger_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            noisy_sig = _mix_noise(sig, snr_db_range=(3.0, 15.0))
            noisy_danger.append(noisy_sig)
    results["noisy_danger"] = {
        "signals": noisy_danger,
        "label": 1,
        "name": "Noisy Danger (simulated phone mic)",
    }

    phone_danger_signals = []
    for p in danger_files[:20]:
        sig = _load_raw(p)
        if sig is not None:
            phone_sig = augment_signal(sig, p=1.0)
            phone_danger_signals.append(phone_sig)
    results["phone_aug_danger"] = {
        "signals": phone_danger_signals,
        "label": 1,
        "name": "Phone-Augmented Danger",
    }

    phone_non_danger_signals = []
    for p in non_danger_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            phone_sig = augment_signal(sig, p=0.8)
            phone_non_danger_signals.append(phone_sig)
    results["phone_aug_non_danger"] = {
        "signals": phone_non_danger_signals,
        "label": 0,
        "name": "Phone-Augmented Non-Danger",
    }

    phone_mic_signals = []
    phone_mic_labels = []
    for p in phone_danger[:10]:
        sig = _load_raw(p)
        if sig is not None:
            phone_mic_signals.append(sig)
            phone_mic_labels.append(1)
    for p in phone_non_danger[:20]:
        sig = _load_raw(p)
        if sig is not None:
            phone_mic_signals.append(sig)
            phone_mic_labels.append(0)
    results["phone_mic_real"] = {
        "signals": phone_mic_signals,
        "labels": phone_mic_labels,
        "name": "Phone-Mic Real Recordings",
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate binary gate on phone-realistic conditions")
    parser.add_argument("--output", type=str, default=str(ML_DIR / "gate_evaluation_report.json"), help="Output JSON path")
    args = parser.parse_args()

    log("Loading model and scaler...")
    model, classes, scaler, threshold = load_model_and_scaler()
    log(f"Model loaded. Threshold: {threshold:.2f}")

    eval_sets = build_evaluation_set()
    all_reports = []

    for key, info in eval_sets.items():
        if "files" in info:
            mels = []
            labels = []
            for p in info["files"]:
                sig = _load_raw(p)
                if sig is not None:
                    mel = _compute_mel(sig)
                    mels.append(mel)
                    labels.append(info["label"])
            if not mels:
                log(f"Skipping {key}: no valid files")
                continue
            mels = np.array(mels, dtype=np.float32)
            labels = np.array(labels, dtype=np.int64)
        elif "signals" in info and "labels" in info:
            mels = []
            for sig in info["signals"]:
                mel = _compute_mel(sig)
                mels.append(mel)
            mels = np.array(mels, dtype=np.float32)
            labels = np.array(info["labels"], dtype=np.int64)
        elif "signals" in info:
            mels = []
            for sig in info["signals"]:
                mel = _compute_mel(sig)
                mels.append(mel)
            mels = np.array(mels, dtype=np.float32)
            labels = np.full(len(mels), info["label"], dtype=np.int64)
        else:
            continue

        report = evaluate_dataset(model, scaler, threshold, mels, labels, info["name"])
        all_reports.append(report)

    summary = {
        "threshold": float(threshold),
        "evaluations": all_reports,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log(f"\nReport saved: {args.output}")

    log("\n" + "=" * 60)
    log("GATE EVALUATION SUMMARY")
    log("=" * 60)
    for r in all_reports:
        log(f"\n{r['name']}:")
        log(f"  Danger recall: {r['danger_recall']:.4f}")
        log(f"  Non-danger specificity: {r['non_danger_recall']:.4f}")
        log(f"  FPR: {r['non_danger_fp_rate']:.4f}")
        log(f"  FNR: {r['danger_fnr']:.4f}")
        log(f"  Threshold: {threshold:.2f}")


if __name__ == "__main__":
    main()
