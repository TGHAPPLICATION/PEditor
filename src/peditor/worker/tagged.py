"""標記 PDF 的結構樹檢查與 /ActualText 同步（ADR-0017；只在 worker 使用）。

目標字元所在的標記內容（BDC）帶替代文字、或結構元素／祖先帶 /Alt、/E → 拒絕。
結構元素鏈上唯一的 /ActualText 完全等於其涵蓋內容的擷取文字時，允許編輯並同步替換同一字元範圍。
"""

from __future__ import annotations

from dataclasses import dataclass

import pikepdf

from peditor.core.limits import MAX_OBJECT_WALK
from peditor.worker.content import TextRun, interpret

_ALT_KEYS = ("/ActualText", "/Alt", "/E")


@dataclass(frozen=True)
class ActualTextSync:
    element: tuple[int, int]  # 結構元素 objgen
    old: str
    new: str
    mcid: int  # 儲存後以 MCID 找回結構元素（存檔會重編物件號）


def _props(inst, resources) -> pikepdf.Dictionary | None:
    if str(inst.operator) != "BDC" or len(inst.operands) < 2:
        return None
    props = inst.operands[1]
    if isinstance(props, pikepdf.Name):
        table = resources.get("/Properties") if isinstance(resources, pikepdf.Dictionary) else None
        props = table.get(props) if isinstance(table, pikepdf.Dictionary) else None
    return props if isinstance(props, pikepdf.Dictionary) else None


def marked_content(page: pikepdf.Page, runs: list[TextRun]) -> dict[int, tuple[int | None, bool]]:
    """每段文字運算子（以 runs 索引）所在的最內層 MCID，以及外層任一標記內容是否帶替代文字。"""
    resources = page.obj.get("/Resources")
    by_stream: dict[tuple, dict[int, int]] = {}
    for i, run in enumerate(runs):
        if not run.form_path:
            by_stream.setdefault(run.stream, {})[run.op_index] = i
    result: dict[int, tuple[int | None, bool]] = {}
    contents = page.obj.get("/Contents")
    streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
    stack: list[tuple[int | None, bool]] = []  # 標記內容可跨 content stream
    for stream in streams:
        if not isinstance(stream, pikepdf.Stream):
            continue
        wanted = by_stream.get(stream.objgen, {})
        for index, inst in enumerate(pikepdf.parse_content_stream(stream)):
            if not isinstance(inst, pikepdf.ContentStreamInstruction):
                continue
            op = str(inst.operator)
            if op in ("BDC", "BMC"):
                props = _props(inst, resources)
                mcid = props.get("/MCID") if props is not None else None
                alt = props is not None and any(k in props for k in _ALT_KEYS)
                stack.append((int(mcid) if isinstance(mcid, int) else None, alt))
            elif op == "EMC":
                if stack:
                    stack.pop()
            elif index in wanted:
                mcid = next((m for m, _ in reversed(stack) if m is not None), None)
                result[wanted[index]] = (mcid, any(alt for _, alt in stack))
    return result


def _number_tree_get(node, key: int):
    """/ParentTree 數字樹查詢；走訪節點數有上限。"""
    stack, steps = [node], 0
    while stack:
        node = stack.pop()
        steps += 1
        if steps > MAX_OBJECT_WALK or not isinstance(node, pikepdf.Dictionary):
            return None
        nums = node.get("/Nums")
        if isinstance(nums, pikepdf.Array):
            for i in range(0, len(nums) - 1, 2):
                if nums[i] == key:
                    return nums[i + 1]
        kids = node.get("/Kids")
        if isinstance(kids, pikepdf.Array):
            for kid in kids:
                limits = kid.get("/Limits") if isinstance(kid, pikepdf.Dictionary) else None
                if isinstance(limits, pikepdf.Array) and len(limits) == 2:
                    if not int(limits[0]) <= key <= int(limits[1]):
                        continue
                stack.append(kid)
    return None


def _mcids_under(element: pikepdf.Dictionary, page: pikepdf.Page) -> list[int] | None:
    """結構元素依 /K 順序涵蓋的 MCID（只限本頁）；含 OBJR 或他頁內容時回 None。"""
    out: list[int] = []
    stack = [(element.get("/K"), element.get("/Pg"))]
    steps = 0
    while stack:
        item, pg = stack.pop()
        steps += 1
        if steps > MAX_OBJECT_WALK:
            return None
        if item is None:
            continue
        if isinstance(item, int):
            if pg is not None and pg.objgen != page.obj.objgen:
                return None
            out.append(int(item))
        elif isinstance(item, pikepdf.Array):
            stack.extend((k, pg) for k in reversed(list(item)))
        elif isinstance(item, pikepdf.Dictionary):
            kind = str(item.get("/Type", ""))
            if kind == "/OBJR":
                return None
            if kind == "/MCR":
                if "/Stm" in item:
                    return None
                stack.append((item.get("/MCID"), item.get("/Pg", pg)))
            else:  # 子結構元素
                stack.append((item.get("/K"), item.get("/Pg", pg)))
    return out


def check(
    pdf: pikepdf.Pdf, page_index: int, runs: list[TextRun], changed: list[int],
    char_start: int, old: str, new: str,
) -> tuple[str | None, ActualTextSync | None]:  # fmt: skip
    """回傳（拒絕理由碼或 None, 需同步的 /ActualText 或 None）。

    changed：實際改動涉及的 runs 索引；char_start：改動在第一段文字中的起始字元位置。
    """
    root = pdf.Root.get("/StructTreeRoot")
    if not isinstance(root, pikepdf.Dictionary):
        return None, None
    page = pdf.pages[page_index]
    marks = marked_content(page, runs)
    mcids = {marks.get(i, (None, False))[0] for i in changed}
    if any(marks.get(i, (None, False))[1] for i in changed):
        return "UNSUPPORTED_FEATURE", None
    if len(mcids) != 1:
        return "UNSUPPORTED_FEATURE", None  # 跨標記內容
    mcid = mcids.pop()
    if mcid is None:
        return None, None  # 不在結構中的內容（例如 Artifact）
    reason, holder = _holder(root, page, mcid)
    if reason or holder is None:
        return reason, None
    covered = _covered_runs(holder, page, marks, len(runs))
    if covered is None:
        return "UNSUPPORTED_FEATURE", None
    text, offset = "", None
    for i in covered:
        if i == changed[0]:
            offset = len(text) + char_start
        text += runs[i].text
    actual = str(holder.ActualText)
    if offset is None or actual != text or actual[offset : offset + len(old)] != old:
        return "UNSUPPORTED_FEATURE", None
    updated = actual[:offset] + new + actual[offset + len(old) :]
    return None, ActualTextSync(holder.objgen, actual, updated, mcid)


def synced(pdf: pikepdf.Pdf, page_index: int, mcid: int) -> bool:
    """儲存後驗證：MCID 所屬的 /ActualText 完全等於其涵蓋內容的擷取文字（ADR-0017）。"""
    root = pdf.Root.get("/StructTreeRoot")
    if not isinstance(root, pikepdf.Dictionary):
        return False
    page = pdf.pages[page_index]
    reason, holder = _holder(root, page, mcid)
    if reason or holder is None:
        return False
    runs = interpret(page).runs
    covered = _covered_runs(holder, page, marked_content(page, runs), len(runs))
    if covered is None:
        return False
    return str(holder.ActualText) == "".join(runs[i].text for i in covered)


def _holder(root, page: pikepdf.Page, mcid: int) -> tuple[str | None, pikepdf.Dictionary | None]:
    """MCID 所屬結構元素鏈上唯一帶 /ActualText 的元素。

    帶 /Alt、/E、多層 /ActualText 或結構不一致時回拒絕理由碼。
    """
    parents = page.obj.get("/StructParents")
    array = _number_tree_get(root.get("/ParentTree"), int(parents)) if parents is not None else None
    element = array[mcid] if isinstance(array, pikepdf.Array) and mcid < len(array) else None
    if not isinstance(element, pikepdf.Dictionary):
        return "UNSUPPORTED_FEATURE", None  # 結構不一致，不猜
    holder = None
    node, depth = element, 0
    while isinstance(node, pikepdf.Dictionary) and "/S" in node:
        depth += 1
        if depth > 64:
            return "RESOURCE_LIMIT", None
        if "/Alt" in node or "/E" in node:
            return "UNSUPPORTED_FEATURE", None
        if "/ActualText" in node:
            if holder is not None:
                return "UNSUPPORTED_FEATURE", None
            holder = node
        node = node.get("/P")
    return None, holder


def _covered_runs(holder, page: pikepdf.Page, marks: dict, count: int) -> list[int] | None:
    """/ActualText 涵蓋的文字運算子（runs 索引，依 /K 順序）。

    含 OBJR、他頁內容或重複 MCID 時回 None。重複 MCID 會讓同一段內容在
    /ActualText 中出現兩次，同步只能改到其中一處（P2 triage f007）。
    """
    covered = _mcids_under(holder, page)
    if covered is None or len(covered) != len(set(covered)):
        return None
    by_mcid: dict[int, list[int]] = {}
    for i in range(count):
        m = marks.get(i, (None, False))[0]
        if m is not None:
            by_mcid.setdefault(m, []).append(i)
    return [i for m in covered for i in by_mcid.get(m, [])]
