"""G6-04 輔助：格線推估（ADR-0023）——三種畫線方式、合併格、未封閉區域、斜線與 Form 內線段、上限。"""

import pikepdf
import pytest

from peditor.core.geometry import IDENTITY
from peditor.worker import table
from peditor.worker.content import FilledRect, PageContent, Stroke, interpret


def _grid_strokes(xs, ys, skip=(), width=1.0, form_path=()):
    """以描邊線段畫網格（PDF 空間＝頁面空間，to_page 用 IDENTITY）；skip 為不畫的線段鍵。"""
    content = PageContent()
    for i, y in enumerate(ys):
        for j in range(len(xs) - 1):
            if ("h", i, j) not in skip:
                content.strokes.append(Stroke((xs[j], y), (xs[j + 1], y), width, form_path))
    for j, x in enumerate(xs):
        for i in range(len(ys) - 1):
            if ("v", j, i) not in skip:
                content.strokes.append(Stroke((x, ys[i]), (x, ys[i + 1]), width, form_path))
    return content


def _cells(content):
    return table.detect(table.rules(content, IDENTITY))


def test_regular_grid_and_line_width():
    cells = _cells(_grid_strokes([0, 100, 200, 300], [0, 30, 60], width=2.0))
    assert [(c.row, c.col, c.row_span, c.col_span) for c in cells] == [
        (r, c, 1, 1) for r in range(2) for c in range(3)
    ]
    assert cells[0].bbox == [0, 0, 100, 30] and cells[0].inner == [1, 1, 99, 29]


def test_thin_filled_rects_same_as_strokes():
    """Word 以 0.48 pt 細矩形畫框線（片段之間有小間隙、交點另有小方塊）：與描邊結果相同。"""
    content = PageContent()
    t = 0.48
    for y in (0, 30, 60):
        for x0, x1 in ((0.5, 99.5), (100.5, 199.5)):
            content.filled_rects.append(
                FilledRect([(x0, y), (x1, y), (x1, y + t), (x0, y + t)], ())
            )
        for x in (0, 100, 200):
            content.filled_rects.append(
                FilledRect([(x, y), (x + t, y), (x + t, y + t), (x, y + t)], ())
            )
    for x in (0, 100, 200):
        for y0, y1 in ((0.5, 29.5), (30.5, 59.5)):
            content.filled_rects.append(
                FilledRect([(x, y0), (x + t, y0), (x + t, y1), (x, y1)], ())
            )
    cells = _cells(content)
    assert [(c.row, c.col) for c in cells] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert all(c.row_span == c.col_span == 1 for c in cells)


def test_merged_cell_and_open_region():
    """第 2 列中間的直線不畫 → 合併格（1×2）；最左邊缺一段框線 → 該區域不成格。"""
    xs, ys = [0, 100, 200, 300], [0, 30, 60, 90]
    cells = _cells(_grid_strokes(xs, ys, skip={("v", 1, 1)}))
    merged = next(c for c in cells if (c.row, c.col) == (1, 0))
    assert (merged.row_span, merged.col_span) == (1, 2) and merged.bbox == [0, 30, 200, 60]
    assert len(cells) == 8
    cells = _cells(_grid_strokes(xs, ys, skip={("v", 0, 2)}))
    assert (2, 0) not in {(c.row, c.col) for c in cells} and len(cells) == 8


def test_diagonal_form_and_thick_rects_ignored():
    content = _grid_strokes([0, 100, 200], [0, 30, 60])
    content.strokes.append(Stroke((0, 0), (100, 30), 1.0, ()))  # 斜線
    content.filled_rects.append(FilledRect([(10, 5), (90, 5), (90, 25), (10, 25)], ()))  # 底色
    assert len(_cells(content)) == 4
    assert _cells(_grid_strokes([0, 100, 200], [0, 30, 60], form_path=("Fm0@1,0",))) == []


def test_limits(monkeypatch):
    monkeypatch.setattr(table, "MAX_TABLE_CELLS", 3)
    assert _cells(_grid_strokes([0, 100, 200, 300], [0, 30, 60])) == []
    found = table.rules(PageContent(paths_truncated=True), IDENTITY)
    assert found.truncated and table.detect(found) == []
    monkeypatch.setattr(table, "MAX_RULE_PAIRS", 3)  # 2 條水平 × 2 條垂直＝4 組交會判定
    found = table.rules(_grid_strokes([0, 100], [0, 30]), IDENTITY)
    assert found.truncated and table.detect(found) == []


def test_interpreter_records_paths(monkeypatch):
    """content 解譯器：描邊、描邊的 re、填色 re 都記錄；曲線與只建路徑（n）不記錄；
    超過上限即截斷。"""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(300, 300))
    pdf.pages[0].Contents = pdf.make_stream(
        b"2 w 10 10 m 100 10 l S 20 20 50 30 re S 0 0 10 0.5 re f "
        b"0 0 m 10 10 20 0 30 30 c S 5 5 10 10 re n"
    )
    content = interpret(pdf.pages[0])
    assert len(content.strokes) == 1 + 4 and content.strokes[0].width == 2.0
    assert len(content.filled_rects) == 1 and not content.paths_truncated
    monkeypatch.setattr("peditor.worker.content.MAX_RULE_PATHS", 2)
    assert interpret(pdf.pages[0]).paths_truncated


@pytest.mark.parametrize("box,ok", [
    ([1, 1, 99, 29], True),  # 一格之內
    ([1, 1, 199, 29], False),  # 跨兩格（中間有線）
    ([-50, -50, -10, -10], False),  # 框內沒有文字
])  # fmt: skip
def test_assess_box(box, ok):
    found = table.rules(_grid_strokes([0, 100, 200], [0, 30, 60]), IDENTITY)
    cells = table.detect(found)
    text = [{"target_id": "t1", "text": "A", "bbox": [10, 10, 20, 20],
             "capability": {"status": "support", "reasons": []}}]  # fmt: skip
    result = table.assess_box(box, found, cells, text, [])
    assert (result["capability"]["status"] == "support") is ok
