# BÁO CÁO ĐIỀU TRA: HIỆN TƯỢNG XUẤT HIỆN PHIÊN BẢN v1.5.5 THAY VÌ v1.6.6

**Dự án:** 1998 TEAM — Photobooth  
**Phiên bản mong muốn:** v1.6.6 (Build 166)  
**Phiên bản ghi nhận:** v1.5.5  
**Thời điểm ghi nhận:** 01/11/2026 12:05:12  
**Trạng thái xử lý:** ĐÃ XÁC ĐỊNH CHÍNH XÁC NGUYÊN NHÂN GỐC 100%. Chưa xóa hoặc thay đổi bất kỳ file cài đặt nào.

---

## 1. XÁC ĐỊNH EXECUTABLE THỰC TẾ ĐANG CHẠY

Qua kiểm tra tiến trình hệ thống bằng Windows Management Instrumentation (WMI / CIM):

| Thuộc tính | Giá trị thực tế trên hệ thống |
| :--- | :--- |
| **Process ID (PID)** | `13160` |
| **Tên tiến trình** | `1998TeamPhotobooth.exe` |
| **Đường dẫn thực thi (Executable Path)** | `C:\Users\Admin\AppData\Local\Temp\pytest-of-Admin\pytest-281\test_live_isolated_upgrade_pre0\LiveUpgradeEnv\InstalledApp\1998TeamPhotobooth.exe` |
| **Thư mục làm việc** | `C:\Users\Admin\AppData\Local\Temp\pytest-of-Admin\pytest-281\test_live_isolated_upgrade_pre0\LiveUpgradeEnv\InstalledApp` |
| **Command Line khởi chạy** | `"C:\Users\Admin\AppData\Local\Temp\pytest-of-Admin\pytest-281\test_live_isolated_upgrade_pre0\LiveUpgradeEnv\InstalledApp\1998TeamPhotobooth.exe"` |
| **Thời điểm sinh tiến trình** | `01/11/2026 12:05:12` (Khởi chạy từ `explorer.exe` PID `15888`) |
| **Dung lượng nhị phân** | `10,619,604` bytes (~10.12 MB) |
| **Mã băm SHA256** | `64449cef1c29f3185dc71a86718dfce348c11294398ff3da39b9f0ca02320ada` |

---

## 2. NGUỒN GỐC XUẤT HIỆN BẢN v1.5.5

Tệp executable trên **KHÔNG PHẢI** do mã nguồn dự án bị rollback. Mã nguồn dự án vẫn nằm ở `v1.6.6 Build 166`.  
Nguồn gốc phát sinh v1.5.5 như sau:

1. **Bộ cài đặt gốc phát sinh file:**
   - Tập tin: `dist_installer\1998-TEAM-Setup-v1.5.5-Build155.exe` (Bộ cài lịch sử được tạo từ ngày 23/10/2026).
2. **Kịch bản kiểm thử kích hoạt:**
   - Trong quá trình chạy bộ test tự động (`pytest`), bài test `test_live_isolated_upgrade_preserves_all_data` trong tệp [`vietphotobooth/tests/test_v155_release_audit.py`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/tests/test_v155_release_audit.py#L505-L572) đã thực thi lệnh cài đặt bộ cài `1998-TEAM-Setup-v1.5.5-Build155.exe` vào thư mục tạm `tmp_path`.
3. **Cơ chế chiếm đoạt Shortcut và Registry của Inno Setup:**
   - Khi `1998-TEAM-Setup-v1.5.5-Build155.exe` chạy cài đặt ngầm:
     - Inno Setup đọc định nghĩa `[Icons]` trong `VietPhotoBooth.iss`.
     - Vì bài test không truyền cờ `/NOICONS` và `/TASKS=""`, Inno Setup đã **ghi đè shortcut ngoài Desktop** (`C:\Users\Admin\Desktop\1998 TEAM – Photobooth.lnk`) và **Start Menu** (`C:\Users\Admin\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\1998 TEAM – Photobooth.lnk`).
     - Cả hai shortcut này bị đổi đường dẫn đích (`TargetPath`) trỏ thẳng vào:  
       `C:\Users\Admin\AppData\Local\Temp\pytest-of-Admin\pytest-281\test_live_isolated_upgrade_pre0\LiveUpgradeEnv\InstalledApp\1998TeamPhotobooth.exe`.
     - Inno Setup đồng thời ghi đè khóa Registry gỡ cài đặt:  
       `HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{676858C6-2A30-4E77-A479-D21F91264A09}_is1`  
       thành `Version: 1.5.5`, `InstallLocation: C:\Users\Admin\AppData\Local\Temp\...`.
4. **Lỗi không dọn dẹp tiến trình trong bài test:**
   - Cuối kịch bản nâng cấp `run_update.ps1`, script gọi `Invoke-AppLaunch` để bật ứng dụng vừa cài đặt lên.
   - Bài test có hàm `_cleanup_test_spawned_processes` tại dòng 205 để tắt tiến trình này sau khi test xong.
   - Tuy nhiên, tại dòng 219 của `test_v155_release_audit.py`:  
     Lệnh PowerShell `Where-Object { $_.ExecutablePath ... }` khi truyền qua chuỗi `powershell -Command "..."` trong Python đã bị lỗi cú pháp do ký tự `$_` bị PowerShell hiểu nhầm thành biến rỗng. Kết quả là lệnh tìm PID bị lỗi ngầm (`ParserError`), không tắt được tiến trình `1998TeamPhotobooth.exe` (v1.5.5).
   - Tiến trình này tiếp tục chạy ngầm, hiển thị cửa sổ v1.5.5 trên màn hình Desktop.
   - Khi người dùng click vào icon ngoài Desktop, shortcut tiếp tục mở lại chính bản v1.5.5 trong thư mục Temp này.

---

## 3. ĐỐI CHIẾU CÁC VỊ TRÍ PHIÊN BẢN TRÊN TOÀN HỆ THỐNG

| Vị trí | Phiên bản | Build | Đường dẫn / Ghi chú |
| :--- | :--- | :--- | :--- |
| **Mã nguồn Single Source of Truth** | **1.6.6** | **166** | `vietphotobooth/version.py` (Chuẩn xác 100%) |
| **Giao diện khi chạy từ mã nguồn** | **1.6.6** | **166** | `py -3.12 -m vietphotobooth.main` (Hiển thị đúng `v1.6.6`) |
| **Bản Build PyInstaller độc lập** | **1.6.6** | **166** | `dist\1998TeamPhotobooth\1998TeamPhotobooth.exe` (10.7 MB, tạo lúc 10:58 ngày 01/11/2026) |
| **Bộ cài đặt Windows Setup** | **1.6.6** | **166** | `dist_installer\1998-TEAM-Setup-v1.6.6-Build166.exe` (95.3 MB, tạo lúc 10:59 ngày 01/11/2026) |
| **Thư mục cài đặt cũ Windows** | **1.6.1** | **161** | `C:\Users\Admin\AppData\Local\Programs\1998TeamPhotobooth\1998TeamPhotobooth.exe` (Tạo ngày 24/10/2026) |
| **Tiến trình đang chạy hiển thị lỗi** | **1.5.5** | **155** | `C:\Users\Admin\AppData\Local\Temp\pytest-of-Admin\...\1998TeamPhotobooth.exe` (Sinh ra từ bài test `test_v155_release_audit.py`) |
| **Desktop Shortcut hiện tại** | **1.5.5** | **155** | `C:\Users\Admin\Desktop\1998 TEAM – Photobooth.lnk` (Đang trỏ nhầm vào Temp v1.5.5 do Inno Setup test ghi đè) |
| **Start Menu Shortcut hiện tại** | **1.5.5** | **155** | `Start Menu\Programs\1998 TEAM – Photobooth.lnk` (Đang trỏ nhầm vào Temp v1.5.5) |

---

## 4. KẾT LUẬN NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE)

1. **Mã nguồn dự án KHÔNG HỀ BỊ ROLLBACK.** Mã nguồn, logic camera, Face/Eye AF và toàn bộ tính năng vẫn đang ở đúng phiên bản **v1.6.6 Build 166**.
2. Hiện tượng xuất hiện bản v1.5.5 là do **hiệu ứng phụ (side-effect) của bài kiểm thử tích hợp Inno Setup** (`test_live_isolated_upgrade_preserves_all_data`):
   - Chạy trực tiếp bộ cài thật `1998-TEAM-Setup-v1.5.5-Build155.exe` mà không có cờ cô lập shortcut (`/NOICONS`).
   - Hàm dọn dẹp tiến trình trong bài test bị lỗi cú pháp PowerShell, để sót lại tiến trình v1.5.5 đang mở trên màn hình.
   - Shortcut trên Desktop và Start Menu bị trỏ nhầm về thư mục `Temp\pytest-of-Admin\...`.

---

## 5. PHƯƠNG ÁN KHẮC PHỤC AN TOÀN (ĐỀ XUẤT)

Theo nguyên tắc an toàn, hiện tại chưa có thay đổi nào được áp dụng. Đề xuất quy trình khắc phục an toàn như sau:

### Bước 1: Đóng tiến trình thử nghiệm v1.5.5 đang chạy
- Tắt an toàn tiến trình PID `13160` đang chạy từ thư mục `Temp\pytest-of-Admin\...`.

### Bước 2: Khôi phục lại Shortcut Desktop và Start Menu
- Cập nhật lại đường dẫn đích của `C:\Users\Admin\Desktop\1998 TEAM – Photobooth.lnk` và Start Menu về đúng thư mục cài đặt thực tế của ứng dụng (`C:\Users\Admin\AppData\Local\Programs\1998TeamPhotobooth\1998TeamPhotobooth.exe` hoặc bản build `dist\1998TeamPhotobooth\1998TeamPhotobooth.exe`).

### Bước 3: Sửa triệt để mã nguồn kiểm thử `test_v155_release_audit.py`
1. Thêm cờ `/NOICONS` và `/TASKS=""` khi gọi Inno Setup trong môi trường test để Inno Setup **không bao giờ được phép đè shortcut Desktop của người dùng**:
   ```python
   # Trong generate_updater_runner_script hoặc lệnh gọi test:
   # Thêm đối số: /NOICONS /TASKS=""
   ```
2. Sửa lỗi cú pháp PowerShell trong `_cleanup_test_spawned_processes` dòng 219 (dùng `psutil` hoặc `wmic` / script chuẩn không bị nuốt biến `$_`) để đảm bảo mọi tiến trình sinh ra trong `tmp_path` đều bị tắt 100% sau khi bài test hoàn tất.
3. Không tự động khởi chạy GUI (`Invoke-AppLaunch`) khi chạy trong chế độ headless automated test.
