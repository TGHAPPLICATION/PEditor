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
| G1-11 | §7、ADR-0016 | 協定層錯誤碼 INVALID_REQUEST、WORKER_FAILED 正式列入，與能力判定碼分開且不重疊（P1 報告 U1） | `tests/unit/test_protocol_codes.py::test_error_code_sets_match_spec_and_adrs`、`::test_unknown_error_code_refused`；既有 `tests/integration/test_api_contract.py::test_contract_errors`、`tests/security/test_worker_limits.py::test_oversized_worker_response_rejected` | — | PASS（CI run 39712870262 雙平台 75 passed） |

## G2：真正文字修改（P2）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G2-01 | G2-1 | 宣告支援文字案例 100% 通過，≥20 次操作、3 種產生來源、2 種繁中字型 | `tests/integration/test_edit_text.py::test_all_supported_text_cases`、`::test_supported_case_coverage` | T、F 群組 support | PASS（manifest 18 案＋E01–E04＝22 次操作；模式 A 7＋4、模式 B 11；pymupdf／reportlab／word／libreoffice；Noto Sans TC、Noto Serif TC、Droid；CI run 39734651133 雙平台 267 passed） |
| G2-02 | G2-2 | 目標 occurrence 舊字形移除，新文可搜尋、複製，Unicode 精確相符 | `tests/integration/test_edit_text.py::test_target_occurrence_replaced_dual_engine`、`::test_all_supported_text_cases` | T／F／L support 18 份＋E02–E04 | PASS（新文為子字串比對、模式 B 去空白後比對，經工程師接受並記錄理由，見 P2 報告 U7）（模式 A、B；舊文移除由 MuPDF、PDFium 各自計數（獨立核對 #1 後補 PDFium）；新文為去空白後子字串比對；CI run 39734651133 雙平台 267 passed，補強後 CI run 40458762159 雙平台 273 passed） |
| G2-03 | G2-3 | 密集鄰字、背景、線條不被修改；不靠白底覆蓋 | `tests/integration/test_edit_text.py::test_neighbors_and_lines_untouched`、`tests/integration/test_visual.py::test_changed_page_outside_mask_threshold` | L03、L04、L05、T07、F07、T03 | PASS（L03 密集鄰字＋紅框、L05 彩底等 6 案：繪圖／色彩運算子完全相同、無新增覆蓋；目標外文字運算子逐一保留；視覺見 G2-11；CI run 39734651133 雙平台 267 passed） |
| G2-04 | G2-4 | 不支援、缺字、溢出回傳理由碼，磁碟與工作文件不變 | `tests/integration/test_edit_text.py::test_rejections_leave_files_unchanged`、`::test_mode_b_font_unavailable`、`::test_overflow_rejected`、`::test_unsupported_encoding_rejected_on_edit_path` | F03、F05、F08、T01、F02 | PASS（F03、F08 𠮷 於原字型與 Noto Sans TC 皆缺 → GLYPH_MISSING；模式 B 字型不可用亦同；F05 編輯路徑回 UNSUPPORTED_ENCODING、溢出拒絕後運算子與磁碟 hash 不變（獨立核對 #2 後補）；CI run 39734651133 雙平台 267 passed，補強後 CI run 40458762159 雙平台 273 passed） |
| G2-05 | G2-5 | 同原字型模式不偷換字型；B 模式證明先移除舊內容 | `tests/integration/test_edit_text.py::test_mode_a_keeps_font_mode_b_removes_old`、`::test_target_occurrence_replaced_dual_engine`、`tests/integration/test_evidence.py::test_operator_diff_evidence` | 模式 A：T01、T02、T08、F01、F04、L02、L03、E02–E04；模式 B：其餘 11 份 | PASS（模式 A 不換字型；模式 B 11 案證明原字型舊字形已不存在並明示字型替換；CI run 39734651133 雙平台 267 passed） |
| G2-06 | P2 | 超框一律拒絕，不偷偷縮字 | `tests/integration/test_edit_text.py::test_overflow_rejected`、`::test_stale_plan_and_revision_conflict` | T01（模式 A）、F02（模式 B） | PASS（模式 A、B；CI run 39734651133 雙平台 267 passed） |
| G2-07 | §8.1-1 | 內容／資源解碼差異證明 occurrence 運算子已改寫 | `tests/integration/test_evidence.py::test_operator_diff_evidence` | T／F／L support 18 份 | PASS（18 案：模式 A 就地改寫、模式 B 拆分並新增一個字型資源；CI run 39734651133 雙平台 267 passed） |
| G2-08 | §8.1-4 | 完整另存、清除不可達物件，無增量歷史 | `tests/integration/test_evidence.py::test_full_rewrite_no_incremental_history`、`::test_export_refuses_existing_destination_and_bad_path`、`::test_validation_failure_writes_nothing`、`tests/integration/test_cli_edit.py` | T／F／L support 18 份 | PASS（18 案；/ObjStm、/XRef 結構串流不計入不可達；CI run 39734651133 雙平台 267 passed） |
| G2-09 | §8.2 | qpdf 無新增錯誤／warning | `tests/integration/test_evidence.py::test_no_new_qpdf_warnings`、`tests/unit/test_manifest.py::test_qpdf_warnings_recorded` | 全部 support | PASS（manifest `qpdf_warnings`、18 案；CI run 39734651133 雙平台 267 passed） |
| G2-10 | §8.2 | 未修改頁同引擎像素完全相同 | `tests/integration/test_visual.py::test_untouched_pages_pixel_identical` | 測試內組合（F04／T02＋T07 第 2 頁） | PASS（CI run 39734651133 雙平台 267 passed） |
| G2-11 | §8.2、ADR-0019 | 已修改頁：改動區 +2 pt 外每通道差 >8/255 的像素 ≤0.01% | `tests/integration/test_visual.py::test_changed_page_outside_mask_threshold` | T／F／L support 18 份＋E02–E04 | PASS（18 案＋E02–E04；T02 PDFium 依 ADR-0019 以位置驗證；CI run 39734651133 雙平台 267 passed） |
| G2-12 | §8.2 | 目標外框定位誤差 ≤0.5 pt | `tests/integration/test_visual.py::test_target_bbox_within_half_point` | T／F／L support 18 份＋E02–E04 | PASS（18 案＋E02–E04、兩引擎；CI run 39734651133 雙平台 267 passed） |
| G2-16 | §8.2、ADR-0015 | MuPDF 渲染空白的 7 份（T01、F01、F02、F05、L02、L03、B01）視覺比對只以 PDFium 判定；這 7 份 PDFium 渲染非空白、其他 support fixture MuPDF 渲染非空白（例外清單不得擴大） | `tests/integration/test_visual.py::test_mupdf_blank_exceptions_fixed` | T01、F01、F02、F05、L02、L03、B01 | PASS（以目標文字外框內筆畫判定；CI run 39730468778 雙平台 147 passed） |
| G2-17 | §8.1、ADR-0017 | 標記 PDF：替代文字（ActualText／Alt／E，含結構元素與祖先）涵蓋目標即拒絕；可編輯者儲存後結構樹與 MCID 不變 | `tests/integration/test_tagged.py::test_tagged_structure_preserved`、`::test_tagged_actualtext_rejected`、`::test_tagged_actualtext_equal_is_synced`、`::test_tagged_duplicate_mcid_rejected`、`::test_tagged_actualtext_verified_after_save` | T05、T06、T08、F06、F07、L04；腳本產生 | PASS（6 份標記 PDF 結構不變；Word 4 份同步 /ActualText（ADR-0017 修訂），儲存後驗證 /ActualText 完全等於新內容擷取文字（產品直譯器的 ToUnicode 文字，只查 /ParentTree 指到的元素），不等則復原（P2 報告 U6）；重複 MCID 拒絕（f007）；拒絕規則 5 案；U6 實作後 CI run 40479995390 雙平台 275 passed；CI run 39734651133 雙平台 267 passed） |
| G2-18 | §7、ADR-0018 §1 | span target：運算子內部分文字與連續多段運算子；只改不同的字，改動範圍限同一 BT（T08 跨 4 個 BT 的選取） | `tests/unit/test_edit_plan.py::test_span_target_resolution`、`tests/integration/test_edit_multi.py`（改動跨同 BT 多段運算子：套用與拒絕） | T01、T08、F04、T04；測試內產生樣本 | PASS（CI run 39731302355 雙平台 155 passed） |
| G2-19 | P2、ADR-0018 §2 | 模式 A 字寬不同時，目標後續字形位置不變 | `tests/integration/test_edit_text.py::test_following_glyphs_shift`、`tests/integration/test_edit_multi.py::test_multi_operator_change` | F04、E03、T02 | PASS（單段與多段；CI run 39731302355 雙平台 155 passed） |
| G2-20 | G2-1 | 編輯案例實作前鎖定：manifest 18 個＋`edit_cases.csv` 4 個＝22 次操作（含同一文件連續編輯） | `tests/unit/test_manifest.py::test_edit_cases_locked`、`tests/integration/test_edit_text.py::test_chained_edit_e01_through_worker` | E01–E04 | PASS（鎖定 22 次操作；E01 經 worker 連續編輯、E02–E04 執行；CI run 39734651133 雙平台 267 passed） |
| G2-21 | §8.2 | 視覺門檻以 P2 實測基準鎖定後才寫入測試 | `scripts/p2_visual_baseline.py` → `reports/P2/visual_baseline.json`；報告記錄 | 全部 support | PASS（`reports/P2/visual_baseline.json`：21 次單步操作，改動區外超標像素皆為 0，唯 T02 PDFium 見 ADR-0019；維持 spec §8.2 原門檻） |
| G2-22 | §7、§8.1、P2 安全掃描 | P2 triage 確認 3 項之回歸（`reports/P2/security/TRIAGE.md`）：f004 模式 A 在 TJ 結尾位移之後插入時，新字畫在計畫起點；f002／f012 目標 content stream 被參照超過一次（同頁 /Contents 重複、Form XObject、註解外觀、其他頁）時拒絕 SHARED_RESOURCE_UNSAFE；f014 內容差異只比對前後相同運算子之間的部分，未改動串流不進入平方級比對 | `tests/security/test_p2_scan_regressions.py::test_f004_insertion_after_trailing_tj_number_drawn_at_planned_start`、`::test_f002_shared_content_stream_rejected`（3 種共用方式）、`::test_f014_identical_operators_diffed_linearly`（修正前 f004、f002 失敗，f014 逾時） | 腳本產生（測試內） | PASS（CI run 40442075176 雙平台 272 passed；macOS 首次因 /ID 秒數邊界不穩定 1 failed，重跑通過） |
| G2-13 | §7 | EditPlan 欄位完整；UI 不可送原始 PDF 指令 | `tests/unit/test_edit_plan.py::test_edit_plan_schema` | — | PASS（CI run 39719180645 雙平台 80 passed） |
| G2-14 | §7 | target_id 含 revision、page、content stream、operator span、geometry hash | `tests/unit/test_edit_plan.py::test_target_id_components` | — | PASS（CI run 39719180645 雙平台 80 passed） |
| G2-15 | §8.1 | 不宣稱鑑識級遮蔽 | 文件審查（`README.md` 限制節） | — | PASS（README「限制」節） |

## G3：儲存交易、撤銷與復原（P3）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G3-01 | G3 | 50 次操作 undo／redo 等價（command log 重播，ADR-0020 §1） | `tests/integration/test_transaction.py::test_50_undo_redo_equivalent`（50 步逐步撤銷到原檔再逐步重做，每步內容指紋相同）、`::test_replay_failure_restores_state`、`::test_service_undo_redo_and_truncation`、`::test_worker_restart_replays_log` | 腳本產生（Helvetica 樣本）、T01 | PASS（CI run 40827373536 雙平台 299 passed） |
| G3-02 | G3 | 儲存重開後目標正確 | `tests/integration/test_transaction.py::test_reopen_after_save` | T01 | PASS（CI run 40827373536 雙平台 299 passed） |
| G3-03 | G3 | 寫入／驗證／rename 前注入中斷，原檔與既有目的檔完整 | `tests/integration/test_crash_injection.py::test_interrupt_each_stage`（子行程 os._exit，3 階段）、`::test_exception_at_stage_cleans_up`、`::test_worker_crash_during_export_preserves_destination`、`::test_stale_temp_removed_on_next_save`、`::test_stale_temp_threshold` | T01 | PASS（CI run 40827373536 雙平台 299 passed） |
| G3-04 | G3 | 100 次另存循環無毀損 | `tests/integration/test_transaction.py::test_100_save_cycles`（以上一次輸出為來源，兩檔輪替覆寫） | T01 | PASS（CI run 40827373536 雙平台 299 passed） |
| G3-05 | G3 | 損壞與外部修改回傳明確錯誤（REVISION_CONFLICT） | `tests/integration/test_transaction.py::test_external_modification_detected`、`::test_destination_rules`、`tests/integration/test_crash_injection.py::test_temp_hash_mismatch_rejected` | T01 | PASS（CI run 40827373536 雙平台 299 passed） |
| G3-06 | P3 | 空間不足不破壞既有目的檔 | `tests/integration/test_crash_injection.py::test_disk_full_preserves_destination`、`tests/integration/test_transaction.py::test_failure_no_partial_output`（以模擬 ENOSPC 驗證；真實磁碟填滿 NOT RUN） | T01 | PASS（CI run 40827373536 雙平台 299 passed） |
| G3-07 | P3 | 復原草稿由使用者選擇開啟、敏感暫存有保留期限（7 天，ADR-0020 §5） | `tests/integration/test_drafts.py::test_draft_opt_in_and_expiry`、`::test_draft_rejected_when_source_changed`、`::test_draft_expires_after_7_days`、`::test_draft_store_ignores_bad_ids_and_files`、`::test_draft_errors_carry_no_path_and_do_not_undo_edit` | T01 | PASS（CI run 40850680948 雙平台 306 passed） |
| G3-08 | §7 | 失敗不更新 revision、不落地部分輸出（f003、f017、R3-1）；另存前文字與視覺驗證（ADR-0020 §4） | `tests/integration/test_transaction.py::test_failure_no_partial_output`、`::test_product_checks_detect_problems`、`tests/integration/test_crash_injection.py::test_os_errors_carry_no_path`、`::test_fsync_failure_after_replace_is_warning`（錯誤不含路徑，P3 U4） | T01、F04 | PASS（CI run 40850680948 雙平台 306 passed） |
| G3-09 | §7、§8.1、P3 安全掃描 | P3 triage 確認 1 項之回歸（`reports/P3/security/TRIAGE.md`）：f015 另存前視覺驗證的渲染像素不超過 12 MP，遮罩內像素不逐點讀取、區外超標即停止 | `tests/security/test_p3_scan_regressions.py::test_f015_visual_check_render_budget`（修正前渲染 50,013,184 像素而失敗）、`::test_f015_mask_pixels_not_visited`、`::test_f015_outside_count_matches_per_pixel_definition`（後兩項在修正前因函式介面不同而失敗） | 腳本產生（測試內） | PASS（CI run 40840198233 雙平台 303 passed） |

## G4：桌面文字編輯流程（P4，兩平台實機）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G4-01 | G4 | 每平台至少 12 個 E2E 流程 | `tests/gui/test_e2e.py::test_flow_*`（12 項） | T01、F02、F04 | PASS（本機 Windows offscreen）、CI run 41029981106 雙平台 360 passed；Windows 實機（2026-11-02，`reports/P4/windows-acceptance.md`，驗收人自填、無截圖） PASS（W02、W04、W07–W13、W15、W17–W19、W21、W27–W31）；macOS 實機 NOT RUN |
| G4-02 | G4 | IME 組字中不提前送出 | `tests/gui/test_ime.py::test_preedit_not_committed`、`::test_enter_during_preedit_not_planned`（P4 U7；以 QInputMethodEvent 模擬）+ 實機人工 | T01 | PASS（本機 Windows offscreen）、CI run 41029981106 雙平台 360 passed；Windows 實機（2026-11-02，`reports/P4/windows-acceptance.md`，驗收人自填、無截圖） PASS（W16a–W16f，微軟注音）；macOS 實機 NOT RUN |
| G4-03 | G4 | 中文路徑、空白檔名、emoji 路徑 | `tests/gui/test_paths.py::test_unicode_paths`（3 組：開啟、編輯、另存、重開；繞過檔案對話框） | T01 | PASS（本機 Windows offscreen）、CI run 41029981106 雙平台 360 passed；Windows 實機（2026-11-02，`reports/P4/windows-acceptance.md`，驗收人自填、無截圖） PASS（W02、W03、W17–W21，原生檔案對話框）；macOS 實機 NOT RUN |
| G4-04 | G4 | 取消不提交 | `tests/gui/test_e2e.py::test_cancel_does_not_commit` | F04（預登記 T01） | PASS（本機 Windows offscreen）、CI run 41029981106 雙平台 360 passed；Windows 實機（2026-11-02，`reports/P4/windows-acceptance.md`，驗收人自填、無截圖） NOT RUN（W26 結果不明，P4 U14 列 P7）；macOS 實機 NOT RUN |
| G4-05 | G4 | 不可編輯物件顯示原因 | `tests/gui/test_e2e.py::test_reason_shown_for_uneditable` | F05、U01 | PASS（本機 Windows offscreen）、CI run 41029981106 雙平台 360 passed；Windows 實機（2026-11-02，`reports/P4/windows-acceptance.md`，驗收人自填、無截圖） PASS（W05、W06、W14）；macOS 實機 NOT RUN |
| G4-07 | G4 | 中文字型正確顯示（UI 與預覽） | `tests/gui/test_fonts.py::test_cjk_font_rendering`（頁面與前後對照預覽；offscreen 無系統字型，UI 元件字形限實機人工） | T05（預登記 T01；T01 屬 ADR-0015 MuPDF 空白檔，改用 T05）；實機 B02 | 預覽：PASS（本機 Windows offscreen）、CI run 41029981106 雙平台 360 passed；UI：Windows 實機（2026-11-02，`reports/P4/windows-acceptance.md`，驗收人自填、無截圖） PASS（W01、W03、W03b）；macOS 實機 NOT RUN |
| G4-06 | P4 | Ctrl／Cmd 快捷鍵；worker 不阻塞 UI（≤100 ms） | `tests/gui/test_shortcuts.py::test_platform_shortcuts`、`tests/gui/test_responsiveness.py::test_ui_not_blocked` | F04（預登記 T01） | PASS（本機 Windows offscreen）、CI run 41029981106 雙平台 360 passed；Windows 實機（2026-11-02，`reports/P4/windows-acceptance.md`，驗收人自填、無截圖） PASS（W10、W11、W17、W23–W25）；macOS Cmd 實機 NOT RUN |
| G4-08 | §7、ADR-0021 §1／§2 | 預覽：PREVIEW_UNRELIABLE 恰標出 ADR-0015 的 7 份；preview_edit 不提交（revision、內容不變，原計畫可套用）、其他未套用計畫失效、無效 plan_id 回 INVALID_REQUEST | `tests/integration/test_preview.py::test_preview_unreliable_exactly_mupdf_blank`、`::test_preview_edit_does_not_commit`、`::test_preview_edit_invalidates_other_plans_and_rejects_bad_ids` | available fixture 43 份（排除加密 U02、損壞 S01）、F04 | PASS（本機 Windows）、CI run 41029981106 雙平台 360 passed |
| G4-09 | ADR-0021 §2、P3 U4／U9 | 草稿結構驗證（f001）、復原失敗關閉文件、參數副本（f006）、中斷暫存檔紀錄與啟動清除（U9） | `tests/integration/test_drafts.py::test_draft_structure_validated`（14 組）、`::test_recover_failure_closes_document`、`tests/integration/test_transaction.py::test_plan_params_copied`、`tests/integration/test_crash_injection.py::test_temp_recorded_while_writing`、`::test_cleanup_recorded_removes_only_own_temps`、`::test_cleanup_recorded_malformed_registry`、`tests/gui/test_startup.py`（2 項，啟動接線；ADR-0021 §2 例外）、`tests/gui/test_drafts_ui.py`（7 項：全列草稿 P4 U9；正常關閉刪草稿、取消重試、關閉前收下結果、關閉中不詢問草稿 P4 U11） | T01、F04、測試內樣本 | PASS（本機 Windows）、CI run 41029981106 雙平台 360 passed |

## G5：圖片替換（P5）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G5-01 | G5 | 宣告支援 I 案例全部通過（真修改證據：只有選定 `Do` 改名、新圖像素、雙引擎遮罩外差異、未再使用的原圖不保留） | `tests/integration/test_edit_image.py::test_all_supported_image_cases`（7 組） | I01–I07 | PASS（本機 Windows）、CI run 41609744423 雙平台 406 passed |
| G5-02 | G5 | 同 xref 同頁／跨頁重用時只改選定 occurrence（copy-on-write） | `tests/integration/test_edit_image.py::test_only_selected_occurrence_changed`（2 組）、`::test_shared_content_stream_rejected`、`::test_form_sharing_page_resources_keeps_original` | I02、I03 | PASS（本機 Windows）、CI run 41609744423 雙平台 406 passed |
| G5-03 | G5 | 其他頁視覺不變；外框誤差 ≤0.5 pt | `tests/integration/test_edit_image.py::test_other_pages_unchanged_and_bbox` | I01–I07（外框）、I02（其他頁） | PASS（本機 Windows）、CI run 41609744423 雙平台 406 passed |
| G5-04 | G5、ADR-0009、ADR-0022 §1 | 拒絕非支援遮罩／剪裁；像素上限（檔頭檢查後才解碼、補邊後上限）；不支援或損壞的圖片檔 | `tests/integration/test_edit_image.py::test_reject_unsupported_mask_clip`、`tests/unit/test_image_asset.py`（8 項） | I09、I01、測試內圖片 | PASS（本機 Windows）、CI run 41609744423 雙平台 406 passed |
| G5-05 | ADR-0022 §1–§3、§5 | 比例不同時等比置中、兩側透明；透明遮罩由新圖決定、不沿用原 SMask；JPEG 不補邊時原樣嵌入；圖片蓋住的文字不變；預覽建好的圖片資料由套用重用；EXIF 方向提示 | `tests/integration/test_edit_image.py::test_aspect_fit_and_smask`、`::test_image_text_check_detects_changed_text`、`::test_built_image_reused_after_preview`（U3）、`::test_exif_orientation_warned`（U4） | I01、I04、I05、I06 | PASS（本機 Windows）、CI run 41609744423 雙平台 406 passed |
| G5-06 | ADR-0022 §5 | 經 DocumentService：新圖登記、預覽不提交、undo／redo、worker 重啟重播、復原草稿（含新圖檔）、錯誤訊息不含路徑、與文字修改共用 log | `tests/integration/test_image_service.py`（5 項）、`tests/integration/test_drafts.py::test_draft_structure_validated`（新增 3 組） | I01、I03、I06 | PASS（本機 Windows）、CI run 41609744423 雙平台 406 passed |
| G5-07 | ADR-0022 §6 | 桌面圖片替換流程（點選、選新圖、前後對照、套用、復原、重做、另存；不可替換時顯示原因） | `tests/gui/test_image_ui.py`（2 項） | I01、I03、I09 | PASS（本機 Windows offscreen）、CI run 41609744423 雙平台 406 passed；實機 NOT RUN |

## G6：既有規則表格儲存格（P6）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G6-01 | G6 | 宣告支援 B 案例全部通過（目標格偵測與 manifest 可改動區域 ≤0.5 pt；雙引擎擷取到新文字；遮罩外差異 ≤0.01%） | `tests/integration/test_edit_cell.py::test_all_supported_cell_cases`（5 組） | B01–B05 | PASS（本機 Windows）、CI run 41809762756 雙平台 482 passed |
| G6-02 | G6 | 邊線幾何／筆畫寬不變，其他格（含同格其他行）擷取與視覺不變；另存前格線比對 | `tests/integration/test_edit_cell.py::test_borders_and_other_cells_unchanged`（5 組）、`::test_rules_check_detects_changed_borders`、`::test_frame_with_inner_lines_clips_region`（2 組：外框內含空白數字格、小表格；Q1）、`::test_manual_box_sees_form_lines`（Q2）、`::test_lines_drawn_any_way_block_region`（5 組：填色多邊形、往上凸的曲線、點線、粗填色、斜線；第二輪 R1、R2）、`::test_underline_and_nearby_lines_do_not_block`（7 組：填色與描邊底線、刪除線、右側同高的線、下方小框、延伸到右邊的底線、填空線；第二輪 R3、第三輪 S5）、`::test_any_drawing_blocks_long_text`（7 組：曲線、shading、註解、Type3、inline image、方形線帽、粗斜線；第三輪 S1–S3）、`::test_fill_over_text_does_not_cut_into_text`（2 組：粗刪除線、底色塊；第三輪 S4）、`::test_faint_hidden_and_tight_lines_block_long_text`（9 組：淡灰與淡紅影像、半透明／圖層 OFF／只在列印顯示／Rect 為間接參照／直接寫在 /Annots 裡的註解（第五輪 F1、F2、F4）、緊貼文字的影像與註解直線；第四輪 T1–T3）、`::test_annotation_over_text_rejects_and_link_does_not_block`（第四輪 T2）、`::test_unreadable_annotation_rect_rejects`（4 組：3 或 5 個數字、非數字、字串；第五輪 F3）、`::test_text_near_border_can_grow`（2 組：L03 加長；第四輪 T4） | B01–B05 | PASS（本機 Windows）、CI run 41809762756 雙平台 482 passed |
| G6-03 | G6 | 溢出阻擋 | `tests/integration/test_edit_cell.py::test_cell_overflow_rejected`（2 組） | B01、B04 | PASS（本機 Windows）、CI run 41809762756 雙平台 482 passed |
| G6-04 | G6、ADR-0013、ADR-0023 §1、§3 | 人工選定格仍需能力判定；合併格（偵測或框選）拒絕；格線推估（三種畫線方式、合併格、未封閉區域、斜線、Form、上限） | `tests/integration/test_edit_cell.py::test_manual_cell_requires_assessment`、`::test_text_crossing_border_rejected`、`::test_text_api_respects_cell_judgement`（U2）、`::test_frame_keeps_previous_text_edits`（Q3）、`::test_text_api_region_cannot_cross_borders`（Q4）、`tests/unit/test_table_grid.py`（9 項）、`tests/integration/test_analyzer.py::test_capability_matches_manifest`（B 組目標格；B06 移出 DEFERRED） | B06、測試內樣本 | PASS（本機 Windows）、CI run 41809762756 雙平台 482 passed |
| G6-05 | ADR-0023 §2 | 多行格一次只改指定行，可改動區域不含同格其他行；空白格拒絕 | `tests/integration/test_edit_cell.py::test_multiline_cell_line_layout`（2 組）、`::test_empty_cell_rejected` | B02、B05、測試內樣本 | PASS（本機 Windows）、CI run 41809762756 雙平台 482 passed |
| G6-06 | ADR-0023 §4 | 經 DocumentService：預覽不提交、undo／redo、worker 重啟重播、復原草稿、人工框選 | `tests/integration/test_cell_service.py`（3 項） | B04、測試內樣本 | PASS（本機 Windows）、CI run 41809762756 雙平台 482 passed |
| G6-07 | ADR-0023 §5 | 桌面儲存格編輯（點格內文字、行選擇、合併格顯示原因、手動選格） | `tests/gui/test_cell_ui.py`（3 項） | B04、B05、B06、測試內樣本 | PASS（本機 Windows offscreen）、CI run 41809762756 雙平台 482 passed；實機 NOT RUN |

## G7：離線與安全強化（P7，兩平台實機）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G7-01 | G7 | 斷網完整開／編／存 | 實機 `scripts/p7_offline_check.ps1`（網路介面全部中斷）+ `tests/security/test_offline_flow.py::test_offline_flow`（主行程與 worker 以 audit hook 禁止並記錄 Python 層 socket 事件，完整流程後兩邊都沒有事件）、`::test_deny_hook_blocks_sockets`、`::test_worker_hook_records_swallowed_attempts`（對照） | T01 | 自動測試 PASS（本機 Windows）、CI run 42150652779 雙平台（Windows 552 passed、macOS 549 passed）；Windows 實機 PASS（2026-11-11，`scripts/p7_offline_check.ps1`，P8 報告 §6）；macOS 實機 NOT RUN（ADR-0003） |
| G7-02 | G7 | app 與全部子程序零非 loopback 出站；無 HTTP listener | 實機 `scripts/p7_offline_check.ps1`（輪詢流程行程樹的 TCP／UDP）+ `tests/security/test_no_listener.py::test_no_listening_sockets`（重複執行流程期間背景輪詢至少 3 次〔每輪約 1–2 秒〕與結束後，測試行程與 worker 整棵行程樹沒有任何 socket，含 loopback）、`::test_connection_check_detects_sockets`、`::test_connection_check_covers_child_processes`（對照） | T01、S02–S06 | 自動測試 PASS（本機 Windows）、CI run 42150652779 雙平台（Windows 552 passed、macOS 549 passed）；Windows 實機 PASS（2026-11-11，Sockets seen 0，P8 報告 §6）；macOS 實機 NOT RUN |
| G7-03 | G7 | 惡意樣本不啟動外部程式／連線 | `tests/security/test_malicious.py::test_no_external_launch`（5 組：S02–S06；S06 Launch 若執行會建立 sentinel 檔）、`tests/security/test_sandbox.py::test_worker_cannot_spawn_processes`、`::test_spawn_hook_works_without_job`（對照） | S02–S06 | PASS（本機 Windows）、CI run 42150652779 雙平台（Windows 552 passed、macOS 549 passed）；macOS 子行程限制 NOT RUN（ADR-0024 缺口） |
| G7-04 | G7 | worker 逾時可停止、崩潰可重啟 | `tests/security/test_worker_limits.py::test_basic_timeout_and_cancel`、`::test_worker_crash_recovers`（P1）、`tests/security/test_sandbox.py::test_worker_dies_with_main_process`、`tests/unit/test_replay_batches.py`（2 個測試、3 項）、`tests/gui/test_p7_ui.py::test_shutdown_wait_is_bounded` | T01 | PASS（本機 Windows）、CI run 42150652779 雙平台（Windows 552 passed、macOS 549 passed）；隨主行程終止 macOS NOT RUN |
| G7-05 | G7 | 日誌不洩漏 sentinel、原文、密碼、完整路徑 | `tests/security/test_logging.py::test_no_sentinel_in_logs`、`::test_cli_stderr_has_no_sentinel`（2 組） | T01、S01–S03、U02 | PASS（本機 Windows）、CI run 42150652779 雙平台（Windows 552 passed、macOS 549 passed） |
| G7-06 | P7 | 限制初值：200 MB、500 頁、50 MP、30 秒、2 GB；載入前／解析中限制 | `tests/security/test_p7_limits.py`（11 項：Flate 炸彈、ASCII85＋Flate、LZW 估上限、一般串流、CMap 線性、50 MP 影像、毀損 Flate、bfrange 陣列線性、未塗繪路徑點數、文件層級超限仍可渲染且頁面超限仍拒絕、墨跡檢查像素上限）、`tests/security/test_sandbox.py::test_memory_limit_controlled`、`tests/security/test_worker_limits.py::test_file_size_and_page_limits`（P1）、`tests/security/test_ipc_fuzz.py`（32 項，含請求總逾時）、`tests/security/test_malicious.py[S03]` | S03、S04 | PASS（本機 Windows）、CI run 42150652779 雙平台（Windows 552 passed、macOS 549 passed）；記憶體上限 macOS NOT RUN（ADR-0024 缺口） |
| G7-07 | P7 | OS 沙箱／權限評估與缺口報告 | ADR-0024 §2、reports/P7 §8 文件審查 | — | 文件完成，待獨立核對 |

## G8：打包、實機與發布候選（P8，兩平台實機）

| 需求 ID | spec | 需求 | 預定 test ID | fixture | 狀態 |
| --- | --- | --- | --- | --- | --- |
| G8-01 | G8 | 乾淨 VM／實機無 Python、無網路可安裝並完成核心流程 | 實機驗收清單 S01–S15（Windows Sandbox，`scripts/p8_sandbox.ps1`）＋ `packaging/build_release.py` 打包結果自我檢查 | T01、F02、I01、B01 | 自我檢查 CI 雙平台 PASS；Windows 實機 PASS（2026-11-10～12，S12 NOT RUN；S14 新版重測僅口頭回報；`reports/P8/acceptance.md`）；macOS NOT RUN |
| G8-02 | G8 | 兩種 PDF 閱讀器正常開啟輸出 | 實機驗收清單 R01–R03（Acrobat Reader、Edge） | T05、F06、I01、B03 | Windows 實機 PASS（2026-11-11） |
| G8-03 | G8 | 完整支援矩陣 100%；61 fixture 與 12 盲測結果（依 ADR-0012 為 11 份，U06 無法製作） | `tests/integration/test_release_matrix.py`（49＋1 項）＋ `peditor blind-run`（`tests/integration/test_cli_blind.py`） | 全部 | 矩陣 PASS（本機）；盲測 NOT RUN（工程師 2026-11-11 決定附條件發布，日後補測） |
| G8-04 | G8 | 已知缺陷清單、SBOM、LICENSE、相依來源與版本、卸載／草稿清理說明 | `docs/release/`、`packaging/sbom/`、`THIRD_PARTY_NOTICES.md` 文件審查 | — | 文件完成；授權核對待負責人 |
| G8-06 | P8 實機 S10 | 編輯面板內容可捲動、「套用」固定在底部；前後對照圖限高；浮動面板高度不超出螢幕；面板顯示或叫回時底部不超出螢幕可用範圍；視窗標題顯示安裝包建置 commit | `tests/gui/test_layout.py::test_apply_button_visible_on_short_panel`、`::test_floating_panel_kept_above_taskbar`、`::test_build_id_in_title` | I01、T01 | PASS（本機 Linux offscreen）、CI run 42773024799 雙平台；Windows 實機 S10 PASS（安裝包推定 57ab13a，P8 報告 U7） |
| G8-07 | P8 實機 S13、ADR-0027 | 有未另存修改時，關閉視窗或開啟另一份檔案前詢問「另存／不儲存／取消」；另存成功才繼續，取消或另存失敗停在原文件；改了又復原、復原草稿後也算未另存 | `tests/gui/test_unsaved.py`（9 項）、`tests/gui/test_drafts_ui.py::test_close_window_while_busy`（進行中不詢問） | F04、T01 | PASS（本機 Linux offscreen）；Windows 實機 S13b PASS（2026-11-12，安裝包推定 d702e29） |
| G8-08 | P8 實機回報（2026-11-12）、ADR-0018 §1 | 同一運算子中間的純插入錨定在前一個字形之後，取代其與下一個字形之間原有的位移（例如先前刪字留下的空白）；模式 A、B 皆同 | `tests/integration/test_edit_text.py::test_insert_into_gap_after_deletion`（各／每） | T05 | PASS（本機 Linux）；Windows 實機待驗 |
| G8-09 | ADR-0028、P8 實機回報 | 新字較寬時同一行後面的字往右推（較窄往左收），可延伸到頁面右緣、同一行其他內容或垂直線之前；指定區域內的字不被推出區域；影像比對以擴大後的改動區為準 | `tests/integration/test_edit_text.py::test_following_glyphs_shift`（G2-19 改寫）、`::test_push_extends_to_right_limit`、`tests/integration/test_edit_multi.py::test_multi_operator_change`、`tests/integration/test_visual.py::test_changed_page_outside_mask_threshold` | T05、B01、F04、T02、T01 | PASS（本機 Linux）；Windows 實機待驗 |
| G8-05 | P8 | 標明 macOS 最低支援版本 | ADR-0025 §3（15.0、Apple Silicon） | — | 完成 |

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
