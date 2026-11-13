# PEditor 安裝、解除安裝與草稿清理（P8 發布候選）

> 本版是**未簽署的測試包**，只供內部 POC，不是正式部署（spec P8、ADR-0025）。

## 系統需求

| 平台 | 需求 |
| --- | --- |
| Windows | Windows 10／11 x64。不需要 Python、不需要網路。 |
| macOS | macOS 15.0（Sequoia）以上、Apple Silicon（ADR-0025 §3）。不支援 Intel Mac。不需要 Python、不需要網路。 |

## 取得與核對

安裝包由 CI 的 `release` job 建置（GitHub Actions artifact `peditor-Windows`、`peditor-macOS`），
附 `SHA256SUMS.txt` 與 `release.json`。安裝前請比對 SHA-256：

```powershell
Get-FileHash -Algorithm SHA256 PEditor-<版本>-windows-x64-setup.exe
```

```bash
shasum -a 256 PEditor-<版本>-macos-arm64.dmg
```

## 授權與原始碼

PEditor 依 AGPL-3.0-only 散布（`LICENSE`、`NOTICE`），不提供任何擔保。

- **對應原始碼**：https://github.com/TGHAPPLICATION/PEditor 。每個安裝包由視窗標題括號內的 commit 建置，
  該版原始碼在 `https://github.com/TGHAPPLICATION/PEditor/tree/<commit>`；程式內「說明 → 關於 PEditor」也會顯示。
- **散布**：以 GitHub Releases 為主，原始碼與安裝包在同一處。若另行轉載安裝包（例如機關內部網站），
  轉載處須附上述原始碼連結（AGPL-3.0 §6）。
- **第三方授權**：安裝目錄的 `THIRD_PARTY_NOTICES.md` 與 `licenses/` 資料夾。

## Windows

1. 執行 `PEditor-<版本>-windows-x64-setup.exe`。安裝在 `%LOCALAPPDATA%\Programs\PEditor`，不需系統管理權限。
2. 未簽署：SmartScreen 會顯示「Windows 已保護您的電腦」，需按「其他資訊 → 仍要執行」。
3. 端點防護（防毒）可能把未簽署的執行檔判為可疑而隔離（2026-11-06 已發生，ADR-0025 §4）。請不要自行停用防毒；
   由資訊單位以 `SHA256SUMS.txt` 的雜湊確認後加入白名單，或等正式簽章版。
4. 從開始功能表開啟「PEditor」。

**解除安裝**：設定 → 應用程式 → 已安裝的應用程式 → PEditor → 解除安裝。只移除程式檔，下列使用者資料保留。

## macOS

1. 開啟 `PEditor-<版本>-macos-arm64.dmg`，把 PEditor 拖到「應用程式」。
2. 未簽署、未 notarize：第一次開啟時 Gatekeeper 會阻擋。請在「系統設定 → 隱私權與安全性」按「強制打開」。
3. **解除安裝**：把「應用程式」中的 PEditor 移到垃圾桶。使用者資料同樣保留。

## 使用者資料與草稿清理

PEditor 不寫日誌檔（ADR-0024 §4）。會留在電腦上的只有：

| 資料 | Windows | macOS | 內容與保留 |
| --- | --- | --- | --- |
| 復原草稿 | `%LOCALAPPDATA%\PEditor\drafts\` | `~/Library/Application Support/PEditor/drafts/` | 未另存就關閉時的編輯紀錄（含原檔路徑與新文字，權限 0600）；7 天後自動刪除；正常關閉文件時刪除（ADR-0020 §5） |
| 暫存檔紀錄 | `%LOCALAPPDATA%\PEditor\pending-temps.json`（及 `.lock`） | `~/Library/Application Support/PEditor/pending-temps.json` | 另存中斷時留下的暫存檔路徑；下次啟動時刪除超過 10 分鐘的暫存檔（ADR-0024 §7） |
| 另存暫存檔 | 與目的檔同資料夾的 `.~peditor-*.tmp.pdf` | 同左 | 只在另存中斷時殘留；下次啟動或下次另存到同資料夾時清除 |

**完全清除**（解除安裝後）：關閉 PEditor，刪除整個 `PEditor` 資料夾（Windows：`%LOCALAPPDATA%\PEditor`；
macOS：`~/Library/Application Support/PEditor`）。若曾在另存途中強制結束，另檢查目的資料夾是否有 `.~peditor-*.tmp.pdf`。

## 離線

PEditor 不連網：不自動更新、不下載字型或外部內容、不送 telemetry（spec P7、ADR-0024）。所有字型與相依都在安裝包內。
