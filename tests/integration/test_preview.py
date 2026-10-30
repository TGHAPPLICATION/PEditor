"""P4 預覽（ADR-0021）：PREVIEW_UNRELIABLE 偵測範圍、worker 端 preview_edit 不提交。"""

import base64
import hashlib
import io

import pikepdf
import pytest
import visual

from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, edit, span

SKIP = {"ENCRYPTED_DOCUMENT", "MALFORMED_DOCUMENT"}


def _fingerprint(document) -> str:
    buf = io.BytesIO()
    document.pike.save(buf, static_id=True, compress_streams=True,
                       object_stream_mode=pikepdf.ObjectStreamMode.preserve)  # fmt: skip
    return hashlib.sha256(buf.getvalue()).hexdigest()


def _plan(document, old, new):
    params = {"target_id": span.find(document, 0, old).span_id, "new_text": new,
              "policy": "prefer_a"}  # fmt: skip
    plan = edit.plan_text_edit(document, params)
    assert plan["ready"], plan["unsupported_reasons"]
    return plan["plan_id"]


def test_preview_unreliable_exactly_mupdf_blank():
    """ADR-0021 §1：repo 內 fixture 中，任一頁帶 PREVIEW_UNRELIABLE 的恰為 ADR-0015 的 7 份。"""
    flagged = set()
    for fid, row in visual.manifest().items():
        if row["status"] != "available" or row["reason_code"] in SKIP:
            continue
        document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
        try:
            for index in range(document.page_count):
                page = analyzer.inspect_page(document, index)
                assert set(page["notices"]) <= {"PREVIEW_UNRELIABLE"}, fid
                if page["notices"]:
                    flagged.add(fid)
        finally:
            document.close()
    assert flagged == visual.MUPDF_BLANK


def test_preview_edit_does_not_commit():
    """preview_edit：前後圖不同；revision、內容、已套用清單不變；同一計畫之後仍可套用。"""
    document = analyzer.open_document(str(visual.FILES / "F04.pdf"))
    try:
        plan_id = _plan(document, "World", "Earth")
        before_print, revision = _fingerprint(document), document.revision
        result = edit.preview_edit(document, plan_id)
        assert result["page_index"] == 0 and result["mode"] == "A"
        before, after = (base64.b64decode(result[k]["png_base64"]) for k in ("before", "after"))
        assert before != after
        x0, y0, x1, y1 = result["box"]
        width, height = result["after"]["width"], result["after"]["height"]
        assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
        assert document.revision == revision and document.applied == []
        assert _fingerprint(document) == before_print
        assert "Hello World" in document.mu[0].get_text()

        edit.apply_edit(document, plan_id, revision)  # 預覽後沿用原 plan_id
        assert document.revision == revision + 1 and "Hello Earth" in document.mu[0].get_text()
    finally:
        document.close()


def test_preview_edit_invalidates_other_plans_and_rejects_bad_ids():
    document = analyzer.open_document(str(visual.FILES / "F04.pdf"))
    try:
        first = _plan(document, "World", "Earth")
        second = _plan(document, "Hello", "Howdy")
        edit.preview_edit(document, first)
        with pytest.raises(ProtocolError):  # ADR-0021 後果：同文件其他未套用計畫失效
            edit.apply_edit(document, second, document.revision)
        for bad in ("0" * 16, None, 123):
            with pytest.raises(ProtocolError) as exc:
                edit.preview_edit(document, bad)
            assert exc.value.code == "INVALID_REQUEST"
    finally:
        document.close()
