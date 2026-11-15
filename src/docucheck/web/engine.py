"""GPU lifecycle without invoking the per-image demonstration CLI."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from .processes import JsonWorker, checkpoint, start_process, stop_process
from .ipc import worker_environment
from .settings import ROOT


class InferenceEngine:
    def __init__(self, settings):
        self.settings = settings
        self.ocr = self.extraction = self.llama = self.llama_log = None
        self.loads = {"ocr":0, "qwen":0, "extraction_worker":0}
        self.manifest = None
        self.provenance = {}
        self.cleanup_failed = False
        self.log_root = settings.storage / "engine_logs"
        self.log_root.mkdir(parents=True, exist_ok=True)

    def gpu(self):
        import psutil
        text = subprocess.check_output(["nvidia-smi", "--id=0", "--query-gpu=memory.used,memory.free",
                                        "--format=csv,noheader,nounits"], text=True, timeout=10)
        used, free = [int(v.strip()) for v in text.strip().split(",")]
        process = psutil.Process()
        rss = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                rss += child.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        return {"used_mib":used, "free_mib":free, "sampled_at":time.time(), "sampled_process_tree_rss_bytes":rss}

    def preflight(self):
        if not (Path(self.settings.llama_binary).is_file() or shutil.which(self.settings.llama_binary)):
            raise ValueError("Missing llama-server binary; see WEB_DEMO.md")
        manifest_path = self.settings.models / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = {"qwen/model.gguf", "phocr/ch_PP-OCRv5_server_det.onnx",
                    "vietocr/vgg_transformer.pth", "vietocr/config.yml"}
        entries = {entry["path"]:entry for entry in manifest["files"]}
        if not required <= set(entries):
            raise ValueError("Incomplete offline model bundle")
        for name in required:
            path = (self.settings.models / name).resolve()
            if not path.is_relative_to(self.settings.models.resolve()):
                raise ValueError("Unsafe model manifest path")
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != entries[name]["sha256"]:
                raise ValueError("Model bundle checksum mismatch")
        expected = json.loads((ROOT / "configs/qwen3_4b_q4_k_m.json").read_text(encoding="utf-8"))["sha256"]
        if entries["qwen/model.gguf"]["sha256"] != expected:
            raise ValueError("Wrong Qwen GGUF")
        # Avoid importing NumPy/OpenCV/PHOCR into the lightweight API process.
        expected_phocr = "0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad"
        if entries["phocr/ch_PP-OCRv5_server_det.onnx"]["sha256"] != expected_phocr:
            raise ValueError("Wrong PHOCR model")
        self.manifest = manifest
        files = [*(ROOT / "src/docucheck/extraction").glob("*.py"),
                 *(ROOT / "src/docucheck/ocr").glob("*.py"),
                 *(ROOT / "src/docucheck/web").glob("*.py"), ROOT / "configs/qwen3_4b_q4_k_m.json"]
        self.provenance = {"build_revision":self.settings.build_revision,
            "source_sha256":{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
            "model_checksums_verified":True, "accuracy_verified":False}
        self.gpu()

    def env(self):
        return worker_environment({**os.environ, "PYTHONPATH":str(ROOT / "src"),
                "OMP_NUM_THREADS":str(self.settings.cpu_threads),
                "OPENBLAS_NUM_THREADS":str(self.settings.cpu_threads), "CUDA_VISIBLE_DEVICES":"0"})

    def _new_worker(self, role, cancel, deadline):
        path = self.log_root / f"{role}.log"
        self._rotate(path)
        return JsonWorker(self.settings.ocr_python if role == "ocr" else sys.executable,
                          role, self.settings.models, self.settings.extraction_mode, path,
                          cancel, min(deadline, time.monotonic()+self.settings.startup_timeout), self.env())

    @staticmethod
    def _rotate(path):
        if path.exists() and path.stat().st_size > 5 * 1024**2:
            path.replace(path.with_suffix(".previous.log"))

    def _close_ocr(self):
        if self.ocr:
            self.ocr.close()
            self.ocr = None

    def _close_llama(self):
        if self.llama:
            stop_process(self.llama)
            self.llama = None
        if self.llama_log:
            self.llama_log.close()
            self.llama_log = None

    def close(self):
        # Called only by the owning inference thread, after its stage unwinds.
        def close_extraction():
            if self.extraction:
                self.extraction.close()
                self.extraction = None
        errors = []
        for action in (self._close_ocr, close_extraction, self._close_llama):
            try:
                action()
            except Exception as error:
                errors.append(error)
        if errors:
            self.cleanup_failed = True
            raise RuntimeError("gpu_cleanup_failed") from errors[0]

    def _wait_release(self, previous_free, cancel, deadline):
        until = min(deadline, time.monotonic()+15)
        while self.gpu()["free_mib"] < previous_free - 256:
            checkpoint(cancel, until)
            time.sleep(.15)

    def _start_llama(self, cancel, deadline):
        if self.llama and self.llama.poll() is None:
            return
        self._close_llama()
        with socket.socket() as probe:
            # Linux retains accepted connections in TIME_WAIT after an exclusive
            # job stops its server. Match the server's reusable-address bind;
            # an actual active listener still fails (SO_REUSEPORT is not used).
            # Do not enable Windows SO_REUSEADDR: its ownership semantics differ.
            if os.name != "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", self.settings.llama_port))
            except OSError as error:
                raise RuntimeError("llama_port_unavailable") from error
        if self.gpu()["free_mib"] < self.settings.min_free_mib:
            raise RuntimeError("insufficient_gpu_headroom")
        log_path = self.log_root / "llama.log"
        self._rotate(log_path)
        self.llama_log = log_path.open("a", encoding="utf-8")
        offset = log_path.stat().st_size
        self.llama = start_process([self.settings.llama_binary, "-m", str(self.settings.models / "qwen/model.gguf"),
            "-ngl", "99", "-c", "8192", "-np", "1", "-b", "256", "-ub", "128",
            "-t", str(self.settings.cpu_threads), "--host", "127.0.0.1", "--port", str(self.settings.llama_port),
            # Match the existing CLI: model-loader offload diagnostics are not
            # present at verbosity 3 in the pinned b12345 Windows build.
            "--jinja", "-lv", "4"], self.llama_log, stdout=self.llama_log, env=self.env())
        until = min(deadline, time.monotonic()+self.settings.startup_timeout)
        while True:
            checkpoint(cancel, until)
            if self.llama.poll() is not None:
                raise RuntimeError("llama_start_failed")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.settings.llama_port}/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.2)
        self.llama_log.flush()
        with log_path.open("r", encoding="utf-8", errors="replace") as stream:
            stream.seek(offset)
            text = stream.read()
        matches = re.findall(r"offloaded (\d+)/(\d+) layers", text)
        if not matches or any(a != b or int(a) == 0 for a,b in matches):
            raise RuntimeError("full_cuda_offload_not_verified")
        self.loads["qwen"] += 1

    def run(self, job, directory, progress, cancel):
        started = time.monotonic()
        deadline = started + self.settings.job_timeout
        timing, samples = {}, []
        before_loads = dict(self.loads)
        record = {"image_id":job["id"], "image_path":"image.png", "split":"web",
                  "source_subset":"web_upload", "image_width":job["image"]["width"],
                  "image_height":job["image"]["height"], "regions":[]}
        (directory / "manifest.jsonl").write_text(json.dumps(record, ensure_ascii=False)+"\n", encoding="utf-8")
        try:
            progress("loading")
            checkpoint(cancel, deadline)
            if self.settings.gpu_policy == "exclusive":
                self._close_llama()
            elif self.ocr is None and self.llama is None:
                if self.gpu()["free_mib"] < self.settings.resident_free_mib:
                    raise RuntimeError("resident_gpu_budget_unavailable")
            samples.append(self.gpu())
            load_started = time.monotonic()
            if self.ocr is None:
                if samples[-1]["free_mib"] < self.settings.min_free_mib:
                    raise RuntimeError("insufficient_gpu_headroom")
                self.ocr = self._new_worker("ocr", cancel, deadline)
                self.loads["ocr"] += 1
            timing["ocr_load_seconds"] = time.monotonic()-load_started
            progress("ocr")
            stage_started = time.monotonic()
            ocr = self.ocr.request({"directory":str(directory), "record":record}, cancel,
                                   min(deadline, stage_started+self.settings.ocr_timeout))
            timing["ocr_seconds"] = time.monotonic()-stage_started
            samples.append(self.gpu())
            progress("loading")
            if self.settings.gpu_policy == "exclusive":
                baseline_free = samples[0]["free_mib"]
                self._close_ocr()
                self._wait_release(baseline_free, cancel, deadline)
            load_started = time.monotonic()
            self._start_llama(cancel, deadline)
            if self.extraction is None:
                self.extraction = self._new_worker("extract", cancel, deadline)
                self.loads["extraction_worker"] += 1
            timing["qwen_load_seconds"] = time.monotonic()-load_started
            progress("extracting")
            stage_started = time.monotonic()
            extraction = self.extraction.request({"directory":str(directory), "record":record,
                "base_url":f"http://127.0.0.1:{self.settings.llama_port}",
                "http_timeout":self.settings.extraction_timeout}, cancel,
                min(deadline, stage_started+self.settings.extraction_timeout))
            checkpoint(cancel, deadline)
            timing["extraction_seconds"] = time.monotonic()-stage_started
            timing["worker_total_seconds"] = time.monotonic()-started
            samples.append(self.gpu())
            result = {key:value["value_normalized"] for key,value in extraction["fields"].items()}
            public_fields = {key:{"value":value["value_normalized"], "status":value["status"],
                "issues":value["issues"], "ocr_confidence":value["ocr_confidence"],
                "precision":value.get("precision"),
                "polygons":[e["polygon"] for e in value["evidence"]]}
                for key,value in extraction["fields"].items()}
            runtime = {"mode":self.settings.extraction_mode, "gpu_policy":self.settings.gpu_policy,
                "timing":timing, "gpu_samples":samples, "peak_sampled_system_gpu_mib":max(v["used_mib"] for v in samples),
                "model_load_count":dict(self.loads), "job_load_count":{k:self.loads[k]-v for k,v in before_loads.items()},
                "build_revision":self.settings.build_revision, "usage":extraction.get("usage"),
                "model_manifest":self.manifest, "provenance":self.provenance,
                "image_normalization":job["image"]}
            (directory / "runtime.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
            (directory / "receipt.ai.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            partial = ocr["partial"] or any(v["status"] != "ok" for v in public_fields.values())
            return {"result":result, "fields":public_fields, "timing":timing,
                    "resource_samples":samples, "job_load_count":runtime["job_load_count"],
                    "model_load_count":dict(self.loads), "state":"partial" if partial else "succeeded"}
        except BaseException:
            self.close()
            raise
