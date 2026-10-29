# VULN-FINDINGS（P3 靜態掃描）

- 技能：vuln-scan (defending-code-reference-harness@d3bea6b) --no-score，依 .claude/skills/vuln-scan/SKILL.md 手動執行；掃描時間：2026-10-29T07:30:00+00:00；範圍：P3 新增／修改的 `src/` 程式，4 個焦點區域
- 合計 15 項（HIGH 0／MEDIUM 0／LOW 15，低信心 4）。這些是**未經驗證的靜態候選**，驗證結果見 `TRIAGE.md`。
- worker 端寫入、讀回與部分檔清理路徑：掃描子代理人未發現問題（category=none，不列入）。

| id | severity | category | file:line | title |
| --- | --- | --- | --- | --- |
| F-001 | LOW | input-validation / type-confusion | `src/peditor/core/drafts.py:65` | Draft JSON gets no schema check: a malformed draft crashes list_drafts on every launch and leaves recover_draft half-done |
| F-002 | LOW | retention-bypass | `src/peditor/core/drafts.py:105` | The 7-day expiry never triggers when saved_at is NaN, Infinity, or in the future |
| F-003 | LOW | integrity / retention | `src/peditor/core/drafts.py:80` | list() reports the draft_id written inside the file, not the filename, so discard or recover can act on a different draft |
| F-004 | LOW | path-injection / untrusted-input | `src/peditor/core/service.py:255` | recover_draft opens the raw path stored in the draft file before any validation |
| F-005 | LOW | trust boundary / state desync | `src/peditor/core/service.py:177` | Main process takes revision numbers and plan ids from the worker without checking them, and updates the log before reading new_revision |
| F-006 | LOW | integrity | `src/peditor/core/service.py:164` | Command log keeps a reference to the caller's editable_region list |
| F-007 | LOW | error handling / state consistency | `src/peditor/core/service.py:334` | apply_edit, undo and redo report failure after the edit is committed when saving the draft fails |
| F-008 | LOW | algorithmic complexity / integrity | `src/peditor/core/service.py:355` | Undo and worker-restart restore replay the whole log in one request with a fixed 30 s timeout, so edits can become unsaveable |
| F-009 | LOW | toctou | `src/peditor/export/transaction.py:98` | No-overwrite rule is enforced only by an earlier check; os.replace always clobbers the destination |
| F-010 | LOW | information disclosure / error handling | `src/peditor/export/transaction.py:47` | Raw OSError with the full path escapes the save transaction; fsync failure after replace reported as failure |
| F-011 | LOW | data leakage / partial output | `src/peditor/export/transaction.py:124` | A temp file with the full document can stay in the user's folder indefinitely when cleanup fails |
| F-012 | LOW | permission regression | `src/peditor/export/transaction.py:98` | Overwrite by rename replaces the destination's mode/ACL with the temp file's defaults |
| F-013 | LOW | validation bypass | `src/peditor/worker/edit.py:298` | Visual-check mask defaults to glyph boxes that an embedded font can inflate |
| F-014 | LOW | validation bypass | `src/peditor/worker/export.py:198` | text_check is a whole-page substring test, so text already elsewhere on the page satisfies it |
| F-015 | LOW | algorithmic complexity | `src/peditor/worker/export.py:249` | Pure-Python pixel loop over up to 50 MP per edited page lets a crafted PDF make Save exceed the 30 s timeout |

### F-001：Draft JSON gets no schema check: a malformed draft crashes list_drafts on every launch and leaves recover_draft half-done

`src/peditor/core/drafts.py:65` · input-validation / type-confusion · LOW · confidence 0.8

DraftStore.load only checks that the value is a dict and saved_at is a number. list() (80-82) indexes draft_id/path/sha256/position directly, so one draft missing a key raises KeyError and hides all valid drafts for up to 7 days. recover_draft (service.py:250-276) opens draft['path'] first, then uses log/position unchecked: max(e['base_revision'] ...) and log[:position] raise TypeError/KeyError/ValueError, and only ServiceError is caught, so the just-opened document stays open. A negative or too-large position passes replay and leaves an inconsistent doc.position (redo IndexError), which _save_draft then writes back.

**情境：** A corrupted or planted draft file in %LOCALAPPDATA%\PEditor\drafts makes every list_drafts() call raise, or leaves an orphaned open document when the user selects it.

**建議：** Validate the schema in load() (draft_id == file stem, str path, 64-hex sha256, list of dicts with int base_revision >= 0 and dict params, int position in [0, len(log)], finite saved_at); treat failures as corrupt. In recover_draft, close the document on any exception.

### F-002：The 7-day expiry never triggers when saved_at is NaN, Infinity, or in the future

`src/peditor/core/drafts.py:105` · retention-bypass · LOW · confidence 0.7

_expired computes `not isinstance(saved,(int,float)) or now - saved > RETENTION_S`. json.loads accepts NaN/Infinity; NaN and +inf never compare as expired, and a future timestamp (clock skew) delays expiry by the skew. .tmp and unparsable files use st_mtime and have the same future-mtime weakness. Drafts contain the new plaintext, so this breaks the spec P3 retention rule and ADR-0020 §5.

**情境：** The clock was ahead when the draft was saved; after correction the draft with confidential text stays indefinitely. A planted saved_at: NaN makes a draft permanent.

**建議：** Reject NaN/Infinity (parse_constant), require math.isfinite, and treat saved_at in the future as expired/corrupt.

### F-003：list() reports the draft_id written inside the file, not the filename, so discard or recover can act on a different draft

`src/peditor/core/drafts.py:80` · integrity / retention · LOW · confidence 0.6

list() loads each file by its filename stem but returns data['draft_id'] from the contents without checking it matches. recover_draft and discard_draft then act on folder/<id>.json. A mismatch makes discard delete another draft (or nothing) while the listed draft stays, and recover open a different draft than the one shown.

**情境：** A corrupted A.json with draft_id B: the user discards the entry for A, B.json is deleted and A.json with its plaintext stays.

**建議：** Return the filename stem as draft_id, or reject files whose draft_id differs from the stem.

### F-004：recover_draft opens the raw path stored in the draft file before any validation

`src/peditor/core/service.py:255` · path-injection / untrusted-input · LOW · confidence 0.4

draft['path'] from the JSON file goes straight to open_document and the worker; type, absoluteness and UNC/device paths are not checked, and the SHA-256 comparison happens only after the worker has opened the file. On Windows a UNC path makes the worker contact an SMB host (breaking offline guarantee, leaking NTLM). Requires same-user write access to the drafts folder and the user choosing the draft.

**情境：** A planted draft with path \\attacker\s\report.pdf; when selected the worker connects over SMB before the hash mismatch rejects it.

**建議：** Require path to be a str absolute local path; reject UNC, \\?\ and \\.\ paths; require an existing regular file.

### F-005：Main process takes revision numbers and plan ids from the worker without checking them, and updates the log before reading new_revision

`src/peditor/core/service.py:177` · trust boundary / state desync · LOW · confidence 0.35

apply_edit/undo/redo set doc.revision = result['new_revision'] without checking it is doc.revision + 1; plan_text_edit stores plan_id and preconditions.revision from the worker. apply_edit truncates/appends the log and increments position before reading new_revision; a missing key leaves log advanced but revision not. When the plan entry is missing the main process raises while the worker is already at R+1. A compromised worker can return a stale new_revision so that after restart the restore uses an old revision number and caller-held target_ids/expected_revision match again.

**情境：** A compromised worker returns new_revision equal to an earlier revision, then crashes; after restore old target_ids pass revision checks against different content.

**建議：** Compute the next revision in the main process and require the worker value to match; validate plan ids and preconditions; read results before mutating the log; restart the worker on desync.

### F-006：Command log keeps a reference to the caller's editable_region list

`src/peditor/core/service.py:164` · integrity · LOW · confidence 0.3

plan_text_edit stores the caller's editable_region list object in params and logs that same dict. A later mutation by the caller silently changes what undo/redo/restore/drafts replay, including allowed_change_mask used by the export visual check.

**情境：** UI reuses its selection-rectangle list; after an undo or worker crash the replayed edit uses an enlarged region, widening the area ignored by the visual check.

**建議：** Copy/normalize parameters (list(map(float, region))) before storing.

### F-007：apply_edit, undo and redo report failure after the edit is committed when saving the draft fails

`src/peditor/core/service.py:334` · error handling / state consistency · LOW · confidence 0.4

_advance updates revision and clears plans, then _save_draft calls DraftStore.save which re-raises OSError. The worker has committed and the log/position are updated, but the caller receives an exception (not even a ServiceError).

**情境：** Drafts folder full or locked: the user sees an error, assumes the edit was not applied, and saves a file that contains it.

**建議：** Make draft persistence best-effort (catch OSError, report as warning) or save the draft before committing in-memory state.

### F-008：Undo and worker-restart restore replay the whole log in one request with a fixed 30 s timeout, so edits can become unsaveable

`src/peditor/core/service.py:355` · algorithmic complexity / integrity · LOW · confidence 0.5

undo sends log[:position-1] and the restart restore sends log[:position] as single replay requests under REQUEST_TIMEOUT_S=30. Each replayed command does a full reopen (edit.py:410 only to set the revision), _references walk, pike.save and reopen; cost is driven by the PDF. If the sum exceeds 30 s, undo times out, the worker restarts, and every later _doc_call (including export) repeats the failing restore; the except path's close_document on the new worker masks the original error.

**情境：** A large or object-heavy PDF makes each edit take 3-5 s; after about 10 edits undo times out and the document can no longer be saved.

**建議：** Replay in chunks or scale the timeout with command count; drop the redundant reopen; consider log+snapshot; do not mask the original error.

### F-009：No-overwrite rule is enforced only by an earlier check; os.replace always clobbers the destination

`src/peditor/export/transaction.py:98` · toctou · LOW · confidence 0.4

destination() rejects an existing file when overwrite=False and records state None; _check re-reads file_state before os.replace, which replaces unconditionally. A file created at the destination between the last check and os.replace is overwritten, contrary to ADR-0020 §3.4.

**情境：** A sync client writes a colleague's report.pdf into the folder right before the rename; it is overwritten without a conflict error.

**建議：** When state is None, use a non-clobbering rename (os.link+unlink on POSIX, os.rename on Windows).

### F-010：Raw OSError with the full path escapes the save transaction; fsync failure after replace reported as failure

`src/peditor/export/transaction.py:47` · information disclosure / error handling · LOW · confidence 0.5

file_state calls sha256_file without catching open errors (locked/unreadable destination); sha256_file(temp) raises FileNotFoundError if the worker reports success without a file; _fsync_dir can fail after os.replace succeeded. destination_token/export_document only translate ProtocolError and the CLI only catches ServiceError, so the OSError (with the full path) reaches the caller/stderr, and in the fsync case a completed save is reported as failed with the token not consumed.

**情境：** Exporting over a PDF locked by a viewer crashes with PermissionError containing the full path in stderr.

**建議：** Convert OSError to ProtocolError without paths; treat post-replace fsync failure as success with a warning and always consume the token.

### F-011：A temp file with the full document can stay in the user's folder indefinitely when cleanup fails

`src/peditor/export/transaction.py:124` · data leakage / partial output · LOW · confidence 0.35

_remove ignores every OSError; stale temps are only removed by a later commit into the same folder after 600 s. A worker still holding the handle after kill timeout, antivirus/indexer locks, or a main-process crash leave .~peditor-*.tmp.pdf next to the destination until the user saves into that folder again.

**情境：** A timed-out save in a synced folder leaves a full copy of the edited document that is synced to the cloud.

**建議：** Retry deletion, record failed temp paths in app state and clean at startup/exit, report a warning.

### F-012：Overwrite by rename replaces the destination's mode/ACL with the temp file's defaults

`src/peditor/export/transaction.py:98` · permission regression · LOW · confidence 0.25

The worker creates the temp with default permissions; os.replace swaps the directory entry, so an overwritten destination loses a restrictive mode (e.g. 0600), explicit ACL or ownership.

**情境：** A 0600 confidential.pdf in a group-readable directory becomes 0644 after an overwrite save.

**建議：** Copy the existing destination's mode to the temp before replace (best-effort ACL), or create temps 0600.

### F-013：Visual-check mask defaults to glyph boxes that an embedded font can inflate

`src/peditor/worker/edit.py:298` · validation bypass · LOW · confidence 0.4

Without editable_region, allowed_change_mask is the union of MuPDF char bboxes (_selection_box), derived from font ascender/descender which an embedded font controls; nothing bounds it. visual_check ignores all pixels inside it, so a crafted font can draw changes far from the baseline inside the inflated band. VISUAL_OUTSIDE_LIMIT is also a fraction of pixels, so at reduced zoom up to ~5000 pixels may change outside the mask.

**情境：** A font with +/-20000 unit metrics makes the replacement glyph also draw a minus sign 200 pt below; the default mask covers it and the save passes.

**建議：** Derive the default mask from computed baseline geometry and font size; clamp masks to the crop box; use an absolute pixel limit.

### F-014：text_check is a whole-page substring test, so text already elsewhere on the page satisfies it

`src/peditor/worker/export.py:198` · validation bypass · LOW · confidence 0.6

text_check tests whether the whitespace-stripped new text occurs anywhere in the whitespace-stripped page text, not within the edited region and not compared to the original. An existing (possibly invisible) copy satisfies it. The overlap skip drops an edit whenever a later edit's mask overlaps, and masks can be inflated (F-013).

**情境：** A page already contains hidden '1,000,000'; the user changes a visible amount to '1,000,000' with codes that extract incorrectly, and text_check still passes.

**建議：** Extract text clipped to the edit mask (page.get_text(clip=...)), or compare occurrence counts with the original; only skip when a later mask contains the earlier one.

### F-015：Pure-Python pixel loop over up to 50 MP per edited page lets a crafted PDF make Save exceed the 30 s timeout

`src/peditor/worker/export.py:249` · algorithmic complexity · LOW · confidence 0.55

visual_check renders two pixmaps of up to MAX_RENDER_PIXELS (50 MP) and _outside_pixels iterates every pixel of every differing row in Python, with a generator per pixel for mask spans. A huge page with very large text makes a one-character edit change thousands of full-width rows, giving 10^7-5*10^7 Python iterations per page; the request exceeds 30 s and the document can never be saved.

**情境：** One 3500x3500 pt page with 2000 pt text; changing '100' to '200' makes every save time out.

**建議：** Zero mask spans by slicing and compare rows as bytes, or use pixmap operations; cap the visual-check pixel budget below MAX_RENDER_PIXELS and return RESOURCE_LIMIT.
