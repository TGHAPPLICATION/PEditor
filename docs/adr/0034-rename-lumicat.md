# ADR-0034：專案改名 LUMICAT 與品牌圖示、配色

- 狀態：已接受（2026-11-24，工程師要求「更換專案名稱，一併更換 ICON」，附 LUMICAT Brand Kit v1.0；選擇「全部改名」、畫面寫法「LUMICAT」、
  介面改品牌藍、圖示「保留商標、改版須換圖示」）
- 日期：2026-11-24
- 決策者：工程師

## 決策

1. **全部改名**：Python 套件 `peditor` → `lumicat`（`src/lumicat`）、命令列 `lumicat`、環境變數 `PEDITOR_*` → `LUMICAT_*`、
   執行檔 `LUMICAT.exe`／`LUMICAT.app`、視窗標題、關於、安裝程式、右鍵選單「用 LUMICAT 開啟」、機碼（`LUMICAT.pdf`、`Software\LUMICAT`）、
   使用者資料夾 `LUMICAT`、CI 產物名稱、文件。GitHub repo 改名為 `TGHAPPLICATION/LUMICAT`（GitHub 會把舊網址轉址）。
2. **不改的**：`reports/`、`docs/adr/` 的歷史紀錄；fixture 與產生器（`tests/fixtures/`、`scripts/gen_fixtures.py` 內的「PEditor fixture generator」、
   `peditor-sentinel` 等字樣是測試資料內容，改了會改變 fixture hash）。
3. **舊資料沿用**：第一次啟動時，舊資料夾 `PEditor`（草稿、暫存紀錄）在新資料夾不存在時改名為 `LUMICAT`；改名失敗（例如舊版仍在執行）就繼續用舊資料夾。
   暫存檔清除同時接受舊名稱 `.~peditor-*.tmp.pdf`。
4. **安裝程式**：新的 AppId（不覆蓋 PEditor 測試版；先解除安裝舊版）；安裝程式與解除安裝顯示 LUMICAT 圖示。
5. **圖示**：`src/lumicat/resources/icons/lumicat-{16…256}.png`（視窗、工作列，打包進 `resources/icons`）、`packaging/icons/lumicat.ico`（Windows 執行檔與安裝程式）、
   `lumicat.icns`（macOS .app）。品牌指南與色票放在 `docs/brand/`。
6. **配色**：主色深海藍 `#00529B`（白字對比 7.8:1）、背景純淨白 `#F4FAFF`；光耀藍 `#079CE3` 對白底只有 3.1:1，不當文字色。WCAG 4.5:1 檢查照跑。
7. **授權**：程式碼 AGPL-3.0 不變；名稱與圖示不在 AGPL 範圍，由專案保留，修改版須換名稱與圖示（`docs/brand/TRADEMARK.md`、`NOTICE`）。

## 後果

- 品牌包說明圖示由 AI 生成、非向量原稿，名稱尚未做商標檢索：正式發布前須確認（`docs/brand/TRADEMARK.md`）。
- 16／32 px 圖示是原圖縮製，小尺寸辨識度需實機看。
- uv.lock 只有專案名稱改變（相依版本不變，已比對）。
- 測試：`tests/gui/test_brand.py`；其餘測試隨改名更新。
