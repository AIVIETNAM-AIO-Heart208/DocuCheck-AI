#!/usr/bin/env python3
"""Download optional pretrained crop-recognition models into local outputs."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("vietocr", "paddleocr"), required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.engine == "vietocr":
            output = REPOSITORY_ROOT / "outputs/ocr/models/vietocr/vgg_transformer.pth"
            output.parent.mkdir(parents=True, exist_ok=True)
            if not output.is_file():
                urllib.request.urlretrieve("https://vocr.vn/data/vietocr/vgg_transformer.pth", output)
            print(output)
        else:
            cache = REPOSITORY_ROOT / "outputs/ocr/models/paddleocr"
            os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache)
            from paddleocr import TextRecognition

            TextRecognition(model_name="latin_PP-OCRv5_mobile_rec", device="cpu")
            print(cache / "official_models/latin_PP-OCRv5_mobile_rec")
    except Exception as error:
        print(f"Model setup failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
