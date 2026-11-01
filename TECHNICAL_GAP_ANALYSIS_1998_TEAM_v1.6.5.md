# 1998 TEAM PHOTOBOOTH — BÁO CÁO PHÂN TÍCH KHOẢNG CÁCH KỸ THUẬT (TECHNICAL GAP ANALYSIS)
**Phiên bản mốc cơ sở (Baseline):** v1.6.5 – Build 165  
**Phương pháp phân tích:** Rà soát tĩnh và động toàn bộ mã nguồn thực tế (Code Audit), đối chiếu bằng chứng kỹ thuật từ đối thủ thực tế (`HihiBooth`, `Maytech Photobooth`), không giả định tính năng.  
**Mục tiêu chiến lược:** Xây dựng cơ sở dữ liệu kỹ thuật vững chắc để hoạch định lộ trình nâng cấp thận trọng, ổn định từ v1.6.5 tới v2.0.0, bắt đầu từ phiên bản **v1.6.6**.  
**Trạng thái thực hiện:** Phân tích kỹ thuật thuần túy — **KHÔNG SỬA ĐỔI MÃ NGUỒN, KHÔNG THAY ĐỔI VERSION, KHÔNG ĐÓNG GÓI BỘ CÀI**.

---

## 1. HỆ THỐNG PHÂN LOẠI TRẠNG THÁI (CLASSIFICATION TAXONOMY)

Mọi hạng mục kỹ thuật trong báo cáo này được xếp loại nghiêm ngặt theo 5 trạng thái:
- **`EXISTS` (Đã có & Xác nhận hoạt động):** Đã hiện diện trong mã nguồn `vietphotobooth/`, có unit/integration test bảo vệ và xác nhận hoạt động ổn định trong thực tế.
- **`PARTIAL` (Đã có một phần / Chưa tối ưu):** Đã có nền tảng mã nguồn nhưng còn thiếu tính năng cốt lõi, xử lý thủ công hoặc tiềm ẩn rủi ro cơ học/phần cứng.
- **`MISSING` (Hoàn toàn chưa có):** Chưa có bất kỳ đoạn mã, tài nguyên hay cơ chế xử lý nào trong mã nguồn hiện tại.
- **`UNVERIFIED` (Chưa đủ bằng chứng kiểm chứng):** Có dấu hiệu cấu hình hoặc interface nhưng chưa có điều kiện kiểm chứng thực nghiệm trên phần cứng thật.
- **`NOT_APPLICABLE` (Không phù hợp / Không áp dụng):** Tính năng đối thủ có nhưng đi ngược lại triết lý Studio Cưới cao cấp của 1998 TEAM (ví dụ: AR filter 3D hoạt hình tai thỏ biến dạng).

---

## 2. MA TRẬN TỔNG HỢP KHOẢNG CÁCH KỸ THUẬT 1998 TEAM v1.6.5

| STT | Phân Hệ / Tính Năng Kỹ Thuật | Trạng Thái | File Mã Nguồn Trọng Tâm | Mức Độ Ưu Tiên |
| :---: | :--- | :---: | :--- | :---: |
| **1** | **Nikon MAID Type0026 USB Direct 21.5 FPS** | `EXISTS` | `camera/backends/nikon_maid/` | Baseline Core |
| **2** | **Unified Pre-Capture Face & Eye AF Engine** | `EXISTS` | `camera/face_eye_af_controller.py` | Baseline Core |
| **3** | **Zero UI Overlay trên Live View Kiosk** | `EXISTS` | `desktop/widgets/kiosk_page.py` | Baseline Core |
| **4** | **Bảo tồn ảnh gốc 100% (`photo_{i}_original.jpg`)**| `EXISTS` | `desktop/widgets/kiosk_page.py:1839` | Baseline Core |
| **5** | **Transaction Token (`tx_id`) & Watchdog 2.2s** | `EXISTS` | `desktop/widgets/kiosk_page.py:1760` | Baseline Core |
| **6** | **Chụp lại toàn bộ phiên (`_retake_session`)** | `EXISTS` | `desktop/widgets/kiosk_page.py:2215` | Baseline Core |
| **7** | **Smart Beauty (Làm mịn LAB + Micro-Texture)** | `EXISTS` | `filters/beauty_engine.py` | Baseline Core |
| **8** | **Son môi thông minh loại trừ răng (Lip Tint)** | `EXISTS` | `filters/beauty_engine.py:410` | Baseline Core |
| **9** | **Render Template 300 DPI & Dual-Strip 4x6** | `EXISTS` | `processing/template_engine.py` | Baseline Core |
| **10**| **Chia sẻ ảnh qua mạng nội bộ LAN QR Offline** | `EXISTS` | `sharing/token_manager.py`, `server.py` | Baseline Core |
| **11**| **Đồng bộ Google Drive Offline-First (Registry)** | `EXISTS` | `cloud/sync_manager.py` | Baseline Core |
| **12**| **Bàn phím số ảo cảm ứng (`TouchNumberPadDialog`)**| `EXISTS` | `desktop/widgets/kiosk_page.py:55` | Baseline Core |
| **13**| **Snap-to-Grid trong Frame Designer (Bước 20px)** | `EXISTS` | `desktop/widgets/frame_designer_page.py:701`| Cần tinh chỉnh |
| **14**| **Bù trừ lề in DNP tự động (Safety Zoom 98%)** | `PARTIAL` | `printing/manager.py:72`, `spooler.py:173` | **P0 (v1.6.6)** |
| **15**| **Khớp hướng giấy tự động với Driver DNP (Rotate 90°)**| `PARTIAL` | `printing/spooler.py:167` | **P0 (v1.6.6)** |
| **16**| **Giãn cách lệnh in nhiệt thăng hoa (Pacing Delay)**| `PARTIAL` | `printing/manager.py:260` | **P0 (v1.6.6)** |
| **17**| **Bộ đếm giấy máy in (Paper Counter Telemetry)** | `PARTIAL` | `printing/manager.py:74` | P1 |
| **18**| **Âm thanh chỉ dẫn đếm ngược & Giọng nói Studio** | `MISSING` | Chưa có module audio (`vietphotobooth/`) | **P0 (v1.6.6)** |
| **19**| **Chụp lại từng kiểu ảnh hỏng (Single-Shot Retake)**| `MISSING` | `desktop/widgets/guest_review_dialog.py` | P1 |
| **20**| **Quay video hậu trường Behind-The-Scenes (BTS MP4)**| `MISSING` | Chưa có VideoWriter / Timelapse buffer | P1 |
| **21**| **Nén video thích ứng CRF (Adaptive Bitrate)** | `MISSING` | Chưa có module video compression | P1 |
| **22**| **Đánh má hồng AI (Anatomical Blush Tinting)** | `MISSING` | `filters/beauty_engine.py` | P2 |
| **23**| **Lịch sử hoàn tác Undo/Redo (`QUndoStack`)** | `MISSING` | `desktop/widgets/frame_designer_page.py` | P1 |
| **24**| **Đường gióng từ tính thông minh (Magnetic Alignment)**| `MISSING` | `desktop/widgets/frame_designer_page.py` | P2 |
| **25**| **Cấu hình độc lập cho từng ô ảnh (Per-Slot Profile)**| `MISSING` | `frames/frame_models.py` | P2 |
| **26**| **Giao diện Kiosk xoay dọc (Portrait Mode 9:16)** | `MISSING` | `desktop/widgets/kiosk_page.py` | P2 |
| **27**| **Chỉ báo độ trễ mạng trực quan (Ping Health Meter)**| `MISSING` | `desktop/main_window.py` | P1 |
| **28**| **Thanh toán chuyển khoản tự động VietQR động** | `MISSING` | Chưa có module payment | P2 |
| **29**| **Tự động ngắt thanh toán khi mất mạng (Fallback)**| `MISSING` | Chưa có module payment | P2 |
| **30**| **Đầu đọc tiền mặt phần cứng RS-232 (ICT L70/TOP TB74)**| `MISSING`| Chưa có serial communication | P3 |
| **31**| **Đọc sensor phần cứng giấy/mực DNP qua USB/SNMP** | `MISSING` | `printing/dnp_rx1hs.py` | P2 |
| **32**| **Tách God Class `kiosk_page.py` (2.391 dòng)** | `PARTIAL` | `desktop/widgets/kiosk_page.py` | P1 (Tái cấu trúc)|
| **33**| **AR Filter 3D tai thỏ / Biến dạng khuôn mặt** | `NOT_APPLICABLE` | Không phù hợp tiệc cưới sang trọng | Loại bỏ |

---

## 3. PHÂN TÍCH CHI TIẾT TỪNG HẠNG MỤC GAP ANALYSIS

---

### HẠNG MỤC 01: BÙ TRỪ LỀ IN DNP TỰ ĐỘNG (SAFETY ZOOM MARGIN)
- **Phân loại:** `PARTIAL`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/printing/manager.py#L72`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/printing/manager.py#L72): `self.zoom = 1.0` (mặc định không co lề).
  - [`vietphotobooth/printing/spooler.py#L173-L183`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/printing/spooler.py#L173-L183):
    ```python
    if zoom != 1.0 or offset_x != 0 or offset_y != 0:
        orig_w, orig_h = img.size
        clamped_zoom = max(0.5, min(2.0, zoom))
        new_w = max(10, int(orig_w * clamped_zoom))
        new_h = max(10, int(orig_h * clamped_zoom))
        scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (orig_w, orig_h), (255, 255, 255))
        paste_x = (orig_w - new_w) // 2 + offset_x
        paste_y = (orig_h - new_h) // 2 + offset_y
        canvas.paste(scaled, (paste_x, paste_y))
        img = canvas
    ```
- **Cơ chế hiện tại:** Nếu `self.zoom == 1.0` (giá trị mặc định khi cài đặt), đoạn mã scale bị bỏ qua hoàn toàn. Ảnh được gửi thẳng 100% kích thước vào DC máy in. Người vận hành phải vào trang Cài Đặt và kéo thanh trượt zoom xuống 0.98 thủ công.
- **Phần còn thiếu (Gap):** Không có cơ chế tự động áp dụng `zoom = 0.98` khi máy in đích là máy in nhiệt thăng hoa (DNP DS-RX1HS, QW410, Citizen, Sinfonia).
- **Module chịu ảnh hưởng:** `vietphotobooth.printing.manager`, `vietphotobooth.printing.spooler`.
- **Rủi ro hồi quy:** Rất thấp nếu chỉ áp dụng khi profile máy in là Dye-Sub và người dùng không cố ý ghi đè zoom tùy chỉnh.
- **Kiểm thử cần thực hiện:**
  - Unit test: Gửi lệnh in với printer name chứa "DNP" hoặc "RX1", kiểm tra kích thước ảnh đầu ra được scale đúng 98% và căn giữa.
  - Integration test: Đảm bảo các máy in thông thường (như Canon Selphy hoặc máy in văn phòng PDF) không bị co lề ngoài ý muốn nếu không thuộc danh sách dye-sub.
- **Điều kiện nghiệm thu:** Ảnh in trên máy DNP DS-RX1HS không bị lưỡi dao chém mất chữ hoặc viền khung; lề an toàn cách mép cắt ít nhất 1.5 - 2mm.

---

### HẠNG MỤC 02: TỰ ĐỘNG KHỚP HƯỚNG GIẤY VỚI DRIVER MÁY IN (AUTO ORIENTATION MATCH)
- **Phân loại:** `PARTIAL`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/printing/spooler.py#L167-L170`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/printing/spooler.py#L167-L170):
    ```python
    if orientation.lower() in ("landscape", "ngang") and img.height > img.width:
        img = img.rotate(90, expand=True)
    elif orientation.lower() in ("portrait", "dọc") and img.width > img.height:
        img = img.rotate(90, expand=True)
    ```
  - [`vietphotobooth/printing/spooler.py#L189-L199`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/printing/spooler.py#L189-L199):
    ```python
    horz_res = hdc.GetDeviceCaps(win32con.HORZRES)
    vert_res = hdc.GetDeviceCaps(win32con.VERTRES)
    dib.draw(hdc.GetHandleOutput(), (0, 0, horz_res, vert_res))
    ```
- **Cơ chế hiện tại:** Mã nguồn chỉ kiểm tra chuỗi tham số `orientation` ("portrait" hoặc "landscape") do ứng dụng truyền vào. Nếu driver Windows của máy in DNP đang được cấu hình cố định là Landscape (chiều rộng > chiều cao) trong khi phần mềm gửi lệnh in dọc, `img` vẫn là ảnh dọc (`img.width < img.height`) nhưng hàm `dib.draw` lại kéo giãn bức ảnh vào khung `(0, 0, horz_res, vert_res)`!
- **Phần còn thiếu (Gap):** Không so sánh tỷ lệ khung hình thực tế của ảnh (`img.width > img.height`) với tỷ lệ khổ trang thực tế của driver đọc từ `hdc.GetDeviceCaps(win32con.HORZRES)` và `VERTRES`.
- **Module chịu ảnh hưởng:** `vietphotobooth.printing.spooler`.
- **Rủi ro hồi quy:** Thấp; chỉ cần đảo ảnh 90 độ khi tỷ lệ hướng trang của driver không trùng với tỷ lệ ảnh.
- **Kiểm thử cần thực hiện:**
  - Mock test: Giả lập `horz_res = 1800, vert_res = 1200` (Landscape) và `img = 1200x1800` (Portrait); xác nhận ảnh được tự động xoay 90 độ trước khi nạp vào DIB.
- **Điều kiện nghiệm thu:** 100% không bao giờ xảy ra lỗi ảnh bị méo dạng hoặc co hẹp do lệch hướng trang giữa phần mềm và Windows Driver.

---

### HẠNG MỤC 03: GIÃN CÁCH LỆNH IN NHIỆT THĂNG HOA (THERMAL PACING DELAY)
- **Phân loại:** `PARTIAL`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/printing/manager.py#L260`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/printing/manager.py#L260): `time.sleep(1.0)` (chờ cố định 1 giây sau khi gửi job).
- **Cơ chế hiện tại:** Vòng lặp `_process_queue_loop` chờ 1 giây sau khi gửi lệnh in. Tuy nhiên, nếu một job có `job.copies > 1` (ví dụ khách chọn in 4 bản), trong `spooler.py#L194-L202`, vòng lặp `for copy_idx in range(copies)` bắn liên tục các trang `hdc.StartPage()` / `hdc.EndPage()` vào spooler mà không có khoảng nghỉ giữa các trang.
- **Phần còn thiếu (Gap):** Không có khoảng giãn cách an toàn 2.0 - 2.5 giây giữa các bản in liên tiếp của máy in nhiệt DNP DS-RX1HS (như đối thủ HihiBooth đã triển khai với `Start-Sleep -Milliseconds 2500`).
- **Module chịu ảnh hưởng:** `vietphotobooth.printing.spooler`, `vietphotobooth.printing.manager`.
- **Rủi ro hồi quy:** Tăng nhẹ thời gian in tổng thể, nhưng bảo vệ hoàn toàn đầu nhiệt và cơ chế kéo ribbon.
- **Kiểm thử cần thực hiện:**
  - Unit test: Xác nhận thời gian giãn cách giữa các `StartDoc/EndDoc` trong đa bản in đạt ≥ 2.0s.
- **Điều kiện nghiệm thu:** Máy in DNP không bao giờ bị nghẽn buffer hoặc rách ribbon mực khi khách in dồn dập 4 - 6 dải ảnh.

---

### HẠNG MỤC 04: HỆ THỐNG ÂM THANH CHỈ DẪN ĐẾM NGƯỢC & GIỌNG NÓI STUDIO (AUDIO PROMPTS)
- **Phân loại:** `MISSING`
- **File & Vị trí mã nguồn:**
  - Chưa tồn tại module `vietphotobooth/audio/` trong toàn bộ dự án.
  - [`vietphotobooth/desktop/widgets/kiosk_page.py#L1690-L1740`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L1690-L1740): Hàm `_on_countdown_tick` chỉ cập nhật giao diện thị giác:
    ```python
    self.lbl_countdown.setText(str(self.countdown_remaining))
    ```
- **Cơ chế hiện tại:** Hoàn toàn câm lặng (Mute). Khách chỉ nhìn số nhảy trên màn hình.
- **Phần còn thiếu (Gap):**
  1. Chưa có audio assets (tiếng tít đếm nhịp `tick.wav`, tiếng chụp màn trập `shutter.wav`, giọng đọc tiếng Việt "Ba, hai, một. Cười lên nào!" `voice_vi.wav`).
  2. Chưa có lớp điều khiển âm thanh `SoundController` sử dụng `QSoundEffect` của PySide6.
  3. Chưa có công tắc bật/tắt âm thanh trong `ConfigManager` và Settings.
- **Module chịu ảnh hưởng:** `vietphotobooth.desktop.widgets.kiosk_page`, `vietphotobooth.core.config`, thêm mới package `vietphotobooth.audio`.
- **Rủi ro hồi quy:** Thấp nếu `QSoundEffect` được chạy non-blocking trên Qt GUI Thread và xử lý an toàn khi thiết bị không có soundcard/loa.
- **Kiểm thử cần thực hiện:**
  - Mock test: Thử nghiệm kích hoạt âm thanh khi `countdown_remaining == 3, 2, 1, 0`.
  - Fallback test: Kiểm tra ứng dụng không bị crash khi không có audio output device (soundcard disabled).
- **Điều kiện nghiệm thu:** Khách nghe thấy âm thanh đếm nhịp rõ ràng; có thể tắt âm thanh trong Cài Đặt bất cứ lúc nào.

---

### HẠNG MỤC 05: CHỤP LẠI TỪNG KIỂU ẢNH HỎNG (SINGLE-SHOT RETAKE)
- **Phân loại:** `MISSING`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/desktop/widgets/kiosk_page.py#L2215-L2220`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L2215-L2220):
    ```python
    def _retake_session(self):
        confirm = QMessageBox.question(self, "Chụp Lại", "Bạn có chắc muốn bỏ lượt chụp này và chụp lại từ đầu?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self._reset_to_idle()
    ```
- **Cơ chế hiện tại:** Hiện tại chỉ có tính năng hủy toàn bộ phiên chụp (`_reset_to_idle`) và bắt đầu lại từ đầu cả 3 hoặc 4 kiểu.
- **Phần còn thiếu (Gap):** Thiếu cơ chế cho phép khách chọn riêng 1 ô ảnh bị hỏng (ví dụ ô số 2 khách bị nhắm mắt) và chỉ chụp lại đúng ô đó (`retake_single_slot(slot_index)`).
- **Module chịu ảnh hưởng:** `vietphotobooth.desktop.widgets.kiosk_page`, `vietphotobooth.desktop.widgets.guest_review_dialog`.
- **Rủi ro hồi quy:** **Cao!** Can thiệp vào luồng `captured_originals`, index ảnh và Transaction Token. Cần thiết kế state machine chuyển trạng thái cực kỳ chặt chẽ để không làm hỏng thứ tự ảnh trong template.
- **Kiểm thử cần thực hiện:**
  - Unit test: Thay thế ảnh tại vị trí index `k`, xác nhận template 300 DPI cập nhật đúng ảnh mới tại ô `k`, giữ nguyên các ô còn lại.
  - Regression test: Kiểm tra luồng in và đồng bộ cloud không bị tải nhầm ảnh cũ.
- **Điều kiện nghiệm thu:** Khách chụp lại được 1 kiểu duy nhất; template cập nhật tức thì trong vòng 300ms.

---

### HẠNG MỤC 06: QUAY VIDEO HẬU TRƯỜNG BEHIND-THE-SCENES (BTS TIMELAPSE MP4)
- **Phân loại:** `MISSING`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/desktop/widgets/kiosk_page.py#L1600-L1650`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L1600-L1650): Hàm `_update_live_frame` chỉ hiển thị frame lên viewport Qt `self.viewport.update_frame(pixmap)`. Frame Live View bị vứt bỏ ngay sau khi hiển thị.
- **Cơ chế hiện tại:** Không lưu trữ frame video nào trong quá trình đếm ngược.
- **Phần còn thiếu (Gap):** Thiếu module ghi hình video `TimelapseRecorder` trích xuất frame từ Live View (10 FPS) và nén thành file `recap.mp4` bằng OpenCV `cv2.VideoWriter`.
- **Module chịu ảnh hưởng:** `vietphotobooth.processing`, `vietphotobooth.desktop.widgets.kiosk_page`, `vietphotobooth.server`.
- **Rủi ro hồi quy:** **Trung bình - Cao!** Việc nén video tiêu tốn CPU/RAM. Nếu nén trên GUI thread sẽ gây giật màn hình hoặc đơ Live View. Bắt buộc phải chạy trên một background worker độc lập với độ ưu tiên thấp (`QThread.LowPriority`).
- **Kiểm thử cần thực hiện:**
  - Performance test: Đo FPS Live View và mức sử dụng CPU trong khi vừa Live View vừa ghi buffer frame.
  - Format test: Xác minh file MP4 mở được trên trình duyệt di động iOS Safari và Android Chrome.
- **Điều kiện nghiệm thu:** Xuất ra file MP4 dưới 10MB; mã QR cho phép khách tải cả ảnh in lẫn video hậu trường.

---

### HẠNG MỤC 07: LỊCH SỬ HOÀN TÁC UNDO / REDO TRONG TRÌNH THIẾT KẾ KHUNG
- **Phân loại:** `MISSING`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/desktop/widgets/frame_designer_page.py#L650-L850`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/frame_designer_page.py#L650-L850): Các hàm `mouseMoveEvent`, `mouseReleaseEvent`, thêm slot, xóa slot đều thay đổi trực tiếp trên đối tượng `self.current_template` mà không có ngăn xếp hoàn tác.
- **Cơ chế hiện tại:** Mọi thao tác kéo thả, xóa, sửa kích thước đều có hiệu lực ngay lập tức. Nếu lỡ tay xóa một ô ảnh hoặc kéo lệch vị trí, người dùng không thể bấm `Ctrl+Z` để khôi phục.
- **Phần còn thiếu (Gap):** Thiếu tích hợp Qt `QUndoStack` và `QUndoCommand`.
- **Module chịu ảnh hưởng:** `vietphotobooth.desktop.widgets.frame_designer_page`.
- **Rủi ro hồi quy:** Trung bình; cần đảm bảo đồng bộ giữa trạng thái canvas và danh sách slot trên sidebar.
- **Kiểm thử cần thực hiện:**
  - Unit test: Thực hiện chuỗi Thêm -> Di chuyển -> Đổi kích thước -> Undo 3 lần -> Redo 3 lần; xác nhận tọa độ và số lượng slot khớp 100%.
- **Điều kiện nghiệm thu:** Người dùng bấm `Ctrl+Z` và `Ctrl+Y` hoàn tác/làm lại mượt mà cho mọi thao tác chỉnh sửa khung.

---

### HẠNG MỤC 08: GIAO DIỆN KIOSK XOAY DỌC (PORTRAIT MODE 9:16)
- **Phân loại:** `MISSING`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/desktop/widgets/kiosk_page.py#L200-L350`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L200-L350): Bố cục giao diện được thiết kế cố định bằng `QHBoxLayout` 3 cột ngang (Cột sự kiện bên trái 260px, Live View ở giữa mở rộng, Trạng thái máy ảnh bên phải 260px).
- **Cơ chế hiện tại:** Giao diện tối ưu cho màn hình ngang tỷ lệ 16:9 (1920x1080). Khi ứng dụng chạy trên màn hình cảm ứng đặt dọc (1080x1920), 3 cột bị ép chặt lại, khung Live View bị thu nhỏ xuống dưới 400px chiều ngang và xuất hiện thanh cuộn ngang gây mất thẩm mỹ.
- **Phần còn thiếu (Gap):** Chưa có cơ chế phát hiện tỷ lệ màn hình (Aspect Ratio Detection) và chuyển đổi linh hoạt sang bố cục 1 cột xếp dọc (Vertical Stacked Layout).
- **Module chịu ảnh hưởng:** `vietphotobooth.desktop.widgets.kiosk_page`, `vietphotobooth.desktop.styles`.
- **Rủi ro hồi quy:** Cao đối với giao diện Kiosk; cần đảm bảo chuyển đổi layout không làm gián đoạn worker camera hoặc mất tín hiệu kết nối.
- **Kiểm thử cần thực hiện:**
  - Responsive test: Chạy Kiosk ở độ phân giải 1920x1080 (ngang) và 1080x1920 (dọc); xác nhận không xuất hiện thanh cuộn không mong muốn.
- **Điều kiện nghiệm thu:** Màn hình dọc hiển thị Live View chiếm 60-65% diện tích nửa trên, các nút bấm điều khiển xếp gọn ở nửa dưới.

---

### HẠNG MỤC 09: BỘ ĐẾM GIẤY VÀ CẢM BIẾN VẬT TƯ PHẦN CỨNG MÁY IN
- **Phân loại:** `PARTIAL`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/printing/manager.py#L74-L77`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/printing/manager.py#L74-L77):
    ```python
    self.paper_count = 120
    self.paper_max = 400
    self.paper_warning_threshold = 50
    ```
  - [`vietphotobooth/printing/manager.py#L255`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/printing/manager.py#L255): `self.paper_count = max(0, self.paper_count - job.copies)`
- **Cơ chế hiện tại:** `PrintManager` lưu biến đếm `paper_count` trong `config.json` và tự động trừ dần sau mỗi lần gửi lệnh in thành công.
- **Phần còn thiếu (Gap):** Không đọc được dữ liệu cảm biến thực tế từ vi điều khiển phần cứng của máy in DNP qua cổng USB (như Maytech dùng `CyStat64.dll` hoặc SNMP). Nếu người dùng thay cuộn giấy mới ngoài đời thực mà không vào phần mềm bấm nút "Nạp giấy", số đếm sẽ sai lệch hoàn toàn.
- **Module chịu ảnh hưởng:** `vietphotobooth.printing.manager`, `vietphotobooth.printing.dnp_rx1hs`.
- **Rủi ro hồi quy:** Thấp; chỉ là module đọc telemetry phụ trợ.
- **Kiểm thử cần thực hiện:**
  - Hardware/Mock test: Đọc mã lỗi máy in (Hết giấy, hết mực, mở nắp) qua Windows Spooler API `GetPrinter`.
- **Điều kiện nghiệm thu:** Hiển thị cảnh báo chính xác khi máy in thực tế hết giấy hoặc kẹt cơ.

---

### HẠNG MỤC 10: TÁI CẤU TRÚC PHÂN RÃ FILE "GOD CLASS" `kiosk_page.py`
- **Phân loại:** `PARTIAL`
- **File & Vị trí mã nguồn:**
  - [`vietphotobooth/desktop/widgets/kiosk_page.py`](file:///c:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py): Độ dài **2.391 dòng mã**.
- **Cơ chế hiện tại:** File này đang gánh vác cùng lúc 6 trách nhiệm độc lập:
  1. Xây dựng giao diện Qt, layout 3 cột, stylesheets.
  2. Vòng đời Live View và hiển thị khung hình.
  3. Quản lý trạng thái đếm ngược và Transaction Token.
  4. Điều phối lấy nét Autofocus và Watchdog Timer 2.2s.
  5. Xử lý sau chụp (sao lưu ảnh gốc, Smart Beauty prompt).
  6. Điều phối lệnh in ấn và đồng bộ hóa đám mây.
- **Phần còn thiếu (Gap):** Thiếu sự phân tách trách nhiệm (Separation of Concerns). Khó khăn trong việc thêm tính năng mới (như audio đếm ngược hoặc quay video recap) mà không làm tăng nguy cơ phát sinh lỗi tiềm ẩn.
- **Module chịu ảnh hưởng:** Toàn bộ hệ thống giao diện Kiosk.
- **Rủi ro hồi quy:** **CỰC KỲ CAO!** Đây là trái tim vận hành của photobooth. Mọi sự xáo trộn cấu trúc không có kiểm thử hồi quy chặt chẽ đều có thể làm hỏng phiên chụp tại sự kiện.
- **Kiểm thử cần thực hiện:**
  - Chạy toàn bộ 294 bài test tự động hiện có sau mỗi bước bóc tách nhỏ (Refactoring in thin slices).
- **Điều kiện nghiệm thu:** Tách thành các lớp helper/controller nhỏ hơn mà không làm thay đổi bất kỳ hành vi bên ngoài nào của Kiosk.

---

## 4. CHIẾN LƯỢC QUẢN LÝ RỦI RO & BẢO TOÀN HỆ THỐNG CỐT LÕI

Để bảo vệ tuyệt đối sự ổn định của phiên bản mốc cơ sở v1.6.5, toàn bộ quy trình phát triển từ v1.6.5 tới v2.0.0 phải tuân thủ nghiêm ngặt 5 "Ranh Giới Đỏ" (Red Lines):

1. **RANH GIỚI ĐỎ 1 — BẢO TOÀN NIKON MAID3 USB DIRECT:**
   Tuyệt đối không sửa đổi mã nguồn trong `vietphotobooth/camera/backends/nikon_maid/` (`maid_session.py`, `maid_loader.py`, `nikon_d780_backend.py`, `camera_worker.py`). Backend này đã chứng minh độ ổn định tuyệt đối và tốc độ 21.5 FPS trên thiết bị Nikon D780 thật.
2. **RANH GIỚI ĐỎ 2 — BẢO TOÀN CAPTURE TRANSACTION & WATCHDOG:**
   Không thay đổi cơ chế định danh giao dịch `tx_id = f"tx_{int(time.time()*1000)}"`, cờ `_active_capture_tx`, và Watchdog Timer 2.2 giây đã giải quyết triệt để vấn đề race condition và chống chụp đúp.
3. **RANH GIỚI ĐỎ 3 — BẢO TOÀN UNIFIED FACE/EYE AF ENGINE:**
   Giữ nguyên luồng chia sẻ `FaceEyeAFController` giữa `CameraPage` và `KioskPage`, bảo toàn nguyên lý Zero UI Overlay (không hiện khung nhận diện trong buồng chụp Kiosk).
4. **RANH GIỚI ĐỎ 4 — BẢO TỒN DỮ LIỆU GỐC:**
   Giữ vững quy tắc: Mọi ảnh chụp từ máy ảnh bắt buộc phải sao lưu bản gốc `photo_{index}_original.jpg` vào đĩa cứng trước khi áp dụng bất kỳ bộ lọc làm đẹp hay template nào.
5. **RANH GIỚI ĐỎ 5 — QUY TRÌNH PHÁT HÀNH TỪNG BƯỚC NHỎ (THIN SLICES):**
   Không gộp nhiều tính năng lớn vào cùng một phiên bản. Mỗi phiên bản chỉ giải quyết từ 2 đến 3 hạng mục nhỏ, có đầy đủ bài test kiểm chứng và mã thoát `pytest` trả về 0 trước khi đóng gói.
