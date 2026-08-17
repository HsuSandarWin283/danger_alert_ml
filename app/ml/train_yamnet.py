from __future__ import annotations

import csv
import os
import pickle
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import librosa
import numpy as np
import tensorflow as tf
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
CUSTOM_DATASET_DIR = APP_DIR / "dataset"
META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"

YAMNET_MODEL_PATH = ML_DIR / "yamnet_classifier.pkl"
REPORT_PATH = ML_DIR / "yamnet_training_report.txt"

YAMNET_MODEL_DIR = ML_DIR / "yamnet_model"
YAMNET_SAMPLE_RATE = 16000
CLIP_DURATION = 3.0
TARGET_SAMPLES = int(YAMNET_SAMPLE_RATE * CLIP_DURATION)
CLIP_DURATION = 3.0
TARGET_SAMPLES = int(YAMNET_SAMPLE_RATE * CLIP_DURATION)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac"}

CUSTOM_CLASS_FOLDERS = {
    "gunshot": "gun_shot",
    "scream": "scream",
}

ACCIDENT_CLASS_FOLDER = "accident"

ESC50_TARGET_CATEGORIES = {
    "glass_breaking": "glass_break",
}

ESC50_EXCLUDED_CATEGORIES = {
    "glass_breaking",
    "siren",
    "car_horn",
    "chainsaw",
    "fireworks",
    "crying_baby",
}

BG_CATEGORIES = [
    "rain", "wind", "engine", "thunderstorm", "sea_waves",
    "train", "helicopter", "airplane", "insects", "crickets",
    "chirping_birds", "vacuum_cleaner", "washing_machine",
    "crow", "dog", "cat", "footsteps", "clock_tick",
]

random_state = 42


def log(msg, lines=None):
    print(msg, flush=True)
    if lines is not None:
        lines.append(msg)


def load_audio_16k(path: Path) -> np.ndarray | None:
    try:
        signal, _ = librosa.load(str(path), sr=YAMNET_SAMPLE_RATE, mono=True, duration=CLIP_DURATION)
        if len(signal) < TARGET_SAMPLES:
            signal = np.pad(signal, (0, TARGET_SAMPLES - len(signal)))
        else:
            signal = signal[:TARGET_SAMPLES]
        return signal.astype(np.float32)
    except Exception:
        return None


def load_yamnet():
    return tf.saved_model.load(str(YAMNET_MODEL_DIR))


def extract_yamnet_embedding(yamnet, signal: np.ndarray) -> np.ndarray:
    waveform = tf.convert_to_tensor(signal, dtype=tf.float32)
    scores, embeddings, spectrogram = yamnet(waveform)
    embedding = tf.reduce_mean(embeddings, axis=0).numpy()
    return embedding.astype(np.float32)


def load_esc50_samples() -> list[dict]:
    samples = []
    skipped = Counter()

    if not META_FILE.exists():
        raise FileNotFoundError(f"ESC-50 metadata not found: {META_FILE}")

    with META_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = row["category"]
            filename = row["filename"]
            audio_path = AUDIO_DIR / filename

            if not audio_path.exists():
                skipped["missing_audio"] += 1
                continue

            if category in ESC50_TARGET_CATEGORIES:
                label = ESC50_TARGET_CATEGORIES[category]
            elif category in ESC50_EXCLUDED_CATEGORIES:
                skipped[f"excluded:{category}"] += 1
                continue
            else:
                label = "normal"

            samples.append({
                "path": audio_path,
                "label": label,
                "group": f"esc50:{filename}",
                "origin": f"esc50:{category}",
            })

    log("ESC-50 skipped categories/files:")
    for key, count in sorted(skipped.items()):
        log(f"  {key}: {count}")

    return samples


def load_custom_samples() -> list[dict]:
    samples = []
    missing = []

    for label, folder_name in CUSTOM_CLASS_FOLDERS.items():
        folder = CUSTOM_DATASET_DIR / folder_name
        if not folder.exists():
            missing.append(str(folder))
            continue

        for audio_path in sorted(folder.iterdir()):
            if audio_path.is_file() and audio_path.suffix.lower() in AUDIO_EXTENSIONS:
                samples.append({
                    "path": audio_path,
                    "label": label,
                    "group": f"custom:{folder_name}:{audio_path.stem}",
                    "origin": f"custom:{folder_name}",
                })

    accident_dir = CUSTOM_DATASET_DIR / ACCIDENT_CLASS_FOLDER
    if accident_dir.exists():
        for sub in accident_dir.iterdir():
            if sub.is_dir():
                for audio_path in sorted(sub.iterdir()):
                    if audio_path.is_file() and audio_path.suffix.lower() in AUDIO_EXTENSIONS:
                        samples.append({
                            "path": audio_path,
                            "label": "accident",
                            "group": f"custom:accident:{sub.name.lower()}:{audio_path.stem}",
                            "origin": f"custom:accident:{sub.name.lower()}",
                        })
    else:
        missing.append(str(accident_dir))

    if missing:
        log("Missing custom dataset folders:")
        for folder in missing:
            log(f"  {folder}")

    return samples


def make_pipeline():
    from sklearn.pipeline import Pipeline
    from sklearn.linear_model import LogisticRegression
    return Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=2000, class_weight="balanced", n_jobs=-1)),
    ])


def main() -> None:
    lines = []
    t_start = time.time()

    log("=" * 60, lines)
    log("YAMNet + sklearn CLASSIFIER TRAINING", lines)
    log("=" * 60, lines)

    esc50_samples = load_esc50_samples()
    custom_samples = load_custom_samples()
    all_samples = esc50_samples + custom_samples

    log(f"ESC-50 samples loaded: {len(esc50_samples)}", lines)
    log(f"Custom samples loaded: {len(custom_samples)}", lines)
    log(f"Total samples before filtering: {len(all_samples)}", lines)

    counts = Counter(s["label"] for s in all_samples)
    total = len(all_samples)
    log("Class distribution before feature extraction:")
    for label in sorted(counts):
        log(f"  {label}: {counts[label]} ({counts[label] / total * 100:.2f}%)")

    log("\n=== PHASE 1: Load YAMNet ===", lines)
    yamnet = load_yamnet()
    log("YAMNet loaded.", lines)

    log("\n=== PHASE 2: Extract YAMNet Embeddings ===", lines)
    embeddings = []
    labels = []
    groups = []
    failed = []

    for idx, sample in enumerate(all_samples, start=1):
        signal = load_audio_16k(sample["path"])
        if signal is None:
            failed.append(f"{sample['path']} ({sample['label']})")
            continue

        try:
            emb = extract_yamnet_embedding(yamnet, signal)
            embeddings.append(emb)
            labels.append(sample["label"])
            groups.append(sample["group"])
        except Exception as exc:
            failed.append(f"{sample['path']} ({sample['label']}): {exc}")

        if idx % 100 == 0 or idx == len(all_samples):
            log(f"  Processed {idx}/{len(all_samples)}", lines)

    if failed:
        log(f"  Failed embeddings: {len(failed)} files")
        for item in failed[:20]:
            log(f"    {item}")
        if len(failed) > 20:
            log(f"    ... {len(failed) - 20} more")
    else:
        log("  Failed embeddings: 0 files")

    if not embeddings:
        raise RuntimeError("No valid embeddings extracted.")

    X = np.vstack(embeddings).astype(np.float32)
    y = np.array(labels)
    groups = np.array(groups)
    log(f"  Embedding shape: {X.shape}", lines)

    log("\n=== PHASE 3: Train sklearn Classifier ===", lines)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    labels_unique = sorted(set(y))
    label_encoder = {label: idx for idx, label in enumerate(labels_unique)}
    y_encoded = np.array([label_encoder[l] for l in y])

    min_groups = min(len(set(groups[y == label])) for label in labels_unique)
    n_splits = min(5, min_groups)
    if n_splits < 2:
        n_splits = 2

    cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)
    y_pred = np.empty_like(y_encoded)

    for fold, (train_idx, test_idx) in enumerate(cv.split(X_scaled, y_encoded, groups), start=1):
        pipeline = make_pipeline()
        pipeline.fit(X_scaled[train_idx], y_encoded[train_idx])
        y_pred[test_idx] = pipeline.predict(X_scaled[test_idx])
        log(f"  Fold {fold}/{n_splits} done", lines)

    log("\nConfusion matrix:", lines)
    cm = confusion_matrix(y_encoded, y_pred, labels=np.arange(len(labels_unique)))
    log("Labels: " + ", ".join(labels_unique), lines)
    log(cm.astype(int).tolist(), lines)

    log("\nClassification report:", lines)
    report = classification_report(
        y_encoded, y_pred,
        target_names=labels_unique,
        zero_division=0,
        digits=4,
    )
    log(report, lines)

    final_pipeline = make_pipeline()
    final_pipeline.fit(X_scaled, y_encoded)

    payload = {
        "pipeline": final_pipeline,
        "scaler": scaler,
        "classes": labels_unique,
        "embedding_dim": X.shape[1],
        "sample_rate": YAMNET_SAMPLE_RATE,
        "duration": CLIP_DURATION,
        "feature_version": "yamnet_1024_avg_v1",
        "training_label_counts": dict(Counter(y)),
        "failed_files": failed,
    }

    if YAMNET_MODEL_PATH.exists():
        YAMNET_MODEL_PATH.unlink()

    with YAMNET_MODEL_PATH.open("wb") as f:
        pickle.dump(payload, f)

    log(f"\nModel saved to: {YAMNET_MODEL_PATH}", lines)
    log(f"Total training time: {time.time() - t_start:.1f}s", lines)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(str(line) for line in lines))
        f.write("\n")
    log(f"Report saved: {REPORT_PATH}", lines)


def make_pipeline():
    from sklearn.pipeline import Pipeline
    from sklearn.linear_model import LogisticRegression
    return Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=2000, class_weight="balanced", n_jobs=-1)),
    ])


if __name__ == "__main__":
    main()
