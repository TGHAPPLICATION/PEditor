# ADR-0013：P1 能力判定延後項目（B06 合併格、F03／F08 缺字）

- 狀態：已接受（2026-10-21，工程師於 P1 S2 確認 B06；F03／F08 依 spec §7 API 分工）
- 日期：2026-10-21
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

G1 要求「可編輯／不可編輯符合預定清單」。repo 內 45 份 available fixture 中，有 3 份的預期拒絕無法在 P1 的
只讀 API（`open_document`、`inspect_page`、`assess_editability`）判定：

- **B06**（`reject UNSUPPORTED_LAYOUT`，合併儲存格）：需辨識表格線條與格界，屬 P6「以文字及線條推估表格」。
- **F03、F08**（`reject GLYPH_MISSING`）：缺字取決於使用者要輸入的新文字，spec §7 的 `plan_text_edit(…, new_text, …)`
  才有新文字（P2）。

P1 對這 3 份只能判定「文字層可定位」，輸出為 `support`。

## 選項

1. **延後判定並明列**：P1 測試以 `DEFERRED` 清單逐項說明，報告標註；P2／P6 補上判定與測試。
2. P1 先做表格偵測與新文字缺字檢查：P1 多 1–2 人日，且提前做掉 P2／P6 的工作。

## 決策

採用選項 1（工程師 2026-10-21 於 P1 S2 選定 B06 延至 P6）。

## 後果

- 在 P2／P6 補上前，`inspect_page` 對 B06 的格內文字、F03／F08 的原文回報 `support`；這只代表文字層可對應，
  **不得**據此在 P2–P5 允許編輯：
  - P2 的 `plan_text_edit` 必須對 F03、F08 回 `GLYPH_MISSING`（G2-04）。
  - P6 的 `plan_cell_edit` 必須對 B06 回 `UNSUPPORTED_LAYOUT`（G6）；P2–P5 不得把 B06 當支援案例使用。
- G1-03 以「42 份逐項相符＋3 份依本 ADR 延後」驗收；`tests/integration/test_analyzer.py` 的 `DEFERRED` 只能包含本 ADR 列出的 fixture。
