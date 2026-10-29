"""P3 安全掃描確認項目之回歸（reports/P3/security/TRIAGE.md）。"""

import time

import pikepdf
import pymupdf

from peditor.worker import analyzer, edit, export, span


def _huge_page(tmp_path):
    """14400 pt 見方的頁面上，字級 3000 的兩個數字。"""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(14400, 14400))
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica,
        Encoding=pikepdf.Name.WinAnsiEncoding))  # fmt: skip
    pdf.pages[0].Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    pdf.pages[0].Contents = pdf.make_stream(b"BT /F1 3000 Tf 1000 6000 Td (00) Tj ET")
    path = tmp_path / "huge.pdf"
    pdf.save(path)
    return path


def test_f015_visual_check_bounded_on_huge_page(tmp_path):
    """f015：大頁面、大字級改一個字時，遮罩內的像素不逐點走訪，渲染像素有上限。
    本機實測：修正前（50 MP、逐點）14.5 秒，同頁改字或多頁即超過 30 秒逾時；修正後 0.4 秒。"""
    document = analyzer.open_document(str(_huge_page(tmp_path)))
    try:
        target = span.find(document, 0, "00")
        plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": "11"})
        assert plan["ready"], plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        data = document.working_bytes()
        start = time.perf_counter()
        assert export.visual_check(document, data, {0}) == []
        assert time.perf_counter() - start < 10
    finally:
        document.close()


def _pixmap(width, height, pixels):
    return pymupdf.Pixmap(pymupdf.csRGB, width, height, bytes(pixels), False)


def test_f015_outside_count_matches_per_pixel_definition():
    """區段比對與提早結束不改變計數結果（門檻內）。"""
    width, height = 40, 10
    a = bytearray(width * height * 3)
    b = bytearray(a)
    for x, y, delta in [(1, 1, 9), (5, 2, 8), (20, 3, 200), (35, 9, 30), (12, 5, 100)]:
        b[(y * width + x) * 3 + 1] = delta
    before, after = _pixmap(width, height, a), _pixmap(width, height, b)
    masks = [(10, 4, 25, 6)]  # 涵蓋 (12, 5)
    # 逐點定義：差異 >8 且不在遮罩內 → (1,1)、(20,3)、(35,9)
    assert export._outside_pixels(before, after, masks, 100) == 3
    assert export._outside_pixels(before, after, masks, 1) == 2  # 超過門檻即停止
    assert export._outside_pixels(before, after, [], 100) == 4
