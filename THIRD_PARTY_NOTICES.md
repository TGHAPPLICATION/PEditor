# 第三方元件授權清單（草稿）

> 草稿，版本取自 P0 的 `uv.lock`。正式散布前（P8）以 SBOM 重新產生並由負責人核對（ADR-0002）。

## 執行期相依（隨產品散布）

| 元件 | 版本 | 授權 | 備註 |
| --- | --- | --- | --- |
| PyMuPDF（含 MuPDF） | 1.28.2 | AGPL-3.0（或 Artifex 商業授權） | 本產品採 AGPL 路線 |
| pikepdf | 10.14.0 | MPL-2.0 | wheel 內含 qpdf（Apache-2.0） |
| PySide6-Essentials | 6.11.2 | LGPL-3.0-only | Qt 6 函式庫以動態連結使用 |
| shiboken6 | 6.11.2 | LGPL-3.0-only | |
| Pillow | 12.3.0 | MIT-CMU | pikepdf 相依 |
| lxml | 6.1.3 | BSD-3-Clause | pikepdf 相依；wheel 內含 libxml2／libxslt（MIT） |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | pikepdf 相依 |
| CPython | 3.13 | PSF-2.0 | 打包時內嵌 |

## 字型

| 字型 | 授權 | 用途 |
| --- | --- | --- |
| Droid Sans Fallback（PyMuPDF 內建 `china-t`） | Apache-2.0 | 僅合成 fixture |
| Noto Sans TC／Noto Serif TC | OFL-1.1 | 人工 fixture；模式 B 重繪候選（P2 決定） |

## 建置與開發工具（不隨產品散布）

PyInstaller（GPL-2.0-or-later，含 bootloader 例外）、pytest、pytest-qt、ruff、jsonschema（MIT）。
