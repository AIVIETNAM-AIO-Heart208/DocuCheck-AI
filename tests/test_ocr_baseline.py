import json

from PIL import Image

from docucheck.ocr.baseline import TesseractBaseline, parse_tesseract_tsv
from docucheck.ocr.inference import run_batch


def test_tsv_parser_preserves_vietnamese_text_polygon_and_confidence():
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t10\t20\t50\t12\t91.5\tCỬA HÀNG\n"
    )
    prediction = parse_tesseract_tsv(tsv)[0]
    assert prediction["text"] == "CỬA HÀNG"
    assert prediction["polygon"] == [[10.0, 20.0], [60.0, 20.0], [60.0, 32.0], [10.0, 32.0]]
    assert prediction["confidence"] == 0.915


def test_tsv_parser_drops_empty_and_zero_area_rows():
    tsv = (
        "level\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t2\t0\t10\t90\tbad box\n"
        "5\t1\t2\t10\t10\t-1\t\n"
    )
    assert parse_tesseract_tsv(tsv) == []


def test_invalid_image_is_not_reported_as_empty_recognition(tmp_path):
    invalid = tmp_path / "invalid.jpg"
    invalid.write_text("not an image", encoding="utf-8")
    baseline = TesseractBaseline.__new__(TesseractBaseline)
    try:
        baseline.predict(invalid)
    except ValueError as error:
        assert "Invalid or unreadable" in str(error)
    else:
        raise AssertionError("Expected invalid image to raise")


def test_batch_saves_spatial_predictions_and_failures_locally(tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    Image.new("RGB", (20, 10), "white").save(image_dir / "valid.jpg")
    (image_dir / "invalid.jpg").write_text("bad", encoding="utf-8")
    records = [
        {"image_id": "valid-id", "image_path": "images/valid.jpg", "split": "internal_dev", "source_split": "train"},
        {"image_id": "bad-id", "image_path": "images/invalid.jpg", "split": "internal_dev", "source_split": "train"},
    ]

    class FakeEngine:
        model_names = {"recognition": "vie.traineddata"}
        model_source = "synthetic"
        model_sha256 = "fake-hash"
        engine_version = "tesseract 5.x"
        language = "vie"
        page_segmentation_mode = 6
        ocr_engine_mode = 1
        model_load_seconds = 0.0
        device = "cpu"

        def predict(self, image_path):
            if image_path.name == "invalid.jpg":
                raise ValueError("invalid image")
            return [{"text": "MẪU", "polygon": [[1, 1], [8, 1], [8, 4], [1, 4]], "confidence": 0.8}]

    metadata = run_batch(records, dataset_root=tmp_path, split="internal_dev", output_dir=tmp_path / "out", engine=FakeEngine())
    predictions = [json.loads(line) for line in (tmp_path / "out" / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    failures = [json.loads(line) for line in (tmp_path / "out" / "failures.jsonl").read_text(encoding="utf-8").splitlines()]
    assert metadata["images_succeeded"] == 1
    assert metadata["images_failed"] == 1
    assert predictions[0]["predictions"][0]["polygon"][2] == [8, 4]
    assert failures[0]["error_type"] == "ValueError"
