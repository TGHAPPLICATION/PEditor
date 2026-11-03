"""P4 U9：復原草稿對話框列出全部未逾期草稿；捨棄後再列出其餘，復原一份後其餘保留。
P4 U11：正常關閉視窗刪除草稿。"""

import shutil
import threading
import time

from PySide6.QtCore import Qt
from test_e2e import FILES, apply, click_target, open_file, preview, wait

from peditor.core import drafts
from peditor.core.service import DocumentService
from peditor.ui.app import DraftDialog

SAMPLES = [
    {"draft_id": "0123456789abcdef", "path": "/secret/folder/甲.pdf", "operations": 2,
     "saved_at": 1_800_000_000.0},
    {"draft_id": "fedcba9876543210", "path": "/secret/folder/乙 報告.pdf", "operations": 1,
     "saved_at": 1_800_000_100.0},
    {"draft_id": "00112233445566ff", "path": "/secret/folder/丙😀.pdf", "operations": 5,
     "saved_at": 1_800_000_200.0},
]  # fmt: skip


def test_draft_dialog_lists_all(qtbot):
    dialog = DraftDialog(SAMPLES)
    qtbot.addWidget(dialog)
    texts = [dialog.list.item(i).text() for i in range(dialog.list.count())]
    assert len(texts) == 3
    names = ("甲.pdf", "乙 報告.pdf", "丙😀.pdf")
    for text, draft, name in zip(texts, SAMPLES, names, strict=True):
        assert text.startswith(name) and f"{draft['operations']} 項編輯" in text
        assert "secret" not in text  # 只顯示檔名，不含完整路徑

    for row, action in ((1, "discard"), (2, "recover")):
        dialog.choice = None
        dialog.list.setCurrentRow(row)
        qtbot.mouseClick(dialog.buttons[action], Qt.MouseButton.LeftButton)
        assert dialog.choice == (action, SAMPLES[row]["draft_id"])
    dialog.choice = None
    qtbot.mouseClick(dialog.buttons["later"], Qt.MouseButton.LeftButton)
    assert dialog.choice is None


def _crash_with_edit(qtbot, make_window, store_dir, source):
    window = make_window(DocumentService(drafts=drafts.DraftStore(store_dir)))
    open_file(qtbot, window, source)
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    window.service.close()  # 模擬異常結束：草稿留下


def test_offer_drafts_lists_all_and_reoffers_after_discard(qtbot, make_window, tmp_path):
    store_dir = tmp_path / "drafts"
    sources = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    for source in sources:
        shutil.copyfile(FILES / "F04.pdf", source)
        _crash_with_edit(qtbot, make_window, store_dir, source)

    offered = []

    def ask(items):
        offered.append([d["draft_id"] for d in items])
        action = "discard" if len(offered) == 1 else "recover"
        return action, items[0]["draft_id"]

    window = make_window(DocumentService(drafts=drafts.DraftStore(store_dir)), ask_draft=ask)
    window.offer_drafts()
    qtbot.waitUntil(lambda: window.document_id is not None, timeout=60_000)
    wait(qtbot, window)
    assert len(offered) == 2 and len(offered[0]) == 2  # 兩份都列出
    assert offered[1] == [i for i in offered[0] if i != offered[0][0]]  # 捨棄後再列出其餘
    assert any(t["text"] == "Hello Earth" for t in window.page["text_targets"])


def test_close_window_discards_draft(qtbot, make_window, tmp_path):
    """U11（ADR-0020 §5）：按視窗關閉＝正常 close_document，草稿刪除；異常結束才留下。"""
    store = drafts.DraftStore(tmp_path / "drafts")
    source = tmp_path / "a.pdf"
    shutil.copyfile(FILES / "F04.pdf", source)
    window = make_window(DocumentService(drafts=store))
    open_file(qtbot, window, source)
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    assert len(store.list()) == 1
    window.close()
    assert store.list() == [] and window.document_id is None


def test_close_window_while_busy(qtbot, make_window, tmp_path, monkeypatch):
    """U11：長操作進行中關閉視窗，先取消再關閉文件，不等操作完成；草稿刪除。"""
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    store = drafts.DraftStore(tmp_path / "drafts")
    source = tmp_path / "a.pdf"
    shutil.copyfile(FILES / "F04.pdf", source)
    window = make_window(DocumentService(drafts=store))
    open_file(qtbot, window, source)
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    service = window.service
    window._run(lambda: service._send_raw("_sleep", {"seconds": 20}), lambda _: None)
    qtbot.waitUntil(lambda: service.inflight_request is not None, timeout=60_000)
    started = time.monotonic()
    window.close()
    assert time.monotonic() - started < 10
    assert store.list() == [] and window.document_id is None


def test_close_window_while_busy_between_calls(qtbot, make_window, monkeypatch):
    """U11：工作還在 Python 端（尚未送出請求）時關閉，cancel 打不中；
    須重試到取消成功，不等長操作完成。"""
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    service = window.service

    began = threading.Event()

    def two_steps():
        began.set()
        time.sleep(0.5)
        return service._send_raw("_sleep", {"seconds": 20})

    window._run(two_steps, lambda _: None)
    qtbot.waitUntil(began.is_set)  # 工作已開始（尚未開始會被直接取消，驗不到重試）
    started = time.monotonic()
    window.close()
    assert time.monotonic() - started < 10
    assert service._docs == {}


def test_close_window_delivers_finished_result(qtbot, make_window, tmp_path):
    """U11：關閉時已完成但結果尚未送回主執行緒的工作（例如開檔、復原草稿），先收下再關閉，不留文件與草稿。"""
    store = drafts.DraftStore(tmp_path / "drafts")
    window = make_window(DocumentService(drafts=store))
    service = window.service
    opened = service.open_document(str(FILES / "F04.pdf"))  # 視窗尚不知道這份文件

    began = threading.Event()

    def late():
        began.set()
        time.sleep(0.3)
        return opened

    window._run(late, window._opened)
    qtbot.waitUntil(began.is_set)  # 工作已開始（尚未開始會被直接取消，驗不到晚到的結果）
    window.close()
    assert service._docs == {} and window.document_id is None


def test_close_window_does_not_offer_drafts(qtbot, make_window, tmp_path):
    """U11：關閉中送達的結果若是「再列出草稿」（捨棄後的回呼），不在關閉流程中跳出對話框。"""
    store_dir = tmp_path / "drafts"
    shutil.copyfile(FILES / "F04.pdf", tmp_path / "a.pdf")
    _crash_with_edit(qtbot, make_window, store_dir, tmp_path / "a.pdf")
    asked = []
    window = make_window(DocumentService(drafts=drafts.DraftStore(store_dir)),
                         ask_draft=lambda items: asked.append(items))  # fmt: skip
    began = threading.Event()
    window._run(lambda: (began.set(), time.sleep(0.3)), lambda _: window.offer_drafts())
    qtbot.waitUntil(began.is_set)  # 工作已開始（尚未開始會被直接取消，回呼不會執行）
    window.close()
    assert asked == []
