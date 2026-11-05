#!/usr/bin/env python3
"""Compare complete Tesseract, VietOCR, and PaddleOCR crop evaluations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from docucheck.evaluation.comparison import compare_crop_runs, write_comparison  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for engine in ("tesseract", "vietocr", "paddleocr"):
        parser.add_argument(f"--{engine}", required=True, help=f"{engine} evaluation directory")
    parser.add_argument("--output-dir", default="outputs/ocr/engine_comparison")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = {name: Path(getattr(args, name)) for name in ("tesseract", "vietocr", "paddleocr")}
    output = Path(args.output_dir)
    paths = {name: path if path.is_absolute() else REPOSITORY_ROOT / path for name, path in paths.items()}
    output = output if output.is_absolute() else REPOSITORY_ROOT / output
    try:
        summary, details = compare_crop_runs(paths)
        write_comparison(output, summary, details)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"OCR comparison failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
