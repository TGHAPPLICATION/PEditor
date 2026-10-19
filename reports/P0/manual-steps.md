# P0 人工項目操作手冊

P0 需要人工完成的事項與完整指令。建議依下表順序處理；每項完成後把結果貼給 Claude，或填回 `reports/P0/report.md`。

| 順序 | 項目 | 誰 | 期限 | 估時 | 可交給本機 Claude Code？ |
| --- | --- | --- | --- | --- | --- |
| 1 | GitHub repo 設定 | repo 管理者 | 本週 | 15 分 | 可（需你已 `gh auth login`） |
| 2 | 鎖定 I04、I07 的預期值 — **已於 2026-10-16 決定（ADR-0009）** | 工程師 | P2 前 | 10 分 | 已完成 |
| 3 | Windows 11 實機驗證（G0-05） | 工程師 | P0 第 1 週 | 20 分 | 可（視窗是否出現須你回答） |
| 4 | 製作 24 份人工 fixture | 工程師 | P1 驗收前 | 4–6 小時 | 部分（Word／LibreOffice 操作須人工；登記可交給它） |
| 5 | 製作 12 份盲測 fixture | **不參與實作的人** | P2 開工前 | 3–4 小時 | **不可**（盲測不得讓 AI 看到） |
| 6 | 審查並合併 P0 PR | 工程師 | 1、3 完成後 | 1 小時 | 審查須你做；合併指令可交給它 |
| 7 | Claude 用量紀錄 | 負責人 | P0 第 1 週 | 15 分 | 只能你做 |
| 8 | macOS 實機（2026-11-16 前） | 負責人 | — | — | 取得後同第 3 項 |

指令中的 PowerShell 都在 **PEditor 資料夾**、以**一般使用者**（非系統管理員）執行。

---

## 0. 讓本機 Claude Code 代為執行（選用）

目前對話的 Claude 跑在雲端容器，無法操作你的電腦。你的電腦已裝 Claude Code，可以在本機開一個 session 代跑第 1、3、4.5、6 項：

```powershell
cd $HOME
git clone https://github.com/TGHAPPLICATION/PEditor.git
cd PEditor
git checkout claude/compassionate-mayer-4gov5x   # P0 合併前；合併後改用 main
claude
```

進入 Claude Code 後輸入：

```text
讀 CLAUDE.md 與 reports/P0/manual-steps.md，依第 3 節執行 Windows 實機驗證，
每個指令執行前先讓我確認，最後把 build/p0-check/summary.md 的內容給我。
```

想在手機或 Claude App 上看著它跑，改在同一資料夾執行 `claude remote-control`。

注意：第 5 項盲測**不要**交給任何 AI 工具，盲測內容一旦被看到就失去意義。

---

## 1. GitHub repo 設定

需要 repo 的 Admin 權限。以下提供 CLI 與網頁兩種做法，擇一即可。

### 1.1 安裝並登入 GitHub CLI（第一次）

```powershell
winget install --id GitHub.cli -e
# 重新開啟 PowerShell
gh auth login          # 選 GitHub.com → HTTPS → Login with a web browser
gh auth status         # 確認已登入
```

### 1.2 CLI 做法（一次完成）

```powershell
$R = "TGHAPPLICATION/PEditor"

# (1) 預設分支改為 main
gh repo edit $R --default-branch main

# (2) 保護 main：規則定義在 repo 的 .github/rulesets/main-protection.json
#     （禁止刪除與 force push、必須走 PR、兩個 CI 檢查須通過、討論串須解決）
gh api -X POST "repos/$R/rulesets" --input .github/rulesets/main-protection.json

# (3) Dependabot alerts（只通知，不自動開升級 PR；升級仍走 ADR）
gh api -X PUT "repos/$R/vulnerability-alerts"

# (4) Secret scanning 與 push protection
'{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}' |
  gh api -X PATCH "repos/$R" --input -

# (5) Actions：預設 token 唯讀、不允許 Actions 核准 PR
gh api -X PUT "repos/$R/actions/permissions/workflow" `
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false

# (6) 外部貢獻者的 PR 須核准後才跑 CI
gh api -X PUT "repos/$R/actions/permissions/fork-pr-contributor-approval" `
  -f approval_policy=all_external_contributors
```

驗證：

```powershell
gh api "repos/$R" --jq ".default_branch"                          # 應為 main
gh api "repos/$R/rulesets" --jq ".[].name"                        # 應有 main-protection
gh api "repos/$R" --jq ".security_and_analysis"                   # secret_scanning 為 enabled
gh api "repos/$R/actions/permissions/workflow"                    # default_workflow_permissions = read
```

若某一行回 `404` 或 `422`，代表該設定的 API 名稱已改版或帳號權限不足，改用 1.3 的網頁做法完成該項即可。

### 1.3 網頁做法

repo：<https://github.com/TGHAPPLICATION/PEditor>

1. **預設分支**：Settings → General → Default branch → ⇄ → 選 `main` → Update。
2. **保護 main**：Settings → Rules → Rulesets → New ruleset → **Import a ruleset** → 選 repo 內的
   `.github/rulesets/main-protection.json` → Create。
   （沒有 Import 按鈕時：New branch ruleset，名稱 `main-protection`、Active、Target 選 Include default branch，
   勾 Restrict deletions、Block force pushes、Require a pull request before merging、
   Require status checks to pass 並加入 `test (windows-latest)` 與 `test (macos-15)`。）
3. **安全功能**：Settings → Advanced Security（或 Code security）→ Dependabot alerts **Enable**；
   Secret scanning **Enable**，Push protection **Enable**。
4. **Actions**：Settings → Actions → General →
   Fork pull request workflows from outside collaborators 選 **Require approval for all external contributors**；
   Workflow permissions 選 **Read repository contents and packages permissions**，
   取消勾選 Allow GitHub Actions to create and approve pull requests → Save。

---

## 2. 鎖定 fixture 預期值

ADR-0001～0008 已於 2026-10-12 全部接受，S01、S02、S05 依 ADR-0007 定為拒絕。

I04、I07 已於 2026-10-16 決定（ADR-0009）：兩者皆改為 `support`（I04 含 SMask 透明遮罩；I07 為矩陣層級裁剪）；
另新增 I09（`reject UNSUPPORTED_LAYOUT`，非矩形裁剪路徑）補位，保留「拒絕非支援遮罩／剪裁」的可測試樣本。
詳見 `docs/adr/0009-image-mask-crop-scope.md`。

---

## 3. Windows 11 實機驗證（G0-05）

目的：證明在 Windows 11 x64 實機上能安裝相依、通過測試、打包，並實際開出視窗。
`scripts\p0_windows_check.ps1` 會一次跑完全部步驟並產生結果摘要；CI 的 Windows job 也跑同一支腳本（只是不開視窗）。

### 3.1 安裝工具（第一次才需要）

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
# 機關禁用 winget 時，uv 改用官方安裝指令：
#   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# 重新開啟 PowerShell 後確認：
git --version
uv --version
```

### 3.2 取得程式

```powershell
cd $HOME
git clone https://github.com/TGHAPPLICATION/PEditor.git
cd PEditor
git checkout claude/compassionate-mayer-4gov5x   # P0 合併前；合併後改 git checkout main
git pull
```

### 3.3 執行驗證腳本

```powershell
powershell -ExecutionPolicy Bypass -File scripts\p0_windows_check.ps1
```

腳本依序執行：環境資訊 → `uv sync --locked` → 下載字型並驗 SHA-256 → ruff → pytest → smoke build。
第一次約 3–5 分鐘（下載約 200 MB）。最後會開兩次視窗並問你：

1. `Did a window titled 'PEditor 0.0.1' appear? (y/n)`：看到標題為「PEditor 0.0.1」、中央寫「PEditor（P0 空白視窗）」的視窗就輸入 `y`，然後按 Enter。
2. `Did the packaged peditor.exe window appear? (y/n)`：同上，這次是打包後的 exe。若 Windows Defender 跳出「Windows 已保護您的電腦」，按「其他資訊」→「仍要執行」。

視窗會由腳本自動關閉。請拍一張第 1 個視窗的截圖存在機關內部空間（不需上傳 repo）。

### 3.4 回傳結果

```powershell
Get-Content build\p0-check\summary.md
```

把輸出整段貼給 Claude，由 Claude 回填 `reports/P0/report.md` 的 G0-05 與環境表。摘要只含 OS 版本、CPU、記憶體、版本號與各步驟結果，不含電腦名稱、帳號或路徑。

`result: **FAIL**` 時，再執行下列指令，把錯誤段落貼給 Claude；不要自行跳過測試：

```powershell
Get-Content build\p0-check\log.txt -Tail 80
```

---

## 4. 製作人工 fixture（24 份，入 repo）

內容一律為**合成文字**，不得使用真實公文、人名、身分證號、電話。

### 4.1 安裝字型（Word／LibreOffice 共用）

1. 完成第 3 節（腳本會下載字型）後，到 `PEditor\tests\fixtures\fonts\`；或先執行 `uv run python scripts/fetch_fonts.py`。
2. 對 `NotoSansTC-Regular.otf` 與 `NotoSerifTC-VF.ttf` 按右鍵 → **安裝**。
3. 重新開啟 Word／LibreOffice，字型清單可找到「Noto Sans TC」「Noto Serif TC」。

**不要**使用標楷體、新細明體、微軟正黑體等系統字型：它們的授權不允許隨 repo 公開散布嵌入字型的 PDF（ADR-0008）。

Windows 11 已內建同名的 Noto Sans TC／Noto Serif TC 可變字型，Word 會優先選用內建版；依 ADR-0010 接受，
登記時在 manifest notes 註明。

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

**個資**：Word 會把 Office 使用者名稱寫進 PDF 的 Author。匯出前到 檔案 → 資訊 → 內容，清空「作者」「上次修改者」；
LibreOffice 則到 檔案 → 屬性 → 一般，取消勾選「套用使用者資料」。匯出後確認 PDF 內容中沒有姓名。

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
| I04 | Word | — | 插入一張含透明背景的 PNG（可用小畫家 3D 或任一工具做 200×100 圓形、背景透明）；已確認支援（ADR-0009） |
| I05 | LibreOffice | — | 插入一張 JPEG 照片（自行拍攝的物品照，**不得有人臉、車牌、文件**） |
| I06 | Word | Noto Sans TC | 一段文字，插入圖片並設「文字在後」，讓圖片蓋住部分文字 |
| I07 | LibreOffice | — | 插入圖片後用 **裁剪** 工具裁掉四周各 20%；已確認支援（ADR-0009） |
| I09 | LibreOffice **Draw** | — | 插入圖片後裁剪為**非矩形圖形**（例如置入圓形或任意多邊形容器、或用「剪裁為形狀」功能）；預期拒絕 UNSUPPORTED_LAYOUT（ADR-0009 補位樣本） |
| B03 | Word | Noto Sans TC | 3×3 表格：第 1 列「項目／數量／備註」，第 2 列「文具／12／合成」，第 3 列「紙張／300／資料」 |
| B04 | LibreOffice | Noto Serif TC | 同 B03 內容的 3×3 表格 |
| B05 | Word | Noto Sans TC | 2×3 表格，第 2 列第 3 格內兩行：「第一行」換行「第二行」 |
| B06 | LibreOffice | Noto Sans TC | 3×3 表格，第 2 列第 1、2 格**合併**，內容「合併格」 |
| U03 | LibreOffice **Draw** | Noto Sans TC | 文字「外框文字」→ 右鍵 → **轉換** → **成為多邊形** → 匯出 PDF（確認 PDF 中無法選取文字） |
| U04 | LibreOffice | Noto Sans TC | 內容「簽章測試」，匯出 PDF 時 **數位簽章** 分頁用自簽憑證簽署（見 4.6） |
| U05 | LibreOffice | Noto Sans TC | 內容「PDF/A 測試」，匯出時勾 **PDF/A**，版本 **PDF/A-2b** |

S03–S06（壓縮炸彈、深層巢狀、附件、Launch）會在 P7 由腳本產生，不用人工製作。

### 4.5 登記到 repo

把做好的 PDF 依編號命名（`T05.pdf`、`F06.pdf`…），集中放在一個資料夾，例如 `C:\fixtures`。

**逐份登記**：

```powershell
uv run python scripts/register_fixture.py T05 "C:\fixtures\T05.pdf"
```

**一次登記整個資料夾**：

```powershell
Get-ChildItem C:\fixtures\*.pdf | ForEach-Object {
  uv run python scripts/register_fixture.py $_.BaseName $_.FullName
}
```

每份會顯示 `已登記：sha256=… bbox=…`。顯示「找不到原文」代表 PDF 中的文字和 manifest 的目標原文不一致，請檢查後重新匯出、再登記一次（會覆蓋）。

**檢查並推送**：

```powershell
uv run pytest
git checkout -b p0-human-fixtures
git add tests/fixtures/files tests/fixtures/manifest.csv
git commit -m "P0：新增人工 fixture"
git push -u origin p0-human-fixtures
gh pr create --base main --title "P0：新增人工 fixture" --body "依 reports/P0/manual-steps.md 第 4 節製作"
```

也可以把 PDF 交給本機 Claude Code，請它執行上面的登記與推送。

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
內容不得告訴工程師，也**不得**放進 repo、雲端硬碟或任何 AI 工具（包含 Claude Code）。

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


### 5.1 製作與保管

1. 依上表製作，內容自訂但須為合成資料。檔名用編號（`T10.pdf`…），存到加密隨身碟，例如 `E:\blind`。
2. 每份另寫一張「答案卡」（`T10.txt`）：目標頁、目標原文、新文、預期結果。
3. 建立 hash 清冊：

```powershell
Get-FileHash -Algorithm SHA256 E:\blind\*.pdf |
  Select-Object @{n="fixture_id";e={[IO.Path]::GetFileNameWithoutExtension($_.Path)}}, Hash |
  Export-Csv E:\blind\hash-ledger.csv -NoTypeInformation -Encoding UTF8
Get-Content E:\blind\hash-ledger.csv
```

4. 只把 `hash-ledger.csv`（只有編號與 hash，沒有內容）交給工程師，供 P8 確認檔案未被更動。
5. 隨身碟由保管人收存；P8 盲測時由保管人在離線實機上執行。

---

## 6. 審查並合併 P0

PR：<https://github.com/TGHAPPLICATION/PEditor/pull/1>

```powershell
gh pr view 1 --repo TGHAPPLICATION/PEditor --web       # 在瀏覽器開啟審查
gh pr checks 1 --repo TGHAPPLICATION/PEditor           # 確認兩個 CI 檢查皆 pass
```

審查重點：
- `docs/spec.md` 附錄 A
- `tests/fixtures/manifest.csv`：合成 fixture 只含合成資料（G0-11）
- `docs/traceability.md`：每個需求都有 test ID（G0-12）

在 PR 留言「G0-11、G0-12 審查通過」，並完成第 3 項後合併：

```powershell
gh pr review 1 --repo TGHAPPLICATION/PEditor --comment --body "G0-11、G0-12 審查通過；G0-05 Windows 實機 PASS"
gh pr merge 1 --repo TGHAPPLICATION/PEditor --merge --delete-branch=false
```

（用 `--merge` 保留完整紀錄，不用 squash，避免改寫歷史。）

---

## 7. Claude 用量紀錄

1. P0 期間每天在 Claude Code 輸入 `/usage`（舊版沒有此指令時，到 claude.ai → 設定 → 用量查看），記下用量與是否碰到上限。
2. 一週後若常碰到上限，調整方案或延長日曆（計畫書風險表）。
3. 結果告訴 Claude，回填 `reports/P0/report.md` §9。

---

## 8. macOS 實機（2026-11-16 前）

1. 先詢問借用 Apple Silicon Mac（M1 以上、16 GB），11/17 起約需 5 週；借不到則採購 Mac mini M4 16 GB／256 GB（約 NT$19,900）。
2. 取得後在「終端機」執行：

```bash
xcode-select --install                               # 安裝 git（已安裝會提示）
curl -LsSf https://astral.sh/uv/install.sh | sh      # 安裝 uv，完成後重開終端機
git clone https://github.com/TGHAPPLICATION/PEditor.git
cd PEditor && git checkout main
bash scripts/p0_macos_check.sh
cat build/p0-check/summary.md
```

3. 首次開啟打包後的 app 若被 Gatekeeper 擋下：系統設定 → 隱私權與安全性 → 「仍要打開」。
4. 把 `summary.md` 內容貼給 Claude，回填 G0-06。
5. 11/16 仍無方案 → 依 ADR-0003 觸發停止條件，由負責人決定。
