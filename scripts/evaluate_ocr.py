#!/usr/bin/env python3
"""Compute local full-page or recognition-crop OCR metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from docucheck.data.preprocessing import write_jsonl  # noqa: E402
from docucheck.evaluation.metrics import evaluate_crop_records, evaluate_ocr_records  # noqa: E402
from docucheck.ocr.inference import load_manifest  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/processed/manifest.jsonl")
    parser.add_argument("--predictions", default="outputs/ocr/tesseract_internal_dev/predictions.jsonl")
    parser.add_argument("--runtime", default=None, help="Runtime metadata JSON used for latency context")
    parser.add_argument("--split", default="internal_dev")
    parser.add_argument("--output-dir", default="outputs/ocr/evaluation")
    parser.add_argument("--mode", choices=("full-page", "crop"), default="full-page")
    parser.add_argument(
        "--iou-threshold", type=float, default=0.5,
        help="Recorded for future detection evaluation; current word/region pairing has no detection F1",
    )
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
    try:
        if args.mode == "crop":
            summary, image_details = evaluate_crop_records(manifest, predictions, split=args.split)
            region_details = None
        else:
            summary, image_details, region_details = evaluate_ocr_records(
                manifest, predictions, split=args.split, iou_threshold=args.iou_threshold
            )
    except ValueError as error:
        print(f"OCR evaluation failed: {error}", file=sys.stderr)
        return 2
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
        "model_sha256": runtime.get("model_sha256"),
        "device": runtime.get("device"),
        "page_segmentation_mode": runtime.get("preprocessing", {}).get("page_segmentation_mode"),
        "inference_image_count": runtime.get("manifest_record_count"),
        "images_failed": runtime.get("images_failed"),
        "mean_successful_image_latency_seconds": runtime.get("mean_successful_image_latency_seconds"),
        "cpu_count_logical": runtime.get("cpu_count_logical"),
        "platform": runtime.get("platform"),
    }
    summary["evaluation_environment"] = {
        "python_version": platform.python_version(),
        "cpu_count_logical": os.cpu_count(),
        "platform": platform.platform(),
    }
    summary["input_sha256"] = {
        name: hashlib.sha256(paths[name].read_bytes()).hexdigest()
        for name in ("manifest", "predictions")
    }
    if runtime_path and runtime_path.is_file():
        summary["input_sha256"]["runtime"] = hashlib.sha256(runtime_path.read_bytes()).hexdigest()
    output = paths["output_dir"]
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.mode == "crop":
        write_jsonl(output / "per_crop_metrics.jsonl", image_details)
        summary_keys = (
            "split", "split_role", "metric_status", "evaluated_crops", "excluded_crops",
            "empty_hypothesis_crops", "cer", "wer", "exact_match_rate",
        )
    else:
        write_jsonl(output / "per_image_metrics.jsonl", image_details)
        write_jsonl(output / "per_region_alignment.jsonl", region_details)
        summary_keys = (
            "split", "metric_status", "images_with_full_page_ground_truth", "images_with_ground_truth_and_predictions",
            "evaluated_ground_truth_regions", "excluded_invalid_geometry_regions", "cer", "wer",
            "unmatched_ground_truth_regions", "unmatched_ground_truth_region_rate",
            "unassigned_prediction_word_boxes", "unassigned_prediction_word_box_rate", "detection_metrics",
        )
    print(json.dumps({key: summary[key] for key in summary_keys}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
