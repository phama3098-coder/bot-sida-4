# VIETPHOTOBOOTH — ỨNG DỤNG PHOTOBOOTH DESKTOP CHUYÊN NGHIỆP CHO WINDOWS

![Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%2064--bit-blue)
![GUI](https://img.shields.io/badge/GUI-PySide6%20%7C%20Qt%206-green)
![Python](https://img.shields.io/badge/Python-3.12-brightgreen)
![Tests](https://img.shields.io/badge/Tests-25%2F25%20Passing%20(100%25)-success)
![Installer](https://img.shields.io/badge/Installer-VietPhotoBooth--Setup.exe%20(~83MB)-orange)

**VietPhotoBooth** là ứng dụng **Desktop Native (Windows Native Window)** chuyên nghiệp, vận hành trực tiếp trên **Windows 10 và Windows 11 (64-bit)**, không yêu cầu mở trình duyệt web (không phải website gói webview).

Ứng dụng được thiết kế cho tiệc cưới, sinh nhật, sự kiện doanh nghiệp và các booth chụp ảnh lấy liền tự động với màn hình cảm ứng, tích hợp máy ảnh DSLR/Mirrorless/Webcam, in nhiệt DNP DS-RX1HS tự động cắt và chia sẻ ảnh qua mã QR trong mạng nội bộ.

---

## 🌟 ĐẶC ĐIỂM KỸ THUẬT NỔI BẬT

### 1. Ứng Dụng Desktop Native Hoàn Chỉnh (PySide6 / Qt 6)
- **Không phải ứng dụng Web**: Chạy dưới dạng cửa sổ desktop Windows độc lập (`QMainWindow`), tối ưu hóa đồ họa phần cứng bằng Qt6, mượt mà trên màn hình cảm ứng từ 15 đến 32 inch.
- **Chế độ Kiosk Toàn Màn Hình (F11 Kiosk Mode)**: Tự động ẩn thanh tác vụ Windows và thanh tiêu đề, khóa an toàn bằng **mã PIN 4 số** ngăn khách chạm thoát ứng dụng.
- **Dịch vụ phụ trợ ngầm**: Máy chủ FastAPI nội bộ chạy trong luồng nền (daemon thread) chỉ nhằm phục vụ việc quét mã QR và tải ảnh về smartphone của khách qua WiFi nội bộ mà không cần Internet.

### 2. Studio Bộ Lọc Màu Mở Rộng & Bảng Tra Màu 3D LUT (.cube)
- **12 Preset màu tích hợp sẵn**:
  - `Tự Nhiên (Natural)`, `Ấm Áp (Warm)`, `Tươi Mát (Cool)`, `Cổ Điển (Vintage)`, `Hoài Cổ 80s (Retro)`, `Trắng Đen Nghệ Thuật (B&W)`, `Nâu Hoài Niệm (Sepia)`, `Mịn Da Rạng Rỡ (Soft Skin)`, `Tươi Sáng Rực Rỡ (Bright Pop)`, `Tương Phản Ấn Tượng (High Contrast)`, `Hôn Lễ Lãng Mạn (Wedding Dream)`, `Điện Ảnh Cinematic (Teal & Orange)`.
- **14 Tham số tinh chỉnh chuyên sâu**:
  - Phơi sáng (Exposure), Độ sáng (Brightness), Độ tương phản (Contrast), Độ bão hòa (Saturation), Nhiệt độ màu (Temp), Sắc độ (Tint), Vùng sáng (Highlights), Vùng tối (Shadows), Gamma, Độ sắc nét (Sharpness), Mờ phim (Fade), Tối 4 góc (Vignette), Trắng đen (Grayscale), Tông nâu (Sepia).
- **Làm mịn da thông minh (Soft Skin)**:
  - Sử dụng bộ lọc song phương (Bilateral Filter) kết hợp nhận diện mặt nạ da người YCbCr; xóa sạch khuyết điểm da nhưng bảo toàn độ nét của mắt, tóc và sống mũi.
- **Hỗ trợ chuẩn 3D LUT (.cube)**:
  - Phân tích cú pháp file `.cube` chuẩn Adobe / DaVinci Resolve, nội suy tam tuyến (trilinear interpolation) tốc độ cao bằng NumPy, điều chỉnh cường độ hòa trộn từ 0% đến 100%.
- **Quản lý Preset không phá hủy (Non-Destructive)**:
  - Lưu, nhân bản, sửa tên, xóa, xuất/nhập file cấu hình preset `.json`. Ảnh gốc trong thư mục `Originals/` luôn được bảo toàn nguyên bản 100%.

### 3. Trình Thiết Kế Khung Ảnh (Frame Designer) & Nhập Khung PNG Ngoài
- **Độ phân giải chuẩn in ấn 300 DPI**:
  - `2x6 inch` (600 x 1800 px): Dải dọc 3 hoặc 4 ảnh truyền thống.
  - `4x6 inch` (1200 x 1800 px đứng / 1800 x 1200 px ngang): Bố cục lưới 2x2 hoặc dải ngang sự kiện doanh nghiệp.
  - `4x6 inch Ghép Đôi 2 Dải 2x6 (Dual Cut)`: Bố cục tối ưu hóa cho máy in nhiệt DNP DS-RX1HS tự động cắt đôi thành 2 dải rời sau khi in.
- **Nhập khung PNG ngoài (Overlay PNG Import)**:
  - Nhập trực tiếp file PNG viền hoa văn có kênh trong suốt (Alpha Channel) từ Photoshop/Canva; tự động căn lề 300 DPI và phân bổ các ô ảnh.
- **Bố cục linh hoạt**:
  - Di chuyển, thay đổi kích thước từng ô ảnh (PhotoSlot), bo góc tròn (`Corner Radius`), vẽ viền (`Border Width/Color`).
  - Thêm các lớp chữ nghệ thuật tiếng Việt (`{event_name}`, `{date}`, tên cô dâu chú rể) và logo nhà tài trợ.
- **Kiểm tra mép xén (Bleed) & Vùng an toàn (Safe Zone)**:
  - Cảnh báo trực quan nếu ô ảnh hoặc chữ rơi vào vùng xén lề của máy in.

### 4. Điều Khiển Đa Thiết Bị Máy Ảnh (Camera Adapter)
- **Simulator**: Bộ giả lập máy ảnh với ảnh chân dung mẫu, cho phép kiểm thử toàn bộ quy trình mà không cần cắm máy ảnh thật.
- **DirectShow UVC**: Tương thích mọi dòng Webcam USB (Logitech C920, C930e, Brio 4K, Razer Kiyo...).
- **digiCamControl**: Điều khiển máy ảnh chuyên nghiệp DSLR & Mirrorless (Canon EOS, Nikon D/Z, Sony Alpha).

### 5. In Ấn Chuyên Dụng (Windows Print Spooler & DNP DS-RX1HS)
- Tích hợp trực tiếp với Windows Print Spooler qua Win32 API (`win32print`).
- Profile chuyên dụng điều khiển dao cắt 2-inch cho máy in nhiệt **DNP DS-RX1HS**.
- In thẻ kiểm tra màu sắc & độ căn lề (Test Print Card).
- Quản lý hàng đợi in độc lập; lỗi máy in không bao giờ làm mất ảnh của khách.

### 6. Đóng Gói Bộ Cài Windows Độc Lập (.exe)
- Bộ cài hoàn chỉnh `dist_installer\VietPhotoBooth-Setup.exe` (~83 MB) được tạo bởi Inno Setup 6.
- Cài đặt nhanh chóng, không yêu cầu quyền Administrator, tự động tạo icon Desktop & Start Menu, tích hợp trình gỡ cài đặt sạch sẽ.

---

## 📁 CẤU TRÚC MÃ NGUỒN

```
photobooth/
├── dist_installer/
│   └── VietPhotoBooth-Setup.exe          # Bộ cài đặt Windows hoàn chỉnh (~83MB)
├── Assets/                               # Tài nguyên hệ thống mở rộng
│   ├── Filters/
│   │   ├── BuiltIn/                      # 12 file JSON preset mặc định
│   │   ├── Custom/                       # Preset do người dùng tự tạo
│   │   └── LUTs/                         # File 3D LUT (.cube) điện ảnh
│   └── Frames/                           # Mẫu khung in ấn phân theo danh mục
│       ├── Wedding/                      # Khung tiệc cưới lãng mạn
│       ├── Birthday/                     # Khung sinh nhật rực rỡ
│       ├── Corporate/                    # Khung sự kiện doanh nghiệp
│       └── Custom/                       # Khung dải đôi DNP & khung tự nhập
├── vietphotobooth/
│   ├── desktop/                          # GIAO DIỆN NATIVE DESKTOP (PySide6)
│   │   ├── styles.py                     # QSS Dark Theme tối ưu cảm ứng Kiosk
│   │   ├── main_window.py                # Cửa sổ chính & điều hướng tabs/PIN
│   │   └── widgets/
│   │       ├── kiosk_page.py             # Màn hình Kiosk chụp ảnh chính
│   │       ├── filter_editor_page.py     # Studio chỉnh sửa 14 thanh trượt & LUT
│   │       ├── frame_designer_page.py    # Trình thiết kế bố cục khung in 300 DPI
│   │       ├── camera_page.py            # Quản lý & chẩn đoán kết nối máy ảnh
│   │       ├── printing_page.py          # Quản lý máy in Windows & hàng đợi
│   │       ├── events_page.py            # Thư viện ảnh sự kiện, in lại, xuất ZIP
│   │       └── settings_page.py          # Cài đặt mã PIN, Kiosk timeout, LAN IP
│   ├── filters/                          # LÕI XỬ LÝ BỘ LỌC & 3D LUT
│   │   ├── lut_parser.py                 # Bộ đọc .cube & nội suy tam tuyến
│   │   └── filter_engine.py              # Bộ máy 14 tham số & làm mịn da
│   ├── frames/                           # LÕI THIẾT KẾ & XUẤT ẢNH IN
│   │   ├── frame_models.py               # Mô hình FrameTemplate, Slot, TextLayer
│   │   ├── frame_designer.py             # Ghép ảnh 300 DPI, kiểm tra Bleed
│   │   └── frame_manager.py              # Nhập khung PNG ngoài & quản lý khung
│   ├── camera/                           # ADAPTER ĐIỀU KHIỂN MÁY ẢNH
│   │   ├── base.py                       # Abstract CameraAdapter
│   │   ├── simulator.py                  # Giả lập máy ảnh phần mềm
│   │   ├── directshow.py                 # Webcam USB DirectShow
│   │   ├── digicam.py                    # DSLR/Mirrorless Canon, Nikon, Sony
│   │   └── manager.py                    # Bộ điều phối máy ảnh an toàn
│   ├── printing/                         # ADAPTER MÁY IN WINDOWS
│   │   ├── spooler.py                    # Windows Print Spooler Win32 API
│   │   ├── dnp_rx1hs.py                  # Profile dao cắt tự động DNP DS-RX1HS
│   │   └── manager.py                    # Quản lý hàng đợi và in thẻ kiểm tra
│   ├── sharing/                          # CHIA SẺ MẠNG LAN & MÃ QR
│   │   └── token_manager.py              # Token 128-bit và mã QR tự động
│   ├── core/                             # LÕI NGHIỆP VỤ HỆ THỐNG
│   │   ├── config.py                     # Cấu hình persistent JSON & mã PIN
│   │   ├── events.py                     # Quản lý sự kiện và thư mục ảnh
│   │   └── logger.py                     # Ghi nhật ký xoay vòng UTF-8
│   ├── tests/                            # 25 TEST CASES TỰ ĐỘNG (100% PASS)
│   ├── main.py                           # Điểm khởi chạy chính Desktop GUI
│   └── server.py                         # Dịch vụ tải ảnh di động nền qua QR
├── VietPhotoBooth.iss                    # Kịch bản Inno Setup 6
├── vietphotobooth.spec                   # Kịch bản PyInstaller
└── DOCS_HUONG_DAN_SU_DUNG.md             # Cẩm nang vận hành tiếng Việt chi tiết
```

---

## 🚀 HƯỚNG DẪN CÀI ĐẶT VÀ VẬN HÀNH

### 1. Cài đặt nhanh bằng bộ cài (.exe)
Tải và chạy file:
```
dist_installer\VietPhotoBooth-Setup.exe
```
Khởi động ứng dụng từ biểu tượng **VietPhotoBooth** trên Desktop.

### 2. Chạy từ mã nguồn (Môi trường phát triển Python 3.12)
```powershell
# 1. Kích hoạt môi trường và cài đặt dependencies
py -3.12 -m pip install PySide6 opencv-python pillow numpy pywin32 qrcode fastapi "uvicorn[standard]" pytest pyinstaller

# 2. Khởi chạy ứng dụng Desktop
py -3.12 vietphotobooth/main.py

# Hoặc khởi động trực tiếp vào chế độ Kiosk toàn màn hình
py -3.12 vietphotobooth/main.py --kiosk
```

### 3. Chạy toàn bộ kiểm thử tự động
```powershell
$env:PYTHONIOENCODING="utf-8"
py -3.12 -m pytest vietphotobooth/tests -v
```
*(Đạt 25/25 test cases thành công 100%)*

### 4. Đóng gói lại bộ cài đặt mới
```powershell
# 1. Biên dịch file nhị phân độc lập bằng PyInstaller
py -3.12 -m PyInstaller vietphotobooth.spec --clean -y

# 2. Sao chép tài nguyên Assets vào thư mục bản dựng
Copy-Item -Path "Assets" -Destination "dist\VietPhotoBooth\Assets" -Recurse -Force

# 3. Tạo file cài đặt Setup bằng Inno Setup
iscc VietPhotoBooth.iss
```
File cài đặt hoàn chỉnh: `dist_installer\VietPhotoBooth-Setup.exe`.

---

## 📖 TÀI LIỆU HƯỚNG DẪN CHI TIẾT
- [Cẩm nang hướng dẫn sử dụng phần mềm VietPhotoBooth](file:///c:/Users/Admin/Documents/photobooth/DOCS_HUONG_DAN_SU_DUNG.md)
- [Bảng tương thích máy ảnh DSLR/Mirrorless & cài driver](file:///c:/Users/Admin/Documents/photobooth/DOCS_TUONG_THICH_MAY_ANH.md)
- [Hướng dẫn cấu hình máy in & profile cắt đôi DNP DS-RX1HS](file:///c:/Users/Admin/Documents/photobooth/DOCS_CAU_HINH_MAY_IN.md)
- [Hướng dẫn thiết kế template & nhập khung PNG ngoài](file:///c:/Users/Admin/Documents/photobooth/DOCS_THIET_KE_TEMPLATE.md)
- [Hướng dẫn sao lưu, phục hồi và bảo mật mã PIN](file:///c:/Users/Admin/Documents/photobooth/DOCS_SAO_LUU_PHUC_HOI.md)
