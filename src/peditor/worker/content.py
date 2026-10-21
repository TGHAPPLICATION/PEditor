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
    LimitExceeded,
)
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
class PageContent:
    runs: list[TextRun] = field(default_factory=list)
    images: list[ImageUse] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # 解析失敗原因（不含原文）
    inline_images: int = 0


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

    # --- 進入點 -------------------------------------------------------
    def run(self) -> PageContent:
        contents = self.page.obj.get("/Contents")
        streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
        gs = _GState()
        resources = self.page.obj.get("/Resources") or pikepdf.Dictionary()
        try:
            for stream in streams:
                if not isinstance(stream, pikepdf.Stream):
                    continue
                gs = self._execute(stream, resources, gs, ())
        except LimitExceeded as exc:  # 超過工作量上限：停止解析，由 analyzer 回報 RESOURCE_LIMIT
            self.result.errors.append(f"limit:{exc}")
        return self.result

    def _execute(self, stream, resources, gs: _GState, form_path) -> _GState:
        try:
            instructions = pikepdf.parse_content_stream(stream)
        except pikepdf.PdfError:
            self.result.errors.append("content_parse")
            return gs
        key = stream.objgen
        stack: list[_GState] = []
        text_m: Matrix = IDENTITY
        line_m: Matrix = IDENTITY
        path: list[tuple[list[tuple[float, float]], bool, bool]] = []  # (點, 是否 re, 是否含曲線)
        pending_clip = False
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
                    self._path_op(op, ops, gs.ctm, path)
                elif op in ("W", "W*"):
                    pending_clip = True
                elif op in _PAINT:
                    if pending_clip and path:
                        if len(gs.clips) >= MAX_CLIPS:
                            raise LimitExceeded("clips")
                        gs.clips.append(_make_clip(path))
                    path, pending_clip = [], False
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
        )
        for item in items:
            if isinstance(item, pikepdf.String):
                if font is None:
                    continue
                for code in font.codes(bytes(item)):
                    trm = multiply(multiply(render, text_m), gs.ctm)
                    run.glyphs.append(Glyph(code, font.unicode(code), apply(trm, 0.0, 0.0)))
                    tx = font.width(code) * gs.size + gs.char_space
                    if code == 32 and not font.two_byte:
                        tx += gs.word_space
                    text_m = multiply((1, 0, 0, 1, tx * gs.scale, 0), text_m)
            else:
                tx = -_num(item) / 1000.0 * gs.size * gs.scale
                text_m = multiply((1, 0, 0, 1, tx, 0), text_m)
        self.result.runs.append(run)
        return text_m

    # --- 路徑與 clip --------------------------------------------------
    @staticmethod
    def _path_op(op, ops, ctm: Matrix, path) -> None:
        nums = [_num(v) for v in ops]
        if op == "re":
            x, y, w, h = nums[:4]
            pts = [
                apply(ctm, px, py) for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
            ]
            path.append((pts, True, False))
        elif op == "m":
            path.append(([apply(ctm, nums[0], nums[1])], False, False))
        elif op == "h":
            return
        elif path:
            pts, is_re, curved = path[-1]
            pts.append(apply(ctm, nums[-2], nums[-1]))
            path[-1] = (pts, is_re, curved or op in ("c", "v", "y"))

    # --- XObject ------------------------------------------------------
    def _do(self, key, index, name, resources, gs: _GState, form_path) -> None:
        xobjects = resources.get("/XObject")
        xobj = xobjects.get(name) if isinstance(xobjects, pikepdf.Dictionary) else None
        if not isinstance(xobj, pikepdf.Stream):
            self.result.errors.append("xobject_missing")
            return
        subtype = str(xobj.get("/Subtype", ""))
        if subtype == "/Image":
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


def _make_clip(path) -> Clip:
    points = [p for pts, _, _ in path for p in pts]
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


def interpret(page: pikepdf.Page) -> PageContent:
    return _Interpreter(page).run()


def image_rect(use: ImageUse) -> tuple[float, float, float, float]:
    """影像單位正方形經 CTM 後的外接矩形（PDF 空間）。"""
    return bbox_of(use.ctm, (0.0, 0.0, 1.0, 1.0))
