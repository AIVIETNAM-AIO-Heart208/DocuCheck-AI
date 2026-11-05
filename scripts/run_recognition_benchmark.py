#!/usr/bin/env python3
"""Audit recognition crops and run a fixed Tesseract benchmark, train then val.

All images, transcripts, predictions, galleries and evidence stay local. Use a
fresh output directory for each run; existing inference artifacts are not reused.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from docucheck.data.loader import resolve_dataset_root  # noqa: E402
from docucheck.evaluation.metrics import normalize_text  # noqa: E402
from docucheck.ocr.baseline import TesseractBaseline, TSV_CONFIG  # noqa: E402
from docucheck.ocr.inference import load_manifest, run_batch  # noqa: E402
from scripts.evaluate_ocr import main as evaluate_main  # noqa: E402


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit(records, dataset_root, output):
    seen = set()
    issues = []
    hashes = defaultdict(list)
    details = []
    for row in records:
        image_id = row.get("image_id")
        row_issues = []
        if not isinstance(image_id, str) or not image_id or image_id in seen:
            row_issues.append("invalid_or_duplicate_id")
        seen.add(image_id)
        if row.get("split") not in {"official_train", "official_val"}:
            row_issues.append("unexpected_split")
        if not isinstance(row.get("text_raw"), str) or not normalize_text(row["text_raw"]):
            row_issues.append("empty_or_invalid_transcript")
        if row.get("image_status") != "valid" or row.get("text_status") != "present":
            row_issues.append("invalid_manifest_status")
        path = (dataset_root / row["image_path"]).resolve()
        width = height = None
        digest = None
        if not path.is_relative_to(dataset_root):
            row_issues.append("image_outside_dataset_root")
        else:
            try:
                digest = sha256(path)
                with Image.open(path) as image:
                    image.load()
                    width, height = image.size
                if digest != row.get("checksum_sha256"):
                    row_issues.append("checksum_mismatch")
                if (width, height) != (row.get("image_width"), row.get("image_height")):
                    row_issues.append("dimension_mismatch")
                hashes[digest].append((image_id, row.get("split")))
            except (OSError, ValueError) as error:
                row_issues.append(f"unreadable_image:{type(error).__name__}")
        details.append({"image_id": image_id, "split": row.get("split"), "width": width,
                        "height": height, "sha256": digest, "issues": row_issues})
        if row_issues:
            issues.append({"image_id": image_id, "issues": row_issues})
    cross_split = [items for items in hashes.values() if len({s for _, s in items}) > 1]
    valid = [r for r in details if not r["issues"]]
    summary = {
        "record_count": len(records), "unique_ids": len(seen),
        "split_counts": dict(Counter(r.get("split") for r in records)),
        "decoded_and_verified_images": len(valid), "invalid_records": len(issues),
        "issue_counts": dict(Counter(i for row in issues for i in row["issues"])),
        "cross_split_exact_duplicate_groups": len(cross_split),
        "within_dataset_duplicate_groups": sum(len(v) > 1 for v in hashes.values()),
        "image_shape_quantiles": {
            key: np.quantile([r[key] for r in valid], [0, .25, .5, .75, 1]).tolist()
            for key in ("width", "height")
        } if valid else {},
        "line_layout_policy": "Inspect deterministic train-only gallery; no automatic word/line labels inferred.",
        "parent_receipt_kie_mapping": "unverified; not inferred",
        "issues": issues, "cross_split_exact_duplicates": cross_split,
    }
    write_json(output / "audit.json", summary)
    (output / "audited_images.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in details), encoding="utf-8")
    return summary


def train_gallery(records, dataset_root, output):
    train = sorted((r for r in records if r["split"] == "official_train"), key=lambda r: r["image_id"])
    rng = random.Random(42)
    sample = rng.sample(train, min(12, len(train)))
    for ordered in (sorted(train, key=lambda r: (r["image_width"] / r["image_height"], r["image_id"])),
                    sorted(train, key=lambda r: (r["image_height"], r["image_id"]))):
        sample.extend(r for r in ordered[:6] if r not in sample)
    canvas = Image.new("RGB", (1500, ((len(sample) + 2) // 3) * 150), "#eeeeee")
    draw = ImageDraw.Draw(canvas)
    for i, row in enumerate(sample):
        x, y = (i % 3) * 500, (i // 3) * 150
        draw.text((x + 10, y + 4), f"{i+1:02d} | {row['image_width']}x{row['image_height']} | train", fill="black")
        with Image.open(dataset_root / row["image_path"]) as image:
            tile = ImageOps.contain(image.convert("RGB"), (480, 118))
            canvas.paste(tile, (x + 10, y + 26))
    canvas.save(output / "train_layout_audit.png")
    write_json(output / "train_layout_sample.json", [{"index": i + 1, "image_id": r["image_id"]} for i, r in enumerate(sample)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/processed/recognition_manifest.jsonl")
    parser.add_argument("--dataset-root", default=None)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/ocr/week2/goal1")
    parser.add_argument("--tesseract", default=None, help="Executable path, otherwise use PATH")
    parser.add_argument("--tessdata-dir", type=Path, default=ROOT / "outputs/ocr/tessdata_fast")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    if (output / "locked_config.json").exists():
        parser.error("This output directory already contains a locked run; choose a fresh directory.")
    output.mkdir(parents=True, exist_ok=True)
    root = resolve_dataset_root(args.dataset_root)
    records = load_manifest(args.manifest)
    print("Auditing crop images, hashes, dimensions, transcripts and split IDs...", flush=True)
    summary = audit(records, root, output)
    print(json.dumps({k: summary[k] for k in ("record_count", "split_counts", "invalid_records", "cross_split_exact_duplicate_groups")}), flush=True)
    if summary["invalid_records"] or summary["cross_split_exact_duplicate_groups"]:
        raise ValueError("Recognition audit failed; inspect audit.json before inference")
    train_gallery(records, root, output)
    if args.audit_only:
        return 0
    engine = TesseractBaseline(tessdata_dir=args.tessdata_dir, executable=args.tesseract, psm=7)
    source_files = [
        "scripts/run_recognition_benchmark.py", "scripts/evaluate_ocr.py",
        "src/docucheck/ocr/baseline.py", "src/docucheck/ocr/inference.py",
        "src/docucheck/evaluation/metrics.py", "docs/WEEK2_RECOGNITION_PROTOCOL.md",
    ]
    config = {
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": sha256(args.manifest), "audit_sha256": sha256(output / "audit.json"),
        "split_counts": summary["split_counts"], "psm": 7, "oem": 1, "language": "vie",
        "engine_version": engine.engine_version, "model_sha256": engine.model_sha256,
        "model_source": engine.model_source, "executable_sha256": sha256(engine.executable),
        "tsv_config_sha256": sha256(TSV_CONFIG), "image_preprocessing": "none; original crop bytes",
        "device": "cpu", "batch_size": 1, "workers": 1,
        "selection_policy": "Fixed PSM 7 single-line baseline; no validation-based tuning in this run.",
        "historical_validation_exposure": "Repository documentation already reports prior validation PSM 6/7 results; this is a reproducibility run, not a previously unseen holdout.",
        "split_policy": "Official train is diagnostic; official val is final fixed-config evaluation; no rates pooled.",
        "python_version": platform.python_version(), "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in ("Pillow", "numpy", "opencv-python-headless")},
        "source_sha256": {name: sha256(ROOT / name) for name in source_files},
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "argv": sys.argv, "dataset_root": str(root),
    }
    write_json(output / "locked_config.json", config)
    for split in ("official_train", "official_val"):
        run_dir = output / split
        print(f"Running fixed PSM 7: {split}", flush=True)
        runtime = run_batch(records, dataset_root=root, split=split, output_dir=run_dir, engine=engine)
        if runtime["images_failed"]:
            raise RuntimeError(f"{split}: {runtime['images_failed']} inference failures; inspect failures.jsonl")
        result = evaluate_main([
            "--mode", "crop", "--manifest", str(args.manifest.resolve()),
            "--predictions", str(run_dir / "predictions.jsonl"), "--split", split,
            "--output-dir", str(run_dir),
        ])
        if result:
            raise RuntimeError(f"Evaluation failed for {split}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
