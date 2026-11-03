"""既有規則表格：由線條推估格線與儲存格（spec P6、G6；ADR-0023；只在 worker 使用）。

- 格線：頁面層級（不含 Form 內）的水平、垂直直線段——描邊線段、描邊的 `re`，
  以及厚度 ≤2 pt 的填色 `re`（Word 以細矩形畫框線）；換算到頁面空間後，
  同一位置（差 ≤1 pt）且相接（間隙 ≤1 pt）的片段合併成一條線。
- 表格：互相交會的水平線與垂直線為一組；線的位置構成網格。共用邊沒有線的相鄰網格合併；
  合併後為矩形且四邊都有線者為一格，跨多個網格的格（合併格）拒絕 `UNSUPPORTED_LAYOUT`。
- 格內文字：文字目標完整落在格內緣以內者屬於該格，依垂直位置分行；跨過格線的文字使該格拒絕；
  空白格拒絕（只修改既有文字，ADR-0023 §2）。
- 人工選格：使用者框選的範圍不能有線穿過、不能跨多個已偵測的格或碰到合併格，其餘判定同上。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from peditor.core.geometry import Matrix, apply
from peditor.core.limits import MAX_RULE_PAIRS, MAX_TABLE_CELLS
from peditor.worker.content import PageContent

MAX_THICKNESS = 2.0  # 填色矩形視為線的最大厚度（pt）
TOL = 1.0  # 同一條線的位置差、相接片段的間隙、線段涵蓋判定（pt）
TEXT_TOL = 0.5  # 文字外框落在格內緣的容許（pt）


@dataclass
class Line:
    horizontal: bool
    pos: float  # 水平線的 y、垂直線的 x（頁面空間）
    a: float  # 起點（水平線 x0、垂直線 y0）
    b: float
    width: float  # 線寬或細矩形厚度


@dataclass
class Rules:
    horizontal: list[Line]
    vertical: list[Line]
    truncated: bool = False  # 線段過多，未做偵測


def rules(content: PageContent, to_page: Matrix) -> Rules:
    """頁面層級的格線（合併後）。"""
    if content.paths_truncated:
        return Rules([], [], truncated=True)
    raw: list[Line] = []
    for stroke in content.strokes:
        if stroke.form_path:
            continue
        (x0, y0), (x1, y1) = apply(to_page, *stroke.p0), apply(to_page, *stroke.p1)
        if abs(y0 - y1) <= 0.01 and abs(x0 - x1) > 0.01:
            raw.append(Line(True, (y0 + y1) / 2, min(x0, x1), max(x0, x1), stroke.width))
        elif abs(x0 - x1) <= 0.01 and abs(y0 - y1) > 0.01:
            raw.append(Line(False, (x0 + x1) / 2, min(y0, y1), max(y0, y1), stroke.width))
    for rect in content.filled_rects:
        if rect.form_path:
            continue
        pts = [apply(to_page, *p) for p in rect.corners]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        if height <= MAX_THICKNESS and width > height:
            raw.append(Line(True, (min(ys) + max(ys)) / 2, min(xs), max(xs), height))
        elif width <= MAX_THICKNESS and height > width:
            raw.append(Line(False, (min(xs) + max(xs)) / 2, min(ys), max(ys), width))
    hs, vs = _merge([r for r in raw if r.horizontal]), _merge([r for r in raw if not r.horizontal])
    if len(hs) * len(vs) > MAX_RULE_PAIRS:  # 交會判定為平方級：線太多即不偵測
        return Rules([], [], truncated=True)
    return Rules(hs, vs)


def _merge(lines: list[Line]) -> list[Line]:
    """同一位置（差 ≤TOL）且相接（間隙 ≤TOL）的片段合併成一條。"""
    out: list[Line] = []
    for group in _clusters(sorted(lines, key=lambda line: line.pos), lambda line: line.pos):
        pos = sum(line.pos for line in group) / len(group)
        current: Line | None = None
        for line in sorted(group, key=lambda line: line.a):
            if current is not None and line.a <= current.b + TOL:
                current.b = max(current.b, line.b)
                current.width = max(current.width, line.width)
            else:
                current = Line(line.horizontal, pos, line.a, line.b, line.width)
                out.append(current)
    return out


def _clusters(items: list, key) -> list[list]:
    groups: list[list] = []
    for item in items:
        if groups and key(item) - key(groups[-1][0]) <= TOL:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


@dataclass
class Cell:
    table: int
    row: int
    col: int
    row_span: int
    col_span: int
    bbox: list[float]  # 格線中線圍成的範圍（頁面空間）
    inner: list[float]  # 扣掉半個線寬的格內緣


def detect(found: Rules) -> list[Cell]:
    """全部偵測到的格（含合併格）。"""
    hs, vs = found.horizontal, found.vertical
    parent = list(range(len(hs) + len(vs)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, h in enumerate(hs):
        for j, v in enumerate(vs):
            if h.a - TOL <= v.pos <= h.b + TOL and v.a - TOL <= h.pos <= v.b + TOL:
                parent[root(i)] = root(len(hs) + j)
    groups: dict[int, tuple[list[Line], list[Line]]] = {}
    for i, h in enumerate(hs):
        groups.setdefault(root(i), ([], []))[0].append(h)
    for j, v in enumerate(vs):
        groups.setdefault(root(len(hs) + j), ([], []))[1].append(v)
    tables = [g for g in groups.values() if len(g[0]) >= 2 and len(g[1]) >= 2]
    tables.sort(key=lambda g: (min(h.pos for h in g[0]), min(v.pos for v in g[1])))
    cells: list[Cell] = []
    for index, (t_hs, t_vs) in enumerate(tables):
        cells += _cells(index, t_hs, t_vs)
    return cells


def _positions(lines: list[Line]) -> list[float]:
    groups = _clusters(sorted(lines, key=lambda line: line.pos), lambda line: line.pos)
    return [sum(line.pos for line in g) / len(g) for g in groups]


def _covered(lines: list[Line], pos: float, a: float, b: float) -> Line | None:
    for line in lines:
        if abs(line.pos - pos) <= TOL and line.a <= a + TOL and line.b >= b - TOL:
            return line
    return None


def _cells(index: int, hs: list[Line], vs: list[Line]) -> list[Cell]:
    ys, xs = _positions(hs), _positions(vs)
    rows, cols = len(ys) - 1, len(xs) - 1
    if rows * cols > MAX_TABLE_CELLS:
        return []
    parent = list(range(rows * cols))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols and not _covered(vs, xs[c + 1], ys[r], ys[r + 1]):
                parent[root(r * cols + c)] = root(r * cols + c + 1)
            if r + 1 < rows and not _covered(hs, ys[r + 1], xs[c], xs[c + 1]):
                parent[root(r * cols + c)] = root((r + 1) * cols + c)
    regions: dict[int, list[tuple[int, int]]] = {}
    for r in range(rows):
        for c in range(cols):
            regions.setdefault(root(r * cols + c), []).append((r, c))
    out = []
    for units in regions.values():
        r0, r1 = min(u[0] for u in units), max(u[0] for u in units)
        c0, c1 = min(u[1] for u in units), max(u[1] for u in units)
        if len(units) != (r1 - r0 + 1) * (c1 - c0 + 1):
            continue  # 不是矩形
        top = [_covered(hs, ys[r0], xs[c], xs[c + 1]) for c in range(c0, c1 + 1)]
        bottom = [_covered(hs, ys[r1 + 1], xs[c], xs[c + 1]) for c in range(c0, c1 + 1)]
        left = [_covered(vs, xs[c0], ys[r], ys[r + 1]) for r in range(r0, r1 + 1)]
        right = [_covered(vs, xs[c1 + 1], ys[r], ys[r + 1]) for r in range(r0, r1 + 1)]
        if not all(top + bottom + left + right):
            continue  # 四邊沒有都畫線：不是格
        half = [max(line.width for line in side) / 2 for side in (left, top, right, bottom)]
        bbox = [xs[c0], ys[r0], xs[c1 + 1], ys[r1 + 1]]
        inner = [bbox[0] + half[0], bbox[1] + half[1], bbox[2] - half[2], bbox[3] - half[3]]
        out.append(Cell(index, r0, c0, r1 - r0 + 1, c1 - c0 + 1, bbox, inner))
    return sorted(out, key=lambda cell: (cell.row, cell.col))


def cell_id(revision: int, page_index: int, cell: Cell) -> str:
    """spec §7：含 revision、頁、表格、列欄與幾何 hash，不只是 bbox。"""
    key = ",".join(f"{v:.2f}" for v in cell.inner)
    digest = hashlib.sha256(key.encode("ascii")).hexdigest()[:12]
    return f"c:r{revision}:p{page_index}:t{cell.table}:{cell.row}.{cell.col}:g{digest}"


def _inside(bbox, box) -> bool:
    return (bbox[0] >= box[0] - TEXT_TOL and bbox[1] >= box[1] - TEXT_TOL
            and bbox[2] <= box[2] + TEXT_TOL and bbox[3] <= box[3] + TEXT_TOL)  # fmt: skip


def _overlaps(a, b, tol: float = 0.0) -> bool:
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def assess(box: list[float], text_targets: list[dict], reasons: list[str]) -> dict:
    """格內文字分行與能力判定。reasons 為此格已知的拒絕理由（文件層、合併格等）。"""
    reasons = list(reasons)
    members = []
    for target in text_targets:
        bbox = target.get("bbox")
        if not bbox or not _overlaps(bbox, box):
            continue
        if not _inside(bbox, box):
            reasons.append("UNSUPPORTED_LAYOUT")  # 文字跨過格線
            continue
        members.append(target)
        reasons += target["capability"]["reasons"]
    lines: list[list[dict]] = []
    for target in sorted(members, key=lambda t: (t["bbox"][1] + t["bbox"][3]) / 2):
        center = (target["bbox"][1] + target["bbox"][3]) / 2
        if lines:
            last = lines[-1][0]["bbox"]
            if abs(center - (last[1] + last[3]) / 2) <= (last[3] - last[1]) / 2:
                lines[-1].append(target)
                continue
        lines.append([target])
    out_lines = []
    for line in lines:
        line.sort(key=lambda t: t["bbox"][0])
        out_lines.append({
            "text": "".join(t["text"] for t in line),
            "target_ids": [t["target_id"] for t in line],
            "bbox": [min(t["bbox"][0] for t in line), min(t["bbox"][1] for t in line),
                     max(t["bbox"][2] for t in line), max(t["bbox"][3] for t in line)],
        })  # fmt: skip
    if not out_lines:
        reasons.append("UNSUPPORTED_LAYOUT")  # 空白格：只修改既有文字
    unique = list(dict.fromkeys(reasons))
    status = "reject" if unique else "support"
    return {"lines": out_lines, "empty": not out_lines,
            "capability": {"status": status, "reasons": unique}}  # fmt: skip


def cell_targets(cells: list[Cell], text_targets, revision, page_index, doc_reasons) -> list[dict]:
    out = []
    for cell in cells:
        reasons = list(doc_reasons)
        if cell.row_span > 1 or cell.col_span > 1:
            reasons.append("UNSUPPORTED_LAYOUT")  # 合併格（ADR-0013、ADR-0023）
        result = assess(cell.inner, text_targets, reasons)
        out.append({
            "cell_id": cell_id(revision, page_index, cell), "table": cell.table, "row": cell.row,
            "col": cell.col, "row_span": cell.row_span, "col_span": cell.col_span,
            "bbox": [round(v, 2) for v in cell.bbox],
            "inner_bbox": [round(v, 2) for v in cell.inner],
            **result,
        })  # fmt: skip
    return out


def assess_box(box, found: Rules, cells: list[Cell], text_targets, doc_reasons) -> dict:
    """人工選格（ADR-0023 §3）：框內不能有線穿過、不能跨多個已偵測的格或碰到合併格。"""
    reasons = list(doc_reasons)
    if found.truncated:
        reasons.append("RESOURCE_LIMIT")
    x0, y0, x1, y1 = box
    for line in found.horizontal:
        if y0 + TOL < line.pos < y1 - TOL and min(line.b, x1) - max(line.a, x0) > TOL:
            reasons.append("UNSUPPORTED_LAYOUT")
    for line in found.vertical:
        if x0 + TOL < line.pos < x1 - TOL and min(line.b, y1) - max(line.a, y0) > TOL:
            reasons.append("UNSUPPORTED_LAYOUT")
    touched = [c for c in cells if _overlaps(c.inner, box, TOL)]
    if len(touched) > 1 or any(c.row_span > 1 or c.col_span > 1 for c in touched):
        reasons.append("UNSUPPORTED_LAYOUT")
    return {"bbox": list(box), "inner_bbox": list(box), **assess(box, text_targets, reasons)}
