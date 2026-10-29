"""復原草稿（G3-07；spec P3、ADR-0020 §5）：由使用者選擇開啟、保留 7 天。"""

import json
import shutil
import sys
from pathlib import Path

import pytest

from peditor.core import drafts
from peditor.core.service import DocumentService, ServiceError

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _row(manifest_rows, fixture_id):
    return next(r for r in manifest_rows if r["fixture_id"] == fixture_id)


def _edit(service, doc, row, revision=0):
    span_id = service.find_text(doc, 0, row["original_text"])
    region = [float(v) for v in row["editable_region_pt"].split(",")]
    plan = service.plan_text_edit(doc, span_id, row["new_text"], "prefer_a", revision, region)
    return service.apply_edit(doc, plan["plan_id"], revision)["new_revision"]


def test_draft_opt_in_and_expiry(manifest_rows, tmp_path):
    row = _row(manifest_rows, "T01")
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "T01.pdf", source)
    store_dir = tmp_path / "drafts"

    # 編輯後異常結束（未 close_document）：草稿留在草稿區
    service = DocumentService(drafts=drafts.DraftStore(store_dir))
    try:
        doc = service.open_document(source)["document_id"]
        assert service.list_drafts() == []  # 尚未編輯不留草稿
        _edit(service, doc, row)
    finally:
        service.close()
    saved = list(store_dir.glob("*.json"))
    assert len(saved) == 1
    if sys.platform != "win32":
        assert saved[0].stat().st_mode & 0o077 == 0  # 只有使用者可讀寫

    with DocumentService(drafts=drafts.DraftStore(store_dir)) as service:
        listed = service.list_drafts()
        assert [d["operations"] for d in listed] == [1]
        assert "log" not in listed[0]  # 列表不含編輯內容
        # 不自動開啟：直接開原檔是未修改狀態
        plain = service.open_document(source)
        assert plain["revision"] == 0
        service.find_text(plain["document_id"], 0, row["original_text"])
        service.close_document(plain["document_id"])
        # 使用者選擇後才復原
        recovered = service.recover_draft(listed[0]["draft_id"])
        doc = recovered["document_id"]
        service.find_text(doc, 0, row["new_text"])
        assert service.history(doc)["undo"] == 1
        rev = service.undo(doc, recovered["revision"])["new_revision"]
        service.find_text(doc, 0, row["original_text"])
        assert service.list_drafts() == []  # 撤銷到沒有編輯：草稿刪除
        service.redo(doc, rev)
        assert len(service.list_drafts()) == 1
        service.close_document(doc)  # 正常關閉：刪除草稿
        assert service.list_drafts() == []


def test_draft_rejected_when_source_changed(manifest_rows, tmp_path):
    row = _row(manifest_rows, "T01")
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "T01.pdf", source)
    store = drafts.DraftStore(tmp_path / "drafts")
    service = DocumentService(drafts=store)
    try:
        _edit(service, service.open_document(source)["document_id"], row)
    finally:
        service.close()
    source.write_bytes(source.read_bytes() + b"\n%changed\n")
    with DocumentService(drafts=store) as service:
        draft_id = service.list_drafts()[0]["draft_id"]
        with pytest.raises(ServiceError) as exc:
            service.recover_draft(draft_id)
        assert exc.value.code == "REVISION_CONFLICT"
        assert len(service.list_drafts()) == 1  # 草稿保留，由使用者決定是否捨棄
        service.discard_draft(draft_id)
        assert service.list_drafts() == []


def test_draft_expires_after_7_days(tmp_path):
    clock = [1_000_000.0]
    store = drafts.DraftStore(tmp_path, now=lambda: clock[0])
    store.save("0123456789abcdef", "x.pdf", "0" * 64, [{"params": {}, "base_revision": 0}], 1)
    clock[0] += drafts.RETENTION_S - 1
    assert len(store.list()) == 1
    clock[0] += 2
    assert store.list() == [] and list(tmp_path.glob("*.json")) == []

    store.save("fedcba9876543210", "x.pdf", "0" * 64, [], 0)
    clock[0] += drafts.RETENTION_S + 1
    drafts.DraftStore(tmp_path, now=lambda: clock[0])  # 建立草稿區時即清除
    assert list(tmp_path.glob("*.json")) == []


def test_draft_store_ignores_bad_ids_and_files(tmp_path):
    store = drafts.DraftStore(tmp_path)
    assert store.load("../../etc/passwd") is None
    (tmp_path / "0123456789abcdef.json").write_text("{not json", encoding="utf-8")
    assert store.list() == []
    (tmp_path / "aaaaaaaaaaaaaaaa.json").write_text(json.dumps([1]), encoding="utf-8")
    assert store.list() == []
