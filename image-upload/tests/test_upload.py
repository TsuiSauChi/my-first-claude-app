import pytest
from PIL import Image

from app.main import MAX_UPLOAD_BYTES
from conftest import encode


def test_upload_converts_stores_and_serves(client):
    src = encode(Image.new("RGB", (1200, 900), (90, 140, 200)), "JPEG", quality=95)
    res = client.post("/upload", files={"file": ("photo.jpg", src, "image/jpeg")})
    assert res.status_code == 200
    body = res.json()
    assert body["url"] == f"/images/{body['id']}.webp"
    assert (body["width"], body["height"]) == (1200, 900)
    assert body["original_bytes"] == len(src)

    img = client.get(body["url"])
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/webp"
    assert "immutable" in img.headers["cache-control"]
    assert len(img.content) == body["bytes"]


def test_lying_content_type_is_ignored(client):
    src = encode(Image.new("RGB", (10, 10)), "PNG")
    res = client.post("/upload", files={"file": ("x.txt", src, "text/plain")})
    assert res.status_code == 200


def test_non_image_returns_415(client):
    res = client.post("/upload", files={"file": ("x.jpg", b"not an image", "image/jpeg")})
    assert res.status_code == 415


def test_empty_file_returns_400(client):
    res = client.post("/upload", files={"file": ("x.jpg", b"", "image/jpeg")})
    assert res.status_code == 400


def test_oversized_upload_returns_413(client):
    res = client.post("/upload", files={"file": ("big.jpg", b"\0" * (MAX_UPLOAD_BYTES + 1), "image/jpeg")})
    assert res.status_code == 413


def test_index_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "WebP Upload" in res.text


def test_oversized_content_length_rejected_before_reading(client):
    res = client.post(
        "/upload", content=b"x",
        headers={"content-type": "multipart/form-data; boundary=b", "content-length": str(MAX_UPLOAD_BYTES * 4)},
    )
    assert res.status_code == 413


def test_oversized_chunked_upload_is_cut_off():
    # TestClient buffers the whole body before sending, so drive the middleware directly
    # with a stream that has no Content-Length, as a chunked upload would.
    import asyncio

    from fastapi import HTTPException

    from app.main import MAX_BODY_BYTES, BodySizeLimit

    chunks_sent = 0

    async def receive():
        nonlocal chunks_sent
        chunks_sent += 1
        return {"type": "http.request", "body": b"\0" * (1024 * 1024), "more_body": chunks_sent < 64}

    async def app(scope, receive, send):
        while (await receive())["more_body"]:
            pass

    scope = {"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=b")]}
    with pytest.raises(HTTPException) as e:
        asyncio.run(BodySizeLimit(app, MAX_BODY_BYTES)(scope, receive, None))
    assert e.value.status_code == 413
    assert chunks_sent == MAX_BODY_BYTES // (1024 * 1024) + 1  # stopped just past the limit
