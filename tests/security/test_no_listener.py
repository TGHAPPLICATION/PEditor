"""G7-02：本架構沒有 HTTP listener，app 與全部子行程沒有任何 socket（spec P7、ADR-0004）。

IPC 只用 stdin／stdout 管線，不開任何 TCP／UDP socket（含 loopback）。完整的開檔、分析、渲染、
規劃、預覽、套用、另存流程進行期間，背景執行緒持續輪詢（每 0.2 秒，加上每次列舉本身的時間）
測試行程（扮演 app 主行程）與 worker 整棵行程樹的 socket，結束後再查一次，全部必須為空
（P7 獨立核對 V4）。輪詢可能漏掉短於間隔的 socket；Python 層的嘗試由 G7-01 的 audit hook 涵蓋。
實機的對外連線監測見 P7 報告與 `scripts/p7_offline_check.ps1`。
"""

import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from network import connections

from peditor.core.service import DocumentService

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_connection_check_detects_sockets():
    """對照：測試行程自己開 loopback listener 時，檢查方式確實列得出來（避免空檢查）。"""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        assert any(f":{port}" in row for row in connections([], include_self=True))


def test_connection_check_covers_child_processes():
    """對照：子行程（經 venv 轉介程式啟動的直譯器）開 listener 時，以父行程查詢也列得出來。"""
    code = (
        "import socket, sys, time\n"
        "s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen()\n"
        "print(s.getsockname()[1], flush=True)\n"
        "time.sleep(60)\n"
    )
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        port = int(child.stdout.readline())
        assert any(f":{port}" in row for row in connections([], include_self=True))
    finally:
        child.kill()
        child.wait()


def test_no_listening_sockets(tmp_path):
    with DocumentService() as svc:
        opened = svc.open_document(FILES / "T01.pdf")
        worker = svc._worker.proc.pid
        seen: list[str] = []
        errors: list[BaseException] = []
        polls = [0]
        stop = threading.Event()

        def poll() -> None:
            while not stop.is_set():
                try:
                    seen.extend(connections([worker], include_self=True))
                    polls[0] += 1
                except BaseException as exc:  # noqa: BLE001 — 列舉失敗須讓測試失敗
                    errors.append(exc)
                    return
                time.sleep(0.2)

        poller = threading.Thread(target=poll, daemon=True)
        poller.start()
        try:
            doc = opened["document_id"]
            page = svc.inspect_page(doc, 0)
            svc.render_page(doc, 0)
            target = next(t for t in page["text_targets"] if "衛生局" in t["text"])
            new_text = target["text"].replace("衛生局", "測試局")
            plan = svc.plan_text_edit(doc, target["target_id"], new_text)
            assert plan["ready"], plan["unsupported_reasons"]
            svc.preview_edit(doc, plan["plan_id"], opened["revision"])
            applied = svc.apply_edit(doc, plan["plan_id"], opened["revision"])
            token = svc.destination_token(tmp_path / "out.pdf")
            svc.export_document(doc, token, applied["new_revision"])
            while polls[0] < 2 and not errors:  # 流程很快時至少輪詢兩次
                time.sleep(0.1)
        finally:
            stop.set()
            poller.join(timeout=120)
        assert not errors, errors
        assert seen == []
        assert connections([worker], include_self=True) == []
