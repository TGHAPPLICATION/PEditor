# Triage Report

9 in -> 0 duplicates, 3 false positives, 6 confirmed (0 high / 1 med / 5 low), 1 need manual test

- 技能：triage（defending-code-reference-harness@d3bea6b，依 `.claude/skills/triage/SKILL.md` 手動執行，ADR-0005）；日期：2026-11-05；範圍：P7 掃描候選 9 項＋觀察 1 項，程式以 commit `0533432` 為準；處理對照 `87ec3b2`（程式與回歸測試）與 `8ca60b2`（ADR-0024 增補）。
- 掃描子代理人第一次執行中途停止，沒有寫出檔案、也沒有做 triage；`VULN-FINDINGS.*` 依其候選清單補寫，本報告逐項重新讀程式驗證。
- 兩票都由 triage 代理人本身以兩個獨立角度判讀，沒有另派子代理人。A 票：SKILL.md 3a 的對抗式驗證（從 sink 反向追可達性、找保護、套排除規則）；B 票：對照 ADR-0024／THREAT_MODEL 宣稱的控制，判斷控制是否確實失效、影響是否越過信任邊界。只有 f009 分票，依 recall 判為 needs_manual_test，沒有加第三票。

Context: interactive (P1/P3 interview answers reused; same product and trust boundary); environment = offline single-user desktop app, untrusted PDFs and worker output, operator flags trusted, app-written drafts may be corrupted but other same-user processes are not a boundary; scoring = derived HIGH/MEDIUM/LOW; noise tolerance = recall; 2-vote verification (one split, f009, kept under recall). Input: `VULN-FINDINGS.json` (scanner ids F-001..F-009 map to f001..f009).

## Act on these

### [MEDIUM] Corrupt Flate data makes _inflated_size report 0, so a later filter multiplies to 0 or NaN and passes the 64 MB pre-decompression check  (f001 / F-001)
`src/peditor/worker/streams.py:68` | resource exhaustion / size-check bypass | claimed MEDIUM (alignment 0) | confidence 8.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (2):**
- 使用者開啟並檢視不可信 PDF 的某一頁
- 該頁的內容、字型或 CMap 串流是「Flate 後面還有其他過濾器」，而且 Flate 資料毀損
**Threat-model match:** T5（ADR-0024 §3 的解壓前限制失效；Windows 仍有 Job Object 2 GB，macOS 沒有）
**Why:** `streams.py:68-69` 吞掉 `zlib.error` 後回傳 total。zlib 在串流中段毀損時，該次 `decompress` 直接拋錯、不回傳輸出（本次以標準函式庫確認），已解出的前段因此被算成 0。`check`（89-93）把剩下的過濾器倍數相乘，得到 0 或 NaN，`bound > limit` 都不成立。可達路徑：`content.py:182`（內容串流）、`content.py:283`（字型串流）→ `check`，之後交給 MuPDF 擷取與 `render_page`。單一 Flate 時低估不會超過上限，只有多段過濾器的串流受影響。前置條件少、本機開檔，依表為 LOW；因直接對應 T5，升一級為 MEDIUM。
**Reachability evidence:** src/peditor/worker/content.py:182, src/peditor/worker/content.py:283
**Outcome:** fixed（`87ec3b2`）。zlib 出錯時改回傳 limit：錯誤發生前的輸出不會超過該次的 max_length，所以 limit 是有效上限。比較改成 `not bound <= limit`，NaN 也會被拒絕。ADR-0024 §3 增補。回歸測試 `tests/security/test_p7_limits.py::test_corrupt_flate_before_other_filter_rejected`。

### [LOW] parse_cmap bfrange array regex is quadratic when the closing ] is missing  (f004 / F-004)
`src/peditor/worker/fonts.py:408` | ReDoS / algorithmic complexity | claimed LOW (alignment 0) | confidence 9.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (1):**
- 使用者開啟並檢視某一頁，該頁用到的字型其 ToUnicode CMap 含大量未結尾的 bfrange 陣列
**Threat-model match:** T5（受 30 秒逾時與 worker 重啟限制）
**Why:** `fonts.py:407-409` 的 `\[[^\]]*\]` 在缺 `]` 時，每個起點都掃到區塊結尾。本次在暫存目錄單獨計時 `0533432` 的正規表示式：2,000／4,000／8,000 個未結尾項目分別約 0.16／0.66／2.7 秒（數量加倍、時間約 4 倍），新寫法 0.001～0.009 秒；4 MB 上限可放數十萬個起點，遠超過 30 秒。任何 `Tf` 都會經 `content.py:231` → `_font` → `load_font` → `parse_cmap` 觸發，只要檢視頁面就會執行。排除規則 1 明文保留 ReDoS。影響受逾時終止、限於該份文件，所以不升級（同 P3 f015）。P2 f022 是同類問題（`_blocks` 層級），當時以分票 1-2 判為誤報；本項是 P7 宣稱已線性化之後仍殘留的同類問題。
**Reachability evidence:** src/peditor/worker/content.py:231
**Outcome:** fixed（`87ec3b2`）。陣列改為 `\[[^\]\[]*\]`，遇到下一個 `[` 即停。ADR-0024 §3 增補。回歸測試 `tests/security/test_p7_limits.py::test_cmap_unterminated_array_linear`（牆鐘時間 < 2 秒）。

### [LOW] Points of a path that is never painted accumulate without the MAX_PAINTED_POINTS limit  (f005 / F-005)
`src/peditor/worker/content.py:350` | unbounded allocation | claimed LOW (alignment 0) | confidence 7.5/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (1):**
- 使用者開啟並檢視某一頁，該頁內容串流含極大量從未塗繪的路徑運算子
**Threat-model match:** T5
**Why:** 路徑運算子經 `content.py:214` 進 `_path_op`，曲線細分成 16 點延伸（369-377）。path 只在 `_PAINT` 分支（219-226）清空，`MAX_PAINTED_POINTS` 只在塗繪時檢查。唯一的間接上限是一百萬個運算子：約一千六百萬個點 tuple，估計 1.5～2 GB，而內容串流本身只需約 14 MB，低於 64 MB 上限。運算子上限與 Windows Job Object 有間接約束，所以不升級。
**Reachability evidence:** src/peditor/worker/content.py:214
**Outcome:** fixed（`87ec3b2`）。`_execute` 以 `path_points` 累計每個路徑運算子新增的點數，超過 `MAX_PAINTED_POINTS` 即頁面 RESOURCE_LIMIT。ADR-0024 §3 增補。回歸測試 `tests/security/test_p7_limits.py::test_unpainted_path_points_bounded`。

### [LOW] Cell ink check renders the cell region with no pixel cap and walks samples in pure Python, so a huge page can exceed the 30 s timeout  (f003 / F-003)
`src/peditor/worker/cell.py:105` | algorithmic complexity / unbounded allocation | claimed LOW (alignment 0) | confidence 7.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (3):**
- 使用者開啟頁面極大的不可信 PDF
- 格線偵測在該頁找到格
- 使用者選格並要求規劃儲存格編輯
**Threat-model match:** T5（受 30 秒逾時限制；Windows 另有 Job Object 記憶體上限）
**Why:** `cell.py:69` 無條件呼叫 `_ink_clip`；105-106 以 150 DPI 渲染整個 region，沒有像素檢查；110-112 用 Python 取樣四分之一的像素。`render_page` 的 50 MP 上限依呼叫端 DPI 計算（最低 18 DPI），所以能檢視的頁面在 150 DPI 下可達數十億像素。同類為 P3 f015。
**Reachability evidence:** src/peditor/worker/cell.py:69
**Outcome:** fixed（`87ec3b2`）。渲染前以「面積 × INK_ZOOM²」對 `INK_MAX_PIXELS`=12 MP 檢查，超過即該行 RESOURCE_LIMIT。ADR-0024 §3 增補。回歸測試 `tests/security/test_p7_limits.py::test_ink_check_pixel_bound`：以 monkeypatch 把上限降為 100 像素，在 B01 上驗證拒絕路徑，沒有用真正的極大頁面測試。

### [LOW] 50 MP and 64 MB checks cover only objects the interpreter walks; inline images, SMasks, tiling patterns, soft-mask groups, Type3 /Resources and embedded Type0 CMaps are decompressed by MuPDF unchecked  (f006 / F-006)
`src/peditor/worker/content.py:381` | incomplete limit coverage / resource exhaustion | claimed LOW (alignment 0) | confidence 7.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo
**Verdict:** mitigated, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (1):**
- 使用者開啟並檢視某一頁，該頁的大尺寸或高壓縮比資料放在解譯器不走訪的物件裡
**Threat-model match:** T5（Windows 由 Job Object 2 GB 與 30 秒逾時減輕；macOS 沒有記憶體強制）
**Why:** `content.py:388-390` 只檢查 Image XObject 本身的尺寸，inline image（195-197）只計數；`/SMask`、`/Pattern`、soft-mask group、Type3 `/Resources` 都不走訪；`_font_streams`（447-466）不含 Type0 的 `/Encoding` CMap 串流。這些物件由 MuPDF 在擷取和 `render_page`（`analyzer.py:407`）時自行解壓。`0533432` 版 ADR-0024 後果只寫到「註解外觀、影像等」，§3 卻宣稱影像超過 50 MP 即 RESOURCE_LIMIT。
**Reachability evidence:** src/peditor/worker/content.py:389, src/peditor/worker/analyzer.py:407
**Outcome:** documented。未改程式；ADR-0024「後果」的殘餘（`8ca60b2`）已逐一列出 inline image、影像的 SMask、tiling pattern、soft-mask group、Type3 /Resources、Type0 內嵌 CMap、註解外觀，並註明只受 Job Object 記憶體上限保護（macOS 無）。

### [LOW] render_page decides 'over limit, do not render' from pikepdf's parse while MuPDF parses the same file independently  (f009 / F-009)
`src/peditor/worker/analyzer.py:405` | parser differential | claimed LOW (alignment 0) | confidence 4.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo
**Verdict:** needs_manual_test, votes {'true_positive': 1, 'false_positive': 0, 'cannot_verify': 1}
**Preconditions (3):**
- 使用者開啟需要修復的不可信 PDF
- qpdf 與 MuPDF 對同一頁解析出不同的內容或資源
- 只有 MuPDF 看到的那部分內容超過工作量或解壓上限
**Threat-model match:** T5（上限同 f006）
**Why:** 超限判定來自 `interpret(document.pike.pages[i])`（`analyzer.py:476`），實際渲染卻由 `document.mu`（407）執行，兩個解析器各自開啟同一份位元組（117、131）。修復過的檔案只標 MALFORMED_DOCUMENT（125-127、138-140），`render_page` 不看這個理由。A 票為 cannot_verify：兩者對特定毀損結構是否真的解析出不同內容，取決於 qpdf／MuPDF 的修復行為，靜態讀 Python 無法確認。
**Reachability evidence:** src/peditor/worker/analyzer.py:476, src/peditor/worker/analyzer.py:407
> Recommend a human build a PoC; static reasoning hit its limit.
**Outcome:** documented。未改程式；ADR-0024「後果」的殘餘（`8ca60b2`）已列入（候選 9）。尚未做執行期驗證。

## Dropped

| id | title | file:line | why dropped |
| --- | --- | --- | --- |
| f002 | On Windows, copymode makes the temp file read-only when overwriting a read-only destination, so the temp with the full document cannot be deleted after replace fails | `src/peditor/export/transaction.py:145` | implausible_trigger; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f007 | Request timeout restarts on every line read, so a worker that keeps sending responses for other request ids never times out | `src/peditor/core/service.py:582` | implausible_trigger; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f008 | ActiveProcessLimit only blocks processes the worker creates directly; ADR-0024 §1 overstates it | `src/peditor/core/sandbox.py:141` | not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |

## Correctness defects confirmed in code (dropped as security findings)

驗證時確認機制存在，但沒有不可信輸入能觸發，或觸發者是已被攻陷、本來就有使用者權限的 worker，或只是文件措辭問題。工程師仍決定全部處理：

| id | defect | outcome |
| --- | --- | --- |
| f002 | Windows 覆寫唯讀目的檔：`copymode` 使暫存檔唯讀，`os.replace` 失敗後 `_remove`、`_remove_stale`、啟動清除都刪不掉，含完整新文件的暫存檔長期留在目的資料夾（P7 修 P3 f012 帶入的回歸；觸發者是使用者自己的另存，內容就是要存進該資料夾的文件，同 P3 f011 類） | fixed `87ec3b2`：Windows 不複製權限（唯讀屬性與 ACL）；`tests/integration/test_crash_injection.py::test_overwrite_readonly_leaves_no_readonly_temp`（只在 Windows 執行）；ADR-0024 後果增補 |
| f007 | `_exchange` 每讀一行重新計時，持續送出其他 request_id 回應的 worker 可使請求不逾時。只有已被攻陷的 worker 做得到，而它本來就常駐並具使用者權限；使用者仍可取消（`service.py:406-416` 會終止 worker） | fixed `87ec3b2`：以 monotonic deadline 計算整個請求的時間；`tests/security/test_ipc_fuzz.py::test_request_timeout_is_total`；ADR-0024 §5 增補 |
| f008 | `ActiveProcessLimit` 只擋 worker 直接建立的子行程，ADR-0024 §1 原措辭「被攻陷後執行外部程式都會失敗」過強；程式設定正確（未設 BREAKAWAY_OK） | documented `8ca60b2`：ADR-0024 §1 改寫，§2 缺口補上間接啟動。**THREAT_MODEL.md T1 仍寫「不得建立子行程」，未同步修正** |

## 觀察（非安全）與修正後發現的問題

### O-1：Document-level RESOURCE_LIMIT makes render_page refuse every page

`src/peditor/worker/analyzer.py:405`。屬實：`_analyze_page` 把 `doc_reasons` 併入每頁 reasons（477-481、500、551、585），書籤或表單欄位節點過多的文件整份無法檢視。

**Outcome:** fixed（`87ec3b2`）。文件層級已有 RESOURCE_LIMIT 時，`render_page` 不再以 RESOURCE_LIMIT 拒絕；回歸測試 `tests/security/test_p7_limits.py::test_document_level_limit_still_renders`；ADR-0024 §3 增補。

**修正後的問題（已修，`57fdb4d`）：** 新條件（`87ec3b2` `analyzer.py:406-407`）分不出兩種情況：只有文件層級超限，以及文件層級和頁面本身都超限。文件層級已有 RESOURCE_LIMIT 時，頁面本身超限（壓縮炸彈、工作量上限）的頁面也會交給 MuPDF 渲染。文件層級超限的條件同樣來自不可信 PDF，因此 ADR-0024 §3「超過即該頁 RESOURCE_LIMIT，且不交給 MuPDF 擷取或渲染（render_page 也拒絕）」在這類文件上不成立。後果同 f006，受 Job Object 記憶體上限與逾時限制。回歸測試只驗證正常頁面能渲染，沒有驗證超限頁面在這種情況下仍被拒絕。建議由 `_analyze_page` 另外記錄頁面本身是否超限，`render_page` 改用該值判定，並補一個「文件層級超限＋頁面超限仍拒絕」的測試。

**Outcome（主代理人補記）：** fixed `57fdb4d`——`_analyze_page` 把內容本身超限的頁記入 `Document.limited_pages`，`render_page` 只依此判定；`tests/security/test_p7_limits.py::test_document_level_limit_still_renders` 加上「文件層級超限時 S03 仍拒絕渲染」；把判定改回 `87ec3b2` 的條件後該測試失敗（反向驗證 M25）。

## 驗證執行紀錄

- 回歸測試：2026-11-05 於本機 Windows、HEAD `8ca60b2` 執行 `uv run pytest -p no:cacheprovider tests/security/test_p7_limits.py tests/security/test_ipc_fuzz.py::test_request_timeout_is_total tests/integration/test_crash_injection.py::test_overwrite_readonly_leaves_no_readonly_temp`，13 passed。沒有在 `0533432` 上執行這些測試，所以未確認修正前會失敗；macOS 未執行（f002 的測試在 macOS 為 skip）。
- 單獨檢查：f004 在暫存目錄計時新舊正規表示式（不匯入產品碼）；f001 以標準函式庫 zlib 確認中段毀損時 `decompress` 拋錯、不回傳該次輸出。兩者都不是 PDF，也沒有寫入 repo。
- 本報告對 MuPDF／qpdf 行為的推論（f001 毀損 Flate 的前段會被下一個過濾器處理、f009 修復差異）沒有讀 C／C++ 原始碼確認。
