# ADAS V4.0 — Controller, Contract & Repair Policy

## Scope
Only STEP 2–6; no Channel Audit, market/keyword research, vidIQ, STEP 1 or STEP 7. Five standalone skills are retained. `00_CONTROLLER_V4` is not a sixth skill. The reference corpus is packaged in STEP 5 without altering its texts.

## State chart
`CREATED` → `TITLE_LOCKED` → `OUTLINE_APPROVED` → `A_READY` → `B_READY` → `C_READY` → `AUDIT_IN_PROGRESS` → `PUBLISH_READY` → `EXPORTED`.

The Python CLI saves `project_state.json` under each project, tracking SHA256 and per-part repair cycles. Each `gate` command returns JSON, exit 0 on PASS or exit 2 on FAIL. Do not manually edit state. On any unsupported transition, stop with an error.

## Input/output contracts
| Stage | Required files | Work | Output |
|---|---|---|---|
| STEP 2 | seed, optional local history | single idea, choose DNA; heuristic originality check | `plans/idea.json`, `LOCKED_TITLE`, L1–L6 draft |
| STEP 3 | title, idea, references | coherent 20–24 scenes, 3 reveals, story bible | `plans/blueprint.json`, timelines, setup/payoff and proof chain |
| STEP 4-A | approved blueprint | narration A, part gate, handoff | `script/A.txt`, `script/A_HANDOFF.json` |
| STEP 4-B | previous part SHA and handoff | narration B, confirm continuity from A | `script/B.txt`, `script/B_HANDOFF.json` |
| STEP 4-C | prior part SHA/handoffs | narration C, pay title promise | `script/C.txt`, `script/C_HANDOFF.json` |
| STEP 5 | three clean parts + current hashes | two-pass audit, locks, repair tickets | `qa/audit.json` |
| STEP 4-PATCH | scoped tickets + current SHA | edit only failing original lines, no unapproved unlock | patched PART + patch proof |
| STEP 6 | QA PASS & six-line spec | SEO, thumbnail, export and final visual QA | 16:9 final JPG/PNG, metadata, archive record |

## Fixed length contract
Unicode NFC normalization; count only categories Letter (`L*`) and Number (`N*`), **not** whitespace or punctuation. UTF-8 decode is strict; malformed input fails instead of using replacement characters. Part A 13,334–16,000; B 13,334–17,000; C 13,334–17,000; total 40,001–50,000. Part-specific minima mean actual achievable total min is 40,002.

## Anti-duplication
STEP 2 uses an 8-field fingerprint: relation, setting, trigger, evidence, mechanism, reveal, payoff, consequence. RED: same mechanism+payoff, or extremely similar title. YELLOW: three or more matching fields or moderate title 3-gram similarity. Comparison to the 35 original titles only tests title surface similarity; this does NOT certify that the content of all 35 complete scripts differs. Offline project HISTORY_INDEX.json can store more meaningful fingerprint comparison.

## Story DNA selector
Choose `PRIMARY_STORY_DNA`, `SECONDARY_DNA` (1–2), `HOOK_DNA`, `EMOTIONAL_ARC`, `REVERSAL_MECHANISM`. Select based on evidence access, justified motivations and useful scenes, not random mixing. See STEP 2 `references/creative_dna_v4.md`. A single Narrative Spine and title promise must govern all PARTs.

## Step 3 blueprint gate
The CLI checks required structural fields, 20–24 scenes, part budgets, three reveals with at least two registered seed IDs, proof-source metadata, one title-promise-payoff mapping, entry/exit state in A/B/C. Humans/AI still must actually verify scene chronology, plausible access, legal/medical/ownership limits and whether reveal seeds precede the payoff. A JSON PASS is *not* a creative-logic certification.

## Writer continuity handoff
After every part store `script/{PART}_HANDOFF.json`: end date/time/location, person knowledge IDs, documents and access, seeds, unresolved loops, closed loops, next scene, SHA of that exact narration part. Before writing B or C, confirm incoming knowledge and loop resolution. Automated gate blocks unexplained disappearing facts/loops, but cannot prove event truthfulness.

## Step 5 two-pass QA
1. Pass I: causal necessity, timeline, character knowledge, proof chain, authority, title payoff and setup integrity. P0/P1/P2 root causes, not superficial prose polish.
2. Pass II: score 12 categories A–L /100 (original rubric), pacing, retention, emotion, Japanese naturalness, consequence. Preserve passed spans.

Thresholds: total 95; B logic 16/18, C continuity 8/10, D motivation 8/10, E setup/payoff 8/10, I realism 5/7; zero P0; A/B/C all PASS_LOCKED. Fatal score caps preserved. Reviewer must document coverage and source SHA, but coverage attestation is not proof that an AI genuinely read 100%. The validator only enforces declared source match and rubric arithmetic. Mechanical failures return `AUDIT_NOT_STARTED`; no compensation via high score.

## Patch protocol and conflicts
- STEP 5 generates `qa/audit.json` with tickets; never edits script.
- Ticket includes ID, part, P0/P1/P2, root cause, allowed one-based inclusive line range in *baseline* file, acceptance criteria and forbidden regions.
- STEP 4 uses `gate --target REPAIR --part X` to reserve a repair cycle, creates candidate without overwriting baseline, invokes `commit-patch --candidate ... --tickets ...`.
- The patch engine verifies baseline SHA and unchanged other-part hashes, checks modified lines against ticket scope, keeps within character limits, then commits. Re-run STEP 5 full A/B/C.
- `PASS_LOCKED` parts cannot be patched, even if tickets were hallucinated. If needed, `LOCK_OVERRIDE_REQUEST` asks user for explicit decision; do not silently treat a userless field as authorization.
- No more than 3 cycles for any part. If 2 consecutive cycles fail to improve, stop cosmetic edits; output root-cause request for replan of the failing part only. The controller doesn't auto-approve a replan that changes locked dependencies.
- If 3 cycles exhausted or blocked by locked seed, stop, with concrete reason and next permitted action.

## Thumbnail contract
Use `thumbnail_spec.json` L1–L5 and L6 split spans; exact six physical rows, L6 two differently colored phrases same baseline. Colors L1 yellow, L2 white, L3 magenta, L4 yellow, L5 cyan, L6 cyan+magenta. Final dimensions 1280×720 or 1920×1080 (16:9), right face ~35–40%, dark behind text, no legible prop text. A final image generated directly by AI can wrap even when the spec is correct: visual review required. Preferred approach is AI background **without text** and deterministic six-row typography overlay (supports local font path, none bundled). The renderer guarantees six overlay rows but does not verify background text or face fraction; attest these manually in `visual_qa`.

## Source provenance
The old source manifest is retained as provenance; hashes and sizes of the 35 `reference_corpus/ref_XX.txt` in the supplied ZIP differ. `packaged_corpus_manifest.json` is SHA256 of the **actual packaged bytes**. Do not represent it as hash verification of the originals shown by the historical manifest.

## QA notes
The test suite is synthetic and validates mechanics (state, SHA, UTF-8, count, patch, thumb output, malformed data), not creative quality. The user should pilot on a real Japanese script and manually review semantically important details.
