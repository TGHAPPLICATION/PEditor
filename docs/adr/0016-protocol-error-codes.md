# ADR-0016：協定層錯誤碼 INVALID_REQUEST、WORKER_FAILED（P1 報告 U1）

- 狀態：已接受（2026-10-22，工程師決定正式列入）
- 日期：2026-10-22
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

spec §7 的錯誤碼與 ADR-0007 的能力判定碼都描述「文件或編輯操作為何不可行」。P1 的 worker 協定（ADR-0004）
另需回報兩類與文件內容無關的失敗，P1 已以下列兩碼實作（`src/peditor/core/protocol.py` 的 `PROTOCOL_ERROR_CODES`），
但未列入 spec／ADR 清單（P1 報告 §9 U1）。

## 決策

正式列入兩個**協定層**錯誤碼，與能力判定碼分開（不出現在 capability report 的 `reasons`）：

| 代碼 | 用途 | retryable | 產生位置 |
| --- | --- | --- | --- |
| `INVALID_REQUEST` | 呼叫端請求本身不合法：訊息非 JSON／非物件、協定版本不符、缺 `request_id`、未知操作、`params` 型別錯、缺 `path`、檔案無法讀取、文件未開啟、頁碼或 DPI 超出範圍 | 否（相同請求重送結果相同） | `protocol.py`、`worker/server.py`、`worker/analyzer.py`、`core/service.py` |
| `WORKER_FAILED` | worker 無法完成請求且原因不屬任何既有碼 | 依下列情況 | `worker/server.py`、`core/service.py` |

`WORKER_FAILED` 的 retryable：

- **worker 內未預期例外**（`server.py` 攔截任何非 `ProtocolError` 例外）：`false`。同一份文件、同一請求通常會再次觸發同一例外；
  訊息固定為「處理文件時發生未預期錯誤」，只在 stderr 記錄例外類別名稱，不含文件原文或路徑。
- **worker 行程異常結束或回應格式錯誤**（`service.py`）：`true`。主行程已重啟 worker，呼叫端可重新開啟文件後重試。

規則：

- 能力判定與編輯失敗一律使用 spec §7／ADR-0007 的碼；只有在請求不合法或 worker 本身失敗時才使用協定層碼，
  不得以 `WORKER_FAILED` 取代可判定的理由碼（例如逾時仍回 `RESOURCE_LIMIT`、取消仍回 `CANCELLED`）。
- 新增協定層錯誤碼須另立 ADR。

## 後果

- `protocol.py` 的 `ERROR_CODES`（spec §7＋ADR-0007）與 `PROTOCOL_ERROR_CODES`（本 ADR）以單元測試鎖定內容且互不重疊
  （`tests/unit/test_protocol_codes.py`，G1-11）。
- spec §7 錯誤碼清單本身未修改；spec 下一版修訂時應補列本 ADR 的兩碼。
- 既有行為不變：`tests/integration/test_api_contract.py::test_contract_errors`（INVALID_REQUEST）、
  `tests/security/test_worker_limits.py::test_oversized_worker_response_rejected`（WORKER_FAILED）。
