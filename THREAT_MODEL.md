# Threat Model: PEditor

## 1. System context

PEditor 是在 Windows x64 與 macOS arm64 上執行的離線桌面 PDF 文字編輯器，供機關承辦人修改既有 PDF 內文字（含繁體中文子集字型）並保留排版。以 Python 3.13 + PySide6（Qt 6）實作 UI，PDF 解析與改寫使用 PyMuPDF（MuPDF，C）與 pikepdf（qpdf，C++）。產品不需也不應有任何網路連線。

使用者開啟的 PDF 來源不受控（公文附件、外部來函、下載檔），因此 PDF 一律視為不可信輸入。依 ADR-0004，解析在獨立 worker 子行程進行，主行程只處理 worker 回傳的結構化資料；儲存以暫存檔 + 原子取代完成。產品以 AGPL-3.0 開源，GitHub repo 與 CI 日誌公開。

P0 時點只有空白 UI、fixture 產生器與 CI。P1（2026-10-21）實作 worker 子行程、JSON Lines IPC 與只讀分析器。

P2（2026-10-27，分支 `p2-text-edit`）加入文字編輯與另存，仍只有 CLI（`peditor edit-text`），尚無編輯 UI：
- worker 新增 `find_text`、`plan_text_edit`、`apply_edit`、`export_document` 四個操作；編輯直接改寫 worker 記憶體中的工作文件（content stream、字型資源、標記 PDF 的 /ActualText）。
- **另存由 worker 直接寫入呼叫端指定的路徑**（`src/peditor/worker/export.py`）：先完整重寫並驗證（無增量歷史、無不可達物件、qpdf 問題數不增、MuPDF 不需修復、頁數不變），通過後以 `open(..., "xb")` 寫入並 fsync；目的檔已存在即拒絕。P2 沒有覆寫原檔、暫存檔或原子取代，這些屬 P3 儲存交易。
- 模式 B 以 Noto Sans TC 重建新文字：字型檔從環境變數 `PEDITOR_MODE_B_FONT` 或套件內 `resources/fonts/` 讀取，並驗證 SHA-256（ADR-0008、ADR-0018）。
- CLI 在輸出資料夾另寫 `plan.json`（EditPlan）與 `validation.json`（含內容差異），兩者含被替換的原文。

P3（2026-10-29，分支 `p3-transaction`，ADR-0020）加入儲存交易、undo／redo 與復原草稿：
- 另存改用 `destination_token`：主行程解析實際路徑並記錄目的檔狀態；worker 只把驗證過的內容寫入主行程指定的同目錄暫存檔，主行程比對 hash、確認原檔與目的檔未被修改後原子取代（`src/peditor/export/transaction.py`）。原檔永遠不被覆寫。
- command log 在主行程；undo、redo 與 worker 重啟後的還原都由 worker 從原始位元組重播。
- 復原草稿（command log，含新文字）存在使用者本機資料目錄，保留 7 天。

本模型於 P7 再依實作更新。

## 2. Assets

| asset | description | sensitivity |
|---|---|---|
| 使用者文件內容 | 開啟與編輯中的 PDF 文字與影像，可能含公文、個資 | high |
| 原始檔完整性 | 使用者磁碟上的原 PDF；儲存失敗不得毀損 | high |
| 編輯正確性 | 改後文件只含使用者預期的變更，舊文字不殘留（模式 B） | high |
| 使用者主機 | 執行 PEditor 的使用者帳號權限與其他檔案 | critical |
| 離線保證 | 產品不產生任何出站連線 | high |
| 發佈產物 | 安裝包／離線升級包及其 hash | high |
| 原始碼與 CI | 公開 GitHub repo、Actions 工作流程 | medium |

## 3. Entry points & trust boundaries

| entry_point | description | trust_boundary | reachable_assets |
|---|---|---|---|
| 開啟 PDF 檔 | 使用者選取任意 PDF，交由 worker 以 MuPDF／qpdf 解析 | 不可信檔案 → worker 行程記憶體 | 使用者主機, 使用者文件內容 |
| worker → 主行程 IPC | worker 回傳 JSON Lines（文字框、點陣圖、capability report） | worker（可能已被攻陷）→ UI 主行程 | 使用者主機, 使用者文件內容, 原始檔完整性 |
| 編輯請求 | 使用者輸入搜尋文字、新文字、頁碼、occurrence、可改動區域；worker 依不可信 PDF 的字型與 ToUnicode 產生 EditPlan 並套用（P2） | 使用者輸入＋不可信檔案 → worker 工作文件 | 編輯正確性, 使用者文件內容 |
| 儲存 | P3：worker 驗證後寫入主行程指定的同目錄暫存檔；主行程比對 hash、檢查原檔與目的檔後原子取代 | worker 輸出 → 使用者檔案系統 | 原始檔完整性, 編輯正確性 |
| 復原草稿 | 主行程把 command log（含新文字）寫入使用者本機資料目錄；使用者選擇後才讀回重播 | 本機資料目錄 → 主行程 → worker | 使用者文件內容, 編輯正確性 |
| 附屬輸出 | CLI 寫出的 `plan.json`、`validation.json`（含被替換的原文與內容差異） | worker 結果 → 使用者檔案系統 | 使用者文件內容, 編輯正確性 |
| 模式 B 字型檔 | 由環境變數 `PEDITOR_MODE_B_FONT` 或套件資源載入，於 worker 內子集化後嵌入輸出 | 本機檔案 → worker → 輸出 PDF | 編輯正確性, 發佈產物 |
| 檔名與路徑 | 中文、超長、特殊字元路徑；拖放 | 使用者輸入 → 檔案 API | 原始檔完整性 |
| 相依套件與建置 | PyPI wheel、GitHub Actions、PyInstaller | 第三方供應鏈 → 建置產物 | 發佈產物, 使用者主機 |
| 離線升級包 | 手動發佈的升級包與 hash | 傳遞媒介 → 使用者主機 | 發佈產物, 使用者主機 |
| 公開 repo 與 CI 日誌 | fixture、測試輸出、issue | repo 內容 → 公眾 | 使用者文件內容 |

## 4. Threats

| id | threat | actor | surface | asset | impact | likelihood | status | controls | evidence |
|---|---|---|---|---|---|---|---|---|---|
| T1 | 惡意 PDF 經 MuPDF／qpdf 解析造成記憶體破壞並在使用者權限下執行程式碼 | remote_unauth | 開啟 PDF 檔 | 使用者主機, 使用者文件內容 | critical | likely | partially_mitigated | P1：解析只在 worker 子行程（G1-01 測試主行程無 PDF 程式庫）；崩潰／逾時即終止並重啟；worker 以 `python -P` 啟動，不載入工作目錄中的同名模組（P1 安全掃描 f011）。非 OS 沙箱，worker 仍有使用者權限（P7 評估）。Pillow（pikepdf 相依）升至 13.0.0 修補 9 項 Dependabot 警示（ADR-0014）；產品目前不載入 Pillow，日後若在 worker 以 Pillow 解碼使用者影像，須另設大小／像素上限 | MuPDF 與 qpdf 歷年記憶體安全 CVE（P1 vuln-scan 時補 CVE 編號） |
| T2 | 已被攻陷或異常的 worker 透過 IPC 送出畸形訊息，攻陷或癱瘓 UI 主行程 | remote_unauth | worker → 主行程 IPC | 使用者主機, 使用者文件內容 | critical | possible | partially_mitigated | P1：JSON Lines、單則 64 MiB 上限（主行程讀取時即限制）、逾時、畸形回應即重啟；尚未以 schema 驗證回應內容（P7 加 fuzz 與 schema）。P2：主行程直接使用 worker 回傳的 EditPlan 與驗證報告（triage f008，判為誤報：worker 已有使用者權限，可直接寫檔）；P2 起 worker 自行寫出另存檔，被攻陷的 worker 不需經主行程即可寫檔，與 T1 同一風險 | reports/P2/security/TRIAGE.md |
| T6 | 相依套件或 CI action 遭供應鏈攻擊，於建置或執行時植入惡意程式 | supply_chain | 相依套件與建置 | 發佈產物, 使用者主機 | critical | rare | partially_mitigated | uv.lock 雜湊鎖定、exclude-newer 冷卻期、Actions commit SHA 鎖定、contents: read 權限 | |
| T8 | 竄改的安裝包或離線升級包被安裝至使用者主機 | supply_chain | 離線升級包 | 發佈產物, 使用者主機 | critical | rare | unmitigated | 規劃附 hash 發佈；簽章延至正式散布（P8） | |
| T3 | 儲存中斷、崩潰或磁碟滿導致原 PDF 毀損或遺失 | local_user | 儲存 | 原始檔完整性 | high | likely | mitigated | P3（ADR-0020 §3）：原檔永遠不被覆寫（目的檔為任何已開啟文件的原檔即拒絕）；worker 在目的目錄的隨機暫存檔寫入並 fsync，主行程比對 SHA-256、再次確認原檔與目的檔未變，才以 `os.replace` 原子取代；任一步失敗刪除暫存檔、目的檔不動；worker 寫入失敗刪除部分檔（f017 已修）。crash injection：在寫入、驗證、rename 前以 os._exit 中止主行程，原檔與既有目的檔皆完整（G3-03）；100 次另存循環（G3-04）；空間不足以模擬 ENOSPC 驗證（G3-06，真實磁碟填滿未測）。殘餘：中斷留下的暫存檔要等下次寫入同資料夾才清除（P3 triage f011，判為預期設計） | G3-03、G3-04、G3-06、G3-08；ADR-0020 |
| T4 | 模式 B 只覆蓋未移除，舊文字仍可被擷取，造成資訊外洩 | insider | 儲存 | 編輯正確性, 使用者文件內容 | high | possible | partially_mitigated | P2：模式 B 先把原字型的目標字碼自 content stream 移除再以新字型重建，不使用白框或覆蓋（G2-05）；兩引擎擷取確認目標 occurrence 舊文已不存在（G2-02）；標記 PDF 同步 /ActualText，儲存後驗證其值完全等於新文字，不等則復原並回 VALIDATION_FAILED，重複 MCID 拒絕（G2-17，ADR-0017）。殘餘：/ParentTree 與 /K 不一致的結構樹未檢查（f006），舊文可能留在未被 /ParentTree 指到的 /ActualText、/Alt、/E；只處理目標 occurrence，同頁其他相同文字、書籤、註解、中繼資料中的舊文不在範圍（spec §8.1）；附屬輸出含原文見 T13 | G2-02、G2-05、G2-17；reports/P2/report.md §9 U4 |
| T9 | 真實公文、個資或文件原文經 fixture、日誌、錯誤回報進入公開 repo 或 CI 日誌 | insider | 公開 repo 與 CI 日誌 | 使用者文件內容 | high | possible | partially_mitigated | 只放合成 fixture、盲測樣本離線保管、日誌不含原文與路徑（CLAUDE.md） | |
| T7 | 產品或相依於執行時產生出站連線，破壞離線保證或外洩內容 | supply_chain | 相依套件與建置 | 離線保證, 使用者文件內容 | high | rare | partially_mitigated | test_offline_guard 禁止產品碼匯入網路模組；P7 實機零出站監測 | |
| T5 | 惡意 PDF 以資源耗盡（巨大頁數、壓縮炸彈、深層巢狀物件）癱瘓應用程式 | remote_unauth | 開啟 PDF 檔 | 使用者主機 | medium | likely | partially_mitigated | P1：讀檔前檢查檔案大小（200 MB）、開檔後解析頁面前檢查頁數（500）、每請求 30 秒逾時、Form 巢狀深度 8 與循環偵測；P1 安全掃描後另限運算子數、Form 呼叫數、q 深度、clip 數、CMap 大小與展開數、欄位／書籤節點數、渲染像素面積（reports/P1/security/TRIAGE.md）；P2：另存時內容差異比對先去除前後相同運算子，未改動的串流不進入平方級比對（triage f014 已修，G2-22）。未修：`parse_cmap` 對未結束的 bfchar／bfrange 區塊為平方級（f022）、ToUnicode／CIDToGIDMap／字型程式在限制前完整解壓（f024），目前只靠 30 秒逾時，列 P7；記憶體與解壓限制於 P7。P3：另存前視覺驗證的渲染上限 12 MP、遮罩內像素不逐點走訪、超標即停（triage f015 已修，G3-09）；undo／worker 重啟還原以單一請求重播整個 command log，步數多時可能超過 30 秒逾時（f008，判為設計取捨，P4 量測後再議） | reports/P2/security/TRIAGE.md；reports/P3/security/TRIAGE.md |
| T10 | 特製路徑或檔名（路徑穿越、符號連結）使儲存覆寫非預期檔案 | local_user | 檔名與路徑 | 原始檔完整性 | medium | rare | mitigated | P3：另存改用 `destination_token`（spec §7）：主行程以 `realpath` 解析實際路徑（含符號連結）、須為 .pdf 且上層目錄存在；既有檔只在明確 overwrite 時取代；目的檔與已開啟文件的原檔為同一檔（samefile）即拒絕；worker 只收到主行程產生的暫存檔名（G3-05）。殘餘：`overwrite=False` 時最後檢查與 `os.replace` 之間的極短窗口（P3 triage f009，判為理論性 TOCTOU，列 P7）；覆寫後權限／ACL 為暫存檔預設值（f012，列 P7） | G3-05；ADR-0020 §3 |
| T11 | 特製 PDF 使一次編輯改到使用者未選取的內容，或新文字畫到可改動區域外，而變更報告未完整呈現 | remote_unauth | 編輯請求 | 編輯正確性 | medium | possible | partially_mitigated | P2：目標 content stream 被同頁重複、Form XObject、註解外觀或其他頁共用時拒絕（SHARED_RESOURCE_UNSAFE，f002／f012 已修）；模式 A 結尾插入位置與溢出檢查一致（f004 已修）；新文字外框超出可改動區域回 TEXT_OVERFLOW，不縮字（G2-06）；另存時輸出逐運算子內容差異與資源差異（G2-07）。殘餘：模式 A 依 PDF 自帶的 ToUnicode 選字碼，與渲染器實際字形可能不同（f005，判為預期行為）；溢出只檢查基線起訖點，負字寬或 Tc 可使中間字形越界（f011）；ToUnicode 字碼超出字型字碼空間時計畫通過但套用失敗（f023）；模式 B 兩字對到同一字形時 ToUnicode 只保留後者（f018）。P3：套用失敗以開啟自的位元組回滾，revision 與 target_id 不變（f003、R3-1 已修，G3-08）；另存前產品端文字與 MuPDF 視覺驗證（ADR-0020 §4）。殘餘：視覺驗證在 worker 內執行，對被攻陷的 worker 不構成邊界；ADR-0015 的 7 份 MuPDF 渲染空白檔視覺驗證無效；預設遮罩取字形外框，可被嵌入字型放大（P3 triage f013，同 P2 f013） | G2-06、G2-07、G2-22、G3-08；reports/P2/security/TRIAGE.md；reports/P3/security/TRIAGE.md |
| T12 | 以環境變數指向竄改的模式 B 字型檔，使嵌入的字形與字碼不符或觸發 fontTools 解析缺陷 | local_user | 模式 B 字型檔 | 編輯正確性 | low | rare | mitigated | 載入前驗證 SHA-256 必須等於 ADR-0008 鎖定值，不符即視為模式 B 不可用（`src/peditor/worker/fontb.py`）；字型只在 worker 內處理 | ADR-0008、ADR-0018 §4 |
| T13 | 被替換或刪除的原文經 `plan.json`、`validation.json` 留在輸出資料夾，使用者把整個資料夾交給他人時外洩 | insider | 附屬輸出 | 使用者文件內容 | medium | possible | accepted | P2 為證據需要刻意輸出（triage f009，判為預期行為）；README 說明會另輸出這兩個檔，但沒有提醒其中含原文。P3 UI 是否仍輸出、預設位置與提示方式待決定（§6）。P3 另加復原草稿（含新文字）：存在使用者本機資料目錄而非文件旁、不自動開啟、保留 7 天、正常關閉即刪（G3-07，ADR-0020 §5）；草稿目錄需同使用者寫入權限才能竄改，不視為邊界（P3 triage f001～f004） | reports/P2/security/TRIAGE.md f009；reports/P3/security/TRIAGE.md |

## 5. Deprioritized

| threat | reason |
|---|---|
| 網路攻擊者遠端存取服務 | 產品無任何網路服務或連線（離線設計） |
| 多使用者權限提升 | 單機單使用者桌面程式，不提供權限分離 |
| PDF 內 JavaScript 執行 | 產品不執行 PDF JavaScript；P1 capability report 應標示含 JS 的檔案 |
| 數位簽章偽造 | 含簽章檔案屬拒絕範圍（manifest reason=signed），不做簽章驗證 |
| 雲端 Mac 租用帶來的資料外洩 | ADR-0003 不採用雲端租機 |

## 6. Open questions

- worker 是否需作業系統層級沙箱（macOS sandbox-exec／App Sandbox、Windows AppContainer／Job Object），或子行程 + 資源限制即足夠？成本與維運負擔需人工決定（P7 前）。
- 使用者文件是否屬機密等級，是否需要暫存檔加密或儲存後安全刪除暫存？
- 正式散布是否需程式碼簽章與公證（Apple notarization）；未簽章時 macOS Gatekeeper 的使用者操作流程？
- 機關端是否有端點防護會阻擋未簽章執行檔或子行程啟動？
- 離線升級包的 hash 透過何種可信管道傳遞？
- 已決定（P3，ADR-0020 §3）：沿用 ADR-0004，worker 寫入主行程指定的暫存檔，主行程核對後取代；worker 不再收到目的路徑。worker 仍有使用者權限，被攻陷時可寫任意路徑（T1），是否以 OS 沙箱限制其寫檔留待 P7 與上一題一併評估。
- `plan.json`、`validation.json` 含被替換的原文（T13）：P3 UI 是否保留這類輸出、預設存放位置，以及是否需提示使用者？

## 7. Provenance

- mode: bootstrap
- date: 2026-10-12
- target: TGHAPPLICATION/PEditor @ P0（branch claude/compassionate-mayer-4gov5x）
- inputs: 規格 v1.1（docs/spec.md）；離線 PDF 編輯器執行計畫書 v1.1；docs/adr/0001–0008；skill 參考 anthropics/defending-code-reference-harness@d3bea6b
- owner: unset
- update: 2026-10-28，P2（branch p2-text-edit @ 005a781）。依 P2 新增的編輯、另存路徑與 P2 安全掃描 triage（reports/P2/security/TRIAGE.md）更新 §1、§3、T2–T5、T10，新增 T11–T13 與 §6 兩項；回應 reports/P2/report.md §9 U2
- update: 2026-10-29，P3（branch p3-transaction）。依 ADR-0020 與 P3 安全掃描 triage（reports/P3/security/TRIAGE.md）更新 §1、§3（新增復原草稿）、T3、T5、T10、T11、T13 與 §6、§8

## 8. Recommended mitigations

| mitigation | threat_ids | closes_class | effort |
|---|---|---|---|
| 所有 PDF 解析只在 worker 子行程執行，崩潰即重啟 | T1, T5 | partial | M |
| IPC 訊息以 schema 驗證、限制長度與逾時，主行程不信任 worker 輸出 | T2 | yes | S |
| worker 設記憶體／CPU 時間／頁數上限 | T5 | yes | S |
| 儲存一律暫存檔 + fsync + 原子取代，並以 crash injection 驗證 | T3, T10 | yes | M |
| 模式 B 儲存後以文字擷取與運算子掃描驗證舊內容已移除 | T4 | yes | S |
| 相依與 Actions 雜湊／SHA 鎖定、冷卻期、升級走 ADR 與完整回歸 | T6, T7 | partial | S |
| 發佈產物附 SHA-256 並經獨立管道傳遞；正式散布再加簽章 | T8 | partial | S |
| 產品碼禁止網路模組 + 實機零出站監測 | T7 | partial | S |
| fixture 只用合成內容、開啟 secret scanning、日誌去識別 | T9 | partial | S |
| 套用編輯失敗回滾（P3 已完成：以開啟自的位元組回滾） | T11 | partial | S |
| 結構樹 /ParentTree 與 /K 交叉核對，不一致即拒絕標記 PDF 編輯 | T4 | partial | S |
| 另存改用 `destination_token`，由主行程解析實際路徑並負責取代（P3 已完成；worker 仍寫暫存檔） | T10, T2 | partial | M |
| 不覆寫時以不取代既有檔的 rename（POSIX link＋unlink、Windows os.rename）；覆寫時保留原權限 | T10 | yes | S |
| 草稿 JSON 結構驗證、主行程以 OSError → SAVE_FAILED 包裝且不含路徑（P3 triage f001、f010） | T13, T9 | partial | S |
| 附屬輸出預設不含原文，或明確提示含原文 | T13 | yes | S |
