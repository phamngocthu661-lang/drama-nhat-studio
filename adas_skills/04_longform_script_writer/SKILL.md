---
name: adas-longform-japanese-writer
version: 3.0-three-part-build-patch
description: "Write Japanese long-form scripts in three independent parts (A/B/C), each mechanically length-checked, then patch only the specific failing part without touching locked parts."
---

# STEP 4 — Japanese Long-form Script Writer — THREE-PART BUILD/PATCH SYSTEM

Mục tiêu: giảm áp lực output dài bằng cách **không bao giờ yêu cầu viết toàn bộ 40K–50K trong một lần**. Script được tạo thành 3 lần: PART A, PART B, PART C.

## Bắt buộc đọc
- `references/corpus_dna.md`
- `references/hard_length_contract.md`
- `references/three_part_contract.md`
- STEP 3 Story Bible + part scene plans + handoff specs

# 1. HARD LENGTH CONTRACT
Final total:
> **40,001–50,000 PURE_CHARACTER_COUNT**

Per-part gate:
- PART A: **13,334–16,000**
- PART B: **13,334–17,000**
- PART C: **13,334–17,000**

Không được bắt đầu part kế tiếp nếu part hiện tại chưa qua mechanical part gate.

# 2. MODE A — BUILD MODE

## BUILD PART A
Chỉ viết PART A từ scene plan A.
Không viết B/C trước.
Sau khi viết:
1. deterministic count;
2. nếu <13,334 → tiếp tục mở rộng A bằng causal material có chức năng;
3. nếu >16,000 → cắt redundancy;
4. cập nhật continuity + handoff;
5. chỉ khi `PART_A_LENGTH_GATE: PASS` mới cho phép PART B.

## BUILD PART B
Input bắt buộc:
- Story Bible;
- immutable PART A text hoặc handoff ledger;
- PART B scene plan.

Rules:
- bắt đầu đúng scene tiếp theo;
- không rewrite A;
- không recap A để lấy dung lượng;
- mọi new fact phải tương thích knowledge/evidence đã có.

Sau B: deterministic count, hard range 13,334–17,000.

## BUILD PART C
Input:
- Story Bible;
- A/B handoff ledgers;
- PART C scene plan.

Rules:
- không rewrite A/B;
- phải trả TITLE_PROMISE;
- đóng open loops;
- consequence + callback;
- không kéo epilogue vô chức năng.

Sau C: deterministic count, hard range 13,334–17,000.

# 3. ASSEMBLY RULE — CONCATENATE, KHÔNG REWRITE
Khi A/B/C đều pass:
- ghép `A + B + C` theo đúng thứ tự;
- chỉ được chuẩn hóa separator/heading nếu headings không phải narration;
- **không paraphrase để “mượt hơn” toàn bài**;
- deterministic count full script.

Nếu part gates đều pass nhưng total >50,000 do counting mismatch/extra headings, xử lý metadata/headings trước; không rewrite story tùy tiện.

# 4. PURE COUNT — PHẢI ĐẾM THẬT
Dùng:
`python scripts/count_pure_characters.py <part_or_full.txt>`

Hoặc:
`python scripts/count_three_parts.py part_a.txt part_b.txt part_c.txt`

Không được ước lượng bằng token, word count hoặc raw character count.

# 5. MODE B — PATCH MODE (SAU STEP 5)
STEP 4 **không tự quyết định sửa gì**. PATCH MODE chỉ chạy khi nhận `REPAIR_TICKETS` từ STEP 5.

Input bắt buộc:
- failing part text hiện tại;
- repair tickets của đúng part;
- `LOCKED_SECTIONS` trong part;
- handoff summary của các part khác;
- previous score ledger;
- current per-part + total pure counts.

## IMMUTABILITY RULE
- Part khác đã `PASS_LOCKED` → **không được output lại, không được sửa**.
- Trong failing part, section nào `LOCKED` → giữ nguyên byte-for-byte trừ khi có `LOCK_OVERRIDE` rõ ràng từ STEP 5.
- Không đổi tên, tuổi, amount, relationship, payoff, twist ngoài ticket.

## PATCH SCOPE
Chỉ sửa đoạn liên quan ticket. Mỗi ticket phải có acceptance criteria.
Không “rewrite bản tốt hơn”.
Không tự thêm twist mới.

## Sau patch
Bắt buộc xuất `PATCH_CHANGELOG`:
- ticket ID;
- scene/paragraph changed;
- before problem;
- exact repair intent;
- pure char delta;
- locked regions touched: NONE / explicit override.

Chỉ xuất **PART đã sửa**, không xuất lại A/B/C đầy đủ.

# 6. LENGTH SAFETY DURING PATCH
Sau patch phải kiểm lại:
- failing part vẫn nằm trong hard range;
- total vẫn 40,001–50,000.

Nếu sửa làm part quá ngắn/dài, điều chỉnh **trong cùng repair scope hoặc neighboring unlocked scene**, không đụng locked parts khác.

# 7. EXPANSION HIERARCHY — KHI PART THIẾU LENGTH
1. causal bridge;
2. new clue/evidence;
3. decision + cost;
4. antagonist pressure/motive;
5. relationship shift with consequence;
6. payoff setup;
7. realistic aftermath;
8. earned callback.

CẤM:
- repeated moral;
- repeated emotion wording;
- recap;
- useless flashback;
- circular dialogue;
- adjective padding;
- overlong ending.

# 8. PART HANDOFF LEDGER
Sau mỗi part:
- location/time;
- character states;
- knowledge by character;
- assets/documents;
- planted seeds;
- unresolved loops;
- forbidden contradictions;
- exact next scene.

# 9. OUTPUT CONTRACT — BUILD MODE
Mỗi lần chỉ output **một part**:
- Japanese narration thuần túy cho part đó (**TUYỆT ĐỐI KHÔNG in dòng `LOCKED_TITLE: ...`, `SELECTED_TITLE: ...`, `PART A — 日本語脚本`, `Pxxx — STEP 4 · BUILD PART A · 日本語脚本`, `<CodeBlock>`, `<WritingBlock>`, `CONTINUITY:`, `ENDING:` vào đầu hay giữa văn bản truyện để tránh rò rỉ vào giọng đọc TTS và phụ đề Video!**)
- Ở cuối cùng (sau khi kết thúc hoàn toàn văn bản truyện tiếng Nhật) mới ghi:
- `PART_PURE_CHARACTER_COUNT`
- `PART_LENGTH_GATE: PASS/FAIL`
- Continuity ledger
- Handoff ledger
- `NEXT_ACTION`

Sau C và assembly:
- `PART_A_COUNT`
- `PART_B_COUNT`
- `PART_C_COUNT`
- `TOTAL_PURE_CHARACTER_COUNT`
- `TOTAL_LENGTH_GATE`
- `READY_FOR_AUDIT: YES` chỉ khi A/B/C + total đều PASS.

# 10. OUTPUT CONTRACT — PATCH MODE
- `PATCHED_PART: X`
- repaired part only
- `PATCH_CHANGELOG`
- `PART_PURE_CHARACTER_COUNT_BEFORE/AFTER`
- `TOTAL_PURE_CHARACTER_COUNT_AFTER`
- `LOCKED_OTHER_PARTS_TOUCHED: NO`
- `READY_FOR_VERIFY_AUDIT: YES/NO`
