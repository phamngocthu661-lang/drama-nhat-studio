# ADAS V4 — Cài đặt và gọi lệnh

## Cài 5 skill riêng
1. Giải nén `ADAS_5_SKILLS_V4_0_UPGRADED.zip`.
2. Trong `01_INSTALL_5_SKILLS/`, cài lần lượt 5 ZIP `02` tới `06` vào hệ thống skill đang sử dụng.
3. Sao chép nội dung `instructions.txt` hoặc `00_CONTROLLER_V4/PROJECT_WORKFLOW.md` vào phần Project Instructions nếu sản xuất toàn bộ trong cùng một dự án ChatGPT.
4. Chỉ cần dùng `scripts/adas_v4.py` trong từng skill để kiểm cơ học cục bộ. Dùng `00_CONTROLLER_V4/scripts/adas_v4.py` khi chạy controller xuyên STEP. Python 3.10+; Pillow cho thumbnail render/check.
5. Không yêu cầu STEP 1, STEP 7, dữ liệu kênh hay nghiên cứu thị trường.

## Lệnh chạy chuẩn
Giả sử lệnh chạy từ thư mục giải nén (thay `P401` và đường dẫn cho dự án của bạn):

```bash
PY=python
V4=adas_skills/00_CONTROLLER_V4/scripts/adas_v4.py
$PY "$V4" init --dir ./P401 --id P401 --seed 'ý tưởng chính'
$PY "$V4" originality ./P401/plans/idea.json --history adas_skills/02_idea_title_packaging/references/reference_title_history.json ./HISTORY_INDEX.json
$PY "$V4" gate --dir ./P401 --target TITLE_LOCKED --title 'TIÊU ĐỀ NHẬT ĐÃ CHỐT'
$PY "$V4" blueprint ./P401/plans/blueprint.json
$PY "$V4" gate --dir ./P401 --target OUTLINE_APPROVED --blueprint ./P401/plans/blueprint.json
# Sau khi viết A + A_HANDOFF.json
$PY "$V4" gate --dir ./P401 --target A_READY
# Sau khi viết B + B_HANDOFF.json
$PY "$V4" gate --dir ./P401 --target B_READY
# Sau khi viết C + C_HANDOFF.json
$PY "$V4" gate --dir ./P401 --target C_READY
$PY "$V4" parts ./P401/script/A.txt ./P401/script/B.txt ./P401/script/C.txt
$PY "$V4" gate --dir ./P401 --target AUDIT_IN_PROGRESS
$PY "$V4" audit ./P401/qa/audit.json --a ./P401/script/A.txt --b ./P401/script/B.txt --c ./P401/script/C.txt --title 'TIÊU ĐỀ NHẬT ĐÃ CHỐT'
$PY "$V4" gate --dir ./P401 --target PUBLISH_READY --audit ./P401/qa/audit.json
$PY "$V4" render-thumbnail ./P401/publish/thumbnail_spec.json --background ./P401/publish/background.png --out ./P401/publish/final.jpg --font /path/to/your/installed/JapaneseBoldFont.ttc
# Sau khi nhìn ảnh và ghi visual_qa vào thumbnail_spec.json:
$PY "$V4" thumbnail ./P401/publish/thumbnail_spec.json --image ./P401/publish/final.jpg
$PY "$V4" gate --dir ./P401 --target EXPORTED --spec ./P401/publish/thumbnail_spec.json --image ./P401/publish/final.jpg
$PY "$V4" archive --dir ./P401 --history ./HISTORY_INDEX.json
```

Lệnh `originality` có thể báo YELLOW nếu dữ liệu cục bộ gần giống; đó là cờ cần người dùng đánh giá, không phải chứng nhận máy tự hiểu nội dung. Nếu file HISTORY_INDEX.json chưa tồn tại, bỏ đường dẫn này và chỉ dùng reference hoặc tạo file mẫu trước.

## Nếu QA chưa PASS
```bash
python "$V4" gate --dir ./P401 --target REPAIR --part B
# STEP 4 tạo ./P401/patch_candidate_B.txt, không sửa baseline trực tiếp.
python "$V4" patch --before ./P401/script/B.txt --after ./P401/patch_candidate_B.txt --tickets ./P401/qa/audit.json --part B --cycle 1
python "$V4" commit-patch --dir ./P401 --part B --candidate ./P401/patch_candidate_B.txt --tickets ./P401/qa/audit.json
# STEP 5 bắt buộc audit lại A/B/C, tạo audit.json mới.
```

**STOP** khi sửa dòng ngoài ticket, khác SHA, đổi title, hết 3 cycles/part, thiếu scope, hoặc cần sửa vùng PASS_LOCKED chưa được người dùng cho phép. Không dùng `gate OUTLINE_APPROVED` để lách trạng thái.

## Ba lệnh kiểm nhanh
```bash
python "$V4" count ./P401/script/A.txt --part A
python "$V4" verify-state --dir ./P401
python "$V4" verify-corpus adas_skills/05_script_auditor_100/reference_corpus adas_skills/05_script_auditor_100/references/packaged_corpus_manifest.json
```

## Định nghĩa lỗi kiểm thử
- `status=PASS`, exit code 0: cơ học đạt.
- `status=FAIL`, exit code 2: phải sửa/duyệt trước khi tiếp tục.
- Semantic quality (lỗi logic, drama, luật Nhật, timing reveal), cảm xúc và ảnh thumbnail thực tế vẫn cần kiểm định AI/human độc lập; đừng coi PASS cơ học là publish-ready nếu chưa đạt QA.
