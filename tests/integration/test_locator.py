"""G1-08：字形對應到可修改的 content stream 運算子；擷取 bbox 不算定位。

對照方式獨立於 worker：用 pikepdf 直接取出目標回報的 stream 與運算子，確認它確實是文字顯示運算子，
且其字串位元組數等於回報的字碼數；再以 PyMuPDF search_for 的框比對定位結果（≤0.5 pt）。
"""

from pathlib import Path

import pikepdf
import pytest

from peditor.core.locate import find_text, span_bbox, span_capability

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _string_bytes(operands, operator):
    items = operands[0] if operator == "TJ" else operands[-1:]
    return b"".join(bytes(i) for i in items if isinstance(i, pikepdf.String))


@pytest.mark.parametrize("fid", ["T01", "F04", "L03"])
def test_glyph_maps_to_content_stream_operator(service, available_rows, fid):
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
        for ti in dict.fromkeys(ti for ti, _ in span):
            target = targets[ti]
            stream = pdf.get_object(tuple(target["stream"]))
            instruction = pikepdf.parse_content_stream(stream)[target["op_index"]]
            operator = str(instruction.operator)
            assert operator == target["operator"] and operator in {"Tj", "TJ", "'", '"'}
            data = _string_bytes(instruction.operands, operator)
            two_byte = target["font"]["two_byte"]
            assert len(data) == target["code_count"] * (2 if two_byte else 1)
    service.close_document(doc)
