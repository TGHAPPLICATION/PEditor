"""G8-03：完整支援矩陣（spec §8.4：宣告支援 case 通過率 100%、錯誤標成可編輯率 0%）。

經由 DocumentService（worker 子行程）對 manifest 每份 available fixture 跑一次完整判定：
- support：依目標類型（文字、圖片、儲存格）規劃 → ready → 套用 → 交易式另存，另存驗證通過。
- readonly／reject：manifest 的理由碼出現在文件、頁面、目標或計畫的理由中，
  而且沒有任何計畫是 ready。
盲測 11 份與 U06（ADR-0012）不在 repo：本測試確認它們在 manifest 為 pending，結果由保管人以
`scripts/p8_blind_run.py` 在離線實機產生（P8 報告）。
"""

import csv
from pathlib import Path

import pymupdf
import pytest

from peditor.core.service import DocumentService, ServiceError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FILES = FIXTURES / "files"


def _rows() -> list[dict]:
    with open(FIXTURES / "manifest.csv", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


AVAILABLE = [r for r in _rows() if r["status"] == "available"]
PENDING = [r for r in _rows() if r["status"] != "available"]


def _region(text: str) -> list[float] | None:
    return [float(v) for v in text.split(",")] if text else None


def _png(width: int, height: int) -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pix.set_rect(pix.irect, (255, 0, 255))
    return pix.tobytes("png")


def _plan(svc: DocumentService, doc: str, row: dict, page: dict, tmp_path: Path) -> dict:
    """依目標類型規劃 manifest 的編輯；回傳計畫。"""
    target, index = row["target"], int(row["page_index"])
    if target.startswith("image#"):
        image = page["image_targets"][int(target.removeprefix("image#"))]
        x0, y0, x1, y1 = image["visible_bbox"]
        png = tmp_path / f"{row['fixture_id']}.png"
        png.write_bytes(_png(max(1, round((x1 - x0) * 2)), max(1, round((y1 - y0) * 2))))
        asset = svc.register_image(doc, png)["asset_id"]
        return svc.plan_image_edit(doc, image["target_id"], asset)
    if target.startswith("cell("):
        r, c = map(int, target.removeprefix("cell(").removesuffix(")").split(","))
        cell = next(x for x in page["cell_targets"] if (x["row"], x["col"]) == (r, c))
        lines = cell["lines"]
        line = next((i for i, x in enumerate(lines) if row["original_text"] in x["text"]), 0)
        new = lines[line]["text"].replace(row["original_text"], row["new_text"]) if lines else "x"
        return svc.plan_cell_edit(doc, cell["cell_id"], new, line_index=line)
    span = svc.find_text(doc, index, row["original_text"])
    return svc.plan_text_edit(doc, span, row["new_text"],
                              editable_region=_region(row["editable_region_pt"]))  # fmt: skip


@pytest.mark.parametrize("row", AVAILABLE, ids=[r["fixture_id"] for r in AVAILABLE])
def test_release_matrix(row, tmp_path):
    expected, reason = row["expected"], row["reason_code"]
    with DocumentService() as svc:
        try:
            opened = svc.open_document(FILES / f"{row['fixture_id']}.pdf")
        except ServiceError as exc:  # 開檔即受控拒絕
            assert expected == "reject" and exc.code == reason, (exc.code, reason)
            return
        doc = opened["document_id"]
        assessment = svc.assess_editability(doc)
        reasons = set(assessment["document"]["reasons"])
        page = None
        if opened["page_count"]:
            page = svc.inspect_page(doc, int(row["page_index"]))
            reasons |= set(page["capabilities"]["reasons"])
            for t in page["text_targets"] + page["image_targets"] + page["cell_targets"]:
                reasons |= set(t["capability"]["reasons"])
        if expected == "support":
            plan = _plan(svc, doc, row, page, tmp_path)
            assert plan["ready"], plan["unsupported_reasons"]
            applied = svc.apply_edit(doc, plan["plan_id"], opened["revision"])
            token = svc.destination_token(tmp_path / "out.pdf")
            report = svc.export_document(doc, token, applied["new_revision"])["validation_report"]
            assert report["ok"], report["failures"]
            return
        if page is not None and row["target"] and row["new_text"]:
            try:
                plan = _plan(svc, doc, row, page, tmp_path)
            except ServiceError as exc:  # 找不到可編輯的目標也是受控拒絕
                reasons.add(exc.code)
            else:
                assert not plan["ready"], "錯誤標成可編輯"
                reasons |= set(plan["unsupported_reasons"])
        assert reason in reasons, (reason, sorted(reasons))


def test_matrix_covers_manifest():
    """61 份 = repo 內 49 份 available + 盲測 11 份 + U06（ADR-0012）；未在 repo 的都是 pending。"""
    assert len(AVAILABLE) + len(PENDING) == 61
    assert len(AVAILABLE) == 49
    assert {r["fixture_id"] for r in PENDING if r["blind"] == "true"} >= {"T10", "T11", "T12"}
    assert all(r["status"] == "pending" for r in PENDING)
