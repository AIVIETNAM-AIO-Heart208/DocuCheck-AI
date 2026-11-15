"""Bound the multipart stream before FastAPI spools it to temporary files."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class BodyLimit:
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") != "/api/jobs":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail":"Content-Length không hợp lệ."}, status_code=400)(scope, receive, send)
        if length > self.max_bytes or length < 0:
            return await JSONResponse({"detail":"Ảnh vượt giới hạn dung lượng request."}, status_code=413)(scope, receive, send)
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                raise HTTPException(413, "Ảnh vượt giới hạn dung lượng request.")
            return message

        await self.app(scope, bounded_receive, send)
