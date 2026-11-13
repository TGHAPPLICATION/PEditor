# 第三方元件授權清單

> 版本取自 `uv.lock`；P8 以 SBOM 重新產生（元件與版本與 P0 相同，見 `docs/release/dependencies.md`）。
> 授權核對結果見 `reports/P8/license-review.md`（ADR-0002）；**負責人簽核：2026-11-13**。
> 各元件授權全文附在安裝目錄的 `licenses/` 資料夾（建置時由 `packaging/build_release.py` 收集）。

## 執行期相依（隨產品散布）

| 元件 | 版本 | 授權 | 備註 |
| --- | --- | --- | --- |
| PyMuPDF（含 MuPDF） | 1.28.2 | AGPL-3.0（或 Artifex 商業授權） | 本產品採 AGPL 路線 |
| pikepdf | 10.14.0 | MPL-2.0 | wheel 內含 qpdf（Apache-2.0） |
| PySide6-Essentials | 6.11.2 | LGPL-3.0-only（上游為 LGPL-3.0／GPL-2.0／GPL-3.0 三選一，本產品選用 LGPL-3.0） | Qt 6 函式庫以動態連結使用 |
| shiboken6 | 6.11.2 | LGPL-3.0-only（同上，三選一選用 LGPL-3.0） | |
| Pillow | 13.0.0 | MIT-CMU | pikepdf 相依 |
| lxml | 6.1.3 | BSD-3-Clause | pikepdf 相依；wheel 內含 libxml2／libxslt（MIT） |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | pikepdf 相依 |
| fontTools | 4.66.0 | MIT | 模式 A 字形檢查、模式 B 字型子集化（ADR-0018） |
| CPython | 3.13 | PSF-2.0 | 打包時內嵌；`licenses/python/` |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later 含 bootloader 例外 | 編入執行檔；例外允許以任何授權散布；`licenses/pyinstaller/` |

### wheel 內含的原生函式庫與資料檔

| 來源 | 元件 | 授權 | 全文位置 |
| --- | --- | --- | --- |
| PyMuPDF（MuPDF 1.28.2） | freetype、harfbuzz、jbig2dec、lcms2、libjpeg、openjpeg、zlib、gumbo、mujs、extract、tesseract、leptonica、zxing-cpp、zint、brotli、cmark-gfm（依 MuPDF 子模組，是否全部編入未逐一確認） | FTL、MIT、AGPL-3.0、IJG、BSD-2、Zlib、Apache-2.0、ISC 等 | `licenses/mupdf-thirdparty/` |
| pikepdf | qpdf；libjpeg-turbo；Windows：OpenSSL、zlib（靜態連結）、Microsoft VC++ 執行階段 | Apache-2.0；IJG＋BSD-3＋Zlib；Apache-2.0；Zlib；Microsoft 可再散布條款（AGPL §1 系統元件例外） | `licenses/pikepdf/third-party-licenses/` |
| pikepdf 資料檔 | sRGB ICC、veraPDF 規則（CC-BY-4.0，© veraPDF Consortium）、pdfminer.six 編碼表 | Zlib、CC-BY-4.0、MIT | 同上 |
| Pillow | FreeType、libjpeg、zlib、libpng、libwebp、lcms2、openjpeg、brotli 等 | 見 Pillow `LICENSE` | `licenses/pillow/LICENSE` |
| lxml | libxml2、libxslt、zlib；Windows wheel 另含 libiconv | MIT、Zlib、**LGPL-2.1**（原始碼：https://github.com/lxml/lxml 與其建置腳本；見授權核對 F6） | `licenses/lxml/` |
| PySide6 | Qt 6 函式庫與外掛（動態連結，可替換安裝目錄內的 Qt 共享函式庫） | LGPL-3.0（Qt 自身第三方元件見 Qt 文件「Licenses Used in Qt」） | `licenses/qt/` |

## 字型

| 字型 | 授權 | 用途 |
| --- | --- | --- |
| Droid Sans Fallback（PyMuPDF 內建 `china-t`） | Apache-2.0 | 僅合成 fixture |
| Noto Sans TC Regular（noto-cjk@f8d1575） | OFL-1.1 | **隨安裝包散布**：模式 B 重建字型，授權檔 `peditor/resources/fonts/LICENSE-NotoSansCJK.txt`（ADR-0008、ADR-0025）；fixture |
| Noto Serif TC（google/fonts@bd8f81d） | OFL-1.1 | 僅 fixture（不散布） |

## 建置與開發工具（不隨產品散布）

PyInstaller（GPL-2.0-or-later，含 bootloader 例外）、Inno Setup（Inno Setup License）、pytest、pytest-qt、ruff、jsonschema、fontTools（MIT）、
ReportLab（BSD）、pypdfium2（Apache-2.0／BSD-3-Clause，含 PDFium）。

SBOM 草案（僅執行期相依）：`packaging/sbom/sbom-runtime.cdx.json`。
