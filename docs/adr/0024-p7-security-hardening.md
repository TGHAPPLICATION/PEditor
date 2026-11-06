# ADR-0024：P7 離線與安全強化（worker OS 限制、解壓前限制、回應驗證、沙箱缺口）

- 狀態：已接受（2026-11-04，工程師於 P7 S1／S2 決定「照建議」；2026-11-05 S04 預期由工程師決定；
  同日安全掃描候選 1–9 的處理工程師決定「照建議」，§1、§3、§5、後果增補；2026-11-06 獨立核對第一輪 V1、V6、V7
  工程師決定「照建議」：§1、§2（spec 最低要求對照表）、§5、後果增補，P7 報告 U6 接受）
- 日期：2026-11-05
- 決策者：工程師
- 需人工確認：否（已確認）；P7 報告 §9 待決項目另列

## 背景

spec P7：所有 PDF 視為不可信輸入；不執行 JavaScript、Launch、嵌入檔；worker 限制時間、輸出、記憶體、深度、
頁數、檔案與像素大小，崩潰後可重啟；不啟用 telemetry、遠端字型、自動更新、外部下載；記錄不含原文、密碼或完整
使用者路徑。OS 保護：在 Windows／macOS 分別評估沙箱與權限機制，最低須有獨立程序、限制 IPC、路徑白名單與 OS
出站封鎖驗證；Python API 不足以證明完整 OS 沙箱，報告須明列缺口。限制初值：檔案 200 MB、500 頁、單張影像
50 MP、單操作 30 秒、worker 2 GB；載入前與解析中都要限制，不能先完整解壓才檢查。

P1 起已有：worker 子行程（ADR-0004）、檔案大小與頁數、30 秒逾時、取消、崩潰重啟、Form 深度與循環、運算子數、
渲染像素等工作量上限（core/limits.py）；產品碼不匯入網路模組（test_offline_guard）。
THREAT_MODEL §6 的待決問題：worker 是否需要 OS 層級沙箱。

## 決策

### 1. worker 的 OS 層級限制（core/sandbox.py）

- **Windows**：worker 以 `CREATE_SUSPENDED` 建立，主行程以 Job Object 包住後才恢復執行（Toolhelp 列舉執行緒、
  `ResumeThread`），沒有未受限的時間窗。Job 限制：
  - 行程記憶體上限 2 GB（`WORKER_MEMORY_BYTES`）；Python 層配置超過時 worker 回 `RESOURCE_LIMIT`（MemoryError），
    不是崩潰。MuPDF、qpdf 原生配置失敗時的回應沒有驗證（可能回 `WORKER_FAILED`，或 worker 結束後由主行程重啟；
    P7 獨立核對 V7）。
  - `ActiveProcessLimit`：worker 自己不得再建立子行程（Launch 與被攻陷後直接建立行程都會失敗）。不涵蓋經由
    已存在的其他行程或系統服務間接啟動程式（例如 COM、排程工作、殼層代為開啟），列入 §2 缺口。開發環境的 venv
    `python.exe` 是轉介程式、會再啟動真正的直譯器，該情況允許 2 個行程（仍不能再多）；打包後為 1。
  - `KILL_ON_JOB_CLOSE`：主行程的 job handle 關閉（含主行程異常結束）時 worker 一併終止，不留孤兒行程。
  - UI 限制（桌面、剪貼簿、全域 atom、USER handle 等）。
  - 套用失敗即不使用該 worker（fail closed，回 `WORKER_FAILED`）。
- **macOS／POSIX**：worker 讀任何請求之前自行設 `RLIMIT_AS`（2 GB）與 `RLIMIT_CORE`（0），hard limit 一併設定。
  macOS 核心不強制 `RLIMIT_AS`，記憶體上限在 macOS 只是宣告；也沒有等同 `ActiveProcessLimit` 的機制。
  設定失敗時不中止（POSIX 不是 fail closed，與 Windows 不同）。
- 以 ctypes 呼叫系統 API，不新增相依。

### 2. 不做完整 OS 沙箱（缺口明列）

| 機制 | 評估 | 決定 |
| --- | --- | --- |
| Windows AppContainer／低完整性等級 | 可限制檔案與網路存取，但 worker 須能讀使用者選的 PDF、寫同目錄暫存檔；需為每次開檔授權路徑（或由主行程把位元組傳給 worker 並改由主行程寫檔），並調整 PyInstaller 打包 | 不做（P8 後另議） |
| Windows Job Object | 記憶體、子行程、隨主行程終止、UI 限制 | 採用（§1） |
| macOS App Sandbox | 需簽章與 entitlements，配合 P8 打包與 notarization；Python 子行程須同一 bundle | 不做（P8 與正式散布時另議） |
| macOS `sandbox-exec` | Apple 已標為 deprecated，規則語法無正式文件 | 不採用 |
| 網路封鎖 | 產品碼不匯入網路模組（測試）、測試以 audit hook 驗證無 socket、實機以腳本監測 | 不加 OS 防火牆規則（需系統管理權限） |

spec P7「最低必須有獨立程序、限制 IPC、路徑白名單與作業系統出站封鎖驗證」逐項（P7 獨立核對 V1）：

| 最低要求 | 狀態 | 說明 |
| --- | --- | --- |
| 獨立程序 | 達成 | 解析只在 worker 子行程（ADR-0004）；Windows 另以 Job Object 限制（§1） |
| 限制 IPC | 達成 | 只用 stdin／stdout 管線、JSON Lines、單行大小上限；請求參數白名單（P1）；回應結構驗證（§5）；無任何 socket（G7-02 測試） |
| 路徑白名單 | 部分達成 | 主行程層級：開檔路徑由使用者選擇、另存只接受 `destination_token`（ADR-0020 §3），worker 只收主行程指定的路徑；worker 本身沒有 OS 強制的路徑限制，被攻陷時可讀寫使用者可存取的任何檔案 |
| 作業系統出站封鎖驗證 | 部分達成 | 沒有加 OS 防火牆封鎖規則（需系統管理權限）；以自動測試（audit hook、socket 監測）與實機監測腳本驗證「沒有出站」；Windows 實機尚未執行，macOS 實機 NOT RUN |

缺口：worker 仍以使用者權限執行，可讀寫使用者可存取的所有檔案、可開 socket（被攻陷時），也可能經由其他行程或
系統服務間接啟動程式（Job Object 只擋 worker 直接建立子行程）；主行程與 worker 之間只靠 stdin／stdout 管線。
macOS 上記憶體與子行程都沒有 OS 強制。

### 3. 解壓前的大小限制（worker/streams.py；P2 triage f024）

- 內容串流（含 Form）、字型程式（FontFile／2／3）、ToUnicode、CIDToGIDMap、Type3 字形程序在交給 pikepdf 或
  MuPDF 之前先算出解壓後大小：開頭的 ASCIIHex／ASCII85 實際解碼，接著的 FlateDecode 以 zlib 分段解壓、超過上限
  即停；其餘過濾器以最大膨脹倍數估上限（RunLength 128、LZW 4096、Flate 1032），不認得的過濾器視為無上限。
- 上限：每個串流 64 MB（`MAX_STREAM_BYTES`）、CMap 4 MB（既有）。超過即該頁 `RESOURCE_LIMIT`，且不交給 MuPDF
  擷取或渲染（`render_page` 也拒絕）。
- 影像 XObject 宣告的寬×高超過 50 MP 即該頁 `RESOURCE_LIMIT`（MuPDF 渲染時才配置）。
- CMap 的 bfchar／bfrange 區塊改為線性掃描（P2 triage f022：未結尾的區塊使正規表示式變成平方級）；bfrange 內缺 `]`
  的陣列遇到下一個 `[` 即停（P7 安全掃描候選 4）。
- Flate 資料毀損時 zlib 會丟掉該次呼叫的輸出，大小改以上限計；估計結果為 NaN（0 × 無上限）也拒絕（候選 1）。
- 未塗繪的路徑累積的點數同樣受 `MAX_PAINTED_POINTS` 限制，超過即頁面 `RESOURCE_LIMIT`（候選 5）。
- 儲存格墨跡檢查（ADR-0023 §2）渲染像素上限 12 MP（同另存視覺驗證），超過即該行 `RESOURCE_LIMIT`（候選 3）。
- `render_page` 只在頁面本身超限時拒絕；文件層級的 `RESOURCE_LIMIT`（書籤、表單欄位過多）仍可檢視（掃描觀察）。

### 4. 不寫日誌檔

- 產品不寫日誌；worker 的 stderr 導向 DEVNULL，只寫例外類型名稱。會離開行程的文字只有錯誤訊息（不含原文與路徑）
  與 CLI 的理由碼。G7-05 以 sentinel（資料夾名、檔名、文件內容、新文字）檢查錯誤訊息、worker stderr、CLI 輸出。
- 復原草稿（ADR-0020 §5）與另存報告（plan.json／validation.json，THREAT_MODEL T13）含原檔路徑與文字，是使用者
  資料而非日誌，維持 0600 與既有清除規則。

### 5. worker 回應驗證（core/protocol.py `validate_response`；P1 triage f006、f020、f021）

- 主行程對每個 operation 檢查回應結構：`ok` 為布林、`result` 為物件且主行程用到的欄位型別正確（int 不接受 bool）、
  `error` 的 code 在已知清單、message 為字串且 ≤1,000 字、retryable 為布林；request_id 必須是字串或 null。
  不符即視為 worker 異常：終止重啟、回 `WORKER_FAILED`。request_id 是其他字串的回應視為不是這個請求的回應而略過
  （仍受請求總逾時限制，P7 獨立核對 V7）。只檢查結構，不檢查巢狀內容的語義（被攻陷的 worker
  仍可回傳結構正確但內容錯誤的結果，影響限於 UI 顯示與該次操作）。
- worker 只回傳字串 request_id。
- 逾時以整個請求計，不因 worker 送出其他 request_id 的回應而重新計時（候選 7）。

### 6. 重播分批（P3 triage f008、P6 第四輪 T7）

- undo、草稿復原、worker 重啟後還原的重播，每 10 筆（`REPLAY_BATCH`）一個請求，各自受 30 秒逾時；第二批起失敗即
  終止重啟 worker，下次請求依 command log 重開重播。還原失敗時關閉文件的錯誤不再蓋過原錯誤。

### 7. 其他帶入項目

- 另存（P3 triage f009、f012）：不覆寫時，目的檔在最後檢查後才出現也不取代（Windows `os.rename`；POSIX
  `os.link` 再刪暫存檔，不支援硬連結的檔案系統退回檢查後 rename）；覆寫時保留目的檔的權限位元（Windows ACL 不複製）。
- 多實例（P4 U10）：啟動清除只刪超過 10 分鐘的暫存檔；暫存檔紀錄的讀改寫加檔案鎖。
- 關閉流程（ADR-0021 增補、P4 U11）：等待執行中工作每階段上限 10 秒，逾時即終止 worker。
- P4 U13：開啟 0 頁文件時清除前一份文件的頁面與目標框。

### 8. 惡意樣本 S03–S06

- S03 壓縮炸彈（128 MB 空白的 Flate）→ 頁面 `RESOURCE_LIMIT`；S05 嵌入附件、S06 Launch（會在目前資料夾建立
  sentinel 檔）→ `ACTIVE_CONTENT`。
- S04 深層巢狀物件：`/Annots` 指向巢狀 100,000 層的陣列。qpdf 解析超過 500 層即視為損毀，產品回
  `MALFORMED_DOCUMENT`；manifest 預期由 P0 預訂的 `RESOURCE_LIMIT` 改為 `MALFORMED_DOCUMENT`
  （工程師 2026-11-05 決定）。未被走訪的位置放深層巢狀不會被解析，對產品沒有影響。

## 後果

- Windows：worker 記憶體、子行程、孤兒行程有 OS 強制；macOS 沒有（G7-04、G7-06 的相關測試只在 Windows 執行，
  macOS 記為 NOT RUN）。
- 解壓前限制使含 64 MB 以上單一串流或不認得過濾器的內容串流的頁面不能編輯（偏保守）；LZW 串流原始大小超過
  16 KB 即視為超限。
- 回應結構不符一律重啟 worker，比原本嚴格。
- 殘餘：解壓前檢查與 50 MP 檢查只涵蓋 content 解譯器實際走到的物件；inline image、影像的 SMask、tiling pattern、
  soft-mask group、Type3 字型的 /Resources、Type0 內嵌 CMap、註解外觀、shading（含 Type 4–7 mesh 串流）、Function
  串流、ICCBased 色彩描述檔，以及影像資料本身（只檢查宣告的寬×高，不檢查壓縮比；P7 獨立核對 V6），都由 MuPDF
  自行解壓，炸彈只受 Job Object
  記憶體上限保護（macOS 無；候選 6）；「超限、不渲染」以 pikepdf 的解析結果判定，MuPDF 對同一份檔案的解析（例如需要
  修復的檔案）可能不同（候選 9）；
  非完整 OS 沙箱（§2）；實機出站監測以輪詢進行，短於輪詢間隔的連線嘗試可能漏掉（自動測試以 audit hook 與
  Job Object 補足）。
- 覆寫時權限位元只在 POSIX 保留；Windows 不複製唯讀屬性與 ACL（唯讀的目的檔無法取代，回 SAVE_FAILED；候選 2：
  複製唯讀屬性會使暫存檔取代失敗後刪不掉）。
