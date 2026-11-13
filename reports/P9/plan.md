# P9 頁面工具與介面改版 — S1／S2（待工程師確認後實作）

依 CLAUDE.md 工作流程：S1 確認輸入、S2 拆解任務；工程師確認後才進入 S3 實作（分支 `p9-page-tools`）。

## S1 輸入

- 需求來源：工程師 2026-11-13 附件（Colab PDF 工具）與選擇（見 ADR-0029 背景）。
- 決策：ADR-0029（提議）。相關：ADR-0004（worker）、ADR-0021（另存交易）、ADR-0027（未另存提醒）、ADR-0002（授權）。
- 缺漏／假設（請確認）：
  1. 「刪除」「保留」「擷取」合成兩個畫面：刪除頁面、保留頁面（擷取＝保留，範圍語法相同）。
  2. 合併的檔案順序在對話框內以上下移動按鈕調整（不做拖曳）。
  3. 結果不保留書籤；有表單欄位的檔案拒絕合併／插入。
  4. 深色主題不在本段範圍。

## S2 需求 → 測試 → 檔案

| 需求 ID | 內容 | 測試 ID | 修改檔案 |
| --- | --- | --- | --- |
| P9-01 | 頁碼範圍解析（`1-3,5`、去重、越界與格式錯誤的訊息） | `tests/unit/test_page_ranges.py` | `src/peditor/core/pages.py`（新） |
| P9-02 | worker `compose_pages`：依來源＋頁碼組成新檔；限制輸入數、總頁數；拒絕加密、表單、損毀 | `tests/integration/test_compose_pages.py` | `src/peditor/worker/pages.py`（新）、`worker/main.py`、`core/limits.py` |
| P9-03 | 刪除／保留／合併／插入四種計畫轉換 | 同上（參數化） | `core/pages.py` |
| P9-04 | 輸出驗證：重開比對頁數與每頁內容雜湊；失敗即刪除輸出 | 同上 | `worker/pages.py` |
| P9-05 | 經目的地權杖與原子寫入另存；不覆寫來源 | 同上、`tests/security/` 既有測試 | `core/service.py` |
| P9-06 | 「工具 → 頁面工具…」對話框（四個分頁、範圍驗證、合併順序、結果與限制說明、開啟結果） | `tests/gui/test_page_tools.py` | `src/peditor/ui/page_tools.py`（新）、`ui/app.py` |
| P9-07 | 有未另存修改時先詢問（ADR-0027） | 同上 | `ui/app.py` |
| P9-08 | 介面視覺改版：QSS 主題、工具列分組與圖示、面板版面 | `tests/gui/test_theme.py`（主題載入、主要元件套用、對比度檢查）＋視覺稿確認 | `src/peditor/ui/theme.py`、`ui/theme.qss`（新）、`ui/app.py` |
| P9-09 | 打包：主題檔進安裝包；離線檢查不變 | `tests/unit/test_release_licenses.py` 類似的自我檢查 | `packaging/build_release.py` |
| P9-10 | 文件：spec §4／§6、THREAT_MODEL、traceability、已知限制 | 文件審查 | `docs/` |
| P9-11 | 實機：Windows 沙箱驗收（新增清單項目） | 驗收頁面 | — |

## 步驟

1. 工程師確認 ADR-0029 與本表。
2. 先交介面視覺稿（設計稿），工程師確認後再實作 P9-08。
3. P9-01～P9-07、P9-09 實作與測試；worker 新增多檔輸入，結束前跑 `/vuln-scan`、`/triage`（CLAUDE.md 技能時點），並由獨立子代理人核對。
4. CI 雙平台、Windows 沙箱實機、`reports/P9/report.md`。

## 輸出格式

程式與測試（分支 `p9-page-tools` → PR）、ADR-0029、`reports/P9/report.md`、實機驗收清單新增項目。

## 驗收標準

- 自動測試與 CI 雙平台通過；既有文字編輯測試不變。
- Windows 實機：四種頁面工具各產生正確新檔（頁數、順序、內容與 Edge 開啟一致）；視覺改版經工程師確認。
- 須請人類確認：ADR-0029、視覺稿、S1 的 4 項假設、實機結果。
