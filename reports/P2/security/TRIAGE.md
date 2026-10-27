# Triage Report

24 in -> 0 duplicates, 21 false positives, 3 confirmed (0 high / 0 med / 3 low), 0 need manual test

Context: interactive (P1 interview answers reused; same product and trust boundary); environment = offline single-user desktop app, untrusted PDFs and worker output, operator flags trusted but cwd contents untrusted; scoring = derived HIGH/MEDIUM/LOW; noise tolerance = recall; 2-vote verification with a 3rd tie-break vote where the first two split (f003, f012, f022). Input: `VULN-FINDINGS.json` (scanner ids F-001..F-024 map to f001..f024).

## Act on these

### [LOW] content_diff runs quadratic difflib over every content stream of every page  (f014 / F-014)
`src/peditor/worker/export.py:76` | algorithmic complexity | claimed LOW (alignment +1) | confidence 6.5/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei only)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (3):**
- User opens an attacker-crafted PDF with a content stream of ~1e5+ identical or repetitive operators
- User exports (no edit needed; export_document always runs content_diff on every stream)
- Open/analyze completes within its own limits before export
**Threat-model match:** T5 resource exhaustion (weak: bounded by the 30 s timeout and worker restart)
**Why:** export.py:76 SequenceMatcher(autojunk=False) on every stream incl. unedited pages; ~N^2 steps for N identical ops; no operator cap on this path (content.py:161 only, 1M per page); only bound is REQUEST_TIMEOUT_S=30 (limits.py:10, service.py:258-261) so export fails with RESOURCE_LIMIT after a full CPU timeout. Legitimate dense pages (maps/CAD) may also hit it.

A crafted PDF reliably drives SequenceMatcher(autojunk=False) to ~O(N^2) over uncapped operator lists; MAX_CONTENT_OPERATORS is only enforced in content.py:161. Impact is bounded by REQUEST_TIMEOUT_S=30 and kill/restart: that one document cannot be exported. Requires local open+export and is self-limiting, so LOW; claimed LOW is about right. Dense legitimate pages (maps/CAD) may also hit it, a usability concern.
**Reachability evidence:** src/peditor/cli.py:101, src/peditor/worker/export.py:163

### [LOW] Mode A pure insertion at end of TJ inserts after trailing TJ numbers, diverging from planned geometry (TEXT_OVERFLOW bypass)  (f004 / F-004)
`src/peditor/worker/edit.py:412` | integrity / overflow-check bypass | claimed MEDIUM (alignment -2) | confidence 6.5/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei only)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (4):**
- User opens an attacker-crafted (or unusual) PDF whose target run is a TJ array ending in a numeric adjustment, e.g. [(Amount:) -60000] TJ
- User performs a pure insertion at the end of that run (g0=g1=len(glyphs))
- Plan resolves to mode A replace, so edit.py:412 writes after the trailing number while edit.py:162 checked the planned point
- User applies and saves without re-rendering and noticing the misplaced text
**Threat-model match:** none
**Why:** For end-of-run insertion _start_origin (edit.py:323-325) places start at last glyph origin + advance, ignoring a trailing TJ number that content.py:216-217 shows does move the text position. TEXT_OVERFLOW (edit.py:162) uses that position, but _rewrite_op (edit.py:412) sets lo=hi=len(tokens), writing new glyphs after the trailing number; [(X) -60000] TJ gets a plan inside the region while drawn ~60 em away. Mode B correctly uses positions[-1]+1 (edit.py:424); nothing post-write checks allowed_change_mask.

The overflow check validates a start point that ignores the trailing TJ number while the rewrite places glyphs after it, with no post-write geometry check. Exploitation needs a crafted PDF plus a specific edit shape and the user not noticing, so 3+ preconditions with local interaction only. Outcome is misplaced text visible on re-render; MEDIUM inflated by about one level.
**Reachability evidence:** src/peditor/worker/edit.py:147, src/peditor/worker/span.py:151

### [LOW] _shared_stream misses same-page duplicate /Contents entries and Form-XObject/annotation-AP reuse of the target content stream  (f002 / F-002)
`src/peditor/worker/edit.py:328` | integrity / shared-object modification | claimed MEDIUM (alignment -2) | confidence 6.0/10
**Owner:** component: src/peditor/worker/; no CODEOWNERS; single-maintainer repo (git log: tghtaipei only)
**Verdict:** exploitable, votes {'true_positive': 2, 'false_positive': 0, 'cannot_verify': 0}
**Preconditions (4):**
- User opens an attacker-crafted PDF (local delivery)
- Target content stream is reused in a way _shared_stream misses: listed twice in the same page's /Contents, used as a Form XObject via Do, or as an annotation /AP (edit.py:328-337 skips the target page)
- User selects text inside that shared stream and the plan passes the other gates
- User approves the edit and exports; harm requires relying on the change report, which omits XObject-propagated changes
**Threat-model match:** none
**Why:** _shared_stream (edit.py:328-337) skips the target page and compares only other pages' /Contents; a stream listed twice on page 1 or reused as Form XObject via Do or /AP is not detected, while Form copies are rejected only as edit targets (analyzer.py:503). _rewrite (edit.py:376-383) mutates the shared instruction in place and _rewrite_op code check (edit.py:404) passes for duplicates. content_diff (export.py:62-111) compares only /Contents so the XObject-propagated change is unreported. Impact low: attacker gets only the user's typed text duplicated.

Needs local delivery plus the user selecting text inside the shared stream and approving the edit: 3+ preconditions, no remote path, so LOW. Integrity-only: the user's own edit also changes unselected copies of the stream and the change report omits them; no code execution, leakage or damage to the original. Claimed MEDIUM inflated by about one level.
**Reachability evidence:** src/peditor/worker/edit.py:106

## Dropped

| id | title | file:line | why dropped |
| --- | --- | --- | --- |
| f001 | Revision restarts at 0 after worker restart; expected_revision can approve a document that silently lost applied edits | `src/peditor/core/service.py:201` | already_handled/implausible_trigger; rule 3 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f003 | Failed apply_edit leaves the working document half-edited (stream/resources mutated before checks); later export/commit includes it | `src/peditor/worker/edit.py:349` | implausible_trigger; rule 13 (votes {'true_positive': 1, 'false_positive': 2, 'cannot_verify': 0}) |
| f005 | Mode A selects codes from attacker /ToUnicode and checks glyphs via a mapping different from the renderer's | `src/peditor/worker/fonts.py:113` | intentional_behavior; rule 3 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f006 | Alt/E/ActualText check trusts /ParentTree and /P back-links, which can disagree with the /K tree | `src/peditor/worker/tagged.py:146` | implausible_trigger/not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f007 | Duplicate MCID in holder /K: only last copy rewritten, old text remains in /ActualText | `src/peditor/worker/tagged.py:176` | not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f008 | Main process uses worker results without schema validation; worker keys override main-process report fields | `src/peditor/cli.py:97` | implausible_trigger/not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f009 | edit-text writes removed original text in plaintext to plan.json/validation.json beside output | `src/peditor/cli.py:107` | intentional_behavior; rule 3 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f010 | export_document passes raw caller path to worker; spec §7 requires destination_token | `src/peditor/core/service.py:156` | implausible_trigger; rule 8 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f011 | Overflow check tests only baseline start/end; negative widths or Tc let intermediate glyphs leave the region | `src/peditor/worker/edit.py:162` | not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f012 | _between_pieces checks nothing when runs come from different occurrences of the same stream or op_index not increasing | `src/peditor/worker/edit.py:236` | not_actionable; rule 12 (votes {'true_positive': 1, 'false_positive': 2, 'cannot_verify': 0}) |
| f013 | Default allowed_change_mask covers whole target runs, not the selected glyphs | `src/peditor/worker/edit.py:297` | not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f015 | Incremental check counts raw 'startxref' bytes; attacker bytes block every export | `src/peditor/worker/export.py:136` | not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f016 | Export computes content/resource diffs but never checks them against the applied plans | `src/peditor/worker/export.py:163` | already_handled/intentional_behavior; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f017 | Failed write leaves a partial PDF at the destination | `src/peditor/worker/export.py:167` | implausible_trigger; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f018 | Mode B ToUnicode keeps only the last character when two characters map to the same Noto glyph | `src/peditor/worker/fontb.py:134` | not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f019 | Outline check accepts composites/degenerate paths that render blank | `src/peditor/worker/fonts.py:268` | implausible_trigger/not_actionable; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f020 | CID-keyed CFF with one ToUnicode code missing from charset falls back to code-as-GID | `src/peditor/worker/fonts.py:287` | not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f021 | calcBounds interprets attacker CFF charstrings with unbounded subroutine fan-out | `src/peditor/worker/fonts.py:297` | already_handled; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f022 | parse_cmap lazy regexes quadratic on unterminated beginbfchar/beginbfrange blocks (4 MiB cap still allows ~1e11 steps) | `src/peditor/worker/fonts.py:359` | already_handled; rule 12 (votes {'true_positive': 1, 'false_positive': 2, 'cannot_verify': 0}) |
| f023 | ToUnicode codes outside the font code space reach encode; plan ready but apply crashes | `src/peditor/worker/fonts.py:374` | not_actionable; rule 12 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |
| f024 | ToUnicode/CIDToGIDMap/font programs fully decompressed before limits; CIDToGIDMap re-inflated per glyph check | `src/peditor/worker/fonts.py:393` | already_handled/implausible_trigger; rule 13 (votes {'true_positive': 0, 'false_positive': 2, 'cannot_verify': 0}) |

## Correctness defects confirmed in code (dropped as security findings)

Verifiers confirmed the mechanism exists but found no security impact (attacker already authors the PDF, operator-supplied input, or fail-closed). Listed for P2/P3 engineering follow-up, not as vulnerabilities.

| id | defect | suggested owner phase |
| --- | --- | --- |
| f003 | `apply_edit` mutates stream/Resources before the /ActualText check with no rollback; direct struct element (objgen 0,0) fails after rewrite (split vote 1-2) | P2 fix or P3 transaction |
| f012 | `_between_pieces` slice empty when `op_index` not increasing; cross-occurrence span on a stream listed twice in `/Contents` (split vote 1-2); same root cause as f002 | with f002 |
| f022 | `parse_cmap` lazy regex quadratic on unterminated `beginbfchar`/`beginbfrange`, bounded only by 30 s timeout (split vote 1-2) | P7 limits |
| f006 | ParentTree//P chain not cross-checked against /K; negative MCID indexes from end | P2 (ADR-0017 guard) |
| f007 | `_mcids_under` keeps duplicate MCIDs; ActualText sync leaves old text with a 'synced' warning | P2 (ADR-0017 guard) |
| f017 | failed write leaves a partial PDF at the destination (spec §7 'no partial output') | P3 transaction |
| f018 | mode B ToUnicode collapses code points sharing one Noto glyph | P2 |
| f023 | ToUnicode codes outside the font code space give a ready plan that fails at apply | P2 |
| f015 | raw `startxref` byte count can block export of a file containing that string | P2/P3 |
| f024 | ToUnicode/CIDToGIDMap/font programs inflated before size checks | P7 limits |
