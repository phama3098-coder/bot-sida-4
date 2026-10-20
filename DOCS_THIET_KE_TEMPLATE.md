# HƯỚNG DẪN THIẾT KẾ VÀ TÙY CHỈNH TEMPLATE PHOTOBOOTH (2x6 VÀ 4x6 INCH)

Template (khung ảnh) là yếu tố quyết định tính thẩm mỹ và nhận diện thương hiệu cho từng sự kiện tiệc cưới, sinh nhật hay sự kiện doanh nghiệp. **VietPhotoBooth** hỗ trợ thiết kế template với độ phân giải vật lý chuẩn **300 DPI**, đảm bảo ảnh in ra không bị vỡ hạt hay nhòe chữ.

---

## 1. KÍCH THƯỚC CHUẨN IN VẬT LÝ VÀ ĐỘ PHÂN GIẢI (300 DPI)

| Loại Template | Kích Thước Vật Lý | Độ Phân Giải Pixel (300 DPI) | Tỷ Lệ Khung Hình | Mục Đích Sử Dụng |
| :--- | :--- | :--- | :---: | :--- |
| **Dải 2x6 inch** | 5.08 x 15.24 cm | **600 x 1800 pixel** | 1:3 | Dải ảnh Photobooth dọc cổ điển (3 hoặc 4 ảnh). |
| **Dải đôi 2x6 trên khổ 4x6** | 10.16 x 15.24 cm | **1200 x 1800 pixel** | 2:3 | Chứa 2 dải 2x6 giống hệt nhau đặt cạnh nhau để dao cắt máy in nhiệt (DNP DS-RX1HS) cắt đôi tự động. |
| **Khổ 4x6 inch Dọc (Portrait)** | 10.16 x 15.24 cm | **1200 x 1800 pixel** | 2:3 | Bố cục lưới 4 ảnh (2x2) hoặc 3 ảnh kèm chân trang lớn. |
| **Khổ 4x6 inch Ngang (Landscape)** | 15.24 x 10.16 cm | **1800 x 1200 pixel** | 3:2 | Bố cục 3 ảnh ngang kèm thanh thương hiệu bên dưới. |

---

## 2. NGUYÊN TẮC VÙNG AN TOÀN (SAFE MARGINS & BLEED)

Các dòng máy in ảnh nhiệt khi in tràn lề (Borderless) luôn kéo dãn nhẹ tờ giấy khoảng **1.5% đến 2%** để đảm bảo không bị dính viền trắng ở mép giấy. Do đó:
- **Vùng cắt mép (Bleed Zone)**: Khoảng 25 - 30 pixel tính từ 4 cạnh ngoài cùng của canvas. **Không đặt chữ, logo hoặc các chi tiết quan trọng sát mép này.**
- **Vùng cắt đôi ở giữa (Center Cut Zone)**: Đối với template `1200x1800 px` ghép đôi 2 dải 2x6, dao cắt máy in sẽ chém ngay vị trí trục `x = 600 px`. Cần chừa khoảng cách an toàn ít nhất 30 pixel về mỗi bên của trục này (`x = 570 px` đến `x = 630 px`).

---

## 3. CẤU TRÚC FILE TEMPLATE JSON

Các template trong VietPhotoBooth được lưu dưới định dạng file `.json` trong thư mục:
`Documents/VietPhotoBooth/Templates/` (hoặc cấu hình riêng theo sự kiện).

### Ví dụ 1: Template dải 2x6 inch (3 ảnh)
```json
{
  "id": "strip_2x6_3photos",
  "name": "Dải Photobooth 2x6 inch (3 Ảnh)",
  "type": "2x6",
  "canvas_size": [600, 1800],
  "bg_color": "#FFFFFF",
  "text_color": "#222222",
  "slots": [
    {"x": 40, "y": 60, "w": 520, "h": 390},
    {"x": 40, "y": 480, "w": 520, "h": 390},
    {"x": 40, "y": 900, "w": 520, "h": 390}
  ],
  "text_area": {
    "title_y": 1360,
    "subtitle_y": 1450,
    "date_y": 1540,
    "footer_y": 1620
  }
}
```

### Ý nghĩa các thông số:
- `id`: Mã nhận diện duy nhất của template.
- `canvas_size`: [Chiều rộng, Chiều cao] tính bằng pixel ở 300 DPI.
- `bg_color`: Mã màu nền HEX (ví dụ `#FFFFFF` trắng, `#000000` đen, `#FFF8F0` kem).
- `slots`: Mảng chứa tọa độ các ô đặt ảnh:
  - `x`: Tọa độ góc trái bên trên theo trục ngang.
  - `y`: Tọa độ góc trái bên trên theo trục dọc.
  - `w`: Chiều rộng của khung ảnh con.
  - `h`: Chiều cao của khung ảnh con.
- `text_area`: Tọa độ trục Y để in tiêu đề sự kiện, phụ đề và ngày tháng.

---

## 4. QUY TRÌNH THIẾT KẾ BẰNG PHOTOSHOP / CANVA

Nếu bạn muốn tạo khung ảnh có hoa văn, họa tiết độc quyền theo yêu cầu của khách hàng:
1. Mở **Adobe Photoshop** hoặc **Canva**.
2. Tạo file thiết kế mới:
   - Với dải 2x6 inch: Chiều rộng **600 px**, Chiều cao **1800 px**, Độ phân giải **300 DPI**.
   - Với khổ 4x6 inch: Chiều rộng **1200 px**, Chiều cao **1800 px**, Độ phân giải **300 DPI**.
3. Thiết kế phông nền, chèn logo công ty, tên cô dâu chú rể, hoa trang trí.
4. Đục thủng các ô đặt ảnh thành trong suốt (Transparent).
5. Xuất file ảnh dưới định dạng **PNG 24-bit có kênh trong suốt (Alpha Channel)**.
6. Đặt file PNG này vào thư mục `Templates/` của sự kiện trong VietPhotoBooth để làm lớp phủ khung ảnh (Overlay Frame).
