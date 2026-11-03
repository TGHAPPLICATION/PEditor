"""G4-01、G4-04、G4-05：桌面編輯流程 E2E（pytest-qt、offscreen、真的 DocumentService 與 worker）。

在 CI 與 Windows 製作機都會跑；macOS 實機 E2E 依 ADR-0021 §3 另行人工驗收（NOT RUN 時於報告註明）。
"""

import hashlib
import os
import shutil
from pathlib import Path

import pymupdf
from PySide6.QtCore import QPoint, Qt

from peditor.core import drafts
from peditor.core.service import DocumentService
from peditor.ui.messages import NOTICES, reason_text

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
TIMEOUT = 60_000


def wait(qtbot, window):
    qtbot.waitUntil(lambda: not window.busy, timeout=TIMEOUT)


def open_file(qtbot, window, path):
    window.open_path(str(path))
    wait(qtbot, window)
    assert window.document_id is not None


def click_target(qtbot, window, text):
    target = next(t for t in window.page["text_targets"] if text in t["text"])
    rect = window.view.target_rect(target["target_id"])
    pos = window.view.mapFromScene(rect.center())
    qtbot.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(pos))
    assert window.selection is not None and window.selection["target_id"] == target["target_id"]
    return target


def find(qtbot, window, text):
    window.panel.find_text.setText(text)
    qtbot.mouseClick(window.panel.find_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)
    assert window.selection is not None and window.selection["text"] == text


def preview(qtbot, window, new_text):
    window.panel.new_text.setText(new_text)
    qtbot.mouseClick(window.panel.preview_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)


def apply(qtbot, window):
    qtbot.mouseClick(window.panel.apply_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)


def page_text(path):
    with pymupdf.open(path) as doc:
        return doc[0].get_text()


def test_flow_open_shows_page_and_thumbnails(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    assert window.page_count == 1 and window.thumbs.count() == 1
    assert not window.view.scene().itemsBoundingRect().isEmpty()
    assert not window.thumbs.item(0).icon().isNull()
    assert window.notice.text() == ""


def test_flow_click_selects_target(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    assert window.panel.selected.text() == "Hello World"
    assert window.panel.new_text.text() == "Hello World" and window.panel.preview_button.isEnabled()


def test_flow_preview_shows_before_after_without_commit(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    assert window.plan["ready"] and window.plan["mode"] == "A"
    assert "模式 A" in window.panel.info.text()
    before, after = window.panel.before.pixmap(), window.panel.after.pixmap()
    assert not before.isNull() and not after.isNull() and before.toImage() != after.toImage()
    assert window.revision == 0 and window.panel.apply_button.isEnabled()  # 預覽不提交


def test_flow_apply_updates_page(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    assert window.revision == 1 and window.last_error is None
    assert any(t["text"] == "Hello Earth" for t in window.page["text_targets"])
    assert window.actions["undo"].isEnabled() and not window.actions["redo"].isEnabled()


def test_flow_undo_redo(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    window.actions["undo"].trigger()
    wait(qtbot, window)
    assert any(t["text"] == "Hello World" for t in window.page["text_targets"])
    assert window.actions["redo"].isEnabled() and not window.actions["undo"].isEnabled()
    window.actions["redo"].trigger()
    wait(qtbot, window)
    assert any(t["text"] == "Hello Earth" for t in window.page["text_targets"])
    assert window.revision == 3


def test_flow_save_as_and_reopen(qtbot, make_window, tmp_path):
    out = tmp_path / "out.pdf"
    window = make_window(ask_save=lambda: str(out))
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    window.actions["save"].trigger()
    wait(qtbot, window)
    assert window.last_error is None and "Hello Earth" in page_text(out)
    open_file(qtbot, window, out)
    assert any(t["text"] == "Hello Earth" for t in window.page["text_targets"])


def test_flow_save_overwrites_existing_destination(qtbot, make_window, tmp_path):
    out = tmp_path / "out.pdf"
    out.write_bytes(b"old content")
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    window.save_as(str(out))  # 對話框已確認覆寫（QFileDialog 內建）
    wait(qtbot, window)
    assert window.last_error is None and "Hello World" in page_text(out)


def test_flow_mode_b_shows_font_replacement(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F02.pdf")
    click_target(qtbot, window, "醫事")
    preview(qtbot, window, "藥事人員名冊")
    assert window.plan["ready"] and window.plan["mode"] == "B"
    assert "字型替換" in window.panel.info.text() and "Noto Sans TC" in window.panel.info.text()


def test_flow_overflow_explained_and_not_applicable(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello " + "W" * 80)
    assert not window.plan["ready"]
    assert reason_text("TEXT_OVERFLOW") in window.panel.info.text()
    assert not window.panel.apply_button.isEnabled() and window.revision == 0


def test_flow_find_text_selects_span(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "T01.pdf")
    window.panel.find_text.setText("衛生局")
    qtbot.mouseClick(window.panel.find_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)
    assert window.selection is not None and window.selection["text"] == "衛生局"
    preview(qtbot, window, "測試局")
    apply(qtbot, window)
    assert window.revision == 1
    assert any("測試局" in t["text"] for t in window.page["text_targets"])


def test_flow_preview_unreliable_notice(qtbot, make_window):
    """ADR-0021 §1：MuPDF 依規範渲染空白的檔案提示使用者。"""
    window = make_window()
    open_file(qtbot, window, FILES / "T01.pdf")
    assert NOTICES["PREVIEW_UNRELIABLE"] in window.notice.text()


def test_flow_recover_draft_after_crash(qtbot, make_window, tmp_path):
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "F04.pdf", source)
    store_dir = tmp_path / "drafts"
    window = make_window(DocumentService(drafts=drafts.DraftStore(store_dir)))
    open_file(qtbot, window, source)
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    window.service.close()  # 模擬異常結束：沒有 close_document，草稿留下

    second = make_window(DocumentService(drafts=drafts.DraftStore(store_dir)),
                         ask_draft=lambda items: ("recover", items[0]["draft_id"]))  # fmt: skip
    second.offer_drafts()
    wait(qtbot, second)
    assert second.document_id is not None
    assert any(t["text"] == "Hello Earth" for t in second.page["text_targets"])
    assert second.actions["undo"].isEnabled()


def test_cancel_does_not_commit(qtbot, make_window, monkeypatch):
    """G4-04：進行中的請求取消後不提交；worker 重啟後回到原狀態並可繼續編輯。"""
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    service, doc, plan_id = window.service, window.document_id, window.plan["plan_id"]

    def slow_apply():
        service._send_raw("_sleep", {"seconds": 20})  # 代表一個長操作
        return service.apply_edit(doc, plan_id, 0)

    window._run(slow_apply, window._changed)
    qtbot.waitUntil(lambda: service.inflight_request is not None, timeout=TIMEOUT)
    assert window.actions["cancel"].isEnabled()
    window.actions["cancel"].trigger()
    wait(qtbot, window)
    assert window.last_error is not None and window.last_error.code == "CANCELLED"
    assert window.revision == 0 and service.history(doc) == {"revision": 0, "undo": 0, "redo": 0}
    window.load_page(0)
    wait(qtbot, window)
    assert any(t["text"] == "Hello World" for t in window.page["text_targets"])


def test_reason_shown_for_uneditable(qtbot, make_window):
    """G4-05：不可編輯的物件顯示原因、不能預覽。"""
    window = make_window()
    open_file(qtbot, window, FILES / "F05.pdf")
    target = next(t for t in window.page["text_targets"] if t["capability"]["status"] != "support")
    window.select_target(target)
    assert window.panel.info.text().startswith("無法編輯：")
    assert reason_text(target["capability"]["reasons"][0]) in window.panel.info.text()
    assert not window.panel.preview_button.isEnabled()

    open_file(qtbot, window, FILES / "U01.pdf")
    assert reason_text("NO_TEXT_LAYER") in window.notice.text()


def test_source_never_modified(qtbot, make_window, tmp_path):
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "F04.pdf", source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    window = make_window()
    open_file(qtbot, window, source)
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    window.save_as(str(source))  # 另存到原檔：拒絕
    wait(qtbot, window)
    assert window.last_error is not None and window.last_error.code == "INVALID_REQUEST"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert not any(n.startswith(".~peditor-") for n in os.listdir(tmp_path))
