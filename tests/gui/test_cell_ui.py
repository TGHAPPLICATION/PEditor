"""G6-07：桌面儲存格編輯流程 E2E（pytest-qt、offscreen、真的 DocumentService 與 worker）。"""

import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, Qt
from test_e2e import apply, open_file, preview, wait

from peditor.core.geometry import PageGeometry
from peditor.ui.app import PAGE_DPI
from peditor.ui.messages import reason_text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from cell_samples import cell_box, table_pdf  # noqa: E402

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def click_cell_text(qtbot, window, text):
    """點格內文字：選取的是儲存格（target_id 為 cell_id），不是單一文字目標。"""
    target = next(t for t in window.page["text_targets"] if text in t["text"])
    rect = window.view.target_rect(target["target_id"])
    pos = window.view.mapFromScene(rect.center())
    qtbot.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(pos))
    assert window.selection is not None and window.selection["kind"] == "cell"


def _cell_text(window, row, col):
    cell = next(c for c in window.page["cell_targets"] if (c["row"], c["col"]) == (row, col))
    return [line["text"] for line in cell["lines"]]


def test_flow_cell_edit_preview_apply(qtbot, make_window):
    """B04：點格內文字 → 儲存格編輯（顯示列欄）→ 預覽 → 套用；格內其他格不變。"""
    window = make_window()
    open_file(qtbot, window, FILES / "B04.pdf")
    click_cell_text(qtbot, window, "300")
    assert window.selection["kind"] == "cell"
    assert window.panel.selected.text() == "表格第 3 列第 2 欄：300"
    assert not window.panel.line_choice.isVisible()
    preview(qtbot, window, "250")
    assert window.plan is not None and window.plan["ready"]
    assert window.plan["target"]["cell"]["row"] == 2
    apply(qtbot, window)
    assert _cell_text(window, 2, 1) == ["250"] and _cell_text(window, 1, 1) == ["12"]


def test_flow_multiline_and_merged_cells(qtbot, make_window):
    """B05 多行格顯示行選擇；B06 合併格顯示原因、不能預覽。"""
    window = make_window()
    open_file(qtbot, window, FILES / "B05.pdf")
    click_cell_text(qtbot, window, "第二行")
    choice = window.panel.line_choice
    assert choice.isVisible() and choice.count() == 2 and choice.currentIndex() == 1
    choice.setCurrentIndex(0)
    assert window.selection["line_index"] == 0 and window.panel.new_text.text() == "第一行"

    open_file(qtbot, window, FILES / "B06.pdf")
    click_cell_text(qtbot, window, "合併格")
    assert window.panel.info.text() == "無法編輯：" + reason_text("UNSUPPORTED_LAYOUT")
    assert not window.panel.preview_button.isEnabled()


def _drag(qtbot, window, box):
    geom = window.page["page_geometry"]
    to_view = PageGeometry(tuple(geom["cropbox"]), geom["rotation"]).page_to_view(PAGE_DPI / 72)
    viewport = window.view.viewport()
    points = []
    for x, y in ((box[0], box[1]), (box[2], box[3])):
        vx, vy = (
            to_view[0] * x + to_view[2] * y + to_view[4],
            to_view[1] * x + to_view[3] * y + to_view[5],
        )
        points.append(window.view.mapFromScene(QPointF(vx, vy)))
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=QPoint(points[0]))
    qtbot.mouseMove(viewport, pos=QPoint(points[1]))
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=QPoint(points[1]))


def test_flow_manual_cell(qtbot, make_window, tmp_path):
    """無框線表格：手動選格拉框 → 判定通過 → 預覽 → 套用；框到兩格時顯示原因。"""
    path = tmp_path / "borderless.pdf"
    table_pdf(path, [["Item", "Qty"], ["Pen", "12"]], vertical=False)
    window = make_window()
    open_file(qtbot, window, path)
    assert window.page["cell_targets"] == []
    window.actions["manual_cell"].trigger()
    assert window.view.box_mode
    box = cell_box(1, 1)
    _drag(qtbot, window, [box[0] + 2, box[1] + 2, box[2] - 2, box[3] - 2])
    wait(qtbot, window)
    assert window.selection["kind"] == "manual_cell" and not window.view.box_mode
    assert window.panel.selected.text() == "手動選格：12"
    preview(qtbot, window, "21")
    assert window.plan["ready"] and window.plan["target"]["cell"]["manual"]
    apply(qtbot, window)
    assert any(t["text"] == "21" for t in window.page["text_targets"])

    window.actions["manual_cell"].trigger()
    left = cell_box(1, 0)
    _drag(qtbot, window, [left[0] + 2, left[1] - 28, box[2] - 2, box[3] - 2])  # 跨兩列、兩欄
    wait(qtbot, window)
    assert window.panel.info.text().startswith("無法編輯：")
    assert not window.panel.preview_button.isEnabled()
