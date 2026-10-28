import csv

from PIL import Image

from docucheck.data.eda import collect_field_geometry, collect_image_features
from docucheck.data.loader import load_kie_records
from docucheck.data.eda import select_annotation_audit_sample, summarize_field_missingness
import pandas as pd


def test_collects_local_image_and_normalized_region_features(tmp_path):
    image_dir = tmp_path / "train_images" / "train_images"
    image_dir.mkdir(parents=True)
    Image.new("RGB", (40, 30), "white").save(image_dir / "fixture.jpg")
    row = {
        "img_id": "fixture.jpg",
        "anno_polygons": repr([{"category_id": 15, "segmentation": [[1, 2, 21, 2, 21, 12, 1, 12]]}]),
        "anno_texts": "Tên",
        "anno_labels": "SELLER",
        "anno_num": "1",
        "anno_image_quality": "0.5",
    }
    with (tmp_path / "mcocr_train_df.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    records = load_kie_records(tmp_path)
    image_features = collect_image_features(records, tmp_path)
    geometry = collect_field_geometry(records, image_features)

    assert bool(image_features.iloc[0]["image_valid"])
    assert image_features.iloc[0]["aspect_ratio"] == 40 / 30
    assert geometry.iloc[0]["center_x_normalized"] == 11 / 40
    assert geometry.iloc[0]["center_y_normalized"] == 7 / 30


def test_missingness_separates_no_label_from_unavailable_gt():
    result = summarize_field_missingness([
        {"annotation_status": "source_annotation_arrays_empty", "regions": []},
        {"annotation_status": "no_kie_ground_truth_columns_observed", "regions": []},
        {"annotation_status": "annotated", "regions": [{"canonical_field": "seller_name", "text_raw": "", "validation_issues": ["zero_area"]}]},
    ])["seller_name"]
    assert result["without_label_annotation"] == result["ground_truth_unavailable"] == result["with_label"] == 1
    assert result["with_invalid_geometry"] == result["with_missing_or_empty_text"] == 1
    assert result["confirmed_field_absent"] is None


def test_audit_sample_is_seeded_unique_and_contains_rare_cases():
    records = [{"image_id": str(i), "source_split": "train", "regions": [
        {"canonical_field": "seller_name", "label_status": "unmapped" if i == 0 else "mapped", "validation_issues": ["zero_area"] if i == 1 else []}],
        "ocr_ground_truth_status": "available"} for i in range(60)]
    records[2]["regions"] = []
    records.append({"image_id": "official", "source_split": "official_validation"})
    features = pd.DataFrame([{"image_id": str(i), "laplacian_variance": i * 10} for i in range(60)])
    sample = select_annotation_audit_sample(records, features)
    assert len(sample) == len({r["image_id"] for r in sample}) == 40
    assert {"0", "1", "2"} <= {r["image_id"] for r in sample}
    assert all(r["review_status"] == "not_reviewed" for r in sample)
    assert sample == select_annotation_audit_sample(list(reversed(records)), features)
    assert "official" not in {r["image_id"] for r in sample}
