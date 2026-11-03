---
name: adas-seo-publish-pack
description: "Create Japanese YouTube SEO metadata and final 6-layer high-CTR thumbnail packaging after script quality approval."
---

# SEO, Metadata & Final Thumbnail Publish Pack

Mục tiêu: packaging SEO hỗ trợ Browse/Suggested mà không phá title CTR; đồng thời tạo final thumbnail đúng visual DNA đã khóa ở skill 02.

## Bắt buộc dùng reference
Đọc:
- `references/corpus_dna.md`
- `references/thumbnail_dna_6_layer.md`
- `references/hard_length_contract.md`

Không sao chép exact thumbnail competitor. Học cơ chế visual/narrative hierarchy.

## HARD Prerequisite
STEP 6 chỉ được chạy khi **đồng thời**:
- audit skill 05 ≥95
- zero P0
- `PURE_CHARACTER_COUNT` đã được deterministic-verified
- `40,001 <= PURE_CHARACTER_COUNT <= 50,000`
- `LENGTH_GATE = PASS`
- `PART_A_STATUS = PASS_LOCKED`
- `PART_B_STATUS = PASS_LOCKED`
- `PART_C_STATUS = PASS_LOCKED`
- STEP 5 final audit is VERIFY/PASS, not merely a baseline with open repair tickets

Nếu script <=40,000 hoặc >50,000 pure chars, hoặc còn bất kỳ part nào chưa `PASS_LOCKED`: **STOP** và quay đúng STEP 4 PATCH / STEP 5 VERIFY. Không tạo publish-ready pack. Với dự án này, length gate không được bypass bằng điểm cao.

## SEO principle
Title của niche này là mini-story; không nhét `[感動する話][朗読][スカッと]` nếu làm title yếu.
SEO đặt chủ yếu ở description, hashtags, playlist và channel semantic consistency.

## Metadata workflow
1. Giữ title winner; chỉ sửa nếu audit cho thấy title promise sai.
2. Description line 1 nói rõ format/topic tự nhiên.
3. 3 core hashtags tối đa ưu tiên: `#感動する話 #朗読 #スカッとする話`.
4. Thêm 2–3 topic hashtags phù hợp thật sự.
5. Không giả `#実話` nếu story là fiction/dramatized.
6. Playlist theo intent.
7. Nếu video dài, có thể dùng `聞き流し`, `作業用`, `長編朗読` khi đúng trải nghiệm.

# FINAL THUMBNAIL SYSTEM — BẮT BUỘC

## 1. Narrative structure
Thumbnail phải dùng đủ 6 semantic beats từ skill 02:
1. Relationship anchor
2. Situation/event
3. Conflict
4. Concrete escalation
5. Reversal trigger
6. Reaction cliffhanger

Không quay lại hệ 3 tầng.

## 2. Layout signature
- 16:9.
- Text nằm bên trái/trung tâm, có thể mở rộng chiều ngang (60–75% khung hình) và **ĐƯỢC PHÉP ĐÈ LÊN MỘT PHẦN ẢNH MẶT / VAI NHÂN VẬT** bên phải để mỗi hàng chữ nằm gọn trên 1 dòng ngang duy nhất, tuyệt đối không bị ép xuống dòng phụ.
- Main protagonist lớn bên phải, khoảng 30–40% khung.
- 1–2 supporting characters ở background/center-left hoặc center-right tùy scene.
- Proof object rõ nếu story có: document/letter/phone/photo/bankbook/repair object.

## 3. Left-side background treatment — LOCKED STYLE
- **Darken vùng nền bên trái phía sau chữ khoảng vừa phải**.
- Dùng vignette/charcoal-black transparent overlay, không phải nền đen phẳng.
- Mục tiêu: chữ bật lên, scene vẫn còn đọc được.
- Right-side protagonist giữ warm highlights/skin detail sáng hơn.

## 4. Text style
- Huge ultra-bold Japanese text.
- Thick black outline.
- Strong drop shadow.
- Tight leading nhưng không dính chữ.
- Text density cao theo niche, nhưng phải mobile-readable.
- Không minimalist.

## 5. Color hierarchy
- White: narration/setup.
- Yellow: key event, relationship, concrete number/detail.
- Pink/Magenta: insult, betrayal, quote, emotional abnormality.
- Cyan/Blue: impact/reversal emphasis.

## 6. Final payoff line — LOCKED TWO-TONE STYLE
Dòng cuối phải là line lớn nhất.
Chia thành hai semantic phrase:
- Phrase 1 → **cyan/bright blue gradient**
- Phrase 2 → **vivid pink/magenta**
- Thick black outline + shadow cho cả hai.

Không bắt buộc chính xác 50/50 theo ký tự; ưu tiên chia đẹp theo nghĩa.

## 7. Character expression
Main protagonist:
- face lớn, dễ đọc trên mobile;
- emotion mạnh nhưng realistic;
- teary/shocked/hurt/silent anger/stunned realization tùy story.

Supporting figures:
- phải có meaningful reaction: mock / gasp / bow / freeze / point / glare.
- không chỉ đứng cho đủ người.

## 8. Scene proof
Background phải chứng minh story setting:
- banquet/reunion
- family home
- hospital
- bank
- funeral/memorial
- wedding
- repair scene
- hotel/company event
Tùy title.

## 9. Generate 1 Final Master Thumbnail Concept
- Tập trung toàn lực tạo **1 mẫu Thumbnail Master duy nhất** mạnh nhất, kết hợp đồng thời:
  + Biểu cảm khuôn mặt đau đớn/bàng hoàng của nhân vật chính (Emotion-heavy)
  + Hành động/lời sỉ nhục từ phe phản diện (Conflict-heavy)
  + Vật chứng bước ngoặt + phản ứng đứng hình ở dòng 6 (Reversal cliffhanger)
- Giữ chuẩn dark-left + two-tone bottom payoff signature (Cyan + Magenta).

## 10. Thumbnail Quality Score — 100
- Immediate curiosity 20
- Mobile readability 15
- Emotional face strength 15
- Six-layer story completeness 15
- Story specificity 10
- Reaction cliffhanger power 10
- Visual evidence clarity 5
- Hierarchy/color logic 5
- Originality 5

**Publish gate:** ưu tiên candidate ≥90. Không publish candidate <85 nếu có thể remake.

# Image-generation prompt contract
Khi tạo prompt final (`<THUMBNAIL_PROMPT_1>`), phải mô tả rõ:
- Bắt đầu bằng lệnh tạo ảnh mới hoàn toàn từ văn bản (`Generate a brand-new image from scratch using text-to-image, horizontal landscape size 1536x1024, do NOT look for any reference image to edit`). TUYỆT ĐỐI KHÔNG ghi `3840x2160` hay `1536x864` (vì công cụ tạo ảnh chuẩn của OpenAI chỉ nhận kích thước ngang `1536x1024`).
- TUYỆT ĐỐI KHÔNG đưa các câu lệnh hậu kiểm như `reject and regenerate`, `check the rendered image`, `compare with previous image`, hay `modify/edit` vào bên trong nội dung `<THUMBNAIL_PROMPT_1>` để tránh làm công cụ tạo ảnh hiểu nhầm là chỉnh sửa ảnh có sẵn.
- Japanese high-CTR long-form story poster style
- dense multi-line text
- left background slightly darker behind text
- main protagonist right side
- secondary characters supporting story
- 6 semantic beats in text
- white/yellow/pink/cyan hierarchy
- final bottom line split cyan + magenta
- thick black outlines and shadows
- no watermark/logo

## Human check bắt buộc
Sau image generation:
- kiểm tra Japanese text chính xác;
- kiểm tra line break: TUYỆT ĐỐI ĐÚNG 6 DÒNG (L1 đến L6);
- phần chữ ĐƯỢC PHÉP đè lên một phần ảnh mặt/nhân vật để giữ đúng 6 dòng ngang không bị rớt dòng;
- kiểm tra mobile readability;
- kiểm tra proof object có đúng story;
- kiểm tra dòng cuối đúng split cyan/magenta;
- kiểm tra vùng trái đủ tối nhưng không mất scene.

## Output
- `PURE_CHARACTER_COUNT_VERIFIED`
- `LENGTH_GATE: PASS`
- Final title
- Description
- Hashtags
- Playlist assignment
- Thumbnail Master Concept (1 mẫu duy nhất)
- Exact 6-layer Japanese thumbnail text
- Line-break plan
- Color plan
- Final payoff split plan
- Single Image-generation prompt (`<THUMBNAIL_PROMPT_1>`)
- Thumbnail score /100
- Pinned-comment draft
- Upload checklist
- `MANUAL_PUBLISH_REQUIRED` nếu không có connector upload YouTube.


## HARD OVERRIDE — SIX_LINES_ONLY (USER-LOCKED; highest precedence for thumbnail)
- Text rendered ON the thumbnail MUST be EXACTLY SIX visible physical text lines, not 7, 8, 9 or 10.
- Each of the six semantic beats occupies EXACTLY ONE line. No wrapping, duplicate captions, extra headline, microtext, numerical decoration, subtitles, watermarks or text in scene props that reads as an additional headline.
- LINE_BREAK_PLAN must specify exactly L1–L6, no separate seventh line. If a line is too long, SHORTEN its Japanese wording; NEVER split it into an additional line.
- L1 RELATIONSHIP, L2 SITUATION, L3 CONFLICT, L4 ESCALATION, L5 REVERSAL, L6 REACTION. Preserve story logic and avoid revealing the final truth.
- L6 is exactly ONE physical line, with TWO colored semantic SPANS within it: cyan/blue phrase + magenta phrase. Do not place the two colors on separate lines.
- Image-generation prompts must include the six exact Japanese line strings, their colors, and a prohibition on any other rendered textual overlays. Always specify `size="1536x1024"` and phrase as a brand-new standalone text-to-image prompt.
- This rule overrides any historical reference suggesting 7–10 lines or permitting beat-to-line expansion, including older STEP 2/STEP 6 outputs.
- Output validation flag: SIX_LINES_ONLY: PASS only if visible count = 6; otherwise FAIL.
