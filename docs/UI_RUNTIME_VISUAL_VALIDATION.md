# UI Runtime Visual Validation — 1998 TEAM Photobooth

**Ngày kiểm tra:** 2026-11-04 (Asia/Saigon)  
**Repository:** `C:\Users\Admin\Documents\photobooth`  
**Branch / HEAD:** `feature/v2.0.0-photobooth` / `08bfb13c54c142da3342114425ce195634cd04f3`  
**Ứng dụng chạy:** từ source bằng Python 3.12.10, Qt/PySide6; không dùng EXE. Phiên bản hiển thị trong Settings: **v2.0.0 Build 206**.  
**Phạm vi:** Runtime visual audit chỉ đọc. Không sửa source/style/config production, không chạy test/build, không in, upload, tạo QR hoặc thao tác dữ liệu thật.

## 1. Kết quả tóm tắt

Ứng dụng khởi động được trong profile kiểm tra riêng và đóng bình thường. Phiên runtime dùng **Camera Simulator**, không có Nikon hoặc máy in vật lý. Đã quan sát Dashboard/navigation, Kiosk idle, countdown, capture review, retake theo slot, composition, Smart Beauty, Frame Gallery, Frame Designer, Filter Editor, Camera/Live View, Printer status, Events và Settings. PIN được người dùng tự nhập tại máy; Codex không nhập PIN. Các thao tác có thể lưu ảnh chỉ dùng dữ liệu mô phỏng trong profile tạm.

Các lỗi hiển thị runtime có bằng chứng:

- Frame Designer bị cắt các control ở mép phải cả ở cửa sổ 1277×752 và cửa sổ tối đa 1920×1080.
- Trang Camera bị cắt panel thông tin/điều khiển bên phải ở 1277×752.
- Trang Printer và Events có nội dung/control vượt vùng nhìn thấy ở 1277×752; phần dưới có thể cuộn, nhưng hàng nút bên phải cũng bị cắt. Không kết luận scroll bị hỏng.
- Filter Editor có thông điệp empty-state tương phản rất thấp và accent xanh cyan khác palette Soft Taupe đã duyệt.
- Một số trang hiện dòng “Đang đồng bộ Google Drive” dù profile dùng chế độ mô phỏng; đây là nhãn giao diện quan sát được, không chứng minh có truyền dữ liệu thật.

System DPI được đọc là 96 DPI (100%); desktop 1920×1080. Chỉ thử được cửa sổ 1277×752 và chế độ tối đa 1920×1080. Không thay đổi độ phân giải hay Windows scaling.

## 2. Cô lập dữ liệu và khởi chạy

- Đọc lại `AGENTS.md`, `GEMINI.md` và Constitution/hướng dẫn hiện có trước runtime. Không chỉnh các file này.
- Profile kiểm tra: `C:\Users\Admin\AppData\Local\Temp\Photobooth_UI_Runtime_20261104`.
- `LOCALAPPDATA`, `APPDATA`, `USERPROFILE`, `TEMP`, `TMP` được chuyển riêng vào profile tạm. Cấu hình dùng `storage_dir` dưới profile, sự kiện `UI_AUDIT_Runtime`, `camera_backend=simulator`, `auto_print=false`, `auto_check_on_startup=false`, `gdrive_simulation_mode=true`.
- Khởi chạy source bằng Python 3.12.10 với bytecode writing disabled và `--no-server`; không chạy EXE cũ, không mở LAN server. Simulator báo 960×640, nguồn khoảng 30 FPS.
- Lần khởi chạy cô lập đầu tiên gặp lỗi BOM trong file cấu hình thử nghiệm và app quay về cấu hình mặc định; phiên đó được đóng bình thường. File cấu hình tạm được ghi lại UTF-8 không BOM, sau đó khởi chạy lại thành công. Không đụng cấu hình production. Đây là lỗi của bước tạo profile thử, không phải lỗi source được xác nhận.
- Log runtime có cảnh báo OpenCV DNN về target không hỗ trợ, FilterEngine nạp 0 preset và Guest Canvas báo không có ảnh đầu vào khi khởi động. Chưa điều tra sâu các cảnh báo vì phạm vi là visual audit. FrameManager nạp 21 template. Simulator không có khuôn mặt, vì vậy thông báo Eye AF không tìm thấy mặt không đánh giá khả năng nhận diện trên camera thật.
- App được đóng qua thao tác đóng cửa sổ bình thường; cửa sổ Python Photobooth biến mất khỏi danh sách cửa sổ. Không gửi lệnh AF, không kết nối camera hoặc printer vật lý.
- Screenshot runtime phản ánh working tree tại thời điểm kiểm tra với HEAD nêu trên và các sửa đổi chưa commit đã tồn tại trước nhiệm vụ; không khẳng định working tree trùng hoàn toàn với commit HEAD.

## 3. Thiết lập hình ảnh

| Thuộc tính | Giá trị |
|---|---|
| Desktop | 1920×1080 |
| Windows scaling | 100% (96 DPI), đọc trạng thái hệ thống; không thay đổi |
| Kích thước cửa sổ trong ảnh | 1277×752 và 1920×1080 |
| Runtime | Simulator; event `UI_AUDIT_Runtime`; không dùng ảnh/sự kiện production |
| Palette tham chiếu | #C8C5BD, #D9D5CC, #B9B5AB, #E2DED5, #AAA69D, #353631, #716F68, #AD905B, #D0BC94; Live View #17191C |

## 4. Screenshot evidence

Tất cả ảnh nằm dưới `docs/ui-audit/screenshots/`. Thời gian dưới đây là giờ máy Windows (Asia/Saigon), lấy từ thời điểm ghi ảnh. Các ảnh có tên `photobooth_*` là những ảnh được bổ sung trong phiên kiểm tra này; ảnh còn lại được lưu ở các bước runtime trước trong cùng tác vụ.

| Màn hình / trạng thái | Screenshot | Kích thước ảnh | Thời gian (04-11-2026) | Nguồn / ghi chú |
|---|---|---:|---|---|
| Dashboard / navigation | `dashboard_simulator_1277x752.png` | 1277×752 | 14:44:22 | Simulator, test profile |
| Kiosk idle, cửa sổ | `kiosk_idle_simulator_1277x752.png` | 1277×752 | 14:43:33 | Simulator, test profile |
| Kiosk idle, toàn màn hình | `kiosk_idle_simulator_1920x1080.png` | 1920×1080 | 14:45:42 | Simulator, test profile |
| Guest idle | `guest_idle_simulator_1920x1080.png` | 1920×1080 | 14:46:16 | Simulator, test profile |
| Countdown chạy | `countdown_3s_simulator_1920x1080.png` | 1920×1080 | 14:47:04 | Simulator, ảnh 1/3 |
| Review sau capture | `capture_review_simulator_1920x1080.png` | 1920×1080 | 14:47:42 | 3 ảnh mô phỏng; không lưu/in |
| Smart Beauty dialog | `smart_beauty_review_dialog_1102x752.png` | 1102×752 | 14:47:42 | Review dữ liệu mô phỏng; không chỉnh thông số để lưu |
| Photo Composition | `photo_composition_review_simulator_1920x1080.png` | 1920×1080 | 14:49:20 | 3 slot ảnh mô phỏng |
| Retake một slot / countdown | `slot_retake_countdown_simulator_1920x1080.png` | 1920×1080 | 14:49:48 | Retake trong lượt mô phỏng |
| PIN dialog | `touch_pin_dialog_simulator_1920x1080.png` | 1920×1080 | 14:52:08 | Dialog; PIN do người dùng tự nhập |
| PIN dialog crop | `touch_pin_dialog_crop_382x552.png` | 382×552 | 14:51:24 | Crop bằng chứng dialog |
| Frame Gallery | `frame_gallery_top_1277x752.png` | 1277×752 | 14:53:53 | 21 template đã nạp |
| Frame Gallery → yêu cầu PIN | `frame_gallery_frame_designer_pin_prompt_1277x752.png` | 1277×752 | 14:54:54 | Dialog quyền truy cập |
| Frame Designer | `photobooth_frame_designer_top_1277x752.png` | 1277×752 | 14:56:21 | Runtime, test profile |
| Frame Designer cuộn | `photobooth_frame_designer_scrolled_1277x752.png` | 1277×752 | 14:56:37 | Vertical scrolling có hoạt động |
| Frame Designer tối đa hóa | `photobooth_frame_designer_maximized_1920x1080.png` | 1920×1080 | 14:57:27 | Vẫn thấy control mép phải bị cắt |
| Filter Editor, parent | `photobooth_filter_editor_with_parent_1277x752.png` | 1277×752 | 14:59:06 | Empty preview / accent cyan |
| Filter Editor dialog | `photobooth_filter_editor_dialog_1092x752.png` | 1092×752 | 14:59:06 | Dialog từ editor; không tạo preset |
| Settings đầu trang | `photobooth_settings_top_1277x752.png` | 1277×752 | 15:00:29 | Chỉ quan sát |
| Settings cuộn | `photobooth_settings_scrolled_1277x752.png` | 1277×752 | 15:00:45 | Chỉ quan sát |
| Camera settings + Live View Simulator | `photobooth_camera_liveview_simulator_1277x752.png` | 1277×752 | 15:02:50 | 960×640; ~30 FPS; không phải camera thật |
| Events / event không ảnh | `photobooth_events_library_empty_simulator_1277x752.png` | 1277×752 | 15:03:29 | `UI_AUDIT_Runtime`, 0 ảnh thành phẩm |
| Printer status | `photobooth_printer_status_simulator_1277x752.png` | 1277×752 | 15:03:19 | Chỉ trạng thái; không print |

## 5. Trạng thái từng nhóm màn hình

| Màn hình / chức năng | Trạng thái | Bằng chứng và ranh giới |
|---|---|---|
| Dashboard, navigation | Runtime đã chụp | Điều hướng và Dashboard nhìn được; các status thiết bị trên Dashboard có vẻ là dữ liệu demo, không khớp thiết bị Simulator đang chạy. Không xem các status đó là bằng chứng Nikon/DNP thật. |
| Events | Runtime đã chụp một event thử nghiệm rỗng | Event có 0 ảnh thành phẩm. Dòng đồng bộ Google Drive hiển thị dù cấu hình profile mô phỏng; không xác minh network và không bấm đồng bộ. Không tạo/xóa event. |
| Frame Gallery | Runtime đã chụp | 21 templates có sẵn; trạng thái empty/no-results không tạo được trong kiểm tra này. |
| Frame Designer | Runtime đã chụp, kể cả cuộn và tối đa hóa | Bằng chứng clipping mép phải ở hai kích thước; cuộn dọc hoạt động. Không chỉnh/saving frame. |
| Devices | Chưa kiểm tra | Không có luồng mở riêng an toàn được xác nhận trong cửa sổ thời gian này. |
| Camera / Live View | Runtime Simulator đã chụp | Frame pattern Simulator 960×640, counter ~30 FPS; panel phải bị cắt ở 1277×752. Không có camera vật lý. Không bấm AF hoặc connect device. |
| Kiosk / Guest Idle | Runtime đã chụp | Idle và full-screen; nút bắt đầu lớn, dễ nhận thấy. |
| Capture / Countdown | Runtime Simulator đã thao tác | Thực hiện một lượt ba ảnh và countdown 3 giây; ảnh là dữ liệu mô phỏng trong profile tạm. Không đánh giá shutter vật lý hay âm thanh. |
| Review / Retake | Runtime Simulator đã thao tác | Review và retake theo slot xuất hiện. Không phát sinh thao tác in, upload hoặc chia sẻ. |
| Photo Composition | Runtime Simulator đã chụp | Có composition với ảnh mô phỏng. Không lưu thành phẩm ra production. |
| Printing | Runtime status đã chụp | Có trạng thái “Sẵn sàng”; nội dung cột phải bị cắt ở cửa sổ 1277×752. Không gửi lệnh in; không xác minh printer vật lý. |
| QR Sharing | Chưa kiểm tra trực tiếp | Không mở QR, tạo mã hoặc chia sẻ. Chỉ đối chiếu finding source trước đây. |
| Gallery / Session Lightbox | Chưa kiểm tra riêng | Event gallery hiển thị trạng thái 0 ảnh; không mở lightbox hoặc QR. |
| Settings | Runtime đã chụp, đầu trang và cuộn | Chỉ quan sát; không đổi setting. |
| PIN dialog | Runtime đã chụp | Người dùng tự nhập PIN theo xác nhận; Codex không gõ PIN. Không kiểm tra lockout. |
| Smart Beauty | Dialog runtime đã chụp | Preview mô phỏng không có mặt; UI hiển thị trạng thái không phát hiện mặt. Không đánh giá thuật toán trên ảnh người thật. |
| Filter/LUT Editor | Runtime đã chụp | Empty preview thông điệp kém tương phản; accent cyan. Không tạo/chỉnh/lưu filter. |
| Các dialog/popups khác | Chưa kiểm tra đầy đủ | Chỉ các dialog nêu cụ thể trong inventory ảnh đã được mở. Không tạo lỗi hay xác thực để ép trạng thái error. |

## 6. Findings và đối chiếu `docs/UI_AUDIT_VALIDATION.md`

| Finding gốc | Trạng thái runtime sau kiểm tra | Bằng chứng / giới hạn |
|---|---|---|
| UI-FUNC-01 — capture lỗi một phần có thể tái dùng session/ghi đè ảnh; High | Chưa xác minh runtime; không bác bỏ | Chỉ kiểm tra capture thành công và retake Simulator. Không cố tình làm lỗi/disconnect hay khởi chạy lại cùng session sau partial failure. Giữ nguyên finding source. |
| UI-ARCH-01 — tab protection phụ thuộc thứ tự index; Medium | Source-only | Không reorder tab hoặc kiểm tra fixture. Không có lỗi runtime tái hiện. |
| UI-VIS-01 — QR modal màu lạnh ngoài palette; Medium | Chưa xác minh runtime | Không mở QR modal; source finding vẫn là căn cứ hiện có. |
| UI-VIS-02 — Filter/LUT Editor accent lạnh; Medium | Runtime xác nhận | `photobooth_filter_editor_with_parent_1277x752.png`: số/accent cyan nổi bật trên nền preview tối; empty-state text khó đọc. Reviewer độc lập nhìn thấy cùng vấn đề. |
| UI-RESP-01 — thiếu coverage responsive/DPI; Medium (gap) | Runtime xác nhận clipping ở một số kích thước | Frame Designer 1277×752 và 1920×1080; Camera, Events, Printer 1277×752. Không kiểm tra đủ ma trận độ phân giải/DPI; không khẳng định mọi control hoặc mọi kích thước đều lỗi. |
| UI-CONS-01 — frame cards khác implementation giữa màn; Low | Chưa đủ đối chiếu runtime | Gallery được chụp, nhưng không đặt các card ở Gallery/Kiosk/Review vào cùng trạng thái để so sánh parity. |
| UI-VIS-03 — icon SVG và emoji trộn lẫn; Low | Hiện diện trực quan, không xác nhận lỗi | Screenshot có glyph/emoji; không đo baseline, contrast, accessibility hoặc khác biệt font. |
| UI-UX-01 — empty/no-results feedback; Low | Events empty state được quan sát một phần | Event có 0 ảnh; dưới viewport có vùng thư viện, nhưng không kết luận thiếu scroll vì ảnh tĩnh không chứng minh được. Frame Gallery có dữ liệu nên empty search chưa thử. |

### Runtime findings mới, được giới hạn theo ảnh

1. **Clipping ngang Frame Designer — xác nhận.** Hai reviewer responsive/visual cùng quan sát right-side fields/buttons vượt mép cửa sổ ở `photobooth_frame_designer_top_1277x752.png` và `photobooth_frame_designer_maximized_1920x1080.png`. Cuộn dọc có hoạt động; chưa xác định có cơ chế cuộn ngang ẩn hay không.
2. **Clipping ngang Camera page — xác nhận ở 1277×752.** Backend selector, bảng thông tin thiết bị và một số control phía phải bị cắt trong `photobooth_camera_liveview_simulator_1277x752.png`.
3. **Trang Printer và Events bị giới hạn vùng nhìn thấy — xác nhận theo screenshot 1277×752.** Cột phải bị cắt; phần nội dung dưới nằm ngoài viewport. Có thể trang hỗ trợ cuộn, nên đây là quan sát viewport, không kết luận lỗi scrolling.
4. **Filter Editor empty state — xác nhận dễ đọc kém.** Thông điệp trên preview tối khó phân biệt; numeric accents cyan lệch palette tham chiếu. Contrast chưa được đo bằng công cụ.
5. **Countdown và Kiosk idle feedback nhìn rõ trong ảnh.** Countdown có số lớn và tiến trình ảnh; Kiosk có nút bắt đầu nổi bật. Đây là nhận xét về frame chụp, không chứng minh touch target tốt.
6. **Dòng “Đang đồng bộ Google Drive” cần làm rõ.** Đây là trạng thái hiển thị cho event tạm trong profile cấu hình simulation. Chưa đọc network traffic và không xác định có hành vi đồng bộ thật; không đưa ra kết luận về rò rỉ dữ liệu.

Các nhận xét bổ sung của agent về thấp tương phản ở subtitle hoặc kích cỡ nút được phân loại là quan sát/chủ quan; không ghi thành lỗi xác nhận nếu không có phép đo hoặc thao tác tương tác hỗ trợ.

## 7. Đánh giá độc lập screenshot

Ba lượt review chỉ xem ảnh, không sửa file:

- **Visual Design:** xác nhận clipping Frame Designer ở cửa sổ nhỏ và tối đa hóa; xác nhận accent cyan/empty-state Filter Editor. Nhận xét palette tổng thể ở Dashboard/Kiosk/Events/Frame Designer khá thống nhất.
- **UX:** xác nhận feedback countdown rõ; ghi nhận cột/nút Events, Printer, Camera bị cắt và trạng thái đồng bộ Google Drive có thể gây nhầm lẫn. Không xem thao tác touch là đã test.
- **Responsive:** xác nhận clipping Frame Designer và Camera; xác nhận cuộn dọc Frame Designer hoạt động. Không quy lỗi cho cuộn dọc Events/Printer chỉ dựa trên crop.
- **Coordinator (Architecture/Regression):** đối chiếu source và báo cáo UI audit cũ; không thay đổi findings nguồn chỉ vì chưa tái hiện runtime.

Ý kiến về contrast chưa có số đo; ý kiến về touch target chưa được thao tác trên màn hình cảm ứng thật. Chúng không được ghi thành lỗi chắc chắn.

## 8. Những mục chưa kiểm tra / chưa thể kết luận

- Kích thước 1024×680, 1366×768 và 1600×900.
- Windows scaling 125%, 150%, 200%; không thay đổi DPI của máy.
- Touchscreen thực, keyboard-only navigation, focus ring, screen reader và thao tác một tay.
- Camera/Nikon D780 thật, quality hoặc latency camera vật lý, AF, hành vi shutter và ảnh người thật.
- Printer vật lý, trạng thái lỗi máy in, hết giấy và thao tác in.
- QR modal, QR sharing, Gallery/Lightbox, cloud sync thật hoặc upload; không tạo mã hoặc request chia sẻ.
- Error/loading/disabled states cần phần cứng hay lỗi cưỡng bức.
- Devices page, một số màn quản trị được bảo vệ, toàn bộ dialog/modal trong inventory.
- Capture failure sau partial success và nguy cơ overwrite UI-FUNC-01.
- Độ tương phản định lượng, quy chuẩn WCAG cho màn hình native.

## 9. Test, thao tác và file

- **Automated tests:** Không chạy, theo yêu cầu audit-only.
- **Build/installer:** Không chạy.
- **Source/config production:** Không sửa.
- **Camera/printer thật:** Không kết nối/điều khiển.
- **Profile tạm:** Được tạo trong `%TEMP%`; được giữ nguyên để người dùng có thể kiểm tra. Không xóa.
- **Git trước/sau:** Trước runtime, trạng thái được ghi trong `docs/UI_AUDIT_VALIDATION.md`: branch `feature/v2.0.0-photobooth`, 18 modified tracked paths (`vietphotobooth/audio/constants.py`, `audio/sound_controller.py`, `camera/backends/digicam_control.py`, `camera/backends/directshow_webcam.py`, `camera/connection_manager.py`, `desktop/styles.py`, `desktop/widgets/dashboard_page.py`, `devices_page.py`, `events_page.py`, `kiosk_page.py`, `live_viewport.py`, `printing_page.py`, `qr_sharing_page.py`, `session_lightbox_dialog.py`, `settings_page.py`, `smart_beauty_panel.py`, `touch_pin_dialog.py`, `vietphotobooth/tests/test_v200_rc2_hardening.py`) và các mục untracked `.agents/skills/speckit-*` (9 thư mục), `.specify/`, `docs/BASELINE_AUDIT_VALIDATION.md`, `docs/BASELINE_SYSTEM_AUDIT.md`, `docs/UI_AUDIT_VALIDATION.md`, `vietphotobooth/tests/test_dynamic_countdown_voice_sync.py`, `test_simulator_countdown_audio_timeline.py`. Sau kiểm tra, `git status --short --branch` chạy read-only thành công khi cấp `safe.directory` chỉ qua biến môi trường cho đúng lệnh; không ghi Git config. Các mục trước vẫn còn; chỉ phát sinh thêm `docs/UI_RUNTIME_VISUAL_VALIDATION.md` và `docs/ui-audit/` chứa 24 screenshot PNG. Không có modified tracked path mới.
- **Tạo trong nhiệm vụ runtime này:** `docs/UI_RUNTIME_VISUAL_VALIDATION.md` và các ảnh sau trong `docs/ui-audit/screenshots/`: `photobooth_camera_liveview_simulator_1277x752.png`, `photobooth_events_library_empty_simulator_1277x752.png`, `photobooth_filter_editor_dialog_1092x752.png`, `photobooth_filter_editor_with_parent_1277x752.png`, `photobooth_frame_designer_maximized_1920x1080.png`, `photobooth_frame_designer_scrolled_1277x752.png`, `photobooth_frame_designer_top_1277x752.png`, `photobooth_printer_status_simulator_1277x752.png`, `photobooth_settings_scrolled_1277x752.png`, `photobooth_settings_top_1277x752.png`. Các screenshot khác được tạo ở các bước trước của cùng tác vụ và được liệt kê ở bảng trên.

## 10. Kết luận

Runtime inspection xác nhận một số lỗi clipping trên cửa sổ 1277×752, và clipping Frame Designer còn xuất hiện trong ảnh tối đa hóa 1920×1080. Filter Editor có mismatch màu và empty-state khó đọc. Kiosk/countdown/review Simulator hoạt động đủ để tạo ảnh minh họa; không thể suy rộng sang camera, AF, shutter hoặc printer thật.

Đây là kết quả audit, không phải phê duyệt thiết kế hoặc triển khai. Không có giao diện hay source nào được sửa. Dừng tại báo cáo và chờ người dùng duyệt trước khi bắt đầu bất kỳ UI fix nào.