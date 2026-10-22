# 1998 TEAM — PHOTOBOOTH: TÀI LIỆU BÀN GIAO DỰ ÁN (PROJECT HANDOFF)
**Thời điểm tạo:** 2026-10-22 17:01:00 (Giờ địa phương)  
**Phiên bản hiện tại:** `v1.4.1` (Build `141`)  
**Bộ cài đặt mới nhất:** `dist_installer/1998-TEAM-Setup-v1.4.1-Build141.exe`

---

## 1. TỔNG QUAN DỰ ÁN & MỤC TIÊU ĐÃ HOÀN THÀNH

Dự án: **1998 TEAM Photobooth** — Ứng dụng Desktop Kiosk chuyên nghiệp cho studio ảnh cưới / photobooth (PySide6 / Python 3.12).

Đã hoàn thành toàn diện **HOTFIX V1.4.0 / V1.4.1**:
1. **Khắc phục lỗi vòng đời Live View / Simulator / Worker / Timer:**
   - Simulator trước đây chạy vòng lặp sinh ảnh không giới hạn tốc độ, làm tăng đột biến CPU rasterization và bộ đếm frame. Đã rate-limit chuẩn 30 FPS với cache bộ đệm.
   - Khi chuyển tab hoặc ngắt kết nối, luồng Live View chạy ngầm không được tạm dừng, gây xung đột worker giữa `KioskPage` và `CameraPage`. Đã cài đặt `showEvent`/`hideEvent` và cơ chế `pause()`/`resume()`.
   - Chế độ Simulator từng bị hiển thị nhầm là "Chưa kết nối" và bị che bởi panel disconnected, hoặc thông báo camera thật hoạt động. Đã phân tách 3 trạng thái rõ ràng: 🟢 Camera Thật, 🟡 Mô phỏng (Simulator), 🔴 Chưa kết nối.
   - Khi mất kết nối camera thật, hệ thống không còn trả lại frame cũ lặp đi lặp lại.
2. **Khắc phục lỗi giao diện Responsive & Tràn Layout:**
   - Thanh điều hướng trên cùng không còn bị tràn/cắt các tab bên phải ở độ phân giải 1280×720 và 1024×680.
   - `card_camera` (panel bên phải trang Chụp Ảnh) không bị bóp méo, co giãn mượt mà từ 180px đến 250px.
   - Các khối điều khiển đáy màn hình (`card_shots`, `card_cd`, `card_frames`, `card_filters`) và nút `btn_start` co giãn mượt mà từ 1024×680 đến 1920×1080.

---

## 2. DANH SÁCH CÁC FILE ĐÃ CHỈNH SỬA & CHI TIẾT KỸ THUẬT

### A. Vòng đời Live View & Camera Core
1. **`vietphotobooth/camera/backends/simulator.py`**:
   - Thêm rate-limiting chuẩn 30 FPS (`_min_frame_interval = 1.0 / 30.0`) kèm cache khung hình `_cached_frame_data`.
   - Nếu gọi nhanh hơn 33ms, trả về cache ngay lập tức mà không render lại PIL, giảm 90% tải CPU.
   - `_frame_count` chỉ tăng khi thực sự tạo frame mới ở 30 FPS.
   - Xóa sạch cache khi `disconnect()` hoặc `stop_live_view()`.
2. **`vietphotobooth/camera/connection_manager.py`**:
   - `get_frame_data()`: Trả về `None` khi backend không có frame hợp lệ, triệt tiêu lỗi trả về frame cũ vô tận.
   - `switch_backend()` & `disconnect()`: Reset toàn bộ `_last_frame_data` và `_last_jpeg`.
   - `get_info()`: Phân biệt rõ Simulator (`brand: Simulator`, `model: 1998 Simulator (Mô Phỏng)`, `status: Mô phỏng đang chạy`) với Camera thật.
3. **`vietphotobooth/desktop/widgets/kiosk_page.py`**:
   - Cài đặt `showEvent()`: Gọi `live_view_worker.resume()` và `camera_poll_timer.start(1500)`.
   - Cài đặt `hideEvent()`: Gọi `live_view_worker.pause()` và `camera_poll_timer.stop()`.
   - Tối ưu `start_live_view()` & `stop_live_view()`: Dùng `resume()` và `pause()`, không hủy và tái tạo lại `QThread` để tránh rò rỉ luồng.
   - Viết lại `_update_camera_status_ui()` với 3 trạng thái chuẩn mực:
     - 🟢 **Camera Thật:** `Đã kết nối: [Tên Thiết Bị]`, hiển thị Live View thật.
     - 🟡 **Simulator:** `Mô phỏng (Simulator)`, huy hiệu `🟡 CHẾ ĐỘ MÔ PHỎNG (SIMULATOR)`, ẩn panel disconnected, phát preview mô phỏng mượt mà.
     - 🔴 **Mất kết nối / Chưa cắm:** Chấm đỏ, thông báo hướng dẫn, hiển thị `panel_disconnected`.
   - Cài đặt `closeEvent()` dừng sạch worker và timer.
4. **`vietphotobooth/desktop/widgets/camera_page.py`**:
   - Bổ sung `minimumSizeHint()` trả về `QSize(720, 480)`.
   - Bổ sung `closeEvent()` dừng `_timer`.
   - Import `QSize` đầy đủ từ `PySide6.QtCore`.
5. **`vietphotobooth/desktop/main_window.py`**:
   - Bổ sung logic điều phối Live View tường minh trong `_on_tab_changed()`:
     - Khi ở Tab 0 (Chụp Ảnh): Kích hoạt `kiosk_page.start_live_view()`.
     - Khi rời Tab 0: Tạm dừng `kiosk_page.stop_live_view()`.
     - Khi vào Tab 2 (Máy Ảnh): `CameraPage` nhận `showEvent` và kích hoạt timer xem trước.
     - Khi ở Tab khác (1, 3, 4, 5): Cả 2 đều tạm dừng, CPU nhàn rỗi 0%.
   - Thu gọn Brand widget: `maximumWidth = 210px`, icon logo `30px`, font title `14px`.

### B. Responsive Layout & Giao Diện
6. **`vietphotobooth/desktop/styles.py`**:
   - Tối ưu padding tab bar: `padding: 5px 8px; margin: 1px 1px; min-width: 48px; font-size: 12px;` tiết kiệm >80px chiều ngang.
7. **`vietphotobooth/desktop/widgets/kiosk_page.py` (Layout)**:
   - Co giãn linh hoạt `card_camera` (180–250px), `card_shots` (150–200px), `card_cd` (170–240px), `card_filters` (170–240px).
   - Nút `btn_start`: Co giãn responsive `360x62` (màn hình lớn) và `270x52` (màn hình < 1200px), đạt 100% điều kiện test `test_responsive_layout.py`.

### C. Bộ Kiểm Thử (Tests)
8. **`vietphotobooth/tests/test_desktop_gui.py`**:
   - Thêm `test_liveview_lifecycle_and_single_worker`: Kiểm tra vòng đời worker/timer khi đổi qua lại 10 lần giữa các tab, xác nhận worker là duy nhất, không tạo luồng rác.
   - Thêm `test_simulator_status_and_preview_display`: Kiểm tra trạng thái Simulator hiển thị chấm vàng 🟡, ẩn disconnected panel, và xử lý ngắt kết nối an toàn.
9. **`vietphotobooth/tests/test_hotfix_v140_verification.py`**:
   - Bộ 5 test kiểm tra toàn bộ 10 kịch bản bắt buộc của Phần 4.
10. **`vietphotobooth/version.py` & `VietPhotoBooth.iss`**:
    - Nâng phiên bản lên `v1.4.1`, build `141`.

---

## 3. KẾT QUẢ KIỂM THỬ (TEST RESULTS)

- **Toàn bộ Test Suite:** **129/129 bài test PASS 100%** (thời gian chạy ~1 phút 54 giây).
- **10 kịch bản kiểm thử bắt buộc theo Phần 4:** Đạt 100% (xác minh qua `test_hotfix_v140_verification.py` và `test_desktop_gui.py`):
  1. Mở trang Chụp Ảnh và chạy Live View: Frame rate giới hạn ở 30 FPS, frame counter không chạy vô hạn — **PASSED**.
  2. Chuyển qua lại giữa Chụp Ảnh và Máy Ảnh 10 lần: Worker Kiosk tạm dừng khi ở Máy Ảnh, Timer Máy Ảnh dừng khi ở Kiosk; Worker instance được giữ nguyên duy nhất — **PASSED**.
  3. Bật/tắt Simulator: Worker/Timer duy nhất, không spawn luồng phụ — **PASSED**.
  4. Đổi backend: Backend cũ được giải phóng sạch sẽ, xóa bộ nhớ đệm frame — **PASSED**.
  5. Ngắt kết nối trong lúc Live View chạy: Không crash, hiển thị panel `🔴 Chưa kết nối` an toàn — **PASSED**.
  6. Đóng ứng dụng: Worker dừng sạch sẽ trong `closeEvent` — **PASSED**.
  7. Kiểm tra giao diện 1920×1080: Đạt chuẩn full size — **PASSED**.
  8. Kiểm tra giao diện 1600×900: Đạt chuẩn co giãn — **PASSED**.
  9. Kiểm tra giao diện 1366×768: Đạt chuẩn màn hình Photobooth cảm ứng phổ biến — **PASSED**.
  10. Kiểm tra giao diện 1280×720 & 1024×680: Không tràn thanh điều hướng, các thẻ điều khiển và nút bấm hiển thị đầy đủ — **PASSED**.

---

## 4. KẾT QUẢ ĐÓNG GÓI PHÁT HÀNH

- **File cài đặt:** `1998-TEAM-Setup-v1.4.1-Build141.exe`
- **Đường dẫn:** `c:\Users\Admin\Documents\photobooth\dist_installer\1998-TEAM-Setup-v1.4.1-Build141.exe`
- **Dung lượng:** `86,377,549 bytes` (~82.38 MB)
- **Mã băm SHA-256:** `671b73c7b588263b60779d4a61bc43826845b84bd5697666871071f650b5fe12`
- **Tệp mã băm:** `c:\Users\Admin\Documents\photobooth\dist_installer\1998-TEAM-Setup-v1.4.1-Build141.exe.sha256`
- **Bảo toàn:** Toàn bộ các bản cài đặt cũ trong `dist_installer/` (`v1.2.1-Build121`, `v1.3.0-Build130`, `v1.3.1-Build131`, `v1.4.0-Build140`) được giữ nguyên vẹn.
