# UI Audit Validation — 1998 TEAM Photobooth

**Ngày kiểm tra:** 2026-11-04 (Asia/Saigon)  
**Repository:** C:\Users\Admin\Documents\photobooth  
**Branch / HEAD:** feature/v2.0.0-photobooth / 08bfb13c54c142da3342114425ce195634cd04f3  
**Phạm vi:** Audit chỉ đọc UI/UX. Không sửa source, stylesheet, config, Spec Kit Constitution, workflow, hoặc audit trước đây. Không chạy test, build hay thao tác có thể in/xóa dữ liệu.

## 1. Tóm tắt điều hành

Audit rà soát cấu trúc Qt, palette Soft Taupe Studio, luồng operator/guest, sizing/responsive và các điểm giao nhau với camera, capture, audio, frame, printing và QR.

**Kết luận chính:** Có một rủi ro chức năng mức High trong recovery sau capture failure: Kiosk xóa danh sách ảnh trong bộ nhớ nhưng giữ session ID/thư mục. Khi bắt đầu lại, code có thể dùng lại cùng đường dẫn và ghi đè ảnh số 1 của lượt trước. Đây là kết luận từ luồng source, chưa tái hiện runtime.

Source cũng xác nhận hai vùng UI ghi đè màu lệch khỏi palette đã duyệt (QR modal và Filter/LUT Editor), điều hướng/PIN phụ thuộc chỉ số tab, các dialog/card frame có cách triển khai riêng, và một số màn hình chỉ có empty state rất tối giản. Chưa có kết luận về chữ bị cắt, touch ergonomics hoặc màu hiển thị thực tế vì không kiểm tra giao diện runtime.

**Tổng số findings:** Critical 0, High 1, Medium 4, Low 3. Không có finding nào được xác nhận bằng screenshot mới.

## 2. Spec Kit và điều phối agent

### Spec Kit đã xác minh

- .specify/workflows/workflow-registry.json đăng ký một workflow: speckit, “Full SDD Cycle”, version 1.0.1.
- .specify/workflows/speckit/workflow.yml xác định chuỗi speckit.specify → speckit.plan → speckit.tasks → speckit.implement với các review gates.
- Repository có các skill folders speckit-analyze, speckit-checklist, speckit-clarify, speckit-constitution, speckit-converge, speckit-implement, speckit-plan, speckit-specify và speckit-tasks.
- speckit-analyze mô tả phân tích tính nhất quán giữa spec.md, plan.md và tasks.md sau khi tạo task; đây không phải workflow UI audit.
- Workflow đăng ký không có bước inventory UI, screenshot hay phối hợp reviewer. Chạy chu trình SDD sẽ tạo/sửa artifact ngoài phạm vi audit. Vì vậy workflow được kiểm tra nhưng không được chạy; không có file Spec Kit nào được thay đổi.
- Impeccable skill tồn tại trong .agents/skills/impeccable. Tham chiếu audit của skill dành cho web; nhánh native nêu iOS/Android/adaptive. Không có hướng dẫn audit native Windows/PySide phù hợp trực tiếp, nên không gọi installer/detector hoặc tạo artifact từ skill này.

### Agent thực sự tham gia

Có 4 instance: coordinator Codex và 3 agent con được giao độc lập. Các vai trò được gộp do giới hạn concurrency:

| Vai trò | Người thực hiện | Phạm vi |
|---|---|---|
| A — UI Architecture | Agent con 1 | Qt pages/dialogs, navigation, shared components, styling |
| B — Visual Design | Agent con 2 | Màu, typography, icon, spacing và đối chiếu palette |
| C — UX & Workflow | Agent con 3 | Operator/Guest flows, state feedback và regressions |
| D — Responsive & Kiosk | Coordinator | Sizing, scrolling, scaling, touch/kiosk; static source |
| E — Regression & Consistency | Coordinator | Cross-check phát hiện với source/test inventory và chức năng liên quan |

Ba agent con chỉ gửi kết quả trong phiên; họ không tạo file, không chạy app/test và không sửa Git. Coordinator đối chiếu source cho các phát hiện ưu tiên cao. Các agent không phải những chương trình kiểm định chuyên ngành riêng; đây là những lượt rà soát độc lập do công cụ phối hợp agent của Codex điều phối.

## 3. Phương pháp và giới hạn bằng chứng

- Source hiện tại và một số bài test liên quan được đọc tĩnh; test coverage được lập danh mục nhưng không chạy.
- Không có cửa sổ Photobooth đang chạy trong danh sách cửa sổ máy tính khi kiểm tra. Danh sách có một đường dẫn EXE trong thư mục pytest tạm nhưng không có cửa sổ đang mở; không dùng EXE đó làm bằng chứng phiên bản hiện tại.
- Không chạy ứng dụng từ source: main.py không có cờ test-profile/simulator-only; cấu hình mặc định đặt camera_backend là DirectShow. ConfigManager ghi config theo LOCALAPPDATA; FrameManager/FilterEngine khởi tạo thư mục và preset mặc định; do đó không thể khẳng định launch bình thường sẽ không tạo hoặc cập nhật dữ liệu ngoài artifact báo cáo. Đổi sang profile/config tạm hoặc backend Simulator cũng sẽ là thay đổi cấu hình của phiên kiểm tra. Để giữ quy tắc không thay đổi cấu hình, không khởi chạy UI.
- Screenshot 1998 TEAM đã xuất hiện trong nội dung trao đổi trước không được xem là ảnh chụp mới của working tree hiện tại. Không có screenshot runtime nào được tạo/lưu.
- Vì thiếu runtime evidence, mọi nhận xét về màu/geometry được ghi là source-based; việc clipping, contrast nhìn thấy, focus order và cảm giác thao tác vẫn cần xác minh trực tiếp.

## 4. Inventory toàn bộ màn hình và component

Các nhóm dưới đây đều được kiểm tra ở mức source. “Static” không có nghĩa đã xác nhận hình thức render.

| # | Màn hình / component | Source chính | Kết quả static |
|---:|---|---|---|
| 1 | Dashboard | desktop/widgets/dashboard_page.py, DashboardPage | Có QScrollArea; responsive test kiểm tra container và một số control, chưa kiểm tra mọi child geometry. |
| 2 | Navigation / tab bar / stack | desktop/main_window.py, MainWindow | Có 6 tab chính; access gating dùng số index; xem UI-ARCH-01. |
| 3 | Events | desktop/widgets/events_page.py, EventsPage | Có tạo/chuyển sự kiện, gallery; empty gallery chủ yếu thể hiện số lượng. |
| 4 | Frame Gallery | desktop/widgets/frame_tab_container.py, frame_gallery_page.py | Có filter/search và card; zero-result không có thông điệp empty riêng trong refresh_gallery. |
| 5 | Frame Designer | desktop/widgets/frame_designer_page.py, FrameDesignerPage/InteractiveCanvas | Có canvas và scroll controls; page có minimum sizing; clipping chưa xác minh. |
| 6 | Device Management | desktop/widgets/devices_page.py, DevicesPage | Có danh sách thiết bị/channel; chưa xác minh trạng thái rỗng/lỗi bằng runtime. |
| 7 | Camera Connection | desktop/widgets/camera_page.py, CameraPage | Có chọn backend/device, connect/disconnect và status text; control source được phân tích. |
| 8 | Live View | desktop/widgets/live_viewport.py, CameraLiveViewport; camera_page.py | Có viewport/resize handling; không kiểm tra frame hiển thị thật. |
| 9 | Kiosk / Guest Idle | desktop/widgets/kiosk_page.py, guest_idle_screen.py | Có màn chờ, bắt đầu và thao tác kiosk; touch target/runtime focus chưa xác minh. |
| 10 | Capture / Countdown | kiosk_page.py, KioskPage | Có 3/5/10 giây, đếm từng giây, cancel; luồng capture failure có finding High. |
| 11 | Review / Retake | kiosk_page.py, guest_review_dialog.py, GuestReviewWidget | Có retake toàn phiên và theo slot, chọn ảnh; recovery sau lỗi một phần cần cải thiện. |
| 12 | Photo Composition | frames/frame_designer.py, guest_review_dialog.py | Có ghép ảnh, frame, crop và layer; visual parity không được render kiểm tra. |
| 13 | Printing | desktop/widgets/printing_page.py, PrintingPage | Có printer selection/status và print controls; không gọi printer hoặc print test. |
| 14 | QR Sharing | desktop/widgets/qr_sharing_page.py, events_page.py QR modal | Có màn QR và modal; QR modal dùng màu hardcode lệch palette. |
| 15 | Gallery / Session Lightbox | events_page.py, session_lightbox_dialog.py | Có danh sách session và lightbox; không có dữ liệu runtime mẫu để đánh giá visually. |
| 16 | Settings | desktop/widgets/settings_page.py, SettingsPage | Có nhóm settings và scroll; không thay đổi cài đặt. |
| 17 | Touch PIN Dialog | desktop/widgets/touch_pin_dialog.py, TouchPinDialog | Có keypad/status/lockout logic; kích thước và focus thực tế chưa xác minh. |
| 18 | Smart Beauty Panel | desktop/widgets/smart_beauty_panel.py, SmartBeautyDialog | Có preview và adjustment controls; chưa thử xử lý ảnh runtime. |
| 19 | Shared dialogs/popups/notifications | camera_page.py, frame_designer_page.py, filter_editor_page.py, guest_review_dialog.py, kiosk_page.py, events_page.py | Inventory bao gồm camera diagnostic/fullscreen, import frame, filter editor/dialog, crop, photo picker, touch number pad, print-copy/QR modal và QMessageBox flows. |
| 20 | Filter/LUT Editor | desktop/widgets/filter_editor_page.py, FilterEditorPage/FilterEditorDialog | Là màn bổ sung ngoài danh sách tối thiểu; preview accent có mismatch với palette. |

Các class/component bổ sung được lập danh mục tĩnh gồm DeviceChannelCard, FrameCard, FrameCardWidget, ReviewFrameCard, PhotoThumbnailCard, SlotCard, PrintMarginPreviewWidget, GuestInteractiveCanvas và InteractiveCanvas. Không thể xác nhận states hover/focus/disabled/empty thực tế nếu không chạy UI.

## 5. Findings đã xác minh chéo

### UI-FUNC-01 — Capture failure có thể làm lượt mới dùng lại session và ghi đè ảnh trước

- **Màn hình/component:** Capture / Countdown; KioskPage.
- **Loại:** Functional, UX, regression/data integrity.
- **Severity:** High.
- **Tái hiện:** Có điều kiện; chưa chạy để tái hiện.
- **Bằng chứng source:** vietphotobooth/desktop/widgets/kiosk_page.py, start_capture_flow reset captured_originals/captured_paths và shot index nhưng không reset current_session_id/session_dir. Trong _trigger_shot, code chỉ tạo session directory khi current_session_id rỗng rồi ghi photo_{current_shot_index}.jpg. _abort_capture_due_to_disconnect đưa state về IDLE và clear hai danh sách ảnh nhưng không clear current_session_id/session_dir. CameraConnectionManager.capture_photo lưu đè target path nếu ảnh mới thành công. Backup *_original.jpg chỉ tạo nếu file backup chưa tồn tại.
- **Hệ quả có thể xảy ra:** Nếu đã chụp thành công một hoặc nhiều ảnh, sau đó capture lỗi/disconnect và người vận hành bắt đầu lại, session còn giữ nguyên; index bắt đầu từ 1 và target photo_1.jpg có thể bị ghi lại. Danh sách ảnh trên UI đã bị xóa, vì vậy khách/operator cũng mất ngữ cảnh các ảnh còn nằm trên disk.
- **Agent phát hiện / xác minh:** C agent phát hiện; coordinator đối chiếu source và luồng ghi file.
- **Test coverage:** test_kiosk_face_eye_af_capture.py kiểm tra các nhánh AF/capture; test_camera_connection_manager.py kiểm tra manager save. Không tìm thấy test cho partial success → failure → start new capture, không overwrite session cũ.
- **Cách kiểm chứng tương lai:** Trong profile tạm và Simulator, chụp thành công ít nhất một ảnh, ép lần sau trả lỗi/disconnect, thử bắt đầu lại và xác nhận session ID/path/bytes cũ được bảo toàn hoặc có xác nhận rõ trước khi thay thế.
- **Ảnh hưởng phụ thuộc:** Kiosk, lưu ảnh Originals, Guest Review, session recovery và event gallery.
- **Hướng xử lý cần đặc tả trước:** Định nghĩa rõ retry cùng session hay bắt đầu session mới; giữ tiến độ đã chụp; quy tắc overwrite/unique filename; khôi phục trạng thái sau disconnect.

### UI-ARCH-01 — Điều hướng và PIN protection phụ thuộc thứ tự tab/page

- **Màn hình/component:** Navigation, Operator pages, PIN.
- **Loại:** Consistency / Regression.
- **Severity:** Medium.
- **Bằng chứng source:** main_window.py, MainWindow.PROTECTED_TABS là {2,3,4,5}; _init_ui thêm tab theo thứ tự index 0–5; _on_tab_changed và switch_to_tab kiểm tra index số. QStackedWidget cũng dùng index số để chuyển Dashboard, Devices, QR và guest idle.
- **Kết luận:** Các index đang tương ứng với tab hiện tại; chưa chứng minh có lỗi đang xảy ra. Thêm/reorder tab/page có thể làm sai route hoặc PIN protection nếu không cập nhật cùng lúc.
- **Agent phát hiện / xác minh:** Agent A; coordinator đối chiếu.
- **Test coverage:** test_desktop_gui.py có test khởi tạo và PIN/tab protection; không kiểm tra cấu hình sau reorder hoặc định danh route độc lập index.
- **Cách kiểm chứng tương lai:** Kiểm tra mapping role→tab bằng ID ổn định; test thêm/reorder tab giả trong fixture.
- **Hướng xử lý cần đặc tả:** Navigation IDs và quy tắc quyền gắn với page identity thay vì số thứ tự.

### UI-VIS-01 — QR modal có bảng màu lạnh khác Soft Taupe Studio

- **Màn hình/component:** Events → QR modal.
- **Loại:** Visual / Consistency.
- **Severity:** Medium.
- **Bằng chứng source:** desktop/styles.py khai báo palette Soft Taupe và màu live view #17191C. events_page.py, EventsPage._open_qr_dialog_ui đặt tiêu đề/link #1E40AF, trạng thái #059669 và text #64748B; modal/dialog được style riêng.
- **Agent phát hiện / xác minh:** Agent B; coordinator đối chiếu mã.
- **Test coverage:** Không tìm thấy visual snapshot hoặc test so màu modal với design tokens.
- **Cách kiểm chứng tương lai:** Screenshot ở trạng thái QR LAN và Google Drive, so sánh từng màu với palette đã duyệt.
- **Hướng xử lý cần đặc tả:** Chốt ngoại lệ semantic colors cho QR/status và quy tắc dùng tokens trong dialog.

### UI-VIS-02 — Filter/LUT Editor dùng accent xanh lạnh ngoài palette

- **Màn hình/component:** Filter/LUT Editor, mở từ Settings/Kiosk.
- **Loại:** Visual / Consistency.
- **Severity:** Medium.
- **Bằng chứng source:** filter_editor_page.py đặt preview background #0B0F19, viền #334155 và số value #38BDF8. Preview dark không tự nó là lỗi vì Live View được phép tối; mismatch cụ thể là viền/accent xanh. SettingsPage._open_filter_editor và Kiosk callback cung cấp đường vào màn này.
- **Agent phát hiện / xác minh:** Agent B; coordinator đối chiếu các hằng số.
- **Test coverage:** Không tìm thấy visual snapshot hoặc palette assertion cho màn này.
- **Cách kiểm chứng tương lai:** Chụp màn Editor tại preview, preset list và trạng thái điều chỉnh; so với palette và ngoại lệ được duyệt.
- **Hướng xử lý cần đặc tả:** Xác định vùng preview tối được phép và token cho accent/value/border.

### UI-RESP-01 — Sizing/responsive hiện mới được kiểm tra ở mức top-level

- **Màn hình/component:** Dashboard, Frame Designer, Filter/LUT Editor, các dialog.
- **Loại:** Responsive / Accessibility.
- **Severity:** Medium (gap kiểm chứng, chưa phải lỗi clipping xác nhận).
- **Bằng chứng source:** MainWindow minimum size 1024×680; FrameDesignerPage có minimum size 820×560; FilterEditor preview minimum 480×420, panel scroll minimum width 360; QR modal setFixedSize(480,580), TouchPinDialog setFixedSize(380,520), nhiều card/dialog dùng fixed dimensions. Một số trang có QScrollArea và resizeEvent, nhưng không đồng nhất.
- **Test coverage:** test_v200_rc2_hardening.py::test_rc2_responsive_resolutions resize top-level ở 1366×768, 1600×900 và 1920×1080; assertions chủ yếu xác nhận kích thước cửa sổ, dashboard scroll và banner. Không kiểm tra child geometry, scaling 125–200%, màn 1024×680, clipping/focus hoặc toàn bộ dialog.
- **Kết luận:** Bằng chứng xác nhận constraint cố định và khoảng trống test; chưa chứng minh nội dung bị cắt.
- **Cách kiểm chứng tương lai:** Visual runtime ở 1024×680, 1366×768, 1600×900 và 1920×1080; Windows scaling 100/125/150/200%; chụp dialog dài và pages có panel cạnh nhau; kiểm tra scroll và touch reachability.
- **Hướng xử lý cần đặc tả:** Minimum supported work area, DPI behavior, touch target/focus criteria, scroll/overflow acceptance.

### UI-CONS-01 — Frame card có các implementation riêng giữa các màn

- **Màn hình/component:** Frame Gallery, Kiosk selection, Guest Review.
- **Loại:** Consistency / Architecture.
- **Severity:** Low.
- **Bằng chứng source:** frame_gallery_page.py::FrameCard, kiosk_page.py::FrameCardWidget, guest_review_dialog.py::ReviewFrameCard có logic thumbnail/selection/caption riêng với kích thước khác nhau.
- **Agent phát hiện / xác minh:** Agent A; source paths đối chiếu.
- **Test coverage:** Frame/gallery tests bao phủ từng màn riêng; chưa có cross-surface visual parity test.
- **Kết luận:** Sự trùng lặp source được xác nhận; kích cỡ khác nhau có thể là quyết định phù hợp theo ngữ cảnh, không khẳng định phải gom component.
- **Cách kiểm chứng tương lai:** Screenshot ba context ở cùng trạng thái selected/unselected và rà lại interaction states.
- **Hướng xử lý cần đặc tả:** Phân biệt token/pattern chung với biến thể kích thước hợp lệ.

### UI-VIS-03 — SVG và emoji cùng được dùng cho control chức năng

- **Màn hình/component:** Kiosk, Camera, Settings, QR.
- **Loại:** Visual / Consistency.
- **Severity:** Low.
- **Bằng chứng source:** desktop/icons.py cung cấp SVG icons; một số controls trong kiosk_page.py, camera_page.py, settings_page.py và qr_sharing_page.py dùng emoji trong text.
- **Agent phát hiện / xác minh:** Agent B; coordinator đối chiếu source.
- **Kết luận:** Hai icon vocabulary khác nhau được xác nhận. Khác biệt glyph, baseline hoặc hiển thị emoji phụ thuộc Windows font/runtime; chưa chứng minh clipping hay usability defect.
- **Test coverage:** Không tìm thấy visual snapshots across fonts/Windows.
- **Cách kiểm chứng tương lai:** Chụp cùng màn trên Windows font/scale được hỗ trợ, kiểm tra baseline, màu sắc, hit area và tính nhất quán.

### UI-UX-01 — Empty/no-results feedback chưa rõ ở Frame Gallery và Events Gallery

- **Màn hình/component:** Frame Gallery, Events photo gallery.
- **Loại:** UX.
- **Severity:** Low.
- **Bằng chứng source:** FrameGalleryPage.refresh_gallery cập nhật count rồi chỉ tạo card khi có template; nếu danh sách rỗng không có empty/no-results content trong method này. EventsPage._refresh_gallery reset table; nếu final directory chưa có thì cập nhật số 0 rồi return.
- **Agent phát hiện / xác minh:** Agent C; coordinator đối chiếu source.
- **Test coverage:** Không tìm thấy test empty search, event chưa có ảnh hoặc empty-state copy.
- **Kết luận:** Thiếu nội dung empty riêng trong các đường code nêu trên; chưa quan sát để xác định bố cục trắng có dễ nhận biết trong UI hay không.
- **Cách kiểm chứng tương lai:** Mở event mới chưa có ảnh, tìm kiếm không kết quả, filter frame rỗng; xác nhận có hướng dẫn bước tiếp theo.

## 6. Design System consistency

Palette được định nghĩa trong desktop/styles.py và khớp với brief Soft Taupe Studio:
main #C8C5BD; surface #D9D5CC; secondary #B9B5AB; input #E2DED5; border #AAA69D; primary text #353631; secondary text #716F68; champagne #AD905B; highlight #D0BC94; live view #17191C.

Source có token semantic success/warning/danger. Những màu semantic này không bị đánh dấu là lỗi chỉ vì khác taupe; review phân biệt màu trạng thái có chủ đích với accent trang trí. Hai mismatch được chứng minh trong QR modal và Filter/LUT Editor. Source cũng chứa inline styles ở nhiều page; đây là style ownership phân tán, chưa đủ bằng chứng để kết luận toàn bộ inline colors sai.

Typography defaults khai báo Segoe UI/Arial/Tahoma. MainWindow có font substitution cho emoji/symbol trên Windows. Không đo contrast, glyph clipping hoặc font scaling do không có runtime screenshot.

## 7. Visual inspection và screenshot evidence

**Trạng thái:** BLOCKED / chưa thực hiện.

- Không có screenshot UI Photobooth mới trong audit này.
- Không tạo thư mục docs/ui-audit/screenshots vì chưa có ảnh runtime hợp lệ để lưu.
- Cửa sổ Antigravity/Chrome được liệt kê trên máy không phải bằng chứng Photobooth source UI hiện tại.
- Không dùng screenshot cũ trong hội thoại để kết luận trạng thái hiện tại.
- Muốn hoàn tất phase này mà không ghi cấu hình thật cần một test profile/simulator launch mode được cho phép, có thể chạy app mà không ghi vào cấu hình/người dùng/source project, cùng quy trình lưu screenshot evidence. Source hiện không cung cấp cờ test-profile/simulator-only.

## 8. Cross-agent findings và mức xác minh

- Agent A và coordinator cùng xác nhận numeric tab/stack mapping qua source; đây là regression risk, không phải lỗi điều hướng hiện thời.
- Agent B và coordinator cùng xác nhận mã màu hardcode của QR modal và Filter/LUT Editor; tính mismatch với palette được chứng minh tĩnh, appearance render chưa xác minh.
- Agent C phát hiện session reuse sau partial capture failure; coordinator lần theo reset/list/save logic và xác nhận điều kiện có thể ghi lại filename cũ. Chưa chạy scenario.
- Agent C cũng ghi nhận positive feedback flows: camera-not-connected warning, disabled countdown controls, visible countdown/cancel, retake/review, printer result và PIN lockout. Source có các đường này nhưng chưa xác nhận chúng hiển thị/đọc tốt ở runtime.
- Không có xung đột findings cần bỏ qua. Các phát hiện chủ quan về “đẹp/xấu” không được xếp severity nếu thiếu tiêu chí/ảnh.
- Hình ảnh về layout clipping, focus order, touch ease, actual contrast và DPI không được tính là cross-agent verified.

## 9. Regression risks

1. Sửa session reset phải giữ an toàn ảnh Originals/recovery và không phá retake một slot.
2. Điều chỉnh style tokens phải giữ trạng thái semantic success/warning/error dễ phân biệt và không đổi Live View #17191C.
3. Thay điều hướng phải giữ PIN gate cho Camera, Printer, Events, Settings và hỗ trợ shortcut/tab switch.
4. Sizing/scroll sửa đổi có thể ảnh hưởng Camera preview, Frame Designer canvas, Smart Beauty preview và Guest Review.
5. Không thay capture/audio/printing/QR logic trong audit này; kiểm tra runtime sau này cần tránh tạo print thật hoặc upload.
6. Không dùng screenshot hay test widgets hiện có làm bằng chứng cho các trang/dialog không được chụp/quan sát.

## 10. Nội dung chưa thể kiểm chứng

- Render hiện tại của tất cả 20 nhóm màn hình/component.
- Clipping/overflow, DPI 125–200%, cửa sổ bị giới hạn, focus/keyboard navigation, hover/disabled state.
- Touch target spacing và thao tác một tay trên màn kiosk.
- Camera preview/actual frame, countdown audio, capture failure/retake visual states.
- Empty states thực tế với event/library rỗng.
- In-app QR dialog, printer status và error modals bằng dữ liệu runtime.
- Accessibility contrast và screen reader semantics.
- Tái hiện rủi ro ghi đè session bằng Simulator.
- Các finding Severity Medium/Low là source-based, chưa có screenshot xác nhận.

## 11. Đề xuất thứ tự xử lý sau khi báo cáo được duyệt

1. Đặc tả và kiểm thử bảo toàn session/ảnh sau partial failure (UI-FUNC-01).
2. Chốt ngoại lệ màu QR/Filter so với Soft Taupe; sau đó kiểm tra screenshot (UI-VIS-01/02).
3. Định nghĩa contract ID cho page navigation và quyền PIN (UI-ARCH-01).
4. Bổ sung visual/DPI/touch acceptance coverage trước khi tuyên bố responsive pass (UI-RESP-01).
5. Xác định empty-state copy và kiểm tra các card frame ở từng context (UI-UX-01, UI-CONS-01).
6. Rà soát icon vocabulary sau khi có Windows screenshot hiện hành (UI-VIS-03).

Đây là thứ tự kiểm chứng/đặc tả, không phải quyết định thiết kế hay phê duyệt triển khai.

## 12. Acceptance criteria cho vòng kiểm chứng UI tiếp theo

- Mỗi màn hình trong inventory có ít nhất một ảnh runtime hiện hành, tên ảnh gắn với screen/state/resolution.
- Các màn chính và dialog quan trọng được chụp ở minimum supported resolution và 1366×768, 1600×900, 1920×1080.
- DPI 100%, 125%, 150%, 200% được ghi nhận; không có button/text bị cắt, và mọi overflow có scroll cue.
- Mọi flow có empty/loading/disabled/error/success state được kiểm chứng hoặc được ghi rõ là không áp dụng.
- Touch control chính đạt tiêu chí kích thước/khoảng cách do product duyệt; keyboard focus đi theo thứ tự có thể dự đoán.
- Palette được so bằng token/source và screenshot; semantic status colors cùng Live View có tiêu chí ngoại lệ rõ.
- Session retry sau lỗi không ghi đè ảnh/session cũ khi chưa có hành động được xác nhận.
- Tab/page access tests bám ID/permission contract và giữ nguyên nhóm protected pages.
- Không thao tác printer thật, upload, xóa hoặc thay đổi config production trong bước runtime.

## 13. File/test/status record

**File được tạo:** docs/UI_AUDIT_VALIDATION.md  
**Screenshot mới:** Không có.  
**Files khác đã thay đổi trong lượt audit:** Không có.

**Tests:** Chỉ đọc test source, không chạy. Đã rà các test có liên quan gồm test_desktop_gui.py, test_v200_rc2_hardening.py, test_kiosk_face_eye_af_capture.py, test_camera_connection_manager.py, test_frames_and_designer.py, test_processing_and_templates.py và test_audio_and_frame_gallery_final.py. Report ghi coverage gaps theo đó.

**Git status trước audit (tóm tắt):**
- Branch feature/v2.0.0-photobooth.
- 18 modified tracked paths có sẵn trong audio, camera backend/manager, desktop styles/widgets và test_v200_rc2_hardening.py.
- Untracked có .agents/skills (9 Spec Kit skill folders), .specify/, docs/BASELINE_AUDIT_VALIDATION.md, docs/BASELINE_SYSTEM_AUDIT.md, test_dynamic_countdown_voice_sync.py và test_simulator_countdown_audio_timeline.py.
- Những thay đổi này không do audit hiện tại tạo.

**Git status sau audit:** Các mục trên không đổi; chỉ có thêm docs/UI_AUDIT_VALIDATION.md. Không reset, checkout, stash, clean, commit hoặc tag.

## Appendix — source/test references

- Navigation and main design tokens: vietphotobooth/desktop/main_window.py, MainWindow; vietphotobooth/desktop/styles.py.
- Screen implementations: vietphotobooth/desktop/widgets/*.py; full source inventory is in Section 4.
- Partial failure/session path: vietphotobooth/desktop/widgets/kiosk_page.py, start_capture_flow, _trigger_shot, _abort_capture_due_to_disconnect, _execute_photo_capture, _reset_to_idle; vietphotobooth/camera/connection_manager.py, capture_photo.
- QR palette: vietphotobooth/desktop/widgets/events_page.py, _open_qr_dialog_ui.
- Filter palette/sizing: vietphotobooth/desktop/widgets/filter_editor_page.py, FilterEditorPage/FilterEditorDialog.
- Empty states: vietphotobooth/desktop/widgets/frame_gallery_page.py, refresh_gallery; events_page.py, _refresh_gallery.
- Separate frame cards: frame_gallery_page.py::FrameCard; kiosk_page.py::FrameCardWidget; guest_review_dialog.py::ReviewFrameCard.
- Tests referenced above are inspected only; none executed.

