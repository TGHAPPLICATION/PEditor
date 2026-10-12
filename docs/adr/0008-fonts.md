# ADR-0008：繁中字型來源與鎖定

- 狀態：提議；**需人工確認**
- 日期：2026-10-12
- 需人工確認：是（P2 模式 B 實作前）

## 背景

spec §2：繁中字型採 Noto Sans CJK TC 或 Source Han Sans TC，包裝具合法嵌入／散布授權的字型，不散布系統字型。
G2 要求至少 2 種繁中字型與 3 種 PDF 產生來源。

## 決策

| 字型 | 來源（鎖定 commit） | 授權 | 用途 |
| --- | --- | --- | --- |
| Noto Sans TC Regular（Noto Sans CJK TC 子集 OTF，CFF） | notofonts/noto-cjk@f8d1575 | OFL-1.1 | fixture；模式 B 預設重建字型候選 |
| Noto Serif TC（variable TTF，預設 instance 為 ExtraLight） | google/fonts@bd8f81d | OFL-1.1 | fixture（ReportLab 只支援 TrueType） |
| Droid Sans Fallback | PyMuPDF 內建 | Apache-2.0 | 僅 fixture |

- 字型檔不入 repo（共約 22 MB），以 `scripts/fetch_fonts.py` 下載並驗證 `tests/fixtures/fonts/fonts.json` 的 SHA-256；
  授權全文提交於 `tests/fixtures/fonts/LICENSE-*.txt`。
- 已確認三者皆**不含 𠮷（U+20BB7）**：含此字的替換須回傳 `GLYPH_MISSING`，不可顯示方框（spec §5）。
- MuPDF 1.28 的 `subset_fonts()` 無法子集化 CFF OTF（會整套嵌入約 4.9 MB），fixture 改用 fontTools 預先子集化；
  P2 實作模式 B 時須沿用同一作法並驗證。

## 後果

- 產品打包（P8）需將選定字型與 OFL 授權一併放入安裝包。
- 若需涵蓋 𠮷 等擴充區字，須另選字型並更新本 ADR。
