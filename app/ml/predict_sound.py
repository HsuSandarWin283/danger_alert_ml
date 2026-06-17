import os
import pickle

import numpy as np

try:
    from .features import (
        EXPECTED_FEATURE_DIM,
        FEATURE_VERSION,
        extract_features,
        get_audio_info,
    )
except ImportError:
    from features import (
        EXPECTED_FEATURE_DIM,
        FEATURE_VERSION,
        extract_features,
        get_audio_info,
    )

MODEL_DIR = os.path.dirname(__file__) or "."
MODEL_PATH = os.path.join(MODEL_DIR, "danger_sound_model.pkl")


def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Please run train_model.py first.")

    with open(MODEL_PATH, "rb") as f:
        checkpoint = pickle.load(f)

    pipeline = checkpoint.get("pipeline")
    classes = checkpoint.get("classes")
    saved_feature_version = checkpoint.get("feature_version")

    if pipeline is None:
        pipeline = (checkpoint["scaler"], checkpoint["model"])

    if saved_feature_version != FEATURE_VERSION:
        print(
            "WARNING: Model feature version does not match prediction feature version. "
            f"Saved={saved_feature_version}, Current={FEATURE_VERSION}"
        )

    return pipeline, classes, checkpoint


def _predict_proba(pipeline, features):
    X = np.array([features])

    if hasattr(pipeline, "predict_proba"):
        return pipeline.predict_proba(X)[0]

    scaler, model = pipeline
    X_scaled = scaler.transform(X)
    return model.predict_proba(X_scaled)[0]


def predict_with_debug(audio_path):
    audio_info = get_audio_info(audio_path)
    features = extract_features(audio_path)
    pipeline, classes, checkpoint = load_model()
    probabilities = _predict_proba(pipeline, features)

    predicted_idx = int(np.argmax(probabilities))
    class_labels = [str(label) for label in classes]
    predicted_label = class_labels[predicted_idx]

    warnings = []
    if checkpoint.get("feature_version") != FEATURE_VERSION:
        warnings.append("feature_version_mismatch")
    if int(checkpoint.get("sample_rate", 0)) != audio_info["sample_rate"]:
        warnings.append("input_sample_rate_differs_from_training_sr")
    if features.shape[0] != EXPECTED_FEATURE_DIM:
        warnings.append("unexpected_feature_dimension")

    return {
        "audio_info": audio_info,
        "feature_shape": list(features.shape),
        "feature_version": FEATURE_VERSION,
        "model_feature_version": checkpoint.get("feature_version"),
        "model_sample_rate": checkpoint.get("sample_rate"),
        "model_classes": class_labels,
        "class_probabilities": {
            label: float(prob) for label, prob in zip(class_labels, probabilities)
        },
        "predicted_class": predicted_label,
        "confidence": float(probabilities[predicted_idx]),
        "warnings": warnings,
    }


def predict(audio_path):
    result = predict_with_debug(audio_path)
    return {
        "prediction": result["predicted_class"],
        "confidence": result["confidence"],
        "probabilities": result["class_probabilities"],
        "feature_version": result["feature_version"],
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
