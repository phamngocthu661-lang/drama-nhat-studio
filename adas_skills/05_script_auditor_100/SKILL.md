---
name: adas-script-auditor-100
version: 3.0-audit-only-part-lock
description: "Audit-only 100-point QA for three-part Japanese scripts. Locks passed parts, issues repair tickets for failing parts, and verifies targeted patches without rewriting the script."
---

# STEP 5 — Script Auditor — AUDIT ONLY / PART LOCK / REPAIR TICKETS

Mục tiêu: **đánh giá, khóa phần đã tốt, chỉ định chính xác phần cần sửa**. STEP 5 **KHÔNG ĐƯỢC viết lại kịch bản**.

## Bắt buộc đọc
- `references/corpus_dna.md`
- `references/logic_failure_catalog.md`
- `references/scoring_rubric.md`
- `references/hard_length_contract.md`
- `references/three_part_contract.md`

# 1. INPUT GATE — KHÔNG NHẬN DRAFT THIẾU LENGTH & KIỂM TRA VỆ SINH KỊCH BẢN (ZERO METADATA LEAK)
Baseline audit chỉ chạy khi STEP 4 đã cung cấp:
- PART A count PASS;
- PART B count PASS;
- PART C count PASS;
- TOTAL 40,001–50,000;
- `READY_FOR_AUDIT: YES`.

### ⚠️ QUY TẮC BẮT BUỘC VỀ VỆ SINH VĂN BẢN KỊCH BẢN (CLEAN_TTS_SCRIPT_GATE — CHỐNG RÒ RỈ `[LOCKED_TITLE]` & METADATA):
- Khi kiểm tra PART A, PART B, PART C và bản ghép `script_clean.txt` / `{ID}_KICH_BAN.txt`, Agent Kiểm Tra Kịch Bản **BẮT BUỘC quét, ghi chú (note lại) và XÓA BỎ NGAY LẬP TỨC** mọi dòng tiêu đề khóa hoặc nhãn kỹ thuật bị rò rỉ vào văn bản truyện để tránh tuyệt đối tình trạng tạo Voice (TTS) và Render Video đọc/hiển thị nhầm các dòng này:
  1. Mọi dòng bắt đầu bằng hoặc chứa `LOCKED_TITLE:`, `SELECTED_TITLE:`, `WINNING_TITLE:`, `FINAL_TITLE:`, `DRAFT_TITLE:` (bao gồm cả trường hợp câu tiêu đề dài bị tách thành 2–4 dòng kế tiếp kết thúc bằng `…` hoặc `…」`).
  2. Mọi dòng tiêu đề bước/phần như `Pxxx — STEP 4 · BUILD PART A · 日本語脚本`, `PART A — 日本語脚本`, `PART A — 日本語ナレーション本文`, `STEP 4`, `BUILD PART A/B/C`.
  3. Mọi thẻ bọc UI/Code như `<CodeBlock...>`, `</CodeBlock>`, `<WritingBlock...>`, `</WritingBlock>` và các dòng ghi chú kỹ thuật `CONTINUITY: ...`, `ENDING: ...`, `HANDOFF_LEDGER`, `PURE_CHARACTER_COUNT`.
- Văn bản kịch bản bàn giao sang tạo Voice & Render Video phải là **100% văn bản tự sự và lời thoại tiếng Nhật thuần túy**.

Nếu một part fail mechanical length:
> `AUDIT_NOT_STARTED — RETURN_TO_STEP_4_BUILD_PART_X`

Không chấm 100 điểm một bản 19K/20K rồi tạo vòng lặp vô nghĩa.

# 2. BASELINE AUDIT MODE
Đọc 100% A+B+C, lập:
- event causal chain;
- timeline;
- character knowledge matrix;
- money/assets/documents/authority ledger;
- setup/payoff map;
- open loops;
- retention map.

Sau đó chấm rubric 100 điểm như cũ.

# 3. PART STATUS — BẮT BUỘC
Ngoài score toàn bài, gán mỗi part một trạng thái:

- `PASS_LOCKED` — part đạt chức năng, không cần sửa.
- `PATCH_REQUIRED` — architecture cơ bản đúng, chỉ cần sửa targeted scenes/spans.
- `REPLAN_REQUIRED` — lỗi gốc nằm ở architecture của part; quay STEP 3 `REPLAN_PART_X`.

Một part `PASS_LOCKED` trở thành **immutable** cho các vòng sửa sau.

# 4. KEEP UNCHANGED = HARD LOCK
Phần đạt không chỉ “khuyên giữ”. Phải xuất `LOCK_MANIFEST`:
- part;
- scenes/spans locked;
- criteria đã đạt;
- reason to preserve.

STEP 4 PATCH MODE không được sửa locked part/spans.

Nếu fix một P0 thực sự cần thay seed trong part locked, auditor phải phát hành:
`LOCK_OVERRIDE: PART X / SCENE Y / EXACT PURPOSE`
Chỉ đoạn đó được reopen.

# 5. REPAIR TICKETS — KHÔNG TỰ SỬA
Mỗi issue phải thành ticket có ID:
- `TICKET_ID`
- `PART`
- `PRIORITY: P0/P1/P2`
- `LOCATION`
- `ROOT_CAUSE`
- `WHY_IT_HURTS_LOGIC/RETENTION`
- `ALLOWED_EDIT_SCOPE`
- `DO_NOT_TOUCH`
- `ACCEPTANCE_CRITERIA`
- `EXPECTED_SCORE_DELTA`

Auditor **không viết replacement prose** trừ khi user chỉ hỏi ví dụ ngắn; không tự rewrite script.

# 6. 100-POINT RUBRIC
### A. Title promise & premise integrity — 8
### B. Causal logic & plot necessity — 18
### C. Timeline, geography & continuity — 10
### D. Character motivation & behavioral consistency — 10
### E. Setup → payoff fairness — 10
### F. Information control & three-layer reveal — 8
### G. Retention architecture & pacing — 10
### H. Emotional architecture & moral reversal — 8
### I. Plausibility / domain realism — 7
### J. Japanese spoken naturalness — 5
### K. Originality & trope fatigue control — 3
### L. Ending, consequence & callback — 3
TOTAL 100.

Publish-ready requires:
- all part length gates PASS;
- total length gate PASS;
- total ≥95;
- Logic ≥16/18;
- Continuity ≥8/10;
- Motivation ≥8/10;
- Setup/payoff ≥8/10;
- Realism ≥5/7;
- zero P0;
- **PART A/B/C = PASS_LOCKED**.

# 7. SCORE LEDGER — CHỐNG RUBRIC DRIFT
Baseline audit tạo `MASTER_SCORE_LEDGER`:
- score từng category;
- evidence;
- locked/open status;
- version number.

Ở vòng verify:
- score/category của phần không bị patch **được bảo lưu**;
- không tự nhiên hạ điểm một phần không đổi vì “cảm giác lần chấm khác”.
- chỉ reopen category nếu patch ảnh hưởng dependency; phải ghi `REOPEN_REASON`.

# 8. VERIFY / DELTA AUDIT MODE
Sau STEP 4 PATCH, STEP 5 đọc:
- patched part;
- full-script handoff/locked part context;
- previous score ledger;
- repair tickets;
- patch changelog.

Bắt buộc:
1. check từng ticket PASS/FAIL;
2. regression check toàn story;
3. xác nhận locked parts không đổi;
4. re-count patched part + total;
5. tính `SCORE_DELTA`.

Output kiểu:
- Previous 88
- Current 94
- T01 +3 PASS
- T02 +2 PASS
- Regression -0

Nếu patch làm hỏng phần locked hoặc tổng score giảm do sửa ngoài scope:
> `PATCH_REJECTED — RESTORE_PREVIOUS_VERSION`

Không tiếp tục vá trên một version tệ hơn.

# 9. ANTI-INFINITE-LOOP RULE
Tối đa **3 repair cycles cho mỗi part**.

Escalation:
- cùng ticket fail 2 lần liên tiếp → không tiếp tục wording patch; chuyển STEP 3 `REPLAN_PART_X`;
- score của part không tăng sau 2 cycles → `REPLAN_PART_X`;
- sau cycle 3 vẫn chưa đạt → STOP PATCH LOOP, root-cause review ở STEP 3.

Không bao giờ “sửa mãi đến 100” bằng rewrite ngẫu nhiên.

# 10. ROOT-CAUSE RULE
Ticket phải sửa nguyên nhân, không sửa triệu chứng.
Ví dụ “emotion yếu” không được mặc định thêm 800 chars khóc; phải xác định relationship setup, sacrifice, cost, reveal timing hay consequence đang thiếu.

# 11. HARD SCORE CAPS
Giữ các cap logic:
- fatal causal contradiction: max 69;
- character knows critical info without path: max 69;
- title promise not paid: max 74;
- plot-feasibility timeline contradiction: max 79;
- sole unseeded deus ex machina: max 79;
- impossible essential legal/medical/ownership action: max 74;
- final reveal contradicts narrator objective fact: max 69.

Length fail không đi vào baseline scoring; trả thẳng STEP 4.

# 12. OUTPUT — BASELINE AUDIT
1. `AUDIT_VERSION`
2. length compliance A/B/C/total
3. final score /100
4. score table
5. `PART_STATUS_TABLE`
6. P0/P1/P2
7. causal chain audit
8. timeline/continuity audit
9. character knowledge audit
10. setup/payoff/open loops
11. retention map
12. **LOCK_MANIFEST / KEEP UNCHANGED**
13. **REPAIR_TICKETS grouped by PART**
14. projected score after tickets
15. `NEXT_ACTION` = STEP 4 PATCH PART X hoặc STEP 3 REPLAN PART X hoặc STEP 6.

# 13. OUTPUT — VERIFY AUDIT
1. previous/current version
2. ticket verification
3. part lock integrity
4. regression check
5. previous score → current score
6. category deltas
7. remaining tickets only
8. updated part status
9. updated lock manifest
10. cycle count by part
11. next action.
