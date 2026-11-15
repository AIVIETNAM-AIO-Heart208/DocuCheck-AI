"""One inference owner and bounded durable queue, responsive to status/cancel."""

import asyncio
import logging
import json
import os
import threading
import time
import traceback

from .processes import Cancelled

log = logging.getLogger(__name__)


def failure_details(error):
    """Only known error identifiers are public; paths/tracebacks stay local."""
    known = {
        "llama_port_unavailable": "Cổng nội bộ Qwen chưa khả dụng. Khởi động lại ứng dụng; nếu lỗi lặp lại, kiểm tra tiến trình đang dùng cổng trên máy chủ.",
        "worker_ContextBudgetExceeded": "Biên lai có quá nhiều nội dung cho giới hạn xử lý hiện tại. Hãy dùng ảnh chỉ chứa biên lai, bỏ nền hoặc giấy tờ bên cạnh, rồi thử lại.",
        "full_cuda_offload_not_verified": "Chưa xác nhận được Qwen đã nạp đầy đủ lên GPU. Kiểm tra log khởi động Qwen trên máy chủ.",
        "llama_start_failed": "Qwen không khởi động được. Kiểm tra runtime CUDA và model trên máy chủ.",
        "resident_gpu_budget_unavailable": "VRAM trống chưa đủ cho chế độ resident. Dùng exclusive hoặc giải phóng GPU.",
        "insufficient_gpu_headroom": "GPU không còn đủ bộ nhớ trống để nạp bộ xử lý.",
        "worker_OutOfMemoryError": "Bộ xử lý hết bộ nhớ GPU. Giải phóng GPU hoặc dùng chế độ exclusive.",
        "worker_ModuleNotFoundError": "Môi trường inference thiếu thư viện. Kiểm tra log worker trên máy chủ.",
        "storage_quota": "Kho lưu trữ tạm đã đầy. Kiểm tra dữ liệu demo trên máy chủ.",
        "ipc_UnicodeDecodeError": "Không đọc được kết quả worker do encoding. Khởi động lại web sau khi cập nhật bản sửa UTF-8.",
        "worker_UnicodeDecodeError": "Worker gặp lỗi đọc văn bản. Kiểm tra file UTF-8 và log extraction trên máy chủ.",
    }
    identifier = str(error)
    if identifier in known:
        return {"code":identifier, "message":known[identifier]}
    if isinstance(error, TimeoutError):
        return {"code":"timeout", "message":"Bước xử lý vượt thời gian cho phép. Hãy kiểm tra log máy chủ."}
    return {"code":"inference_failed", "message":"Xử lý thất bại. Kiểm tra model/GPU hoặc gửi lại ảnh; kết quả cũ không được dùng lại."}


class InstanceLock:
    def __init__(self, root):
        self.stream = (root / "server.lock").open("a+b")
        self.stream.seek(0)
        self.stream.write(b"0")
        self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError("Another web worker owns this storage; use exactly one Uvicorn worker")

    def close(self):
        self.stream.close()


class Coordinator:
    def __init__(self, settings, store, engine):
        self.settings, self.store, self.engine = settings, store, engine
        self.ready = False
        self.error = None
        self.wake = asyncio.Event()
        self.admission = asyncio.Lock()
        self.stopping = False
        self.current_id = None
        self.current_cancel = None
        self.task = None
        self.instance = None

    async def start(self):
        self.instance = InstanceLock(self.store.root)
        await asyncio.to_thread(self.store.interrupted)
        self.task = asyncio.create_task(self.loop())

    async def stop(self):
        self.stopping = True
        if self.current_cancel:
            self.current_cancel.set()
        self.wake.set()
        if self.task:
            await self.task  # Do not cancel a thread while it still owns GPU processes.
        if self.instance:
            self.instance.close()

    def cancel(self, key):
        if self.current_id == key and self.current_cancel:
            self.current_cancel.set()
        self.wake.set()

    async def loop(self):
        try:
            await asyncio.to_thread(self.engine.preflight)
            self.ready = True
            while not self.stopping:
                self.wake.clear()
                await asyncio.to_thread(self.store.prune, self.settings.ttl_seconds)
                job = await asyncio.to_thread(self.store.claim)
                if job is None:
                    try:
                        await asyncio.wait_for(self.wake.wait(), timeout=10)
                    except asyncio.TimeoutError:
                        pass
                    continue
                self.current_id = job["id"]
                cancel = self.current_cancel = threading.Event()
                if self.store.get(job["id"])["state"] == "cancel_requested":
                    cancel.set()

                def progress(stage):
                    with self.store.lock:
                        latest = self.store.get(job["id"])
                        if latest["state"] == "cancel_requested":
                            cancel.set()
                        if cancel.is_set():
                            raise Cancelled("cancelled")
                        self.store.update(job["id"], state=stage, stage=stage)

                try:
                    if self.store.disk_usage() >= self.settings.disk_bytes:
                        raise RuntimeError("storage_quota")
                    result = await asyncio.to_thread(self.engine.run, job, self.store.directory(job["id"]), progress, cancel)
                    with self.store.lock:
                        latest = self.store.get(job["id"])
                        if cancel.is_set() or latest["state"] == "cancel_requested":
                            raise Cancelled("cancelled")
                        result["timing"]["queue_wait_seconds"] = job["started"]-job["created"]
                        result["timing"]["submission_to_completion_seconds"] = time.time()-job["created"]
                        self.store.update(job["id"], **result, stage=result["state"], finished=time.time())
                except Cancelled:
                    self.store.update(job["id"], state="cancelled", stage="cancelled", finished=time.time())
                except Exception as error:
                    log.exception("Job %s failed (%s)", job["id"], type(error).__name__)
                    details = failure_details(error)
                    failure_path = self.store.directory(job["id"]) / "failure.json"
                    try:
                        failure_path.write_text(json.dumps({"public_error":details, "exception_type":type(error).__name__,
                            "detail":str(error), "traceback":traceback.format_exc()}, ensure_ascii=False, indent=2), encoding="utf-8")
                    except OSError:
                        log.exception("Could not persist job failure diagnostics")
                    self.store.update(job["id"], state="failed", stage="failed", finished=time.time(),
                        error=details)
                    if getattr(self.engine, "cleanup_failed", False):
                        raise RuntimeError("GPU cleanup failed; rejecting further jobs") from error
                finally:
                    self.current_id = self.current_cancel = None
        except Exception:
            self.error = "Dịch vụ chưa sẵn sàng. Kiểm tra model bundle, GPU và log máy chủ."
            await asyncio.to_thread(self.store.interrupted, "Dịch vụ inference không còn sẵn sàng; hãy kiểm tra máy chủ trước khi gửi lại.")
            log.exception("Inference coordinator unavailable")
        finally:
            self.ready = False
            await asyncio.to_thread(self.engine.close)
