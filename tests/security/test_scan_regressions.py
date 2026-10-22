"""P1 安全掃描確認的 8 項（reports/P1/security/TRIAGE.md）回歸測試。

每項以腳本產生的最小惡意 PDF 驗證：工作量受限並回報 RESOURCE_LIMIT／ACTIVE_CONTENT，
且在數秒內結束（修正前會耗用數 GB 記憶體或執行到 30 秒逾時）。
"""

import time
from pathlib import Path

import pikepdf
import pytest

from peditor.core.protocol import ProtocolError
from peditor.core.service import DocumentService
from peditor.worker import analyzer

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
FAST = 10.0  # 秒


def _pdf(path: Path, content: bytes, resources=None, media=(0, 0, 200, 200)) -> pikepdf.Pdf:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=media[2:])
    page = pdf.pages[0]
    page.obj.MediaBox = pikepdf.Array(list(media))
    page.Resources = resources or pikepdf.Dictionary()
    page.Contents = pdf.make_stream(content)
    return pdf


def _type0(pdf: pikepdf.Pdf, w=None, to_unicode: bytes | None = None) -> pikepdf.Dictionary:
    cid = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.CIDFontType2, BaseFont=pikepdf.Name("/X"),
        CIDSystemInfo=pikepdf.Dictionary(Registry="Adobe", Ordering="Identity", Supplement=0),
    )  # fmt: skip
    if w is not None:
        cid.W = pikepdf.Array(w)
    font = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0, BaseFont=pikepdf.Name("/X"),
        Encoding=pikepdf.Name("/Identity-H"), DescendantFonts=pikepdf.Array([cid]),
    )  # fmt: skip
    if to_unicode is not None:
        font.ToUnicode = pdf.make_stream(to_unicode)
    return pdf.make_indirect(font)


def _inspect(path: Path) -> dict:
    document = analyzer.open_document(str(path))
    try:
        started = time.monotonic()
        page = analyzer.inspect_page(document, 0)
        assert time.monotonic() - started < FAST
        return page
    finally:
        document.close()


def test_f001_cid_width_range_bounded(tmp_path):
    from peditor.worker.fonts import _cid_widths

    started = time.monotonic()
    widths = _cid_widths(pikepdf.Array([0, 4_000_000_000, 500]))
    assert time.monotonic() - started < FAST
    assert len(widths) <= 0x10000  # 夾在 2 位元組 CID 空間內
    pdf = _pdf(tmp_path / "w.pdf", b"BT /F1 12 Tf 20 100 Td <0001> Tj ET")
    pdf.pages[0].Resources = pikepdf.Dictionary(
        Font=pikepdf.Dictionary(F1=_type0(pdf, w=[0, 4_000_000_000, 500]))
    )
    pdf.save(tmp_path / "w.pdf")
    _inspect(tmp_path / "w.pdf")  # 在時限內完成
    # 多個寬範圍累計超過展開上限 → RESOURCE_LIMIT
    pdf.pages[0].Resources.Font.F1.DescendantFonts[0].W = pikepdf.Array([0, 65535, 500] * 10)
    pdf.save(tmp_path / "w2.pdf")
    assert "RESOURCE_LIMIT" in _inspect(tmp_path / "w2.pdf")["capabilities"]["reasons"]


def test_f005_tounicode_expansion_bounded(tmp_path):
    cmap = b"begincmap\n" + b"1 beginbfrange <0000> <FFFF> <0041> endbfrange\n" * 100 + b"endcmap"
    pdf = _pdf(tmp_path / "c.pdf", b"BT /F1 12 Tf 20 100 Td <0001> Tj ET")
    pdf.pages[0].Resources = pikepdf.Dictionary(
        Font=pikepdf.Dictionary(F1=_type0(pdf, to_unicode=cmap))
    )
    pdf.save(tmp_path / "c.pdf")
    page = _inspect(tmp_path / "c.pdf")
    assert "RESOURCE_LIMIT" in page["capabilities"]["reasons"]


def test_f004_form_fan_out_bounded(tmp_path):
    pdf = _pdf(tmp_path / "f.pdf", b"/X Do")
    child = pdf.make_stream(b"0 0 1 1 re f", Type=pikepdf.Name.XObject,
                            Subtype=pikepdf.Name.Form, BBox=[0, 0, 200, 200])  # fmt: skip
    for _ in range(7):  # 8 層、每層呼叫下一層 10 次 → 10^8 次（修正前）
        parent = pdf.make_stream(b"/X Do " * 10, Type=pikepdf.Name.XObject,
                                 Subtype=pikepdf.Name.Form, BBox=[0, 0, 200, 200])  # fmt: skip
        parent.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(X=child))
        child = parent
    pdf.pages[0].Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(X=child))
    pdf.save(tmp_path / "f.pdf")
    page = _inspect(tmp_path / "f.pdf")
    assert "RESOURCE_LIMIT" in page["capabilities"]["reasons"]


@pytest.mark.parametrize("content", [b"0 0 1 1 re W n\n" * 200, b"q\n" * 1000])
def test_f012_clip_and_gstate_depth_bounded(tmp_path, content):
    _pdf(tmp_path / "q.pdf", content).save(tmp_path / "q.pdf")
    page = _inspect(tmp_path / "q.pdf")
    assert "RESOURCE_LIMIT" in page["capabilities"]["reasons"]


def test_f009_shared_and_cyclic_kids_walked_once(tmp_path):
    pdf = _pdf(tmp_path / "k.pdf", b"")
    field = pdf.make_indirect(pikepdf.Dictionary(T="a"))
    field.Kids = pikepdf.Array([field, field])  # 修正前約 2^33 步
    pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([field]))
    pdf.save(tmp_path / "k.pdf")
    started = time.monotonic()
    document = analyzer.open_document(str(tmp_path / "k.pdf"))
    assert time.monotonic() - started < FAST
    assert "RESOURCE_LIMIT" not in document.flags["reasons"]
    document.close()


def _js_action(pdf):
    return pdf.make_indirect(pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="app.alert(1)"))


def test_f007_outline_and_parent_field_actions_detected(tmp_path):
    pdf = _pdf(tmp_path / "o.pdf", b"")
    item = pdf.make_indirect(pikepdf.Dictionary(Title="b", A=_js_action(pdf)))
    pdf.Root.Outlines = pdf.make_indirect(pikepdf.Dictionary(First=item, Last=item, Count=1))
    pdf.save(tmp_path / "o.pdf")
    document = analyzer.open_document(str(tmp_path / "o.pdf"))
    assert document.flags["reasons"] == ["ACTIVE_CONTENT"]
    document.close()

    pdf = _pdf(tmp_path / "p.pdf", b"")
    kid = pdf.make_indirect(pikepdf.Dictionary(T="k"))
    parent = pdf.make_indirect(pikepdf.Dictionary(
        T="p", Kids=pikepdf.Array([kid]), AA=pikepdf.Dictionary(K=_js_action(pdf))))  # fmt: skip
    pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([parent]))
    pdf.save(tmp_path / "p.pdf")
    document = analyzer.open_document(str(tmp_path / "p.pdf"))
    assert document.flags["reasons"] == ["ACTIVE_CONTENT"]
    document.close()


def test_f007_plain_hyperlink_not_rejected(tmp_path):
    pdf = _pdf(tmp_path / "u.pdf", b"")
    uri = pikepdf.Dictionary(S=pikepdf.Name.URI, URI="https://example.invalid")
    link = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link,
                              Rect=[0, 0, 10, 10], A=uri)  # fmt: skip
    pdf.pages[0].obj.Annots = pikepdf.Array([pdf.make_indirect(link)])
    pdf.save(tmp_path / "u.pdf")
    document = analyzer.open_document(str(tmp_path / "u.pdf"))
    assert document.flags["active_content"] == []
    document.close()


def test_f003_owner_password_only_rejected(tmp_path):
    pdf = _pdf(tmp_path / "e.pdf", b"BT /F1 12 Tf 20 100 Td (a) Tj ET")
    pdf.save(tmp_path / "e.pdf", encryption=pikepdf.Encryption(owner="owner", user=""))
    document = analyzer.open_document(str(tmp_path / "e.pdf"))
    assert document.flags["encrypted"] is True
    assert document.flags["reasons"] == ["ENCRYPTED_DOCUMENT"]
    with pytest.raises(ProtocolError) as exc:
        analyzer.inspect_page(document, 0)
    assert exc.value.code == "ENCRYPTED_DOCUMENT"
    document.close()


def _sig_value():
    return pikepdf.Dictionary(Type=pikepdf.Name.Sig, Filter=pikepdf.Name("/Adobe.PPKLite"))


def _signed_reasons(path: Path) -> list[str]:
    document = analyzer.open_document(str(path))
    try:
        assert document.flags["signed"] is True
        return document.flags["reasons"]
    finally:
        document.close()


def test_f008_inherited_ft_signature_detected(tmp_path):
    pdf = _pdf(tmp_path / "s.pdf", b"")
    parent = pdf.make_indirect(pikepdf.Dictionary(T="sig", FT=pikepdf.Name.Sig))
    kid = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Widget, Rect=[0, 0, 10, 10],
        Parent=parent, V=_sig_value()))  # fmt: skip
    parent.Kids = pikepdf.Array([kid])
    pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([parent]))
    pdf.save(tmp_path / "s.pdf")
    assert _signed_reasons(tmp_path / "s.pdf") == ["SIGNED_DOCUMENT"]


def test_f008_widget_outside_fields_detected(tmp_path):
    pdf = _pdf(tmp_path / "w.pdf", b"")
    widget = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Widget, Rect=[0, 0, 10, 10],
        FT=pikepdf.Name.Sig, V=_sig_value()))  # fmt: skip
    pdf.pages[0].obj.Annots = pikepdf.Array([widget])
    pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([]))
    pdf.save(tmp_path / "w.pdf")
    assert _signed_reasons(tmp_path / "w.pdf") == ["SIGNED_DOCUMENT"]


def test_f008_deep_field_tree_not_supported(tmp_path):
    pdf = _pdf(tmp_path / "d.pdf", b"")
    node = pdf.make_indirect(pikepdf.Dictionary(T="leaf", FT=pikepdf.Name.Sig, V=_sig_value()))
    for i in range(100):  # 超過走訪深度上限 → 不得判為 support
        parent = pdf.make_indirect(pikepdf.Dictionary(T=f"n{i}", Kids=pikepdf.Array([node])))
        node.Parent = parent
        node = parent
    pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([node]))
    pdf.save(tmp_path / "d.pdf")
    document = analyzer.open_document(str(tmp_path / "d.pdf"))
    assert document.flags["status"] == "reject"
    assert "RESOURCE_LIMIT" in document.flags["reasons"]
    document.close()


def test_f008_long_parent_chain_not_supported(tmp_path):
    pdf = _pdf(tmp_path / "c.pdf", b"")
    parent = pdf.make_indirect(pikepdf.Dictionary(T="root", FT=pikepdf.Name.Sig, V=_sig_value()))
    for i in range(100):  # 不在 /Fields 的 widget，/Parent 鏈超過繼承查找上限 → 不得判為 support
        parent = pdf.make_indirect(pikepdf.Dictionary(T=f"n{i}", Parent=parent))
    widget = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Widget, Rect=[0, 0, 10, 10],
        Parent=parent))  # fmt: skip
    pdf.pages[0].obj.Annots = pikepdf.Array([widget])
    pdf.save(tmp_path / "c.pdf")
    document = analyzer.open_document(str(tmp_path / "c.pdf"))
    assert document.flags["status"] == "reject"
    assert "RESOURCE_LIMIT" in document.flags["reasons"]
    document.close()


def test_f016_render_pixel_area_bounded(tmp_path):
    _pdf(tmp_path / "big.pdf", b"", media=(0, 0, 14400, 14400)).save(tmp_path / "big.pdf")
    document = analyzer.open_document(str(tmp_path / "big.pdf"))
    with pytest.raises(ProtocolError) as exc:
        analyzer.render_page(document, 0, 150)
    assert exc.value.code == "RESOURCE_LIMIT"
    document.close()


def test_f011_worker_ignores_modules_in_cwd(tmp_path, monkeypatch):
    marker = tmp_path / "pwned.txt"
    for name in ("pymupdf.py", "pikepdf.py"):
        (tmp_path / name).write_text(
            f"import pathlib\npathlib.Path({str(marker)!r}).write_text('x')\n", encoding="utf-8"
        )
    monkeypatch.chdir(tmp_path)
    with DocumentService() as svc:
        opened = svc.open_document(FILES / "T05.pdf")
        assert svc.inspect_page(opened["document_id"], 0)["text_targets"]
    assert not marker.exists()
