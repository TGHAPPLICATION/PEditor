"""改動跨同一 BT 內相鄰的多段文字運算子（G2-18、G2-19、G2-11；ADR-0018 §1、§2）。

既有 fixture 縮小到實際改動範圍後都只涉及一段運算子，故以測試內產生的 Helvetica 樣本驗證。
"""

import io

import pikepdf
import pytest
import visual

from peditor.worker import analyzer, edit, span
from peditor.worker.content import interpret

ORIGIN_TOL = 0.01  # pt


def _sample(tmp_path, content: bytes, name="m.pdf"):
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(400, 200))
    fonts = pikepdf.Dictionary()
    for key, base in (("F1", "Helvetica"), ("F2", "Times-Roman")):
        fonts[f"/{key}"] = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name(f"/{base}"),
            Encoding=pikepdf.Name.WinAnsiEncoding))  # fmt: skip
    pdf.pages[0].Resources = pikepdf.Dictionary(Font=fonts)
    pdf.pages[0].Contents = pdf.make_stream(content)
    path = tmp_path / name
    pdf.save(path)
    return path


def _origins(document, text):
    """依內容尋找 text 的字形原點（PDF 空間）。"""
    glyphs = [g for r in interpret(document.pike.pages[0]).runs for g in r.glyphs]
    chars = "".join(g.unicode or "\x00" for g in glyphs)
    pos = chars.index(text)
    return [g.origin for g in glyphs[pos : pos + len(text)]]


CASES = [
    # 兩段：「Hel」「lo」→ 改動「ello」跨兩段；後續「 World」不得移動
    (b"BT /F1 24 Tf 72 100 Td (Hel) Tj (lo) Tj ( World) Tj ET", "Hello", "Howdy", " World", 2,
     "Howdy World"),
    # 三段、含原有 TJ 位移與段間狀態運算子（色彩、Tc）；改動「BCD」跨三段，「E」與「 tail」不得移動
    (b"BT /F1 24 Tf 72 100 Td [(A) -50 (B)] TJ 0 g (C) Tj 1 Tc [(D) 20 (E)] TJ 0 Tc ( tail) Tj ET",
     "ABCDE", "AxyzE", "E tail", 3, "AxyzE tail"),
    # 新文較長
    (b"BT /F1 24 Tf 72 100 Td (Hel) Tj (lo) Tj ( World) Tj ET", "Hello", "Hi there", " World", 2,
     "Hi there World"),
]  # fmt: skip


@pytest.mark.parametrize(("content", "old", "new", "tail", "pieces", "expected"), CASES)
def test_multi_operator_change(tmp_path, content, old, new, tail, pieces, expected):
    path = _sample(tmp_path, content)
    document = analyzer.open_document(str(path))
    try:
        original = document.working_bytes()
        tail_before = _origins(document, tail)
        target = span.find(document, 0, old)
        plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": new,
                                              "editable_region": [0, 0, 400, 200]})  # fmt: skip
        assert plan["ready"] and plan["mode"] == "A", plan["unsupported_reasons"]
        assert len(plan["target"]["change"]["target_ids"]) == pieces
        edit.apply_edit(document, plan["plan_id"], 0)
        result = document.working_bytes()
        tail_after = _origins(document, tail)
        for (x0, y0), (x1, y1) in zip(tail_before, tail_after, strict=True):
            assert abs(x0 - x1) <= ORIGIN_TOL and abs(y0 - y1) <= ORIGIN_TOL  # G2-19
    finally:
        document.close()
    # 改動區：計畫的新字起點到「新字終點、原改動終點（後續文字起點）」較遠者；頁面座標 y 向下
    start_x = plan["geometry"]["baseline_start"][0]
    end_x = max(plan["geometry"]["baseline_end"][0], tail_before[0][0])
    region = [start_x, 100 - 24, end_x, 100 + 8]
    mask = visual.mask_pixels(original, 0, region)
    for engine in ("mupdf", "pdfium"):
        assert visual.char_origins(engine, result, expected), engine  # 兩引擎擷取到新文＋後續
        stats = visual.diff_stats(visual.render(engine, original), visual.render(engine, result),
                                  mask)  # fmt: skip
        assert stats["outside_fraction"] == 0, (engine, stats)  # G2-11（此樣本可達 0）
        assert stats["over_total"] > 0, engine
    with pikepdf.open(io.BytesIO(result)) as pdf:
        assert pdf.check_pdf_syntax() == []


@pytest.mark.parametrize(("content", "reason"), [
    (b"BT /F1 24 Tf 72 100 Td (Hel) Tj 30 0 Td (lo) Tj ET", "UNSUPPORTED_LAYOUT"),  # 段間移位
    (b"BT /F1 24 Tf 72 100 Td (Hel) Tj /F2 24 Tf (lo) Tj ET", "UNSUPPORTED_LAYOUT"),  # 段間換字型
    (b"BT /F1 24 Tf 72 100 Td (Hel) Tj /F1 20 Tf (lo) Tj ET", "UNSUPPORTED_LAYOUT"),  # 字級不同
    (b"BT /F1 24 Tf 72 100 Td /Span <</MCID 0>> BDC (Hel) Tj EMC "
     b"/Span <</MCID 1>> BDC (lo) Tj EMC ET", "UNSUPPORTED_FEATURE"),  # 跨標記內容（ADR-0017）
    (b"BT /F1 24 Tf 72 100 Td (Hel) Tj ET BT /F1 24 Tf 108 100 Td (lo) Tj ET",
     "UNSUPPORTED_LAYOUT"),  # 跨 BT
])  # fmt: skip
def test_multi_operator_rejections(tmp_path, content, reason):
    path = _sample(tmp_path, content)
    document = analyzer.open_document(str(path))
    try:
        working = document.working_bytes()
        target = span.find(document, 0, "Hello")
        plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": "Howdy",
                                              "editable_region": [0, 0, 400, 200]})  # fmt: skip
        assert not plan["ready"] and reason in plan["unsupported_reasons"], plan
        assert document.working_bytes() == working and document.revision == 0
    finally:
        document.close()
