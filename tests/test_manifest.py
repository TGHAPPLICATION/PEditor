"""G0：fixture manifest 結構與合成 fixture 產生器。"""

import csv
import hashlib
import json

import jsonschema
import pymupdf
import pytest
from conftest import ROOT

MANIFEST = ROOT / "tests" / "fixtures" / "manifest.csv"
SCHEMA = ROOT / "tests" / "fixtures" / "manifest.schema.json"


def _rows():
    with MANIFEST.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_manifest_rows_match_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for row in _rows():
        jsonschema.validate(row, schema)


def test_manifest_counts():
    rows = _rows()
    assert len(rows) == 60
    assert len({r["id"] for r in rows}) == 60
    assert sum(r["blind"] == "true" for r in rows) == 12


def test_every_synthetic_row_has_generator(gen_fixtures):
    for row in gen_fixtures.synthetic_rows():
        assert row["generator"] in gen_fixtures.GENERATORS, row["id"]


def test_generated_fixtures_open_as_expected(gen_fixtures, generated_dir):
    for row in gen_fixtures.synthetic_rows():
        path = generated_dir / f"{row['id']}.pdf"
        if row["reason"] in {"malformed", "not_pdf"}:
            with pytest.raises(pymupdf.FileDataError):
                pymupdf.open(path)
            continue
        with pymupdf.open(path) as doc:
            if row["generator"] == "encrypted_user_pw":
                assert doc.needs_pass
            else:
                assert doc.page_count >= 1


def _reject_property_holds(reason, doc):
    page = doc[0]
    if reason == "font_not_embedded":
        return page.get_text().strip() and all(f[1] == "n/a" for f in doc.get_page_fonts(0))
    if reason == "no_text_layer":
        return not page.get_text().strip()
    if reason == "encrypted":
        return doc.needs_pass or doc.metadata.get("encryption")
    if reason == "form_fields":
        return doc.is_form_pdf
    if reason == "invisible_text":
        return page.get_text().strip() and b"3 Tr" in page.read_contents()
    raise AssertionError(f"未處理的 reason：{reason}")


def test_reject_fixtures_have_stated_property(gen_fixtures, generated_dir):
    for row in gen_fixtures.synthetic_rows():
        if row["expected"] != "reject" or row["reason"] in {"malformed", "not_pdf"}:
            continue
        with pymupdf.open(generated_dir / f"{row['id']}.pdf") as doc:
            if doc.needs_pass:
                assert row["reason"] == "encrypted", row["id"]
                continue
            assert _reject_property_holds(row["reason"], doc), row["id"]


def test_generator_is_deterministic(gen_fixtures, generated_dir, tmp_path):
    gen_fixtures.generate(tmp_path)
    for row in gen_fixtures.synthetic_rows():
        if row["generator"] in gen_fixtures.NONDETERMINISTIC:
            continue
        name = f"{row['id']}.pdf"
        a = hashlib.sha256((generated_dir / name).read_bytes()).hexdigest()
        b = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        assert a == b, name


def test_cjk_subset_font_is_embedded(generated_dir):
    with pymupdf.open(generated_dir / "S04.pdf") as doc:
        fonts = doc.get_page_fonts(0)
        assert any("+" in f[3] and f[1] == "ttf" for f in fonts)
        assert "臺北市政府" in doc[0].get_text()
