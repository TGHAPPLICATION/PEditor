"""模式 B 重建字型：Noto Sans TC 子集嵌入（ADR-0008、ADR-0018 §4；只在 worker 使用）。

嵌入方式：fontTools 子集化（只含新文用字）後，把 CID-keyed CFF 的 charset
重新編號為「CID＝字形索引」，
以裸 CFF（FontFile3 /CIDFontType0C）＋ Identity-H 嵌入。字碼、CID、字形索引三者一致，
不論閱讀器以 CID 查 charset 或直接當字形索引都得到同一字形
（P0 fixture 的 MuPDF 空白問題見 U3、ADR-0015）。

字型檔不入庫（ADR-0008）：依序找環境變數 PEDITOR_MODE_B_FONT、套件內 resources/fonts/（P8 打包），
並驗證 SHA-256；找不到或不符時模式 B 不可用。
"""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

import pikepdf

FONT_FILE = "NotoSansTC-Regular.otf"
FONT_NAME = "NotoSansTC-Regular"
FONT_SHA256 = "5bab0cb3c1cf89dde07c4a95a4054b195afbcfe784d69d75c340780712237537"  # ADR-0008
ENV = "PEDITOR_MODE_B_FONT"

_state: dict = {}


def _candidates() -> list[Path]:
    paths = []
    if os.environ.get(ENV):
        paths.append(Path(os.environ[ENV]))
    paths.append(Path(__file__).resolve().parents[1] / "resources" / "fonts" / FONT_FILE)
    return paths


def _font_bytes() -> bytes | None:
    if "bytes" not in _state:
        _state["bytes"] = None
        for path in _candidates():
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if hashlib.sha256(data).hexdigest() == FONT_SHA256:
                _state["bytes"] = data
                break
    return _state["bytes"]


def available() -> bool:
    return _font_bytes() is not None


def _metrics():
    """cmap、字寬（千分之一 em）與字型度量；只讀一次。"""
    if "metrics" not in _state:
        from fontTools.ttLib import TTFont

        tt = TTFont(io.BytesIO(_font_bytes()), lazy=True)
        upm = tt["head"].unitsPerEm
        scale = 1000.0 / upm
        hmtx = tt["hmtx"]
        head, hhea, os2 = tt["head"], tt["hhea"], tt["OS/2"]
        _state["metrics"] = {
            "cmap": tt.getBestCmap(),
            "width": lambda name: hmtx[name][0] * scale,
            "bbox": [round(v * scale) for v in (head.xMin, head.yMin, head.xMax, head.yMax)],
            "ascent": round(hhea.ascent * scale),
            "descent": round(hhea.descent * scale),
            "cap_height": round(getattr(os2, "sCapHeight", 700) * scale),
        }
    return _state["metrics"]


def missing(text: str) -> list[str]:
    """Noto Sans TC 沒有字形的字元（例如 𠮷；ADR-0008）。"""
    cmap = _metrics()["cmap"]
    return [ch for ch in dict.fromkeys(text) if ord(ch) not in cmap]


def widths(text: str) -> list[float]:
    """每個字元的字寬（千分之一 em）。"""
    m = _metrics()
    return [m["width"](m["cmap"][ord(ch)]) for ch in text]


def build_font(pdf: pikepdf.Pdf, text: str) -> tuple[pikepdf.Object, list[int]]:
    """產生只含 text 用字的 Type0 字型物件；回傳（字型, 每個字元的字碼）。"""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    cmap = _metrics()["cmap"]
    names = [cmap[ord(ch)] for ch in text]
    tt = TTFont(io.BytesIO(_font_bytes()))
    options = subset.Options()
    options.desubroutinize = True
    options.notdef_outline = True
    options.name_IDs = []
    options.layout_features = []
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=[ord(ch) for ch in dict.fromkeys(text)])
    subsetter.subset(tt)
    order = tt.getGlyphOrder()
    cff = tt["CFF "].cff
    top = cff[cff.fontNames[0]]
    renamed = {old: (".notdef" if i == 0 else f"cid{i:05d}") for i, old in enumerate(order)}
    top.CharStrings.charStrings = {renamed[k]: v for k, v in top.CharStrings.charStrings.items()}
    top.charset = [renamed[g] for g in top.charset]
    buf = io.BytesIO()
    cff.compile(buf, tt)
    codes = [order.index(name) for name in names]

    m = _metrics()
    tag = "".join(chr(65 + b % 26) for b in hashlib.sha256(text.encode("utf-8")).digest()[:6])
    base = pikepdf.Name(f"/{tag}+{FONT_NAME}")
    descriptor = pikepdf.Dictionary(
        Type=pikepdf.Name.FontDescriptor, FontName=base, Flags=4, FontBBox=m["bbox"],
        ItalicAngle=0, Ascent=m["ascent"], Descent=m["descent"], CapHeight=m["cap_height"],
        StemV=80, FontFile3=pdf.make_stream(buf.getvalue(), Subtype=pikepdf.Name("/CIDFontType0C")),
    )  # fmt: skip
    w = pikepdf.Array()
    for code, name in sorted(set(zip(codes, names, strict=True))):
        w.extend([code, pikepdf.Array([round(m["width"](name), 3)])])
    cid_font = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.CIDFontType0, BaseFont=base,
        CIDSystemInfo=pikepdf.Dictionary(Registry="Adobe", Ordering="Identity", Supplement=0),
        FontDescriptor=pdf.make_indirect(descriptor), W=w, DW=1000,
    )  # fmt: skip
    font = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0, BaseFont=base,
        Encoding=pikepdf.Name("/Identity-H"), DescendantFonts=[pdf.make_indirect(cid_font)],
        ToUnicode=pdf.make_stream(_to_unicode(dict(zip(codes, text, strict=True)))),
    )  # fmt: skip
    return pdf.make_indirect(font), codes


def _to_unicode(mapping: dict[int, str]) -> bytes:
    lines = [f"<{code:04X}> <{ch.encode('utf-16-be').hex().upper()}>" for code, ch in
             sorted(mapping.items())]  # fmt: skip
    body = "\n".join(
        f"{len(chunk)} beginbfchar\n" + "\n".join(chunk) + "\nendbfchar"
        for chunk in (lines[i : i + 100] for i in range(0, len(lines), 100))
    )
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        f"{body}\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    ).encode("ascii")
