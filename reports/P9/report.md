# P9 關卡報告：頁面工具與介面改版（ADR-0029）

## 1. 階段／commit／日期

- 階段：P9（2026-11-13 追加；ADR-0029）
- 分支：`p9-page-tools`；commit：`8b7d4c0`（實作）、本報告所在 commit（獨立核對修正與文件）
- 日期：2026-11-13

## 2. 環境

| 環境 | 版本 | 說明 |
| --- | --- | --- |
| 本工作環境 | Linux 容器、Python 3.13、鎖定相依（`uv sync --locked`） | 自動測試；Qt offscreen |
| CI | GitHub Actions windows-latest、macos-15 | run 43390191795（`8b7d4c0`）test 與 release 雙平台 success；修正後的 run 見 PR |
| Windows 實機 | — | **NOT RUN**（待工程師，清單 P9a～P9e） |
| macOS 實機 | — | NOT RUN（ADR-0003） |

## 3. 需求 → test ID → fixture／hash → 結果

見 `docs/traceability.md` P9-01～P9-11。摘要：

| 需求 | test ID | 結果 |
| --- | --- | --- |
| P9-01 範圍解析 | `tests/unit/test_page_ranges.py` | PASS |
| P9-02～P9-05 compose_pages | `tests/unit/test_compose_worker.py`、`tests/integration/test_compose_pages.py` | PASS |
| P9-06、P9-07 對話框與流程 | `tests/gui/test_page_tools.py` | PASS（offscreen） |
| P9-08 視覺改版 | `tests/gui/test_theme.py`；視覺稿工程師已確認 | PASS（offscreen）；實機待驗 |
| P9-09 打包 | CI release | PASS（CI）；無新增資料檔 |
| P9-11 實機 | 驗收清單 P9a～P9e | NOT RUN（待工程師） |

## 4. 執行命令、exit code、測試數

- `uv run ruff check . && uv run ruff format --check .`：exit 0
- `uv run pytest -q --deselect tests/integration/test_fixtures.py::test_generator_reproduces_committed_bytes`：707 passed、4 skipped（本環境）。
  略過的一項在本環境的 main 上也失敗（fixture 位元組重現的環境差異），CI 雙平台通過。
- 這不是 Windows 實機證據。

## 5. 真修改證據

- 頁面工具輸出：worker 寫出前重新開啟，比對頁數與每頁內容串流的**原始位元組與篩選器**等於來源頁（不是重繪、不是點陣化）。
- 測試以 MuPDF 擷取每頁文字確認頁序（刪除、保留、合併、插入四種），並確認來源檔不變。

## 6. 資料完整性與資源／出站紀錄

- 只在 worker 處理；上限：20 份、合計 ≤200 MB、輸出 ≤500 頁且 ≤200 MB；同一頁不得重複；串流不解壓（解壓炸彈測試 15 秒內完成）。
- 經目的地權杖與原子寫入；目的檔不得是任何來源或已開啟文件（samefile）。沒有新增網路相關程式碼。

## 7. 限制、阻擋、未測項目

- 不保留書籤、文件結構樹、表單；含表單欄位、加密、簽章、主動內容、PDF/A、XFA 的來源一律拒絕（F13）。
- 不提供壓縮（工程師決定；附件的圖片重壓縮會整頁點陣化）。
- 選「不儲存」後若勾選「完成後開啟新檔」，開啟結果時會再詢問一次未另存的修改（安全但重複；未修）。
- Windows 實機、macOS 實機：NOT RUN。
- 深色主題：不在本段範圍。

## 8. 安全審查

- THREAT_MODEL 新增 T16（多檔不可信輸入、資源放大、主動內容帶入）。
- `/vuln-scan`、`/triage`：**NOT RUN**（不在 CLAUDE.md 的 P9 時點，為節省成本未執行）；改由獨立子代理人做安全與正確性核對（§11）。

## 9. 不確定性與人工確認項目

| 編號 | 內容 | 處理 |
| --- | --- | --- |
| U1 | 視覺改版只在 Linux offscreen 截圖確認；Windows 字型（Microsoft JhengHei UI）與 DPI 縮放下的實際外觀未看過 | 待實機 P9e |
| U2 | 頁面上註解的非主動動作（例如 URI 連結）照原樣保留 | 列 T16 殘餘 |
| U3 | 合併大量大檔可能超過 30 秒逾時 | 列 T16 殘餘；實機觀察 |

## 10. 關卡結果

- **BLOCKED**：自動化部分完成、獨立核對問題已修正；**Windows 實機驗收待工程師**（清單 P9a～P9e）。

## 11. 獨立核對紀錄

- 2026-11-13，未參與實作的子代理人（只讀）核對 `315475d..8b7d4c0`。確認：參數驗證、上限、拒絕條件、錯誤訊息不含路徑、
  不在 UI 行程開 PDF、防覆寫（samefile、大小寫、符號連結）、繼承的 MediaBox／Rotate／Resources 正確帶入、註解 /P 只改新檔。
  指出並已修正：
  - （中）輸出比對以 `read_bytes()` 解壓串流，繞過 `MAX_STREAM_BYTES`（292 KB 檔解壓到 300 MB、記憶體 1.27 GB）→ 改為原樣複製、
    比對原始位元組與篩選器；另發現 qpdf 語法檢查也會解壓所有串流，改為只重新開啟檢查（不做語法檢查）。
  - （中）未另存時選「另存」，頁面工具仍讀原檔 → 改讀剛另存的新檔。
  - （低）同一頁出現兩次會共用註解物件 → worker 拒絕重複頁。
  - 測試缺口（繼承屬性、重複頁、解壓、驗證失敗不寫檔、目的檔等於來源或已開啟文件、bool 參數、份數與大小上限、
    簽章與主動內容、選「另存」流程）→ 已補。
  - 文件不一致（ADR §3、§6、plan 檔案清單、traceability P9-09～P9-11、缺報告）→ 已修正。
  - 未修：選「不儲存」後開啟結果時再問一次（低，§7）。
