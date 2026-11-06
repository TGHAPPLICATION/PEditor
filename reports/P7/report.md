# P7 關卡報告：離線與安全強化

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段自動測試在本機 Windows 製作機與 CI 執行，**不是實機證據**；G7 實機項目見 §3、§6。

## 1. 階段／commit／日期

- 階段：P7　分支：`p7-security-hardening`　commit：`c2891d7`（worker Job Object／rlimit）、`16e860a`（解壓前大小限制、CMap 線性解析、影像像素上限）、
  `699e80d`（S03、S05、S06；惡意樣本與 socket 測試；超限頁面不渲染）、`420c686`（回應結構驗證、畸形輸入測試）、`dce8aec`（G7-05、G7-01 自動測試）、
  `968b027`（重播分批、關閉等待上限、U13）、`294e352`（S04）、`c594efd`（`.gitattributes`）、`132eb14`（f009、f012、U10）、`e2e899c`（實機腳本）、
  `c5960e0`、`3412e05`、`860927c`（測試補強）、`0533432`（關閉逾時後不發 signal）、`87ec3b2`、`57fdb4d`（安全掃描候選與 triage 處理）、`ac66cba`（第一輪核對 V3–V5、V8）　日期：2026-11-04～11-05
- 只改報告、traceability、THREAT_MODEL 或 CI 紀錄的 commit 依 P4 慣例不列。
- S1／S2 決定（工程師 2026-11-04「照建議」）：OS 限制採 Windows Job Object＋POSIX rlimit、不做完整沙箱並列缺口；Windows 實機以一鍵腳本由工程師執行，
  macOS NOT RUN；帶入項目做安全與穩定性類，U13 一併處理，P4 U12、U14、P5 U3 移 P8；不新增產品日誌，G7-05 改檢查所有對外輸出。
  2026-11-05：S04 預期改為 `MALFORMED_DOCUMENT`（工程師「你的建議」）；安全掃描候選 1–9 與觀察的處理（工程師「照建議」，§8）。
- 撰寫：Claude Code；審查：待工程師；獨立核對：待（CLAUDE.md：由未參與實作的子代理人核對）

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；PySide6 6.11.2；fontTools 4.66.0；pypdfium2 5.13.0、Pillow 13.0.0（只在測試）；Noto Sans TC（ADR-0008） |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest x64 | GitHub 標準 runner | 套件同上（`uv.lock`）；offscreen |
| CI macos | macos-15 arm64 | GitHub 標準 runner | 套件同上（`uv.lock`）；offscreen |

相依沒有變更（`uv.lock`、`pyproject.toml` 未改）。新增 fixture S03–S06（§3），其餘 fixture 未重產；新增 `.gitattributes`（`*.pdf binary`，S04 全為 ASCII，
避免 checkout 時換行轉換改變 xref 位移與 hash）。

## 3. 需求 → test ID → fixture／hash → 結果

fixture hash（前 12 碼）：S03 `8f5cbf6df7a7`、S04 `2dd116833d7e`、S05 `1ea4c88f4f75`、S06 `c9eadedcf5e3`；其餘同 P6。
「本機」＝Windows 製作機；「CI」＝run [42011872284](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42011872284)（commit `ad427c0`）windows-latest 550 passed＋1 skipped（POSIX 權限位元測試）、macos-15 547 passed＋4 skipped（Windows-only 的 Job Object 與唯讀屬性測試）。

| 需求 ID | test ID | fixture | 環境 | 結果 |
| --- | --- | --- | --- | --- |
| G7-01 斷網完整開／編／存 | `tests/security/test_offline_flow.py::test_offline_flow`（主行程與 worker 以 audit hook 禁止並記錄 Python 層的 socket 事件，完整開、分析、渲染、規劃、預覽、套用、復原、重做、另存後兩邊都沒有事件；原生函式庫的 socket 不經 audit hook，由 G7-02 涵蓋）、`::test_deny_hook_blocks_sockets`、`::test_worker_hook_records_swallowed_attempts`（對照） | T01 | 本機、CI | PASS（自動測試）；**Windows 實機 NOT RUN**（`scripts/p7_offline_check.ps1` 須於網路介面全部中斷時由工程師執行；本機以連網狀態試跑腳本：10 輪、25.5 秒、FLOW-OK，見 §6）；macOS 實機 NOT RUN |
| G7-02 零出站、無 listener | `tests/security/test_no_listener.py::test_no_listening_sockets`（流程進行中背景持續輪詢、結束後再查一次，測試行程＝主行程與 worker 整棵行程樹沒有任何 socket，含 loopback；列舉失敗即測試失敗）、`::test_connection_check_detects_sockets`、`::test_connection_check_covers_child_processes`（對照：自己或子行程開 listener 時列得出來） | T01 | 本機、CI | PASS（自動測試）；**Windows 實機 NOT RUN**（同上腳本）；macOS 實機 NOT RUN |
| G7-03 惡意樣本不啟動外部程式／連線 | `tests/security/test_malicious.py::test_no_external_launch`（S02–S06 開檔、判定、分析、渲染、另存；S06 Launch 若執行會在目前資料夾建立 sentinel 檔；worker 無 socket）、`tests/security/test_sandbox.py::test_worker_cannot_spawn_processes`、`::test_spawn_hook_works_without_job`（對照） | S02–S06 | 本機、CI | PASS；子行程限制 macOS 無 OS 強制（ADR-0024 缺口，Windows-only 測試在 macOS 略過，記 NOT RUN） |
| G7-04 逾時停止、崩潰重啟 | `tests/security/test_worker_limits.py`（P1：逾時、取消、崩潰重啟）、`tests/security/test_sandbox.py::test_worker_dies_with_main_process`（worker 執行長操作時主行程異常結束，worker 整棵行程樹一併終止）、`tests/unit/test_replay_batches.py`（3 項）、`tests/gui/test_p7_ui.py::test_shutdown_wait_is_bounded` | T01 | 本機、CI | PASS；隨主行程終止 macOS NOT RUN |
| G7-05 日誌不洩漏 | `tests/security/test_logging.py::test_no_sentinel_in_logs`（sentinel 資料夾、檔名、文件內容、新文字；錯誤訊息與 worker stderr）、`::test_cli_stderr_has_no_sentinel`（2 組） | T01、S01–S03、U02 | 本機、CI | PASS |
| G7-06 限制初值、載入前／解析中限制 | `tests/security/test_p7_limits.py`（11 項）、`tests/security/test_sandbox.py::test_memory_limit_controlled`、`tests/security/test_ipc_fuzz.py`（32 項）、`test_malicious.py[S03]`、`[S04]`、P1 的檔案大小與頁數測試 | S03、S04 | 本機、CI | PASS；記憶體上限 macOS NOT RUN（ADR-0024 缺口） |
| G7-07 OS 沙箱評估與缺口 | ADR-0024 §2、本報告 §8 | — | 文件 | 待獨立核對 |

限制初值對照（spec P7）：檔案 200 MB、500 頁（P1，讀檔前與解析頁面前）；單張影像 50 MP（渲染、新圖、PDF 內影像宣告）；單操作 30 秒（P1；重播分批後每批各自計時）；
worker 2 GB（Windows Job Object 強制；macOS 只宣告）；另加單一串流解壓後 64 MB（解壓前檢查）。

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .  → exit 0
uv run pytest -q                                        → 528 passed、1 failed（Windows 製作機，968b027 前的工作區；失敗為 test_drafts 的注入點，見下）
uv run pytest -q                                        → exit 0，550 passed、1 skipped（Windows 製作機，18d3c3e；POSIX 權限位元測試略過）
```

- 第一次在重播分批後跑全套時，被 Claude Code 因系統記憶體不足終止（無輸出、不是測試失敗）；工程師同意後重跑：528 passed、1 failed。
  失敗的 `test_drafts.py::test_recover_failure_closes_document` 以替換 `_doc_call` 注入重播失敗，重播改走 `_replay_batches` 後注入不到；
  改為替換 `_replay_batches`，預期（任何例外都關閉文件、草稿保留）不變（`968b027`）。
- 第一輪核對處理後（`3e99755`）本機全套 551 passed、1 failed：`test_offline_guard.py::test_no_network_imports_in_product_code`——V3 的對照 hook（`_socket`）在 worker 的測試 hook 裡匯入了 socket，違反「產品碼不得匯入網路模組」；改為在測試端子行程安裝同一個 `_deny_network` 並嘗試建立 socket（`14b6f79`），M26 重做仍抓到。
- CI：run [42011872284](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42011872284)（commit `ad427c0`）windows-latest 550 passed＋1 skipped（POSIX 權限位元測試）、macos-15 547 passed＋4 skipped（Windows-only 的 Job Object 與唯讀屬性測試）；run [42005863669](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42005863669)（commit `0533432`）windows-latest 543 passed＋1 skipped（POSIX 權限位元測試）、macos-15 541 passed＋3 skipped（Windows-only 的 Job Object 測試）。先前 run [42004855861](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42004855861)（commit `78bce58`）
  macos-15 在 `tests/gui/test_p7_ui.py::test_shutdown_wait_is_bounded` 發生 segmentation fault（windows-latest 543 passed）：關閉等待逾時返回後，
  背景工作結束時對已回收的 JobRunner 發 signal。產品端改為逾時返回前先標記放棄、之後結束的工作不再發 signal，測試改為結束前等背景工作完成（`0533432`）；
  run [41982237300](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41982237300)（commit `c594efd`）windows-latest 535 passed、macos-15 532 passed＋3 skipped。
- P7 新增測試：`tests/security/` 的 `test_sandbox.py` 4 項、`test_p7_limits.py` 11 項、`test_malicious.py` 5 項、`test_no_listener.py` 3 項、`test_ipc_fuzz.py` 32 項、
  `test_logging.py` 3 項、`test_offline_flow.py` 3 項；`tests/unit/test_replay_batches.py` 3 項；`tests/gui/test_p7_ui.py` 2 項；`test_crash_injection.py` 4 項；
  另 `test_analyzer.py`、`test_fixtures.py`、`test_manifest.py` 納入 S03–S06。
- **反向驗證**（repo 外的臨時腳本；工作區先提交乾淨，逐一改壞實作、跑對應測試、再還原）：26 項全部被抓到（M3、M16 第一次沒抓到，補強測試後重做抓到；M17–M25 為安全掃描候選與 triage 處理後、M26 為第一輪核對處理後補做）——

  | # | 改壞的地方 | 抓到的測試 |
  | --- | --- | --- |
  | M1 | 不套用 Job Object | `test_sandbox.py::test_memory_limit_controlled` |
  | M2 | 不限子行程數 | `::test_worker_cannot_spawn_processes` |
  | M3 | 不設 KILL_ON_JOB_CLOSE | `::test_worker_dies_with_main_process`（第一次沒抓到：閒置的 worker 在管線關閉時自己結束；改為 worker 執行長操作時主行程結束，`3412e05` 後重做抓到） |
  | M4 | MemoryError 不轉 RESOURCE_LIMIT | `::test_memory_limit_controlled` |
  | M5 | 不檢查解壓後大小 | `test_p7_limits.py::test_flate_bomb_rejected_before_full_decode` |
  | M6 | CMap 改回正規表示式 | `::test_cmap_unterminated_blocks_linear`（300 秒未結束，視為抓到） |
  | M7 | 不限影像像素 | `::test_huge_image_page_rejected` |
  | M8 | 超限頁面照常渲染 | `test_malicious.py[S03]`（第一次執行途中工作區被還原，結果不可信，重做） |
  | M9 | 不驗證回應結構 | `test_ipc_fuzz.py::test_service_rejects_malformed_responses` |
  | M10 | 回傳非字串 request_id | `::test_worker_rejects_malformed_lines` |
  | M11 | 重播不分批 | `test_replay_batches.py::test_replay_split_into_batches` |
  | M12 | 關閉等待無上限 | `test_p7_ui.py::test_shutdown_wait_is_bounded` |
  | M13 | 0 頁文件不清畫面 | `::test_zero_page_document_clears_previous_page` |
  | M14 | 不覆寫時仍取代 | `test_crash_injection.py::test_no_overwrite_refuses_destination_created_late` |
  | M15 | 啟動清除不看年齡 | `::test_cleanup_recorded_keeps_recent_temps` |
  | M16 | 錯誤訊息帶路徑 | `test_logging.py::test_no_sentinel_in_logs`（第一次沒抓到：測試給的圖片檔讀得到，沒走到錯誤路徑；`860927c` 加入讀不到的檔案後重做抓到） |
  | M17 | 毀損 Flate 回傳已解出大小（候選 1） | `test_p7_limits.py::test_corrupt_flate_before_other_filter_rejected` |
  | M18 | NaN 視為通過（候選 1） | 同上 |
  | M19 | Windows 也複製權限（候選 2） | `test_crash_injection.py::test_overwrite_readonly_leaves_no_readonly_temp` |
  | M20 | bfrange 陣列改回原寫法（候選 4） | `test_p7_limits.py::test_cmap_unterminated_array_linear`（90 秒未結束，視為抓到） |
  | M21 | 文件層級超限也不渲染（觀察） | `::test_document_level_limit_still_renders` |
  | M22 | 未塗繪路徑不限點數（候選 5） | `::test_unpainted_path_points_bounded` |
  | M23 | 墨跡檢查不限像素（候選 3） | `::test_ink_check_pixel_bound` |
  | M24 | 逾時每行重新計時（候選 7） | `test_ipc_fuzz.py::test_request_timeout_is_total`（90 秒未結束，視為抓到） |
  | M25 | 渲染判定改回 `87ec3b2` 的條件（triage 指出的繞過） | `test_p7_limits.py::test_document_level_limit_still_renders`（S03 部分） |
  | M26 | worker 的 deny hook 不記錄事件（第一輪核對 V3） | `test_offline_flow.py::test_worker_hook_records_swallowed_attempts` |

- 反向驗證過程：M6 卡住時第一版腳本的逾時只終止 `uv`，pytest 孫行程仍握著管線而一直等待；以 Stop-Process 終止後，腳本的外層 shell 結束但 Python 腳本繼續跑完，
  其間我以 `git checkout` 還原了當時突變中的 analyzer.py（M8），因此 M8 重做。之後的腳本改為每項寫入結果、逾時以 `taskkill /T` 終止整棵行程樹。

## 5. 真修改證據

不適用（P7 沒有新增編輯功能）。既有的編輯證據不受影響：G2–G6 測試全部通過（§4）。

## 6. 資料完整性與資源／出站紀錄

- **出站**：產品碼不匯入網路模組（`test_offline_guard`）；自動測試以 audit hook 禁止 socket 完成完整流程（G7-01）、流程中無任何 socket（G7-02）。
- **實機腳本試跑**（2026-11-05，製作機，**網路連線中**，因此不是 G7-01 證據）：`powershell -ExecutionPolicy Bypass -File scripts\p7_offline_check.ps1` → exit 0；
  10 輪、25.5 秒、輪詢 29 次（平均間隔 0.88 秒，`Get-NetTCPConnection` 本身約 0.8 秒）、行程樹最多 6 個行程、看到的 socket 0 個；S06 未建立 sentinel 檔。
  輪詢可能漏掉短於間隔的連線嘗試（§7）。
- **資源**：Windows 上 worker 記憶體 2 GB、子行程、隨主行程終止由 Job Object 強制；S03 壓縮炸彈不解壓即拒絕；S04 深層巢狀物件 0.7 秒內受控拒絕。
- **另存**：不覆寫時晚出現的目的檔不被取代（f009）、覆寫保留權限位元（f012）；暫存檔紀錄加鎖、啟動只清除過期暫存檔（U10）。
  P3 triage f011（暫存檔刪不掉）已由 P3 U9 的紀錄檔＋啟動清除處理：刪不掉的路徑留在紀錄，下次啟動再刪。

## 7. 限制、阻擋、未測項目

- **Windows 實機 G7-01、G7-02：NOT RUN**——須由工程師在網路介面全部中斷時執行 `scripts\p7_offline_check.ps1`，把 `build\p7-check\summary.md` 交回。
- **macOS 實機：NOT RUN**（ADR-0003：P7 斷網與零出站不能以 CI 代替）；macOS 上記憶體與子行程限制沒有 OS 強制，相關 4 項測試在 macOS 略過。
- 實機出站監測以輪詢進行，短於約 1 秒的連線嘗試可能漏掉；自動測試的 audit hook（任何 socket 操作即失敗）與 Job Object 補足。
- 非完整 OS 沙箱：worker 仍有使用者的檔案與網路權限（ADR-0024 §2）。spec P7 四項最低要求（ADR-0024 §2 對照表）：獨立程序、限制 IPC 達成；路徑白名單只在主行程層級（部分達成）；OS 出站封鎖驗證只有監測、沒有封鎖規則，Windows 實機待執行（部分達成）；見 §9 U6。
- 只靠讀程式確認、沒有測試抓得到的項目：worker 以暫停狀態建立再套用 Job（拿掉時間窗本質上難以測到）；MuPDF、qpdf 原生配置失敗時的回應碼。
- 打包後（PyInstaller）worker 在 Job 內以 1 個行程啟動未驗證，列 P8。S06 的 Launch 只定義 Windows 的命令，macOS 上「沒有 sentinel 檔」的檢查沒有實際作用。
- 實機腳本以「Up 的網卡數」判斷斷網；虛擬網卡（VPN、Hyper-V）可能維持 Up，摘要列出每張網卡的狀態供工程師判斷。
- MuPDF 自行解壓、不經 content 解譯器的串流（註解外觀等）只受記憶體上限保護。
- 回應驗證只檢查結構，不檢查巢狀內容語義。
- P4 U12、U14、P5 U3 移至 P8（S2 決定）。

## 8. 安全審查

- 依 ADR-0005，以 `.claude/skills/vuln-scan`、`triage`（defending-code-reference-harness@d3bea6b）手動執行，由未參與實作的子代理人進行。
- **vuln-scan**：第一次執行的子代理人讀完範圍內程式（`0533432`）、列出候選 9 項與觀察 1 項後，因一段回應被安全分類器擋下而中途停止，沒有寫出檔案；
  工程師決定照建議處理全部候選（`87ec3b2` 程式與回歸測試、`8ca60b2` ADR-0024 增補）。之後另一個子代理人依該候選清單補寫 `reports/P7/security/VULN-FINDINGS.{json,md}`
  並逐項重新讀程式驗證（候選的信心值與確切掃描時間未保留，JSON 中 `confidence` 為 null）。
- **triage**（`reports/P7/security/TRIAGE.{json,md}`）：沿用 P1／P3 訪談的信任邊界；9 項中確認 6 項（MEDIUM 1：f001 毀損 Flate 使解壓前上限被繞過；LOW 5：f003 墨跡檢查無像素上限、
  f004 bfrange 陣列平方級、f005 未塗繪路徑點數、f006 MuPDF 自行解壓的物件不受檢查〔documented〕、f009 pikepdf 與 MuPDF 解析差異〔needs manual test，documented〕），
  誤報 3 項（f002 Windows 唯讀暫存檔：沒有越過信任邊界，但屬 P7 帶入的正確性回歸，已修；f007 逾時重新計時：只有被攻陷的 worker 做得到，已修；f008 ADR 措辭過強，已修文件）。
  兩票由 triage 子代理人以兩個角度自行判讀（未另派子代理人），f009 分票依 recall 保留。
- triage 另指出：觀察項的第一版修正（`87ec3b2`，文件層級已超限就不拒絕渲染）使文件層級超限的文件中、頁面本身超限的頁面也被交給 MuPDF 渲染；
  `57fdb4d` 改為記錄頁面本身是否超限（`Document.limited_pages`），並補測試（M25）。THREAT_MODEL T1 的「不得建立子行程」同步修正為「worker 不得直接建立子行程」。
- triage 未在修正前的 commit 上執行回歸測試；MuPDF／qpdf 對毀損 Flate 與修復差異的行為未以原始碼確認（TRIAGE.md 已註明）。
- OS 沙箱評估：ADR-0024 §2（Windows AppContainer、Job Object；macOS App Sandbox、sandbox-exec；網路封鎖）與缺口。
- `THREAT_MODEL.md` 已更新：T1、T2、T5、T7、T10、§6 OS 沙箱待決問題（已決定）、控制清單。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 處理 |
| --- | --- | --- | --- |
| U1 | 解壓前限制使單一串流超過 64 MB、含不認得過濾器的內容串流、原始大小超過 16 KB 的 LZW 串流所在頁面不能編輯 | 偏保守；45 份既有 fixture 無影響（全套通過） | **接受**（工程師 2026-11-05 回覆「你建議」） |
| U2 | worker 回應結構不符一律重啟 worker | 比原本嚴格 | **接受**（工程師 2026-11-05 回覆「你建議」） |
| U3 | Windows 實機驗證須工程師執行腳本；macOS 實機 NOT RUN | G7 要求兩平台實機 | **附條件**（工程師 2026-11-05 回覆「你建議」）：Windows 實機由工程師斷網後執行 `scripts\p7_offline_check.ps1`，結果寫回 §6（目前 NOT RUN）；macOS 實機依 ADR-0021／ADR-0003 附條件，取得實機後補驗 |
| U4 | 安全掃描後新增的保守行為：毀損的 Flate 後接其他過濾器即視為超限；未塗繪路徑點數超過 100,000 即頁面 RESOURCE_LIMIT；格區域渲染超過 12 MP 的儲存格編輯回 RESOURCE_LIMIT | 這類頁面或格不能編輯 | **接受**（工程師 2026-11-05 回覆「你建議」） |
| U5 | 殘餘（ADR-0024 後果）：MuPDF 自行解壓的物件（inline image、SMask、pattern、soft mask、Type3 資源、內嵌 CMap、註解外觀、shading、Function、ICC、影像資料的壓縮比）只受記憶體上限保護；pikepdf 與 MuPDF 對同檔的解析差異（triage f009，needs manual test） | macOS 無記憶體上限 | **列殘餘**（工程師 2026-11-05 回覆「你建議」；ADR-0024 後果、THREAT_MODEL T1、T5） |
| U6 | spec P7 最低要求中「路徑白名單」只在主行程層級（worker 無 OS 強制）、「作業系統出站封鎖驗證」只有監測沒有封鎖規則（ADR-0024 §2 對照表；第一輪核對 V1） | worker 被攻陷時可讀寫使用者檔案、可嘗試連線 | 待工程師決定 |

## 10. 關卡結果

- **關卡結果：BLOCKED**。自動測試全部通過（本機 550 passed）、反向驗證 26 項全部被抓到、vuln-scan／triage 完成且確認項目已處理；
  run [42011872284](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42011872284)（commit `ad427c0`）windows-latest 550 passed＋1 skipped（POSIX 權限位元測試）、macos-15 547 passed＋4 skipped（Windows-only 的 Job Object 與唯讀屬性測試）；§9 U1–U5 已由工程師決定（U3 附條件）；Windows 實機 G7-01、G7-02 待工程師執行；macOS 實機 NOT RUN；獨立核對待執行。
- **下一段可開始：否**（條件：上述項目完成並由工程師決定）。

## 11. 獨立核對紀錄

第一輪（2026-11-05，HEAD `3897d18`）：未參與實作、也未做 P7 安全掃描與 triage 的 Claude 子代理人核對（暫時腳本與複本放在 repo 外，結束時工作區乾淨）。
自行驗證屬實：§1 commit 都在分支上；ruff、format 通過，pytest 550 passed、1 skipped；反向驗證抽查 M2、M3、M9、M14、M17、M25 都被抓到；
49 份 fixture 在 main 與 HEAD 之間只有 S03 不同（預期）；主行程結束時 worker 整棵行程樹（轉介程式、直譯器、conhost）都終止；
連線檢查涵蓋轉介程式底下的直譯器；worker 的 deny hook 會安裝；Job Object 生效順序與 fail closed 成立；限制初值逐項符合 spec；
P7 對既有測試的修改都有正當理由。結論「有出入」，**有 must-fix**：

| # | 內容 | 處理 |
| --- | --- | --- |
| V1（must-fix） | spec P7「最低必須有獨立程序、限制 IPC、路徑白名單與作業系統出站封鎖驗證」沒有逐項說明達成與否：路徑白名單只有主行程層級（開檔路徑、destination_token），worker 無 OS 強制；OS 出站封鎖沒有防火牆封鎖、只有監測腳本且實機 NOT RUN | 工程師決定全部照建議處理（2026-11-06）。ADR-0024 §2 加 spec 四項最低要求對照表（獨立程序、限制 IPC 達成；路徑白名單、OS 出站封鎖驗證部分達成）；§7 同步；部分達成兩項列 §9 U6 |
| V2（should-fix） | 測試數不一致：§3 G7-06 列寫 test_p7_limits 6 項、test_ipc_fuzz 31 項（實際 11、32）；traceability G7-04 寫 test_replay_batches 2 項（2 個函式、3 個收集項） | §3 G7-06 改為 11 項、32 項；traceability G7-04 改為「2 個測試、3 項」 |
| V3（should-fix） | G7-01：worker 的 deny hook 只擋不記錄，被 worker 內部吞掉的 socket 嘗試不會被發現（拿掉 worker hook 測試仍通過）；audit hook 只涵蓋 Python 層，原生函式庫的 socket 不在內；報告「禁止所有 socket」過強 | `ac66cba`：worker 的 deny hook 記錄事件到 `PEDITOR_TEST_NETWORK_LOG`，`test_offline_flow` 確認 worker 端沒有事件；新增 `test_worker_hook_records_swallowed_attempts`（對照，M26）；措辭改為「Python 層 socket 事件」，原生函式庫由 G7-02 涵蓋 |
| V4（should-fix） | G7-02：自動測試只在兩個時間點快照（不是「流程中」）；`network.py::_children` 不檢查 PowerShell／pgrep 結束碼，枚舉失敗會假通過；對照組只涵蓋測試行程自己 | `ac66cba`：`test_no_listening_sockets` 改為背景持續輪詢（每 0.2 秒加列舉時間）並在結束後再查；`network.py::_children` 列舉失敗即 RuntimeError；新增子行程對照 `test_connection_check_covers_child_processes` |
| V5（should-fix） | G7-04：`test_worker_dies_with_main_process` 只檢查轉介程式的 PID，沒檢查真正的直譯器 | `ac66cba`：主行程結束前取得 worker 整棵行程樹，逐一確認都已終止 |
| V6（should-fix） | ADR-0024 殘餘未列 shading（含 mesh 串流）、Function、ICCBased 串流，以及影像資料本身的壓縮比（只檢查宣告的寬×高） | ADR-0024 後果殘餘補列 shading（含 mesh）、Function、ICCBased、影像資料壓縮比；§9 U5 同步 |
| V7（備查） | 措辭：ADR §1「超限回 RESOURCE_LIMIT 不是崩潰」只驗證 Python 層配置；ADR §5 不相符的字串 request_id 實際是略過而非視為異常；THREAT_MODEL T2「每種訊息都有畸形輸入測試」主行程端只測 open_document；POSIX limit_self 失敗不中止，ADR §1 未寫 | ADR-0024 §1 註明原生配置失敗未驗證、POSIX 不是 fail closed；§5 改為「request_id 必須是字串或 null，其他字串略過」；THREAT_MODEL T2 改為 worker 端每種請求、主行程端以 open_document 測畸形回應 |
| V8（備查） | 拿掉 CREATE_SUSPENDED 沒有測試抓得到（時間窗本質上難測，靠讀程式確認）；打包後 ActiveProcessLimit 1 未驗證（建議 P8）；S06 sentinel 只在 Windows 有意義；TRIAGE.md f008 列「T1 未同步」已過時；實機腳本以「Up 網卡數＝0」判斷斷網，虛擬網卡可能使其不為 0；G7-05 未檢查 CLI stdout、未 assert worker stderr 檔非空 | §7 補列（暫停建立靠讀程式確認、打包後行程數列 P8、S06 只在 Windows 有意義）；實機腳本改為列出每張網卡狀態（`ac66cba`）；TRIAGE.md f008 列的「T1 未同步」已由 `57fdb4d` 處理（§8 已記）；G7-05 未檢查 CLI stdout 與 worker stderr 檔非空，備查不處理 |
