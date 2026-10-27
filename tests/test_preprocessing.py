import csv
import shutil

import pytest
from PIL import Image

from docucheck.data.preprocessing import prepare_records
from docucheck.data.splitting import find_cross_split_duplicate_groups
from docucheck.data.validation import validate_manifest


def _write_dataset(root, *, invalid_geometry=False, include_duplicate_validation=True):
    train_dir = root / "train_images" / "train_images"
    val_dir = root / "val_images" / "val_images"
    train_dir.mkdir(parents=True)
    val_dir.mkdir(parents=True)
    Image.new("RGB", (40, 30), "white").save(train_dir / "receipt_a.jpg")
    shutil.copyfile(train_dir / "receipt_a.jpg", train_dir / "receipt_b.jpg")
    Image.new("RGB", (40, 30), "black").save(train_dir / "other.jpg")
    if include_duplicate_validation:
        shutil.copyfile(train_dir / "receipt_a.jpg", val_dir / "validation.jpg")

    polygon = [[-1, 2, 20, 2, 20, 12, -1, 12]] if invalid_geometry else [[1, 2, 20, 2, 20, 12, 1, 12]]
    rows = []
    for name in ("receipt_a.jpg", "receipt_b.jpg"):
        rows.append({
            "img_id": name,
            "anno_polygons": repr([{"category_id": 15, "segmentation": polygon}]),
            "anno_texts": "CỬA HÀNG MẪU",
            "anno_labels": "SELLER",
            "anno_num": "1",
            "anno_image_quality": "0.5",
        })
    with (root / "mcocr_train_df.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for name in ("text_recognition_train_data.txt", "text_recognition_val_data.txt"):
        (root / name).write_text("", encoding="utf-8")


def test_prepare_records_retains_provenance_unicode_and_quarantines_duplicates(tmp_path):
    _write_dataset(tmp_path)
    records, recognition, report = prepare_records(tmp_path, seed=42, validation_fraction=0.5)
    train = [row for row in records if row["source_split"] == "train"]
    duplicate_rows = [row for row in train if row["source_image_name"].startswith("receipt_")]

    assert len(records) == 4
    assert len(recognition) == 0
    assert all(row["image_path"].startswith("train_images/") for row in train)
    assert all(row["image_id"] != row["source_image_name"] for row in train)
    assert duplicate_rows[0]["image_group_id"] == duplicate_rows[1]["image_group_id"]
    assert duplicate_rows[0]["split"] == duplicate_rows[1]["split"] == "excluded_duplicate_of_official_validation"
    assert report["official_validation_duplicate_quarantine_count"] == 2
    assert report["cross_split_duplicate_group_count"] == 0
    assert find_cross_split_duplicate_groups(records) == {}
    assert duplicate_rows[0]["regions"][0]["text_raw"] == "CỬA HÀNG MẪU"
    assert duplicate_rows[0]["regions"][0]["bbox_xyxy"] == [1.0, 2.0, 20.0, 12.0]
    assert validate_manifest(records)["valid"]


def test_invalid_geometry_is_reported_or_skipped_explicitly(tmp_path):
    _write_dataset(tmp_path, invalid_geometry=True, include_duplicate_validation=False)
    records, _, report = prepare_records(tmp_path, invalid_policy="report")
    assert report["invalid_record_count"] == 2
    assert report["geometry_issue_counts"]["out_of_image_bounds"] == 2
    assert len(records) == 3

    skipped, _, skip_report = prepare_records(tmp_path, invalid_policy="skip")
    assert len(skipped) == 1
    assert skip_report["skipped_record_count"] == 2


def test_prepare_fail_policy_rejects_invalid_records(tmp_path):
    _write_dataset(tmp_path, invalid_geometry=True, include_duplicate_validation=False)
    with pytest.raises(ValueError, match="invalid records"):
        prepare_records(tmp_path, invalid_policy="fail")
