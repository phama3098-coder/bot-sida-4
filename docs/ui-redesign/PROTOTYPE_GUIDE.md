# 1998 TEAM PHOTOBOOTH — PROTOTYPE TESTING GUIDE (ROUND 2.1 REFINED)
## Hướng Dẫn Khảo Sát & Kiểm Thử Bản Mẫu Tương Tác Hoàn Thiện v2.1

> **Bản mẫu tương tác:** `docs/ui-redesign/PROTOTYPE/index.html`  
> **Độ phân giải tham chiếu:** 1920×1080 (Chuẩn màn hình Kiosk tỷ lệ 16:9)  
> **Khởi chạy tức thì:** Mở trực tiếp trên Chrome hoặc Edge không cần cài đặt  
> **Đường dẫn tuyệt đối:** [index.html](file:///c:/Users/Admin/Documents/photobooth/docs/ui-redesign/PROTOTYPE/index.html)

---

## 1. CÁCH KHỞI CHẠY BẢN MẪU TƯƠNG TÁC

Chủ dự án có thể mở bản mẫu theo 2 cách đơn giản:
- **Cách 1 (Nhanh nhất):** Nhấp chuột trực tiếp vào liên kết tệp [index.html](file:///c:/Users/Admin/Documents/photobooth/docs/ui-redesign/PROTOTYPE/index.html) trên trình duyệt Google Chrome hoặc Microsoft Edge.
- **Cách 2 (Khởi chạy máy chủ cục bộ Python):**
  ```bash
  py -3.12 -m http.server 8090 --directory docs/ui-redesign/PROTOTYPE
  ```
  Sau đó mở địa chỉ: `http://localhost:8090` trên trình duyệt.

---

## 2. KỊCH BẢN KIỂM THỬ 1: SLOT-BASED RETAKE VỚI 4 ẢNH MINH HỌA RIÊNG BIỆT

Đây là tính năng trọng tâm đã được nâng cấp triệt để trong Round 2.1:

1. **Khởi động phiên Kiosk:**
   - Tại giao diện Buồng Lái Vận Hành, bấm nút màu vàng **`🚀 BẮT ĐẦU PHOTOBOOTH (F11)`**.
   - Màn hình chuyển sang chế độ khách chụp Kiosk toàn màn hình (Tông sáng ấm tiệc cưới thân thiện).
2. **Tiến hành chụp 4 tư thế với Pose Guidance:**
   - Chạm vào nút lớn **`👉 CHẠM ĐỂ CHỤP NGAY`**.
   - Viewfinder xuất hiện kèm **Hộp Hướng Dẫn Tư Thế (Pose Guidance Box)** phía dưới màn hình:
     - Shot 1: `👋 Tư thế 1: Vẫy tay chào bạn bè` (Nụ cười rạng rỡ và bàn tay vẫy chào)
     - Shot 2: `🫰 Tư thế 2: Bắn tim nhí nhảnh` (Tạo hình ngón tay bắn tim siêu ngọt ngào)
     - Shot 3: `😄 Tư thế 3: Cười thật tươi rạng rỡ` (Cười hết cỡ khoe trọn nụ cười xinh)
     - Shot 4: `✌️ Tư thế 4: Tạo dáng V-Sign cá tính` (Giơ 2 ngón tay chữ V phong cách Hàn Quốc)
   - Mỗi shot đếm ngược 3s có âm thanh giọng đọc tiếng Việt, tiếng bíp và tiếng trập cơ khí Nikon.
3. **Màn hình Review với 4 ảnh khác nhau hoàn toàn:**
   - Sau khi chụp xong shot 4, màn hình chuyển sang **Xem Lại Ảnh (Review)** hiển thị dải 4 ô.
   - **Xác minh trực quan:** 4 ô ảnh mang 4 màu nền và tư thế nhân vật hoàn toàn khác nhau:
     - Ô 1: Vẫy tay chào (Nền cam đào, nhãn `Ô #1 • ẢNH GỐC`).
     - Ô 2: Bắn tim nhí nhảnh (Nền hồng rose, nhãn `Ô #2 • ẢNH GỐC`).
     - Ô 3: Cười tươi rạng rỡ (Nền vàng nắng, nhãn `Ô #3 • ẢNH GỐC`).
     - Ô 4: Tạo dáng V-Sign (Nền tím lavender, nhãn `Ô #4 • ẢNH GỐC`).
4. **Thực hiện chụp lại riêng Ô #2 (Slot Retake):**
   - Nhấp vào nút **`🔄 Chụp Lại Ô #2`** ngay trên ô số 2.
   - Live View mở ra kèm biểu ngữ đỏ:  
     `🔄 ĐANG CHỤP LẠI RIÊNG Ô SỐ 2 (CÁC Ô 1, 3, 4 ĐƯỢC BẢO TOÀN NGUYÊN VẸN)`  
     và Pose Guidance cập nhật: `😉 Tư thế 2 mới: Nháy mắt cá tính & Chu môi`.
   - Sau khi đếm ngược 3s và chụp: Hệ thống đưa trở lại màn hình Review:
     - **Ô số 2** lập tức được thay thế bằng hình ảnh tư thế nháy mắt mới (Nền xanh ngọc emerald) kèm nhãn nổi bật:  
       `★ ĐÃ CHỤP LẠI (SLOT #2) ★`.
     - **Các ô #1, #3, #4** được bảo toàn nguyên vẹn 100%, không bị xáo trộn, xoay vòng hay mất ảnh!
     - **Bảng kiểm định phía dưới (Slot Audit Status)** khẳng định rõ:
       - Ô #1: `[ẢNH GỐC - BẢO TOÀN]` (Vẫy tay chào)
       - Ô #2: `[ĐÃ CHỤP LẠI - CẬP NHẬT]` (Bắn Tim ➜ Nháy Mắt)
       - Ô #3: `[ẢNH GỐC - BẢO TOÀN]` (Cười tươi)
       - Ô #4: `[ẢNH GỐC - BẢO TOÀN]` (Tạo dáng V-Sign)

---

## 3. KỊCH BẢN KIỂM THỬ 2: THỬ NGHIỆM TRẠNG THÁI CAMERA & MÁY IN

1. **Tại trang Capture Studio (Buồng Chụp Kỹ Thuật):**
   - Quan sát thanh công cụ **`⚡ THỬ TRẠNG THÁI CAMERA`**.
   - Bấm thử lần lượt 6 trạng thái để xem phản hồi trực quan đa kênh:
     - `✓ Connected` ➜ Sẵn sàng chụp, đèn xanh lá.
     - `⏳ Connecting` ➜ Đang bắt tay giao thức PTP USB 3.0.
     - `⚡ Busy` ➜ Đang chụp / xả buffer thẻ SD.
     - `⚠️ Warning` ➜ Cảnh báo nhiệt độ cảm biến cao hoặc pin dưới 15%.
     - `✕ Error` ➜ Báo lỗi trập cơ hoặc thẻ nhớ bị khóa write-protect.
     - `✕ Disconnected` ➜ Báo mất cáp USB kết nối máy ảnh.
2. **Tại trang Printing Center (Trung Tâm In Ấn):**
   - Quan sát thanh công cụ **`⚡ THỬ TRẠNG THÁI MÁY IN`**.
   - Bấm thử lần lượt 4 trạng thái máy in nhiệt DNP DS-RX1HS:
     - `✓ Ready` ➜ Sẵn sàng nhận lệnh in.
     - `⚠️ Out of Paper` ➜ Hết cuộn giấy in 4x6 (Đồng hồ báo đỏ).
     - `✕ Spooler Error` ➜ Lỗi dịch vụ hàng đợi in Print Spooler của Windows.
     - `✕ Disconnected` ➜ Mất cáp USB máy in nhiệt.

---

## 4. KỊCH BẢN KIỂM THỬ 3: BẢO MẬT KIOSK ĐA TẦNG (PIN MASKED & LOCKOUT)

1. **Thao tác bí mật mở bàn phím PIN:**
   - Trong khi đang ở chế độ Kiosk, nhấp nhanh liên tục 3 lần vào góc trên cùng bên phải màn hình (hoặc nhấn phím `F11`).
   - Hộp thoại **"Xác Thực Quản Trị Viên"** xuất hiện với 4 dấu chấm tròn mã hóa `••••`.
2. **Thử nghiệm nhập sai mã PIN:**
   - Bấm thử mã số sai, ví dụ: `1 - 2 - 3 - 4`.
   - Quan sát: Các dấu chấm tròn rung lắc mạnh mẽ (Shake animation) và hiển thị cảnh báo đỏ.
   - Nhập sai tiếp lần 2 và lần 3: Hệ thống lập tức kích hoạt **Khóa an toàn 30 giây**:  
     `🔒 ĐÃ KHÓA AN TOÀN: Vui lòng chờ 30s... 29s...` đồng thời vô hiệu hóa toàn bộ bàn phím.
3. **Thử nghiệm nhập đúng mã PIN & Hộp thoại xác nhận:**
   - Khi bàn phím mở lại, bấm đúng mã PIN mặc định: **`1 - 9 - 9 - 8`**.
   - Hộp thoại xác nhận xuất hiện: `Xác Nhận Thoát Chế Độ Kiosk?`.
   - Bấm nút **`🚪 XÁC NHẬN THOÁT SANG OPERATOR`** để trở về Buồng Lái Vận Hành.

---

## 5. THAM SỐ URL HỖ TRỢ TEST TỰ ĐỘNG (QUERY PARAMS)

Bản mẫu hỗ trợ các query params trên URL để nhảy thẳng tới bất kỳ màn hình nào:
- `?theme=hybrid&view=dashboard`: Mở trực tiếp Dashboard vận hành.
- `?theme=hybrid&view=capture`: Mở trực tiếp Capture Studio buồng chụp.
- `?theme=hybrid&mode=kiosk&stage=idle`: Mở màn hình Kiosk Welcome chào khách.
- `?theme=hybrid&mode=kiosk&stage=countdown`: Mở màn hình Viewfinder đang đếm ngược chụp lại ô số 2.
- `?theme=hybrid&mode=kiosk&stage=review`: Mở màn hình Review dải 4 ô với ô 2 đã chụp lại.
- `?theme=hybrid&view=printing`: Mở Trung tâm Quản lý Máy In DNP.
- `?theme=hybrid&view=devices`: Mở Giám sát Chẩn đoán Thiết bị.
