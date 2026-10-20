# HƯỚNG DẪN VẬN HÀNH PHẦN MỀM 1998 TEAM — PHOTOBOOTH
### 1998 Studio Phóng Sự Cưới & Sự Kiện Chuyên Nghiệp

> **Ứng dụng Desktop Native chuyên nghiệp dành cho Windows 10 & 11 (64-bit)**  
> Phát triển trên nền tảng **PySide6 (Qt 6)** phong cách Luxury Wedding Studio, tối ưu cho màn hình cảm ứng Kiosk, tích hợp máy ảnh DSLR/Mirrorless/Webcam, in nhiệt DNP tự động cắt và chia sẻ ảnh QR qua mạng nội bộ.

---

## 1. CÀI ĐẶT & KHỞI CHẠY

### 1.1. Cài đặt bằng file bộ cài (.exe)
- Chạy file: `dist_installer\1998-Team-Photobooth-Setup.exe`.
- Trình cài đặt tự động cài đặt vào máy tính mà **không yêu cầu quyền Administrator**.
- Tự động tạo biểu tượng ngoài màn hình Desktop và trong Start Menu: **1998 TEAM — Photobooth**.

### 1.2. Khởi chạy từ mã nguồn Python
```powershell
# Chạy ứng dụng giao diện Desktop tiêu chuẩn
py -3.12 -m vietphotobooth.main

# Hoặc khởi động trực tiếp vào chế độ Kiosk toàn màn hình
py -3.12 -m vietphotobooth.main --kiosk
```

---

## 2. HƯỚNG DẪN CÁC PHÂN HỆ CHỨC NĂNG (6 MỤC ĐIỀU HƯỚNG)

Giao diện quản trị được tổ chức thành 6 phân hệ chuyên nghiệp:
1. `📸 Chụp Ảnh`
2. `🖼️ Khung Ảnh`
3. `📷 Máy Ảnh`
4. `🖨️ Máy In`
5. `📁 Sự Kiện & Thư Viện`
6. `⚙️ Cài Đặt`

---

### A. Màn Hình Photobooth Kiosk (`Tab: 📸 Chụp Ảnh`)
Màn hình phục vụ khách chụp ảnh trực tiếp tại sự kiện cưới & hội nghị:
1. **Khung Live View trung tâm**: Chiếm diện tích lớn nhất giao diện, hiển thị mượt mà 30 FPS từ máy ảnh hoặc webcam.
2. **Cảnh báo mất kết nối camera**: Nếu chưa cắm cáp USB hoặc camera bị ngắt kết nối, màn hình hiển thị bảng cảnh báo "CHƯA KẾT NỐI MÁY ẢNH" cùng nút "🔌 Kết Nối Lại Máy Ảnh", không hiển thị hình người mô phỏng.
3. **Thanh trạng thái đầu trang**:
   - Hiển thị logo **1998 Studio**, trạng thái kết nối camera, độ phân giải thực tế.
   - Bộ chọn số lượng ảnh mỗi lượt (3 ảnh / 4 ảnh / 2 ảnh / 1 ảnh).
   - Bộ chọn thời gian đếm ngược (3 giây / 5 giây / 10 giây).
4. **Thanh điều khiển đáy trang (Không thanh cuộn ngang)**:
   - **Chọn Khung Ảnh**: Danh sách các mẫu khung tiệc cưới, sinh nhật, doanh nghiệp hoặc dải đôi 2x6.
   - **Bộ Lọc Màu**: Khởi tạo sạch sẽ không chứa bộ lọc mẫu. Hiển thị thông báo *"Chưa có bộ lọc. Hãy thêm bộ lọc của bạn"* cùng nút **"+ Thêm Bộ Lọc"** để người dùng tự tạo hoặc nạp preset/LUT của studio.
   - **Nút BẮT ĐẦU CHỤP**: Nút bấm màu vàng Champagne cỡ lớn. Khi bấm, hệ thống kích hoạt chuỗi chụp tuần tự với nhịp đếm ngược và hiệu ứng flash.
5. **Màn hình xem kết quả (Review Mode)**:
   - **Nút IN ẢNH NGAY**: Gửi lệnh in trực tiếp tới máy in nhiệt DNP DS-RX1HS / Windows Spooler.
   - **Nút QUÉT MÃ QR**: Hiển thị popup chứa mã QR độ nét cao và địa chỉ IP LAN để khách dùng smartphone tải ảnh về máy.
   - **Chụp lại (Retake)**, **Lưu ảnh (Save)** & **Hoàn tất (Finish)**: Cho phép chụp lại nếu chưa ưng ý hoặc quay về màn hình chờ đón lượt khách tiếp theo.

---

### B. Trình Thiết Kế Khung Ảnh (`Tab 2: 🖼️ Khung Ảnh`)
Hệ thống thiết kế và bố cục khung in ảnh chuẩn mực 300 DPI:
1. **Khổ in hỗ trợ**:
   - `2x6`: Dải dọc truyền thống (600 x 1800 px tại 300 DPI).
   - `4x6_portrait`: Khổ đứng 4x6 inch (1200 x 1800 px).
   - `4x6_landscape`: Khổ ngang 4x6 inch (1800 x 1200 px).
   - `4x6_dual`: Ghép đôi 2 dải 2x6 trên một khổ giấy 4x6 (chuẩn in cho máy in nhiệt DNP DS-RX1HS tự động cắt đôi thành 2 dải rời).
2. **Nhập khung PNG ngoài (Overlay Import)**:
   - Bấm **Nhập Khung PNG Ngoài** -> Chọn file PNG do Photoshop thiết kế có viền trong suốt (Alpha Channel).
   - Hệ thống tự động tạo mẫu khung mới, căn chỉnh tỷ lệ 300 DPI và gán các ô ảnh tương thích.
3. **Chỉnh sửa các ô ảnh (Slots) & Bo góc**:
   - Tự do thêm/xóa ô ảnh, thay đổi tọa độ `X, Y, W, H`, độ bo góc tròn `Corner Radius`, viền ảnh `Border Width/Color`.
4. **Văn bản nghệ thuật & Logo**:
   - Thêm các dòng chữ như `{event_name}`, `{date}`, tên cô dâu chú rể, lời chúc mừng sinh nhật với font chữ tiếng Việt sắc nét.
5. **Cảnh báo mép xén (Bleed) & Vùng an toàn (Safe Zone)**:
   - Hệ thống tự động phân tích và đưa ra cảnh báo thời gian thực nếu ô ảnh hoặc chữ nằm sát mép cắt máy in.

---

### D. Quản Lý Máy Ảnh (`Tab: 📷 Máy Ảnh`)
1. **Lựa chọn Trình điều khiển (Backend)**:
   - `Simulator`: Bộ giả lập máy ảnh tích hợp sẵn ảnh chân dung mẫu, cho phép kiểm thử toàn bộ tính năng mà không cần cắm máy ảnh thật.
   - `DirectShow Webcam (USB UVC)`: Hỗ trợ tất cả các dòng webcam USB chuẩn Windows (Logitech C920/C930e/Brio, Razer Kiyo...).
   - `digiCamControl`: Điều khiển các dòng máy ảnh DSLR và Mirrorless qua cổng USB (Canon EOS, Nikon D/Z-series, Sony Alpha).
2. **Kiểm tra khả năng & Chụp thử**:
   - Bảng chẩn đoán tính năng thực tế: Live View, Chụp độ phân giải cao, Căn chỉnh thông số.
   - Nút **Chụp Thử Nghiệm** để kiểm tra ngay chất lượng ánh sáng và tiêu cự.

---

---

### C. Quản Lý Máy Ảnh (`Tab 3: 📷 Máy Ảnh`)
1. **Lựa chọn Trình điều khiển (Backend)**:
   - `Simulator`: Bộ giả lập máy ảnh với tín hiệu kiểm thử SMPTE và vòng ngắm studio, cho phép kiểm thử toàn bộ tính năng mà không cần cắm máy ảnh thật.
   - `DirectShow Webcam (USB UVC)`: Hỗ trợ tất cả các dòng webcam USB chuẩn Windows (Logitech C920/C930e/Brio, Razer Kiyo...).
   - `digiCamControl`: Điều khiển các dòng máy ảnh DSLR và Mirrorless qua cổng USB (Canon EOS, Nikon D/Z-series, Sony Alpha).
2. **Kiểm tra khả năng & Chụp thử**:
   - Bảng chẩn đoán tính năng thực tế: Live View, Chụp độ phân giải cao, Căn chỉnh thông số.
   - Nút **Chụp Thử Nghiệm** để kiểm tra ngay chất lượng ánh sáng và tiêu cự.

---

### D. Quản Lý Máy In & Hàng Đợi (`Tab 4: 🖨️ Máy In`)
1. **Nhận diện Driver Windows Spooler**:
   - Tự động liệt kê mọi máy in đã cài đặt trên Windows (`DNP DS-RX1HS`, `Citizen CY-02`, `Hiti P525L`, `Canon SELPHY`...).
2. **Cấu hình cắt đôi 2x6 inch (DNP Cut Mode)**:
   - Tích hợp profile điều khiển dao cắt tự động cho máy in nhiệt thăng hoa DNP DS-RX1HS.
3. **In thẻ kiểm tra (Test Print Card)**:
   - Tạo và in thẻ thử nghiệm chuẩn 300 DPI gồm: dải màu kiểm tra đầu in (Color Bar), thước đo căn lề, đường chỉ cắt dao đôi.
4. **Hàng đợi in thời gian thực (Print Queue)**:
   - Theo dõi từng lệnh in: Mã lệnh, tên file, số bản, trạng thái `SPOOLING`, `COMPLETED`, `ERROR`. Hỗ trợ xóa lịch sử hoặc thử lại lệnh in bị lỗi.

---

### E. Quản Lý Sự Kiện & Thư Viện (`Tab 5: 📁 Sự Kiện & Thư Viện`)
1. **Quản lý sự kiện**:
   - Tạo sự kiện mới (ví dụ: `DamCuoi_TuanLan`, `SinhNhat_BaoNgoc`).
   - Tự động tạo cấu trúc thư mục chuẩn: `Originals/`, `Final/`, `Thumbnails/`, `Templates/`, `Logs/`.
2. **Thư viện ảnh đã chụp**:
   - Danh sách toàn bộ các lượt chụp trong sự kiện.
   - Hỗ trợ **In lại (Reprint)** cho khách muốn in thêm ảnh lưu niệm.
   - Hỗ trợ **Xem lại mã QR** cho từng lượt chụp.
   - **Xuất File ZIP**: Nén toàn bộ ảnh gốc và ảnh thành phẩm của sự kiện vào 1 file `.zip` duy nhất để bàn giao cho khách hàng hoặc cô dâu chú rể.

---

### F. Cài Đặt Hệ Thống, Bảo Mật PIN & Bộ Lọc (`Tab 6: ⚙️ Cài Đặt`)
1. **Bảo mật mã PIN**:
   - Khi bật bảo mật PIN, khách hàng tại booth không thể tự ý thoát ra ngoài màn hình Windows hoặc can thiệp vào các tab cấu hình quản trị.
   - Mã PIN mặc định khi xuất xưởng: `1234`. Có thể đổi mã PIN mới dễ dàng.
2. **Toàn màn hình Kiosk (F11)**:
   - Bấm `F11` hoặc nút **Bật Toàn Màn Hình** để đưa ứng dụng vào chế độ Kiosk chuyên nghiệp, tự động ẩn thanh tiêu đề và thanh tác vụ Windows.
3. **Quản lý Bộ Lọc Màu (Filter Studio)**:
   - Mở trực tiếp từ nút **"+ Thêm Bộ Lọc"** tại màn hình Chụp Ảnh hoặc nút **"🎨 Mở Trình Biên Tập Bộ Lọc Màu (Filter Studio)"** trong mục Cài Đặt.
   - Tinh chỉnh 14 tham số màu sắc (Exposure, Brightness, Contrast, Temp, Tint, Shadows, Highlights, Gamma, Vignette...).
   - Thuật toán làm mịn da chân dung (Soft Skin) bằng lọc song phương YCbCr.
   - Nạp file `.cube` 3D LUT từ Photoshop/Lightroom với thanh trượt cường độ hòa trộn 0 - 100%.
   - Tạo mới, nhân bản, lưu, xuất và nhập cấu hình bộ lọc JSON.
4. **Máy chủ chia sẻ ảnh mạng LAN**:
   - Hiển thị địa chỉ IP trạm và cổng dịch vụ (mặc định: `8000`).
   - Khách hàng kết nối chung mạng WiFi với trạm Photobooth là có thể quét mã QR để tải ảnh trực tiếp về smartphone.
