"""標記 PDF：結構樹不被破壞、替代文字規則（G2-17；ADR-0017 含 2026-10-22 修訂）。"""

import csv
import io
from pathlib import Path

import pikepdf
import pymupdf
import pytest

from peditor.worker import analyzer, edit, span
from peditor.worker.content import interpret

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TAGGED = ("T05", "T06", "F06", "L04", "T08", "F07")  # Word 4 份帶 /ActualText；LibreOffice 2 份沒有
WITH_ACTUAL_TEXT = {"T05", "T06", "F06", "L04"}


def _rows():
    with open(FIXTURES / "manifest.csv", encoding="utf-8", newline="") as fh:
        return {r["fixture_id"]: r for r in csv.DictReader(fh)}


def _structure(data: bytes) -> dict:
    """結構樹摘要：元素類型序列、ParentTree 各鍵的陣列長度、頁面 StructParents、頁面 MCID。"""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        root = pdf.Root.StructTreeRoot
        kinds, stack, seen = [], [root.get("/K")], set()
        while stack:
            node = stack.pop()
            if isinstance(node, pikepdf.Array):
                stack.extend(reversed(list(node)))
            elif isinstance(node, pikepdf.Dictionary) and "/S" in node:
                if node.objgen in seen:
                    continue
                seen.add(node.objgen)
                kinds.append(str(node.S))
                stack.append(node.get("/K"))
        nums = list(root.ParentTree.get("/Nums", []))
        parents = {int(k): len(v) if isinstance(v, pikepdf.Array) else 1
                   for k, v in zip(nums[::2], nums[1::2], strict=True)}  # fmt: skip
        page = pdf.pages[0]
        mcids = []
        for inst in pikepdf.parse_content_stream(page):
            if str(inst.operator) == "BDC" and isinstance(inst.operands[1], pikepdf.Dictionary):
                if "/MCID" in inst.operands[1]:
                    mcids.append(int(inst.operands[1].MCID))
        return {"kinds": kinds, "parents": parents, "struct_parents": int(page.obj.StructParents),
                "mcids": mcids}  # fmt: skip


@pytest.mark.parametrize("fid", TAGGED)
def test_tagged_structure_preserved(fid):
    row = _rows()[fid]
    document = analyzer.open_document(str(FIXTURES / "files" / f"{fid}.pdf"))
    try:
        original = document.working_bytes()
        target = span.find(document, 0, row["original_text"])
        region = [float(v) for v in row["editable_region_pt"].split(",")]
        plan = edit.plan_text_edit(document, {"target_id": target.span_id,
                                              "new_text": row["new_text"],
                                              "editable_region": region})  # fmt: skip
        assert plan["ready"], plan["unsupported_reasons"]
        synced = [c for c in plan["resource_changes"] if c["kind"] == "StructElem"]
        assert bool(synced) == (fid in WITH_ACTUAL_TEXT)
        edit.apply_edit(document, plan["plan_id"], 0)
        result = document.working_bytes()
        before, after = _structure(original), _structure(result)
        assert before == after  # 元素、ParentTree、StructParents、MCID 都不變
        assert len(after["mcids"]) == len(set(after["mcids"]))  # 每個 MCID 只出現一次
        if fid in WITH_ACTUAL_TEXT:
            # 同步後的 /ActualText 含新文、不再含舊文；仍等於其涵蓋內容的擷取文字
            covered = "".join(r.text for r in interpret(document.pike.pages[0]).runs)
            with pikepdf.open(io.BytesIO(result)) as pdf:
                actual = [str(o.ActualText) for o in pdf.objects
                          if isinstance(o, pikepdf.Dictionary) and "/ActualText" in o]  # fmt: skip
            assert any(row["new_text"] in a for a in actual)
            assert all(a in covered for a in actual)  # 每個 /ActualText 都是頁面內容的一段
            assert not any(row["original_text"] in a and row["original_text"] not in row["new_text"]
                           for a in actual)  # fmt: skip
            with pymupdf.open(stream=result, filetype="pdf") as doc:  # MuPDF 會讀 /ActualText
                assert row["new_text"] in doc[0].get_text().replace("\n", "")
    finally:
        document.close()


def _tagged_sample(tmp_path, element_extra=None, bdc_extra=b"", parent_tree=True):
    """一頁 Helvetica「Hello World」包在 MCID 0 的標記內容，結構元素 /P 對應之。"""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(400, 200))
    page = pdf.pages[0]
    font = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                                BaseFont=pikepdf.Name.Helvetica,
                                                Encoding=pikepdf.Name.WinAnsiEncoding))  # fmt: skip
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    text = b"BT /F1 24 Tf 72 100 Td (Hello World) Tj ET"
    page.Contents = pdf.make_stream(b"/P <</MCID 0" + bdc_extra + b">> BDC " + text + b" EMC")
    root = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.StructTreeRoot))
    element = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.StructElem, S=pikepdf.Name.P,
                                                   P=root, Pg=page.obj, K=0))  # fmt: skip
    for key, value in (element_extra or {}).items():
        element[key] = value
    root.K = pikepdf.Array([element])
    nums = [0, pikepdf.Array([element])] if parent_tree else []
    root.ParentTree = pdf.make_indirect(pikepdf.Dictionary(Nums=pikepdf.Array(nums)))
    page.obj.StructParents = 0
    pdf.Root.StructTreeRoot = root
    pdf.Root.MarkInfo = pikepdf.Dictionary(Marked=True)
    path = tmp_path / "tagged.pdf"
    pdf.save(path)
    return path


def _plan(path):
    document = analyzer.open_document(str(path))
    target = span.find(document, 0, "Hello")
    plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": "Howdy",
                                          "editable_region": [0, 0, 400, 200]})  # fmt: skip
    return document, plan


@pytest.mark.parametrize(("kwargs", "reason"), [
    ({"element_extra": {"/Alt": pikepdf.String("greeting")}}, "UNSUPPORTED_FEATURE"),
    ({"element_extra": {"/E": pikepdf.String("Hello")}}, "UNSUPPORTED_FEATURE"),
    # ActualText 與內容不相等：MuPDF 擷取改取 ActualText，P1 的字形/Unicode 交叉比對即先拒絕
    ({"element_extra": {"/ActualText": pikepdf.String("Hi World")}},
     "UNSUPPORTED_ENCODING,UNSUPPORTED_LAYOUT"),
    ({"bdc_extra": b" /Alt (greeting)"}, "UNSUPPORTED_FEATURE"),  # 標記內容上的替代文字
    ({"parent_tree": False}, "UNSUPPORTED_FEATURE"),  # MCID 查不到結構元素
])  # fmt: skip
def test_tagged_actualtext_rejected(tmp_path, kwargs, reason):
    document, plan = _plan(_tagged_sample(tmp_path, **kwargs))
    try:
        assert not plan["ready"] and plan["unsupported_reasons"] == reason.split(","), plan
    finally:
        document.close()


def test_tagged_actualtext_equal_is_synced(tmp_path):
    path = _tagged_sample(tmp_path, element_extra={"/ActualText": pikepdf.String("Hello World")})
    document, plan = _plan(path)
    try:
        assert plan["ready"] and plan["mode"] == "A"
        edit.apply_edit(document, plan["plan_id"], 0)
        element = document.pike.Root.StructTreeRoot.K[0]
        assert str(element.ActualText) == "Howdy World"
    finally:
        document.close()
