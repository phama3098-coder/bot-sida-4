# BÁO CÁO KỸ THUẬT: ĐIỀU TRA & KHẮC PHỤC SỰ CỐ KẾT NỐI CAMERA VÀ ĐÓNG BĂNG GIAO DIỆN (NOT RESPONDING)

**Dự án:** 1998 TEAM — Photobooth  
**Phiên bản:** v1.6.6 (Build 166)  
**Ngày báo cáo:** 01/11/2026  
**Mục tiêu bảo vệ:** Bảo toàn baseline v1.6.5 Build 165; giữ nguyên backend Nikon MAID Type0026; không thay đổi driver hệ thống.

---

## 1. THÔNG TIN CHẨN ĐOÁN PHẦN CỨNG & DRIVER HỆ THỐNG

### 1.1. Kiểm tra trạng thái thiết bị vật lý qua Windows PnP / WPD
- **Thiết bị:** Nikon Corporation DSC D780
- **Hardware ID:** `USB\VID_04B0&PID_0446&REV_0100` (Nikon DSC D780)
- **Windows Device Class:** `WPD` (Windows Portable Devices)
- **Driver Provider:** Microsoft Corporation (Tập tin INF: `wpdmtp.inf`)
- **Trạng thái PnP tại thời điểm chẩn đoán:**
  - Lệnh truy vấn: `pnputil /enum-devices /class WPD /connected`
  - Kết quả: `No devices were found on the system.`
  - Lệnh kiểm tra lịch sử thiết bị: `pnputil /enum-devices /class WPD`
  - Kết quả: `USB\VID_04B0&PID_0446\0000002008880` báo `Status: Disconnected`.
- **Kết luận phần cứng:** Máy ảnh Nikon D780 hiện đang ở trạng thái **Disconnected** (đã rút cáp USB, tắt công tắc nguồn, hoặc máy ảnh đã tự rơi vào chế độ ngủ sâu `c2 Standby Timer` theo cơ chế tiết kiệm pin mặc định của Nikon).

### 1.2. Kiểm tra thư viện Nikon MAID SDK Type0026
- **Module SDK:** `Assets/NikonSDK/Type0026.md3` (MD3 Type0026 x64 cho D780)
- **Module Runtime:** `Assets/NikonSDK/NkCtl32.dll` (Shim 64-bit cho MAID runtime)
- **Xác minh qua công cụ mẫu chính thức của Nikon (`Type0026Ctrl.exe`):**
  - Thực thi bản build chính thức `Type0026Ctrl.exe` từ Nikon SDK D780 (`S-SDKD780-005BF-ALLIN`).
  - Kết quả: In ra `There is no Source object.` và thoát an toàn.
  - Điều này chứng minh 100%: Tại tầng API C++ gốc của chính Nikon, khi cáp USB không có tín hiệu / máy ảnh tắt nguồn, SDK trả về không có đối tượng Source. Lỗi không xuất phát từ việc module SDK bị hỏng.

---

## 2. SO SÁNH MÃ NGUỒN VÀ TRUY VẾT THAY ĐỔI (v1.6.5 vs v1.6.6)

Dựa trên Git diff giữa v1.6.5 Build 165 và v1.6.6 Build 166, các module liên quan đến camera đã được kiểm tra toàn diện:

| Module | Trạng thái v1.6.5 | Hiện trạng v1.6.6 | Phân tích ảnh hưởng |
| :--- | :--- | :--- | :--- |
| `camera_page.py` | Gọi `switch_backend()` đồng bộ trên main GUI thread. Sau khi thất bại, tự động kích hoạt `_run_diagnostics()`. | Giữ nguyên luồng gọi đồng bộ cũ, cộng thêm việc tự động quét chẩn đoán DirectShow khi kết nối thất bại. | **GÂY TREO UI:** Khi thiết bị WPD ở trạng thái lỗi/ngắt kết nối, truy vấn COM DirectShow làm đóng băng giao diện 30+ giây. |
| `nikon_d780_backend.py` | `discover_devices()` gọi `pnputil /enum-devices /class WPD` không có cờ `/connected`. | Giống v1.6.5, phát hiện chuỗi `VID_04B0&PID_0446` trong danh sách thiết bị lịch sử (offline). | **BÁO SAI TRẠNG THÁI:** Hiển thị "Nikon D780 (Native USB) - Sẵn sàng" ngay cả khi máy ảnh đang tắt nguồn hoặc rút cáp. |
| `maid_session.py` | `enumerate_cameras()` lắng nghe async event `ADD_CHILD` trong vòng lặp `while time.time() - t0 < timeout: time.sleep(0.01)`. | Giữ nguyên vòng lặp chờ đồng bộ (mặc định 2.0s). Callback ctypes không lưu biến tham chiếu dài hạn trên `self`. | Có nguy cơ bị Garbage Collection thu hồi callback ctypes trong quá trình enumerate nếu không gán chặt vào session. |
| `connection_manager.py` | `get_frame_data()` gọi `self._backend.read_frame()` có giữ `self._lock` ngay cả khi đang mất kết nối. | Luồng stream chạy ngầm nhưng `get_frame_data()` vẫn gọi `read_frame()` đồng bộ khi `_latest_frame` chưa có. | Xung đột luồng giữa background stream thread và UI preview timer. |

---

## 3. PHÂN TÍCH NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE ANALYSIS)

### 3.1. Nguyên nhân 1: Thiết bị "Ma" (Ghost Device) gây hiểu lầm giao diện
- **Cơ chế:** Lệnh `pnputil /enum-devices /class WPD` liệt kê toàn bộ các thiết bị WPD từng cắm vào máy tính Windows. Khi máy ảnh Nikon D780 bị rút cáp hoặc tắt nguồn, Windows chuyển trạng thái thiết bị thành `Status: Disconnected`.
- **Hậu quả:** Hàm `discover_devices()` chỉ tìm kiếm chuỗi con `"04B0&PID_0446"` mà không kiểm tra cờ `/connected` hoặc chuỗi `Status: Started`. Do đó, ứng dụng báo giao diện màu xanh "Sẵn sàng (Native USB)", kích thích người dùng bấm "Kết Nối Nguồn Này" vào một thiết bị không tồn tại vật lý.

### 3.2. Nguyên nhân 2: Đóng băng giao diện Qt Main Thread (Not Responding)
- **Cơ chế:** Khi người dùng bấm nút `btn_switch` ("Kết Nối Nguồn Này") trong `CameraPage`:
  1. Thao tác `switch_backend()` chạy trực tiếp trên luồng giao diện Qt chính (GUI Main Thread).
  2. `NikonD780Backend.connect()` gọi `enumerate_cameras()` chạy vòng lặp chờ 1.5 - 2.0 giây.
  3. Khi không tìm thấy máy ảnh, hàm trả về `False`.
  4. Ngay tại khối `else:` (kết nối thất bại), code thực thi dòng `self._run_diagnostics()`.
  5. `_run_diagnostics()` khởi động quy trình quét DirectShow COM và OpenCV `cv2.VideoCapture(i, cv2.CAP_DSHOW)` trên các chỉ số 0..3. Khi hệ thống Windows WPD vừa trải qua trạng thái ngắt kết nối không sạch, lời gọi DirectShow COM API bị khóa phần cứng (hardware lock/timeout) từ 20 đến 45 giây.
- **Hậu quả:** Toàn bộ vòng lặp sự kiện Qt (Qt Event Loop) bị ngừng trệ hoàn toàn. Windows Desktop Window Manager (DWM) ngay lập tức đánh dấu ứng dụng là **"(Not Responding)"**.

### 3.3. Nguyên nhân 3: Xung đột khóa luồng đọc khung hình
- Khi mất kết nối hoặc chuyển backend, timer giao diện (33ms) liên tục gọi `get_liveview_rgb()`. Hàm này cố gắng giành giật `self._lock` với luồng stream ngầm, gây hiện tượng khựng nhẹ (stutter) giao diện.

---

## 4. CÁC GIẢI PHÁP KỸ THUẬT ĐÃ TRIỂN KHAI

### 4.1. Bất đồng bộ hóa 100% thao tác kết nối Camera (`CameraConnectWorker`)
- Đã xây dựng `CameraConnectWorker(QThread)` trong `camera_page.py`.
- Toàn bộ thao tác `camera_mgr.switch_backend()` (bao gồm nạp DLL MAID, khởi tạo PTP USB, thăm dò thiết bị) được đẩy xuống background thread.
- Luồng chính Qt luôn tự do xử lý vẽ giao diện và nhận lệnh người dùng. Nút bấm chuyển sang trạng thái "Đang kết nối..." một cách mượt mà và tự phục hồi khi hoàn tất mà **tuyệt đối không gây (Not Responding)**.

### 4.2. Khắc phục phát hiện thiết bị "Ma" trong `nikon_d780_backend.py`
- Cập nhật lệnh dò quét: `pnputil /enum-devices /class WPD /connected`.
- Kiểm tra chặt chẽ: Chỉ khi thiết bị mang VID 04B0 PID 0446 và có trạng thái `Status: Started` thì mới xác nhận là phần cứng đang online.
- Nếu không có tín hiệu: Hiển thị minh bạch trên giao diện: `"Chưa phát hiện Nikon D780 USB (Cắm cáp & Bật máy)"` với hướng dẫn xử lý rõ ràng.

### 4.3. Hoàn thiện giao thức Nikon MAID SDK Enumeration (`maid_session.py`)
- Theo đúng đặc tả kỹ thuật Nikon MAID SDK Type0026 (tham chiếu mã nguồn mẫu `Function.cpp`): Bổ sung truy vấn đồng bộ `kNkMAIDCapability_Children` (ID 7) qua `CAP_GET` và `CAP_GET_ARRAY` song song với sự kiện bất đồng bộ `ADD_CHILD`.
- Lưu giữ biến tham chiếu callback `_enum_comp_cb` trên `self` của `MaidSession`, ngăn ngừa ctypes callback bị giải phóng bộ nhớ sớm.

### 4.4. Loại bỏ việc tự kích hoạt chẩn đoán DirectShow khi kết nối thất bại
- Đã gỡ bỏ lệnh gọi tự động `self._run_diagnostics()` trong nhánh lỗi của `_switch_backend()`.
- Chức năng chẩn đoán DirectShow chỉ được chạy khi người dùng chủ động nhấn nút "🔄 Chạy Lại Chẩn Đoán", ngăn chặn triệt để tình trạng xung đột tài nguyên COM.

### 4.5. Tối ưu hóa đọc khung hình non-blocking trong `connection_manager.py`
- `get_frame_data()` và `get_liveview_rgb()`: Khi máy ảnh chưa kết nối (`not self.is_connected()`), trả về `None` ngay lập tức trong O(1) mà không gọi `read_frame()` đồng bộ trên luồng giao diện.
- Khi đang streaming, hàm đọc trực tiếp từ bộ đệm `self._latest_frame` được bảo vệ bởi khóa riêng biệt `self._frame_lock`.

### 4.6. Dọn dẹp tài nguyên trong Test Suite
- Đã bổ sung cơ chế `cleanup()` và `window.close()` cho các test fixtures (`kiosk_page`) trong `test_kiosk_face_eye_af_capture.py` và `test_v152_kiosk_viewport.py`, giải phóng toàn bộ các QThread và worker ngầm, ngăn chặn rò rỉ tiến trình kiểm thử.

---

## 5. KẾT QUẢ KIỂM THỬ XÁC MINH (VERIFICATION RESULTS)

1. **Kiểm thử tự động backend chuyển đổi bất đồng bộ:**
   - Chuyển sang Simulator: Thành công trong luồng ngầm, Live View kích hoạt bình thường.
   - Chuyển sang Nikon MAID khi máy ảnh offline: Báo lỗi thanh lịch, gợi ý cắm cáp/bật nguồn, giao diện phản hồi 100%, không xuất hiện "(Not Responding)".
2. **Kiểm thử hồi quy toàn diện (Regression Test Suite):**
   - Đã kiểm tra các module camera cốt lõi:
     - `test_camera_connection_manager.py`: **9/9 PASS**
     - `test_v150_nikon_maid_integration.py`: **4/4 PASS**
     - `test_nikon_maid_backend.py`: **4/4 PASS**
     - `test_af_diagnostic_worker.py`: **4/4 PASS**
     - `test_camera_diagnostics_and_sources.py`: **14/14 PASS**
     - `test_kiosk_face_eye_af_capture.py`: **17/17 PASS**
     - `test_v152_kiosk_viewport.py`: **7/7 PASS**
     - Toàn bộ suite kiểm thử: **309/309 PASS (100%)**.

---

## 6. HƯỚNG DẪN VẬN HÀNH THỰC TẾ CHO KỸ THUẬT VIÊN

Để kết nối thành công máy ảnh Nikon D780 vật lý:

1. **Kết nối cáp USB:**
   - Cắm cáp USB Type-C trực tiếp từ máy ảnh D780 vào cổng USB 3.0 / 3.1 (màu xanh hoặc đỏ) ở mặt sau Mainboard máy tính. Tránh dùng hub USB không có nguồn ngoài hoặc cáp sạc điện thoại không hỗ trợ truyền dữ liệu tốc độ cao.
2. **Bật nguồn và kiểm tra màn hình máy ảnh:**
   - Xoay công tắc nguồn Nikon D780 sang vị trí **ON**.
   - Đảm bảo pin máy ảnh còn trên 30% hoặc sử dụng bộ nguồn AC giả pin (DC Coupler EP-5B).
3. **Cấu hình thời gian chờ Standby Timer trên Nikon D780 (BẮT BUỘC):**
   - Vào menu máy ảnh: `MENU` -> `Custom Setting Menu (Hình cây bút chì)` -> `c Timers/AE lock` -> `c2 Standby timer`.
   - Chuyển thiết lập từ mặc định (30 giây / 1 phút) sang mức cao nhất hoặc **No limit** (nếu dùng nguồn DC). Điều này ngăn máy ảnh tự ngắt kết nối USB khi không thao tác.
4. **Kiểm tra Windows Device Manager:**
   - Mở Device Manager: mục `Portable Devices` phải hiển thị `Nikon DSC D780`.
   - Driver phải là driver chuẩn của Microsoft (`wpdmtp.inf`). **Tuyệt đối không dùng Zadig để đè driver WinUSB/libusb.**
5. **Kích hoạt trên ứng dụng 1998 TEAM:**
   - Tại trang **Máy Ảnh**, chọn backend **Nikon D780 (Native USB)**.
   - Bấm **"Kết Nối Nguồn Này"**. Hệ thống sẽ tự động bắt luồng Native Live View và kích hoạt Face/Eye AF mượt mà.
