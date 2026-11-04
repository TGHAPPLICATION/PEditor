"""表格儲存格改字（spec P6、§7 plan_cell_edit；ADR-0023；只在 worker 使用）。

格內一次只改一行（ADR-0023 §1）：以該行的文字目標組成 span，沿用 P2 `plan_text_edit`（模式 A／B、
溢出判定、真修改），可改動區域為「格內緣 × 該行所在的水平帶」，扣掉與同格其他行（片段）之間的一半，
再裁到不碰任何障礙線（含 Form 內的線；P6 核對 Q1、Q2），最後以渲染結果的墨跡為準再裁一次
（第三輪核對 S1–S3：shading、註解、Type3、影像等任何畫法），不包含同格其他行與其他格。
不自動換行、不重排；新文字超出可改動區域回 `TEXT_OVERFLOW`。格本身不支援時（合併格、跨格文字、
空白格、人工框選不合規則）直接拒絕，不規劃。
"""

from __future__ import annotations

import collections
import math
import secrets

import pymupdf

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
        warnings = ["空白格：只修改既有文字，不新增內容"] if cell.get("empty") else []
        return _reject(document, params, page_index, info, cell["capability"]["reasons"], warnings)
    lines = cell["lines"]
    if params["line_index"] >= len(lines):
        raise ProtocolError("INVALID_REQUEST", "行號超出範圍")
    line = lines[params["line_index"]]
    if line["capability"]["reasons"]:  # 這一行的文字本身不支援（只擋這一行；P6 核對 Q3）
        return _reject(document, params, page_index, info, line["capability"]["reasons"])
    found = document.tables[page_index][0]
    region = table.clip(_line_band(cell["inner_bbox"], lines, params["line_index"]),
                        line["bbox"], found.obstacles)  # fmt: skip
    # 有垂直線穿過這一行的文字，或區域內有斜邊（斜線表頭等；第二輪核對 R2）
    if region is None or table.hits_diagonal(region, found.diagonals):
        return _reject(document, params, page_index, info, ["UNSUPPORTED_LAYOUT"])
    region = _ink_clip(document, page_index, region, line["bbox"])
    if region is None:
        return _reject(document, params, page_index, info, ["UNSUPPORTED_LAYOUT"])
    texts = {t["target_id"]: t["text"] for t in analyzer.inspect_page(document, page_index)[
        "text_targets"]}  # fmt: skip
    target = SpanTarget(tuple(line["target_ids"]), 0, len(texts[line["target_ids"][-1]]))
    text_params = {"target_id": target.span_id, "new_text": params["new_text"],
                   "policy": params["policy"], "editable_region": region}  # fmt: skip
    plan = edit.plan_text_edit(document, text_params)
    plan["target"]["cell"] = info
    pending = document.plans.get(plan["plan_id"])
    if pending is not None:
        pending.plan.target["cell"] = info
        pending.op, pending.params = "cell", params
    return plan


INK_ZOOM = 150 / 72  # 墨跡檢查的渲染解析度（150 DPI，與另存視覺驗證相同）
INK_TOL = 48  # 與區域底色任一通道相差超過此值即為墨跡（避開反鋸齒的淡邊）
TEXT_MARGIN = 1.0  # 目標文字外框外擴（pt），其內的墨跡是這一行自己的字形


def _ink_clip(document, page_index: int, region: list[float], text_bbox) -> list[float] | None:
    """以渲染結果為準裁切可改動區域（ADR-0023 §2，第三輪核對）：MuPDF 渲染目前工作文件的這一頁
    （含註解外觀、shading、Type3、影像），扣掉目標文字自己的範圍後，與區域底色不同的像素即為墨跡；
    從文字往左右延伸到第一個有墨跡的欄、再往上下延伸到第一個有墨跡的列。渲染空白的檔案
    （ADR-0015）沒有墨跡，只靠向量障礙線。"""
    with pymupdf.open(stream=document.current, filetype="pdf") as doc:
        page = doc[page_index]
        page.set_rotation(0)  # 與頁面空間（未套用 /Rotate）一致
        pix = page.get_pixmap(matrix=pymupdf.Matrix(INK_ZOOM, INK_ZOOM), clip=pymupdf.Rect(*region),
                              alpha=False, colorspace=pymupdf.csRGB)  # fmt: skip
    width, height, stride, data = pix.width, pix.height, pix.stride, pix.samples
    if not width or not height:
        return None
    samples = (data[r * stride + c * 3 : r * stride + c * 3 + 3]
               for r in range(0, height, 2) for c in range(0, width, 2))  # fmt: skip
    counts = collections.Counter(samples)
    background = counts.most_common(1)[0][0]

    def ink(row: int, col: int) -> bool:
        i = row * stride + col * 3
        return max(abs(data[i + k] - background[k]) for k in range(3)) > INK_TOL

    def col_of(x: float) -> int:
        return min(width, max(0, math.floor(x * INK_ZOOM) - pix.x))

    def row_of(y: float) -> int:
        return min(height, max(0, math.floor(y * INK_ZOOM) - pix.y))

    tx0, ty0, tx1, ty1 = (text_bbox[0] - TEXT_MARGIN, text_bbox[1] - TEXT_MARGIN,
                          text_bbox[2] + TEXT_MARGIN, text_bbox[3] + TEXT_MARGIN)  # fmt: skip
    c0, c1, r0, r1 = (
        col_of(tx0),
        max(col_of(tx1) + 1, col_of(tx0) + 1),
        row_of(ty0),
        row_of(ty1) + 1,
    )
    # 左右延伸只看文字的上方 3/4：底線區的墨跡（底線、填空線）不擋（同 table.clip）
    core = row_of(ty0 + (ty1 - ty0) * (1 - table.UNDERLINE_ZONE)) + 1
    rows = range(r0, min(core, height))
    left, right = 0, width
    for col in range(min(c1, width), width):  # 文字右側：第一個有墨跡的欄
        if any(ink(r, col) for r in rows):
            right = col
            break
    for col in range(min(c0, width) - 1, -1, -1):  # 文字左側
        if any(ink(r, col) for r in rows):
            left = col + 1
            break
    cols = range(left, right)
    top, bottom = 0, height
    for row in range(r0 - 1, -1, -1):  # 文字上方：第一個有墨跡的列
        if any(ink(row, c) for c in cols):
            top = row + 1
            break
    for row in range(min(r1, height), height):  # 文字下方
        if any(ink(row, c) for c in cols):
            bottom = row
            break
    z = INK_ZOOM
    clipped = [max(region[0], (pix.x + left) / z), max(region[1], (pix.y + top) / z),
               min(region[2], (pix.x + right) / z),
               min(region[3], (pix.y + bottom) / z)]  # fmt: skip
    if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
        return None
    return clipped


def _reject(document, params, page_index, info, reasons, warnings=()) -> dict:
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
        unsupported_reasons=list(reasons),
        warnings=list(warnings),
    )
    return edit._store(document, plan, None)


def _line_band(inner: list[float], lines: list[dict], index: int) -> list[float]:
    """格內緣裡屬於這一行的範圍：與上下行之間取中線（沒有則到格邊），與同一列左右的片段之間也取中線。"""
    box = lines[index]["bbox"]
    x0, y0, x1, y1 = inner
    for i, other in enumerate(lines):
        if i == index:
            continue
        o = other["bbox"]
        if o[1] < box[3] and box[1] < o[3]:  # 同一列的片段：左右切開
            if o[0] >= box[2]:
                x1 = min(x1, (box[2] + o[0]) / 2)
            elif o[2] <= box[0]:
                x0 = max(x0, (o[2] + box[0]) / 2)
        elif o[3] <= box[1]:
            y0 = max(y0, (o[3] + box[1]) / 2)
        elif o[1] >= box[3]:
            y1 = min(y1, (box[3] + o[1]) / 2)
    return [x0, y0, x1, y1]
