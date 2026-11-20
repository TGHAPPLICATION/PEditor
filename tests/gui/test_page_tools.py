"""P9-06、P9-07：「工具 → 頁面工具…」對話框與主視窗流程（ADR-0029）。"""

import pymupdf
import pytest
from test_e2e import apply, click_target, open_file, preview, wait

from peditor.core import pages
from peditor.ui.page_tools import PageToolsDialog, Request, Source


def _sample(path, label, count):
    doc = pymupdf.open()
    for i in range(count):
        doc.new_page(width=300, height=200).insert_text((40, 100), f"{label}{i + 1}", fontsize=24)
    doc.save(path)
    doc.close()
    return str(path)


def _texts(path):
    with pymupdf.open(path) as doc:
        return [p.get_text().strip() for p in doc]


def _dialog(qtbot, current, probe=None, files=(), file=None):
    probes = {}

    def default_probe(path):
        if path in probes:
            raise ValueError(probes[path])
        return Source(path, 2)

    dialog = PageToolsDialog(current, probe or default_probe, lambda: list(files), lambda: file)
    qtbot.addWidget(dialog)
    return dialog, probes


def test_range_tabs_build_plans(qtbot):
    dialog, _ = _dialog(qtbot, Source("/x/a.pdf", 5))
    dialog.tabs.setCurrentIndex(0)
    dialog.delete_range.setText("2,4-5")
    assert dialog.delete_info.text() == "將刪除 3 頁，新檔共 2 頁"
    request = dialog.build()
    assert request.sources == ["/x/a.pdf"] and request.plan == [(0, 0), (0, 2)]
    dialog.tabs.setCurrentIndex(1)
    dialog.keep_range.setText("9")
    assert "超出頁數" in dialog.keep_info.text()
    with pytest.raises(pages.RangeError):
        dialog.build()
    dialog.submit()  # 不合法：顯示錯誤、不關閉
    assert "超出頁數" in dialog.error.text() and dialog.request is None


def test_merge_tab_order_and_errors(qtbot):
    dialog, probes = _dialog(qtbot, Source("/x/a.pdf", 1), files=["/x/b.pdf", "/x/bad.pdf"])
    probes["/x/bad.pdf"] = "無法使用：加密"
    dialog.tabs.setCurrentIndex(2)
    dialog.add_files()
    assert dialog.merge_list.count() == 2  # 目前檔案＋b；bad 被拒絕
    assert "bad.pdf：無法使用：加密" in dialog.error.text() and "/x/" not in dialog.error.text()
    dialog.merge_list.setCurrentRow(1)
    dialog.up_button.click()  # b 移到最前面
    assert [s.name for s in dialog.sources()] == ["b.pdf", "a.pdf"]
    request = dialog.build()
    assert request.sources == ["/x/b.pdf", "/x/a.pdf"]
    assert request.plan == [(0, 0), (0, 1), (1, 0)]
    assert dialog.ok_button.text() == "另存合併檔…"


def test_insert_tab(qtbot):
    dialog, _ = _dialog(qtbot, Source("/x/a.pdf", 3), file="/x/b.pdf")
    dialog.tabs.setCurrentIndex(3)
    with pytest.raises(pages.RangeError, match="選擇要插入"):
        dialog.build()
    dialog.choose_insert()
    dialog.position.setValue(1)
    assert dialog.build().plan == pages.insert_plan(3, 2, 1)


def test_without_open_document(qtbot):
    dialog, _ = _dialog(qtbot, None)
    assert not dialog.delete_range.isEnabled() and not dialog.insert_button.isEnabled()
    with pytest.raises(pages.RangeError, match="先開啟"):
        dialog.build()


def test_main_window_runs_tool_and_opens_result(qtbot, make_window, tmp_path):
    a = _sample(tmp_path / "a.pdf", "A", 3)
    out = tmp_path / "out.pdf"
    seen = []

    def ask(current):
        seen.append(current)
        return Request("delete", [current.path], pages.delete_plan(3, [1]), open_after=True)

    window = make_window(ask_page_tool=ask, ask_save=lambda: str(out))
    open_file(qtbot, window, a)
    window.actions["page_tools"].trigger()
    wait(qtbot, window)
    qtbot.waitUntil(lambda: window.page_count == 2 and not window.busy, timeout=30000)
    assert seen[0].path == a and seen[0].page_count == 3
    assert _texts(out) == ["A1", "A3"]
    assert window.service.document_path(window.document_id) == str(out)


def test_unsaved_changes_asked_first(qtbot, make_window, tmp_path):
    """P9-07：目前文件有未另存修改時先詢問（ADR-0027）；取消則不開啟頁面工具。"""
    from test_e2e import FILES

    asked, opened = [], []
    window = make_window(ask_unsaved=lambda: asked.append(True) or "cancel",
                         ask_page_tool=lambda current: opened.append(current))  # fmt: skip
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Earth")
    apply(qtbot, window)
    window.page_tools()
    assert asked and opened == []
    window._ask_unsaved = lambda: "discard"
    window.page_tools()
    assert len(opened) == 1


def test_probe_reports_reasons(make_window, tmp_path):
    import pikepdf

    a = _sample(tmp_path / "a.pdf", "A", 1)
    with pikepdf.open(a) as pdf:
        pdf.save(tmp_path / "s.pdf", encryption=pikepdf.Encryption(owner="o", user="u"))
    window = make_window()
    assert window.probe(a) == Source(a, 1)
    with pytest.raises(ValueError, match="無法使用"):
        window.probe(str(tmp_path / "s.pdf"))


def test_saved_choice_uses_saved_file(qtbot, make_window, tmp_path):
    """獨立核對：未另存時選「另存」，頁面工具讀剛另存的新檔（含修改），不是原檔。"""
    from test_e2e import FILES

    saved = tmp_path / "saved.pdf"
    seen = []
    window = make_window(ask_unsaved=lambda: "save", ask_save=lambda: str(saved),
                         ask_page_tool=lambda current: seen.append(current))  # fmt: skip
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Earth")
    apply(qtbot, window)
    window.page_tools()
    qtbot.waitUntil(lambda: bool(seen), timeout=30000)
    assert seen[0].path == str(saved)
    window.page_tools()  # 之後沒有再改：仍用另存的新檔
    assert seen[1].path == str(saved)
