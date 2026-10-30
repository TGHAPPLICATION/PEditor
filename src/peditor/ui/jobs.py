"""背景工作：DocumentService 呼叫在單一背景執行緒依序執行，
結果經 Qt signal 回主執行緒（ADR-0021 §2）。

主執行緒不等待 worker（G4-06）。取消直接呼叫 DocumentService.cancel（可跨執行緒）。
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal

from peditor.core.service import ServiceError


class JobRunner(QObject):
    _finished = Signal(object, object, object)  # 回呼, 結果, 錯誤
    busy_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="peditor-job")
        self._pending = 0
        self._finished.connect(self._deliver)

    @property
    def busy(self) -> bool:
        return self._pending > 0

    def submit(self, func: Callable[[], object], on_done: Callable[[object], None],
               on_error: Callable[[ServiceError], None]) -> None:  # fmt: skip
        self._pending += 1
        if self._pending == 1:
            self.busy_changed.emit(True)

        def run() -> None:
            try:
                result = func()
            except ServiceError as exc:
                self._finished.emit(on_error, None, exc)
            except Exception:  # noqa: BLE001 — 不讓背景例外消失；訊息不帶細節（CLAUDE.md）
                self._finished.emit(on_error, None, ServiceError("WORKER_FAILED", "未預期錯誤"))
            else:
                self._finished.emit(on_done, result, None)

        self._pool.submit(run)

    def _deliver(self, callback, result, error) -> None:
        self._pending -= 1
        try:
            callback(error if error is not None else result)
        finally:
            if self._pending == 0:
                self.busy_changed.emit(False)

    def shutdown(self, wait: bool = False) -> None:
        self._pool.shutdown(wait=wait, cancel_futures=True)
