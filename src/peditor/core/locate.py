"""在 inspect_page 的文字目標中找字串（不分空白），回傳對應的目標與字形位置。

只比對 content stream 順序串接後的字形 Unicode；找不到時回空串列，不以 bbox 猜測。
"""

from __future__ import annotations

from typing import Any

Span = list[tuple[int, int]]  # [(text_targets 索引, 該目標 glyphs 索引), ...]


def find_text(text_targets: list[dict[str, Any]], text: str) -> list[Span]:
    wanted = "".join(text.split())
    if not wanted:
        return []
    sequence: list[tuple[str, int, int]] = []
    for ti, target in enumerate(text_targets):
        for gi, glyph in enumerate(target["glyphs"]):
            for ch in glyph["c"] or "�":
                sequence.append((ch, ti, gi))
    joined = "".join(ch for ch, _, _ in sequence)
    spans, start = [], joined.find(wanted)
    while start >= 0:
        refs = dict.fromkeys((ti, gi) for _, ti, gi in sequence[start : start + len(wanted)])
        spans.append(list(refs))
        start = joined.find(wanted, start + 1)
    return spans


def span_capability(text_targets: list[dict[str, Any]], span: Span) -> dict[str, Any]:
    """span 涵蓋的所有目標的能力合併：任一目標有理由碼即不可編輯。"""
    reasons: list[str] = []
    for ti in dict.fromkeys(ti for ti, _ in span):
        reasons += text_targets[ti]["capability"]["reasons"]
    unique = list(dict.fromkeys(reasons))
    status = "support" if not unique else ("readonly" if unique == ["NO_TEXT_LAYER"] else "reject")
    return {"status": status, "reasons": unique}


def span_bbox(text_targets: list[dict[str, Any]], span: Span) -> list[float] | None:
    boxes = [text_targets[ti]["glyphs"][gi]["bbox"] for ti, gi in span]
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]  # fmt: skip
