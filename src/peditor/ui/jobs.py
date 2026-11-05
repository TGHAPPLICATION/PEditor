"""背景工作：DocumentService 呼叫在單一背景執行緒依序執行，
結果經 Qt signal 回主執行緒（ADR-0021 §2）。

主執行緒不等待 worker（G4-06）；例外是關閉時的 shutdown（ADR-0021 §2，P4 U11）。
取消直接呼叫 DocumentService.cancel（可跨執行緒）。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait

from PySide6.QtCore import QCoreApplication, QObject, Signal

from peditor.core.service import ServiceError

SHUTDOWN_WAIT_S = 10.0  # 關閉時等待執行中工作的上限（每階段；P7）


class JobRunner(QObject):
    _finished = Signal(object, object, object)  # 回呼, 結果, 錯誤
    busy_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="peditor-job")
        self._pending = 0
        self._futures: set[Future] = set()
        self._closed = False
        self._abandoned = False  # shutdown 逾時返回：之後才結束的工作不再送回結果
        self._finished.connect(self._deliver)

    @property
    def busy(self) -> bool:
        return self._pending > 0

    @property
    def closed(self) -> bool:
        return self._closed

    def submit(self, func: Callable[[], object], on_done: Callable[[object], None],
               on_error: Callable[[ServiceError], None]) -> None:  # fmt: skip
        if self._closed:  # 視窗關閉後不再接受工作（P4 U11）
            return
        self._pending += 1
        if self._pending == 1:
            self.busy_changed.emit(True)

        def run() -> None:
            try:
                result = func()
            except ServiceError as exc:
                outcome = (on_error, None, exc)
            except Exception:  # noqa: BLE001 — 不讓背景例外消失；訊息不帶細節（CLAUDE.md）
                outcome = (on_error, None, ServiceError("WORKER_FAILED", "未預期錯誤"))
            else:
                outcome = (on_done, result, None)
            if not self._abandoned:  # 視窗可能已銷毀：不對它發 signal（P7）
                self._finished.emit(*outcome)

        future = self._pool.submit(run)
        self._futures.add(future)
        future.add_done_callback(self._futures.discard)

    def _deliver(self, callback, result, error) -> None:
        self._pending -= 1
        try:
            callback(error if error is not None else result)
        finally:
            if self._pending == 0:
                self.busy_changed.emit(False)

    def shutdown(self, cancel: Callable[[], object] | None = None,
                 kill: Callable[[], object] | None = None) -> None:  # fmt: skip
        """關閉（P4 U11）：不再接受工作、取消排隊中的工作；執行中的工作每 50 ms 呼叫一次 cancel
        直到結束（多段呼叫的工作在兩段之間取消不到，須重試），再把已完成工作的結果送回主執行緒。
        總等待有上限（P7，ADR-0021 增補）：超過 SHUTDOWN_WAIT_S 仍未結束即呼叫 kill（終止 worker），
        再等 SHUTDOWN_WAIT_S 後不論結果都返回；仍在主行程端運算的工作留在背景執行緒，
        行程結束時才等它完成，結果不再送回（視窗可能已銷毀）。
        工作不得攔下 CANCELLED 後重試，否則不會結束。"""
        self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)
        deadline = time.monotonic() + SHUTDOWN_WAIT_S
        killed = False
        while running := [f for f in list(self._futures) if not f.done()]:
            if time.monotonic() > deadline:
                if killed or kill is None:
                    self._abandoned = True  # 先設旗標：之後才結束的工作不再發 signal
                    break
                kill()
                killed, deadline = True, time.monotonic() + SHUTDOWN_WAIT_S
            if cancel is not None:
                cancel()
            wait(running, timeout=0.05)
        QCoreApplication.sendPostedEvents(self)
