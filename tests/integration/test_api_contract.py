"""G1-06：open_document、inspect_page、assess_editability 的合約（spec §7）。"""

import re
from pathlib import Path

import pytest

from peditor.core.service import ServiceError

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
TARGET_ID = re.compile(r"^[ti]:r\d+:p\d+:s\d+\.\d+:o\d+:f[^:]*:g[0-9a-f]{12}$")


def test_open_inspect_assess(service, available_rows):
    row = next(r for r in available_rows if r["fixture_id"] == "T01")
    opened = service.open_document(FILES / "T01.pdf")
    assert set(opened) >= {"document_id", "revision", "sha256", "page_count", "document_flags"}
    assert opened["revision"] == 0
    assert opened["sha256"] == row["sha256"]
    assert opened["page_count"] == 1
    assert opened["document_flags"]["status"] == "support"
    doc = opened["document_id"]

    page = service.inspect_page(doc, 0, expected_revision=0)
    assert set(page) >= {"page_geometry", "text_targets", "image_targets", "capabilities"}
    assert page["page_geometry"]["rotation"] == 0
    assert page["text_targets"], "T01 應有文字目標"
    for target in page["text_targets"]:
        assert TARGET_ID.match(target["target_id"]), target["target_id"]
        assert target["capability"]["status"] in {"support", "readonly", "reject"}
    ids = [t["target_id"] for t in page["text_targets"]]
    assert len(set(ids)) == len(ids)
    # 同一 revision 重查得到相同 target_id（可重現）
    assert [t["target_id"] for t in service.inspect_page(doc, 0)["text_targets"]] == ids

    assessment = service.assess_editability(doc)
    assert assessment["document"] == {"status": "support", "reasons": []}
    assert [p["page_index"] for p in assessment["pages"]] == [0]
    service.close_document(doc)


def test_contract_errors(service):
    doc = service.open_document(FILES / "T01.pdf")["document_id"]
    with pytest.raises(ServiceError) as exc:
        service.inspect_page(doc, 0, expected_revision=5)
    assert exc.value.code == "REVISION_CONFLICT" and exc.value.retryable
    with pytest.raises(ServiceError) as exc:
        service.inspect_page(doc, 3)
    assert exc.value.code == "INVALID_REQUEST"
    service.close_document(doc)

    encrypted = service.open_document(FILES / "U02.pdf")
    assert encrypted["document_flags"]["reasons"] == ["ENCRYPTED_DOCUMENT"]
    with pytest.raises(ServiceError) as exc:
        service.inspect_page(encrypted["document_id"], 0)
    assert exc.value.code == "ENCRYPTED_DOCUMENT"
    # 錯誤訊息不含檔案路徑
    assert str(FILES) not in exc.value.message and "U02" not in exc.value.message
