"""P2 安全掃描確認的 3 項（reports/P2/security/TRIAGE.md）回歸測試。

每項以腳本產生的最小 PDF 驗證：f004 新字畫在計畫的起點；f002／f012 共用的 content stream
拒絕為 SHARED_RESOURCE_UNSAFE；f014 未改動的大量相同運算子不進入平方級比對。
"""

import io
import re
import time

import pikepdf
import pytest

from peditor.worker import analyzer, edit, export, span
from peditor.worker.content import interpret

FAST = 10.0  # 秒
REGION = [0, 0, 400, 200]


def _without_id(data: bytes) -> bytes:
    """trailer /ID 第二元素每次存檔不同（跨秒時）；比對位元組時排除（P2 U3）。"""
    return re.sub(rb"/ID\s*\[\s*<[0-9A-Fa-f]*>\s*<[0-9A-Fa-f]*>\s*\]", b"", data)


def _pdf(content: bytes, pages: int = 1) -> tuple[pikepdf.Pdf, pikepdf.Stream]:
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica,
        Encoding=pikepdf.Name.WinAnsiEncoding))  # fmt: skip
    for _ in range(pages):
        pdf.add_blank_page(page_size=(400, 200))
        pdf.pages[-1].Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    stream = pdf.make_stream(content)
    pdf.pages[0].Contents = stream
    return pdf, stream


def _plan(tmp_path, pdf: pikepdf.Pdf, old: str, new: str):
    path = tmp_path / "s.pdf"
    pdf.save(path)
    document = analyzer.open_document(str(path))
    target = span.find(document, 0, old)
    plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": new,
                                          "editable_region": REGION})  # fmt: skip
    return document, plan


def test_f004_insertion_after_trailing_tj_number_drawn_at_planned_start(tmp_path):
    pdf, _ = _pdf(b"BT /F1 24 Tf 72 100 Td [(Amount:) -6000] TJ ET")
    document, plan = _plan(tmp_path, pdf, "Amount:", "Amount:9")
    try:
        assert plan["ready"] and plan["mode"] == "A", plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        glyphs = [g for r in interpret(document.pike.pages[0]).runs for g in r.glyphs]
        nine = next(g for g in glyphs if g.unicode == "9")
        # 頁面無旋轉、無裁切：頁面 x 與 PDF x 相同（修正前新字落在 144 pt 之外）
        assert abs(nine.origin[0] - plan["geometry"]["baseline_start"][0]) <= 0.01
    finally:
        document.close()


def _same_page_twice(pdf, stream):
    pdf.pages[0].Contents = pikepdf.Array([stream, stream])


def _form_on_other_page(pdf, stream):
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Form
    stream.BBox = pikepdf.Array([0, 0, 400, 200])
    stream.Resources = pdf.pages[0].Resources
    pdf.pages[1].Resources.XObject = pikepdf.Dictionary(X0=stream)
    pdf.pages[1].Contents = pdf.make_stream(b"/X0 Do")


def _annotation_appearance(pdf, stream):
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Form
    stream.BBox = pikepdf.Array([0, 0, 400, 200])
    annot = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Square,
                               Rect=pikepdf.Array([0, 0, 10, 10]),
                               AP=pikepdf.Dictionary(N=stream))  # fmt: skip
    pdf.pages[1].Annots = pikepdf.Array([pdf.make_indirect(annot)])


@pytest.mark.parametrize("share", [_same_page_twice, _form_on_other_page, _annotation_appearance])
def test_f002_shared_content_stream_rejected(tmp_path, share):
    pdf, stream = _pdf(b"BT /F1 24 Tf 72 100 Td (Hello) Tj ET", pages=2)
    share(pdf, stream)
    document, plan = _plan(tmp_path, pdf, "Hello", "Howdy")
    try:
        working = document.working_bytes()
        assert not plan["ready"] and "SHARED_RESOURCE_UNSAFE" in plan["unsupported_reasons"], plan
        assert (
            _without_id(document.working_bytes()) == _without_id(working) and document.revision == 0
        )
    finally:
        document.close()


def test_f014_identical_operators_diffed_linearly():
    # 未改動的 50,000 組相同路徑運算子（修正前每次匯出都在比對中逾時）
    pdf, _ = _pdf(b"0 0 m 1 1 l S\n" * 50_000 + b"BT /F1 24 Tf 72 100 Td (Hello) Tj ET")
    before = _bytes(pdf)
    pdf.pages[0].Contents.write(pdf.pages[0].Contents.read_bytes().replace(b"(Hello)", b"(Howdy)"))
    after = _bytes(pdf)
    started = time.monotonic()
    assert export.content_diff(before, before) == []
    changes = export.content_diff(before, after)
    assert time.monotonic() - started < FAST
    assert len(changes) == 1 and changes[0]["kind"] == "replace"
    assert changes[0]["before"] == ["(Hello) Tj"] and changes[0]["after"] == ["(Howdy) Tj"]
    assert changes[0]["before_ops"] == [150_003, 150_004]


def _bytes(pdf: pikepdf.Pdf) -> bytes:
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()
