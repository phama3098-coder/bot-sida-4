# 1998 TEAM PHOTOBOOTH — RELEASE NOTES v1.6.6 (BUILD 166)

**Ngày phát hành:** 2026-11-01  
**Trạng thái phát hành:** Release Candidate (RC)  
**Nhà phát triển:** 1998 Studio phóng sự cưới  

---

## 1. TỔNG QUAN PHIÊN BẢN v1.6.6
Phiên bản **v1.6.6 – Build 166** là bản cập nhật tiếp nối kiến trúc Unified AF Engine của v1.6.5, tập trung nâng cấp độ tin cậy vận hành thực tế thông qua hai hệ thống cốt lõi: **Printing Hardening** (Tối ưu hóa và an toàn in ấn nhiệt) và **Studio Audio System** (Hệ thống âm thanh tương tác studio đa luồng độ trễ cực thấp).

Phiên bản này được xây dựng trên nguyên tắc bảo toàn tính ổn định cao nhất:
- Không thay đổi backend Nikon MAID Type0026.
- Giữ nguyên kiến trúc Unified Face/Eye AF Engine, Capture Transaction Token (`tx_id`) và Watchdog 2.2 giây.
- Không can thiệp driver hệ thống của Windows.

---

## 2. CÁC TÍNH NĂNG & NÂNG CẤP CHÍNH

### A. Printing Hardening (In ấn chuyên nghiệp & an toàn nhiệt)
1. **Print Preset Catalog (`vietphotobooth/printing/presets.py`):**
   - Hỗ trợ hồ sơ cấu hình chuyên biệt theo từng dòng máy in nhiệt phổ biến tại thị trường photobooth Việt Nam: DNP DS620, DNP RX1HS, Citizen CY-02, HiTi P525L, Fujifilm ASK-300 và máy in tiêu chuẩn.
   - Định nghĩa chính xác kích thước vùng in vật lý, độ phân giải DPI, tỷ lệ khung hình và chế độ in (4x6", 2x6" strip 2 dải, 6x8").
2. **Safety Margin Configurable (Vùng an toàn chống mất mép):**
   - Thay vì ép cứng tỉ lệ zoom 98%, hệ thống cho phép bật/tắt và tùy chỉnh Safety Margin (98% – 100%) linh hoạt theo từng model máy in và kích thước khung ảnh.
3. **Smart Auto-Orientation (Tự động xoay thông minh):**
   - Tự động tính toán hướng xoay (Landscape / Portrait) dựa trên so sánh tỷ lệ khung hình đầu vào với hướng khay giấy vật lý thực tế của máy in.
4. **Thermal Pacing (Bảo vệ đầu in nhiệt):**
   - Cung cấp cơ chế giãn cách lệnh in (Thermal Pacing delay) cấu hình linh hoạt theo từng model, chống hiện tượng sốc nhiệt, kẹt ribbon hoặc quá nhiệt motor kéo giấy khi phục vụ sự kiện đông khách liên tục.
5. **Giao diện điều khiển tại Printing Settings:**
   - Bổ sung các checkbox và input điều khiển Safety Margin, Auto Orientation và Printer Preset trực quan trong trang Cài đặt Máy in.

### B. Studio Audio System (Âm thanh studio tương tác)
1. **Kiến trúc QSoundEffect độ trễ cực thấp:**
   - Module `vietphotobooth/audio/` độc lập, vận hành trên nền `PySide6.QtMultimedia.QSoundEffect` sử dụng buffer âm thanh PCM nạp sẵn trong bộ nhớ, loại bỏ hoàn toàn độ trễ khi phát trong Kiosk.
2. **Bộ âm thanh tương tác chuẩn phòng chụp:**
   - **Countdown Tick (`countdown_tick.wav`):** Âm tích tắc đếm ngược đồng bộ từng giây (giây 3, 2, 1).
   - **Vietnamese Voice Guide (`countdown_voice_vi.wav`):** Giọng thông báo tiếng Việt chuẩn studio ("3, 2, 1... Cười lên nào!") giúp khách hàng tự nhiên tạo dáng trước ống kính.
   - **Studio Shutter Click (`shutter_click.wav`):** Âm thanh màn trập cơ khí chân thực ngay tại thời điểm phơi sáng, mang lại phản hồi xúc giác âm thanh tin cậy cho khách.
3. **Đồng bộ Kiosk Lifecycle:**
   - Quản lý trạng thái âm thanh gắn liền với luồng chụp của KioskPage. Tự động ngắt khi chuyển màn hình hoặc kết thúc phiên chụp.

### C. UI/UX & Kiosk Lifecycle Hardening
1. **Comprehensive Lifecycle Cleanup (`KioskPage.cleanup`):**
   - Ngắt dọn dẹp triệt để `CameraLiveViewWorker` (QThread), `FaceDetectionService` worker thread, camera polling timers và audio sound effects khi Kiosk đóng hoặc bị hủy.
2. **Khắc phục triệt để lỗi Modal Dialog Blocking:**
   - Loại bỏ các hộp thoại `QMessageBox.warning` modal trong luồng chụp tự động, tránh hiện tượng treo tiến trình khi camera gặp sự cố ngắt kết nối bất ngờ.
3. **Sửa lỗi giao diện:**
   - Khắc phục lỗi `NameError: name 'QCheckBox' is not defined` trong `vietphotobooth/desktop/widgets/printing_page.py`.

---

## 3. THÔNG TIN ĐÓNG GÓI & CHECKSUM

| Thuộc tính | Giá trị chi tiết |
| :--- | :--- |
| **Tên ứng dụng** | 1998 TEAM — Photobooth |
| **Phiên bản (Version)** | `1.6.6` |
| **Số hiệu Build** | `166` |
| **Ngày build** | `2026-11-01` |
| **Tệp bộ cài đặt** | `1998-TEAM-Setup-v1.6.6-Build166.exe` |
| **Tệp cài đặt phụ** | `1998-TEAM-Photobooth-Setup-v1.6.6.exe` |
| **Dung lượng file** | `95,316,171 bytes (~90.90 MB)` |
| **Mã băm SHA-256** | `dc4b2824886330c3c85a79d1e97085872800c8cbf5a21a8d37b5443f53897c50` |
| **File Checksum** | `1998-TEAM-Setup-v1.6.6-Build166.exe.sha256` |

---

## 4. KẾT QUẢ KIỂM THỬ HỒI QUY TOÀN BỘ (FULL REGRESSION)
- **Tổng số ca kiểm thử:** `309 / 309 tests`
- **Tỷ lệ vượt qua:** `100% PASS`
- **Mã thoát (Exit code):** `0`
- **Thời gian chạy kiểm thử:** `207.16 giây`
- Không có bất kỳ hồi quy nào đối với hệ thống lấy nét Face/Eye AF, Nikon MAID Type0026, Transaction Token hay Kiosk Workflow.
