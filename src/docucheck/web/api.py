"""Same-origin local demo API; all inference runs outside the event loop."""

import asyncio
from contextlib import asynccontextmanager
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
from typing import Literal
from urllib.parse import urlsplit
import uuid

from fastapi import FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, StrictInt, field_validator

from docucheck.extraction.contracts import FIELDS

from .coordinator import Coordinator
from .body_limit import BodyLimit
from .engine import InferenceEngine
from .settings import Settings
from .storage import Capacity, Conflict, Store
from .uploads import normalize_upload

STATIC = Path(__file__).with_name("static")


class ReceiptValues(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seller_name: str | None
    seller_address: str | None
    transaction_datetime: str | None
    total_amount: StrictInt | None

    @field_validator("seller_name", "seller_address")
    @classmethod
    def text(cls, value):
        if value is not None and (not value.strip() or len(value) > 2000):
            raise ValueError("Use null for missing text; max 2000 characters")
        return value.strip() if value else None

    @field_validator("transaction_datetime")
    @classmethod
    def date(cls, value):
        if value is None:
            return None
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?", value):
            raise ValueError("Use ISO date or local datetime without timezone")
        dt.datetime.fromisoformat(value)
        return value

    @field_validator("total_amount")
    @classmethod
    def amount(cls, value):
        if value is not None and abs(value) > 9_007_199_254_740_991:
            raise ValueError("Amount exceeds exact integer range supported by this demo")
        return value


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: ReceiptValues
    revision: StrictInt
    confirmed: bool = False

    @field_validator("revision")
    @classmethod
    def valid_revision(cls, value):
        if value < 0:
            raise ValueError("Revision must be nonnegative")
        return value


def owner(request):
    cookie = request.cookies.get("docucheck_session", "")
    if not re.fullmatch(r"[a-f0-9]{64}", cookie):
        raise HTTPException(401, "Khởi tạo phiên bằng trang chủ trước.")
    return hashlib.sha256(cookie.encode()).hexdigest()


def create_app(settings=None, engine=None):
    settings = settings or Settings.from_env()
    store = Store(settings.storage)
    coordinator = Coordinator(settings, store, engine or InferenceEngine(settings))

    @asynccontextmanager
    async def lifespan(app):
        await coordinator.start()
        try:
            yield
        finally:
            await coordinator.stop()

    app = FastAPI(title="DocuCheck AI", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.coordinator, app.state.store = coordinator, store
    app.add_middleware(BodyLimit, max_bytes=settings.max_bytes + 1024*1024)

    @app.middleware("http")
    async def same_origin(request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            parsed = urlsplit(origin)
            if parsed.netloc != request.headers.get("host") or parsed.scheme != request.url.scheme:
                return JSONResponse({"detail":"Nguồn request không hợp lệ."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; object-src 'none'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def job_for(key, request):
        try:
            uuid.UUID(key)
            return store.get(key, owner(request))
        except (KeyError, ValueError):
            raise HTTPException(404, "Không tìm thấy tác vụ trong phiên này.")

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/session")
    async def session(request: Request, response: Response):
        cookie = request.cookies.get("docucheck_session", "")
        if not re.fullmatch(r"[a-f0-9]{64}", cookie):
            response.set_cookie("docucheck_session", secrets.token_hex(32), httponly=True,
                                samesite="strict", secure=settings.cookie_secure, max_age=7*86400)
        return {"max_bytes":settings.max_bytes, "max_pixels":settings.max_pixels,
                "retention_hours":settings.ttl_seconds/3600}

    @app.get("/health/live")
    async def live():
        return {"status":"alive"}

    @app.get("/health/ready")
    async def ready():
        return JSONResponse({"ready":coordinator.ready, "busy":coordinator.current_id is not None,
            "model_state":"loaded_or_lazy", "gpu_policy":settings.gpu_policy,
            "models_loaded":{"ocr":getattr(coordinator.engine,"ocr",None) is not None,
                             "qwen":getattr(coordinator.engine,"llama",None) is not None},
            "extraction_mode":settings.extraction_mode, "message":coordinator.error,
            "load_count":dict(getattr(coordinator.engine, "loads", {}))},
            status_code=200 if coordinator.ready else 503)

    @app.post("/api/jobs", status_code=202)
    async def submit(request: Request, file: UploadFile = File(...),
                     idempotency_key: str = Header(..., alias="Idempotency-Key")):
        session_owner = owner(request)
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", idempotency_key):
            raise HTTPException(422, "Idempotency-Key không hợp lệ.")
        if not coordinator.ready:
            raise HTTPException(503, "Dịch vụ đang chuẩn bị hoặc chưa đủ điều kiện chạy GPU.")
        async with coordinator.admission:
            existing = await asyncio.to_thread(store.find_token, session_owner, idempotency_key)
            if existing:
                await file.close()
                return {"job_id":existing["id"], "status_url":f"/api/jobs/{existing['id']}"}
            await asyncio.to_thread(store.prune, settings.ttl_seconds)
            usage = await asyncio.to_thread(store.disk_usage)
            # Reserve enough headroom for decoding an uncompressed RGB image and artifacts.
            if usage + settings.max_pixels*4 + settings.max_bytes > settings.disk_bytes:
                raise HTTPException(503, "Kho lưu trữ tạm đã đầy.")
            key = str(uuid.uuid4())
            directory = store.directory(key)
            directory.mkdir()
            temporary = directory / "upload.bin"
            created = False
            try:
                total = 0
                with temporary.open("wb") as stream:
                    while chunk := await file.read(1024*1024):
                        total += len(chunk)
                        if total > settings.max_bytes:
                            raise HTTPException(413, "Ảnh vượt giới hạn dung lượng.")
                        await asyncio.to_thread(stream.write, chunk)
                decoding = asyncio.create_task(asyncio.to_thread(normalize_upload, temporary, settings.max_pixels))
                try:
                    image = await asyncio.shield(decoding)
                except asyncio.CancelledError:
                    await decoding  # Wait for decoder to close files before deleting the job directory.
                    raise
                temporary.unlink()
                try:
                    job, created = await asyncio.to_thread(store.create, session_owner, idempotency_key, key, image, settings)
                except Capacity as error:
                    raise HTTPException(429, str(error), headers={"Retry-After":"3"})
                coordinator.wake.set()
                return {"job_id":job["id"], "status_url":f"/api/jobs/{job['id']}"}
            except ValueError as error:
                raise HTTPException(422, str(error))
            finally:
                await file.close()
                if not created:
                    # directory is a freshly generated UUID, already checked against storage root.
                    await asyncio.to_thread(shutil.rmtree, directory)

    @app.get("/api/jobs/{key}")
    async def status(key: str, request: Request):
        job = job_for(key, request)
        job["queue_position"] = await asyncio.to_thread(store.queue_position, key)
        return job

    @app.post("/api/jobs/{key}/cancel")
    async def cancel(key: str, request: Request):
        job_for(key, request)
        body = await asyncio.to_thread(store.cancel, key, owner(request))
        coordinator.cancel(key)
        return {"state":body["state"]}

    @app.put("/api/jobs/{key}/review")
    async def review(key: str, body: ReviewBody, request: Request):
        job_for(key, request)
        try:
            result = await asyncio.to_thread(store.review, key, owner(request), body.values.model_dump(), body.revision, body.confirmed)
        except Conflict as error:
            raise HTTPException(409, str(error))
        return {"review":result["review"], "revision":result["revision"]}

    @app.get("/api/jobs/{key}/image")
    async def image(key: str, request: Request):
        job_for(key, request)
        return FileResponse(store.directory(key) / "image.png", media_type="image/png", headers={"Cache-Control":"no-store"})

    @app.get("/api/jobs/{key}/download")
    async def download(key: str, request: Request, version: Literal["ai", "reviewed"] = "ai"):
        job = job_for(key, request)
        if job["state"] not in {"succeeded", "partial"}:
            raise HTTPException(409, "Chưa có kết quả của tác vụ này.")
        if version == "reviewed":
            if not job["review"] or not job["review"]["confirmed"]:
                raise HTTPException(409, "Hãy lưu và xác nhận bản chỉnh sửa trước.")
            values = job["review"]["values"]
        else:
            values = job["result"]
        return Response(json.dumps({field:values[field] for field in FIELDS}, ensure_ascii=False, indent=2),
                        media_type="application/json", headers={"Cache-Control":"no-store",
                        "Content-Disposition":f'attachment; filename="receipt-{key}-{version}.json"'})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
