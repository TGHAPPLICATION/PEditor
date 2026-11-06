"""G7-01：不使用網路完成開檔、分析、渲染、規劃、預覽、套用、復原、重做、另存（spec P7）。

CI 無法拔網路線；這裡以 Python audit hook 讓主行程與 worker 的 Python 層 socket 事件
（建立、解析主機名、連線、bind）都立即失敗並記錄，再跑完整流程，最後確認兩邊都沒有任何事件——
被 worker 內部吞掉的嘗試也會留下紀錄（P7 獨立核對 V3）。原生函式庫（MuPDF、qpdf）直接開的 socket
不經 audit hook，由 G7-02 的 socket 監測涵蓋。實機斷網見 P7 報告與 `scripts/p7_offline_check.ps1`。
"""

import subprocess
import sys
from pathlib import Path

from peditor.core.service import DocumentService

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"

FLOW = """
import sys
events = []
def deny(event, args):
    if event.startswith("socket."):
        events.append(event)
        raise RuntimeError("network: " + event)
sys.addaudithook(deny)
from peditor.core.service import DocumentService
with DocumentService() as svc:
    opened = svc.open_document(sys.argv[1])
    doc = opened["document_id"]
    page = svc.inspect_page(doc, 0)
    svc.render_page(doc, 0)
    target = next(t for t in page["text_targets"] if "衛生局" in t["text"])
    plan = svc.plan_text_edit(doc, target["target_id"], target["text"].replace("衛生局", "測試局"))
    assert plan["ready"], plan["unsupported_reasons"]
    svc.preview_edit(doc, plan["plan_id"], opened["revision"])
    revision = svc.apply_edit(doc, plan["plan_id"], opened["revision"])["new_revision"]
    revision = svc.undo(doc, revision)["new_revision"]
    revision = svc.redo(doc, revision)["new_revision"]
    token = svc.destination_token(sys.argv[2])
    report = svc.export_document(doc, token, revision)
    assert report["validation_report"]["ok"], report
assert not events, events
print("OFFLINE-OK")
"""


def _deny_env(monkeypatch, log: Path) -> None:
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    monkeypatch.setenv("PEDITOR_TEST_DENY_NETWORK", "1")
    monkeypatch.setenv("PEDITOR_TEST_NETWORK_LOG", str(log))


def test_offline_flow(tmp_path, monkeypatch):
    log = tmp_path / "worker-network.log"
    _deny_env(monkeypatch, log)
    out = tmp_path / "out.pdf"
    command = [sys.executable, "-P", "-c", FLOW, str(FILES / "T01.pdf"), str(out)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert result.returncode == 0 and "OFFLINE-OK" in result.stdout, result.stderr[-2000:]
    assert out.stat().st_size > 0
    assert not log.exists() or log.read_text(encoding="utf-8") == ""  # worker 端沒有任何事件


def test_deny_hook_blocks_sockets(monkeypatch):
    """對照：同一個 audit hook 確實會擋下 socket（避免空檢查）。"""
    code = (
        "import sys\n"
        "def deny(e, a):\n"
        "    if e.startswith('socket.'): raise RuntimeError(e)\n"
        "sys.addaudithook(deny)\n"
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('127.0.0.1', 9), timeout=1)\n"
        "except RuntimeError:\n"
        "    print('BLOCKED')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert "BLOCKED" in result.stdout, result.stderr


def test_worker_hook_records_swallowed_attempts(tmp_path, monkeypatch):
    """對照：worker 內部嘗試建立 socket 並吞掉錯誤時，紀錄檔仍有事件（worker 端的檢查不是空的）。"""
    log = tmp_path / "worker-network.log"
    _deny_env(monkeypatch, log)
    with DocumentService() as svc:
        assert svc._send_raw("_socket", {}) == {"created": False}
    assert "socket." in log.read_text(encoding="utf-8")
