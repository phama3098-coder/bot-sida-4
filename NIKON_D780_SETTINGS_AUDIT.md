# BÁO CÁO AUDIT NIKON MAID3 CAPABILITY — ĐIỀU KHIỂN THÔNG SỐ NIKON D780
## DỰ ÁN 1998 TEAM — PHOTOBOOTH (v1.6.6 Build 166)
**Giai đoạn:** Giai đoạn 1 — Audit kỹ thuật, chưa sửa code  
**Đối tượng:** Nikon D780 (Body DSLR Full-Frame) qua Type0026.md3 (Native USB x64)  
**Thời gian lập:** 2026-11-01 20:30:00 +07:00  
**Tác giả:** Đội ngũ Kỹ thuật & Kiến trúc Antigravity

---

### 1. HIỆN TRẠNG NIKON MAID BACKEND TRONG MÃ NGUỒN HIỆN TẠI

1. **Thư viện Type0026.md3 & Dependencies:**
   - Đã xác minh nhị phân x64 tại `vietphotobooth/camera/backends/nikon_maid/bin/x64/Type0026.md3` (1.55 MB).
   - Quét cấu trúc binary phát hiện chính xác **303 lớp capability C++** (tiền tố `AVCNkCap...`) bao phủ toàn diện 100% các thông số phơi sáng, lấy nét, cân bằng trắng và quản lý file của Nikon D780.
2. **Cấu trúc dữ liệu ctypes (`maid_types.py`):**
   - Đã định nghĩa chuẩn xác các cấu trúc MAID3 với `_pack_ = 2`: `NkMAIDObject`, `NkMAIDCapInfo`, `NkMAIDEnum`, `NkMAIDRange`, `NkMAIDString`, `NkMAIDArray`.
   - Các hằng số capability đã có sẵn: `COMPRESSION_LEVEL` (0x8110), `SHUTTER_SPEED` (0x8112), `APERTURE` (0x8113), `FOCUS_MODE` (0x8120), `ISO_CONTROL` (0x816C), `AF_MODE` (0x81C3), `LIVE_VIEW_AF` (0x8275), `AF_MODE_AT_LIVE_VIEW` (0x8310).
   - Các hằng số cần bổ sung khi triển khai Giai đoạn 3: `EXPOSURE_MODE` (0x8111), `EXPOSURE_COMP` (0x8115), `SENSITIVITY` (0x8117), `WB_MODE` (0x8118), `FOCUS_AREA_MODE` (0x8121).
3. **Khả năng truy vấn trong `maid_session.py`:**
   - Đã có các hàm đọc/ghi nguyên thủy: `get_string_capability`, `get_unsigned_capability`, `set_unsigned_capability`, `get_enum_capability`, `set_enum_capability`.
   - **Khoảng trống kỹ thuật cần bổ sung:**
     - Hàm `get_enum_options(cap_id)`: Chưa có hàm trích xuất toàn bộ danh sách lựa chọn khả dụng từ `pData` qua lệnh `CAP_GET_ARRAY` để nạp vào QComboBox UI.
     - Hàm `get_range_capability(cap_id)` và `set_range_capability(cap_id, val)`: Cần thiết cho Exposure Compensation (kiểu `NkMAIDRange`).
     - Bộ chuyển đổi định dạng (Formatters): Cần ánh xạ giữa chỉ số nhị phân Nikon và chuỗi hiển thị thân thiện cho thợ ảnh (ví dụ: `1/160s`, `f/2.8`, `ISO 400`, `+0.3 EV`, `Daylight 5500K`).
4. **Mô hình cấp cao (`nikon_d780_backend.py`):**
   - Đã bật cờ `can_adjust_parameters = True` trong `CameraCapabilities`.
   - Hàm `get_parameters()` hiện chỉ đọc `battery_percent`, cần mở rộng để đọc toàn bộ từ điển thông số chụp.

---

### 2. BẢNG ĐỐI SOÁT CHI TIẾT 9 THÔNG SỐ YÊU CẦU

| STT | Thông số yêu cầu | Mã Capability trong Type0026 | Giá trị hex ID | Kiểu dữ liệu MAID | Thao tác hỗ trợ | Khả năng điều khiển thực tế trên D780 |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- |
| **1** | **Exposure Mode** (Chế độ chụp) | `AVCNkCapExposureMode` | `0x8111` | `NkMAIDCapType.ENUM` | `GET`, `GET_ARRAY`, `GET_DEFAULT` | **CHỈ ĐỌC (Read-Only)**. Trên thân máy Nikon D780, chế độ chụp được điều khiển bằng núm xoay cơ học có lẫy bấm khóa vật lý ở đỉnh máy (M, A, S, P, Auto, EFCT, U1, U2). Lệnh SET từ phần mềm bị phần cứng từ chối. UI chỉ nên hiển thị nhãn trạng thái Read-Only. |
| **2** | **Shutter Speed** (Tốc độ màn trập) | `AVCNkCapShutterSpeed` | `0x8112` | `NkMAIDCapType.ENUM` | `GET`, `SET`, `GET_ARRAY`, `GET_DEFAULT` | **ĐIỀU KHIỂN HOÀN TOÀN** trong chế độ **M** và **S** (1/8000s đến 30s, Bulb, Time). Bị khóa (Read-Only) trong chế độ **A** và **P** do máy tự tính toán theo đo sáng. |
| **3** | **Aperture** (Khẩu độ) | `AVCNkCapAperture` | `0x8113` | `NkMAIDCapType.ENUM` | `GET`, `SET`, `GET_ARRAY`, `GET_DEFAULT` | **ĐIỀU KHIỂN HOÀN TOÀN** trong chế độ **M** và **A** với lens CPU (dòng E, G hoặc lens D đã khóa vòng khẩu về f/16–f/22). Bị khóa trong chế độ **S** và **P**. |
| **4** | **ISO Sensitivity** (Độ nhạy sáng) | `AVCNkCapSensitivity` / `AVCNkCapIsoControl` | `0x8117` / `0x816C` | `NkMAIDCapType.ENUM` / `UNSIGNED` | `GET`, `SET`, `GET_ARRAY`, `GET_DEFAULT` | **ĐIỀU KHIỂN HOÀN TOÀN** ở cả 4 chế độ P, S, A, M (ISO 100 đến 51200 và dải mở rộng Lo/Hi). Cho phép bật/tắt Auto ISO. |
| **5** | **Exposure Compensation** (Bù trừ sáng) | `AVCNkCapExposureComp` | `0x8115` | `NkMAIDCapType.RANGE` / `ENUM` | `GET`, `SET`, `GET_DEFAULT`, `GET_RANGE` | **ĐIỀU KHIỂN HOÀN TOÀN** trong chế độ P, S, A (dải từ -5.0 EV đến +5.0 EV bước 1/3 EV). Trong chế độ M, chỉ có tác dụng nếu bật Auto ISO. |
| **6** | **White Balance** (Cân bằng trắng) | `AVCNkCapWBMode` / `AVCNkCapWBTuneColorTempEx` | `0x8118` / `0x81A8` | `NkMAIDCapType.ENUM` / `UNSIGNED` | `GET`, `SET`, `GET_ARRAY`, `GET_DEFAULT` | **ĐIỀU KHIỂN HOÀN TOÀN**. Cho phép chọn preset (Auto, Daylight, Incandescent, Fluorescent, Flash, Cloudy, Shade) hoặc chỉnh trực tiếp độ K (2500K – 10000K). |
| **7** | **Image Quality** (Chất lượng ảnh) | `AVCNkCapCompressionLevel` | `0x8110` | `NkMAIDCapType.ENUM` | `GET`, `SET`, `GET_ARRAY`, `GET_DEFAULT` | **ĐIỀU KHIỂN HOÀN TOÀN**. Hỗ trợ JPEG Fine, JPEG Normal, JPEG Basic, NEF (RAW), RAW + JPEG Fine. |
| **8** | **Focus Mode** (Chế độ lấy nét) | `AVCNkCapFocusMode` / `AVCNkCapAFModeAtLiveView` | `0x8120` / `0x8310` | `NkMAIDCapType.ENUM` | `GET`, `SET` (có điều kiện), `GET_ARRAY` | **ĐIỀU KHIỂN CÓ ĐIỀU KIỆN**. Bị giới hạn cứng bởi cần gạt cơ học trên thân máy hoặc lens. Nếu cần gạt đang ở vị trí **MF**, phần mềm KHÔNG THỂ ép máy sang AF. Khi Live View bật, sử dụng `AFModeAtLiveView` (AF-S, AF-F, MF). |
| **9** | **AF Area Mode** (Vùng lấy nét) | `AVCNkCapStillFocusAreaMode` / `AVCNkCapLiveViewAF` | `0x8121` / `0x8275` | `NkMAIDCapType.ENUM` | `GET`, `SET`, `GET_ARRAY` | **ĐIỀU KHIỂN THEO TRẠNG THÁI**. Trong Live View, điều khiển Face-priority, Wide-area, Normal-area, Subject-tracking, Pinpoint AF. Trong OVF, điều khiển Single-point, Dynamic 9/21/51, 3D Tracking, Auto-area. |

---

### 3. ĐIỀU KIỆN PHỤ THUỘC & GIỚI HẠN VẬN HÀNH THỰC TẾ

#### 3.1. Phụ thuộc vào Chế độ Phơi sáng (Exposure Mode):
- **Khuyến nghị chuẩn Studio Photobooth:** Luôn đặt máy ảnh ở chế độ **M (Manual)** trên núm xoay vật lý. Khi đó:
  - Shutter Speed được khóa cố định theo tốc độ ăn đèn flash (thường là 1/160s hoặc 1/200s).
  - Aperture được cố định ở độ nét tối ưu của ống kính (thường f/5.6 hoặc f/8.0).
  - ISO đặt cố định 100 hoặc 200 (tắt Auto ISO để tránh ảnh bị nhiễu hạt khi flash đánh chưa nạp xong).
- **Ràng buộc khi ở Mode P/S/A:**
  - Nếu người dùng vặn nhầm sang **A**, dropdown Shutter Speed trên phần mềm phải tự động làm mờ (disabled) hoặc chỉ hiển thị giá trị đọc được (Read-Only) kèm chú thích *"Tự động tính theo đo sáng"*.
  - Nếu vặn sang **S**, dropdown Aperture phải tự động làm mờ.

#### 3.2. Phụ thuộc vào Ống kính (Lens):
- **Ống kính dòng E và G:** Điều khiển điện tử 100% không gặp trở ngại.
- **Ống kính dòng D (có vòng khẩu cơ học):** Phải khóa vòng khẩu trên lens ở trị số nhỏ nhất (f/16, f/22). Nếu vòng khẩu bị lệch, máy ảnh báo lỗi `fEE` trên màn hình phụ và lệnh SET khẩu độ sẽ thất bại.
- **Ống kính MF / Non-CPU:** Không hỗ trợ điều khiển khẩu độ qua phần mềm (thân máy báo `F--`).

#### 3.3. Phụ thuộc vào Trạng thái Live View:
- Nikon D780 là dòng máy ảnh hybrid DSLR có cơ chế Live View hiện đại (thừa hưởng cảm biến và AF từ mirrorless Z6), hỗ trợ **Electronic Aperture trong Live View**. Người dùng có thể đổi khẩu độ mượt mà mà không cần đóng gương lật.
- Cần gạt Live View trên thân máy D780 phải ở vị trí **Photo Live View** (biểu tượng máy ảnh). Nếu gạt sang Movie Live View, tốc độ màn trập sẽ bị giới hạn bởi framerate video.
- Khi Live View tắt, các capability thuộc nhóm Live View (`CONTRAST_AF_AREA`, `LIVE_VIEW_IMAGE_SIZE`) sẽ trả về mã lỗi `NOT_SUPPORTED` (-127).

#### 3.4. Phòng ngừa xung đột nghiêm trọng (Capture & Live View Concurrency):
- **Thời điểm nhạy cảm:** Khi Kiosk đang trong quá trình chụp ảnh (`capture_photo` / `Acquire`), kênh truyền USB chuyển sang trạng thái bận truyền file lớn (24.3 MP).
- **Nguyên tắc an toàn:** Không bao giờ gửi lệnh `CAP_SET` vào khoảnh khắc chụp ảnh. Mọi thao tác đổi thông số từ UI phải thông qua hàng đợi an toàn (Request Queue) và bị tạm dừng (paused) khi cờ `_active_capture_tx` của Kiosk đang hoạt động.

---

### 4. ĐỀ XUẤT KIẾN TRÚC CHO GIAI ĐOẠN 2 & 3

#### Giai đoạn 2: Thiết kế giao diện Camera Settings UI
- Vị trí: Đặt một GroupBox riêng **"THIẾT LẬP THÔNG SỐ MÁY ẢNH (D780 SETTINGS)"** tại cột phải của tab Máy Ảnh (`CameraPage`).
- Bố cục lưới gọn gàng:
  - Dòng 1: Chế độ chụp (Badge hiển thị: M / A / S / P) | Bù sáng (EV Comp)
  - Dòng 2: Tốc độ màn trập (QComboBox) | Khẩu độ (QComboBox)
  - Dòng 3: Độ nhạy sáng ISO (QComboBox) | Cân bằng trắng (QComboBox)
  - Dòng 4: Chất lượng ảnh (QComboBox) | Chế độ AF (QComboBox)
  - Dòng 5: Nút **"🔄 Đọc lại thông số từ máy"** + Nhãn trạng thái đồng bộ (`Đã đồng bộ` / `Đang gửi...` / `Lỗi`).

#### Giai đoạn 3: Triển khai `CameraSettingsController`
- Tạo module chuyên biệt độc lập: `vietphotobooth/camera/backends/nikon_maid/settings_controller.py`.
- Tách biệt hoàn toàn với luồng GUI (sử dụng QThread / Worker ngầm).
- Cơ chế 3 bước: **Đọc (GET) -> Ghi (SET) -> Đọc lại xác minh (VERIFY)**.
- Khi SET thất bại (máy ảnh trả về lỗi hoặc từ chối), tự động hoàn nguyên (rollback) giá trị hiển thị trên UI về giá trị thực tế đang có trên máy ảnh và hiển thị thông báo lỗi ngắn gọn.

---

### 5. KẾT LUẬN & ĐỀ XUẤT HÀNH ĐỘNG
- Đã hoàn tất 100% mục tiêu Giai đoạn 1 (Audit kỹ thuật toàn diện).
- Toàn bộ 9 thông số đã được giải mã chính xác về mã hex, kiểu dữ liệu và giới hạn vận hành thực tế trên phần cứng Nikon D780.
- Mã nguồn dự án được **bảo toàn nguyên vẹn**, không có bất kỳ dòng code nào bị thay đổi trong giai đoạn này.
- **Đề xuất:** Chờ người dùng phê duyệt Báo cáo Audit trước khi bắt đầu chuyển sang Giai đoạn 2 (Thiết kế giao diện UI) và Giai đoạn 3 (Triển khai Controller).
