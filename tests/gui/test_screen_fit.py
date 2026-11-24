"""2026-11-24 實機：高 DPI 時對話框下方按鈕超出畫面下緣、文字被遮住 → 全部介面檢查。

以小的螢幕可用範圍模擬（1366×768 縮放 125%、1920×1080 縮放 150%，皆扣除工作列），
檢查每個視窗與對話框：整個框在可用範圍內；看得到的按鈕完整在框內、寬高不小於其建議尺寸（文字不被裁切）。
"""

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QAbstractButton, QApplication
from test_e2e import FILES, click_target, open_file

from lumicat.ui import screen
from lumicat.ui.app import DraftDialog
from lumicat.ui.page_tools import PageToolsDialog, Source
from lumicat.ui.text_extract import TextExtractDialog

AREAS = {"1366x768@125%": QRect(0, 0, 1093, 574), "1920x1080@150%": QRect(0, 0, 1280, 680)}


@pytest.fixture(params=list(AREAS))
def area(request, monkeypatch):
    rect = AREAS[request.param]
    monkeypatch.setattr(screen, "available_area", lambda _widget: rect)
    return rect


def check(widget, area):
    QApplication.processEvents()
    frame = widget.frameGeometry()
    assert area.contains(frame), (type(widget).__name__, frame, area)
    for button in widget.findChildren(QAbstractButton):
        if not button.isVisibleTo(widget) or button.window() is not widget:
            continue
        hint = button.sizeHint()
        name = button.text() or button.objectName()
        assert button.width() >= hint.width() and button.height() >= hint.height(), name
        top_left = button.mapTo(widget, button.rect().topLeft())
        bottom_right = button.mapTo(widget, button.rect().bottomRight())
        assert widget.rect().contains(top_left) and widget.rect().contains(bottom_right), name


def test_text_extract_dialog(qtbot, area):
    pages = {i: {"text": "第一行\n" * 80, "limited": False} for i in range(30)}
    dialog = TextExtractDialog(30, 0, pages.__getitem__, lambda: None)
    qtbot.addWidget(dialog)
    dialog.range.setText("1-30")
    dialog.run()
    dialog.show()
    check(dialog, area)


def test_page_tools_dialog_all_tabs(qtbot, area):
    current = Source("C:/x/目前.pdf", 12)
    dialog = PageToolsDialog(current, lambda p: Source(p, 3), lambda: [], lambda: None)
    qtbot.addWidget(dialog)
    for index in range(20):
        dialog._add_source(Source(f"C:/x/檔案{index}.pdf", 3))
    dialog.show()
    for tab in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(tab)
        check(dialog, area)


def test_draft_dialog(qtbot, area):
    drafts = [{"draft_id": f"{i:016x}", "path": f"C:/x/很長的檔名_{i}_" + "甲" * 40 + ".pdf",
               "operations": 3, "saved_at": 1_795_000_000} for i in range(40)]  # fmt: skip
    dialog = DraftDialog(drafts)
    qtbot.addWidget(dialog)
    dialog.show()
    check(dialog, area)


def test_main_window_find_bar_and_editor(qtbot, make_window, area):
    window = make_window()
    check(window, area)
    open_file(qtbot, window, FILES / "F02.pdf")
    click_target(qtbot, window, "醫事")
    window.panel.new_text.setText("藥事人員名冊")
    window.panel.apply_button.click()
    from test_e2e import wait

    wait(qtbot, window)
    assert window.panel.info.isVisible()
    viewport = window.view.viewport()
    button = window.panel.apply_button
    corner = button.mapTo(viewport, button.rect().bottomRight())
    assert viewport.rect().contains(corner) and button.width() >= button.sizeHint().width()
    window.show_find()
    check(window.find_bar, area)


def test_message_boxes_fit_smallest_area(qtbot):
    """「關於」與未另存提醒是 Qt 自動調整大小的訊息框：確認在最小的可用範圍內放得下。"""
    from PySide6.QtWidgets import QMessageBox

    from lumicat.ui.app import about_text

    smallest = AREAS["1366x768@125%"]
    unsaved = ("這份文件有尚未另存的修改，要先另存嗎？", ["另存…", "不儲存", "取消"])
    for text, buttons in ((about_text("abc1234"), ["OK"]), unsaved):
        box = QMessageBox()
        qtbot.addWidget(box)
        box.setText(text)
        for label in buttons:
            box.addButton(label, QMessageBox.ButtonRole.AcceptRole)
        box.show()
        QApplication.processEvents()
        assert box.width() <= smallest.width() - 16 and box.height() <= smallest.height() - 56


def test_main_window_restore_keeps_user_position(qtbot, make_window, area):
    """P12 獨立核對：只在第一次顯示時移回畫面內；之後（例如從最小化還原）不移動使用者放的位置。"""
    window = make_window()
    QApplication.processEvents()
    window.move(area.right() - 50, area.bottom() - 50)  # 使用者自己拖到邊緣
    moved = window.pos()
    window.hide()
    window.show()
    QApplication.processEvents()
    assert window.pos() == moved
