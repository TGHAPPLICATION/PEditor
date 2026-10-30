# P4 關卡報告：桌面文字編輯流程

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段 G4 測試都在 offscreen 平台執行（本機 Windows 與 CI），**不是實機證據**。

## 1. 階段／commit／日期

- 階段：P4　分支：`p4-desktop-ui`　commit：`28d89b5`（實作與 G4 測試）、`ecc067b`（U2 補測試，G4-08、G4-09）、本報告核對修正 commit　日期：2026-10-30
- 撰寫：Claude Code；審查：待工程師；獨立核對：2026-10-30 完成，結論「有出入」，處理見 §11
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
「本機」＝Windows 製作機 offscreen；「CI」＝run 40998022034（commit `ecc067b`）雙平台 349 passed，涵蓋 G4-01～G4-09（§4）。實機欄另列。

| 需求 ID | test ID | fixture | 本機／CI | 實機 |
| --- | --- | --- | --- | --- |
| G4-01 | `tests/gui/test_e2e.py::test_flow_*`（12 項：開檔與縮圖、點選、預覽前後對照不提交、套用、undo／redo、另存重開、覆寫既有目的檔、模式 B 字型替換、溢出說明、尋找文字跨段落選取、預覽不可靠提示、崩潰後復原草稿），另 `::test_source_never_modified` | T01、F02、F04 | PASS | Windows NOT RUN；macOS NOT RUN |
| G4-02 | `tests/gui/test_ime.py::test_preedit_not_committed`：以 QInputMethodEvent 模擬注音組字，組字中文字不進入內容、不規劃；確認字不規劃；Enter 後只以已確認的「測試局」規劃一次。**未涵蓋組字中按 Enter**（§9 U7） | T01 | PASS | Windows NOT RUN；macOS NOT RUN |
| G4-03 | `tests/gui/test_paths.py::test_unicode_paths`（3 組：中文目錄＋中文檔名、空白、emoji）：開啟、編輯、另存到同類路徑、重開見新文字 | T01 | PASS | Windows NOT RUN；macOS NOT RUN（測試以 `ask_save`／`open_path` 繞過原生檔案對話框，對話框選取這類路徑須實機） |
| G4-04 | `test_e2e.py::test_cancel_does_not_commit`：長操作中取消回 CANCELLED，revision 與 history 皆為 0，worker 重啟後頁面為原文 | F04 | PASS | — |
| G4-05 | `test_e2e.py::test_reason_shown_for_uneditable`：不可編輯目標顯示「無法編輯：<理由>」且不能預覽；U01 顯示無文字層 | F05、U01 | PASS | — |
| G4-06 | `tests/gui/test_shortcuts.py::test_platform_shortcuts`：開啟／另存／復原／重做為 Qt 標準鍵、修飾鍵為 ControlModifier（Qt 在 macOS 對應 Cmd）、原生顯示 Windows `Ctrl+`／macOS `⌘`；以按鍵實際觸發 undo、redo | F04 | PASS | Windows NOT RUN；macOS Cmd NOT RUN |
| G4-06 | `tests/gui/test_responsiveness.py::test_ui_not_blocked`：worker 睡 1.5 秒期間，10 ms 計時器的最大間隔 ≤100 ms、送出工作 ≤100 ms | F04 | PASS | — |
| G4-07 | `tests/gui/test_fonts.py::test_cjk_font_rendering`：頁面原中文字形有畫出（文字框內有深色像素）；兩個不同中文新字串的「修改後」預覽圖不同（排除空白與同一缺字框）；介面拿到的文字未改碼 | T05 | 預覽 PASS | UI 元件中文字形 NOT RUN（offscreen 沒有系統字型，見 §7） |
| G4-08 | `tests/integration/test_preview.py`（3 項）：全部 available fixture（排除加密、損壞）逐頁分析，帶 PREVIEW_UNRELIABLE 的恰為 ADR-0015 的 7 份；worker 層 preview_edit 前後圖不同、revision／內容指紋／applied 不變、之後同一 plan_id 可套用；其他未套用計畫失效；無效 plan_id 回 INVALID_REQUEST | 全部 available、F04 | PASS | — |
| G4-09 | `test_drafts.py::test_draft_structure_validated`（14 組）、`::test_recover_failure_closes_document`、`test_transaction.py::test_plan_params_copied`、`test_crash_injection.py::test_temp_recorded_while_writing`、`::test_cleanup_recorded_removes_only_own_temps` | T01、F04、測試內樣本 | PASS | — |

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
uv run pytest -q                                        → exit 0，349 passed（Windows 製作機 offscreen，2026-10-30，U2 補測試後）
```

- P4 新增 43 項測試。`tests/gui/` 22 項：`test_e2e.py` 15 項、`test_paths.py` 3 項（參數化）、`test_ime.py`、`test_shortcuts.py`、`test_responsiveness.py`、`test_fonts.py` 各 1 項。
  U2 補測試 21 項（G4-08、G4-09）：`test_preview.py` 3 項、`test_drafts.py` 15 項（結構驗證 14 組＋復原失敗）、`test_crash_injection.py` 2 項、`test_transaction.py` 1 項；
  既有檔案只在末尾新增測試（`test_crash_injection.py` 另加 `import json`）。P3 既有 306 項未修改、全數通過。
- U2 補測試的反向驗證（暫時把修正改回舊行為後執行，再以 `git checkout` 還原）：拿掉 `_valid`→結構驗證 12／14 組失敗（另 2 組是 saved_at 的 NaN 與未來時間，由 `_expired` 負責，未改動）；
  editable_region 不存副本→`test_plan_params_copied` 失敗；復原只捕 ServiceError→`test_recover_failure_closes_document` 失敗；
  不寫暫存紀錄→`test_temp_recorded_while_writing` 失敗；清除時不檢查命名→`test_cleanup_recorded_removes_only_own_temps` 失敗；preview_edit 不回滾→`test_preview_edit_does_not_commit` 失敗。`tests/gui/conftest.py` 的 `make_window` fixture 與 `test_e2e.py` 同在 `28d89b5` 新增。
- CI：run [40994221324](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40994221324)（commit `28d89b5`，不含 G4-08、G4-09）windows-latest 328 passed、macos-15 328 passed；
  run [40998022034](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40998022034)（commit `ecc067b`）windows-latest 349 passed、macos-15 349 passed。
  同分支的 run 40994200432 是推送時 commit 尚未建立所觸發，內容為 P3 合併點 `0ecf673`，不是 P4 證據。
- 實作時發現並修正：`drafts.py` 的 `_valid()`（P3 triage f001）插在 `DraftStore` 類別中間，使 `_remove_if_old`、`_file` 變成 `_valid` 內的巢狀函式；
  修正前 5 項失敗（`test_drafts.py` 4 項、`test_flow_recover_draft_after_crash`）。
- `test_ui_not_blocked` 的反向驗證（臨時檔，未入庫）：`JobRunner.submit` 改為同步執行時，失敗點是 `window.busy` 斷言，不是計時斷言（獨立核對 V3）；另在睡眠工作期間於主執行緒插入 250 ms 工作，計時斷言失敗（最大間隔 260 ms > 100 ms），確認計時量測有效。量測的是 worker `_sleep` 期間的事件迴圈；主執行緒自身的工作（`_previewed` 解碼 PNG、`load_page` 顯示頁面）耗時未量測。
- preview_edit 不回滾的反向驗證，獨立核對重做時的失敗點是重新規劃時的 REVISION_CONFLICT 例外（不是 revision／指紋斷言），另有 2 項測試同時失敗；結論相同。
- `test_fonts.py`：traceability 預登記 T01，第一版改用 F02，兩者都在 ADR-0015 的 7 份 MuPDF 空白檔內（F02 頁面文字區域渲染全白，測試失敗），改用 T05（不在例外清單）。

## 5. 真修改證據

本段沒有新增編輯能力，編輯證據沿用 P2（`reports/P2/evidence/`）。P4 的 UI 經 DocumentService 呼叫既有 plan／apply／undo／redo／export，
E2E 測試確認：套用後頁面目標文字更新、另存檔以 PyMuPDF 擷取到新文字、重開後目標為新文字；原檔 SHA-256 不變（`test_source_never_modified`）。

新增的 `preview_edit`（ADR-0021 §2）：在工作文件上套用計畫、渲染改動頁前後圖、以開啟自的位元組回滾，再以同一參數重新規劃並沿用 plan_id。
E2E 確認預覽後 UI 的 revision 仍為 0、前後圖不同、之後可正常套用。

## 6. 資料完整性與資源／出站紀錄

- **UI 不碰 PDF**：`src/peditor/ui/` 不匯入 PyMuPDF／pikepdf，G1-01 測試持續通過。但不是「只用 DocumentService」：`app.py:38` 匯入 `core.geometry`（點擊判定座標換算）；`app.py:518-526` 的 `run()` 直接建立 `DraftStore`、設定 `transaction.registry` 並呼叫 `transaction.cleanup_recorded()`，繞過 DocumentService，與 ADR-0021 §2 的字面不一致；這段啟動接線沒有測試（§9 U8）。
- **預覽不提交**：`preview_edit` 回滾到套用前的位元組與 applied 清單，revision 不變；副作用是同文件其他未套用計畫會失效（ADR-0021 後果）。
- **暫存檔清除（P3 U9）**：交易建立暫存檔時記錄到本機資料目錄的 `pending-temps.json`，完成或已刪除即移除紀錄；
  UI 啟動時刪除紀錄中符合 `.~peditor-*.tmp.pdf` 命名的檔案。紀錄失敗不影響另存（G4-09）。
- **復原草稿**：UI 啟用；啟動時取得未逾期草稿清單，但對話框一次只詢問第一份（`app.py:493-500`），其他草稿要到下次啟動才詢問（§9 U9）；對話框只顯示檔名、不含完整路徑。草稿結構驗證（f001）：draft_id、path、sha256、log、position、
  每筆 params 與 base_revision 型別不符即視為損壞並刪除；saved_at 非有限數或晚於現在 60 秒以上視為無效。
  復原時任何例外都關閉開啟一半的文件（`except BaseException`）。
- **參數副本（P3 f006）**：`plan_text_edit` 的 editable_region 存副本。
- **錯誤訊息**：UI 只顯示理由碼對應的繁中說明（`ui/messages.py`），不含路徑與原文；未預期例外統一顯示 WORKER_FAILED。
- **出站**：新增模組未匯入網路模組（`test_offline_guard` 通過）。實機出站監測於 P7。
- **資源**：預覽每次約為一次 apply 加一次重新規劃；頁面 100 DPI、縮圖 24 DPI、縮圖最多 200 頁。效能未量測（§7）。

## 7. 限制、阻擋、未測項目

- **Windows 實機人工驗收**：NOT RUN。IME（注音／倉頡實機輸入）、快捷鍵實按、中文 UI 字型、12 個 E2E 流程的人工操作皆未做。
- **macOS 實機**：NOT RUN（ADR-0021 §3、P3 U1）。
- **UI 中文字形**：offscreen 平台的字型資料庫沒有任何繁中字型（實測 `QFontDatabase.families(TraditionalChinese)` 為 0），
  介面元件的中文是否顯示正確無法自動驗證。
- **ADR-0015 的 7 份檔案**：預覽空白，只顯示 `PREVIEW_UNRELIABLE` 提示；E2E 只確認 T01 有提示。
- **E2E 的捷徑**：覆寫既有目的檔直接呼叫 `save_as`（覆寫確認對話框未測）；G4-04 以私有 `window._run` 搭配 worker `_sleep` 模擬長操作，不是實際套用流程；G4-05 以 `select_target` 選取，不是點選；G4-03 繞過檔案對話框。這些都須實機補驗。
- **G4-07 字型測試**能分辨空白與同一缺字框，但不驗證畫出的字形是否對應正確的字。
- **G4-08** 的「全部 available fixture」排除加密（U02）與損壞（S01），實際 43／45 份；pending 的 16 份不在 repo。
- **§8.3 效能**：NOT RUN（P2 U5、P3 U7 延續）。大檔的預覽與 undo 重播耗時未量測。
- **盲測**：NOT RUN，P8 執行。

## 8. 安全審查

- CLAUDE.md 規定的 vuln-scan／triage 時點是 P1、P2、P3、P7，P4 沒有規定：**NOT RUN**。
- 新增的攻擊面：worker 操作 `preview_edit`（只接受 plan_id，型別錯誤回 INVALID_REQUEST）；`cid_not_in_charset` 解析字型程式（例外一律回 False）；
  本機資料目錄的 `pending-temps.json`（啟動時讀取，只刪符合本程式命名的檔案）。
- `THREAT_MODEL.md`：**未更新**。新增的暫存紀錄檔與 preview_edit 是否需列入，見 §9 U5。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | Windows 實機人工驗收（IME、快捷鍵、中文 UI 字型、E2E）尚未執行；macOS 實機依 ADR-0021 NOT RUN | G4 要求「兩平台實機」，目前只有 offscreen 證據 | 工程師安排 Windows 實機驗收；macOS 依 P3 U1 |
| U2 | 第一版報告時下列行為改動沒有直接測試：暫存紀錄與啟動清除（P3 U9）；PREVIEW_UNRELIABLE 恰標出 7 份；`_valid`（f001）；editable_region 副本（f006）；復原失敗關閉文件；preview_edit 的 worker 層行為 | — | **已處理**（工程師 2026-10-30 決定合併前補）：G4-08、G4-09 共 21 項，反向驗證見 §4 |
| U3 | G4-02 只在 Qt 層模擬組字；實機輸入法在組字中按 Enter 由輸入法處理，offscreen 無法驗證 | IME 證據不完整 | 實機驗收（U1） |
| U4 | `preview_edit` 會讓同文件其他未套用計畫失效；UI 一次只有一個計畫，目前沒有影響 | 未來多計畫 UI 須注意 | 備查 |
| U5 | `THREAT_MODEL.md` 未納入 `pending-temps.json` 與 `preview_edit` | 威脅模型與實作不一致 | 工程師決定是否在 P4 合併前更新 |
| U7 | 組字中（preedit 進行中）按 Enter：offscreen 以 QInputMethodEvent 模擬後按 Enter，`returnPressed` 仍觸發，送出空字串規劃（獨立核對 V6 延伸、臨時測試，未入庫）。`app.py:374` 註解「組字中不觸發 returnPressed」不是 Qt 保證的行為，程式沒有自己的防護；實機輸入法通常先吃掉 Enter，但未驗證 | 實機上若輸入法不攔截 Enter，會以組字前的內容（可能是空字串）規劃 | 工程師決定：合併前在 UI 加防護（例如追蹤 preedit 狀態，組字中不規劃）並補測試，或待實機驗收確認 |
| U8 | `run()` 繞過 DocumentService 直接操作 `DraftStore`、`transaction.registry`（獨立核對 V2），啟動接線無測試 | 與 ADR-0021 §2 字面不一致 | 工程師決定：收進 DocumentService，或在 ADR-0021 註明例外並補啟動接線測試 |
| U9 | 多份草稿時一次只詢問第一份（獨立核對 V11） | 其他草稿要到下次啟動才處理；逾期前未處理即刪除 | 工程師決定是否改為列出全部 |
| U6 | P3 延續：U3（重播 30 秒逾時）、U7（§8.3 效能）、U10（影像雜湊解讀）、U11（逾時路徑無測試）、U12（服務層 undo 失敗無測試） | 同 P3 報告 | 同 P3 報告 |

## 10. 關卡結果

- CI：run [40998022034](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40998022034)（commit `ecc067b`）windows-latest 349 passed、macos-15 349 passed；先前 run 40994221324（commit `28d89b5`）雙平台 328 passed。
- **關卡結果：BLOCKED**。G4-01～G4-09 都有自動測試，本機與 CI 雙平台通過；但 G4 要求兩平台實機，Windows 實機人工驗收尚未執行（U1），
  U2 已補測試。
- **下一段可開始：否**。條件：Windows 實機驗收完成（含 G4-03 檔案對話框與 U7 組字中 Enter）；工程師決定 U7、U8。macOS 依 ADR-0021 §3 附條件。

## 11. 獨立核對紀錄

第一輪（2026-10-30，HEAD `ecc067b`）：未參與實作的 Claude 子代理人重跑 ruff（通過）與 pytest（349 passed）；以 `git diff 0ecf673 HEAD -- tests/` 確認既有測試沒有刪除或改預期；
核對 CI run 40994221324、40998022034、40994200432 的 commit 與測試數；核對 fixture hash、套件版本、offscreen 繁中字型數；
重做 4 項反向驗證（preview_edit 不回滾、editable_region 不存副本、拿掉 `_valid`、JobRunner 改同步），結束時工作目錄乾淨。結論「有出入」，無 must-fix，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| V1（should-fix） | 報告引用的 CI run 40994221324 是 `28d89b5`，不含 G4-08、G4-09 的 21 項 | §1、§3、§4、§10 與 traceability 改引 run 40998022034（`ecc067b`，雙平台 349 passed） |
| V2（should-fix） | §6「UI 只匯入 DocumentService 與 Qt」不準確；`run()` 繞過 DocumentService，啟動接線無測試 | §6 改寫；§9 U8 |
| V3（should-fix） | JobRunner 同步化的反向驗證失敗在 busy 斷言，未證明計時斷言有效；主執行緒工作未量測 | 另做反向驗證（主執行緒插入 250 ms，計時斷言失敗）；§4 註明 |
| V4（should-fix） | G4-03 實機「不需」是自行判斷，檔案對話框未驗證 | 改為 Windows／macOS NOT RUN，§7 註明 |
| V5 | conftest 不是「移動」 | §4 改寫 |
| V6 | IME 測試未涵蓋組字中按 Enter | 以臨時測試驗證，發現 offscreen 下仍會以空字串規劃；§3、§9 U7 |
| V7 | E2E 有捷徑（save_as、_run、select_target） | §7 註明 |
| V8 | preview_edit 反向驗證的失敗型態 | §4 註明 |
| V9 | traceability 未說明 G4-04／G4-06 fixture 由 T01 改 F04、G4-08 排除 2 份 | traceability 補註；§7 註明 43／45 份 |
| V10 | macOS CI 的 Python 是 3.13.15 | §2 改寫 |
| V11 | 多份草稿一次只問一份 | §6 改寫；§9 U9 |
