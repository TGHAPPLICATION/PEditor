# ADR-0004：架構與 IPC — UI 主行程 + PDF worker 子行程

- 狀態：提議（P1 實作時定案細節）
- 日期：2026-10-12
- 需人工確認：是（審查 P1 前）

## 背景

PDF 為不可信輸入；MuPDF、qpdf 為 C/C++ 程式庫，歷年有記憶體安全 CVE。若解析與 UI 同行程，
惡意 PDF 造成的崩潰或程式碼執行會直接影響 UI 與未儲存的工作。單人維運，架構須簡單。

## 選項

1. 單行程：最簡單；崩潰即失去工作，無隔離。
2. **UI 主行程 + 單一 worker 子行程（stdin/stdout JSON Lines）**：標準函式庫即可，跨平台一致。
3. 本機 socket／HTTP 服務：引入網路堆疊，違反離線原則且增加攻擊面。

## 決策

採選項 2：

- **主行程**（PySide6 UI）不 import PyMuPDF／pikepdf 處理使用者檔案；只顯示 worker 回傳的資料
  （頁面點陣圖、文字框、capability report）。
- **worker**：`python -m peditor.worker`（打包後為同一執行檔的子命令），以 `subprocess` 啟動，
  stdin/stdout 傳 JSON Lines，每則訊息有長度上限與逾時；stderr 只寫不含原文的診斷碼。
- worker 崩潰或逾時 → 主行程終止並重啟 worker，回報「檔案無法處理」，不影響其他已開啟檔案。
- 資源限制（記憶體、CPU 時間、頁數、物件數）於 P7 加上；P1 先預留設定點。
- 儲存：worker 寫入暫存檔 → 主行程驗證 → 原子取代（P3 儲存交易）。
- 不使用任何網路 IPC（含 localhost）。

## 後果

- IPC schema 於 P1 定義並以測試鎖定；每個訊息型別需有 fuzz／畸形輸入測試（P7）。
- PyInstaller 打包需確保 worker 子命令可被啟動（P8 驗證）。
