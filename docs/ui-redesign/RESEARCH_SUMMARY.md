# 1998 TEAM PHOTOBOOTH — RESEARCH SUMMARY
## Tổng Hợp Nghiên Cứu & Đánh Giá Sản Phẩm Tham Chiếu

> **Tài liệu:** Báo cáo tổng hợp nghiên cứu UI/UX trước thiết kế  
> **Dự án:** 1998 TEAM Photobooth Redesign  
> **Mục tiêu:** Đúc kết các ưu điểm, nhược điểm và bài học từ các sản phẩm Photobooth hàng đầu (Web & Desktop) để định hình kiến trúc trải nghiệm cho 1998 TEAM.

---

## 1. DANH MỤC SẢN PHẨM THAM CHIẾU & PHƯƠNG PHÁP KHẢO SÁT

Chúng tôi đã tiến hành rà soát đối chiếu dựa trên dữ liệu kiểm chứng thực nghiệm từ các tài liệu nghiên cứu trước đây của dự án (`PHOTObooth_REFERENCE_RESEARCH_01.md`, `ANTIGRAVITY_HIHIBOOTH_RESEARCH.md`, `ANTIGRAVITY_MAYTECH_RESEARCH.md`, `COMPETITOR_RESEARCH_1998_TEAM.md`):

| Nhóm sản phẩm | Tên sản phẩm | Nền tảng | Trạng thái khảo sát | Ghi chú phương pháp |
| :--- | :--- | :--- | :--- | :--- |
| **Web Photobooth** | **BeautyPlus** | Web Cloud | **Đã trực tiếp kiểm chứng** | Khảo sát thực tế DOM, Network chunks, Next.js pageProps, quy trình chụp 4 ô đếm ngược 3s. |
| **Web Photobooth** | **PhotoXinhh (FreeHihi)** | Web App | **Đã trực tiếp kiểm chứng** | Khảo sát thực tế Vue 3 bundle, 222 frame, 7 categories, âm thanh màn trập, Video Recap, Canvas export. |
| **Desktop Photobooth** | **HihiBooth** | Windows Desktop | **Quan sát & Phân tích UI** | Khảo sát cấu trúc kiosk sự kiện, luồng chọn frame và kết nối máy in nhiệt. |
| **Desktop Photobooth** | **Maytech Photobooth** | Windows Desktop | **Quan sát & Phân tích UI** | Khảo sát giao diện vận hành kiosk thương mại tại thị trường Việt Nam. |
| **Incumbent Baseline**| **1998 TEAM v1.6.6** | Windows Desktop | **Kiểm tra mã nguồn nội bộ (Read-Only)** | Phân tích `main_window.py`, `kiosk_page.py`, `camera_page.py`, `printing_page.py`, `events_page.py`. |

---

## 2. PHÂN TÍCH 10 KHÍA CẠNH CỐT LÕI TỪ THỰC TIỄN

### 2.1. Bố Cục Màn Hình (Screen Layout Architecture)
- **Web Booth (BeautyPlus, PhotoXinhh):** Tập trung vào màn hình dọc (Mobile-first / Tablet-first) hoặc chia 3 cột phẳng trên desktop. Bố cục đặt khung ngắm camera ở vị trí trung tâm, dock thao tác dồn xuống đáy.
- **Desktop Photobooth chuyên nghiệp (HihiBooth, Maytech):** Tận dụng màn hình cảm ứng tỷ lệ 16:9 (1920×1080) xoay ngang hoặc xoay dọc (Portrait Kiosk). Bố cục phân định rạch ròi: Live View chiếm từ 55% đến 70% diện tích màn hình để người dùng quan sát từ cự ly 1.5m – 2m.
- **Bài học cho 1998 TEAM:** Màn hình chụp chính (Capture Studio / Kiosk) phải ưu tiên Live View khổng lồ, sạch sẽ, không để thanh menu hoặc thông số kỹ thuật che lấp tầm nhìn.

### 2.2. Cách Tổ Chức Chức Năng (Feature Organization)
- **Cái bẫy "Photo Editor":** Một số phần mềm mắc sai lầm nghiêm trọng khi đưa thanh công cụ chỉnh sửa (Toolbar dày đặc, Layer panel, Canvas zoom, điều chỉnh chi tiết từng millimet) vào màn hình vận hành. Điều này làm rối loạn nhân viên sự kiện và khiến khách hàng hoảng sợ.
- **Tiêu chuẩn "Photobooth-First":**
  - Màn hình chính là **Trung tâm vận hành (Operation Cockpit)** hoặc **Sân khấu chụp (Capture Stage)**.
  - Các công cụ thiết kế chuyên sâu (Frame Designer, Cấu hình phơi sáng DSLR, Cấu hình Driver máy in) được cô lập vào khu vực Quản trị (Admin / Settings), chỉ nhân viên có thẩm quyền mới mở khi cần chuẩn bị.

### 2.3. Luồng Chụp Ảnh (Capture Workflow)
- Khảo sát chuỗi thao tác thực tế cho thấy luồng tối ưu tại sự kiện gồm 4 nhịp:
  1. **Chào mừng (Idle/Welcome):** Chạm vào màn hình để bắt đầu.
  2. **Đếm ngược & Tạo dáng (Countdown):** Nhịp 3s – 5s kết hợp âm thanh đếm nhịp và số đếm nảy động (Pulse animation).
  3. **Chụp tuần tự (Burst Capture):** Chớp trắng lóe sáng (White Flash) kết hợp tiếng trập cơ khí, đẩy ảnh con ngay vào khung xem trước.
  4. **Xem lại & Chấp nhận (Review & Accept):** Xem tổng thể khung ảnh hoàn chỉnh trước khi in.

### 2.4. Cách Chọn & Duyệt Khung (Frame Selection)
- Duyệt khung theo danh sách phẳng bấm Next/Prev 20 lần là một trải nghiệm tệ hại khi số lượng khung vượt quá 20 mẫu.
- **Mô hình xuất sắc từ PhotoXinhh:** Phân loại theo **Danh mục dạng Tab/Chip ngang** (*Cơ bản, Hoạt hình, Kỷ niệm, Đám cưới, Công ty*) kết hợp thumbnail nén tải tức thì. Khách hàng tìm thấy phong cách mong muốn chỉ trong 2 lần chạm.

### 2.5. Cơ Chế Chụp Lại (Review & Retake)
- **Hạn chế của các app web:** Khi bấm "Retake", hệ thống xóa sạch cả 4 ảnh và bắt khách chụp lại từ đầu, gây ức chế và làm tắc nghẽn hàng đợi tại booth.
- **Đột phá cho 1998 TEAM:** Hỗ trợ **Slot-based Retake (Chụp lại theo ô con)**. Khách chỉ cần chạm vào đúng ô ảnh thứ 2 bị nhắm mắt để chụp lại duy nhất ô đó, 3 ô đẹp còn lại được giữ nguyên vẹn!

### 2.6. Quản Lý Sự Kiện (Event-Driven Architecture)
- Tại thực địa, máy photobooth không hoạt động chung chung; nó luôn chạy theo một **Sự Kiện Cụ Thể** (ví dụ: *Đám cưới Minh & Linh*, *Gala Year End Tech 2026*).
- Mọi tài nguyên (Ảnh gốc, Ảnh in, Thống kê số phiên, Bộ template cho phép dùng, Mã QR tải ảnh) đều phải tự động gắn kết theo ID Sự Kiện đang kích hoạt.

### 2.7. Điều Khiển Máy Ảnh (Camera Control)
- Phân biệt rõ giữa hai trạng thái:
  - **Khách chụp:** Chỉ cần thấy hình ảnh phản chiếu gương mượt mà, khung nét mặt/mắt tự động bắt dính.
  - **Nhân viên chuẩn bị:** Cần nút bấm nhanh "Test Camera", "Test Live View", "Khởi động lại kết nối USB", và kiểm tra pin/thẻ nhớ mà không cần mở nắp buồng máy.

### 2.8. Điều Khiển Máy In (Printing Pipeline)
- Không biến giao diện in thành hộp thoại "Print Dialog" tiêu chuẩn của Windows (gây đơ app hoặc lộ màn hình Windows Desktop).
- Cần có:
  - Thanh trạng thái cuộn giấy & ruy-băng còn lại (Paper/Ribbon gauge).
  - Hàng đợi in trực quan (Print Spooler Queue).
  - Nút bấm In lại (Reprint) nhanh chóng trong Gallery nếu bản in trước bị kẹt giấy hoặc khách muốn in thêm bản kỷ niệm.

### 2.9. Hiển Thị Trạng Thái Thiết Bị (Device Status Indicators)
- Trạng thái phần cứng phải được biểu thị bằng đèn LED màu sắc chuẩn công nghiệp:
  - 🟢 **Xanh lá (Ready/Online):** Thiết bị sẵn sàng, hoạt động hoàn hảo.
  - 🟡 **Vàng (Warning/Busy):** Đang bận xử lý, nhiệt độ máy in tăng cao, hoặc giấy sắp hết (< 20 bản).
  - 🔴 **Đỏ (Error/Offline):** Mất kết nối USB, hết giấy, kẹt cửa trập máy ảnh.

### 2.10. Chuyển Đổi An Toàn Giữa Operator và Guest/Kiosk
- Trong sự kiện đông người, khách chụp (đặc biệt là trẻ em hoặc khách say bia tiệc cưới) rất dễ vô tình chạm vào các nút cấu hình làm hỏng buổi diễn.
- **Giải pháp chuyển đổi:**
  - Chuyển sang Guest: Một cú nhấp "Start Kiosk" từ Dashboard.
  - Thoát khỏi Guest về Operator: Yêu cầu **Cử chỉ góc bí mật (Long-press góc trên bên phải trong 3 giây)** hoặc chạm 5 lần liên tiếp để hiện màn hình khóa mã PIN 4 số.

---

## 3. TỔNG KẾT BÀI HỌC ÁP DỤNG CHO 1998 TEAM

```
┌────────────────────────────────────────────────────────────────────────┐
│ BÀI HỌC CỐT LÕI ĐỊNH HÌNH THIẾT KẾ MỚI                                 │
├────────────────────────────────────────────────────────────────────────┤
│ 1. BIẾN MÀN HÌNH CHÍNH THÀNH DASHBOARD VẬN HÀNH SỰ KIỆN                │
│    Mở app là thấy ngay: Sự kiện nào? Thiết bị ổn không? Sẵn sàng chưa? │
├────────────────────────────────────────────────────────────────────────┤
│ 2. TÁCH BIỆT RẠCH RÒI 2 CHẾ ĐỘ: OPERATOR & GUEST KIOSK                 │
│    Operator có buồng lái chuyên nghiệp; Guest có sân khấu tối giản.    │
├────────────────────────────────────────────────────────────────────────┤
│ 3. ĐƯA FRAME DESIGNER VỀ ĐÚNG VỊ TRÍ CÔNG CỤ PHỤ TRỢ                    │
│    Không để công cụ vẽ template chiếm sóng của quy trình vận hành.    │
├────────────────────────────────────────────────────────────────────────┤
│ 4. THAO TÁC CẢM ỨNG CHUẨN CÔNG THÁI HỌC (HIT TARGETS >= 48PX)          │
│    Nút bấm to, rõ ràng, khoảng cách an toàn, typography dễ đọc từ xa.   │
├────────────────────────────────────────────────────────────────────────┤
│ 5. BẢO VỆ 100% TÍNH NĂNG OFFLINE VÀ PHẦN CỨNG NIKON / DNP              │
│    Mọi thiết kế đều tôn vinh chất lượng DSLR và tốc độ in nhiệt dye-sub│
└────────────────────────────────────────────────────────────────────────┘
```
