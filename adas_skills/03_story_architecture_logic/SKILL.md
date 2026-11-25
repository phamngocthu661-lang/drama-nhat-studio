---
name: adas-story-architecture-logic
version: 4.0.0
description: "Build a causal 3-part story architecture for a 40,001–50,000-pure-character Japanese long-form script, with independent Part A/B/C capacity and repair-safe boundaries."
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


# STEP 3 — Story Architecture & Logic Preflight — THREE-PART CONTRACT

Mục tiêu: thiết kế **đủ chất liệu thật** để STEP 4 có thể viết kịch bản thành **3 lần độc lập: PART A → PART B → PART C**, tổng cuối luôn trên 40,000 ký tự thuần và không quá 50,000.

## Bắt buộc đọc
- `references/corpus_dna.md`
- `references/logic_failure_catalog.md`
- `references/hard_length_contract.md`
- `references/three_part_contract.md`

# 1. HARD FINAL LENGTH CONTRACT
Final script chỉ hợp lệ khi:

> **40,001 ≤ TOTAL_PURE_CHARACTER_COUNT ≤ 50,000**

`PURE_CHARACTER_COUNT` = Unicode Letters + Numbers sau NFC normalization; loại punctuation, symbols, whitespace, tab, line break.

## 3-part hard ranges
Mỗi part phải tự đạt mechanical gate trước khi part kế tiếp được viết:
- **PART A:** 13,334–16,000 pure chars
- **PART B:** 13,334–17,000 pure chars
- **PART C:** 13,334–17,000 pure chars

Tổng minimum theo contract này = **40,002**, nên không thể vô tình rơi về 40,000.
Tổng maximum = **50,000**.

### Target an toàn
- PART A: 14,000–15,000
- PART B: 14,500–15,500
- PART C: 15,000–16,000
- Total target: khoảng **44,000–46,500** pure chars

# 2. PART FUNCTIONS — KHÔNG CHIA CƠ HỌC 1/3

## PART A — FOUNDATION / HOOK / FIRST PURSUIT
Chức năng:
- cold open;
- normal world;
- relationship/wound;
- inciting trigger;
- first clue / first pursuit;
- kết ở một open loop đủ mạnh để kéo sang B.

PART A phải thiết lập các seed quan trọng cho climax. Không được để C tự sinh proof mới không có nguồn.

## PART B — INVESTIGATION / CONTRADICTION / MIDPOINT / ESCALATION
Chức năng:
- pursuit;
- wrong interpretation + cost;
- clue 2 / contradiction;
- midpoint reveal;
- relationship/motivation shift;
- escalation toward final truth;
- kết ở pre-climax hoặc Reveal 2, chưa trả hết TITLE_PROMISE.

## PART C — FINAL ESCALATION / REVEAL / PAYOFF / CONSEQUENCE
Chức năng:
- final evidence chain;
- pre-climax choice + cost;
- Reveal 3 / moral reinterpretation;
- trả TITLE_PROMISE;
- realistic consequence;
- relationship/state change;
- callback ending.

# 3. SCENE CAPACITY PLAN
Không chỉ viết 12 beat chung chung. Phải chia **20–24 meaningful scenes**, thường:
- PART A: 6–8 scenes
- PART B: 7–8 scenes
- PART C: 6–8 scenes

Mỗi scene phải có:
- `SCENE_PURPOSE`
- `NEW_INFORMATION`
- `ACTION`
- `CONFLICT_OR_PRESSURE`
- `STATE_CHANGE`
- `SETUP_OR_PAYOFF`
- `TARGET_PURE_CHARS`

Scene không có state change → không được dùng để đạt length.

# 4. STORY BIBLE & LOGIC LEDGER
Bắt buộc có:
- protagonist: tuổi, nghề, tài chính, tính cách, weakness;
- WANT / WOUND / FALSE BELIEF;
- key relationships/history;
- antagonist motive + incentive + fear + leverage;
- SECRET + PROOF;
- Reveal 1 / Reveal 2 / Reveal 3;
- callback object;
- ending state change.

Logic ledger:
`EVENT → CAUSE → WHO KNOWS → HOW THEY KNOW → EVIDENCE → EFFECT → LATER PAYOFF`

Event quyết định climax mà thiếu một ô → FAIL.

# 5. PART BOUNDARY / HANDOFF CONTRACT
Mỗi part phải kết thúc bằng `PART_HANDOFF_LEDGER` gồm:
- current date/time/location;
- current character states;
- what each character knows;
- money/assets/documents currently in play;
- seeds already planted;
- open loops;
- forbidden contradictions;
- exact next scene start.

PART B không được recap A để lấy dung lượng. PART C không được recap A+B để lấy dung lượng.

# 6. LOGIC PREFLIGHT
Trước approve phải kiểm tra:
- character knowledge leaks;
- impossible timeline/travel/age;
- pregnancy/child age;
- ownership/bank/legal/medical/corporate authority;
- evidence provenance;
- antagonist motive;
- no deus ex machina;
- ≥2 seed cho final reveal;
- narrator không nói sai objective fact;
- TITLE_PROMISE có payoff cụ thể ở C.

# 7. LENGTH FEASIBILITY GATE
Không được approve bằng cách “gán số” cho scene rỗng.
Mỗi scene phải có material có chức năng.

Bắt buộc xuất:
- `PART_A_PLANNED_PURE_CHARS`
- `PART_B_PLANNED_PURE_CHARS`
- `PART_C_PLANNED_PURE_CHARS`
- `TOTAL_PLANNED_PURE_CHARS`

Chỉ `APPROVED_FOR_DRAFTING: YES` nếu cả 3 part nằm trong hard range và total ≤50,000.

# 8. REPLAN MODE — CHỈ REPLAN PART BỊ LỖI
Sau STEP 5, nếu một part bị `REPLAN_REQUIRED`, STEP 3 chỉ **đề xuất** `REPLAN_PART_X` trên part chưa khóa; không tự quay STEP 3/sửa phần đã PASS_LOCKED. Nếu chạm dependency đã khóa → `DEPENDENCY_BLOCKED` và xin quyết định của người dùng.

Rules:
- các part `PASS_LOCKED` là immutable;
- chỉ đọc summary/handoff của locked parts để bảo toàn continuity;
- chỉ thay architecture của part fail;
- nếu sửa part fail thực sự cần thay seed ở part locked, phải tạo `LOCK_OVERRIDE_REQUEST` chỉ rõ scene/câu cần reopen và lý do;
- không được mở toàn part locked chỉ vì tiện.

# 9. OUTPUT CONTRACT
- Story Bible
- Character knowledge matrix
- Timeline
- Logic ledger
- Setup/payoff table
- 20–24 scene plan
- `PART_A_SCENE_PLAN`
- `PART_B_SCENE_PLAN`
- `PART_C_SCENE_PLAN`
- 3 part budgets
- 3 handoff specs
- P0/P1/P2 risk list
- `APPROVED_FOR_DRAFTING: YES/NO`

Nếu NO, nói rõ **part nào thiếu capacity hoặc logic gì**, không được đẩy lỗi xuống STEP 4.


## V4 STEP 3 EXTENSION — EXECUTABLE BLUEPRINT
- Tạo `plans/blueprint.json` theo JSON template, **20–24 scene**; mỗi scene phải có `id`, `part`, `purpose`, `new_info`, `action`, `conflict`, `state_change`, `evidence`, `knowledge_transfer`, `target_chars`.
- Lập `PROOF_CHAIN` xác định người tạo, địa điểm lưu, người xem, đường được quyền truy cập, scene xuất hiện; cấm dữ liệu có được bằng truy cập bất hợp pháp/phi thực tế.
- Xác định Character Knowledge, Timeline, Motivation, Setup→Payoff, Reveal Map và Seed IDs đủ hai lần gieo hợp lý cho mỗi reveal.
- `TITLE_PROMISE` và `PAYOFF_ID` kết nối bất biến; PART A→B→C có `entry_state`, `exit_state`, `open_loops`, `next_scene`.
- Chạy `python scripts/adas_v4.py blueprint plans/blueprint.json`; only JSON-structure PASS plus semantic logic preflight PASS mới chuyển STEP 4.
- `REPLAN_PART_X`: chỉ phần FAIL, chỉ trước khi khóa; sau khi có `PASS_LOCKED`, nếu cần sửa seed trong part locked → `DEPENDENCY_BLOCKED + LOCK_OVERRIDE_REQUEST`, không tự chỉnh STEP 3/4.
