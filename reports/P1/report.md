# P1 關卡報告：只讀分析器與能力判定

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：P1　分支：`p1-analyzer`　commit：`af39cdf`（程式）、`e65ad4c`（獨立核對修正）　日期：2026-10-21
- 撰寫：Claude Code；審查：待工程師；獨立核對：未參與實作的 Claude 子代理人（§11）
- 輸入：spec v1.1 P1／G1／§7、ADR-0001～0012、manifest（45 份 available）、P0 報告 §10 延續條件
- S2 決定（工程師 2026-10-21）：B 組在 P1 只判定格內文字，B06 合併格延至 P6（ADR-0013）；S03–S06 維持 P7 產生

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；pypdfium2 5.13.0；PySide6-Essentials 6.11.2 |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest x64 | GitHub 標準 runner | Python 3.13.16；套件同上（`uv.lock`，未升級） |
| CI macos | macos-15 arm64 | GitHub 標準 runner | Python 3.13.15；套件同上 |

本段未新增或升級相依（`uv.lock` 未變）。

## 3. 需求 → test ID → fixture／hash → 結果

| 需求 ID | test ID | fixture（hash 前 12 碼） | 環境 | 結果 |
| --- | --- | --- | --- | --- |
| G1-01 | `tests/security/test_worker_isolation.py::test_main_process_never_imports_pdf_libs_for_user_files`、`::test_main_process_modules_do_not_import_pdf_libs_or_worker` | T05 `3704edfda119` | 本機、CI 雙平台 | PASS |
| G1-02 | `tests/integration/test_analyzer.py::test_all_fixtures_analyzed_or_rejected` | repo 內 45 份 available | 本機、CI 雙平台 | PASS（45 份）；盲測 11 份 NOT RUN（P8 由保管人執行）；U06 無法製作（ADR-0012）；S03–S06 NOT RUN（P7 產生） |
| G1-03 | `tests/integration/test_analyzer.py::test_capability_matches_manifest`、`::test_xfa_rejected` | 45 份 available；XFA 為測試內合成檔 | 本機、CI 雙平台 | PASS（附條件）：42 份逐項相符；F03 `d0e6918195a0`、F08 `7a79c777c6d5`、B06 `ef732af2d87c` 依 ADR-0013 延後（§7） |
| G1-04 | `tests/unit/test_geometry.py::test_coordinate_round_trip_within_half_point`、`::test_pdf_to_page_matches_pymupdf` | T01 `65a4ebca20fe`、L01、L02 `0e744136f8ca` | 本機、CI 雙平台 | PASS |
| G1-05 | `tests/unit/test_geometry.py::test_hit_test_zoom_and_rotation`（0／90／180／270° × 100／200%） | L02 `0e744136f8ca` | 本機、CI 雙平台 | PASS |
| G1-06 | `tests/integration/test_api_contract.py::test_open_inspect_assess`、`::test_contract_errors` | T01、U02 `a2c282a74c2c` | 本機、CI 雙平台 | PASS |
| G1-07 | `tests/integration/test_cli_analyze.py::test_json_report_and_png`、`::test_rejected_document_reports_reason_without_path` | T01、T07 `eb85f8ac17b3`、U02 | 本機、CI 雙平台 | PASS（T01 等 7 份輸出的 PNG 為空白頁，見 §9 U3；非空白只在 T07 驗證） |
| G1-08 | `tests/integration/test_locator.py::test_glyph_maps_to_content_stream_operator`、`tests/unit/test_content_parsing.py` | T01、F04 `6dda72bbbb80`、L03 `a8b045e2972a` | 本機、CI 雙平台 | PASS |
| G1-09 | `tests/security/test_worker_limits.py::test_basic_timeout_and_cancel`、`::test_worker_crash_recovers`、`::test_reopen_detects_external_modification`、`::test_active_content_reported_not_executed`、`::test_file_size_and_page_limits`、`::test_form_depth_and_cycle_limited`、`::test_oversized_worker_response_rejected` | T01、T05、S02 `88e4c27ba76f`；測試內合成 Form 巢狀／循環檔 | 本機、CI 雙平台 | PASS（基本版；完整資源限制於 P7） |

G1 各驗收條件：

- **全部分析或受控拒絕，不崩潰**：repo 內 45 份全部完成；加密（U02）、損毀（S01）回理由碼，無 worker 崩潰。
- **可編輯／不可編輯符合預定清單**：42 份與 manifest 的 expected／reason_code 逐項相同；另 3 份依 ADR-0013 延後（P1 輸出為 support，P2／P6 須改判），故本項為**附條件通過**。文字 support 案例另比對定位框與 manifest `bbox_pt`（≤0.5 pt；兩者同取自 PyMuPDF 擷取，屬一致性檢查而非獨立證據），影像案例比對可見範圍（I07 矩陣層級裁剪、I09 非矩形 clip）。
- **座標 round-trip ≤0.5 pt；縮放與旋轉命中**：以 PyMuPDF 頁面矩陣與 PDFium 實際渲染像素為獨立對照。
- **停止條件「字形無法可靠對應 content stream」未觸發**：直譯器由 content stream 自行計算字形原點（不取自 PyMuPDF），與 PyMuPDF 擷取原點比對：U02 加密無法解析，其餘 44 份（含修復後開啟、無字形的 S01）中，所有可對應 Unicode 的非空白字形都找到擷取字元，差距 ≤0.052 pt（2026-10-21 量測，T02 最大；獨立核對重算為 0.0518 pt）。G1-08 另以 pikepdf 取回目標回報的 stream／運算子（確認為 Tj／TJ），清空其字串後另存，PyMuPDF 重新擷取時原文消失、其餘文字不變，證明正是這些運算子繪出目標字形。

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q                                        → exit 0，58 passed（Windows 實機，獨立核對修正後；修正前 54 passed）
uv run peditor analyze tests/fixtures/files/L02.pdf --out <tmp>   → exit 0，約 2.9 秒（含 worker 啟動）
```

CI：run [39544656448](https://github.com/TGHAPPLICATION/PEditor/actions/runs/39544656448)（commit `e65ad4c`，獨立核對修正後）
windows-latest 58 passed、macos-15 58 passed，P0 檢查腳本（含 smoke build）result PASS。
修正前：run 39543474799（commit `66c6a79`）雙平台 54 passed。

## 5. 真修改證據

不適用（P1 只讀，不修改 PDF）。

## 6. 資料完整性與資源／出站紀錄

- 分析過程不寫入來源 PDF；worker 以位元組讀入（上限 200 MB），回報 SHA-256，`test_api_contract` 比對 manifest hash。
- worker 重啟後依原路徑重開並比對 SHA-256，不符回 `REVISION_CONFLICT`（`test_reopen_detects_external_modification`）。
- 錯誤訊息不含路徑與原文（`test_contract_errors`、`test_rejected_document_reports_reason_without_path`）；worker 的 MuPDF 錯誤／警告輸出已關閉，stderr 只寫例外類別名稱。
- 出站：新增模組未匯入網路模組（`test_offline_guard` 通過）；IPC 為 stdin/stdout，無 socket。實機出站監測於 P7。

## 7. 限制、阻擋、未測項目

- **盲測 11 份**：NOT RUN，P8 由保管人在離線實機執行（hash 清冊見 P0 報告 §6）。
- **S03–S06**：NOT RUN，manifest 原訂 P7 產生（工程師 2026-10-21 決定維持）。
- **F03、F08（GLYPH_MISSING）**：缺字取決於新文字，屬 `plan_text_edit`（P2，G2-04）；P1 只驗證目標可定位、文字層可判定。
- **B06（合併儲存格）**：表格結構偵測屬 P6；P1 判定格內文字為 support（文字層本身可對應），P6 須改判 UNSUPPORTED_LAYOUT；P2–P5 不得把 B06 當支援案例（ADR-0013）。
- **打包後的 worker 子命令**（`peditor --worker`）：程式已就緒，PyInstaller 產物內啟動 worker 未驗證，P8 處理（ADR-0004 後果）。
- **資源限制**：P1 只有檔案大小（讀檔前）、頁數（MuPDF／pikepdf 開檔後、解析頁面前）、逾時、Form 深度與循環、worker 回應單行長度（讀取時）；記憶體、解壓膨脹、物件數限制於 P7。
- **qpdf 原有 warning 的 manifest 欄位**（P0 報告 §7「P1 加入欄位」）：P1 未加入。目前 available 中只有 S01 有 qpdf 問題（`test_support_and_readonly_fixtures_pass_qpdf_check`）；改於 P2 實作 G2-09「不得新增 warning」時加入欄位。
- **不列為目標**：inline image（只計數 `inline_images`）、文字繪製模式的 clip（Tr 4–7）未特別處理。
- **tagged PDF**：只在目標位於含 `/ActualText` 的標記內容時判 UNSUPPORTED_FEATURE；結構樹其他部分未檢查（spec §8.1：P2 起若修改 tagged PDF 須另驗）。
- **macOS 實機**：NOT RUN（ADR-0003，CI 證據替代至 P3）。

## 8. 安全審查

- `/vuln-scan`、`/triage`：**NOT RUN**。defending-code-reference-harness 技能未安裝於本機；依 CLAUDE.md，複製進 `.claude/` 前須核對 Apache-2.0 授權並鎖定 commit `d3bea6b…`，需工程師同意（§9 U7）。
- 本段自行檢查的攻擊面：worker 對任何未預期例外回 `WORKER_FAILED` 而不崩潰；主行程對 worker 回應做長度上限與 JSON 解碼檢查，畸形回應即重啟 worker；Form XObject 遞迴有深度上限與循環偵測；ToUnicode 解析失敗視為無對應（不猜測）。
- `THREAT_MODEL.md` 已更新：T1、T2、T5 由 unmitigated 改為 partially_mitigated，並註明 P1 控制與剩餘缺口（非 OS 沙箱、回應尚無 schema 驗證、資源限制不完整）。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | 新增兩個**協定層**錯誤碼 `INVALID_REQUEST`（請求格式錯、頁碼超出範圍、文件未開啟）與 `WORKER_FAILED`（worker 未預期例外或異常結束），不在 spec §7／ADR-0007 清單；能力判定碼未增加 | 錯誤碼清單擴充；如需正式納入請以 ADR 確認 | 工程師 |
| U2 | 頁面能力指「文字編輯」：沒有任何文字目標的頁面判 `readonly NO_TEXT_LAYER`（U01 掃描、U03 輪廓文字、I01–I03 純圖片頁皆然），影像目標各自判定。因此 **U01 的掃描影像本身被判為可替換（support）**；結構上無法區分「掃描影像」與「一般圖片」（需 OCR，不在範圍） | 若認為掃描頁的影像也應唯讀，需另定規則（例如面積門檻）並以 ADR 確認 | 工程師 |
| U3 | **MuPDF 1.28.2 無法渲染 P0 以 PyMuPDF 產生的 Noto Sans TC（CFF，OTTO 包裝）fixture**：T01、F01、F02、F05、L02、L03、B01 渲染為空白頁（`FT_Load_Glyph … invalid argument`），PDFium 正常、文字擷取正常 | **P1 本身的產品輸出已受影響**：`render_page`／`peditor analyze` 對這 7 份輸出空白 PNG（獨立核對以 L02 重現）；P1 渲染對照改用 PDFium。**P2 的同引擎視覺比對（§8.2）若用 MuPDF，這 7 份會是空白對空白而失去意義**。P2 開工前須決定：重產這 7 份（hash 改變，依 CLAUDE.md 說明原因）或這 7 份改用 PDFium 視覺比對 | 工程師 |
| U4 | L07 直排以啟發式偵測：同一 BT 內連續單字 run、x 相同、y 遞減（Word 以每行一字排直書，無 Identity-V） | 罕見版面可能誤判；真正 Identity-V 另以字型編碼判定 | 工程師知悉 |
| U5 | 無 fixture 覆蓋的理由碼對應：Type3 → UNSUPPORTED_LAYOUT（spec §4 同列）；非 Identity-H 的 CMap → UNSUPPORTED_ENCODING；Form XObject 內的文字／影像 → UNSUPPORTED_LAYOUT（保守，未區分是否共享）；DCT／Flate 以外的影像濾鏡或 ImageMask → UNSUPPORTED_FEATURE；`/ActualText` → UNSUPPORTED_FEATURE | 皆為「拒絕」方向，不放寬支援範圍 | 工程師知悉 |
| U6 | ToUnicode 不可靠以**字型**為單位：頁上同一字型任一已用字碼無對應，該字型的所有目標都拒絕（依 ADR-0011 不只判目標區域） | T09 全頁 F1 字型文字皆不可編輯 | 已依 ADR-0011 |
| U7 | `/vuln-scan`、`/triage` 未執行（§8） | ADR-0005 要求 P1 結束前執行；未執行即進 P2 須工程師明確同意 | 工程師：同意安裝 harness 技能後補跑，或同意延後 |

## 10. 關卡結果

- CI：run 39544656448（commit `e65ad4c`）雙平台 58 passed
- **關卡結果：PASS（附條件）**（範圍：repo 內 45 份 available；G1-01～G1-09 均有測試證據；G1-03 為 42 份相符＋3 份依 ADR-0013 延後；盲測、S03–S06 NOT RUN 並註明原因）
- **下一段可開始：待工程師決定 U7**（安全掃描未依 ADR-0005 於 P1 結束前執行；工程師同意補跑或延後後，PR 合併即可開始）。延續條件：U3 須在 P2 視覺比對實作前決定；U1、U2 建議 P2 開工前確認；ADR-0013 的 F03／F08 於 P2、B06 於 P6 補判定。

## 11. 獨立核對紀錄

第一輪（2026-10-21，HEAD `b1e2990`）：未參與實作的 Claude 子代理人重跑 ruff／pytest（54 passed）、核對 CI run 39543474799、45 份 fixture hash、字形原點誤差（重算 0.0518 pt）、7 份 MuPDF 空白渲染、主行程隔離與錯誤訊息。結論：核心數字一致，未隱藏失敗或改測試預期；提出 12 項出入，處理如下：

| # | 出入 | 處理 |
| --- | --- | --- |
| 1 | G1-07 PNG 對 7 份為空白，未註明 | G1-07 結果與 U3 加註（P1 輸出本身受影響） |
| 2 | G1-08 對照獨立性被高估（bbox 同源、位元組數同義反覆） | 改為「清空運算子後重新擷取」的獨立對照；§3 改寫敘述 |
| 3 | 資料限制無測試；頁數非開檔前檢查 | 新增 `test_file_size_and_page_limits`、`test_form_depth_and_cycle_limited`；修正 §7 與 THREAT_MODEL 敘述 |
| 4 | B06 輸出 support 無 ADR；G1 字面未達成 | 新增 ADR-0013；G1-03 與關卡結果改為「PASS（附條件）」 |
| 5 | CI windows Python 版本寫錯 | 改為 3.13.16 |
| 6 | S01 並非開檔即無法解析 | 改為「其餘 44 份（含 S01）」 |
| 7 | UNSUPPORTED_ENCODING 斷言偏弱 | 改為「含無對應字碼的目標全部被判 UNSUPPORTED_ENCODING」 |
| 8 | G1-01 靜態檢查未說明排除 `__main__.py` | 測試內加註原因（只為版本字串匯入，不開使用者 PDF） |
| 9 | 回應長度上限為事後檢查 | 改為讀取時以 `readline(上限+1)` 限制；新增 `test_oversized_worker_response_rejected` |
| 10 | P0 延續項 qpdf warning 欄位未交代 | §7 註明未加入，改於 P2（G2-09）處理 |
| 11 | traceability G2-04 漏列 F08 | 補上 |
| 12 | U7 未決卻寫「下一段可開始：是」 | 改為待工程師決定 U7 |

