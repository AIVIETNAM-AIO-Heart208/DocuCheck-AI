"""Receipt text detection plus VietOCR recognition orchestration."""

from __future__ import annotations

import json
import os
import platform
import tempfile
import time
from pathlib import Path
from typing import Any

from docucheck.data.loader import resolve_dataset_root
from docucheck.ocr.detectors import crop_polygon


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _failure(
    *,
    image_id: str,
    split: str,
    stage: str,
    error: Exception | None = None,
    candidate_id: str | None = None,
    region_index: int | None = None,
    validation_issue: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "image_id": image_id,
        "split": split,
        "stage": stage,
    }
    if candidate_id is not None:
        row["candidate_id"] = candidate_id
    if region_index is not None:
        row["region_index"] = region_index
    if validation_issue is not None:
        row["error_type"] = "InvalidDetectorGeometry"
        row["error_message"] = validation_issue
    elif error is not None:
        row["error_type"] = type(error).__name__
        row["error_message"] = str(error)
    return row


def run_hybrid_batch(
    records: list[dict[str, Any]],
    *,
    dataset_root: str | Path | None = None,
    split: str = "internal_dev",
    output_dir: str | Path = "outputs/ocr/paddle_vietocr",
    limit: int | None = None,
    detector: Any,
    recognizer: Any,
) -> dict[str, Any]:
    """Run a text detector followed by VietOCR on receipt records."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer")
    root = resolve_dataset_root(dataset_root)
    selected = [record for record in records if record.get("split") == split]
    if any(record.get("source_subset") == "text_recognition" for record in selected):
        raise ValueError("Hybrid receipt inference does not accept recognition-crop records")
    selected = sorted(selected, key=lambda record: record["image_id"])
    if limit is not None:
        selected = selected[:limit]

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prediction_path = output / "predictions.jsonl"
    failures_path = output / "failures.jsonl"
    predictions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    image_seconds: list[float] = []
    candidate_count = 0
    detected_candidate_count = 0
    recognized_count = 0
    empty_hypotheses = 0
    candidate_failures = 0
    receipt_failures = 0
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="docucheck-hybrid-") as crop_dir:
        for record in selected:
            image_id = record["image_id"]
            image_path = root / record["image_path"]
            image_started = time.perf_counter()
            image_failures: list[dict[str, Any]] = []
            image_predictions: list[dict[str, Any]] = []
            try:
                detected_candidates = detector.predict(image_path)
                detected_candidate_count += len(detected_candidates)
                for issue in getattr(detector, "last_issues", []):
                    issue_failure = _failure(
                        image_id=image_id,
                        split=split,
                        stage="detection",
                        region_index=issue.get("region_index"),
                        validation_issue=issue.get("validation_issue"),
                    )
                    image_failures.append(issue_failure)
                    candidate_failures += 1

                candidates = [
                    {
                        **candidate,
                        "candidate_id": f"{image_id}:candidate-{ordinal:04d}",
                    }
                    for ordinal, candidate in enumerate(detected_candidates, 1)
                ]

                for ordinal, candidate in enumerate(candidates, 1):
                    candidate_id = candidate["candidate_id"]
                    candidate_count += 1
                    crop_path = Path(crop_dir) / f"{len(predictions):06d}-{ordinal:04d}.png"
                    try:
                        try:
                            crop_polygon(image_path, candidate["polygon"], crop_path)
                        except Exception as error:
                            image_failures.append(_failure(
                                image_id=image_id,
                                split=split,
                                stage="crop",
                                error=error,
                                candidate_id=candidate_id,
                                region_index=candidate.get("region_index"),
                            ))
                            candidate_failures += 1
                            continue
                        recognized = recognizer.predict(crop_path)
                        if len(recognized) > 1:
                            raise ValueError("VietOCR returned more than one prediction for one crop")
                        if recognized:
                            text = recognized[0].get("text", "")
                            confidence = recognized[0].get("confidence")
                            recognition_status = "ok" if text else "empty"
                        else:
                            text = ""
                            confidence = None
                            recognition_status = "empty"
                        if not text:
                            empty_hypotheses += 1
                        image_predictions.append({
                            "candidate_id": candidate_id,
                            "region_index": candidate.get("region_index"),
                            "polygon": candidate["polygon"],
                            "detector_confidence": candidate.get("confidence"),
                            "text": text,
                            "recognition_confidence": confidence,
                            "recognition_status": recognition_status,
                            "status": "ok",
                        })
                        recognized_count += 1
                    except Exception as error:  # Preserve candidate failures separately from empty text.
                        image_failures.append(_failure(
                            image_id=image_id,
                            split=split,
                            stage="recognition",
                            error=error,
                            candidate_id=candidate_id,
                            region_index=candidate.get("region_index"),
                        ))
                        candidate_failures += 1
            except Exception as error:
                image_failures.append(_failure(
                    image_id=image_id,
                    split=split,
                    stage="detection",
                    error=error,
                ))
                receipt_failures += 1

            status = "ok" if not image_failures else "partial"
            predictions.append({
                "image_id": image_id,
                "source_split": record.get("source_split"),
                "source_subset": record.get("source_subset"),
                "split": split,
                "status": status,
                "predictions": image_predictions,
                "latency_seconds": time.perf_counter() - image_started,
            })
            failures.extend(image_failures)
            if status == "ok":
                image_seconds.append(predictions[-1]["latency_seconds"])

    metadata = {
        "pipeline": (
            "phocr-detector-vietocr"
            if detector.engine_name == "PHOCRTextDetection"
            else "paddle-detector-vietocr"
        ),
        "detector": detector.engine_name,
        "detector_version": detector.engine_version,
        "detector_model_names": detector.model_names,
        "detector_model_source": detector.model_source,
        "detector_model_sha256": detector.model_sha256,
        "detector_device": detector.device,
        "recognizer": recognizer.engine_name,
        "recognizer_version": recognizer.engine_version,
        "recognizer_model_names": recognizer.model_names,
        "recognizer_model_source": recognizer.model_source,
        "recognizer_model_sha256": recognizer.model_sha256,
        "recognizer_device": recognizer.device,
        "preprocessing": {
            "detector": detector.preprocessing,
            "crop": {
                "mode": "perspective-rectify",
                "output": "temporary PNG",
                "padding_percent": 0,
            },
            "recognizer": recognizer.preprocessing,
        },
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count_logical": os.cpu_count(),
        "batch_size": 1,
        "workers": 1,
        "split": split,
        "manifest_record_count": len(selected),
        "images_succeeded": sum(row["status"] == "ok" for row in predictions),
        "images_partial": sum(row["status"] == "partial" for row in predictions),
        "images_failed": receipt_failures,
        "detected_candidates": candidate_count,
        "source_detected_candidates": detected_candidate_count,
        "recognized_candidates": recognized_count,
        "empty_hypotheses": empty_hypotheses,
        "candidate_failures": candidate_failures,
        "receipt_failures": receipt_failures,
        "detector_model_load_seconds": detector.model_load_seconds,
        "recognizer_model_load_seconds": recognizer.model_load_seconds,
        "inference_elapsed_seconds": time.perf_counter() - started,
        "mean_successful_image_latency_seconds": (
            sum(image_seconds) / len(image_seconds) if image_seconds else None
        ),
        "prediction_file": prediction_path.name,
        "failure_file": failures_path.name,
    }
    _write_jsonl(prediction_path, predictions)
    _write_jsonl(failures_path, failures)
    (output / "runtime.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata
