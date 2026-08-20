from __future__ import annotations

import csv
import os
import pickle
import random
import time
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

try:
    import librosa
except ImportError:
    raise ImportError("librosa is required: pip install librosa")

_FFMPEG_DIR = Path(r"C:\Users\Hsu Sandar Win\AppData\Local\Python\ffmpeg\ffmpeg-9.0-essentials_build\bin")
if _FFMPEG_DIR.exists():
    os.environ["PATH"] = str(_FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")
# On Colab / Linux, ffmpeg is already in PATH

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
    CUSTOM_DATASET_DIR = project_root / 'dataset'

    for esc50_candidate in [
        CUSTOM_DATASET_DIR / 'ESC-50',
        APP_DIR / 'database' / 'ESC-50-master',
    ]:
        if esc50_candidate.exists():
            ESC50_DIR = esc50_candidate
            break
    else:
        ESC50_DIR = CUSTOM_DATASET_DIR / 'ESC-50'
else:
    APP_DIR = Path(__file__).resolve().parents[1]
    ML_DIR = Path(__file__).resolve().parent
    CUSTOM_DATASET_DIR = APP_DIR / "dataset"
    ESC50_DIR = APP_DIR / "database" / "ESC-50-master"

META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"

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

matplotlib_available = False
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

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
OUTPUT_REPORT_PATH = ML_DIR / "training_report.txt"
OUTPUT_CM_IMAGE = ML_DIR / "confusion_matrix.png"
OUTPUT_CURVES_IMAGE = ML_DIR / "training_curves.png"

SAMPLE_RATE = 22050
DURATION = 3.0
N_MELS = 128
N_FFT = 2048
HOP_LENGTH = 512
IMG_HEIGHT = 128
IMG_WIDTH = 128
TARGET_LENGTH = int(SAMPLE_RATE * DURATION)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

BG_CATEGORIES = [
    "rain", "wind", "engine", "thunderstorm", "sea_waves",
    "train", "helicopter", "airplane", "insects", "crickets",
    "chirping_birds", "vacuum_cleaner", "washing_machine",
    "crow", "dog", "cat", "footsteps", "clock_tick",
]

ACCIDENT_SOUND_CATEGORIES = ["glass_breaking", "car_horn"]
DANGER_EXCLUDED_CATEGORIES = {
    "gunshot", "siren", "chainsaw", "fireworks", "crying_baby",
    "glass_breaking", "car_horn",
}

NORMAL_SAMPLE_COUNT = 400
MIX_PROB = 0.7
SNR_RANGE = (5.0, 20.0)
VOLUME_RANGE = (0.8, 1.2)

random.seed(42)
np.random.seed(42)
torch.manual_seed(42)


def log(msg: str, lines: list[str] | None = None) -> None:
    print(msg, flush=True)
    if lines is not None:
        lines.append(msg)


def load_audio_file(path: Path) -> np.ndarray | None:
    try:
        signal, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True, duration=DURATION, res_type="soxr_hq")
        if len(signal) < TARGET_LENGTH:
            signal = np.pad(signal, (0, TARGET_LENGTH - len(signal)))
        else:
            signal = signal[:TARGET_LENGTH]

        peak = np.max(np.abs(signal))
        if peak > 0:
            signal = signal / peak * 0.95

        return signal
    except Exception as exc:
        print(f"FAILED LOAD: {path} | {type(exc).__name__}: {exc}", flush=True)
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
    bg_chunk = bg[safe_offset: safe_offset + len(fg)].copy()

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


def select_normal_files(esc50: dict[str, list[Path]], target_count: int = NORMAL_SAMPLE_COUNT) -> list[Path]:
    normal_paths: list[Path] = []
    for cat, files in esc50.items():
        if cat not in DANGER_EXCLUDED_CATEGORIES and cat not in BG_CATEGORIES:
            normal_paths.extend(files)
    random.shuffle(normal_paths)
    sampled = normal_paths[:target_count]
    return sampled


class OnTheFlyAudioDataset(Dataset):
    def __init__(
        self,
        data: list[tuple[np.ndarray, str, str]],
        bg_signals: list[np.ndarray],
        accident_signals: dict[str, list[np.ndarray]],
        classes: list[str],
        class_to_idx: dict[str, int],
        mean_val: float,
        std_val: float,
        augment: bool = False,
        mix_prob: float = MIX_PROB,
    ):
        self.data = data
        self.bg_signals = bg_signals
        self.accident_signals = accident_signals
        self.classes = classes
        self.class_to_idx = class_to_idx
        self.mean_val = mean_val
        self.std_val = std_val
        self.augment = augment
        self.mix_prob = mix_prob

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        signal, label, src = self.data[idx]

        if self.augment:
            signal = self._augment(signal, label)

        mel = audio_to_mel(signal)
        mel = (mel - self.mean_val) / self.std_val
        mel_tensor = torch.tensor(mel, dtype=torch.float32).unsqueeze(0)
        label_idx = self.class_to_idx[label]

        return mel_tensor, torch.tensor(label_idx, dtype=torch.long)

    def _augment(self, signal: np.ndarray, label: str) -> np.ndarray:
        if random.random() < 0.3:
            signal = signal * random.uniform(0.8, 1.2)

        if random.random() < 0.3:
            shift = random.randint(-2205, 2205)
            signal = np.roll(signal, shift)
            if shift > 0:
                signal[:shift] = 0
            else:
                signal[shift:] = 0

        if label != "normal" and random.random() < self.mix_prob:
            if self.bg_signals:
                bg_sig = random.choice(self.bg_signals)
                snr_db = random.uniform(*SNR_RANGE)
                vol = random.uniform(*VOLUME_RANGE)
                offset = random_bg_offset(len(bg_sig))
                signal = mix_two_signals(signal, bg_sig, snr_db, vol, offset)

        return signal


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
    mel_db = np.clip(mel_db, -80.0, 0.0)
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


def main() -> None:
    lines: list[str] = []
    t_start = time.time()

    log("=" * 60, lines)
    log("DANGER SOUND CNN TRAINING (PyTorch)", lines)
    log("Original Dataset + On-The-Fly Augmentation", lines)
    log("=" * 60, lines)

    esc50 = load_esc50_by_category()
    log(f"ESC-50 categories loaded: {len(esc50)}", lines)

    gunshot_paths = collect_custom_files("Gunshot")
    scream_paths = collect_custom_files("Scream")
    accident_paths = collect_custom_files("Accident")

    log(f"Gunshot files: {len(gunshot_paths)}", lines)
    log(f"Scream files: {len(scream_paths)}", lines)
    log(f"Accident files: {len(accident_paths)}", lines)

    normal_paths = select_normal_files(esc50, NORMAL_SAMPLE_COUNT)
    log(f"Selected Normal files (ESC-50): {len(normal_paths)}", lines)

    bg_pool: list[Path] = []
    for cat in BG_CATEGORIES:
        bg_pool.extend(esc50.get(cat, []))
    log(f"Background pool: {len(bg_pool)} files ({len(BG_CATEGORIES)} categories)", lines)

    accident_sound_pool: list[Path] = []
    for cat in ACCIDENT_SOUND_CATEGORIES:
        accident_sound_pool.extend(esc50.get(cat, []))
    log(f"Accident sound pool (glass_breaking + car_horn): {len(accident_sound_pool)} files", lines)

    log("\n=== PHASE 1: Load original audio into memory ===", lines)

    def load_batch(paths: list[Path], label: str) -> list[tuple[np.ndarray, str, str]]:
        results: list[tuple[np.ndarray, str, str]] = []
        t0 = time.time()
        for i, p in enumerate(paths):
            sig = load_audio_file(p)
            if sig is not None:
                results.append((sig, label, str(p)))
            if (i + 1) % 100 == 0:
                log(f"  [{label}] {i + 1}/{len(paths)} ({time.time() - t0:.1f}s)", lines)
        log(f"  [{label}] loaded {len(results)}/{len(paths)} ({time.time() - t0:.1f}s)", lines)
        return results

    gunshot_originals = load_batch(gunshot_paths, "gunshot")
    scream_originals = load_batch(scream_paths, "scream")
    accident_originals = load_batch(accident_paths, "accident")
    normal_originals = load_batch(normal_paths, "normal")

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

    bg_flat: list[np.ndarray] = []
    for sigs in bg_loaded.values():
        bg_flat.extend(sigs)
    log(f"  Total background signals: {len(bg_flat)}", lines)

    log("\n=== DATASET VALIDATION ===", lines)
    log(f"Resolved paths:", lines)
    log(f"  APP_DIR: {APP_DIR}", lines)
    log(f"  ML_DIR: {ML_DIR}", lines)
    log(f"  CUSTOM_DATASET_DIR: {CUSTOM_DATASET_DIR}", lines)
    log(f"  ESC50_DIR: {ESC50_DIR}", lines)
    log(f"  META_FILE: {META_FILE}", lines)
    log(f"  META_FILE exists: {META_FILE.exists()}", lines)

    total_danger = len(gunshot_originals) + len(scream_originals) + len(accident_originals)
    total_originals = total_danger + len(normal_originals)

    log(f"\nDataset counts:", lines)
    log(f"  Gunshot: {len(gunshot_originals)}", lines)
    log(f"  Scream: {len(scream_originals)}", lines)
    log(f"  Accident: {len(accident_originals)}", lines)
    log(f"  Normal: {len(normal_originals)}", lines)
    log(f"  Total danger originals: {total_danger}", lines)
    log(f"  Total training originals: {total_originals}", lines)

    if len(gunshot_originals) == 0 or len(scream_originals) == 0 or len(accident_originals) == 0:
        log("\nERROR: Dataset not found!", lines)
        log(f"Expected paths:", lines)
        log(f"  Gunshot: {CUSTOM_DATASET_DIR / 'Gunshot'}", lines)
        log(f"  Scream: {CUSTOM_DATASET_DIR / 'Scream'}", lines)
        log(f"  Accident: {CUSTOM_DATASET_DIR / 'Accident'}", lines)
        log("Please check the dataset paths and folder names.", lines)
        raise FileNotFoundError("Dataset folders not found. Check paths above.")

    log("\n=== PHASE 2: Train/Validation/Test Split ===", lines)

    all_originals = gunshot_originals + scream_originals + accident_originals + normal_originals
    random.shuffle(all_originals)

    n_total = len(all_originals)
    n_train = int(n_total * 0.8)
    n_val = int(n_total * 0.1)
    n_test = n_total - n_train - n_val

    train_data = all_originals[:n_train]
    val_data = all_originals[n_train: n_train + n_val]
    test_data = all_originals[n_train + n_val:]

    log(f"Total original files: {n_total}", lines)
    log(f"Train: {len(train_data)} files", lines)
    log(f"Validation: {len(val_data)} files", lines)
    log(f"Test: {len(test_data)} files", lines)

    for split_name, split_data in [("Train", train_data), ("Validation", val_data), ("Test", test_data)]:
        counts = Counter(d[1] for d in split_data)
        log(f"  {split_name} distribution: {dict(counts)}", lines)

    log("\n=== PHASE 3: Compute Normalization Statistics ===", lines)

    classes = sorted(set(d[1] for d in all_originals))
    class_to_idx = {c: i for i, c in enumerate(classes)}
    log(f"Classes: {classes}", lines)

    t_norm = time.time()
    train_mels = []
    for sig, lbl, src in train_data:
        mel = audio_to_mel(sig)
        train_mels.append(mel)
    train_mels = np.array(train_mels, dtype=np.float32)
    mean_val = float(np.mean(train_mels))
    std_val = float(np.std(train_mels))
    if std_val < 1e-8:
        std_val = 1.0
    log(f"  Train mel mean: {mean_val:.4f}, std: {std_val:.4f} ({time.time() - t_norm:.1f}s)", lines)

    scaler_info = {"mean": mean_val, "std": std_val}
    with open(OUTPUT_SCALER_PATH, "wb") as f:
        pickle.dump(scaler_info, f)
    log(f"Scaler saved: {OUTPUT_SCALER_PATH}", lines)

    log("\n=== PHASE 4: Create Datasets ===", lines)

    train_dataset = OnTheFlyAudioDataset(
        train_data, bg_flat, accident_sound_loaded,
        classes, class_to_idx, mean_val, std_val,
        augment=True, mix_prob=MIX_PROB,
    )
    val_dataset = OnTheFlyAudioDataset(
        val_data, bg_flat, accident_sound_loaded,
        classes, class_to_idx, mean_val, std_val,
        augment=False, mix_prob=0.0,
    )
    test_dataset = OnTheFlyAudioDataset(
        test_data, bg_flat, accident_sound_loaded,
        classes, class_to_idx, mean_val, std_val,
        augment=False, mix_prob=0.0,
    )

    log(f"Train dataset size: {len(train_dataset)}", lines)
    log(f"Validation dataset size: {len(val_dataset)}", lines)
    log(f"Test dataset size: {len(test_dataset)}", lines)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log(f"Device: {device}", lines)

    train_counts = Counter(d[1] for d in train_data)
    num_classes = len(classes)

    cw = np.zeros(num_classes, dtype=np.float32)
    for ci in range(num_classes):
        cw[ci] = len(train_data) / (num_classes * max(train_counts.get(classes[ci], 1), 1))
    cw_t = torch.tensor(cw, dtype=torch.float32).to(device)
    log(f"Class weights: {dict(zip(classes, cw.tolist()))}", lines)

    sw = [cw[class_to_idx[d[1]]] for d in train_data]
    sampler = WeightedRandomSampler(sw, num_samples=len(sw), replacement=True)

    train_loader = DataLoader(train_dataset, batch_size=32, sampler=sampler, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=64, shuffle=False, num_workers=0)

    log("\n=== PHASE 5: Cross-Validation Training ===", lines)

    from sklearn.model_selection import StratifiedGroupKFold

    def get_group(src: str) -> str:
        return Path(src).name

    groups = np.array([get_group(d[2]) for d in train_data])
    y_train = np.array([class_to_idx[d[1]] for d in train_data])

    unique_per_class = {}
    for cls_idx in range(num_classes):
        mask = y_train == cls_idx
        unique_per_class[cls_idx] = len(set(groups[mask]))

    min_groups = min(unique_per_class.values())
    n_splits = min(5, min_groups)
    if n_splits < 2:
        n_splits = 2
    log(f"StratifiedGroupKFold: {n_splits} splits", lines)
    log(f"Unique groups per class: {dict((classes[k], v) for k, v in unique_per_class.items())}", lines)

    skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)

    fold_results = []
    all_fold_preds = np.full_like(y_train, -1)
    all_fold_true = np.full_like(y_train, -1)

    for fold_idx, (tr_idx, vl_idx) in enumerate(skf.split(train_data, y_train, groups), 1):
        log(f"\n--- Fold {fold_idx}/{n_splits} ---", lines)

        fold_train = [train_data[i] for i in tr_idx]
        fold_val = [train_data[i] for i in vl_idx]

        fold_train_ds = OnTheFlyAudioDataset(
            fold_train, bg_flat, accident_sound_loaded,
            classes, class_to_idx, mean_val, std_val,
            augment=True, mix_prob=MIX_PROB,
        )
        fold_val_ds = OnTheFlyAudioDataset(
            fold_val, bg_flat, accident_sound_loaded,
            classes, class_to_idx, mean_val, std_val,
            augment=False, mix_prob=0.0,
        )

        fold_train_loader = DataLoader(fold_train_ds, batch_size=32, sampler=WeightedRandomSampler(
            [cw[class_to_idx[d[1]]] for d in fold_train], num_samples=len(fold_train), replacement=True
        ), num_workers=0)
        fold_val_loader = DataLoader(fold_val_ds, batch_size=64, shuffle=False, num_workers=0)

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
            for bx, by in fold_train_loader:
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
                for bx, by in fold_val_loader:
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
            for bx, by in fold_val_loader:
                bx = bx.to(device)
                out = model(bx)
                fold_preds.extend(out.argmax(1).cpu().numpy())
                fold_true.extend(by.numpy())

        fp = np.array(fold_preds)
        ft = np.array(fold_true)
        all_fold_preds[vl_idx] = fp
        all_fold_true[vl_idx] = ft

        fold_acc = float(np.mean(fp == ft))
        fold_f1 = float(f1_score(ft, fp, average="macro", zero_division=0))
        log(f"  Fold {fold_idx} val_acc={fold_acc:.4f} macro_f1={fold_f1:.4f}", lines)
        fold_results.append({"fold": fold_idx, "val_acc": fold_acc, "macro_f1": fold_f1, "epochs": epoch})

    valid_mask = all_fold_preds >= 0
    y_true_final = all_fold_true[valid_mask]
    y_pred_final = all_fold_preds[valid_mask]

    log("\n=== PHASE 6: Cross-Validation Evaluation ===", lines)

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

    log("\nPer-class metrics (CV):", lines)
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

    log("\n=== PHASE 7: Train Final Model on Full Training Set ===", lines)

    full_train_ds = OnTheFlyAudioDataset(
        train_data, bg_flat, accident_sound_loaded,
        classes, class_to_idx, mean_val, std_val,
        augment=True, mix_prob=MIX_PROB,
    )
    full_train_loader = DataLoader(full_train_ds, batch_size=32, sampler=sampler, num_workers=0)

    final_model = DangerSoundCNN(num_classes).to(device)
    final_optimizer = optim.Adam(final_model.parameters(), lr=1e-3, weight_decay=1e-4)
    final_criterion = nn.CrossEntropyLoss(weight=cw_t)
    final_scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        final_optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6,
    )

    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    best_final_acc = 0.0
    best_final_state = None
    patience_c = 0

    for epoch in range(1, 81):
        final_model.train()
        ft_loss = 0.0
        ft_correct = 0
        ft_total = 0
        for bx, by in full_train_loader:
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
            for bx, by in val_loader:
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
            log(f"  Epoch {epoch:3d} | t_loss={ft_loss:.4f} t_acc={ft_acc:.4f} "
                f"| v_loss={fv_loss:.4f} v_acc={fv_acc:.4f} | lr={lr:.6f}", lines)

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

    log("\n=== PHASE 8: Final Test Evaluation ===", lines)

    test_results = evaluate_model(final_model, test_loader, device, classes)
    log(f"Test loss: {test_results['loss']:.4f}", lines)
    log(f"Test accuracy: {test_results['accuracy']:.4f}", lines)
    log("\nClassification Report (Test):", lines)
    log(test_results["report"], lines)
    log("Confusion Matrix (Test):", lines)
    log(f"Labels: {classes}", lines)
    for i, row in enumerate(test_results["confusion_matrix"]):
        log(f"  {classes[i]}: {row.tolist()}", lines)
    log("\nPer-class metrics (Test):", lines)
    for cls, metrics in test_results["per_class"].items():
        log(f"  {cls}: precision={metrics['precision']:.4f} recall={metrics['recall']:.4f} "
            f"f1={metrics['f1']:.4f} support={metrics['support']}", lines)

    log("\n=== PHASE 9: Save Model ===", lines)
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

    lines.append(f"\nDataset Summary:")
    lines.append(f"  Gunshot original: {len(gunshot_originals)}")
    lines.append(f"  Scream original: {len(scream_originals)}")
    lines.append(f"  Accident original: {len(accident_originals)}")
    lines.append(f"  Normal original: {len(normal_originals)}")
    lines.append(f"  Train: {len(train_data)}")
    lines.append(f"  Validation: {len(val_data)}")
    lines.append(f"  Test: {len(test_data)}")
    lines.append(f"\nAugmentation: on-the-fly only (no permanent augmented files)")
    lines.append(f"  Mix probability: {MIX_PROB}")
    lines.append(f"  SNR range: {SNR_RANGE}")
    lines.append(f"  Volume range: {VOLUME_RANGE}")

    with open(OUTPUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")
    log(f"Report saved: {OUTPUT_REPORT_PATH}", lines)


if __name__ == "__main__":
    main()
