"""另存與真修改證據（spec §7 export_document、§8.1、§8.2；只在 worker 使用）。

P2 只做「完整重寫、驗證通過才寫出、不覆寫既有檔」；暫存檔、flush、原子 rename 與覆寫交易屬 P3。
驗證：
- 完整另存：trailer 無 /Prev、只有一個 startxref（無增量歷史，§8.1-4）；xref 中沒有不可達物件。
- qpdf 結構檢查（pikepdf check_pdf_syntax）問題數不得多於原檔（§8.2）；重開不需修復、頁數不變。
- 內容差異：逐頁、逐 content stream 比對解析後的運算子（§8.1-1）。
"""

from __future__ import annotations

import difflib
import hashlib
import io
import os

import pikepdf
import pymupdf

from peditor.core.limits import MAX_OBJECT_WALK
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer


def qpdf_problems(data: bytes) -> list[str] | None:
    """qpdf 開檔警告＋語法檢查問題；無法開啟回 None。"""
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            return [*map(str, pdf.get_warnings()), *pdf.check_pdf_syntax()]
    except pikepdf.PdfError:
        return None


def unreachable_objects(pdf: pikepdf.Pdf) -> int:
    """xref 中從 trailer 走不到的間接物件數。"""
    reachable: set[tuple[int, int]] = set()
    stack: list = [pdf.trailer]
    steps = 0
    while stack:
        obj = stack.pop()
        steps += 1
        if steps > MAX_OBJECT_WALK * 10:
            raise ProtocolError("RESOURCE_LIMIT", "物件數超過上限")
        if isinstance(obj, (pikepdf.Dictionary, pikepdf.Array, pikepdf.Stream)):
            if obj.is_indirect:
                if obj.objgen in reachable:
                    continue
                reachable.add(obj.objgen)
            if isinstance(obj, pikepdf.Stream):
                stack.extend(obj.stream_dict.values())
            elif isinstance(obj, pikepdf.Array):
                stack.extend(obj)
            else:
                stack.extend(obj.values())
    # 物件串流容器（/ObjStm）與交叉參照串流（/XRef）是檔案結構本身，依規範不會被參照
    listed = {o.objgen for o in pdf.objects if o is not None and o.objgen != (0, 0)
              and not (isinstance(o, pikepdf.Stream)
                       and str(o.get("/Type", "")) in ("/ObjStm", "/XRef"))}  # fmt: skip
    return len(listed - reachable)


def content_diff(before: bytes, after: bytes) -> list[dict]:
    """逐頁、逐 content stream（依頁面 /Contents 順序）比對解析後的運算子。"""
    changes = []
    with pikepdf.open(io.BytesIO(before)) as old, pikepdf.open(io.BytesIO(after)) as new:
        if len(old.pages) != len(new.pages):
            raise ProtocolError("VALIDATION_FAILED", "頁數改變")
        for page_index, (p0, p1) in enumerate(zip(old.pages, new.pages, strict=True)):
            s0, s1 = _streams(p0), _streams(p1)
            if len(s0) != len(s1):
                changes.append({"page_index": page_index, "kind": "streams", "before": len(s0),
                                "after": len(s1)})  # fmt: skip
                continue
            for order, (a, b) in enumerate(zip(s0, s1, strict=True)):
                ops_a, ops_b = _ops(a), _ops(b)
                matcher = difflib.SequenceMatcher(a=ops_a, b=ops_b, autojunk=False)
                for tag, i0, i1, j0, j1 in matcher.get_opcodes():
                    if tag == "equal":
                        continue
                    changes.append({
                        "page_index": page_index, "stream_order": order, "kind": tag,
                        "before_ops": [i0, i1], "after_ops": [j0, j1],
                        "before": [op.decode("latin-1") for op in ops_a[i0:i1]],
                        "after": [op.decode("latin-1") for op in ops_b[j0:j1]],
                    })  # fmt: skip
    return changes


def resource_diff(before: bytes, after: bytes) -> list[dict]:
    """每頁字型與 XObject 資源名稱的增減（模式 A 應為空）。"""
    out = []
    with pikepdf.open(io.BytesIO(before)) as old, pikepdf.open(io.BytesIO(after)) as new:
        for page_index, (p0, p1) in enumerate(zip(old.pages, new.pages, strict=True)):
            for kind in ("/Font", "/XObject"):
                k0, k1 = _resource_names(p0, kind), _resource_names(p1, kind)
                if k0 != k1:
                    out.append({"page_index": page_index, "kind": kind.lstrip("/"),
                                "added": sorted(k1 - k0), "removed": sorted(k0 - k1)})  # fmt: skip
    return out


def _resource_names(page: pikepdf.Page, kind: str) -> set[str]:
    resources = page.obj.get("/Resources")
    table = resources.get(kind) if isinstance(resources, pikepdf.Dictionary) else None
    return set(map(str, table.keys())) if isinstance(table, pikepdf.Dictionary) else set()


def _streams(page: pikepdf.Page) -> list[pikepdf.Stream]:
    contents = page.obj.get("/Contents")
    items = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
    return [s for s in items if isinstance(s, pikepdf.Stream)]


def _ops(stream: pikepdf.Stream) -> list[bytes]:
    return [pikepdf.unparse_content_stream([inst]) for inst in pikepdf.parse_content_stream(stream)]


def validate(original: bytes, data: bytes) -> dict:
    baseline = qpdf_problems(original)
    problems = qpdf_problems(data)
    report: dict = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "qpdf_baseline": None if baseline is None else len(baseline),
        "qpdf_output": None if problems is None else len(problems),
        "qpdf_new_problems": [],
    }
    failures = []
    if problems is None:
        failures.append("qpdf_open")
    else:
        # 訊息含物件號碼，重寫後會重編，故以問題數判定；訊息只供參考
        report["qpdf_new_problems"] = [p for p in problems if p not in (baseline or [])]
        if len(problems) > len(baseline or []):
            failures.append("qpdf_new_problems")
        with pikepdf.open(io.BytesIO(data)) as pdf:
            report["incremental"] = "/Prev" in pdf.trailer or data.count(b"startxref") != 1
            report["unreachable_objects"] = unreachable_objects(pdf)
            page_count = len(pdf.pages)
        if report["incremental"]:
            failures.append("incremental")
        if report["unreachable_objects"]:
            failures.append("unreachable_objects")
        with pymupdf.open(stream=data, filetype="pdf") as mu, \
                pymupdf.open(stream=original, filetype="pdf") as orig:  # fmt: skip
            report["mupdf_repaired"] = bool(mu.is_repaired)
            if mu.is_repaired:
                failures.append("mupdf_repaired")
            if mu.page_count != orig.page_count or page_count != orig.page_count:
                failures.append("page_count")
    report["failures"] = failures
    report["ok"] = not failures
    return report


def export_document(document: analyzer.Document, destination) -> dict:
    """驗證通過才寫出；目的檔已存在時拒絕（P2 不覆寫，交易式覆寫屬 P3）。"""
    if not isinstance(destination, str) or not destination.lower().endswith(".pdf"):
        raise ProtocolError("INVALID_REQUEST", "目的檔必須是 .pdf")
    if os.path.exists(destination):
        raise ProtocolError("SAVE_FAILED", "目的檔已存在")
    data = document.working_bytes()
    report = validate(document.original, data)
    report["content_changes"] = content_diff(document.original, data)
    report["resource_changes"] = resource_diff(document.original, data)
    if not report["ok"]:
        raise ProtocolError("VALIDATION_FAILED", "輸出驗證失敗：" + ",".join(report["failures"]))
    try:
        with open(destination, "xb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        raise ProtocolError("SAVE_FAILED", "無法寫入目的檔") from exc
    return {"output_hash": report["sha256"], "validation_report": report}
