"""視覺比對共用工具（spec §8.2；ADR-0015）。只用 Pillow，不依賴 numpy。

同引擎原／新比對：MuPDF、PDFium 各自以 150 DPI、RGB、無 alpha 渲染，逐像素比較。
遮罩：事前宣告的可改動區域（manifest／edit_cases 的 editable_region_pt）外擴 2 pt，換算到渲染像素。
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path

import pikepdf
import pymupdf
import pypdfium2
import pypdfium2.raw as pdfium_c
from PIL import Image, ImageChops, ImageDraw

from peditor.core.geometry import bbox_of
from peditor.worker import analyzer, edit, span

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FILES = FIXTURES / "files"
DPI = 150
ZOOM = DPI / 72
CHANNEL_TOL = 8  # 每通道差異 >8/255 才計入（spec §8.2）
OUTSIDE_LIMIT = 0.0001  # 改動區 +2 pt 外的超標像素比例 ≤0.01%（spec §8.2）
MARGIN_PT = 2.0
POSITION_TOL = 0.5  # 目標外框定位誤差（pt）
# ADR-0015：MuPDF 1.28.2 渲染空白的 7 份，視覺比對只以 PDFium 判定
MUPDF_BLANK = frozenset({"T01", "F01", "F02", "F05", "L02", "L03", "B01"})
BLANK_DARK_PIXELS = 100  # 亮度 <128 的像素少於此數視為空白頁


def manifest() -> dict[str, dict[str, str]]:
    with open(FIXTURES / "manifest.csv", encoding="utf-8", newline="") as fh:
        return {r["fixture_id"]: r for r in csv.DictReader(fh)}


def engines(fixture_id: str) -> tuple[str, ...]:
    return ("pdfium",) if fixture_id in MUPDF_BLANK else ("mupdf", "pdfium")


def render(engine: str, data: bytes, page_index: int = 0) -> Image.Image:
    if engine == "mupdf":
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            pix = doc[page_index].get_pixmap(dpi=DPI, alpha=False, colorspace=pymupdf.csRGB)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    pdf = pypdfium2.PdfDocument(data)
    try:
        return pdf[page_index].render(scale=ZOOM).to_pil().convert("RGB")
    finally:
        pdf.close()


def dark_pixels(image: Image.Image) -> int:
    return sum(image.convert("L").histogram()[:128])


def is_blank(image: Image.Image) -> bool:
    return dark_pixels(image) < BLANK_DARK_PIXELS


INK_DELTA = 64  # 與區域主色相差超過此值（任一通道）視為筆畫
INK_PIXELS = 20


def has_ink(image: Image.Image, box: tuple[int, int, int, int] | None = None) -> bool:
    """區域內是否有筆畫：與該區域最常見顏色（背景，可能是彩底）差異大的像素數。"""
    crop = image.crop(box) if box else image
    background = max(crop.getcolors(crop.size[0] * crop.size[1]))[1]
    solid = Image.new("RGB", crop.size, background)
    r, g, b = ImageChops.difference(crop, solid).split()
    peak = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return sum(peak.histogram()[INK_DELTA + 1 :]) >= INK_PIXELS


def text_box_pixels(
    data: bytes, page_index: int, bbox_pt: list[float]
) -> tuple[int, int, int, int]:
    """目標文字外框（頁面座標 pt）→ 渲染像素（向內取整並內縮）。"""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        geom = analyzer.page_geometry(pdf.pages[page_index])
    vx0, vy0, vx1, vy1 = bbox_of(geom.page_to_view(ZOOM), tuple(bbox_pt))
    # 內縮 3 像素：外框緊貼字形，避免把貼著外框的線條（例如 L03 的紅框）算成筆畫
    return math.ceil(vx0) + 3, math.ceil(vy0) + 3, math.floor(vx1) - 3, math.floor(vy1) - 3


def mask_pixels(data: bytes, page_index: int, region_pt: list[float]) -> tuple[int, int, int, int]:
    """頁面座標（pt）的可改動區域外擴 2 pt → 渲染像素矩形（含旋轉；向外取整）。"""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        geom = analyzer.page_geometry(pdf.pages[page_index])
    x0, y0, x1, y1 = region_pt
    grown = (x0 - MARGIN_PT, y0 - MARGIN_PT, x1 + MARGIN_PT, y1 + MARGIN_PT)
    vx0, vy0, vx1, vy1 = bbox_of(geom.page_to_view(ZOOM), grown)
    return math.floor(vx0), math.floor(vy0), math.ceil(vx1), math.ceil(vy1)


def diff_stats(before: Image.Image, after: Image.Image, mask=None) -> dict:
    """超過每通道門檻的像素數；mask 內與 mask 外分開計。"""
    if before.size != after.size:
        return {"size_mismatch": True}
    diff = ImageChops.difference(before, after)
    r, g, b = diff.split()
    peak = ImageChops.lighter(ImageChops.lighter(r, g), b)
    over = peak.point(lambda v: 255 if v > CHANNEL_TOL else 0)
    total_over = over.histogram()[255]
    outside = over.copy()
    if mask is not None:
        ImageDraw.Draw(outside).rectangle(mask, fill=0)
    outside_over = outside.histogram()[255]
    pixels = before.size[0] * before.size[1]
    return {
        "size_mismatch": False,
        "pixels": pixels,
        "over_total": total_over,
        "over_outside": outside_over,
        "outside_fraction": outside_over / pixels,
        "max_channel_diff": peak.getextrema()[1],
    }


def apply_manifest_edit(fixture_id: str, old: str, new: str, region: list[float], data=None):
    """以 worker 函式套用一次替換；回傳（原始位元組, 結果位元組, 計畫）。"""
    import tempfile

    tmp = None
    path = FILES / f"{fixture_id}.pdf"
    if data is not None:  # 測試內組合的文件（例如兩頁）
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            fh.write(data)
        path = tmp = Path(fh.name)
    document = analyzer.open_document(str(path))
    try:
        target = span.find(document, 0, old)
        params = {"target_id": target.span_id, "new_text": new, "editable_region": region}
        plan = edit.plan_text_edit(document, params)
        if not plan["ready"]:
            return document.original, None, plan
        edit.apply_edit(document, plan["plan_id"], document.revision)
        return document.original, document.working_bytes(), plan
    finally:
        document.close()
        if tmp is not None:
            tmp.unlink()


def char_origins(engine: str, data: bytes, text: str, page_index: int = 0) -> list[list]:
    """每個 text 出現位置的字元原點（頁面座標 pt）；以引擎自己的擷取結果尋找。"""
    if engine == "mupdf":
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            blocks = doc[page_index].get_text("rawdict")["blocks"]
            chars = [(c["c"], c["origin"]) for b in blocks for line in b.get("lines", [])
                     for s in line["spans"] for c in s["chars"]]  # fmt: skip
    else:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            to_page = analyzer.page_geometry(pdf.pages[page_index]).pdf_to_page()
        pdf = pypdfium2.PdfDocument(data)
        try:
            textpage = pdf[page_index].get_textpage()
            chars = []
            for i in range(textpage.count_chars()):
                x, y = pdfium_c.c_double(), pdfium_c.c_double()
                pdfium_c.FPDFText_GetCharOrigin(textpage.raw, i, x, y)
                ch = chr(pdfium_c.FPDFText_GetUnicode(textpage.raw, i))
                a, b, c, d, e, f = to_page
                chars.append((ch, (a * x.value + c * y.value + e, b * x.value + d * y.value + f)))
        finally:
            pdf.close()
    chars = [(ch, o) for ch, o in chars if not ch.isspace() and ch not in "\r\n\x00"]
    wanted = [ch for ch in text if not ch.isspace()]
    found = []
    seq = [ch for ch, _ in chars]
    for i in range(len(seq) - len(wanted) + 1):
        if seq[i : i + len(wanted)] == wanted:
            found.append([o for _, o in chars[i : i + len(wanted)]])
    return found
