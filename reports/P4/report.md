# P4 關卡報告：桌面文字編輯流程

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段 G4 測試都在 offscreen 平台執行（本機 Windows 與 CI），**不是實機證據**。

## 1. 階段／commit／日期

- 階段：P4　分支：`p4-desktop-ui`　commit：`28d89b5`（實作與 G4 測試）、`ecc067b`（U2 補測試，G4-08、G4-09）、`2aafaf3`（核對出入處理）、`c234632`（U7 修正）、`77a6348`（U8）、`b9a383e`（U9）、`efc3ddf`（U5，THREAT_MODEL）、`87f8e12`（U10 列 P7）、`cb40fdf`（第二輪核對出入處理，見 §11）、`00f8a7d`（實機驗收清單初版，U1）、`f601f84`（實機驗收清單，第三輪核對）、`5d4a5df`（U11）、`51c3c0d`（U11 第四輪核對補修）、`5b3f148`（U11 第五輪核對處理）、`ffcecc3`（第六輪核對 A4、A5）、`3f712aa`（第七輪核對 B1–B3）、`46febae`（第八輪核對 C1–C3，只改文件）、`314314a`（PR 核對處理）、`5d131f3`（CI 失敗時印完整 log，U15）、`c6a86d9`／`497a86e`（U15 調查與接受殘餘）、`1c4c88a`（第十一輪核對處理）、`c70b012`（第十二輪核對處理）、`6a384af`（第十三輪核對處理）、`cd89a7e`（第十四輪核對處理）、`b813899`（U15 第二次崩潰紀錄）、`c4ce81a`（第十五輪核對處理）、`c3c3524`（U15 合併前查明：測試收尾）、`69cbdc4`（U15 接受殘餘、U16 逾時設定）、`f80ed47`（第十六輪核對處理）、`e9cae93`（Windows 實機驗收結果，U1）、`a1a46c9`（第十七輪核對處理）。§1 只列實作、U 項處理與核對處理的 commit，不是完整清單；只補 hash、CI 證據或核對紀錄的報告 commit 不列（第十四輪 I1）　日期：2026-10-30～11-02
- 撰寫：Claude Code；審查：待工程師；獨立核對：2026-10-30～11-02 十七輪（第一輪 `ecc067b`、第二輪 `efc3ddf` 針對 U5、第三輪 `00f8a7d` 針對實機驗收清單、第四輪 `90dcf84` 針對 U11、第五輪 `e2c8cf4` 針對 U11 補修、第六輪 `5b3f148` 針對第五輪處理、第七輪 `60d0cab` 針對 A4／A5、第八輪 `3f712aa` 針對 B1–B3、第九輪 `0ddc265` 針對 C1–C3、第十輪 PR #11、第十一輪 U15 `497a86e`、第十二輪 `f9ff456`、第十三輪 `c70b012`、第十四輪 `b8f491b`、第十五輪 `eb73c3d` 針對 U15 第二次崩潰、第十六輪 `0fd7070` 針對 U15 測試收尾與 U16、第十七輪 `0fe585f` 針對 Windows 實機驗收寫回），前五輪結論「有出入」、第六輪無程式上的 must-fix、第七、八輪無 must-fix、第九輪無出入、第十、十一輪有出入、第十二至十五輪無 must-fix、第十六輪有出入（1 項 must-fix）、第十七輪有出入（無 must-fix），處理見 §11
- 輸入：spec v1.1 P4／G4／§7／§9、ADR-0001～0021、manifest、P3 報告 §9 延續項目（U2、U4 f001／f006、U9）、`docs/traceability.md` 預登記的 G4-01～G4-07
- S1／S2 工程師決定（2026-10-29，ADR-0021）：預覽維持 MuPDF，偵測 CID 不在 charset 時提示 `PREVIEW_UNRELIABLE`；
  UI 只呼叫 DocumentService 公開 API、單一背景執行緒；新增 worker 操作 `preview_edit`；macOS 只有 CI 證據，實機項目標 NOT RUN。

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；pypdfium2 5.13.0（只在測試）；fontTools 4.66.0；Pillow 13.0.0；PySide6-Essentials 6.11.2；pytest-qt；字型同 P2。**G4 測試以 offscreen 執行，非實機人工驗收** |
| Windows 實機（人工驗收，2026-11-02） | Windows 11 26H2（`winver`，驗收人填寫）；顯示縮放 150%、1920×1080 | 未記錄（是否為製作機未記錄） | commit `8d1f0ed`，依清單 §1 步驟（驗收人未另記套件版本）；輸入法微軟注音；非一般使用者帳號（系統管理員） |
| macOS 實機 | NOT RUN（無實機，ADR-0003、ADR-0021 §3） | — | — |
| CI windows | windows-latest x64（windows-2025 映像） | GitHub 標準 runner | Python 3.13.16；套件同上（`uv.lock`）；offscreen |
| CI macos | macos-15 arm64 | GitHub 標準 runner | Python 3.13.15（Python 小版本不由 `uv.lock` 鎖定）；套件同上；offscreen |

相依沒有變更（`uv.lock` 未改）。

## 3. 需求 → test ID → fixture／hash → 結果

fixture hash（前 12 碼）：T01 `65a4ebca20fe`、T05 `3704edfda119`、F02 `661ad2572758`、F04 `6dda72bbbb80`、F05 `6ba509976fbf`、U01 `29d8728efbee`。
「本機」＝Windows 製作機 offscreen；「CI」＝run 41029981106（commit `ffcecc3`）雙平台 360 passed，涵蓋 G4-01～G4-09、U7～U9、U11（含第四至六輪補修）與第二輪核對 W1（§4）。實機欄另列：Windows 為 2026-11-02 人工驗收（commit `8d1f0ed`，`reports/P4/windows-acceptance.md` W01–W31 共 37 項，驗收人填寫，未提交截圖，§7）。

| 需求 ID | test ID | fixture | 本機／CI | 實機 |
| --- | --- | --- | --- | --- |
| G4-01 | `tests/gui/test_e2e.py::test_flow_*`（12 項：開檔與縮圖、點選、預覽前後對照不提交、套用、undo／redo、另存重開、覆寫既有目的檔、模式 B 字型替換、溢出說明、尋找文字跨段落選取、預覽不可靠提示、崩潰後復原草稿），另 `::test_source_never_modified` | T01、F02、F04 | PASS | Windows 實機 PASS（W02、W07–W13、W15、W04、W17–W19、W21、W27–W31）；macOS NOT RUN |
| G4-02 | `tests/gui/test_ime.py::test_preedit_not_committed`：以 QInputMethodEvent 模擬注音組字，組字中文字不進入內容、不規劃；確認字不規劃；Enter 後只以已確認的「測試局」規劃一次；`::test_enter_during_preedit_not_planned`：組字中按 Enter 或「預覽」不規劃，確認後才規劃（U7） | T01 | PASS | Windows 實機 PASS（W16a–W16f，微軟注音；「其他」欄亦填 PASS，但未記錄是哪個輸入法；W16f 備註見 §9 U17）；macOS NOT RUN |
| G4-03 | `tests/gui/test_paths.py::test_unicode_paths`（3 組：中文目錄＋中文檔名、空白、emoji）：開啟、編輯、另存到同類路徑、重開見新文字 | T01 | PASS | Windows 實機 PASS（W02、W03、W17–W21，原生檔案對話框選取中文、空白、emoji 路徑）；macOS NOT RUN |
| G4-04 | `test_e2e.py::test_cancel_does_not_commit`：長操作中取消回 CANCELLED，revision 與 history 皆為 0，worker 重啟後頁面為原文 | F04 | PASS | Windows 實機：驗收人自填 PASS，是否實際取消成功不明（W26；清單預期人手多半來不及而標 NOT RUN；§9 U14 待決） |
| G4-05 | `test_e2e.py::test_reason_shown_for_uneditable`：不可編輯目標顯示「無法編輯：<理由>」且不能預覽；U01 顯示無文字層 | F05、U01 | PASS | Windows 實機 PASS（W05、W06、W14） |
| G4-06 | `tests/gui/test_shortcuts.py::test_platform_shortcuts`：開啟／另存／復原／重做為 Qt 標準鍵、修飾鍵為 ControlModifier（Qt 在 macOS 對應 Cmd）、原生顯示 Windows `Ctrl+`／macOS `⌘`；以按鍵實際觸發 undo、redo | F04 | PASS | Windows 實機 PASS（W10、W11、W17、W23、W24；W10、W11 備註見 §9 U12）；macOS Cmd NOT RUN |
| G4-06 | `tests/gui/test_responsiveness.py::test_ui_not_blocked`：worker 睡 1.5 秒期間，10 ms 計時器的最大間隔 ≤100 ms、送出工作 ≤100 ms | F04 | PASS | Windows 實機 PASS（W25，只能排除明顯凍結） |
| G4-07 | `tests/gui/test_fonts.py::test_cjk_font_rendering`：頁面原中文字形有畫出（文字框內有深色像素）；兩個不同中文新字串的「修改後」預覽圖不同（排除空白與同一缺字框）；介面拿到的文字未改碼 | T05 | 預覽 PASS | UI 元件中文字形：Windows 實機 PASS（W01、W03、W03b）；macOS NOT RUN |
| G4-08 | `tests/integration/test_preview.py`（3 項）：全部 available fixture（排除加密、損壞）逐頁分析，帶 PREVIEW_UNRELIABLE 的恰為 ADR-0015 的 7 份；worker 層 preview_edit 前後圖不同、revision／內容指紋／applied 不變、之後同一 plan_id 可套用；其他未套用計畫失效；無效 plan_id 回 INVALID_REQUEST | 全部 available、F04 | PASS | Windows 實機 PASS（W04、W08、W13） |
| G4-09 | `test_drafts.py::test_draft_structure_validated`（14 組）、`::test_recover_failure_closes_document`、`test_transaction.py::test_plan_params_copied`、`test_crash_injection.py::test_temp_recorded_while_writing`、`::test_cleanup_recorded_removes_only_own_temps`、`::test_cleanup_recorded_malformed_registry`（第二輪核對 W1）、`tests/gui/test_startup.py`（2 項，U8）、`tests/gui/test_drafts_ui.py`（7 項：全列草稿 U9；正常關閉刪草稿 U11） | T01、F04、測試內樣本 | PASS | Windows 實機 PASS（W20、W22、W27–W31） |

G4 驗收條件：

1. **每平台至少 12 個 E2E 流程**：G4-01 有 12 項 `test_flow_*`，CI 雙平台執行通過；spec 寫「兩平台實機」：Windows 實機人工驗收 PASS（2026-11-02），macOS 實機 NOT RUN（ADR-0021 §3）。
2. **IME 組字中不提前送出**：G4-02 只驗證到 Qt 層（QInputMethodEvent）；實際輸入法（注音、倉頡、macOS 注音）的 Enter 由輸入法吃掉，offscreen 無法模擬；Windows 實機以微軟注音驗收 W16a–W16f PASS（組字中 Enter 只確認組字、不觸發預覽），倉頡、macOS 注音 NOT RUN。
3. **中文、空白、emoji 路徑**：G4-03。
4. **取消不提交**：G4-04。
5. **不可編輯物件顯示原因**：G4-05。
6. **中文字型正確顯示**：G4-07 預覽部分；UI 部分 Windows 實機 W01、W03、W03b PASS。
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

- **Windows 實機人工驗收**：2026-11-02 完成，commit `8d1f0ed`，37／37 PASS、FAIL 0、NOT RUN 0（`reports/P4/windows-acceptance.md`，結果由驗收人填入 Artifact 頁面的資料庫，Claude 讀出後逐項寫入清單）。環境：Windows 11 26H2、縮放 150%、1920×1080、微軟注音、系統管理員帳號（非一般使用者，清單要求記錄；以一般帳號執行的行為未驗）。限制：(1) 證據只有驗收人自填的結果與備註，**未提交截圖**（清單建議放 `reports/P4/evidence/windows/`，該資料夾不存在），Claude 無法獨立確認；(2) W16a–W16f 的「其他」輸入法欄填 PASS，但環境只記錄微軟注音，未記錄另一個輸入法的名稱；(3) 備註：W09「ㄅㄨ」（意義不明，照錄）；W10 焦點留在輸入欄時 Ctrl+Z 沒有被輸入欄吃掉（與 U12 描述不同，§9 U12）；W11 Ctrl+Shift+Z 沒作用（符合 U12）；W16f 有些罕用字、簡體字無法顯示（§9 U17）；(4) W26 清單預期人手來不及取消、多半標 NOT RUN，驗收人標 PASS，未記錄是看到「已取消，未提交變更」或其他情形（§9 U14）；(5) 倉頡等其他輸入法、一般使用者帳號、其他縮放比例未驗；(6) 清單要求記下的觀察有兩項只填 PASS：W24 未記錄工具列提示內容、W06 未記錄開啟 U02 後能否點選前一份文件的框。
- **macOS 實機**：NOT RUN（ADR-0021 §3、P3 U1）。
- **UI 中文字形**：offscreen 平台的字型資料庫沒有任何繁中字型（實測 `QFontDatabase.families(TraditionalChinese)` 為 0），
  介面元件的中文是否顯示正確無法自動驗證。
- **ADR-0015 的 7 份檔案**：預覽空白，只顯示 `PREVIEW_UNRELIABLE` 提示；E2E 只確認 T01 有提示。
- **E2E 的捷徑**：覆寫既有目的檔直接呼叫 `save_as`（覆寫確認對話框未測）；G4-04 與 U11 的 `test_close_window_while_busy*`、`test_close_window_delivers_finished_result` 以私有 `window._run`、`window._opened`、`service._send_raw`／`open_document` 搭配 worker `_sleep` 模擬長操作或晚到的結果，並以 `service._docs` 斷言沒有殘留文件；`test_close_window_does_not_offer_drafts` 以 `_run` 加 sleep 工作模擬「捨棄後再列出草稿」的回呼，不是實際捨棄流程，不是實際套用流程；G4-05 以 `select_target` 選取，不是點選；G4-03 繞過檔案對話框。Windows 實機已補驗：覆寫確認對話框（W19）、點選（W05、W06、W14）、原生檔案對話框選取特殊路徑（W02、W03、W17–W21）、實際捨棄後再列出其餘草稿（W30）；仍未實機補驗：G4-04 取消（W26 是否取消成功不明，U14）、U11 的關閉時正在處理中與晚到結果（清單未含）；macOS 全部 NOT RUN。
- **G4-07 字型測試**能分辨空白與同一缺字框，但不驗證畫出的字形是否對應正確的字。
- **G4-08** 的「全部 available fixture」排除加密（U02）與損壞（S01），實際 43／45 份；pending 的 16 份不在 repo。
- **§8.3 效能**：NOT RUN（P2 U5、P3 U7 延續）。大檔的預覽與 undo 重播耗時未量測。
- **盲測**：NOT RUN，P8 執行。
- **CI 偶發崩潰**：run 41017732159（commit `90dcf84`，只改 .md，程式碼與 `5d4a5df` 相同）windows-latest 的 pytest 啟動約 5 秒後以 0xC0000005（access violation）結束，macOS 通過；同一程式碼在 `5d4a5df`（run 41017277282）通過，其後各 run（含之後的程式修改）皆通過，屬偶發。日誌只有 P0 check 腳本截取的堆疊末段，看不出是哪個測試，沒有 artifact，原因未查明。P2／P3 報告記錄 Windows 匯入 pypdfium2 時 faulthandler 會印出 access violation 但不中斷，是否同一原因無法確認（§9 U15）。
  U15 調查（2026-11-02，工程師決定合併前查明）：(1) CI 改為失敗時印出完整檢查 log（commit `5d131f3`）；(2) 重跑 CI 8 次（push／pull_request 各 1 次：run 41371098105、41371103064；workflow_dispatch 6 次：41371446753～41372961561），雙平台全部 360 passed；(3) 本機 Windows 製作機全套 pytest 10 次全部 360 passed，每次都在收集階段出現同一個已被攔下的 pypdfium2 `init_lib` access violation；(4) 單獨匯入 pypdfium2 300 次全部正常結束（第一次未保存輸出，2026-11-02 重做，僅保存摘要於工作機 scratchpad `u15/import300.txt`，不進 repo；指令為以 `.venv` 的 python 執行 `python -X faulthandler -c "import pypdfium2"` 300 次並統計結束碼）；(5) 截至撰寫時（`c6a86d9` 之前），repo 的 `ci` workflow 163 次已完成 run（不含取消、不含 CodeQL 等其他 workflow，以最終 attempt 計）只有這 1 次崩潰；其他失敗都不是崩潰：P3 run 40826959745 的 macOS 測試失敗（已處理），以及 P2 run 40442075176 第一次 attempt 的 macOS 測試失敗（`gh run list` 只顯示最終 attempt，P2 報告已記錄）；(6) 崩潰發生在 pytest 啟動後 5.0 秒內（成功的 run 約 100 秒），本機收集約 2～2.7 秒（`u15/collect_time.txt`），所以落在收集階段或最前面幾項 GUI 測試，無法再細分。**結論：無法重現，原因未查明；工程師 2026-11-02 決定接受殘餘**；最可能是收集時匯入 pypdfium2（只有測試用）的初始化例外偶發未被攔下，但沒有直接證據。之後再發生時，CI 會印出完整堆疊。
  此 run 原先漏看：實作方只等修正 commit 的 CI，未檢查只改文件的 commit 的 CI（PR 獨立核對發現）。
  **第二次崩潰（2026-11-02，接受殘餘之後）**：run 41376869342（push，commit `44c41c2`，只改報告）macos-15 的 pytest 以 `Fatal Python error: Bus error` 結束（exit 138），同一 run 的 windows-latest 360 passed；同一 commit 的 pull_request run 41376874900 雙平台 360 passed，所以 PR 頁面看不出。這次有 `5d131f3` 加的完整 log：崩潰在 `tests/gui/test_drafts_ui.py::test_offer_drafts_lists_all_and_reoffers_after_discard`（第 2 個測試檔的第 2 項，`tests/gui/test_app_smoke.py` 2 項已通過），主執行緒在 `qtbot.waitUntil`（test 第 70 行）中做 Python 記憶體回收（"Garbage-collecting"）；同時 JobRunner 執行緒在 `recover_draft` → `_save_draft` → `drafts.py:61 save`（json.dump），另一個執行緒停在 `service.py:79 _WorkerProcess._read`。堆疊沒有 pypdfium2。因此：(a) 崩潰不只發生在 Windows；(b) 先前「最可能是 pypdfium2 初始化」的推測沒有支持；(c) 崩潰的測試是 U9 新增的（`b9a383e`），背景執行緒在 P3 服務層的 `recover_draft`／`_save_draft` 寫草稿、由 P4 UI（`app.py:532`）呼叫，不能排除產品碼或測試碼引起；(d) 頻率改為 2／174（`ci` workflow 截至 `44c41c2` 已完成、不含取消的 run，以最終 attempt 計）。Windows 那次（41017732159）只有堆疊末段，是否同一原因無法確認；但它發生在 pytest 啟動後 5 秒內，與 `test_drafts_ui.py` 在測試順序中的位置相符（推測，無直接證據）。本機 Windows 製作機以 `uv run python -X faulthandler -m pytest tests/gui/test_drafts_ui.py -q -p no:cacheprovider` 執行 50 次（2026-11-02 10:47～10:56），50 次結束碼皆 0，未重現（僅保存結束碼摘要於工作機 scratchpad `u15b/summary.txt`，不進 repo；通過時逐次輸出未保存）；macOS 本機未跑。原因未查明。
  此 run 也是只改報告的 commit 的 push run，與 41017732159 同樣容易漏看。
  **第二次崩潰後調查（2026-11-02，工程師決定合併前查明）**：(1) 重現：本機 Windows 以 GC 門檻 (1, 1, 1) 在同一行程重複崩潰的測試 600 次、依 CI 順序跑 `test_app_smoke.py`＋`test_drafts_ui.py` 100 次；暫時分支 `u15-macos-stress`（查完已刪除，不合併）的 workflow 在 macos-15 跑同兩檔 300 次（預設與最低 GC 門檻各 150 次，run 41385803445）、全套 pytest 86 次（run 41385803445 6 次、run 41396708110 80 次；其中 1 次卡住未跑完，見下），全部未崩潰。run 41385803445 的全套第 6 次卡住約 54 分鐘直到 job 逾時，該次未保存輸出，卡在何處不明；run 41396708110 加上 `faulthandler_timeout=120` 與每次 8 分鐘上限後 80 次未再卡住。(2) 追蹤（以不進 repo 的測試外掛記錄每個 `MainWindow` 被回收的時間與執行緒）：pytest-qt 4.5.0 只以弱參照登記 `addWidget` 的視窗，收尾時只呼叫 `close()`、`deleteLater()`（`pytestqt/qtbot.py` `_close_widgets`），延遲刪除要到之後的事件迴圈才處理；`MainWindow` 有循環參照（例如 `self._ask_open = self._dialog_open`），Python 端要到之後的 GC 才回收。修正前 `tests/gui` 的 34 個視窗全部不在自己的測試收尾時回收，其中 24 個在背景工作執行緒 `peditor-job_0` 觸發的 GC 中回收（Qt 物件應在所屬的 GUI 執行緒銷毀）；依 CI 順序時，`test_app_smoke.py::test_main_window_shows` 的視窗在 `test_offer_drafts_lists_all_and_reoffers_after_discard` 執行中被主執行緒 GC 回收，與 run 41376869342 的崩潰位置相同（這筆追蹤以 GC 門檻 (1, 1, 1) 執行，輸出未保存；第十六輪核對以 `ec06659` 的 tests 依 CI 順序、GC 門檻 0 與 1 各 2 次重跑，4 次都重現）。(3) 處理：`tests/gui/conftest.py` 新增 autouse fixture `_destroy_widgets_at_teardown`，每項測試收尾時（qtbot 關閉視窗、`make_window` 關閉服務之後）在主執行緒處理延遲刪除（`QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`）並執行 `gc.collect()`；修正後 34 個視窗都在各自測試收尾時於主執行緒回收。只改測試收尾，不改產品碼、不改測試預期，測試數不變（360）。產品的 `MainWindow` 存活到程式結束，`DraftDialog` 有父視窗，未見同樣情形（未做完整稽核）。**結論：崩潰仍未重現；「測試留下的視窗在其他測試中被 GC 回收，部分在背景執行緒銷毀」有旁證、無直接證據。修正消除了這個條件，但無法證明崩潰不再發生。** 卡住的那一次原因不明，與崩潰是否同源也不明。
  **工程師 2026-11-02 決定附條件接受殘餘**（§9 U15）；卡住另列 U16。為使之後的卡住留下證據，`pyproject.toml` 加 `faulthandler_timeout = 300`、`faulthandler_exit_on_timeout = true`（pytest 9.1.1 內建，`_pytest/faulthandler.py`）：單一測試超過 300 秒即印出所有執行緒堆疊並結束 pytest，CI 由逾時取消改為測試失敗（只限卡在單一測試的 setup、call 或 teardown 內；卡在收集、session 結束或直譯器結束時仍會逾時取消、不留堆疊；只印 Python 堆疊，不含原生堆疊），`Full check log (on failure)` 會印出完整 log。秒數依本機 `--durations`：最慢 8.93 秒（`test_100_save_cycles`），測試內等待最長 60 秒（`waitUntil`）。以 3 秒覆寫跑一個 sleep 60 秒的暫時測試（不進 repo）驗證：印出 `Timeout (0:00:03)!` 與堆疊、結束碼 1。

## 8. 安全審查

- CLAUDE.md 規定的 vuln-scan／triage 時點是 P1、P2、P3、P7，P4 沒有規定：**NOT RUN**。
- 新增的攻擊面：worker 操作 `preview_edit`（只接受 plan_id，型別錯誤回 INVALID_REQUEST）；`cid_not_in_charset` 解析字型程式（例外一律回 False）；
  本機資料目錄的 `pending-temps.json`（啟動時讀取，只刪符合本程式命名的檔案）。`PREVIEW_UNRELIABLE` 偵測使每次 `inspect_page` 都以 fontTools 解析 CID-keyed CFF，只開檔檢視就會觸發（P2 模式 A 只在規劃時），見 THREAT_MODEL T5。
- `THREAT_MODEL.md`：已更新（U5），第二輪獨立核對後再修正（§11）。§1 加 P4 段落；§3 編輯請求加 `preview_edit`、新增「暫存紀錄檔」入口；T3 殘餘改為啟動清除後的情況；T5 加 `preview_edit` 成本與 charset 偵測的字型解析；T11 加點擊判定與 preview_edit 回滾；新增 T14（`pending-temps.json` 遭竄改或洩漏資料夾路徑，low／mitigated）。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | （原始描述）Windows 實機人工驗收（IME、快捷鍵、中文 UI 字型、E2E）尚未執行；macOS 實機依 ADR-0021 NOT RUN | G4 要求「兩平台實機」，原本只有 offscreen 證據 | **Windows 已驗收**（2026-11-02，`8d1f0ed`）：37／37 PASS，限制見 §7（無截圖、另一輸入法未記名稱、系統管理員帳號）；備註衍生 U12、U14、U17 的待決事項；macOS 依 P3 U1 |
| U2 | 第一版報告時下列行為改動沒有直接測試：暫存紀錄與啟動清除（P3 U9）；PREVIEW_UNRELIABLE 恰標出 7 份；`_valid`（f001）；editable_region 副本（f006）；復原失敗關閉文件；preview_edit 的 worker 層行為 | — | **已處理**（工程師 2026-10-30 決定合併前補）：G4-08、G4-09 共 21 項，反向驗證見 §4 |
| U3 | G4-02 只在 Qt 層模擬組字；實機輸入法在組字中按 Enter 由輸入法處理，offscreen 無法驗證 | IME 證據不完整 | 實機驗收（U1）：Windows 微軟注音 W16a–W16f PASS（2026-11-02，驗收人自填）；倉頡等其他輸入法、macOS NOT RUN |
| U4 | `preview_edit` 會讓同文件其他未套用計畫失效；UI 一次只有一個計畫，目前沒有影響 | 未來多計畫 UI 須注意 | 備查 |
| U5 | `THREAT_MODEL.md` 未納入 `pending-temps.json` 與 `preview_edit` | 威脅模型與實作不一致 | **已處理**（工程師 2026-10-30 決定更新）：見 §8；文件變更，無行為改動、無新測試 |
| U7 | 組字中（preedit 進行中）按 Enter：offscreen 下 `returnPressed` 仍觸發，修正前會送出空字串規劃（獨立核對 V6 延伸）；`app.py` 原註解「組字中不觸發 returnPressed」不是 Qt 保證的行為 | 實機輸入法若不攔截 Enter，會以組字前內容規劃 | **已處理**（工程師 2026-10-30 決定合併前修）：`TextInput` 追蹤組字狀態，組字中按 Enter 或「預覽」不規劃；測試 `test_enter_during_preedit_not_planned`（修正前失敗）。實機輸入法行為：Windows 微軟注音 W16a–W16f PASS（2026-11-02），倉頡、macOS NOT RUN |
| U8 | `run()` 繞過 DocumentService 直接操作 `DraftStore`、`transaction.registry`（獨立核對 V2），啟動接線無測試 | 與 ADR-0021 §2 字面不一致 | **已處理**（工程師 2026-10-30 決定在 ADR 註明例外並補測試）：抽成 `prepare_storage()`，ADR-0021 §2 新增例外說明；`tests/gui/test_startup.py` 2 項 |
| U9 | 多份草稿時一次只詢問第一份（獨立核對 V11） | 其他草稿要到下次啟動才處理 | **已處理**（工程師 2026-10-30 決定改為全列）：`DraftDialog` 列出全部草稿、捨棄後再列出其餘；`tests/gui/test_drafts_ui.py` 2 項（修正前行為下失敗）。復原一份後其餘仍要到下次啟動才列出 |
| U10 | 多實例同時執行：啟動清除不檢查暫存檔年齡、沒有單一實例鎖；`_record` 讀改寫未加鎖（第二輪核對 W2） | 另一實例的另存失敗（原檔與目的檔不受影響）；並行時可能遺失紀錄而退回 P3 清除方式 | **列 P7**（工程師 2026-10-30 決定）；已記入 THREAT_MODEL T3、§8 |
| U11 | 按視窗 ✕ 正常關閉時 UI 不呼叫 `close_document`（`closeEvent` 只停 JobRunner），草稿不刪，下次啟動仍列出（第三輪核對，offscreen 實測） | 與 ADR-0020 §5「正常 close_document 時刪除」及 THREAT_MODEL T13「正常關閉即刪」不一致；草稿（含新文字）多留最多 7 天 | **已處理**（工程師 2026-10-30 決定修）：`closeEvent` 先取消進行中的請求、等背景執行緒結束，再 `close_document`（刪草稿）；測試 `tests/gui/test_drafts_ui.py::test_close_window_discards_draft`、`::test_close_window_while_busy`（修正前／拿掉取消時失敗，§4）；第四輪核對後補：取消重試、關閉前收下已完成結果（`::test_close_window_while_busy_between_calls`、`::test_close_window_delivers_finished_result`）；第五輪核對後補：關閉中不再跳出草稿對話框（`::test_close_window_does_not_offer_drafts`），ADR-0021 §2 註明關閉流程是「主執行緒不等待 worker」的例外；清單 W31 改為依 ADR 判定。未驗證：Windows 登出／關機時是否觸發 closeEvent（Qt session 行為，須實機） |
| U12 | 快捷鍵：「重做」只綁第一組 Ctrl+Y（`setShortcut`），Ctrl+Shift+Z 無作用；套用後焦點在「尋找文字」欄，Ctrl+Z 由輸入欄處理而非文件復原；工具列提示不顯示快捷鍵 | 使用者可能以為復原失效 | **列 P7**（工程師 2026-10-30 決定）；清單 W10、W11、W24 標已知不符。實機（2026-11-02）：W11 Ctrl+Shift+Z 無作用，與已知相符；W24 標 PASS，未記錄提示內容；W10 備註「焦點在輸入欄時沒有吃掉 Ctrl+Z」，與 U12「輸入欄會吃掉 Ctrl+Z」不符，可能是輸入欄當時沒有可復原的編輯（Qt `QLineEdit` 有自己的復原堆疊，空堆疊時是否轉交視窗快捷鍵未查證），未查明；U12 描述是否修正，**待工程師決定** |
| U13 | 開啟 0 頁文件（加密 U02）後頁面區仍顯示前一份文件與目標框 | 使用者可能點選到已關閉文件的框 | **列 P7**（工程師 2026-10-30 決定）；清單 W06 記錄。實機（2026-11-02）W06 標 PASS，未記錄開啟 U02 後能否點選前一份文件的框 |
| U15 | CI 偶發 pytest 崩潰（Windows 0xC0000005，run 41017732159；macOS Bus error，run 41376869342），原因未查明（§7） | 可能是測試環境或原生程式庫（pypdfium2／PyMuPDF／Qt）的偶發問題，也可能是產品碼觸發；未查明前無法排除 | 工程師 2026-11-02 決定合併前查明：已調查，無法重現、原因未查明（§7）；CI 已改為失敗時印完整 log。**接受殘餘**（工程師 2026-11-02 決定）：頻率約 1／163，其後 CI 全通過（41017732159 之後至 `497a86e` 前成功 20 次、取消 3 次不計，其中與 `497a86e` 程式碼相同者 16 次）；再發生時依完整堆疊另行處理。**2026-11-02 再發生**：run 41376869342（`44c41c2`）macos-15 Bus error，崩潰在 `test_drafts_ui.py::test_offer_drafts_lists_all_and_reoffers_after_discard`（主執行緒記憶體回收、背景執行緒 `recover_draft` 寫草稿），堆疊無 pypdfium2，頻率改為 2／174（§7）。接受殘餘所依據的「只有 1 次、最可能是 pypdfium2」已不成立；是否維持接受殘餘或合併前查明，**待工程師決定**。**工程師 2026-11-02 決定合併前查明（第二次崩潰後）**：壓測未重現（本機 Windows 700 次；macOS 385 次完成、1 次卡住）；追蹤發現測試留下的 `MainWindow` 在其他測試中才被 GC 回收，修正前 34 個中 24 個在背景執行緒觸發的 GC 中回收（量的是 Python 包裝物件的回收時機與執行緒）；`tests/gui/conftest.py` 改為每項測試收尾即在主執行緒銷毀（§7）。原因仍未證實；macOS 全套 pytest 另有 1 次卡住（原因不明，列 U16）。**附條件接受殘餘（工程師 2026-11-02 決定）**：修正後 CI 只要再崩潰一次即撤回接受，依完整堆疊重新調查（之後的崩潰不能再以測試留下的視窗解釋） |
| U16 | macOS 全套 pytest 卡住 1 次：run 41385803445（U15 壓測，暫時分支）的第 6 次約 54 分鐘無輸出直到 job 逾時，未保存輸出，卡在何處不明；其後 80 次（run 41396708110）未再發生；正式 `ci` workflow 未見過（§7） | 正式 CI 卡住會以 30 分鐘逾時取消，原本不留堆疊 | **已處理證據收集**（工程師 2026-11-02 決定）：`pyproject.toml` 加 `faulthandler_timeout = 300`、`faulthandler_exit_on_timeout = true`（§7），只涵蓋卡在單一測試內的情形，能否抓到 run 41385803445 那種卡住未經驗證；原因未查明，再發生時依堆疊處理 |
| U14 | G4-04 實際套用流程的取消，人工在實機來不及操作（套用約 0.15 秒） | G4-04 只有 offscreen 證據（worker 延遲模擬） | **列 P7**（工程師 2026-10-30 決定）；清單 W26 照實記錄。實機（2026-11-02）W26 標 PASS，未記錄是否看到「已取消，未提交變更」；是取消成功或來不及取消而判 PASS 不明，是否請驗收人補記，**待工程師決定** |
| U17 | Windows 實機 W16f（微軟注音選同音字）備註：有些罕用字、簡體字無法顯示（2026-11-02）。未記錄是哪些字、在輸入欄或頁面／預覽圖、顯示為方框或空白 | 可能是 UI 字型或模式 B 字型（Noto Sans TC）缺字；公文罕用字無法輸入或顯示會影響使用 | 補記哪些字與位置後判斷原因；處理方式（列 P7、合併前查明或備查）**待工程師決定** |
| U6 | P3 延續：U3（重播 30 秒逾時）、U7（§8.3 效能）、U10（影像雜湊解讀）、U11（逾時路徑無測試）、U12（服務層 undo 失敗無測試） | 同 P3 報告 | 同 P3 報告 |

## 10. 關卡結果

- CI：ci.yml 最後變更於 `5d131f3`（U15）；`c3c3524` 改 GUI 測試收尾（U15），`69cbdc4` 加 pytest faulthandler 逾時（U16），其後只改報告；`8d1f0ed`（Windows 實機驗收所用 commit）的 run 41409043376（push）、41409049958（pull_request）windows-latest 360 passed、macos-15 360 passed；`0fd7070` 的 run 41407315420（push）、41407321597（pull_request）windows-latest 360 passed、macos-15 360 passed；`07700c0` 的 run 41404337580（push）、41404342839（pull_request）windows-latest 360 passed、macos-15 360 passed；`44c41c2` 的 run 41376869342（push）macos-15 pytest 崩潰（Bus error，U15 第二次，§7）、windows-latest 360 passed，run 41376874900（pull_request）雙平台 360 passed；`497a86e` 的 run 41373728592（push）、41373734102（pull_request）windows-latest 360 passed、macos-15 360 passed；U15 重跑 8 次見 §7；程式證據 run [41029981106](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41029981106)（commit `ffcecc3`，第六輪核對 A4、A5 處理後）windows-latest 360 passed、macos-15 360 passed；run [41028316187](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41028316187)（commit `5b3f148`，U11 第五輪核對處理後）windows-latest 360 passed、macos-15 360 passed；run [41022660909](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41022660909)（commit `51c3c0d`，U11 第四輪補修後）windows-latest 359 passed、macos-15 359 passed；run [41017277282](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41017277282)（commit `5d4a5df`，U11 修正後）windows-latest 357 passed、macos-15 357 passed；run [41011809272](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41011809272)（commit `cb40fdf`，第二輪核對處理後）windows-latest 355 passed、macos-15 355 passed；run 41010683123（commit `efc3ddf`，U5，只改文件）雙平台 354 passed；run [41005065222](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41005065222)（commit `b9a383e`，U9 修正後）windows-latest 354 passed、macos-15 354 passed；run 41004289165（`77a6348`）352 passed；run 41001063910（commit `c234632`，U7 修正後）雙平台 350 passed；run 40998022034（commit `ecc067b`）雙平台 349 passed；先前 run 40994221324（commit `28d89b5`）雙平台 328 passed。
- **關卡結果：BLOCKED**。G4-01～G4-09 都有自動測試，本機與 CI 雙平台通過；Windows 實機人工驗收 2026-11-02 完成，37／37 PASS（U1，限制見 §7），尚待獨立核對；U12、U14、U17 有待工程師決定的事項；macOS 實機 NOT RUN（ADR-0021 §3）。
  U2 已補測試。
- **下一段可開始：否**。條件：Windows 實機驗收已完成並寫回本報告（2026-11-02）；尚須由未參與實作者再做一次獨立核對、工程師決定 U12、U14、U17 的待決事項，並依結果更新本節關卡結果；macOS 依 ADR-0021 §3 附條件。U15（CI 偶發崩潰）工程師曾接受殘餘（2026-11-02），其後同日在 macOS 再發生一次（run 41376869342，§7）；工程師決定合併前查明，已修正測試收尾（§7），崩潰未重現、原因未證實；工程師 2026-11-02 決定附條件接受殘餘（再崩潰即撤回）。U16（macOS 卡住 1 次）已加逾時堆疊收集，原因未查明。

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

第九輪（2026-10-30，HEAD `0ddc265`，針對第八輪 C1–C3，只改文件）：未參與實作的 Claude 子代理人在 %TEMP% 的 worktree 以量測腳本重測（Windows 製作機，非 pytest、**不是實機驗收證據**）：worker 已死時 `close_document` 共 0.458 秒，建立行程約 0.010 秒在計時外、`_exchange` 0.447 秒在計時內；另以「子行程先睡 3 秒再進 worker」反證，逾時 1 秒時於 1.009 秒逾時並收掉新 worker，確認 ADR-0021 §2 C1 新文字與程式一致。
§1、§11 的修改與 `46febae`、`0ddc265` 的 diff 一致，全 repo .md 沒有殘留過時說法（舊用詞只在已加註的歷史引文）；`ffcecc3` 之後只改 .md。文件 commit 的 CI：run 41040138927（`46febae`）、41040808503（`0ddc265`）雙平台 360 passed。結束時 worktree 已移除、工作目錄乾淨。結論「無必須修正、無建議修正」，備查：

| # | 備查 | 處理 |
| --- | --- | --- |
| D1 | 計時前除建立行程外，還有取得 `_lock`、對已死舊 worker 的 `kill()`、`send()`，實測皆毫秒級；ADR 只點名建立行程 | 備查，不改 ADR |
| D2 | worker 已死時 `close_document` 送給新 worker 的是舊 `worker_id`，錯誤被吞掉，不影響上限（屬 Y7 同一情境）；Y7 措辭未點名 Popen OSError，但語意涵蓋 | 備查 |
| D3 | §1 不列只改報告的 commit（例如 `0ddc265`），屬既有慣例 | 備查（已由第十三輪 H1、第十四輪 I1 的慣例取代） |
| D4 | ADR 修改的人工確認與 ADR 開頭未註明 10-30 增補，無法從 repo 核對 | 須工程師審查時確認 |

第十輪（2026-10-30，PR #11，HEAD `a5650cb`，針對 PR 本身）：未參與實作的 Claude 子代理人只讀核對 PR 說明、狀態、diff 範圍與 commit：29 個檔案都在 P4 範圍，沒改 `uv.lock`、`pyproject.toml`、`.github`、fixture，沒有二進位、字型、密鑰、備份檔或個人路徑；產品碼沒有新增網路模組匯入，日誌與錯誤訊息沒有新增路徑或原文；27 個 commit 都有 Co-Authored-By；PR head 的 CI（run 41041241010、41044468904）雙平台 360 passed、CodeQL 通過。結論「有出入」，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| E1（must-fix） | run 41017732159（`90dcf84`）Windows pytest 偶發崩潰 0xC0000005，報告與 PR 都沒提 | §7 揭露（實作方已查 log 確認）；§9 U15 → 2026-11-02 已調查（無法重現）、工程師接受殘餘（§7、§9，第十一輪核對）；其後 2026-11-02 在 macOS 再發生，工程師決定合併前查明、修正測試收尾並附條件接受殘餘（§9 U15，第十五輪 J4、第十六輪 K1） |
| E2（must-fix） | PR 合併前條件缺「實機結果寫回後再做獨立核對」「依結果更新 §10、macOS 附條件」 | §10 條件補上；PR 說明 checkbox 補上 |
| E3（must-fix） | PR 已是 CLEAN／MERGEABLE，轉成 ready 即可合併 | PR 維持 draft；PR 說明註明 W01–W31 完成並核對前不轉 ready |
| E4 | PR「出入均已處理或列備查」未含 A6／B4／C4／D4（待工程師確認） | PR 說明改寫；ADR-0021 開頭新增增補註記，checkbox 改為審查確認此註記 |
| E5 | PR 需知悉未列 U11 殘餘（登出／關機未驗證、關閉時 Python 端等待無上限）與 §7 NOT RUN 摘要 | PR 說明補上 |
| E6 | PR「G4-01～G4-09 都有自動測試（offscreen）」不精確，G4-08、G4-09 多為 integration 測試 | PR 說明改為「G4-01～07 為 offscreen GUI 測試」 |
| E7 | ruleset「main-protection」規則內容未展開，是否要求 review 無法核對；崩潰原因無法核對 | 備查 |

第十一輪（2026-11-02，HEAD `497a86e`，針對 U15 調查與接受殘餘）：未參與實作的 Claude 子代理人只讀核對 `5d131f3` 的 ci.yml 修改（只加 `run:` 步驟、沒有新增 action，兩平台 log 路徑一致，log 沒有主機名或使用者名，只有公開 runner 路徑）、以 GitHub 紀錄逐一核對重跑結果與 CI 歷史、比對崩潰與成功 run 的時間戳（5.0 秒、約 100.6 秒），並以 scratchpad 原始輸出佐證本機 10 次。結論「有出入」，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| F1（must-fix） | §7 與 PR 寫「重跑 CI 10 次（含 8 次 workflow_dispatch）」，實際 workflow_dispatch 6 次、共 8 次（實作方的迴圈為 6 次，回報時寫錯） | §7、PR 改為 8 次（push／PR 各 1＋dispatch 6），雙平台全部 360 passed |
| F2（must-fix） | §11 E1 處理欄仍寫「§9 U15 待工程師決定」 | 補上調查與接受殘餘的結果；新增本輪紀錄 |
| F3 | 「163 次」未說明不含取消、以最終 attempt 計；漏列 P2 run 40442075176 第一次 attempt 的 macOS 測試失敗 | §7 補註與補列（均非崩潰） |
| F4 | 「同一程式碼……皆通過」「同一程式碼其後 20 次」用詞不精確（之後有程式修改） | 改為「其後各 run（含之後的程式修改）」「其後 20 次（與 HEAD 程式碼相同者 16 次）」 |
| F5 | §1 commit 清單未列 `5d131f3` 等；§10 未列 PR head 的 CI | §1、§10 補上（run 41373728592、41373734102 雙平台 360 passed） |
| F6 | 匯入 300 次與本機收集時間沒有保存原始輸出，無法核對 | 2026-11-02 重做並保存（`u15/import300.txt`：300／300 正常；`u15/collect_time.txt`：2.0～2.7 秒）；scratchpad 不進 repo |
| F7 | `p0_macos_check.sh` 註解「log.txt (no host or user names)」字面略寬（含 runner 路徑）；失敗時印 log 的步驟尚未在真實失敗中執行過 | 備查 |

第十二輪（2026-11-02，HEAD `f9ff456`，針對第十一輪 F1–F6）：未參與實作的 Claude 子代理人只讀核對：workflow_dispatch 確為 6 次、push／pull_request 各 1 次，8 個 run 雙平台 360 passed；P2 run 40442075176 attempt 1 以 API 確認 macOS「P0 check script」步驟失敗；「20 次（16 次）」依指定方法計算正確；scratchpad 的本機輸出與報告一致；報告沒有完整個人路徑、沒有殘留過時說法（只在 §11 出入欄引用）；`f9ff456` 的 CI（run 41374443530、41374446777）雙平台 360 passed、所有檢查通過。結論「無 must-fix」，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| G1 | §10「PR head 的 run」指 `497a86e`，PR head 已是 `f9ff456` | 改為「最後一次 CI 設定變更後（`497a86e`；其後只改報告）的 run」 |
| G2 | §9 U15「其後 CI 20 次」未寫計數區間與排除的取消 run（至今已 24 次） | 改為「41017732159 之後至 `497a86e` 前成功 20 次、取消 3 次不計，其中程式碼相同者 16 次」 |
| G3 | §7 (5) 的 163 未寫截止點、未說明只計 `ci` workflow | 補「截至 `c6a86d9` 之前、只計 `ci` workflow」 |
| G4 | `import300.txt` 只有一行摘要，沒有指令與逐次輸出，且 scratchpad 不進 repo | §7 (4) 註明「僅保存摘要、不進 repo」並寫出指令 |
| G5 | §1 日期仍為 2026-10-30；P2 attempt 1「1 failed、271 passed」只能靠 P2 報告（job log 被 gh 擋下）；PR 已 CLEAN，只靠 draft 擋合併（E3） | §1 日期改為 2026-10-30～11-02；其餘備查 |

第十三輪（2026-11-02，HEAD `c70b012`，針對第十二輪 G1–G5）：未參與實作的 Claude 子代理人只讀核對 G1–G5 與 diff 一致，20／3／16（以 `src`、`tests` 比對程式碼相同）與 163（`c6a86d9` 之前建立、排除取消；以 `497a86e` 為截止則 164）和 GitHub 紀錄相符，摘要檔不在 repo；`c70b012` 的 CI（run 41374961468、41374966881）雙平台 360 passed、CodeQL 通過。結論「無 must-fix」，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| H1 | §1 commit 清單列了 `1c4c88a`（第十一輪核對處理）卻沒列同性質的 `c70b012`，與 D3 慣例不一致 | 補列；核對處理 commit 一律列入，只補 hash 或 CI 證據的報告 commit 不列 |
| H2 | §10「最後一次 CI 設定變更後（commit `497a86e`）」用詞不精確：設定變更在 `5d131f3`，`497a86e` 只改報告 | 改為「ci.yml 最後變更於 `5d131f3`，其後只改報告；`497a86e` 的 run …」 |
| H3 | 匯入 300 次的指令只寫在報告、摘要檔未保存；「程式碼相同」只比 `src`／`tests`（`5d131f3` 前 7 次 ci.yml 不同）；PR 說明的 163 未寫截止點；PR 只靠 draft 擋合併 | PR 說明的 163 已補截止點（`c6a86d9` 之前）；其餘備查 |

實機結果寫回本報告後須再做一次獨立核對（§10）；本輪處理（H1、H2）是否另做核對，待工程師決定（其後工程師決定另做，即第十四輪）。

第十四輪（2026-11-02，HEAD `b8f491b`，針對第十三輪 H1、H2 與 `b8f491b` 的更正，工程師決定另做核對）：未參與實作的 Claude 子代理人只讀核對 H1、H2 與 diff、git、CI 紀錄一致（ci.yml 最後變更於 `5d131f3`、其後只改報告；`497a86e` 的兩個 run 雙平台 360 passed）；逐一對照分支上所有 commit，12 個核對處理 commit 都在 §1、9 個只補 hash 或 CI 證據的 commit 都未列；全文搜尋「工程師」「決定」，`b8f491b` 更正後沒有再把未發生的決定寫成已決定；`b8f491b` 的 CI（run 41375934178、41375938460）雙平台 360 passed、CodeQL 通過。結論「無 must-fix」，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| I1 | H1 慣例只分兩類，`00f8a7d`（實機驗收清單初版）、`87f8e12`（U10）、`aa68068`、`a5650cb`、`b0458b9`、`b8f491b` 兩類都不屬於；§1 沒說明不是完整清單 | §1 補列 `00f8a7d`、`87f8e12`（與已列的 U5 同性質），並註明「只列實作、U 項處理與核對處理 commit，不是完整清單；只補 hash、CI 證據或核對紀錄的報告 commit 不列」；`b8f491b`（更正一句紀錄）屬後者，不列 |
| I2 | D3「不列只改報告的 commit」與 H1「核對處理 commit 一律列入」互相矛盾 | D3 處理欄註明已由 H1、I1 的慣例取代 |
| I3 | H3 仍把「PR 說明的 163 未寫截止點」列為備查，但 PR 說明已補 | H3 處理欄改寫 |
| I4 | 第十三輪紀錄「是否另做核對，待工程師決定」已過時 | 補註「其後工程師決定另做，即第十四輪」 |
| I5 | 2026-10-30 那批工程師決定（U2–U14、Z1、A4／A5／B1／C1）只能從報告判斷；PR 只靠 draft 擋合併；`6a384af` 的歷史中仍有那句錯誤陳述（`b8f491b` 已更正，不改寫歷史） | 備查；PR 合併前清單已有「工程師審查確認」 |

第十五輪（2026-11-02，HEAD `eb73c3d`，針對 `b813899`、`eb73c3d`：U15 第二次崩潰紀錄）：未參與實作的 Claude 子代理人只讀核對 run 41376869342 的完整 log 與報告一致（macos-15 pytest 結束碼 138、Bus error 在 `test_drafts_ui.py` 第 2 項、主執行緒 "Garbage-collecting" 於第 70 行 `qtbot.waitUntil`、背景執行緒 `recover_draft` → `_save_draft` → `drafts.py:61`、另一執行緒在 `service.py:79 _read`、堆疊無 pypdfium2；windows-latest 360 passed）；run 41376874900 雙平台 360 passed；2／174 重算相符（`ci` workflow 至 run 41376874900 共 182 次，扣除取消 8 次為 174 次，失敗 3 次中 40826959745 為測試失敗、非崩潰）；本機 50 次摘要不在 repo，未寫成 CI 或實機證據；「待工程師決定」在 §9、§10 一致；§1 列 `b813899`、未列 `eb73c3d`，符合 I1 慣例。`eb73c3d` 的 CI（run 41381556766、41381562080）雙平台 360 passed。結論「無 must-fix」，工程師決定全部處理（2026-11-02），處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| J1 | §7 本機 50 次寫「全部 7 passed」，但摘要只保存結束碼（通過時逐次 log 已刪）；寫的指令與實際（`uv run python -X faulthandler -m pytest tests/gui/test_drafts_ui.py -q -p no:cacheprovider`）不同 | 改為「50 次結束碼皆 0（僅保存結束碼摘要）」並寫出實際指令 |
| J2 | §7 (c)「草稿／關閉流程（U9、U11）測試」不精確：崩潰測試是 U9 加的（`b9a383e`），背景執行緒的 `recover_draft`／`_save_draft` 是 P3 服務層程式，由 P4 `app.py:532` 呼叫 | §7 (c) 依此改寫 |
| J3 | PR #11 說明仍寫「163 次只 1 次崩潰、工程師接受殘餘」，U15 勾選項仍為已勾，與報告「2／174、待工程師決定」矛盾（不在本輪 diff 範圍，合併前須改） | PR 說明補第二次崩潰與 2／174，U15 勾選改回未勾、註明待工程師決定 |
| J4 | §9 U15 項目欄仍只寫 Windows 0xC0000005；§11 E1 處理欄仍為「工程師接受殘餘」，未註明其後再發生 | U15 項目欄補 macOS run；E1 處理欄補「其後再發生，待工程師決定」 |
| J5 | 核對時 push run 41381556766 的 windows-latest 尚未跑完 | 已確認：其後雙平台 360 passed（見本段首） |

第十六輪（2026-11-02，HEAD `0fd7070`，針對 `c3c3524`、`69cbdc4`：U15 測試收尾修正、附條件接受殘餘、U16 逾時設定）：未參與實作的 Claude 子代理人只讀核對：收尾順序與鎖定版本原始碼一致（pytest-qt 4.5.0 `plugin.py` `pytest_runtest_teardown` 在 fixture 收尾前呼叫 `_close_widgets`，`_add_widget` 只存弱參照，`_close_widgets` 只 `close()`／`deleteLater()`；pytest 9.1.1 autouse 最先建立、最後收尾），另實測 `processEvents()` 不處理 DeferredDelete、`sendPostedEvents(None, DeferredDelete)` 會；PySide6 6.11.2 stub 支援該呼叫；tests/ 只新增 fixture，360 tests collected；`faulthandler_timeout`／`faulthandler_exit_on_timeout` 存在且行為相符，檢查腳本遇 pytest 非 0 會使 step 失敗、`if: failure()` 會執行；run 41385803445、41396708110 的次數與卡住時間相符，暫時分支已刪除；本機 700 次與修正前後 trace（34／0／24、34／34）和工作機 scratchpad 檔案相符，並在 HEAD 重跑 tests/gui 得 34／34；`07700c0` 的 CI（run 41404337580、41404342839）與 `0fd7070` 的 CI（run 41407315420、41407321597）雙平台 360 passed；報告與 PR 的工程師決定都對得上；§1 列 `c3c3524`、`69cbdc4`，未列只補 hash 的 `07700c0`、`0fd7070`；產品碼 `src/peditor/ui/` 只見 `JobRunner()` 無父物件，生命期隨 MainWindow。結論「有出入」（1 項 must-fix），工程師決定 K1–K5、K7、K8 處理，K6、K9 備查（2026-11-02），處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| K1（must-fix） | §11 E1 處理欄仍寫「其後 2026-11-02 在 macOS 再發生，是否維持接受殘餘待工程師決定」，與 §9 U15、§10、PR 說明的「附條件接受殘餘」矛盾（比照第十二輪 F2、第十五輪 J4） | E1 處理欄改為「工程師決定合併前查明、修正測試收尾並附條件接受殘餘」 |
| K2 | PR 說明「需工程師知悉」的 U16 項目與 U4、U6 黏在同一行，原「- U3（實機輸入法組字中 Enter）」一行遺失（實作方更新 PR 說明時的替換錯誤） | PR 說明恢復「- U3（實機輸入法組字中 Enter）、U4…、U6…」一行 |
| K3 | §9 U15 與 PR 寫「24 個在背景執行緒銷毀」，但追蹤量的是 Python 包裝物件的 `weakref.finalize` 觸發時機與執行緒，不是 C++ 物件解構的執行緒；§7「在 `peditor-job_0` 觸發的 GC 中回收」較精確 | §9 U15 與 PR 改為「在背景執行緒觸發的 GC 中回收」並註明量的是 Python 包裝物件 |
| K4 | §7「依 CI 順序時 `test_main_window_shows` 的視窗在 `test_offer_drafts…` 執行中被主執行緒 GC 回收」，保存的 trace 沒有這筆（那次追蹤未保存）；核對者以 `ec06659` 的 tests 依 CI 順序重跑 4 次，4 次都重現 | §7 註明該筆追蹤未保存及本輪重跑結果 |
| K5（部分推論） | faulthandler 計時只包住單一測試（`pytest_runtest_protocol`）；卡在收集、session 結束或直譯器結束時仍會逾時取消、不留堆疊，且只印 Python 堆疊；能否抓到 run 41385803445 那種卡住未經驗證 | §7 與 U16 補適用範圍 |
| K6 | 追蹤外掛的 phase 在 teardown 後要到下一個測試的 call 才更新，`teardown:X` 分不出 X 的收尾或下一個測試的 setup；修正後回收發生在 fixture 內的 `gc.collect()`，結論可信 | 備查 |
| K7 | §9 U15 處理欄兩次出現「工程師 2026-11-02 決定合併前查明」（`497a86e` 前與第二次崩潰後），中間夾「待工程師決定」，容易混淆 | 第二次加註「（第二次崩潰後）」 |
| K8 | macOS「386 次」含 run 41385803445 full 卡住的第 6 次，實際完成 385 次、卡住 1 次 | §7 註明 1 次卡住未跑完；§9 與 PR 改為「385 次完成、1 次卡住」 |
| K9 | 產品碼抽查只見 `JobRunner()`（`app.py:226`）無父物件，生命期隨 MainWindow；報告已註明未做完整稽核 | 備查 |

第十七輪（2026-11-02，HEAD `0fe585f`，針對 `e9cae93`：Windows 實機驗收結果寫回，以及 PR #11 說明更新）：未參與實作的 Claude 子代理人只讀核對，以驗收頁面資料庫讀出的原始資料為基準：清單只改結果、環境、統計欄（word-diff），37 項全 PASS、無漏項或多寫，四則備註（W09、W10、W11、W16f）忠實；環境逐項相符；§3 實機欄的 W 編號與清單「附：對照」逐條一致；§1 列 `e9cae93`、未列只補 hash 的 `0fe585f`；§10 的 run 41409043376、41409049958 headSha 為 `8d1f0ed`，log 雙平台 360 passed；PR head `0fe585f` 的 run 41426503958、41426513645 為 success（未逐一看 log 計數）；U12、U14、U17 皆寫待工程師決定，未把未做的決定寫成已決定。結論「有出入」（無 must-fix），工程師決定 L1–L8 全部處理（2026-11-02），處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| L1 | §3 G4-04 實機欄以「Windows 實機 PASS」開頭，但同格與 U14 都說不出是否實際取消成功，說得比證據強 | §3 G4-04 實機欄改為「驗收人自填 PASS，是否實際取消成功不明」 |
| L2 | §7「E2E 的捷徑」仍寫覆寫確認對話框、點選、檔案對話框「都須實機補驗」，未反映 W19、W14、W02／W03／W17–W21 已實機驗收；PR 說明「E2E 有測試捷徑須實機補驗」同 | §7「E2E 的捷徑」改列 Windows 實機已補驗（W19、W05／W06／W14、W02／W03／W17–W21、W30）與仍未補驗（G4-04 取消、U11 關閉時處理中與晚到結果、macOS）；PR 說明同步 |
| L3 | §9 U3 處理欄仍為「實機驗收（U1）」、U7 仍寫「實機輸入法行為仍待 U1 驗收」，與 §3 第 2 點、PR 說明的 W16a–f 結果不一致 | U3、U7 處理欄補 W16a–f 結果與未驗範圍（倉頡、macOS） |
| L4 | §9 U1 問題欄仍寫「尚未執行」「目前只有 offscreen 證據」 | U1 問題欄加註「（原始描述）」 |
| L5 | W24（提示內容）、W06（能否點前一份文件的框）清單要求記下的觀察，原始資料只有 PASS；U12 寫「W24 標 PASS，與已知相符」屬推論，U13、§7 未註明 W06 未記錄 | U12 改為「W24 標 PASS，未記錄提示內容」；U13 與 §7 補「W06 未記錄框是否可點」 |
| L6 | §2「依清單 §1 以 `uv sync --locked --all-groups` 安裝，套件同上」為依步驟推定，驗收人未記錄 | §2 改為「依清單 §1 步驟（驗收人未另記套件版本）」 |
| L7 | 清單統計「其他觀察」只寫 W10、W16f，漏 W09、W11 | 清單統計補 W09、W11 |
| L8 | 清單結果欄混入 Claude 的判讀（W09「意義不明」、W16「輸入法名稱未記錄」、W10／W11 與 U12 的比較），與驗收人原文混在一起 | 清單結果欄只留驗收人原文，判讀留在報告（§7、U12） |
