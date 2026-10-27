"""Batch OCR inference and privacy-local prediction artifacts."""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Any

from docucheck.data.loader import resolve_dataset_root
from docucheck.ocr.baseline import TesseractBaseline


def load_manifest(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def run_batch(
    records: list[dict[str, Any]],
    *,
    dataset_root: str | Path | None = None,
    split: str = "internal_dev",
    output_dir: str | Path = "outputs/ocr/paddle",
    limit: int | None = None,
    engine: TesseractBaseline | None = None,
    tessdata_dir: str | Path = "outputs/ocr/tessdata_fast",
) -> dict[str, Any]:
    """Run predictions on one declared manifest split, recording per-image failures."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer")
    root = resolve_dataset_root(dataset_root)
    selected = [record for record in records if record.get("split") == split]
    selected = sorted(selected, key=lambda record: record["image_id"])
    if limit is not None:
        selected = selected[:limit]
    engine = engine or TesseractBaseline(tessdata_dir=tessdata_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prediction_path = output / "predictions.jsonl"
    failures_path = output / "failures.jsonl"
    inference_started = time.perf_counter()
    predictions = []
    failures = []
    per_image_seconds = []
    for record in selected:
        image_path = root / record["image_path"]
        image_started = time.perf_counter()
        try:
            rows = engine.predict(image_path)
            predictions.append(
                {
                    "image_id": record["image_id"],
                    "source_split": record.get("source_split"),
                    "split": split,
                    "status": "ok",
                    "predictions": rows,
                    "latency_seconds": time.perf_counter() - image_started,
                }
            )
            per_image_seconds.append(predictions[-1]["latency_seconds"])
        except Exception as error:  # Record failures; do not reinterpret them as empty OCR.
            failures.append(
                {
                    "image_id": record["image_id"],
                    "split": split,
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                }
            )

    for path, rows in ((prediction_path, predictions), (failures_path, failures)):
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    metadata = {
        "engine": "Tesseract",
        "engine_version": engine.engine_version,
        "python_version": platform.python_version(),
        "model_names": engine.model_names,
        "model_source": engine.model_source,
        "model_sha256": engine.model_sha256,
        "language": engine.language,
        "device": engine.device,
        "preprocessing": {
            "page_segmentation_mode": engine.page_segmentation_mode,
            "ocr_engine_mode": engine.ocr_engine_mode,
            "output": "word-level TSV with axis-aligned polygons",
        },
        "split": split,
        "manifest_record_count": len(selected),
        "images_succeeded": len(predictions),
        "images_failed": len(failures),
        "model_load_seconds": engine.model_load_seconds,
        "inference_elapsed_seconds": time.perf_counter() - inference_started,
        "mean_successful_image_latency_seconds": (
            sum(per_image_seconds) / len(per_image_seconds) if per_image_seconds else None
        ),
        "prediction_file": prediction_path.name,
        "failure_file": failures_path.name,
    }
    (output / "runtime.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata
