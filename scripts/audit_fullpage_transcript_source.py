#!/usr/bin/env python3
"""Compare a recorded full-page manifest with original sidecar text boundaries."""
import argparse
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_psm_comparison import load_manifest, save, sha


def audit_source(manifest, dataset_root):
    labels = {"OTHER", "SELLER", "ADDRESS", "TIMESTAMP", "TOTAL_COST"}
    counts, files, examples = Counter(), [], []
    for r in (r for r in load_manifest(manifest) if r.get("split") == "internal_dev"):
        source = dataset_root / "kie_data/kie_data/boxes_and_transcripts" / (Path(r["source_image_name"]).stem + ".tsv")
        raw = source.read_text(encoding="utf-8-sig").splitlines()
        files.append({"path": str(source), "sha256": sha(source)})
        present = 0
        for region in r["ocr_regions"]:
            counts["regions"] += 1
            line = raw[region["source_line"] - 1]
            if line != region["source_raw"]:
                raise ValueError("Manifest source_raw differs from sidecar")
            fields = line.split(",", 9)
            if len(fields) != 10 or "," not in fields[-1]:
                counts["malformed"] += 1
                continue
            text, label = fields[-1].rsplit(",", 1)
            counts["known_label" if label in labels else "unknown_label"] += 1
            counts["transcript_present" if text.strip() else "transcript_empty"] += 1
            valid = not region["validation_issues"] and bool(region.get("polygon"))
            if valid:
                counts["valid_geometry_transcript_present" if text.strip() else "valid_geometry_transcript_empty"] += 1
            counts["manifest_text_differs_from_source_transcript"] += text != region["text_raw"]
            present += bool(text.strip()) and valid
            if len(examples) < 8 and text.strip():
                examples.append({"image_id": r["image_id"], "source_line": region["source_line"],
                    "source_raw": line, "current_gt": region["text_raw"], "candidate_transcript": text, "terminal_label": label})
        counts["images_with_nonempty_valid_transcript" if present else "images_without_nonempty_valid_transcript"] += 1
    return {"status": "requires_protocol_decision" if counts["manifest_text_differs_from_source_transcript"] else "consistent",
        "finding": "Compare ID + eight coordinates + transcript (may contain commas) + terminal category against manifest text; do not change source or infer missing transcripts.",
        "counts": dict(counts), "examples": examples, "source_files": files,
        "scope": "Internal_dev full-page sidecars only. Recognition crop benchmark uses separate source and parser."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, default=ROOT / "data/mcocr")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output file to preserve prior evidence")
    result = audit_source(args.manifest, args.dataset_root)
    save(args.output, result)
    print(result["counts"])


if __name__ == "__main__":
    main()
