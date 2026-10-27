# P2 關卡報告：真正文字修改 CLI POC

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：P2　分支：`p2-text-edit`　commit：`c0196b6`（程式，含安全修補）、`674fbb2`（traceability）　日期：2026-10-27
- 撰寫：Claude Code；審查：待工程師；獨立核對：待執行（§11）
- 輸入：spec v1.1 P2／G2／§7／§8.1／§8.2、ADR-0001～0019、manifest（qpdf_warnings 欄位於步驟 4 加入）、
  `tests/fixtures/edit_cases.csv`（E01–E04）、P1 報告 §10 延續條件
- P2 前置分支（已合併 main）：`p2-prep-f003-f008`（P1 U8）、`p2-pillow-13`（ADR-0014）、`p2-u3-pdfium-visual`（ADR-0015）、
  `p2-adr-protocol-codes`（ADR-0016）
- S1／S3 工程師決定（2026-10-22）：標記 PDF 支援並驗證結構樹（ADR-0017，步驟 7 修訂同步 /ActualText）；
  文字編輯政策與模式 B 字型 Noto Sans TC（ADR-0018）；PDFium 小數字寬截斷改以位置驗證（ADR-0019）

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；pypdfium2 5.13.0；fontTools 4.66.0；Pillow 13.0.0；PySide6-Essentials 6.11.2；Noto Sans TC／Noto Serif TC 依 `scripts/fetch_fonts.py` 鎖定 SHA-256 |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest x64 | GitHub 標準 runner | Python 3.13.16；套件同上（`uv.lock`） |
| CI macos | macos-15 arm64 | GitHub 標準 runner | Python 3.13.15；套件同上 |

相依變更：Pillow 12.3.0 → 13.0.0（ADR-0014，前置分支）；fontTools 由 dev 改為執行期相依（版本不變，ADR-0018；`uv.lock` 只改分組）。
視覺基準（`reports/P2/visual_baseline.json`）在 Windows 製作機量測：150 DPI、每通道容許 8/255、遮罩邊界 2 pt。

## 3. 需求 → test ID → fixture／hash → 結果

支援案例（repo 內 18 份，hash 前 12 碼）：T01 `65a4ebca20fe`、T02 `0c25d0dcbb3f`、T03 `51ab60ba6650`、T04 `6c60ba41cf1b`、
T05 `3704edfda119`、T06 `d080361bf9ef`、T07 `eb85f8ac17b3`、T08 `3d5e0046e2c7`、F01 `856059b4cdf1`、F02 `661ad2572758`、
F04 `6dda72bbbb80`、F06 `5bece6ae67bc`、F07 `8a4af4b104d7`、L01 `bc67ee410ef5`、L02 `0e744136f8ca`、L03 `a8b045e2972a`、
L04 `0b854bbe0768`、L05 `1f45125c32db`。拒絕案例：F03 `d0e6918195a0`、F05 `6ba509976fbf`、F08 `7a79c777c6d5`。

除 G2-15（文件審查）與 G2-21（視覺基準，只在 Windows 製作機量測）外，各列環境皆為「本機 Windows、CI 雙平台」；
CI 證據為 run 40442075176 attempt 2（commit `c0196b6`）雙平台 272 passed，各列首次通過的 run 記於 `docs/traceability.md`。
獨立核對後補強的測試（G2-02、G2-04）見 §11。

| 需求 ID | test ID | fixture | 結果 |
| --- | --- | --- | --- |
| G2-01 | `tests/integration/test_edit_text.py::test_all_supported_text_cases`、`::test_supported_case_coverage` | 18 份＋E01–E04 | PASS：22 次操作（模式 A 7＋E01–E04、模式 B 11）；產生來源 pymupdf／reportlab／word／libreoffice；字型 Noto Sans TC、Noto Serif TC、Droid Sans Fallback |
| G2-02 | `test_edit_text.py::test_target_occurrence_replaced_dual_engine`（模式 A 10 案）、`::test_all_supported_text_cases`（18 份＋E02–E04） | 18 份＋E02–E04 | PASS（兩引擎擷取到新文：去空白後子字串比對；目標 occurrence 舊文移除：MuPDF、PDFium 各自計數，PDFium 計數為獨立核對後補） |
| G2-03 | `test_edit_text.py::test_neighbors_and_lines_untouched`、`tests/integration/test_visual.py::test_changed_page_outside_mask_threshold` | L03、L04、L05、T07、F07、T03 | PASS（繪圖／色彩運算子完全相同、無新增覆蓋；目標外文字運算子逐一保留） |
| G2-04 | `test_edit_text.py::test_rejections_leave_files_unchanged`、`::test_mode_b_font_unavailable`、`::test_overflow_rejected`、`::test_unsupported_encoding_rejected_on_edit_path` | F03、F05、F08；T01、F02（溢出） | PASS（F03、F08 GLYPH_MISSING：𠮷 於原字型與 Noto Sans TC 皆缺，磁碟與工作文件位元組不變；F05 編輯路徑 UNSUPPORTED_ENCODING、溢出拒絕後運算子與磁碟 hash 不變，兩者為獨立核對後補；P1 ADR-0013 延後項完成） |
| G2-05 | `test_edit_text.py::test_target_occurrence_replaced_dual_engine`（模式 A 10 案，`font_changes` 為空）、`::test_mode_a_keeps_font_mode_b_removes_old`（模式 B 11 案）、`tests/integration/test_evidence.py::test_operator_diff_evidence` | 模式 A：T01、T02、T08、F01、F04、L02、L03、E02–E04；模式 B：其餘 11 份 | PASS（模式 A 不換字型；模式 B 證明原字型舊字形已不存在並明示字型替換） |
| G2-06 | `test_edit_text.py::test_overflow_rejected`、`::test_stale_plan_and_revision_conflict` | T01（A）、F02（B） | PASS（超框拒絕，不縮字） |
| G2-07 | `test_evidence.py::test_operator_diff_evidence` | 18 份 | PASS |
| G2-08 | `test_evidence.py::test_full_rewrite_no_incremental_history`、`::test_export_refuses_existing_destination_and_bad_path`、`::test_validation_failure_writes_nothing`、`::test_unreachable_count_ignores_only_file_structure_streams`、`tests/integration/test_cli_edit.py` | 18 份 | PASS（/ObjStm、/XRef 結構串流不計入不可達） |
| G2-09 | `test_evidence.py::test_no_new_qpdf_warnings`、`tests/unit/test_manifest.py::test_qpdf_warnings_recorded` | 全部 support | PASS（manifest `qpdf_warnings` 欄位，P0 延續項） |
| G2-10 | `test_visual.py::test_untouched_pages_pixel_identical` | 測試內組合（F04／T02＋T07 第 2 頁） | PASS |
| G2-11 | `test_visual.py::test_changed_page_outside_mask_threshold` | 18 份＋E02–E04 | PASS（T02 PDFium 依 ADR-0019 以位置驗證） |
| G2-12 | `test_visual.py::test_target_bbox_within_half_point` | 18 份＋E02–E04 | PASS（兩引擎） |
| G2-13 | `tests/unit/test_edit_plan.py::test_edit_plan_schema` | — | PASS |
| G2-14 | `test_edit_plan.py::test_target_id_components` | — | PASS |
| G2-15 | 文件審查（`README.md`「限制」節） | — | PASS（不宣稱鑑識級遮蔽） |
| G2-16 | `test_visual.py::test_mupdf_blank_exceptions_fixed` | T01、F01、F02、F05、L02、L03、B01 | PASS（ADR-0015 例外清單固定為 7 份） |
| G2-17 | `tests/integration/test_tagged.py::test_tagged_structure_preserved`、`::test_tagged_actualtext_rejected`、`::test_tagged_actualtext_equal_is_synced` | T05、T06、T08、F06、F07、L04；腳本產生 | PASS（附條件）：結構樹與 MCID 不變；Word 4 份同步 /ActualText（測試以子字串比對）。ADR-0017 修訂要求的「儲存後 /ActualText 完全等於新內容擷取文字」未在產品端驗證；這 4 份的 MuPDF 擷取會讀 /ActualText，字形內容的獨立驗證只有 PDFium（§9 U6） |
| G2-18 | `test_edit_plan.py::test_span_target_resolution`、`tests/integration/test_edit_multi.py` | T01、T08、F04、T04；測試內樣本 | PASS |
| G2-19 | `test_edit_text.py::test_following_glyphs_unmoved`、`test_edit_multi.py::test_multi_operator_change` | F04、E03、T02 | PASS |
| G2-20 | `tests/unit/test_manifest.py::test_edit_cases_locked`、`test_edit_text.py::test_chained_edit_e01_through_worker` | E01–E04 | PASS（實作前鎖定 22 次操作；E01 經 worker 連續編輯） |
| G2-21 | `scripts/p2_visual_baseline.py` → `reports/P2/visual_baseline.json` | 全部 support | PASS（21 次單步操作改動區外超標像素皆為 0，唯 T02 PDFium 見 ADR-0019；維持 §8.2 原門檻） |
| G2-22 | `tests/security/test_p2_scan_regressions.py`（5 項） | 腳本產生 | PASS（P2 安全掃描 3 項回歸，§8） |

G2 各驗收條件：

1. **宣告支援案例 100%、≥20 次操作、3 種來源、2 種繁中字型**：22 次操作全過；4 種來源；繁中字型 Noto Sans TC、Noto Serif TC（另 Droid Sans Fallback）。
2. **目標 occurrence 舊字形移除，新文可搜尋、複製**：兩引擎擷取逐案驗證；只判定目標 occurrence（spec §8.1），不以全檔搜尋驗收。
3. **鄰字、背景、線條不被修改，不靠白底**：內容差異證明只改目標運算子；無新增繪圖運算子；視覺比對改動區 +2 pt 外為 0（T02 PDFium 例外見 ADR-0019）。
4. **不支援、缺字、溢出回理由碼且不變**：GLYPH_MISSING、UNSUPPORTED_ENCODING、TEXT_OVERFLOW、SHARED_RESOURCE_UNSAFE 等拒絕時 revision 不變、工作文件不變（GLYPH_MISSING 與 SHARED_RESOURCE_UNSAFE 以位元組比對，UNSUPPORTED_ENCODING 與 TEXT_OVERFLOW 以運算子比對），磁碟檔 hash 不變。
5. **模式 A 不換字型；模式 B 先移除舊內容**：模式 A `font_policy=keep_original`、資源差異為空；模式 B 原字型的目標字碼已自 content stream 移除，新增一個字型資源並在計畫中明示。

停止條件均未觸發：未使用紅框／新圖層／點陣化；4 種產生來源皆成功；第二引擎（PDFium）擷取皆成功；無「宣稱成功但原文仍在指定內容」。

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q                                        → exit 0，272 passed（Windows 實機，2026-10-27，含 G2-22 的 5 項；獨立核對後補強見 §11）
uv run python scripts/p2_evidence.py reports/P2/evidence → exit 0，21 案（commit 994c452 產生）
```

Windows 本機每次 import pypdfium2 時，faulthandler 會印出「Windows fatal exception: access violation」與堆疊（`pypdfium2/_library_scope.py` 的 `init_lib`）；
這是程式庫初始化時已被處理的例外，行程繼續執行、測試全數通過，非 P2 引入。

CI：run [40442075176](https://github.com/TGHAPPLICATION/PEditor/actions/runs/40442075176)（commit `c0196b6`）**attempt 2** windows-latest 272 passed、
macos-15 272 passed，P0 檢查腳本（含 smoke build）PASS。attempt 1 的 macOS 為 1 failed、271 passed：CI log 被 P0 腳本截斷，看不到失敗的測試名稱，
只看得到兩份 PDF 位元組只差在 /ID 第二元素；「是比對兩次 `working_bytes()` 的測試」是依此推論（本機重現「同秒存檔相同、隔 1.1 秒不同」），
重跑失敗 job 後通過（§9 U3）。修補前：run 40439343547（commit `994c452`）雙平台 267 passed。

## 5. 真修改證據

`reports/P2/evidence/<案例>/`（`scripts/p2_evidence.py` 產生，21 案：18 份 manifest＋E02–E04；E01 為經 worker 的連續編輯，以 G2-20 測試驗證）：

- `plan.json`（EditPlan：模式、實際改動範圍、字型替換、資源變更、警告）、`validation.json`（qpdf、增量歷史、不可達物件、解碼後內容差異、資源差異）、
  `extraction.json`（MuPDF、PDFium 改動前後頁面文字與目標 occurrence 計數）、`compare.png`（目標區域原／新渲染，上 PDFium、下 MuPDF）。
- 彙總 `summary.json`：21 案 `validation_ok` 全為 true；兩引擎皆擷取到新文 21／21；模式 A 10 案、模式 B 11 案。
- `output.pdf` 不入庫（Word fixture 約 4–5 MB），SHA-256 記於 `summary.json`。以腳本重產時內容相同，但 hash 會因 trailer /ID
  （與隨機的 plan_id、document_id）而不同，所以這個 hash 不能用來驗證重產結果（§9 U3）。獨立核對在 HEAD（安全修補之後）重產兩次逐位元組比對：
  21 案差異全落在 /ID；JSON 除 /ID 衍生值與隨機 ID 外與入庫證據相同，證據在修補後仍有效。
- 驗證範圍：`validation.json` 的「沒有非預期變更」涵蓋各頁 content stream 運算子與頁面 /Resources；標記 PDF 的 StructElem /ActualText
  變更只記於 `plan.json` 的 `resource_changes`，不在 `validation.json` 的比對範圍內（F06、L04、T05、T06）。
- ADR-0015 例外的 7 份在 `compare.png` 的 MuPDF 列為空白，該 7 份視覺判定只用 PDFium。

## 6. 資料完整性與資源／出站紀錄

- 來源 PDF 不寫入；編輯只改 worker 內的工作文件，`apply_edit` 成功才 `commit`（revision 加一）。另存為完整重寫，trailer 無 /Prev、
  只有一個 startxref、無不可達物件，驗證通過才寫出；目的檔已存在即拒絕（P2 不覆寫，交易式覆寫屬 P3）。
- 拒絕路徑（理由碼）不改 revision、不改工作文件位元組（G2-04）。已知例外見 §9 U4（f003：`apply_edit` 在 ActualText 檢查失敗時無回滾）。
- 錯誤訊息不含路徑與原文；`edit-text` CLI 的 `plan.json`／`validation.json` 依設計包含原文與內容差異（README 已載明，triage f009）。
- 出站：新增模組未匯入網路模組（`test_offline_guard` 通過）；IPC 仍為 stdin/stdout。實機出站監測於 P7。
- 資源：沿用 P1 限制；安全修補後 `content_diff` 不再對未改動運算子做平方級比對（f014），共用串流參照走訪受 `MAX_OBJECT_WALK` 限制。
  完整記憶體與解壓限制於 P7。

## 7. 限制、阻擋、未測項目

- **盲測**（T10–T12、F09、F10、L08 等）：NOT RUN，P8 由保管人在離線實機執行。
- **macOS 實機**：NOT RUN（ADR-0003，CI 證據替代至 P3）。
- **§8.3 效能與穩定**：NOT RUN。spec 寫「P2 決定是否調整或收縮規模」，本段未量測（§9 U5）。
- **模式 B 字型來源**：產品依序找環境變數 `PEDITOR_MODE_B_FONT`、套件內 `resources/fonts/`（P8 打包）；目前未打包，未設定時模式 B
  一律回 GLYPH_MISSING（`test_mode_b_font_unavailable`）。測試與證據以 fixture 字型設定環境變數。
- **`export_document` 參數**：實作接受呼叫端路徑，spec §7 定為 `destination_token`（triage f010，安全上判為誤報）；留待 P3 儲存交易一併處理。
- **支援範圍**：單一橫排文字、同一 BT 內相鄰運算子；Form XObject 內文字、直排、換行顯示運算子（`'`、`"`）需補償時、跨 BT 選取一律拒絕（ADR-0018）。
- **B06**：仍依 ADR-0013 延至 P6。

## 8. 安全審查

- **`/vuln-scan`**（`reports/P2/security/VULN-FINDINGS.{json,md}`，2026-10-22）：範圍為 P2 新增／修改的 `src/`，5 個焦點區域；
  24 項候選（MEDIUM 7／LOW 17），`--no-score`。本工作階段無法載入 repo 技能，依 `.claude/skills/vuln-scan/SKILL.md` 手動執行。
- **`/triage`**（`reports/P2/security/TRIAGE.{json,md}`，2026-10-27）：沿用 P1 的訪談答案（同一產品與信任邊界，未重新訪談），
  威脅模型 T1／T3／T9／T5，嚴重度依前提推導，分歧時 recall。每項 2 位獨立驗證子代理人投票，前兩票分歧的 f003、f012、f022 加第 3 票。
  結果：**3 項確認（LOW 3）、21 項誤報、0 重複**；原 7 項 MEDIUM 均降級或判誤報。本機 `python3` 為 Microsoft Store 替身，checkpoint 改以 `python` 執行。
- **確認項目與修正**（`c0196b6`；回歸測試 `tests/security/test_p2_scan_regressions.py`，修正前 f004、f002 失敗、f014 逾時）：

  | id | 嚴重度 | 問題 | 修正 |
  | --- | --- | --- | --- |
  | f014 | LOW | `content_diff` 對每頁每個串流做 `SequenceMatcher(autojunk=False)`，大量相同運算子為平方級，匯出必然逾時（`export.py`） | 先去除前後相同運算子，只比對中間改動部分 |
  | f004 | LOW | 模式 A 在 TJ 結尾位移之後純插入時，計畫起點與實際寫入位置不同，繞過 TEXT_OVERFLOW（`edit.py`） | 插在結尾位移之前（同模式 B） |
  | f002 | LOW | `_shared_stream` 只看其他頁 /Contents，漏同頁重複列出、Form XObject、註解外觀共用（`edit.py`） | 計算整份文件對目標串流的間接參照數，>1 即 SHARED_RESOURCE_UNSAFE；同時涵蓋 f012 |

- **判為誤報但程式缺陷屬實**（安全上不可利用，列為後續；清單見 `TRIAGE.md` 末節）：
  - f003 `apply_edit` 在 /ActualText 檢查前已改寫串流與資源，失敗時無回滾
  - f017 寫檔失敗留下部分輸出（違反 spec §7，P3）
  - f006 標記 PDF 的 /Alt、/E 檢查只信 /ParentTree 與 /P，可被與 /K 不一致的結構繞過
  - f007 /K 中重複的 MCID 使 /ActualText 同步後**舊文仍留在 /ActualText**，卻照樣給出「已同步」警告；這對應 spec 停止條件
    「宣稱成功但原文仍在指定內容」（在惡意或畸形的結構樹上），§9 U6
  - f018 模式 B ToUnicode 合併共用同一字形的碼位
  - f023 超出字碼空間的 ToUnicode 碼使計畫 ready、套用時失敗
  - f015 原始 `startxref` 位元組計數可阻擋含此字串的檔案匯出
  - f022／f024 CMap 正則平方級與解壓前未限大小（P7）
  - TRIAGE 建議由 P2 處理的 f006、f007、f018、f023、f015 本段**均未修正**（§9 U4）
- `THREAT_MODEL.md`：本段**未更新**（§9 U2）。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | 分支 commit 依序為 S3 步驟 1–7、9，**沒有步驟 8 的 commit**；repo 內也找不到步驟 8 的定義 | 若步驟 8 原有規劃的工作，可能未完成 | 工程師確認步驟 8 是否被合併、取消或漏做 |
| U2 | P2 引入編輯與另存路徑（worker 寫出檔案、修改工作文件），`THREAT_MODEL.md` 未隨之更新（CLAUDE.md：架構變更時更新） | 威脅模型未反映 T3 完整性控制與 worker 寫檔權限 | 工程師決定是否於合併前更新 |
| U3 | 3 個測試直接比對兩次 `working_bytes()` 的位元組（`test_edit_multi.py:106`、`test_edit_text.py:293`、`test_p2_scan_regressions.py:88`），存檔跨秒時 /ID 不同而失敗 | CI 偶發失敗（本段已發生 1 次）；另 `tests/security/test_worker_limits.py::test_basic_timeout_and_cancel`（依實際時間判定）在本機整套測試負載下失敗 1 次，單獨重跑 3 次與整套重跑皆通過，未修改 | 工程師決定：比對時排除 /ID，或產品存檔改用固定 /ID（會改變輸出）；時間性測試是否放寬須另以 ADR 決定，本段未動 |
| U4 | triage 確認屬實但未修的正確性缺陷（§8 末項）：TRIAGE 建議 P2 處理的 f006、f007、f018、f023、f015；建議 P3 的 f003（無回滾）、f017（部分輸出）；P7 的 f022、f024 | f003：唯一呼叫端 CLI 在失敗時中止、不匯出，目前無實際後果，P3 引入 UI／多次編輯後會暴露；f007 見 U6 | 工程師決定哪些排入 P2 收尾 |
| U5 | spec §8.3 效能基準「P2 決定是否調整或收縮規模」，本段未量測 | 規模決策延後 | 工程師決定是否於 P3 前量測 |
| U6 | ADR-0017 修訂（`docs/adr/0017-tagged-pdf-text-edit.md:46,52`）要求「儲存後須驗證 /ActualText 仍完全等於新內容的擷取文字」，產品端未實作：`apply_edit` 只確認舊值相等後寫入新值，匯出驗證沒有 /ActualText 檢查；測試以子字串比對。f007 顯示在重複 MCID 的結構上，同步後舊文會留在 /ActualText 而仍回報「已同步」。另外 MuPDF 擷取會讀 /ActualText，T05、T06、F06、L04 的 MuPDF「擷取到新文」來自同步寫入值，字形內容的獨立驗證只有 PDFium | G2-17 改標「PASS（附條件）」；在畸形結構樹上可能違反 spec §8.1「不能只更新畫面」的對應要求 | 工程師決定：P2 收尾補上儲存後等值驗證（並拒絕重複 MCID），或修訂 ADR-0017 |

## 10. 關卡結果

- CI：run 40442075176（commit `c0196b6`）雙平台 272 passed
- **關卡結果：PASS（附條件）**（範圍：repo 內 18 份支援＋3 份拒絕 fixture、E01–E04；G2-01～G2-22 均有測試證據，
  G2-17 附條件見 U6；盲測、macOS 實機、§8.3 效能 NOT RUN 並註明原因）
- **下一段可開始：待定**：須由工程師確認 U1、U2、U6；U3、U4、U5 可於 P3 開工前決定。

## 11. 獨立核對紀錄

第一輪（2026-10-27，HEAD `2486d14`）：未參與實作的 Claude 子代理人重跑 ruff／pytest（272 passed）、核對 CI run 40442075176（兩次 attempt）、
40439343547 與 traceability 引用的 run、summary.json（21 案）、21 個 fixture hash、T01／T03／F06／L04／T07 的真修改證據、視覺基準、
c0196b6 的修補與回歸測試；並在 HEAD 重產證據兩次逐位元組比對。結論：主要數字、hash、CI 與真修改證據一致，未發現把 CI 寫成實機或漏列 NOT RUN；
提出 10 項出入，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| 1 | G2-02 的 test ID／fixture 不符；PDFium 只驗新文存在、未驗舊文移除；「Unicode 精確相符」實為去空白後子字串比對 | `test_all_supported_text_cases` 補 PDFium 舊文計數；§3 G2-02 改寫 test ID、fixture 與比對方式 |
| 2 | F05 不在任何 P2 編輯路徑測試中；溢出測試只查 revision | 新增 `test_unsupported_encoding_rejected_on_edit_path`（F05 以 P1 目標 ID 規劃，回 UNSUPPORTED_ENCODING）；`test_overflow_rejected` 補運算子與磁碟 hash 檢查（以運算子比對，避開 U3 的 /ID 不穩定） |
| 3 | ADR-0017 修訂的「儲存後 /ActualText 等值驗證」產品端未實作；MuPDF 擷取讀 /ActualText | G2-17 改「PASS（附條件）」，新增 §9 U6 待工程師決定（未自行實作，屬 ADR 範圍） |
| 4 | f007 描述不準；TRIAGE 建議 P2 處理的 f006、f007、f018、f023、f015 未修卻只點名 f003、f017 | §8 逐項改寫 f007 並對應停止條件；U4 補列全部未修項目 |
| 5 | output.pdf hash 因 /ID 無法用於驗證重產 | §5 改寫並連到 U3 |
| 6 | 證據產生於安全修補之前 | §5 註明核對者已於 HEAD 重產比對，內容相同 |
| 7 | CI 272 passed 為 attempt 2；失敗測試名稱為推論 | §4 註明 attempt 與推論依據 |
| 8 | G2-15、G2-21 非雙平台 | §3 說明另註 |
| 9 | G2-05、G2-08 未列實際驗證的 test ID | §3 補列，G2-05 改列實際案例 |
| 10 | validation.json 不涵蓋 StructElem /ActualText 變更 | §5 註明驗證範圍 |

另：本機測試輸出的 faulthandler 堆疊先前誤判為「殘留輸出」，已查明為 pypdfium2 初始化時的已處理例外（§4）。

補強後本機與 CI 結果見下一個 commit 的 traceability 更新。
