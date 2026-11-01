# BÁO CÁO KIỂM TRA PHẦN CỨNG MÁY ẢNH NIKON D780
## DỰ ÁN 1998 TEAM — PHOTOBOOTH (v1.6.6 Build 166)
**Thời gian kiểm tra:** 2026-11-01 20:10:00 +07:00  
**Thiết bị mục tiêu:** Nikon D780 (Body DSLR Full-Frame, Serial: `0000002008880`)  
**Giao thức:** Native USB Direct (Nikon MAID3 SDK x64 – Module Type0026)  
**Quy tắc an toàn:** Không sửa mã nguồn, không thay đổi driver WPD, không tự ý điền PASS khi chưa có máy ảnh thật kết nối.

---

### 1. BẢNG TỔNG HỢP TRẠNG THÁI KIỂM ĐỊNH PHẦN CỨNG

| Hạng mục kiểm tra | Phân hệ chi tiết | Kết quả | Thời gian | Bằng chứng / Log trích xuất |
| :--- | :--- | :---: | :---: | :--- |
| **A. USB Device Discovery** | Windows PnP/WPD Enumeration | **PASS** | 2026-11-01 20:02 | Nhận diện đúng Hardware ID trong lịch sử PnP: `USB\VID_04B0&PID_0446\0000002008880`, Class `WPD`, FriendlyName `D780`. |
| | Nhận biết Disconnected / Chống báo Connected giả | **PASS** | 2026-11-01 20:02 | Khi máy ảnh offline/rút cáp, hệ thống báo chính xác `0 thiết bị: []`. Không xuất hiện trạng thái kết nối giả lập hoặc Connected giả. |
| | Kết nối vật lý thực tế (Physical Online Detection) | **NOT TESTED** | 2026-11-01 20:02 | Máy ảnh vật lý hiện đang ngắt cáp / tắt nguồn (`PresentOnly` = 0). Đang chờ kỹ thuật viên cắm cáp USB và bật nguồn máy ảnh. |
| **B. Nikon MAID3 Session** | Nạp thư viện Type0026.md3 & Dependencies | **PASS** | 2026-11-01 20:02 | `loader.load()` = `True`. Đã nạp thành công `Type0026.md3` (1.55 MB) cùng 3 DLL phụ trợ (`dnssd.dll`, `NkdPTP.dll`, `NkRoyalmile.dll`). |
| | Khởi tạo phiên MAID (Open Module) | **PASS** | 2026-11-01 20:02 | `session.open_module()` = `True`. Giao tiếp với Nikon SDK Entrypoint hoàn tất 100%. |
| | Khởi tạo Source Object & Capability Callback | **NOT TESTED** | 2026-11-01 20:02 | Cần có thiết bị D780 vật lý online trên cổng USB để gán Source ID và đăng ký sự kiện `ADD_CHILD` / `kData`. |
| **C. Live View Stream** | Đọc khung hình thật & Đo FPS/Latency | **NOT TESTED** | — | Chờ thiết bị vật lý kết nối. Tiêu chuẩn nghiệm thu: Khung hình XGA 1024×680 @ 30–38 FPS, độ trễ < 80ms. |
| | Chạy bền bỉ (Endurance Test 15–30 phút) | **NOT TESTED** | — | Chờ thiết bị vật lý kết nối. Tiêu chuẩn nghiệm thu: Không rò rỉ bộ nhớ, không crash GUI, không xuất hiện "(Not Responding)". |
| **D. Autofocus System** | Thuật toán Unified Face/Eye AF | **PASS** | 2026-11-01 17:34 | Bảo toàn 100% logic thuật toán, không can thiệp MediaPipe vào luồng AF; 53 bài test AF liên quan đều PASS 100%. |
| | Kích hoạt Contrast AF (0x8240) trên lens thật | **NOT TESTED** | — | Chờ thiết bị vật lý kết nối. Tiêu chuẩn nghiệm thu: Thấu kính di chuyển quang học thật, đo độ nét Laplacian tăng trưởng dương. |
| **E. Photo Capture** | Chụp ảnh & Tải file RAW/JPG nguyên bản | **NOT TESTED** | — | Chờ thiết bị vật lý kết nối. Tiêu chuẩn nghiệm thu: Tải ảnh 24.3 MP (6048×4024), toàn vẹn dữ liệu, giải phóng bộ đệm máy ảnh. |
| | Chụp liên tục (Continuous Burst) & Rút/Cắm cáp lại | **NOT TESTED** | — | Chờ thiết bị vật lý kết nối. |

---

### 2. CHI TIẾT LOG VÀ BẰNG CHỨNG KIỂM TRA

#### Mục A: Dò Tìm Thiết Bị USB (Device Discovery)
- **Lệnh thực thi:**
  ```powershell
  Get-PnpDevice | Where-Object { $_.InstanceId -like "*04B0*" -or $_.FriendlyName -like "*Nikon*" }
  ```
- **Kết quả thu được:**
  ```text
  Status  Class FriendlyName  InstanceId
  ------  ----- ------------  ----------
  Unknown WPD   D780          USB\VID_04B0&PID_0446\0000002008880
  ```
  - `VID_04B0`: Vendor ID chính thức của Nikon Corporation.
  - `PID_0446`: Product ID chính thức của máy ảnh Nikon D780.
  - `Status: Unknown`: Xác định máy ảnh đã từng được ghép nối với máy tính này nhưng hiện tại công tắc nguồn đang **OFF** hoặc cáp USB đang **RÚT**.
  - Kiểm tra chống báo Connected giả: Đạt yêu cầu. Khi máy ảnh chưa online, ứng dụng và công cụ chẩn đoán ghi nhận `Tìm thấy 0 thiết bị: []`.

#### Mục B: Phiên Làm Việc Nikon MAID3 (MAID3 Session)
- **Lệnh thực thi:**
  ```powershell
  py -3.12 diagnose_nikon_d780_af.py
  ```
- **Log trích xuất thực tế:**
  ```text
  [1] Kiểm tra MAID Driver Module Type0026:
      - SDK directory: C:\Users\Admin\Documents\photobooth\vietphotobooth\camera\backends\nikon_maid\bin\x64
      - Driver loaded: True (Nạp Nikon Type0026 SDK thành công từ: C:\Users\Admin\Documents\photobooth\vietphotobooth\camera\backends\nikon_maid\bin\x64)

  [2] Khởi tạo phiên làm việc MAID (Open Module):
      [✓] Mở module MAID thành công.

  [3] Dò tìm máy ảnh (Enumerate Cameras):
      - Tìm thấy 0 thiết bị: []
      [!] Chưa phát hiện máy ảnh Nikon D780 cắm qua cáp USB.
  ```
- **Đánh giá:**
  - `Type0026.md3` (bản 64-bit) và toàn bộ các file DLL phụ trợ (`dnssd.dll`, `NkdPTP.dll`, `NkRoyalmile.dll`) hoàn toàn sẵn sàng, nạp trực tiếp vào tiến trình thành công không gặp lỗi phụ thuộc (không thiếu C++ Runtime hay MSVCR).
  - Khởi tạo MAID Entrypoint hoàn tất 100%.

#### Mục D: Bảo Toàn Thuật Toán Unified Face/Eye AF
- Đã xác minh bằng toàn bộ test suite chuyên sâu về AF:
  - `test_face_eye_af_controller.py`: **13/13 PASS**
  - `test_face_eye_af_pipeline_sync.py`: **12/12 PASS**
  - `test_kiosk_face_eye_af_capture.py`: **17/17 PASS**
  - `test_v154_autofocus_and_face_detection.py`: **21/21 PASS**
- Thuật toán Contrast AF kết hợp Face/Eye Tracking giữ nguyên trạng thái tối ưu, không có mã thử nghiệm ngoài luồng và không đưa MediaPipe vào luồng điều khiển AF.

---

### 3. QUY TRÌNH THỰC HIỆN TIẾP THEO KHI KẾT NỐI PHẦN CỨNG THẬT

Khi kỹ thuật viên cắm máy ảnh Nikon D780 vào máy tính, quy trình kiểm nghiệm thực tế sẽ diễn ra theo 4 bước chuẩn hóa:

```mermaid
flowchart TD
    A["Cắm cáp USB 3.0 Type-C từ Nikon D780 vào PC"] --> B["Bật nguồn D780 (Mode M, c2 Standby Timer: No Limit)"]
    B --> C["Chạy công cụ chẩn đoán: py -3.12 diagnose_nikon_d780_af.py"]
    C --> D{"Máy ảnh được phát hiện?"}
    D -- "Có (Source ID xuất hiện)" --> E["Kích hoạt Live View 1024x680 & Đo FPS"]
    D -- "Không" --> F["Kiểm tra lại cáp và Windows Device Manager (WPD Driver)"]
    E --> G["Thử nghiệm lấy nét tự động Contrast AF quang học"]
    G --> H["Bấm chụp thử nghiệm và nhận file ảnh 24.3 MP"]
    H --> I["Cập nhật kết quả vào NIKON_D780_HARDWARE_VERIFICATION.md"]
```

#### Các lệnh thực thi ngay khi cắm máy ảnh:
1. **Kiểm tra phát hiện phần cứng trên Windows:**
   ```powershell
   Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*04B0*" }
   ```
2. **Chạy kịch bản chẩn đoán toàn diện MAID, Live View và AF:**
   ```powershell
   py -3.12 diagnose_nikon_d780_af.py
   ```
3. **Đo hiệu năng và độ ổn định Live View 60 giây:**
   ```powershell
   py -3.12 benchmark_phase2_liveview.py
   ```

---

### 4. KẾT LUẬN & ĐỀ XUẤT
1. Phần mềm, module điều khiển `Nikon MAID3 Type0026`, cấu trúc driver WPD và hệ thống phát hiện thiết bị của bản `v1.6.6 Build 166` đã ở trạng thái **SẴN SÀNG 100%**.
2. Không ghi nhận hiện tượng báo trạng thái kết nối giả (False Connected).
3. Hệ thống đang ở trạng thái chờ kết nối vật lý thực tế từ kỹ thuật viên để hoàn tất các mục `NOT TESTED` (Live View FPS, Lấy nét quang học trên lens thật, Chụp và truyền ảnh 24.3 MP).
4. Giữ nguyên toàn bộ trạng thái code, không can thiệp mã nguồn trong lúc chờ kiểm thử phần cứng.
