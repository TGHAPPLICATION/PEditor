# P8 關卡報告：打包、實機與發布候選

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段的安裝包是**未簽署的測試包**，不是正式部署（spec P8、ADR-0025）。

## 1. 階段／commit／日期

- 階段：P8　分支：`p8-release`　commit：`aa98cf6`（發布建置腳本、CI release job）、`8be8f1d`（P4 U12）、`ca3968a`（支援矩陣測試、Inno Setup 6.7.1）、
  `e8ca31d`（Windows bootloader 由原始碼編譯）、`d224591`（盲測工具）、`6abe8b7`（ADR-0025、發布文件、SBOM、Sandbox 腳本）、`ffc51a3`（實機驗收清單）、`4a56661`（實機發現：不支援行的介面處理）、`716d1f3`（頁面縮放）、`9aba032`（浮動編輯面板、Ctrl+F 尋找、選單）、`2ab591a`（沒有 ToUnicode 時顯示 MuPDF 擷取文字）
  日期：2026-11-06
- 只改報告、traceability、THREAT_MODEL 或 CI 紀錄的 commit 依 P4 慣例不列。
- S1／S2 決定（工程師 2026-11-06「照建議」）：Windows 用 Inno Setup、macOS 用 CI 建 app／DMG 不簽署、乾淨環境用 Windows Sandbox、
  閱讀器用 Acrobat Reader 與 Edge、盲測由保管人以離線腳本執行、U12 修正、U14 照實記錄、P5 U3 列已知缺陷、瘦身有實測才做、發布文件與 SBOM 重產。
  同日防毒移除本機建置的 `PEditor.exe` 後，處理方向「照建議」（ADR-0025 §4：A 原始碼編譯 bootloader、B 簽章列為正式散布前提、C 回報誤判與白名單）。
- 撰寫：Claude Code；審查：待工程師；獨立核對：待（CLAUDE.md：由未參與實作的子代理人核對）

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；PySide6 6.11.2；fontTools 4.66.0；PyInstaller 6.22.3；Noto Sans TC（ADR-0008） |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest x64 | GitHub 標準 runner | 套件同上（`uv.lock`）；Inno Setup 6.7.1（Chocolatey）；release 以原始碼重建 PyInstaller 6.22.3 |
| CI macos | macos-15 arm64 | GitHub 標準 runner | 套件同上；DMG 以 `hdiutil` |

相依沒有變更（`uv.lock`、`pyproject.toml` 未改）；fixture 未重產。建置期新增 Inno Setup（不進產品執行期，ADR-0025 §2）。

## 3. 需求 → test ID → fixture／hash → 結果

| 需求 ID | test ID／證據 | 環境 | 結果 |
| --- | --- | --- | --- |
| G8-01 乾淨環境、無 Python、無網路可安裝並完成核心流程 | 實機驗收清單 S01–S15（Windows Sandbox，`scripts/p8_sandbox.ps1`）；打包結果自我檢查（`packaging/build_release.py`：`--smoke`、T01 模式 A、F02 模式 B 經打包後 worker） | CI 自我檢查；實機 | 自我檢查 CI 雙平台 PASS；**Windows 實機 NOT RUN（待工程師）**；macOS 實機 NOT RUN |
| G8-02 兩種 PDF 閱讀器正常開啟 | 實機驗收清單 R01–R03（Acrobat Reader、Edge） | 實機 | **NOT RUN（待工程師）** |
| G8-03 支援矩陣 100%；fixture 與盲測 | `tests/integration/test_release_matrix.py`（49 份 available 經 worker 完整判定＋1 項涵蓋檢查）；盲測 `peditor blind-run`（`tests/integration/test_cli_blind.py`：輸出不含文件內容） | 本機 | 矩陣 PASS（49／49）；**盲測 11 份 NOT RUN（待保管人）**；U06 無法製作（ADR-0012） |
| G8-04 已知缺陷、SBOM、LICENSE、相依、卸載／草稿清理 | `docs/release/known-issues.md`、`packaging/sbom/sbom-runtime.cdx.json`、`LICENSE`、`THIRD_PARTY_NOTICES.md`、`docs/release/dependencies.md`、`docs/release/install.md` | 文件 | 文件完成；**授權核對待負責人**（ADR-0002） |
| G8-05 macOS 最低支援版本 | ADR-0025 §3：15.0、Apple Silicon（pikepdf 10.14.0 只有 `macosx_15_0_arm64` wheel） | 文件 | 完成 |
| P4 U12 | `tests/gui/test_shortcuts.py::test_all_standard_bindings_tooltips_and_focus` | 本機 | PASS；實機 S08、S09 待執行 |

## 4. 執行命令、exit code、測試數

```
uv run python packaging/build_release.py --no-installer  → exit 0（Windows 製作機；self_check smoke ok、T01 mode A、F02 mode B；onedir 166.8 MiB）
uv run pytest -q tests/integration/test_release_matrix.py → exit 0，50 passed
```

- CI：run [42155653810](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42155653810)（commit `e8ca31d`）test 雙平台、release 雙平台 success：
  Windows `PEditor-0.0.1-windows-x64-setup.exe`（SHA-256 `913e443d…`，onedir 176.6 MiB）、macOS `PEditor-0.0.1-macos-arm64.dmg`
  （先前 run 42153657549 為 `60686e01…`，onedir 158.6 MiB），兩平台打包後自我檢查都通過。先前 run 42153657549（`aa98cf6`）
  Windows release 失敗：Chocolatey 沒有 Inno Setup 6.4.3，改鎖 6.7.1（`ca3968a`）。
- 本機全套：`uv run ruff check . && uv run ruff format --check . && uv run pytest -q` → exit 0，604 passed、1 skipped（Windows 製作機，e1969cc；POSIX 權限位元測試略過）。
- 本機全套 → exit 0，612 passed、1 skipped（bcd6059，實機發現與工程師要求處理後）。CI run [42170637580](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42170637580)（commit `bcd6059`）test 與 release 雙平台 success；Windows 安裝包 SHA-256 `c63b0911f1b9674076aca72d93bb98c6309e6759a0cac8dd734b251cce40e64d`——**實機驗收以此版為準**。
- 反向驗證：P8-M1（重做只綁第一組標準鍵）、P8-M2（套用後不移焦點）都被 `test_shortcuts.py` 抓到；P8-M3（格支援時不看行的判定）、P8-M4（不能改的行仍預填）、P8-M5（不顯示□）都被 `test_cell_ui.py::test_unsupported_line_not_previewable` 抓到。
- **工程師回報（2026-11-06）：編碼問題仍未解決**——`4a56661` 後亂碼改成「□」、不能預覽，但文字仍看不到也不能改。查證：字型為標楷體 Type0、Identity-H、Adobe-CNS1-3、沒有 ToUnicode；MuPDF 依內建字集表擷取正確。依 ADR-0011 判為拒絕是既定範圍，讓它可編輯屬擴大支援範圍。工程師決定「照建議」：方案 A（`2ab591a`）——目標與儲存格的行另附 `display_text`（對應不到的字改用 MuPDF 在同一位置擷取的字），面板顯示並註明「MuPDF 擷取，僅供參考」，判定與定位仍用 `text`（該格仍 `reject`）；測試 `test_analyzer.py::test_display_text_for_unmapped_glyphs`、`test_cell_ui.py::test_display_text_shown_for_reference`；反向驗證 P8-M12、P8-M13 都被抓到。方案 B 寫成 ADR-0026（提議、待人工確認）：該 PDF 的子集字型沒有 cmap 與字形名稱，原設想的交叉驗證做不到，建議維持拒絕，另段評估字形形狀比對。已知缺陷 F10。
- **工程師要求（2026-11-06）：編輯面板浮動、尋找改為 Ctrl+F**——編輯與搜尋佔空間。`9aba032`：編輯面板改為 QDockWidget，預設浮動在視窗右側，可拖動、貼回邊緣或關閉，「檢視 → 編輯面板」切換，選取內容時自動叫回；尋找移出面板，改為選單「編輯 → 尋找…」（平台標準 Find 鍵，Windows 為 Ctrl+F），小型浮動視窗、Enter 送出，不放工具列；新增「檔案」「編輯」「檢視」選單（與工具列共用動作）。`test_e2e.py` 的尋找改由選單開啟尋找框（介面變更，預期不變）。測試 `tests/gui/test_layout.py`（2 項）；反向驗證 P8-M9（面板不浮動）、P8-M10（選取時不叫回）、P8-M11（尋找也放工具列）都被抓到。
- **工程師要求（2026-11-06）：頁面縮放**——文件字很小時看不清楚。`716d1f3`：放大、縮小、實際大小、符合寬度（工具列與平台標準快捷鍵、Ctrl＋0），Ctrl＋滾輪；25%–400%；放大停止 300 ms 後以 min(300 DPI, 100 DPI×縮放) 重新渲染該頁（字不糊），換頁或文件變動時丟棄結果；點選判定用場景座標，縮放不影響。測試 `tests/gui/test_zoom.py`（5 項）；反向驗證 P8-M6（不套用縮放轉換）、P8-M7（放大不重新渲染）、P8-M8（滾輪不縮放）都被抓到。實機驗收清單待加一項。
- **工程師實機發現（2026-11-06）**：以 CI 安裝包開啟一份外部下載的公開 PDF（非盲測、不入 repo），表格儲存格的選取內容、行選單與新文字欄顯示 U+FFFD 亂碼，且「預覽」可按。查證：該字型（標楷體，Type0）沒有 ToUnicode，文字目標與儲存格的每一行都正確判為 `UNSUPPORTED_ENCODING`，實際規劃 `ready: false`，**沒有誤標成可編輯**；問題在介面：選取儲存格時只看格的結構判定（support），沒看所選行的判定，並把對應不到的字（U+FFFD）原樣顯示與預填。`4a56661` 修正：以所選行的判定為準（不能預覽、直接顯示原因）、不能改的目標不預填新文字、對應不到的字顯示為「□」。我最初未查證就說「違反錯誤標成可編輯率 0%」，查證後更正。

## 5. 真修改證據

不適用（P8 沒有新增編輯功能）。打包後的真修改以自我檢查的 T01、F02 另存驗證通過為證據。

## 6. 資料完整性與資源／出站紀錄

- 打包後 worker：自我檢查的 `edit-text` 經打包後的 `--worker` 子命令執行；Windows 上在 Job Object 內以 1 個行程執行（打包後沒有 venv 轉介程式）——
  P1、P7 帶入的「打包後 worker」驗證以此完成（Windows 與 macOS 皆在 CI）。
- 模式 B 字型：F02 的自我檢查清除 `PEDITOR_MODE_B_FONT`，只能用打包進去的字型（SHA-256 由 `fontb.py` 驗證）。

## 7. 限制、阻擋、未測項目

- **防毒**：2026-11-06 製作機的防毒移除了本機建置的 `PEditor.exe`（PyInstaller 預編譯 bootloader、未簽署）；偵測名稱與防毒產品待工程師提供。
  CI 的 Windows release 已改以原始碼重建同版 PyInstaller（log：`Building pyinstaller==6.22.3`、`PYINSTALLER_COMPILE_BOOTLOADER=1`；
  log 中沒有直接看到 bootloader 編譯輸出，是否確實重新編譯與能否避開誤判，待實機下載驗證，清單 A01）。
- **Windows 實機**（G8-01、G8-02、U12、P5 U2／U5、P6 U5、P4 U14、P7 附條件）：NOT RUN，待工程師依清單執行。
- **盲測 11 份**：NOT RUN，待保管人。
- **macOS 實機**：NOT RUN（ADR-0003）；DMG 只在 CI 建置與自我檢查。
- **授權核對**（ADR-0002）：待負責人。
- 安裝包未簽署；SmartScreen／Gatekeeper 會警告（ADR-0025）。

## 8. 安全審查

- CLAUDE.md 規定的 vuln-scan／triage 時點是 P1、P2、P3、P7，P8 沒有規定：**NOT RUN**。
- `THREAT_MODEL.md`：T8（竄改的安裝包）待更新——安裝包附 SHA-256，未簽署；§6「端點防護會阻擋未簽章執行檔」已有實例。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 處理 |
| --- | --- | --- | --- |
| U1 | 防毒誤判未簽署的執行檔；原始碼編譯 bootloader 的效果未知 | 機關電腦可能無法安裝 | 待工程師（偵測名稱、A01 結果） |
| U2 | Windows 實機驗收、盲測、授權核對都需人工 | G8 要求實機與盲測 | 待工程師／保管人／負責人 |
| U3 | macOS 實機 NOT RUN | G8 的 macOS 部分 | 待工程師決定（附條件） |
| U4 | ADR-0026（提議）：沒有 ToUnicode 的 CID 字集字型是否納入編輯；建議維持拒絕、另段評估字形形狀比對 | 這類政府表格不能修改 | 待工程師決定 |

## 10. 關卡結果

- **關卡結果：BLOCKED**。自動化部分完成（建置、自我檢查、支援矩陣、發布文件）；實機驗收、盲測、授權核對、獨立核對待執行。
- **下一段可開始：—**（P8 為最後一段；發布候選待工程師決定）。

## 11. 獨立核對紀錄

（待執行）
