"""ADR-0033：「文字擷取」對話框與主視窗流程；「頁面管理」改名與位置見 test_theme.py。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from test_e2e import FILES, apply, click_target, open_file, preview

from peditor.ui.text_extract import NO_TEXT, TextExtractDialog, combine

PAGES = {0: {"text": "第一頁內容\n第二行", "limited": False},
         1: {"text": "", "limited": False},
         2: {"text": "Hello 第三頁", "limited": False},
         3: {"text": "", "limited": True}}  # fmt: skip


def make_dialog(qtbot, current=0, saver=lambda: None):
    calls = []

    def extract(index):
        calls.append(index)
        return PAGES[index]

    dialog = TextExtractDialog(4, current, extract, saver)
    qtbot.addWidget(dialog)
    return dialog, calls


def test_defaults_to_current_page(qtbot):
    dialog, calls = make_dialog(qtbot, current=2)
    assert dialog.range.text() == "3" and calls == [2]
    assert dialog.text.toPlainText() == "—— 第 3 頁 ——\nHello 第三頁"
    assert dialog.text.isReadOnly()


def test_range_combines_pages_with_headers_and_notes(qtbot):
    dialog, calls = make_dialog(qtbot)
    dialog.range.setText("1-4")
    qtbot.mouseClick(dialog.extract_button, Qt.MouseButton.LeftButton)
    assert calls[-4:] == [0, 1, 2, 3]
    text = dialog.text.toPlainText()
    assert text == combine([(i, PAGES[i]) for i in range(4)])
    assert "—— 第 1 頁 ——\n第一頁內容\n第二行\n\n—— 第 2 頁 ——\n" + NO_TEXT in text
    assert "超過處理上限" in text
    assert "第 2 頁沒有文字" in dialog.info.text()


def test_bad_range_shows_error_keeps_text(qtbot):
    dialog, _ = make_dialog(qtbot)
    before = dialog.text.toPlainText()
    dialog.range.setText("9")
    dialog.run()
    assert dialog.info.text() and dialog.text.toPlainText() == before


def test_copy_all(qtbot):
    dialog, _ = make_dialog(qtbot)
    qtbot.mouseClick(dialog.copy_button, Qt.MouseButton.LeftButton)
    assert QGuiApplication.clipboard().text() == dialog.text.toPlainText()


def test_search_finds_and_wraps(qtbot):
    dialog, _ = make_dialog(qtbot)
    dialog.range.setText("1-3")
    dialog.run()
    dialog.search.setText("頁")
    dialog.find_next()
    first = dialog.text.textCursor().selectionStart()
    assert dialog.text.textCursor().selectedText() == "頁"
    for _ in range(20):  # 到底後從頭找
        dialog.find_next()
    assert dialog.text.textCursor().selectedText() == "頁"
    dialog.search.setText("不存在")
    dialog.find_next()
    assert "找不到" in dialog.info.text() and first >= 0


def test_save_txt_utf8_bom_adds_extension(qtbot, tmp_path):
    target = tmp_path / "中文 資料夾" / "擷取結果"
    target.parent.mkdir()
    dialog, _ = make_dialog(qtbot, saver=lambda: str(target))
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    saved = target.with_name("擷取結果.txt")
    assert saved.read_bytes().startswith(b"\xef\xbb\xbf")
    assert saved.read_text(encoding="utf-8-sig").replace("\r\n", "\n") == dialog.text.toPlainText()
    assert dialog.info.text() == "已另存 擷取結果.txt"  # 只顯示檔名
    assert str(tmp_path) not in dialog.info.text()


def test_save_failure_message_without_path(qtbot, tmp_path):
    dialog, _ = make_dialog(qtbot, saver=lambda: str(tmp_path / "沒有這個資料夾" / "x.txt"))
    dialog.save_text()
    assert dialog.info.text() == "無法寫入文字檔"


def test_main_window_extracts_current_state(qtbot, make_window):
    window = make_window()
    assert not window.actions["text_extract"].isEnabled()  # 沒開檔
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)  # 未另存
    shown = []
    window._exec_dialog = shown.append
    window.actions["text_extract"].trigger()
    dialog = shown[0]
    assert dialog.text.toPlainText() == "—— 第 1 頁 ——\nHello Earth"
    dialog.deleteLater()
