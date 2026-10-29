"""DocumentService：主行程端的 typed API，所有 PDF 解析都轉交 worker 子行程（ADR-0004、spec §7）。

主行程不匯入 PyMuPDF／pikepdf（G1-01）。worker 逾時、崩潰或被取消時終止並在下次請求時重啟，
已開啟的文件依原路徑重新開啟，以 SHA-256 確認檔案未被外部修改，再重播 command log 回到目前版本。

P3（ADR-0020）：command log 與 undo／redo 在此；另存以 destination_token 經
`peditor.export.transaction` 交易寫出；傳入 DraftStore 時保存復原草稿。
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from peditor.core.drafts import DraftStore
from peditor.core.limits import REQUEST_TIMEOUT_S
from peditor.core.protocol import (
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    ProtocolError,
    decode,
    encode,
)
from peditor.export import transaction


class ServiceError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):  # PyInstaller：同一執行檔的子命令（ADR-0004）
        return [sys.executable, "--worker"]
    # -P：不把目前資料夾放進 sys.path，避免載入工作目錄中的同名模組（P1 安全掃描 f011）
    return [sys.executable, "-P", "-m", "peditor.worker"]


@dataclass
class _Doc:
    path: str
    sha256: str
    worker_id: str | None
    revision: int = 0
    # command log：每筆 {"params": plan_text_edit 參數, "base_revision": 規劃時的 revision}
    # （ADR-0020 §1）
    log: list[dict] = field(default_factory=list)
    position: int = 0  # 已套用的筆數；log[position:] 為可重做
    plans: dict[str, dict] = field(default_factory=dict)  # plan_id → 尚未套用的 log 項目
    draft_id: str | None = None


class _WorkerProcess:
    def __init__(self, command: list[str]) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(  # noqa: S603 — 固定命令，不含使用者輸入
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        self.lines: queue.Queue[bytes | None] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self.proc.stdout is not None
        # 讀取時就限制單行長度，超長回應不整行載入記憶體（T2）
        while line := self.proc.stdout.readline(MAX_MESSAGE_BYTES + 1):
            if len(line) > MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
                self.lines.put(b"")  # 交由 _exchange 判為格式錯誤並重啟 worker
                return
            self.lines.put(line)
        self.lines.put(None)

    def send(self, data: bytes) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def kill(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        for stream in (self.proc.stdin, self.proc.stdout):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass


class DocumentService:
    def __init__(
        self,
        timeout: float = REQUEST_TIMEOUT_S,
        command: list[str] | None = None,
        drafts: DraftStore | None = None,
    ) -> None:
        self.timeout = timeout
        self.command = command or worker_command()
        self.drafts = drafts  # None：不保存復原草稿（CLI、測試預設；ADR-0020 §5）
        self._worker: _WorkerProcess | None = None
        self._docs: dict[str, _Doc] = {}
        self._tokens: dict[str, transaction.Destination] = {}
        self._lock = threading.Lock()  # 每次只處理一個請求（每份文件串行修改，spec §7）
        self._state = threading.Lock()
        self._inflight: str | None = None
        self._cancelled: set[str] = set()

    # --- spec §7 API ---------------------------------------------------
    def open_document(self, path: str | os.PathLike) -> dict[str, Any]:
        path = os.fspath(path)
        result = self._call("open_document", params={"path": path})
        document_id = result["document_id"]
        doc = _Doc(path, result["sha256"], document_id, revision=result["revision"])
        if self.drafts is not None:
            doc.draft_id = self.drafts.new_id()
        self._docs[document_id] = doc
        return result

    def inspect_page(self, document_id: str, page_index: int, expected_revision: int | None = None):
        return self._doc_call(
            document_id, "inspect_page", {"page_index": page_index}, expected_revision
        )

    def assess_editability(self, document_id: str, expected_revision: int | None = None):
        return self._doc_call(document_id, "assess_editability", {}, expected_revision)

    def render_page(self, document_id: str, page_index: int, dpi: int = 150):
        return self._doc_call(
            document_id, "render_page", {"page_index": page_index, "dpi": dpi}, None
        )

    def find_text(self, document_id: str, page_index: int, text: str, occurrence: int = 0):
        """以內容尋找文字，回傳 span_id（不是 bbox 定位；ADR-0018 §1）。"""
        params = {"page_index": page_index, "text": text, "occurrence": occurrence}
        return self._doc_call(document_id, "find_text", params, None)["span_id"]

    def plan_text_edit(
        self,
        document_id: str,
        target_id: str,
        new_text: str,
        policy: str = "prefer_a",
        expected_revision: int | None = None,
        editable_region: list[float] | None = None,
    ):
        params = {"target_id": target_id, "new_text": new_text, "policy": policy}
        if editable_region is not None:
            params["editable_region"] = editable_region
        plan = self._doc_call(document_id, "plan_text_edit", params, expected_revision)
        if plan.get("ready"):
            self._docs[document_id].plans[plan["plan_id"]] = {
                "params": params, "base_revision": plan["preconditions"]["revision"]
            }  # fmt: skip
        return plan

    def apply_edit(self, document_id: str, plan_id: str, expected_revision: int):
        """套用 ready 的計畫並記入 command log；revision 不符即回 REVISION_CONFLICT。"""
        result = self._doc_call(document_id, "apply_edit", {"plan_id": plan_id}, expected_revision)
        doc = self._docs[document_id]
        entry = doc.plans.get(plan_id)
        if entry is None:  # worker 套用成功卻沒有對應計畫：log 不完整，重播會失準
            raise ServiceError("VALIDATION_FAILED", "計畫紀錄不一致")
        del doc.log[doc.position :]  # 新操作截斷可重做的部分
        doc.log.append(entry)
        doc.position += 1
        return self._advance(doc, result)

    def undo(self, document_id: str, expected_revision: int) -> dict:
        """撤銷一筆：由原檔重播前 position−1 筆（ADR-0020 §1）。"""
        doc = self._require(document_id, expected_revision)
        if doc.position == 0:
            raise ServiceError("INVALID_REQUEST", "沒有可撤銷的操作")
        params = {"commands": doc.log[: doc.position - 1], "revision": doc.revision + 1,
                  "reset": True}  # fmt: skip
        result = self._doc_call(document_id, "replay", params, expected_revision)
        doc.position -= 1
        return self._advance(doc, result)

    def redo(self, document_id: str, expected_revision: int) -> dict:
        """重做一筆：在目前狀態上重播第 position 筆。"""
        doc = self._require(document_id, expected_revision)
        if doc.position == len(doc.log):
            raise ServiceError("INVALID_REQUEST", "沒有可重做的操作")
        params = {"commands": [doc.log[doc.position]], "revision": doc.revision + 1,
                  "reset": False}  # fmt: skip
        result = self._doc_call(document_id, "replay", params, expected_revision)
        doc.position += 1
        return self._advance(doc, result)

    def history(self, document_id: str) -> dict:
        doc = self._require(document_id, None)
        return {"revision": doc.revision, "undo": doc.position,
                "redo": len(doc.log) - doc.position}  # fmt: skip

    def destination_token(self, path: str | os.PathLike, overwrite: bool = False) -> str:
        """另存目的地的 token（spec §7 destination_token；ADR-0020 §3）。
        目的檔已存在而 overwrite 為否時回 SAVE_FAILED。"""
        try:
            dest = transaction.destination(path, overwrite)
        except ProtocolError as exc:
            raise ServiceError(exc.code, exc.message, exc.retryable) from None
        except OSError:  # 不讓含路徑的系統錯誤外流（CLAUDE.md）
            raise ServiceError("SAVE_FAILED", "無法存取目的地") from None
        token = uuid.uuid4().hex
        self._tokens[token] = dest
        return token

    def export_document(self, document_id: str, destination_token: str, expected_revision: int):
        """交易式另存：worker 寫入同目錄暫存檔並驗證，主行程核對後原子取代目的檔。
        原檔或目的檔在取得 token 後被修改：REVISION_CONFLICT；目的檔是原檔：INVALID_REQUEST。"""
        doc = self._require(document_id, expected_revision)
        dest = self._tokens.get(destination_token) if isinstance(destination_token, str) else None
        if dest is None:
            raise ServiceError("INVALID_REQUEST", "目的地 token 無效")
        if any(transaction.is_same_file(dest.path, d.path) for d in self._docs.values()):
            raise ServiceError("INVALID_REQUEST", "不可覆寫已開啟文件的原檔")

        def write(temp: str) -> dict:
            return self._doc_call(document_id, "export_document", {"destination": temp},
                                  expected_revision)  # fmt: skip

        try:
            result = transaction.commit(dest, doc.path, doc.sha256, write)
        except ProtocolError as exc:
            raise ServiceError(exc.code, exc.message, exc.retryable) from None
        except OSError:
            raise ServiceError("SAVE_FAILED", "另存失敗") from None
        del self._tokens[destination_token]  # token 只用一次；再存須重新取得（目的檔狀態已改變）
        return result

    # --- 復原草稿（ADR-0020 §5） --------------------------------------
    def list_drafts(self) -> list[dict]:
        return self._drafts_call(self.drafts.list) if self.drafts is not None else []

    def recover_draft(self, draft_id: str) -> dict[str, Any]:
        """使用者選擇後才復原：開啟原檔、確認 SHA-256 與草稿相同，再重播到草稿位置。"""
        draft = self._drafts_call(self.drafts.load, draft_id) if self.drafts is not None else None
        if draft is None:
            raise ServiceError("INVALID_REQUEST", "草稿不存在或已逾期")
        opened = self.open_document(draft["path"])
        document_id = opened["document_id"]
        if opened["sha256"] != draft["sha256"]:
            self.close_document(document_id)
            raise ServiceError("REVISION_CONFLICT", "原檔已與草稿不同")
        doc = self._docs[document_id]
        log, position = draft["log"], draft["position"]
        if position:
            # revision 須大於 log 中任何規劃時版本，之後的 target_id 才不會與舊版本混淆
            revision = max(e["base_revision"] for e in log) + 1
            params = {"commands": log[:position], "revision": revision, "reset": False}
            try:
                result = self._doc_call(document_id, "replay", params, 0)
            except ServiceError:
                self.close_document(document_id)
                raise
            doc.revision = result["new_revision"]
        doc.log, doc.position = log, position
        result = {**opened, "revision": doc.revision}
        if self.drafts is not None:  # 改由新開啟的文件接手；舊草稿刪除
            warning = self._save_draft(doc)
            if warning is None:
                self._drafts_call(self.drafts.discard, draft_id)
            else:  # 新草稿沒寫成：保留舊草稿
                result["warnings"] = [warning]
        return result

    def discard_draft(self, draft_id: str) -> None:
        if self.drafts is not None:
            self._drafts_call(self.drafts.discard, draft_id)

    def close_document(self, document_id: str) -> None:
        doc = self._docs.pop(document_id, None)
        if doc is None:
            return
        if doc.draft_id is not None and self.drafts is not None:
            try:
                self.drafts.discard(doc.draft_id)
            except ProtocolError:
                pass  # 刪不掉的草稿於 7 天後由 purge 刪除
        if doc.worker_id is not None and self._worker is not None:
            try:
                self._call("close_document", document_id=doc.worker_id)
            except ServiceError:
                pass

    def cancel(self, request_id: str | None = None) -> bool:
        """取消進行中的請求：終止 worker（單執行緒 worker 無法中斷單一操作）。"""
        with self._state:
            target = self._inflight
            if target is None or (request_id is not None and request_id != target):
                return False
            self._cancelled.add(target)
            worker = self._worker
        if worker is not None:
            worker.kill()
        return True

    @property
    def inflight_request(self) -> str | None:
        return self._inflight

    def close(self) -> None:
        with self._state:
            worker, self._worker = self._worker, None
        if worker is not None:
            worker.kill()

    def __enter__(self) -> DocumentService:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- 內部 ----------------------------------------------------------
    def _require(self, document_id: str, expected_revision: int | None) -> _Doc:
        doc = self._docs.get(document_id)
        if doc is None:
            raise ServiceError("INVALID_REQUEST", "文件未開啟")
        if expected_revision is not None and expected_revision != doc.revision:
            raise ServiceError("REVISION_CONFLICT", "文件版本不符", retryable=True)
        return doc

    def _advance(self, doc: _Doc, result: dict) -> dict:
        """編輯已在 worker 生效：更新版本；草稿寫不成只加警告，不回報失敗（P3 triage f007）。"""
        doc.revision = result["new_revision"]
        doc.plans.clear()  # 計畫只對規劃時的版本有效
        warning = self._save_draft(doc)
        return {**result, "warnings": [warning]} if warning else result

    def _save_draft(self, doc: _Doc) -> str | None:
        """寫入或刪除草稿；失敗時回傳警告文字（不含路徑）。"""
        if self.drafts is None or doc.draft_id is None:
            return None
        try:
            if doc.position == 0:  # 沒有已套用的編輯：不留草稿
                self.drafts.discard(doc.draft_id)
            else:
                self.drafts.save(doc.draft_id, doc.path, doc.sha256, doc.log, doc.position)
        except ProtocolError as exc:
            return f"復原草稿未更新：{exc.message}"
        return None

    def _drafts_call(self, func, *args):
        try:
            return func(*args)
        except ProtocolError as exc:
            raise ServiceError(exc.code, exc.message, exc.retryable) from None

    def _doc_call(self, document_id: str, operation: str, params: dict, expected_revision):
        doc = self._docs.get(document_id)
        if doc is None:
            raise ServiceError("INVALID_REQUEST", "文件未開啟")
        self._ensure_worker()  # worker 已結束時先重啟，才能判斷文件是否需重開
        if doc.worker_id is None:  # worker 重啟過：依原路徑重開、確認未被外部修改、重播 log
            reopened = self._call("open_document", params={"path": doc.path})
            if reopened["sha256"] != doc.sha256:
                self._call("close_document", document_id=reopened["document_id"])
                raise ServiceError("REVISION_CONFLICT", "檔案已被外部修改")
            if doc.revision != reopened["revision"]:
                restore = {"commands": doc.log[: doc.position], "revision": doc.revision,
                           "reset": False}  # fmt: skip
                try:
                    self._call("replay", document_id=reopened["document_id"], params=restore)
                except ServiceError:
                    self._call("close_document", document_id=reopened["document_id"])
                    raise
            doc.worker_id = reopened["document_id"]
            doc.plans.clear()  # worker 端計畫已隨重啟消失
        return self._call(operation, document_id=doc.worker_id, params=params,
                          expected_revision=expected_revision)  # fmt: skip

    def _ensure_worker(self) -> _WorkerProcess:
        with self._state:
            if self._worker is None or self._worker.proc.poll() is not None:
                if self._worker is not None:
                    self._worker.kill()
                self._worker = _WorkerProcess(self.command)
                for doc in self._docs.values():
                    doc.worker_id = None
            return self._worker

    def _restart(self) -> None:
        with self._state:
            worker, self._worker = self._worker, None
        if worker is not None:
            worker.kill()
        for doc in self._docs.values():
            doc.worker_id = None

    def _call(self, operation, document_id=None, params=None, expected_revision=None,
              request_id=None) -> dict:  # fmt: skip
        with self._lock:
            request_id = request_id or uuid.uuid4().hex
            message = {
                "request_id": request_id,
                "protocol_version": PROTOCOL_VERSION,
                "document_id": document_id,
                "expected_revision": expected_revision,
                "operation": operation,
                "params": params or {},
            }
            worker = self._ensure_worker()
            with self._state:
                self._inflight = request_id
            try:
                return self._exchange(worker, request_id, encode(message))
            finally:
                with self._state:
                    self._inflight = None
                    self._cancelled.discard(request_id)

    def _exchange(self, worker: _WorkerProcess, request_id: str, data: bytes) -> dict:
        try:
            worker.send(data)
        except OSError:
            self._restart()
            raise self._failure(request_id) from None
        while True:
            try:
                line = worker.lines.get(timeout=self.timeout)
            except queue.Empty:
                self._restart()
                raise ServiceError("RESOURCE_LIMIT", "操作逾時，已終止處理程序") from None
            if line is None:
                self._restart()
                raise self._failure(request_id)
            try:
                response = decode(line)
            except ProtocolError:
                self._restart()
                raise ServiceError(
                    "WORKER_FAILED", "處理程序回應格式錯誤", retryable=True
                ) from None
            if response.get("request_id") not in (request_id, None):
                continue
            if response.get("ok"):
                return response["result"]
            error = response.get("error") or {}
            raise ServiceError(error.get("code", "WORKER_FAILED"), error.get("message", ""),
                               bool(error.get("retryable")))  # fmt: skip

    def _failure(self, request_id: str) -> ServiceError:
        if request_id in self._cancelled:
            return ServiceError("CANCELLED", "已取消", retryable=True)
        return ServiceError("WORKER_FAILED", "處理程序異常結束", retryable=True)

    def _send_raw(self, operation: str, params: dict, request_id: str | None = None) -> dict:
        """測試用：送出任意 operation（例如 worker 的測試 hook）。"""
        return self._call(operation, params=params, request_id=request_id)
