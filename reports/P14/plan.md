# P14 作業系統內建 OCR — S1／S2（待工程師確認後實作）

依 CLAUDE.md：S1 確認輸入、S2 拆解任務；工程師確認後才進入 S3（分支 `p14-os-ocr`，從 `p13-lumicat` 分出）。

## 目標

在「文字擷取」中，沒有文字層的頁（掃描圖片）可以用作業系統內建 OCR 辨識出繁體中文，結果可選取、複製、另存。只讀，不改 PDF。

## 背景

- 工程師 2026-11-25 決定先試作業系統內建 OCR：PP-OCR 為百度產品，受資安署「大陸廠牌資通訊產品」盤點原則影響（從嚴認定、含軟體與套件）；
  OS 內建 OCR 來源無疑慮、不增加模型檔。
- Windows：`Windows.Media.Ocr`（Windows 10 起內建；需「中文（台灣）」的 OCR 選用功能）。Python 端用 PyWinRT（`winrt-Windows.Media.Ocr` 等，MIT）。
- macOS：Vision `VNRecognizeTextRequest`（`.accurate`、`zh-Hant`）。Python 端用 PyObjC（`pyobjc-framework-Vision`，MIT）。
- 已知限制：Vision 對**直書中文**幾乎辨識不出來（Apple 開發者論壇）；Windows OCR 直書能力未知，需實測。
- 新增相依須 ADR（CLAUDE.md），版本受 `exclude-newer = 2026-09-28` 限制。

## 步驟

| 需求 ID | 內容 | 測試 ID | 修改檔案 |
| --- | --- | --- | --- |
| P14-01 | ADR-0035：選用 OS 內建 OCR、新增相依（依平台標記）、授權、威脅模型 | 文件審查 | `docs/adr/0035-os-ocr.md`、`THREAT_MODEL.md`（T18）、`licenses/` |
| P14-02 | worker 操作 `ocr_page`：在 worker 以 MuPDF 把該頁畫成點陣（約 300 dpi，長邊上限依 OS 限制縮小），交給 OS OCR，回傳逐行文字；逾時、記憶體上限；不支援或缺語言時回傳明確代碼 | `tests/integration/test_ocr_page.py`（Windows／macOS 在 CI 實跑；Linux 驗證參數與「不支援」路徑） | `src/lumicat/worker/ocr.py`（新）、`worker/server.py`、`core/protocol.py`、`core/service.py`、`core/limits.py` |
| P14-03 | 「文字擷取」：沒有文字的頁顯示「辨識圖片文字」；辨識結果標「（OCR 辨識，可能有錯字）」；缺 OCR 語言時說明安裝方式 | `tests/gui/test_text_extract.py`（新增） | `src/lumicat/ui/text_extract.py`、`ui/app.py` |
| P14-04 | 準確度量測：以既有繁中 fixture 轉成純圖片頁，比對 OCR 結果的字元正確率；CI 的 Windows 先安裝 zh-TW OCR 選用功能 | `tests/integration/test_ocr_accuracy.py`（CI 才跑）、`scripts/ocr_benchmark.py` | `.github/workflows/ci.yml` |
| P14-05 | 打包：PyInstaller 帶入 PyWinRT／PyObjC；安裝包大小變化記錄 | CI release 的自我檢查 | `packaging/build_release.py`（如需） |
| P14-06 | 實機：Windows 沙箱辨識合成掃描頁，並用工程師提供的去識別化掃描檔量測 | 驗收清單 P14a～ | — |

S4 自我檢查同既有流程；S5 產出 `reports/P14/report.md`，標明哪些只有 CI 證據。

## 輸出格式

程式與測試（分支 `p14-os-ocr` → PR）、ADR-0035、OCR 準確度量測表（Windows／macOS 各自的字元正確率與每頁秒數）、`reports/P14/report.md`、驗收清單新增項目。

## 驗收標準

- CI 雙平台通過；Windows 與 macOS 在 CI 上對合成掃描頁的繁中字元正確率有數據（門檻待量測後由工程師訂）。
- Windows 實機：沙箱能辨識；缺語言時有清楚說明；結果可複製、另存。
- 產品程式仍不匯入網路模組；PDF 仍只在 worker 開啟；OCR 結果與錯誤訊息不寫日誌、不含路徑。

## 須請人類確認

1. 觸發方式：按鈕手動辨識，或擷取時自動辨識沒有文字的頁。
2. 範圍只做「文字擷取」（只讀）；不做可搜尋 PDF（另議）。
3. 缺 OCR 語言時只顯示安裝說明（需系統管理員權限，不自動安裝）。
4. macOS 是否一併做（CI 可測，實機仍 NOT RUN）。
5. 能否提供 5～10 頁去識別化掃描檔做實機量測。
