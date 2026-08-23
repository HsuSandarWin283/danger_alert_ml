from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict

with open("false_positive_report.json") as f:
    data = json.load(f)

meta = {}
with open("../database/ESC-50-master/meta/esc50.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        meta[row["filename"]] = {
            "target": int(row["target"]),
            "category": row["category"],
        }

cat_stats = defaultdict(lambda: {"total": 0, "fp": 0, "predictions": Counter()})
for r in data["results"]:
    fname = r["file"]
    if fname in meta:
        cat = meta[fname]["category"]
        cat_stats[cat]["total"] += 1
        pred = r["prediction"]
        cat_stats[cat]["predictions"][pred] += 1
        if r["is_false_positive"]:
            cat_stats[cat]["fp"] += 1

print("Category-wise false positive analysis:")
print("=" * 60)
for cat in sorted(cat_stats.keys()):
    stats = cat_stats[cat]
    fp_rate = stats["fp"] / stats["total"] * 100 if stats["total"] > 0 else 0
    print(
        f"{cat:25s} tested={stats['total']:3d}  fp={stats['fp']:3d}  fp_rate={fp_rate:5.1f}%  predictions={dict(stats['predictions'])}"
    )

print("\n" + "=" * 60)
print("False positive files with categories:")
for r in data["results"]:
    if r["is_false_positive"]:
        fname = r["file"]
        if fname in meta:
            cat = meta[fname]["category"]
            norm = r["probabilities"].get("normal", 0)
            print(
                f"  {fname:40s} cat={cat:20s} pred={r['prediction']:10s} conf={r['confidence']:.4f}  norm={norm:.4f}"
            )
