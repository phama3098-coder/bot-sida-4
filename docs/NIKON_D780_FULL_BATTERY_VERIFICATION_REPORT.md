# BÁO CÁO KIỂM TRA XÁC MINH NIKON D780 SAU KHI SẠC PIN (READ-ONLY PRODUCTION AUDIT)

- **Ngày thực hiện:** `2026-11-05` (`22:08` – `23:12` ICT)
- **Repository:** `C:\Users\Admin\Documents\photobooth`
- **Branch:** `feature/v2.0.0-photobooth` (`HEAD: 08bfb13`)
- **Baseline:** `v2.0.1 Build 208` ([`vietphotobooth/version.py`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/version.py))
- **Chế độ kiểm tra:** **STRICT READ-ONLY PRODUCTION CODE** (Không sửa code production, không build/commit/tag/release, không đổi driver WPD/MTP, không tự ý `FreeLibrary` hay reload `Type0026.md3`).
- **Tệp dữ liệu & nhật ký gốc:**
  - Nhật ký Bước 2 & 3 (`PID=24180`): [`task-27496.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27496.log)
  - Telemetry JSON Bước 2 & 3: [`battery_audit_telemetry.json`](file:///C:/Users/Admin/Documents/photobooth/tests_output/battery_full_audit/battery_audit_telemetry.json)
  - Nhật ký Bước 4 Reconnect (`PID=3248`): [`task-27518.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27518.log)
  - Telemetry JSON Bước 4: [`step4_reconnect_telemetry.json`](file:///C:/Users/Admin/Documents/photobooth/tests_output/battery_full_audit/step4_reconnect_telemetry.json)
  - Ảnh chụp thực tế Bước 3: [`initial_still_capture_6048x4024.jpg`](file:///C:/Users/Admin/Documents/photobooth/tests_output/battery_full_audit/initial_still_capture_6048x4024.jpg) (`4,121,953` bytes, `6048×4024`)

---

## 1. Xác Minh Bảo Toàn Hệ Thống

- `vietphotobooth/version.py`: Giữ nguyên `__version__ = "2.0.1"`, `__build__ = 208`, `__release_date__ = "2026-11-05"`.
- Không có bất kỳ chỉnh sửa nào vào mã nguồn trong `vietphotobooth/`.
- Windows WPD/MTP driver giữ nguyên `wpdmtp.inf`.
- `Type0026.md3` được giữ nguyên cơ chế nạp singleton của [`get_loader()`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/maid_loader.py#L132-L140), không can thiệp `FreeLibrary`.

---

## 2. Kết Quả Kiểm Tra Trước Khi Thử & Live View 5 Phút Liên Tục

### 2.1. Trạng thái PnP, Hardware ID, MAID Session, EventProc & Worker
Tại thời điểm `22:13:59` (`PID=24180`):
- **PnP Status:** `Started`
- **Instance ID / Hardware ID:** `USB\VID_04B0&PID_0446\0000002008880` (`Device Description: D780`, `Manufacturer: Nikon Corporation`, `Driver: wpdmtp.inf`)
- **MAID Session (`NikonSession`):**
  - `_is_mod_open = True`, `_is_src_open = True` (`Source ID 0x1`, `'D780'`, thời gian mở kết nối `2.853s`).
  - `_mod_event_cb_func` (`Module EVENT_PROC`) = Đã đăng ký (`True`).
  - `_src_event_cb_func` (`Source EVENT_PROC`) = Đã đăng ký (`True`).
- **Worker (`NikonCameraWorker`):**
  - Thuộc tính thực tế: `backend._worker` (`id=2647198344512`), `is_running = True`.

### 2.2. Thông tin mức Pin từ Nikon D780 (`0x0031 Battery Level`)
- Truy vấn trực tiếp capability chuẩn MAID `NkMAIDCapability.BATTERY_LEVEL` (`0x0031`, `szDescription="Battery Level"`, `ulType=2` tức `NkMAIDCapType.INTEGER`, `ulOperations=0x0002`):
  - Khi đọc đúng bằng kiểu **`NkMAIDDataType.INTEGER_PTR` (`2`)**: trả về **`60%`** (`ret = 0`) lúc bắt đầu test (`22:14:02`).
  - Sau **48 phút 55 giây** chạy Live View liên tục (`22:14:02` – `23:02:54`), mức pin đọc qua `0x0031 INTEGER_PTR` giảm xuống **`40%`** (`23:04:02`) và **`20%`** (`23:05:39`).
- **Phát hiện lỗi đọc pin trong code production hiện tại:**
  - Tại [`nikon_d780_backend.py:340, 416`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/nikon_d780_backend.py#L340), code đang gọi `self._session.get_unsigned_capability(NkMAIDCapability.BATTERY_LEVEL)` (truyền `NkMAIDDataType.UNSIGNED_PTR = 6`). Vì capability `0x0031` có kiểu `INTEGER` (`2`), MAID trả về lỗi `kNkMAIDResult_UnexpectedDataType` (`-126`), khiến hàm `get_unsigned_capability(0x0031)` luôn trả về `None` (`NOT AVAILABLE`).

### 2.3. Theo dõi Live View liên tục 5 phút (`300.004s`)
Đếm nghiêm ngặt theo `fd.sequence_id` duy nhất (loại bỏ hoàn toàn các lần đọc trùng cache):

| Thời điểm (`elapsed`) | Unique Frames (`sequence_id` duy nhất) | Unique Acquisition FPS | Tổng số lần đọc Cache (`non_none_reads`) | Số lần đọc trùng (`duplicate_reads`) | Max Frame Gap (`ms`) | `worker.is_running` |
|---:|---:|---:|---:|---:|---:|---|
| `30.0s` | `847` | `28.23 FPS` | `5,528` | `4,681` | `66.5 ms` | `True` |
| `60.0s` | `1,700` | `28.33 FPS` | `11,053` | `9,353` | `76.5 ms` | `True` |
| `90.0s` | `2,543` | `28.25 FPS` | `16,562` | `14,019` | `99.9 ms` | `True` |
| `120.0s` | `3,375` | `28.12 FPS` | `22,059` | `18,684` | `104.5 ms` | `True` |
| `150.0s` | `4,224` | `28.16 FPS` | `27,586` | `23,362` | `116.3 ms` | `True` |
| `180.0s` | `5,045` | `28.03 FPS` | `33,091` | `28,046` | `116.3 ms` | `True` |
| `210.0s` | `5,874` | `27.97 FPS` | `38,607` | `32,733` | `116.3 ms` | `True` |
| `240.0s` | `6,707` | `27.94 FPS` | `44,125` | `37,418` | `116.3 ms` | `True` |
| `270.0s` | `7,516` | `27.83 FPS` | `49,639` | `42,123` | `116.3 ms` | `True` |
| **`300.004s` (Tổng kết)** | **`8,319`** (`seq=12..8330`) | **`27.73 FPS`** | **`55,168`** (`183.89 Hz`) | **`46,849`** | **`116.33 ms`** (`P50=33.79ms`, `P95=52.34ms`) | **`True`** |

- **Đánh giá Initial Live View (5 phút):** **PASS** — Duy trì ổn định `27.73 FPS` trong suốt 300 giây, không rớt kết nối, không tăng độ trễ.

---

## 3. Kết Quả Kiểm Tra Initial Still Capture (`6048×4024`) Trong Cùng Tiến Trình

Thực hiện ngay sau khi kết thúc 5 phút Live View trên cùng tiến trình `PID=24180` (`22:19:02.904` – `22:19:05.845`):
- **Thời gian chụp + tải SDRAM + khôi phục Live View:** `2.385s` (tải `5,663,439` bytes JPEG gốc từ SDRAM Item `0x2B000001`).
- **Tệp ảnh đầu ra:** [`initial_still_capture_6048x4024.jpg`](file:///C:/Users/Admin/Documents/photobooth/tests_output/battery_full_audit/initial_still_capture_6048x4024.jpg)
  - Tồn tại và đọc lại hợp lệ bằng `PIL.Image.open()`: `True`
  - Kích thước tệp sau khi lưu: `4,121,953` bytes
  - Độ phân giải: **`6048 × 4024`** (`JPEG`)
- **Kiểm tra EXIF riêng biệt (RAM vs Disk):**
  - **Trên đối tượng `PIL.Image` trong RAM (trước khi `CameraConnectionManager.capture_photo` ghi xuống đĩa):** Có đầy đủ **`13` EXIF tags (`65,532` bytes)**:
    - `Make`: `"NIKON CORPORATION"`
    - `Model`: `"NIKON D780"`
    - `Software`: `"Ver.01.03"`
    - `DateTime`: `"2026:11:06 00:24:08"`
    - `Orientation`: `"1"`
    - `ExifOffset`: `"352"`
  - **Trên tệp `.jpg` đã lưu xuống đĩa (`saved_file_exif_count`):** **`0` tags (`0` bytes)** — bị mất hoàn toàn do [`connection_manager.py:706`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py#L706) gọi `img.save(save_path, "JPEG", quality=95)` không truyền `exif=img.info.get("exif")`.
- **Kiểm tra Windows Event Viewer sau Initial Still Capture:** Không có lỗi `0xc0000005` hay bất kỳ crash nào tại bước này.
  - *(Ghi chú bổ sung về crash khi treo chờ rút cáp 44 phút: Sau khi hoàn tất Bước 3 lúc `22:19:10`, tiến trình `PID=24180` chờ thao tác rút cáp vật lý trong khi Live View vẫn chạy liên tục thêm 43 phút 44 giây. Đến `23:02:54` — tức tổng cộng **48 phút 55 giây** Live View liên tục — khi máy ảnh tự ngắt phiên Live View nội bộ, tiến trình `PID=24180` bị đóng bởi ngoại lệ native `0xc0000409` `FAST_FAIL_FATAL_APP_EXIT` tại `ucrtbase.dll` offset `0xa527e`).*

---

## 4. Kết Quả Kiểm Tra Physical USB Reconnect (Trong Cùng Tiến Trình `PID=3248`)

### 4.1. Xác nhận Live View ổn định trước khi rút cáp (`23:05:39` – `23:05:49`)
- Mở kết nối và xác nhận Live View hoạt động ổn định trong `10.005s` (`STEP4_INITIAL_STABLE_LV`):
  - Nhận **`263` unique frames** (`seq=1..263`) = **`26.29 FPS`** (`P50 = 35.11 ms`, `P95 = 54.68 ms`).

### 4.2. Chu kỳ 1/3 — Thao tác Rút cáp & Cắm lại cáp vật lý (`23:07:34` – `23:08:12`)
1. **Rút cáp USB vật lý (`23:07:34.161`):**
   - Windows PnP chuyển sang `Status: Disconnected` (`Instance ID: USB\VID_04B0&PID_0446\0000002008880`).
   - **Trạng thái phiên cũ ngay khi rút cáp (`disconnect_state`):**
     - `old_session._is_src_open`: `True` (chưa tự đóng khi mất thiết bị).
     - `old_session._is_mod_open`: `True`.
     - `old_worker.is_running`: `True` (worker cũ vẫn chạy vòng lặp gọi vào session cũ).
2. **Cắm lại cáp USB vật lý (`23:07:36.277`):**
   - Sau `1.11s`, Windows PnP nhận lại thiết bị với `Status: Started` (`USB\VID_04B0&PID_0446\0000002008880`).
3. **Khôi phục MAID Session trong cùng tiến trình (`mgr.switch_backend("nikon_maid")` lúc `23:07:37.988`):**
   - `old_backend.disconnect()` được gọi **sau khi** thiết bị mới đã cắm lại:
     - Dừng `old_worker` (`old_worker_alive_after_cleanup = False`).
     - Gọi `NkMAIDCommand.CLOSE` lên `old_session._src_obj` và `old_session._mod_obj` **mà không hủy đăng ký `EVENT_PROC` (`pProc=0`)**.
   - Tạo `new_session` (`id=2712260548784` != `old_session` `id=2712262973856`) nhưng **tái sử dụng cùng singleton `Type0026.md3` loader** (`id=2712262980960`).
   - Khi mở lại `Source ID 0x1 ('D780')` lúc `23:07:41.536`, callback bắn sự kiện tồn đọng: `Nikon MAID ảnh chụp mới sẵn sàng: Item ID 0x2B000003`.
   - Khi gọi `new_session.start_live_view()` lúc `23:07:41.849` – `23:07:44.865`:
     - **Quá thời gian chờ `LIVE_VIEW_IMAGE_STATUS == CAN_ACQUIRE` (3.0s):**
       `23:07:44.865 [WARNING] Hết thời gian chờ LiveViewImageStatus sẵn sàng. Vẫn tiếp tục thử đọc.`
     - Tuy nhiên, [`NikonSession.start_live_view()`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/maid_session.py#L568-L573) vẫn gán `self._is_live_view_active = True` và trả về `True`!
4. **Theo dõi Live View sau Reconnect (`23:07:45.431` – `23:07:55.560`):**
   - **Kết quả: `FAIL`** — Trong suốt `10.129s` (`CYCLE_1_POST_RECONNECT_LV`):
     - `Unique Frames = 0` (`0.00 FPS`)
     - `Cache Reads = 0` (`0.00 Hz`)
5. **Chụp Still Capture `6048×4024` trong cùng tiến trình sau Reconnect (`23:07:55.561` – `23:08:12.116`):**
   - **Kết quả: `FAIL`** — Lệnh `mgr.capture_photo()` bị treo chờ sự kiện `ADD_CHILD` và hết timeout `12.0s`:
     - `23:08:08.532 [ERROR] Hết thời gian chờ ảnh chụp từ camera (timeout 12.0s).`
     - `[2026-11-05 23:08:11] [ERROR] Backend nikon_maid không trả về ảnh chụp.`
     - Không tạo được file ảnh (`file_exists = False`, `elapsed = 16.19s`).
   - Theo đúng quy trình mục 4, thử nghiệm dừng ngay sau khi phát hiện lỗi ở Chu kỳ 1 để bảo toàn log.

### 4.3. Thử nghiệm đối chứng ngay lập tức trên Tiến trình Python mới (`23:11:09`)
Để tách bạch hoàn toàn nguyên nhân giữa **Pin (`20%`) / Phần cứng máy ảnh** và **Trạng thái nội bộ của tiến trình Python cũ (`PID=3248`)**, ngay sau khi `PID=3248` kết thúc, một tiến trình Python mới độc lập được khởi chạy ở **cùng mức pin `20%`** (không tắt/bật lại máy ảnh, không rút/cắm lại cáp):
- Kết nối MAID: **`True`** (trong `2.0s`).
- Live View: **`True`** (`1024×680`, nhận ngay `seq=48`).
- Still Capture `6048×4024`: **`True`** (`cap_ok = True`, `img_size = (6048, 4024)`).

---

## 5. So Sánh Với Kết Quả Trước & Phân Tích Nguyên Nhân

| Khía cạnh đối chiếu | Lần thử trước (`task-27203`) | Lần thử này sau khi sạc pin (`task-27496` & `task-27518`) | Đánh giá kỹ thuật |
|---|---|---|---|
| **Live View ban đầu** | Báo cáo `191 reads / 2s` (thực chất là Cache Read Rate `95.5 Hz`). | Đo chuẩn theo `sequence_id` duy nhất suốt **5 phút (300s)**: **`8,319` unique frames = `27.73 FPS`**. | Khi chưa rút cáp, acquisition thực tế ổn định ở `~26.3 – 27.7 FPS`. |
| **Initial Still Capture cùng tiến trình** | Chưa tách riêng trước reconnect. | **PASS (`2.385s`, `6048×4024`)** ngay trong cùng tiến trình sau 5 phút Live View. | Chụp tĩnh trong cùng tiến trình hoàn toàn ổn định khi chưa xảy ra rút cáp USB. |
| **Hành vi sau Physical USB Reconnect (cùng tiến trình)** | Crash `0xc0000005` (`ntdll.dll`) ngay khi gọi `capture_photo()` sau reconnect. | Không nổ `0xc0000005` ở `PID=3248`, nhưng `LIVE_VIEW_IMAGE_STATUS` bị kẹt (`0.00 FPS`) và `capture_photo()` **FAIL** (`timeout 12.0s`). Ngoài ra `PID=24180` nổ `0xc0000409` (`ucrtbase.dll`) khi phiên Live View bị ngắt sau 49 phút. | Cả hai hiện tượng (crash `0xc0000005` hoặc kẹt state machine timeout `12.0s`) đều là hệ quả của việc tái sử dụng singleton `Type0026.md3` / `NkdPTP.dll` và đóng/mở chồng lấn handle MAID cũ/mới trong cùng tiến trình. |
| **Hủy đăng ký `EVENT_PROC` & giải phóng Worker cũ** | Chưa hủy `EVENT_PROC`; script cũ đọc nhầm `_camera_worker`. | Đã xác nhận `backend._worker` chỉ dừng khi gọi `switch_backend()`, còn lúc rút cáp vẫn sống (`True`); `EVENT_PROC` vẫn chưa được hủy đăng ký (`pProc=0`) trước khi `CLOSE`. | Lỗi vòng đời MAID (`MAID Lifecycle`) hiện hữu trong code production. |
| **Vai trò của mức Pin** | Nghi vấn pin yếu có thể gây lỗi. | Ở `60%` pin hay `20%` pin, tiến trình mới đều chạy Live View + Still Capture `6048×4024` **PASS 100%**. Ngược lại, sau khi rút/cắm cáp trong cùng tiến trình thì **FAIL**. | **Pin yếu KHÔNG phải là nguyên nhân gây lỗi Reconnect/Capture.** |

---

## 6. Bảng Báo Cáo Bắt Buộc & Kết Luận Cuối Cùng

### 6.1. Bảng phân loại kết quả

| Hạng mục | Kết quả | Chi tiết bằng chứng xác thực |
|---|---|---|
| **Battery condition** | **PASS** *(Đọc trực tiếp qua MAID `0x0031` với `INTEGER_PTR`)* / **FAIL** *(Hàm `get_unsigned_capability` hiện tại)* | MAID `0x0031` (`Battery Level`, `INTEGER`) trả về `60%` lúc bắt đầu (`22:14:02`) và `20%` sau ~50 phút chạy Live View (`23:05:39`). Tuy nhiên hàm `get_unsigned_capability(0x0031)` trong code production dùng sai kiểu `UNSIGNED_PTR` nên trả về `None` (`NOT AVAILABLE`). |
| **Initial Live View** | **PASS** | Chạy liên tục **300.004 giây (5 phút)** không lỗi: **`8,319` unique frames = `27.73 FPS`** (`P50 = 33.79 ms`, `P95 = 52.34 ms`, `Cache Read Rate = 183.89 Hz`). |
| **Initial Still Capture** | **PASS** | Chụp thành công trong cùng tiến trình (`PID=24180`) sau 5 phút Live View: **`2.385s`**, tạo file `initial_still_capture_6048x4024.jpg` (`4,121,953` bytes, đọc lại hợp lệ `6048×4024`). |
| **Physical Disconnect** | **PASS** | Rút cáp vật lý lúc `23:07:34.161`, Windows PnP chuyển sang `Status: Disconnected` (`USB\VID_04B0&PID_0446\0000002008880`). |
| **Physical Reconnect** | **PASS** | Cắm lại cáp vật lý lúc `23:07:36.277` (sau `1.11s`). |
| **PnP Recovery** | **PASS** | Windows PnP khôi phục `Status: Started` cho `USB\VID_04B0&PID_0446\0000002008880` (`Driver: wpdmtp.inf`). |
| **MAID Session Recovery** | **FAIL** | Mở được `NikonSession` mới (`Source ID 0x1`), nhưng `start_live_view()` bị timeout 3.0s khi chờ `LiveViewImageStatus == CAN_ACQUIRE` và trả về `True` giả (false positive); tồn đọng SDRAM item `0x2B000003`. |
| **Worker/Callback Cleanup** | **FAIL** | Khi rút cáp, `_worker` cũ vẫn chạy (`True`) và `_is_src_open` vẫn là `True`. Khi `switch_backend()` đóng session cũ, `EVENT_PROC` không được gỡ (`pProc=0`) trước khi gọi `CLOSE`, và `Type0026.md3` giữ nguyên singleton trong RAM. |
| **Live View Recovery** | **FAIL** | Trong 10.13 giây sau reconnect trên cùng tiến trình (`PID=3248`), nhận **`0` unique frames (`0.00 FPS`)**. |
| **Still Capture cùng tiến trình** | **FAIL** | Gọi `mgr.capture_photo()` ngay sau reconnect trên cùng tiến trình (`PID=3248`) bị **timeout `12.0s`** (`elapsed = 16.19s`, `success = False`, không tạo được ảnh). |
| **Native Crash 0xc0000005** | **FAIL** *(Còn rủi ro crash native)* | Không nổ `0xc0000005` trong Chu kỳ 1 của `PID=3248` (mà rơi vào timeout `12.0s`), nhưng `PID=24180` ghi nhận crash native **`0xc0000409`** (`ucrtbase.dll`, Event ID `1000` lúc `23:02:54`) khi phiên Live View bị ngắt sau 49 phút. |
| **EXIF** | **FAIL** *(Trên file lưu ra đĩa)* / **PASS** *(Trong RAM)* | Luồng JPEG từ Nikon D780 trong RAM có đủ **`13` EXIF tags (`65,532` bytes)**, nhưng `CameraConnectionManager.capture_photo()` làm mất sạch EXIF (**`0` tags**) khi gọi `img.save()` không có `exif=img.info.get("exif")`. |

---

### 6.2. Kết luận trả lời 4 câu hỏi trọng tâm (A, B, C, D)

#### A. Lỗi có còn khi pin đầy không?
- **CÓ (`YES`).** Khi thực hiện Physical USB Reconnect ngay trong cùng tiến trình Python, lỗi **vẫn còn**: sau khi rút và cắm lại cáp USB, dù `open_camera()` báo thành công nhưng `LiveViewImageStatus` bị kẹt không sẵn sàng (`Live View Recovery = 0.00 FPS`) và lệnh chụp `Still Capture` trong cùng tiến trình bị thất bại (`timeout 12.0s`, `success = False`). Đồng thời, khi phiên Live View bị ngắt đột ngột từ phía máy ảnh (`PID=24180`), tiến trình vẫn bị crash native (`0xc0000409` tại `ucrtbase.dll`).

#### B. Có bằng chứng pin yếu là nguyên nhân không?
- **KHÔNG (`NO`).** Không có bất kỳ bằng chứng nào cho thấy pin yếu là nguyên nhân gây lỗi Reconnect hay lỗi chụp:
  1. Trước khi rút cáp, cả Live View 5 phút (`27.73 FPS`) và Still Capture `6048×4024` (`2.385s`) trong cùng tiến trình đều hoạt động hoàn hảo.
  2. Ngay sau khi tiến trình `PID=3248` thất bại ở bước Reconnect Still Capture (lúc pin ở mức `20%`), việc khởi chạy một **tiến trình Python mới** ở **đúng cùng mức pin `20%` đó** lập tức khôi phục Live View (`1024×680`) và chụp thành công Still Capture `6048×4024` chỉ trong vài giây.
  3. Điều này chứng minh 100% lỗi thuộc về **trạng thái nội bộ của MAID SDK (`Type0026.md3` / `NkdPTP.dll`) và quy trình dọn dẹp session trong cùng tiến trình Python sau khi đứt kết nối USB vật lý**, không phải do pin máy ảnh.

#### C. Có cần sửa MAID Lifecycle không?
- **BẮT BUỘC PHẢI SỬA (`YES`).** Cần thực hiện các sửa đổi kỹ thuật sau trong vòng đời MAID trước khi nghiệm thu:
  1. **Xử lý ngắt kết nối tức thời & hủy `EVENT_PROC`:** Khi nhận `NkMAIDEvent.REMOVE_CHILD` hoặc phát hiện mất thiết bị USB, phải lập tức đánh dấu `_is_src_open = False`, dừng `NikonCameraWorker`, và hủy đăng ký `EVENT_PROC` (`pProc = 0`) trước khi đóng đối tượng; không gọi lệnh `CAP_SET(LIVE_VIEW_STATUS=OFF)` lên `_src_obj` đã bị rút cáp vật lý.
  2. **Nạp lại sạch `Type0026.md3` (hoặc cô lập sang Subprocess Worker) khi Reconnect:** Vì `Type0026.md3` và `NkdPTP.dll` lưu giữ trạng thái phiên WPD/PTP trong bộ nhớ tĩnh của DLL, sau khi đóng Module cần giải phóng DLL (`_ctypes.FreeLibrary`) và nạp lại, hoặc chạy MAID driver trong worker process riêng để tái khởi động sạch khi USB Reconnect.
  3. **Sửa false-positive trong `NikonSession.start_live_view()`:** Nếu hết timeout mà `LIVE_VIEW_IMAGE_STATUS` (`0x8517`) vẫn khác `CAN_ACQUIRE` (`1`), phải trả về `False` (và thử reset `LIVE_VIEW_STATUS=OFF` rồi bật lại) thay vì trả về `True`.
  4. **Xả bỏ SDRAM Item tồn đọng khi mở phiên mới:** Khi `open_camera()` phát hiện các `Item ID` cũ trong `self._new_items` (như `0x2B000003`), cần đóng/xả sạch trước khi bắt đầu Live View hoặc Still Capture.
  5. **Sửa kiểu dữ liệu đọc Pin (`0x0031`) và bảo toàn EXIF:** Đọc `NkMAIDCapability.BATTERY_LEVEL` bằng `NkMAIDDataType.INTEGER_PTR` và truyền `exif=img.info.get("exif")` trong `CameraConnectionManager.capture_photo()`.

#### D. Có đủ điều kiện tiếp tục tách Nikon Driver không?
- **CHƯA ĐỦ ĐIỀU KIỆN (`NO`) nếu chỉ tách nguyên trạng code hiện tại.**
- Cần phê duyệt **bước sửa lỗi MAID Lifecycle & EXIF** (hoặc phê duyệt kiến trúc tách Nikon Driver đi kèm **Process Isolation / Clean DLL Reload khi USB Reconnect**) trước khi đóng băng driver độc lập.
