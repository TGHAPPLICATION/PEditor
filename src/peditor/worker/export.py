"""另存與真修改證據（spec §7 export_document、§8.1、§8.2；只在 worker 使用）。

worker 只做「完整重寫、驗證通過才建立新檔寫出」；暫存檔命名、原子取代與覆寫交易在主行程
（`peditor.export.transaction`，ADR-0020 §3）。
驗證：
- 完整另存：trailer 無 /Prev、只有一個 startxref（無增量歷史，§8.1-4）；xref 中沒有不可達物件。
- qpdf 結構檢查（pikepdf check_pdf_syntax）問題數不得多於原檔（§8.2）；重開不需修復、頁數不變。
- 內容差異：逐頁、逐 content stream 比對解析後的運算子（§8.1-1）。
- 文字與視覺（P3，ADR-0020 §4）：新文字可擷取；改動頁在可改動區域外沒有超標像素差異。
"""

from __future__ import annotations

import difflib
import hashlib
import io
import math
import os

import pikepdf
import pymupdf

from peditor.core.geometry import bbox_of
from peditor.core.limits import MAX_OBJECT_WALK
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer

# spec §8.2 視覺門檻（與 tests/integration/visual.py 相同）
VISUAL_DPI = 150
CHANNEL_TOL = 8
VISUAL_OUTSIDE_LIMIT = 0.0001
VISUAL_MARGIN_PT = 2.0
# 視覺驗證的渲染像素上限：大頁面降低 DPI，比對工作量有界（P3 triage f015；A2 於 150 DPI 約 8.7 MP）
VISUAL_MAX_PIXELS = 12_000_000


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
                # 只比對前後相同運算子之間的部分：SequenceMatcher 遇大量相同運算子為平方級，
                # 未改動的串流不得進入比對（P2 triage f014）
                lo, hi = _common_ends(ops_a, ops_b)
                matcher = difflib.SequenceMatcher(
                    a=ops_a[lo : len(ops_a) - hi], b=ops_b[lo : len(ops_b) - hi], autojunk=False
                )
                for tag, i0, i1, j0, j1 in matcher.get_opcodes():
                    if tag == "equal":
                        continue
                    i0, i1, j0, j1 = i0 + lo, i1 + lo, j0 + lo, j1 + lo
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


def _common_ends(a: list[bytes], b: list[bytes]) -> tuple[int, int]:
    """相同開頭與相同結尾的運算子數（兩者不重疊）。"""
    limit = min(len(a), len(b))
    lo = 0
    while lo < limit and a[lo] == b[lo]:
        lo += 1
    hi = 0
    while hi < limit - lo and a[-1 - hi] == b[-1 - hi]:
        hi += 1
    return lo, hi


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


def text_check(document: analyzer.Document, data: bytes) -> list[dict]:
    """每筆已套用編輯的新文字（去空白）須出現在輸出該頁的擷取文字中（ADR-0020 §4）。

    同頁之後有可改動區域重疊的編輯時略過（新文字可能已被後續編輯取代）；新文字為空時略過。
    """
    missing = []
    with pymupdf.open(stream=data, filetype="pdf") as mu:
        texts: dict[int, str] = {}
        for i, item in enumerate(document.applied):
            wanted = "".join(item["new_text"].split())
            later = document.applied[i + 1 :]
            if not wanted or any(o["page_index"] == item["page_index"]
                                 and _overlap(o["mask"], item["mask"]) for o in later):  # fmt: skip
                continue
            page_index = item["page_index"]
            if page_index not in texts:
                texts[page_index] = "".join(mu[page_index].get_text().split())
            if wanted not in texts[page_index]:
                missing.append({"page_index": page_index, "edit_index": i})
    return missing


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def visual_check(document: analyzer.Document, data: bytes, pages: set[int]) -> list[dict]:
    """改動頁以 MuPDF 渲染原檔與輸出：可改動區域外擴 2 pt 之外，每通道差異 >8/255 的像素
    比例須 ≤0.01%（spec §8.2、ADR-0020 §4）。回傳超標的頁。"""
    failed = []
    with pymupdf.open(stream=document.original, filetype="pdf") as old, \
            pymupdf.open(stream=data, filetype="pdf") as new:  # fmt: skip
        for page_index in sorted(pages):
            rect = new[page_index].rect
            area = max(rect.width * rect.height, 1)
            zoom = min(VISUAL_DPI / 72, math.sqrt(VISUAL_MAX_PIXELS / area))
            before = old[page_index].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False,
                                                colorspace=pymupdf.csRGB)  # fmt: skip
            after = new[page_index].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False,
                                               colorspace=pymupdf.csRGB)  # fmt: skip
            if (before.width, before.height) != (after.width, after.height):
                failed.append({"page_index": page_index, "size_mismatch": True})
                continue
            to_view = analyzer.page_geometry(document.pike.pages[page_index]).page_to_view(zoom)
            masks = [_mask_pixels(to_view, a["mask"]) for a in document.applied
                     if a["page_index"] == page_index]  # fmt: skip
            limit = int(VISUAL_OUTSIDE_LIMIT * before.width * before.height)
            outside = _outside_pixels(before, after, masks, limit)
            if outside > limit:
                failed.append({"page_index": page_index, "over_outside": outside})
    return failed


def _mask_pixels(to_view, region) -> tuple[int, int, int, int]:
    """頁面座標（pt）的可改動區域外擴 2 pt → 渲染像素矩形（含旋轉；向外取整）。"""
    x0, y0, x1, y1 = region
    grown = (x0 - VISUAL_MARGIN_PT, y0 - VISUAL_MARGIN_PT, x1 + VISUAL_MARGIN_PT,
             y1 + VISUAL_MARGIN_PT)  # fmt: skip
    vx0, vy0, vx1, vy1 = bbox_of(to_view, grown)
    return math.floor(vx0), math.floor(vy0), math.ceil(vx1), math.ceil(vy1)


def _outside_pixels(before: pymupdf.Pixmap, after: pymupdf.Pixmap, masks, limit: int) -> int:
    """遮罩外差異超過門檻的像素數，超過 limit 即停止（P3 triage f015）。

    逐列先整段比對遮罩外的區段，只有內容不同的區段才逐點檢查；遮罩內的像素不走訪。
    """
    width, stride = before.width, before.stride
    a, b = before.samples, after.samples
    count = 0
    for y in range(before.height):
        base = y * stride
        if a[base : base + width * 3] == b[base : base + width * 3]:
            continue
        spans = [(m[0], m[2]) for m in masks if m[1] <= y < m[3]]
        for x0, x1 in _outside_segments(width, spans):
            lo, hi = base + x0 * 3, base + x1 * 3
            if a[lo:hi] == b[lo:hi]:
                continue
            for i in range(lo, hi, 3):
                peak = max(abs(a[i] - b[i]), abs(a[i + 1] - b[i + 1]), abs(a[i + 2] - b[i + 2]))
                if peak > CHANNEL_TOL:
                    count += 1
                    if count > limit:
                        return count
    return count


def _outside_segments(width: int, spans) -> list[tuple[int, int]]:
    """[0, width) 扣掉遮罩區段後的區段。"""
    out, x = [], 0
    for x0, x1 in sorted((max(0, s), min(width, e)) for s, e in spans if e > 0 and s < width):
        if x0 > x:
            out.append((x, x0))
        x = max(x, x1)
    if x < width:
        out.append((x, width))
    return out


def export_document(document: analyzer.Document, destination) -> dict:
    """完整重寫、驗證通過才以 `xb` 建立並寫出 destination（P3 起由主行程給同目錄暫存路徑，
    再由主行程原子取代目的檔；ADR-0020 §3）。寫入失敗時刪除已寫出的部分（f017）。"""
    if not isinstance(destination, str) or not destination.lower().endswith(".pdf"):
        raise ProtocolError("INVALID_REQUEST", "目的檔必須是 .pdf")
    if os.path.exists(destination):
        raise ProtocolError("SAVE_FAILED", "目的檔已存在")
    data = document.working_bytes()
    report = validate(document.original, data)
    report["content_changes"] = content_diff(document.original, data)
    report["resource_changes"] = resource_diff(document.original, data)
    if report["ok"]:
        pages = {c["page_index"] for c in report["content_changes"] + report["resource_changes"]}
        pages |= {a["page_index"] for a in document.applied}
        report["text_missing"] = text_check(document, data)
        report["visual_failed"] = visual_check(document, data, pages)
        if report["text_missing"]:
            report["failures"].append("text_missing")
        if report["visual_failed"]:
            report["failures"].append("visual_outside_mask")
        report["ok"] = not report["failures"]
    if not report["ok"]:
        raise ProtocolError("VALIDATION_FAILED", "輸出驗證失敗：" + ",".join(report["failures"]))
    try:
        fh = open(destination, "xb")  # noqa: SIM115 — 失敗時須先關閉再刪除
    except OSError as exc:
        raise ProtocolError("SAVE_FAILED", "無法寫入目的檔") from exc
    try:
        with fh:
            _write(fh, data)
        with open(destination, "rb") as check:  # 讀回比對：驗證過的內容就是磁碟上的內容
            if check.read(len(data) + 1) != data:
                raise OSError("寫入內容不符")
    except OSError as exc:
        try:
            os.remove(destination)
        except OSError:
            pass
        raise ProtocolError("SAVE_FAILED", "無法寫入目的檔") from exc
    return {"output_hash": report["sha256"], "validation_report": report}


def _write(fh, data: bytes) -> None:
    fh.write(data)
    fh.flush()
    os.fsync(fh.fileno())
