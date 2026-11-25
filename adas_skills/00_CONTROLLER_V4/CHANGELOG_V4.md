# ADAS V4.0.0 — Changelog

## Phạm vi
Nâng cấp `adas_skills.zip` (STEP 2/3/4/5/6) mà KHÔNG thêm STEP 1, STEP 7, Channel Audit, nghiên cứu thị trường hoặc vidIQ. Giữ tất cả file tham khảo (35 scripts) nguyên bytes.

## Sửa các xung đột P0
- Controller cũ nêu STEP 1 và 7 dù không có trong ZIP; bản V4 chỉ điều phối 5 skill.
- STEP 3/5 đề xuất replan nhưng Controller từng cấm quay STEP 3; quy tắc mới: chỉ đề xuất phạm vi part chưa khóa, không âm thầm đổi baseline hoặc sửa PASS_LOCKED. Nếu cần đổi seed đã khóa, yêu cầu người dùng quyết định.
- STEP 5 cũ vừa tuyên bố audit-only vừa ra lệnh xóa metadata; V4 không cho auditor chỉnh script. Writer-side exporter mới có `clean-script` và báo cáo để duyệt.
- STEP 6 từng cho thay title trong tình huống audit; V4 khóa title bất biến.
- Prompt tạo ảnh cũ dùng 1536×1024 (3:2) trong khi yêu cầu ảnh cuối 16:9; V4 dùng background không chữ và renderer 1280×720.

## Chức năng mới
1. Offline originality fingerprint 8 yếu tố + reference title index (35 nguồn tên) + local HISTORY_INDEX.
2. Creative DNA Selector mới, không phụ thuộc research web.
3. JSON Story Blueprint 20–24 scene, ngân sách A/B/C, các seed IDs và proof provenance.
4. Strict UTF-8 Unicode NFC L/N counters và metadata-leak detector; error JSON + exit code.
5. Continuity handoff JSON và kiểm soát knowledge/open-loop transitions A→B→C.
6. State machine và SHA256 khóa title/part/audit; two-pass audit trong STEP 5.
7. Scoped patch tickets, tối đa 3 repair cycles/part, audit freshness và rollback qua candidate file không ghi đè trước khi PASS.
8. Thumbnail 6-line spec, L6 two-colored same baseline, output 16:9, visual review gate.
9. Bộ SHA256 mới cho actual `reference_corpus/ref_XX.txt`; historical source manifest vẫn giữ riêng.
10. Template JSON, tài liệu gọi lệnh, unit/smoke tests và ZIP cài đặt riêng.

## Giữ nguyên
- ONE IDEA mặc định; `LOCKED_TITLE` STEP 2–6.
- 3 PART A/B/C; A 13,334–16,000; B/C 13,334–17,000; total 40,001–50,000 pure chars.
- Rubric 100, hard minimum 95, subsection gates B/C/D/E/I, zero P0, 3 part PASS_LOCKED.
- Thumbnail sáu dòng vật lý, L6 cyan+magenta cùng baseline.

## Giới hạn trung thực
- Người đánh giá vẫn phải đọc và kiểm chứng logic/nhân vật/pháp lý; score và coverage từ reviewer không phải chứng minh bằng mã.
- Originality bằng heuristic, không hiểu toàn bộ semantics nếu chỉ có tiêu đề của reference.
- Thumbnail visual QA do reviewer cung cấp; ảnh nền có chữ hoặc bố cục gương mặt vẫn cần kiểm tra bằng mắt.
- Kiểm thử synthetic ≠ chứng minh chất lượng kịch bản thật.
