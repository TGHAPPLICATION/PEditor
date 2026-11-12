# P8 關卡報告：打包、實機與發布候選

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段的安裝包是**未簽署的測試包**，不是正式部署（spec P8、ADR-0025）。

## 1. 階段／commit／日期

- 階段：P8　分支：`p8-release`　commit：`aa98cf6`（發布建置腳本、CI release job）、`8be8f1d`（P4 U12）、`ca3968a`（支援矩陣測試、Inno Setup 6.7.1）、
  `e8ca31d`（Windows bootloader 由原始碼編譯）、`d224591`（盲測工具）、`6abe8b7`（ADR-0025、發布文件、SBOM、Sandbox 腳本）、`ffc51a3`（實機驗收清單）、`4a56661`（實機發現：不支援行的介面處理）、`716d1f3`（頁面縮放）、`9aba032`（浮動編輯面板、Ctrl+F 尋找、選單）、`2ab591a`（沒有 ToUnicode 時顯示 MuPDF 擷取文字）、
  `0b821ff`、`57ab13a`（實機 S10：編輯面板「套用」被擠出畫面；視窗標題顯示建置 commit）
  日期：2026-11-06（自動化部分）、2026-11-10～11-11（Windows 實機驗收）
- 只改報告、traceability、THREAT_MODEL 或 CI 紀錄的 commit 依 P4 慣例不列。
- S1／S2 決定（工程師 2026-11-06「照建議」）：Windows 用 Inno Setup、macOS 用 CI 建 app／DMG 不簽署、乾淨環境用 Windows Sandbox、
  閱讀器用 Acrobat Reader 與 Edge、盲測由保管人以離線腳本執行、U12 修正、U14 照實記錄、P5 U3 列已知缺陷、瘦身有實測才做、發布文件與 SBOM 重產。
  同日防毒移除本機建置的 `PEditor.exe` 後，處理方向「照建議」（ADR-0025 §4：A 原始碼編譯 bootloader、B 簽章列為正式散布前提、C 回報誤判與白名單）。
- 撰寫：Claude Code；審查：待工程師；獨立核對：待（CLAUDE.md：由未參與實作的子代理人核對）

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；PySide6 6.11.2；fontTools 4.66.0；PyInstaller 6.22.3；Noto Sans TC（ADR-0008） |
| Windows Sandbox（製作機上，`scripts/p8_sandbox.ps1`） | 同主機 OS；沙箱內無網路、無 Python | 同 P0 | 只有安裝包（見 §4 實機驗收用安裝包） |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest x64 | GitHub 標準 runner | 套件同上（`uv.lock`）；Inno Setup 6.7.1（Chocolatey）；release 以原始碼重建 PyInstaller 6.22.3 |
| CI macos | macos-15 arm64 | GitHub 標準 runner | 套件同上；DMG 以 `hdiutil` |

相依沒有變更（`uv.lock`、`pyproject.toml` 未改）；fixture 未重產。建置期新增 Inno Setup（不進產品執行期，ADR-0025 §2）。

## 3. 需求 → test ID → fixture／hash → 結果

| 需求 ID | test ID／證據 | 環境 | 結果 |
| --- | --- | --- | --- |
| G8-01 乾淨環境、無 Python、無網路可安裝並完成核心流程 | 實機驗收清單 S01–S15（Windows Sandbox，`scripts/p8_sandbox.ps1`）；打包結果自我檢查（`packaging/build_release.py`：`--smoke`、T01 模式 A、F02 模式 B 經打包後 worker） | CI 自我檢查；實機 | 自我檢查 CI 雙平台 PASS；**Windows 實機 PASS**（S01–S11、S13、S13b、S14、S15；S12 NOT RUN；S06、S13、S13b、S14 於 11/12 以 ADR-0027 新版重測；S04c、S05 在 `c06e5aa` 上測，新版面板未重看，U6）；macOS 實機 NOT RUN |
| G8-02 兩種 PDF 閱讀器正常開啟 | 實機驗收清單 R01–R03（Acrobat Reader、Edge） | 實機（主機） | **PASS**（R01–R03，2026-11-11） |
| G8-03 支援矩陣 100%；fixture 與盲測 | `tests/integration/test_release_matrix.py`（49 份 available 經 worker 完整判定＋1 項涵蓋檢查）；盲測 `peditor blind-run`（`tests/integration/test_cli_blind.py`：輸出不含文件內容） | 本機 | 矩陣 PASS（49／49）；**盲測 11 份 NOT RUN（工程師 2026-11-11 決定本輪略過）**；U06 無法製作（ADR-0012） |
| G8-04 已知缺陷、SBOM、LICENSE、相依、卸載／草稿清理 | `docs/release/known-issues.md`、`packaging/sbom/sbom-runtime.cdx.json`、`LICENSE`、`THIRD_PARTY_NOTICES.md`、`docs/release/dependencies.md`、`docs/release/install.md` | 文件 | 文件完成；**授權核對待負責人**（ADR-0002） |
| G8-05 macOS 最低支援版本 | ADR-0025 §3：15.0、Apple Silicon（pikepdf 10.14.0 只有 `macosx_15_0_arm64` wheel） | 文件 | 完成 |
| G8-06 實機 S10：編輯面板「套用」不被擠出畫面 | `tests/gui/test_layout.py::test_apply_button_visible_on_short_panel`、`::test_floating_panel_kept_above_taskbar`、`::test_build_id_in_title` | 本機 offscreen、CI；實機 | 自動測試 PASS；實機 S10 PASS（安裝包推定 `57ab13a`，U7） |
| P4 U12 | `tests/gui/test_shortcuts.py::test_all_standard_bindings_tooltips_and_focus` | 本機；實機 | PASS；實機 S08、S09 PASS |
| P4 U14 套用中取消 | `tests/gui/test_e2e.py::test_cancel_does_not_commit` | 本機 offscreen；實機 | offscreen PASS；**實機 S12 NOT RUN**（套用太快來不及按 Esc，與 P4 相同） |
| P4 U11／ADR-0020 §5 草稿 | `tests/gui/test_drafts_ui.py`；實機 S13（強制結束後重開詢問草稿）、S14（另存後關閉不再詢問） | 實機 | PASS（S13 依修訂後步驟重測，見 §7） |
| P5 U2／U5 半透明圖片替換 | 實機 S10、R03 | 實機 | PASS |
| P6 U5 儲存格與手動選格 | 實機 S11 | 實機 | PASS |
| P7 附條件 G7-01、G7-02（Windows 實機斷網、零出站） | `scripts/p7_offline_check.ps1`（實機驗收清單 P01） | 實機（主機，網路中斷） | **PASS**（§6） |

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
- 本機全套 → exit 0，612 passed、1 skipped（bcd6059，實機發現與工程師要求處理後）。CI run [42170637580](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42170637580)（commit `bcd6059`）test 與 release 雙平台 success；Windows 安裝包 SHA-256 `c63b0911f1b9674076aca72d93bb98c6309e6759a0cac8dd734b251cce40e64d`（已被下一版取代）。
- 本機全套 → exit 0，614 passed、1 skipped（c06e5aa，方案 A 後）。CI run [42174486671](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42174486671)（commit `c06e5aa`）test 與 release 雙平台 success；Windows 安裝包 SHA-256 `1c6ba32c7406c4d93ae143eb18864d9a44d84c1b78938e03547c859f1e7fa92f`——S01–S09 的實機驗收用此版；之後 `0b821ff`、`57ab13a` 修改了程式，S10 以後用的版本見下方「實機驗收」。
- 反向驗證：P8-M1（重做只綁第一組標準鍵）、P8-M2（套用後不移焦點）都被 `test_shortcuts.py` 抓到；P8-M3（格支援時不看行的判定）、P8-M4（不能改的行仍預填）、P8-M5（不顯示□）都被 `test_cell_ui.py::test_unsupported_line_not_previewable` 抓到。
- **ADR-0027 關閉前提醒（2026-11-11，工程師決定並確認設計）**：`MainWindow` 記錄開檔與另存成功時的版本，不同即視為未另存；
  關閉或開啟另一份檔案前詢問「另存…／不儲存／取消」；另存成功才繼續；復原草稿後視為未另存；工作進行中關閉不詢問（P4 U11）。
  測試 `tests/gui/test_unsaved.py`（9 項）；`tests/gui/conftest.py` 的 `make_window` 預設回答「不儲存」，避免既有測試被對話框擋住。
  反向驗證：關閉不詢問、換檔不詢問、另存後不更新已存版本、「不儲存」不生效、復原草稿視為已存，都被抓到。
  本工作環境全套：ruff 通過；pytest 622 passed、4 skipped、1 failed（同上 fixture 位元重現，環境差異）。
  CI run [42997750865](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42997750865)（`d702e29`）test 與 release 雙平台 success；實機重測用此版安裝包（標題 `PEditor 0.0.1（d702e29）`）。
- **實機驗收（2026-11-10～11-11）**：清單與結果見 `reports/P8/acceptance.md`。
  - CI run [42766515136](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42766515136)（`0b821ff`）、
    [42773024799](https://github.com/TGHAPPLICATION/PEditor/actions/runs/42773024799)（`57ab13a`）test 與 release 雙平台 success。
    安裝包 SHA-256 未取回（工作環境無法下載 CI artifact）；工程師以 A02 核對 SHA256SUMS.txt。
  - 實機驗收用安裝包依結果時間對應（工程師未逐項回報視窗標題）：S01–S09（11/10 10:19–11:22，台北時間）為 `c06e5aa`；
    S10（11/10 16:02）晚於 `57ab13a` release 完成（15:15），推定為 `57ab13a`；S11–S15、R01–R03（11/11）與 S13 重測推定為 `57ab13a`。
    `0b821ff`／`57ab13a` 只改編輯面板版面、視窗標題與建置腳本，S01–S09 的結果不受影響，但 S04c（浮動面板）與 S05（預覽）的畫面已有變動，未在新版重看。
  - 本工作環境（Linux 容器）全套：`uv run ruff check . && uv run ruff format --check . && uv run pytest -q` → ruff 通過；
    pytest 613 passed、4 skipped、**1 failed**（`tests/integration/test_fixtures.py::test_generator_reproduces_committed_bytes`；
    改動前的 `c2493df` 在同一環境也失敗，屬環境差異，CI 雙平台通過）。這不是 Windows 製作機證據。
- **工程師回報（2026-11-06）：編碼問題仍未解決**——`4a56661` 後亂碼改成「□」、不能預覽，但文字仍看不到也不能改。查證：字型為標楷體 Type0、Identity-H、Adobe-CNS1-3、沒有 ToUnicode；MuPDF 依內建字集表擷取正確。依 ADR-0011 判為拒絕是既定範圍，讓它可編輯屬擴大支援範圍。工程師決定「照建議」：方案 A（`2ab591a`）——目標與儲存格的行另附 `display_text`（對應不到的字改用 MuPDF 在同一位置擷取的字），面板顯示並註明「MuPDF 擷取，僅供參考」，判定與定位仍用 `text`（該格仍 `reject`）；測試 `test_analyzer.py::test_display_text_for_unmapped_glyphs`、`test_cell_ui.py::test_display_text_shown_for_reference`；反向驗證 P8-M12、P8-M13 都被抓到。方案 B 寫成 ADR-0026（工程師 2026-11-06 決定採 B0、B2 另段評估）：該 PDF 的子集字型沒有 cmap 與字形名稱，原設想的交叉驗證做不到，建議維持拒絕，另段評估字形形狀比對。已知缺陷 F10。
- **工程師要求（2026-11-06）：編輯面板浮動、尋找改為 Ctrl+F**——編輯與搜尋佔空間。`9aba032`：編輯面板改為 QDockWidget，預設浮動在視窗右側，可拖動、貼回邊緣或關閉，「檢視 → 編輯面板」切換，選取內容時自動叫回；尋找移出面板，改為選單「編輯 → 尋找…」（平台標準 Find 鍵，Windows 為 Ctrl+F），小型浮動視窗、Enter 送出，不放工具列；新增「檔案」「編輯」「檢視」選單（與工具列共用動作）。`test_e2e.py` 的尋找改由選單開啟尋找框（介面變更，預期不變）。測試 `tests/gui/test_layout.py`（2 項）；反向驗證 P8-M9（面板不浮動）、P8-M10（選取時不叫回）、P8-M11（尋找也放工具列）都被抓到。
- **工程師要求（2026-11-06）：頁面縮放**——文件字很小時看不清楚。`716d1f3`：放大、縮小、實際大小、符合寬度（工具列與平台標準快捷鍵、Ctrl＋0），Ctrl＋滾輪；25%–400%；放大停止 300 ms 後以 min(300 DPI, 100 DPI×縮放) 重新渲染該頁（字不糊），換頁或文件變動時丟棄結果；點選判定用場景座標，縮放不影響。測試 `tests/gui/test_zoom.py`（5 項）；反向驗證 P8-M6（不套用縮放轉換）、P8-M7（放大不重新渲染）、P8-M8（滾輪不縮放）都被抓到。實機清單 S04b PASS（11/10，`c06e5aa`）。
- **工程師實機發現（2026-11-06）**：以 CI 安裝包開啟一份外部下載的公開 PDF（非盲測、不入 repo），表格儲存格的選取內容、行選單與新文字欄顯示 U+FFFD 亂碼，且「預覽」可按。查證：該字型（標楷體，Type0）沒有 ToUnicode，文字目標與儲存格的每一行都正確判為 `UNSUPPORTED_ENCODING`，實際規劃 `ready: false`，**沒有誤標成可編輯**；問題在介面：選取儲存格時只看格的結構判定（support），沒看所選行的判定，並把對應不到的字（U+FFFD）原樣顯示與預填。`4a56661` 修正：以所選行的判定為準（不能預覽、直接顯示原因）、不能改的目標不預填新文字、對應不到的字顯示為「□」。我最初未查證就說「違反錯誤標成可編輯率 0%」，查證後更正。

## 5. 真修改證據

不適用（P8 沒有新增編輯功能）。打包後的真修改以自我檢查的 T01、F02 另存驗證通過為證據。

## 6. 資料完整性與資源／出站紀錄

- **P7 附條件 G7-01、G7-02（實機清單 P01，2026-11-11 16:38 台北時間）**：工程師於製作機中斷網路後執行（16:38 為摘要的執行時間，16:42 為清單填寫時間）
  `scripts\p7_offline_check.ps1`（原始碼 `p8-release` zip，依下載時分支最新版推定為 `57ab13a`；zip 無 git，摘要的 Commit 欄空白）。
  摘要：Windows 11 Pro 10.0.26300；Up 的網路介面 1 個，為 `vEthernet (Default Switch)`（Hyper-V 虛擬介面，Windows Sandbox 使用），
  Wi-Fi、乙太網路與兩個 Fortinet VPN 介面皆 Disconnected；Flow exit code 0、`FLOW-OK`；10 輪、13.7 秒；
  socket 輪詢 26 次（**平均間隔 0.53 秒**，腳本設計為 100 ms）；行程樹最多 6 個；**Sockets seen 0**（含 loopback 與 listener）。
  `flow.json`：T01 另存成功（all_saved true）；S02、S05、S06 `ACTIVE_CONTENT`，S03 `RESOURCE_LIMIT`（不渲染），S04 `MALFORMED_DOCUMENT`；
  `sentinel_files` 為空（S06 的 Launch 未被執行）。
  判定 PASS。輪詢較設計稀疏，短於約 0.5 秒的連線嘗試可能漏看，由自動測試（audit hook、Job Object）補足。

- 打包後 worker：自我檢查的 `edit-text` 經打包後的 `--worker` 子命令執行；Windows 上在 Job Object 內以 1 個行程執行（打包後沒有 venv 轉介程式）——
  P1、P7 帶入的「打包後 worker」驗證以此完成（Windows 與 macOS 皆在 CI）。
- 模式 B 字型：F02 的自我檢查清除 `PEDITOR_MODE_B_FONT`，只能用打包進去的字型（SHA-256 由 `fontb.py` 驗證）。

## 7. 限制、阻擋、未測項目

- **防毒**：2026-11-06 製作機的防毒移除了本機建置的 `PEditor.exe`（PyInstaller 預編譯 bootloader、未簽署）；偵測名稱與防毒產品待工程師提供。
  CI 的 Windows release 已改以原始碼重建同版 PyInstaller（log：`Building pyinstaller==6.22.3`、`PYINSTALLER_COMPILE_BOOTLOADER=1`；
  log 中沒有直接看到 bootloader 編譯輸出，是否確實重新編譯無法確認）。實機清單 A01（2026-11-06）：下載 CI 安裝包時防毒沒有攔截，PASS；
  只代表製作機的防毒，不代表其他機關電腦。
- **Windows 實機**：A01–A03、S01–S11、S13、S13b、S14、S15、R01–R03、P01 PASS；**S12（P4 U14）NOT RUN**（套用太快來不及按 Esc，只有 offscreen 證據）。
- **ADR-0027 新版重測（2026-11-12，台北時間 15:05–15:08）**：S06（依新步驟用 T05）、S13（強制結束後詢問草稿）、S13b（關閉前提醒：取消不關、另存後自動關閉、換檔詢問並可不儲存）PASS；
  S14 工程師回報「測試都通過了」，但頁面紀錄未更新（仍為 11/11 舊版的 PASS，重按會取消勾選），依工程師口頭回報記為重測通過。
- **實機發現（S10，2026-11-10）**：圖片替換預覽後，前後對照圖把「套用」擠出畫面（浮動面板高 720 px，加上預覽後內容更高，超出沙箱螢幕）。
  `0b821ff`：面板內容改捲動、「套用」固定底部、前後對照圖限高 160 px、首次顯示依螢幕縮短面板；工程師回報仍被遮後
  `57ab13a`：面板每次顯示或叫回都依所在螢幕可用範圍縮短，並在安裝包視窗標題顯示建置 commit（工程師無法分辨裝的是哪一版）。
  第一次重測的「仍被遮」無法確定是修正不足或裝到舊安裝包（當時標題沒有版本）。新版重測 PASS。
- **清單步驟錯誤（S13，2026-11-11）**：原步驟「改一處不另存、關閉視窗，重開應詢問草稿」與 ADR-0020 §5（正常關閉刪除草稿，P4 W31 已實測）矛盾，
  首測 FAIL。程式未改；步驟改為 `taskkill /IM PEditor.exe /F` 模擬當機。第二次仍未出現詢問，查證：工作管理員「結束工作」或不加 `/F` 會先送關閉訊息，
  走正常關閉並刪除草稿；本工作環境以 SIGKILL 結束後草稿保留可列出。工程師以 `/F` 重測，草稿檔在強制結束前後都存在，重開出現詢問，PASS。
- **盲測 11 份**：NOT RUN。工程師 2026-11-11 決定本輪略過（保管人未執行）；G8「12 盲測結果」（ADR-0012 為 11 份）未滿足。
- **macOS 實機**：NOT RUN（ADR-0003）；DMG 只在 CI 建置與自我檢查。
- **授權核對**（ADR-0002）：待負責人。
- 安裝包未簽署；SmartScreen／Gatekeeper 會警告（ADR-0025）。

## 8. 安全審查

- CLAUDE.md 規定的 vuln-scan／triage 時點是 P1、P2、P3、P7，P8 沒有規定：**NOT RUN**。
- `THREAT_MODEL.md`：T8（竄改的安裝包）待更新——安裝包附 SHA-256，未簽署；§6「端點防護會阻擋未簽章執行檔」已有實例。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 處理 |
| --- | --- | --- | --- |
| U1 | 防毒誤判未簽署的執行檔；原始碼編譯 bootloader 的效果未知 | 機關電腦可能無法安裝 | A01 PASS（製作機下載 CI 安裝包未被攔）；先前被移除的本機建置之偵測名稱仍待工程師；正式散布前提為簽章（ADR-0025 §4） |
| U2 | 盲測、授權核對需人工；Windows 實機驗收已完成（S12 NOT RUN） | G8 要求盲測 | **盲測：附條件發布**（工程師 2026-11-11 決定；保管人日後補測 11 份，結果寫回本報告）；授權：待負責人 |
| U3 | macOS 實機 NOT RUN | G8 的 macOS 部分 | 待工程師決定（附條件） |
| U4 | ADR-0026：沒有 ToUnicode 的 CID 字集字型是否納入編輯 | 這類政府表格不能修改 | **維持拒絕（B0），B2 另段評估**（工程師 2026-11-06「照建議」）；使用者確認的整行替換 **B3 列下一版**、整份統一換字型不採用（工程師同日決定） |
| U5 | 改了沒存就按 ✕，或直接開啟另一份檔案：依 ADR-0020 §5 草稿被刪，修改消失且沒有提醒 | 使用者可能遺失修改 | ADR-0027 已接受並實作；**Windows 實機 S13b PASS**（11/12）；剩「工作進行中關閉不詢問」列 F11 |
| U6 | S05 備註「預覽時字數太多，很擁擠看不到預覽」（`c06e5aa`） | 預覽可讀性 | 工程師 2026-11-11 確認新版（`0b821ff` 起限制前後對照圖高度、面板可捲動）已改善；未另做實機項目 |
| U7 | 實機項目用的安裝包版本未逐項以視窗標題記錄 | 證據對應版本 | 11/10 下午～11/11：推定 `57ab13a`（工程師「不確定，應該是」）；11/12 重測：工程師依指示安裝 run 42997750865（`d702e29`）或最新 run（`8f88e25`，程式相同），備註未寫標題，**仍屬推定** |
| U8 | P01 輪詢平均 0.53 秒，較設計 100 ms 稀疏 | 極短連線嘗試可能漏看 | 由自動測試補足；照實記錄 |
| U9 | S06 的 PASS（11/10 10:40）早於清單 10:50 修訂（S04–S07 改用 T05） | S06 證據 | 工程師 11/11 確認不是用 T05；**11/12 以新安裝包依新步驟重測 PASS** |
| U10 | 工程師 11/11 在對話中回報主機上找不到 R01–R03 要開的輸出檔，R01–R03 的 PASS 紀錄在 11/11 15:45–15:53 | R01–R03 證據是否來自本輪輸出 | 工程師 2026-11-11 確認：R01–R03 是用重新另存的輸出檢查；找不到檔案是在那之前 |

## 10. 關卡結果

- **關卡結果：BLOCKED**。自動化部分與 Windows 實機驗收完成（S12 NOT RUN）、P7 附條件 G7-01／G7-02 Windows 實機 PASS；
  未滿足：授權核對（ADR-0002，待負責人）；
  macOS 實機（ADR-0003）。盲測 11 份 NOT RUN，工程師 2026-11-11 決定**附條件發布**（日後補測）。
- **下一段可開始：—**（P8 為最後一段；發布候選待工程師決定）。

## 11. 獨立核對紀錄

- 2026-11-11，未參與實作的子代理人（只讀）核對 `3126415`：程式修改（`0b821ff`、`57ab13a`）與報告描述、G8-06 三個 test ID、
  CI run 42766515136／42773024799 結論、ADR-0020 §5 與 `close_document` 行為、acceptance.md 合計 26 項（PASS 24、NOT RUN 2）均一致。
  指出 4 類問題，已於下一個 commit 修正：§4 過時的「實機驗收以此版為準（之後只改文件）」；頁面縮放實機項目狀態（S04b）未回填；
  S10、P01 的版本對應未標「推定」、G8-01 未附註 S04c／S05 在舊版測；F11 漏了「開啟另一份檔案」也會遺失修改；另補 P01 執行與填寫時間差。
  無法查證：本工作環境的測試數（核對者未重跑）、安裝包 SHA-256（未取回）、工程師自填的實機結果（無截圖）、驗收頁面原始檔（不在 repo）。
