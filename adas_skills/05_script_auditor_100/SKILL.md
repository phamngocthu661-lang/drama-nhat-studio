---
name: adas-script-auditor-100
version: 4.0.0
description: "Audit-only 100-point QA for three-part Japanese scripts. Locks passed parts, issues repair tickets for failing parts, and verifies targeted patches without rewriting the script."
---

## V4.0 CROSS-SKILL CONTRACT — BẮT BUỘC (ưu tiên so với nội dung V3 cũ)
- Chạy trong phạm vi **STEP 2–STEP 6**. Không STEP 1/7, không Channel Audit, không nghiên cứu thị trường, không bắt buộc vidIQ.
- `references/ADAS_V4_WORKFLOW.md` là bản hợp đồng vận hành trong skill cài độc lập; `00_CONTROLLER_V4/PROJECT_WORKFLOW.md` là bản gốc của gói tổng. Dùng CLI `scripts/adas_v4.py` hoặc bản controller cùng phiên bản.
- `LOCKED_TITLE` bất biến từ STEP 2–6. Không thay bằng synonym hay đổi dấu; muốn thay phải tạo project/version mới có chấp thuận của user.
- Japanese narration luôn lưu `script/A.txt`, `script/B.txt`, `script/C.txt` độc lập, UTF-8 strict, metadata sidecar JSON.
- Cốt truyện theo **20–24 meaningful scenes**, A/B/C part budgets + tổng đúng Hard Contract; không thêm filler.
- STEP 5 tuyệt đối audit-only: chỉ phát ticket. STEP 4 mới sửa, và chỉ theo ticket/scope, có SHA baseline; một part PASS_LOCKED không tự động mở khóa.
- Mỗi Part tối đa 3 repair cycles; không lặp vô hạn. REPLAN ở STEP 3 chỉ được đề xuất và biên tập phần chưa khóa; mở vùng đã khóa cần user override rõ.
- Điểm số 100 do reviewer nhận định; công cụ cơ học **không** tự xác nhận logic, nguồn pháp lý, retentions hay cảm xúc đúng.


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

### CLEAN_TTS_SCRIPT_GATE — AUDIT ONLY
- STEP 5 chỉ phát hiện và lập ticket `METADATA_LEAK`, KHÔNG xóa hay chỉnh bất kỳ byte nào của kịch bản.
- STEP 4 Writer phải xuất narration sạch và có thể dùng `adas_v4.py clean-script` tạo bản mới + báo cáo các dòng bị loại, sau đó người biên tập duyệt phần bị loại; phải chạy lại length gate.
- Metadata dài nhiều dòng, đoạn có thể là lời kể thực sự, hoặc nghi vấn nhãn kỹ thuật phải được rà soát thủ công; không tự xóa theo suy đoán.

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
- `REPLAN_REQUIRED` — lỗi gốc tại architecture; xuất yêu cầu đề xuất `REPLAN_PART_X` cho part chưa khóa, không tự tác động dữ liệu hay đảo ngược state.

Một part `PASS_LOCKED` trở thành **immutable** cho các vòng sửa sau.

# 4. KEEP UNCHANGED = HARD LOCK
Phần đạt không chỉ “khuyên giữ”. Phải xuất `LOCK_MANIFEST`:
- part;
- scenes/spans locked;
- criteria đã đạt;
- reason to preserve.

STEP 4 PATCH MODE không được sửa locked part/spans.

Nếu fix P0 cần thay seed trong part locked: phát hành `LOCK_OVERRIDE_REQUEST: PART X / SCENE Y / EXACT PURPOSE` và **DỪNG CHỜ user phê duyệt**, không được tự mở vùng khóa.

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
- cùng ticket fail 2 lần liên tiếp → không tiếp tục wording patch; dừng và đề xuất STEP 3 `REPLAN_PART_X` có kiểm soát;
- score của part không tăng sau 2 cycles → yêu cầu quyết định root-cause `REPLAN_PART_X`;
- sau cycle 3 vẫn chưa đạt → STOP PATCH LOOP, nêu root-cause và đề xuất review STEP 3 nếu không đụng vùng đã khóa.

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


## V4 STEP 5 EXTENSION — TWO-PASS AUDIT INSIDE EXISTING STEP
- **Pass 1 / Logic & dependencies**: đọc A+B+C, causal chain, timeline, knowledge, proof/authority, motivation, seed/payoff. Tạo P0/P1 tickets trước khi đánh giá văn phong.
- **Pass 2 / Global holistic quality**: phân bổ điểm rubric 12 category, retention, emotion, spoken Japanese, originality, ending, regression. Giữ vùng đã PASS.
- Hai pass là công đoạn nội bộ STEP 5, KHÔNG thêm STEP mới, KHÔNG tự sửa script. Ghi `qa/audit.json` theo template và source_sha256 từng part; `coverage.reviewed_full=true` là reviewer ATTESTATION chứ không phải bằng chứng phần mềm đã đọc toàn bộ.
- `python scripts/adas_v4.py audit qa/audit.json --a script/A.txt --b script/B.txt --c script/C.txt --title ...` kiểm score/coverage/metadata/part hashes, trả PUBLISH gate. FAIL thì phát tickets kèm line scope, quay STEP 4.
- Không mở khóa part `PASS_LOCKED` nếu không có lệnh user; fatal issue, title promise sai, knowledge leap phải chặn ngay cả khi tổng >=95.
- Repair cycle per part <=3; 2 lần không tiến bộ thì dừng patch wording, chỉ đề xuất root-cause replan trong phạm vi chưa khóa; không lặp vô hạn.
