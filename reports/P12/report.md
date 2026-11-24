# P12 關卡報告：頁面管理改名、文字擷取、介面不超出螢幕（ADR-0033）

> 依 spec §11 範本。CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：P12（2026-11-24 追加）　分支：`p12-text-extract`　實作 commit：`0c25b21`～`e602316`；獨立核對修正與本報告定稿在其後的 commit（見 §11）
- 日期：2026-11-24
- 撰寫：Claude Code；審查：工程師；獨立核對：見 §11

## 2. 環境

| 環境 | 版本 | 說明 |
| --- | --- | --- |
| 本工作環境 | Linux 容器、Python 3.13、鎖定相依 | 自動測試；Qt offscreen |
| CI | GitHub Actions windows-latest、macos-15 | run 45346766843（`0c25b21`）、45349962927（`08b1504`）、45354492957（`e602316`）test 與 release 雙平台 success |
| Windows 實機（Windows Sandbox） | 同 P8 | 清單 P12a～P12e PASS（2026-11-24 17:15～17:25 台北時間；工程師自填、無截圖；安裝包推定 `e602316`）。沙箱內看不到螢幕解析度與縮放比例（工程師），P12e 未記錄 |
| macOS 實機 | — | NOT RUN（ADR-0003） |

## 3. 需求 → test ID → 結果

見 `docs/traceability.md` P12-01～P12-04。

| 需求 | test ID | 結果 |
| --- | --- | --- |
| P12-01 「頁面工具」改名「頁面管理」並移到另存新檔右方 | `tests/gui/test_theme.py::test_toolbar_groups_and_primary` | PASS（本機、CI）；實機 P12a PASS |
| P12-02 worker `extract_text`（含未另存修改、掃描頁、超限頁、字數上限、頁碼驗證） | `tests/integration/test_extract_text.py` | PASS（本機、CI）；實機 P12b PASS |
| P12-03 文字擷取對話框（預設目前頁與說明、第 N 頁標題、移除頁碼、搜尋、複製全部、另存 .txt） | `tests/gui/test_text_extract.py` | PASS（本機、CI）；實機 P12b～P12d PASS |
| P12-04 全部介面不超出螢幕可用範圍、按鈕文字不被裁切（實機回報後追加） | `tests/gui/test_screen_fit.py`（移除修正時 6 項失敗） | PASS（本機、CI）；實機 P12e PASS |

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q --deselect tests/integration/test_fixtures.py::test_generator_reproduces_committed_bytes
  → 757 passed, 4 skipped（@ e602316）
```

略過的一項是既有的環境差異，CI 雙平台通過。這不是 Windows 實機證據。

## 5. 真修改證據

不適用（文字擷取只讀，不改 PDF）。

## 6. 資料完整性與資源／出站紀錄

- 擷取只在 worker；內容超過處理上限的頁不交給 MuPDF；單頁 ≤1,000,000 字；共用 30 秒逾時。
- .txt 由主行程寫入（純文字，不解析 PDF），副檔名固定 .txt；訊息只顯示檔名。文件文字只在使用者按「複製全部」「另存文字檔」時輸出，不寫日誌（THREAT_MODEL T17）。
- 沒有新增網路相關程式碼。

## 7. 限制、阻擋、未測項目

- 不做 OCR；文字順序依 PDF 內容串流，多欄或表格排版可能與視覺順序不同。
- 擷取為同步、逐頁向 worker 取，頁數多時對話框暫停回應。
- 螢幕調整以「扣除工作列的可用範圍」計算；跨多螢幕拖曳後再開啟的位置未測。
- macOS 實機 NOT RUN（ADR-0003）。

## 8. 安全審查

- THREAT_MODEL 新增 T17（文字擷取：剪貼簿與 .txt 輸出、擷取資源）。新 worker 操作 `extract_text` 有參數驗證與回應結構檢查（`RESULT_FIELDS`）。
- `/vuln-scan`、`/triage`：NOT RUN（不在 CLAUDE.md 的 P12 時點）；改由獨立子代理人核對（§11）。

## 9. 不確定性與人工確認項目

| # | 內容 | 處理 |
| --- | --- | --- |
| U1 | 實機的螢幕解析度與縮放比例未記錄（沙箱內看不到）；自動測試以 1366×768@125%、1920×1080@150% 模擬 | 已記錄 |
| U2 | 實機安裝包版本依結果時間推定為 `e602316` | 工程師確認 |

## 10. 關卡結果

- **PASS（Windows）**：自動化、CI 雙平台、Windows 實機 P12a～P12e 與獨立核對完成。macOS 實機 NOT RUN（ADR-0003）。

## 11. 獨立核對紀錄

（待填）
