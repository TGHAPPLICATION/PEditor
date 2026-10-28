# ADR-0017：標記 PDF（tagged PDF）支援文字編輯，並驗證結構樹

- 狀態：已接受（2026-10-22，工程師於 P2 S1 選定「支援並驗證結構樹」，S3 確認本文細節）
- 日期：2026-10-22
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

spec §8.1：「若支援 tagged PDF，另驗證 ActualText／結構樹；MVP 未支援時阻擋，不能只更新畫面。」

P2 宣告支援的 18 個文字案例中，6 個是標記 PDF：T05、T06、F06、L04（Word）與 T08、F07（LibreOffice）。
P1 只在目標位於含 `/ActualText` 的**標記內容**（content stream 的 BDC 屬性）時判 `UNSUPPORTED_FEATURE`，
結構樹其他部分未檢查（P1 報告 §7）。若一律阻擋標記 PDF，Word 來源將全部失去（6 個 support 改 reject）。

標記 PDF 中，文字顯示運算子包在 `/Tag <</MCID n>> BDC … EMC` 內；結構樹（`/StructTreeRoot`）的結構元素經
`/K` 指向 MCID，`/ParentTree` 由頁面 `/StructParents` 反查。輔助技術讀到的文字有兩種來源：

1. 從 MCID 對應的內容取出實際文字（改內容即同步改到）。
2. 結構元素或標記內容上的替代文字 `/ActualText`、`/Alt`、`/E`（改內容**不會**同步，舊文字仍留在檔案中）。

## 選項

1. **支援，限「替代文字不涵蓋目標」的情況**，並驗證結構樹未受破壞。
2. 一律阻擋標記 PDF：支援範圍縮減，Word 來源全部失去。

## 決策

採用選項 1（工程師 2026-10-22 選定）。

### 能力判定（P2 補 P1 缺口，`plan_text_edit` 與 `inspect_page` 一致）

目標字元所在的標記內容，若符合下列任一條件，判 `UNSUPPORTED_FEATURE`：

- 標記內容屬性含 `/ActualText`、`/Alt`、`/E`（P1 只查 `/ActualText`，P2 補 `/Alt`、`/E`）。
- 經 `/StructParents` → `/ParentTree` → 結構元素，該元素**或任一祖先**含 `/ActualText`、`/Alt`、`/E`。
- 文件有 `/StructTreeRoot`，但目標的 MCID 在 `/ParentTree` 查不到、或查到的不是結構元素（結構不一致，不猜）。
- 目標跨越兩個以上不同 MCID 的標記內容（P2 不處理跨標記內容的替換）。此處的「目標」指 ADR-0018 §1 的
  **實際改動範圍**（去掉相同開頭與結尾後），選取範圍可跨多個 MCID（例：T08）。

結構樹走訪沿用 P1 的節點數與深度上限，超過判 `RESOURCE_LIMIT`。

### 修訂（2026-10-22，P2 步驟 7，工程師確認）：同步更新與內容相等的 /ActualText

P2 實作時發現：Word 產生的 T05、T06、F06、L04，目標所在的 `/Span` 結構元素帶有 `/ActualText`，內容就是該行原文
（例如 T05「本府辦理年度資訊安全稽核，請各單位配合。…」）。只改內容時，MuPDF 擷取會改從 `/ActualText` 取得**舊字**，
PDFium 則取得新字，正是本 ADR 背景所述的風險。工程師選定同步更新，取代上列「元素或祖先含 `/ActualText` 即拒絕」：

- 結構元素或祖先**含 `/Alt` 或 `/E`** → 仍拒絕（`UNSUPPORTED_FEATURE`）。
- 元素與祖先中**只有一個**含 `/ActualText`，且該 `/ActualText` **完全等於**它所涵蓋內容的擷取文字
  （依 `/K` 順序串接各 MCID 的文字，限同一頁、不含 OBJR）→ 允許編輯，並對 `/ActualText` 套用**同一字元範圍**的替換；
  儲存後須驗證 `/ActualText` 仍完全等於新內容的擷取文字。
- 不相等、跨頁、含 OBJR、多個層級都有 `/ActualText` → 拒絕（`UNSUPPORTED_FEATURE`）。
- 標記內容（BDC 屬性）上的 `/ActualText`、`/Alt`、`/E` 仍一律拒絕。
- 這是唯一允許修改的結構樹欄位；結構元素、MCID、`/ParentTree` 等仍不得變動。

### 編輯規則

- 模式 A：只改寫 Tj／TJ 的字串運算元，BDC／EMC 與其屬性完全不動。
- 模式 B：舊的文字顯示運算子移除後，新文字的運算子插入**同一個** BDC … EMC 範圍內，MCID 不變。
- 不新增、刪除或重新編號結構元素與 MCID；不修改 `/ParentTree`、`/RoleMap`、`/ClassMap`。

### 儲存後驗證（G2-17）

- `/StructTreeRoot` 仍存在；結構元素數量、`/ParentTree` 的鍵集合與每頁 `/StructParents` 不變。
- 每頁 content stream 中出現的 MCID 集合不變，且每個 MCID 仍只出現在一個標記內容中。
- 目標 MCID 經 PyMuPDF 與 PDFium 擷取的文字為新文；其他 MCID 的擷取文字不變。

## 後果

- `worker/content.py` 的 `TextRun` 需記錄所在標記內容的 MCID 與屬性（P1 只記是否有 `/ActualText`）。
- 測試：`tests/integration/test_edit_text.py::test_tagged_structure_preserved`（T05、T08 等）、
  `::test_tagged_actualtext_rejected`（腳本產生含結構元素 `/ActualText` 與 `/Alt` 的樣本，測試內產生）。
- 本 ADR 不宣稱輸出符合 PDF/UA；只保證結構樹不被破壞、替代文字不與新內容矛盾。
- P1 報告 §7 的「tagged PDF 只檢查 `/ActualText`」缺口在 P2 補上。
