# Thumbnail DNA — 6-Layer Japanese Story Poster System

## Core objective
Thumbnail phải cho người xem cảm giác: **đã hiểu gần nửa câu chuyện nhưng vẫn thiếu đúng đáp án quan trọng nhất nên phải click**.

## Six semantic beats
1. Relationship anchor — Ai với ai?
2. Situation/event — Đang ở đâu/khi nào?
3. Conflict — Điều gì sai/bất công?
4. Concrete escalation — Chính xác họ đã nói/làm gì?
5. Reversal trigger — Khoảnh khắc mọi thứ sắp đổi chiều.
6. Reaction cliffhanger — Phản ứng cực mạnh nhưng giữ lại đáp án.

## Visual layout
- 16:9.
- 55–65% text ở trái/trung tâm.
- 30–40% main face ở phải.
- 1–2 secondary characters ở phía sau/giữa khung.
- Main protagonist sáng hơn; vùng trái sau chữ tối hơn nhẹ.

## Color logic
- White = narration.
- Yellow = key event/detail/relationship.
- Pink/magenta = insult/betrayal/quote/emotional abnormality.
- Cyan/blue = impact/reversal.

## Final line signature
Dòng cuối là text lớn nhất và **split two-tone**:
- left semantic half: cyan/blue
- right semantic half: vivid pink/magenta
- thick black outline + strong shadow.

## Background signature
Phía trái có dark vignette hoặc charcoal overlay nhẹ để text nổi bật; không biến background thành nền đen phẳng.

## What not to do
- Không tối giản 2–3 từ.
- Không chỉ 1 khuôn mặt + slogan chung chung.
- Không dùng background sáng rối phía sau text.
- Không dùng 6 màu ngẫu nhiên.
- Không reveal final truth.
- Không copy exact line breaks/phrasing/composition của competitor.


## HARD OVERRIDE — SIX_LINES_ONLY (USER-LOCKED; highest precedence for thumbnail)
- Text rendered ON the thumbnail MUST be EXACTLY SIX visible physical text lines, not 7, 8, 9 or 10.
- Each of the six semantic beats occupies EXACTLY ONE line. No wrapping, duplicate captions, extra headline, microtext, numerical decoration, subtitles, watermarks or text in scene props that reads as an additional headline.
- LINE_BREAK_PLAN must specify exactly L1–L6, no separate seventh line. If a line is too long, SHORTEN its Japanese wording; NEVER split it into an additional line.
- L1 RELATIONSHIP, L2 SITUATION, L3 CONFLICT, L4 ESCALATION, L5 REVERSAL, L6 REACTION. Preserve story logic and avoid revealing the final truth.
- L6 is exactly ONE physical line, with TWO colored semantic SPANS within it: cyan/blue phrase + magenta phrase. Do not place the two colors on separate lines.
- Image-generation prompts must include the six exact Japanese line strings, their colors, and a prohibition on any other rendered textual overlays. Rendered images must be VISUALLY COUNTED: if not exactly six, REJECT/REGENERATE; do not label PASS.
- This rule overrides any historical reference suggesting 7–10 lines or permitting beat-to-line expansion, including older STEP 2/STEP 6 outputs.
- Output validation flag: SIX_LINES_ONLY: PASS only if visible count = 6; otherwise FAIL.
