# licenses/

PEditor 安裝包隨附的第三方授權全文（P8 授權核對 F1；對照 `THIRD_PARTY_NOTICES.md`）。

- `<套件名>/`：建置時由各套件 wheel 的 `dist-info` 複製（pymupdf、pikepdf 與其 `third-party-licenses/`、
  pyside6-essentials、shiboken6、pillow、lxml、packaging、fonttools、pyinstaller）。
- `qt/`：Qt 6（PySide6、shiboken6）選用的 LGPL-3.0 及其引用的 GPL-3.0 全文（SPDX license-list-data，
  2026-11-12 取得）；PySide6 wheel 未附授權全文。Qt 自身內含的第三方元件見 Qt 文件「Licenses Used in Qt」。
- `mupdf-thirdparty/`：MuPDF 1.28.2 子模組（ArtifexSoftware 的 thirdparty-* 與 jbig2dec、mujs、extract 倉庫，
  2026-11-12 取得預設分支）的授權檔，檔名為「元件--原檔名」。PyMuPDF wheel 只附一行 `COPYING`。
  是否每一項都編入 PyMuPDF wheel 未逐一確認（curl、freeglut 只用於 MuPDF 檢視器，未收）。
- `python/`：CPython 的 PSF-2.0 全文；建置環境找得到 CPython 的 `LICENSE.txt`（含其內嵌元件）時一併附上。
