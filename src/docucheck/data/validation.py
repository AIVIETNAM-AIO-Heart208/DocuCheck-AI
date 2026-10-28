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
            and bool(PureWindowsPath(value).parts)
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


def _positive_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _issues_match(value: Any, expected: list[str]) -> bool:
    return (isinstance(value, list) and all(isinstance(item, str) for item in value)
            and len(value) == len(set(value)) and set(value) == set(expected))


def _validate_text(region: dict[str, Any], schema: str, issues: Counter) -> None:
    value = region.get("text_raw")
    if value is not None and not isinstance(value, str):
        issues["invalid_text_type"] += 1
        return
    expected = text_status(value)
    if region.get("text_status") not in ("present", "missing_in_source", "empty_in_source"):
        issues["unrecognized_text_status"] += 1
    elif (region["text_status"] != expected and
          not (schema == "1.0" and value is not None and region["text_status"] == "present")):
        issues["inconsistent_text_status"] += 1


def validate_manifest(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Check metadata against source values; recorded source errors are allowed."""
    # Local import avoids the loader's dependency on the path validator.
    from docucheck.data.loader import FIELD_MAPPING

    issues: Counter[str] = Counter()
    objects = [record for record in records if isinstance(record, dict)]
    issues["invalid_record_entries"] = len(records) - len(objects)
    records = objects
    ids = [record.get("image_id") for record in records
           if isinstance(record.get("image_id"), str) and record["image_id"].strip()]
    issues["duplicate_image_ids"] = len(ids) - len(set(ids))
    for record in records:
        if not isinstance(record.get("image_id"), str) or not record["image_id"].strip():
            issues["invalid_image_ids"] += 1
        path = record.get("image_path")
        if not is_relative_dataset_path(path):
            issues["invalid_or_absolute_image_paths"] += 1
        schema = record.get("schema_version")
        if schema not in ("1.0", "1.1"):
            issues["missing_or_unknown_schema_version"] += 1
        split = record.get("split")
        if not split:
            issues["missing_split"] += 1
        subset = record.get("source_subset")
        allowed_splits = {
            "kie_train": ("internal_train", "internal_dev", "excluded_duplicate_of_official_validation"),
            "official_validation": ("official_validation_inventory",),
            "text_recognition": ("official_train", "official_val", "excluded_duplicate_of_official_val"),
        }
        if not isinstance(subset, str) or subset not in allowed_splits:
            issues["invalid_source_subset"] += 1
        elif split not in allowed_splits[subset]:
            issues["invalid_split_for_subset"] += 1
        source_split = record.get("source_split")
        expected_source = ("official_validation" if subset == "official_validation" else
                           "val" if subset == "text_recognition" and split == "official_val" else "train")
        if source_split != expected_source:
            issues["inconsistent_source_split"] += 1
        if "checksum_sha256" in record and record.get("image_group_id") != record["checksum_sha256"]:
            issues["inconsistent_image_content_group"] += 1
        if record.get("image_group_id") is not None and not isinstance(record["image_group_id"], str):
            issues["invalid_image_content_group"] += 1
        if record.get("image_status") == "valid" and any(
            not _positive_number(record.get(key))
            for key in ("image_width", "image_height")
        ):
            issues["valid_image_missing_dimensions"] += 1
        width, height = (record.get(key) if _positive_number(record.get(key)) else 0
                         for key in ("image_width", "image_height"))
        geometry_issues = set()
        for key in ("regions", "ocr_regions"):
            value = record.get(key, [])
            if not isinstance(value, list):
                issues["invalid_region_arrays"] += 1
                continue
            if subset in ("text_recognition", "official_validation") and value:
                issues["unexpected_regions_for_subset"] += 1
            for region in value:
                if not isinstance(region, dict):
                    issues["invalid_region_entries"] += 1
                    continue
                _validate_text(region, schema, issues)
                source = "kie" if key == "regions" else "full_page_transcription"
                if region.get("annotation_source") != source:
                    issues["inconsistent_region_annotation_source"] += 1
                label = region.get("label_raw")
                if label is not None and not isinstance(label, str):
                    issues["invalid_label_type"] += 1
                else:
                    field = FIELD_MAPPING.get(label) if key == "regions" else None
                    status = ("not_applicable" if key == "ocr_regions" else
                              "missing_in_source" if not label else "mapped" if field else "unmapped")
                    if region.get("canonical_field") != field:
                        issues["inconsistent_canonical_field"] += 1
                    if (schema != "1.0" or "label_status" in region) and region.get("label_status") != status:
                        issues["inconsistent_label_status"] += 1
                    if key == "ocr_regions" and label is not None:
                        issues["ocr_region_has_kie_label"] += 1
                actual = validate_polygon(region.get("polygon"), width, height)
                geometry_issues.update(actual)
                if not _issues_match(region.get("validation_issues"), actual):
                    issues["inconsistent_geometry_issues"] += 1
                bbox = region.get("bbox_xyxy")
                if actual:
                    if bbox is not None:
                        issues["invalid_geometry_has_derived_bbox"] += 1
                else:
                    points = [(float(x), float(y)) for x, y in region["polygon"]]
                    expected = [min(x for x, y in points), min(y for x, y in points),
                                max(x for x, y in points), max(y for x, y in points)]
                    if (not isinstance(bbox, list) or len(bbox) != 4
                            or any(type(v) not in (int, float) or not math.isfinite(v) for v in bbox)
                            or bbox != expected):
                        issues["inconsistent_derived_bbox"] += 1
        if subset == "text_recognition":
            _validate_text(record, schema, issues)
            if any(key in record for key in ("label_raw", "label_status", "canonical_field", "polygon", "bbox_xyxy")):
                issues["recognition_record_has_region_metadata"] += 1
            if schema != "1.0" and record.get("annotation_source") != f"text_recognition_{source_split}_data.txt":
                issues["inconsistent_recognition_annotation_source"] += 1
        else:
            # 1.0 official inventory did not yet carry a geometry summary.
            if not (schema == "1.0" and subset == "official_validation" and "validation_issues" not in record):
                if not _issues_match(record.get("validation_issues"), list(geometry_issues)):
                    issues["inconsistent_record_geometry_issues"] += 1
            if any(key in record for key in ("text_raw", "text_status")):
                issues["receipt_record_has_crop_transcript"] += 1
        if subset == "official_validation" and record.get("annotation_status") != "no_kie_ground_truth_columns_observed":
            issues["inconsistent_inventory_annotation_status"] += 1
    # Invalid types are already reported above; do not crash during leakage checks.
    cross_split = find_cross_split_duplicate_groups([
        record for record in records
        if isinstance(record.get("image_group_id"), str) and isinstance(record.get("split"), str)
    ])
    issues["cross_split_exact_duplicate_groups"] = len(cross_split)
    return {
        "record_count": len(records) + issues["invalid_record_entries"],
        "issue_counts": {key: count for key, count in sorted(issues.items()) if count},
        "cross_split_duplicate_groups": cross_split,
        "valid": not any(issues.values()),
    }
