#!/usr/bin/env python3
"""Build local standardized MC-OCR manifests and split diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from docucheck.data.preprocessing import prepare_records, write_jsonl  # noqa: E402
from docucheck.data.validation import validate_manifest  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default=None, help="MC-OCR root (default: MC_OCR_ROOT or data/mcocr)")
    parser.add_argument("--output-dir", default="data/processed", help="Local output directory (gitignored)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--invalid-policy", choices=("report", "skip", "fail"), default="report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPOSITORY_ROOT / output_dir
    try:
        records, recognition, report = prepare_records(
            args.dataset_root,
            seed=args.seed,
            validation_fraction=args.validation_fraction,
            invalid_policy="report" if args.invalid_policy == "fail" else args.invalid_policy,
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "validation_report.json"
    report["manifest_validation"] = validate_manifest(records + recognition)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.invalid_policy == "fail" and report["invalid_record_count"]:
        print(f"Found {report['invalid_record_count']} invalid records; report: {report_path}", file=sys.stderr)
        return 2

    write_jsonl(output_dir / "manifest.jsonl", records)
    write_jsonl(output_dir / "recognition_manifest.jsonl", recognition)
    split_summary = {
        "records_by_split": report["records_by_split"],
        "recognition_records_by_split": report["recognition_records_by_split"],
        "source_template_grouping": report["source_template_grouping"],
        "cross_split_duplicate_group_count": report["cross_split_duplicate_group_count"],
        "exact_duplicate_groups": report["exact_duplicate_groups"],
    }
    (output_dir / "split_summary.json").write_text(
        json.dumps(split_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output_dir": "configured local output directory",
        "records": len(records),
        "recognition_records": len(recognition),
        "records_by_split": report["records_by_split"],
        "recognition_records_by_split": report["recognition_records_by_split"],
        "invalid_record_count": report["invalid_record_count"],
        "cross_split_duplicate_group_count": report["cross_split_duplicate_group_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
