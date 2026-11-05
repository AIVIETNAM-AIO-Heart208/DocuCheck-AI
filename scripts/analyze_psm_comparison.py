#!/usr/bin/env python3
"""Summarize paired image differences with exploratory image-bootstrap intervals."""
import argparse
from collections import Counter
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_psm_comparison import load_manifest, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    folder = args.run_dir
    target = folder / "paired_analysis.json"
    if target.exists():
        parser.error("Analysis exists; preserve prior evidence")
    rows = {p: {r["image_id"]: r for r in load_manifest(folder / f"psm{p}/per_image_metrics.jsonl")} for p in (6, 4, 11)}
    ids = sorted(rows[6])
    if any(set(rows[p]) != set(ids) for p in (4, 11)):
        raise ValueError("PSM image sets differ")
    samples = np.random.default_rng(42).integers(0, len(ids), size=(5000, len(ids)))
    results = {}
    for p in (4, 11):
        result = {}
        for metric, numerator, denominator in (("cer", "char_errors", "gt_characters"), ("wer", "word_errors", "gt_words")):
            counts = Counter("improved" if rows[p][i][metric] < rows[6][i][metric] else
                             "worse" if rows[p][i][metric] > rows[6][i][metric] else "equal" for i in ids)
            weights = np.array([rows[6][i][denominator] for i in ids])
            if any(rows[p][i][denominator] != rows[6][i][denominator] for i in ids):
                raise ValueError("Reference denominators differ")
            differences = np.array([rows[p][i][numerator] - rows[6][i][numerator] for i in ids])
            distribution = differences[samples].sum(axis=1) / weights[samples].sum(axis=1)
            result[metric] = {"image_counts": dict(counts), "micro_delta_candidate_minus_psm6": float(differences.sum() / weights.sum()),
                              "paired_image_bootstrap_percentile_95_interval": np.quantile(distribution, [.025, .975]).tolist()}
        results[str(p)] = result
    save(target, {"seed": 42, "resamples": 5000, "sampling_unit": "image; paired across PSMs",
        "interpretation": "Exploratory post-run uncertainty, not a preregistered hypothesis test. Treats images as independent; does not correct source annotation/alignment errors or receipt-level dependence.",
        "script_sha256": sha(__file__), "results": results})
    print(results)


if __name__ == "__main__":
    main()
