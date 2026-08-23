from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1]
ML_DIR = Path(__file__).resolve().parent
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"
PREDICT_URL = "http://192.168.99.112:8000/predict"

TEST_CATEGORIES = [
    "car_horn", "glass_breaking", "clapping", "breathing", "engine",
    "footsteps", "dog", "siren", "fireworks", "chainsaw",
    "door_wood_creaks", "door_wood_knock", "crying_baby", "laughing",
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
            try:
                r = requests.post(PREDICT_URL, files=files_data, timeout=30)
            except requests.RequestException as exc:
                print(f"Request failed for {path.name}: {exc}")
                continue
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
            "gate_probability": data.get("danger_probability"),
            "gate_threshold": data.get("gate_threshold"),
            "gate_decision": data.get("gate_decision"),
            "top2_probability": data.get("top2_probability"),
            "margin": data.get("margin"),
        })

print("=" * 90)
print("UNKNOWN / NON-DANGER EVALUATION")
print("=" * 90)
print(f"Total tested: {len(results)}")
print(f"Danger detections: {sum(1 for r in results if r['is_danger'])}")
print(f"False Positive Rate: {sum(1 for r in results if r['is_danger']) / max(len(results), 1) * 100:.2f}%")

by_cat = defaultdict(list)
for r in results:
    by_cat[r["category"]].append(r)

print("\nPer-category results:")
for cat in sorted(by_cat.keys()):
    items = by_cat[cat]
    fp = sum(1 for i in items if i["is_danger"])
    print(f"  {cat:25s}: tested={len(items):2d}  fp={fp:2d}  fp_rate={fp/len(items)*100:5.1f}%")

print("\nDetailed results:")
for r in results:
    print(f"  {r['file']:40s} cat={r['category']:20s} raw={r['raw_prediction']:10s} gate={r.get('gate_decision', 'N/A'):10s} danger={r['is_danger']} reason={r['reason']}")

with open(ML_DIR / "unknown_evaluation_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {ML_DIR / 'unknown_evaluation_results.json'}")
