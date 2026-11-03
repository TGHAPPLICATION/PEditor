# P5 關卡報告：圖片替換

> 依 spec §11 範本（`reports/TEMPLATE.md`）。未執行項目標 `NOT RUN`；CI 證據與實機證據分開記錄。
> 本段測試在本機 Windows 製作機（GUI 為 offscreen）與 CI 執行，**不是實機證據**。

## 1. 階段／commit／日期

- 階段：P5　分支：`p5-image-replace`　commit：`c1a1c87`（實作與 G5 測試）、`d5dc648`（補測試：共用 content stream、圖片頁文字變動偵測）、`cfee71a`（證據包與產生腳本 `scripts/p5_evidence.py`）、`bdc355f`（U3 快取、U4 EXIF 提示）、`a584ca8`（第一輪核對 N1、N6、N7）　日期：2026-11-03
- 只改報告、traceability 或 CI 紀錄的 commit（`11cb4c7`、`86d47bf`、`89614e0` 等）依 P4 慣例不列。
- 撰寫：Claude Code；審查：待工程師；獨立核對：待（CLAUDE.md：由未參與實作的子代理人核對）
- 輸入：spec v1.1 P5／G5／§7／§8／§9、ADR-0001～0021（重點 ADR-0009）、manifest I01–I09、`docs/traceability.md` 預登記的 G5-01～G5-04、P4 報告 §10（下一段可開始：是，附條件）
- S1／S2 工程師決定（2026-11-03「照建議」，ADR-0022）：
  1. 比例不同時變換矩陣不動，等比置中、兩側補透明；
  2. 透明遮罩由新圖決定，不沿用原 SMask；
  3. 主行程讀檔交 worker 登記（asset_id＝SHA-256），worker 檢查格式與像素上限後以 PyMuPDF 解碼，不新增 Pillow 執行期相依；草稿另存新圖檔；
  4. P5 含最小版 UI。
- 實作與 S2 說明不同之處（ADR-0022「實作差異」，§9 U1）：檔案大小上限 50 MB 改為 32 MB；透明通道以預乘遮罩 `/Matte` 嵌入；另加 PNG／JPEG 結構檢查。
- §9 U1–U5 工程師決定（2026-11-03「照建議」）：U1 接受；U2 保留做法、列 P8 實機檢查；U3 預覽建好的圖片資料由套用重用（`bdc355f`），其餘列 P7；U4 只提示不轉正（`bdc355f`）；U5 不擋 P5、併入 P8 實機驗收。

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機（製作機） | Windows 11 Pro 10.0.26300 x64 | 同 P0 | Python 3.13.16；PyMuPDF 1.28.2；pikepdf 10.14.0；PySide6 6.11.2；fontTools 4.66.0；pypdfium2 5.13.0、Pillow 13.0.0（只在測試）；Noto Sans TC（ADR-0008） |
| macOS 實機 | NOT RUN（無實機，ADR-0003） | — | — |
| CI windows | windows-latest x64 | GitHub 標準 runner | 套件同上（`uv.lock`）；offscreen |
| CI macos | macos-15 arm64 | GitHub 標準 runner | 套件同上（`uv.lock`）；offscreen |

相依沒有變更（`uv.lock`、`pyproject.toml` 未改）。

## 3. 需求 → test ID → fixture／hash → 結果

fixture hash（前 12 碼）：I01 `7a8001d4d803`、I02 `3e241f7b6fef`、I03 `7bd88c07864d`、I04 `04a408c4cee4`、I05 `a4b27c478ce9`、I06 `fd2c9cc50675`、I07 `e88b9a7270f1`、I09 `ddc12162a6d8`。
「本機」＝Windows 製作機（GUI 為 offscreen）；「CI」＝run [41609744423](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41609744423)（commit `a1fca9d`）windows-latest 406 passed、macos-15 406 passed。

| 需求 ID | test ID | fixture | 本機 | CI |
| --- | --- | --- | --- | --- |
| G5-01 | `tests/integration/test_edit_image.py::test_all_supported_image_cases`（7 組）：只有選定的 `Do` 改名；新圖尺寸與像素；MuPDF、PDFium 遮罩外差異 ≤0.01%、可見範圍中心為新圖；沒有其他地方用的原圖不保留 | I01–I07 | PASS | PASS |
| G5-02 | `::test_only_selected_occurrence_changed`（I02 跨頁、I03 同頁）：另一個出現位置仍指向原圖（位元組相同），選定的指向新圖；`::test_shared_content_stream_rejected`：content stream 被另一頁共用時拒絕；`::test_form_sharing_page_resources_keeps_original`：沒有自己 /Resources 的 Form 沿用頁面資源畫同名原圖時，不移除原名稱、Form 內仍是原圖（核對 N1） | I02、I03、測試內樣本 | PASS | PASS |
| G5-03 | `::test_other_pages_unchanged_and_bbox`：I02 第 2 頁雙引擎逐像素相同、內容差異只在第 1 頁；I01–I07 替換後外框與可見範圍誤差 ≤0.5 pt（實測 0） | I01–I07 | PASS | PASS |
| G5-04 | `::test_reject_unsupported_mask_clip`（I09 非矩形剪裁 UNSUPPORTED_LAYOUT；補邊後 72 MP 回 RESOURCE_LIMIT）；`tests/unit/test_image_asset.py`（8 項：格式、GIF／BMP／CMYK／無損 JPEG、截斷與 CRC 錯誤、像素上限在解碼前檢查、大小上限、參數白名單、EXIF 方向） | I09、I01、測試內圖片 | PASS | PASS |
| G5-05 | `::test_aspect_fit_and_smask`：正方形新圖放入 2:1 外框補透明（SMask、`/Matte`），雙引擎左側露出白色頁面；I04 不透明新圖不帶 SMask、半透明新圖產生新 SMask；I05 JPEG 原樣嵌入；I06 擷取文字不變。`::test_image_text_check_detects_changed_text`：文字有變動時另存前驗證能偵測；`::test_built_image_reused_after_preview`：預覽後套用與重播不再解碼壓縮（U3）；`::test_exif_orientation_warned`：EXIF 方向 6 提示、一般 JPEG 不提示（U4） | I01、I04、I05、I06 | PASS | PASS |
| G5-06 | `tests/integration/test_image_service.py`（5 項：逾期草稿連新圖檔一起刪（核對 N7）；預覽不提交、undo／redo、worker 重啟重播；草稿含新圖檔、復原、正常關閉刪除、新圖檔遺失視為損壞；錯誤不含路徑、未使用新圖釋放；與文字修改共用 log）；`test_drafts.py::test_draft_structure_validated` 新增 3 組 | I01、I03、I06 | PASS | PASS |
| G5-07 | `tests/gui/test_image_ui.py`（2 項：點選圖片、選新圖、前後對照、套用、復原、重做、另存到中文與空白檔名；I09 顯示原因、GIF 顯示原因） | I01、I03、I09 | PASS（offscreen） | PASS |

實機：G5 不在 ADR-0003 規定須實機的關卡（G4、G7、G8）；圖片 UI 的實機操作與原生檔案對話框 NOT RUN（§7）。

## 4. 執行命令、exit code、測試數

```
uv run ruff check . && uv run ruff format --check .   → exit 0
uv run pytest -q                                        → exit 0，396 passed（Windows 製作機，c1a1c87）
uv run pytest -q                                        → exit 0，398 passed（Windows 製作機，d5dc648 補 2 項）
uv run pytest -q                                        → exit 0，404 passed（Windows 製作機，bdc355f，U3／U4 補 6 項）
uv run pytest -q                                        → exit 0，406 passed（Windows 製作機，a584ca8，第一輪核對補 2 項）
uv run python scripts/p5_evidence.py reports/P5/evidence → exit 0
```

- P5 新增 46 項測試：`test_edit_image.py` 17 項（含參數化 9 組）、`test_image_asset.py` 19 項（參數化 13 組）、`test_image_service.py` 5 項、`test_image_ui.py` 2 項、`test_drafts.py` 新增 3 組。P4 既有 360 項未修改預期（`test_drafts.py` 只在參數清單末尾加 3 組），全數通過。
- **反向驗證**（`scripts` 外的臨時腳本，逐一改壞實作、跑對應測試、再以 `git checkout` 還原，工作區乾淨）：16 項改動全部被測試抓到（M12、M13 為 U3／U4 處理後補做，M14–M16 為第一輪核對處理後補做；第一次做 M12 時以 `git checkout` 還原，誤把尚未提交的 U3／U4 修改一併還原，重新套用、先提交後再做）——

  | # | 改壞的內容 | 失敗的測試 |
  | --- | --- | --- |
  | M1 | 改寫原圖物件（等同全文件 `replace_image(xref)`） | `test_only_selected_occurrence_changed` 2 組、`test_other_pages_unchanged_and_bbox` |
  | M2 | 頁面資源就地修改、不複製 | `test_all_supported_image_cases[I02]`、`test_only_selected_occurrence_changed[I02]`、`test_other_pages_unchanged_and_bbox` |
  | M3 | 不移除原名稱 | `test_all_supported_image_cases` 5 組（I01、I04–I07） |
  | M4 | 不補邊 | `test_aspect_fit_and_smask`、`test_padding_geometry` |
  | M5 | 不檢查 PNG 結構 | `test_unsupported_or_broken_images_rejected` 3 組 |
  | M6 | 不檢查共用 content stream | `test_shared_content_stream_rejected` |
  | M7 | 解碼前不檢查像素上限 | `test_pixel_limit_checked_before_decoding` |
  | M8 | 重播不分派圖片計畫 | `test_image_service.py` 2 項 |
  | M9 | 草稿不存新圖 | `test_image_draft_recovery` |
  | M10 | worker 重啟不重新登記新圖 | `test_image_preview_undo_redo_and_restart` |
  | M11 | 另存不檢查圖片頁文字 | `test_image_text_check_detects_changed_text` |
  | M12 | 每次都重新解碼壓縮（不重用，`bdc355f` 後） | `test_built_image_reused_after_preview` |
  | M13 | 不提示 EXIF 方向（`bdc355f` 後） | `test_exif_orientation_warned` |
  | M14 | 判斷移除原名稱時排除 Form 內的使用（N1 修正前的行為） | `test_form_sharing_page_resources_keeps_original` |
  | M15 | 逾期草稿只刪 JSON（N7 修正前的行為） | `test_expired_draft_purges_its_images` |
  | M16 | `register_asset` 不檢查參數白名單 | `test_register_asset_keep_and_bad_data` |

- 本機 pytest 收集階段會印出一次 `Windows fatal exception: access violation`（`pypdfium2` 載入 pdfium 時，faulthandler 回報已處理的例外）；單獨 `python -X faulthandler -c "import pypdfium2"` 也會出現且 exit 0，與 P5 程式無關，測試照常完成。
- CI：run [41609744423](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41609744423)（commit `a1fca9d`）windows-latest 406 passed、macos-15 406 passed；先前 run 41593863258（`cfee71a`）、41594346667（`11cb4c7`）雙平台 398 passed，41607137231（`86d47bf`）雙平台 404 passed，只作歷史紀錄。

## 5. 真修改證據

證據包 `reports/P5/evidence/`（`scripts/p5_evidence.py` 產生；`output.pdf` 不入庫，SHA-256 記於 `summary.json`）。新圖為與外框同比例的單色洋紅 PNG。

| 案例 | 內容差異（解碼後運算子） | 頁面 XObject 資源 | 原圖保留 | 遮罩外差異（MuPDF／PDFium） | 可見範圍中心（兩引擎） | 其他 |
| --- | --- | --- | --- | --- | --- | --- |
| I01 | 第 1 頁 `/fzImg0 Do` → `/PEditorI1 Do` | 新增 `/PEditorI1`、移除 `/fzImg0` | 否 | 0／0 | (255,0,255) | |
| I02 | 同上（只第 1 頁） | 第 1 頁新增、移除 | 是（第 2 頁仍用） | 0／0 | (255,0,255) | 第 2 頁兩引擎逐像素相同 |
| I03 | `/fzImg1 Do` → `/PEditorI1 Do` | 新增 `/PEditorI1`、移除 `/fzImg1` | 是（`/fzImg0` 仍用） | 0／0 | (255,0,255) | |
| I04 | `/Image14 Do` → `/PEditorI1 Do` | 新增、移除 | 否 | 0／0 | (255,0,255) | 警告：原透明遮罩不沿用 |
| I05 | `/Im4 Do` → `/PEditorI1 Do` | 新增、移除 | 否 | 0／0 | (255,0,255) | |
| I06 | `/Image14 Do` → `/PEditorI1 Do` | 新增、移除 | 否 | 0／0 | (255,0,255) | 被蓋住的文字兩引擎擷取與原檔相同 |
| I07 | `/Im4 Do` → `/PEditorI1 Do` | 新增、移除 | 否 | 0／0 | (255,0,255) | 警告：原圖經剪裁 |
| I09 | — | — | — | — | — | 拒絕 `UNSUPPORTED_LAYOUT` |

- `summary.json` 的 `output_sha256` 只對應當次產出：輸出檔 trailer `/ID` 為隨機值，重產後雜湊不同；`visual.json`、`compare.png` 可逐位元組重產（第一輪核對 N5）。
- 每案另存驗證都通過：完整重寫、無增量歷史、無不可達物件、qpdf 問題數不增、MuPDF 不需修復；圖片頁擷取文字與原檔相同（`text_changed` 為空）。
- 「原圖保留」以輸出中是否有與原圖 raw 位元組相同的串流判定：只有其他出現位置仍使用時保留（I02、I03）。
- 遮罩為 manifest 事前宣告的 `editable_region_pt`（可見範圍 ±2 pt）再外擴 2 pt，不是看完差異才決定。

## 6. 資料完整性與資源／出站紀錄

- **UI 不碰 PDF、不解碼圖片**：`src/peditor/ui/` 與 `core/service.py` 不匯入 PyMuPDF／pikepdf／Pillow；主行程只讀新圖檔位元組（G1-01 測試持續通過）。
- **只改選定的出現位置**：新增圖片物件與新資源名稱，只改選定的 `Do`；頁面資源與 /XObject 字典寫時複製（M2 反向驗證）；content stream 共用即拒絕。
- **原檔**：不修改（沿用 P3 交易；`test_source_never_modified` 持續通過）。
- **草稿**：新圖檔 `<draft_id>-<SHA-256>.img` 與草稿 JSON 同目錄、0600、先寫圖再寫 JSON；載入時 SHA-256 不符即視為損壞並刪除；正常關閉一併刪除；草稿已不存在的新圖檔超過 7 天由 purge 刪除。
- **錯誤訊息**：讀不到的圖片檔回「無法讀取圖片檔」，不含路徑（`test_register_image_errors_and_release`）。
- **出站**：新增模組未匯入網路模組（`test_offline_guard` 通過）。
- **資源**：新圖 ≤32 MB、≤50 MP（含補邊）；主行程與 worker 只保留 command log 與未套用計畫用到的新圖。量測（本機，`I01`，各 5 次）：

  | 新圖 | 登記 | 預覽 | 套用 | 另存 |
  | --- | --- | --- | --- | --- |
  | PNG 2000×1000 雜訊（4.8 MB，比例相同） | 0.06 s | 0.52 s | 0.44 s | 0.09 s |
  | PNG 6000×3000 漸層（18 MP，比例相同） | 0.09 s | 0.43 s | 0.36 s | 0.15 s |
  | JPEG 6000×4000 雜訊（13 MB、24 MP，需補邊） | 0.36 s | 6.65 s | 6.06 s | 1.10 s |

  U3 處理後（`bdc355f`，預覽建好的圖片資料由套用重用）：套用在預覽之後依序為 0.00 s、0.00 s、0.03 s；登記、預覽、另存不變（24 MP JPEG 預覽 6.66 s）。
  需補邊的大 JPEG 預覽須解碼並以 Flate 重新壓縮，仍超過 spec §8.3 單頁預覽 2 秒的產品目標（§9 U3，列 P7）；在 30 秒逾時內。18 MP 純雜訊 PNG（約 54 MB）超過 32 MB 上限，登記即拒絕。

## 7. 限制、阻擋、未測項目

- **實機**：圖片 UI 的實機操作、原生「選擇新圖片」對話框 NOT RUN（E2E 以 `ask_image` 注入路徑）；macOS 實機 NOT RUN（ADR-0003）。工程師決定併入 P8 實機驗收（U5），P8 清單須加：點選圖片與選檔對話框、套用後另存重開、半透明 PNG 替換結果在 Acrobat Reader 與 Edge 的顯示（U2）。
- **圖片格式**：只收 PNG 與 8 位元灰階／RGB JPEG；JPEG EXIF 方向只提示、不轉正（U4；PNG 的 eXIf 區塊不讀）；ICC 色彩描述檔不保留；調色盤 PNG 以 RGB 嵌入；16 位元 PNG 降為 8 位元。
- **預乘遮罩**：低透明度像素的色彩精度降低（8 位元預乘）；只以 MuPDF、PDFium 驗證渲染，其他閱讀器未測（§9 U2）。
- **原名稱移除條件中的 Type3 分支**沒有 fixture 覆蓋（頁面有 Type3 字型時保留原名稱，原圖會留在檔案中）。
- **不擴大支援範圍**：Form 內的圖片、inline image、旋轉或翻轉的圖片、非矩形剪裁維持拒絕（P1 判定未改）。
- **盲測 I08**：NOT RUN，P8 執行。

## 8. 安全審查

- CLAUDE.md 規定的 vuln-scan／triage 時點是 P1、P2、P3、P7，P5 沒有規定：**NOT RUN**。P7 掃描範圍應包含 `worker/image.py` 與 `register_asset`。
- 新增的攻擊面：使用者提供的 PNG／JPEG 在 worker 內以 MuPDF 解碼；worker 操作 `register_asset`（base64、keep 清單型別檢查）、`plan_image_edit`（參數白名單、asset_id 格式）；草稿目錄的新圖檔。
- `THREAT_MODEL.md` 已更新：§3 新增「新圖片檔」入口；新增 T15（惡意或損壞的圖片檔）；T1 改寫 Pillow 註記；T11 加圖片 copy-on-write 控制。

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |
| U1 | 實作與 S2 說明不同：檔案大小上限 50 MB → 32 MB（base64 經 IPC 須在 64 MiB 單則上限內）；預乘遮罩 `/Matte`；另加 PNG／JPEG 結構檢查（ADR-0022「實作差異」） | 大於 32 MB 的圖片無法使用 | **接受**（工程師 2026-11-03） |
| U2 | 透明通道以預乘遮罩 `/Matte` 嵌入，只驗證 MuPDF 與 PDFium；低透明度像素精度降低 | 其他閱讀器若不支援 /Matte，半透明邊緣顏色可能偏暗（只影響新圖本身帶半透明像素的情況；補邊遮罩只有 0 與 255） | **保留做法，列 P8 實機檢查**（工程師 2026-11-03；§7） |
| U3 | 需補邊的大圖預覽與套用各約 6 秒（24 MP JPEG），超過 spec §8.3 單頁預覽 2 秒目標；可快取預覽建好的圖片物件給套用重用、或降低壓縮等級 | 大圖操作慢；未超過 30 秒逾時 | **P5 先做快取**（`bdc355f`：套用 6.06 s → 0.03 s，§6），**預覽仍約 6.7 秒，列 P7**（工程師 2026-11-03） |
| U4 | 不讀 JPEG EXIF 方向 | 手機直拍照片替換後可能橫躺（預覽可見） | **只提示、不轉正**（工程師 2026-11-03；`bdc355f`，計畫附警告） |
| U5 | G5 的介面流程只有 offscreen 證據；圖片對話框與實機操作 NOT RUN | 實機行為未驗證 | **不擋 P5，併入 P8 實機驗收**（工程師 2026-11-03；§7） |

## 10. 關卡結果

- **關卡結果：BLOCKED**。G5-01～G5-07 本機全部通過，反向驗證 16 項全部被抓到；run [41609744423](https://github.com/TGHAPPLICATION/PEditor/actions/runs/41609744423)（commit `a1fca9d`）windows-latest 406 passed、macos-15 406 passed；U1–U5 已由工程師決定並處理（§9）；已經第一輪獨立核對（§11），N1–N7 已處理；待工程師審查決定關卡結果。
- **下一段可開始：否**（條件：工程師決定並更新本節）。

## 11. 獨立核對紀錄

第一輪（2026-11-03，HEAD `86d47bf`，範圍 `81d51d5..86d47bf`）：未參與實作的 Claude 子代理人核對（暫時腳本放在 repo 外，工作區乾淨）。
自行驗證屬實：I01–I07 只有選定的 `Do` 改名，I02 第 2 頁與 I03 的 `/fzImg0` 仍指向原圖（raw 雜湊相同），未再使用的原圖從輸出移除，外框誤差 0；
自建樣本（同名同頁兩次且資源跨頁共用、圖片在第 2 個 content stream、同一 stream 列兩次、EXIF 方向 6／8、半透明 PNG 補邊）行為正確；
像素與大小上限在解碼前檢查；測試數 404（P5 新增 44）；反向驗證以 monkeypatch 抽驗 M1、M2、M3、M10、M12，報告列的失敗測試都在其中；
證據包重產除輸出雜湊外一致；`uv.lock`、`pyproject.toml` 未改，P4 測試預期未改，錯誤訊息不含路徑；§9 U1–U5 與工程師決定一致；
ruff 通過、pytest 404 passed；CI run 41593863258（`cfee71a`）、41594346667（`11cb4c7`）雙平台 398 passed，41607137231（`86d47bf`）雙平台 404 passed。
結論「有出入」（無 must-fix）：

| # | 內容 | 處理 |
| --- | --- | --- |
| N1（should-fix） | `image.py` 判斷可否移除原名稱時只看頁面層級的 `Do`；沒有自己 /Resources 的 Form（沿用頁面資源）內部用同名畫原圖時，替換頁面層級那次仍移除原名稱，Form 內的圖消失（自建樣本重現：計畫 ready、套用成功，另存被 `visual_outside_mask` 擋下） | 工程師決定全部照建議處理（2026-11-03）。修正（`a584ca8`）：同頁任何同名使用（含 Form 內）都保留原名稱；測試 `test_form_sharing_page_resources_keeps_original`（反向驗證 M14）；ADR-0022 §4、THREAT_MODEL T11 補寫移除條件 |
| N2（should-fix） | §10 寫「反向驗證 11 項」，§4 表為 M1–M13 共 13 項 | §10 改為實際項數（現為 M1–M16 共 16 項） |
| N3（should-fix） | 報告 §1／§3／§4／§10 與 traceability G5 的 CI 證據引用 run 41593863258（`cfee71a`，398 passed），不涵蓋 `bdc355f` 的程式與 6 項新測試 | 改引用處理後最新 commit 的 CI run（§3、§4、§10、traceability）；舊 run 只作歷史紀錄 |
| N4（should-fix，小） | §1 commit 清單缺 `cfee71a`、`11cb4c7`、`86d47bf` | §1 補 `cfee71a`（含證據產生腳本）與 `a584ca8`；只改報告的 commit 依 P4 慣例不列並註明 |
| N5（備查） | `summary.json` 的 `output_sha256` 因 trailer `/ID` 隨機，每次重產不同 | §5 註明 |
| N6（備查） | `test_image_service.py` docstring 寫草稿新圖檔 0600，但沒有權限斷言 | `a584ca8`：`test_image_draft_recovery` 加權限斷言（非 Windows 才檢查，同 `test_drafts.py`） |
| N7（備查） | (a) 過期草稿 purge 只刪 JSON，對應 `.img` 要到下一輪 purge 才刪；(b) `register_asset` 未知參數直接忽略，未走白名單 | `a584ca8`：(a) purge 刪逾期草稿時改呼叫 `discard`，連新圖檔一起刪，測試 `test_expired_draft_purges_its_images`（M15）；(b) `register_asset` 只收 data、keep，測試加一例（M16） |
