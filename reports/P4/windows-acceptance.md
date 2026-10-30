# P4 Windows 實機驗收清單（G4，報告 §9 U1）

本清單補 offscreen 測試驗證不到的項目：實際輸入法、實按快捷鍵、中文介面字型、原生檔案對話框、人工操作 E2E。
結果填在每項的「結果」欄（PASS／FAIL／NOT RUN＋原因），完成後交給 Claude 寫回 `reports/P4/report.md`（§3 實機欄、§7、§10）。

- 只用 repo 內的合成 fixture（`tests/fixtures/files/`），**不要用真實公文**。
- 截圖若含使用者名稱或完整路徑（檔案對話框、PowerShell 視窗常見），請裁掉或塗掉再提交（CLAUDE.md）。截圖放 `reports/P4/evidence/windows/`，檔名用項目編號（例如 `W03.png`）。
- 每項 FAIL 請記：實際看到什麼、可否重現、當時的輸入法。
- 標「已知不符」的項目是獨立核對已發現、工程師決定列 P7 的產品問題（報告 §9 U12–U14）；照實記錄即可。
- 頁面空白：T01、F02、F05 屬 ADR-0015 的 MuPDF 空白檔，頁面與預覽圖空白、只看得到藍框或灰框，屬預期，不算失敗。
- 預估 60–90 分鐘。

## 0. 環境紀錄

| 項目 | 填寫 |
| --- | --- |
| 日期／執行人 | |
| Windows 版本（`winver`） | |
| 顯示縮放（設定 → 系統 → 顯示器） | |
| 輸入法（例：微軟注音、倉頡、速成） | |
| commit（`git rev-parse --short HEAD`） | |
| 是否為一般使用者帳號（非系統管理員） | |

## 1. 準備

以下指令請**直接貼到 PowerShell 視窗**執行（不要存成 .ps1：Windows PowerShell 5.1 讀無 BOM 的腳本會弄壞中文與 emoji 路徑）。
整個驗收期間都用**同一個 PowerShell 視窗**啟動 PEditor：`$env:PEDITOR_MODE_B_FONT` 只在這個視窗有效，沒設定時模式 B 不可用（W13、W16、W25、W26 會失敗）。

```powershell
cd <PEditor 資料夾>
git switch p4-desktop-ui
git pull
uv sync --locked --all-groups
uv run python scripts/fetch_fonts.py
$env:PEDITOR_MODE_B_FONT = (Resolve-Path tests\fixtures\fonts\NotoSansTC-Regular.otf).Path

# 測試用資料夾：中文＋空白＋emoji 路徑（emoji 以字碼組成，避免編碼問題）
$e = [char]::ConvertFromUtf32(0x1F600)
$W = Join-Path ([Environment]::GetFolderPath('Desktop')) "P4驗收"
New-Item -ItemType Directory -Force "$W\中文 資料夾" | Out-Null
New-Item -ItemType Directory -Force "$W\表情$e" | Out-Null
Copy-Item tests\fixtures\files\F04.pdf "$W\中文 資料夾\公文 草稿.pdf"
Copy-Item tests\fixtures\files\T05.pdf "$W\表情$e\稽核$e.pdf"
Copy-Item tests\fixtures\files\F04.pdf "$W\F04.pdf"
(Get-FileHash "$W\中文 資料夾\公文 草稿.pdf").Hash   # 記下：原檔 hash（W20 比對）
explorer $W

uv run peditor
```

之後每次要「重新啟動 PEditor」，都在同一個視窗再執行 `uv run peditor`。
若啟動時出現「復原草稿」對話框（先前測試留下的），選「捨棄」直到清空，再開始 W01。

## 2. 開啟與檢視（G4-01、G4-03、G4-05、G4-07、G4-08）

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W01 | 看主視窗的工具列、側欄、狀態列（尚未開檔） | 中文標籤（開啟、另存新檔、復原、重做、取消、選取的文字、新文字、預覽、修改前、修改後、套用、尋找）正常顯示，無方框或亂碼；標題為 `PEditor <版本>`；多數按鈕灰色屬正常 | |
| W02 | 按工具列「開啟」，在**原生檔案對話框**中瀏覽到 `P4驗收\中文 資料夾`，選 `公文 草稿.pdf` | 頁面與縮圖出現；狀態列「已開啟，共 1 頁」；提示列空白 | |
| W03 | 「開啟」→ 在對話框中選 `P4驗收\表情😀\稽核😀.pdf` | 第一行「本府辦理年度資訊安全稽核，請各單位配合…」中文字形正確，不是空白或方框 | |
| W03b | 開啟 `tests\fixtures\files\B02.pdf`（表格，Noto Serif TC；traceability G4-07 預登記的實機樣本） | 表格中「市府大樓」等明體中文字形正確 | |
| W04 | 開啟 `tests\fixtures\files\T01.pdf` | 頁面空白（預期）；提示列「此頁字型不符 PDF 規範（CID 與字型程式不一致），預覽可能空白；另存不受影響」 | |
| W05 | 開啟 `tests\fixtures\files\U01.pdf` | 提示列「此頁：此頁沒有文字層（例如掃描或圖片頁），只能檢視」 | |
| W06 | 開啟 `tests\fixtures\files\U02.pdf`（加密），再開 `S01.pdf`（損壞） | U02：狀態列「已開啟，共 0 頁」、提示列「此檔不能編輯：文件已加密，不提供編輯」。S01：提示列「此頁：檔案結構損壞或需修復，不提供編輯」。都不當掉、不含路徑。**已知不符（U13，列 P7）**：開 U02 後頁面區仍顯示前一份文件，請記下是否還能點選其中的框 | |

## 3. 點選、預覽、套用、復原（G4-01、G4-05、G4-06）

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W07 | 開啟 `P4驗收\中文 資料夾\公文 草稿.pdf`，在頁面上點「World」 | 側欄「選取的文字」為 `Hello World`；新文字欄預填 `Hello World`；「預覽」可按 | |
| W08 | 新文字改為 `Hello Earth`，按「預覽」 | 「修改前／修改後」兩張圖不同；顯示「模式 A（沿用原字型）」；狀態列「預覽完成，按「套用」提交」；頁面本身**尚未**改變；「復原」仍不可按 | |
| W09 | 按「套用」 | 頁面顯示 `Hello Earth`；狀態列「已更新」；「復原」可按 | |
| W10 | **先點一下頁面空白處**（讓焦點離開輸入欄），再按 **Ctrl+Z** | 回到 `Hello World`；「重做」可按。另記：若不先點頁面、焦點留在輸入欄時按 Ctrl+Z，是否沒有作用（**已知不符，U12 列 P7**：輸入欄會吃掉 Ctrl+Z） | |
| W11 | 焦點在頁面時按 **Ctrl+Y** | 回到 `Hello Earth`。另按 Ctrl+Z 再按 **Ctrl+Shift+Z**，記下是否有作用（**已知不符，U12 列 P7**：目前只綁 Ctrl+Y） | |
| W12 | 點頁面上那行字（`Hello Earth` 或 `Hello World` 皆可），新文字輸入 `Hello ` 加 80 個 `W`，按「預覽」 | 側欄「無法修改：新文字會超出可改動區域；不會自動縮小字級」；狀態列「無法修改」；「套用」不可按 | |
| W13 | 開啟 `tests\fixtures\files\F02.pdf`，點頁面上**唯一的藍框**（頁面空白屬預期），新文字改為 `藥事人員名冊`，按「預覽」 | 側欄顯示「模式 B（字型替換）」與 Noto Sans TC 字型替換說明；修改前／後圖空白不算失敗 | |
| W14 | 開啟 `tests\fixtures\files\F05.pdf`，點頁面上的灰框 | 側欄「無法編輯：字型編碼無法可靠對應文字（缺少或不一致的 ToUnicode），無法安全修改」；「預覽」不可按。「選取的文字」顯示亂碼屬預期（此檔沒有 ToUnicode） | |
| W15 | 開啟 T01，在「尋找文字」輸入 `衛生局`，按「尋找」，新文字改 `測試局`，預覽、套用；再按 Ctrl+Shift+S 存成 `P4驗收\T01-out.pdf`，用 Edge 開啟 | 選取為 `衛生局`；狀態列「已更新」「已另存」；Edge 中看到「臺北市政府測試局公告」（Edge 用 PDFium，此檔可正常顯示） | |

## 4. 繁中輸入法（G4-02，U3、U7）

先開啟 `P4驗收\中文 資料夾\公文 草稿.pdf`，點那行字，於「新文字」欄操作（「測試」需模式 B，須已設定 §1 的字型）。每種輸入法各做一次（至少微軟注音；有倉頡／速成者一併）。

| # | 步驟 | 預期 | 結果（注音） | 結果（其他） |
| --- | --- | --- | --- | --- |
| W16a | 清空新文字欄，用輸入法打「測試」，**組字中（字下有底線、尚未確認）不要按任何鍵**，觀察 3 秒 | 不會自動預覽；修改前／修改後圖不變 | | |
| W16b | 組字中按 **Enter** | Enter 只確認組字（字變為一般文字），**不觸發預覽**；若有觸發，記下預覽使用的文字（側欄或修改後圖）是否為完整確認後的「測試」 | | |
| W16c | 確認後再按一次 Enter | 以「測試」預覽一次（模式 B） | | |
| W16d | 組字中直接按「預覽」按鈕 | 預覽使用的文字不含注音符號或半成品，等於欄位最後顯示的文字（滑鼠點按鈕時輸入法通常會先確認組字，屬合理） | | |
| W16e | 組字中按 Esc | 只取消組字，不會取消其他操作、不報錯 | | |
| W16f | 打一個字後用選字視窗選同音字（例如「試→是」） | 選字視窗位置在輸入欄附近；選的字正確進入欄位 | | |

## 5. 另存與路徑（G4-01、G4-03）

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W17 | 開啟 `中文 資料夾\公文 草稿.pdf`，點那行字，改 `Hello Earth`，預覽、套用，按 **Ctrl+Shift+S** | 出現原生「另存新檔」對話框 | |
| W18 | 存到 `P4驗收\表情😀\輸出 結果😀.pdf` | 狀態列「已另存」；用 Edge 開該檔看到 `Hello Earth`；原檔 `公文 草稿.pdf` 仍是 `Hello World` | |
| W19 | （仍在編輯 `公文 草稿.pdf`）再按 Ctrl+Shift+S，選同一個 `輸出 結果😀.pdf` | 原生對話框詢問是否取代；選「是」後狀態列「已另存」，檔案可正常開啟 | |
| W20 | （仍在編輯 `公文 草稿.pdf`）按 Ctrl+Shift+S，選原檔 `公文 草稿.pdf` 本身 | 原生對話框詢問是否取代；選「是」後狀態列與側欄顯示「操作無法執行」（不可覆寫原檔）；`(Get-FileHash "$W\中文 資料夾\公文 草稿.pdf").Hash` 與 §1 記下的相同 | |
| W21 | 在 PEditor 開啟 `表情😀\輸出 結果😀.pdf` | 頁面為 `Hello Earth` | |
| W22 | 在 PowerShell 執行下方指令 | 沒有任何 `.~peditor-*.tmp.pdf` 殘留（暫存檔不是隱藏檔，用 `-Force` 只是保險） | |

```powershell
Get-ChildItem -Force -Recurse $W -Filter ".~peditor-*"
```

## 6. 快捷鍵與回應（G4-04、G4-06）

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W23 | 按 **Ctrl+O** | 開啟檔案對話框 | |
| W24 | 將滑鼠停在工具列各按鈕上 | 記下提示內容。**已知**：目前只顯示按鈕名稱（例如「開啟」），不顯示快捷鍵（U12，列 P7） | |
| W25 | 在 F02 做模式 B 預覽（W13）時拖動視窗、捲動縮圖 | 視窗不凍結、不出現「沒有回應」。操作約 0.5 秒，只能排除明顯凍結；量化證據以 `test_responsiveness`（offscreen）為準 | |
| W26 | 在 F02 按「套用」後立刻按 **Esc**（取消） | 若來得及取消：狀態列「已取消，未提交變更」、頁面不變、「復原」不可按。套用約 0.15 秒，人手多半來不及，此時標 NOT RUN（報告 §7、U14 列 P7：G4-04 實機無法人工重現） | |

## 7. 復原草稿（G4-01、G4-09）

強制結束 PEditor 的指令（W27、W30 使用；在另一個 PowerShell 視窗執行）：

```powershell
Get-Process | Where-Object MainWindowTitle -like 'PEditor *' | Stop-Process -Force
Start-Sleep 3; Get-Process python -ErrorAction SilentlyContinue   # 記下是否還有殘留的 python 行程
```

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W27 | 開啟 `P4驗收\F04.pdf`，點那行字，套用 `Hello Earth`（不要另存），**等狀態列顯示「已更新」**，再以上方指令強制結束 | PEditor 關閉；沒有殘留的 PEditor worker（若有 python 行程，記下數量） | |
| W28 | 重新啟動 PEditor | 出現「復原草稿」對話框：「找到 N 份未儲存的編輯草稿，請選擇要復原或捨棄的草稿：」，清單至少有 `F04.pdf　1 項編輯　<yyyy-MM-dd HH:mm>`，不顯示完整路徑；按鈕「復原／捨棄／稍後再說」 | |
| W29 | 選 `F04.pdf` 那份，按「復原」 | 開啟 `F04.pdf`，頁面為 `Hello Earth`；「復原」可按 | |
| W30 | 開啟 `中文 資料夾\公文 草稿.pdf`，套用一次，強制結束。重新啟動，對話框出現時按「**稍後再說**」；開啟 `P4驗收\F04.pdf`，套用一次，強制結束。再重新啟動 | 對話框列出 `公文 草稿.pdf` 與 `F04.pdf` 兩份；選一份按「捨棄」後，對話框再出現並只剩另一份；按「稍後再說」關閉 | |
| W31 | 重新啟動，把對話框中所有草稿「捨棄」。開啟 `P4驗收\F04.pdf`，套用一次，按視窗 **✕** 正常關閉，再重新啟動 | 依 ADR-0020 §5，正常關閉的文件不留草稿：不出現「復原草稿」對話框（U11 已修正） | |

## 8. 收尾

```powershell
Remove-Item -Recurse -Force $W
```

| 統計 | 填寫 |
| --- | --- |
| PASS 數／總數 | |
| FAIL 項目 | |
| NOT RUN 項目與原因 | |
| 其他觀察（字型模糊、高 DPI 版面、對話框文字截斷等） | |

## 附：對照

| G4 條件 | 本清單項目 | 自動測試（offscreen，非實機） |
| --- | --- | --- |
| G4-01 E2E 流程（12 個 `test_flow_*`） | 開檔 W02、點選 W07、預覽 W08、套用 W09、undo／redo W10–W11、另存重開 W17–W18／W21、覆寫 W19、模式 B W13、溢出 W12、尋找 W15、預覽不可靠 W04、復原草稿 W27–W31 | `tests/gui/test_e2e.py` |
| G4-02 IME | W16a–W16f | `tests/gui/test_ime.py` |
| G4-03 中文／空白／emoji 路徑 | W02、W03、W17–W21 | `tests/gui/test_paths.py` |
| G4-04 取消不提交 | W26（人工多半來不及，見報告 §7） | `test_e2e.py::test_cancel_does_not_commit` |
| G4-05 不可編輯原因（點選） | W05、W06、W14 | `test_e2e.py::test_reason_shown_for_uneditable` |
| G4-06 快捷鍵、不阻塞 | W10、W11、W17、W23–W25 | `tests/gui/test_shortcuts.py`、`test_responsiveness.py` |
| G4-07 中文字型 | W01、W03、W03b（B02） | `tests/gui/test_fonts.py`（只驗預覽圖） |
| G4-08 預覽 | W04、W08、W13 | `tests/integration/test_preview.py` |
| G4-09 草稿、暫存檔 | W20、W22、W27–W31 | `tests/gui/test_drafts_ui.py`、`test_startup.py`、`test_crash_injection.py` |
