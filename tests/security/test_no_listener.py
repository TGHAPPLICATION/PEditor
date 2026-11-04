"""G7-02：本架構沒有 HTTP listener，app 與全部子行程沒有任何 socket（spec P7、ADR-0004）。

IPC 只用 stdin／stdout 管線，不開任何 TCP／UDP socket（含 loopback）。這裡在完整的
開檔、分析、渲染、規劃、套用、預覽、另存流程進行中與結束後，列出測試行程（扮演 app 主行程）
與 worker 的 socket，必須為空。實機的對外連線監測（含系統防火牆封鎖）見 P7 報告與
`scripts/p7_offline_check.ps1`。
"""

import socket
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


def test_no_listening_sockets(tmp_path):
    with DocumentService() as svc:
        opened = svc.open_document(FILES / "T01.pdf")
        doc = opened["document_id"]
        page = svc.inspect_page(doc, 0)
        svc.render_page(doc, 0)
        target = next(t for t in page["text_targets"] if "衛生局" in t["text"])
        plan = svc.plan_text_edit(
            doc, target["target_id"], target["text"].replace("衛生局", "測試局")
        )
        assert plan["ready"], plan["unsupported_reasons"]
        svc.preview_edit(doc, plan["plan_id"], opened["revision"])
        applied = svc.apply_edit(doc, plan["plan_id"], opened["revision"])
        worker = svc._worker.proc.pid
        assert connections([worker], include_self=True) == []
        token = svc.destination_token(tmp_path / "out.pdf")
        svc.export_document(doc, token, applied["new_revision"])
        assert connections([worker], include_self=True) == []
