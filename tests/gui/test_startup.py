"""P4 U8：啟動時的本機儲存接線（ADR-0021 §2 例外）。

建立草稿區、設定暫存檔紀錄位置、清除上次中斷留下的暫存檔。"""

import json

from peditor.core import drafts
from peditor.core.protocol import ProtocolError
from peditor.export import transaction
from peditor.ui.app import prepare_storage


def _leftover(tmp_path, monkeypatch):
    data_dir = tmp_path / "PEditor"
    monkeypatch.setattr(drafts, "default_dir", lambda: data_dir / "drafts")
    monkeypatch.setattr(transaction, "registry", None)  # 測試結束時還原
    data_dir.mkdir()
    temp = tmp_path / ".~peditor-00000000000000aa.tmp.pdf"
    temp.write_bytes(b"content")
    (data_dir / "pending-temps.json").write_text(json.dumps([str(temp)]), encoding="utf-8")
    return data_dir, temp


def test_prepare_storage_wires_drafts_and_cleans_temps(tmp_path, monkeypatch):
    data_dir, temp = _leftover(tmp_path, monkeypatch)
    store = prepare_storage()
    assert isinstance(store, drafts.DraftStore) and store.folder == data_dir / "drafts"
    assert transaction.registry == str(data_dir / "pending-temps.json")
    assert not temp.exists() and transaction._recorded() == []


def test_prepare_storage_without_drafts_still_cleans(tmp_path, monkeypatch):
    """草稿區不可用時照常啟動（不保存草稿），暫存檔仍清除。"""
    data_dir, temp = _leftover(tmp_path, monkeypatch)

    def unavailable(*args, **kwargs):
        raise ProtocolError("SAVE_FAILED", "無法使用復原草稿區")

    monkeypatch.setattr(drafts, "DraftStore", unavailable)
    assert prepare_storage() is None
    assert transaction.registry == str(data_dir / "pending-temps.json") and not temp.exists()
