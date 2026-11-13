"""頁面工具：依「來源檔＋頁碼」清單組成新 PDF（ADR-0029；只在 worker 使用）。

每份來源先過一般開檔檢查（大小、加密、損毀、資源上限、簽章、主動內容等，任一不支援即拒絕），
另拒絕有表單欄位的檔案（合併後欄位名稱會衝突）。頁面以 pikepdf 複製（內容、資源、註解、
頁面大小與旋轉）；不保留書籤、文件層級的結構樹與 JavaScript。
寫出前重新開啟比對頁數與每頁內容串流；通過才以 `xb` 寫入主行程給的暫存路徑（ADR-0020 §3）。
"""

from __future__ import annotations

import hashlib
import io
import os

import pikepdf

from peditor.core.limits import MAX_COMPOSE_BYTES, MAX_COMPOSE_SOURCES, MAX_FILE_BYTES, MAX_PAGES
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, export


def compose_pages(params: dict) -> dict:
    sources, plan, destination = (
        params.get("sources"),
        params.get("plan"),
        params.get("destination"),
    )
    if (not isinstance(sources, list) or not 1 <= len(sources) <= MAX_COMPOSE_SOURCES
            or not all(isinstance(s, str) for s in sources)):  # fmt: skip
        raise ProtocolError("INVALID_REQUEST", "來源檔清單錯誤")
    if not isinstance(destination, str) or not destination.lower().endswith(".pdf"):
        raise ProtocolError("INVALID_REQUEST", "目的檔必須是 .pdf")
    if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_PAGES:
        raise ProtocolError("INVALID_REQUEST", "頁面清單錯誤")
    if os.path.exists(destination):
        raise ProtocolError("SAVE_FAILED", "目的檔已存在")
    documents: list[analyzer.Document] = []
    try:
        total = 0
        for path in sources:
            document = analyzer.open_document(path)
            documents.append(document)
            total += len(document.original or b"")
            if total > MAX_COMPOSE_BYTES:
                raise ProtocolError("RESOURCE_LIMIT", "來源檔合計超過大小上限")
            _check_source(document, len(documents))
        pages = []
        for item in plan:
            ints = isinstance(item, list) and all(
                isinstance(v, int) and not isinstance(v, bool) for v in item
            )
            if not ints or len(item) != 2:
                raise ProtocolError("INVALID_REQUEST", "頁面清單錯誤")
            source, index = item
            if not 0 <= source < len(documents) or not 0 <= index < documents[source].page_count:
                raise ProtocolError("INVALID_REQUEST", "頁碼超出範圍")
            pages.append((source, index))
        data = _compose(documents, pages)
    finally:
        for document in documents:
            document.close()
    digest = hashlib.sha256(data).hexdigest()
    _write(destination, data)
    return {"output_hash": digest, "page_count": len(pages)}


def _check_source(document: analyzer.Document, number: int) -> None:
    reasons = document.doc_reasons
    if reasons:  # 與開檔相同的判定；訊息只說第幾份檔案，不含路徑
        raise ProtocolError(reasons[0], f"第 {number} 份檔案無法使用（{reasons[0]}）")
    acroform = document.pike.Root.get("/AcroForm")
    if isinstance(acroform, pikepdf.Dictionary) and len(acroform.get("/Fields", [])) > 0:
        raise ProtocolError("UNSUPPORTED_FEATURE", f"第 {number} 份檔案有表單欄位，無法合併或插入")


def _compose(documents: list[analyzer.Document], pages: list[tuple[int, int]]) -> bytes:
    out = pikepdf.new()
    for source, index in pages:
        out.pages.append(documents[source].pike.pages[index])
    for page in out.pages:  # 註解指回原檔頁面的 /P、結構樹索引在新檔無意義，移除以免懸空參照
        if "/StructParents" in page.obj:
            del page.obj["/StructParents"]
        for annot in page.obj.get("/Annots", []):
            if isinstance(annot, pikepdf.Dictionary):
                for key in ("/P", "/StructParent"):
                    if key in annot:
                        del annot[key]
    buffer = io.BytesIO()
    out.save(buffer, deterministic_id=True)
    data = buffer.getvalue()
    if len(data) > MAX_FILE_BYTES:
        raise ProtocolError("RESOURCE_LIMIT", "輸出檔超過大小上限")
    _verify(documents, pages, data)
    return data


def _verify(documents, pages, data: bytes) -> None:
    """重新開啟：無修復警告、頁數相同、每頁內容串流與來源頁相同（spec §8.1 真內容，不是重繪）。"""
    problems = export.qpdf_problems(data)
    if problems is None:
        raise ProtocolError("VALIDATION_FAILED", "輸出驗證失敗：無法重新開啟")
    with pikepdf.open(io.BytesIO(data)) as pdf:
        if pdf.get_warnings() or len(pdf.pages) != len(pages):
            raise ProtocolError("VALIDATION_FAILED", "輸出驗證失敗：頁數不符或需要修復")
        for page, (source, index) in zip(pdf.pages, pages, strict=True):
            original = documents[source].pike.pages[index]
            if _content(page) != _content(original):
                raise ProtocolError("VALIDATION_FAILED", "輸出驗證失敗：頁面內容不符")


def _content(page: pikepdf.Page) -> list[bytes]:
    return [s.read_bytes() for s in export._streams(page)]


def _write(destination: str, data: bytes) -> None:
    try:
        fh = open(destination, "xb")  # noqa: SIM115 — 失敗時須先關閉再刪除
    except OSError as exc:
        raise ProtocolError("SAVE_FAILED", "無法寫入目的檔") from exc
    try:
        with fh:
            export._write(fh, data)
        with open(destination, "rb") as check:
            if check.read(len(data) + 1) != data:
                raise OSError("寫入內容不符")
    except OSError as exc:
        try:
            os.remove(destination)
        except OSError:
            pass
        raise ProtocolError("SAVE_FAILED", "無法寫入目的檔") from exc
