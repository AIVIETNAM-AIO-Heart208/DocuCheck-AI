"""Geometry validation for source annotations."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from docucheck.data.splitting import find_cross_split_duplicate_groups


def is_relative_dataset_path(value: Any) -> bool:
    """Reject absolute, drive-relative and parent traversal paths on any host."""
    return (isinstance(value, str) and bool(value.strip())
            and not PurePosixPath(value).is_absolute()
            and not PureWindowsPath(value).drive
            and not PureWindowsPath(value).root
            and ".." not in PureWindowsPath(value).parts)


def text_status(value: str | None) -> str:
    if value is None:
        return "missing_in_source"
    return "present" if value.strip() else "empty_in_source"


def validate_polygon(
    polygon: Any, width: int, height: int, *, require_within_image: bool = True
) -> list[str]:
    """Return explicit validation issues for an xy polygon."""
    issues = []
    if not isinstance(polygon, list) or len(polygon) < 3:
        return ["missing_or_too_few_vertices"]
    try:
        if any(not isinstance(point, (list, tuple)) or len(point) != 2 for point in polygon):
            return ["malformed_vertices"]
        points = [(float(point[0]), float(point[1])) for point in polygon]
    except (TypeError, ValueError, IndexError, OverflowError):
        return ["malformed_vertices"]
    if any(not math.isfinite(x) or not math.isfinite(y) for x, y in points):
        issues.append("non_finite_coordinates")
        return issues
    area2 = abs(
        sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )
    )
    if area2 == 0:
        issues.append("zero_area")
    if len(set(points)) != len(points):
        issues.append("repeated_vertices")

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, c):
        return (cross(a, b, c) == 0 and min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))

    for i in range(len(points)):
        a, b = points[i], points[(i + 1) % len(points)]
        for j in range(i + 1, len(points)):
            if j == i + 1 or (i == 0 and j == len(points) - 1):
                continue
            c, d = points[j], points[(j + 1) % len(points)]
            if ((cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0)
                    or any((on_segment(a, b, c), on_segment(a, b, d),
                            on_segment(c, d, a), on_segment(c, d, b)))):
                if "self_intersection" not in issues:
                    issues.append("self_intersection")
    if require_within_image and (width <= 0 or height <= 0):
        issues.append("image_dimensions_unavailable")
    elif require_within_image and any(
        x < 0 or y < 0 or x > width or y > height for x, y in points
    ):
        issues.append("out_of_image_bounds")
    return issues


def validate_record_regions(record: dict[str, Any], width: int, height: int) -> list[dict[str, Any]]:
    results = []
    for index, region in enumerate(record.get("regions", [])):
        issues = validate_polygon(region.get("polygon"), width, height)
        results.append({"index": index, "valid": not issues, "issues": issues})
    return results


def validate_manifest(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Check standardized record identities, relative paths, and split leakage."""
    issues: Counter[str] = Counter()
    ids = [record.get("image_id") for record in records
           if isinstance(record.get("image_id"), str) and record["image_id"].strip()]
    issues["duplicate_image_ids"] = len(ids) - len(set(ids))
    for record in records:
        if not isinstance(record.get("image_id"), str) or not record["image_id"].strip():
            issues["invalid_image_ids"] += 1
        path = record.get("image_path")
        if not is_relative_dataset_path(path):
            issues["invalid_or_absolute_image_paths"] += 1
        if record.get("schema_version") not in {"1.0", "1.1"}:
            issues["missing_or_unknown_schema_version"] += 1
        if not record.get("split"):
            issues["missing_split"] += 1
        if record.get("image_status") == "valid" and any(
            not isinstance(record.get(key), (int, float)) or not math.isfinite(record[key]) or record[key] <= 0
            for key in ("image_width", "image_height")
        ):
            issues["valid_image_missing_dimensions"] += 1
        regions = []
        for key in ("regions", "ocr_regions"):
            value = record.get(key, [])
            if not isinstance(value, list):
                issues["invalid_region_arrays"] += 1
            else:
                regions.extend(value)
        if record.get("source_subset") == "text_recognition":
            regions.append(record)
        for region in regions:
            if not isinstance(region, dict):
                issues["invalid_region_entries"] += 1
                continue
            if region.get("text_status") not in {"present", "missing_in_source", "empty_in_source"}:
                issues["unrecognized_text_status"] += 1
            elif region.get("text_raw") is not None and not isinstance(region["text_raw"], str):
                issues["invalid_text_type"] += 1
            elif region["text_status"] != text_status(region.get("text_raw")):
                issues["inconsistent_text_status"] += 1
            if region.get("bbox_xyxy") is not None and region.get("validation_issues"):
                issues["invalid_geometry_has_derived_bbox"] += 1
    cross_split = find_cross_split_duplicate_groups(records)
    issues["cross_split_exact_duplicate_groups"] = len(cross_split)
    return {
        "record_count": len(records),
        "issue_counts": {key: count for key, count in sorted(issues.items()) if count},
        "cross_split_duplicate_groups": cross_split,
        "valid": not any(issues.values()),
    }
