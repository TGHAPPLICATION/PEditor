# ADR-0021：P4 桌面編輯流程（UI 架構、預覽引擎、macOS 驗收範圍）

- 狀態：已接受（2026-10-29，工程師於 P4 S1／S2 決定）
- 日期：2026-10-29
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

spec P4 要求開檔、縮圖、預覽、點選文字、替換輸入、模式／字型／溢出提示、前後對照、undo/redo、另存、進度與取消，
繁中 UI／IME、Ctrl／Cmd 快捷鍵，worker 不阻塞 UI；§9 要求「只包裝已驗證 API……不得讓 UI 私自改 PDF」。
P3 報告 §9 U2：ADR-0015 的 7 份 fixture 以 MuPDF 渲染為空白，P4 預覽前須處理。ADR-0003：P4 的 IME、Cmd、E2E 不能以 CI 取代實機。

## 決策

### 1. 預覽引擎：維持 MuPDF，偵測後提示

- 查明原因（2026-10-29）：這 7 份以 Identity-H 引用 CID-keyed CFF 子集字型，頁面字碼（＝CID）為 1～21，
  但字型 charset 保留原始 CID（例如 cid10896）。依 PDF 規範 CID 須經 charset 查字形，查不到即無字形；MuPDF 依規範處理而空白，
  PDFium 退而以字形索引顯示。把該字型 charset 改為「CID＝字形索引」後，MuPDF 即正常渲染（臨時驗證，未入庫）。
  所以是檔案不符規範（P0 以 PyMuPDF 產生 fixture 的方式造成），不是 MuPDF 缺陷。
- 決定：不新增執行期相依。worker 分析頁面時偵測「頁面用到的 CID 不在字型 charset」，頁面結果加
  `notices: ["PREVIEW_UNRELIABLE"]`；UI 顯示「此頁字型不符規範，預覽可能空白；另存不受影響」。
  對 repo 內 fixture，偵測結果恰為上述 7 份。
- 不採用：改以 PDFium 預覽（預覽將與依規範處理的閱讀器不同，且增加打包體積與授權項目）；判為不支援（等於縮小支援範圍）。

### 2. UI 架構

- `src/peditor/ui/`：主視窗（工具列、縮圖、頁面檢視、編輯側欄、狀態列）。UI 只呼叫 DocumentService 的公開 API，
  不匯入 PyMuPDF／pikepdf、不組 PDF 指令（G1-01 測試持續有效）。
- 所有 DocumentService 呼叫在單一背景執行緒依序執行（DocumentService 本就串行），結果以 Qt signal 回主執行緒；
  主執行緒不等待 worker。取消呼叫既有 `DocumentService.cancel`（終止 worker；下次請求依 command log 重播還原，未完成的操作不提交）。
- 選取：點選頁面上的文字目標（以 `inspect_page` 的 bbox 做點擊判定，送出的是 target_id，不以 bbox 定位內容），
  在側欄輸入整段新文字；另提供「尋找文字」以 span 選取跨運算子範圍。實際替換範圍由 P2 span 機制計算。
- 前後對照：新增 worker 操作 `preview_edit(plan_id)`（spec §7）：在工作文件上套用計畫、渲染改動區域前後圖、
  再以開啟自的位元組回滾並重新規劃同一計畫；revision 不變、不提交。
- IME：只在使用者按「預覽」或 Enter（且不在組字中）時規劃，組字中的 preedit 不送出。
- 快捷鍵：Qt 標準鍵（QKeySequence.StandardKey），Windows 為 Ctrl、macOS 為 Cmd。
- 復原草稿：UI 啟用；啟動時列出未逾期草稿由使用者選擇復原或捨棄。先修正 P3 triage f001（草稿結構驗證）、
  f006（保存參數副本）；啟動時清除先前中斷留下的另存暫存檔（P3 U9，路徑記錄在本機資料目錄）。
- 例外（2026-10-30，工程師於 P4 報告 U8 決定）：啟動時的本機儲存接線 `ui/app.py::prepare_storage` 不經 DocumentService，
  直接建立 `DraftStore`、設定 `transaction.registry` 並呼叫 `transaction.cleanup_recorded()`。理由：這是行程啟動設定，
  發生在任何文件開啟前，只涉及本程式自己的資料目錄與暫存檔，不碰使用者 PDF。其餘 UI 程式仍只呼叫 DocumentService 公開 API；
  點擊判定的座標換算另匯入 `core.geometry`（純計算）。測試：`tests/gui/test_startup.py`。
- 例外（2026-10-30，工程師於 P4 報告 U11 決定）：關閉視窗（`closeEvent`）時主執行緒會等待：`JobRunner.shutdown` 每 50 ms 重試取消直到執行中的工作結束，
  等待時間為目前這段 Python 端運算加上每次終止 worker 最多 5 秒；之後在主執行緒同步呼叫 `close_document`（刪除草稿，ADR-0020 §5）。
  理由：關閉後不能留下開啟中的文件與草稿，結果晚到的工作也要先收下再關閉。關閉中送達的結果不再開啟對話框或排入新工作。
  測試：`tests/gui/test_drafts_ui.py` 的 `test_close_window_*`。

### 3. macOS 驗收範圍

目前沒有 macOS 實機。Windows 在實機驗收；macOS 只有 CI（offscreen）證據，IME、Cmd 快捷鍵、E2E 的實機項目標 NOT RUN，
G4 結果標附條件，取得實機後補驗（ADR-0003、P3 U1）。

## 後果

- 這類不符規範的檔案，使用者在預覽看不到內容，只看到提示；另存結果與原檔同樣不符規範（模式 A 沿用原字碼）。
- `preview_edit` 每次需套用與回滾，耗時約為一次 apply 加一次重新規劃。
