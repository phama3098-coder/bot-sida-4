# 1998 TEAM PHOTOBOOTH — HYBRID DESIGN SYSTEM SPECIFICATION (ROUND 2)
## Quy Chuẩn Thiết Kế Lai Ghép (Hybrid Tokens, Components & Telemetry)

> **Tài liệu:** Đặc tả kỹ thuật Design Tokens & Thành phần giao diện v2.0  
> **Quy chuẩn:** Hybrid Direction (Operator: Concept A | Kiosk: Concept B | Status: Concept C)  
> **Khả năng tiếp cận:** WCAG 2.1 Level AA, Touchscreen Ergonomics Compliant

---

## 1. NỀN TẢNG THIẾT KẾ LAI GHÉP (HYBRID TOKENS)

### 1.1. Bảng Màu Không Gian Kép (Dual-Space Palette)

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. BUỒNG LÁI OPERATOR (CONCEPT A — PREMIUM STUDIO)                     │
├───────────────────────┬────────────────────────┬───────────────────────┤
│ Background Deep       │ Card Surface           │ Brand Accent Gold     │
│ #0B0F19 (Obsidian)    │ #151D2A (Midnight)     │ #D4AF37 (Champagne)   │
├───────────────────────┼────────────────────────┼───────────────────────┤
│ Text Primary          │ Text Secondary         │ Divider Line          │
│ #F8FAFC (Ivory)       │ #94A3B8 (Cool Slate)   │ rgba(212,175,55,0.2)  │
└───────────────────────┴────────────────────────┴───────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ 2. SÂN KHẤU KIOSK KHÁCH CHỤP (CONCEPT B — MODERN EVENT)                │
├───────────────────────┬────────────────────────┬───────────────────────┤
│ Background Canvas     │ Card Surface           │ Brand Accent Rose     │
│ #F8FAFC (Warm Pearl)  │ #FFFFFF (Pure White)   │ #E11D48 (Coral Rose)  │
├───────────────────────┼────────────────────────┼───────────────────────┤
│ Secondary Accent      │ Text Primary           │ Focus Ring            │
│ #8B5CF6 (Lavender)    │ #0F172A (Charcoal)     │ #FFE4E6 (Rose Glow)   │
└───────────────────────┴────────────────────────┴───────────────────────┘
```

---

## 2. HỆ THỐNG TRẠNG THÁI PHẦN CỨNG ĐA KÊNH (CONCEPT C TELEMETRY)

Tuân thủ nguyên tắc không dựa vào màu sắc làm tín hiệu duy nhất: Mọi chỉ báo trạng thái thiết bị đều bao gồm **4 lớp thông tin đồng thời**:
1. **Biểu tượng hình học (Icon):** `✓`, `⟳`, `⚠`, `✕`, `⏻`.
2. **Nhãn văn bản rõ ràng (Textual Badge):** `CONNECTED`, `BUSY`, `WARNING`, `ERROR`, `DISCONNECTED`.
3. **Màu sắc & Độ tương phản:** Đạt chuẩn WCAG AA trên cả nền sáng lẫn nền tối.
4. **Thông số kỹ thuật đi kèm:** % Pin, Nhiệt độ °C, Số bản in còn lại.

| Trạng thái | Icon | Nhãn văn bản | Màu nền badge | Màu chữ & viền | Ý nghĩa thực tế |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **Sẵn sàng** | `✓` | `CONNECTED` / `READY` | `rgba(16, 185, 129, 0.15)` | `#10B981` | Thiết bị online, sẵn sàng phục vụ |
| **Đang bận** | `⟳` | `BUSY / COOLING` | `rgba(59, 130, 246, 0.15)` | `#38BDF8` | Đang nạp lệnh, làm mát đầu in DNP |
| **Cảnh báo** | `⚠` | `WARNING / PAPER LOW` | `rgba(245, 158, 11, 0.15)` | `#F59E0B` | Giấy sắp hết (<20 bản), nhiệt độ tăng |
| **Lỗi** | `✕` | `ERROR / CHECK DEVICE`| `rgba(239, 68, 68, 0.18)` | `#EF4444` | Kẹt giấy, mất kết nối USB máy ảnh |
| **Ngắt kết nối**| `⏻`| `DISCONNECTED` | `rgba(148, 163, 184, 0.12)`| `#94A3B8` | Thiết bị tắt nguồn hoặc chưa cắm cáp |

---

## 3. THÀNH PHẦN SLOT RETAKE (SLOT-BASED RETAKE COMPONENT)

- **Cấu trúc dải ảnh 4 ô:** Mỗi ô ảnh con là một đối tượng độc lập có thuộc tính:
  - `slot_num`: Số thứ tự từ 1 đến 4.
  - `is_retaken`: Cờ boolean đánh dấu ô này có vừa được chụp lại hay không.
  - `timestamp`: Thời gian ghi nhận shot.
- **Nút chụp lại ô con (Overlay Button):**
  - Đặt tại góc trên bên phải của từng ô ảnh: `🔄 Chụp lại ô #X`.
  - Kích thước vùng bấm tối thiểu 44×28px bo tròn dạng pill (`rounded-full`), có hiệu ứng đổ bóng chống chìm trên mọi phông nền ảnh.
- **Biểu ngữ chỉ dẫn khi Retake (Retake HUD Banner):**
  - Khi bắt đầu chụp lại ô con, trên khung Live View xuất hiện dải biểu ngữ màu đỏ hồng san hô:  
    `🔄 ĐANG CHỤP LẠI RIÊNG Ô SỐ X (CÁC Ô CÒN LẠI ĐƯỢC BẢO TOÀN NGUYÊN VẸN)`
  - Đảm bảo người dùng biết chắc chắn các ô ảnh đẹp khác không bị xóa mất.

---

## 4. QUY CHUẨN BẢO MẬT KIOSK (KIOSK SECURITY COMPONENT)

- **Điểm chạm bí mật:** Vùng cảm ứng vô hình kích thước 90×90px đặt tại góc trên cùng bên phải màn hình Kiosk. Yêu cầu **3 lần chạm nhanh liên tiếp trong 1.2 giây** hoặc **nhấn giữ 3 giây**.
- **Bàn phím số mã PIN:**
  - 4 dấu chấm tròn hiển thị mật mã (`••••`).
  - Khi nhập sai: Các dấu chấm chuyển màu đỏ và rung lắc (Shake animation 400ms), hiển thị thông báo: `❌ Mã PIN không đúng! Đã thử sai X/3 lần.`
  - Khi sai quá 3 lần: Kích hoạt bộ đếm khóa an toàn (Lockout countdown) trong 30 giây, tạm thời vô hiệu hóa bàn phím số.
- **Hộp thoại xác nhận thoát:**
  - Ngăn ngừa việc nhân viên nhập đúng PIN nhưng vô tình chuyển tab khi khách chưa rời khỏi buồng chụp.
  - Yêu cầu xác nhận lần 2: `Xác nhận thoát ra Buồng Lái Operator?`
