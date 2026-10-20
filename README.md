# 1998 TEAM — PHOTOBOOTH DESKTOP CHO WINDOWS
### 1998 Studio Phóng Sự Cưới & Sự Kiện Chuyên Nghiệp

![Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%2064--bit-blue)
![GUI](https://img.shields.io/badge/GUI-PySide6%20%7C%20Qt%206-green)
![Python](https://img.shields.io/badge/Python-3.12-brightgreen)
![Tests](https://img.shields.io/badge/Tests-25%2F25%20Passing%20(100%25)-success)
![Theme](https://img.shields.io/badge/Theme-Navy%20%7C%20Black%20%7C%20Champagne%20Gold-gold)
![Installer](https://img.shields.io/badge/Installer-1998--Team--Photobooth--Setup.exe-orange)

**1998 TEAM — Photobooth** là ứng dụng **Desktop Native (Windows Native Window)** chuyên nghiệp chuẩn Studio cưới, vận hành trực tiếp trên **Windows 10 và Windows 11 (64-bit)**, không phải website trình duyệt, không dùng WebView bọc ngoài.

Ứng dụng được thiết kế riêng cho **1998 Studio phóng sự cưới**, tiệc cưới cao cấp, sinh nhật, sự kiện doanh nghiệp và các booth chụp ảnh lấy liền tự động với màn hình cảm ứng, tích hợp máy ảnh DSLR/Mirrorless/Webcam, in nhiệt DNP DS-RX1HS tự động cắt và chia sẻ ảnh qua mã QR trong mạng nội bộ.

---

## 🌟 ĐẶC ĐIỂM THƯƠNG HIỆU & NÂNG CẤP MỚI

### 1. Nhận Diện Thương Hiệu 1998 Studio Phóng Sự Cưới
- **Bộ nhận diện chuẩn xác**: Sử dụng logo gốc chính thức của **1998 Studio phóng sự cưới** làm logo chính, icon Windows `.ico` đa độ phân giải (16x16 đến 256x256).
- **Bảng màu Luxury Studio**: Xanh than đậm (`#0D1527`, `#0E1629`), Đen sâu thẳm (`#070A12`, `#050811`), Vàng Champagne (`#D4AF37`, `#E5C158`, `#F7E7CE`).
- **Nút bấm cảm ứng lớn**: Nút "📸 BẮT ĐẦU CHỤP" màu vàng champagne nổi bật, chữ tiếng Việt to rõ, dễ chạm, bố cục không bao giờ xuất hiện thanh cuộn ngang gây cản trở.
- **Thứ tự 6 phân hệ chuẩn**:
  1. `📸 Chụp Ảnh`
  2. `🖼️ Khung Ảnh`
  3. `📷 Máy Ảnh`
  4. `🖨️ Máy In`
  5. `📁 Sự Kiện & Thư Viện`
  6. `⚙️ Cài Đặt`

### 2. Màn Hình Chụp Ảnh Chuyên Nghiệp (Kiosk Live View)
- **Live View chiếm diện tích lớn nhất**: Khung ngắm tỷ lệ 3:2 mở rộng bao phủ trung tâm giao diện.
- **Thông báo mất kết nối chân thực**: Khi chưa cắm hoặc mất kết nối camera, hiển thị thông báo rõ ràng "CHƯA KẾT NỐI MÁY ẢNH" cùng nút "🔌 Kết Nối Lại Máy Ảnh", tuyệt đối không dùng hình người mô phỏng giả lập.
- **Thanh trạng thái trực quan**: Hiển thị trạng thái camera, độ phân giải hiện thời, bộ chọn số ảnh mỗi lượt (3 ảnh / 4 ảnh) và thời gian đếm ngược (3s / 5s / 10s).
- **Hậu kỳ sau chụp (Review Mode)**: Cho phép khách xem trước ảnh ghép hoàn chỉnh, Chụp lại (Retake), Lưu ảnh, Quét mã QR tải về điện thoại ngay, In ảnh tức thì và Hoàn tất phiên.

### 3. Hệ Thống Bộ Lọc Màu Sạch (Filter Studio Mở Rộng)
- **Thư viện khởi tạo sạch**: Xóa bỏ hoàn toàn các bộ lọc mẫu giả lập. Khởi tạo rỗng với thông báo thân thiện *"Chưa có bộ lọc. Hãy thêm bộ lọc của bạn"*.
- **Nút "+ Thêm Bộ Lọc"**: Cho phép mở ngay hộp thoại thiết kế màu sắc, chỉnh sửa 14 tham số (phơi sáng, nhiệt độ, sắc độ, mịn da YCbCr, vignette...) hoặc nạp file `.cube` 3D LUT từ Lightroom/Photoshop.
- **Quản lý toàn diện**: Tạo mới, đổi tên, nhân bản, lưu, xóa, xuất và nhập file cấu hình JSON.
- **Bảo toàn ảnh gốc (Non-Destructive)**: Ảnh chụp gốc được lưu nguyên bản 100% tại `Originals/`, không bao giờ bị ghi đè hay mất chi tiết.

### 4. Tách Biệt Dữ Liệu Khách Hàng Ngoài Thư Mục Cài Đặt
- Toàn bộ khung ảnh tự thiết kế, bộ lọc màu tự tạo, nhật ký hệ thống và ảnh sự kiện được lưu trữ tại `%LOCALAPPDATA%\1998TeamPhotobooth`. Khi cập nhật hoặc cài đặt lại phần mềm, tài sản của studio không bao giờ bị xóa mất.

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
