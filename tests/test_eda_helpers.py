import csv

from PIL import Image

from docucheck.data.eda import collect_field_geometry, collect_image_features
from docucheck.data.loader import load_kie_records


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
