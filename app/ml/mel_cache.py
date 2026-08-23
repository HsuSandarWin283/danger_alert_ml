from __future__ import annotations

import hashlib
import os
import pickle
from pathlib import Path

import numpy as np
import librosa

SAMPLE_RATE = 22050
DURATION = 3.0
N_MELS = 128
N_FFT = 2048
HOP_LENGTH = 512
IMG_HEIGHT = 128
IMG_WIDTH = 128
TARGET_LENGTH = int(SAMPLE_RATE * DURATION)


def _compute_mel(signal: np.ndarray) -> np.ndarray:
    mel = librosa.feature.melspectrogram(
        y=signal,
        sr=SAMPLE_RATE,
        n_mels=N_MELS,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    mel_db = np.clip(mel_db, -80.0, 0.0)
    from scipy.ndimage import zoom
    zh = IMG_HEIGHT / mel_db.shape[0]
    zw = IMG_WIDTH / mel_db.shape[1]
    resized = zoom(mel_db, (zh, zw), order=1)
    return resized[:IMG_HEIGHT, :IMG_WIDTH].astype(np.float32)


def precompute_mel_for_path(audio_path: str | Path, sr: int = SAMPLE_RATE, duration: float = DURATION) -> np.ndarray | None:
    try:
        signal, _ = librosa.load(str(audio_path), sr=sr, mono=True, duration=duration, res_type="soxr_hq")
        if len(signal) < TARGET_LENGTH:
            signal = np.pad(signal, (0, TARGET_LENGTH - len(signal)))
        else:
            signal = signal[:TARGET_LENGTH]
        peak = np.max(np.abs(signal))
        if peak > 0:
            signal = signal / peak * 0.95
        return _compute_mel(signal)
    except Exception:
        return None


def _cache_key_for(audio_path: str | Path) -> str:
    h = hashlib.sha1(str(audio_path).encode("utf-8")).hexdigest()[:12]
    return f"{Path(audio_path).stem}_{h}.npy"


def ensure_cache(
    audio_paths: list[Path],
    cache_dir: str | Path,
    *,
    recompute: bool = False,
    progress_every: int = 200,
) -> tuple[list[np.ndarray], list[int]]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    index_path = cache_dir / "index.pkl"
    index: dict[str, str] = {}
    if index_path.exists() and not recompute:
        try:
            with open(index_path, "rb") as f:
                index = pickle.load(f)
        except Exception:
            index = {}

    features: list[np.ndarray] = []
    valid_indices: list[int] = []

    for i, p in enumerate(audio_paths):
        key = _cache_key_for(p)
        cache_file = cache_dir / key

        if cache_file.exists() and not recompute:
            try:
                mel = np.load(cache_file)
                features.append(mel)
                valid_indices.append(i)
                index[key] = str(p)
                continue
            except Exception:
                pass

        mel = precompute_mel_for_path(p)
        if mel is not None:
            np.save(cache_file, mel)
            features.append(mel)
            valid_indices.append(i)
            index[key] = str(p)

        if (i + 1) % progress_every == 0:
            print(f"  cached {i + 1}/{len(audio_paths)} ({len(features)} valid)")

    with open(index_path, "wb") as f:
        pickle.dump(index, f)

    return features, valid_indices


def load_cache(
    audio_paths: list[Path],
    cache_dir: str | Path,
) -> tuple[list[np.ndarray], list[int]]:
    cache_dir = Path(cache_dir)
    if not cache_dir.exists():
        return [], []

    index_path = cache_dir / "index.pkl"
    if not index_path.exists():
        return [], []

    try:
        with open(index_path, "rb") as f:
            index = pickle.load(f)
    except Exception:
        return [], []

    rev = {v: k for k, v in index.items()}
    features: list[np.ndarray] = []
    valid_indices: list[int] = []

    for i, p in enumerate(audio_paths):
        key = rev.get(str(p))
        if key is None:
            continue
        cache_file = cache_dir / key
        if cache_file.exists():
            try:
                mel = np.load(cache_file)
                features.append(mel)
                valid_indices.append(i)
            except Exception:
                pass

    return features, valid_indices


def compute_normalization(mels: list[np.ndarray]) -> dict:
    if not mels:
        return {"mean": 0.0, "std": 1.0}
    arr = np.array(mels, dtype=np.float32)
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    if std < 1e-8:
        std = 1.0
    return {"mean": mean, "std": std}


def normalize_mel(mel: np.ndarray, scaler: dict) -> np.ndarray:
    mean = scaler["mean"]
    std = scaler["std"]
    if std > 0:
        mel = (mel - mean) / std
    return mel
