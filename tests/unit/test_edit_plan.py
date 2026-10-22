"""EditPlan 結構、target_id 組成與 span target 解析（G2-13、G2-14、G2-18；ADR-0018 §1）。"""

from dataclasses import fields
from pathlib import Path

import pytest

from peditor.core.editplan import (
    EditPlan,
    SpanTarget,
    common_affixes,
    parse_target_id,
    validate_plan_params,
)
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, span

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
SPEC_PLAN_FIELDS = {"mode", "preconditions", "target", "resource_changes", "allowed_change_mask",
                    "new_text", "font_policy", "geometry", "unsupported_reasons"}  # fmt: skip


@pytest.fixture
def open_fixture():
    opened = []

    def _open(fixture_id):
        document = analyzer.open_document(str(FILES / f"{fixture_id}.pdf"))
        opened.append(document)
        return document

    yield _open
    for document in opened:
        document.close()


def _code(fn, *args):
    with pytest.raises(ProtocolError) as exc:
        fn(*args)
    return exc.value.code


def test_edit_plan_schema():
    names = {f.name for f in fields(EditPlan)}
    assert SPEC_PLAN_FIELDS <= names  # spec §7
    assert {"font_changes", "warnings"} <= names  # ADR-0018 §4
    good = {"target_id": "span:x", "new_text": "測試局", "policy": "a_only",
            "editable_region": [1, 2, 3, 4]}  # fmt: skip
    assert validate_plan_params(good)["editable_region"] == [1.0, 2.0, 3.0, 4.0]
    assert validate_plan_params({"target_id": "x", "new_text": "a"})["policy"] == "prefer_a"
    # 呼叫端不能送 PDF 指令或任何白名單外的參數
    assert _code(validate_plan_params, {**good, "operators": "BT /F1 12 Tf (x) Tj ET"}) == (
        "INVALID_REQUEST"
    )
    for bad in ({**good, "new_text": ""}, {**good, "new_text": "x" * 201},
                {**good, "new_text": "a\u0000b"}, {**good, "new_text": "a‮b"},
                {**good, "policy": "B"}, {**good, "editable_region": [3, 2, 1, 4]},
                {**good, "editable_region": [0, 0, float("nan"), 1]},
                {**good, "editable_region": [0, 0, True, 1]}, {"new_text": "a"}):  # fmt: skip
        assert _code(validate_plan_params, bad) == "INVALID_REQUEST", bad
    plan = EditPlan("p", "d", {}, {}, "x", "prefer_a", None, "keep", None,
                    unsupported_reasons=["GLYPH_MISSING"])  # fmt: skip
    assert plan.to_dict()["ready"] is False


def test_target_id_components(open_fixture):
    document = open_fixture("T01")
    target = analyzer.inspect_page(document, 0)["text_targets"][0]
    ref = parse_target_id(target["target_id"])
    assert (ref.kind, ref.revision, ref.page_index) == ("t", document.revision, 0)
    assert list(ref.stream) == target["stream"] and ref.op_index == target["op_index"]
    assert len(ref.geometry) == 12  # 幾何 hash（spec §7：不能只是 bbox 或 xref）
    sel = SpanTarget((target["target_id"],), 5, 8)
    assert SpanTarget.parse(sel.span_id) == sel
    for bad in ("", "t:r0:p0", target["target_id"] + "+x", "i" + target["target_id"][1:]):
        with pytest.raises(ProtocolError):
            SpanTarget.parse(f"span:{bad}:c0-1")
    stale = SpanTarget((target["target_id"].replace(":r0:", ":r1:"),), 0, 1)
    assert _code(span.resolve, document, stale) == "REVISION_CONFLICT"


def test_common_affixes():
    assert common_affixes("衛生局", "測試局") == (0, 1)
    assert common_affixes("三樓", "三樓第二會議室") == (2, 0)
    assert common_affixes("aaa", "aa") == (2, 0)


def test_span_target_resolution(open_fixture):
    # T01：一段運算子內的部分文字；只改「衛生」，「局」不動
    document = open_fixture("T01")
    sel = span.resolve(document, span.find(document, 0, "衛生局"))
    assert sel.text == "衛生局" and len(sel.pieces) == 1
    change = span.change(sel, "測試局")
    assert (change.old_text, change.new_text, change.reasons) == ("衛生", "測試", [])
    assert change.pieces[0].g1 - change.pieces[0].g0 == 2

    # T08：選取跨 4 個 BT（LibreOffice），實際改動只有最後一段的「8889」（ADR-0018 §1）
    document = open_fixture("T08")
    target = span.find(document, 0, "（02）2720-8889")
    assert len(target.parts) == 4
    sel = span.resolve(document, target)
    change = span.change(sel, "（02）2720-0000")
    assert (change.old_text, change.new_text) == ("8889", "0000")
    assert len(change.pieces) == 1 and change.pieces[0].target["target_id"] == target.parts[-1]
    assert change.reasons == []
    # 改動跨 BT → UNSUPPORTED_LAYOUT
    assert "UNSUPPORTED_LAYOUT" in span.change(sel, "【03】2720-8889").reasons

    # F04：同一運算子內較短替換，保留「H」
    document = open_fixture("F04")
    change = span.change(span.resolve(document, span.find(document, 0, "Hello")), "Hi")
    assert (change.old_text, change.new_text) == ("ello", "i")

    # T04：純插入，錨定在「三樓」之後
    document = open_fixture("T04")
    change = span.change(span.resolve(document, span.find(document, 0, "三樓")), "三樓第二會議室")
    assert (change.old_text, change.new_text) == ("", "第二會議室")
    assert change.pieces[0].g0 == change.pieces[0].g1

    # 新舊相同、找不到、選取不連續
    sel = span.resolve(document, span.find(document, 0, "三樓"))
    assert _code(span.change, sel, "三樓") == "INVALID_REQUEST"
    assert _code(span.find, document, 0, "不存在的字串") == "INVALID_REQUEST"
    t01 = open_fixture("T01")
    ids = [t["target_id"] for t in analyzer.inspect_page(t01, 0)["text_targets"]]
    assert _code(span.resolve, t01, SpanTarget((ids[0], ids[1]), 0, 1)) == "UNSUPPORTED_LAYOUT"
