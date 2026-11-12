# P8 授權核對（ADR-0002）— 核對結果與待決事項

- 核對日期：2026-11-12；核對版本：`main` @ `c4e0e2b`
- 核對者：Claude（自動核對與文件整理）；**簽核：待負責人**
- 依據：ADR-0002、`LICENSE`、`THIRD_PARTY_NOTICES.md`、`packaging/sbom/sbom-runtime.cdx.json`、`uv.lock`、
  各套件 wheel 內的 `dist-info` 授權檔、`packaging/build_release.py`、`packaging/windows/peditor.iss`
- 方法：讀取已安裝套件的授權中繼資料與授權檔；在本工作環境（Linux）以 `build_release.build()` 產生 onedir，檢查實際打包內容。
  **Windows 安裝包內容未實際檢查**（工作環境無法下載 CI artifact）；Windows 專屬的內容依各 wheel 官方說明推定，下文標「推定」。

> 這不是法律意見。授權相容性的判斷依各元件公開的授權條款；機關對外散布前，建議由機關法務或負責人確認第 4 節的決定。

## 1. 結論

- **授權相容性：通過。** 執行期相依皆與 AGPL-3.0-only 相容，沒有 GPL-2.0-only 或專有授權的元件（Microsoft VC++ Runtime 屬可再散布條款，見 F5）。
- **散布義務：未通過，需先補齊 4 項（F1–F4）才能正式散布。** 主要是安裝包沒有附上第三方授權全文、
  程式沒有顯示 AGPL 要求的法律聲明、沒有指出對應原始碼的位置、沒有著作權人聲明。

## 2. 相依與授權（執行期，隨安裝包散布）

`uv export --no-dev` 的執行期相依與 `dist-info` 中繼資料一致，和 `THIRD_PARTY_NOTICES.md`、ADR-0002 的表格相符：

| 元件 | 版本 | 授權（中繼資料） | 與 AGPL-3.0 相容 |
| --- | --- | --- | --- |
| PyMuPDF（含 MuPDF） | 1.28.2 | AGPL-3.0 或 Artifex 商業授權（選 AGPL） | 是 |
| pikepdf | 10.14.0 | MPL-2.0 | 是（MPL-2.0 §3.3） |
| PySide6-Essentials、shiboken6（Qt 6） | 6.11.2 | LGPL-3.0-only 或 GPL-2.0／3.0（選 LGPL-3.0） | 是（動態連結） |
| Pillow | 13.0.0 | MIT-CMU | 是 |
| lxml | 6.1.3 | BSD-3-Clause | 是 |
| packaging | 26.3 | Apache-2.0 或 BSD-2-Clause | 是 |
| fontTools | 4.66.0 | MIT | 是 |
| CPython | 3.13 | PSF-2.0 | 是 |
| Noto Sans TC | noto-cjk@f8d1575 | OFL-1.1 | 是（授權檔已隨包） |

各 wheel 內含的原生函式庫（依 wheel 內授權說明）：

| 來源 | 內含元件 | 授權 |
| --- | --- | --- |
| pikepdf | qpdf；libjpeg-turbo；Windows 另靜態連結 OpenSSL、zlib，並附 MSVC 執行階段 DLL（推定，依 pikepdf 第三方說明） | Apache-2.0；IJG＋BSD-3＋Zlib（IJG 要求附 README）；Apache-2.0；Zlib；Microsoft 可再散布條款 |
| pikepdf 資料檔 | sRGB ICC、veraPDF 規則、pdfminer 編碼表 | Zlib；**CC-BY-4.0**（需署名）；MIT |
| Pillow | FreeType、libjpeg、zlib、libpng、libwebp、lcms2、openjpeg、brotli 等 | FTL 或 GPL-2.0（選 FTL，需署名）、IJG、Zlib、MIT、BSD 等（Pillow `LICENSE` 1,574 行已整理） |
| lxml | libxml2、libxslt、zlib；Windows wheel 另含 **libiconv** | MIT、Zlib；**LGPL-2.1**（見 F6） |
| MuPDF | freetype、harfbuzz、jbig2dec、lcms2mt、libjpeg、openjpeg、zlib、gumbo、extract 等 | 各自授權（PyMuPDF wheel 只附一行 `COPYING`，沒有第三方授權全文） |
| PySide6 | Qt 6 函式庫與外掛 | LGPL-3.0（wheel 內**沒有**授權全文） |

## 3. 發現

| 編號 | 嚴重度 | 發現 | 依據 | 建議修正 |
| --- | --- | --- | --- | --- |
| F1 | 高 | 安裝包只附 `LICENSE`（AGPL）、`THIRD_PARTY_NOTICES.md`、Noto 授權；**沒有** Qt（LGPL-3.0＋其引用的 GPL-3.0 全文）、MPL-2.0、Apache-2.0、MIT／BSD 各元件的授權與著作權聲明。PyInstaller 不會帶入 `dist-info` 授權檔（本機 onedir 實測只找到上述 3 個檔） | LGPL-3.0 §4(a)(b)、MIT／BSD／Zlib／IJG「二進位散布須附聲明」、MPL-2.0 §3.2、Apache-2.0 §4 | 建置時把各套件 `dist-info` 授權檔、pikepdf 第三方授權、Qt 的 LGPL-3.0／GPL-3.0 全文、MuPDF 第三方授權、CPython 與 PyInstaller bootloader 授權，收進安裝目錄 `licenses/`；`THIRD_PARTY_NOTICES.md` 改為正式版並逐項指向 |
| F2 | 高 | 程式沒有「關於」畫面，沒有顯示 AGPL 要求的「適當法律聲明」（著作權、無擔保、授權與如何取得授權全文） | AGPL-3.0 §5(d)、§0「Appropriate Legal Notices」 | 新增「說明 → 關於 PEditor」：版本與建置 commit、著作權人、無擔保聲明、AGPL-3.0、原始碼網址、第三方授權資料夾 |
| F3 | 高 | 安裝包與說明文件沒有指出**該版本**的對應原始碼位置 | AGPL-3.0 §6（散布目的碼須提供對應原始碼）；MPL-2.0 §3.2(a) | 安裝說明與「關於」畫面列出 repo 網址與該版 commit（或 tag）；若安裝包不在 GitHub 散布，於散布處附同樣說明（§6(d)） |
| F4 | 中 | 專案沒有著作權人聲明（`LICENSE` 為 FSF 原文，README 只寫 AGPL） | AGPL-3.0「How to Apply」、§5(d) | 由負責人決定著作權人名稱（見第 4 節），寫入 README、`NOTICE` 與「關於」畫面 |
| F5 | 低 | Microsoft VC++ 執行階段 DLL（pikepdf Windows wheel 附帶，推定）屬 Microsoft 可再散布條款，非開源授權 | AGPL-3.0 §1「System Libraries」例外 | 一般視為系統元件例外；在 `THIRD_PARTY_NOTICES.md` 註明並附其條款檔 |
| F6 | 中 | lxml 的 Windows wheel 內含 libiconv（LGPL-2.1，依 lxml 授權說明）；若為靜態連結，LGPL-2.1 §6 要求讓使用者能以修改過的 libiconv 重新連結 | LGPL-2.1 §6 | 提供 lxml 原始碼取得方式與版本（lxml 公開、可自行重建）；**請負責人或法務確認此做法可接受**。本產品只經 pikepdf 間接使用 lxml |
| F7 | 低 | 打包含 `QtNetwork` 與 TLS 外掛（Linux 本機 onedir 實測，Windows 推定相同）。授權上沒有問題，但與「離線、不連網」的產品定位不一致 | spec 離線要求（`tests/security/test_offline_guard.py` 只檢查 `src/`） | 另案評估以 PyInstaller `--exclude-module` 排除；非授權阻擋項 |
| F8 | 低 | SBOM 只列 Python 套件，沒有列 wheel 內的原生函式庫 | — | 可接受；`THIRD_PARTY_NOTICES.md` 補列原生函式庫即可 |

## 4. 需要負責人決定的事

1. **著作權人名稱**（F4）：例如「臺北市政府衛生局」或開發者個人。這會寫進 README、`NOTICE` 與「關於」畫面。
2. **散布管道**（F3）：只在 GitHub Releases、市府內部網站，或兩者都有。若不只在 GitHub，散布處須附原始碼取得說明。
3. **libiconv（LGPL-2.1）的處理方式**（F6）：接受「指向 lxml 公開原始碼」的做法，或請法務確認。
4. **PyMuPDF 走 AGPL 路線**：ADR-0002 已決定；確認機關對外散布 AGPL 軟體沒有內部規定上的障礙。

## 5. 修正後的簽核清單（給負責人）

- [ ] F1：安裝目錄 `licenses/` 含上表所有元件的授權全文；`THIRD_PARTY_NOTICES.md` 由「草稿」改為正式版
- [ ] F2：「關於」畫面顯示著作權、無擔保、AGPL-3.0、原始碼網址、第三方授權位置
- [ ] F3：安裝說明與「關於」畫面列出對應原始碼（repo＋commit 或 tag）
- [ ] F4：著作權人名稱已寫入 README、`NOTICE`、「關於」畫面
- [ ] F5、F6：已在 `THIRD_PARTY_NOTICES.md` 註明；F6 的處理方式已確認
- [ ] 以 Windows 安裝包實際檢查 `licenses/` 內容（本次未能檢查 Windows 安裝包）
- [ ] 負責人簽核：姓名＿＿＿＿＿＿　日期＿＿＿＿＿＿
