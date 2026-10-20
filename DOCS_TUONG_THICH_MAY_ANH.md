# BẢNG TƯƠNG THÍCH MÁY ẢNH VÀ HƯỚNG DẪN CÀI ĐẶT DRIVER

Tài liệu này cung cấp chi tiết danh mục các dòng máy ảnh DSLR, Mirrorless và Webcam tương thích với phần mềm **VietPhotoBooth** trên nền tảng Windows 10/11 64-bit, cùng hướng dẫn cấu hình thiết bị thực tế.

---

## 1. NGUYÊN TẮC ĐÁNH GIÁ TƯƠNG THÍCH

VietPhotoBooth tuân thủ nguyên tắc trung thực kỹ thuật, phân loại rõ ràng 5 cấp độ tương thích:
1. **Đã kiểm thử đầy đủ bằng thiết bị thật (Fully Tested Hardware)**: Thiết bị đã được cắm vào máy tính Windows, thực hiện chuỗi chụp, tải ảnh, live view và in ấn ổn định liên tục.
2. **Đã kiểm thử một phần (Partially Tested)**: Hoạt động tốt chức năng chụp và tải ảnh; live view hoặc đổi thông số có thể cần cấu hình riêng.
3. **Backend nhận diện được nhưng chưa kiểm thử đầy đủ (Detected / Untested)**: Driver nhận diện máy ảnh qua giao thức PTP/WIA nhưng chưa chạy qua sự kiện thực tế kéo dài.
4. **Cần SDK hoặc Driver riêng của hãng (Needs SDK / Driver)**: Cần cài đặt driver chuyên dụng của hãng sản xuất trước khi kết nối.
5. **Chưa hỗ trợ (Unsupported)**: Các dòng máy compact cũ không có cổng USB tethering hoặc giao thức điều khiển từ xa.

---

## 2. BẢNG TƯƠNG THÍCH CHI TIẾT THEO MODEL

### 2.1. Hãng CANON (Khuyến nghị số 1 cho Photobooth)

| Model Máy Ảnh | Backend Điều Khiển | Chụp | Tải Ảnh | Live View | Đổi Thông Số | Trạng Thái Kiểm Thử | Ghi Chú Kỹ Thuật |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Canon EOS 5D Mark IV / III** | EDSDK / digiCamControl | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Khung ngắm Fullframe cực nét. Tắt Auto Power Off. |
| **Canon EOS 6D / 6D Mark II** | EDSDK / digiCamControl | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Dòng máy Fullframe phổ biến nhất tại tiệc cưới. |
| **Canon EOS Rebel T6 / T7 / 2000D / 1500D** | EDSDK / digiCamControl | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Lựa chọn số 1 về chi phí/hiệu năng trong booth. |
| **Canon EOS 80D / 90D / 77D** | EDSDK / digiCamControl | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Lấy nét Dual Pixel siêu nhanh, nhận diện khuôn mặt tốt. |
| **Canon EOS R / R5 / R6 / RP / R50 / R10** | Canon EDSDK v13.x | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử một phần | Cần dùng cáp USB-C 3.1 chính hãng để tránh rớt live view. |
| **Canon M50 / M50 Mark II / M200** | EOS Webcam Utility / PTP | ✅ | ✅ | ✅ | ❌ | Đã kiểm thử một phần | Có thể dùng qua EOS Webcam Utility hoặc cổng Clean HDMI. |

### 2.2. Hãng NIKON

| Model Máy Ảnh | Backend Điều Khiển | Chụp | Tải Ảnh | Live View | Đổi Thông Số | Trạng Thái Kiểm Thử | Ghi Chú Kỹ Thuật |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Nikon D3200 / D3300 / D3400 / D3500** | digiCamControl / Nikon SDK | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Bản D3400/D3500 cần kiểm tra firmware không bị khóa tethering. |
| **Nikon D5300 / D5500 / D5600** | digiCamControl / Nikon SDK | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Hoạt động rất mát máy, không bị quá nhiệt khi chạy cả ngày. |
| **Nikon D7100 / D7200 / D7500** | digiCamControl / Nikon SDK | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Rất bền bỉ trong sự kiện lớn kéo dài trên 10 tiếng. |
| **Nikon D750 / D780 / D810 / D850** | digiCamControl / Nikon SDK | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Khuyến nghị để chất lượng JPEG Fine/Normal để tăng tốc tải ảnh. |
| **Nikon Z5 / Z6 / Z7 / Z50 / Z fc** | Nikon Z SDK / digiCamControl | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử một phần | Bật chế độ [PC Connection] trong menu máy ảnh. |

### 2.3. Hãng SONY

| Model Máy Ảnh | Backend Điều Khiển | Chụp | Tải Ảnh | Live View | Đổi Thông Số | Trạng Thái Kiểm Thử | Ghi Chú Kỹ Thuật |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Sony A6000 / A6300 / A6400 / A6500** | Sony Remote / PC Remote | ✅ | ✅ | ✅ | ❌ | Đã kiểm thử một phần | Cần vào Menu USB Connection -> chọn [PC Remote]. |
| **Sony A7 II / A7 III / A7 IV / A7C** | Sony Camera Remote SDK | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử một phần | Cần cài Sony Imaging Edge Driver. Live view mượt. |
| **Sony ZV-E10 / ZV-1** | USB Streaming UVC | ✅ | ✅ | ✅ | ❌ | Đã kiểm thử đầy đủ | Bật chế độ [USB Streaming] -> Nhận diện ngay như webcam UVC. |

### 2.4. Hãng FUJIFILM, PANASONIC, OLYMPUS

| Model Máy Ảnh | Backend Điều Khiển | Chụp | Tải Ảnh | Live View | Đổi Thông Số | Trạng Thái Kiểm Thử | Ghi Chú Kỹ Thuật |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Fujifilm X-T2 / X-T3 / X-T4 / X-S10** | FUJIFILM X Webcam | ✅ | ✅ | ✅ | ❌ | Cần SDK/Driver riêng | Cài ứng dụng FUJIFILM X Webcam 2.x trên Windows. |
| **Panasonic Lumix GH5 / G9 / S5** | LUMIX Tether / UVC Card | ✅ | ✅ | ✅ | ❌ | Cần SDK/Driver riêng | Khuyên dùng cáp HDMI + thẻ thu hình Elgato Cam Link 4K. |
| **Olympus OM-D E-M1 / E-M5** | OM Capture Hot Folder | ✅ | ✅ | ❌ | ❌ | Nhận diện nhưng chưa kiểm thử | Chụp qua cơ chế giám sát thư mục (Hot folder). |

### 2.5. WEBCAM USB CHUẨN UVC & THẺ THU HÌNH (CAPTURE CARD)

| Thiết Bị | Backend Điều Khiển | Chụp | Tải Ảnh | Live View | Đổi Thông Số | Trạng Thái Kiểm Thử | Ghi Chú Kỹ Thuật |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Logitech Brio 4K / C920 / C922** | Windows DirectShow | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Chuẩn UVC không cần driver. Bật là chạy ngay. |
| **Elgato Cam Link 4K** | Windows DirectShow | ✅ | ✅ | ✅ | ❌ | Đã kiểm thử đầy đủ | Biến mọi máy ảnh có cổng Clean HDMI thành camera Photobooth. |
| **Bộ Giả Lập VietPhotoBooth** | Software Simulator | ✅ | ✅ | ✅ | ✅ | Đã kiểm thử đầy đủ | Phục vụ demo, kiểm thử không cần phần cứng. |

---

## 3. HƯỚNG DẪN CÀI ĐẶT DRIVER MÁY ẢNH TRÊN WINDOWS

### 3.1. Cài đặt và cấu hình digiCamControl (Dành cho Canon/Nikon/Sony)
1. Tải bản cài đặt digiCamControl chính thức từ: `http://digicamcontrol.com/download`
2. Tiến hành cài đặt theo mặc định vào: `C:\Program Files (x86)\digiCamControl\`
3. Mở digiCamControl, cắm máy ảnh qua cáp USB và bật nguồn máy ảnh.
4. Vào menu **Settings -> Webserver**:
   - Tích chọn **Enable**.
   - Cổng mặc định: **`5513`**.
   - Bấm **Save**.
5. Trong VietPhotoBooth, vào **Quản Trị -> Cài Đặt Máy Ảnh -> Chọn backend `digiCamControl DSLR`** -> Bấm **Lưu & Kết Nối**.

### 3.2. Cấu hình cài đặt trên thân máy ảnh (Camera Body Settings)
Để tránh máy ảnh bị ngắt kết nối hoặc treo màn trập giữa chừng sự kiện, bạn **BẮT BUỘC** thực hiện các bước sau trên thân máy:
- **Chế độ phơi sáng**: Chuyển vòng xoay chế độ sang **`M` (Manual)**. Đặt tốc độ màn trập cố định từ `1/125s` đến `1/160s`, khẩu độ `f/4.0` - `f/5.6`, ISO `400` - `800` phù hợp với ánh sáng đèn booth.
- **Lấy nét**: Chuyển ống kính sang **AF (Tự động)** hoặc khóa nét tay (MF) vào vị trí đứng của khách nếu phông nền cố định.
- **Tắt chế độ ngủ tự động (Auto Power Off)**: Vào Menu máy ảnh -> `Auto Power Off` -> Chọn **`Disable` (Tắt)**.
- **Nguồn điện**: Tuyệt đối **KHÔNG** dùng pin máy ảnh thông thường cho sự kiện dài. Hãy dùng **Bộ giả lập nguồn AC (Dummy Battery / DC Coupler)** cắm trực tiếp vào ổ điện 220V để máy chạy 24/7 không bị hết pin.
