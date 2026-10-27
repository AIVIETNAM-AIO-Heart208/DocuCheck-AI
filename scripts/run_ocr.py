#!/usr/bin/env python3
"""Run the local pretrained OCR baseline over a prepared manifest split."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from docucheck.ocr.inference import load_manifest, run_batch  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/processed/manifest.jsonl")
    parser.add_argument("--dataset-root", default=None, help="MC-OCR root (default: MC_OCR_ROOT or data/mcocr)")
    parser.add_argument("--split", default="internal_dev", help="Manifest split; defaults to the held-out internal development subset")
    parser.add_argument("--output-dir", default="outputs/ocr/tesseract")
    parser.add_argument("--tessdata-dir", default="outputs/ocr/tessdata_fast")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N sorted records (smoke run)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = REPOSITORY_ROOT / manifest_path
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPOSITORY_ROOT / output_dir
    if not manifest_path.is_file():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    try:
        records = load_manifest(manifest_path)
        if not any(record.get("split") == args.split for record in records):
            print(f"No records found for split {args.split!r}", file=sys.stderr)
            return 2
        metadata = run_batch(
            records,
            dataset_root=args.dataset_root,
            split=args.split,
            output_dir=output_dir,
            limit=args.limit,
            tessdata_dir=args.tessdata_dir,
        )
    except Exception as error:
        print(f"OCR run failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps({key: metadata[key] for key in (
        "engine", "engine_version", "model_names", "model_sha256", "device",
        "split", "manifest_record_count", "images_succeeded", "images_failed",
        "mean_successful_image_latency_seconds",
    )}, indent=2))
    return 0 if metadata["images_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
