# P4 Windows 實機驗收清單（G4，報告 §9 U1）

本清單補 offscreen 測試驗證不到的項目：實際輸入法、實按快捷鍵、中文介面字型、原生檔案對話框、人工操作 E2E。
結果填在每項的「結果」欄（PASS／FAIL／NOT RUN＋原因），完成後交給 Claude 寫回 `reports/P4/report.md`（§3 實機欄、§7、§10）。

- 只用 repo 內的合成 fixture（`tests/fixtures/files/`），**不要用真實公文**。
- 截圖若含使用者名稱或完整路徑，請裁掉或塗掉再提交（CLAUDE.md：不含完整檔案路徑）。截圖放 `reports/P4/evidence/windows/`，檔名用項目編號（例如 `W03.png`）。
- 每項 FAIL 請記：實際看到什麼、可否重現、當時的輸入法。
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

在 PEditor 資料夾以 PowerShell（一般使用者）執行：

```powershell
git switch p4-desktop-ui
git pull
uv sync --locked --all-groups
uv run python scripts/fetch_fonts.py

# 測試用資料夾：中文＋空白＋emoji 路徑
$W = Join-Path $env:USERPROFILE "Desktop\P4驗收"
New-Item -ItemType Directory -Force "$W\中文 資料夾" | Out-Null
New-Item -ItemType Directory -Force "$W\表情😀" | Out-Null
Copy-Item tests\fixtures\files\F04.pdf "$W\中文 資料夾\公文 草稿.pdf"
Copy-Item tests\fixtures\files\T05.pdf "$W\表情😀\稽核😀.pdf"
Copy-Item tests\fixtures\files\F04.pdf "$W\F04.pdf"

uv run peditor
```

若啟動時出現「復原草稿」對話框（先前測試留下的），選「捨棄」直到清空，再開始 W01。

## 2. 開啟與檢視（G4-01、G4-03、G4-07）

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W01 | 看主視窗的工具列、側欄、狀態列 | 中文標籤（開啟、另存新檔、復原、重做、取消、預覽、套用、尋找、修改前／修改後）都正常顯示，無方框或亂碼；標題為 `PEditor <版本>` | |
| W02 | 按工具列「開啟」，在**原生檔案對話框**中瀏覽到 `P4驗收\中文 資料夾`，選 `公文 草稿.pdf` | 頁面與縮圖出現；狀態列「已開啟，共 1 頁」；提示列空白 | |
| W03 | 「開啟」→ 選 `P4驗收\表情😀\稽核😀.pdf` | 頁面中文字形正確顯示（「資訊安全稽核」），不是空白或方框 | |
| W04 | 開啟 `tests\fixtures\files\T01.pdf` | 提示列顯示「此頁字型不符規範，預覽可能空白；另存不受影響」類訊息（PREVIEW_UNRELIABLE） | |
| W05 | 開啟 `tests\fixtures\files\U01.pdf` | 提示列說明沒有文字層（唯讀） | |
| W06 | 開啟 `tests\fixtures\files\U02.pdf`（加密）與 `S01.pdf`（損壞） | 各顯示繁中原因，不當掉；訊息不含完整路徑 | |

## 3. 點選、預覽、套用、復原（G4-01）

使用 W02 開啟的 `公文 草稿.pdf`（內容 `Hello World`）。

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W07 | 在頁面上點「World」 | 側欄「選取的文字」為 `Hello World`；新文字欄預填 `Hello World`；「預覽」可按 | |
| W08 | 新文字改為 `Hello Earth`，按「預覽」 | 「修改前／修改後」兩張圖不同；顯示「模式 A（沿用原字型）」；頁面本身**尚未**改變；「復原」仍不可按 | |
| W09 | 按「套用」 | 頁面顯示 `Hello Earth`；狀態列「已更新」；「復原」可按 | |
| W10 | 按 **Ctrl+Z**（不要點工具列） | 回到 `Hello World`；「重做」可按 | |
| W11 | 按 **Ctrl+Y**；再 Ctrl+Z 一次後改按 **Ctrl+Shift+Z** | 兩者都回到 `Hello Earth`（Qt 在 Windows 的「重做」標準鍵含這兩組） | |
| W12 | 點頁面上的 `Hello Earth`，新文字輸入 `Hello ` 加 80 個 `W`，按「預覽」 | 說明文字超出可改動區域（溢出）；「套用」不可按 | |
| W13 | 開啟 `tests\fixtures\files\F02.pdf`，點「醫事」，改為 `藥事人員名冊`，預覽 | 顯示「字型替換」與 `Noto Sans TC`（此檔預覽圖可能空白，屬 PREVIEW_UNRELIABLE，不算失敗） | |
| W14 | 開啟 `tests\fixtures\files\F05.pdf`，點頁面上的文字 | 側欄顯示「無法編輯：<原因>」；「預覽」不可按（G4-05） | |
| W15 | 開啟 T01，在「尋找文字」輸入 `衛生局`，按「尋找」，新文字改 `測試局`，預覽、套用 | 選取為 `衛生局`；套用後頁面目標變為 `測試局`（頁面可能空白，可改由 W17 另存後以其他閱讀器確認） | |

## 4. 繁中輸入法（G4-02，U3、U7）

在 `公文 草稿.pdf` 選取「World」後，於「新文字」欄操作。每種輸入法各做一次（至少微軟注音；有倉頡／速成者一併）。

| # | 步驟 | 預期 | 結果（注音） | 結果（其他） |
| --- | --- | --- | --- | --- |
| W16a | 清空新文字欄，用輸入法打「測試」，**組字中（字下有底線、尚未確認）不要按任何鍵**，觀察 3 秒 | 不會自動預覽；修改前／修改後圖不變 | | |
| W16b | 組字中按 **Enter** | Enter 只確認組字（字變為一般文字），**不觸發預覽**；若有觸發，記下預覽使用的文字是否為完整確認後的「測試」 | | |
| W16c | 確認後再按一次 Enter | 以「測試」預覽一次 | | |
| W16d | 組字中直接按「預覽」按鈕 | 不以未確認的字預覽（不預覽，或只以已確認部分預覽——記下實際行為） | | |
| W16e | 組字中按 Esc | 只取消組字，不會取消其他操作、不報錯 | | |
| W16f | 打一個字後用選字視窗選同音字（例如「試→是」） | 選字視窗位置在輸入欄附近；選的字正確進入欄位 | | |

## 5. 另存與路徑（G4-01、G4-03）

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W17 | 在 `公文 草稿.pdf` 套用 `Hello Earth` 後按 **Ctrl+Shift+S** | 出現原生「另存新檔」對話框 | |
| W18 | 存到 `P4驗收\表情😀\輸出 結果😀.pdf` | 狀態列「已另存」；用 Edge 開該檔看到 `Hello Earth`；原檔 `公文 草稿.pdf` 仍是 `Hello World` | |
| W19 | 在 PEditor 開啟 W18 的輸出檔 | 頁面為 `Hello Earth` | |
| W20 | 再另存一次到同一個 `輸出 結果😀.pdf` | 原生對話框詢問是否取代；選「是」後成功，檔案可正常開啟 | |
| W21 | 另存時選擇原檔 `公文 草稿.pdf` 本身 | 拒絕（不可覆寫原檔），原檔內容不變 | |
| W22 | 另存完成後檢查 `P4驗收\表情😀\` | 沒有殘留 `.~peditor-*.tmp.pdf`（需在檔案總管開啟「顯示隱藏的項目」） | |

## 6. 快捷鍵與回應（G4-06）

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W23 | 按 **Ctrl+O** | 開啟檔案對話框 | |
| W24 | 將滑鼠停在工具列各按鈕上 | 提示中的快捷鍵顯示為 `Ctrl+…`（記下實際內容） | |
| W25 | 在 F02 做模式 B 預覽（W13）時拖動視窗、捲動縮圖 | 視窗不凍結、不出現「沒有回應」 | |
| W26 | 在 F02 按「套用」後立刻按 **Esc**（取消） | 若來得及取消：顯示已取消、頁面不變、「復原」不可按。若操作太快無法取消，標 NOT RUN（CI 的 G4-04 以 worker 延遲模擬） | |

## 7. 復原草稿（G4-01）

| # | 步驟 | 預期 | 結果 |
| --- | --- | --- | --- |
| W27 | 開啟 `P4驗收\F04.pdf`，套用 `Hello Earth`（不要另存）。另開 PowerShell 強制結束：`Get-Process \| Where-Object MainWindowTitle -like 'PEditor *' \| Stop-Process -Force` | PEditor 關閉 | |
| W28 | 重新 `uv run peditor` | 出現「復原草稿」對話框，列出 `F04.pdf　1 項編輯　<時間>`，不顯示完整路徑 | |
| W29 | 選該草稿，按「復原」 | 開啟 `F04.pdf`，頁面為 `Hello Earth`；「復原」可按 | |
| W30 | 重複 W27 兩次（先 `公文 草稿.pdf`，再 `F04.pdf`），重新啟動 | 對話框列出兩份；選一份按「捨棄」後，對話框再出現並只剩另一份；按「稍後再說」關閉 | |
| W31 | 正常關閉 PEditor（按視窗 ✕），再啟動 | 「稍後再說」的那份仍會列出；正常關閉的文件不再列出 | |

## 8. 收尾

```powershell
Remove-Item -Recurse -Force (Join-Path $env:USERPROFILE "Desktop\P4驗收")
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
| G4-01 E2E 流程 | W02、W07–W13、W15、W17–W20、W27–W31 | `tests/gui/test_e2e.py` |
| G4-02 IME | W16a–W16f | `tests/gui/test_ime.py` |
| G4-03 中文／空白／emoji 路徑 | W02、W03、W17–W20 | `tests/gui/test_paths.py` |
| G4-04 取消不提交 | W26 | `test_e2e.py::test_cancel_does_not_commit` |
| G4-05 不可編輯原因 | W05、W06、W14 | `test_e2e.py::test_reason_shown_for_uneditable` |
| G4-06 快捷鍵、不阻塞 | W10、W11、W17、W23–W25 | `tests/gui/test_shortcuts.py`、`test_responsiveness.py` |
| G4-07 中文字型 | W01、W03 | `tests/gui/test_fonts.py`（只驗預覽圖） |
| G4-09 草稿、暫存檔 | W22、W27–W31 | `tests/gui/test_drafts_ui.py`、`test_startup.py` |
