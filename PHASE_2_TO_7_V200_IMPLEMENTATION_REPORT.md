# BÁO CÁO TRIỂN KHAI HOÀN TẤT — 1998 TEAM PHOTOBOOTH v2.0.0
**Dự án:** 1998 TEAM — Photobooth  
**Nhánh làm việc:** `feature/v2.0.0-photobooth`  
**Baseline bảo vệ:** `v1.6.6-build166-baseline` (commit `4235fb5`)  
**Ngày báo cáo:** 02/11/2026  

---

## 1. TỔNG QUAN TIẾN ĐỘ THỰC HIỆN

Thực hiện theo chỉ đạo của Chủ dự án trong **MASTER IMPLEMENTATION PROMPT — 1998 TEAM PHOTOBOOTH v2.0.0**, toàn bộ 7 giai đoạn triển khai chuyển đổi sang **Hybrid Design v2.0** đã được hoàn tất và nghiệm thu 100% với bộ kiểm thử tự động đạt **318/318 bài kiểm thử PASS (100% Green)**.

| Giai đoạn | Nội dung | Trạng thái | Minh chứng & Module |
|:---|:---|:---:|:---|
| **Phase 1** | Kiểm tra toàn bộ mã nguồn & Phân tích phụ thuộc | **HOÀN TẤT** | `PHASE_1_SOURCE_AUDIT_AND_ARCHITECTURE_MAPPING.md` |
| **Phase 2** | Giao diện cốt lõi & Buồng Lái Operator Dashboard | **HOÀN TẤT** | `vietphotobooth/desktop/widgets/dashboard_page.py`, `MainWindow.window_stack` |
| **Phase 3** | Tích hợp Camera Engine & Live View không ngắt quãng | **HOÀN TẤT** | Bảo toàn Nikon MAID3 + WPD, không disconnect khi chuyển trang |
| **Phase 4** | Chụp lại theo từng ô (Slot-based Retake) & Template | **HOÀN TẤT** | `kiosk_page.py`, `guest_review_dialog.py`, bảo toàn 100% các ô khác |
| **Phase 5** | Trung tâm In ấn & Chia sẻ QR Mạng nội bộ Offline LAN | **HOÀN TẤT** | `vietphotobooth/desktop/widgets/qr_sharing_page.py` |
| **Phase 6** | Giám sát Thiết bị Đa kênh (Concept C) & Khóa PIN cảm ứng | **HOÀN TẤT** | `devices_page.py`, `touch_pin_dialog.py` (Rung lắc + Khóa 30s) |
| **Phase 7** | Kiểm thử Tích hợp & Nghiệm thu toàn diện | **HOÀN TẤT** | `py -3.12 -m pytest`: **318/318 PASS (100%)** |

---

## 2. CHI TIẾT CÁC PHÂN HỆ VÀ TÍNH NĂNG MỚI ĐÃ TRIỂN KHAI

### 2.1. Buồng Lái Vận Hành Trung Tâm (Operator Dashboard — Concept A)
- **Tệp nguồn:** [`vietphotobooth/desktop/widgets/dashboard_page.py`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/dashboard_page.py)
- **Kiến trúc:** Bố cục 2 cột bất đối xứng (60/40) chuyên nghiệp.
- **Tính năng nổi bật:**
  - 4 Thẻ KPI vận hành trung thực: Doanh thu ca, Số lượt chụp thành công, Tỷ lệ in thành công, Mức giấy khay in còn lại (đánh dấu `[DEMO]` / `[SIMULATED]` rõ ràng cho dữ liệu mẫu).
  - Khung ngắm Live View trung tâm sử dụng `CameraLiveViewport` siêu mượt, giữ nguyên tỷ lệ quang học 3:2.
  - 3 Huy hiệu trạng thái phần cứng đa kênh chuẩn Concept C: Máy ảnh Nikon D780 (USB Native), Máy in DNP DS-RX1HS (Spooler), Mạng chia sẻ Offline LAN (Wi-Fi Hotspot).
  - Nút bấm vàng khổng lồ `🚀 BẮT ĐẦU PHOTOBOOTH (F11)` chuyển đổi tức thì sang chế độ khách chụp Kiosk.
  - Thanh công cụ thao tác nhanh: Chụp thử (Test Shot), In thử (Test Print), Mở chẩn đoán thiết bị (Telemetry), Quản lý chia sẻ QR.

### 2.2. Chụp Lại Theo Ô Độc Lập (Slot-based Retake) — Bảo Toàn Dữ Liệu Tuyệt Đối
- **Tệp nguồn:**
  - [`vietphotobooth/desktop/widgets/guest_review_dialog.py`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/guest_review_dialog.py)
  - [`vietphotobooth/desktop/widgets/kiosk_page.py`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py)
- **Cơ chế hoạt động:**
  - Trong trang Hoàn Thiện Ảnh (Review Page), mỗi ô ảnh hiển thị thẻ `PhotoThumbnailCard` kèm nút `Chụp lại`.
  - Trên thanh công cụ chỉnh sửa dưới Canvas, có thêm nút nổi bật `Chụp lại ô này`.
  - Khi khách hàng hoặc nhân viên bấm chụp lại riêng ô số 2 (`photo_idx = 1`):
    1. Trạng thái phiên chuyển sang `RETAKE_SLOT` với mục tiêu `_retake_slot_index = 1`.
    2. Cửa sổ Viewfinder mở ra với thông báo: `📸 Đang chụp lại Ô số 2!`.
    3. Đếm ngược và chụp 1 tấm duy nhất cho riêng ô này.
    4. Cập nhật trực tiếp: `self.captured_originals[1] = new_photo` và `self.captured_paths[1] = new_path`.
    5. **Tuyệt đối bảo toàn:** Toàn bộ ảnh của ô 1 (`index 0`), ô 3 (`index 2`), ô 4 (`index 3`) được giữ nguyên 100%, không bị xáo trộn hoặc xóa mất.
    6. Tự động quay lại trang Hoàn thiện ảnh với khung hình đã được cập nhật ngay lập tức.
  - Nếu mất kết nối máy ảnh hoặc hủy thao tác trong lúc retake, hệ thống lập tức khôi phục màn hình Review với đầy đủ 4 ảnh cũ, loại bỏ rủi ro mất dữ liệu của khách.

### 2.3. Khóa Bảo Mật PIN Cảm Ứng (Touch PIN Dialog & 30s Lockout)
- **Tệp nguồn:** [`vietphotobooth/desktop/widgets/touch_pin_dialog.py`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/touch_pin_dialog.py)
- **Tính năng bảo mật:**
  - 4 Chấm tròn bảo mật (PIN Indicator Dots) phản hồi ánh sáng vàng Champagne `#D4AF37` theo từng ký tự nhập.
  - Bàn phím số cảm ứng lớn [1..9, 0, ⌫, Xóa] trên màn hình, đồng thời hỗ trợ bàn phím vật lý máy tính.
  - Tự động thẩm định ngay khi nhập đủ 4 chữ số (không cần bấm Enter).
  - **Hiệu ứng rung lắc (Shake Animation):** Hộp thoại rung lắc vật lý và các chấm chuyển sang màu đỏ rực `#EF4444` khi nhập sai.
  - **Cơ chế khóa an toàn:** Nếu nhập sai 3 lần liên tiếp, hộp thoại tự động vô hiệu hóa toàn bộ bàn phím và đếm ngược khóa an toàn 30 giây (`🔒 Nhập sai 3 lần. Tự khóa 30s...`).

### 2.4. Trung Tâm Giám Sát Thiết Bị & Cảm Biến Đa Kênh (Devices Telemetry)
- **Tệp nguồn:** [`vietphotobooth/desktop/widgets/devices_page.py`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/devices_page.py)
- **4 Kênh đo đạc thời gian thực (Concept C):**
  - **Kênh 1 — Máy ảnh:** Nikon D780 Native USB (Type0026 SDK), phân giải chụp 6048×4024, FPS đo đạc, trạng thái Live View.
  - **Kênh 2 — Máy in:** DNP DS-RX1HS, số lượng giấy còn lại trong khay (`700/700 tờ`), trạng thái hàng đợi Windows Spooler.
  - **Kênh 3 — Mạng nội bộ:** Wi-Fi Hotspot `1998TEAM-PHOTOBOOTH`, địa chỉ IP quầy và cổng kết nối web.
  - **Kênh 4 — Ổ đĩa & Bộ nhớ:** Dung lượng trống (GB), phần trăm đã sử dụng, tính toàn vẹn cơ sở dữ liệu SQLite3 WAL.

### 2.5. Trung Tâm Chia Sẻ QR Mạng Nội Bộ (Offline LAN QR Sharing)
- **Tệp nguồn:** [`vietphotobooth/desktop/widgets/qr_sharing_page.py`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/qr_sharing_page.py)
- **Khả năng hoạt động độc lập hoàn toàn:**
  - Phát sóng Wi-Fi điểm truy cập nội bộ (SSID: `1998TEAM-PHOTOBOOTH`, Pass: `1998studio`).
  - Địa chỉ máy chủ FastAPI cục bộ (Local IP + Cổng 8080).
  - Tự động tạo mã QR 300 DPI với token 128-bit mã hóa ngẫu nhiên an toàn.
  - Mô phỏng màn hình tải ảnh trên điện thoại của khách hàng (Mobile Preview) và nút mở thử nghiệm trên trình duyệt.

---

## 3. BẢO VỆ TUYỆT ĐỐI HỆ THỐNG MÁY ẢNH NIKON D780 VÀ BASELINE

1. **Giữ nguyên 100% Nikon MAID3 Backend:**
   - Bộ tệp lõi `Type0026.md3`, `NkRoyalmile.dll`, `NkdPTP.dll` không bị chỉnh sửa.
   - Trình điều khiển Windows WPD Native Driver giữ nguyên, tuyệt đối không cài Zadig / WinUSB.
   - Quản lý phiên `CameraConnectionManager` được duy trì xuyên suốt vòng đời ứng dụng, việc chuyển đổi giữa Dashboard, Capture Studio, Devices hay Kiosk không hề ngắt phiên hay làm gián đoạn luồng Live View.
2. **Bảo tồn 100% 6 Tab vận hành của Baseline:**
   - Cấu trúc `self.tabs` với 6 tab ("Chụp Ảnh", "Khung Ảnh", "Máy Ảnh", "Máy In", "Sự Kiện & Thư Viện", "Cài Đặt") được giữ nguyên vẹn bên trong `self.window_stack[0]`.
   - Nhờ đó, toàn bộ 306 bài test kiểm thử của các phiên bản trước đều pass 100% mà không cần sửa đổi bất kỳ logic kiểm thử nào.
3. **Bảo tồn các bộ cài đặt:**
   - Thư mục `dist_installer/` và các bản phát hành cũ không bị tác động. Không tự ý chạy `build_release.py` khi chưa có chỉ đạo phê duyệt nghiệm thu từ Chủ dự án.

---

## 4. KẾT QUẢ KIỂM THỬ TÍCH HỢP (REGRESSION TEST SUITE)

Chạy lệnh kiểm thử toàn diện:
```powershell
py -3.12 -m pytest
```

**Kết quả thu được:**
```
================= 318 passed, 4 warnings in 211.28s (0:03:31) =================
Exit Code: 0 (100% PASS)
```

**Chi tiết các bài kiểm thử mới cho v2.0.0:**
1. `vietphotobooth/tests/test_v200_dashboard_and_navigation.py`:
   - `test_dashboard_page_components`: PASS.
   - `test_dashboard_navigation_switch`: PASS.
   - `test_dashboard_signals`: PASS.
2. `vietphotobooth/tests/test_v200_slot_retake.py`:
   - `test_photo_thumbnail_card_retake_button_and_signal`: PASS.
   - `test_review_widget_slot_retake_signal_propagation`: PASS.
   - `test_kiosk_retake_single_slot_preserves_other_slots`: PASS (Bảo toàn 100% các ô còn lại khi retake).
   - `test_kiosk_retake_slot_abort_preserves_all_slots`: PASS (Khôi phục toàn vẹn 4 ảnh cũ khi hủy retake).
3. `vietphotobooth/tests/test_v200_devices_and_security.py`:
   - `test_touch_pin_keypad_and_dots`: PASS.
   - `test_touch_pin_authentication_and_lockout`: PASS (Rung lắc + Khóa 30s sau 3 lần sai).
   - `test_devices_telemetry_page_channels`: PASS.
   - `test_qr_sharing_page_offline_lan`: PASS.
   - `test_main_window_v200_extended_navigation`: PASS.
