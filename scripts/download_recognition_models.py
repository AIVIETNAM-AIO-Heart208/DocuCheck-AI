#!/usr/bin/env python3
"""Download optional pretrained OCR models into local outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PHOCR_MODEL_URL = (
    "https://www.modelscope.cn/models/puhuilab/PHOCR/resolve/master/"
    "onnx/PP-OCRv5/det/ch_PP-OCRv5_server_det.onnx"
)
PHOCR_MODEL_SHA256 = "0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad"
DOWNLOAD_TIMEOUT_SECONDS = 30


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine",
        choices=("vietocr", "paddleocr", "paddleocr-detector", "phocr-detector"),
        required=True,
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_verified(url: str, output: Path, expected_sha256: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and _sha256(output) == expected_sha256:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=f".{output.name}.", delete=False) as stream:
            temporary = Path(stream.name)
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        actual_sha256 = _sha256(temporary)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"Checksum mismatch for {output.name}: expected {expected_sha256}, got {actual_sha256}"
            )
        os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _write_provenance(path: Path, *, model_name: str, url: str, sha256: str) -> None:
    path.with_suffix(path.suffix + ".json").write_text(
        json.dumps({"model_name": model_name, "url": url, "sha256": sha256}, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.engine == "vietocr":
            output = REPOSITORY_ROOT / "outputs/ocr/models/vietocr/vgg_transformer.pth"
            output.parent.mkdir(parents=True, exist_ok=True)
            if not output.is_file():
                urllib.request.urlretrieve("https://vocr.vn/data/vietocr/vgg_transformer.pth", output)
            print(output)
        elif args.engine == "paddleocr":
            cache = REPOSITORY_ROOT / "outputs/ocr/models/paddleocr"
            os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache)
            from paddleocr import TextRecognition

            TextRecognition(model_name="latin_PP-OCRv5_mobile_rec", device="cpu")
            print(cache / "official_models/latin_PP-OCRv5_mobile_rec")
        else:
            if args.engine == "phocr-detector":
                output = REPOSITORY_ROOT / "outputs/ocr/models/phocr/official_models/ch_PP-OCRv5_server_det.onnx"
                _download_verified(PHOCR_MODEL_URL, output, PHOCR_MODEL_SHA256)
                _write_provenance(
                    output,
                    model_name="ch_PP-OCRv5_server_det",
                    url=PHOCR_MODEL_URL,
                    sha256=PHOCR_MODEL_SHA256,
                )
                print(output)
                return 0
            cache = REPOSITORY_ROOT / "outputs/ocr/models/paddleocr"
            os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache)
            from paddleocr import TextDetection

            TextDetection(model_name="PP-OCRv6_medium_det", device="cpu", enable_mkldnn=False).close()
            print(cache / "official_models/PP-OCRv6_medium_det")
    except Exception as error:
        print(f"Model setup failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
