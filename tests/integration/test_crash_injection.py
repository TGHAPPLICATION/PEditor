"""儲存交易的中斷注入與磁碟空間不足（G3-03、G3-06；ADR-0020 §3）。"""

import hashlib
import shutil
import subprocess
import sys
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
