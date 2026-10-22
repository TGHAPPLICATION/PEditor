# 追溯表：需求 → 關卡 → test ID

依 spec v1.1 逐條編號，G0 要求「指定每個需求的 test ID」。未來的 test ID 是**預定名稱**，
實作該段時必須使用同名測試或在此表更新對照；改名須同步本表。

狀態：`PASS`（已有測試且通過）、`CI`（只有 CI 證據）、`MANUAL`（人工驗收）、`NOT RUN`（未執行，附原因）、`PLANNED`（尚未到該段）。
fixture 欄引用 `tests/fixtures/manifest.csv` 的 fixture_id；hash 見 manifest。

## G0：規格、環境與資料集（spec §6 P0）

| 需求 ID | spec | 需求 | test ID／證據 | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G0-01 | §2 | Python 與相依鎖定版本 | `uv.lock`；CI `uv sync --locked` | — | PASS |
| G0-02 | §6 P0 | 最小測試流程（lint + pytest）在 Windows／macOS CI 執行 | `.github/workflows/ci.yml` job `test` | — | CI |
| G0-03 | §6 P0 | 空白桌面 app 可啟動 | `tests/gui/test_app_smoke.py::test_main_window_shows`、`::test_cli_smoke_exits_zero` | — | PASS（本機）、CI |
| G0-04 | §6 P0 | 兩平台打包最小 Qt app（smoke build） | `packaging/smoke_build.py`（CI 步驟 Smoke build） | — | PASS（本機）、CI |
| G0-05 | §6 G0 | Windows 11 x64 實機啟動 | `scripts/p0_windows_check.ps1`（人工實機執行，manual-steps §3）；`build/p0-check/summary.md`（2026-10-16，commit `7ca2eb3`） | — | PASS |
| G0-06 | §6 G0 | macOS Apple Silicon 實機啟動 | ADR-0003：P0–P3 以 CI macos-15 arm64 證據替代；實機用 `scripts/p0_macos_check.sh`（manual-steps §8） | — | NOT RUN（無實機） |
| G0-07 | §5 | 61 份 fixture manifest，群組數 T12／F10／L8／I9／B8／U6／S8 | `tests/unit/test_manifest.py::test_manifest_has_61_fixtures_in_spec_groups`、`::test_manifest_rows_match_schema` | 全部 | PASS |
| G0-08 | §5 | 至少 12 份盲測，未用於實作調整、不進 repo | `tests/unit/test_manifest.py::test_at_least_12_blind_fixtures_kept_offline` | T10–T12、F09–F10、L08、I08、B07–B08、U06、S07–S08 | PASS（結構）；製作 11 份，U06 無法製作（ADR-0012） |
| G0-09 | §6 P0 | 至少 20 份可重現首批樣本，非單一產生器 | `tests/unit/test_manifest.py::test_first_batch_has_20_reproducible_fixtures_from_two_generators`、`tests/integration/test_fixtures.py::test_generator_reproduces_committed_bytes` | 21 份合成 | PASS |
| G0-10 | §6 G0 | fixture hash 可驗證 | `tests/unit/test_manifest.py::test_committed_fixture_hashes_match_manifest`、`::test_no_unlisted_files_in_fixture_dir` | 全部 available | PASS |
| G0-11 | §6 G0 | 沒有正式 PDF（只有合成資料） | `scripts/gen_fixtures.py` 合成內容；人工 fixture 依 manual-steps §4 規則；PR #1 審查（2026-10-16） | 全部 | PASS |
| G0-12 | §6 G0 | 每個需求指定 test ID | 本表；PR #1 審查（2026-10-16） | — | PASS |
| G0-13 | §3、§6 G0 | 嚴格 A 或允許 A/B 已記錄 | `docs/adr/0001-edit-semantics.md` | — | PASS（已確認：允許 A/B） |
| G0-14 | §2 | LICENSE、THIRD_PARTY_NOTICES、SBOM 草案 | `LICENSE`、`THIRD_PARTY_NOTICES.md`、`packaging/sbom/sbom-runtime.cdx.json` | — | PASS（草案） |
| G0-15 | §5 | fixture 預期性質正確（雙引擎擷取、qpdf、理由碼性質） | `tests/integration/test_fixtures.py::test_support_text_targets_found_by_both_engines`、`::test_support_and_readonly_fixtures_pass_qpdf_check`、`::test_reject_fixtures_have_stated_property`、`::test_mode_a_targets_have_new_glyphs_in_original_subset`、`::test_shared_image_fixtures` | 21 份合成 | PASS |
| G0-16 | §1、P7 | 產品程式碼無網路模組（離線靜態護欄） | `tests/security/test_offline_guard.py::test_no_network_imports_in_product_code` | — | PASS |
| G0-17 | §2、§5 | 字型授權與來源可驗證 | `scripts/fetch_fonts.py`（SHA-256）、`tests/fixtures/fonts/LICENSE-*.txt`、ADR-0008 | — | PASS |

## G1：只讀分析器與能力判定（P1）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G1-01 | P1 | parser 在 worker 執行，主行程不開 PDF | `tests/security/test_worker_isolation.py::test_main_process_never_imports_pdf_libs_for_user_files`、`::test_main_process_modules_do_not_import_pdf_libs_or_worker` | T05 | PASS |
| G1-02 | G1 | 61 份全部分析或受控拒絕，不崩潰 | `tests/integration/test_analyzer.py::test_all_fixtures_analyzed_or_rejected` | repo 內 45 份 available | PASS（45 份）；盲測 11 份 NOT RUN（P8）、U06 無法製作（ADR-0012）、S03–S06 NOT RUN（P7 產生） |
| G1-03 | G1 | 可編輯／不可編輯符合 manifest | `tests/integration/test_analyzer.py::test_capability_matches_manifest`、`::test_xfa_rejected` | repo 內 45 份 available | PASS（附條件，42 份）；F03、F08 GLYPH_MISSING 延至 P2（G2-04）、B06 合併格延至 P6（ADR-0013） |
| G1-04 | G1 | 座標 round-trip 誤差 ≤0.5 pt | `tests/unit/test_geometry.py::test_coordinate_round_trip_within_half_point`、`::test_pdf_to_page_matches_pymupdf` | T01、L01、L02 | PASS |
| G1-05 | G1 | 100／200% 縮放與 0／90／180／270° 旋轉命中正確 | `tests/unit/test_geometry.py::test_hit_test_zoom_and_rotation` | L02 | PASS |
| G1-06 | P1 | API：open_document、inspect_page、assess_editability | `tests/integration/test_api_contract.py::test_open_inspect_assess`、`::test_contract_errors` | T01、U02 | PASS |
| G1-07 | P1 | CLI JSON 分析報告與頁面 PNG | `tests/integration/test_cli_analyze.py::test_json_report_and_png`、`::test_rejected_document_reports_reason_without_path` | T01、T07、U02 | PASS |
| G1-08 | G1 停止 | 字形能對應到可修改 content stream（bbox 不算定位） | `tests/integration/test_locator.py::test_glyph_maps_to_content_stream_operator`、`tests/unit/test_content_parsing.py` | T01、F04、L03 | PASS |
| G1-09 | P7 | P1 起即有基本隔離、取消、資料限制、不執行主動內容 | `tests/security/test_worker_limits.py::test_basic_timeout_and_cancel`、`::test_worker_crash_recovers`、`::test_reopen_detects_external_modification`、`::test_active_content_reported_not_executed`、`::test_file_size_and_page_limits`、`::test_form_depth_and_cycle_limited`、`::test_oversized_worker_response_rejected`、`tests/security/test_scan_regressions.py`（P1 安全掃描 8 項） | T01、T05、S02 | PASS（基本版；完整資源限制於 P7） |
| G1-10 | §4 | 只有 owner 密碼的加密檔判 ENCRYPTED_DOCUMENT；繼承 `/FT`、未列入 `/Fields` 的簽章 widget 判 SIGNED_DOCUMENT；過深欄位樹不判 support（P1 報告 U8：f003、f008） | `tests/security/test_scan_regressions.py::test_f003_owner_password_only_rejected`、`::test_f008_inherited_ft_signature_detected`、`::test_f008_widget_outside_fields_detected`、`::test_f008_long_parent_chain_not_supported`、`::test_f008_deep_field_tree_not_supported`（本項為防護測試：驗證既有 `_fields` 走訪上限，f003／f008 修正前亦通過） | 腳本產生（測試內） | PASS（CI run 39709877095 雙平台 73 passed） |

## G2：真正文字修改（P2）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G2-01 | G2-1 | 宣告支援文字案例 100% 通過，≥20 次操作、3 種產生來源、2 種繁中字型 | `tests/integration/test_edit_text.py::test_all_supported_text_cases` | T、F 群組 support | PLANNED |
| G2-02 | G2-2 | 目標 occurrence 舊字形移除，新文可搜尋、複製，Unicode 精確相符 | `tests/integration/test_edit_text.py::test_target_occurrence_replaced_dual_engine` | T01–T04 | PLANNED |
| G2-03 | G2-3 | 密集鄰字、背景、線條不被修改；不靠白底覆蓋 | `tests/integration/test_edit_text.py::test_neighbors_and_lines_untouched` | L03、B01 | PLANNED |
| G2-04 | G2-4 | 不支援、缺字、溢出回傳理由碼，磁碟與工作文件不變 | `tests/integration/test_edit_text.py::test_rejections_leave_files_unchanged` | F03、F05、F08 | PLANNED |
| G2-05 | G2-5 | 同原字型模式不偷換字型；B 模式證明先移除舊內容 | `tests/integration/test_edit_text.py::test_mode_a_keeps_font_mode_b_removes_old` | F01、F02 | PLANNED |
| G2-06 | P2 | 超框一律拒絕，不偷偷縮字 | `tests/integration/test_edit_text.py::test_overflow_rejected` | T04 | PLANNED |
| G2-07 | §8.1-1 | 內容／資源解碼差異證明 occurrence 運算子已改寫 | `tests/integration/test_evidence.py::test_operator_diff_evidence` | T01 | PLANNED |
| G2-08 | §8.1-4 | 完整另存、清除不可達物件，無增量歷史 | `tests/integration/test_evidence.py::test_full_rewrite_no_incremental_history` | T01 | PLANNED |
| G2-09 | §8.2 | qpdf 無新增錯誤／warning | `tests/integration/test_evidence.py::test_no_new_qpdf_warnings` | 全部 support | PLANNED |
| G2-10 | §8.2 | 未修改頁同引擎像素完全相同 | `tests/integration/test_visual.py::test_untouched_pages_pixel_identical` | I02 | PLANNED |
| G2-11 | §8.2 | 已修改頁：改動區 +2 pt 外每通道差 >8/255 的像素 ≤0.01% | `tests/integration/test_visual.py::test_changed_page_outside_mask_threshold` | T01–T04 | PLANNED |
| G2-12 | §8.2 | 目標外框定位誤差 ≤0.5 pt | `tests/integration/test_visual.py::test_target_bbox_within_half_point` | T01–T04 | PLANNED |
| G2-16 | §8.2、ADR-0015 | MuPDF 渲染空白的 7 份（T01、F01、F02、F05、L02、L03、B01）視覺比對只以 PDFium 判定；這 7 份 PDFium 渲染非空白、其他 support fixture MuPDF 渲染非空白（例外清單不得擴大） | `tests/integration/test_visual.py::test_mupdf_blank_exceptions_fixed` | T01、F01、F02、F05、L02、L03、B01 | PLANNED |
| G2-13 | §7 | EditPlan 欄位完整；UI 不可送原始 PDF 指令 | `tests/unit/test_edit_plan.py::test_edit_plan_schema` | — | PLANNED |
| G2-14 | §7 | target_id 含 revision、page、content stream、operator span、geometry hash | `tests/unit/test_edit_plan.py::test_target_id_components` | — | PLANNED |
| G2-15 | §8.1 | 不宣稱鑑識級遮蔽 | 文件審查（使用說明） | — | PLANNED |

## G3：儲存交易、撤銷與復原（P3）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G3-01 | G3 | 50 次操作 undo／redo 等價 | `tests/integration/test_transaction.py::test_50_undo_redo_equivalent` | T01 | PLANNED |
| G3-02 | G3 | 儲存重開後目標正確 | `tests/integration/test_transaction.py::test_reopen_after_save` | T01 | PLANNED |
| G3-03 | G3 | 寫入／驗證／rename 前注入中斷，原檔與既有目的檔完整 | `tests/integration/test_crash_injection.py::test_interrupt_each_stage` | T01 | PLANNED |
| G3-04 | G3 | 100 次另存循環無毀損 | `tests/integration/test_transaction.py::test_100_save_cycles` | T01 | PLANNED |
| G3-05 | G3 | 損壞與外部修改回傳明確錯誤（REVISION_CONFLICT） | `tests/integration/test_transaction.py::test_external_modification_detected` | T01 | PLANNED |
| G3-06 | P3 | 空間不足不破壞既有目的檔 | `tests/integration/test_crash_injection.py::test_disk_full_preserves_destination` | T01 | PLANNED |
| G3-07 | P3 | 復原草稿由使用者選擇開啟、敏感暫存有保留期限 | `tests/integration/test_drafts.py::test_draft_opt_in_and_expiry` | — | PLANNED |
| G3-08 | §7 | 失敗不更新 revision、不落地部分輸出 | `tests/integration/test_transaction.py::test_failure_no_partial_output` | F03 | PLANNED |

## G4：桌面文字編輯流程（P4，兩平台實機）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G4-01 | G4 | 每平台至少 12 個 E2E 流程 | `tests/gui/test_e2e.py::test_flow_*`（12 項） | T、F | PLANNED |
| G4-02 | G4 | IME 組字中不提前送出 | `tests/gui/test_ime.py::test_preedit_not_committed` + 實機人工 | — | PLANNED |
| G4-03 | G4 | 中文路徑、空白檔名、emoji 路徑 | `tests/gui/test_paths.py::test_unicode_paths` | T01 | PLANNED |
| G4-04 | G4 | 取消不提交 | `tests/gui/test_e2e.py::test_cancel_does_not_commit` | T01 | PLANNED |
| G4-05 | G4 | 不可編輯物件顯示原因 | `tests/gui/test_e2e.py::test_reason_shown_for_uneditable` | F05、U01 | PLANNED |
| G4-07 | G4 | 中文字型正確顯示（UI 與預覽） | `tests/gui/test_fonts.py::test_cjk_font_rendering` + 實機人工 | T01、B02 | PLANNED |
| G4-06 | P4 | Ctrl／Cmd 快捷鍵；worker 不阻塞 UI（≤100 ms） | `tests/gui/test_shortcuts.py::test_platform_shortcuts`、`tests/gui/test_responsiveness.py::test_ui_not_blocked` | T01 | PLANNED |

## G5：圖片替換（P5）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G5-01 | G5 | 宣告支援 I 案例全部通過 | `tests/integration/test_edit_image.py::test_all_supported_image_cases` | I01–I07 | PLANNED |
| G5-02 | G5 | 同 xref 同頁／跨頁重用時只改選定 occurrence（copy-on-write） | `tests/integration/test_edit_image.py::test_only_selected_occurrence_changed` | I02、I03 | PLANNED |
| G5-03 | G5 | 其他頁視覺不變；外框誤差 ≤0.5 pt | `tests/integration/test_edit_image.py::test_other_pages_unchanged_and_bbox` | I02 | PLANNED |
| G5-04 | G5 | 拒絕非支援遮罩／剪裁；像素上限 | `tests/integration/test_edit_image.py::test_reject_unsupported_mask_clip` | I09 | PLANNED |

## G6：既有規則表格儲存格（P6）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G6-01 | G6 | 宣告支援 B 案例全部通過 | `tests/integration/test_edit_cell.py::test_all_supported_cell_cases` | B01–B05 | PLANNED |
| G6-02 | G6 | 邊線幾何／筆畫寬不變，其他格擷取與視覺不變 | `tests/integration/test_edit_cell.py::test_borders_and_other_cells_unchanged` | B01、B02 | PLANNED |
| G6-03 | G6 | 溢出阻擋 | `tests/integration/test_edit_cell.py::test_cell_overflow_rejected` | B01 | PLANNED |
| G6-04 | G6 | 人工選定格仍需能力判定 | `tests/integration/test_edit_cell.py::test_manual_cell_requires_assessment` | B06 | PLANNED |

## G7：離線與安全強化（P7，兩平台實機）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G7-01 | G7 | 斷網完整開／編／存 | 實機人工 + `tests/security/test_offline_flow.py` | T01 | PLANNED |
| G7-02 | G7 | app 與全部子程序零非 loopback 出站；無 HTTP listener | 實機出站監測 + `tests/security/test_no_listener.py::test_no_listening_sockets` | 全部 | PLANNED |
| G7-03 | G7 | 惡意樣本不啟動外部程式／連線 | `tests/security/test_malicious.py::test_no_external_launch` | S01–S06 | PLANNED |
| G7-04 | G7 | worker 逾時可停止、崩潰可重啟 | `tests/security/test_worker_limits.py::test_timeout_kills_worker` | S03、S04 | PLANNED |
| G7-05 | G7 | 日誌不洩漏 sentinel、原文、密碼、完整路徑 | `tests/security/test_logging.py::test_no_sentinel_in_logs` | S02、U02 | PLANNED |
| G7-06 | P7 | 限制初值：200 MB、500 頁、50 MP、30 秒、2 GB；載入前／解析中限制 | `tests/security/test_worker_limits.py::test_limits_enforced_before_full_parse` | S03 | PLANNED |
| G7-07 | P7 | OS 沙箱／權限評估與缺口報告 | reports/P7 文件審查 | — | PLANNED |

## G8：打包、實機與發布候選（P8，兩平台實機）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G8-01 | G8 | 乾淨 VM／實機無 Python、無網路可安裝並完成核心流程 | 實機人工 | T01 | PLANNED |
| G8-02 | G8 | 兩種 PDF 閱讀器正常開啟輸出 | 實機人工 | T01–T04 | PLANNED |
| G8-03 | G8 | 完整支援矩陣 100%；61 fixture 與 12 盲測結果（依 ADR-0012 為 11 份，U06 無法製作） | `tests/integration/test_release_matrix.py` + 盲測人工 | 全部 | PLANNED |
| G8-04 | G8 | 已知缺陷清單、SBOM、LICENSE、相依來源與版本、卸載／草稿清理說明 | 文件審查 | — | PLANNED |
| G8-05 | P8 | 標明 macOS 最低支援版本 | 文件審查 | — | PLANNED |

## 共通（§8）

| 需求 ID | spec | 需求 | 預定 test ID | 狀態 |
| --- | --- | --- | --- | --- |
| X-01 | §8.3 | 首次預覽 p95 ≤3 s、單頁替換預覽 ≤2 s、另存 ≤15 s、UI ≤100 ms（實機 20 次） | `tests/perf/test_benchmarks.py`（實機） | PLANNED |
| X-02 | §8.3 | 50 次循環 worker 峰值 ≤2 GB、無單調洩漏 | `tests/perf/test_memory.py` | PLANNED |
| X-03 | §8.4 | 錯誤標成可編輯率 = 0%；盲測誤判即回歸 | `tests/integration/test_analyzer.py::test_no_false_editable` | PLANNED |
| X-04 | §8.4 | core 分支覆蓋率目標 85%（輔助） | `pytest --cov=peditor.core`（P1 起加入） | PLANNED |
| X-06 | §7 | SHARED_RESOURCE_UNSAFE：共享資源無法安全 copy-on-write 時拒絕 | `tests/integration/test_edit_image.py::test_shared_resource_unsafe_rejected` | PLANNED |
| X-07 | §7 | VALIDATION_FAILED：輸出驗證失敗不落地 | `tests/integration/test_transaction.py::test_validation_failed_no_output` | PLANNED |
| X-08 | §7 | SAVE_FAILED：寫入失敗回報且原檔不變 | `tests/integration/test_crash_injection.py::test_save_failed_reported` | PLANNED |
| X-09 | §7 | CANCELLED：預覽／長操作可取消 | `tests/integration/test_api_contract.py::test_cancel_returns_cancelled` | PLANNED |
| X-10 | §7 | 錯誤包含可讀說明與是否可重試 | `tests/unit/test_errors.py::test_error_has_message_and_retryable` | PLANNED |
| X-05 | §8.2 | 視覺門檻於 P0／P2 以基準實測後鎖定，修改須 ADR | P2 基準報告 | PLANNED（P0 NOT RUN：尚無編輯引擎可量測） |
