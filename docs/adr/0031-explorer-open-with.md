# ADR-0031：檔案總管右鍵「用 PEditor 開啟」

- 狀態：已接受（2026-11-24，工程師要求「安裝時加入機碼，點選 PDF 檔右鍵可以看到用 PEditor 開啟的選項」）
- 日期：2026-11-24
- 決策者：工程師

## 背景

目前只能先開 PEditor 再選檔。工程師希望在檔案總管直接對 PDF 按右鍵開啟。安裝程式為個人安裝（`PrivilegesRequired=lowest`，ADR-0025），
不能寫 HKLM；Windows 11 的新版右鍵選單只直接列出「開啟方式」與 IExplorerCommand 擴充，傳統動詞放在「顯示更多選項」裡。

## 決策

1. **命令列參數**：`PEditor.exe <檔案.pdf>` 啟動後開啟該檔，流程與「開啟…」相同（一律經 worker 檢查，ADR-0004）。
   以檔案啟動時不詢問復原草稿（留到下次一般啟動再列出），避免復原對話框蓋過使用者要開的檔。每次右鍵開一個新視窗（ADR-0030）。
2. **安裝程式機碼（全部在 HKCU，卸載時移除）**：
   - `Software\Classes\SystemFileAssociations\.pdf\shell\PEditor`：右鍵「用 PEditor 開啟」（Windows 10 直接顯示；Windows 11 在「顯示更多選項」）。
   - `Software\Classes\PEditor.pdf` 加 `.pdf\OpenWithProgids` 的值：出現在「開啟方式」清單（Windows 11 新版右鍵選單第一層即可看到）。
   - 指令一律為 `"{app}\PEditor.exe" "%1"`（兩者都加引號，含空白的路徑不會被拆開）。
3. **不改預設 PDF 程式**：不寫 `.pdf` 的預設值、不碰 `UserChoice`；使用者要設為預設時自行在 Windows 設定選擇。
4. 不做 IExplorerCommand（需 COM DLL 與套件身分／簽章，維運成本高）。
5. `peditor.iss` 改為 UTF-8（只有選單文字是中文；CI 鎖定 Inno Setup 6.7.1，6.3 起可讀無 BOM 的 UTF-8）。

## 後果

- Windows 11 的第一層選單看到的是「開啟方式 → PEditor」，不是獨立的「用 PEditor 開啟」；後者在「顯示更多選項」。
- 命令列參數是不可信輸入：只當作一般檔案路徑交給既有的開檔流程，錯誤訊息不含路徑（spec §9）。
- macOS 不在本 ADR 範圍（.app 的「打開檔案」事件需另行處理）。
- 測試：`tests/gui/test_shell_open.py`（參數傳遞、啟動開檔、不問草稿、錯誤不含路徑、安裝程式機碼靜態檢查）。
