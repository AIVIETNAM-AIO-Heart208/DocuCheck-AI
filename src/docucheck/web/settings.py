"""Explicit resource settings shared by API, coordinator and child workers."""

from dataclasses import dataclass
import os
from pathlib import Path

from docucheck.extraction.contracts import EXTRACTION_MODES


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    storage: Path = ROOT / "outputs/web"
    models: Path = ROOT / "models"
    ocr_python: str = "python"
    llama_binary: str = "llama-server"
    extraction_mode: str = "refined"
    gpu_policy: str = "exclusive"
    resident_validated: bool = False
    resident_free_mib: int = 7000
    min_free_mib: int = 512
    queue_size: int = 4
    per_session: int = 2
    max_bytes: int = 15 * 1024 * 1024
    max_pixels: int = 25_000_000
    disk_bytes: int = 2 * 1024**3
    ttl_seconds: int = 24 * 3600
    startup_timeout: int = 180
    ocr_timeout: int = 180
    extraction_timeout: int = 180
    job_timeout: int = 600
    cpu_threads: int = 4
    llama_port: int = 8097
    build_revision: str = "working-tree"
    cookie_secure: bool = False

    def __post_init__(self):
        if self.extraction_mode not in EXTRACTION_MODES:
            raise ValueError("Invalid EXTRACTION_MODE")
        if self.gpu_policy not in {"resident", "exclusive"}:
            raise ValueError("Invalid GPU_POLICY")
        if self.gpu_policy == "resident" and not self.resident_validated:
            raise ValueError("Resident mode requires RESIDENT_VALIDATED=true after GPU budget validation")
        for name in ("resident_free_mib", "min_free_mib", "queue_size", "per_session",
                     "max_bytes", "max_pixels", "disk_bytes", "ttl_seconds", "startup_timeout",
                     "ocr_timeout", "extraction_timeout", "job_timeout", "cpu_threads"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 1024 <= self.llama_port <= 65535:
            raise ValueError("LLAMA_PORT must be an unprivileged TCP port")

    @classmethod
    def from_env(cls):
        names = {"storage": "STORAGE_DIR", "models": "MODEL_DIR", "ocr_python": "OCR_PYTHON",
                 "llama_binary": "LLAMA_BINARY", "extraction_mode": "EXTRACTION_MODE",
                 "gpu_policy": "GPU_POLICY", "build_revision": "BUILD_REVISION"}
        values = {}
        defaults = cls()
        for field in cls.__dataclass_fields__:
            key = names.get(field, field.upper())
            if key not in os.environ:
                continue
            value = os.environ[key]
            default = getattr(defaults, field)
            if isinstance(default, bool):
                if value.lower() not in {"true", "false"}:
                    raise ValueError(f"{key} must be true or false")
                value = value.lower() == "true"
            elif isinstance(default, int):
                value = int(value)
            elif isinstance(default, Path):
                value = Path(value).expanduser().resolve()
            values[field] = value
        return cls(**values)
