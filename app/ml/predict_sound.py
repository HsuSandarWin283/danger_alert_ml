import os
import pickle

import numpy as np
import librosa

try:
    from .features import FEATURE_VERSION, get_audio_info
except ImportError:
    from features import FEATURE_VERSION, get_audio_info

MODEL_DIR = os.path.dirname(__file__) or "."

CNN_MODEL_PATH = os.path.join(MODEL_DIR, "danger_sound_cnn_model.h5")
CNN_CLASSES_PATH = os.path.join(MODEL_DIR, "cnn_classes.pkl")
CNN_SCALER_PATH = os.path.join(MODEL_DIR, "cnn_scaler_info.pkl")

LEGACY_MODEL_PATH = os.path.join(MODEL_DIR, "danger_sound_model.pkl")

CNN_SAMPLE_RATE = 22050
CNN_DURATION = 5.0
CNN_N_MELS = 128
CNN_N_FFT = 2048
CNN_HOP_LENGTH = 512
CNN_IMG_HEIGHT = 128
CNN_IMG_WIDTH = 128

_cnn_model = None
_cnn_classes = None
_cnn_scaler_info = None
_model_type = None


def _compute_mel_spectrogram(audio_path):
    signal, _ = librosa.load(
        audio_path,
        sr=CNN_SAMPLE_RATE,
        mono=True,
        duration=CNN_DURATION,
        res_type="soxr_hq",
    )

    target_length = int(CNN_SAMPLE_RATE * CNN_DURATION)
    if len(signal) < target_length:
        signal = np.pad(signal, (0, target_length - len(signal)))
    else:
        signal = signal[:target_length]

    mel = librosa.feature.melspectrogram(
        y=signal,
        sr=CNN_SAMPLE_RATE,
        n_mels=CNN_N_MELS,
        n_fft=CNN_N_FFT,
        hop_length=CNN_HOP_LENGTH,
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)

    from scipy.ndimage import zoom

    zoom_h = CNN_IMG_HEIGHT / mel_db.shape[0]
    zoom_w = CNN_IMG_WIDTH / mel_db.shape[1]
    mel_resized = zoom(mel_db, (zoom_h, zoom_w), order=1)

    mel_resized = mel_resized[:CNN_IMG_HEIGHT, :CNN_IMG_WIDTH]

    return mel_resized


def _load_cnn_model():
    import tensorflow as tf

    model = tf.keras.models.load_model(CNN_MODEL_PATH)

    with open(CNN_CLASSES_PATH, "rb") as f:
        raw = pickle.load(f)

    if isinstance(raw, dict) and "classes" in raw:
        classes = raw["classes"]
    else:
        classes = raw

    scaler_info = None
    if os.path.exists(CNN_SCALER_PATH):
        with open(CNN_SCALER_PATH, "rb") as f:
            scaler_info = pickle.load(f)

    return model, classes, scaler_info


def _load_legacy_model():
    with open(LEGACY_MODEL_PATH, "rb") as f:
        checkpoint = pickle.load(f)

    pipeline = checkpoint.get("pipeline")
    classes = checkpoint.get("classes")

    if pipeline is None:
        pipeline = (checkpoint["scaler"], checkpoint["model"])

    return pipeline, classes, checkpoint


def load_model():
    global _cnn_model, _cnn_classes, _cnn_scaler_info, _model_type

    if _cnn_model is not None:
        return

    if os.path.exists(CNN_MODEL_PATH):
        print("Loading TensorFlow CNN model...")
        _cnn_model, _cnn_classes, _cnn_scaler_info = _load_cnn_model()
        _model_type = "cnn"

        class_labels = [str(c) for c in _cnn_classes]
        print(f"CNN model loaded successfully.")
        print(f"Classes: {class_labels}")
    elif os.path.exists(LEGACY_MODEL_PATH):
        print("WARNING: CNN model not found. Falling back to legacy sklearn model.")
        pipeline, classes, _ = _load_legacy_model()
        _cnn_model = pipeline
        _cnn_classes = classes
        _cnn_scaler_info = None
        _model_type = "legacy"

        class_labels = [str(c) for c in _cnn_classes]
        print(f"Legacy model loaded. Classes: {class_labels}")
    else:
        raise FileNotFoundError(
            f"No model found. Expected CNN model at {CNN_MODEL_PATH} "
            f"or legacy model at {LEGACY_MODEL_PATH}."
        )


def _predict_cnn(audio_path):
    mel = _compute_mel_spectrogram(audio_path)

    if _cnn_scaler_info and "mean" in _cnn_scaler_info and "std" in _cnn_scaler_info:
        mean = _cnn_scaler_info["mean"]
        std = _cnn_scaler_info["std"]
        if std > 0:
            mel = (mel - mean) / std

    mel_input = mel.reshape(1, CNN_IMG_HEIGHT, CNN_IMG_WIDTH, 1)
    probabilities = _cnn_model.predict(mel_input, verbose=0)[0]

    return probabilities


def _predict_legacy(audio_path):
    from .features import extract_features

    features = extract_features(audio_path)
    X = np.array([features])

    pipeline = _cnn_model
    if hasattr(pipeline, "predict_proba"):
        probabilities = pipeline.predict_proba(X)[0]
    else:
        scaler, model = pipeline
        X_scaled = scaler.transform(X)
        probabilities = model.predict_proba(X_scaled)[0]

    return probabilities


def predict_with_debug(audio_path):
    load_model()

    audio_info = get_audio_info(audio_path)

    if _model_type == "cnn":
        mel = _compute_mel_spectrogram(audio_path)
        feature_shape = list(mel.shape)

        mel_normalized = mel.copy()
        if _cnn_scaler_info and "mean" in _cnn_scaler_info and "std" in _cnn_scaler_info:
            mean = _cnn_scaler_info["mean"]
            std = _cnn_scaler_info["std"]
            if std > 0:
                mel_normalized = (mel_normalized - mean) / std

        mel_input = mel_normalized.reshape(1, CNN_IMG_HEIGHT, CNN_IMG_WIDTH, 1)
        probabilities = _cnn_model.predict(mel_input, verbose=0)[0]
    else:
        from .features import extract_features, EXPECTED_FEATURE_DIM

        features = extract_features(audio_path)
        feature_shape = list(features.shape)
        X = np.array([features])

        if hasattr(_cnn_model, "predict_proba"):
            probabilities = _cnn_model.predict_proba(X)[0]
        else:
            scaler, model = _cnn_model
            X_scaled = scaler.transform(X)
            probabilities = model.predict_proba(X_scaled)[0]

    predicted_idx = int(np.argmax(probabilities))
    class_labels = [str(label) for label in _cnn_classes]
    predicted_label = class_labels[predicted_idx]

    warnings = []
    if audio_info["sample_rate"] != CNN_SAMPLE_RATE:
        warnings.append("input_sample_rate_differs_from_training_sr")

    return {
        "audio_info": audio_info,
        "feature_shape": feature_shape,
        "feature_version": "cnn_mel_128x128_v1" if _model_type == "cnn" else FEATURE_VERSION,
        "model_feature_version": "cnn_mel_128x128_v1" if _model_type == "cnn" else FEATURE_VERSION,
        "model_sample_rate": CNN_SAMPLE_RATE,
        "model_classes": class_labels,
        "class_probabilities": {
            label: float(prob) for label, prob in zip(class_labels, probabilities)
        },
        "predicted_class": predicted_label,
        "confidence": float(probabilities[predicted_idx]),
        "warnings": warnings,
    }


def predict(audio_path):
    load_model()

    audio_info = get_audio_info(audio_path)

    if _model_type == "cnn":
        probabilities = _predict_cnn(audio_path)
    else:
        probabilities = _predict_legacy(audio_path)

    predicted_idx = int(np.argmax(probabilities))
    class_labels = [str(label) for label in _cnn_classes]
    predicted_label = class_labels[predicted_idx]

    return {
        "prediction": predicted_label,
        "confidence": float(probabilities[predicted_idx]),
        "probabilities": {
            label: float(prob) for label, prob in zip(class_labels, probabilities)
        },
        "feature_version": "cnn_mel_128x128_v1" if _model_type == "cnn" else FEATURE_VERSION,
    }


if __name__ == "__main__":
    import json
    import sys

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
