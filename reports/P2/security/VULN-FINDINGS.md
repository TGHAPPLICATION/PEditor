# VULN-FINDINGS（P2 靜態掃描）

- 技能：vuln-scan (defending-code-reference-harness@d3bea6b) --no-score，依 .claude/skills/vuln-scan/SKILL.md 手動執行（本工作階段無法載入 repo 技能）；掃描時間：2026-10-22T06:49:55+00:00；範圍：P2 新增／修改的 `src/` 程式，5 個焦點區域
- 合計 24 項（HIGH 0／MEDIUM 7／LOW 17，低信心 5）。這些是**未經驗證的靜態候選**，驗證結果見 `TRIAGE.md`。

| id | severity | category | file:line | title |
| --- | --- | --- | --- | --- |
| F-001 | MEDIUM | data-integrity / revision race across worker restart | `src/peditor/core/service.py:201` | Revision restarts at 0 after worker restart; expected_revision can approve a document that silently lost applied edits |
| F-002 | MEDIUM | integrity / shared-object modification | `src/peditor/worker/edit.py:328` | _shared_stream misses same-page duplicate /Contents entries and Form-XObject/annotation-AP reuse of the target content stream |
| F-003 | MEDIUM | integrity / non-atomic state mutation | `src/peditor/worker/edit.py:349` | Failed apply_edit leaves the working document half-edited (stream/resources mutated before checks); later export/commit includes it |
| F-004 | MEDIUM | integrity / overflow-check bypass | `src/peditor/worker/edit.py:412` | Mode A pure insertion at end of TJ inserts after trailing TJ numbers, diverging from planned geometry (TEXT_OVERFLOW bypass) |
| F-005 | MEDIUM | integrity: wrong glyph rendered while mode A reports success | `src/peditor/worker/fonts.py:113` | Mode A selects codes from attacker /ToUnicode and checks glyphs via a mapping different from the renderer's |
| F-006 | MEDIUM | integrity / check bypass (assistive-tech text retains old content) | `src/peditor/worker/tagged.py:146` | Alt/E/ActualText check trusts /ParentTree and /P back-links, which can disagree with the /K tree |
| F-007 | MEDIUM | integrity / partial ActualText sync | `src/peditor/worker/tagged.py:176` | Duplicate MCID in holder /K: only last copy rewritten, old text remains in /ActualText |
| F-008 | LOW | compromised-worker response handling (no schema validation) | `src/peditor/cli.py:97` | Main process uses worker results without schema validation; worker keys override main-process report fields |
| F-009 | LOW | sensitive data exposure in sidecar output | `src/peditor/cli.py:107` | edit-text writes removed original text in plaintext to plan.json/validation.json beside output |
| F-010 | LOW | path handling across IPC (spec §7 deviation) | `src/peditor/core/service.py:156` | export_document passes raw caller path to worker; spec §7 requires destination_token |
| F-011 | LOW | integrity / overflow-check bypass | `src/peditor/worker/edit.py:162` | Overflow check tests only baseline start/end; negative widths or Tc let intermediate glyphs leave the region |
| F-012 | LOW | integrity / validation bypass | `src/peditor/worker/edit.py:236` | _between_pieces checks nothing when runs come from different occurrences of the same stream or op_index not increasing |
| F-013 | LOW | integrity / overflow-check weakness | `src/peditor/worker/edit.py:297` | Default allowed_change_mask covers whole target runs, not the selected glyphs |
| F-014 | LOW | algorithmic complexity | `src/peditor/worker/export.py:76` | content_diff runs quadratic difflib over every content stream of every page |
| F-015 | LOW | validation logic (fail-closed DoS) | `src/peditor/worker/export.py:136` | Incremental check counts raw 'startxref' bytes; attacker bytes block every export |
| F-016 | LOW | validation bypass | `src/peditor/worker/export.py:163` | Export computes content/resource diffs but never checks them against the applied plans |
| F-017 | LOW | file handling / partial output | `src/peditor/worker/export.py:167` | Failed write leaves a partial PDF at the destination |
| F-018 | LOW | integrity: generated ToUnicode loses characters | `src/peditor/worker/fontb.py:134` | Mode B ToUnicode keeps only the last character when two characters map to the same Noto glyph |
| F-019 | LOW | integrity: blank glyph accepted as present | `src/peditor/worker/fonts.py:268` | Outline check accepts composites/degenerate paths that render blank |
| F-020 | LOW | integrity: wrong glyph decision (CID vs GID) | `src/peditor/worker/fonts.py:287` | CID-keyed CFF with one ToUnicode code missing from charset falls back to code-as-GID |
| F-021 | LOW | algorithmic complexity (untrusted font program) | `src/peditor/worker/fonts.py:297` | calcBounds interprets attacker CFF charstrings with unbounded subroutine fan-out |
| F-022 | LOW | ReDoS / algorithmic complexity | `src/peditor/worker/fonts.py:359` | parse_cmap lazy regexes quadratic on unterminated beginbfchar/beginbfrange blocks (4 MiB cap still allows ~1e11 steps) |
| F-023 | LOW | exception escaping / plan-apply inconsistency | `src/peditor/worker/fonts.py:374` | ToUnicode codes outside the font code space reach encode; plan ready but apply crashes |
| F-024 | LOW | unbounded memory (decompress before size check) | `src/peditor/worker/fonts.py:393` | ToUnicode/CIDToGIDMap/font programs fully decompressed before limits; CIDToGIDMap re-inflated per glyph check |

### F-001（掃描代號 F-05-01）

- MEDIUM／信心 0.4／`src/peditor/core/service.py:201`

After restart _doc_call silently reopens original at revision 0; revision numbers repeat; expected_revision None skips check.

**Exploit**：Edit A (rev1) -> malicious page forces timeout/restart -> reopen rev0 -> edit B -> export with expected_revision=1 succeeds without A.

**建議**：Mark document reset after restart: fail later calls (REVISION_CONFLICT/WORKER_FAILED) until explicit reopen, or epoch; make expected_revision mandatory for plan/apply/export.

### F-002（掃描代號 F-01-01；重複：F-02-01）

- MEDIUM／信心 0.65／`src/peditor/worker/edit.py:328`

_shared_stream only scans other pages' /Contents. (a) the same stream listed twice in the target page's /Contents (interpreter executes each entry; two TextRuns share stream/op_index; different fonts possible) and (b) the page content stream also referenced as a Form XObject (Do) or annotation /AP are not detected; _rewrite rewrites the shared instruction in place so every other drawing changes; content_diff only diffs /Contents so (b) is not reported.

**Exploit**：Page-1 content stream also used as Form XObject on page 3 (or listed twice on page 1 under different CTM/font); editing a word on page 1 silently changes page 3 / the second instance (possibly garbage glyphs).

**建議**：Count all references to the target stream objgen (all pages' /Contents including same page, /XObject resources recursively, annotation /AP); refuse SHARED_RESOURCE_UNSAFE if >1, or copy-on-write the stream.

### F-003（掃描代號 F-02-02）

- MEDIUM／信心 0.5／`src/peditor/worker/edit.py:349`

_rewrite mutates page Resources (mode B) and writes the stream before ActualText sync check and before all _rewrite_op checks; no rollback; server keeps document; export_document serializes dirty pike. Direct (non-indirect) ActualText holder gives objgen (0,0) and fails after rewrite.

**Exploit**：Tagged PDF with direct struct element holding /ActualText: apply rewrites content then fails; user exports -> new glyphs with old /ActualText.

**建議**：Make apply transactional (validate all first, or snapshot working bytes and restore on exception); reject non-indirect holder in tagged.py.

### F-004（掃描代號 F-01-02）

- MEDIUM／信心 0.6／`src/peditor/worker/edit.py:412`

For g0==len(glyphs) the plan's start = last glyph origin + advance (ignores trailing TJ number) but _rewrite_op replace sets lo=hi=len(tokens), placing new glyphs after trailing numbers; mode B uses positions[-1]+1 correctly.

**Exploit**：[(Amount:) -60000] TJ; appending text: plan reports in-region, glyphs drawn ~60 em away.

**建議**：Insert at positions[-1]+1 when g0==len(positions) (match split_b); regression test with trailing TJ number.

### F-005（掃描代號 F-03-03）

- MEDIUM／信心 0.5／`src/peditor/worker/fonts.py:113`

encode reverse-maps ToUnicode only; single-byte TrueType glyph lookup uses (3,1)+ToUnicode char; base14 has_glyph/width use ToUnicode char not /Encoding; Type0 accepts any outlined CID regardless of which character it draws.

**Exploit**：ToUnicode maps code 0x31->'9'; editing 100->900 emits 0x31 rendered as '1'; plan/extraction say 900, viewers show 100.

**建議**：Derive code->glyph like the renderer (Encoding/Differences->glyph name->cmap/post; CIDToGIDMap/charset) and require ToUnicode to agree with an independent source; refuse mode A on disagreement.

### F-006（掃描代號 F-04-01）

- MEDIUM／信心 0.5／`src/peditor/worker/tagged.py:146`

Element found only via ParentTree; climbs attacker-controlled /P; no verification that element's /K lists the MCID or chain reaches StructTreeRoot. (a) ParentTree points to decoy element without /Alt while real /K owner has /Alt/ActualText; (b) leaf /P null -> real ancestor with /Alt never examined. Negative MCID indexes from end. No ADR-0017 post-save validation in product code.

**Exploit**：/P element with /Alt containing old name/ID owns MCID 0 in /K; ParentTree maps MCID 0 to orphan /Span; edit succeeds, /Alt still has old text.

**建議**：Cross-validate ParentTree element lists the MCID in /K and /P chain consistent with /K up to StructTreeRoot; reject negative MCID; ideally walk /K from root collecting all covering elements; add post-save checks.

### F-007（掃描代號 F-04-02）

- MEDIUM／信心 0.6／`src/peditor/worker/tagged.py:176`

_mcids_under does not dedupe; covered=[5,5] doubles text and offset overwritten to last copy; ActualText 'OLDOLD' passes equality; result 'OLDNEW'.

**Exploit**：/Span /K [0 0] with doubled ActualText; edit reports ActualText synced but old text remains.

**建議**：Reject duplicate MCIDs in covered list (UNSUPPORTED_FEATURE); verify after sync that old text no longer present / equality with new content.

### F-008（掃描代號 F-05-04）

- LOW／信心 0.3／`src/peditor/cli.py:97`

KeyError/TypeError tracebacks; {**exported} lets worker override source_sha256; output_hash trusted from worker.

**Exploit**：Compromised worker forges validation.json attesting clean export.

**建議**：Schema-validate results (WORKER_FAILED on mismatch); main-process fields last/nested; compute output_hash in main process.

### F-009（掃描代號 F-05-03）

- LOW／信心 0.35／`src/peditor/cli.py:107`

plan contains old_text; validation content_changes contain old operator bytes; write_text follows symlinks/overwrites.

**Exploit**：Redacting an ID then sharing the output folder leaks the ID via plan.json/validation.json.

**建議**：Omit old text/operands by default (hashes/lengths), opt-in flag; exclusive create for sidecars.

### F-010（掃描代號 F-05-02）

- LOW／信心 0.5／`src/peditor/core/service.py:156`

Worker writes to any .pdf path not existing (O_EXCL safe vs TOCTOU); no canonicalization, UNC/device not rejected; worker holds write authority.

**Exploit**：Future less-trusted caller or sandboxed worker could write to UNC share (outbound SMB) / device path.

**建議**：Main process validates destination (reject UNC/device/\\?\, require existing parent) and writes bytes/temp itself (P3 transaction).

### F-011（掃描代號 F-01-04）

- LOW／信心 0.35／`src/peditor/worker/edit.py:162`

new_adv sums attacker-controlled widths and Tc/Tw; only start and end points checked against region.

**Exploit**：Codes with alternating-sign advances: endpoints in mask, intermediate glyphs outside.

**建議**：Check every cumulative glyph origin, or reject negative effective advances.

### F-012（掃描代號 F-02-07）

- LOW／信心 0.3／`src/peditor/worker/edit.py:236`

Slice instructions[first.op_index+1 : last.op_index] empty if last<=first; same stream listed twice in /Contents allows cross-occurrence span.

**Exploit**：/Contents [S T S]: span across occurrences passes, edits delete glyphs in both occurrences.

**建議**：Require same occurrence and strictly increasing op_index (or reject duplicate stream occurrences entirely, cf. F-01-01).

### F-013（掃描代號 F-01-03）

- LOW／信心 0.45／`src/peditor/worker/edit.py:297`

_selection_box uses all glyph bboxes of each target run, so a longer replacement mid-run can overlap following text without TEXT_OVERFLOW when no editable_region is given.

**Exploit**：'Pay to: ACME Ltd. Amount 100' single Tj; 100->100,000 overlaps following glyphs yet reported within mask.

**建議**：Default region from glyphs [g0,g1) of change pieces only, or require editable_region.

### F-014（掃描代號 F-02-04）

- LOW／信心 0.7／`src/peditor/worker/export.py:76`

SequenceMatcher autojunk=False on all pages incl. unedited; N identical ops -> O(N^2); MAX_CONTENT_OPERATORS not applied.

**Exploit**：Page 2 with 200k identical path ops -> every export times out.

**建議**：Diff only streams whose decoded bytes differ; prefix/suffix trim; cap operator count (RESOURCE_LIMIT).

### F-015（掃描代號 F-02-06）

- LOW／信心 0.4／`src/peditor/worker/export.py:136`

data.count(b'startxref') != 1 matches bytes inside uncompressed/filtered stream data or Info strings.

**Exploit**：JPEG COM segment containing 'startxref' -> export always VALIDATION_FAILED.

**建議**：Structural check: /Prev in trailer and single xref section (parse final startxref only).

### F-016（掃描代號 F-02-03）

- LOW／信心 0.5／`src/peditor/worker/export.py:163`

Write decision depends only on qpdf/incremental/unreachable/repair/page count; changes outside planned streams/ops/pages or undeclared resource changes are not rejected.

**Exploit**：With F-01-01 PDF, export reports ok while content_changes lists an unedited page.

**建議**：Record expected change set per committed plan; VALIDATION_FAILED on any change outside it.

### F-017（掃描代號 F-02-05）

- LOW／信心 0.6／`src/peditor/worker/export.py:167`

OSError during write/flush/fsync raises SAVE_FAILED without unlinking the partially written file (spec §7: no partial output); retry then blocked by 'exists'.

**Exploit**：Disk full mid-write leaves truncated PDF that may be mistaken for the saved document.

**建議**：Write temp + fsync + exclusive rename (P3), or unlink destination on failure.

### F-018（掃描代號 F-03-08）

- LOW／信心 0.3／`src/peditor/worker/fontb.py:134`

dict(zip(codes, text)) collapses distinct code points sharing a glyph.

**Exploit**：U+2F00 and U+4E00 in new text extract as the same character.

**建議**：Detect conflicting duplicates; reject or give distinct codes.

### F-019（掃描代號 F-03-05）

- LOW／信心 0.4／`src/peditor/worker/fonts.py:268`

TrueType numberOfContours!=0 accepts composites with empty components; CFF calcBounds not None accepts zero-area paths.

**Exploit**：Subset keeps digits as composites to empty glyph; mode A succeeds, renders blank.

**建議**：Require non-zero-area bounds after resolving composites (bounded).

### F-020（掃描代號 F-03-04）

- LOW／信心 0.45／`src/peditor/worker/fonts.py:287`

by_index chosen for ROS fonts when any mapped code is not in charset; renderers use charset; also odd-length CIDToGIDMap last code reads 1 byte.

**Exploit**：Charset CIDs blank but same-numbered GIDs outlined; one bogus ToUnicode code forces GID interpretation; edit renders blank/.notdef.

**建議**：Require charset for ROS fonts unless ALL mapped codes fail CID lookup and resolve by index consistently (justify P0 fixtures); treat odd-length CIDToGIDMap as malformed.

### F-021（掃描代號 F-03-02）

- LOW／信心 0.55／`src/peditor/worker/fonts.py:297`

fontTools op_callsubr has no depth/operation limit; N^d fan-out per glyph; not cached; called per char per candidate code.

**Exploit**：CFF glyph calling 20-deep chain of subrs each calling next 4 times -> plan hangs until timeout.

**建議**：Bounded custom charstring walker (depth<=10, op budget) or no interpretation; memoize per glyph.

### F-022（掃描代號 F-03-01）

- LOW／信心 0.7／`src/peditor/worker/fonts.py:359`

re.findall(beginbfchar(.*?)endbfchar) with many begin tokens and no end scans to end each time; same for bfrange array pattern; runs during interpret() for every Tf. (Related to P1 F-022.)

**Exploit**：ToUnicode inflating to 4 MB of 'beginbfchar' with no terminator hangs page analysis until timeout; worker restart loses unsaved edits.

**建議**：Linear tokenizer / str.find-based block scan; stop at first unterminated block; cap blocks.

### F-023（掃描代號 F-03-06）

- LOW／信心 0.6／`src/peditor/worker/fonts.py:374`

parse_cmap accepts up to 4 hex digits for single-byte fonts and unbounded lo_i+i in bfrange array form; _regroup raises on >255 / >0xFFFF.

**Exploit**：Single-byte font ToUnicode <0141> <0041>; typing A gives ready mode A, apply -> WORKER_FAILED.

**建議**：Drop codes outside code space (0-255 single-byte, 0-0xFFFF two-byte); bound array form by hi_i.

### F-024（掃描代號 F-03-07）

- LOW／信心 0.4／`src/peditor/worker/fonts.py:393`

read_bytes before MAX_CMAP_BYTES; FontFile2/3 uncapped; glyph_name calls gid_map.read_bytes each call.

**Exploit**：Huge CIDToGIDMap re-inflated per character -> OOM/timeout.

**建議**：Cache CIDToGIDMap bytes per checker; cap sizes (P7 for general decompression limits).
