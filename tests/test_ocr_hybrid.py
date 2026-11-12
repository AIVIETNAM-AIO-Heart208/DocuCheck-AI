import json

from PIL import Image

from docucheck.ocr.hybrid import merge_line_candidates, run_hybrid_batch


class FakeDetector:
    engine_name = "PaddleOCRTextDetection"
    engine_version = "test"
    model_names = {"detection": "test-detector"}
    model_source = "synthetic"
    model_sha256 = "detector-hash"
    device = "cpu"
    model_load_seconds = 0.0
    preprocessing = {"mode": "text-detection-only"}

    def __init__(self):
        self.last_issues = []

    def predict(self, image_path):
        self.last_issues = []
        return [{
            "region_index": 0,
            "polygon": [[5.0, 5.0], [45.0, 5.0], [45.0, 20.0], [5.0, 20.0]],
            "confidence": 0.9,
        }]


class FakeRecognizer:
    engine_name = "VietOCR"
    engine_version = "test"
    model_names = {"recognition": "test-recognizer"}
    model_source = "synthetic"
    model_sha256 = "recognizer-hash"
    device = "cpu"
    model_load_seconds = 0.0
    preprocessing = {"mode": "recognition-only"}

    def __init__(self, *, error=False, empty=False):
        self.error = error
        self.empty = empty

    def predict(self, image_path):
        if self.error:
            raise RuntimeError("recognizer failed")
        if self.empty:
            return []
        return [{"text": "TỔNG CỘNG 39.000", "confidence": 0.8}]


def _candidate(candidate_id, polygon, confidence=None):
    return {
        "candidate_id": candidate_id,
        "polygon": polygon,
        "confidence": confidence,
    }


def test_merge_line_preserves_single_polygon_and_orders_lines():
    single = [[12.0, 10.0], [42.0, 12.0], [40.0, 22.0], [10.0, 20.0]]
    merged = merge_line_candidates([
        _candidate("b", [[50, 40], [70, 40], [70, 50], [50, 50]], 0.8),
        _candidate("a", single, 0.9),
    ])
    assert [row["source_candidate_ids"] for row in merged] == [["a"], ["b"]]
    assert merged[0]["polygon"] == single


def test_merge_line_unions_same_line_and_keeps_separate_line():
    merged = merge_line_candidates([
        _candidate("right", [[35, 10], [55, 10], [55, 20], [35, 20]], 0.8),
        _candidate("left", [[5, 10], [25, 10], [25, 20], [5, 20]], 0.9),
        _candidate("below", [[5, 35], [25, 35], [25, 45], [5, 45]], 0.7),
    ])
    assert [row["source_candidate_ids"] for row in merged] == [["left", "right"], ["below"]]
    assert merged[0]["polygon"] == [[5.0, 10.0], [55.0, 10.0], [55.0, 20.0], [5.0, 20.0]]
    assert merged[0]["confidence"] == 0.8


def _records(tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    for name in ("a.png", "b.png"):
        Image.new("RGB", (80, 40), "white").save(image_dir / name)
    return [
        {"image_id": "b", "image_path": "images/b.png", "source_split": "train", "source_subset": "kie_train", "split": "internal_dev"},
        {"image_id": "a", "image_path": "images/a.png", "source_split": "train", "source_subset": "kie_train", "split": "internal_dev"},
    ]


def test_hybrid_batch_preserves_sorted_receipt_and_candidate_evidence(tmp_path):
    metadata = run_hybrid_batch(
        _records(tmp_path)[:1],
        dataset_root=tmp_path,
        split="internal_dev",
        output_dir=tmp_path / "out",
        detector=FakeDetector(),
        recognizer=FakeRecognizer(),
    )

    prediction = json.loads((tmp_path / "out" / "predictions.jsonl").read_text(encoding="utf-8"))
    assert prediction["image_id"] == "b"
    assert prediction["status"] == "ok"
    candidate = prediction["predictions"][0]
    assert candidate["candidate_id"] == "b:candidate-0001"
    assert candidate["polygon"] == [[5.0, 5.0], [45.0, 5.0], [45.0, 20.0], [5.0, 20.0]]
    assert candidate["detector_confidence"] == 0.9
    assert candidate["text"] == "TỔNG CỘNG 39.000"
    assert candidate["recognition_confidence"] == 0.8
    assert candidate["recognition_status"] == "ok"
    assert metadata["detected_candidates"] == metadata["recognized_candidates"] == 1
    assert metadata["images_succeeded"] == 1


def test_hybrid_batch_separates_recognition_failure_from_empty_text(tmp_path):
    records = _records(tmp_path)
    output = tmp_path / "out"
    metadata = run_hybrid_batch(
        records,
        dataset_root=tmp_path,
        split="internal_dev",
        output_dir=output,
        detector=FakeDetector(),
        recognizer=FakeRecognizer(error=True),
    )

    predictions = [json.loads(line) for line in (output / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    failures = [json.loads(line) for line in (output / "failures.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["image_id"] for row in predictions] == ["a", "b"]
    assert all(row["status"] == "partial" for row in predictions)
    assert all(row["predictions"] == [] for row in predictions)
    assert all(row["stage"] == "recognition" for row in failures)
    assert all(row["error_type"] == "RuntimeError" for row in failures)
    assert metadata["images_partial"] == 2
    assert metadata["recognized_candidates"] == 0


def test_hybrid_batch_records_empty_recognition_as_successful_candidate(tmp_path):
    output = tmp_path / "out"
    run_hybrid_batch(
        _records(tmp_path)[:1],
        dataset_root=tmp_path,
        split="internal_dev",
        output_dir=output,
        detector=FakeDetector(),
        recognizer=FakeRecognizer(empty=True),
    )

    prediction = json.loads((output / "predictions.jsonl").read_text(encoding="utf-8"))
    assert prediction["status"] == "ok"
    assert prediction["predictions"][0]["text"] == ""
    assert prediction["predictions"][0]["recognition_status"] == "empty"
    assert (output / "failures.jsonl").read_text(encoding="utf-8") == ""


def test_hybrid_batch_merge_line_preserves_members_and_disables_padding(tmp_path):
    image = tmp_path / "images" / "receipt.png"
    image.parent.mkdir()
    Image.new("RGB", (80, 50), "white").save(image)
    records = [{
        "image_id": "receipt",
        "image_path": "images/receipt.png",
        "source_split": "train",
        "split": "internal_dev",
    }]

    class Detector(FakeDetector):
        def predict(self, image_path):
            return [
                {"region_index": 0, "polygon": [[5, 5], [25, 5], [25, 15], [5, 15]], "confidence": 0.9},
                {"region_index": 1, "polygon": [[30, 5], [50, 5], [50, 15], [30, 15]], "confidence": 0.8},
            ]

    metadata = run_hybrid_batch(
        records,
        dataset_root=tmp_path,
        split="internal_dev",
        output_dir=tmp_path / "out",
        detector=Detector(),
        recognizer=FakeRecognizer(),
        merge_lines=True,
    )
    prediction = json.loads((tmp_path / "out" / "predictions.jsonl").read_text(encoding="utf-8"))
    candidate = prediction["predictions"][0]
    assert candidate["candidate_id"] == "receipt:line-0001"
    assert candidate["source_candidate_ids"] == ["receipt:candidate-0001", "receipt:candidate-0002"]
    assert metadata["pre_merge_candidates"] == 2
    assert metadata["post_merge_candidates"] == 1
    assert metadata["preprocessing"]["crop"]["padding_percent"] == 0


def test_hybrid_batch_rejects_recognition_manifest_records(tmp_path):
    image = tmp_path / "crop.png"
    Image.new("RGB", (20, 10), "white").save(image)
    records = [{
        "image_id": "crop",
        "image_path": "crop.png",
        "source_subset": "text_recognition",
        "split": "official_val",
    }]
    try:
        run_hybrid_batch(
            records,
            dataset_root=tmp_path,
            split="official_val",
            output_dir=tmp_path / "out",
            detector=FakeDetector(),
            recognizer=FakeRecognizer(),
        )
    except ValueError as error:
        assert "recognition-crop" in str(error)
    else:
        raise AssertionError("Expected recognition manifest rejection")
