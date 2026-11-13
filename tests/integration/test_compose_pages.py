"""P9-02～P9-05：頁面工具組成新檔（ADR-0029）。
經 DocumentService → worker，PDF 只在 worker 解析。"""

import pikepdf
import pymupdf
import pytest

from peditor.core import pages
from peditor.core.service import ServiceError


def _sample(path, label: str, count: int, *, outline=False, link=False):
    doc = pymupdf.open()
    for i in range(count):
        page = doc.new_page(width=300, height=200)
        page.insert_text((40, 100), f"{label}{i + 1}", fontsize=24)
        if link:
            page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(40, 80, 120, 110),
                              "uri": "https://example.invalid/"})  # fmt: skip
    if outline:
        doc.set_toc([[1, f"{label} 書籤", 1]])
    doc.save(path)
    doc.close()
    return str(path)


def _streams(page) -> list[bytes]:
    contents = page.obj.Contents
    items = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
    return [s.read_bytes() for s in items]


def _texts(path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text().strip() for page in doc]


def _compose(service, tmp_path, sources, plan, name="out.pdf"):
    token = service.destination_token(tmp_path / name)
    result = service.compose_pages(sources, plan, token)
    return result, tmp_path / name


def test_delete_keep_merge_insert(service, tmp_path):
    a = _sample(tmp_path / "a.pdf", "A", 4)
    b = _sample(tmp_path / "b.pdf", "B", 2)
    cases = {
        "delete": ([a], pages.delete_plan(4, pages.parse_ranges("2,4", 4)), ["A1", "A3"]),
        "keep": ([a], pages.keep_plan(4, pages.parse_ranges("4,1-2", 4)), ["A1", "A2", "A4"]),
        "merge": ([a, b], pages.merge_plan([4, 2]), ["A1", "A2", "A3", "A4", "B1", "B2"]),
        "insert": ([a, b], pages.insert_plan(4, 2, 1), ["A1", "B1", "B2", "A2", "A3", "A4"]),
    }
    for name, (sources, plan, expected) in cases.items():
        result, out = _compose(service, tmp_path, sources, plan, f"{name}.pdf")
        assert result["page_count"] == len(expected)
        assert _texts(out) == expected, name
    assert _texts(a) == ["A1", "A2", "A3", "A4"]  # 來源不變


def test_output_keeps_content_and_drops_outline(service, tmp_path):
    a = _sample(tmp_path / "a.pdf", "A", 2, outline=True, link=True)
    _, out = _compose(service, tmp_path, [a], pages.keep_plan(2, [1]))
    with pikepdf.open(a) as src, pikepdf.open(out) as pdf:
        assert _streams(pdf.pages[0]) == _streams(src.pages[1])
        assert "/Outlines" not in pdf.Root  # 不保留書籤
        annots = pdf.pages[0].obj.get("/Annots", [])
        assert len(annots) == 1 and "/P" not in annots[0]  # 連結保留；不指回原檔頁面
        assert pdf.pages[0].mediabox == src.pages[1].mediabox


def test_rejects_form_and_encrypted_sources(service, tmp_path):
    a = _sample(tmp_path / "a.pdf", "A", 1)
    form = tmp_path / "form.pdf"
    with pikepdf.open(a) as pdf:
        field = pdf.make_indirect(pikepdf.Dictionary(FT=pikepdf.Name.Tx, T=pikepdf.String("x")))
        pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([field]))
        pdf.save(form)
    secret = tmp_path / "secret.pdf"
    with pikepdf.open(a) as pdf:
        pdf.save(secret, encryption=pikepdf.Encryption(owner="o", user="u"))
    for bad, code in ((form, "UNSUPPORTED_FEATURE"), (secret, "ENCRYPTED_DOCUMENT")):
        token = service.destination_token(tmp_path / f"out-{code}.pdf")
        with pytest.raises(ServiceError) as info:
            service.compose_pages([a, str(bad)], pages.merge_plan([1, 1]), token)
        assert info.value.code == code
        assert "form" not in info.value.message and str(tmp_path) not in info.value.message
        assert not (tmp_path / f"out-{code}.pdf").exists()


def test_never_overwrites_sources(service, tmp_path):
    a = _sample(tmp_path / "a.pdf", "A", 2)
    before = (tmp_path / "a.pdf").read_bytes()
    token = service.destination_token(tmp_path / "a.pdf", overwrite=True)
    with pytest.raises(ServiceError) as info:
        service.compose_pages([a], pages.keep_plan(2, [0]), token)
    assert info.value.code == "INVALID_REQUEST"
    assert (tmp_path / "a.pdf").read_bytes() == before


@pytest.mark.parametrize("plan", [[(0, 5)], [(1, 0)], [(0, -1)]])
def test_rejects_out_of_range_plan(service, tmp_path, plan):
    a = _sample(tmp_path / "a.pdf", "A", 2)
    token = service.destination_token(tmp_path / "out.pdf")
    with pytest.raises(ServiceError) as info:
        service.compose_pages([a], plan, token)
    assert info.value.code == "INVALID_REQUEST"
    assert not (tmp_path / "out.pdf").exists()


def test_probe_document(service, tmp_path):
    a = _sample(tmp_path / "a.pdf", "A", 3)
    assert service.probe_document(a) == {"page_count": 3, "reasons": []}
