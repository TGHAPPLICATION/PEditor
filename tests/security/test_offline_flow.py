"""G7-01：不使用網路完成開檔、分析、渲染、規劃、預覽、套用、復原、重做、另存（spec P7）。

CI 無法拔網路線；這裡以 Python audit hook 讓主行程與 worker 任何 socket 操作（建立、解析主機名、
連線、bind）都立即失敗，再跑完整流程。實機斷網（含系統防火牆封鎖）見 P7 報告與
`scripts/p7_offline_check.ps1`。
"""

import subprocess
import sys
from pathlib import Path

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


def test_offline_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    monkeypatch.setenv("PEDITOR_TEST_DENY_NETWORK", "1")
    out = tmp_path / "out.pdf"
    command = [sys.executable, "-P", "-c", FLOW, str(FILES / "T01.pdf"), str(out)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert result.returncode == 0 and "OFFLINE-OK" in result.stdout, result.stderr[-2000:]
    assert out.stat().st_size > 0


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
