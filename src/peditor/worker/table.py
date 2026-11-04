"""既有規則表格：由線條推估格線與儲存格（spec P6、G6；ADR-0023；只在 worker 使用）。

- 格線：頁面層級（不含 Form 內）的水平、垂直直線段——描邊線段、描邊的 `re`，
  以及厚度 ≤2 pt 的填色 `re`（Word 以細矩形畫框線）；換算到頁面空間後，
  同一位置（差 ≤1 pt）且相接（間隙 ≤1 pt）的片段合併成一條線。
- 表格：互相交會的水平線與垂直線為一組；線的位置構成網格。共用邊沒有線的相鄰網格合併；
  合併後為矩形且四邊都有線者為一格，跨多個網格的格（合併格）拒絕 `UNSUPPORTED_LAYOUT`。
- 格內文字：文字目標完整落在格內緣以內者屬於該格，依垂直位置分行；跨過格線的文字使該格拒絕；
  空白格拒絕（只修改既有文字，ADR-0023 §2）。
- 人工選格：使用者框選的範圍不能有線穿過、不能跨多個已偵測的格或碰到合併格，其餘判定同上。
- 障礙線（P6 核對 Q1、Q2；第二輪 R1、R2）：頁面與 Form 內每一個實際畫出的子路徑
  （描邊或填色、`re` 或多邊形、含曲線——曲線以控制點連成的折線表示，偏保守）的邊；
  水平、垂直的邊為障礙線，斜的邊另存。格的偵測只用頁面層級的細格線；可改動區域裁到
  不碰任何障礙線、碰到斜邊即拒絕；人工框選與另存前比對也用障礙線。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from peditor.core.geometry import Matrix, apply
from peditor.core.limits import MAX_RULE_PAIRS, MAX_TABLE_CELLS
from peditor.worker.content import PageContent

MAX_THICKNESS = 2.0  # 填色矩形視為線的最大厚度（pt）
TOL = 1.0  # 同一條線的位置差、相接片段的間隙、線段涵蓋判定（pt）
TEXT_TOL = 0.5  # 文字外框落在格內緣的容許（pt）
THIN_SHAPE = 6.0  # 已繪製路徑外框厚度 ≤此值且長度超過厚度 3 倍時視為一條線（底線、細框線）


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
    obstacles: list[Line] = field(
        default_factory=list
    )  # 障礙線：已繪製路徑的水平、垂直邊（含 Form 內）
    diagonals: list[tuple] = field(default_factory=list)  # 已繪製路徑的斜邊 ((x0, y0), (x1, y1))


def _rect_line(pts, max_thickness: float) -> Line | None:
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    if height <= max_thickness and width > 3 * height:
        return Line(True, (min(ys) + max(ys)) / 2, min(xs), max(xs), height)
    if width <= max_thickness and height > 3 * width:
        return Line(False, (min(xs) + max(xs)) / 2, min(ys), max(ys), width)
    return None


def rules(content: PageContent, to_page: Matrix) -> Rules:
    """頁面層級的格線（合併後）與障礙線。"""
    if content.paths_truncated:
        return Rules([], [], truncated=True)
    grid: list[Line] = []
    for stroke in content.strokes:
        if stroke.form_path:
            continue
        line = _axis_line(apply(to_page, *stroke.p0), apply(to_page, *stroke.p1), stroke.width)
        if line is not None:
            grid.append(line)
    for rect in content.filled_rects:
        thin = None if rect.form_path else _rect_line([apply(to_page, *p) for p in rect.corners],
                                                      MAX_THICKNESS)  # fmt: skip
        if thin is not None:
            grid.append(thin)
    blocks: list[Line] = []
    diagonals: list[tuple] = []
    for painted in content.painted:
        pts = [apply(to_page, *p) for p in painted.points]
        thin = _rect_line(pts, THIN_SHAPE) if len(pts) > 1 else None
        if thin is not None:  # 細長的形狀（填色底線、細框線）整個視為一條線，不拆成四邊
            thin.width = max(thin.width, painted.width)
            blocks.append(thin)
            continue
        edges = list(zip(pts, pts[1:], strict=False))
        if painted.closed and len(pts) > 2:
            edges.append((pts[-1], pts[0]))
        for p0, p1 in edges:
            if abs(p0[0] - p1[0]) <= 0.01 and abs(p0[1] - p1[1]) <= 0.01:
                continue
            line = _axis_line(p0, p1, painted.width)
            if line is not None:
                blocks.append(line)
            else:
                diagonals.append((p0, p1))
    hs, vs = (
        _merge([r for r in grid if r.horizontal]),
        _merge([r for r in grid if not r.horizontal]),
    )
    if len(hs) * len(vs) > MAX_RULE_PAIRS:  # 交會判定為平方級：線太多即不偵測
        return Rules([], [], truncated=True)
    obstacles = _merge([r for r in blocks if r.horizontal]) + _merge(
        [r for r in blocks if not r.horizontal]
    )
    return Rules(hs, vs, obstacles=obstacles, diagonals=diagonals)


def _axis_line(p0, p1, width: float) -> Line | None:
    (x0, y0), (x1, y1) = p0, p1
    if abs(y0 - y1) <= 0.01 and abs(x0 - x1) > 0.01:
        return Line(True, (y0 + y1) / 2, min(x0, x1), max(x0, x1), width)
    if abs(x0 - x1) <= 0.01 and abs(y0 - y1) > 0.01:
        return Line(False, (x0 + x1) / 2, min(y0, y1), max(y0, y1), width)
    return None


def crosses(region, obstacles: list[Line]) -> bool:
    """區域內部（扣 TOL）有障礙線穿過；短段（點線）也算（第二輪核對 R1）。邊上的線不算。"""
    x0, y0, x1, y1 = region
    for line in obstacles:
        if line.horizontal:
            if y0 + TOL < line.pos < y1 - TOL and min(line.b, x1) - max(line.a, x0) > 0:
                return True
        elif x0 + TOL < line.pos < x1 - TOL and min(line.b, y1) - max(line.a, y0) > 0:
            return True
    return False


def hits_diagonal(region, diagonals) -> bool:
    """任一斜邊與區域內部相交（Liang–Barsky；第二輪核對 R2：斜線表頭等）。"""
    x0, y0, x1, y1 = region[0] + 0.01, region[1] + 0.01, region[2] - 0.01, region[3] - 0.01
    for (ax, ay), (bx, by) in diagonals:
        dx, dy = bx - ax, by - ay
        lo, hi = 0.0, 1.0
        for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
            if p == 0:
                if q < 0:
                    break
            elif p < 0:
                lo = max(lo, q / p)
            else:
                hi = min(hi, q / p)
        else:
            if lo <= hi:
                return True
    return False


def clip(region, text_bbox, obstacles: list[Line]) -> list[float] | None:
    """把可改動區域裁到不碰任何障礙線（P6 核對 Q1；第二輪核對 R3），依障礙線與文字的相對位置：

    - 與文字垂直範圍重疊（在文字旁邊）：
      - 也與文字水平範圍重疊：水平線（底線、刪除線）不擋——新文字只沿基線延伸；
        垂直線即穿過文字，回 None。
      - 在文字左或右：裁左右邊界到線為止（扣半個線寬）。
    - 不與文字垂直範圍重疊（在文字上或下）：裁上下邊界。
    """
    x0, y0, x1, y1 = region
    tx0, ty0, tx1, ty1 = text_bbox
    for line in obstacles:
        half = line.width / 2
        if line.horizontal:
            ox0, ox1, oy0, oy1 = line.a, line.b, line.pos - half, line.pos + half
        else:
            ox0, ox1, oy0, oy1 = line.pos - half, line.pos + half, line.a, line.b
        if not (ox0 < x1 + TOL and ox1 > x0 - TOL and oy0 < y1 + TOL and oy1 > y0 - TOL):
            continue  # 不碰區域
        beside = min(oy1, ty1 + TOL) - max(oy0, ty0 - TOL) > 0
        if beside:
            if min(ox1, tx1) - max(ox0, tx0) > 0:
                if line.horizontal:
                    continue  # 底線、刪除線
                return None  # 垂直線穿過文字
            if ox0 >= tx1:
                x1 = min(x1, ox0)
            else:
                x0 = max(x0, ox1)
        elif oy1 <= ty0:
            y0 = max(y0, oy1)
        else:
            y1 = min(y1, oy0)
    if x0 >= x1 or y0 >= y1:
        return None
    return [x0, y0, x1, y1]


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
    """格內文字分行與能力判定。reasons 為此格已知的結構性拒絕理由（文件層、合併格等）。

    格本身只因結構問題拒絕（合併格、跨格文字、空白格）；格內某段文字不支援時只擋它所在的行
    （P6 核對 Q3）。同一基線上間距大於一個字高的文字分成不同的行（片段）。
    """
    reasons = list(reasons)
    members, touching = [], []
    for target in text_targets:
        bbox = target.get("bbox")
        if not bbox or not _overlaps(bbox, box):
            continue
        touching.append(target["target_id"])
        if not _inside(bbox, box):
            reasons.append("UNSUPPORTED_LAYOUT")  # 文字跨過格線
            continue
        members.append(target)
    rows: list[list[dict]] = []
    for target in sorted(members, key=lambda t: (t["bbox"][1] + t["bbox"][3]) / 2):
        center = (target["bbox"][1] + target["bbox"][3]) / 2
        if rows:
            last = rows[-1][0]["bbox"]
            if abs(center - (last[1] + last[3]) / 2) <= (last[3] - last[1]) / 2:
                rows[-1].append(target)
                continue
        rows.append([target])
    segments: list[list[dict]] = []
    for row in rows:
        row.sort(key=lambda t: t["bbox"][0])
        em = max(t["bbox"][3] - t["bbox"][1] for t in row)
        segments.append([row[0]])
        for target in row[1:]:
            if target["bbox"][0] - max(t["bbox"][2] for t in segments[-1]) > em:
                segments.append([target])
            else:
                segments[-1].append(target)
    out_lines = []
    for line in segments:
        line_reasons = list(dict.fromkeys(r for t in line for r in t["capability"]["reasons"]))
        out_lines.append({
            "text": "".join(t["text"] for t in line),
            "target_ids": [t["target_id"] for t in line],
            "bbox": [min(t["bbox"][0] for t in line), min(t["bbox"][1] for t in line),
                     max(t["bbox"][2] for t in line), max(t["bbox"][3] for t in line)],
            "capability": {"status": "reject" if line_reasons else "support",
                           "reasons": line_reasons},
        })  # fmt: skip
    if not out_lines:
        reasons.append("UNSUPPORTED_LAYOUT")  # 空白格：只修改既有文字
    unique = list(dict.fromkeys(reasons))
    status = "reject" if unique else "support"
    return {"lines": out_lines, "empty": not out_lines, "text_ids": touching,
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
    # 框內不能有障礙線或斜邊（含 Form 內；第一輪 Q2、第二輪 R1、R2）
    if crosses(box, found.obstacles) or hits_diagonal(box, found.diagonals):
        reasons.append("UNSUPPORTED_LAYOUT")
    touched = [c for c in cells if _overlaps(c.inner, box, TOL)]
    if len(touched) > 1 or any(c.row_span > 1 or c.col_span > 1 for c in touched):
        reasons.append("UNSUPPORTED_LAYOUT")
    return {"bbox": list(box), "inner_bbox": list(box), **assess(box, text_targets, reasons)}
