# ADR-0035：作業系統內建 OCR（文字擷取的掃描頁辨識）

- 狀態：已接受（2026-11-25，工程師確認 P14 計畫：按鈕手動辨識、Windows 與 macOS 都做、缺語言只顯示說明、以合成掃描圖量測）
- 日期：2026-11-25
- 決策者：工程師

## 背景

同仁需要從掃描檔（沒有文字層）取得文字。評估開源模型後，PP-OCR（百度）準度最好，但受資安署「大陸廠牌資通訊產品」盤點原則影響
（從嚴認定、範圍含軟體與套件；開源未明文排除）。工程師決定先用作業系統內建 OCR：來源無疑慮、不需隨附模型檔。

## 決策

1. **引擎**：Windows 用 `Windows.Media.Ocr`（Windows 10 起內建，需「中文（台灣）」OCR 選用功能）；macOS 用 Vision
   `VNRecognizeTextRequest`（`.accurate`、`zh-Hant`＋`en-US`；需 macOS 13 以上的語言查詢介面）。其他平台不提供。
2. **新增相依**（依平台標記，只在該平台安裝與打包；版本受 `exclude-newer` 限制）：PyWinRT 3.2.1（`winrt-runtime`、
   `winrt-Windows.Foundation`、`.Foundation.Collections`、`.Globalization`、`.Graphics.Imaging`、`.Media.Ocr`、`.Storage.Streams`，MIT）；
   PyObjC 12.2.2（`pyobjc-framework-Vision` 及其相依 core、Cocoa、Quartz、CoreML，MIT）。uv.lock 只新增，既有版本不變。
3. **在 worker 執行**：新操作 `ocr_page`（參數 `page_index`；回傳 `{"text", "lines"}`）。頁面在 worker 以 MuPDF 畫成灰階點陣
   （長邊 ≤3,500 px、≤300 dpi；與 render_page 相同的超限頁檢查），只把點陣交給系統 OCR；受 worker 的記憶體上限與 30 秒逾時約束。
   Windows 中文以單字為「詞」，合併時中文之間不加空白；macOS 依框的位置由上而下、由左而右排列。
4. **錯誤碼**：`OCR_UNAVAILABLE`（系統沒有可用的辨識）、`OCR_LANGUAGE_MISSING`（未安裝繁中辨識；畫面顯示安裝路徑，需系統管理員權限，不自動安裝）。
5. **介面**：「文字擷取」中沒有文字、未超限的頁才出現「辨識圖片文字」，按下才辨識（手動）；結果頁加註「以下為 OCR 辨識結果，可能有錯字，請核對」，
   移除頁碼時註記一併移除。只讀，不改 PDF、不產生可搜尋 PDF。
6. **驗證**：CI 的 Windows 先安裝 zh-TW OCR 選用功能，CI 設 `LUMICAT_REQUIRE_OCR=1`（缺語言即失敗，不略過）；以繁中 fixture 畫成 200 dpi 純圖片頁量測字元正確率
   （`scripts/ocr_benchmark.py`，結果寫入 CI 摘要）。T05 門檻暫訂 80%，實測後由工程師調整。發布自我檢查以打包結果執行 `ocr-probe`，確認元件有打包。

## 後果

- 已知限制：Vision 對直書中文幾乎辨識不出（Apple 開發者論壇）；Windows 直書能力待實測。準確度依系統版本而異。
- 辨識結果與錯誤不寫日誌；`ocr-probe` 只輸出狀態與字數。
- 安裝包增加 PyWinRT／PyObjC 的二進位檔（大小記錄於 P14 報告）。
- 測試：`tests/unit/test_ocr_helpers.py`、`tests/integration/test_ocr_page.py`、`tests/gui/test_text_extract.py`、`tests/unit/test_protocol_codes.py`。
