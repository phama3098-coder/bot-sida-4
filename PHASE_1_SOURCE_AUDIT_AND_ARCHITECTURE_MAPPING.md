# 1998 TEAM PHOTOBOOTH v2.0.0
# PHASE 1 — SOURCE AUDIT & ARCHITECTURE MAPPING REPORT

> **Dự án:** 1998 TEAM Photobooth  
> **Phiên bản đích:** v2.0.0  
> **Kiến trúc:** Hybrid Design System v2.0 (Operator: Concept A | Kiosk: Concept B | Status: Concept C)  
> **Baseline bảo vệ:** v1.6.6 Build 166 (Commit `4235fb5`, Tag `v1.6.6-build166-baseline`, 306/306 Tests PASS)  
> **Nhánh phát triển:** `feature/v2.0.0-photobooth`  
> **Ngày lập:** 2026-11-02  
> **Trạng thái:** HOÀN TẤT & SẴN SÀNG TRIỂN KHAI PHASE 2  

---

## 1. MỤC TIÊU & CAM KẾT BẢO TỒN BASELINE

Theo chỉ thị của Chủ dự án:
1. **Phiên bản đích**: Chuyển thẳng lên **v2.0.0**, bỏ qua các nhánh cập nhật nhỏ lẻ (v1.6.7, v1.6.8...).
2. **Bảo tồn tuyệt đối Build 166**:
   - Toàn bộ source baseline Build 166 đã được commit tại nhánh `feature/v1.6.6-printing-and-audio` và gắn tag cố định `v1.6.6-build166-baseline`.
   - Kết quả kiểm thử trước khi phân nhánh: **306/306 test PASS (100%)**.
   - Mọi công việc v2.0.0 được thực hiện độc lập trên nhánh `feature/v2.0.0-photobooth`.
   - Không ghi đè installer, không thay đổi file release cũ trong `releases/v1.6.6-build166/` và `dist_installer/`.
3. **Bảo toàn Camera Engine**:
   - Giữ nguyên Nikon MAID3 Backend (`Type0026.md3`, `NkRoyalmile.dll`, `NkdPTP.dll`).
   - Giữ nguyên driver Windows WPD Native (tuyệt đối không dùng Zadig hay WinUSB).
   - Bảo toàn cơ chế Live View, Face/Eye AF tracking, và Capture Transaction Token.

---

## 2. KIỂM KÊ MÃ NGUỒN BUILD 166 (SOURCE CODE INVENTORY)

Toàn bộ gói mã nguồn chính `vietphotobooth/` gồm **116 tệp Python** phân chia theo 7 tầng chức năng rõ ràng:

### 2.1. Tầng Giao Diện Người Dùng (Presentation Layer — Desktop GUI)
| Tệp nguồn | Số dòng | Lớp đối tượng chính | Chức năng hiện tại (v1.6.6) | Đánh giá chuyển đổi v2.0.0 |
| :--- | :---: | :--- | :--- | :--- |
| `desktop/main_window.py` | 609 | `MainWindow` | Quản lý cửa sổ chính qua `QTabWidget` (6 tab). | **Tái cấu trúc**: Chuyển sang bố cục 2 tầng: Sidebar Operator 10 phân hệ + Fullscreen Kiosk Mode. |
| `desktop/widgets/kiosk_page.py` | 2,435 | `KioskPage`, `CompositeWorker`, `PrintWorker` | Điều khiển luồng chụp Kiosk, preview, đếm ngược. | **Tái cấu trúc lớn**: Tách nhỏ các view, tích hợp Pose Guidance và Slot-based Retake 4 ô độc lập. |
| `desktop/widgets/camera_page.py` | 1,960 | `CameraPage`, `DiagnosticWorker`, `CameraConnectWorker` | Thiết lập máy ảnh, chẩn đoán, live view preview. | **Nâng cấp thành `CaptureStudioPage`**: Bổ sung toolbar 6 trạng thái camera và tiến trình 4 slots. |
| `desktop/widgets/events_page.py` | 915 | `EventsPage` | CRUD sự kiện, lồng album thư viện ảnh. | **Tái cấu trúc**: Tách Gallery ra riêng, tối ưu hóa giao diện danh thiếp sự kiện Concept A. |
| `desktop/widgets/templates_page.py` | 480 | `TemplatesPage`, `FrameTabContainer` | Duyệt khung ảnh, quản lý template. | **Nâng cấp**: Bổ sung bộ lọc danh mục (4 ô Hàn Quốc, Đám cưới...) và hiển thị số slot. |
| `desktop/widgets/frame_designer_page.py`| 1,040 | `FrameDesignerPage` | Trình thiết kế khung ảnh, tọa độ pixel slot. | **Tách biệt**: Trở thành phân hệ quản trị độc lập, tách rời khỏi luồng chụp photobooth. |
| `desktop/widgets/printing_page.py` | 520 | `PrintingPage` | Thiết lập máy in, hàng đợi in Spooler. | **Nâng cấp thành `PrintingCenterPage`**: Bổ sung đồng hồ đo giấy/ruy-băng và toolbar 4 trạng thái lỗi. |
| `desktop/widgets/settings_page.py` | 530 | `SettingsPage` | Cài đặt âm thanh, Google Drive, đổi mã PIN. | **Tái cấu trúc**: Cải tiến giao diện cấu hình âm lượng loa Kiosk, giọng đọc tiếng Việt và đổi mã PIN. |
| `desktop/widgets/live_viewport.py` | 453 | `CameraLiveViewport` | Viewport hiển thị Live View mượt mà, tỷ lệ 3:2. | **GIỮ NGUYÊN & KẾ THỪA 100%**: Đã tối ưu hóa chống nhấp nháy, hỗ trợ bounding box Eye AF và hiệu ứng flash. |
| `desktop/widgets/smart_beauty_panel.py` | 280 | `SmartBeautyEngine`, `SmartBeautyDialog` | Bảng điều chỉnh làm đẹp da mặt. | **GIỮ NGUYÊN**: Gọi qua workflow khi cần kích hoạt bộ lọc làm đẹp. |
| `desktop/styles.py` | 393 | Constants & QSS | Bảng màu và CSS giao diện v1.6.6. | **Mở rộng**: Bổ sung Design Tokens Hybrid System (Obsidian, Champagne Gold, Warm Pearl). |

### 2.2. Tầng Điều Phối & Máy Trạng Thái (Application & Workflow Layer)
| Tệp nguồn | Số dòng | Lớp đối tượng chính | Chức năng | Định hướng v2.0.0 |
| :--- | :---: | :--- | :--- | :--- |
| `core/state_machine.py` | 256 | `SessionManager` | Quản lý trạng thái phiên chụp (Idle, Countdown, Review...). | **Nâng cấp**: Bổ sung trạng thái `RETAKE_SLOT` hỗ trợ chụp lại từng ô con độc lập. |
| `core/events.py` | 261 | `EventManager` | Quản lý thư mục sự kiện, ID phiên, số lượng ảnh. | **Kế thừa 100%**: Tiếp tục là nguồn lưu trữ phiên và metadata. |
| `core/config.py` | 185 | `ConfigManager` | Đọc ghi cấu hình JSON cục bộ. | **Kế thừa 100%**: Mở rộng thêm các cấu hình Kiosk theme preset và mã PIN. |
| `core/auth.py` | 145 | `AdminAuthManager` | Xác thực quyền quản trị viên bằng mã PIN. | **Nâng cấp**: Tích hợp cơ chế mã hóa dấu chấm tròn, rung lắc báo sai và khóa an toàn 30 giây. |
| `core/font_registry.py` | 221 | `FontRegistry` | Quản lý phông chữ tiếng Việt cho khung ảnh. | **Kế thừa 100%**. |

### 2.3. Tầng Động Cơ Máy Ảnh (Camera Engine — BẢO TOÀN TUYỆT ĐỐI)
| Tệp nguồn | Số dòng | Lớp đối tượng chính | Chức năng | Trạng thái bảo toàn |
| :--- | :---: | :--- | :--- | :--- |
| `camera/connection_manager.py` | 846 | `CameraConnectionManager`, `FPSTracker` | Điều phối kết nối thống nhất, quản lý backend, FPS. | **BẢO TOÀN 100%**: Không sửa đổi kiến trúc, giữ nguyên capture transaction token. |
| `camera/manager.py` | 26 | `CameraManager` | Wrapper kế thừa tương thích ngược. | **BẢO TOÀN 100%**. |
| `camera/backends/nikon_maid/maid_session.py` | 1,104 | `NikonSession` | Giao tiếp MAID3 SDK mức thấp với Nikon D780. | **BẢO TOÀN 100%**: Tuyệt đối không can thiệp. |
| `camera/backends/nikon_maid/nikon_d780_backend.py` | 336 | `NikonD780Backend` | Triển khai cụ thể cho body Nikon D780 DSLR. | **BẢO TOÀN 100%**. |
| `camera/backends/nikon_maid/maid_loader.py` | 141 | `NikonSDKLoader` | Nạp DLL native (`Type0026.md3`, `NkRoyalmile.dll`). | **BẢO TOÀN 100%**. |
| `camera/backends/nikon_maid/camera_worker.py` | 218 | `NikonCameraWorker` | Luồng nền đọc Live View và tải ảnh trập. | **BẢO TOÀN 100%**. |
| `camera/face_detector.py` | 354 | `FaceEyeDetector`, `FaceDetectionService` | Nhận diện khuôn mặt và mắt qua Haar / YuNet DNN. | **BẢO TOÀN 100%**. |
| `camera/face_eye_af_controller.py` | 706 | `FaceEyeAFController` | Tự động điều khiển vùng lấy nét theo mắt. | **BẢO TOÀN 100%**. |
| `camera/backends/simulator.py` | 193 | `SimulatorBackend` | Giả lập máy ảnh phục vụ kiểm thử tự động. | **BẢO TOÀN 100%**. |

### 2.4. Tầng Xử Lý Hình Ảnh (Image Processing & Compositing)
| Tệp nguồn | Số dòng | Lớp đối tượng chính | Chức năng | Định hướng v2.0.0 |
| :--- | :---: | :--- | :--- | :--- |
| `processing/image_processor.py` | 231 | `ImageProcessor` | Xoay, lật gương, cắt cúp và điều chỉnh tỷ lệ ảnh. | **Kế thừa 100%**: Sử dụng để xử lý từng slot riêng biệt. |
| `processing/template_engine.py` | 308 | `TemplateEngine` | Ghép các slot ảnh vào khung in theo tọa độ pixel. | **Kế thừa & Nâng cấp**: Hỗ trợ xuất composite tức thì khi có 1 slot retake. |
| `filters/filter_engine.py` | 390 | `FilterEngine` | Áp dụng bộ lọc màu LUT và hiệu ứng nghệ thuật. | **Kế thừa 100%**. |
| `filters/beauty_engine.py` | 320 | `BeautyEngine` | Thuật toán làm mịn da và làm sáng khuôn mặt. | **Kế thừa 100%**. |

### 2.5. Tầng In Ấn & Spooler (Printing Engine)
| Tệp nguồn | Số dòng | Lớp đối tượng chính | Chức năng | Định hướng v2.0.0 |
| :--- | :---: | :--- | :--- | :--- |
| `printing/manager.py` | 366 | `PrintManager`, `PrintJob` | Quản lý lệnh in, căn lề, số lượng bản sao. | **Kế thừa 100%**. |
| `printing/spooler.py` | 275 | `WindowsPrintSpooler` | Giao tiếp driver máy in nhiệt qua Windows Spooler. | **Kế thừa 100%**: Bảo đảm in mượt không kẹt spooler. |
| `printing/dnp_rx1hs.py` | 83 | `DNPRX1HSProfile` | Cấu hình chuyên dụng cho máy in DNP DS-RX1HS. | **Kế thừa 100%**. |

### 2.6. Tầng Chia Sẻ Ngoại Vi & Âm Thanh (QR / LAN Sharing & Studio Audio)
| Tệp nguồn | Số dòng | Lớp đối tượng chính | Chức năng | Định hướng v2.0.0 |
| :--- | :---: | :--- | :--- | :--- |
| `server.py` | 412 | FastAPI Web Server | Máy chủ HTTP nội bộ cho khách quét QR tải ảnh. | **Kế thừa 100%**: Hoạt động offline 100% không cần Internet. |
| `sharing/token_manager.py` | 148 | `TokenManager`, `ShareToken` | Tạo và quản lý mã token tải ảnh an toàn. | **Kế thừa 100%**. |
| `audio/sound_controller.py` | 173 | `SoundController` | Phát âm thanh giọng đếm tiếng Việt và trập Nikon. | **Kế thừa 100%**: Liên kết trực tiếp với Kiosk Viewfinder. |

---

## 3. SƠ ĐỒ ĐỐI CHIẾU KIẾN TRÚC: BUILD 166 VS V2.0.0 (ARCHITECTURE MAPPING)

```
========================================================================================
KIẾN TRÚC BUILD 166 (CŨ)                 KIẾN TRÚC v2.0.0 (HYBRID APPROVED)
========================================================================================

MainWindow (QTabWidget 6 tab đỉnh)       MainWindow (Kiến trúc 2 chế độ Hybrid)
│                                        ├── 1. OPERATOR COCKPIT (Concept A - Obsidian & Gold)
├─ Tab 1: Kiosk (chụp ảnh lồng tab)      │   ├── Navigation Sidebar (10 Phân Hệ Riêng Biệt):
├─ Tab 2: Khung ảnh (thư viện + design)  │   │   ├── 01. Dashboard (Buồng lái tác nghiệp trung tâm) [MỚI]
├─ Tab 3: Máy ảnh (cấu hình kỹ thuật)    │   │   ├── 02. Capture Studio (Buồng chụp kỹ thuật) [NÂNG CẤP]
├─ Tab 4: Máy in (driver & test print)   │   │   ├── 03. Events (Quản lý sự kiện) [NÂNG CẤP]
├─ Tab 5: Sự kiện & Thư viện (gộp chung) │   │   ├── 04. Templates (Thư viện khung 4 ô) [NÂNG CẤP]
└─ Tab 6: Cài đặt (hệ thống & bản quyền) │   │   ├── 05. Gallery (Thư viện ảnh sự kiện) [MỚI]
                                         │   │   ├── 06. Printing Center (Quản lý máy in DNP) [NÂNG CẤP]
                                         │   │   ├── 07. QR Sharing (Chia sẻ mạng nội bộ) [MỚI]
                                         │   │   ├── 08. Devices (Giám sát thiết bị đa kênh) [MỚI]
                                         │   │   ├── 09. Settings (Cài đặt hệ thống & PIN) [NÂNG CẤP]
                                         │   │   └── 10. Frame Designer (Trình thiết kế tọa độ) [TÁCH BIỆT]
                                         │   └── Nút Chuyển Chế Độ Kiosk Toàn Màn Hình: [🚀 START PHOTOBOOTH (F11)]
                                         │
                                         └── 2. GUEST / KIOSK STAGE (Concept B - Modern Event)
                                             ├── Điểm chạm bí mật góc phải (3 chạm) + Bàn phím PIN mã hóa + Khóa 30s
                                             ├── 1. Màn hình chờ Welcome: Nút chạm cực đại 340×88px
                                             ├── 2. Màn hình chụp & đếm ngược: Viewfinder + Pose Guidance Overlay Box
                                             ├── 3. Màn hình Review 4 Ô: Hỗ trợ Slot-based Retake (Chụp lại từng ô)
                                             └── 4. Màn hình in & nhận QR: Vòng tròn tiến trình + mã QR tại chỗ
```

---

## 4. MA TRẬN PHÂN CHIA NHIỆM VỤ CÁC PHÂN HỆ V2.0.0

| STT | Phân hệ v2.0.0 | Mã module triển khai | Phần tái sử dụng từ Build 166 | Phần xây dựng mới hoàn toàn |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Dashboard** | `desktop/widgets/dashboard_page.py` | Lấy dữ liệu từ `EventManager`, `PrintManager`, `CameraConnectionManager`. | Giao diện buồng lái Concept A: 4 stat cards có nhãn `[DEMO]`, Live View feed trung tâm, active template card, nút Start Kiosk F11. |
| **2** | **Capture Studio** | `desktop/widgets/capture_studio_page.py` | Kế thừa toàn bộ logic từ `CameraPage`, `DiagnosticWorker`, `CameraConnectWorker`, `LiveViewport`. | Bố cục buồng chụp Concept A, toolbar 6 trạng thái camera (`Connected`, `Connecting`, `Busy`, `Warning`, `Error`, `Disconnected`), danh sách 4 tư thế sẵn sàng. |
| **3** | **Quản Lý Sự Kiện** | `desktop/widgets/events_page.py` | Kế thừa `EventManager`, logic tạo thư mục, lưu trữ metadata. | Giao diện thẻ sự kiện hiện đại, hiển thị số phiên/bản in, nút kích hoạt 1 cú click. |
| **4** | **Thư Viện Khung** | `desktop/widgets/templates_page.py` | Kế thừa `FrameManager`, `FrameTemplate`. | Thẻ chip lọc danh mục (4 ô Hàn Quốc, Đám cưới, Doanh nghiệp...), lưới template hiển thị số slot chuẩn 1x4 strip. |
| **5** | **Thư Viện Ảnh** | `desktop/widgets/gallery_page.py` | Kế thừa logic đọc file ảnh từ `EventManager`. | Giao diện album ảnh độc lập: Lưới ảnh composite 4 ô, nhãn phiên, lịch sử chụp lại từng ô, nút In lại và Xem QR. |
| **6** | **Trung Tâm In Ấn** | `desktop/widgets/printing_center_page.py`| Kế thừa `PrintManager`, `WindowsPrintSpooler`, `DNPRX1HSProfile`. | Đồng hồ đo cuộn giấy DNP 486/700 `[SIMULATED]`, ruy-băng 69%, toolbar 4 trạng thái lỗi máy in, danh sách hàng đợi Spooler. |
| **7** | **Chia Sẻ Mã QR** | `desktop/widgets/qr_sharing_page.py` | Kế thừa `server.py`, `TokenManager`. | Màn hình quản trị Wi-Fi Hotspot LAN, thông số SSID/IP/Port, khung mô phỏng giao diện web di động của khách. |
| **8** | **Giám Sát Phần Cứng**| `desktop/widgets/devices_page.py` | Kế thừa các hàm đọc telemetry trong `CameraConnectionManager` và `PrintManager`. | Bảng giám sát đa kênh Concept C cho Nikon D780, DNP DS-RX1HS và WiFi, banner cảnh báo kiểm thử minh bạch. |
| **9** | **Cài Đặt Hệ Thống** | `desktop/widgets/settings_page.py` | Kế thừa `ConfigManager`, `AdminAuthManager`. | Bố cục cài đặt âm thanh studio, giọng đọc đếm ngược tiếng Việt, ô đổi mã PIN quản trị viên. |
| **10**| **Frame Designer** | `desktop/widgets/frame_designer_page.py`| Kế thừa canvas và logic căn chỉnh slot từ v1.6.6. | Tách rời thành phân hệ độc lập, giao diện tối ưu cho việc căn chỉnh 4 ô ảnh mà không làm gián đoạn luồng chụp. |
| **11**| **Guest / Kiosk Mode**| `desktop/widgets/kiosk_page.py` | Kế thừa `LiveViewport`, `SoundController`, `ImageProcessor`, `TemplateEngine`. | **Kiến trúc Kiosk Concept B mới**:<br>• Hộp Pose Guidance Overlay theo từng shot.<br>• Màn hình Review dải 4 ô độc lập.<br>• **Slot-based Retake**: Chọn chụp lại ô #2, bảo toàn 100% ô 1, 3, 4.<br>• Điểm chạm bí mật góc phải + PIN keypad mã hóa dấu chấm tròn + rung lắc + khóa an toàn 30 giây. |

---

## 5. PHÂN TÍCH RỦI RO & BIỆN PHÁP KIỂM SOÁT (RISK ASSESSMENT)

1. **Rủi ro ngắt Live View / MAID session khi chuyển tab**:
   - *Nguyên nhân tiềm ẩn*: Trong kiến trúc desktop cũ, việc chuyển đổi QWidget có thể gọi `hideEvent` làm ngắt kết nối worker camera.
   - *Giải pháp*: Tách rời vòng đời `CameraConnectionManager` hoàn toàn khỏi UI. Đối tượng camera chạy ở cấp độ `MainWindow` xuyên suốt phiên ứng dụng. Các widget (`DashboardPage`, `CaptureStudioPage`, `KioskPage`) chỉ gắn kết/ngắt kết nối sự kiện render frame (`frame_ready` signal), không bao giờ gọi lệnh ngắt camera backend khi chuyển tab.
2. **Rủi ro Slot-based Retake làm sai lệch dữ liệu ảnh**:
   - *Nguyên nhân tiềm ẩn*: Ghi đè nhầm file ảnh gốc hoặc tạo chỉ mục sai trong mảng ảnh.
   - *Giải pháp*: Xây dựng cấu trúc dữ liệu `SessionSlotManager` có kiểm soát:
     ```python
     class SessionSlot:
         slot_index: int       # 0, 1, 2, 3
         raw_image_path: str   # Đường dẫn ảnh gốc độ phân giải cao
         is_retaken: bool      # False (gốc) hoặc True (đã chụp lại)
         timestamp: float      # Thời điểm chụp
     ```
     Khi chụp lại slot $k$, chỉ cập nhật đúng phần tử tại index $k$, 3 phần tử còn lại được bảo toàn nguyên vẹn 100%. Bắt buộc viết bài kiểm thử Unit Test chuyên biệt trước khi tích hợp vào giao diện.
3. **Rủi ro hồi quy (Regression) đối với 306 bài test hiện tại**:
   - *Giải pháp*: Giữ nguyên các hàm cốt lõi và public interfaces. Kiểm tra pytest liên tục sau mỗi giai đoạn triển khai để duy trì 100% tỷ lệ PASS.

---

## 6. KẾ HOẠCH HÀNH ĐỘNG TIẾP THEO: PHASE 2 — CORE UI & NAVIGATION

Sau khi Phase 1 đã hoàn tất khảo sát toàn diện và lập bản đồ kiến trúc:
- **Bước 1**: Xây dựng khung điều hướng chính `MainWindow` theo kiến trúc Hybrid: Sidebar Operator Concept A (10 phân hệ) + Container Kiosk Concept B.
- **Bước 2**: Xây dựng phân hệ mới `DashboardPage` làm trung tâm buồng lái vận hành.
- **Bước 3**: Triển khai Design System Tokens (Dark Obsidian, Champagne Gold, Warm Pearl) vào hệ thống stylesheet.
- **Bước 4**: Chạy kiểm thử xác minh và chụp ảnh giao diện thực tế.
