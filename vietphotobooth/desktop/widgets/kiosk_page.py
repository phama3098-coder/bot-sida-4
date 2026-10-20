"""
VietPhotoBooth Kiosk Page
The main interactive touch-screen photobooth interface:
Live Camera Preview, 3/5/10s Countdown, Multi-shot Sequence, Real-time Filter & Frame Bar,
Instant Print Dispatch, and Guest LAN QR Code Sharing.
"""

import os
import time
from typing import Optional, List
from PIL import Image
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QScrollArea, QFrame, QSizePolicy, QDialog, QSpinBox, QMessageBox, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QFont, QPainter

from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.filters.filter_engine import FilterEngine, FilterPreset
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_models import FrameTemplate
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class KioskPage(QWidget):
    """Màn hình Photobooth Kiosk chính tương tác cảm ứng cho khách hàng."""

    session_finished = Signal(str) # Bắn tín hiệu khi phiên chụp hoàn tất

    def __init__(
        self,
        camera_mgr: CameraManager,
        filter_engine: FilterEngine,
        frame_mgr: FrameManager,
        print_mgr: PrintManager,
        event_mgr: EventManager,
        token_mgr: TokenManager,
        config_mgr: ConfigManager,
        parent=None
    ):
        super().__init__(parent)
        self.camera_mgr = camera_mgr
        self.filter_engine = filter_engine
        self.frame_mgr = frame_mgr
        self.print_mgr = print_mgr
        self.event_mgr = event_mgr
        self.token_mgr = token_mgr
        self.config_mgr = config_mgr

        # Trạng thái phiên chụp
        self.current_state = "IDLE"  # IDLE, COUNTDOWN, CAPTURING, REVIEW
        self.countdown_remaining = 3
        self.countdown_duration = self.config_mgr.get("kiosk.countdown_sec", 3)
        self.total_shots_needed = 3
        self.current_shot_index = 0
        self.captured_originals: List[Image.Image] = []
        self.captured_paths: List[str] = []
        self.selected_filter_id: str = "natural"
        self.selected_frame_id: Optional[str] = None
        self.current_composite: Optional[Image.Image] = None
        self.current_session_id: Optional[str] = None
        self.current_token: Optional[str] = None

        # Timer Live View Camera (30 fps)
        self.live_view_timer = QTimer(self)
        self.live_view_timer.timeout.connect(self._update_live_view)

        # Timer Countdown (1 giây mỗi nấc)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._on_countdown_tick)

        self._init_ui()
        self._load_initial_templates()
        self.start_live_view()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        # 1. KHU VỰC TRUNG TÂM (LIVE VIEW HOẶC REVIEW KẾT QUẢ)
        self.center_frame = QFrame()
        self.center_frame.setObjectName("card_panel")
        self.center_layout = QVBoxLayout(self.center_frame)
        self.center_layout.setContentsMargins(0, 0, 0, 0)

        # Label hiển thị Video Live View hoặc Ảnh hoàn thiện
        self.lbl_viewport = QLabel()
        self.lbl_viewport.setAlignment(Qt.AlignCenter)
        self.lbl_viewport.setStyleSheet("background-color: #000000; border-radius: 12px;")
        self.lbl_viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_viewport.setMinimumSize(640, 480)
        self.center_layout.addWidget(self.lbl_viewport)

        # Lớp overlay đếm ngược to ở giữa
        self.lbl_countdown = QLabel("", self.lbl_viewport)
        self.lbl_countdown.setAlignment(Qt.AlignCenter)
        self.lbl_countdown.setStyleSheet("color: #FFFFFF; font-size: 130px; font-weight: 900; background: rgba(0,0,0,0.4); border-radius: 30px;")
        self.lbl_countdown.hide()

        # Label trạng thái ảnh ("Đang chụp ảnh 1/3...")
        self.lbl_status_badge = QLabel("", self.lbl_viewport)
        self.lbl_status_badge.setAlignment(Qt.AlignCenter)
        self.lbl_status_badge.setStyleSheet("color: #38BDF8; font-size: 26px; font-weight: bold; background: rgba(15,23,42,0.85); padding: 8px 24px; border-radius: 20px;")
        self.lbl_status_badge.hide()

        self.main_layout.addWidget(self.center_frame, 7)

        # 2. KHU VỰC TÙY CHỌN DẢI BỘ LỌC VÀ KHUNG ẢNH (CUỘN NGANG)
        self.options_panel = QFrame()
        self.options_panel.setObjectName("card_panel")
        self.options_layout = QVBoxLayout(self.options_panel)
        self.options_layout.setContentsMargins(8, 4, 8, 4)

        # Tabs hoặc dải lọc: Bộ Lọc Màu & Mẫu Khung
        strip_label = QLabel("<b>Chọn Bộ Lọc Màu & Khung Hình:</b>")
        strip_label.setStyleSheet("color: #94A3B8; font-size: 13px;")
        self.options_layout.addWidget(strip_label)

        # Scroll area chứa các nút bộ lọc
        self.scroll_filters = QScrollArea()
        self.scroll_filters.setFixedHeight(80)
        self.scroll_filters.setWidgetResizable(True)
        self.scroll_filters.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_filters.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.filter_buttons_container = QWidget()
        self.filter_buttons_layout = QHBoxLayout(self.filter_buttons_container)
        self.filter_buttons_layout.setContentsMargins(4, 4, 4, 4)
        self.filter_buttons_layout.setSpacing(8)
        self.scroll_filters.setWidget(self.filter_buttons_container)
        self.options_layout.addWidget(self.scroll_filters)

        # Scroll area chứa các nút khung
        self.scroll_frames = QScrollArea()
        self.scroll_frames.setFixedHeight(80)
        self.scroll_frames.setWidgetResizable(True)
        self.scroll_frames.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_frames.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.frame_buttons_container = QWidget()
        self.frame_buttons_layout = QHBoxLayout(self.frame_buttons_container)
        self.frame_buttons_layout.setContentsMargins(4, 4, 4, 4)
        self.frame_buttons_layout.setSpacing(8)
        self.scroll_frames.setWidget(self.frame_buttons_container)
        self.options_layout.addWidget(self.scroll_frames)

        self.main_layout.addWidget(self.options_panel, 3)

        # 3. THANH ĐIỀU KHIỂN CHÍNH (NÚT BẤM TO)
        self.bottom_control_bar = QHBoxLayout()
        self.bottom_control_bar.setContentsMargins(0, 4, 0, 4)

        # Bộ chọn thời gian đếm ngược
        self.combo_timer = QComboBox()
        self.combo_timer.addItems(["Đếm ngược: 3 Giây", "Đếm ngược: 5 Giây", "Đếm ngược: 10 Giây"])
        self.combo_timer.currentIndexChanged.connect(self._on_timer_selected)
        self.bottom_control_bar.addWidget(self.combo_timer)

        # NÚT BẮT ĐẦU CHỤP KHỔNG LỒ
        self.btn_start = QPushButton("📸 BẮT ĐẦU CHỤP")
        self.btn_start.setObjectName("btn_big_capture")
        self.btn_start.clicked.connect(self.start_capture_flow)
        self.bottom_control_bar.addWidget(self.btn_start, 1)

        # NÚT THAO TÁC KHI Ở CHẾ ĐỘ XEM KẾT QUẢ (REVIEW)
        self.btn_retake = QPushButton("🔄 Chụp Lại")
        self.btn_retake.setObjectName("btn_secondary")
        self.btn_retake.setMinimumHeight(60)
        self.btn_retake.clicked.connect(self._retake_session)
        self.btn_retake.hide()
        self.bottom_control_bar.addWidget(self.btn_retake)

        self.btn_qr = QPushButton("📱 Quét Mã QR")
        self.btn_qr.setObjectName("btn_secondary")
        self.btn_qr.setMinimumHeight(60)
        self.btn_qr.clicked.connect(self._show_qr_dialog)
        self.btn_qr.hide()
        self.bottom_control_bar.addWidget(self.btn_qr)

        self.btn_print = QPushButton("🖨️ IN ẢNH NGAY")
        self.btn_print.setObjectName("btn_success")
        self.btn_print.setMinimumHeight(60)
        self.btn_print.clicked.connect(self._print_composite)
        self.btn_print.hide()
        self.bottom_control_bar.addWidget(self.btn_print)

        self.btn_finish = QPushButton("✅ Hoàn Tất")
        self.btn_finish.setObjectName("btn_secondary")
        self.btn_finish.setMinimumHeight(60)
        self.btn_finish.clicked.connect(self._finish_session)
        self.btn_finish.hide()
        self.bottom_control_bar.addWidget(self.btn_finish)

        self.main_layout.addLayout(self.bottom_control_bar)

    def _load_initial_templates(self):
        # Tải các nút Filter
        self._populate_filter_strip()
        # Tải các nút Khung
        self._populate_frame_strip()

    def _populate_filter_strip(self):
        # Xóa các nút cũ
        for i in reversed(range(self.filter_buttons_layout.count())):
            w = self.filter_buttons_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        presets = self.filter_engine.get_presets()
        for p in presets:
            btn = QPushButton(f"✨ {p.name}")
            btn.setObjectName("btn_secondary")
            btn.setCheckable(True)
            if p.id == self.selected_filter_id:
                btn.setChecked(True)
                btn.setStyleSheet("background-color: #3B82F6; color: #FFFFFF; font-weight: bold;")
            btn.clicked.connect(lambda checked, pid=p.id: self._on_filter_clicked(pid))
            self.filter_buttons_layout.addWidget(btn)

    def _populate_frame_strip(self):
        for i in reversed(range(self.frame_buttons_layout.count())):
            w = self.frame_buttons_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        frames = self.frame_mgr.list_frames()
        if frames and not self.selected_frame_id:
            self.selected_frame_id = frames[0].id

        for f in frames:
            btn = QPushButton(f"🖼️ {f.name}")
            btn.setObjectName("btn_secondary")
            btn.setCheckable(True)
            if f.id == self.selected_frame_id:
                btn.setChecked(True)
                btn.setStyleSheet("background-color: #EC4899; color: #FFFFFF; font-weight: bold;")
            btn.clicked.connect(lambda checked, fid=f.id: self._on_frame_clicked(fid))
            self.frame_buttons_layout.addWidget(btn)

    def _on_filter_clicked(self, filter_id: str):
        self.selected_filter_id = filter_id
        self._populate_filter_strip()
        if self.current_state == "REVIEW":
            self._render_and_display_composite()

    def _on_frame_clicked(self, frame_id: str):
        self.selected_frame_id = frame_id
        self._populate_frame_strip()
        if self.current_state == "REVIEW":
            self._render_and_display_composite()

    def _on_timer_selected(self, index: int):
        durations = [3, 5, 10]
        self.countdown_duration = durations[index]

    # -------------------------------------------------------------
    # CAMERA LIVE VIEW
    # -------------------------------------------------------------
    def start_live_view(self):
        self.live_view_timer.start(33) # ~30 fps

    def stop_live_view(self):
        self.live_view_timer.stop()

    def _update_live_view(self):
        if self.current_state not in ("IDLE", "COUNTDOWN", "CAPTURING"):
            return

        frame_data = self.camera_mgr.get_liveview()
        if not frame_data:
            return

        if isinstance(frame_data, bytes):
            qimg = QImage.fromData(frame_data)
        elif isinstance(frame_data, np.ndarray):
            h, w, ch = frame_data.shape
            qimg = QImage(frame_data.data, w, h, ch * w, QImage.Format_RGB888)
        else:
            return

        if qimg.isNull():
            return

        pixmap = QPixmap.fromImage(qimg)

        # Căn chỉnh kích thước hiển thị
        lbl_w = self.lbl_viewport.width()
        lbl_h = self.lbl_viewport.height()
        scaled = pixmap.scaled(lbl_w, lbl_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_viewport.setPixmap(scaled)

        # Căn giữa nhãn đếm ngược
        if self.lbl_countdown.isVisible():
            self.lbl_countdown.setGeometry((lbl_w - 220) // 2, (lbl_h - 220) // 2, 220, 220)
        if self.lbl_status_badge.isVisible():
            self.lbl_status_badge.setGeometry((lbl_w - 360) // 2, lbl_h - 90, 360, 55)

    # -------------------------------------------------------------
    # TIẾN TRÌNH CHỤP ẢNH TỰ ĐỘNG (CAPTURE FLOW)
    # -------------------------------------------------------------
    def start_capture_flow(self):
        if self.current_state != "IDLE":
            return

        self.current_state = "COUNTDOWN"
        self.captured_originals.clear()
        self.captured_paths.clear()
        self.current_shot_index = 1

        # Xác định số lượng ảnh cần chụp theo khung đang chọn
        selected_tmpl = self.frame_mgr.get_frame(self.selected_frame_id)
        if selected_tmpl and selected_tmpl.slots:
            self.total_shots_needed = len(selected_tmpl.slots) if not selected_tmpl.is_dual_strip else len(selected_tmpl.slots) // 2
        else:
            self.total_shots_needed = 3

        # Ẩn nút Start, hiện thông báo
        self.btn_start.setEnabled(False)
        self.combo_timer.setEnabled(False)
        self._start_single_shot_countdown()

    def _start_single_shot_countdown(self):
        self.countdown_remaining = self.countdown_duration
        self.lbl_countdown.setText(str(self.countdown_remaining))
        self.lbl_countdown.show()

        self.lbl_status_badge.setText(f"Chuẩn bị! Ảnh {self.current_shot_index} / {self.total_shots_needed}")
        self.lbl_status_badge.show()

        self.countdown_timer.start(1000)

    def _on_countdown_tick(self):
        self.countdown_remaining -= 1
        if self.countdown_remaining > 0:
            self.lbl_countdown.setText(str(self.countdown_remaining))
        elif self.countdown_remaining == 0:
            self.lbl_countdown.setText("📸")
        else:
            self.countdown_timer.stop()
            self.lbl_countdown.hide()
            self._trigger_shot()

    def _trigger_shot(self):
        self.current_state = "CAPTURING"
        # Hiệu ứng flash chớp trắng
        self.lbl_viewport.setStyleSheet("background-color: #FFFFFF;")
        QTimer.singleShot(100, lambda: self.lbl_viewport.setStyleSheet("background-color: #000000; border-radius: 12px;"))

        # Tạo thư mục session nếu chưa có
        if not self.current_session_id:
            active_event = self.event_mgr.get_active_event_name()
            dirs = self.event_mgr.get_event_dirs(active_event)
            sess_name = time.strftime("Session_%Y%m%d_%H%M%S")
            self.current_session_id = sess_name
            self.session_dir = os.path.join(dirs["originals"], sess_name)
            os.makedirs(self.session_dir, exist_ok=True)

        target_path = os.path.join(self.session_dir, f"photo_{self.current_shot_index}.jpg")

        # Chụp ảnh chất lượng cao
        success, captured_img = self.camera_mgr.capture_photo(target_path)
        if success and captured_img:
            self.captured_originals.append(captured_img)
            self.captured_paths.append(target_path)
        else:
            # Fallback tạo ảnh mẫu nếu camera lỗi
            logger.warning("Không chụp được ảnh từ camera thật, sử dụng frame mô phỏng.")
            fallback_img = Image.new("RGB", (1800, 1200), color=(100, 150, 200))
            fallback_img.save(target_path)
            self.captured_originals.append(fallback_img)
            self.captured_paths.append(target_path)

        # Kiểm tra xem đã đủ số lượng ảnh chưa
        if self.current_shot_index < self.total_shots_needed:
            self.current_shot_index += 1
            # Nghỉ 1 giây rồi tiếp tục đếm ngược cho ảnh tiếp theo
            self.current_state = "COUNTDOWN"
            QTimer.singleShot(1200, self._start_single_shot_countdown)
        else:
            # Hoàn tất chụp tất cả ảnh -> Chuyển sang màn hình xem kết quả
            self.lbl_status_badge.setText("✨ Đang xử lý ảnh hoàn thiện...")
            QTimer.singleShot(500, self._enter_review_state)

    # -------------------------------------------------------------
    # MÀN HÌNH XEM KẾT QUẢ & CHIA SẺ (REVIEW STATE)
    # -------------------------------------------------------------
    def _enter_review_state(self):
        self.current_state = "REVIEW"
        self.stop_live_view()
        self.lbl_countdown.hide()
        self.lbl_status_badge.hide()

        # Đổi các nút điều khiển phía dưới
        self.btn_start.hide()
        self.combo_timer.hide()

        self.btn_retake.show()
        self.btn_qr.show()
        self.btn_print.show()
        self.btn_finish.show()

        # Tạo mã token chia sẻ cho session này
        active_event = self.event_mgr.get_active_event_name()
        token_info = self.token_mgr.create_token(active_event, self.current_session_id)
        self.current_token = token_info.token

        self._render_and_display_composite()

    def _render_and_display_composite(self):
        if not self.captured_originals:
            return

        # 1. Áp dụng bộ lọc màu lên từng ảnh gốc (Non-destructive)
        preset = self.filter_engine.get_preset(self.selected_filter_id)
        filtered_photos = []
        for orig in self.captured_originals:
            if preset:
                filtered_photos.append(self.filter_engine.apply_preset(orig, preset))
            else:
                filtered_photos.append(orig.copy())

        # 2. Ghép khung in 300 DPI bằng FrameDesigner
        template = self.frame_mgr.get_frame(self.selected_frame_id)
        if not template:
            template = self.frame_mgr.list_frames()[0]

        event_name = self.event_mgr.get_active_event_name()
        event_info = {"name": event_name}
        self.current_composite = FrameDesigner.render_composite(filtered_photos, template, event_info)

        # 3. Lưu ảnh thành phẩm vào thư mục Final của Event
        dirs = self.event_mgr.get_event_dirs(event_name)
        final_filename = f"{self.current_session_id}_final.jpg"
        final_path = os.path.join(dirs["final"], final_filename)
        self.current_composite.save(final_path, "JPEG", quality=95, dpi=(300, 300))

        # 4. Hiển thị ảnh thành phẩm lên Viewport
        rgb = self.current_composite.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        lbl_w = self.lbl_viewport.width()
        lbl_h = self.lbl_viewport.height()
        scaled = pixmap.scaled(lbl_w, lbl_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_viewport.setPixmap(scaled)

    def _print_composite(self):
        if not self.current_composite:
            return

        # Hỏi số lượng bản in
        copies_dialog = QDialog(self)
        copies_dialog.setWindowTitle("In Ảnh Photobooth")
        copies_dialog.setFixedSize(340, 200)
        l = QVBoxLayout(copies_dialog)

        l.addWidget(QLabel("<b>Chọn Số Lượng Bản In:</b>"))
        spin_copies = QSpinBox()
        spin_copies.setRange(1, 10)
        spin_copies.setValue(1)
        spin_copies.setFixedHeight(44)
        spin_copies.setStyleSheet("font-size: 20px; font-weight: bold;")
        l.addWidget(spin_copies)

        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("btn_secondary")
        btn_cancel.clicked.connect(copies_dialog.reject)
        btn_box.addWidget(btn_cancel)

        btn_confirm = QPushButton("In Ngay")
        btn_confirm.setObjectName("btn_success")
        btn_confirm.clicked.connect(copies_dialog.accept)
        btn_box.addWidget(btn_confirm)
        l.addLayout(btn_box)

        if copies_dialog.exec() == QDialog.Accepted:
            num_copies = spin_copies.value()
            event_name = self.event_mgr.get_active_event_name()
            dirs = self.event_mgr.get_event_dirs(event_name)
            final_path = os.path.join(dirs["final"], f"{self.current_session_id}_final.jpg")

            # Gửi vào Spooler máy in
            success = self.print_mgr.print_image(final_path, copies=num_copies)
            if success:
                QMessageBox.information(self, "Đang In", f"Đã gửi lệnh in {num_copies} bản tới máy in!")
            else:
                QMessageBox.warning(self, "Máy In", "Lệnh in đã được ghi nhận. Vui lòng kiểm tra kết nối máy in trong tab 'Máy In'!")

    def _show_qr_dialog(self):
        if not self.current_token:
            return

        active_event = self.event_mgr.get_active_event_name()
        qr_img = self.token_mgr.generate_qr_code(self.current_token)
        lan_url = self.token_mgr.get_sharing_url(self.current_token)

        dlg = QDialog(self)
        dlg.setWindowTitle("Quét Mã QR Tải Ảnh Về Điện Thoại")
        dlg.setFixedSize(450, 520)
        l = QVBoxLayout(dlg)
        l.setSpacing(14)

        title = QLabel("Quét Mã Để Tải Ảnh Ngay!")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #38BDF8;")
        l.addWidget(title)

        lbl_qr = QLabel()
        lbl_qr.setAlignment(Qt.AlignCenter)
        rgb = qr_img.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        lbl_qr.setPixmap(QPixmap.fromImage(qimg).scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        l.addWidget(lbl_qr)

        lbl_url = QLabel(f"Liên kết tải ảnh:\n<b>{lan_url}</b>")
        lbl_url.setAlignment(Qt.AlignCenter)
        lbl_url.setWordWrap(True)
        lbl_url.setStyleSheet("color: #94A3B8; font-size: 13px;")
        l.addWidget(lbl_url)

        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("btn_secondary")
        btn_close.clicked.connect(dlg.accept)
        l.addWidget(btn_close)

        dlg.exec()

    def _retake_session(self):
        confirm = QMessageBox.question(self, "Chụp Lại", "Bạn có chắc muốn bỏ lượt chụp này và chụp lại từ đầu?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self._reset_to_idle()

    def _finish_session(self):
        self.session_finished.emit(self.current_session_id or "")
        self._reset_to_idle()

    def _reset_to_idle(self):
        self.current_state = "IDLE"
        self.current_session_id = None
        self.current_token = None
        self.captured_originals.clear()
        self.captured_paths.clear()

        # Hiển thị lại các nút Kiosk chính
        self.btn_start.show()
        self.btn_start.setEnabled(True)
        self.combo_timer.show()
        self.combo_timer.setEnabled(True)

        self.btn_retake.hide()
        self.btn_qr.hide()
        self.btn_print.hide()
        self.btn_finish.hide()

        self.start_live_view()
