# ADR-0011：T09（Microsoft Print to PDF）ToUnicode 缺數字，預期改為拒絕

- 狀態：已接受（2026-10-20，工程師確認）
- 日期：2026-10-20
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

`manifest.csv` 原定 T09 為 `support`：以 Word 輸入「公告日期：中華民國115年10月12日」，經
「Microsoft Print to PDF」輸出（第三種產生路徑），目標原文「10月12日」→「10月13日」。

2026-10-20 在製作機（Windows 11 Pro、Word 2021 16.0.14334、Win11 內建 Noto Sans TC VF 2.04）製作後發現：

- 畫面呈現正確（「115 年 10 月 12 日」）。
- 嵌入字型 `CIDFont+F1`（Type0／Identity-H，FontFile2 已 instancing、無 `fvar`／`gvar`）的 `/ToUnicode`
  只有 13 筆 bfchar（中文、`T`、空白、全形冒號），**完全沒有 0–9**。
- PyMuPDF 與 PDFium 都把數字的 CID 直接當成 Unicode，「10月12日」擷取為「俸俷月俸俹日」；
  頁面上找不到目標原文。

這是 Print to PDF 實際會產出的檔案，不是製作操作錯誤（同一腳本重產兩次結果相同）。

## 選項

1. **保留此輸出，T09 改為 `reject UNSUPPORTED_ENCODING`**：與 F05（缺 `/ToUnicode`）同一規則——無法可靠逆向映射即拒絕。
   T 組少一份 support 樣本，但多一份真實的「ToUnicode 不完整」樣本。
2. 保留 support，目標改為不含數字的文字：文件其他位置仍有錯誤映射，P1 須能只判定目標區域，支援範圍變寬。
3. 改用 Word 另存 PDF：放棄第三種產生路徑。

## 決策

採用選項 1：T09 `expected=reject`、`reason_code=UNSUPPORTED_ENCODING`，`original_text`／`new_text` 不變，`bbox_pt` 留空
（與 F05 相同，擷取不到原文）。

- `tests/integration/test_fixtures.py::test_reject_fixtures_have_stated_property` 的 UNSUPPORTED_ENCODING 性質改為：
  頁面擷取不到原文，且頁面上沒有任何字型的 `/ToUnicode` 涵蓋原文全部字元（無 `/ToUnicode` 視為未涵蓋）。
  F05 仍符合（無 `/ToUnicode`）；T09 符合（缺數字）。

## 後果

- P1 能力判定須偵測「`/ToUnicode` 存在但未涵蓋頁面實際使用的 CID」，不可只檢查有無 `/ToUnicode`。
- T 組 support 樣本由 T01–T08 與盲測 T10–T12 構成；Print to PDF 路徑改為拒絕樣本，不在 support 矩陣內。
- 若日後 Windows 更新改變 Print to PDF 行為，重產 T09 前須重新確認本 ADR。
