from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np
import librosa

SAMPLE_RATE = 22050
DURATION = 3.0
TARGET_LENGTH = int(SAMPLE_RATE * DURATION)

_FFMPEG_DIR = Path(r"C:\Users\Hsu Sandar Win\AppData\Local\Python\ffmpeg\ffmpeg-9.0-essentials_build\bin")
if _FFMPEG_DIR.exists():
    os.environ["PATH"] = str(_FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")


def _load_raw(path: str | Path, sr: int = SAMPLE_RATE, duration: float = DURATION) -> np.ndarray | None:
    try:
        signal, _ = librosa.load(str(path), sr=sr, mono=True, duration=duration, res_type="soxr_hq")
        if len(signal) < TARGET_LENGTH:
            signal = np.pad(signal, (0, TARGET_LENGTH - len(signal)))
        else:
            signal = signal[:TARGET_LENGTH]
        peak = np.max(np.abs(signal))
        if peak > 0:
            signal = signal / peak * 0.95
        return signal.astype(np.float32)
    except Exception:
        return None


def _apply_gain(signal: np.ndarray, gain_range: tuple[float, float] = (0.3, 1.5)) -> np.ndarray:
    gain = random.uniform(*gain_range)
    return signal * gain


def _apply_time_shift(signal: np.ndarray, max_shift_ms: int = 200) -> np.ndarray:
    max_shift = int(SAMPLE_RATE * max_shift_ms / 1000)
    if max_shift <= 0:
        return signal
    shift = random.randint(-max_shift, max_shift)
    shifted = np.roll(signal, shift)
    if shift > 0:
        shifted[:shift] = 0.0
    else:
        shifted[shift:] = 0.0
    return shifted


def _apply_low_pass(signal: np.ndarray, cutoff_range: tuple[float, float] = (3000.0, 8000.0)) -> np.ndarray:
    nyquist = SAMPLE_RATE / 2.0
    cutoff = random.uniform(*cutoff_range)
    cutoff = min(cutoff, nyquist - 100.0)
    from scipy.signal import butter, lfilter
    b, a = butter(4, cutoff / nyquist, btype="low")
    return lfilter(b, a, signal).astype(np.float32)


def _apply_high_pass(signal: np.ndarray, cutoff_range: tuple[float, float] = (80.0, 300.0)) -> np.ndarray:
    nyquist = SAMPLE_RATE / 2.0
    cutoff = random.uniform(*cutoff_range)
    cutoff = max(cutoff, 10.0)
    from scipy.signal import butter, lfilter
    b, a = butter(4, cutoff / nyquist, btype="high")
    return lfilter(b, a, signal).astype(np.float32)


def _apply_band_pass(signal: np.ndarray) -> np.ndarray:
    nyquist = SAMPLE_RATE / 2.0
    low = random.uniform(200.0, min(800.0, nyquist - 500.0))
    high = random.uniform(max(low + 500.0, 4000.0), min(12000.0, nyquist - 100.0))
    if high <= low:
        high = low + 500.0
    from scipy.signal import butter, lfilter
    b, a = butter(4, [low / nyquist, high / nyquist], btype="band")
    return lfilter(b, a, signal).astype(np.float32)


def _generate_noise(duration: float, noise_type: str = "white") -> np.ndarray:
    from scipy.signal import lfilter
    samples = int(SAMPLE_RATE * duration)
    if noise_type == "white":
        return np.random.randn(samples).astype(np.float32) * 0.1
    elif noise_type == "pink":
        white = np.random.randn(samples).astype(np.float32)
        pink = lfilter([1.0], [1.0, -0.98], white)
        return pink * 0.08
    elif noise_type == "room":
        white = np.random.randn(samples).astype(np.float32)
        room = lfilter([1.0], [1.0, -0.85, 0.2], white)
        return room * 0.06
    else:
        return np.random.randn(samples).astype(np.float32) * 0.1


def _mix_noise(signal: np.ndarray, snr_db_range: tuple[float, float] = (5.0, 25.0)) -> np.ndarray:
    noise_types = ["white", "pink", "room"]
    noise_type = random.choice(noise_types)
    noise = _generate_noise(len(signal) / SAMPLE_RATE, noise_type=noise_type)
    if len(noise) != len(signal):
        noise = np.pad(noise, (0, max(0, len(signal) - len(noise))))
        noise = noise[:len(signal)]

    signal_power = np.mean(signal ** 2)
    noise_power = np.mean(noise ** 2)
    if noise_power < 1e-8:
        return signal

    snr_db = random.uniform(*snr_db_range)
    desired_noise_power = signal_power / (10 ** (snr_db / 10.0))
    noise = noise * np.sqrt(desired_noise_power / noise_power)

    mixed = signal + noise
    peak = np.max(np.abs(mixed))
    if peak > 0.99:
        mixed *= 0.99 / peak
    return mixed.astype(np.float32)


def _apply_reverb(signal: np.ndarray, decay_range: tuple[float, float] = (0.2, 0.6)) -> np.ndarray:
    decay = random.uniform(*decay_range)
    ir_length = random.randint(int(SAMPLE_RATE * 0.1), int(SAMPLE_RATE * 0.4))
    ir = np.exp(-np.arange(ir_length) / (decay * ir_length)).astype(np.float32)
    ir = ir / (ir.sum() + 1e-8)
    reverb = np.convolve(signal, ir, mode="full")[:len(signal)]
    reverb = reverb * 0.7 + signal * 0.3
    peak = np.max(np.abs(reverb))
    if peak > 0.99:
        reverb *= 0.99 / peak
    return reverb.astype(np.float32)


def _apply_compression(signal: np.ndarray, threshold: float = 0.3, ratio: float = 4.0) -> np.ndarray:
    from scipy.signal import lfilter
    d = random.uniform(0.2, 0.5)
    r = random.uniform(3.0, 8.0)
    env = lfilter([1.0], [1.0, -d], np.abs(signal))
    gain = np.where(env > r, 1.0 + (env - r) * (1.0 / r - 1.0), 1.0)
    compressed = signal * gain
    peak = np.max(np.abs(compressed))
    if peak > 0.99:
        compressed *= 0.99 / peak
    return compressed.astype(np.float32)


def augment_signal(signal: np.ndarray, p: float = 0.8) -> np.ndarray:
    if random.random() > p:
        return signal

    aug = signal.copy()

    if random.random() < 0.7:
        aug = _apply_gain(aug, gain_range=(0.2, 1.2))

    if random.random() < 0.6:
        aug = _mix_noise(aug, snr_db_range=(3.0, 30.0))

    if random.random() < 0.5:
        aug = _apply_time_shift(aug, max_shift_ms=200)

    if random.random() < 0.4:
        aug = _apply_low_pass(aug, cutoff_range=(3000.0, 10000.0))

    if random.random() < 0.3:
        aug = _apply_high_pass(aug, cutoff_range=(80.0, 400.0))

    if random.random() < 0.2:
        aug = _apply_band_pass(aug)

    if random.random() < 0.2:
        aug = _apply_reverb(aug, decay_range=(0.2, 0.6))

    if random.random() < 0.3:
        aug = _apply_compression(aug)

    peak = np.max(np.abs(aug))
    if peak > 0:
        aug = aug / peak * 0.95

    return aug.astype(np.float32)


def load_and_augment(path: str | Path, sr: int = SAMPLE_RATE, duration: float = DURATION, p: float = 0.8) -> np.ndarray | None:
    signal = _load_raw(path, sr=sr, duration=duration)
    if signal is None:
        return None
    return augment_signal(signal, p=p)
