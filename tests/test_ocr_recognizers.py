import hashlib

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

    engine = VietOCRBaseline(model_path=model, backend=Backend())
    assert engine.predict(image) == [{"text": "CỬA HÀNG", "confidence": 0.9}]
    assert engine.model_sha256 == hashlib.sha256(b"model").hexdigest()


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
