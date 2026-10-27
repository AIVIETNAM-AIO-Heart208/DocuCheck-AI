"""Reusable image and region feature extraction for exploratory analysis."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd

from docucheck.data.loader import load_full_page_text_records


def _edge_angle_degrees(polygon: list[list[float]]) -> float | None:
    if len(polygon) < 2:
        return None
    x1, y1 = polygon[0]
    x2, y2 = polygon[1]
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    return ((angle + 90) % 180) - 90


def collect_image_features(
    records: list[dict[str, Any]], dataset_root: str | Path | None = None
) -> pd.DataFrame:
    """Measure image dimensions and simple visual heuristics on train images."""
    text_records = load_full_page_text_records(dataset_root)
    text_by_image = {record["image_id"]: record["regions"] for record in text_records}
    rows = []
    for record in records:
        path = Path(record["image_path"])
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            rows.append({"image_id": record["image_id"], "image_path": path, "image_valid": False})
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        ocr_regions = text_by_image.get(record["image_id"], [])
        angles = [
            _edge_angle_degrees(region["polygon"])
            for region in ocr_regions
            if region.get("polygon")
        ]
        angles = [angle for angle in angles if angle is not None]
        transcript_lengths = [
            len(region["text_raw"])
            for region in ocr_regions
            if region.get("text_raw") is not None
        ]
        rows.append(
            {
                "image_id": record["image_id"],
                "image_path": path,
                "image_valid": True,
                "width": width,
                "height": height,
                "aspect_ratio": width / height,
                "orientation": "landscape" if width > height else "portrait_or_square",
                "brightness_mean": float(gray.mean()),
                "contrast_std": float(gray.std()),
                "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                "ocr_region_count": len(ocr_regions),
                "ocr_transcript_codepoints": sum(transcript_lengths),
                "longest_region_codepoints": max(transcript_lengths, default=0),
                "median_text_edge_angle_degrees": float(np.median(angles)) if angles else np.nan,
                "median_abs_text_edge_angle_degrees": float(np.median(np.abs(angles))) if angles else np.nan,
            }
        )
    return pd.DataFrame(rows)


def collect_field_geometry(
    records: list[dict[str, Any]], image_features: pd.DataFrame
) -> pd.DataFrame:
    """Return normalized KIE region centers and areas, retaining source labels."""
    dimensions = image_features.set_index("image_id")[["width", "height"]].to_dict("index")
    rows = []
    for record in records:
        size = dimensions.get(record["image_id"])
        if not size:
            continue
        width, height = size["width"], size["height"]
        for region in record["regions"]:
            polygon = region.get("polygon")
            if not polygon:
                continue
            points = np.asarray(polygon, dtype=float)
            x1, y1 = points.min(axis=0)
            x2, y2 = points.max(axis=0)
            rows.append(
                {
                    "image_id": record["image_id"],
                    "label_raw": region["label_raw"],
                    "canonical_field": region["canonical_field"],
                    "center_x_normalized": float(points[:, 0].mean() / width),
                    "center_y_normalized": float(points[:, 1].mean() / height),
                    "bbox_area_fraction": float(max(0, x2 - x1) * max(0, y2 - y1) / (width * height)),
                }
            )
    return pd.DataFrame(rows)


def select_gallery_examples(
    records: list[dict[str, Any]], image_features: pd.DataFrame
) -> dict[str, dict[str, Any]]:
    """Select deterministic examples for observed quality/geometry extremes."""
    by_id = {record["image_id"]: record for record in records}
    frame = image_features[image_features["image_valid"]].copy()
    if frame.empty:
        return {}
    selections = {
        "sharpest heuristic": frame.sort_values("laplacian_variance", ascending=False).iloc[0],
        "lowest sharpness heuristic": frame.sort_values("laplacian_variance").iloc[0],
        "largest text tilt": frame.sort_values("median_abs_text_edge_angle_degrees", ascending=False, na_position="last").iloc[0],
        "most annotated text regions": frame.sort_values("ocr_region_count", ascending=False).iloc[0],
        "longest observed transcript region": frame.sort_values("longest_region_codepoints", ascending=False).iloc[0],
    }
    result = {}
    seen = set()
    for category, row in selections.items():
        image_id = row["image_id"]
        if image_id in seen:
            candidates = frame[~frame["image_id"].isin(seen)]
            if candidates.empty:
                continue
            if category == "sharpest heuristic":
                row = candidates.sort_values("laplacian_variance", ascending=False).iloc[0]
            elif category == "lowest sharpness heuristic":
                row = candidates.sort_values("laplacian_variance").iloc[0]
            elif category == "largest text tilt":
                row = candidates.sort_values("median_abs_text_edge_angle_degrees", ascending=False, na_position="last").iloc[0]
            elif category == "most annotated text regions":
                row = candidates.sort_values("ocr_region_count", ascending=False).iloc[0]
            else:
                row = candidates.sort_values("longest_region_codepoints", ascending=False).iloc[0]
            image_id = row["image_id"]
        seen.add(image_id)
        result[category] = by_id[image_id]
    return result
