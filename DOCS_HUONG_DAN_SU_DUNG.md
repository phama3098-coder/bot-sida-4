# HƯỚNG DẪN CÀI ĐẶT VÀ SỬ DỤNG PHẦN MỀM VIETPHOTOBOOTH

Chào mừng bạn đến với **VietPhotoBooth** — phần mềm Photobooth chuyên nghiệp dành riêng cho hệ điều hành **Windows 10 và Windows 11 (64-bit)**.

Phần mềm được thiết kế tối ưu cho:
- Tiệc cưới, sinh nhật, thôi nôi.
- Sự kiện doanh nghiệp, hội nghị, triển lãm.
- Kiosk booth chụp ảnh tự động.
- In ảnh lấy liền chuẩn màu trên máy in nhiệt thăng hoa (DNP DS-RX1HS, Citizen, HiTi...).
- Chia sẻ ảnh tốc độ cao qua mã QR trong mạng nội bộ (LAN) không cần Internet.

---

## 1. YÊU CẦU HỆ THỐNG VÀ CÀI ĐẶT

### 1.1. Cấu hình phần cứng & phần mềm đề xuất
- **Hệ điều hành**: Windows 10 64-bit hoặc Windows 11 64-bit.
- **Bộ vi xử lý (CPU)**: Intel Core i3 thế hệ 6 trở lên hoặc AMD Ryzen 3 trở lên.
- **Bộ nhớ RAM**: Tối thiểu 4 GB (khuyến nghị 8 GB trở lên).
- **Ổ cứng**: Còn trống tối thiểu 5 GB (khuyến nghị dùng ổ SSD).
- **Màn hình**: Hỗ trợ cảm ứng (Touchscreen) với độ phân giải tối thiểu 1920x1080 (Full HD).
- **Cổng kết nối**: Cổng USB 3.0 / USB-C tốc độ cao để cắm máy ảnh DSLR/Mirrorless và máy in.

### 1.2. Hướng dẫn cài đặt bằng file Setup
1. Tải bộ cài `VietPhotoBooth-Setup.exe` từ thư mục:
   `C:\Users\Admin\Documents\photobooth\dist_installer\VietPhotoBooth-Setup.exe`
2. Nhấp đúp chuột vào file `VietPhotoBooth-Setup.exe`.
3. Trình cài đặt sẽ tự động:
   - Cài đặt toàn bộ ứng dụng vào thư mục của người dùng (`%LOCALAPPDATA%\Programs\VietPhotoBooth`).
   - Không yêu cầu quyền Administrator nếu cài cho tài khoản cá nhân.
   - Tạo biểu tượng **VietPhotoBooth** trên màn hình Desktop.
   - Tạo lối tắt trong Start Menu.
4. Tích chọn **"Khởi động VietPhotoBooth ngay bây giờ"** và bấm **Hoàn tất (Finish)**.
5. Phần mềm sẽ tự động khởi chạy và mở giao diện cảm ứng Kiosk trên trình duyệt mặc định tại địa chỉ: `http://localhost:8080/`.

---

## 2. QUY TRÌNH VẬN HÀNH DÀNH CHO KHÁCH HÀNG

Giao diện được thiết kế 100% bằng tiếng Việt với các nút bấm to, rõ ràng, cảm ứng siêu nhạy:

### Bước 1: Màn hình chờ (Idle)
- Khách nhìn thấy thông điệp chào mừng, tên cặp đôi hoặc tên sự kiện.
- Khách nhìn thấy khung ngắm camera trực tiếp (Live View) để chỉnh trang trang phục, đầu tóc.
- Khách chạm tay vào nút tròn lớn: **📸 BẮT ĐẦU CHỤP ẢNH**.

### Bước 2: Đếm ngược và tạo dáng (Countdown)
- Phần mềm kiểm tra độ sẵn sàng của máy ảnh.
- Đồng hồ đếm ngược hiển thị số lớn (5, 4, 3, 2, 1) kèm âm thanh nhắc nhở.
- Máy ảnh nháy sáng (Flash) chụp ảnh số 1.
- Nghỉ 2 giây để khách đổi dáng.
- Tiếp tục đếm ngược và chụp các kiểu tiếp theo (tổng cộng 3 hoặc 4 kiểu tùy cài đặt).

### Bước 3: Xem trước và thành phẩm (Preview)
- Sau khi chụp xong kiểu cuối cùng, hệ thống tự động ghép loạt ảnh vào khung ảnh (Template 2x6 hoặc 4x6) với độ phân giải chuẩn 300 DPI.
- Trên màn hình xuất hiện:
  - Bản xem trước của bức ảnh hoàn chỉnh.
  - Mã QR để tải ảnh về điện thoại.
  - Tùy chọn in ảnh: Chọn 1 bản hoặc 2 bản.

### Bước 4: In ảnh và Quét mã QR
- **In ảnh**: Chạm vào nút màu xanh **"IN ẢNH NGAY"**. Lệnh in được chuyển tức thì vào Windows Print Spooler. Máy in ảnh nhiệt (ví dụ DNP DS-RX1HS) sẽ in ra trong vòng 12-15 giây.
- **Quét QR**: Khách dùng camera điện thoại quét mã QR hiển thị góc phải màn hình để tải ngay ảnh chất lượng cao về điện thoại mà không cần 4G hay Internet.
- Chạm nút **"✅ Hoàn Tất"** để quay về màn hình chờ đón lượt khách tiếp theo.

---

## 3. HƯỚNG DẪN QUẢN TRỊ VIÊN (ADMIN DASHBOARD)

Tại màn hình chờ, chạm vào nút **⚙️ Quản Trị** ở góc trên bên phải.
- Màn hình hiển thị bàn phím số cảm ứng yêu cầu mã PIN.
- Mã PIN mặc định ban đầu là: **`1234`**.

Bảng quản trị gồm 10 phân hệ chuyên sâu:

### 1. Tổng Quan (Overview)
- Xem nhanh tình trạng kết nối máy ảnh, máy in, tên sự kiện đang hoạt động và dung lượng ổ cứng còn trống.

### 2. Cài Đặt Máy Ảnh (Camera Settings)
- **Chọn nguồn máy ảnh**:
  - `Camera Simulator`: Bộ giả lập phần mềm (dùng khi chạy thử hoặc dựng sự kiện trước khi cắm máy ảnh thật).
  - `DirectShow UVC Webcam`: Dành cho Webcam USB (Logitech C920, Brio...) hoặc thẻ thu hình Clean HDMI (Elgato Cam Link 4K).
  - `digiCamControl DSLR`: Dành cho máy ảnh chuyên nghiệp DSLR/Mirrorless Canon, Nikon, Sony.
- Xem khung ngắm Live View thực tế để căn chỉnh góc máy trong booth.

### 3. Kiểm Tra Tương Thích (Compatibility Matrix)
- Tra cứu danh sách hơn 30 model máy ảnh phổ biến trên thị trường.
- Xem rõ model nào đã kiểm thử thực tế, model nào cần driver hoặc hạn chế đã biết.

### 4. Máy In & Hàng Đợi (Printer & Queue)
- Liệt kê toàn bộ máy in Windows.
- Chọn máy in sự kiện và khổ giấy (4x6 inch hoặc 2x6 inch).
- Nút **"In Thử (Test Card)"**: In một thẻ kiểm tra chuẩn 300 DPI có thước căn lề, dải màu sRGB và đường cắt 2x6 inch để kiểm tra độ sắc nét và dao cắt của máy in.
- Bảng hàng đợi in (Print Queue): Hiển thị trạng thái từng lệnh in (Đang chờ, Đang gửi tới Spooler, Đã tiếp nhận, Hoàn thành, Lỗi). Quản trị viên có thể bấm "Thử lại" hoặc "Hủy" lệnh in bị kẹt.

### 5. Khung Ảnh (Templates)
- Chọn mẫu khung ảnh mặc định:
  - `Dải Photobooth 2x6 inch (3 Ảnh)`: Dải dọc 600x1800 px.
  - `Dải Photobooth 2x6 inch (4 Ảnh)`: Dải dọc 600x1800 px.
  - `Ghép Đôi 2 Dải 2x6 trên Khổ 4x6 (3 Ảnh)`: Chuẩn in 1200x1800 px có đường cắt đôi dành cho máy DNP DS-RX1HS.
  - `Khổ 4x6 Lưới 4 Ảnh (2x2 Grid)`.
  - `Khổ 4x6 Ngang (Landscape) 3 Ảnh`.

### 6. Quản Lý Sự Kiện (Events)
- **Tạo sự kiện mới**: Nhập tên sự kiện (ví dụ `DamCuoi_MinhLinh_2026`). Phần mềm tự động tạo cấu trúc 5 thư mục chuẩn:
  - `Originals/`: Chứa toàn bộ file ảnh gốc chưa qua chỉnh sửa.
  - `Final/`: Chứa file ảnh thành phẩm độ phân giải cao 300 DPI.
  - `Thumbnails/`: Chứa ảnh thu nhỏ để tải thư viện nhanh.
  - `Templates/`: Mẫu khung riêng của sự kiện.
  - `Logs/`: Nhật ký hoạt động của sự kiện.
- **Xuất ZIP**: Cho phép nén toàn bộ ảnh sự kiện thành 1 file ZIP duy nhất để bàn giao ngay cho khách hàng hoặc cô dâu chú rể.

### 7. Thư Viện Ảnh (Photo Library)
- Duyệt toàn bộ ảnh đã chụp của sự kiện.
- Bấm vào ảnh để xem kích thước lớn hoặc tải file gốc về máy.

### 8. QR & Mạng LAN (Local Sharing)
- Hiển thị địa chỉ IP nội bộ của máy chủ Photobooth (ví dụ `192.168.1.150:8080`).
- Danh sách các token chia sẻ ảnh đang hoạt động.
- Nút **"Thu hồi"**: Hủy ngay quyền truy cập của một bức ảnh nếu cần bảo mật.

### 9. Cài Đặt Hệ Thống (Settings)
- Đổi tiêu đề sự kiện, phụ đề, ngày tháng.
- Cấu hình thời gian đếm ngược: 3 giây, 5 giây hoặc 10 giây.
- Cấu hình số kiểu ảnh mỗi phiên: 3 hoặc 4 kiểu.
- Cấu hình thời gian nghỉ giữa các kiểu: 1 đến 5 giây.
- Đổi mã PIN quản trị mới.

### 10. Nhật Ký & Chẩn Đoán (Diagnostics)
- Xem log hệ thống thời gian thực từ file `vietphotobooth.log` để phát hiện lỗi camera, máy in hoặc sự cố mạng.
