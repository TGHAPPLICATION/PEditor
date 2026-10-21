"""G1-08：字形對應到可修改的 content stream 運算子；擷取 bbox 不算定位。

獨立對照：用 pikepdf 取出目標回報的 stream／運算子，確認是文字顯示運算子；再把這些運算子的字串清空後
另存，以 PyMuPDF 重新擷取——原文必須消失、頁上其他文字必須保留，證明正是這些運算子繪出目標字形。
（定位框來自 PyMuPDF 擷取字元，與 manifest bbox 同源，只作一致性檢查，不算獨立證據。）
"""

from pathlib import Path

import pikepdf
import pymupdf
import pytest

from peditor.core.locate import find_text, span_bbox, span_capability

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _blank(operands, operator):
    if operator == "TJ":
        return [pikepdf.Array([])]
    return [*operands[:-1], pikepdf.String(b"")]


@pytest.mark.parametrize("fid", ["T01", "F04", "L03"])
def test_glyph_maps_to_content_stream_operator(service, available_rows, fid, tmp_path):
    row = next(r for r in available_rows if r["fixture_id"] == fid)
    doc = service.open_document(FILES / f"{fid}.pdf")["document_id"]
    page = service.inspect_page(doc, int(row["page_index"]))
    targets = page["text_targets"]

    spans = find_text(targets, row["original_text"])
    assert len(spans) == 1, fid
    span = spans[0]
    assert span_capability(targets, span)["status"] == "support"

    # 定位框與 manifest（PyMuPDF search_for）一致
    expected = [float(v) for v in row["bbox_pt"].split(",")]
    got = span_bbox(targets, span)
    assert all(abs(a - b) <= 0.5 for a, b in zip(got, expected, strict=True)), (got, expected)

    with pikepdf.open(FILES / f"{fid}.pdf") as pdf:
        by_stream = {}
        for ti in dict.fromkeys(ti for ti, _ in span):
            target = targets[ti]
            by_stream.setdefault(tuple(target["stream"]), []).append(target)
        for objgen, group in by_stream.items():
            stream = pdf.get_object(objgen)
            instructions = list(pikepdf.parse_content_stream(stream))
            for target in group:
                inst = instructions[target["op_index"]]
                operator = str(inst.operator)
                assert operator == target["operator"] and operator in {"Tj", "TJ", "'", '"'}
                instructions[target["op_index"]] = pikepdf.ContentStreamInstruction(
                    _blank(list(inst.operands), operator), inst.operator
                )
            stream.write(pikepdf.unparse_content_stream(instructions))
        blanked = tmp_path / "blanked.pdf"
        pdf.save(blanked)
    service.close_document(doc)

    with pymupdf.open(blanked) as edited, pymupdf.open(FILES / f"{fid}.pdf") as original:
        before = "".join(original[0].get_text().split())
        after = "".join(edited[0].get_text().split())
    target_text = "".join(row["original_text"].split())
    assert target_text in before and target_text not in after
    # 只移除了這些運算子繪出的文字：擷取結果恰為原文去掉被清空運算子的文字，其餘不變
    expected = before
    for ti in dict.fromkeys(ti for ti, _ in span):
        expected = expected.replace("".join(targets[ti]["text"].split()), "", 1)
    assert after == expected, fid
