"""Build standardized, local-only MC-OCR manifests."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from docucheck.data.loader import (
    FIELD_MAPPING,
    load_full_page_text_records,
    load_kie_records,
    load_text_recognition_pairs,
    resolve_dataset_root,
)
from docucheck.data.splitting import assign_internal_splits, find_cross_split_duplicate_groups
from docucheck.data.validation import is_relative_dataset_path, text_status, validate_polygon


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _opaque_id(source_subset: str, relative_path: str) -> str:
    value = f"mcocr-v1|{source_subset}|{relative_path}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:24]


def _bbox_xyxy(polygon: list[list[float]] | None) -> list[float] | None:
    if not polygon:
        return None
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return [min(xs), min(ys), max(xs), max(ys)]


def _normalize_region(region: dict[str, Any], width: int, height: int, source: str) -> dict[str, Any]:
    polygon = region.get("polygon")
    issues = validate_polygon(polygon, width, height)
    return {
        "text_raw": region.get("text_raw"),
        "text_status": text_status(region.get("text_raw")),
        "label_raw": region.get("label_raw"),
        "canonical_field": region.get("canonical_field"),
        "polygon": polygon,
        "bbox_xyxy": _bbox_xyxy(polygon) if not issues else None,
        "category_id": region.get("category_id"),
        "source_geometry": region.get("source_annotation", {"polygon": polygon}),
        "annotation_source": source,
        "source_issue": region.get("source_issue"),
        "source_line": region.get("source_line"),
        "source_raw": region.get("source_raw"),
        "label_status": ("not_applicable" if source != "kie" else
                         "missing_in_source" if not region.get("label_raw") else
                         "mapped" if region.get("canonical_field") else "unmapped"),
        "validation_issues": issues,
    }


def _read_validation_inventory(root: Path) -> list[dict[str, Any]]:
    image_dir = root / "val_images" / "val_images"
    csv_path = root / "mcocr_val_sample_df.csv"
    source_ids = set()
    if csv_path.is_file():
        columns = pd.read_csv(csv_path, nrows=0).columns
        if "anno_labels" in columns or "anno_polygons" in columns:
            raise ValueError("Validation CSV now contains KIE columns; inventory-only adapter needs review")
        source_ids = set(pd.read_csv(csv_path, usecols=["img_id"])["img_id"].dropna().astype(str))
    image_names = {path.name for path in image_dir.iterdir() if path.is_file()} if image_dir.is_dir() else set()
    for name in source_ids:
        if not is_relative_dataset_path(name) or len(Path(name.replace("\\", "/")).parts) != 1:
            raise ValueError("Invalid source image identifier in validation inventory CSV")
    names = sorted(image_names | source_ids)
    records = []
    for name in names:
        image_path = image_dir / name
        image_meta = _image_meta(image_path)
        checksum = _sha256_file(image_path) if image_path.is_file() else None
        records.append({
            "schema_version": "1.1",
            "image_id": _opaque_id("official_validation", name),
            "image_path": (Path("val_images") / "val_images" / name).as_posix(),
            "source_image_name": name,
            "source_subset": "official_validation",
            "source_split": "official_validation",
            "split": "official_validation_inventory",
            "split_provenance": "provided image directory; source CSV contains no KIE label or polygon columns",
            "image_group_id": checksum,
            "checksum_sha256": checksum,
            "image_width": image_meta.get("width"),
            "image_height": image_meta.get("height"),
            "image_mode": image_meta.get("mode"),
            "image_status": "valid" if image_meta.get("valid") else image_meta.get("error_type", "invalid"),
            "annotation_status": "no_kie_ground_truth_columns_observed",
            "regions": [],
            "ocr_regions": [],
            "ocr_ground_truth_status": "unavailable",
            "source_id_listed_in_sample_csv": name in source_ids,
            "validation_issues": [],
        })
    return records


def _image_meta(path: Path) -> dict[str, Any]:
    from docucheck.data.loader import inspect_image

    return inspect_image(path) if path.is_file() else {"valid": False, "error_type": "missing_file"}


def prepare_records(
    dataset_root: str | Path | None = None,
    *,
    seed: int = 42,
    validation_fraction: float = 0.2,
    invalid_policy: str = "report",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Normalize image-level KIE/OCR data and crop-recognition pairs."""
    if invalid_policy not in {"report", "skip", "fail"}:
        raise ValueError("invalid_policy must be one of: report, skip, fail")
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be strictly between 0 and 1")
    root = resolve_dataset_root(dataset_root)
    source_kie = load_kie_records(root)
    source_ocr = load_full_page_text_records(root)
    ocr_by_image = {record["image_id"]: record["regions"] for record in source_ocr}
    prepared = []
    issue_counts: Counter[str] = Counter()
    image_status_counts: Counter[str] = Counter()
    annotation_status_counts: Counter[str] = Counter()
    all_image_names = {path.name for path in (root / "train_images" / "train_images").glob("*") if path.is_file()}
    source_id_counts = Counter(record["image_id"] for record in source_kie)
    for source in source_kie:
        name = source["image_id"]
        if not is_relative_dataset_path(name) or len(Path(name.replace("\\", "/")).parts) != 1:
            raise ValueError(f"Invalid source image identifier at KIE CSV line {source['source_line']}; source left unchanged")
    source_rows = [(record["image_id"], record) for record in source_kie]
    source_rows.extend((name, None) for name in sorted(all_image_names - set(source_id_counts)))
    source_rows.sort(key=lambda pair: (pair[0], pair[1]["source_line"] if pair[1] else 0))

    # Include image files without a source annotation row so they remain visible in validation reports.
    for image_name, source in source_rows:
        image_path = root / "train_images" / "train_images" / image_name
        image_meta = None
        try:
            from docucheck.data.loader import inspect_image

            image_meta = inspect_image(image_path) if image_path.is_file() else {"valid": False, "error_type": "missing_file"}
        except OSError:
            image_meta = {"valid": False, "error_type": "read_error"}
        if image_meta["valid"]:
            image_status = "valid"
            checksum = _sha256_file(image_path)
        else:
            image_status = image_meta.get("error_type", "invalid")
            checksum = None
        image_status_counts[image_status] += 1

        source_regions = source["regions"] if source else []
        regions = [
            _normalize_region(region, image_meta["width"], image_meta["height"], "kie")
            if image_meta["valid"]
            else _normalize_region(region, 0, 0, "kie")
            for region in source_regions
        ]
        ocr_regions_source = ocr_by_image.get(image_name)
        ocr_regions = [
            _normalize_region(region, image_meta["width"], image_meta["height"], "full_page_transcription")
            if image_meta["valid"]
            else _normalize_region(region, 0, 0, "full_page_transcription")
            for region in (ocr_regions_source or [])
        ]
        if not source:
            annotation_status = "no_kie_row"
        elif not source_regions:
            annotation_status = "source_annotation_arrays_empty"
        else:
            annotation_status = "annotated"
        annotation_status_counts[annotation_status] += 1
        annotation_issues = []
        if source:
            if len(set(source["source_region_counts"].values())) > 1:
                annotation_issues.append("source_array_length_mismatch")
            if source["polygon_parse_error"]:
                annotation_issues.append("polygon_parse_failure")
            if source_id_counts[image_name] > 1:
                annotation_issues.append("duplicate_source_image_id")
        if annotation_status != "annotated":
            annotation_issues.append(annotation_status)
        if any(region["label_status"] == "unmapped" for region in regions):
            annotation_issues.append("unmapped_label")
        if any(region["label_status"] == "missing_in_source" for region in regions):
            annotation_issues.append("missing_label")
        if any(region["text_status"] != "present" for region in regions + ocr_regions):
            annotation_issues.append("missing_or_empty_transcription")
        if any(region["source_issue"] for region in ocr_regions):
            annotation_issues.append("ocr_source_parse_failure")

        for region in regions + ocr_regions:
            issue_counts.update(region["validation_issues"])
        unmapped = sorted({
            region["label_raw"] for region in regions
            if region["label_raw"] and region["canonical_field"] is None
        })
        relative_path = (Path("train_images") / "train_images" / image_name).as_posix()
        record = {
            "schema_version": "1.1",
            "image_id": _opaque_id("train", relative_path + (
                f"|source_line={source['source_line']}" if source and source_id_counts[image_name] > 1 else "")),
            "image_path": relative_path,
            "source_image_name": image_name,
            "source_subset": "kie_train",
            "source_split": "train",
            "split": None,
            "split_provenance": None,
            "source_group_id": None,
            "image_group_id": checksum,
            "checksum_sha256": checksum,
            "image_width": image_meta.get("width"),
            "image_height": image_meta.get("height"),
            "image_mode": image_meta.get("mode"),
            "image_status": image_status,
            "annotation_status": annotation_status,
            "annotation_issues": sorted(annotation_issues),
            "source_line": source["source_line"] if source else None,
            "source_annotations": source["source_annotations"] if source else None,
            "source_region_counts": source["source_region_counts"] if source else None,
            "polygon_parse_error": source["polygon_parse_error"] if source else None,
            "annotation_fields": {
                "anno_num": source["source_annotations"].get("anno_num") if source else None,
                "anno_image_quality": source["source_annotations"].get("anno_image_quality") if source else None,
                "unmapped_labels": unmapped,
            },
            "regions": regions,
            "ocr_regions": ocr_regions,
            "ocr_ground_truth_status": (
                "unavailable_sidecar" if ocr_regions_source is None else
                "empty_sidecar" if not ocr_regions_source else
                "no_usable_transcriptions" if not any(r["text_status"] == "present" for r in ocr_regions) else
                "partial_transcriptions" if any(r["text_status"] != "present" for r in ocr_regions) else "available"),
            "validation_issues": sorted({
                issue for region in regions + ocr_regions for issue in region["validation_issues"]
            }),
        }
        prepared.append(record)

    validation_inventory = _read_validation_inventory(root)
    official_validation_hashes = {
        record["image_group_id"] for record in validation_inventory if record["image_group_id"]
    }
    train_records = [record for record in prepared if record["source_split"] == "train"]
    eligible_train = [record for record in train_records if record["image_group_id"] not in official_validation_hashes]
    quarantined = [record for record in train_records if record["image_group_id"] in official_validation_hashes]
    prepared_train = assign_internal_splits(
        eligible_train, seed=seed, validation_fraction=validation_fraction
    ) if eligible_train else []
    for record in quarantined:
        record["split"] = "excluded_duplicate_of_official_validation"
        record["split_provenance"] = "quarantined exact image duplicate of official validation"
    split_by_image = {record["image_id"]: record for record in prepared_train}
    for record in prepared:
        replacement = split_by_image.get(record["image_id"])
        if replacement:
            record.update(replacement)
    all_records = prepared + validation_inventory
    duplicates = find_cross_split_duplicate_groups(all_records)
    duplicate_counts = Counter(record["image_group_id"] for record in prepared if record["image_group_id"])
    report = {
        "dataset_root_label": "configured local MC-OCR root",
        "seed": seed,
        "internal_validation_fraction": validation_fraction,
        "invalid_policy": invalid_policy,
        "records_by_split": dict(Counter(record["split"] for record in all_records)),
        "image_status_counts": dict(image_status_counts),
        "annotation_status_counts": dict(annotation_status_counts),
        "annotation_issue_counts": dict(Counter(issue for record in prepared for issue in record["annotation_issues"])),
        "kie_region_count": sum(len(record["regions"]) for record in prepared),
        "ocr_region_count": sum(len(record["ocr_regions"]) for record in prepared),
        "ocr_ground_truth_status_counts": dict(Counter(
            record["ocr_ground_truth_status"] for record in prepared
        )),
        "geometry_issue_counts": dict(sorted(issue_counts.items())),
        "exact_duplicate_groups": sum(count > 1 for count in duplicate_counts.values()),
        "records_in_exact_duplicate_groups": sum(count for count in duplicate_counts.values() if count > 1),
        "cross_split_duplicate_group_count": len(duplicates),
        "cross_split_duplicate_groups": duplicates,
        "official_validation_duplicate_quarantine_count": len(quarantined),
        "official_validation_duplicate_quarantine_groups": len({
            record["image_group_id"] for record in quarantined if record["image_group_id"]
        }),
        "source_template_grouping": "unavailable in the observed source fields; grouped by exact image SHA-256",
        "field_mapping": FIELD_MAPPING.copy(),
        "unmapped_labels": dict(Counter(
            label for record in prepared for label in record["annotation_fields"]["unmapped_labels"]
        )),
    }

    invalid_records = [
        record for record in all_records
        if record["image_status"] != "valid" or record["validation_issues"] or
        set(record.get("annotation_issues", [])) - {"no_kie_row", "source_annotation_arrays_empty", "unmapped_label"}
    ]
    report["invalid_record_count"] = len(invalid_records)
    if invalid_policy == "fail" and invalid_records:
        raise ValueError(f"Found {len(invalid_records)} invalid records; see validation report")
    if invalid_policy == "skip" and invalid_records:
        invalid_ids = {record["image_id"] for record in invalid_records}
        all_records = [record for record in all_records if record["image_id"] not in invalid_ids]
        report["skipped_record_count"] = len(invalid_records)
    else:
        report["skipped_record_count"] = 0
    report["records_by_split"] = dict(Counter(record["split"] for record in all_records))

    recognition_records = []
    for split in ("train", "val"):
        pairs = load_text_recognition_pairs(split, root)
        path_counts = Counter(str(pair["image_path"]) for pair in pairs)
        for pair in pairs:
            image_path = pair["image_path"]
            rel_path = image_path.relative_to(root).as_posix() if image_path.is_relative_to(root) else image_path.as_posix()
            meta = None
            try:
                from docucheck.data.loader import inspect_image

                meta = inspect_image(image_path)
            except OSError:
                meta = {"valid": False, "error_type": "read_error"}
            checksum = _sha256_file(image_path) if meta["valid"] else None
            recognition_records.append(
                {
                    "schema_version": "1.1",
                    "image_id": _opaque_id(f"text_recognition_{split}", rel_path + (
                        f"|source_line={pair['source_line']}" if path_counts[str(image_path)] > 1 else "")),
                    "image_path": rel_path,
                    "source_image_name": image_path.name,
                    "source_subset": "text_recognition",
                    "source_split": split,
                    "split": f"official_{split}",
                    "split_provenance": "provided text_recognition manifest",
                    "source_image_ref": pair["source_image_ref"],
                    "source_line": pair["source_line"],
                    "annotation_source": f"text_recognition_{split}_data.txt",
                    "annotation_issues": ["duplicate_source_image_ref"] if path_counts[str(image_path)] > 1 else [],
                    "image_group_id": checksum,
                    "checksum_sha256": checksum,
                    "image_width": meta.get("width"),
                    "image_height": meta.get("height"),
                    "image_status": "valid" if meta["valid"] else meta.get("error_type", "invalid"),
                    "text_raw": pair["text_raw"],
                    "text_status": text_status(pair["text_raw"]),
                }
            )
    recognition_validation_hashes = {
        record["image_group_id"] for record in recognition_records
        if record["source_split"] == "val" and record["image_group_id"]
    }
    recognition_quarantine_count = 0
    for record in recognition_records:
        if record["source_split"] == "train" and record["image_group_id"] in recognition_validation_hashes:
            record["split"] = "excluded_duplicate_of_official_val"
            record["split_provenance"] = "quarantined exact crop duplicate of official recognition validation"
            recognition_quarantine_count += 1
    report["recognition_records_by_split"] = dict(Counter(record["split"] for record in recognition_records))
    report["recognition_validation_duplicate_quarantine_count"] = recognition_quarantine_count
    report["recognition_missing_crop_count"] = sum(record["image_status"] != "valid" for record in recognition_records)
    report["recognition_text_status_counts"] = dict(Counter(record["text_status"] for record in recognition_records))
    invalid_recognition = [r for r in recognition_records
                           if r["image_status"] != "valid" or r["text_status"] != "present" or r["annotation_issues"]]
    report["invalid_recognition_record_count"] = len(invalid_recognition)
    if invalid_policy == "fail" and invalid_recognition:
        raise ValueError(f"Found {len(invalid_recognition)} invalid recognition records")
    if invalid_policy == "skip":
        invalid_ids = {r["image_id"] for r in invalid_recognition}
        recognition_records = [r for r in recognition_records if r["image_id"] not in invalid_ids]
    report["recognition_records_by_split"] = dict(Counter(r["split"] for r in recognition_records))
    report["skipped_recognition_record_count"] = len(invalid_recognition) if invalid_policy == "skip" else 0
    return all_records, recognition_records, report


def write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    def json_safe(value):
        # JSON has no NaN/Infinity literals. Keep their spelling as strings;
        # original annotation strings and validation issues preserve evidence.
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, dict):
            return {key: json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_safe(item) for item in value]
        return value

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(json_safe(record), ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(output)
