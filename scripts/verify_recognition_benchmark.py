#!/usr/bin/env python3
"""Verify saved recognition evidence and recompute metrics without OCR inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docucheck.evaluation.metrics import evaluate_crop_records  # noqa: E402
from docucheck.ocr.inference import load_manifest  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches_locked_source(name, current_digest, locked_digest, revisions):
    """Accept recorded editorial revisions only for documentation, never code."""
    if current_digest == locked_digest:
        return True
    if not name.startswith("docs/") or not name.endswith(".md"):
        return False
    revision = revisions.get(name, {})
    return (revision.get("original_sha256") == locked_digest
            and revision.get("revised_sha256") == current_digest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/processed/recognition_manifest.jsonl")
    args = parser.parse_args(argv)
    run = args.run_dir.resolve()
    lock = json.loads((run / "locked_config.json").read_text(encoding="utf-8"))
    checks = []

    def require(condition, label):
        if not condition:
            raise ValueError(f"Verification failed: {label}")
        checks.append(label)

    require(digest(args.manifest) == lock["manifest_sha256"], "manifest SHA-256 matches locked input")
    require(digest(run / "audit.json") == lock["audit_sha256"], "audit SHA-256 matches locked audit")
    revision_path = run / "documentation_revisions.json"
    revisions = json.loads(revision_path.read_text(encoding="utf-8")) if revision_path.is_file() else {}
    for name, expected in lock["source_sha256"].items():
        current = digest(ROOT / name)
        label = "source matches lock" if current == expected else "document matches recorded editorial revision"
        require(matches_locked_source(name, current, expected, revisions), f"{label}: {name}")
    records = load_manifest(args.manifest)
    results = {}
    for split in ("official_train", "official_val"):
        directory = run / split
        predictions = load_manifest(directory / "predictions.jsonl")
        failures = load_manifest(directory / "failures.jsonl")
        runtime = json.loads((directory / "runtime.json").read_text(encoding="utf-8"))
        saved = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        details = load_manifest(directory / "per_crop_metrics.jsonl")
        summary, recomputed = evaluate_crop_records(records, predictions, split=split)
        for key, value in summary.items():
            require(saved.get(key) == value, f"{split}: recomputed {key}")
        require(details == recomputed, f"{split}: all per-crop metrics and text match predictions/GT")
        require(len(predictions) == lock["split_counts"][split] == runtime["images_succeeded"]
                == runtime["manifest_record_count"], f"{split}: complete prediction/runtime/manifest counts")
        require(len(failures) == runtime["images_failed"] == 0, f"{split}: zero execution failures")
        for key in ("engine_version", "model_sha256"):
            require(runtime[key] == lock[key], f"{split}: locked {key}")
        require(runtime["preprocessing"]["page_segmentation_mode"] == lock["psm"], f"{split}: locked PSM")
        require(runtime["preprocessing"]["ocr_engine_mode"] == lock["oem"], f"{split}: locked OEM")
        for name, path in (("manifest", args.manifest), ("predictions", directory / "predictions.jsonl"),
                           ("runtime", directory / "runtime.json")):
            require(digest(path) == saved["input_sha256"][name], f"{split}: evaluation input hash {name}")
        results[split] = {key: saved[key] for key in (
            "evaluated_crops", "cer", "wer", "exact_match_rate", "empty_hypothesis_crops")}
    report = {"status": "passed", "checks": checks, "results": results,
              "inference_rerun": False, "verification": "Full metric recomputation from saved predictions and original manifest"}
    (run / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "check_count": len(checks), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
