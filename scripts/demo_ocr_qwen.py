"""Run selected receipt OCR and a managed local CUDA Qwen process sequentially."""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from docucheck.extraction.qwen import (
    RUNTIME_CONFIG,
    QwenClient,
    render_demo,
    write_json,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        required=True,
        help="Preselected receipt manifest (at most three records)",
    )
    parser.add_argument("--output-dir", required=True, help="New run directory")
    parser.add_argument(
        "--reuse-ocr",
        action="store_true",
        help="Explicitly reuse OCR in this directory",
    )
    args = parser.parse_args()
    directory = Path(args.output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    records = [
        json.loads(x)
        for x in Path(args.manifest).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    if not 1 <= len(records) <= 3:
        raise ValueError("Select one to three receipts")
    if (directory / "extractions.jsonl").exists():
        raise ValueError("Use a new directory; predictions already exist")
    logs = directory / "logs"
    logs.mkdir(exist_ok=True)
    snapshots = []

    def gpu():
        value = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).strip()
        snapshots.append({"time": time.time(), "used_free_MiB": value})
        return value

    gpu()
    if not args.reuse_ocr:
        with (logs / "ocr.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                [
                    str(ROOT / ".venv-phocr-gpu/Scripts/python.exe"),
                    str(ROOT / "scripts/run_ocr_cuda.py"),
                    "--engine",
                    "phocr-vietocr",
                    "--device",
                    "cuda:0",
                    "--manifest",
                    str(Path(args.manifest).resolve()),
                    "--split",
                    records[0]["split"],
                    "--output-dir",
                    str(directory / "ocr"),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=ROOT,
                check=False,
            )
        # VietOCR may emit harmless warnings on stderr; artifacts determine success.
        runtime = json.loads((directory / "ocr/runtime.json").read_text())
        if runtime["images_failed"] or runtime["candidate_failures"]:
            raise RuntimeError(f"OCR failed, exit={completed.returncode}")
    gpu()
    binary = next((ROOT / "outputs/runtime/llama-b12345").rglob("llama-server.exe"))
    model = (
        ROOT
        / "outputs/models/qwen3_4b_instruct_2507/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    )
    command = [
        str(binary),
        "-m",
        str(model),
        "-ngl",
        "99",
        "-c",
        str(RUNTIME_CONFIG["context"]),
        "-np",
        "1",
        "-b",
        "256",
        "-ub",
        "128",
        "--host",
        "127.0.0.1",
        "--port",
        "8097",
        "--jinja",
        "-lv",
        "4",
    ]
    result_code = 1
    with (logs / "qwen.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            client = QwenClient(timeout=2)
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Qwen process exited; see logs/qwen.log")
                try:
                    client.request("/health")
                    break
                except (OSError, urllib.error.URLError, json.JSONDecodeError):
                    time.sleep(1)
            else:
                raise TimeoutError("Qwen startup timeout")
            gpu()
            log.flush()
            text = (logs / "qwen.log").read_text(encoding="utf-8", errors="replace")
            if "offloaded 37/37 layers" not in text:
                raise RuntimeError("Full GPU offload not verified; inspect log")
            write_json(directory / "server_props.json", client.request("/props"))
            extraction = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "scripts/extract_receipt_fields.py"),
                    "--ocr",
                    str(directory / "ocr/predictions.jsonl"),
                    "--manifest",
                    str(Path(args.manifest).resolve()),
                    "--output-dir",
                    str(directory),
                ],
                cwd=ROOT,
            )
            while extraction.poll() is None:
                gpu()
                time.sleep(1)
            result_code = extraction.returncode
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            gpu()
            write_json(
                directory / "runtime.json",
                {
                    "command": command,
                    "download": json.loads(
                        (model.parent / "download.json").read_text()
                    ),
                    "gpu_memory_samples": snapshots,
                    "peak_observed_used_MiB": max(
                        int(s["used_free_MiB"].split(",")[0]) for s in snapshots
                    ),
                    "ocr_reused": args.reuse_ocr,
                    "confidence_policy": "minimum recognition confidence; null if any missing",
                    "exit_code": result_code,
                },
            )
    results = [
        json.loads(x)
        for x in (directory / "extractions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    images = {
        r["image_id"]: os.path.relpath(
            ROOT / "data/mcocr" / r["image_path"], directory
        ).replace("\\", "/")
        for r in records
    }
    render_demo(results, directory, images)
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
