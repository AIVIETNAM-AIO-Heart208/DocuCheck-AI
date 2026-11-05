"""Validate and compare complete crop OCR evaluation runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docucheck.data.preprocessing import write_jsonl
from docucheck.evaluation.metrics import normalize_text
from docucheck.ocr.inference import load_manifest

ENGINES = ("tesseract", "vietocr", "paddleocr")


def _load_run(name: str, path: str | Path) -> dict[str, Any]:
    root = Path(path)
    runtime_path = root / "runtime.json"
    metrics_path = root / "metrics.json"
    details_path = root / "per_crop_metrics.jsonl"
    if not all(item.is_file() for item in (runtime_path, metrics_path, details_path)):
        raise ValueError(f"{name}: missing runtime.json, metrics.json, or per_crop_metrics.jsonl")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    details = load_manifest(details_path)
    for key in ("engine", "engine_version", "model_names", "model_source", "device", "split"):
        if not runtime.get(key):
            raise ValueError(f"{name}: missing runtime provenance {key}")
    if runtime["split"] != "official_val" or metrics.get("split") != "official_val":
        raise ValueError(f"{name}: expected official_val artifacts")
    if runtime.get("images_failed") or runtime.get("images_succeeded") != metrics.get("evaluated_crops"):
        raise ValueError(f"{name}: incomplete inference coverage")
    ids = [row.get("image_id") for row in details]
    if len(ids) != len(set(ids)) or len(ids) != metrics.get("evaluated_crops"):
        raise ValueError(f"{name}: invalid per-crop coverage")
    return {"runtime": runtime, "metrics": metrics, "details": {row["image_id"]: row for row in details}}


def compare_crop_runs(paths: dict[str, str | Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if set(paths) != set(ENGINES):
        raise ValueError(f"Expected comparison engines: {', '.join(ENGINES)}")
    runs = {name: _load_run(name, paths[name]) for name in ENGINES}
    id_sets = {name: set(run["details"]) for name, run in runs.items()}
    if len({frozenset(ids) for ids in id_sets.values()}) != 1:
        raise ValueError("Engine crop ID sets do not match")
    denominators = {
        (run["metrics"].get("ground_truth_characters"), run["metrics"].get("ground_truth_words"))
        for run in runs.values()
    }
    if len(denominators) != 1:
        raise ValueError("Engine ground-truth denominators do not match")

    rows = []
    for name, run in runs.items():
        runtime, metrics = run["runtime"], run["metrics"]
        rows.append({
            "engine_key": name,
            "engine": runtime["engine"],
            "engine_version": runtime["engine_version"],
            "model_names": runtime["model_names"],
            "model_source": runtime["model_source"],
            "model_sha256": runtime.get("model_sha256"),
            "device": runtime["device"],
            "successful_crops": runtime["images_succeeded"],
            "failed_crops": runtime["images_failed"],
            "mean_latency_seconds": runtime.get("mean_successful_image_latency_seconds"),
            "cer": metrics["cer"],
            "character_errors": metrics["character_errors"],
            "ground_truth_characters": metrics["ground_truth_characters"],
            "wer": metrics["wer"],
            "word_errors": metrics["word_errors"],
            "ground_truth_words": metrics["ground_truth_words"],
            "empty_hypothesis_crops": metrics["empty_hypothesis_crops"],
            "text_normalization_policy": metrics["text_normalization_policy"],
        })
    rows.sort(key=lambda row: (row["cer"], row["engine_key"]))

    per_crop = []
    for image_id in sorted(next(iter(id_sets.values()))):
        first = runs[ENGINES[0]]["details"][image_id]
        engines = {}
        for name in ENGINES:
            detail = runs[name]["details"][image_id]
            if detail["text_gt"] != first["text_gt"]:
                raise ValueError(f"Ground-truth transcript mismatch for crop {image_id}")
            engines[name] = {
                key: detail[key]
                for key in ("text_pred", "char_errors", "gt_characters", "cer", "word_errors", "gt_words", "wer")
            }
        per_crop.append({
            "image_id": image_id,
            "text_gt": first["text_gt"],
            "engines": engines,
            "disagreement": len({normalize_text(row["text_pred"]) for row in engines.values()}) > 1,
        })
    return {"split": "official_val", "engines": rows}, per_crop


def write_comparison(output_dir: str | Path, summary: dict[str, Any], details: list[dict[str, Any]]) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_jsonl(output / "per_crop_comparison.jsonl", details)
