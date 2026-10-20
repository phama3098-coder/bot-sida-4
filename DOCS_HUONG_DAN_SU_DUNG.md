# HƯỚNG DẪN VẬN HÀNH PHẦN MỀM VIETPHOTOBOOTH

> **Ứng dụng Desktop Native chuyên nghiệp dành cho Windows 10 & 11 (64-bit)**  
> Phát triển trên nền tảng **PySide6 (Qt 6)**, tối ưu cho màn hình cảm ứng Kiosk, tích hợp máy ảnh DSLR/Mirrorless/Webcam, in nhiệt DNP tự động cắt và chia sẻ ảnh QR qua mạng nội bộ.

---

## 1. CÀI ĐẶT & KHỞI CHẠY

### 1.1. Cài đặt bằng file bộ cài (.exe)
- Chạy file: `dist_installer\VietPhotoBooth-Setup.exe`.
- Trình cài đặt tự động cài đặt vào máy tính mà **không yêu cầu quyền Administrator**.
- Tự động tạo biểu tượng ngoài màn hình Desktop và trong Start Menu: **VietPhotoBooth**.

### 1.2. Khởi chạy từ mã nguồn Python
```powershell
# Chạy ứng dụng giao diện Desktop tiêu chuẩn
py -3.12 -m vietphotobooth.main

# Hoặc khởi động trực tiếp vào chế độ Kiosk toàn màn hình
py -3.12 -m vietphotobooth.main --kiosk
```

---

## 2. HƯỚNG DẪN CÁC PHÂN HỆ CHỨC NĂNG

### A. Màn Hình Photobooth Kiosk (`Tab: 📸 Chụp Ảnh`)
Màn hình phục vụ khách chụp ảnh trực tiếp tại sự kiện:
1. **Xem trước trực tiếp (Live View)**: Hiển thị mượt mà 30 FPS từ máy ảnh hoặc webcam.
2. **Chọn đếm ngược**: Tùy chọn 3 giây, 5 giây hoặc 10 giây.
3. **Nút BẮT ĐẦU CHỤP**: Nút bấm cảm ứng cỡ lớn. Khi bấm, hệ thống kích hoạt chuỗi chụp tuần tự (3 hoặc 4 ảnh) với nhịp đếm ngược và hiệu ứng chớp flash trực quan.
4. **Màn hình xem kết quả (Review State)**:
   - **Dải bộ lọc màu (Filter Strip)**: Khách hàng chạm vào các thẻ bộ lọc (`Tự Nhiên`, `Ấm Áp`, `Cổ Điển`, `Trắng Đen`, `Mịn Da Rạng Rỡ`, `Điện Ảnh Cinematic`...) để đổi hiệu ứng tức thì mà **không làm mất ảnh gốc**.
   - **Dải khung ảnh (Frame Strip)**: Chạm đổi giữa các mẫu khung tiệc cưới, sinh nhật, doanh nghiệp hoặc dải đôi 2x6.
   - **Nút IN ẢNH NGAY**: Chọn số lượng bản in (1 - 10 bản) và gửi trực tiếp tới máy in Windows Spooler.
   - **Nút QUÉT MÃ QR**: Hiển thị popup chứa mã QR độ nét cao và địa chỉ IP LAN để khách dùng smartphone tải ảnh gốc và ảnh khung về máy.
   - **Chụp lại (Retake)** & **Hoàn tất (Finish)**: Cho phép chụp lại nếu chưa ưng ý hoặc quay về màn hình chờ đón lượt khách tiếp theo.

---

### B. Studio Chỉnh Sửa Bộ Lọc Màu & 3D LUT (`Tab: 🎨 Bộ Lọc Màu`)
Bộ công cụ chuyên sâu cho chuyên viên kỹ thuật thiết kế và tùy biến tông màu ảnh:
1. **14 Thanh trượt tham số xử lý ảnh số**:
   - **Phơi sáng (Exposure)**: Bù trừ sáng -100 đến +100 (-1.5 EV đến +1.5 EV).
   - **Độ sáng (Brightness)**: Cân chỉnh tổng thể vùng sáng.
   - **Độ tương phản (Contrast)**: Tăng giảm chiều sâu khối hình.
   - **Vùng sáng (Highlights)** & **Vùng tối (Shadows)**: Tinh chỉnh chi tiết ngược sáng hoặc bóng tối.
   - **Gamma**: Tinh chỉnh dải sắc độ từ 0.2 đến 3.0.
   - **Độ bão hòa (Saturation)**: Đậm đà hoặc nhạt màu.
   - **Nhiệt độ màu (Temperature)**: Tông xanh mát (< 0) hoặc vàng ấm (> 0).
   - **Sắc độ (Tint)**: Xanh lá (< 0) hoặc hồng tím (> 0).
   - **Chuyển Trắng Đen (Grayscale)** & **Tông Nâu Cổ Điển (Sepia)**.
   - **Làm mịn da (Soft Skin)**: Thuật toán lọc song phương kết hợp nhận diện vùng da người (YCbCr Skin Mask), làm mịn nốt mụn và khuyết điểm nhưng vẫn giữ nguyên khối mũi và nét mí mắt.
   - **Độ sắc nét (Sharpness)**, **Mờ phim nâng đen (Fade)**, **Tối 4 góc (Vignette)**.
2. **Hỗ trợ bảng tra màu chuẩn điện ảnh 3D LUT (.cube)**:
   - Tự động nạp các file `.cube` trong thư mục `Assets/Filters/LUTs/`.
   - Hỗ trợ nút **Nhập File .cube Ngoài** từ DaVinci Resolve / Photoshop / Lightroom.
   - Thanh trượt điều chỉnh cường độ hòa trộn LUT từ 0% đến 100%.
3. **Quản lý Preset**:
   - **Tạo mới**, **Nhân bản**, **Lưu thay đổi**, **Xóa**.
   - **Xuất file JSON** để chia sẻ preset giữa các máy booth hoặc **Nhập JSON** từ bên ngoài.

---

### C. Trình Thiết Kế Khung Ảnh (`Tab: 🖼️ Khung Ảnh`)
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

### E. Quản Lý Máy In & Hàng Đợi (`Tab: 🖨️ Máy In`)
1. **Nhận diện Driver Windows Spooler**:
   - Tự động liệt kê mọi máy in đã cài đặt trên Windows (`DNP DS-RX1HS`, `Citizen CY-02`, `Hiti P525L`, `Canon SELPHY`...).
2. **Cấu hình cắt đôi 2x6 inch (DNP Cut Mode)**:
   - Tích hợp profile điều khiển dao cắt tự động cho máy in nhiệt thăng hoa DNP DS-RX1HS.
3. **In thẻ kiểm tra (Test Print Card)**:
   - Tạo và in thẻ thử nghiệm chuẩn 300 DPI gồm: dải màu kiểm tra đầu in (Color Bar), thước đo căn lề, đường chỉ cắt dao đôi.
4. **Hàng đợi in thời gian thực (Print Queue)**:
   - Theo dõi từng lệnh in: Mã lệnh, tên file, số bản, trạng thái `SPOOLING`, `COMPLETED`, `ERROR`. Hỗ trợ xóa lịch sử hoặc thử lại lệnh in bị lỗi.

---

### F. Quản Lý Sự Kiện & Thư Viện (`Tab: 📁 Sự Kiện & Thư Viện`)
1. **Quản lý sự kiện**:
   - Tạo sự kiện mới (ví dụ: `DamCuoi_TuanLan`, `SinhNhat_BaoNgoc`).
   - Tự động tạo cấu trúc thư mục chuẩn: `Originals/`, `Final/`, `Thumbnails/`, `Templates/`, `Logs/`.
2. **Thư viện ảnh đã chụp**:
   - Danh sách toàn bộ các lượt chụp trong sự kiện.
   - Hỗ trợ **In lại (Reprint)** cho khách muốn in thêm ảnh lưu niệm.
   - Hỗ trợ **Xem lại mã QR** cho từng lượt chụp.
   - **Xuất File ZIP**: Nén toàn bộ ảnh gốc và ảnh thành phẩm của sự kiện vào 1 file `.zip` duy nhất để bàn giao cho khách hàng hoặc cô dâu chú rể.

---

### G. Cài Đặt Hệ Thống & Bảo Mật PIN (`Tab: ⚙️ Cài Đặt`)
1. **Bảo mật mã PIN**:
   - Khi bật bảo mật PIN, khách hàng tại booth không thể tự ý thoát ra ngoài màn hình Windows hoặc can thiệp vào các tab cấu hình quản trị.
   - Mã PIN mặc định khi xuất xưởng: `1234`. Có thể đổi mã PIN mới dễ dàng.
2. **Toàn màn hình Kiosk (F11)**:
   - Bấm `F11` hoặc nút **Bật Toàn Màn Hình** để đưa ứng dụng vào chế độ Kiosk chuyên nghiệp, ẩn thanh tiêu đề và thanh tác vụ Windows.
3. **Máy chủ chia sẻ ảnh mạng LAN**:
   - Hiển thị địa chỉ IP trạm và cổng dịch vụ (mặc định: `8000`).
   - Khách hàng kết nối chung mạng WiFi với trạm Photobooth là có thể quét mã QR để tải ảnh trực tiếp về smartphone.
