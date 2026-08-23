from __future__ import annotations

import argparse
import csv
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
    roc_auc_score,
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
    precompute_mel_for_path,
    _compute_mel,
)
from phone_augment import (
    _load_raw,
    augment_signal,
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

DANGER_CLASSES = ["accident", "gunshot", "scream"]
NON_DANGER_CLASS = "non_danger"

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


class CachedBinaryDataset(Dataset):
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


class BinaryDangerGate(nn.Module):
    def __init__(self):
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
            nn.Linear(128, 1),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x).squeeze(1)


def evaluate_binary_gate(model, dataloader, device):
    model.eval()
    all_preds = []
    all_true = []
    all_probs = []

    with torch.no_grad():
        for bx, by in dataloader:
            bx, by = bx.to(device), by.to(device)
            logits = model(bx)
            probs = torch.sigmoid(logits)
            preds = (probs >= 0.5).long()
            all_preds.extend(preds.cpu().numpy())
            all_true.extend(by.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())

    all_preds = np.array(all_preds)
    all_true = np.array(all_true)
    all_probs = np.array(all_probs)

    accuracy = np.mean(all_preds == all_true)
    precision = precision_score(all_true, all_preds, zero_division=0)
    recall = recall_score(all_true, all_preds, zero_division=0)
    f1 = f1_score(all_true, all_preds, zero_division=0)

    danger_recall = recall_score(all_true, all_preds, pos_label=1, zero_division=0)
    non_danger_recall = recall_score(all_true, all_preds, pos_label=0, zero_division=0)
    non_danger_fp_rate = np.sum((all_true == 0) & (all_preds == 1)) / max(np.sum(all_true == 0), 1)

    try:
        auc = roc_auc_score(all_true, all_probs)
    except ValueError:
        auc = 0.0

    report = classification_report(all_true, all_preds, target_names=["non_danger", "danger"], digits=4, zero_division=0)
    cm = confusion_matrix(all_true, all_preds)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "danger_recall": danger_recall,
        "non_danger_recall": non_danger_recall,
        "non_danger_fp_rate": non_danger_fp_rate,
        "auc": auc,
        "report": report,
        "confusion_matrix": cm,
        "predictions": all_preds,
        "probabilities": all_probs,
        "true": all_true,
    }


def find_best_threshold(probs, true):
    best_f1 = 0
    best_thresh = 0.5
    best_metrics = None

    for thresh in np.arange(0.3, 0.95, 0.05):
        preds = (probs >= thresh).astype(int)
        tp = np.sum((true == 1) & (preds == 1))
        fp = np.sum((true == 0) & (preds == 1))
        fn = np.sum((true == 1) & (preds == 0))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        non_danger_fp_rate = fp / max(np.sum(true == 0), 1)

        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh
            best_metrics = {
                "threshold": float(thresh),
                "f1": float(f1),
                "precision": float(precision),
                "recall": float(recall),
                "danger_recall": float(recall),
                "non_danger_recall": float(1 - non_danger_fp_rate),
                "non_danger_fp_rate": float(non_danger_fp_rate),
            }

    return best_thresh, best_metrics


def generate_augmented_signals(raw_signals: list[np.ndarray], labels: list[str], aug_per_original: int = AUG_PER_ORIGINAL) -> tuple[list[np.ndarray], list[str]]:
    aug_signals = []
    aug_labels = []

    for sig, lbl in zip(raw_signals, labels):
        for _ in range(aug_per_original):
            aug_sig = augment_signal(sig, p=0.9)
            aug_signals.append(aug_sig)
            aug_labels.append(lbl)

    return aug_signals, aug_labels


def compute_mels_from_signals(signals: list[np.ndarray]) -> np.ndarray:
    mels = []
    for sig in signals:
        mel = _compute_mel(sig)
        mels.append(mel)
    return np.array(mels, dtype=np.float32)


def main():
    parser = argparse.ArgumentParser(description="CPU-optimized binary danger gate training with phone-realistic augmentation")
    parser.add_argument("--epochs", type=int, default=30, help="Max epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--num-workers", type=int, default=2, help="DataLoader workers")
    parser.add_argument("--cache-dir", type=str, default=str(ML_DIR / "mel_cache_gate"), help="Mel feature cache directory")
    parser.add_argument("--recompute-cache", action="store_true", help="Force recompute mel cache")
    parser.add_argument("--aug-per-original", type=int, default=AUG_PER_ORIGINAL, help="Number of augmented versions per original audio")
    args = parser.parse_args()

    lines: list[str] = []
    t_start = time.time()

    log("=" * 60, lines)
    log("BINARY DANGER GATE TRAINING", lines)
    log("Phone-Realistic Augmentation + Mel Caching", lines)
    log("=" * 60, lines)

    esc50 = load_esc50_by_category()
    log(f"ESC-50 categories loaded: {len(esc50)}", lines)

    gunshot_paths = collect_custom_files("Gunshot")
    scream_paths = collect_custom_files("Scream")
    accident_paths = collect_custom_files("Accident")

    log(f"Gunshot files: {len(gunshot_paths)}", lines)
    log(f"Scream files: {len(scream_paths)}", lines)
    log(f"Accident files: {len(accident_paths)}", lines)

    danger_paths = [(p, "danger") for p in gunshot_paths + scream_paths + accident_paths]
    non_danger_paths = []
    for cat, files in esc50.items():
        for p in files:
            non_danger_paths.append((p, "non_danger"))

    random.shuffle(danger_paths)
    random.shuffle(non_danger_paths)

    log(f"Danger samples: {len(danger_paths)}", lines)
    log(f"Non-danger samples: {len(non_danger_paths)}", lines)

    max_non_danger = min(len(non_danger_paths), len(danger_paths) * 3)
    non_danger_paths = non_danger_paths[:max_non_danger]
    log(f"Non-danger samples used: {len(non_danger_paths)}", lines)

    all_paths = [p for p, _ in danger_paths + non_danger_paths]
    all_labels = [l for _, l in danger_paths + non_danger_paths]

    log(f"\nTotal files: {len(all_paths)}", lines)

    log("\n=== PHASE 1: Load raw audio ===", lines)
    raw_signals = []
    valid_indices = []
    for i, p in enumerate(all_paths):
        sig = _load_raw(p)
        if sig is not None:
            raw_signals.append(sig)
            valid_indices.append(i)
        if (i + 1) % 200 == 0:
            log(f"  Loaded {i + 1}/{len(all_paths)} ({len(raw_signals)} valid)", lines)

    log(f"Loaded raw signals: {len(raw_signals)}/{len(all_paths)}", lines)
    filtered_labels = [all_labels[i] for i in valid_indices]
    filtered_paths = [all_paths[i] for i in valid_indices]

    log("\n=== PHASE 2: Apply realistic augmentations ===", lines)
    danger_mask = [l == "danger" for l in filtered_labels]
    danger_signals = [s for s, m in zip(raw_signals, danger_mask) if m]
    danger_labels = [l for l, m in zip(filtered_labels, danger_mask) if m]
    non_danger_signals = [s for s, m in zip(raw_signals, danger_mask) if not m]
    non_danger_labels = [l for l, m in zip(filtered_labels, danger_mask) if not m]

    log(f"Danger originals: {len(danger_signals)}", lines)
    log(f"Non-danger originals: {len(non_danger_signals)}", lines)

    aug_danger_signals, aug_danger_labels = generate_augmented_signals(
        danger_signals, danger_labels, args.aug_per_original
    )
    aug_non_danger_signals, aug_non_danger_labels = generate_augmented_signals(
        non_danger_signals, non_danger_labels, args.aug_per_original
    )

    log(f"Augmented danger: {len(aug_danger_signals)}", lines)
    log(f"Augmented non-danger: {len(aug_non_danger_signals)}", lines)

    all_signals = raw_signals + aug_danger_signals + aug_non_danger_signals
    all_labels_aug = filtered_labels + aug_danger_labels + aug_non_danger_labels

    log(f"Total signals after augmentation: {len(all_signals)}", lines)

    log("\n=== PHASE 3: Compute mel features ===", lines)
    t_mel = time.time()
    all_mels = []
    for i, sig in enumerate(all_signals):
        mel = _compute_mel(sig)
        all_mels.append(mel)
        if (i + 1) % 500 == 0:
            log(f"  Mel computed {i + 1}/{len(all_signals)} ({time.time() - t_mel:.1f}s)", lines)
    log(f"Mel computation done: {len(all_mels)} ({time.time() - t_mel:.1f}s)", lines)

    mels_array = np.array(all_mels, dtype=np.float32)
    labels_array = np.array([1 if l == "danger" else 0 for l in all_labels_aug])

    scaler = compute_normalization(all_mels)
    log(f"Normalization: mean={scaler['mean']:.4f}, std={scaler['std']:.4f}", lines)

    normed = [normalize_mel(m, scaler) for m in all_mels]
    mels_array = np.stack(normed).astype(np.float32)

    log("\n=== PHASE 4: Train/Validation/Test Split ===", lines)
    n_total = len(mels_array)
    n_train = int(n_total * 0.8)
    n_val = int(n_total * 0.1)
    n_test = n_total - n_train - n_val

    perm = np.random.RandomState(42).permutation(n_total)
    train_idx = perm[:n_train]
    val_idx = perm[n_train: n_train + n_val]
    test_idx = perm[n_train + n_val:]

    train_mels = mels_array[train_idx]
    train_labels = labels_array[train_idx]
    val_mels = mels_array[val_idx]
    val_labels = labels_array[val_idx]
    test_mels = mels_array[test_idx]
    test_labels = labels_array[test_idx]

    log(f"Train: {len(train_labels)} files", lines)
    log(f"Validation: {len(val_labels)} files", lines)
    log(f"Test: {len(test_labels)} files", lines)

    for split_name, split_labels in [("Train", train_labels), ("Validation", val_labels), ("Test", test_labels)]:
        counts = Counter(["danger" if l == 1 else "non_danger" for l in split_labels])
        log(f"  {split_name} distribution: {dict(counts)}", lines)

    log("\n=== PHASE 5: Create Datasets ===", lines)
    train_dataset = CachedBinaryDataset(train_mels, train_labels, augment=True)
    val_dataset = CachedBinaryDataset(val_mels, val_labels, augment=False)
    test_dataset = CachedBinaryDataset(test_mels, test_labels, augment=False)

    device = torch.device("cpu")
    log(f"Device: {device}", lines)

    train_counts = Counter(["danger" if l == 1 else "non_danger" for l in train_labels])
    cw = torch.tensor([
        len(train_labels) / (2 * max(train_counts.get("non_danger", 1), 1)),
        len(train_labels) / (2 * max(train_counts.get("danger", 1), 1)),
    ], dtype=torch.float32).to(device)
    log(f"Class weights: non_danger={cw[0]:.4f}, danger={cw[1]:.4f}", lines)

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

    log("\n=== PHASE 6: Train Binary Gate ===", lines)

    model = BinaryDangerGate().to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([cw[1] / cw[0]]).to(device))
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6,
    )

    best_val_f1 = 0.0
    best_state = None
    patience_counter = 0
    max_patience = 7
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    start_epoch = 1

    OUTPUT_CHECKPOINT = ML_DIR / "danger_gate_checkpoint.pth"

    if OUTPUT_CHECKPOINT.exists():
        try:
            checkpoint = torch.load(OUTPUT_CHECKPOINT, map_location=device, weights_only=False)
            model.load_state_dict(checkpoint["model_state_dict"])
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
            best_val_f1 = checkpoint["best_val_f1"]
            patience_counter = checkpoint["patience_counter"]
            start_epoch = checkpoint["epoch"] + 1
            history = checkpoint["history"]
            best_state = checkpoint.get("best_state")
            log(f"Resumed from checkpoint at epoch {checkpoint['epoch']}", lines)
        except Exception as exc:
            log(f"Failed to load checkpoint: {exc}", lines)

    for epoch in range(start_epoch, args.epochs + 1):
        model.train()
        t_loss = 0.0
        t_correct = 0
        t_total = 0
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device).float()
            optimizer.zero_grad()
            logits = model(bx)
            loss = criterion(logits, by)
            loss.backward()
            optimizer.step()
            t_loss += loss.item() * bx.size(0)
            probs = torch.sigmoid(logits)
            preds = (probs >= 0.5).long()
            t_correct += preds.eq(by.long()).sum().item()
            t_total += bx.size(0)

        t_loss /= t_total
        t_acc = t_correct / t_total

        model.eval()
        v_loss = 0.0
        v_correct = 0
        v_total = 0
        with torch.no_grad():
            for bx, by in val_loader:
                bx, by = bx.to(device), by.to(device).float()
                logits = model(bx)
                loss = criterion(logits, by)
                v_loss += loss.item() * bx.size(0)
                probs = torch.sigmoid(logits)
                preds = (probs >= 0.5).long()
                v_correct += preds.eq(by.long()).sum().item()
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

        if v_acc > best_val_f1:
            best_val_f1 = v_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= max_patience:
            log(f"  Early stop at epoch {epoch} (best val_acc={best_val_f1:.4f})", lines)
            break

        checkpoint = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "best_val_f1": best_val_f1,
            "patience_counter": patience_counter,
            "history": history,
            "best_state": best_state,
        }
        torch.save(checkpoint, OUTPUT_CHECKPOINT)

    if best_state:
        model.load_state_dict(best_state)
        model.to(device)

    log("\n=== PHASE 7: Evaluate Binary Gate ===", lines)

    val_results = evaluate_binary_gate(model, val_loader, device)
    test_results = evaluate_binary_gate(model, test_loader, device)

    log(f"Validation accuracy: {val_results['accuracy']:.4f}", lines)
    log(f"Validation F1: {val_results['f1']:.4f}", lines)
    log(f"Validation danger recall: {val_results['danger_recall']:.4f}", lines)
    log(f"Validation non-danger recall: {val_results['non_danger_recall']:.4f}", lines)
    log(f"Validation non-danger FP rate: {val_results['non_danger_fp_rate']:.4f}", lines)
    log(f"Validation AUC: {val_results['auc']:.4f}", lines)

    log("\nClassification Report (Validation):", lines)
    log(val_results["report"], lines)

    log("Confusion Matrix (Validation):", lines)
    cm = val_results["confusion_matrix"]
    log(f"  non_danger: {cm[0].tolist()}", lines)
    log(f"  danger:     {cm[1].tolist()}", lines)

    log(f"\nTest accuracy: {test_results['accuracy']:.4f}", lines)
    log(f"Test F1: {test_results['f1']:.4f}", lines)
    log(f"Test danger recall: {test_results['danger_recall']:.4f}", lines)
    log(f"Test non-danger recall: {test_results['non_danger_recall']:.4f}", lines)
    log(f"Test non-danger FP rate: {test_results['non_danger_fp_rate']:.4f}", lines)

    log("\nClassification Report (Test):", lines)
    log(test_results["report"], lines)

    log("Confusion Matrix (Test):", lines)
    cm = test_results["confusion_matrix"]
    log(f"  non_danger: {cm[0].tolist()}", lines)
    log(f"  danger:     {cm[1].tolist()}", lines)

    best_thresh, best_metrics = find_best_threshold(
        val_results["probabilities"], val_results["true"]
    )
    log(f"\nBest threshold from validation: {best_thresh:.2f}", lines)
    for k, v in best_metrics.items():
        log(f"  {k}: {v:.4f}", lines)

    log("\n=== PHASE 8: Save Model ===", lines)

    OUTPUT_MODEL_PATH = ML_DIR / "danger_gate_model.pth"
    OUTPUT_CLASSES_PATH = ML_DIR / "gate_classes.pkl"
    OUTPUT_SCALER_PATH = ML_DIR / "gate_scaler_info.pkl"
    OUTPUT_REPORT_PATH = ML_DIR / "gate_training_report.txt"
    OUTPUT_THRESHOLD_JSON = ML_DIR / "gate_thresholds.json"

    torch.save({
        "model_state_dict": model.state_dict(),
        "classes": ["non_danger", "danger"],
        "num_classes": 2,
        "sample_rate": SAMPLE_RATE,
        "duration": DURATION,
        "n_mels": N_MELS,
        "n_fft": N_FFT,
        "hop_length": HOP_LENGTH,
        "img_height": IMG_HEIGHT,
        "img_width": IMG_WIDTH,
        "scaler_info": scaler,
        "best_threshold": best_thresh,
        "threshold_metrics": best_metrics,
        "aug_per_original": args.aug_per_original,
    }, OUTPUT_MODEL_PATH)
    log(f"Model saved: {OUTPUT_MODEL_PATH}", lines)

    with open(OUTPUT_CLASSES_PATH, "wb") as f:
        pickle.dump({"classes": ["non_danger", "danger"]}, f)
    log(f"Classes saved: {OUTPUT_CLASSES_PATH}", lines)

    with open(OUTPUT_SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    log(f"Scaler saved: {OUTPUT_SCALER_PATH}", lines)

    with open(OUTPUT_THRESHOLD_JSON, "w") as f:
        import json
        json.dump({
            "best_threshold": best_thresh,
            "validation_metrics": best_metrics,
            "danger_recall": val_results["danger_recall"],
            "non_danger_recall": val_results["non_danger_recall"],
            "non_danger_fp_rate": val_results["non_danger_fp_rate"],
            "auc": val_results["auc"],
            "aug_per_original": args.aug_per_original,
        }, f, indent=2)
    log(f"Threshold saved: {OUTPUT_THRESHOLD_JSON}", lines)

    log("\n" + "=" * 60, lines)
    log("BINARY GATE TRAINING COMPLETE", lines)
    log("=" * 60, lines)

    lines.append(f"\nSummary:")
    lines.append(f"  Danger samples: {len(danger_paths)}")
    lines.append(f"  Non-danger samples: {len(non_danger_paths)}")
    lines.append(f"  Original signals: {len(raw_signals)}")
    lines.append(f"  Augmented signals: {len(aug_danger_signals) + len(aug_non_danger_signals)}")
    lines.append(f"  Total training signals: {len(all_signals)}")
    lines.append(f"  Train: {len(train_labels)}")
    lines.append(f"  Validation: {len(val_labels)}")
    lines.append(f"  Test: {len(test_labels)}")
    lines.append(f"  Best threshold: {best_thresh:.2f}")
    lines.append(f"  Val non-danger FP rate: {val_results['non_danger_fp_rate']:.4f}")
    lines.append(f"  Val danger recall: {val_results['danger_recall']:.4f}")
    lines.append(f"  Total time: {time.time() - t_start:.1f}s")

    with open(OUTPUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")
    log(f"Report saved: {OUTPUT_REPORT_PATH}", lines)


if __name__ == "__main__":
    main()
