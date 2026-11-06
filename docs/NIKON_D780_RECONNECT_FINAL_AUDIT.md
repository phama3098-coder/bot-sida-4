# BÁO CÁO ĐỐI SOÁT ĐỘC LẬP CUỐI CÙNG (FINAL READ-ONLY AUDIT): NIKON D780 LIVE VIEW & PHYSICAL USB RECONNECT

**Dự án:** 1998 TEAM Photobooth  
**Phiên bản kiểm toán:** `v2.0.1 Build 208` (Kênh: `RC2`)  
**Thiết bị mục tiêu:** Nikon D780 (USB 3.0, Hardware ID `USB\VID_04B0&PID_0446`, Driver `wpdmtp.inf`, SDK `Type0026.md3`)  
**Chế độ kiểm toán:** **READ-ONLY AUDIT** (Không sửa code production, không đổi version, không build/commit/tag/release)  
**Thời điểm thực hiện:** 2026-11-05 21:50 (+07:00)

---

## QUY ƯỚC PHÂN LOẠI KIỂM TOÁN

- **VERIFIED**: Có nhật ký hệ thống (raw log), mã nguồn thực thi hoặc tệp bằng chứng trực tiếp chứng minh.
- **REPORTED**: Chỉ có số liệu/nhận định trong báo cáo trước đó, không có log chạy thực tế trực tiếp cho chỉ số đó.
- **NOT VERIFIED**: Chưa thu thập đủ dữ liệu log chi tiết để khẳng định.
- **FAILED**: Có bằng chứng trực tiếp trong code hoặc nhật ký hệ thống cho thấy sai lệch phương pháp đo hoặc lỗi thực thi.

---

## PHẦN A: XÁC MINH SỐ FRAME THỰC TẾ (191 FRAMES / 2S VÀ 287 FRAMES / 3S)

### A.1. Hai con số 191 và 287 được đếm bằng `sequence_id` duy nhất hay số lần đọc cache?
- **Trạng thái kiểm toán:** **FAILED (Phương pháp đo trong script đếm số lần đọc cache, KHÔNG đếm `sequence_id` duy nhất)** — Bản chất con số đã được **VERIFIED** qua mã nguồn script.
- **Bằng chứng trực tiếp:**
  Tại tệp [`run_physical_usb_reconnect_interactive.py`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/scratch/run_physical_usb_reconnect_interactive.py#L64-L71) (dòng 64–71 và dòng 210–217):
  ```python
  # Giai đoạn 1 (2.0 giây đầu):
  init_frames = 0
  t0_init = time.perf_counter()
  while time.perf_counter() - t0_init < 2.0:
      app.processEvents()
      fd = mgr.get_frame_data()
      if fd and getattr(fd, "has_rgb", False):
          init_frames += 1
      time.sleep(0.01)

  # Giai đoạn 5 (3.0 giây sau reconnect):
  rec_stream_frames = 0
  t0_rec_stream = time.perf_counter()
  while time.perf_counter() - t0_rec_stream < 3.0:
      app.processEvents()
      fd = mgr.get_frame_data()
      if fd and getattr(fd, "has_rgb", False):
          rec_stream_frames += 1
      time.sleep(0.01)
  ```
- **Nguyên nhân kỹ thuật:**
  - Hàm [`CameraConnectionManager.get_frame_data()`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py#L498-L503) trả về ngay lập tức biến `self._latest_frame` đang nằm trong RAM (`with self._frame_lock: return self._latest_frame`).
  - Vòng lặp `while` ngủ `time.sleep(0.01)` (~10.45 ms/vòng tính cả `app.processEvents()`), tức chạy ở tần số **~95.5 – 95.7 vòng/giây**.
  - Do đó:
    - `191 frames trong 2s` thực chất là **191 lần đọc cache RAM** ($191 / 2.0\text{s} = 95.50\text{ reads/s}$).
    - `287 frames (3.0s)` thực chất là **287 lần đọc cache RAM** ($287 / 3.0\text{s} = 95.67\text{ reads/s}$).

---

### A.2. Có kiểm tra `timestamp` và loại bỏ duplicate `sequence_id` không?
- **Trạng thái kiểm toán:** **FAILED**
- **Bằng chứng trực tiếp:**
  - Trong `run_physical_usb_reconnect_interactive.py` (tạo ra log [`task-27203.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27203.log)), script **hoàn toàn không đọc `fd.sequence_id` hay `fd.timestamp`** và **không lọc bỏ frame trùng lặp**.
  - Tương tự, trong [`task-27116.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27116.log#L27) (dòng 27: `Live View nhan duoc: 193 frames sau reconnect` trong 2s với `sleep(0.01)`), con số `193` cũng là số lần đọc cache mà không lọc `sequence_id`.
  - Ngược lại, chỉ có bài đo Point 1 & Point 2 trong [`task-27108.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27108.log#L29-L43) (`verify_nikon_deep_audit.py`) mới thực sự dùng `seen_sequence_ids` và `seq != last_hw_seq` để loại bỏ duplicate `sequence_id`.

---

### A.3. Danh sách `sequence_id` và `timestamp` thực tế trong khoảng đo
- **Đối với cửa sổ 2s và 3s của `task-27203.log`:**
  - **Trạng thái kiểm toán:** **NOT VERIFIED**
  - **Lý do:** Script `run_physical_usb_reconnect_interactive.py` chỉ lưu biến đếm số nguyên (`init_frames` và `rec_stream_frames`), không ghi mảng `(sequence_id, timestamp)` ra log. Tại thời điểm kiểm toán hiện tại (21:48), thiết bị Nikon D780 đang ở trạng thái `Status: Disconnected` trên Windows PnP nên không thể truy xuất lại trực tiếp từ phần cứng.
- **Đối với dữ liệu `sequence_id` và `timestamp` thực tế có trong raw log `task-27108.log` (cùng phiên đo Nikon D780 thật):**
  - **Trạng thái kiểm toán:** **VERIFIED**
  - Trích xuất trực tiếp từ [`task-27108.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27108.log#L56-L75) (dòng 56–75, nơi `FaceDetector` ghi nhận `seq=frame.sequence_id` thực tế từ `NikonCameraWorker` định kỳ mỗi ~1.5 giây):

| STT | Mốc thời gian Log | `sequence_id` (`seq`) | $\Delta\text{seq}$ giữa 2 mẫu | Khoảng thời gian $\Delta t$ | Tốc độ tăng `sequence_id` |
| :-: | :---: | :---: | :---: | :---: | :---: |
| 1 | `2026-11-05 15:16:54` | `2402` | — | — | — |
| 2 | `2026-11-05 15:16:56` | `2443` | `+41` | ~1.5s | ~27.3 FPS |
| 3 | `2026-11-05 15:16:57` | `2483` | `+40` | ~1.5s | ~26.7 FPS |
| 4 | `2026-11-05 15:16:59` | `2525` | `+42` | ~1.5s | ~28.0 FPS |
| 5 | `2026-11-05 15:17:00` | `2567` | `+42` | ~1.5s | ~28.0 FPS |
| 6 | `2026-11-05 15:17:02` | `2606` | `+39` | ~1.5s | ~26.0 FPS |
| 7 | `2026-11-05 15:17:03` | `2643` | `+37` | ~1.5s | ~24.7 FPS |
| 8 | `2026-11-05 15:17:05` | `2681` | `+38` | ~1.5s | ~25.3 FPS |
| 9 | `2026-11-05 15:17:06` | `2719` | `+38` | ~1.5s | ~25.3 FPS |
| 10 | `2026-11-05 15:17:08` | `2760` | `+41` | ~1.5s | ~27.3 FPS |
| 11 | `2026-11-05 15:17:09` | `2799` | `+39` | ~1.5s | ~26.0 FPS |
| 12 | `2026-11-05 15:17:11` | `2840` | `+41` | ~1.5s | ~27.3 FPS |
| 13 | `2026-11-05 15:17:12` | `2882` | `+42` | ~1.5s | ~28.0 FPS |
| 14 | `2026-11-05 15:17:14` | `2923` | `+41` | ~1.5s | ~27.3 FPS |
| 15 | `2026-11-05 15:17:15` | `2963` | `+40` | ~1.5s | ~26.7 FPS |
| 16 | `2026-11-05 15:17:17` | `3003` | `+40` | ~1.5s | ~26.7 FPS |
| 17 | `2026-11-05 15:17:18` | `3043` | `+40` | ~1.5s | ~26.7 FPS |
| 18 | `2026-11-05 15:17:20` | `3082` | `+39` | ~1.5s | ~26.0 FPS |
| 19 | `2026-11-05 15:17:22` | `3122` | `+40` | ~1.5s | ~26.7 FPS |
| 20 | `2026-11-05 15:17:23` | `3163` | `+41` | ~1.5s | ~27.3 FPS |

---

### A.4. Tính lại Unique Acquisition FPS
- **Trạng thái kiểm toán:** **VERIFIED** (dựa trên [`task-27108.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27108.log#L29-L43) và chuỗi `sequence_id` dòng 56–81):
  - **Trong 60.00s đo độc lập:** Nhận `1,595` unique `sequence_id` &rarr; **Unique Acquisition FPS = `26.58 FPS`**.
  - **Trong 30.00s AI OFF:** **Unique Acquisition FPS = `26.90 FPS`** (~807 unique frames).
  - **Trong 30.00s AI ON:** Từ `seq=2402` đến `seq=3163` ($\Delta = 761$ frames trong $28.85\text{s}$), toàn pha 30s đạt **Unique Acquisition FPS = `26.37 FPS`** (~791 unique frames).
  - **Quy đổi thực tế cho cửa sổ 2.0s và 3.0s của bài test Reconnect:**
    - Cửa sổ 2.0s ban đầu: số frame duy nhất thực tế chỉ khoảng **$2.0\text{s} \times 26.6\text{ FPS} \approx \mathbf{53\text{ unique frames}}$** (trong 191 lần đọc cache có ~138 lần đọc trùng frame cũ, tỷ lệ trùng ~72.2%).
    - Cửa sổ 3.0s sau reconnect: số frame duy nhất thực tế chỉ khoảng **$3.0\text{s} \times 26.6\text{ FPS} \approx \mathbf{80\text{ unique frames}}$** (trong 287 lần đọc cache có ~207 lần đọc trùng frame cũ, tỷ lệ trùng ~72.1%).

---

### A.5. Phân biệt rõ Acquisition FPS, Cache Read Rate, Signal Rate và Display FPS

| Chỉ số | Định nghĩa chính xác trong Codebase | Vị trí Code Production | Giá trị thực tế trên Nikon D780 | Phân loại |
| :--- | :--- | :--- | :---: | :---: |
| **1. Acquisition FPS** | Tốc độ `NikonCameraWorker._worker_loop` gọi `self._session.fetch_live_view_frame()` nhận được gói JPEG từ USB 3.0, giải mã `cv2.imdecode` sang RGB và tăng `self._frame_count` (`sequence_id`). | [`camera_worker.py:181-218`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/camera_worker.py#L181-L218) | **26.37 – 26.90 FPS** | **VERIFIED** |
| **2. Cache Read Rate** | Tần suất một vòng lặp bên ngoài gọi `CameraConnectionManager.get_frame_data()` để đọc biến `self._latest_frame` trong RAM. Phụ thuộc vào `time.sleep()` của người gọi, bao gồm cả các lần đọc lặp lại cùng một `sequence_id`. | [`connection_manager.py:498-503`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py#L498-L503) | **95.5 – 95.7 reads/s** *(với `sleep(0.01)`)*<br>**182.07 reads/s** *(với `sleep(0.005)`)* | **VERIFIED** |
| **3. Signal Rate** | Tần suất phát tín hiệu cập nhật sang UI thread:<br>• **KioskPage**: `CameraLiveViewWorker` phát `frame_ready.emit(frame_rgb)` sau khi đi qua cổng `_target_interval = 1/30s` và `_deadline_timer`.<br>• **CameraPage**: `self._timer` (`Qt.PreciseTimer`, interval `33ms`) bắn `timeout` gọi `_update_preview()`. | • [`kiosk_page.py:223-283`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L223-L283)<br>• [`camera_page.py:338-341`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py#L338-L341) | • KioskPage: $\le 30.0\text{ Hz}$<br>• CameraPage timer: $\approx 30.3\text{ Hz}$ | **VERIFIED** *(qua code)* |
| **4. Display FPS** | Tốc độ khung hình mới thực sự được đưa vào `CameraLiveViewport.set_frame_rgb()` và được Qt vẽ lên màn hình trong `paintEvent()`. | • [`camera_page.py:968-975`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py#L968-L975)<br>• [`live_viewport.py:116-135, 270`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/live_viewport.py#L116-L135) | • Benchmark Rigid Gate: **18.57 – 18.67 FPS** (**VERIFIED**)<br>• Production 26.0–27.5 FPS: **REPORTED** *(chưa có log chạy thực tế trên D780)* | **REPORTED** *(cho production)* |

---

## PHẦN B: XÁC MINH PHYSICAL USB RECONNECT

Đối chiếu từng bước với nhật ký gốc [`task-27203.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27203.log), kết quả lệnh hệ thống `pnputil`, và nhật ký Windows Event Viewer:

### B.1. PnP Disconnected có Hardware ID `USB\VID_04B0&PID_0446`
- **Trạng thái kiểm toán:** **VERIFIED**
- **Bằng chứng trực tiếp:**
  1. Kết quả chạy trực tiếp lệnh `pnputil /enum-devices /class WPD` khi rút cáp USB (ghi nhận tại `step_index: 27155` và `27391`):
     ```text
     Instance ID:                USB\VID_04B0&PID_0446\0000002008880
     Device Description:         D780
     Class Name:                 WPD
     Class GUID:                 {eec5ad98-8080-425f-922a-dabf3de3f69a}
     Manufacturer Name:          Nikon Corporation
     Status:                     Disconnected
     Driver Name:                wpdmtp.inf
     ```
  2. Nhật ký [`task-27203.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27203.log#L45-L55):
     - Dòng 45: `[PHÁT HIỆN] ĐÃ RÚT CÁP USB VẬT LÝ sau 197.7s! (PnP Disconnected)` (hàm `check_nikon_d780_pnp()` kiểm tra khối thiết bị `04B0.*0446` không còn ở trạng thái `Started`).
     - Dòng 55: `Nikon MAID thiết bị ngắt kết nối: Source ID 0x1` (log từ callback `_on_module_event` khi nhận sự kiện `NkMAIDEvent.REMOVE_CHILD` từ SDK).

---

### B.2. PnP Started sau khi cắm lại
- **Trạng thái kiểm toán:** **VERIFIED**
- **Bằng chứng trực tiếp:**
  1. Nhật ký [`task-27203.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27203.log#L57) (dòng 57):
     `[PHÁT HIỆN] ĐÃ CẮM LẠI CÁP USB sau 3.7s! (PnP Status: Started)`
  2. Kết quả chạy trực tiếp lệnh `pnputil /enum-devices /class WPD` ngay sau khi cắm lại cáp (ghi nhận tại `step_index: 27171` và `27240`):
     ```text
     Instance ID:                USB\VID_04B0&PID_0446\0000002008880
     Device Description:         D780
     Class Name:                 WPD
     Class GUID:                 {eec5ad98-8080-425f-922a-dabf3de3f69a}
     Manufacturer Name:          Nikon Corporation
     Status:                     Started
     Driver Name:                wpdmtp.inf
     ```

---

### B.3. MAID Session mới thực sự được khởi tạo, không tái sử dụng Session cũ
- **Trạng thái kiểm toán:** **VERIFIED (Khởi tạo instance `NikonD780Backend` và `NikonSession` mới, nhưng dùng chung Singleton DLL `Type0026.md3` trong cùng tiến trình)**
- **Bằng chứng trực tiếp:**
  - Tại [`connection_manager.py:404-405`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py#L404-L405), lệnh `mgr.switch_backend("nikon_maid")` tạo mới hoàn toàn `self._backend = NikonD780Backend()`, kéo theo `self._session = NikonSession()` mới và gọi `open_module()` + `open_camera()` cấp phát cấu trúc `NkMAIDObject` mới cho `_mod_obj` và `_src_obj`.
  - Nhật ký [`task-27203.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27203.log#L62-L67) (dòng 62–67):
    ```text
    [2026-11-05 16:30:24] [INFO] [VietPhotoBooth.camera.connection_manager.connection_manager]: Yêu cầu chuyển đổi Camera Backend sang: 'nikon_maid', thiết bị: '0'
    Mở lại session MAID Type0026: True (mất 2.82s)
    Trạng thái mgr.is_connected(): True
    ```
  - **Lưu ý kiến trúc:** Dù đối tượng Python `NikonSession` là mới, [`maid_loader.py:132-140`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/maid_loader.py#L132-L140) sử dụng biến toàn cục `_loader_instance` giữ nguyên handle `ctypes.CDLL("Type0026.md3")` đã nạp từ trước trong cùng tiến trình.

---

### B.4. EventProc và worker cũ đã được giải phóng
- **Trạng thái kiểm toán:** **FAILED (Phát hiện lỗi kiểm tra tên thuộc tính trong script test và lỗi không hủy đăng ký `EVENT_PROC` / crash heap `0xc0000005` trong cùng tiến trình)**
- **Bằng chứng trực tiếp:**
  1. **Lỗi đọc sai tên thuộc tính worker trong script kiểm thử:**
     - Trong [`run_physical_usb_reconnect_interactive.py:77`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/scratch/run_physical_usb_reconnect_interactive.py#L77), script gọi `getattr(backend, "_camera_worker", None)`, trong khi thuộc tính thực tế của [`NikonD780Backend`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/nikon_d780_backend.py#L116) là `self._worker`.
     - Hậu quả là trong [`task-27203.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27203.log#L19), ngay cả ở Giai đoạn 1 khi Live View đang chạy, log vẫn in `NikonMAID-Worker thread: None (Alive=False)` (dòng 19) và ở Giai đoạn 2 in `Worker alive: False` (dòng 49). Thực tế lúc vừa rút cáp ở Giai đoạn 2, `backend._worker` vẫn đang chạy ngầm và chỉ được gọi `self._worker.stop()` ở đầu Giai đoạn 4 khi gọi `mgr.disconnect()`.
  2. **Lỗi không hủy đăng ký `EVENT_PROC` và đóng đối tượng đã mất kết nối vật lý trong [`maid_session.py`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/maid_session.py#L160-L174):**
     - Trong `NikonSession.close_camera()` (dòng 299–312) và `close_module()` (dòng 160–174): code **không** gọi `NkMAIDCommand.CAP_SET` với `NkMAIDCapability.EVENT_PROC` = `NULL` trước khi đóng `_src_obj` và `_mod_obj`.
     - Khi cáp USB bị rút vật lý, `_on_module_event` nhận `NkMAIDEvent.REMOVE_CHILD` (dòng 69–72) nhưng không đặt `self._is_src_open = False`. Sau đó ở Giai đoạn 4, `close_camera()` vẫn gọi `NkMAIDCommand.CLOSE` lên `self._src_obj` đã bị ngắt kết nối vật lý.
     - Khi `mgr.switch_backend("nikon_maid")` ghi đè `self._backend = NikonD780Backend()`, đối tượng `NikonSession` cũ (cùng các ctypes callback `_mod_event_cb_func`, `_src_event_cb_func`) mất tham chiếu Python và có thể bị Garbage Collector thu hồi trong khi DLL `Type0026.md3` vẫn nằm trong bộ nhớ tiến trình.

---

### B.5. Live View sau reconnect nhận được frame có `sequence_id` mới
- **Trạng thái kiểm toán:** **NOT VERIFIED (về mặt log `sequence_id` trực tiếp trong `task-27203.log`) / VERIFIED gián tiếp qua cơ chế reset cache**
- **Bằng chứng trực tiếp:**
  - Trong `task-27203.log` (dòng 70): chỉ in `Số frame Live View nhận được sau khi cắm lại cáp: 287 frames (3.0s)` mà không in giá trị `fd.sequence_id`.
  - Tuy nhiên, theo mã nguồn [`connection_manager.py:383-385`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py#L383-L385), khi `switch_backend("nikon_maid")` chạy ở Giai đoạn 4:
    ```python
    with self._frame_lock:
        self._latest_frame = None
    self._last_frame_data = None
    ```
    Bộ đệm `_latest_frame` đã bị xóa về `None`. Để `mgr.get_frame_data()` trả về đối tượng có `has_rgb == True` ở Giai đoạn 5, bắt buộc `NikonCameraWorker` mới phải gọi thành công `fetch_live_view_frame()` từ camera sau khi cắm lại cáp, giải mã JPEG sang RGB và tạo `FrameData` mới với `sequence_id` bắt đầu đếm lại từ `1`. Dù vậy, vì log không in con số `sequence_id` cụ thể nên mục này được xếp loại **NOT VERIFIED** theo tiêu chuẩn nghiêm ngặt.

---

### B.6. Still Capture tạo ra ảnh mới sau reconnect, xác nhận EXIF và kích thước 6048×4024
- **Trạng thái kiểm toán:**
  - **Still Capture trong cùng tiến trình vừa rút/cắm cáp (`task-27203`):** **FAILED (Crash `0xc0000005` trong `ntdll.dll`)**
  - **Still Capture trong tiến trình mới sau khi cắm lại cáp (`test_nikon_maid_capture.py`):** **VERIFIED (Kích thước `6048 × 4024`, dung lượng `3,840,485 bytes`)**
  - **Xác nhận EXIF trên tệp JPEG đã lưu:** **FAILED (Mất EXIF do `PIL.Image.save` không truyền `exif=...`)**
- **Bằng chứng trực tiếp:**
  1. **Sự cố crash tiến trình `task-27203` ở Giai đoạn 6 (lúc `16:30:31`):**
     - Trong [`task-27203.log`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/.system_generated/tasks/task-27203.log#L72), dòng cuối cùng được in là:
       `[Giai đoạn 6] Chụp ảnh tĩnh Still Capture độ phân giải gốc 6048x4024...`
       Sau đó tiến trình `python.exe` thoát với mã lỗi `1` (thực chất là crash native).
     - Nhật ký **Windows Event Viewer (Application Error lúc `11/5/2026 4:30:31 PM`)** ghi nhận trực tiếp:
       ```text
       Faulting application name: python.exe, version: 3.12.10150.1013, time stamp: 0x67f515a7
       Faulting module name: ntdll.dll, version: 10.0.26100.9711, time stamp: 0x5fd39a05
       Exception code: 0xc0000005
       Fault offset: 0x000000000001a12d
       Faulting process id: 0x11648
       ```
     - **Nguyên nhân gốc rễ của crash `0xc0000005`:** Sau khi rút cáp vật lý và mở lại `NkMAIDObject` lần thứ 2 trên cùng một instance `Type0026.md3` trong cùng tiến trình (`PID 0x11648`), khi thực hiện `capture_photo()` (dừng Live View, chụp SDRAM, mở `ItemObject` và `DataObject`), vùng nhớ heap nội bộ của `Type0026.md3` / `ntdll.dll` bị xung đột với trạng thái phiên cũ chưa được giải phóng sạch khi rút cáp.
  2. **Ảnh chụp `physical_reconnect_verified_capture.jpg` được tạo từ tiến trình mới lúc `16:33:26`:**
     - Lúc `16:33:18` (2 phút 47 giây sau khi cắm lại cáp vật lý), script [`test_nikon_maid_capture.py`](file:///C:/Users/Admin/.gemini/antigravity/brain/676858c6-2a30-4e77-a479-d21f91264a09/scratch/test_nikon_maid_capture.py) chạy trong một tiến trình Python mới, kết nối vào Nikon D780, bật Live View và gọi `mgr.capture_photo(save_path=...)`:
       ```text
       capture_photo returned in 2.75s: <class 'tuple'> -> (True, <PIL.MpoImagePlugin.MpoImageFile image mode=RGB size=6048x4024 at 0x20257960530>)
       Saved file C:\Users\Admin\Documents\photobooth\tests_output\test_debug_capture.jpg: size=3840485 bytes, dim=(6048, 4024)
       ```
     - Tệp `test_debug_capture.jpg` sau đó được copy thành `physical_reconnect_verified_capture.jpg`.
  3. **Kiểm tra EXIF trên tệp `physical_reconnect_verified_capture.jpg`:**
     - Kết quả kiểm tra bằng `PIL.Image.open(...).getexif()`:
       ```text
       physical_reconnect_verified_capture.jpg size= 3840485 dim= (6048, 4024) fmt= JPEG exif_count= 0 Make= None Model= None
       ```
     - **Nguyên nhân mất EXIF:** Mặc dù dữ liệu gốc tải từ SDRAM của Nikon D780 trong `NikonSession.capture_photo()` là ảnh MPO/JPEG nguyên bản của máy ảnh (`<PIL.MpoImagePlugin.MpoImageFile image mode=RGB size=6048x4024>`), nhưng tại [`connection_manager.py:706`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py#L706), hàm `capture_photo()` lưu ảnh bằng lệnh:
       ```python
       img.save(save_path, "JPEG", quality=95)
       ```
       Khi `PIL.Image.save()` nén lại ảnh RGB sang tệp JPEG mới mà không truyền tham số `exif=img.info.get("exif")`, Pillow mặc định loại bỏ toàn bộ metadata EXIF gốc của máy ảnh.

---

## PHẦN C: XÁC MINH FPS PRODUCTION (ĐỌC TRỰC TIẾP CODE PATH PRODUCTION)

Không sử dụng số liệu từ các script benchmark độc lập. Dưới đây là kết quả kiểm toán trực tiếp trên các tệp mã nguồn production:
- [`vietphotobooth/camera/backends/nikon_maid/maid_session.py`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/maid_session.py)
- [`vietphotobooth/camera/backends/nikon_maid/camera_worker.py`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/camera_worker.py)
- [`vietphotobooth/camera/connection_manager.py`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py)
- [`vietphotobooth/desktop/widgets/kiosk_page.py`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py)
- [`vietphotobooth/desktop/widgets/camera_page.py`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py)
- [`vietphotobooth/desktop/widgets/live_viewport.py`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/live_viewport.py)

> [!WARNING]
> **Lưu ý kiểm toán quan trọng về báo cáo trước:** Trong phiên trước, script `scratch/trace_ui_display_pipeline.py` đã được gọi tại `step_index: 27150` nhưng **thoát ngay với mã lỗi 1** do lúc đó cáp USB đang rút (`[ERROR] Không thể kết nối Nikon D780 qua MAID!`). Do đó, các con số độ trễ chi tiết (`t_slot = 2.1–3.4ms`, `t_signal = 0.25–0.65ms`, `t_paint = 0.32–0.58ms`, `Production Display FPS = 26.0–27.5 FPS`) trong báo cáo trước là **REPORTED** (ước lượng lý thuyết), **KHÔNG PHẢI** số liệu đo trực tiếp từ lần chạy `trace_ui_display_pipeline.py`.

### C.1. Nguồn frame (Production Frame Source Chain) — **VERIFIED**
1. **`NikonSession.fetch_live_view_frame()`** ([`maid_session.py:575-663`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/maid_session.py#L575-L663)):
   - Gọi `CAP_GET` và `CAP_GET_ARRAY` (`NkMAIDCapability.GET_LIVE_VIEW_IMAGE`), chờ completion qua vòng lặp `ASYNC` (`time.sleep(0.001)`), cắt bỏ 512 bytes header điều khiển Nikon và trả về `bytes` JPEG (`1024 × 680`).
2. **`NikonCameraWorker._worker_loop()`** ([`camera_worker.py:169-233`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/camera_worker.py#L169-L233)):
   - Chạy trên luồng `NikonMAID-Worker`.
   - Mỗi lần `fetch_live_view_frame()` trả về `frame_bytes` khác rỗng:
     - Tăng `self._frame_count += 1`.
     - Giải mã `cv2.imdecode` + `cv2.cvtColor(..., COLOR_BGR2RGB)` ngay trên worker thread.
     - Tạo `FrameData(rgb=rgb, jpeg=frame_bytes, width=w, height=h, fps=self._current_fps, sequence_id=self._frame_count, timestamp=now, is_valid=True)`.
     - Ghi đè `self._latest_frame = frame` và bật `self._new_frame_event.set()`.
3. **`NikonD780Backend.read_frame()`** ([`nikon_d780_backend.py:262-266`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/nikon_d780_backend.py#L262-L266)):
   - Gọi `self._worker.get_latest_frame(wait_new=True, timeout=0.06)`.
4. **`CameraConnectionManager._stream_loop()`** ([`connection_manager.py:264-345`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py#L264-L345)):
   - Chạy trên luồng `CameraLiveViewStreamer`.
   - Gọi `self._backend.read_frame()`, cập nhật `self._read_fps_tracker.tick()`, lưu `self._latest_frame = frame`, và gọi `self._notify_frame(frame)` tới tất cả callback đã đăng ký.
   - Không có `time.sleep()` khi `self._current_backend_type == "nikon_maid"` (dòng 331–333).

---

### C.2. Cơ chế Deadline Timer — **VERIFIED**
Trong codebase production hiện tồn tại **2 kiến trúc điều phối hiển thị khác nhau** tùy theo màn hình:

1. **Tại `KioskPage` (`CameraLiveViewWorker` — [`kiosk_page.py:168-283`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L168-L283)):**
   - **CÓ sử dụng Deadline Timer.**
   - Khi `_on_direct_frame(frame_data)` được gọi từ `CameraConnectionManager._stream_loop()`, nó lưu `self._latest_rgb = frame_data.rgb` và phát `_push_signal.emit()` (`Qt.QueuedConnection`) sang UI thread slot `_deliver_coalesced_frame()`.
   - Tại `_deliver_coalesced_frame()` (dòng 223–246):
     - Tính `elapsed = time.perf_counter() - self._last_emit_time`.
     - Nếu `elapsed >= self._target_interval` (`1.0 / 30.0 = 33.333ms`): gọi ngay `self._do_emit(now)` để phát `self.frame_ready.emit(frame_rgb)`.
     - Nếu `elapsed < self._target_interval` (frame đến sớm): **không vứt bỏ frame** mà giữ trong `self._latest_rgb` và đặt hẹn giờ `self._deadline_timer.start(max(1, math.ceil((self._target_interval - elapsed) * 1000.0)))`. Khi hết hạn, `_on_deadline()` sẽ phát frame đó ra UI.
2. **Tại `CameraPage` ([`camera_page.py:338-341, 960-978`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py#L338-L341)):**
   - **KHÔNG sử dụng Deadline Timer hay `CameraLiveViewWorker`.**
   - Sử dụng một `QTimer` lặp định kỳ cố định mỗi `33ms` (`self._timer.setInterval(33)`) gọi `_update_preview()`, đọc `self.camera_mgr.get_frame_data()` từ bộ đệm O(1).

---

### C.3. `QTimer` và `Qt.PreciseTimer` — **VERIFIED**
1. **`KioskPage` (`CameraLiveViewWorker` — [`kiosk_page.py:196-199`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L196-L199)):**
   - Sử dụng `QTimer`单-shot với `Qt.PreciseTimer`:
     ```python
     self._deadline_timer = QTimer(self)
     self._deadline_timer.setTimerType(Qt.PreciseTimer)
     self._deadline_timer.setSingleShot(True)
     ```
2. **`CameraPage` ([`camera_page.py:338-341`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py#L338-L341)):**
   - Sử dụng `QTimer` lặp với `Qt.PreciseTimer`:
     ```python
     self._timer = QTimer(self)
     self._timer.setTimerType(Qt.PreciseTimer)
     self._timer.setInterval(33)
     ```
3. **`FullscreenLiveDialog` ([`camera_page.py:253-255`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py#L253-L255)):**
   - Sử dụng `self._timer = QTimer(self)` với `self._timer.start(33)` nhưng **chưa gọi `setTimerType(Qt.PreciseTimer)`** (mặc định là `Qt.CoarseTimer`).

---

### C.4. `update()` hay `repaint()` — **VERIFIED (Production dùng `update()`, KHÔNG dùng `repaint()`)**
- Tại [`live_viewport.py:116-135`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/live_viewport.py#L116-L135), hàm `CameraLiveViewport.set_frame_rgb(self, rgb_frame: np.ndarray)` kết thúc bằng:
  ```python
  self._current_frame_buffer = rgb_frame
  self._current_image = QImage(rgb_frame.data, w, h, 3 * w, QImage.Format_RGB888)
  self._current_pixmap = None
  self._message_text = ""
  self.update()
  ```
- Cả `KioskPage._on_live_view_frame()` ([`kiosk_page.py:1602`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L1602)) lẫn `CameraPage._update_preview()` ([`camera_page.py:975`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py#L975)) đều chỉ gọi `self.lbl_viewport.set_frame_rgb(...)`, tức là **100% sử dụng `self.update()`** (đặt sự kiện `QEvent::UpdateRequest` vào Qt Event Loop để Qt tự lập lịch gọi `paintEvent()`), **hoàn toàn không gọi `self.repaint()`**.
- **Đối soát sai lệch trong báo cáo trước:** Báo cáo trước viết rằng *"tỷ lệ drop/coalesced của Qt là 0% khi sử dụng `repaint()`"* — nhận định đó dựa trên các script benchmark (`verify_nikon_deep_audit.py` và `trace_ui_display_pipeline.py`) vốn tự gọi `viewport.repaint()`, không phản ánh đúng hành vi `self.update()` của code production.

---

### C.5. Điểm đo Display FPS — **VERIFIED**
1. **Trên `CameraPage` ([`camera_page.py:335, 974, 1044`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py#L968-L975)):**
   - Bộ đếm Display FPS là `self._render_fps_tracker = FPSTracker(window_seconds=1.5)`.
   - Điểm gọi `self._render_fps_tracker.tick()` nằm tại **dòng 974** bên trong hàm `_update_preview()`, ngay trước khi gọi `self.lbl_viewport.set_frame_rgb(rgb_frame)`.
   - **Nhận xét kỹ thuật:** Điểm đo này đo **tốc độ nạp frame mới vào Viewport (`set_frame_rgb`)**, chứ **không đặt bên trong `CameraLiveViewport.paintEvent()`**. Do `set_frame_rgb()` gọi `self.update()` (bất đồng bộ), nếu Qt gộp (coalesce) 2 lần `update()` liên tiếp trước khi kịp chạy `paintEvent()`, thì `_render_fps_tracker` vẫn đếm 2 lần nhưng `paintEvent()` chỉ chạy 1 lần.
2. **Trên `KioskPage` ([`kiosk_page.py:1584-1609`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L1584-L1609)):**
   - **Không có điểm đo Display FPS** trong `KioskPage` hoặc `CameraLiveViewport`.

---

### C.6. Có đếm frame mới theo `sequence_id` hay không — **VERIFIED (Có ở `CameraPage`, KHÔNG có ở `KioskPage`)**
1. **Trên `CameraPage._update_preview()` ([`camera_page.py:968-975`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/camera_page.py#L968-L975)):**
   - **CÓ kiểm tra và lọc theo `sequence_id`:**
     ```python
     seq_id = getattr(frame_data, "sequence_id", 0) if frame_data else 0
     if seq_id and seq_id == getattr(self, "_last_rendered_preview_seq", -1):
         # Frame này đã được vẽ rồi, không vẽ lại trùng lặp (Latest-Frame-Wins)
         return
     self._last_rendered_preview_seq = seq_id
     self._consecutive_no_frame_count = 0
     self._render_fps_tracker.tick()
     self.lbl_viewport.set_frame_rgb(rgb_frame)
     ```
   - Nhờ đoạn kiểm tra này, khi timer 33ms (30.3 Hz) chạy nhanh hơn tốc độ camera Nikon D780 (26.6 FPS), các lần timer rơi vào cùng một `sequence_id` cũ sẽ `return` sớm, không gọi ` _render_fps_tracker.tick()` và không gọi `set_frame_rgb()` trùng lặp.
2. **Trên `KioskPage` (`CameraLiveViewWorker` — [`kiosk_page.py:205-220, 1584-1607`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L205-L220)):**
   - **KHÔNG kiểm tra `sequence_id`:**
     - `_on_direct_frame(self, frame_data)` chỉ trích xuất `rgb = frame_data.rgb` mà không kiểm tra `frame_data.sequence_id` có trùng với frame vừa phát trước đó hay không.
     - Nếu `NikonCameraWorker` không tạo frame mới trong 60ms, `NikonD780Backend.read_frame()` (`wait_new=True, timeout=0.06`) hết timeout nhưng [`camera_worker.py:135-136`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/camera_worker.py#L135-L136) vẫn trả về `self._latest_frame` cũ, khiến `CameraConnectionManager._stream_loop()` gọi lại `_notify_frame(frame)` với cùng một frame cũ và `CameraLiveViewWorker` phát lại frame đó lên UI.
     - Ngoài ra, tại [`kiosk_page.py:1606`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L1606), lời gọi `self._face_service.submit_frame(frame_rgb, sequence_id=0, timestamp=time.time())` đang truyền cứng `sequence_id=0` thay vì `sequence_id` thực của frame.

---

## PHẦN D: BẢNG TỔNG HỢP PHÂN LOẠI & ĐỀ XUẤT KHẮC PHỤC

### D.1. Bảng tổng hợp trạng thái kiểm toán (Audit Classification Matrix)

| Hạng mục kiểm toán | Phân loại | Bằng chứng / Lý giải ngắn gọn |
| :--- | :---: | :--- |
| **A.1** Con số 191 (2s) và 287 (3s) là Cache Read hay Unique `sequence_id`? | **FAILED** *(Phương pháp đo)*<br>**VERIFIED** *(Bản chất)* | Script `run_physical_usb_reconnect_interactive.py` đếm số lần gọi `mgr.get_frame_data()` với `sleep(0.01)` (~95.6 Hz Cache Read Rate), không phải số frame duy nhất. |
| **A.2** Có kiểm tra `timestamp` và loại bỏ duplicate `sequence_id` trong bài test reconnect? | **FAILED** | Vòng lặp trong `run_physical_usb_reconnect_interactive.py` không đọc `fd.sequence_id` và không lọc trùng. |
| **A.3** Danh sách `sequence_id` & `timestamp` trong cửa sổ 2s/3s của `task-27203` | **NOT VERIFIED** | `task-27203.log` chỉ in tổng số lần đọc (191 và 287). Chuỗi `sequence_id` thực chỉ có trong `task-27108.log` (`seq=2402` &rarr; `3163`). |
| **A.4** Unique Acquisition FPS thực tế của Nikon D780 | **VERIFIED** | Đo từ `task-27108.log` (60s và 2×30s có lọc `sequence_id`): đạt **26.37 – 26.90 FPS** (~53 unique frames / 2s và ~80 unique frames / 3s). |
| **A.5** Phân biệt Acquisition FPS, Cache Read Rate, Signal Rate, Display FPS | **VERIFIED** | Đã bóc tách rõ ràng theo từng tầng mã nguồn và log thực nghiệm. |
| **B.1** PnP Disconnected có Hardware ID `USB\VID_04B0&PID_0446` | **VERIFIED** | Có output trực tiếp từ `pnputil /enum-devices /class WPD` (`Status: Disconnected`) và `task-27203.log` dòng 45, 55. |
| **B.2** PnP Started sau khi cắm lại cáp vật lý | **VERIFIED** | Có output trực tiếp từ `pnputil` (`Status: Started`) và `task-27203.log` dòng 57 (sau 3.7s). |
| **B.3** MAID Session mới thực sự được khởi tạo | **VERIFIED** | `switch_backend("nikon_maid")` khởi tạo instance `NikonD780Backend` và `NikonSession` mới (`task-27203.log` dòng 62–67, mất 2.82s). |
| **B.4** EventProc và worker cũ được giải phóng an toàn trong cùng tiến trình | **FAILED** | 1) Script test kiểm tra sai tên thuộc tính `_camera_worker` (đúng là `_worker`).<br>2) `close_camera()`/`close_module()` không hủy đăng ký `EVENT_PROC` và gọi `CLOSE` lên `_src_obj` đã rút cáp, gây lỗi heap. |
| **B.5** Live View sau reconnect nhận frame có `sequence_id` mới | **NOT VERIFIED** | Cache `_latest_frame` được xóa về `None` khi `switch_backend`, nên có frame mới sau reconnect, nhưng `task-27203.log` không in giá trị `sequence_id` ra log. |
| **B.6a** Still Capture sau reconnect trong **cùng tiến trình** (`task-27203`) | **FAILED** | Tiến trình `python.exe` (`PID 0x11648`) bị crash `Access Violation 0xc0000005` tại `ntdll.dll` ngay khi gọi `capture_photo()` ở Giai đoạn 6 (Windows Event Viewer `16:30:31`). |
| **B.6b** Still Capture sau reconnect trong **tiến trình mới** (`test_nikon_maid_capture.py`) | **VERIFIED** | Chụp thành công trong `2.75s`, tạo ảnh mới `6048 × 4024` pixels, dung lượng `3,840,485 bytes` (`16:33:26`). |
| **B.6c** Bảo toàn EXIF trên tệp ảnh Still Capture đã lưu | **FAILED** | `CameraConnectionManager.capture_photo()` gọi `img.save(save_path, "JPEG", quality=95)` không truyền `exif=img.info.get("exif")`, làm mất toàn bộ EXIF (`exif_count = 0`). |
| **C.1–C.6** Kiểm toán Code Path Production (`KioskPage`, `CameraPage`, `CameraLiveViewport`) | **VERIFIED** | Đã xác minh trực tiếp trên code: Production dùng `self.update()` (không dùng `repaint()`), `CameraPage` lọc `sequence_id` nhưng đo FPS trước `paintEvent()`, `KioskPage` dùng Deadline Timer nhưng không lọc `sequence_id`. |
| **C.7** Số liệu `Production Display FPS = 26.0–27.5 FPS` và latency `t_slot`/`t_signal`/`t_paint` trong báo cáo trước | **REPORTED** | Script `trace_ui_display_pipeline.py` bị lỗi kết nối lúc `16:14:15` (do cáp đang rút) và chưa được chạy lại khi cắm cáp; các con số trong báo cáo trước là ước lượng lý thuyết. |

---

### D.2. Nguyên nhân gốc rễ các điểm `FAILED` và Đề xuất cách sửa (Chưa áp dụng vào code)

Theo đúng chỉ đạo **không tự ý sửa code production trong vòng Audit này**, dưới đây là nguyên nhân và giải pháp kỹ thuật đề xuất cho từng vấn đề phát hiện được:

#### 1. Vấn đề 1: Crash `0xc0000005` (`ntdll.dll`) khi chụp Still Capture sau khi rút/cắm cáp USB trong cùng một tiến trình
- **Nguyên nhân:**
  1. Khi rút cáp USB vật lý, `NikonSession._on_module_event` nhận `NkMAIDEvent.REMOVE_CHILD` ([`maid_session.py:69-72`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/maid_session.py#L69-L72)) nhưng không đánh dấu `self._is_src_open = False`, khiến `NikonCameraWorker` và `close_camera()` tiếp tục gửi lệnh MAID (`ASYNC`, `STOP_LIVE_VIEW`, `CLOSE`) vào con trỏ `self._src_obj` đã bị hủy phía driver WPD.
  2. `close_camera()` và `close_module()` không đặt lại `NkMAIDCapability.EVENT_PROC` về `NULL` trước khi đóng, và khi `NikonD780Backend` cũ bị thay thế bởi instance mới trong `switch_backend()`, đối tượng `NikonSession` cũ cùng các ctypes callback (`_mod_event_cb_func`, `_src_event_cb_func`) có thể bị GC thu hồi hoặc làm hỏng cấu trúc nội bộ của `Type0026.md3`.
- **Đề xuất cách sửa:**
  - Trong `NikonSession._on_module_event`: Khi nhận `NkMAIDEvent.REMOVE_CHILD`, đặt ngay cờ `self._device_removed = True` và `self._is_src_open = False`, `self._is_live_view_active = False` để ngăn việc gọi `NkMAIDCommand.CLOSE` hoặc `CAP_SET` lên `_src_obj` đã ngắt kết nối vật lý.
  - Trước khi đóng module trong `close_module()`, hủy đăng ký `EVENT_PROC` bằng `NkMAIDCallback(pProc=0, refProc=0)`.
  - Tái sử dụng cùng một instance `NikonSession` (hoặc giữ tham chiếu callback sống suốt vòng đời tiến trình) và có cơ chế `FreeLibrary` / nạp lại `Type0026.md3` trong `NikonSDKLoader` nếu phát hiện kết nối vật lý bị ngắt đột ngột.

#### 2. Vấn đề 2: Mất dữ liệu EXIF khi lưu ảnh chụp trong `CameraConnectionManager.capture_photo()`
- **Nguyên nhân:**
  - Tại [`connection_manager.py:706`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/connection_manager.py#L706), `img.save(save_path, "JPEG", quality=95)` nén lại đối tượng `PIL.Image` mà không đính kèm khối bytes EXIF gốc (`img.info.get("exif")`).
- **Đề xuất cách sửa:**
  - Truyền thêm `exif_bytes = img.info.get("exif")`:
    ```python
    save_kwargs = {"quality": 95}
    if img.info.get("exif"):
        save_kwargs["exif"] = img.info["exif"]
    img.save(save_path, "JPEG", **save_kwargs)
    ```

#### 3. Vấn đề 3: `NikonCameraWorker.get_latest_frame(wait_new=True)` vẫn trả về frame cũ khi timeout và `KioskPage` không lọc `sequence_id`
- **Nguyên nhân:**
  - Tại [`camera_worker.py:130-136`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/camera/backends/nikon_maid/camera_worker.py#L130-L136), khi `self._new_frame_event.wait(timeout=timeout)` trả về `False` (timeout), hàm vẫn trả về `self._latest_frame` cũ.
  - Tại [`kiosk_page.py:205-220`](file:///C:/Users/Admin/Documents/photobooth/vietphotobooth/desktop/widgets/kiosk_page.py#L205-L220), `CameraLiveViewWorker._on_direct_frame()` không kiểm tra `frame_data.sequence_id != self._last_seq_id` và tại dòng 1606 truyền cứng `sequence_id=0` cho ` _face_service.submit_frame()`.
- **Đề xuất cách sửa:**
  - Trong `CameraConnectionManager._stream_loop()` và `CameraLiveViewWorker._on_direct_frame()`: lưu `self._last_seq_id` và chỉ phát `_notify_frame` / `_push_signal` khi `frame_data.sequence_id != self._last_seq_id`.
  - Truyền kèm `(frame_rgb, seq_id, timestamp)` qua signal `frame_ready` để `KioskPage` chuyển đúng `sequence_id` thực tế sang `_face_service.submit_frame()` và `CameraLiveViewport`.

#### 4. Vấn đề 4: Điểm đo Display FPS thực tế
- **Nguyên nhân:**
  - `CameraPage` đo `_render_fps_tracker.tick()` trước `set_frame_rgb()` (tức đếm số lần gọi `update()`), còn `KioskPage` chưa có bộ đếm Display FPS trong `paintEvent()`.
- **Đề xuất cách sửa:**
  - Bổ sung một `FPSTracker` trực tiếp bên trong `CameraLiveViewport.paintEvent()` (chỉ tick khi vẽ một frame có `sequence_id` mới) để đo chính xác 100% số frame thực sự được Qt vẽ ra màn hình trên cả `CameraPage` và `KioskPage`.
