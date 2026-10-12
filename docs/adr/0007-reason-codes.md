# ADR-0007：補充能力判定理由碼

- 狀態：提議；**需人工確認**
- 日期：2026-10-12
- 需人工確認：是（P1 開工前；manifest 的 expected／reason_code 依此填寫）

## 背景

spec §7 錯誤碼著重於編輯操作（GLYPH_MISSING、TEXT_OVERFLOW…）。P1 的 capability report 與 §4 支援矩陣
還需要描述「為何整份或整頁不可編輯」，例如掃描檔、損毀檔、含主動內容。§4 要求「需理由碼；不能猜測替換」。

## 決策

保留 spec §7 全部錯誤碼，補充四個能力判定碼：

| 代碼 | 用途 | 對應 spec |
| --- | --- | --- |
| `NO_TEXT_LAYER` | 掃描 PDF、向量輪廓文字：唯讀並提示 | §4「掃描 PDF、向量輪廓文字」 |
| `MALFORMED_DOCUMENT` | 結構損毀（含 MuPDF／qpdf 需修復才可開啟） | §5 S 群組、§7 失敗規則 |
| `ACTIVE_CONTENT` | JavaScript、Launch、嵌入檔等主動內容 | P7「不執行 JavaScript、Launch、嵌入檔」 |
| `UNSUPPORTED_FEATURE` | PDF/A、XFA、複雜可及性標記 | §4「數位簽章、加密、PDF/A、XFA…」（簽章與加密沿用 §7 既有碼） |

`expected` 欄位值：`support`（宣告支援）、`reject`（拒絕編輯）、`readonly`（可預覽但唯讀）。

## 待確認

- 含 JavaScript／附件的文件（S02、S05）預設為 `reject ACTIVE_CONTENT`。若希望「可編輯但絕不執行主動內容」，
  改為 `support` 並在 P7 驗證不執行。
- 經 MuPDF 自動修復可開啟的損毀檔（S01）預設拒絕，避免在修復結果上編輯後覆寫。
