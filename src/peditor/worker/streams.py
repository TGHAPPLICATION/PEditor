"""解壓前的大小限制（spec P7「不能先完整解壓才檢查」；P2 triage f024；ADR-0024）。

pikepdf 的 read_bytes() 與 parse_content_stream() 會一次解出整個串流，MuPDF 渲染與擷取也是；
壓縮炸彈（S03）可讓 1 MB 解成數 GB。這裡在交給它們之前先以有上限的方式算出解壓後大小：

- 開頭的 ASCIIHex／ASCII85 實際解碼（大小不會超過原文），接著的 FlateDecode 以 zlib 分段解壓，
  超過上限立即停止——最常見的寫法（只有 Flate）得到確切大小。
- 之後其餘的過濾器以最大膨脹倍數估上限（RunLength 128、LZW 4096、Flate 1032）；不認得的
  過濾器（影像用的 DCT 等出現在內容、字型串流）視為無上限。
- 確切大小或上限估計超過 limit 即 LimitExceeded，不交給 pikepdf／MuPDF 解壓。
"""

from __future__ import annotations

import base64
import math
import re
import zlib

import pikepdf

from peditor.core.limits import MAX_STREAM_BYTES, LimitExceeded

_RATIO = {
    "/ASCIIHexDecode": 1,
    "/ASCII85Decode": 4,  # 「z」一個字元解成 4 個位元組
    "/RunLengthDecode": 128,
    "/LZWDecode": 4096,
    "/FlateDecode": 1032,  # deflate 理論最大壓縮比
}
_SPACE = re.compile(rb"\s+")


def _filters(stream: pikepdf.Stream) -> list[str]:
    value = stream.get("/Filter")
    if value is None:
        return []
    items = list(value) if isinstance(value, pikepdf.Array) else [value]
    return [str(v) for v in items]


def _ascii(name: str, data: bytes) -> bytes | None:
    data = _SPACE.sub(b"", data)
    try:
        if name == "/ASCIIHexDecode":
            data = data.split(b">", 1)[0]
            return bytes.fromhex((data + b"0" if len(data) % 2 else data).decode("ascii"))
        data = data.split(b"~>", 1)[0].removeprefix(b"<~")
        return base64.a85decode(data)
    except ValueError:
        return None


def _inflated_size(data: bytes, limit: int) -> int:
    """分段解壓，回傳解壓後大小；超過 limit 即停止並 LimitExceeded。資料毀損時回傳已解出的大小
    （qpdf 對毀損資料同樣只解出前段）。"""
    inflater = zlib.decompressobj()
    total = 0
    try:
        while data:
            out = inflater.decompress(data, limit + 1 - total)
            total += len(out)
            if total > limit:
                raise LimitExceeded("stream_size")
            data = inflater.unconsumed_tail
            if inflater.eof or not out:
                break
    except zlib.error:
        pass
    return total


def check(stream: pikepdf.Stream, limit: int = MAX_STREAM_BYTES) -> None:
    """串流解壓後可能超過 limit 即 LimitExceeded（不實際交給 pikepdf 解壓）。"""
    filters = _filters(stream)
    data = stream.read_raw_bytes()
    exact: bytes | None = data
    size = len(data)
    i = 0
    while i < len(filters) and filters[i] in ("/ASCIIHexDecode", "/ASCII85Decode") and exact:
        exact = _ascii(filters[i], exact)
        if exact is None:
            break
        size = len(exact)
        i += 1
    if exact is not None and i < len(filters) and filters[i] == "/FlateDecode":
        size = _inflated_size(exact, limit)
        i += 1
    bound: float = size
    for name in filters[i:]:
        bound *= _RATIO.get(name, math.inf)
    if bound > limit:
        raise LimitExceeded("stream_size")


def read(stream: pikepdf.Stream, limit: int = MAX_STREAM_BYTES) -> bytes:
    """檢查大小後才解壓讀出。"""
    check(stream, limit)
    data = stream.read_bytes()
    if len(data) > limit:
        raise LimitExceeded("stream_size")
    return data


def parse(stream: pikepdf.Stream, limit: int = MAX_STREAM_BYTES):
    """檢查大小後才解析內容串流（取代直接呼叫 pikepdf.parse_content_stream）。"""
    check(stream, limit)
    return pikepdf.parse_content_stream(stream)
