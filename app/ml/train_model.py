from __future__ import annotations

import csv
import os
import pickle
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

try:
    from .features import FEATURE_VERSION, extract_features
except ImportError:
    from features import FEATURE_VERSION, extract_features

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
CUSTOM_DATASET_DIR = APP_DIR / "dataset"
META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"
MODEL_PATH = ML_DIR / "danger_sound_model.pkl"
REPORT_PATH = ML_DIR / "training_report.txt"

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac"}
CUSTOM_CLASS_FOLDERS = {
    "gunshot": "gun_shot",
    "scream": "scream",
}
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

SAMPLE_RATE = 22050


@dataclass
class AudioSample:
    path: Path
    label: str
    group: str
    origin: str


def is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def custom_group_key(path: Path) -> str:
    stem = path.stem
    folder = path.parent.name

    if folder == "gun_shot":
        parts = stem.split("-")
        if len(parts) >= 2:
            return f"custom:gun_shot:{parts[0]}-{parts[1]}"

    return f"custom:{folder}:{stem}"


def load_esc50_samples() -> list[AudioSample]:
    samples: list[AudioSample] = []
    skipped: Counter[str] = Counter()

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

            samples.append(
                AudioSample(
                    path=audio_path,
                    label=label,
                    group=f"esc50:{filename}",
                    origin=f"esc50:{category}",
                )
            )

    print("ESC-50 skipped categories/files:")
    for key, count in sorted(skipped.items()):
        print(f"  {key}: {count}")

    return samples


def load_custom_samples() -> list[AudioSample]:
    samples: list[AudioSample] = []
    missing: list[str] = []

    for label, folder_name in CUSTOM_CLASS_FOLDERS.items():
        folder = CUSTOM_DATASET_DIR / folder_name
        if not folder.exists():
            missing.append(str(folder))
            continue

        for audio_path in sorted(folder.iterdir()):
            if not is_audio_file(audio_path):
                continue
            samples.append(
                AudioSample(
                    path=audio_path,
                    label=label,
                    group=custom_group_key(audio_path),
                    origin=f"custom:{folder_name}",
                )
            )

    if missing:
        print("Missing custom dataset folders:")
        for folder in missing:
            print(f"  {folder}")

    return samples


def log_class_distribution(samples: list[AudioSample], log) -> None:
    counts = Counter(sample.label for sample in samples)
    total = len(samples)

    log("Class distribution before feature extraction:")
    for label in sorted(counts):
        count = counts[label]
        log(f"  {label}: {count} ({count / total * 100:.2f}%)")

    if not counts:
        log("  WARNING: No samples found.")
        return

    min_count = min(counts.values())
    max_count = max(counts.values())
    imbalance_ratio = max_count / min_count if min_count else 0
    log(f"  Max/min class ratio: {imbalance_ratio:.2f}x")

    if imbalance_ratio > 10:
        log("  WARNING: Class imbalance is high. Balanced class weighting is enabled.")


def log_group_summary(labels: np.ndarray, groups: np.ndarray, log) -> None:
    label_groups: dict[str, set[str]] = defaultdict(set)
    label_samples = Counter(labels)

    for label, group in zip(labels, groups):
        label_groups[str(label)].add(str(group))

    duplicate_groups = [group for group, count in Counter(groups).items() if count > 1]

    log("Group leakage summary:")
    log(f"  Valid samples: {len(labels)}")
    log(f"  Unique groups: {len(set(groups))}")
    log(f"  Groups with multiple clips: {len(duplicate_groups)}")

    for label in sorted(label_samples):
        log(
            f"  {label}: {label_samples[label]} samples, "
            f"{len(label_groups[label])} groups"
        )

    if duplicate_groups:
        log("  NOTE: Multi-clip groups are present and group-aware splitting is used.")


def extract_dataset_features(samples: list[AudioSample], log) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    features: list[np.ndarray] = []
    labels: list[str] = []
    groups: list[str] = []
    failed: list[str] = []

    log(f"Extracting features from {len(samples)} samples...")

    for index, sample in enumerate(samples, start=1):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sample_features = extract_features(
                    str(sample.path),
                    sr=SAMPLE_RATE,
                )
            features.append(sample_features)
            labels.append(sample.label)
            groups.append(sample.group)
        except Exception as exc:
            failed.append(f"{sample.path} ({sample.label}): {exc}")

        if index % 100 == 0 or index == len(samples):
            log(f"  Processed {index}/{len(samples)} samples")

    if failed:
        log(f"  Failed feature extraction: {len(failed)} files")
        for item in failed[:20]:
            log(f"    {item}")
        if len(failed) > 20:
            log(f"    ... {len(failed) - 20} more")
    else:
        log("  Failed feature extraction: 0 files")

    if not features:
        raise RuntimeError("No valid features were extracted. Check audio paths and formats.")

    log(f"  Feature vector size: {features[0].shape[0]}")

    return np.vstack(features), np.array(labels), np.array(groups), failed


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "model",
                ExtraTreesClassifier(
                    n_estimators=200,
                    class_weight="balanced_subsample",
                    random_state=42,
                    n_jobs=-1,
                    max_features="sqrt",
                    min_samples_leaf=1,
                ),
            ),
        ]
    )


def evaluate_model(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    log,
) -> tuple[Pipeline, LabelEncoder, np.ndarray]:
    labels = np.array(sorted(set(y)))
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    min_groups_per_class = min(
        len(set(groups[y == label])) for label in labels
    )
    n_splits = min(5, min_groups_per_class)

    if n_splits < 2:
        raise RuntimeError("Not enough groups per class for group-aware cross-validation.")

    cv = StratifiedGroupKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=42,
    )
    y_pred = np.empty_like(y_encoded)

    log(f"Evaluating with {n_splits}-fold StratifiedGroupKFold...")

    for fold, (train_idx, test_idx) in enumerate(cv.split(X, y_encoded, groups), start=1):
        fold_counts = Counter(y[test_idx])
        log(f"  Fold {fold} test counts: {dict(sorted(fold_counts.items()))}")

        pipeline = build_pipeline()
        pipeline.fit(X[train_idx], y_encoded[train_idx])
        y_pred[test_idx] = pipeline.predict(X[test_idx])

    log("\nConfusion matrix:")
    matrix = confusion_matrix(y_encoded, y_pred, labels=np.arange(len(labels)))
    log("Labels: " + ", ".join(labels.tolist()))
    log(matrix.astype(int).tolist())

    log("\nClassification report:")
    report = classification_report(
        y_encoded,
        y_pred,
        target_names=labels.tolist(),
        zero_division=0,
        digits=4,
    )
    log(report)

    final_pipeline = build_pipeline()
    final_pipeline.fit(X, y_encoded)

    return final_pipeline, label_encoder, labels


def save_model(
    pipeline: Pipeline,
    label_encoder: LabelEncoder,
    class_distribution: Counter,
    failed_files: list[str],
    log,
) -> None:
    if MODEL_PATH.exists():
        MODEL_PATH.unlink()
        log(f"Deleted old model file: {MODEL_PATH}")

    payload = {
        "pipeline": pipeline,
        "scaler": pipeline.named_steps["scaler"],
        "model": pipeline.named_steps["model"],
        "classes": label_encoder.classes_,
        "feature_version": FEATURE_VERSION,
        "sample_rate": SAMPLE_RATE,
        "training_label_counts": dict(class_distribution),
        "failed_files": failed_files,
    }

    with MODEL_PATH.open("wb") as f:
        pickle.dump(payload, f)

    log(f"\nModel saved to: {MODEL_PATH}")


def write_report(lines: list[str]) -> None:
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


def main() -> None:
    report_lines: list[str] = []

    def log(message: str = "") -> None:
        print(message)
        report_lines.append(str(message))

    log("Danger sound training pipeline")
    log(f"Custom dataset root: {CUSTOM_DATASET_DIR}")
    log(f"ESC-50 root: {ESC50_DIR}")
    log(f"Model output: {MODEL_PATH}")

    esc50_samples = load_esc50_samples()
    custom_samples = load_custom_samples()
    samples = esc50_samples + custom_samples

    log(f"\nESC-50 samples loaded: {len(esc50_samples)}")
    log(f"Custom samples loaded: {len(custom_samples)}")
    log(f"Total samples before filtering: {len(samples)}")

    log_class_distribution(samples, log)

    X, y, groups, failed_files = extract_dataset_features(samples, log)
    class_distribution = Counter(y)

    log("\nClass distribution after successful feature extraction:")
    total = len(y)
    for label in sorted(class_distribution):
        count = class_distribution[label]
        log(f"  {label}: {count} ({count / total * 100:.2f}%)")

    log_group_summary(y, groups, log)

    pipeline, label_encoder, labels = evaluate_model(X, y, groups, log)
    save_model(pipeline, label_encoder, class_distribution, failed_files, log)

    log(f"Saved classes: {labels.tolist()}")
    log(f"Feature version: {FEATURE_VERSION}")
    write_report(report_lines)
    log(f"Training report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
