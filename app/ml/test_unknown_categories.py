from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import requests

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"
PREDICT_URL = "http://192.168.99.112:8000/predict"

DANGER_CATEGORIES = {"gunshot", "siren", "chainsaw", "fireworks", "crying_baby", "glass_breaking", "car_horn"}

TEST_CATEGORIES = [
    "car_horn", "glass_breaking", "clapping", "breathing", "engine",
    "footsteps", "dog", "cat", "rain", "wind", "thunderstorm",
    "sea_waves", "train", "helicopter", "airplane", "insects",
    "crickets", "chirping_birds", "vacuum_cleaner", "washing_machine",
    "crow", "clock_tick", "drinking_sipping", "brushing_teeth",
    "snoring", "laughing", "coughing", "pig", "rooster", "sneezing",
]

meta = {}
with open(META_FILE, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        meta[row["filename"]] = row["category"]

cat_files: dict[str, list[Path]] = defaultdict(list)
for f in AUDIO_DIR.glob("*.wav"):
    cat = meta.get(f.name, "unknown")
    if cat in TEST_CATEGORIES:
        cat_files[cat].append(f)

results = []
for cat in TEST_CATEGORIES:
    files = cat_files.get(cat, [])
    if not files:
        continue
    for path in files[:10]:
        with open(path, "rb") as f:
            files_data = {"file": (path.name, f, "audio/wav")}
            r = requests.post(PREDICT_URL, files=files_data, timeout=30)
        if r.status_code != 200:
            continue
        data = r.json()
        results.append({
            "file": path.name,
            "expected_class": "normal",
            "category": cat,
            "raw_prediction": data.get("raw_prediction", ""),
            "final_prediction": data.get("prediction", ""),
            "confidence": data.get("confidence", 0),
            "is_danger": data.get("is_danger", False),
            "reason": data.get("reason", ""),
            "margin": data.get("debug", {}).get("margin", 0),
        })

print(f"Total tested: {len(results)}")
print(f"Danger detections: {sum(1 for r in results if r['is_danger'])}")
print(f"False Positive Rate: {sum(1 for r in results if r['is_danger']) / len(results) * 100:.2f}%")

by_cat = defaultdict(list)
for r in results:
    by_cat[r["category"]].append(r)

print("\nPer-category results:")
for cat in sorted(by_cat.keys()):
    items = by_cat[cat]
    fp = sum(1 for i in items if i["is_danger"])
    print(f"  {cat:25s}: tested={len(items):2d}  fp={fp:2d}  fp_rate={fp/len(items)*100:5.1f}%")

with open(ML_DIR / "unknown_test_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {ML_DIR / 'unknown_test_results.json'}")
