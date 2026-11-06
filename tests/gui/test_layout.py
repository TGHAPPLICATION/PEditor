"""P8 工程師要求：編輯面板改為浮動、尋找改為選單「編輯 → 尋找…」（Ctrl+F）。"""

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


def test_edit_panel_floats_and_comes_back(qtbot, make_window):
    window = make_window()
    dock = window.panel_dock
    assert isinstance(dock, QDockWidget) and dock.widget() is window.panel
    assert dock.isFloating()
    features = dock.features()
    assert features & QDockWidget.DockWidgetFeature.DockWidgetFloatable
    assert features & QDockWidget.DockWidgetFeature.DockWidgetMovable
    assert window.actions["panel"] in _menu_actions(window, "檢視")
    open_file(qtbot, window, FILES / "T01.pdf")
    dock.close()
    assert not dock.isVisible()
    click_target(qtbot, window, "衛生局")  # 選取後面板自動叫回
    assert dock.isVisible()
    window.actions["panel"].trigger()
    assert not dock.isVisible()
