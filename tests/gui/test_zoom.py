"""頁面縮放（P8 工程師要求）：25%–400%，按鈕、快捷鍵與 Ctrl＋滾輪；放大後以較高 DPI 重新渲染；
點選判定在任何縮放下都對應同一個目標（場景座標不變）。"""

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from test_e2e import FILES, click_target, open_file, wait

from peditor.core.limits import MAX_RENDER_DPI
from peditor.ui import app


def test_zoom_actions_and_bounds(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "T01.pdf")
    view = window.view
    window.actions["zoom_in"].trigger()
    assert abs(view.zoom - app.ZOOM_STEP) < 1e-6 and abs(view.transform().m11() - view.zoom) < 1e-6
    for _ in range(20):
        window.actions["zoom_in"].trigger()
    assert view.zoom == app.ZOOM_MAX
    for _ in range(30):
        window.actions["zoom_out"].trigger()
    assert view.zoom == app.ZOOM_MIN
    window.actions["zoom_reset"].trigger()
    assert view.zoom == 1.0
    assert not window.actions["zoom_in"].shortcut().isEmpty()  # 平台的標準放大鍵


def test_ctrl_wheel_zooms(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "T01.pdf")
    view = window.view
    center = QPointF(view.viewport().rect().center())

    event = QWheelEvent(center, view.mapToGlobal(center.toPoint()).toPointF(), QPoint(0, 0),
                        QPoint(0, 120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.ControlModifier, Qt.ScrollPhase.NoScrollPhase,
                        False)  # fmt: skip
    view.wheelEvent(event)
    assert abs(view.zoom - app.ZOOM_STEP) < 1e-6


def test_click_selects_same_target_when_zoomed(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "T01.pdf")
    window.view.set_zoom(2.0)
    target = click_target(qtbot, window, "衛生局")  # 以縮放後的檢視座標點擊
    assert "衛生局" in target["text"]


def test_zoom_in_renders_sharper(qtbot, make_window):
    """放大後停止 300 ms，以 min(MAX_RENDER_DPI, 100×縮放) 重新渲染；圖縮回場景大小，框位置不變。"""
    window = make_window()
    open_file(qtbot, window, FILES / "T01.pdf")
    item = window.view._pixmap_item
    width = item.pixmap().width()
    scene_width = window.view.scene().sceneRect().width()
    window.view.set_zoom(4.0)
    qtbot.waitUntil(lambda: window._sharp_dpi == MAX_RENDER_DPI, timeout=60_000)
    wait(qtbot, window)
    assert item.pixmap().width() > width * 2.5
    assert abs(item.boundingRect().width() * item.scale() - scene_width) < 2
    assert window.view.scene().sceneRect().width() == scene_width


def test_zoom_kept_across_pages(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "I02.pdf")  # 兩頁
    window.view.set_zoom(1.5)
    window.load_page(1)
    wait(qtbot, window)
    assert window.view.zoom == 1.5 and window.page_index == 1
