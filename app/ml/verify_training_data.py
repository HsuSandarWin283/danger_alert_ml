from __future__ import annotations

import csv
import pickle
from collections import Counter
from pathlib import Path

import librosa
import numpy as np
import torch

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
CUSTOM_DATASET_DIR = APP_DIR / "dataset"
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

DANGER_EXCLUDED_CATEGORIES = {
    "gunshot", "siren", "chainsaw", "fireworks", "crying_baby",
    "glass_breaking", "car_horn",
}

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}


def log(msg: str) -> None:
    print(msg, flush=True)


def collect_custom_files(folder_name: str) -> list[Path]:
    folder = CUSTOM_DATASET_DIR / folder_name
    if not folder.exists():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )


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


def main() -> None:
    log("=" * 60)
    log("PRE-TRAINING DATA VERIFICATION")
    log("=" * 60)

    # 1. Check paths
    log("\n[1] PATH VERIFICATION")
    log(f"  APP_DIR: {APP_DIR}")
    log(f"  CUSTOM_DATASET_DIR: {CUSTOM_DATASET_DIR}")
    log(f"  ESC50_DIR: {ESC50_DIR}")
    log(f"  META_FILE: {META_FILE}")
    log(f"  META_FILE exists: {META_FILE.exists()}")

    # 2. Check custom dataset folders
    log("\n[2] CUSTOM DATASET FOLDERS")
    for folder_name in ["Gunshot", "Scream", "Accident"]:
        folder = CUSTOM_DATASET_DIR / folder_name
        files = collect_custom_files(folder_name)
        log(f"  {folder_name}: {len(files)} files")
        if len(files) == 0:
            log(f"    WARNING: No files found in {folder}")

    # 3. Check ESC-50 metadata
    log("\n[3] ESC-50 METADATA")
    if not META_FILE.exists():
        log("  ERROR: ESC-50 metadata not found!")
        return

    meta = {}
    with META_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            meta[row["filename"]] = {
                "target": int(row["target"]),
                "category": row["category"],
            }
    log(f"  Total ESC-50 entries: {len(meta)}")

    # Count categories
    cat_counts = Counter(v["category"] for v in meta.values())
    log(f"  Unique categories: {len(cat_counts)}")
    log(f"  Categories with >5 files: {sum(1 for c in cat_counts.values() if c > 5)}")

    # 4. Check excluded categories
    log("\n[4] EXCLUDED CATEGORIES (danger sounds)")
    for cat in sorted(DANGER_EXCLUDED_CATEGORIES):
        count = cat_counts.get(cat, 0)
        log(f"  {cat}: {count} files")

    # 5. Check problematic categories from false positive analysis
    log("\n[5] PROBLEMATIC CATEGORIES (from FP analysis)")
    problematic = [
        "clapping", "breathing", "brushing_teeth", "pig", "rooster",
        "sneezing", "clock_alarm", "snoring", "toilet_flush", "hand_saw"
    ]
    for cat in problematic:
        count = cat_counts.get(cat, 0)
        log(f"  {cat}: {count} files")

    # 6. Check audio loading
    log("\n[6] AUDIO LOADING TEST")
    gunshot_paths = collect_custom_files("Gunshot")
    scream_paths = collect_custom_files("Scream")
    accident_paths = collect_custom_files("Accident")

    test_files = []
    if gunshot_paths:
        test_files.append(("gunshot", gunshot_paths[0]))
    if scream_paths:
        test_files.append(("scream", scream_paths[0]))
    if accident_paths:
        test_files.append(("accident", accident_paths[0]))

    for label, path in test_files:
        sig = load_audio_file(path)
        if sig is not None:
            mel = audio_to_mel(sig)
            log(f"  {label}: loaded OK, shape={sig.shape}, mel shape={mel.shape}, "
                f"min={mel.min():.2f}, max={mel.max():.2f}")
        else:
            log(f"  {label}: FAILED TO LOAD")

    # 7. Check ESC-50 audio files
    log("\n[7] ESC-50 AUDIO FILES")
    esc50_files = list(AUDIO_DIR.glob("*.wav"))
    log(f"  Total ESC-50 audio files: {len(esc50_files)}")

    # Check a few specific files from false positive analysis
    fp_test_files = [
        "4-189838-A-22.wav", "4-189836-A-22.wav", "5-249937-A-22.wav",
        "3-233151-A-2.wav", "1-27724-A-1.wav"
    ]
    for fname in fp_test_files:
        fpath = AUDIO_DIR / fname
        if fpath.exists():
            sig = load_audio_file(fpath)
            if sig is not None:
                mel = audio_to_mel(sig)
                cat = meta.get(fname, {}).get("category", "unknown")
                log(f"  {fname} ({cat}): loaded OK, mel shape={mel.shape}")
            else:
                log(f"  {fname}: FAILED TO LOAD")
        else:
            log(f"  {fname}: FILE NOT FOUND")

    # 8. Summary
    log("\n[8] SUMMARY")
    total_danger = len(gunshot_paths) + len(scream_paths) + len(accident_paths)
    log(f"  Custom danger files: {total_danger}")
    log(f"  ESC-50 total files: {len(meta)}")
    log(f"  ESC-50 excluded (danger): {sum(cat_counts.get(c, 0) for c in DANGER_EXCLUDED_CATEGORIES)}")
    log(f"  ESC-50 problematic FPs: {sum(cat_counts.get(c, 0) for c in problematic)}")

    # Calculate available normal files (excluding danger and problematic)
    normal_candidates = [
        cat for cat in cat_counts.keys()
        if cat not in DANGER_EXCLUDED_CATEGORIES and cat not in problematic
    ]
    normal_available = sum(cat_counts.get(c, 0) for c in normal_candidates)
    log(f"  ESC-50 clean normal candidates: {len(normal_candidates)} categories, {normal_available} files")

    log("\n[9] READY FOR TRAINING?")
    if len(gunshot_paths) > 0 and len(scream_paths) > 0 and len(accident_paths) > 0:
        if normal_available >= 400:
            log("  YES - Data looks good for retraining")
            log(f"  Recommended normal samples: {min(normal_available, 700)}")
        else:
            log("  WARNING: Not enough clean normal files")
    else:
        log("  NO - Missing custom dataset files")


if __name__ == "__main__":
    main()
