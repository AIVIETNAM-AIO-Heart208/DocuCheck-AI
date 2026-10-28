"""Read-only adapters for the locally downloaded MC-OCR exports."""

from __future__ import annotations

import ast
import csv
import os
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from docucheck.data.validation import is_relative_dataset_path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_ROOT = REPOSITORY_ROOT / "data" / "mcocr"

FIELD_MAPPING = {
    "SELLER": "seller_name",
    "ADDRESS": "seller_address",
    "TIMESTAMP": "transaction_datetime",
    "TOTAL_COST": "total_amount",
}


def resolve_dataset_root(dataset_root: str | Path | None = None) -> Path:
    """Resolve an explicit root, MC_OCR_ROOT, or the workspace default."""
    value = dataset_root or os.environ.get("MC_OCR_ROOT") or DEFAULT_DATASET_ROOT
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    return path.resolve()


def _split_cell(value: str | None) -> list[str]:
    if value is None or not value.strip() or value.strip().lower() == "nan":
        return []
    return value.split("|||")


def _parse_polygons(value: str | None) -> list[dict[str, Any]]:
    if value is None or not value.strip() or value.strip().lower() == "nan":
        return []
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, list):
        raise ValueError("anno_polygons must be a list")
    return parsed


def _polygon_from_annotation(annotation: dict[str, Any]) -> list[list[float]] | None:
    segmentation = annotation.get("segmentation")
    if not isinstance(segmentation, list) or not segmentation:
        return None
    coordinates = segmentation[0]
    if not isinstance(coordinates, list) or len(coordinates) < 6 or len(coordinates) % 2:
        return None
    try:
        return [
            [float(coordinates[index]), float(coordinates[index + 1])]
            for index in range(0, len(coordinates), 2)
        ]
    except (TypeError, ValueError):
        return None


def load_kie_records(dataset_root: str | Path | None = None) -> list[dict[str, Any]]:
    """Load KIE train rows without dropping incomplete or unmapped regions."""
    root = resolve_dataset_root(dataset_root)
    csv_path = root / "mcocr_train_df.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"MC-OCR KIE annotation CSV not found under {root}")

    records = []
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        for source_line, row in enumerate(csv.DictReader(stream), 2):
            texts = _split_cell(row.get("anno_texts"))
            labels = _split_cell(row.get("anno_labels"))
            polygon_parse_error = None
            try:
                polygons = _parse_polygons(row.get("anno_polygons"))
            except (SyntaxError, ValueError, TypeError) as error:
                polygons = []
                polygon_parse_error = type(error).__name__
            count = max(len(texts), len(labels), len(polygons))
            regions = []
            for index in range(count):
                raw_annotation = polygons[index] if index < len(polygons) else {}
                annotation = raw_annotation if isinstance(raw_annotation, dict) else {}
                label = labels[index] if index < len(labels) else None
                text = texts[index] if index < len(texts) else None
                regions.append(
                    {
                        "text_raw": text,
                        "label_raw": label,
                        "canonical_field": FIELD_MAPPING.get(label),
                        "category_id": annotation.get("category_id"),
                        "polygon": _polygon_from_annotation(annotation),
                        "source_annotation": raw_annotation,
                    }
                )
            records.append(
                {
                    "image_id": row.get("img_id", ""),
                    "image_path": root / "train_images" / "train_images" / row.get("img_id", ""),
                    "source_split": "train",
                    "source_annotations": {
                        "anno_num": row.get("anno_num"),
                        "anno_image_quality": row.get("anno_image_quality"),
                        "anno_texts": row.get("anno_texts"),
                        "anno_labels": row.get("anno_labels"),
                        "anno_polygons": row.get("anno_polygons"),
                    },
                    "source_line": source_line,
                    "regions": regions,
                    "source_region_counts": {
                        "texts": len(texts),
                        "labels": len(labels),
                        "polygons": len(polygons),
                    },
                    "polygon_parse_error": polygon_parse_error,
                }
            )
    return records


def summarize_annotations(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return aggregate schema/coverage diagnostics without receipt text."""
    label_counts: Counter[str] = Counter()
    field_images: Counter[str] = Counter()
    field_regions: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    region_counts = []

    for record in records:
        counts = record["source_region_counts"]
        if len(set(counts.values())) > 1:
            issues["source_array_length_mismatch"] += 1
        if record.get("polygon_parse_error"):
            issues["polygon_parse_failure"] += 1
        if not counts["texts"] and not counts["labels"] and not counts["polygons"]:
            issues["all_annotation_arrays_empty"] += 1
        region_counts.append(max(counts.values()))
        image_fields = set()
        for region in record["regions"]:
            if not isinstance(region["source_annotation"], dict):
                issues["malformed_polygon_entry"] += 1
            label = region["label_raw"]
            if label:
                label_counts[label] += 1
            field = region["canonical_field"]
            if field:
                field_regions[field] += 1
                image_fields.add(field)
            if region["polygon"] is None:
                issues["missing_or_malformed_polygon"] += 1
        for field in image_fields:
            field_images[field] += 1

    return {
        "record_count": len(records),
        "region_count": sum(region_counts),
        "region_count_per_image": region_counts,
        "label_region_counts": dict(sorted(label_counts.items())),
        "field_image_counts": dict(sorted(field_images.items())),
        "field_region_counts": dict(sorted(field_regions.items())),
        "issue_counts": dict(sorted(issues.items())),
        "known_labels": sorted(label_counts),
        "field_mapping": FIELD_MAPPING.copy(),
    }


def inspect_image(path: str | Path) -> dict[str, Any]:
    """Check one local image and return dimensions/mode or an error category."""
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            return {
                "valid": True,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "format": image.format,
            }
    except (OSError, UnidentifiedImageError, ValueError) as error:
        return {"valid": False, "error_type": type(error).__name__}


def load_full_page_text_records(
    dataset_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Load full-page text boxes/transcripts, preserving comma characters in text."""
    root = resolve_dataset_root(dataset_root)
    sidecar_dir = root / "kie_data" / "kie_data" / "boxes_and_transcripts"
    records = []
    for path in sorted(sidecar_dir.glob("*.tsv")):
        regions = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            fields = line.split(",", 10)
            issue = None
            polygon = None
            text = None
            if len(fields) != 11:
                issue = "unexpected_field_count"
            else:
                try:
                    values = [float(value) for value in fields[1:9]]
                    polygon = [[values[i], values[i + 1]] for i in range(0, 8, 2)]
                except ValueError:
                    issue = "invalid_coordinates"
                text = fields[10]
            regions.append(
                {
                    "source_row": fields[0] if fields else str(line_number),
                    "text_raw": text,
                    "polygon": polygon,
                    "source_issue": issue,
                    "source_line": line_number,
                    "source_raw": line,
                }
            )
        records.append(
            {
                "image_id": f"{path.stem}.jpg",
                "image_path": root / "train_images" / "train_images" / f"{path.stem}.jpg",
                "source_split": "train",
                "regions": regions,
            }
        )
    return records


def load_text_recognition_pairs(
    split: str, dataset_root: str | Path | None = None
) -> list[dict[str, Any]]:
    """Load crop/transcript pairs from the official recognition task manifests."""
    if split not in {"train", "val"}:
        raise ValueError("split must be 'train' or 'val'")
    root = resolve_dataset_root(dataset_root)
    manifest = root / f"text_recognition_{split}_data.txt"
    pairs = []
    with manifest.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            image_ref, separator, text = line.rstrip("\r\n").partition("\t")
            if not is_relative_dataset_path(image_ref):
                raise ValueError(f"Invalid recognition image path at {manifest.name}:{line_number}")
            candidate = root / image_ref
            if not candidate.is_file():
                crop_candidate = root / "text_recognition_mcocr_data" / "text_recognition_mcocr_data" / Path(image_ref).name
                if crop_candidate.is_file():
                    candidate = crop_candidate
            pairs.append(
                {
                    "image_path": candidate,
                    "source_image_ref": image_ref,
                    "text_raw": text if separator else None,
                    "source_split": split,
                    "source_line": line_number,
                }
            )
    return pairs


def summarize_ocr_exports(dataset_root: str | Path | None = None) -> dict[str, Any]:
    """Summarize OCR annotations and crop pairs without emitting transcript content."""
    root = resolve_dataset_root(dataset_root)
    page_records = load_full_page_text_records(root)
    page_rows = [region for record in page_records for region in record["regions"]]
    pairs = {split: load_text_recognition_pairs(split, root) for split in ("train", "val")}
    detector_dir = root / "text_detector" / "text_detector" / "txt"
    detector_rows = 0
    detector_malformed = 0
    for path in detector_dir.glob("*.txt"):
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            detector_rows += 1
            values = line.split(",")
            if len(values) != 9 or any(not value.strip() for value in values[:8]):
                detector_malformed += 1
    image_names = {path.name for path in (root / "text_recognition_mcocr_data" / "text_recognition_mcocr_data").glob("*.jpg")}
    pair_image_names = {Path(pair["image_path"]).name for split_pairs in pairs.values() for pair in split_pairs}
    text_lengths = [len(pair["text_raw"]) for split_pairs in pairs.values() for pair in split_pairs if pair["text_raw"] is not None]
    train_image_names = {
        path.name for path in (root / "train_images" / "train_images").glob("*") if path.is_file()
    }
    page_sidecar_names = {f"{record['image_id']}" for record in page_records}
    return {
        "full_page_sidecar_images": len(page_records),
        "full_page_sidecars_without_image": sum(not Path(record["image_path"]).is_file() for record in page_records),
        "train_images_without_full_page_sidecar": len(train_image_names - page_sidecar_names),
        "full_page_text_regions": len(page_rows),
        "full_page_malformed_rows": sum(region["source_issue"] is not None for region in page_rows),
        "full_page_empty_transcriptions": sum(not (region["text_raw"] or "").strip() for region in page_rows),
        "detector_annotation_images": sum(1 for _ in detector_dir.glob("*.txt")),
        "detector_regions": detector_rows,
        "detector_malformed_rows": detector_malformed,
        "recognition_pairs": {split: len(split_pairs) for split, split_pairs in pairs.items()},
        "recognition_empty_transcriptions": sum(
            not (pair["text_raw"] or "").strip()
            for split_pairs in pairs.values()
            for pair in split_pairs
        ),
        "recognition_crop_images": len(image_names),
        "recognition_pairs_without_crop": len(pair_image_names - image_names),
        "recognition_crop_images_without_pair": len(image_names - pair_image_names),
        "transcription_length_codepoints": {
            "min": min(text_lengths) if text_lengths else None,
            "median": sorted(text_lengths)[len(text_lengths) // 2] if text_lengths else None,
            "max": max(text_lengths) if text_lengths else None,
        },
    }


def audit_dataset(dataset_root: str | Path | None = None) -> dict[str, Any]:
    """Summarize observed MC-OCR inventory, KIE annotations, and image health."""
    root = resolve_dataset_root(dataset_root)
    records = load_kie_records(root)
    train_images = root / "train_images" / "train_images"
    val_images = root / "val_images" / "val_images"
    train_names = {path.name for path in train_images.glob("*") if path.is_file()}
    annotation_names = {record["image_id"] for record in records}
    image_integrity = Counter()
    dimensions = Counter()
    modes = Counter()
    corrupt_ids = []
    for path in sorted(train_images.glob("*")):
        if not path.is_file():
            continue
        result = inspect_image(path)
        if result["valid"]:
            image_integrity["valid"] += 1
            dimensions[(result["width"], result["height"])] += 1
            modes[result["mode"]] += 1
        else:
            image_integrity["corrupt"] += 1
            corrupt_ids.append(path.name)

    val_csv = root / "mcocr_val_sample_df.csv"
    val_annotation_rows = 0
    val_columns = []
    if val_csv.is_file():
        with val_csv.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            val_columns = reader.fieldnames or []
            val_annotation_rows = sum(1 for _ in reader)
    return {
        "dataset_root": root,
        "source_files": {
            "kie_train_csv": (root / "mcocr_train_df.csv").is_file(),
            "kie_validation_sample_csv": val_csv.is_file(),
            "text_detector_annotations": sum(
                1 for _ in (root / "text_detector" / "text_detector" / "txt").glob("*.txt")
            ),
            "text_recognition_train_pairs": sum(
                1 for _ in (root / "text_recognition_train_data.txt").open(encoding="utf-8-sig")
            ) if (root / "text_recognition_train_data.txt").is_file() else 0,
            "text_recognition_validation_pairs": sum(
                1 for _ in (root / "text_recognition_val_data.txt").open(encoding="utf-8-sig")
            ) if (root / "text_recognition_val_data.txt").is_file() else 0,
        },
        "ocr_exports": summarize_ocr_exports(root),
        "image_inventory": {
            "train_image_count": len(train_names),
            "train_annotation_count": len(annotation_names),
            "unpaired_train_images": len(train_names - annotation_names),
            "annotations_without_image": len(annotation_names - train_names),
            "validation_image_count": sum(1 for path in val_images.glob("*") if path.is_file()),
            "validation_sample_rows": val_annotation_rows,
            "validation_has_kie_labels": "anno_labels" in val_columns,
            "validation_has_kie_polygons": "anno_polygons" in val_columns,
        },
        "image_integrity": dict(image_integrity),
        "image_dimensions": {f"{w}x{h}": n for (w, h), n in sorted(dimensions.items())},
        "color_modes": dict(modes),
        "corrupt_image_ids": corrupt_ids,
        "annotations": summarize_annotations(records),
    }
