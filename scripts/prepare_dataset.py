#!/usr/bin/env python3
"""Build local standardized MC-OCR manifests and split diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from docucheck.data.preprocessing import _manifest_statistics, prepare_records, write_jsonl  # noqa: E402
from docucheck.data.validation import validate_manifest  # noqa: E402

ARTIFACTS = ("manifest.jsonl", "recognition_manifest.jsonl", "split_summary.json", "validation_report.json")
SPLIT_SUMMARY_KEYS = (
    "records_by_split", "recognition_records_by_split", "source_template_grouping",
    "cross_split_duplicate_group_count", "exact_duplicate_groups",
)


def _write_json(path: Path, value: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _strict_json(value: str):
    def reject(constant):
        raise ValueError(f"Non-standard JSON constant: {constant}")
    return json.loads(value, parse_constant=reject)


def verify_outputs(output_dir: Path) -> None:
    """Reject missing/mixed/corrupted artifacts, including a stale report."""
    report = _strict_json((output_dir / "validation_report.json").read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("Validation report must be a JSON object")
    hashes = report.get("artifact_sha256", {})
    if not isinstance(hashes, dict) or set(hashes) != set(ARTIFACTS[:-1]):
        raise ValueError("Missing artifact checksums; regenerate this output bundle")
    for name in ARTIFACTS[:-1]:
        if hashes[name] != _sha256(output_dir / name):
            raise ValueError(f"Artifact checksum mismatch: {name}")
    manifests = []
    for name in ARTIFACTS[:2]:
        with (output_dir / name).open(encoding="utf-8") as stream:
            manifests.append([_strict_json(line) for line in stream])
    validation = validate_manifest(manifests[0] + manifests[1])
    if not validation["valid"] or validation != report.get("manifest_validation"):
        raise ValueError("Manifest validation does not match the report")
    summary = _strict_json((output_dir / "split_summary.json").read_text(encoding="utf-8"))
    if summary != {key: report[key] for key in SPLIT_SUMMARY_KEYS}:
        raise ValueError("Split summary does not match the report")
    for key, records in zip(SPLIT_SUMMARY_KEYS[:2], manifests):
        if dict(Counter(r["split"] for r in records)) != report[key]:
            raise ValueError(f"Manifest split counts do not match: {key}")
    stats = _manifest_statistics(*manifests)
    if stats != report.get("output_statistics"):
        raise ValueError("Output statistics do not match the manifests")
    for key in ("exact_duplicate_groups", "records_in_exact_duplicate_groups",
                "cross_split_duplicate_group_count", "cross_split_duplicate_groups",
                "official_validation_duplicate_quarantine_count", "official_validation_duplicate_quarantine_groups",
                "recognition_validation_duplicate_quarantine_count"):
        if report.get(key) != stats[key]:
            raise ValueError(f"Output duplicate statistics do not match: {key}")


def _publish(staging: Path, output_dir: Path) -> None:
    """Back up before replacing; report is the last consistency marker."""
    backup = staging / "backup"
    backup.mkdir()
    for name in ARTIFACTS:
        if (output_dir / name).exists():
            shutil.copyfile(output_dir / name, backup / name)
    replaced = []
    try:
        for name in ARTIFACTS:
            (staging / name).replace(output_dir / name)
            replaced.append(name)
    except OSError:
        for name in reversed(replaced):
            if (backup / name).exists():
                (backup / name).replace(output_dir / name)
            else:
                (output_dir / name).unlink()
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default=None, help="MC-OCR root (default: MC_OCR_ROOT or data/mcocr)")
    parser.add_argument("--output-dir", default="data/processed", help="Local output directory (gitignored)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--invalid-policy", choices=("report", "skip", "fail"), default="report")
    parser.add_argument("--verify-only", action="store_true", help="Verify the existing output bundle without preparing data")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPOSITORY_ROOT / output_dir
    try:
        if args.verify_only:
            verify_outputs(output_dir)
            print("Output bundle verified")
            return 0
        records, recognition, report = prepare_records(
            args.dataset_root,
            seed=args.seed,
            validation_fraction=args.validation_fraction,
            invalid_policy="report" if args.invalid_policy == "fail" else args.invalid_policy,
        )
        # Fail uses report internally to collect every receipt/crop diagnostic.
        report["invalid_policy"] = args.invalid_policy
        report["manifest_validation"] = validate_manifest(records + recognition)
        output_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".prepare-", dir=output_dir) as directory:
            staging = Path(directory)
            if (not report["manifest_validation"]["valid"] or
                    (args.invalid_policy == "fail" and
                     (report["invalid_record_count"] or report["invalid_recognition_record_count"]))):
                failure_path = output_dir / "validation_failure_report.json"
                _write_json(staging / failure_path.name, report)
                (staging / failure_path.name).replace(failure_path)
                print(f"Preparation rejected: receipt errors={report['invalid_record_count']}, "
                      f"recognition errors={report['invalid_recognition_record_count']}, "
                      f"structure={report['manifest_validation']['issue_counts']}; report: {failure_path}", file=sys.stderr)
                return 2
            write_jsonl(staging / "manifest.jsonl", records)
            write_jsonl(staging / "recognition_manifest.jsonl", recognition)
            _write_json(staging / "split_summary.json", {key: report[key] for key in SPLIT_SUMMARY_KEYS})
            report["artifact_sha256"] = {name: _sha256(staging / name) for name in ARTIFACTS[:-1]}
            _write_json(staging / "validation_report.json", report)
            verify_outputs(staging)
            _publish(staging, output_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        return 2
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
