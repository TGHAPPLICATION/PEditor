# Threat Model: PEditor

## 1. System context

PEditor 是在 Windows x64 與 macOS arm64 上執行的離線桌面 PDF 文字編輯器，供機關承辦人修改既有 PDF 內文字（含繁體中文子集字型）並保留排版。以 Python 3.13 + PySide6（Qt 6）實作 UI，PDF 解析與改寫使用 PyMuPDF（MuPDF，C）與 pikepdf（qpdf，C++）。產品不需也不應有任何網路連線。

使用者開啟的 PDF 來源不受控（公文附件、外部來函、下載檔），因此 PDF 一律視為不可信輸入。依 ADR-0004，解析在獨立 worker 子行程進行，主行程只處理 worker 回傳的結構化資料；儲存以暫存檔 + 原子取代完成。產品以 AGPL-3.0 開源，GitHub repo 與 CI 日誌公開。

P0 時點只有空白 UI、fixture 產生器與 CI。P1（2026-10-21）實作 worker 子行程、JSON Lines IPC 與只讀分析器；編輯核心與儲存交易尚未實作，本模型於 P3、P7 再依實作更新。

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
| 儲存 | worker 產出暫存檔，主行程驗證後原子取代 | worker 輸出 → 使用者檔案系統 | 原始檔完整性, 編輯正確性 |
| 檔名與路徑 | 中文、超長、特殊字元路徑；拖放 | 使用者輸入 → 檔案 API | 原始檔完整性 |
| 相依套件與建置 | PyPI wheel、GitHub Actions、PyInstaller | 第三方供應鏈 → 建置產物 | 發佈產物, 使用者主機 |
| 離線升級包 | 手動發佈的升級包與 hash | 傳遞媒介 → 使用者主機 | 發佈產物, 使用者主機 |
| 公開 repo 與 CI 日誌 | fixture、測試輸出、issue | repo 內容 → 公眾 | 使用者文件內容 |

## 4. Threats

| id | threat | actor | surface | asset | impact | likelihood | status | controls | evidence |
|---|---|---|---|---|---|---|---|---|---|
| T1 | 惡意 PDF 經 MuPDF／qpdf 解析造成記憶體破壞並在使用者權限下執行程式碼 | remote_unauth | 開啟 PDF 檔 | 使用者主機, 使用者文件內容 | critical | likely | partially_mitigated | P1：解析只在 worker 子行程（G1-01 測試主行程無 PDF 程式庫）；崩潰／逾時即終止並重啟。非 OS 沙箱，worker 仍有使用者權限（P7 評估） | MuPDF 與 qpdf 歷年記憶體安全 CVE（P1 vuln-scan 時補 CVE 編號） |
| T2 | 已被攻陷或異常的 worker 透過 IPC 送出畸形訊息，攻陷或癱瘓 UI 主行程 | remote_unauth | worker → 主行程 IPC | 使用者主機, 使用者文件內容 | critical | possible | partially_mitigated | P1：JSON Lines、單則 64 MiB 上限（主行程讀取時即限制）、逾時、畸形回應即重啟；尚未以 schema 驗證回應內容（P7 加 fuzz 與 schema） | |
| T6 | 相依套件或 CI action 遭供應鏈攻擊，於建置或執行時植入惡意程式 | supply_chain | 相依套件與建置 | 發佈產物, 使用者主機 | critical | rare | partially_mitigated | uv.lock 雜湊鎖定、exclude-newer 冷卻期、Actions commit SHA 鎖定、contents: read 權限 | |
| T8 | 竄改的安裝包或離線升級包被安裝至使用者主機 | supply_chain | 離線升級包 | 發佈產物, 使用者主機 | critical | rare | unmitigated | 規劃附 hash 發佈；簽章延至正式散布（P8） | |
| T3 | 儲存中斷、崩潰或磁碟滿導致原 PDF 毀損或遺失 | local_user | 儲存 | 原始檔完整性 | high | likely | unmitigated | 規劃暫存檔 + 原子取代 + crash injection 測試（P3） | |
| T4 | 模式 B 只覆蓋未移除，舊文字仍可被擷取，造成資訊外洩 | insider | 儲存 | 編輯正確性, 使用者文件內容 | high | possible | unmitigated | ADR-0001 要求證明舊內容已移除（G2 第 5 點，P2 實作） | |
| T9 | 真實公文、個資或文件原文經 fixture、日誌、錯誤回報進入公開 repo 或 CI 日誌 | insider | 公開 repo 與 CI 日誌 | 使用者文件內容 | high | possible | partially_mitigated | 只放合成 fixture、盲測樣本離線保管、日誌不含原文與路徑（CLAUDE.md） | |
| T7 | 產品或相依於執行時產生出站連線，破壞離線保證或外洩內容 | supply_chain | 相依套件與建置 | 離線保證, 使用者文件內容 | high | rare | partially_mitigated | test_offline_guard 禁止產品碼匯入網路模組；P7 實機零出站監測 | |
| T5 | 惡意 PDF 以資源耗盡（巨大頁數、壓縮炸彈、深層巢狀物件）癱瘓應用程式 | remote_unauth | 開啟 PDF 檔 | 使用者主機 | medium | likely | partially_mitigated | P1：讀檔前檢查檔案大小（200 MB）、開檔後解析頁面前檢查頁數（500）、每請求 30 秒逾時、Form 巢狀深度 8 與循環偵測；記憶體與解壓限制於 P7 | |
| T10 | 特製路徑或檔名（路徑穿越、符號連結）使儲存覆寫非預期檔案 | local_user | 檔名與路徑 | 原始檔完整性 | medium | rare | unmitigated | 規劃儲存時解析實際路徑並驗證（P3） | |

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

## 7. Provenance

- mode: bootstrap
- date: 2026-10-12
- target: TGHAPPLICATION/PEditor @ P0（branch claude/compassionate-mayer-4gov5x）
- inputs: 規格 v1.1（docs/spec.md）；離線 PDF 編輯器執行計畫書 v1.1；docs/adr/0001–0008；skill 參考 anthropics/defending-code-reference-harness@d3bea6b
- owner: unset

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
