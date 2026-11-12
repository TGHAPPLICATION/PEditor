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


def test_apply_button_visible_on_short_panel(qtbot, make_window, tmp_path):
    """P8 實機 S10：圖片替換預覽後，面板較矮時「套用」仍在可見範圍內（不被前後對照擠出）。"""
    from PIL import Image
    from test_image_ui import click_image

    from peditor.ui.app import PREVIEW_MAX_H

    new_image = tmp_path / "translucent.png"
    Image.new("RGBA", (240, 160), (200, 0, 120, 128)).save(new_image, "PNG")
    window = make_window(ask_image=lambda: str(new_image))
    open_file(qtbot, window, FILES / "I01.pdf")
    click_image(qtbot, window, 0)
    window.panel.image_button.click()
    wait(qtbot, window)
    assert window.panel.apply_button.isEnabled()
    for label in (window.panel.before, window.panel.after):
        assert 0 < label.pixmap().height() <= PREVIEW_MAX_H
    window.panel_dock.resize(360, 420)  # 矮螢幕：內容超出時捲動，「套用」不捲走
    window.panel_dock.show()
    qtbot.waitUntil(lambda: window.panel.apply_button.isVisible())
    button = window.panel.apply_button
    bottom = button.mapTo(window.panel, button.rect().bottomLeft()).y()
    assert bottom <= window.panel.height()
    assert not window.panel.scroll.isAncestorOf(button)


def test_floating_panel_kept_above_taskbar(qtbot, make_window):
    """P8 實機 S10：浮動面板底部超出螢幕可用範圍時縮短（內容改捲動），叫回時也重新檢查。"""
    window = make_window()
    dock = window.panel_dock
    open_file(qtbot, window, FILES / "T01.pdf")
    screen = dock.screen().availableGeometry()
    dock.resize(360, 720)
    dock.move(screen.left() + 10, screen.bottom() - 200)  # 底部遠超出螢幕
    dock.close()
    click_target(qtbot, window, "衛生局")  # 選取後叫回並重新檢查
    assert dock.isVisible()
    frame = dock.frameGeometry()
    assert frame.bottom() <= screen.bottom() and frame.top() >= screen.top()
    assert dock.height() >= 320


def test_build_id_in_title(tmp_path):
    """P8：安裝包的視窗標題帶建置 commit，實機驗收可辨認裝的是哪一版；開發環境不顯示。"""
    from peditor.ui.app import _build_suffix

    build = tmp_path / "BUILD"
    assert _build_suffix(build) == ""
    build.write_text("0b821ff", encoding="ascii")
    assert _build_suffix(build) == "（0b821ff）"
    build.write_text("bad value\n<x>", encoding="ascii")
    assert _build_suffix(build) == ""
