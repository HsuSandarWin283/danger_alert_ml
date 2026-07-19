from __future__ import annotations

import csv
import os
import pickle
import random
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

try:
    import librosa
except ImportError:
    raise ImportError("librosa is required: pip install librosa")

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
except ImportError:
    raise ImportError("PyTorch is required: pip install torch")

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedGroupKFold

matplotlib_available = False
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    matplotlib_available = True
except ImportError:
    pass

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
CUSTOM_DATASET_DIR = APP_DIR / "dataset"
META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"

OUTPUT_MODEL_PATH = ML_DIR / "danger_sound_cnn_model.pth"
OUTPUT_CLASSES_PATH = ML_DIR / "cnn_classes.pkl"
OUTPUT_SCALER_PATH = ML_DIR / "cnn_scaler_info.pkl"
OUTPUT_REPORT_PATH = ML_DIR / "augmented_training_report.txt"
OUTPUT_CM_IMAGE = ML_DIR / "confusion_matrix.png"
OUTPUT_CURVES_IMAGE = ML_DIR / "training_curves.png"

SAMPLE_RATE = 22050
DURATION = 5.0
N_MELS = 128
N_FFT = 2048
HOP_LENGTH = 512
IMG_HEIGHT = 128
IMG_WIDTH = 128
TARGET_LENGTH = int(SAMPLE_RATE * DURATION)

SNR_RANGE = (5.0, 20.0)
VOLUME_RANGE = (0.5, 1.5)
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

CLASS_TARGETS = {
    "gunshot": 1100,
    "scream": 600,
    "accident": 500,
}

BG_CATEGORIES = [
    "rain", "wind", "engine", "thunderstorm", "sea_waves",
    "train", "helicopter", "airplane", "insects", "crickets",
    "chirping_birds", "vacuum_cleaner", "washing_machine",
    "crow", "dog", "cat", "footsteps", "clock_tick",
]

ACCIDENT_SOUND_CATEGORIES = ["glass_breaking", "car_horn"]
DANGER_EXCLUDED_CATEGORIES = {
    "glass_breaking", "car_horn", "siren", "chainsaw",
    "fireworks", "crying_baby",
}

random.seed(42)
np.random.seed(42)
torch.manual_seed(42)


def log(msg: str, lines: list[str] | None = None) -> None:
    print(msg, flush=True)
    if lines is not None:
        lines.append(msg)


def load_audio_file(path: Path) -> np.ndarray | None:
    try:
        signal, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True, duration=DURATION)
        if len(signal) < TARGET_LENGTH:
            signal = np.pad(signal, (0, TARGET_LENGTH - len(signal)))
        else:
            signal = signal[:TARGET_LENGTH]
        return signal
    except Exception:
        return None


def compute_rms(signal: np.ndarray) -> float:
    if len(signal) == 0:
        return 0.0
    return float(np.sqrt(np.mean(signal ** 2)))


def mix_two_signals(
    foreground: np.ndarray,
    background: np.ndarray,
    snr_db: float,
    fg_volume: float,
    bg_offset: int = 0,
) -> np.ndarray:
    fg = foreground * fg_volume
    fg_rms = compute_rms(fg)
    if fg_rms < 1e-8:
        return fg

    bg = background.copy()
    bg_len = len(bg)
    if bg_len < len(fg):
        bg = np.tile(bg, (len(fg) // bg_len) + 1)

    safe_offset = bg_offset % max(1, len(bg) - len(fg))
    bg_chunk = bg[safe_offset : safe_offset + len(fg)].copy()

    bg_rms = compute_rms(bg_chunk)
    if bg_rms < 1e-8:
        return fg

    desired_bg_rms = fg_rms / (10 ** (snr_db / 20.0))
    bg_chunk *= desired_bg_rms / bg_rms

    mixed = fg + bg_chunk
    peak = np.max(np.abs(mixed))
    if peak > 0.99:
        mixed *= 0.99 / peak
    return mixed


def mix_multi_signals(signals: list[np.ndarray], snr_db: float, fg_volume: float) -> np.ndarray:
    if len(signals) == 0:
        return np.zeros(TARGET_LENGTH, dtype=np.float32)
    if len(signals) == 1:
        return signals[0] * fg_volume

    result = signals[0] * fg_volume
    for i in range(1, len(signals)):
        bg_offset = random.randint(0, max(0, len(signals[i]) - len(result)))
        result = mix_two_signals(result, signals[i], snr_db, 1.0, bg_offset)
    return result


def random_bg_offset(bg_length: int) -> int:
    if bg_length <= TARGET_LENGTH:
        return 0
    return random.randint(0, bg_length - TARGET_LENGTH)


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


def collect_custom_files(folder_name: str) -> list[Path]:
    folder = CUSTOM_DATASET_DIR / folder_name
    if not folder.exists():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )


def collect_accident_subdir_files() -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    accident_dir = CUSTOM_DATASET_DIR / "accident"
    if not accident_dir.exists():
        return result
    for sub in accident_dir.iterdir():
        if sub.is_dir():
            files = [
                p for p in sub.iterdir()
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
            ]
            if files:
                result[sub.name.lower()] = sorted(files)
    return result


class MelSpectrogramDataset(Dataset):
    def __init__(
        self,
        mels: np.ndarray,
        labels: np.ndarray,
        augment: bool = False,
    ):
        self.mels = torch.tensor(mels, dtype=torch.float32).unsqueeze(1)
        self.labels = torch.tensor(labels, dtype=torch.long)
        self.augment = augment

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        x = self.mels[idx]
        y = self.labels[idx]
        if self.augment:
            x = self._apply_augmentation(x)
        return x, y

    def _apply_augmentation(self, x: torch.Tensor) -> torch.Tensor:
        if random.random() < 0.3:
            noise = torch.randn_like(x) * 0.02
            x = x + noise
        if random.random() < 0.2:
            x = x * random.uniform(0.8, 1.2)
        return x


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
            nn.Linear(256, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)


def audio_to_mel(signal: np.ndarray) -> np.ndarray:
    mel = librosa.feature.melspectrogram(
        y=signal, sr=SAMPLE_RATE, n_mels=N_MELS,
        n_fft=N_FFT, hop_length=HOP_LENGTH,
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    from scipy.ndimage import zoom
    zh = IMG_HEIGHT / mel_db.shape[0]
    zw = IMG_WIDTH / mel_db.shape[1]
    resized = zoom(mel_db, (zh, zw), order=1)
    return resized[:IMG_HEIGHT, :IMG_WIDTH].astype(np.float32)


def plot_confusion_matrix(y_true, y_pred, classes, path):
    if not matplotlib_available:
        return
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(len(classes)),
        yticks=np.arange(len(classes)),
        xticklabels=classes,
        yticklabels=classes,
        ylabel="True label",
        xlabel="Predicted label",
        title="Confusion Matrix",
    )
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                j, i, format(cm[i, j], "d"),
                ha="center", va="center",
                color="white" if cm[i, j] > thresh else "black",
            )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log(f"Confusion matrix image saved: {path}")


def plot_training_curves(history, path):
    if not matplotlib_available or not history:
        return
    epochs = range(1, len(history["train_loss"]) + 1)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(epochs, history["train_loss"], "b-", label="Train Loss")
    ax1.plot(epochs, history["val_loss"], "r-", label="Val Loss")
    ax1.set_title("Loss")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(epochs, history["train_acc"], "b-", label="Train Acc")
    ax2.plot(epochs, history["val_acc"], "r-", label="Val Acc")
    ax2.set_title("Accuracy")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Accuracy")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log(f"Training curves saved: {path}")


def main() -> None:
    lines: list[str] = []
    t_start = time.time()

    log("=" * 60, lines)
    log("DANGER SOUND CNN TRAINING WITH AUGMENTATION (PyTorch)", lines)
    log("=" * 60, lines)

    esc50 = load_esc50_by_category()
    log(f"ESC-50 categories loaded: {len(esc50)}", lines)

    gunshot_paths = collect_custom_files("gun_shot")
    scream_paths = collect_custom_files("scream")
    accident_subdirs = collect_accident_subdir_files()
    accident_paths = [p for files in accident_subdirs.values() for p in files]

    log(f"Gunshot files: {len(gunshot_paths)}", lines)
    log(f"Scream files: {len(scream_paths)}", lines)
    log(f"Accident files: {len(accident_paths)}", lines)

    bg_pool: list[Path] = []
    for cat in BG_CATEGORIES:
        bg_pool.extend(esc50.get(cat, []))
    log(f"Background pool: {len(bg_pool)} files ({len(BG_CATEGORIES)} categories)", lines)

    accident_sound_pool: list[Path] = []
    for cat in ACCIDENT_SOUND_CATEGORIES:
        accident_sound_pool.extend(esc50.get(cat, []))
    log(f"Accident sound pool (glass_breaking + car_horn): {len(accident_sound_pool)} files", lines)

    normal_paths: list[Path] = []
    for cat, files in esc50.items():
        if cat not in DANGER_EXCLUDED_CATEGORIES and cat not in BG_CATEGORIES:
            normal_paths.extend(files)
    log(f"Normal pool (ESC-50): {len(normal_paths)} files", lines)

    log("\n=== PHASE 1: Load audio into memory ===", lines)

    def load_batch(paths: list[Path], label: str) -> list[tuple[np.ndarray, str, str]]:
        results: list[tuple[np.ndarray, str, str]] = []
        t0 = time.time()
        for i, p in enumerate(paths):
            sig = load_audio_file(p)
            if sig is not None:
                results.append((sig, label, str(p)))
            if (i + 1) % 200 == 0:
                log(f"  [{label}] {i + 1}/{len(paths)} ({time.time() - t0:.1f}s)", lines)
        log(f"  [{label}] loaded {len(results)}/{len(paths)} ({time.time() - t0:.1f}s)", lines)
        return results

    gunshot_originals = load_batch(gunshot_paths, "gunshot")
    scream_originals = load_batch(scream_paths, "scream")
    accident_originals = load_batch(accident_paths, "accident")

    bg_loaded: dict[str, list[np.ndarray]] = {}
    for cat in BG_CATEGORIES:
        sigs = []
        for p in esc50.get(cat, []):
            s = load_audio_file(p)
            if s is not None:
                sigs.append(s)
        if sigs:
            bg_loaded[cat] = sigs
    log(f"  Background categories loaded: {len(bg_loaded)}", lines)

    accident_sound_loaded: dict[str, list[np.ndarray]] = {}
    for cat in ACCIDENT_SOUND_CATEGORIES:
        sigs = []
        for p in esc50.get(cat, []):
            s = load_audio_file(p)
            if s is not None:
                sigs.append(s)
        if sigs:
            accident_sound_loaded[cat] = sigs

    accident_subdir_loaded: dict[str, list[np.ndarray]] = {}
    for subdir_name, paths in accident_subdirs.items():
        sigs = []
        for p in paths:
            s = load_audio_file(p)
            if s is not None:
                sigs.append(s)
        if sigs:
            accident_subdir_loaded[subdir_name] = sigs

    normal_sampled = random.sample(normal_paths, min(1200, len(normal_paths)))
    normal_originals = load_batch(normal_sampled, "normal")

    bg_flat: list[np.ndarray] = []
    for sigs in bg_loaded.values():
        bg_flat.extend(sigs)
    log(f"  Total background signals: {len(bg_flat)}", lines)

    log("\n=== PHASE 2: Data Augmentation ===", lines)

    all_data: list[tuple[np.ndarray, str, str, str]] = []

    def pick_random_bg() -> np.ndarray:
        return random.choice(bg_flat)

    def pick_random_from_dict(d: dict[str, list[np.ndarray]]) -> np.ndarray:
        cat = random.choice(list(d.keys()))
        return random.choice(d[cat])

    def augment_danger_class(
        originals: list[tuple[np.ndarray, str, str]],
        label: str,
        target: int,
    ) -> None:
        for sig, lbl, src in originals:
            all_data.append((sig, lbl, src, "original"))

        existing = len(originals)
        need = target - existing
        if need <= 0:
            return

        log(f"  {label}: {existing} originals -> generating {need} augmented (target: {target})", lines)

        for i in range(need):
            fg_sig, _, fg_src = random.choice(originals)
            bg_sig = pick_random_bg()

            snr_db = random.uniform(*SNR_RANGE)
            vol = random.uniform(*VOLUME_RANGE)
            offset = random_bg_offset(len(bg_sig))

            mixed = mix_two_signals(fg_sig, bg_sig, snr_db, vol, offset)
            all_data.append((mixed, label, f"aug:{fg_src}+bg", "augmented"))

            if (i + 1) % 200 == 0:
                log(f"    {label}: {i + 1}/{need}", lines)

    augment_danger_class(gunshot_originals, "gunshot", CLASS_TARGETS["gunshot"])
    augment_danger_class(scream_originals, "scream", CLASS_TARGETS["scream"])

    log(f"\n  Accident augmentation: {len(accident_originals)} originals -> target {CLASS_TARGETS['accident']}", lines)
    for sig, lbl, src in accident_originals:
        all_data.append((sig, lbl, src, "original"))

    accident_need = CLASS_TARGETS["accident"] - len(accident_originals)
    if accident_need > 0:
        subdir_names = list(accident_subdir_loaded.keys())
        accident_sound_cats = list(accident_sound_loaded.keys())

        for i in range(accident_need):
            strategy = random.choice(["two_mix", "three_mix"])

            if strategy == "two_mix":
                fg_subdir = random.choice(subdir_names)
                fg_sig = random.choice(accident_subdir_loaded[fg_subdir])

                bg_type = random.choice(["glass", "horn", "bg"])
                if bg_type == "glass" and "glass_breaking" in accident_sound_loaded:
                    bg_sig = pick_random_from_dict(accident_sound_loaded)
                elif bg_type == "horn" and "car_horn" in accident_sound_loaded:
                    bg_sig = pick_random_from_dict(accident_sound_loaded)
                else:
                    bg_sig = pick_random_bg()

                snr_db = random.uniform(*SNR_RANGE)
                vol = random.uniform(*VOLUME_RANGE)
                offset = random_bg_offset(len(bg_sig))
                mixed = mix_two_signals(fg_sig, bg_sig, snr_db, vol, offset)

            else:
                fg_subdir = random.choice(subdir_names)
                fg_sig = random.choice(accident_subdir_loaded[fg_subdir])

                extra1_type = random.choice(["other_accident", "glass", "horn", "bg"])
                if extra1_type == "other_accident":
                    other_sub = random.choice(subdir_names)
                    extra1 = random.choice(accident_subdir_loaded[other_sub])
                elif extra1_type in ("glass", "horn"):
                    extra1 = pick_random_from_dict(accident_sound_loaded)
                else:
                    extra1 = pick_random_bg()

                extra2_type = random.choice(["glass", "horn", "bg"])
                if extra2_type in ("glass", "horn") and accident_sound_loaded:
                    extra2 = pick_random_from_dict(accident_sound_loaded)
                else:
                    extra2 = pick_random_bg()

                snr_db = random.uniform(*SNR_RANGE)
                vol = random.uniform(*VOLUME_RANGE)
                mixed = mix_multi_signals([fg_sig, extra1, extra2], snr_db, vol)

            all_data.append((mixed, "accident", f"aug:accident:{strategy}:{i}", "augmented"))

            if (i + 1) % 200 == 0:
                log(f"    accident: {i + 1}/{accident_need}", lines)

    for sig, lbl, src in normal_originals:
        all_data.append((sig, lbl, src, "original"))

    normal_target = 1200
    normal_need_extra = normal_target - len(normal_originals)
    if normal_need_extra > 0:
        log(f"\n  Normal: {len(normal_originals)} originals -> generating {normal_need_extra} extra with light augmentation", lines)
        for i in range(normal_need_extra):
            sig, lbl, src = random.choice(normal_originals)
            bg_sig = pick_random_bg()
            snr_db = random.uniform(15.0, 30.0)
            vol = random.uniform(0.7, 1.3)
            offset = random_bg_offset(len(bg_sig))
            mixed = mix_two_signals(sig, bg_sig, snr_db, vol, offset)
            all_data.append((mixed, "normal", f"aug_normal:{src}", "augmented"))
            if (i + 1) % 200 == 0:
                log(f"    normal: {i + 1}/{normal_need_extra}", lines)

    random.shuffle(all_data)

    log(f"\nTotal dataset size: {len(all_data)}", lines)
    counts = Counter(d[1] for d in all_data)
    orig_counts = Counter(d[1] for d in all_data if d[3] == "original")
    aug_counts = Counter(d[1] for d in all_data if d[3] == "augmented")
    for label in sorted(counts):
        log(f"  {label}: {counts[label]} (orig: {orig_counts.get(label, 0)}, aug: {aug_counts.get(label, 0)})", lines)

    log("\n=== PHASE 3: Mel Spectrogram Extraction ===", lines)
    t_mel = time.time()

    mels: list[np.ndarray] = []
    labels: list[str] = []
    sources: list[str] = []
    failed = 0

    for i, (sig, label, src, _) in enumerate(all_data):
        try:
            mel = audio_to_mel(sig)
            mels.append(mel)
            labels.append(label)
            sources.append(src)
        except Exception:
            failed += 1

        if (i + 1) % 500 == 0 or (i + 1) == len(all_data):
            log(f"  Mel: {i + 1}/{len(all_data)} (failed: {failed}) ({time.time() - t_mel:.1f}s)", lines)

    X_all = np.array(mels, dtype=np.float32)
    y_all = np.array(labels)
    source_all = np.array(sources)
    log(f"Feature shape: {X_all.shape}", lines)

    classes = sorted(set(labels))
    class_to_idx = {c: i for i, c in enumerate(classes)}
    y_encoded = np.array([class_to_idx[c] for c in y_all])
    log(f"Classes: {classes}", lines)

    log("\n=== PHASE 4: Stratified Group K-Fold Training ===", lines)

    def get_group(source_str: str) -> str:
        if source_str.startswith("aug:"):
            parts = source_str.split("+")
            if len(parts) > 1:
                bg_part = parts[-1]
                if bg_part.startswith("bg:"):
                    return bg_part
            return source_str
        return source_str

    groups = np.array([get_group(s) for s in source_all])

    unique_per_class = {}
    for cls_idx in range(len(classes)):
        mask = y_encoded == cls_idx
        unique_per_class[cls_idx] = len(set(groups[mask]))

    min_groups = min(unique_per_class.values())
    n_splits = min(5, min_groups)
    if n_splits < 2:
        n_splits = 2
    log(f"StratifiedGroupKFold: {n_splits} splits", lines)
    log(f"Unique groups per class: {dict((classes[k], v) for k, v in unique_per_class.items())}", lines)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log(f"Device: {device}", lines)

    skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)

    fold_results: list[dict] = []
    all_fold_preds = np.full_like(y_encoded, -1)
    all_fold_true = np.full_like(y_encoded, -1)

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X_all, y_encoded, groups), 1):
        log(f"\n--- Fold {fold_idx}/{n_splits} ---", lines)

        X_traw = X_all[train_idx]
        y_train = y_encoded[train_idx]
        X_valraw = X_all[val_idx]
        y_val = y_encoded[val_idx]

        mean_val = float(np.mean(X_traw))
        std_val = float(np.std(X_traw))
        if std_val > 0:
            X_train = (X_traw - mean_val) / std_val
            X_val = (X_valraw - mean_val) / std_val
        else:
            X_train = X_traw.copy()
            X_val = X_valraw.copy()

        X_train_t = torch.tensor(X_train, dtype=torch.float32).unsqueeze(1)
        y_train_t = torch.tensor(y_train, dtype=torch.long)
        X_val_t = torch.tensor(X_val, dtype=torch.float32).unsqueeze(1)
        y_val_t = torch.tensor(y_val, dtype=torch.long)

        train_counts = Counter(y_train.tolist())
        num_classes = len(classes)

        cw = np.zeros(num_classes, dtype=np.float32)
        for ci in range(num_classes):
            cw[ci] = len(y_train) / (num_classes * max(train_counts.get(ci, 1), 1))
        cw_t = torch.tensor(cw, dtype=torch.float32).to(device)

        sw = [cw[y] for y in y_train]
        sampler = WeightedRandomSampler(sw, num_samples=len(sw), replacement=True)

        train_ds = MelSpectrogramDataset(X_train, y_train, augment=True)
        val_ds = MelSpectrogramDataset(X_val, y_val, augment=False)
        train_loader = DataLoader(train_ds, batch_size=32, sampler=sampler)
        val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)

        model = DangerSoundCNN(num_classes).to(device)
        criterion = nn.CrossEntropyLoss(weight=cw_t)
        optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6,
        )

        best_val_acc = 0.0
        patience_counter = 0
        max_patience = 20
        best_state = None

        for epoch in range(1, 81):
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

            if epoch % 10 == 0 or epoch == 1:
                log(f"  Epoch {epoch:3d} | t_loss={t_loss:.4f} t_acc={t_acc:.4f} "
                    f"| v_loss={v_loss:.4f} v_acc={v_acc:.4f} | lr={lr:.6f}", lines)

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

        model.eval()
        fold_preds = []
        fold_true = []
        with torch.no_grad():
            for bx, by in val_loader:
                bx = bx.to(device)
                out = model(bx)
                fold_preds.extend(out.argmax(1).cpu().numpy())
                fold_true.extend(by.numpy())

        fp = np.array(fold_preds)
        ft = np.array(fold_true)
        all_fold_preds[val_idx] = fp
        all_fold_true[val_idx] = ft

        fold_acc = float(np.mean(fp == ft))
        fold_f1 = float(f1_score(ft, fp, average="macro", zero_division=0))
        log(f"  Fold {fold_idx} val_acc={fold_acc:.4f} macro_f1={fold_f1:.4f}", lines)
        fold_results.append({"fold": fold_idx, "val_acc": fold_acc, "macro_f1": fold_f1, "epochs": epoch})

    valid_mask = all_fold_preds >= 0
    y_true_final = all_fold_true[valid_mask]
    y_pred_final = all_fold_preds[valid_mask]

    log("\n=== PHASE 5: Final Evaluation (CV Aggregated) ===", lines)

    overall_acc = float(np.mean(y_pred_final == y_true_final))
    log(f"\nOverall CV Accuracy: {overall_acc:.4f}", lines)

    avg_val_acc = np.mean([f["val_acc"] for f in fold_results])
    avg_val_f1 = np.mean([f["macro_f1"] for f in fold_results])
    avg_epochs = np.mean([f["epochs"] for f in fold_results])
    log(f"Average fold val_acc: {avg_val_acc:.4f}", lines)
    log(f"Average fold macro_f1: {avg_val_f1:.4f}", lines)
    log(f"Average epochs per fold: {avg_epochs:.1f}", lines)

    report = classification_report(
        y_true_final, y_pred_final, target_names=classes, digits=4, zero_division=0,
    )
    log("\nClassification Report (CV Aggregated):", lines)
    log(report, lines)

    cm = confusion_matrix(y_true_final, y_pred_final)
    log("Confusion Matrix:", lines)
    log(f"Labels: {classes}", lines)
    for i, row in enumerate(cm):
        log(f"  {classes[i]}: {row.tolist()}", lines)

    log("\nPer-class metrics:", lines)
    for i, cls in enumerate(classes):
        mask_i = y_true_final == i
        total_i = int(np.sum(mask_i))
        correct_i = int(np.sum((y_true_final == i) & (y_pred_final == i)))
        recall_i = correct_i / total_i if total_i > 0 else 0

        pred_mask_i = y_pred_final == i
        tp = int(np.sum((y_true_final == i) & (y_pred_final == i)))
        fp = int(np.sum((y_true_final != i) & (y_pred_final == i)))
        precision_i = tp / (tp + fp) if (tp + fp) > 0 else 0
        f1_i = 2 * precision_i * recall_i / (precision_i + recall_i) if (precision_i + recall_i) > 0 else 0

        log(f"  {cls}: precision={precision_i:.4f} recall={recall_i:.4f} f1={f1_i:.4f} support={total_i}", lines)

    plot_confusion_matrix(y_true_final, y_pred_final, classes, OUTPUT_CM_IMAGE)

    log("\n=== PHASE 6: Train Final Model on Full Dataset ===", lines)

    mean_full = float(np.mean(X_all))
    std_full = float(np.std(X_all))
    if std_full > 0:
        X_normalized = (X_all - mean_full) / std_full
    else:
        X_normalized = X_all.copy()

    scaler_info = {"mean": mean_full, "std": std_full}
    with open(OUTPUT_SCALER_PATH, "wb") as f:
        pickle.dump(scaler_info, f)
    log(f"Scaler saved: {OUTPUT_SCALER_PATH}", lines)

    X_full_t = torch.tensor(X_normalized, dtype=torch.float32).unsqueeze(1)
    y_full_t = torch.tensor(y_encoded, dtype=torch.long)

    full_counts = Counter(y_encoded.tolist())
    cw_full = np.zeros(len(classes), dtype=np.float32)
    for ci in range(len(classes)):
        cw_full[ci] = len(y_encoded) / (len(classes) * max(full_counts.get(ci, 1), 1))
    cw_full_t = torch.tensor(cw_full, dtype=torch.float32).to(device)

    sw_full = [cw_full[y] for y in y_encoded]
    sampler_full = WeightedRandomSampler(sw_full, num_samples=len(sw_full), replacement=True)

    full_ds = MelSpectrogramDataset(X_normalized, y_encoded, augment=True)
    full_loader = DataLoader(full_ds, batch_size=32, sampler=sampler_full)

    final_model = DangerSoundCNN(len(classes)).to(device)
    final_optimizer = optim.Adam(final_model.parameters(), lr=1e-3, weight_decay=1e-4)
    final_criterion = nn.CrossEntropyLoss(weight=cw_full_t)

    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    best_final_acc = 0.0
    best_final_state = None
    patience_c = 0

    n_val = int(len(y_encoded) * 0.15)
    val_indices = np.random.RandomState(42).choice(len(y_encoded), n_val, replace=False)
    train_mask = np.ones(len(y_encoded), dtype=bool)
    train_mask[val_indices] = False

    X_trn = X_normalized[train_mask]
    y_trn = y_encoded[train_mask]
    X_vln = X_normalized[val_indices]
    y_vln = y_encoded[val_indices]

    X_trn_t = torch.tensor(X_trn, dtype=torch.float32).unsqueeze(1)
    y_trn_t = torch.tensor(y_trn, dtype=torch.long)
    X_vln_t = torch.tensor(X_vln, dtype=torch.float32).unsqueeze(1)
    y_vln_t = torch.tensor(y_vln, dtype=torch.long)

    trn_counts = Counter(y_trn.tolist())
    cw_trn = np.zeros(len(classes), dtype=np.float32)
    for ci in range(len(classes)):
        cw_trn[ci] = len(y_trn) / (len(classes) * max(trn_counts.get(ci, 1), 1))
    cw_trn_t = torch.tensor(cw_trn, dtype=torch.float32).to(device)

    sw_trn = [cw_trn[y] for y in y_trn]
    sampler_trn = WeightedRandomSampler(sw_trn, num_samples=len(sw_trn), replacement=True)

    trn_ds = MelSpectrogramDataset(X_trn, y_trn, augment=True)
    vln_ds = MelSpectrogramDataset(X_vln, y_vln, augment=False)
    trn_loader = DataLoader(trn_ds, batch_size=32, sampler=sampler_trn)
    vln_loader = DataLoader(vln_ds, batch_size=64, shuffle=False)

    final_optimizer = optim.Adam(final_model.parameters(), lr=1e-3, weight_decay=1e-4)
    final_criterion = nn.CrossEntropyLoss(weight=cw_trn_t)
    final_scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        final_optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6,
    )

    log("Training final model...", lines)
    t_final = time.time()

    for epoch in range(1, 81):
        final_model.train()
        ft_loss = 0.0
        ft_correct = 0
        ft_total = 0
        for bx, by in trn_loader:
            bx, by = bx.to(device), by.to(device)
            final_optimizer.zero_grad()
            out = final_model(bx)
            loss = final_criterion(out, by)
            loss.backward()
            final_optimizer.step()
            ft_loss += loss.item() * bx.size(0)
            ft_correct += out.argmax(1).eq(by).sum().item()
            ft_total += bx.size(0)

        ft_loss /= ft_total
        ft_acc = ft_correct / ft_total

        final_model.eval()
        fv_loss = 0.0
        fv_correct = 0
        fv_total = 0
        with torch.no_grad():
            for bx, by in vln_loader:
                bx, by = bx.to(device), by.to(device)
                out = final_model(bx)
                loss = final_criterion(out, by)
                fv_loss += loss.item() * bx.size(0)
                fv_correct += out.argmax(1).eq(by).sum().item()
                fv_total += by.size(0)

        fv_loss /= fv_total
        fv_acc = fv_correct / fv_total

        final_scheduler.step(fv_loss)
        lr = final_optimizer.param_groups[0]["lr"]

        history["train_loss"].append(ft_loss)
        history["train_acc"].append(ft_acc)
        history["val_loss"].append(fv_loss)
        history["val_acc"].append(fv_acc)

        if epoch % 10 == 0 or epoch == 1:
            elapsed = time.time() - t_final
            log(f"  Epoch {epoch:3d} | t_loss={ft_loss:.4f} t_acc={ft_acc:.4f} "
                f"| v_loss={fv_loss:.4f} v_acc={fv_acc:.4f} | lr={lr:.6f} ({elapsed:.1f}s)", lines)

        if fv_acc > best_final_acc:
            best_final_acc = fv_acc
            best_final_state = {k: v.cpu().clone() for k, v in final_model.state_dict().items()}
            patience_c = 0
        else:
            patience_c += 1

        if patience_c >= 20:
            log(f"  Early stop at epoch {epoch} (best val_acc={best_final_acc:.4f})", lines)
            break

    if best_final_state:
        final_model.load_state_dict(best_final_state)
        final_model.to(device)

    plot_training_curves(history, OUTPUT_CURVES_IMAGE)

    log(f"\nFinal model best val_acc: {best_final_acc:.4f}", lines)
    log(f"Total training time: {time.time() - t_start:.1f}s", lines)

    log("\n=== PHASE 7: Save Model ===", lines)
    torch.save(
        {
            "model_state_dict": final_model.state_dict(),
            "classes": classes,
            "num_classes": len(classes),
            "sample_rate": SAMPLE_RATE,
            "duration": DURATION,
            "n_mels": N_MELS,
            "n_fft": N_FFT,
            "hop_length": HOP_LENGTH,
            "img_height": IMG_HEIGHT,
            "img_width": IMG_WIDTH,
            "scaler_info": scaler_info,
        },
        OUTPUT_MODEL_PATH,
    )
    log(f"Model saved: {OUTPUT_MODEL_PATH}", lines)

    with open(OUTPUT_CLASSES_PATH, "wb") as f:
        pickle.dump({"classes": classes}, f)
    log(f"Classes saved: {OUTPUT_CLASSES_PATH}", lines)

    log("\n" + "=" * 60, lines)
    log("TRAINING COMPLETE", lines)
    log("=" * 60, lines)

    with open(OUTPUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")
    log(f"Report saved: {OUTPUT_REPORT_PATH}", lines)


if __name__ == "__main__":
    main()
