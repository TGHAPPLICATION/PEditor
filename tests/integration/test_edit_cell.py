"""表格儲存格改字（G6；spec P6、ADR-0013、ADR-0023）。

格線推估、一次改一行、邊線與其他格不變、溢出與合併格拒絕。

真修改證據沿用 P2（模式 A／B）：內容只改目標行的文字運算子；另存驗證含格線比對（rules_check）；
MuPDF（ADR-0015 例外除外）與 PDFium 各自渲染，manifest 事前宣告的可改動區域 +2 pt 外差異 ≤0.01%，
其他格（含同格其他行）擷取文字相同、像素無超標差異。
"""

import io
import re

import pikepdf
import pymupdf
import pypdfium2
import pytest
import visual
from cell_samples import cell_box, ops_pdf, rich_pdf, table_pdf, text

from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, cell, edit, export, span, table
from peditor.worker.content import interpret

SUPPORTED = ("B01", "B02", "B03", "B04", "B05")


def _row(fid):
    return visual.manifest()[fid]


def _floats(text):
    return [float(v) for v in text.split(",")]


def _target_cell(page, row):
    r, c = map(int, row["target"].removeprefix("cell(").removesuffix(")").split(","))
    return next(t for t in page["cell_targets"] if (t["row"], t["col"]) == (r, c))


def _line_index(cell_target, old):
    return next(i for i, line in enumerate(cell_target["lines"]) if old in line["text"])


def _edit(fid, tmp_path):
    """以 manifest 的原文／新文改目標格的那一行並另存。

    回傳（原檔, 輸出, 計畫, 目標格, 驗證報告）。
    """
    row = _row(fid)
    document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
    try:
        target = _target_cell(analyzer.inspect_page(document, 0), row)
        index = _line_index(target, row["original_text"])
        new_line = target["lines"][index]["text"].replace(row["original_text"], row["new_text"])
        plan = cell.plan_cell_edit(document, {"cell_id": target["cell_id"], "line_index": index,
                                              "new_text": new_line})  # fmt: skip
        assert plan["ready"], plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        dest = tmp_path / f"{fid}-out.pdf"
        report = export.export_document(document, str(dest))["validation_report"]
        return document.original, dest.read_bytes(), plan, target, report
    finally:
        document.close()


def _texts_in(data: bytes, box) -> dict[str, str]:
    """兩引擎各自擷取 box（頁面空間）內的文字。"""
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        mu = doc[0].get_text(clip=pymupdf.Rect(*box))
    pdf = pypdfium2.PdfDocument(data)
    try:
        page = pdf[0]
        height = page.get_height()
        textpage = page.get_textpage()
        pd = textpage.get_text_bounded(left=box[0], bottom=height - box[3], right=box[2],
                                       top=height - box[1])  # fmt: skip
    finally:
        pdf.close()
    return {"mupdf": "".join(mu.split()), "pdfium": "".join(pd.split())}


def _rules(data: bytes):
    with pikepdf.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[0]
        found = table.rules(interpret(page), analyzer.page_geometry(page).pdf_to_page())
        return [(r.horizontal, round(r.pos, 3), round(r.a, 3), round(r.b, 3), round(r.width, 3))
                for r in found.horizontal + found.vertical]  # fmt: skip


@pytest.mark.parametrize("fid", SUPPORTED)
def test_all_supported_cell_cases(fid, tmp_path):
    """G6-01：B01–B05 目標格偵測正確（格線中線與 manifest 可改動區域 ≤0.5 pt）、可改，
    雙引擎擷取到新文字。"""
    row = _row(fid)
    original, output, plan, target, report = _edit(fid, tmp_path)
    assert report["ok"], report["failures"]
    assert report["rules_changed"] == [] and report["text_missing"] == []
    region = _floats(row["editable_region_pt"])
    assert max(abs(a - b) for a, b in zip(target["bbox"], region, strict=True)) <= 0.5
    assert plan["mode"] in ("A", "B") and plan["target"]["cell"]["cell_id"] == target["cell_id"]
    assert all(c["page_index"] == 0 for c in report["content_changes"])
    texts = _texts_in(output, target["inner_bbox"])
    for engine, extracted in texts.items():
        assert row["new_text"] in extracted and row["original_text"] not in extracted, engine
    mask = visual.mask_pixels(original, 0, region)
    for engine in visual.engines(fid):
        stats = visual.diff_stats(visual.render(engine, original), visual.render(engine, output),
                                  mask)  # fmt: skip
        assert stats["outside_fraction"] <= visual.OUTSIDE_LIMIT, (engine, stats)


@pytest.mark.parametrize("fid", SUPPORTED)
def test_borders_and_other_cells_unchanged(fid, tmp_path):
    """G6-02：格線位置、範圍與線寬完全不變；其他格與同格其他行的擷取文字相同、像素無超標差異。"""
    original, output, plan, target, report = _edit(fid, tmp_path)
    assert _rules(original) == _rules(output)
    document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
    try:
        cells = analyzer.inspect_page(document, 0)["cell_targets"]
    finally:
        document.close()
    protected = [c["inner_bbox"] for c in cells if c["cell_id"] != target["cell_id"]]
    index = plan["target"]["cell"]["line_index"]
    protected += [line["bbox"] for i, line in enumerate(target["lines"]) if i != index]
    assert len(protected) >= 2
    for box in protected:
        assert _texts_in(original, box) == _texts_in(output, box), box
    for engine in visual.engines(fid):
        before, after = visual.render(engine, original), visual.render(engine, output)
        for box in protected:
            x0, y0, x1, y1 = visual.mask_pixels(original, 0, box)
            crop = (x0 + 3, y0 + 3, x1 - 3, y1 - 3)  # 內縮，排除格線本身的邊緣像素
            stats = visual.diff_stats(before.crop(crop), after.crop(crop))
            assert stats["over_total"] == 0, (engine, box, stats)


@pytest.mark.parametrize("fid", ("B01", "B04"))
def test_cell_overflow_rejected(fid):
    """G6-03：新文字超出格內緣回 TEXT_OVERFLOW，不縮字、不換行。"""
    row = _row(fid)
    document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
    try:
        target = _target_cell(analyzer.inspect_page(document, 0), row)
        plan = cell.plan_cell_edit(document, {"cell_id": target["cell_id"],
                                              "new_text": "1234567890" * 6})  # fmt: skip
        assert not plan["ready"] and plan["unsupported_reasons"] == ["TEXT_OVERFLOW"]
    finally:
        document.close()


def test_manual_cell_requires_assessment(tmp_path):
    """G6-04：B06 合併格（偵測或人工框選）都拒絕；人工框選跨格、有線穿過、切到文字也拒絕；
    無框線表格以人工框選可改，仍經能力判定與溢出檢查。"""
    row = _row("B06")
    document = analyzer.open_document(str(visual.FILES / "B06.pdf"))
    try:
        page = analyzer.inspect_page(document, 0)
        merged = _target_cell(page, row)
        assert (merged["row_span"], merged["col_span"]) == (1, 2)
        assert merged["capability"] == {"status": row["expected"], "reasons": [row["reason_code"]]}
        plan = cell.plan_cell_edit(document, {"cell_id": merged["cell_id"], "new_text": "X"})
        assert not plan["ready"] and plan["unsupported_reasons"] == ["UNSUPPORTED_LAYOUT"]
        manual = cell.assess_cell_box(document, {"cell_box": merged["inner_bbox"], "page_index": 0})
        assert manual["capability"]["status"] == "reject"
        others = [c for c in page["cell_targets"] if c["col_span"] == 1]
        a, b = others[0]["inner_bbox"], others[1]["inner_bbox"]  # 第 1 列相鄰兩格
        both = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
        assert cell.assess_cell_box(document, {"cell_box": both, "page_index": 0})[
            "capability"]["status"] == "reject"  # fmt: skip
    finally:
        document.close()

    path = tmp_path / "borderless.pdf"
    table_pdf(path, [["Item", "Qty"], ["Pen", "12"]], vertical=False)
    document = analyzer.open_document(str(path))
    try:
        assert analyzer.inspect_page(document, 0)["cell_targets"] == []
        box = cell_box(1, 1)
        partial = [box[0], box[1], box[0] + 12, box[3]]  # 只框到「12」的一部分
        assert cell.assess_cell_box(document, {"cell_box": partial, "page_index": 0})[
            "capability"]["status"] == "reject"  # fmt: skip
        tall = [box[0], box[1] - 30, box[2], box[3]]  # 中間有水平線穿過
        assert cell.assess_cell_box(document, {"cell_box": tall, "page_index": 0})[
            "capability"]["status"] == "reject"  # fmt: skip
        inner = [box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1]
        assessed = cell.assess_cell_box(document, {"cell_box": inner, "page_index": 0})
        assert assessed["capability"]["status"] == "support"
        assert [line["text"] for line in assessed["lines"]] == ["12"]
        too_long = cell.plan_cell_edit(document, {"cell_box": inner, "page_index": 0,
                                                  "new_text": "123456789012345"})  # fmt: skip
        assert too_long["unsupported_reasons"] == ["TEXT_OVERFLOW"]
        plan = cell.plan_cell_edit(document, {"cell_box": inner, "page_index": 0,
                                              "new_text": "21"})  # fmt: skip
        assert plan["ready"] and plan["target"]["cell"]["manual"]
        edit.apply_edit(document, plan["plan_id"], 0)
        dest = tmp_path / "out.pdf"
        report = export.export_document(document, str(dest))["validation_report"]
        assert report["ok"], report["failures"]
    finally:
        document.close()
    assert "21" in _texts_in(dest.read_bytes(), inner)["mupdf"]


@pytest.mark.parametrize("fid,line", [("B02", 1), ("B05", 1)])
def test_multiline_cell_line_layout(fid, line, tmp_path):
    """G6-05：多行格一次只改指定的一行；可改動區域不含同格其他行；
    行號超出範圍回 INVALID_REQUEST。"""
    original, output, plan, target, report = _edit(fid, tmp_path)
    assert report["ok"] and plan["target"]["cell"]["line_index"] == line
    other = target["lines"][1 - line]
    mask = plan["allowed_change_mask"]
    assert mask[1] >= other["bbox"][3] or mask[3] <= other["bbox"][1]  # 遮罩與另一行不重疊
    assert _texts_in(original, other["bbox"]) == _texts_in(output, other["bbox"])
    document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
    try:
        cell_id = _target_cell(analyzer.inspect_page(document, 0), _row(fid))["cell_id"]
        with pytest.raises(ProtocolError) as info:
            cell.plan_cell_edit(document, {"cell_id": cell_id, "line_index": 2, "new_text": "X"})
        assert info.value.code == "INVALID_REQUEST"
    finally:
        document.close()


def test_empty_cell_rejected(tmp_path):
    """G6-05：空白格只能檢視，不新增文字（ADR-0023 §2）。"""
    path = tmp_path / "empty.pdf"
    table_pdf(path, [["Item", "Qty"], ["Pen", None]])
    document = analyzer.open_document(str(path))
    try:
        cells = analyzer.inspect_page(document, 0)["cell_targets"]
        assert len(cells) == 4
        empty = next(c for c in cells if (c["row"], c["col"]) == (1, 1))
        assert empty["empty"] and empty["capability"]["reasons"] == ["UNSUPPORTED_LAYOUT"]
        plan = cell.plan_cell_edit(document, {"cell_id": empty["cell_id"], "new_text": "5"})
        assert not plan["ready"] and "空白格：只修改既有文字，不新增內容" in plan["warnings"]
        filled = next(c for c in cells if (c["row"], c["col"]) == (1, 0))
        assert filled["capability"]["status"] == "support"
    finally:
        document.close()


def test_rules_check_detects_changed_borders(tmp_path):
    """另存前驗證：改格的頁面格線若有變動（模擬拿掉一條線、改線寬）即判為失敗。"""
    original, output, plan, target, report = _edit("B04", tmp_path)
    document = analyzer.open_document(str(visual.FILES / "B04.pdf"))
    try:
        document.applied = [{"page_index": 0, "mask": plan["allowed_change_mask"],
                             "new_text": "", "kind": "cell"}]  # fmt: skip
        assert export.rules_check(document, output) == []
        for old, new in ((rb"0\.5\s+w", b"0.75 w"), (rb"l\s+S", b"l n")):
            with pikepdf.open(io.BytesIO(output)) as pdf:
                contents = pdf.pages[0].obj.Contents
                streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
                for stream in streams:
                    stream.write(re.sub(old, new, stream.read_bytes(), count=1))
                buf = io.BytesIO()
                pdf.save(buf)
            assert export.rules_check(document, buf.getvalue()) == [0], old
    finally:
        document.close()


def test_text_crossing_border_rejected(tmp_path):
    """G6-04：文字跨過格線時，兩邊的格都拒絕（不知道該屬哪一格，改了會動到鄰格）。"""
    path = tmp_path / "crossing.pdf"
    table_pdf(path, [["Item", "Qty"], ["A very long product name", "12"]])
    document = analyzer.open_document(str(path))
    try:
        cells = {
            (c["row"], c["col"]): c for c in analyzer.inspect_page(document, 0)["cell_targets"]
        }
        assert cells[(1, 0)]["capability"]["reasons"] == ["UNSUPPORTED_LAYOUT"]
        assert cells[(1, 1)]["capability"]["reasons"] == ["UNSUPPORTED_LAYOUT"]
        assert cells[(0, 0)]["capability"]["status"] == "support"
    finally:
        document.close()


def test_text_api_respects_cell_judgement(tmp_path):
    """U2：plan_text_edit 改到不支援格內（或跨格）的文字時也拒絕；支援格內的文字照常可改。"""
    row = _row("B06")
    document = analyzer.open_document(str(visual.FILES / "B06.pdf"))
    try:
        target = span.find(document, 0, row["original_text"])
        plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": "合併欄"})
        assert not plan["ready"] and plan["unsupported_reasons"] == ["UNSUPPORTED_LAYOUT"]
        other = span.find(document, 0, "備考")
        assert edit.plan_text_edit(document, {"target_id": other.span_id, "new_text": "備註"})[
            "unsupported_reasons"] != ["UNSUPPORTED_LAYOUT"]  # fmt: skip
    finally:
        document.close()
    path = tmp_path / "crossing.pdf"
    table_pdf(path, [["Item", "Qty"], ["A very long product name", "12"]])
    document = analyzer.open_document(str(path))
    try:
        crossing = span.find(document, 0, "product")
        plan = edit.plan_text_edit(document, {"target_id": crossing.span_id, "new_text": "produce"})
        assert plan["unsupported_reasons"] == ["UNSUPPORTED_LAYOUT"]
        item = span.find(document, 0, "Item")
        assert edit.plan_text_edit(document, {"target_id": item.span_id, "new_text": "Iten"})[
            "ready"
        ]
    finally:
        document.close()


FRAME = "0 G 1 w 30 60 340 180 re S"  # 外框：PDF 空間 x 30–370、y 60–240（頁面空間 y 60–240）
INNER_LAYOUTS = {
    # 外框內右側一排空白數字格（不碰外框）：身分證字號格
    "id_boxes": ["200 170 m 350 170 l S", "200 200 m 350 200 l S"]
    + [f"{x} 170 m {x} 200 l S" for x in (200, 230, 260, 290, 320, 350)],
    # 外框內右側另一個 2×2 表格
    "nested_table": ["200 120 m 350 120 l S", "200 160 m 350 160 l S", "200 200 m 350 200 l S",
                     "200 120 m 200 200 l S", "275 120 m 275 200 l S", "350 120 m 350 200 l S"],
}  # fmt: skip


@pytest.mark.parametrize("layout", sorted(INNER_LAYOUTS))
def test_frame_with_inner_lines_clips_region(layout, tmp_path):
    """Q1：外框格內還有其他格線時，可改動區域裁到不碰那些線；新文字不能畫進內層格。"""
    path = tmp_path / f"{layout}.pdf"
    ops_pdf(path, [FRAME, *INNER_LAYOUTS[layout], text(40, 180, "ID No.")])
    document = analyzer.open_document(str(path))
    try:
        page = analyzer.inspect_page(document, 0)
        frame = next(c for c in page["cell_targets"] if c["bbox"][0] == 30)
        assert [line["text"] for line in frame["lines"]] == ["ID No."]
        long_text = "ID No. (national identification card number)"  # 會越過 x=200 的內層格線
        plan = cell.plan_cell_edit(document, {"cell_id": frame["cell_id"], "new_text": long_text})
        assert plan["unsupported_reasons"] == ["TEXT_OVERFLOW"]
        plan = cell.plan_cell_edit(document, {"cell_id": frame["cell_id"], "new_text": "ID No. 2"})
        assert plan["ready"] and plan["allowed_change_mask"][2] <= 200 - 0.5
        edit.apply_edit(document, plan["plan_id"], 0)
        report = export.export_document(document, str(tmp_path / "out.pdf"))["validation_report"]
        assert report["ok"], report["failures"]
    finally:
        document.close()


def test_manual_box_sees_form_lines(tmp_path):
    """Q2：格線畫在 Form 內、文字在頁面層級：框選跨過 Form 內的線拒絕；
    另存前比對含 Form 內的線。"""
    form = ["0 G 1 w 50 250 m 350 250 l S", "50 220 m 350 220 l S", "50 250 m 50 220 l S",
            "150 250 m 150 220 l S", "350 250 m 350 220 l S"]  # fmt: skip
    path = tmp_path / "form_lines.pdf"
    ops_pdf(path, ["q /Fm0 Do Q", text(56, 230, "Pen"), text(156, 230, "12")], form)
    document = analyzer.open_document(str(path))
    try:
        assert analyzer.inspect_page(document, 0)["cell_targets"] == []  # Form 內的線不偵測格
        across = [52, 52, 348, 78]
        assert cell.assess_cell_box(document, {"cell_box": across, "page_index": 0})[
            "capability"]["reasons"] == ["UNSUPPORTED_LAYOUT"]  # fmt: skip
        left = [52, 52, 148, 78]
        assert cell.assess_cell_box(document, {"cell_box": left, "page_index": 0})[
            "capability"]["status"] == "support"  # fmt: skip
        plan = cell.plan_cell_edit(document, {"cell_box": left, "page_index": 0, "new_text": "Ink"})
        assert plan["ready"]
        edit.apply_edit(document, plan["plan_id"], 0)
        dest = tmp_path / "out.pdf"
        assert export.export_document(document, str(dest))["validation_report"]["ok"]
        with pikepdf.open(dest) as pdf:
            form_stream = pdf.pages[0].Resources.XObject.Fm0
            form_stream.write(form_stream.read_bytes().replace(b"1 w", b"2 w", 1))
            buf = io.BytesIO()
            pdf.save(buf)
        assert export.rules_check(document, buf.getvalue()) == [0]
    finally:
        document.close()


def test_frame_keeps_previous_text_edits(tmp_path):
    """Q3：頁框內有一段旋轉文字時只擋那一行，其他文字（main 上可改）仍可改；
    同一行間距大的兩段文字分成兩個片段，各自可改。"""
    path = tmp_path / "frame.pdf"
    ops_pdf(path, ["0 G 1 w 20 20 360 260 re S", text(40, 250, "Title"), text(40, 200, "Body"),
                   text(0, 0, "Side", "0 1 -1 0 360 100"), text(40, 150, "Left"),
                   text(300, 150, "Right")])  # fmt: skip
    document = analyzer.open_document(str(path))
    try:
        frame = analyzer.inspect_page(document, 0)["cell_targets"][0]
        assert frame["capability"]["status"] == "support"
        by_text = {line["text"]: i for i, line in enumerate(frame["lines"])}
        assert {"Title", "Body", "Side", "Left", "Right"} <= set(by_text)
        assert frame["lines"][by_text["Side"]]["capability"]["status"] == "reject"
        title = span.find(document, 0, "Title")
        assert edit.plan_text_edit(document, {"target_id": title.span_id, "new_text": "Tytle"})[
            "ready"
        ]

        def plan(name, new):
            params = {"cell_id": frame["cell_id"], "line_index": by_text[name], "new_text": new}
            return cell.plan_cell_edit(document, params)

        for name, new in (("Title", "Tytle"), ("Right", "Rigid")):
            assert plan(name, new)["ready"], name
        left_box = frame["lines"][by_text["Left"]]["bbox"]
        assert plan("Right", "Rigid")["allowed_change_mask"][0] > left_box[2]  # 不含同列左邊的片段
        assert not plan("Side", "Sides")["ready"]
    finally:
        document.close()


def test_text_api_region_cannot_cross_borders():
    """Q4：plan_text_edit 由呼叫端給的可改動區域有格線穿過時拒絕；
    manifest 的格範圍（線在邊上）照常。"""
    row = _row("B01")
    document = analyzer.open_document(str(visual.FILES / "B01.pdf"))
    try:
        target = span.find(document, 0, row["original_text"])
        whole = [72.0, 100.0, 522.0, 190.0]
        plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": "21",
                                              "editable_region": whole})  # fmt: skip
        assert plan["unsupported_reasons"] == ["UNSUPPORTED_LAYOUT"]
        region = _floats(row["editable_region_pt"])
        assert edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": "21",
                                              "editable_region": region})["ready"]  # fmt: skip
    finally:
        document.close()


ROUND2 = {
    # 第二輪核對 R1：非描邊、非 re 的畫法
    "fill_polygon": ["119.5 160 m 120.5 160 l 120.5 245 l 119.5 245 l h f"],
    # 兩端點在下方、往上凸穿過文字列的曲線：只看端點會是一條在文字下方的水平線
    "curve": ["0.5 w 100 152 m 100 280 340 280 340 152 c S"],
    "dotted_segments": [f"0.5 w 120 {y} m 120 {y + 0.8} l S" for y in range(160, 245, 2)],
    "thick_fill": ["116 160 8 85 re f"],
    # 第二輪核對 R2：斜線表頭
    "diagonal": ["0.5 w 50 250 m 350 150 l S"],
}  # fmt: skip


@pytest.mark.parametrize("kind", sorted(ROUND2))
def test_lines_drawn_any_way_block_region(kind, tmp_path):
    """第二輪 R1、R2：以填色多邊形、曲線、點線、粗填色畫的內層線也擋住新文字；斜線使該行拒絕。"""
    path = tmp_path / f"{kind}.pdf"
    ops_pdf(path, ["0 G 1 w 50 150 300 100 re S", *ROUND2[kind], text(56, 230, "AB")])
    document = analyzer.open_document(str(path))
    try:
        frame = analyzer.inspect_page(document, 0)["cell_targets"][0]
        plan = cell.plan_cell_edit(document, {"cell_id": frame["cell_id"],
                                              "new_text": "ABCDEFGHIJKLMNOPQ"})  # fmt: skip
        # 斜線與曲線（第三輪核對 S1 起曲線細分成折線，穿過該行的區域即為斜邊）使該行拒絕
        expected = "UNSUPPORTED_LAYOUT" if kind in ("diagonal", "curve") else "TEXT_OVERFLOW"
        assert plan["unsupported_reasons"] == [expected], plan["unsupported_reasons"]
        box = [52, 52, 348, 98]  # 人工框選整個外框內緣：框內有內層線或斜線即拒絕
        assert cell.assess_cell_box(document, {"cell_box": box, "page_index": 0})[
            "capability"]["reasons"] == ["UNSUPPORTED_LAYOUT"]  # fmt: skip
    finally:
        document.close()


ROUND2_FREE = {
    # 第二輪核對 R3：不應擋的線（相對 8e1b844 不得回歸）
    "underline_fill": ["56 226 14 0.6 re f"],
    "underline_stroke": ["0.5 w 56 226.5 m 70 226.5 l S"],
    "strike": ["0.5 w 56 234 m 70 234 l S"],
    "line_right_same_height": ["0.5 w 200 234 m 340 234 l S"],
    "box_below": ["0.5 w 60 160 40 40 re S"],
    # 第三輪核對 S5：延伸到右邊的底線、文字後面同高的填空線（在上面填字）
    "underline_to_right": ["0 G 0.5 w 56 227 m 300 227 l S"],
    "fill_in_blank": ["0 G 0.5 w 76 227 m 250 227 l S"],
}  # fmt: skip


@pytest.mark.parametrize("kind", sorted(ROUND2_FREE))
def test_underline_and_nearby_lines_do_not_block(kind, tmp_path):
    """第二輪 R3：底線、刪除線、文字右側同高的線、文字下方的小框不擋改字；另存通過。"""
    path = tmp_path / f"{kind}.pdf"
    ops_pdf(path, ["0 G 1 w 50 150 300 100 re S", *ROUND2_FREE[kind], text(56, 230, "AB")])
    document = analyzer.open_document(str(path))
    try:
        frame = analyzer.inspect_page(document, 0)["cell_targets"][0]
        # 整段替換（改字起點在文字開頭），左右邊界都會被檢查到
        plan = cell.plan_cell_edit(document, {"cell_id": frame["cell_id"], "new_text": "ZZZZ"})
        assert plan["ready"], plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        report = export.export_document(document, str(tmp_path / "out.pdf"))["validation_report"]
        assert report["ok"], report["failures"]
    finally:
        document.close()


ROUND3 = {
    # 第三輪核對 S1：曲線本身穿過文字列，控制點折線卻在格外
    "curve_outside_polyline": dict(ops=["0.5 w 200 245 m 400 245 400 60 200 60 c S"]),
    # S2：不是路徑的畫法
    "shading_bar": dict(ops=["q 199 150 2 100 re W n /Sh0 sh Q"], shading=True),
    "annotation_line": dict(ops=[],
                            annots=[([195, 150, 205, 250], "0 G 2 w 200 150 m 200 250 l S")]),
    "type3_bar": dict(ops=[text(200, 160, "|").replace("/F1", "/F3")], type3=True),
    "inline_image": dict(ops=["q 2 0 0 100 199 150 cm BI /W 1 /H 1 /CS /G /BPC 8 ID \x00 EI Q"]),
    # S3：線帽與粗斜線
    "square_cap": dict(ops=["0 G 20 w 2 J 200 160 m 200 222 l S"]),
    "thick_diagonal_outside": dict(ops=["0 G 100 w 385 250 m 395 150 l S"]),
}  # fmt: skip


DIAGONAL_KINDS = {"curve_outside_polyline", "thick_diagonal_outside"}


@pytest.mark.parametrize("kind", sorted(ROUND3))
def test_any_drawing_blocks_long_text(kind, tmp_path):
    """第三輪 S1–S3：曲線、shading、註解、Type3、影像、線帽、粗斜線畫出的東西都擋住新文字
    （墨跡檢查）。"""
    case = ROUND3[kind]
    path = tmp_path / f"{kind}.pdf"
    rich_pdf(path, ["0 G 1 w 50 150 300 100 re S", *case["ops"], text(56, 230, "AB")],
             shading=case.get("shading", False), annots=case.get("annots"),
             type3=case.get("type3", False))  # fmt: skip
    document = analyzer.open_document(str(path))
    try:
        frame = next(c for c in analyzer.inspect_page(document, 0)["cell_targets"]
                     if any(line["text"] == "AB" for line in c["lines"]))  # fmt: skip
        index = next(i for i, line in enumerate(frame["lines"]) if line["text"] == "AB")
        long_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGH"
        plan = cell.plan_cell_edit(document, {"cell_id": frame["cell_id"], "line_index": index,
                                              "new_text": long_text})  # fmt: skip
        assert not plan["ready"], plan["allowed_change_mask"]
        short = cell.plan_cell_edit(document, {"cell_id": frame["cell_id"], "line_index": index,
                                               "new_text": "ABC"})  # fmt: skip
        if kind in DIAGONAL_KINDS:  # 曲線、粗斜線穿過這一行的區域：整行拒絕（ADR-0023 §2）
            assert short["unsupported_reasons"] == ["UNSUPPORTED_LAYOUT"]
        else:  # 不碰到畫出的東西就照常可改
            assert short["ready"], short["unsupported_reasons"]
    finally:
        document.close()


@pytest.mark.parametrize("ops", [["56 232 16 7 re f"], ["54 225 22 16 re f"]],
                         ids=["thick_strike", "highlight"])  # fmt: skip
def test_fill_over_text_does_not_cut_into_text(ops, tmp_path):
    """第三輪 S4：7 pt 粗刪除線、文字底色塊不把可改動區域裁進文字裡；在它們範圍內的改字照常可改。"""
    path = tmp_path / "fill.pdf"
    ops_pdf(path, ["0 G 1 w 50 150 300 100 re S", "0.6 g", *ops, "0 g", text(56, 230, "AB")])
    document = analyzer.open_document(str(path))
    try:
        frame = analyzer.inspect_page(document, 0)["cell_targets"][0]
        plan = cell.plan_cell_edit(document, {"cell_id": frame["cell_id"], "new_text": "ZZ"})
        assert plan["ready"], plan["unsupported_reasons"]
        mask, text_box = plan["allowed_change_mask"], frame["lines"][0]["bbox"]
        assert mask[0] <= text_box[0] and mask[1] <= text_box[1] and mask[3] >= text_box[3]
        edit.apply_edit(document, plan["plan_id"], 0)
        report = export.export_document(document, str(tmp_path / "out.pdf"))["validation_report"]
        assert report["ok"], report["failures"]
    finally:
        document.close()
