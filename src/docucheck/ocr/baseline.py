"""Tesseract 5 Vietnamese OCR adapter returning word polygons."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from docucheck.data.loader import REPOSITORY_ROOT


TSV_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "tesseract_tsv.conf"


def parse_tesseract_tsv(tsv_text: str) -> list[dict[str, Any]]:
    """Parse word-level TSV into recognized text, axis-aligned polygons, and scores."""
    predictions = []
    for line in tsv_text.splitlines()[1:]:
        # Tesseract can emit literal tabs/newlines inside recognized text. Parse
        # the fixed numeric prefix and treat the remainder of each physical row
        # as text so malformed continuation fragments cannot become giant tokens.
        columns = line.split("\t", 11)
        if len(columns) != 12:
            continue
        _, _, _, _, _, _, left_raw, top_raw, width_raw, height_raw, confidence_raw, text = columns
        text = text.strip()
        if not text:
            continue
        try:
            left = float(left_raw)
            top = float(top_raw)
            width = float(width_raw)
            height = float(height_raw)
            raw_confidence = float(confidence_raw)
        except ValueError:
            continue
        if width <= 0 or height <= 0:
            continue
        polygon = [
            [left, top],
            [left + width, top],
            [left + width, top + height],
            [left, top + height],
        ]
        predictions.append(
            {
                "text": text,
                "polygon": polygon,
                "confidence": raw_confidence / 100 if raw_confidence >= 0 else None,
            }
        )
    return predictions


class TesseractBaseline:
    """Use the Tesseract LSTM Vietnamese model with word-level TSV geometry."""

    language = "vie"
    page_segmentation_mode = 6
    ocr_engine_mode = 1
    model_repository = "tesseract-ocr/tessdata_fast"
    model_revision = "87416418657359cb625c412a48b6e1d6d41c29bd"

    def __init__(
        self,
        *,
        tessdata_dir: str | Path = "outputs/ocr/tessdata_fast",
        executable: str | None = None,
        language: str = "vie",
        psm: int = 6,
        oem: int = 1,
    ):
        self.tessdata_dir = Path(tessdata_dir)
        if not self.tessdata_dir.is_absolute():
            self.tessdata_dir = REPOSITORY_ROOT / self.tessdata_dir
        self.tessdata_dir = self.tessdata_dir.resolve()
        self.executable = executable or shutil.which("tesseract")
        self.language = language
        self.page_segmentation_mode = psm
        self.ocr_engine_mode = oem
        self.model_path = self.tessdata_dir / f"{language}.traineddata"
        if not self.executable:
            raise FileNotFoundError("Tesseract 5 executable not found on PATH")
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"OCR language model not found at {self.model_path}; run scripts/download_ocr_model.py"
            )
        self.model_sha256 = self._sha256(self.model_path)
        result = subprocess.run([self.executable, "--version"], capture_output=True, text=True, check=True)
        self.engine_version = result.stdout.splitlines()[0].strip()
        self.model_load_seconds = 0.0

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @property
    def model_names(self) -> dict[str, str]:
        return {"recognition": self.model_path.name}

    @property
    def model_source(self) -> str:
        return f"{self.model_repository}@{self.model_revision}"

    @property
    def device(self) -> str:
        return "cpu"

    def predict(self, image_path: str | Path) -> list[dict[str, Any]]:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, ValueError) as error:
            raise ValueError("Invalid or unreadable image") from error

        with tempfile.TemporaryDirectory(prefix="docucheck-ocr-") as temp_dir:
            output_base = Path(temp_dir) / "page"
            command = [
                self.executable,
                str(path),
                str(output_base),
                "--tessdata-dir",
                str(self.tessdata_dir),
                "-l",
                self.language,
                "--psm",
                str(self.page_segmentation_mode),
                "--oem",
                str(self.ocr_engine_mode),
                str(TSV_CONFIG),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Tesseract exited with status {result.returncode}: {result.stderr.strip()}")
            tsv_path = output_base.with_suffix(".tsv")
            if not tsv_path.is_file():
                raise RuntimeError("Tesseract completed without producing TSV output")
            return parse_tesseract_tsv(tsv_path.read_text(encoding="utf-8", errors="replace"))
