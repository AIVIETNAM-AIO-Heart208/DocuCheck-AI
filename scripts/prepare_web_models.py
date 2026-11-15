"""Explicit setup only: copy local weights and produce a checksum-verified offline bundle."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(source, destination, config_file=None, fetch_config=False):
    import yaml
    if destination.exists():
        raise ValueError("Destination exists; choose a new model bundle directory")
    if config_file is None and not fetch_config:
        raise ValueError("Supply --config-file with merged VietOCR YAML, or explicitly --fetch-config")
    qwen = json.loads((ROOT / "configs/qwen3_4b_q4_k_m.json").read_text(encoding="utf-8"))
    weights = [
        (source / "models/qwen3_4b_instruct_2507" / qwen["filename"], "qwen/model.gguf", qwen["sha256"],
         f"https://huggingface.co/{qwen['repository']}/tree/{qwen['revision']}"),
        (source / "ocr/models/phocr/official_models/ch_PP-OCRv5_server_det.onnx", "phocr/ch_PP-OCRv5_server_det.onnx",
         "0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad",
         "https://www.modelscope.cn/models/puhuilab/PHOCR"),
        (source / "ocr/models/vietocr/vgg_transformer.pth", "vietocr/vgg_transformer.pth", None,
         "https://vocr.vn/data/vietocr/vgg_transformer.pth")]
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".docucheck-models-", dir=destination.parent)).resolve()
    try:
        files = []
        for local, name, expected, origin in weights:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local, target)
            actual = digest(target)
            if expected and actual != expected:
                raise ValueError(f"Wrong weights: {local.name}")
            files.append({"path":name, "sha256":actual, "bytes":target.stat().st_size,
                          "source":origin, "verification":"pinned_reference" if expected else "local_source_hash_only"})
        if config_file:
            config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            config_source = "user-provided merged VietOCR YAML"
        else:
            config = {}
            for name in ("base.yml", "vgg-transformer.yml"):
                with urllib.request.urlopen("https://vocr.vn/data/vietocr/config/"+name, timeout=30) as response:
                    config.update(yaml.safe_load(response.read().decode("utf-8")))
            config_source = "https://vocr.vn/data/vietocr/config/ (base.yml + vgg-transformer.yml)"
        if not isinstance(config, dict) or config.get("backbone") != "vgg19_bn" or config.get("seq_modeling") != "transformer":
            raise ValueError("Expected complete vgg_transformer configuration")
        config["weights"] = "vgg_transformer.pth"  # Worker sets absolute weights/device; no URL fallback.
        config["device"] = "cuda:0"
        config["cnn"]["pretrained"] = False
        config["predictor"]["beamsearch"] = False
        target = stage / "vietocr/config.yml"
        target.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=True), encoding="utf-8")
        files.append({"path":"vietocr/config.yml", "sha256":digest(target), "bytes":target.stat().st_size,
                      "source":config_source, "verification":"setup_snapshot_hash"})
        manifest = {"schema_version":1, "model":"Qwen3-4B-Instruct-2507-Q4_K_M",
                    "qwen_revision":qwen["revision"], "files":files,
                    "licenses":"See SOURCES_AND_LICENSES.md; verify model redistribution terms before bundling"}
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (stage / "SOURCES_AND_LICENSES.md").write_text(
            "# Model bundle sources\n\n" + "\n".join(f"- {entry['path']}: {entry['source']}" for entry in files)
            + "\n\nSoftware/model source notices: https://github.com/pbcquoc/vietocr ; "
              "https://github.com/ggml-org/llama.cpp ; PHOCR PyPI/model source above.\n"
              "This manifest records provenance, not a license grant. Model-specific redistribution "
              "licenses have not been independently verified by this script; include any required "
              "license texts/model cards with your submission.\n", encoding="utf-8")
        stage.rename(destination)
        print(f"Offline bundle prepared: {destination}")
    finally:
        if stage.exists() and stage.parent == destination.parent and stage.name.startswith(".docucheck-models-"):
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--destination", type=Path, default=ROOT / "models")
    parser.add_argument("--config-file", type=Path)
    parser.add_argument("--fetch-config", action="store_true", help="Explicitly allow one-time download of YAML config only")
    args = parser.parse_args()
    prepare(args.source_root, args.destination, args.config_file, args.fetch_config)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
