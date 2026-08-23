from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mel_cache import (
    SAMPLE_RATE,
    DURATION,
    N_MELS,
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
from train_danger_classifier import DangerSoundCNN, evaluate_model

_FFMPEG_DIR = Path(r"C:\Users\Hsu Sandar Win\AppData\Local\Python\ffmpeg\ffmpeg-9.0-essentials_build\bin")
if _FFMPEG_DIR.exists():
    os.environ["PATH"] = str(_FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
CUSTOM_DATASET_DIR = APP_DIR / "dataset"
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

MODEL_PATH = ML_DIR / "danger_sound_cnn_model.pth"
CLASSES_PATH = ML_DIR / "cnn_classes.pkl"
SCALER_PATH = ML_DIR / "cnn_scaler_info.pkl"
THRESHOLD_JSON = ML_DIR / "classifier_thresholds.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def load_model_and_scaler():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    if not SCALER_PATH.exists():
        raise FileNotFoundError(f"Scaler not found: {SCALER_PATH}")

    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    state_dict = checkpoint["model_state_dict"]
    classes = checkpoint.get("classes", ["accident", "gunshot", "scream"])
    scaler = checkpoint.get("scaler_info", None)

    if scaler is None and SCALER_PATH.exists():
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)

    model = DangerSoundCNN(len(classes))
    model.load_state_dict(state_dict)
    model.eval()

    return model, classes, scaler


def predict(model, mel: np.ndarray, scaler: dict, classes: list[str]) -> tuple[int, np.ndarray]:
    mel_norm = normalize_mel(mel, scaler)
    mel_input = mel_norm.reshape(1, 1, IMG_HEIGHT, IMG_WIDTH)
    mel_tensor = torch.tensor(mel_input, dtype=torch.float32)

    with torch.no_grad():
        logits = model(mel_tensor)
        probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        pred = int(np.argmax(probs))

    return pred, probs


def load_custom_paths(folder: str, max_count: int | None = None) -> list[Path]:
    folder = CUSTOM_DATASET_DIR / folder
    if not folder.exists():
        return []
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
    if max_count is not None and len(files) > max_count:
        random.shuffle(files)
        files = files[:max_count]
    return files


def build_evaluation_sets():
    results = {}

    gunshot_files = load_custom_paths("Gunshot", 50)
    scream_files = load_custom_paths("Scream", 50)
    accident_files = load_custom_paths("Accident", 50)

    results["clean_gunshot"] = {"files": gunshot_files, "label": "gunshot", "name": "Clean Gunshot"}
    results["clean_scream"] = {"files": scream_files, "label": "scream", "name": "Clean Scream"}
    results["clean_accident"] = {"files": accident_files, "label": "accident", "name": "Clean Accident"}

    low_vol_gunshot = []
    for p in gunshot_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            low_sig = _apply_gain(sig, gain_range=(0.05, 0.2))
            low_vol_gunshot.append(low_sig)
    results["low_volume_gunshot"] = {"signals": low_vol_gunshot, "label": "gunshot", "name": "Low-Volume Gunshot"}

    low_vol_scream = []
    for p in scream_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            low_sig = _apply_gain(sig, gain_range=(0.05, 0.2))
            low_vol_scream.append(low_sig)
    results["low_volume_scream"] = {"signals": low_vol_scream, "label": "scream", "name": "Low-Volume Scream"}

    low_vol_accident = []
    for p in accident_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            low_sig = _apply_gain(sig, gain_range=(0.05, 0.2))
            low_vol_accident.append(low_sig)
    results["low_volume_accident"] = {"signals": low_vol_accident, "label": "accident", "name": "Low-Volume Accident"}

    noisy_gunshot = []
    for p in gunshot_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            noisy_sig = _mix_noise(sig, snr_db_range=(3.0, 15.0))
            noisy_gunshot.append(noisy_sig)
    results["noisy_gunshot"] = {"signals": noisy_gunshot, "label": "gunshot", "name": "Noisy Gunshot"}

    noisy_scream = []
    for p in scream_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            noisy_sig = _mix_noise(sig, snr_db_range=(3.0, 15.0))
            noisy_scream.append(noisy_sig)
    results["noisy_scream"] = {"signals": noisy_scream, "label": "scream", "name": "Noisy Scream"}

    noisy_accident = []
    for p in accident_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            noisy_sig = _mix_noise(sig, snr_db_range=(3.0, 15.0))
            noisy_accident.append(noisy_sig)
    results["noisy_accident"] = {"signals": noisy_accident, "label": "accident", "name": "Noisy Accident"}

    phone_gunshot = []
    for p in gunshot_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            phone_sig = augment_signal(sig, p=1.0)
            phone_gunshot.append(phone_sig)
    results["phone_gunshot"] = {"signals": phone_gunshot, "label": "gunshot", "name": "Phone-Augmented Gunshot"}

    phone_scream = []
    for p in scream_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            phone_sig = augment_signal(sig, p=1.0)
            phone_scream.append(phone_sig)
    results["phone_scream"] = {"signals": phone_scream, "label": "scream", "name": "Phone-Augmented Scream"}

    phone_accident = []
    for p in accident_files[:30]:
        sig = _load_raw(p)
        if sig is not None:
            phone_sig = augment_signal(sig, p=1.0)
            phone_accident.append(phone_sig)
    results["phone_accident"] = {"signals": phone_accident, "label": "accident", "name": "Phone-Augmented Accident"}

    return results


def evaluate_dataset(model, scaler, classes, mels: list[np.ndarray], labels: list[str], name: str) -> dict:
    if not mels:
        return {"name": name, "accuracy": 0.0, "samples": 0}

    class_to_idx = {c: i for i, c in enumerate(classes)}
    y_true = []
    y_pred = []
    all_probs = []

    for sig, lbl in zip(mels, labels):
        mel = _compute_mel(sig)
        pred, probs = predict(model, mel, scaler, classes)
        y_pred.append(pred)
        y_true.append(class_to_idx[lbl])
        all_probs.append(probs)

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    all_probs = np.array(all_probs)

    accuracy = np.mean(y_pred == y_true)
    precision = precision_score(y_true, y_pred, average="macro", zero_division=0)
    recall = recall_score(y_true, y_pred, average="macro", zero_division=0)
    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(classes))))
    report = classification_report(y_true, y_pred, target_names=classes, digits=4, zero_division=0)

    per_class = {}
    for i, cls in enumerate(classes):
        mask_i = y_true == i
        total_i = int(np.sum(mask_i))
        correct_i = int(np.sum((y_true == i) & (y_pred == i)))
        recall_i = correct_i / total_i if total_i > 0 else 0

        pred_mask_i = y_pred == i
        tp = int(np.sum((y_true == i) & (y_pred == i)))
        fp = int(np.sum((y_true != i) & (y_pred == i)))
        precision_i = tp / (tp + fp) if (tp + fp) > 0 else 0
        f1_i = 2 * precision_i * recall_i / (precision_i + recall_i) if (precision_i + recall_i) > 0 else 0

        per_class[cls] = {
            "precision": precision_i,
            "recall": recall_i,
            "f1": f1_i,
            "support": total_i,
        }

    return {
        "name": name,
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "samples": int(len(y_true)),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "report": report,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate 3-class classifier on clean and phone-like conditions")
    parser.add_argument("--output", type=str, default=str(ML_DIR / "classifier_evaluation_report.json"), help="Output JSON path")
    args = parser.parse_args()

    log("Loading model and scaler...")
    model, classes, scaler = load_model_and_scaler()
    log(f"Model loaded. Classes: {classes}")

    eval_sets = build_evaluation_sets()
    all_reports = []

    for key, info in eval_sets.items():
        if "files" in info:
            signals = []
            labels = []
            for p in info["files"]:
                sig = _load_raw(p)
                if sig is not None:
                    signals.append(sig)
                    labels.append(info["label"])
            if not signals:
                log(f"Skipping {key}: no valid files")
                continue
        elif "signals" in info:
            signals = info["signals"]
            labels = [info["label"]] * len(signals)
        else:
            continue

        report = evaluate_dataset(model, scaler, classes, signals, labels, info["name"])
        all_reports.append(report)

        log(f"\n=== {report['name']} ===")
        log(f"  Accuracy:  {report['accuracy']:.4f}")
        log(f"  Precision: {report['precision']:.4f}")
        log(f"  Recall:    {report['recall']:.4f}")
        log(f"  F1:        {report['f1']:.4f}")
        log(f"  Samples:   {report['samples']}")
        for cls, metrics in report["per_class"].items():
            log(f"  {cls}: precision={metrics['precision']:.4f} recall={metrics['recall']:.4f} f1={metrics['f1']:.4f} support={metrics['support']}")
        log(f"  Confusion Matrix:")
        for i, row in enumerate(report["confusion_matrix"]):
            log(f"    {classes[i]}: {row}")

    summary = {
        "classes": classes,
        "evaluations": all_reports,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log(f"\nReport saved: {args.output}")

    log("\n" + "=" * 60)
    log("CLASSIFIER EVALUATION SUMMARY")
    log("=" * 60)
    for r in all_reports:
        log(f"\n{r['name']}: acc={r['accuracy']:.4f} f1={r['f1']:.4f} n={r['samples']}")


if __name__ == "__main__":
    main()
