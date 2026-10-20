import mimetypes
import os
import threading
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .convert import UnsupportedImage, to_webp
from .storage import LocalStorage

# Some systems lack this mapping, which makes StaticFiles serve .webp as text/plain.
mimetypes.add_type("image/webp", ".webp")

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
# Room for multipart boundaries and headers around the file itself.
MAX_BODY_BYTES = MAX_UPLOAD_BYTES + 64 * 1024
# Decoding and encoding are CPU- and memory-heavy; don't run more than this many at once.
CONVERT_CONCURRENCY = int(os.environ.get("CONVERT_CONCURRENCY", max(1, (os.cpu_count() or 2) // 2)))
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", Path(__file__).resolve().parent.parent / "storage"))

TOO_LARGE = f"Image is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."


class BodySizeLimit:
    """Reject oversized request bodies while they stream in.

    Starlette writes the whole multipart upload to a temp file before the handler
    runs, so a size check inside the handler comes too late to protect the disk.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope["headers"])
        length = headers.get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            return await JSONResponse({"detail": TOO_LARGE}, status_code=413)(scope, receive, send)

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # FastAPI re-raises HTTPException from body parsing unchanged.
                    raise HTTPException(413, TOO_LARGE)
            return message

        await self.app(scope, limited_receive, send)


class CachedStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            # Ids are random and files never change, so cache them for a year.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_app(storage_dir: Path) -> FastAPI:
    app = FastAPI(title="Image upload")
    app.add_middleware(BodySizeLimit, max_bytes=MAX_BODY_BYTES)
    storage = LocalStorage(storage_dir)
    app.mount("/images", CachedStaticFiles(directory=storage_dir), name="images")
    converting = threading.BoundedSemaphore(CONVERT_CONCURRENCY)

    @app.post("/upload")
    def upload(file: UploadFile = File(...)):
        # Sync def: FastAPI runs it in a threadpool, so encoding doesn't block the event loop.
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, TOO_LARGE)
        if not data:
            raise HTTPException(400, "The uploaded file is empty.")
        try:
            with converting:
                result = to_webp(data)
        except UnsupportedImage as e:
            raise HTTPException(415, f"Could not read this file as an image: {e}")

        image_id = storage.save(result.data)
        return {
            "id": image_id,
            "url": storage.url_for(image_id),
            "width": result.width,
            "height": result.height,
            "bytes": len(result.data),
            "original_bytes": len(data),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

    return app


app = create_app(STORAGE_DIR)
