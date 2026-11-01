# 1998 TEAM PHOTOBOOTH — CONCEPT C: PROFESSIONAL BOOTH CONTROL
## Hướng Thiết Kế C: Trạm Điều Khiển Tác Nghiệp Vận Hành Cao Độ (Mission-Control Cockpit)

> **Mã thiết kế:** `CONCEPT-C`  
> **Tên gọi:** Professional Booth Control  
> **Khí chất (Vibe):** Vững chãi, thực dụng, sắc bén, kiểm soát tuyệt đối, độ tin cậy công nghiệp (Industrial Reliability).

---

## 1. TRIẾT LÝ THỊ GIÁC & CẢM XÚC (VISUAL PHILOSOPHY)

Concept C được thiết kế dành riêng cho các **Đơn Vị Cho Thuê Photobooth Chuyên Nghiệp** và các nhà vận hành kỹ thuật cần chạy booth liên tục 24/7 tại các sự kiện quy mô hàng ngàn lượt khách. Triết lý thiết kế tối thượng ở đây là: **Thông tin hiển thị dày đặc, trạng thái phần cứng minh bạch tức thì, không màu mè hoa mỹ, thao tác nhanh chuẩn xác như trạm kiểm soát không lưu**.

```
BẢNG MÀU CHỦ ĐẠO (CONCEPT C):
┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
│ Primary Background      │ Surface / Control Dark  │ Tactical Electric Blue  │
│ #121316 (Charcoal Black)│ #181A20 (Graphite Card) │ #3B82F6 (Telemetry Blue)│
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Status LED Online       │ Status LED Warning      │ Status LED Fault        │
│ #10B981 (Emerald Green) │ #F59E0B (Amber Alert)   │ #EF4444 (Critical Red)  │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

---

## 2. QUY CHUẨN ĐỒ HỌA CHI TIẾT

### 2.1. Nghệ Thuật Chữ (Typography)
- Phông chữ kỹ thuật hiện đại không chân **BeVietnam Pro** kết hợp chữ số dạng đơn khoảng cách (Monospace Numbers: `font-variant-numeric: tabular-nums`).
- Mọi con số chỉ số (Số giây đếm ngược, Lượng giấy còn lại, Tốc độ in, Nhiệt độ đầu in, Bộ đếm phiên) đều được căn lề thẳng hàng tăm tắp, chống hiện tượng nhảy số gây giật mắt.

### 2.2. Xử Lý Bề Mặt, Thẻ Card & Đường Viền
- Bề mặt card sử dụng tông xám than đậm dập nổi nhẹ (`border: 1px solid #2B2F3A`).
- Bo góc vừa phải dứt khoát (`8px – 10px`), tối ưu hóa tối đa diện tích hiển thị để không lãng phí từng pixel màn hình.
- Các đèn tín hiệu phần cứng (Hardware Status LED) có hiệu ứng phát sáng nhấp nháy thực tế, người vận hành chỉ cần liếc mắt 0.1 giây là biết thiết bị nào đang gặp trục trặc.

### 2.3. Cấu Trúc Khung Ngắm (Live View & Sân Khấu Kiosk)
- Khung Live View tích hợp thanh đo tín hiệu kỹ thuật xung quanh: Mức pin Nikon D780, số shot còn lại trong thẻ nhớ, vạch thước cân bằng điện tử.
- Nút Shutter to bản thiết kế dạng nút bấm công nghiệp (Industrial Push Button) màu xanh điện quang (Electric Blue), mang lại cảm giác bấm dứt khoát, chắc chắn.
- Màn hình Kiosk chuyển sang giao diện tối giản tối đa: Khung hình chiếm trọn tâm điểm, loại bỏ mọi yếu tố gây xao nhãng để đẩy nhanh tốc độ xoay vòng khách tại booth.

---

## 3. MỤC TIÊU PHÙ HỢP & BỐI CẢNH ỨNG DỤNG

- **Các sự kiện kích hoạt thương hiệu cường độ cao (High-Volume Brand Activations):** Nơi photobooth phải chụp 300–500 phiên/ngày không ngừng nghỉ.
- **Hệ thống photobooth nhượng quyền hoặc cho thuê tự động (Franchise Kiosks):** Nơi nhân viên vận hành chỉ cần theo dõi các chỉ số cảnh báo giấy mực và lỗi kẹt giấy.
- **Các triển lãm công nghệ, hội chợ Expo:** Hòa hợp hoàn hảo với không gian công nghệ số và thiết bị điện tử tối tân.

---

## 4. ĐÁNH GIÁ ĐIỂM MẠNH & HẠN CHẾ

### Điểm mạnh:
- Khả năng kiểm soát và giám sát phần cứng tốt nhất trong cả 3 concept; phát hiện lỗi tiềm ẩn từ rất sớm (hết giấy, nóng máy, mất tín hiệu USB).
- Tốc độ thao tác cực kỳ nhanh, mật độ thông tin cao giúp kỹ thuật viên làm chủ hoàn toàn tình huống.
- Tiết kiệm điện năng và không gây mỏi mắt khi vận hành trong ca trực kéo dài nhiều giờ.

### Hạn chế:
- Vẻ ngoài có phần cơ khí, kỹ thuật; ít lãng mạn hơn khi đặt trong không gian tiệc cưới hoa lệ.
- Cần nhân viên có chút kiến thức kỹ thuật để khai thác hết các số liệu hiển thị.
