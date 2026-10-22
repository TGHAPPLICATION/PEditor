"""文字編輯計畫與套用（spec §3、§7；ADR-0001、ADR-0018；只在 worker 使用）。

模式 A：只改寫目標文字顯示運算子中被替換字形的字碼，原字型、座標、其他運算子不動；
新舊字寬差以 TJ 位移補償，目標之後的字形位置不變（ADR-0018 §2）。
模式 B（P2 步驟 7）尚未實作：A 不可行時計畫回 GLYPH_MISSING 並註明。
"""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass

import pikepdf

from peditor.core.editplan import EditPlan, SpanTarget, parse_target_id, validate_plan_params
from peditor.core.geometry import apply, contains
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, span
from peditor.worker.content import TextRun

POSITION_TOL = 0.01  # pt；溢出判定的數值容許


@dataclass
class _Pending:
    plan: EditPlan
    run: TextRun
    g0: int
    g1: int
    codes: list[int]
    compensation: float  # TJ 位移（千分之一字級）；0 表示不需補償


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
    if len(change.pieces) != 1:
        plan.unsupported_reasons.append("UNSUPPORTED_LAYOUT")
        plan.warnings.append("改動跨多段運算子尚未實作（P2 步驟 6）")
        return _store(document, plan, None)
    run = selection.runs[piece.run_index]
    if _shared_stream(document, selection.page_index, run):
        plan.unsupported_reasons.append("SHARED_RESOURCE_UNSAFE")
        return _store(document, plan, None)
    codes = run.font.encode(change.new_text, {g.code for g in run.glyphs}) if run.font else None
    if codes is None:
        plan.unsupported_reasons.append("GLYPH_MISSING")
        if params["policy"] == "prefer_a":
            plan.warnings.append("原字型缺字，需模式 B；模式 B 尚未實作（P2 步驟 7）")
        return _store(document, plan, None)

    old_codes = [g.code for g in run.glyphs[piece.g0 : piece.g1]]
    old_adv = sum(run.advance(c) for c in old_codes)
    new_adv = sum(run.advance(c) for c in codes)
    compensation = (new_adv - old_adv) * 1000.0 / run.size if run.size else 0.0
    if abs(compensation) < 1e-6:
        compensation = 0.0
    if compensation and run.operator in ("'", '"'):
        plan.unsupported_reasons.append("UNSUPPORTED_LAYOUT")  # 換行顯示運算子無法以 TJ 補償
        return _store(document, plan, None)

    start = _start_origin(run, piece.g0)
    a, b = run.matrix[0], run.matrix[1]
    end = (start[0] + new_adv / run.size * a, start[1] + new_adv / run.size * b)
    to_page = analyzer.page_geometry(document.pike.pages[selection.page_index]).pdf_to_page()
    page_start, page_end = apply(to_page, *start), apply(to_page, *end)
    plan.geometry = {
        "baseline_start": [round(v, 3) for v in page_start],
        "baseline_end": [round(v, 3) for v in page_end],
        "font_size": run.size,
        "pdfium_width_residual_pt": _truncation_residual(run, old_codes, codes),
    }
    if not all(contains(tuple(region), *p, tol=POSITION_TOL) for p in (page_start, page_end)):
        plan.unsupported_reasons.append("TEXT_OVERFLOW")
        return _store(document, plan, None)
    plan.mode = "A"
    plan.resource_changes = []
    return _store(document, plan, _Pending(plan, run, piece.g0, piece.g1, codes, compensation))


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
    _rewrite_mode_a(document, pending)
    document.commit()
    return {"new_revision": document.revision, "command_id": secrets.token_hex(8)}


def _rewrite_mode_a(document: analyzer.Document, pending: _Pending) -> None:
    run = pending.run
    stream = document.pike.get_object(run.stream)
    instructions = list(pikepdf.parse_content_stream(stream))
    inst = instructions[run.op_index]
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
    glyph_positions = [i for i, (kind, _) in enumerate(tokens) if kind == "g"]
    if [tokens[i][1] for i in glyph_positions] != [g.code for g in run.glyphs]:
        raise ProtocolError("VALIDATION_FAILED", "內容與計畫不一致")
    if pending.g0 < pending.g1:
        lo, hi = glyph_positions[pending.g0], glyph_positions[pending.g1 - 1] + 1
    else:  # 純插入
        lo = hi = glyph_positions[pending.g0] if pending.g0 < len(glyph_positions) else len(tokens)
    replaced = tokens[lo:hi]
    kept_numbers = [t for t in replaced if t[0] == "n"]  # 被替換字形之間原有的位移
    new_tokens = [("g", code) for code in pending.codes] + kept_numbers
    if pending.compensation:
        # TJ 數值 n 使位置移動 -n/1000×字級；n＝(新寬−舊寬)×1000/字級 抵銷字寬差
        new_tokens.append(("n", pending.compensation))
    tokens[lo:hi] = new_tokens
    array = _regroup(tokens, run.font.two_byte)
    if run.operator == "TJ" or len(array) != 1 or not isinstance(array[0], pikepdf.String):
        if run.operator in ("'", '"'):
            raise ProtocolError("VALIDATION_FAILED", "內容與計畫不一致")
        new_inst = pikepdf.ContentStreamInstruction([pikepdf.Array(array)], pikepdf.Operator("TJ"))
    else:
        new_inst = pikepdf.ContentStreamInstruction([*operands[:-1], array[0]], inst.operator)
    instructions[run.op_index] = new_inst
    stream.write(pikepdf.unparse_content_stream(instructions))


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
