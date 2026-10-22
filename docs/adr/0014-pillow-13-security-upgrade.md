# ADR-0014：Pillow 升級至 13.0.0（Dependabot 安全警示）

- 狀態：已接受（2026-10-22，工程師選定選項 1、例外日期 2026-10-17）
- 日期：2026-10-22
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

GitHub Dependabot 對 `uv.lock` 鎖定的 Pillow 12.3.0 開出 9 項警示，修正版本皆為 13.0.0：

| # | 嚴重度 | GHSA | 摘要 |
| --- | --- | --- | --- |
| 1 | critical | GHSA-8g5g-8vmr-9782 | ImagingJpegDecode heap 溢位 |
| 2 | high | GHSA-c6hw-5grf-ff96 | TiffDecode tile／RGBA 路徑越界讀取 |
| 4 | high | GHSA-p4wg-p73j-c528 | 解析 PDF 頁面樹／trailer 鏈無限遞迴 |
| 5 | high | GHSA-pchr-8j38-3x4p | TIFF encoder ColorMap 越界讀取 |
| 6 | high | GHSA-q45j-58j2-45rg | TiffDecode 短 JPEG strip 回傳未初始化記憶體 |
| 8 | high | GHSA-65qm-jvmh-6pqg | GIF seek 於 DecompressionBombError 後保留尺寸（DoS） |
| 9 | high | GHSA-58r4-6rv3-gfh8 | `_imagingmorph` 零寬影像越界存取 |
| 3 | medium | GHSA-462x-pgg6-55fp | tiled TIFF copy4 越界讀取 |
| 7 | medium | GHSA-vx6w-vv9f-6gvg | EPS `load(scale)` 繞過解壓縮炸彈上限 |

相依來源與目前暴露面（2026-10-22 查核）：

- Pillow 非直接相依：由 pikepdf 10.14.0（執行期，`Pillow>=10.0.1`，無上限）與 reportlab 5.0.1（dev，fixture 產生器）帶入。
- `src/` 未匯入 Pillow；載入 `peditor.worker.analyzer`、`peditor.worker.server` 後 `PIL` 不在 `sys.modules`。
  pikepdf 只在 `PdfImage` 等影像 API 才延遲匯入 Pillow，產品目前未使用。
- 測試僅 `tests/integration/test_cli_analyze.py` 以 Pillow 讀取自產 PNG（可信輸入）。

因此目前**不可經使用者 PDF 觸發**，但：

1. PyInstaller 打包會把 Pillow 12.3.0 一併散布，SBOM 會列出含已知漏洞的元件。
2. P2 起的影像替換（I 群組、G2 之後各段）若經 pikepdf `PdfImage` 解碼使用者 PDF 內影像，JPEG／TIFF 相關漏洞
   （#1、#2、#3、#6）即直接落在 worker 的不可信輸入路徑上（THREAT_MODEL T1、T2）。

Pillow 13.0.0 發佈於 2026-10-16，晚於 `tool.uv.exclude-newer = "2026-09-28T00:00:00Z"`，依 CLAUDE.md 須以 ADR 處理。

## 選項

1. **只對 Pillow 開冷卻期例外**：`[tool.uv]` 加 `exclude-newer-package = { pillow = "2026-10-17T00:00:00Z" }`
   （uv 0.13.1 支援，已以 `uv lock --help` 核對），全域 `exclude-newer` 不變；`uv lock --upgrade-package pillow`。
   只有 Pillow 一個套件變動。
2. **全域 `exclude-newer` 往後移到 2026-10-17**：同時放行冷卻期內所有套件的新版本，變動範圍大，違反「只做必要變更」。
3. **暫不升級**：記錄暴露面為零並延到真正使用 Pillow 時處理；打包與 SBOM 期間持續帶著已知 critical 漏洞。
4. **在 P2 的設計中禁止產品使用 Pillow 解碼**：可降低暴露，但無法消除打包散布的已知漏洞元件，且限制 P2 實作選擇。

## 決策

採用選項 1（工程師 2026-10-22 確認）。

- 冷卻期例外只限 Pillow，日期定為 13.0.0 發佈次日；13.0.x 之後的修補版仍受全域冷卻期管制，需另以 ADR 調整。
- 不調整 pikepdf、reportlab 或其他套件版本。

## 後果

- `pyproject.toml` 新增 `exclude-newer-package`；`uv.lock` 只有 Pillow 版本與 hash 改變（PR 須以 diff 證明）。
- Pillow 13 為大版本：須跑完整回歸——`uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`、
  `uv run python scripts/gen_fixtures.py` 後確認 manifest hash 是否改變（reportlab 產生的 fixture 可能經 Pillow 嵌入影像；
  若 hash 改變須在報告列出原因），以及 `packaging/smoke_build.py`，並由 CI 補跑 Windows x64 / macOS arm64。
- `packaging/sbom/sbom-runtime.cdx.json` 與 `THIRD_PARTY_NOTICES.md` 若列有 Pillow 版本，須一併更新（Pillow 授權 MIT-CMU 不變）。
- `THREAT_MODEL.md` T1／T2 註明：產品若在 worker 內以 Pillow 解碼使用者影像，須另有大小／像素上限，並維持於本 ADR 的修補版以上。
- 若回歸失敗或 hash 有無法說明的改變，不合併，回到選項 3 或 4 重新評估。

## 回歸結果（2026-10-22，本機 Windows）

- `uv lock --upgrade-package pillow`：只有 `pillow 12.3.0 → 13.0.0` 與 `[options.exclude-newer-package]` 變動，其他 31 個套件不變。
- `uv run ruff check .`、`uv run ruff format --check .`：通過；`uv run pytest`：72 passed（同分支另補 G1-10 測試後為 73 passed）。
- `scripts/gen_fixtures.py`：21 份合成 fixture 中只有 U02 hash 改變。U02 以 AES-256 加密，salt／IV 每次隨機，
  同一 Pillow 版本連續重產兩次 hash 亦不同（`ca2623…` → `cf7497…`），與本次升級無關；其餘 20 份 hash 不變。
  重產結果未提交，manifest 維持原 hash。
- `packaging/smoke_build.py`：PEDITOR_SMOKE_OK，onedir 161.1 MiB。
- `THIRD_PARTY_NOTICES.md`、`packaging/sbom/sbom-runtime.cdx.json` 的 Pillow 版本改為 13.0.0；`THREAT_MODEL.md` T1 已註記。
- CI（Windows x64 / macOS arm64）：見 PR。
