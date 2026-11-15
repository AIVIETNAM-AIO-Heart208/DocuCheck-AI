"""Lifecycle contracts using fake IPC workers; no subprocess/model is started."""

import threading
import uuid
from types import SimpleNamespace

import pytest

from docucheck.web.engine import InferenceEngine
from docucheck.web.processes import Cancelled
from docucheck.web.settings import Settings


def test_posix_port_probe_allows_reuse_but_reports_active_listener(tmp_path, monkeypatch):
    """Fake socket verifies reuse is set before bind, no process is started."""
    import socket
    import time
    engine = InferenceEngine(Settings(storage=tmp_path))
    calls = []

    class Probe:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def setsockopt(self, level, option, value):
            calls.append((level, option, value))
        def bind(self, address):
            assert calls == [(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]
            raise OSError(98, "Address already in use")

    monkeypatch.setattr("docucheck.web.engine.os", SimpleNamespace(name="posix"))
    monkeypatch.setattr("docucheck.web.engine.socket.socket", Probe)
    with pytest.raises(RuntimeError, match="llama_port_unavailable"):
        engine._start_llama(threading.Event(), time.monotonic()+10)
    assert engine.llama is None


@pytest.mark.parametrize("policy,expected", [("resident",1),("exclusive",2)])
def test_two_jobs_model_load_counts(tmp_path,monkeypatch,policy,expected):
    settings=Settings(storage=tmp_path,gpu_policy=policy,resident_validated=policy=="resident")
    engine=InferenceEngine(settings)
    engine.manifest={}
    monkeypatch.setattr(engine,"gpu",lambda:{"used_mib":0,"free_mib":8000,"sampled_at":0})
    class Worker:
        def __init__(self,role):
            self.role=role
            self.closed=False
        def close(self):
            self.closed=True
        def request(self,payload,cancel,deadline):
            assert not self.closed
            if self.role=="ocr":
                return {"partial":False}
            return {"fields":{key:{"value_normalized":value,"status":"ok","issues":[],
                    "ocr_confidence":None,"evidence":[]} for key,value in {
                    "seller_name":"SHOP","seller_address":"Road","transaction_datetime":"2020-01-01","total_amount":0}.items()}}
    monkeypatch.setattr(engine,"_new_worker",lambda role,*args:Worker(role))
    monkeypatch.setattr(engine,"_close_llama",lambda:setattr(engine,"llama",None))
    def start(*args):
        if engine.llama is None:
            engine.llama=object()
            engine.loads["qwen"]+=1
    monkeypatch.setattr(engine,"_start_llama",start)
    for _ in range(2):
        key=str(uuid.uuid4())
        directory=tmp_path/key
        directory.mkdir()
        result=engine.run({"id":key,"image":{"width":20,"height":30}},directory,lambda stage:None,threading.Event())
        assert result["result"]["total_amount"]==0
    assert engine.loads["ocr"]==engine.loads["qwen"]==expected
    assert engine.loads["extraction_worker"]==1
    engine.close()


def test_cancellation_before_work_closes_owned_workers(tmp_path,monkeypatch):
    engine=InferenceEngine(Settings(storage=tmp_path))
    cancel=threading.Event()
    cancel.set()
    calls=[]
    monkeypatch.setattr(engine,"close",lambda:calls.append("close"))
    with pytest.raises(Cancelled):
        engine.run({"id":"unused","image":{"width":1,"height":1}},tmp_path,lambda stage:None,cancel)
    assert calls==["close"]


def test_missing_binary_fails_before_any_gpu_command(tmp_path,monkeypatch):
    engine=InferenceEngine(Settings(storage=tmp_path,llama_binary="missing-docucheck-llama-binary"))
    monkeypatch.setattr("docucheck.web.engine.shutil.which",lambda _:None)
    def unexpected_gpu():
        raise AssertionError("GPU was queried before binary validation")
    monkeypatch.setattr(engine,"gpu",unexpected_gpu)
    with pytest.raises(ValueError,match="Missing llama-server"):
        engine.preflight()


@pytest.mark.parametrize("offload_line,accepted", [
    ("load_tensors: offloaded 37/37 layers to GPU\n",True),
    ("load_tensors: offloaded 0/37 layers to GPU\n",False),
    ("server: model loaded\n",False),
])
def test_llama_start_uses_diagnostic_verbosity_and_requires_full_offload(tmp_path,monkeypatch,offload_line,accepted):
    """No socket/process/network: exercise the startup check with saved-log text."""
    engine=InferenceEngine(Settings(storage=tmp_path))
    monkeypatch.setattr(engine,"gpu",lambda:{"free_mib":8000})
    class Socket:
        def setsockopt(self, level, option, value):
            assert value == 1
        def __enter__(self):
            return self
        def __exit__(self,*args):
            pass
        def bind(self,address):
            assert address[0]=="127.0.0.1"
    class Response:
        status=200
        def __enter__(self):
            return self
        def __exit__(self,*args):
            pass
    class Process:
        def poll(self):
            return None
    def start(command,log,**kwargs):
        assert command[command.index("-lv")+1]=="4"
        assert command[command.index("-ngl")+1]=="99"
        log.write(offload_line)
        log.flush()
        return Process()
    monkeypatch.setattr("docucheck.web.engine.socket.socket",Socket)
    monkeypatch.setattr("docucheck.web.engine.urllib.request.urlopen",lambda *a,**kw:Response())
    monkeypatch.setattr("docucheck.web.engine.start_process",start)
    import time
    try:
        if accepted:
            engine._start_llama(threading.Event(),time.monotonic()+10)
            assert engine.loads["qwen"]==1
        else:
            with pytest.raises(RuntimeError,match="full_cuda_offload_not_verified"):
                engine._start_llama(threading.Event(),time.monotonic()+10)
            assert engine.loads["qwen"]==0
    finally:
        if engine.llama_log:
            engine.llama_log.close()
