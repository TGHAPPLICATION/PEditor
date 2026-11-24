# P10 關卡報告：多開視窗、檔案總管右鍵開啟與預設程式（ADR-0030、ADR-0031）

> 依 spec §11 範本。CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：P10（2026-11-24 追加）　分支：`p10-multi-window`　實作 commit：`7b832dd`～`a8de098`；獨立核對修正與本報告定稿在其後的 commit（見 §11）
- 日期：2026-11-24
- 撰寫：Claude Code；審查：工程師；獨立核對：見 §11

## 2. 環境

| 環境 | 版本 | 說明 |
| --- | --- | --- |
| 本工作環境 | Linux 容器、Python 3.13、鎖定相依 | 自動測試；Qt offscreen |
| CI | GitHub Actions windows-latest、macos-15 | 各 commit test 與 release 雙平台 success（例：run 45314774904 `42d3e6b`、45321818577 `23723be`、45335585872 `0cd8bd8`）；Inno Setup 6.7.1 |
| Windows 實機（Windows Sandbox） | 同 P8 | 清單 P10a～P10f PASS（2026-11-24 10:26～13:59 台北時間；工程師自填、無截圖）。測試用安裝包為 `p11-inline-edit` 分支建置（含 P10），見 §9 U1 |
| macOS 實機 | — | NOT RUN（ADR-0003） |

## 3. 需求 → test ID → 結果

| 需求 | test ID | 結果 |
| --- | --- | --- |
| P10-01 草稿跨視窗鎖定（另一視窗使用中的草稿不列出、不能刪；全部結束後可復原） | `tests/unit/test_drafts_multi.py`（含跨行程鎖）、既有 `test_drafts*` | PASS（本機、CI）；實機 P10b PASS |
| P10-02 開新視窗（Ctrl+N）；標題顯示檔名與未另存「 *」；不在選單列重複；另存後顯示新檔名 | `tests/gui/test_multi_window.py` | PASS（本機 offscreen、CI）；實機 P10a、P10f PASS |
| P10-03 右鍵「用 PEditor 開啟」與「開啟方式」（HKCU、卸載移除、不自行改預設）；`PEditor.exe <檔案>`；完成頁選用「設為 PDF 預設程式」 | `tests/gui/test_shell_open.py`（參數、啟動開檔、機碼與 [Code] 中文靜態檢查） | PASS（本機、CI 建置）；實機 P10c、P10d、P10e PASS |

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q --deselect tests/integration/test_fixtures.py::test_generator_reproduces_committed_bytes
  → 724 passed, 4 skipped（p10-multi-window，含獨立核對修正）
```

略過的一項是既有的環境差異（fixture 位元組重現），本環境的 main 上也失敗，CI 雙平台通過。這不是 Windows 實機證據。

## 5. 真修改證據

不適用（本段不改 PDF 編輯核心；開檔仍經 worker，ADR-0004）。

## 6. 資料完整性與資源／出站紀錄

- 草稿：每份草稿以 OS 檔案鎖（Windows `msvcrt.locking`、POSIX `fcntl.flock`）標示使用中；行程結束（含強制結束）時 OS 釋放鎖，草稿照常可復原。
- 機碼只寫 `HKCU\Software\Classes\…`、`HKCU\Software\PEditor\Capabilities`、`HKCU\Software\RegisteredApplications`，卸載時移除；不寫 `UserChoice`、不改預設程式。
- 沒有新增網路相關程式碼（`tests/security/test_offline_guard.py` 通過）。完成頁勾選框只開啟本機 Windows 設定（`ms-settings:`）。

## 7. 限制、阻擋、未測項目

- Windows 11 新版右鍵選單第一層只看得到「開啟方式 → PEditor」；「用 PEditor 開啟」在「顯示更多選項」（不做 IExplorerCommand，ADR-0031 §4）。
- 以右鍵開檔啟動時不詢問復原草稿，留到下次一般啟動。
- 「設為預設程式」直接開到 PEditor 頁面需 Windows 11 較新版本；舊版開到一般預設應用程式頁。
- macOS：右鍵／「打開檔案」事件不在範圍；實機 NOT RUN（ADR-0003）。

## 8. 安全審查

- THREAT_MODEL T13 補充（草稿跨行程鎖）。命令列檔案參數視為不可信輸入，走既有開檔檢查，錯誤訊息不含路徑（`test_startup_bad_file_shows_error_without_path`）。
- `/vuln-scan`、`/triage`：NOT RUN（不在 CLAUDE.md 的 P10 時點，為節省成本未執行）；改由獨立子代理人核對（§11）。

## 9. 不確定性與人工確認項目

| # | 內容 | 處理 |
| --- | --- | --- |
| U1 | 實機測試的安裝包來自 `p11-inline-edit`（含 P10 與 P11），不是 `p10-multi-window` 單獨建置；依結果時間推定：P10a、P10b 用 `7b832dd`（當時選單列右側仍有檔名，之後工程師要求拿掉），P10c 用 `42d3e6b` 之後的版本，P10d、P10e 用 `23723be`，P10f 用 `0cd8bd8`。標題版本號未記錄 | 工程師確認 |
| U2 | 完成頁勾選框中文先前顯示為方框或問號；改為碼位組成並換字型後實機 P10e PASS，原因（解碼或字型）未個別確認 | 已記錄 |
| U3 | `a8de098` 是 `0cd8bd8` 的 cherry-pick（讓 P10 分支自足），實機測的是 `0cd8bd8` | 已記錄 |
| U4 | 取得草稿鎖失敗（極罕見：新草稿編號剛好被另一行程持有）時不提示，該草稿不受跨視窗保護 | 低，已記錄未修 |
| U5 | 以「-」開頭的相對檔名會被當成選項；檔案總管一律傳絕對路徑，不影響右鍵開啟 | 低，已記錄未修 |
| U6 | PR #19 的 CI（`39fb4c3`）windows-latest 兩次 test 中一次 `test_no_listening_sockets` 失敗：列出 214 筆系統服務的 socket（pid 948、3984 等）。原因是測試輔助程式以父 pid 建行程樹，Windows 不改掛孤兒行程，父 pid 被重用時（wininit、csrss 的父行程 smss 早已結束）整串系統服務被誤認為測試行程的子孫。修正：建立時間早於父行程者不算子行程（`tests/security/network.py`），不是放寬檢查；同一 commit 另一次 windows test 通過 | 已修正，重跑 CI |

## 10. 關卡結果

- **PASS（Windows）**：自動化、CI 雙平台、Windows 實機 P10a～P10f 與獨立核對完成。macOS 實機 NOT RUN（ADR-0003）。

## 11. 獨立核對紀錄

- 2026-11-24，未參與實作的子代理人（只讀）核對 `main..p10-multi-window` 與報告。確認：跨行程鎖（`msvcrt.locking` 鎖位置 0、空檔可鎖、解鎖前 `lseek(0)`；
  關閉時先刪草稿、`finally` 放鎖）、purge 略過使用中草稿、命令列檔案走 worker、無網路模組、標題只顯示檔名、機碼全在 HKCU 且 `"%1"` 加引號、
  卸載移除、不寫 `UserChoice`、`[Code]` 碼位組成的中文逐字正確。
  指出並已修正：
  - （低）兩個視窗可同時復原同一份草稿 → 復原前先取得草稿鎖，取不到就拒絕（`test_recover_refused_while_other_window_holds_draft`）。
  - （低）Ctrl+N 沒有測試 → 補於 `test_new_window_spawns_process`。
  - 報告不一致：§10 寫核對完成但 §11 待填、traceability 仍寫實機待驗、測試數是在 P11 分支跑的 → 已改正（本節、§4、traceability）。
  - 未修（低，§9 U4、U5）：取鎖失敗不提示；「-」開頭的相對檔名。
