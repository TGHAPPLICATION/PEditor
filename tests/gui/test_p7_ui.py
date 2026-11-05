"""P7：關閉時等待執行中工作有上限（ADR-0021 增補）；開啟 0 頁文件不留下前一份文件（P4 U13）。"""

import threading
import time
from pathlib import Path

from PySide6.QtWidgets import QGraphicsRectItem

from peditor.ui import jobs

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
TIMEOUT = 60_000


def test_shutdown_wait_is_bounded(qtbot, monkeypatch):
    """取消不了的工作：超過上限即呼叫 kill，kill 後再超過上限即返回，不無限等待。"""
    monkeypatch.setattr(jobs, "SHUTDOWN_WAIT_S", 0.2)
    runner = jobs.JobRunner()
    release = threading.Event()
    runner.submit(lambda: release.wait(10), lambda _: None, lambda _: None)
    time.sleep(0.05)
    killed = []
    started = time.monotonic()
    runner.shutdown(cancel=lambda: None, kill=lambda: killed.append(True))
    assert time.monotonic() - started < 2
    assert killed == [True]
    release.set()


def test_zero_page_document_clears_previous_page(qtbot, make_window):
    window = make_window()
    window.open_path(str(FILES / "T01.pdf"))
    qtbot.waitUntil(lambda: window.page is not None and not window.busy, timeout=TIMEOUT)
    assert any(isinstance(i, QGraphicsRectItem) for i in window.view.scene().items())
    window.open_path(str(FILES / "U02.pdf"))  # 加密：0 頁
    qtbot.waitUntil(lambda: window.page_count == 0 and not window.busy, timeout=TIMEOUT)
    assert window.view.scene().items() == []
    assert window.page is None and window.view.target_at(10, 10) is None
