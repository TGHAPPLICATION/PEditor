"""ADR-0033：文字擷取 worker 操作（只讀；目前工作文件，含已套用、未另存的修改）。"""

from pathlib import Path

import pymupdf
import pytest

from peditor.core.service import DocumentService, ServiceError
from peditor.worker import analyzer

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_extract_page_text_including_unsaved_edit():
    with DocumentService() as service:
        doc = service.open_document(FILES / "F04.pdf")["document_id"]
        assert service.extract_text(doc, 0) == {"text": "Hello World", "limited": False}
        target = next(t for t in service.inspect_page(doc, 0)["text_targets"]
                      if "World" in t["text"])  # fmt: skip
        plan = service.plan_text_edit(doc, target["target_id"], "Hello Earth", "prefer_a", 0)
        service.apply_edit(doc, plan["plan_id"], 0)
        assert service.extract_text(doc, 0)["text"] == "Hello Earth"  # 未另存的修改也擷取


def test_extract_chinese_lines_trimmed():
    with DocumentService() as service:
        doc = service.open_document(FILES / "T05.pdf")["document_id"]
        text = service.extract_text(doc, 0)["text"]
    assert text.startswith("T05\n本府辦理年度資訊安全稽核")
    assert all(line == line.rstrip() for line in text.splitlines())


def test_image_only_page_has_no_text():
    with DocumentService() as service:
        doc = service.open_document(FILES / "I02.pdf")["document_id"]
        assert service.extract_text(doc, 1) == {"text": "", "limited": False}


def test_bad_page_index_rejected():
    with DocumentService() as service:
        doc = service.open_document(FILES / "F04.pdf")["document_id"]
        for bad in (-1, 1, "0", True):
            with pytest.raises(ServiceError):
                service.extract_text(doc, bad)


def test_limited_page_not_extracted_and_char_limit(monkeypatch):
    document = analyzer.open_document(str(FILES / "F04.pdf"))
    try:
        analyzer.inspect_page(document, 0)
        document.limited_pages.add(0)  # 內容超過處理上限的頁不交給 MuPDF
        assert analyzer.extract_text(document, 0) == {"text": "", "limited": True}
        document.limited_pages.clear()
        monkeypatch.setattr(analyzer, "MAX_EXTRACT_CHARS", 5)
        with pytest.raises(Exception, match="擷取上限"):
            analyzer.extract_text(document, 0)
    finally:
        document.close()


def test_multi_page(tmp_path):
    path = tmp_path / "兩頁.pdf"
    pdf = pymupdf.open()
    for text in ("first page", "second page"):
        pdf.new_page().insert_text((72, 72), text)
    pdf.save(path)
    with DocumentService() as service:
        doc = service.open_document(path)["document_id"]
        texts = [service.extract_text(doc, i)["text"] for i in (0, 1)]
    assert texts == ["first page", "second page"]


def test_bool_page_index_rejected_on_multi_page():
    """P12 獨立核對：bool 是 int 的子類別，True 不得當成第 2 頁（I02 有 2 頁）。"""
    with DocumentService() as service:
        doc = service.open_document(FILES / "I02.pdf")["document_id"]
        for bad in (True, False):
            with pytest.raises(ServiceError) as info:
                service.extract_text(doc, bad)
            assert info.value.code == "INVALID_REQUEST"
