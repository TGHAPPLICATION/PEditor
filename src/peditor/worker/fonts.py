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
    source: pikepdf.Dictionary | None = None  # 原字型物件（模式 A 檢查嵌入字形）
    _base14: pymupdf.Font | None = None
    _reverse: dict[str, list[int]] | None = None
    _outline: object = None  # 字碼 → 是否有字形的檢查函式（延遲載入）

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

    def encode(
        self, text: str, preferred: set[int] | frozenset[int] = frozenset()
    ) -> list[int] | None:
        """模式 A：把 text 逐字轉回本字型的字碼，且字形確實存在；任一字做不到回 None（不猜測）。

        同一字元有多個字碼時，優先用本頁已使用的字碼（preferred），否則取最小者。
        """
        if self.unsupported is not None or not (self.embedded or self._base14 is not None):
            return None
        if self._reverse is None:
            self._reverse = {}
            candidates = (
                self.to_unicode.items()
                if self.to_unicode is not None
                else ((code, self.unicode(code)) for code in ([] if self.two_byte else range(256)))
            )
            for code, uni in candidates:
                if uni and len(uni) == 1:
                    self._reverse.setdefault(uni, []).append(code)
        codes = []
        for ch in text:
            options = sorted(self._reverse.get(ch, []), key=lambda c: (c not in preferred, c))
            code = next((c for c in options if self.has_glyph(c, ch.isspace())), None)
            if code is None:
                return None
            codes.append(code)
        return codes

    def has_glyph(self, code: int, blank_ok: bool = False) -> bool:
        """字碼在字型中有字形（嵌入子集可能只留空字形）；blank_ok 時空白字形也算。"""
        if self._base14 is not None:
            uni = self.unicode(code)
            return bool(uni) and self._base14.has_glyph(ord(uni)) != 0
        if self._outline is None:
            self._outline = _outline_checker(self)
        try:
            return self._outline(code, blank_ok)
        except Exception:  # noqa: BLE001 — 延遲解析時才遇到畸形字形：視為沒有字形
            return False


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
    info.source = font
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
    info.source = font
    return info


def _outline_checker(info: FontInfo):
    """以 fontTools 讀嵌入字型程式，回傳 (code, blank_ok) → 是否有字形；無法判定一律 False。

    支援：Type0 的 FontFile2（CIDToGIDMap Identity 或 stream）、FontFile3 CIDFontType0C／OpenType；
    單位元組 TrueType（FontFile2，依 cmap (3,1)、(1,0)、(3,0) 查字形）。其他格式不做模式 A。
    """
    import io

    from fontTools.cffLib import CFFFontSet
    from fontTools.ttLib import TTFont

    def never(code: int, blank_ok: bool) -> bool:
        return False

    font = info.source
    if font is None:
        return never
    cid_font = None
    if info.two_byte:
        descendants = font.get("/DescendantFonts") or []
        cid_font = descendants[0] if len(descendants) else None
        holder = cid_font
    else:
        holder = font
    descriptor = holder.get("/FontDescriptor") if holder is not None else None
    if not isinstance(descriptor, pikepdf.Dictionary):
        return never
    try:
        if isinstance(descriptor.get("/FontFile2"), pikepdf.Stream):
            tt = TTFont(io.BytesIO(descriptor.FontFile2.read_bytes()), lazy=True)
            order = tt.getGlyphOrder()
            glyf = tt["glyf"]

            def glyph_name(code: int) -> str | None:
                if cid_font is not None:
                    gid_map = cid_font.get("/CIDToGIDMap")
                    if isinstance(gid_map, pikepdf.Stream):
                        data = gid_map.read_bytes()
                        gid = int.from_bytes(data[2 * code : 2 * code + 2], "big")
                    else:
                        gid = code
                    return order[gid] if 0 < gid < len(order) else None
                uni = info.unicode(code)
                for (pid, eid), key in (((3, 1), ord(uni) if uni else None), ((1, 0), code),
                                        ((3, 0), code), ((3, 0), 0xF000 + code)):  # fmt: skip
                    table = tt["cmap"].getcmap(pid, eid)
                    if key is not None and table is not None and key in table.cmap:
                        return table.cmap[key]
                return None

            def check(code: int, blank_ok: bool) -> bool:
                name = glyph_name(code)
                if name is None or name not in glyf:
                    return False
                return blank_ok or glyf[name].numberOfContours != 0

            return check
        file3 = descriptor.get("/FontFile3")
        if isinstance(file3, pikepdf.Stream):
            data = file3.read_bytes()
            if str(file3.get("/Subtype", "")) == "/OpenType":
                cff = TTFont(io.BytesIO(data), lazy=True)["CFF "].cff
            else:
                cff = CFFFontSet()
                cff.decompile(io.BytesIO(data), None)
            top = cff[cff.fontNames[0]]
            charstrings = top.CharStrings
            order = top.getGlyphOrder()
            # 字碼 → 字形：CID-keyed 依 charset（cidNNNNN）；部分產生器
            # （PyMuPDF＋fontTools 子集，見 U3、ADR-0015）實際以字碼為字形索引。
            # 依本字型 ToUnicode 已對應的字碼一致採用其中一種，否則不判定。
            mapped = [c for c in (info.to_unicode or {}) if c]
            by_cid = hasattr(top, "ROS") and all(f"cid{c:05d}" in charstrings for c in mapped)
            by_index = not by_cid and all(c < len(order) for c in mapped)
            if not info.two_byte or not mapped or not (by_cid or by_index):
                return never

            def check(code: int, blank_ok: bool) -> bool:
                if code == 0:
                    return False
                name = f"cid{code:05d}" if by_cid else (order[code] if code < len(order) else None)
                if name is None or name not in charstrings:
                    return False
                return blank_ok or charstrings[name].calcBounds(charstrings) is not None

            return check
    except Exception:  # noqa: BLE001 — 畸形字型程式：不做模式 A（不猜測）
        return never
    return never


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
