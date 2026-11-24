# LUMICAT 安裝、解除安裝與草稿清理（P8 發布候選）

> 本版是**未簽署的測試包**，只供內部 POC，不是正式部署（spec P8、ADR-0025）。

## 系統需求

| 平台 | 需求 |
| --- | --- |
| Windows | Windows 10／11 x64。不需要 Python、不需要網路。 |
| macOS | macOS 15.0（Sequoia）以上、Apple Silicon（ADR-0025 §3）。不支援 Intel Mac。不需要 Python、不需要網路。 |

## 取得與核對

安裝包由 CI 的 `release` job 建置（GitHub Actions artifact `lumicat-Windows`、`lumicat-macOS`），
附 `SHA256SUMS.txt` 與 `release.json`。安裝前請比對 SHA-256：

```powershell
Get-FileHash -Algorithm SHA256 LUMICAT-<版本>-windows-x64-setup.exe
```

```bash
shasum -a 256 LUMICAT-<版本>-macos-arm64.dmg
```

## 授權與原始碼

LUMICAT 依 AGPL-3.0-only 散布（`LICENSE`、`NOTICE`），不提供任何擔保。

- **對應原始碼**：https://github.com/TGHAPPLICATION/LUMICAT 。每個安裝包由視窗標題括號內的 commit 建置，
  該版原始碼在 `https://github.com/TGHAPPLICATION/LUMICAT/tree/<commit>`；程式內「說明 → 關於 LUMICAT」也會顯示。
- **散布**：以 GitHub Releases 為主，原始碼與安裝包在同一處。若另行轉載安裝包（例如機關內部網站），
  轉載處須附上述原始碼連結（AGPL-3.0 §6）。
- **第三方授權**：安裝目錄的 `THIRD_PARTY_NOTICES.md` 與 `licenses/` 資料夾。

## Windows

1. 執行 `LUMICAT-<版本>-windows-x64-setup.exe`。安裝在 `%LOCALAPPDATA%\Programs\LUMICAT`，不需系統管理權限。
2. 未簽署：SmartScreen 會顯示「Windows 已保護您的電腦」，需按「其他資訊 → 仍要執行」。
3. 端點防護（防毒）可能把未簽署的執行檔判為可疑而隔離（2026-11-06 已發生，ADR-0025 §4）。請不要自行停用防毒；
   由資訊單位以 `SHA256SUMS.txt` 的雜湊確認後加入白名單，或等正式簽章版。
4. 從開始功能表開啟「LUMICAT」。

**右鍵開啟**（ADR-0031）：安裝後對 PDF 按右鍵，Windows 11 可在「開啟方式 → LUMICAT」或「顯示更多選項 → 用 LUMICAT 開啟」；Windows 10 直接顯示「用 LUMICAT 開啟」。安裝程式不會自行把 LUMICAT 設為預設 PDF 程式；要設為預設，可在安裝完成頁勾選「設定 LUMICAT 為 PDF 預設程式」，它會開啟 Windows 設定的 LUMICAT 頁面，在「.pdf」選 LUMICAT 即可（之後也可從 設定 → 應用程式 → 預設應用程式 → LUMICAT 設定）。

**從 PEditor 測試版改裝**（ADR-0034）：LUMICAT 是新的安裝識別，不會覆蓋舊的 PEditor；請先在「已安裝的應用程式」解除安裝 PEditor，再安裝 LUMICAT。舊的草稿與暫存紀錄資料夾（`PEditor`）會在第一次啟動 LUMICAT 時自動改名為 `LUMICAT` 沿用。

**解除安裝**：設定 → 應用程式 → 已安裝的應用程式 → LUMICAT → 解除安裝。移除程式檔與右鍵選單機碼，下列使用者資料保留。

## macOS

1. 開啟 `LUMICAT-<版本>-macos-arm64.dmg`，把 LUMICAT 拖到「應用程式」。
2. 未簽署、未 notarize：第一次開啟時 Gatekeeper 會阻擋。請在「系統設定 → 隱私權與安全性」按「強制打開」。
3. **解除安裝**：把「應用程式」中的 LUMICAT 移到垃圾桶。使用者資料同樣保留。

## 使用者資料與草稿清理

LUMICAT 不寫日誌檔（ADR-0024 §4）。會留在電腦上的只有：

| 資料 | Windows | macOS | 內容與保留 |
| --- | --- | --- | --- |
| 復原草稿 | `%LOCALAPPDATA%\LUMICAT\drafts\` | `~/Library/Application Support/LUMICAT/drafts/` | 未另存就關閉時的編輯紀錄（含原檔路徑與新文字，權限 0600）；7 天後自動刪除；正常關閉文件時刪除（ADR-0020 §5） |
| 暫存檔紀錄 | `%LOCALAPPDATA%\LUMICAT\pending-temps.json`（及 `.lock`） | `~/Library/Application Support/LUMICAT/pending-temps.json` | 另存中斷時留下的暫存檔路徑；下次啟動時刪除超過 10 分鐘的暫存檔（ADR-0024 §7） |
| 另存暫存檔 | 與目的檔同資料夾的 `.~lumicat-*.tmp.pdf` | 同左 | 只在另存中斷時殘留；下次啟動或下次另存到同資料夾時清除 |

**完全清除**（解除安裝後）：關閉 LUMICAT，刪除整個 `LUMICAT` 資料夾（Windows：`%LOCALAPPDATA%\LUMICAT`；
macOS：`~/Library/Application Support/LUMICAT`）。若曾在另存途中強制結束，另檢查目的資料夾是否有 `.~lumicat-*.tmp.pdf`。

## 離線

LUMICAT 不連網：不自動更新、不下載字型或外部內容、不送 telemetry（spec P7、ADR-0024）。所有字型與相依都在安裝包內。
