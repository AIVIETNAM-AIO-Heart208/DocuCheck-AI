import csv

from PIL import Image

from docucheck.data.loader import load_full_page_text_records, load_kie_records, summarize_annotations


def _write_fixture(root, *, polygon=None, text="CỬA HÀNG MẪU", label="SELLER"):
    image_dir = root / "train_images" / "train_images"
    image_dir.mkdir(parents=True)
    Image.new("RGB", (40, 30), "white").save(image_dir / "fixture.jpg")
    row = {
        "img_id": "fixture.jpg",
        "anno_polygons": repr(
            [{"category_id": 15, "segmentation": [[1, 2, 20, 2, 20, 12, 1, 12]]}]
            if polygon is None
            else polygon
        ),
        "anno_texts": text,
        "anno_labels": label,
        "anno_num": "1",
        "anno_image_quality": "0.5",
    }
    with (root / "mcocr_train_df.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def test_loads_vietnamese_annotation_and_maps_observed_label(tmp_path):
    _write_fixture(tmp_path)

    record = load_kie_records(tmp_path)[0]
    region = record["regions"][0]

    assert region["text_raw"] == "CỬA HÀNG MẪU"
    assert region["label_raw"] == "SELLER"
    assert region["canonical_field"] == "seller_name"
    assert region["polygon"] == [[1.0, 2.0], [20.0, 2.0], [20.0, 12.0], [1.0, 12.0]]
    assert summarize_annotations([record])["region_count"] == 1


def test_preserves_unmapped_label_and_missing_arrays(tmp_path):
    _write_fixture(tmp_path, polygon=[], text="", label="")
    # Preserve the original strings for a separate unmapped source class.
    rows = list(csv.DictReader((tmp_path / "mcocr_train_df.csv").open(encoding="utf-8")))
    rows[0]["anno_texts"] = "Tổng"
    rows[0]["anno_labels"] = "TOTAL_TOTAL_COST"
    rows[0]["anno_polygons"] = repr(
        [{"category_id": 18, "segmentation": [[1, 2, 20, 2, 20, 12, 1, 12]]}]
    )
    with (tmp_path / "mcocr_train_df.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    region = load_kie_records(tmp_path)[0]["regions"][0]
    assert region["label_raw"] == "TOTAL_TOTAL_COST"
    assert region["canonical_field"] is None
    assert region["text_raw"] == "Tổng"


def test_mismatched_source_arrays_are_not_silently_dropped(tmp_path):
    _write_fixture(tmp_path)
    path = tmp_path / "mcocr_train_df.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows[0]["anno_labels"] = "SELLER|||ADDRESS"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    record = load_kie_records(tmp_path)[0]
    assert len(record["regions"]) == 2
    assert record["regions"][1]["text_raw"] is None
    assert "source_array_length_mismatch" in summarize_annotations([record])["issue_counts"]


def test_full_page_transcript_parser_preserves_commas(tmp_path):
    sidecar_dir = tmp_path / "kie_data" / "kie_data" / "boxes_and_transcripts"
    sidecar_dir.mkdir(parents=True)
    (sidecar_dir / "fixture.tsv").write_text(
        "0,1,2,20,2,20,12,1,12,,Tổng tiền, đã thanh toán\n", encoding="utf-8"
    )
    records = load_full_page_text_records(tmp_path)
    assert records[0]["regions"][0]["text_raw"] == "Tổng tiền, đã thanh toán"
    assert records[0]["regions"][0]["polygon"] == [[1, 2], [20, 2], [20, 12], [1, 12]]
