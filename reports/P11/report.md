# P11 關卡報告：頁面上的半透明編輯框（ADR-0032）

> 依 spec §11 範本。CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：P11（2026-11-24 追加）　分支：`p11-inline-edit`（從 `p10-multi-window` 的 `2608f22` 分出，之後合併 P10 的修正）　實作 commit：`e809a1c`；獨立核對修正與本報告定稿在其後的 commit（見 §11）
- 日期：2026-11-24
- 撰寫：Claude Code；審查：工程師；獨立核對：見 §11

## 2. 環境

| 環境 | 版本 | 說明 |
| --- | --- | --- |
| 本工作環境 | Linux 容器、Python 3.13、鎖定相依 | 自動測試；Qt offscreen |
| CI | GitHub Actions windows-latest、macos-15 | run 45318974888（`e809a1c`）、45321818577（`23723be`）、45335585872（`0cd8bd8`）test 與 release 雙平台 success |
| Windows 實機（Windows Sandbox） | 同 P8 | 清單 P11a～P11d PASS（2026-11-24 12:20～13:38 台北時間；工程師自填、無截圖；安裝包推定 `23723be`，標題未記錄） |
| macOS 實機 | — | NOT RUN（ADR-0003） |

## 3. 需求 → test ID → 結果

見 `docs/traceability.md` P11-01～P11-03。

| 需求 | test ID | 結果 |
| --- | --- | --- |
| P11-01 頁面上的編輯框（位置、焦點、Esc／×、移除右側面板） | `tests/gui/test_e2e.py`、`tests/gui/test_layout.py` | PASS（本機 offscreen、CI）；實機 P11a、P11d PASS |
| P11-02 一個「套用」或 Enter 寫回並關閉；IME 組字中不送出；不能改時原因在框內 | `test_e2e.py`、`test_ime.py`、`test_cell_ui.py`、`test_image_ui.py`、`test_fonts.py` | PASS（本機 offscreen、CI）；實機 P11b PASS |
| P11-03 有提醒先在框內顯示、「確認套用」才寫回；改字後重新規劃；告知訊息不問 | `test_e2e.py::test_flow_mode_b_shows_font_replacement`、`::test_flow_changing_text_after_warning_replans`、`::test_info_only_warning_does_not_ask` | PASS（本機 offscreen、CI）；實機 P11c PASS |

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q --deselect tests/integration/test_fixtures.py::test_generator_reproduces_committed_bytes
  → 732 passed, 4 skipped（含 P10 與獨立核對修正）
```

略過的一項是既有的環境差異，CI 雙平台通過。這不是 Windows 實機證據。

## 5. 真修改證據

- 核心寫入流程不變（worker 規劃、寫入後驗證，spec §8）；UI 只把「預覽 → 套用」改為「規劃 → （有提醒先確認）→ 套用」，不再呼叫 `preview_edit`。
- 測試以套用後重新擷取頁面文字確認寫回（`test_flow_apply_without_warnings_writes_back_and_closes`、mode B 流程）；`test_fonts.py` 改為比對套用後頁面的中文字形（不是前後對照圖）。

## 6. 資料完整性與資源／出站紀錄

- 每次套用仍是一筆可 undo／redo 的修改；另存交易不變。沒有新增網路相關程式碼。

## 7. 限制、阻擋、未測項目

- 不再有修改前／修改後對照圖；改錯以 Ctrl+Z 復原（工程師決定）。
- 被視為「只是告知」而不詢問的訊息以前綴比對（目前只有「已同步更新結構樹」）；worker 新增提醒時預設會詢問。
- 編輯框高度超過頁面可視範圍時（極小視窗）可能部分被裁切。
- 編輯框開著時不做放大後的高解析度重新渲染（關閉後才做），放大時頁面暫時較模糊。
- macOS 實機 NOT RUN（ADR-0003）。

## 8. 安全審查

- 不涉及 worker、IPC、parser；THREAT_MODEL 不需更新。
- `/vuln-scan`、`/triage`：NOT RUN（不在 CLAUDE.md 的 P11 時點）；改由獨立子代理人核對（§11）。

## 9. 不確定性與人工確認項目

| # | 內容 | 處理 |
| --- | --- | --- |
| U1 | spec §P4 的「前後對照」由 ADR-0032 取代 | 工程師已決定（2026-11-24） |
| U2 | 實機安裝包版本依結果時間推定 | 工程師確認 |
| U3 | 獨立核對修正（`b5c74b3`：處理中 Esc、延後渲染、縮放重新放置、失敗後不全選）在實機測試之後，只有自動測試與 CI 證據 | 下次實機一併確認 |

## 10. 關卡結果

- **PASS（Windows）**：自動化、CI 雙平台、Windows 實機 P11a～P11d 與獨立核對完成。macOS 實機 NOT RUN（ADR-0003）。

## 11. 獨立核對紀錄

- 2026-11-24，未參與實作的子代理人（只讀）核對 `p10-multi-window..p11-inline-edit` 與報告。確認：改字、換行、換圖都會讓舊計畫失效；undo／redo、換頁、開檔清除選取並關閉編輯框；
  忙碌時重複觸發與 IME 組字中 Enter 被擋下；刪除的前後對照與浮動面板測試有 ADR-0032 理由，修改後的測試仍驗證寫回結果。
  指出並已修正：
  - （中）處理中焦點在編輯框時按 Esc，編輯框的 Esc 與「取消」衝突、兩者都不執行（G4-04）→ 處理中停用編輯框的 Esc（`test_escape_while_busy_cancels`，移除修正時此測試失敗）。
  - （低）放大後 300 ms 的背景重新渲染會停用輸入欄、打斷組字 → 編輯框開著時延後到關閉後（`test_sharper_render_waits_until_editor_closes`，移除修正時失敗）。
  - （低）視窗大小改變時未重新放置編輯框 → 補 `resizeEvent`；失敗後回到輸入欄會全選、下一鍵覆蓋整段 → 只在剛開啟時全選。
  - 測試缺口：縮放後位置的斷言幾乎永遠成立 → 改為檢查緊鄰選取內容與縮窄視窗後仍在可視範圍；補多行格換行、換圖後不沿用待確認計畫的測試。
  - 文件：G4-07、G5-07 仍寫前後對照；P11-02 少列 `test_fonts.py`；traceability 仍寫實機待驗；§11 待填 → 已改正。
- 定稿後：ruff exit 0；pytest 732 passed、4 skipped（略過既有環境差異 1 項）。
