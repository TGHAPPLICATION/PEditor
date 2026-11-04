# P6 關卡報告：既有規則表格儲存格修改

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段測試在本機 Windows 製作機（GUI 為 offscreen）與 CI 執行，**不是實機證據**。

## 1. 階段／commit／日期

- 階段：P6　分支：`p6-table-cells`　commit：`4cc46d1`（核心：格線推估、cell_targets、plan_cell_edit、格線不變驗證）、
  `81048cc`（UI 與服務層測試）、`c23e1f3`（ADR-0023、證據包與產生腳本 `scripts/p6_evidence.py`）、`2030145`（格線變動偵測測試）、
  `edfe9c8`（跨格文字測試）、`d6438e0`（格線交會判定上限）、`bcdb0e0`（U2：文字層 API 也遵守格判定）、`5f01555`、`c2bd36a`（第一輪核對 Q1–Q4）、`34479a3`、`891c292`、`61ecba2`（第二輪核對 R1–R3）、`c438064`、`222d4ff`、`56dfe3b`（第三輪核對 S1–S5）、`aaec696`（第四輪核對 T1–T4）　日期：2026-11-03～11-04
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
「本機」＝Windows 製作機（GUI 為 offscreen）；「CI」＝CI 待補（第四輪核對處理後推送）。

| 需求 ID | test ID | fixture | 本機 | CI |
| --- | --- | --- | --- | --- |
| G6-01 | `tests/integration/test_edit_cell.py::test_all_supported_cell_cases`（5 組）：目標格格線中線與 manifest 可改動區域 ≤0.5 pt；計畫 ready（B01 模式 A、其餘模式 B）；另存驗證含格線不變；兩引擎擷取目標格為新文字、不含原文；遮罩外差異 ≤0.01% | B01–B05 | PASS | PASS |
| G6-02 | `::test_borders_and_other_cells_unchanged`（5 組）：格線位置、範圍、線寬完全相同；其他格與同格其他行兩引擎擷取相同、像素無超標差異；`::test_rules_check_detects_changed_borders`：拿掉一條線或改線寬時另存前驗證能偵測；`::test_frame_with_inner_lines_clips_region`（2 組，Q1）：外框內含空白數字格或小表格時，可改動區域裁到內層格線左側、長字溢出拒絕、短字可改且另存通過；`::test_manual_box_sees_form_lines`（Q2）：格線在 Form 內時框選跨線拒絕、框在格內可改，另存前比對能偵測 Form 內線寬變動；`::test_lines_drawn_any_way_block_region`（5 組，第二輪 R1、R2）：內層線以填色多邊形、往上凸的曲線、點線、8 pt 粗填色畫時長字溢出拒絕，斜線使該行拒絕，人工框選整個外框也拒絕；`::test_underline_and_nearby_lines_do_not_block`（5 組，第二輪 R3）：填色與描邊底線、刪除線、右側同高的線、下方小框不擋整段替換，另存通過；第三輪 S5 加延伸到右邊的底線、填空線（共 7 組）；`::test_any_drawing_blocks_long_text`（7 組，第三輪 S1–S3）：曲線（控制點折線在格外）、shading 直條、註解外觀、Type3 長線、inline image、方形線帽、粗斜線畫出的東西都擋住長字，曲線與粗斜線使整行拒絕；`::test_fill_over_text_does_not_cut_into_text`（2 組，第三輪 S4）：7 pt 粗刪除線下改字可長過刪除線右緣、底色塊內改字可改，可改動區域不被裁進文字 | B01–B05、測試內樣本 | PASS | PASS |
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
uv run pytest -q                                        → exit 0，455 passed（Windows 製作機，34479a3，第二輪核對補 10 組）
uv run pytest -q                                        → exit 0，466 passed（Windows 製作機，222d4ff，第三輪核對補 11 組）
uv run pytest -q                                        → exit 0，476 passed（Windows 製作機，aaec696，第四輪核對補 10 組）
uv run python scripts/p6_evidence.py reports/P6/evidence → exit 0
```

- P6 新增 70 項測試：`test_edit_cell.py` 55 項（含參數化 46 組）、`test_table_grid.py` 9 項（參數化 3 組）、`test_cell_service.py` 3 項、`test_cell_ui.py` 3 項。
  既有測試只改 `test_analyzer.py`：B06 移出 `DEFERRED`，B 組加驗目標格（收緊，沒有放寬預期）；P5 既有 406 項全數通過。
- **反向驗證**（repo 外的臨時腳本；工作區先提交乾淨，逐一改壞實作、跑對應測試、再以 `git checkout` 還原）：37 項中 36 項被測試抓到，M29 沒有（見表後說明）（M14 為 U2 處理後補做，M15–M20 為第一輪、M21–M26 為第二輪、M27–M32 為第三輪、M33–M37 為第四輪核對處理後補做）——

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
  | M21 | 只填色的路徑不當障礙線（R1 修正前） | `test_lines_drawn_any_way_block_region[fill_polygon]`、`[thick_fill]` |
  | M22 | 曲線只記端點、不記控制點 | `test_lines_drawn_any_way_block_region[curve]` |
  | M23 | 長度 ≤1 pt 的線段不算（R1 修正前） | `test_lines_drawn_any_way_block_region[dotted_segments]` |
  | M24 | 不檢查斜邊（儲存格編輯、呼叫端區域、人工框選三處一起拿掉；任一處都會擋） | `test_lines_drawn_any_way_block_region[diagonal]` |
  | M25 | 細長形狀拆成四邊（不視為一條線） | `test_underline_and_nearby_lines_do_not_block[underline_fill]` |
  | M26 | 底線與刪除線也擋（R3 修正前） | `test_underline_and_nearby_lines_do_not_block` 3 組 |
  | M27 | 不做墨跡檢查 | `test_any_drawing_blocks_long_text` 4 組（shading、註解、Type3、inline image） |
  | M28 | 曲線不細分（改回控制點折線） | `test_any_drawing_blocks_long_text[curve_outside_polyline]` |
  | M29 | 向量的線帽延伸拿掉 | 沒有被抓到：墨跡檢查照樣擋住線帽（多一層防護，同 M24 的性質）；只有 MuPDF 渲染空白的檔案才會只靠向量 |
  | M30 | 與文字重疊的填色形狀不略過（S4 修正前） | `test_fill_over_text_does_not_cut_into_text[thick_strike]`（第一次沒抓到：新文字太短沒碰到刪除線右緣，改成較長的新文字（`56dfe3b`）後重做抓到） |
  | M31 | 沒有底線區（底線、填空線也擋） | `test_underline_and_nearby_lines_do_not_block` 2 組（延伸到右邊的底線、填空線） |
  | M32 | 斜邊不計線寬 | `test_any_drawing_blocks_long_text[thick_diagonal_outside]` |
  | M33 | 墨跡門檻回到 48 | `test_faint_hidden_and_tight_lines_block_long_text` 2 組（淡灰、淡紅影像） |
  | M34 | 不裁註解範圍 | 同上 3 組（圖層 OFF、只在列印顯示、緊貼文字的註解）、`test_annotation_over_text_rejects_and_link_does_not_block` |
  | M35 | 不認緊貼文字的直線 | 同上 `[image_in_margin]` |
  | M36 | 渲染最外圈也看（T4 修正前） | `test_text_near_border_can_grow` 2 組 |
  | M37 | 連結註解也當障礙 | `test_annotation_over_text_rejects_and_link_does_not_block` |

- 第一次在 `d6438e0` 跑全套時超過 600 秒，被 Claude Code 因系統記憶體不足終止（無輸出、不是測試失敗）；2026-11-04 重跑 163 秒、439 passed。
- Q4 第一版檢查區域內所有障礙線，L03 的 8 項既有測試失敗（manifest 區域是字形外框，上下碰到紅框的水平線）；改為只檢查垂直線（直立文字只沿基線延伸）後通過（`c2bd36a`）。
- 第二輪核對處理後第一次反向驗證，M22–M25 沒被抓到：測試樣本不夠嚴（曲線兩端點本身就連成垂直線、新文字與原文共用開頭使改字起點不受左邊界影響）、M23 的改法本身無效、M24 只拿掉一處而另兩處仍會擋；改用往上凸的曲線與整段替換（`891c292`）、修正改法後重做，全部抓到。重做時一度因改動字串不符，cell.py 的暫時改動沒有還原，發現後以 `git checkout` 還原並確認工作區乾淨。
- 第二輪核對者的樣本（c00–c18、d01–d08）以處理後的程式重跑：R1、R2 的樣本長字溢出或拒絕；R3 的 d01–d03、c16、c18 可改，與 `8e1b844` 結果相同（c15 在 `8e1b844` 也拒絕：框內只畫了一半的線使整個框成為合併格，屬結構判定）。
- 第三輪核對處理：`test_lines_drawn_any_way_block_region[curve]` 的預期由 `TEXT_OVERFLOW` 改為 `UNSUPPORTED_LAYOUT`：曲線改為細分折線後，往上凸的曲線穿過該行區域成為斜邊，依 ADR-0023 §2 整行拒絕（行為改變，不是放寬）。第三輪核對者的探針樣本（`probe.py` 13 組、`probe_r3.py` 8 組）以處理後的程式重跑：S1–S3 的長字全部被擋；7 pt 粗刪除線、延伸到右邊的底線、填空線可改；底色塊、比文字長的粗刪除線、文字右側基線高度的 0 寬線、文字內的小直線仍擋（§9 U6）。修改測試時一度以正規表示式誤刪一大段測試（未提交），以 `git checkout` 還原後改用精準替換。
- 第四輪核對處理：M34 的半透明註解（`[annot_transparent]`）沒有單獨被抓到——拿掉註解範圍後，`/CA 0.15` 的黑線與底色相差約 38，仍超過新門檻 24，由墨跡檢查擋下（同 M29 的多一層防護）。
- 本機 pytest 收集階段會印出一次 `Windows fatal exception: access violation`（`pypdfium2` 載入時 faulthandler 回報已處理的例外，P5 報告 §4 已查明，與本段無關）。
- CI：CI 待補（第四輪核對處理後推送）；先前 run [41782916232](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41782916232)（commit `477c058`）、run [41773442853](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41773442853)（commit `6590885`）只改報告，雙平台 466 passed（第四輪核對 T8 補列）；run [41773028292](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41773028292)（commit `2ae6716`）windows-latest 466 passed、macos-15 466 passed（第三輪核對處理後）；run [41767780036](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41767780036)（commit `85c7273`）windows-latest 455 passed、macos-15 455 passed（第三輪核對處理前）；run [41763225080](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41763225080)（commit `ee23f84`）windows-latest 445 passed、macos-15 445 passed（第二輪核對處理前）；run [41758086017](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41758086017)（commit `75a804f`）windows-latest 440 passed、macos-15 440 passed（第一輪核對處理前）；run [41757007669](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41757007669)（commit `37b9767`）windows-latest 439 passed、macos-15 439 passed（U2 前，只作歷史紀錄）。

## 5. 真修改證據

證據包 `reports/P6/evidence/`（`scripts/p6_evidence.py` 於 `c2bd36a` 重產（第一輪核對 Q6），`61ecba2` 再重產（第二輪核對處理後，只有隨機值與浮點尾數不同），`56dfe3b` 再重產（第三輪核對處理後：墨跡檢查以像素為單位，可改動區域縮小約 0.3 pt），`aaec696` 處理後再重產（第四輪核對 T4：渲染最外圈不看，可改動區域回到向量裁切的邊界，放大約 0.1–0.4 pt）；`output.pdf` 不入庫，SHA-256 記於 `summary.json`，trailer `/ID` 隨機，重產後雜湊不同）。
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
| U6 | 第三輪核對處理後的保守行為（ADR-0023 §2、後果）：(a) 底色塊、比文字長的刪除線讓新文字不能長過它們（`8e1b844` 時可以）；(b) 曲線、斜線穿過該行的區域即整行拒絕（圓角框、斜線表頭的格不能改）；(c) 人工框選的判定只用向量，墨跡檢查在規劃時才做；(d) 文字範圍內的非文字墨跡無法和字形區分；(e) MuPDF 渲染空白的 7 份檔只有向量判斷 | 可改的範圍比 `8e1b844` 小；(d)(e) 為殘餘 | **(a)(b)(c) 接受、(d)(e) 列殘餘**（工程師 2026-11-04；ADR-0023 後果、THREAT_MODEL T11 已列） |
| U7 | 第四輪核對處理後的保守行為：除 Link、Popup 外的註解範圍與文字重疊即該行拒絕（螢光筆、包住整格的方框註解、蓋在文字上的表單欄位），不看註解是否顯示 | 這類格不能改；原本可改 | 待工程師決定 |
| U5 | 儲存格 UI 只有 offscreen 證據 | 實機行為未驗證 | **併入 P8 實機驗收**（工程師 2026-11-04） |

## 10. 關卡結果

- **關卡結果：BLOCKED**。G6-01～G6-07 本機全部通過，反向驗證 37 項中 36 項被抓到（M29 由墨跡檢查兜底，§4）；CI 待補（第四輪核對處理後推送）；U1–U6 已由工程師決定並處理、U7 待工程師決定（§9）；已經四輪獨立核對（§11），第一輪 Q1–Q8、第二輪 R1–R3、第三輪 S1–S6、第四輪 T1–T8 已處理；工程師決定做範圍很小的第五輪核對（只確認 T1–T4 修正本身），關卡結果於第五輪後決定。
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

第二輪（2026-11-04，HEAD `d62002c`，聚焦第一輪 Q1–Q4 的修正）：另一個未參與實作、也未做第一輪的 Claude 子代理人核對（暫時腳本與樣本放在 repo 外，工作區乾淨）。
自行驗證屬實：描邊實線、虛線、Form 內的線（含 /Matrix 2 倍縮放、三層巢狀 Form 平移）、q/cm 平移、cm 旋轉 90 度的線，以及外框內小表格，長字都回 `TEXT_OVERFLOW`；
人工框選跨過 Form 內的線拒絕；Q3、Q4 未發現新漏洞（/Rotate 90 裁切正常、基線水平的假設成立）；repo 內支援格 44 行逐一規劃無一被拒；
反向驗證重做 M15、M16、M19 與報告相符；測試數 445（P6 新增 39）、證據包重產一致、§11 處理欄只寫工程師說過的決定；ruff 通過、pytest 445 passed；
CI run 41763225080（`ee23f84`）、41763722255（`d62002c`）雙平台 445 passed。結論「有出入」，**有 1 項 must-fix**：

| # | 內容 | 處理 |
| --- | --- | --- |
| R1（must-fix） | 用非 `re` 的填色多邊形、曲線（`c` 等）或每段 ≤1 pt 的短段畫的格線不算障礙線：外框內 x=120 的內層線以這三種方式畫時，長字計畫 ready、另存通過，線右側新增深色像素 2086 個；整張表用填色多邊形畫時人工框選也能跨格（與 Q2 同類）。THREAT_MODEL T11 的殘餘未揭露 | 工程師決定全部照建議處理（2026-11-04）。`34479a3`：障礙線改取頁面與 Form 內每一個已繪製子路徑的邊（描邊或填色、`re` 或多邊形、曲線取控制點折線），細長形狀（≤6 pt、長度超過 3 倍）視為一條線，每段都算、不設最短長度；人工框選與另存前比對同樣改用；測試 `test_lines_drawn_any_way_block_region`（M21–M23）；ADR-0023 §1、THREAT_MODEL T11 補寫 |
| R2（should-fix） | 斜線表頭（格內對角線）不受限制，新文字可穿過斜線、另存通過 | `34479a3`：斜邊另存，裁切後的可改動區域、人工框選範圍、呼叫端區域內有斜邊即拒絕；測試同上 `[diagonal]`（M24） |
| R3（should-fix） | `clip()` 過度拒絕（相對 `8e1b844` 回歸）：底線（細填色或描邊）、刪除線、文字右側同高度的水平線、文字正下方不相連的小框，都被判「線穿過文字」而拒絕；UI 點格內文字一律走儲存格編輯，這類文字在 UI 改不了（main 可經 P4 文字路徑改）。repo 內 fixture 不受影響 | `34479a3`：裁切依線與文字的相對位置——與文字同高且水平重疊的水平線（底線、刪除線）不擋、只有垂直線穿過文字才拒絕、其餘裁向線所在的一側；測試 `test_underline_and_nearby_lines_do_not_block`（M25、M26）；核對者樣本 d01–d03、c16、c18 與 `8e1b844` 結果相同 |
| R4（備查） | Q3、Q4 驗證合理；殘餘（P2 既有）：溢出只檢查基線起訖點，字形墨跡可越過區域邊 ≤2 pt；粗於 6 pt 的填色框線不算障礙線；影像畫的線未測 | 殘餘列入 ADR-0023 後果與 THREAT_MODEL T11：影像畫的線不算障礙線、字形墨跡可越過區域邊 ≤2 pt；粗於 6 pt 的填色框線已由 R1 的處理涵蓋（四邊都算） |
| R5（備查） | 報告與證據一致（測試數、§3、證據包、CI、§11 處理欄、規則、diff 範圍） | 不需處理 |

第三輪（2026-11-04，HEAD `a0f64b7`，聚焦第二輪 R1–R3 的修正）：另一個未參與實作、也未做前兩輪的 Claude 子代理人核對（暫時腳本與樣本放在 repo 外，工作區乾淨）。
自行驗證屬實：白線、虛線、極小傾斜、文字剪裁加 `sh` 等畫法正確擋下；反向驗證重做 M21、M24（三處一起）、M26 與報告相符（只拿掉 cell.py 一處時由 edit.py 再擋，與 §4 說明一致）；
測試數 455（P6 新增 49）、CI run 41767780036（`85c7273`）與 41768222738（`a0f64b7`）雙平台 455 passed、證據包只有隨機值不同、§11 第二輪處理欄與 commit 相符；
`d62002c..a0f64b7` 測試只有新增；`pyproject.toml`、`uv.lock` 未改；ruff 通過、pytest 455 passed。結論「有出入」，**有 must-fix**：

| # | 內容 | 處理 |
| --- | --- | --- |
| S1（must-fix） | 曲線以控制點折線表示並不保守：開放曲線不一定碰到控制點折線（樣本 `200 245 m 400 245 400 60 200 60 c S`，折線的垂直邊在格外），新文字穿過曲線、計畫 ready、另存通過；人工框選避開折線也一樣。ADR-0023、THREAT_MODEL T11、報告「偏保守」的說法不成立 | 工程師決定全部照建議處理（2026-11-04）。`c438064`：曲線細分成 16 段折線；ADR-0023、THREAT_MODEL T11 刪除「偏保守」；儲存格編輯另加墨跡檢查；測試 `test_any_drawing_blocks_long_text[curve_outside_polyline]`（M28） |
| S2（must-fix，或列殘餘） | 不是路徑的畫法不算障礙線：`sh`（剪裁加 shading 畫出的直條）、註解外觀串流畫的線、Type3 字形 CharProc 畫的長線（字形外框很小），新文字都能穿過、另存通過，人工框選也判支援；殘餘清單只列了影像 | `c438064`：儲存格編輯規劃時以 MuPDF 渲染該頁、以墨跡再裁一次可改動區域，涵蓋 shading、註解外觀、Type3、影像等任何畫法；測試 `test_any_drawing_blocks_long_text`（shading、註解、Type3、inline image；M27）。人工框選的判定仍只用向量（§9 U6） |
| S3（should-fix） | 忽略筆畫幾何：方形／圓形線帽沿長度方向延伸的部分、粗斜線的寬度（只看中心線）不算，新文字可畫進線帽或粗斜線 | `c438064`：描邊的線兩端外擴半個線寬（線帽）、斜邊判斷計入線寬；測試 `[square_cap]`、`[thick_diagonal_outside]`（M32；M29 由墨跡檢查兜底，未被抓到，§4） |
| S4（should-fix） | R3 仍有過度拒絕：只填色形狀的零寬邊在 `clip()` 判錯位置（`beside` 對零寬水平邊恆為 0），7 pt 粗刪除線、較長的粗刪除線、文字底色塊都被裁到文字內而回 `TEXT_OVERFLOW`（`8e1b844` 皆 ready）；方向安全但理由錯，且違反「刪除線不擋」 | `c438064`、`56dfe3b`：範圍判斷含端點；只填色的形狀與文字重疊時向量判斷略過其邊（`clip` 與呼叫端區域檢查），交給墨跡檢查；測試 `test_fill_over_text_does_not_cut_into_text`（M30）。底色塊、比文字長的刪除線仍讓新文字不能長過它們（§9 U6） |
| S5（備查） | 相對 `8e1b844` 的其他行為改變：「Name:」後同高的填空線、文字右側基線高度的 0 寬線現在 `TEXT_OVERFLOW`，文字範圍內的小直線現在 `UNSUPPORTED_LAYOUT`；多半合理，建議 ADR 註明填空線行為 | `222d4ff`：文字外框下方 1/4 為底線區，其中的水平線（底線、填空線）不擋左右延伸，向量與墨跡判斷一致；填空線、延伸到右邊的底線恢復可改（與 `8e1b844` 相同）；測試加 2 組（M31）；ADR-0023 §2 註明 |
| S6（備查） | 效能：24k 條曲線 `inspect_page` 0.52 s、峰值 33 MB（`8e1b844` 0.34 s、7 MB），可接受；超過 `MAX_PAINTED_POINTS` 截斷後，給 `editable_region` 的 `plan_text_edit` 回 `RESOURCE_LIMIT`（UI 不帶區域不受影響），輪廓文字、地圖頁較易觸發，建議 ADR 註明 | ADR-0023 §1 註明曲線細分後的點也計入上限、截斷時給 `editable_region` 的 `plan_text_edit` 回 `RESOURCE_LIMIT` |
| S7（備查） | M24 只拿掉 cell.py 一處不會被抓到（edit.py 再擋），與 §4 說明一致 | 不需處理 |

第四輪（2026-11-04，HEAD `477c058`，聚焦墨跡檢查與第三輪處理；核對中途遇到用量上限暫停，重置後繼續，先前進度未保留而全部重做）：
另一個未參與實作、也未做前三輪的 Claude 子代理人核對（暫時腳本與樣本放在 repo 外，工作區乾淨）。
自行驗證屬實：0.1 pt、0.05 pt、0 寬線、灰色 0.75 的線、/Rotate 90／270 加 CropBox 偏移、OFF 的 OCG 裡的向量線都擋下；
反向驗證重做 M27、M29（未抓到，與報告一致）、M31 相符；`[curve]` 預期改為 `UNSUPPORTED_LAYOUT` 的理由成立（更嚴、不是放寬）；
45 份 fixture 回歸掃描：文字計畫 266 筆與 `8e1b844` 無差異，儲存格計畫 208 筆只有 L03 2 筆不同（T4）；§4、§9 U6、§11 第三輪處理欄一致；
相依未改；ruff 通過、pytest 466 passed；CI run 41773028292、41773442853、41782916232 雙平台 466 passed。結論「有出入」，**有 must-fix**：

| # | 內容 | 處理 |
| --- | --- | --- |
| T1（must-fix，或列殘餘） | 淡色、半透明的線不算墨跡（`INK_TOL = 48`）：以註解外觀畫的灰 0.82、淡紅、黑線加 `/CA 0.15` 的直線，長字 ready、另存通過，新文字穿過線（向量畫的淺灰線本來就會被向量判斷擋下） | 工程師決定全部照建議處理（2026-11-04）。`aaec696`：註解範圍一律當障礙（不靠渲染）；墨跡門檻 48 → 24；與底色相差 ≤24 的極淡線條列殘餘（ADR-0023 後果、THREAT_MODEL T11）；測試 `test_faint_hidden_and_tight_lines_block_long_text`（淡灰、淡紅影像、半透明註解；M33、M34） |
| T2（must-fix） | MuPDF 不畫、其他閱讀器或列印會出現的內容：註解帶 `/OC`（OCG 預設 OFF）、註解 `F=36`（NoView＋Print），墨跡檢查看不到，長字 ready、另存通過，PDFium 一般渲染或列印渲染可見新字壓過黑線；不屬已列殘餘 (e) | `aaec696`：除 Link、Popup 外所有註解的範圍不看旗標與 /OC 一律當障礙，與文字重疊即拒絕；測試同上 `[annot_oc_off]`、`[annot_print_only]`、`test_annotation_over_text_rejects_and_link_does_not_block`（M34、M37）；新增保守行為列 §9 U7 |
| T3（should-fix） | 文字外框外擴 1 pt 內的直線（以註解或 inline image 畫、從格頂到格底）不算墨跡，新字穿過；向量畫的同樣線會被裁；不屬已列殘餘 (d)（那是文字範圍內） | `aaec696`：外擴 1 pt 內墨跡佔文字列至少一半、又延伸到文字列外的欄當作直線；註解畫的由註解範圍擋；測試 `[image_in_margin]`、`[annot_in_margin]`（M35、M34） |
| T4（should-fix） | L03 回歸（過度拒絕）：文字外框貼近紅框內緣，紅框反鋸齒落在渲染範圍第 0 列與最後一列，左右掃描把每一欄都當成墨跡，右界被裁在文字右緣＋1 pt；L03 格內加長 1 字或 3 字在 `8e1b844` ready、現在 `TEXT_OVERFLOW`，UI 也改不了；文字貼近格線的格都會中 | `aaec696`：渲染範圍最外圈的列與欄不看；L03 格內加長 1 字、3 字恢復可改（與 `8e1b844` 相同）；測試 `test_text_near_border_can_grow`（M36） |
| T5（備查） | 底線區的墨跡與向量判斷不一致：從下方伸進文字下方 1/4 的直條，以 inline image 畫時不擋、以向量畫時擋；底線區的小方塊不擋（符合 S5 設計，但可能壓到下伸部） | ADR-0023 後果、THREAT_MODEL T11 註明底線區可能壓到下伸部 |
| T6（備查） | 曲線細分讓表格偵測上限更早觸發：任意位置有隨機曲線時，`8e1b844` 20,000 條仍偵測得到，HEAD 約 6,000 條（7,000 條）即無格；建議 ADR 補實際數字 | ADR-0023 §1 補實際數字（約 6,000 條） |
| T7（備查） | 效能：每次 `plan_cell_edit` fixture 平均 27 ms（最大 109 ms）、整頁大影像 0.15–0.19 s；`preview_edit` 1.21 s；大影像頁重播 40 筆儲存格編輯 HEAD 36.0 s、`8e1b844` 29.8 s，兩者都達到或超過 30 秒逾時（主因每筆 reopen，既有問題；墨跡檢查多約 20%），replay 沒有筆數上限 | THREAT_MODEL T5 註明重播耗時與 30 秒逾時（同 P3 f008），列 P7 |
| T8（備查） | 報告只引用到 run 41773028292（`2ae6716`），之後 41773442853、41782916232 未列；本機 466 passed 記在 `222d4ff`，`56dfe3b` 改測試參數後本機未重跑（CI 有涵蓋） | §4 CI 補列 41773442853、41782916232；本機於 `aaec696` 重跑全套 |
