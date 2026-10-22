"""主行程與 worker 之間的 JSON Lines 協定（ADR-0004、spec §7）。只用標準函式庫，兩端共用。

請求：{"request_id", "protocol_version", "document_id", "expected_revision", "operation", "params"}
回應：{"request_id", "ok": true, "result": {...}} 或 {"request_id", "ok": false, "error": {...}}
error：{"code", "message", "retryable"}；message 不得含文件原文或完整檔案路徑。
"""

from __future__ import annotations

import json
from typing import Any

PROTOCOL_VERSION = 1

# 單則訊息上限（頁面 PNG 以 base64 回傳，150 DPI A4 約 1 MB 以內）
MAX_MESSAGE_BYTES = 64 * 1024 * 1024

# spec §7 錯誤碼 + ADR-0007 能力判定碼
ERROR_CODES = frozenset(
    {
        "UNSUPPORTED_ENCODING",
        "UNSUPPORTED_LAYOUT",
        "GLYPH_MISSING",
        "TEXT_OVERFLOW",
        "SHARED_RESOURCE_UNSAFE",
        "SIGNED_DOCUMENT",
        "ENCRYPTED_DOCUMENT",
        "REVISION_CONFLICT",
        "RESOURCE_LIMIT",
        "VALIDATION_FAILED",
        "SAVE_FAILED",
        "CANCELLED",
        "NO_TEXT_LAYER",
        "MALFORMED_DOCUMENT",
        "ACTIVE_CONTENT",
        "UNSUPPORTED_FEATURE",
    }
)
# 協定層錯誤（非能力判定；ADR-0016）：請求格式錯誤、worker 異常結束
PROTOCOL_ERROR_CODES = frozenset({"INVALID_REQUEST", "WORKER_FAILED"})

OPERATIONS = frozenset(
    {
        "open_document",
        "inspect_page",
        "assess_editability",
        "render_page",
        "plan_text_edit",
        "apply_edit",
        "close_document",
    }
)


class ProtocolError(Exception):
    """可回傳給呼叫端的錯誤；code 必須在 ERROR_CODES 或 PROTOCOL_ERROR_CODES。"""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        if code not in ERROR_CODES | PROTOCOL_ERROR_CODES:
            raise ValueError(f"未知錯誤碼 {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


def encode(message: dict[str, Any]) -> bytes:
    data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(data) > MAX_MESSAGE_BYTES:
        raise ProtocolError("RESOURCE_LIMIT", "訊息超過大小上限")
    return data


def decode(line: bytes) -> dict[str, Any]:
    if len(line) > MAX_MESSAGE_BYTES:
        raise ProtocolError("RESOURCE_LIMIT", "訊息超過大小上限")
    try:
        message = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("INVALID_REQUEST", "訊息不是 JSON") from exc
    if not isinstance(message, dict):
        raise ProtocolError("INVALID_REQUEST", "訊息必須是物件")
    return message


def validate_request(message: dict[str, Any]) -> None:
    if message.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("INVALID_REQUEST", "協定版本不符")
    if not isinstance(message.get("request_id"), str):
        raise ProtocolError("INVALID_REQUEST", "缺少 request_id")
    if message.get("operation") not in OPERATIONS:
        raise ProtocolError("INVALID_REQUEST", "未知操作")
    if not isinstance(message.get("params", {}), dict):
        raise ProtocolError("INVALID_REQUEST", "params 必須是物件")
