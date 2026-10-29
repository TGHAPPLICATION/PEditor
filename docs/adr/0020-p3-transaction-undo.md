# ADR-0020：P3 儲存交易、撤銷與復原草稿

- 狀態：已接受（2026-10-28，工程師於 P3 S2 選定 undo 機制、覆寫範圍、草稿保留期與 U4 範圍）
- 日期：2026-10-28
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

spec P3 要求原檔唯讀、每次操作基於版本、至少 50 次 undo/redo、預設另存、完整重寫；儲存為
「同目錄臨時檔 → flush → 結構／文字／視覺驗證 → 原子 rename」，並檢查目的檔變動與來源 hash；
復原草稿由使用者選擇開啟，含敏感內容的暫存不可無限制保留。ADR-0004 已定「worker 寫入暫存檔 →
主行程驗證 → 原子取代」與 `destination_token`。P2 留下 f003（套用失敗無回滾）、f017（部分輸出）、
f010（worker 收原始路徑）、R3-1（復原後 target_id 改變）。

## 決策

### 1. undo／redo：command log 重播

- command log 存在主行程（`DocumentService`），每筆為 `plan_text_edit` 的參數（target_id、new_text、policy、
  editable_region）與規劃時的 `base_revision`；不存文件位元組。
- 撤銷：worker 由開檔時的原始位元組重播 log 前 n−1 筆。重做：在目前狀態上重播第 n 筆。
- 重播每筆時，worker 先把文件 revision 設回該筆的 `base_revision`（target_id 含 revision），重新規劃並套用；
  任一筆失敗即整次重播復原到重播前狀態。規劃不是 ready 時回 `VALIDATION_FAILED`；規劃或套用本身拋出的錯誤以原錯誤碼回傳。
- revision 單調遞增：apply、undo、redo 都回 `目前 revision + 1`，不會回到舊數字。
- 新的 apply 會截斷尚未重做的部分（標準 undo 堆疊）。log 不設上限，spec 要求至少 50 次。
- worker 重啟後，主行程以 SHA-256 確認原檔未變，再重播 log 到目前位置並沿用目前 revision；
  呼叫端手上的 revision 仍然有效（P2 時重啟會失去已套用的編輯）。
- 代價：撤銷要從頭重播，耗時與步數成正比（實測 T01 模式 A 每步約 22 ms、F02 模式 B 約 166 ms）。

### 2. 套用失敗回滾（f003、R3-1）

worker 文件保存「目前狀態的來源位元組」。`apply_edit` 任一步失敗（含 /ActualText 儲存後驗證），
以這份位元組重新開啟並還原 revision；物件編號與失敗前相同，target_id 不變（取代 P2 以重寫結果復原的做法）。

### 3. 儲存交易

1. 呼叫端以 `destination_token(path, overwrite)` 取得 token：主行程解析實際路徑（`realpath`，含符號連結），
   須為 .pdf、上層目錄存在；記錄目的檔當時的狀態（不存在，或大小、修改時間、SHA-256）。
   目的檔已存在而 `overwrite` 為否時回 `SAVE_FAILED`。
2. `export_document(document_id, destination_token, expected_revision)`：
   - 目的檔是任何已開啟文件的原檔時拒絕（`INVALID_REQUEST`，原檔唯讀）。
   - 原檔 SHA-256 與開啟時不同、目的檔狀態與取得 token 時不同：`REVISION_CONFLICT`。
   - 主行程在目的目錄取一個隨機暫存檔名（`.~peditor-<16 hex>.tmp.pdf`），只把這個暫存路徑交給 worker；
     worker 看不到真正的目的路徑。
   - worker：完整重寫 → 結構、文字、視覺驗證 → 以 `xb` 建立暫存檔、寫入、fsync → 讀回比對位元組。
     寫入失敗時刪除自己寫出的部分檔（f017）。
   - 主行程：比對暫存檔 SHA-256 與 worker 回報值，再次檢查原檔與目的檔 → `os.replace` 原子取代 →
     （POSIX）fsync 目錄。任何一步失敗都刪除暫存檔，目的檔不動。
3. 程式中斷留下的暫存檔：下次寫入同一目錄時，刪除符合上述命名且超過 10 分鐘的暫存檔。
4. 原檔永遠不被覆寫；既有目的檔只在 `overwrite` 為真時以原子取代覆寫。

### 4. 儲存前驗證（worker）

- 結構：沿用 P2（完整重寫、無不可達物件、qpdf 問題數不增、MuPDF 不需修復、頁數不變）。
- 文字：每筆已套用的編輯，新文字（去空白）須出現在輸出該頁的 MuPDF 擷取文字中；
  同頁之後有可改動區域重疊的編輯時略過（新文字可能被後續編輯取代）；新文字為空時略過。
- 視覺：內容有改動的頁面，以 MuPDF 150 DPI 渲染原檔與輸出，所有編輯可改動區域外擴 2 pt 之外，
  每通道差異 >8/255 的像素比例須 ≤0.01%（spec §8.2）。內容沒改動的頁面以運算子比對確認（G2-10），不渲染。
- 視覺驗證用 MuPDF（產品執行期相依）；pypdfium2 只在測試使用。ADR-0015 的 7 份 MuPDF 渲染空白檔，
  產品端視覺驗證實際上無法偵測差異，此限制待 ADR-0015 後續（P4 預覽前）處理。

### 5. 復原草稿

- 位置：使用者本機資料目錄（Windows `%LOCALAPPDATA%\PEditor\drafts`、macOS
  `~/Library/Application Support/PEditor/drafts`），不放在文件旁；每份開啟的文件一個 JSON 檔，
  內容為原檔路徑、SHA-256、command log、目前位置、儲存時間。以暫存檔＋原子取代寫入，POSIX 權限 0600。
- 每次 apply／undo／redo 後更新；正常 `close_document` 時刪除。
- 不自動開啟：`list_drafts()` 列出，呼叫端（P4 UI）由使用者選擇後才 `recover_draft()`；
  原檔 SHA-256 與草稿不同時拒絕（`REVISION_CONFLICT`）。`discard_draft()` 刪除。
- 保留 7 天：超過 7 天的草稿在列出或建立草稿區時刪除。
- 草稿含新文字，屬敏感內容；DocumentService 預設不啟用草稿（CLI 不用），由 UI 傳入草稿目錄才啟用。

### 6. U4 範圍

P3 修正 f003、f017；f006、f018、f023、f015 不在 P3 範圍。

## 後果

- `export_document` 參數由路徑改為 `destination_token`（spec §7）；worker 端 `export.export_document` 仍收路徑
  （只會收到主行程產生的暫存路徑），G2-08 的「不覆寫既有檔」在 worker 端保留。
- 撤銷較慢的步數多時，P4 UI 須顯示進行中狀態；若量測不足再改為「log＋定期快照」並另立 ADR。
- 磁碟空間不足以模擬錯誤（寫入時拋出 ENOSPC）驗證；真實磁碟填滿未測。
