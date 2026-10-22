# QUY TẮC PHÁT TRIỂN & PHÁT HÀNH DỰ ÁN 1998 TEAM — PHOTOBOOTH

## BẮT BUỘC: CẬP NHẬT PHIÊN BẢN VÀ BUILD MỚI MỖI LẦN SỬA ĐỔI

Theo chỉ đạo bắt buộc của người dùng:
**Mỗi lần thực hiện bất kỳ sửa đổi nào vào mã nguồn (sửa lỗi, thêm chức năng, cải tiến giao diện UI/UX, tối ưu hiệu năng)**:

### 1. Tăng Phiên Bản và Số Build (Single Source of Truth)
- Luôn cập nhật trong tệp `vietphotobooth/version.py`:
  - `__version__`: Cập nhật theo chuẩn Semantic Versioning (ví dụ: `1.2.1` -> `1.2.2` hoặc `1.3.0` tùy mức độ sửa đổi).
  - `__build__`: Luôn tăng số build number (ví dụ: `121` -> `122`).
  - `__release_date__`: Cập nhật ngày phát hành hiện tại (định dạng `YYYY-MM-DD`).
- Không để tồn tại các chuỗi phiên bản hardcode rời rạc ngoài tệp này.

### 2. Xác Minh Toàn Bộ Bài Test
- Chạy toàn bộ bộ kiểm thử: `py -3.12 -m pytest`.
- Đảm bảo 100% test pass và mã thoát trả về 0.

### 3. Đóng Gói Bộ Cài Đặt Mới Sau Khi Sửa
- Chạy script đóng gói tự động: `py -3.12 build_release.py`.
- Tên bộ cài phải tuân theo quy tắc: `1998-TEAM-Setup-v{__version__}-Build{__build__}.exe`.
- Tuyệt đối không xóa hoặc ghi đè làm mất các bản cài đặt cũ trong thư mục `dist_installer/`.
- Tạo kèm file checksum `.sha256`.

### 4. Báo Cáo Người Dùng
- Luôn báo cáo rõ ràng:
  - Số phiên bản mới và build mới.
  - Tên file bộ cài và đường dẫn trong `dist_installer/`.
  - Dung lượng file và mã băm SHA-256.
