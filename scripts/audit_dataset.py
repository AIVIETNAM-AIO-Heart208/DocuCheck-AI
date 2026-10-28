#!/usr/bin/env python3
"""Create local-only near-duplicate candidates and a stratified annotation review pack."""

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from docucheck.data.duplicates import audit_near_duplicates
from docucheck.data.eda import collect_image_features, select_annotation_audit_sample, summarize_field_missingness
from docucheck.data.loader import resolve_dataset_root
from docucheck.data.preprocessing import write_jsonl
from docucheck.data.validation import validate_manifest


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/processed/manifest.jsonl")
    parser.add_argument("--dataset-root", default=None)
    parser.add_argument("--output-dir", default="outputs/audit/week1")
    parser.add_argument("--mode", choices=("all", "near-duplicates", "annotations"), default="all")
    parser.add_argument("--threshold", type=int, default=6, help="Maximum 63-bit pHash Hamming distance")
    parser.add_argument("--sample-size", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    output = REPOSITORY_ROOT / args.output_dir
    try:
        if not 0 <= args.threshold <= 63 or args.sample_size <= 0:
            raise ValueError("threshold must be 0..63 and sample-size must be positive")
        manifest = REPOSITORY_ROOT / args.manifest
        records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not validate_manifest(records)["valid"]:
            raise ValueError("Manifest validation failed; regenerate or inspect it before auditing")
        if (output / "annotation_review.csv").exists() and args.mode in {"all", "annotations"}:
            raise ValueError("Review template already exists; choose a new output directory to preserve reviewer work")
        root = resolve_dataset_root(args.dataset_root)
        output.mkdir(parents=True, exist_ok=True)
        summary = {"seed": args.seed, "human_review_status": "not_performed"}
        if args.mode in {"all", "near-duplicates"}:
            candidates, near_summary, failures = audit_near_duplicates(records, root, threshold=args.threshold)
            write_jsonl(output / "near_duplicate_candidates.jsonl", candidates)
            write_jsonl(output / "near_duplicate_failures.jsonl", failures)
            (output / "near_duplicate_summary.json").write_text(json.dumps(near_summary, indent=2) + "\n", encoding="utf-8")
            page = ["<meta charset='utf-8'><title>Local near-duplicate review</title>",
                    "<h1>Candidate pairs — not confirmed duplicates</h1><p>Similar layout does not prove the same transaction.</p>"]
            for candidate in candidates:
                page.append(f"<h2>Distance {candidate['hamming_distance']}; {html.escape(candidate['split_pair'])}</h2>")
                for side in ("left", "right"):
                    relative = Path(os.path.relpath(root / candidate[f"{side}_image_path"], output)).as_posix()
                    from urllib.parse import quote
                    page.append(f"<figure style='display:inline-block;width:45%'><figcaption>{html.escape(candidate[f'{side}_image_id'])}</figcaption><img loading='lazy' style='width:100%' src='{html.escape(quote(relative))}'></figure>")
            (output / "near_duplicates.html").write_text("\n".join(page), encoding="utf-8")
            summary["near_duplicates"] = near_summary
        if args.mode in {"all", "annotations"}:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from docucheck.visualization.receipt import plot_standardized_record

            train = [r for r in records if r.get("source_split") == "train"]
            if not train:
                raise ValueError("No source train records available for annotation review")
            features = collect_image_features(train, root)
            selected = select_annotation_audit_sample(train, features, size=args.sample_size, seed=args.seed)
            by_id = {r["image_id"]: r for r in train}
            feature_by_id = features.set_index("image_id").to_dict("index")
            page = ["<meta charset='utf-8'><title>Local annotation review</title>",
                    "<h1>Annotation audit — pending human review</h1>",
                    "<p>Source KIE polygons and labels. Geometry validity is not annotation correctness. Record findings in annotation_review.csv.</p>"]
            review_rows = []
            image_dir = output / "overlays"
            image_dir.mkdir(exist_ok=True)
            for item in selected:
                image_id = item["image_id"]
                record = by_id[image_id]
                feature = feature_by_id[image_id]
                item["metadata"] = {
                    "split": record["split"], "annotation_status": record["annotation_status"],
                    "annotation_issues": record.get("annotation_issues", []),
                    "geometry_issues": record.get("validation_issues", []),
                    "kie_region_count": len(record["regions"]),
                    "ocr_ground_truth_status": record["ocr_ground_truth_status"],
                    **{key: feature.get(key) for key in ("width", "height", "brightness_mean", "contrast_std", "laplacian_variance")},
                }
                page.append(f"<h2>{html.escape(image_id)}</h2><pre>{html.escape(json.dumps(item, indent=2))}</pre>")
                fig, ax = plt.subplots(figsize=(9, 12))
                try:
                    plot_standardized_record(record, dataset_root=root, ax=ax)
                    fig.savefig(image_dir / f"{image_id}.png", dpi=110, bbox_inches="tight")
                    page.append(f"<img loading='lazy' style='max-width:100%' src='overlays/{image_id}.png'>")
                except (OSError, ValueError, TypeError) as error:
                    item["overlay_error"] = type(error).__name__
                    page.append("<p>Overlay unavailable; inspect source status.</p>")
                finally:
                    plt.close(fig)
                review_rows.append({"image_id": image_id, "review_status": "not_reviewed",
                                    **dict.fromkeys(("annotation_correctness", "wrong_label", "wrong_geometry",
                                                     "missing_field_annotation", "unreadable_text", "uncertain",
                                                     "region_indices", "field", "evidence_notes", "reviewer", "reviewed_at"), "")})
            with (output / "annotation_review.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(review_rows[0]))
                writer.writeheader()
                writer.writerows(review_rows)
            write_jsonl(output / "annotation_sample.jsonl", selected)
            (output / "annotations.html").write_text("\n".join(page), encoding="utf-8")
            summary["annotation_sample_count"] = len(selected)
            summary["field_missingness"] = summarize_field_missingness(records)
            summary["unmapped_region_count"] = sum(r.get("label_status") == "unmapped" for row in train for r in row["regions"])
        (output / "audit_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(f"Audit failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
