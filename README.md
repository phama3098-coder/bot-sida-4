# VIETPHOTOBOOTH — PHẦN MỀM PHOTOBOOTH CHUYÊN NGHIỆP CHO WINDOWS

![Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%2064--bit-blue)
![Python](https://img.shields.io/badge/Python-3.12-brightgreen)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success)
![License](https://img.shields.io/badge/License-MIT-orange)

**VietPhotoBooth** là giải pháp phần mềm Photobooth thương mại hoàn chỉnh, được phát triển chuyên biệt cho môi trường **Windows 10 và Windows 11 (64-bit)**. 

Phần mềm được nghiên cứu, phát triển dựa trên việc kế thừa mô hình của dự án mã nguồn mở [PhotoboothProject/photobooth](https://github.com/PhotoboothProject/photobooth), đồng thời tái thiết kế và xây dựng lại toàn bộ lõi xử lý để khắc phục các hạn chế phụ thuộc vào Linux, loại bỏ hoàn toàn yêu cầu cấu hình thủ công phức tạp (Apache, PHP, WSL2, CUPS) và tối ưu hóa tối đa cho các thiết bị phần cứng thực tế trên Windows (máy ảnh DSLR/Mirrorless, webcam UVC, máy in ảnh nhiệt DNP DS-RX1HS).

---

## 🌟 TÍNH NĂNG NỔI BẬT

1. **Giao diện Kiosk 100% Tiếng Việt**: Thiết kế hiện đại, nút bấm kích thước lớn, phản hồi cảm ứng mượt mà, phù hợp cho màn hình cảm ứng từ 15 đến 32 inch.
2. **Quy trình chụp ảnh hoàn chỉnh**:
   - Màn hình chờ hiển thị Live View thời gian thực và thông điệp sự kiện.
   - Đếm ngược trực quan (3s, 5s hoặc 10s) kèm hiệu ứng chớp flash và âm thanh.
   - Chụp loạt 3 hoặc 4 kiểu ảnh liên tiếp với thời gian nghỉ tạo dáng.
   - Tự động ghép loạt ảnh vào khung template theo chuẩn in ấn 300 DPI.
3. **Bộ Khung Ảnh (Template Engine 300 DPI)**:
   - **Dải 2x6 inch (600x1800 px)**: Bố cục 3 ảnh hoặc 4 ảnh truyền thống.
   - **Khổ 4x6 inch (1200x1800 px)**: Ghép đôi 2 dải 2x6 đặt cạnh nhau phục vụ dao cắt tự động của máy in nhiệt thăng hoa.
   - **Khổ 4x6 inch Ngang (1800x1200 px)**: Bố cục lưới và chân trang tùy biến.
4. **Hệ thống In ấn Windows (Windows Print Spooler)**:
   - Tích hợp sâu Win32 API (`win32print`), không qua CUPS hay dòng lệnh trung gian.
   - Quản lý hàng đợi in chuyên nghiệp với mã định danh `JOB-YYYYMMDD-XXXX`.
   - Cấu hình chuyên dụng cho máy in ảnh nhiệt **DNP DS-RX1HS**, Citizen CY-02, HiTi P525L.
   - Không bao giờ xóa hoặc làm mất ảnh của khách nếu máy in gặp sự cố (hết giấy, kẹt giấy). Hỗ trợ in thử (Test Card) và in lại ảnh cũ.
5. **Chia sẻ ảnh qua mã QR trong mạng nội bộ (LAN Sharing)**:
   - Máy chủ nội bộ tích hợp tự động nhận diện IP máy trạm (ví dụ `192.168.1.150:8080`).
   - Mã truy cập ngẫu nhiên 128-bit an toàn, bảo vệ chống duyệt thư mục trái phép.
   - Khách dùng camera điện thoại quét QR và tải ảnh gốc trực tiếp mà **hoàn toàn không cần Internet hay 4G**.
   - Có thời hạn hết hạn và nút thu hồi tức thì từ trang quản trị.
6. **Quản lý sự kiện và thư viện ảnh**:
   - Phân cấp thư mục chuẩn: `Events/<Tên_Sự_Kiện>/Originals, Final, Thumbnails, Templates, Logs`.
   - Tạo sự kiện mới, đổi tên, chuyển sự kiện linh hoạt.
   - Giám sát và cảnh báo dung lượng ổ đĩa tự động.
   - Xuất toàn bộ ảnh sự kiện thành 1 file ZIP duy nhất để bàn giao khách hàng.
7. **Bảo mật và Quản trị**:
   - Trang quản trị với 10 phân hệ đầy đủ chức năng, được bảo vệ bằng mã PIN (bàn phím số ảo cảm ứng).
8. **Đóng gói bộ cài Windows duy nhất**:
   - Bộ cài độc lập `VietPhotoBooth-Setup.exe` (khoảng 57 MB), cài đặt nhanh chóng, không yêu cầu quyền Admin, tự động tạo lối tắt Desktop và Start Menu, tích hợp sẵn trình gỡ cài đặt sạch sẽ.

---

## 📁 CẤU TRÚC THƯ MỤC DỰ ÁN

```
photobooth/
├── dist_installer/
│   └── VietPhotoBooth-Setup.exe          # Bộ cài đặt Windows hoàn chỉnh
├── vietphotobooth/
│   ├── camera/
│   │   ├── base.py                       # Lớp trừu tượng CameraAdapter
│   │   ├── simulator.py                  # Bộ giả lập máy ảnh (Camera Simulator)
│   │   ├── directshow.py                 # Điều khiển Webcam UVC & Thẻ thu hình
│   │   ├── digicam.py                    # Bridge điều khiển DSLR Nikon, Canon, Sony
│   │   ├── compatibility.py              # Cơ sở dữ liệu tra cứu tương thích model
│   │   └── manager.py                    # Quản lý tập trung nguồn camera
│   ├── core/
│   │   ├── config.py                     # Quản lý cấu hình persistent JSON & mã PIN
│   │   ├── events.py                     # Quản lý sự kiện và phân cấp thư mục
│   │   ├── logger.py                     # Ghi nhật ký hệ thống xoay vòng
│   │   └── state_machine.py              # State machine điều phối chu kỳ chụp ảnh
│   ├── processing/
│   │   ├── image_processor.py            # Cắt ảnh bảo toàn tỷ lệ, bộ lọc màu
│   │   └── template_engine.py            # Ghép khung ảnh 2x6, 4x6 và dual-cut 300 DPI
│   ├── printing/
│   │   ├── spooler.py                    # Windows Print Spooler Win32 API
│   │   ├── dnp_rx1hs.py                  # Profile máy in nhiệt DNP DS-RX1HS
│   │   └── manager.py                    # Hàng đợi in, in thử và theo dõi trạng thái
│   ├── sharing/
│   │   └── token_manager.py              # Quản lý token chia sẻ và sinh mã QR
│   ├── ui/
│   │   ├── templates/
│   │   │   ├── index.html                # Giao diện Kiosk cảm ứng tiếng Việt
│   │   │   ├── admin.html                # Bảng quản trị 10 phân hệ chức năng
│   │   │   └── guest.html                # Trang tải ảnh trên di động cho khách
│   │   └── static/                       # Tài nguyên tĩnh CSS, JS, hình ảnh
│   ├── tests/                            # Bộ kiểm thử tự động toàn diện
│   │   ├── test_camera.py
│   │   ├── test_config.py
│   │   ├── test_events.py
│   │   ├── test_printing.py
│   │   ├── test_processing_and_templates.py
│   │   ├── test_session_and_server.py
│   │   └── test_sharing_and_qr.py
│   ├── server.py                         # Máy chủ FastAPI & REST APIs
│   └── main.py                           # Điểm khởi chạy chính của ứng dụng
├── upstream_photobooth/                  # Mã nguồn gốc tham chiếu PhotoboothProject
├── VietPhotoBooth.iss                    # Kịch bản đóng gói Inno Setup 6
├── vietphotobooth.spec                   # Kịch bản biên dịch PyInstaller
├── DOCS_HUONG_DAN_SU_DUNG.md             # Hướng dẫn sử dụng tiếng Việt chi tiết
├── DOCS_TUONG_THICH_MAY_ANH.md           # Bảng tương thích máy ảnh & cài driver
├── DOCS_CAU_HINH_MAY_IN.md               # Hướng dẫn cấu hình máy in & DNP DS-RX1HS
├── DOCS_THIET_KE_TEMPLATE.md             # Hướng dẫn thiết kế template 2x6 và 4x6
└── DOCS_SAO_LUU_PHUC_HOI.md              # Hướng dẫn sao lưu, cập nhật và gỡ cài đặt
```

---

## 🚀 HƯỚNG DẪN KHỞI CHẠY VÀ PHÁT TRIỂN

### 1. Cài đặt môi trường phát triển (Python 3.12)
```powershell
py -3.12 -m pip install fastapi "uvicorn[standard]" pillow pywin32 opencv-python "qrcode[pil]" jinja2 python-multipart requests pytest pyinstaller
```

### 2. Chạy ứng dụng từ mã nguồn
```powershell
py -3.12 vietphotobooth/main.py
```
Ứng dụng sẽ tự động mở trình duyệt tại: `http://localhost:8080/`.

### 3. Chạy bộ kiểm thử tự động
```powershell
py -3.12 -m pytest vietphotobooth/tests -v
```

### 4. Đóng gói bộ cài đặt Windows (.exe)
```powershell
# 1. Biên dịch file nhị phân độc lập
py -3.12 -m PyInstaller vietphotobooth.spec --noconfirm

# 2. Đóng gói bộ cài đặt Setup bằng Inno Setup Compiler
iscc VietPhotoBooth.iss
```
File cài đặt hoàn chỉnh sẽ xuất hiện tại:
`dist_installer\VietPhotoBooth-Setup.exe`

---

## 📚 TÀI LIỆU CHI TIẾT BÀN GIAO
- [Hướng dẫn sử dụng chi tiết](file:///c:/Users/Admin/Documents/photobooth/DOCS_HUONG_DAN_SU_DUNG.md)
- [Bảng tương thích máy ảnh & cài đặt driver](file:///c:/Users/Admin/Documents/photobooth/DOCS_TUONG_THICH_MAY_ANH.md)
- [Hướng dẫn cấu hình máy in & profile DNP DS-RX1HS](file:///c:/Users/Admin/Documents/photobooth/DOCS_CAU_HINH_MAY_IN.md)
- [Hướng dẫn thiết kế template 2x6 và 4x6 300 DPI](file:///c:/Users/Admin/Documents/photobooth/DOCS_THIET_KE_TEMPLATE.md)
- [Hướng dẫn sao lưu, phục hồi và gỡ cài đặt](file:///c:/Users/Admin/Documents/photobooth/DOCS_SAO_LUU_PHUC_HOI.md)
