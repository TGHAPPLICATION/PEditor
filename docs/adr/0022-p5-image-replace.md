# ADR-0022：P5 圖片替換（新圖登記、比例與透明遮罩、copy-on-write、草稿）

- 狀態：已接受（2026-11-03，工程師於 P5 S1／S2 決定「照建議」）
- 日期：2026-11-03
- 決策者：工程師
- 需人工確認：否（已確認）；實作時與 S2 說明不同之處列在「實作差異」，待工程師審查

## 背景

spec P5：單次圖片 occurrence 定位、資源 clone-on-write、維持變換矩陣／裁切／透明度；支援 PNG／JPEG；
預設維持外框比例，替換前檢查像素上限。G5：同一 xref 同頁及跨頁重用時只改選定 occurrence、其他頁視覺不變、
外框 ≤0.5 pt；簡單 SMask 與矩陣層級裁剪屬支援範圍，非矩形 clip path 等仍拒絕（ADR-0009）。
§7：`plan_image_edit(document_id, target_id, local_asset_id, expected_revision)`；不傳任意系統檔案路徑。
ADR-0009 把「新圖與原圖透明通道／尺寸不符時的處理」留給 P5。P1 已為每個圖片 `Do` 產生目標與能力判定，
P5 不改判定規則（不放寬支援範圍）。

## 決策

### 1. 新圖登記（local_asset_id）

- 主行程 `DocumentService.register_image(document_id, path)` 只讀檔案位元組（上限 32 MB），以 base64 經 IPC
  送 worker `register_asset`；asset_id＝位元組 SHA-256。主行程不解碼圖片。
- worker 先讀檔頭：只收 PNG 與 JPEG（8 位元、灰階或 RGB；CMYK、無損、階層、算術編碼 JPEG 拒絕），
  像素（寬×高）上限 50 MP（spec P7 單張影像），通過才以 PyMuPDF 解碼。PNG 另檢查每個區塊 CRC、有 IDAT 且以
  IEND 結束；JPEG 須有影像結束標記——MuPDF 會把截斷檔補成部分影像而不報錯（實測）。
  不支援或損壞回 `UNSUPPORTED_FEATURE`，超過上限回 `RESOURCE_LIMIT`。
- 不新增 Pillow 執行期相依（Pillow 目前只在 dev 群組）。
- 主行程只保留 command log 與未套用計畫用到的新圖，其餘在下次登記時兩端一起釋放。

### 2. 比例：變換矩陣不動，等比置中、兩側補透明

- 新圖畫進原本的單位正方形，`cm`、剪裁、圖形狀態（含 /ca 等透明度）都不動，外框與位置不變。
- 新圖長寬比與外框（CTM 的寬高，pt）相差超過 1%：在新圖兩側補透明邊到外框比例，新圖等比置中。
  補邊後的像素也受 50 MP 上限；超過時計畫不可套用（`RESOURCE_LIMIT`）。
- 經剪裁的圖片（I07）依 ADR-0009：外框指未剪裁的放置範圍，原剪裁照樣套到新圖，只顯示剪裁範圍內的部分；計畫附警告。

### 3. 透明遮罩：由新圖決定

- 新圖有透明部分（PNG alpha 非全不透明）或補了透明邊：產生新的 SMask（DeviceGray、Flate）。
- 新圖沒有透明部分：不帶 SMask；原圖的 SMask 不沿用（那是舊圖的形狀），原圖有 SMask 時計畫附警告。
- MuPDF 解碼的透明通道為預乘色彩，SMask 以 `/Matte` 黑色宣告（PDF 預乘遮罩），不逐點還原。
- JPEG 不需補邊時原樣嵌入（DCTDecode，位元組與新圖檔相同）；其餘解碼後以 Flate 壓縮嵌入。

### 4. copy-on-write

- 新增圖片 XObject 與新資源名稱（`/PEditorI<n>`），只把選定的那一個 `Do` 改成新名稱；原圖物件不動，
  同頁或其他頁的其他出現位置仍指向原圖。頁面 /Resources 與其 /XObject 先複製一份給這頁。
- 目標 content stream 被其他頁或重複列出共用時拒絕（`SHARED_RESOURCE_UNSAFE`，同 P2 文字）。
- 這頁已沒有其他頁面層級的 `Do` 用到原名稱、且頁面沒有 Type3 字型（可能借用頁面資源）時，移除原名稱；
  原圖若也沒有其他地方使用，完整另存時不再保留在檔案中。
- target_id 沿用 P1（含 revision、頁、content stream、運算子索引、Form 路徑、幾何 hash）；計畫只收 target_id 與
  asset_id（白名單），不接受路徑或 PDF 指令。

### 5. 套用、預覽、undo／redo、草稿

- 計畫 `mode="image"`，可改動區域＝目標可見範圍；`apply_edit`、`preview_edit`、另存交易與文字修改共用。
- command log 項目加 `"op": "image"`，params 為 `{target_id, asset_id}`；重播依 op 選規劃函式。
  worker 重啟與草稿復原時，主行程先重新登記新圖再重播。
- 復原草稿：新圖存成 `<draft_id>-<SHA-256>.img`（權限 0600），與草稿 JSON 同目錄、一起刪除；
  載入時新圖遺失或 SHA-256 不符即視為損壞草稿。保留期與 ADR-0020 §5 相同。
- 另存前驗證（ADR-0020 §4）加一項：只有圖片替換的頁面，輸出的擷取文字須與原檔完全相同（例如被圖片蓋住的文字，I06）。

### 6. UI（最小版）

頁面上的圖片目標以橘框標示，點選後側欄「選擇新圖片…」（PNG／JPEG 檔案對話框）→ 登記、規劃、前後對照 →
「套用」；復原、重做、另存沿用 P4。不能替換的圖片顯示原因。

## 選項（S2 時提出）

- 比例：拉伸填滿（變形）、比例不同即拒絕（實用性低）→ 未採用。
- 遮罩：沿用原 SMask（形狀與新圖無關，尺寸不同時須重採樣）→ 未採用。
- 介面：只做 core 與整合測試（P6–P8 沒排介面工作，功能到發布時沒有入口）→ 未採用。

## 實作差異（相對 S2 說明，待工程師審查）

1. **檔案大小上限 50 MB → 32 MB**：新圖以 base64 經 IPC 傳送，50 MB 會超過單則訊息上限 64 MiB（ADR-0004）；
   改傳路徑給 worker 讀檔又會讓草稿與重播依賴原圖檔不變，故降為 32 MB。
2. **預乘遮罩 /Matte**：S2 未提；為避免 Python 逐點還原 50 MP 影像。
3. **PNG／JPEG 結構檢查**：S2 未提；MuPDF 對截斷檔不報錯（§1）。

## 後果

- 新增 `src/peditor/worker/image.py`；修改 `worker/edit.py`（apply／preview／replay 依 op 分派）、`worker/analyzer.py`
  （記錄每個圖片目標的出現位置）、`worker/export.py`、`worker/server.py`、`core/protocol.py`（`register_asset`、
  `plan_image_edit`）、`core/editplan.py`、`core/limits.py`、`core/service.py`、`core/drafts.py`、`ui/app.py`、`ui/messages.py`。
- 限制：不讀 JPEG 的 EXIF 方向（手機照片可能橫躺，預覽可見）；ICC 色彩描述檔不保留（以 DeviceGray／DeviceRGB 嵌入）；
  PNG 調色盤圖解碼後以 RGB 嵌入（檔案較大）；16 位元 PNG 降為 8 位元。
- 新的不可信輸入（使用者提供的圖片檔，在 worker 內以 MuPDF 解碼）記入 THREAT_MODEL。
