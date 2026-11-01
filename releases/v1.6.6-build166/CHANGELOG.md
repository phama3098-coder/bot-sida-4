# CHANGELOG — 1998 TEAM PHOTOBOOTH

Tất cả các thay đổi đáng chú ý của dự án được ghi lại tại tài liệu này.  
Định dạng tuân thủ [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) và phiên bản theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.6.6] - 2026-11-01 (Build 166)

### Added
- **Printing Hardening Engine (`vietphotobooth/printing/presets.py`):**
  - Danh mục Preset máy in chuyên dụng cho DNP DS620, DNP RX1HS, Citizen CY-02, HiTi P525L, Fujifilm ASK-300 và Default Printer.
  - Hỗ trợ Safety Margin có thể cấu hình linh hoạt (mặc định 98% cho dòng DNP, hỗ trợ viền 100%).
  - Tính năng Smart Auto-Orientation tự động phát hiện và xoay ảnh khớp khổ giấy vật lý.
  - Thermal Pacing delay bảo vệ đầu in nhiệt khỏi sốc nhiệt hoặc kẹt ribbon trong các phiên in liên tục.
- **Studio Audio System (`vietphotobooth/audio/`):**
  - Module quản lý âm thanh tương tác `StudioAudioPlayer` sử dụng `PySide6.QtMultimedia.QSoundEffect` với buffer bộ nhớ độ trễ thấp.
  - Tài nguyên âm thanh WAV chuyên nghiệp:
    - `Assets/Audio/countdown_tick.wav`: Âm tích tắc đếm ngược đồng bộ nhịp giây.
    - `Assets/Audio/countdown_voice_vi.wav`: Giọng thông báo tiếng Việt chuẩn phòng chụp ("3, 2, 1... Cười lên nào!").
    - `Assets/Audio/shutter_click.wav`: Âm thanh màn trập cơ khí phản hồi khi chụp.
- **Kiosk Cleanup Lifecycle:**
  - Bổ sung hàm dọn dẹp toàn diện `KioskPage.cleanup()` nhằm dừng an toàn các QThread, timers, FaceDetectionService và audio effects khi tắt Kiosk.
- **Packaging Hidden Imports:**
  - Cập nhật `vietphotobooth.spec` bổ sung `PySide6.QtMultimedia`, `vietphotobooth.audio.*`, `vietphotobooth.printing.presets`.

### Fixed
- **UI Import Bug:** Sửa lỗi thiếu `QCheckBox` trong `PySide6.QtWidgets` tại `vietphotobooth/desktop/widgets/printing_page.py`.
- **Modal Block Bug:** Loại bỏ modal blocking `QMessageBox.warning` trong luồng chụp tự động Kiosk khi xảy ra lỗi camera ngắt kết nối.
- **Clean Test Execution:** Mocking và tự động giải phóng tài nguyên trong bài kiểm thử `test_v166_studio_audio.py` ngăn ngừa hiện tượng treo Qt event loop.

### Changed
- **Version Bump:** Cập nhật phiên bản từ `1.6.5` (Build 165) lên `1.6.6` (Build 166) trong `vietphotobooth/version.py` và `VietPhotoBooth.iss`.
- **Packaging Pipeline:** Tự động tạo bộ cài đặt Windows Inno Setup `1998-TEAM-Setup-v1.6.6-Build166.exe` và file kiểm tra SHA-256 song song.

---

## [1.6.5] - 2026-10-31 (Build 165)

### Added
- **Unified Face/Eye AF Engine:** Hợp nhất bộ máy lấy nét tự động nhận diện khuôn mặt và mắt giữa CameraPage và KioskPage.
- **Kiosk Clean UI:** Ẩn hoàn toàn bounding box và reticle trong KioskPage, giữ trải nghiệm trực quan cho khách hàng trong khi vẫn duy trì AF chính xác vào mắt.

---

## [1.6.4] - 2026-10-31 (Build 164)

### Added
- Pre-Capture Face/Eye AF trên Kiosk với Capture Transaction Token và Watchdog 2.2 giây.
- Khắc phục cạnh tranh lệnh AF trên Nikon D780 qua giao tiếp Type0026.
