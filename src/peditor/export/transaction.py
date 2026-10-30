"""儲存交易（主行程；ADR-0004、ADR-0020 §3）。不匯入 PDF 程式庫，只處理檔案與 hash。

流程：檢查原檔與目的檔 → 同目錄暫存檔名交給 worker 寫入並驗證 → 比對暫存檔 SHA-256 →
再次檢查 → os.replace 原子取代 →（POSIX）fsync 目錄。任何一步失敗都刪除暫存檔，目的檔不動。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from peditor.core.protocol import ProtocolError

TEMP_PATTERN = re.compile(r"^\.~peditor-[0-9a-f]{16}\.tmp\.pdf$")
STALE_TEMP_S = 600  # 程式中斷留下的暫存檔，超過此秒數才清除（避免刪到其他執行中的寫入）
CHUNK = 1024 * 1024

# crash injection（G3-03）：測試設為 callable，於各階段前被呼叫；產品不設定
fault: Callable[[str], None] | None = None
# 寫入中暫存檔的紀錄檔（UI 設定在本機資料目錄）：程式中斷後下次啟動時清除（P3 U9、ADR-0021）
registry: str | None = None


@dataclass(frozen=True)
class FileState:
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class Destination:
    path: str  # realpath
    state: FileState | None  # 取得 token 時的目的檔狀態；None 表示當時不存在


def file_state(path: str) -> FileState | None:
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ProtocolError("SAVE_FAILED", "無法讀取目的檔") from exc
    try:
        digest = sha256_file(path)
    except OSError as exc:  # 例如被其他程式以禁止讀取的方式鎖定；訊息不帶路徑（CLAUDE.md）
        raise ProtocolError("SAVE_FAILED", "無法讀取目的檔") from exc
    return FileState(st.st_size, st.st_mtime_ns, digest)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def destination(path: str | os.PathLike, overwrite: bool) -> Destination:
    """解析實際路徑（含符號連結）並記錄目的檔狀態。"""
    real = os.path.realpath(os.fspath(path))
    if not real.lower().endswith(".pdf"):
        raise ProtocolError("INVALID_REQUEST", "目的檔必須是 .pdf")
    if not os.path.isdir(os.path.dirname(real)):
        raise ProtocolError("SAVE_FAILED", "目的資料夾不存在")
    if os.path.isdir(real):
        raise ProtocolError("SAVE_FAILED", "目的路徑是資料夾")
    state = file_state(real)
    if state is not None and not overwrite:
        raise ProtocolError("SAVE_FAILED", "目的檔已存在")
    return Destination(real, state)


def is_same_file(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def commit(dest: Destination, source_path: str, source_sha256: str,
           write: Callable[[str], dict]) -> dict:  # fmt: skip
    """write(暫存路徑) 由 worker 建立、驗證並寫入暫存檔，回傳 {output_hash, validation_report}。"""
    if is_same_file(dest.path, source_path):
        raise ProtocolError("INVALID_REQUEST", "不可覆寫原檔")
    _check(dest, source_path, source_sha256)
    folder = os.path.dirname(dest.path)
    _remove_stale(folder)
    temp = os.path.join(folder, f".~peditor-{secrets.token_hex(8)}.tmp.pdf")
    _record(temp, add=True)
    try:
        _stage("write")
        result = write(temp)
        _stage("verify")
        try:
            written = sha256_file(temp)
        except OSError as exc:
            raise ProtocolError("SAVE_FAILED", "無法讀取暫存檔") from exc
        if written != result.get("output_hash"):
            raise ProtocolError("SAVE_FAILED", "暫存檔內容與驗證結果不符")
        _check(dest, source_path, source_sha256)
        _stage("rename")
        try:
            os.replace(temp, dest.path)
        except OSError as exc:
            raise ProtocolError("SAVE_FAILED", "無法取代目的檔") from exc
    except BaseException:
        _remove(temp)
        if not os.path.exists(temp):
            _record(temp, add=False)
        raise
    _record(temp, add=False)
    # 已取代：之後的失敗不能回報為另存失敗，只加警告（P3 triage f010）
    try:
        _fsync_dir(folder)
    except OSError:
        result = {
            **result,
            "warnings": [*result.get("warnings", []), "目錄同步失敗，斷電時可能遺失本次儲存"],
        }
    return result


def _check(dest: Destination, source_path: str, source_sha256: str) -> None:
    try:
        source = sha256_file(source_path)
    except OSError:
        source = None
    if source != source_sha256:
        raise ProtocolError("REVISION_CONFLICT", "原檔已被外部修改")
    if file_state(dest.path) != dest.state:
        raise ProtocolError("REVISION_CONFLICT", "目的檔已被外部修改")


def _stage(name: str) -> None:
    if fault is not None:
        fault(name)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass  # 不存在，或刪不掉時由下次寫入同一資料夾時清除


def _remove_stale(folder: str) -> None:
    """刪除本程式先前中斷時留下、超過 STALE_TEMP_S 的暫存檔（含文件內容，不可長期保留）。"""
    now = time.time()
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        if not TEMP_PATTERN.match(name):
            continue
        path = os.path.join(folder, name)
        try:
            if now - os.stat(path).st_mtime > STALE_TEMP_S:
                os.remove(path)
        except OSError:
            continue


def _recorded() -> list[str]:
    try:
        with open(registry, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, TypeError, RecursionError):  # 巢狀過深的 JSON 亦視為損壞
        return []
    return [p for p in data if isinstance(p, str)] if isinstance(data, list) else []


def _record(temp: str, add: bool) -> None:
    """盡力而為：紀錄失敗不影響另存（暫存檔仍會由下次寫入同資料夾時清除）。"""
    if registry is None:
        return
    paths = [p for p in _recorded() if p != temp] + ([temp] if add else [])
    try:
        with open(registry, "w", encoding="utf-8") as fh:
            json.dump(paths, fh)
    except OSError:
        pass


def cleanup_recorded() -> int:
    """啟動時刪除上次中斷留下的暫存檔（只刪符合本程式命名的檔案），回傳刪除數。"""
    if registry is None:
        return 0
    removed, kept = 0, []
    for path in _recorded():
        if not TEMP_PATTERN.match(os.path.basename(path)):
            continue
        try:
            os.remove(path)
            removed += 1
        except FileNotFoundError:
            pass
        except OSError:
            kept.append(path)
    try:
        with open(registry, "w", encoding="utf-8") as fh:
            json.dump(kept, fh)
    except OSError:
        pass
    return removed


def _fsync_dir(folder: str) -> None:
    if os.name != "posix":
        return  # Windows 不支援開啟資料夾 fsync；os.replace 為 MoveFileEx 取代
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
