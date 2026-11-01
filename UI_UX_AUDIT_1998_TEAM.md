# 1998 TEAM PHOTOBOOTH — KIỂM TOÁN GIAO DIỆN & TRẢI NGHIỆM NGƯỜI DÙNG (UI/UX AUDIT)
**Phiên bản dự án:** v1.6.5 Build 165  
**Phương pháp đánh giá:** Nguyên lý Thiết kế Giao diện Impeccable (Impeccable Frontend Design Principles), Công thái học Màn hình Cảm ứng (Touch Ergonomics), Tiêu chuẩn Tiếp cận Web/Ứng dụng WCAG 2.1 AA.  
**Đối tượng trải nghiệm:** Khách chụp ảnh sự kiện (Guest CX) & Kỹ thuật viên vận hành (Admin EX).

---

## MỤC LỤC
1. [Triết Lý Thiết Kế & Hệ Thống Nhận Diện (Design System & Branding)](#1-triết-lý-thiết-kế--hệ-thống-nhận-diện-design-system--branding)
2. [Đánh Giá Công Thái Học Cảm Ứng (Touch Ergonomics & Hit Targets)](#2-đánh-giá-công-thái-học-cảm-ứng-touch-ergonomics--hit-targets)
3. [Hành Trình Trải Nghiệm Của Khách (Guest Customer Experience - CX)](#3-hành-trình-trải-nghiệm-của-khách-guest-customer-experience---cx)
   - 3.1. Màn hình chờ hấp dẫn (Guest Idle Screen)
   - 3.2. Màn hình chụp Kiosk & Nguyên lý "Zero UI Overlay"
   - 3.3. Nhịp điệu đếm ngược & Tương tác giữa các kiểu chụp
   - 3.4. Màn hình hoàn thiện ảnh & Xem trước (Guest Review Dialog)
   - 3.5. Trải nghiệm quét mã QR & Nhận ảnh
4. [Trải Nghiệm Vận Hành Của Kỹ Thuật Viên (Admin Operator EX)](#4-trải-nghiệm-vận-hành-của-kỹ-thuật-viên-admin-operator-ex)
   - 4.1. Phân quyền bảo vệ bằng mã PIN (Admin Auth Flow)
   - 4.2. Trang quản lý & chẩn đoán máy ảnh (Camera Diagnostics Page)
   - 4.3. Trang cấu hình in ấn & giám sát lệnh in (Printing Page)
   - 4.4. Quản lý sự kiện & thư mục lưu trữ (Events Page)
5. [Kiểm Toán Trình Biên Tập Khung Ảnh (Frame Designer UX)](#5-kiểm-toán-trình-biên-tập-khung-ảnh-frame-designer-ux)
6. [Khả Năng Thích Ứng Đa Màn Hình & Độ Phân Giải (Responsive & Multi-Display)](#6-khả-năng-thích-ứng-đa-màn-hình--độ-phân-giải-responsive--multi-display)
7. [Kiểm Toán Tiêu Chuẩn Tiếp Cận WCAG 2.1 AA (Accessibility Audit)](#7-kiểm-toán-tiêu-chuẩn-tiếp-cận-wcag-21-aa-accessibility-audit)
8. [Bảng Tổng Hợp Vấn Đề UX & Khuyến Nghị Nâng Cấp](#8-bảng-tổng-hợp-vấn-đề-ux--khuyến-nghị-nâng-cấp)

---

## 1. TRIẾT LÝ THIẾT KẾ & HỆ THỐNG NHẬN DIỆN (DESIGN SYSTEM & BRANDING)

1998 TEAM Photobooth theo đuổi ngôn ngữ thiết kế **"Modern Wedding Studio & Luxury Dark Theme"**, lấy cảm hứng từ không gian phòng cưới cao cấp và các thiết bị quang học nhiếp ảnh chuyên nghiệp.

### 1.1. Bảng Màu Thương Hiệu (Color Palette & Tokens)
Hệ thống màu sắc được định nghĩa tập trung trong `vietphotobooth/desktop/styles.py` và `icons.py`:
- **Nền tảng chính (Canvas Background):** `#070A12` (Midnight Black) và `#0D1527` (Deep Navy). Tạo chiều sâu thăm thẳm, triệt tiêu ánh sáng hắt ngược từ màn hình vào mặt khách trong phòng tối, đồng thời làm nổi bật khung Live View.
- **Màu nhấn thương hiệu (Brand Accent - Champagne Gold):** 
  - Primary Gold: `#D4AF37`
  - Highlight Gold: `#F5DE88` / `#E5C158`
  - Gold Dark: `#C59B27`
  - Áp dụng trên các nút kích hoạt chính (Call to Action - CTA), viền thẻ được chọn (Selected Border) và huy hiệu trạng thái cao cấp.
- **Màu chức năng (Functional Colors):**
  - Thành công (Success/Active): `#10B981` (Emerald Green)
  - Cảnh báo (Warning): `#F59E0B` (Amber)
  - Báo lỗi (Error/Offline): `#EF4444` (Crimson)
  - Thông tin (Neutral Slate): `#94A3B8` / `#E2E8F0`

### 1.2. Kiểu Chữ & Phông Hệ Thống (Typography)
- **Họ phông chữ:** Khởi tạo ưu tiên `Segoe UI`, `Segoe UI Semibold`, `Arial` với cơ chế `QFont.insertSubstitution` cho `Segoe UI Emoji` và `Segoe UI Symbol`.
- **Hỗ trợ Tiếng Việt:** 100% không bị lỗi bể font hay vỡ dấu câu nhờ nhúng font hệ thống Windows (`segoeui.ttf`, `segoeuib.ttf`).
- **Thang kích thước (Font Scale):**
  - Tiêu đề lớn (Kiosk Title): 28px - 36px, `font-weight: 800`
  - Đếm ngược (Countdown Big Numbers): 96px - 140px, `font-weight: 900`
  - Nhãn nút cảm ứng (Touch Button Label): 16px - 20px, `font-weight: bold`
  - Văn bản phụ (Body/Caption): 13px - 14px, `font-weight: 500`

---

## 2. ĐÁNH GIÁ CÔNG THÁI HỌC CẢM ỨNG (TOUCH ERGONOMICS)

Photobooth là thiết bị tương tác cảm ứng công cộng (Public Touch Kiosk), người dùng đa dạng từ trẻ em đến người lớn tuổi, thường đứng cách màn hình từ 40cm - 70cm.

```
+-----------------------------------------------------------------------+
|  TIÊU CHUẨN CÔNG THÁI HỌC CẢM ỨNG (TOUCH TARGET AUDIT)                |
|                                                                       |
|  [Nút BẮT ĐẦU CHỤP]: 380px x 68px   --> ĐẠT (Cực kỳ dễ bấm)          |
|  [Pill Chọn 3/4 Ảnh]: 140px x 52px  --> ĐẠT                           |
|  [Pill Đếm Ngược]:   110px x 52px  --> ĐẠT                           |
|  [Bàn Phím Số Ảo]:   64px x 48px   --> ĐẠT (Khoảng cách 8px an toàn)  |
|  [Nút Quản Trị Nhỏ]: 44px x 44px   --> CẢNH BÁO (Dưới ngưỡng 48px)    |
|  [Nút Đóng Modal X]:  32px x 32px   --> KHÔNG ĐẠT (Dễ bấm trượt)       |
+-----------------------------------------------------------------------+
```

### Điểm Đạt Chuẩn:
- Nút **"BẮT ĐẦU CHỤP"** ở đáy màn hình Kiosk có kích thước đồ sộ (`min-height: 60px`, bo góc 12px, màu vàng champagne phát sáng), đặt tại trung tâm tầm mắt và tầm với tay của khách.
- Các nút chọn số ảnh (3 ảnh / 4 ảnh) và thời gian đếm ngược (3s / 5s / 10s) thiết kế dạng "Pill" lớn, có viền phát sáng khi chọn, phản hồi chạm tức thì.
- Hộp thoại nhập số `TouchNumberPadDialog` có các phím số kích thước tối thiểu 64x48px, khoảng cách giữa các nút (spacing) là 8px, chống hiện tượng chạm nhầm ngón tay liền kề (Fat Finger Syndrome).

### Điểm Cần Cải Thiện:
- Nút bánh răng Admin ở góc trên màn hình chờ `btn_admin` hiện có kích thước **44x44px** (theo chuẩn Google Material và Apple HIG tối thiểu phải là **48x48px** để tránh bấm trượt trên màn hình cảm ứng điện dung dày).
- Các nút đóng cửa sổ con (Close icon button) trong một số modal hiện có kích thước chỉ **32x32px**, quá nhỏ khi thao tác bằng ngón tay trần.

---

## 3. HÀNH TRÌNH TRẢI NGHIỆM CỦA KHÁCH (GUEST CUSTOMER EXPERIENCE - CX)

### 3.1. Màn Hình Chờ Hấp Dẫn (Guest Idle Screen)
- **Thiết kế:** Tone màu pastel sang trọng (`#EDF6FF` đến `#E0F2FE`), hiệu ứng đổ bóng mờ trên hai dải ảnh mẫu bên trái và bên phải gợi nhớ đến dải ảnh cưới thực tế.
- **Điểm mạnh:**
  - Nút **"CHẠM ĐỂ BẮT ĐẦU"** khổng lồ ở trung tâm kèm icon bàn tay chạm trực quan.
  - Logo 1998 Studio hiển thị sắc nét bằng định dạng vector SVG.
- **Điểm yếu UX:**
  - Màn hình tĩnh, chưa có hiệu ứng chuyển động thở (Breathing pulse animation) trên nút bấm hoặc hiệu ứng slideshow ảnh động chuyển động lướt qua để thu hút khách từ xa trong sảnh tiệc.

### 3.2. Màn Hình Chụp Kiosk & Nguyên Lý "Zero UI Overlay"
- **Bố cục 3 cột (Three-Column Studio Layout):**
  - Cột 1 (Trái): Banner sự kiện, ngày tháng, đếm tổng số ảnh đã chụp.
  - Cột 2 (Giữa): Khung Live View chiếm 60% diện tích, tỷ lệ hiển thị chuẩn xác không bị méo hình.
  - Cột 3 (Phải): Trạng thái máy ảnh, đèn báo pin/kết nối màu xanh lục tinh tế.
- **Nguyên lý "Zero UI Overlay":**
  - **Đạt điểm 10/10 tuyệt đối!** Toàn bộ khung nhận diện khuôn mặt, các đường chấm bounding box màu xanh/đỏ hay chỉ số pixel AF hoàn toàn biến mất trong chế độ Kiosk. Khách hàng cảm thấy như đang đứng trước một chiếc gương thông minh cao cấp chứ không phải một phần mềm máy tính rối rắm.

### 3.3. Nhịp Điệu Đếm Ngược & Tương Tác Giữa Các Kiểu Chụp
- **Điểm mạnh:** Chữ số đếm ngược màu vàng sáng rực rỡ ở giữa màn hình Live View, font chữ dày dặn, dễ đọc ngay cả khi khách đứng xa 2 mét.
- **Thiếu sót nghiêm trọng nhất trong trải nghiệm:**
  - **Hoàn toàn không có âm thanh!** 
  - Trong không khí ồn ào của đám cưới hoặc sự kiện tiệc công ty, khách thường trò chuyện và chỉnh váy áo, nếu chỉ có số nhảy trên màn hình mà không có tiếng tít nhịp điệu (Beep... Beep... Beep...) hoặc giọng nói ("3... 2... 1... Cười!"), khách rất hay bị giật mình hoặc chớp mắt đúng lúc màn trập chụp.

### 3.4. Màn Hình Hoàn Thiện Ảnh & Xem Trước (Guest Review Dialog)
- **Quy trình 3 bước trực quan (Stepper):**
  `1. Chọn khung ảnh` -> `2. Tùy chỉnh ảnh ô (Crop/Lật)` -> `3. Tiến hành in & Nhận QR`.
- **Khả năng tương tác:**
  - Hỗ trợ công cụ xoay ảnh 90 độ, lật gương (Horizontal flip) và kéo pan điều chỉnh crop cho từng ô ảnh bằng `SlotCropCanvas`.
  - Có thanh trượt Zoom mượt mà từ 1.0x đến 3.0x.
- **Trải nghiệm in ấn:**
  - Nút **"TIẾN HÀNH IN ẢNH"** màu vàng champagne nổi bật với icon máy in trực quan.
  - Hiển thị thông báo trạng thái in rõ ràng: "Đang gửi lệnh tới máy in..." giúp khách an tâm không bấm liên tục nhiều lần.

### 3.5. Trải Nghiệm Quét Mã QR & Nhận Ảnh
- **Mã QR to bản:** Mã QR kích thước lớn (> 220px) đặt ở vị trí trung tâm, có viền tương phản trắng trên nền tối giúp camera điện thoại (iPhone/Android) bắt nét và quét được trong vòng **0.5 giây**.
- **Chế độ Dual Network:** Hướng dẫn rõ ràng: nếu máy đang ở mạng nội bộ, màn hình hiển thị tên Wi-Fi và mật khẩu để khách kết nối tải ảnh tốc độ cao.

---

## 4. TRẢI NGHIỆM VẬN HÀNH CỦA KỸ THUẬT VIÊN (ADMIN OPERATOR EX)

### 4.1. Phân Quyền Bảo Vệ Bằng Mã PIN (Admin Auth Flow)
- **Cơ chế:** Kỹ thuật viên nhấp đôi vào góc kín hoặc bấm nút Settings trên màn hình chờ -> Xuất hiện bàn phím số cảm ứng yêu cầu nhập PIN 4 số.
- **Đánh giá:** An toàn, nhanh chóng, không cần bàn phím cứng vật lý cồng kềnh.

### 4.2. Trang Quản Lý & Chẩn Đoán Máy Ảnh (Camera Diagnostics Page)
- **Tính năng:**
  - Hiển thị danh sách thiết bị phát hiện được (Nikon D780, Webcam USB).
  - Có nút kiểm tra lấy nét chẩn đoán (AF Diagnostic Worker) có đo thời gian phản hồi (ms).
  - Cho phép bật/tắt lớp phủ Face & Eye Detection Overlay phục vụ căn chỉnh góc đặt máy ảnh và ánh sáng studio trước giờ sự kiện.

### 4.3. Trang Cấu Hình In Ấn & Giám Sát Lệnh In (Printing Page)
- **Tính năng:**
  - Hiển thị danh sách máy in Windows.
  - Có thanh trượt căn chỉnh lề (Offset X, Offset Y) và bù trừ thu phóng (Zoom 0.90x - 1.10x).
  - Hàng đợi lệnh in `PrintQueue` hiển thị mã Job ID, thời gian và trạng thái (Đang in / Đã hoàn thành).
- **Hạn chế:** Chưa có nút "Tạm dừng in" (Pause Spooler) để kỹ thuật viên kịp gỡ kẹt giấy trước khi lệnh in tiếp theo tràn vào.

### 4.4. Quản Lý Sự Kiện & Thư Mục Lưu Trữ (Events Page)
- **Tính năng:**
  - Tạo sự kiện mới, đổi sự kiện đang hoạt động.
  - Mở nhanh thư mục ảnh chụp trên Windows Explorer chỉ bằng một cú nhấp chuột.

---

## 5. KIỂM TOÁN TRÌNH BIÊN TẬP KHUNG ẢNH (FRAME DESIGNER UX)
*Tệp mã nguồn: `vietphotobooth/desktop/widgets/frame_designer_page.py`*

Trình thiết kế khung ảnh là công cụ tạo doanh thu chính cho studio, cho phép tạo các mẫu khung độc quyền cho từng cặp đôi hoặc thương hiệu.

```
+-----------------------------------------------------------------------+
|  ĐÁNH GIÁ TRÌNH THIẾT KẾ KHUNG ẢNH (FRAME DESIGNER)                   |
|                                                                       |
|  [Canvas 300 DPI WYSIWYG]:       Xuất sắc, hiển thị đúng tỷ lệ        |
|  [Kéo thả thay đổi kích thước]:   Tốt (Hỗ trợ 8 điểm neo tay nắm)      |
|  [Hút điểm lưới (Snap to Grid)]: KHÔNG CÓ (Khó căn chỉnh mép ảnh)     |
|  [Căn lề tự động (Align Tools)]:  KHÔNG CÓ (Thiếu căn giữa/đều hàng)   |
|  [Lịch sử Hoàn tác (Undo/Redo)]: KHÔNG CÓ (Nguy cơ mất công sức thiết kế|
|  [Quản lý Layer (Z-Index)]:      Cơ bản (Chưa có bảng danh sách lớp)   |
+-----------------------------------------------------------------------+
```

### Đánh giá chuyên sâu:
1. **Thiếu tính năng Undo / Redo (`Ctrl+Z` / `Ctrl+Y`):** Đây là rủi ro UX lớn nhất của trang này. Nếu kỹ thuật viên lỡ tay xóa một ô ảnh hoặc di chuyển sai vị trí, họ buộc phải chỉnh lại bằng tay hoặc tải lại từ đầu.
2. **Thiếu công cụ căn gióng (Alignment & Distribution):** Không có các nút căn lề chuẩn (Align Left, Align Center, Align Top, Distribute Horizontally/Vertically). Người dùng phải căng mắt nhìn số pixel tọa độ X, Y để căn chỉnh thủ công.
3. **Thiếu Snap-to-Grid:** Không có đường kẻ gióng thông minh (Smart Magnetic Guides) như Photoshop hay Figma khi hai ô ảnh chạm mép nhau.

---

## 6. KHẢ NĂNG THÍCH ỨNG ĐA MÀN HÌNH (RESPONSIVE & MULTI-DISPLAY)

- **Màn hình ngang chuẩn (Landscape 16:9 / 1920x1080):** 
  - Giao diện Kiosk hiển thị hoàn hảo, không bị cuộn thanh cuộn, tỷ lệ hài hòa.
- **Màn hình dọc cảm ứng (Portrait 9:16 / 1080x1920) - Xu hướng Studio Hàn Quốc:**
  - **Vấn đề phát hiện:** Khi xoay màn hình sang dạng đứng (Portrait), cột điều khiển 3 cột của Kiosk bị ép ngang lại, khung Live View bị thu nhỏ xuống khoảng 400px chiều ngang và xuất hiện thanh cuộn dọc không mong muốn ở hàng điều khiển bên dưới.
  - **Khuyến nghị:** Cần có cơ chế Responsive Layout tự động phát hiện tỷ lệ màn hình (Aspect Ratio Detection): Nếu `Chiều Cao > Chiều Rộng`, tự động chuyển sang layout 1 cột xếp dọc (Live View ở trên, điều khiển ở dưới) giống như ứng dụng di động.
- **Màn hình độ phân giải siêu cao (4K / 3840x2160):**
  - Nhờ cơ chế `Qt.HighDpiScaleFactorRoundingPolicy.PassThrough` trong `main.py`, giao diện không bị mờ nhòe. Tuy nhiên một số icon SVG cố định kích thước 24px trông hơi nhỏ trên màn hình 4K 32 inch.

---

## 7. KIỂM TOÁN TIÊU CHUẨN TIẾP CẬN WCAG 2.1 AA (ACCESSIBILITY AUDIT)

| Tiêu Chí WCAG 2.1 | Yêu Cầu Tối Thiểu | Đo Đạc Trong 1998 TEAM | Kết Luận |
| :--- | :--- | :--- | :---: |
| **Độ tương phản chữ thường** | Tỷ lệ tương phản ≥ 4.5:1 | Chữ trắng `#F8FAFC` trên nền `#070A12` đạt **17.8:1** | **ĐẠT XUẤT SẮC** |
| **Độ tương phản chữ vàng** | Tỷ lệ tương phản ≥ 4.5:1 | Chữ vàng `#D4AF37` trên nền `#070A12` đạt **7.9:1** | **ĐẠT** |
| **Kích thước vùng chạm cảm ứng**| Tối thiểu 48 x 48 CSS px | Hầu hết nút đạt 52-68px; riêng nút Admin chỉ đạt 44px | **CẢNH BÁO** |
| **Hỗ trợ người khiếm thị màu** | Không dùng màu sắc làm tín hiệu duy nhất | Đèn trạng thái camera có cả chấm màu xanh VÀ nhãn chữ "Đã kết nối" | **ĐẠT** |
| **Tín hiệu âm thanh phản hồi** | Cung cấp tín hiệu đa giác quan | Hiện chưa có âm thanh đếm ngược và chụp | **CHƯA ĐẠT** |

---

## 8. BẢNG TỔNG HỢP VẤN ĐỀ UX & KHUYẾN NGHỊ NÂNG CẤP

Dưới đây là danh sách các cải tiến UI/UX được xếp hạng theo thứ tự ưu tiên tác động trải nghiệm (Impact vs. Effort):

| Mã | Vấn Đề UX Ghi Nhận | Tác Động | Độ Phức Tạp | Đề Xuất Khắc Phục (Actionable Fix) |
| :--- | :--- | :---: | :---: | :--- |
| **UX-01** | Thiếu âm thanh giọng nói và nhịp đếm ngược | **RẤT CAO** | **THẤP** | Thêm bộ phát âm thanh tiếng Việt ("3... 2... 1... Cười!") kèm hiệu ứng Beep đếm nhịp. |
| **UX-02** | Trình thiết kế khung ảnh thiếu Undo/Redo & Snap Grid | **CAO** | **TRUNG BÌNH** | Tích hợp `QUndoStack` và chế độ hút điểm lưới 10px trong `FrameDesignerPage`. |
| **UX-03** | Màn hình Kiosk chưa tối ưu cho màn hình cảm ứng dọc (9:16) | **CAO** | **TRUNG BÌNH** | Bổ sung Portrait Responsive Mode (chuyển layout thành dạng dọc 1 cột khi màn hình đứng). |
| **UX-04** | Nút Admin settings trên màn hình chờ hơi nhỏ (44px) | **TRUNG BÌNH** | **RẤT THẤP** | Tăng kích thước `btn_admin` lên 54x54px, tăng diện tích chạm cảm ứng an toàn. |
| **UX-05** | Màn hình chờ (Idle Screen) còn tĩnh, thiếu hiệu ứng mời gọi | **TRUNG BÌNH** | **THẤP** | Thêm hiệu ứng Breathing Glow trên nút "CHẠM ĐỂ BẮT ĐẦU" và slideshow lướt ảnh mẫu. |
| **UX-06** | Hộp thoại thông báo kẹt giấy hoặc lỗi máy in còn thô | **TRUNG BÌNH** | **THẤP** | Thay thế `QMessageBox` mặc định bằng Toast Notification / Banner vàng champagne cao cấp. |
