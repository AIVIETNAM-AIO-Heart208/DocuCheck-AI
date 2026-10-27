"""Text and polygon metrics for OCR prediction analysis."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any

import cv2
import numpy as np

NORMALIZATION_POLICY = "Unicode NFKC, casefold, collapse whitespace; preserve Vietnamese diacritics and punctuation"
WER_TOKENIZATION_POLICY = "Whitespace-separated tokens (Vietnamese syllables, not linguistic word segmentation)"


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(value.split())


def edit_distance(reference: str, hypothesis: str) -> int:
    """Compute Levenshtein distance with O(min(n,m)) memory."""
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for i, ref_char in enumerate(reference, 1):
        current = [i]
        for j, hyp_char in enumerate(hypothesis, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (ref_char != hyp_char),
            ))
        previous = current
    return previous[-1]


def cer(reference: str, hypothesis: str) -> tuple[int, int]:
    ref, hyp = normalize_text(reference), normalize_text(hypothesis)
    return edit_distance(ref, hyp), len(ref)


def wer(reference: str, hypothesis: str) -> tuple[int, int]:
    ref, hyp = normalize_text(reference).split(), normalize_text(hypothesis).split()
    if len(ref) < len(hyp):
        ref, hyp = hyp, ref
    previous = list(range(len(hyp) + 1))
    for i, ref_token in enumerate(ref, 1):
        current = [i]
        for j, hyp_token in enumerate(hyp, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (ref_token != hyp_token),
            ))
        previous = current
    return previous[-1], len(normalize_text(reference).split())


def polygon_area(polygon: list[list[float]]) -> float:
    points = np.asarray(polygon, dtype=np.float32)
    return float(abs(cv2.contourArea(points))) if points.ndim == 2 and len(points) >= 3 else 0.0


def polygon_iou(first: list[list[float]], second: list[list[float]]) -> float:
    """IoU for convex source/prediction polygons."""
    area_first, area_second = polygon_area(first), polygon_area(second)
    if area_first <= 0 or area_second <= 0:
        return 0.0
    try:
        intersection, _ = cv2.intersectConvexConvex(
            np.asarray(first, dtype=np.float32), np.asarray(second, dtype=np.float32)
        )
    except cv2.error:
        return 0.0
    union = area_first + area_second - float(intersection)
    return float(intersection) / union if union > 0 else 0.0


def greedy_polygon_matching(
    predictions: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    *,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """One-to-one IoU matching for compatible prediction/GT region granularity."""
    if not 0 <= iou_threshold <= 1:
        raise ValueError("iou_threshold must be between 0 and 1")
    candidates = []
    for pred_index, prediction in enumerate(predictions):
        for gt_index, target in enumerate(ground_truth):
            iou = polygon_iou(prediction["polygon"], target["polygon"])
            if iou >= iou_threshold:
                candidates.append((iou, pred_index, gt_index))
    candidates.sort(key=lambda value: (-value[0], value[1], value[2]))
    matched_predictions, matched_ground_truth, matches = set(), set(), []
    for iou, pred_index, gt_index in candidates:
        if pred_index in matched_predictions or gt_index in matched_ground_truth:
            continue
        matched_predictions.add(pred_index)
        matched_ground_truth.add(gt_index)
        matches.append({"prediction_index": pred_index, "ground_truth_index": gt_index, "iou": iou})
    return {
        "matches": matches,
        "unmatched_prediction_indices": [i for i in range(len(predictions)) if i not in matched_predictions],
        "unmatched_ground_truth_indices": [i for i in range(len(ground_truth)) if i not in matched_ground_truth],
        "true_positives": len(matches),
        "false_positives": len(predictions) - len(matches),
        "false_negatives": len(ground_truth) - len(matches),
    }


def detection_scores(matching: dict[str, Any]) -> dict[str, float | int]:
    tp, fp, fn = matching["true_positives"], matching["false_positives"], matching["false_negatives"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def _center(polygon: list[list[float]]) -> tuple[float, float]:
    points = np.asarray(polygon, dtype=float)
    return float(points[:, 0].mean()), float(points[:, 1].mean())


def _contains_center(polygon: list[list[float]], point: tuple[float, float]) -> bool:
    contour = np.asarray(polygon, dtype=np.float32)
    return cv2.pointPolygonTest(contour, point, False) >= 0


def align_word_predictions_to_lines(
    predictions: list[dict[str, Any]], ground_truth: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[int]]:
    """Group word boxes by the GT line polygon containing each prediction center."""
    valid_ground_truth = [
        region for region in ground_truth
        if region.get("text_raw") is not None and region.get("polygon")
        and not region.get("validation_issues")
    ]
    assigned: dict[int, list[dict[str, Any]]] = defaultdict(list)
    unmatched_predictions = []
    for prediction_index, prediction in enumerate(predictions):
        polygon = prediction.get("polygon")
        if not polygon:
            unmatched_predictions.append(prediction_index)
            continue
        point = _center(polygon)
        containing = [
            (polygon_area(region["polygon"]), gt_index)
            for gt_index, region in enumerate(valid_ground_truth)
            if _contains_center(region["polygon"], point)
        ]
        if not containing:
            unmatched_predictions.append(prediction_index)
            continue
        _, best_gt_index = min(containing)
        assigned[best_gt_index].append(prediction)

    aligned = []
    for gt_index, target in enumerate(valid_ground_truth):
        words = assigned.get(gt_index, [])
        words.sort(key=lambda row: (_center(row["polygon"])[1], _center(row["polygon"])[0]))
        aligned.append(
            {
                "ground_truth_index": gt_index,
                "text_gt": target["text_raw"],
                "text_pred": " ".join(row["text"] for row in words),
                "polygon_gt": target["polygon"],
                "prediction_count": len(words),
                "matched": bool(words),
            }
        )
    return aligned, unmatched_predictions


def evaluate_ocr_records(
    manifest: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    split: str,
    iou_threshold: float = 0.5,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate text by center-in-GT-line grouping; detection score is gated separately."""
    manifest_by_id = {record["image_id"]: record for record in manifest if record.get("split") == split}
    predictions_by_id = {row["image_id"]: row for row in predictions if row.get("split") == split}
    image_details, region_details = [], []
    total_char_errors = total_gt_chars = total_word_errors = total_gt_words = 0
    excluded_invalid_regions = excluded_empty_transcriptions = evaluated_regions = 0
    unmatched_prediction_count = missing_region_count = images_with_gt = images_with_gt_predictions = 0
    for image_id in sorted(manifest_by_id):
        record = manifest_by_id[image_id]
        gt_regions = record.get("ocr_regions", [])
        if not gt_regions or record.get("ocr_ground_truth_status") != "available":
            continue
        images_with_gt += 1
        valid_gt = []
        for region in gt_regions:
            if region.get("validation_issues") or not region.get("polygon"):
                excluded_invalid_regions += 1
            elif region.get("text_raw") is None:
                excluded_empty_transcriptions += 1
            elif not normalize_text(region["text_raw"]):
                excluded_empty_transcriptions += 1
            else:
                valid_gt.append(region)
        prediction_row = predictions_by_id.get(image_id)
        predicted_regions = prediction_row.get("predictions", []) if prediction_row and prediction_row.get("status") == "ok" else []
        aligned, unmatched_predictions = align_word_predictions_to_lines(predicted_regions, valid_gt)
        if valid_gt and predicted_regions:
            images_with_gt_predictions += 1
        unmatched_prediction_count += len(unmatched_predictions)
        image_char_errors = image_gt_chars = image_word_errors = image_gt_words = 0
        for row in aligned:
            char_errors, gt_chars = cer(row["text_gt"], row["text_pred"])
            word_errors, gt_words = wer(row["text_gt"], row["text_pred"])
            total_char_errors += char_errors
            total_gt_chars += gt_chars
            total_word_errors += word_errors
            total_gt_words += gt_words
            image_char_errors += char_errors
            image_gt_chars += gt_chars
            image_word_errors += word_errors
            image_gt_words += gt_words
            evaluated_regions += 1
            missing_region_count += not row["matched"]
            region_details.append({"image_id": image_id, **row, "char_errors": char_errors, "gt_characters": gt_chars,
                                   "word_errors": word_errors, "gt_words": gt_words})
        image_details.append(
            {
                "image_id": image_id,
                "split": split,
                "image_width": record.get("image_width"),
                "image_height": record.get("image_height"),
                "ocr_region_count": len(gt_regions),
                "valid_ground_truth_region_count": len(valid_gt),
                "evaluated_region_count": len(aligned),
                "char_errors": image_char_errors,
                "gt_characters": image_gt_chars,
                "cer": image_char_errors / image_gt_chars if image_gt_chars else None,
                "word_errors": image_word_errors,
                "gt_words": image_gt_words,
                "wer": image_word_errors / image_gt_words if image_gt_words else None,
                "unassigned_prediction_count": len(unmatched_predictions),
            }
        )

    summary = {
        "split": split,
        "metric_status": "available" if total_gt_chars else "N/A — unavailable ground truth",
        "images_with_full_page_ground_truth": images_with_gt,
        "images_with_ground_truth_and_predictions": images_with_gt_predictions,
        "evaluated_ground_truth_regions": evaluated_regions,
        "excluded_invalid_geometry_regions": excluded_invalid_regions,
        "excluded_empty_transcription_regions": excluded_empty_transcriptions,
        "cer": total_char_errors / total_gt_chars if total_gt_chars else None,
        "character_errors": total_char_errors,
        "ground_truth_characters": total_gt_chars,
        "wer": total_word_errors / total_gt_words if total_gt_words else None,
        "word_errors": total_word_errors,
        "ground_truth_words": total_gt_words,
        "unmatched_ground_truth_regions": missing_region_count,
        "unassigned_prediction_word_boxes": unmatched_prediction_count,
        "text_normalization_policy": NORMALIZATION_POLICY,
        "wer_tokenization_policy": WER_TOKENIZATION_POLICY,
        "recognition_alignment": "Assign each Tesseract word box to the smallest valid full-page GT polygon containing its center; sort assigned words by y then x and compare to the GT region transcript.",
        "detection_metrics": {
            "status": "N/A — incompatible region granularity",
            "iou_threshold": iou_threshold,
            "reason": "MC-OCR full-page GT polygons annotate text lines/regions while Tesseract emits word-level boxes; one-to-one detection F1 would conflate segmentation with detection.",
        },
    }
    return summary, image_details, region_details
