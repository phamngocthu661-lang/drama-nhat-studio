---
name: adas-idea-title-packaging
description: "Generate, score and package original Japanese story premises, titles and 6-layer high-CTR thumbnail narratives before outlining."
---

# Idea, Title & 6-Layer Thumbnail Packaging Engine

Mục tiêu: biến research thành premise đủ mạnh để đáng viết 90–120 phút; chọn title **trước** khi viết script; đồng thời tạo cấu trúc thumbnail 6 tầng theo visual language của niche Japanese long-form family drama.

## Bắt buộc dùng reference corpus
Đọc `references/corpus_dna.md` và `references/hard_length_contract.md` trước khi thực hiện. Đọc thêm `references/thumbnail_dna_6_layer.md` khi tạo packaging. Các pattern chỉ dùng như benchmark cơ chế; không sao chép exact wording/composition của competitor.

## Input
- `MECHANISM_LIBRARY` + `30_RAW_PREMISES` từ skill 01, hoặc seed topic của người dùng.
- Audience/channel positioning.
- Nếu có ảnh competitor/reference trong Project, dùng chúng để hiểu visual language nhưng không copy nguyên thumbnail.


# HARD LONG-FORM CAPACITY GATE
Trước khi một idea được chọn làm winner, phải chứng minh premise có thể phát triển tự nhiên thành **40,001–50,000 ký tự thuần** theo `hard_length_contract.md`.

Bắt buộc xuất:
- `LONGFORM_CAPACITY: PASS / RISK / FAIL`
- ít nhất 8–12 meaningful turns/scenes có chức năng khác nhau
- ít nhất 3 reveal layers
- đủ consequence/relationship movement để kéo dài mà không lặp filler

Nếu `LONGFORM_CAPACITY != PASS`, idea không được handoff sang STEP 3 dù Idea Score/Title Score cao.

## 1. Tạo premise bằng ma trận
Kết hợp 4 chiều:
- RELATION: 母娘 / 父娘 / 夫婦 / 元夫婦 / 義母嫁 / 兄妹 / 姉妹 / 祖父母 / 婚約者 / 親子
- SETTING: 病院 / 銀行 / 同窓会 / 葬儀 / 結婚式 / 正月 / お盆 / 実家 / マンション / 学校 / 旅館
- PROOF OBJECT: 手紙 / 通帳 / 写真 / 鍵 / バッグ / 箱 / 領収書 / 指輪 / 古い携帯 / 病院書類
- EMOTION: 恩返し / 後悔 / 裏切り / 誤解 / 再会 / 嫉妬 / 犠牲 / 尊厳 / 許し

## 2. Idea Score — 100
- Curiosity gap 20
- Emotional stake 20
- Relatability of relationship 15
- Concrete evidence/object 10
- Reveal ladder potential 15
- Plausibility 10
- Thumbnail clarity 5
- Originality vs references 5

**Rule:** dưới 75 → không viết. 75–84 → cần sửa premise. 85+ → đủ vào vòng title.

## 3. Anti-copy gate
So với competitor/reference gần nhất. Idea mới phải đổi ít nhất 4/6 yếu tố:
1 relationship, 2 setting, 3 trigger, 4 hidden secret, 5 proof object, 6 final payoff.
Nếu chỉ đổi vật thể/địa điểm nhưng giữ cùng logic → FAIL.

## 4. Tạo 3 title/idea
- A = Mystery-led
- B = Emotion-led
- C = Conflict-led
Mỗi title nên là mini-trailer, thường 55–100 Japanese chars theo corpus; không ép nếu câu chuyện cần khác.

### Title construction
`ordinary relationship/situation → specific injustice or anomaly → concrete detail/quote → transition → withheld consequence`

Dùng số cụ thể khi nó làm câu chuyện đáng tin; không tăng tiền vô lý chỉ để sốc.

## 5. Title quality gate — 50
- hiểu premise trong 3 giây: 8
- có unanswered question rõ: 10
- có quan hệ người-với-người: 8
- có chi tiết/vật chứng cụ thể: 6
- không spoil đáp án cuối: 6
- believable specificity: 5
- khác title competitor: 4
- dễ dựng thumbnail: 3
Chỉ giữ title ≥42/50.

# 6. Thumbnail Narrative Architecture — BẮT BUỘC 6 TẦNG

Không dùng hệ 3 tầng cũ. Thumbnail phải được viết như một **mini screenplay 6 beat**.

### LAYER 1 — RELATIONSHIP ANCHOR
Trả lời: **Ai với ai?**
Ví dụ loại thông tin: 夫 / 妻 / 義母 / 娘 / 兄夫婦 / 元妻 / 婚約者.

### LAYER 2 — SITUATION / EVENT
Trả lời: **Ở đâu / khi nào / sự kiện gì?**
Ví dụ: 同窓会 / 長寿祝い / 新婚初夜 / 銀行 / 病院 / 実家 / 納骨堂.

### LAYER 3 — CONFLICT
Trả lời: **Ai tạo ra sự bất công / xúc phạm / bí mật?**
Ví dụ: 見下した / 離婚を切り出した / 平手打ちした / 嘲笑った.

### LAYER 4 — CONCRETE ESCALATION
Trả lời: **Họ đã làm gì cụ thể?**
Phải có hành động hoặc lời thoại có thể hình dung được. Không dùng xung đột chung chung.

### LAYER 5 — REVERSAL TRIGGER
Khoảnh khắc báo hiệu mọi thứ sắp đảo chiều.
Ưu tiên transition như: `だが / ところが / すると / 直後 / その瞬間 / 数日後`.

### LAYER 6 — REACTION CLIFFHANGER
Không nói đáp án cuối. Chỉ cho một phản ứng cực mạnh chứng minh bí mật/twist tồn tại.
Ví dụ loại phản ứng: `凍りついた / 泣き崩れた / 言葉を失った / 青ざめた / 深々と頭を下げた`.

**QUY TẮC CỨNG:** 6 semantic beats = ĐÚNG 6 dòng chữ hiển thị. Tuyệt đối không tách 1 beat thành hai dòng; rút ngắn nội dung nếu cần. Dòng 6 gồm hai cụm màu cyan và magenta TRÊN CÙNG MỘT DÒNG.

# 7. Visual DNA của thumbnail

### Default composition
- 16:9.
- Text chiếm khoảng 55–65% bên trái/trung tâm.
- Main protagonist chiếm khoảng 30–40% bên phải.
- 1–2 supporting characters ở hậu cảnh/giữa khung làm bằng chứng tình huống.
- 1 proof object khi hữu ích: 離婚届 / 手紙 / スマホ / 通帳 / 鍵 / 写真 / 修理パネル.

### Background treatment — BẮT BUỘC
- **Nửa bên trái phía sau text phải tối hơn một chút** so với bên phải.
- Dùng dark vignette/charcoal-black overlay vừa đủ để chữ nổi mạnh.
- Không làm mất hoàn toàn scene; vẫn nhìn được ngữ cảnh phía sau.
- Giữ protagonist bên phải sáng/ấm hơn để hút mắt.

### Character treatment
- Ưu tiên protagonist nữ Nhật 30–45 tuổi khi story phù hợp.
- Gương mặt lớn, cảm xúc rõ: shock / hurt / near tears / silent anger / stunned realization.
- Supporting characters phải phản ứng rõ, không đứng làm nền vô nghĩa.

# 8. Color Hierarchy — chuẩn mới

Không tô màu ngẫu nhiên. Dùng màu theo chức năng:
- **White:** narration/setup trung tính.
- **Yellow:** relationship, event, concrete key detail, money/time emphasis.
- **Pink/Magenta:** insult, quote, betrayal, abnormality, emotional collision.
- **Cyan/Blue:** impact/reversal/payoff emphasis.

### FINAL PAYOFF LINE — BẮT BUỘC TWO-TONE
Dòng cuối lớn nhất phải chia hai phần màu:
- khoảng nửa trái: **cyan/bright blue gradient**
- khoảng nửa phải: **vivid pink/magenta**
- cả hai có thick black outline + shadow.

Không cần chia đúng 50/50 theo ký tự; chia theo semantic phrase sao cho đẹp và dễ đọc.

Ví dụ pattern:
`顔面蒼白で` → cyan/blue
`凍りついた……` → pink/magenta

# 9. Text Styling
- Ultra-bold Japanese display text.
- Thick black outline.
- Strong drop shadow.
- High contrast.
- Dense but readable.
- Không dùng minimalist typography.
- Không để khoảng trống quá nhiều.
- Text phải đọc được trên mobile.

# 10. Thumbnail Quality Score — 100
- Immediate curiosity: 20
- Mobile readability: 15
- Emotional face strength: 15
- 6-layer story completeness: 15
- Story specificity: 10
- Reaction cliffhanger power: 10
- Supporting visual evidence: 5
- Visual hierarchy/color logic: 5
- Originality vs competitor: 5

**Gate:** dưới 80 → remake. 80–84 → usable but weak. 85+ → strong candidate. 90+ → preferred winner.

# 11. Output bắt buộc cho mỗi finalist
1. `THUMBNAIL_ANGLE`
2. `MAIN_PROTAGONIST` — age/gender/emotion/pose
3. `SUPPORTING_FIGURES`
4. `PROOF_OBJECT`
5. `LAYER_1_RELATIONSHIP`
6. `LAYER_2_SITUATION`
7. `LAYER_3_CONFLICT`
8. `LAYER_4_CONCRETE_ESCALATION`
9. `LAYER_5_REVERSAL_TRIGGER`
10. `LAYER_6_REACTION_CLIFFHANGER`
11. `LINE_BREAK_PLAN`
12. `COLOR_PLAN`
13. `LEFT_BACKGROUND_DARKENING: YES`
14. `BOTTOM_PAYOFF_TWO_TONE: CYAN + MAGENTA`
15. `THUMBNAIL_SCORE /100`

## Output tổng của skill
1. Top 5 premise + Idea Score
2. 3 titles cho mỗi top premise
3. Chọn 1 title winner + lý do
4. `TITLE_PROMISE`: chính xác người xem đang đòi câu trả lời gì
5. Full 6-layer thumbnail narrative architecture
6. `ORIGINALITY_DIFF`: 4/6 yếu tố đã đổi so với reference gần nhất
7. `LONGFORM_CAPACITY` + scene/reveal capacity note
8. Handoff cho skill 03


## HARD OVERRIDE — SIX_LINES_ONLY (USER-LOCKED; highest precedence for thumbnail)
- Text rendered ON the thumbnail MUST be EXACTLY SIX visible physical text lines, not 7, 8, 9 or 10.
- Each of the six semantic beats occupies EXACTLY ONE line. No wrapping, duplicate captions, extra headline, microtext, numerical decoration, subtitles, watermarks or text in scene props that reads as an additional headline.
- LINE_BREAK_PLAN must specify exactly L1–L6, no separate seventh line. If a line is too long, SHORTEN its Japanese wording; NEVER split it into an additional line.
- L1 RELATIONSHIP, L2 SITUATION, L3 CONFLICT, L4 ESCALATION, L5 REVERSAL, L6 REACTION. Preserve story logic and avoid revealing the final truth.
- L6 is exactly ONE physical line, with TWO colored semantic SPANS within it: cyan/blue phrase + magenta phrase. Do not place the two colors on separate lines.
- Image-generation prompts must include the six exact Japanese line strings, their colors, and a prohibition on any other rendered textual overlays. Rendered images must be VISUALLY COUNTED: if not exactly six, REJECT/REGENERATE; do not label PASS.
- This rule overrides any historical reference suggesting 7–10 lines or permitting beat-to-line expansion, including older STEP 2/STEP 6 outputs.
- Output validation flag: SIX_LINES_ONLY: PASS only if visible count = 6; otherwise FAIL.
