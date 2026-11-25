# TEST REPORT — ADAS V4.0.0

Test command: `python -m unittest discover -s 00_CONTROLLER_V4/tests -v`

## Automated tests
9 tests PASS (2026-11-10):
- UTF-8 strict error + Unicode NFC letter/number counting.
- A/B/C hard bounds, metadata leakage gate.
- Story Blueprint 21 scenes and seeded reveals / rejection of malformed reveal.
- Offline originality RED when same mechanism/payoff despite changed title/relation.
- Scoped patch accepted; unauthorized line rejected; 4th cycle rejected.
- Fatal score cap & P0 block, stale audit sources blocked.
- Six-row deterministic typography renderer 1280×720; visual check remains required.
- End-to-end state machine CREATED→EXPORTED, title alteration blocked.
- Two actual C-part repair commits with A/B SHA preserved, stale QA blocked between repairs, final QA reopened and passed.

## Reference corpus integrity
- `verify-corpus`: 35/35 actual packaged `ref_XX.txt` hashes PASS.
- Original historical filename/hash manifest is not asserted to match these differently represented files.

## Not tested / manual verification required
- An actual 40–50k Japanese story for coherent causality, natural TTS or real authority rules.
- Visual face position, cropped scene truthfulness, true six visible rows on arbitrary AI background.
- Model's ability to spot all narrative defects.
- Performance inside a specific user's ChatGPT skill runtime or publishing app.

**Result:** mechanical gates have PASS coverage from synthetic tests; recommend one complete real script pilot before considering production stable.
