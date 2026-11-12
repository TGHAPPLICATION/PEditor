import gc

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from peditor.core.service import DocumentService
from peditor.ui.app import MainWindow


@pytest.fixture(autouse=True)
def _destroy_widgets_at_teardown():
    """P4 U15：pytest-qt 收尾時只 close() 與 deleteLater()，視窗要到下一個測試的事件迴圈
    才刪除，MainWindow 的循環參照也要等之後的 GC，會在其他測試進行中（背景工作執行中）
    才銷毀。autouse 最先建立、最後收尾：在 qtbot 關閉視窗、make_window 關閉服務之後，
    於主執行緒立即處理延遲刪除並回收。"""
    yield
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


@pytest.fixture
def make_window(qtbot):
    services = []

    def make(service=None, **kwargs):
        service = service or DocumentService()
        services.append(service)
        # 未另存提醒（ADR-0027）的預設對話框會擋住測試；需要測它的測試自行傳入 ask_unsaved
        kwargs.setdefault("ask_unsaved", lambda: "discard")
        window = MainWindow(service, **kwargs)
        qtbot.addWidget(window)
        window.show()
        return window

    yield make
    for service in services:
        service.close()
