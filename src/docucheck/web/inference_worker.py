"""Isolated, persistent OCR or extraction worker. Started only by the user-run app."""

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
import traceback

from docucheck.extraction.contracts import EXTRACTION_MODES
from .ipc import configure_stdio, message_line


def emit(payload):
    sys.stdout.write(message_line(payload))
    sys.stdout.flush()


def load_ocr(models):
    import torch  # Make bundled CUDA/cuDNN libraries visible before ONNX.
    import onnxruntime as ort
    if hasattr(ort, "preload_dlls"):
        ort.preload_dlls()
    from docucheck.ocr.detectors import PHOCRTextDetector
    from docucheck.ocr.recognizers import VietOCRBaseline
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    torch.set_num_threads(int(__import__("os").environ.get("OMP_NUM_THREADS", "4")))
    detector = PHOCRTextDetector(model_path=models / "phocr/ch_PP-OCRv5_server_det.onnx", device="cuda:0")
    session = getattr(detector.backend, "session", None)
    if session is None:
        session = getattr(getattr(detector.backend, "backend", None), "session", None)
    if session is not None and not hasattr(session, "get_providers"):
        session = getattr(session, "session", None)
    providers = session.get_providers() if session else []
    if not providers or providers[0] != "CUDAExecutionProvider":
        raise RuntimeError("Actual PHOCR CUDA provider unavailable")
    recognizer = VietOCRBaseline(model_path=models / "vietocr/vgg_transformer.pth", device="cuda:0",
                                scale_factor=2, config_path=models / "vietocr/config.yml")
    if str(next(recognizer.backend.model.parameters()).device) != "cuda:0":
        raise RuntimeError("Actual VietOCR device is not cuda:0")
    return detector, recognizer, {"providers":providers, "recognizer_device":"cuda:0"}


def main():
    configure_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("ocr", "extract"))
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--mode", choices=EXTRACTION_MODES, required=True)
    args = parser.parse_args()
    try:
        with redirect_stdout(sys.stderr):
            if args.role == "ocr":
                detector, recognizer, info = load_ocr(args.models)
            else:
                from docucheck.extraction.qwen import QwenClient
                info = {"role":"extraction_http_client"}
        emit({"ok":True, "ready":True, **info})
    except Exception as error:
        traceback.print_exc(file=sys.stderr)
        emit({"ok":False, "code":type(error).__name__})
        return 1
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            directory = Path(request["directory"])
            with redirect_stdout(sys.stderr):
                if args.role == "ocr":
                    from docucheck.ocr.hybrid import run_hybrid_batch
                    from docucheck.extraction.ocr_contract import validate_runtime
                    metadata = run_hybrid_batch([request["record"]], dataset_root=directory,
                        split="web", output_dir=directory / "ocr", detector=detector,
                        recognizer=recognizer, crop_padding_percent=10)
                    validate_runtime(metadata)
                    if metadata["images_failed"] or metadata["recognized_candidates"] == 0:
                        raise RuntimeError("OCR produced no usable evidence")
                    result = {"runtime":metadata, "partial":bool(metadata["candidate_failures"])}
                else:
                    from docucheck.extraction.qwen import adapt, write_json
                    row = json.loads((directory / "ocr/predictions.jsonl").read_text(encoding="utf-8").splitlines()[0])
                    record = request["record"]
                    adapted = adapt(row, record["image_width"], record["image_height"])
                    adapted["image_dimensions"] = {"width":record["image_width"], "height":record["image_height"]}
                    write_json(directory / "inputs" / f"{row['image_id']}.json", adapted)
                    client = QwenClient(request["base_url"], timeout=request["http_timeout"], extraction_mode=args.mode)
                    result = client.extract(adapted, directory)
                    write_json(directory / "extraction.json", result)
            emit({"ok":True, "request_id":request["request_id"], "result":result})
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            emit({"ok":False, "request_id":request.get("request_id"), "code":type(error).__name__})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
