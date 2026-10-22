"""文件開啟、文件旗標與頁面能力判定（只在 worker 使用；spec P1、§4、ADR-0007）。

能力判定只依可驗證的結構性質，不依檔名或 manifest：
- 文件層：加密、損毀／需修復、數位簽章、PDF/A、XFA、主動內容 → 整份拒絕。
- 頁面層：沒有任何文字目標（掃描、輪廓文字、純圖片頁）→ 文字唯讀；影像目標各自判定。
- 目標層：每個文字顯示運算子與影像 Do 各為一個目標，字形須對應到 content stream 且與
  PyMuPDF 擷取的字元位置（≤0.5 pt）及 Unicode 一致，才可能判為支援。
"""

from __future__ import annotations

import base64
import hashlib
import io
import secrets
from dataclasses import dataclass, field

import pikepdf
import pymupdf

from peditor.core.geometry import PageGeometry, apply, bbox_of
from peditor.core.limits import (
    MAX_FILE_BYTES,
    MAX_OBJECT_WALK,
    MAX_PAGES,
    MAX_RENDER_DPI,
    MAX_RENDER_PIXELS,
    LimitExceeded,
)
from peditor.core.protocol import ProtocolError
from peditor.worker import fonts as fontmod
from peditor.worker.content import PageContent, TextRun, image_rect, interpret

LOCATE_TOL = 0.5  # G1：字形定位與 PyMuPDF 擷取位置的容許誤差（pt）
_SUPPORTED_IMAGE_FILTERS = frozenset({"/DCTDecode", "/FlateDecode"})

pymupdf.TOOLS.mupdf_display_errors(False)
pymupdf.TOOLS.mupdf_display_warnings(False)


@dataclass
class Document:
    document_id: str
    sha256: str
    revision: int
    page_count: int
    flags: dict
    pike: pikepdf.Pdf | None = None
    mu: pymupdf.Document | None = None
    pages: dict[int, dict] = field(default_factory=dict)
    # 每頁全部文字運算子（含不可見）與 target_id → 索引；供 span 解析（ADR-0018），不回傳給呼叫端
    runs: dict[int, tuple[list[TextRun], dict[str, int]]] = field(default_factory=dict)
    plans: dict[str, object] = field(default_factory=dict)  # plan_id → 待套用的計畫（worker 內部）
    original: bytes = b""  # 開啟時的檔案內容（另存驗證的 qpdf 基準與內容差異；spec §8.1、§8.2）

    @property
    def doc_reasons(self) -> list[str]:
        return list(self.flags["reasons"])

    def close(self) -> None:
        if self.mu is not None:
            self.mu.close()
        if self.pike is not None:
            self.pike.close()

    def working_bytes(self) -> bytes:
        """工作文件完整重寫後的位元組（不含增量更新；spec §8.1-4）。"""
        buf = io.BytesIO()
        self.pike.save(
            buf, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.preserve
        )
        return buf.getvalue()

    def commit(self) -> None:
        """套用修改後：以重寫結果重新開啟、revision 加一、清除依舊版本建立的快取與計畫。"""
        data = self.working_bytes()
        self.close()
        self.pike = pikepdf.open(io.BytesIO(data))
        self.mu = pymupdf.open(stream=data, filetype="pdf")
        self.revision += 1
        self.pages.clear()
        self.runs.clear()
        self.plans.clear()


def open_document(path: str) -> Document:
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise ProtocolError("INVALID_REQUEST", "無法讀取檔案") from exc
    if len(data) > MAX_FILE_BYTES:
        raise ProtocolError("RESOURCE_LIMIT", "檔案超過大小上限")
    digest = hashlib.sha256(data).hexdigest()
    reasons: list[str] = []
    flags: dict = {"encrypted": False, "repaired": False, "signed": False, "pdfa": False,
                   "xfa": False, "active_content": [], "tagged": False}  # fmt: skip

    mu = None
    try:
        mu = pymupdf.open(stream=data, filetype="pdf")
    except Exception:  # noqa: BLE001 — MuPDF 對畸形檔拋出多種例外
        reasons.append("MALFORMED_DOCUMENT")
    # 只有 owner 密碼（user 密碼為空）的檔案 needs_pass 為假，仍須判為加密（P1 安全掃描 f003）
    if mu is not None and (mu.needs_pass or (mu.metadata or {}).get("encryption")):
        flags["encrypted"] = True
        mu.close()
        return _doc(digest, 0, flags, ["ENCRYPTED_DOCUMENT"])
    if mu is not None and mu.is_repaired:
        flags["repaired"] = True
        reasons.append("MALFORMED_DOCUMENT")

    pike = None
    try:
        pike = pikepdf.open(io.BytesIO(data))
        if pike.is_encrypted:  # f003：MuPDF 無法開啟時仍由 pikepdf 判定
            flags["encrypted"] = True
            pike.close()
            if mu is not None:
                mu.close()
            return _doc(digest, 0, flags, ["ENCRYPTED_DOCUMENT"])
        if pike.get_warnings():
            flags["repaired"] = True
            reasons.append("MALFORMED_DOCUMENT")
    except pikepdf.PasswordError:
        flags["encrypted"] = True
        return _doc(digest, 0, flags, ["ENCRYPTED_DOCUMENT"])
    except pikepdf.PdfError:
        reasons.append("MALFORMED_DOCUMENT")

    page_count = mu.page_count if mu is not None else 0
    if page_count > MAX_PAGES:
        if mu is not None:
            mu.close()
        if pike is not None:
            pike.close()
        return _doc(digest, page_count, flags, ["RESOURCE_LIMIT"])
    if pike is not None:
        try:
            _document_features(pike, flags, reasons)
        except LimitExceeded:  # 表單／書籤樹過大或有大量共享節點（P1 安全掃描 f009）
            reasons.append("RESOURCE_LIMIT")
    document = _doc(digest, page_count, flags, reasons)
    document.pike, document.mu, document.original = pike, mu, data
    return document


def _doc(digest: str, page_count: int, flags: dict, reasons: list[str]) -> Document:
    unique = list(dict.fromkeys(reasons))
    flags = {**flags, "status": "reject" if unique else "support", "reasons": unique}
    return Document(secrets.token_hex(8), digest, 0, page_count, flags)


def _document_features(pdf: pikepdf.Pdf, flags: dict, reasons: list[str]) -> None:
    root = pdf.Root
    acroform = root.get("/AcroForm")
    if isinstance(acroform, pikepdf.Dictionary):
        if "/XFA" in acroform:
            flags["xfa"] = True
            reasons.append("UNSUPPORTED_FEATURE")
        fields = list(_fields(acroform.get("/Fields", [])))
        if any(_is_signed(f) for f in fields):
            flags["signed"] = True
            reasons.append("SIGNED_DOCUMENT")
    # 未列在 /AcroForm/Fields 的簽章 widget 也要判定（P1 安全掃描 f008）
    widgets = [annot for page in pdf.pages for annot in page.obj.get("/Annots", [])
               if isinstance(annot, pikepdf.Dictionary)
               and str(annot.get("/Subtype", "")) == "/Widget"]  # fmt: skip
    if any(_is_signed(w) for w in widgets):
        flags["signed"] = True
        reasons.append("SIGNED_DOCUMENT")
    if "/Perms" in root:
        flags["signed"] = True
        reasons.append("SIGNED_DOCUMENT")
    try:
        pdfa = pdf.open_metadata().get("pdfaid:part") is not None
    except Exception:  # noqa: BLE001 — XMP 畸形時不阻擋其他判定
        pdfa = False
    if pdfa:
        flags["pdfa"] = True
        reasons.append("UNSUPPORTED_FEATURE")
    flags["tagged"] = "/StructTreeRoot" in root
    active = _active_content(pdf)
    if active:
        flags["active_content"] = active
        reasons.append("ACTIVE_CONTENT")


def _fields(fields):
    """表單欄位樹；共享或自我參照的 /Kids 只走一次，節點數有上限（P1 安全掃描 f009）。"""
    seen: set = set()
    stack = [iter(fields)]
    count = 0
    while stack:
        field_ = next(stack[-1], None)
        if field_ is None:
            stack.pop()
            continue
        if not isinstance(field_, pikepdf.Dictionary):
            continue
        if field_.is_indirect:
            if field_.objgen in seen:
                continue
            seen.add(field_.objgen)
        count += 1
        if count > MAX_OBJECT_WALK or len(stack) > 64:
            raise LimitExceeded("fields")
        yield field_
        kids = field_.get("/Kids")
        if isinstance(kids, pikepdf.Array):
            stack.append(iter(kids))


def _inherited(node: pikepdf.Dictionary, key: str):
    """可繼承的欄位屬性（/FT、/V）沿 /Parent 往上找；鏈長有上限並略過循環（P1 安全掃描 f008）。"""
    seen: set = set()
    for _ in range(64):
        if not isinstance(node, pikepdf.Dictionary):
            return None
        if key in node:
            return node.get(key)
        if node.is_indirect:
            if node.objgen in seen:
                return None
            seen.add(node.objgen)
        node = node.get("/Parent")
    raise LimitExceeded("field parent chain")


def _is_signed(field_: pikepdf.Dictionary) -> bool:
    return str(_inherited(field_, "/FT") or "") == "/Sig" and isinstance(
        _inherited(field_, "/V"), pikepdf.Dictionary
    )


def _action_kinds(action, seen: set, depth: int = 0) -> set[str]:
    if not isinstance(action, pikepdf.Dictionary) or depth > 16:
        return set()
    key = action.objgen if action.is_indirect else None
    if key is not None:
        if key in seen:
            return set()
        seen.add(key)
    kinds = set()
    kind = str(action.get("/S", ""))
    if kind in _ACTIVE_ACTIONS:
        kinds.add(kind.lstrip("/"))
    nxt = action.get("/Next")
    for item in nxt if isinstance(nxt, pikepdf.Array) else [nxt]:
        kinds |= _action_kinds(item, seen, depth + 1)
    return kinds


# ADR-0007 的主動內容：會執行程式、開啟外部程式／檔案、送出或匯入資料、播放多媒體的動作。
# 文件內跳頁（GoTo）與超連結（URI，產品不自動開啟）不在此列。
_ACTIVE_ACTIONS = frozenset({"/JavaScript", "/Launch", "/SubmitForm", "/ImportData", "/GoToE",
                             "/Rendition", "/RichMediaExecute"})  # fmt: skip
_ACTIVE_ANNOTS = {"/FileAttachment": "EmbeddedFile", "/RichMedia": "Multimedia",
                  "/Screen": "Multimedia", "/Movie": "Multimedia", "/Sound": "Multimedia",
                  "/3D": "Multimedia"}  # fmt: skip


def _aa_kinds(holder, seen: set) -> set[str]:
    kinds: set[str] = set()
    kinds |= _action_kinds(holder.get("/A"), seen)
    aa = holder.get("/AA")
    if isinstance(aa, pikepdf.Dictionary):
        for value in aa.values():
            kinds |= _action_kinds(value, seen)
    return kinds


def _outline_items(root):
    """書籤樹（/First、/Next）；走訪節點數有上限並略過循環。"""
    outlines = root.get("/Outlines")
    if not isinstance(outlines, pikepdf.Dictionary):
        return
    seen: set = set()
    stack = [outlines.get("/First")]
    count = 0
    while stack:
        item = stack.pop()
        if not isinstance(item, pikepdf.Dictionary):
            continue
        if item.is_indirect:
            if item.objgen in seen:
                continue
            seen.add(item.objgen)
        count += 1
        if count > MAX_OBJECT_WALK:
            raise LimitExceeded("outlines")
        yield item
        stack.extend([item.get("/Next"), item.get("/First")])


def _active_content(pdf: pikepdf.Pdf) -> list[str]:
    """P1 安全掃描 f007：另走訪書籤、表單欄位（含非 widget 的父欄位）的 /A 與 /AA。"""
    root = pdf.Root
    seen: set = set()
    kinds = _action_kinds(root.get("/OpenAction"), seen)
    for item in _outline_items(root):
        kinds |= _action_kinds(item.get("/A"), seen)
    acroform = root.get("/AcroForm")
    if isinstance(acroform, pikepdf.Dictionary):
        for field_ in _fields(acroform.get("/Fields", [])):
            kinds |= _aa_kinds(field_, seen)
    for holder in [root, *[p.obj for p in pdf.pages]]:
        aa = holder.get("/AA")
        if isinstance(aa, pikepdf.Dictionary):
            for value in aa.values():
                kinds |= _action_kinds(value, seen)
    names = root.get("/Names")
    if isinstance(names, pikepdf.Dictionary):
        if "/JavaScript" in names:
            kinds.add("JavaScript")
        if "/EmbeddedFiles" in names:
            kinds.add("EmbeddedFile")
    for page in pdf.pages:
        for annot in page.obj.get("/Annots", []):
            if not isinstance(annot, pikepdf.Dictionary):
                continue
            subtype = str(annot.get("/Subtype", ""))
            if subtype in _ACTIVE_ANNOTS:
                kinds.add(_ACTIVE_ANNOTS[subtype])
            kinds |= _aa_kinds(annot, seen)
    return sorted(kinds)


# --- 頁面 ---------------------------------------------------------------


def _require_pages(document: Document) -> None:
    if document.flags["encrypted"]:
        raise ProtocolError("ENCRYPTED_DOCUMENT", "文件已加密")
    if document.page_count > MAX_PAGES:
        raise ProtocolError("RESOURCE_LIMIT", "頁數超過上限")
    if document.pike is None or document.mu is None:
        raise ProtocolError("MALFORMED_DOCUMENT", "文件結構無法解析")


def _check_index(document: Document, page_index) -> int:
    if not isinstance(page_index, int) or not 0 <= page_index < document.page_count:
        raise ProtocolError("INVALID_REQUEST", "頁碼超出範圍")
    return page_index


def page_geometry(pike_page: pikepdf.Page) -> PageGeometry:
    media = [float(v) for v in pike_page.mediabox]
    crop = [float(v) for v in pike_page.obj.get("/CropBox", pike_page.mediabox)]
    media = [min(media[0], media[2]), min(media[1], media[3]), max(media[0], media[2]),
             max(media[1], media[3])]  # fmt: skip
    crop = [max(min(crop[0], crop[2]), media[0]), max(min(crop[1], crop[3]), media[1]),
            min(max(crop[0], crop[2]), media[2]), min(max(crop[1], crop[3]), media[3])]  # fmt: skip
    return PageGeometry(tuple(crop), int(pike_page.obj.get("/Rotate", 0)))


def inspect_page(document: Document, page_index) -> dict:
    _require_pages(document)
    page_index = _check_index(document, page_index)
    if page_index not in document.pages:
        document.pages[page_index] = _analyze_page(document, page_index)
    return document.pages[page_index]


def assess_editability(document: Document) -> dict:
    result = {
        "document": {"status": document.flags["status"], "reasons": document.doc_reasons},
        "pages": [],
    }
    try:
        _require_pages(document)
    except ProtocolError:
        return result
    for index in range(document.page_count):
        page = inspect_page(document, index)
        result["pages"].append({"page_index": index, **page["capabilities"]})
    return result


def render_page(document: Document, page_index, dpi) -> dict:
    _require_pages(document)
    page_index = _check_index(document, page_index)
    if not isinstance(dpi, int) or not 18 <= dpi <= MAX_RENDER_DPI:
        raise ProtocolError("INVALID_REQUEST", "DPI 超出範圍")
    rect = document.mu[page_index].rect
    if rect.width * rect.height * (dpi / 72) ** 2 > MAX_RENDER_PIXELS:  # P1 安全掃描 f016
        raise ProtocolError("RESOURCE_LIMIT", "頁面渲染尺寸超過上限")
    pix = document.mu[page_index].get_pixmap(dpi=dpi)
    return {"width": pix.width, "height": pix.height,
            "png_base64": base64.b64encode(pix.tobytes("png")).decode("ascii")}  # fmt: skip


def _chars(mu_page: pymupdf.Page) -> dict[tuple[int, int], list[dict]]:
    """PyMuPDF 擷取字元，依原點以 1 pt 格子分桶。"""
    grid: dict[tuple[int, int], list[dict]] = {}
    for block in mu_page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for ch in span["chars"]:
                    x, y = ch["origin"]
                    grid.setdefault((round(x), round(y)), []).append(ch)
    return grid


def _match(grid, x: float, y: float, unicode: str | None) -> tuple[dict | None, bool]:
    """回傳（位置吻合的字元, Unicode 是否一致）。"""
    best, best_d = None, LOCATE_TOL
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for ch in grid.get((round(x) + dx, round(y) + dy), []):
                d = max(abs(ch["origin"][0] - x), abs(ch["origin"][1] - y))
                if d <= best_d and (best is None or ch["c"] == unicode or best["c"] != unicode):
                    best, best_d = ch, d
    return best, best is not None and best["c"] == unicode


def _upright(matrix) -> bool:
    a, b, c, d, _, _ = matrix
    scale = max(abs(a), abs(d), 1e-9)
    return a > 0 and d > 0 and abs(b) / scale < 1e-3 and abs(c) / scale < 1e-3


def _vertical_runs(runs: list[TextRun], visible: list[bool]) -> set[int]:
    """Word 等以「每行一字、往下堆疊」排直書：同一 BT 內連續單字 run，x 相同、y 遞減。"""
    flagged: set[int] = set()
    chain: list[int] = []

    def single(i: int):
        glyphs = [g for g in runs[i].glyphs if not (g.unicode or "").isspace()]
        return glyphs[0] if visible[i] and len(glyphs) == 1 else None

    for i in range(len(runs)):
        g = single(i)
        if g is not None and chain:
            prev = single(chain[-1])
            same_block = runs[chain[-1]].bt_index == runs[i].bt_index
            if (
                same_block
                and abs(prev.origin[0] - g.origin[0]) <= LOCATE_TOL
                and g.origin[1] < prev.origin[1]
            ):
                chain.append(i)
                continue
        if len(chain) >= 2:
            flagged.update(chain)
        chain = [i] if g is not None else []
    if len(chain) >= 2:
        flagged.update(chain)
    return flagged


def _analyze_page(document: Document, page_index: int) -> dict:
    pike_page = document.pike.pages[page_index]
    mu_page = document.mu[page_index]
    geom = page_geometry(pike_page)
    to_page = geom.pdf_to_page()
    content: PageContent = interpret(pike_page)
    doc_reasons = document.doc_reasons
    if any(e.startswith("limit:") for e in content.errors):
        # 超過工作量上限：不再交給 MuPDF 擷取（同一份內容會讓 MuPDF 做相同的放大工作）
        document.runs[page_index] = ([], {})
        return _page_result(page_index, geom, [], [], 0, [*doc_reasons, "RESOURCE_LIMIT"])
    grid = _chars(mu_page)
    rev = document.revision

    # 每個字型在本頁用到的字碼都要有可靠 Unicode，否則整個字型不可信（ADR-0011）
    unreliable_fonts = set()
    for run in content.runs:
        if run.font is not None and any(g.unicode is None for g in run.glyphs):
            unreliable_fonts.add(id(run.font))

    visible = [any(not (g.unicode or "").isspace() or g.unicode is None for g in r.glyphs)
               for r in content.runs]  # fmt: skip
    vertical = _vertical_runs(content.runs, visible)
    text_targets = []
    run_index: dict[str, int] = {}
    for i, run in enumerate(content.runs):
        if not visible[i]:
            continue
        reasons = list(doc_reasons)
        glyphs, mismatch, unlocated = [], False, False
        for g in run.glyphs:
            x, y = apply(to_page, *g.origin)
            ch, same = _match(grid, x, y, g.unicode)
            if g.unicode is not None and g.unicode.isspace():
                continue
            if ch is None:
                unlocated = True
            elif not same:
                mismatch = True
            glyphs.append(
                {"c": g.unicode, "bbox": [round(v, 2) for v in ch["bbox"]] if ch else None}
            )
        font = run.font
        if font is None or font.unsupported == fontmod.UNSUPPORTED_CMAP:
            reasons.append("UNSUPPORTED_ENCODING")
        if font is not None and id(font) in unreliable_fonts:
            reasons.append("UNSUPPORTED_ENCODING")
        if mismatch:
            reasons.append("UNSUPPORTED_ENCODING")
        if font is not None and font.unsupported in (fontmod.VERTICAL, fontmod.TYPE3):
            reasons.append("UNSUPPORTED_LAYOUT")
        if unlocated or not _upright(run.matrix) or i in vertical or run.form_path:
            reasons.append("UNSUPPORTED_LAYOUT")
        if run.actual_text:
            reasons.append("UNSUPPORTED_FEATURE")
        boxes = [g["bbox"] for g in glyphs if g["bbox"]]
        bbox = ([min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                 max(b[3] for b in boxes)] if boxes else None)  # fmt: skip
        text_targets.append({
            "target_id": _target_id("t", rev, page_index, run.stream, run.op_index, run.form_path,
                                    f"{run.text}|{bbox}|{font.key if font else ''}"),
            "stream": list(run.stream),
            "op_index": run.op_index,
            "operator": run.operator,
            "form_path": list(run.form_path),
            "text": run.text,
            "code_count": len(run.glyphs),
            "bbox": [round(v, 2) for v in bbox] if bbox else None,
            "font": _font_summary(font),
            "size": round(run.size, 3),
            "glyphs": glyphs,
            "capability": _capability(reasons),
        })  # fmt: skip
        run_index[text_targets[-1]["target_id"]] = i
    document.runs[page_index] = (content.runs, run_index)

    image_targets = []
    for use in content.images:
        reasons = list(doc_reasons)
        rect = bbox_of(to_page, image_rect(use))
        visible_rect = list(rect)
        for clip in use.clips:
            cx0, cy0, cx1, cy1 = bbox_of(to_page, clip.bbox)
            visible_rect = [max(visible_rect[0], cx0), max(visible_rect[1], cy0),
                            min(visible_rect[2], cx1), min(visible_rect[3], cy1)]  # fmt: skip
        a, b, c, d, _, _ = use.ctm
        if use.form_path or abs(b) > 1e-6 or abs(c) > 1e-6 or a <= 0 or d <= 0:
            reasons.append("UNSUPPORTED_LAYOUT")
        if any(not clip.is_rect for clip in use.clips):
            reasons.append("UNSUPPORTED_LAYOUT")
        filters = use.xobject.get("/Filter")
        filters = [str(f) for f in (filters if isinstance(filters, pikepdf.Array) else [filters])
                   if f is not None]  # fmt: skip
        if any(f not in _SUPPORTED_IMAGE_FILTERS for f in filters) or use.xobject.get("/ImageMask"):
            reasons.append("UNSUPPORTED_FEATURE")
        image_targets.append({
            "target_id": _target_id("i", rev, page_index, use.stream, use.op_index, use.form_path,
                                    f"{use.name}|{use.xobject.objgen}|{rect}"),
            "stream": list(use.stream),
            "op_index": use.op_index,
            "form_path": list(use.form_path),
            "name": use.name,
            "xobject": list(use.xobject.objgen),
            "bbox": [round(v, 2) for v in rect],
            "visible_bbox": [round(v, 2) for v in visible_rect],
            "has_smask": "/SMask" in use.xobject,
            "filters": filters,
            "capability": _capability(reasons),
        })  # fmt: skip

    page_reasons = list(doc_reasons)
    error_reasons = []
    if any(e.startswith("limit:") for e in content.errors):
        error_reasons.append("RESOURCE_LIMIT")
    if any(not e.startswith("limit:") for e in content.errors):
        error_reasons.append("MALFORMED_DOCUMENT")
    page_reasons += error_reasons
    if not text_targets and not page_reasons:
        # 頁面能力指文字編輯：沒有任何文字目標即唯讀（掃描、輪廓文字、純圖片頁）；影像目標各自判定
        page_reasons.append("NO_TEXT_LAYER")
    if error_reasons:
        for target in text_targets + image_targets:
            target["capability"] = _capability([*target["capability"]["reasons"], *error_reasons])

    return _page_result(page_index, geom, text_targets, image_targets, content.inline_images,
                        page_reasons)  # fmt: skip


def _page_result(page_index, geom, text_targets, image_targets, inline_images, reasons) -> dict:
    return {
        "page_index": page_index,
        "page_geometry": {
            "cropbox": list(geom.cropbox),
            "rotation": geom.rotation,
            "width": geom.width,
            "height": geom.height,
        },
        "text_targets": text_targets,
        "image_targets": image_targets,
        "inline_images": inline_images,
        "capabilities": _capability(reasons),
    }


def _capability(reasons: list[str]) -> dict:
    unique = list(dict.fromkeys(reasons))
    if not unique:
        status = "support"
    elif set(unique) == {"NO_TEXT_LAYER"}:
        status = "readonly"
    else:
        status = "reject"
    return {"status": status, "reasons": unique}


def _font_summary(font) -> dict | None:
    if font is None:
        return None
    return {
        "resource": font.key,
        "subtype": font.subtype,
        "base_font": font.base_font,
        "embedded": font.embedded,
        "two_byte": font.two_byte,
        "has_to_unicode": font.to_unicode is not None,
    }


def _target_id(kind, rev, page_index, stream, op_index, form_path, geometry_key) -> str:
    """spec §7：revision、page_index、content stream、運算子 occurrence、Form 路徑、幾何 hash。"""
    digest = hashlib.sha256(geometry_key.encode("utf-8")).hexdigest()[:12]
    form = "/".join(form_path)
    return f"{kind}:r{rev}:p{page_index}:s{stream[0]}.{stream[1]}:o{op_index}:f{form}:g{digest}"
