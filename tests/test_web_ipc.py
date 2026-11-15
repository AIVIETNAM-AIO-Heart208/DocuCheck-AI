"""Unicode IPC regression tests without OCR, models, network or subprocesses."""

import io
import json
import threading
import time

import pytest

from docucheck.web.ipc import configure_stdio, message_line, worker_environment


def receipt():
    return {"seller_name":"Joma Bakery café / THỨC COFFEE",
            "seller_address":"22 Quang Trung, P10, Gò Vấp — Đắk Lắk 🧾",
            "transaction_datetime":"2020-08-16T10:36", "total_amount":305000,
            "path":"C:/Người dùng/biên lai.png", "decomposed":"a\u0301"}


@pytest.mark.parametrize("encoding", ["cp1252", "cp1258", "utf-8", "ascii"])
def test_json_frame_preserves_unicode_across_legacy_windows_streams(encoding):
    data=receipt()
    wire=message_line(data)
    assert wire.isascii()
    assert wire.endswith("\n") and wire.count("\n")==1
    assert json.loads(wire.encode(encoding).decode("utf-8"))==data
    with pytest.raises(ValueError):
        message_line({"invalid":float("nan")})


def test_worker_emit_uses_safe_frame_even_on_cp1252_stdout(monkeypatch):
    from docucheck.web.inference_worker import emit
    output=io.BytesIO()
    stream=io.TextIOWrapper(output,encoding="cp1252",errors="strict")
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout",stream)
        emit({"ok":True,"result":receipt()})
    assert json.loads(output.getvalue().decode("utf-8"))["result"]==receipt()


def test_utf8_environment_overrides_inherited_code_page_without_mutating_it():
    original={"PYTHONIOENCODING":"cp1252","PYTHONUTF8":"0","OTHER":"kept"}
    prepared=worker_environment(original)
    assert prepared["PYTHONIOENCODING"]=="utf-8"
    assert prepared["PYTHONUTF8"]=="1"
    assert prepared["OTHER"]=="kept"
    assert original["PYTHONIOENCODING"]=="cp1252"


def test_stdio_explicit_utf8(monkeypatch):
    class Stream:
        def reconfigure(self,**options):
            self.options=options
    streams=[Stream(),Stream(),Stream()]
    with monkeypatch.context() as patch:
        for name,stream in zip(("stdin","stdout","stderr"),streams):
            patch.setattr("sys."+name,stream)
        configure_stdio()
    assert streams[0].options==streams[1].options=={"encoding":"utf-8","errors":"strict"}
    assert streams[2].options=={"encoding":"utf-8","errors":"backslashreplace"}


def test_json_worker_launch_and_request_use_utf8_contract(tmp_path,monkeypatch):
    from docucheck.web.processes import JsonWorker
    stopped=[]
    class Process:
        def __init__(self):
            self.stdin=io.StringIO()
            self.stdout=io.StringIO(message_line({"ok":True,"ready":True}))
        def poll(self):
            return None
    def launch(command,log,**kwargs):
        assert command[1:3]==["-X","utf8"]
        assert kwargs["encoding"]=="utf-8" and kwargs["errors"]=="strict"
        assert kwargs["env"]["PYTHONIOENCODING"]=="utf-8"
        return Process()
    monkeypatch.setattr("docucheck.web.processes.start_process",launch)
    monkeypatch.setattr("docucheck.web.processes.stop_process",lambda process:stopped.append(process))
    worker=JsonWorker("not-executed","extract",tmp_path,"refined",tmp_path/"worker.log",
                      threading.Event(),time.monotonic()+5,{"PYTHONIOENCODING":"cp1252"})
    worker.reader.join(timeout=1)
    def response(cancel,deadline):
        wire=worker.process.stdin.getvalue()
        assert wire.isascii()
        request=json.loads(wire)
        assert request["directory"]=="C:/Người dùng/biên lai"
        return {"ok":True,"request_id":request["request_id"],"result":receipt()}
    worker.receive=response
    assert worker.request({"directory":"C:/Người dùng/biên lai"},threading.Event(),time.monotonic()+5)==receipt()
    worker.close()
    assert len(stopped)==1
