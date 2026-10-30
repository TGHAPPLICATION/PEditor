# P4 關卡報告：桌面文字編輯流程

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段 G4 測試都在 offscreen 平台執行（本機 Windows 與 CI），**不是實機證據**。

## 1. 階段／commit／日期

- 階段：P4　分支：`p4-desktop-ui`　commit：`28d89b5`（實作與 G4 測試）、`ecc067b`（U2 補測試，G4-08、G4-09）、`2aafaf3`（核對出入處理）、`c234632`（U7 修正）、`77a6348`（U8）、`b9a383e`（U9）、`efc3ddf`（U5，THREAT_MODEL）、`cb40fdf`（第二輪核對出入處理，見 §11）、`f601f84`（實機驗收清單，第三輪核對）、`5d4a5df`（U11）、`51c3c0d`（U11 第四輪核對補修）、`5b3f148`（U11 第五輪核對處理）、`ffcecc3`（第六輪核對 A4、A5）、`3f712aa`（第七輪核對 B1–B3）、`46febae`（第八輪核對 C1–C3，只改文件）　日期：2026-10-30
- 撰寫：Claude Code；審查：待工程師；獨立核對：2026-10-30 八輪（第一輪 `ecc067b`、第二輪 `efc3ddf` 針對 U5、第三輪 `00f8a7d` 針對實機驗收清單、第四輪 `90dcf84` 針對 U11、第五輪 `e2c8cf4` 針對 U11 補修、第六輪 `5b3f148` 針對第五輪處理、第七輪 `60d0cab` 針對 A4／A5、第八輪 `3f712aa` 針對 B1–B3），前五輪結論「有出入」、第六輪無程式上的 must-fix、第七、八輪無 must-fix，處理見 §11
- 輸入：spec v1.1 P4／G4／§7／§9、ADR-0001～0021、manifest、P3 報告 §9 延續項目（U2、U4 f001／f006、U9）、`docs/traceability.md` 預登記的 G4-01～G4-07
- S1／S2 工程師決定（2026-10-29，ADR-0021）：預覽維持 MuPDF，偵測 CID 不在 charset 時提示 `PREVIEW_UNRELIABLE`；
  UI 只呼叫 DocumentService 公開 API、單一背景執行緒；新增 worker 操作 `preview_edit`；macOS 只有 CI 證據，實機項目標 NOT RUN。

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；pypdfium2 5.13.0（只在測試）；fontTools 4.66.0；Pillow 13.0.0；PySide6-Essentials 6.11.2；pytest-qt；字型同 P2。**G4 測試以 offscreen 執行，非實機人工驗收** |
| macOS 實機 | NOT RUN（無實機，ADR-0003、ADR-0021 §3） | — | — |
| CI windows | windows-latest x64（windows-2025 映像） | GitHub 標準 runner | Python 3.13.16；套件同上（`uv.lock`）；offscreen |
| CI macos | macos-15 arm64 | GitHub 標準 runner | Python 3.13.15（Python 小版本不由 `uv.lock` 鎖定）；套件同上；offscreen |

相依沒有變更（`uv.lock` 未改）。

## 3. 需求 → test ID → fixture／hash → 結果

fixture hash（前 12 碼）：T01 `65a4ebca20fe`、T05 `3704edfda119`、F02 `661ad2572758`、F04 `6dda72bbbb80`、F05 `6ba509976fbf`、U01 `29d8728efbee`。
「本機」＝Windows 製作機 offscreen；「CI」＝run 41029981106（commit `ffcecc3`）雙平台 360 passed，涵蓋 G4-01～G4-09、U7～U9、U11（含第四至六輪補修）與第二輪核對 W1（§4）。實機欄另列。

| 需求 ID | test ID | fixture | 本機／CI | 實機 |
| --- | --- | --- | --- | --- |
| G4-01 | `tests/gui/test_e2e.py::test_flow_*`（12 項：開檔與縮圖、點選、預覽前後對照不提交、套用、undo／redo、另存重開、覆寫既有目的檔、模式 B 字型替換、溢出說明、尋找文字跨段落選取、預覽不可靠提示、崩潰後復原草稿），另 `::test_source_never_modified` | T01、F02、F04 | PASS | Windows NOT RUN；macOS NOT RUN |
| G4-02 | `tests/gui/test_ime.py::test_preedit_not_committed`：以 QInputMethodEvent 模擬注音組字，組字中文字不進入內容、不規劃；確認字不規劃；Enter 後只以已確認的「測試局」規劃一次；`::test_enter_during_preedit_not_planned`：組字中按 Enter 或「預覽」不規劃，確認後才規劃（U7） | T01 | PASS | Windows NOT RUN；macOS NOT RUN |
| G4-03 | `tests/gui/test_paths.py::test_unicode_paths`（3 組：中文目錄＋中文檔名、空白、emoji）：開啟、編輯、另存到同類路徑、重開見新文字 | T01 | PASS | Windows NOT RUN；macOS NOT RUN（測試以 `ask_save`／`open_path` 繞過原生檔案對話框，對話框選取這類路徑須實機） |
| G4-04 | `test_e2e.py::test_cancel_does_not_commit`：長操作中取消回 CANCELLED，revision 與 history 皆為 0，worker 重啟後頁面為原文 | F04 | PASS | — |
| G4-05 | `test_e2e.py::test_reason_shown_for_uneditable`：不可編輯目標顯示「無法編輯：<理由>」且不能預覽；U01 顯示無文字層 | F05、U01 | PASS | — |
| G4-06 | `tests/gui/test_shortcuts.py::test_platform_shortcuts`：開啟／另存／復原／重做為 Qt 標準鍵、修飾鍵為 ControlModifier（Qt 在 macOS 對應 Cmd）、原生顯示 Windows `Ctrl+`／macOS `⌘`；以按鍵實際觸發 undo、redo | F04 | PASS | Windows NOT RUN；macOS Cmd NOT RUN |
| G4-06 | `tests/gui/test_responsiveness.py::test_ui_not_blocked`：worker 睡 1.5 秒期間，10 ms 計時器的最大間隔 ≤100 ms、送出工作 ≤100 ms | F04 | PASS | — |
| G4-07 | `tests/gui/test_fonts.py::test_cjk_font_rendering`：頁面原中文字形有畫出（文字框內有深色像素）；兩個不同中文新字串的「修改後」預覽圖不同（排除空白與同一缺字框）；介面拿到的文字未改碼 | T05 | 預覽 PASS | UI 元件中文字形 NOT RUN（offscreen 沒有系統字型，見 §7） |
| G4-08 | `tests/integration/test_preview.py`（3 項）：全部 available fixture（排除加密、損壞）逐頁分析，帶 PREVIEW_UNRELIABLE 的恰為 ADR-0015 的 7 份；worker 層 preview_edit 前後圖不同、revision／內容指紋／applied 不變、之後同一 plan_id 可套用；其他未套用計畫失效；無效 plan_id 回 INVALID_REQUEST | 全部 available、F04 | PASS | — |
| G4-09 | `test_drafts.py::test_draft_structure_validated`（14 組）、`::test_recover_failure_closes_document`、`test_transaction.py::test_plan_params_copied`、`test_crash_injection.py::test_temp_recorded_while_writing`、`::test_cleanup_recorded_removes_only_own_temps`、`::test_cleanup_recorded_malformed_registry`（第二輪核對 W1）、`tests/gui/test_startup.py`（2 項，U8）、`tests/gui/test_drafts_ui.py`（7 項：全列草稿 U9；正常關閉刪草稿 U11） | T01、F04、測試內樣本 | PASS | — |

G4 驗收條件：

1. **每平台至少 12 個 E2E 流程**：G4-01 有 12 項 `test_flow_*`，CI 雙平台執行通過；但 spec 寫「兩平台實機」，實機 NOT RUN。
2. **IME 組字中不提前送出**：G4-02 只驗證到 Qt 層（QInputMethodEvent）；實際輸入法（注音、倉頡、macOS 注音）的 Enter 由輸入法吃掉，offscreen 無法模擬，須實機。
3. **中文、空白、emoji 路徑**：G4-03。
4. **取消不提交**：G4-04。
5. **不可編輯物件顯示原因**：G4-05。
6. **中文字型正確顯示**：G4-07 預覽部分；UI 部分須實機。
7. **Ctrl／Cmd 快捷鍵、worker 不阻塞 UI**：G4-06。

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q                                        → exit 0，360 passed（Windows 製作機 offscreen，2026-10-30，第六輪核對 A4／A5 處理後）
```

- P4 新增 54 項測試（含 U7 的 1 項、U8 的 2 項、U9 的 2 項、第二輪核對 W1 的 1 項、U11 的 5 項，見下）。初版 G4 的 `tests/gui/` 22 項：`test_e2e.py` 15 項、`test_paths.py` 3 項（參數化）、`test_ime.py`、`test_shortcuts.py`、`test_responsiveness.py`、`test_fonts.py` 各 1 項。
  U2 補測試 21 項（G4-08、G4-09）：`test_preview.py` 3 項、`test_drafts.py` 15 項（結構驗證 14 組＋復原失敗）、`test_crash_injection.py` 2 項、`test_transaction.py` 1 項；
  既有檔案只在末尾新增測試（`test_crash_injection.py` 另加 `import json`）。P3 既有 306 項未修改、全數通過。
- U2 補測試的反向驗證（暫時把修正改回舊行為後執行，再以 `git checkout` 還原）：拿掉 `_valid`→結構驗證 12／14 組失敗（另 2 組是 saved_at 的 NaN 與未來時間，由 `_expired` 負責，未改動）；
  editable_region 不存副本→`test_plan_params_copied` 失敗；復原只捕 ServiceError→`test_recover_failure_closes_document` 失敗；
  不寫暫存紀錄→`test_temp_recorded_while_writing` 失敗；清除時不檢查命名→`test_cleanup_recorded_removes_only_own_temps` 失敗；preview_edit 不回滾→`test_preview_edit_does_not_commit` 失敗。`tests/gui/conftest.py` 的 `make_window` fixture 與 `test_e2e.py` 同在 `28d89b5` 新增。
- CI：run [40994221324](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40994221324)（commit `28d89b5`，不含 G4-08、G4-09）windows-latest 328 passed、macos-15 328 passed；
  run [40998022034](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40998022034)（commit `ecc067b`）windows-latest 349 passed、macos-15 349 passed；
  U7 修正後 run [41001063910](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41001063910)（commit `c234632`）windows-latest 350 passed、macos-15 350 passed。
  同分支的 run 40994200432 是推送時 commit 尚未建立所觸發，內容為 P3 合併點 `0ecf673`，不是 P4 證據。
- U7 修正（`app.py` 新增 `TextInput`，記錄 IME 組字狀態；`request_preview` 組字中不規劃）與測試 `test_ime.py::test_enter_during_preedit_not_planned`。反向驗證：拿掉組字檢查後該測試失敗（規劃了空字串 `['']`）。
- U8 處理：`run()` 的啟動接線抽成 `app.py::prepare_storage()`（行為不變），ADR-0021 §2 註明例外；測試 `tests/gui/test_startup.py` 2 項（草稿區與紀錄位置設定、清除上次暫存檔；草稿區不可用時仍啟動並清除）。反向驗證（以備份檔還原）：拿掉清除或拿掉紀錄位置設定，2 項皆失敗。
- U9 修正：新增 `DraftDialog`，列出全部未逾期草稿（檔名、編輯數、儲存時間，不含完整路徑），使用者選一份復原或捨棄；捨棄後再列出其餘；復原一份後其餘保留，下次啟動再列出（一次只開一份文件）。測試 `tests/gui/test_drafts_ui.py` 2 項。反向驗證（以備份檔還原）：捨棄後不再列出、只列第一份，各使對應測試失敗。
  U8 處理後 CI run [41004289165](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41004289165)（commit `77a6348`）雙平台 352 passed；U9 修正後 run [41005065222](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41005065222)（commit `b9a383e`）windows-latest 354 passed、macos-15 354 passed。
- 第二輪核對 W1 修正：`transaction._recorded()` 另捕捉 `RecursionError`（巢狀過深的 `pending-temps.json` 原會使啟動與另存中斷）；測試 `test_crash_injection.py::test_cleanup_recorded_malformed_registry`（巢狀過深、非清單、刪除失敗保留）。反向驗證（以備份檔還原）：拿掉 `RecursionError` 後該測試失敗（json decoder RecursionError）。CI run [41011809272](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41011809272)（commit `cb40fdf`）windows-latest 355 passed、macos-15 355 passed。
- U11 修正：`MainWindow.closeEvent` 在背景工作進行中先 `service.cancel()`，`JobRunner.shutdown(wait=True)` 等背景執行緒結束，再 `close_document` 刪除草稿。測試 `test_drafts_ui.py::test_close_window_discards_draft`、`::test_close_window_while_busy`（worker `_sleep` 20 秒中關閉，10 秒內完成）。反向驗證（以備份檔還原）：拿掉 `close_document`→前者失敗（草稿仍在）；拿掉取消→後者失敗（等了 20 秒）。CI run [41017277282](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41017277282)（commit `5d4a5df`）windows-latest 357 passed、macos-15 357 passed。
- U11 第四輪核對補修（§11 Y1、Y2）：`JobRunner.shutdown(cancel)` 不再接受新工作、取消排隊中的工作，對執行中的工作每 50 ms 重試 cancel 直到結束（多段呼叫的工作在兩段之間 cancel 打不中，原本會凍結主執行緒到整個工作完成），再以 `QCoreApplication.sendPostedEvents` 收下已完成工作的結果，之後才 `close_document`（原本關閉後才送達的開檔／復原結果會留下文件與草稿，並因對已關閉的執行緒池送工作而丟 RuntimeError）。測試 `::test_close_window_while_busy_between_calls`（工作先在 Python 端 0.5 秒再送 20 秒請求）、`::test_close_window_delivers_finished_result`。反向驗證（以備份檔還原）：只取消一次→前者失敗（等了 20 秒）；拿掉 `sendPostedEvents`→後者失敗（service 仍有 1 份文件）。殘餘：取消重試只能打斷 worker 端的請求；關閉時主執行緒仍要等目前這段 Python 端運算跑完（無上限），每次終止 worker 最多再等 5 秒（ADR-0021 §2 例外）。CI run [41022660909](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41022660909)（commit `51c3c0d`）windows-latest 359 passed、macos-15 359 passed。
- U11 第五輪核對處理（§11 Z1–Z5）：關閉後 `offer_drafts` 直接 return（`JobRunner.closed`），不在關閉流程中跳出「復原草稿」對話框；ADR-0021 §2 與 `jobs.py`／`app.py` docstring 註明關閉流程是「主執行緒不等待 worker」的例外。測試 `test_drafts_ui.py::test_close_window_does_not_offer_drafts`。反向驗證（以備份檔還原；第六輪核對連跑 3 次重做）：拿掉 closed 檢查→失敗（對話框被呼叫）。CI run [41028316187](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41028316187)（commit `5b3f148`）windows-latest 360 passed、macos-15 360 passed。
- 第六輪核對處理（§11 A4、A5）：`test_close_window_while_busy_between_calls`、`test_close_window_delivers_finished_result`、`test_close_window_does_not_offer_drafts` 改為等工作確實開始（`threading.Event`）才關閉視窗，消除「工作未開始即被取消而偽通過」；反向驗證重做（以備份檔還原）：只取消一次、拿掉 `sendPostedEvents`、拿掉 closed 檢查，三項各自失敗（實作方各跑 1 次；第七輪核對各跑 3 次，9／9 只有對應測試失敗）。ADR-0021 §2 補關閉時 `close_document` IPC 的等待上限。本機 360 passed；CI run [41029981106](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41029981106)（commit `ffcecc3`）windows-latest 360 passed、macos-15 360 passed。
- 實作時發現並修正：`drafts.py` 的 `_valid()`（P3 triage f001）插在 `DraftStore` 類別中間，使 `_remove_if_old`、`_file` 變成 `_valid` 內的巢狀函式；
  修正前 5 項失敗（`test_drafts.py` 4 項、`test_flow_recover_draft_after_crash`）。
- `test_ui_not_blocked` 的反向驗證（臨時檔，未入庫）：`JobRunner.submit` 改為同步執行時，失敗點是 `window.busy` 斷言，不是計時斷言（獨立核對 V3）；另在睡眠工作期間於主執行緒插入 250 ms 工作，計時斷言失敗（最大間隔 260 ms > 100 ms），確認計時量測有效。量測的是 worker `_sleep` 期間的事件迴圈；主執行緒自身的工作（`_previewed` 解碼 PNG、`load_page` 顯示頁面）耗時未量測。
- preview_edit 不回滾的反向驗證，獨立核對重做時的失敗點是重新規劃時的 REVISION_CONFLICT 例外（不是 revision／指紋斷言），另有 2 項測試同時失敗；結論相同。
- `test_fonts.py`：traceability 預登記 T01，第一版改用 F02，兩者都在 ADR-0015 的 7 份 MuPDF 空白檔內（F02 頁面文字區域渲染全白，測試失敗），改用 T05（不在例外清單）。

## 5. 真修改證據

本段沒有新增編輯能力，編輯證據沿用 P2（`reports/P2/evidence/`）。P4 的 UI 經 DocumentService 呼叫既有 plan／apply／undo／redo／export，
E2E 測試確認：套用後頁面目標文字更新、另存檔以 PyMuPDF 擷取到新文字、重開後目標為新文字；原檔 SHA-256 不變（`test_source_never_modified`）。

新增的 `preview_edit`（ADR-0021 §2）：在工作文件上套用計畫、渲染改動頁前後圖、回滾到套用前的工作文件位元組（ADR-0021 §2 寫作「開啟自的位元組」，指同一件事），再以同一參數重新規劃並沿用 plan_id。
E2E 確認預覽後 UI 的 revision 仍為 0、前後圖不同、之後可正常套用。

## 6. 資料完整性與資源／出站紀錄

- **UI 不碰 PDF**：`src/peditor/ui/` 不匯入 PyMuPDF／pikepdf，G1-01 測試持續通過。但不是「只用 DocumentService」：`app.py:38` 匯入 `core.geometry`（點擊判定座標換算）；啟動時的 `prepare_storage()` 直接建立 `DraftStore`、設定 `transaction.registry` 並呼叫 `transaction.cleanup_recorded()`，不經 DocumentService；已在 ADR-0021 §2 註明為例外，測試 `tests/gui/test_startup.py`（§9 U8）。
- **預覽不提交**：`preview_edit` 回滾到套用前的位元組與 applied 清單，revision 不變；副作用是同文件其他未套用計畫會失效（ADR-0021 後果）。
- **暫存檔清除（P3 U9）**：交易建立暫存檔時記錄到本機資料目錄的 `pending-temps.json`，完成或已刪除即移除紀錄；
  UI 啟動時刪除紀錄中符合 `.~peditor-*.tmp.pdf` 命名的檔案。紀錄失敗或紀錄檔損壞（含巢狀過深）不影響啟動與另存（G4-09）。CLI 不設紀錄檔。
  殘餘：啟動清除不檢查年齡、沒有單一實例鎖，同時執行兩個 PEditor 時後啟動者會使前者寫入中的另存失敗（原檔與目的檔不受影響）；紀錄讀改寫未加鎖（§9 U10，列 P7）。
- **復原草稿**：UI 啟用；啟動時列出全部未逾期草稿，由使用者選一份復原或捨棄；捨棄後再列出其餘，復原一份後其餘保留到下次啟動（§9 U9）；對話框只顯示檔名、不含完整路徑。草稿結構驗證（f001）：draft_id、path、sha256、log、position、
  每筆 params 與 base_revision 型別不符即視為損壞並刪除；saved_at 非有限數或晚於現在 60 秒以上視為無效。
  復原時任何例外都關閉開啟一半的文件（`except BaseException`）。
- **參數副本（P3 f006）**：`plan_text_edit` 的 editable_region 存副本。
- **錯誤訊息**：UI 只顯示理由碼對應的繁中說明（`ui/messages.py`），不含路徑與原文；未預期例外統一顯示 WORKER_FAILED。
- **出站**：新增模組未匯入網路模組（`test_offline_guard` 通過）。實機出站監測於 P7。
- **資源**：預覽每次約為一次 apply 加一次重新規劃；頁面 100 DPI、縮圖 24 DPI、縮圖最多 200 頁。效能未量測（§7）。

## 7. 限制、阻擋、未測項目

- **Windows 實機人工驗收**：NOT RUN。驗收清單見 `reports/P4/windows-acceptance.md`（W01–W31，經第三輪獨立核對修正，§11）。G4-04 實機：套用約 0.15 秒，人工來不及按取消，清單 W26 多半只能標 NOT RUN（§9 U14）。IME（注音／倉頡實機輸入）、快捷鍵實按、中文 UI 字型、12 個 E2E 流程的人工操作皆未做。
- **macOS 實機**：NOT RUN（ADR-0021 §3、P3 U1）。
- **UI 中文字形**：offscreen 平台的字型資料庫沒有任何繁中字型（實測 `QFontDatabase.families(TraditionalChinese)` 為 0），
  介面元件的中文是否顯示正確無法自動驗證。
- **ADR-0015 的 7 份檔案**：預覽空白，只顯示 `PREVIEW_UNRELIABLE` 提示；E2E 只確認 T01 有提示。
- **E2E 的捷徑**：覆寫既有目的檔直接呼叫 `save_as`（覆寫確認對話框未測）；G4-04 與 U11 的 `test_close_window_while_busy*`、`test_close_window_delivers_finished_result` 以私有 `window._run`、`window._opened`、`service._send_raw`／`open_document` 搭配 worker `_sleep` 模擬長操作或晚到的結果，並以 `service._docs` 斷言沒有殘留文件；`test_close_window_does_not_offer_drafts` 以 `_run` 加 sleep 工作模擬「捨棄後再列出草稿」的回呼，不是實際捨棄流程，不是實際套用流程；G4-05 以 `select_target` 選取，不是點選；G4-03 繞過檔案對話框。這些都須實機補驗。
- **G4-07 字型測試**能分辨空白與同一缺字框，但不驗證畫出的字形是否對應正確的字。
- **G4-08** 的「全部 available fixture」排除加密（U02）與損壞（S01），實際 43／45 份；pending 的 16 份不在 repo。
- **§8.3 效能**：NOT RUN（P2 U5、P3 U7 延續）。大檔的預覽與 undo 重播耗時未量測。
- **盲測**：NOT RUN，P8 執行。

## 8. 安全審查

- CLAUDE.md 規定的 vuln-scan／triage 時點是 P1、P2、P3、P7，P4 沒有規定：**NOT RUN**。
- 新增的攻擊面：worker 操作 `preview_edit`（只接受 plan_id，型別錯誤回 INVALID_REQUEST）；`cid_not_in_charset` 解析字型程式（例外一律回 False）；
  本機資料目錄的 `pending-temps.json`（啟動時讀取，只刪符合本程式命名的檔案）。`PREVIEW_UNRELIABLE` 偵測使每次 `inspect_page` 都以 fontTools 解析 CID-keyed CFF，只開檔檢視就會觸發（P2 模式 A 只在規劃時），見 THREAT_MODEL T5。
- `THREAT_MODEL.md`：已更新（U5），第二輪獨立核對後再修正（§11）。§1 加 P4 段落；§3 編輯請求加 `preview_edit`、新增「暫存紀錄檔」入口；T3 殘餘改為啟動清除後的情況；T5 加 `preview_edit` 成本與 charset 偵測的字型解析；T11 加點擊判定與 preview_edit 回滾；新增 T14（`pending-temps.json` 遭竄改或洩漏資料夾路徑，low／mitigated）。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | Windows 實機人工驗收（IME、快捷鍵、中文 UI 字型、E2E）尚未執行；macOS 實機依 ADR-0021 NOT RUN | G4 要求「兩平台實機」，目前只有 offscreen 證據 | 工程師安排 Windows 實機驗收；macOS 依 P3 U1 |
| U2 | 第一版報告時下列行為改動沒有直接測試：暫存紀錄與啟動清除（P3 U9）；PREVIEW_UNRELIABLE 恰標出 7 份；`_valid`（f001）；editable_region 副本（f006）；復原失敗關閉文件；preview_edit 的 worker 層行為 | — | **已處理**（工程師 2026-10-30 決定合併前補）：G4-08、G4-09 共 21 項，反向驗證見 §4 |
| U3 | G4-02 只在 Qt 層模擬組字；實機輸入法在組字中按 Enter 由輸入法處理，offscreen 無法驗證 | IME 證據不完整 | 實機驗收（U1） |
| U4 | `preview_edit` 會讓同文件其他未套用計畫失效；UI 一次只有一個計畫，目前沒有影響 | 未來多計畫 UI 須注意 | 備查 |
| U5 | `THREAT_MODEL.md` 未納入 `pending-temps.json` 與 `preview_edit` | 威脅模型與實作不一致 | **已處理**（工程師 2026-10-30 決定更新）：見 §8；文件變更，無行為改動、無新測試 |
| U7 | 組字中（preedit 進行中）按 Enter：offscreen 下 `returnPressed` 仍觸發，修正前會送出空字串規劃（獨立核對 V6 延伸）；`app.py` 原註解「組字中不觸發 returnPressed」不是 Qt 保證的行為 | 實機輸入法若不攔截 Enter，會以組字前內容規劃 | **已處理**（工程師 2026-10-30 決定合併前修）：`TextInput` 追蹤組字狀態，組字中按 Enter 或「預覽」不規劃；測試 `test_enter_during_preedit_not_planned`（修正前失敗）。實機輸入法行為仍待 U1 驗收 |
| U8 | `run()` 繞過 DocumentService 直接操作 `DraftStore`、`transaction.registry`（獨立核對 V2），啟動接線無測試 | 與 ADR-0021 §2 字面不一致 | **已處理**（工程師 2026-10-30 決定在 ADR 註明例外並補測試）：抽成 `prepare_storage()`，ADR-0021 §2 新增例外說明；`tests/gui/test_startup.py` 2 項 |
| U9 | 多份草稿時一次只詢問第一份（獨立核對 V11） | 其他草稿要到下次啟動才處理 | **已處理**（工程師 2026-10-30 決定改為全列）：`DraftDialog` 列出全部草稿、捨棄後再列出其餘；`tests/gui/test_drafts_ui.py` 2 項（修正前行為下失敗）。復原一份後其餘仍要到下次啟動才列出 |
| U10 | 多實例同時執行：啟動清除不檢查暫存檔年齡、沒有單一實例鎖；`_record` 讀改寫未加鎖（第二輪核對 W2） | 另一實例的另存失敗（原檔與目的檔不受影響）；並行時可能遺失紀錄而退回 P3 清除方式 | **列 P7**（工程師 2026-10-30 決定）；已記入 THREAT_MODEL T3、§8 |
| U11 | 按視窗 ✕ 正常關閉時 UI 不呼叫 `close_document`（`closeEvent` 只停 JobRunner），草稿不刪，下次啟動仍列出（第三輪核對，offscreen 實測） | 與 ADR-0020 §5「正常 close_document 時刪除」及 THREAT_MODEL T13「正常關閉即刪」不一致；草稿（含新文字）多留最多 7 天 | **已處理**（工程師 2026-10-30 決定修）：`closeEvent` 先取消進行中的請求、等背景執行緒結束，再 `close_document`（刪草稿）；測試 `tests/gui/test_drafts_ui.py::test_close_window_discards_draft`、`::test_close_window_while_busy`（修正前／拿掉取消時失敗，§4）；第四輪核對後補：取消重試、關閉前收下已完成結果（`::test_close_window_while_busy_between_calls`、`::test_close_window_delivers_finished_result`）；第五輪核對後補：關閉中不再跳出草稿對話框（`::test_close_window_does_not_offer_drafts`），ADR-0021 §2 註明關閉流程是「主執行緒不等待 worker」的例外；清單 W31 改為依 ADR 判定。未驗證：Windows 登出／關機時是否觸發 closeEvent（Qt session 行為，須實機） |
| U12 | 快捷鍵：「重做」只綁第一組 Ctrl+Y（`setShortcut`），Ctrl+Shift+Z 無作用；套用後焦點在「尋找文字」欄，Ctrl+Z 由輸入欄處理而非文件復原；工具列提示不顯示快捷鍵 | 使用者可能以為復原失效 | **列 P7**（工程師 2026-10-30 決定）；清單 W10、W11、W24 標已知不符 |
| U13 | 開啟 0 頁文件（加密 U02）後頁面區仍顯示前一份文件與目標框 | 使用者可能點選到已關閉文件的框 | **列 P7**（工程師 2026-10-30 決定）；清單 W06 記錄 |
| U14 | G4-04 實際套用流程的取消，人工在實機來不及操作（套用約 0.15 秒） | G4-04 只有 offscreen 證據（worker 延遲模擬） | **列 P7**（工程師 2026-10-30 決定）；清單 W26 照實記錄 |
| U6 | P3 延續：U3（重播 30 秒逾時）、U7（§8.3 效能）、U10（影像雜湊解讀）、U11（逾時路徑無測試）、U12（服務層 undo 失敗無測試） | 同 P3 報告 | 同 P3 報告 |

## 10. 關卡結果

- CI：run [41029981106](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41029981106)（commit `ffcecc3`，第六輪核對 A4、A5 處理後）windows-latest 360 passed、macos-15 360 passed；run [41028316187](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41028316187)（commit `5b3f148`，U11 第五輪核對處理後）windows-latest 360 passed、macos-15 360 passed；run [41022660909](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41022660909)（commit `51c3c0d`，U11 第四輪補修後）windows-latest 359 passed、macos-15 359 passed；run [41017277282](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41017277282)（commit `5d4a5df`，U11 修正後）windows-latest 357 passed、macos-15 357 passed；run [41011809272](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41011809272)（commit `cb40fdf`，第二輪核對處理後）windows-latest 355 passed、macos-15 355 passed；run 41010683123（commit `efc3ddf`，U5，只改文件）雙平台 354 passed；run [41005065222](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41005065222)（commit `b9a383e`，U9 修正後）windows-latest 354 passed、macos-15 354 passed；run 41004289165（`77a6348`）352 passed；run 41001063910（commit `c234632`，U7 修正後）雙平台 350 passed；run 40998022034（commit `ecc067b`）雙平台 349 passed；先前 run 40994221324（commit `28d89b5`）雙平台 328 passed。
- **關卡結果：BLOCKED**。G4-01～G4-09 都有自動測試，本機與 CI 雙平台通過；但 G4 要求兩平台實機，Windows 實機人工驗收尚未執行（U1），
  U2 已補測試。
- **下一段可開始：否**。條件：Windows 實機驗收完成（含 G4-03 檔案對話框與實機輸入法組字中按 Enter）。macOS 依 ADR-0021 §3 附條件。

## 11. 獨立核對紀錄

第一輪（2026-10-30，HEAD `ecc067b`）：未參與實作的 Claude 子代理人重跑 ruff（通過）與 pytest（349 passed）；以 `git diff 0ecf673 HEAD -- tests/` 確認既有測試沒有刪除或改預期；
核對 CI run 40994221324、40998022034、40994200432 的 commit 與測試數；核對 fixture hash、套件版本、offscreen 繁中字型數；
重做 4 項反向驗證（preview_edit 不回滾、editable_region 不存副本、拿掉 `_valid`、JobRunner 改同步），結束時工作目錄乾淨。結論「有出入」，無 must-fix，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| V1（should-fix） | 報告引用的 CI run 40994221324 是 `28d89b5`，不含 G4-08、G4-09 的 21 項 | §1、§3、§4、§10 與 traceability 改引 run 40998022034（`ecc067b`，雙平台 349 passed） |
| V2（should-fix） | §6「UI 只匯入 DocumentService 與 Qt」不準確；`run()` 繞過 DocumentService，啟動接線無測試 | §6 改寫；§9 U8，ADR-0021 註明例外並補測試 |
| V3（should-fix） | JobRunner 同步化的反向驗證失敗在 busy 斷言，未證明計時斷言有效；主執行緒工作未量測 | 另做反向驗證（主執行緒插入 250 ms，計時斷言失敗）；§4 註明 |
| V4（should-fix） | G4-03 實機「不需」是自行判斷，檔案對話框未驗證 | 改為 Windows／macOS NOT RUN，§7 註明 |
| V5 | conftest 不是「移動」 | §4 改寫 |
| V6 | IME 測試未涵蓋組字中按 Enter | 以臨時測試驗證，發現 offscreen 下仍會以空字串規劃；§9 U7，已修正並補測試 |
| V7 | E2E 有捷徑（save_as、_run、select_target） | §7 註明 |
| V8 | preview_edit 反向驗證的失敗型態 | §4 註明 |
| V9 | traceability 未說明 G4-04／G4-06 fixture 由 T01 改 F04、G4-08 排除 2 份 | traceability 補註；§7 註明 43／45 份 |
| V10 | macOS CI 的 Python 是 3.13.15 | §2 改寫 |
| V11 | 多份草稿一次只問一份 | §6 改寫；§9 U9，已改為全列並補測試 |

第二輪（2026-10-30，HEAD `efc3ddf`，針對 U5 的 THREAT_MODEL 更新）：未參與實作的 Claude 子代理人只讀核對 THREAT_MODEL 每項新陳述與程式碼、測試是否相符，
確認 CI run 41010683123（`efc3ddf`）雙平台 354 passed，並在 scratchpad 實測過深 JSON 與 `cleanup_recorded()`；結束時工作目錄乾淨。結論「有出入」，must-fix 1 項（W1，已由實作方重現），處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| W1（must-fix） | T14「JSON 錯誤一律視為空紀錄」不成立：巢狀過深的 `pending-temps.json` 使 `_recorded()` 丟出 RecursionError，啟動（`prepare_storage`）與另存（`_record`）中斷，每次啟動重現 | 程式修正（另捕捉 `RecursionError`）並補測試 `test_cleanup_recorded_malformed_registry`（修正前失敗，§4）；T14 改寫 |
| W2（should-fix） | 啟動清除不檢查年齡、無單一實例鎖，多實例時會刪掉另一實例寫入中的暫存檔；`_record` 讀改寫未加鎖 | THREAT_MODEL T3 殘餘、§8 新增一列；§6、§9 U10，列 P7 |
| W3（should-fix） | T5 未說明 charset 偵測在每次 `inspect_page` 執行、不快取，只開檔檢視即讓不可信 CFF 進入 fontTools | T5、§1 補述；§8 註明 |
| W4（should-fix） | §1「所有呼叫在單一背景執行緒」過寬：`cancel`、`history`、`list_drafts` 在主執行緒 | THREAT_MODEL §1 改寫（ADR-0021 §2 原文同此寫法，未改 ADR） |
| W5（should-fix） | T3 未註明「僅 UI；CLI 不記錄」；T14 所述非清單、刪除失敗保留、符號連結無測試 | T3 補註；非清單與刪除失敗保留補入 W1 測試；符號連結在 T14 標「未測」 |
| W6（should-fix） | 報告 §1 未列 `efc3ddf`、§10 未列 run 41010683123 | 已補 |
| W7 | 「開啟自的位元組」實為套用前的工作文件位元組 | THREAT_MODEL §1、T11 與報告 §5 改寫；ADR-0021 未改 |
| W8 | preview_edit 成本另含一次重新開啟 | T5 補述 |
| W9 | T14 排在 T13 之前；§8 無 T14 對應列 | T14 移到 T13 之後；§8 新增一列（與 W2 同列） |
| W10 | G4-08 只測 revision 0 的預覽回滾；provenance 未標 commit | 備查，未處理 |

第三輪（2026-10-30，HEAD `00f8a7d`，針對 Windows 實機驗收清單）：未參與撰寫的 Claude 子代理人以 offscreen MainWindow、真的 worker 與 Windows PowerShell 5.1 實測清單各步驟（**不是實機證據**），結束時工作目錄乾淨。
結論「清單無法照做」，處理如下（清單已重寫；產品行為不符的項目列 §9 U11–U14：U11 已修正，U12–U14 列 P7）：

| # | 出入 | 處理 |
| --- | --- | --- |
| X1（must-fix） | W19 開啟輸出檔後，W20 存回同檔被拒、W21 選原檔時原檔已不在開啟清單而**真的被覆寫** | 重排：另存、覆寫、拒絕覆寫原檔都在編輯 `公文 草稿.pdf` 時做，最後才開輸出檔；W20 加 hash 比對 |
| X2（must-fix） | 準備步驟沒設 `PEDITOR_MODE_B_FONT`，模式 B 不可用（W13、W16、W25、W26 失敗） | §1 加設定並說明須同一視窗啟動 |
| X3（must-fix） | 套用後焦點在輸入欄，Ctrl+Z 被吃掉；Ctrl+Shift+Z 未綁定 | W10 先點頁面；W11 以 Ctrl+Y 判定，Ctrl+Shift+Z 記錄；U12 |
| X4（must-fix） | 拒絕覆寫原檔時 UI 實際顯示「操作無法執行」，且先出現原生取代確認 | W20 改寫 |
| X5（must-fix） | 工具列提示不顯示快捷鍵 | W24 改為記錄；U12 |
| X6（must-fix） | 按 ✕ 正常關閉不刪草稿，W31 無法依 ADR 判定 | U11 已修正並補測試；W31 依 ADR 判定 |
| X7（must-fix） | W15 以 W17 確認結果，但 W17 是另一份文件 | W15 改為另存 T01 後以 Edge 確認 |
| X8 | emoji 路徑在 5.1 無 BOM 腳本會壞；桌面可能被 OneDrive 重新導向 | 以 `ConvertFromUtf32` 組字、`GetFolderPath('Desktop')`，並註明直接貼到視窗 |
| X9 | W27 指令放在表格內，`\|` 複製後失效 | 移到 code block；加等「已更新」與殘留行程檢查 |
| X10 | W04–W06、W12–W14 預期字串不精確；空白頁、灰框、亂碼未說明 | 寫出 `ui/messages.py` 實際字串；說明 ADR-0015 空白檔屬預期 |
| X11 | W16 未先重開文件；W16d 判定不明 | 補前置步驟與判定標準 |
| X12 | W30 中途重啟的對話框未說明按什麼 | 改為「稍後再說」 |
| X13 | W22 暫存檔不是隱藏檔 | 改用 `Get-ChildItem -Force -Recurse` |
| X14 | W25、W26 人工操作太短 | 註明限制；§7、U14 |
| X15 | 附表 G4-01 缺 W04、沒有 G4-08；traceability G4-07 預登記實機樣本 B02 未在清單 | 附表補；新增 W03b（B02） |
| X16 | 開 U02 後頁面區仍顯示前一份文件 | W06 記錄；U13 |

第四輪（2026-10-30，HEAD `90dcf84`，針對 U11 修正）：未參與實作的 Claude 子代理人在 repo 外的 worktree（HEAD 與分支起點 `0ecf673`）實測 closeEvent 各情境與反向驗證（offscreen，**不是實機證據**），確認 357 項與 CI run 41017277282 一致；結束時 worktree 已移除、工作目錄乾淨。結論「主要情境正確，無 must-fix」，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| Y1（風險） | 工作還在 Python 端或兩段呼叫之間時 `cancel()` 回 False，`shutdown(wait=True)` 等整個工作完成（實測 8.5 秒，最壞為 30 秒逾時乘呼叫數），主執行緒凍結 | `JobRunner.shutdown(cancel)` 每 50 ms 重試取消；測試 `test_close_window_while_busy_between_calls`（§4） |
| Y2（風險） | 取消沒打中的工作在關閉後才送回結果：開檔留下文件、復原留下新草稿、`_load_thumbs` 對已關閉的執行緒池送工作丟 RuntimeError | 關閉前 `sendPostedEvents` 收下結果再 `close_document`；關閉後 `submit` 直接忽略；測試 `test_close_window_delivers_finished_result`（§4） |
| Y3 | §7 捷徑段未揭露 U11 測試也用私有 `_run`、`_send_raw` 與 `_sleep` hook | §7 補 |
| Y4 | §3 G4-09 未列 `test_drafts_ui.py`；§1 未寫第三輪；§4「tests/gui 22 項」易誤讀為目前總數 | 已補與改寫 |
| Y5 | Windows 登出／關機、macOS Cmd+Q 是否觸發 closeEvent 無法核對 | §9 U11 註明未驗證 |
| Y6 | 沒有 service 卻 busy 時關閉會 AttributeError | closeEvent 改為 service 為 None 時不傳 cancel |
| Y7 | worker 閒置時已死再關閉會多啟動一個 worker 再由 `service.close()` 收掉；close_document 罕見的未攔例外交給 excepthook（視窗仍關閉）；任務前提「teardown 先 service.close」有誤（pytest-qt 先關視窗） | 備查，未處理 |

第五輪（2026-10-30，HEAD `e2c8cf4`，針對 U11 補修 `51c3c0d`）：未參與實作的 Claude 子代理人在 %TEMP% 的 worktree 重做反向驗證（只取消一次、拿掉 `sendPostedEvents`，另加「改送 app 物件」）皆失敗，確認結果事件排在 JobRunner 的佇列；確認 359 項（較 `0ecf673` 多 53 項、既有測試刪除 0 行）與 CI run 41022660909 一致（offscreen，**不是實機證據**）；結束時 worktree 已移除、工作目錄乾淨。結論「無 must-fix」，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| Z1（建議） | 關閉流程在主執行緒等待（shutdown、`close_document` 的 IPC），與 ADR-0021 §2、`jobs.py`／`app.py` docstring「主執行緒不等待 worker」字面衝突 | ADR-0021 §2 新增關閉流程例外（工程師 2026-10-30 同意）；兩個 docstring 註明例外 |
| Z2（建議） | 關閉時仍等目前這段 Python 端運算（無上限），每次終止 worker 最多 5 秒；Y1 寫法易誤解為已完全解決 | §4、ADR-0021 §2、`JobRunner.shutdown` docstring 揭露 |
| Z3（建議） | 關閉中送達的回呼若是 `offer_drafts`，會在 closeEvent 中跳出模態「復原草稿」對話框（已重現） | 關閉後 `offer_drafts` 直接 return（`JobRunner.closed`）；測試 `test_close_window_does_not_offer_drafts`（拿掉檢查時失敗） |
| Z4（建議） | §7 未揭露 `service._docs`、`window._opened` | §7 補 |
| Z5 | 工作若攔下 CANCELLED 後無限重試，shutdown 迴圈不結束（目前沒有這種工作）；排隊工作被取消後 `busy` 停在 True（關閉後無影響）；排隊中的 `close_document(old)` 被取消會留下舊文件與草稿（機率極低）；`test_close_window_delivers_finished_result` 依賴工作在 close 前已開始（實測 200 次 0 次未開始）；`_futures` 併發安全依賴 GIL；func 丟 BaseException 時不送結果；第四輪 Y1「8.5 秒」無實驗紀錄可核對 | 備查，未處理；`JobRunner.shutdown` docstring 註明工作不得攔下 CANCELLED 後重試 |

第六輪（2026-10-30，HEAD `5b3f148`，針對第五輪處理）：未參與實作的 Claude 子代理人在 %TEMP% 的 worktree 重做反向驗證（拿掉 closed 檢查，連跑 3 次皆失敗），逐一檢查關閉中送達的回呼不再開對話框或排入工作，核對 ADR-0021 §2 新段落的 50 ms、5 秒與程式一致，確認 360 項（較 `0ecf673` 多 54 項、既有測試刪除 0 行）與 CI run 41028316187 雙平台 360 passed 一致（offscreen 與 CI，**不是實機證據**）。結束時 worktree 已移除、工作目錄乾淨。結論「程式無 must-fix」：

| # | 出入 | 處理 |
| --- | --- | --- |
| A1（must-fix） | §3、§10、traceability 的 CI 證據仍是 run 41022660909（359，不含新測試） | 改引 run 41028316187（`5b3f148`，雙平台 360 passed） |
| A2 | §7 未揭露新測試以 `_run`＋sleep 工作模擬捨棄回呼 | §7 補 |
| A3 | §4 沒有第五輪處理的專段；§1 未列 `5b3f148` | 已補 |
| A4 | 新測試若工作在 close 前尚未開始，會被取消而偽通過（不會誤報失敗；空閒時實測 200/200 已開始，高負載未測），與 `test_close_window_delivers_finished_result` 同一依賴 | **已處理**（工程師 2026-10-30 決定修）：三項關閉測試（含同樣依賴的 `test_close_window_while_busy_between_calls`）改為工作開頭設 `threading.Event`，`qtbot.waitUntil` 確認已開始才 close；工作若未開始則等待逾時而失敗，不會偽通過。反向驗證重做，三項各自失敗（§4） |
| A5 | ADR-0021 §2 未寫關閉時 `close_document` 的 IPC 每次最多等 30 秒（逾時再 kill 最多 5 秒） | **已處理**（工程師 2026-10-30 決定修）：ADR-0021 §2 補「worker 存活時 `close_document` 再送一個 IPC，每次最多等 `REQUEST_TIMEOUT_S` 30 秒，逾時後終止 worker 最多再 5 秒」（第七輪 B1、第八輪 C1 已改寫） |
| A6 | ADR-0021 開頭狀態／日期未註明 2026-10-30 增補（與 U8 先例一致）；「工程師同意」無法從 repo 核對，須審查時確認；新 worktree 缺被 git 忽略的字型會大量失敗 | 備查 |

第七輪（2026-10-30，HEAD `60d0cab`，針對 A4／A5 處理 `ffcecc3`）：未參與實作的 Claude 子代理人在 %TEMP% 的 worktree（已複製字型）實測：把執行緒池 submit 換成回傳已取消的 Future，模擬工作未開始即被取消——`ffcecc3` 前的 between_calls、does_not_offer_drafts 偽通過，處理後三項皆 waitUntil 逾時而失敗，確認 A4 前提存在且修法有效；
三種反向修改各跑 3 次，9／9 只有對應測試失敗；空閒 24／24、CPU 滿載 18／18 通過；`ffcecc3` 對測試只有新增、原 assert 未改；ADR 的 30 秒、5 秒與程式一致；360 項（較 `0ecf673` 多 54）與 CI run 41029981106 雙平台 360 passed 一致（offscreen 與 CI，**不是實機證據**）。結束時 worktree 已移除、工作目錄乾淨。結論「無 must-fix」：

| # | 出入 | 處理 |
| --- | --- | --- |
| B1 | ADR-0021 §2「worker 存活時」與程式條件（service 持有 worker）不精確；worker 已死時會先重啟再送 IPC（Y7），同受 30 秒＋5 秒上限 | ADR 改為「service 持有 worker 時（worker 已死則先重啟一個，啟動時間計入同一逾時）」（工程師 2026-10-30 決定修；第八輪 C1 再改寫為「新 worker 的直譯器載入計入同一逾時，建立行程的呼叫本身不計入」） |
| B2 | §4 指令區本機 360 passed 標註仍是「第五輪核對處理後」 | 改為「第六輪核對 A4／A5 處理後」 |
| B3 | §4 未寫 A4 反向驗證的連跑次數 | 補 |
| B4 | 主執行緒被系統卡住超過約 0.3 秒時，does_not_offer_drafts 可能誤報失敗、另兩項可能弱通過（負載下 18／18 通過）；ADR 修改的人工確認與 ADR 開頭未註明 10-30 增補（A6）無法從 repo 核對 | 備查；須工程師審查時確認 |

第八輪（2026-10-30，HEAD `3f712aa`，針對第七輪 B1–B3，只改文件）：未參與實作的 Claude 子代理人在 %TEMP% 的 worktree 以量測腳本實測 worker 已死時 `close_document` 的耗時組成（Windows 製作機，非 pytest、**不是實機驗收證據**）：總共 0.438 秒，其中建立行程（Popen）0.010 秒在逾時計時之前、等待回應 0.428 秒在計時之內；把逾時設為 0.05 秒時於 0.068 秒逾時並收掉新 worker，確認新 worker 的啟動等待受同一逾時限制。另確認 `3f712aa` 觸發的 CI run 41038379550 雙平台 360 passed（文件 commit 的 CI，程式證據仍引用 run 41029981106）。結束時 worktree 已移除、工作目錄乾淨。結論「無 must-fix」：

| # | 出入 | 處理 |
| --- | --- | --- |
| C1 | ADR-0021 §2「啟動時間計入同一逾時」不精確：直譯器載入在 30 秒內，但建立行程的呼叫本身（約 10 ms）在計時外、無上限（Popen 丟 OSError 已列 Y7 備查） | ADR 改為「新 worker 的直譯器載入計入同一逾時，建立行程的呼叫本身不計入」（工程師 2026-10-30 決定處理出入）；§11 B1 引文同步註明 |
| C2 | §1 commit 清單未列 `3f712aa` | 補 |
| C3 | §11 A5 處理欄仍引用舊文字「worker 存活時」 | 該列補註「第七輪 B1、第八輪 C1 已改寫」 |
| C4 | 送 IPC 另需 `doc.worker_id` 不是 None（ADR 未寫，只會讓 IPC 變少、不影響上限）；第七輪實驗數字無法從 repo 驗證；ADR 修改的人工確認與 ADR 開頭未註明 10-30 增補須工程師確認 | 備查 |

