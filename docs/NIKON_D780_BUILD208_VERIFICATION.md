# BÁO CÁO BÀN GIAO KỸ THUẬT: NIKON D780 HARDWARE VERIFICATION & FRAME DESIGNER BUILD 208
## DỰ ÁN 1998 TEAM — PHOTOBOOTH (v2.0.1 Build 208 RC)

**Ngày lập:** 2026-11-05  
**Hệ điều hành:** Windows 11 Pro 64-bit  
**Môi trường runtime:** Python 3.12.10 (AMD64)  
**Thiết bị phần cứng đã xác minh:** Nikon D780 (DSLR Full-Frame 24.5 MP)  
**Driver:** Microsoft WPD/MTP (`wpdmtp.inf`, Service `WUDFWpdMtp`)  
**SDK Backend:** Nikon MAID3 Type0026 SDK x64  
**Trạng thái phiên bản:** Version **2.0.1**, Build **208** (Bảo toàn nguyên vẹn)

---

## 1. TỔNG HỢP CÁC THAY ĐỔI NIKON BACKEND

Toàn bộ chu trình điều khiển phần cứng của Nikon D780 đã được sửa đổi, tối ưu hóa và xác minh hoạt động 100% trên thiết bị thật:

| Hạng mục | Cơ chế kỹ thuật | Trạng thái xác minh |
|---|---|---|
| **1. PnP Parser** | Thay thế so khớp chuỗi cứng bằng regex chuẩn hóa `re.search(r"Status\s*:\s*Started\b", block, re.IGNORECASE)` với khả năng cô lập từng khối thiết bị (`Instance ID:` block). Xử lý hoàn hảo hiện tượng output Windows `pnputil` chứa 21 khoảng trắng giữa `Status:` và `Started`. Tích hợp cơ chế Fallback sang PowerShell `Get-PnpDevice` khi `pnputil` gặp lỗi hoặc timeout. | **PASS** (16/16 unit tests) |
| **2. MAID Enumeration** | Khởi tạo module `Type0026.md3` (1.55 MB x64), gọi `NkMAIDCommand.ENUM_CHILDREN`. Nhận diện bất đồng bộ qua sự kiện `NkMAIDEvent.ADD_CHILD` (event 0). Phát hiện máy ảnh thật với **Source ID: 1** (`0x1`) chỉ sau **0.06 giây**. | **PASS** (Thực tế trên D780) |
| **3. Source Object** | Mở phiên điều khiển phần cứng bằng lệnh `NkMAIDCommand.OPEN` với Source ID 1. Khởi tạo đối tượng `_src_obj` và đăng ký callback `EventProc`. Đọc thành công tên định danh thiết bị: **`D780`** (Cap ID 9: `NAME`). | **PASS** (Thực tế trên D780) |
| **4. Live View** | Thiết lập độ phân giải chuẩn XGA (`NkMAIDLiveViewImageSize.XGA = 3`: `1024 × 680`, tỷ lệ 3:2 chuẩn cảm biến full-frame). Kích hoạt `LIVE_VIEW_STATUS = ON_REMOTE_LV (3)`. Đọc luồng dữ liệu liên tục qua `GET_LIVE_VIEW_IMAGE` từ offset 512. Tốc độ thực tế **21.9 FPS**, độ trễ **30.3 ms/frame**, nhận đủ 25/25 frames. Tắt Live View an toàn, hạ gương lật/cảm biến êm ái. | **PASS** (Ảnh mẫu lưu tại `nikon_d780_liveview_sample.jpg`) |
| **5. Still Capture** | Sửa lỗi cú pháp tại dòng 980 `maid_session.py` (`NkMAIDResult.SUCCESS` -> `NkMAIDResult.NO_ERROR`). Cấu hình `SAVE_MEDIA = SDRAM (1)`. Phát lệnh `NkMAIDCommand.CAP_START` (Cap ID 17: `CAPTURE`). Shutter actuation hoàn tất trong **0.80s**, kích hoạt sự kiện âm thanh màn trập `on_capture_start`, nhận sự kiện tạo ảnh mới `NkMAIDEvent.ADD_CHILD` với `Item ID: 0x2B000001`. | **PASS** (Thực tế trên D780) |
| **6. Image Download** | Mở `Item Object (0x2B000001)` và `Data Object (1)`. Kích hoạt `ACQUIRE`, nhận toàn bộ chunks dữ liệu qua callback `DataProc`. Tải trọn vẹn tệp ảnh gốc **5,179,322 bytes (~4.94 MB)** với độ phân giải cảm biến **`6048 × 4024` (24.5 MP)**, Color Mode RGB, chuẩn EXIF `NIKON CORPORATION - NIKON D780`. | **PASS** (Lưu tại `nikon_d780_test_capture_1.jpg`) |
| **7. Cleanup & Teardown** | Đóng tuần tự `Data Object` -> `Item Object` -> `Source Object` -> `Module Object`. Bộ nhớ đệm SDRAM của máy ảnh được giải phóng hoàn toàn, không rò rỉ bộ nhớ hoặc khóa cổng USB. Thử nghiệm Re-discovery ngay sau khi đóng: Hệ thống quét lại và tìm thấy ngay Nikon D780 với `sources=[1]`. | **PASS** (Xác nhận quét lại thành công) |

---

## 2. DANH MỤC CÁC TỆP ĐÃ THAY ĐỔI & MỤC ĐÍCH

```
vietphotobooth/
├── camera/backends/nikon_maid/
│   ├── nikon_d780_backend.py          [SỬA ĐỔI] Thêm parse_pnputil_device_status, check_nikon_d780_pnp, cập nhật discover_devices()
│   ├── maid_session.py                [SỬA ĐỔI] Sửa dòng 980: NkMAIDResult.SUCCESS -> NkMAIDResult.NO_ERROR
│   └── maid_types.py                  [SỬA ĐỔI] Thêm alias SUCCESS = 0 vào enum NkMAIDResult
└── tests/
    ├── test_nikon_pnp_parser.py       [TẠO MỚI] 16 ca kiểm thử độc lập cho PnP regex, multi-device isolation, PowerShell fallback
    └── test_nikon_maid_backend.py     [SỬA ĐỔI] Thêm test_maid_result_success_and_capture_callback()
```

### Chi tiết mục đích sửa đổi:
1. **`vietphotobooth/camera/backends/nikon_maid/nikon_d780_backend.py`**:
   - Khắc phục triệt để Bug A: `pnputil` xuất ra chuỗi `Status:                     Started` (21 khoảng trắng) khiến parser chuỗi cứng trước đó đánh giá `False`, dẫn đến việc bỏ qua hoàn toàn lệnh gọi MAID SDK enumeration.
   - Bổ sung tách khối thiết bị (device isolation) để trạng thái `Started` của thiết bị USB khác không gây nhận diện sai cho Nikon D780.
   - Thêm cơ chế dự phòng an toàn bằng PowerShell `Get-PnpDevice` với xử lý toàn diện các ngoại lệ `TimeoutExpired`, `CalledProcessError`, `FileNotFoundError`.
2. **`vietphotobooth/camera/backends/nikon_maid/maid_session.py`**:
   - Sửa lỗi `AttributeError` tại dòng 980 trong hàm `capture_photo()` do tham chiếu nhầm `NkMAIDResult.SUCCESS` thay vì `NkMAIDResult.NO_ERROR`.
3. **`vietphotobooth/camera/backends/nikon_maid/maid_types.py`**:
   - Bổ sung `SUCCESS = 0` vào enum `NkMAIDResult` để đảm bảo tương thích ngược và ngăn ngừa lỗi runtime tương tự trong tương lai.
4. **`vietphotobooth/tests/test_nikon_pnp_parser.py`**:
   - Bộ unit test toàn diện 16 bài kiểm tra bảo vệ chất lượng mã nguồn: kiểm tra output 21 spaces thực tế, 1 space, tabs, ký tự hoa/thường, từ chối trạng thái `Disconnected`/`Disabled`, kiểm tra cô lập đa thiết bị, kiểm tra fallback PowerShell khi subprocess lỗi hoặc timeout, và xác nhận `discover_devices()` gọi đúng `enumerate_cameras()`.
5. **`vietphotobooth/tests/test_nikon_maid_backend.py`**:
   - Thêm bài kiểm thử mock xác minh `NkMAIDResult.NO_ERROR == NkMAIDResult.SUCCESS == 0` và callback `on_capture_start` kích hoạt thành công.

---

## 3. CẤU HÌNH SDK & DRIVER WINDOWS CẦN BẢO TOÀN

Để máy ảnh Nikon D780 tiếp tục vận hành ổn định trên Windows, **BẮT BUỘC BẢO TOÀN NGUYÊN VẸN** các thiết lập hệ thống sau:

### 3.1. Windows Driver
- **Driver bắt buộc:** Microsoft WPD/MTP chuẩn (`wpdmtp.inf`).
- **Service quản lý:** `WUDFWpdMtp` (Windows Driver Foundation - User-mode Driver Framework).
- **Phân lớp thiết bị:** Class `WPD` (`{eec5ad98-8080-425f-922a-dabf3de3f69a}`).
- **Cấm kỵ phần cứng:**
  - **TUYỆT ĐỐI KHÔNG** sử dụng Zadig hoặc cài đè WinUSB / libusb lên thiết bị Nikon D780.
  - **TUYỆT ĐỐI KHÔNG** xóa hoặc sửa `LowerFilters` trong Registry của Windows WPD.

### 3.2. Cấu hình Binary SDK Type0026 x64
Thư mục gốc: `vietphotobooth/camera/backends/nikon_maid/bin/x64/`
- `Type0026.md3` (1.55 MB, chứa 303 lớp capability C++ của Nikon D780).
- `NkdPTP.dll` (Thư viện giao thức PTP USB giao tiếp native x64).
- `NkRoyalmile.dll` (Thư viện tầng lõi Nikon SDK).
- `dnssd.dll` (Thư viện phụ trợ mạng/discovery của SDK).
- Cấu trúc struct trong Python `ctypes` bắt buộc giữ nguyên căn chỉnh `_pack_ = 2`.

### 3.3. Thiết lập trên thân máy ảnh Nikon D780
- **Menu c2 (Standby Timer):** Đặt thành `No limit` (Không giới hạn) để ngăn máy ảnh tự ngắt kết nối USB khi ở chế độ chờ.
- **Cổng kết nối:** Cáp USB Type-C cắm trực tiếp vào bo mạch chủ (Mainboard USB 3.0/3.1 port), tránh qua USB Hub không trợ lực nguồn.

---

## 4. KẾT QUẢ KIỂM THỬ THỰC TẾ

### 4.1. Dữ liệu phần cứng thật (Hardware Verification)
- **Live View Stream:**
  - Khung hình mẫu: `tests_output/nikon_d780_verification/nikon_d780_liveview_sample.jpg` (298,645 bytes).
  - Độ phân giải: **`1024 × 680` (XGA)**.
  - Tốc độ khung hình: **21.9 FPS** (ổn định liên tục 25 frames).
  - Độ trễ trung bình: **30.3 ms/frame**.
- **Chụp ảnh độ phân giải gốc:**
  - Tệp ảnh lưu: `tests_output/nikon_d780_verification/nikon_d780_test_capture_1.jpg` (5,179,322 bytes).
  - Độ phân giải gốc: **`6048 × 4024` pixels** (Full-Frame 24.5 Megapixels).
  - Định dạng: MPO/JPEG (Exif đầy đủ thông số Make/Model/Firmware/Orientation/DPI).

### 4.2. Bộ kiểm thử tự động (Automated Test Suite)
1. **Toàn bộ 25 bài kiểm thử Nikon Backend:**
   ```text
   py -3.12 -m pytest vietphotobooth/tests/test_nikon_maid_backend.py vietphotobooth/tests/test_v150_nikon_maid_integration.py vietphotobooth/tests/test_nikon_pnp_parser.py
   ============================= 25 passed in 1.75s =============================
   ```
   -> **25/25 tests PASS 100%**.

2. **Toàn bộ 9 bài kiểm thử Responsive UI của Frame Designer (Build 208):**
   ```text
   py -3.12 -m pytest vietphotobooth/tests/test_frame_designer_responsive.py
   ============================= 9 passed in 13.94s ==============================
   ```
   -> **9/9 tests PASS 100%**, xác nhận giao diện Frame Designer Build 208 hoàn toàn không bị ảnh hưởng, không clipping ở mọi độ phân giải (1277×752, 1366×768, 1600×900, 1920×1080).

---

## 5. CÁC GIỚI HẠN CHƯA ĐƯỢC XÁC MINH (CẦN LƯU Ý KHI VẬN HÀNH)

Mặc dù giao tiếp cốt lõi (Live View, Shutter, Download, Cleanup) đã hoạt động hoàn hảo, các khía cạnh vận hành thực địa sau đây **chưa được kiểm thử dài hạn**:

1. **Độ ổn định trong phiên chụp kéo dài:**
   - Chưa kiểm thử vận hành liên tục 4–8 tiếng trong tiệc cưới/sự kiện thực tế (nhiệt độ cảm biến khi bật Live View liên tục, tình trạng cạn pin camera nếu không dùng bộ cấp nguồn giả AC Adapter EP-5B / EH-5d).
2. **Chụp liên tục nhiều ảnh (Burst / Multi-shot):**
   - Mới kiểm thử chụp đơn lẻ từng phát (single shot). Chưa kiểm nghiệm chuỗi chụp liên tiếp 4 phát trong quy trình Kiosk (đếm ngược 3-2-1 chụp liên tục 4 ảnh).
3. **Autofocus và các chế độ lấy nét thực tế:**
   - Kiểm thử thực tế hiện tại đang tắt lấy nét trước chụp (`autofocus_first=False`) để ưu tiên phản hồi màn trập tức thì (thường photobooth đặt khẩu nhỏ F/5.6 - F/8 và lấy nét tay MF cố định sẵn khoảng cách). Chế độ Contrast AF trong Live View hoặc Phase Detection AF cần kiểm thử thêm với điều kiện ánh sáng thực tế tại sự kiện.
4. **Khả năng tương thích với các dòng máy ảnh Nikon khác:**
   - Mã nguồn đã được tối ưu cho Nikon D780 (Type0026 SDK). Các dòng máy khác như Nikon Z5, Z6 II, Zfc, D750, D850 sử dụng các module MAID khác (`Type0024.md3`, `Type0020.md3`, v.v.) chưa được kiểm thử trong phạm vi đợt này.
5. **Kiểm thử tích hợp đồng thời với máy in DNP DS-RX1HS:**
   - Chưa kiểm thử một phiên photobooth khép kín đầu-cuối: Khách đứng trước booth -> Live View D780 hiển thị trên màn hình cảm ứng -> Đếm ngược 3-2-1 -> Chụp 4 ảnh 24.5MP -> Ghép template 4x6 -> Lệnh in gửi tới máy in nhiệt DNP DS-RX1HS -> Cắt ảnh và nhả ảnh ra khay.

---

## 6. KẾT LUẬN & BÀN GIAO

- **Hệ thống Nikon MAID Native USB của 1998 TEAM Photobooth đã sẵn sàng vận hành thực tế.**
- Toàn bộ working tree và mã nguồn được bảo toàn tuyệt đối, không thay đổi số phiên bản, không tự ý đóng gói bộ cài.
- Báo cáo này đóng vai trò tài liệu kỹ thuật chuẩn mực cho các phiên phát triển và kiểm thử thực địa tiếp theo.
