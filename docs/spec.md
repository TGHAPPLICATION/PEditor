# 離線桌面 PDF 編輯器：Claude 分段開發規格與測試標準
版本：1.1（v1.0 原文 + 繁體校正 + 附錄 A 修訂）｜日期：2026-10-12｜交付對象：開發者、Claude Code、人工驗收者

## 1. 任務基線與完成定義
目標：反覆修改既有繁體中文 PDF 的文字、圖片與既有表格儲存格，另存為可由一般 PDF 閱讀器開啟的 PDF。
背景：Windows 11、macOS；每台電腦獨立離線執行；允許公開原始碼，優先零授權費元件；不建置帳號、伺服器或多人協作。
開發工具以 Claude Code 為假設；若使用 Claude 網頁版，仍須由開發者在兩種 OS 執行建置與測試。
產品執行不依賴 Claude、LLM API、網路、遠端字型或遠端授權。使用 Claude 開發通常需要連線，與產品離線能力分開驗收。
只將合成或經人工確認可提供的測試資料交給雲端開發工具，不能因產品離線而假設開發資料也不會送出。

輸出：原始碼、鎖定相依版本、測試樣本與預期結果、逐段測試報告、Windows/macOS 安裝包、使用與限制說明、授權清單。
MVP 完成：全部硬性安全／資料完整性測試通過；宣告支援的每個案例通過；Windows 與 macOS 都有實機紀錄；未支援檔案明確阻擋且原檔不變。
需要人工確認：產品支援範圍縮減、替代字型造成版面改變、簽章文件處理、對外發布與授權核對。
一般改錯、補測試、重跑失敗測試不需逐次請示；未通過關卡不能宣稱完成或進入依賴該能力的階段。

## 2. 最低成本技術基線
| 層級 | 選型 | 用途與限制 |
|---|---|---|
| 語言 | Python，同一個雙平台支援版本 | 第 0 段鎖版，不隨意追最新版 |
| 桌面 UI | PySide6／Qt Widgets | 原生桌面操作，減少 WebView、HTTP 服務及多語言維護 |
| 預覽、文字幾何、字型資訊 | PyMuPDF／MuPDF | 可擷取與渲染；不能把擷取出的 span 當成可直接寫回的文字物件 |
| PDF 物件與 content stream | pikepdf／qpdf | 操作字型資源、內容運算子、共享物件與完整另存；不是完整排版引擎 |
| 繁中字型 | Noto Sans CJK TC 或 Source Han Sans TC | 包裝具合法嵌入／散布授權的字型；不任意散布 Windows/macOS 系統字型 |
| 測試 | pytest、pytest-qt、qpdf 檢查、第二套 PDF 解譯器 | 文字、結構、GUI、雙引擎視覺比對 |
| 打包 | PyInstaller，依平台各自建置 | 不宣稱可從單一 OS 跨平台產出全部安裝包 |

PyMuPDF／MuPDF 提供 AGPL 與商業授權。建議此專案先評估採 AGPL-3.0，遵守相依元件、Qt 模組、打包與字型各自授權；公開原始碼本身不是全部授權義務。第 0 段產出 LICENSE、THIRD_PARTY_NOTICES 與 SBOM 草案，正式散布前再由負責人確認。
本規劃是降低工程複雜度的選型建議，並非已完成的相容性／授權鑑定。

架構：Qt UI → DocumentService → EditPlanner → 隔離的 PDF worker → Validator → ExportService。
UI 不直接拼接 PDF 指令；工作程序用受控 stdin/stdout IPC，不開 localhost HTTP。
worker 隔離故障不等於 OS 沙箱。第 7 段另驗證 OS 權限限制與可做到的隔離程度。

## 3. 編輯語義：禁止假完成
A. 原內容運算子修改：定位 content stream 中的 Tj／TJ、文字狀態與字型資源，改寫指定文字的編碼與位移；必要時更新字型映射。不能以搜尋原始位元組或全檔字串取代代替解析。
B. 移除後重建：確實刪除目標文字顯示運算子或對應字形，再建立新文字內容；允許重用／新增合法嵌入字型，必須明示字型替換與排版變化。
C. 覆蓋：白色矩形、FreeText 註解、只加新文字、整頁點陣化後重新包成 PDF，都不能算 A／B。

本 MVP 可接受 A 與 B，但優先驗證 A；B 必須仍保留周圍文字與向量內容。若使用者要求「保持原字型與物件，只修改原運算子」，只有 A 算通過，需在第 0 段選定嚴格模式。
PyMuPDF 的 redaction 是區域移除工具，會有誤傷重疊字形或圖形的風險；不能直接當作精準編輯 API。必須顯式設定圖片／圖形處理方式，通過非目標內容檢查才可作 B 的受限實作。

## 4. MVP 支援矩陣
| 類型 | MVP 行為 |
|---|---|
| 橫排繁中、英數、標點，文字映射可靠 | 支援固定區域替換、同長／短字串、區域內可容納的長字串 |
| 原字型子集沒有新字 | 以已包裝繁中字型重建並預覽；不可默默顯示方框 |
| 既有 JPEG／PNG 類 Image XObject | 支援替換選定出現位置；共享圖片須複製資源避免連帶改動 |
| 規則矩形表格 | 修改人工確認的既有儲存格文字，線條與其他儲存格不變 |
| 掃描 PDF、向量輪廓文字 | 唯讀並提示；OCR 不納入直接編輯驗收 |
| 直排、任意旋轉、Type3、複雜剪裁、巢狀共享 Form | 初版偵測並阻擋該物件編輯；仍可安全預覽 |
| 無可靠 ToUnicode／無法逆向映射 | 不承諾可編輯，需理由碼；不能猜測替換 |
| 數位簽章、加密、PDF/A、XFA、複雜可及性標記 | 初版偵測後編輯阻擋或唯讀；不宣稱保留合規或簽章 |
| 表格插刪列、合併儲存格、自動跨頁重排 | 不納入 MVP |

表格通常由文字與線條組成，不保證有可編輯的原生「表格物件」。MVP 的完成範圍是固定格內改字，不等同 Word／Excel 表格編輯器。

## 5. 可追溯文件與測試資料
建議 repo 目錄：
- CLAUDE.md：共同開發規則與禁止事項。
- docs/spec.md：需求與支援矩陣。
- docs/adr/：架構、編輯語義、字型、儲存及授權決策。
- src/ui/、src/core/、src/worker/、src/export/。
- tests/unit/、tests/integration/、tests/gui/、tests/security/。
- tests/fixtures/：合成 PDF、產生腳本、字型授權及 fixture manifest。
- reports/P0/ 到 reports/P8/：命令、環境、測試結果、證據。
- packaging/：各平台打包與離線安裝說明。

固定 60 份測試 PDF，避免全部用同一引擎產生：
| 群組 | 數量 | 內容 |
|---|---:|---|
| T 基礎文字 | 12 | 繁中英數混排、全形標點、同字數／較短／較長替換 |
| F 字型與編碼 | 10 | 子集字型、新字、缺字、CID、缺映射、不同產生器 |
| L 幾何與背景 | 8 | CropBox、頁面旋轉、密集鄰字、彩底、透明背景 |
| I 圖片 | 8 | 獨立圖片、跨頁共享、多次出現、透明遮罩、背景重疊 |
| B 表格 | 8 | 規則表格、多行格、邊線、相鄰格、應拒絕的複雜格 |
| U 特殊文件 | 6 | 掃描、輪廓文字、簽章、加密、PDF/A、XFA |
| S 損毀與惡意 | 8 | 畸形內容、解壓膨脹、深層巢狀、JavaScript、附件等 |

每份 manifest：fixture_id、SHA-256、產生器與版本、字型、支援／拒絕預期、page_index、目標 object／操作位置、bbox、原文、新文、可改動區域、不可改動區域、預期理由碼。
精確哪些 case 可編輯必須在 P2 前鎖定；另保留至少 12 份未用於實作調整的盲測，防止只針對 golden fixture 通過。
樣本涵蓋：臺、灣、醫、衛、龜、𠮷等。部分字型不含特殊字時，預期為明確拒絕或事先指定且已驗證的替代字型，不容許假字形。

## 6. 分段開發：每段是獨立交付與關卡

### P0：規格、環境與資料集（2–4 人日）
輸入：本文件、兩平台可用環境、授權選擇。
工作：建立 repo／依賴 lock／最小測試流程、60 份 fixture manifest、至少 20 份可重現首批樣本、支援矩陣、ADR；先探查兩平台打包最小 Qt app，避免最後才發現原生依賴問題。
輸出：可安裝開發環境、空白桌面 app、資料集腳本、追溯表。
驗收 G0：Windows 11 x64 與 macOS Apple Silicon 均啟動；fixture hash 可驗證；沒有正式 PDF；指定每個需求的 test ID；嚴格 A 或允許 A/B 已記錄。
停止：授權選擇衝突、~~沒有 macOS 實機可驗證~~ **P3 結束時仍無 macOS 實機取得方案**（v1.1 修訂，ADR-0003）、需求仍要求任意 PDF 無差別完美修改。

### P1：只讀分析器與能力判定（4–6 人日）
工作：開檔、逐頁渲染、文字／字形 bbox、font／xref 資訊、頁面幾何、圖片出現位置；建立 capability report；parser 在 worker 執行。
API：open_document、inspect_page、assess_editability。
輸出：CLI JSON 分析報告與頁面 PNG；此段 UI 可極簡。
驗收 G1：所有 60 份分析或受控拒絕，不崩潰；可編輯／不可編輯符合預定清單；座標 round-trip 誤差 ≤0.5 pt；100／200% 縮放與 0／90／180／270° 頁面旋轉命中正確位置。
停止：無法將擷取字形可靠對應到可修改 content stream；單純有 bbox 不能視為已定位。

### P2：真正文字修改 CLI POC（8–15 人日；最高風險）
工作：解析支援子集內的文字狀態、Tj／TJ、資源、編碼及位移；產出 EditPlan；先只做單一橫排文字 run，逐步到跨多個 run 的固定框。
處理原字型可用字、新字型資源、Unicode 映射、不同字寬、背景保留；替換新字超框一律拒絕，不偷偷縮字。
輸出：edit_text CLI、原／新 PDF、解碼內容差異、雙引擎擷取與渲染報告。
驗收 G2：
1. 所有宣告支援的文字案例 100% 通過，至少包含 20 次操作、3 種 PDF 產生來源、2 種繁中字型。
2. 指定目標 occurrence 的舊字形顯示內容移除，新文可搜尋、複製，Unicode 精確相符。
3. 密集鄰字、背景、線條不被修改；不能靠白底覆蓋。
4. 不支援、缺字、溢出回傳理由碼，磁碟與工作文件均不變。
5. 同原字型模式不可偷偷更換字型；B 模式需證據表明先移除舊內容。
停止：只有紅框／新圖層／點陣化、只有單一生成器成功、第二引擎擷取失敗、宣稱成功但原文仍在指定內容。

### P3：儲存交易、撤銷與復原（4–6 人日）
工作：原檔唯讀；每次操作基於版本及影像雜湊；以 command log／快照支援至少 50 次 undo/redo；預設另存；完整重寫輸出，不採增量附加。
儲存：同目錄臨時檔 → flush → 結構／文字／視覺驗證 → 原子 rename；檢查目的檔已有變動與來源 hash；空間不足時不破壞已有目的檔。
驗收 G3：50 操作撤銷重做結果等價；儲存重開後目標正確；在寫入、驗證、rename 前注入中斷，原檔／既有目的檔完整；100 次另存循環無資料毀損；損壞與外部修改回傳明確錯誤。
復原草稿必須由使用者選擇開啟，包含敏感內容的暫存不可長期無限制保留。

### P4：桌面文字編輯流程（6–10 人日）
工作：開檔、縮圖、預覽、點選文字、替換輸入、模式／字型／溢出提示、前後對照、undo/redo、另存、進度與取消。
繁中 UI／IME；鍵盤 Ctrl 與 Cmd；worker 不阻塞 UI。
驗收 G4：每平台至少 12 個 E2E 流程；IME 組字中不提前送出；中文字型與中文路徑／空白檔名／emoji 路徑；取消不提交；不可編輯物件有原因。
禁止用完整頁面 DOM 或 HTML 匯出假裝完成原 PDF 編輯。

### P5：圖片替換（4–7 人日）
工作：單次圖片 invocation 定位、資源 clone-on-write、維持變換矩陣／裁切／透明度；支援 PNG/JPEG；預設維持外框比例，替換前檢查像素上限。
驗收 G5：全部宣告支援 I 案例；同一 xref 在同頁及跨頁重用時，只改選定 occurrence；其他頁視覺不變；保持原外框 ≤0.5 pt；拒絕非支援遮罩／剪裁。
直接 replace_image(xref) 是全文件資源替換，不可當成單次位置替換。

### P6：既有規則表格儲存格修改（5–9 人日）
工作：以文字及線條推估表格／人工確認框；固定框內編輯；複用 P2；同格多行需明確 line layout；移除舊內容但保留邊線。
驗收 G6：全部宣告支援 B 案例；邊線幾何／筆畫寬不變、其他格擷取文字及視覺不變；溢出阻擋；無法辨識的格可人工選定但仍需能力判定。
不實作列插刪、合併、跨頁重排，也不將匯出 Excel 當作直接修改 PDF。

### P7：離線與安全強化（5–8 人日）
工作：所有 PDF 視為不可信輸入；不執行 JavaScript、Launch、嵌入檔；不自動開外部連結；worker 限制時間／輸出／記憶體，限制深度、頁數、檔案／像素大小；崩潰後可重啟。
不啟用 telemetry、遠端字型、自動更新、外部內容下載；記錄不含原文、密碼或完整使用者路徑。
OS 保護：在 Windows/macOS 分別評估沙箱／權限機制；最低必須有獨立程序、限制 IPC、路徑白名單與作業系統出站封鎖驗證。Python API 不足以證明完整 OS 沙箱，報告須明列缺口。
驗收 G7：斷網完整開／編／存；監測 app 與全部子程序零非 loopback 出站嘗試，並且本架構沒有 HTTP listener；惡意樣本不啟動外部程式／連線；worker 逾時可停止；日誌不洩漏測試敏感 sentinel。
限制參數初值：檔案 200 MB、500 頁、單張影像 50 MP、單操作 30 秒、worker 2 GB。以上是產品政策待實測值，不是程式庫保證；超限受控拒絕。載入前／解析中都要限制，不能先完整解壓才檢查。
P7 是安全強化關卡；P1 起即需基本程序隔離、取消、資料限制與不執行主動內容，不把全部安全工作拖到末段。

### P8：打包、實機與發布候選（4–7 人日）
工作：Windows 原生建置安裝包；macOS Apple Silicon 原生建置 app／DMG；全部依賴、字型、資源本地包裝；標明 macOS 最低支援版本。
Intel Mac 若有部署需求，再加獨立打包與完整實機測試，不預設已有支援。
驗收 G8：乾淨 VM／實機無 Python、無網路可安裝與完成核心流程；兩種 PDF 閱讀器正常開啟；完整支援矩陣 100%；60 fixture 與 12 盲測結果；已知缺陷清單、SBOM、LICENSE、相依來源與版本、卸載／草稿清理說明。
正式散布 Windows 簽章及 macOS Developer ID／notarization 另行核價；內部 POC 可人工信任，但不能將未簽署測試包標成正式部署完成。

## 7. 核心 API 合約
使用內部 Python typed API／JSON IPC；不建立對外 REST。
每個請求：request_id、protocol_version、document_id、expected_revision、operation。每份文件串行修改；預覽可取消；不傳任意 shell 指令／任意系統檔案路徑。

- open_document(path) → document_id、revision、sha256、page_count、document_flags。
- inspect_page(document_id, page_index) → page_geometry、text_targets、image_targets、capabilities。
- plan_text_edit(document_id, target_id, new_text, policy, expected_revision) → EditPlan。
- plan_image_edit(document_id, target_id, local_asset_id, expected_revision) → EditPlan。
- plan_cell_edit(document_id, cell_id, new_text, expected_revision) → EditPlan。
- preview_edit(plan_id) → before／after、affected_regions、font_changes、warnings。
- apply_edit(plan_id, expected_revision) → new_revision、command_id。
- undo／redo(document_id, expected_revision) → new_revision。
- export_document(document_id, destination_token, expected_revision) → output_hash、validation_report。
- cancel(request_id)、close_document(document_id)。

target_id 不能只是 bbox 或 xref；必須包含 document revision、page_index、content stream identity、operator span／occurrence、Form path（支援時）、geometry hash。xref 不跨儲存版本視為永久 ID。
EditPlan：mode A/B、preconditions、target、resource_changes、allowed_change_mask、new_text、font_policy、geometry、unsupported_reasons；禁止由 UI 任意發入原始 PDF 指令。
幾何：點 pt=1/72 inch；儲存格式明示原點、CropBox、頁面旋轉、矩陣；UI 座標與 PDF 座標在單一模組轉換。
錯誤碼：UNSUPPORTED_ENCODING、UNSUPPORTED_LAYOUT、GLYPH_MISSING、TEXT_OVERFLOW、SHARED_RESOURCE_UNSAFE、SIGNED_DOCUMENT、ENCRYPTED_DOCUMENT、REVISION_CONFLICT、RESOURCE_LIMIT、VALIDATION_FAILED、SAVE_FAILED、CANCELLED。
失敗：不更新 revision、不落地部分輸出、不回傳虛假的 success；錯誤包含可讀說明與是否可重試。

## 8. 共通測試標準
### 8.1 真正修改證據
每次文字替換同時交付：
1. 解碼與解析後的內容／資源差異，證明特定 occurrence 原文字運算子或對應字形已移除或改寫。
2. PyMuPDF 與第二套解譯器（如 Poppler）分別擷取結果，新文 Unicode 正確；從指定區域／目標移除舊文。
3. 雙引擎原／新渲染比對，背景、鄰字、線條保留；輸出可搜尋與選取。
4. 完整另存、清除不可達物件，確認沒有增量歷史保留被修改的舊目標。

不能只用「舊字串全檔搜尋不到」驗收：中文字可能編碼／壓縮，同字串也可能在別頁合法存在。
若原文在未修改位置仍存在，應保留；只判定目標 occurrence。字型內含舊字形不代表舊文字仍在；可到達的原顯示內容與不可達歷史需區分。
PDF metadata、附件、註解等其他位置可能仍有相同文字；本編輯器不是保證全文件不可復原的機密抹除工具。不得把這套測試宣稱為鑑識級遮蔽驗證。
若支援 tagged PDF，另驗證 ActualText／結構樹；MVP 未支援時阻擋，不能只更新畫面。

### 8.2 視覺與結構
- qpdf 結構檢查無新增錯誤；fixture 原有 warning 在 manifest 記錄，不能新增 warning。
- 固定各平台引擎與字型版本、150 DPI、相同色彩參數；同引擎原／新比對，不直接要求不同引擎像素一樣。
- 未修改頁：同引擎像素完全相同；若字型／渲染導致不確定差異，必須查明不能擴大遮罩掩蓋。
- 已修改頁：事前宣告的改動區域加 2 pt 邊界以外，每通道差異 >8/255 的像素 ≤0.01%；同時全部非目標文字內容與幾何不變。
- 遮罩不能包含其他儲存格或整頁；由預先 manifest／EditPlan 決定，不能看完 diff 才調整。
- 目標外框定位誤差 ≤0.5 pt；線條物件幾何與樣式不變。字型替換的視覺差異只限目標區域，需人工確認。
- 門檻在 P0/P2 用基準實測後鎖定；如需修改須寫 ADR，不能為通過個別測試偷偷放寬。

### 8.3 效能與穩定
暫定基準：Windows 11 4 核／16 GB／SSD；Apple Silicon Mac／16 GB；固定本地 100 頁、50 MB 樣本。
首次可互動預覽 p95 ≤3 秒；單頁替換預覽 p95 ≤2 秒；上述樣本完整另存 p95 ≤15 秒；UI 操作回應 ≤100 ms。
各平台至少 20 次測量，記錄冷／暖啟動、CPU、記憶體、PDF hash；不將上限 500 頁當成已保證同一速度。
50 次操作循環，worker 峰值 ≤2 GB；無持續單調成長的資源洩漏；長操作可取消。
以上是產品目標而非已測結果，P2 決定是否調整或收縮規模。

### 8.4 放行規則
硬性項目：原檔安全、真修改證據、拒絕行為、字型正確、無鄰區損害、離線、兩平台核心流程，必須全過。
宣告支援 case pass rate=100%；整體 60 fixture 成功編輯率不作指標，因其中故意包含應拒絕案例。
錯誤標成可編輯率=0%；盲測如出現誤判，回到能力判定或縮小支援矩陣，再全部回歸。
覆蓋率僅輔助：core 分支覆蓋目標 85%，不能以數字取代真修改、安全與實機證據。
本機未安裝的 OS／工具：標示 NOT RUN，不得以推測填 PASS。

## 9. 交給 Claude 的共同提示詞
將以下內容放入專案開發指示（這是專案規範，不要求安裝新 Skill）：

「你是此專案的實作者。先讀 docs/spec.md、ADR、fixture manifest 與上一段測試報告。本次只完成指定 Px。
S1 確認輸入、現有程式與平台；S2 列需求對應 test ID 及修改檔案；S3 先實作最小可測版本；S4 執行單元／整合／回歸與需要的 GUI 測試；S5 回報不確定性及 NOT RUN。
禁止用白框、註解覆蓋、整頁點陣化冒充原內容編輯；禁止改測試預期掩蓋失敗；禁止未核對的套件 API、放寬支援範圍、把抽取 bbox 當成內容定位。
不得自動上傳 PDF、安裝 telemetry、加入線上服務。依賴版本需鎖定，API 查官方文件。
每段輸出：變更摘要、逐條驗收結果、實際命令與 exit code、環境版本、fixture hash、差異證據、限制、下段前提。
有錯誤先修復並回歸；涉及核心語義、授權或支援範圍改變時提出 ADR 待人工確認。未完成就標示 BLOCKED，不寫已完成。」

### 逐段可複製啟動指令
P0：「完成 P0。建立規格、ADR、60 fixture manifest 和首批 20 份合成 PDF；鎖定依賴，兩平台 smoke build。不要實作編輯核心。交付 G0 證據。」
P1：「以 G0 為前提完成只讀分析器與 capability report；建立字形到 content stream 的支援子集定位。每份 PDF 回傳支援能力或理由碼，完成 G1。」
P2：「先用 CLI 完成單一繁中 run 的模式 A 真修改，再驗證模式 B 是否必要。完整另存。逐案交付內容運算子差異、雙引擎擷取與視覺差異，完成 G2 前不要擴寫 UI。」
P3：「在 G2 引擎上加入版本衝突檢查、transaction、完整另存、undo/redo 及 crash injection，證明原檔與已有目的檔不會損壞。」
P4：「只包裝已驗證 API，完成 Qt 繁中 IME、點選、前後預覽、取消及另存流程。補兩平台 E2E；不得讓 UI 私自改 PDF。」
P5：「完成單次圖片 occurrence 替換；共享 XObject 必須 copy-on-write，跨頁／同頁其他 occurrence 不變。完成 G5。」
P6：「完成規則表格既有儲存格改字，人工確認格界線，沿用 P2。保持邊線與相鄰格，溢出拒絕，完成 G6。」
P7：「完成安全強化與 OS 限制驗證，測試惡意 PDF、資源限制、零出站、日誌與暫存；明列程序隔離與真正沙箱的差距。」
P8：「在各 OS 原生打包；乾淨離線環境執行完整驗收及盲測。交付安裝包、hash、SBOM、限制、實測報告，未執行不填 PASS。」

## 10. 工期與節省成本順序
估計為有 PDF 經驗的單一工程師搭配 Claude 的工程投入，不是 Claude 自動產碼時間：
P0 2–4、P1 4–6、P2 8–15、P3 4–6、P4 6–10、P5 4–7、P6 5–9、P7 5–8、P8 4–7 人日，合計 42–72 人日；再保留 20–30% 風險緩衝，約 50–94 人日。
POC P0–P2：14–25 人日；先設定此預算上限，G2 失敗時決定收縮支援範圍或停止，避免先投入華麗 UI。
最低可用文字版：P0–P4，但只能作受控內部試用；對外／正式部署仍須 P7–P8。
完整 MVP：全部階段。先文字後圖片再固定表格，不做 OCR、帳號／同步、AI 自動改寫或 Word 級重排。
零套件授權費不等於零成本：人工驗收、Mac 測試機、Claude 使用費、平台簽章與維運另列。
維運：鎖定版本、固定 fixture 回歸、定期檢視解析器安全更新；離線手動發佈有簽章／hash 的升級包，不建置常駐後端。

## 11. 測試報告範本
階段／commit／日期：
OS、架構、硬體、Python／套件／字型版本：
需求 ID → test ID → fixture ID／hash → PASS／FAIL／NOT RUN：
執行命令、exit code、測試數：
真修改證據路徑、抽取結果、視覺差異：
資料完整性與資源／出站紀錄：
限制、阻擋、未測項目：
人工確認項目：
關卡結果：PASS／BLOCKED；下一段可開始：是／否。

## 12. 技能與官方技術參考
已查閱使用者指定來源：
- Anthropic Skills：https://github.com/anthropics/skills
- PDF skill：https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md
  用於理解 PDF 擷取與工具流程；不是已完成的原內容編輯引擎。repo 說明指出部分文件技能為 source-available，不可一概視為開源授權。本次不複製其程式進入產品。
- Microsoft SkillOpt：https://github.com/microsoft/SkillOpt
  是技能最佳化與驗證框架；初版不加入，採用明確關卡與保留盲測即足以開始。

官方 API／授權參考（實作時以鎖定版本為準）：
- https://pymupdf.readthedocs.io/en/latest/page.html
- https://pymupdf.readthedocs.io/en/latest/about.html
- https://pikepdf.readthedocs.io/en/latest/topics/content_streams.html
- https://pikepdf.readthedocs.io/en/latest/topics/streams.html
- https://doc.qt.io/qtforpython-6/licenses.html

本文件為規格與規劃；未執行任何 PDF 編輯 POC，未保證以上元件組合已能通過 G2。完成能力必須以後續實測證據認定。


---

## 附錄 A：v1.1 修訂與決策回填

v1.1 不改變 v1.0 的需求與驗收門檻；只做繁體校正、回填已確認決策，並記錄需人工確認的補充。

| # | 修訂 | 狀態 | 依據 |
|---|---|---|---|
| A1 | 簡體字校正為繁體（換、確、圖、預、數、單、內、應、並、與、會、規、則、為、約、階、於；泄漏→洩漏、坐標→座標） | 已完成 | 執行計畫書 v1.1 |
| A2 | §3 編輯語義：**允許 A/B，優先 A**（非嚴格 A 模式）；B 須證明先移除舊內容（G2 第 5 點） | 已確認 | ADR-0001 |
| A3 | §2 授權：AGPL-3.0，repo 已公開（TGHAPPLICATION/PEditor） | 已確認 | ADR-0002 |
| A4 | §6 P0 停止條件：「沒有 macOS 實機可驗證」改為「P3 結束時仍無 macOS 實機取得方案」；G0 的 macOS 啟動以 CI（macos-15 arm64）證據達成，實機項目標 NOT RUN，G4、G7、G8 仍須實機 | **待人工確認** | ADR-0003 |
| A5 | §2 架構落地為 `src/peditor/{ui,core,worker,export}`（§5 的 `src/ui/` 等對應為同名子套件，以便打包與匯入） | 已實作 | ADR-0004 |
| A6 | §2／§8.1 第二套解譯器採 **PDFium（pypdfium2）**，結構檢查採 **qpdf（經 pikepdf `check_pdf_syntax`）**；Poppler 因 Windows 安裝與維運成本高不列為必要 | **待人工確認** | ADR-0006 |
| A7 | §7 錯誤碼補充 capability／拒絕用理由碼：`NO_TEXT_LAYER`、`MALFORMED_DOCUMENT`、`ACTIVE_CONTENT`、`UNSUPPORTED_FEATURE` | **待人工確認** | ADR-0007 |
| A8 | §2 繁中字型：模式 B 與 fixture 採 Noto Sans TC（Noto Sans CJK TC 子集 OTF）與 Noto Serif TC，均 OFL-1.1；來源鎖定 commit 與 SHA-256 | **待人工確認** | ADR-0008 |
| A9 | §5 fixture 編號採「群組字母 + 序號」（T01–T12、F01–F10、L01–L08、I01–I08、B01–B08、U01–U06、S01–S08）；盲測 12 份離線保管 | 已實作 | tests/fixtures/manifest.csv |
| A10 | §5 報告目錄採 `reports/P0/` … `reports/P8/`，每段 `report.md` 依 §11 範本 | 已實作 | reports/TEMPLATE.md |
