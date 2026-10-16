# ADR-0006：第二套解譯器與結構檢查工具

- 狀態：已接受（2026-10-12，負責人確認）
- 日期：2026-10-12
- 需人工確認：否（已確認）

## 背景

spec §2、§8.1 要求「PyMuPDF 與第二套解譯器（如 Poppler）」分別擷取與渲染，並以 qpdf 做結構檢查。
Poppler 在 Windows 沒有官方 pip 套件，需另行安裝 binary（conda 或手動），CI 與開發機維運成本較高。

## 選項

1. Poppler（pdftotext／pdftoppm）：與規格範例一致；Windows 安裝與版本鎖定麻煩。
2. **PDFium（pypdfium2）**：Chrome 使用的解譯器，與 MuPDF 為不同實作；pip wheel 支援 Windows x64、macOS arm64，可由 `uv.lock` 鎖版。
3. pdf.js：需 Node 執行環境，不適合。

## 決策

- 第二解譯器採 pypdfium2（PDFium），列為 dev 相依（不隨產品散布）。
- 結構檢查採 qpdf，經 pikepdf `Pdf.check_pdf_syntax()` 呼叫（pikepdf wheel 內含 qpdf，不需另裝）。
- 若日後審查要求 Poppler，可在 P8 實機驗收以 Poppler 補一輪擷取，不改變 CI 流程。

## 後果

- `tests/integration/test_fixtures.py` 已用 PDFium 交叉驗證支援樣本的原文可擷取。
- P2 的雙引擎渲染比對以 MuPDF 與 PDFium 各自「同引擎原／新比對」（spec §8.2）。
