from __future__ import annotations

import argparse
import csv
import json
import os
import pickle
import random
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader, Dataset, TensorDataset

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

_FFMPEG_DIR = Path(r"C:\Users\Hsu Sandar Win\AppData\Local\Python\ffmpeg\ffmpeg-9.0-essentials_build\bin")
if _FFMPEG_DIR.exists():
    os.environ["PATH"] = str(_FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

_IN_COLAB = False
try:
    import google.colab
    _IN_COLAB = True
except ImportError:
    pass

if _IN_COLAB:
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[2]
    APP_DIR = project_root / 'app'
    ML_DIR = APP_DIR / 'ml'
    CUSTOM_DATASET_DIR = APP_DIR / 'dataset'
    ESC50_DIR = APP_DIR / 'database' / 'ESC-50-master'
else:
    APP_DIR = Path(__file__).resolve().parents[1]
    ML_DIR = Path(__file__).resolve().parent
    CUSTOM_DATASET_DIR = APP_DIR / "dataset"
    ESC50_DIR = APP_DIR / "database" / "ESC-50-master"

META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

GUNSHOT_SAMPLE_COUNT = 300
SCREAM_SAMPLE_COUNT = 210
ACCIDENT_SAMPLE_COUNT = 200
GUNSHOT_AUG_PER_ORIGINAL = 5
AUG_PER_ORIGINAL = 3

random.seed(42)
np.random.seed(42)
torch.manual_seed(42)


def log(msg: str, lines: list[str] | None = None) -> None:
    print(msg, flush=True)
    if lines is not None:
        lines.append(msg)


def load_esc50_by_category() -> dict[str, list[Path]]:
    by_cat: dict[str, list[Path]] = {}
    if not META_FILE.exists():
        raise FileNotFoundError(f"ESC-50 metadata not found: {META_FILE}")
    with META_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            audio_path = AUDIO_DIR / row["filename"]
            if audio_path.exists():
                by_cat.setdefault(row["category"], []).append(audio_path)
    return by_cat


def collect_custom_files(folder_name: str, max_count: int | None = None) -> list[Path]:
    folder = CUSTOM_DATASET_DIR / folder_name
    if not folder.exists():
        return []
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
    if max_count is not None and len(files) > max_count:
        random.shuffle(files)
        files = files[:max_count]
    return files


class CachedMelDataset(Dataset):
    def __init__(self, mels: np.ndarray, labels: np.ndarray, augment: bool = False):
        self.mels = mels.astype(np.float32)
        self.labels = labels.astype(np.int64)
        self.augment = augment

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        mel = self.mels[idx].copy()
        label = int(self.labels[idx])

        if self.augment:
            if random.random() < 0.3:
                mel = mel * random.uniform(0.85, 1.15)
            if random.random() < 0.2:
                freq_mask_width = random.randint(1, 8)
                f0 = random.randint(0, max(0, N_MELS - freq_mask_width))
                mel[f0:f0 + freq_mask_width, :] = 0.0

        mel_tensor = torch.tensor(mel, dtype=torch.float32).unsqueeze(0)
        return mel_tensor, torch.tensor(label, dtype=torch.long)


class DangerSoundCNN(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.1),

            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.15),

            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.2),

            nn.Conv2d(128, 256, 3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)


def evaluate_model(model, dataloader, device, classes):
    model.eval()
    all_preds = []
    all_true = []
    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    criterion = nn.CrossEntropyLoss()

    with torch.no_grad():
        for bx, by in dataloader:
            bx, by = bx.to(device), by.to(device)
            out = model(bx)
            loss = criterion(out, by)
            total_loss += loss.item() * bx.size(0)
            preds = out.argmax(1)
            total_correct += preds.eq(by).sum().item()
            total_samples += bx.size(0)
            all_preds.extend(preds.cpu().numpy())
            all_true.extend(by.cpu().numpy())

    avg_loss = total_loss / total_samples if total_samples > 0 else 0.0
    accuracy = total_correct / total_samples if total_samples > 0 else 0.0

    report = classification_report(
        all_true, all_preds, target_names=classes, digits=4, zero_division=0,
    )
    cm = confusion_matrix(all_true, all_preds)

    per_class = {}
    for i, cls in enumerate(classes):
        mask_i = np.array(all_true) == i
        total_i = int(np.sum(mask_i))
        correct_i = int(np.sum((np.array(all_true) == i) & (np.array(all_preds) == i)))
        recall_i = correct_i / total_i if total_i > 0 else 0

        pred_mask_i = np.array(all_preds) == i
        tp = int(np.sum((np.array(all_true) == i) & (np.array(all_preds) == i)))
        fp = int(np.sum((np.array(all_true) != i) & (np.array(all_preds) == i)))
        precision_i = tp / (tp + fp) if (tp + fp) > 0 else 0
        f1_i = 2 * precision_i * recall_i / (precision_i + recall_i) if (precision_i + recall_i) > 0 else 0

        per_class[cls] = {
            "precision": precision_i,
            "recall": recall_i,
            "f1": f1_i,
            "support": total_i,
        }

    return {
        "loss": avg_loss,
        "accuracy": accuracy,
        "report": report,
        "confusion_matrix": cm,
        "per_class": per_class,
        "predictions": np.array(all_preds),
        "true": np.array(all_true),
    }


def find_best_thresholds(probs, true, classes):
    best_macro_f1 = 0
    best_conf = 0.5
    best_margin = 0.0
    best_metrics = None

    sorted_probs = np.sort(probs, axis=1)[:, ::-1]
    margins = sorted_probs[:, 0] - sorted_probs[:, 1]

    for conf in np.arange(0.4, 0.95, 0.05):
        for margin in np.arange(0.0, 0.5, 0.05):
            preds = []
            for i in range(len(true)):
                top1_idx = int(np.argmax(probs[i]))
                if probs[i][top1_idx] >= conf and margins[i] >= margin:
                    preds.append(top1_idx)
                else:
                    preds.append(-1)

            preds = np.array(preds, dtype=int)
            mask = preds != -1
            if np.sum(mask) == 0:
                continue

            macro_f1 = f1_score(true[mask], preds[mask], average="macro", zero_division=0)
            if macro_f1 > best_macro_f1:
                best_macro_f1 = macro_f1
                best_conf = float(conf)
                best_margin = float(margin)
                best_metrics = {
                    "confidence": best_conf,
                    "margin": best_margin,
                    "macro_f1": float(macro_f1),
                    "accepted_rate": float(np.mean(mask)),
                }

    return best_conf, best_margin, best_metrics


def stratified_split(paths: list[Path], labels: list[str], train_frac=0.8, val_frac=0.1):
    from collections import defaultdict
    by_class = defaultdict(list)
    for p, l in zip(paths, labels):
        by_class[l].append(p)

    train_paths, val_paths, test_paths = [], [], []
    for cls, cls_paths in sorted(by_class.items()):
        n_total = len(cls_paths)
        n_train = int(n_total * train_frac)
        n_val = int(n_total * val_frac)
        random.shuffle(cls_paths)
        train_paths.extend([(p, cls) for p in cls_paths[:n_train]])
        val_paths.extend([(p, cls) for p in cls_paths[n_train:n_train + n_val]])
        test_paths.extend([(p, cls) for p in cls_paths[n_train + n_val:]])

    return train_paths, val_paths, test_paths


def generate_augmented_signals(raw_signals: list[np.ndarray], labels: list[str], aug_per_original: int) -> tuple[list[np.ndarray], list[str]]:
    aug_signals = []
    aug_labels = []

    for sig, lbl in zip(raw_signals, labels):
        for _ in range(aug_per_original):
            aug_sig = augment_signal(sig, p=0.9)
            aug_signals.append(aug_sig)
            aug_labels.append(lbl)

    return aug_signals, aug_labels


def main():
    parser = argparse.ArgumentParser(description="CPU-optimized 3-class danger classifier training with phone augmentation")
    parser.add_argument("--epochs", type=int, default=30, help="Max epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--num-workers", type=int, default=2, help="DataLoader workers")
    parser.add_argument("--cache-dir", type=str, default=str(ML_DIR / "mel_cache_classifier"), help="Mel feature cache directory")
    parser.add_argument("--recompute-cache", action="store_true", help="Force recompute mel cache")
    parser.add_argument("--aug-per-original", type=int, default=AUG_PER_ORIGINAL, help="Number of augmented versions per original training audio")
    args = parser.parse_args()

    lines: list[str] = []
    t_start = time.time()

    log("=" * 60, lines)
    log("3-CLASS DANGER CLASSIFIER TRAINING", lines)
    log("Phone-Realistic Augmentation + Mel Caching", lines)
    log("=" * 60, lines)

    gunshot_paths = collect_custom_files("Gunshot", GUNSHOT_SAMPLE_COUNT)
    scream_paths = collect_custom_files("Scream", SCREAM_SAMPLE_COUNT)
    accident_paths = collect_custom_files("Accident", ACCIDENT_SAMPLE_COUNT)

    log(f"Gunshot files: {len(gunshot_paths)}", lines)
    log(f"Scream files: {len(scream_paths)}", lines)
    log(f"Accident files: {len(accident_paths)}", lines)

    all_danger_paths = [(p, "gunshot") for p in gunshot_paths] + [(p, "scream") for p in scream_paths] + [(p, "accident") for p in accident_paths]
    all_danger_labels = [l for _, l in all_danger_paths]

    log(f"\nTotal danger files: {len(all_danger_paths)}", lines)

    log("\n=== PHASE 1: Stratified Train/Val/Test Split ===", lines)
    train_split, val_split, test_split = stratified_split(
        [p for p, _ in all_danger_paths],
        [l for _, l in all_danger_paths],
        train_frac=0.8,
        val_frac=0.1,
    )

    log(f"Train split: {len(train_split)} files", lines)
    log(f"Validation split: {len(val_split)} files", lines)
    log(f"Test split: {len(test_split)} files", lines)

    for split_name, split_data in [("Train", train_split), ("Validation", val_split), ("Test", test_split)]:
        counts = Counter([l for _, l in split_data])
        log(f"  {split_name} distribution: {dict(counts)}", lines)

    log("\n=== PHASE 2: Load Raw Audio ===", lines)
    def load_raw_batch(split_data):
        signals = []
        valid = []
        for i, (p, lbl) in enumerate(split_data):
            sig = _load_raw(p)
            if sig is not None:
                signals.append(sig)
                valid.append((p, lbl))
            if (i + 1) % 100 == 0:
                log(f"  Loaded {i + 1}/{len(split_data)} ({len(signals)} valid)", lines)
        return signals, valid

    train_signals, train_valid = load_raw_batch(train_split)
    val_signals, val_valid = load_raw_batch(val_split)
    test_signals, test_valid = load_raw_batch(test_split)

    log(f"Train raw signals: {len(train_signals)}", lines)
    log(f"Validation raw signals: {len(val_signals)}", lines)
    log(f"Test raw signals: {len(test_signals)}", lines)

    log("\n=== PHASE 3: Apply Augmentation to TRAIN Only ===", lines)

    aug_train_signals = []
    aug_train_labels = []

    for sig, lbl in zip(train_signals, [l for _, l in train_valid]):
        if lbl == "gunshot":
            aug_count = GUNSHOT_AUG_PER_ORIGINAL
        else:
            aug_count = AUG_PER_ORIGINAL
        for _ in range(aug_count):
            aug_sig = augment_signal(sig, p=0.9)
            aug_train_signals.append(aug_sig)
            aug_train_labels.append(lbl)

    log(f"Original train signals: {len(train_signals)}", lines)
    log(f"Augmented train signals: {len(aug_train_signals)}", lines)

    all_train_signals = train_signals + aug_train_signals
    all_train_labels = [l for _, l in train_valid] + aug_train_labels

    log(f"Total train signals after augmentation: {len(all_train_signals)}", lines)

    log("\n=== PHASE 4: Compute Mel Features ===", lines)
    t_mel = time.time()

    train_mels = []
    for i, sig in enumerate(all_train_signals):
        mel = _compute_mel(sig)
        train_mels.append(mel)
        if (i + 1) % 500 == 0:
            log(f"  Train mel {i + 1}/{len(all_train_signals)} ({time.time() - t_mel:.1f}s)", lines)

    val_mels = []
    for i, sig in enumerate(val_signals):
        mel = _compute_mel(sig)
        val_mels.append(mel)
        if (i + 1) % 100 == 0:
            log(f"  Val mel {i + 1}/{len(val_signals)} ({time.time() - t_mel:.1f}s)", lines)

    test_mels = []
    for i, sig in enumerate(test_signals):
        mel = _compute_mel(sig)
        test_mels.append(mel)
        if (i + 1) % 100 == 0:
            log(f"  Test mel {i + 1}/{len(test_signals)} ({time.time() - t_mel:.1f}s)", lines)

    log(f"Mel computation done: train={len(train_mels)}, val={len(val_mels)}, test={len(test_mels)} ({time.time() - t_mel:.1f}s)", lines)

    all_mels = train_mels + val_mels + test_mels
    scaler = compute_normalization(all_mels)
    log(f"Normalization: mean={scaler['mean']:.4f}, std={scaler['std']:.4f}", lines)

    train_mels_norm = np.stack([normalize_mel(m, scaler) for m in train_mels]).astype(np.float32)
    val_mels_norm = np.stack([normalize_mel(m, scaler) for m in val_mels]).astype(np.float32)
    test_mels_norm = np.stack([normalize_mel(m, scaler) for m in test_mels]).astype(np.float32)

    classes = ["accident", "gunshot", "scream"]
    class_to_idx = {c: i for i, c in enumerate(classes)}

    train_labels = np.array([class_to_idx[l] for l in all_train_labels], dtype=np.int64)
    val_labels = np.array([class_to_idx[l] for _, l in val_valid], dtype=np.int64)
    test_labels = np.array([class_to_idx[l] for _, l in test_valid], dtype=np.int64)

    log(f"\nTrain: {len(train_labels)} files", lines)
    log(f"Validation: {len(val_labels)} files", lines)
    log(f"Test: {len(test_labels)} files", lines)

    for split_name, split_labels in [("Train", train_labels), ("Validation", val_labels), ("Test", test_labels)]:
        counts = Counter([classes[i] for i in split_labels])
        log(f"  {split_name} distribution: {dict(counts)}", lines)

    log("\n=== PHASE 5: Create Datasets ===", lines)
    train_dataset = CachedMelDataset(train_mels_norm, train_labels, augment=True)
    val_dataset = CachedMelDataset(val_mels_norm, val_labels, augment=False)
    test_dataset = CachedMelDataset(test_mels_norm, test_labels, augment=False)

    device = torch.device("cpu")
    log(f"Device: {device}", lines)

    train_counts = Counter([classes[i] for i in train_labels])
    num_classes = len(classes)
    cw = np.zeros(num_classes, dtype=np.float32)
    for ci in range(num_classes):
        cw[ci] = len(train_labels) / (num_classes * max(train_counts.get(classes[ci], 1), 1))
    class_weight_boost = {"gunshot": 1.8, "accident": 1.0, "scream": 1.0}
    for ci, cls in enumerate(classes):
        cw[ci] *= class_weight_boost.get(cls, 1.0)
    cw_t = torch.tensor(cw, dtype=torch.float32).to(device)
    log(f"Class weights: {dict(zip(classes, cw.tolist()))}", lines)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=False,
        persistent_workers=False,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=False,
        persistent_workers=False,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=False,
        persistent_workers=False,
    )

    log("\n=== PHASE 6: Train Model ===", lines)

    model = DangerSoundCNN(num_classes).to(device)
    criterion = nn.CrossEntropyLoss(weight=cw_t)
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6,
    )

    best_val_acc = 0.0
    best_state = None
    patience_counter = 0
    max_patience = 7
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}

    for epoch in range(1, args.epochs + 1):
        model.train()
        t_loss = 0.0
        t_correct = 0
        t_total = 0
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            out = model(bx)
            loss = criterion(out, by)
            loss.backward()
            optimizer.step()
            t_loss += loss.item() * bx.size(0)
            t_correct += out.argmax(1).eq(by).sum().item()
            t_total += bx.size(0)

        t_loss /= t_total
        t_acc = t_correct / t_total

        model.eval()
        v_loss = 0.0
        v_correct = 0
        v_total = 0
        with torch.no_grad():
            for bx, by in val_loader:
                bx, by = bx.to(device), by.to(device)
                out = model(bx)
                loss = criterion(out, by)
                v_loss += loss.item() * bx.size(0)
                v_correct += out.argmax(1).eq(by).sum().item()
                v_total += by.size(0)

        v_loss /= v_total
        v_acc = v_correct / v_total

        scheduler.step(v_loss)
        lr = optimizer.param_groups[0]["lr"]

        if epoch == 1 or epoch % 5 == 0:
            log(f"  Epoch {epoch:3d}/{args.epochs} | t_loss={t_loss:.4f} t_acc={t_acc:.4f} "
                f"| v_loss={v_loss:.4f} v_acc={v_acc:.4f} | lr={lr:.6f}", lines)

        history["train_loss"].append(t_loss)
        history["train_acc"].append(t_acc)
        history["val_loss"].append(v_loss)
        history["val_acc"].append(v_acc)

        if v_acc > best_val_acc:
            best_val_acc = v_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= max_patience:
            log(f"  Early stop at epoch {epoch} (best val_acc={best_val_acc:.4f})", lines)
            break

    if best_state:
        model.load_state_dict(best_state)
        model.to(device)

    log("\n=== PHASE 7: Evaluate ===", lines)

    val_results = evaluate_model(model, val_loader, device, classes)
    test_results = evaluate_model(model, test_loader, device, classes)

    log(f"Validation accuracy: {val_results['accuracy']:.4f}", lines)
    log(f"Validation loss: {val_results['loss']:.4f}", lines)
    log("\nClassification Report (Validation):", lines)
    log(val_results["report"], lines)

    log(f"\nTest accuracy: {test_results['accuracy']:.4f}", lines)
    log(f"Test loss: {test_results['loss']:.4f}", lines)
    log("\nClassification Report (Test):", lines)
    log(test_results["report"], lines)

    log("Confusion Matrix (Test):", lines)
    cm = test_results["confusion_matrix"]
    for i, row in enumerate(cm):
        log(f"  {classes[i]}: {row.tolist()}", lines)

    log("\nPer-class metrics (Test):", lines)
    for cls, metrics in test_results["per_class"].items():
        log(f"  {cls}: precision={metrics['precision']:.4f} recall={metrics['recall']:.4f} "
            f"f1={metrics['f1']:.4f} support={metrics['support']}", lines)

    log("\n=== PHASE 8: Threshold Tuning ===", lines)

    model.eval()
    val_probs = []
    with torch.no_grad():
        for bx, _ in val_loader:
            bx = bx.to(device)
            out = model(bx)
            val_probs.append(torch.softmax(out, dim=1).cpu().numpy())
    val_probs = np.concatenate(val_probs, axis=0)

    best_conf, best_margin, best_metrics = find_best_thresholds(val_probs, val_results["true"], classes)
    log(f"Best confidence threshold: {best_conf:.2f}", lines)
    log(f"Best margin threshold: {best_margin:.2f}", lines)
    for k, v in best_metrics.items():
        log(f"  {k}: {v:.4f}", lines)

    threshold_info = {
        "confidence_threshold": best_conf,
        "margin_threshold": best_margin,
        "validation_metrics": best_metrics,
        "classes": classes,
    }

    log("\n=== PHASE 9: Save Model ===", lines)

    OUTPUT_MODEL_PATH = ML_DIR / "danger_sound_cnn_model.pth"
    OUTPUT_CLASSES_PATH = ML_DIR / "cnn_classes.pkl"
    OUTPUT_SCALER_PATH = ML_DIR / "cnn_scaler_info.pkl"
    OUTPUT_REPORT_PATH = ML_DIR / "training_report.txt"
    OUTPUT_THRESHOLD_JSON = ML_DIR / "classifier_thresholds.json"

    torch.save({
        "model_state_dict": model.state_dict(),
        "classes": classes,
        "num_classes": num_classes,
        "sample_rate": SAMPLE_RATE,
        "duration": DURATION,
        "n_mels": N_MELS,
        "n_fft": N_FFT,
        "hop_length": HOP_LENGTH,
        "img_height": IMG_HEIGHT,
        "img_width": IMG_WIDTH,
        "scaler_info": scaler,
        "threshold_info": threshold_info,
        "aug_per_original": args.aug_per_original,
    }, OUTPUT_MODEL_PATH)
    log(f"Model saved: {OUTPUT_MODEL_PATH}", lines)

    with open(OUTPUT_CLASSES_PATH, "wb") as f:
        pickle.dump({"classes": classes}, f)
    log(f"Classes saved: {OUTPUT_CLASSES_PATH}", lines)

    with open(OUTPUT_SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    log(f"Scaler saved: {OUTPUT_SCALER_PATH}", lines)

    with open(OUTPUT_THRESHOLD_JSON, "w") as f:
        json.dump(threshold_info, f, indent=2)
    log(f"Thresholds saved: {OUTPUT_THRESHOLD_JSON}", lines)

    log("\n" + "=" * 60, lines)
    log("3-CLASS CLASSIFIER TRAINING COMPLETE", lines)
    log("=" * 60, lines)

    lines.append(f"\nSummary:")
    lines.append(f"  Original danger files: {len(all_danger_paths)}")
    lines.append(f"  Train originals: {len(train_split)}")
    lines.append(f"  Train augmented: {len(aug_train_signals)}")
    lines.append(f"  Train total: {len(all_train_labels)}")
    lines.append(f"  Validation: {len(val_split)}")
    lines.append(f"  Test: {len(test_split)}")
    lines.append(f"  Classes: {classes}")
    lines.append(f"  Aug per original: {args.aug_per_original}")
    lines.append(f"  Best val_acc: {best_val_acc:.4f}")
    lines.append(f"  Test accuracy: {test_results['accuracy']:.4f}")
    lines.append(f"  Confidence threshold: {best_conf:.2f}")
    lines.append(f"  Margin threshold: {best_margin:.2f}")
    lines.append(f"  Total time: {time.time() - t_start:.1f}s")

    with open(OUTPUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")
    log(f"Report saved: {OUTPUT_REPORT_PATH}", lines)


if __name__ == "__main__":
    main()
