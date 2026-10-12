# P0 人工項目操作手冊

本手冊列出 P0 需要人工完成的事項。建議依下表順序處理；每項完成後勾選，並把結果填回 `reports/P0/report.md`。

| 順序 | 項目 | 誰 | 期限 | 估時 |
| --- | --- | --- | --- | --- |
| 1 | GitHub repo 設定（預設分支、分支保護、安全功能） | repo 管理者 | 本週 | 30 分 |
| 2 | ~~確認 ADR~~（2026-10-12 已全部接受）；fixture 預期值 | 工程師／負責人 | P2 前 | 30 分 |
| 3 | Windows 11 實機驗證 | 工程師 | P0 第 1 週 | 1 小時 |
| 4 | 製作人工 fixture（23 份入 repo） | 工程師 | P1 開工前 | 4–6 小時 |
| 5 | 製作盲測 fixture（12 份離線保管） | **不參與實作的人** | P2 開工前 | 3–4 小時 |
| 6 | 審查並合併 P0 | 工程師 | 1–5 完成後 | 1 小時 |
| 7 | Claude 用量與方案 | 負責人 | P0 第 1 週 | 15 分 |
| 8 | macOS 實機取得方案 | 負責人 | 2026-11-16 前 | — |

---

## 1. GitHub repo 設定

repo：<https://github.com/TGHAPPLICATION/PEditor>（需 Admin 權限）

### 1.1 預設分支改為 `main`

`main` 已由 Claude 建立。

1. 進入 repo → **Settings** → 左側 **General**。
2. 在 **Default branch** 區塊按 ⇄（Switch to another branch），選 `main` → **Update** → 確認。

### 1.2 保護 `main`

1. **Settings** → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**。
2. Ruleset name：`main-protection`；Enforcement status：**Active**。
3. Target branches → **Add target** → **Include default branch**。
4. 勾選：
   - **Restrict deletions**
   - **Block force pushes**
   - **Require a pull request before merging**（Required approvals 設 1；單人開發可設 0，但仍要走 PR）
   - **Require status checks to pass** → **Add checks**，加入 `test (windows-latest)` 與 `test (macos-15)`
     （需先有一次 CI 執行紀錄才搜尋得到）。
5. **Create**。

### 1.3 開啟安全功能

**Settings** → **Advanced Security**（或 **Code security**）：

1. **Dependabot alerts** → **Enable**（相依有已知漏洞時通知；不啟用自動升級 PR，升級仍走 ADR）。
2. **Secret scanning** → **Enable**；**Push protection** → **Enable**。

### 1.4 Actions 權限（公開 repo 必做）

**Settings** → **Actions** → **General**：

1. **Fork pull request workflows from outside collaborators**：選 **Require approval for all external contributors**。
2. **Workflow permissions**：選 **Read repository contents and packages permissions**，取消勾選 **Allow GitHub Actions to create and approve pull requests**。

完成後在 `reports/P0/report.md` §9 勾選「GitHub 設定」。

---

## 2. 確認 ADR 與 fixture 預期值

閱讀下列檔案，同意就把檔頭的「狀態：提議」改成「狀態：已接受（YYYY-MM-DD，姓名）」。不同意請寫下原因，交給 Claude 修訂。

| ADR | 要決定的事 | 建議 |
| --- | --- | --- |
| `docs/adr/0003-macos-verification.md` | G0 的 macOS 啟動先用 CI 證據；停止條件改為「P3 結束仍無 Mac 實機方案」 | 接受 |
| `docs/adr/0006-test-engines.md` | 第二解譯器用 PDFium（pypdfium2），不用 Poppler | 接受（Windows 不必另裝 Poppler） |
| `docs/adr/0007-reason-codes.md` | 新增 4 個理由碼；含 JavaScript／附件的 PDF 預設拒絕編輯 | 接受 |
| `docs/adr/0008-fonts.md` | 字型採 Noto Sans TC／Noto Serif TC（OFL） | 接受 |

另請確認 `tests/fixtures/manifest.csv` 中標「預期值待人工確認」的列：

| fixture | 目前預期 | 問題 |
| --- | --- | --- |
| S01 | reject MALFORMED_DOCUMENT | MuPDF 能自動修復開啟。要拒絕，還是修復後允許編輯？ |
| S02、S05 | reject ACTIVE_CONTENT | 含 JavaScript／附件。要拒絕，還是允許編輯但保證不執行？ |
| I04 | support | 含透明遮罩的 PNG，P5 要不要支援？ |
| I07 | reject UNSUPPORTED_LAYOUT | 經剪裁的圖片，P5 要不要支援？ |
| U01、U03 | readonly NO_TEXT_LAYER | 掃描檔、外框文字只能預覽 |

修改方式：直接在 GitHub 網頁編輯 `manifest.csv` 的 `expected`／`reason_code` 欄位，或在對話中告訴 Claude。
合成樣本（S01、S02、U01）的預期值寫在 `scripts/gen_fixtures.py` 的 `SYNTHETIC` 清單，請 Claude 一併修改。

---

## 3. Windows 11 實機驗證（G0-05）

目的：證明在 Windows 11 x64 實機上能安裝相依、通過測試、啟動空白 app、完成 smoke build。

### 3.1 準備（第一次才需要）

以**一般使用者**開啟 PowerShell：

```powershell
# 1. 安裝 Git 與 uv（如機關禁用 winget，改由軟體中心或官網離線安裝檔安裝）
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
# 重新開啟 PowerShell 後確認
git --version
uv --version
```

### 3.2 取得程式並測試

```powershell
cd $HOME
git clone https://github.com/TGHAPPLICATION/PEditor.git
cd PEditor
git checkout main          # 合併前請改用 claude/compassionate-mayer-4gov5x

uv sync --locked --all-groups            # 約 1–3 分鐘，下載約 200 MB
uv run python scripts/fetch_fonts.py     # 下載 2 個字型並驗證 SHA-256
uv run ruff check .
uv run pytest                            # 預期：全部 passed
```

### 3.3 啟動 app（實機視窗，不用 offscreen）

```powershell
uv run peditor
```

預期：出現標題「PEditor 0.0.1」的空白視窗，中央顯示「PEditor（P0 空白視窗）」。拍一張螢幕截圖，關閉視窗。

### 3.4 smoke build（打包後啟動）

```powershell
uv run python packaging/smoke_build.py
```

預期最後兩行出現 `PEDITOR_SMOKE_OK {...}` 和 `smoke build OK, onedir size = ... MiB`。
再雙擊 `build\smoke\dist\peditor\peditor.exe`，確認視窗能開啟（Windows Defender 可能詢問，選「仍要執行」）。

### 3.5 記錄環境

```powershell
winver                                   # 記下版本，例如 24H2（組建 26100.xxxx）
Get-ComputerInfo -Property CsProcessors, CsTotalPhysicalMemory, OsArchitecture
uv run peditor --version                 # 記下 Python／套件版本
```

### 3.6 回填結果

把下列資訊填入 `reports/P0/report.md` 的 §2 環境表與 §3 的 G0-05 列（或貼給 Claude 代填）：

- Windows 版本與組建、CPU、記憶體
- `pytest` 最後一行（例如 `21 passed in 6.1s`）與 exit code
- smoke build 的 onedir 大小
- 螢幕截圖檔名（截圖存到機關內部空間即可，不必上傳 repo）

任何一步失敗：複製完整錯誤訊息交給 Claude，不要自行跳過測試。

---

## 4. 製作人工 fixture（23 份，入 repo）

目的：補齊「不同產生器」（Word、LibreOffice、Windows 列印、瀏覽器列印）與特殊文件。內容一律為**合成文字**，
不得使用真實公文、人名、身分證號、電話。

### 4.1 安裝字型（Word／LibreOffice 共用）

1. 完成 §3.2 的 `fetch_fonts.py` 後，到 `PEditor\tests\fixtures\fonts\`。
2. 對 `NotoSansTC-Regular.otf` 與 `NotoSerifTC-VF.ttf` 按右鍵 → **安裝**。
3. 重新開啟 Word／LibreOffice，字型清單可找到「Noto Sans TC」「Noto Serif TC」。

**不要**使用標楷體、新細明體、微軟正黑體等系統字型：它們的授權不允許隨 repo 公開散布嵌入字型的 PDF（ADR-0008）。

### 4.2 共通版面

- 紙張 A4、直向、邊界 2.54 cm；字級 12 pt（標題 14 pt）；每份只做 1 頁。
- 每份文件第一行寫 fixture 編號（例如「T05」），方便辨識；目標文字放在第 2 行以後。
- 「目標原文」必須在頁面上**只出現一次**（除非該列說明要重複）。

### 4.3 匯出設定

**Word（Microsoft 365／2021）**：檔案 → 另存新檔 → 檔案類型選 **PDF** → **選項**：
- 頁面範圍：全部；**不要**勾「ISO 19005-1 相容（PDF/A）」（U05 除外）
- **不要**勾「無法內嵌字型時點陣化文字」
- 勾選「文件結構標籤以協助工具使用」（保持預設）
- 最佳化：**標準**

**LibreOffice Writer（24.x 以上）**：檔案 → **匯出為 PDF…** → 一般：
- **不要**勾「PDF/A」（U05 除外）、不要勾「混合 PDF（嵌入 ODF）」
- 圖片：無失真壓縮；**不要**勾「降低影像解析度」
- 其餘保持預設 → 匯出

檔名一律用 fixture 編號，例如 `T05.pdf`。

### 4.4 各 fixture 內容

`目標原文`與`新文`已預填在 `manifest.csv`，請照抄，不要改字。

| fixture | 工具 | 字型 | 製作內容 |
| --- | --- | --- | --- |
| T05 | Word | Noto Sans TC | 一段 3 行文字，其中一句「本府辦理年度資訊安全稽核，請各單位配合。」 |
| T06 | Word | Noto Serif TC | 一行「發文單位：臺北市政府資訊局」 |
| T07 | LibreOffice | Noto Sans TC | 一行「地點：本府」，同一行右側留白到右邊界 |
| T08 | LibreOffice | Noto Serif TC | 一行「Email：test@example.gov.tw，電話（02）2720-8889」 |
| T09 | Word → **列印** | Noto Sans TC | 「公告日期：中華民國115年10月12日」；用 檔案 → 列印 → 印表機選 **Microsoft Print to PDF** 輸出 |
| F06 | Word | Noto Sans TC | 標題「醫療院所名冊（合成）」，下方 3 行任意合成內容，**全文不要出現「藥」「事」兩字** |
| F07 | LibreOffice | Noto Serif TC | 一行「衛生資料彙整（合成）」 |
| F08 | LibreOffice | Noto Sans TC | 一行「承辦人：吉野」 |
| L04 | Word | Noto Sans TC | 一行「重要：請攜帶身分證件」，段落 → 框線及網底 → 網底 **黃色** |
| L05 | LibreOffice | Noto Serif TC | 插入一張半透明圖片（圖片 → 屬性 → 透明度 50%）後置於文字下方，文字「背景圖測試文字」疊在圖上 |
| L06 | LibreOffice **Draw** | Noto Sans TC | 文字方塊「旋轉四十五度」，位置及大小 → 旋轉 45° → 匯出 PDF |
| L07 | Word | Noto Sans TC | 插入文字方塊，文字方向設 **垂直**，內容「直排文字測試」 |
| I04 | Word | — | 插入一張含透明背景的 PNG（可用小畫家 3D 或任一工具做 200×100 圓形、背景透明） |
| I05 | LibreOffice | — | 插入一張 JPEG 照片（自行拍攝的物品照，**不得有人臉、車牌、文件**） |
| I06 | Word | Noto Sans TC | 一段文字，插入圖片並設「文字在後」，讓圖片蓋住部分文字 |
| I07 | LibreOffice | — | 插入圖片後用 **裁剪** 工具裁掉四周各 20% |
| B03 | Word | Noto Sans TC | 3×3 表格：第 1 列「項目／數量／備註」，第 2 列「文具／12／合成」，第 3 列「紙張／300／資料」 |
| B04 | LibreOffice | Noto Serif TC | 同 B03 內容的 3×3 表格 |
| B05 | Word | Noto Sans TC | 2×3 表格，第 2 列第 3 格內兩行：「第一行」換行「第二行」 |
| B06 | LibreOffice | Noto Sans TC | 3×3 表格，第 2 列第 1、2 格**合併**，內容「合併格」 |
| U03 | LibreOffice **Draw** | Noto Sans TC | 文字「外框文字」→ 右鍵 → **轉換** → **成為多邊形** → 匯出 PDF（確認 PDF 中無法選取文字） |
| U04 | LibreOffice | Noto Sans TC | 內容「簽章測試」，匯出 PDF 時 **數位簽章** 分頁用自簽憑證簽署（見 4.6） |
| U05 | LibreOffice | Noto Sans TC | 內容「PDF/A 測試」，匯出時勾 **PDF/A**，版本 **PDF/A-2b** |

S03–S06（壓縮炸彈、深層巢狀、附件、Launch）會在 P7 由腳本產生，不用人工製作。

### 4.5 登記到 repo

每做完一份，在 PEditor 資料夾執行：

```powershell
uv run python scripts/register_fixture.py T05 "C:\path\to\T05.pdf"
```

腳本會複製檔案到 `tests/fixtures/files/T05.pdf`，並在 manifest 填入 SHA-256、產生器版本、目標位置。
若顯示「找不到原文」，代表 PDF 中的文字和 manifest 的「目標原文」不一致，請檢查後重新匯出。

全部登記後：

```powershell
uv run pytest
git checkout -b p0-human-fixtures
git add tests/fixtures/files tests/fixtures/manifest.csv
git commit -m "P0：新增人工 fixture"
git push -u origin p0-human-fixtures
```

再到 GitHub 開 PR 合併到 `main`（或把 PDF 交給 Claude 代為登記）。

### 4.6 U04 自簽憑證（只用於測試）

PowerShell：

```powershell
New-SelfSignedCertificate -Subject "CN=PEditor Test Signer" -Type CodeSigningCert `
  -CertStoreLocation Cert:\CurrentUser\My -NotAfter (Get-Date).AddYears(1)
```

LibreOffice 在 Windows 會讀取「目前使用者」憑證存放區。匯出 PDF → **數位簽章** 分頁 → 選取 → 選「PEditor Test Signer」→ 匯出。
做完後可在 `certmgr.msc` → 個人 → 憑證 中刪除此測試憑證。

---

## 5. 製作盲測 fixture（12 份，不入 repo）

盲測用來確認程式不是只針對已知樣本調整（spec §5、G8）。**必須由不參與實作與審查程式的人製作與保管**，
內容不得告訴工程師或 Claude，也**不得**放進 repo、雲端硬碟或任何 AI 工具。

| fixture | 類型 | 工具建議 | 預期 |
| --- | --- | --- | --- |
| T10 | 一般繁中段落、同字數替換 | Word + Noto Serif TC | support |
| T11 | 中英數混排、較短替換 | LibreOffice + Noto Sans TC | support |
| T12 | 一般繁中段落 | 瀏覽器（Edge／Chrome）開 HTML 後「列印 → 另存為 PDF」 | support |
| F09 | 新字不在原子集 | Word + Noto Serif TC | support（模式 B） |
| F10 | 新字為 𠮷 等擴充區字 | LibreOffice + Noto Sans TC | reject GLYPH_MISSING |
| L08 | 彩色或圖片背景上的文字 | LibreOffice | support |
| I08 | 單張圖片替換 | Word | support |
| B07 | 規則表格改單格 | Word | support |
| B08 | 含合併儲存格的表格 | LibreOffice | reject UNSUPPORTED_LAYOUT |
| U06 | XFA 表單 | 如無法取得 XFA 工具，改用 Adobe 範例格式自行製作；做不到請標記「無法製作」 | reject UNSUPPORTED_FEATURE |
| S07 | 損毀檔（任選一份 PDF，用記事本刪掉中間數行後存檔） | 記事本 | reject MALFORMED_DOCUMENT |
| S08 | 大量頁面（如 600 頁）的文件 | Word 複製貼上後匯出 | reject RESOURCE_LIMIT |

步驟：

1. 依上表製作，內容自訂但須為合成資料；每份另寫一張「答案卡」（目標頁、目標原文、新文、預期結果）。
2. 計算 hash（不會複製檔案）：
   `uv run python scripts/register_fixture.py T10 "E:\blind\T10.pdf" --hash-only`
3. 把 12 份 PDF、答案卡與 hash 清冊存到**機關內部加密隨身碟或內部 NAS 的限制存取資料夾**。
4. 只把 hash 清冊（不含內容）提供給工程師，用來在 P8 確認檔案未被更動。
5. P8 盲測時由保管人在離線實機上執行並記錄結果。

---

## 6. 審查並合併 P0

1. 確認 1–4 已完成（盲測可在 P2 前完成）。
2. 到 GitHub 開 PR：base 選 `main`，compare 選 `claude/compassionate-mayer-4gov5x`（也可請 Claude 開）。
3. 審查重點：`docs/spec.md` 附錄 A、ADR、`tests/fixtures/manifest.csv`、`reports/P0/report.md`。
4. CI 兩個 job 都綠燈後 **Merge**。之後每段一個分支、一個 PR（CLAUDE.md S3）。

---

## 7. Claude 用量與方案

1. P0 期間記錄每天使用 Claude Code 的時數與是否碰到用量上限。
2. 一週後評估：若常碰到上限，調整方案或延長日曆（計畫書風險表）。
3. 結果記在 `reports/P0/report.md` §9。

---

## 8. macOS 實機取得方案（2026-11-16 前）

1. 先詢問機關或同事是否可借用 Apple Silicon Mac（M1 以上、16 GB 記憶體），需 11/17 起約 5 週可用時段。
2. 借不到就採購 Mac mini M4 16 GB／256 GB（約 NT$19,900）。
3. 取得後執行 §3 的同一套步驟（指令把 `.exe` 改為 `build/smoke/dist/peditor/peditor`），回填 G0-06。
4. 11/16 仍無方案 → 依 ADR-0003 觸發停止條件，由負責人決定。
