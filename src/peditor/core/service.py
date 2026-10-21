"""DocumentService：主行程端的 typed API，所有 PDF 解析都轉交 worker 子行程（ADR-0004、spec §7）。

主行程不匯入 PyMuPDF／pikepdf（G1-01）。worker 逾時、崩潰或被取消時終止並在下次請求時重啟，
已開啟的文件依原路徑重新開啟，並以 SHA-256 確認檔案未被外部修改。
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass
from typing import Any

from peditor.core.limits import REQUEST_TIMEOUT_S
from peditor.core.protocol import (
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    ProtocolError,
    decode,
    encode,
)


class ServiceError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):  # PyInstaller：同一執行檔的子命令（ADR-0004）
        return [sys.executable, "--worker"]
    return [sys.executable, "-m", "peditor.worker"]


@dataclass
class _Doc:
    path: str
    sha256: str
    worker_id: str | None


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
        self, timeout: float = REQUEST_TIMEOUT_S, command: list[str] | None = None
    ) -> None:
        self.timeout = timeout
        self.command = command or worker_command()
        self._worker: _WorkerProcess | None = None
        self._docs: dict[str, _Doc] = {}
        self._lock = threading.Lock()  # 每次只處理一個請求（每份文件串行修改，spec §7）
        self._state = threading.Lock()
        self._inflight: str | None = None
        self._cancelled: set[str] = set()

    # --- spec §7 API ---------------------------------------------------
    def open_document(self, path: str | os.PathLike) -> dict[str, Any]:
        path = os.fspath(path)
        result = self._call("open_document", params={"path": path})
        document_id = result["document_id"]
        self._docs[document_id] = _Doc(path, result["sha256"], document_id)
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

    def close_document(self, document_id: str) -> None:
        doc = self._docs.pop(document_id, None)
        if doc is not None and doc.worker_id is not None and self._worker is not None:
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
    def _doc_call(self, document_id: str, operation: str, params: dict, expected_revision):
        doc = self._docs.get(document_id)
        if doc is None:
            raise ServiceError("INVALID_REQUEST", "文件未開啟")
        self._ensure_worker()  # worker 已結束時先重啟，才能判斷文件是否需重開
        if doc.worker_id is None:  # worker 重啟過：依原路徑重開並確認未被外部修改
            reopened = self._call("open_document", params={"path": doc.path})
            if reopened["sha256"] != doc.sha256:
                self._call("close_document", document_id=reopened["document_id"])
                raise ServiceError("REVISION_CONFLICT", "檔案已被外部修改")
            doc.worker_id = reopened["document_id"]
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
