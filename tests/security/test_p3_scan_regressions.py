"""P3 安全掃描確認項目之回歸（reports/P3/security/TRIAGE.md）。

f015 的檢查不用牆鐘時間（機器負載不同，修正前耗時 4～15 秒不等），改驗證工作量的上限本身：
渲染像素不超過上限、遮罩內像素不逐點讀取、超標即停止。修正前三項都會失敗。
"""

from types import SimpleNamespace

import pikepdf
import pymupdf

from peditor.worker import analyzer, edit, export, span

PIXEL_BUDGET = 12_000_000  # f015 修補訂定的視覺驗證渲染上限


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


def test_f015_visual_check_render_budget(tmp_path, monkeypatch):
    """大頁面的視覺驗證以較低 DPI 渲染，像素數不超過上限（修正前為 50 MP）；結果仍正確。"""
    sizes = []
    original = pymupdf.Page.get_pixmap

    def recording(self, *args, **kwargs):
        pix = original(self, *args, **kwargs)
        sizes.append(pix.width * pix.height)
        return pix

    document = analyzer.open_document(str(_huge_page(tmp_path)))
    try:
        target = span.find(document, 0, "00")
        plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": "11"})
        assert plan["ready"], plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        data = document.working_bytes()
        monkeypatch.setattr(pymupdf.Page, "get_pixmap", recording)
        assert export.visual_check(document, data, {0}) == []
    finally:
        document.close()
    assert len(sizes) == 2 and max(sizes) <= PIXEL_BUDGET


class _CountingBytes(bytes):
    """記錄逐位元組（整數索引）讀取次數；切片讀取不計。"""

    reads = 0

    def __getitem__(self, key):
        if isinstance(key, int):
            type(self).reads += 1
        return super().__getitem__(key)


def _pixmap(width, height, pixels, counting=False):
    samples = _CountingBytes(pixels) if counting else bytes(pixels)
    return SimpleNamespace(width=width, height=height, stride=width * 3, samples=samples)


def test_f015_mask_pixels_not_visited():
    """所有差異都在遮罩內時，不逐點讀取任何像素（修正前每個不同列都逐點讀取整列）。"""
    width, height = 200, 50
    a = bytes(width * height * 3)
    b = bytes([255]) * (width * height * 3)  # 每個像素都不同
    _CountingBytes.reads = 0
    before = _pixmap(width, height, a, counting=True)
    after = _pixmap(width, height, b, counting=True)
    assert export._outside_pixels(before, after, [(0, 0, width, height)], 10) == 0
    assert _CountingBytes.reads == 0


def test_f015_outside_count_matches_per_pixel_definition():
    """區段比對與提早結束不改變計數結果；超過門檻即停止。"""
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
