# ADR-0002：產品採 AGPL-3.0-only 開源

- 狀態：已接受（計畫書 v1.1）；**機關同意公開與 repo 歸屬待人工確認**
- 日期：2026-10-12
- 需人工確認：是（P0 第 1 週）

## 背景

PyMuPDF 為 AGPL-3.0／Artifex 商業授權雙授權。不購買商業授權時，產品散布須相容 AGPL。
公開 repo 也讓 GitHub Actions 標準 runner 免費（含 macOS arm64）。

## 決策

- 產品授權：`AGPL-3.0-only`（`LICENSE` 為 FSF 原文）。
- 相依授權相容性（P0 實測版本見 `uv.lock`）：

| 元件 | 授權 | 使用方式 |
| --- | --- | --- |
| PyMuPDF（含 MuPDF） | AGPL-3.0 | 一般相依 |
| pikepdf（含 qpdf） | MPL-2.0（qpdf：Apache-2.0） | 一般相依 |
| PySide6-Essentials／shiboken6（Qt 6） | LGPL-3.0 | **動態連結**；打包時保留可替換的 Qt 共享函式庫 |
| Pillow、lxml 等傳遞相依 | MIT-CMU／BSD | 一般相依 |
| PyInstaller（僅建置） | GPL-2.0+ 含 bootloader 例外 | 不隨產品散布其原始碼義務 |
| 字型 | 只用 OFL（如 Noto Sans/Serif TC）或 Apache-2.0（Droid Sans Fallback，僅合成 fixture） | 嵌入 |

- repo 自 P0 起公開；只放合成 fixture。

## 後果

- 若機關不同意公開：AGPL 方案不成立 → CI 改計費、PyMuPDF 需商業授權 → 回到授權決策（高風險，計畫書風險表）。
- 正式散布前（P8）由負責人核對 `THIRD_PARTY_NOTICES.md` 與 SBOM。
- 不得引入與 AGPL 不相容的相依（如 GPL-2.0-only、專有授權）；新增相依須更新本 ADR 的表格。
