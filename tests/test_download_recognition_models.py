import hashlib
import json

from scripts import download_recognition_models as models


def test_verified_model_download_writes_only_model_and_provenance(tmp_path, monkeypatch):
    payload = b"detector model"
    expected = hashlib.sha256(payload).hexdigest()
    output = tmp_path / "models" / "detector.onnx"

    def fake_urlopen(url, timeout):
        assert url == "https://example.invalid/model.onnx"
        assert timeout == 30

        class Response:
            def __enter__(self):
                from io import BytesIO

                return BytesIO(payload)

            def __exit__(self, *args):
                return False

        return Response()

    monkeypatch.setattr(models.urllib.request, "urlopen", fake_urlopen)
    models._download_verified("https://example.invalid/model.onnx", output, expected)
    models._write_provenance(
        output,
        model_name="detector",
        url="https://example.invalid/model.onnx",
        sha256=expected,
    )

    assert output.read_bytes() == payload
    assert json.loads(output.with_suffix(".onnx.json").read_text()) == {
        "model_name": "detector",
        "url": "https://example.invalid/model.onnx",
        "sha256": expected,
    }


def test_verified_model_download_rejects_bad_checksum(tmp_path, monkeypatch):
    output = tmp_path / "detector.onnx"

    monkeypatch.setattr(
        models.urllib.request,
        "urlopen",
        lambda url, timeout: type(
            "Response",
            (),
            {
                "__enter__": lambda self: __import__("io").BytesIO(b"wrong"),
                "__exit__": lambda self, *args: False,
            },
        )(),
    )
    try:
        models._download_verified("https://example.invalid/model.onnx", output, "0" * 64)
    except RuntimeError as error:
        assert "Checksum mismatch" in str(error)
    else:
        raise AssertionError("Expected checksum mismatch")
    assert not output.exists()
