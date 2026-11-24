"""ADR-0030：多個 PEditor 視窗同時執行時，開啟中文件的草稿不被另一個視窗列出或刪除。"""

import pytest

from peditor.core.drafts import DraftStore
from peditor.core.protocol import ProtocolError

LOG = [{"params": {}, "base_revision": 0}]


def _save(store, draft_id):
    store.save(draft_id, "/x/a.pdf", "0" * 64, LOG, 1, {})


def test_claimed_draft_hidden_from_other_window(tmp_path):
    a, b = DraftStore(tmp_path), DraftStore(tmp_path)  # 兩個視窗共用同一個草稿區
    draft = a.new_id()
    assert a.claim(draft)
    _save(a, draft)
    assert [d["draft_id"] for d in a.list()] == [draft]  # 持有者自己看得到
    assert b.list() == [] and b.in_use(draft)  # 另一個視窗看不到、判定使用中
    with pytest.raises(ProtocolError, match="另一個 PEditor"):
        b.discard(draft)
    assert (tmp_path / f"{draft}.json").exists()
    assert not b.claim(draft)  # 不能同時持有


def test_released_or_crashed_draft_becomes_recoverable(tmp_path):
    a, b = DraftStore(tmp_path), DraftStore(tmp_path)
    draft = a.new_id()
    a.claim(draft)
    _save(a, draft)
    a.release(draft)  # 正常關閉以外的情況（例如強制結束）由作業系統釋放鎖，效果相同
    assert [d["draft_id"] for d in b.list()] == [draft]
    b.discard(draft)
    assert b.list() == [] and not (tmp_path / f"{draft}.lock").exists()


def test_purge_keeps_draft_in_use(tmp_path):
    now = [1_000_000.0]
    a = DraftStore(tmp_path, now=lambda: now[0])
    draft = a.new_id()
    a.claim(draft)
    _save(a, draft)
    now[0] += 8 * 24 * 3600  # 超過 7 天
    DraftStore(tmp_path, now=lambda: now[0])  # 另一個視窗啟動時 purge
    assert (tmp_path / f"{draft}.json").exists()


def test_claim_rejects_bad_id(tmp_path):
    assert not DraftStore(tmp_path).claim("../x")


def test_lock_held_by_other_process(tmp_path):
    """真的跨行程：子行程持有草稿鎖時看不到；子行程被強制結束後即可復原。"""
    import subprocess
    import sys

    draft = "0123456789abcdef"
    _save(DraftStore(tmp_path), draft)
    code = ("import sys,time;from peditor.core.drafts import DraftStore;"
            f"s=DraftStore({str(tmp_path)!r});assert s.claim({draft!r});"
            "print('held',flush=True);time.sleep(60)")  # fmt: skip
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "held"
        assert DraftStore(tmp_path).list() == []
    finally:
        child.kill()  # 模擬當機或強制結束
        child.wait()
    assert [d["draft_id"] for d in DraftStore(tmp_path).list()] == [draft]


def test_recover_refused_while_other_window_holds_draft(tmp_path):
    """獨立核對（P10）：兩個視窗同時復原同一份草稿時，只有先取得鎖的那個可以。"""
    from peditor.core.service import DocumentService, ServiceError

    draft = "0123456789abcdef"
    _save(DraftStore(tmp_path), draft)
    holder = DraftStore(tmp_path)
    assert holder.claim(draft)  # 另一個視窗正在復原
    with DocumentService(drafts=DraftStore(tmp_path)) as service:
        with pytest.raises(ServiceError, match="另一個 PEditor"):
            service.recover_draft(draft)
    holder.release(draft)
    assert (tmp_path / f"{draft}.json").exists()  # 草稿仍在，之後可復原
