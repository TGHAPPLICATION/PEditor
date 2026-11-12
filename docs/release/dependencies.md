# PEditor 相依來源與版本（P8 發布候選）

> 版本以 `uv.lock` 為準（`tool.uv.exclude-newer` 鎖定）；P8 沒有變更相依。授權由負責人核對後才能正式散布（ADR-0002）——
> **核對：待負責人**。

## 隨安裝包散布（執行期）

| 元件 | 版本 | 來源 | 授權 | SBOM |
| --- | --- | --- | --- | --- |
| CPython | 3.13（uv 管理的 python-build-standalone，CI 實際版本見建置 log） | python.org／astral-sh/python-build-standalone | PSF-2.0 | — |
| PyMuPDF（含 MuPDF） | 1.28.2 | PyPI wheel | AGPL-3.0 | ✓ |
| pikepdf（含 qpdf） | 10.14.0 | PyPI wheel | MPL-2.0（qpdf Apache-2.0） | ✓ |
| PySide6-Essentials | 6.11.2 | PyPI wheel | LGPL-3.0（選用） | ✓ |
| shiboken6 | 6.11.2 | PyPI wheel | LGPL-3.0（選用） | ✓ |
| Pillow | 13.0.0 | PyPI wheel | MIT-CMU | ✓ |
| lxml | 6.1.3 | PyPI wheel | BSD-3-Clause | ✓ |
| packaging | 26.3 | PyPI wheel | Apache-2.0 OR BSD-2-Clause | ✓ |
| fontTools | 4.66.0 | PyPI wheel | MIT | ✓ |
| Noto Sans TC Regular（模式 B 重建字型） | notofonts/noto-cjk@f8d1575，SHA-256 `5bab0cb3…237537` | GitHub（`scripts/fetch_fonts.py` 驗證） | OFL-1.1（授權檔隨附 `peditor/resources/fonts/LICENSE-NotoSansCJK.txt`） | — |

SBOM：`packaging/sbom/sbom-runtime.cdx.json`（CycloneDX 1.5，`uv export --format cyclonedx1.5 --no-dev --frozen --preview`；
P8 重新產生，元件與版本與 P0 草案相同）。

## 建置工具（不隨產品散布）

| 工具 | 版本 | 用途 |
| --- | --- | --- |
| PyInstaller | 6.22.3（Windows release 以原始碼編譯 bootloader，ADR-0025 §4） | onedir 凍結 |
| Inno Setup | 6.7.1（Chocolatey） | Windows 安裝程式 |
| hdiutil | macOS 內建 | DMG |
| uv | 0.11.32 | 鎖定安裝 |

## 安裝包

| 平台 | 檔名 | SHA-256 |
| --- | --- | --- |
| Windows | `PEditor-<版本>-windows-x64-setup.exe` | 見該次 CI artifact 的 `SHA256SUMS.txt`、`release.json` |
| macOS | `PEditor-<版本>-macos-arm64.dmg` | 同上 |
