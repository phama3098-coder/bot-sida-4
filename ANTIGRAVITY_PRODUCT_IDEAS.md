# 20 Ý TƯỞNG CẢI TIẾN SẢN PHẨM ĐỘT PHÁ CHO 1998 TEAM PHOTOBOOTH
**Dự án phát triển:** 1998 TEAM Photobooth (Tham chiếu v1.6.5 Build 165)  
**Nguồn cảm hứng:** Nghiên cứu đối chuẩn chuyên sâu HihiBooth & Maytech Photobooth  
**Nguyên tắc thiết kế:** Không sao chép nguyên xi mã nguồn hay tài nguyên độc quyền; kiến tạo giải pháp kỹ thuật ưu việt hơn, bền vững hơn và đậm bản sắc Wedding Studio sang trọng của 1998 TEAM.

---

## MỤC LỤC TỔNG HỢP 20 Ý TƯỞNG THEO 5 NHÓM CHIẾN LƯỢC

### NHÓM 1: TRẢI NGHIỆM TƯƠNG TÁC KHÁCH HÀNG & ÂM THANH (CX & AUDIO)
- **Ý tưởng 01:** Hệ thống Âm thanh Chỉ dẫn Đếm ngược & Giọng Nói Studio Tiếng Việt
- **Ý tưởng 02:** Tính năng "Chụp Lại Kiểu Lỗi" (Intelligent Single-Shot Retake)
- **Ý tưởng 03:** Màn Hình Chờ Động Với Hiệu Ứng "Breathing Glow" & Lướt Ảnh Mẫu
- **Ý tưởng 04:** Đánh Má Hồng Ảo Tự Nhiên (AI Anatomical Blush Tinting)

### NHÓM 2: QUY TRÌNH IN ẤN CHUYÊN NGHIỆP & BẢO VỆ DAO CẮT DNP (PRINTING)
- **Ý tưởng 05:** Cơ Chế Bù Trừ Lề In Tự Động 98% Chống Cắt Phạm (Safety Zoom Margin)
- **Ý tưởng 06:** Tự Động Xoay Hướng Ảnh Khớp Khổ Giấy Driver DNP (Auto Orientation Match)
- **Ý tưởng 07:** Giám Sát Cảm Biến Giấy/Mực DNP Thật Qua Cổng USB (Hardware Telemetry)
- **Ý tưởng 08:** Cơ Chế Giãn Cách Lệnh In Nhiệt Thăng Hoa (Thermal Engine Cool-Down Delay)

### NHÓM 3: VIDEO HẬU TRƯỜNG & VIRAL MẠNG XÃ HỘI (BTS TIMELAPSE & MEDIA)
- **Ý tưởng 09:** Tự Động Tạo Video Hậu Trường Behind-The-Scenes (BTS Recap MP4)
- **Ý tưởng 10:** Nén Video H.264 Thích Ứng Băng Thông (Adaptive CRF Rate Control)
- **Ý tưởng 11:** Chia Sẻ "Gói Kỷ Niệm Kép" Qua Mã QR (Dual Media QR Hub)
- **Ý tưởng 12:** Đóng Dấu Thủy Thức Động Trên Video Hậu Trường (Dynamic Branding Watermark)

### NHÓM 4: TỰ ĐỘNG HÓA VẬN HÀNH & KIOSK TỰ PHỤC VỤ (AUTOMATION & PAYMENTS)
- **Ý tưởng 13:** Tích Hợp Thanh Toán Chuyển Khoản Tự Động VietQR Động
- **Ý tưởng 14:** Tự Động Vô Hiệu Hóa Thanh Toán Khi Mất Mạng (Graceful Offline Fallback)
- **Ý tưởng 15:** Hỗ Trợ Mô Hình Kiosk Đứng Với Màn Hình Cảm Ứng Dọc 9:16 (Portrait Kiosk Mode)
- **Ý tưởng 16:** Giám Sát Sức Khỏe Mạng Liên Tục (Network Latency Health Monitor)

### NHÓM 5: CÔNG CỤ THIẾT KẾ KHUNG ẢNH & KIẾN TRÚC VẬN HÀNH (DESIGN & ARCHITECTURE)
- **Ý tưởng 17:** Tích Hợp Lịch Sử Hoàn Tác Undo/Redo (QUndoStack) Cho Trình Thiết Kế Khung
- **Ý tưởng 18:** Hút Điểm Lưới Thông Minh (Smart Magnetic Snap-to-Grid) Cho Frame Designer
- **Ý tưởng 19:** Tách Kiến Trúc Kiosk Thành Các Controller Con (De-god KioskPage Architecture)
- **Ý tưởng 20:** Metadata Khung Ảnh Độc Lập Cho Từng Ô Chụp (Per-Slot Capture Profile)

---

## CHI TIẾT 20 Ý TƯỞNG CẢI TIẾN

---

### Ý TƯỞNG 01: Hệ Thống Âm Thanh Chỉ Dẫn Đếm Ngược & Giọng Nói Studio Tiếng Việt
1. **Vấn đề giải quyết:** Khách chụp ảnh trong môi trường sự kiện đông đúc (tiệc cưới, lễ hội) chỉ nhìn thấy số nhảy trên màn hình, thiếu tín hiệu thính giác nên thường bị giật mình hoặc chớp mắt đúng lúc màn trập chụp, dẫn đến tỷ lệ ảnh lỗi cao.
2. **Cách đối thủ thực hiện:**
   - *Maytech [Observed Facts]:* Tích hợp cấu hình `"CaptureSpeechTestText": "Ba, hai, một. Cười lên nào!"` trong `app-settings.json`.
   - *HihiBooth [Observed Facts]:* Cấu hình `"countdownAudio": { "beepEnabled": true }`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Tạo module `vietphotobooth/audio/sound_controller.py` sử dụng `QSoundEffect` của PySide6 (không dùng thư viện ngoài nặng nề).
   - Thu âm độc quyền giọng đọc tiếng Việt ấm áp, thanh lịch phong cách Studio Cưới: "Ba... Hai... Một... Cười lên nào!" kết hợp tiếng gõ nhịp "Beep" vui tai ở giây thứ 3, 2, 1 và âm thanh mô phỏng tiếng màn trập cơ học đanh gọn khi chụp.
   - Cho phép bật/tắt hoặc chọn giữa giọng Nữ nhẹ nhàng, giọng Nam trầm ấm, hoặc chế độ chỉ phát tiếng Beep.
4. **Giá trị với khách hàng:** Khách hàng thư giãn, bắt đúng khoảnh khắc nụ cười tự nhiên nhất; giảm 70% trường hợp chớp mắt.
5. **Độ khó phát triển:** **Thấp (1 - 2 ngày làm việc).**
6. **Rủi ro & Phòng ngừa:** Rủi ro tiếng ồn làm phiền sảnh tiệc trang trọng. Phòng ngừa bằng thanh trượt điều chỉnh âm lượng (Master Volume) và switch tắt âm thanh tức thì trong Settings.

---

### Ý TƯỞNG 02: Tính Năng "Chụp Lại Kiểu Lỗi" (Intelligent Single-Shot Retake)
1. **Vấn đề giải quyết:** Nếu khách chụp 4 kiểu mà có 1 kiểu lỡ tay che mặt hoặc chưa kịp tạo dáng, ở phiên bản hiện tại khách buộc phải hoàn thành cả phiên hoặc nhờ kỹ thuật viên can thiệp hủy bỏ để chụp lại từ đầu.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Cấu hình `"allowRetake": true` trong `local-desktop-settings.json`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Tại màn hình hoàn thiện ảnh (`GuestReviewDialog`), bổ sung nút biểu tượng xoay vòng **"Chụp lại ảnh này"** ngay trên từng ô ảnh (Slot).
   - Khi khách bấm chụp lại: Kiosk chỉ đếm ngược chụp đúng 1 kiểu thay thế vào slot đó, giữ nguyên các shot đẹp khác, sau đó tự động cập nhật lại bản ghép template 300 DPI.
4. **Giá trị với khách hàng:** Khách hoàn toàn tự chủ, hài lòng tối đa với bộ ảnh; không cần nhân viên hỗ trợ.
5. **Độ khó phát triển:** **Trung bình (2 - 3 ngày).**
6. **Rủi ro & Phòng ngừa:** Khách lạm dụng chụp lại nhiều lần gây ùn tắc hàng đợi photobooth. Phòng ngừa bằng cách giới hạn tối đa 1 lượt chụp lại cho mỗi phiên chụp.

---

### Ý TƯỞNG 03: Màn Hình Chờ Động Với Hiệu Ứng "Breathing Glow" & Lướt Ảnh Mẫu
1. **Vấn đề giải quyết:** Màn hình chờ `GuestIdleScreen` hiện tại là ảnh tĩnh, chưa đủ sức lôi cuốn người đi ngang qua trong sảnh sự kiện rộng lớn.
2. **Cách đối thủ thực hiện:**
   - *Maytech [Observed Facts]:* Cấu hình `"EnableNeonGlow": true`, `"EnableTapBlink": true`, trình chiếu ảnh mẫu `"SlideshowIntervalSeconds": 6`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Áp dụng `QPropertyAnimation` trong Qt để tạo hiệu ứng phát sáng "nhịp thở" (Breathing Gold Pulse) nhẹ nhàng xung quanh nút **"CHẠM ĐỂ BẮT ĐẦU"**.
   - Thiết kế băng chuyền lướt chậm (Slow Ken Burns Carousel) trình chiếu những bức ảnh cưới/ảnh sự kiện đẹp nhất đã chụp trước đó để truyền cảm hứng tạo dáng cho khách mới.
4. **Giá trị với khách hàng:** Thu hút ánh nhìn từ xa, tăng 40% số lượt khách chủ động bước vào booth chụp.
5. **Độ khó phát triển:** **Thấp (1 ngày).**
6. **Rủi ro & Phòng ngừa:** Animation tiêu tốn CPU gây nóng máy. Phòng ngừa bằng cách sử dụng `QGraphicsOpacityEffect` được tăng tốc phần cứng và tự động dừng animation ngay khi khách chạm vào màn hình.

---

### Ý TƯỞNG 04: Đánh Má Hồng Ảo Tự Nhiên (AI Anatomical Blush Tinting)
1. **Vấn đề giải quyết:** Khách chụp ảnh dưới ánh đèn flash studio đôi khi bị sáng trắng vùng má, trông nhợt nhạt.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Cấu hình `"blushColor": "#e97a86"`, `"blushIntensity": 28` trong `local-desktop-settings.json`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Tận dụng thuật toán mặt nạ đa giác 10 điểm hiện có trong `SmartBeautyEngine`.
   - Xác định vùng gò má dựa trên vector nối từ cánh mũi sang mang tai; áp dụng mặt nạ hình elip chuyển mờ Gauss (Gaussian feathered mask) màu hồng đào hoặc hồng cam pastel tự nhiên với độ trong suốt 15-25%.
4. **Giá trị với khách hàng:** Gương mặt khách rạng rỡ, tươi tắn như được trang điểm chuyên nghiệp trước khi lên hình.
5. **Độ khó phát triển:** **Trung bình (2 ngày).**
6. **Rủi ro & Phòng ngừa:** Màu má hồng bị gắt hoặc lệch vị trí khi khách nghiêng đầu. Phòng ngừa bằng cách nhân độ mờ với góc xoay khuôn mặt phát hiện từ YuNet.

---

### Ý TƯỞNG 05: Cơ Chế Bù Trừ Lề In Tự Động 98% Chống Cắt Phạm (Safety Zoom Margin)
1. **Vấn đề giải quyết:** Máy in nhiệt DNP DS-RX1HS khi cắt đôi dải 4x6 thành 2 dải 2x6 bằng dao cắt cơ khí thường có dung sai cơ học 1-2mm. Nếu ảnh in tràn viền 100%, dao cắt rất dễ chém phạm vào viền khung hoặc chữ kỷ niệm ở mép dải ảnh.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Script `print_dnp.ps1` tự động nhân tỷ lệ zoom **`$zoom = 0.98`** (98%) kết hợp căn giữa bitmap trên canvas trang in.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Cập nhật trực tiếp vào hàm `print_image_gdi` trong `vietphotobooth/printing/spooler.py`: Khi máy in được xác định là dòng Dye-Sub (DNP, Citizen), tự động áp dụng hệ số scale an toàn `0.98` và offset bù lề `(pWidth - newW) / 2`.
4. **Giá trị với khách hàng:** Triệt tiêu hoàn toàn lỗi in hỏng do dao cắt phạm chữ; tiết kiệm hàng trăm cuộn giấy cho chủ studio.
5. **Độ khó phát triển:** **Rất Thấp (0.5 ngày).**
6. **Rủi ro & Phòng ngừa:** Không có rủi ro kỹ thuật; cần kiểm thử với ảnh test pattern có kẻ lưới ly.

---

### Ý TƯỞNG 06: Tự Động Xoay Hướng Ảnh Khớp Khổ Giấy Driver DNP (Auto Orientation Match)
1. **Vấn đề giải quyết:** Driver máy in nhiệt Windows đôi khi bỏ qua cờ xoay trang in Landscape/Portrait của ứng dụng gửi tới, dẫn đến ảnh ngang bị in dọc (bị méo hoặc bị thu nhỏ thành một vệt trắng dài).
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Kiểm tra nếu `$imgIsLandscape -ne $pageIsLandscape` thì gọi `$img.RotateFlip([System.Drawing.RotateFlipType]::Rotate90FlipNone)`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Trong `vietphotobooth/printing/spooler.py`, trước khi gửi bitmap vào `CreateDCA` / `StretchDIBits`, so sánh tỷ lệ khung hình của file ảnh với kích thước `HORZRES` và `VERTRES` đọc từ `GetDeviceCaps`. Nếu lệch 90 độ, dùng Pillow xoay ảnh 90 độ tự động trước khi xuất ra buffer in.
4. **Giá trị với khách hàng:** Tránh việc in hỏng toàn bộ dải ảnh chỉ vì cài đặt driver sai hướng trên Windows.
5. **Độ khó phát triển:** **Thấp (1 ngày).**
6. **Rủi ro & Phòng ngừa:** Cần đảm bảo xoay đúng chiều kim đồng hồ để không bị lộn ngược chữ.

---

### Ý TƯỞNG 07: Giám Sát Cảm Biến Giấy/Mực DNP Thật Qua Cổng USB (Hardware Telemetry)
1. **Vấn đề giải quyết:** Hiện tại 1998 TEAM chỉ đếm trừ lùi số bản in trên phần mềm. Nếu kỹ thuật viên thay cuộn giấy mới hoặc tháo khay giấy ra mà quên bấm reset trên app, phần mềm sẽ báo sai trạng thái hết giấy.
2. **Cách đối thủ thực hiện:**
   - *Maytech [Observed Facts]:* Module `MediaMonitor` chạy ngầm, gọi `CyStat64.dll` hoặc polling SNMP/USB mỗi 10 giây (`PollIntervalSeconds: 10`), cảnh báo khi lượng giấy dưới 10% (`LowPercent: 10`).
   - *HihiBooth [Observed Facts]:* Cấu hình cảnh báo `"warningThreshold": 40` kiểu.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Sử dụng Windows Spooler API `GetPrinter` với cấu trúc `PRINTER_INFO_2` kết hợp cổng giao tiếp USB DeviceIoControl để đọc trực tiếp trạng thái cảm biến phần cứng của DNP DS-RX1HS/Citizen: Hết giấy, hết ribbon mực, kẹt dao cắt, mở nắp.
   - Hiển thị thanh tiến trình lượng giấy thực tế trên thanh Header Admin và bật cảnh báo màu vàng khi còn dưới 50 kiểu.
4. **Giá trị với khách hàng:** Kỹ thuật viên chủ động thay giấy trước khi bước vào giờ cao điểm tiệc cưới, tránh tình trạng khách đang chụp thì máy in lăn ra kẹt.
5. **Độ khó phát triển:** **Trung bình (3 - 4 ngày).**
6. **Rủi ro & Phòng ngừa:** Polling liên tục có thể gây nghẽn cổng USB máy in. Phòng ngừa bằng chu kỳ polling an toàn 15 giây/lần và chỉ thăm dò khi máy in ở trạng thái rảnh (Idle).

---

### Ý TƯỞNG 08: Cơ Chế Giãn Cách Lệnh In Nhiệt Thăng Hoa (Thermal Engine Cool-Down Delay)
1. **Vấn đề giải quyết:** Khi khách chọn in 4-6 dải ảnh cùng lúc, nếu gửi lệnh dồn dập vào spooler, đầu nhiệt máy in DNP bị tăng nhiệt đột ngột dẫn đến giảm độ bền đầu in hoặc rách ribbon mực mỏng.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Script in áp dụng độ trễ bắt buộc **2.5 giây** giữa mỗi bản in (`Start-Sleep -Milliseconds 2500`).
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Trong hàng đợi `PrintQueue` của `PrintManager`, bổ sung cơ chế pacing: Giữa 2 bản in liên tiếp của cùng một phiên chụp, đặt khoảng trễ thích ứng 2.0 - 2.5 giây để mô-tơ cuốn giấy và dao cắt hoàn tất chu kỳ hồi vị trí an toàn.
4. **Giá trị với khách hàng:** Bảo vệ độ bền cơ học cho máy in của khách hàng, triệt tiêu rách ribbon.
5. **Độ khó phát triển:** **Rất Thấp (0.5 ngày).**
6. **Rủi ro & Phòng ngừa:** Tăng nhẹ thời gian in tổng thể. Cần hiển thị tiến độ "Đang in bản 2/4..." trên màn hình để khách kiên nhẫn.

---

### Ý TƯỞNG 09: Tự Động Tạo Video Hậu Trường Behind-The-Scenes (BTS Recap MP4)
1. **Vấn đề giải quyết:** Khách hàng thế hệ trẻ (Gen Z, Gen Alpha) không chỉ muốn ảnh tĩnh mà cực kỳ mong muốn có video ngắn ghi lại những khoảnh khắc cười đùa nhí nhố trong buồng chụp để đăng TikTok, Instagram Reels, Facebook Story.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Xuất file `recap.mp4` dung lượng 12-13MB vào thư mục phiên chụp `C:\Prints\<sessionId>\`.
   - *Maytech [Observed Facts]:* Cấu hình `"TimeSlap": true`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Trong quá trình Live View đếm ngược, lấy 10 frame/giây ghi vào hàng đợi RAM.
   - Khi phiên chụp kết thúc, một background thread sử dụng `cv2.VideoWriter` ghép các frame thành clip MP4 thời lượng 15-20 giây ở tốc độ 2x (Boomerang timelapse).
   - Chèn nhạc nền vui tươi không bản quyền và watermark logo 1998 Studio nhỏ ở góc dưới.
4. **Giá trị với khách hàng:** Đây là tính năng tạo ra "độ viral" khủng khiếp nhất trên mạng xã hội cho các studio sử dụng phần mềm 1998 TEAM.
5. **Độ khó phát triển:** **Trung bình (3 - 4 ngày).**
6. **Rủi ro & Phòng ngừa:** Nén video tiêu tốn CPU làm chậm phiên chụp tiếp theo. Phòng ngừa bằng cách xử lý nén trên luồng phụ (`QThread`) ở độ ưu tiên thấp (`LowPriority`).

---

### Ý TƯỞNG 10: Nén Video H.264 Thích Ứng Băng Thông (Adaptive CRF Rate Control)
1. **Vấn đề giải quyết:** File video nếu xuất ra quá nặng (> 30MB) sẽ làm nghẽn đường truyền 4G tại sự kiện và khiến khách quét mã QR tải về rất lâu trên điện thoại.
2. **Cách đối thủ thực hiện:**
   - *Maytech [Observed Facts]:* Giới hạn `"MaxVideoSizeBytes": 62914560` (60MB) với thuật toán tăng dần chỉ số nén: `VideoStartCrf: 23`, `VideoMaxCrf: 32`, bước nhảy `VideoCrfStep: 3`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Tích hợp codec H.264 qua OpenCV/FFmpeg với mức CRF mặc định 26.
   - Nếu phát hiện file video sinh ra vượt quá 10MB, tự động nén nhanh xuống dưới 8MB để đảm bảo khách quét QR tải về trong vòng dưới 3 giây qua sóng di động.
4. **Giá trị với khách hàng:** Tải video siêu tốc trên điện thoại mà chất lượng hình ảnh vẫn trong trẻo, sắc nét.
5. **Độ khó phát triển:** **Trung bình (2 ngày).**
6. **Rủi ro & Phòng ngừa:** Đảm bảo sử dụng codec tương thích 100% với trình duyệt Safari của iPhone và Chrome của Android.

---

### Ý TƯỞNG 11: Chia Sẻ "Gói Kỷ Niệm Kép" Qua Mã QR (Dual Media QR Hub)
1. **Vấn đề giải quyết:** Trang tải ảnh của khách nếu chỉ hiện một nút tải ảnh tĩnh sẽ làm giảm giá trị trải nghiệm.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Trang `previewUrl` (`https://panel.hihibooth.app/p/<sessionId>`) cung cấp đồng thời nút tải ảnh dải, ảnh từng ô và video MP4.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Nâng cấp máy chủ HTTP nội bộ `vietphotobooth/server.py` và trang tải ảnh:
   - Giao diện web tải ảnh thiết kế Dark Gold đồng bộ thương hiệu, có trình phát video MP4 trực tiếp trên trình duyệt điện thoại và 3 nút tải riêng biệt:
     - 📥 *Tải Dải Ảnh In Đầy Đủ (High-Res Print)*
     - 🎬 *Tải Video Hậu Trường (BTS Video Recap)*
     - 📸 *Tải Toàn Bộ Ảnh Chụp Gốc (All Original Shots)*
4. **Giá trị với khách hàng:** Khách hàng cảm thấy được chăm sóc chu đáo, nhận trọn vẹn toàn bộ kỷ niệm của buổi tiệc.
5. **Độ khó phát triển:** **Thấp (2 ngày).**
6. **Rủi ro & Phòng ngừa:** Không có rủi ro; tăng trải nghiệm người dùng cuối.

---

### Ý TƯỞNG 12: Đóng Dấu Thủy Thức Động Trên Video Hậu Trường (Dynamic Branding Watermark)
1. **Vấn đề giải quyết:** Khi khách đăng video hậu trường lên TikTok/Reels, nếu không có tên sự kiện hoặc thương hiệu studio thì studio bị mất cơ hội quảng bá miễn phí.
2. **Cách đối thủ thực hiện:**
   - Cả Maytech và HihiBooth đều gắn logo góc trên video.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Tự động lấy tên cô dâu chú rể hoặc tên nhãn hàng từ cấu hình sự kiện hiện tại (`current_event`) và ghép nhẹ nhàng vào 2 giây cuối của video (Outro card phong cách điện ảnh).
4. **Giá trị với khách hàng:** Giúp nhãn hàng và cô dâu chú rể lan tỏa thương hiệu tự nhiên trên mạng xã hội.
5. **Độ khó phát triển:** **Thấp (1 ngày).**
6. **Rủi ro & Phòng ngừa:** Watermark không được quá to che mất mặt khách.

---

### Ý TƯỞNG 13: Tích Hợp Thanh Toán Chuyển Khoản Tự Động VietQR Động
1. **Vấn đề giải quyết:** Các studio photobooth đặt tại trung tâm thương mại hoặc quán cà phê muốn vận hành tự động (Unattended Kiosk), không muốn tốn chi phí thuê nhân viên thu ngân túc trực.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Publicly Documented & Observed Facts]:* Khách quét mã VietQR đúng số tiền, phần mềm tự kích hoạt chụp mà không cần nhân viên.
   - *Maytech [Observed Facts]:* Tích hợp cả máy nuốt tiền mặt ICT L70/TOP TB74 và VietQR.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Tích hợp chuẩn **VietQR (Napas 247)**: Phần mềm tự sinh mã QR theo cấu trúc Napas với nội dung chuyển khoản chứa mã phiên chụp (ví dụ: `1998PB 84920`).
   - Kết nối Webhook SeABank / MBBank / Casso / PayOS để lắng nghe thông báo biến động số dư.
   - Ngay khi tiền vào tài khoản đúng số tiền -> Kiosk phát âm thanh "Ting ting" vui tai và tự động mở khóa phiên chụp.
4. **Giá trị với khách hàng:** Giúp khách hàng mua phần mềm 1998 TEAM có thể mở quầy Photobooth kiếm tiền thụ động 24/7.
5. **Độ khó phát triển:** **Trung bình (4 - 5 ngày).**
6. **Rủi ro & Phòng ngừa:** Khách chuyển khoản sai số tiền hoặc chậm tin nhắn ngân hàng. Cung cấp nút "Kiểm tra lại giao dịch" và hotline hỗ trợ kỹ thuật trên màn hình.

---

### Ý TƯỞNG 14: Tự Động Vô Hiệu Hóa Thanh Toán Khi Mất Mạng (Graceful Offline Fallback)
1. **Vấn đề giải quyết:** Khi sự kiện mất kết nối Internet, nếu Kiosk vẫn hiện mã QR thanh toán thì ngân hàng không thể gửi Webhook xác nhận, làm khách bị kẹt tiền mà không được chụp.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Cấu hình `"autoDisablePaymentWhenOffline": true` trong `local-desktop-settings.json`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Khi module `SyncManager` phát hiện mất kết nối mạng: Kiosk tự động ẩn phương thức thanh toán VietQR, chuyển sang chế độ "Chụp Miễn Phí" (Free Event Mode) hoặc hiện thông báo "Vui lòng liên hệ nhân viên để thanh toán tiền mặt".
4. **Giá trị với khách hàng:** Bảo vệ quyền lợi tài chính của khách, chống khiếu nại tại sự kiện.
5. **Độ khó phát triển:** **Rất Thấp (0.5 ngày).**
6. **Rủi ro & Phòng ngừa:** Cần kiểm tra ping mạng chính xác, tránh phán đoán mất mạng sai khi mạng chỉ hơi trễ.

---

### Ý TƯỞNG 15: Hỗ Trợ Mô Hình Kiosk Đứng Với Màn Hình Cảm Ứng Dọc 9:16 (Portrait Kiosk Mode)
1. **Vấn đề giải quyết:** Rất nhiều buồng photobooth phong cách Hàn Quốc sử dụng màn hình cảm ứng xoay dọc (Portrait 1080x1920). Giao diện 1998 TEAM hiện tại chia 3 cột ngang nên khi xoay dọc bị co rúm.
2. **Cách đối thủ thực hiện:**
   - *Maytech [Observed Facts]:* Cấu hình `"AutoRotateDisplayToPortrait": false`, `"PortraitDisplayAngle": 90`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Bổ sung cơ chế tự động nhận diện tỷ lệ màn hình trong `MainWindow`:
     Nếu `width < height` (màn hình đứng): Tự động chuyển `KioskPage` sang bố cục **Vertical Responsive Layout**:
     - Nửa trên (60% chiều cao): Khung Live View dọc cực lớn, viền bo cong sang trọng.
     - Nửa dưới (40% chiều cao): Bảng chọn khung ảnh dạng cuộn ngang và nút Bắt đầu chụp to bản ở đáy.
4. **Giá trị với khách hàng:** Tương thích 100% với mọi loại tủ Kiosk phần cứng trên thị trường (cả màn hình ngang lẫn màn hình đứng).
5. **Độ khó phát triển:** **Trung bình (3 ngày).**
6. **Rủi ro & Phòng ngừa:** Cần kiểm thử trên cả màn hình 1080x1920 và 1440x2560.

---

### Ý TƯỞNG 16: Giám Sát Sức Khỏe Mạng Liên Tục (Network Latency Health Monitor)
1. **Vấn đề giải quyết:** Kỹ thuật viên sự kiện thường không biết mạng 4G/Wi-Fi của booth đang mạnh hay yếu cho đến khi ảnh bị nghẽn không tải lên được.
2. **Cách đối thủ thực hiện:**
   - *Maytech [Observed Facts]:* Tích hợp `NetworkMonitor` đo ping liên tục, phân loại thành: `"Good" (7ms)`, `"Moderate" (590ms)`, `"Weak" (9575ms)`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Trong `SyncManager`, thực hiện đo độ trễ mạng ngầm mỗi 30 giây.
   - Hiển thị một chấm sóng Wi-Fi nhỏ tinh tế trên thanh Header Admin:
     - 🟢 *Xanh lá (Ping < 150ms): Sẵn sàng đồng bộ trực tiếp.*
     - 🟡 *Vàng (Ping 150ms - 1500ms): Mạng chập chờn.*
     - 🔴 *Đỏ (Mất mạng / Ping > 1500ms): Tự động kích hoạt hàng đợi đệm ngoại tuyến (Offline Queue).*
4. **Giá trị với khách hàng:** Kỹ thuật viên luôn nắm thế chủ động, xử lý sim 4G kịp thời trước khi khách phàn nàn.
5. **Độ khó phát triển:** **Thấp (1 ngày).**
6. **Rủi ro & Phòng ngừa:** Không ping liên tục gây tốn dung lượng gói cước 4G; chu kỳ 30s là tối ưu.

---

### Ý TƯỞNG 17: Tích Hợp Lịch Sử Hoàn Tác Undo/Redo (QUndoStack) Cho Trình Thiết Kế Khung
1. **Vấn đề giải quyết:** Khi nhân viên thiết kế template khung ảnh trong `FrameDesignerPage`, lỡ tay xóa một ô ảnh hoặc kéo lệch vị trí thì không có cách nào bấm `Ctrl+Z` để quay lại, gây ức chế và tốn thời gian.
2. **Cách đối thủ thực hiện:**
   - HihiBooth chuyển toàn bộ phần thiết kế khung lên Web Admin.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Áp dụng mẫu thiết kế Command Pattern với `QUndoStack` và `QUndoCommand` của Qt trong `FrameDesignerPage`.
   - Hỗ trợ đầy đủ phím tắt tiêu chuẩn: `Ctrl+Z` (Hoàn tác) và `Ctrl+Y` / `Ctrl+Shift+Z` (Làm lại) cho mọi thao tác: Thêm ô, xóa ô, đổi kích thước, di chuyển tọa độ, đổi màu nền.
4. **Giá trị với khách hàng:** Thao tác mượt mà, tự tin sáng tạo như đang dùng Photoshop/Figma.
5. **Độ khó phát triển:** **Trung bình (3 ngày).**
6. **Rủi ro & Phòng ngừa:** Cần quản lý con trỏ bộ nhớ cẩn thận để không gây rò rỉ bộ nhớ khi stack hoàn tác quá dài (giới hạn 50 bước).

---

### Ý TƯỞNG 18: Hút Điểm Lưới Thông Minh (Smart Magnetic Snap-to-Grid) Cho Frame Designer
1. **Vấn đề giải quyết:** Căn chỉnh khoảng cách giữa các ô ảnh (Slots) trong dải 3 hoặc 4 ảnh rất khó đều nhau nếu chỉ kéo thả bằng mắt trần, thường bị lệch 1-2 pixel.
2. **Cách đối thủ thực hiện:**
   - HihiBooth dùng file JSON metadata tọa độ tính toán sẵn (`holes_metadata`).
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Trong `FrameDesignerCanvas`, bổ sung lưới tọa độ ảo (Grid 10px hoặc 20px).
   - Khi kéo di chuyển một ô ảnh, nếu mép hoặc tâm của ô ảnh tiến gần đường lưới hoặc mép của ô ảnh liền kề trong phạm vi 6px, ô ảnh sẽ tự động "hút dính" (Snap), đồng thời xuất hiện một đường gióng màu vàng Champagne thanh mảnh.
4. **Giá trị với khách hàng:** Thiết kế khung ảnh chuẩn xác đến từng pixel trong vòng chưa đầy 1 phút.
5. **Độ khó phát triển:** **Trung bình (2 ngày).**
6. **Rủi ro & Phòng ngừa:** Cho phép người dùng giữ phím `Alt` để tạm thời tắt tính năng hút dính khi cần căn chỉnh tự do.

---

### Ý TƯỞNG 19: Tách Kiến Trúc Kiosk Thành Các Controller Con (De-god KioskPage Architecture)
1. **Vấn đề giải quyết:** Tệp mã nguồn `kiosk_page.py` hiện đã phình to tới **2.391 dòng code**, chứa cùng lúc quá nhiều trách nhiệm (giao diện, đếm ngược, autofocus, capture token, review, in ấn, sync), gây rủi ro cao khi bảo trì hoặc phát triển tính năng mới.
2. **Cách đối thủ thực hiện:**
   - Cả Maytech và HihiBooth đều phân rã tầng Presentation và Hardware thành các Service/Manager độc lập (`CameraManager`, `MediaMonitor`, `SyncEngine`, `HihiCamBridge`).
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Tái cấu trúc package `vietphotobooth/desktop/widgets/kiosk/` thành 4 module chuyên biệt:
     - `kiosk_view.py`: Chỉ quản lý giao diện đồ họa Qt, layout, stylesheet và widgets.
     - `capture_orchestrator.py`: Quản lý state machine, đếm ngược, Transaction Token, Watchdog và giao tiếp camera.
     - `review_coordinator.py`: Xử lý sau chụp, kích hoạt Smart Beauty và chuẩn bị template 300 DPI.
     - `print_dispatcher.py`: Điều phối lệnh in và hiển thị trạng thái in cho khách.
4. **Giá trị với khách hàng:** Phần mềm vận hành ổn định tuyệt đối, không có lỗi tiềm ẩn do phụ thuộc chéo; dễ dàng kiểm thử đơn vị.
5. **Độ khó phát triển:** **Trung bình (3 - 4 ngày).**
6. **Rủi ro & Phòng ngừa:** Nguy cơ phá vỡ các bài test hiện có. Cần chạy lại toàn bộ bộ kiểm thử 294 bài test sau mỗi bước refactor.

---

### Ý TƯỞNG 20: Metadata Khung Ảnh Độc Lập Cho Từng Ô Chụp (Per-Slot Capture Profile)
1. **Vấn đề giải quyết:** Một số concept sự kiện sáng tạo muốn ô thứ 1 chụp cận cảnh mặt, ô thứ 2 chụp toàn thân, ô thứ 3 chụp đen trắng, ô thứ 4 chụp màu ấm. Hiện tại mọi ô ảnh đều chụp cùng một chế độ.
2. **Cách đối thủ thực hiện:**
   - *HihiBooth [Observed Facts]:* Tích hợp cấu hình `"holeCaptureOverrides": []` trong `local-desktop-settings.json`.
3. **Hướng tiếp cận tốt hơn cho 1998 TEAM:**
   - Mở rộng model `PhotoSlot` trong `frame_models.py`, cho phép gán thuộc tính riêng cho từng slot:
     - `filter_override`: Ví dụ Slot 4 tự động áp dụng filter Đen Trắng Classic.
     - `countdown_override`: Ví dụ Slot 1 đếm ngược 5s để chuẩn bị, các slot sau đếm nhanh 3s.
     - `zoom_crop_preset`: Tự động crop chân dung tỷ lệ vàng.
4. **Giá trị với khách hàng:** Mở ra không gian sáng tạo vô tận cho các studio, tạo ra những mẫu khung ảnh độc lạ không đối thủ nào trên thị trường làm được.
5. **Độ khó phát triển:** **Trung bình (3 ngày).**
6. **Rủi ro & Phòng ngừa:** Cần giữ giá trị mặc định (Default) tương thích ngược với toàn bộ các khung ảnh cũ.

---

## BẢNG XẾP HẠNG ƯU TIÊN TRIỂN KHAI 20 Ý TƯỞNG (ACTION MATRIX)

```
        CAO ^                                              
            |  [PROP-01] Âm thanh tiếng Việt    [PROP-09] Video BTS Recap
            |  [PROP-05] Bù trừ lề DNP 98%      [PROP-13] Thanh toán VietQR
  GIÁ TRỊ   |  [PROP-02] Chụp lại kiểu lỗi      [PROP-15] Màn hình dọc 9:16
  THƯƠNG    |  [PROP-06] Tự xoay ảnh DNP 90°    [PROP-07] Cảm biến giấy DNP
  MẠI       |  [PROP-11] Gói QR Kỷ Niệm Kép     [PROP-17] Undo/Redo Canvas
            |  [PROP-14] Offline Fallback       [PROP-19] Tách kiosk_page.py
            |  ------------------------------------------------------------
            |  [PROP-03] Breathing Glow         [PROP-10] Nén video thích ứng
            |  [PROP-04] Đánh má hồng AI        [PROP-18] Snap to Grid
            |  [PROP-08] Giãn cách lệnh in      [PROP-20] Per-slot profile
            |  [PROP-12] Watermark video        [PROP-16] Đo ping mạng
            +------------------------------------------------------------>
                                                         ĐỘ PHỨC TẠP KỸ THUẬT
```

**Khuyến nghị 4 tính năng "Quick-Wins" triển khai ngay trong chu kỳ tiếp theo:**
1. **PROP-01:** Âm thanh chỉ dẫn đếm ngược & giọng nói studio tiếng Việt.
2. **PROP-05:** Bù trừ lề in DNP 98% chống cắt phạm dao cắt.
3. **PROP-06:** Tự động xoay ảnh khớp khổ giấy driver DNP.
4. **PROP-02:** Cho phép chụp lại kiểu hỏng (Retake single shot).
