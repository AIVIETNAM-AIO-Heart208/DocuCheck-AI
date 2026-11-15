"""Run one image through OCR and CUDA Qwen; stdout contains only four-field JSON."""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docucheck.extraction.contracts import EXTRACTION_MODES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Receipt image path")
    parser.add_argument("--output", type=Path, help="Also save the four-field JSON here")
    parser.add_argument("--extraction-mode", choices=EXTRACTION_MODES, default="baseline")
    args = parser.parse_args()
    try:
        image = args.image.resolve(strict=True)
        with Image.open(image) as receipt:
            width, height = receipt.size
        identity = hashlib.sha256(image.read_bytes()).hexdigest()[:24]
        base = ROOT / "outputs/ocr_to_qwen/single_receipt"
        base.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=f"{identity}_", dir=base))
        manifest = work / "manifest.jsonl"
        manifest.write_text(json.dumps({
            "image_id": identity, "image_path": str(image),
            "image_width": width, "image_height": height,
            "split": "internal_dev", "source_subset": "single_receipt",
            "regions": [],
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        log_path = work / "pipeline.log"
        print(f"Running OCR and CUDA Qwen. Logs: {log_path}", file=sys.stderr)
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/demo_ocr_qwen.py"),
                "--manifest", str(manifest), "--output-dir", str(work),
                "--extraction-mode", args.extraction_mode,
            ], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError(f"Pipeline failed. Inspect {log_path}")
        payload = json.loads((work / "receipts" / f"{identity}.json").read_text(encoding="utf-8"))
        if args.extraction_mode == "refined":
            diagnostics = work / "extractions.jsonl"
            row = json.loads(diagnostics.read_text(encoding="utf-8").splitlines()[0])
            review = [key for key, value in row.get("fields", {}).items()
                      if value["status"] == "needs_review"]
            print(f"Refined diagnostics: {diagnostics}; needs_review: {review}", file=sys.stderr)
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
