"""Geometry validation for source annotations."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from docucheck.data.splitting import find_cross_split_duplicate_groups


def validate_polygon(
    polygon: Any, width: int, height: int, *, require_within_image: bool = True
) -> list[str]:
    """Return explicit validation issues for an xy polygon."""
    issues = []
    if not isinstance(polygon, list) or len(polygon) < 3:
        return ["missing_or_too_few_vertices"]
    try:
        points = [(float(point[0]), float(point[1])) for point in polygon]
    except (TypeError, ValueError, IndexError):
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
    if require_within_image and any(
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
    ids = [record.get("image_id") for record in records]
    issues["duplicate_image_ids"] = len(ids) - len(set(ids))
    for record in records:
        path = record.get("image_path")
        if not isinstance(path, str) or not path or path.startswith("/"):
            issues["invalid_or_absolute_image_paths"] += 1
        if record.get("image_status") == "valid" and (
            not record.get("image_width") or not record.get("image_height")
        ):
            issues["valid_image_missing_dimensions"] += 1
        for region in record.get("regions", []) + record.get("ocr_regions", []):
            if region.get("text_status") not in {"present", "missing_in_source"}:
                issues["unrecognized_text_status"] += 1
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
