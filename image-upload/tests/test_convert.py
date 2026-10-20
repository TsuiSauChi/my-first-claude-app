from io import BytesIO

import pytest
from PIL import Image

from app.convert import MAX_EDGE, UnsupportedImage, to_webp
from conftest import encode


def open_webp(data: bytes) -> Image.Image:
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    img = Image.open(BytesIO(data))
    assert img.format == "WEBP"
    return img


def test_jpeg_becomes_webp():
    src = encode(Image.new("RGB", (800, 600), (200, 40, 40)), "JPEG", quality=95)
    result = to_webp(src)
    assert (result.width, result.height) == (800, 600)
    assert open_webp(result.data).size == (800, 600)


def test_png_alpha_is_kept():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    img.paste((10, 200, 10, 255), (16, 16, 48, 48))
    out = open_webp(to_webp(encode(img, "PNG")).data)
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((32, 32)) == (10, 200, 10, 255)  # lossless for small alpha PNGs


def test_exif_rotation_applied_and_metadata_removed():
    img = Image.new("RGB", (400, 200), (30, 30, 200))
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90° CW to display
    exif[0x010F] = "TestCam"  # Make
    result = to_webp(encode(img, "JPEG", exif=exif.tobytes()))
    assert (result.width, result.height) == (200, 400)
    out = open_webp(result.data)
    assert "exif" not in out.info
    assert len(out.getexif()) == 0


def test_large_image_is_downscaled():
    result = to_webp(encode(Image.new("RGB", (6000, 3000), "white"), "PNG"))
    assert (result.width, result.height) == (MAX_EDGE, MAX_EDGE // 2)


def test_small_image_is_not_upscaled():
    result = to_webp(encode(Image.new("RGB", (40, 30), "white"), "BMP"))
    assert (result.width, result.height) == (40, 30)


def test_animated_gif_keeps_frames():
    frames = [Image.new("RGB", (50, 50), (i * 60, 0, 0)) for i in range(4)]
    src = encode(frames[0], "GIF", save_all=True, append_images=frames[1:], duration=120, loop=0)
    out = open_webp(to_webp(src).data)
    assert out.n_frames == 4


def test_cmyk_and_grayscale_are_converted():
    for mode in ("CMYK", "L"):
        fmt = "JPEG"
        out = open_webp(to_webp(encode(Image.new(mode, (20, 20)), fmt)).data)
        assert out.mode == "RGB"


def test_rejects_non_image():
    with pytest.raises(UnsupportedImage):
        to_webp(b"hello, this is not an image")


def test_rejects_truncated_image():
    src = encode(Image.new("RGB", (300, 300), "red"), "PNG")
    with pytest.raises(UnsupportedImage):
        to_webp(src[: len(src) // 2])


def test_rejects_decompression_bomb():
    # 7000x7000 = 49 MP, above the 40 MP limit, but tiny on disk
    with pytest.raises(UnsupportedImage):
        to_webp(encode(Image.new("1", (7000, 7000)), "PNG"))


# --- Fixes from code review ---------------------------------------------------

def test_mpo_phone_photo_uses_first_frame():
    main = Image.new("RGB", (300, 200), (200, 0, 0))
    depth = Image.new("RGB", (300, 200), (0, 0, 200))
    src = encode(main, "MPO", save_all=True, append_images=[depth])
    assert Image.open(BytesIO(src)).format == "MPO"
    out = open_webp(to_webp(src).data).convert("RGB")
    assert out.getpixel((10, 10))[0] > 150  # the main (red) picture, not the depth map


def test_multipage_tiff_uses_first_page():
    pages = [Image.new("RGB", (60, 40), c) for c in ("red", "blue")]
    src = encode(pages[0], "TIFF", save_all=True, append_images=pages[1:])
    result = to_webp(src)
    assert (result.width, result.height) == (60, 40)
    assert open_webp(result.data).getpixel((5, 5))[0] > 200


def test_colour_profile_converted_to_srgb():
    from conftest import display_p3_icc
    colour = (200, 100, 50)
    src = encode(Image.new("RGB", (20, 20), colour), "PNG", icc_profile=display_p3_icc())
    out = open_webp(to_webp(src).data)
    assert "icc_profile" not in out.info
    r, g, b = out.convert("RGB").getpixel((10, 10))
    # P3 orange is more saturated than the same numbers in sRGB.
    assert r > colour[0] + 5 and b < colour[2]


def test_broken_colour_profile_is_ignored():
    src = encode(Image.new("RGB", (20, 20), (10, 20, 30)), "PNG", icc_profile=b"not a profile")
    assert open_webp(to_webp(src).data).convert("RGB").getpixel((5, 5)) == (10, 20, 30)


def test_16bit_greyscale_is_scaled_not_clipped():
    img = Image.new("I;16", (16, 16), 32768)
    out = open_webp(to_webp(encode(img, "PNG")).data).convert("RGB")
    assert all(120 <= v <= 136 for v in out.getpixel((8, 8)))


def test_rejects_image_between_one_and_two_times_pixel_limit():
    # 42 MP: Pillow itself only warns here, so this is our own check.
    with pytest.raises(UnsupportedImage, match="megapixels"):
        to_webp(encode(Image.new("1", (7000, 6000)), "PNG"))


def test_rejects_animation_with_too_many_pixels_before_decoding():
    import time
    frames = [Image.new("RGB", (2000, 2000), (i * 8, 0, 0)) for i in range(30)]
    src = encode(frames[0], "GIF", save_all=True, append_images=frames[1:])
    start = time.monotonic()
    with pytest.raises(UnsupportedImage, match="too large"):
        to_webp(src)
    assert time.monotonic() - start < 2


def test_rejects_animation_with_too_many_frames():
    frames = [Image.new("RGB", (4, 4), (i % 256, i // 256, 0)) for i in range(302)]
    src = encode(frames[0], "GIF", save_all=True, append_images=frames[1:])
    with pytest.raises(UnsupportedImage, match="frames"):
        to_webp(src)


def test_animation_follows_exif_rotation():
    frames = [Image.new("RGB", (80, 40), (i * 60, 0, 0)) for i in range(3)]
    exif = Image.Exif()
    exif[0x0112] = 6
    src = encode(frames[0], "WEBP", save_all=True, append_images=frames[1:], exif=exif.tobytes())
    out = open_webp(to_webp(src).data)
    assert out.n_frames == 3
    assert out.size == (40, 80)


def test_animation_keeps_frame_durations():
    frames = [Image.new("RGB", (20, 20), (i * 60, 0, 0)) for i in range(3)]
    src = encode(frames[0], "GIF", save_all=True, append_images=frames[1:], duration=[50, 300, 1000])
    out = open_webp(to_webp(src).data)
    durations = []
    for i in range(out.n_frames):
        out.seek(i)
        out.load()  # WebP frame info is filled in on load
        durations.append(out.info["duration"])
    assert durations == [50, 300, 1000]


def test_unneeded_formats_are_rejected():
    with pytest.raises(UnsupportedImage):
        to_webp(encode(Image.new("RGB", (32, 32), "red"), "ICO"))


def test_small_opaque_png_is_lossless():
    img = Image.new("RGB", (64, 64), (13, 57, 201))
    img.putpixel((3, 3), (250, 1, 2))
    out = open_webp(to_webp(encode(img, "PNG")).data).convert("RGB")
    assert out.getpixel((3, 3)) == (250, 1, 2)
    assert out.getpixel((40, 40)) == (13, 57, 201)
