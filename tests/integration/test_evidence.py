"""真修改證據與完整另存（G2-07、G2-08、G2-09；spec §8.1、§8.2）。"""

import csv
import io
from pathlib import Path

import pikepdf
import pymupdf
import pypdfium2
import pytest

from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, edit, export, span

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FILES = FIXTURES / "files"
MODE_A = ("T01", "T02", "T08", "F01", "F04", "L02", "L03")  # 見 test_edit_text.MODE_A
MODE_B = ("T03", "T04", "T05", "T06", "T07", "F02", "F06", "F07", "L01", "L04", "L05")
ALL = MODE_A + MODE_B


def _rows():
    with open(FIXTURES / "manifest.csv", encoding="utf-8", newline="") as fh:
        return {r["fixture_id"]: r for r in csv.DictReader(fh)}


def _edited(fid: str, tmp_path: Path):
    """套用 manifest 的替換並另存；回傳（原始位元組, 輸出位元組, 匯出結果, 計畫）。"""
    row = _rows()[fid]
    document = analyzer.open_document(str(FILES / f"{fid}.pdf"))
    try:
        target = span.find(document, 0, row["original_text"])
        region = [float(v) for v in row["editable_region_pt"].split(",")]
        plan = edit.plan_text_edit(document, {"target_id": target.span_id,
                                              "new_text": row["new_text"],
                                              "editable_region": region})  # fmt: skip
        assert plan["ready"], plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        out = tmp_path / f"{fid}-out.pdf"
        result = export.export_document(document, str(out))
        return document.original, out.read_bytes(), result, plan
    finally:
        document.close()


@pytest.mark.parametrize("fid", ALL)
def test_operator_diff_evidence(fid, tmp_path):
    """§8.1-1：解析後的運算子差異只在目標 occurrence 的一個文字顯示運算子。
    模式 A：就地改寫該運算子、資源不變；模式 B：該運算子拆成「前段、換字型、新字、換回、後段」，
    只新增一個字型資源（G2-5：先移除舊內容）。"""
    original, output, result, plan = _edited(fid, tmp_path)
    report = result["validation_report"]
    changes = report["content_changes"]
    assert len(changes) == 1, changes
    change = changes[0]
    assert change["kind"] == "replace" and change["page_index"] == 0
    assert change["before_ops"][1] - change["before_ops"][0] == 1
    assert change["before_ops"][0] == change["after_ops"][0]  # 同一位置的運算子被改寫
    if plan["mode"] == "A":
        assert change["after_ops"][1] - change["after_ops"][0] == 1
        assert change["after"][0].rstrip().endswith(("TJ", "Tj"))
        assert report["resource_changes"] == []
    else:
        name = plan["resource_changes"][0]["added"]
        tf = [op for op in change["after"] if op.rstrip().endswith("Tf")]
        assert len(tf) == 2 and tf[0].startswith(name + " ")  # 換成新字型、再換回原字型
        assert all(op.rstrip().endswith(("TJ", "Tf")) for op in change["after"])
        assert report["resource_changes"] == [
            {"page_index": 0, "kind": "Font", "added": [name], "removed": []}
        ]
    # 報告與獨立重算一致
    assert export.content_diff(original, output) == changes


@pytest.mark.parametrize("fid", ALL)
def test_full_rewrite_no_incremental_history(fid, tmp_path):
    """§8.1-4：完整另存、無增量歷史、無不可達物件；舊的目標運算子不存在於任何物件中。"""
    original, output, result, _ = _edited(fid, tmp_path)
    report = result["validation_report"]
    assert report["ok"] and not report["incremental"] and report["unreachable_objects"] == 0
    assert output.count(b"startxref") == 1
    with pikepdf.open(io.BytesIO(output)) as pdf:
        assert "/Prev" not in pdf.trailer
        assert export.unreachable_objects(pdf) == 0
        old_op = report["content_changes"][0]["before"][0].encode("latin-1")
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Stream):
                data = obj.read_bytes() if "/Subtype" not in obj or obj.Subtype != "/Image" else b""
                assert old_op not in data
    row = _rows()[fid]
    old, new = row["original_text"], row["new_text"]
    # 兩引擎擷取：新文存在；舊文只少了目標 occurrence（新文本身含原文時另計）
    with pymupdf.open(stream=original, filetype="pdf") as a, \
            pymupdf.open(stream=output, filetype="pdf") as b:  # fmt: skip
        before, after = a[0].get_text().replace("\n", ""), b[0].get_text().replace("\n", "")
    assert new.replace(" ", "") in after.replace(" ", "")
    assert after.count(old) == before.count(old) - 1 + new.count(old)
    pdf = pypdfium2.PdfDocument(output)
    try:
        text = pdf[0].get_textpage().get_text_range().replace("\r\n", "").replace("\n", "")
    finally:
        pdf.close()
    assert new.replace(" ", "") in text.replace(" ", "")


@pytest.mark.parametrize("fid", ALL)
def test_no_new_qpdf_warnings(fid, tmp_path):
    """§8.2、G2-09：輸出的 qpdf 問題數不多於 manifest 記錄的原檔問題數。"""
    _, output, result, _ = _edited(fid, tmp_path)
    baseline = int(_rows()[fid]["qpdf_warnings"])
    problems = export.qpdf_problems(output)
    assert problems is not None and len(problems) <= baseline
    assert result["validation_report"]["qpdf_output"] == len(problems)


def test_unreachable_count_ignores_only_file_structure_streams():
    """/ObjStm、/XRef 串流不算不可達；真正的孤立物件仍計入（qpdf 另存會丟掉孤立物件，故手寫）。"""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>",
               b"<< /Orphan true >>"]  # fmt: skip
    data = bytearray(b"%PDF-1.7\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    data += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    data += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    with pikepdf.open(io.BytesIO(bytes(data))) as pdf:
        assert export.unreachable_objects(pdf) == 1
    # 同一份文件以物件串流＋交叉參照串流另存：結構串流不計入，孤立物件已被 qpdf 移除
    with pikepdf.open(io.BytesIO(bytes(data))) as pdf:
        buf = io.BytesIO()
        pdf.save(buf, object_stream_mode=pikepdf.ObjectStreamMode.generate)
    with pikepdf.open(io.BytesIO(buf.getvalue())) as pdf:
        assert any(isinstance(o, pikepdf.Stream) and o.get("/Type") == "/ObjStm"
                   for o in pdf.objects if o is not None)  # fmt: skip
        assert export.unreachable_objects(pdf) == 0


def test_export_refuses_existing_destination_and_bad_path(tmp_path):
    document = analyzer.open_document(str(FILES / "T01.pdf"))
    try:
        existing = tmp_path / "exists.pdf"
        existing.write_bytes(b"keep")
        cases = [
            (str(existing), "SAVE_FAILED"),
            (str(tmp_path / "out.txt"), "INVALID_REQUEST"),
            (None, "INVALID_REQUEST"),
        ]
        for destination, code in cases:
            with pytest.raises(ProtocolError) as exc:
                export.export_document(document, destination)
            assert exc.value.code == code
        assert existing.read_bytes() == b"keep"
        assert not (tmp_path / "out.txt").exists()
    finally:
        document.close()


def test_validation_failure_writes_nothing(tmp_path, monkeypatch):
    """驗證失敗（例如新增 qpdf 問題）時不得落地任何輸出（spec §7 失敗規則）。"""
    document = analyzer.open_document(str(FILES / "T01.pdf"))
    try:

        def injected(data):
            return [] if data == document.original else ["injected"]

        monkeypatch.setattr(export, "qpdf_problems", injected)
        out = tmp_path / "out.pdf"
        with pytest.raises(ProtocolError) as exc:
            export.export_document(document, str(out))
        assert exc.value.code == "VALIDATION_FAILED"
        assert not out.exists()
    finally:
        document.close()
