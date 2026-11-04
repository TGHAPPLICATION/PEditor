"""G7-03：惡意樣本不啟動外部程式、不連線；受控拒絕（spec P7、ADR-0007、ADR-0024）。

S02（OpenAction JavaScript）、S05（嵌入附件）、S06（Launch，執行時會在目前資料夾建立 sentinel 檔）、
S03（壓縮炸彈）經 worker 開啟、判定、逐頁分析、渲染與另存，之後：
- 目前資料夾沒有 sentinel 檔（Launch 沒有被執行）；
- 回應全部是理由碼，worker 仍可用（不是崩潰）；
- 沒有任何連線（同 test_no_listener 的檢查方式）。
"""

from pathlib import Path

import pytest
from network import connections

from peditor.core.service import DocumentService, ServiceError

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
EXPECTED = {
    "S02": ("document", "ACTIVE_CONTENT"),
    "S05": ("document", "ACTIVE_CONTENT"),
    "S06": ("document", "ACTIVE_CONTENT"),
    "S03": ("page", "RESOURCE_LIMIT"),
}


@pytest.mark.parametrize("fid", sorted(EXPECTED))
def test_no_external_launch(fid, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # worker 繼承目前資料夾；Launch 若被執行會在此建立 sentinel 檔
    level, reason = EXPECTED[fid]
    with DocumentService() as svc:
        opened = svc.open_document(FILES / f"{fid}.pdf")
        doc = opened["document_id"]
        assessment = svc.assess_editability(doc)
        if level == "document":
            assert assessment["document"] == {"status": "reject", "reasons": [reason]}
        page = svc.inspect_page(doc, 0)
        assert reason in page["capabilities"]["reasons"]
        if reason == "RESOURCE_LIMIT":  # 超限頁面不交給 MuPDF 渲染：受控拒絕
            with pytest.raises(ServiceError) as exc:
                svc.render_page(doc, 0)
            assert exc.value.code == "RESOURCE_LIMIT"
        else:
            svc.render_page(doc, 0)
        token = svc.destination_token(tmp_path / "out.pdf")
        try:
            svc.export_document(doc, token, opened["revision"])
        except ServiceError as exc:
            assert exc.code in {"VALIDATION_FAILED", "RESOURCE_LIMIT"}, exc.code
        worker_pid = svc._worker.proc.pid
        assert connections([worker_pid]) == []
        svc.close_document(doc)
        assert svc._worker.proc.poll() is None  # worker 沒有崩潰
    assert not list(tmp_path.glob("peditor-sentinel*"))
