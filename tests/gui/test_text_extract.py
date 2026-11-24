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
    # 欄位已預填目前頁，另有說明提示可自行輸入
    assert dialog.hint.isVisibleTo(dialog) and "可自行輸入頁碼" in dialog.hint.text()
    assert "1-4" in dialog.hint.text() and dialog.range.toolTip() == dialog.hint.text()


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


def test_bad_range_clears_old_result(qtbot):
    """P12 獨立核對：頁碼錯誤時清空舊結果，不讓上一次的內容被當成這次頁碼的結果。"""
    dialog, _ = make_dialog(qtbot)
    assert dialog.text.toPlainText()
    dialog.range.setText("9")
    dialog.run()
    assert dialog.info.text() and dialog.text.toPlainText() == ""
    assert not dialog.copy_button.isEnabled() and not dialog.headers_button.isEnabled()


def test_extract_failure_and_total_limit_clear_result(qtbot, monkeypatch):
    from peditor.ui import text_extract

    def fail(_index):
        raise ValueError("處理逾時")

    dialog = TextExtractDialog(4, 0, fail, lambda: None)
    qtbot.addWidget(dialog)
    assert dialog.info.text() == "處理逾時" and dialog.text.toPlainText() == ""
    monkeypatch.setattr(text_extract, "MAX_EXTRACT_TOTAL_CHARS", 10)
    dialog, _ = make_dialog(qtbot)
    dialog.range.setText("1-4")
    dialog.run()
    assert "太多" in dialog.info.text() and dialog.text.toPlainText() == ""


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
    count = dialog.text.toPlainText().count("頁")
    for _ in range(count - 1):
        dialog.find_next()
    last = dialog.text.textCursor().selectionStart()
    assert last > first
    dialog.find_next()  # 到底後從頭找：回到第一個
    assert dialog.text.textCursor().selectionStart() == first
    assert dialog.text.textCursor().selectedText() == "頁" and "找不到" not in dialog.info.text()
    dialog.search.setText("不存在")
    dialog.find_next()
    assert "找不到" in dialog.info.text()


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


def test_remove_and_restore_page_headers(qtbot):
    """工程師 2026-11-24：「複製全部」前方的「移除頁碼」；移除後複製與另存都不含標題，可加回。"""
    dialog, _ = make_dialog(qtbot)
    dialog.range.setText("1-4")
    dialog.run()
    row = next(dialog.layout().itemAt(i).layout() for i in range(dialog.layout().count())
               if dialog.layout().itemAt(i).layout()
               and dialog.layout().itemAt(i).layout().indexOf(dialog.copy_button) >= 0)  # fmt: skip
    assert row.indexOf(dialog.headers_button) == row.indexOf(dialog.copy_button) - 1  # 緊鄰左方
    assert dialog.headers_button.isEnabled()
    qtbot.mouseClick(dialog.headers_button, Qt.MouseButton.LeftButton)
    assert dialog.text.toPlainText() == "第一頁內容\n第二行\n\nHello 第三頁"
    assert dialog.headers_button.text() == "加回頁碼"
    qtbot.mouseClick(dialog.copy_button, Qt.MouseButton.LeftButton)
    assert QGuiApplication.clipboard().text() == "第一頁內容\n第二行\n\nHello 第三頁"
    dialog.range.setText("3")  # 重新擷取仍維持不加頁碼
    dialog.run()
    assert dialog.text.toPlainText() == "Hello 第三頁"
    qtbot.mouseClick(dialog.headers_button, Qt.MouseButton.LeftButton)
    assert dialog.text.toPlainText() == "—— 第 3 頁 ——\nHello 第三頁"
    assert dialog.headers_button.text() == "移除頁碼"


def test_headers_toggle_works_with_only_empty_pages(qtbot):
    """P12 獨立核對：移除頁碼後擷取只有空白頁的範圍，仍可按「加回頁碼」。"""
    dialog, _ = make_dialog(qtbot)
    qtbot.mouseClick(dialog.headers_button, Qt.MouseButton.LeftButton)
    dialog.range.setText("2")
    dialog.run()
    assert dialog.text.toPlainText() == "" and dialog.headers_button.isEnabled()
    qtbot.mouseClick(dialog.headers_button, Qt.MouseButton.LeftButton)
    assert dialog.text.toPlainText() == "—— 第 2 頁 ——\n" + NO_TEXT


def test_save_does_not_overwrite_appended_name_and_is_atomic(qtbot, tmp_path, monkeypatch):
    existing = tmp_path / "結果.txt"
    existing.write_text("原本的內容", encoding="utf-8")
    dialog, _ = make_dialog(qtbot, saver=lambda: str(tmp_path / "結果"))
    dialog.save_text()  # 補上 .txt 後的檔名已存在：不覆寫
    assert existing.read_text(encoding="utf-8") == "原本的內容"
    assert "已存在" in dialog.info.text() and str(tmp_path) not in dialog.info.text()

    import peditor.ui.text_extract as module

    def broken_replace(*_a):
        raise OSError("disk full")

    monkeypatch.setattr(module.os, "replace", broken_replace)
    dialog._ask_save = lambda: str(existing)  # 對話框已確認覆寫
    dialog.save_text()
    assert dialog.info.text() == "無法寫入文字檔"
    assert existing.read_text(encoding="utf-8") == "原本的內容"  # 失敗不留半個檔
    assert sorted(p.name for p in tmp_path.iterdir()) == ["結果.txt"]
