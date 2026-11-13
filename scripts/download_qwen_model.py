"""Download the pinned GGUF and official Windows CUDA runtime locally."""

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

REVISION = "ae44f08e1392f39c0e474af10c3ff8355c8b6688"
BUILD = "b12345"
ROOT = Path(__file__).resolve().parents[1]
MODEL = (
    ROOT
    / "outputs/models/qwen3_4b_instruct_2507/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
)
RUNTIME = ROOT / "outputs/runtime/llama-b12345"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    urls = [
        (
            MODEL,
            f"https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/resolve/{REVISION}/{MODEL.name}",
        )
    ]
    for name in [
        f"llama-{BUILD}-bin-win-cuda-12.4-x64.zip",
        "cudart-llama-bin-win-cuda-12.4-x64.zip",
    ]:
        urls.append(
            (
                RUNTIME / name,
                f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}/{name}",
            )
        )
    records = []
    for path, url in urls:
        if not path.exists():
            print("Downloading", path.name, flush=True)
            temporary = path.with_suffix(path.suffix + ".partial")
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(path)
        records.append(
            {
                "file": str(path.relative_to(ROOT)),
                "url": url,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )
        if (
            path == MODEL
            and records[-1]["sha256"]
            != "2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e"
        ):
            raise ValueError("GGUF checksum mismatch; refusing to use model")
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                archive.extractall(RUNTIME)
    (MODEL.parent / "download.json").write_text(
        json.dumps(
            {"revision": REVISION, "runtime_build": BUILD, "files": records}, indent=2
        ),
        encoding="utf-8",
    )
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
