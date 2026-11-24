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
    window.actions["find"].trigger()  # 選單「編輯 → 尋找…」（Ctrl+F）
    window.find_bar.find_text.setText(text)
    qtbot.mouseClick(window.find_bar.find_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)
    assert window.selection is not None and window.selection["text"] == text


def preview(qtbot, window, new_text):
    """輸入新文字（ADR-0032 起沒有預覽；保留名稱以減少測試改動）。"""
    window.panel.new_text.setText(new_text)


def apply(qtbot, window, confirm=True):
    """按「套用」；計畫有提醒時編輯框先顯示提醒，confirm=True 時再按「確認套用」。"""
    qtbot.mouseClick(window.panel.apply_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)
    if confirm and window.panel.isVisible() and window.panel.apply_button.text() == "確認套用":
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
    assert window.panel.new_text.text() == "Hello World" and window.panel.apply_button.isEnabled()
    # ADR-0032：點選即開頁面上的編輯框，焦點在輸入欄且全選，只有「套用」
    assert window.panel.isVisible() and window.panel.parent() is window.view.viewport()
    box = window.panel.new_text
    assert box.hasFocus() and box.selectedText() == "Hello World"
    assert not hasattr(window.panel, "preview_button") and not hasattr(window, "panel_dock")
    assert window.panel.apply_button.text() == "套用"


def test_flow_editor_placed_at_target(qtbot, make_window):
    """編輯框在選取文字附近（正下方或上方），不超出頁面可視範圍；捲動後跟著移動。"""
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    target = window.view.mapFromScene(window._anchor).boundingRect()
    frame = window.panel.geometry()
    assert window.view.viewport().rect().contains(frame)
    assert frame.top() >= target.bottom() or frame.bottom() <= target.top()
    window.view.set_zoom(2.0)
    qtbot.wait(10)
    moved = window.view.mapFromScene(window._anchor).boundingRect()
    after = window.panel.geometry()
    assert moved != target and window.view.viewport().rect().contains(after)
    if window.view.viewport().rect().intersects(moved):  # 選取內容仍在畫面上：編輯框緊鄰它
        assert after.top() >= moved.bottom() or after.bottom() <= moved.top()
        assert after.left() == max(
            8, min(moved.left(), window.view.viewport().rect().right() - after.width() - 8)
        )
    window.resize(window.width() - 200, window.height())  # 視窗變窄後重新放置
    qtbot.wait(10)
    assert window.view.viewport().rect().contains(window.panel.geometry())


def test_sharper_render_waits_until_editor_closes(qtbot, make_window, monkeypatch):
    """獨立核對（P11）：編輯中不跑背景重新渲染（會停用輸入欄、打斷組字），關閉編輯框後才跑。"""
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    calls = []
    real = window.service.render_page
    monkeypatch.setattr(window.service, "render_page", lambda *a: calls.append(a) or real(*a))
    window.view.set_zoom(2.0)
    qtbot.wait(400)
    assert calls == [] and window.panel.new_text.isEnabled() and window.panel.new_text.hasFocus()
    window.close_editor()
    qtbot.waitUntil(lambda: calls != [], timeout=TIMEOUT)


def test_flow_apply_without_warnings_writes_back_and_closes(qtbot, make_window):
    """沒有提醒：一次「套用」就寫回頁面、關閉編輯框、焦點回頁面（ADR-0032 §2）。"""
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window, confirm=False)
    assert window.revision == 1 and not window.panel.isVisible() and window.selection is None
    assert any(t["text"] == "Hello Earth" for t in window.page["text_targets"])


def test_flow_escape_closes_editor_without_change(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    window.panel.new_text.setText("Hello Earth")
    qtbot.keyClick(window.panel.new_text, Qt.Key.Key_Escape)
    assert not window.panel.isVisible() and window.selection is None and window.revision == 0
    click_target(qtbot, window, "World")
    qtbot.mouseClick(window.panel.close_button, Qt.MouseButton.LeftButton)
    assert not window.panel.isVisible() and window.revision == 0


def test_flow_enter_applies(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    window.panel.new_text.setText("Hello Earth")
    qtbot.keyClick(window.panel.new_text, Qt.Key.Key_Return)
    wait(qtbot, window)
    assert window.revision == 1 and not window.panel.isVisible()


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
    apply(qtbot, window, confirm=False)
    # 有提醒：先在編輯框顯示、不寫回；按「確認套用」才寫回（ADR-0032 §3）
    assert window.plan["ready"] and window.plan["mode"] == "B" and window.revision == 0
    assert window.panel.isVisible() and window.panel.info.isVisible()
    assert "Noto Sans TC" in window.panel.info.text()
    assert window.panel.apply_button.text() == "確認套用"
    qtbot.mouseClick(window.panel.apply_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)
    assert window.revision == 1 and not window.panel.isVisible()
    assert "藥事人員名冊" in "".join(t["text"] for t in window.page["text_targets"])


def test_flow_changing_text_after_warning_replans(qtbot, make_window):
    """提醒顯示後又改字：回到「套用」，重新規劃，不沿用舊計畫。"""
    window = make_window()
    open_file(qtbot, window, FILES / "F02.pdf")
    click_target(qtbot, window, "醫事")
    preview(qtbot, window, "藥事人員名冊")
    apply(qtbot, window, confirm=False)
    assert window.panel.apply_button.text() == "確認套用"
    old_plan = window.plan["plan_id"]
    qtbot.keyClicks(window.panel.new_text, "2")
    assert window.panel.apply_button.text() == "套用" and not window.panel.info.isVisible()
    apply(qtbot, window, confirm=False)
    assert window.revision == 0 and window.plan["plan_id"] != old_plan
    assert window.panel.apply_button.text() == "確認套用"


def test_info_only_warning_does_not_ask(qtbot, make_window, monkeypatch):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    real = window.service.plan_text_edit

    def plan(*args, **kwargs):
        return {**real(*args, **kwargs), "warnings": ["已同步更新結構樹 /ActualText（ADR-0017）"]}

    monkeypatch.setattr(window.service, "plan_text_edit", plan)
    apply(qtbot, window, confirm=False)
    assert window.revision == 1


def test_flow_overflow_explained_and_not_applicable(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello " + "W" * 80)
    apply(qtbot, window)
    assert not window.plan["ready"] and window.revision == 0
    assert reason_text("TEXT_OVERFLOW") in window.panel.info.text()
    assert window.panel.isVisible() and window.panel.new_text.hasFocus()  # 留在框內修改


def test_flow_find_text_selects_span(qtbot, make_window):
    window = make_window()
    open_file(qtbot, window, FILES / "T01.pdf")
    window.actions["find"].trigger()
    window.find_bar.find_text.setText("衛生局")
    qtbot.mouseClick(window.find_bar.find_button, Qt.MouseButton.LeftButton)
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
    service, doc = window.service, window.document_id
    plan_id = service.plan_text_edit(doc, window.selection["target_id"], "Hello Earth",
                                     "prefer_a", 0)["plan_id"]  # fmt: skip

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


def test_escape_while_busy_cancels(qtbot, make_window, monkeypatch):
    """獨立核對（P11）：處理中焦點在編輯框時按 Esc 是「取消」（G4-04），不與編輯框的 Esc 衝突。"""
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    service = window.service
    window._run(lambda: service._send_raw("_sleep", {"seconds": 20}), lambda _: None)
    qtbot.waitUntil(lambda: service.inflight_request is not None, timeout=TIMEOUT)
    window.panel.close_button.setFocus()
    qtbot.keyClick(window.panel.close_button, Qt.Key.Key_Escape)
    wait(qtbot, window)
    assert window.last_error is not None and window.last_error.code == "CANCELLED"
    assert window.panel.isVisible() and window.revision == 0  # 編輯框留著，可再套用
    qtbot.keyClick(window.panel.new_text, Qt.Key.Key_Escape)  # 不忙時 Esc 關閉編輯框
    assert not window.panel.isVisible()


def test_reason_shown_for_uneditable(qtbot, make_window):
    """G4-05：不可編輯的物件顯示原因、不能套用。"""
    window = make_window()
    open_file(qtbot, window, FILES / "F05.pdf")
    target = next(t for t in window.page["text_targets"] if t["capability"]["status"] != "support")
    window.select_target(target)
    assert window.panel.info.text().startswith("無法編輯：")
    assert reason_text(target["capability"]["reasons"][0]) in window.panel.info.text()
    assert not window.panel.apply_button.isEnabled() and not window.panel.new_text.isEnabled()
    assert window.panel.isVisible() and window.panel.close_button.hasFocus()

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
