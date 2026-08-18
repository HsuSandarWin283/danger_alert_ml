from __future__ import annotations

import logging
import os
import pickle
from typing import Any

import numpy as np
import librosa

try:
    from .features import FEATURE_VERSION, get_audio_info
except ImportError:
    from features import FEATURE_VERSION, get_audio_info

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.dirname(__file__) or "."

CNN_MODEL_PATH_PTH = os.path.join(MODEL_DIR, "danger_sound_cnn_model.pth")
CNN_CLASSES_PATH = os.path.join(MODEL_DIR, "cnn_classes.pkl")
CNN_SCALER_PATH = os.path.join(MODEL_DIR, "cnn_scaler_info.pkl")
LEGACY_MODEL_PATH = os.path.join(MODEL_DIR, "danger_sound_model.pkl")
YAMNET_MODEL_PATH = os.path.join(MODEL_DIR, "yamnet_classifier.pkl")

CNN_SAMPLE_RATE = 22050
CNN_DURATION = 3.0
CNN_N_MELS = 128
CNN_N_FFT = 2048
CNN_HOP_LENGTH = 512
CNN_IMG_HEIGHT = 128
CNN_IMG_WIDTH = 128
TARGET_LENGTH = int(CNN_SAMPLE_RATE * CNN_DURATION)

_cnn_model = None
_cnn_classes = None
_cnn_scaler_info = None
_model_type: str | None = None
_device = None


class DangerSoundCNN:
    _instance_class = None

    @staticmethod
    def _build_class(num_classes: int):
        import torch
        import torch.nn as nn

        class _DangerSoundCNN(nn.Module):
            def __init__(self, n_classes: int):
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
                    nn.Linear(128, n_classes),
                )

            def forward(self, x):
                x = self.features(x)
                x = x.view(x.size(0), -1)
                return self.classifier(x)

        return _DangerSoundCNN


def _get_device():
    global _device
    if _device is None:
        import torch
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return _device


def _compute_mel_spectrogram(audio_path: str) -> tuple[np.ndarray, dict]:
    import soundfile as sf

    raw_signal, raw_sr = sf.read(audio_path, dtype="float32", always_2d=False)
    if raw_signal.ndim > 1:
        raw_signal = raw_signal.mean(axis=1)

    signal, _ = librosa.load(
        audio_path,
        sr=CNN_SAMPLE_RATE,
        mono=True,
        duration=CNN_DURATION,
        res_type="soxr_hq",
    )

    if len(signal) < TARGET_LENGTH:
        signal = np.pad(signal, (0, TARGET_LENGTH - len(signal)))
    else:
        signal = signal[:TARGET_LENGTH]

    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak * 0.95

    mel = librosa.feature.melspectrogram(
        y=signal,
        sr=CNN_SAMPLE_RATE,
        n_mels=CNN_N_MELS,
        n_fft=CNN_N_FFT,
        hop_length=CNN_HOP_LENGTH,
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)

    mel_db = np.clip(mel_db, -80.0, 0.0)

    from scipy.ndimage import zoom
    zoom_h = CNN_IMG_HEIGHT / mel_db.shape[0]
    zoom_w = CNN_IMG_WIDTH / mel_db.shape[1]
    mel_resized = zoom(mel_db, (zoom_h, zoom_w), order=1)
    mel_final = mel_resized[:CNN_IMG_HEIGHT, :CNN_IMG_WIDTH].astype(np.float32)

    debug_info = {
        "raw_file_sr": int(raw_sr),
        "raw_file_samples": len(raw_signal),
        "raw_file_duration_sec": float(len(raw_signal) / raw_sr),
        "raw_file_rms": float(np.sqrt(np.mean(raw_signal ** 2))),
        "raw_file_peak": float(np.max(np.abs(raw_signal))),
        "resampled_length": len(signal),
        "signal_rms_after_resample": float(np.sqrt(np.mean(signal ** 2))),
        "mel_raw_shape": list(mel_db.shape),
        "mel_resized_shape": list(mel_final.shape),
        "mel_min": float(mel_final.min()),
        "mel_max": float(mel_final.max()),
        "mel_mean": float(mel_final.mean()),
        "mel_std": float(mel_final.std()),
    }

    return mel_final, debug_info


def _normalize_mel(mel: np.ndarray) -> tuple[np.ndarray, dict]:
    debug_info = {}
    if _cnn_scaler_info and "mean" in _cnn_scaler_info and "std" in _cnn_scaler_info:
        mean = _cnn_scaler_info["mean"]
        std = _cnn_scaler_info["std"]
        debug_info["scaler_mean"] = mean
        debug_info["scaler_std"] = std
        if std > 0:
            normalized = (mel - mean) / std
            debug_info["normalized_min"] = float(normalized.min())
            debug_info["normalized_max"] = float(normalized.max())
            debug_info["normalized_mean"] = float(normalized.mean())
            debug_info["normalized_std"] = float(normalized.std())
            return normalized, debug_info
    debug_info["scaler_applied"] = False
    return mel, debug_info


def _load_pytorch_model() -> tuple:
    import torch

    checkpoint = torch.load(CNN_MODEL_PATH_PTH, map_location="cpu", weights_only=False)

    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
        classes = checkpoint.get("classes", [])
        num_classes = checkpoint.get("num_classes", len(classes))
        scaler_info = checkpoint.get("scaler_info", None)
    else:
        state_dict = checkpoint
        with open(CNN_CLASSES_PATH, "rb") as f:
            raw = pickle.load(f)
        classes = raw["classes"] if isinstance(raw, dict) and "classes" in raw else raw
        num_classes = len(classes)
        scaler_info = None
        if os.path.exists(CNN_SCALER_PATH):
            with open(CNN_SCALER_PATH, "rb") as f:
                scaler_info = pickle.load(f)

    DangerSoundCNN._instance_class = DangerSoundCNN._build_class(num_classes)
    model = DangerSoundCNN._instance_class(num_classes)
    model.load_state_dict(state_dict)

    device = _get_device()
    model = model.to(device)
    model.eval()

    logger.info("PyTorch model loaded on %s with %d classes", device, num_classes)
    return model, classes, scaler_info


def _load_legacy_model() -> tuple:
    with open(LEGACY_MODEL_PATH, "rb") as f:
        checkpoint = pickle.load(f)

    pipeline = checkpoint.get("pipeline")
    classes = checkpoint.get("classes")

    if pipeline is None:
        pipeline = (checkpoint["scaler"], checkpoint["model"])

    return pipeline, classes, checkpoint


def load_model() -> None:
    global _cnn_model, _cnn_classes, _cnn_scaler_info, _model_type

    if _cnn_model is not None:
        return

    if os.path.exists(CNN_MODEL_PATH_PTH):
        logger.info("Loading PyTorch CNN model from %s", CNN_MODEL_PATH_PTH)
        try:
            _cnn_model, _cnn_classes, _cnn_scaler_info = _load_pytorch_model()
            _model_type = "pytorch"
            logger.info("PyTorch model loaded. Classes: %s", [str(c) for c in _cnn_classes])
        except Exception as exc:
            logger.exception("Failed to load PyTorch model")
            raise RuntimeError(f"PyTorch model loading failed: {exc}") from exc
    elif os.path.exists(LEGACY_MODEL_PATH):
        logger.warning("PyTorch model not found. Falling back to legacy model.")
        try:
            _cnn_model, _cnn_classes, _ = _load_legacy_model()
            _cnn_scaler_info = None
            _model_type = "legacy"
            logger.info("Legacy model loaded. Classes: %s", [str(c) for c in _cnn_classes])
        except Exception as exc:
            logger.exception("Failed to load legacy model")
            raise RuntimeError(f"Legacy model loading failed: {exc}") from exc
    else:
        raise FileNotFoundError(
            f"No model found. Expected PyTorch at {CNN_MODEL_PATH_PTH}, "
            f"or legacy at {LEGACY_MODEL_PATH}."
        )


def _predict_pytorch(audio_path: str, debug: bool = False) -> tuple[np.ndarray, dict]:
    import torch

    mel, mel_debug = _compute_mel_spectrogram(audio_path)
    mel_norm, norm_debug = _normalize_mel(mel)

    mel_input = mel_norm.reshape(1, 1, CNN_IMG_HEIGHT, CNN_IMG_WIDTH)
    mel_tensor = torch.tensor(mel_input, dtype=torch.float32).to(_get_device())

    with torch.no_grad():
        logits = _cnn_model(mel_tensor)
        probabilities = torch.nn.functional.softmax(logits, dim=1).cpu().numpy()[0]

    all_debug = {**mel_debug, **norm_debug}
    all_debug["tensor_shape"] = list(mel_input.shape)
    all_debug["logits"] = logits.cpu().numpy().tolist()
    all_debug["probabilities"] = {
        str(c): float(p) for c, p in zip(_cnn_classes, probabilities)
    }

    return probabilities, all_debug


def _predict_legacy(audio_path: str) -> np.ndarray:
    try:
        from .features import extract_features
    except ImportError:
        from features import extract_features

    features = extract_features(audio_path)
    X = np.array([features])

    pipeline = _cnn_model
    if hasattr(pipeline, "predict_proba"):
        return pipeline.predict_proba(X)[0]

    scaler, model = pipeline
    X_scaled = scaler.transform(X)
    return model.predict_proba(X_scaled)[0]


def predict(audio_path: str) -> dict[str, Any]:
    load_model()

    audio_info = get_audio_info(audio_path)

    if _model_type == "pytorch":
        probabilities, _debug = _predict_pytorch(audio_path)
    elif _model_type == "legacy":
        probabilities = _predict_legacy(audio_path)
    else:
        raise RuntimeError(f"Unknown model type: {_model_type}")

    predicted_idx = int(np.argmax(probabilities))
    class_labels = [str(c) for c in _cnn_classes]
    predicted_label = class_labels[predicted_idx]

    feature_version = {
        "pytorch": "cnn_mel_128x128_v2",
    }.get(_model_type, FEATURE_VERSION)

    return {
        "prediction": predicted_label,
        "confidence": float(probabilities[predicted_idx]),
        "probabilities": {
            label: float(prob) for label, prob in zip(class_labels, probabilities)
        },
        "feature_version": feature_version,
    }


def predict_with_debug(audio_path: str) -> dict[str, Any]:
    load_model()

    audio_info = get_audio_info(audio_path)

    if _model_type == "pytorch":
        probabilities, debug_info = _predict_pytorch(audio_path, debug=True)
        feature_shape = debug_info.get("mel_resized_shape", [CNN_IMG_HEIGHT, CNN_IMG_WIDTH])
    elif _model_type == "legacy":
        try:
            from .features import extract_features, EXPECTED_FEATURE_DIM
        except ImportError:
            from features import extract_features, EXPECTED_FEATURE_DIM

        features = extract_features(audio_path)
        feature_shape = list(features.shape)
        debug_info = {}

        if hasattr(_cnn_model, "predict_proba"):
            probabilities = _cnn_model.predict_proba(features.reshape(1, -1))[0]
        else:
            scaler, model = _cnn_model
            X_scaled = scaler.transform(features.reshape(1, -1))
            probabilities = model.predict_proba(X_scaled)[0]
    else:
        raise RuntimeError(f"Unknown model type: {_model_type}")

    predicted_idx = int(np.argmax(probabilities))
    class_labels = [str(c) for c in _cnn_classes]
    predicted_label = class_labels[predicted_idx]

    feature_version = {
        "pytorch": "cnn_mel_128x128_v2",
    }.get(_model_type, FEATURE_VERSION)

    return {
        "audio_info": audio_info,
        "feature_shape": feature_shape,
        "feature_version": feature_version,
        "model_feature_version": feature_version,
        "model_sample_rate": CNN_SAMPLE_RATE,
        "model_classes": class_labels,
        "class_probabilities": {
            label: float(prob) for label, prob in zip(class_labels, probabilities)
        },
        "predicted_class": predicted_label,
        "confidence": float(probabilities[predicted_idx]),
        "warnings": [],
        "debug": debug_info,
    }


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python predict_sound.py <audio_file> [--debug]")
        sys.exit(1)

    audio_file = sys.argv[1]

    if "--debug" in sys.argv:
        print(json.dumps(predict_with_debug(audio_file), indent=2))
    else:
        result = predict(audio_file)
        print(f"Prediction: {result['prediction']}")
        print(f"Confidence: {result['confidence']:.4f}")
        print(f"Probabilities: {result['probabilities']}")
