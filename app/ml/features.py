import numpy as np
import librosa

SAMPLE_RATE = 22050
CLIP_DURATION = 5.0
N_MFCC = 20
N_FFT = 2048
HOP_LENGTH = 512
FEATURE_VERSION = "mfcc20_delta_delta2_chroma_contrast_tonnetz_stats_v1"


def _stats(values):
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    return np.concatenate([values.mean(axis=1), values.std(axis=1)]).astype(np.float32)


def extract_features(audio_path, sr=SAMPLE_RATE, duration=CLIP_DURATION, n_mfcc=N_MFCC):
    signal, _ = librosa.load(
        audio_path,
        sr=sr,
        mono=True,
        duration=duration,
        res_type="soxr_hq",
    )

    target_length = int(sr * duration)
    if len(signal) < target_length:
        signal = np.pad(signal, (0, target_length - len(signal)))
    else:
        signal = signal[:target_length]

    mfcc = librosa.feature.mfcc(
        y=signal,
        sr=sr,
        n_mfcc=n_mfcc,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)
    chroma = librosa.feature.chroma_stft(
        y=signal,
        sr=sr,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    contrast = librosa.feature.spectral_contrast(
        y=signal,
        sr=sr,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    tonnetz = librosa.feature.tonnetz(y=signal, sr=sr)
    centroid = librosa.feature.spectral_centroid(
        y=signal,
        sr=sr,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    bandwidth = librosa.feature.spectral_bandwidth(
        y=signal,
        sr=sr,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    rolloff = librosa.feature.spectral_rolloff(
        y=signal,
        sr=sr,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    zcr = librosa.feature.zero_crossing_rate(signal, hop_length=HOP_LENGTH)
    rms = librosa.feature.rms(y=signal, hop_length=HOP_LENGTH)

    features = [
        _stats(mfcc),
        _stats(delta),
        _stats(delta2),
        _stats(chroma),
        _stats(contrast),
        _stats(tonnetz),
        _stats(centroid),
        _stats(bandwidth),
        _stats(rolloff),
        _stats(zcr),
        _stats(rms),
    ]

    return np.concatenate(features).astype(np.float32)
