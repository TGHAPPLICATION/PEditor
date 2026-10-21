# VULN-FINDINGS（P1 靜態掃描）

- 技能：vuln-scan (defending-code-reference-harness@d3bea6b), --no-score；掃描時間：2026-10-21T06:03:38+00:00；範圍：`src/` 18 檔（1,815 行），5 個焦點區域
- 合計 23 項（HIGH 0／MEDIUM 8／LOW 15，低信心 4）。這些是**未經驗證的靜態候選**，驗證結果見 `TRIAGE.md`。

| id | severity | category | file:line | title |
| --- | --- | --- | --- | --- |
| F-001 | MEDIUM | code-injection (module search path hijack) | `src/peditor/core/service.py:39` | Non-frozen worker launched with `python -m peditor.worker` puts cwd first on sys.path |
| F-002 | MEDIUM | timeout-bypass | `src/peditor/core/service.py:224` | Per-request timeout resets on every line; a compromised worker can hang the main process indefinitely |
| F-003 | MEDIUM | classification-bypass | `src/peditor/worker/analyzer.py:74` | Owner-password-only encrypted PDF (empty user password) is not flagged and is classified support |
| F-004 | MEDIUM | classification-bypass | `src/peditor/worker/analyzer.py:150` | Signature detection ignores inherited /FT, fields deeper than 32 levels, and widgets not in /AcroForm/Fields |
| F-005 | MEDIUM | classification-bypass | `src/peditor/worker/analyzer.py:171` | Active-content scan misses outlines, AcroForm field /AA, many action types and annotation kinds |
| F-006 | MEDIUM | algorithmic-complexity / unbounded-allocation | `src/peditor/worker/content.py:274` | Form XObject fan-out is unbounded: N^8 work and memory |
| F-007 | MEDIUM | unbounded-allocation | `src/peditor/worker/fonts.py:186` | CIDFont /W range form expands an attacker-chosen range into a dict with no bound |
| F-008 | MEDIUM | unbounded-allocation | `src/peditor/worker/fonts.py:220` | ToUnicode bfrange expansion unbounded per range and in total |
| F-009 | LOW | improper-input-validation | `src/peditor/cli.py:35` | analyze() trusts worker result shape/content; unvalidated bytes written as .png; uncaught exceptions print tracebacks |
| F-010 | LOW | sensitive-data-in-logs / terminal-escape-injection | `src/peditor/cli.py:43` | CLI prints worker-supplied error code without allow-list validation |
| F-011 | LOW | algorithmic-complexity | `src/peditor/core/locate.py:23` | find_text collects unbounded overlapping matches over worker-supplied glyphs |
| F-012 | LOW | logic-flaw | `src/peditor/core/service.py:111` | Main process keys documents by worker-chosen document_id; a compromised worker can overwrite another document's handle |
| F-013 | LOW | race-condition | `src/peditor/core/service.py:169` | Unsynchronized _docs / worker_id state across _doc_call, _restart, _ensure_worker, open/close |
| F-014 | LOW | improper-input-validation | `src/peditor/core/service.py:242` | Worker responses not schema-checked: crafted shapes raise non-ServiceError exceptions and skip restart |
| F-015 | LOW | algorithmic-complexity | `src/peditor/worker/analyzer.py:141` | Exponential traversal in _fields with shared or self-referencing /Kids (depth-bounded only) |
| F-016 | LOW | classification-correctness | `src/peditor/worker/analyzer.py:220` | page_geometry ignores inherited /CropBox and /UserUnit; may diverge from MuPDF geometry |
| F-017 | LOW | unbounded-allocation | `src/peditor/worker/analyzer.py:256` | render_page pixmap size bounded only by DPI, not by pixel area |
| F-018 | LOW | algorithmic-complexity / quadratic-memory | `src/peditor/worker/content.py:137` | Unbounded q-stack depth with growing clip lists gives quadratic memory |
| F-019 | LOW | input-validation / non-finite float across IPC | `src/peditor/worker/content.py:142` | Huge operands produce inf/NaN matrices that bypass layout checks and cross IPC |
| F-020 | LOW | improper-exception-handling | `src/peditor/worker/content.py:193` | Non-dictionary /Resources raises AttributeError that escapes the per-operator handler and fails the whole request |
| F-021 | LOW | improper-error-handling | `src/peditor/worker/fonts.py:154` | Malformed font dictionaries raise uncaught exception types; whole page fails |
| F-022 | LOW | redos | `src/peditor/worker/fonts.py:205` | Quadratic regex scanning in parse_cmap on crafted ToUnicode text |
| F-023 | LOW | improper-input-validation | `src/peditor/worker/fonts.py:238` | Lone surrogate code points from /Differences or bfrange increments make inspect_page fail with UnicodeEncodeError |

### F-001（F-05-01）Non-frozen worker launched with `python -m peditor.worker` puts cwd first on sys.path

`src/peditor/core/service.py:39` · code-injection (module search path hijack) · MEDIUM · confidence 0.55

**Description.** worker_command() returns [sys.executable, '-m', 'peditor.worker']; _WorkerProcess.__init__ (service.py:52-59) starts it with no cwd= and no -I/-P. With -m, Python prepends the current directory to sys.path, so peditor/ or pymupdf.py/pikepdf.py in the operator's cwd are imported by the worker before site-packages. The CLI entry (console script) has no cwd entry, so only the worker is exposed.

**Exploit scenario.** Victim extracts an attacker ZIP containing case.pdf plus pymupdf.py, cd's into it and runs `peditor analyze case.pdf --out out`; the worker imports the planted module and executes code as the user.

**Recommendation.** Launch the worker with `-I` (or `-P`/PYTHONSAFEPATH=1) and an explicit safe cwd.

### F-002（F-04-01）Per-request timeout resets on every line; a compromised worker can hang the main process indefinitely

`src/peditor/core/service.py:224` · timeout-bypass · MEDIUM · confidence 0.75

**Description.** _exchange loops on worker.lines.get(timeout=self.timeout); the timeout is per line. Lines whose request_id is neither the current id nor None hit `continue` with no deadline, while _call holds self._lock, blocking all other calls. The reader thread fills an unbounded queue.

**Exploit scenario.** Worker compromised via a MuPDF/qpdf bug emits {"request_id":"x",...} every second; UI/CLI freezes forever, timeout/restart never fires.

**Recommendation.** Use one absolute deadline per request; treat mismatched request_id as a protocol violation (restart + WORKER_FAILED); bound the queue.

### F-003（F-03-01）Owner-password-only encrypted PDF (empty user password) is not flagged and is classified support

`src/peditor/worker/analyzer.py:74` · classification-bypass · MEDIUM · confidence 0.7

**Description.** Encryption is detected only via mu.needs_pass and pikepdf.PasswordError. A PDF with an empty user password and owner restrictions opens in both without a password, so flags['encrypted'] stays False and status is support; mu.is_encrypted / pike.is_encrypted are never checked.

**Exploit scenario.** A 'no modification' restricted PDF is marked editable; a later pikepdf save() drops encryption and permission restrictions.

**Recommendation.** Also reject when mu.is_encrypted or pike.is_encrypted (or /Encrypt in trailer).

### F-004（F-03-02）Signature detection ignores inherited /FT, fields deeper than 32 levels, and widgets not in /AcroForm/Fields

`src/peditor/worker/analyzer.py:150` · classification-bypass · MEDIUM · confidence 0.6

**Description.** _is_signed requires /FT /Sig and /V on the same dict; /FT is inheritable. _fields stops at depth > 32 silently. Only /AcroForm/Fields and /Perms are scanned, not page /Annots widgets.

**Exploit scenario.** A signed PDF whose /FT /Sig sits on a parent field is classified editable; editing invalidates the signature without SIGNED_DOCUMENT rejection.

**Recommendation.** Resolve inherited /FT; treat any /V with /Type /Sig or /ByteRange as signed; scan page widgets; treat depth overflow as reject.

### F-005（F-03-03）Active-content scan misses outlines, AcroForm field /AA, many action types and annotation kinds

`src/peditor/worker/analyzer.py:171` · classification-bypass · MEDIUM · confidence 0.65

**Description.** _active_content checks Root /OpenAction, Root/page /AA, /Names JavaScript/EmbeddedFiles keys, page annotation /A,/AA and FileAttachment. It does not walk /Outlines actions, field-level /AA on non-widget fields, action types other than JavaScript/Launch (SubmitForm, ImportData, GoToR, GoToE, Rendition, RichMediaExecute), RichMedia/Screen/Movie/Sound annotations, or action arrays.

**Exploit scenario.** JavaScript placed in a bookmark action or in a field /AA /K keystroke action yields a 'support' classification.

**Recommendation.** Walk outlines and all fields/annotations with cycle detection; use an allowlist of permitted action types; handle action arrays.

### F-006（F-01-01）Form XObject fan-out is unbounded: N^8 work and memory

`src/peditor/worker/content.py:274` · algorithmic-complexity / unbounded-allocation · MEDIUM · confidence 0.7

**Description.** _do caps depth (MAX_FORM_DEPTH=8) and direct cycles, but a Form may Do the same child any number of times; each visit re-parses the stream (no cache) and appends runs/images to self.result.

**Exploit scenario.** 8-level chain where each level contains ~100 '/Next Do'; a few KB file triggers ~100^8 executions, gigabytes of RAM before the 30 s timeout.

**Recommendation.** Add a per-interpret budget (operators, Form invocations, runs/images) and cache parsed instructions per objgen.

### F-007（F-02-01）CIDFont /W range form expands an attacker-chosen range into a dict with no bound

`src/peditor/worker/fonts.py:186` · unbounded-allocation · MEDIUM · confidence 0.8

**Description.** _cid_widths: for `c_first c_last w`, `for cid in range(first, last + 1): widths[cid] = value` with no cap; reached on any Tf using the font.

**Exploit scenario.** /W [0 4000000000 500] in a few-hundred-byte PDF makes the worker allocate tens of GB before the timeout.

**Recommendation.** Clamp CIDs to 0..65535 and cap entries, or store ranges lazily.

### F-008（F-02-02）ToUnicode bfrange expansion unbounded per range and in total

`src/peditor/worker/fonts.py:220` · unbounded-allocation · MEDIUM · confidence 0.7

**Description.** parse_cmap: lo/hi hex has no length limit; each range expands up to ~1.1M entries before chr() overflows; thousands of ranges in a small compressed stream build billions of entries. No decompressed-size cap.

**Exploit scenario.** 5,000 bfrange lines of ~1M entries each in a few-KB Flate stream exhaust memory.

**Recommendation.** Reject ranges with hi-lo > 255 or source > 4 hex digits; cap total entries and the ToUnicode stream size.

### F-009（F-05-03）analyze() trusts worker result shape/content; unvalidated bytes written as .png; uncaught exceptions print tracebacks

`src/peditor/cli.py:35` · improper-input-validation · LOW · confidence 0.3

**Description.** Only ServiceError is caught; malformed results raise KeyError/TypeError/binascii.Error; OSError messages include full output path; png_base64 not checked for PNG signature; NaN accepted into report.json.

**Exploit scenario.** Compromised worker returns non-PNG bytes or malformed structures; CLI writes arbitrary bytes as page PNG or dumps a traceback.

**Recommendation.** Validate results (page_index range, PNG signature, strict base64), catch Exception/OSError with fixed codes, allow_nan=False.

### F-010（F-05-02）CLI prints worker-supplied error code without allow-list validation

`src/peditor/cli.py:43` · sensitive-data-in-logs / terminal-escape-injection · LOW · confidence 0.35

**Description.** ServiceError.code comes from the worker response (service.py:245) unchecked; cli.py prints it verbatim to stderr; can carry document text, paths or terminal escape sequences.

**Exploit scenario.** Compromised worker returns an error code containing ESC sequences or document text; printed to terminal/CI logs.

**Recommendation.** Map codes not in ERROR_CODES|PROTOCOL_ERROR_CODES to WORKER_FAILED; use fixed local messages.

### F-011（F-05-04）find_text collects unbounded overlapping matches over worker-supplied glyphs

`src/peditor/core/locate.py:23` · algorithmic-complexity · LOW · confidence 0.15

**Description.** O(matches x len(wanted)) time/memory; glyph['c'] not type-checked so spans can misalign.

**Exploit scenario.** 1M identical glyphs and a 1,000-char repeated search hang the UI process.

**Recommendation.** Cap matches, non-overlapping search, require str for c, bound glyph count.

### F-012（F-04-03）Main process keys documents by worker-chosen document_id; a compromised worker can overwrite another document's handle

`src/peditor/core/service.py:111` · logic-flaw · LOW · confidence 0.45

**Description.** open_document stores self._docs[result['document_id']] without collision check; reopen-by-path then uses the wrong path; worker also supplies the sha256 used for the external-modification check.

**Exploit scenario.** Malicious doc B returns doc A's id; A's handle now refers to B's path/content.

**Recommendation.** Generate handles in the main process (uuid4); reject duplicate/ill-formed worker ids.

### F-013（F-04-04）Unsynchronized _docs / worker_id state across _doc_call, _restart, _ensure_worker, open/close

`src/peditor/core/service.py:169` · race-condition · LOW · confidence 0.4

**Description.** _doc_call reads/updates worker_id outside _lock; _restart/_ensure_worker iterate _docs while other threads mutate it; cancel() may kill a worker serving a later request.

**Exploit scenario.** Concurrent UI open/close during a worker restart raises RuntimeError or sends stale ids.

**Recommendation.** Hold _lock across _doc_call and _docs mutations; iterate over a copy; check target request under lock in cancel().

### F-014（F-04-02）Worker responses not schema-checked: crafted shapes raise non-ServiceError exceptions and skip restart

`src/peditor/core/service.py:242` · improper-input-validation · LOW · confidence 0.7

**Description.** decode only checks dict; response['result'] KeyError, error.get AttributeError if error is not a dict; forged codes/messages pass through; worker not restarted on these paths.

**Exploit scenario.** Compromised worker returns result [1] or error 'x'; main process raises TypeError/AttributeError, worker stays alive.

**Recommendation.** Validate per-operation schema; on violation restart and raise WORKER_FAILED; wrap unexpected exceptions.

### F-015（F-03-04）Exponential traversal in _fields with shared or self-referencing /Kids (depth-bounded only)

`src/peditor/worker/analyzer.py:141` · algorithmic-complexity · LOW · confidence 0.6

**Description.** _fields has no visited set; A /Kids [A A] yields ~2^33 items within the depth bound of 32.

**Exploit scenario.** Small crafted PDF pins the worker CPU until the 30 s timeout on every open.

**Recommendation.** Track visited objgen; budget total nodes; treat cycles as MALFORMED_DOCUMENT.

### F-016（F-03-06）page_geometry ignores inherited /CropBox and /UserUnit; may diverge from MuPDF geometry

`src/peditor/worker/analyzer.py:220` · classification-correctness · LOW · confidence 0.3

**Description.** Reads /CropBox only from the page dict; ignores /UserUnit; int(/Rotate) truncates; crop outside media yields inverted box.

**Exploit scenario.** Inherited CropBox causes mismatched coordinate frames for UI overlay (mostly fail-safe via glyph location check).

**Recommendation.** Use inherited attribute resolution or MuPDF's cropbox/rotation; reject UserUnit != 1; validate Rotate and non-empty crop.

### F-017（F-03-05）render_page pixmap size bounded only by DPI, not by pixel area

`src/peditor/worker/analyzer.py:256` · unbounded-allocation · LOW · confidence 0.45

**Description.** get_pixmap(dpi=dpi) with attacker-controlled page box/UserUnit; a 14400 pt page at 300 dpi requests ~10 GB.

**Exploit scenario.** Huge MediaBox page rendered at default DPI drives worker memory to many GB.

**Recommendation.** Compute pixel count before rendering; reject or clamp above a cap (e.g. 50 MP).

### F-018（F-01-02）Unbounded q-stack depth with growing clip lists gives quadratic memory

`src/peditor/worker/content.py:137` · algorithmic-complexity / quadratic-memory · LOW · confidence 0.55

**Description.** Each q copies gs (including the clip list); clips grow with each W n; no caps; ImageUse also copies clips.

**Exploit scenario.** 200k 're W n' then 200k 'q' in a compressible stream allocates ~4e10 list slots.

**Recommendation.** Cap q depth and clips per state; keep an intersected bbox instead of a list.

### F-019（F-01-03）Huge operands produce inf/NaN matrices that bypass layout checks and cross IPC

`src/peditor/worker/content.py:142` · input-validation / non-finite float across IPC · LOW · confidence 0.4

**Description.** _num is plain float(); multiply yields inf/NaN without exception; NaN CTM passes the analyzer's layout checks (comparisons with NaN are False); json.dumps allows NaN.

**Exploit scenario.** cm with 300-digit reals drives CTM to NaN; image reported as supported with NaN bboxes sent to the UI.

**Recommendation.** Reject non-finite/huge operands in _num; check finiteness after multiply; json.dumps(allow_nan=False).

### F-020（F-01-04）Non-dictionary /Resources raises AttributeError that escapes the per-operator handler and fails the whole request

`src/peditor/worker/content.py:193` · improper-exception-handling · LOW · confidence 0.4

**Description.** resources is only truthiness-checked; /Resources 5 makes resources.get raise AttributeError, not in the caught tuple; whole request returns WORKER_FAILED instead of a page-level MALFORMED_DOCUMENT.

**Exploit scenario.** PDF with /Resources 1 makes analysis of the file fail.

**Recommendation.** Normalize resources to pikepdf.Dictionary; widen the handler.

### F-021（F-02-05）Malformed font dictionaries raise uncaught exception types; whole page fails

`src/peditor/worker/fonts.py:154` · improper-error-handling · LOW · confidence 0.5

**Description.** DescendantFonts [/Foo] -> AttributeError; non-dict FontDescriptor -> AttributeError; escapes the Tf handler to server.py generic handler (WORKER_FAILED).

**Exploit scenario.** One malformed font resource blocks analysis of all text on the page.

**Recommendation.** Type-check objects; mark font unsupported on any parse error.

### F-022（F-02-03）Quadratic regex scanning in parse_cmap on crafted ToUnicode text

`src/peditor/worker/fonts.py:205` · redos · LOW · confidence 0.6

**Description.** Lazy `beginbfchar(.*?)endbfchar` with N unmatched begins is O(N*len); `\[[^\]]*\]` alternative also quadratic on unclosed brackets; stream size uncapped.

**Exploit scenario.** Few-MB ToUnicode of repeated 'beginbfrange <><>[' burns CPU until the timeout.

**Recommendation.** Cap stream length; linear tokenizer; bound array scans.

### F-023（F-02-04）Lone surrogate code points from /Differences or bfrange increments make inspect_page fail with UnicodeEncodeError

`src/peditor/worker/fonts.py:238` · improper-input-validation · LOW · confidence 0.55

**Description.** _glyph_name_unicode accepts uniD800-uniDFFF; bfrange increments can step into surrogates; _target_id encodes utf-8 -> UnicodeEncodeError -> WORKER_FAILED; if reaching protocol.encode it could escape serve().

**Exploit scenario.** /Differences [65 /uniD800] with (A) Tj makes the page permanently un-analyzable.

**Recommendation.** Reject surrogates and > 0x10FFFF; defensive encoding in _target_id; catch encode errors in serve().
