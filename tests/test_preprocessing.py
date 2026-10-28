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


def _rewrite_csv(root, transform):
    path = root / "mcocr_train_df.csv"
    with path.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    rows = transform(rows)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_duplicate_csv_ids_preserved_with_distinct_record_ids(tmp_path):
    _write_dataset(tmp_path)
    _rewrite_csv(tmp_path, lambda rows: rows + [dict(rows[0], anno_texts="Another annotation")])
    records, _, _ = prepare_records(tmp_path)
    copies = [r for r in records if r["source_image_name"] == "receipt_a.jpg"]
    assert len(copies) == 2
    assert len({r["image_id"] for r in copies}) == 2
    assert {r["regions"][0]["text_raw"] for r in copies} == {"CỬA HÀNG MẪU", "Another annotation"}
    assert all("duplicate_source_image_id" in r["annotation_issues"] for r in copies)
    assert validate_manifest(records)["valid"]


def test_parse_failures_missing_image_and_raw_arrays_are_preserved(tmp_path):
    _write_dataset(tmp_path)
    _rewrite_csv(tmp_path, lambda rows: [dict(rows[0], anno_polygons="broken [", anno_texts="", anno_labels="UNKNOWN"), rows[1]])
    (tmp_path / "train_images/train_images/receipt_a.jpg").unlink()
    records, _, report = prepare_records(tmp_path)
    row = next(r for r in records if r["source_image_name"] == "receipt_a.jpg")
    assert row["image_status"] == "missing_file"
    assert row["source_annotations"]["anno_polygons"] == "broken ["
    assert row["polygon_parse_error"] == "SyntaxError"
    assert {"polygon_parse_failure", "source_array_length_mismatch", "unmapped_label"} <= set(row["annotation_issues"])
    assert row["regions"][0]["canonical_field"] is None
    assert row["regions"][0]["text_status"] == "missing_in_source"
    assert row["ocr_ground_truth_status"] == "unavailable_sidecar"


def test_empty_and_malformed_sidecars_are_not_available_gt(tmp_path):
    _write_dataset(tmp_path)
    directory = tmp_path / "kie_data/kie_data/boxes_and_transcripts"
    directory.mkdir(parents=True)
    (directory / "receipt_a.tsv").write_text("", encoding="utf-8")
    (directory / "receipt_b.tsv").write_text("malformed row", encoding="utf-8")
    records, _, _ = prepare_records(tmp_path)
    by_name = {r["source_image_name"]: r for r in records}
    assert by_name["receipt_a.jpg"]["ocr_ground_truth_status"] == "empty_sidecar"
    bad = by_name["receipt_b.jpg"]
    assert bad["ocr_ground_truth_status"] == "no_usable_transcriptions"
    assert bad["ocr_regions"][0]["source_raw"] == "malformed row"
    assert bad["ocr_regions"][0]["source_issue"] == "unexpected_field_count"


def test_recognition_pairs_have_separate_provenance_and_preserve_repeated_lines(tmp_path):
    _write_dataset(tmp_path)
    (tmp_path / "text_recognition_train_data.txt").write_text(
        "train_images/train_images/receipt_a.jpg\ttext one\n"
        "train_images/train_images/receipt_a.jpg\t\n", encoding="utf-8")
    _, recognition, report = prepare_records(tmp_path)
    assert len(recognition) == 2
    assert len({r["image_id"] for r in recognition}) == 2
    assert [r["text_status"] for r in recognition] == ["present", "empty_in_source"]
    assert all(r["annotation_source"] == "text_recognition_train_data.txt" for r in recognition)
    assert all("canonical_field" not in r and "parent_image_id" not in r for r in recognition)
    assert report["invalid_recognition_record_count"] == 2
    assert validate_manifest(recognition)["valid"]


def test_preparation_reproducibility_and_schema_across_all_subsets(tmp_path):
    import hashlib
    from docucheck.data.preprocessing import write_jsonl
    _write_dataset(tmp_path)
    first = prepare_records(tmp_path)
    second = prepare_records(tmp_path)
    for i in (0, 1):
        write_jsonl(tmp_path / f"first{i}.jsonl", first[i])
        write_jsonl(tmp_path / f"second{i}.jsonl", second[i])
        assert hashlib.sha256((tmp_path / f"first{i}.jsonl").read_bytes()).digest() == hashlib.sha256((tmp_path / f"second{i}.jsonl").read_bytes()).digest()
    assert all(r["schema_version"] == "1.1" for r in first[0] + first[1])


@pytest.mark.parametrize("identifier", ["", "../escape.jpg", "C:/private/a.jpg"])
def test_invalid_source_identifier_fails_explicitly(tmp_path, identifier):
    _write_dataset(tmp_path)
    _rewrite_csv(tmp_path, lambda rows: [dict(rows[0], img_id=identifier)])
    with pytest.raises(ValueError, match="Invalid source image identifier"):
        prepare_records(tmp_path)


def test_corrupt_images_and_missing_official_inventory_files_are_retained(tmp_path):
    _write_dataset(tmp_path)
    (tmp_path / "train_images/train_images/receipt_b.jpg").write_bytes(b"not an image")
    (tmp_path / "mcocr_val_sample_df.csv").write_text("img_id,anno_texts\nmissing.jpg,\n", encoding="utf-8")
    records, _, _ = prepare_records(tmp_path)
    by_name = {r["source_image_name"]: r for r in records}
    assert by_name["receipt_b.jpg"]["image_status"] == "UnidentifiedImageError"
    assert by_name["missing.jpg"]["image_status"] == "missing_file"
    assert by_name["missing.jpg"]["source_split"] == "official_validation"


def test_jsonl_nonfinite_source_geometry_is_strict_json(tmp_path):
    import json
    from docucheck.data.preprocessing import write_jsonl
    path = tmp_path / "invalid.jsonl"
    write_jsonl(path, [{"polygon": [[float("inf"), float("nan")]], "validation_issues": ["non_finite_coordinates"]}])
    def reject(value):
        raise AssertionError(f"Non-standard JSON: {value}")
    result = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)
    assert result["polygon"] == [["inf", "nan"]]
