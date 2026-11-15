"""Extract fields from existing OCR JSONL using a local CUDA Qwen server."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from docucheck.extraction.contracts import EXTRACTION_MODES
from docucheck.extraction.qwen import QwenClient, adapt, write_json
from docucheck.extraction.export import export_receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--image-id", action="append")
    parser.add_argument("--base-url", default="http://127.0.0.1:8097")
    parser.add_argument("--extraction-mode", choices=EXTRACTION_MODES, default="baseline")
    args = parser.parse_args()
    directory = Path(args.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "extractions.jsonl").exists():
        raise ValueError("Use a new directory; extractions already exist")
    from docucheck.extraction.refinement_provenance import capture
    write_json(directory / "provenance.json", capture(args.extraction_mode, Path(args.ocr), Path(args.manifest)))
    manifest = {
        r["image_id"]: r
        for r in map(
            json.loads, Path(args.manifest).read_text(encoding="utf-8").splitlines()
        )
    }
    results = []
    for row in map(json.loads, Path(args.ocr).read_text(encoding="utf-8").splitlines()):
        if args.image_id and row["image_id"] not in args.image_id:
            continue
        try:
            record = manifest[row["image_id"]]
            adapted = adapt(row, record["image_width"], record["image_height"])
            if args.extraction_mode == "refined":
                adapted["image_dimensions"] = {"width": record["image_width"], "height": record["image_height"]}
            write_json(directory / "inputs" / f"{row['image_id']}.json", adapted)
            print(f"[{row['image_id']}] extraction mode={args.extraction_mode}", file=sys.stderr)
            result = QwenClient(args.base_url, extraction_mode=args.extraction_mode).extract(adapted, directory)
            review = [key for key, value in result["fields"].items() if value["status"] == "needs_review"]
            if review:
                print(f"Review {review}; diagnostics: {directory / 'extractions.jsonl'}", file=sys.stderr)
        except (OSError, ValueError, KeyError, TypeError) as error:
            result = {
                "image_id": row["image_id"],
                "status": "failed",
                "error": f"{type(error).__name__}: {error}",
            }
            write_json(
                directory / "responses" / f"{row['image_id']}.error.json", result
            )
        results.append(result)
    (directory / "extractions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results),
        encoding="utf-8",
    )
    export_receipts(results, directory)
    print(
        json.dumps(
            [
                {
                    "image_id": r["image_id"],
                    "status": r["status"],
                    "error": r.get("error"),
                }
                for r in results
            ]
        )
    )
    return int(any(r["status"] != "ok" for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
