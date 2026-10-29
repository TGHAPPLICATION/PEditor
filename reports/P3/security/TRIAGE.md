# Triage Report

15 in -> 0 duplicates, 14 false positives, 1 confirmed (0 high / 0 med / 1 low), 0 need manual test

Context: interactive (P1 interview answers reused; same product and trust boundary); environment = offline single-user desktop app, untrusted PDFs and worker output, operator flags trusted, app-written drafts may be corrupted but other same-user processes are not a boundary; scoring = derived HIGH/MEDIUM/LOW; noise tolerance = recall; 2-vote verification (no split votes, so no tie-break). Input: `VULN-FINDINGS.json` (scanner ids F-001..F-015 map to f001..f015).

## Act on these

### [LOW] Pure-Python pixel loop over up to 50 MP per edited page lets a crafted PDF make Save exceed the 30 s timeout  (f015 / F-015)
`src/peditor/worker/export.py:249` | algorithmic complexity | claimed LOW (alignment 0) | confidence 6.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions:**
- User opens an attacker-crafted PDF with a very large page (~3400 pt or more square) and an editable text run at a very large font size
- User edits that run and saves (export always runs visual_check on edited pages)
**Threat-model match:** T5 resource exhaustion (bounded by the 30 s timeout and worker restart)
**Why:** export_document always runs visual_check on edited pages (export.py:279); zoom keeps large pages near MAX_RENDER_PIXELS=50 MP instead of refusing them (export.py:218), and _outside_pixels walks every x of every differing row in pure Python with a generator per pixel, even inside the mask (249-260). No page-size or font-size limit on this path (analyzer.py:354, 393 only limits render_page). A crafted huge page with huge editable text costs 10^7-5*10^7 iterations, beyond REQUEST_TIMEOUT_S=30, so Save always fails for that document. Same class as P2 f014.
**Reachability evidence:** src/peditor/worker/export.py:279
**Outcome:** fixed — visual_check renders at most VISUAL_MAX_PIXELS=12 MP (zoom reduced until MuPDF's rounded-up pixmap fits); _outside_pixels compares outside-mask segments as bytes, never reads mask pixels and stops once the count exceeds the limit；回歸測試 `tests/security/test_p3_scan_regressions.py`（3 項，驗證工作量上限而非牆鐘時間：渲染像素 ≤12 MP、遮罩內像素不逐點讀取、超標即停）。修正前程式（commit 1440555）：渲染 50,013,184 像素而失敗，另兩項因函式介面不同而失敗；修正前 visual_check 實測耗時依機器負載 4～15 秒

## Dropped

| id | title | file:line | why dropped |
| --- | --- | --- | --- |
| f001 | Draft JSON gets no schema check: a malformed draft crashes list_drafts on every launch and leaves recover_draft half-done | `src/peditor/core/drafts.py:65` | implausible_trigger; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f002 | The 7-day expiry never triggers when saved_at is NaN, Infinity, or in the future | `src/peditor/core/drafts.py:105` | implausible_trigger; rule 16 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f003 | list() reports the draft_id written inside the file, not the filename, so discard or recover can act on a different draft | `src/peditor/core/drafts.py:80` | implausible_trigger; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f004 | recover_draft opens the raw path stored in the draft file before any validation | `src/peditor/core/service.py:255` | implausible_trigger; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f005 | Main process takes revision numbers and plan ids from the worker without checking them, and updates the log before reading new_revision | `src/peditor/core/service.py:177` | implausible_trigger/not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f006 | Command log keeps a reference to the caller's editable_region list | `src/peditor/core/service.py:164` | implausible_trigger; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f007 | apply_edit, undo and redo report failure after the edit is committed when saving the draft fails | `src/peditor/core/service.py:334` | implausible_trigger; rule 2 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f008 | Undo and worker-restart restore replay the whole log in one request with a fixed 30 s timeout, so edits can become unsaveable | `src/peditor/core/service.py:355` | intentional_behavior/not_actionable; rule 3 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f009 | No-overwrite rule is enforced only by an earlier check; os.replace always clobbers the destination | `src/peditor/export/transaction.py:98` | implausible_trigger; rule 16 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f010 | Raw OSError with the full path escapes the save transaction; fsync failure after replace reported as failure | `src/peditor/export/transaction.py:47` | implausible_trigger/not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f011 | A temp file with the full document can stay in the user's folder indefinitely when cleanup fails | `src/peditor/export/transaction.py:124` | intentional_behavior/not_actionable; rule 3 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f012 | Overwrite by rename replaces the destination's mode/ACL with the temp file's defaults | `src/peditor/export/transaction.py:98` | not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f013 | Visual-check mask defaults to glyph boxes that an embedded font can inflate | `src/peditor/worker/edit.py:298` | duplicate; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f014 | text_check is a whole-page substring test, so text already elsewhere on the page satisfies it | `src/peditor/worker/export.py:198` | intentional_behavior; rule 3 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |

## Correctness defects confirmed in code (dropped as security findings)

Verifiers confirmed the mechanism exists but found no security impact (no untrusted input reaches it, the worker is already untrusted, or the result is a nuisance only). Listed for engineering follow-up, not as vulnerabilities.

| id | defect | suggested owner phase |
| --- | --- | --- |
| f001 | 草稿 JSON 無結構檢查：缺鍵使 `list()` KeyError；`recover_draft` 只攔 ServiceError，log／position 型別錯誤時已開啟的文件不會關閉 | P4（UI 啟用草稿前） |
| f007 | `_advance` 在 revision 已前進後才存草稿，寫草稿失敗時回報例外但編輯已套用 | P4（UI 啟用草稿前） |
| f008 | undo／worker 重啟還原／草稿復原以單一請求重播整個 log，步數多時可超過 30 秒逾時並反覆失敗；還原失敗時 close_document 的錯誤會蓋過原錯誤 | P4（量測後決定分段重播或 log＋快照，需 ADR） |
| f010 | `file_state`／暫存檔 hash／目錄 fsync 的 OSError 未轉為 ProtocolError，訊息含完整路徑（違反 CLAUDE.md）；fsync 失敗發生在 replace 之後時誤報失敗 | P3 收尾或 P4 |
| f006 | `plan_text_edit` 以參照保存呼叫端的 editable_region，呼叫端之後改動會影響重播 | P4（UI 呼叫端） |
| f009 | `overwrite=False` 時 `os.replace` 仍會取代在最後檢查後才出現的檔案（非原子的不覆寫） | P7 |
| f011 | 暫存檔刪除失敗時只靠下次寫入同資料夾清除 | P7 |
| f012 | 覆寫既有檔後，原檔的權限／ACL 被暫存檔預設值取代 | P7 |
