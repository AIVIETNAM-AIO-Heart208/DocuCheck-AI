"""Run the existing OCR CLI after loading CUDA DLLs from PyTorch on Windows."""

import json
import runpy
import sys
from pathlib import Path

import torch  # Load CUDA/cuDNN DLLs before ONNX Runtime creates its session.

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from docucheck.ocr.detectors import PHOCRTextDetector
from docucheck.ocr.recognizers import VietOCRBaseline

original = PHOCRTextDetector.__init__


def checked_init(self, **kwargs):
    original(self, **kwargs)
    session = getattr(self.backend, "session", None)
    if session is None:
        session = getattr(getattr(self.backend, "backend", None), "session", None)
    if session is not None and not hasattr(session, "get_providers"):
        session = getattr(session, "session", None)
    providers = session.get_providers() if session else []
    if not providers or providers[0] != "CUDAExecutionProvider":
        raise RuntimeError(f"Actual PHOCR session is not CUDA: {providers}")
    print(
        json.dumps(
            {
                "actual_phocr_providers": providers,
                "torch_cuda": torch.cuda.is_available(),
            }
        ),
        flush=True,
    )


PHOCRTextDetector.__init__ = checked_init
original_recognizer = VietOCRBaseline.__init__


def checked_recognizer(self, **kwargs):
    original_recognizer(self, **kwargs)
    actual = str(next(self.backend.model.parameters()).device)
    if actual != "cuda:0":
        raise RuntimeError(f"Actual VietOCR model device is {actual}")
    print(json.dumps({"actual_vietocr_device": actual}), flush=True)


VietOCRBaseline.__init__ = checked_recognizer
runpy.run_path(str(Path(__file__).with_name("run_ocr.py")), run_name="__main__")
