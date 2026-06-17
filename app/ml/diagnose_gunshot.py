import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ml.predict_sound import predict_with_debug

CUSTOM_GUNSHOT_DIR = Path(r"D:\danger_alert_ml\app\dataset\gun_shot")


def main():
    candidates = sorted(CUSTOM_GUNSHOT_DIR.glob("*.wav"))

    if not candidates:
        raise SystemExit(f"No .wav files found in {CUSTOM_GUNSHOT_DIR}")

    audio_file = candidates[0]
    print(f"Testing gunshot file: {audio_file}")
    result = predict_with_debug(str(audio_file))

    print("\nAudio info:")
    for key, value in result["audio_info"].items():
        print(f"  {key}: {value}")

    print("\nFeature shape:", result["feature_shape"])
    print("Feature version:", result["feature_version"])
    print("Model feature version:", result["model_feature_version"])
    print("Model sample rate:", result["model_sample_rate"])
    print("Model classes:", result["model_classes"])
    print("Warnings:", result["warnings"])
    print("\nClass probabilities:")
    for label, probability in result["class_probabilities"].items():
        print(f"  {label}: {probability:.6f}")

    print("\nPredicted class:", result["predicted_class"])
    print("Confidence:", result["confidence"])


if __name__ == "__main__":
    main()
