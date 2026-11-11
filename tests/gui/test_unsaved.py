"""ADR-0027：關閉或開啟另一份文件前，提醒尚未另存的修改（另存／不儲存／取消）。"""

import shutil

from test_e2e import FILES, apply, click_target, open_file, page_text, preview, wait

from peditor.core import drafts
from peditor.core.service import DocumentService


def _edited(qtbot, make_window, tmp_path, answers, **kwargs):
    """開 F04、改一處；answers 為依序回覆的選擇，asked 記錄被問了幾次。"""
    asked = []

    def ask():
        asked.append(True)
        return answers.pop(0) if answers else "discard"  # 用完（測試收尾關閉視窗）一律不儲存

    store = drafts.DraftStore(tmp_path / "drafts")
    source = tmp_path / "a.pdf"
    shutil.copyfile(FILES / "F04.pdf", source)
    window = make_window(DocumentService(drafts=store), ask_unsaved=ask, **kwargs)
    open_file(qtbot, window, source)
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    assert window.unsaved and len(store.list()) == 1
    return window, store, asked


def test_close_cancel_keeps_window(qtbot, make_window, tmp_path):
    window, store, asked = _edited(qtbot, make_window, tmp_path, ["cancel"])
    window.close()
    assert asked and window.isVisible() and window.document_id is not None
    assert len(store.list()) == 1  # 取消：草稿與文件都還在


def test_close_discard_closes_and_deletes_draft(qtbot, make_window, tmp_path):
    window, store, asked = _edited(qtbot, make_window, tmp_path, ["discard"])
    window.close()
    assert asked and not window.isVisible() and window.document_id is None
    assert store.list() == []  # 不儲存：照 ADR-0020 §5 刪草稿


def test_close_save_then_closes(qtbot, make_window, tmp_path):
    out = tmp_path / "out.pdf"
    window, store, asked = _edited(qtbot, make_window, tmp_path, ["save"],
                                   ask_save=lambda: str(out))  # fmt: skip
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=30000)
    assert len(asked) == 1  # 另存後再關閉不重複詢問
    assert "Hello Earth" in page_text(out) and store.list() == []


def test_close_save_dialog_cancelled_stays(qtbot, make_window, tmp_path):
    window, _, asked = _edited(qtbot, make_window, tmp_path, ["save"], ask_save=lambda: None)
    window.close()
    assert asked and window.isVisible() and window.unsaved


def test_close_save_failure_stays(qtbot, make_window, tmp_path):
    bad = tmp_path / "missing-folder" / "out.pdf"  # 資料夾不存在：另存失敗
    window, _, asked = _edited(qtbot, make_window, tmp_path, ["save"], ask_save=lambda: str(bad))
    window.close()
    wait(qtbot, window)
    assert asked and window.last_error is not None
    assert window.isVisible() and window.unsaved and not bad.exists()


def test_open_other_file_asks_and_cancel_keeps_document(qtbot, make_window, tmp_path):
    window, store, asked = _edited(qtbot, make_window, tmp_path, ["cancel", "discard"])
    doc = window.document_id
    window.open_path(str(FILES / "T01.pdf"))
    wait(qtbot, window)
    assert len(asked) == 1 and window.document_id == doc and len(store.list()) == 1
    open_file(qtbot, window, FILES / "T01.pdf")  # 第二次選「不儲存」：換檔
    assert len(asked) == 2 and window.document_id != doc and store.list() == []


def test_no_prompt_without_changes_or_after_save(qtbot, make_window, tmp_path):
    out = tmp_path / "out.pdf"
    asked = []
    window = make_window(ask_unsaved=lambda: asked.append(True) or "discard",
                         ask_save=lambda: str(out))  # fmt: skip
    open_file(qtbot, window, FILES / "F04.pdf")
    open_file(qtbot, window, FILES / "F04.pdf")  # 沒有修改：換檔不詢問
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    window.actions["save"].trigger()
    wait(qtbot, window)
    assert not window.unsaved
    window.close()
    assert asked == [] and not window.isVisible()


def test_undo_back_to_original_still_asks(qtbot, make_window, tmp_path):
    """保守判定：改了又全部復原，版本仍與開檔時不同，照樣詢問。"""
    window, _, asked = _edited(qtbot, make_window, tmp_path, ["cancel"])
    window.actions["undo"].trigger()
    wait(qtbot, window)
    window.close()
    assert asked and window.isVisible()


def test_recovered_draft_counts_as_unsaved(qtbot, make_window, tmp_path):
    """復原的草稿修改尚未另存：關閉時要詢問。"""
    window, store, _ = _edited(qtbot, make_window, tmp_path, [])
    window.service.close()  # 模擬異常結束：草稿留下
    asked = []
    second = make_window(DocumentService(drafts=drafts.DraftStore(store.folder)),
                         ask_draft=lambda items: ("recover", items[0]["draft_id"]),
                         ask_unsaved=lambda: asked.append(True) or "cancel")  # fmt: skip
    second.offer_drafts()
    wait(qtbot, second)
    assert second.document_id is not None and second.unsaved
    second.close()
    assert asked and second.isVisible()
    second._ask_unsaved = lambda: "discard"  # 收尾
