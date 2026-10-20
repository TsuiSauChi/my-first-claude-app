"""Convert an uploaded image to WebP.

Pure bytes-in, bytes-out so it can be tested without HTTP.
"""
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

# Limits are checked from the file header, before any pixels are decoded.
MAX_PIXELS = 40_000_000             # one still image or one animation frame
MAX_FRAMES = 300
MAX_ANIMATION_PIXELS = 100_000_000  # all source frames together (bounds CPU)
MAX_OUTPUT_PIXELS = 50_000_000      # all resized frames together (bounds memory)
# Pillow's own bomb check, as a backstop: it raises at 2x this, before allocating.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

MAX_EDGE = 2048
QUALITY = 80
LOSSLESS_MAX_PIXELS = 1_000_000

# Only common web/photo formats; Pillow can read many more (PSD, EPS, FITS...) that we don't need.
# MPO (multi-picture JPEG from phones) is opened through the JPEG entry.
ALLOWED_FORMATS = ("JPEG", "PNG", "GIF", "WEBP", "BMP", "TIFF")
ANIMATED_FORMATS = {"GIF", "WEBP", "PNG"}
# Multi-frame formats where only the first frame is the picture (MPO: phone depth/portrait shots).
FIRST_FRAME_FORMATS = {"MPO", "TIFF"}

ORIENTATION_TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}

SRGB = ImageCms.createProfile("sRGB")


class UnsupportedImage(ValueError):
    """The bytes are not an image we can safely decode."""


@dataclass
class WebPResult:
    data: bytes
    width: int
    height: int


def _open(data: bytes) -> Image.Image:
    """Open from the header only; no pixels are decoded yet."""
    try:
        with Image.open(BytesIO(data), formats=ALLOWED_FORMATS) as probe:
            probe.verify()  # checks integrity, leaves the image unusable
        img = Image.open(BytesIO(data), formats=ALLOWED_FORMATS)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as e:
        raise UnsupportedImage(str(e) or "not a valid image") from e
    if img.width * img.height > MAX_PIXELS:
        raise UnsupportedImage(f"image is larger than {MAX_PIXELS // 1_000_000} megapixels")
    return img


def _load(img: Image.Image) -> None:
    try:
        img.load()
    except (OSError, SyntaxError) as e:
        raise UnsupportedImage(str(e) or "image data is damaged") from e


def _scaled_size(width: int, height: int) -> tuple[int, int]:
    scale = min(1.0, MAX_EDGE / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def _to_srgb(img: Image.Image, icc: bytes | None) -> Image.Image:
    """Convert pixels from their embedded colour profile to sRGB (e.g. iPhone Display P3)."""
    if not icc or img.mode not in ("RGB", "RGBA", "CMYK", "L"):
        return img
    try:
        src = ImageCms.ImageCmsProfile(BytesIO(icc))
        return ImageCms.profileToProfile(
            img, src, SRGB, outputMode="RGBA" if img.mode == "RGBA" else "RGB"
        )
    except (ImageCms.PyCMSError, OSError, ValueError):
        return img  # broken profile: keep pixels as they are


def _normalize_mode(img: Image.Image) -> Image.Image:
    if img.mode in ("RGB", "RGBA"):
        return img
    if img.mode.startswith("I;16"):
        # 16-bit grey: scale 0-65535 down to 0-255 instead of clipping.
        return img.convert("I").point(lambda v: v / 256).convert("RGB")
    if img.mode in ("I", "F"):
        lo, hi = img.getextrema()
        scale = 255 / (hi - lo) if hi > lo else 0
        return img.convert("F").point(lambda v: (v - lo) * scale).convert("RGB")
    if img.mode in ("LA", "PA", "RGBa", "La") or (img.mode == "P" and "transparency" in img.info):
        return img.convert("RGBA")
    return img.convert("RGB")


def _prepare_frame(frame: Image.Image, icc: bytes | None, transpose) -> Image.Image:
    frame = _to_srgb(frame, icc)
    frame = _normalize_mode(frame)
    if transpose is not None:
        frame = frame.transpose(transpose)
    frame.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)  # never upscales
    return frame


def _orientation(img: Image.Image):
    try:
        return ORIENTATION_TRANSPOSE.get(img.getexif().get(0x0112))
    except Exception:
        return None


def to_webp(data: bytes) -> WebPResult:
    img = _open(data)
    source_format = img.format
    n_frames = getattr(img, "n_frames", 1)
    icc = img.info.get("icc_profile")
    transpose = _orientation(img)

    if n_frames > 1 and source_format in FIRST_FRAME_FORMATS:
        n_frames = 1
    elif n_frames > 1 and source_format not in ANIMATED_FORMATS:
        raise UnsupportedImage(f"multi-frame {source_format} files are not supported")

    out = BytesIO()
    if n_frames > 1:
        out_w, out_h = _scaled_size(img.width, img.height)
        if n_frames > MAX_FRAMES:
            raise UnsupportedImage(f"animation has more than {MAX_FRAMES} frames")
        if img.width * img.height * n_frames > MAX_ANIMATION_PIXELS or out_w * out_h * n_frames > MAX_OUTPUT_PIXELS:
            raise UnsupportedImage("animation is too large")

        frames, durations = [], []
        for i in range(n_frames):
            img.seek(i)
            _load(img)
            durations.append(img.info.get("duration", 100))
            frames.append(_prepare_frame(img.copy(), icc, transpose))
        # Frames can differ in mode (some with transparency); WebP needs one.
        mode = "RGBA" if any(f.mode == "RGBA" for f in frames) else "RGB"
        frames = [f if f.mode == mode else f.convert(mode) for f in frames]
        frames[0].save(
            out, "WEBP", save_all=True, append_images=frames[1:],
            duration=durations, loop=img.info.get("loop", 0), quality=QUALITY, method=4,
        )
        width, height = frames[0].size
    else:
        _load(img)
        # Saving pixels only drops EXIF/GPS; colour is converted to sRGB first.
        img = _prepare_frame(img, icc, transpose)
        # Small PNGs are usually screenshots, logos or diagrams: keep them pixel-exact.
        lossless = source_format == "PNG" and img.width * img.height <= LOSSLESS_MAX_PIXELS
        if lossless:
            img.save(out, "WEBP", lossless=True, method=4)
        else:
            img.save(out, "WEBP", quality=QUALITY, method=4)
        width, height = img.size

    return WebPResult(out.getvalue(), width, height)
