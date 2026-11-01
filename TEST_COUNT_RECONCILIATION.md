# BÁO CÁO ĐỐI SOÁT CHÊNH LỆCH TEST SUITE: 306/306 VS 309/309
## DỰ ÁN: 1998 TEAM — PHOTOBOOTH (v1.6.6 Build 166)
**Thời gian thực hiện:** 2026-11-01 20:05:00 +07:00  
**Tác giả:** Đội ngũ Kỹ thuật & Kiểm thử Antigravity  
**Mục tiêu:** Xác định chính xác 100% nguyên nhân chênh lệch giữa số lượng 309 tests (trong các báo cáo trước) và 306 tests (hiện tại); kiểm tra tính toàn vẹn của toàn bộ mã nguồn kiểm thử.

---

### 1. TỔNG QUAN KẾT QUẢ ĐỐI SOÁT

| Chỉ tiêu | Giá trị trước đây | Giá trị hiện tại | Chênh lệch |
| :--- | :---: | :---: | :---: |
| **Tổng số test phát hiện (Collected)** | 309 | 306 | -3 tests |
| **Số test thuộc `vietphotobooth/tests`** | 306 | 306 | **0 (Nguyên vẹn 100%)** |
| **Số test ngoài dự án (External Skill Fixtures)** | 3 | 0 (đã cách ly) | -3 tests |
| **Số test bị xóa / sửa tên / vô hiệu hóa** | 0 | 0 | **0** |
| **Tỷ lệ Pass trong `vietphotobooth/tests`** | 100% (306/306) | 100% (306/306) | **0% lỗi** |

> [!IMPORTANT]
> **KẾT LUẬN CỐT LÕI:**  
> Không có bất kỳ bài test nào thuộc hệ thống 1998 TEAM Photobooth bị xóa, bị bỏ qua, bị đổi tên hay bị tắt.  
> Đúng 3 bài test chênh lệch thuộc về thư mục fixture đánh giá kỹ năng ngoài: `agent-skills/evals/fixtures/test-driven-development-ecosystem/test_ledger.py`.

---

### 2. CHI TIẾT 3 BÀI TEST CHÊNH LỆCH

Khi chạy lệnh thu thập không giới hạn phạm vi thư mục trên toàn workspace:
```powershell
py -3.12 -m pytest agent-skills/evals/fixtures/test-driven-development-ecosystem/test_ledger.py --collect-only
```

Pytest thu thập được chính xác 3 bài test:
1. `agent-skills/evals/fixtures/test-driven-development-ecosystem/test_ledger.py::ApplyEntriesTest::test_applies_a_single_credit`
2. `agent-skills/evals/fixtures/test-driven-development-ecosystem/test_ledger.py::ApplyEntriesTest::test_applies_multiple_credits_in_order`
3. `agent-skills/evals/fixtures/test-driven-development-ecosystem/test_ledger.py::ApplyEntriesTest::test_rejects_unknown_entry_kinds`

#### Nguồn gốc của 3 test này:
- Tại đầu phiên làm việc (Yêu cầu 1), người dùng chỉ thị nạp các bộ công cụ kỹ năng mở rộng:
  - *REA – Reverse Engineer Anything*
  - *Impeccable*
  - *Addy Osmani Agent Skills*
- Quá trình cài đặt đã đưa thư mục `agent-skills/` vào thư mục làm việc của workspace.
- Trong bộ `Addy Osmani Agent Skills`, có fixture đánh giá kỹ năng `test-driven-development-ecosystem` chứa file mẫu kế toán `test_ledger.py`.
- Trước khi tạo `pytest.ini`, lệnh `py -3.12 -m pytest` quét toàn bộ đệ quy thư mục gốc và vô tình thu thập luôn 3 test mẫu của Agent Skill:
  $$\text{306 tests (Photobooth)} + \text{3 tests (Skill Fixture)} = \mathbf{309\text{ tests}}.$$

---

### 3. DANH SÁCH CHI TIẾT 37 FILE VÀ 306 TEST CỦA 1998 TEAM PHOTOBOOTH

Toàn bộ 306 tests thuộc thư mục `vietphotobooth/tests/` được bảo toàn nguyên vẹn 100%:

| STT | File Kiểm Thử | Số Lượng Test | Nội Dung & Phạm Vi |
| :---: | :--- | :---: | :--- |
| 1 | `test_af_diagnostic_worker.py` | 4 | Worker chẩn đoán AF và Watchdog |
| 2 | `test_camera.py` | 3 | Camera Manager & DirectShow switching |
| 3 | `test_camera_connection_manager.py` | 9 | Connection Manager, PnP discovery |
| 4 | `test_camera_diagnostics_and_sources.py` | 14 | Quét nguồn video và xuất báo cáo |
| 5 | `test_config.py` | 1 | Quản lý cấu hình ConfigManager |
| 6 | `test_desktop_gui.py` | 10 | Giao diện Desktop MainWindow & Frame Designer |
| 7 | `test_digicam_connection.py` | 11 | digiCamControl fallback backend |
| 8 | `test_events.py` | 1 | Quản lý cấu trúc sự kiện |
| 9 | `test_face_eye_af_controller.py` | 13 | Unified Face/Eye AF Controller |
| 10 | `test_face_eye_af_pipeline_sync.py` | 12 | Đồng bộ hóa pipeline nhận diện khuôn mặt và AF |
| 11 | `test_filters_and_luts.py` | 4 | Bộ lọc màu LUT và hiệu ứng ảnh |
| 12 | `test_frames_and_designer.py` | 14 | Frame Manager và Designer |
| 13 | `test_gdrive_cloud.py` | 4 | Đồng bộ Google Drive |
| 14 | `test_guest_review.py` | 8 | Màn hình Review ảnh cho khách |
| 15 | `test_hotfix_v140_verification.py` | 5 | Kiểm thử hotfix v1.4.0 |
| 16 | `test_kiosk_face_eye_af_capture.py` | 17 | Kiosk tích hợp Face/Eye AF và chụp ảnh |
| 17 | `test_kiosk_in_window_review.py` | 7 | Kiosk In-Window Review dialog |
| 18 | `test_nikon_maid_backend.py` | 4 | Nikon MAID backend wrapper |
| 19 | `test_printing.py` | 3 | Module in ấn cơ bản |
| 20 | `test_processing_and_templates.py` | 4 | Xử lý ảnh mẫu và ghép khung |
| 21 | `test_redesign_panels.py` | 4 | Các panel giao diện tái thiết kế |
| 22 | `test_responsive_layout.py` | 4 | Bố cục co giãn màn hình |
| 23 | `test_session_and_server.py` | 2 | API Server nội bộ và Session |
| 24 | `test_sharing_and_qr.py` | 1 | Chia sẻ ảnh qua mã QR |
| 25 | `test_smart_beauty_panel.py` | 16 | Smart Beauty Panel và thuật toán làm đẹp |
| 26 | `test_updates_and_version.py` | 31 | Kiểm tra cập nhật, SemVer, GitHub Release |
| 27 | `test_v142_features.py` | 4 | Tính năng theo dõi FPS và click review |
| 28 | `test_v143_camera_and_logo.py` | 5 | Render Logo SVG và Stream Worker |
| 29 | `test_v150_nikon_maid_integration.py` | 4 | Tích hợp Nikon MAID vào GUI |
| 30 | `test_v151_viewport_stability.py` | 4 | Ổn định Viewport Live View |
| 31 | `test_v152_kiosk_viewport.py` | 7 | Kiosk Live Viewport và Flash Effect |
| 32 | `test_v153_liveview_optimization.py` | 6 | Tối ưu hóa phân giải XGA 1024x680 Live View |
| 33 | `test_v154_autofocus_and_face_detection.py` | 23 | Autofocus MAID và kiểm thử lấy nét ống kính |
| 34 | `test_v155_one_click_updater.py` | 17 | Auto-updater một chạm |
| 35 | `test_v155_release_audit.py` | 15 | Kiểm thử nâng cấp thực tế và bảo toàn dữ liệu |
| 36 | `test_v166_printing_hardening.py` | 7 | Print Presets, Safety Margin 98%, Thermal Pacing |
| 37 | `test_v166_studio_audio.py` | 8 | Studio Audio System (Countdown, Voice, Shutter) |
| **TỔNG CỘNG** | **37 Files** | **306 Tests** | **100% PASS** |

---

### 4. ĐÁNH GIÁ ẢNH HƯỞNG CỦA `pytest.ini`, `conftest.py` VÀ `pytest_unconfigure`

1. **`pytest.ini`:**
   - `testpaths = vietphotobooth/tests`: Thiết lập chuẩn mực của dự án, đảm bảo pytest chỉ kiểm thử mã nguồn chính của ứng dụng `vietphotobooth`, không quét lan sang các thư mục công cụ/AI skills ngoài luồng.
   - `--capture=sys`: Thay thế cờ bắt mặc định fd của pytest trên Windows, ngăn chặn lỗi xung đột file descriptor khi PySide6/Qt C++ runtime đóng cửa sổ.
2. **`conftest.py`:**
   - Bảo toàn fixture offscreen `qapp` cho toàn bộ các bài test GUI.
   - Thêm cơ chế `sys.stdout.flush()` và `sys.stderr.flush()` trước khi kết thúc phiên.
3. **`pytest_unconfigure`:**
   - Đảm bảo khi tiến trình pytest hoàn thành nhiệm vụ, hệ điều hành giải phóng nhanh các luồng ngầm của Media Foundation / WASAPI audio driver (do `QSoundEffect` tạo ra), loại bỏ triệt để lỗi crash `0xC0000409` khi Windows C runtime DLL detach.
   - Giữ nguyên mã thoát thực tế của pytest (`_session_exitstatus`), đảm bảo nếu có test fail thì pytest vẫn trả về mã lỗi `> 0`.

---

### 5. KẾT LUẬN ĐỐI SOÁT
- Cơ số test thực tế chuẩn của mã nguồn 1998 TEAM Photobooth hiện tại là **306 tests**.
- Toàn bộ 306 tests đều vượt qua kiểm tra với mã thoát `0`.
- Chênh lệch 3 test đã được giải trình chi tiết và có bằng chứng đối soát rõ ràng 100%.
