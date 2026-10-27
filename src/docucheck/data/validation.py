"""Geometry validation for source annotations."""

from __future__ import annotations

import math
from typing import Any


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
