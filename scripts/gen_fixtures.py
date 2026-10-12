"""產生合成 fixture（manifest 中 source=synthetic-pymupdf 的項目）。

內容全為合成文字，不含真實公文或個資，可放公開 repo 與 CI（見 CLAUDE.md 資料規定）。
輸出具決定性：同一套鎖定版本下重跑，位元組相同。

用法：uv run python scripts/gen_fixtures.py [輸出目錄]（預設 tests/fixtures/generated）
"""

from __future__ import annotations

import csv
import hashlib
import sys
from collections.abc import Callable
from pathlib import Path

import pikepdf
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "manifest.csv"
DEFAULT_OUT = ROOT / "tests" / "fixtures" / "generated"

FIXED_DATE = "D:20260101000000Z"
LATIN = "The quick brown fox jumps over the lazy dog."
CJK = "臺北市政府公文測試：本段文字為合成內容。"
SAVE_OPTS = {"garbage": 3, "deflate": True, "no_new_id": True}


def _new_doc() -> pymupdf.Document:
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


def _save(doc: pymupdf.Document, path: Path, **extra) -> None:
    doc.save(path, **{**SAVE_OPTS, **extra})
    doc.close()


def _cjk_font() -> pymupdf.Font:
    # PyMuPDF 內建 Droid Sans Fallback（Apache-2.0），可合法嵌入合成 fixture
    return pymupdf.Font("china-t")


def latin_simple(path: Path) -> None:
    doc = _new_doc()
    doc.new_page().insert_text((72, 72), LATIN, fontname="helv", fontsize=12)
    _save(doc, path)


def latin_multipage(path: Path) -> None:
    doc = _new_doc()
    for i in range(3):
        doc.new_page().insert_text((72, 72), f"Page {i + 1}: {LATIN}", fontname="helv")
    _save(doc, path)


def latin_tj_array(path: Path) -> None:
    doc = _new_doc()
    page = doc.new_page()
    page.insert_text((72, 72), " ", fontname="helv")  # 讓頁面資源含 /helv
    xref = page.get_contents()[0]
    doc.update_stream(xref, b"BT /helv 12 Tf 72 720 Td [(Hel) -20 (lo W) 15 (orld)] TJ ET")
    _save(doc, path)


def cjk_subset_embedded(path: Path) -> None:
    doc = _new_doc()
    page = doc.new_page()
    page.insert_font(fontname="cjk", fontbuffer=_cjk_font().buffer)
    page.insert_text((72, 72), CJK, fontname="cjk", fontsize=14)
    doc.subset_fonts()
    _save(doc, path)


def cjk_not_embedded(path: Path) -> None:
    doc = _new_doc()
    doc.new_page().insert_text((72, 72), CJK, fontname="china-t", fontsize=14)
    _save(doc, path)


def mixed_line(path: Path) -> None:
    doc = _new_doc()
    page = doc.new_page()
    page.insert_font(fontname="cjk", fontbuffer=_cjk_font().buffer)
    page.insert_text((72, 72), "Ref No. 115-0001", fontname="helv", fontsize=12)
    page.insert_text((180, 72), "號函：測試", fontname="cjk", fontsize=12)
    doc.subset_fonts()
    _save(doc, path)


def rotated_page(path: Path) -> None:
    doc = _new_doc()
    page = doc.new_page()
    page.insert_text((72, 72), LATIN, fontname="helv")
    page.set_rotation(90)
    _save(doc, path)


def rotated_text(path: Path) -> None:
    doc = _new_doc()
    doc.new_page().insert_text((200, 200), LATIN, fontname="helv", rotate=90)
    _save(doc, path)


def table_grid(path: Path) -> None:
    doc = _new_doc()
    page = doc.new_page()
    page.insert_font(fontname="cjk", fontbuffer=_cjk_font().buffer)
    x0, y0, cw, rh = 72, 100, 150, 30
    cells = [["項目", "數量", "備註"], ["文具", "12", "合成"], ["紙張", "300", "資料"]]
    for r in range(len(cells) + 1):
        page.draw_line((x0, y0 + r * rh), (x0 + 3 * cw, y0 + r * rh))
    for c in range(4):
        page.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + len(cells) * rh))
    for r, row in enumerate(cells):
        for c, text in enumerate(row):
            page.insert_text((x0 + c * cw + 6, y0 + r * rh + 20), text, fontname="cjk")
    doc.subset_fonts()
    _save(doc, path)


def repeated_occurrences(path: Path) -> None:
    doc = _new_doc()
    page = doc.new_page()
    for i in range(5):
        page.insert_text((72, 72 + i * 20), f"Item {i}: alpha beta alpha", fontname="helv")
    _save(doc, path)


def image_only(path: Path) -> None:
    doc = _new_doc()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 200, 50), False)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 272, 122), pixmap=pix)
    _save(doc, path)


def encrypted_user_pw(path: Path) -> None:
    doc = _new_doc()
    doc.new_page().insert_text((72, 72), LATIN, fontname="helv")
    # 固定密碼的合成樣本；加密檔每次產生的 key 不同，不檢查決定性
    _save(doc, path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="fixture", owner_pw="owner")


def encrypted_owner_only(path: Path) -> None:
    doc = _new_doc()
    doc.new_page().insert_text((72, 72), LATIN, fontname="helv")
    _save(
        doc,
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        permissions=pymupdf.PDF_PERM_PRINT,
    )


def truncated(path: Path) -> None:
    latin_simple(path)
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])


def not_pdf(path: Path) -> None:
    path.write_bytes(hashlib.sha256(b"peditor-not-pdf").digest() * 64)


def form_field(path: Path) -> None:
    doc = _new_doc()
    page = doc.new_page()
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "name"
    widget.field_value = "Sample"
    widget.rect = pymupdf.Rect(72, 72, 272, 92)
    page.add_widget(widget)
    _save(doc, path)


def incremental_update(path: Path) -> None:
    latin_simple(path)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.docinfo["/Title"] = "incremental"
        pdf.save(path, deterministic_id=True)
    doc = pymupdf.open(path)
    doc[0].insert_text((72, 100), "Appended by incremental save.", fontname="helv")
    doc.save(path, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP, no_new_id=True)
    doc.close()


def empty_page(path: Path) -> None:
    doc = _new_doc()
    doc.new_page()
    _save(doc, path)


def many_pages(path: Path) -> None:
    doc = _new_doc()
    for i in range(50):
        doc.new_page().insert_text((72, 72), f"Page {i + 1}: {LATIN}", fontname="helv")
    _save(doc, path)


def invisible_text(path: Path) -> None:
    doc = _new_doc()
    doc.new_page().insert_text((72, 72), LATIN, fontname="helv", render_mode=3)
    _save(doc, path)


GENERATORS: dict[str, Callable[[Path], None]] = {
    f.__name__: f
    for f in (
        latin_simple,
        latin_multipage,
        latin_tj_array,
        cjk_subset_embedded,
        cjk_not_embedded,
        mixed_line,
        rotated_page,
        rotated_text,
        table_grid,
        repeated_occurrences,
        image_only,
        encrypted_user_pw,
        encrypted_owner_only,
        truncated,
        not_pdf,
        form_field,
        incremental_update,
        empty_page,
        many_pages,
        invisible_text,
    )
}

# 加密每次產生隨機 key／salt，不納入決定性檢查
NONDETERMINISTIC = {"encrypted_user_pw", "encrypted_owner_only"}


def synthetic_rows(manifest: Path = MANIFEST) -> list[dict[str, str]]:
    with manifest.open(encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh) if r["source"] == "synthetic-pymupdf"]


def generate(out_dir: Path = DEFAULT_OUT, manifest: Path = MANIFEST) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for row in synthetic_rows(manifest):
        path = out_dir / f"{row['id']}.pdf"
        GENERATORS[row["generator"]](path)
        paths.append(path)
    return paths


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    for p in generate(out):
        print(p.relative_to(out), hashlib.sha256(p.read_bytes()).hexdigest()[:16])
