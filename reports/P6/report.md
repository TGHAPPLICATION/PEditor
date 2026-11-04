# P6 關卡報告：既有規則表格儲存格修改

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段測試在本機 Windows 製作機（GUI 為 offscreen）與 CI 執行，**不是實機證據**。

## 1. 階段／commit／日期

- 階段：P6　分支：`p6-table-cells`　commit：`4cc46d1`（核心：格線推估、cell_targets、plan_cell_edit、格線不變驗證）、
  `81048cc`（UI 與服務層測試）、`c23e1f3`（ADR-0023、證據包與產生腳本 `scripts/p6_evidence.py`）、`2030145`（格線變動偵測測試）、
  `edfe9c8`（跨格文字測試）、`d6438e0`（格線交會判定上限）、`bcdb0e0`（U2：文字層 API 也遵守格判定）、`5f01555`、`c2bd36a`（第一輪核對 Q1–Q4）　日期：2026-11-03～11-04
- 只改報告、traceability、THREAT_MODEL 或 CI 紀錄的 commit 依 P4 慣例不列。
- 撰寫：Claude Code；審查：待工程師；獨立核對：待（CLAUDE.md：由未參與實作的子代理人核對）
- 輸入：spec v1.1 P6／G6／§4／§7／§8、ADR-0001～0022（重點 ADR-0013 的 B06 延後項目）、manifest B01–B08、
  `docs/traceability.md` 預登記的 G6-01～G6-04、P5 報告 §10（下一段可開始：是）
- S1／S2 工程師決定（2026-11-03「照建議」，ADR-0023）：
  1. 多行格一次只改一行（`line_index`），不換行、不重排；
  2. 空白格拒絕；
  3. 人工選格可用，但仍經能力判定（不能有線穿過、不能跨格或碰到合併格、文字須完整在框內），合併格一律拒絕；
  4. 含最小版 UI。
- §9 U1–U5 工程師決定（2026-11-04「照建議」）：U1 接受；U2 收緊——`plan_text_edit` 改到不支援格內或跨格的文字也拒絕（`bcdb0e0`）；U3 接受（先復原再改）；U4 接受（不在 MVP 範圍）；U5 併入 P8 實機驗收。
- S1 實測：P2 引擎在給定 manifest 可改動區域時已能改 B01–B05（模式 A／B，另存驗證通過），P6 的工作是表格結構。

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；PySide6 6.11.2；fontTools 4.66.0；pypdfium2 5.13.0、Pillow 13.0.0（只在測試）；Noto Sans TC（ADR-0008） |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest x64 | GitHub 標準 runner | 套件同上（`uv.lock`）；offscreen |
| CI macos | macos-15 arm64 | GitHub 標準 runner | 套件同上（`uv.lock`）；offscreen |

相依沒有變更（`uv.lock`、`pyproject.toml` 未改）；fixture 未重產。

## 3. 需求 → test ID → fixture／hash → 結果

fixture hash（前 12 碼）：B01 `1a409bb195b5`、B02 `7861dc6039a9`、B03 `74bd86c71d2c`、B04 `db65ca0699c0`、B05 `e6cb11e5a755`、B06 `ef732af2d87c`。
「本機」＝Windows 製作機（GUI 為 offscreen）；「CI」＝run [41763225080](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41763225080)（commit `ee23f84`）windows-latest 445 passed、macos-15 445 passed。

| 需求 ID | test ID | fixture | 本機 | CI |
| --- | --- | --- | --- | --- |
| G6-01 | `tests/integration/test_edit_cell.py::test_all_supported_cell_cases`（5 組）：目標格格線中線與 manifest 可改動區域 ≤0.5 pt；計畫 ready（B01 模式 A、其餘模式 B）；另存驗證含格線不變；兩引擎擷取目標格為新文字、不含原文；遮罩外差異 ≤0.01% | B01–B05 | PASS | PASS |
| G6-02 | `::test_borders_and_other_cells_unchanged`（5 組）：格線位置、範圍、線寬完全相同；其他格與同格其他行兩引擎擷取相同、像素無超標差異；`::test_rules_check_detects_changed_borders`：拿掉一條線或改線寬時另存前驗證能偵測；`::test_frame_with_inner_lines_clips_region`（2 組，Q1）：外框內含空白數字格或小表格時，可改動區域裁到內層格線左側、長字溢出拒絕、短字可改且另存通過；`::test_manual_box_sees_form_lines`（Q2）：格線在 Form 內時框選跨線拒絕、框在格內可改，另存前比對能偵測 Form 內線寬變動 | B01–B05、測試內樣本 | PASS | PASS |
| G6-03 | `::test_cell_overflow_rejected`（2 組）：60 字新文字回 `TEXT_OVERFLOW` | B01、B04 | PASS | PASS |
| G6-04 | `::test_manual_cell_requires_assessment`：B06 合併格（1×2）偵測與框選都拒絕、框選跨兩格拒絕；無框線表格框選切到文字、有線穿過拒絕，框好可改、溢出仍拒絕；`::test_text_crossing_border_rejected`；`::test_text_api_respects_cell_judgement`（U2：`plan_text_edit` 改 B06 合併格或跨格文字拒絕、支援格照常）；`tests/unit/test_table_grid.py`（9 項：規則網格與線寬、細填色矩形、合併格與未封閉區域、斜線／Form／底色不算、上限、解譯器記錄、框選判定）；`test_analyzer.py::test_capability_matches_manifest`（B06 移出 `DEFERRED`，B 組改驗目標格判定與範圍）；`::test_frame_keeps_previous_text_edits`（Q3）：頁框內有旋轉文字時只擋那一行，其他文字的 `plan_text_edit` 與儲存格編輯照常；同列間距大的兩段分成兩個片段、可改動區域不含另一段；`::test_text_api_region_cannot_cross_borders`（Q4）：呼叫端區域有垂直格線穿過拒絕、manifest 格範圍照常 | B01–B06、測試內樣本 | PASS | PASS |
| G6-05 | `::test_multiline_cell_line_layout`（B02、B05 第 2 行）：只改指定行、可改動區域不含另一行、另一行擷取不變、行號超出回 `INVALID_REQUEST`；`::test_empty_cell_rejected` | B02、B05、測試內樣本 | PASS | PASS |
| G6-06 | `tests/integration/test_cell_service.py`（3 項：預覽不提交、undo／redo、worker 重啟重播、另存；復原草稿；人工框選經服務層） | B04、測試內樣本 | PASS | PASS |
| G6-07 | `tests/gui/test_cell_ui.py`（3 項：點格內文字改為儲存格編輯並套用；多行格行選擇、合併格顯示原因；手動選格拉框、套用，框到兩格顯示原因） | B04、B05、B06、測試內樣本 | PASS（offscreen） | PASS |

實機：G6 不在 ADR-0003 規定須實機的關卡（G4、G7、G8）；儲存格 UI 實機操作 NOT RUN（§7）。

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q                                        → exit 0，437 passed（Windows 製作機，81048cc）
uv run pytest -q                                        → exit 0，439 passed（Windows 製作機，d6438e0）
uv run pytest -q                                        → exit 0，440 passed（Windows 製作機，bcdb0e0，U2 補 1 項）
uv run pytest -q                                        → exit 0，445 passed（Windows 製作機，c2bd36a，第一輪核對補 5 項）
uv run python scripts/p6_evidence.py reports/P6/evidence → exit 0
```

- P6 新增 39 項測試：`test_edit_cell.py` 24 項（含參數化 16 組）、`test_table_grid.py` 9 項（參數化 3 組）、`test_cell_service.py` 3 項、`test_cell_ui.py` 3 項。
  既有測試只改 `test_analyzer.py`：B06 移出 `DEFERRED`，B 組加驗目標格（收緊，沒有放寬預期）；P5 既有 406 項全數通過。
- **反向驗證**（repo 外的臨時腳本；工作區先提交乾淨，逐一改壞實作、跑對應測試、再以 `git checkout` 還原）：20 項全部被測試抓到（M14 為 U2 處理後補做，M15–M20 為第一輪核對處理後補做）——

  | # | 改壞的內容 | 失敗的測試 |
  | --- | --- | --- |
  | M1 | 合併格不拒絕 | `test_manual_cell_requires_assessment`、`test_capability_matches_manifest` |
  | M2 | 共用邊沒有線也不合併網格 | `test_manual_cell_requires_assessment`、`test_merged_cell_and_open_region` |
  | M3 | 不把細填色矩形當格線（Word） | B03、B05 的 G6-01／G6-02、`test_multiline_cell_line_layout[B05]`、`test_thin_filled_rects_same_as_strokes` |
  | M4 | 跨格文字不拒絕 | `test_text_crossing_border_rejected`（第一次反向驗證時沒有被抓到，補這項測試後重做） |
  | M5 | 空白格不拒絕 | `test_empty_cell_rejected`、`test_assess_box[box2-False]` |
  | M6 | 可改動區域為整個格內緣（含同格其他行） | `test_multiline_cell_line_layout` 2 組 |
  | M7 | 另存不比對格線 | `test_rules_check_detects_changed_borders` |
  | M8 | 人工選格不檢查穿過的線 | `test_manual_cell_requires_assessment` |
  | M9 | 人工選格不檢查合併格與多格 | `test_manual_cell_requires_assessment` |
  | M10 | 重播不分派儲存格計畫 | `test_cell_service.py` 3 項 |
  | M11 | 草稿不接受 `op: cell` | `test_cell_draft_recovery` |
  | M12 | Form 內的線也當格線 | `test_diagonal_form_and_thick_rects_ignored` |
  | M13 | 不檢查格線交會判定上限 | `test_limits` |
  | M14 | `plan_text_edit` 不檢查儲存格判定（U2 修正前的行為） | `test_text_api_respects_cell_judgement` |
  | M15 | 可改動區域不裁到障礙線（Q1 修正前） | `test_frame_with_inner_lines_clips_region` 2 組 |
  | M16 | 障礙線不含 Form 內的線（Q2 修正前） | `test_manual_box_sees_form_lines` |
  | M17 | 格內不支援的文字使整格拒絕（Q3 修正前） | `test_frame_keeps_previous_text_edits` |
  | M18 | 同一列不依間距分段（Q3 修正前） | `test_frame_keeps_previous_text_edits` |
  | M19 | 呼叫端區域不檢查格線（Q4 修正前） | `test_text_api_region_cannot_cross_borders` |
  | M20 | 另存比對不含障礙線（Q2 修正前） | `test_manual_box_sees_form_lines` |

- 第一次在 `d6438e0` 跑全套時超過 600 秒，被 Claude Code 因系統記憶體不足終止（無輸出、不是測試失敗）；2026-11-04 重跑 163 秒、439 passed。
- Q4 第一版檢查區域內所有障礙線，L03 的 8 項既有測試失敗（manifest 區域是字形外框，上下碰到紅框的水平線）；改為只檢查垂直線（直立文字只沿基線延伸）後通過（`c2bd36a`）。
- 本機 pytest 收集階段會印出一次 `Windows fatal exception: access violation`（`pypdfium2` 載入時 faulthandler 回報已處理的例外，P5 報告 §4 已查明，與本段無關）。
- CI：run [41763225080](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41763225080)（commit `ee23f84`）windows-latest 445 passed、macos-15 445 passed；先前 run [41758086017](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41758086017)（commit `75a804f`）windows-latest 440 passed、macos-15 440 passed（第一輪核對處理前）；run [41757007669](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41757007669)（commit `37b9767`）windows-latest 439 passed、macos-15 439 passed（U2 前，只作歷史紀錄）。

## 5. 真修改證據

證據包 `reports/P6/evidence/`（`scripts/p6_evidence.py` 於 `c2bd36a` 重產（第一輪核對 Q6）；`output.pdf` 不入庫，SHA-256 記於 `summary.json`，trailer `/ID` 隨機，重產後雜湊不同）。
每案以 manifest 原文／新文改目標格中含原文的那一行；B06 拒絕。

| 案例 | 目標格（列, 欄, 跨列, 跨欄） | 行 | 模式 | 格線 | 其他格與同格其他行 | 遮罩外差異（MuPDF／PDFium） | 其他格超標像素 | 擷取目標格 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B01 | (1,1,1,1) | 0 | A | 8 條不變 | 擷取相同 | —／0（ADR-0015：MuPDF 空白檔只用 PDFium） | 0 | 兩引擎「21」 |
| B02 | (0,0,1,1) | 1 | B | 5 條不變 | 擷取相同（含第 1 行） | 0／0 | 0 | 兩引擎含「第二行：市政大樓」 |
| B03 | (1,1,1,1) | 0 | B | 8 條不變 | 擷取相同 | 0／0 | 0 | 兩引擎「15」 |
| B04 | (2,1,1,1) | 0 | B | 8 條不變 | 擷取相同 | 0／0 | 0 | 兩引擎「250」 |
| B05 | (1,2,1,1) | 1 | B | 7 條不變 | 擷取相同（含「第一行」） | 0／0 | 0 | 兩引擎含「第貳行」 |
| B06 | (1,0,1,2) 合併格 | — | — | — | — | — | — | 拒絕 `UNSUPPORTED_LAYOUT` |

- 每案另存驗證都通過：完整重寫、無增量歷史、無不可達物件、qpdf 問題數不增、MuPDF 不需修復、新文字可擷取、格線不變（`rules_changed` 為空）。
- 內容差異只在第 1 頁；模式 B 案例資源差異為新增 `/PEditorB1` 字型（P2 模式 B），模式 A（B01）無資源差異。
- 遮罩為 manifest 事前宣告的 `editable_region_pt`（目標格範圍）外擴 2 pt；「其他格」為其他格內緣與同格其他行外框，各內縮 3 像素排除格線邊緣。

## 6. 資料完整性與資源／出站紀錄

- **只改目標行**：可改動區域＝格內緣 × 該行水平帶，不含其他格與同格其他行（M6 反向驗證）；P2 真修改機制不變。
- **格線不動**：另存前比對合併後格線（位置、起訖、線寬到 0.01 pt），不同即拒絕另存（`rules_changed`）。
- **原檔**：不修改（沿用 P3 交易）。**錯誤訊息**：不含路徑或原文。**出站**：新增模組未匯入網路模組（`test_offline_guard` 通過）。
- **資源**：每頁記錄的直線段＋填色矩形 ≤20,000 筆、合併後水平線數×垂直線數 ≤1,000,000、單一表格 ≤10,000 格。量測（本機）：
  - repo 內 43 份 available fixture（排除加密 U02、損壞 S01）共 44 頁，表格偵測合計 0.003 s（解譯 0.076 s）（第一輪核對以 45 份計為 45 頁、0.0021 s；計數範圍不同，第一輪核對 Q8）；
  - 合成的密集網格（10,100 段、2,500 格）0.04 s；
  - 10,000 條水平×10,000 條垂直線：加上限前 8.9 s（每次 `inspect_page` 都會付出），加上限後 0.04 s（不偵測）。

## 7. 限制、阻擋、未測項目

- **實機**：儲存格 UI 實機操作（點選、行選擇、拉框）NOT RUN；macOS 實機 NOT RUN（ADR-0003）。工程師決定併入 P8 實機驗收（U5）。
- **格線偵測範圍**：只認水平、垂直線；旋轉的表格、格線在 Form 內的表格、只有底色沒有線的表格不自動偵測。後兩者在文字位於頁面層級時可用人工選格；框選與可改動區域裁切會檢查 Form 內的線（Q2）。
- **被四邊線框住的文字**（例如 L03 的紅框）也視為 1×1 的格：UI 點選後以框內緣作為可改動區域（§9 U1）。
- **同一行改第二次**：模式 B 改過的行混用原字型與 Noto Sans TC，再改同一行會因 P2 的跨段限制拒絕 `UNSUPPORTED_LAYOUT`（可先復原再改）。
- **文字層 API**：`plan_text_edit` 改到結構上不支援的格（合併格、跨格文字）內的文字時沿用該格的拒絕理由（U2，`bcdb0e0`；Q3 後格內其他文字不支援不影響）；呼叫端給的區域有垂直格線穿過即拒絕（Q4）；`inspect_page` 的文字目標判定本身不變（B06 格內文字仍為 support，判定落在格與計畫）。
- **不擴大範圍**：不做列插刪、合併、跨頁重排、整格多行改寫、空白格補字、匯出 Excel。
- **盲測 B07、B08**：NOT RUN，P8 執行。

## 8. 安全審查

- CLAUDE.md 規定的 vuln-scan／triage 時點是 P1、P2、P3、P7，P6 沒有規定：**NOT RUN**。P7 掃描範圍應包含 `worker/table.py`、`worker/cell.py` 與 content 解譯器新增的路徑記錄。
- 新增的攻擊面：content 解譯器記錄路徑（受 `MAX_RULE_PATHS` 限制）；表格偵測在每次 `inspect_page` 執行（受 `MAX_RULE_PAIRS`、`MAX_TABLE_CELLS` 限制）；
  worker 操作 `plan_cell_edit`、`assess_cell_box`（參數白名單、cell_id 格式、矩形有限數值與順序檢查）。
- `THREAT_MODEL.md` 已更新：T5 加表格偵測工作量上限；T11 加儲存格改字的範圍控制與格線驗證。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | 任何被四邊線框住的文字都視為 1×1 的格（例如 L03 紅框）；UI 點選後改走儲存格編輯，可改動區域變成框內緣（原本 P4 是文字外框） | 框內較長的新文字變得可以放；框外仍擋 | **接受**（工程師 2026-11-04） |
| U2 | `plan_text_edit`（API）仍可改不支援格內的文字（例如 B06），只有 UI 會先判定格 | 經 API 或 CLI 的呼叫者可繞過格判定 | **收緊**（工程師 2026-11-04）：`bcdb0e0` 起 `plan_text_edit` 改到不支援格內或跨格的文字也拒絕，測試 `test_text_api_respects_cell_judgement`（M14） |
| U3 | 同一行模式 B 改過後無法再改同一行（P2 限制） | 需先復原再改 | **接受**（工程師 2026-11-04） |
| U4 | 格線偵測只認水平、垂直線；Form 內與旋轉表格不偵測 | 這類表格不自動偵測；文字在頁面層級時可用人工選格（框選會檢查 Form 內的線，第一輪核對 Q2）；文字也在 Form 內時文字本身即不支援 | **接受**（工程師 2026-11-04；不在 MVP 範圍） |
| U5 | 儲存格 UI 只有 offscreen 證據 | 實機行為未驗證 | **併入 P8 實機驗收**（工程師 2026-11-04） |

## 10. 關卡結果

- **關卡結果：BLOCKED**。G6-01～G6-07 本機全部通過，反向驗證 20 項全部被抓到；run [41763225080](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41763225080)（commit `ee23f84`）windows-latest 445 passed、macos-15 445 passed；U1–U5 已由工程師決定並處理（§9）；已經第一輪獨立核對（§11），Q1–Q8 已處理；待工程師決定是否再做一輪核對與關卡結果。
- **下一段可開始：否**（條件：工程師決定並更新本節）。

## 11. 獨立核對紀錄

第一輪（2026-11-04，HEAD `8e1b844`，範圍 `e8a1ddd..8e1b844`）：未參與實作的 Claude 子代理人核對（暫時腳本與樣本放在 repo 外，工作區乾淨）。
自行驗證屬實：B01–B05 只改目標那一個文字運算子（B01 模式 A 的 `TJ`、B02–B05 模式 B 的 `Tf`／`TJ` 序列），沒有新增 `re f`、`Do` 或點陣化；
以 PyMuPDF `get_drawings` 獨立比對格線前後相同；遮罩外 words 相同、超標像素 0；B06 經 cell_id、人工框選、`plan_text_edit` 都拒絕；
服務層 undo／redo、worker 重啟、草稿復原正確；反向驗證抽驗 M1、M4、M6、M14 與報告相符；測試數 440（P6 新增 34），`test_analyzer.py` 為收緊；
`uv.lock`、`pyproject.toml` 未改；§9 U1–U5 與工程師決定一致；ruff 通過、pytest 440 passed；CI run 41757007669、41758086017、41758629103 皆通過。
結論「有出入」，**有 2 項 must-fix**：

| # | 內容 | 處理 |
| --- | --- | --- |
| Q1（must-fix） | 已偵測的格只看外框四邊有線，不檢查框內有沒有其他格線；外框內含小表格或空白數字格（例如身分證字號格）時，外框格判為支援、可改動區域為整個框寬，新文字可畫進內層格且另存通過（自建樣本重現；人工框選同一範圍則因有線穿過而拒絕，兩條路徑不一致） | 工程師決定全部照建議處理（2026-11-04）。`5f01555`：可改動區域裁到不碰任何障礙線（文字往四周延伸到第一條線為止），有線穿過該行文字即拒絕；測試 `test_frame_with_inner_lines_clips_region`（外框內含空白數字格、小表格；M15）；ADR-0023 §2、THREAT_MODEL T11 修正 |
| Q2（must-fix） | 人工框選與另存前格線比對只看頁面層級的線，看不到 Form 內的格線；格線在 Form 內、文字在頁面層級時，框選跨過 Form 內的線仍判支援，改長字可畫進鄰格且另存通過。ADR-0023 後果與報告 §9 U4 對「Form 內表格可否人工選格」的描述互相矛盾 | `5f01555`：新增障礙線（頁面與 Form 內所有水平、垂直線及 ≤6 pt 細長填色框線），人工框選、可改動區域裁切、另存前比對都用障礙線；測試 `test_manual_box_sees_form_lines`（M16、M20）；ADR-0023 後果與 §9 U4 的描述改為一致 |
| Q3（should-fix） | U2 的 `_cell_blockers` 與 UI「點格內文字一律走儲存格編輯」會擋到 P2／P4 原本可改的文字：頁框內有一段直排或旋轉文字時，整頁文字的 `plan_text_edit` 都被擋（main 上可改）；外框內同一行兩段文字在 UI 被併成一行、儲存格編輯拒絕。repo 內 T／F／L 組沒有回歸 | `5f01555`：格只因結構問題拒絕（合併格、跨格文字、空白格），格內不支援的文字只擋它所在的行；同一列間距大於一個字高的文字分成不同片段；`_cell_blockers` 只看結構問題；測試 `test_frame_keeps_previous_text_edits`（M17、M18） |
| Q4（should-fix） | `plan_text_edit` 由呼叫端給的 `editable_region` 不受格線限制（B01 給整張表範圍，26 字新文字 ready） | `5f01555`、`c2bd36a`：呼叫端給的 `editable_region` 有垂直障礙線穿過即拒絕（只看垂直線：支援的文字都是直立的；第一版看全部線時 L03 既有測試失敗，§4）；測試 `test_text_api_region_cannot_cross_borders`（M19） |
| Q5（should-fix） | §10 寫「反向驗證 13 項」，§4 為 M1–M14 共 14 項 | §10 改為實際項數（現為 M1–M20 共 20 項） |
| Q6（should-fix） | repo 內證據包在 `c23e1f3` 產生，`bcdb0e0` 後 `cells.json` 缺 `text_ids` 欄位（其餘內容重產一致） | `c2bd36a` 後重產證據包（§5） |
| Q7（should-fix） | THREAT_MODEL T11 的 P6 句子插在 P5 句子中間；未提 U2；依 Q1、Q2「不含其他格」目前不成立 | T11 的 P6 句子移到 P5 內容之後並改寫，補 U2、Q1–Q4 |
| Q8（備查） | §6 寫「44 頁 fixture」，核對者數到 45 頁（45 檔中 1 檔無法解譯）；時間數字相符 | §6 註明計數範圍（43 份、44 頁；重新量測 0.003 s） |
| Q9（備查） | 其他自建樣本行為合理：/Rotate 90 與 CropBox 偏移、CTM 放大線寬、合併格、跨格文字、白色線（保守方向）、Form 內表格不偵測 | 不需處理 |
