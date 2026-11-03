"""復原草稿（主行程；spec P3、ADR-0020 §5）。

草稿是開啟中文件的 command log（含新文字，屬敏感內容），存在使用者本機資料目錄，
不放在文件旁。不自動開啟：只列出，由使用者選擇後才復原。保留 7 天，逾期即刪。
檔案系統錯誤一律轉成不含路徑的 SAVE_FAILED（CLAUDE.md；P3 獨立核對 V6）。
"""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import sys
import time
from pathlib import Path

from peditor.core.protocol import ProtocolError

RETENTION_S = 7 * 24 * 3600
_NAME = re.compile(r"^[0-9a-f]{16}\.json$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def default_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "PEditor" / "drafts"


class DraftStore:
    def __init__(self, folder: str | os.PathLike | None = None, now=time.time) -> None:
        self.folder = Path(folder) if folder is not None else default_dir()
        self._now = now
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ProtocolError("SAVE_FAILED", "無法使用復原草稿區") from exc
        self.purge()

    def new_id(self) -> str:
        return secrets.token_hex(8)

    def save(self, draft_id: str, path: str, sha256: str, log: list[dict], position: int) -> None:
        """以暫存檔＋原子取代寫入；POSIX 權限 0600。"""
        data = {"draft_id": draft_id, "path": path, "sha256": sha256, "log": log,
                "position": position, "saved_at": self._now()}  # fmt: skip
        target = self._file(draft_id)
        temp = target.with_name(f".{target.name}.{secrets.token_hex(4)}.tmp")
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as exc:
            raise ProtocolError("SAVE_FAILED", "無法寫入復原草稿") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp, target)
        except BaseException as exc:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, OSError):
                raise ProtocolError("SAVE_FAILED", "無法寫入復原草稿") from exc
            raise

    def load(self, draft_id: str) -> dict | None:
        if not _NAME.match(f"{draft_id}.json"):
            return None
        try:
            data = json.loads(self._file(draft_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not _valid(data, draft_id) or self._expired(data):  # 損壞或逾期：刪除（P3 triage f001）
            self.discard(draft_id)
            return None
        return data

    def list(self) -> list[dict]:
        """未逾期的草稿摘要（不含 command log 內容）；逾期或損壞的草稿一併刪除。"""
        self.purge()
        out = []
        for name in sorted(self._names()):
            if not _NAME.match(name):
                continue
            data = self.load(name[:-5])
            if data is None:
                continue
            out.append({"draft_id": data["draft_id"], "path": data["path"],
                        "sha256": data["sha256"], "operations": data["position"],
                        "saved_at": data["saved_at"]})  # fmt: skip
        return out

    def discard(self, draft_id: str) -> None:
        if _NAME.match(f"{draft_id}.json"):
            try:
                self._file(draft_id).unlink(missing_ok=True)
            except OSError as exc:
                raise ProtocolError("SAVE_FAILED", "無法刪除復原草稿") from exc

    def purge(self) -> None:
        for name in self._names():
            path = self.folder / name
            if name.endswith(".tmp") and name.startswith("."):
                self._remove_if_old(path)
            elif _NAME.match(name):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    self._remove_if_old(path)
                    continue
                if not _valid(data, name[:-5]) or self._expired(data):
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass  # 下次列出或建立草稿區時再試

    def _names(self) -> list[str]:
        try:
            return os.listdir(self.folder)
        except OSError as exc:
            raise ProtocolError("SAVE_FAILED", "無法讀取復原草稿區") from exc

    def _expired(self, data: dict) -> bool:
        saved = data.get("saved_at")
        if not isinstance(saved, (int, float)) or not math.isfinite(saved):
            return True
        age = self._now() - saved
        return age > RETENTION_S or age < -60  # 未來時間（時鐘錯誤）視為無效，不得無限保留

    def _remove_if_old(self, path: Path) -> None:
        try:
            if self._now() - path.stat().st_mtime > RETENTION_S:
                path.unlink()
        except OSError:
            pass

    def _file(self, draft_id: str) -> Path:
        return self.folder / f"{draft_id}.json"


def _valid(data, draft_id: str) -> bool:
    """草稿結構（P3 triage f001）：不符即視為損壞。"""
    if not isinstance(data, dict) or data.get("draft_id") != draft_id:
        return False
    log, position = data.get("log"), data.get("position")
    if not (isinstance(data.get("path"), str) and isinstance(data.get("sha256"), str)
            and _SHA256.match(data["sha256"]) and isinstance(log, list)
            and isinstance(position, int) and not isinstance(position, bool)
            and 0 <= position <= len(log)):  # fmt: skip
        return False
    return all(isinstance(e, dict) and isinstance(e.get("params"), dict)
               and isinstance(e.get("base_revision"), int)
               and not isinstance(e.get("base_revision"), bool) and e["base_revision"] >= 0
               for e in log)  # fmt: skip
