"""Receipt text detection plus VietOCR recognition orchestration."""

from __future__ import annotations

import json
import os
import platform
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

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


def merge_line_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group detector candidates into deterministic line-level crops."""
    items = []
    for index, candidate in enumerate(candidates):
        points = np.asarray(candidate["polygon"], dtype=np.float32)
        x1, y1 = points.min(axis=0)
        x2, y2 = points.max(axis=0)
        items.append({
            "index": index,
            "candidate": candidate,
            "candidate_id": candidate.get("candidate_id", f"candidate-{index + 1:04d}"),
            "x1": float(x1),
            "y1": float(y1),
            "x2": float(x2),
            "y2": float(y2),
            "cy": float((y1 + y2) / 2),
            "height": max(1.0, float(y2 - y1)),
        })
    items.sort(key=lambda item: (item["cy"], item["x1"], item["index"]))
    groups: list[dict[str, Any]] = []
    for item in items:
        selected = None
        for group in groups:
            min_height = min(item["height"], group["height"])
            overlap = max(0.0, min(item["y2"], group["y2"]) - max(item["y1"], group["y1"])) / min_height
            center_gap = abs(item["cy"] - group["cy"])
            horizontal_gap = max(0.0, item["x1"] - group["x2"], group["x1"] - item["x2"])
            if (overlap >= 0.30 or center_gap <= 0.50 * min_height) and horizontal_gap <= 2.5 * max(item["height"], group["height"]):
                selected = group
                break
        if selected is None:
            selected = {
                "items": [],
                "x1": item["x1"],
                "y1": item["y1"],
                "x2": item["x2"],
                "y2": item["y2"],
                "cy": item["cy"],
                "height": item["height"],
            }
            groups.append(selected)
        selected["items"].append(item)
        selected["x1"] = min(selected["x1"], item["x1"])
        selected["y1"] = min(selected["y1"], item["y1"])
        selected["x2"] = max(selected["x2"], item["x2"])
        selected["y2"] = max(selected["y2"], item["y2"])
        selected["cy"] = sum(member["cy"] for member in selected["items"]) / len(selected["items"])
        selected["height"] = selected["y2"] - selected["y1"]
    groups.sort(key=lambda group: (group["y1"], group["x1"]))

    merged = []
    for ordinal, group in enumerate(groups, 1):
        members = sorted(group["items"], key=lambda item: (item["x1"], item["index"]))
        member_candidates = [member["candidate"] for member in members]
        polygon = (
            member_candidates[0]["polygon"]
            if len(member_candidates) == 1
            else [[group["x1"], group["y1"]], [group["x2"], group["y1"]], [group["x2"], group["y2"]], [group["x1"], group["y2"]]]
        )
        confidences = [candidate.get("confidence") for candidate in member_candidates if candidate.get("confidence") is not None]
        merged.append({
            "line_index": ordinal,
            "polygon": polygon,
            "confidence": min(confidences) if confidences else None,
            "source_candidate_ids": [member["candidate_id"] for member in members],
            "region_index": member_candidates[0].get("region_index"),
        })
    return merged


def run_hybrid_batch(
    records: list[dict[str, Any]],
    *,
    dataset_root: str | Path | None = None,
    split: str = "internal_dev",
    output_dir: str | Path = "outputs/ocr/paddle_vietocr",
    limit: int | None = None,
    detector: Any,
    recognizer: Any,
    merge_lines: bool = False,
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

                candidates = []
                for ordinal, candidate in enumerate(detected_candidates, 1):
                    candidates.append({
                        **candidate,
                        "candidate_id": f"{image_id}:candidate-{ordinal:04d}",
                    })
                if merge_lines:
                    candidates = merge_line_candidates(candidates)

                for ordinal, candidate in enumerate(candidates, 1):
                    candidate_id = (
                        f"{image_id}:line-{ordinal:04d}"
                        if merge_lines
                        else candidate["candidate_id"]
                    )
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
                        if merge_lines:
                            image_predictions[-1]["source_candidate_ids"] = candidate["source_candidate_ids"]
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
            "line_merge": {
                "enabled": merge_lines,
                "vertical_overlap_threshold": 0.30,
                "center_gap_height_ratio": 0.50,
                "horizontal_gap_height_ratio": 2.5,
            },
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
        "pre_merge_candidates": detected_candidate_count,
        "post_merge_candidates": candidate_count,
        "recognized_candidates": recognized_count,
        "empty_hypotheses": empty_hypotheses,
        "merged_candidates": candidate_count if merge_lines else None,
        "line_merge": {
            "enabled": merge_lines,
            "vertical_overlap_threshold": 0.30,
            "center_gap_height_ratio": 0.50,
            "horizontal_gap_height_ratio": 2.5,
        },
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
