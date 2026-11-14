"""Read-only provenance capture, called only when the user starts extraction."""

import hashlib
import json
from pathlib import Path
import subprocess


def capture(mode: str, ocr: Path, manifest: Path) -> dict:
    root = Path(__file__).resolve().parents[3]

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def git(*args):
        completed = subprocess.run(["git", *args], cwd=root, capture_output=True,
                                   text=True, check=False)
        return completed.stdout if completed.returncode == 0 else None

    files = [*Path(__file__).parent.glob("*.py"), root / "configs/qwen3_4b_q4_k_m.json"]
    runtime = ocr.parent / "runtime.json"
    return {"extraction_mode": mode, "commit": git("rev-parse", "HEAD"),
            "working_tree_status": git("status", "--short", "--untracked-files=no"),
            "source_sha256": {str(p.relative_to(root)): digest(p) for p in files},
            "ocr_sha256": digest(ocr), "manifest_sha256": digest(manifest),
            "ocr_runtime": json.loads(runtime.read_text(encoding="utf-8")) if runtime.exists() else None,
            "model_config": json.loads((root / "configs/qwen3_4b_q4_k_m.json").read_text()),
            "weights_sha256_verified_in_this_capture": False,
            "comparison_or_accuracy_verified": False}
