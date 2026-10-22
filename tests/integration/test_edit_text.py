"""P2 文字編輯：模式 A 就地改寫（G2-02 模式 A 部分、G2-04 部分、G2-06、G2-19、G2-20 E01）。

模式 B（P2 步驟 7）完成前，需模式 B 的案例在計畫階段回 GLYPH_MISSING 並註明尚未實作；
G2-01「全部宣告支援案例」於步驟 7 補齊。
"""

import csv
import hashlib
from pathlib import Path

import pikepdf
import pypdfium2
import pytest

from peditor.core.protocol import ProtocolError
from peditor.core.service import DocumentService
from peditor.worker import analyzer, edit, span
from peditor.worker.content import interpret

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FILES = FIXTURES / "files"
# 原字型子集含全部新字（fontTools 檢查字形輪廓）→ 模式 A。其餘 support 案例需模式 B（步驟 7）。
MODE_A = {"T01", "T02", "T08", "F01", "F04", "L02", "L03"}
ORIGIN_TOL = 0.01  # pt


def _manifest():
    with open(FIXTURES / "manifest.csv", encoding="utf-8", newline="") as fh:
        return {r["fixture_id"]: r for r in csv.DictReader(fh)}


def _edit_cases():
    with open(FIXTURES / "edit_cases.csv", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _region(text: str) -> list[float]:
    return [float(v) for v in text.split(",")]


def _mode_a_cases():
    rows = _manifest()
    cases = [(fid, rows[fid]["original_text"], rows[fid]["new_text"],
              rows[fid]["editable_region_pt"]) for fid in sorted(MODE_A)]  # fmt: skip
    cases += [(c["fixture_id"], c["original_text"], c["new_text"], c["editable_region_pt"])
              for c in _edit_cases() if not c["after_case"]]  # fmt: skip
    return cases


def _plan(document, old, new, region, policy="prefer_a"):
    params = {
        "target_id": span.find(document, 0, old).span_id,
        "new_text": new,
        "policy": policy,
        "editable_region": _region(region),
    }
    return edit.plan_text_edit(document, params)


def _texts(data: bytes) -> tuple[str, str]:
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        mu = doc[0].get_text().replace("\n", "")
    pdf = pypdfium2.PdfDocument(data)
    try:
        pdfium = pdf[0].get_textpage().get_text_range().replace("\r\n", "").replace("\n", "")
    finally:
        pdf.close()
    return mu, pdfium


def _ops(data: bytes) -> list[list[tuple]]:
    """每頁每個 content stream 的解析後運算子（用於差異比對）。"""
    with pikepdf.open(__import__("io").BytesIO(data)) as pdf:
        out = []
        for page in pdf.pages:
            for inst in pikepdf.parse_content_stream(page):
                out.append((str(inst.operator), pikepdf.unparse_content_stream([inst])))
        return out


@pytest.mark.parametrize(("fid", "old", "new", "region"), _mode_a_cases())
def test_target_occurrence_replaced_dual_engine(fid, old, new, region):
    """模式 A：只有目標運算子被改寫；兩引擎都擷取到新文、目標位置不再有舊文。"""
    document = analyzer.open_document(str(FILES / f"{fid}.pdf"))
    try:
        original = document.working_bytes()
        before_count = _texts(original)[0].count(old)
        plan = _plan(document, old, new, region)
        assert plan["ready"] and plan["mode"] == "A", (
            plan["unsupported_reasons"],
            plan["warnings"],
        )
        assert plan["font_changes"] == []  # 模式 A 不換字型（G2-5）
        edit.apply_edit(document, plan["plan_id"], 0)
        assert document.revision == 1
        result = document.working_bytes()
        mu, pdfium = _texts(result)
        assert new in mu and new in pdfium
        assert mu.count(old) == before_count - 1  # 只移除目標 occurrence
        before_ops, after_ops = _ops(original), _ops(result)
        changed = [i for i, (a, b) in enumerate(zip(before_ops, after_ops, strict=True)) if a != b]
        assert len(changed) == 1 and after_ops[changed[0]][0] in ("TJ", "Tj")
    finally:
        document.close()


def _stream_key(document, run):
    """(頁面 content stream 順序, 運算子索引)；儲存會重編物件號碼，不能用 objgen 比對前後。"""
    contents = document.pike.pages[0].obj.Contents
    streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
    return ([s.objgen for s in streams].index(run.stream), run.op_index)


def _origins(document):
    runs = interpret(document.pike.pages[0]).runs
    return [
        (_stream_key(document, r), i, g.unicode, g.origin)
        for r in runs
        for i, g in enumerate(r.glyphs)
    ]


@pytest.mark.parametrize(("fid", "old", "new"), [
    ("F04", "Hello", "Hi"),  # E03：較短，後續「 World」不得移動
    ("F04", "World", "Earth"),
    ("T02", "10 月 31 日", "11 月 5 日"),
    ("T01", "衛生局", "測試局"),
])  # fmt: skip
def test_following_glyphs_unmoved(fid, old, new):
    """G2-19：字寬不同時以 TJ 位移補償，目標之後的字形原點不變（ADR-0018 §2）。"""
    document = analyzer.open_document(str(FILES / f"{fid}.pdf"))
    try:
        sel = span.resolve(document, span.find(document, 0, old))
        change = span.change(sel, new)
        piece = change.pieces[0]
        run = sel.runs[piece.run_index]
        op = _stream_key(document, run)
        before = [o for o in _origins(document) if o[0] != op or o[1] >= piece.g1]
        plan = _plan(document, old, new, "0,0,999,999")
        edit.apply_edit(document, plan["plan_id"], 0)
        shift = len(change.new_text) - (piece.g1 - piece.g0)
        after = {(o[0], o[1] - shift if o[0] == op else o[1]): o for o in _origins(document)}
        for op_index, index, uni, (x, y) in before:
            if op_index == op and index < piece.g0:
                continue
            _, _, uni2, (x2, y2) = after[(op_index, index)]
            assert uni == uni2
            assert abs(x - x2) <= ORIGIN_TOL and abs(y - y2) <= ORIGIN_TOL, (uni, x, x2)
    finally:
        document.close()


def test_overflow_rejected():
    """G2-06：超出可改動區域一律 TEXT_OVERFLOW，不縮字；計畫不可套用、文件不變。"""
    row = _manifest()["T01"]
    document = analyzer.open_document(str(FILES / "T01.pdf"))
    try:
        plan = _plan(document, "衛生局", "衛生局局局局", row["editable_region_pt"])
        assert plan["unsupported_reasons"] == ["TEXT_OVERFLOW"] and not plan["ready"]
        with pytest.raises(ProtocolError) as exc:
            edit.apply_edit(document, plan["plan_id"], 0)
        assert exc.value.code == "INVALID_REQUEST"
        assert document.revision == 0
    finally:
        document.close()


def test_rejections_leave_files_unchanged():
    """G2-04（模式 A 部分）：缺字回 GLYPH_MISSING；拒絕不改磁碟檔與工作文件。"""
    rows = _manifest()
    for fid in ("F03", "F02"):
        path = FILES / f"{fid}.pdf"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        document = analyzer.open_document(str(path))
        try:
            working = document.working_bytes()
            plan = _plan(document, rows[fid]["original_text"], rows[fid]["new_text"],
                         rows[fid]["editable_region_pt"], policy="a_only")  # fmt: skip
            assert plan["unsupported_reasons"] == ["GLYPH_MISSING"] and plan["mode"] is None
            assert document.revision == 0 and document.working_bytes() == working
        finally:
            document.close()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest == rows[fid]["sha256"]


def test_stale_plan_and_revision_conflict():
    document = analyzer.open_document(str(FILES / "T01.pdf"))
    try:
        region = _manifest()["T01"]["editable_region_pt"]
        first = _plan(document, "衛生局", "測試局", region)
        second = _plan(document, "衛生局", "測試局", region)
        with pytest.raises(ProtocolError) as exc:
            edit.apply_edit(document, first["plan_id"], 5)
        assert exc.value.code == "REVISION_CONFLICT"
        edit.apply_edit(document, first["plan_id"], 0)
        with pytest.raises(ProtocolError) as exc:  # 套用後舊版本的計畫全部失效
            edit.apply_edit(document, second["plan_id"], 1)
        assert exc.value.code == "INVALID_REQUEST"
    finally:
        document.close()


def test_chained_edit_e01_through_worker():
    """E01（G2-20）：經 worker 連續兩次編輯同一文件；revision 遞增、第二次以第一次結果為基礎。"""
    case = next(c for c in _edit_cases() if c["case_id"] == "E01")
    row = _manifest()["T01"]
    path = FILES / "T01.pdf"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with DocumentService() as svc:
        doc = svc.open_document(path)
        did = doc["document_id"]
        for revision, (old, new, region) in enumerate([
            (row["original_text"], row["new_text"], row["editable_region_pt"]),
            (case["original_text"], case["new_text"], case["editable_region_pt"]),
        ]):  # fmt: skip
            page = svc.inspect_page(did, 0, expected_revision=revision)
            target = next(t for t in page["text_targets"] if old in t["text"])
            start = target["text"].index(old)
            span_id = f"span:{target['target_id']}:c{start}-{start + len(old)}"
            plan = svc.plan_text_edit(did, span_id, new, expected_revision=revision,
                                      editable_region=_region(region))  # fmt: skip
            assert plan["ready"] and plan["mode"] == "A"
            assert svc.apply_edit(did, plan["plan_id"], revision)["new_revision"] == revision + 1
        texts = [t["text"] for t in svc.inspect_page(did, 0, expected_revision=2)["text_targets"]]
        assert any("衛生局" in t for t in texts) and not any("測試局" in t for t in texts)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest  # 原檔不變
