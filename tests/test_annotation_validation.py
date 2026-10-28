from docucheck.data.validation import validate_polygon
from docucheck.data.validation import validate_manifest
import pytest


def test_accepts_valid_polygon_inside_image():
    assert validate_polygon([[1, 1], [9, 1], [9, 8], [1, 8]], 10, 10) == []


def test_reports_invalid_polygon_geometry():
    assert validate_polygon([[1, 1], [2, 2]], 10, 10) == ["missing_or_too_few_vertices"]
    assert "zero_area" in validate_polygon([[1, 1], [2, 2], [3, 3]], 10, 10)
    assert "out_of_image_bounds" in validate_polygon([[-1, 1], [2, 1], [2, 3]], 10, 10)


def test_nonzero_area_self_intersection_and_malformed_vertices():
    assert "self_intersection" in validate_polygon([[0, 0], [6, 5], [0, 4], [4, 0]], 10, 10)
    assert validate_polygon([[0, 0, 3], [1, 0], [1, 1]], 10, 10) == ["malformed_vertices"]
    assert validate_polygon([[{}, 0], [1, 0], [1, 1]], 10, 10) == ["malformed_vertices"]
    assert "non_finite_coordinates" in validate_polygon([[float("nan"), 0], [1, 0], [1, 1]], 10, 10)
    assert "image_dimensions_unavailable" in validate_polygon([[0, 0], [1, 0], [1, 1]], 0, 0)


@pytest.mark.parametrize("path", ["C:/private/a.jpg", "C:receipt.jpg", "../a.jpg", "x/../a.jpg", "\\\\host\\share\\a.jpg", "/a.jpg", ""])
def test_cross_platform_unsafe_manifest_paths(path):
    report = validate_manifest([{"image_id": "id", "image_path": path}])
    assert report["issue_counts"]["invalid_or_absolute_image_paths"] == 1


def test_invalid_duplicate_ids_and_leakage_are_detected():
    records = [{"image_id": "a", "image_path": "a.jpg", "image_group_id": "same", "split": split}
               for split in ("internal_train", "internal_dev")]
    records.append({"image_id": None, "image_path": "b.jpg", "regions": None})
    report = validate_manifest(records)
    for key in ("duplicate_image_ids", "invalid_image_ids", "cross_split_exact_duplicate_groups", "invalid_region_arrays"):
        assert report["issue_counts"][key] == 1


def _receipt(*, schema="1.1", polygon=None):
    from docucheck.data.preprocessing import _normalize_region

    region = _normalize_region({
        "text_raw": "Cửa hàng", "label_raw": "SELLER", "canonical_field": "seller_name",
        "polygon": polygon if polygon is not None else [[1, 1], [9, 1], [9, 8], [1, 8]],
    }, 10, 10, "kie")
    return {
        "schema_version": schema, "image_id": "receipt", "image_path": "images/receipt.jpg",
        "source_subset": "kie_train", "source_split": "train", "split": "internal_train",
        "image_status": "valid", "image_width": 10, "image_height": 10,
        "regions": [region], "ocr_regions": [], "validation_issues": region["validation_issues"].copy(),
    }


@pytest.mark.parametrize("patch", [
    {"canonical_field": "total_amount"}, {"label_status": "unmapped"},
    {"label_raw": "TOTAL_TOTAL_COST", "canonical_field": "total_amount"},
    {"label_raw": ["SELLER"]}, {"text_raw": 123}, {"text_status": "empty_in_source"},
    {"bbox_xyxy": [0, 0, 10, 10]}, {"validation_issues": ["zero_area"]},
    {"annotation_source": "full_page_transcription"},
])
def test_rejects_inconsistent_region_metadata_without_mutating_source(patch):
    from copy import deepcopy

    record = _receipt()
    record["regions"][0].update(patch)
    before = deepcopy(record)
    assert not validate_manifest([record])["valid"]
    assert record == before


def test_geometry_errors_are_source_quality_until_diagnostics_or_bbox_are_wrong():
    record = _receipt(polygon=[[-1, 1], [9, 1], [9, 8], [-1, 8]])
    assert validate_manifest([record])["valid"]
    record["regions"][0]["validation_issues"] = []
    assert not validate_manifest([record])["valid"]
    record["regions"][0]["bbox_xyxy"] = [-1, 1, 9, 8]
    assert "invalid_geometry_has_derived_bbox" in validate_manifest([record])["issue_counts"]


def test_record_geometry_summary_must_match_regions():
    record = _receipt()
    record["validation_issues"] = ["out_of_image_bounds"]
    assert not validate_manifest([record])["valid"]


def test_unmapped_and_missing_labels_are_preserved_with_consistent_metadata():
    for label, status in [("TOTAL_TOTAL_COST", "unmapped"), (None, "missing_in_source"), ("", "missing_in_source")]:
        record = _receipt()
        record["regions"][0].update(label_raw=label, label_status=status, canonical_field=None)
        assert validate_manifest([record])["valid"]
        assert record["regions"][0]["label_raw"] == label


def test_schema_10_legacy_status_and_optional_label_diagnostics():
    record = _receipt(schema="1.0")
    region = record["regions"][0]
    region.pop("label_status")
    region["text_raw"] = " "
    region["text_status"] = "present"  # 1.0 distinguished null only.
    assert validate_manifest([record])["valid"]
    region["text_status"] = "empty_in_source"
    assert validate_manifest([record])["valid"]  # Already-supported explicit status.
    region["text_status"] = "present"
    record["schema_version"] = "1.1"
    assert not validate_manifest([record])["valid"]


@pytest.mark.parametrize("patch", [
    {"split": "random_split"}, {"split": ["internal_train"]},
    {"source_split": "val"}, {"source_subset": "other"},
    {"schema_version": []}, {"image_width": True}, {"image_path": "."},
    {"checksum_sha256": "a" * 64, "image_group_id": "b" * 64},
])
def test_rejects_invalid_identity_split_and_image_metadata(patch):
    record = _receipt()
    record.update(patch)
    assert not validate_manifest([record])["valid"]


def test_ocr_kie_recognition_and_inventory_are_kept_separate():
    record = _receipt()
    region = record["regions"].pop()
    region.update(annotation_source="full_page_transcription", label_raw=None,
                  canonical_field=None, label_status="not_applicable")
    record["ocr_regions"] = [region]
    assert validate_manifest([record])["valid"]
    region["canonical_field"] = "seller_name"
    assert not validate_manifest([record])["valid"]

    crop = {key: value for key, value in record.items() if key not in {"regions", "ocr_regions", "validation_issues"}}
    crop.update(source_subset="text_recognition", source_split="val", split="official_val",
                annotation_source="text_recognition_val_data.txt", text_raw="Tổng", text_status="present")
    assert validate_manifest([crop])["valid"]
    crop["regions"] = [region]
    assert not validate_manifest([crop])["valid"]

    inventory = _receipt()
    inventory.update(source_subset="official_validation", source_split="official_validation",
                     split="official_validation_inventory", regions=[],
                     annotation_status="no_kie_ground_truth_columns_observed")
    assert validate_manifest([inventory])["valid"]
    inventory["regions"] = [_receipt()["regions"][0]]
    assert not validate_manifest([inventory])["valid"]


def test_schema_10_inventory_and_recognition_allow_legacy_optional_fields():
    inventory = _receipt(schema="1.0")
    inventory.update(source_subset="official_validation", source_split="official_validation",
                     split="official_validation_inventory", regions=[],
                     annotation_status="no_kie_ground_truth_columns_observed")
    inventory.pop("validation_issues")
    assert validate_manifest([inventory])["valid"]
    crop = {key: value for key, value in inventory.items() if key not in {"regions", "ocr_regions", "annotation_status"}}
    crop.update(source_subset="text_recognition", source_split="train", split="official_train",
                text_raw="", text_status="present")
    assert validate_manifest([crop])["valid"]
