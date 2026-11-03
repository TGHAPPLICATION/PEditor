"""G5-04 輔助：新圖登記的格式、像素上限與參數檢查（ADR-0022）。"""

import base64
import io
import struct
import zlib

import pytest
from PIL import Image

from peditor.core.editplan import validate_image_params
from peditor.core.protocol import ProtocolError
from peditor.worker import image


def _png(size=(4, 3), mode="RGB", color=(1, 2, 3)) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, "PNG")
    return buf.getvalue()


def _image(fmt, mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (4, 3)).save(buf, fmt)
    return buf.getvalue()


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def _png_header_only(width: int, height: int) -> bytes:
    """結構完整（IHDR、空 IDAT、IEND）但沒有像素資料的 PNG：只靠檔頭宣告尺寸。"""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", b"")
            + _chunk(b"IEND", b""))  # fmt: skip


def _code(func, *args) -> str:
    with pytest.raises(ProtocolError) as info:
        func(*args)
    return info.value.code


def test_supported_formats_and_alpha():
    asset = image.load_asset(_png())
    assert (asset.format, asset.width, asset.height, asset.components) == ("png", 4, 3, 3)
    assert not asset.has_alpha
    assert not image.load_asset(_png(mode="RGBA", color=(1, 2, 3, 255))).has_alpha  # 全不透明
    assert image.load_asset(_png(mode="RGBA", color=(1, 2, 3, 10))).has_alpha
    assert image.load_asset(_png(mode="L", color=9)).components == 1
    jpeg = image.load_asset(_image("JPEG"))
    assert (jpeg.format, jpeg.components) == ("jpeg", 3)
    assert image.load_asset(_image("JPEG", "L")).components == 1


@pytest.mark.parametrize(
    "data",
    [
        _image("GIF", "P"),
        _image("BMP"),
        _image("JPEG", "CMYK"),
        b"\xff\xd8\xff\xc3\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00",  # 無損 JPEG
        _png()[:40],  # 檔頭完整、內容截斷
        _png()[:-12],  # 少了 IEND
        _png()[:30] + bytes([_png()[30] ^ 0xFF]) + _png()[31:],  # IHDR 的 CRC 不符
        _image("JPEG")[:-2],  # 少了影像結束標記
        b"",
    ],
    ids=[
        "gif",
        "bmp",
        "cmyk-jpeg",
        "lossless-jpeg",
        "truncated-png",
        "no-iend",
        "bad-crc",
        "truncated-jpeg",
        "empty",
    ],
)
def test_unsupported_or_broken_images_rejected(data):
    assert _code(image.load_asset, data) == "UNSUPPORTED_FEATURE"


def test_pixel_limit_checked_before_decoding(monkeypatch):
    def never(*args):
        raise AssertionError("超過像素上限的圖片不得解碼")

    monkeypatch.setattr(image.pymupdf, "Pixmap", never)
    assert _code(image.load_asset, _png_header_only(10_000, 5_001)) == "RESOURCE_LIMIT"


def test_size_limit(monkeypatch):
    monkeypatch.setattr(image, "MAX_IMAGE_BYTES", 64)
    assert _code(image.load_asset, _png((40, 40))) == "RESOURCE_LIMIT"


def test_register_asset_keep_and_bad_data():
    class Doc:
        assets: dict = {}

    doc = Doc()
    doc.assets = {}
    first = image.register_asset(doc, {"data": base64.b64encode(_png()).decode()})
    second = image.register_asset(doc, {"data": base64.b64encode(_png(color=(9, 9, 9))).decode(),
                                        "keep": []})  # fmt: skip
    assert list(doc.assets) == [second["asset_id"]] and first["asset_id"] != second["asset_id"]
    assert _code(image.register_asset, doc, {"data": "不是 base64"}) == "INVALID_REQUEST"
    assert _code(image.register_asset, doc, {}) == "INVALID_REQUEST"


def test_padding_geometry():
    assert image.padding(200, 100, (200.0, 100.0)) is None
    assert image.padding(201, 100, (200.0, 100.0)) is None  # 1% 以內不補邊
    assert image.padding(100, 100, (200.0, 100.0)) == (200, 100, 50, 0)
    assert image.padding(100, 100, (100.0, 200.0)) == (100, 200, 0, 50)
    with pytest.raises(ProtocolError, match="像素"):
        image.padding(1, 8000, (8000.0, 1.0))


def test_image_plan_params_whitelist():
    target = "i:r0:p0:s9.0:o2:f:g4611d2fee076"
    ok = {"target_id": target, "asset_id": "0" * 64}
    assert validate_image_params(ok) == ok
    for bad in (
        {**ok, "path": "x.png"},  # 不接受路徑或其他參數
        {**ok, "target_id": "t:r0:p0:s9.0:o2:f:g4611d2fee076"},  # 文字目標
        {**ok, "asset_id": "abc"},
    ):
        assert _code(validate_image_params, bad) == "INVALID_REQUEST"


@pytest.mark.parametrize("value", [1, 3, 6, 8])
def test_jpeg_orientation(value):
    exif = Image.Exif()
    exif[0x0112] = value
    buf = io.BytesIO()
    Image.new("RGB", (4, 3)).save(buf, "JPEG", exif=exif.tobytes())
    assert image.jpeg_orientation(buf.getvalue()) == value
    assert image.load_asset(buf.getvalue()).orientation == value
    assert image.jpeg_orientation(_image("JPEG")) == 1  # 沒有 Exif
    assert image.jpeg_orientation(b"\xff\xd8\xff\xe1\x00\x08Exif\x00\x00") == 1  # 截斷的 Exif
