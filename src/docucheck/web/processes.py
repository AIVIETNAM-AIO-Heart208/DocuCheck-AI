"""Bounded JSON-line IPC; only the coordinator owns and stops child processes."""

import json
import logging
import os
import queue
import signal
import subprocess
import threading
import time
import uuid

from .ipc import message_line, worker_environment

log = logging.getLogger(__name__)


class Cancelled(RuntimeError):
    pass


def checkpoint(cancel, deadline):
    if cancel.is_set():
        raise Cancelled("cancelled")
    if time.monotonic() >= deadline:
        raise TimeoutError("stage_timeout")


def start_process(command, log, **kwargs):
    options = {"creationflags":subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session":True}
    return subprocess.Popen(command, stderr=log, **options, **kwargs)


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait(timeout=10)
            return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=10)


class JsonWorker:
    def __init__(self, python, role, models, mode, log_path, cancel, deadline, env):
        self.log = log_path.open("a", encoding="utf-8")
        try:
            self.process = start_process([python, "-X", "utf8", "-m", "docucheck.web.inference_worker", role,
                                          "--models", str(models), "--mode", mode], self.log,
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         text=True, encoding="utf-8", errors="strict", bufsize=1,
                                         env=worker_environment(env))
        except OSError:
            self.log.close()
            raise
        self.messages = queue.Queue(maxsize=2)

        def read():
            try:
                while True:
                    line = self.process.stdout.readline(64 * 1024 * 1024)
                    if not line:
                        break
                    if not line.endswith("\n"):
                        raise ValueError("Worker response exceeds IPC limit")
                    self.messages.put(json.loads(line))
            except (OSError, ValueError) as error:
                log.exception("Worker IPC read failed (%s)", type(error).__name__)
                self.messages.put({"ok":False, "code":type(error).__name__, "source":"ipc"})

        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        try:
            hello = self.receive(cancel, deadline)
            if not hello.get("ready"):
                raise RuntimeError("worker_start_failed")
            self.info = hello
        except BaseException:
            self.close()
            raise

    def receive(self, cancel, deadline):
        while True:
            checkpoint(cancel, deadline)
            try:
                response = self.messages.get(timeout=.1)
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError("worker_exited")
                continue
            if not response.get("ok"):
                prefix = "ipc_" if response.get("source") == "ipc" else "worker_"
                raise RuntimeError(prefix + response.get("code", "failed"))
            return response

    def request(self, payload, cancel, deadline):
        key = uuid.uuid4().hex
        self.process.stdin.write(message_line({**payload, "request_id":key}))
        self.process.stdin.flush()
        response = self.receive(cancel, deadline)
        if response.get("request_id") != key:
            raise RuntimeError("worker_response_mismatch")
        return response["result"]

    def close(self):
        try:
            stop_process(self.process)
        finally:
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()
            self.log.close()
