"""G4-06：worker 執行長操作時主執行緒不被阻塞（事件迴圈間隔 ≤ 100 ms）。"""

from PySide6.QtCore import QElapsedTimer, QTimer
from test_e2e import FILES, open_file, wait

LIMIT_MS = 100


def test_ui_not_blocked(qtbot, make_window, monkeypatch):
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    window = make_window()
    open_file(qtbot, window, FILES / "F04.pdf")
    clock, gaps, last = QElapsedTimer(), [], [0]
    clock.start()

    def tick():
        now = clock.elapsed()
        gaps.append(now - last[0])
        last[0] = now

    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(tick)
    service = window.service
    started = clock.elapsed()
    window._run(lambda: service._send_raw("_sleep", {"seconds": 1.5}), lambda _: None)
    submit_ms = clock.elapsed() - started
    assert window.busy and window.actions["cancel"].isEnabled()
    last[0] = clock.elapsed()
    timer.start()
    wait(qtbot, window)
    timer.stop()
    assert submit_ms <= LIMIT_MS
    assert len(gaps) >= 50 and max(gaps) <= LIMIT_MS, max(gaps)
