"""字型解碼：字碼切分、字寬、Unicode 對應（只在 worker 使用）。

支援子集（spec §4）：
- Type0 + Identity-H（2 位元組 CID），字寬取 /W、/DW，Unicode 只取 /ToUnicode。
- 單位元組字型（Type1、TrueType、MMType1、Type3），字寬取 /Widths；Unicode 先取 /ToUnicode，
  沒有時才用標準編碼（WinAnsi、MacRoman、Standard）。
其他 CMap（Identity-V、預定義 CMap、內嵌 CMap）標為不支援，不猜測對應。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pikepdf
import pymupdf

from peditor.core.limits import MAX_CMAP_BYTES, MAX_CODE_EXPANSION, LimitExceeded

# 不支援原因（對應理由碼由 capability 決定）
VERTICAL = "vertical"
UNSUPPORTED_CMAP = "unsupported_cmap"
TYPE3 = "type3"

_BASE14 = {
    "Helvetica": "helv",
    "Helvetica-Bold": "hebo",
    "Helvetica-Oblique": "heit",
    "Helvetica-BoldOblique": "hebi",
    "Times-Roman": "tiro",
    "Times-Bold": "tibo",
    "Times-Italic": "tiit",
    "Times-BoldItalic": "tibi",
    "Courier": "cour",
    "Courier-Bold": "cobo",
    "Courier-Oblique": "coit",
    "Courier-BoldOblique": "cobi",
    "Symbol": "symb",
    "ZapfDingbats": "zadb",
}
_SIMPLE_ENCODINGS = {
    "/WinAnsiEncoding": "cp1252",
    "/MacRomanEncoding": "mac_roman",
    "/StandardEncoding": "latin-1",  # 只用於 ASCII 可列印範圍，見 _standard_unicode
}


@dataclass
class FontInfo:
    key: str  # 資源名稱，例如 "/F1"
    objgen: tuple[int, int]
    subtype: str
    base_font: str
    two_byte: bool
    embedded: bool
    unsupported: str | None = None
    to_unicode: dict[int, str] | None = None
    widths: dict[int, float] = field(default_factory=dict)  # 字碼 → 字寬（文字空間千分之一單位）
    default_width: float = 0.0
    width_scale: float = 0.001  # Type3 以 FontMatrix 換算
    encoding: str | None = None  # 單位元組字型的標準編碼
    differences: dict[int, str] = field(default_factory=dict)
    _base14: pymupdf.Font | None = None

    def codes(self, data: bytes) -> list[int]:
        if self.two_byte:
            if len(data) % 2:
                data = data + b"\x00"
            return [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]
        return list(data)

    def width(self, code: int) -> float:
        """字碼的水平位移（文字空間單位，未乘字級）。"""
        if code in self.widths:
            return self.widths[code] * self.width_scale
        if self._base14 is not None:
            ch = self.unicode(code)
            if ch:
                return self._base14.glyph_advance(ord(ch[0]))
        return self.default_width * self.width_scale

    def unicode(self, code: int) -> str | None:
        """字碼對應的 Unicode；無可靠對應時回 None（不猜測）。"""
        if self.to_unicode is not None:
            return self.to_unicode.get(code)
        if self.two_byte:
            return None
        if code in self.differences:
            return _glyph_name_unicode(self.differences[code])
        if self.encoding == "latin-1":
            return chr(code) if 0x20 <= code < 0x7F and code not in (0x27, 0x60) else None
        if self.encoding:
            try:
                return bytes([code]).decode(self.encoding)
            except UnicodeDecodeError:
                return None
        return None


def load_font(key: str, font: pikepdf.Dictionary) -> FontInfo:
    subtype = str(font.get("/Subtype", ""))
    base_font = str(font.get("/BaseFont", "")).lstrip("/")
    objgen = font.objgen
    if subtype == "/Type0":
        return _load_type0(key, font, objgen, base_font)
    info = FontInfo(
        key=key,
        objgen=objgen,
        subtype=subtype,
        base_font=base_font,
        two_byte=False,
        embedded=_embedded(font.get("/FontDescriptor")),
    )
    if subtype == "/Type3":
        info.unsupported = TYPE3
        matrix = [float(v) for v in font.get("/FontMatrix", [0.001, 0, 0, 0.001, 0, 0])]
        info.width_scale = matrix[0]
    first = int(font.get("/FirstChar", 0))
    for i, w in enumerate(font.get("/Widths", [])):
        info.widths[first + i] = float(w)
    descriptor = font.get("/FontDescriptor")
    if descriptor is not None:
        info.default_width = float(descriptor.get("/MissingWidth", 0))
    if not info.widths and not info.embedded:
        name = base_font.split("+")[-1]
        if name in _BASE14:
            info._base14 = pymupdf.Font(_BASE14[name])
    encoding = font.get("/Encoding")
    if isinstance(encoding, pikepdf.Dictionary):
        info.encoding = _SIMPLE_ENCODINGS.get(str(encoding.get("/BaseEncoding", "")))
        code = 0
        for item in encoding.get("/Differences", []):
            if isinstance(item, pikepdf.Name):
                info.differences[code] = str(item).lstrip("/")
                code += 1
            else:
                code = int(item)
    elif encoding is not None:
        info.encoding = _SIMPLE_ENCODINGS.get(str(encoding))
    elif info._base14 is not None and base_font not in ("Symbol", "ZapfDingbats"):
        info.encoding = "latin-1"
    info.to_unicode = _load_to_unicode(font)
    return info


def _load_type0(key: str, font: pikepdf.Dictionary, objgen, base_font: str) -> FontInfo:
    encoding = str(font.get("/Encoding", ""))
    descendants = font.get("/DescendantFonts") or []
    cid_font = descendants[0] if len(descendants) else None
    info = FontInfo(
        key=key,
        objgen=objgen,
        subtype="/Type0",
        base_font=base_font,
        two_byte=True,
        embedded=_embedded(cid_font.get("/FontDescriptor") if cid_font is not None else None),
    )
    if encoding == "/Identity-V":
        info.unsupported = VERTICAL
    elif encoding != "/Identity-H":
        info.unsupported = UNSUPPORTED_CMAP
    if cid_font is not None:
        info.default_width = float(cid_font.get("/DW", 1000))
        info.widths = _cid_widths(cid_font.get("/W", []))
    info.to_unicode = _load_to_unicode(font)
    return info


def _embedded(descriptor) -> bool:
    return descriptor is not None and any(
        k in descriptor for k in ("/FontFile", "/FontFile2", "/FontFile3")
    )


def _cid_widths(w) -> dict[int, float]:
    """/W 陣列；CID 限於 2 位元組空間（Identity-H），展開總數有上限（P1 安全掃描 f001）。"""
    widths: dict[int, float] = {}
    items = list(w)
    budget = MAX_CODE_EXPANSION
    i = 0
    while i < len(items):
        first = int(items[i])
        nxt = items[i + 1] if i + 1 < len(items) else None
        if isinstance(nxt, pikepdf.Array):
            budget -= len(nxt)
            if budget < 0:
                raise LimitExceeded("cid_widths")
            for j, value in enumerate(nxt):
                if 0 <= first + j <= 0xFFFF:
                    widths[first + j] = float(value)
            i += 2
        elif i + 2 < len(items):
            last, value = int(items[i + 1]), float(items[i + 2])
            lo, hi = max(first, 0), min(last, 0xFFFF)
            budget -= max(hi - lo + 1, 0)
            if budget < 0:
                raise LimitExceeded("cid_widths")
            for cid in range(lo, hi + 1):
                widths[cid] = value
            i += 3
        else:
            break
    return widths


_HEX = r"<([0-9A-Fa-f]*)>"


def _utf16(hexstr: str) -> str:
    data = bytes.fromhex(hexstr if len(hexstr) % 2 == 0 else hexstr + "0")
    return data.decode("utf-16-be", errors="replace")


def parse_cmap(text: str) -> dict[int, str]:
    """解析 /ToUnicode CMap 的 bfchar／bfrange。

    來源字碼限 1–2 位元組（本專案支援的字型）；展開總數有上限（P1 安全掃描 f005）。
    """
    if len(text) > MAX_CMAP_BYTES:
        raise LimitExceeded("cmap_size")
    mapping: dict[int, str] = {}
    budget = MAX_CODE_EXPANSION
    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(_HEX + r"\s*" + _HEX, block):
            if 0 < len(src) <= 4:
                mapping[int(src, 16)] = _utf16(dst)
    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        for lo, hi, rest in re.findall(
            _HEX + r"\s*" + _HEX + r"\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)", block
        ):
            if not (0 < len(lo) <= 4 and 0 < len(hi) <= 4):
                continue
            lo_i, hi_i = int(lo, 16), int(hi, 16)
            budget -= max(hi_i - lo_i + 1, 0)
            if budget < 0:
                raise LimitExceeded("cmap_entries")
            if rest.startswith("["):
                for i, dst in enumerate(re.findall(_HEX, rest)):
                    mapping[lo_i + i] = _utf16(dst)
                continue
            base = _utf16(rest[1:-1])
            if not base:
                continue
            for i in range(hi_i - lo_i + 1):
                code = ord(base[-1]) + i
                if code > 0x10FFFF:
                    break
                mapping[lo_i + i] = base[:-1] + chr(code)
    return mapping


def _load_to_unicode(font: pikepdf.Dictionary) -> dict[int, str] | None:
    stream = font.get("/ToUnicode")
    if not isinstance(stream, pikepdf.Stream):
        return None
    try:
        return parse_cmap(stream.read_bytes().decode("latin-1"))
    except (pikepdf.PdfError, ValueError):
        return {}


def _glyph_name_unicode(name: str) -> str | None:
    """Differences 的字形名稱：只接受 uniXXXX 與單一 ASCII 字母／數字，不猜測其他名稱。"""
    if re.fullmatch(r"uni[0-9A-Fa-f]{4}", name):
        return chr(int(name[3:], 16))
    if len(name) == 1 and name.isascii() and name.isalnum():
        return name
    return {"space": " ", "period": ".", "comma": ",", "hyphen": "-"}.get(name)
