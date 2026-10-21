"""G1-02、G1-03：repo 內全部 available fixture 經 worker 分析或受控拒絕，能力判定符合 manifest。

盲測 11 份（P8 由保管人執行）、U06（ADR-0012）、S03–S06（P7 產生）不在 repo，於 P1 報告標 NOT RUN。
"""

from pathlib import Path

import pikepdf
import pytest

from peditor.core.locate import find_text, span_bbox, span_capability
from peditor.core.service import ServiceError

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"

# 能力判定不在 P1 範圍的預期，逐項說明；P1 只驗證目標可定位且未崩潰（P1 報告 §3、§9）
DEFERRED = {
    "F03": "GLYPH_MISSING 取決於新文字，於 plan_text_edit 判定（P2，G2-04）",
    "F08": "GLYPH_MISSING 取決於新文字，於 plan_text_edit 判定（P2，G2-04）",
    "B06": "合併儲存格偵測屬 P6（P1 S2 工程師決定 2026-10-21）",
}
DOCUMENT_REASONS = {
    "ENCRYPTED_DOCUMENT",
    "MALFORMED_DOCUMENT",
    "SIGNED_DOCUMENT",
    "UNSUPPORTED_FEATURE",
    "ACTIVE_CONTENT",
}


def _analyze(service, fid):
    opened = service.open_document(FILES / f"{fid}.pdf")
    doc = opened["document_id"]
    assessment = service.assess_editability(doc)
    pages = {}
    for summary in assessment["pages"]:
        pages[summary["page_index"]] = service.inspect_page(doc, summary["page_index"])
    service.close_document(doc)
    return opened, assessment, pages


def test_all_fixtures_analyzed_or_rejected(service, available_rows):
    analyzed = 0
    for row in available_rows:
        try:
            opened, assessment, pages = _analyze(service, row["fixture_id"])
        except ServiceError as exc:  # 受控拒絕：必須是理由碼，不能是 worker 崩潰
            pytest.fail(f"{row['fixture_id']}: {exc.code}")
        status = assessment["document"]["status"]
        assert status in {"support", "reject"}, row["fixture_id"]
        if status == "support":
            assert len(pages) == opened["page_count"], row["fixture_id"]
        analyzed += 1
    assert analyzed == len(available_rows) == 45


def test_capability_matches_manifest(service, available_rows):
    checked = []
    for row in available_rows:
        fid, expected, reason = row["fixture_id"], row["expected"], row["reason_code"]
        opened, assessment, pages = _analyze(service, fid)
        document = assessment["document"]
        if reason in DOCUMENT_REASONS:
            assert document == {"status": "reject", "reasons": [reason]}, fid
            checked.append(fid)
            continue
        assert document["status"] == "support", fid
        page = pages[int(row["page_index"])]
        if reason == "NO_TEXT_LAYER":
            assert page["capabilities"] == {"status": expected, "reasons": [reason]}, fid
            checked.append(fid)
            continue

        target = row["target"]
        if target.startswith("image#"):
            image = page["image_targets"][int(target.removeprefix("image#"))]
            assert image["capability"]["status"] == expected, fid
            assert image["capability"]["reasons"] == ([reason] if reason else []), fid
            bbox = [float(v) for v in row["bbox_pt"].split(",")]
            assert all(
                abs(a - b) <= 0.5 for a, b in zip(image["visible_bbox"], bbox, strict=True)
            ), fid
            checked.append(fid)
            continue

        targets = page["text_targets"]
        spans = find_text(targets, row["original_text"])
        if reason == "UNSUPPORTED_ENCODING":
            # 原文無法可靠擷取：找不到，或找到但不可編輯；且頁上有字型被判 UNSUPPORTED_ENCODING
            assert all(span_capability(targets, s)["status"] == "reject" for s in spans), fid
            assert any("UNSUPPORTED_ENCODING" in t["capability"]["reasons"] for t in targets), fid
            checked.append(fid)
            continue
        assert len(spans) == 1, fid
        capability = span_capability(targets, spans[0])
        if fid in DEFERRED:
            assert capability["status"] == "support", fid  # 文字層可定位；拒絕判定延後
            continue
        assert capability["status"] == expected, (fid, capability)
        assert capability["reasons"] == ([reason] if reason else []), (fid, capability)
        if expected == "support":
            bbox = [float(v) for v in row["bbox_pt"].split(",")]
            got = span_bbox(targets, spans[0])
            assert all(abs(a - b) <= 0.5 for a, b in zip(got, bbox, strict=True)), (fid, got)
        checked.append(fid)
    assert len(checked) + len(DEFERRED) == len(available_rows)


def test_xfa_rejected(service, tmp_path):
    """ADR-0012：XFA 無實際樣本，以腳本合成檔驗證拒絕路徑（非盲測、不計入 manifest）。"""
    path = tmp_path / "xfa.pdf"
    with pikepdf.open(FILES / "T07.pdf") as pdf:
        xfa = pdf.make_stream(b"<xdp:xdp xmlns:xdp='http://ns.adobe.com/xdp/'></xdp:xdp>")
        pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array(), XFA=xfa)
        pdf.save(path)
    opened = service.open_document(path)
    assert opened["document_flags"]["xfa"] is True
    assert opened["document_flags"]["reasons"] == ["UNSUPPORTED_FEATURE"]
    service.close_document(opened["document_id"])
