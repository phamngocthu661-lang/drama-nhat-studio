## HARD OVERRIDE — SIX_LINES_ONLY (USER-LOCKED; highest precedence for thumbnail)
- Text rendered ON the thumbnail MUST be EXACTLY SIX visible physical text lines, not 7, 8, 9 or 10.
- Each of the six semantic beats occupies EXACTLY ONE line. No wrapping, duplicate captions, extra headline, microtext, numerical decoration, subtitles, watermarks or text in scene props that reads as an additional headline.
- LINE_BREAK_PLAN must specify exactly L1–L6, no separate seventh line. If a line is too long, SHORTEN its Japanese wording; NEVER split it into an additional line.
- L1 RELATIONSHIP, L2 SITUATION, L3 CONFLICT, L4 ESCALATION, L5 REVERSAL, L6 REACTION. Preserve story logic and avoid revealing the final truth.
- L6 is exactly ONE physical line, with TWO colored semantic SPANS within it: cyan/blue phrase + magenta phrase. Do not place the two colors on separate lines.
- Image-generation prompts must include the six exact Japanese line strings, their colors, and a prohibition on any other rendered textual overlays. Rendered images must be VISUALLY COUNTED: if not exactly six, REJECT/REGENERATE; do not label PASS.
- This rule overrides any historical reference suggesting 7–10 lines or permitting beat-to-line expansion, including older STEP 2/STEP 6 outputs.
- Output validation flag: SIX_LINES_ONLY: PASS only if visible count = 6; otherwise FAIL.
