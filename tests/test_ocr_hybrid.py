import hashlib
import json

from PIL import Image

from docucheck.ocr.hybrid import run_hybrid_batch
from docucheck.ocr.recognizers import VietOCRBaseline


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


def test_hybrid_batch_preserves_direct_candidates_and_disables_padding(tmp_path):
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
    )
    prediction = json.loads((tmp_path / "out" / "predictions.jsonl").read_text(encoding="utf-8"))
    candidates = prediction["predictions"]
    assert [candidate["candidate_id"] for candidate in candidates] == [
        "receipt:candidate-0001", "receipt:candidate-0002",
    ]
    assert all("source_candidate_ids" not in candidate for candidate in candidates)
    assert metadata["detected_candidates"] == 2
    assert metadata["recognized_candidates"] == 2
    assert "line_merge" not in metadata
    assert "pre_merge_candidates" not in metadata
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


def test_hybrid_batch_applies_e1_and_preserves_input_provenance(tmp_path):
    records = _records(tmp_path)[:1]
    source = tmp_path / "images" / "b.png"
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(records[0]) + "\n", encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    model = tmp_path / "model.pth"
    model.write_bytes(b"model")
    seen_sizes = []

    class Backend:
        def predict(self, image, return_prob=False):
            seen_sizes.append(image.size)
            return "MẪU", 0.9

    recognizer = VietOCRBaseline(model_path=model, backend=Backend(), scale_factor=2)
    output = tmp_path / "out"
    metadata = run_hybrid_batch(
        records,
        dataset_root=tmp_path,
        split="internal_dev",
        output_dir=output,
        detector=FakeDetector(),
        recognizer=recognizer,
        crop_padding_percent=5,
    )

    assert seen_sizes == [(84, 32)]
    prediction = json.loads((output / "predictions.jsonl").read_text(encoding="utf-8"))
    assert prediction["predictions"][0]["polygon"] == [
        [5.0, 5.0], [45.0, 5.0], [45.0, 20.0], [5.0, 20.0],
    ]
    assert metadata["preprocessing"]["recognizer"]["experiment"] == "E1"
    assert metadata["preprocessing"]["recognizer"]["scale_factor"] == 2
    assert metadata["preprocessing"]["recognizer"]["resampling"] == "LANCZOS"
    assert metadata["preprocessing"]["crop"]["padding_percent"] == 5
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == manifest_hash
