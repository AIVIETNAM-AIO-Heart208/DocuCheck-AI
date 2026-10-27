#!/usr/bin/env python3
"""Compute local OCR recognition metrics where full-page transcription GT exists."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from docucheck.data.preprocessing import write_jsonl  # noqa: E402
from docucheck.evaluation.metrics import evaluate_ocr_records, greedy_polygon_matching, detection_scores  # noqa: E402
from docucheck.ocr.inference import load_manifest  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/processed/manifest.jsonl")
    parser.add_argument("--predictions", default="outputs/ocr/tesseract_internal_dev/predictions.jsonl")
    parser.add_argument("--runtime", default=None, help="Runtime metadata JSON used for latency context")
    parser.add_argument("--split", default="internal_dev")
    parser.add_argument("--output-dir", default="outputs/ocr/evaluation")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = {}
    for name in ("manifest", "predictions", "runtime", "output_dir"):
        value = getattr(args, name)
        if value is None:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = REPOSITORY_ROOT / path
        paths[name] = path
    if not paths["manifest"].is_file() or not paths["predictions"].is_file():
        print("Manifest or prediction file is missing", file=sys.stderr)
        return 2
    manifest = load_manifest(paths["manifest"])
    predictions = load_manifest(paths["predictions"])
    summary, image_details, region_details = evaluate_ocr_records(
        manifest, predictions, split=args.split, iou_threshold=args.iou_threshold
    )
    runtime = {}
    runtime_path = paths.get("runtime")
    if runtime_path is None:
        candidate = paths["predictions"].parent / "runtime.json"
        runtime_path = candidate if candidate.is_file() else None
    if runtime_path and runtime_path.is_file():
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    summary["inference_runtime_context"] = {
        "engine": runtime.get("engine"),
        "engine_version": runtime.get("engine_version"),
        "device": runtime.get("device"),
        "inference_image_count": runtime.get("manifest_record_count"),
        "images_failed": runtime.get("images_failed"),
        "mean_successful_image_latency_seconds": runtime.get("mean_successful_image_latency_seconds"),
        "cpu_count_logical": __import__("os").cpu_count(),
        "platform": platform.platform(),
    }
    output = paths["output_dir"]
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(output / "per_image_metrics.jsonl", image_details)
    write_jsonl(output / "per_region_alignment.jsonl", region_details)
    print(json.dumps({key: summary[key] for key in (
        "split", "metric_status", "images_with_full_page_ground_truth", "images_with_ground_truth_and_predictions",
        "evaluated_ground_truth_regions", "excluded_invalid_geometry_regions", "cer", "wer",
        "unmatched_ground_truth_regions", "unassigned_prediction_word_boxes", "detection_metrics",
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
