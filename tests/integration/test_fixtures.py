"""G0：首批合成 fixture 的可重現性與「預期性質」（雙引擎、qpdf 結構檢查）。

這些測試確認 fixture 本身符合 manifest 的描述，不是編輯功能的驗收。
"""

import hashlib
from pathlib import Path

import pikepdf
import pymupdf
import pypdfium2
import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = ROOT / "tests" / "fixtures" / "files"
FONT_DIR = ROOT / "tests" / "fixtures" / "fonts"
PACKAGED_FONTS = [FONT_DIR / "NotoSansTC-Regular.otf", FONT_DIR / "NotoSerifTC-VF.ttf"]


def _path(row):
    return FILES / f"{row['fixture_id']}.pdf"


def _rows(rows, **match):
    return [r for r in rows if all(r[k] == v for k, v in match.items())]


def _pdfium_text(path, page_index):
    doc = pypdfium2.PdfDocument(str(path))
    try:
        return doc[page_index].get_textpage().get_text_range().replace("\r", "")
    finally:
        doc.close()


def _embedded_font_has(doc, page_index, text):
    """頁面上任一嵌入字型是否含 text 的全部字形。"""
    for xref, ext, *_ in doc.get_page_fonts(page_index):
        if ext == "n/a":
            continue
        buffer = doc.extract_font(xref)[3]
        font = pymupdf.Font(fontbuffer=buffer)
        if all(font.has_glyph(ord(ch)) for ch in text if not ch.isspace()):
            return True
    return False


def test_generator_reproduces_committed_bytes(gen_fixtures, tmp_path):
    for fid, path in gen_fixtures.generate(tmp_path).items():
        if not gen_fixtures.BY_ID[fid].deterministic:
            continue
        expected = hashlib.sha256((FILES / f"{fid}.pdf").read_bytes()).hexdigest()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, fid


def test_support_text_targets_found_by_both_engines(available_rows):
    for row in _rows(available_rows, expected="support", target="text"):
        page = int(row["page_index"])
        with pymupdf.open(_path(row)) as doc:
            assert row["original_text"] in doc[page].get_text(), row["fixture_id"]
            hits = doc[page].search_for(row["original_text"])
            x0, y0, x1, y1 = (float(v) for v in row["bbox_pt"].split(","))
            assert any(abs(h.x0 - x0) <= 0.5 and abs(h.y0 - y0) <= 0.5 for h in hits)
        assert row["original_text"] in _pdfium_text(_path(row), page), row["fixture_id"]


def test_support_and_readonly_fixtures_pass_qpdf_check(available_rows):
    for row in available_rows:
        if row["reason_code"] in {"ENCRYPTED_DOCUMENT", "MALFORMED_DOCUMENT"}:
            continue
        with pikepdf.open(_path(row)) as pdf:
            assert pdf.check_pdf_syntax() == [], row["fixture_id"]


def test_mode_a_targets_have_new_glyphs_in_original_subset(available_rows):
    """新字已在原嵌入子集 → 可走模式 A；F02 刻意缺字 → 需模式 B（ADR-0001）。"""
    for fid in ("T01", "F01", "L02", "L03", "B01"):
        row = _rows(available_rows, fixture_id=fid)[0]
        with pymupdf.open(_path(row)) as doc:
            assert _embedded_font_has(doc, 0, row["new_text"]), fid
    f02 = _rows(available_rows, fixture_id="F02")[0]
    with pymupdf.open(_path(f02)) as doc:
        assert not _embedded_font_has(doc, 0, f02["new_text"])
    assert pymupdf.Font(fontfile=str(PACKAGED_FONTS[0])).has_glyph(ord("藥"))


@pytest.mark.parametrize(
    "reason",
    ["GLYPH_MISSING", "UNSUPPORTED_ENCODING", "NO_TEXT_LAYER", "ENCRYPTED_DOCUMENT",
     "MALFORMED_DOCUMENT", "ACTIVE_CONTENT"],
)  # fmt: skip
def test_reject_fixtures_have_stated_property(available_rows, reason):
    rows = _rows(available_rows, reason_code=reason)
    assert rows, reason
    for row in rows:
        path = _path(row)
        if reason == "MALFORMED_DOCUMENT":
            with pikepdf.open(path) as pdf:
                assert pdf.check_pdf_syntax(), row["fixture_id"]
            continue
        with pymupdf.open(path) as doc:
            if reason == "ENCRYPTED_DOCUMENT":
                assert doc.needs_pass, row["fixture_id"]
                continue
            page = doc[int(row["page_index"])]
            if reason == "GLYPH_MISSING":
                missing = [ch for ch in row["new_text"] if ch not in row["original_text"]]
                for font_path in PACKAGED_FONTS:
                    font = pymupdf.Font(fontfile=str(font_path))
                    assert not all(font.has_glyph(ord(ch)) for ch in missing), row["fixture_id"]
                assert not pymupdf.Font("china-t").has_glyph(ord(missing[0]))
            elif reason == "UNSUPPORTED_ENCODING":
                assert row["original_text"] not in page.get_text(), row["fixture_id"]
                assert all("/ToUnicode" not in doc.xref_object(f[0]) for f in doc.get_page_fonts(0))
            elif reason == "NO_TEXT_LAYER":
                assert not page.get_text().strip(), row["fixture_id"]
            elif reason == "ACTIVE_CONTENT":
                catalog = doc.xref_object(doc.pdf_catalog())
                assert "/OpenAction" in catalog, row["fixture_id"]


def test_shared_image_fixtures(available_rows):
    with pymupdf.open(FILES / "I02.pdf") as doc:
        assert doc[0].get_images()[0][0] == doc[1].get_images()[0][0]
    with pymupdf.open(FILES / "I03.pdf") as doc:
        xref = doc[0].get_images()[0][0]
        assert len(doc[0].get_image_rects(xref)) == 2
