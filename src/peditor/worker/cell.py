"""表格儲存格改字（spec P6、§7 plan_cell_edit；ADR-0023；只在 worker 使用）。

格內一次只改一行（ADR-0023 §1）：以該行的文字目標組成 span，沿用 P2 `plan_text_edit`（模式 A／B、
溢出判定、真修改），可改動區域為「格內緣 × 該行所在的水平帶」，不包含同格其他行與其他格。
不自動換行、不重排；新文字超出可改動區域回 `TEXT_OVERFLOW`。格本身不支援時（合併格、跨格文字、
空白格、人工框選不合規則）直接拒絕，不規劃。
"""

from __future__ import annotations

import secrets

from peditor.core.editplan import EditPlan, SpanTarget, validate_cell_params
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, edit, table


def _resolve(document: analyzer.Document, params: dict) -> tuple[int, dict]:
    """（頁, 格）：已偵測的格以 cell_id 查找；人工框選以 cell_box 判定。"""
    page_index = params["page_index"]
    page = analyzer.inspect_page(document, page_index)
    found, cells, by_id = document.tables[page_index]
    if params["cell_id"] is not None:
        cell = by_id.get(params["cell_id"])
        if cell is None:
            raise ProtocolError("INVALID_REQUEST", "儲存格不存在")
        return page_index, cell
    cell = table.assess_box(params["cell_box"], found, cells, page["text_targets"],
                            document.doc_reasons)  # fmt: skip
    return page_index, {**cell, "cell_id": None, "manual": True}


def assess_cell_box(document: analyzer.Document, params: dict) -> dict:
    """人工框選範圍的能力判定與分行（只讀；UI 框選後顯示）。"""
    params = validate_cell_params({**params, "new_text": "-"}, require_text=False)
    return _resolve(document, params)[1]


def plan_cell_edit(document: analyzer.Document, params: dict) -> dict:
    params = validate_cell_params(params)
    page_index, cell = _resolve(document, params)
    info = {"cell_id": cell["cell_id"], "row": cell.get("row"), "col": cell.get("col"),
            "manual": bool(cell.get("manual")), "inner_bbox": cell["inner_bbox"],
            "line_index": params["line_index"]}  # fmt: skip
    if cell["capability"]["reasons"]:
        plan = EditPlan(
            plan_id=secrets.token_hex(8),
            document_id=document.document_id,
            preconditions={"sha256": document.sha256, "revision": document.revision},
            target={"page_index": page_index, "cell": info},
            new_text=params["new_text"],
            policy=params["policy"],
            mode=None,
            font_policy="keep_original",
            allowed_change_mask=None,
            unsupported_reasons=list(cell["capability"]["reasons"]),
        )
        if cell.get("empty"):
            plan.warnings.append("空白格：只修改既有文字，不新增內容")
        return edit._store(document, plan, None)
    lines = cell["lines"]
    if params["line_index"] >= len(lines):
        raise ProtocolError("INVALID_REQUEST", "行號超出範圍")
    line = lines[params["line_index"]]
    texts = {t["target_id"]: t["text"] for t in analyzer.inspect_page(document, page_index)[
        "text_targets"]}  # fmt: skip
    target = SpanTarget(tuple(line["target_ids"]), 0, len(texts[line["target_ids"][-1]]))
    region = _line_band(cell["inner_bbox"], lines, params["line_index"])
    text_params = {"target_id": target.span_id, "new_text": params["new_text"],
                   "policy": params["policy"], "editable_region": region}  # fmt: skip
    plan = edit.plan_text_edit(document, text_params)
    plan["target"]["cell"] = info
    pending = document.plans.get(plan["plan_id"])
    if pending is not None:
        pending.plan.target["cell"] = info
        pending.op, pending.params = "cell", params
    return plan


def _line_band(inner: list[float], lines: list[dict], index: int) -> list[float]:
    """格內緣的水平範圍 × 該行與上下行之間的中線（第一行到格頂、最後一行到格底）。"""
    box = lines[index]["bbox"]
    top = inner[1] if index == 0 else (lines[index - 1]["bbox"][3] + box[1]) / 2
    bottom = inner[3] if index == len(lines) - 1 else (box[3] + lines[index + 1]["bbox"][1]) / 2
    return [inner[0], top, inner[2], bottom]
