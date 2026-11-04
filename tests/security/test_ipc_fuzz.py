"""ADR-0004「每個訊息型別需有畸形輸入測試」；P1 triage f006、f020、f021（P7）。

- worker 端：每個 operation 都送參數型別錯誤、缺參數、未開啟文件等畸形請求，回應一律符合協定
  （validate_response），而且是可辨識的理由碼，不是未預期例外（WORKER_FAILED）。
- 主行程端：假 worker 回傳結構不符的回應（缺欄位、型別錯、未知錯誤碼、ok 不是布林等），
  一律回 WORKER_FAILED 並重啟 worker，不讓 KeyError／TypeError 流進呼叫端。
"""

import io
import json
import sys
from pathlib import Path

import pytest

from peditor.core.protocol import OPERATIONS, PROTOCOL_VERSION, validate_response
from peditor.core.service import DocumentService, ServiceError
from peditor.worker import server

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
BAD_VALUES = [None, "x", -1, 10**30, 1.5, True, [], {}, [1, "x"], "\x00" * 3]
KEYS = ["path", "page_index", "dpi", "text", "occurrence", "target_id", "new_text", "policy",
        "editable_region", "plan_id", "data", "keep", "asset_id", "cell_id", "line_index",
        "cell_box", "commands", "revision", "reset", "destination"]  # fmt: skip


def _exchange(lines: list[bytes]) -> list[dict]:
    out = io.BytesIO()
    server.serve(io.BytesIO(b"".join(lines)), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def _request(operation, params, document_id=None, expected_revision=None, rid="r") -> bytes:
    message = {"request_id": rid, "protocol_version": PROTOCOL_VERSION, "operation": operation,
               "document_id": document_id, "expected_revision": expected_revision,
               "params": params}  # fmt: skip
    return json.dumps(message).encode() + b"\n"


@pytest.mark.parametrize("operation", sorted(OPERATIONS - {"open_document"}))
def test_worker_rejects_malformed_params(operation):
    """先開檔（取得 document_id），再對同一個 worker 送該 operation 的各種畸形參數。"""
    open_line = _request("open_document", {"path": str(FILES / "B01.pdf")}, rid="open")
    first = _exchange([open_line])[0]
    document_id = first["result"]["document_id"]
    lines = [open_line, _request(operation, {}, document_id, rid="empty"),
             _request(operation, {}, "no-such-document", rid="nodoc")]  # fmt: skip
    for i, value in enumerate(BAD_VALUES):
        params = {key: value for key in KEYS}
        lines.append(_request(operation, params, document_id, rid=f"bad{i}"))
        lines.append(_request(operation, params, document_id, expected_revision=value,
                              rid=f"rev{i}"))  # fmt: skip
    responses = _exchange(lines)[1:]
    assert len(responses) == len(lines) - 1
    for line, response in zip(lines[1:], responses, strict=True):
        rid = json.loads(line)["request_id"]
        validate_response(operation, response, rid)
        if operation != "close_document":
            assert response["ok"] is False, (operation, rid)
            assert response["error"]["code"] != "WORKER_FAILED", (operation, rid, response)


@pytest.mark.parametrize(
    "line",
    [b"not json\n", b"[]\n", b"123\n", b'{"request_id": 5}\n', b"\xff\xfe\n",
     b'{"request_id": "r", "protocol_version": 1, "operation": "nope"}\n',
     b'{"request_id": "r", "protocol_version": 99, "operation": "inspect_page"}\n',
     b'{"request_id": "r", "protocol_version": 1, "operation": "inspect_page", "params": []}\n'],
)  # fmt: skip
def test_worker_rejects_malformed_lines(line):
    (response,) = _exchange([line])
    validate_response("inspect_page", response, "r")
    assert response["ok"] is False and response["error"]["code"] == "INVALID_REQUEST"


BAD_RESPONSES = {
    "not_object": "[]",
    "ok_missing": '{"request_id": RID}',
    "ok_not_bool": '{"request_id": RID, "ok": 1, "result": {}}',
    "result_not_object": '{"request_id": RID, "ok": true, "result": []}',
    "missing_sha256": '{"request_id": RID, "ok": true, "result": {"document_id": "d",'
    ' "revision": 0, "page_count": 1, "document_flags": {}}}',
    "revision_is_bool": '{"request_id": RID, "ok": true, "result": {"document_id": "d",'
    ' "revision": true, "sha256": "s", "page_count": 1, "document_flags": {}}}',
    "unknown_code": '{"request_id": RID, "ok": false, "error": {"code": "PWNED",'
    ' "message": "x", "retryable": false}}',
    "message_not_str": '{"request_id": RID, "ok": false, "error": {"code": "INVALID_REQUEST",'
    ' "message": 5, "retryable": false}}',
    "huge_message": '{"request_id": RID, "ok": false, "error": {"code": "INVALID_REQUEST",'
    ' "message": "' + "x" * 5000 + '", "retryable": false}}',
}


@pytest.mark.parametrize("kind", sorted(BAD_RESPONSES))
def test_service_rejects_malformed_responses(kind, tmp_path):
    """假 worker 對 open_document 回傳結構不符的回應：WORKER_FAILED，且 worker 被重啟。"""
    fake = tmp_path / "fake_worker.py"
    body = BAD_RESPONSES[kind]
    fake.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    rid = json.dumps(json.loads(line)['request_id'])\n"
        f"    sys.stdout.write({body!r}.replace('RID', rid) + '\\n')\n"
        "    sys.stdout.flush()\n",
        encoding="utf-8",
    )
    with DocumentService(command=[sys.executable, str(fake)]) as svc:
        with pytest.raises(ServiceError) as exc:
            svc.open_document(FILES / "T01.pdf")
        assert exc.value.code == "WORKER_FAILED", kind
        assert svc._worker is None  # 已終止，下次請求時重啟
