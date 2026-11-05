#!/usr/bin/env python3
"""Correct full-page transcript boundaries in a separate manifest and reuse locked OCR."""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from docucheck.data.loader import parse_full_page_text_line
from docucheck.data.validation import text_status
from docucheck.data.preprocessing import write_jsonl
from docucheck.evaluation.metrics import evaluate_ocr_records
from scripts.evaluate_ocr import main as evaluate_main
from scripts.run_psm_comparison import PSMS, SPLIT, audit, compare_row, load_manifest, read, save, sha


def corrected_records(original, root):
    selected = sorted((r for r in original if r.get("split") == SPLIT), key=lambda r: r["image_id"])
    corrected, source_files = [], {}
    for before in selected:
        r = copy.deepcopy(before)
        source = root / "kie_data/kie_data/boxes_and_transcripts" / (Path(r["source_image_name"]).stem + ".tsv")
        lines = source.read_text(encoding="utf-8-sig").splitlines()
        source_files[str(source)] = sha(source)
        for region in r["ocr_regions"]:
            raw = lines[region["source_line"] - 1]
            if raw != region["source_raw"]:
                raise ValueError("Original sidecar differs from preserved manifest source row")
            parsed = parse_full_page_text_line(raw, region["source_line"])
            if parsed["source_issue"] or parsed["polygon"] != region["polygon"]:
                raise ValueError("Unexpected source schema or polygon change")
            region.update(text_raw=parsed["text_raw"], text_status=text_status(parsed["text_raw"]),
                          source_category=parsed["source_category"])
        r["ocr_ground_truth_status"] = (
            "no_usable_transcriptions" if not any(x["text_status"] == "present" for x in r["ocr_regions"]) else
            "partial_transcriptions" if any(x["text_status"] != "present" for x in r["ocr_regions"]) else "available")
        corrected.append(r)
    return corrected, source_files


def comparison_row(psm, metrics, runtime, predictions):
    return {**compare_row(psm, metrics, runtime, predictions),
            **{f"geometry_{k}": v for k, v in metrics["geometry_coverage"].items()}}


def verify(output):
    lock = read(output / "locked_config.json")
    source_run = Path(lock["source_run"])
    checks = []

    def require(condition, label):
        if not condition:
            raise ValueError(f"Verification failed: {label}")
        checks.append(label)

    for name, digest in lock["evaluation_source_sha256"].items():
        require(sha(ROOT / name) == digest, f"evaluation source: {name}")
        require(sha(output / "source_snapshot" / name) == digest, f"evaluation snapshot: {name}")
    require(sha(source_run / "locked_config.json") == lock["inference_lock_sha256"], "original inference lock")
    require(sha(output / "inference_locked_config.json") == lock["inference_lock_sha256"], "copied inference lock")
    inference = read(output / "inference_locked_config.json")
    for name, digest in inference["source_sha256"].items():
        require(sha(source_run / "source_snapshot" / name) == digest, f"historical inference source: {name}")
        require(sha(output / "inference_source_snapshot" / name) == digest, f"copied inference source: {name}")
    require(sha(inference["executable"]) == inference["executable_sha256"], "inference executable identity")
    require(sha(inference["model_path"]) == inference["model_sha256"], "inference model identity")
    require(sha(source_run / "manifest.jsonl") == lock["original_manifest_sha256"], "original manifest preserved")
    require(sha(inference["manifest_path"]) == lock["original_manifest_sha256"], "data/processed manifest preserved")
    require(sha(output / "original_manifest.jsonl") == lock["original_manifest_sha256"], "original manifest copy")
    records, sources = corrected_records(load_manifest(output / "original_manifest.jsonl"), Path(lock["dataset_root"]))
    require(sources == lock["sidecar_sha256"], "all original sidecar hashes")
    require(records == load_manifest(output / "manifest.jsonl"), "corrected manifest exactly derived from source")
    require(sha(output / "manifest.jsonl") == lock["manifest_sha256"], "corrected manifest hash")
    audited = audit(records, Path(lock["dataset_root"]))
    require(audited == read(output / "audit.json"), "231 image identities and exclusion audit")
    require(audited["evaluated_regions"] == 4265, "nonempty valid source transcript population")
    comparison = []
    for psm in PSMS:
        sub = output / f"psm{psm}"
        for name in ("predictions.jsonl", "failures.jsonl", "runtime.json"):
            digest = lock["inference_artifact_sha256"][f"psm{psm}/{name}"]
            require(sha(sub / name) == sha(source_run / f"psm{psm}" / name) == digest,
                    f"PSM {psm}: unchanged inference {name}")
        predictions = load_manifest(sub / "predictions.jsonl")
        require(len(predictions) == 231 and {r["image_id"] for r in predictions} == {r["image_id"] for r in records},
                f"PSM {psm}: exact ID coverage")
        runtime = read(sub / "runtime.json")
        require(runtime["images_failed"] == 0 and runtime["images_succeeded"] == 231 and not load_manifest(sub / "failures.jsonl"),
                f"PSM {psm}: all successful")
        require(runtime["preprocessing"]["page_segmentation_mode"] == psm and runtime["preprocessing"]["ocr_engine_mode"] == 1,
                f"PSM {psm}: PSM/OEM")
        for key in ("engine_version", "model_sha256", "python_version", "platform", "workers", "batch_size", "omp_thread_limit"):
            require(runtime[key] == inference[key], f"PSM {psm}: inference {key}")
        metrics, images, regions = evaluate_ocr_records(records, predictions, split=SPLIT)
        saved = read(sub / "metrics.json")
        require(all(saved[k] == v for k, v in metrics.items()), f"PSM {psm}: aggregate recalculation")
        require(images == load_manifest(sub / "per_image_metrics.jsonl"), f"PSM {psm}: per-image recalculation")
        require(regions == load_manifest(sub / "per_region_alignment.jsonl"), f"PSM {psm}: per-region recalculation")
        for key, path in {"manifest": output / "manifest.jsonl", "predictions": sub / "predictions.jsonl", "runtime": sub / "runtime.json"}.items():
            require(saved["input_sha256"][key] == sha(path), f"PSM {psm}: {key} evaluation provenance")
        old = read(source_run / f"psm{psm}" / "metrics.json")
        geometry = metrics["geometry_coverage"]
        require(geometry["valid_regions"] == old["evaluated_ground_truth_regions"] == 8304 and
                geometry["unmatched_regions"] == old["unmatched_ground_truth_regions"] and
                geometry["unassigned_word_boxes"] == old["unassigned_prediction_word_boxes"],
                f"PSM {psm}: geometry coverage agrees with pre-correction geometry")
        require(metrics["excluded_empty_transcription_regions"] == 4039 and metrics["excluded_invalid_geometry_regions"] == 104,
                f"PSM {psm}: disjoint exclusion counts")
        comparison.append(comparison_row(psm, metrics, runtime, predictions))
    if (output / "comparison.json").exists():
        require(read(output / "comparison.json") == comparison, "comparison matches verified metrics")
    save(output / "verification.json", {"status": "passed", "check_count": len(checks), "checks": checks,
         "scope": "Corrected source provenance, identities, coverage and arithmetic; visual review remains separate."})
    return comparison


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    if args.verify_only:
        verify(output)
        print("Corrected comparison verification passed")
        return 0
    if args.source_run is None:
        parser.error("--source-run is required for re-evaluation")
    if output.exists() and any(output.iterdir()):
        parser.error("Choose a new empty directory; preserve previous artifacts")
    source = args.source_run.resolve()
    old_lock = read(source / "locked_config.json")
    root = Path(old_lock["dataset_root"])
    records, sidecars = corrected_records(load_manifest(source / "manifest.jsonl"), root)
    audited = audit(records, root)
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "manifest.jsonl", records)
    save(output / "audit.json", audited)
    shutil.copyfile(source / "manifest.jsonl", output / "original_manifest.jsonl")
    shutil.copyfile(source / "locked_config.json", output / "inference_locked_config.json")
    shutil.copytree(source / "source_snapshot", output / "inference_source_snapshot")
    source_names = sorted([p.relative_to(ROOT).as_posix() for p in (ROOT / "src/docucheck").rglob("*.py")] +
        ["scripts/reevaluate_psm_comparison.py", "scripts/run_psm_comparison.py", "scripts/evaluate_ocr.py",
         "scripts/verify_psm_evidence.py", "scripts/review_psm_comparison.py", "docs/PSM_CORRECTED_PROTOCOL.md"])
    for name in source_names:
        dest = output / "source_snapshot" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    artifacts = {}
    for psm in PSMS:
        (output / f"psm{psm}").mkdir()
        for name in ("predictions.jsonl", "runtime.json", "failures.jsonl"):
            relative = f"psm{psm}/{name}"
            shutil.copyfile(source / relative, output / relative)
            artifacts[relative] = sha(source / relative)
    lock = {"protocol_revision": 2, "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "authorization": "Transcript parser correction and separate evaluation manifest approved; reuse unchanged image predictions.",
        "argv": sys.argv, "source_run": str(source), "dataset_root": str(root),
        "inference_lock_sha256": sha(source / "locked_config.json"),
        "original_manifest_sha256": sha(source / "manifest.jsonl"), "manifest_sha256": sha(output / "manifest.jsonl"),
        "evaluation_source_sha256": {n: sha(ROOT / n) for n in source_names}, "sidecar_sha256": sidecars,
        "inference_artifact_sha256": artifacts, "image_count": 231,
        "changed_manifest_fields": ["ocr_regions.text_raw", "ocr_regions.text_status", "ocr_regions.source_category", "ocr_ground_truth_status"],
        "image_ids_splits_paths_polygons": "preserved exactly; only internal_dev records copied to evaluation manifest"}
    save(output / "locked_config.json", lock)
    for psm in PSMS:
        sub = output / f"psm{psm}"
        if evaluate_main(["--manifest", str(output / "manifest.jsonl"), "--predictions", str(sub / "predictions.jsonl"),
                          "--split", SPLIT, "--mode", "full-page", "--output-dir", str(sub)]):
            raise RuntimeError(f"Evaluation failed: PSM {psm}")
    comparison = verify(output)
    save(output / "comparison.json", comparison)
    import csv
    with (output / "comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    print(json.dumps(comparison, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
