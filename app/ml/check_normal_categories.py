import csv
from collections import Counter
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
ESC50_DIR = APP_DIR / "database" / "ESC-50-master"
META_FILE = ESC50_DIR / "meta" / "esc50.csv"
AUDIO_DIR = ESC50_DIR / "audio"

DANGER_EXCLUDED = {"gunshot", "siren", "chainsaw", "fireworks", "crying_baby", "glass_breaking", "car_horn"}
PROBLEMATIC = {"clapping", "breathing", "brushing_teeth", "pig", "rooster", "sneezing", "clock_alarm", "snoring", "toilet_flush", "hand_saw"}

meta = {}
with open(META_FILE, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        meta[row["filename"]] = row["category"]

normal_files = []
for f in AUDIO_DIR.glob("*.wav"):
    cat = meta.get(f.name, "unknown")
    if cat not in DANGER_EXCLUDED and cat not in PROBLEMATIC:
        normal_files.append(cat)

cat_counts = Counter(normal_files)
print(f"Total clean normal files: {len(normal_files)}")
print(f"Categories: {len(cat_counts)}")
print()
print("Categories in normal class:")
for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
    print(f"  {cat:25s}: {cnt:3d}")
