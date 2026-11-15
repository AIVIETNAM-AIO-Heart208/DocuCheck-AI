"""Optional web tests; mock engine only. Never starts OCR/Qwen or CUDA."""

import io
import threading
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from PIL import Image

from docucheck.web.api import create_app
from docucheck.web.processes import Cancelled
from docucheck.web.settings import Settings


class FakeEngine:
    def __init__(self):
        self.active=0
        self.maximum=0
        self.loads={"fake":0}
        self.release=threading.Event()
        self.release.set()
        self.fail=False

    def preflight(self):
        pass

    def close(self):
        pass

    def run(self,job,directory,progress,cancel):
        self.active+=1
        self.maximum=max(self.maximum,self.active)
        try:
            progress("ocr")
            while not self.release.wait(.02):
                if cancel.is_set():
                    raise Cancelled("cancelled")
            if self.fail:
                raise RuntimeError("private-host-path-must-not-leak")
            result={"seller_name":"THỨC COFFEE","seller_address":None,
                    "transaction_datetime":"2020-01-01","total_amount":0}
            return {"result":result,"fields":{key:{"value":value,"status":"ok","issues":[],
                    "ocr_confidence":.9,"polygons":[],"precision":None} for key,value in result.items()},
                    "state":"succeeded","timing":{},"model_load_count":{}}
        finally:
            self.active-=1


def picture():
    stream=io.BytesIO()
    Image.new("RGB",(20,30)).save(stream,format="PNG")
    return stream.getvalue()


def wait(client,key):
    until=time.monotonic()+5
    while time.monotonic()<until:
        response=client.get(f"/api/jobs/{key}")
        response.raise_for_status()
        body=response.json()
        if body["state"] in {"succeeded","partial","failed","cancelled"}:
            return body
        time.sleep(.01)
    raise AssertionError("Fake job did not finish")


def connect(tmp_path,engine):
    return TestClient(create_app(Settings(storage=tmp_path),engine))


def ready(client):
    client.get("/api/session")
    for _ in range(100):
        if client.get("/health/ready").status_code==200:
            return
        time.sleep(.01)
    raise AssertionError("Fake coordinator not ready")


def submit(client,key="test-key-123"):
    return client.post("/api/jobs",files={"file":("../../bad-name.png",picture(),"image/png")},headers={"Idempotency-Key":key})


def test_result_review_download_and_no_cross_session(tmp_path):
    with connect(tmp_path,FakeEngine()) as client:
        ready(client)
        response=submit(client)
        assert response.status_code==202
        key=response.json()["job_id"]
        assert submit(client).json()["job_id"]==key
        job=wait(client,key)
        values=job["result"]
        assert values["total_amount"]==0
        assert client.get(f"/api/jobs/{key}/download").headers["cache-control"]=="no-store"
        assert set(client.get(f"/api/jobs/{key}/download").json())==set(values)
        assert client.get(f"/api/jobs/{key}/download?version=reviewed").status_code==409
        draft=client.put(f"/api/jobs/{key}/review",json={"values":values,"revision":0,"confirmed":False})
        assert draft.status_code==200
        confirmed=client.put(f"/api/jobs/{key}/review",json={"values":values,"revision":1,"confirmed":True})
        assert confirmed.json()["review"]["confirmed"]
        reviewed=client.get(f"/api/jobs/{key}/download?version=reviewed")
        assert reviewed.json()==values
        assert reviewed.headers["cache-control"]=="no-store"
        client.cookies.clear()
        client.get("/api/session")
        assert client.get(f"/api/jobs/{key}").status_code==404


def test_status_remains_responsive_and_cancel_releases_gpu_owner(tmp_path):
    engine=FakeEngine()
    engine.release.clear()
    with connect(tmp_path,engine) as client:
        ready(client)
        key=submit(client).json()["job_id"]
        until=time.monotonic()+2
        while not engine.active and time.monotonic()<until:
            time.sleep(.01)
        assert client.get("/health/live").status_code==200
        assert client.post(f"/api/jobs/{key}/cancel").status_code==200
        assert wait(client,key)["state"]=="cancelled"
        assert engine.active==0
        assert engine.maximum==1


def test_failure_has_no_previous_receipt_and_bad_upload(tmp_path):
    engine=FakeEngine()
    with connect(tmp_path,engine) as client:
        ready(client)
        first=submit(client).json()["job_id"]
        wait(client,first)
        engine.fail=True
        second=submit(client,"second-key").json()["job_id"]
        job=wait(client,second)
        assert job["state"]=="failed" and job["result"] is None
        assert "private-host-path" not in job["error"]["message"]
        assert client.get(f"/api/jobs/{second}/download").status_code==409
        bad=client.post("/api/jobs",files={"file":("bad.png",b"not-image","image/png")},headers={"Idempotency-Key":"bad-file-key"})
        assert bad.status_code==422
        forbidden=client.post("/api/jobs",headers={"Origin":"https://other.example","Idempotency-Key":"other-key"})
        assert forbidden.status_code==403


def test_review_validation_rejects_timezone_and_boolean_amount():
    from docucheck.web.api import ReceiptValues
    from pydantic import ValidationError
    values={"seller_name":None,"seller_address":None,"transaction_datetime":"2020-01-01","total_amount":0}
    with pytest.raises(ValidationError):
        ReceiptValues(**{**values,"total_amount":True})
    with pytest.raises(ValidationError):
        ReceiptValues(**{**values,"transaction_datetime":"2020-01-01T12:00+07:00"})


def test_bounded_queue_and_queued_cancellation(tmp_path):
    engine=FakeEngine()
    engine.release.clear()
    app=create_app(Settings(storage=tmp_path,queue_size=1,per_session=3),engine)
    with TestClient(app) as client:
        ready(client)
        first=submit(client,"first-key").json()["job_id"]
        until=time.monotonic()+2
        while not engine.active and time.monotonic()<until:
            time.sleep(.01)
        second=submit(client,"second-key")
        assert second.status_code==202
        assert submit(client,"third-key").status_code==429
        queued=second.json()["job_id"]
        assert client.post(f"/api/jobs/{queued}/cancel").json()["state"]=="cancelled"
        client.post(f"/api/jobs/{first}/cancel")
        assert wait(client,first)["state"]=="cancelled"
        assert engine.maximum==1


def test_upload_limits_before_inference(tmp_path):
    app=create_app(Settings(storage=tmp_path,max_bytes=10),FakeEngine())
    with TestClient(app) as client:
        ready(client)
        assert submit(client).status_code==413
        assert client.post("/api/jobs",content=b"",headers={"Content-Length":"999999999"}).status_code==413


def test_preflight_failure_keeps_ui_alive_but_rejects_jobs(tmp_path):
    class NotReady(FakeEngine):
        def preflight(self):
            raise RuntimeError("missing model fixture")
    with connect(tmp_path,NotReady()) as client:
        client.get("/api/session")
        assert client.get("/health/live").status_code==200
        assert client.get("/health/ready").status_code==503
        assert submit(client).status_code==503
