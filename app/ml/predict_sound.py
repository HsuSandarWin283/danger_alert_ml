import os
import pickle

import numpy as np

try:
    from .features import FEATURE_VERSION, extract_features
except ImportError:
    from features import FEATURE_VERSION, extract_features

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

    return pipeline, classes


def predict(audio_path):
    pipeline, classes = load_model()
    features = extract_features(audio_path)
    X = np.array([features])

    if hasattr(pipeline, "predict_proba"):
        probabilities = pipeline.predict_proba(X)[0]
    else:
        scaler, model = pipeline
        X_scaled = scaler.transform(X)
        probabilities = model.predict_proba(X_scaled)[0]

    predicted_idx = int(np.argmax(probabilities))
    confidence = float(probabilities[predicted_idx])
    class_labels = [str(label) for label in classes]
    predicted_label = class_labels[predicted_idx]

    return {
        "prediction": predicted_label,
        "confidence": confidence,
        "probabilities": {
            label: float(prob) for label, prob in zip(class_labels, probabilities)
        },
        "feature_version": FEATURE_VERSION,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python predict_sound.py <audio_file>")
        sys.exit(1)

    audio_file = sys.argv[1]
    result = predict(audio_file)
    print(f"Prediction: {result['prediction']}")
    print(f"Confidence: {result['confidence']:.4f}")
    print(f"Probabilities: {result['probabilities']}")
