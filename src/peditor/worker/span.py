"""span target 解析與實際改動範圍（ADR-0018 §1；只在 worker 使用）。

選取範圍：同頁、同一 content stream、同一 Form 路徑、在內容順序中連續的文字運算子。
實際改動範圍：去掉選取文字與新文相同的開頭、結尾後，向外擴到字形邊界；
只能涉及同一 BT 內相鄰的運算子，
且涉及的每一段能力都必須是 support。
"""

from __future__ import annotations

from dataclasses import dataclass

from peditor.core.editplan import SpanTarget, common_affixes
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer
from peditor.worker.content import TextRun


@dataclass(frozen=True)
class Piece:
    """一段文字運算子中的字形範圍 [g0, g1)；g0 == g1 表示插入點。"""

    run_index: int
    target: dict
    g0: int
    g1: int


@dataclass(frozen=True)
class Selection:
    page_index: int
    runs: list[TextRun]
    pieces: list[Piece]

    @property
    def text(self) -> str:
        return "".join(_chars(self.runs[p.run_index], p.g0, p.g1) for p in self.pieces)


@dataclass(frozen=True)
class Change:
    """實際改動：pieces 為被替換的字形（純插入時為單一插入點），old／new 為對應文字。"""

    pieces: list[Piece]
    old_text: str
    new_text: str
    reasons: list[str]


def _glyph_text(run: TextRun, index: int) -> str:
    return run.glyphs[index].unicode or "�"


def _chars(run: TextRun, g0: int, g1: int) -> str:
    return "".join(_glyph_text(run, i) for i in range(g0, g1))


def _glyph_at(run: TextRun, char_offset: int) -> int:
    """字元位移所在的字形邊界索引；不在邊界（切開連字）回 UNSUPPORTED_ENCODING。"""
    pos = 0
    for i in range(len(run.glyphs) + 1):
        if pos == char_offset:
            return i
        if i == len(run.glyphs) or pos > char_offset:
            break
        pos += len(_glyph_text(run, i))
    raise ProtocolError("UNSUPPORTED_ENCODING", "字元範圍未落在字形邊界")


def resolve(document: analyzer.Document, span: SpanTarget) -> Selection:
    if span.revision != document.revision:
        raise ProtocolError("REVISION_CONFLICT", "文件版本已變更")
    page = analyzer.inspect_page(document, span.page_index)
    runs, index = document.runs[span.page_index]
    targets = {t["target_id"]: t for t in page["text_targets"]}
    if any(p not in targets for p in span.parts):
        raise ProtocolError("INVALID_REQUEST", "目標不存在")
    positions = [index[p] for p in span.parts]
    first = runs[positions[0]]
    if positions != list(range(positions[0], positions[0] + len(positions))) or any(
        runs[i].stream != first.stream or runs[i].form_path != first.form_path for i in positions
    ):
        raise ProtocolError("UNSUPPORTED_LAYOUT", "選取範圍的文字運算子不連續")
    pieces = []
    for n, (part, i) in enumerate(zip(span.parts, positions, strict=True)):
        g0 = _glyph_at(runs[i], span.start) if n == 0 else 0
        g1 = _glyph_at(runs[i], span.end) if n == len(positions) - 1 else len(runs[i].glyphs)
        if g0 > g1:
            raise ProtocolError("INVALID_REQUEST", "字元範圍錯誤")
        pieces.append(Piece(i, targets[part], g0, g1))
    return Selection(span.page_index, runs, pieces)


def find(
    document: analyzer.Document, page_index: int, text: str, occurrence: int = 0
) -> SpanTarget:
    """以內容（非 bbox）在同一 content stream 連續的文字運算子中尋找第 occurrence 個 text。"""
    if not text:
        raise ProtocolError("INVALID_REQUEST", "搜尋文字為空")
    analyzer.inspect_page(document, page_index)
    runs, index = document.runs[page_index]
    ids = {i: tid for tid, i in index.items()}
    found = 0
    for start in sorted(ids):
        joined, owners, i = "", [], start
        while (i in ids and runs[i].stream == runs[start].stream
               and len(joined) < len(runs[start].text) + len(text)):  # fmt: skip
            owners.append((i, len(joined)))
            joined += runs[i].text
            i += 1
        # 只計起點落在第一段的出現，同一出現不會被不同起點重複計數
        pos = joined.find(text)
        while pos != -1 and pos < len(runs[start].text):
            if found == occurrence:
                end = pos + len(text)
                parts = [(ids[j], off) for j, off in owners if off < end]
                return SpanTarget(tuple(p for p, _ in parts), pos, end - parts[-1][1])
            found += 1
            pos = joined.find(text, pos + 1)
    raise ProtocolError("INVALID_REQUEST", "找不到指定文字")


def change(selection: Selection, new_text: str) -> Change:
    """去掉相同開頭、結尾，得到實際改動範圍並檢查 BT 與能力（ADR-0018 §1）。"""
    old = selection.text
    if old == new_text:
        raise ProtocolError("INVALID_REQUEST", "新文字與原文相同")
    prefix, suffix = common_affixes(old, new_text)
    # 選取範圍內每個字形的（piece, 字形索引, 字元起點, 字元終點）
    glyphs, pos = [], 0
    for piece in selection.pieces:
        run = selection.runs[piece.run_index]
        for g in range(piece.g0, piece.g1):
            width = len(_glyph_text(run, g))
            glyphs.append((piece, g, pos, pos + width))
            pos += width
    lo, hi = prefix, len(old) - suffix
    if lo == hi and lo not in {0, *(item[3] for item in glyphs)}:
        # 插入點落在連字字形中間：改為替換該字形（前後仍是相同的開頭、結尾）
        containing = next(item for item in glyphs if item[2] < lo < item[3])
        lo, hi = containing[2], containing[3]
    if lo < hi:
        hit = [item for item in glyphs if item[3] > lo and item[2] < hi]
        lo, hi = hit[0][2], hit[-1][3]  # 向外擴到字形邊界
        pieces: dict[int, list] = {}
        for piece, g, _, _ in hit:
            pieces.setdefault(piece.run_index, [piece, g, g])[2] = g
        changed = [Piece(p.run_index, p.target, g0, g1 + 1) for p, g0, g1 in pieces.values()]
    elif prefix:  # 純插入：錨定在相同開頭最後一個字形之後
        piece, g, _, end = next(item for item in glyphs if item[3] == lo)
        changed = [Piece(piece.run_index, piece.target, g + 1, g + 1)]
        lo = hi = end
    else:  # 沒有相同開頭：錨定在相同結尾第一個字形之前
        piece, g, start, _ = glyphs[0]
        changed = [Piece(piece.run_index, piece.target, g, g)]
        lo = hi = start
    reasons: list[str] = []
    runs = [selection.runs[p.run_index] for p in changed]
    indices = [p.run_index for p in changed]
    adjacent = indices == list(range(indices[0], indices[0] + len(indices)))
    if len({r.bt_index for r in runs}) != 1 or not adjacent:
        reasons.append("UNSUPPORTED_LAYOUT")
    for piece in changed:
        reasons += piece.target["capability"]["reasons"]
    new_part = new_text[lo : len(new_text) - (len(old) - hi)]
    return Change(changed, old[lo:hi], new_part, list(dict.fromkeys(reasons)))
