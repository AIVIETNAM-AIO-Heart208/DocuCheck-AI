#!/usr/bin/env python3
"""Audit, lock, run and verify the three full-page Tesseract PSM experiments."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from docucheck.data.loader import resolve_dataset_root, parse_full_page_text_line
from docucheck.evaluation.metrics import evaluate_ocr_records, normalize_text
from docucheck.ocr.baseline import TesseractBaseline, TSV_CONFIG
from docucheck.ocr.inference import load_manifest
from scripts.run_ocr import main as run_main
from scripts.evaluate_ocr import main as evaluate_main

PSMS = (6, 4, 11)
SPLIT = "internal_dev"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit(records, root, expected=231):
    ids = [r.get("image_id") for r in records]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Manifest IDs must be present and unique across splits")
    selected = sorted((r for r in records if r.get("split") == SPLIT), key=lambda r: r["image_id"])
    if len(selected) != expected:
        raise ValueError(f"Expected {expected} internal_dev images, got {len(selected)}")
    images, exclusions = [], []
    for r in selected:
        path = (root / r["image_path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Image outside dataset root")
        digest = sha(path)
        with Image.open(path) as im:
            im.load()
            size = im.size
        if digest != r.get("checksum_sha256") or size != (r["image_width"], r["image_height"]):
            raise ValueError(f"Image identity mismatch: {r['image_id']}")
        if r.get("ocr_ground_truth_status") not in {"available", "partial_transcriptions"} or not r.get("ocr_regions"):
            raise ValueError(f"Missing full-page GT: {r['image_id']}")
        valid = 0
        for index, region in enumerate(r["ocr_regions"]):
            if region.get("source_raw") is not None:
                parsed = parse_full_page_text_line(region["source_raw"], region["source_line"])
                if parsed["source_issue"] or parsed["text_raw"] != region.get("text_raw"):
                    raise ValueError(f"Full-page transcript source mismatch: {r['image_id']}; correct the manifest before benchmarking")
            reason = None
            if region.get("validation_issues") or not region.get("polygon"):
                reason = "invalid_geometry"
            elif region.get("text_raw") is None or not normalize_text(region["text_raw"]):
                reason = "empty_transcription"
            else:
                valid += 1
            if reason:
                exclusions.append({"image_id": r["image_id"], "source_region_index": index,
                                   "reason": reason, "validation_issues": region.get("validation_issues", [])})
        if not valid:
            raise ValueError(f"No evaluable GT: {r['image_id']}")
        images.append({"image_id": r["image_id"], "image_path": r["image_path"], "sha256": digest,
                       "width": size[0], "height": size[1], "valid_regions": valid})
    return {"split": SPLIT, "image_count": len(images), "images": images,
            "evaluated_regions": sum(r["valid_regions"] for r in images), "excluded_regions": exclusions}


def compare_row(psm, metrics, runtime, predictions):
    return {"psm": psm, "images_succeeded": runtime["images_succeeded"],
            "images_failed": runtime["images_failed"],
            "empty_images": sum(not r["predictions"] for r in predictions),
            **{k: metrics[k] for k in ("total_prediction_word_boxes", "unassigned_prediction_word_boxes",
                "unassigned_prediction_word_box_denominator", "unassigned_prediction_word_box_rate",
                "unmatched_ground_truth_regions", "unmatched_ground_truth_region_denominator",
                "unmatched_ground_truth_region_rate", "cer", "wer", "character_errors", "ground_truth_characters",
                "word_errors", "ground_truth_words", "excluded_invalid_geometry_regions", "excluded_empty_transcription_regions")},
            "runtime_seconds": runtime["inference_elapsed_seconds"],
            "mean_seconds_per_image": runtime["mean_successful_image_latency_seconds"]}


def verify(output):
    lock = read(output / "locked_config.json")
    checks = []

    def require(condition, name):
        if not condition:
            raise ValueError(f"Verification failed: {name}")
        checks.append(name)

    require(sha(output / "manifest.jsonl") == lock["manifest_sha256"], "manifest snapshot hash")
    require(sha(lock["manifest_path"]) == lock["manifest_sha256"], "original manifest hash")
    for name, digest in lock["source_sha256"].items():
        require(sha(ROOT / name) == digest, f"current source: {name}")
        require(sha(output / "source_snapshot" / name) == digest, f"snapshot: {name}")
    require(sha(lock["executable"]) == lock["executable_sha256"], "executable hash")
    require(sha(lock["model_path"]) == lock["model_sha256"], "model hash")
    require(sha(output / "audit.json") == lock["audit_sha256"], "audit hash")
    records = load_manifest(output / "manifest.jsonl")
    audited = audit(records, Path(lock["dataset_root"]))
    require(audited == read(output / "audit.json"), "all image bytes, dimensions and GT exclusions")
    expected_ids = {r["image_id"] for r in audited["images"]}
    comparison = []
    for psm in PSMS:
        folder = output / f"psm{psm}"
        predictions = load_manifest(folder / "predictions.jsonl")
        runtime = read(folder / "runtime.json")
        require(len(predictions) == len(expected_ids) and {r["image_id"] for r in predictions} == expected_ids,
                f"PSM {psm}: exact ID coverage")
        require(not load_manifest(folder / "failures.jsonl"), f"PSM {psm}: no failures")
        require(runtime["images_failed"] == 0 and runtime["images_succeeded"] == runtime["manifest_record_count"] == 231,
                f"PSM {psm}: runtime counts")
        for key in ("engine_version", "model_sha256", "python_version", "platform", "workers", "batch_size", "omp_thread_limit"):
            require(runtime[key] == lock[key], f"PSM {psm}: {key}")
        require(runtime["preprocessing"] == {"page_segmentation_mode": psm, "ocr_engine_mode": 1,
                "output": "word-level TSV with axis-aligned polygons"}, f"PSM {psm}: preprocessing")
        require(runtime["language"] == "vie" and runtime["device"] == "cpu", f"PSM {psm}: language/device")
        metrics, images, regions = evaluate_ocr_records(records, predictions, split=SPLIT)
        saved = read(folder / "metrics.json")
        require(all(saved[k] == v for k, v in metrics.items()), f"PSM {psm}: recomputed aggregate metrics")
        require(images == load_manifest(folder / "per_image_metrics.jsonl"), f"PSM {psm}: per-image metrics")
        require(regions == load_manifest(folder / "per_region_alignment.jsonl"), f"PSM {psm}: per-region metrics")
        for key, path in {"manifest": output / "manifest.jsonl", "predictions": folder / "predictions.jsonl",
                          "runtime": folder / "runtime.json"}.items():
            require(saved["input_sha256"][key] == sha(path), f"PSM {psm}: {key} provenance")
        require(metrics["evaluated_ground_truth_regions"] == audited["evaluated_regions"], f"PSM {psm}: GT coverage")
        comparison.append(compare_row(psm, metrics, runtime, predictions))
    if (output / "comparison.json").exists():
        require(comparison == read(output / "comparison.json"), "comparison matches verified runs")
    save(output / "verification.json", {"status": "passed", "checks": checks, "check_count": len(checks),
         "scope": "Technical verification only; visual review is separate.", "verified_at_utc": datetime.now(timezone.utc).isoformat()})
    return comparison


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/processed/manifest.jsonl")
    parser.add_argument("--dataset-root", default=None)
    parser.add_argument("--tesseract", default=None)
    parser.add_argument("--tessdata-dir", type=Path, default=ROOT / "outputs/ocr/tessdata_fast")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    if args.verify_only:
        verify(output)
        print("Verification passed")
        return 0
    if output.exists() and any(output.iterdir()):
        parser.error("Choose a new, empty output directory; previous evidence must not be overwritten")
    root = resolve_dataset_root(args.dataset_root)
    records = load_manifest(args.manifest)
    audited = audit(records, root)
    os.environ["OMP_THREAD_LIMIT"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    engine = TesseractBaseline(executable=args.tesseract, tessdata_dir=args.tessdata_dir, psm=6)
    output.mkdir(parents=True, exist_ok=True)
    save(output / "audit.json", audited)
    shutil.copyfile(args.manifest, output / "manifest.jsonl")
    sources = sorted([str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "src/docucheck").rglob("*.py")]
        + ["scripts/run_psm_comparison.py", "scripts/run_ocr.py", "scripts/evaluate_ocr.py",
           "configs/tesseract_tsv.conf", "docs/PSM_CORRECTED_PROTOCOL.md", "pyproject.toml", "uv.lock"])
    for name in sources:
        dest = output / "source_snapshot" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    commands = {}
    for psm in PSMS:
        folder = output / f"psm{psm}"
        commands[str(psm)] = {
            "inference": ["--manifest", str(output / "manifest.jsonl"), "--dataset-root", str(root),
                "--split", SPLIT, "--psm", str(psm), "--tesseract", str(engine.executable),
                "--tessdata-dir", str(engine.tessdata_dir), "--output-dir", str(folder)],
            "evaluation": ["--manifest", str(output / "manifest.jsonl"), "--predictions", str(folder / "predictions.jsonl"),
                "--mode", "full-page", "--split", SPLIT, "--output-dir", str(folder)]}
    lock = {"locked_at_utc": datetime.now(timezone.utc).isoformat(), "argv": sys.argv,
        "psm_order": list(PSMS), "split": SPLIT, "image_count": 231, "oem": 1,
        "image_preprocessing": "none; original image bytes", "manifest_path": str(args.manifest.resolve()),
        "manifest_sha256": sha(args.manifest), "audit_sha256": sha(output / "audit.json"),
        "dataset_root": str(root), "executable": str(Path(engine.executable).resolve()),
        "executable_sha256": sha(engine.executable), "engine_version": engine.engine_version,
        "model_path": str(engine.model_path), "model_sha256": engine.model_sha256, "model_source": engine.model_source,
        "workers": 1, "batch_size": 1, "omp_thread_limit": "1", "omp_num_threads": "1",
        "python_version": platform.python_version(), "platform": platform.platform(), "cpu_count_logical": os.cpu_count(),
        "packages": {n: importlib.metadata.version(n) for n in ("Pillow", "numpy", "opencv-python-headless")},
        "source_sha256": {name: sha(ROOT / name) for name in sources}, "commands": commands,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "timing_limit": "Single sequential run per PSM; wall latency includes process startup; no statistical speed ranking."}
    save(output / "locked_config.json", lock)
    (output / "tesseract_version.txt").write_text(subprocess.check_output([engine.executable, "--version"], text=True), encoding="utf-8")
    for psm in PSMS:
        print(f"Running PSM {psm}: 231 images, one thread", flush=True)
        if run_main(commands[str(psm)]["inference"]):
            raise RuntimeError(f"PSM {psm} inference failed; retain artifacts and inspect failures")
        if evaluate_main(commands[str(psm)]["evaluation"]):
            raise RuntimeError(f"PSM {psm} evaluation failed")
    comparison = verify(output)
    save(output / "comparison.json", comparison)
    with (output / "comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    print(json.dumps(comparison, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
