"""復原草稿（G3-07；spec P3、ADR-0020 §5）：由使用者選擇開啟、保留 7 天。"""

import json
import shutil
import sys
from pathlib import Path

import pytest

from peditor.core import drafts
from peditor.core.protocol import ProtocolError
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


def test_draft_errors_carry_no_path_and_do_not_undo_edit(manifest_rows, tmp_path, monkeypatch):
    """U4／f007：草稿區不可用回不含路徑的 SAVE_FAILED；寫草稿失敗時編輯照常生效，只加警告。"""
    blocker = tmp_path / "not-a-folder"
    blocker.write_bytes(b"x")
    with pytest.raises(ProtocolError) as exc:
        drafts.DraftStore(blocker / "drafts")
    assert exc.value.code == "SAVE_FAILED" and str(tmp_path) not in exc.value.message

    store = drafts.DraftStore(tmp_path / "drafts")

    def failing_save(*args, **kwargs):
        raise ProtocolError("SAVE_FAILED", "無法寫入復原草稿")

    monkeypatch.setattr(store, "save", failing_save)
    row = _row(manifest_rows, "T01")
    with DocumentService(drafts=store) as service:
        doc = service.open_document(FILES / "T01.pdf")["document_id"]
        span_id = service.find_text(doc, 0, row["original_text"])
        region = [float(v) for v in row["editable_region_pt"].split(",")]
        plan = service.plan_text_edit(doc, span_id, row["new_text"], "prefer_a", 0, region)
        result = service.apply_edit(doc, plan["plan_id"], 0)
        assert result["new_revision"] == 1 and result["warnings"]
        assert service.history(doc) == {"revision": 1, "undo": 1, "redo": 0}
        service.find_text(doc, 0, row["new_text"])


def _good_draft(draft_id):
    return {"draft_id": draft_id, "path": "x.pdf", "sha256": "0" * 64,
            "log": [{"params": {}, "base_revision": 0}], "position": 1,
            "saved_at": 1_000_000.0}  # fmt: skip


@pytest.mark.parametrize(
    "change",
    [{"draft_id": "fedcba9876543210"}, {"path": 1}, {"sha256": "g" * 64}, {"sha256": "0" * 63},
     {"log": {}}, {"position": True}, {"position": 2}, {"position": -1},
     {"log": [{"params": [], "base_revision": 0}]}, {"log": [{"params": {}, "base_revision": -1}]},
     {"log": [{"params": {}, "base_revision": False}]}, {"log": ["x"]},
     {"saved_at": float("nan")}, {"saved_at": 1_000_000.0 + 61}],
)  # fmt: skip
def test_draft_structure_validated(tmp_path, change):
    """P3 triage f001：結構不符或時間無效的草稿視為損壞，不載入、不列出並刪除。"""
    draft_id = "0123456789abcdef"
    store = drafts.DraftStore(tmp_path, now=lambda: 1_000_000.0)
    path = tmp_path / f"{draft_id}.json"
    path.write_text(json.dumps(_good_draft(draft_id)), encoding="utf-8")
    assert store.load(draft_id) is not None  # 對照：未改動的草稿有效
    path.write_text(json.dumps({**_good_draft(draft_id), **change}), encoding="utf-8")
    assert store.list() == [] and not path.exists()
    path.write_text(json.dumps({**_good_draft(draft_id), **change}), encoding="utf-8")
    assert store.load(draft_id) is None and not path.exists()


def test_recover_failure_closes_document(manifest_rows, tmp_path, monkeypatch):
    """重播時任何例外（不只 ServiceError）都關閉開啟一半的文件、草稿保留（P3 triage f001）。"""
    row = _row(manifest_rows, "T01")
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "T01.pdf", source)
    store = drafts.DraftStore(tmp_path / "drafts")
    service = DocumentService(drafts=store)
    try:
        _edit(service, service.open_document(source)["document_id"], row)
    finally:
        service.close()
    with DocumentService(drafts=store) as service:
        draft_id = service.list_drafts()[0]["draft_id"]
        original = service._doc_call

        def failing(document_id, operation, *args):
            if operation == "replay":
                raise RuntimeError("boom")
            return original(document_id, operation, *args)

        monkeypatch.setattr(service, "_doc_call", failing)
        with pytest.raises(RuntimeError):
            service.recover_draft(draft_id)
        assert service._docs == {}
        assert [d["draft_id"] for d in service.list_drafts()] == [draft_id]
