"""復原草稿（主行程；spec P3、ADR-0020 §5）。

草稿是開啟中文件的 command log（含新文字，屬敏感內容），存在使用者本機資料目錄，
不放在文件旁。不自動開啟：只列出，由使用者選擇後才復原。保留 7 天，逾期即刪。
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

RETENTION_S = 7 * 24 * 3600
_NAME = re.compile(r"^[0-9a-f]{16}\.json$")


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
        self.folder.mkdir(parents=True, exist_ok=True)
        self.purge()

    def new_id(self) -> str:
        return secrets.token_hex(8)

    def save(self, draft_id: str, path: str, sha256: str, log: list[dict], position: int) -> None:
        """以暫存檔＋原子取代寫入；POSIX 權限 0600。"""
        data = {"draft_id": draft_id, "path": path, "sha256": sha256, "log": log,
                "position": position, "saved_at": self._now()}  # fmt: skip
        target = self._file(draft_id)
        temp = target.with_name(f".{target.name}.{secrets.token_hex(4)}.tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp, target)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

    def load(self, draft_id: str) -> dict | None:
        if not _NAME.match(f"{draft_id}.json"):
            return None
        try:
            data = json.loads(self._file(draft_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or self._expired(data):
            self.discard(draft_id)
            return None
        return data

    def list(self) -> list[dict]:
        """未逾期的草稿摘要（不含 command log 內容）；逾期或損壞的草稿一併刪除。"""
        self.purge()
        out = []
        for name in sorted(os.listdir(self.folder)):
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
            self._file(draft_id).unlink(missing_ok=True)

    def purge(self) -> None:
        for name in os.listdir(self.folder):
            path = self.folder / name
            if name.endswith(".tmp") and name.startswith("."):
                self._remove_if_old(path)
            elif _NAME.match(name):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    self._remove_if_old(path)
                    continue
                if not isinstance(data, dict) or self._expired(data):
                    path.unlink(missing_ok=True)

    def _expired(self, data: dict) -> bool:
        saved = data.get("saved_at")
        return not isinstance(saved, (int, float)) or self._now() - saved > RETENTION_S

    def _remove_if_old(self, path: Path) -> None:
        try:
            if self._now() - path.stat().st_mtime > RETENTION_S:
                path.unlink()
        except OSError:
            pass

    def _file(self, draft_id: str) -> Path:
        return self.folder / f"{draft_id}.json"
