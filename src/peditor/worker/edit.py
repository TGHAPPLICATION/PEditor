"""文字編輯計畫與套用（spec §3、§7；ADR-0001、ADR-0018；只在 worker 使用）。

模式 A：只改寫目標文字顯示運算子中被替換字形的字碼，原字型、座標、其他運算子不動；
新舊字寬差以 TJ 位移補償，目標之後的字形位置不變（ADR-0018 §2）。
改動跨同一 BT 內相鄰的多段運算子時，新字碼放入第一段，最後一段以開頭位移把剩餘字形放回原位。
模式 B：原字型缺字時移除舊字形，在同一 BT 內換用 Noto Sans TC 子集字型畫新字，
再換回原字型（ADR-0018 §4）。
"""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass

import pikepdf

from peditor.core.editplan import EditPlan, SpanTarget, parse_target_id, validate_plan_params
from peditor.core.geometry import apply, contains
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, fontb, span, tagged
from peditor.worker.content import TextRun

POSITION_TOL = 0.01  # pt；溢出判定的數值容許


# 多段改動時，段與段之間只允許不移動文字位置的狀態運算子（ADR-0018 §2）
_STATE_OPS = frozenset({"Tf", "Tc", "Tw", "Tz", "TL", "Ts", "Tr", "gs", "g", "G", "rg", "RG",
                        "k", "K", "cs", "CS", "sc", "SC", "scn", "SCN", "w", "J", "j", "M", "d",
                        "ri", "i"})  # fmt: skip
_MARKED_OPS = frozenset({"BDC", "BMC", "EMC", "MP", "DP"})


@dataclass
class _OpEdit:
    """一個文字顯示運算子的改寫。

    mode：replace＝替換字形 [g0, g1)（保留其間原有位移，可附補償）；
    head＝自 g0 起到運算子結尾全部移除後放入新字碼；all＝全部移除；
    tail＝移除開頭到字形 g1 之前（g1 為字形數時保留結尾位移），開頭放入補償；
    split_b／head_b＝模式 B：拆成「前段、換字型畫新字、換回原字型、（後段）」。
    """

    run: TextRun
    mode: str
    g0: int
    g1: int
    codes: list[int]
    number: float  # TJ 位移（千分之一字級）；0 表示不需要


@dataclass
class _Pending:
    plan: EditPlan
    edits: list[_OpEdit]
    text: str = ""  # 實際改動的新文字（模式 B 依此建子集字型）
    font_name: str | None = None  # 模式 B 新增的字型資源名稱
    sync: tagged.ActualTextSync | None = None  # 需同步的結構元素 /ActualText（ADR-0017）


def _span_target(document: analyzer.Document, target_id: str) -> SpanTarget:
    """span target_id，或 P1 的單一文字目標（整段運算子）。"""
    if target_id.startswith("span:"):
        return SpanTarget.parse(target_id)
    page_index = parse_target_id(target_id).page_index
    analyzer.inspect_page(document, page_index)
    runs, index = document.runs.get(page_index, ([], {}))
    if target_id not in index:
        raise ProtocolError("INVALID_REQUEST", "目標不存在")
    return SpanTarget((target_id,), 0, len(runs[index[target_id]].text))


def plan_text_edit(document: analyzer.Document, params: dict) -> dict:
    params = validate_plan_params(params)
    target = _span_target(document, params["target_id"])
    selection = span.resolve(document, target)
    change = span.change(selection, params["new_text"])
    region = params["editable_region"] or _selection_box(selection)
    piece = change.pieces[0]
    plan = EditPlan(
        plan_id=secrets.token_hex(8),
        document_id=document.document_id,
        preconditions={"sha256": document.sha256, "revision": document.revision},
        target={
            "span_id": target.span_id,
            "page_index": target.page_index,
            "selected_text": selection.text,
            "change": {
                "target_ids": [p.target["target_id"] for p in change.pieces],
                "glyph_range": [[p.g0, p.g1] for p in change.pieces],
                "old_text": change.old_text,
                "new_text": change.new_text,
            },
        },
        new_text=params["new_text"],
        policy=params["policy"],
        mode=None,
        font_policy="keep_original",
        allowed_change_mask=region,
        unsupported_reasons=list(change.reasons),
    )
    if plan.unsupported_reasons:
        return _store(document, plan, None)
    runs = [selection.runs[p.run_index] for p in change.pieces]
    run = runs[0]
    if _shared_stream(document, selection.page_index, run):
        plan.unsupported_reasons.append("SHARED_RESOURCE_UNSAFE")
        return _store(document, plan, None)
    if len(runs) > 1:
        reason = _between_pieces(document, runs)
        if reason:
            plan.unsupported_reasons.append(reason)
            return _store(document, plan, None)
    char_start = sum(len(g.unicode or "�") for g in run.glyphs[: piece.g0])
    reason, sync = tagged.check(document.pike, selection.page_index, selection.runs,
                                [p.run_index for p in change.pieces], char_start,
                                change.old_text, change.new_text)  # fmt: skip
    if reason:
        plan.unsupported_reasons.append(reason)
        return _store(document, plan, None)
    codes = run.font.encode(change.new_text, {g.code for g in run.glyphs}) if run.font else None
    mode = "A" if codes is not None else "B"
    if mode == "B":
        blocker = _mode_b_blocker(params["policy"], run, change.new_text)
        if blocker:
            plan.unsupported_reasons.append(blocker[0])
            plan.warnings += blocker[1:]
            return _store(document, plan, None)
        new_adv = sum(w / 1000.0 * run.size + run.char_space
                      for w in fontb.widths(change.new_text))  # fmt: skip
    else:
        new_adv = sum(run.advance(c) for c in codes)

    old_codes = [g.code for p, r in zip(change.pieces, runs, strict=True)
                 for g in r.glyphs[p.g0 : p.g1]]  # fmt: skip
    start = _start_origin(run, piece.g0)
    a, b = run.matrix[0], run.matrix[1]
    end = (start[0] + new_adv / run.size * a, start[1] + new_adv / run.size * b)
    if mode == "A" and len(runs) == 1:
        old_adv = sum(run.advance(c) for c in old_codes)
        compensation = (new_adv - old_adv) * 1000.0 / run.size if run.size else 0.0
        if abs(compensation) < 1e-6:
            compensation = 0.0
        if compensation and run.operator in ("'", '"'):
            plan.unsupported_reasons.append("UNSUPPORTED_LAYOUT")  # 換行顯示運算子無法以 TJ 補償
            return _store(document, plan, None)
        edits = [_OpEdit(run, "replace", piece.g0, piece.g1, codes, compensation)]
    else:
        edits = _position_edits(change, runs, codes, start, end, mode)
        if edits is None:
            plan.unsupported_reasons.append("UNSUPPORTED_LAYOUT")
            return _store(document, plan, None)

    to_page = analyzer.page_geometry(document.pike.pages[selection.page_index]).pdf_to_page()
    page_start, page_end = apply(to_page, *start), apply(to_page, *end)
    plan.geometry = {
        "baseline_start": [round(v, 3) for v in page_start],
        "baseline_end": [round(v, 3) for v in page_end],
        "font_size": run.size,
        "pdfium_width_residual_pt": _truncation_residual(run, old_codes, codes or []),
    }
    if not all(contains(tuple(region), *p, tol=POSITION_TOL) for p in (page_start, page_end)):
        plan.unsupported_reasons.append("TEXT_OVERFLOW")
        return _store(document, plan, None)
    plan.mode = mode
    font_name = None
    if mode == "B":
        font_name = _new_font_name(document, selection.page_index)
        plan.font_policy = "replace_with_packaged"
        plan.font_changes = [{"from": run.font.base_font if run.font else None,
                              "to": fontb.FONT_NAME, "text": change.new_text}]  # fmt: skip
        plan.resource_changes = [{"page_index": selection.page_index, "kind": "Font",
                                  "added": font_name, "font": fontb.FONT_NAME}]  # fmt: skip
        plan.warnings.append("字型已替換為 Noto Sans TC，需人工確認版面（ADR-0018 §4）")
        if change.old_text != selection.text or change.new_text != params["new_text"]:
            plan.warnings.append("選取範圍內原字型與 Noto Sans TC 並存（只重建實際改動的字）")
    if sync is not None:
        plan.resource_changes.append({
            "page_index": selection.page_index, "kind": "StructElem", "field": "ActualText",
            "element": list(sync.element),
        })  # fmt: skip
        plan.warnings.append("已同步更新結構樹 /ActualText（ADR-0017）")
    return _store(document, plan, _Pending(plan, edits, change.new_text, font_name, sync))


def _mode_b_blocker(policy: str, run: TextRun, text: str) -> tuple[str, ...] | None:
    """模式 B 不可行時回傳（理由碼, 說明…）。"""
    if policy == "a_only":
        return ("GLYPH_MISSING",)
    if run.operator in ("'", '"'):
        return ("UNSUPPORTED_LAYOUT",)  # 換行顯示運算子無法拆成多段
    if not fontb.available():
        return ("GLYPH_MISSING", "原字型缺字，且模式 B 字型（Noto Sans TC）不可用")
    if fontb.missing(text):
        return ("GLYPH_MISSING", "原字型與 Noto Sans TC 都沒有部分新字")
    return None


def _new_font_name(document: analyzer.Document, page_index: int) -> str:
    fonts = _page_fonts(document.pike.pages[page_index])
    n = 1
    while f"/PEditorB{n}" in fonts:
        n += 1
    return f"/PEditorB{n}"


def _page_resources(page: pikepdf.Page) -> pikepdf.Dictionary:
    """頁面（含自 /Pages 繼承）的 /Resources；沒有時回空字典。"""
    node = page.obj
    for _ in range(64):
        res = node.get("/Resources")
        if isinstance(res, pikepdf.Dictionary):
            return res
        node = node.get("/Parent")
        if not isinstance(node, pikepdf.Dictionary):
            break
    return pikepdf.Dictionary()


def _page_fonts(page: pikepdf.Page) -> set[str]:
    fonts = _page_resources(page).get("/Font")
    return set(map(str, fonts.keys())) if isinstance(fonts, pikepdf.Dictionary) else set()


def _between_pieces(document: analyzer.Document, runs: list[TextRun]) -> str | None:
    """多段改動：同字型、同字級、同方向基線，段與段之間只有不移動文字位置的狀態運算子。"""
    first = runs[0]
    for run in runs[1:]:
        if run.font is None or first.font is None or run.font.objgen != first.font.objgen:
            return "UNSUPPORTED_LAYOUT"  # 換字型會把原屬他字型的字改成第一段的字型
        if run.size != first.size or run.scale != first.scale or run.operator in ("'", '"'):
            return "UNSUPPORTED_LAYOUT"
        if any(abs(u - v) > 1e-6 for u, v in zip(run.matrix[:4], first.matrix[:4], strict=True)):
            return "UNSUPPORTED_LAYOUT"
    instructions = list(pikepdf.parse_content_stream(document.pike.get_object(first.stream)))
    for inst in instructions[first.op_index + 1 : runs[-1].op_index]:
        if not isinstance(inst, pikepdf.ContentStreamInstruction):
            return "UNSUPPORTED_LAYOUT"
        op = str(inst.operator)
        if op in _MARKED_OPS:
            return "UNSUPPORTED_FEATURE"  # 跨標記內容（ADR-0017）
        if op in ("Tj", "TJ") or op in _STATE_OPS:
            if op == "Tf" and inst.operands and str(inst.operands[0]) != first.font.key:
                return "UNSUPPORTED_LAYOUT"
            continue
        return "UNSUPPORTED_LAYOUT"  # Td／Tm／T*、路徑、影像等
    return None


def _tail_number(piece_last, first: TextRun, last: TextRun, start, end) -> float | None:
    """把改動之後的字形放回原位所需的 TJ 位移（千分之一字級）。

    以基線方向上的實際位置計算（含原有 TJ 位移），不累加字寬；不在同一基線回 None。
    """
    ux, uy = first.matrix[0], first.matrix[1]
    unit = math.hypot(ux, uy)
    if unit == 0:
        return None
    ux, uy = ux / unit, uy / unit
    if piece_last.g1 < len(last.glyphs):
        target = last.glyphs[piece_last.g1].origin
    else:
        tail = last.glyphs[-1]
        step = last.advance(tail.code) / last.size
        target = (tail.origin[0] + step * last.matrix[0], tail.origin[1] + step * last.matrix[1])
    # 剩餘字形應在的位置 − 新字之後的位置（基線方向，PDF 空間）
    gap = (target[0] - end[0]) * ux + (target[1] - end[1]) * uy
    if abs(-(target[0] - start[0]) * uy + (target[1] - start[1]) * ux) > POSITION_TOL:
        return None
    number = -gap * 1000.0 / math.hypot(last.matrix[0], last.matrix[1])
    return number if abs(number) > 1e-6 else 0.0


def _position_edits(change, runs, codes, start, end, mode: str) -> list[_OpEdit] | None:
    """模式 A 多段，或模式 B（單段／多段）：新字放在第一段的改動起點；中間段清空；
    最後一段（單段時即同一段）以位移把改動之後的字形放回原位。"""
    first, last = runs[0], runs[-1]
    p0, pl = change.pieces[0], change.pieces[-1]
    number = _tail_number(pl, first, last, start, end)
    if number is None:
        return None
    if len(runs) == 1:  # 只有模式 B 會走到單段
        return [_OpEdit(first, "split_b", p0.g0, p0.g1, [], number)]
    head = "head" if mode == "A" else "head_b"
    edits = [_OpEdit(first, head, p0.g0, len(first.glyphs), codes or [], 0.0)]
    edits += [_OpEdit(r, "all", 0, len(r.glyphs), [], 0.0) for r in runs[1:-1]]
    edits.append(_OpEdit(last, "tail", 0, pl.g1, [], number))
    return edits


def _store(document: analyzer.Document, plan: EditPlan, pending: _Pending | None) -> dict:
    if pending is not None:
        document.plans[plan.plan_id] = pending
    return plan.to_dict()


def _selection_box(selection: span.Selection) -> list[float]:
    boxes = [g["bbox"] for p in selection.pieces for g in p.target["glyphs"] if g["bbox"]]
    if not boxes:
        raise ProtocolError("INVALID_REQUEST", "需指定 editable_region")
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
            max(b[3] for b in boxes)]  # fmt: skip


def _truncation_residual(run: TextRun, old_codes: list[int], new_codes: list[int]) -> float:
    """PDFium 將單位元組字型的小數 /Widths 截為整數（ADR-0019）：以規範字寬計算的補償，
    在 PDFium 中會讓目標之後的字形移動此距離（pt）。Type0 與無小數字寬時為 0。"""
    font = run.font
    if font is None or font.two_byte:
        return 0.0

    def lost(codes: list[int]) -> float:
        return sum(math.trunc(font.widths[c]) - font.widths[c] for c in codes if c in font.widths)

    residual = (lost(new_codes) - lost(old_codes)) * run.size / 1000.0 * run.scale
    return round(residual, 6) if abs(residual) > 1e-9 else 0.0


def _start_origin(run: TextRun, g0: int) -> tuple[float, float]:
    """改動起點（PDF 空間基線點）：第 g0 個字形原點；插在最後時為最後字形之後。"""
    if g0 < len(run.glyphs):
        return run.glyphs[g0].origin
    last = run.glyphs[g0 - 1]
    step = run.advance(last.code) / run.size
    return (last.origin[0] + step * run.matrix[0], last.origin[1] + step * run.matrix[1])


def _shared_stream(document: analyzer.Document, page_index: int, run: TextRun) -> bool:
    """目標 content stream 也被其他頁使用時，就地改寫會連帶改動其他頁。"""
    for i, page in enumerate(document.pike.pages):
        if i == page_index:
            continue
        contents = page.obj.get("/Contents")
        streams = contents if isinstance(contents, pikepdf.Array) else [contents]
        if any(isinstance(s, pikepdf.Stream) and s.objgen == run.stream for s in streams):
            return True
    return False


def apply_edit(document: analyzer.Document, plan_id, expected_revision) -> dict:
    pending = document.plans.get(plan_id) if isinstance(plan_id, str) else None
    if pending is None:
        raise ProtocolError("INVALID_REQUEST", "計畫不存在或已失效")
    if expected_revision != document.revision or (
        pending.plan.preconditions["revision"] != document.revision
    ):
        raise ProtocolError("REVISION_CONFLICT", "文件版本不符", retryable=True)
    _rewrite(document, pending)
    if pending.sync is not None:
        element = document.pike.get_object(pending.sync.element)
        if str(element.get("/ActualText")) != pending.sync.old:
            raise ProtocolError("VALIDATION_FAILED", "內容與計畫不一致")
        element.ActualText = pikepdf.String(pending.sync.new)
    document.commit()
    return {"new_revision": document.revision, "command_id": secrets.token_hex(8)}


def _rewrite(document: analyzer.Document, pending: _Pending) -> None:
    streams = {e.run.stream for e in pending.edits}
    if len(streams) != 1:
        raise ProtocolError("VALIDATION_FAILED", "內容與計畫不一致")
    b_codes: list[int] = []
    if pending.font_name is not None:  # 模式 B：新增子集字型資源（頁面資源寫時複製）
        font, b_codes = fontb.build_font(document.pike, pending.text)
        page = document.pike.pages[pending.plan.target["page_index"]]
        resources = pikepdf.Dictionary(_page_resources(page))
        fonts = resources.get("/Font")
        fonts = (
            pikepdf.Dictionary(fonts)
            if isinstance(fonts, pikepdf.Dictionary)
            else pikepdf.Dictionary()
        )
        fonts[pending.font_name] = font
        resources.Font = fonts
        page.obj.Resources = resources
    stream = document.pike.get_object(streams.pop())
    instructions = list(pikepdf.parse_content_stream(stream))
    # 由後往前改寫：模式 B 會把一個運算子展開成多個，先改後面的才不影響前面的索引
    for edit in sorted(pending.edits, key=lambda e: e.run.op_index, reverse=True):
        index = edit.run.op_index
        instructions[index : index + 1] = _rewrite_op(instructions[index], edit, b_codes,
                                                      pending.font_name)  # fmt: skip
    stream.write(pikepdf.unparse_content_stream(instructions))


def _tj(tokens, two_byte: bool):
    return pikepdf.ContentStreamInstruction([pikepdf.Array(_regroup(tokens, two_byte))],
                                            pikepdf.Operator("TJ"))  # fmt: skip


def _rewrite_op(inst, edit: _OpEdit, b_codes: list[int], font_name: str | None) -> list:
    run = edit.run
    if not isinstance(inst, pikepdf.ContentStreamInstruction) or str(inst.operator) != run.operator:
        raise ProtocolError("VALIDATION_FAILED", "內容與計畫不一致")
    operands = list(inst.operands)
    items = list(operands[0]) if run.operator == "TJ" else [operands[-1]]
    tokens: list[tuple[str, object]] = []  # ("g", 字碼) 或 ("n", TJ 位移)
    for item in items:
        if isinstance(item, pikepdf.String):
            tokens += [("g", code) for code in run.font.codes(bytes(item))]
        else:
            tokens.append(("n", item))
    positions = [i for i, (kind, _) in enumerate(tokens) if kind == "g"]
    if [tokens[i][1] for i in positions] != [g.code for g in run.glyphs]:
        raise ProtocolError("VALIDATION_FAILED", "內容與計畫不一致")
    glyphs = [("g", code) for code in edit.codes]
    number = [("n", edit.number)] if edit.number else []
    if edit.mode == "replace":
        if edit.g0 < edit.g1:
            lo, hi = positions[edit.g0], positions[edit.g1 - 1] + 1
        else:  # 純插入
            lo = hi = positions[edit.g0] if edit.g0 < len(positions) else len(tokens)
        kept = [t for t in tokens[lo:hi] if t[0] == "n"]  # 被替換字形之間原有的位移
        # TJ 數值 n 使位置移動 -n/1000×字級；n＝(新寬−舊寬)×1000/字級 抵銷字寬差
        tokens[lo:hi] = glyphs + kept + number
    elif edit.mode == "head":
        tokens[positions[edit.g0] :] = glyphs
    elif edit.mode == "all":
        tokens = []
    elif edit.mode == "tail":
        hi = positions[edit.g1] if edit.g1 < len(positions) else positions[-1] + 1
        tokens[:hi] = number
    elif edit.mode in ("split_b", "head_b"):
        end_of_glyphs = positions[-1] + 1 if positions else len(tokens)
        lo = positions[edit.g0] if edit.g0 < len(positions) else end_of_glyphs
        if edit.mode == "head_b":
            suffix = []
        elif edit.g1 > edit.g0:
            hi = positions[edit.g1] if edit.g1 < len(positions) else end_of_glyphs
            suffix = number + tokens[hi:]  # 被改字形與後段之間的原有位移已含在補償中
        else:  # 純插入
            suffix = number + tokens[lo:]
        sequence = [_tj(tokens[:lo], run.font.two_byte)] if tokens[:lo] else []
        sequence += [
            pikepdf.ContentStreamInstruction(
                [pikepdf.Name(font_name), run.size], pikepdf.Operator("Tf")
            ),  # fmt: skip
            _tj([("g", code) for code in b_codes], True),
            pikepdf.ContentStreamInstruction(
                [pikepdf.Name(run.font.key), run.size], pikepdf.Operator("Tf")
            ),  # fmt: skip
        ]
        if suffix:
            sequence.append(_tj(suffix, run.font.two_byte))
        return sequence
    array = _regroup(tokens, run.font.two_byte)
    if run.operator == "TJ" or len(array) != 1 or not isinstance(array[0], pikepdf.String):
        if run.operator in ("'", '"'):
            raise ProtocolError("VALIDATION_FAILED", "內容與計畫不一致")
        return [pikepdf.ContentStreamInstruction([pikepdf.Array(array)], pikepdf.Operator("TJ"))]
    return [pikepdf.ContentStreamInstruction([*operands[:-1], array[0]], inst.operator)]


def _regroup(tokens, two_byte: bool) -> list:
    out: list = []
    buf = bytearray()
    for kind, value in tokens:
        if kind == "g":
            buf += value.to_bytes(2, "big") if two_byte else bytes([value])
            continue
        if buf:
            out.append(pikepdf.String(bytes(buf)))
            buf = bytearray()
        out.append(value if not isinstance(value, float) else round(value, 3))
    if buf or not out:
        out.append(pikepdf.String(bytes(buf)))
    return out
