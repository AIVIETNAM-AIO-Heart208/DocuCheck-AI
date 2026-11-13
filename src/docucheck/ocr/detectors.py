"""Optional text detectors and source-coordinate crop helpers."""

from __future__ import annotations

import importlib.metadata
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from docucheck.data.loader import REPOSITORY_ROOT
from docucheck.ocr.recognizers import _image, _local_path, _paddle_device, _sha256_path


PADDLE_DETECTOR_MODEL_NAME = "PP-OCRv6_medium_det"
PADDLE_DETECTOR_MODEL_DIR = (
    "outputs/ocr/models/paddleocr/official_models/PP-OCRv6_medium_det"
)
PHOCR_DETECTOR_MODEL_NAME = "ch_PP-OCRv5_server_det"
PHOCR_DETECTOR_MODEL_PATH = (
    "outputs/ocr/models/phocr/official_models/ch_PP-OCRv5_server_det.onnx"
)
PHOCR_DETECTOR_MODEL_URL = (
    "https://www.modelscope.cn/models/puhuilab/PHOCR/resolve/master/"
    "onnx/PP-OCRv5/det/ch_PP-OCRv5_server_det.onnx"
)
PHOCR_DETECTOR_MODEL_SHA256 = (
    "0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad"
)


def validate_polygon(
    polygon: Any,
    width: int,
    height: int,
) -> str | None:
    """Return a validation issue for a detector quadrilateral, if any."""
    if not isinstance(polygon, (list, tuple)) or len(polygon) != 4:
        return "expected_quadrilateral"
    try:
        points = [[float(point[0]), float(point[1])] for point in polygon]
    except (IndexError, TypeError, ValueError):
        return "malformed_points"
    if any(not np.isfinite(value) for point in points for value in point):
        return "nonfinite_coordinate"
    if any(
        x < 0 or x > width or y < 0 or y > height
        for x, y in points
    ):
        return "out_of_bounds"
    area = abs(sum(
        points[index][0] * points[(index + 1) % 4][1]
        - points[(index + 1) % 4][0] * points[index][1]
        for index in range(4)
    )) / 2
    if area <= 0:
        return "degenerate_polygon"
    return None


def _as_polygon(value: Any) -> list[list[float]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [[float(point[0]), float(point[1])] for point in value]


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    polygon = candidate["polygon"]
    return (
        min(point[1] for point in polygon),
        min(point[0] for point in polygon),
        max(point[1] for point in polygon),
        max(point[0] for point in polygon),
        tuple(value for point in polygon for value in point),
    )


class PaddleOCRTextDetector:
    """Use PaddleOCR text detection without invoking its recognizer."""

    engine_name = "PaddleOCRTextDetection"
    model_name = PADDLE_DETECTOR_MODEL_NAME
    model_source = "PaddleOCR official model catalog"
    device = "cpu"

    def __init__(
        self,
        *,
        model_dir: str | Path = PADDLE_DETECTOR_MODEL_DIR,
        device: str = "cpu",
        backend: Any | None = None,
    ):
        started = time.perf_counter()
        self.model_dir = _local_path(model_dir)
        self.device = _paddle_device(device)
        if not self.model_dir.is_dir():
            raise FileNotFoundError(
                f"PaddleOCR detector model not found at {self.model_dir}; "
                "run scripts/download_recognition_models.py --engine paddleocr-detector"
            )
        if backend is None:
            try:
                from paddleocr import TextDetection
            except ImportError as error:
                raise RuntimeError(
                    "PaddleOCR dependencies are missing; run uv sync --extra paddleocr"
                ) from error
            if self.device.startswith("gpu"):
                import paddle

                if not paddle.device.is_compiled_with_cuda():
                    raise RuntimeError("Paddle GPU requested but the installed PaddlePaddle has no CUDA support")
            backend = TextDetection(
                model_name=self.model_name,
                model_dir=str(self.model_dir),
                device=self.device,
                enable_mkldnn=False,
            )
        self.backend = backend
        module = backend.__class__.__module__
        self.engine_version = (
            importlib.metadata.version("paddleocr")
            if module.startswith(("paddleocr", "paddlex"))
            else "test"
        )
        self.model_names = {"detection": self.model_name}
        self.model_sha256 = _sha256_path(self.model_dir)
        self.model_load_seconds = time.perf_counter() - started
        self.last_issues: list[dict[str, Any]] = []

    @property
    def preprocessing(self) -> dict[str, Any]:
        return {
            "mode": "text-detection-only",
            "output": "validated quadrilateral polygons",
            "enable_mkldnn": False,
        }

    def predict(self, image_path: str | Path) -> list[dict[str, Any]]:
        path = Path(image_path)
        with _image(path) as image:
            width, height = image.size
        self.last_issues = []
        results = list(self.backend.predict(str(path)))
        if not results:
            return []
        if len(results) != 1:
            raise ValueError(f"Expected one detector result for one image, got {len(results)}")
        result = results[0]
        polygons = result.get("dt_polys") if hasattr(result, "get") else None
        scores = result.get("dt_scores") if hasattr(result, "get") else None
        if polygons is None or scores is None or len(polygons) != len(scores):
            raise ValueError("PaddleOCR detector result is missing aligned dt_polys/dt_scores")

        candidates = []
        for index, (raw_polygon, raw_score) in enumerate(zip(polygons, scores)):
            try:
                polygon = _as_polygon(raw_polygon)
            except (IndexError, TypeError, ValueError):
                self.last_issues.append({
                    "region_index": index,
                    "polygon": [],
                    "validation_issue": "malformed_points",
                })
                continue
            issue = validate_polygon(polygon, width, height)
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                issue = issue or "invalid_confidence"
                score = None
            if score is not None and (not np.isfinite(score) or not 0 <= score <= 1):
                issue = issue or "invalid_confidence"
            if issue:
                self.last_issues.append({
                    "region_index": index,
                    "polygon": polygon,
                    "confidence": score,
                    "validation_issue": issue,
                })
                continue
            candidates.append({
                "region_index": index,
                "polygon": polygon,
                "confidence": score,
            })
        return sorted(candidates, key=_candidate_sort_key)


class PHOCRTextDetector:
    """Use PHOCR's detector component without invoking its recognizer."""

    engine_name = "PHOCRTextDetection"
    model_name = PHOCR_DETECTOR_MODEL_NAME
    model_source = PHOCR_DETECTOR_MODEL_URL
    device = "cpu"

    def __init__(
        self,
        *,
        model_path: str | Path = PHOCR_DETECTOR_MODEL_PATH,
        device: str = "cpu",
        backend: Any | None = None,
    ):
        started = time.perf_counter()
        self.model_path = _local_path(model_path)
        self.device = device
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"PHOCR detector model not found at {self.model_path}; "
                "run scripts/download_recognition_models.py --engine phocr-detector"
            )
        if backend is None:
            try:
                from phocr.det import TextDetector
                from phocr.main import DEFAULT_CFG_PATH
                from phocr.utils.parse_parameters import ParseParams
            except ImportError as error:
                raise RuntimeError(
                    "PHOCR dependencies are missing; use the documented isolated PHOCR/VietOCR environment"
                ) from error
            if device.startswith("cuda"):
                import onnxruntime

                if "CUDAExecutionProvider" not in onnxruntime.get_available_providers():
                    raise RuntimeError(
                        "PHOCR CUDA requested but ONNX Runtime has no CUDAExecutionProvider"
                    )
            config = ParseParams.load(DEFAULT_CFG_PATH)
            config.Det.engine_cfg = config.EngineConfig[config.Det.engine_type.value]
            config.Det.model_path = str(self.model_path)
            config.Det.engine_cfg.use_cuda = device.startswith("cuda")
            backend = TextDetector(config.Det)
        self.backend = backend
        if device.startswith("cuda"):
            session = getattr(backend, "session", None)
            providers = session.get_providers() if hasattr(session, "get_providers") else None
            if providers is not None and providers[0] not in {
                "CUDAExecutionProvider",
                "TensorrtExecutionProvider",
            }:
                raise RuntimeError(
                    "PHOCR CUDA requested but the detector initialized on "
                    f"{providers}; expose compatible CUDA libraries before inference"
                )
        module = backend.__class__.__module__
        self.engine_version = (
            importlib.metadata.version("phocr")
            if module.startswith("phocr")
            else "test"
        )
        self.model_names = {"detection": self.model_name}
        self.model_sha256 = _sha256_path(self.model_path)
        self.model_load_seconds = time.perf_counter() - started
        self.last_issues: list[dict[str, Any]] = []

    @property
    def preprocessing(self) -> dict[str, Any]:
        return {
            "mode": "text-detection-only",
            "output": "validated quadrilateral polygons",
            "box_thresh": 0.5,
            "unclip_ratio": 1.6,
            "recognizer_invoked": False,
        }

    def predict(self, image_path: str | Path) -> list[dict[str, Any]]:
        path = Path(image_path)
        with _image(path) as source:
            rgb = np.asarray(source)
            height, width = rgb.shape[:2]
            image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        self.last_issues = []
        result = self.backend(image)
        polygons = result.get("boxes") if hasattr(result, "get") else getattr(result, "boxes", None)
        scores = result.get("scores") if hasattr(result, "get") else getattr(result, "scores", None)
        if polygons is None:
            return []
        if scores is None:
            scores = [None] * len(polygons)
        if len(polygons) != len(scores):
            raise ValueError("PHOCR detector result has unaligned boxes and scores")

        candidates = []
        for index, (raw_polygon, raw_score) in enumerate(zip(polygons, scores)):
            try:
                polygon = _as_polygon(raw_polygon)
            except (IndexError, TypeError, ValueError):
                self.last_issues.append({
                    "region_index": index,
                    "polygon": [],
                    "validation_issue": "malformed_points",
                })
                continue
            issue = validate_polygon(polygon, width, height)
            score = None
            if raw_score is not None:
                try:
                    score = float(raw_score)
                except (TypeError, ValueError):
                    issue = issue or "invalid_confidence"
                if score is not None and (not np.isfinite(score) or not 0 <= score <= 1):
                    issue = issue or "invalid_confidence"
            if issue:
                self.last_issues.append({
                    "region_index": index,
                    "polygon": polygon,
                    "confidence": score,
                    "validation_issue": issue,
                })
                continue
            candidates.append({
                "region_index": index,
                "polygon": polygon,
                "confidence": score,
            })
        return sorted(candidates, key=_candidate_sort_key)


def crop_polygon(
    image_path: str | Path,
    polygon: list[list[float]],
    output_path: str | Path,
    *,
    padding_percent: float = 0,
) -> Path:
    """Perspective-rectify a detector quadrilateral into a local crop."""
    source_path = Path(image_path)
    destination_path = Path(output_path)
    try:
        padding_percent = float(padding_percent)
    except (TypeError, ValueError) as error:
        raise ValueError("padding_percent must be a finite non-negative number") from error
    if not np.isfinite(padding_percent) or padding_percent < 0:
        raise ValueError("padding_percent must be a finite non-negative number")
    with Image.open(source_path) as source:
        source = source.convert("RGB")
        width, height = source.size
        issue = validate_polygon(polygon, width, height)
        if issue:
            raise ValueError(f"Cannot crop invalid polygon: {issue}")
        points = np.asarray(polygon, dtype=np.float32)
        if padding_percent:
            center = points.mean(axis=0)
            points = center + (points - center) * (1 + padding_percent / 100)
            points[:, 0] = np.clip(points[:, 0], 0, width)
            points[:, 1] = np.clip(points[:, 1], 0, height)
            issue = validate_polygon(points.tolist(), width, height)
            if issue:
                raise ValueError(f"Cannot crop invalid padded polygon: {issue}")
        top_width = np.linalg.norm(points[1] - points[0])
        bottom_width = np.linalg.norm(points[2] - points[3])
        left_height = np.linalg.norm(points[3] - points[0])
        right_height = np.linalg.norm(points[2] - points[1])
        crop_width = max(1, int(round(max(top_width, bottom_width))))
        crop_height = max(1, int(round(max(left_height, right_height))))
        target = np.asarray(
            [[0, 0], [crop_width - 1, 0], [crop_width - 1, crop_height - 1], [0, crop_height - 1]],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(points, target)
        pixels = cv2.warpPerspective(
            np.asarray(source),
            matrix,
            (crop_width, crop_height),
            borderValue=(255, 255, 255),
        )
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(destination_path)
    return destination_path
