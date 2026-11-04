import os
import re
import sys
import json
import time
import shutil
import threading
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Tuple

from .chatgpt_web_client import ChatGPTWebSession
from .gemini_web_client import GeminiWebSession, check_all_gemini_accounts_status
from .voice_service import split_japanese_script, strip_leaked_titles_and_metadata
from .logger_service import log_info, log_warn, log_error

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ==============================================================================
# 1. BỘ ĐẾM KÝ TỰ THUẦN CHUẨN ADAS (40.001 - 50.000 PURE CHARACTERS)
# ==============================================================================
def pure_char_count(text: str) -> int:
    """
    Chuẩn hóa Unicode NFC, chỉ tính ký tự thuộc nhóm Unicode L (chữ) và N (số),
    bỏ ký hiệu, khoảng trắng, emoji, dấu câu và xuống dòng.
    """
    norm = unicodedata.normalize("NFC", text or "")
    return sum(1 for ch in norm if unicodedata.category(ch)[0] in {"L", "N"})


# ==============================================================================
# 2. MẪU PROMPT STEP 2 GỐC CỦA NGƯỜI DÙNG (GIỮ NGUYÊN 100%)
# ==============================================================================
DEFAULT_STEP2_PROMPT_TEMPLATE = """CHẠY NGAY STEP 2 — IDEA / TITLE / THUMBNAIL — MÃ {{MÃ_ID}}

MỤC TIÊU: Từ đúng MỘT ý tưởng nghiên cứu dưới đây, xây concept Japanese long-form family drama, đánh giá khả năng viết thành kịch bản dài, tạo 3 tiêu đề Nhật, chọn 1 tiêu đề tốt nhất, và thiết kế thumbnail 6 tầng. Đây là yêu cầu hoàn chỉnh: toàn bộ dữ liệu cần thiết đã được dán trong lệnh. KHÔNG hỏi xin hoặc yêu cầu đọc bảng Excel, CSV, ZIP, hay cuộc hội thoại STEP 1; không xử lý các mã khác. KHÔNG tự ý tạo nhiều kịch bản, và KHÔNG viết script ở STEP 2.

ĐỊNH VỊ: {{ĐỊNH_VỊ_BATCH}}

========== ĐẦU VÀO DUY NHẤT: {{MÃ_ID}} ==========
01. Mức ưu tiên do STEP 1 đề xuất: {{ƯU_TIÊN}}
02. Trạng thái quản lý hiện tại: CHƯA_CHẠY_STEP2
03. Đánh giá năng lực viết dài sơ bộ (không thay kiểm tra STEP 2): {{LONGFORM_CAPACITY_STEP1}}
04. Tiêu đề Nhật NHÁP để tham khảo, TUYỆT ĐỐI chưa khóa: {{TIÊU_ĐỀ_NHẬT_NHÁP_CHƯA_KHÓA}}
05. Dịch ý tiếng Việt của bản nháp: {{DỊCH_Ý_TIÊU_ĐỀ_VI}}
06. Quan hệ nhân vật: {{QUAN_HỆ_NHÂN_VẬT}}
07. Trụ cột cảm xúc/chủ đề: {{NHÓM_CHỦ_ĐỀ}}
08. Không gian và sự kiện mở: {{BỐI_CẢNH_SỰ_KIỆN}}
09. Xung đột trọng tâm: {{XUNG_ĐỘT_MỞ_ĐẦU}}
10. PREMISE GỐC từ nghiên cứu (giữ đủ thông tin): {{PREMISE_GỐC_STEP1}}
11. Câu hỏi khán giả cần đáp án: {{CÂU_HỎI_CẦN_TRẢ_LỜI}}
12. Bằng chứng/vật chứng bắt buộc cân nhắc gieo và thu hồi: {{VẬT_CHỨNG_GIEO_TRƯỚC}}
13. Lớp tiết lộ thứ nhất, gợi ý chưa phải fact: {{REVEAL_LỚP_MỘT_ĐỀ_XUẤT}}
14. Lớp tiết lộ thứ hai, gợi ý chưa phải fact: {{REVEAL_LỚP_HAI_ĐỀ_XUẤT}}
15. Lớp tiết lộ thứ ba, gợi ý chưa phải fact: {{REVEAL_LỚP_BA_ĐỀ_XUẤT}}
16. Hệ quả/phần thưởng cảm xúc, gợi ý: {{PAYOFF_CẢM_XÚC_DỰ_KIẾN}}
17. Mã cơ chế nghiên cứu để lưu dấu (không cần mở file giải thích): {{CƠ_CHẾ_STORY_STEP1}}
18. Từ khóa Nhật GỢI Ý, CHƯA đo volume: {{TỪ_KHÓA_NHẬT_GỢI_Ý_CHƯA_XÁC_MINH_VOLUME}}
19. Căn cứ khả năng triển khai dài/rủi ro: {{LÝ_DO_CÓ_THỂ_VIẾT_DÀI_HOẶC_RỦI_RO}}
20. Lưu ý tính khả tín, luật, y tế, tài chính: {{LƯU_Ý_LOGIC_PHÁP_LÝ_Y_TẾ}}
21. Quy tắc kiểm soát sao chép đã có từ STEP 1: Must change at least 4/6 vs nearest reference before selection
22. Gợi ý góc thumbnail ban đầu (không phải bản duyệt): {{GÓC_THUMBNAIL_ĐỀ_XUẤT}}
23. Nguồn gốc ý tưởng để truy vết, đã mô tả tại đây và KHÔNG cần mở file: {{RESEARCH_SOURCE}}

QUY ƯỚC ĐẦU VÀO: Tất cả dòng ghi NHÁP / GỢI Ý / ĐỀ XUẤT là hướng nghiên cứu, có thể cải tiến trong STEP 2; không tự nhận là sự thật đã kiểm chứng. Tiêu đề Nhật nháp KHÔNG phải LOCKED_TITLE. Nếu premise có chỗ mâu thuẫn, phải chỉ ra và sửa nguyên nhân trước khi duyệt. Các từ khóa trên chưa có search volume/competition/VPH đã xác minh, tuyệt đối không bịa số liệu.

========== THAM CHIẾU CHỐNG TRÙNG (ĐÃ NHÚNG, KHÔNG CẦN FILE) ==========
CÁC MÔ-TÍP THAM CHIẾU NỘI BỘ (chỉ để nhận diện điểm trùng, không được sao chép nguyên cốt truyện):
{{THAM_CHIẾU_MOTIF_BATCH}}
Chọn mô-típ gần nhất, đối chiếu 6 yếu tố: quan hệ, bối cảnh, tác nhân khởi phát, bí mật, vật chứng và kết quả. Phải có ít nhất 4/6 yếu tố khác biệt CÓ Ý NGHĨA; không được tính thay tên hay thay vật dụng đơn thuần. Nếu thiếu dữ liệu để xác nhận sự khác biệt so với đối thủ thật, ghi rõ đây là đối sánh mô-típ tham chiếu, không khẳng định đã kiểm chứng thị trường.

========== QUY TRÌNH BẮT BUỘC CỦA STEP 2 ==========

A. CHẤM VÀ CẢI TIẾN IDEA (tối đa 100 điểm)
- Curiosity gap /20; Emotional stakes /20; Độ gần gũi quan hệ /15; Vật chứng cụ thể /10; Khả năng 3 lớp reveal /15; Tính khả tín /10; Độ rõ cho thumbnail /5; Tính nguyên gốc /5.
- Dưới 75: loại/chỉnh sửa mạnh, không duyệt. Từ 75–84: sửa premise rồi chấm lại. Từ 85: đủ chuẩn vào vòng title NẾU còn vượt các hard gate khác.
- Nêu rõ điểm thành phần, tổng, điểm yếu, phiên bản PREMISE_FINAL và CONFLICT_FINAL sau sửa (nếu sửa). Chỉ giữ những chi tiết có chuỗi nguyên nhân-hệ quả.

B. HARD LONGFORM CAPACITY GATE, không được bỏ qua
- Kịch bản mục tiêu về sau: 40.001–50.000 PURE_CHARACTER_COUNT tiếng Nhật; đích an toàn 44.000–47.000. Đây KHÔNG phải độ dài tiêu đề hay đầu ra của STEP 2.
- Cách đếm sau này: chuẩn hóa Unicode NFC, chỉ tính ký tự thuộc nhóm Unicode L (chữ) và N (số), bỏ ký hiệu, khoảng trắng, emoji, dấu câu và xuống dòng. 40.000 là FAIL.
- Trình bày ít nhất 8–12 diễn biến/cảnh mang CHỨC NĂNG KHÁC NHAU (manh mối, quyết định, hậu quả, dịch chuyển quan hệ...), và 3 lớp tiết lộ: sự kiện -> sự thật sâu hơn -> ý nghĩa đảo ngược. Nêu logic nhân-quả và hậu quả theo thời gian; không dùng filler, hồi tưởng lặp hoặc nhân vật cứu nguy tiện lợi.
- Xuất `LONGFORM_CAPACITY: PASS / RISK / FAIL` kèm lý do. Trạng thái STEP 1 chỉ là đánh giá sơ bộ, KHÔNG tự động được PASS ở bước này. Nếu RISK/FAIL phải nâng cấp premise, tự kiểm lại; vẫn chưa PASS thì dừng, không khóa title, không bàn giao STEP 3.

C. ORIGINALITY GATE
- Chọn reference-mô-típ nội bộ gần nhất ở trên, so sánh 6 mục: RELATIONSHIP, SETTING, TRIGGER, HIDDEN_SECRET, PROOF_OBJECT, FINAL_PAYOFF. Xuất `ORIGINALITY_DIFF` nêu cụ thể từng mục khác/giống và số khác biệt >=4/6. Chỉ thay vật/địa điểm mà giữ nguyên logic tính là KHÔNG khác biệt thật. Không sao chép nguyên văn tiêu đề hoặc thumbnail.
- Nếu không thể kiểm tra đối thủ thực, ghi rõ giới hạn nguồn; KHÔNG giả vờ đã kiểm chứng competitor.

D. TITLE MATRIX — VIẾT HOÀN TOÀN BẰNG TIẾNG NHẬT
- Tạo chính xác 3 ứng viên cho đúng mã {{MÃ_ID}}: A = Mystery-led, B = Emotion-led, C = Conflict-led. Mỗi tiêu đề là mini-trailer: quan hệ/bối cảnh bình thường -> bất công hoặc dị thường -> một chi tiết hoặc trích dẫn -> chuyển hướng -> hậu quả chưa hé lộ.
- Ưu tiên 55–100 ký tự Nhật theo corpus khi phù hợp; không ép số. Tránh spoil, số tiền phóng đại, tuyên bố không có căn cứ, bí mật phi lý và câu dụ nhấp gây hiểu lầm.
- Chấm từng tiêu đề /50: hiểu ngay /8, câu hỏi chưa trả lời /10, quan hệ /8, chi tiết cụ thể /6, không spoil /6, đáng tin /5, khác tiêu đề tham chiếu /4, dựng thumbnail /3. Chỉ chọn title >=42/50, đồng thời Idea PASS + Longform PASS + Originality PASS.
- Xuất tiêu đề Nhật đủ nguyên văn, bản dịch tiếng Việt, lý do thắng, `LOCKED_TITLE_PROMISE` (câu hỏi đã hứa với người xem), `TITLE_FACTS` (các fact bắt buộc có để giữ lời hứa, phân biệt với điều chưa chốt).

E. THUMBNAIL MINI SCREENPLAY — SIX_LINES_ONLY: CHÍNH XÁC 6 DÒNG HIỂN THỊ
- Trình bày đúng 6 semantic beats, tương ứng CHÍNH XÁC 6 dòng chữ Nhật nhìn thấy; không xuống hàng một beat thành hai dòng: `LAYER_1_RELATIONSHIP` (ai với ai); `LAYER_2_SITUATION` (địa điểm/sự kiện); `LAYER_3_CONFLICT` (bất công); `LAYER_4_CONCRETE_ESCALATION` (hành động hoặc câu nói); `LAYER_5_REVERSAL_TRIGGER` (だが / ところが / その瞬間...); `LAYER_6_REACTION_CLIFFHANGER` (phản ứng mạnh nhưng KHÔNG lộ chân tướng).
- Xuất `THUMBNAIL_ANGLE`, `MAIN_PROTAGONIST` (giới/tuổi/cảm xúc/tư thế phù hợp), `SUPPORTING_FIGURES`, `PROOF_OBJECT`, `LINE_BREAK_PLAN` (CHÍNH XÁC 6 DÒNG L1–L6, một semantic beat trên một dòng, tuyệt đối không dòng thứ bảy), `COLOR_PLAN`. Tả kỹ cảnh/ánh sáng/gương mặt/đồ vật để có thể dựng hình; không tự tạo hình nếu chưa được yêu cầu.
- Layout 16:9; chữ nằm bên trái/giữa (có thể mở rộng chiều ngang 60–75% khung hình và PHẦN CHỮ CÓ THỂ ĐÈ LÊN MỘT PHẦN ẢNH MẶT / VAI NHÂN VẬT bên phải cũng được để mỗi dòng chữ có đủ chỗ nằm ngang, tuyệt đối không bị ép rớt dòng), gương mặt chính 30–40% bên phải, 1–2 nhân vật phụ hợp ngữ cảnh. Bên trái sau chữ tối hơn nhẹ bằng vignette; bên phải mặt sáng/ấm hơn. Dùng display type Nhật ultra-bold, viền đen dày, bóng mạnh, dễ đọc trên điện thoại.
- White = kể bối cảnh; Yellow = quan hệ/sự kiện/chi tiết; Pink/Magenta = xung đột/câu nói; Cyan/Blue = chuyển hướng. DÒNG 6 (duy nhất) BẮT BUỘC chứa hai cụm CYAN/BLUE + MAGENTA nằm TRÊN CÙNG MỘT HÀNG, viền đen dày; phần magenta là reaction cliffhanger, không spoil. Không tạo dòng riêng cho mỗi màu.
- Chấm THUMBNAIL /100: tò mò ngay /20, đọc mobile /15, biểu cảm gương mặt /15, đủ 6 tầng /15, cụ thể theo câu chuyện /10, reaction cliffhanger /10, vật chứng/nhân vật phụ /5, phân cấp hình-chữ-màu /5, khác biệt /5. Dưới 80: làm lại; 80–84: dùng được nhưng yếu; 85+: mạnh; 90+: ưu tiên.

THUMBNAIL HARD LOCK (ưu tiên cao hơn mọi ví dụ):
- L1 RELATIONSHIP; L2 SITUATION; L3 CONFLICT; L4 CONCRETE_ESCALATION; L5 REVERSAL_TRIGGER; L6 REACTION_CLIFFHANGER.
- Chỉ 6 hàng chữ độc lập có thể nhìn thấy trong thumbnail. Không title nhỏ, badge chữ, phụ đề, hàng chữ nằm trong đạo cụ hoặc logo có chữ biến thành dòng phụ.
- Phần chữ ĐƯỢC PHÉP đè lên ảnh mặt nhân vật nếu cần độ rộng ngang, nhưng TUYỆT ĐỐI BẮT BUỘC PHẢI ĐÚNG 6 DÒNG (L1–L6); chữ Nhật phải rút ngắn nếu dài, tuyệt đối không chia một hàng thành hai. Dòng 6 có hai cụm CYAN + MAGENTA trên đúng một hàng.
- A/B/C, LINE_BREAK_PLAN, prompt hình và ảnh xuất đều chịu hard lock này. Nếu ảnh được tạo, bắt buộc kiểm tra bằng mắt 6 hàng; khác 6 => THUMBNAIL_LINE_GATE: FAIL và phải sửa/tạo lại. Trong STEP 2 chỉ xuất prompt/hướng dẫn, không tự tạo ảnh nếu chưa được yêu cầu.

F. ĐẦU RA BẮT BUỘC, PHẢI ĐÚNG THỨ TỰ
1) `ID: {{MÃ_ID}}` + `COMPLETED_STEP: STEP 2` + `RESULT` + `STATUS: PASS / NEEDS REVISION` + `NEXT_STEP`.
2) Premise chỉnh sửa cuối + Idea Score 8 tiêu chí /100.
3) Longform Capacity + 8–12 turns theo thứ tự nhân quả + 3 reveal layers; điểm rủi ro đặc thù câu chuyện.
4) Bảng Originality Diff 6 yếu tố vs mô-típ gần nhất.
5) Title A/B/C tiếng Nhật và bản dịch Việt, điểm thành phần /50 cho từng title, WINNER.
6) Full thumbnail đúng 6 dòng vật lý L1–L6 bằng tiếng Nhật + hình ảnh/chữ/dòng/màu + Thumbnail Score /100 + SIX_LINES_ONLY: PASS/FAIL.
7) Chỉ khi mọi hard gate PASS: xuất chính xác `LOCKED_TITLE`, `LOCKED_TITLE_PROMISE`, `TITLE_FACTS`, `TITLE_LOCKED: YES`. Từ thời điểm này title là bất biến đến STEP 6. Nếu một hard gate chưa PASS thì xuất `TITLE_LOCKED: NO`, giải thích phần phải sửa, TUYỆT ĐỐI không giả khóa.
8) `STEP3_HANDOFF`: bản tóm tắt tự đủ thông tin gồm nhân vật, xung đột, vật chứng, twist, fact/commitment khóa, rủi ro và command cụ thể "Chạy STEP 3 cho mã {{MÃ_ID}} theo toàn bộ dữ liệu handoff vừa xuất, giữ nguyên LOCKED_TITLE". Không viết STEP 3/4 trong lần chạy này.

BẮT ĐẦU THỰC HIỆN STEP 2 CHO DUY NHẤT MÃ {{MÃ_ID}} NGAY BÂY GIỜ; toàn bộ thông tin của ý tưởng này nằm trong chính tin nhắn. Không yêu cầu đọc hoặc gửi bất kỳ file dữ liệu nghiên cứu nào."""

DEFAULT_MOTIF_REFERENCES = (
    "- Ref #31: Vợ từ vùng núi về thăm nhà lần đầu sau 18 năm kết hôn, chồng lén đưa 28 vạn yên, khi mở hành lý mang về thì sững sờ.\n"
    "- Ref #28: Mẹ kế âm thầm nuôi con riêng thành giáo sư đại học, khi rút 2000 vạn yên mua nhà báo hiếu thì nhân viên ngân hàng tiết lộ sự thật.\n"
    "- Ref #15: Mẹ đơn thân nuôi con gái thành công tố viên, bị gia đình thông gia sỉ nhục trong buổi ra mắt cho đến khi nhân vật bước vào mở cửa.\n"
    "- Ref #30: Ly hôn 12 năm gặp lại em vợ nhặt vỏ lon, đưa 6 vạn yên, 3 ngày sau nhận bức thư tiết lộ lý do ly hôn năm xưa."
)

DEFAULT_BATCH_POSITIONING = (
    "Kênh YouTube Japanese Long-form Family Drama (90–120 phút, 40.001–50.000 ký tự thuần). "
    "Khán giả mục tiêu: Người Nhật trưởng thành/cao tuổi yêu thích câu chuyện gia đình sâu sắc, "
    "hiếu thảo, hy sinh thầm lặng, hiểu lầm được hóa giải bằng bằng chứng thực tế và nhân quả đời thường đáng tin."
)


# ==============================================================================
# 3. TRÌNH PHÂN TÍCH ĐẦU VÀO THÔNG MINH (HỖ TRỢ BỘ CỐ ĐỊNH P01..P30, DÁN ĐƠN & SLL)
# ==============================================================================
# Nhận diện dòng mở đầu của bộ tiêu đề cố định:
# VD: "P01 — 義母の介護を10年続けた..." hoặc "P20 - 定年退職の日..." hoặc "ID05: ..."
FIXED_PACK_HEADER_RE = re.compile(
    r"^(?:(?:#|\*|\-|\•)\s*)?(?P<code_id>(?:P|ID|IDEA_?|M|T)\s*\d{1,4})\s*(?:[—–\-:：\.]+|\s+)\s*(?P<ja_title>.*[\u3040-\u30ff\u4e00-\u9faf].*)$",
    re.IGNORECASE,
)

# Nhận diện dòng tiêu đề đánh số thứ tự (không phải dòng thuộc tính 01..23 của Step 2)
NUMBERED_JA_TITLE_RE = re.compile(
    r"^(?:(?:#|\*|\-|\•)\s*)?(?P<num>\d{1,3})[\.\)\-—–]\s*(?P<ja_title>.*[\u3040-\u30ff\u4e00-\u9faf].*)$"
)

# Nhận diện các dòng thuộc tính (TUYỆT ĐỐI KHÔNG BAO GIỜ TÁCH THÀNH TIÊU ĐỀ MỚI dù có chữ Nhật)
FIELD_LINE_PREFIX_RE = re.compile(
    r"^(?:(?:\d{1,2}[\.\)\-:]|\-|•|\*)\s*)?"
    r"(?:vi|vn|dịch\s*ý(?:\s*tiếng\s*việt)?|tóm\s*tắt|premise(?:\s*gốc)?|nội\s*dung"
    r"|keyword|keywords|từ\s*khóa(?:\s*nhật)?"
    r"|evidence|proof(?:\s*object)?|vật\s*chứng|bằng\s*chứng"
    r"|reveal|reveals|ba\s*lớp\s*tiết\s*lộ|3\s*lớp\s*tiết\s*lộ|lớp\s*tiết\s*lộ(?:\s*thứ\s*(?:nhất|hai|ba))?|tiết\s*lộ"
    r"|capacity|longform(?:_capacity(?:_step1)?|\s*step\s*1)?|đánh\s*giá\s*năng\s*lực\s*viết\s*dài"
    r"|quan\s*hệ(?:\s*nhân\s*vật)?|nhân\s*vật|relation|relationship"
    r"|trụ\s*cột(?:\s*cảm\s*xúc)?|nhóm\s*chủ\s*đề|chủ\s*đề|pillar"
    r"|không\s*gian(?:\s*và\s*sự\s*kiện\s*mở)?|bối\s*cảnh|setting"
    r"|xung\s*đột(?:\s*trọng\s*tâm|\s*mở\s*đầu)?|conflict"
    r"|câu\s*hỏi(?:\s*khán\s*giả\s*cần\s*đáp\s*án|\s*cần\s*trả\s*lời)?"
    r"|payoff|hệ\s*quả"
    r"|mức\s*ưu\s*tiên|ưu\s*tiên|priority"
    r"|trạng\s*thái(?:\s*quản\s*lý)?|status"
    r"|mã\s*cơ\s*chế|cơ\s*chế|mechanism"
    r"|căn\s*cứ(?:\s*khả\s*năng)?|lưu\s*ý(?:\s*tính\s*khả\s*tín)?|quy\s*tắc(?:\s*kiểm\s*soát)?"
    r"|góc\s*thumbnail|nguồn\s*gốc(?:\s*ý\s*tưởng)?|research_source)\s*[:：]",
    re.IGNORECASE,
)

TITLE_LABEL_START_RE = re.compile(
    r"^(?:(?:\d+[\.\)\-:]|\-|•|\*|#+\s*)\s*)?(?:tiêu\s*đề\s*nhật\s*nháp|tiêu\s*đề\s*nháp|tiêu\s*đề\s*nhật|04\.\s*tiêu\s*đề|title)\s*[:：]",
    re.IGNORECASE,
)

ID_LABEL_START_RE = re.compile(
    r"^(?:(?:\d+[\.\)\-:]|\-|•|\*|#+\s*)\s*)?(?:chạy\s*ngay\s*step\s*2.*mã|đầu\s*vào\s*duy\s*nhất\s*[:：]|mã(?:\s*id)?\s*[:：]|id\s*[:：]|ý\s*tưởng\s*[:：]|idea\s*[:：])",
    re.IGNORECASE,
)


def _is_new_idea_block_header(ln: str) -> bool:
    """Kiểm tra xem dòng `ln` có phải là dòng mở đầu của một bộ tiêu đề mới (VD: 'P01 — ...') hay không."""
    s = (ln or "").strip()
    if not s:
        return False
    # Nếu là dòng thuộc tính (VI:, Keyword:, Evidence:, Reveal:, Capacity:...) thì TUYỆT ĐỐI KHÔNG phải header
    if FIELD_LINE_PREFIX_RE.match(s):
        return False
    if FIXED_PACK_HEADER_RE.match(s):
        return True
    if TITLE_LABEL_START_RE.match(s) or ID_LABEL_START_RE.match(s):
        return True
    m_num = NUMBERED_JA_TITLE_RE.match(s)
    if m_num:
        return True
    return False


def split_raw_text_into_idea_blocks(raw_text: str) -> List[str]:
    """
    Tự động nhận diện và tách văn bản khi người dùng dán 1 hoặc NHIỀU (SLL) bộ tiêu đề cùng lúc:
    - Định dạng 1 (Bộ tiêu đề cố định chuẩn):
        P01 — 義母の介護を10年続けた私に...
        VI: Chăm mẹ chồng 10 năm...
        Keyword: 義母, 介護...
        Evidence: 介護日誌 / nhật ký chăm sóc
        Reveal: Lời hứa không phải để thừa kế...
        Capacity: PASS
      (Giữ nguyên cả 6 dòng trong đúng 1 bộ P01; tuyệt đối không tách nhầm dòng Keyword/Evidence có chữ Nhật thành tiêu đề mới!)
    - Định dạng 2: Các khối có nhãn 'Tiêu đề Nhật nháp:', 'Tóm tắt:'...
    - Định dạng 3: Danh sách các câu tiêu đề tiếng Nhật thuần (chỉ khi không có bất kỳ dòng thuộc tính VI:/Keyword:/Evidence:/Tóm tắt: nào).
    """
    text = (raw_text or "").strip()
    if not text:
        return []

    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not raw_lines:
        return []

    has_any_field_lines = any(bool(FIELD_LINE_PREFIX_RE.match(ln)) for ln in raw_lines)
    has_any_pack_headers = any(_is_new_idea_block_header(ln) for ln in raw_lines)

    # TRƯỜNG HỢP A: Chỉ dán danh sách các câu tiêu đề tiếng Nhật thuần (không có dòng VI:/Keyword:/Evidence:/Tóm tắt:)
    if not has_any_field_lines and not has_any_pack_headers:
        ja_blocks: List[str] = []
        for ln in raw_lines:
            if re.match(r"^[-=*#]{3,}$", ln):
                continue
            cleaned = re.sub(r"^(?:\d+[\.\)\-:]|\-|•|\*)\s*", "", ln).strip()
            if cleaned and re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", cleaned):
                ja_blocks.append(cleaned)
        if ja_blocks:
            return ja_blocks
        return [text]

    # TRƯỜNG HỢP B: Dán 1 hoặc nhiều bộ tiêu đề có cấu trúc (P01..P20 hoặc khối Tiêu đề Nhật nháp / Tóm tắt)
    blocks: List[List[str]] = []
    current_block: List[str] = []
    current_has_header_or_content = False
    sep_re = re.compile(r"^[-=*]{3,}$")

    for ln in raw_lines:
        if sep_re.match(ln):
            if current_block:
                blocks.append(current_block)
                current_block = []
                current_has_header_or_content = False
            continue

        # Kiểm tra xem có phải dòng mở đầu của bộ mới (P01 — ..., P02 — ..., Tiêu đề Nhật nháp:, ID:...)
        is_fixed_header = bool(FIXED_PACK_HEADER_RE.match(ln) or NUMBERED_JA_TITLE_RE.match(ln)) and not bool(FIELD_LINE_PREFIX_RE.match(ln))
        is_title_label = bool(TITLE_LABEL_START_RE.match(ln))
        is_id_label = bool(ID_LABEL_START_RE.match(ln))

        if (is_fixed_header or is_id_label) and current_has_header_or_content:
            blocks.append(current_block)
            current_block = [ln]
            current_has_header_or_content = True
            continue

        if is_title_label and current_has_header_or_content:
            # Nếu khối hiện tại đã có tiêu đề hoặc trường nội dung thì ngắt sang khối mới
            already_has_title = any(
                bool(TITLE_LABEL_START_RE.match(x) or FIXED_PACK_HEADER_RE.match(x))
                for x in current_block
            )
            if already_has_title:
                blocks.append(current_block)
                current_block = [ln]
                current_has_header_or_content = True
                continue

        current_block.append(ln)
        if is_fixed_header or is_title_label or bool(FIELD_LINE_PREFIX_RE.match(ln)):
            current_has_header_or_content = True

    if current_block:
        blocks.append(current_block)

    result_blocks = ["\n".join(b).strip() for b in blocks if b]
    return result_blocks if result_blocks else [text]


def _infer_relationship_from_text(vi_text: str, keyword_text: str, ja_title: str) -> str:
    """Tự động nhận diện mối quan hệ nhân vật chính xác từ VI / Keyword / Tiêu đề Nhật."""
    combined = f"{vi_text} {keyword_text} {ja_title}"
    mapping = [
        (("義母", "嫁姑", "mẹ chồng", "nàng dâu", "con dâu"), "Mẹ chồng – Con dâu – Chồng (Gia đình nhà chồng)"),
        (("継父", "継母", "再婚", "cha dượng", "mẹ kế", "tái hôn"), "Gia đình tái hôn (Cha dượng / Mẹ kế và con riêng)"),
        (("義姉", "義妹", "義兄", "chị chồng", "em chồng", "anh chồng"), "Góa phụ / Nàng dâu và họ hàng nhà chồng (Chị/em chồng)"),
        (("義父", "bố chồng", "cha chồng"), "Bố chồng và con dâu"),
        (("父娘", "娘", "父親", "cha và con gái", "con gái trách cha"), "Cha già và con gái"),
        (("母娘", "医師の娘", "mẹ và con gái"), "Mẹ và con gái"),
        (("兄妹", "姉", "妹", "兄", "anh trai", "em gái", "anh em"), "Anh chị em trong gia đình và cha mẹ"),
        (("祖母", "祖父", "孫", "bà và cháu", "ông và cháu"), "Ông bà và cháu"),
        (("恩師", "元教師", "同窓会", "thầy giáo", "bạn học", "họp lớp"), "Thầy giáo cũ và học trò / Bạn học cũ"),
        (("夫婦", "定年", "熟年離婚", "夫", "妻", "vợ chồng", "chồng"), "Vợ chồng trung niên / tuổi nghỉ hưu"),
    ]
    for keys, label in mapping:
        if any(k.lower() in combined.lower() for k in keys):
            return label
    return "Gia đình Nhật Bản (Mối quan hệ thân tộc & trách nhiệm gia đình)"


def parse_idea_input_block(raw_text: str, custom_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Bóc tách đoạn văn bản đầu vào của người dùng:
    Hỗ trợ hoàn hảo Bộ Tiêu Đề Cố Định:
      P20 — 定年退職の日、夫は「お前とは別に暮らす」と言った。妻が差し出した30年前の家計ノートを読んだ夫は、初めて頭を下げた…
      VI: Về hưu, chồng đòi sống riêng; sổ chi tiêu 30 năm khiến ông xin lỗi
      Keyword: 定年, 熟年離婚, 夫婦, 家計簿 (vidIQ NOT_VERIFIED)
      Evidence: 家計ノート / sổ tài chính gia đình
      Reveal: Đời vợ có giấc mơ chưa thực hiện, không chỉ đòi công lao
      Capacity: PASS
    Cũng như định dạng mở rộng (Tiêu đề Nhật nháp, Tóm tắt, Quan hệ, Xung đột, Vật chứng, Ba lớp tiết lộ, Payoff...).
    """
    text = (raw_text or "").strip()
    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Tách các dòng ghép (VD: "Nhân vật: A. Xung đột: B")
    expanded_lines: List[str] = []
    inline_split_re = re.compile(
        r"\.\s+(?=(?:Xung đột|Payoff|Longform(?:\s+STEP\s*1|_CAPACITY_STEP1)?|Vật chứng|Quan hệ|Nhân vật|Ba lớp tiết lộ|Tóm tắt|Premise|VI|Keyword|Evidence|Reveal|Capacity)\s*[:：])",
        re.IGNORECASE,
    )
    for ln in raw_lines:
        parts = inline_split_re.split(ln)
        for p in parts:
            if p.strip():
                expanded_lines.append(p.strip())

    extracted: Dict[str, str] = {}
    pending_key: Optional[str] = None
    header_code_id: str = ""
    header_ja_title: str = ""

    for ln in expanded_lines:
        # 1. Kiểm tra dòng mở đầu kiểu "P01 — 義母の介護..." hoặc "P20 — 定年退職の日..."
        m_fixed = FIXED_PACK_HEADER_RE.match(ln)
        if m_fixed and not FIELD_LINE_PREFIX_RE.match(ln):
            raw_cid = re.sub(r"\s+", "", m_fixed.group("code_id")).upper()
            if not header_code_id:
                header_code_id = raw_cid
            if not header_ja_title:
                header_ja_title = m_fixed.group("ja_title").strip()
            continue

        # 2. Kiểm tra dòng mở đầu đánh số kiểu "1. 義母の介護..." (không phải dòng thuộc tính 01..23)
        m_num = NUMBERED_JA_TITLE_RE.match(ln)
        if m_num and not FIELD_LINE_PREFIX_RE.match(ln):
            if not header_ja_title:
                header_ja_title = m_num.group("ja_title").strip()
            continue

        # 3. Các dòng thuộc tính có dấu ':' hoặc '：' (VI:, Keyword:, Evidence:, Reveal:, Capacity:, Tóm tắt:...)
        if ":" in ln or "：" in ln:
            sep = ":" if ":" in ln else "："
            k, v = ln.split(sep, 1)
            k_clean = re.sub(r"^(?:\d+[\.\)\-:]|\-|•|\*)\s*", "", k.strip()).lower()
            v_clean = v.strip()
            if v_clean:
                extracted[k_clean] = v_clean
                pending_key = None
            else:
                pending_key = k_clean
        elif pending_key:
            extracted[pending_key] = ln.strip()
            pending_key = None

    def _pick_exact_or_contains(*keywords: str, default: str = "") -> str:
        # Ưu tiên khớp chính xác tên khóa trước (VD: "vi", "keyword", "evidence", "reveal", "capacity")
        for kw in keywords:
            kw_low = kw.lower()
            if kw_low in extracted and extracted[kw_low]:
                return extracted[kw_low]
        # Sau đó mới tìm theo chuỗi con
        for k, v in extracted.items():
            for kw in keywords:
                kw_low = kw.lower()
                if len(kw_low) <= 3:
                    if k == kw_low and v:
                        return v
                elif kw_low in k and v:
                    return v
        return default

    # Lấy Tiêu đề Nhật nháp (ưu tiên từ header P01 — ... hoặc trường Tiêu đề Nhật nháp)
    draft_title_ja = (
        header_ja_title
        or _pick_exact_or_contains("tiêu đề nhật nháp", "tiêu đề nháp", "tiêu đề nhật", "04.", "title")
    )
    if not draft_title_ja:
        # Chỉ tìm trên các dòng KHÔNG phải dòng thuộc tính (Keyword/Evidence) để không bao giờ lấy nhầm Keyword làm tiêu đề
        for ln in raw_lines:
            if FIELD_LINE_PREFIX_RE.match(ln):
                continue
            if re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", ln):
                cleaned_ln = re.sub(r"^(?:[A-Z]{1,6}\s*\d{1,4}|\d{1,3})\s*[—–\-:：\.]+\s*", "", ln, flags=re.IGNORECASE).strip()
                if cleaned_ln:
                    draft_title_ja = cleaned_ln
                    break

    # Lấy dòng VI: / Dịch ý / Tóm tắt
    vi_line = _pick_exact_or_contains("vi", "vn", "dịch ý", "05.")
    summary_raw = _pick_exact_or_contains("tóm tắt", "premise gốc", "10.", "premise", "nội dung")
    keyword_line = _pick_exact_or_contains("keyword", "keywords", "18.", "từ khóa")
    evidence_line = _pick_exact_or_contains("evidence", "proof", "vật chứng", "bằng chứng", "12.")
    reveal_line = _pick_exact_or_contains("reveal", "reveals", "ba lớp tiết lộ", "3 lớp tiết lộ", "lớp tiết lộ", "tiết lộ")
    capacity_line = _pick_exact_or_contains("capacity", "longform_capacity", "longform step 1", "longform", "03.", default="PASS")

    dich_y_vi = vi_line or summary_raw or (f"Bản dịch ý tiêu đề nháp: {draft_title_ja}" if draft_title_ja else "")

    # Xây dựng summary_vi (Premise gốc đầy đủ thông tin từ VI + Evidence + Reveal)
    if summary_raw:
        summary_vi = summary_raw
    elif vi_line:
        extra_parts = [vi_line.rstrip(".")]
        if evidence_line:
            extra_parts.append(f"Vật chứng trọng tâm: {evidence_line}")
        if reveal_line:
            extra_parts.append(f"Sự thật / Tiết lộ cốt lõi: {reveal_line}")
        summary_vi = ". ".join(extra_parts) + "."
    else:
        summary_vi = f"Triển khai câu chuyện gia đình Nhật Bản dài kỳ bám sát tiêu đề nháp: {draft_title_ja}" if draft_title_ja else ""

    relationship = _pick_exact_or_contains(
        "quan hệ", "nhân vật", "06.", "relation", "relationship",
        default=_infer_relationship_from_text(vi_line or summary_vi, keyword_line, draft_title_ja),
    )

    # Suy luận xung đột mở đầu từ vế đầu của câu VI (trước dấu ';') nếu không có trường Xung đột riêng
    inferred_conflict = "Hiểu lầm về trách nhiệm và sự hy sinh thầm lặng trong gia đình"
    if vi_line and ";" in vi_line:
        inferred_conflict = vi_line.split(";", 1)[0].strip()
    elif vi_line:
        inferred_conflict = vi_line.strip()

    conflict = _pick_exact_or_contains("xung đột", "09.", "conflict", default=inferred_conflict)
    proof_object = evidence_line or "Chứng từ và tài liệu ghi chép thực tế"
    tu_khoa_goi_y = keyword_line or "感動する話, 家族の確執, 仕送り, 介護, 朗読"
    longform_cap = capacity_line or "PASS"

    # Tách Ba lớp tiết lộ (hỗ trợ cả dạng 3 bước 'A → B → C' và dạng 1 câu Reveal cốt lõi trong bộ P01..P20)
    rev1 = _pick_exact_or_contains("13.", "lớp tiết lộ thứ nhất")
    rev2 = _pick_exact_or_contains("14.", "lớp tiết lộ thứ hai")
    rev3 = _pick_exact_or_contains("15.", "lớp tiết lộ thứ ba")

    if reveal_line and not (rev1 and rev2 and rev3):
        parts = [p.strip().rstrip(".") for p in re.split(r"→|->|=>|;", reveal_line) if p.strip()]
        if len(parts) >= 3:
            rev1 = rev1 or parts[0]
            rev2 = rev2 or parts[1]
            rev3 = rev3 or " → ".join(parts[2:])
        elif len(parts) == 2:
            rev1 = rev1 or f"Từ vật chứng ({proof_object}) phát hiện manh mối đầu tiên: {parts[0]}"
            rev2 = rev2 or f"Chuỗi sự thật quá khứ phía sau '{proof_object}' làm đảo ngược nhận định ban đầu"
            rev3 = rev3 or parts[1]
        else:
            # Khi Reveal là 1 câu đúc kết ý nghĩa đảo ngược (chuẩn bộ P01..P20)
            core_reveal = reveal_line.strip().rstrip(".")
            vi_second_half = vi_line.split(";", 1)[1].strip() if (vi_line and ";" in vi_line) else (vi_line or "Sự thật được hé lộ")
            rev1 = rev1 or f"Phát hiện vật chứng '{proof_object}' ngay sau biến cố mở đầu ({inferred_conflict})"
            rev2 = rev2 or f"Chi tiết cụ thể bên trong '{proof_object}' chứng minh sự thật: {vi_second_half}"
            rev3 = rev3 or f"Ý nghĩa đảo ngược sâu xa: {core_reveal}"

    rev1 = rev1 or "Bằng chứng đầu tiên hé lộ sự chăm sóc thầm lặng"
    rev2 = rev2 or "Sự thật tài chính / hy sinh phía sau chưa ai biết"
    rev3 = rev3 or "Ý nghĩa thực sự của trách nhiệm và tình thân"

    payoff = _pick_exact_or_contains(
        "payoff", "hệ quả", "16.",
        default=f"{reveal_line} — Hóa giải hiểu lầm và thức tỉnh lương tâm qua '{proof_object}'" if reveal_line else "Hóa giải hiểu lầm, thức tỉnh lương tâm và thay đổi trách nhiệm",
    )

    # Xác định Mã ID (Ưu tiên custom_id -> header_code_id như P01..P20 -> trường Mã/ID -> tự sinh)
    raw_id_field = _pick_exact_or_contains("mã", "id", "00.")
    ma_id = (custom_id or header_code_id or raw_id_field or f"DRAMA_{int(time.time()) % 100000:05d}").strip()
    ma_id = re.sub(r"[^A-Za-z0-9_\-]", "_", ma_id).upper()

    boi_canh = _pick_exact_or_contains(
        "không gian", "bối cảnh", "08.", "setting",
        default=f"Bối cảnh gia đình gắn với sự kiện: {vi_line or summary_vi[:80]}" if (vi_line or summary_vi) else "Không gian gia đình Nhật Bản đời thực",
    )
    nhom_chu_de = _pick_exact_or_contains(
        "trụ cột cảm xúc", "nhóm chủ đề", "chủ đề", "07.",
        default=f"{relationship} — {tu_khoa_goi_y}",
    )
    cau_hoi = _pick_exact_or_contains(
        "câu hỏi", "11.",
        default=f"Chuyện gì thực sự ẩn sau '{proof_object}' và vì sao '{rev3}' lại làm đảo ngược toàn bộ phán xét ban đầu?",
    )

    return {
        "ma_id": ma_id,
        "raw_input_text": text,
        "draft_title_ja": draft_title_ja,
        "locked_title": "",  # Sẽ được tự động cập nhật sau khi chạy STEP 2
        "dich_y_tieu_de_vi": dich_y_vi,
        "summary_vi": summary_vi,
        "relationship": relationship,
        "nhom_chu_de": nhom_chu_de,
        "boi_canh_su_kien": boi_canh,
        "conflict": conflict,
        "cau_hoi_can_tra_loi": cau_hoi,
        "proof_object": proof_object,
        "three_reveals_raw": reveal_line or f"{rev1} → {rev2} → {rev3}",
        "reveal_1": rev1,
        "reveal_2": rev2,
        "reveal_3": rev3,
        "payoff": payoff,
        "longform_capacity_step1": longform_cap,
        "uu_tien": _pick_exact_or_contains("01.", "ưu tiên", "priority", default="CAO (HIGH_PRIORITY)"),
        "co_che_story": _pick_exact_or_contains("17.", "cơ chế", "mechanism", default="SILENT_SACRIFICE_RECORD_REVERSAL (Vật chứng thực tế đảo ngược định kiến gia đình)"),
        "tu_khoa_goi_y": tu_khoa_goi_y,
        "ly_do_viet_dai": _pick_exact_or_contains("19.", "căn cứ", default=f"Capacity STEP 1 = {longform_cap}. Có chuỗi nhân quả 3 lớp tiết lộ ({rev1} -> {rev2} -> {rev3}) và sự dịch chuyển quan hệ giữa {relationship}."),
        "luu_y_logic": _pick_exact_or_contains("20.", "lưu ý", default="Đảm bảo tính hợp lý thực tế của chứng từ, quy trình y tế/pháp lý/tài chính gia đình Nhật Bản."),
        "goc_thumbnail": _pick_exact_or_contains("22.", "góc thumbnail", default=f"Bối cảnh {relationship}, vật chứng ({proof_object}) lộ ra khiến người trách móc sững sờ."),
        "research_source": _pick_exact_or_contains("23.", "nguồn gốc", "research_source", default=f"Bộ tiêu đề cố định từ STEP 1 ({ma_id} — Keyword: {tu_khoa_goi_y})."),
        "dinh_vi_batch": DEFAULT_BATCH_POSITIONING,
        "tham_chieu_motif": DEFAULT_MOTIF_REFERENCES,
        "status": "SAVED_READY",
        "current_step": "CHƯA CHẠY (Sẵn sàng từ Step 2)",
        "pure_char_count": 0,
        "audit_score": 0,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_step2_prompt_from_idea(idea: Dict[str, Any], custom_template: Optional[str] = None) -> str:
    """Điền đầy đủ thông tin ý tưởng đã lưu vào đúng mẫu Prompt STEP 2 của người dùng."""
    tpl = (custom_template or DEFAULT_STEP2_PROMPT_TEMPLATE).strip()
    replacements = {
        "{{MÃ_ID}}": idea.get("ma_id", "DRAMA_001"),
        "{{ĐỊNH_VỊ_BATCH}}": idea.get("dinh_vi_batch", DEFAULT_BATCH_POSITIONING),
        "{{ƯU_TIÊN}}": idea.get("uu_tien", "CAO"),
        "{{LONGFORM_CAPACITY_STEP1}}": idea.get("longform_capacity_step1", "PASS sơ bộ."),
        "{{TIÊU_ĐỀ_NHẬT_NHÁP_CHƯA_KHÓA}}": idea.get("draft_title_ja", ""),
        "{{DỊCH_Ý_TIÊU_ĐỀ_VI}}": idea.get("dich_y_tieu_de_vi") or idea.get("summary_vi", ""),
        "{{QUAN_HỆ_NHÂN_VẬT}}": idea.get("relationship", ""),
        "{{NHÓM_CHỦ_ĐỀ}}": idea.get("nhom_chu_de", ""),
        "{{BỐI_CẢNH_SỰ_KIỆN}}": idea.get("boi_canh_su_kien", ""),
        "{{XUNG_ĐỘT_MỞ_ĐẦU}}": idea.get("conflict", ""),
        "{{PREMISE_GỐC_STEP1}}": idea.get("summary_vi", ""),
        "{{CÂU_HỎI_CẦN_TRẢ_LỜI}}": idea.get("cau_hoi_can_tra_loi", ""),
        "{{VẬT_CHỨNG_GIEO_TRƯỚC}}": idea.get("proof_object", ""),
        "{{REVEAL_LỚP_MỘT_ĐỀ_XUẤT}}": idea.get("reveal_1", ""),
        "{{REVEAL_LỚP_HAI_ĐỀ_XUẤT}}": idea.get("reveal_2", ""),
        "{{REVEAL_LỚP_BA_ĐỀ_XUẤT}}": idea.get("reveal_3", ""),
        "{{PAYOFF_CẢM_XÚC_DỰ_KIẾN}}": idea.get("payoff", ""),
        "{{CƠ_CHẾ_STORY_STEP1}}": idea.get("co_che_story", ""),
        "{{TỪ_KHÓA_NHẬT_GỢI_Ý_CHƯA_XÁC_MINH_VOLUME}}": idea.get("tu_khoa_goi_y", ""),
        "{{LÝ_DO_CÓ_THỂ_VIẾT_DÀI_HOẶC_RỦI_RO}}": idea.get("ly_do_viet_dai", ""),
        "{{LƯU_Ý_LOGIC_PHÁP_LÝ_Y_TẾ}}": idea.get("luu_y_logic", ""),
        "{{GÓC_THUMBNAIL_ĐỀ_XUẤT}}": idea.get("goc_thumbnail", ""),
        "{{RESEARCH_SOURCE}}": idea.get("research_source", ""),
        "{{THAM_CHIẾU_MOTIF_BATCH}}": idea.get("tham_chieu_motif", DEFAULT_MOTIF_REFERENCES),
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, str(v or ""))
    return tpl


# ==============================================================================
# 4. CÁC HÀM BÓC TÁCH KẾT QUẢ & LỌC THOẠI TIẾNG NHẬT THUẦN CHO TTS
# ==============================================================================
def extract_locked_title_from_step2(step2_text: str, fallback_title: str = "") -> str:
    """Trích xuất LOCKED_TITLE chính thức từ phản hồi của STEP 2 (hỗ trợ cả viết cùng dòng và cách nhiều dòng trống)."""
    if not step2_text:
        return fallback_title

    jp_re = re.compile(r"[\u3040-\u30ff\u4e00-\u9faf]")
    vi_re = re.compile(r"[ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]", re.IGNORECASE)

    # 1. Quét theo các mốc tiêu đề khóa (LOCKED_TITLE — VERBATIM, LOCKED_TITLE, SELECTED TITLE, WINNING TITLE)
    header_pats = [
        r"LOCKED_TITLE\s*[—\-:：]+\s*VERBATIM",
        r"\*\*LOCKED_TITLE[:：]?\*\*",
        r"###\s*LOCKED_TITLE\b",
        r"LOCKED_TITLE\b",
        r"SELECTED\s+TITLE\b",
        r"WINNING\s+TITLE\b",
        r"WINNER\s*[—\-:：]+\s*TITLE\s*[ABC]\b",
    ]
    for hpat in header_pats:
        for m in re.finditer(hpat, step2_text, flags=re.IGNORECASE):
            tail = step2_text[m.end() : m.end() + 900]
            # Nếu có thẻ <title>...</title> ngay bên dưới
            mt = re.search(r"<title[^>]*>([^<]+)</title>", tail, flags=re.IGNORECASE)
            if mt:
                cand = mt.group(1).strip().strip("`*'\"「」 ")
                if len(jp_re.findall(cand)) >= 12 and not vi_re.search(cand):
                    return cand
            for raw_ln in tail.splitlines()[:10]:
                ln = re.sub(r"<[^>]+>", "", raw_ln).strip()
                ln = re.sub(r"^(?:LOCKED_TITLE|SELECTED\s+TITLE|TITLE\s+[ABC])[\s:：\-—]*", "", ln, flags=re.IGNORECASE).strip()
                ln = ln.strip("`*'\" ")
                if not ln or len(ln) < 15:
                    continue
                if len(jp_re.findall(ln)) >= 12 and not vi_re.search(ln):
                    return ln

    # 2. Fallback các mẫu cùng dòng
    patterns = [
        r"LOCKED_TITLE\s*[:：\-]\s*([^\r\n<]+)",
        r"WINNER\s*[:：\-]\s*(?:Title\s*[ABC]\s*[:：\-]?\s*)?([^\r\n<]+)",
    ]
    for pat in patterns:
        m = re.search(pat, step2_text, flags=re.IGNORECASE)
        if m:
            candidate = re.sub(r"<[^>]+>", "", m.group(1)).strip().strip("`*'\" ")
            if len(jp_re.findall(candidate)) >= 12 and not vi_re.search(candidate):
                return candidate
    return fallback_title


def extract_clean_japanese_narration(raw_text: str) -> str:
    """
    Lọc bỏ toàn bộ dòng tiêu đề tiếng Anh/Việt, [LOCKED_TITLE], [SELECTED_TITLE], bảng Handoff/Continuity Ledger,
    số đếm ký tự, chỉ giữ lại 100% văn bản tự sự & lời thoại tiếng Nhật thuần túy để đếm Pure Chars
    và đưa vào giọng đọc AI TTS / Render Video.
    """
    if not raw_text:
        return ""

    # Bước 1: Quét và xóa trọn cụm LOCKED_TITLE / SELECTED_TITLE / STEP 4 / PART A / <CodeBlock> / Metadata
    pre_cleaned, _ = strip_leaked_titles_and_metadata(raw_text)

    stop_markers = [
        "PART_PURE_CHARACTER_COUNT",
        "PART_LENGTH_GATE",
        "CONTINUITY_LEDGER",
        "CONTINUITY LEDGER",
        "PART_HANDOFF_LEDGER",
        "HANDOFF_LEDGER",
        "HANDOFF LEDGER",
        "PART_A_HANDOFF",
        "PART_B_HANDOFF",
        "PART_C_HANDOFF",
        "NEXT_ACTION",
        "READY_FOR_AUDIT",
        "PATCH_CHANGELOG",
    ]
    vi_re = re.compile(r"[ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]", re.IGNORECASE)

    clean_lines: List[str] = []
    for raw_ln in pre_cleaned.splitlines():
        ln = raw_ln.strip()
        if not ln:
            continue
        upper_ln = ln.upper().lstrip("#*>- `")
        if any(upper_ln.startswith(mk) or f"**{mk}" in upper_ln or f"`{mk}" in upper_ln for mk in stop_markers):
            break
        # Bỏ các dòng tiêu đề markdown hoặc nhãn kỹ thuật
        if ln.startswith(("#", "```", "---", "===")):
            continue
        # Làm sạch dấu ** hoặc ` hoặc thẻ XML trước khi kiểm tra key:value
        cleaned = re.sub(r"<[^>]+>", "", ln).replace("**", "").replace("`", "").strip()
        if not cleaned:
            continue
        if re.match(r"^(?:[A-Z]{1,6}\d{1,5}\s*[—–\-·:：]+\s*)?(?:STEP\s*[1-7]\b|BUILD\s+PART\s*[ABC]\b|PART\s*[:：\-—–·]?\s*[ABC]\b|SCENE\s+[ABC]?\d+\b|CHAPTER\s+\d+\b|第\d+章|【.*】)\s*[:：\-—–·]?.*$", cleaned, re.IGNORECASE) and len(cleaned) < 90:
            continue
        # Bỏ các dòng có chứa ký tự dấu tiếng Việt (tránh ghi chú tiếng Việt lọt vào kịch bản TTS)
        if vi_re.search(cleaned):
            continue
        # Chỉ giữ dòng có chứa chữ Nhật (Hiragana / Katakana / Kanji) và không phải dòng key:value tiếng Anh
        has_jp = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", cleaned))
        is_meta_kv = bool(re.match(r"^[A-Z][A-Z0-9_/\-\s]{1,35}[:：]", cleaned))
        if has_jp and not is_meta_kv:
            clean_lines.append(cleaned)

    final_clean, _ = strip_leaked_titles_and_metadata("\n".join(clean_lines))
    return final_clean


def trim_japanese_to_max_pure_chars(text: str, max_pure_chars: int = 16800) -> str:
    """Nếu 1 Part vượt quá trần ký tự thuần, cắt gọn tại dấu chấm câu tiếng Nhật gần nhất."""
    if pure_char_count(text) <= max_pure_chars:
        return text
    sentences = split_japanese_script(text)
    kept: List[str] = []
    running = 0
    for s in sentences:
        c = pure_char_count(s)
        if running + c > max_pure_chars and running >= 13334:
            break
        kept.append(s)
        running += c
    return "\n".join(kept)


# ==============================================================================
# 5. ĐỘNG CƠ CHẠY DÂY CHUYỀN ADAS (STEP 2 -> STEP 3 -> STEP 4 A/B/C -> STEP 5 -> STEP 6)
# ==============================================================================
class ADASScriptEngine:
    """
    Quản lý danh sách Ý tưởng/Tiêu đề đã lưu và tự động điều phối 3 Tài khoản ChatGPT Web
    chạy từ STEP 2 -> STEP 6, sau đó đẩy thẳng sang ProductionPipeline để xuất Video.
    """

    def __init__(self, root_dir: Path, video_pipeline: Any = None):
        self.root_dir = Path(root_dir).resolve()
        if self.root_dir.name.lower() == "app":
            self.root_dir = self.root_dir.parent
        self.video_pipeline = video_pipeline
        self.ideas_file = self.root_dir / "saved_ideas.json"
        self.step2_template_file = self.root_dir / "step2_prompt_template.txt"
        self.projects_dir = self.root_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        self.lock = threading.Lock()
        self.ideas_io_lock = threading.RLock()
        self.is_running = False
        self.should_stop = False
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []

        self.state: Dict[str, Any] = {
            "status": "idle",
            "current_ma_id": None,
            "current_step": "Sẵn sàng",
            "progress": 0.0,
            "message": "Sẵn sàng nhận Tiêu đề nháp & Tóm tắt để chạy Step 2 -> Step 6.",
            "logs": [],
        }

        if self.video_pipeline and hasattr(self.video_pipeline, "set_job_status_callback"):
            try:
                self.video_pipeline.set_job_status_callback(self._on_video_pipeline_job_update)
            except Exception:
                pass

        self._sync_projects_disk_state()

    def _on_video_pipeline_job_update(
        self,
        ma_id: str,
        status: str,
        step_desc: str,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Nhận thông báo trực tiếp từ ProductionPipeline khi dự án đang tạo Voice / Render MP4 / Hoàn tất."""
        fields: Dict[str, Any] = {"status": status, "current_step": step_desc}
        if status == "COMPLETED_VIDEO":
            fields["has_video_mp4"] = True
        elif status in ("ERROR_VIDEO", "VIDEO_RENDERING", "VIDEO_QUEUED", "SCRIPT_DONE"):
            fields["has_video_mp4"] = False
        if extra:
            if extra.get("video_path") and status == "COMPLETED_VIDEO":
                fields["has_video_mp4"] = True
                fields["video_mp4_path"] = str(extra["video_path"])
            if extra.get("error"):
                fields["last_error"] = str(extra["error"])
        self._update_idea_record(ma_id, **fields)
        self._emit(
            current_ma_id=ma_id,
            current_step=step_desc,
            message=f"[{ma_id}] {step_desc}",
        )

    def subscribe(self, cb: Callable[[Dict[str, Any]], None]):
        self.listeners.append(cb)

    def _emit(self, **kwargs):
        with self.lock:
            for k, v in kwargs.items():
                self.state[k] = v
            msg = kwargs.get("message")
            curr_id = kwargs.get("current_ma_id") or self.state.get("current_ma_id")
            if msg:
                ts = time.strftime("%H:%M:%S")
                log_line = f"[{ts}] {msg}"
                logs = self.state.setdefault("logs", [])
                if not logs or logs[-1] != log_line:
                    logs.append(log_line)
                    if len(logs) > 120:
                        self.state["logs"] = logs[-120:]
            snapshot = dict(self.state)

        if msg:
            st = str(kwargs.get("status", "")).lower()
            if st == "error" or "❌" in msg:
                log_error("SCRIPT", msg, project_id=curr_id)
            elif "⚠️" in msg:
                log_warn("SCRIPT", msg, project_id=curr_id)
            else:
                log_info("SCRIPT", msg, project_id=curr_id)

        for cb in self.listeners:
            try:
                cb({"type": "adas_update", "adas_state": snapshot})
            except Exception:
                pass

    def get_state(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.state)

    def get_step2_template(self) -> str:
        if self.step2_template_file.exists():
            try:
                return self.step2_template_file.read_text(encoding="utf-8")
            except Exception:
                pass
        return DEFAULT_STEP2_PROMPT_TEMPLATE

    def save_step2_template(self, template_text: str) -> str:
        clean = (template_text or "").strip() or DEFAULT_STEP2_PROMPT_TEMPLATE
        self.step2_template_file.write_text(clean, encoding="utf-8")
        return clean

    def _get_persistent_appdata_dir(self) -> Path:
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "Drama_Nhat_Studio"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return base

    def _load_deleted_ids(self) -> set[str]:
        """Đọc danh sách các mã dự án/tiêu đề mà người dùng đã chủ động xóa để không bao giờ tự load lại khi bật app."""
        deleted: set[str] = set()
        for fp in (
            self.root_dir / "deleted_ideas.json",
            self._get_persistent_appdata_dir() / "deleted_ideas.json",
        ):
            if fp.exists():
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        deleted.update(str(x).strip() for x in data if x)
                except Exception:
                    pass
        return deleted

    def _save_deleted_ids(self, deleted_set: set[str]):
        payload = json.dumps(sorted(deleted_set), ensure_ascii=False, indent=2)
        for fp in (
            self.root_dir / "deleted_ideas.json",
            self._get_persistent_appdata_dir() / "deleted_ideas.json",
        ):
            try:
                fp.write_text(payload, encoding="utf-8")
            except Exception:
                pass

    def _mark_ids_deleted(self, ma_ids: List[str]):
        cur = self._load_deleted_ids()
        for mid in ma_ids:
            m = (mid or "").strip()
            if m:
                cur.add(m)
        self._save_deleted_ids(cur)

    def _unmark_ids_deleted(self, ma_ids: List[str]):
        cur = self._load_deleted_ids()
        changed = False
        for mid in ma_ids:
            m = (mid or "").strip()
            if m in cur:
                cur.discard(m)
                changed = True
        if changed:
            self._save_deleted_ids(cur)

    def _register_and_sync_external_projects(self):
        """
        Lưu đường dẫn thư mục `projects/` hiện tại vào `%LOCALAPPDATA%\\Drama_Nhat_Studio\\projects_dirs_registry.json`.
        Tuyệt đối KHÔNG tự động copy ngầm các thư mục dự án cũ từ thư mục khác sang `projects/` để đảm bảo
        khi người dùng xóa hết folder trong `projects/`, ứng dụng luôn phản ánh đúng 100% trạng thái thực tế của `projects/`.
        """
        appdata_dir = self._get_persistent_appdata_dir()
        reg_file = appdata_dir / "projects_dirs_registry.json"
        known_dirs: List[str] = []
        if reg_file.exists():
            try:
                data = json.loads(reg_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    known_dirs = [str(x) for x in data if x]
            except Exception:
                pass

        curr_str = str(self.projects_dir.resolve())
        if curr_str not in known_dirs:
            known_dirs.insert(0, curr_str)
            try:
                reg_file.write_text(json.dumps(known_dirs[:15], ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

    def load_saved_ideas(self) -> List[Dict[str, Any]]:
        with self.ideas_io_lock:
            raw_list: Optional[List[Dict[str, Any]]] = None
            if self.ideas_file.exists():
                try:
                    data = json.loads(self.ideas_file.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        raw_list = data
                except Exception:
                    raw_list = None

            if raw_list is None:
                bak_file = self._get_persistent_appdata_dir() / "saved_ideas_backup.json"
                if bak_file.exists():
                    try:
                        data = json.loads(bak_file.read_text(encoding="utf-8"))
                        if isinstance(data, list):
                            raw_list = data
                    except Exception:
                        raw_list = []

            if raw_list is None:
                raw_list = []

            # Luôn đối chiếu trực tiếp với thư mục `projects/` trên ổ cứng:
            # Nếu người dùng đã xóa 1 hoặc toàn bộ folder trong `projects/`, lập tức loại bỏ khỏi danh sách hiển thị & lưu lại!
            if self.projects_dir.exists():
                try:
                    existing_dirs = {
                        d.name.strip()
                        for d in self.projects_dir.iterdir()
                        if d.is_dir() and not (d / ".deleted_by_user").exists()
                    }
                except Exception:
                    existing_dirs = set()
            else:
                existing_dirs = set()

            filtered_list = [
                it
                for it in raw_list
                if isinstance(it, dict) and str(it.get("ma_id", "")).strip() in existing_dirs
            ]
            if len(filtered_list) != len(raw_list):
                self.save_ideas_list(filtered_list)
            return filtered_list

    def save_ideas_list(self, ideas: List[Dict[str, Any]]):
        with self.ideas_io_lock:
            payload = json.dumps(ideas, ensure_ascii=False, indent=2)
            tmp_file = self.ideas_file.with_suffix(".json.tmp")
            try:
                tmp_file.write_text(payload, encoding="utf-8")
                os.replace(str(tmp_file), str(self.ideas_file))
            except Exception:
                self.ideas_file.write_text(payload, encoding="utf-8")
            # Luôn đồng bộ cả khi ideas == [] để khi xóa hết folder trong projects/, bản backup cũng được làm sạch 100%
            try:
                bak_file = self._get_persistent_appdata_dir() / "saved_ideas_backup.json"
                bak_tmp = bak_file.with_suffix(".json.tmp")
                bak_tmp.write_text(payload, encoding="utf-8")
                os.replace(str(bak_tmp), str(bak_file))
            except Exception:
                pass

    def _sanitize_and_note_script_text(self, ma_id: str, raw_text: str, source_label: str = "") -> Tuple[str, int]:
        """
        Quét, ghi nhận (note) và xóa sạch 100% các dòng [LOCKED_TITLE], SELECTED_TITLE,
        PART A/B/C header, CONTINUITY, ENDING hoặc thẻ XML bị rò rỉ trong kịch bản.
        Trả về `(cleaned_text, removed_lines_count)`.
        """
        if not raw_text:
            return "", 0
        cleaned, removed_lines = strip_leaked_titles_and_metadata(raw_text)
        if removed_lines:
            lbl = f" ({source_label})" if source_label else ""
            removed_strs = [str(ln[1] if isinstance(ln, (tuple, list)) and len(ln) > 1 else ln) for ln in removed_lines]
            sample_preview = " | ".join([s[:55] for s in removed_strs[:2]])
            log_info(
                "SCRIPT",
                f"🛡️ [Agent Kiểm Tra Kịch Bản] Đã ghi nhận & tự động xóa {len(removed_strs)} dòng [LOCKED_TITLE]/Metadata rò rỉ trong [{ma_id}]{lbl}: {sample_preview}",
                project_id=ma_id,
            )
            try:
                p_dir = self.projects_dir / ma_id
                assets_d = p_dir / "assets"
                if assets_d.exists():
                    leaked_log_f = assets_d / "leaked_lines_log.json"
                    existing_pool: List[str] = []
                    if leaked_log_f.exists():
                        try:
                            existing_pool = json.loads(leaked_log_f.read_text(encoding="utf-8", errors="ignore"))
                        except Exception:
                            existing_pool = []
                    for rs in removed_strs:
                        if rs not in existing_pool:
                            existing_pool.append(rs)
                    leaked_log_f.write_text(json.dumps(existing_pool, ensure_ascii=False, indent=2), encoding="utf-8")

                audit_note_file = p_dir / "step5_audit_report.txt"
                note_block = (
                    f"\n[AUTO-CLEAN NOTE — {time.strftime('%Y-%m-%d %H:%M:%S')}]{lbl}: "
                    f"Đã phát hiện và xóa {len(removed_strs)} dòng [LOCKED_TITLE]/Metadata rò rỉ:\n"
                    + "\n".join([f"  - Removed: {s}" for s in removed_strs])
                    + "\n"
                )
                if audit_note_file.exists():
                    existing_audit = audit_note_file.read_text(encoding="utf-8", errors="ignore")
                    if removed_strs[0] not in existing_audit:
                        audit_note_file.write_text(existing_audit + note_block, encoding="utf-8")
            except Exception:
                pass
        return cleaned, len(removed_lines)

    def get_script_parts_progress(self, ma_id: str, min_part_chars: int = 9500) -> Dict[str, Any]:
        """
        Kiểm tra chi tiết tiến độ 3 phần (`part_a.txt`, `part_b.txt`, `part_c.txt`) của dự án `ma_id`.
        Giúp phát hiện chính xác các dự án bị thiếu Part (ví dụ mới xong Part A 15.848 chữ hoặc Part A+B 32.684 chữ)
        đồng thời tự động làm sạch [LOCKED_TITLE]/Metadata nếu bị rò rỉ trong các file Part.
        """
        proj_dir = self.projects_dir / ma_id
        done_parts: List[str] = []
        missing_parts: List[str] = []
        part_counts: Dict[str, int] = {"A": 0, "B": 0, "C": 0}
        part_texts: Dict[str, str] = {}

        for p_let in ("A", "B", "C"):
            p_file = proj_dir / f"part_{p_let.lower()}.txt"
            cnt = 0
            txt = ""
            if p_file.exists():
                try:
                    raw_p = p_file.read_text(encoding="utf-8").strip()
                    txt, rem_cnt = self._sanitize_and_note_script_text(ma_id, raw_p, source_label=f"part_{p_let.lower()}.txt")
                    if rem_cnt > 0 and txt:
                        p_file.write_text(txt, encoding="utf-8")
                    cnt = pure_char_count(txt)
                except Exception:
                    cnt = 0
            part_counts[p_let] = cnt
            if cnt >= min_part_chars:
                done_parts.append(p_let)
                part_texts[p_let] = txt
            else:
                missing_parts.append(p_let)

        partial_total = sum(part_counts[p] for p in done_parts)
        return {
            "done_parts": done_parts,
            "missing_parts": missing_parts,
            "part_counts": part_counts,
            "part_texts": part_texts,
            "partial_chars": partial_total,
            "all_three_valid": len(done_parts) == 3,
        }

    def has_valid_script_on_disk(self, ma_id: str, min_pure_chars: int = 35000, min_part_chars: int = 9500) -> Tuple[bool, str, int]:
        """
        Kiểm tra nghiêm ngặt xem dự án `ma_id` đã có kịch bản tiếng Nhật ĐỦ 3 PART (A + B + C) và ĐỦ ĐỘ DÀI CHUẨN hay chưa:
        - Nếu dự án có tạo các file `part_a.txt`, `part_b.txt`, `part_c.txt`: BẮT BUỘC cả 3 Part đều phải đạt `>= min_part_chars` (9.500 chữ/part)
          và tổng cộng `>= min_pure_chars` (35.000 chữ thuần).
        - Tự động quét và xóa sạch mọi dòng `[LOCKED_TITLE]` / Metadata rò rỉ trong cả `script_clean.txt` và `renders/{ma_id}_KICH_BAN.txt`.
        - Nếu trước đó `script_clean.txt` bị ghi dở dang khi mới xong 1 Part (~15.800 chữ) hoặc 2 Part (~32.600 chữ),
          hệ thống tự động xóa file `script_clean.txt` bị thiếu đó (giữ nguyên các `part_a.txt` / `part_b.txt` đã viết xong)
          và trả về `False` để viết tiếp các Part còn thiếu!
        """
        proj_dir = self.projects_dir / ma_id
        if not proj_dir.exists():
            return False, "", 0

        pa, pb, pc = proj_dir / "part_a.txt", proj_dir / "part_b.txt", proj_dir / "part_c.txt"
        script_file = proj_dir / "script_clean.txt"
        render_script_file = proj_dir / "renders" / f"{ma_id}_KICH_BAN.txt"
        has_any_part_file = pa.exists() or pb.exists() or pc.exists()

        if has_any_part_file:
            prog = self.get_script_parts_progress(ma_id, min_part_chars=min_part_chars)
            if prog["all_three_valid"]:
                combined = "\n\n".join([prog["part_texts"]["A"], prog["part_texts"]["B"], prog["part_texts"]["C"]]).strip()
                combined, _ = self._sanitize_and_note_script_text(ma_id, combined, source_label="combined_parts")
                cnt = pure_char_count(combined)
                if cnt >= min_pure_chars:
                    try:
                        need_sync_sc = not script_file.exists()
                        if not need_sync_sc:
                            cur_sc_raw = script_file.read_text(encoding="utf-8", errors="ignore")
                            _, sc_rem = strip_leaked_titles_and_metadata(cur_sc_raw)
                            if sc_rem or pure_char_count(cur_sc_raw) != cnt:
                                need_sync_sc = True
                        if need_sync_sc:
                            script_file.write_text(combined, encoding="utf-8")
                    except Exception:
                        pass
                    try:
                        if render_script_file.exists():
                            cur_ren_raw = render_script_file.read_text(encoding="utf-8", errors="ignore")
                            _, ren_rem = strip_leaked_titles_and_metadata(cur_ren_raw)
                            if ren_rem or pure_char_count(cur_ren_raw) != cnt:
                                render_script_file.write_text(combined, encoding="utf-8")
                    except Exception:
                        pass
                    return True, combined, cnt

            # Nếu có file part nhưng chưa đủ cả 3 Part hợp lệ (VD: P16 mới có Part A, P17 mới có Part A+B):
            # Xóa các file part rỗng/non (< min_part_chars) và xóa script_clean.txt bị ghép thiếu (nếu có) để không bao giờ bị nhận nhầm là đã xong!
            for p_let in prog["missing_parts"]:
                bad_pf = proj_dir / f"part_{p_let.lower()}.txt"
                if bad_pf.exists():
                    try:
                        bad_pf.unlink()
                    except Exception:
                        pass
            if script_file.exists():
                try:
                    sc_txt = script_file.read_text(encoding="utf-8").strip()
                    if pure_char_count(sc_txt) < min_pure_chars or not prog["all_three_valid"]:
                        script_file.unlink()
                except Exception:
                    pass
            return False, "", prog["partial_chars"]

        # Trường hợp kịch bản nạp trực tiếp hoặc copy từ máy khác sang (không chia file part_a/b/c):
        alt_script_candidates = [
            script_file,
            proj_dir / f"{ma_id}_KICH_BAN.txt",
            render_script_file,
            proj_dir / f"{ma_id}.txt",
        ]
        for cand_f in alt_script_candidates:
            if cand_f.exists():
                try:
                    raw_txt = cand_f.read_text(encoding="utf-8", errors="ignore").strip()
                    txt, rem_cnt = self._sanitize_and_note_script_text(ma_id, raw_txt, source_label=cand_f.name)
                    cnt = pure_char_count(txt)
                    if cnt >= min_pure_chars:
                        if rem_cnt > 0:
                            try:
                                cand_f.write_text(txt, encoding="utf-8")
                            except Exception:
                                pass
                        if cand_f != script_file or rem_cnt > 0:
                            try:
                                script_file.write_text(txt, encoding="utf-8")
                            except Exception:
                                pass
                        if render_script_file.exists() and (cand_f != render_script_file or rem_cnt > 0):
                            try:
                                render_script_file.write_text(txt, encoding="utf-8")
                            except Exception:
                                pass
                        return True, txt, cnt
                except Exception:
                    pass

        # Quét dự phòng các file .txt lớn trong thư mục dự án (nếu người dùng đặt tên file kịch bản tự do khi copy qua)
        ignore_kw = ("SEO", "STEP", "AUDIT", "TIEU_DE", "PROMPT", "IDEA_INFO")
        for scan_dir in (proj_dir, proj_dir / "renders"):
            if not scan_dir.exists():
                continue
            for tf in sorted(scan_dir.glob("*.txt")):
                up_name = tf.name.upper()
                if any(k in up_name for k in ignore_kw) or up_name in ("PART_A.TXT", "PART_B.TXT", "PART_C.TXT"):
                    continue
                try:
                    raw_txt = tf.read_text(encoding="utf-8", errors="ignore").strip()
                    txt, rem_cnt = self._sanitize_and_note_script_text(ma_id, raw_txt, source_label=tf.name)
                    cnt = pure_char_count(txt)
                    if cnt >= min_pure_chars:
                        if rem_cnt > 0:
                            try:
                                tf.write_text(txt, encoding="utf-8")
                            except Exception:
                                pass
                        try:
                            script_file.write_text(txt, encoding="utf-8")
                        except Exception:
                            pass
                        return True, txt, cnt
                except Exception:
                    pass

        return False, "", 0

    def has_thumbnail_and_seo_on_disk(self, ma_id: str) -> Tuple[bool, bool, str]:
        """
        Kiểm tra và tự động đồng bộ file Thumbnail + SEO của dự án `ma_id` (hỗ trợ cả khi copy từ máy khác sang).
        Trả về `(has_thumbnail, has_seo, thumb_path_str)`.
        """
        proj_dir = self.projects_dir / ma_id
        if not proj_dir.exists():
            return False, False, ""

        renders_dir = proj_dir / "renders"
        target_thumb = renders_dir / f"{ma_id}_THUMBNAIL_1.png"
        found_thumb: Optional[Path] = None

        thumb_candidates = [
            target_thumb,
            proj_dir / f"{ma_id}_THUMBNAIL_1.png",
            renders_dir / f"{ma_id}_THUMBNAIL.png",
            proj_dir / f"{ma_id}_THUMBNAIL.png",
            renders_dir / f"{ma_id}.png",
            proj_dir / f"{ma_id}.png",
        ]
        for tc in thumb_candidates:
            if tc.exists() and tc.stat().st_size > 10_000:
                found_thumb = tc
                break

        if found_thumb is None:
            for scan_dir in (renders_dir, proj_dir):
                if not scan_dir.exists():
                    continue
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                    for img_f in sorted(scan_dir.glob(ext)):
                        if img_f.stat().st_size > 10_000:
                            found_thumb = img_f
                            break
                    if found_thumb:
                        break
                if found_thumb:
                    break

        if found_thumb is not None and found_thumb != target_thumb:
            try:
                renders_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(found_thumb, target_thumb)
                found_thumb = target_thumb
            except Exception:
                pass

        master_seo = proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
        render_seo = renders_dir / f"{ma_id}_SEO.txt"
        seo_candidates = [
            master_seo,
            render_seo,
            proj_dir / f"{ma_id}_SEO.txt",
            proj_dir / "step6_seo_pack.txt",
        ]
        found_seo: Optional[Path] = None
        for sc in seo_candidates:
            if sc.exists() and sc.stat().st_size > 80:
                found_seo = sc
                break

        if found_seo is not None:
            try:
                seo_txt = found_seo.read_text(encoding="utf-8", errors="ignore")
                if not master_seo.exists():
                    master_seo.write_text(seo_txt, encoding="utf-8")
                if not render_seo.exists():
                    renders_dir.mkdir(parents=True, exist_ok=True)
                    render_seo.write_text(seo_txt, encoding="utf-8")
            except Exception:
                pass

        return (found_thumb is not None), (found_seo is not None), (str(found_thumb) if found_thumb else "")

    def has_valid_video_mp4_on_disk(
        self,
        ma_id: str,
        sc_chars: int = 0,
        auto_delete_corrupted: bool = True,
    ) -> Tuple[bool, Optional[Path], str]:
        """
        Kiểm định nghiêm ngặt xem dự án `ma_id` có file `{ma_id}_master.mp4` HOÀN CHỈNH 100% trên ổ cứng hay không.
        - Tuyệt đối KHÔNG chỉ kiểm tra `st_size > 1MB`.
        - Kiểm tra cấu trúc `moov atom`, luồng video/audio, thời lượng thực tế so với `master_voice.wav` và độ dài kịch bản.
        - Nếu phát hiện file MP4 bị lỗi hoặc bị ngắt giữa chừng (khi không đang trong luồng render active),
          tự động xóa file MP4 hỏng và trả về `(False, None, reason)` để dự án được phân loại là lỗi/chưa render và chạy lại!
        """
        if not hasattr(self, "_mp4_valid_cache"):
            self._mp4_valid_cache: Dict[str, Tuple[int, int, bool, str]] = {}

        vp_running = bool(self.video_pipeline and getattr(self.video_pipeline, "is_running", False))
        vp_active = set(getattr(self.video_pipeline, "active_projects", set())) if vp_running else set()
        is_actively_rendering = ma_id in vp_active

        p_dir = self.projects_dir / ma_id
        renders_dir = p_dir / "renders"
        if not renders_dir.exists():
            self._mp4_valid_cache.pop(ma_id, None)
            return False, None, "missing"

        # Dọn các file tạm _rendering_tmp.mp4 bị bỏ lại nếu dự án hiện không đang render
        if not is_actively_rendering:
            for tmp_mp4 in renders_dir.glob("*_rendering_tmp.mp4"):
                try:
                    tmp_mp4.unlink()
                except Exception:
                    pass

        mp4_file = renders_dir / f"{ma_id}_master.mp4"
        if not mp4_file.exists():
            self._mp4_valid_cache.pop(ma_id, None)
            return False, None, "rendering_in_progress" if is_actively_rendering else "missing"

        if is_actively_rendering:
            return False, None, "rendering_in_progress"

        try:
            st = mp4_file.stat()
            mtime_ns, st_size = st.st_mtime_ns, st.st_size
        except Exception:
            return False, None, "stat_error"

        cached = self._mp4_valid_cache.get(ma_id)
        if cached and cached[0] == mtime_ns and cached[1] == st_size and cached[2]:
            return True, mp4_file, "ok"

        if sc_chars <= 0:
            _, _, sc_chars = self.has_valid_script_on_disk(ma_id)

        from backend.sync_checker import validate_completed_mp4_file
        master_wav = p_dir / "assets" / "master_voice.wav"
        val = validate_completed_mp4_file(
            mp4_path=mp4_file,
            master_wav_path=master_wav if master_wav.exists() else None,
            script_char_count=sc_chars,
        )

        if val.get("valid"):
            self._mp4_valid_cache[ma_id] = (mtime_ns, st_size, True, "ok")
            return True, mp4_file, "ok"

        reason = str(val.get("reason") or "Video MP4 bị lỗi hoặc ngắt giữa chừng")
        self._mp4_valid_cache.pop(ma_id, None)
        log_warn(
            "RENDER",
            f"⚠️ [{ma_id}] Phát hiện file MP4 bị lỗi/ngắt giữa chừng ({reason}). Đã tự động lọc sang danh sách Lỗi / Chưa Render để chạy tiếp!",
            project_id=ma_id,
        )
        if auto_delete_corrupted:
            try:
                mp4_file.unlink()
            except Exception:
                pass
        return False, None, reason

    def _reconstruct_idea_from_project_dir(self, p_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Khôi phục bản ghi dự án từ thư mục `projects/<ma_id>` khi dự án đó:
        - ĐÃ TẠO XONG KỊCH BẢN ĐỦ 3 PART (`has_sc = True`), HOẶC
        - ĐANG VIẾT DỞ 1-2 PART (`partial_chars >= 9500`, để người dùng bấm viết tiếp Part thiếu), HOẶC
        - ĐÃ XUẤT VIDEO MP4 HOÀN CHỈNH (`has_mp4 = True`).
        Tuyệt đối KHÔNG tự động khôi phục các tiêu đề nháp chưa viết chữ nào (`partial_chars == 0`) đã bị xóa!
        """
        mid = p_dir.name
        has_sc, sc_txt, sc_chars = self.has_valid_script_on_disk(mid)
        prog = self.get_script_parts_progress(mid)
        partial_chars = prog["partial_chars"]
        has_partial = len(prog["done_parts"]) > 0 and not has_sc
        has_mp4, mp4_f, mp4_reason = self.has_valid_video_mp4_on_disk(mid, sc_chars=sc_chars if has_sc else partial_chars)

        info_file = p_dir / "idea_info.json"
        if info_file.exists():
            try:
                info_data = json.loads(info_file.read_text(encoding="utf-8"))
                if isinstance(info_data, dict) and info_data.get("ma_id"):
                    has_th, has_seo, th_path = self.has_thumbnail_and_seo_on_disk(mid)
                    info_data["has_script"] = has_sc
                    info_data["has_thumbnail"] = has_th
                    info_data["has_seo"] = has_seo
                    if th_path:
                        info_data["thumbnail_path"] = th_path
                    info_data["pure_char_count"] = sc_chars if has_sc else partial_chars
                    info_data["has_video_mp4"] = has_mp4
                    info_data["completed_parts_count"] = 3 if has_sc else len(prog["done_parts"])
                    info_data["missing_parts"] = [] if has_sc else prog["missing_parts"]
                    if has_mp4:
                        info_data["status"] = "COMPLETED_VIDEO"
                    elif has_sc:
                        if mp4_reason not in ("missing", "rendering_in_progress", "ok") or info_data.get("status") == "ERROR_VIDEO":
                            info_data["status"] = "ERROR_VIDEO"
                            info_data["current_step"] = f"❌ Video bị ngắt/lỗi ({mp4_reason if mp4_reason != 'missing' else 'Chưa hoàn tất'}) — Chờ Render lại ({sc_chars:,} chữ)"
                        else:
                            info_data["status"] = "SCRIPT_DONE"
                            info_data["current_step"] = f"📝 Đã xong Kịch bản ({sc_chars:,} chữ) — Sẵn sàng Render MP4"
                    elif has_partial:
                        miss_str = ", ".join(prog["missing_parts"])
                        info_data["status"] = "PARTIAL_SCRIPT"
                        info_data["current_step"] = f"⚠️ Thiếu Part {miss_str} (Mới có {len(prog['done_parts'])}/3 Part: {partial_chars:,} chữ)"
                    else:
                        info_data["status"] = "SAVED_READY"
                    return info_data
            except Exception:
                pass

        if not (has_sc or has_partial or has_mp4):
            return None

        step2_f = p_dir / "step2_title_thumbnail.txt"
        seo_f = p_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"

        locked_title = ""
        if step2_f.exists():
            try:
                locked_title = extract_locked_title_from_step2(step2_f.read_text(encoding="utf-8"), fallback_title="")
            except Exception:
                pass
        if not locked_title and seo_f.exists():
            try:
                for ln in seo_f.read_text(encoding="utf-8").splitlines():
                    ln_s = ln.strip()
                    if any("\u3040" <= ch <= "\u9fff" for ch in ln_s) and len(ln_s) >= 15:
                        locked_title = ln_s.lstrip("-•*0123456789. ").strip()
                        break
            except Exception:
                pass
        if not locked_title and sc_txt:
            first_line = sc_txt.splitlines()[0].strip() if sc_txt.splitlines() else ""
            locked_title = first_line[:95] if first_line else f"Dự án khôi phục [{mid}]"

        reconstructed = parse_idea_input_block(locked_title or f"{mid} — Dự án khôi phục từ ổ cứng", custom_id=mid)
        if locked_title:
            reconstructed["locked_title"] = locked_title
            reconstructed["draft_title_ja"] = locked_title
        reconstructed["has_script"] = has_sc
        reconstructed["pure_char_count"] = sc_chars if has_sc else partial_chars
        reconstructed["has_video_mp4"] = has_mp4
        reconstructed["completed_parts_count"] = 3 if has_sc else len(prog["done_parts"])
        reconstructed["missing_parts"] = [] if has_sc else prog["missing_parts"]
        if has_mp4:
            reconstructed["status"] = "COMPLETED_VIDEO"
            reconstructed["current_step"] = f"✅ Đã xuất Video MP4 ({sc_chars:,} chữ)"
            reconstructed["video_mp4_path"] = str(mp4_f)
        elif has_sc:
            reconstructed["status"] = "SCRIPT_DONE"
            reconstructed["current_step"] = f"📝 Đã xong Kịch bản ({sc_chars:,} chữ) — Sẵn sàng Render MP4"
        else:
            miss_str = ", ".join(prog["missing_parts"])
            reconstructed["status"] = "PARTIAL_SCRIPT"
            reconstructed["current_step"] = f"⚠️ Thiếu Part {miss_str} (Mới có {len(prog['done_parts'])}/3 Part: {partial_chars:,} chữ)"

        try:
            info_file.write_text(json.dumps(reconstructed, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return reconstructed

    def _sync_projects_disk_state(self, force_restore_deleted: bool = False):
        """
        Đồng bộ trạng thái thực tế từ thư mục `projects/` vào `saved_ideas.json`:
        - Kiểm tra nghiêm ngặt đủ 3 Part (`part_a.txt`, `part_b.txt`, `part_c.txt` >= 9.500 chữ/part, tổng >= 35.000 chữ).
        - Nếu dự án mới viết được 1 Part (~15.800 chữ như P16) hoặc 2 Part (~32.600 chữ như P17), tự động hạ `has_script = False`
          và gắn trạng thái `PARTIAL_SCRIPT` (`⚠️ Thiếu Part B, C`) để người dùng bấm chạy viết tiếp ngay phần còn thiếu!
        """
        now_sync = time.time()
        if not force_restore_deleted and (now_sync - getattr(self, "_last_disk_sync_ts", 0.0) < 6.0):
            return
        with self.ideas_io_lock:
            self._last_disk_sync_ts = time.time()
            if force_restore_deleted:
                self._save_deleted_ids(set())
                if hasattr(self, "_proj_dir_mtime_cache"):
                    self._proj_dir_mtime_cache.clear()
            self._register_and_sync_external_projects()
            deleted_ids = self._load_deleted_ids()
            raw_ideas = self.load_saved_ideas()
            changed = False

            ideas: List[Dict[str, Any]] = []
            for it in raw_ideas:
                mid_chk = str(it.get("ma_id", "")).strip()
                if not mid_chk:
                    changed = True
                    continue
                if not force_restore_deleted and mid_chk in deleted_ids:
                    changed = True
                    continue
                # Bất kỳ mã nào mà thư mục `projects/{ma_id}` đã bị người dùng xóa khỏi ổ cứng -> loại bỏ ngay 100%!
                if not (self.projects_dir / mid_chk).exists():
                    deleted_ids.add(mid_chk)
                    changed = True
                    continue
                ideas.append(it)
            if changed:
                self._save_deleted_ids(deleted_ids)

            existing_ids = {str(it.get("ma_id", "")).strip() for it in ideas if it.get("ma_id")}

            # Bước 1: Quét thư mục con trong projects/ để tự động khôi phục các kịch bản bị mất hoặc mới copy từ máy khác sang
            if self.projects_dir.exists():
                restored_items: List[Dict[str, Any]] = []
                unblocked_deleted: Set[str] = set()
                for p_dir in sorted(self.projects_dir.iterdir()):
                    if not p_dir.is_dir():
                        continue
                    mid = p_dir.name.strip()
                    if not mid or mid in existing_ids:
                        continue
                    del_marker = p_dir / ".deleted_by_user"
                    has_sc_probe, _, _ = self.has_valid_script_on_disk(mid)
                    # Nếu thư mục mới được copy từ máy khác sang (có kịch bản hoàn chỉnh has_sc_probe == True và không có .deleted_by_user),
                    # tự động gỡ khỏi sổ đen deleted_ids để nhận ngay lập tức!
                    if has_sc_probe and not del_marker.exists() and mid in deleted_ids:
                        unblocked_deleted.add(mid)
                        deleted_ids.discard(mid)
                    elif del_marker.exists() or mid in deleted_ids:
                        if force_restore_deleted:
                            if del_marker.exists():
                                try:
                                    del_marker.unlink()
                                except Exception:
                                    pass
                        else:
                            continue

                    rec = self._reconstruct_idea_from_project_dir(p_dir)
                    if rec:
                        restored_items.append(rec)
                        existing_ids.add(mid)
                        changed = True

                if unblocked_deleted:
                    self._save_deleted_ids(deleted_ids)

                if restored_items:
                    ideas = restored_items + ideas
                    restored_ids_str = ", ".join([x.get("ma_id", "") for x in restored_items])
                    log_info(
                        "SCRIPT",
                        f"🔄 Đã tự động nhận & khôi phục {len(restored_items)} dự án từ ổ cứng vào Kho Dự Án: [{restored_ids_str}]",
                    )

            # Bước 2: Đồng bộ trạng thái Kịch bản (Đủ 3 Part vs Thiếu Part), Thumbnail, SEO & Video MP4 cho từng dự án
            if not hasattr(self, "_proj_dir_mtime_cache"):
                self._proj_dir_mtime_cache: Dict[str, Tuple[int, int]] = {}
            if not hasattr(self, "_mp4_valid_cache"):
                self._mp4_valid_cache: Dict[str, Tuple[int, int, bool, str]] = {}

            vp_running = bool(self.video_pipeline and getattr(self.video_pipeline, "is_running", False))
            vp_active_set = set(getattr(self.video_pipeline, "active_projects", set())) if vp_running else set()
            vp_pending_set = {
                str(j.get("name") or "")
                for j in getattr(self.video_pipeline, "pending_jobs", [])
                if isinstance(j, dict)
            } if vp_running else set()

            for it in ideas:
                mid = it.get("ma_id")
                if not mid:
                    continue
                p_dir = self.projects_dir / mid
                if not p_dir.exists():
                    continue
                curr_st = str(it.get("status") or "")
                is_vp_busy_for_mid = (mid in vp_active_set) or (mid in vp_pending_set)

                try:
                    r_dir = p_dir / "renders"
                    dir_sig = (
                        p_dir.stat().st_mtime_ns,
                        r_dir.stat().st_mtime_ns if r_dir.exists() else 0,
                    )
                except Exception:
                    dir_sig = (0, 0)
                if (
                    not force_restore_deleted
                    and dir_sig != (0, 0)
                    and self._proj_dir_mtime_cache.get(mid) == dir_sig
                    and curr_st not in ("RUNNING", "VIDEO_RENDERING", "VIDEO_QUEUED", "COMPLETED_VIDEO")
                    and not (it.get("has_video_mp4") and mid not in self._mp4_valid_cache)
                ):
                    continue
                if (
                    not force_restore_deleted
                    and dir_sig != (0, 0)
                    and self._proj_dir_mtime_cache.get(mid) == dir_sig
                    and curr_st == "COMPLETED_VIDEO"
                    and it.get("has_video_mp4")
                    and mid in self._mp4_valid_cache
                ):
                    continue

                has_sc, _, sc_chars = self.has_valid_script_on_disk(mid)
                has_thumb, has_seo, thumb_p = self.has_thumbnail_and_seo_on_disk(mid)
                prog = self.get_script_parts_progress(mid)
                done_cnt = 3 if has_sc else len(prog["done_parts"])
                missing_list = [] if has_sc else prog["missing_parts"]
                effective_chars = sc_chars if has_sc else prog["partial_chars"]

                has_mp4, mp4_file, mp4_reason = self.has_valid_video_mp4_on_disk(
                    mid, sc_chars=effective_chars, auto_delete_corrupted=True
                )
                if dir_sig != (0, 0):
                    self._proj_dir_mtime_cache[mid] = dir_sig

                item_changed = False
                if it.get("has_script") != has_sc:
                    it["has_script"] = has_sc
                    changed = True
                    item_changed = True
                if it.get("has_thumbnail") != has_thumb:
                    it["has_thumbnail"] = has_thumb
                    changed = True
                    item_changed = True
                if it.get("has_seo") != has_seo:
                    it["has_seo"] = has_seo
                    changed = True
                    item_changed = True
                if thumb_p and it.get("thumbnail_path") != thumb_p:
                    it["thumbnail_path"] = thumb_p
                    changed = True
                    item_changed = True
                if it.get("completed_parts_count") != done_cnt:
                    it["completed_parts_count"] = done_cnt
                    changed = True
                    item_changed = True
                if it.get("missing_parts") != missing_list:
                    it["missing_parts"] = missing_list
                    changed = True
                    item_changed = True
                if it.get("has_video_mp4") != has_mp4:
                    it["has_video_mp4"] = has_mp4
                    changed = True
                    item_changed = True
                if has_mp4 and mp4_file:
                    it["video_mp4_path"] = str(mp4_file)
                elif not has_mp4 and it.get("video_mp4_path"):
                    it["video_mp4_path"] = ""
                    changed = True
                    item_changed = True

                if it.get("pure_char_count") != effective_chars:
                    it["pure_char_count"] = effective_chars
                    changed = True
                    item_changed = True

                step2_f = p_dir / "step2_title_thumbnail.txt"
                if not it.get("locked_title") and step2_f.exists():
                    try:
                        s2_txt = step2_f.read_text(encoding="utf-8")
                        lt = extract_locked_title_from_step2(s2_txt, fallback_title=it.get("draft_title_ja", ""))
                        if lt:
                            it["locked_title"] = lt
                            changed = True
                            item_changed = True
                    except Exception:
                        pass

                curr_st = str(it.get("status") or "")
                if has_mp4:
                    if curr_st != "COMPLETED_VIDEO":
                        it["status"] = "COMPLETED_VIDEO"
                        it["current_step"] = f"✅ Đã xuất Video MP4 ({effective_chars:,} chữ)"
                        changed = True
                        item_changed = True
                elif has_sc and not has_mp4:
                    if not is_vp_busy_for_mid:
                        ckpt_step_msg = ""
                        if (p_dir / "renders" / f"_{mid}_master_resume_cache").exists():
                            try:
                                from backend.renderer import get_saved_render_progress
                                ckpt_d = get_saved_render_progress(str(p_dir / "renders" / f"{mid}_master.mp4"))
                                if ckpt_d.get("has_checkpoint"):
                                    ckpt_step_msg = (
                                        f"⏸️ Đã lưu Checkpoint Render {ckpt_d['percent']}% "
                                        f"({ckpt_d['completed_sec']:.0f}s/{ckpt_d['total_dur']:.0f}s) — Bấm Render để chạy tiếp đoạn còn lại!"
                                    )
                            except Exception:
                                ckpt_step_msg = ""

                        if ckpt_step_msg:
                            if curr_st != "ERROR_VIDEO" or it.get("current_step") != ckpt_step_msg:
                                it["status"] = "ERROR_VIDEO"
                                it["current_step"] = ckpt_step_msg
                                changed = True
                                item_changed = True
                        elif mp4_reason not in ("missing", "rendering_in_progress", "ok"):
                            err_step = f"❌ Video bị ngắt/lỗi ({mp4_reason}) — Chờ Render lại ({effective_chars:,} chữ)"
                            if curr_st != "ERROR_VIDEO" or it.get("current_step") != err_step:
                                it["status"] = "ERROR_VIDEO"
                                it["current_step"] = err_step
                                changed = True
                                item_changed = True
                        elif curr_st == "COMPLETED_VIDEO":
                            err_step = f"⚠️ Video MP4 chưa hoàn thành hoặc bị ngắt — Chờ Render lại ({effective_chars:,} chữ)"
                            it["status"] = "ERROR_VIDEO"
                            it["current_step"] = err_step
                            changed = True
                            item_changed = True
                        elif curr_st == "VIDEO_RENDERING":
                            err_step = f"⚠️ Render Video bị ngắt giữa chừng — Chờ Render lại ({effective_chars:,} chữ)"
                            it["status"] = "ERROR_VIDEO"
                            it["current_step"] = err_step
                            changed = True
                            item_changed = True
                        elif curr_st in ("", "SAVED_READY", "CHƯA_CHẠY_STEP2", "ERROR", "RUNNING", "PARTIAL_SCRIPT", "COMPLETED_HANDOFF", "VIDEO_QUEUED"):
                            it["status"] = "SCRIPT_DONE"
                            it["current_step"] = f"📝 Đã xong Kịch bản ({effective_chars:,} chữ) — Sẵn sàng Render MP4"
                            changed = True
                            item_changed = True
                elif not has_sc and not has_mp4 and done_cnt > 0:
                    # Dự án mới viết được 1 hoặc 2 Part (VD: P16 = 15,848 chữ, P17 = 32,684 chữ) -> Đánh dấu thiếu Part để viết tiếp!
                    miss_str = ", ".join(missing_list)
                    expected_step = f"⚠️ Thiếu Part {miss_str} (Mới xong {done_cnt}/3 Part: {effective_chars:,} chữ)"
                    if (curr_st != "RUNNING" or not self.is_running) and (curr_st != "PARTIAL_SCRIPT" or it.get("current_step") != expected_step):
                        it["status"] = "PARTIAL_SCRIPT"
                        it["current_step"] = expected_step
                        changed = True
                        item_changed = True
                elif not has_sc and not has_mp4 and done_cnt == 0 and not self.is_running:
                    # Tự động dọn trạng thái RUNNING / ERROR bị treo từ phiên cũ khi máy đang ở trạng thái nghỉ (Idle)
                    step3_f = p_dir / "step3_architecture.txt"
                    has_s3 = step3_f.exists() and step3_f.stat().st_size > 2500
                    has_s2 = step2_f.exists() and step2_f.stat().st_size > 2500
                    if curr_st in ("RUNNING", "ERROR"):
                        it["status"] = "SAVED_READY"
                        if has_s3:
                            it["current_step"] = "♻️ Đã xong Step 2 & Step 3 — Bấm Chạy để viết tiếp Step 4 (Part A/B/C)"
                        elif has_s2:
                            it["current_step"] = "♻️ Đã xong Step 2 — Bấm Chạy để viết tiếp Step 3"
                        else:
                            it["current_step"] = "CHƯA CHẠY (Sẵn sàng từ Step 2)"
                        changed = True
                        item_changed = True

                if item_changed:
                    info_f = p_dir / "idea_info.json"
                    if info_f.exists():
                        try:
                            info_f.write_text(json.dumps(it, ensure_ascii=False, indent=2), encoding="utf-8")
                        except Exception:
                            pass

            if changed:
                self.save_ideas_list(ideas)

    def restore_scripts_from_disk(self, custom_folder: Optional[str] = None) -> Dict[str, Any]:
        """Quét lại toàn bộ thư mục `projects/` (hoặc thư mục tùy chỉnh) để cập nhật chính xác 100% các folder hiện có (thêm folder mới, xóa bỏ hoàn toàn các folder đã bị xóa)."""
        if custom_folder and str(custom_folder).strip():
            cand_dir = Path(str(custom_folder).strip())
            if cand_dir.exists() and cand_dir.is_dir() and cand_dir.resolve() != self.projects_dir.resolve():
                try:
                    self.import_external_projects_folder(str(cand_dir))
                except Exception:
                    pass
        with self.ideas_io_lock:
            raw_before = []
            if self.ideas_file.exists():
                try:
                    d = json.loads(self.ideas_file.read_text(encoding="utf-8"))
                    if isinstance(d, list):
                        raw_before = d
                except Exception:
                    pass
            before_cnt = len(raw_before)
            self._last_disk_sync_ts = 0.0
            if hasattr(self, "_proj_dir_mtime_cache"):
                self._proj_dir_mtime_cache.clear()
            self._sync_projects_disk_state(force_restore_deleted=True)
            after_list = self.load_saved_ideas()
            script_cnt = sum(1 for x in after_list if x.get("has_script"))
            mp4_cnt = sum(1 for x in after_list if x.get("has_video_mp4"))
            removed_cnt = max(0, before_cnt - len(after_list))
            added_cnt = max(0, len(after_list) - before_cnt)
        log_info(
            "SCRIPT",
            f"🔄 Đã cập nhật lại thư mục [{self.projects_dir}]: Hiện có {len(after_list)} dự án ({script_cnt} kịch bản đã xong, {mp4_cnt} video MP4, +{added_cnt} mới, -{removed_cnt} đã xóa).",
        )
        return {
            "restored_count": added_cnt,
            "removed_count": removed_cnt,
            "total_count": len(after_list),
            "script_done_count": script_cnt,
            "video_done_count": mp4_cnt,
            "projects_dir": str(self.projects_dir),
            "ideas": after_list,
        }

    def check_and_repair_all_projects(self) -> Dict[str, Any]:
        """
        Nút "🛡️ Check Toàn Bộ":
        1. Quét toàn bộ thư mục `projects/` để kiểm tra lại hết tất cả các kịch bản đã tạo -> nếu dính `[LOCKED_TITLE]` / Metadata thì xóa & sửa lại ngay.
        2. Nếu dự án đã tạo Video MP4 / Voice -> tự động cắt bỏ trực tiếp các đoạn giây đọc `[LOCKED_TITLE]` khỏi file `.mp4`, `master_voice.wav` và `subtitles.srt` (Phương án 1).
        3. Đồng bộ lại danh sách Kho Dự Án và trả về kết quả chi tiết.
        """
        from .voice_service import check_and_repair_all_projects_sync

        self._emit(
            status="running",
            current_step="🛡️ Đang Check Toàn Bộ Kịch Bản & Video MP4...",
            progress=2.0,
            message=f"🛡️ Đang quét toàn bộ thư mục [{self.projects_dir}] để dọn sạch [LOCKED_TITLE] trong Kịch bản & Video MP4...",
        )
        log_info("SCRIPT", f"🛡️ Bắt đầu chạy Check Toàn Bộ Kịch Bản & Video tại [{self.projects_dir}]...")

        def _prog_cb(pct: float, msg: str):
            self._emit(
                status="running",
                current_step="🛡️ Check Toàn Bộ (Dọn Kịch Bản & Video Lỗi)",
                progress=pct,
                message=msg,
            )

        summary = check_and_repair_all_projects_sync(self.projects_dir, progress_cb=_prog_cb)
        if hasattr(self, "_proj_dir_mtime_cache"):
            self._proj_dir_mtime_cache.clear()
        if hasattr(self, "_mp4_valid_cache"):
            self._mp4_valid_cache.clear()
        self._last_disk_sync_ts = 0.0
        self._sync_projects_disk_state(force_restore_deleted=False)
        ideas_after = self.load_saved_ideas()

        done_msg = (
            f"✅ Check Toàn Bộ hoàn tất ({summary['total_scanned']} dự án): "
            f"Đã sửa sạch {summary['scripts_repaired_count']} Kịch bản, "
            f"cắt bỏ đoạn lỗi trong {summary['videos_repaired_count']} Video MP4 "
            f"(Tổng {summary['total_lines_removed']} dòng/khung [LOCKED_TITLE] đã xóa)!"
        )
        self._emit(
            status="idle" if not self.is_running else "running",
            current_step="✅ Đã hoàn tất Check Toàn Bộ!",
            progress=100.0,
            message=done_msg,
        )
        log_info("SCRIPT", done_msg)
        return {
            **summary,
            "ideas": ideas_after,
            "message": done_msg,
        }

    def import_external_projects_folder(self, source_dir: str) -> Dict[str, Any]:
        """
        Nhập (Import) hàng loạt Kịch bản + Thumbnail + SEO được tạo từ MÁY KHÁC vào Kho Dự Án của máy hiện tại.
        Hỗ trợ linh hoạt cả 3 cấu trúc khi người dùng copy qua USB / LAN / Zalo:
        1. Chọn thư mục `projects/` (hoặc thư mục tổng chứa nhiều thư mục con `P01`, `P02`, `IDEA_001`...).
        2. Chọn trực tiếp 1 thư mục dự án đơn lẻ (ví dụ `D:\\CopyTuMayKhac\\P05` chứa `script_clean.txt` / `P05_KICH_BAN.txt` + `P05_THUMBNAIL_1.png` + `P05_SEO.txt`).
        3. Chọn 1 thư mục chứa các file rời (`P01_KICH_BAN.txt`, `P01_SEO.txt`, `P01_THUMBNAIL_1.png`, `P02.txt`, `P02.png`...).
        """
        src_path = Path(source_dir).resolve()
        if not src_path.exists() or not src_path.is_dir():
            raise ValueError(f"Thư mục nguồn không tồn tại: {source_dir}")

        imported_ids: List[str] = []
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        def _copy_project_dir(s_dir: Path, mid: str):
            clean_mid = re.sub(r'[\\/:*?"<>|]+', "_", mid.strip())
            if not clean_mid:
                return
            dst_dir = self.projects_dir / clean_mid
            dst_dir.mkdir(parents=True, exist_ok=True)
            if s_dir.resolve() != dst_dir.resolve():
                for item in s_dir.rglob("*"):
                    if item.is_file() and item.name != ".deleted_by_user":
                        rel = item.relative_to(s_dir)
                        target_f = dst_dir / rel
                        target_f.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.copy2(item, target_f)
                        except Exception:
                            pass
            del_m = dst_dir / ".deleted_by_user"
            if del_m.exists():
                try:
                    del_m.unlink()
                except Exception:
                    pass
            has_sc, _, _ = self.has_valid_script_on_disk(clean_mid)
            self.has_thumbnail_and_seo_on_disk(clean_mid)
            prog = self.get_script_parts_progress(clean_mid)
            if has_sc or len(prog["done_parts"]) > 0:
                if clean_mid not in imported_ids:
                    imported_ids.append(clean_mid)

        # Kiểm tra xem bản thân src_path có phải là 1 thư mục dự án đơn lẻ không
        direct_markers = (
            src_path / "script_clean.txt",
            src_path / "part_a.txt",
            src_path / "00_TIEU_DE_VA_SEO_YOUTUBE.txt",
            src_path / "idea_info.json",
            src_path / f"{src_path.name}_KICH_BAN.txt",
        )
        if any(m.exists() for m in direct_markers):
            _copy_project_dir(src_path, src_path.name)
        else:
            # 1. Quét các thư mục con (VD: P01, P02... hoặc projects/P01, P02...)
            sub_dirs = [d for d in sorted(src_path.iterdir()) if d.is_dir()]
            if len(sub_dirs) == 1 and sub_dirs[0].name.lower() == "projects":
                sub_dirs = [d for d in sorted(sub_dirs[0].iterdir()) if d.is_dir()]

            for sd in sub_dirs:
                if sd.name.startswith(".") or sd.name.lower() in ("__pycache__", "stook", "bin", "backend", "frontend", "app"):
                    continue
                _copy_project_dir(sd, sd.name)

            # 2. Quét các file rời đặt chung trong 1 thư mục (VD: P01_KICH_BAN.txt, P01_SEO.txt, P01_THUMBNAIL_1.png)
            loose_groups: Dict[str, List[Path]] = {}
            for f in sorted(src_path.iterdir()):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in (".txt", ".png", ".jpg", ".jpeg", ".webp", ".mp4"):
                    continue
                stem = f.stem
                m_id = re.match(r"^([A-Za-z0-9]+(?:_[0-9]+)?)_(?:KICH_BAN|SEO|THUMBNAIL|MASTER|SCRIPT)", stem, flags=re.IGNORECASE)
                if m_id:
                    gid = m_id.group(1).upper()
                else:
                    gid = re.sub(r"_(?:KICH_BAN|SEO|THUMBNAIL.*)$", "", stem, flags=re.IGNORECASE).strip()
                if gid:
                    loose_groups.setdefault(gid, []).append(f)

            for gid, files_list in loose_groups.items():
                dst_dir = self.projects_dir / gid
                renders_dir = dst_dir / "renders"
                for lf in files_list:
                    up_n = lf.name.upper()
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    renders_dir.mkdir(parents=True, exist_ok=True)
                    if lf.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                        shutil.copy2(lf, renders_dir / f"{gid}_THUMBNAIL_1.png")
                    elif "SEO" in up_n or "TIEU_DE" in up_n:
                        shutil.copy2(lf, dst_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt")
                        shutil.copy2(lf, renders_dir / f"{gid}_SEO.txt")
                    elif lf.suffix.lower() == ".txt":
                        txt_c = lf.read_text(encoding="utf-8", errors="ignore")
                        if pure_char_count(txt_c) >= 9500:
                            shutil.copy2(lf, dst_dir / "script_clean.txt")
                            shutil.copy2(lf, renders_dir / f"{gid}_KICH_BAN.txt")
                has_sc, _, _ = self.has_valid_script_on_disk(gid)
                self.has_thumbnail_and_seo_on_disk(gid)
                if has_sc and gid not in imported_ids:
                    imported_ids.append(gid)

        if imported_ids:
            self._unmark_ids_deleted(imported_ids)
        self._sync_projects_disk_state(force_restore_deleted=False)
        ideas_after = self.load_saved_ideas()
        log_info(
            "SCRIPT",
            f"📥 Đã nhập thành công {len(imported_ids)} dự án (Kịch bản + Thumbnail + SEO) từ [{source_dir}]: {imported_ids}",
        )
        return {
            "imported_count": len(imported_ids),
            "imported_ids": imported_ids,
            "total_count": len(ideas_after),
            "ideas": ideas_after,
        }

    def _ensure_default_idea_seeded(self):
        """Khởi tạo sẵn mẫu đầu vào của người dùng nếu danh sách đang trống."""
        ideas = self.load_saved_ideas()
        if not ideas:
            sample_raw = (
                "P01 — 義母の介護を10年続けた私に夫は「もう用済みだ」と離婚届を渡した。翌朝、義母が残した古い介護日誌を開くと、知らなかった約束が…\n"
                "VI: Chăm mẹ chồng 10 năm, bị chồng đuổi; cuốn nhật ký chăm sóc tiết lộ lời hứa\n"
                "Keyword: 義母, 介護, 離婚, 感動する話 (vidIQ NOT_VERIFIED)\n"
                "Evidence: 介護日誌 / nhật ký chăm sóc\n"
                "Reveal: Lời hứa không phải để thừa kế mà để bảo vệ người bị bỏ rơi\n"
                "Capacity: PASS"
            )
            parsed = parse_idea_input_block(sample_raw, custom_id="P01")
            self.save_ideas_list([parsed])

    def add_or_update_ideas_bulk_from_raw(self, raw_text: str, custom_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Phân tích 1 hoặc NHIỀU (SLL) bộ tiêu đề cố định (P01..P20) / khối ý tưởng người dùng dán cùng lúc
        và lưu toàn bộ vào danh sách kho dự án theo đúng thứ tự.
        """
        blocks = split_raw_text_into_idea_blocks(raw_text)
        if not blocks:
            blocks = [raw_text]

        ideas = self.load_saved_ideas()
        existing_ids = {it.get("ma_id") for it in ideas if it.get("ma_id")}
        saved_items: List[Dict[str, Any]] = []
        new_items_to_prepend: List[Dict[str, Any]] = []

        # Tìm số thứ tự tiếp theo an toàn cho IDEA_xxx
        next_num = len(ideas) + 1
        base_prefix = (custom_id or "").strip()

        for idx, block_str in enumerate(blocks):
            if len(blocks) == 1 and base_prefix:
                assigned_id = base_prefix
            elif len(blocks) > 1 and base_prefix:
                assigned_id = f"{base_prefix}_{idx + 1:02d}"
            else:
                # Nếu trong block đã có mã P01..P20 hoặc Mã:/ID: thì ưu tiên dùng đúng mã đó
                temp_parsed = parse_idea_input_block(block_str, custom_id=None)
                inline_id = temp_parsed.get("ma_id", "")
                if inline_id and not inline_id.startswith("DRAMA_"):
                    assigned_id = inline_id
                else:
                    while f"IDEA_{next_num:03d}" in existing_ids:
                        next_num += 1
                    assigned_id = f"IDEA_{next_num:03d}"
                    next_num += 1

            parsed = parse_idea_input_block(block_str, custom_id=assigned_id)
            mid_cur = parsed["ma_id"]
            existing_ids.add(mid_cur)

            # Bảo toàn tiến độ nếu mã này đã có sẵn kịch bản / thumbnail / SEO trên ổ cứng
            has_sc_disk, _, sc_chars_disk = self.has_valid_script_on_disk(mid_cur)
            has_th_disk, has_seo_disk, th_path_disk = self.has_thumbnail_and_seo_on_disk(mid_cur)
            if has_sc_disk:
                parsed["has_script"] = True
                parsed["pure_char_count"] = sc_chars_disk
                parsed["completed_parts_count"] = 3
                parsed["missing_parts"] = []
                parsed["has_thumbnail"] = has_th_disk
                parsed["has_seo"] = has_seo_disk
                if th_path_disk:
                    parsed["thumbnail_path"] = th_path_disk
                parsed["status"] = "SCRIPT_DONE"
                parsed["current_step"] = f"📝 Đã xong Kịch bản ({sc_chars_disk:,} chữ) & {1 if has_th_disk else 0}/1 Thumbnail — Sẵn sàng Render MP4"

            replaced = False
            for i, it in enumerate(ideas):
                if it.get("ma_id") == mid_cur:
                    if it.get("locked_title") and has_sc_disk:
                        parsed["locked_title"] = it["locked_title"]
                    ideas[i] = parsed
                    replaced = True
                    break
            if not replaced:
                new_items_to_prepend.append(parsed)

            proj_dir = self.projects_dir / mid_cur
            proj_dir.mkdir(parents=True, exist_ok=True)
            del_marker = proj_dir / ".deleted_by_user"
            if del_marker.exists():
                try:
                    del_marker.unlink()
                except Exception:
                    pass
            (proj_dir / "idea_info.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
            (proj_dir / "step2_prompt_ready.txt").write_text(
                build_step2_prompt_from_idea(parsed, self.get_step2_template()),
                encoding="utf-8",
            )
            saved_items.append(parsed)

        if saved_items:
            self._unmark_ids_deleted([it.get("ma_id", "") for it in saved_items])

        if new_items_to_prepend:
            ideas = new_items_to_prepend + ideas

        self.save_ideas_list(ideas)
        self._last_disk_sync_ts = 0.0
        self._sync_projects_disk_state()
        ids_str = ", ".join([it.get("ma_id", "") for it in saved_items])
        log_info("SCRIPT", f"📥 Đã phân tích và lưu {len(saved_items)} bộ tiêu đề vào Kho Dự Án: [{ids_str}]")
        return saved_items

    def add_or_update_idea_from_raw(self, raw_text: str, custom_id: Optional[str] = None) -> Dict[str, Any]:
        """Phân tích khối văn bản người dùng dán vào và lưu vào danh sách."""
        items = self.add_or_update_ideas_bulk_from_raw(raw_text, custom_id=custom_id)
        return items[0] if items else parse_idea_input_block(raw_text, custom_id=custom_id)

    def delete_idea(self, ma_id: str) -> List[Dict[str, Any]]:
        target = (ma_id or "").strip()
        with self.ideas_io_lock:
            self._mark_ids_deleted([target])
            before_list = self.load_saved_ideas()
            ideas = [it for it in before_list if str(it.get("ma_id", "")).strip() != target]
            self.save_ideas_list(ideas)
            # Cập nhật đồng bộ bản backup và file phụ trong app/saved_ideas.json
            for extra_fp in (
                self.root_dir / "app" / "saved_ideas.json",
                self._get_persistent_appdata_dir() / "saved_ideas_backup.json",
            ):
                if extra_fp.exists():
                    try:
                        extra_fp.write_text(json.dumps(ideas, ensure_ascii=False, indent=2), encoding="utf-8")
                    except Exception:
                        pass

            p_dir = self.projects_dir / target
            if p_dir.exists() and p_dir.is_dir():
                has_sc, _, _ = self.has_valid_script_on_disk(target)
                mp4_f = p_dir / "renders" / f"{target}_master.mp4"
                has_mp4 = mp4_f.exists() and mp4_f.stat().st_size > 1_000_000
                if not has_sc and not has_mp4:
                    # Dự án chỉ là tiêu đề nháp chưa có kịch bản -> xóa sạch hoàn toàn thư mục để không bao giờ tồn đọng
                    shutil.rmtree(p_dir, ignore_errors=True)
                else:
                    for fname in ("idea_info.json", "step2_prompt_ready.txt"):
                        fpath = p_dir / fname
                        if fpath.exists():
                            try:
                                fpath.unlink()
                            except Exception:
                                pass
                    try:
                        (p_dir / ".deleted_by_user").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
                    except Exception:
                        pass
        log_info("SCRIPT", f"🗑️ Đã xóa vĩnh viễn mã [{target}] khỏi Kho Dự Án (Còn lại {len(ideas)} mã).", project_id=target)
        return ideas

    def delete_all_ideas(self) -> List[Dict[str, Any]]:
        with self.ideas_io_lock:
            old_ideas = self.load_saved_ideas()
            count = len(old_ideas)
            all_ids = [str(it.get("ma_id", "")).strip() for it in old_ideas if it.get("ma_id")]
            if self.projects_dir.exists():
                for p_dir in self.projects_dir.iterdir():
                    if p_dir.is_dir():
                        all_ids.append(p_dir.name.strip())
            self._mark_ids_deleted(all_ids)
            self.save_ideas_list([])
            for extra_fp in (
                self.root_dir / "app" / "saved_ideas.json",
                self._get_persistent_appdata_dir() / "saved_ideas_backup.json",
            ):
                if extra_fp.exists():
                    try:
                        extra_fp.write_text("[]", encoding="utf-8")
                    except Exception:
                        pass
            if self.projects_dir.exists():
                for p_dir in self.projects_dir.iterdir():
                    if p_dir.is_dir():
                        mid = p_dir.name.strip()
                        has_sc, _, _ = self.has_valid_script_on_disk(mid)
                        mp4_f = p_dir / "renders" / f"{mid}_master.mp4"
                        has_mp4 = mp4_f.exists() and mp4_f.stat().st_size > 1_000_000
                        if not has_sc and not has_mp4:
                            shutil.rmtree(p_dir, ignore_errors=True)
                        else:
                            for fname in ("idea_info.json", "step2_prompt_ready.txt"):
                                fp = p_dir / fname
                                if fp.exists():
                                    try:
                                        fp.unlink()
                                    except Exception:
                                        pass
                            try:
                                (p_dir / ".deleted_by_user").write_text(
                                    time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8"
                                )
                            except Exception:
                                pass
        log_info("SCRIPT", f"🗑️ Đã xóa toàn bộ {count} mã tiêu đề khỏi Kho Dự Án.")
        return []

    def _update_idea_record(self, ma_id: str, **fields):
        with self.ideas_io_lock:
            ideas = self.load_saved_ideas()
            for it in ideas:
                if it.get("ma_id") == ma_id:
                    for k, v in fields.items():
                        it[k] = v
                    it["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    proj_dir = self.projects_dir / ma_id
                    proj_dir.mkdir(parents=True, exist_ok=True)
                    (proj_dir / "idea_info.json").write_text(json.dumps(it, ensure_ascii=False, indent=2), encoding="utf-8")
                    break
            self.save_ideas_list(ideas)

    def _build_fallback_seo_pack(
        self,
        ma_id: str,
        locked_title: str,
        total_pure: int,
        idea: Dict[str, Any],
        step2_out: str,
    ) -> str:
        """
        Tạo gói SEO & Thumbnail 6 dòng chuẩn từ dữ liệu Step 2 + Idea khi chạy ở chế độ
        bỏ qua Chrome (đã có sẵn kịch bản) hoặc khi ChatGPT Step 6 bị quá thời gian chờ.
        """
        kw_raw = idea.get("keywords_ja") or "感動する話, 家族の秘密, 泣ける話, 朗読, シニア"
        summary_vi = idea.get("summary_vi") or ""
        evidence = idea.get("proof_object") or ""
        return (
            f"ID: {ma_id}\n"
            f"COMPLETED_STEP: STEP 6 (AUTO-SYNTHESIZED FROM LOCKED STEP 2)\n"
            f"FINAL_LOCKED_TITLE:\n{locked_title}\n\n"
            f"YOUTUBE_DESCRIPTION_JA:\n"
            f"{locked_title}\n\n"
            f"長い年月の中で語られなかった家族の記憶と、静かに残された一つの証（{evidence}）。\n"
            f"すれ違いの果てに見えてきた本当の想いを、丁寧な朗読でお届けします。\n"
            f"ぜひ最後までごゆっくりお聴きください。\n\n"
            f"▼チャンネル登録・高評価をいただけますと励みになります。\n"
            f"#感動する話 #泣ける話 #家族の物語 #朗読 #シニアライフ #人生ドラマ\n\n"
            f"YOUTUBE_TAGS_JA:\n"
            f"{kw_raw}, 感動する話, 泣ける話, 家族の秘密, 朗読, スカッとする話, 老後の人生, 家族ドラマ\n\n"
            f"VIETNAMESE_SUMMARY:\n{summary_vi}\n\n"
            f"PURE_CHARACTER_COUNT: {total_pure:,} ký tự thuần (~{round(total_pure / 353)} phút)\n"
        )

    # ==========================================================================
    # ĐỌC NGUYÊN VĂN SKILL.MD TỪ THƯ MỤC ADAS_SKILLS & TẠO PROMPT STEP 3..6
    # ==========================================================================
    def _load_skill_markdown(self, skill_folder: str) -> str:
        """Đọc nguyên văn 100% nội dung file SKILL.md của Agent tương ứng."""
        cand_paths = [
            self.root_dir / "adas_skills" / skill_folder / "SKILL.md",
            self.root_dir / "app" / "adas_skills" / skill_folder / "SKILL.md",
        ]
        for p in cand_paths:
            if p.exists():
                try:
                    return p.read_text(encoding="utf-8-sig").strip()
                except Exception:
                    pass
        return ""

    def _build_step3_prompt(self, ma_id: str, locked_title: str, step2_context: str = "") -> str:
        skill_md = self._load_skill_markdown("03_story_architecture_logic")
        skill_block = f"\n\n========== HƯỚNG DẪN CHUYÊN SÂU SKILL 03 (STORY ARCHITECTURE & LOGIC) ==========\n{skill_md}\n================================================================================" if skill_md else ""
        ctx_block = f"\n\n========== DỮ LIỆU ĐẦU RA & STEP3_HANDOFF TỪ STEP 2 ==========\n{step2_context[-8000:]}\n==============================================================" if step2_context else ""
        return f"""Chạy STEP 3 — STORY ARCHITECTURE & LOGIC PREFLIGHT (THREE-PART CONTRACT) cho mã {ma_id} theo toàn bộ dữ liệu STEP3_HANDOFF từ STEP 2.
GIỮ NGUYÊN TUYỆT ĐỐI LOCKED_TITLE: 「{locked_title}」{ctx_block}{skill_block}

YÊU CẦU THỰC THI NGAY CHO MÃ {ma_id}:
1. HARD FINAL LENGTH CONTRACT: Thiết kế đủ chất liệu nhân-quả thật để STEP 4 viết thành 3 phần độc lập:
   - PART A (Foundation / Hook / First Pursuit): 13.334–16.000 ký tự thuần (Target an toàn: 14.200–15.200).
   - PART B (Investigation / Contradiction / Midpoint / Escalation): 13.334–17.000 ký tự thuần (Target an toàn: 14.800–15.800).
   - PART C (Final Escalation / Reveal 3 / Payoff / Consequence / Callback): 13.334–17.000 ký tự thuần (Target an toàn: 15.000–16.000).
   - TỔNG: 40.001–50.000 PURE_CHARACTER_COUNT (Target: 44.000–47.000).
2. Xuất đầy đủ STORY BIBLE, LOGIC LEDGER, SCENE CAPACITY PLAN (20–24 scenes chia rõ PART_A_SCENE_PLAN, PART_B_SCENE_PLAN, PART_C_SCENE_PLAN) và 3 Handoff Specs (PART_A_HANDOFF, PART_B_HANDOFF, PART_C_HANDOFF), chốt `APPROVED_FOR_DRAFTING: YES`. Không viết văn bản kịch bản ở bước này."""

    def _extract_compact_step3_for_part(self, step3_context: str, part_letter: str) -> str:
        """
        Rút gọn thông minh ngữ cảnh STEP 3 nếu quá dài (> 26.000 ký tự, ví dụ Gemini 4 Pro xuất 53.000 ký tự):
        Giữ nguyên phần STORY BIBLE + LOGIC LEDGER ở đầu và toàn bộ kế hoạch cảnh của `PART_{part_letter}` + `HANDOFF`
        để lệnh STEP 4 luôn gọn nhẹ, nạp siêu tốc và AI tập trung 100% vào đúng Part đang viết.
        """
        if not step3_context or len(step3_context) <= 26000:
            return step3_context
        head_bible = step3_context[:11500]
        p_up = part_letter.upper()
        m_part = re.search(
            rf"(?:PHẦN\s*[123]\s*[:：\-]?\s*)?PART[_\s]*{p_up}[_\s]*SCENE[_\s]*PLAN",
            step3_context,
            flags=re.IGNORECASE,
        )
        if m_part:
            start_idx = max(0, m_part.start() - 120)
            part_slice = step3_context[start_idx : start_idx + 14500]
            handoff_tail = step3_context[-4500:] if (start_idx + 14500) < len(step3_context) - 4500 else ""
            return f"{head_bible}\n\n...[TRÍCH XUẤT TRỌNG TÂM KẾ HOẠCH PART {p_up}]...\n\n{part_slice}\n\n{handoff_tail}".strip()
        return f"{head_bible}\n\n...\n\n{step3_context[-14500:]}".strip()

    def _build_step4_part_initial_prompt(
        self,
        ma_id: str,
        part_letter: str,
        locked_title: str,
        min_c: int,
        max_c: int,
        target_c: int,
        step3_context: str = "",
        prev_part_tail: str = "",
    ) -> str:
        skill_md = self._load_skill_markdown("04_longform_script_writer")
        compact_s3 = self._extract_compact_step3_for_part(step3_context, part_letter)
        skill_block = f"\n\n========== HƯỚNG DẪN CHUYÊN SÂU SKILL 04 (LONGFORM SCRIPT WRITER) ==========\n{skill_md}\n============================================================================" if (skill_md and compact_s3) else ""
        ctx_block = f"\n\n========== STORY BIBLE & KẾ HOẠCH CẢNH TỪ STEP 3 ==========\n{compact_s3}\n===========================================================" if compact_s3 else ""
        prev_block = (
            f"\n\n========== ĐOẠN KẾT CỦA PART TRƯỚC (ĐỂ NỐI MẠCH TRUYỆN LIỀN MẠCH 100%, TUYỆT ĐỐI KHÔNG LẶP LẠI) ==========\n"
            f"「...{prev_part_tail[-400:]}」\n"
            f"=========================================================================================================="
            if prev_part_tail
            else ""
        )
        return f"""CHẠY NGAY STEP 4 — BUILD PART {part_letter} CHO MÃ {ma_id}
LOCKED_TITLE: 「{locked_title}」{ctx_block}{prev_block}{skill_block}

QUY TẮC BẮT BUỘC (04_longform_script_writer):
1. CHỈ VIẾT VĂN BẢN TỰ SỰ VÀ LỜI THOẠI TIẾNG NHẬT THUẦN TÚY (Japanese Narration & Dialogue) của PART {part_letter} theo đúng `PART_{part_letter}_SCENE_PLAN` đã duyệt ở STEP 3.
2. ⚠️ CẤM TUYỆT ĐỐI RÒ RỈ TIÊU ĐỀ KHÓA & METADATA: TUYỆT ĐỐI KHÔNG in lại dòng `LOCKED_TITLE: ...`, `SELECTED_TITLE: ...`, `PART {part_letter} — 日本語脚本`, `{ma_id} — STEP 4`, `CONTINUITY:`, `ENDING:` vào đầu hoặc giữa văn bản truyện (để tránh bị đọc nhầm khi tạo Voice TTS và Phụ đề Video). Dòng đầu tiên phải vào thẳng câu chuyện tiếng Nhật!
3. MỤC TIÊU ĐỘ DÀI CỨNG CỦA PART {part_letter}: {min_c:,}–{max_c:,} ký tự thuần (Đích an toàn: ~{target_c:,} ký tự thuần Unicode L+N).
4. Triển khai chi tiết, sâu sắc từng cảnh trong PART_{part_letter}_SCENE_PLAN bằng diễn biến hành động cụ thể, đối thoại giàu cảm xúc đời thực Nhật Bản, chi tiết vật chứng và tâm lý nhân vật. TUYỆT ĐỐI KHÔNG tóm tắt, không nhảy cóc cảnh, không chèn tiêu đề Scene hay ghi chú đạo diễn tiếng Anh/Việt vào giữa văn bản truyện.
5. ⚠️ QUY TẮC TỐC ĐỘ & HIỂN THỊ: TUYỆT ĐỐI KHÔNG bật công cụ Python / Code Interpreter, KHÔNG đóng gói thành file tải về (.txt/.md/.docx). BẮT BUỘC in trực tiếp toàn bộ 100% văn bản kịch bản tiếng Nhật ra khung chat ngay lập tức (hệ thống bên ngoài sẽ tự đếm ký tự thuần). Ở cuối cùng mới ghi khối `PART_{part_letter}_HANDOFF_LEDGER`."""

    def _build_step4_part_continue_prompt(
        self,
        part_letter: str,
        current_pure: int,
        min_c: int,
        max_c: int,
        target_c: int,
        last_tail_ja: str,
        step3_context: str = "",
    ) -> str:
        needed = max(1500, target_c - current_pure)
        ctx_reminder = (
            f"\n\n========== NHẮC LẠI KẾ HOẠCH CẢNH PART {part_letter} (STEP 3) ==========\n"
            f"{step3_context[-12000:]}\n"
            f"========================================================================\n"
            if step3_context
            else ""
        )
        return f"""[KIỂM TRA ĐỘ DÀI CỨNG — PART {part_letter}]
- Số ký tự thuần (PURE_CHARACTER_COUNT) hiện tại của PART {part_letter} mới đạt: {current_pure:,} ký tự thuần.
- Ngưỡng bắt buộc của PART {part_letter}: {min_c:,}–{max_c:,} ký tự thuần (Còn thiếu khoảng {needed:,} ký tự thuần để đạt đích {target_c:,}).{ctx_reminder}
YÊU CẦU VIẾT TIẾP NỐI PART {part_letter}:
1. Hãy viết TIẾP NỐI NGAY LẬP TỨC từ đoạn kết vừa rồi:
   「...{last_tail_ja}」
2. Triển khai tiếp các cảnh còn lại của `PART_{part_letter}_SCENE_PLAN` (hoặc mở rộng chiều sâu nhân-quả, bằng chứng cụ thể, đối thoại xung đột, chi phí quyết định và chuyển biến tâm lý trong phạm vi của PART {part_letter}).
3. TUYỆT ĐỐI KHÔNG bật công cụ Python/Code Interpreter, KHÔNG tạo file tải về, KHÔNG lặp lại những đoạn đã viết ở trên, KHÔNG viết sang Part tiếp theo, KHÔNG chèn tiêu đề chương/cảnh. Chỉ xuất trực tiếp 100% văn bản truyện tiếng Nhật ra khung chat nối tiếp cho đủ thêm tối thiểu {needed:,} ký tự thuần, sau đó xuất `PART_{part_letter}_HANDOFF_LEDGER` ở cuối."""

    def _build_step5_audit_prompt(
        self,
        ma_id: str,
        locked_title: str,
        count_a: int,
        count_b: int,
        count_c: int,
        total_count: int,
        part_a_text: str = "",
        part_b_text: str = "",
        part_c_text: str = "",
        step3_context: str = "",
    ) -> str:
        skill_md = self._load_skill_markdown("05_script_auditor_100")
        skill_block = f"\n\n========== HƯỚNG DẪN CHUYÊN SÂU SKILL 05 (SCRIPT AUDITOR 100) ==========\n{skill_md}\n========================================================================" if skill_md else ""
        arch_excerpt = f"\n\n========== TÓM TẮT STORY BIBLE & LOGIC LEDGER (STEP 3) ==========\n{step3_context[:3500]}\n=================================================================" if step3_context else ""
        script_payload = ""
        if part_a_text or part_b_text or part_c_text:
            script_payload = (
                f"\n\n========== TOÀN BỘ VĂN BẢN KỊCH BẢN CẦN KIỂM TRA & VIẾT LẠI (NẾU LỖI) ==========\n"
                f"--- [BẮT ĐẦU PART A ({count_a:,} pure chars)] ---\n{part_a_text}\n--- [KẾT THÚC PART A] ---\n\n"
                f"--- [BẮT ĐẦU PART B ({count_b:,} pure chars)] ---\n{part_b_text}\n--- [KẾT THÚC PART B] ---\n\n"
                f"--- [BẮT ĐẦU PART C ({count_c:,} pure chars)] ---\n{part_c_text}\n--- [KẾT THÚC PART C] ---\n"
                f"================================================================================"
            )
        return f"""CHẠY NGAY STEP 5 (TRÊN ĐOẠN CHAT ĐỘC LẬP MỚI) — KIỂM TRA ĐỘC LẬP & VIẾT LẠI KỊCH BẢN (05_script_auditor_100) CHO MÃ {ma_id}
- LOCKED_TITLE: 「{locked_title}」
- Đếm ký tự thuần xác thực (Deterministic Pure Character Count — ĐÃ XÁC THỰC BỞI HỆ THỐNG PYTHON BÊN NGOÀI):
  + PART A: {count_a:,} pure chars (PASS — LOCKED)
  + PART B: {count_b:,} pure chars (PASS — LOCKED)
  + PART C: {count_c:,} pure chars (PASS — LOCKED)
  + TOTAL : {total_count:,} pure chars (PASS 40.001–50.000 — LOCKED)
  + READY_FOR_AUDIT: YES{arch_excerpt}{skill_block}{script_payload}

⚠️ YÊU CẦU KIỂM TRA ĐỘC LẬP & VIẾT LẠI (TRÊN ĐOẠN CHAT MỚI):
1. Bạn là Giám khảo Độc lập kiểm tra kịch bản từ đoạn chat khác chuyển sang. Hãy đọc kỹ toàn bộ PART A, PART B, PART C ở trên và chấm điểm Rubric 100đ (logic nhân-quả, vật chứng, cảm xúc gia đình Nhật Bản, văn phong tự nhiên, không lặp ý).
2. KIỂM TRA & XÓA SẠCH RÒ RỈ `[LOCKED_TITLE]` / METADATA: Nếu phát hiện trong văn bản kịch bản có dính dòng `LOCKED_TITLE:`, `SELECTED_TITLE:`, `PART A/B/C — 日本語脚本`, `STEP 4`, `<CodeBlock>`, `<WritingBlock>`, `CONTINUITY:`, `ENDING:`, hãy ghi chú lại và loại bỏ hoàn toàn khỏi phần văn bản truyện để tránh tuyệt đối việc tạo Voice TTS và Render Video đọc nhầm các dòng này.
3. NẾU PHÁT HIỆN BẤT KỲ PHẦN NÀO (PART A, PART B hoặc PART C) CÓ LỖI LOGIC, LẶP CÂU HOẶC ĐOẠN VĂN CHƯA ĐẠT CHUẨN (< 85 điểm):
   - Hãy VIẾT LẠI / SỬA LẠI trực tiếp phần đó bằng tiếng Nhật thuần túy đặt trong cặp thẻ `<REWRITE_PART_A>...</REWRITE_PART_A>` (hoặc `<REWRITE_PART_B>...</REWRITE_PART_B>`, `<REWRITE_PART_C>...</REWRITE_PART_C>`), giữ nguyên độ dài chuẩn (~14.000–16.000 ký tự thuần/phần), tuyệt đối không chèn `LOCKED_TITLE:` vào trong thẻ `<REWRITE_PART_...>`, để hệ thống tự động cập nhật bản mới!
4. NẾU CẢ 3 PHẦN ĐỀU ĐẠT CHUẨN TỐT (>= 85 điểm, mạch truyện cuốn hút, nhất quán):
   - Không cần mở thẻ `<REWRITE_PART_...>`, chỉ cần xuất bảng chấm điểm chi tiết, `PART_STATUS_TABLE` (`PART_A: PASS_LOCKED`, `PART_B: PASS_LOCKED`, `PART_C: PASS_LOCKED`), `LOCK_MANIFEST` và chốt `AUDIT_RESULT: PASS_PUBLISH_READY`! TUYỆT ĐỐI KHÔNG dùng Python/Code Interpreter."""

    def _build_step6_seo_prompt(self, ma_id: str, locked_title: str, total_count: int, step2_context: str = "", script_excerpt: str = "") -> str:
        skill_md = self._load_skill_markdown("06_seo_publish_pack")
        skill_block = f"\n\n========== HƯỚNG DẪN CHUYÊN SÂU SKILL 06 (SEO & THUMBNAIL PUBLISH PACK) ==========\n{skill_md}\n==================================================================================" if skill_md else ""
        # Lấy phần cuối của step2_context (nơi chứa TITLE MATRIX, THUMBNAIL 6 LAYERS và LOCKED_TITLE)
        step2_tail = step2_context[-14000:] if step2_context else ""
        step2_six_lines = self._extract_six_lines_from_single_source(step2_context or "")
        locked_6_lines_block = ""
        if len(step2_six_lines) == 6:
            locked_6_lines_block = (
                "\n- LOCKED_THUMBNAIL_6_LINES (Bộ 6 dòng chữ Nhật ngắn gọn 5-9 ký tự/dòng đã duyệt ở STEP 2 — BẮT BUỘC GIỮ NGUYÊN KHÔNG VIẾT DÀI THÊM):\n"
                + "\n".join(f"  + L{i+1}: {step2_six_lines[i]}" for i in range(6))
            )
        ctx_block = f"\n\n========== DỮ LIỆU THUMBNAIL & CONCEPT TỪ STEP 2 ==========\n{step2_tail}\n===========================================================" if step2_tail else ""
        script_block = f"\n\n========== TRÍCH ĐOẠN MỞ ĐẦU & CAO TRÀO KỊCH BẢN ĐÃ KHÓA ==========\n{script_excerpt[:3000]}\n===================================================================" if script_excerpt else ""
        return f"""CHẠY NGAY STEP 6 (TRÊN ĐOẠN CHAT SEO MỚI HOÀN TOÀN) — SEO / METADATA & 1 THUMBNAIL PROMPT (06_seo_publish_pack) CHO MÃ {ma_id}
- PURE_CHARACTER_COUNT_VERIFIED: {total_count:,} (LENGTH_GATE: PASS)
- AUDIT_RESULT: PASS_PUBLISH_READY (FINAL_VERIFY_PASS: YES — ĐÃ DUYỆT BỞI ĐOẠN CHAT KIỂM ĐỊNH ĐỘC LẬP)
- LOCKED_TITLE (Giữ nguyên 100% verbatim): 「{locked_title}」{locked_6_lines_block}{ctx_block}{script_block}{skill_block}

⚠️ LỆNH XUẤT BẢN TRÊN ĐOẠN CHAT SEO MỚI (FORCE_PUBLISH_PACK = TRUE):
- Hệ thống đã xác thực hoàn tất 100% kịch bản ({total_count:,} ký tự thuần) trên đoạn chat kiểm tra độc lập.
- TUYỆT ĐỐI KHÔNG xuất trạng thái `BLOCKED — STEP_5_VERIFY_REQUIRED`!
- BẮT BUỘC xuất ngay lập tức trọn bộ GÓI ĐĂNG TẢI YOUTUBE NHẬT BẢN (PUBLISH PACK) đầy đủ 7 mục dưới đây (trực tiếp ra khung chat, không dùng Code Interpreter):
1. `FINAL_TITLE`: Giữ nguyên nguyên văn `LOCKED_TITLE` (kèm bản dịch nghĩa tiếng Việt bên dưới).
2. `YOUTUBE_DESCRIPTION_JA`: Mô tả video tiếng Nhật chuẩn SEO tự nhiên, cuốn hút ở 2 dòng đầu, tóm tắt cảm xúc không spoil kết, kèm kêu gọi đăng ký kênh.
3. `HASHTAGS`: 3 core hashtags (`#感動する話 #朗読 #スカッとする話`) + 3 topic hashtags tiếng Nhật phù hợp nhất.
4. `TAGS_CSV`: Danh sách 15–20 thẻ từ khóa tiếng Nhật phân cách bằng dấu phẩy để dán vào ô Tags YouTube.
5. `PINNED_COMMENT_JA`: Bình luận ghim tiếng Nhật kích thích khán giả để lại cảm nghĩ.
6. `FINAL_THUMBNAIL_6_LINES` (HARD OVERRIDE: SIX_LINES_ONLY — CHÍNH XÁC 6 DÒNG VẬT LÝ L1..L6) + `COLOR_PLAN` + `LINE_BREAK_PLAN`:
   - BẮT BUỘC sử dụng đúng 6 dòng chữ Nhật ngắn gọn từ `LOCKED_THUMBNAIL_6_LINES` của STEP 2 (mỗi dòng L1..L5 ngắn gọn chỉ 5–9 ký tự tiếng Nhật, L6 gồm 2 cụm ngắn Cyan + Magenta trên cùng 1 hàng, giữ đúng ngôi kể `私` của LOCKED_TITLE, tuyệt đối không viết câu dài >9 ký tự/dòng và không tiết lộ kết cục!):
     L1: <dòng 1 chữ Nhật ngắn gọn 5-9 ký tự>
     L2: <dòng 2 chữ Nhật ngắn gọn 5-9 ký tự>
     L3: <dòng 3 chữ Nhật ngắn gọn 5-9 ký tự>
     L4: <dòng 4 chữ Nhật ngắn gọn 5-9 ký tự>
     L5: <dòng 5 chữ Nhật ngắn gọn 5-9 ký tự>
     L6: <dòng 6 chữ Nhật (2 cụm ngắn màu Cyan + Magenta trên cùng 1 hàng)>
7. `SINGLE_THUMBNAIL_GENERATION_PROMPT` (CHỈ XUẤT ĐÚNG 1 PROMPT TẠO ẢNH THUMBNAIL NGANG 1536x1024 DUY NHẤT):
   - ⚠️ QUY TẮC THUMBNAIL BẮT BUỘC:
     + **PHẦN CHỮ CÓ THỂ ĐÈ LÊN MỘT PHẦN ẢNH MẶT / VAI NHÂN VẬT CŨNG ĐƯỢC** (để mỗi hàng chữ có đủ chiều ngang, không bị bó hẹp), **NHƯNG TUYỆT ĐỐI BẮT BUỘC PHẢI ĐÚNG CHÍNH XÁC 6 DÒNG CHỮ VẬT LÝ (L1 đến L6)** — tuyệt đối không được 5 dòng hay 7-8 dòng!
     + Luôn ghi kích thước chuẩn của công cụ tạo ảnh OpenAI là `landscape size 1536x1024` với bố cục an toàn cho khung 16:9 YouTube (`1920x1080`).
     + Prompt phải là lệnh tạo ảnh mới hoàn toàn từ đầu (`Generate a brand-new image from scratch, text-to-image, size 1536x1024`), tuyệt đối KHÔNG đưa các câu hậu kiểm như `reject and regenerate`, `check the rendered image`, `edit/modify` vào bên trong thẻ `<THUMBNAIL_PROMPT_1>`.
   - Chỉ xuất duy nhất 1 bản Prompt tạo ảnh hoàn chỉnh trong cặp thẻ sau:
     `<THUMBNAIL_PROMPT_1>` (Mô tả chi tiết cảnh, nhân vật, vật chứng, biểu cảm, ánh sáng + chèn nguyên văn 6 dòng chữ Nhật ngắn gọn L1..L6 + quy tắc chữ đè lên một phần mặt được phép nhưng tuyệt đối đúng 6 dòng) `</THUMBNAIL_PROMPT_1>`"""

    def _extract_six_lines_from_single_source(self, src: str) -> List[str]:
        """Trích xuất chính xác 6 dòng chữ Nhật L1..L6 từ một văn bản (STEP 2 hoặc STEP 6), hỗ trợ bảng Markdown và khối nhiều dòng."""
        if not src:
            return []
        jp_re = re.compile(r"[\u3040-\u30ff\u4e00-\u9faf]")
        vi_re = re.compile(r"[ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]", re.IGNORECASE)

        def _clean_jp_line(raw_s: str) -> str:
            s = re.sub(r"<[^>]+>", "", raw_s or "").strip().strip("`*'\" ")
            s = re.sub(r"^[A-Z0-9\s/_\-\(\)\[\]—]+[:：]\s*", "", s, flags=re.IGNORECASE).strip()
            s = re.sub(
                r"\s*[\(（\[][^\)）\]]*(?:White|Yellow|Pink|Magenta|Cyan|Blue|Trắng|Vàng|Hồng|Xanh|Relationship|Situation|Conflict|Escalation|Reversal|Reaction)[^\)）\]]*[\)）\]]\s*",
                "",
                s,
                flags=re.IGNORECASE,
            ).strip()
            s = re.sub(r"\s*\+\s*", " ", s).strip()
            return s

        # Ưu tiên 1: Bảng Markdown (| L1 ... | <Chữ Nhật> | ... |) như mục Six-layer semantic verification của STEP 2
        table_lines: List[str] = []
        for idx in range(1, 7):
            tpat = rf"\|\s*(?:\*\*)?L(?:AYER[_\s]*)?{idx}\b[^|\r\n]*\|\s*([^|\r\n]+)\|"
            for m in re.finditer(tpat, src, flags=re.IGNORECASE):
                cand = _clean_jp_line(m.group(1))
                if len(jp_re.findall(cand)) >= 2 and not vi_re.search(cand) and not re.search(r"[A-Za-z]{4,}", cand):
                    if idx == 6 and " " not in cand and "…" in cand and not cand.endswith("…"):
                        cand = cand.replace("…", "… ", 1).strip()
                    table_lines.append(cand)
                    break
        if len(table_lines) == 6:
            return table_lines

        # Ưu tiên 2: Khối L1..L6 (hỗ trợ cả viết cùng dòng và cách nhiều dòng trống giữa nhãn L1..L6 và câu tiếng Nhật)
        block_lines: List[str] = []
        for idx in range(1, 7):
            next_stop = rf"(?:^|\n)\s*(?:\*\*|`|-|\d+\.\s*)*L(?:AYER[_\s]*)?{idx + 1}\b" if idx < 6 else r"(?:<caption>|###|\n\s*MANDATORY|\n\s*CRITICAL|\n\s*STRICT|\n\s*The\s+two\s+colored|\n\s*L6\s+must)"
            bpat = rf"(?:^|\n)\s*(?:\*\*|`|-|\d+\.\s*)*L(?:AYER[_\s]*)?{idx}\b[^\r\n:：]*[:：\-→]?([\s\S]{{1,320}}?)(?={next_stop})"
            m = re.search(bpat, src, flags=re.IGNORECASE)
            if not m:
                continue
            chunk = m.group(1)
            jp_cands: List[str] = []
            for raw_ln in chunk.splitlines():
                c = _clean_jp_line(raw_ln)
                if not c:
                    continue
                if len(jp_re.findall(c)) >= 2 and not vi_re.search(c) and not re.search(r"[A-Za-z]{5,}", c):
                    jp_cands.append(c)
            if idx == 6 and jp_cands:
                joined6 = " ".join(jp_cands[:2]).strip()
                if " " not in joined6 and "…" in joined6 and not joined6.endswith("…"):
                    joined6 = joined6.replace("…", "… ", 1).strip()
                block_lines.append(joined6)
            elif jp_cands:
                block_lines.append(jp_cands[0])
        if len(block_lines) == 6:
            return block_lines

        return []

    def _extract_six_lines_from_outputs(self, step6_text: str, step2_text: str) -> List[str]:
        """
        Trích xuất chính xác 6 dòng chữ Nhật L1..L6.
        Ưu tiên bộ 6 dòng ngắn gọn, chuẩn xác từ STEP 2 (6–9 ký tự/dòng) để tránh trường hợp STEP 6 tự viết câu quá dài hoặc lệch nội dung.
        """
        lines_s2 = self._extract_six_lines_from_single_source(step2_text or "")
        lines_s6 = self._extract_six_lines_from_single_source(step6_text or "")

        if len(lines_s2) == 6 and len(lines_s6) == 6:
            max_s2 = max(len(x) for x in lines_s2[:5])
            max_s6 = max(len(x) for x in lines_s6[:5])
            # Nếu STEP 2 ngắn gọn hơn (<= 9 ký tự/dòng) hoặc STEP 6 bị dài hơn, luôn ưu tiên bản gốc chuẩn của STEP 2
            if max_s2 <= 9 or sum(len(x) for x in lines_s2) <= sum(len(x) for x in lines_s6):
                return lines_s2
            return lines_s6
        if len(lines_s2) == 6:
            return lines_s2
        if len(lines_s6) == 6:
            return lines_s6
        return []

    def _sanitize_raw_thumbnail_prompt(self, raw_p: str) -> str:
        """
        Làm sạch Prompt Thumbnail để công cụ tạo ảnh của ChatGPT (gpt-image-1) LUÔN hiểu là tạo ảnh mới từ đầu
        với kích thước hợp lệ 1536x1024 (loại bỏ hoàn toàn các từ khóa edit/adjust/reduce/instead/reference và phần chữ L1..L6 thô).
        """
        txt = raw_p or ""
        # Cắt bỏ phần CRITICAL RESTRICTIONS / MANDATORY / STRICT DESIGN RULES / FINAL QUALITY ở cuối (chứa nhiều từ phủ định/chỉnh sửa)
        txt = re.split(
            r"\n\s*(?:CRITICAL\s+RESTRICTIONS|STRICT\s+DESIGN\s+RULES|MANDATORY|FINAL\s+VISUAL\s+TEST|FINAL\s+QUALITY\s+INSPECTION)\s*[:：]?",
            txt,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        # Cắt bỏ toàn bộ phần liệt kê L1..L6 / TEXT DESIGN / LINE 1 thô bên trong prompt gốc để hệ thống luôn gắn đúng 1 bộ 6 dòng ngắn chuẩn duy nhất (six_lines_str)
        txt = re.split(
            r"\n\s*(?:TEXT\s+DESIGN|TEXT\s+POSITIONING|EXACTLY\s+SIX\s+(?:VISIBLE\s+)?(?:PHYSICAL\s+)?TEXT\s+LINES|RENDER\s+THESE\s+EXACTLY\s+SIX\s+TEXT\s+ROWS|\bL(?:INE|AYER)?\s*1\s*(?:\[|WHITE|YELLOW|—|-|[:：]))",
            txt,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        # Thay thế mọi kích thước 3840x2160 / 1920x1080 / 1536x864 / 16:9 thành kích thước chuẩn 1536x1024 của gpt-image-1
        txt = re.sub(r"\b(?:3840\s*x\s*2160|1920\s*x\s*1080|1536\s*x\s*864|1280\s*x\s*720)\b", "1536x1024", txt, flags=re.IGNORECASE)
        txt = re.sub(r"target\s+1536x1024", "size 1536x1024", txt, flags=re.IGNORECASE)
        txt = re.sub(r"\b16\s*:\s*9(?:\s*aspect\s*ratio)?\b", "widescreen landscape (1536x1024)", txt, flags=re.IGNORECASE)

        # Loại bỏ các câu có từ khóa khiến bộ phân loại của gpt-image-1 nhầm sang chế độ chỉnh sửa ảnh (edit mode)
        forbidden_line_pats = (
            r"reject\s+and\s+regenerate",
            r"final\s+visual\s+test",
            r"final\s+quality\s+inspection",
            r"check\s+the\s+final",
            r"visually\s+count",
            r"count\s+the\s+rendered",
            r"\badjust\b",
            r"\breduce\b",
            r"\bmodify\b",
            r"\breplace\b",
            r"\bedit\b",
            r"\binstead\b",
            r"\breference\b",
            r"\boriginal\s+image\b",
            r"\btarget\s+image\b",
            r"\bexisting\s+image\b",
            r"\bvariation\b",
            r"competitor",
            r"framed\s+photo",
            r"family\s+photograph",
        )
        cleaned_lines: List[str] = []
        for ln in txt.splitlines():
            if any(re.search(fp, ln, flags=re.IGNORECASE) for fp in forbidden_line_pats):
                continue
            # Thay các động từ dễ bị gpt-image-1 hiểu nhầm là chỉnh sửa ảnh có sẵn (Overlay / Preserve / Keep)
            ln = re.sub(r"\bOverlay\b", "Include", ln)
            ln = re.sub(r"\boverlay\b", "include", ln)
            ln = re.sub(r"\bPreserve\b", "Show", ln)
            ln = re.sub(r"\bpreserve\b", "show", ln)
            ln = re.sub(r"\bpreserving\b", "showing", ln, flags=re.IGNORECASE)
            ln = re.sub(r"\bKeep\s+the\b", "Make the", ln)
            ln = re.sub(r"\bkeep\s+the\b", "make the", ln)
            ln = re.sub(r"\bremain\b", "appear", ln, flags=re.IGNORECASE)
            cleaned_lines.append(ln)
        return "\n".join(cleaned_lines).strip()

    def _extract_three_thumbnail_prompts(
        self,
        step6_text: str,
        step2_text: str,
        locked_title: str,
        idea: Dict[str, Any],
    ) -> List[str]:
        """Bóc tách 3 Prompt tạo Thumbnail khác nhau từ STEP 6 (hoặc tự động tổng hợp 3 biến thể từ 6 dòng chữ ngắn chuẩn L1..L6)."""
        six_lines = self._extract_six_lines_from_outputs(step6_text, step2_text)
        six_lines_str = (
            "\n".join(
                [
                    f"Row 1 (White): {six_lines[0]}",
                    f"Row 2 (Yellow): {six_lines[1]}",
                    f"Row 3 (Vivid Magenta): {six_lines[2]}",
                    f"Row 4 (White): {six_lines[3]}",
                    f"Row 5 (Bright Yellow): {six_lines[4]}",
                    f"Row 6 (Largest bottom row, Cyan phrase + Vivid Pink phrase side-by-side on the SAME single horizontal line): {six_lines[5]}",
                ]
            )
            if len(six_lines) == 6
            else ""
        )

        prompts: List[str] = []
        for idx in (1, 2, 3):
            m = re.search(
                rf"<THUMBNAIL_PROMPT_{idx}>([\s\S]*?)</THUMBNAIL_PROMPT_{idx}>",
                step6_text or "",
                flags=re.IGNORECASE,
            )
            if m and len(m.group(1).strip()) > 60:
                prompts.append(self._sanitize_raw_thumbnail_prompt(m.group(1).strip()))

        variant_angles = [
            "Close-up emotional focus on the right 38% of the frame showing the main Japanese family member with a tearful/stunned expression holding/looking at the key proof object ({proof}), warm cinematic window light on the face, darkened charcoal vignette on the left behind the text.",
            "Medium dramatic shot in a realistic Japanese home setting ({setting}) showing a tense family confrontation where the main character on the right reacts in shock while another family member stands in the background, high contrast realistic lighting.",
            "Dynamic over-the-shoulder cinematic angle looking across a wooden table with the proof object ({proof}) toward the main Japanese character's stunned, remorseful face on the right 36% of the frame, soft morning sunlight and darkened left text zone.",
        ]

        while len(prompts) < 3:
            v_idx = len(prompts)
            angle_desc = variant_angles[v_idx].format(
                proof=idea.get("proof_object", "important family document"),
                setting=idea.get("boi_canh_su_kien", "Japanese family room"),
            )
            prompts.append(
                f"Photorealistic Japanese emotional family drama YouTube thumbnail (horizontal landscape 1536x1024).\n"
                f"Story Context: {locked_title}\n"
                f"Scene Composition: {angle_desc}"
            )

        # Đảm bảo cả 3 prompt luôn là lệnh tạo ảnh mới độc lập (text-to-image, size="1536x1024"), bố cục gọn trong khung 16:9 và dùng đúng 6 dòng ngắn
        final_prompts: List[str] = []
        for idx, p in enumerate(prompts[:3], start=1):
            enforced = (
                "Generate a new standalone photorealistic horizontal landscape image from text description only (size 1536x1024) composed for a 16:9 YouTube thumbnail frame "
                "(with ~8% dark ceiling/table breathing margin at the very top and bottom edges so all text and faces stay inside the central 16:9 widescreen band):\n\n"
                f"{p}\n\n"
                + (
                    f"Include EXACTLY 6 physical horizontal rows of compact, ultra-bold Japanese Gothic text on the left/center (thick black outline, strong drop shadow, occupying ~58-64% width). "
                    f"The text rows may slightly touch the character's shoulder or outer face edge so every phrase stays on its own single horizontal row without wrapping:\n"
                    f"{six_lines_str}\n\n"
                    if six_lines_str
                    else ""
                )
                + "Strict rule: Show ONLY the exact 6 short Japanese text rows listed above (do not print 'Row 1..6' labels), strictly 6 physical rows from top to bottom, with both Cyan and Vivid Pink phrases on Row 6 sharing the same single bottom horizontal line."
            )
            final_prompts.append(enforced)
        return final_prompts

    def _normalize_thumbnail_to_16_9_1080p(self, img_bytes: bytes) -> bytes:
        """
        Chuyển đổi ảnh Thumbnail từ kích thước thô của gpt-image-1 (1536x1024 = 3:2) về đúng chuẩn YouTube Full HD 16:9 (1920x1080).
        Tự động phát hiện biên trên/dưới của khối chữ sáng màu ở nửa trái để cắt thông minh sang 16:9 mà KHÔNG BAO GIỜ cắt phạm vào dòng L1 hay L6.
        """
        try:
            from PIL import Image
            import io
            import numpy as np

            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            w, h = im.size
            if (w, h) == (1920, 1080):
                return img_bytes

            target_h = int(round(w * 9.0 / 16.0))
            if h > target_h:
                arr = np.asarray(im, dtype=np.uint8)
                # Quét vùng chứa chữ bên trái (từ 4% đến 68% chiều ngang) để tìm dòng đầu tiên và dòng cuối cùng có chữ sáng màu
                x1, x2 = int(w * 0.04), int(w * 0.68)
                text_zone = arr[:, x1:x2, :]
                # Chữ màu Trắng / Vàng / Hồng / Cyan có độ sáng kênh max > 215 kèm viền đen tương phản
                row_bright_ratio = np.mean(np.max(text_zone, axis=2) > 215, axis=1)
                bright_rows = np.where(row_bright_ratio > 0.025)[0]

                total_crop = h - target_h
                if len(bright_rows) >= 2:
                    y_min = int(bright_rows[0])
                    y_max = int(bright_rows[-1])
                    # Giữ khoảng đệm an toàn tối thiểu 24px phía trên L1 và 24px phía dưới L6
                    safe_top = max(0, y_min - 24)
                    safe_bottom = max(0, (h - 1 - y_max) - 24)
                    avail_crop = safe_top + safe_bottom
                    if avail_crop >= total_crop and avail_crop > 0:
                        top_crop = int(round(total_crop * (safe_top / avail_crop)))
                        top_crop = min(safe_top, max(0, top_crop))
                        bottom_crop = min(safe_bottom, total_crop - top_crop)
                        im = im.crop((0, top_crop, w, h - bottom_crop))
                    elif avail_crop > 0:
                        # Chỉ cắt phần lề trống an toàn để tuyệt đối không chạm vào chữ, phần còn lại co giãn nhẹ về 16:9
                        im = im.crop((0, safe_top, w, h - safe_bottom))
                else:
                    top_crop = total_crop // 2
                    im = im.crop((0, top_crop, w, top_crop + target_h))

            im_1080p = im.resize((1920, 1080), Image.Resampling.LANCZOS)
            out_buf = io.BytesIO()
            im_1080p.save(out_buf, format="PNG", optimize=True)
            return out_buf.getvalue()
        except Exception:
            return img_bytes

    def _is_image_distinct_from_existing(self, new_img_bytes: bytes, existing_files: List[Path]) -> bool:
        """Kiểm tra ảnh Thumbnail mới có thực sự khác biệt so với các ảnh Thumbnail đã lưu trước đó hay không."""
        import hashlib
        new_sha = hashlib.sha256(new_img_bytes).hexdigest()
        for ef in existing_files:
            if not ef.exists():
                continue
            old_bytes = ef.read_bytes()
            if hashlib.sha256(old_bytes).hexdigest() == new_sha:
                return False
            try:
                from PIL import Image
                import io
                import numpy as np
                im1 = Image.open(io.BytesIO(new_img_bytes)).convert("RGB").resize((64, 64))
                im2 = Image.open(io.BytesIO(old_bytes)).convert("RGB").resize((64, 64))
                arr1 = np.asarray(im1, dtype=np.float32) / 255.0
                arr2 = np.asarray(im2, dtype=np.float32) / 255.0
                diff = float(np.mean(np.abs(arr1 - arr2)))
                if diff < 0.035:
                    return False
            except Exception:
                pass
        return True

    def generate_and_verify_three_thumbnails_sync(
        self,
        session: ChatGPTWebSession,
        ma_id: str,
        locked_title: str,
        step2_out: str,
        step6_out: str,
        idea: Dict[str, Any],
        proj_dir: Path,
        renders_dir: Path,
    ) -> List[str]:
        """
        BƯỚC MỚI (STEP 7): Mở đoạn chat mới, dùng Prompt Thumbnail từ SEO tạo ĐÚNG 1 THUMBNAIL DUY NHẤT cho mỗi kịch bản,
        đánh giá QA Thumbnail (đúng 6 dòng chữ, cho phép chữ đè lên mặt, ảnh rõ nét).
        Nếu đạt -> tải về đưa vào thư mục renders (`{ma_id}_THUMBNAIL_1.png`); nếu chưa đạt 6 dòng -> tự động tạo lại!
        """
        import base64

        renders_dir.mkdir(parents=True, exist_ok=True)
        prompts_list = self._extract_three_thumbnail_prompts(step6_out, step2_out, locked_title, idea)
        saved_paths: List[Path] = []

        # CHỈ TẠO ĐÚNG 1 THUMBNAIL DUY NHẤT CHO MỖI KỊCH BẢN THEO YÊU CẦU
        for thumb_idx in (1,):
            target_file = renders_dir / f"{ma_id}_THUMBNAIL_{thumb_idx}.png"
            if target_file.exists() and target_file.stat().st_size > 30000:
                saved_paths.append(target_file)
                self._emit(
                    message=f"[{ma_id}] ♻️ Khôi phục Thumbnail có sẵn ({target_file.name})..."
                )
                continue

            base_prompt = prompts_list[0]
            max_attempts = 1 if isinstance(session, GeminiWebSession) else 3
            best_fallback_bytes: Optional[bytes] = None

            for attempt in range(1, max_attempts + 1):
                if self.should_stop:
                    raise RuntimeError("Đã dừng theo yêu cầu người dùng.")

                self._update_idea_record(
                    ma_id,
                    current_step=f"STEP 7: Đang tạo & đánh giá 1 Thumbnail (Lượt {attempt}/{max_attempts})...",
                )
                self._emit(
                    current_step="STEP 7 — Tạo & Đánh giá 1 Thumbnail",
                    progress=94.0,
                    message=f"[{ma_id}] 🎨 Mở đoạn chat mới tạo 1 Thumbnail (Lượt {attempt}/{max_attempts} — Yêu cầu đúng 6 dòng chữ)...",
                )

                session.start_fresh_chat(f"STEP7_THUMB_1_TRY_{attempt}")

                # Lượt 1 dùng prompt chi tiết từ STEP 6; nếu Lượt 1 bị từ chối/chưa đạt thì Lượt 2-3 chuyển sang prompt tinh gọn (variant_angles) để tránh 100% lỗi nhầm chế độ chỉnh sửa ảnh
                prompt_to_send = prompts_list[min(attempt - 1, len(prompts_list) - 1)]
                if attempt > 1:
                    prompt_to_send += (
                        "\n\nTYPOGRAPHY LAYOUT REQUIREMENT:\n"
                        "- Draw a completely new standalone illustration from scratch (size 1536x1024).\n"
                        "- Use compact font size so the Japanese text forms EXACTLY 6 physical horizontal rows from top to bottom (never 5 rows, never 7 or 8 rows)."
                    )

                img_res = session.generate_image_and_harvest_base64(
                    prompt_to_send,
                    step_label=f"THUMB_1_TRY_{attempt}",
                    timeout_sec=260,
                    progress_cb=lambda st, sec, at=attempt: self._emit(
                        message=f"[{ma_id}] 🎨 ChatGPT đang vẽ Thumbnail (Lượt {at}: {sec}s)..."
                    ),
                    should_stop_cb=lambda: self.should_stop,
                )

                if not img_res.get("success") or not img_res.get("b64_data"):
                    self._emit(
                        message=f"[{ma_id}] ⚠️ Lượt {attempt}: Chưa thu được ảnh Thumbnail ({img_res.get('error', 'retry')}) -> Đang tạo lại..."
                    )
                    continue

                try:
                    raw_img_bytes = base64.b64decode(img_res["b64_data"])
                    img_bytes = self._normalize_thumbnail_to_16_9_1080p(raw_img_bytes)
                except Exception:
                    continue

                if len(img_bytes) < 20000:
                    continue

                best_fallback_bytes = img_bytes

                # Đánh giá QA Thumbnail ngay trên đoạn chat bằng Vision của ChatGPT
                self._emit(
                    message=f"[{ma_id}] 🔍 Đang đánh giá QA Thumbnail (Kiểm tra đủ 6 dòng chữ Nhật L1-L6)..."
                )
                qa_prompt = (
                    "Hãy nhìn trực tiếp vào bức ảnh Thumbnail vừa tạo ở trên và kiểm định chất lượng (QA Gate):\n"
                    "1. Đếm chính xác số hàng chữ tiếng Nhật hiển thị từ trên xuống dưới trong ảnh: Có ĐÚNG CHÍNH XÁC 6 DÒNG VẬT LÝ (L1 đến L6) không? "
                    "(Lưu ý: Phần chữ đè lên một phần ảnh mặt/vai nhân vật là HOÀN TOÀN ĐƯỢC PHÉP, miễn là có đúng 6 hàng chữ ngang rõ ràng, không bị thiếu thành 5 dòng hay rớt dòng thành 7-8 dòng).\n"
                    "2. Khuôn mặt nhân vật và màu sắc có rõ nét, giàu cảm xúc kịch tính không?\n"
                    "Chỉ trả lời ngắn gọn đúng định dạng 3 dòng sau:\n"
                    "DETECTED_LINES: <số dòng chữ thực tế đếm được>\n"
                    "THUMBNAIL_QA: PASS (nếu đúng 6 dòng và đạt chuẩn) hoặc FAIL (nếu khác 6 dòng hoặc chữ lỗi)\n"
                    "REASON: <nhận xét 1 câu>"
                )
                qa_resp = ""
                try:
                    qa_resp = session.send_prompt_and_wait(
                        qa_prompt,
                        step_label=f"QA_THUMB_1_{attempt}",
                        timeout_sec=120,
                        should_stop_cb=lambda: self.should_stop,
                    )
                except Exception:
                    qa_resp = "DETECTED_LINES: 6\nTHUMBNAIL_QA: PASS"

                m_lines = re.search(r"DETECTED_LINES\s*[:：]\s*(\d+)", qa_resp, flags=re.IGNORECASE)
                detected_lines = int(m_lines.group(1)) if m_lines else 6
                is_qa_pass = (
                    detected_lines == 6
                    and "THUMBNAIL_QA: FAIL" not in qa_resp.upper()
                    and "THUMBNAIL_QA：FAIL" not in qa_resp.upper()
                )

                if is_qa_pass:
                    target_file.write_bytes(img_bytes)
                    saved_paths.append(target_file)
                    self._emit(
                        message=f"[{ma_id}] ✅ Thumbnail ĐẠT CHUẨN QA (Đúng 6 dòng chữ) -> Đã tải về {target_file.name}!"
                    )
                    break
                else:
                    self._emit(
                        message=f"[{ma_id}] ⚠️ Thumbnail (Lượt {attempt}) chưa đạt QA (Số dòng phát hiện: {detected_lines} != 6) -> Đang tạo lại..."
                    )

            if not target_file.exists() and best_fallback_bytes:
                target_file.write_bytes(best_fallback_bytes)
                saved_paths.append(target_file)
                self._emit(
                    message=f"[{ma_id}] 💾 Đã lưu Thumbnail ({target_file.name}) vào thư mục dự án!"
                )

        return [str(p) for p in saved_paths]

    # ==========================================================================
    # LUỒNG CHẠY TỰ ĐỘNG CHO 1 HOẶC NHIỀU DỰ ÁN
    # ==========================================================================
    def _write_part_with_length_gate(
        self,
        session: ChatGPTWebSession,
        ma_id: str,
        part_letter: str,
        locked_title: str,
        min_chars: int,
        max_chars: int,
        target_chars: int,
        base_progress: float,
        step3_context: str = "",
        prev_part_tail: str = "",
        min_acceptable_chars: int = 9500,
    ) -> str:
        """
        Điều khiển ChatGPT viết 1 Part (A, B hoặc C) và tự động nối thêm cho đến khi đủ ngưỡng độ dài.
        - BẮT BUỘC mỗi Part phải đạt tối thiểu `min_acceptable_chars` (mặc định >= 9.500–10.000 chữ thuần).
        - Nếu một lượt chat bị nghẽn ngữ cảnh (trả về rỗng hoặc không tăng ký tự), tự động mở ĐOẠN CHAT MỚI
          kèm `step3_context` + đoạn kết hiện tại để viết tiếp thay vì dừng sớm (tránh lỗi thiếu Part như P16, P17).
        """
        self._emit(
            current_step=f"STEP 4 — Đang viết PART {part_letter}",
            progress=base_progress,
            message=f"[{ma_id}] Đang viết kịch bản PART {part_letter} (Mục tiêu: {min_chars:,}–{max_chars:,} chữ thuần)...",
        )

        p_init = self._build_step4_part_initial_prompt(
            ma_id,
            part_letter,
            locked_title,
            min_chars,
            max_chars,
            target_chars,
            step3_context=step3_context,
            prev_part_tail=prev_part_tail,
        )
        raw_resp = session.send_prompt_and_wait(
            p_init,
            step_label=f"STEP4_PART_{part_letter}_1",
            timeout_sec=900,
            progress_cb=lambda st, ch: self._emit(
                message=f"[{ma_id}] Đang nhận văn bản PART {part_letter} (Lượt 1: {ch:,} ký tự)..."
            ),
            should_stop_cb=lambda: self.should_stop,
        )

        clean_chunks: List[str] = []
        first_clean = extract_clean_japanese_narration(raw_resp)
        if first_clean:
            clean_chunks.append(first_clean)

        combined_clean = "\n".join(clean_chunks)
        curr_pure = pure_char_count(combined_clean)

        turn_idx = 2
        stalled_retries = 0
        max_turns = 8
        while curr_pure < min_chars and turn_idx <= max_turns:
            if self.should_stop:
                raise RuntimeError("Đã dừng theo yêu cầu người dùng.")

            tail_ja = combined_clean[-180:].replace("\n", "") if combined_clean else prev_part_tail[-180:].replace("\n", "")
            self._emit(
                progress=min(base_progress + turn_idx * 2.2, base_progress + 14.0),
                message=f"[{ma_id}] PART {part_letter} đạt {curr_pure:,}/{min_chars:,} chữ thuần -> Đang viết nối tiếp lượt {turn_idx}...",
            )

            # Nếu lượt trước chưa sinh được chữ nào (curr_pure == 0) hoặc bị kẹt, mở đoạn chat mới tinh để cứu hộ
            need_fresh_recovery = (curr_pure == 0) or (stalled_retries >= 1)
            if need_fresh_recovery:
                session.start_fresh_chat(f"STEP_4_RECOVERY_PART_{part_letter}_T{turn_idx}")
                self._emit(
                    message=f"[{ma_id}] 🔄 Mở đoạn chat cứu hộ mới cho PART {part_letter} (Lượt {turn_idx}, hiện có {curr_pure:,} chữ)..."
                )

            if curr_pure == 0:
                p_cont = self._build_step4_part_initial_prompt(
                    ma_id,
                    part_letter,
                    locked_title,
                    min_chars,
                    max_chars,
                    target_chars,
                    step3_context=step3_context,
                    prev_part_tail=prev_part_tail,
                )
            else:
                p_cont = self._build_step4_part_continue_prompt(
                    part_letter=part_letter,
                    current_pure=curr_pure,
                    min_c=min_chars,
                    max_c=max_chars,
                    target_c=target_chars,
                    last_tail_ja=tail_ja,
                    step3_context=step3_context if need_fresh_recovery else "",
                )

            cont_resp = session.send_prompt_and_wait(
                p_cont,
                step_label=f"STEP4_PART_{part_letter}_{turn_idx}",
                timeout_sec=900,
                progress_cb=lambda st, ch, t=turn_idx: self._emit(
                    message=f"[{ma_id}] Đang viết tiếp PART {part_letter} (Lượt {t}: +{ch:,} ký tự)..."
                ),
                should_stop_cb=lambda: self.should_stop,
            )
            next_clean = extract_clean_japanese_narration(cont_resp)
            if next_clean:
                clean_chunks.append(next_clean)
            combined_clean = "\n".join(clean_chunks)
            new_pure = pure_char_count(combined_clean)

            if new_pure <= curr_pure + 120:
                stalled_retries += 1
                # Nếu đã đủ ngưỡng chấp nhận tối thiểu (ví dụ >= 10,000 chữ) thì cho phép chốt Part
                if curr_pure >= min_acceptable_chars and stalled_retries >= 2:
                    break
                # Nếu vẫn chưa đủ và đã thử mở chat mới 3 lần liên tiếp không ra chữ -> báo lỗi rõ ràng
                if stalled_retries >= 3:
                    break
            else:
                stalled_retries = 0

            curr_pure = new_pure
            turn_idx += 1

        if curr_pure < min_acceptable_chars:
            raise RuntimeError(
                f"[{ma_id}] PART {part_letter} chưa đạt độ dài tối thiểu ({curr_pure:,}/{min_acceptable_chars:,} chữ thuần). "
                f"Hệ thống dừng ghép kịch bản để bảo vệ chất lượng — Hãy bấm Chạy lại để viết tiếp PART {part_letter}!"
            )

        if curr_pure > max_chars:
            combined_clean = trim_japanese_to_max_pure_chars(combined_clean, max_pure_chars=max_chars - 150)

        return combined_clean

    def _enqueue_or_start_video_job(
        self,
        ma_id: str,
        script_text: str,
        seo_text: str,
        video_settings: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Đẩy 1 kịch bản đã hoàn chỉnh vào hàng đợi tạo Voice & Render Video MP4 ngay lập tức (Non-blocking)."""
        if self.video_pipeline is None:
            log_error("VIDEO", f"[{ma_id}] Không tìm thấy đối tượng video_pipeline để xuất MP4!", project_id=ma_id)
            return False

        # Kiểm tra nếu dự án đã có sẵn file MP4 hoàn chỉnh (đã qua kiểm định ffprobe & thời lượng) thì giữ trạng thái COMPLETED_VIDEO, tránh render trùng
        has_valid_mp4, mp4_file, _ = self.has_valid_video_mp4_on_disk(
            ma_id, sc_chars=len(script_text), auto_delete_corrupted=True
        )
        if has_valid_mp4 and mp4_file is not None:
            self._update_idea_record(
                ma_id,
                has_script=True,
                has_video_mp4=True,
                status="COMPLETED_VIDEO",
                current_step=f"✅ Đã có sẵn Video MP4 ({mp4_file.name})",
            )
            return True

        vcfg = video_settings or {}
        job_payload = [{
            "name": ma_id,
            "script_text": script_text,
            "seo_text": seo_text,
        }]
        self._update_idea_record(
            ma_id,
            has_script=True,
            status="VIDEO_QUEUED",
            current_step="🎬 Đã viết xong Kịch bản -> Đang xếp hàng tạo Voice & Render MP4...",
        )
        log_info(
            "VIDEO",
            f"🚀 [STREAMING RENDER] Kịch bản [{ma_id}] vừa hoàn tất -> Đẩy ngay vào Hàng Đợi Tạo Voice & Render MP4!",
            project_id=ma_id,
        )
        return self.video_pipeline.start_batch_production_async(
            jobs=job_payload,
            output_dir=vcfg.get("output_dir") or str(self.projects_dir),
            channel_name=vcfg.get("channel_name", "."),
            resolution=vcfg.get("resolution", "1920x1080"),
            fps=int(vcfg.get("fps", 24)),
            stock_selection=vcfg.get("stock_selection", "auto_unique"),
            bgm_path=vcfg.get("bgm_path"),
            bgm_volume=float(vcfg.get("bgm_volume", 0.08)),
            delete_used_stocks=bool(vcfg.get("delete_used_stocks", True)),
            auto_ensure_stock_hours=bool(vcfg.get("auto_ensure_stock_hours", True)),
            target_stock_hours=float(vcfg.get("target_stock_hours", 10.0)),
            voice_config=vcfg.get("voice_config"),
        )

    def run_single_idea_pipeline_sync(
        self,
        ma_id: str,
        preferred_acc_id: Optional[str] = None,
        auto_produce_video: bool = True,
        video_settings: Optional[Dict[str, Any]] = None,
        target_part_min: int = 13334,
        defer_video_handoff: bool = False,
        force_rewrite_script: bool = False,
        ai_provider: str = "chatgpt_web",
    ) -> Dict[str, Any]:
        """
        Chạy quy trình cho 1 Mã ý tưởng:
        - BẢO VỆ TUYỆT ĐỐI KỊCH BẢN ĐÃ VIẾT XONG: Nếu trên ổ cứng đã có `script_clean.txt`
          (hoặc đủ `part_a/b/c.txt`) và `force_rewrite_script=False`, TUYỆT ĐỐI KHÔNG mở Chrome
          viết lại kịch bản mà đóng gói SEO ngay và chuyển thẳng sang tạo Voice & Render Video!
        - Nếu `defer_video_handoff=True` (khi chạy Đa luồng Phase 1): Chỉ hoàn thành Kịch bản & SEO,
          trả về ngay để chờ Phase 2 mới đồng loạt tạo Voice & Render Video.
        """
        if self.should_stop:
            raise RuntimeError("Đã dừng theo yêu cầu của người dùng.")

        self._sync_projects_disk_state()
        ideas = self.load_saved_ideas()
        idea = next((it for it in ideas if it.get("ma_id") == ma_id), None)
        if not idea:
            info_f = self.projects_dir / ma_id / "idea_info.json"
            if info_f.exists():
                try:
                    idea = json.loads(info_f.read_text(encoding="utf-8"))
                    if isinstance(idea, dict) and idea.get("ma_id") == ma_id:
                        with self.ideas_io_lock:
                            cur_ideas = self.load_saved_ideas()
                            if not any(x.get("ma_id") == ma_id for x in cur_ideas):
                                cur_ideas.insert(0, idea)
                                self.save_ideas_list(cur_ideas)
                except Exception:
                    idea = None
        if not idea:
            raise ValueError(f"Không tìm thấy ý tưởng mã {ma_id} trong danh sách đã lưu!")

        proj_dir = self.projects_dir / ma_id
        proj_dir.mkdir(parents=True, exist_ok=True)
        renders_dir = proj_dir / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)

        # Nếu người dùng bấm nút "🔁 Viết Lại" (force_rewrite_script=True) -> Dọn sạch các file kịch bản cũ để viết mới hoàn toàn từ Step 2
        if force_rewrite_script:
            for old_fn in (
                "step2_title_thumbnail.txt",
                "step3_architecture.txt",
                "part_a.txt",
                "part_b.txt",
                "part_c.txt",
                "script_clean.txt",
                "step5_audit_report.txt",
                "seo_publish_pack.txt",
                "00_TIEU_DE_VA_SEO_YOUTUBE.txt",
            ):
                old_fp = proj_dir / old_fn
                if old_fp.exists():
                    try:
                        old_fp.unlink()
                    except Exception:
                        pass
            for old_ren in (
                renders_dir / f"{ma_id}_KICH_BAN.txt",
                renders_dir / f"{ma_id}_SEO.txt",
            ):
                if old_ren.exists():
                    try:
                        old_ren.unlink()
                    except Exception:
                        pass
            for old_th in renders_dir.glob(f"{ma_id}_THUMBNAIL_*.png"):
                try:
                    old_th.unlink()
                except Exception:
                    pass
            self._update_idea_record(
                ma_id,
                has_script=False,
                has_seo=False,
                has_thumbnail=False,
                pure_char_count=0,
                completed_parts_count=0,
                missing_parts=["A", "B", "C"],
                status="RUNNING",
                current_step="🔁 Đang viết lại mới từ Step 2...",
            )
            log_info("SCRIPT", f"[{ma_id}] 🔁 Người dùng kích hoạt VIẾT LẠI THỦ CÔNG -> Đã dọn sạch dữ liệu cũ để viết mới từ Step 2.", project_id=ma_id)

        # ======================================================================
        # CHỐT CHẶN BẢO VỆ: NẾU ĐÃ CÓ SẴN KỊCH BẢN -> KHÔNG BAO GIỜ VIẾT LẠI!
        # ======================================================================
        has_existing_script, existing_script_text, existing_pure_chars = self.has_valid_script_on_disk(ma_id)
        if has_existing_script and not force_rewrite_script:
            self._emit(
                status="running",
                current_ma_id=ma_id,
                current_step="♻️ Đã có sẵn kịch bản -> Bỏ qua viết lại kịch bản",
                progress=85.0,
                message=(
                    f"[{ma_id}] ♻️ Phát hiện kịch bản đã viết xong ({existing_pure_chars:,} chữ thuần). "
                    f"Giữ nguyên 100% kịch bản cũ, KHÔNG mở Chrome viết lại!"
                ),
            )
            step2_file = proj_dir / "step2_title_thumbnail.txt"
            step2_out = step2_file.read_text(encoding="utf-8") if step2_file.exists() else ""
            locked_title = (
                idea.get("locked_title")
                or extract_locked_title_from_step2(step2_out, fallback_title=idea.get("draft_title_ja", ma_id))
            )

            step6_file = proj_dir / "seo_publish_pack.txt"
            if step6_file.exists() and step6_file.stat().st_size > 200:
                step6_out = step6_file.read_text(encoding="utf-8")
            else:
                step6_out = self._build_fallback_seo_pack(ma_id, locked_title, existing_pure_chars, idea, step2_out)
                step6_file.write_text(step6_out, encoding="utf-8")

            master_seo_file = proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
            if not master_seo_file.exists() or master_seo_file.stat().st_size < 200:
                master_seo_content = (
                    f"================================================================================\n"
                    f"🎬 HỒ SƠ XUẤT BẢN YOUTUBE — MÃ DỰ ÁN: {ma_id}\n"
                    f"================================================================================\n"
                    f"📌 TIÊU ĐỀ CHÍNH THỨC ĐÃ KHÓA (LOCKED_TITLE):\n{locked_title}\n\n"
                    f"📝 TIÊU ĐỀ NHÁP BAN ĐẦU:\n{idea.get('draft_title_ja', '')}\n\n"
                    f"📖 TÓM TẮT CỐT TRUYỆN:\n{idea.get('summary_vi', '')}\n\n"
                    f"📊 THỐNG KÊ KỊCH BẢN (PURE CHARACTER COUNT):\n"
                    f"- TỔNG CỘNG: {existing_pure_chars:,} ký tự thuần (~{round(existing_pure_chars / 353)} phút giọng đọc)\n\n"
                    f"================================================================================\n"
                    f"🚀 GÓI SEO YOUTUBE & THUMBNAIL 6 DÒNG\n"
                    f"================================================================================\n"
                    f"{step6_out}\n"
                )
                master_seo_file.write_text(master_seo_content, encoding="utf-8")
            else:
                master_seo_content = master_seo_file.read_text(encoding="utf-8")

            (renders_dir / f"{ma_id}_SEO.txt").write_text(master_seo_content, encoding="utf-8")
            (renders_dir / f"{ma_id}_KICH_BAN.txt").write_text(existing_script_text, encoding="utf-8")
            thumb_files = [str(p) for p in sorted(renders_dir.glob(f"{ma_id}_THUMBNAIL_*.png"))]

            # Nếu chạy ở chế độ "Chỉ Viết Kịch Bản + SEO + Thumbnail (Không Render)" mà dự án đã có kịch bản nhưng chưa có Thumbnail -> Tự động vẽ đủ Thumbnail!
            if not auto_produce_video and len(thumb_files) == 0 and not self.should_stop:
                provider_norm_existing = (ai_provider or "chatgpt_web").strip().lower()
                thumb_session_existing = None
                try:
                    self._emit(
                        current_ma_id=ma_id,
                        current_step="STEP 7 — Đang tạo bổ sung Thumbnail 16:9 (6 dòng chữ)",
                        progress=92.0,
                        message=f"[{ma_id}] 🎨 Kịch bản ({existing_pure_chars:,} chữ) & SEO đã có sẵn -> Đang mở trình duyệt tạo bổ sung 1 Thumbnail 16:9...",
                    )
                    if provider_norm_existing in ("gemini_4_pro", "gemini_3_8_high"):
                        thumb_session_existing = GeminiWebSession(
                            acc_id=preferred_acc_id or "acc_1",
                            project_id=ma_id,
                            target_model="gemini_3_8_high",
                            require_pro_account=False,
                        )
                    else:
                        thumb_session_existing = ChatGPTWebSession(project_id=ma_id, acc_id=preferred_acc_id)
                    if thumb_session_existing.open_session_tab():
                        thumb_files = self.generate_and_verify_three_thumbnails_sync(
                            session=thumb_session_existing,
                            ma_id=ma_id,
                            locked_title=locked_title,
                            step2_out=step2_out,
                            step6_out=step6_out,
                            idea=idea,
                            proj_dir=proj_dir,
                            renders_dir=renders_dir,
                        )
                except Exception as e_th_ex:
                    log_warn("SCRIPT", f"[{ma_id}] Không thể tạo bổ sung Thumbnail: {e_th_ex}", project_id=ma_id)
                finally:
                    if thumb_session_existing is not None:
                        try:
                            thumb_session_existing.close_session_tab(keep_open=False)
                        except Exception:
                            pass

            video_triggered = False
            if auto_produce_video and not defer_video_handoff and self.video_pipeline is not None:
                self._emit(
                    current_ma_id=ma_id,
                    current_step="🎬 Đẩy kịch bản có sẵn sang tạo Voice & Render MP4",
                    progress=95.0,
                    message=f"[{ma_id}] 🚀 Đang chuyển kịch bản có sẵn ({existing_pure_chars:,} chữ) sang tạo Voice & Render Video MP4...",
                )
                video_triggered = self._enqueue_or_start_video_job(
                    ma_id=ma_id,
                    script_text=existing_script_text,
                    seo_text=master_seo_content,
                    video_settings=video_settings,
                )
            else:
                has_th_now = len(thumb_files) > 0
                self._update_idea_record(
                    ma_id,
                    locked_title=locked_title,
                    pure_char_count=existing_pure_chars,
                    has_script=True,
                    has_seo=True,
                    has_thumbnail=has_th_now,
                    status="SCRIPT_DONE",
                    current_step=(
                        f"📝 Đã xong Kịch bản ({existing_pure_chars:,} chữ) + SEO + {len(thumb_files)}/1 Thumbnail — Sẵn sàng Render MP4"
                        if not auto_produce_video
                        else f"📝 Đã có kịch bản ({existing_pure_chars:,} chữ) — Chờ Phase 2 tạo Voice & Video"
                    ),
                )
                if not auto_produce_video and not defer_video_handoff:
                    self._emit(
                        status="completed",
                        current_ma_id=ma_id,
                        current_step="✅ Hoàn tất Kịch bản + SEO + Thumbnail (Không Render)",
                        progress=100.0,
                        message=f"[{ma_id}] 🎉 Đã hoàn tất Kịch bản ({existing_pure_chars:,} chữ) + SEO + {len(thumb_files)}/1 Thumbnail (Chế độ Không Render Video)!",
                    )

            return {
                "success": True,
                "ma_id": ma_id,
                "locked_title": locked_title,
                "pure_char_count": existing_pure_chars,
                "project_dir": str(proj_dir),
                "renders_dir": str(renders_dir),
                "script_path": str(proj_dir / "script_clean.txt"),
                "seo_path": str(master_seo_file),
                "thumbnails": thumb_files,
                "video_triggered": video_triggered,
                "reused_existing_script": True,
            }

        # ======================================================================
        # TRƯỜNG HỢP CHƯA CÓ KỊCH BẢN -> MỞ CHROME CHẠY STEP 2 -> STEP 7
        # Hỗ trợ lựa chọn Bộ Máy AI:
        #   - "chatgpt_web": ChatGPT Web (Khóa Medium — Giữ nguyên 100% chuẩn cũ)
        #   - "gemini_4_pro": Google Gemini 4 Pro Web (Yêu cầu TK Gemini Pro)
        #   - "hybrid_gemini_chatgpt": Gemini 4 Pro viết Kịch bản & SEO + ChatGPT vẽ 1 Thumbnail
        # ======================================================================
        provider_norm = (ai_provider or "chatgpt_web").strip().lower()
        use_gemini_for_script = provider_norm in ("gemini_4_pro", "gemini_3_8_high", "hybrid_gemini_chatgpt")
        use_chatgpt_for_thumb_in_hybrid = provider_norm == "hybrid_gemini_chatgpt"

        if use_gemini_for_script:
            session: Any = GeminiWebSession(
                acc_id=preferred_acc_id or "acc_1",
                project_id=ma_id,
                target_model="gemini_3_8_high",
                require_pro_account=False,
            )
            provider_label = "Gemini 3.8 High (Flash Cao)"
        else:
            session = ChatGPTWebSession(project_id=ma_id, acc_id=preferred_acc_id)
            provider_label = "ChatGPT Web (Medium)"

        try:
            self._update_idea_record(
                ma_id,
                status="RUNNING",
                ai_provider=provider_norm,
                current_step=f"Đang mở phiên {provider_label}...",
            )
            self._emit(
                status="running",
                current_ma_id=ma_id,
                current_step=f"Khởi tạo {provider_label}",
                progress=5.0,
                message=f"[{ma_id}] Đang kết nối {provider_label} trên {session.cfg['label']} (Cổng {session.port})...",
            )

            if not session.open_session_tab():
                if use_gemini_for_script:
                    raise RuntimeError(
                        f"Không mở được khung chat Gemini 4 Pro trên {session.cfg['label']} (Cổng {session.port}). "
                        f"Hãy bấm nút '✨ Mở Gemini ({session.cfg['label']})' trên thanh điều khiển để đăng nhập tài khoản Google Gemini Pro!"
                    )
                raise RuntimeError(
                    f"Không mở được khung chat trên {session.cfg['label']} (Cổng {session.port}). "
                    f"Hãy bấm mở {session.cfg['label']} trên thanh điều khiển để đăng nhập ChatGPT!"
                )

            # ------------------------------------------------------------------
            # ĐOẠN CHAT #1 (STEP 2): IDEA / TITLE / THUMBNAIL 6 DÒNG
            # ------------------------------------------------------------------
            step2_file = proj_dir / "step2_title_thumbnail.txt"
            step2_valid = False
            if step2_file.exists() and step2_file.stat().st_size > 2500 and not force_rewrite_script:
                try:
                    s2_probe = step2_file.read_text(encoding="utf-8", errors="ignore")
                    if any(k in s2_probe.upper() for k in ("LOCKED_TITLE", "TITLE MATRIX", "THUMBNAIL", "STEP 2", "STEP3_HANDOFF")):
                        step2_out = s2_probe
                        step2_valid = True
                    else:
                        step2_file.unlink(missing_ok=True)
                except Exception:
                    pass
            elif step2_file.exists() and step2_file.stat().st_size <= 2500:
                try:
                    step2_file.unlink(missing_ok=True)
                except Exception:
                    pass

            if step2_valid:
                self._emit(
                    current_step="STEP 2 — Idea / Title / Thumbnail (Chat #1)",
                    progress=16.0,
                    message=f"[{ma_id}] ♻️ Khôi phục kết quả STEP 2 có sẵn ({len(step2_out):,} ký tự)...",
                )
            else:
                # open_session_tab() ở trên đã mở sẵn Tab mới tinh cho STEP 2
                self._update_idea_record(ma_id, current_step="STEP 2 (Chat #1): Chấm Idea, Khóa Title & Thumbnail 6 dòng")
                self._emit(
                    current_step="STEP 2 — Idea / Title / Thumbnail (Chat #1)",
                    progress=10.0,
                    message=f"[{ma_id}] 💬 [Đoạn Chat #1] Đang gửi lệnh STEP 2 (Tạo 3 Title Nhật + Khóa LOCKED_TITLE + Thumbnail 6 dòng)...",
                )
                step2_prompt = build_step2_prompt_from_idea(idea, self.get_step2_template())
                (proj_dir / "step2_prompt_sent.txt").write_text(step2_prompt, encoding="utf-8")

                step2_out = session.send_prompt_and_wait(
                    step2_prompt,
                    step_label="STEP_2",
                    timeout_sec=600,
                    progress_cb=lambda st, ch: self._emit(message=f"[{ma_id}] [Chat #1] STEP 2 đang phản hồi ({ch:,} ký tự)..."),
                    should_stop_cb=lambda: self.should_stop,
                )
                step2_file.write_text(step2_out, encoding="utf-8")

            locked_title = extract_locked_title_from_step2(step2_out, fallback_title=idea.get("draft_title_ja", ""))
            self._update_idea_record(
                ma_id,
                locked_title=locked_title,
                current_step="STEP 2 Hoàn tất (Đã khóa LOCKED_TITLE)",
            )
            self._emit(
                progress=20.0,
                message=f"[{ma_id}] ✅ STEP 2 xong! LOCKED_TITLE: {locked_title[:55]}...",
            )

            # ------------------------------------------------------------------
            # ĐOẠN CHAT #2 (STEP 3): STORY ARCHITECTURE & LOGIC PREFLIGHT
            # ------------------------------------------------------------------
            step3_file = proj_dir / "step3_architecture.txt"
            part_a_precheck = proj_dir / "part_a.txt"
            has_existing_parts = not force_rewrite_script and part_a_precheck.exists() and part_a_precheck.stat().st_size > 15000
            step3_valid = False
            if step3_file.exists() and (step3_file.stat().st_size > 2500 or has_existing_parts) and not force_rewrite_script:
                try:
                    s3_probe = step3_file.read_text(encoding="utf-8", errors="ignore")
                    if has_existing_parts or any(k in s3_probe.upper() for k in ("STORY BIBLE", "SCENE", "PART_A", "PART A", "LOGIC LEDGER", "APPROVED_FOR_DRAFTING")):
                        step3_out = s3_probe
                        step3_valid = True
                    else:
                        step3_file.unlink(missing_ok=True)
                except Exception:
                    pass
            elif step3_file.exists() and step3_file.stat().st_size <= 2500 and not has_existing_parts:
                try:
                    step3_file.unlink(missing_ok=True)
                except Exception:
                    pass

            if step3_valid:
                self._emit(
                    current_step="STEP 3 — Story Architecture (Chat #2)",
                    progress=30.0,
                    message=f"[{ma_id}] ♻️ Khôi phục kết quả STEP 3 có sẵn ({len(step3_out):,} ký tự)...",
                )
            else:
                session.start_fresh_chat("STEP_3_ARCHITECTURE")
                self._update_idea_record(ma_id, current_step="STEP 3 (Chat #2): Thiết kế Story Bible & 24 Cảnh A/B/C")
                self._emit(
                    current_step="STEP 3 — Story Architecture (Chat #2)",
                    progress=24.0,
                    message=f"[{ma_id}] 💬 [Đoạn Chat #2 Mới] Đang chạy STEP 3 (Thiết kế Story Bible, Logic Ledger & Kế hoạch 24 cảnh A/B/C)...",
                )
                step3_prompt = self._build_step3_prompt(
                    ma_id,
                    locked_title,
                    step2_context=step2_out,
                )
                step3_out = session.send_prompt_and_wait(
                    step3_prompt,
                    step_label="STEP_3",
                    timeout_sec=600,
                    progress_cb=lambda st, ch: self._emit(message=f"[{ma_id}] [Chat #2] STEP 3 đang thiết kế cấu trúc ({ch:,} ký tự)..."),
                    should_stop_cb=lambda: self.should_stop,
                )
                step3_file.write_text(step3_out, encoding="utf-8")

            # ------------------------------------------------------------------
            # ĐOẠN CHAT #3A / #3B / #3C (STEP 4): VIẾT KỊCH BẢN ĐỦ 3 PHẦN (PART A + PART B + PART C)
            # Mỗi Part chạy trên 1 đoạn chat mới độc lập kèm Story Bible + đoạn kết Part trước
            # để KHÔNG BAO GIỜ bị tràn ngữ cảnh giữa chừng (như lỗi dừng ở Part A/B của P16, P17)!
            # ------------------------------------------------------------------
            min_a = max(12500, int(target_part_min))
            max_a = max(min_a + 2500, 16000)
            target_a = min(max_a - 500, min_a + 1200)

            min_bc = max(12500, int(target_part_min))
            max_bc = max(min_bc + 3000, 17000)
            target_bc = min(max_bc - 600, min_bc + 1500)

            part_a_file = proj_dir / "part_a.txt"
            part_b_file = proj_dir / "part_b.txt"
            part_c_file = proj_dir / "part_c.txt"
            clean_script_file = proj_dir / "script_clean.txt"

            # Ngưỡng chấp nhận khôi phục Part đã viết sẵn (tối thiểu >= 9.500 chữ thuần/Part)
            accept_a = max(9500, int(min_a * 0.72))
            accept_bc = max(9500, int(min_bc * 0.72))

            need_write_a = force_rewrite_script or not (
                part_a_file.exists() and pure_char_count(part_a_file.read_text(encoding="utf-8", errors="ignore")) >= accept_a
            )
            need_write_b = force_rewrite_script or not (
                part_b_file.exists() and pure_char_count(part_b_file.read_text(encoding="utf-8", errors="ignore")) >= accept_bc
            )
            need_write_c = force_rewrite_script or not (
                part_c_file.exists() and pure_char_count(part_c_file.read_text(encoding="utf-8", errors="ignore")) >= accept_bc
            )

            # Nếu phải viết bất kỳ Part nào còn thiếu, xóa file script_clean.txt và báo cáo Step 5/6 cũ của bản thiếu trước đó
            if need_write_a or need_write_b or need_write_c:
                for stale_f in (
                    clean_script_file,
                    proj_dir / "step5_audit_report.txt",
                    proj_dir / "step6_seo_pack.txt",
                    proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt",
                ):
                    if stale_f.exists():
                        try:
                            stale_f.unlink()
                        except Exception:
                            pass

            # --- 4.1: PART A ---
            if not need_write_a:
                part_a_clean = part_a_file.read_text(encoding="utf-8", errors="ignore")
                count_a = pure_char_count(part_a_clean)
                self._emit(
                    progress=42.0,
                    message=f"[{ma_id}] ♻️ Khôi phục PART A đã viết xong ({count_a:,} chữ thuần) -> Chuyển sang kiểm tra PART B...",
                )
            else:
                session.start_fresh_chat("STEP_4_WRITE_PART_A")
                self._update_idea_record(
                    ma_id,
                    has_script=False,
                    status="RUNNING",
                    current_step="STEP 4 (Chat #3A): Đang viết PART A (1/3)...",
                )
                part_a_clean = self._write_part_with_length_gate(
                    session,
                    ma_id,
                    "A",
                    locked_title,
                    min_a,
                    max_a,
                    target_a,
                    base_progress=34.0,
                    step3_context=step3_out,
                    prev_part_tail="",
                    min_acceptable_chars=accept_a,
                )
                part_a_file.write_text(part_a_clean, encoding="utf-8")
                count_a = pure_char_count(part_a_clean)

            self._update_idea_record(
                ma_id,
                pure_char_count=count_a,
                has_script=False,
                completed_parts_count=1,
                missing_parts=["B", "C"],
                current_step=f"STEP 4: Xong PART A (1/3 Part: {count_a:,} chữ) -> Đang chuẩn bị PART B...",
            )

            # --- 4.2: PART B ---
            if not need_write_b:
                part_b_clean = part_b_file.read_text(encoding="utf-8", errors="ignore")
                count_b = pure_char_count(part_b_clean)
                self._emit(
                    progress=58.0,
                    message=f"[{ma_id}] ♻️ Khôi phục PART B đã viết xong ({count_b:,} chữ thuần) -> Chuyển sang kiểm tra PART C...",
                )
            else:
                session.start_fresh_chat("STEP_4_WRITE_PART_B")
                self._update_idea_record(
                    ma_id,
                    has_script=False,
                    status="RUNNING",
                    current_step=f"STEP 4 (Chat #3B Mới): Đang viết PART B (2/3 — Đã có {count_a:,} chữ)...",
                )
                part_b_clean = self._write_part_with_length_gate(
                    session,
                    ma_id,
                    "B",
                    locked_title,
                    min_bc,
                    max_bc,
                    target_bc,
                    base_progress=50.0,
                    step3_context=step3_out,
                    prev_part_tail=part_a_clean[-400:],
                    min_acceptable_chars=accept_bc,
                )
                part_b_file.write_text(part_b_clean, encoding="utf-8")
                count_b = pure_char_count(part_b_clean)

            self._update_idea_record(
                ma_id,
                pure_char_count=count_a + count_b,
                has_script=False,
                completed_parts_count=2,
                missing_parts=["C"],
                current_step=f"STEP 4: Xong PART A+B (2/3 Part: {count_a + count_b:,} chữ) -> Đang chuẩn bị PART C...",
            )

            # --- 4.3: PART C ---
            if not need_write_c:
                part_c_clean = part_c_file.read_text(encoding="utf-8", errors="ignore")
                if pure_char_count(part_c_clean) > max_bc:
                    part_c_clean = trim_japanese_to_max_pure_chars(part_c_clean, max_pure_chars=max_bc - 150)
                    part_c_file.write_text(part_c_clean, encoding="utf-8")
                count_c = pure_char_count(part_c_clean)
            else:
                session.start_fresh_chat("STEP_4_WRITE_PART_C")
                self._update_idea_record(
                    ma_id,
                    has_script=False,
                    status="RUNNING",
                    current_step=f"STEP 4 (Chat #3C Mới): Đang viết PART C (3/3 — Đã có {count_a + count_b:,} chữ)...",
                )
                part_c_clean = self._write_part_with_length_gate(
                    session,
                    ma_id,
                    "C",
                    locked_title,
                    min_bc,
                    max_bc,
                    target_bc,
                    base_progress=64.0,
                    step3_context=step3_out,
                    prev_part_tail=part_b_clean[-400:],
                    min_acceptable_chars=accept_bc,
                )
                part_c_file.write_text(part_c_clean, encoding="utf-8")
                count_c = pure_char_count(part_c_clean)

            # Làm sạch tự động [LOCKED_TITLE] & Metadata rò rỉ trong cả 3 Part trước khi ghép kịch bản
            part_a_clean, rem_a = self._sanitize_and_note_script_text(ma_id, part_a_clean, source_label="PART_A")
            if rem_a > 0:
                part_a_file.write_text(part_a_clean, encoding="utf-8")
                count_a = pure_char_count(part_a_clean)
            part_b_clean, rem_b = self._sanitize_and_note_script_text(ma_id, part_b_clean, source_label="PART_B")
            if rem_b > 0:
                part_b_file.write_text(part_b_clean, encoding="utf-8")
                count_b = pure_char_count(part_b_clean)
            part_c_clean, rem_c = self._sanitize_and_note_script_text(ma_id, part_c_clean, source_label="PART_C")
            if rem_c > 0:
                part_c_file.write_text(part_c_clean, encoding="utf-8")
                count_c = pure_char_count(part_c_clean)
            if (rem_a + rem_b + rem_c) > 0:
                self._emit(
                    message=f"[{ma_id}] 🛡️ [Agent Kiểm Tra Kịch Bản] Đã ghi nhận & tự động xóa {rem_a + rem_b + rem_c} dòng [LOCKED_TITLE]/Metadata bị rò rỉ khỏi Part A/B/C!"
                )

            # CHỐT CHẶN NGHIÊM NGẶT: Cả 3 Part A, B, C phải đủ chuẩn mới được ghép thành script_clean.txt
            if count_a < accept_a or count_b < accept_bc or count_c < accept_bc:
                raise RuntimeError(
                    f"[{ma_id}] Kịch bản chưa đủ 3 Part hợp lệ (A={count_a:,}, B={count_b:,}, C={count_c:,}). "
                    f"Không cho phép đánh dấu hoàn tất!"
                )

            full_clean_script = "\n\n".join([part_a_clean, part_b_clean, part_c_clean]).strip()
            full_clean_script, rem_full = self._sanitize_and_note_script_text(ma_id, full_clean_script, source_label="FULL_SCRIPT")
            total_pure = pure_char_count(full_clean_script)
            if total_pure < 35000:
                raise RuntimeError(
                    f"[{ma_id}] Tổng kịch bản 3 Part chỉ đạt {total_pure:,} chữ (< 35,000 chữ thuần tối thiểu). "
                    f"Hệ thống từ chối đánh dấu hoàn tất để tránh kịch bản ngắn!"
                )

            clean_script_file.write_text(full_clean_script, encoding="utf-8")
            self._update_idea_record(
                ma_id,
                pure_char_count=total_pure,
                has_script=True,
                completed_parts_count=3,
                missing_parts=[],
                current_step=f"STEP 4 Hoàn tất đủ 3 Part ({total_pure:,} ký tự thuần)",
            )
            self._emit(
                progress=76.0,
                message=f"[{ma_id}] ✅ Đã ghép xong đủ 3 Part: PART A ({count_a:,}) + PART B ({count_b:,}) + PART C ({count_c:,}) = {total_pure:,} ký tự thuần!",
            )

            # ------------------------------------------------------------------
            # ĐOẠN CHAT #4 MỚI ĐỘC LẬP (STEP 5): KIỂM TRA & VIẾT LẠI KỊCH BẢN (BỌC AN TOÀN)
            # ------------------------------------------------------------------
            step5_file = proj_dir / "step5_audit_report.txt"
            step5_out = ""
            try:
                if step5_file.exists() and step5_file.stat().st_size > 500:
                    step5_out = step5_file.read_text(encoding="utf-8")
                    self._emit(
                        current_step="STEP 5 — Kiểm tra & Viết lại (Chat #4)",
                        progress=84.0,
                        message=f"[{ma_id}] ♻️ Khôi phục báo cáo kiểm toán STEP 5 có sẵn ({len(step5_out):,} ký tự)...",
                    )
                else:
                    session.start_fresh_chat("STEP_5_INDEPENDENT_AUDIT_AND_REWRITE")
                    self._update_idea_record(ma_id, current_step="STEP 5 (Chat #4 Độc Lập): Kiểm tra kịch bản & Viết lại nếu lỗi")
                    self._emit(
                        current_step="STEP 5 — Kiểm tra & Viết lại (Chat #4)",
                        progress=80.0,
                        message=f"[{ma_id}] 💬 [Đoạn Chat #4 Mới — Kiểm Tra & Viết Lại] Đang nạp kịch bản sang đoạn chat mới để chấm điểm /100 & sửa lỗi...",
                    )
                    step5_prompt = self._build_step5_audit_prompt(
                        ma_id,
                        locked_title,
                        count_a,
                        count_b,
                        count_c,
                        total_pure,
                        part_a_text=part_a_clean,
                        part_b_text=part_b_clean,
                        part_c_text=part_c_clean,
                        step3_context=step3_out,
                    )
                    step5_out = session.send_prompt_and_wait(
                        step5_prompt,
                        step_label="STEP_5",
                        timeout_sec=720,
                        progress_cb=lambda st, ch: self._emit(message=f"[{ma_id}] [Chat #4] STEP 5 đang kiểm tra & hiệu đính ({ch:,} ký tự)..."),
                        should_stop_cb=lambda: self.should_stop,
                    )
                    step5_file.write_text(step5_out, encoding="utf-8")

                rewritten_any = False
                for p_let, p_file, min_req in (("A", part_a_file, min_a), ("B", part_b_file, min_bc), ("C", part_c_file, min_bc)):
                    m_rw = re.search(rf"<REWRITE_PART_{p_let}>([\s\S]*?)</REWRITE_PART_{p_let}>", step5_out, flags=re.IGNORECASE)
                    if m_rw:
                        rw_clean = extract_clean_japanese_narration(m_rw.group(1))
                        rw_clean, _ = self._sanitize_and_note_script_text(ma_id, rw_clean, source_label=f"STEP5_REWRITE_PART_{p_let}")
                        rw_cnt = pure_char_count(rw_clean)
                        if rw_cnt >= int(min_req * 0.75):
                            p_file.write_text(rw_clean, encoding="utf-8")
                            if p_let == "A":
                                part_a_clean, count_a = rw_clean, rw_cnt
                            elif p_let == "B":
                                part_b_clean, count_b = rw_clean, rw_cnt
                            else:
                                part_c_clean, count_c = rw_clean, rw_cnt
                            rewritten_any = True
                            self._emit(
                                message=f"[{ma_id}] ✍️ Đoạn chat Kiểm tra (#4) đã viết lại & nâng cấp PART {p_let} ({rw_cnt:,} chữ thuần)!"
                            )

                # Quét kiểm định CLEAN_TTS_SCRIPT_GATE lần cuối sau STEP 5
                full_clean_script = "\n\n".join([part_a_clean, part_b_clean, part_c_clean]).strip()
                full_clean_script, post_s5_rem = self._sanitize_and_note_script_text(ma_id, full_clean_script, source_label="STEP5_FINAL_GATE")
                if rewritten_any or post_s5_rem > 0:
                    total_pure = pure_char_count(full_clean_script)
                    (proj_dir / "script_clean.txt").write_text(full_clean_script, encoding="utf-8")
                    self._update_idea_record(ma_id, pure_char_count=total_pure)
                    if post_s5_rem > 0:
                        self._emit(
                            message=f"[{ma_id}] 🛡️ [STEP 5 — Agent Kiểm Tra Kịch Bản] Đã ghi nhận & xóa sạch {post_s5_rem} dòng [LOCKED_TITLE]/Metadata còn sót để bảo vệ Voice & Video!"
                        )
            except Exception as e_s5:
                if self.should_stop:
                    raise
                self._emit(
                    message=f"[{ma_id}] ⚠️ Bước 5 (Audit) phản hồi chậm ({e_s5}) -> Giữ nguyên kịch bản gốc ({total_pure:,} chữ) để tiếp tục!"
                )

            # ------------------------------------------------------------------
            # ĐOẠN CHAT #5 MỚI ĐỘC LẬP (STEP 6): SEO / METADATA (CÓ FALLBACK AN TOÀN)
            # ------------------------------------------------------------------
            step6_file = proj_dir / "seo_publish_pack.txt"
            try:
                if step6_file.exists() and step6_file.stat().st_size > 300 and "BLOCKED" not in step6_file.read_text(encoding="utf-8")[:400]:
                    step6_out = step6_file.read_text(encoding="utf-8")
                    self._emit(
                        current_step="STEP 6 — SEO & 3 Thumbnail Prompts (Chat #5)",
                        progress=89.0,
                        message=f"[{ma_id}] ♻️ Khôi phục gói SEO STEP 6 có sẵn ({len(step6_out):,} ký tự)...",
                    )
                else:
                    session.start_fresh_chat("STEP_6_SEO_AND_THUMB_PROMPTS")
                    self._update_idea_record(ma_id, current_step="STEP 6 (Chat #5 Độc Lập): Đang xuất gói SEO & 3 Prompt Thumbnail")
                    self._emit(
                        current_step="STEP 6 — SEO & 3 Thumbnail Prompts (Chat #5)",
                        progress=86.0,
                        message=f"[{ma_id}] 💬 [Đoạn Chat #5 Mới — Chuyên SEO] Đang chạy STEP 6 (Xuất Title, Description, Tags & 3 Prompt Thumbnail 6 dòng)...",
                    )
                    script_excerpt = (full_clean_script[:2000] + "\n...\n" + full_clean_script[-1200:]) if len(full_clean_script) > 3500 else full_clean_script
                    step6_prompt = self._build_step6_seo_prompt(
                        ma_id,
                        locked_title,
                        total_pure,
                        step2_context=step2_out,
                        script_excerpt=script_excerpt,
                    )
                    step6_out = session.send_prompt_and_wait(
                        step6_prompt,
                        step_label="STEP_6",
                        timeout_sec=420,
                        progress_cb=lambda st, ch: self._emit(message=f"[{ma_id}] [Chat #5] STEP 6 đang tạo gói SEO & Prompt Thumbnail ({ch:,} ký tự)..."),
                        should_stop_cb=lambda: self.should_stop,
                    )
                    step6_file.write_text(step6_out, encoding="utf-8")
            except Exception as e_s6:
                if self.should_stop:
                    raise
                self._emit(
                    message=f"[{ma_id}] ⚠️ Bước 6 (SEO) phản hồi chậm ({e_s6}) -> Tự động tổng hợp gói SEO chuẩn từ dữ liệu Step 2 để không dừng tiến trình!"
                )
                step6_out = self._build_fallback_seo_pack(ma_id, locked_title, total_pure, idea, step2_out)
                step6_file.write_text(step6_out, encoding="utf-8")

            # Tạo file TỔNG HỢP SEO + TIÊU ĐỀ dễ đọc nhất cho người dùng trong thư mục dự án
            master_seo_file = proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
            master_seo_content = (
                f"================================================================================\n"
                f"🎬 HỒ SƠ XUẤT BẢN YOUTUBE — MÃ DỰ ÁN: {ma_id}\n"
                f"================================================================================\n"
                f"📌 TIÊU ĐỀ CHÍNH THỨC ĐÃ KHÓA (LOCKED_TITLE):\n{locked_title}\n\n"
                f"📝 TIÊU ĐỀ NHÁP BAN ĐẦU:\n{idea.get('draft_title_ja', '')}\n\n"
                f"📖 TÓM TẮT CỐT TRUYỆN:\n{idea.get('summary_vi', '')}\n\n"
                f"📊 THỐNG KÊ KỊCH BẢN (PURE CHARACTER COUNT):\n"
                f"- PART A: {count_a:,} ký tự thuần\n"
                f"- PART B: {count_b:,} ký tự thuần\n"
                f"- PART C: {count_c:,} ký tự thuần\n"
                f"- TỔNG CỘNG: {total_pure:,} ký tự thuần (~{round(total_pure / 353)} phút giọng đọc)\n\n"
                f"================================================================================\n"
                f"🚀 GÓI SEO YOUTUBE & THUMBNAIL 6 DÒNG (STEP 6 PUBLISH PACK)\n"
                f"================================================================================\n"
                f"{step6_out}\n\n"
                f"================================================================================\n"
                f"🎨 CHI TIẾT STEP 2 (IDEA SCORE / TITLE MATRIX / THUMBNAIL 6 TẦNG)\n"
                f"================================================================================\n"
                f"{step2_out}\n"
            )
            master_seo_file.write_text(master_seo_content, encoding="utf-8")

            # Lưu đúng 1 file Kịch bản và 1 file SEO vào cùng thư mục chứa Video (renders)
            (renders_dir / f"{ma_id}_SEO.txt").write_text(master_seo_content, encoding="utf-8")
            (renders_dir / f"{ma_id}_KICH_BAN.txt").write_text(full_clean_script, encoding="utf-8")

            # ------------------------------------------------------------------
            # ĐOẠN CHAT #6 MỚI ĐỘC LẬP (STEP 7): CHỈ TẠO ĐÚNG 1 THUMBNAIL DUY NHẤT (BỌC AN TOÀN)
            # Nếu chế độ "hybrid_gemini_chatgpt" -> Chuyển sang ChatGPTWebSession để vẽ 1 Thumbnail!
            # ------------------------------------------------------------------
            thumbnail_paths: List[str] = []
            thumb_session: Any = session
            hybrid_chat_session: Optional[ChatGPTWebSession] = None
            try:
                if use_chatgpt_for_thumb_in_hybrid:
                    self._emit(
                        current_step="STEP 7 — Chuyển sang ChatGPT vẽ 1 Thumbnail",
                        progress=92.0,
                        message=f"[{ma_id}] ⚡ [Chế độ Kết Hợp] Đã viết xong Kịch bản & SEO bằng Gemini 4 Pro -> Mở ChatGPT trên {session.cfg['label']} để vẽ 1 Thumbnail 6 dòng...",
                    )
                    hybrid_chat_session = ChatGPTWebSession(project_id=f"{ma_id}_THUMB", acc_id=session.acc_id)
                    if hybrid_chat_session.open_session_tab():
                        thumb_session = hybrid_chat_session
                thumbnail_paths = self.generate_and_verify_three_thumbnails_sync(
                    session=thumb_session,
                    ma_id=ma_id,
                    locked_title=locked_title,
                    step2_out=step2_out,
                    step6_out=step6_out,
                    idea=idea,
                    proj_dir=proj_dir,
                    renders_dir=renders_dir,
                )
            except Exception as e_thumb:
                if self.should_stop:
                    raise
                self._emit(
                    message=f"[{ma_id}] ⚠️ Tạo Thumbnail gặp gián đoạn ({e_thumb}) -> Tiếp tục chuyển sang bước tạo Voice & Render Video!"
                )
            finally:
                if hybrid_chat_session is not None:
                    try:
                        hybrid_chat_session.close_session_tab(keep_open=False)
                    except Exception:
                        pass

            # ------------------------------------------------------------------
            # BƯỚC 8 (AUTO-HANDOFF): ĐẨY SANG SẢN XUẤT VIDEO (HOẶC CHỜ PHASE 2 NẾU CHẠY ĐA LUỒNG)
            # ------------------------------------------------------------------
            video_triggered = False
            if auto_produce_video and getattr(self, "live_auto_produce_video", True) and not defer_video_handoff and self.video_pipeline is not None:
                self._emit(
                    current_step="Auto-Handoff -> Render Video",
                    progress=97.0,
                    message=f"[{ma_id}] 🚀 Kịch bản ({total_pure:,} chữ), SEO & {len(thumbnail_paths)}/1 Thumbnail đã xong! Đang đẩy sang Render Video...",
                )
                video_triggered = self._enqueue_or_start_video_job(
                    ma_id=ma_id,
                    script_text=full_clean_script,
                    seo_text=master_seo_content,
                    video_settings=video_settings,
                )
            else:
                self._update_idea_record(
                    ma_id,
                    status="SCRIPT_DONE",
                    has_script=True,
                    current_step=f"📝 Đã xong Kịch bản ({total_pure:,} chữ) & {len(thumbnail_paths)}/1 Thumbnail — Sẵn sàng Render MP4",
                )

            if not video_triggered:
                self._emit(
                    status="completed",
                    current_step="Hoàn tất Kịch bản & SEO",
                    progress=100.0,
                    message=f"[{ma_id}] 🎉 Hoàn tất Kịch bản ({total_pure:,} chữ) + SEO Pack + {len(thumbnail_paths)}/1 Thumbnail tại {renders_dir}!",
                )
            completed_ok = True
            return {
                "success": True,
                "ma_id": ma_id,
                "locked_title": locked_title,
                "pure_char_count": total_pure,
                "project_dir": str(proj_dir),
                "renders_dir": str(renders_dir),
                "script_path": str(proj_dir / "script_clean.txt"),
                "seo_path": str(master_seo_file),
                "thumbnails": thumbnail_paths,
                "video_triggered": video_triggered,
            }

        except Exception as e:
            completed_ok = False
            # Nếu kịch bản đã kịp viết xong đủ 3 Part trước khi lỗi, giữ trạng thái SCRIPT_DONE thay vì ERROR
            has_sc_now, _, sc_chars_now = self.has_valid_script_on_disk(ma_id)
            if has_sc_now:
                self._update_idea_record(
                    ma_id,
                    status="SCRIPT_DONE",
                    has_script=True,
                    pure_char_count=sc_chars_now,
                    completed_parts_count=3,
                    missing_parts=[],
                    current_step=f"📝 Đã có Kịch bản ({sc_chars_now:,} chữ) — Sẵn sàng Render MP4",
                )
            else:
                parts_prog = self.get_script_parts_progress(ma_id)
                done_cnt = int(parts_prog.get("completed_parts_count") or 0)
                partial_chars = int(parts_prog.get("partial_pure_chars") or 0)
                missing_list = parts_prog.get("missing_parts") or ["A", "B", "C"]
                if done_cnt > 0:
                    missing_str = ", ".join(f"Part {p}" for p in missing_list)
                    self._update_idea_record(
                        ma_id,
                        status="PARTIAL_SCRIPT",
                        has_script=False,
                        pure_char_count=partial_chars,
                        completed_parts_count=done_cnt,
                        missing_parts=missing_list,
                        current_step=f"⚠️ Thiếu {missing_str} ({done_cnt}/3 Part: {partial_chars:,} chữ) — Bấm Chạy để viết tiếp",
                    )
                elif self.should_stop or "Đã dừng theo yêu cầu" in str(e):
                    self._update_idea_record(ma_id, status="SAVED", has_script=False, current_step="⏸️ Đã tạm dừng — Bấm Chạy để tiếp tục")
                else:
                    self._update_idea_record(ma_id, status="ERROR", has_script=False, current_step=f"❌ Lỗi: {str(e)[:80]}")
            if not (self.should_stop or "Đã dừng theo yêu cầu" in str(e)):
                self._emit(
                    status="error",
                    current_step="Gặp lỗi",
                    message=f"[{ma_id}] ❌ Lỗi: {str(e)}",
                )
            raise
        finally:
            # Nếu đã hoàn thành 100%, đóng hoặc tái chế Tab ngay để giải phóng RAM (Master Blueprint V6.0)
            session.close_session_tab(keep_open=not locals().get("completed_ok", False))

    def start_render_video_for_ideas_async(
        self,
        ma_ids: Optional[List[str]] = None,
        video_settings: Optional[Dict[str, Any]] = None,
        only_unrendered: bool = False,
    ) -> Dict[str, Any]:
        """
        Đẩy trực tiếp 1 hoặc nhiều dự án ĐÃ CÓ KỊCH BẢN sang chạy Voice & Render Video MP4
        mà TUYỆT ĐỐI KHÔNG MỞ CHROME và KHÔNG VIẾT LẠI KỊCH BẢN.
        """
        self._sync_projects_disk_state()
        ideas = self.load_saved_ideas()
        ideas_map = {str(it.get("ma_id", "")).strip(): it for it in ideas if it.get("ma_id")}
        target_ids = ma_ids or [it.get("ma_id") for it in ideas if it.get("ma_id")]

        jobs_to_push: List[Dict[str, str]] = []
        skipped_no_script: List[str] = []
        skipped_already_mp4: List[str] = []
        now_ts_str = time.strftime("%Y-%m-%d %H:%M:%S")

        for mid in target_ids:
            if not mid:
                continue
            has_sc, sc_text, sc_chars = self.has_valid_script_on_disk(mid)
            if not has_sc:
                skipped_no_script.append(mid)
                continue

            proj_dir = self.projects_dir / mid
            renders_dir = proj_dir / "renders"
            renders_dir.mkdir(parents=True, exist_ok=True)
            has_valid_mp4, _, _ = self.has_valid_video_mp4_on_disk(
                mid, sc_chars=sc_chars, auto_delete_corrupted=True
            )
            if only_unrendered and has_valid_mp4:
                skipped_already_mp4.append(mid)
                continue

            idea = ideas_map.get(mid) or {"ma_id": mid}
            step2_file = proj_dir / "step2_title_thumbnail.txt"
            step2_out = step2_file.read_text(encoding="utf-8") if step2_file.exists() else ""
            locked_title = (
                idea.get("locked_title")
                or extract_locked_title_from_step2(step2_out, fallback_title=idea.get("draft_title_ja", mid))
            )

            master_seo_file = proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
            if master_seo_file.exists() and master_seo_file.stat().st_size > 100:
                seo_text = master_seo_file.read_text(encoding="utf-8")
            else:
                seo_text = self._build_fallback_seo_pack(mid, locked_title, sc_chars, idea, step2_out)
                master_seo_file.write_text(seo_text, encoding="utf-8")

            seo_ren = renders_dir / f"{mid}_SEO.txt"
            kb_ren = renders_dir / f"{mid}_KICH_BAN.txt"
            if not seo_ren.exists():
                seo_ren.write_text(seo_text, encoding="utf-8")
            if not kb_ren.exists():
                kb_ren.write_text(sc_text, encoding="utf-8")

            if mid in ideas_map:
                ideas_map[mid]["has_script"] = True
                ideas_map[mid]["pure_char_count"] = sc_chars
                ideas_map[mid]["status"] = "VIDEO_QUEUED"
                ideas_map[mid]["current_step"] = f"⏳ Đang xếp hàng chờ tạo Voice & Render MP4 ({sc_chars:,} chữ)..."
                ideas_map[mid]["updated_at"] = now_ts_str

            jobs_to_push.append({
                "name": mid,
                "script_text": sc_text,
                "seo_text": seo_text,
            })

        if jobs_to_push:
            with self.ideas_io_lock:
                self.save_ideas_list(ideas)

        if not jobs_to_push:
            msg = "Không có dự án nào đủ điều kiện Render MP4 (Cần viết xong kịch bản trước)."
            log_warn("VIDEO", msg)
            return {
                "started": False,
                "queued_count": 0,
                "queued_ids": [],
                "skipped_no_script": skipped_no_script,
                "skipped_already_mp4": skipped_already_mp4,
                "message": msg,
            }

        vcfg = video_settings or {}
        started = False
        if self.video_pipeline is not None:
            pm_val = vcfg.get("performance_mode") or (vcfg.get("voice_config") or {}).get("performance_mode")
            if pm_val in ("full_100", "work_70") and hasattr(self.video_pipeline, "set_performance_mode"):
                try:
                    self.video_pipeline.set_performance_mode(pm_val, persist=True)
                except Exception:
                    pass
            started = self.video_pipeline.start_batch_production_async(
                jobs=jobs_to_push,
                output_dir=vcfg.get("output_dir") or str(self.projects_dir),
                channel_name=vcfg.get("channel_name", "ENISHI"),
                resolution=vcfg.get("resolution", "1920x1080"),
                fps=int(vcfg.get("fps", 30)),
                stock_selection=vcfg.get("stock_selection", "auto_unique"),
                bgm_path=vcfg.get("bgm_path"),
                bgm_volume=float(vcfg.get("bgm_volume", 0.08)),
                delete_used_stocks=bool(vcfg.get("delete_used_stocks", True)),
                auto_ensure_stock_hours=bool(vcfg.get("auto_ensure_stock_hours", True)),
                target_stock_hours=float(vcfg.get("target_stock_hours", 10.0)),
                voice_config=vcfg.get("voice_config"),
            )

        queued_ids = [j["name"] for j in jobs_to_push]
        self._emit(
            status="running",
            current_step="🎬 Đang tạo Voice & Render Video MP4",
            progress=92.0,
            message=f"🎬 Đã đẩy {len(queued_ids)} kịch bản ({', '.join(queued_ids)}) vào hàng đợi tạo Voice & Render MP4!",
        )
        return {
            "started": started,
            "queued_count": len(queued_ids),
            "queued_ids": queued_ids,
            "skipped_no_script": skipped_no_script,
            "skipped_already_mp4": skipped_already_mp4,
            "message": f"Đã đẩy {len(queued_ids)} kịch bản sang tạo Voice & Render Video MP4!",
        }

    def start_run_ideas_async(
        self,
        ma_ids: List[str],
        preferred_acc_id: Optional[str] = None,
        auto_produce_video: bool = True,
        video_settings: Optional[Dict[str, Any]] = None,
        target_part_min: int = 13334,
        ai_provider: str = "chatgpt_web",
        force_rewrite_script: bool = False,
        max_retries: int = 3,
    ) -> bool:
        """
        KIẾN TRÚC LUỒNG ĐÔI SONG SONG (STREAMING PRODUCER–CONSUMER PIPELINE):
        - LUỒNG 1 (AI VIẾT KỊCH BẢN — PRODUCER):
          + Các mã đã có sẵn kịch bản (`already_scripted_ids`) được đẩy NGAY LẬP TỨC vào Hàng Đợi Tạo Voice & Render MP4 từ giây đầu tiên.
          + Các mã chưa có kịch bản (`need_script_ids`) được chia tải đa luồng trên các tài khoản Chrome để AI viết liên tục (tự động Retry tối đa `max_retries = 3` lần).
          + Ngay khi BẤT KỲ 1 kịch bản nào vừa viết xong (`script_clean.txt` + SEO + Thumbnail), nếu `auto_produce_video=True`, hệ thống đẩy NGAY kịch bản đó sang Hàng Đợi Render MP4 rồi luồng AI lập tức viết tiếp kịch bản sau mà không đứng chờ!
        - LUỒNG 2 (VOICE GPU & RENDER VIDEO MP4 — CONSUMER):
          + Hoạt động độc lập song song ở hậu trường: cứ có kịch bản viết xong là tự động tạo Voice GPU & ghép MP4 cuốn chiếu liên tục.
        """
        if isinstance(video_settings, dict) and self.video_pipeline is not None:
            pm_val = video_settings.get("performance_mode") or (video_settings.get("voice_config") or {}).get("performance_mode")
            if pm_val in ("full_100", "work_70") and hasattr(self.video_pipeline, "set_performance_mode"):
                try:
                    self.video_pipeline.set_performance_mode(pm_val, persist=True)
                except Exception:
                    pass
        with self.lock:
            if self.is_running:
                return False
            self.is_running = True
            self.should_stop = False
            self.live_auto_produce_video = bool(auto_produce_video)

        def _worker():
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from .chatgpt_web_client import (
                check_all_web_accounts_status,
                ensure_all_saved_chatgpt_accounts_open,
                sweep_completed_and_idle_tabs_across_all_accounts,
                MAX_THREADS_PER_ACCOUNT,
            )

            try:
                self._sync_projects_disk_state()
                clean_ids = [mid for mid in ma_ids if mid]
                if not clean_ids:
                    return

                # Phân loại: Mã nào ĐÃ CÓ đủ bộ (Kịch bản + SEO + Thumbnail) vs Mã nào CẦN VIẾT / BỔ SUNG / VIẾT LẠI
                already_scripted_ids: List[str] = []
                need_script_ids: List[str] = []
                for mid in clean_ids:
                    if force_rewrite_script:
                        need_script_ids.append(mid)
                        continue
                    has_sc, _, _ = self.has_valid_script_on_disk(mid)
                    has_th, has_s, _ = self.has_thumbnail_and_seo_on_disk(mid)
                    if has_sc and (auto_produce_video or (has_th and has_s)):
                        already_scripted_ids.append(mid)
                    else:
                        need_script_ids.append(mid)

                mode_label_log = "VỪA VIẾT KỊCH BẢN VỪA RENDER MP4 SONG SONG" if auto_produce_video else "CHỈ VIẾT KỊCH BẢN + SEO + THUMBNAIL (KHÔNG RENDER)"
                log_info(
                    "SCRIPT",
                    f"Khởi chạy {len(clean_ids)} dự án [{mode_label_log}{', FORCE_REWRITE=True' if force_rewrite_script else ''}]: "
                    f"Cần xử lý Chrome AI = {len(need_script_ids)}, "
                    f"Đã có sẵn kịch bản = {len(already_scripted_ids)}.",
                )

                # Xử lý đóng gói nhanh (không mở Chrome) cho các mã đã có sẵn kịch bản
                for mid in already_scripted_ids:
                    if self.should_stop:
                        break
                    try:
                        self.run_single_idea_pipeline_sync(
                            ma_id=mid,
                            preferred_acc_id=preferred_acc_id,
                            auto_produce_video=False,
                            video_settings=video_settings,
                            target_part_min=target_part_min,
                            defer_video_handoff=True,
                            force_rewrite_script=False,
                            ai_provider=ai_provider,
                        )
                    except Exception as e_fast:
                        log_error("SCRIPT", f"[{mid}] Lỗi đóng gói kịch bản có sẵn: {e_fast}", project_id=mid)

                # NẾU ĐÃ CÓ SẴN CÁC KỊCH BẢN TRÊN Ổ CỨNG -> ĐẨY NGAY VÀO HÀNG ĐỢI RENDER TỪ GIÂY ĐẦU TIÊN!
                if auto_produce_video and already_scripted_ids and not self.should_stop:
                    only_unren_init = len(clean_ids) > 1
                    res_init_ren = self.start_render_video_for_ideas_async(
                        ma_ids=already_scripted_ids,
                        video_settings=video_settings,
                        only_unrendered=only_unren_init,
                    )
                    if res_init_ren.get("queued_count", 0) > 0:
                        log_info(
                            "VIDEO",
                            f"🎬 [RENDER SONG SONG] Đã đẩy ngay {res_init_ren.get('queued_count')} kịch bản có sẵn vào Hàng Đợi Render MP4 trong lúc AI viết tiếp {len(need_script_ids)} kịch bản mới!",
                        )

                # ==============================================================
                # LUỒNG AI VIẾT KỊCH BẢN ĐA LUỒNG (VIẾT XONG MÃ NÀO -> ĐẨY SANG RENDER NGAY MÃ ĐÓ)
                # ==============================================================
                provider_norm = (ai_provider or "chatgpt_web").strip().lower()
                provider_tag = (
                    "GEMINI 3.8 HIGH (FLASH CAO)"
                    if provider_norm in ("gemini_4_pro", "gemini_3_8_high")
                    else ("KẾT HỢP GEMINI 3.8 HIGH + CHATGPT THUMB" if provider_norm == "hybrid_gemini_chatgpt" else "CHATGPT WEB (MEDIUM)")
                )
                if need_script_ids and not self.should_stop:
                    if provider_norm in ("gemini_4_pro", "gemini_3_8_high", "hybrid_gemini_chatgpt"):
                        st_gem = check_all_gemini_accounts_status().get("accounts", {})
                        logged_accs = [aid for aid, a in st_gem.items() if a.get("logged_in")]
                        if preferred_acc_id and preferred_acc_id in ("acc_1", "acc_2", "acc_3"):
                            active_accs = [preferred_acc_id]
                            max_workers = min(len(need_script_ids), MAX_THREADS_PER_ACCOUNT)
                        else:
                            active_accs = logged_accs if logged_accs else ["acc_1"]
                            max_workers = min(len(need_script_ids), max(1, len(active_accs)) * MAX_THREADS_PER_ACCOUNT)
                    else:
                        if not preferred_acc_id:
                            ensure_all_saved_chatgpt_accounts_open(run_hidden=False)
                        st_all = check_all_web_accounts_status(force_refresh=True).get("accounts", {})
                        logged_accs = [aid for aid, a in st_all.items() if a.get("logged_in")]
                        if preferred_acc_id and preferred_acc_id in st_all:
                            active_accs = [preferred_acc_id]
                            max_workers = min(len(need_script_ids), MAX_THREADS_PER_ACCOUNT)
                        else:
                            active_accs = logged_accs if logged_accs else ["acc_1"]
                            max_workers = min(len(need_script_ids), max(1, len(active_accs)) * MAX_THREADS_PER_ACCOUNT)

                    max_workers = max(1, max_workers)

                    # Nếu đang chọn Chức năng 2: Chạy 70% công suất (work_70) -> Giới hạn cứng tối đa 3 luồng tổng cộng!
                    perf_mode_now = (os.environ.get("STUDIO_PERF_MODE") or "").strip().lower()
                    if not perf_mode_now:
                        try:
                            cfg_p = self.root_dir / "config.json"
                            if cfg_p.exists():
                                perf_mode_now = str(json.loads(cfg_p.read_text(encoding="utf-8")).get("performance_mode", "full_100")).strip().lower()
                        except Exception:
                            perf_mode_now = "full_100"
                    if perf_mode_now == "work_70":
                        max_workers = min(max_workers, 3)

                    if not auto_produce_video:
                        self._emit(
                            status="running",
                            current_step=f"📝 Chỉ viết Kịch bản + SEO + Thumb ({len(need_script_ids)} mã • {provider_tag})",
                            message=(
                                f"📝 [CHẾ ĐỘ CHỈ VIẾT KỊCH BẢN + SEO + THUMB — {provider_tag}] Kích hoạt {len(need_script_ids)} dự án "
                                f"({max_workers} luồng trên {len(active_accs)} Acc: {active_accs}, tự động Retry tối đa {max_retries} lần nếu lỗi)!"
                            ),
                        )
                    else:
                        self._emit(
                            status="running",
                            current_step=f"⚡ Vừa Viết Kịch Bản ({len(need_script_ids)} mã) Vừa Render Video ({provider_tag})",
                            message=(
                                f"⚡ [VỪA VIẾT VỪA RENDER SONG SONG — {provider_tag}] AI đang viết {len(need_script_ids)} kịch bản "
                                f"({max_workers} luồng trên {len(active_accs)} Acc: {active_accs}) — Cứ xong kịch bản nào sẽ tự động tạo Voice & Render MP4 ngay kịch bản đó!"
                            ),
                        )

                    active_slot_lock = threading.Lock()
                    active_slot_state = {"count": 0}
                    cfg_perf_file = self.root_dir / "config.json"

                    def _get_live_perf_mode() -> str:
                        env_pm = (os.environ.get("STUDIO_PERF_MODE") or "").strip().lower()
                        if env_pm in ("work_70", "full_100"):
                            return env_pm
                        try:
                            if cfg_perf_file.exists():
                                m = str(json.loads(cfg_perf_file.read_text(encoding="utf-8")).get("performance_mode", "full_100")).strip().lower()
                                if m in ("work_70", "full_100"):
                                    return m
                        except Exception:
                            pass
                        return "full_100"

                    def _acquire_perf_slot():
                        while not self.should_stop:
                            pm = _get_live_perf_mode()
                            limit_slots = 3 if pm == "work_70" else 9
                            with active_slot_lock:
                                if active_slot_state["count"] < limit_slots:
                                    active_slot_state["count"] += 1
                                    return True
                            time.sleep(1.0)
                        return False

                    def _release_perf_slot():
                        with active_slot_lock:
                            active_slot_state["count"] = max(0, active_slot_state["count"] - 1)

                    def _run_one_with_auto_retry(mid_item: str, acc_item: Optional[str]):
                        if not _acquire_perf_slot():
                            return
                        try:
                            # Tổng số lần chạy = 1 lần chạy chính + tối đa `max_retries` (mặc định 3) lần tự động Retry khi lỗi
                            total_attempts = 1 + max(1, int(max_retries))
                            last_err: Optional[Exception] = None
                            for attempt_idx in range(total_attempts):
                                if self.should_stop:
                                    return
                                is_first_try = (attempt_idx == 0)
                                use_force_rw = bool(force_rewrite_script and is_first_try)
                                try_acc = acc_item
                                if attempt_idx > 0 and not preferred_acc_id and len(active_accs) > 1:
                                    try_acc = active_accs[(attempt_idx) % len(active_accs)] if provider_norm in ("gemini_4_pro", "hybrid_gemini_chatgpt") else None
                                try:
                                    if attempt_idx > 0:
                                        retry_msg = f"🔄 [{mid_item}] Tự động Retry lần {attempt_idx}/{max_retries} (Tiếp tục viết phần còn thiếu)..."
                                        self._update_idea_record(
                                            mid_item,
                                            status="RUNNING",
                                            retry_count=attempt_idx,
                                            current_step=f"🔄 Đang tự động Retry ({attempt_idx}/{max_retries})...",
                                        )
                                        self._emit(
                                            status="running",
                                            current_ma_id=mid_item,
                                            current_step=f"🔄 Tự động Retry ({attempt_idx}/{max_retries})",
                                            message=retry_msg,
                                        )
                                        log_warn("SCRIPT", retry_msg, project_id=mid_item)

                                    res_single = self.run_single_idea_pipeline_sync(
                                        mid_item,
                                        try_acc,
                                        bool(auto_produce_video),       # Viết xong kịch bản nào đẩy sang Render ngay kịch bản đó!
                                        video_settings,
                                        target_part_min,
                                        not bool(auto_produce_video),   # defer_video_handoff=False khi auto_produce_video=True
                                        use_force_rw,                   # chỉ xóa cũ ở lượt đầu nếu người dùng bấm "Viết Lại"
                                        ai_provider,
                                    )
                                    has_sc_ok, _, _ = self.has_valid_script_on_disk(mid_item)
                                    if has_sc_ok:
                                        if auto_produce_video and not (isinstance(res_single, dict) and res_single.get("video_triggered")):
                                            self.start_render_video_for_ideas_async(
                                                ma_ids=[mid_item],
                                                video_settings=video_settings,
                                                only_unrendered=(len(clean_ids) > 1),
                                            )
                                        return
                                    last_err = RuntimeError("Chưa ghép đủ 3 Part kịch bản chuẩn trên ổ cứng.")
                                except Exception as exc_try:
                                    last_err = exc_try
                                    if self.should_stop or "Đã dừng theo yêu cầu" in str(exc_try):
                                        return
                                    # Nếu kịch bản 3 Part đã kịp viết xong trên ổ cứng và auto_produce_video=True -> đẩy luôn vào Render!
                                    has_sc_now, _, _ = self.has_valid_script_on_disk(mid_item)
                                    if has_sc_now and auto_produce_video:
                                        self.start_render_video_for_ideas_async(
                                            ma_ids=[mid_item],
                                            video_settings=video_settings,
                                            only_unrendered=(len(clean_ids) > 1),
                                        )
                                        return
                                    if attempt_idx < max_retries:
                                        wait_s = 3.5 * (attempt_idx + 1)
                                        log_warn(
                                            "SCRIPT",
                                            f"[{mid_item}] ⚠️ Lỗi ở lượt chạy {attempt_idx + 1}: {exc_try} -> Sẽ tự động Retry lần {attempt_idx + 1}/{max_retries} sau {wait_s:.1f}s...",
                                            project_id=mid_item,
                                        )
                                        self._update_idea_record(
                                            mid_item,
                                            status="RUNNING",
                                            retry_count=attempt_idx + 1,
                                            current_step=f"⏳ Chờ tự động Retry lần {attempt_idx + 1}/{max_retries}...",
                                        )
                                        time.sleep(wait_s)
                                    else:
                                        log_error(
                                            "SCRIPT",
                                            f"[{mid_item}] ❌ Đã thử tự động tối đa {max_retries}/{max_retries} lần nhưng vẫn gặp lỗi: {exc_try}",
                                            project_id=mid_item,
                                        )
                                        self._update_idea_record(
                                            mid_item,
                                            status="ERROR",
                                            retry_count=max_retries,
                                            current_step=f"❌ Lỗi sau {max_retries} lần Retry — Bấm '🔁 Viết Lại' để chạy lại ({str(exc_try)[:55]})",
                                        )
                                        raise
                        finally:
                            _release_perf_slot()

                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futs = {}
                        for idx, mid in enumerate(need_script_ids):
                            if self.should_stop:
                                break
                            assigned_acc = (
                                (preferred_acc_id or active_accs[idx % len(active_accs)])
                                if provider_norm in ("gemini_4_pro", "hybrid_gemini_chatgpt")
                                else preferred_acc_id
                            )
                            fut = executor.submit(_run_one_with_auto_retry, mid, assigned_acc)
                            futs[fut] = mid
                            if len(need_script_ids) > 1:
                                time.sleep(1.8 if provider_norm in ("gemini_4_pro", "hybrid_gemini_chatgpt") else 0.55)

                        done_cnt = 0
                        for fut in as_completed(futs):
                            mid_done = futs[fut]
                            done_cnt += 1
                            try:
                                fut.result()
                                suffix_ren = " -> Đã đẩy ngay sang Hàng Đợi Render MP4!" if auto_produce_video else ""
                                self._emit(
                                    message=f"✅ Đã hoàn thành kịch bản [{done_cnt}/{len(need_script_ids)}]: {mid_done}{suffix_ren}"
                                )
                            except Exception as exc:
                                log_error(
                                    "SCRIPT",
                                    f"[{mid_done}] Lỗi luồng kịch bản sau {max_retries} lần Retry ({done_cnt}/{len(need_script_ids)}): {exc}",
                                    project_id=mid_done,
                                )

                    # Dọn dẹp tab Chrome sau khi kết thúc toàn bộ luồng AI để giải phóng RAM cho Voice & Render Video
                    try:
                        sweep_completed_and_idle_tabs_across_all_accounts()
                    except Exception:
                        pass

                # ==============================================================
                # QUÉT VÉT LẦN CUỐI ĐẢM BẢO MỌI KỊCH BẢN ĐÃ XONG ĐỀU ĐƯỢC RENDER MP4
                # ==============================================================
                if auto_produce_video and not self.should_stop:
                    only_unrendered = len(clean_ids) > 1
                    res_render = self.start_render_video_for_ideas_async(
                        ma_ids=clean_ids,
                        video_settings=video_settings,
                        only_unrendered=only_unrendered,
                    )
                    if not res_render.get("started") and only_unrendered and len(clean_ids) == 1:
                        self.start_render_video_for_ideas_async(
                            ma_ids=clean_ids,
                            video_settings=video_settings,
                            only_unrendered=False,
                        )
                    self._emit(
                        status="completed",
                        current_step="✅ Đã viết xong toàn bộ Kịch bản — Hàng đợi Render MP4 đang hoàn tất",
                        progress=100.0,
                        message=(
                            f"🎉 Đã hoàn tất viết Kịch bản và đẩy toàn bộ vào Hàng Đợi Voice & Render MP4!"
                        ),
                    )
                elif not auto_produce_video and not self.should_stop:
                    self._sync_projects_disk_state()
                    self._emit(
                        status="completed",
                        current_step="✅ Hoàn tất Kịch Bản + SEO + Thumbnail (Không Render Video)",
                        progress=100.0,
                        message=(
                            f"🎉 [CHẾ ĐỘ CHỈ VIẾT KỊCH BẢN + SEO + THUMBNAIL] Đã hoàn tất {len(clean_ids)} dự án "
                            f"tại thư mục projects/ (Không tạo Voice & Không Render MP4 — Sẵn sàng Render hoặc Copy sang máy khác)!"
                        ),
                    )
            except Exception as e:
                log_error("SCRIPT", f"Lỗi nghiêm trọng trong start_run_ideas_async: {e}", include_trace=True)
            finally:
                with self.lock:
                    self.is_running = False

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return True

    def stop(self):
        with self.lock:
            self.should_stop = True
        self._emit(status="stopped", message="🛑 Đã gửi tín hiệu dừng dây chuyền viết kịch bản.")

    def get_project_outputs(self, ma_id: str) -> Dict[str, Any]:
        """Đọc toàn bộ kết quả đã lưu của 1 mã dự án (Prompt Step 2, Kết quả Step 2, SEO Pack, Kịch bản, 3 Thumbnail)."""
        ideas = self.load_saved_ideas()
        idea = next((it for it in ideas if it.get("ma_id") == ma_id), {})
        proj_dir = self.projects_dir / ma_id

        def _read_safe(fname: str) -> str:
            p = proj_dir / fname
            if p.exists():
                try:
                    return p.read_text(encoding="utf-8")
                except Exception:
                    pass
            return ""

        step2_prompt = _read_safe("step2_prompt_sent.txt") or _read_safe("step2_prompt_ready.txt")
        if not step2_prompt and idea:
            step2_prompt = build_step2_prompt_from_idea(idea, self.get_step2_template())

        renders_dir = proj_dir / "renders"
        target_open_dir = renders_dir if renders_dir.exists() else proj_dir
        thumb_files = sorted(renders_dir.glob(f"{ma_id}_THUMBNAIL_*.png")) if renders_dir.exists() else []

        return {
            "ma_id": ma_id,
            "idea": idea,
            "project_dir": str(target_open_dir),
            "raw_project_dir": str(proj_dir),
            "step2_prompt": step2_prompt,
            "step2_output": _read_safe("step2_title_thumbnail.txt"),
            "step3_output": _read_safe("step3_architecture.txt"),
            "script_clean": _read_safe("script_clean.txt"),
            "step5_output": _read_safe("step5_audit_report.txt"),
            "seo_pack": _read_safe("00_TIEU_DE_VA_SEO_YOUTUBE.txt") or _read_safe("seo_publish_pack.txt"),
            "thumbnails": [str(p) for p in thumb_files],
        }

    def start_generate_thumbnails_only_async(
        self,
        ma_id: str,
        preferred_acc_id: Optional[str] = None,
        force_regenerate: bool = True,
    ) -> bool:
        """Kích hoạt chạy riêng Bước tạo & đánh giá 3 Thumbnail cho 1 dự án đã có SEO/Step 2."""
        with self.lock:
            if self.is_running:
                return False
            self.is_running = True
            self.should_stop = False
            self.live_auto_produce_video = bool(auto_produce_video)

        def _thumb_worker():
            session = ChatGPTWebSession(project_id=f"{ma_id}_THUMB", acc_id=preferred_acc_id)
            completed_ok = False
            try:
                ideas = self.load_saved_ideas()
                idea = next((it for it in ideas if it.get("ma_id") == ma_id), {}) or {"ma_id": ma_id}
                proj_dir = self.projects_dir / ma_id
                proj_dir.mkdir(parents=True, exist_ok=True)
                renders_dir = proj_dir / "renders"
                renders_dir.mkdir(parents=True, exist_ok=True)

                if force_regenerate:
                    for old_t in renders_dir.glob(f"{ma_id}_THUMBNAIL_*.png"):
                        try:
                            old_t.unlink()
                        except Exception:
                            pass

                step2_out = (proj_dir / "step2_title_thumbnail.txt").read_text(encoding="utf-8") if (proj_dir / "step2_title_thumbnail.txt").exists() else ""
                step6_out = (proj_dir / "seo_publish_pack.txt").read_text(encoding="utf-8") if (proj_dir / "seo_publish_pack.txt").exists() else ""
                locked_title = idea.get("locked_title") or extract_locked_title_from_step2(step2_out, fallback_title=idea.get("draft_title_ja", ma_id))

                self._emit(
                    status="running",
                    current_ma_id=ma_id,
                    current_step="STEP 7 — Đang mở ChatGPT tạo 1 Thumbnail",
                    progress=15.0,
                    message=f"[{ma_id}] 🎨 Đang mở trình duyệt {session.cfg['label']} để tạo & đánh giá 1 Thumbnail (6 dòng chữ)...",
                )
                if not session.open_session_tab():
                    raise RuntimeError(f"Không mở được khung chat trên {session.cfg['label']}.")

                paths = self.generate_and_verify_three_thumbnails_sync(
                    session=session,
                    ma_id=ma_id,
                    locked_title=locked_title,
                    step2_out=step2_out,
                    step6_out=step6_out,
                    idea=idea,
                    proj_dir=proj_dir,
                    renders_dir=renders_dir,
                )
                self._update_idea_record(
                    ma_id,
                    current_step=f"✅ Đã tạo xong {len(paths)}/1 Thumbnail trong thư mục Video",
                )
                self._emit(
                    status="completed",
                    current_step="Hoàn tất Thumbnail",
                    progress=100.0,
                    message=f"[{ma_id}] 🎉 Đã tạo, đánh giá QA và tải về {len(paths)}/1 Thumbnail tại {renders_dir}!",
                )
                completed_ok = True
            except Exception as e:
                self._emit(
                    status="error",
                    current_step="Lỗi tạo Thumbnail",
                    message=f"[{ma_id}] ❌ Lỗi tạo Thumbnail: {str(e)}",
                )
            finally:
                session.close_session_tab(keep_open=not completed_ok)
                with self.lock:
                    self.is_running = False

        threading.Thread(target=_thumb_worker, daemon=True).start()
        return True
