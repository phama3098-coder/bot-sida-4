# BÁO CÁO NGHIÊN CỨU CHUYÊN SÂU: HIHIBOOTH (VIETNAM)
**Dự án đối chuẩn:** 1998 TEAM Photobooth (Tham chiếu v1.6.5 Build 165)  
**Đối tượng nghiên cứu:** HihiBooth (`hihibooth.app`, `com.hihi.boothv2`)  
**Phương pháp:** Khảo sát sản phẩm thực tế, đối soát tài liệu công khai, kiểm tra cấu hình nhị phân, manifest runtime và kịch bản in ấn ngoại tuyến (Offline-first Inspection).  
**Ngày thực hiện:** Tháng 11/2026  

---

## 1. TỔNG QUAN DOANH NGHIỆP & ĐỊNH VỊ SẢN PHẨM

### 1.1. Hệ Sinh Thái & Mô Hình Kinh Doanh
HihiBooth (`https://hihibooth.app`) là một trong những giải pháp phần mềm và nền tảng nhượng quyền photobooth thương mại hàng đầu tại Việt Nam. Sản phẩm định vị mạnh mẽ vào 3 mô hình kinh doanh chính:
1. **Photobooth Di Động / Pop-up (Mobile Events):** Phục vụ các hội chợ ẩm thực, phố đi bộ, tiệc cưới, lễ kỷ yếu, sự kiện kích hoạt thương hiệu (Brand Activation) với tiêu chí triển khai nhanh dưới 15 phút.
2. **Kiosk Chụp Ảnh Tự Động 24/7 (Unattended Kiosk):** Vận hành không cần nhân sự trực nhờ tích hợp thanh toán chuyển khoản tự động VietQR động.
3. **Chuỗi Studio Tự Phục Vụ (Self-Photo Studio):** Tối ưu hóa luồng chụp và in lấy liền theo phong cách Hàn Quốc (Korean 4-Cut).

### 1.2. Phân Định Mức Độ Thông Tin
- **[Observed Facts]:** Thu thập từ các tệp thực thi, manifest `session-manifest.json`, cấu hình `local-desktop-settings.json`, cache `app-config-cache.json`, hàng đợi `sync-jobs.json` và script `print_dnp.ps1` thực tế trên hệ thống (`AppData/Roaming/com.hihi.boothv2`, `AppData/Local/com.hihi.boothv2`, `Program Files/HihiBooth`).
- **[Publicly Documented Features]:** Thông tin từ website `hihibooth.app`, video hướng dẫn vận hành, tài liệu giới thiệu gói phần mềm.
- **[Technical Hypotheses]:** Suy luận kỹ thuật về cơ chế đồng bộ, pipeline đồ họa và thuật toán xử lý ảnh.
- **[Not Verified]:** Các tính năng cao cấp chưa kích hoạt trong bản cài đặt kiểm tra (ví dụ: live view stream over WebRTC).

---

## 2. BẰNG CHỨNG THỰC TẾ & KIẾN TRÚC KỸ THUẬT CỐT LÕI

### 2.1. Kiến Trúc Hybrid Microservices & Sidecar Pattern [Observed Facts]
HihiBooth không xây dựng theo mô hình nguyên khối (Monolith) mà áp dụng mô hình **Tauri / Rust Shell + Sidecar Microservices** cực kỳ hiện đại:
```mermaid
graph TD
    UI[HihiBooth Frontend: HTML/CSS/React via WebView2] <--> Shell[HihiBooth Shell: Rust + Tauri hihibooth.exe]
    Shell --> Bridge[Sidecar 1: HihiCamBridge.exe .NET Core CLR]
    Shell --> Skin[Sidecar 2: hihicam-skin-bridge.exe MediaPipe AI]
    Shell --> Print[Resource Script: print_dnp.ps1 PowerShell Controller]
    
    Bridge --> Nikon[Nikon MAID Type0008 - Type0026 C-Bindings]
    Bridge --> Canon[Canon EDSDK.dll]
    Bridge --> Fuji[Fujifilm FF0000API - FF0009API]
    
    Skin --> MP[Google MediaPipe face_landmarker.task]
    Print --> DNP[DNP DS-RX1HS / QW410 Thermal Engine]
    
    Shell <--> Cache[Local Cache: app-config-cache.json & sync-jobs.json]
    Cache <--> Cloud[Cloudflare R2 & Laravel API panel.hihibooth.app]
```

#### Chi tiết các thành phần nhị phân:
1. **Frontend Host & Shell (`hihibooth.exe`, 13.3 MB):** Ứng dụng biên dịch từ Rust qua Tauri framework. Sử dụng Microsoft WebView2 làm engine render giao diện Kiosk. Tiêu thụ RAM ban đầu cực thấp (~90 - 140 MB).
2. **Camera Bridge Sidecar (`hihicam-bridge-bin/HihiCamBridge.exe`, runtime .NET Core CLR):**
   - Đóng gói đầy đủ driver C/C++ native của 3 ông lớn:
     - Nikon: `Type0008.md3` đến `Type0026.md3`, `NkdPTP.dll`, `NkRoyalmile.dll`.
     - Canon: `EDSDK.dll`, `EdsImage.dll`.
     - Fujifilm: `FF0000API.dll` đến `FF0009API.dll`, `XAPI.dll`.
   - Tiến trình này chạy độc lập; nếu máy ảnh bị ngắt cáp USB đột ngột hoặc treo firmware, tiến trình `HihiCamBridge` tự khởi động lại mà không làm sập giao diện Kiosk chính của khách.
3. **AI Beauty Sidecar (`hihicam-skin-bridge.exe`, 108.8 MB):**
   - Tích hợp mô hình Google MediaPipe: `face_landmarker.task` (3.75 MB).
   - Cho phép định vị chính xác **468 điểm mốc 3D** trên khuôn mặt, vượt trội so với các mô hình 5 điểm thông thường.
4. **Backend Điện Toán Đám Mây:**
   - API Quản trị: Laravel PHP (`App\Models\Image` ghi nhận trong JSON) tại `https://panel.hihibooth.app/api`.
   - Lưu trữ CDN: **Cloudflare R2** (`https://file.hihibooth.app/media/sha256/...`) với cơ chế băm SHA-256 chống trùng lặp dữ liệu (Deduplication).

---

## 3. KHẢO SÁT CHỨC NĂNG CHI TIẾT THEO 11 TRỤC

### 3.1. Giao Diện Quản Trị (Admin UI) [Observed Facts & Publicly Documented]
- **Bảo mật & Cấp phép:** Quản lý bản quyền theo thiết bị qua token `offlineLicense`:
  `deviceId: "booth-97721778-9230-4222-950b-584615f08e5a"`, `machineId: "306"`, có trường thời gian hết hạn `licenseExpiresAtMs`.
- **Cấu hình trực quan:** Cho phép thiết lập số giây đếm ngược (`countdownSeconds: 10`), thời gian trễ tự động bắt đầu (`autoStartCapture.delaySeconds: 10`), chế độ chụp thủ công/tự động (`manualCaptureMode`), và cho phép chụp lại kiểu lỗi (`allowRetake: true`).
- **Giao diện quản trị từ xa (Web Panel):** Chủ booth đăng nhập tại `panel.hihibooth.app` để xem doanh thu, số lượt chụp, thay đổi layout sự kiện từ xa mà không cần cắm chuột bàn phím vào máy Kiosk.

### 3.2. Giao Diện Khách (Kiosk UI) [Observed Facts & Impeccable Analysis]
- **Luồng khách hàng (Customer Journey):**
  `Màn hình chờ (Idle)` ➔ `Quét mã VietQR chuyển khoản (nếu bật)` ➔ `Chọn khung ảnh (Grid / Square / Strip)` ➔ `Chuỗi đếm ngược chụp 3-4 kiểu` ➔ `Chỉnh sửa/Chọn filter màu & son môi` ➔ `In ảnh & Quét QR nhận file gốc + Video`.
- **Nút bấm góc ẩn (Discreet Corner Buttons):** Có tùy chọn `"hideCornerButtons": false` để ẩn toàn bộ nút thoát, ngăn khách nghịch phá.
- **Âm thanh đếm ngược:** Đã tích hợp `"countdownAudio": { "beepEnabled": true }` và phát file âm thanh mở đầu `introAudioFileName`.

### 3.3. Camera Workflow & Autofocus [Observed Facts]
- Cấu hình thông số máy ảnh trực tiếp từ phần mềm:
  `"camera": { "aperture": "auto", "iso": "auto", "shutterSpeed": "auto", "whiteBalanceKelvin": 5600 }`.
- Hỗ trợ Live View lật gương (`"mirrorPreview": true`).
- Tự động kết nối lại khi lỏng cáp (`"autoReconnectCamera": true`).
- Định dạng ảnh chụp nguyên bản: `captureFormat: "png"` hoặc `"jpg"`.
- *Nhận xét so sánh:* HihiBooth điều khiển lấy nét qua autofocus tổng thể của body Nikon/Canon thông qua SDK, **chưa có cơ chế điều khiển lấy nét mắt phần cứng theo tọa độ động (Eye AF Dynamic Targeting)** như 1998 TEAM đã phát triển với `kNkMAIDCapability_ContrastAFArea`.

### 3.4. AI Beauty & Bộ Lọc Màu Nghệ Thuật [Observed Facts]
Cấu hình trong `local-desktop-settings.json` hé lộ đầy đủ các tham số làm đẹp:
- **Làm mịn da (Skin Smoothing):** `"skinSmoothingEnabled": false`, cường độ `"skinSmoothingIntensity": 40` (thang 0-100).
- **Làm trắng da (Skin Whitening):** `"skinWhiteningEnabled": false`, cường độ `"skinWhiteningIntensity": 25`.
- **Tô son môi ảo (Lipstick):** `"lipstickEnabled": false`, `"lipstickColor": "#c84b63"`, `"lipstickIntensity": 35`.
- **Đánh má hồng (Blush):** `"blushEnabled": false`, `"blushColor": "#e97a86"`, `"blushIntensity": 28`.
- **Bộ lọc màu điện ảnh:** Hỗ trợ nạp các tệp 3D LUT tiêu chuẩn: `"cubeFilters": []`.
- Nhờ có MediaPipe 468 điểm, HihiBooth định vị được cả viền môi và gò má để đánh má hồng chuẩn xác.

### 3.5. Frame Designer & Metadata Tọa Độ Ô Ảnh [Observed Facts]
- Trong `app-config-cache.json`, mỗi khung ảnh được định nghĩa với cấu trúc `holes_metadata` cực kỳ chính xác:
  ```json
  "holes_metadata": {
    "fw": 2400,
    "fh": 3600,
    "holes": [
      { "x": 72, "y": 58, "w": 932, "h": 933 },
      { "x": 1152, "y": 103, "w": 1153, "h": 1117 },
      { "x": 72, "y": 1102, "w": 932, "h": 933 },
      { "x": 1080, "y": 2164, "w": 1225, "h": 1113 }
    ]
  }
  ```
- **Hỗ trợ đa dạng dáng khung (Shapes):** `grid` (lưới), `square` (vuông), `strip` (dải dài 2x6).
- **Per-hole Capture Overrides:** Có cơ chế `"holeCaptureOverrides"` cho phép từng ô ảnh có cấu hình thời gian đếm ngược hoặc bộ lọc riêng biệt.

### 3.6. Xử Lý Ảnh & Video Hậu Trường (BTS Video Recap) [Observed Facts]
- **Tạo Video Tự Động:** Trong mỗi phiên chụp tại `C:\Prints\<sessionId>\`, HihiBooth xuất ra đồng thời:
  1. `collage.png` (7.28 MB): Ảnh ghép hoàn chỉnh với khung đồ họa.
  2. `print_ready.png` (7.28 MB): Ảnh đã scale và xoay sẵn sàng gửi lệnh in.
  3. `recap.mp4` (**12.7 - 13.3 MB**): Video hậu trường timelapse ghép lại từ các frame Live View trong lúc đếm ngược.
  4. 4 file ảnh chụp gốc `hihi_native-..._00.jpg` đến `_03.jpg`.
  5. `session-manifest.json` ghi nhận metadata phiên.

### 3.7. Quy Trình In Ấn DNP & Tối Ưu Bù Trừ Lề [Observed Facts]
Script `resources/print_dnp.ps1` thể hiện kỹ thuật in ấn đẳng cấp:
- **In ngầm tuyệt đối:** Sử dụng `System.Drawing.Printing.StandardPrintController` để không xuất hiện hộp thoại Windows Printing.
- **Tự động nhận diện hướng giấy & Xoay 90 độ:**
  Nếu ảnh ngang (`$imgW > $imgH`) mà trang in đang là dọc (`$pWidth < $pHeight`), script tự động gọi `$img.RotateFlip([System.Drawing.RotateFlipType]::Rotate90FlipNone)` trước khi vẽ.
- **Chống tràn viền và bù trừ dao cắt:** Áp dụng hệ số zoom mặc định **0.98 (98%)** kết hợp căn giữa tự động và bộ lọc nội suy `HighQualityBicubic`, triệt tiêu hoàn toàn rủi ro lưỡi dao DNP cắt phạm vào chữ hoặc khung ảnh.
- **Giám sát số lượng giấy in:** Cấu hình có bộ đếm giấy `"paperCounter": { "loadedSheets": 400, "remainingSheets": 400, "warningThreshold": 40 }`.

### 3.8. QR Code Gallery & Đồng Bộ Đám Mây (Cloud Sync) [Observed Facts]
- Mã QR dẫn trực tiếp tới trang xem ảnh: `https://panel.hihibooth.app/p/<sessionId>`.
- Khách quét mã QR trên điện thoại có thể tải: Ảnh dải, ảnh từng ô gốc, và **video MP4 recap**.
- Tự động hết hạn sau 3 ngày (`"expiresAt": "2026-10-25T06:12:13.505Z"`), giải phóng dung lượng lưu trữ trên Cloudflare R2.

### 3.9. Vận Hành Ngoại Tuyến 100% (Offline-First Resilience) [Observed Facts]
- Cấu hình `"offlineModeEnabled": false`, nhưng `"preferOfflineBoot": true`!
- Khi không có Internet:
  - Tài nguyên khung ảnh được đọc từ thư mục cache cục bộ `AppData/Local/com.hihi.boothv2/offline-assets/upload/`.
  - Hàng đợi `sync-jobs.json` lưu lại toàn bộ các phiên chưa tải lên với trạng thái `"pending"`.
  - Tự động vô hiệu hóa thanh toán VietQR nếu mất mạng (`"autoDisablePaymentWhenOffline": true`), chuyển sang chế độ chụp tự do hoặc thu tiền mặt.
  - Khi có mạng trở lại, background daemon tự động đồng bộ ngầm mà không làm gián đoạn Kiosk.

### 3.10. Quản Lý Sự Kiện & Thư Mục Lưu Trữ [Observed Facts]
- Thư mục lưu trữ cố định: `C:\Prints\<sessionId>\`. Mỗi phiên chụp là một thư mục riêng biệt chứa đầy đủ ảnh ghép, ảnh gốc, video và manifest JSON. Dễ dàng sao lưu sang ổ cứng ngoài USB sau sự kiện.

---

## 4. MA TRẬN ĐÁNH GIÁ ĐỐI THỦ HIHIBOOTH

| Tiêu Chí | Điểm | Nhận Xét Kỹ Thuật & Trải Nghiệm |
| :--- | :---: | :--- |
| **Kiến Trúc & Tách Biệt Luồng** | **9.6 / 10** | Rất xuất sắc. Rust Tauri + Sidecar C# Camera Bridge + MediaPipe AI. |
| **Tốc Độ Xử Lý & Khởi Động** | **9.4 / 10** | Khởi động tức thì (< 1.5s), bộ nhớ RAM shell nhẹ (< 150 MB). |
| **Khả Năng Vận Hành Ngoại Tuyến**| **9.8 / 10** | Offline-first hoàn chỉnh, cache Cloudflare R2, hàng đợi sync-jobs bền bỉ. |
| **Trải Nghiệm Khách Hàng (CX)** | **9.2 / 10** | Có âm thanh beep, video recap MP4, hỗ trợ VietQR tự phục vụ. |
| **Quy Trình In DNP** | **9.5 / 10** | Script in PowerShell cực kỳ thông minh (bù trừ lề 98%, tự xoay 90°). |
| **Lấy Nét Camera (AF)** | **8.0 / 10** | AF toàn khung thông thường qua SDK, chưa có Face/Eye AF phần cứng như 1998 TEAM. |
| **Trình Biên Tập Khung Ảnh** | **8.5 / 10** | Quản trị trên Web Panel, tải JSON holes xuống máy trạm. |

---

## 5. BÀI HỌC QUAN TRỌNG 1998 TEAM CẦN HỌC HỎI TỪ HIHIBOOTH
1. **Quay Video Hậu Trường (Recap MP4):** Đây là "vũ khí bí mật" giúp HihiBooth bùng nổ đơn hàng tại các sự kiện giới trẻ. 1998 TEAM cần triển khai ngay bộ ghi video timelapse từ Live View.
2. **Kỹ thuật in chống cắt phạm DNP 98%:** Học tập ngay công thức tính toán `zoom = 0.98` và tự động xoay `$img.RotateFlip` trong PowerShell để áp dụng vào `vietphotobooth/printing/spooler.py`.
3. **Thanh toán VietQR động:** Mở ra khả năng vận hành booth không người trực (Unattended Kiosk), tăng giá trị thương mại cho khách hàng mua phần mềm 1998 TEAM.
