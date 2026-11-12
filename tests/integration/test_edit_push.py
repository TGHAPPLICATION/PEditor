"""ADR-0028：同一行後面的字跟著新字移動；可延伸到右邊界，碰到其他內容即拒絕（G8-08、G8-09）。

以測試內產生的 Helvetica 樣本驗證（字寬：A／B／X 667、C／D 722、s 500、o 556，字級 24）。
"""

import pytest
from test_edit_multi import _origins, _sample

from peditor.worker import analyzer, edit, span

TOL = 0.01  # pt
UNIT = 24 / 1000  # 字寬 → pt


def _plan(document, old, new, region=None):
    return edit.plan_text_edit(document, {"target_id": span.find(document, 0, old).span_id,
                                          "new_text": new, "editable_region": region})  # fmt: skip


def _apply(tmp_path, content, old, new, region=None):
    document = analyzer.open_document(str(_sample(tmp_path, content)))
    plan = _plan(document, old, new, region)
    if plan["ready"]:
        edit.apply_edit(document, plan["plan_id"], 0)
    return document, plan


def test_insert_keeps_following_spacing(tmp_path):
    """插字緊接在前一個字之後，原本的字距（TJ 位移）保留在新字之後；後面的字往右推新字寬度。"""
    content = b"BT /F1 24 Tf 72 100 Td [(Hello) -250 (World)] TJ ET"
    document = analyzer.open_document(str(_sample(tmp_path, content)))
    try:
        (w_before,) = _origins(document, "W")
        (o_before,) = _origins(document, "o")
        plan = _plan(document, "Hello", "Hellos")
        assert plan["ready"] and plan["mode"] == "A", plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        (s_after,) = _origins(document, "sW")[:1]
        (w_after,) = _origins(document, "W")
        assert abs(s_after[0] - (o_before[0] + 556 * UNIT)) <= TOL  # 緊接在 o 之後
        assert abs(w_after[0] - (w_before[0] + 500 * UNIT)) <= TOL  # 推了 s 的寬度，字距不變
        assert abs(plan["geometry"]["shift_pt"] - 500 * UNIT) <= TOL
    finally:
        document.close()


def test_insert_into_existing_gap_does_not_overlap(tmp_path):
    """G8-08：舊版刪字留下的空白（TJ 位移）之前補字：新字在前一個字之後，不疊在後面的字上。"""
    content = b"BT /F1 24 Tf 72 100 Td [(AB) -1000 (CD)] TJ ET"
    document = analyzer.open_document(str(_sample(tmp_path, content)))
    try:
        b, c = _origins(document, "BC")
        plan = _plan(document, "ABCD", "ABXCD")
        assert plan["ready"], plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        x, c2 = _origins(document, "XC")
        assert abs(x[0] - (b[0] + 667 * UNIT)) <= TOL
        assert abs(c2[0] - (c[0] + 667 * UNIT)) <= TOL
        assert c2[0] >= x[0] + 667 * UNIT - TOL
    finally:
        document.close()


def test_delete_pulls_following_text_left(tmp_path):
    """較窄時往左收，不留空白。"""
    content = b"BT /F1 24 Tf 72 100 Td (ABCD) Tj ET"
    document, plan = _apply(tmp_path, content, "ABCD", "ACD")
    try:
        assert plan["ready"]
        a, c = _origins(document, "AC")
        assert abs(c[0] - (a[0] + 667 * UNIT)) <= TOL
        assert abs(plan["geometry"]["shift_pt"] + 667 * UNIT) <= TOL
    finally:
        document.close()


@pytest.mark.parametrize(("new", "ok"), [("AB" + "X" * 3, True), ("AB" + "X" * 7, False)])
def test_push_into_other_text_rejected(tmp_path, new, ok):
    """同一行另一個 BT（重新定位、不跟著移動）的文字：推到之前可以，蓋到就 TEXT_OVERFLOW。"""
    content = b"BT /F1 24 Tf 72 100 Td (AB) Tj ET BT /F1 24 Tf 200 100 Td (YZ) Tj ET"
    document, plan = _apply(tmp_path, content, "AB", new)
    try:
        assert plan["ready"] is ok, plan["unsupported_reasons"]
        if not ok:
            assert plan["unsupported_reasons"] == ["TEXT_OVERFLOW"]
    finally:
        document.close()


LINE = b"0 G 1 w 130 80 m 130 130 l S "
GAP = b"BT /F1 24 Tf 72 100 Td [(AB) -2000 (CD)] TJ ET"


@pytest.mark.parametrize(("old", "new", "ok"), [
    ("AB", "AXB", True),  # B 推到 104→120，還在線（x=130）左邊
    ("AB", "AXXB", False),  # B 被推到線上
    ("AB", "AXXXXXB", False),  # B 整個跳過線（移動後不重疊，但越過了）
    ("ABCD", "BCD", True),  # 往左收 16 pt，C 仍在線右邊
    ("ABCD", "CD", False),  # 往左收 32 pt，C 越過線
])  # fmt: skip
def test_moved_glyphs_cannot_cross_vertical_line(tmp_path, old, new, ok):
    """被移動的每個字形（不只行尾）都不得蓋到或越過垂直線；往左收時也檢查。"""
    document, plan = _apply(tmp_path, LINE + GAP, old, new)
    try:
        assert plan["ready"] is ok, plan["unsupported_reasons"]
    finally:
        document.close()


@pytest.mark.parametrize(("region", "ok"), [
    ([70, 80, 145, 110], False),  # 後面的 CD 原本在區域內：不得被推出區域
    ([70, 80, 125, 110], True),  # 區域只框住目標與新字，CD 原本就在框外：依頁面右緣判定
])  # fmt: skip
def test_explicit_region_keeps_inner_text(tmp_path, region, ok):
    """ADR-0028 §3：指定可改動區域時，原本在框內被推的字不得超出框。"""
    document, plan = _apply(tmp_path, b"BT /F1 24 Tf 72 100 Td (ABCD) Tj ET", "AB", "ABX", region)
    try:
        assert plan["ready"] is ok, plan["unsupported_reasons"]
    finally:
        document.close()
