# HƯỚNG DẪN CẤU HÌNH MÁY IN ẢNH CHUYÊN NGHIỆP TRÊN WINDOWS

Hệ thống in ấn trong **VietPhotoBooth** được xây dựng trực tiếp trên nền tảng **Windows Print Spooler** chuẩn của Microsoft (`win32print`), hoàn toàn không phụ thuộc vào hệ thống CUPS của Linux, đảm bảo khả năng tương thích 100% với driver chính hãng và máy in ảnh nhiệt thăng hoa (Dye-Sublimation Photo Printers).

---

## 1. TỔNG QUAN VỀ CÔNG NGHỆ IN ẢNH PHOTOBOOTH

Trong ngành Photobooth thương mại, có hai định dạng in phổ biến nhất:
1. **Dải ảnh 2x6 inch (5 x 15 cm)**: Định dạng dải ảnh cổ điển với 3 hoặc 4 kiểu ảnh xếp dọc, thường có viền trắng, logo và thông điệp kỷ niệm.
2. **Khổ bưu thiếp 4x6 inch (10 x 15 cm)**: Định dạng ảnh bưu thiếp tiêu chuẩn (1200 x 1800 px @ 300 DPI) chứa 1, 2, 3 hoặc 4 kiểu ảnh.

### Cơ chế Cắt Tự Động (2-inch Cut) trên máy in nhiệt DNP DS-RX1HS
Máy in DNP DS-RX1HS (và Citizen CY-02, HiTi P525L) nạp cuộn giấy khổ 4x6 inch. Khi người dùng muốn có dải 2x6 inch:
- Phần mềm **VietPhotoBooth** sẽ xuất ra một bức ảnh khổ 4x6 inch (1200 x 1800 pixel) chứa **hai dải 2x6 giống hệt nhau đặt cạnh nhau** (Trái và Phải).
- Khi lệnh in được gửi tới máy in có bật tùy chọn **"2-inch Cut"**, máy in sẽ in toàn bộ tờ 4x6 rồi dùng dao cắt cơ học tích hợp tự động chém đôi tờ giấy theo chiều dọc.
- Kết quả: **Khách hàng nhận được 2 dải ảnh 2x6 riêng biệt chỉ trong một lần in duy nhất (khoảng 12.4 giây)!**

---

## 2. HƯỚNG DẪN CẤU HÌNH DRIVER MÁY IN DNP DS-RX1HS

### Bước 1: Cài đặt Driver chính hãng DNP
1. Tải bộ driver chính hãng DNP DS-RX1 / DS-RX1HS dành cho Windows 10/11 64-bit từ trang chủ DNP Imagingcomm.
2. Chạy file cài đặt `Setup.exe` theo hướng dẫn của nhà sản xuất.
3. Cắm cáp USB của máy in vào cổng USB 3.0 trên máy tính và bật nguồn máy in.
4. Kiểm tra trong **Windows Settings -> Bluetooth & devices -> Printers & scanners**, máy in **"DS-RX1"** (hoặc **"DNP DS-RX1HS"**) phải hiển thị trạng thái **"Ready" (Sẵn sàng)**.

### Bước 2: Bật tính năng Cắt 2 dải (2-inch Cut) trong Windows
1. Nhấp vào máy in **DS-RX1** -> Chọn **Printing preferences** (Tùy chọn in).
2. Tại tab **Layout / Paper**:
   - **Paper Size**: Chọn khổ giấy `PR (4x6)` (102 x 152 mm).
   - **Orientation**: Chọn `Portrait` (Khổ dọc).
3. Chuyển sang tab **Options** (hoặc mục **Cut Settings**):
   - Tìm mục **Cut Options** (Tùy chọn cắt).
   - Tích chọn: **`2-inch cut (51x152mm x 2)`** (hoặc `2x6 Cut`).
4. Tại mục **Print Quality**:
   - Chọn **High Speed** (300 x 300 DPI) để thời gian in mỗi ảnh chỉ mất khoảng 12.4 giây.
5. Bấm **Apply** -> **OK** để lưu cấu hình vĩnh viễn.

---

## 3. CẤU HÌNH MÁY IN TRONG VIETPHOTOBOOTH

1. Mở VietPhotoBooth, chạm vào nút **⚙️ Quản Trị** (Mã PIN: `1234`).
2. Vào mục **🖨️ Máy In & Hàng Đợi**.
3. Tại danh sách thả xuống **Máy In Windows Hiện Có**:
   - Chọn máy in **"DS-RX1"** (hoặc máy in bạn đang sử dụng).
   - Khổ giấy: Chọn **`4x6 inch`**.
4. Bấm **"Lưu Cấu Hình Máy In"**.
5. Bấm nút **"In Thử (Test Card)"**:
   - Hệ thống sẽ render một thẻ kiểm tra chuẩn 1200x1800 px gồm thước đo căn lề, dải màu sRGB và đường chỉ cắt 2x6 ở giữa.
   - Kiểm tra tờ giấy in ra: Ảnh phải sắc nét, màu sắc tươi tắn, không bị méo tỷ lệ và dao cắt máy in chém đôi tờ giấy thành hai nửa bằng nhau hoàn hảo.

---

## 4. QUY TRÌNH XỬ LÝ SỰ CỐ MÁY IN TRONG SỰ KIỆN

VietPhotoBooth được thiết kế với cơ chế bảo vệ tối đa: **Không bao giờ làm mất ảnh của khách hàng khi máy in gặp sự cố.**

### 1. Hết giấy hoặc hết mực (No Paper / Ribbon Out)
- **Hiện tượng**: Đèn trên máy in nháy đỏ, hàng đợi in trong VietPhotoBooth chuyển trạng thái sang `Lỗi máy in (Error): Hết giấy / Hết ruy-băng`.
- **Khắc phục**:
  1. Mở nắp máy in, thay cuộn giấy và cuộn ruy-băng mới theo hướng dẫn trên nắp máy.
  2. Đóng chặt nắp máy in cho đến khi đèn chuyển sang màu xanh (Ready).
  3. Vào **Quản Trị -> Máy In & Hàng Đợi** -> Tại dòng lệnh in bị lỗi, bấm nút **"Thử lại"**.
  4. Máy in sẽ lập tức tiếp tục in ảnh mà khách không cần phải chụp lại.

### 2. Kẹt giấy (Paper Jam)
- **Hiện tượng**: Máy phát tiếng kêu và đèn báo kẹt giấy sáng.
- **Khắc phục**:
  1. Tắt nguồn máy in, mở nắp kéo phần giấy bị kẹt ra và cắt bỏ đoạn giấy nhàu.
  2. Bật lại nguồn máy in.
  3. Kiểm tra hàng đợi in trên VietPhotoBooth và bấm **"Thử lại"**.

### 3. Khách muốn in thêm bản (Reprint)
- Nếu khách muốn in thêm ảnh đã chụp từ trước:
  1. Vào **Quản Trị -> Thư Viện Ảnh (Gallery)**.
  2. Tìm bức ảnh theo thời gian hoặc mã phiên chụp.
  3. Bấm vào bức ảnh và gửi lệnh in với số bản mong muốn.
