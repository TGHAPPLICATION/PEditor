# P0 關卡報告：規格、環境與資料集

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：P0　分支：`claude/compassionate-mayer-4gov5x`　commit：`00288a3`（最後一次程式／腳本變更後的 CI 證據，§4）；之後的 commit 只改文件　日期：2026-10-12 起，2026-10-16 完成 Windows 實機驗證與審查
- 撰寫：Claude Code；審查：tghtaipei（PR #1 review 5545939500，2026-10-16）；獨立核對：未參與實作的 Claude 子代理人（§11）
- 輸入：規格 v1.0（已匯入為 `docs/spec.md` v1.1）、執行計畫書 v1.1；repo 已公開

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機 | Windows 11 Pro 10.0.26200（build 26200）x64 | 11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz；RAM 15.8 GB | Python 3.13.16；uv 0.13.1；PySide6-Essentials 6.11.2；PyMuPDF 1.28.2；pikepdf 10.14.0；PyInstaller 6.22.3；字型 SHA-256 相符 |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest（windows-2025）x64 | GitHub 標準 runner | Python 3.13.15；套件同下 |
| CI macos | macos-15 arm64（macOS 15.7） | GitHub 標準 runner（M1） | Python 3.13.15；套件同下 |
| Linux 開發容器 | Linux x86_64 | 雲端容器 | Python 3.13.16 |

鎖定版本（`uv.lock`；`exclude-newer = 2026-09-28`）：PyMuPDF 1.28.2、pikepdf 10.14.0、PySide6-Essentials 6.11.2；
測試工具 pytest 9.1.1、pytest-qt 4.5.0、pypdfium2 5.13.0、ReportLab 5.0.1、fontTools 4.66.0、PyInstaller 6.22.3。
字型：Noto Sans TC Regular（noto-cjk@f8d1575，sha256 `5bab0cb3…`）、Noto Serif TC VF（google/fonts@bd8f81d，sha256 `0077e18f…`）、Droid Sans Fallback（PyMuPDF 內建）。

## 3. 需求 → test ID → fixture／hash → 結果

完整對照見 `docs/traceability.md`（G0–G8、§7 與 §8 共 86 項，均已指定 test ID）。G0 逐條：

| 需求 ID | 內容 | 證據 | 環境 | 結果 |
| --- | --- | --- | --- | --- |
| G0-01 | 相依鎖定 | `uv.lock`；CI `uv sync --locked` | 容器、CI 雙平台 | PASS |
| G0-02 | 最小測試流程 | ci.yml job `test` | CI windows、CI macos | PASS（CI 證據） |
| G0-03 | 空白 app 啟動 | `tests/gui/test_app_smoke.py`（2 項） | 容器 offscreen、CI 雙平台 offscreen | PASS |
| G0-04 | 兩平台打包最小 Qt app | `packaging/smoke_build.py` | 容器、CI 雙平台 | PASS（CI 證據） |
| G0-05 | Windows 11 x64 實機啟動 | manual-steps §3；`scripts/p0_windows_check.ps1` 輸出（轉錄於 §4；原檔 `build/p0-check/summary.md` 只在操作者本機，不入 repo）；PR #1 review 5545939500 | Windows 實機 | PASS（操作者透過本機 Claude Code 執行 `scripts/p0_windows_check.ps1`，並以人工即時觀看確認 `uv run peditor` 與封裝後 `peditor.exe` 兩次視窗皆出現） |
| G0-06 | macOS Apple Silicon 實機啟動 | ADR-0003：P0–P3 以 CI macos-15 arm64 替代 | macOS 實機 | NOT RUN（無實機）；依 ADR-0003（已接受）以 CI macos-15 arm64 證據替代至 P3 |
| G0-07 | 61 份 manifest、群組 T12／F10／L8／I9／B8／U6／S8 | `tests/unit/test_manifest.py` | 容器、CI | PASS |
| G0-08 | ≥12 盲測、不進 repo | 同上 `::test_at_least_12_blind_fixtures_kept_offline` | 容器、CI；保管人 hash 清冊 | PASS（結構）；製作 11／12（2026-10-21 收到 hash 清冊，見 §6）；U06 無法製作（保管人確認），盲測數依 ADR-0012 接受 11 份 |
| G0-09 | ≥20 份可重現首批樣本、非單一產生器 | 21 份（PyMuPDF 14、ReportLab 5、PyMuPDF+pikepdf 1、加密 1）；`::test_generator_reproduces_committed_bytes` | 容器、CI 雙平台 | PASS |
| G0-10 | fixture hash 可驗證 | `::test_committed_fixture_hashes_match_manifest` | 容器、CI | PASS |
| G0-11 | 沒有正式 PDF | 全為合成內容；人工 fixture 規則見 manual-steps §4；PR #1 審查（2026-10-16，review 5545939500） | 人工審查 | PASS |
| G0-12 | 每個需求指定 test ID | `docs/traceability.md`；PR #1 審查（2026-10-16，review 5545939500） | 人工審查 | PASS |
| G0-13 | 嚴格 A 或允許 A/B 已記錄 | ADR-0001：允許 A/B、優先 A | 文件 | PASS |
| G0-14 | LICENSE、THIRD_PARTY_NOTICES、SBOM 草案 | `packaging/sbom/sbom-runtime.cdx.json`（7 元件） | 文件 | PASS（草案） |
| G0-15 | fixture 預期性質 | `tests/integration/test_fixtures.py`（雙引擎擷取、qpdf、理由碼性質、子集缺字） | 容器、CI | PASS |
| G0-16 | 離線靜態護欄 | `tests/security/test_offline_guard.py` | 容器、CI | PASS |
| G0-17 | 字型授權與來源可驗證 | `scripts/fetch_fonts.py`、ADR-0008 | 容器、CI | PASS |

首批 21 份合成 fixture（hash 前 12 碼）：

| fixture | 產生器 | 預期 | hash | fixture | 產生器 | 預期 | hash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | pymupdf | support | 65a4ebca20fe | L03 | pymupdf | support | a8b045e2972a |
| T02 | reportlab | support | 0c25d0dcbb3f | I01 | pymupdf | support | 7a8001d4d803 |
| T03 | pymupdf | support | 51ab60ba6650 | I02 | pymupdf | support | 3e241f7b6fef |
| T04 | reportlab | support | 6c60ba41cf1b | I03 | pymupdf | support | 7bd88c07864d |
| F01 | pymupdf | support | 856059b4cdf1 | B01 | pymupdf | support | 1a409bb195b5 |
| F02 | pymupdf | support（B） | 661ad2572758 | B02 | reportlab | support | 7861dc6039a9 |
| F03 | reportlab | reject GLYPH_MISSING | d0e6918195a0 | U01 | pymupdf | readonly NO_TEXT_LAYER | 29d8728efbee |
| F04 | pymupdf | support | 6dda72bbbb80 | U02 | pymupdf | reject ENCRYPTED_DOCUMENT | a2c282a74c2c |
| F05 | pymupdf+pikepdf | reject UNSUPPORTED_ENCODING | 6ba509976fbf | S01 | pymupdf | reject MALFORMED_DOCUMENT | 211847644e7d |
| L01 | pymupdf | support | bc67ee410ef5 | S02 | pymupdf | reject ACTIVE_CONTENT | 88e4c27ba76f |
| L02 | pymupdf | support | 0e744136f8ca | | | | |

## 4. 執行命令、exit code、測試數

```
uv sync --locked --all-groups            → exit 0
uv run python scripts/fetch_fonts.py     → exit 0（2 字型 SHA-256 相符）
uv run ruff check . && ruff format --check .  → exit 0
uv run pytest                            → exit 0，21 passed（Linux 容器）
uv run python packaging/smoke_build.py   → exit 0，PEDITOR_SMOKE_OK
```

最新 CI：run [38882924296](https://github.com/TGHAPPLICATION/PEditor/actions/runs/38882924296)（commit `00288a3`）雙平台通過；自 `7ca2eb3` 起 CI 改為執行 `scripts/p0_windows_check.ps1 -SkipLaunch`／`scripts/p0_macos_check.sh --skip-launch`，run [38874360160](https://github.com/TGHAPPLICATION/PEditor/actions/runs/38874360160) 的 Windows 摘要為 result PASS、21 passed、smoke 171.1 MiB。

較早的完整數據，CI run [38228037824](https://github.com/TGHAPPLICATION/PEditor/actions/runs/38228037824)（commit `06b8e0e`）：

| job | 平台 | 字型下載 | lint | pytest | smoke build |
| --- | --- | --- | --- | --- | --- |
| test (windows-latest) | Windows Server 2025（10.0.26100）x64，Python 3.13.15 | SHA-256 相符 | 通過 | 21 passed | PEDITOR_SMOKE_OK，169.9 MiB |
| test (macos-15) | macOS 15 arm64，Python 3.13.15 | SHA-256 相符 | 通過 | 通過（job success） | PEDITOR_SMOKE_OK，151.7 MiB |

合成 fixture 在 Windows、macOS 與 Linux 重產的位元組皆與提交檔相同（`test_generator_reproduces_committed_bytes`）。

Windows 11 實機（G0-05，2026-10-16，commit `7ca2eb3`）。以下轉錄自操作者本機的 `build/p0-check/summary.md`（該檔在 `.gitignore` 內，未入 repo）；視窗是否出現只有操作者的人工確認，佐證為 PR #1 review 5545939500：

```
uv sync --locked --all-groups            → exit 0（第1次因快取暫時性寫入衝突 os error 5 失敗，重試後成功）
uv run python scripts/fetch_fonts.py     → exit 0（2 字型 SHA-256 相符）
uv run ruff check .                      → exit 0
uv run ruff format --check .             → exit 0
uv run pytest                            → exit 0，21 passed
uv run python packaging/smoke_build.py   → exit 0，PEDITOR_SMOKE_OK，onedir 161.0 MiB
                                            （第1次因上次 sync 失敗漏裝 PyInstaller 而失敗，重跑 sync 後成功）
視窗檢查                                  → uv run peditor：操作者確認視窗出現；
                                            封裝後 peditor.exe：操作者確認視窗出現
```

第1次 `uv sync` 失敗為本機快取鎖定的暫時性問題（非程式問題），重跑後乾淨完成；因果與重試過程詳見
`build/p0-check/summary.md` 附註。依 CLAUDE.md 規則，此處如實記錄首次失敗與重試，未以 CI 證據冒充實機證據。

## 5. 真修改證據

不適用（P0 不實作編輯核心）。

## 6. 資料完整性與資源／出站紀錄

- fixture 位元組可重現：除 U02（AES 加密 key 隨機）外，重產與提交檔 SHA-256 完全相同。
- 出站：產品程式碼無網路模組（G0-16）；實機出站監測於 P7。

### 盲測 hash 清冊（2026-10-21）

由盲測保管人依 manual-steps §5.15 以 `Get-FileHash -Algorithm SHA256` 產生，只交付編號與 SHA-256；PDF 與答案卡未交給工程師或 Claude，Claude 未經手任何盲測檔案。製作人是否未參與實作，依工程師陳述，Claude 無法自行驗證。P8 盲測前保管人須在離線實機重算並逐行比對。

- 11 份盲測 PDF ＋ `S07-good`（S07 損毀前的對照原檔，不在 manifest）；12 筆 hash 皆為 64 位十六進位、互不相同，且與 `tests/fixtures/files/` 中任何已登記 fixture 都不相同。
- U06（XFA）：2026-10-21 保管人確認**無法製作**（單位內無 LiveCycle／AEM Forms Designer），依 manual-steps §5.12 標記；不列入清冊。

| fixture_id | SHA-256 |
| --- | --- |
| B07 | `22DAA1CBC14E41274FEA502DB5EB6CDA2BC3BDFA886248C003E010E1CB4FE50E` |
| B08 | `C803BA55097DF9A58C968FFED7E3516E771FAD1988AC699094CD66853A8DFEA5` |
| F09 | `7CA7854B670BFEB56391F5B6ED857A06EA695CC67B1BE5EB5B87BFF546CA55CA` |
| F10 | `4D87629F6E914ED2B849007F843F8EFFC6650F2C26750A337C3C4A73CD528C82` |
| I08 | `1129FAB720B690430E2B07F753E2F03ECF035A5FB44EC4A4D7EE58E76856D576` |
| L08 | `15CF52A95FCFF8D5CC1D82602A21C54CF172C7D5ABF798F08580BF0374741081` |
| S07-good | `FE169D09FB431DAC05443F7289C44609A959F7DD10395445DC10A5B8F3C82D67` |
| S07 | `D4C362C55241DD45E4C1720C6C4212751C2FDD0488C8C58CE40613AFE8C0807D` |
| S08 | `3B08A7475BEAD3AC50846ED528B4C44FA624DEB70AB648B10DF6F0780FABC44A` |
| T10 | `FF7D733AD2408C6BC6AD4CECF46AA00085713251D418326A6C0F71868258DE46` |
| T11 | `8B9A5F12C912E88761E8EC7E4EA4E68612EC939A017569B1B57C84BEA7DE4DC7` |
| T12 | `756FE387DDD9857CF21855F37A3B3A89FE2A11B7CC8A91B8B64E59639B083BC8` |

## 7. 限制、阻擋、未測項目

- macOS 實機啟動 NOT RUN（G0-06，依 ADR-0003 以 CI 證據替代）。
- 人工 fixture 24 份已登記（2026-10-20，PR #3）；盲測 11 份已製作並離線保管，U06 無法製作（§6），盲測數依 ADR-0012 接受 11 份；S03–S06 於 P7 以腳本產生。
- §8.2 視覺門檻「P0／P2 以基準實測後鎖定」：P0 無編輯引擎可量測，NOT RUN，於 P2 鎖定（X-05）。
- MuPDF 1.28 `subset_fonts()` 無法子集化 CFF 字型（Noto Sans TC），fixture 改以 fontTools 預先子集化；P2 模式 B 須沿用（ADR-0008）。
- Noto Serif TC 為 variable font，ReportLab 嵌入預設 instance（ExtraLight），字形偏細但不影響測試。
- smoke build 未瘦身（run 38228037824：Windows 169.9 MiB、macOS 151.7 MiB），P8 處理。
- 「不可改動區域」目前為文字描述（如「頁面其餘內容」）；P2 以 EditPlan 的 allowed_change_mask 轉為座標遮罩（spec §8.2「遮罩由預先 manifest／EditPlan 決定」）。
- fixture 原有 qpdf warning：合成 support／readonly 樣本皆為 0（`test_support_and_readonly_fixtures_pass_qpdf_check`）；人工樣本登記時須記錄，P1 加入欄位。

## 8. 安全審查

- `THREAT_MODEL.md`（harness `/threat-model` schema，bootstrap 模式）：10 項威脅，前五 T1 惡意 PDF 記憶體破壞、T2 IPC 攻陷主行程、T6 供應鏈、T8 竄改安裝包、T3 儲存毀損原檔。
- `/vuln-scan`：NOT RUN — P0 無解析／IPC 程式碼，依 ADR-0005 於 P1 結束前執行。
- 供應鏈控制：lock 雜湊、冷卻期、字型 SHA-256、Actions commit SHA 鎖定、`permissions: contents: read`。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | ADR-0003：G0 macOS 以 CI 證據替代、停止條件改為 P3 結束 | G0 能否宣告 PASS | 已接受（2026-10-12） |
| U2 | ADR-0006：第二解譯器用 PDFium 非 Poppler | §8.1 證據工具 | 已接受（2026-10-12） |
| U3 | ADR-0007：新增 4 個理由碼；JS／附件預設拒絕；可修復損毀檔預設拒絕 | P1 能力判定基準 | 已接受（2026-10-12） |
| U4 | ADR-0008：Noto Sans TC／Noto Serif TC | P2 模式 B 字型 | 已接受（2026-10-12） |
| U5 | 人工 fixture 預期值（I04、I07 等）於 P2 前鎖定（spec §5） | P1／P2 驗收 | 已決定（2026-10-16，ADR-0009） |
| U6 | ADR-0009：I04／I07 改為 support、新增 I09 補位拒絕樣本；fixture 總數 60→61 | P5 支援矩陣、G0-07 計數 | 已接受（2026-10-16，工程師） |
| U7 | ADR-0010：Word／LibreOffice 人工 fixture 使用 Windows 11 內建 Noto TC 可變字型（與 ADR-0008 鎖定版不同，嵌入未 instancing 的 VF） | G0-17 字型來源、P1 擷取、P2 模式 B | 已接受（2026-10-19，工程師） |
| U8 | ADR-0011：T09（Microsoft Print to PDF）ToUnicode 缺 0–9，預期由 support 改為 reject UNSUPPORTED_ENCODING | P1 能力判定須偵測不完整 ToUnicode；T 組 support 樣本少一份 | 已接受（2026-10-20，工程師） |
| U9 | 盲測 U06（XFA）無法製作，實際盲測 11 份，少於 spec §5／G8 的 12 份；且 repo 內沒有任何 XFA 樣本 | G8 盲測數量；XFA 拒絕路徑無實際樣本 | 已接受（2026-10-21，工程師）：ADR-0012 接受 11 份；XFA 拒絕以腳本合成檔測試，最晚 P7 |

人工待辦（詳細步驟見 `reports/P0/manual-steps.md`）：

- [x] GitHub：預設分支改 `main`、分支保護、secret scanning、Dependabot alerts、Actions 權限（2026-10-16 已執行並以 `gh api` 驗證生效）
- [x] 確認 ADR-0003、0004、0006、0007、0008（2026-10-12 負責人接受）
- [x] 確認人工 fixture 預期值（I04、I07），P2 前鎖定（2026-10-16，ADR-0009）
- [x] Windows 11 實機驗證（G0-05，2026-10-16 PASS）
- [x] 製作 24 份人工 fixture 並登記（2026-10-20，PR #3；ADR-0010、ADR-0011）
- [x] 盲測 11 份由保管人製作、離線保管，hash 清冊 2026-10-21 收到（§6）
- [x] 盲測 U06（XFA）：2026-10-21 保管人確認無法製作
- [x] 盲測數 11 < 12 的處理：ADR-0012 接受 11 份（2026-10-21）
- [ ] Claude 用量一週紀錄
- [ ] macOS 實機方案（11/16 前）

## 10. 關卡結果

- CI：run 38882924296（commit `00288a3`）雙平台通過
- **關卡結果：PASS**（除 G0-06 外，G0-01～G0-17 均有證據且結果為 PASS；G0-08 盲測結構 PASS、樣本製作排在 P2 前；G0-05 Windows 實機 2026-10-16 PASS；G0-11／G0-12 於 PR #1 審查通過（2026-10-16）；G0-06 依 ADR-0003 以 CI macos-15 arm64 證據替代，實機須於 P3 結束前取得方案、P4 起實測）
- **下一段可開始：是**（P0 PR 合併後）。延續條件：24 份人工 fixture（含 ADR-0009 新增 I09）須在 P1 驗收前登記；12 份盲測須在 P2 開工前完成並離線保管（2026-10-21 已完成 11 份，U06 無法製作；依 ADR-0012 接受 11 份）；macOS 實機方案最晚 2026-11-16，屆時仍無方案則依 ADR-0003 觸發停止條件、交負責人決定。合併條件：PR 最新 commit 的雙平台 CI 通過；GitHub 設定（§9 第一項）建議於合併前完成，最晚 P1 開工前。I04、I07 預期值已於 2026-10-16 依 ADR-0009 鎖定，不再是延續條件。

## 11. 獨立核對紀錄

第一輪（2026-10-12，計畫書版 P0）：子代理人核對發現 8 項不一致，已全部修正（CI run 取消、smoke 大小重複計算、威脅排序、T4 狀態、repo 可見度敘述、追溯表缺漏、理由碼性質測試、PySide6 三選一授權）。

第三輪（2026-10-16，合併前最終核對）：所有 G0 驗收條件皆有證據，PASS 成立；發現 5 項敘述問題並已修正：§7 仍寫 G0-05 NOT RUN、§1 日期與審查者為舊值、CI 證據非最新 commit、G0-05 證據來源（本機檔、人工確認）未寫明、延續條件缺合併條件與停止條件。

第二輪（2026-10-12，規格 v1.1 版 P0）：結論為 fixture hash、群組數、盲測、理由碼性質、bbox、manual-steps 皆一致；發現並已修正：

| # | 發現 | 處理 |
| --- | --- | --- |
| 1 | 報告寫 CI 證據時新 commit 尚無 CI run | 回填 run 38228037824 結果（§4） |
| 2 | smoke 大小來自舊 run | 改用新 run 數字 |
| 3 | spec 正文直接改寫 G0 停止條件，但 ADR-0003 仍為提議 | 正文恢復 v1.0 原句，修訂只留附錄 A4 |
| 4 | 「可重現 ≥20」測試只數 available | 改為只計 deterministic 樣本 |
| 5 | 座標原點未寫明為 CropBox 左上角（L01） | schema 與產生器說明補上 |
| 6 | 追溯表缺 G4 中文字型、§7 四個錯誤碼 | 補 G4-07、X-06～X-10 |
| 7 | CLAUDE.md、pyproject 殘留舊路徑 | 修正 |
| 8 | 「不可改動區域」非座標、缺 qpdf warning 欄 | 列入 §7 限制，P1／P2 處理 |
