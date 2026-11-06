# ADR-0025：P8 發布打包（PyInstaller onedir、Inno Setup、DMG、macOS 最低版本、未簽署）

- 狀態：已接受（2026-11-06，工程師於 P8 S1／S2 決定「照建議」；同日防毒誤判的處理方向「照建議」）
- 日期：2026-11-06
- 決策者：工程師
- 需人工確認：否（已確認）；授權核對（ADR-0002）、程式碼簽章與 notarization 另行決定

## 背景

spec P8：Windows 原生建置安裝包；macOS Apple Silicon 原生建置 app／DMG；全部依賴、字型、資源本地包裝；標明 macOS 最低
支援版本。G8：乾淨 VM／實機無 Python、無網路可安裝並完成核心流程；兩種 PDF 閱讀器正常開啟；已知缺陷清單、SBOM、LICENSE、
相依來源與版本、卸載／草稿清理說明。正式散布的簽章與 notarization 另行核價，未簽署測試包不得標成正式部署完成。
P0 的 smoke build（PyInstaller onedir、主控台）證明相依可凍結；打包後的 worker 子命令（ADR-0004）、模式 B 字型
（ADR-0008、ADR-0018 §4）與 Job Object（ADR-0024）在打包結果中尚未驗證。

## 決策

### 1. 建置（`packaging/build_release.py`）

- PyInstaller onedir、視窗程式（`--windowed`），名稱 PEditor；macOS 產生 `PEditor.app`（bundle id
  `io.github.tghapplication.peditor`）。各平台原生建置，不跨平台產出。
- 模式 B 字型 `NotoSansTC-Regular.otf` 與其 OFL 授權（`LICENSE-NotoSansCJK.txt`）放進 `peditor/resources/fonts/`
  （`fontb.py` 的套件內位置，仍驗證 ADR-0008 的 SHA-256）；`LICENSE`、`THIRD_PARTY_NOTICES.md` 放在程式資料夾。
- **打包結果自我檢查**（不用開發環境的 Python）：`--smoke` 啟動主視窗；`edit-text` 以 T01（模式 A）與 F02（模式 B，
  只能用打包進去的字型）改字並另存。兩者都經由打包後的 worker 子命令；Windows 上 worker 在 Job Object 內以 1 個行程
  執行（ADR-0024 §1；打包後沒有 venv 轉介程式）。任何一項失敗即建置失敗。
- 輸出 `build/release/SHA256SUMS.txt`（安裝包與程式資料夾每個檔案）與 `release.json`。

### 2. 安裝包

- **Windows**：Inno Setup 6（CI 以 Chocolatey 鎖定 6.7.1；6.4.3 在 Chocolatey 上不存在）。每位使用者安裝
  （`PrivilegesRequired=lowest`，裝在 `%LOCALAPPDATA%\Programs\PEditor`，不需系統管理權限）、開始功能表捷徑、解除安裝。
  解除安裝只移除程式檔；使用者的復原草稿與暫存檔紀錄（`%LOCALAPPDATA%\PEditor`）保留，清理方式寫在發布文件。
  Inno Setup 只在建置期使用，不進產品執行期。
- **macOS**：`hdiutil create -format UDZO` 產生 DMG（系統內建，不新增工具）。
- CI 的 `release` job 在兩平台建置、自我檢查並上傳安裝包（保留 30 天）；產物**未簽署**，只供測試。

### 3. macOS 最低支援版本：15.0（Sequoia），Apple Silicon

由 `uv.lock` 鎖定的 arm64 wheel 決定：pikepdf 10.14.0 只有 `macosx_15_0_arm64`（cp313、cp314 abi3）；其餘
PySide6 6.11.2 為 13.0、PyMuPDF 1.28.2 與 Pillow 為 11.0。CI 在 macos-15 建置。Intel Mac 不支援（spec P8）。
降低最低版本需改用較舊的 pikepdf（相依變更，另立 ADR）。

### 4. 防毒誤判與簽章

- 2026-11-06 工程師的 Windows 製作機上，防毒軟體移除了本機建置的 `PEditor.exe`（未簽署的 PyInstaller 視窗程式）；
  偵測名稱待工程師確認。PyInstaller 預編譯的 bootloader 常被啟發式規則誤判。
- 處理（工程師「照建議」）：
  - A：CI 的 Windows release 改用原始碼編譯同一版 PyInstaller（6.22.3）的 bootloader（`PYINSTALLER_COMPILE_BOOTLOADER=1`，
    相依版本不變），降低誤判機率；效果需在實機下載產物後確認，不保證。
  - B：程式碼簽章（Windows Authenticode、macOS Developer ID＋notarization）列為正式散布的前提，另行核價（spec P8）。
  - C：向防毒廠商回報誤判，並由資訊單位以安裝包 SHA-256 加入白名單（內部 POC）。
- 未簽署的安裝包在端點防護下可能無法安裝或執行；THREAT_MODEL §6「機關端是否有端點防護會阻擋未簽章執行檔」已有實例。

## 後果

- 安裝包約 160–180 MB（onedir 未瘦身）。
- macOS 15 以前的版本無法執行；macOS 實機驗收 NOT RUN（ADR-0003）。
- 未簽署：Windows SmartScreen 會警告、macOS Gatekeeper 需使用者手動允許；不得標成正式部署。
- 原始碼編譯 bootloader 只在 CI 的 Windows release 進行；本機建置仍使用預編譯 bootloader。
