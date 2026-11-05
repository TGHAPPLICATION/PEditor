# VULN-FINDINGS（P7 靜態掃描）

- 技能：vuln-scan (defending-code-reference-harness@d3bea6b) --no-score，依 .claude/skills/vuln-scan/SKILL.md 手動執行（ADR-0005）；日期：2026-11-05；範圍：P7 新增／修改的 `src/` 程式（commit `0533432`），4 個焦點區域（解壓前限制與解譯器工作量、儲存格墨跡檢查與頁面渲染、主行程 IPC 逾時、worker OS 限制與另存交易）
- 掃描子代理人第一次執行時讀完範圍內程式並列出候選，但中途停止，沒有寫出檔案、也沒有做 triage；本檔依其候選清單補寫，每項的位置與內容都已對 `0533432` 重新讀程式確認（`git show 0533432:<path>`）。原清單沒有保留各項的信心數值，只標出 F-009 為低信心，JSON 的 `confidence` 因此為 null。
- 合計 9 項（HIGH 0／MEDIUM 1／LOW 8，低信心 1），另 1 項非安全觀察。這些是**未經驗證的靜態候選**，驗證結果見 `TRIAGE.md`。
- file:line 以 `0533432` 為準；修正後的程式在 `87ec3b2`。本檔只寫到問題類別與觸發條件，不含可直接利用的步驟。

| id | severity | category | file:line | title |
| --- | --- | --- | --- | --- |
| F-001 | MEDIUM | resource exhaustion / size-check bypass | `src/peditor/worker/streams.py:68` | Corrupt Flate data makes _inflated_size report 0, so a later filter multiplies to 0 or NaN and passes the 64 MB pre-decompression check |
| F-002 | LOW | data remnant / regression | `src/peditor/export/transaction.py:145` | On Windows, copymode makes the temp file read-only when overwriting a read-only destination, so the temp with the full document cannot be deleted after replace fails |
| F-003 | LOW | algorithmic complexity / unbounded allocation | `src/peditor/worker/cell.py:105` | Cell ink check renders the cell region with no pixel cap and walks samples in pure Python, so a huge page can exceed the 30 s timeout |
| F-004 | LOW | ReDoS / algorithmic complexity | `src/peditor/worker/fonts.py:408` | parse_cmap bfrange array regex is quadratic when the closing ] is missing |
| F-005 | LOW | unbounded allocation | `src/peditor/worker/content.py:350` | Points of a path that is never painted accumulate without the MAX_PAINTED_POINTS limit |
| F-006 | LOW | incomplete limit coverage / resource exhaustion | `src/peditor/worker/content.py:381` | 50 MP and 64 MB checks cover only objects the interpreter walks; inline images, SMasks, tiling patterns, soft-mask groups, Type3 /Resources and embedded Type0 CMaps are decompressed by MuPDF unchecked |
| F-007 | LOW | timeout bypass | `src/peditor/core/service.py:582` | Request timeout restarts on every line read, so a worker that keeps sending responses for other request ids never times out |
| F-008 | LOW | overstated control / documentation | `src/peditor/core/sandbox.py:141` | ActiveProcessLimit only blocks processes the worker creates directly; ADR-0024 §1 overstates it |
| F-009 | LOW（低信心） | parser differential | `src/peditor/worker/analyzer.py:405` | render_page decides 'over limit, do not render' from pikepdf's parse while MuPDF parses the same file independently |

### F-001：Corrupt Flate data makes _inflated_size report 0, so a later filter multiplies to 0 or NaN and passes the 64 MB pre-decompression check

`src/peditor/worker/streams.py:68` · resource exhaustion / size-check bypass · MEDIUM

`_inflated_size`（54-70）在 `zlib.error` 時直接回傳已累計的 total。zlib 會丟掉發生錯誤那次 `decompress` 呼叫的輸出（本次以標準函式庫確認：串流中段毀損時該次呼叫直接拋錯、不回傳已解出的部分），所以第一段 Flate 已有效解出的前段大小會被低估，常常是 0。`check`（73-93）接著把剩下的過濾器的最大膨脹倍數相乘：0 × 倍數 = 0，0 × 不認得的過濾器（`math.inf`）= NaN；`bound > limit` 對 0 和 NaN 都是假，所以檢查通過。只有單一 Flate 時，低估的量不會超過上限（錯誤發生前的輸出不超過該次呼叫的 max_length）；問題出在 Flate 後面還有過濾器的串流。

**情境：** 不可信 PDF 的內容、字型或 CMap 串流用多段過濾器，第一段 Flate 毀損。解壓前檢查通過後，串流由 pikepdf／MuPDF 完整解壓，等於回到 P7 之前「先解壓才檢查」的狀態，只剩 Windows Job Object 記憶體上限和 30 秒逾時擋著。

**建議：** zlib 出錯時以上限計（實際可解出的前段不超過 limit）；比較改成 `not bound <= limit`，NaN 也拒絕。

### F-002：On Windows, copymode makes the temp file read-only when overwriting a read-only destination, so the temp with the full document cannot be deleted after replace fails

`src/peditor/export/transaction.py:145` · data remnant / regression · LOW

`_place`（134-162）覆寫既有目的檔時先執行 `shutil.copymode(dest, temp)`，這是 P7 修 P3 f012 時加入的。Windows 上 chmod 只對應唯讀屬性，所以目的檔唯讀時暫存檔也跟著變唯讀。接著 `os.replace` 對唯讀目的檔失敗，`commit` 的 except 路徑呼叫 `_remove`（181-185）執行 `os.remove`；唯讀檔在 Windows 上刪不掉，例外又被忽略。pending-temps 啟動清除和 `_remove_stale` 也一樣刪不掉，含完整新文件的暫存檔就一直留在目的資料夾。

**情境：** 使用者在 Windows 上以覆寫方式另存到唯讀的既有 PDF。另存回 SAVE_FAILED，資料夾裡卻留下一個刪不掉的暫存檔。

**建議：** Windows 不複製唯讀屬性（POSIX 照舊複製權限位元）。

### F-003：Cell ink check renders the cell region with no pixel cap and walks samples in pure Python, so a huge page can exceed the 30 s timeout

`src/peditor/worker/cell.py:105` · algorithmic complexity / unbounded allocation · LOW

`_ink_clip`（91-）以 150 DPI 渲染整個可改動區域（`get_pixmap`，105-106），再用 Python 產生器每隔兩列兩欄取樣、建 Counter（110-112），之後逐欄逐列呼叫 `ink()`。區域來自格線偵測，大小只受頁面尺寸限制。`render_page` 的 `MAX_RENDER_PIXELS` 只管檢視用的渲染，管不到這裡，所以極大頁面上的大格會讓渲染像素和 Python 迭代數都沒有上限。

**情境：** 不可信 PDF 的頁面極大、含可偵測的表格；使用者選格並要求規劃儲存格編輯，請求超過 30 秒逾時，或配置大量記憶體。

**建議：** 渲染前以「區域面積 × 縮放倍率平方」檢查像素上限（同另存視覺驗證的 12 MP），超過即該行 RESOURCE_LIMIT。

### F-004：parse_cmap bfrange array regex is quadratic when the closing ] is missing

`src/peditor/worker/fonts.py:408` · ReDoS / algorithmic complexity · LOW

bfrange 的正規表示式 `\[[^\]]*\]`（407-409）遇到缺 `]` 的陣列時，每個候選起點都會掃到區塊結尾再回溯，總工作量是「起點數 × 區塊長度」。P2 f022 已把 `_blocks` 改成線性，但區塊內的陣列比對仍是平方級；CMap 的 4 MB 上限仍容許遠超過 30 秒的工作量。

**情境：** 不可信 PDF 的 ToUnicode CMap 在 bfrange 區塊裡放大量未結尾的陣列；開啟並檢視該頁時，`load_font` 會一直解析 CMap 直到逾時。

**建議：** 陣列內容排除 `[`（遇到下一個 `[` 即停），讓每個起點的掃描範圍不重疊。

### F-005：Points of a path that is never painted accumulate without the MAX_PAINTED_POINTS limit

`src/peditor/worker/content.py:350` · unbounded allocation · LOW

`_execute` 遇到 m/l/c/v/y/re 時呼叫 `_path_op`（214），曲線細分成 `CURVE_STEPS`=16 點累積在 path 裡，要等到塗繪運算子才清空。`MAX_PAINTED_POINTS` 只在 `_record_paths` 裡檢查（塗繪時，328-331），未塗繪的路徑只受 `MAX_CONTENT_OPERATORS`（1,000,000）間接限制，單頁可累積約一千六百萬個點的 tuple。

**情境：** 不可信 PDF 的內容串流含大量從未塗繪的曲線運算子；檢視該頁時 worker 配置大量記憶體，也可能逾時。

**建議：** 用同一個上限計算未塗繪路徑累積的點數，超過即 LimitExceeded（頁面 RESOURCE_LIMIT）。

### F-006：50 MP and 64 MB checks cover only objects the interpreter walks; inline images, SMasks, tiling patterns, soft-mask groups, Type3 /Resources and embedded Type0 CMaps are decompressed by MuPDF unchecked

`src/peditor/worker/content.py:381` · incomplete limit coverage / resource exhaustion · LOW

`_do`（381-411）只檢查 Image XObject 本身的 /Width×/Height 和 Form 的內容。下列物件都不會被走訪：inline image（195-197 只計數）、影像的 /SMask、/Pattern 資源、ExtGState 的 soft-mask group、Type3 字型 /Resources 裡的影像。`_font_streams`（447-466）只列 ToUnicode、CIDToGIDMap、FontFile*、CharProcs，不含 Type0 內嵌的 CMap（/Encoding 串流）。這些串流都由 MuPDF 在擷取和渲染時自行解壓、配置記憶體。

**情境：** 不可信 PDF 把大尺寸或高壓縮比的資料放在上述沒被走訪的位置；頁面不會被標成 RESOURCE_LIMIT，`render_page` 照常交給 MuPDF。

**建議：** 走訪並檢查上述物件；或在 ADR-0024 明列為殘餘（只受 Job Object 記憶體上限保護）。

### F-007：Request timeout restarts on every line read, so a worker that keeps sending responses for other request ids never times out

`src/peditor/core/service.py:582` · timeout bypass · LOW

`_exchange`（572-606）每次以 `worker.lines.get(timeout=self.timeout)` 讀一行；request_id 不符的回應以 `continue` 略過（596-597），下一次讀取又重新給滿 30 秒。只要 worker 持續送出其他 request_id 的回應，請求就永遠不會逾時。

**情境：** 已被攻陷或異常的 worker 定期送出 request_id 不相符的回應，主行程的請求一直等下去。

**建議：** 以整個請求計算期限（monotonic deadline），每次讀取只給剩餘時間。

### F-008：ActiveProcessLimit only blocks processes the worker creates directly; ADR-0024 §1 overstates it

`src/peditor/core/sandbox.py:141` · overstated control / documentation · LOW

Job Object 設定的 `JOB_OBJECT_LIMIT_ACTIVE_PROCESS`（136-141）只限制 job 內的行程數。由已存在的其他行程或系統服務代為啟動的程式不屬於這個 job，不受限制。ADR-0024 §1（`0533432` 版）寫「被攻陷後執行外部程式都會失敗」，比實際的保護範圍強。

**情境：** 被攻陷的 worker 透過 job 外的既有行程或系統服務間接啟動程式，ActiveProcessLimit 擋不到。

**建議：** 修正 ADR-0024 §1 措辭，並在 §2 缺口列出間接啟動。

### F-009：render_page decides 'over limit, do not render' from pikepdf's parse while MuPDF parses the same file independently

`src/peditor/worker/analyzer.py:405` · parser differential · LOW · 低信心

`render_page`（396-409）依 `inspect_page` 的結果判斷是否超限，這個結果來自 pikepdf 解析的內容與資源（`content.interpret`）；通過後由 MuPDF 對同一份位元組自行解析並渲染（407）。兩者對需要修復的檔案可能解析出不同的物件，而 MALFORMED_DOCUMENT 不會阻擋渲染。

**情境：** 不可信 PDF 讓 qpdf 和 MuPDF 對同一頁解析出不同內容：pikepdf 看到的內容未超限，MuPDF 實際渲染的內容卻超限。

**建議：** 列為殘餘；或對 MuPDF 修復過的檔案，超限判定改以 MuPDF 的解析為準。

## 觀察（非安全）

### O-1：Document-level RESOURCE_LIMIT makes render_page refuse every page

`src/peditor/worker/analyzer.py:405`

`_analyze_page` 把 `document.doc_reasons` 併入每一頁的 reasons（477-481、500、551、585）。因此文件層級的 RESOURCE_LIMIT（書籤或表單欄位節點過多，analyzer.py 154-158）會讓 `render_page` 對所有頁面都拒絕渲染，整份文件無法檢視。屬可用性問題，不列入安全候選。
