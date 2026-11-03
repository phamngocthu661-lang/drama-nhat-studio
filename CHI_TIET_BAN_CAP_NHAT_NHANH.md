# CHI TIẾT BẢN CẬP NHẬT NHANH TỔNG HỢP — DRAMA NHẬT STUDIO
*(Bản tích hợp đầy đủ toàn bộ các nâng cấp & sửa lỗi mới nhất đến Lần 43 — Ngày 03/11/2026)*

---

## 🔥 MỚI NHẤT TRONG BẢN CẬP NHẬT LẦN 33 → 43 (03/11/2026)
1. **Giao diện Workstation Studio mới (`Industrial Cyber Deck`) + Chuẩn 4 Card Xuất Video & Giả Lập Bố Cục 5 Lớp nguyên bản**:
   - Tích hợp 4 Tab chuyên biệt (`Trạm AI ADAS Tự Động`, `Bàn Dựng Video Chính & Preview 5 Lớp`, `Phòng Thu Voice GPU & Kho Stock`, `Chẩn Đoán GPU/CUDA & Terminal Logs`) kèm bộ lọc dự án (`Tất cả / ⏳ Chưa xong / ✅ Đã xong`) hiển thị 1 dòng siêu gọn.
   - Giữ nguyên chuẩn 4 Card ở phần Xuất Video và khôi phục 100% khung **Giả Lập Bố Cục 5 Lớp (`Live Preview`)** đúng chuẩn engine FFmpeg.
2. **Nâng cấp Tải Video Stock Chống Trùng Tuyệt Đối 100% (`backend/stock_manager.py`)**:
   - **Tải link nào Update & Khóa ngay lập tức link đó** (`record_used_yt_link(..., sync_cloud=True)`) vào `used_stock_links.json`, `STOOK/used_stock_links.json`, `stock_inventory.json` và đẩy thẳng lên **Cloud Note Online (`https://rentry.co/nhat-drama-stock-9f8a7b6c`)**.
   - Đồng bộ 2 chiều đầy đủ cả mã `PX_*` (Pexels), `PB_*` (Pixabay), YouTube ID và URL gốc từ `/raw` Markdown trên Cloud Note.
3. **Tách riêng Cổng & Profile Chrome cho Gemini (`9225–9227`) & Khóa Model `3.8 High` (`Flash Cao`)**:
   - ChatGPT Web dùng cổng `9222–9224` (`BROWSER_PROFILE_1..3`), Gemini Web dùng cổng riêng `9225–9227` (`GEMINI_PROFILE_1..3`), không bao giờ đụng cổng hay đóng nhầm tab của nhau.
4. **Ghi File Nguyên Tử (`Atomic Write`) & Bảo Vệ 100% Danh Sách Kịch Bản Chờ Khi Chạy Đa Luồng SLL (`300+ kịch bản`)**:
   - Ghi `saved_ideas.json` và `saved_ideas_backup.json` nguyên tử qua `.json.tmp` + `os.replace`, đảm bảo chạy 9 luồng song song (3 tài khoản ChatGPT) suốt hàng trăm kịch bản không bao giờ bị mất danh sách chờ.

---

## I. HƯỚNG DẪN CẬP NHẬT NHANH TRONG 5 GIÂY (KHÔNG MẤT KỊCH BẢN & KEY BẢN QUYỀN)

Bạn có thể chọn **1 trong 2 cách** dưới đây (cả 2 cách đều **giữ nguyên 100%** các kịch bản đã tạo `P01..P20` trong `projects/`, `saved_ideas.json`, Key bản quyền `license.json` và tài khoản ChatGPT trong `BROWSER_PROFILE`):

### Cách 1: Giải nén đè trực tiếp
1. Tắt cửa sổ ứng dụng `Drama_Nhat_Studio` đang mở.
2. Giải nén toàn bộ file trong `Drama_Nhat_Studio_Ban_Update_Nhanh.zip` **đè trực tiếp (Replace the files in the destination)** vào thư mục đang cài ứng dụng của bạn.
3. Bấm đúp vào **`Cap_Nhat_Nhanh.bat`** (hoặc `Drama_Nhat_Studio.exe`) để mở lại ứng dụng.

### Cách 2: Giải nén ra thư mục con rồi bấm `Cap_Nhat_Nhanh.bat`
1. Nếu bạn bấm chuột phải vào `Drama_Nhat_Studio_Ban_Update_Nhanh.zip` $\rightarrow$ chọn **Extract All...** (ra thư mục `Drama_Nhat_Studio_Ban_Update_Nhanh\`).
2. Bạn chỉ cần mở thư mục vừa giải nén và **bấm đúp vào file `Cap_Nhat_Nhanh.bat`**:
   - Công cụ sẽ **tự động tắt tiến trình Voice CPU cũ**, **tự động chép toàn bộ file mới vào đúng thư mục chính** của bạn (cả gốc lẫn `app/`) và **tự động bật lại ứng dụng**!

---

## II. TỔNG HỢP CHI TIẾT 7 HẠNG MỤC NÂNG CẤP TRONG BẢN UPDATE NÀY

### 1. Bật Sẵn Server Voice GPU Ngay Khi Mở Ứng Dụng & Chọn 1 Trong 2 Server GPU (`backend/voicevox_service.py`, `backend/pipeline.py`, `frontend/index.html`, `frontend/app.js`)
- **Khắc phục triệt để lỗi tạo Voice bằng CPU chậm chạp**:
  - Tự động tắt tiến trình `run.exe` chế độ CPU cũ (nếu còn chạy ngầm) và khởi động cụm **2 Worker GPU (`--use_gpu` trên cổng `50021` & `50022`)** ngay giây đầu tiên khi mở ứng dụng.
  - Tự động nạp sẵn (`warmup_speaker`) model giọng **`Drama` (`speaker_id = 13`, `speedScale = 0.97`, `pitchScale = -0.02`)** lên VRAM GPU để câu đầu tiên không bị trễ.
  - Tốc độ tạo âm thanh trên GPU đạt **gấp ~30 lần thời lượng thực** (kịch bản 45.000 chữ tạo xong âm thanh chỉ trong ~35–45 giây).
- **Cho phép chọn bật 1 trong 2 Server Voice GPU ngay trên giao diện**:
  - `🟢 Server 1: VOICEVOX DirectML GPU (2 Cổng 50021/50022 • Tốc độ 30x)` — Mặc định khuyên dùng.
  - `🔵 Server 2: OmniVoice CUDA GPU (Zero-Shot Clone từ file mẫu .wav)`.

### 2. Nhận Diện 100% Giọng Đọc Mới Khi Ấn Render Video (`backend/pipeline.py`, `backend/voicevox_service.py`, `frontend/app.js`)
- **Khắc phục lỗi chọn Voice mới nhưng khi ấn Render vẫn chậm hoặc vẫn ra giọng cũ**:
  - Khi bấm bất kỳ nút **`🎬 Render MP4`** hay **`▶️ Chạy Đa Luồng`**, giao diện đính kèm trực tiếp cấu hình `voice_config` đang chọn trên màn hình gửi xuống Backend.
  - Hệ thống kiểm tra chữ ký giọng đọc (`assets/voice_signature.json`). Nếu bạn vừa đổi giọng hoặc chỉnh `Speed / Pitch / Intonation / Pause`, hệ thống tự động xóa `master_voice.wav` cũ và tổng hợp lại ngay bằng giọng mới trên Server GPU đang chọn.
  - **Cấm tuyệt đối việc tự động rơi ngầm về OmniVoice CPU chậm chạp** khi đang chọn Server 1 (`VOICEVOX GPU`).

### 3. Tự Động Cân Đối Đa Luồng Render Tối Đa ~90% GPU & CPU (`backend/pipeline.py`, `backend/renderer.py`)
- **Bộ điều phối tài nguyên động (`HardwareResourceBalancer`)**:
  - Đo tải thời gian thực của `% GPU` (Core + NVENC Encoder + VRAM) và `% CPU` + `% RAM`, hiển thị trực tiếp trên thanh trạng thái: **`⚡ Tự cân đối 90%: GPU X% • CPU Y%`**.
  - Khi bạn bấm Render nhiều video cùng lúc, ứng dụng **không chờ đợi tuần tự từng video** mà tự động mở **Pool Đa Luồng (tối đa 3 video chạy song song)**:
    - Trong khi Video 1 đang ghép hình bằng `FFmpeg h264_nvenc -preset p2`, Video 2 & Video 3 lập tức được tạo sẵn Voice GPU.
    - Nếu tải GPU và CPU còn dưới ngưỡng `88%–90%`, hệ thống tự động cho phép chạy song song nhiều luồng FFmpeg NVENC cùng lúc để tận dụng tối đa 90% sức mạnh phần cứng.

### 4. Khắc Phục Triệt Để Lỗi Kịch Bản Thiếu Part Vẫn Báo Đạt (`P16 = 15,848 chữ`, `P17 = 32,684 chữ`) & Nút `▶️ Viết Tiếp` (`backend/adas_script_engine.py`, `frontend/app.js`, `frontend/style.css`)
- **Nguyên nhân đã xử lý**: Trước đây cả 3 Part A, B, C viết chung trong 1 đoạn chat khiến đoạn chat bị đầy bộ nhớ sau Part A (`P16`) hoặc sau Part B (`P17`), làm Part tiếp theo trả về `0 chữ` nhưng vẫn bị ghép vào `script_clean.txt`.
- **Giải pháp mới**:
  1. **Tách riêng 3 Đoạn Chat Độc Lập cho từng Part (`Chat #3A` cho `PART A`, `Chat #3B` cho `PART B`, `Chat #3C` cho `PART C`)** kèm `Story Bible` + 400 chữ cuối của Part liền trước.
  2. **Cơ chế Mở Đoạn Chat Cứu Hộ tự động**: Nếu bất kỳ lượt viết nào bị đứng chữ khi chưa đủ độ dài, hệ thống tự động mở đoạn chat mới nạp đoạn đang viết dở vào để viết tiếp cho đến khi đủ chữ.
  3. **Chốt chặn 3 Part nghiêm ngặt**: Bắt buộc đủ cả 3 file `part_a.txt`, `part_b.txt`, `part_c.txt` (`>= 9,500 chữ thuần/Part` và tổng `>= 35,000 chữ thuần`) mới được xuất `script_clean.txt` và báo `📝 Xong Kịch bản`.
  4. **Tự động sửa trạng thái cho `P16` và `P17` ngay khi bạn cập nhật xong**:
     - Hệ thống giữ nguyên 100% `part_a.txt` của `P16` (`15,848 chữ`) và `part_a.txt + part_b.txt` của `P17` (`32,684 chữ`), tự động đổi nhãn sang màu cam:
       - `P16`: **`⚠️ Thiếu Part B, C (1/3 Part • 15,848 chữ)`** kèm nút **`▶️ Viết Tiếp`**
       - `P17`: **`⚠️ Thiếu Part C (2/3 Part • 32,684 chữ)`** kèm nút **`▶️ Viết Tiếp`**
     - Bạn chỉ cần bấm **`▶️ Viết Tiếp`**, ứng dụng sẽ viết bù đúng `Part B, C` còn thiếu rồi chạy lại Audit & SEO cho đủ bộ ~48.000 chữ!
  5. **Sửa lỗi giao diện**: Nhãn trạng thái được cố định khung co giãn (`flex-shrink: 0; overflow: hidden;`), tuyệt đối không còn đè lên nút `🎬 Render MP4`.

### 5. Khóa Cố Định Model Viết Kịch Bản Ở Chế Độ `Thinking effort: Medium` (`backend/chatgpt_web_client.py`)
- Cập nhật bộ điều khiển tương thích 100% với **Thanh trượt 3 nấc mới (`Power Slider`: `0 = Instant`, `1 = Medium`, `2 = High`)** của ChatGPT Web (`GPT-6` / `GPT-5.6`).
- Tự động kiểm tra và khóa cố định ở mức **`Thinking effort: Medium`** (`aria-valuenow="1"`) tại cả 3 thời điểm:
  1. Ngay khi mở Tab Chrome mới,
  2. Ngay khi chuyển sang đoạn chat mới độc lập,
  3. Ngay trước khi dán và gửi bất kỳ câu lệnh Prompt nào.

### 6. Mỗi Kịch Bản Chỉ Tạo Đúng 1 Thumbnail Duy Nhất (`{MA_ID}_THUMBNAIL_1.png`) (`backend/adas_script_engine.py`, `adas_skills/06_seo_publish_pack/SKILL.md`, `frontend/app.js`)
- Tại `STEP 6` và `STEP 7`: Chỉ yêu cầu và tạo **1 ảnh Thumbnail Master duy nhất (`{MA_ID}_THUMBNAIL_1.png`)** chuẩn Full HD `1920x1080` (`16:9`, 6 dòng chữ Nhật chuẩn) cho mỗi kịch bản thay vì 3 ảnh như trước, giúp tiết kiệm 2/3 thời gian tạo ảnh.
- Đổi nút trên dòng dự án từ `🖼️ 3 Thumb` thành **`🖼️ Thumb`**.

### 7. Bảo Toàn Kịch Bản Khi Update & Chặn Vĩnh Viễn Tiêu Đề Đã Xóa (`backend/adas_script_engine.py`, `ADMIN_KEYGEN/Dong_Goi_Bo_Cai_Khach_Hang.py`)
- Không bao giờ đóng gói `saved_ideas.json` hay `settings.json` vào trong file ZIP để không ghi đè dữ liệu của bạn.
- Bổ sung nút **`🔄 Khôi Phục Kịch Bản Cũ`** quét toàn bộ thư mục `projects/` để khôi phục ngay các kịch bản đã viết.
- Lưu danh sách các tiêu đề nháp đã xóa vào `deleted_ideas.json` để khi tắt đi bật lại ứng dụng, các tiêu đề đã xóa biến mất vĩnh viễn, không bao giờ tự load lại.

---

## III. DANH SÁCH ĐẦY ĐỦ CÁC FILE CÓ TRONG BẢN UPDATE NHANH NÀY
- `Cap_Nhat_Nhanh.bat` *(Công cụ tự động cập nhật 1-Click & khởi động lại bằng GPU)*
- `Drama_Nhat_Studio.exe`, `Chay_App.bat`, `Cai_Dat_May_Moi.bat`
- `main.py` & `app/main.py`
- `install_setup.py` & `app/install_setup.py`
- `requirements.txt` & `app/requirements.txt`
- `voice_engine_config.json` & `app/voice_engine_config.json` *(Cấu hình mặc định Giọng `Drama` Speed `0.97x` + `voicevox_gpu` + Cân đối `90%` GPU/CPU)*
- Toàn bộ thư mục `backend/` & `app/backend/` (`adas_script_engine.py`, `chatgpt_web_client.py`, `voicevox_service.py`, `pipeline.py`, `renderer.py`, `server.py`, `logger_service.py`, `license_manager.py`, `stock_manager.py`, `sync_checker.py`, `voice_service.py`)
- Toàn bộ thư mục `frontend/` & `app/frontend/` (`index.html`, `app.js`, `style.css`)
- Toàn bộ thư mục `adas_skills/` & `app/adas_skills/` *(Đã cập nhật `06_seo_publish_pack` tạo 1 Thumbnail duy nhất)*
- Toàn bộ thư mục `assets/voices/` *(File mẫu âm thanh `Drama.wav`, `Drama.txt`, `preview_Drama.wav` tốc độ `0.97x`)*
- Tài liệu: `CHI_TIET_BAN_CAP_NHAT_NHANH.txt`, `CHI_TIET_BAN_CAP_NHAT_NHANH.md`, `QUY_TRINH_HOAT_DONG.md`, `TIEN_DO_CODE.md`
