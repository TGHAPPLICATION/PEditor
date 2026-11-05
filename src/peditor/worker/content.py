"""Content stream 直譯器：把每個字形對應到 stream 中的運算子（G1-08）。

逐一解析頁面（與 Form XObject）的 content stream，追蹤圖形狀態（CTM、clip）與文字狀態，
為每個 Tj／TJ／'／" 運算子記下字形的字碼、Unicode 與 PDF 空間原點；為每個影像 Do 記下 CTM 與 clip。
座標全部在 PDF 空間（CTM 之後、頁面 /Rotate 之前）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pikepdf

from peditor.core.geometry import IDENTITY, Matrix, apply, bbox_of, multiply
from peditor.core.limits import (
    MAX_CLIPS,
    MAX_CONTENT_OPERATORS,
    MAX_FORM_DEPTH,
    MAX_FORM_INVOCATIONS,
    MAX_GSTATE_DEPTH,
    MAX_IMAGE_PIXELS,
    MAX_PAINTED_POINTS,
    MAX_RULE_PATHS,
    LimitExceeded,
)
from peditor.worker import streams
from peditor.worker.fonts import FontInfo, load_font

TEXT_SHOW = frozenset({"Tj", "TJ", "'", '"'})
_PAINT = frozenset({"S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"})


@dataclass
class Glyph:
    code: int
    unicode: str | None
    origin: tuple[float, float]


@dataclass
class TextRun:
    """一個文字顯示運算子（occurrence）。"""

    stream: tuple[int, int]
    op_index: int
    operator: str
    font: FontInfo | None
    size: float
    matrix: Matrix  # 首字形的文字繪製矩陣（含 CTM）
    bt_index: int
    form_path: tuple[str, ...]
    actual_text: bool
    glyphs: list[Glyph] = field(default_factory=list)
    # 文字狀態（模式 A 依此計算字寬補償；ADR-0018 §2）
    char_space: float = 0.0
    word_space: float = 0.0
    scale: float = 1.0

    def advance(self, code: int) -> float:
        """字碼的水平位移（文字空間，未乘水平縮放），與 _show 的計算一致。"""
        if self.font is None:
            return 0.0
        tx = self.font.width(code) * self.size + self.char_space
        if code == 32 and not self.font.two_byte:
            tx += self.word_space
        return tx

    @property
    def text(self) -> str:
        return "".join(g.unicode or "�" for g in self.glyphs)


@dataclass
class Clip:
    bbox: tuple[float, float, float, float]
    is_rect: bool


@dataclass
class ImageUse:
    stream: tuple[int, int]
    op_index: int
    name: str
    xobject: pikepdf.Stream
    ctm: Matrix
    clips: list[Clip]
    form_path: tuple[str, ...]


@dataclass
class Stroke:
    """描邊的直線段（PDF 空間）與線寬；表格格線偵測用（P6、ADR-0023）。"""

    p0: tuple[float, float]
    p1: tuple[float, float]
    width: float
    form_path: tuple[str, ...]


@dataclass
class FilledRect:
    """填色的 `re` 矩形四角（PDF 空間）；細長者視為格線（Word 以細矩形畫框線）。"""

    corners: list[tuple[float, float]]
    form_path: tuple[str, ...]


@dataclass
class PaintedPath:
    """實際畫出的子路徑（描邊或填色，含曲線；曲線以控制點連成的折線表示，偏保守），PDF 空間。
    障礙線用（P6 第二輪核對 R1）：不論以何種方式畫，水平、垂直的邊都擋可改動區域，
    斜的邊使該區域拒絕。"""

    points: list[tuple[float, float]]
    closed: bool
    width: float  # 描邊線寬；只填色時為 0
    form_path: tuple[str, ...]


@dataclass
class PageContent:
    runs: list[TextRun] = field(default_factory=list)
    images: list[ImageUse] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # 解析失敗原因（不含原文）
    inline_images: int = 0
    strokes: list[Stroke] = field(default_factory=list)
    filled_rects: list[FilledRect] = field(default_factory=list)
    painted: list[PaintedPath] = field(default_factory=list)
    paths_truncated: bool = False  # 線段超過 MAX_RULE_PATHS：不再記錄，不做表格偵測


@dataclass
class _GState:
    ctm: Matrix = IDENTITY
    clips: list[Clip] = field(default_factory=list)
    font: FontInfo | None = None
    size: float = 0.0
    char_space: float = 0.0
    word_space: float = 0.0
    scale: float = 1.0
    leading: float = 0.0
    rise: float = 0.0
    line_width: float = 1.0

    def copy(self) -> _GState:
        new = _GState(**self.__dict__)
        new.clips = list(self.clips)
        return new


def _num(value) -> float:
    return float(value)


class _Interpreter:
    def __init__(self, page: pikepdf.Page) -> None:
        self.page = page
        self.result = PageContent()
        self.fonts: dict[tuple, FontInfo] = {}
        self.bt_count = 0
        self.operators = 0
        self.form_calls = 0
        self.painted_points = 0

    # --- 進入點 -------------------------------------------------------
    def run(self) -> PageContent:
        contents = self.page.obj.get("/Contents")
        parts = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
        gs = _GState()
        resources = self.page.obj.get("/Resources") or pikepdf.Dictionary()
        try:
            for stream in parts:
                if not isinstance(stream, pikepdf.Stream):
                    continue
                gs = self._execute(stream, resources, gs, ())
        except LimitExceeded as exc:  # 超過工作量上限：停止解析，由 analyzer 回報 RESOURCE_LIMIT
            self.result.errors.append(f"limit:{exc}")
        return self.result

    def _execute(self, stream, resources, gs: _GState, form_path) -> _GState:
        try:
            instructions = streams.parse(stream)  # 解壓前先檢查大小（P7、P2 triage f024）
        except pikepdf.PdfError:
            self.result.errors.append("content_parse")
            return gs
        key = stream.objgen
        stack: list[_GState] = []
        text_m: Matrix = IDENTITY
        line_m: Matrix = IDENTITY
        path: list[tuple[list[tuple[float, float]], bool, bool]] = []  # (點, 是否 re, 是否含曲線)
        pending_clip = False
        path_points = 0
        marked: list[bool] = []

        for index, inst in enumerate(instructions):
            if isinstance(inst, pikepdf.ContentStreamInlineImage):
                self.result.inline_images += 1
                continue
            op = str(inst.operator)
            ops = inst.operands
            self.operators += 1
            if self.operators > MAX_CONTENT_OPERATORS:
                raise LimitExceeded("operators")
            try:
                if op == "q":
                    if len(stack) >= MAX_GSTATE_DEPTH:
                        raise LimitExceeded("gstate_depth")
                    stack.append(gs.copy())
                elif op == "Q":
                    if stack:
                        gs = stack.pop()
                elif op == "cm":
                    gs.ctm = multiply(tuple(_num(v) for v in ops[:6]), gs.ctm)
                elif op in ("m", "l", "c", "v", "y", "re", "h"):
                    path_points += CURVE_STEPS if op in ("c", "v", "y") else 4 if op == "re" else 1
                    if (
                        path_points > MAX_PAINTED_POINTS
                    ):  # 未塗繪的路徑也不得無限累積（P7 掃描候選 5）
                        raise LimitExceeded("path_points")
                    self._path_op(op, ops, gs.ctm, path)
                elif op in ("W", "W*"):
                    pending_clip = True
                elif op == "w":
                    gs.line_width = _num(ops[0])
                elif op in _PAINT:
                    if op != "n" and path:
                        self._record_paths(op, path, gs, form_path)
                    if pending_clip and path:
                        if len(gs.clips) >= MAX_CLIPS:
                            raise LimitExceeded("clips")
                        gs.clips.append(_make_clip(path))
                    path, pending_clip, path_points = [], False, 0
                elif op == "BT":
                    self.bt_count += 1
                    text_m = line_m = IDENTITY
                elif op == "Tf":
                    gs.font = self._font(resources, ops[0])
                    gs.size = _num(ops[1])
                elif op == "Tc":
                    gs.char_space = _num(ops[0])
                elif op == "Tw":
                    gs.word_space = _num(ops[0])
                elif op == "Tz":
                    gs.scale = _num(ops[0]) / 100.0
                elif op == "TL":
                    gs.leading = _num(ops[0])
                elif op == "Ts":
                    gs.rise = _num(ops[0])
                elif op in ("Td", "TD"):
                    tx, ty = _num(ops[0]), _num(ops[1])
                    if op == "TD":
                        gs.leading = -ty
                    line_m = multiply((1, 0, 0, 1, tx, ty), line_m)
                    text_m = line_m
                elif op == "Tm":
                    line_m = text_m = tuple(_num(v) for v in ops[:6])
                elif op == "T*":
                    line_m = multiply((1, 0, 0, 1, 0, -gs.leading), line_m)
                    text_m = line_m
                elif op in TEXT_SHOW:
                    if op in ("'", '"'):
                        if op == '"':
                            gs.word_space, gs.char_space = _num(ops[0]), _num(ops[1])
                        line_m = multiply((1, 0, 0, 1, 0, -gs.leading), line_m)
                        text_m = line_m
                    items = ops[0] if op == "TJ" else ops[-1:]
                    text_m = self._show(key, index, op, items, gs, text_m, form_path, any(marked))
                elif op in ("BDC", "BMC"):
                    marked.append(op == "BDC" and _has_actual_text(ops, resources))
                elif op == "EMC":
                    if marked:
                        marked.pop()
                elif op == "Do":
                    self._do(key, index, ops[0], resources, gs, form_path)
            except (IndexError, TypeError, ValueError, pikepdf.PdfError):
                self.result.errors.append(f"operator:{op}")
        return gs

    # --- 文字 ---------------------------------------------------------
    def _font(self, resources, name) -> FontInfo | None:
        fonts = resources.get("/Font")
        font = fonts.get(name) if isinstance(fonts, pikepdf.Dictionary) else None
        if not isinstance(font, pikepdf.Dictionary):
            self.result.errors.append("font_missing")
            return None
        cache_key = (str(name), font.objgen if font.is_indirect else id(font))
        if cache_key not in self.fonts:
            for stream in _font_streams(font):  # MuPDF 擷取、渲染時也會解壓這些串流（P7）
                streams.check(stream)
            self.fonts[cache_key] = load_font(str(name), font)
        return self.fonts[cache_key]

    def _show(
        self, key, index, op, items, gs: _GState, text_m: Matrix, form_path, actual
    ) -> Matrix:
        font = gs.font
        render = (gs.size * gs.scale, 0.0, 0.0, gs.size, 0.0, gs.rise)
        run = TextRun(
            stream=key,
            op_index=index,
            operator=op,
            font=font,
            size=gs.size,
            matrix=multiply(multiply(render, text_m), gs.ctm),
            bt_index=self.bt_count,
            form_path=form_path,
            actual_text=actual,
            char_space=gs.char_space,
            word_space=gs.word_space,
            scale=gs.scale,
        )
        for item in items:
            if isinstance(item, pikepdf.String):
                if font is None:
                    continue
                for code in font.codes(bytes(item)):
                    trm = multiply(multiply(render, text_m), gs.ctm)
                    run.glyphs.append(Glyph(code, font.unicode(code), apply(trm, 0.0, 0.0)))
                    text_m = multiply((1, 0, 0, 1, run.advance(code) * gs.scale, 0), text_m)
            else:
                tx = -_num(item) / 1000.0 * gs.size * gs.scale
                text_m = multiply((1, 0, 0, 1, tx, 0), text_m)
        self.result.runs.append(run)
        return text_m

    # --- 路徑與 clip --------------------------------------------------
    def _record_paths(self, op, path, gs: _GState, form_path) -> None:
        """記錄描邊的直線段與填色矩形（不含曲線）；表格格線偵測用（ADR-0023）。"""
        stroke = op in ("S", "s", "B", "B*", "b", "b*")
        fill = op in ("f", "F", "f*", "B", "B*", "b", "b*")
        a, b, c, d, _, _ = gs.ctm
        width = abs(gs.line_width) * abs(a * d - b * c) ** 0.5
        for pts, is_re, curved, poly in path:
            self.painted_points += len(poly)
            if self.painted_points > MAX_PAINTED_POINTS:
                self.result.paths_truncated = True
                return
            closed = fill or is_re or op in ("s", "b", "b*")
            self.result.painted.append(
                PaintedPath(list(poly), closed, width if stroke else 0.0, form_path)
            )
            if curved:
                continue
            if len(self.result.strokes) + len(self.result.filled_rects) >= MAX_RULE_PATHS:
                self.result.paths_truncated = True
                return
            if fill and is_re:
                self.result.filled_rects.append(FilledRect(list(pts), form_path))
            if stroke:
                closed = is_re or op in ("s", "b", "b*")
                points = [*pts, pts[0]] if closed and len(pts) > 2 else pts
                for p0, p1 in zip(points, points[1:], strict=False):
                    self.result.strokes.append(Stroke(p0, p1, width, form_path))

    @staticmethod
    def _path_op(op, ops, ctm: Matrix, path) -> None:
        nums = [_num(v) for v in ops]
        if op == "re":
            x, y, w, h = nums[:4]
            pts = [
                apply(ctm, px, py) for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
            ]
            path.append((pts, True, False, list(pts)))
        elif op == "m":
            start = apply(ctm, nums[0], nums[1])
            path.append(([start], False, False, [start]))
        elif op == "h":
            return
        elif path:
            pts, is_re, curved, poly = path[-1]
            pts.append(apply(ctm, nums[-2], nums[-1]))
            # 障礙線用的折線：曲線細分成 CURVE_STEPS 段（第三輪核對 S1：控制點折線不一定碰到曲線）；
            # pts 只含端點（clip 判定沿用 P1 行為）
            points = [apply(ctm, nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            if op == "l" or not poly:
                poly.append(points[-1])
            else:
                start = poly[-1]
                c1, c2, end = {"c": points, "v": [start, *points], "y": [points[0], *points]}[op][
                    :3
                ]
                poly.extend(_bezier(start, c1, c2, end, k / CURVE_STEPS)
                            for k in range(1, CURVE_STEPS + 1))  # fmt: skip
            path[-1] = (pts, is_re, curved or op in ("c", "v", "y"), poly)

    # --- XObject ------------------------------------------------------
    def _do(self, key, index, name, resources, gs: _GState, form_path) -> None:
        xobjects = resources.get("/XObject")
        xobj = xobjects.get(name) if isinstance(xobjects, pikepdf.Dictionary) else None
        if not isinstance(xobj, pikepdf.Stream):
            self.result.errors.append("xobject_missing")
            return
        subtype = str(xobj.get("/Subtype", ""))
        if subtype == "/Image":
            if _num(xobj.get("/Width", 0)) * _num(xobj.get("/Height", 0)) > MAX_IMAGE_PIXELS:
                raise LimitExceeded("image_pixels")  # spec P7 單張影像 50 MP；MuPDF 渲染時才配置
            self.result.images.append(
                ImageUse(key, index, str(name), xobj, gs.ctm, list(gs.clips), form_path)
            )
        elif subtype == "/Form":
            if len(form_path) >= MAX_FORM_DEPTH or any(
                p.endswith(f"@{xobj.objgen}") for p in form_path
            ):
                self.result.errors.append("form_depth")
                return
            self.form_calls += 1
            if self.form_calls > MAX_FORM_INVOCATIONS:
                raise LimitExceeded("form_invocations")
            matrix = tuple(_num(v) for v in xobj.get("/Matrix", [1, 0, 0, 1, 0, 0]))
            inner = gs.copy()
            inner.ctm = multiply(matrix, gs.ctm)
            form_resources = xobj.get("/Resources") or resources
            self._execute(xobj, form_resources, inner, (*form_path, f"{name}@{xobj.objgen}"))


def _has_actual_text(ops, resources) -> bool:
    if len(ops) < 2:
        return False
    props = ops[1]
    if isinstance(props, pikepdf.Name):
        table = resources.get("/Properties")
        props = table.get(props) if isinstance(table, pikepdf.Dictionary) else None
    return isinstance(props, pikepdf.Dictionary) and "/ActualText" in props


CURVE_STEPS = 16  # 曲線細分段數（障礙線用）


def _bezier(p0, p1, p2, p3, s: float) -> tuple[float, float]:
    u = 1 - s
    w0, w1, w2, w3 = u**3, 3 * u * u * s, 3 * u * s * s, s**3
    return (w0 * p0[0] + w1 * p1[0] + w2 * p2[0] + w3 * p3[0],
            w0 * p0[1] + w1 * p1[1] + w2 * p2[1] + w3 * p3[1])  # fmt: skip


def _make_clip(path) -> Clip:
    points = [p for pts, *_ in path for p in pts]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    if len(path) != 1 or path[0][2]:
        return Clip(bbox, False)
    pts = path[0][0]
    tol = 0.01
    corners = {(round(x, 2), round(y, 2)) for x, y in pts}
    on_edges = all(
        (abs(x - bbox[0]) < tol or abs(x - bbox[2]) < tol)
        and (abs(y - bbox[1]) < tol or abs(y - bbox[3]) < tol)
        for x, y in pts
    )
    return Clip(bbox, on_edges and len(corners) == 4)


def _font_streams(font: pikepdf.Dictionary):
    """字型帶的串流：字型程式、ToUnicode、CIDToGIDMap、Type3 字形程序（MuPDF 會解壓）。"""
    holders = [font]
    descendants = font.get("/DescendantFonts")
    if isinstance(descendants, pikepdf.Array):
        holders += [d for d in descendants if isinstance(d, pikepdf.Dictionary)]
    for holder in holders:
        for key in ("/ToUnicode", "/CIDToGIDMap"):
            if isinstance(holder.get(key), pikepdf.Stream):
                yield holder.get(key)
        descriptor = holder.get("/FontDescriptor")
        if isinstance(descriptor, pikepdf.Dictionary):
            for key in ("/FontFile", "/FontFile2", "/FontFile3"):
                if isinstance(descriptor.get(key), pikepdf.Stream):
                    yield descriptor.get(key)
        procs = holder.get("/CharProcs")
        if isinstance(procs, pikepdf.Dictionary):
            yield from (v for v in procs.values() if isinstance(v, pikepdf.Stream))


def interpret(page: pikepdf.Page) -> PageContent:
    return _Interpreter(page).run()


def image_rect(use: ImageUse) -> tuple[float, float, float, float]:
    """影像單位正方形經 CTM 後的外接矩形（PDF 空間）。"""
    return bbox_of(use.ctm, (0.0, 0.0, 1.0, 1.0))
