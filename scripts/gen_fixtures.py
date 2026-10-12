"""產生首批合成 fixture（spec §5、P0），並回寫 manifest 的計算欄位。

- 內容全為合成文字，不含真實公文或個資，可放公開 repo 與 CI。
- 兩種產生器（PyMuPDF、ReportLab）與三種繁中字型（Noto Sans TC、Noto Serif TC、
  Droid Sans Fallback），避免全部同一引擎產生。
- 除加密樣本外，同一套鎖定版本下重跑位元組相同；產出提交於 tests/fixtures/files/，
  manifest 記錄 SHA-256（G0：fixture hash 可驗證）。

座標慣例（manifest 的 bbox_pt／editable_region_pt）：未旋轉頁面空間、左上原點、
y 向下、單位 pt（即 PyMuPDF 在 /Rotate=0 時的頁面座標）。

用法：
  uv run python scripts/fetch_fonts.py          # 先取得字型
  uv run python scripts/gen_fixtures.py         # 產生到 tests/fixtures/files/ 並更新 manifest
  uv run python scripts/gen_fixtures.py OUTDIR  # 只產生到指定目錄（不改 manifest）
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pikepdf
import pymupdf
import reportlab
from fontTools import subset as ft_subset
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MANIFEST = FIXTURES / "manifest.csv"
FILES = FIXTURES / "files"
FONT_DIR = FIXTURES / "fonts"
NOTO_SANS = FONT_DIR / "NotoSansTC-Regular.otf"
NOTO_SERIF = FONT_DIR / "NotoSerifTC-VF.ttf"

FIELDS = [
    "fixture_id", "group", "sha256", "generator", "generator_version", "fonts",
    "expected", "reason_code", "page_index", "target", "bbox_pt", "original_text",
    "new_text", "editable_region_pt", "protected_region", "blind", "storage", "status",
    "notes",
]  # fmt: skip

FIXED_DATE = "D:20260101000000Z"
PYMUPDF_SAVE = {"garbage": 3, "deflate": True, "no_new_id": True}
A4_W, A4_H = A4


# ---------------------------------------------------------------- 共用工具


def _require_fonts() -> None:
    missing = [p.name for p in (NOTO_SANS, NOTO_SERIF) if not p.exists()]
    if missing:
        raise SystemExit(f"缺字型 {missing}：請先執行 uv run python scripts/fetch_fonts.py")


def _doc() -> pymupdf.Document:
    doc = pymupdf.open()
    doc.set_metadata(
        {
            "producer": "PEditor fixture generator",
            "creator": "scripts/gen_fixtures.py",
            "creationDate": FIXED_DATE,
            "modDate": FIXED_DATE,
        }
    )
    return doc


def _page(doc: pymupdf.Document) -> pymupdf.Page:
    return doc.new_page(width=A4_W, height=A4_H)


def _save(doc: pymupdf.Document, path: Path, **extra) -> None:
    doc.save(path, **{**PYMUPDF_SAVE, **extra})
    doc.close()


def _noto_sans_subset(text: str) -> bytes:
    """以 fontTools 子集化 Noto Sans TC（CFF OTF；MuPDF subset_fonts 無法處理 CFF）。

    子集只含 text 用到的字，模擬一般產生器的嵌入子集；不在 text 的字即為「新字缺字」。
    """
    options = ft_subset.Options()
    options.name_IDs = ["*"]
    options.notdef_outline = True
    font = ft_subset.load_font(str(NOTO_SANS), options)
    subsetter = ft_subset.Subsetter(options)
    subsetter.populate(unicodes={ord(ch) for ch in text})
    subsetter.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def _font(page: pymupdf.Page, name: str, text: str = "") -> str:
    """在頁面註冊字型並回傳 fontname。

    droid：完整 TTF，存檔前以 doc.subset_fonts() 子集化。
    noto-sans：以 fontTools 依 text 預先子集化後嵌入（不可再呼叫 subset_fonts）。
    """
    if name == "droid":
        page.insert_font(fontname="droid", fontbuffer=pymupdf.Font("china-t").buffer)
        return "droid"
    if name == "noto-sans":
        page.insert_font(fontname="notosans", fontbuffer=_noto_sans_subset(text))
        return "notosans"
    raise ValueError(name)


def _rl_canvas(buf: io.BytesIO) -> canvas.Canvas:
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    c.setCreator("scripts/gen_fixtures.py")
    c.setProducer("PEditor fixture generator (ReportLab)")
    return c


def _rl_font(name: str) -> str:
    if name == "droid":
        if "DroidTC" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("DroidTC", io.BytesIO(pymupdf.Font("china-t").buffer)))
        return "DroidTC"
    if name == "noto-serif":
        if "NotoSerifTC" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("NotoSerifTC", str(NOTO_SERIF)))
        return "NotoSerifTC"
    raise ValueError(name)


def _rl_save(c: canvas.Canvas, buf: io.BytesIO, path: Path) -> None:
    c.showPage()
    c.save()
    path.write_bytes(buf.getvalue())


def _png(w: int, h: int, seed: int) -> bytes:
    """決定性的合成 RGB 圖片（漸層 + 色塊）。"""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), False)
    for y in range(h):
        for x in range(w):
            pix.set_pixel(x, y, ((x * 255) // w, (y * 255) // h, (seed * 70) % 256))
    return pix.tobytes("png")


# ---------------------------------------------------------------- 產生函式
# 頁面座標：PyMuPDF insert_text 的點為基線左端、左上原點；ReportLab 為左下原點。


def t01(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    lines = ["臺北市政府衛生局公告", "本公告內容為合成測試資料。"]
    f = _font(page, "noto-sans", "".join(lines))
    page.insert_text((72, 100), lines[0], fontname=f, fontsize=14)
    page.insert_text((72, 130), lines[1], fontname=f, fontsize=12)
    _save(doc, path)


def t02(path: Path) -> None:
    buf = io.BytesIO()
    c = _rl_canvas(buf)
    c.setFont(_rl_font("droid"), 12)
    c.drawString(72, A4_H - 100, "案號 115-0001 請於 10 月 31 日前回覆 ABC 公司。")
    c.drawString(72, A4_H - 124, "聯絡電話 02-2720-0000（合成）")
    _rl_save(c, buf, path)


def t03(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    f = _font(page, "droid")
    page.insert_text((72, 100), "依據：本府（一一五）府衛字第１號函。", fontname=f, fontsize=12)
    doc.subset_fonts()
    _save(doc, path)


def t04(path: Path) -> None:
    buf = io.BytesIO()
    c = _rl_canvas(buf)
    c.setFont(_rl_font("noto-serif"), 12)
    c.drawString(72, A4_H - 100, "會議地點：三樓")
    c.drawString(72, A4_H - 124, "會議時間：上午十時")
    _rl_save(c, buf, path)


def f01(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    lines = ["臺灣醫衛龜", "衛生醫療資料（合成）"]
    f = _font(page, "noto-sans", "".join(lines))
    page.insert_text((72, 100), lines[0], fontname=f, fontsize=16)
    page.insert_text((72, 130), lines[1], fontname=f, fontsize=12)
    _save(doc, path)


def f02(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    f = _font(page, "noto-sans", "醫事人員名冊")
    page.insert_text((72, 100), "醫事人員名冊", fontname=f, fontsize=14)
    _save(doc, path)


def f03(path: Path) -> None:
    buf = io.BytesIO()
    c = _rl_canvas(buf)
    c.setFont(_rl_font("droid"), 14)
    c.drawString(72, A4_H - 100, "承辦人：吉田")
    _rl_save(c, buf, path)


def f04(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    page.insert_text((72, 100), " ", fontname="helv")  # 讓頁面資源含 /helv
    xref = page.get_contents()[0]
    doc.update_stream(xref, b"BT /helv 14 Tf 72 742 Td [(Hel) -20 (lo W) 15 (orld)] TJ ET")
    _save(doc, path)


def f05(path: Path) -> None:
    f01(path)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        for font in pdf.pages[0].Resources.Font.values():
            if "/ToUnicode" in font:
                del font["/ToUnicode"]
        pdf.save(path, deterministic_id=True, compress_streams=True)


def l01(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    f = _font(page, "droid")
    page.insert_text((120, 160), "裁切框位移測試：第三科", fontname=f, fontsize=12)
    page.set_cropbox(pymupdf.Rect(50, 50, A4_W - 50, A4_H - 50))
    doc.subset_fonts()
    _save(doc, path)


def l02(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    f = _font(page, "noto-sans", "頁面旋轉測試：北區")
    page.insert_text((72, 100), "頁面旋轉測試：北區", fontname=f, fontsize=12)
    page.set_rotation(90)
    _save(doc, path)


def l03(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    f = _font(page, "noto-sans", "密集鄰字甲乙丙丁戊")
    page.insert_text((72, 100), "密集鄰字甲乙丙丁戊", fontname=f, fontsize=12)
    page.draw_rect(pymupdf.Rect(70, 86, 200, 104), color=(0.8, 0, 0), width=0.5)
    xref = page.get_contents()[0]
    stream = doc.xref_stream(xref)
    # 加負字距讓字形緊貼（Tc），測試鄰字不被誤傷
    doc.update_stream(xref, stream.replace(b"BT", b"BT -1.5 Tc", 1))
    _save(doc, path)


def i01(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    page.insert_image(pymupdf.Rect(72, 72, 272, 172), stream=_png(64, 32, 1))
    _save(doc, path)


def i02(path: Path) -> None:
    doc = _doc()
    img = _png(48, 48, 2)
    xref = 0
    for _ in range(2):
        page = _page(doc)
        if xref:
            page.insert_image(pymupdf.Rect(72, 72, 172, 172), xref=xref)
        else:
            xref = page.insert_image(pymupdf.Rect(72, 72, 172, 172), stream=img)
    _save(doc, path)


def i03(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    xref = page.insert_image(pymupdf.Rect(72, 72, 172, 172), stream=_png(48, 48, 3))
    page.insert_image(pymupdf.Rect(300, 72, 400, 172), xref=xref)
    _save(doc, path)


TABLE_X0, TABLE_Y0, CELL_W, CELL_H = 72, 100, 150, 30
TABLE = [["項目", "數量", "備註"], ["文具", "12", "合成"], ["紙張", "300", "資料"]]


def _cell(r: int, c: int) -> tuple[float, float, float, float]:
    x0, y0 = TABLE_X0 + c * CELL_W, TABLE_Y0 + r * CELL_H
    return (x0, y0, x0 + CELL_W, y0 + CELL_H)


def b01(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    f = _font(page, "noto-sans", "".join("".join(row) for row in TABLE))
    rows, cols = len(TABLE), len(TABLE[0])
    for r in range(rows + 1):
        y = TABLE_Y0 + r * CELL_H
        page.draw_line((TABLE_X0, y), (TABLE_X0 + cols * CELL_W, y), width=1)
    for c in range(cols + 1):
        x = TABLE_X0 + c * CELL_W
        page.draw_line((x, TABLE_Y0), (x, TABLE_Y0 + rows * CELL_H), width=1)
    for r, row in enumerate(TABLE):
        for c, text in enumerate(row):
            x0, y0, _, _ = _cell(r, c)
            page.insert_text((x0 + 6, y0 + 20), text, fontname=f, fontsize=12)
    _save(doc, path)


B02_CELL = (72, 100, 272, 160)  # 左上原點


def b02(path: Path) -> None:
    buf = io.BytesIO()
    c = _rl_canvas(buf)
    font = _rl_font("noto-serif")
    x0, y0, x1, y1 = B02_CELL
    c.setLineWidth(1)
    for x in (x0, x1, x1 + 150):
        c.line(x, A4_H - y0, x, A4_H - y1)
    for y in (y0, y1):
        c.line(x0, A4_H - y, x1 + 150, A4_H - y)
    c.setFont(font, 11)
    c.drawString(x0 + 6, A4_H - (y0 + 18), "第一行：辦理地點")
    c.drawString(x0 + 6, A4_H - (y0 + 36), "第二行：市府大樓")
    c.drawString(x1 + 6, A4_H - (y0 + 18), "鄰格不可改")
    _rl_save(c, buf, path)


def u01(path: Path) -> None:
    src = _doc()
    page = _page(src)
    page.insert_text((20, 40), "掃描影像測試", fontname=_font(page, "droid"), fontsize=24)
    pix = page.get_pixmap(dpi=72, clip=pymupdf.Rect(0, 0, 300, 60), colorspace=pymupdf.csGRAY)
    src.close()
    doc = _doc()
    _page(doc).insert_image(pymupdf.Rect(72, 72, 372, 132), stream=pix.tobytes("png"))
    _save(doc, path)


def u02(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    page.insert_text((72, 100), "Encrypted fixture", fontname="helv")
    # 固定密碼的合成樣本；加密 key 每次隨機，位元組不可重現（只驗提交檔 hash）
    _save(doc, path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="fixture", owner_pw="owner")


def s01(path: Path) -> None:
    t03(path)
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])


def s02(path: Path) -> None:
    doc = _doc()
    page = _page(doc)
    page.insert_text((72, 100), "JavaScript OpenAction fixture", fontname="helv")
    js = doc.get_new_xref()
    doc.update_object(js, "<</S/JavaScript/JS(app.alert\\('peditor-sentinel'\\);)>>")
    doc.xref_set_key(doc.pdf_catalog(), "OpenAction", f"{js} 0 R")
    _save(doc, path)


# ---------------------------------------------------------------- 首批 fixture 定義


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    build: Callable[[Path], None]
    generator: str
    fonts: str
    expected: str
    reason_code: str = ""
    target: str = ""
    original_text: str = ""
    new_text: str = ""
    page_index: int = 0
    occurrence: int = 0
    editable_region: tuple[float, float, float, float] | None = None
    protected_region: str = "頁面其餘內容"
    deterministic: bool = True
    notes: str = ""
    extra: dict = field(default_factory=dict)


SYNTHETIC: list[Fixture] = [
    Fixture("T01", t01, "pymupdf", "Noto Sans TC", "support", target="text",
            original_text="衛生局", new_text="測試局",
            notes="同字數替換；新字皆在原子集內（模式 A）"),
    Fixture("T02", t02, "reportlab", "Droid Sans Fallback", "support", target="text",
            original_text="10 月 31 日", new_text="11 月 5 日", notes="中英數混排、較短替換"),
    Fixture("T03", t03, "pymupdf", "Droid Sans Fallback", "support", target="text",
            original_text="（一一五）", new_text="（一一六）", notes="全形標點與全形數字"),
    Fixture("T04", t04, "reportlab", "Noto Serif TC", "support", target="text",
            original_text="三樓", new_text="三樓第二會議室", editable_region=(72, 84, 400, 106),
            notes="較長替換，可容納於宣告區域"),
    Fixture("F01", f01, "pymupdf", "Noto Sans TC (subset)", "support", target="text",
            original_text="臺灣醫衛龜", new_text="龜衛臺灣醫",
            notes="新字皆在原子集內，預期模式 A"),
    Fixture("F02", f02, "pymupdf", "Noto Sans TC (subset)", "support", target="text",
            original_text="醫事", new_text="藥事",
            notes="新字不在原子集；模式 A 回 GLYPH_MISSING，預期以模式 B 重建（ADR-0001）"),
    Fixture("F03", f03, "reportlab", "Droid Sans Fallback", "reject", "GLYPH_MISSING",
            target="text", original_text="吉田", new_text="𠮷田",
            notes="𠮷（U+20BB7）不在任何已包裝字型，須明確拒絕，不可顯示方框"),
    Fixture("F04", f04, "pymupdf", "Helvetica (base14, WinAnsi)", "support", target="text",
            original_text="World", new_text="Earth", notes="TJ 陣列含字距調整"),
    Fixture("F05", f05, "pymupdf+pikepdf", "Noto Sans TC (subset)", "reject",
            "UNSUPPORTED_ENCODING", target="text", original_text="臺灣醫衛龜",
            new_text="臺灣", notes="移除 /ToUnicode，無法可靠逆向映射"),
    Fixture("L01", l01, "pymupdf", "Droid Sans Fallback", "support", target="text",
            original_text="第三科", new_text="第四科", notes="CropBox 非零原點"),
    Fixture("L02", l02, "pymupdf", "Noto Sans TC", "support", target="text",
            original_text="北區", new_text="旋轉",
            notes="/Rotate 90；bbox 為未旋轉頁面空間"),
    Fixture("L03", l03, "pymupdf", "Noto Sans TC", "support", target="text",
            original_text="丙丁", new_text="甲乙", protected_region="鄰字甲乙戊與紅框",
            notes="負字距 Tc 密集鄰字"),
    Fixture("I01", i01, "pymupdf", "", "support", target="image#0",
            notes="獨立 PNG Image XObject"),
    Fixture("I02", i02, "pymupdf", "", "support", target="image#0", page_index=0,
            protected_region="第 2 頁同一 xref 圖片", notes="跨頁共享 xref，只改第 1 頁"),
    Fixture("I03", i03, "pymupdf", "", "support", target="image#1", occurrence=1,
            protected_region="同頁第 1 次出現", notes="同頁同 xref 兩次出現，只改第 2 次"),
    Fixture("B01", b01, "pymupdf", "Noto Sans TC", "support", target="cell(1,1)",
            original_text="12", new_text="21", editable_region=_cell(1, 1),
            protected_region="格線與其他 8 格", notes="規則 3x3 表格"),
    Fixture("B02", b02, "reportlab", "Noto Serif TC", "support", target="cell(0,0)",
            original_text="市府大樓", new_text="市政大樓", editable_region=B02_CELL,
            protected_region="格線與右鄰格", notes="多行儲存格"),
    Fixture("U01", u01, "pymupdf", "", "readonly", "NO_TEXT_LAYER",
            notes="僅影像，模擬掃描；唯讀並提示（ADR-0007）"),
    Fixture("U02", u02, "pymupdf", "Helvetica", "reject", "ENCRYPTED_DOCUMENT",
            deterministic=False, notes="AES-256 開啟密碼"),
    Fixture("S01", s01, "pymupdf", "Droid Sans Fallback", "reject", "MALFORMED_DOCUMENT",
            notes="檔案截斷一半（ADR-0007）"),
    Fixture("S02", s02, "pymupdf", "Helvetica", "reject", "ACTIVE_CONTENT",
            notes="OpenAction JavaScript（含 sentinel）；不得執行；預期值待人工確認（ADR-0007）"),
]  # fmt: skip

BY_ID = {f.fixture_id: f for f in SYNTHETIC}


# ---------------------------------------------------------------- manifest 計算欄位


def _fmt(rect) -> str:
    return ",".join(f"{v:.2f}" for v in rect)


def _target_bbox(fx: Fixture, path: Path) -> str:
    if fx.reason_code in {"MALFORMED_DOCUMENT", "ENCRYPTED_DOCUMENT"}:
        return ""
    with pymupdf.open(path) as doc:
        page = doc[fx.page_index]
        if fx.target.startswith("image"):
            xref = page.get_images()[0][0]
            rects = page.get_image_rects(xref)
        elif fx.original_text:
            rects = page.search_for(fx.original_text)
        else:
            return ""
        if not rects:
            return ""
        # PyMuPDF 的 search_for／get_image_rects 已是未旋轉頁面座標
        return _fmt(rects[fx.occurrence])


def _versions() -> str:
    return (
        f"pymupdf {pymupdf.VersionBind}; reportlab {reportlab.Version}; "
        f"pikepdf {pikepdf.__version__}"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(manifest: Path = MANIFEST) -> list[dict[str, str]]:
    with manifest.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def generate(out_dir: Path) -> dict[str, Path]:
    _require_fonts()
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for fx in SYNTHETIC:
        path = out_dir / f"{fx.fixture_id}.pdf"
        fx.build(path)
        paths[fx.fixture_id] = path
    return paths


def update_manifest(paths: dict[str, Path], manifest: Path = MANIFEST) -> None:
    rows = read_manifest(manifest)
    versions = _versions()
    for row in rows:
        fx = BY_ID.get(row["fixture_id"])
        if fx is None:
            continue
        path = paths[fx.fixture_id]
        bbox = _target_bbox(fx, path)
        editable = _fmt(fx.editable_region) if fx.editable_region else ""
        if not editable and bbox:
            x0, y0, x1, y1 = (float(v) for v in bbox.split(","))
            editable = _fmt((x0 - 2, y0 - 2, x1 + 2, y1 + 2))  # spec §8.2：目標外 2 pt
        row.update(
            sha256=sha256(path),
            generator=fx.generator,
            generator_version=versions,
            fonts=fx.fonts,
            expected=fx.expected,
            reason_code=fx.reason_code,
            page_index=str(fx.page_index),
            target=fx.target,
            bbox_pt=bbox,
            original_text=fx.original_text,
            new_text=fx.new_text,
            editable_region_pt=editable,
            protected_region=fx.protected_region if fx.expected == "support" else "",
            storage="repo",
            status="available",
            notes=fx.notes,
        )
    with manifest.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for fid, p in generate(Path(sys.argv[1])).items():
            print(fid, sha256(p)[:16])
    else:
        update_manifest(generate(FILES))
        print(f"已產生 {len(SYNTHETIC)} 份到 {FILES.relative_to(ROOT)} 並更新 manifest")
