# P3 關卡報告：儲存交易、撤銷與復原

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：P3　分支：`p3-transaction`　commit：`e977f1c`（實作）、`b59be8b`（macOS CI 測試修正）、`6a09672`（安全掃描、f015 修補、威脅模型）　日期：2026-10-29
- 撰寫：Claude Code；審查：待工程師；獨立核對：待執行（§11）
- 輸入：spec v1.1 P3／G3／§7／§8.1／§8.3、ADR-0001～0020、manifest、P2 報告 §9 延續項目、`docs/traceability.md` 預登記的 G3-01～G3-08
- S2 工程師決定（2026-10-28，ADR-0020）：undo／redo 以 command log 重播；可覆寫既有目的檔、不可覆寫原檔；復原草稿保留 7 天；
  U4 只修 f003、f017。2026-10-29：setuptools Dependabot 警示 #10 延到 P7。

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；pypdfium2 5.13.0（只在測試）；fontTools 4.66.0；Pillow 13.0.0；PySide6-Essentials 6.11.2；字型同 P2 |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest x64 | GitHub 標準 runner | Python 3.13.16；套件同上（`uv.lock`） |
| CI macos | macos-15 arm64 | GitHub 標準 runner | Python 3.13.15；套件同上 |

相依沒有變更（`uv.lock` 未改）。

## 3. 需求 → test ID → fixture／hash → 結果

fixture hash（前 12 碼）：T01 `65a4ebca20fe`、F04 `6dda72bbbb80`；其餘為測試內以 pikepdf 產生的 Helvetica 樣本。
環境皆為「本機 Windows、CI 雙平台」。CI 證據見 §4。

| 需求 ID | test ID | fixture | 結果 |
| --- | --- | --- | --- |
| G3-01 | `tests/integration/test_transaction.py::test_50_undo_redo_equivalent`、`::test_replay_failure_restores_state`、`::test_service_undo_redo_and_truncation`、`::test_worker_restart_replays_log` | 測試內樣本、T01 | PASS：50 次操作（51 個不同狀態）逐步撤銷到原檔、再逐步重做，每步內容指紋（/ID 固定後的完整重寫 SHA-256）都與當時相同；重播失敗回到重播前狀態；服務層 undo／redo、截斷重做、worker 重啟後重播 |
| G3-02 | `test_transaction.py::test_reopen_after_save` | T01 | PASS：另存檔 SHA-256 與回報相同；重開可找到新文字；PDFium 擷取的新文字起點與計畫基線起點差 ≤0.5 pt；舊文字出現次數少一次；原檔 hash 不變 |
| G3-03 | `tests/integration/test_crash_injection.py::test_interrupt_each_stage`（write／verify／rename 三階段）、`::test_exception_at_stage_cleans_up`、`::test_worker_crash_during_export_preserves_destination`、`::test_stale_temp_removed_on_next_save`、`::test_stale_temp_threshold` | T01 | PASS：子行程在各階段前 `os._exit` 中止，原檔 hash 與既有目的檔內容不變；同行程例外與 worker 中途結束時刪除暫存檔；只刪超過 10 分鐘的暫存檔。三個中斷點的實際位置（`transaction.commit`）：write＝交給 worker 之前（暫存檔尚未建立）、verify＝worker 已完成結構／文字／視覺驗證並寫入、fsync、讀回之後，主行程比對 hash 之前、rename＝`os.replace` 之前。依 ADR-0020 §3，結構／文字／視覺驗證在 worker 寫暫存檔前對記憶體內容執行，寫入後以讀回比對確保磁碟內容即驗證過的內容 |
| G3-04 | `test_transaction.py::test_100_save_cycles` | T01 | PASS：以上一次輸出為來源連續 100 次編輯另存（兩檔輪替覆寫），每次驗證通過、SHA-256 相符；最後兩份輸出分別含原文與新文字、頁數 1、不需修復 |
| G3-05 | `test_transaction.py::test_external_modification_detected`、`::test_destination_rules`、`test_crash_injection.py::test_temp_hash_mismatch_rejected` | T01 | PASS：取得 token 後目的檔被改、開啟後原檔被改、worker 重啟時原檔已變，皆回 REVISION_CONFLICT 且不寫出；目的檔為原檔 INVALID_REQUEST；預設不覆寫 SAVE_FAILED；暫存檔 hash 不符 SAVE_FAILED |
| G3-06 | `test_crash_injection.py::test_disk_full_preserves_destination`、`test_transaction.py::test_failure_no_partial_output` | T01 | PASS（以模擬 ENOSPC 驗證；真實磁碟填滿 NOT RUN，§7） |
| G3-07 | `tests/integration/test_drafts.py::test_draft_opt_in_and_expiry`、`::test_draft_rejected_when_source_changed`、`::test_draft_expires_after_7_days`、`::test_draft_store_ignores_bad_ids_and_files` | T01 | PASS：直接開原檔不套用草稿，使用者選擇才復原；原檔已變拒絕復原、草稿保留；7 天逾期刪除；撤銷到無編輯或正常關閉即刪除；POSIX 權限 0600（Windows 不檢查權限位元） |
| G3-08 | `test_transaction.py::test_failure_no_partial_output`、`::test_product_checks_detect_problems` | T01、F04 | PASS：套用失敗後 revision、內容指紋、target_id 都不變（f003、R3-1）；驗證失敗與寫入失敗不留下檔案（f017）；產品端視覺驗證抓到可改動區域外的改動、文字驗證抓到缺少的新文字 |
| G3-09 | `tests/security/test_p3_scan_regressions.py`（3 項） | 測試內樣本 | PASS（P3 安全掃描 f015 回歸，§8） |

G3 各驗收條件：

1. **50 操作撤銷重做結果等價**：G3-01。等價以內容指紋判定（/ID 每次存檔不同，見 §9 U5）。
2. **儲存重開後目標正確**：G3-02。
3. **在寫入、驗證、rename 前注入中斷，原檔／既有目的檔完整**：G3-03，以子行程實際中止整個主行程。
4. **100 次另存循環無資料毀損**：G3-04。
5. **損壞與外部修改回傳明確錯誤**：G3-05（REVISION_CONFLICT、SAVE_FAILED、INVALID_REQUEST）。
6. **P3 其他要求**：預設另存、原檔唯讀（G3-05）；完整重寫不增量（沿用 G2-08）；空間不足不破壞既有目的檔（G3-06）；
   復原草稿由使用者選擇開啟、有保留期限（G3-07）；失敗不更新 revision、不落地部分輸出（G3-08）。
   「每次操作基於版本及影像雜湊」的解讀：版本＝revision（每個請求的 expected_revision，worker 與主行程雙重檢查）＋原檔 SHA-256（開啟、重啟、另存時比對）；
   影像雜湊＝target_id 內的 geometry hash（G2-14）。ADR-0020 與 traceability 原本沒有寫出這項對應，見 §9 U10。

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q                                        → exit 0，306 passed（Windows 實機，2026-10-29，U4／U5 處理後）
```

- P3 新增 31 項測試（G3-01～G3-08 共 28 項、G3-09 共 3 項）；P2 既有 275 項中，3 項依 U5 改為比對時排除 /ID（只改比對方式，期望不變），其餘未修改、全數通過。
- CI：run [40827373536](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40827373536)（commit `b59be8b`）、
  run [40827748845](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40827748845)（commit `1440555`）雙平台 299 passed（安全修補前）；
  安全修補後 run [40832867432](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40832867432)（commit `6a09672`）雙平台 301 passed。獨立核對修正後見 §10。
- 第一次 CI（run 40826959745，commit `e977f1c`）macOS 1 failed、298 passed：`test_worker_killed_during_export_preserves_destination`
  以 1 ms 逾時期待 worker 被終止，macOS 上另存未逾時。原因未查明；改為確定性注入（worker 寫一半暫存檔後 `os._exit`），
  測試改名為 `test_worker_crash_during_export_preserves_destination`（commit `b59be8b`）。
- Windows 執行時 pytest 輸出含 `Windows fatal exception: access violation` 與堆疊，來自測試匯入 pypdfium2 時程式庫初始化
  （stash P3 改動後在 P2 程式碼上同樣出現），測試照常通過，非 P3 引入。

## 5. 真修改證據

本段沒有新增編輯能力，編輯證據沿用 P2（`reports/P2/evidence/`）。P3 的另存交易證據由 G3-02、G3-04 測試在測試內比對：
另存檔 SHA-256 與 worker 回報值相同、重開後新文字在計畫的基線位置、舊文字少一次、每次另存的結構／文字／視覺驗證皆通過。

## 6. 資料完整性與資源／出站紀錄

- **原檔**：唯讀。目的檔是任何已開啟文件的原檔即拒絕（samefile）；每次另存前後兩次比對原檔 SHA-256。
- **目的檔**：worker 只拿到主行程產生的同目錄暫存檔名（`.~peditor-<16 hex>.tmp.pdf`），以 `xb` 建立、寫入、fsync、讀回比對；
  主行程比對暫存檔 SHA-256，再次確認目的檔狀態（不存在，或大小、修改時間、SHA-256）與取得 token 時相同，才 `os.replace`；
  POSIX 另 fsync 目錄。任一步失敗刪除暫存檔。中斷留下的暫存檔超過 10 分鐘，下次寫入同資料夾時刪除。
- **另存前驗證**（ADR-0020 §4）：P2 的結構檢查，加上文字與 MuPDF 視覺（150 DPI、渲染上限 12 MP；可改動區域 +2 pt 外超標像素 ≤0.01%）。
  文字驗證是整頁子字串比對：同頁別處原本就有相同文字時也會通過（triage f014，依 ADR 設計，新字碼在規劃時已由 ToUnicode 反查）。
  T01 等 ADR-0015 的 7 份 MuPDF 渲染空白檔，「每次另存的視覺驗證皆通過」實際上沒有比對到內容（§7）。
- **工作文件**：套用失敗以開啟自的位元組回滾；undo／redo 由原始位元組重播 command log，revision 單調遞增。
- **復原草稿**：本機資料目錄、原子寫入、POSIX 0600、7 天逾期刪除；DocumentService 預設不啟用（CLI 不用），P4 UI 傳入草稿區才啟用。
- **錯誤訊息**：ProtocolError／ServiceError 訊息不含路徑與原文。已知例外：交易中少數 OSError（triage f010），以及復原草稿區的
  `mkdir`、`listdir`、`os.open` 失敗（`drafts.py`，經 apply／undo／redo 傳出）未包裝，會以含完整路徑的原始例外拋出（§9 U4）。
- **暫存檔保留**：程式中斷留下的暫存檔要等下次寫入同資料夾且超過 10 分鐘才清除；使用者不再存到該資料夾時**沒有時間上限**，
  不完全符合 spec P3「包含敏感內容的暫存不可長期無限制保留」（§9 U9）。
- **出站**：新增模組未匯入網路模組（`test_offline_guard` 通過）。實機出站監測於 P7。
- **資源**：視覺驗證渲染上限 12 MP、超標即停（f015）；其餘沿用 P1、P2 限制。undo 重播耗時與步數成正比（S3 時以臨時腳本在本機量測，未入庫：T01 模式 A 每步約 22 ms、F02 模式 B 約 166 ms，各 10 次平均；§9 U3）。

## 7. 限制、阻擋、未測項目

- **macOS 實機**：NOT RUN。ADR-0003 的停止條件為「P3 結束時（最晚 11/16）仍無 macOS 實機取得方案」，見 §9 U1。
- **真實磁碟填滿**：NOT RUN。G3-06 以模擬 ENOSPC（worker 寫一半後拋出、交易層寫入失敗）驗證。
- **§8.3 效能與穩定**：NOT RUN（P2 U5 延續，§9 U7）。50 次操作循環的 worker 峰值記憶體未量測。
- **盲測**：NOT RUN，P8 由保管人在離線實機執行。
- **ADR-0015 的 7 份 MuPDF 渲染空白檔**（T01、F01、F02、F05、L02、L03、B01）：產品端視覺驗證對這 7 份兩邊都是空白，實際上偵測不到差異（§9 U2）。
  G3 測試多用 T01，視覺部分另以 F04 驗證（`test_product_checks_detect_problems`）。
- **G3-01 的 50 次操作**用測試內 Helvetica 樣本（模式 A，每步不同數字），在 worker 函式層直接驗證；經 DocumentService 的 undo／redo 以 T01 驗證流程，步數較少。

## 8. 安全審查

- 依 ADR-0005，以 `.claude/skills/vuln-scan`、`triage`（defending-code-reference-harness@d3bea6b）手動執行。
- **vuln-scan**（`reports/P3/security/VULN-FINDINGS.{json,md}`）：P3 新增／修改的 `src/` 分 4 個焦點區域（主行程儲存交易、worker 另存驗證與寫入、
  undo／重播與回滾、復原草稿）各一個子代理人，15 項候選（全為 LOW）。worker 寫入、讀回與部分檔清理路徑掃描結果為無問題。
- **triage**（`reports/P3/security/TRIAGE.{json,md}`）：沿用 P1 訪談的信任邊界，加註「應用程式自己寫的草稿可能因崩潰毀損，但同使用者的其他行程不是安全邊界」；
  每項 2 票、互不知情的驗證子代理人；沒有分票，未用第 3 票。結果 14 項誤報、1 項確認（LOW）。
- **f015 已修**：另存前視覺驗證的逐點比對迴圈，大頁面大字級時可超過 30 秒逾時。修補：渲染上限 12 MP（依 MuPDF 向外取整後的像素數調降 DPI）；
  遮罩外區段先整段比對、遮罩內像素不逐點讀取、超標即停。
  回歸 `tests/security/test_p3_scan_regressions.py`（G3-09，3 項）驗證工作量上限本身而非牆鐘時間：渲染像素 ≤12 MP、遮罩內像素讀取次數為 0、計數與逐點定義相同且超標即停。
  以修正前的 `src`（commit `1440555`，解壓到暫存目錄、PYTHONPATH 指向它）執行：渲染上限項因渲染 50,013,184 像素而失敗；另兩項因函式介面不同（缺 limit 參數）而失敗。
  修正前 `visual_check` 耗時：我在 S3 時量到 14.5 秒，獨立核對量到 4.1 秒，隨機器負載而異；最初版的回歸測試以「<10 秒」判定，在核對者的機器上修正前也會通過，已改為上述確定性檢查（§11 V1）。
  改寫時另發現第一版修補的渲染上限因 MuPDF 向外取整而超出 6,225 像素（12,006,225），已一併修正。
- 判為誤報但驗證者確認程式行為屬實的正確性缺陷（不是安全問題），列於 TRIAGE.md 末節與 §9 U4。
- `THREAT_MODEL.md`：**已更新**（§1、§3 新增復原草稿進入點、T3 改為 mitigated、T5、T10（維持 partially_mitigated，殘餘 f009、f012）、T11、T13、§6、§7、§8）。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | ADR-0003 停止條件：P3 結束時（最晚 11/16）須有 macOS 實機取得方案 | 沒有方案即觸發停止條件；G4、G7、G8 仍須實機 | 工程師決定借用或購入 |
| U2 | 產品端視覺驗證用 MuPDF；ADR-0015 的 7 份渲染空白檔驗證無效。ADR-0015 第 40 行寫「P3（UI 預覽）前」處理，但 UI 預覽在 P4，判斷為筆誤 | 這 7 類檔案另存時沒有視覺防護；P4 預覽也會是空白 | 工程師確認延到 P4 預覽前另立 ADR 處理 |
| U3 | undo、worker 重啟還原、草稿復原都以單一請求重播整個 log，受 30 秒逾時限制（triage f008，判為設計取捨）；還原失敗時 close_document 的錯誤會蓋過原錯誤 | 大檔多步時 undo 可能逾時並反覆失敗，未存的編輯存不出去 | 工程師決定是否 P4 前量測，再決定分段重播或「log＋快照」（需 ADR） |
| U4 | triage 確認程式行為屬實但非安全問題：f001 草稿缺結構驗證、f007 寫草稿失敗時誤報失敗、f010 OSError 含完整路徑（違反 CLAUDE.md）、f006 editable_region 以參照保存、f009 不覆寫的 rename 非原子、f011 暫存檔刪除失敗、f012 覆寫後權限改變；獨立核對另指出草稿區 OSError 同樣含完整路徑（V6） | f001、f006 在 P4 啟用草稿／UI 前須處理 | **部分已處理**（工程師 2026-10-29 決定合併前修含路徑的錯誤）：交易與草稿區的 OSError 一律轉為不含路徑的 SAVE_FAILED；目的檔已取代後的目錄同步失敗改為警告；寫草稿失敗時編輯照常生效、結果加 `warnings`（同時修正 f007）。測試 `test_crash_injection.py::test_os_errors_carry_no_path`、`::test_fsync_failure_after_replace_is_warning`、`test_drafts.py::test_draft_errors_carry_no_path_and_do_not_undo_edit`（修正前三項皆失敗）。f001、f006 排入 P4；f009、f011、f012 排入 P7 |
| U5 | P2 U3：3 個測試比對兩次存檔位元組，跨秒時 /ID 第二元素不同而偶發失敗 | CI 偶發失敗 | **已處理**（工程師 2026-10-29 決定合併前修）：`test_edit_multi.py`、`test_edit_text.py::test_rejections_leave_files_unchanged`、`test_p2_scan_regressions.py` 改為比對時以正規表示式移除 trailer `/ID [<…><…>]`；產品輸出不變。本機以 T01、F04、T05 各存兩次（相隔 1.1 秒）驗證：原始位元組不同、移除 /ID 後相同 |
| U6 | P2 U4 中 f006、f018、f023、f015 依 S2 決定不在 P3 範圍 | 威脅模型 T4、T11 殘餘風險不變 | 已決定（2026-10-28），列此備查 |
| U7 | spec §8.3 效能基準未量測（P2 U5 延續） | 規模決策與 U3 的重播成本都缺實測 | 工程師決定量測時點 |
| U8 | Dependabot #10（setuptools，build 群組）延到 P7 | 只影響打包工具，不在產品執行期 | 已決定（2026-10-29） |
| U9 | 程式中斷留下的暫存檔（含完整文件）只在下次寫入同資料夾且超過 10 分鐘時清除；不再存到該資料夾就沒有時間上限（獨立核對 V3） | 不完全符合 spec P3「包含敏感內容的暫存不可長期無限制保留」 | 工程師決定：接受為已知限制，或改為在本機資料目錄記錄暫存檔位置、啟動時清除（P4 前） |
| U10 | spec P3「每次操作基於版本及影像雜湊」：本報告解讀為 revision＋原檔 SHA-256＋target_id 的 geometry hash（§3 第 6 點），ADR-0020 未明文 | 解讀若不符原意，需補實作（例如每次操作比對工作文件內容雜湊） | 工程師確認解讀 |
| U11 | 「另存途中逾時終止 worker（RESOURCE_LIMIT）」在 `b59be8b` 改寫測試後已無測試，現只測 worker 崩潰（WORKER_FAILED）；macOS CI 上 1 ms 逾時未觸發的原因未查明（獨立核對 V9） | 與 G7「長操作可取消／逾時可停止」相關 | 工程師決定是否於 P4（取消 UI）前查明 |
| U12 | 重播失敗時：規劃不是 ready 回 VALIDATION_FAILED，其他錯誤以原錯誤碼回傳（ADR-0020 §1 已改寫為此行為）；服務層 undo／redo 失敗時 revision 與 log 不變只有程式審查，沒有服務層測試（只有 worker 層 `test_replay_failure_restores_state`）（V10） | 服務層失敗路徑缺測試證據 | 工程師決定是否補測試 |

## 10. 關卡結果

- CI：run [40832867432](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40832867432)（commit `6a09672`，安全修補後）windows-latest 301 passed、macos-15 301 passed；
  安全修補前 run 40827373536（commit `b59be8b`）、40827748845（commit `1440555`）雙平台 299 passed；
  獨立核對修正後 run [40840198233](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40840198233)（commit `ecf3baa`）windows-latest 303 passed、macos-15 303 passed。
  U4／U5 處理後 run [40850680948](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40850680948)（commit `4c52303`）windows-latest 306 passed、macos-15 306 passed。
- **關卡結果：PASS（附條件）**（範圍：G3-01～G3-09 均有測試證據，本機 Windows 301 passed；真實磁碟填滿、macOS 實機、§8.3 效能 NOT RUN 並註明原因）
- **下一段可開始：待定**：須由工程師確認 U1（macOS 實機方案）、U9、U10；U4、U5 已處理；U2、U3、U7、U11、U12 可於 P4 開工前決定。

## 11. 獨立核對紀錄

第一輪（2026-10-29，HEAD `52d1b79`）：未參與實作的 Claude 子代理人重跑 ruff（通過）與 pytest（301 passed）；
確認 `tests/` 只有新增檔、既有 275 項未改；核對 CI run 40832867432、40826959745；以 `git archive` 取出修正前的 `src` 到暫存目錄重跑 f015 測試；
逐項比對 G3 測試、ADR-0020、spec P3／§7、TRIAGE、THREAT_MODEL。結論「有出入」，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| V1（must-fix） | f015 回歸測試以「<10 秒」判定，修正前程式在核對者機器上 4.1 秒、測試通過；「修正前 14.5 秒失敗」無法重現 | 改為確定性檢查（渲染像素上限、遮罩內不逐點讀取、超標即停）；以修正前 `src` 重跑確認失敗；同時發現並修正渲染上限超出 6,225 像素；§8、TRIAGE、traceability 改寫 |
| V2 | run 40827373536 對應 commit `b59be8b`，不是 `1440555` | §4 改正，並列出 `1440555` 的 run 40827748845 |
| V3 | 中斷留下的暫存檔沒有時間上限 | §6、§9 U9、THREAT_MODEL T3 明列 |
| V4 | 10 分鐘門檻沒有測試 | 新增 `test_stale_temp_threshold` |
| V5 | 「影像雜湊」未對應 | §3 第 6 點寫出解讀，§9 U10 請工程師確認 |
| V6 | 草稿區 OSError 也含路徑 | §6、§9 U4 補列 |
| V7 | G3-04 結論比測試強 | 補 c1 含新文字、未修復的斷言，G3-04 改寫 |
| V8 | G3-03 中斷點的實際意義未說明 | G3-03 補三個中斷點的程式位置與驗證順序 |
| V9 | 逾時路徑已無測試、macOS 1 ms 未逾時原因未查 | §9 U11 |
| V10 | ADR 寫重播失敗一律 VALIDATION_FAILED，實作不同；服務層失敗無測試 | ADR-0020 §1 改寫為實際行為；§9 U12 |
| V11 | 文字驗證為整頁子字串、T01 視覺驗證無效未在 §6 說明 | §6 補註 |
| V12 | VULN-FINDINGS 時間戳晚於 commit；traceability G3-06 fixture 欄；22／166 ms 無證據；T10 標 mitigated 依據不足 | 時間戳改為檔案實際寫入時間 06:44:19Z；G3-06 改 T01；§6 註明臨時腳本量測未入庫；T10 改回 partially_mitigated |

修正後本機 303 passed；CI run 40840198233（commit `ecf3baa`）雙平台 303 passed。
