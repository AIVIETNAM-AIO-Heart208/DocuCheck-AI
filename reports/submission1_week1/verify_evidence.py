"""Report-only, read-only verification; writes aggregate evidence and figures here.

Run from the repository root with the existing Python 3.12 environment.
Does not prepare data, run OCR, execute notebooks, or modify original artifacts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from collections import Counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["MPLCONFIGDIR"] = str(HERE / "qa" / "mplconfig")

import numpy as np
from PIL import Image
from docucheck.data.eda import collect_image_features, select_annotation_audit_sample, summarize_field_missingness
from docucheck.data.loader import load_kie_records
from docucheck.data.validation import validate_manifest
from docucheck.data.splitting import find_cross_split_duplicate_groups
from docucheck.evaluation.metrics import evaluate_ocr_records
from scripts.prepare_dataset import verify_outputs


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main():
    evidence = HERE / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (HERE / "qa").mkdir(exist_ok=True)
    receipts = read_jsonl("data/processed/manifest.jsonl")
    crops = read_jsonl("data/processed/recognition_manifest.jsonl")
    train = [r for r in receipts if r["source_split"] == "train"]
    raw = load_kie_records(ROOT / "data/mcocr")
    raw_by_name = {r["image_id"]: r for r in raw}
    preserved = 0
    for row in train:
        source = raw_by_name[row["source_image_name"]]
        assert len(row["regions"]) == len(source["regions"])
        for normalized, original in zip(row["regions"], source["regions"]):
            for key in ("text_raw", "label_raw", "polygon"):
                assert normalized[key] == original[key]
            preserved += 1

    validated = validate_manifest(receipts + crops)
    assert validated["valid"]
    image_checks = Counter()
    for row in receipts + crops:
        path = ROOT / "data/mcocr" / row["image_path"]
        assert digest(path) == row["checksum_sha256"]
        with Image.open(path) as image:
            image.load()
            assert image.size == (row["image_width"], row["image_height"])
        image_checks["decoded_and_hash_matched"] += 1

    features = collect_image_features(train, ROOT / "data/mcocr")
    sample = read_jsonl("outputs/audit/week1/annotation_sample.jsonl")
    reconstructed = select_annotation_audit_sample(train, features, size=40, seed=42)
    assert [r["image_id"] for r in sample] == [r["image_id"] for r in reconstructed]
    assert [r["selection_reasons"] for r in sample] == [r["selection_reasons"] for r in reconstructed]
    with (ROOT / "outputs/audit/week1/annotation_review.csv").open(encoding="utf-8-sig", newline="") as stream:
        reviews = list(csv.DictReader(stream))
    assert [r["image_id"] for r in reviews] == [r["image_id"] for r in sample]
    review_flags = {flag: dict(Counter(r[flag] for r in reviews)) for flag in
                    ("wrong_label", "wrong_geometry", "missing_field_annotation", "unreadable_text", "uncertain")}

    predictions = read_jsonl("outputs/ocr/tesseract_internal_dev/predictions.jsonl")
    recorded = read_json("outputs/ocr/evaluation/metrics.json")
    recomputed, image_metrics, region_metrics = evaluate_ocr_records(receipts, predictions, split="internal_dev")
    assert all(recorded[k] == v for k, v in recomputed.items())
    assert image_metrics == read_jsonl("outputs/ocr/evaluation/per_image_metrics.jsonl")
    assert region_metrics == read_jsonl("outputs/ocr/evaluation/per_region_alignment.jsonl")
    runtime = read_json("outputs/ocr/tesseract_internal_dev/runtime.json")
    assert digest(ROOT / "outputs/ocr/tessdata_fast/vie.traineddata") == runtime["model_sha256"]
    assert len(predictions) == runtime["images_succeeded"] == 231
    assert all(r["status"] == "ok" for r in predictions)
    assert not read_jsonl("outputs/ocr/tesseract_internal_dev/failures.jsonl")

    bundles = {}
    for directory in ("data/processed", "outputs/audit/goal2_hardening_20261028/run_a", "outputs/audit/goal2_hardening_20261028/run_b"):
        try:
            verify_outputs(ROOT / directory)
            bundles[directory] = {"exit_code": 0, "result": "verified"}
        except (ValueError, OSError, KeyError, TypeError) as error:
            bundles[directory] = {"exit_code": 2, "result": str(error)}
    repeated = {}
    for name in ("manifest.jsonl", "recognition_manifest.jsonl", "split_summary.json", "validation_report.json"):
        a = ROOT / "outputs/audit/goal2_hardening_20261028/run_a" / name
        b = ROOT / "outputs/audit/goal2_hardening_20261028/run_b" / name
        repeated[name] = {"sha256_a": digest(a), "sha256_b": digest(b), "bytes_equal": a.read_bytes() == b.read_bytes()}
        assert repeated[name]["bytes_equal"]
    original_comparison = {}
    for name in ("manifest.jsonl", "recognition_manifest.jsonl", "split_summary.json"):
        old = ROOT / "data/processed" / name
        new = ROOT / "outputs/audit/goal2_hardening_20261028/run_a" / name
        original_comparison[name] = {"bytes_equal": old.read_bytes() == new.read_bytes()}
        if name.endswith(".json"):
            original_comparison[name]["json_equal"] = json.loads(old.read_text(encoding="utf-8")) == json.loads(new.read_text(encoding="utf-8"))

    notebooks = {}
    for path in sorted((ROOT / "notebooks").glob("0*.ipynb")):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
        for cell in cells:
            # Inspect the actual analysis code, including uncommitted local edits.
            compile("".join(cell["source"]), path.name, "exec")
        notebooks[path.relative_to(ROOT).as_posix()] = {
            "code_cells": len(cells), "cells_with_execution_count": sum(c.get("execution_count") is not None for c in cells),
            "error_outputs": sum(o.get("output_type") == "error" for c in cells for o in c.get("outputs", [])),
            "executed_during_report_task": False,
        }
    near = read_jsonl("outputs/audit/week1/near_duplicate_candidates.jsonl")
    near_summary = read_json("outputs/audit/week1/near_duplicate_summary.json")
    assert len(near) == near_summary["candidate_count"] == 36
    assert dict(Counter(r["split_pair"] for r in near)) == near_summary["candidates_by_split_pair"]

    stats = {}
    for column in ("width", "height", "aspect_ratio", "brightness_mean", "contrast_std", "laplacian_variance"):
        stats[column] = {"min": float(features[column].min()), "median": float(features[column].median()), "max": float(features[column].max())}
    regions_per_image = [len(r["regions"]) for r in train]
    summary = {
        "verification_date_local": "2026-10-28", "timezone": "Asia/Saigon",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": platform.python_version(), "platform": platform.platform(),
        "receipt_records": len(receipts), "train_records": len(train), "recognition_records": len(crops),
        "unique_receipt_contents": len({r["checksum_sha256"] for r in receipts}),
        "unique_train_contents": len({r["checksum_sha256"] for r in train}),
        "records_by_split": dict(Counter(r["split"] for r in receipts)),
        "recognition_records_by_split": dict(Counter(r["split"] for r in crops)),
        "kie_regions": sum(regions_per_image), "kie_source_regions_preserved": preserved,
        "ocr_regions": sum(len(r.get("ocr_regions", [])) for r in train),
        "ocr_gt_status": dict(Counter(r["ocr_ground_truth_status"] for r in train)),
        "label_regions": dict(Counter(g["label_raw"] for r in train for g in r["regions"])),
        "train_exact_duplicate_groups": sum(n > 1 for n in Counter(r["checksum_sha256"] for r in train).values()),
        "train_records_in_exact_duplicate_groups": sum(n for n in Counter(r["checksum_sha256"] for r in train).values() if n > 1),
        "train_images_with_all_four_fields": sum(len({g["canonical_field"] for g in r["regions"] if g.get("canonical_field")}) == 4 for r in train),
        "field_missingness": summarize_field_missingness(receipts),
        "kie_regions_per_image": {"min": min(regions_per_image), "q1": float(np.quantile(regions_per_image,.25)), "median": float(np.median(regions_per_image)), "q3": float(np.quantile(regions_per_image,.75)), "max": max(regions_per_image), "mean": float(np.mean(regions_per_image))},
        "image_statistics_train": stats, "orientation": dict(Counter(features["orientation"])),
        "geometry": {key: {"regions": sum(bool(g.get("validation_issues")) for r in train for g in r.get(key, [])), "images": sum(any(g.get("validation_issues") for g in r.get(key, [])) for r in train), "issue_counts": dict(Counter(i for r in train for g in r.get(key, []) for i in g.get("validation_issues", [])))} for key in ("regions", "ocr_regions")},
        "structural_validation": validated, "images": dict(image_checks),
        "active_cross_split_exact_duplicate_groups": len(find_cross_split_duplicate_groups(receipts + crops)),
        "review_status": dict(Counter(r["review_status"] for r in reviews)),
        "review_correctness": dict(Counter(r["annotation_correctness"] for r in reviews)),
        "review_flags": review_flags, "sample_reconstruction_matches": True,
        "near_duplicate_artifact_counts_match": True, "near_duplicate_phash_recomputed": False,
        "near_duplicate_summary": near_summary,
        "ocr_runtime_recorded": runtime, "ocr_word_boxes": sum(len(r["predictions"]) for r in predictions),
        "ocr_metrics_recomputed": recomputed, "ocr_detail_artifacts_match": True,
        "ocr_inference_rerun": False, "bundle_verification": bundles,
        "existing_repeat_bundles": repeated, "preparation_rerun": False, "notebooks": notebooks,
        "original_processed_comparison": original_comparison,
    }
    write_json(evidence / "verified_summary.json", summary)
    paths = set()
    for directory in ("docs", "configs", "src", "scripts", "tests", "notebooks", ".github"):
        paths.update(p for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".yaml", ".yml", ".conf", ".ipynb"))
    paths.update(ROOT / p for p in ("README.md", "pyproject.toml", "uv.lock"))
    for directory in ("data/processed", "outputs/ocr/evaluation", "outputs/ocr/tesseract_internal_dev", "outputs/audit/week1", "outputs/audit/goal2_hardening_20261028", "outputs/audit/verification"):
        paths.update(p for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in (".json", ".jsonl", ".csv", ".py"))
    with (evidence / "artifact_manifest.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path", "bytes", "sha256", "git_tracked", "distribution"])
        for path in sorted(paths):
            relative = path.relative_to(ROOT).as_posix()
            tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", relative], cwd=ROOT, capture_output=True).returncode == 0
            writer.writerow([relative, path.stat().st_size, digest(path), tracked, "source" if tracked else "private_local_do_not_publish"])
    # Only aggregated distributions are exported; no receipt text or images.
    make_figures(features, summary, image_metrics)
    print(json.dumps({k: summary[k] for k in ("commit", "receipt_records", "kie_regions", "ocr_word_boxes", "bundle_verification", "review_correctness")}, indent=2))


def make_figures(features, summary, image_metrics):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.spines.top": False, "axes.spines.right": False, "axes.labelcolor": "#152f46", "text.color": "#152f46", "savefig.facecolor": "white"})
    directory = HERE / "figures"
    directory.mkdir(exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(9, 5.7), layout="constrained")
    for axis, column, label in zip(axes.flat, ("aspect_ratio", "brightness_mean", "contrast_std", "laplacian_variance"), ("Tỷ lệ rộng / cao", "Độ sáng trung bình\n(mức xám 0–255)", "Độ tương phản\n(độ lệch chuẩn mức xám)", "Phương sai Laplacian (mức xám²)")):
        axis.hist(features[column], bins=30, color="#217e87", edgecolor="white", linewidth=.5)
        axis.set(xlabel=label, ylabel="Số ảnh train")
        axis.grid(axis="y", alpha=.15)
    fig.savefig(directory / "eda_distributions.pdf")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), layout="constrained")
    for axis, key, label in zip(axes, ("cer", "wer"), ("CER từng ảnh (tỷ số)", "WER từng ảnh (tỷ số)")):
        values = [r[key] for r in image_metrics if r[key] is not None]
        axis.hist(values, bins=25, color="#217e87", edgecolor="white", linewidth=.5)
        axis.set(xlabel=label, ylabel="Số ảnh dev nội bộ")
        axis.grid(axis="y", alpha=.15)
    fig.savefig(directory / "ocr_error_distribution.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
