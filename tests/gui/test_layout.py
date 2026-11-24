"""P8 工程師要求：尋找改為選單「編輯 → 尋找…」（Ctrl+F）。
ADR-0032：編輯框在頁面上，取代浮動面板。"""

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDockWidget, QToolBar
from test_e2e import FILES, click_target, open_file, wait


def _menu_actions(window, title):
    menu = next(m for m in window.menuBar().actions() if m.text() == title).menu()
    return [a for a in menu.actions() if not a.isSeparator()]


def test_find_is_in_menu_with_ctrl_f(qtbot, make_window):
    window = make_window()
    find = window.actions["find"]
    assert find.shortcuts() == QKeySequence.keyBindings(QKeySequence.StandardKey.Find)
    assert find in _menu_actions(window, "編輯")
    (toolbar,) = window.findChildren(QToolBar)
    assert find not in toolbar.actions()  # 只放在選單
    assert not hasattr(window.panel, "find_text")  # 編輯面板不再放尋找欄
    open_file(qtbot, window, FILES / "T01.pdf")
    find.trigger()
    assert window.find_bar.isVisible()
    window.find_bar.find_text.setText("衛生局")
    window.find_bar.find_text.returnPressed.emit()  # Enter 送出
    wait(qtbot, window)
    assert window.selection is not None and window.selection["text"] == "衛生局"


def test_no_floating_panel_editor_on_page(qtbot, make_window):
    """ADR-0032 取代 P8 的浮動編輯面板：沒有面板、「檢視」不再有「編輯面板」；編輯框在頁面上。"""
    window = make_window()
    assert window.findChildren(QDockWidget) == [] and "panel" not in window.actions
    assert window.panel.parent() is window.view.viewport() and not window.panel.isVisible()
    open_file(qtbot, window, FILES / "T01.pdf")
    click_target(qtbot, window, "衛生局")
    assert window.panel.isVisible()


def test_editor_and_apply_inside_small_view(qtbot, make_window, tmp_path):
    """P8 實機 S10 的延續：視窗很小、提醒很長時，編輯框與「套用」仍在頁面可視範圍內。"""
    window = make_window()
    window.resize(520, 420)
    open_file(qtbot, window, FILES / "F02.pdf")
    click_target(qtbot, window, "醫事")
    window.panel.new_text.setText("藥事人員名冊")
    window.panel.apply_button.click()
    wait(qtbot, window)
    assert window.panel.info.isVisible()  # 字型替換提醒
    viewport = window.view.viewport().rect()
    frame = window.panel.geometry()
    assert viewport.contains(frame.topLeft()) and frame.right() <= viewport.right()
    button = window.panel.apply_button
    corner = button.mapTo(window.view.viewport(), button.rect().bottomRight())
    assert viewport.contains(corner) and button.isVisible()
    for value in (0, window.view.verticalScrollBar().maximum()):  # 捲動後仍在可視範圍
        window.view.verticalScrollBar().setValue(value)
        assert viewport.contains(window.panel.geometry().topLeft())


def test_build_id_in_title(tmp_path):
    """P8：安裝包的視窗標題帶建置 commit，實機驗收可辨認裝的是哪一版；開發環境不顯示。"""
    from peditor.ui.app import _build_suffix

    build = tmp_path / "BUILD"
    assert _build_suffix(build) == ""
    build.write_text("0b821ff", encoding="ascii")
    assert _build_suffix(build) == "（0b821ff）"
    build.write_text("bad value\n<x>", encoding="ascii")
    assert _build_suffix(build) == ""
