"""Where converted images are kept.

Local disk for now. To move to S3/MinIO, implement the same two methods.
"""
import os
import uuid
from pathlib import Path


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes) -> str:
        image_id = uuid.uuid4().hex
        tmp = self.root / f".{image_id}.tmp"
        tmp.write_bytes(data)
        os.replace(tmp, self.root / f"{image_id}.webp")  # atomic: no half-written files served
        return image_id

    def url_for(self, image_id: str) -> str:
        return f"/images/{image_id}.webp"
