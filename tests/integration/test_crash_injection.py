"""儲存交易的中斷注入與磁碟空間不足（G3-03、G3-06；ADR-0020 §3）。"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from peditor.core.protocol import ProtocolError
from peditor.core.service import DocumentService, ServiceError
from peditor.export import transaction

HERE = Path(__file__).resolve().parent
FILES = HERE.parents[0] / "fixtures" / "files"
EXISTING = b"%PDF-1.4\n% existing destination content\n"


def _row(manifest_rows, fixture_id):
    return next(r for r in manifest_rows if r["fixture_id"] == fixture_id)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _temps(folder: Path) -> list[Path]:
    return [p for p in folder.iterdir() if transaction.TEMP_PATTERN.match(p.name)]


@pytest.mark.parametrize("stage", ["write", "verify", "rename"])
def test_interrupt_each_stage(manifest_rows, tmp_path, stage):
    """在寫入、驗證、rename 前中止整個主行程：原檔與既有目的檔都完整。"""
    row = _row(manifest_rows, "T01")
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "T01.pdf", source)
    dest = tmp_path / "dest.pdf"
    dest.write_bytes(EXISTING)
    result = subprocess.run(
        [sys.executable, str(HERE / "crash_child.py"), str(source), str(dest), stage,
         row["original_text"], row["new_text"], row["editable_region_pt"]],
        capture_output=True, timeout=120,
    )  # fmt: skip
    assert result.returncode == 17, result.stderr
    assert _sha(source) == row["sha256"]
    assert dest.read_bytes() == EXISTING
    leftovers = _temps(tmp_path)
    if stage == "write":
        assert leftovers == []  # 暫存檔尚未建立
    else:  # 已寫好的暫存檔留在原處，下次寫入同一資料夾時清除
        assert len(leftovers) == 1


def test_stale_temp_removed_on_next_save(manifest_rows, tmp_path, monkeypatch, service):
    """中斷留下的暫存檔（含文件內容）在下次寫入同一資料夾時刪除（spec P3 暫存保留限制）。"""
    stale = tmp_path / ".~peditor-0123456789abcdef.tmp.pdf"
    stale.write_bytes(b"sensitive")
    other = tmp_path / "unrelated.tmp.pdf"
    other.write_bytes(b"not ours")
    monkeypatch.setattr(transaction, "STALE_TEMP_S", -1)
    doc = service.open_document(FILES / "T01.pdf")["document_id"]
    try:
        service.export_document(doc, service.destination_token(tmp_path / "o.pdf"), 0)
    finally:
        service.close_document(doc)
    assert not stale.exists() and other.read_bytes() == b"not ours"


def test_stale_temp_threshold(tmp_path):
    """只刪超過 10 分鐘的暫存檔：其他執行中的寫入（剛建立的暫存檔）不受影響（ADR-0020 §3.3）。"""
    old = tmp_path / ".~peditor-00000000000000aa.tmp.pdf"
    fresh = tmp_path / ".~peditor-00000000000000bb.tmp.pdf"
    for path in (old, fresh):
        path.write_bytes(b"content")
    stamp = time.time() - transaction.STALE_TEMP_S - 60
    os.utime(old, (stamp, stamp))
    transaction._remove_stale(str(tmp_path))
    assert not old.exists() and fresh.exists()


@pytest.mark.parametrize("stage", ["write", "verify", "rename"])
def test_exception_at_stage_cleans_up(tmp_path, monkeypatch, stage):
    """同一行程內的例外：刪除暫存檔、目的檔不動。"""
    source = tmp_path / "src.pdf"
    source.write_bytes(b"source")
    dest = transaction.destination(tmp_path / "dest.pdf", overwrite=False)
    payload = b"%PDF-1.4 new"

    def write(temp: str) -> dict:
        with open(temp, "xb") as fh:
            fh.write(payload)
        return {"output_hash": hashlib.sha256(payload).hexdigest()}

    def fault(name):
        if name == stage:
            raise KeyboardInterrupt

    monkeypatch.setattr(transaction, "fault", fault)
    with pytest.raises(KeyboardInterrupt):
        transaction.commit(dest, str(source), hashlib.sha256(b"source").hexdigest(), write)
    assert not (tmp_path / "dest.pdf").exists() and _temps(tmp_path) == []


def test_disk_full_preserves_destination(tmp_path):
    """G3-06：worker 寫暫存檔時空間不足（模擬 ENOSPC）：回 SAVE_FAILED，既有目的檔不變、無暫存檔。

    真實磁碟填滿未測（ADR-0020 後果）；worker 端刪除部分檔另見 test_transaction.py::
    test_failure_no_partial_output。"""
    source = tmp_path / "src.pdf"
    source.write_bytes(b"source")
    target = tmp_path / "dest.pdf"
    target.write_bytes(EXISTING)
    dest = transaction.destination(target, overwrite=True)

    def write(temp: str) -> dict:
        with open(temp, "xb") as fh:
            fh.write(b"%PDF-1.4 partial")
        raise ProtocolError("SAVE_FAILED", "無法寫入目的檔")  # worker 回報的錯誤

    with pytest.raises(ProtocolError) as exc:
        transaction.commit(dest, str(source), hashlib.sha256(b"source").hexdigest(), write)
    assert exc.value.code == "SAVE_FAILED"
    assert target.read_bytes() == EXISTING and _temps(tmp_path) == []


def test_temp_hash_mismatch_rejected(tmp_path):
    """暫存檔內容與 worker 回報的 hash 不符（寫入後被改動或毀損）：不取代目的檔。"""
    source = tmp_path / "src.pdf"
    source.write_bytes(b"source")
    target = tmp_path / "dest.pdf"
    target.write_bytes(EXISTING)
    dest = transaction.destination(target, overwrite=True)

    def write(temp: str) -> dict:
        with open(temp, "xb") as fh:
            fh.write(b"%PDF-1.4 corrupted")
        return {"output_hash": "0" * 64}

    with pytest.raises(ProtocolError) as exc:
        transaction.commit(dest, str(source), hashlib.sha256(b"source").hexdigest(), write)
    assert exc.value.code == "SAVE_FAILED"
    assert target.read_bytes() == EXISTING and _temps(tmp_path) == []


# worker 寫出一半暫存檔後異常結束（不經 Python 清理）
_CRASHING_WORKER = """
import os, sys
from peditor.worker import export, server

def crash(document, destination):
    with open(destination, "xb") as fh:
        fh.write(b"%PDF-1.4 partial")
        fh.flush()
    os._exit(1)

export.export_document = crash
sys.exit(server.main())
"""


def test_worker_crash_during_export_preserves_destination(tmp_path):
    """worker 在寫暫存檔途中異常結束：主行程回 WORKER_FAILED，刪除暫存檔，目的檔不變。"""
    target = tmp_path / "dest.pdf"
    target.write_bytes(EXISTING)
    with DocumentService(command=[sys.executable, "-P", "-c", _CRASHING_WORKER]) as service:
        doc = service.open_document(FILES / "T01.pdf")["document_id"]
        token = service.destination_token(target, overwrite=True)
        with pytest.raises(ServiceError) as exc:
            service.export_document(doc, token, 0)
        assert exc.value.code == "WORKER_FAILED"
    assert target.read_bytes() == EXISTING and _temps(tmp_path) == []


def test_os_errors_carry_no_path(tmp_path, monkeypatch, service):
    """U4／f010：讀不到目的檔、暫存檔不見，都回不含路徑的 SAVE_FAILED（CLAUDE.md）。"""
    locked = tmp_path / "locked.pdf"
    locked.write_bytes(EXISTING)
    original = transaction.sha256_file

    def deny(path):
        if path == str(locked.resolve()):
            raise PermissionError(13, "Permission denied", path)
        return original(path)

    monkeypatch.setattr(transaction, "sha256_file", deny)
    with pytest.raises(ServiceError) as exc:
        service.destination_token(locked, overwrite=True)
    assert exc.value.code == "SAVE_FAILED" and str(tmp_path) not in str(exc.value)
    monkeypatch.undo()

    source = tmp_path / "src.pdf"
    source.write_bytes(b"source")
    dest = transaction.destination(tmp_path / "dest.pdf", overwrite=False)
    with pytest.raises(ProtocolError) as perr:  # worker 回報成功但沒有建立暫存檔
        transaction.commit(dest, str(source), hashlib.sha256(b"source").hexdigest(),
                           lambda temp: {"output_hash": "0" * 64})  # fmt: skip
    assert perr.value.code == "SAVE_FAILED" and str(tmp_path) not in perr.value.message


def test_fsync_failure_after_replace_is_warning(tmp_path, monkeypatch):
    """目的檔已取代後的目錄同步失敗只加警告，不回報另存失敗（f010）。"""
    source = tmp_path / "src.pdf"
    source.write_bytes(b"source")
    dest = transaction.destination(tmp_path / "dest.pdf", overwrite=False)
    payload = b"%PDF-1.4 new"

    def write(temp: str) -> dict:
        with open(temp, "xb") as fh:
            fh.write(payload)
        return {"output_hash": hashlib.sha256(payload).hexdigest()}

    def broken_fsync(folder):
        raise OSError(5, "I/O error", folder)

    monkeypatch.setattr(transaction, "_fsync_dir", broken_fsync)
    result = transaction.commit(dest, str(source), hashlib.sha256(b"source").hexdigest(), write)
    assert (tmp_path / "dest.pdf").read_bytes() == payload
    assert result["warnings"] and str(tmp_path) not in result["warnings"][0]


def _commit_with(tmp_path, monkeypatch, stage_hook, name="dest.pdf"):
    source = tmp_path / "src.pdf"
    source.write_bytes(b"source")
    dest = transaction.destination(tmp_path / name, overwrite=False)
    payload = b"%PDF-1.4 new"

    def write(temp: str) -> dict:
        with open(temp, "xb") as fh:
            fh.write(payload)
        return {"output_hash": hashlib.sha256(payload).hexdigest()}

    monkeypatch.setattr(transaction, "fault", stage_hook)
    return transaction.commit(dest, str(source), hashlib.sha256(b"source").hexdigest(), write)


def test_temp_recorded_while_writing(tmp_path, monkeypatch):
    """P3 U9：寫入期間暫存檔路徑記在紀錄檔；完成或失敗清除後移除紀錄。"""
    monkeypatch.setattr(transaction, "registry", str(tmp_path / "pending-temps.json"))
    seen = []
    _commit_with(tmp_path, monkeypatch, lambda name: seen.append(transaction._recorded()))
    assert len(seen) == 3 and all(len(s) == 1 for s in seen)
    assert transaction.TEMP_PATTERN.match(os.path.basename(seen[0][0]))
    assert transaction._recorded() == []

    def fail(name):
        if name == "verify":
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _commit_with(tmp_path, monkeypatch, fail, "dest2.pdf")
    assert transaction._recorded() == [] and _temps(tmp_path) == []
    assert not (tmp_path / "dest2.pdf").exists()


def test_cleanup_recorded_removes_only_own_temps(tmp_path, monkeypatch):
    """啟動時清除：只刪紀錄中符合本程式命名的檔案；不存在的略過；紀錄檔損壞時不刪任何檔。"""
    registry = tmp_path / "pending-temps.json"
    monkeypatch.setattr(transaction, "registry", str(registry))
    left = tmp_path / ".~peditor-00000000000000aa.tmp.pdf"
    other = tmp_path / "important.pdf"
    for path in (left, other):
        path.write_bytes(b"content")
    gone = tmp_path / ".~peditor-00000000000000bb.tmp.pdf"
    registry.write_text(json.dumps([str(left), str(other), str(gone), 5]), encoding="utf-8")
    assert transaction.cleanup_recorded() == 1
    assert not left.exists() and other.exists()
    assert transaction._recorded() == []

    left.write_bytes(b"content")
    registry.write_text("{broken", encoding="utf-8")
    assert transaction.cleanup_recorded() == 0 and left.exists()
    monkeypatch.setattr(transaction, "registry", None)  # 未設定紀錄檔（CLI）：不做任何事
    assert transaction.cleanup_recorded() == 0 and left.exists()
