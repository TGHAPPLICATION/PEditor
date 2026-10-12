# 追溯表：需求 → 關卡 → test ID

> 需求 ID 暫以「關卡-序號」編列（如 `G0-01`）；規格原文匯入後，改用原文的需求編號並保留對照欄。
> 狀態：`PASS`（已有測試且通過）、`CI`（僅 CI 證據）、`MANUAL`（人工驗收）、`NOT RUN`、`TODO`。

| 需求 ID | 需求 | 關卡 | test ID／證據 | 狀態 |
| --- | --- | --- | --- | --- |
| G0-01 | 相依以 lock 檔鎖定，CI 以 `--locked` 安裝 | G0 | `uv.lock`；ci.yml `Install (locked)` | PASS |
| G0-02 | Windows x64 與 macOS arm64 CI 跑 lint 與測試 | G0 | `.github/workflows/ci.yml` job `test` | CI |
| G0-03 | 空白 Qt app 可啟動（offscreen） | G0 | `tests/test_app_smoke.py::test_main_window_shows`、`::test_cli_smoke_exits_zero` | PASS |
| G0-04 | 打包後可啟動（smoke build） | G0 | `scripts/smoke_build.py`（CI 步驟 `Smoke build`） | CI |
| G0-05 | fixture manifest 60 筆、12 盲測、符合 schema | G0 | `tests/test_manifest.py::test_manifest_rows_match_schema`、`::test_manifest_counts` | PASS |
| G0-06 | 合成 fixture 可重現產生 | G0 | `tests/test_manifest.py::test_generator_is_deterministic`、`::test_generated_fixtures_open_as_expected`、`::test_cjk_subset_font_is_embedded` | PASS |
| G0-07 | 產品程式碼不含網路模組 | G0（P7 實機複驗） | `tests/test_offline_guard.py::test_no_network_imports_in_product_code` | PASS |
| G0-08 | 威脅模型建立 | G0 | `THREAT_MODEL.md` | MANUAL |
| G0-09 | 四項決策與架構寫成 ADR | G0 | `docs/adr/0001`–`0005` | MANUAL |
| G0-10 | Windows 實機執行 app 與測試 | G0 | 工程師實測（見 reports/P0.md） | NOT RUN |
| G0-11 | macOS 實機啟動 | G0 → G4 | ADR-0003：延至 P4 | NOT RUN |
| G1-01 | PDF 解析只在 worker 子行程 | G1 | TODO | TODO |
| G1-02 | capability report 對 manifest `expected`／`reason` 一致 | G1 | TODO | TODO |
| G2-05 | 模式 B 須證明舊內容已移除 | G2 | TODO | TODO |
| G3-01 | 儲存交易：中斷不毀損原檔 | G3 | TODO | TODO |
| G7-01 | 零出站連線（實機監測） | G7 | TODO | TODO |
