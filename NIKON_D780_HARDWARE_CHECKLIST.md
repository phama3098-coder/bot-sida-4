# 1998 TEAM PHOTOBOOTH — CHECKLIST KIỂM THỬ MÁY ẢNH NIKON D780 VẬT LÝ

**Phiên bản kiểm thử:** v1.6.6 Build 166  
**Thiết bị mục tiêu:** Nikon D780 (Body DSLR Full-Frame)  
**Mục đích:** Hướng dẫn kỹ thuật viên kiểm thử thực địa từng bước, thu thập log chuyên sâu cho 4 phân hệ (Discovery, Session, Live View, Capture) và loại trừ 100% lỗi môi trường.

---

## PHẦN 1: CHUẨN BỊ VẬT LÝ & THIẾT LẬP MÁY ẢNH (CAMERA PRE-FLIGHT)

| STT | Hạng mục | Hướng dẫn thao tác | Tiêu chí đạt (PASS) | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | **Nguồn điện** | Sử dụng pin EN-EL15b/c trên 60% HOẶC cắm nguồn AC giả pin (DC Coupler EP-5B + EH-5d). | Đèn báo pin trên màn hình phụ máy ảnh hiển thị đầy vạch. | Tránh sập nguồn trong quá trình tethering USB. |
| **1.2** | **Cáp kết nối USB** | Cáp USB-C sang USB-A (hoặc USB-C to USB-C) chuẩn USB 3.0 / 3.1 tốc độ 5Gbps. Cắm trực tiếp cổng USB sau Mainboard máy tính. | Không cắm qua Hub thụ động, không cắm cổng USB 2.0 mặt trước case. | Cáp sạc điện thoại thường chỉ có 480Mbps hoặc thiếu dây data. |
| **1.3** | **Công tắc nguồn** | Xoay công tắc sang vị trí **ON**. | Màn hình phụ LCD trên đỉnh máy sáng số kiểu chụp. | |
| **1.4** | **Nút gạt Chụp/Live View** | Gạt cần chọn sang chế độ **Chụp ảnh tĩnh** (Biểu tượng Máy ảnh, KHÔNG gạt sang Máy quay phim). | Cần gạt đúng vị trí máy ảnh. | Tránh xung đột chế độ Movie Mode của Nikon SDK. |
| **1.5** | **Vòng xoay chế độ (Mode Dial)** | Đặt sang chế độ **M** (Manual). Thiết lập: Khẩu độ f/5.6 - f/8.0, Tốc độ 1/160s, ISO 400 - 800. | Máy ảnh ở Manual Mode. | Giữ đồng nhất ánh sáng studio. |
| **1.6** | **Standby Timer (BẮT BUỘC)** | Nhấn `MENU` -> `Custom Setting Menu (Hình cây bút chì)` -> `c Timers/AE lock` -> `c2 Standby timer` -> Chọn **No limit** (hoặc 30 phút). | Máy ảnh không tự tắt màn hình sau 30 giây. | **QUAN TRỌNG:** Đây là nguyên nhân khiến camera tự ngắt USB (Status: Disconnected). |
| **1.7** | **Thẻ nhớ SD** | Cắm ít nhất 1 thẻ SD có định dạng sạch (Slot 1). | Máy ảnh không báo `[-E-]` (thiếu thẻ nhớ). | Nikon D780 cần thẻ nhớ để bộ đệm màn trập giải phóng an toàn. |

---

## PHẦN 2: KIỂM TRA HỆ ĐIỀU HÀNH WINDOWS & DRIVER

Mở PowerShell với quyền Administrator và chạy các lệnh kiểm tra sau:

### 2.1. Kiểm tra trạng thái thiết bị PnP USB:
```powershell
pnputil /enum-devices /class WPD /connected
```
- **Kết quả đạt:** Xuất hiện `Instance ID: USB\VID_04B0&PID_0446\...` kèm `Status: Started`.
- **Nếu báo `No devices were found`:** Kiểm tra lại cáp, cổng USB, hoặc công tắc nguồn máy ảnh.

### 2.2. Kiểm tra Driver Provider:
- Mở **Device Manager** -> Tìm mục **Portable Devices** (Thiết bị di động).
- Nhấp đúp vào **Nikon DSC D780** -> Tab **Driver**.
- **Tiêu chuẩn:** Driver Provider phải là `Microsoft`, Driver File là `wpdmtp.inf` / `wpdmtp.dll`.
- **CẢNH BÁO:** Nếu thấy libusb, WinUSB, hoặc Zadig driver, phải nhấn *Uninstall Device* và tích chọn *Delete driver* để Windows phục hồi về driver WPD gốc.

---

## PHẦN 3: QUY TRÌNH KIỂM THỬ ỨNG DỤNG (THE 4-PILLAR TEST)

Chạy ứng dụng:
```powershell
py -3.12 -m vietphotobooth.main
```

### Trụ Cột 1: Dò Quét Thiết Bị (Device Discovery)
1. Chuyển sang Tab **Máy Ảnh**.
2. Khi máy ảnh **TẮT NGUỒN hoặc RÚT CÁP**:
   - [ ] Dropdown hiển thị: `"Chưa phát hiện Nikon D780 USB (Cắm cáp & Bật máy)"`.
   - [ ] Thanh trạng thái báo: `🔴 Chưa Kết Nối (Không có tín hiệu)`.
   - [ ] Bảng tính năng ghi nhận: `Trạng thái: Lỗi kết nối / Không khả dụng`.
   - [ ] **TUYỆT ĐỐI KHÔNG** báo `Sẵn sàng` hoặc `Đã kết nối` giả.
3. Bật công tắc máy ảnh sang **ON** và nhấn nút **Làm Mới**:
   - [ ] Dropdown cập nhật: `"Nikon D780 (Native USB) [Direct USB]"`.
   - [ ] Không xuất hiện hộp thoại lỗi.

### Trụ Cột 2: Khởi Tạo MAID Session (MAID Session Initialization)
1. Tại Tab **Máy Ảnh**, chọn backend **Nikon D780 (Native USB)**.
2. Bấm nút **"Kết Nối Nguồn Này"**:
   - [ ] Nút bấm chuyển sang `Đang kết nối...` và vô hiệu hóa tạm thời.
   - [ ] **Giao diện phản hồi 100%:** Có thể di chuyển chuột, không có nhãn "(Not Responding)" từ Windows.
   - [ ] Hộp thoại thông báo thành công xuất hiện:
     - `Trình điều khiển: NIKON_MAID`
     - `Giao tiếp: Native USB Direct (Nikon MAID3 SDK)`
     - `Độ phân giải chụp: 6048 × 4024 (24.3 MP)`
     - `Live View: Native USB Stream (1024×680 ~38 FPS)`
   - [ ] Thanh trạng thái chuyển sang: `🟢 Đã Kết Nối: Nikon D780 (Native USB)`.

### Trụ Cột 3: Phát Trực Tiếp Khung Hình (Live View Streaming)
1. Quan sát Viewport xem trước tại Tab **Máy Ảnh**:
   - [ ] Hình ảnh từ ống kính Nikon D780 xuất hiện rõ nét, màu sắc chuẩn RGB.
   - [ ] Khung hình ổn định ở tốc độ 30 - 38 FPS (không xé hình, không nhấp nháy đen).
   - [ ] Tỷ lệ hiển thị (Aspect Ratio) đúng khung hình 3:2, không bị méo/bẹp.
2. Bật tính năng **"👁 Nhận Diện: BẬT"** và **"🎯 Face/Eye AF: BẬT"**:
   - [ ] Đứng trước ống kính: Xuất hiện khung chữ nhật vàng/xanh bám theo khuôn mặt.
   - [ ] Xuất hiện tâm ngắm tròn màu lục bám sát vào con mắt gần ống kính nhất.
   - [ ] Không có hiện tượng giật hình hoặc drop FPS xuống dưới 20.
3. Chuyển sang Tab **Chụp Ảnh (Kiosk Page)**:
   - [ ] Luồng Live View từ D780 chuyển tiếp mượt mà sang giao diện Kiosk.
   - [ ] **TUYỆT ĐỐI ZERO OVERLAY:** Không hiển thị bất kỳ khung vuông, viền xanh hay tâm ngắm nào trên màn hình Kiosk (đúng tiêu chuẩn Photobooth cao cấp).

### Trụ Cột 4: Lấy Nét & Chụp Ảnh Thật (Autofocus & Photo Capture)
1. Nhấn nút **"📸 Chụp Thử Nghiệm"** trên Tab **Máy Ảnh**:
   - [ ] Nút bấm chuyển sang `📸 Đang Chụp...`.
   - [ ] Nghe thấy tiếng mô-tơ lấy nét lens xoay và tiếng màn trập cơ khí của D780 kêu `Tách`.
   - [ ] Ảnh JPEG 24.3 MP (6048 × 4024) được tải an toàn về đĩa tạm.
   - [ ] Hộp thoại xác nhận hiển thị dung lượng file thực tế (khoảng 6 - 12 MB).
2. Chuyển sang Tab **Chụp Ảnh (Kiosk Page)** và bấm **"BẮT ĐẦU CHỤP"**:
   - [ ] Đếm ngược 3... 2... 1... kèm âm thanh studio.
   - [ ] Trước khoảnh khắc chụp 0.5s: Hệ thống Face/Eye AF ngầm khóa nét vào mắt khách chụp.
   - [ ] Máy ảnh chớp chụp, ảnh hiển thị sắc nét vào vị trí khung trên trang Review.

---

## PHẦN 4: HƯỚNG DẪN TRÍCH XUẤT & PHÂN TÍCH NHẬT KÝ (LOG ISOLATION)

Toàn bộ nhật ký được tự động ghi vào tệp:
`%LOCALAPPDATA%\1998TeamPhotobooth\Logs\1998team_photobooth.log`

### Lệnh lọc log chuyên biệt cho từng phân hệ qua PowerShell:

#### 1. Log Device Discovery:
```powershell
Get-Content "$env:LOCALAPPDATA\1998TeamPhotobooth\Logs\1998team_photobooth.log" | Select-String "discover_devices", "pnputil", "NikonD780Backend"
```

#### 2. Log MAID Session & Capabilities:
```powershell
Get-Content "$env:LOCALAPPDATA\1998TeamPhotobooth\Logs\1998team_photobooth.log" | Select-String "MaidSession", "Type0026", "CapGet", "ADD_CHILD", "DEL_CHILD"
```

#### 3. Log Live View Stream:
```powershell
Get-Content "$env:LOCALAPPDATA\1998TeamPhotobooth\Logs\1998team_photobooth.log" | Select-String "LiveView Streamer", "read_frame", "FPS", "CameraLiveViewWorker"
```

#### 4. Log Capture & Autofocus:
```powershell
Get-Content "$env:LOCALAPPDATA\1998TeamPhotobooth\Logs\1998team_photobooth.log" | Select-String "autofocus", "FaceEyeAF", "capture_photo", "Acquire", "Watchdog"
```

---

## PHẦN 5: BẢNG SO SÁNH PHÂN BIỆT SIMULATOR VÀ NIKON D780 THẬT

| Tiêu chí | Chế độ Giả Lập (Simulator) | Thiết bị Thật (Nikon D780) |
| :--- | :--- | :--- |
| **Driver Backend** | `SIMULATOR` | `NIKON_MAID` (Type0026.md3 x64) |
| **Nguồn cấp hình ảnh** | Ảnh mẫu tĩnh tổng hợp trong RAM | Cảm biến BSI CMOS Full-Frame 24.5 MP thật |
| **Độ phân giải Live View** | 960 × 640 @ 30 FPS | 1024 × 680 @ 38 FPS (USB Stream) |
| **Độ phân giải chụp ảnh** | 2400 × 1600 (3.8 MP) | 6048 × 4024 (24.3 MP nguyên bản) |
| **Thời gian truyền ảnh chụp** | Tức thì (~5ms) | 600ms – 1.2s qua USB 3.0 Direct |
| **Autofocus** | Giả lập trả về `SUCCESS_IN_FOCUS` | Phần cứng lens di chuyển thấu kính quang học |
| **Âm thanh màn trập** | Chỉ có file âm thanh phần mềm phát ra loa | Tiếng màn trập cơ học thật kêu trên thân máy |
| **Chỉ báo trên giao diện** | Chấm vàng `🟡 Mô Phỏng` | Chấm xanh `🟢 Đã Kết Nối: Nikon D780` |
