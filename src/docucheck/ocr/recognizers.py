"""Optional recognition-only OCR adapters for prepared text crops."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import time
from pathlib import Path
from typing import Any

from PIL import Image

from docucheck.data.loader import REPOSITORY_ROOT


def _local_path(path: str | Path) -> Path:
    value = Path(path)
    if not value.is_absolute():
        value = REPOSITORY_ROOT / value
    return value.resolve()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    for item in files:
        if path.is_dir():
            digest.update(str(item.relative_to(path)).encode())
        with item.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _image(path: str | Path) -> Image.Image:
    try:
        return Image.open(path).convert("RGB")
    except (OSError, ValueError) as error:
        raise ValueError("Invalid or unreadable image") from error


class VietOCRBaseline:
    engine_name = "VietOCR"
    language = "vi"
    model_name = "vgg_transformer"
    model_source = "https://vocr.vn/data/vietocr/vgg_transformer.pth"
    device = "cpu"
    preprocessing = {"mode": "recognition-only", "output": "whole-crop text"}

    def __init__(
        self,
        *,
        model_path: str | Path = "outputs/ocr/models/vietocr/vgg_transformer.pth",
        backend: Any | None = None,
    ):
        started = time.perf_counter()
        self.model_path = _local_path(model_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"VietOCR model not found at {self.model_path}; run scripts/download_recognition_models.py --engine vietocr"
            )
        if backend is None:
            os.environ.setdefault("TORCH_HOME", str(_local_path("outputs/ocr/models/vietocr/torch_cache")))
            try:
                from vietocr.tool.config import Cfg
                from vietocr.tool.predictor import Predictor
            except ImportError as error:
                raise RuntimeError("VietOCR dependencies are missing; run uv sync --extra vietocr") from error
            config = Cfg.load_config_from_name(self.model_name)
            config["weights"] = str(self.model_path)
            config["device"] = self.device
            config["cnn"]["pretrained"] = False
            config["predictor"]["beamsearch"] = False
            backend = Predictor(config)
        self.backend = backend
        self.engine_version = importlib.metadata.version("vietocr") if backend.__class__.__module__.startswith("vietocr") else "test"
        self.model_names = {"recognition": self.model_name}
        self.model_sha256 = _sha256_path(self.model_path)
        self.model_load_seconds = time.perf_counter() - started

    def predict(self, image_path: str | Path) -> list[dict[str, Any]]:
        with _image(image_path) as image:
            text, confidence = self.backend.predict(image, return_prob=True)
        text = str(text).strip()
        if not text:
            return []
        if hasattr(confidence, "item"):
            confidence = confidence.item()
        return [{"text": text, "confidence": float(confidence) if confidence is not None else None}]


class PaddleOCRBaseline:
    engine_name = "PaddleOCR"
    language = "vi"
    model_name = "latin_PP-OCRv5_mobile_rec"
    model_source = "PaddleOCR official model catalog"
    device = "cpu"
    preprocessing = {"mode": "recognition-only", "output": "whole-crop text"}

    def __init__(
        self,
        *,
        model_dir: str | Path = "outputs/ocr/models/paddleocr/official_models/latin_PP-OCRv5_mobile_rec",
        backend: Any | None = None,
    ):
        started = time.perf_counter()
        self.model_dir = _local_path(model_dir)
        if not self.model_dir.is_dir():
            raise FileNotFoundError(
                f"PaddleOCR model not found at {self.model_dir}; run scripts/download_recognition_models.py --engine paddleocr"
            )
        if backend is None:
            try:
                from paddleocr import TextRecognition
            except ImportError as error:
                raise RuntimeError("PaddleOCR dependencies are missing; run uv sync --extra paddleocr") from error
            backend = TextRecognition(model_name=self.model_name, model_dir=str(self.model_dir), device=self.device)
        self.backend = backend
        self.engine_version = importlib.metadata.version("paddleocr") if backend.__class__.__module__.startswith(("paddleocr", "paddlex")) else "test"
        self.model_names = {"recognition": self.model_name}
        self.model_sha256 = _sha256_path(self.model_dir)
        self.model_load_seconds = time.perf_counter() - started

    def predict(self, image_path: str | Path) -> list[dict[str, Any]]:
        path = Path(image_path)
        with _image(path):
            pass
        results = list(self.backend.predict(str(path), batch_size=1))
        if not results:
            return []
        text = str(results[0]["rec_text"]).strip()
        if not text:
            return []
        confidence = results[0].get("rec_score") if hasattr(results[0], "get") else results[0]["rec_score"]
        return [{"text": text, "confidence": float(confidence) if confidence is not None else None}]
