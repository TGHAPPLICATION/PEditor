# Triage Report

23 in -> 0 duplicates, 15 false positives, 8 confirmed (0 high / 3 med / 5 low), 0 need manual test

Context: interactive; environment = offline single-user desktop app, untrusted PDFs and worker output, operator flags trusted but cwd contents untrusted; scoring = derived HIGH/MEDIUM/LOW; noise tolerance = recall; 3-vote verification (third vote only where the first two split).

## Act on these

### [MEDIUM] CIDFont /W range form expands an attacker-chosen range into a dict with no bound  (f001)
`src/peditor/worker/fonts.py:186` | unbounded-allocation | claimed MEDIUM (alignment +0) | confidence 8.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei 2, Claude 1)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (4):**
- Victim opens an attacker-supplied PDF
- A page uses Tf on a Type0 font
- Descendant /W holds a huge c_first c_last w range
- No OS memory cap on the worker (only the 30 s timeout)
**Threat-model match:** T5
**Why:** _cid_widths (fonts.py:186-187) expands attacker /W ranges unbounded, reached from any Tf (content.py:155->206->fonts.py:162); only the 30 s timeout limits it, so a tiny PDF can allocate many GB.

One user action (opening a few-hundred-byte PDF) drives a dict of billions of entries; availability-only impact bounded by the 30 s kill, but enough RAM to push the host into swap.
**Reachability evidence:** src/peditor/worker/content.py:155

### [MEDIUM] ToUnicode bfrange expansion unbounded per range and in total  (f005)
`src/peditor/worker/fonts.py:220` | unbounded-allocation | claimed MEDIUM (alignment +1) | confidence 6.5/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei 2, Claude 1)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (4):**
- Victim opens an attacker-supplied PDF
- A font with /ToUnicode is used on an analysed page
- CMap holds many wide bfranges with distinct lo
- No OS memory cap on the worker
**Threat-model match:** T5
**Why:** parse_cmap bfrange (fonts.py:209-221) unbounded per range and in total, no stream size cap (230); tiny Flate stream can exhaust memory before the 30 s kill.

A few-KB Flate stream expands to millions of dict entries within the timeout; base LOW raised one step for the direct T5 match.
**Reachability evidence:** src/peditor/worker/content.py:206

### [MEDIUM] Form XObject fan-out is unbounded: N^8 work and memory  (f004)
`src/peditor/worker/content.py:274` | algorithmic-complexity / unbounded-allocation | claimed MEDIUM (alignment +0) | confidence 6.5/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei 2, Claude 1)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (3):**
- Victim opens an attacker-crafted PDF (analysis runs on open)
- Nested Form XObjects up to depth 8, each calling the same child many times
- Leaf forms contain text/image operators so results accumulate
**Threat-model match:** T5
**Why:** _do (content.py:274-276) bounds only depth and ancestor cycles; k Do per level across 8 forms gives k^8 _execute calls, each re-parsing (117) and appending (239,270); only 30 s kill bounds it, no memory cap.

k^8 fan-out from a small file; only the request timeout bounds CPU and nothing bounds memory before the kill; T5 match with single-step delivery.
**Reachability evidence:** src/peditor/cli.py:37, src/peditor/worker/analyzer.py:325

### [LOW] Exponential traversal in _fields with shared or self-referencing /Kids (depth-bounded only)  (f009)
`src/peditor/worker/analyzer.py:141` | algorithmic-complexity | claimed LOW (alignment +0) | confidence 7.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei 2, Claude 1)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (4):**
- Victim opens an attacker-supplied PDF
- pikepdf opens it within page limits
- AcroForm /Fields contains a self-referencing or shared /Kids fan-out
- No signed field that would short-circuit any()
**Threat-model match:** T5
**Why:** _fields (analyzer.py:141-146) has no visited set unlike _action_kinds; /Kids [A A] yields ~2^33 items on every open; only the 30 s timeout stops it.

One worker pinned at 100% CPU until the 30 s kill; that PDF fails to open, host stays usable.
**Reachability evidence:** src/peditor/worker/analyzer.py:121, src/peditor/worker/server.py:33

### [LOW] Non-frozen worker launched with `python -m peditor.worker` puts cwd first on sys.path  (f011)
`src/peditor/core/service.py:39` | code-injection (module search path hijack) | claimed MEDIUM (alignment -2) | confidence 7.0/10
**Owner:** component: src/peditor/core/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei 2, Claude 1)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (3):**
- Non-frozen install (uv/pip); PyInstaller builds unaffected
- Attacker plants pymupdf.py/pikepdf.py/peditor/ in a folder via a channel other than the PDF
- Victim runs PEditor with that folder as the current directory
**Threat-model match:** T1 (partial)
**Why:** Non-frozen worker started as `python -m peditor.worker` (service.py:39,52-59) with no cwd/-I/-P, so cwd is first on sys.path; worker imports pymupdf/pikepdf (analyzer.py:18-19, fonts.py:15-16); planted modules in an untrusted folder execute as the user.

Real code execution path, but needs three preconditions including a second delivery channel; same exposure as most `python -m` tools. Cheap fix: -P/-I or a trusted cwd.
**Reachability evidence:** src/peditor/cli.py:29

### [LOW] Unbounded q-stack depth with growing clip lists gives quadratic memory  (f012)
`src/peditor/worker/content.py:137` | algorithmic-complexity / quadratic-memory | claimed LOW (alignment +1) | confidence 6.5/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei 2, Claude 1)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (3):**
- Victim opens an attacker-supplied PDF
- Content stream has N `re W n` followed by N `q`
- Blowup happens before the 30 s kill (no memory cap)
**Threat-model match:** T5
**Why:** Each q copies the whole clip list (content.py:88,137) which grows unbounded per W n (149); no caps; a small compressed stream forces O(N*M) allocation; timeout does not cap memory and no rlimit.

O(N^2) memory in the isolated worker, cut off by the watchdog; bounded, recoverable DoS.
**Reachability evidence:** src/peditor/worker/analyzer.py:325

### [LOW] Active-content scan misses outlines, AcroForm field /AA, many action types and annotation kinds  (f007)
`src/peditor/worker/analyzer.py:171` | classification-bypass | claimed MEDIUM (alignment -2) | confidence 6.5/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei 2, Claude 1)
**Verdict:** mitigated, votes {'true_positive': 2, 'false_positive': 1, 'cannot_verify': 0}
**Preconditions (3):**
- Victim opens a PDF whose JS/Launch sits only in /Outlines or parent-field /AA
- No other reject reason is present
- A future edit/save path keeps the action and a JS-capable viewer opens the output
**Threat-model match:** none
**Why:** _active_content never walks /Outlines or AcroForm field /AA; _action_kinds records only JavaScript/Launch; contradicts ADR-0007; impact is policy bypass, likely below MEDIUM.

Policy-classification gap (ADR-0007), not execution: no JS engine and no edit/save path yet. Must be fixed before an edit/save path ships.
**Reachability evidence:** src/peditor/worker/analyzer.py:135, src/peditor/worker/server.py:33

### [LOW] render_page pixmap size bounded only by DPI, not by pixel area  (f016)
`src/peditor/worker/analyzer.py:256` | unbounded-allocation | claimed LOW (alignment +1) | confidence 6.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei 2, Claude 1)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 1, 'cannot_verify': 0}
**Preconditions (3):**
- Victim opens an attacker-supplied PDF and pages are rendered
- Page box is huge (e.g. 14400 pt) within MuPDF limits
- Host lacks free RAM for a multi-GB pixmap
**Threat-model match:** T5
**Why:** render_page bounds only DPI (analyzer.py:254-256); attacker MediaBox drives get_pixmap to ~2.7 GB at default 150 dpi via cli.py:39; timeout/message caps act after allocation; memory limits deferred to P7.

Multi-GB pixmap in the isolated worker; temporary memory pressure until the timeout; add a pixel-area cap.
**Reachability evidence:** src/peditor/cli.py:39

## Dropped

| id | title | file:line | why dropped |
| --- | --- | --- | --- |
| f002 | Per-request timeout resets on every line; a compromised worker can hang the main process indefinitely | `src/peditor/core/service.py:224` | implausible_trigger; rule 13 (votes {'true_positive': 1, 'false_positive': 2, 'cannot_verify': 0}) |
| f003 | Owner-password-only encrypted PDF (empty user password) is not flagged and is classified support | `src/peditor/worker/analyzer.py:74` | not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f006 | Worker responses not schema-checked: crafted shapes raise non-ServiceError exceptions and skip restart | `src/peditor/core/service.py:242` | not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f008 | Signature detection ignores inherited /FT, fields deeper than 32 levels, and widgets not in /AcroForm/Fields | `src/peditor/worker/analyzer.py:150` | implausible_trigger; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f010 | Quadratic regex scanning in parse_cmap on crafted ToUnicode text | `src/peditor/worker/fonts.py:205` | already_handled; rule 3 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f013 | Lone surrogate code points from /Differences or bfrange increments make inspect_page fail with UnicodeEncodeError | `src/peditor/worker/fonts.py:238` | already_handled, not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f014 | Malformed font dictionaries raise uncaught exception types; whole page fails | `src/peditor/worker/fonts.py:154` | already_handled, not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f015 | Main process keys documents by worker-chosen document_id; a compromised worker can overwrite another document's handle | `src/peditor/core/service.py:111` | implausible_trigger; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f017 | Unsynchronized _docs / worker_id state across _doc_call, _restart, _ensure_worker, open/close | `src/peditor/core/service.py:169` | implausible_trigger; rule 16 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f018 | Huge operands produce inf/NaN matrices that bypass layout checks and cross IPC | `src/peditor/worker/content.py:142` | not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f019 | Non-dictionary /Resources raises AttributeError that escapes the per-operator handler and fails the whole request | `src/peditor/worker/content.py:193` | not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f020 | CLI prints worker-supplied error code without allow-list validation | `src/peditor/cli.py:43` | implausible_trigger; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f021 | analyze() trusts worker result shape/content; unvalidated bytes written as .png; uncaught exceptions print tracebacks | `src/peditor/cli.py:35` | not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f022 | page_geometry ignores inherited /CropBox and /UserUnit; may diverge from MuPDF geometry | `src/peditor/worker/analyzer.py:220` | not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f023 | find_text collects unbounded overlapping matches over worker-supplied glyphs | `src/peditor/core/locate.py:23` | implausible_trigger; rule 2 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
