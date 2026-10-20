# HƯỚNG DẪN SAO LƯU, PHỤC HỒI, CẬP NHẬT VÀ GỠ CÀI ĐẶT

Tài liệu này hướng dẫn quy trình bảo toàn dữ liệu sự kiện, sao lưu định kỳ, cập nhật phiên bản mới và gỡ cài đặt phần mềm **VietPhotoBooth**.

---

## 1. NGUYÊN TẮC BẢO TOÀN DỮ LIỆU

VietPhotoBooth tách biệt hoàn toàn giữa **Mã nguồn phần mềm**, **File cấu hình hệ thống** và **Dữ liệu sự kiện**:
- **File cấu hình hệ thống**: Được lưu tại `%LOCALAPPDATA%\VietPhotoBooth\config.json`. File này **không bao giờ bị xóa** khi cập nhật phần mềm hoặc gỡ cài đặt.
- **Thư mục ảnh sự kiện**: Mặc định lưu tại `C:\Users\<Tên_User>\Documents\VietPhotoBooth\Events\`. Bạn có thể thay đổi đường dẫn này sang bất kỳ ổ cứng di động, ổ D: hoặc ổ E: nào trong phần Cài đặt.
- **Cập nhật ứng dụng**: Khi chạy bộ cài bản mới, toàn bộ ảnh cũ, sự kiện cũ và cài đặt mã PIN đều được giữ nguyên 100%.

---

## 2. QUY TRÌNH SAO LƯU DỮ LIỆU SỰ KIỆN

### 2.1. Xuất file ZIP sự kiện tức thì từ giao diện Quản trị
Đây là cách nhanh nhất để bàn giao toàn bộ ảnh cho khách hàng ngay khi tiệc kết thúc:
1. Vào **Quản Trị** (Mã PIN: `1234`).
2. Chọn mục **🎉 Quản Lý Sự Kiện**.
3. Tại bảng danh sách sự kiện, tìm sự kiện vừa kết thúc (ví dụ `DamCuoi_MinhLinh`).
4. Bấm nút **"Xuất ZIP"**.
5. Hệ thống sẽ tự động đóng gói toàn bộ ảnh gốc (`Originals/`) và ảnh thành phẩm (`Final/`) thành 1 file ZIP duy nhất và tải về máy tính. Bạn có thể copy file ZIP này vào USB để trao cho khách hàng.

### 2.2. Sao lưu toàn bộ thư mục dữ liệu thủ công
Để lưu trữ dài hạn sau mùa sự kiện:
1. Đóng ứng dụng VietPhotoBooth.
2. Mở File Explorer, truy cập vào thư mục:
   `C:\Users\<Tên_User>\Documents\VietPhotoBooth\`
3. Copy toàn bộ thư mục `VietPhotoBooth` sang ổ cứng gắn ngoài (External HDD) hoặc dịch vụ lưu trữ đám mây (Google Drive, OneDrive).

---

## 3. PHỤC HỒI DỮ LIỆU (RESTORE)

Khi chuyển sang máy tính mới hoặc cài lại hệ điều hành Windows:
1. Cài đặt lại phần mềm bằng file `VietPhotoBooth-Setup.exe`.
2. Copy thư mục `VietPhotoBooth` đã sao lưu trước đó dán trở lại vào thư mục:
   `C:\Users\<Tên_User>\Documents\VietPhotoBooth\`
3. Khởi động VietPhotoBooth. Phần mềm sẽ tự động nhận diện lại toàn bộ các sự kiện cũ, danh sách ảnh đã chụp và cấu hình in ấn mà không cần thiết lập lại.

---

## 4. QUY TRÌNH CẬP NHẬT PHIÊN BẢN MỚI (UPDATE)

Khi có bản nâng cấp (ví dụ từ v1.0 lên v1.1):
1. Tải file `VietPhotoBooth-Setup.exe` của phiên bản mới.
2. Đóng phiên bản VietPhotoBooth đang chạy (nếu có).
3. Nhấp đúp chuột chạy file `VietPhotoBooth-Setup.exe` mới.
4. Trình cài đặt sẽ tự động nâng cấp các file nhị phân của phần mềm mà không can thiệp vào thư mục ảnh và file cấu hình.
5. Sau khi cài xong, mở lại phần mềm để tiếp tục sử dụng.

---

## 5. HƯỚNG DẪN GỠ CÀI ĐẶT (UNINSTALL)

Nếu không còn nhu cầu sử dụng phần mềm trên máy tính:
1. Vào **Windows Settings -> Apps -> Installed apps** (hoặc Control Panel -> Programs and Features).
2. Tìm ứng dụng có tên **VietPhotoBooth**.
3. Bấm **Uninstall** (Gỡ cài đặt).
4. Trình gỡ cài đặt chính thức (`unins000.exe`) sẽ xóa sạch các file thực thi, biểu tượng Desktop và Start Menu.
5. **Dữ liệu ảnh của bạn trong thư mục Documents/VietPhotoBooth vẫn được giữ an toàn**, đảm bảo bạn không bị mất các bức ảnh quý giá của sự kiện đã qua.
