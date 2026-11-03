# HƯỚNG DẪN CHUYỂN ỨNG DỤNG SANG MÁY TÍNH KHÁC

Ứng dụng **Drama Nhật Studio** được thiết kế độc lập (Self-contained). Bạn có thể copy toàn bộ thư mục `D:\NHAT_DRAMA` sang máy tính khác (hoặc copy vào ổ cứng di động / USB).

---

## 🖥️ 1. YÊU CẦU CẤU HÌNH TRÊN MÁY TÍNH MỚI

| Thành phần | Máy có Card NVIDIA (Khuyên dùng) | Máy chỉ có CPU (Máy văn phòng / Laptop) |
| :--- | :--- | :--- |
| **Hệ điều hành** | Windows 10 hoặc Windows 11 (64-bit) | Windows 10 hoặc Windows 11 (64-bit) |
| **Phần cứng GPU** | Card đồ họa NVIDIA (GTX 1060, 1660, RTX 2060, 3060, 4060, 4070...) | CPU Core i5 / i7 / i9 hoặc AMD Ryzen |
| **Phần mềm bắt buộc** | 1. Python 3.10 hoặc 3.11<br>2. FFmpeg (thêm vào PATH) | 1. Python 3.10 hoặc 3.11<br>2. FFmpeg (thêm vào PATH) |
| **Tốc độ tạo Voice** | Siêu tốc (~20-30 phút cho video 45p) | Chậm hơn một chút do xử lý trên CPU |

---

## ⚙️ 2. ĐÓNG GÓI & CÀI ĐẶT KHI SANG MÁY MỚI (CHỈ LÀM 1 LẦN)

0. **Đóng gói Bộ Cài Khách Hàng chuẩn (Dành cho Admin):**
   - Nhấp đúp vào **`ADMIN_KEYGEN\Dong_Goi_Bo_Cai_Khach_Hang.bat`** để tự động xuất ra file **`D:\Drama_Nhat_Studio_Bo_Cai_Khach_Hang.zip`** (~106 MB, tương thích 100% với `Extract All...` của Windows Explorer, đã lọc sạch Key Admin, Cookie Chrome và video nháp).
1. **Giải nén `Drama_Nhat_Studio_Bo_Cai_Khach_Hang.zip`** sang máy mới (tốt nhất đặt ở ổ `D:\Drama_Nhat_Studio`).
2. **Cài đặt Python & FFmpeg** (nếu máy mới chưa có):
   - Python: Tải tại [python.org](https://www.python.org/downloads/) (Nhớ tích chọn `"Add python.exe to PATH"` khi cài đặt).
   - FFmpeg: Tải bản Portable giải nén và thêm vào biến môi trường PATH.
3. **Chạy file cài đặt tự động 1-Click**:
   - Nhấp đúp vào file 👉 **`Cai_Dat_May_Moi.bat`**
   - File sẽ tự động cài các thư viện PyTorch, FastAPI, PyWebView, yt-dlp.
4. **Bắt đầu sử dụng**:
   - Nhấp đúp vào 👉 **`Chay_App.bat`** để mở ứng dụng Desktop!

---

## 🗑️ 3. CƠ CHẾ DÙNG 2 LẦN MỖI STOCK + TỰ ĐỘNG TẢI BÙ ĐỦ 10 TIẾNG & DỌN DẸP

- **Dùng 2 lần mỗi video stock (Nhân đôi thời lượng & số lượng video):**
  - **Lần 1/2:** Phát bản **Gốc 100%** (làm chậm `0.5x` kéo dài 30p thành 60p).
  - **Lần 2/2:** Tự động **Lật ngang (`hflip`) + Zoom `110%`** (làm chậm `0.5x` tạo thêm 60p hoàn toàn khác biệt).
- **Tự động tải sẵn & tải bù đủ 10 tiếng Stock (Khi sang máy mới hoặc khi vơi kho):**
  - Khi copy sang máy mới (thậm chí không cần copy theo 12GB video trong thư mục `STOOK` để nhẹ USB), bạn chỉ cần bấm nút **`⚡ Tải Sẵn Đủ 10 Tiếng Stock Ngay`** (hoặc bấm chạy sản xuất luôn).
  - Hệ thống sẽ tự động kiểm tra kho: nếu thiếu (ví dụ kho đang `0 tiếng`, hoặc có `9 tiếng` thiếu `1 tiếng` so với mức `10 tiếng`), máy sẽ **tự động tìm video 4K thiên nhiên mới trên YouTube** (đối chiếu chống trùng tuyệt đối qua `used_stock_links.json`), tải đúng phần thời lượng còn thiếu và cắt thành các part 30 phút cho đủ `10 tiếng` rồi mới bắt đầu chạy sản xuất video!
- **Tự động xóa sau khi dùng đủ 2/2 lần:** Khi file stock đã dùng xong cả 2 lần (Gốc + Lật & Zoom 110%), file `.mp4` gốc sẽ tự động được xóa vĩnh viễn khỏi ổ cứng để giải phóng dung lượng, trong khi lịch sử vẫn được khóa vĩnh viễn trong `used_stocks_history.json` và `used_stock_links.json`.

