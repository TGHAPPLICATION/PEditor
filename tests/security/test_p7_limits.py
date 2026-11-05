"""G7-06：解壓前的大小限制（P2 triage f024）、CMap 線性解析（f022）、影像像素上限（spec P7）。"""

import base64
import time
import zlib

import pikepdf
import pytest

from peditor.core.limits import MAX_STREAM_BYTES, LimitExceeded
from peditor.worker import analyzer, fonts, streams

PDF = pikepdf.new()  # 串流的擁有者須存活到測試結束


def _stream(data: bytes, filters=None) -> pikepdf.Stream:
    stream = pikepdf.Stream(PDF, b"")
    if filters is None:
        stream.write(data)
    else:
        stream.write(data, filter=filters)
    return stream


def _bomb(size: int) -> bytes:
    packer = zlib.compressobj(9)
    chunk = b" " * (1024 * 1024)
    return b"".join(packer.compress(chunk) for _ in range(size // len(chunk))) + packer.flush()


def test_flate_bomb_rejected_before_full_decode():
    stream = _stream(_bomb(MAX_STREAM_BYTES + 1024 * 1024), pikepdf.Name.FlateDecode)
    with pytest.raises(LimitExceeded):
        streams.check(stream)


def test_ascii85_then_flate_measured_exactly():
    """ASCII85 包住的 Flate：實際解碼 ASCII85 後以 zlib 分段量測（小檔通過、炸彈拒絕）。"""
    small = base64.a85encode(zlib.compress(b"q Q " * 1000)) + b"~>"
    filters = pikepdf.Array([pikepdf.Name.ASCII85Decode, pikepdf.Name.FlateDecode])
    streams.check(_stream(small, filters))
    big = base64.a85encode(_bomb(MAX_STREAM_BYTES + 1024 * 1024)) + b"~>"
    with pytest.raises(LimitExceeded):
        streams.check(_stream(big, filters))


def test_unmeasured_filters_use_worst_case_ratio():
    """LZW 等無法分段量測的過濾器以最大膨脹倍數估上限；不認得的過濾器視為無上限。"""
    streams.check(_stream(b"\x00" * 1000, pikepdf.Name.LZWDecode))
    with pytest.raises(LimitExceeded):
        streams.check(_stream(b"\x00" * (MAX_STREAM_BYTES // 4096 + 1), pikepdf.Name.LZWDecode))
    with pytest.raises(LimitExceeded):
        streams.check(_stream(b"\x00" * 10, pikepdf.Name.DCTDecode))


def test_plain_streams_unaffected():
    data = b"BT /F1 12 Tf (x) Tj ET" * 100
    assert streams.read(_stream(data)) == data
    assert streams.read(_stream(zlib.compress(data), pikepdf.Name.FlateDecode)) == data


def test_cmap_unterminated_blocks_linear():
    """f022：大量沒有結尾的 beginbfchar 不使解析變成平方級。"""
    text = "beginbfchar <01> <0041>\n" * 150_000
    started = time.monotonic()
    assert fonts.parse_cmap(text) == {}
    assert time.monotonic() - started < 2


def test_huge_image_page_rejected(tmp_path):
    """宣告超過 50 MP 的影像：頁面回 RESOURCE_LIMIT，不交給 MuPDF 配置。"""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    image = pikepdf.Stream(pdf, b"")
    image.write(zlib.compress(b"\x00" * 3), filter=pikepdf.Name.FlateDecode)
    image.Type, image.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
    image.Width, image.Height, image.BitsPerComponent = 10_000, 10_000, 8
    image.ColorSpace = pikepdf.Name.DeviceGray
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=image))
    page.Contents = pdf.make_stream(b"q 100 0 0 100 0 0 cm /Im0 Do Q")
    path = tmp_path / "huge.pdf"
    pdf.save(path)
    document = analyzer.open_document(str(path))
    try:
        assert "RESOURCE_LIMIT" in analyzer.inspect_page(document, 0)["capabilities"]["reasons"]
    finally:
        document.close()
