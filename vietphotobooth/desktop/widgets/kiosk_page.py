"""
1998 TEAM — Photobooth Kiosk Page
Phong cách Studio Cưới chuyên nghiệp, hiện đại, tinh tế.
Khung Live View chiếm diện tích lớn nhất, hiển thị thông báo rõ ràng khi mất kết nối camera,
không hiển thị hình người mô phỏng, giao diện gọn gàng không thanh cuộn ngang,
bộ lọc màu tự quản lý (hiển thị 'Chưa có bộ lọc. Hãy thêm bộ lọc của bạn' khi trống).
"""

import os
import time
from typing import Optional, List
from PIL import Image
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFrame, QSizePolicy, QDialog, QSpinBox, QMessageBox, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QFont

from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.filters.filter_engine import FilterEngine, FilterPreset
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_models import FrameTemplate
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.desktop.widgets.filter_editor_page import FilterEditorDialog
from vietphotobooth.core.logger import get_logger

logger = get_logger()

# Đường dẫn logo 1998 Studio
LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "logo_1998_studio.png"))


class KioskPage(QWidget):
    """Màn hình Photobooth Kiosk chính tương tác cảm ứng phong cách Studio Cưới."""

    session_finished = Signal(str)

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
        self.countdown_duration = int(self.config_mgr.get("countdown_seconds", 5))
        self.total_shots_needed = int(self.config_mgr.get("photos_per_session", 3))
        self.current_shot_index = 0
        self.captured_originals: List[Image.Image] = []
        self.captured_paths: List[str] = []
        self.selected_filter_id: Optional[str] = None
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
        self._load_frame_options()
        self._refresh_filter_options()
        self.start_live_view()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 14)
        self.main_layout.setSpacing(12)

        # -------------------------------------------------------------
        # 1. THANH TRẠNG THÁI & THƯƠNG HIỆU 1998 STUDIO TRÊN CÙNG
        # -------------------------------------------------------------
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)
        header_bar.setSpacing(14)

        # Logo 1998 Studio
        self.lbl_logo = QLabel()
        if os.path.exists(LOGO_PATH):
            pix = QPixmap(LOGO_PATH)
            self.lbl_logo.setPixmap(pix.scaledToHeight(46, Qt.SmoothTransformation))
        else:
            self.lbl_logo.setText("1998 STUDIO")
            self.lbl_logo.setStyleSheet("color: #D4AF37; font-size: 20px; font-weight: bold;")
        header_bar.addWidget(self.lbl_logo)

        brand_title = QLabel("<b>1998 TEAM</b> — Photobooth")
        brand_title.setStyleSheet("color: #F7E7CE; font-size: 20px; font-weight: bold;")
        header_bar.addWidget(brand_title)

        header_bar.addStretch()

        # Badge trạng thái máy ảnh
        self.lbl_cam_status = QLabel("📷 Đang kiểm tra...")
        self.lbl_cam_status.setStyleSheet("background-color: #121C33; color: #D4AF37; border: 1px solid #233152; border-radius: 6px; padding: 6px 12px; font-size: 13px; font-weight: 600;")
        header_bar.addWidget(self.lbl_cam_status)

        # Badge độ phân giải
        self.lbl_resolution = QLabel("📐 1920x1080")
        self.lbl_resolution.setStyleSheet("background-color: #121C33; color: #94A3B8; border: 1px solid #233152; border-radius: 6px; padding: 6px 12px; font-size: 13px;")
        header_bar.addWidget(self.lbl_resolution)

        # Bộ chọn số ảnh mỗi lượt (3 ảnh / 4 ảnh)
        header_bar.addWidget(QLabel("<b style='color:#C5A059;'>Số ảnh:</b>"))
        self.combo_shots = QComboBox()
        self.combo_shots.addItems(["3 Ảnh", "4 Ảnh", "2 Ảnh", "1 Ảnh"])
        self.combo_shots.currentIndexChanged.connect(self._on_shots_changed)
        header_bar.addWidget(self.combo_shots)

        # Bộ chọn thời gian đếm ngược (3s / 5s / 10s)
        header_bar.addWidget(QLabel("<b style='color:#C5A059;'>Đếm ngược:</b>"))
        self.combo_countdown = QComboBox()
        self.combo_countdown.addItems(["3 Giây", "5 Giây", "10 Giây"])
        self.combo_countdown.setCurrentIndex(1) # Mặc định 5s
        self.combo_countdown.currentIndexChanged.connect(self._on_countdown_changed)
        header_bar.addWidget(self.combo_countdown)

        self.main_layout.addLayout(header_bar)

        # -------------------------------------------------------------
        # 2. KHUNG LIVE VIEW TRUNG TÂM (CHIẾM DIỆN TÍCH LỚN NHẤT)
        # -------------------------------------------------------------
        self.center_frame = QFrame()
        self.center_frame.setObjectName("card_panel")
        self.center_layout = QVBoxLayout(self.center_frame)
        self.center_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_viewport = QLabel()
        self.lbl_viewport.setAlignment(Qt.AlignCenter)
        self.lbl_viewport.setStyleSheet("background-color: #050811; border: 2px solid #1E2D4A; border-radius: 12px;")
        self.lbl_viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_viewport.setMinimumSize(720, 480)
        self.center_layout.addWidget(self.lbl_viewport)

        # Panel thông báo rõ ràng khi CHƯA KẾT NỐI MÁY ẢNH (Không hiển thị hình người giả lập)
        self.panel_disconnected = QWidget(self.lbl_viewport)
        l_disc = QVBoxLayout(self.panel_disconnected)
        l_disc.setAlignment(Qt.AlignCenter)
        l_disc.setSpacing(16)

        icon_cam = QLabel("📷❌")
        icon_cam.setAlignment(Qt.AlignCenter)
        icon_cam.setStyleSheet("font-size: 64px;")
        l_disc.addWidget(icon_cam)

        lbl_disc_title = QLabel("CHƯA KẾT NỐI MÁY ẢNH")
        lbl_disc_title.setAlignment(Qt.AlignCenter)
        lbl_disc_title.setStyleSheet("color: #D4AF37; font-size: 26px; font-weight: 900; letter-spacing: 1px;")
        l_disc.addWidget(lbl_disc_title)

        lbl_disc_desc = QLabel("Vui lòng cắm cáp USB máy ảnh DSLR/Mirrorless hoặc Webcam vào máy tính,\nsau đó nhấn nút bên dưới để kết nối.")
        lbl_disc_desc.setAlignment(Qt.AlignCenter)
        lbl_disc_desc.setStyleSheet("color: #CBD5E1; font-size: 16px; line-height: 1.4;")
        l_disc.addWidget(lbl_disc_desc)

        btn_reconnect = QPushButton("🔌 Kết Nối Lại Máy Ảnh")
        btn_reconnect.setObjectName("btn_champagne")
        btn_reconnect.setFixedHeight(50)
        btn_reconnect.setFixedWidth(260)
        btn_reconnect.clicked.connect(self._reconnect_camera)
        l_disc.addWidget(btn_reconnect, alignment=Qt.AlignCenter)

        self.panel_disconnected.hide()

        # Lớp overlay đếm ngược to ở giữa
        self.lbl_countdown = QLabel("", self.lbl_viewport)
        self.lbl_countdown.setAlignment(Qt.AlignCenter)
        self.lbl_countdown.setStyleSheet("color: #D4AF37; font-size: 140px; font-weight: 900; background: rgba(5,8,17,0.65); border: 3px solid #D4AF37; border-radius: 40px;")
        self.lbl_countdown.hide()

        # Label trạng thái ảnh ("Đang chụp ảnh 1/3...")
        self.lbl_status_badge = QLabel("", self.lbl_viewport)
        self.lbl_status_badge.setAlignment(Qt.AlignCenter)
        self.lbl_status_badge.setStyleSheet("color: #F7E7CE; font-size: 24px; font-weight: bold; background: rgba(13,21,39,0.92); border: 1px solid #D4AF37; padding: 10px 28px; border-radius: 20px;")
        self.lbl_status_badge.hide()

        self.main_layout.addWidget(self.center_frame, 8)

        # -------------------------------------------------------------
        # 3. THANH ĐIỀU KHIỂN & BỘ LỌC (GỌN GÀNG, KHÔNG DÙNG SCROLLBAR NGANG)
        # -------------------------------------------------------------
        self.controls_panel = QFrame()
        self.controls_panel.setObjectName("card_panel")
        self.controls_layout = QHBoxLayout(self.controls_panel)
        self.controls_layout.setContentsMargins(14, 10, 14, 10)
        self.controls_layout.setSpacing(16)

        # KHU VỰC CHỌN KHUNG ẢNH
        lbl_frame_title = QLabel("<b style='color:#D4AF37;'>Khung Ảnh:</b>")
        self.controls_layout.addWidget(lbl_frame_title)
        self.combo_frames = QComboBox()
        self.combo_frames.setMinimumWidth(220)
        self.combo_frames.currentIndexChanged.connect(self._on_frame_selected)
        self.controls_layout.addWidget(self.combo_frames)

        # KHU VỰC BỘ LỌC MÀU (THƯ VIỆN SẠCH, HỖ TRỢ THÊM BỘ LỌC)
        self.lbl_filter_title = QLabel("<b style='color:#D4AF37;'>Bộ Lọc:</b>")
        self.controls_layout.addWidget(self.lbl_filter_title)

        self.lbl_no_filter_msg = QLabel("Chưa có bộ lọc. Hãy thêm bộ lọc của bạn")
        self.lbl_no_filter_msg.setStyleSheet("color: #94A3B8; font-style: italic;")
        self.controls_layout.addWidget(self.lbl_no_filter_msg)

        self.combo_filters = QComboBox()
        self.combo_filters.setMinimumWidth(180)
        self.combo_filters.currentIndexChanged.connect(self._on_filter_selected)
        self.combo_filters.hide()
        self.controls_layout.addWidget(self.combo_filters)

        self.btn_add_filter = QPushButton("+ Thêm Bộ Lọc")
        self.btn_add_filter.setObjectName("btn_secondary")
        self.btn_add_filter.clicked.connect(self._open_filter_dialog)
        self.controls_layout.addWidget(self.btn_add_filter)

        self.controls_layout.addStretch()

        # NÚT BẮT ĐẦU CHỤP KHỔNG LỒ (VÀNG CHAMPAGNE)
        self.btn_start = QPushButton("📸 BẮT ĐẦU CHỤP")
        self.btn_start.setObjectName("btn_big_capture")
        self.btn_start.clicked.connect(self.start_capture_flow)
        self.controls_layout.addWidget(self.btn_start)

        # CÁC NÚT KHI Ở CHẾ ĐỘ XEM KẾT QUẢ (REVIEW STATE)
        self.btn_retake = QPushButton("🔄 Chụp Lại")
        self.btn_retake.setObjectName("btn_secondary")
        self.btn_retake.setFixedHeight(54)
        self.btn_retake.clicked.connect(self._retake_session)
        self.btn_retake.hide()
        self.controls_layout.addWidget(self.btn_retake)

        self.btn_save = QPushButton("💾 Lưu Ảnh")
        self.btn_save.setObjectName("btn_secondary")
        self.btn_save.setFixedHeight(54)
        self.btn_save.clicked.connect(self._save_photo_dialog)
        self.btn_save.hide()
        self.controls_layout.addWidget(self.btn_save)

        self.btn_qr = QPushButton("📱 Quét Mã QR")
        self.btn_qr.setObjectName("btn_secondary")
        self.btn_qr.setFixedHeight(54)
        self.btn_qr.clicked.connect(self._show_qr_dialog)
        self.btn_qr.hide()
        self.controls_layout.addWidget(self.btn_qr)

        self.btn_print = QPushButton("🖨️ IN ẢNH NGAY")
        self.btn_print.setObjectName("btn_champagne")
        self.btn_print.setFixedHeight(54)
        self.btn_print.clicked.connect(self._print_composite)
        self.btn_print.hide()
        self.controls_layout.addWidget(self.btn_print)

        self.btn_finish = QPushButton("✅ Hoàn Tất")
        self.btn_finish.setObjectName("btn_secondary")
        self.btn_finish.setFixedHeight(54)
        self.btn_finish.clicked.connect(self._finish_session)
        self.btn_finish.hide()
        self.controls_layout.addWidget(self.btn_finish)

        self.main_layout.addWidget(self.controls_panel, 2)

    # -------------------------------------------------------------
    # QUẢN LÝ KHUNG & BỘ LỌC
    # -------------------------------------------------------------
    def _load_frame_options(self):
        self.combo_frames.blockSignals(True)
        self.combo_frames.clear()
        frames = self.frame_mgr.list_frames()
        if not frames:
            self.combo_frames.addItem("Mặc định 2x6 inch", None)
        else:
            for f in frames:
                self.combo_frames.addItem(f"🖼️ {f.name}", f.id)
            if not self.selected_frame_id and frames:
                self.selected_frame_id = frames[0].id
        self.combo_frames.blockSignals(False)

    def _refresh_filter_options(self):
        presets = self.filter_engine.get_presets()
        self.combo_filters.blockSignals(True)
        self.combo_filters.clear()

        if not presets:
            self.lbl_no_filter_msg.show()
            self.combo_filters.hide()
            self.btn_add_filter.setText("+ Thêm Bộ Lọc")
            self.selected_filter_id = None
        else:
            self.lbl_no_filter_msg.hide()
            self.combo_filters.show()
            self.combo_filters.addItem("-- Không dùng bộ lọc --", None)
            for p in presets:
                self.combo_filters.addItem(f"✨ {p.name}", p.id)
            self.btn_add_filter.setText("Quản Lý Bộ Lọc")

            if self.selected_filter_id:
                idx = self.combo_filters.findData(self.selected_filter_id)
                if idx >= 0:
                    self.combo_filters.setCurrentIndex(idx)

        self.combo_filters.blockSignals(False)

    def _open_filter_dialog(self):
        dlg = FilterEditorDialog(self.filter_engine, self)
        dlg.exec()
        self._refresh_filter_options()
        if self.current_state == "REVIEW":
            self._render_and_display_composite()

    def _on_frame_selected(self, index: int):
        self.selected_frame_id = self.combo_frames.currentData()
        if self.current_state == "REVIEW":
            self._render_and_display_composite()

    def _on_filter_selected(self, index: int):
        self.selected_filter_id = self.combo_filters.currentData()
        if self.current_state == "REVIEW":
            self._render_and_display_composite()

    def _on_shots_changed(self, index: int):
        values = [3, 4, 2, 1]
        self.total_shots_needed = values[index]

    def _on_countdown_changed(self, index: int):
        durations = [3, 5, 10]
        self.countdown_duration = durations[index]

    # -------------------------------------------------------------
    # CAMERA LIVE VIEW & KIỂM TRA KẾT NỐI
    # -------------------------------------------------------------
    def start_live_view(self):
        self.live_view_timer.start(33) # 30 fps
        self._update_camera_status_ui()

    def stop_live_view(self):
        self.live_view_timer.stop()

    def _reconnect_camera(self):
        """Thử dò quét và kết nối lại máy ảnh."""
        self.lbl_cam_status.setText("📷 Đang kết nối lại...")
        # Thử DirectShow trước
        connected = self.camera_mgr.switch_backend("directshow", 0)
        if not connected:
            # Thử digiCamControl
            connected = self.camera_mgr.switch_backend("digicam")
        if not connected:
            # Fallback simulator
            self.camera_mgr.switch_backend("simulator")

        self._update_camera_status_ui()
        if self.camera_mgr.is_connected() and self.camera_mgr.current_backend_name != "simulator":
            QMessageBox.information(self, "Máy Ảnh", "Đã kết nối thành công với máy ảnh!")
        else:
            QMessageBox.warning(self, "Máy Ảnh", "Chưa phát hiện máy ảnh USB. Đang giữ ở chế độ chờ kết nối.")

    def _update_camera_status_ui(self):
        is_conn = self.camera_mgr.is_connected()
        backend = self.camera_mgr.current_backend_name

        if not is_conn or (backend == "simulator" and not getattr(self, "_allow_simulator_preview", False)):
            self.lbl_cam_status.setText("🔴 Chưa kết nối máy ảnh")
            self.lbl_cam_status.setStyleSheet("background-color: #2D1515; color: #F87171; border: 1px solid #7F1D1D; border-radius: 6px; padding: 6px 12px; font-size: 13px; font-weight: 600;")
            self.lbl_resolution.setText("📐 --")
        else:
            self.lbl_cam_status.setText(f"🟢 Đã kết nối ({backend.upper()})")
            self.lbl_cam_status.setStyleSheet("background-color: #0E291C; color: #34D399; border: 1px solid #065F46; border-radius: 6px; padding: 6px 12px; font-size: 13px; font-weight: 600;")
            self.lbl_resolution.setText("📐 1920x1080 (FHD)" if backend != "digicam" else "📐 6000x4000 (24MP)")

    def _update_live_view(self):
        if self.current_state not in ("IDLE", "COUNTDOWN", "CAPTURING"):
            return

        is_connected = self.camera_mgr.is_connected()
        backend = self.camera_mgr.current_backend_name
        lbl_w = self.lbl_viewport.width()
        lbl_h = self.lbl_viewport.height()

        # NẾU CHƯA CÓ CAMERA THẬT (VÀ KHÔNG PHẢI NGƯỜI DÙNG BẬT THỬ SIMULATOR TRONG TAB MÁY ẢNH)
        # -> HIỂN THỊ THÔNG BÁO RÕ RÀNG, KHÔNG VẼ HÌNH NGƯỜI GIẢ LẬP
        if not is_connected or backend == "simulator":
            if not self.panel_disconnected.isVisible():
                self.panel_disconnected.show()
                self.lbl_viewport.setPixmap(QPixmap()) # Xóa ảnh cũ
            self.panel_disconnected.setGeometry(0, 0, lbl_w, lbl_h)
            return
        else:
            if self.panel_disconnected.isVisible():
                self.panel_disconnected.hide()

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
        scaled = pixmap.scaled(lbl_w, lbl_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_viewport.setPixmap(scaled)

        # Căn giữa nhãn đếm ngược
        if self.lbl_countdown.isVisible():
            self.lbl_countdown.setGeometry((lbl_w - 240) // 2, (lbl_h - 240) // 2, 240, 240)
        if self.lbl_status_badge.isVisible():
            self.lbl_status_badge.setGeometry((lbl_w - 380) // 2, lbl_h - 90, 380, 55)

    # -------------------------------------------------------------
    # TIẾN TRÌNH CHỤP ẢNH TỰ ĐỘNG
    # -------------------------------------------------------------
    def start_capture_flow(self):
        if self.current_state != "IDLE":
            return

        # Kiểm tra máy ảnh
        if not self.camera_mgr.is_connected() and self.camera_mgr.current_backend_name != "simulator":
            QMessageBox.warning(self, "Máy Ảnh", "Chưa kết nối máy ảnh! Vui lòng cắm cáp USB máy ảnh và bấm 'Kết Nối Lại Máy Ảnh'.")
            return

        self.current_state = "COUNTDOWN"
        self.captured_originals.clear()
        self.captured_paths.clear()
        self.current_shot_index = 1

        self.btn_start.setEnabled(False)
        self.combo_shots.setEnabled(False)
        self.combo_countdown.setEnabled(False)
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
        # Chớp flash trắng studio
        self.lbl_viewport.setStyleSheet("background-color: #FFFFFF;")
        QTimer.singleShot(120, lambda: self.lbl_viewport.setStyleSheet("background-color: #050811; border: 2px solid #1E2D4A; border-radius: 12px;"))

        # Tạo thư mục session
        if not self.current_session_id:
            active_event = self.event_mgr.get_active_event_name()
            dirs = self.event_mgr.get_event_dirs(active_event)
            sess_name = time.strftime("Session_%Y%m%d_%H%M%S")
            self.current_session_id = sess_name
            self.session_dir = os.path.join(dirs["originals"], sess_name)
            os.makedirs(self.session_dir, exist_ok=True)

        target_path = os.path.join(self.session_dir, f"photo_{self.current_shot_index}.jpg")

        success, captured_img = self.camera_mgr.capture_photo(target_path)
        if success and captured_img:
            self.captured_originals.append(captured_img)
            self.captured_paths.append(target_path)
        else:
            logger.warning("Không chụp được ảnh từ camera thật, sử dụng frame mô phỏng studio.")
            fallback_img = Image.new("RGB", (1800, 1200), color=(14, 21, 39))
            fallback_img.save(target_path)
            self.captured_originals.append(fallback_img)
            self.captured_paths.append(target_path)

        if self.current_shot_index < self.total_shots_needed:
            self.current_shot_index += 1
            self.current_state = "COUNTDOWN"
            QTimer.singleShot(1400, self._start_single_shot_countdown)
        else:
            self.lbl_status_badge.setText("✨ Đang tạo khung ảnh thành phẩm...")
            QTimer.singleShot(600, self._enter_review_state)

    # -------------------------------------------------------------
    # MÀN HÌNH XEM KẾT QUẢ, IN & CHIA SẺ QR (REVIEW STATE)
    # -------------------------------------------------------------
    def _enter_review_state(self):
        self.current_state = "REVIEW"
        self.stop_live_view()
        self.lbl_countdown.hide()
        self.lbl_status_badge.hide()
        self.panel_disconnected.hide()

        # Ẩn nút Chụp, hiện các nút Xem kết quả
        self.btn_start.hide()
        self.btn_retake.show()
        self.btn_save.show()
        self.btn_qr.show()
        self.btn_print.show()
        self.btn_finish.show()

        active_event = self.event_mgr.get_active_event_name()
        token_info = self.token_mgr.create_token(active_event, self.current_session_id)
        self.current_token = token_info.token

        self._render_and_display_composite()

    def _render_and_display_composite(self):
        if not self.captured_originals:
            return

        # 1. Áp dụng bộ lọc màu nếu có (Non-destructive)
        filtered_photos = []
        preset = self.filter_engine.get_preset(self.selected_filter_id) if self.selected_filter_id else None
        for orig in self.captured_originals:
            if preset:
                filtered_photos.append(self.filter_engine.apply_preset(orig, preset))
            else:
                filtered_photos.append(orig.copy())

        # 2. Ghép khung in 300 DPI bằng FrameDesigner
        template = self.frame_mgr.get_frame(self.selected_frame_id)
        if not template:
            frames = self.frame_mgr.list_frames()
            template = frames[0] if frames else None

        if template:
            event_name = self.event_mgr.get_active_event_name()
            event_info = {"name": event_name}
            self.current_composite = FrameDesigner.render_composite(filtered_photos, template, event_info)
        else:
            self.current_composite = filtered_photos[0]

        # 3. Lưu ảnh thành phẩm vào thư mục Final
        event_name = self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(event_name)
        final_filename = f"{self.current_session_id}_final.jpg"
        final_path = os.path.join(dirs["final"], final_filename)
        self.current_composite.save(final_path, "JPEG", quality=95, dpi=(300, 300))

        # 4. Hiển thị lên Viewport
        rgb = self.current_composite.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        lbl_w = self.lbl_viewport.width()
        lbl_h = self.lbl_viewport.height()
        scaled = pixmap.scaled(lbl_w, lbl_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_viewport.setPixmap(scaled)

    def _save_photo_dialog(self):
        if not self.current_composite:
            return
        from PySide6.QtWidgets import QFileDialog
        save_path, _ = QFileDialog.getSaveFileName(self, "Lưu Ảnh Thành Phẩm", f"1998_Studio_{self.current_session_id}.jpg", "Ảnh JPEG (*.jpg);;Ảnh PNG (*.png)")
        if save_path:
            self.current_composite.save(save_path, quality=98)
            QMessageBox.information(self, "Thành Công", f"Đã lưu ảnh thành công vào:\n{save_path}")

    def _print_composite(self):
        if not self.current_composite:
            return

        copies_dialog = QDialog(self)
        copies_dialog.setWindowTitle("1998 Studio — In Ảnh Photobooth")
        copies_dialog.setFixedSize(360, 210)
        l = QVBoxLayout(copies_dialog)
        l.setSpacing(14)

        l.addWidget(QLabel("<b style='color:#D4AF37; font-size:16px;'>Chọn Số Lượng Bản In:</b>"))
        spin_copies = QSpinBox()
        spin_copies.setRange(1, 10)
        spin_copies.setValue(1)
        spin_copies.setFixedHeight(46)
        spin_copies.setStyleSheet("font-size: 20px; font-weight: bold; color: #D4AF37;")
        l.addWidget(spin_copies)

        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("btn_secondary")
        btn_cancel.clicked.connect(copies_dialog.reject)
        btn_box.addWidget(btn_cancel)

        btn_confirm = QPushButton("In Ngay")
        btn_confirm.setObjectName("btn_champagne")
        btn_confirm.clicked.connect(copies_dialog.accept)
        btn_box.addWidget(btn_confirm)
        l.addLayout(btn_box)

        if copies_dialog.exec() == QDialog.Accepted:
            num_copies = spin_copies.value()
            event_name = self.event_mgr.get_active_event_name()
            dirs = self.event_mgr.get_event_dirs(event_name)
            final_path = os.path.join(dirs["final"], f"{self.current_session_id}_final.jpg")

            success = self.print_mgr.print_image(final_path, copies=num_copies)
            if success:
                QMessageBox.information(self, "Đang In", f"Đã gửi lệnh in {num_copies} bản tới máy in!")
            else:
                QMessageBox.warning(self, "Máy In", "Lệnh in đã được ghi nhận vào hàng đợi. Vui lòng kiểm tra cáp máy in trong tab 'Máy In'.")

    def _show_qr_dialog(self):
        if not self.current_token:
            return

        active_event = self.event_mgr.get_active_event_name()
        qr_img = self.token_mgr.generate_qr_code(self.current_token)
        lan_url = self.token_mgr.get_sharing_url(self.current_token)

        dlg = QDialog(self)
        dlg.setWindowTitle("Quét Mã QR Tải Ảnh Về Điện Thoại")
        dlg.setFixedSize(460, 530)
        l = QVBoxLayout(dlg)
        l.setSpacing(14)

        title = QLabel("1998 STUDIO — TẢI ẢNH VỀ ĐIỆN THOẠI")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #D4AF37;")
        l.addWidget(title)

        lbl_qr = QLabel()
        lbl_qr.setAlignment(Qt.AlignCenter)
        rgb = qr_img.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        lbl_qr.setPixmap(QPixmap.fromImage(qimg).scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        l.addWidget(lbl_qr)

        lbl_url = QLabel(f"Đường dẫn tải ảnh:\n<b>{lan_url}</b>")
        lbl_url.setAlignment(Qt.AlignCenter)
        lbl_url.setWordWrap(True)
        lbl_url.setStyleSheet("color: #CBD5E1; font-size: 13px;")
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

        self.btn_start.show()
        self.btn_start.setEnabled(True)
        self.combo_shots.setEnabled(True)
        self.combo_countdown.setEnabled(True)

        self.btn_retake.hide()
        self.btn_save.hide()
        self.btn_qr.hide()
        self.btn_print.hide()
        self.btn_finish.hide()

        self.start_live_view()
