"""視覺與定位（G2-10、G2-11、G2-12、G2-16；spec §8.2、ADR-0015、ADR-0019）。

門檻依 P2 視覺基準（reports/P2/visual_baseline.json，G2-21）鎖定為 spec §8.2 原值：
每通道差 >8/255、改動區 +2 pt 外 ≤0.01%、未修改頁完全相同、目標定位 ≤0.5 pt。
"""

import csv
import difflib
import io

import pikepdf
import pypdfium2
import pypdfium2.raw as pdfium_c
import pytest
import visual
from PIL import ImageChops, ImageDraw

from peditor.core.geometry import bbox_of
from peditor.worker import analyzer

ORIGIN_TOL = 0.01  # pt


def _cases():
    rows = visual.manifest()
    supported = (
        "T01",
        "T02",
        "T08",
        "F01",
        "F04",
        "L02",
        "L03",  # 模式 A（test_edit_text.MODE_A）
        "T03",
        "T04",
        "T05",
        "T06",
        "T07",
        "F02",
        "F06",
        "F07",
        "L01",
        "L04",
        "L05",
    )
    cases = [(f, rows[f]["original_text"], rows[f]["new_text"], rows[f]["editable_region_pt"])
             for f in supported]  # fmt: skip
    with open(visual.FIXTURES / "edit_cases.csv", encoding="utf-8", newline="") as fh:
        cases += [(c["fixture_id"], c["original_text"], c["new_text"], c["editable_region_pt"])
                  for c in csv.DictReader(fh) if not c["after_case"]]  # fmt: skip
    return cases


def _region(text):
    return [float(v) for v in text.split(",")]


def _pdfium_chars(data: bytes):
    pdf = pypdfium2.PdfDocument(data)
    try:
        textpage = pdf[0].get_textpage()
        out = []
        for i in range(textpage.count_chars()):
            x, y = pdfium_c.c_double(), pdfium_c.c_double()
            pdfium_c.FPDFText_GetCharOrigin(textpage.raw, i, x, y)
            ch = chr(pdfium_c.FPDFText_GetUnicode(textpage.raw, i))
            if not ch.isspace():
                out.append((ch, x.value, y.value))
        return out
    finally:
        pdf.close()


def _adr0019_pdfium(original, result, plan, region, mask):
    """ADR-0019：PDFium 以位置驗證取代改動區外像素門檻（行外像素仍須為 0）。"""
    residual = abs(plan["geometry"]["pdfium_width_residual_pt"])
    before, after = _pdfium_chars(original), _pdfium_chars(result)
    with pikepdf.open(io.BytesIO(original)) as pdf:
        geom = analyzer.page_geometry(pdf.pages[0])
    baseline_pdf_y = geom.cropbox[3] - plan["geometry"]["baseline_start"][1]
    matcher = difflib.SequenceMatcher(a=[c[0] for c in before], b=[c[0] for c in after],
                                      autojunk=False)  # fmt: skip
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            _, x0, y0 = before[block.a + k]
            _, x1, y1 = after[block.b + k]
            same_line = abs(y0 - baseline_pdf_y) < plan["geometry"]["font_size"] / 2
            limit = residual + ORIGIN_TOL if same_line else ORIGIN_TOL
            assert abs(x1 - x0) <= limit and abs(y1 - y0) <= ORIGIN_TOL, (x0, x1, y0, y1)
    # 行外不得有任何超標像素：遮去改動區與目標所在行（垂直方向 ±2 pt）後必須為 0
    a, b = visual.render("pdfium", original), visual.render("pdfium", result)
    peak = ImageChops.difference(a, b).convert("RGB")
    r, g, bl = peak.split()
    over = ImageChops.lighter(ImageChops.lighter(r, g), bl).point(
        lambda v: 255 if v > visual.CHANNEL_TOL else 0
    )
    band = (geom.cropbox[0] - geom.cropbox[0], region[1] - visual.MARGIN_PT,
            geom.width, region[3] + visual.MARGIN_PT)  # fmt: skip
    draw = ImageDraw.Draw(over)
    draw.rectangle(mask, fill=0)
    draw.rectangle(tuple(int(v) for v in bbox_of(geom.page_to_view(visual.ZOOM), band)), fill=0)
    assert over.histogram()[255] == 0


@pytest.mark.parametrize(("fid", "old", "new", "region"), _cases())
def test_changed_page_outside_mask_threshold(fid, old, new, region):
    """G2-11：改動區 +2 pt 外每通道差 >8/255 的像素 ≤0.01%（同引擎原／新比對）。"""
    original, result, plan = visual.apply_manifest_edit(fid, old, new, _region(region))
    assert result is not None, plan["unsupported_reasons"]
    mask = visual.mask_pixels(original, 0, _region(region))
    residual = plan["geometry"]["pdfium_width_residual_pt"]
    for engine in visual.engines(fid):
        if engine == "pdfium" and residual and fid not in visual.MUPDF_BLANK:
            _adr0019_pdfium(original, result, plan, _region(region), mask)
            continue
        stats = visual.diff_stats(
            visual.render(engine, original), visual.render(engine, result), mask
        )
        assert not stats["size_mismatch"]
        assert stats["outside_fraction"] <= visual.OUTSIDE_LIMIT, (engine, stats)
        assert stats["over_total"] > 0, (engine, "改動區內應有可見變化")


@pytest.mark.parametrize(("fid", "old", "new", "region"), _cases())
def test_target_bbox_within_half_point(fid, old, new, region):
    """G2-12：兩引擎擷取的新文字原點：起點與計畫基線起點差 ≤0.5 pt，且全在計畫基線範圍內。"""
    _, result, plan = visual.apply_manifest_edit(fid, old, new, _region(region))
    start, end = plan["geometry"]["baseline_start"], plan["geometry"]["baseline_end"]
    changed = plan["target"]["change"]["new_text"]
    for engine in ("mupdf", "pdfium"):
        occurrences = visual.char_origins(engine, result, changed)
        assert occurrences, engine
        best = min(occurrences, key=lambda o: abs(o[0][0] - start[0]) + abs(o[0][1] - start[1]))
        assert abs(best[0][0] - start[0]) <= visual.POSITION_TOL, (engine, best[0], start)
        for x, y in best:
            assert abs(y - start[1]) <= visual.POSITION_TOL, (engine, y, start)
            assert start[0] - visual.POSITION_TOL <= x <= end[0] + visual.POSITION_TOL


@pytest.mark.parametrize(
    ("first", "old", "new"), [("F04", "Hello", "Hi"), ("T02", "10 月 31 日", "10 月 13 日")]
)
def test_untouched_pages_pixel_identical(first, old, new):
    """G2-10：多頁文件中未修改的頁，同引擎渲染像素完全相同（測試內以 T07 組成第 2 頁）。"""
    with pikepdf.open(visual.FILES / f"{first}.pdf") as pdf, \
            pikepdf.open(visual.FILES / "T07.pdf") as other:  # fmt: skip
        pdf.pages.append(other.pages[0])
        buf = io.BytesIO()
        pdf.save(buf)
    combined = buf.getvalue()
    region = [0.0, 0.0, 595.0, 842.0]
    original, result, plan = visual.apply_manifest_edit(first, old, new, region, data=combined)
    assert result is not None, plan["unsupported_reasons"]
    for engine in ("mupdf", "pdfium"):
        a, b = visual.render(engine, original, 1), visual.render(engine, result, 1)
        assert not visual.is_blank(a)
        assert ImageChops.difference(a, b).getbbox() is None, engine


def test_mupdf_blank_exceptions_fixed():
    """G2-16（ADR-0015）：MuPDF 不畫出目標文字的只限 7 份，且 PDFium 畫得出；
    其他 T／F／L／B support 的目標文字 MuPDF 畫得出（例外清單不得擴大）。"""
    skip = {"ENCRYPTED_DOCUMENT", "MALFORMED_DOCUMENT"}
    for fid, row in visual.manifest().items():
        if row["status"] != "available" or row["reason_code"] in skip:
            continue
        listed = fid in visual.MUPDF_BLANK
        if not listed and not (row["expected"] == "support" and fid[0] in "TFLB"):
            continue
        data = (visual.FILES / f"{fid}.pdf").read_bytes()
        page = int(row["page_index"] or 0)
        # 目標文字外框內是否有筆畫；沒有目標外框（F05）時看整頁
        box = (
            visual.text_box_pixels(data, page, _region(row["bbox_pt"])) if row["bbox_pt"] else None
        )
        assert visual.has_ink(visual.render("mupdf", data, page), box) != listed, fid
        assert visual.has_ink(visual.render("pdfium", data, page), box), fid
