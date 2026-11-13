import hashlib

import pytest
from PIL import Image

from docucheck.ocr.recognizers import PaddleOCRBaseline, VietOCRBaseline


def test_vietocr_adapter_returns_whole_crop_text(tmp_path):
    model = tmp_path / "model.pth"
    model.write_bytes(b"model")
    image = tmp_path / "crop.jpg"
    Image.new("RGB", (20, 10), "white").save(image)

    class Backend:
        def predict(self, image, return_prob=False):
            assert return_prob is True
            return " CỬA HÀNG ", 0.9

    engine = VietOCRBaseline(model_path=model, backend=Backend(), device="cuda:0")
    assert engine.predict(image) == [{"text": "CỬA HÀNG", "confidence": 0.9}]
    assert engine.device == "cuda:0"
    assert engine.model_sha256 == hashlib.sha256(b"model").hexdigest()
    assert engine.preprocessing["experiment"] == "E0"


def test_vietocr_scale_variants_resize_in_memory(tmp_path):
    model = tmp_path / "model.pth"
    model.write_bytes(b"model")
    image = tmp_path / "crop.jpg"
    Image.new("RGB", (20, 10), "white").save(image)
    seen_sizes = []

    class Backend:
        def predict(self, image, return_prob=False):
            seen_sizes.append(image.size)
            return "MẪU", 0.9

    for scale, expected_size, experiment in ((1, (20, 10), "E0"), (2, (40, 20), "E1"), (4, (80, 40), "E2")):
        engine = VietOCRBaseline(model_path=model, backend=Backend(), scale_factor=scale)
        assert engine.predict(image) == [{"text": "MẪU", "confidence": 0.9}]
        assert engine.preprocessing["experiment"] == experiment
        assert engine.preprocessing["resampling"] == ("none" if scale == 1 else "LANCZOS")
        assert seen_sizes[-1] == expected_size

    with Image.open(image) as source:
        assert source.size == (20, 10)


def test_vietocr_rejects_unsupported_scale(tmp_path):
    model = tmp_path / "model.pth"
    model.write_bytes(b"model")
    with pytest.raises(ValueError, match="scale_factor must be 1, 2, or 4"):
        VietOCRBaseline(model_path=model, scale_factor=3)


def test_paddleocr_adapter_returns_recognition_only_result(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "inference.json").write_text("{}", encoding="utf-8")
    image = tmp_path / "crop.jpg"
    Image.new("RGB", (20, 10), "white").save(image)

    class Backend:
        def predict(self, image_path, batch_size=1):
            assert batch_size == 1
            return [{"rec_text": "TỔNG TIỀN", "rec_score": 0.8}]

    engine = PaddleOCRBaseline(model_dir=model, backend=Backend())
    assert engine.predict(image) == [{"text": "TỔNG TIỀN", "confidence": 0.8}]
    assert engine.preprocessing["mode"] == "recognition-only"


def test_optional_adapters_require_local_models(tmp_path):
    try:
        VietOCRBaseline(model_path=tmp_path / "missing.pth")
    except FileNotFoundError as error:
        assert "download_recognition_models.py" in str(error)
    else:
        raise AssertionError("Expected missing VietOCR model to fail")

    try:
        PaddleOCRBaseline(model_dir=tmp_path / "missing")
    except FileNotFoundError as error:
        assert "download_recognition_models.py" in str(error)
    else:
        raise AssertionError("Expected missing PaddleOCR model to fail")
