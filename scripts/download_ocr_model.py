#!/usr/bin/env python3
"""Fetch the pinned official fast Vietnamese Tesseract model into local outputs."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODEL_REPOSITORY = "tesseract-ocr/tessdata_fast"
MODEL_REVISION = "87416418657359cb625c412a48b6e1d6d41c29bd"
MODEL_SHA256 = "79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1"
MODEL_URL = (
    "https://raw.githubusercontent.com/"
    f"{MODEL_REPOSITORY}/{MODEL_REVISION}/vie.traineddata"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="outputs/ocr/tessdata_fast")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPOSITORY_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "vie.traineddata"
    if target.exists():
        if sha256(target) == MODEL_SHA256:
            print(f"Verified pinned Vietnamese model already exists: sha256={MODEL_SHA256}")
            return 0
        print(f"Refusing to overwrite unverified model file: {target}", file=sys.stderr)
        return 2

    temporary = target.with_suffix(".traineddata.tmp")
    try:
        urllib.request.urlretrieve(MODEL_URL, temporary)
        actual = sha256(temporary)
        if actual != MODEL_SHA256:
            temporary.unlink(missing_ok=True)
            print(f"Downloaded model checksum mismatch: {actual}", file=sys.stderr)
            return 1
        os.replace(temporary, target)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        print(f"Model download failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Downloaded pinned Vietnamese model: sha256={MODEL_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
