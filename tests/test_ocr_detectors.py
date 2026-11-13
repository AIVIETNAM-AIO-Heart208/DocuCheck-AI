import numpy as np
from PIL import Image

from docucheck.ocr.detectors import PHOCRTextDetector, PaddleOCRTextDetector, crop_polygon


def test_detector_normalizes_and_sorts_fake_regions(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    image = tmp_path / "receipt.png"
    Image.new("RGB", (100, 80), "white").save(image)

    class Backend:
        def predict(self, image_path):
            assert image_path == str(image)
            return [{
                "dt_polys": np.asarray([
                    [[50, 40], [80, 40], [80, 50], [50, 50]],
                    [[10, 10], [40, 10], [40, 20], [10, 20]],
                ]),
                "dt_scores": [0.8, 0.9],
            }]

    detector = PaddleOCRTextDetector(model_dir=model, backend=Backend(), device="cuda:0")
    regions = detector.predict(image)
    assert [region["polygon"][0] for region in regions] == [[10.0, 10.0], [50.0, 40.0]]
    assert [region["confidence"] for region in regions] == [0.9, 0.8]
    assert detector.device == "gpu:0"
    assert detector.preprocessing["enable_mkldnn"] is False


def test_detector_records_invalid_regions_without_emitting_them(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    image = tmp_path / "receipt.png"
    Image.new("RGB", (100, 80), "white").save(image)

    class Backend:
        def predict(self, image_path):
            return [{
                "dt_polys": [
                    [[0, 0], [20, 0], [20, 10], [0, 10]],
                    [[-1, 0], [20, 0], [20, 10], [-1, 10]],
                    [[0, 0], [0, 0], [0, 0], [0, 0]],
                    [[float("nan"), 0], [20, 0], [20, 10], [0, 10]],
                    None,
                ],
                "dt_scores": [0.9, 0.8, 0.7, 0.6, 0.5],
            }]

    detector = PaddleOCRTextDetector(model_dir=model, backend=Backend())
    regions = detector.predict(image)
    assert len(regions) == 1
    assert {issue["validation_issue"] for issue in detector.last_issues} == {
        "out_of_bounds", "degenerate_polygon", "nonfinite_coordinate", "malformed_points"
    }


def test_crop_polygon_preserves_a_rectified_source_region(tmp_path):
    image = tmp_path / "receipt.png"
    output = tmp_path / "crop.png"
    Image.new("RGB", (100, 80), "white").save(image)

    crop_polygon(image, [[10, 10], [50, 14], [48, 34], [8, 30]], output)

    with Image.open(output) as crop:
        assert crop.width >= 39
        assert crop.height >= 20
        assert crop.mode == "RGB"


def test_crop_polygon_expands_and_clips_padding(tmp_path):
    image = tmp_path / "receipt.png"
    output = tmp_path / "crop.png"
    Image.new("RGB", (100, 80), "white").save(image)

    crop_polygon(image, [[1, 10], [41, 10], [41, 30], [1, 30]], output, padding_percent=5)

    with Image.open(output) as crop:
        assert crop.size == (42, 21)


def test_crop_polygon_rejects_invalid_padding(tmp_path):
    image = tmp_path / "receipt.png"
    output = tmp_path / "crop.png"
    Image.new("RGB", (100, 80), "white").save(image)

    try:
        crop_polygon(image, [[10, 10], [40, 10], [40, 30], [10, 30]], output, padding_percent=-1)
    except ValueError as error:
        assert "padding_percent" in str(error)
    else:
        raise AssertionError("Expected negative padding to fail")


def test_phocr_detector_normalizes_optional_scores_without_recognizing(tmp_path):
    model = tmp_path / "detector.onnx"
    model.write_bytes(b"model")
    image = tmp_path / "receipt.png"
    Image.new("RGB", (100, 80), "white").save(image)

    class Output:
        boxes = np.asarray([[[10, 10], [40, 10], [40, 20], [10, 20]]])
        scores = None

    class Backend:
        def __call__(self, pixels):
            assert pixels.shape == (80, 100, 3)
            return Output()

    detector = PHOCRTextDetector(model_path=model, device="cuda:0", backend=Backend())
    regions = detector.predict(image)
    assert regions[0]["polygon"] == [[10.0, 10.0], [40.0, 10.0], [40.0, 20.0], [10.0, 20.0]]
    assert regions[0]["confidence"] is None
    assert detector.device == "cuda:0"
    assert detector.preprocessing["recognizer_invoked"] is False


def test_phocr_detector_records_malformed_geometry(tmp_path):
    model = tmp_path / "detector.onnx"
    model.write_bytes(b"model")
    image = tmp_path / "receipt.png"
    Image.new("RGB", (100, 80), "white").save(image)

    class Output:
        boxes = [None, [[0, 0], [0, 0], [0, 0], [0, 0]]]
        scores = [0.7, 0.8]

    class Backend:
        def __call__(self, pixels):
            return Output()

    detector = PHOCRTextDetector(model_path=model, backend=Backend())
    assert detector.predict(image) == []
    assert [issue["validation_issue"] for issue in detector.last_issues] == [
        "malformed_points", "degenerate_polygon"
    ]


def test_phocr_detector_requires_local_model(tmp_path):
    try:
        PHOCRTextDetector(model_path=tmp_path / "missing.onnx")
    except FileNotFoundError as error:
        assert "--engine phocr-detector" in str(error)
    else:
        raise AssertionError("Expected missing PHOCR model to fail")


def test_phocr_detector_rejects_gpu_backend_that_initialized_on_cpu(tmp_path):
    model = tmp_path / "detector.onnx"
    model.write_bytes(b"model")

    class Session:
        def get_providers(self):
            return ["CPUExecutionProvider"]

    class Backend:
        session = Session()

    try:
        PHOCRTextDetector(model_path=model, device="cuda:0", backend=Backend())
    except RuntimeError as error:
        assert "initialized on" in str(error)
    else:
        raise AssertionError("Expected CPU fallback to be rejected")
