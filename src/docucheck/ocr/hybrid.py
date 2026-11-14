"""Receipt text detection plus VietOCR recognition orchestration."""

from __future__ import annotations

import json
import math
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


def _polygons_touch(first: list[list[float]], second: list[list[float]]) -> bool:
    """Treat overlap or boundary contact between convex detector boxes as a collision."""
    first_points = np.asarray(first, dtype=np.float64)
    second_points = np.asarray(second, dtype=np.float64)
    for polygon in (first_points, second_points):
        for index, point in enumerate(polygon):
            edge = polygon[(index + 1) % len(polygon)] - point
            axis = np.asarray([-edge[1], edge[0]])
            first_projection = first_points @ axis
            second_projection = second_points @ axis
            separated = (
                first_projection.max() < second_projection.min()
                or second_projection.max() < first_projection.min()
            )
            if separated:
                return False
    return True


def _expanded_polygon(polygon: list[list[float]], padding_percent: float) -> list[list[float]]:
    points = np.asarray(polygon, dtype=np.float64)
    center = points.mean(axis=0)
    return (center + (points - center) * (1 + padding_percent / 100)).tolist()


def _horizontal_padding_collision(
    first: dict[str, Any],
    second: dict[str, Any],
    padding_percent: float,
) -> bool:
    if padding_percent <= 0:
        return False
    first_points = np.asarray(first["polygon"], dtype=np.float64)
    second_points = np.asarray(second["polygon"], dtype=np.float64)
    if not _same_line(first_points, second_points):
        return False
    first_expanded = np.asarray(_expanded_polygon(first["polygon"], padding_percent))
    second_expanded = np.asarray(_expanded_polygon(second["polygon"], padding_percent))
    first_x = (first_expanded[:, 0].min(), first_expanded[:, 0].max())
    second_x = (second_expanded[:, 0].min(), second_expanded[:, 0].max())
    return (
        (
            first_x[0] <= second_points[:, 0].max()
            and second_points[:, 0].min() <= first_x[1]
        )
        or (
            second_x[0] <= first_points[:, 0].max()
            and first_points[:, 0].min() <= second_x[1]
        )
    )


def _same_line(first: np.ndarray, second: np.ndarray) -> bool:
    first_min, first_max = first[:, 1].min(), first[:, 1].max()
    second_min, second_max = second[:, 1].min(), second[:, 1].max()
    first_height = first_max - first_min
    second_height = second_max - second_min
    overlap = max(0.0, min(first_max, second_max) - max(first_min, second_min))
    vertical_overlap = overlap / min(first_height, second_height)
    return vertical_overlap >= 0.5


def _merge_predictions(
    image_id: str,
    predictions: list[dict[str, Any]],
    collision_pairs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    by_id = {prediction["candidate_id"]: prediction for prediction in predictions}
    links = {candidate_id: set() for candidate_id in by_id}
    for first_id, second_id in collision_pairs:
        if first_id in by_id and second_id in by_id:
            links[first_id].add(second_id)
            links[second_id].add(first_id)

    groups: list[list[dict[str, Any]]] = []
    visited: set[str] = set()
    for candidate_id in sorted(by_id, key=lambda value: _prediction_sort_key(by_id[value])):
        if candidate_id in visited or not links[candidate_id]:
            continue
        stack = [candidate_id]
        visited.add(candidate_id)
        member_ids = []
        while stack:
            current = stack.pop()
            member_ids.append(current)
            for neighbor in sorted(links[current]):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        members = [by_id[member_id] for member_id in member_ids]
        groups.append(sorted(members, key=_prediction_left_to_right_key))

    merged = []
    for ordinal, members in enumerate(
        sorted(groups, key=lambda group: min(_prediction_sort_key(member) for member in group)), 1
    ):
        points = np.asarray([point for member in members for point in member["polygon"]], dtype=np.float64)
        texts = [member["text"] for member in members if member["text"]]
        recognition_confidences = [member["recognition_confidence"] for member in members if member["recognition_confidence"] is not None]
        detector_confidences = [member["detector_confidence"] for member in members if member["detector_confidence"] is not None]
        min_x, min_y = points.min(axis=0)
        max_x, max_y = points.max(axis=0)
        merged.append({
            "candidate_id": f"{image_id}:merged-candidate-{ordinal:04d}",
            "source_candidate_ids": [member["candidate_id"] for member in members],
            "polygon": [[float(min_x), float(min_y)], [float(max_x), float(min_y)],
                        [float(max_x), float(max_y)], [float(min_x), float(max_y)]],
            "detector_confidence": min(detector_confidences) if detector_confidences else None,
            "text": " ".join(texts),
            "recognition_confidence": min(recognition_confidences) if recognition_confidences else None,
            "recognition_status": "ok" if texts else "empty",
            "status": "ok",
        })
    return merged


def _prediction_sort_key(prediction: dict[str, Any]) -> tuple[float, float, str]:
    points = np.asarray(prediction["polygon"], dtype=np.float64)
    return float(points[:, 1].min()), float(points[:, 0].min()), prediction["candidate_id"]


def _prediction_left_to_right_key(prediction: dict[str, Any]) -> tuple[float, float, str]:
    points = np.asarray(prediction["polygon"], dtype=np.float64)
    return float(points[:, 0].min()), float(points[:, 1].min()), prediction["candidate_id"]


def run_hybrid_batch(
    records: list[dict[str, Any]],
    *,
    dataset_root: str | Path | None = None,
    split: str = "internal_dev",
    output_dir: str | Path = "outputs/ocr/paddle_vietocr",
    limit: int | None = None,
    detector: Any,
    recognizer: Any,
    crop_padding_percent: float = 0,
) -> dict[str, Any]:
    """Run a text detector followed by VietOCR on receipt records."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer")
    try:
        crop_padding_percent = float(crop_padding_percent)
    except (TypeError, ValueError) as error:
        raise ValueError("crop_padding_percent must be a finite non-negative number") from error
    if not math.isfinite(crop_padding_percent) or crop_padding_percent < 0:
        raise ValueError("crop_padding_percent must be a finite non-negative number")
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
    padding_fallback_candidates = 0
    merged_candidate_count = 0
    merged_group_count = 0
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="docucheck-hybrid-") as crop_dir:
        for record in selected:
            image_id = record["image_id"]
            image_path = root / record["image_path"]
            image_started = time.perf_counter()
            image_failures: list[dict[str, Any]] = []
            image_predictions: list[dict[str, Any]] = []
            collision_pairs: list[tuple[str, str]] = []
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
                collision_pairs = []
                for index, candidate in enumerate(candidates):
                    for other in candidates[index + 1:]:
                        if _horizontal_padding_collision(candidate, other, crop_padding_percent):
                            collision_pairs.append((candidate["candidate_id"], other["candidate_id"]))
                effective_padding: dict[str, float] = {}
                for candidate in candidates:
                    padding = crop_padding_percent
                    if padding:
                        expanded = _expanded_polygon(candidate["polygon"], padding)
                        if any(
                            other is not candidate
                            and _polygons_touch(expanded, other["polygon"])
                            for other in candidates
                        ):
                            padding = 0
                            padding_fallback_candidates += 1
                    effective_padding[candidate["candidate_id"]] = padding

                for ordinal, candidate in enumerate(candidates, 1):
                    candidate_id = candidate["candidate_id"]
                    candidate_count += 1
                    crop_path = Path(crop_dir) / f"{len(predictions):06d}-{ordinal:04d}.png"
                    try:
                        try:
                            crop_polygon(
                                image_path,
                                candidate["polygon"],
                                crop_path,
                                padding_percent=effective_padding[candidate_id],
                            )
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
                            "crop_padding_percent": effective_padding[candidate_id],
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
            prediction_row = {
                "image_id": image_id,
                "source_split": record.get("source_split"),
                "source_subset": record.get("source_subset"),
                "split": split,
                "status": status,
                "predictions": image_predictions,
                "latency_seconds": time.perf_counter() - image_started,
            }
            if detector.engine_name == "PHOCRTextDetection":
                merged_predictions = _merge_predictions(image_id, image_predictions, collision_pairs)
                prediction_row["merged_predictions"] = merged_predictions
                merged_candidate_count += sum(len(row["source_candidate_ids"]) for row in merged_predictions)
                merged_group_count += len(merged_predictions)
            predictions.append(prediction_row)
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
                "padding_percent": crop_padding_percent,
                "padding_fallback_percent": 0,
                "padding_fallback_candidates": padding_fallback_candidates,
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
    if detector.engine_name == "PHOCRTextDetection":
        metadata["merged_candidates"] = merged_candidate_count
        metadata["merged_groups"] = merged_group_count
        metadata["postprocessing"] = {
            "mode": "post-ocr-horizontal-padding-collision",
            "recognizer_reinvoked": False,
        }
    _write_jsonl(prediction_path, predictions)
    _write_jsonl(failures_path, failures)
    (output / "runtime.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata
