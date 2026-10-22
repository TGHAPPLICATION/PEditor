# ADR-0015：MuPDF 渲染空白的 7 份 fixture 改以 PDFium 做視覺比對（P1 報告 U3）

- 狀態：已接受（2026-10-22，工程師選定「改用 PDFium」）
- 日期：2026-10-22
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

P1 報告 §9 U3：MuPDF 1.28.2 對 P0 以 PyMuPDF 產生、內嵌 Noto Sans TC（CFF，OTTO 包裝）的 7 份 fixture
——T01、F01、F02、F05、L02、L03、B01——渲染為空白頁（`FT_Load_Glyph … invalid argument`）；PDFium 渲染正常，
兩引擎文字擷取皆正常。

ADR-0006 規定 P2 視覺比對以 MuPDF 與 PDFium 各自做「同引擎原／新比對」（spec §8.2）。對這 7 份，MuPDF 的
原／新兩張圖都是空白，比對必然「完全相同」，無法證明任何事，卻會被誤當成通過證據。T01 又是 G2-11、G2-12
（T01–T04）與 G2-02、G2-07、G2-08 的主要樣本。

## 選項

1. **重產這 7 份 fixture**，改用 MuPDF 可渲染的字型包裝：hash 全部改變，P0／P1 的 fixture 證據與 manifest 須重新核對，
   且需先查明 MuPDF 失敗的確切原因才能確定重產後可渲染。
2. **這 7 份的視覺比對只以 PDFium 判定**：fixture 不變；MuPDF 對這 7 份不得作為視覺證據。

## 決策

採用選項 2（工程師 2026-10-22 確認）。

- spec §8.2 的視覺門檻（G2-10 未修改頁像素完全相同、G2-11 改動區外差異 ≤0.01%、G2-12 外框誤差 ≤0.5 pt）
  對這 7 份**以 PDFium 的同引擎原／新比對判定**。
- 其餘 fixture 仍依 ADR-0006 以 MuPDF、PDFium 兩引擎各自比對，兩者皆須通過。
- 這 7 份的 MuPDF 渲染結果不得列為通過證據；報告須標示「MuPDF：不適用（ADR-0015）」，不得寫 PASS。
- 例外清單只限上列 7 份。新增 fixture 若 MuPDF 渲染空白，須查明原因並另以 ADR 加入，不得自動排除。

## 後果

- `tests/integration/test_visual.py`（P2）以明列常數保存這 7 份 ID，並加一項防護測試：
  - 確認這 7 份 PDFium 渲染**非空白**（否則 PDFium 比對同樣失去意義）；
  - 確認其他 support fixture 的 MuPDF 渲染非空白，避免例外清單悄悄擴大。
- **產品面不因此解決**：`render_page`／`peditor analyze`（MuPDF）對同類檔案仍輸出空白頁，使用者預覽會是空白。
  這是產品缺陷而非測試問題，須在 P3（UI 預覽）前另案處理（查明 MuPDF 失敗原因、升級或換渲染路徑皆須另立 ADR）。
- PDFium（pypdfium2）維持 dev 相依、不隨產品散布（ADR-0006 不變）。
