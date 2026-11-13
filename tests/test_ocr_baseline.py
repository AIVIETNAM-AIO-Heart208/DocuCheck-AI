import hashlib
import json

from PIL import Image

from docucheck.ocr.baseline import TesseractBaseline, parse_tesseract_tsv
from docucheck.ocr.inference import run_batch
from scripts import run_ocr as cli


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
        engine_name = "Tesseract"
        model_names = {"recognition": "vie.traineddata"}
        model_source = "synthetic"
        model_sha256 = "fake-hash"
        engine_version = "tesseract 5.x"
        language = "vie"
        page_segmentation_mode = 6
        ocr_engine_mode = 1
        model_load_seconds = 0.0
        device = "cpu"
        preprocessing = {"page_segmentation_mode": 6}

        def predict(self, image_path):
            if image_path.name == "invalid.jpg":
                raise ValueError("invalid image")
            return [{"text": "MẪU", "polygon": [[1, 1], [8, 1], [8, 4], [1, 4]], "confidence": 0.8}]

    metadata = run_batch(
        records, dataset_root=tmp_path, split="internal_dev", output_dir=tmp_path / "out",
        engine=FakeEngine(), manifest_sha256="manifest-hash",
    )
    predictions = [json.loads(line) for line in (tmp_path / "out" / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    failures = [json.loads(line) for line in (tmp_path / "out" / "failures.jsonl").read_text(encoding="utf-8").splitlines()]
    assert metadata["images_succeeded"] == 1
    assert metadata["images_failed"] == 1
    assert metadata["preprocessing"]["page_segmentation_mode"] == 6
    assert metadata["manifest_sha256"] == "manifest-hash"
    assert predictions[0]["predictions"][0]["polygon"][2] == [8, 4]
    assert failures[0]["error_type"] == "ValueError"


def test_ocr_cli_defaults_to_psm_6_and_accepts_explicit_mode():
    assert cli.build_parser().parse_args([]).psm == 6
    assert cli.build_parser().parse_args([]).engine == "tesseract"
    assert cli.build_parser().parse_args(["--psm", "11"]).psm == 11
    assert cli.build_parser().parse_args(["--engine", "paddle-vietocr"]).engine == "paddle-vietocr"
    assert cli.build_parser().parse_args(["--engine", "phocr-vietocr"]).engine == "phocr-vietocr"
    assert cli.build_parser().parse_args(["--device", "cuda:0"]).device == "cuda:0"
    assert cli.build_parser().parse_args(["--engine", "vietocr"]).scale_factor is None
    assert cli.build_parser().parse_args(["--engine", "vietocr", "--scale-factor", "2"]).scale_factor == 2


def test_ocr_cli_forwards_vietocr_scale_factor(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "image_id": "crop", "image_path": "crop.png", "split": "official_val",
        "source_subset": "text_recognition",
    }) + "\n")
    calls = {}

    class Engine:
        pass

    def fake_engine(**kwargs):
        calls["engine"] = kwargs
        return Engine()

    def fake_run(records, **kwargs):
        calls["run"] = kwargs
        return {
            "engine": "VietOCR", "engine_version": "test", "model_names": {}, "model_sha256": "hash",
            "device": "cpu", "split": "official_val", "manifest_record_count": 1,
            "images_succeeded": 1, "images_failed": 0, "mean_successful_image_latency_seconds": 0.0,
        }

    monkeypatch.setattr(cli, "VietOCRBaseline", fake_engine)
    monkeypatch.setattr(cli, "run_batch", fake_run)
    assert cli.main([
        "--engine", "vietocr", "--manifest", str(manifest), "--split", "official_val",
        "--output-dir", str(tmp_path / "e1-default"),
    ]) == 0
    assert calls["engine"] == {"device": "cpu", "scale_factor": 2}
    assert cli.main([
        "--engine", "vietocr", "--scale-factor", "1", "--manifest", str(manifest),
        "--split", "official_val", "--output-dir", str(tmp_path / "e0"),
    ]) == 0
    assert calls["engine"] == {"device": "cpu", "scale_factor": 1}
    assert cli.main([
        "--engine", "vietocr", "--scale-factor", "2", "--manifest", str(manifest),
        "--split", "official_val",
        "--output-dir", str(tmp_path / "e1"),
    ]) == 0
    assert calls["engine"] == {"device": "cpu", "scale_factor": 2}
    assert calls["run"]["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert "VietOCR" in capsys.readouterr().out


def test_ocr_cli_keeps_tesseract_default_scale(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image_id": "crop", "image_path": "crop.png", "split": "official_val"}) + "\n")
    calls = {}

    def fake_run(records, **kwargs):
        calls.update(kwargs)
        return {
            "engine": "Tesseract", "engine_version": "test", "model_names": {}, "model_sha256": "hash",
            "device": "cpu", "split": "official_val", "manifest_record_count": 1,
            "images_succeeded": 1, "images_failed": 0, "mean_successful_image_latency_seconds": 0.0,
        }

    monkeypatch.setattr(cli, "run_batch", fake_run)
    assert cli.main([
        "--engine", "tesseract", "--manifest", str(manifest), "--split", "official_val",
        "--output-dir", str(tmp_path / "tesseract"),
    ]) == 0
    assert calls["engine"] is None


def test_ocr_cli_rejects_scale_for_non_vietocr(tmp_path, capsys):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image_id": "crop", "image_path": "crop.png", "split": "official_val"}) + "\n")
    assert cli.main([
        "--engine", "tesseract", "--scale-factor", "2", "--manifest", str(manifest),
    ]) == 2
    assert "only with --engine vietocr or --engine phocr-vietocr" in capsys.readouterr().err
    assert cli.main([
        "--engine", "paddle-vietocr", "--scale-factor", "2", "--manifest", str(manifest),
    ]) == 2
    assert "only with --engine vietocr or --engine phocr-vietocr" in capsys.readouterr().err


def test_ocr_cli_rejects_missing_manifest(tmp_path):
    assert cli.main(["--manifest", str(tmp_path / "missing.jsonl")]) == 2


def test_ocr_cli_reports_missing_hybrid_model(tmp_path, capsys):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image_id": "receipt", "image_path": "receipt.png", "split": "internal_dev"}) + "\n")

    assert cli.main([
        "--engine", "paddle-vietocr", "--manifest", str(manifest),
        "--dataset-root", str(tmp_path), "--detector-model-dir", str(tmp_path / "missing-model"),
    ]) == 1
    assert "PaddleOCR detector model not found" in capsys.readouterr().err


def test_ocr_cli_rejects_recognition_manifest_for_hybrid(tmp_path, capsys):
    manifest = tmp_path / "recognition_manifest.jsonl"
    manifest.write_text(json.dumps({
        "image_id": "crop", "image_path": "crop.png", "split": "official_val",
        "source_subset": "text_recognition",
    }) + "\n")

    assert cli.main([
        "--engine", "paddle-vietocr", "--manifest", str(manifest), "--split", "official_val",
    ]) == 2
    assert "does not accept recognition-crop records" in capsys.readouterr().err


def test_ocr_cli_reports_missing_phocr_model(tmp_path, capsys):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image_id": "receipt", "image_path": "receipt.png", "split": "internal_dev"}) + "\n")

    assert cli.main([
        "--engine", "phocr-vietocr", "--manifest", str(manifest),
        "--dataset-root", str(tmp_path), "--phocr-model-path", str(tmp_path / "missing.onnx"),
    ]) == 1
    assert "PHOCR detector model not found" in capsys.readouterr().err


def test_ocr_cli_selects_phocr_hybrid_without_merge_option(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image_id": "receipt", "image_path": "receipt.png", "split": "internal_dev"}) + "\n")
    calls = {}

    class Detector:
        pass

    class Recognizer:
        pass

    def fake_detector(**kwargs):
        calls["detector"] = kwargs
        return Detector()

    def fake_recognizer(**kwargs):
        calls["recognizer"] = kwargs
        return Recognizer()

    monkeypatch.setattr(cli, "PHOCRTextDetector", fake_detector)
    monkeypatch.setattr(cli, "VietOCRBaseline", fake_recognizer)

    def fake_run(records, **kwargs):
        calls["run"] = kwargs
        return {
            "pipeline": "phocr-detector-vietocr", "detector": "PHOCRTextDetection", "detector_version": "test",
            "recognizer": "VietOCR", "recognizer_version": "test", "split": "internal_dev",
            "detector_device": "cuda:0", "recognizer_device": "cuda:0", "manifest_record_count": 1,
            "images_succeeded": 1, "images_partial": 0, "images_failed": 0, "detected_candidates": 1,
            "recognized_candidates": 1, "candidate_failures": 0, "receipt_failures": 0,
        }

    monkeypatch.setattr(cli, "run_hybrid_batch", fake_run)
    assert cli.main([
        "--engine", "phocr-vietocr", "--manifest", str(manifest), "--device", "cuda:0",
        "--phocr-model-path", "detector.onnx", "--model-path", "vietocr.pth",
    ]) == 0
    assert calls["detector"] == {"model_path": "detector.onnx", "device": "cuda:0"}
    assert calls["recognizer"] == {"model_path": "vietocr.pth", "device": "cuda:0"}
    assert calls["run"]["crop_padding_percent"] == 10
    assert "merge_lines" not in calls["run"]


def test_ocr_cli_forwards_phocr_e1_scale(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image_id": "receipt", "image_path": "receipt.png", "split": "internal_dev"}) + "\n")
    calls = {}

    monkeypatch.setattr(cli, "PHOCRTextDetector", lambda **kwargs: calls.setdefault("detector", kwargs) or object())
    monkeypatch.setattr(cli, "VietOCRBaseline", lambda **kwargs: calls.setdefault("recognizer", kwargs) or object())

    def fake_run(records, **kwargs):
        calls["run"] = kwargs
        return {
            "pipeline": "phocr-detector-vietocr", "detector": "PHOCRTextDetection", "detector_version": "test",
            "recognizer": "VietOCR", "recognizer_version": "test", "split": "internal_dev",
            "detector_device": "cpu", "recognizer_device": "cpu", "manifest_record_count": 1,
            "images_succeeded": 1, "images_partial": 0, "images_failed": 0, "detected_candidates": 1,
            "recognized_candidates": 1, "candidate_failures": 0, "receipt_failures": 0,
        }

    monkeypatch.setattr(cli, "run_hybrid_batch", fake_run)
    assert cli.main([
        "--engine", "phocr-vietocr", "--scale-factor", "2", "--manifest", str(manifest),
        "--model-path", "vietocr.pth", "--phocr-model-path", "detector.onnx",
    ]) == 0
    assert calls["recognizer"] == {"model_path": "vietocr.pth", "device": "cpu", "scale_factor": 2}
    assert calls["run"]["crop_padding_percent"] == 10


def test_ocr_cli_keeps_paddle_hybrid_padding_disabled(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image_id": "receipt", "image_path": "receipt.png", "split": "internal_dev"}) + "\n")
    calls = {}

    monkeypatch.setattr(cli, "PaddleOCRTextDetector", lambda **kwargs: calls.setdefault("detector", kwargs) or object())
    monkeypatch.setattr(cli, "VietOCRBaseline", lambda **kwargs: calls.setdefault("recognizer", kwargs) or object())

    def fake_run(records, **kwargs):
        calls["run"] = kwargs
        return {
            "pipeline": "paddle-detector-vietocr", "detector": "PaddleOCRTextDetection", "detector_version": "test",
            "recognizer": "VietOCR", "recognizer_version": "test", "split": "internal_dev",
            "detector_device": "cpu", "recognizer_device": "cpu", "manifest_record_count": 1,
            "images_succeeded": 1, "images_partial": 0, "images_failed": 0, "detected_candidates": 1,
            "recognized_candidates": 1, "candidate_failures": 0, "receipt_failures": 0,
        }

    monkeypatch.setattr(cli, "run_hybrid_batch", fake_run)
    assert cli.main([
        "--engine", "paddle-vietocr", "--manifest", str(manifest),
    ]) == 0
    assert calls["run"]["crop_padding_percent"] == 0


def test_batch_runtime_records_explicit_engine_psm(tmp_path):
    image = tmp_path / "crop.jpg"
    Image.new("RGB", (20, 10), "white").save(image)

    class FakeEngine:
        engine_name = "Tesseract"
        model_names = {"recognition": "vie.traineddata"}
        model_source = model_sha256 = engine_version = "synthetic"
        language = "vie"
        page_segmentation_mode = 11
        ocr_engine_mode = 1
        model_load_seconds = 0.0
        device = "cpu"
        preprocessing = {"page_segmentation_mode": 11}

        def predict(self, image_path):
            return []

    metadata = run_batch(
        [{"image_id": "crop", "image_path": "crop.jpg", "split": "official_val"}],
        dataset_root=tmp_path,
        split="official_val",
        output_dir=tmp_path / "out",
        engine=FakeEngine(),
    )
    assert metadata["preprocessing"]["page_segmentation_mode"] == 11
