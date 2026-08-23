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
fp_details = []

for r in data["results"]:
    fname = r["file"]
    if fname in meta:
        cat = meta[fname]["category"]
        pred = r["prediction"]
        cat_stats[cat]["total"] += 1
        cat_stats[cat]["predictions"][pred] += 1
        if r["is_false_positive"]:
            cat_stats[cat]["fp"] += 1
            fp_details.append({
                "file": fname,
                "category": cat,
                "target": meta[fname]["target"],
                "predicted": pred,
                "confidence": r["confidence"],
            })

print("False Positive Files:")
print("=" * 90)
print(f"{'Filename':<40} {'Category':<20} {'Target':<8} {'Predicted':<12} {'Confidence':<10}")
print("-" * 90)
for d in fp_details:
    print(f"{d['file']:<40} {d['category']:<20} {d['target']:<8} {d['predicted']:<12} {d['confidence']:<10.4f}")

print("\n\nGrouped by ESC-50 Category:")
print("=" * 90)
for cat in sorted(cat_stats.keys()):
    stats = cat_stats[cat]
    fp_rate = stats["fp"] / stats["total"] * 100 if stats["total"] > 0 else 0
    print(f"\n{cat}:")
    print(f"  Tested: {stats['total']}")
    print(f"  False Positives: {stats['fp']} ({fp_rate:.1f}%)")
    preds = dict(stats["predictions"])
    for p, c in sorted(preds.items(), key=lambda x: -x[1]):
        print(f"    {p}: {c}")

print("\n\nCategories with False Positives:")
for cat in sorted(cat_stats.keys()):
    if cat_stats[cat]["fp"] > 0:
        stats = cat_stats[cat]
        fp_rate = stats["fp"] / stats["total"] * 100
        print(f"  {cat}: {stats['fp']}/{stats['total']} ({fp_rate:.1f}%)")
