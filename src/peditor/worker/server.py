"""Worker 主迴圈：stdin 讀一行請求、stdout 寫一行回應（ADR-0004）。

stdout 只寫協定訊息；Python 層的 print 改導向 stderr，避免汙染協定。
stderr 只寫不含原文與路徑的診斷碼。
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, BinaryIO

from peditor.core.protocol import ProtocolError, decode, encode, validate_request

_TEST_HOOKS = os.environ.get("PEDITOR_WORKER_TEST_HOOKS") == "1"


class Worker:
    def __init__(self) -> None:
        from peditor.worker import analyzer

        self.analyzer = analyzer
        self.documents: dict[str, Any] = {}

    def handle(self, message: dict) -> dict:
        operation = message["operation"]
        params = message.get("params", {})
        if operation == "open_document":
            path = params.get("path")
            if not isinstance(path, str):
                raise ProtocolError("INVALID_REQUEST", "缺少 path")
            document = self.analyzer.open_document(path)
            self.documents[document.document_id] = document
            return {
                "document_id": document.document_id,
                "revision": document.revision,
                "sha256": document.sha256,
                "page_count": document.page_count,
                "document_flags": document.flags,
            }
        document = self._document(message)
        if operation == "inspect_page":
            return self.analyzer.inspect_page(document, params.get("page_index"))
        if operation == "assess_editability":
            return self.analyzer.assess_editability(document)
        if operation == "render_page":
            return self.analyzer.render_page(
                document, params.get("page_index"), params.get("dpi", 150)
            )
        if operation == "close_document":
            self.documents.pop(document.document_id).close()
            return {}
        raise ProtocolError("INVALID_REQUEST", "未知操作")

    def _document(self, message: dict):
        document = self.documents.get(message.get("document_id"))
        if document is None:
            raise ProtocolError("INVALID_REQUEST", "文件未開啟")
        expected = message.get("expected_revision")
        if expected is not None and expected != document.revision:
            raise ProtocolError("REVISION_CONFLICT", "文件版本不符", retryable=True)
        return document


def serve(stdin: BinaryIO, stdout: BinaryIO) -> int:
    worker = None
    for line in stdin:
        request_id = None
        try:
            message = decode(line)
            request_id = message.get("request_id")
            if _TEST_HOOKS and message.get("operation") == "_sleep":
                time.sleep(float(message.get("params", {}).get("seconds", 0)))
                response = {"request_id": request_id, "ok": True, "result": {}}
            else:
                validate_request(message)
                if worker is None:
                    worker = Worker()
                response = {"request_id": request_id, "ok": True, "result": worker.handle(message)}
        except ProtocolError as exc:
            response = {"request_id": request_id, "ok": False, "error": exc.to_dict()}
        except Exception as exc:  # noqa: BLE001 — 任何未預期錯誤都回受控失敗，不洩漏細節
            sys.stderr.write(f"worker: {type(exc).__name__}\n")
            error = ProtocolError("WORKER_FAILED", "處理文件時發生未預期錯誤")
            response = {"request_id": request_id, "ok": False, "error": error.to_dict()}
        try:
            stdout.write(encode(response))
        except ProtocolError as exc:
            stdout.write(encode({"request_id": request_id, "ok": False, "error": exc.to_dict()}))
        stdout.flush()
    return 0


def main() -> int:
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    sys.stdout = sys.stderr  # 任何 print 都不得進入協定通道
    return serve(stdin, stdout)
