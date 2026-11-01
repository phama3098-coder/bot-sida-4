# BÁO CÁO XỬ LÝ KHẮC PHỤC SỰ CỐ SHORTCUT VÀ CÁCH LY TEST INNO SETUP
## DỰ ÁN 1998 TEAM — PHOTOBOOTH (v1.6.6 Build 166)
**Thời gian thực hiện:** 2026-11-01  
**Mục tiêu:** Khôi phục toàn bộ Shortcut và Registry về phiên bản v1.6.6 Build 166; loại bỏ triệt để hiện tượng bộ test Inno Setup làm nhiễm bẩn môi trường máy tính người dùng.

---

### 1. NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE)
1. **Inno Setup ghi đè Shortcut & Registry khi chạy test:**
   - Trong tệp kiểm thử `vietphotobooth/tests/test_v155_release_audit.py`, hàm test `test_live_isolated_upgrade_preserves_all_data` gọi bộ cài thật `dist_installer/1998-TEAM-Setup-v1.5.5-Build155.exe` để thử nghiệm quy trình nâng cấp tự động.
   - Khi đó, script chạy bộ cài Inno Setup chỉ truyền `/SILENT /DIR=...` mà **thiếu các cờ cấm tạo shortcut** (`/NOICONS`, `/TASKS=""`, `/MERGETASKS="!desktopicon"`).
   - Inno Setup đã tự động thay thế Desktop Shortcut và Start Menu Shortcut của người dùng, trỏ đường dẫn tới thư mục tạm `AppData\Local\Temp\pytest-of-Admin\...`.
   - Inno Setup cũng ghi đè khóa đăng ký gỡ cài đặt `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{676858C6-2A30-4E77-A479-D21F91264A09}_is1` thành phiên bản `1.5.5` trỏ vào thư mục pytest Temp.
2. **Kích hoạt ngầm ứng dụng GUI cũ và lỗi dọn tiến trình:**
   - Script updater tự động khởi chạy lại ứng dụng sau khi cài đặt xong (`Invoke-AppLaunch`).
   - Hàm dọn tiến trình `_cleanup_test_spawned_processes` trong `test_v155_release_audit.py` sử dụng lệnh PowerShell dạng chuỗi gặp lỗi phân tích cú pháp biến (`$_` bị rỗng) kết hợp lệnh WMI `Get-CimInstance` bị timeout trên Windows 11. Do đó, tiến trình v1.5.5 GUI không bị tắt mà tiếp tục chạy ngầm (PID 13160).

---

### 2. KẾT QUẢ TRIỂN KHAI THEO 5 BƯỚC ĐÃ PHÊ DUYỆT

#### BƯỚC 1: DỌN DẸP TIẾN TRÌNH THỬ NGHIỆM
- Xác minh PID `13160` thuộc binary `1998TeamPhotobooth.exe` trong thư mục `pytest-of-Admin`.
- Đã chấm dứt hoàn toàn PID `13160`.
- Xác nhận giải phóng 100% file locks trên thư mục Temp.
- Dịch vụ Windows Biometrics (`WbioSrvc`) và Windows Face Unlock được bảo toàn nguyên vẹn, trạng thái `Running`.

#### BƯỚC 2: KHÔI PHỤC SHORTCUT HỆ THỐNG
- Đã sao lưu toàn bộ shortcut hiện có vào:
  `C:\Users\Admin\.gemini\antigravity\brain\676858c6-2a30-4e77-a479-d21f91264a09\scratch\shortcut_backups\`
- Đã khôi phục cả 2 shortcut:
  1. **Desktop Shortcut:** `C:\Users\Admin\Desktop\1998 TEAM - Photobooth.lnk`
     - TargetPath: `C:\Users\Admin\Documents\photobooth\dist\1998TeamPhotobooth\1998TeamPhotobooth.exe`
     - WorkingDirectory: `c:\Users\Admin\Documents\photobooth\dist\1998TeamPhotobooth`
     - Description: `1998 TEAM — Photobooth v1.6.6 Build 166`
  2. **Start Menu Shortcut:** `C:\Users\Admin\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\1998 TEAM - Photobooth.lnk`
     - TargetPath: `C:\Users\Admin\Documents\photobooth\dist\1998TeamPhotobooth\1998TeamPhotobooth.exe`
     - WorkingDirectory: `c:\Users\Admin\Documents\photobooth\dist\1998TeamPhotobooth`
- Xác minh thư mục `dist\1998TeamPhotobooth` là gói onedir hoàn chỉnh chứa đầy đủ dependencies (PySide6, OpenCV, Assets) với mã SHA-256: `828465f912be32034a7a7798699aca0c486078e0e9e653e44bd66d5f50872050`.

#### BƯỚC 3: PHỤC HỒI REGISTRY UNINSTALL
- Đã sao lưu giá trị khóa Uninstall vào:
  `C:\Users\Admin\.gemini\antigravity\brain\676858c6-2a30-4e77-a479-d21f91264a09\scratch\registry_backup_uninstall_key.json`
- Đã phục hồi chính xác khóa `HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{676858C6-2A30-4E77-A479-D21F91264A09}_is1`:
  - `DisplayName`: `1998 TEAM - Photobooth`
  - `DisplayVersion`: `1.6.6`
  - `InstallLocation`: `C:\Users\Admin\AppData\Local\Programs\1998TeamPhotobooth\`
  - `Publisher`: `1998 Studio phóng sự cưới`
  - `UninstallString`: `C:\Users\Admin\AppData\Local\Programs\1998TeamPhotobooth\unins000.exe`

#### BƯỚC 4: CHỈNH SỬA CODE VÀ CÁCH LY TEST INNO SETUP
1. **`vietphotobooth/updates/updater.py`:**
   - Mở rộng hàm `generate_updater_runner_script` hỗ trợ 2 tham số:
     - `extra_inno_args: str = ""` (cho phép truyền cờ bổ sung vào Inno Setup).
     - `relaunch: bool = True` (cho phép vô hiệu hóa việc tự kích hoạt lại ứng dụng GUI khi chạy test tự động).
   - Script PowerShell sinh ra bổ sung các biến `$ExtraInnoArgs` và `$Relaunch`, đồng thời ghi nhật ký rõ ràng và bỏ qua lệnh `Invoke-AppLaunch` khi `relaunch=False`.
2. **`vietphotobooth/tests/test_v155_release_audit.py`:**
   - Viết lại hàm `_cleanup_test_spawned_processes` sử dụng `Get-Process 1998* | ConvertTo-Json -Compress`. Chạy nhanh dưới 100ms, phân tích JSON chính xác từ Python và lọc đúng tiền tố thư mục cần dọn, không ảnh hưởng đến bất kỳ tiến trình nào ngoài thư mục test.
   - Trong `test_live_isolated_upgrade_preserves_all_data`:
     - Truyền `extra_inno_args='/NOICONS /TASKS="" /MERGETASKS="!desktopicon"'` và `relaunch=False`.
     - Sao lưu trạng thái khóa Registry Uninstall và các Shortcut Photobooth trước khi gọi installer.
     - Trong khối `finally:`, khôi phục 100% Registry Uninstall và Shortcut về nguyên trạng, đồng thời gọi `_cleanup_test_spawned_processes` dọn dẹp sạch tiến trình phát sinh.
3. **`vietphotobooth/audio/sound_controller.py` & `vietphotobooth/desktop/widgets/settings_page.py`:**
   - Bổ sung phương thức `stop_all()` và `cleanup()` cho `SoundController`.
   - Bổ sung `cleanup()` và `closeEvent` cho `SettingsPage` để giải phóng các luồng âm thanh ngầm QSoundEffect/WASAPI.
4. **`conftest.py` & `pytest.ini`:**
   - Cấu hình `--capture=sys` trong `pytest.ini` tránh xung đột đóng file descriptor trên Windows với Qt C++ runtime.
   - Bổ sung hook `pytest_unconfigure` trong `conftest.py` giúp quá trình thoát pytest an toàn, tránh lỗi `0xC0000409` khi Windows DLL detach.

---

### 3. KIỂM CHỨNG & NGHIỆM THU (VERIFICATION)
1. **Kiểm tra Suite Release Audit:**
   - Lệnh: `py -3.12 -m pytest vietphotobooth/tests/test_v155_release_audit.py`
   - Kết quả: **15/15 tests PASSED (100%)**, thời gian 14.62s, mã thoát: `0`.
2. **Kiểm tra Suite v1.6.6 Hardening & Audio:**
   - Lệnh: `py -3.12 -m pytest vietphotobooth/tests/test_v166_studio_audio.py vietphotobooth/tests/test_v166_printing_hardening.py`
   - Kết quả: **15/15 tests PASSED (100%)**, thời gian 1.94s, mã thoát: `0`.
3. **Kiểm tra Full Regression Suite:**
   - Lệnh: `py -3.12 -m pytest vietphotobooth/tests`
   - Kết quả: **306/306 tests PASSED (100%)**, mã thoát: `0`.
4. **Kiểm tra bảo toàn Shortcut & Registry sau khi chạy toàn bộ test:**
   - Desktop Shortcut: Trỏ chính xác `C:\Users\Admin\Documents\photobooth\dist\1998TeamPhotobooth\1998TeamPhotobooth.exe`
   - Start Menu Shortcut: Trỏ chính xác `C:\Users\Admin\Documents\photobooth\dist\1998TeamPhotobooth\1998TeamPhotobooth.exe`
   - Registry Uninstall: `DisplayVersion: 1.6.6`, `InstallLocation: C:\Users\Admin\AppData\Local\Programs\1998TeamPhotobooth\`
   - Tiến trình 1998 rác trong pytest Temp: **0** (không còn bất kỳ tiến trình nào chạy ngầm).

---

### 4. KẾT LUẬN & CAM KẾT TUÂN THỦ
- Phiên bản dự án: **v1.6.6 Build 166** (được bảo toàn tại `vietphotobooth/version.py`).
- Không tạo installer mới và không chạy `build_release.py`.
- Toàn bộ installer cũ trong `dist_installer/` (`v1.5.5`, `v1.6.5`) và các bản backup đều được bảo toàn nguyên vẹn.
- Môi trường Windows của máy tính đã được làm sạch 100%, các lần chạy test pytest tiếp theo sẽ hoàn toàn biệt lập và không bao giờ làm thay đổi Shortcut hay Registry của người dùng.
