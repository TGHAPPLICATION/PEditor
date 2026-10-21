"""G1-09：P1 基本防護——逾時、取消、worker 崩潰後重啟；不執行主動內容（spec P7「P1 起即需」）。

逾時與取消以 worker 的測試 hook（環境變數 PEDITOR_WORKER_TEST_HOOKS=1 才啟用的 `_sleep`）製造
可預期的長操作；產品執行時不設此變數，hook 不存在。
"""

import threading
import time
from pathlib import Path

import pytest

from peditor.core.service import DocumentService, ServiceError

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


@pytest.fixture
def hooked(monkeypatch):
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    with DocumentService(timeout=2.0) as svc:
        yield svc


def test_basic_timeout_and_cancel(hooked):
    doc = hooked.open_document(FILES / "T01.pdf")["document_id"]

    # 逾時：worker 被終止，回 RESOURCE_LIMIT；之後自動重啟並重開文件
    started = time.monotonic()
    with pytest.raises(ServiceError) as exc:
        hooked._send_raw("_sleep", {"seconds": 30})
    assert exc.value.code == "RESOURCE_LIMIT"
    assert time.monotonic() - started < 10
    assert hooked.inspect_page(doc, 0)["text_targets"]

    # 取消：另一執行緒取消進行中的請求，回 CANCELLED；之後仍可繼續使用
    errors = []

    def slow():
        try:
            hooked._send_raw("_sleep", {"seconds": 30}, request_id="slow-1")
        except ServiceError as e:
            errors.append(e.code)

    thread = threading.Thread(target=slow)
    thread.start()
    for _ in range(100):
        if hooked.inflight_request == "slow-1":
            break
        time.sleep(0.02)
    assert hooked.cancel("slow-1")
    thread.join(timeout=10)
    assert errors == ["CANCELLED"]
    assert hooked.inspect_page(doc, 0)["text_targets"]


def test_worker_crash_recovers(service):
    doc = service.open_document(FILES / "T05.pdf")["document_id"]
    service.inspect_page(doc, 0)
    service._worker.proc.kill()  # 模擬 worker 崩潰
    service._worker.proc.wait(timeout=10)
    page = service.inspect_page(doc, 0)  # 自動重啟並以 SHA-256 確認後重開
    assert page["text_targets"]


def test_reopen_detects_external_modification(tmp_path):
    path = tmp_path / "doc.pdf"
    path.write_bytes((FILES / "T05.pdf").read_bytes())
    with DocumentService() as svc:
        doc = svc.open_document(path)["document_id"]
        svc._worker.proc.kill()
        svc._worker.proc.wait(timeout=10)
        path.write_bytes((FILES / "T06.pdf").read_bytes())  # 外部修改
        with pytest.raises(ServiceError) as exc:
            svc.inspect_page(doc, 0)
        assert exc.value.code == "REVISION_CONFLICT"


def test_active_content_reported_not_executed(service):
    """S02 含 OpenAction JavaScript：只回報 ACTIVE_CONTENT，分析正常完成（不執行 JS）。"""
    opened = service.open_document(FILES / "S02.pdf")
    assert opened["document_flags"]["active_content"] == ["JavaScript"]
    page = service.inspect_page(opened["document_id"], 0)
    assert page["capabilities"]["reasons"] == ["ACTIVE_CONTENT"]
    service.close_document(opened["document_id"])


# --- 資料限制（core/limits.py 設定點；worker 端直接在行程內驗證，以縮小上限避免產生巨大檔案）---


def test_file_size_and_page_limits(monkeypatch):
    from peditor.core.protocol import ProtocolError
    from peditor.worker import analyzer

    monkeypatch.setattr(analyzer, "MAX_FILE_BYTES", 1000)
    with pytest.raises(ProtocolError) as exc:
        analyzer.open_document(str(FILES / "T05.pdf"))
    assert exc.value.code == "RESOURCE_LIMIT"

    monkeypatch.setattr(analyzer, "MAX_FILE_BYTES", 200 * 1024 * 1024)
    monkeypatch.setattr(analyzer, "MAX_PAGES", 0)
    document = analyzer.open_document(str(FILES / "T05.pdf"))
    assert document.flags["reasons"] == ["RESOURCE_LIMIT"]
    assert document.pike is None and document.mu is None  # 超限即不保留解析器物件
    with pytest.raises(ProtocolError) as exc:
        analyzer.inspect_page(document, 0)
    assert exc.value.code == "RESOURCE_LIMIT"


def _form_pdf(path, depth: int, cycle: bool) -> None:
    import pikepdf

    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    forms = []
    for _ in range(depth):
        forms.append(pdf.make_stream(b"", Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Form,
                                     BBox=[0, 0, 200, 200]))  # fmt: skip
    for i, form in enumerate(forms):
        child = (
            forms[0] if cycle and i == len(forms) - 1 else (forms[i + 1] if i + 1 < depth else None)
        )
        if child is not None:
            form.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(X=child))
            form.write(b"/X Do")
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(X=forms[0]))
    page.Contents = pdf.make_stream(b"/X Do")
    pdf.save(path)


@pytest.mark.parametrize(("depth", "cycle"), [(12, False), (3, True)])
def test_form_depth_and_cycle_limited(tmp_path, depth, cycle):
    from peditor.worker import analyzer

    path = tmp_path / "forms.pdf"
    _form_pdf(path, depth, cycle)
    document = analyzer.open_document(str(path))
    page = analyzer.inspect_page(document, 0)  # 不得無限遞迴
    assert "MALFORMED_DOCUMENT" in page["capabilities"]["reasons"]
    document.close()


def test_oversized_worker_response_rejected(monkeypatch, tmp_path):
    """worker 回應超過單行上限：讀取時即中止，不整行載入，回 WORKER_FAILED 並重啟。"""
    import sys

    from peditor.core import service as service_mod

    monkeypatch.setattr(service_mod, "MAX_MESSAGE_BYTES", 1000)
    fake = tmp_path / "fake_worker.py"
    fake.write_text("import sys\nsys.stdin.readline()\nsys.stdout.write('x' * 5000 + '\n')\n")
    with DocumentService(command=[sys.executable, str(fake)]) as svc:
        with pytest.raises(ServiceError) as exc:
            svc.open_document(FILES / "T05.pdf")
    assert exc.value.code == "WORKER_FAILED"
