# P0 關卡報告：規格、環境與資料集

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：P0　分支：`claude/compassionate-mayer-4gov5x`　commit：見 §4 CI run　日期：2026-10-12
- 撰寫：Claude Code；審查：<工程師>；獨立核對：未參與實作的 Claude 子代理人（§11）
- 輸入：規格 v1.0（已匯入為 `docs/spec.md` v1.1）、執行計畫書 v1.1；repo 已公開

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機 | NOT RUN（待人工，manual-steps §3） | — | — |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest（windows-2025）x64 | GitHub 標準 runner | Python 3.13.15；套件同下 |
| CI macos | macos-15 arm64（macOS 15.7） | GitHub 標準 runner（M1） | Python 3.13.15；套件同下 |
| Linux 開發容器 | Linux x86_64 | 雲端容器 | Python 3.13.16 |

鎖定版本（`uv.lock`；`exclude-newer = 2026-09-28`）：PyMuPDF 1.28.2、pikepdf 10.14.0、PySide6-Essentials 6.11.2；
測試工具 pytest 9.1.1、pytest-qt 4.5.0、pypdfium2 5.13.0、ReportLab 5.0.1、fontTools 4.66.0、PyInstaller 6.22.3。
字型：Noto Sans TC Regular（noto-cjk@f8d1575，sha256 `5bab0cb3…`）、Noto Serif TC VF（google/fonts@bd8f81d，sha256 `0077e18f…`）、Droid Sans Fallback（PyMuPDF 內建）。

## 3. 需求 → test ID → fixture／hash → 結果

完整對照見 `docs/traceability.md`（G0–G8 與 §8 共 80 項，均已指定 test ID）。G0 逐條：

| 需求 ID | 內容 | 證據 | 環境 | 結果 |
| --- | --- | --- | --- | --- |
| G0-01 | 相依鎖定 | `uv.lock`；CI `uv sync --locked` | 容器、CI 雙平台 | PASS |
| G0-02 | 最小測試流程 | ci.yml job `test` | CI windows、CI macos | PASS（CI 證據） |
| G0-03 | 空白 app 啟動 | `tests/gui/test_app_smoke.py`（2 項） | 容器 offscreen、CI 雙平台 offscreen | PASS |
| G0-04 | 兩平台打包最小 Qt app | `packaging/smoke_build.py` | 容器、CI 雙平台 | PASS（CI 證據） |
| G0-05 | Windows 11 x64 實機啟動 | manual-steps §3 | Windows 實機 | NOT RUN（待人工） |
| G0-06 | macOS Apple Silicon 實機啟動 | ADR-0003：P0–P3 以 CI macos-15 arm64 替代 | macOS 實機 | NOT RUN（無實機；ADR-0003 待確認） |
| G0-07 | 60 份 manifest、群組 T12／F10／L8／I8／B8／U6／S8 | `tests/unit/test_manifest.py` | 容器、CI | PASS |
| G0-08 | ≥12 盲測、不進 repo | 同上 `::test_at_least_12_blind_fixtures_kept_offline` | 容器、CI | PASS（結構）；製作 NOT RUN |
| G0-09 | ≥20 份可重現首批樣本、非單一產生器 | 21 份（PyMuPDF 14、ReportLab 5、PyMuPDF+pikepdf 1、加密 1）；`::test_generator_reproduces_committed_bytes` | 容器、CI 雙平台 | PASS |
| G0-10 | fixture hash 可驗證 | `::test_committed_fixture_hashes_match_manifest` | 容器、CI | PASS |
| G0-11 | 沒有正式 PDF | 全為合成內容；人工 fixture 規則見 manual-steps §4 | 人工審查 | MANUAL（待審） |
| G0-12 | 每個需求指定 test ID | `docs/traceability.md` | 人工審查 | MANUAL（待審） |
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

CI：見 §10（推送後回填 run 編號與雙平台結果）。

## 5. 真修改證據

不適用（P0 不實作編輯核心）。

## 6. 資料完整性與資源／出站紀錄

- fixture 位元組可重現：除 U02（AES 加密 key 隨機）外，重產與提交檔 SHA-256 完全相同。
- 出站：產品程式碼無網路模組（G0-16）；實機出站監測於 P7。

## 7. 限制、阻擋、未測項目

- Windows／macOS 實機啟動 NOT RUN（G0-05、G0-06）。
- 人工 fixture 23 份、盲測 12 份尚未製作（manifest `status=pending`）；S03–S06 於 P7 以腳本產生。
- §8.2 視覺門檻「P0／P2 以基準實測後鎖定」：P0 無編輯引擎可量測，NOT RUN，於 P2 鎖定（X-05）。
- MuPDF 1.28 `subset_fonts()` 無法子集化 CFF 字型（Noto Sans TC），fixture 改以 fontTools 預先子集化；P2 模式 B 須沿用（ADR-0008）。
- Noto Serif TC 為 variable font，ReportLab 嵌入預設 instance（ExtraLight），字形偏細但不影響測試。
- smoke build 未瘦身（Windows 168 MiB、macOS 149.5 MiB），P8 處理。

## 8. 安全審查

- `THREAT_MODEL.md`（harness `/threat-model` schema，bootstrap 模式）：10 項威脅，前五 T1 惡意 PDF 記憶體破壞、T2 IPC 攻陷主行程、T6 供應鏈、T8 竄改安裝包、T3 儲存毀損原檔。
- `/vuln-scan`：NOT RUN — P0 無解析／IPC 程式碼，依 ADR-0005 於 P1 結束前執行。
- 供應鏈控制：lock 雜湊、冷卻期、字型 SHA-256、Actions commit SHA 鎖定、`permissions: contents: read`。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | ADR-0003：G0 macOS 以 CI 證據替代、停止條件改為 P3 結束 | G0 能否宣告 PASS | 負責人 |
| U2 | ADR-0006：第二解譯器用 PDFium 非 Poppler | §8.1 證據工具 | 工程師 |
| U3 | ADR-0007：新增 4 個理由碼；JS／附件預設拒絕；可修復損毀檔預設拒絕 | P1 能力判定基準 | 工程師 |
| U4 | ADR-0008：Noto Sans TC／Noto Serif TC | P2 模式 B 字型 | 工程師 |
| U5 | 人工 fixture 預期值（I04、I07 等）於 P2 前鎖定（spec §5） | P1／P2 驗收 | 工程師 |

人工待辦（詳細步驟見 `reports/P0/manual-steps.md`）：

- [ ] GitHub：預設分支改 `main`、分支保護、secret scanning、Dependabot alerts、Actions 權限
- [ ] 確認 ADR-0003、0006、0007、0008 與 fixture 預期值
- [ ] Windows 11 實機驗證（G0-05）
- [ ] 製作 23 份人工 fixture 並登記
- [ ] 盲測 12 份（由不參與實作者製作、離線保管）
- [ ] Claude 用量一週紀錄
- [ ] macOS 實機方案（11/16 前）

## 10. 關卡結果

- CI：見下方（推送後回填）
- **關卡結果：BLOCKED**（Claude Code 負責項目已完成；G0-05 Windows 實機、G0-06 macOS（ADR-0003 待確認）、G0-11／G0-12 人工審查未完成）
- **下一段可開始：否**。條件：G0-05 PASS、ADR-0003 接受、人工審查 G0-11／G0-12。人工 fixture 可與 P1 並行，但須在 P1 驗收前完成。

## 11. 獨立核對紀錄

第一輪（2026-10-12，計畫書版 P0）：子代理人核對發現 8 項不一致，已全部修正（CI run 取消、smoke 大小重複計算、威脅排序、T4 狀態、repo 可見度敘述、追溯表缺漏、理由碼性質測試、PySide6 三選一授權）。

第二輪（規格 v1.1 版 P0）：見下方（核對後回填）。
