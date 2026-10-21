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

Windows 11 已內建同名的 Noto Sans TC／Noto Serif TC 可變字型，Word 與 LibreOffice 都會優先選用內建版；依 ADR-0010 接受，
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
- 圖片：無失真壓縮；**不要**勾「降低影像解析度」（I05 等 JPEG 來源例外：保持預設 JPEG 壓縮即原樣嵌入，勾無失真反而會重壓為 Flate）
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
| T09 | Word → **列印** | Noto Sans TC | 「公告日期：中華民國115年10月12日」；用 檔案 → 列印 → 印表機選 **Microsoft Print to PDF** 輸出；ToUnicode 會缺數字，預期拒絕（ADR-0011） |
| F06 | Word | Noto Sans TC | 標題「醫療院所名冊（合成）」，下方 3 行任意合成內容，**全文不要出現「藥」「事」兩字** |
| F07 | LibreOffice | Noto Serif TC | 一行「衛生資料彙整（合成）」 |
| F08 | LibreOffice | Noto Sans TC | 一行「承辦人：吉野」 |
| L04 | Word | Noto Sans TC | 一行「重要：請攜帶身分證件」，段落 → 框線及網底 → 網底 **黃色** |
| L05 | LibreOffice | Noto Serif TC | 插入一張半透明圖片（圖片 → 屬性 → 透明度 50%）後置於文字下方，文字「背景圖測試文字」疊在圖上 |
| L06 | LibreOffice **Draw** | Noto Sans TC | 文字方塊「旋轉四十五度」，位置及大小 → 旋轉 45° → 匯出 PDF |
| L07 | Word | Noto Sans TC | 插入文字方塊，文字方向設 **垂直**，內容「直排文字測試」 |
| I04 | Word | — | 插入一張含透明背景的 PNG（可用小畫家 3D 或任一工具做 200×100 圓形、背景透明）；已確認支援（ADR-0009） |
| I05 | LibreOffice | — | 插入一張 JPEG 照片（自行拍攝的物品照，**不得有人臉、車牌、文件**）；2026-10-20 經工程師同意改用程式產生的合成 JPEG |
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

| fixture | 類型 | 工具 | 預期 |
| --- | --- | --- | --- |
| T10 | 一般繁中段落、同字數替換 | Word + Noto Serif TC | support |
| T11 | 中英數混排、較短替換 | LibreOffice + Noto Sans TC | support |
| T12 | 一般繁中段落 | 記事本寫 HTML → Edge「列印 → 另存為 PDF」 | support |
| F09 | 新字不在原文件中 | Word + Noto Serif TC | support（模式 B） |
| F10 | 新字為 𠮷（字型沒有的字） | LibreOffice + Noto Sans TC | reject GLYPH_MISSING |
| L08 | 彩色底色或圖片背景上的文字 | LibreOffice + Noto Sans TC | support |
| I08 | 單張圖片替換 | Word + 小畫家 | support |
| B07 | 規則表格改單格 | Word + Noto Serif TC | support |
| B08 | 含合併儲存格的表格 | LibreOffice + Noto Sans TC | reject UNSUPPORTED_LAYOUT |
| U06 | XFA 表單 | LiveCycle／AEM Forms Designer；沒有就標「無法製作」 | reject UNSUPPORTED_FEATURE |
| S07 | 損毀檔 | LibreOffice + 記事本 | reject MALFORMED_DOCUMENT |
| S08 | 600～800 頁的文件 | Word | reject RESOURCE_LIMIT |

### 5.1 先懂這件事：製作人不修改 PDF

製作人每份只做兩件事：

1. **做一份 PDF**，做好之後就不再動它。
2. **寫一張「答案卡」**，記下「將來要叫程式把哪裡改成什麼、預期結果是什麼」。

真正的修改在 P8 盲測時，由保管人用 PEditor 照答案卡操作，再檢查程式改得對不對、該拒絕時有沒有拒絕。
所以下文的「挑一個詞換成某個詞」，意思是**在答案卡上指定**，不是現在動手改。

下文各份的示範文字**請勿照抄**，請自己另外編；示範內容工程師也看得到，照抄就不算盲測。

### 5.2 共通規則

**環境**：Windows 11 已內建 Noto Sans TC／Noto Serif TC，在 Word／LibreOffice 字型清單找得到即可，不必另裝。

**內容**：
- 一律為**自己編的合成文字**，不得使用真實公文、人名、身分證號、電話、機關名稱。
- 紙張 A4 直向，邊界與字級用預設（字級 12）。每份文件第一行打編號（例如 `T10`）。
- 「原文」必須在整份文件中**只出現一次**，否則程式不知道要改哪一處。

**設定字型**（中文與英數字要一起設）：
- Word：`Ctrl+A` 全選 → `Ctrl+D` 開「字型」視窗 →「中文字型」與「英文字型」都選指定字型 → 確定。
- LibreOffice：`Ctrl+A` 全選（游標在表格內時要按兩次）→ 格式 → 字元 →「字型」分頁 →「西方文字字型」與「亞洲文字字型」都選指定字型 → 確定。

**匯出 PDF**：設定同 4.3（不要勾 PDF/A、不要勾混合 PDF），**並依 4.3「個資」一段清空作者**。
- Word：檔案 → 另存新檔 → 存檔類型選 **PDF**。
- LibreOffice：檔案 → 匯出為 → **匯出為 PDF…**。
- 檔名用編號（例如 `T10.pdf`），存到加密隨身碟，例如 `E:\blind`。

**確認原文只出現一次**：用 Edge 開啟 PDF，按 `Ctrl+F` 搜尋原文，結果要剛好 **1 筆**。搜不到通常是空格沒打對，換一段原文或照 PDF 實際內容抄。

**答案卡**：每份一張，用記事本存成同編號的 `.txt`（例如 `E:\blind\T10.txt`），**編碼選 UTF-8**。至少寫：

```
編號：
目標頁：第 1 頁
原文：（一字不差，空格也算）
新文：
預期：支援／拒絕＋原因（修改後應顯示什麼、哪些東西不能變）
```

開檔即應拒絕的樣本（U06、S07、S08）不需要原文與新文，目標寫「開啟即應拒絕」。

### 5.3 T10：一般段落，同字數替換（Word）

**測什麼**：最基本的改字，新文用的字文件裡大多已經有。

1. 開 Word 新空白文件，第一行打 `T10`。
2. 第二行起打 3～5 行自己編的中文段落。
   示範：「本週五下午將進行辦公室消防設備檢查，請各位同仁配合，檢查期間請勿使用茶水間。」
3. 字型設為 **Noto Serif TC**（見 5.2），匯出 `T10.pdf`。
4. 從段落挑一個詞當原文（示範：「消防」），在 Edge 搜尋確認只有 1 筆。
5. 想一個**字數相同**的新詞（示範：「電氣」）。
6. 寫答案卡：

```
編號：T10
目標頁：第 1 頁
原文：消防
新文：電氣
預期：支援（修改後應顯示「…辦公室電氣設備檢查…」，其他文字不變）
```

### 5.4 T11：中英數混排，替換成較短文字（LibreOffice）

**測什麼**：中文、英文、數字混在同一行，而且新文比原文短。

1. 開 LibreOffice Writer，第一行打 `T11`。
2. 第二行打一句**同時有中文、英文、數字**的話。
   示範：「新版系統 v2.3 預計於 3 月 15 日上線，屆時支援 PDF 與 Excel 檔案匯入。」
3. 字型設為 **Noto Sans TC**（西方與亞洲都要設，見 5.2），匯出 `T11.pdf`。
4. 原文挑**含英文或數字**的一段（示範：「PDF 與 Excel」），在 Edge 搜尋確認只有 1 筆。
5. 新文要**比原文短**（示範：「CSV」）。
6. 寫答案卡：

```
編號：T11
目標頁：第 1 頁
原文：PDF 與 Excel
新文：CSV
預期：支援（修改後應顯示「…屆時支援 CSV 檔案匯入。」，其他文字不變）
```

注意：原文要照 PDF 上的樣子抄，中英文之間有沒有空格都要一致；不要只挑純中文的部分。

### 5.5 T12：瀏覽器列印的 PDF（記事本＋Edge）

**測什麼**：由瀏覽器產生的 PDF。

1. 開記事本，貼上下面內容，只把「在這裡打自己編的中文段落」換成自己編的 3～5 句中文，其他行不要動：

```html
<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>T12</title>
<style>body { font-family: "Noto Sans TC"; font-size: 12pt; }</style>
</head>
<body>
<p>T12</p>
<p>在這裡打自己編的中文段落</p>
</body>
</html>
```

   示範：`<p>下週一上午九點將進行全棟停電維修，請各單位提前儲存檔案並關閉電腦。</p>`
2. 檔案 → 另存新檔：「存檔類型」選「**所有檔案 (\*.\*)**」（否則會變成 `T12.html.txt`），檔名 `T12.html`，編碼 **UTF-8**，存到 `E:\blind`。
3. 在檔案總管對 `T12.html` 按右鍵 → 開啟檔案 → **Microsoft Edge**，確認中文正常。
4. 在 Edge 按 `Ctrl+P`：
   - 「印表機」選「**另存為 PDF**」（**不要**選「Microsoft Print to PDF」，那是 T09 測過的另一種來源）。
   - 版面配置「直向」；按「更多設定」：紙張 **A4**、邊界「預設」、「**頁首及頁尾**」**不要勾**（勾了會印出日期與檔案路徑）。
   - 按「儲存」，存成 `E:\blind\T12.pdf`。
5. 開啟 `T12.pdf`，確認文字正常、頁面上沒有日期或路徑。
6. 挑一個詞當原文（示範：「停電」），搜尋確認只有 1 筆；新文**字數相同**（示範：「消毒」）。
7. 寫答案卡：

```
編號：T12
目標頁：第 1 頁
原文：停電
新文：消毒
預期：支援（修改後應顯示「…將進行全棟消毒維修…」，其他文字不變）
```

### 5.6 F09：新字是原文件沒用過的字（Word）

**測什麼**：Word 匯出 PDF 時只放入**文件用到的字**（字型子集）。新文若有 PDF 裡沒有的字，程式須自行從字型補進字形（模式 B）。

1. 開 Word 新空白文件，第一行打 `F09`。
2. 第二行打 2～3 句自己編的中文。段落**不要太長**，比較容易找到沒出現過的字。
   示範：「本月社區活動改在三樓會議室舉行，請住戶準時出席。」
3. 字型設為 **Noto Serif TC**，匯出 `F09.pdf`。
4. 挑一個詞當原文（示範：「三樓」），搜尋確認只有 1 筆。
5. 想一個字數相同的新詞（示範：「五樓」），把新詞**每個字分別**在 Word 用 `Ctrl+F` 搜尋：
   - 至少要有一個字是 **0 筆**（示範中「五」是 0 筆）；全部都搜得到就換一個新詞。
   - 新字要是**常用字**（數字、方位、顏色等），不要用罕用字（那是 F10）。
6. 寫答案卡：

```
編號：F09
目標頁：第 1 頁
原文：三樓
新文：五樓
不在文件中的新字：五
預期：支援（模式 B；修改後應顯示「…改在五樓會議室舉行…」，其他文字不變）
```

注意：新字**只寫在答案卡**，絕對不要打進 Word 文件，否則 PDF 會內含這個字，測試就失效。

### 5.7 F10：新字是字型沒有的罕用字（LibreOffice）

**測什麼**：新字連字型檔都沒有（𠮷，上面是「土」，Unicode U+20BB7），程式不能硬改，必須拒絕並回報缺字。

1. 開 LibreOffice Writer，第一行打 `F10`。
2. 第二行打一段自己編的中文，裡面放一個**含「吉」的虛構地名或店名**（文件裡只打一般的「吉」）。
   示範：「本次巡迴展覽第二站設於大吉里活動中心，開放時間為上午九點至下午五點。」
   已登記的 F08 用過「吉野」，請不要用「吉野」。
3. 字型設為 **Noto Sans TC**（西方與亞洲都要設），匯出 `F10.pdf`。
4. 原文挑含「吉」的那個詞（示範：「大吉里」），搜尋確認只有 1 筆。
5. 新文把「吉」換成「𠮷」（示範：「大𠮷里」）。「𠮷」不好打，請從本手冊直接複製：𠮷
6. 寫答案卡，存檔時編碼**一定要選 UTF-8**；存完重新開啟，確認「𠮷」沒有變成「?」或方框：

```
編號：F10
目標頁：第 1 頁
原文：大吉里
新文：大𠮷里
缺字：𠮷（U+20BB7）
預期：拒絕 GLYPH_MISSING（字型沒有「𠮷」，程式應拒絕修改，PDF 保持原樣）
```

注意：
- 「𠮷」**只寫在答案卡**，不要打進文件。
- **只用「𠮷」**，不要換成其他罕用字：其他擴充區字有些 Noto 字型其實有收錄，就不會被拒絕。

### 5.8 L08：彩色底色或圖片背景上的文字（LibreOffice）

**測什麼**：目標文字下面有背景。程式只能改字，背景必須完整，不能出現白框或缺角。

1. 開 LibreOffice Writer，第一行打 `L08`。
2. 第二行打一句自己編的中文。示範：「重要提醒：本週四起門禁卡將更換為新版，請至服務台領取。」
3. 字型設為 **Noto Sans TC**（西方與亞洲都要設）。
4. 加背景，**二選一**：
   - **甲、彩色底色**：游標放在第二行 → 格式 → 段落 →「區域」分頁 → 按「色彩」→ 選**淺色**（淺黃、淺藍、淺綠）→ 確定。
   - **乙、圖片背景**：
     1. 用小畫家畫一張長條形的淺色圖（可塗幾種顏色或花紋，不要照片或人臉），存成 PNG，例如 `E:\blind\L08-bg.png`。
     2. LibreOffice：插入 → 影像… → 選這張圖。
     3. 在圖片上按右鍵 → 環繞 →「**置於背景**」。
     4. 拖動圖片到第二行文字的**正後方**，確認文字清楚可讀。
5. 匯出 `L08.pdf`（用圖片背景時，影像選「**無失真壓縮**」，見 4.3）。開啟確認文字疊在色塊或圖片上。
6. 原文要挑**疊在背景上**的詞（示範：「門禁卡」），搜尋確認只有 1 筆；新文**字數相同**（示範：「識別證」）。
7. 寫答案卡：

```
編號：L08
目標頁：第 1 頁
原文：門禁卡
新文：識別證
背景：段落底色（淺黃）　← 圖片背景請寫「圖片背景 L08-bg.png」
預期：支援（修改後應顯示「…將更換為新版識別證…」；背景色塊／圖片要完整，不能出現白框或缺角）
```

### 5.9 I08：單張圖片替換（Word＋小畫家）

**測什麼**：把頁面上的一張圖換成另一張。新圖要放在原圖位置、大小相同，其他文字不能動。

1. **畫兩張圖**（小畫家，不要照片或人臉）：
   - 原圖：影像 → 調整大小與扭曲 → 單位「像素」、取消「維持外觀比例」、寬 **400** 高 **300** → 畫一些圖形（示範：藍色圓形＋紅色方塊）→ 存成 `E:\blind\I08-old.png`。
   - 新圖：一樣 **400 × 300 像素**，畫一張**明顯不同**的圖（示範：綠色三角形＋黃色星星）→ 存成 `E:\blind\I08-new.png`。
2. 開 Word 新空白文件：
   - 第一行打 `I08`；第二行打一句說明（示範：「下圖為本季活動示意圖。」）。
   - 第三行：插入 → 圖片 → 此裝置 → 選 `I08-old.png`。保持預設的「**與文字排列**」，**不要**裁剪、加框線或特效。
   - 第四行再打一句（示範：「詳細內容請洽承辦單位。」）。
   - 文字字型用 **Noto Sans TC**。整份文件**只能有這一張圖**。
3. 匯出 `I08.pdf`，開啟確認圖片與上下兩行文字都正常。
4. 寫答案卡：

```
編號：I08
目標頁：第 1 頁
目標：頁面上唯一的一張圖片（藍色圓形＋紅色方塊）
新圖：E:\blind\I08-new.png（綠色三角形＋黃色星星，400×300 像素）
預期：支援（修改後圖片換成新圖，位置與大小和原圖相同；上下兩行文字不變）
```

注意：
- 新圖**不要放進 Word 文件**，只存在隨身碟。
- 兩張圖的**像素尺寸要相同**，比例不同時程式會留白或拉伸，無法判斷對錯。
- 新圖不要太大（幾百到一兩千像素寬即可），太大會被程式的像素上限擋下，那是另一種測試。

### 5.10 B07：規則表格改單格（Word）

**測什麼**：只改表格中的一格。其他格文字不能動，格線位置與粗細不能變，新字要放得進那一格。

1. 開 Word 新空白文件，第一行打 `B07`。
2. 插入 → 表格 → 拖出 **3×3**。保持預設格線，**不要合併任何儲存格**。
3. 每格打**一行**簡短文字（2～6 字），**九格內容都不重複**，每格都要有字。示範：

| 品項 | 數量 | 存放位置 |
| --- | --- | --- |
| 投影機 | 2 台 | 二樓會議室 |
| 延長線 | 5 條 | 一樓倉庫 |

4. 字型設為 **Noto Serif TC**，匯出 `B07.pdf`，開啟確認表格、格線、文字都正常。
5. 挑中間或右邊的一格當目標（示範：第 2 列第 3 欄「二樓會議室」），搜尋確認只有 1 筆。
6. 新文**字數相同或更少**、一行（示範：「三樓會議室」）。
7. 寫答案卡：

```
編號：B07
目標頁：第 1 頁
目標格：第 2 列第 3 欄（列由上往下數、欄由左往右數，第 1 列是標題列）
原文：二樓會議室
新文：三樓會議室
預期：支援（修改後該格顯示「三樓會議室」；其他 8 格文字不變；格線位置與粗細不變，不能出現白框或斷線）
```

### 5.11 B08：含合併儲存格的表格（LibreOffice）

**測什麼**：合併儲存格不在支援範圍。程式必須拒絕並回報版面不支援，PDF 保持原樣。
已登記的 B06 是左右合併；B08 請做**上下合併**，兩份才不同。

1. 開 LibreOffice Writer，第一行打 `B08`。
2. 表格 → 插入表格…（`Ctrl+F12`）→ 欄 **3**、列 **4** → 插入。
3. 選取**第 1 欄的第 2、3 列**兩格 → 表格 → **合併儲存格**。兩格會變成一個直的高格子：

```
┌────────┬────────┬────────┐
│  第1列  │        │        │
├────────┼────────┼────────┤
│        │        │        │
│ 合併格  ├────────┼────────┤
│        │        │        │
├────────┼────────┼────────┤
│  第4列  │        │        │
└────────┴────────┴────────┘
```

4. 每格打一行簡短文字，內容不重複、每格都有字；**合併格裡打一個詞**（之後的目標）。人名改用「甲組、乙組」等代稱。
   示範：合併格「行政支援」，右側「文具採購／甲組」「會場布置／乙組」，第 4 列「資訊支援／網路設定／丙組」。
5. 字型設為 **Noto Sans TC**（西方與亞洲都要設），匯出 `B08.pdf`，確認合併格中間沒有橫線。
6. 原文是**合併格裡的詞**（示範：「行政支援」），搜尋確認只有 1 筆；新文任意（示範：「後勤支援」）。
7. 寫答案卡：

```
編號：B08
目標頁：第 1 頁
目標格：第 1 欄第 2～3 列的合併格（上下合併）
原文：行政支援
新文：後勤支援
預期：拒絕 UNSUPPORTED_LAYOUT（程式應說明不支援合併儲存格，不得修改；另存後 PDF 內容與原檔相同）
```

注意：目標一定要是**合併格裡的字**；挑普通格的字就測不到拒絕。

### 5.12 U06：XFA 表單（可能無法製作）

**測什麼**：XFA 是 Adobe 早期的表單格式，內容存在另一套 XML 中。程式開啟時必須拒絕並回報不支援的功能。

Word、LibreOffice、瀏覽器都做不出 XFA；一般 Acrobat Pro「準備表單」做的也**不是** XFA。
只有 **Adobe LiveCycle Designer**（新名 **AEM Forms Designer**）能做。請先確認單位內有沒有人裝了這個軟體。

**有 Designer 時**（介面常為英文）：
1. 檔案 → 新增（File → New）→ 使用空白表單（Use a Blank Form）。
2. 放一個「文字」（Text）物件打 `U06`。
3. 從「物件庫」（Object Library）拖一個「文字欄位」（Text Field），標題（Caption）打自己編的字（示範：「申請單位」）。
4. 再放一個「文字」物件，打一句說明（示範：「本表單僅供測試使用。」）。字型能選 Noto Sans TC 就選，沒有就用預設。
5. 檔案 → 另存新檔（Save As）→ 類型選「**Adobe 動態 XML 表單**」（Adobe Dynamic XML Form），存成 `E:\blind\U06.pdf`。
6. 用 Edge 開啟：出現「Please wait...」或要求用 Adobe Reader 開啟的訊息，表示是動態 XFA，製作成功。
7. 寫答案卡：

```
編號：U06
製作工具：Adobe LiveCycle Designer（版本：____）
存檔類型：Adobe 動態 XML 表單
目標：開啟即應拒絕
預期：拒絕 UNSUPPORTED_FEATURE（程式應說明不支援 XFA 表單，不得進入編輯）
```

**沒有 Designer 時**：直接標「無法製作」，不必勉強：

```
編號：U06
狀態：無法製作
原因：單位內沒有可建立 XFA 表單的軟體（LiveCycle Designer／AEM Forms Designer）
```

不要從網路下載現成的 XFA 表單（屬真實公務文件，來源不明也可能夾帶指令碼）；也不要請工程師或 AI 代做（失去盲測意義）。

### 5.13 S07：損毀檔（LibreOffice＋記事本）

**測什麼**：壞掉的 PDF。程式不能當機或卡住，必須拒絕並回報檔案損毀。

1. 先做一份**新的小 PDF**（不要拿其他盲測樣本）：LibreOffice Writer 第一行打 `S07`，第二行打一兩句中文，字型 **Noto Sans TC**，匯出成 `E:\blind\S07-good.pdf`。
   用 LibreOffice 做的 PDF 只有幾十 KB，記事本開起來快。
2. 在檔案總管複製、貼上 `S07-good.pdf`，把複本改名為 `S07.pdf`。之後只動 `S07.pdf`。
3. 開記事本 → 檔案 → 開啟 → 右下角檔案類型改「**所有檔案 (\*.\*)**」→ 選 `S07.pdf`。畫面是一堆亂碼，這是正常的。
4. 捲到**大約中間**，選取 **10～20 行**按 `Delete`。
   - **不要刪最前面**（開頭 `%PDF-` 那行要留）；**不要刪最後幾行**（結尾 `%%EOF` 要留）。
5. `Ctrl+S` 存檔（有編碼提示直接確定），關閉記事本。
6. 確認 `S07.pdf` 的檔案大小和 `S07-good.pdf` **不同**；相同表示沒刪成功，重做第 4 步。
7. 用 Edge 開啟 `S07.pdf`，記下結果。打不開、版面變亂、看起來正常（Edge 會自動修復）都算成功。
8. 寫答案卡：

```
編號：S07
來源：S07-good.pdf（LibreOffice 匯出）的複本
損壞方式：記事本開啟，刪除中間約 15 行後儲存
Edge 開啟結果：（例如：顯示「無法開啟此 PDF」／打得開但文字消失／看起來正常）
目標：開啟即應拒絕
預期：拒絕 MALFORMED_DOCUMENT（程式應說明檔案損毀，不當機、不卡住、不得進入編輯）
```

hash 清冊中也會有 `S07-good`，以 `S07` 那一行為準。

### 5.14 S08：600～800 頁的文件（Word）

**測什麼**：程式的頁數上限是 500 頁。超過時必須**很快**拒絕並回報超過資源上限，不能先整份讀完、卡住或當機。

1. 開 Word 新空白文件，第一行打 `S08`，第二行起打幾行自己編的中文（示範：「這是頁數測試文件的內容，每一頁都相同。」）。字型 **Noto Sans TC**。
2. `Ctrl+End` 移到最後，按 `Ctrl+Enter` 插入分頁符號。
3. （建議）插入 → 頁碼 → 頁面底端 → 純數字 2，方便確認頁數。
4. **加倍複製**：依序按 `Ctrl+A`（全選）→ `Ctrl+C`（複製）→ `Ctrl+End`（跳到最後）→ `Ctrl+V`（貼上），算一輪；每輪頁數約變兩倍：

```
第 1 輪 → 約 2 頁　　第 4 輪 → 約 16 頁　　第 7 輪 → 約 128 頁
第 2 輪 → 約 4 頁　　第 5 輪 → 約 32 頁　　第 8 輪 → 約 256 頁
第 3 輪 → 約 8 頁　　第 6 輪 → 約 64 頁　　第 9 輪 → 約 512 頁
```

5. 第 9 輪做完後，**只再按一次 `Ctrl+V`**（不要重新全選複製），總頁數約 770。
   Word 左下角狀態列顯示「第 X 頁，共 Y 頁」，確認 **Y 在 600～800 之間**。後幾輪貼上要等幾秒，等頁數更新再按下一鍵。
6. 匯出 `S08.pdf`（可能要一兩分鐘）。Word 文件本身不用存。
7. 用 Edge 開啟，確認上方顯示的總頁數**超過 500**。
8. 寫答案卡：

```
編號：S08
總頁數：770（以 Edge 顯示為準）
檔案大小：____ MB
目標：開啟即應拒絕
預期：拒絕 RESOURCE_LIMIT（超過 500 頁上限；程式應在短時間內說明原因並拒絕，不得卡住、當機或進入編輯）
```

盲測時請記下程式花多久拒絕；超過 30 秒才回應也要記錄。

### 5.15 製作與保管

1. 依 5.3～5.14 製作。所有 PDF、圖片、答案卡都存在加密隨身碟，例如 `E:\blind`。
2. 建立 hash 清冊：

```powershell
Get-FileHash -Algorithm SHA256 E:\blind\*.pdf |
  Select-Object @{n="fixture_id";e={[IO.Path]::GetFileNameWithoutExtension($_.Path)}}, Hash |
  Export-Csv E:\blind\hash-ledger.csv -NoTypeInformation -Encoding UTF8
Get-Content E:\blind\hash-ledger.csv
```

3. 只把 `hash-ledger.csv`（只有編號與 hash，沒有內容）交給工程師，供 P8 確認檔案未被更動。
4. 隨身碟由保管人收存；P8 盲測時由保管人在離線實機上執行。

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
