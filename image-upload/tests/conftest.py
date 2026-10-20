import os
import tempfile
from io import BytesIO

import pytest
from PIL import Image

# Must be set before app.main is imported, so importing it never creates ./storage.
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="image-upload-test-")


def encode(img: Image.Image, fmt: str, **kwargs) -> bytes:
    buf = BytesIO()
    img.save(buf, fmt, **kwargs)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    return TestClient(create_app(tmp_path))


def display_p3_icc() -> bytes:
    """A minimal ICC v2 matrix/TRC profile with Display P3 primaries (D50-adapted)."""
    import struct

    def s15(v):
        return struct.pack(">i", round(v * 65536))

    def xyz(x, y, z):
        return b"XYZ " + b"\0" * 4 + s15(x) + s15(y) + s15(z)

    curve = b"curv" + b"\0" * 4 + struct.pack(">IH", 1, int(2.2 * 256)) + b"\0\0"
    tags = [
        (b"wtpt", xyz(0.9642, 1.0, 0.8249)),
        (b"rXYZ", xyz(0.5151, 0.2412, -0.0011)),
        (b"gXYZ", xyz(0.2920, 0.6922, 0.0419)),
        (b"bXYZ", xyz(0.1571, 0.0666, 0.7841)),
        (b"rTRC", curve), (b"gTRC", curve), (b"bTRC", curve),
    ]
    offset = 128 + 4 + 12 * len(tags)
    table, body = b"", b""
    for sig, data in tags:
        table += sig + struct.pack(">II", offset + len(body), len(data))
        body += data + b"\0" * (-len(data) % 4)
    size = offset + len(body)
    header = (
        struct.pack(">I", size) + b"\0" * 4 + struct.pack(">I", 0x02100000)
        + b"mntrRGB XYZ " + b"\0" * 12 + b"acsp" + b"\0" * 24
        + struct.pack(">I", 0) + s15(0.9642) + s15(1.0) + s15(0.8249) + b"\0" * 48
    )
    assert len(header) == 128
    return header + struct.pack(">I", len(tags)) + table + body
