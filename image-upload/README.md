# Image upload with WebP conversion

A small FastAPI service. It accepts an image upload, converts it to WebP, stores it and returns its URL.

## Pipeline

```
upload → 15 MB limit → decode & verify with Pillow (client Content-Type is ignored)
       → apply EXIF rotation, drop metadata → shrink to max 2048 px edge
       → normalize color mode → encode WebP → save as storage/<id>.webp → JSON
```

- Photos are saved as lossy WebP at quality 80. Small PNGs with transparency (logos, screenshots) are saved lossless.
- Animated GIF, APNG and WebP files keep their frames.
- Images over 40 megapixels are refused, which guards against decompression bombs.
- All image logic is in `app/convert.py` (`to_webp(bytes)`). Storage is in `app/storage.py`. To move to S3 or MinIO, replace `LocalStorage` with a class that has the same `save` and `url_for` methods.

## Run

You need Python 3.9 or newer. Run these commands from the `image-upload` folder:

```bash
cd image-upload

# 1. Create a virtual environment and install the dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# 2. (Optional) Run the tests
.venv/bin/pytest

# 3. Start the server
.venv/bin/uvicorn app.main:app --reload
```

On Windows, use `.venv\Scripts\` in place of `.venv/bin/`.

To try it, open http://localhost:8000 in your browser and pick an image to upload, or upload from the command line:

```bash
curl -F file=@photo.jpg http://localhost:8000/upload
```

| Response | Meaning |
|---|---|
| 200 | `{id, url, width, height, bytes, original_bytes}` |
| 400 | Empty file |
| 413 | Larger than 15 MB |
| 415 | Not a readable image, or over 40 megapixels |

Set `STORAGE_DIR` to store the files somewhere other than `./storage`.
