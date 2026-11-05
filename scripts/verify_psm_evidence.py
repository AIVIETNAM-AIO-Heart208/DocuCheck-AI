#!/usr/bin/env python3
"""Independently check saved edit distances and seal/check a local PSM evidence inventory."""
import argparse
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_psm_comparison import PSMS, load_manifest, read, save, sha


def distance(a, b):
    # Full matrix reference implementation, independent of production metrics.
    matrix = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        matrix[i][0] = i
    for j in range(len(b) + 1):
        matrix[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1,
                               matrix[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    return matrix[-1][-1]


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def verify_distances(output):
    results = []
    for psm in PSMS:
        folder = output / f"psm{psm}"
        metrics = read(folder / "metrics.json")
        regions = load_manifest(folder / "per_region_alignment.jsonl")
        errors = chars = word_errors = words = 0
        for r in regions:
            gt, pred = normalize(r["text_gt"]), normalize(r["text_pred"])
            ce, we = distance(gt, pred), distance(gt.split(), pred.split())
            if (ce, len(gt), we, len(gt.split())) != (r["char_errors"], r["gt_characters"], r["word_errors"], r["gt_words"]):
                raise ValueError(f"Independent distance mismatch: PSM {psm}, {r['image_id']}")
            errors += ce
            chars += len(gt)
            word_errors += we
            words += len(gt.split())
        if (errors, chars, word_errors, words) != tuple(metrics[k] for k in
                ("character_errors", "ground_truth_characters", "word_errors", "ground_truth_words")):
            raise ValueError(f"Independent aggregate mismatch: PSM {psm}")
        results.append({"psm": psm, "regions_checked": len(regions), "character_errors": errors,
                        "ground_truth_characters": chars, "word_errors": word_errors, "ground_truth_words": words})
    return {"status": "passed", "scope": "Independent normalization/edit distances on saved aligned text; alignment verified separately, not independently adjudicated.",
            "results": results}


def inventory(output):
    return {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p != output / "artifact_manifest.json"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--seal", action="store_true", help="Create initial inventory; refuses to replace existing seal")
    args = parser.parse_args(argv)
    output = args.run_dir.resolve()
    seal = output / "artifact_manifest.json"
    if args.seal:
        if seal.exists():
            parser.error("Inventory already exists; do not overwrite historical evidence")
        save(output / "independent_metrics_verification.json", verify_distances(output))
        save(seal, inventory(output))
    else:
        if read(seal) != inventory(output):
            raise ValueError("Evidence inventory differs: missing, added or changed files")
        if read(output / "independent_metrics_verification.json") != verify_distances(output):
            raise ValueError("Independent metrics report mismatch")
    print(json.dumps({"status": "passed", "artifact_count": len(read(seal))}))


if __name__ == "__main__":
    main()
