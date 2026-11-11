"""
1998 TEAM — Photobooth Kiosk Page
Tái thiết kế chính xác theo bố cục mục tiêu:
1. Khu vực chính 3 cột:
   - Cột trái: Sự kiện hiện tại (Cover banner, ngày, địa điểm, số ảnh đã chụp, nút Đổi sự kiện).
   - Cột giữa: Khung Live View lớn (Live camera thật khi kết nối, chờ kết nối chuẩn studio khi ngắt, badges độ phân giải & toàn màn hình).
   - Cột phải: Trạng thái máy ảnh (Chấm đèn trạng thái, thông báo, nút Kết nối máy ảnh vàng champagne, nút Mở cài đặt máy ảnh).
2. Hàng điều khiển 4 thẻ bên dưới:
   - Số ảnh mỗi lượt (3 ảnh / 4 ảnh dạng pill).
   - Đếm ngược (3 giây / 5 giây / 10 giây dạng pill).
   - Mẫu khung ảnh (Thẻ thumbnail thật trực quan từ tệp khung, viền vàng + dấu tích khi chọn, nút chuyển trang và Chọn khung khác).
   - Bộ lọc màu (Thư viện sạch, thông báo Chưa có bộ lọc, nút Thêm bộ lọc vàng champagne).
3. Đáy màn hình:
   - Tùy chọn: Xem trước ảnh sau khi chụp, Tự động in sau khi chụp.
   - Nút BẮT ĐẦU CHỤP khổng lồ vàng champagne quý phái.
   - Nút Toàn màn hình.
"""

import os
import time
import math
import threading
from typing import Optional, List, Dict, Tuple
from PIL import Image
import numpy as np
import shiboken6

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox,
    QFrame, QSizePolicy, QDialog, QSpinBox, QMessageBox,
    QCheckBox, QTabWidget, QLineEdit, QStackedWidget
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize, QThread
from PySide6.QtGui import QPixmap, QImage, QColor, QFont, QIntValidator

from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport
from vietphotobooth.filters.filter_engine import FilterEngine, FilterPreset
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_models import FrameTemplate
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.cloud import SyncManager, SyncStatus
from vietphotobooth.desktop.widgets.filter_editor_page import FilterEditorDialog
from vietphotobooth.core.logger import get_logger
from vietphotobooth.audio import SoundController
from vietphotobooth.desktop.styles import (
    THEME_BG_MAIN, THEME_SURFACE, THEME_BG_SECONDARY, THEME_INPUT_BG,
    THEME_BORDER, THEME_BORDER_LIGHT, THEME_TEXT_PRIMARY, THEME_TEXT_SECONDARY,
    THEME_TEXT_DISABLED, THEME_GOLD, THEME_GOLD_LIGHT, THEME_GOLD_PALE,
    THEME_GOLD_DARK, LIVE_VIEW_BG,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_SECONDARY,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_BORDER, COLOR_BORDER_LIGHT,
    COLOR_CHAMPAGNE, COLOR_CHAMPAGNE_LIGHT, COLOR_PALE_GOLD,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_LIVEVIEW,
    STYLE_BTN_CHAMPAGNE, STYLE_BTN_SECONDARY
)
from vietphotobooth.desktop.icons import (
    COLOR_GOLD, COLOR_GOLD_LIGHT, COLOR_GOLD_DARK, get_svg_icon, get_brand_logo_tight_pixmap
)

logger = get_logger()

# Đường dẫn tài nguyên thương hiệu
LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "logo_1998_transparent.png"))


class TouchNumberPadDialog(QDialog):
    """Bàn phím số cảm ứng kích thước lớn cho Kiosk Photobooth."""
    def __init__(self, current_val: int = 3, min_val: int = 1, max_val: int = 16, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn Số Lượng Ảnh")
        self.setFixedSize(320, 420)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setStyleSheet(
            f"QDialog {{ background-color: {THEME_SURFACE}; border: 2px solid {THEME_GOLD}; border-radius: 14px; }}"
            f"QLabel {{ color: {THEME_TEXT_PRIMARY}; }}"
        )
        self.min_val = min_val
        self.max_val = max_val
        self.value = current_val

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        lbl_title = QLabel("Nhập Số Ảnh Mỗi Lượt")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME_TEXT_PRIMARY};")
        layout.addWidget(lbl_title)

        self.display = QLabel(str(self.value))
        self.display.setAlignment(Qt.AlignCenter)
        self.display.setFixedHeight(54)
        self.display.setStyleSheet(
            f"background-color: {THEME_INPUT_BG}; color: {THEME_TEXT_PRIMARY}; font-size: 28px; font-weight: 900; "
            f"border: 1.5px solid {THEME_BORDER}; border-radius: 10px;"
        )
        layout.addWidget(self.display)

        grid = QGridLayout()
        grid.setSpacing(8)
        btn_style = (
            f"QPushButton {{ background-color: {THEME_SURFACE}; color: {THEME_TEXT_PRIMARY}; font-size: 20px; font-weight: bold; "
            f"border: 1.5px solid {THEME_BORDER}; border-radius: 8px; min-height: 48px; }}"
            f"QPushButton:hover {{ background-color: {THEME_BG_SECONDARY}; border: 1.5px solid {THEME_GOLD}; color: {THEME_TEXT_PRIMARY}; }}"
            f"QPushButton:pressed {{ background-color: #A39F96; }}"
        )

        buttons = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("C", 3, 0), ("0", 3, 1), ("⌫", 3, 2),
        ]
        for text, r, c in buttons:
            btn = QPushButton(text)
            btn.setStyleSheet(btn_style)
            if text.isdigit():
                btn.clicked.connect(lambda _, d=text: self._on_digit(d))
            elif text == "C":
                btn.clicked.connect(self._on_clear)
            elif text == "⌫":
                btn.clicked.connect(self._on_backspace)
            grid.addWidget(btn, r, c)

        layout.addLayout(grid)

        h_actions = QHBoxLayout()
        btn_cancel = QPushButton("Hủy Bỏ")
        btn_cancel.setObjectName("btn_secondary")
        btn_cancel.clicked.connect(self.reject)
        h_actions.addWidget(btn_cancel)

        btn_ok = QPushButton("✅ Xác Nhận")
        btn_ok.setObjectName("btn_champagne")
        btn_ok.clicked.connect(self._on_accept)
        h_actions.addWidget(btn_ok)
        layout.addLayout(h_actions)

    def _on_digit(self, digit: str):
        curr = self.display.text()
        if curr == "0" or curr == "":
            new_txt = digit
        else:
            new_txt = curr + digit
        if len(new_txt) <= 2:
            self.display.setText(new_txt)

    def _on_clear(self):
        self.display.setText("0")

    def _on_backspace(self):
        curr = self.display.text()
        if len(curr) > 1:
            self.display.setText(curr[:-1])
        else:
            self.display.setText("0")

    def _on_accept(self):
        try:
            val = int(self.display.text())
            clamped = max(self.min_val, min(self.max_val, val))
            self.value = clamped
            self.accept()
        except ValueError:
            self.reject()


class CameraLiveViewWorker(QThread):
    """
    Bộ điều phối hiển thị Live View hướng sự kiện (Event-Driven Paced Push):
    - Đăng ký nhận frame trực tiếp từ CameraManager (Direct Push, O(1)).
    - Coalescing / Latest-Frame-Wins: Luôn hiển thị frame mới nhất, không tích tụ hàng đợi.
    - Giới hạn tốc độ hiển thị ở tối đa 30 FPS (chu kỳ 33.33ms).
    - Loại bỏ hoàn toàn vòng lặp polling và sleep ép buộc, giải phóng CPU.
    """
    frame_ready = Signal(object)  # np.ndarray RGB phát sang UI thread
    _push_signal = Signal()       # Signal nội bộ để điều phối delivery trên Qt event loop

    def __init__(self, camera_mgr: CameraManager, parent=None):
        super().__init__(parent)
        self.camera_mgr = camera_mgr
        self._running = True
        self._paused = False
        self._first_frame_logged = False
        self._last_error_log_time = 0.0

        # Pacing & Coalescing (30 FPS cap = 33.33ms interval)
        self._target_interval = 1.0 / 30.0
        self._last_emit_time = 0.0
        self._buffer_lock = threading.Lock()
        self._latest_rgb: Optional[np.ndarray] = None
        self._has_pending = False
        self._stop_event = threading.Event()

        # Dedicated high-precision deadline timer for frame pacing (Qt.PreciseTimer)
        self._deadline_timer = QTimer(self)
        self._deadline_timer.setTimerType(Qt.PreciseTimer)
        self._deadline_timer.setSingleShot(True)
        self._deadline_timer.timeout.connect(self._on_deadline)

        self._push_signal.connect(self._deliver_coalesced_frame, Qt.QueuedConnection)
        if hasattr(self.camera_mgr, "register_frame_callback"):
            self.camera_mgr.register_frame_callback(self._on_direct_frame)

    def _on_direct_frame(self, frame_data) -> None:
        """Callback nhận frame trực tiếp từ background acquisition thread."""
        if not self._running or self._paused or not self.camera_mgr.is_connected():
            return
        if frame_data is None or not getattr(frame_data, "has_rgb", False):
            return

        rgb = frame_data.rgb
        if rgb is None or getattr(rgb, "size", 0) == 0:
            return

        with self._buffer_lock:
            self._latest_rgb = rgb
            if not self._has_pending:
                self._has_pending = True
                self._push_signal.emit()

    @Slot()
    def _deliver_coalesced_frame(self) -> None:
        """Xử lý delivery trên UI thread với pacing 30 FPS và latest-frame-wins."""
        if not self._running or self._paused:
            with self._buffer_lock:
                self._has_pending = False
            return

        # Kiểm tra nếu UI đang bận render frame trước (Single-frame drop)
        parent_widget = self.parent()
        if parent_widget and getattr(parent_widget, "_is_rendering_frame", False):
            if not self._deadline_timer.isActive():
                self._deadline_timer.start(5)
            return

        now = time.perf_counter()
        elapsed = now - self._last_emit_time

        if elapsed >= self._target_interval:
            self._do_emit(now)
        elif not self._deadline_timer.isActive():
            rem = self._target_interval - elapsed
            delay_ms = max(1, math.ceil(rem * 1000.0))
            self._deadline_timer.start(delay_ms)

    @Slot()
    def _on_deadline(self) -> None:
        """Kích hoạt khi đến hạn chót (deadline) để hiển thị frame mới nhất."""
        if not self._running or self._paused:
            with self._buffer_lock:
                self._has_pending = False
            return

        parent_widget = self.parent()
        if parent_widget and getattr(parent_widget, "_is_rendering_frame", False):
            self._deadline_timer.start(5)
            return

        now = time.perf_counter()
        elapsed = now - self._last_emit_time

        if elapsed >= self._target_interval:
            self._do_emit(now)
        else:
            rem = self._target_interval - elapsed
            delay_ms = max(1, math.ceil(rem * 1000.0))
            self._deadline_timer.start(delay_ms)

    def _do_emit(self, now: float) -> None:
        """Phát khung hình mới nhất sang UI thread và cập nhật mốc thời gian emit."""
        self._deadline_timer.stop()
        with self._buffer_lock:
            frame_rgb = self._latest_rgb
            self._has_pending = False

        if frame_rgb is not None and self._running and not self._paused:
            self._last_emit_time = now
            if not self._first_frame_logged:
                logger.info(f"CameraLiveViewWorker nhận khung hình đầu tiên ({frame_rgb.shape[1]}x{frame_rgb.shape[0]}).")
                self._first_frame_logged = True
            self.frame_ready.emit(frame_rgb)

    def run(self):
        """Worker thread chỉ duy trì trạng thái chạy (idle wait) mà không cần polling."""
        logger.info("CameraLiveViewWorker bắt đầu hoạt động (Event-driven Direct Push).")
        self._stop_event.wait()
        logger.info("CameraLiveViewWorker đã dừng.")

    def pause(self):
        self._paused = True
        self._deadline_timer.stop()
        with self._buffer_lock:
            self._latest_rgb = None
            self._has_pending = False
        self._last_emit_time = 0.0

    def resume(self):
        self._paused = False
        self._last_emit_time = 0.0

    def stop(self):
        self._running = False
        self._deadline_timer.stop()
        if hasattr(self.camera_mgr, "unregister_frame_callback"):
            self.camera_mgr.unregister_frame_callback(self._on_direct_frame)
        with self._buffer_lock:
            self._latest_rgb = None
            self._has_pending = False
        self._stop_event.set()
        self.wait(1000)


class CompositeWorker(QThread):
    """
    Luồng xử lý ngầm ghép ảnh và xuất file 300 DPI chất lượng cao.
    Ngăn chặn việc khóa cứng giao diện trong 1-2 giây khi hoàn tất chụp.
    """
    composite_ready = Signal(object, str)  # PIL Image, final_path
    composite_failed = Signal(str)

    def __init__(self, filter_engine, frame_mgr, event_mgr, photos, filter_id, frame_id, session_id, parent=None):
        super().__init__(parent)
        self.filter_engine = filter_engine
        self.frame_mgr = frame_mgr
        self.event_mgr = event_mgr
        self.photos = photos
        self.filter_id = filter_id
        self.frame_id = frame_id
        self.session_id = session_id

    def run(self):
        try:
            # 1. Áp dụng bộ lọc màu nếu có (Non-destructive)
            filtered_photos = []
            preset = self.filter_engine.get_preset(self.filter_id) if self.filter_id else None
            for orig in self.photos:
                if preset:
                    filtered_photos.append(self.filter_engine.apply_preset(orig, preset))
                else:
                    filtered_photos.append(orig.copy())

            # 2. Ghép khung in 300 DPI bằng FrameDesigner
            template = self.frame_mgr.get_frame(self.frame_id)
            if not template:
                frames = self.frame_mgr.list_frames()
                template = frames[0] if frames else None

            event_name = self.event_mgr.get_active_event_name()
            event_info = {"name": event_name}
            if template:
                composite = FrameDesigner.render_composite(filtered_photos, template, event_info)
            else:
                composite = filtered_photos[0]

            # 3. Lưu ảnh thành phẩm 300 DPI vào thư mục Final
            dirs = self.event_mgr.get_event_dirs(event_name)
            final_filename = f"{self.session_id}_final.jpg"
            final_path = os.path.join(dirs["final"], final_filename)
            composite.save(final_path, "JPEG", quality=95, dpi=(300, 300))

            self.composite_ready.emit(composite, final_path)
        except Exception as e:
            logger.error(f"Lỗi trong luồng ghép ảnh ngầm: {e}", exc_info=True)
            self.composite_failed.emit(str(e))


class PrintWorker(QThread):
    """
    Luồng in ảnh ngầm qua spooler Windows, ngăn chặn đơ giao diện khi gửi lệnh in.
    """
    print_finished = Signal(bool, str)

    def __init__(self, print_mgr: PrintManager, file_path: str, copies: int = 1, parent=None):
        super().__init__(parent)
        self.print_mgr = print_mgr
        self.file_path = file_path
        self.copies = copies

    def run(self):
        try:
            success = self.print_mgr.print_image(self.file_path, copies=self.copies)
            msg = f"Đã gửi lệnh in {self.copies} bản tới máy in!" if success else "Lệnh in đã được ghi nhận vào hàng đợi. Vui lòng kiểm tra cáp máy in trong tab 'Máy In'."
            self.print_finished.emit(success, msg)
        except Exception as e:
            self.print_finished.emit(False, str(e))


class FrameCardWidget(QFrame):
    """Thẻ khung ảnh trực quan hiển thị hình thumbnail thật của chính mẫu khung."""

    def __init__(self, template: FrameTemplate, thumbnail_pixmap: QPixmap, is_selected: bool, on_select, parent=None):
        super().__init__(parent)
        self.template = template
        self.on_select = on_select
        self.is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(80)
        self.setMaximumWidth(210)
        self.setFixedHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Khung chứa hình thu nhỏ (thumbnail)
        self.thumb_container = QWidget()
        self.thumb_container.setFixedHeight(62)
        thumb_l = QVBoxLayout(self.thumb_container)
        thumb_l.setContentsMargins(0, 0, 0, 0)
        thumb_l.setAlignment(Qt.AlignCenter)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setPixmap(thumbnail_pixmap.scaled(74, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        thumb_l.addWidget(self.lbl_thumb)

        # Dấu tích vàng Muted Champagne nhận diện khung đang chọn
        self.lbl_badge = QLabel("✓", self.thumb_container)
        self.lbl_badge.setAlignment(Qt.AlignCenter)
        self.lbl_badge.setFixedSize(16, 16)
        self.lbl_badge.setStyleSheet(
            f"background-color: {COLOR_CHAMPAGNE}; color: #FFFFFF; font-weight: 900; font-size: 10px; border-radius: 8px;"
        )
        self.lbl_badge.move(self.thumb_container.width() - 18, 2)
        self.lbl_badge.setVisible(is_selected)

        layout.addWidget(self.thumb_container)

        # Tên khổ in bên dưới
        display_name = template.name
        if template.is_dual_strip or "dual" in template.id.lower() or "ghép đôi" in display_name.lower():
            caption = "4x6 Ghép đôi"
        elif "ngang" in display_name.lower() or "landscape" in template.type.lower():
            caption = "4x6 Ngang"
        elif "4" in display_name and "2x6" in display_name:
            caption = "2x6 4 ảnh"
        elif "3" in display_name and "2x6" in display_name:
            caption = "2x6 3 ảnh"
        else:
            caption = display_name if len(display_name) <= 18 else (display_name[:17] + "…")

        self.lbl_caption = QLabel(caption)
        self.lbl_caption.setAlignment(Qt.AlignCenter)
        self.lbl_caption.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        layout.addWidget(self.lbl_caption)

        self._update_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.lbl_badge.move(self.thumb_container.width() - 18, 2)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.lbl_badge.setVisible(selected)
        self._update_style()

    def _update_style(self):
        if self.is_selected:
            self.setStyleSheet(
                f"FrameCardWidget {{ background-color: {COLOR_PALE_GOLD}; border: 1.5px solid {COLOR_CHAMPAGNE}; border-radius: 10px; }}"
            )
            self.lbl_caption.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        else:
            self.setStyleSheet(
                f"FrameCardWidget {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 10px; }}"
                f"FrameCardWidget:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
            )
            self.lbl_caption.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.on_select:
                self.on_select(self.template.id)
        super().mousePressEvent(event)


class KioskPage(QWidget):
    """Màn hình Photobooth Kiosk Studio Cưới chuẩn xác theo thiết kế mục tiêu."""

    session_finished = Signal(str)
    request_tab_switch = Signal(int)
    request_fullscreen = Signal()
    request_capture_fullscreen = Signal(bool)

    def minimumSizeHint(self) -> QSize:
        return QSize(720, 480)

    def __init__(
        self,
        camera_mgr: CameraManager,
        filter_engine: FilterEngine,
        frame_mgr: FrameManager,
        print_mgr: PrintManager,
        event_mgr: EventManager,
        token_mgr: TokenManager,
        config_mgr: ConfigManager,
        sync_mgr: Optional[SyncManager] = None,
        face_service=None,
        face_eye_af_controller=None,
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
        self.sync_mgr = sync_mgr
        self.current_final_path: Optional[str] = None

        # Trạng thái phiên chụp
        self.current_state = "IDLE"  # IDLE, COUNTDOWN, CAPTURING, REVIEW
        self.countdown_remaining = 3
        self.countdown_duration = int(self.config_mgr.get("countdown_seconds", 3))
        self.total_shots_needed = int(self.config_mgr.get("photos_per_session", 3))
        self.current_shot_index = 0
        self.captured_originals: List[Image.Image] = []
        self.captured_paths: List[str] = []
        self.selected_filter_id: Optional[str] = None
        self.selected_frame_id: Optional[str] = None
        self.current_composite: Optional[Image.Image] = None
        self.current_session_id: Optional[str] = None
        self.current_token: Optional[str] = None
        self._is_capture_immersive: bool = False

        # Cấu hình Smart Beauty Panel sau mỗi ảnh
        self._beauty_settings_cache: Optional[Dict[str, float]] = None
        self._beauty_enabled_cache: Optional[Dict[str, bool]] = None
        self._reuse_beauty_settings: bool = False

        # Carousel khung ảnh
        self.frame_cards: List[FrameCardWidget] = []
        self.frame_carousel_offset = 0

        # Bộ nhớ đệm thumbnail khung ảnh
        self._thumbnail_cache: Dict[str, QPixmap] = {}

        # Luồng chạy ngầm Live View
        self._live_view_active = False
        self.live_view_worker = CameraLiveViewWorker(self.camera_mgr, self)
        self.live_view_worker.frame_ready.connect(self._on_live_view_frame)
        self.live_view_worker.start()

        # Timer kiểm tra kết nối camera định kỳ (1.5s/lần)
        self.camera_poll_timer = QTimer(self)
        self.camera_poll_timer.timeout.connect(self._periodic_camera_check)
        self.camera_poll_timer.start(1500)

        # Timer đếm ngược chụp ảnh
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._on_countdown_tick)

        # Sử dụng Face & Eye Detection Service và FaceEyeAFController dùng chung (Single Source of Truth)
        # Kiosk chia sẻ cùng luồng nhận diện và lấy nét với CameraPage nhưng TUYỆT ĐỐI KHÔNG vẽ overlay
        self._face_service = face_service or getattr(self.camera_mgr, "face_service", None)
        if self._face_service is None:
            from vietphotobooth.camera.face_detector import FaceDetectionService
            self._face_service = FaceDetectionService(target_detection_fps=12.0)
        self._face_service.register_callback(self._on_faces_detected)

        self._face_eye_af_controller = face_eye_af_controller or getattr(self.camera_mgr, "face_eye_af_controller", None)
        if self._face_eye_af_controller is None:
            from vietphotobooth.camera.face_eye_af_controller import FaceEyeAFController
            self._face_eye_af_controller = FaceEyeAFController(
                af_trigger_fn=self.camera_mgr.trigger_autofocus,
                stability_frames=3,
                stability_px_threshold=20.0,
                movement_px_threshold=35.0,
                cooldown_sec=1.8,
            )

        self._latest_detected_faces: List[Any] = []
        self._latest_frame_shape: Optional[Tuple[int, int]] = None
        self._latest_detection_time: float = 0.0
        self._is_af_in_flight: bool = False
        self._capture_transaction_id: int = 0
        self._active_capture_tx: Optional[int] = None
        self._af_watchdog_timer = QTimer(self)
        self._af_watchdog_timer.setSingleShot(True)
        self._af_watchdog_timer.timeout.connect(self._on_af_timeout)
        self._retake_slot_index: Optional[int] = None

        # Bộ điều khiển âm thanh phòng chụp Studio (Voice cues, countdown beeps, mechanical shutter)
        self.sound_controller = SoundController(config_mgr=self.config_mgr, parent=self)

        # Biến đệm và worker nền
        self._composite_worker: Optional[CompositeWorker] = None
        self._print_worker: Optional[PrintWorker] = None
        self._cached_event_count: Optional[int] = None
        self._last_event_name: Optional[str] = None

        self._init_ui()
        self._load_frame_options()
        self._refresh_filter_options()
        self.start_live_view()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Bộ chuyển đổi trang nội bộ (QStackedWidget):
        # Index 0: Giao diện chụp ảnh Kiosk (Live View, nút chụp, chọn filter)
        # Index 1: Giao diện hoàn thiện ảnh & chọn khung (GuestReviewWidget)
        self.kiosk_stack = QStackedWidget(self)
        self.main_layout.addWidget(self.kiosk_stack)

        self.capture_container = QWidget()
        self.capture_layout = QVBoxLayout(self.capture_container)
        self.capture_layout.setContentsMargins(14, 10, 14, 12)
        self.capture_layout.setSpacing(10)

        # =============================================================
        # 1. KHU VỰC CHÍNH (LIVE VIEW MỞ RỘNG & TRẠNG THÁI CAMERA)
        # BỎ KHU VỰC SỰ KIỆN CHIẾM DIỆN TÍCH ĐỂ VIEWPORT CAMERA LỚN NHẤT
        # =============================================================
        self.top_row_layout = QHBoxLayout()
        self.top_row_layout.setSpacing(12)

        # -------------------------------------------------------------
        # KHUNG LIVE VIEW LỚN TỐI ĐA (CHÍNH GIỮA)
        # -------------------------------------------------------------
        self.card_live = QFrame()
        self.card_live.setObjectName("card_live")
        self.card_live.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.card_live.setStyleSheet(f"""
            QFrame#card_live {{
                background-color: {COLOR_LIVEVIEW};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_live = QVBoxLayout(self.card_live)
        l_live.setContentsMargins(6, 4, 6, 6)
        l_live.setSpacing(4)

        # Thanh tiêu đề / trạng thái ngay trên Live View
        self.live_top_bar = QHBoxLayout()
        self.live_top_bar.setContentsMargins(4, 2, 4, 2)

        self.lbl_live_badge = QLabel("📷 CHƯA KẾT NỐI MÁY ẢNH | XEM TRƯỚC GIAO DIỆN")
        self.lbl_live_badge.setStyleSheet(
            f"background-color: #FDE8E8; color: {COLOR_ERROR}; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #FCA5A5;"
        )
        self.live_top_bar.addWidget(self.lbl_live_badge)

        # Huy hiệu hiển thị sự kiện hiện tại gọn gàng
        self.lbl_active_event_pill = QLabel("📁 Sự kiện: SuKien_MacDinh")
        self.lbl_active_event_pill.setStyleSheet(
            f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border-radius: 6px; padding: 4px 10px; border: 1px solid {COLOR_BORDER};"
        )
        self.live_top_bar.addWidget(self.lbl_active_event_pill)

        self.btn_switch_event = QPushButton("Đổi Sự Kiện")
        self.btn_switch_event.setFixedHeight(24)
        self.btn_switch_event.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600; padding: 0 8px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; color: {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
        )
        self.btn_switch_event.clicked.connect(lambda: self.request_tab_switch.emit(4))
        self.live_top_bar.addWidget(self.btn_switch_event)

        self.live_top_bar.addStretch()

        self.lbl_live_res = QLabel("LIVE VIEW 1920 × 1080")
        self.lbl_live_res.setStyleSheet(
            f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 600; border-radius: 6px; padding: 4px 10px; border: 1px solid {COLOR_BORDER};"
        )
        self.live_top_bar.addWidget(self.lbl_live_res)

        self.btn_live_fullscreen = QPushButton()
        self.btn_live_fullscreen.setIcon(get_svg_icon("maximize", 15, COLOR_TEXT_PRIMARY))
        self.btn_live_fullscreen.setIconSize(QSize(15, 15))
        self.btn_live_fullscreen.setFixedSize(28, 26)
        self.btn_live_fullscreen.setCursor(Qt.PointingHandCursor)
        self.btn_live_fullscreen.setToolTip("Chế độ toàn màn hình (F11)")
        self.btn_live_fullscreen.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; padding: 0px; border-radius: 6px; border: 1px solid {COLOR_BORDER}; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
        )
        self.btn_live_fullscreen.clicked.connect(lambda: self.request_fullscreen.emit())
        self.live_top_bar.addWidget(self.btn_live_fullscreen)

        l_live.addLayout(self.live_top_bar)

        # Màn hình Live View chính (Zero-Jitter Viewport)
        self.lbl_viewport = CameraLiveViewport(self.card_live)
        self.lbl_viewport.set_face_detection_enabled(False)
        self.lbl_viewport.set_face_eye_af_state(False, None, None)
        self.lbl_viewport.setMinimumHeight(240)
        self.lbl_viewport.register_resize_callback(self._reposition_viewport_overlays)
        l_live.addWidget(self.lbl_viewport, 1)

        # Panel chờ kết nối rõ ràng (chuẩn studio, KHÔNG hiển thị người giả lập)
        self.panel_disconnected = QWidget(self.lbl_viewport)
        l_disc = QVBoxLayout(self.panel_disconnected)
        l_disc.setAlignment(Qt.AlignCenter)
        l_disc.setSpacing(10)

        icon_cam = QLabel("📷")
        icon_cam.setAlignment(Qt.AlignCenter)
        icon_cam.setStyleSheet(f"font-size: 54px; color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;")
        l_disc.addWidget(icon_cam)

        lbl_disc_title = QLabel("CHƯA KẾT NỐI MÁY ẢNH")
        lbl_disc_title.setAlignment(Qt.AlignCenter)
        lbl_disc_title.setStyleSheet(f"color: {COLOR_CHAMPAGNE}; font-size: 20px; font-weight: 900; background: transparent; border: none;")
        l_disc.addWidget(lbl_disc_title)

        lbl_disc_desc = QLabel("Vui lòng cắm cáp USB máy ảnh DSLR/Mirrorless và bấm nút 'Kết nối máy ảnh' bên phải.")
        lbl_disc_desc.setAlignment(Qt.AlignCenter)
        lbl_disc_desc.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px; background: transparent; border: none;")
        l_disc.addWidget(lbl_disc_desc)

        self.panel_disconnected.show()

        # Panel cảnh báo không có luồng hình ảnh Live View (khi camera báo kết nối nhưng không đọc được frame)
        self.panel_no_feed = QWidget(self.lbl_viewport)
        l_no_feed = QVBoxLayout(self.panel_no_feed)
        l_no_feed.setAlignment(Qt.AlignCenter)
        l_no_feed.setSpacing(10)

        icon_warning = QLabel("⚠️")
        icon_warning.setAlignment(Qt.AlignCenter)
        icon_warning.setStyleSheet("font-size: 48px; background: transparent; border: none;")
        l_no_feed.addWidget(icon_warning)

        self.lbl_no_feed_title = QLabel("CHƯA CÓ TÍN HIỆU LIVE VIEW")
        self.lbl_no_feed_title.setAlignment(Qt.AlignCenter)
        self.lbl_no_feed_title.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 18px; font-weight: 900; background: transparent; border: none;")
        l_no_feed.addWidget(self.lbl_no_feed_title)

        self.lbl_no_feed_desc = QLabel(
            "• Nếu dùng Nikon D780: Hãy gạt cần mở Live View trên máy ảnh, hoặc chọn nguồn 'Nikon Webcam Utility' trong tab Máy Ảnh.\n"
            "• Nếu dùng DIGICAM: digiCamControl chưa phát luồng Live View qua cổng 5513."
        )
        self.lbl_no_feed_desc.setAlignment(Qt.AlignCenter)
        self.lbl_no_feed_desc.setWordWrap(True)
        self.lbl_no_feed_desc.setStyleSheet(
            f"color: {COLOR_PALE_GOLD}; font-size: 13px; background: rgba(30, 26, 22, 0.92); "
            f"padding: 12px 20px; border-radius: 8px; border: 1px solid {COLOR_TEXT_SECONDARY}; line-height: 1.4;"
        )
        l_no_feed.addWidget(self.lbl_no_feed_desc)

        self.panel_no_feed.hide()
        self._last_live_frame_time = 0.0

        # Overlay đếm ngược to ở giữa
        self.lbl_countdown = QLabel("", self.lbl_viewport)
        self.lbl_countdown.setAlignment(Qt.AlignCenter)
        self.lbl_countdown.setStyleSheet(f"color: {COLOR_CHAMPAGNE}; font-size: 130px; font-weight: 900; background: rgba(23,25,28,0.75); border: 3px solid {COLOR_CHAMPAGNE}; border-radius: 36px;")
        self.lbl_countdown.hide()

        # Label trạng thái ảnh ("Đang chụp ảnh 1/3...")
        self.lbl_status_badge = QLabel("", self.lbl_viewport)
        self.lbl_status_badge.setAlignment(Qt.AlignCenter)
        self.lbl_status_badge.setStyleSheet(f"color: {COLOR_PALE_GOLD}; font-size: 20px; font-weight: bold; background: rgba(23,25,28,0.92); border: 1.5px solid {COLOR_CHAMPAGNE}; padding: 8px 24px; border-radius: 18px;")
        self.lbl_status_badge.hide()

        # -------------------------------------------------------------
        # CỘT PHẢI: TRẠNG THÁI MÁY ẢNH (Bảo toàn trong memory & API, không hiển thị trên layout chính)
        # -------------------------------------------------------------
        self.card_camera = QFrame(self)
        self.card_camera.setObjectName("card_camera")
        self.card_camera.setGeometry(-9999, -9999, 200, 100)
        self.card_camera.show()
        self.card_camera.setMinimumWidth(190)
        self.card_camera.setMaximumWidth(250)
        self.card_camera.setStyleSheet(f"""
            QFrame#card_camera {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_cam = QVBoxLayout(self.card_camera)
        l_cam.setContentsMargins(14, 14, 14, 14)
        l_cam.setSpacing(12)

        lbl_cam_card_title = QLabel("📷 <b>TRẠNG THÁI MÁY ẢNH</b>")
        lbl_cam_card_title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        l_cam.addWidget(lbl_cam_card_title)

        # Chấm trạng thái và nhãn
        h_stat = QHBoxLayout()
        h_stat.setSpacing(8)
        self.lbl_cam_dot = QLabel("🔴")
        self.lbl_cam_dot.setStyleSheet("font-size: 16px; border: none; background: transparent;")
        h_stat.addWidget(self.lbl_cam_dot)

        self.lbl_cam_status_text = QLabel("Chưa kết nối máy ảnh")
        self.lbl_cam_status_text.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 14px; font-weight: 700; border: none; background: transparent;")
        h_stat.addWidget(self.lbl_cam_status_text)
        h_stat.addStretch()
        l_cam.addLayout(h_stat)

        # Ghi chú hướng dẫn
        self.lbl_cam_note = QLabel("Hãy kết nối máy ảnh và chọn thiết bị trong mục Máy ảnh để bắt đầu chụp.")
        self.lbl_cam_note.setWordWrap(True)
        self.lbl_cam_note.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; line-height: 1.3; border: none; background: transparent;")
        l_cam.addWidget(self.lbl_cam_note)

        l_cam.addSpacing(6)

        # Nút Kết nối máy ảnh màu vàng champagne
        self.btn_reconnect_cam = QPushButton("🔗 Kết nối máy ảnh")
        self.btn_reconnect_cam.setFixedHeight(42)
        self.btn_reconnect_cam.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT}); "
            f"color: #1C1D1C; font-weight: 800; font-size: 13px; border-radius: 8px; border: none; }}"
            f"QPushButton:hover {{ background: #A88952; color: #FFFFFF; }}"
        )
        self.btn_reconnect_cam.clicked.connect(self._reconnect_camera)
        l_cam.addWidget(self.btn_reconnect_cam)

        # Nút Mở cài đặt máy ảnh
        self.btn_cam_settings = QPushButton("⚙️ Mở cài đặt máy ảnh")
        self.btn_cam_settings.setFixedHeight(42)
        self.btn_cam_settings.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; color: {COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        self.btn_cam_settings.clicked.connect(lambda: self.request_tab_switch.emit(2))
        l_cam.addWidget(self.btn_cam_settings)

        l_cam.addStretch()
        # Không add card_camera vào layout để Live View mở rộng tối đa toàn bộ chiều ngang
        # Thông tin camera được tinh giản trên live_top_bar và quản lý đầy đủ tại Cài đặt/Giám sát thiết bị

        # Giữ lại các layout rỗng để bảo toàn tương thích ngược cho các module/test
        self.ctrl_row_layout = QHBoxLayout()
        self.bottom_bar_layout = QHBoxLayout()

        # =============================================================
        # BỐ CỤC 2 KHU VỰC CHÍNH (BUILD 212):
        # BÊN TRÁI (70–75%): LIVE VIEW LỚN + NÚT BẮT ĐẦU CHỤP CHÍNH GIỮA DƯỚI LIVE VIEW
        # BÊN PHẢI (25–30%): MẪU KHUNG ẢNH -> BỘ LỌC MÀU -> TÙY CHỌN CHỤP -> SỐ ẢNH & ĐẾM NGƯỢC
        # =============================================================

        # -------------------------------------------------------------
        # 1. KHU VỰC BÊN TRÁI (70–75%): LIVE VIEW & NÚT BẮT ĐẦU CHỤP
        # -------------------------------------------------------------
        self.left_live_widget = QWidget()
        self.left_live_widget.setObjectName("left_live_widget")
        self.left_live_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        l_live_area = QVBoxLayout(self.left_live_widget)
        l_live_area.setContentsMargins(0, 0, 0, 0)
        l_live_area.setSpacing(10)

        l_live_area.addWidget(self.card_live, 1)

        # Thanh hành động chính giữa phía dưới Live View (chứa Nút BẮT ĐẦU CHỤP)
        self.capture_action_bar = QWidget()
        self.capture_action_bar.setObjectName("bottom_panel_widget")
        self.bottom_panel_widget = self.capture_action_bar
        self.capture_action_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        l_action_bar = QGridLayout(self.capture_action_bar)
        l_action_bar.setContentsMargins(0, 2, 0, 2)
        l_action_bar.setHorizontalSpacing(8)
        l_action_bar.setColumnStretch(0, 1)
        l_action_bar.setColumnStretch(1, 0)
        l_action_bar.setColumnStretch(2, 1)

        self.btn_start = QPushButton("📷 BẮT ĐẦU CHỤP")
        self.btn_start.setFixedSize(360, 48)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet(
            f"QPushButton {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT});"
            f"  color: #1C1D1C;"
            f"  font-size: 18px;"
            f"  font-weight: 800;"
            f"  letter-spacing: 0.5px;"
            f"  border-radius: 24px;"
            f"  border: none;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: #A88952;"
            f"  color: #FFFFFF;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background: #8F7240;"
            f"  color: #FFFFFF;"
            f"}}"
            f"QPushButton:disabled {{"
            f"  background: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid {COLOR_BORDER};"
            f"}}"
        )
        self.btn_start.clicked.connect(self.start_capture_flow)
        l_action_bar.addWidget(self.btn_start, 0, 1, Qt.AlignCenter)

        # Nút Toàn màn hình & Các nút Review fallback bên phải thanh dưới Live View
        self.right_action_box = QWidget()
        l_act = QHBoxLayout(self.right_action_box)
        l_act.setContentsMargins(0, 0, 0, 0)
        l_act.setSpacing(8)

        self.btn_fullscreen = QPushButton(" Toàn màn hình")
        self.btn_fullscreen.setIcon(get_svg_icon("maximize", 15, COLOR_TEXT_PRIMARY))
        self.btn_fullscreen.setIconSize(QSize(15, 15))
        self.btn_fullscreen.setFixedHeight(48)
        self.btn_fullscreen.setCursor(Qt.PointingHandCursor)
        self.btn_fullscreen.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 600; padding: 0 14px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        self.btn_fullscreen.clicked.connect(lambda: self.request_fullscreen.emit())
        l_act.addWidget(self.btn_fullscreen, 0, Qt.AlignRight)

        # CÁC NÚT KHI Ở CHẾ ĐỘ XEM KẾT QUẢ FALLBACK (ẩn mặc định)
        self.btn_retake = QPushButton("🔄 Chụp Lại")
        self.btn_retake.setFixedHeight(48)
        self.btn_retake.setStyleSheet(f"background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; border-radius: 8px; font-weight: 700; padding: 0 16px;")
        self.btn_retake.clicked.connect(self._retake_session)
        self.btn_retake.hide()
        l_act.addWidget(self.btn_retake)

        self.btn_save = QPushButton("💾 Lưu Ảnh")
        self.btn_save.setFixedHeight(48)
        self.btn_save.setStyleSheet(f"background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; border-radius: 8px; font-weight: 700; padding: 0 16px;")
        self.btn_save.clicked.connect(self._save_photo_dialog)
        self.btn_save.hide()
        l_act.addWidget(self.btn_save)

        self.btn_qr = QPushButton("📱 Quét Mã QR")
        self.btn_qr.setFixedHeight(48)
        self.btn_qr.setStyleSheet(f"background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; border-radius: 8px; font-weight: 700; padding: 0 16px;")
        self.btn_qr.clicked.connect(self._show_qr_dialog)
        self.btn_qr.hide()
        l_act.addWidget(self.btn_qr)

        self.btn_print = QPushButton("🖨️ IN ẢNH")
        self.btn_print.setFixedHeight(48)
        self.btn_print.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT});"
            f"color: #1C1D1C; font-weight: 800; font-size: 14px; border-radius: 8px; border: none; padding: 0 20px;"
        )
        self.btn_print.clicked.connect(self._print_composite)
        self.btn_print.hide()
        l_act.addWidget(self.btn_print)

        self.btn_finish = QPushButton("✅ Hoàn Tất")
        self.btn_finish.setFixedHeight(48)
        self.btn_finish.setStyleSheet(f"background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; border-radius: 8px; font-weight: 700; padding: 0 16px;")
        self.btn_finish.clicked.connect(self._finish_session)
        self.btn_finish.hide()
        l_act.addWidget(self.btn_finish)

        l_action_bar.addWidget(self.right_action_box, 0, 2, Qt.AlignRight)
        l_live_area.addWidget(self.capture_action_bar, 0)

        # -------------------------------------------------------------
        # 2. KHU VỰC ĐIỀU KHIỂN BÊN PHẢI (25–30% CHIỀU RỘNG)
        # THỨ TỰ: 1. MẪU KHUNG ẢNH -> 2. BỘ LỌC MÀU -> 3. TÙY CHỌN CHỤP -> 4. SỐ ẢNH & ĐẾM NGƯỢC
        # -------------------------------------------------------------
        self.right_control_widget = QWidget()
        self.right_control_widget.setObjectName("right_control_widget")
        self.left_column_widget = self.right_control_widget
        self.right_control_widget.setMinimumWidth(300)
        self.right_control_widget.setMaximumWidth(480)
        self.right_control_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        l_col_right = QVBoxLayout(self.right_control_widget)
        l_col_right.setContentsMargins(0, 0, 0, 0)
        l_col_right.setSpacing(8)

        # --- MỤC 1: MẪU KHUNG ẢNH (LƯỚI 2 CỘT THUMBNAIL GỌN GÀNG) ---
        self.card_frames = QFrame()
        self.card_frames.setObjectName("card_frames")
        self.card_frames.setStyleSheet(f"""
            QFrame#card_frames {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_fr = QVBoxLayout(self.card_frames)
        l_fr.setContentsMargins(10, 8, 10, 8)
        l_fr.setSpacing(6)

        h_fr_head = QHBoxLayout()
        h_fr_head.setContentsMargins(0, 0, 0, 0)
        lbl_fr_title = QLabel("🖼️ <b>Mẫu khung ảnh</b>")
        lbl_fr_title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        h_fr_head.addWidget(lbl_fr_title)

        h_fr_head.addStretch()

        self.btn_goto_frames = QPushButton("Chọn khung khác")
        self.btn_goto_frames.setFixedHeight(24)
        self.btn_goto_frames.setCursor(Qt.PointingHandCursor)
        self.btn_goto_frames.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600; padding: 0 8px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; color: {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
        )
        self.btn_goto_frames.clicked.connect(lambda: self.request_tab_switch.emit(1))
        h_fr_head.addWidget(self.btn_goto_frames)
        l_fr.addLayout(h_fr_head)

        self.frames_container_layout = QGridLayout()
        self.frames_container_layout.setContentsMargins(0, 0, 0, 0)
        self.frames_container_layout.setSpacing(6)
        l_fr.addLayout(self.frames_container_layout)

        h_fr_nav = QHBoxLayout()
        h_fr_nav.setContentsMargins(2, 2, 2, 0)
        h_fr_nav.setSpacing(6)

        self.btn_frame_prev = QPushButton()
        self.btn_frame_prev.setIcon(get_svg_icon("chevron_left", 15, COLOR_GOLD_DARK))
        self.btn_frame_prev.setIconSize(QSize(15, 15))
        self.btn_frame_prev.setFixedSize(32, 26)
        self.btn_frame_prev.setCursor(Qt.PointingHandCursor)
        self.btn_frame_prev.setToolTip("Trang trước")
        self.btn_frame_prev.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 0px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
            f"QPushButton:disabled {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER_LIGHT}; }}"
        )
        self.btn_frame_prev.clicked.connect(self._prev_frame_page)
        h_fr_nav.addWidget(self.btn_frame_prev)

        self.lbl_frame_page = QLabel("Trang 1/1")
        self.lbl_frame_page.setAlignment(Qt.AlignCenter)
        self.lbl_frame_page.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        h_fr_nav.addWidget(self.lbl_frame_page, 1)

        self.btn_frame_next = QPushButton()
        self.btn_frame_next.setIcon(get_svg_icon("chevron_right", 15, COLOR_GOLD_DARK))
        self.btn_frame_next.setIconSize(QSize(15, 15))
        self.btn_frame_next.setFixedSize(32, 26)
        self.btn_frame_next.setCursor(Qt.PointingHandCursor)
        self.btn_frame_next.setToolTip("Trang kế tiếp")
        self.btn_frame_next.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 0px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
            f"QPushButton:disabled {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER_LIGHT}; }}"
        )
        self.btn_frame_next.clicked.connect(self._next_frame_page)
        h_fr_nav.addWidget(self.btn_frame_next)

        l_fr.addLayout(h_fr_nav)
        l_col_right.addWidget(self.card_frames)

        # --- MỤC 2: BỘ LỌC MÀU (ĐẶT NGAY DƯỚI MẪU KHUNG ẢNH) ---
        self.card_filters = QFrame()
        self.card_filters.setObjectName("card_filters")
        self.card_filters.setFixedHeight(44)
        self.card_filters.setStyleSheet(f"""
            QFrame#card_filters {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_fil = QHBoxLayout(self.card_filters)
        l_fil.setContentsMargins(10, 4, 10, 4)
        l_fil.setSpacing(6)

        lbl_fil_title = QLabel("🎨 <b>Bộ lọc màu:</b>")
        lbl_fil_title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        l_fil.addWidget(lbl_fil_title)

        self.widget_no_filter = QWidget()
        l_nf = QHBoxLayout(self.widget_no_filter)
        l_nf.setContentsMargins(0, 0, 0, 0)
        l_nf.setSpacing(6)

        lbl_nf_text = QLabel("Chưa chọn")
        lbl_nf_text.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; border: none; background: transparent;")
        l_nf.addWidget(lbl_nf_text, 1)

        self.btn_add_filter_champagne = QPushButton("➕ Thêm")
        self.btn_add_filter_champagne.setFixedHeight(26)
        self.btn_add_filter_champagne.setCursor(Qt.PointingHandCursor)
        self.btn_add_filter_champagne.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT}); "
            f"color: #1C1D1C; font-weight: 800; font-size: 11px; border-radius: 5px; border: none; padding: 0 10px; }}"
            f"QPushButton:hover {{ background: #A88952; color: #FFFFFF; }}"
        )
        self.btn_add_filter_champagne.clicked.connect(self._open_filter_dialog)
        l_nf.addWidget(self.btn_add_filter_champagne)
        l_fil.addWidget(self.widget_no_filter, 1)

        self.widget_has_filters = QWidget()
        l_hf = QHBoxLayout(self.widget_has_filters)
        l_hf.setContentsMargins(0, 0, 0, 0)
        l_hf.setSpacing(4)

        self.combo_active_filters = QComboBox()
        self.combo_active_filters.setFixedHeight(26)
        self.combo_active_filters.setStyleSheet(
            f"QComboBox {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 5px; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600; padding: 0 6px; }}"
        )
        self.combo_active_filters.currentIndexChanged.connect(self._on_filter_changed)
        l_hf.addWidget(self.combo_active_filters, 1)

        self.btn_manage_filter = QPushButton("+")
        self.btn_manage_filter.setFixedSize(26, 26)
        self.btn_manage_filter.setCursor(Qt.PointingHandCursor)
        self.btn_manage_filter.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 5px; color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 700; padding: 0px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; color: {COLOR_TEXT_PRIMARY}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
        )
        self.btn_manage_filter.clicked.connect(self._open_filter_dialog)
        l_hf.addWidget(self.btn_manage_filter)

        self.widget_has_filters.hide()
        l_fil.addWidget(self.widget_has_filters, 1)
        l_col_right.addWidget(self.card_filters)

        # --- MỤC 3: TÙY CHỌN CHỤP (GOM LÀM ĐẸP AI & XEM TRƯỚC) ---
        chk_style = (
            f"QCheckBox {{ color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600; spacing: 6px; }} "
            f"QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {COLOR_BORDER}; border-radius: 4px; background: {COLOR_SURFACE}; }} "
            f"QCheckBox::indicator:checked {{ background: {COLOR_CHAMPAGNE}; border: 1px solid {COLOR_CHAMPAGNE}; }}"
        )
        self.card_options = QFrame()
        self.card_options.setObjectName("card_options")
        self.card_options.setFixedHeight(62)
        self.card_options.setStyleSheet(f"""
            QFrame#card_options {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_opt_box = QVBoxLayout(self.card_options)
        l_opt_box.setContentsMargins(10, 6, 10, 6)
        l_opt_box.setSpacing(4)

        lbl_opt_title = QLabel("⚙️ <b>Tùy chọn chụp</b>")
        lbl_opt_title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        l_opt_box.addWidget(lbl_opt_title)

        l_opt = QHBoxLayout()
        l_opt.setContentsMargins(0, 0, 0, 0)
        l_opt.setSpacing(12)

        self.chk_beauty = QCheckBox("✨ Làm đẹp thông minh AI")
        self.chk_beauty.setChecked(self.config_mgr.get("kiosk.enable_smart_beauty", True))
        self.chk_beauty.toggled.connect(lambda val: self.config_mgr.set("kiosk.enable_smart_beauty", val))
        self.chk_beauty.setStyleSheet(chk_style)
        l_opt.addWidget(self.chk_beauty)

        self.chk_preview = QCheckBox("👁️ Xem trước")
        self.chk_preview.setChecked(True)
        self.chk_preview.setStyleSheet(chk_style)
        l_opt.addWidget(self.chk_preview)

        self.chk_autoprint = QCheckBox("Tự động in")
        self.chk_autoprint.setChecked(False)
        self.chk_autoprint.setStyleSheet(chk_style)
        self.chk_autoprint.hide()
        l_opt.addWidget(self.chk_autoprint)
        l_opt.addStretch()

        l_opt_box.addLayout(l_opt)
        l_col_right.addWidget(self.card_options)

        l_col_right.addStretch(1)

        # --- MỤC 4: SỐ ẢNH VÀ ĐẾM NGƯỢC (CUỐI KHU VỰC ĐIỀU KHIỂN, GOM CHUNG 1 CARD) ---
        self.card_session_settings = QFrame()
        self.card_session_settings.setObjectName("card_session_settings")
        self.card_session_settings.setStyleSheet(f"""
            QFrame#card_session_settings {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_sess = QVBoxLayout(self.card_session_settings)
        l_sess.setContentsMargins(10, 8, 10, 8)
        l_sess.setSpacing(8)

        # Hàng 1: Số ảnh (chuẩn cảm ứng 44×44, 50×44)
        self.card_shots = QFrame(self.card_session_settings)
        self.card_shots.setObjectName("card_shots")
        self.card_shots.setStyleSheet("background: transparent; border: none;")
        l_shots = QHBoxLayout(self.card_shots)
        l_shots.setContentsMargins(0, 0, 0, 0)
        l_shots.setSpacing(6)

        lbl_s_title = QLabel("📚 <b>Số ảnh:</b>")
        lbl_s_title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        l_shots.addWidget(lbl_s_title)
        l_shots.addStretch()

        self.btn_shots_minus = QPushButton("−")
        self.btn_shots_minus.setFixedSize(44, 44)
        self.btn_shots_minus.setCursor(Qt.PointingHandCursor)
        self.btn_shots_minus.setStyleSheet(
            f"QPushButton {{ min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; "
            f"font-size: 22px; font-weight: 900; background-color: {COLOR_SURFACE_SECONDARY}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 8px; color: {COLOR_TEXT_PRIMARY}; padding: 0px; margin: 0px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; color: {COLOR_TEXT_PRIMARY}; background-color: #E2DED5; }}"
            f"QPushButton:pressed {{ background-color: #D5CDC0; }}"
            f"QPushButton:disabled {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid {COLOR_BORDER}; }}"
        )
        self.btn_shots_minus.clicked.connect(self._decrease_shots)
        l_shots.addWidget(self.btn_shots_minus)

        self.txt_shots_input = QLineEdit(str(self.total_shots_needed))
        self.txt_shots_input.setFixedSize(50, 44)
        self.txt_shots_input.setAlignment(Qt.AlignCenter)
        self.txt_shots_input.setMaxLength(2)
        self.txt_shots_input.setToolTip("Nhập trực tiếp số ảnh (1 đến 16)")
        self.txt_shots_input.setStyleSheet(
            f"QLineEdit {{ min-width: 50px; max-width: 50px; min-height: 44px; max-height: 44px; "
            f"background: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; font-size: 16px; font-weight: 900; "
            f"border: 1.5px solid {COLOR_CHAMPAGNE}; border-radius: 8px; padding: 0px; margin: 0px; selection-background-color: {COLOR_CHAMPAGNE}; selection-color: #FFFFFF; }}"
            f"QLineEdit:focus {{ border: 2px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE}; }}"
            f"QLineEdit:disabled {{ background: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid {COLOR_BORDER}; }}"
        )
        self.txt_shots_input.setValidator(QIntValidator(1, 16, self))
        self.txt_shots_input.editingFinished.connect(self._on_shots_input_finished)
        self.txt_shots_input.returnPressed.connect(self._on_shots_input_finished)
        l_shots.addWidget(self.txt_shots_input)

        self.btn_shots_plus = QPushButton("+")
        self.btn_shots_plus.setFixedSize(44, 44)
        self.btn_shots_plus.setCursor(Qt.PointingHandCursor)
        self.btn_shots_plus.setStyleSheet(
            f"QPushButton {{ min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; "
            f"font-size: 22px; font-weight: 900; background-color: {COLOR_SURFACE_SECONDARY}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 8px; color: {COLOR_TEXT_PRIMARY}; padding: 0px; margin: 0px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; color: {COLOR_TEXT_PRIMARY}; background-color: #E2DED5; }}"
            f"QPushButton:pressed {{ background-color: #D5CDC0; }}"
            f"QPushButton:disabled {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid {COLOR_BORDER}; }}"
        )
        self.btn_shots_plus.clicked.connect(self._increase_shots)
        l_shots.addWidget(self.btn_shots_plus)
        l_sess.addWidget(self.card_shots)

        # Đường ngăn cách ngang nhẹ
        sep_sess = QFrame()
        sep_sess.setFrameShape(QFrame.HLine)
        sep_sess.setFrameShadow(QFrame.Plain)
        sep_sess.setStyleSheet(f"color: {COLOR_BORDER_LIGHT};")
        l_sess.addWidget(sep_sess)

        # Hàng 2: Đếm ngược (3s, 5s, 10s)
        self.card_cd = QFrame(self.card_session_settings)
        self.card_cd.setObjectName("card_cd")
        self.card_cd.setStyleSheet("background: transparent; border: none;")
        l_cd = QHBoxLayout(self.card_cd)
        l_cd.setContentsMargins(0, 0, 0, 0)
        l_cd.setSpacing(6)

        lbl_cd_title = QLabel("⏱️ <b>Đếm ngược:</b>")
        lbl_cd_title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        l_cd.addWidget(lbl_cd_title)
        l_cd.addStretch()

        self.btn_cd_3 = QPushButton("3s")
        self.btn_cd_3.setFixedSize(44, 44)
        self.btn_cd_3.setToolTip("Đếm ngược 3 giây")
        self.btn_cd_3.clicked.connect(lambda: self._set_countdown_duration(3))
        l_cd.addWidget(self.btn_cd_3)

        self.btn_cd_5 = QPushButton("5s")
        self.btn_cd_5.setFixedSize(44, 44)
        self.btn_cd_5.setToolTip("Đếm ngược 5 giây")
        self.btn_cd_5.clicked.connect(lambda: self._set_countdown_duration(5))
        l_cd.addWidget(self.btn_cd_5)

        self.btn_cd_10 = QPushButton("10s")
        self.btn_cd_10.setFixedSize(44, 44)
        self.btn_cd_10.setToolTip("Đếm ngược 10 giây")
        self.btn_cd_10.clicked.connect(lambda: self._set_countdown_duration(10))
        l_cd.addWidget(self.btn_cd_10)

        l_sess.addWidget(self.card_cd)
        l_col_right.addWidget(self.card_session_settings)

        # Ghép Khu Vực Trái (73%) và Khu Vực Phải (27%) vào top_row_layout
        self.top_row_layout.addWidget(self.left_live_widget, 73)
        self.top_row_layout.addWidget(self.right_control_widget, 27)
        self.capture_layout.addLayout(self.top_row_layout, 1)

        # Import và tích hợp GuestReviewWidget làm trang hoàn thiện nội bộ (In-window Review)
        from vietphotobooth.desktop.widgets.guest_review_dialog import GuestReviewWidget
        self.review_widget = GuestReviewWidget(
            photos=[],
            frame_mgr=self.frame_mgr,
            initial_frame_id=self.selected_frame_id,
            event_name=self.event_mgr.get_active_event_name(),
            session_id=self.current_session_id or "Session_001",
            print_mgr=self.print_mgr,
            parent=self
        )
        self.review_widget.retake_requested.connect(self._on_review_retake)
        self.review_widget.retake_slot_requested.connect(self._on_review_retake_slot)
        self.review_widget.finish_requested.connect(self._on_review_finish)
        self.review_widget.photo_saved.connect(self._on_review_photo_saved)
        self.review_widget.print_completed.connect(self._on_review_print_completed)
        self.review_widget.frame_changed.connect(self._on_review_frame_changed)

        self.kiosk_stack.addWidget(self.capture_container)  # Index 0: Giao diện chụp ảnh Kiosk
        self.kiosk_stack.addWidget(self.review_widget)      # Index 1: Hoàn thiện ảnh & chọn khung
        self.kiosk_stack.setCurrentIndex(0)

        # Cập nhật style ban đầu cho các nút chọn
        self._update_countdown_buttons_style()

    # -------------------------------------------------------------
    # SỰ KIỆN & THỐNG KÊ
    # -------------------------------------------------------------
    def _load_event_banner(self):
        self._refresh_event_info()

    def _refresh_event_info(self):
        ev_name = self.event_mgr.get_active_event_name()
        if getattr(self, "_last_event_name", None) != ev_name or getattr(self, "_cached_event_count", None) is None:
            self._last_event_name = ev_name
            dirs = self.event_mgr.get_event_dirs(ev_name)
            count = 0
            if os.path.exists(dirs["final"]):
                count = len([f for f in os.listdir(dirs["final"]) if f.lower().endswith((".jpg", ".jpeg", ".png"))])
            self._cached_event_count = count
        if hasattr(self, "lbl_active_event_pill"):
            self.lbl_active_event_pill.setText(f"📁 Sự kiện: {ev_name} ({self._cached_event_count} ảnh)")

    def _increment_event_photo_count(self):
        if getattr(self, "_cached_event_count", None) is not None:
            self._cached_event_count += 1
        else:
            self._cached_event_count = 1
        ev_name = self.event_mgr.get_active_event_name()
        if hasattr(self, "lbl_active_event_pill"):
            self.lbl_active_event_pill.setText(f"📁 Sự kiện: {ev_name} ({self._cached_event_count} ảnh)")

    # -------------------------------------------------------------
    # QUẢN LÝ SỐ ẢNH & ĐẾM NGƯỢC
    # -------------------------------------------------------------
    def _set_shots_count(self, count: int):
        clamped = max(1, min(16, int(count)))
        self.total_shots_needed = clamped
        if hasattr(self, 'txt_shots_input') and self.txt_shots_input.text() != str(clamped):
            self.txt_shots_input.setText(str(clamped))

    def _decrease_shots(self):
        self._set_shots_count(self.total_shots_needed - 1)

    def _increase_shots(self):
        self._set_shots_count(self.total_shots_needed + 1)

    def _on_shots_input_finished(self):
        val = self.txt_shots_input.text().strip()
        try:
            num = int(val)
            self._set_shots_count(num)
        except ValueError:
            self.txt_shots_input.setText(str(self.total_shots_needed))
        self.txt_shots_input.clearFocus()

    def _on_shots_input_clicked(self, event):
        dlg = TouchNumberPadDialog(self.total_shots_needed, min_val=1, max_val=16, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._set_shots_count(dlg.value)
        QLineEdit.mousePressEvent(self.txt_shots_input, event)

    def _set_countdown_duration(self, seconds: int):
        self.countdown_duration = seconds
        self._update_countdown_buttons_style()

    def _update_countdown_buttons_style(self):
        active_style = (
            f"QPushButton {{ min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT}); "
            f"color: #1C1D1C; font-weight: 900; font-size: 14px; border-radius: 8px; border: none; padding: 0px; margin: 0px; }}"
        )
        inactive_style = (
            f"QPushButton {{ min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; "
            f"background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; "
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 14px; font-weight: 700; padding: 0px; margin: 0px; }}"
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; color: {COLOR_TEXT_PRIMARY}; background-color: #E2DED5; }}"
        )
        self.btn_cd_3.setStyleSheet(active_style if self.countdown_duration == 3 else inactive_style)
        self.btn_cd_5.setStyleSheet(active_style if self.countdown_duration == 5 else inactive_style)
        self.btn_cd_10.setStyleSheet(active_style if self.countdown_duration == 10 else inactive_style)

    # -------------------------------------------------------------
    # CAROUSEL THUMBNAIL KHUNG ẢNH THẬT
    # -------------------------------------------------------------
    def _load_frame_options(self):
        # Dọn sạch thẻ cũ trong carousel
        while self.frames_container_layout.count():
            item = self.frames_container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.frame_cards.clear()
        frames = self.frame_mgr.list_frames()

        if not frames:
            lbl_empty = QLabel("Chưa có khung ảnh.")
            lbl_empty.setStyleSheet(f"color: {THEME_TEXT_SECONDARY}; font-style: italic; font-size: 11px; border: none; background: transparent;")
            if isinstance(self.frames_container_layout, QGridLayout):
                self.frames_container_layout.addWidget(lbl_empty, 0, 0, 1, 2)
            else:
                self.frames_container_layout.addWidget(lbl_empty)
            self.btn_frame_prev.setEnabled(False)
            self.btn_frame_next.setEnabled(False)
            if hasattr(self, "lbl_frame_page"):
                self.lbl_frame_page.setText("0/0")
            return

        if not self.selected_frame_id and frames:
            self.selected_frame_id = frames[0].id

        page_size = self._get_carousel_page_size()
        start_idx = self.frame_carousel_offset
        end_idx = min(start_idx + page_size, len(frames))

        for i, idx in enumerate(range(start_idx, end_idx)):
            f = frames[idx]
            pix = self._get_frame_thumbnail_pixmap(f)
            card = FrameCardWidget(
                template=f,
                thumbnail_pixmap=pix,
                is_selected=(f.id == self.selected_frame_id),
                on_select=self._on_frame_card_selected,
                parent=self.card_frames
            )
            self.frame_cards.append(card)
            if isinstance(self.frames_container_layout, QGridLayout):
                row = i // 2
                col = i % 2
                self.frames_container_layout.addWidget(card, row, col)
            else:
                self.frames_container_layout.addWidget(card)

        # Cập nhật trạng thái kích hoạt của nút chuyển trang
        self.btn_frame_prev.setEnabled(self.frame_carousel_offset > 0)
        self.btn_frame_next.setEnabled(self.frame_carousel_offset + page_size < len(frames))
        if hasattr(self, "lbl_frame_page"):
            cur_p = (self.frame_carousel_offset // page_size) + 1
            tot_p = max(1, (len(frames) + page_size - 1) // page_size)
            self.lbl_frame_page.setText(f"{cur_p}/{tot_p}")

    def _get_carousel_page_size(self) -> int:
        """Tính toán số lượng thẻ khung hiển thị trong Cột Trái (2 cột x 2 hoặc 3 hàng)."""
        h = self.height() if hasattr(self, "height") else 768
        if h > 850:
            return 6
        return 4

    def _get_frame_thumbnail_pixmap(self, template: FrameTemplate) -> QPixmap:
        """Sinh hoặc lấy từ bộ nhớ đệm đĩa hình thumbnail thật của khung in ảnh."""
        if template.id in self._thumbnail_cache:
            return self._thumbnail_cache[template.id]

        # 1. Tải tức thì từ bộ nhớ đệm đĩa đã lưu sẵn (<0.5ms)
        try:
            thumb_path = self.frame_mgr.get_or_create_thumbnail(template)
            if thumb_path and os.path.exists(thumb_path):
                pix = QPixmap(thumb_path)
                if not pix.isNull():
                    self._thumbnail_cache[template.id] = pix
                    return pix
        except Exception as e:
            logger.debug(f"Không thể đọc thumbnail đĩa cho khung {template.id}: {e}")

        # 2. Sinh động nếu đĩa chưa có
        try:
            pil_thumb = FrameDesigner.generate_thumbnail(template, max_width=110, max_height=140)
            rgb = pil_thumb.convert("RGB")
            w, h = rgb.size
            qimg = QImage(rgb.tobytes("raw", "RGB"), w, h, 3 * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            self._thumbnail_cache[template.id] = pix
            return pix
        except Exception as e:
            logger.warning(f"Lỗi tạo thumbnail cho khung {template.id}: {e}")
            pix = QPixmap(100, 130)
            pix.fill(QColor(18, 28, 48))
            return pix

    def _prev_frame_page(self):
        frames = self.frame_mgr.list_frames()
        if not frames:
            return
        page_size = self._get_carousel_page_size()
        self.frame_carousel_offset = max(0, self.frame_carousel_offset - page_size)
        self._load_frame_options()

    def _next_frame_page(self):
        frames = self.frame_mgr.list_frames()
        if not frames:
            return
        page_size = self._get_carousel_page_size()
        if self.frame_carousel_offset + page_size < len(frames):
            self.frame_carousel_offset += page_size
            self._load_frame_options()

    def _on_frame_card_selected(self, frame_id: str):
        self.selected_frame_id = frame_id
        for card in self.frame_cards:
            card.set_selected(card.template.id == frame_id)

        template = self.frame_mgr.get_frame(frame_id)
        if template and template.slots:
            # Điều chỉnh số ảnh tương ứng với số slot nếu phù hợp
            if len(template.slots) in (3, 4):
                self._set_shots_count(len(template.slots))

        if self.current_state == "REVIEW":
            self._render_and_display_composite()

    # -------------------------------------------------------------
    # BỘ LỌC MÀU (THƯ VIỆN SẠCH & QUẢN LÝ)
    # -------------------------------------------------------------
    def _refresh_filter_options(self):
        presets = self.filter_engine.get_presets()
        self.combo_active_filters.blockSignals(True)
        self.combo_active_filters.clear()

        if not presets:
            self.widget_no_filter.show()
            self.widget_has_filters.hide()
            self.selected_filter_id = None
        else:
            self.widget_no_filter.hide()
            self.widget_has_filters.show()
            self.combo_active_filters.addItem("-- Không dùng bộ lọc --", None)
            for p in presets:
                self.combo_active_filters.addItem(f"✨ {p.name}", p.id)

            if self.selected_filter_id:
                idx = self.combo_active_filters.findData(self.selected_filter_id)
                if idx >= 0:
                    self.combo_active_filters.setCurrentIndex(idx)

        self.combo_active_filters.blockSignals(False)

    def _open_filter_dialog(self):
        dlg = FilterEditorDialog(self.filter_engine, self)
        dlg.exec()
        self._refresh_filter_options()
        if self.current_state == "REVIEW":
            self._render_and_display_composite()

    def _on_filter_changed(self, index: int):
        self.selected_filter_id = self.combo_active_filters.currentData()
        if self.current_state == "REVIEW":
            self._render_and_display_composite()

    # -------------------------------------------------------------
    # VÒNG ĐỜI GIAO DIỆN & LIVE VIEW (ASYNC THREADED 30 FPS)
    # -------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'live_view_worker'):
            self.live_view_worker.resume()
        if hasattr(self, 'camera_poll_timer') and not self.camera_poll_timer.isActive():
            self.camera_poll_timer.start(1500)
        self._update_camera_status_ui()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, 'live_view_worker'):
            self.live_view_worker.pause()
        if hasattr(self, 'camera_poll_timer') and self.camera_poll_timer.isActive():
            self.camera_poll_timer.stop()
        if hasattr(self, '_af_watchdog_timer') and self._af_watchdog_timer.isActive():
            self._af_watchdog_timer.stop()
        if getattr(self, '_active_capture_tx', None) is not None or getattr(self, '_is_af_in_flight', False):
            self._active_capture_tx = None
            self._is_af_in_flight = False
            try:
                self.camera_mgr.cancel_autofocus()
            except Exception:
                pass
        if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller:
            self._face_eye_af_controller.resume_auto_trigger()

    def start_live_view(self):
        self._live_view_active = True
        if hasattr(self, 'live_view_worker'):
            if not self.live_view_worker.isRunning():
                self.live_view_worker = CameraLiveViewWorker(self.camera_mgr, self)
                self.live_view_worker.frame_ready.connect(self._on_live_view_frame)
                self.live_view_worker.start()
            self.live_view_worker.resume()
        if hasattr(self, '_face_service') and self._face_service:
            is_detect = self.camera_mgr.is_face_detect_enabled() if hasattr(self.camera_mgr, "is_face_detect_enabled") else False
            is_af = self.camera_mgr.is_face_eye_af_enabled() if hasattr(self.camera_mgr, "is_face_eye_af_enabled") else False
            if is_detect or is_af:
                self._face_service.enable()
        self._update_camera_status_ui()

    def stop_live_view(self):
        self._live_view_active = False
        if hasattr(self, '_af_watchdog_timer') and self._af_watchdog_timer.isActive():
            self._af_watchdog_timer.stop()
        if getattr(self, '_active_capture_tx', None) is not None or getattr(self, '_is_af_in_flight', False):
            self._active_capture_tx = None
            self._is_af_in_flight = False
            try:
                self.camera_mgr.cancel_autofocus()
            except Exception:
                pass
        if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller:
            self._face_eye_af_controller.resume_auto_trigger()
        if hasattr(self, 'live_view_worker'):
            self.live_view_worker.pause()

    def _periodic_camera_check(self):
        if self.current_state in ("IDLE", "COUNTDOWN"):
            self._update_camera_status_ui()
            self._check_feed_timeout()

    def _check_feed_timeout(self):
        """Kiểm tra nếu camera kết nối nhưng không phát ra frame nào trong > 2.5s (tránh màn hình đen)."""
        is_conn = self.camera_mgr.is_connected()
        backend = self.camera_mgr.current_backend_name
        if not is_conn or backend == "simulator" or self.current_state not in ("IDLE", "COUNTDOWN"):
            if hasattr(self, "panel_no_feed") and self.panel_no_feed.isVisible():
                self.panel_no_feed.hide()
            return

        elapsed = time.time() - getattr(self, "_last_live_frame_time", 0.0)
        if elapsed > 2.5:
            info = self.camera_mgr.get_info()
            dev_name = info.get("device_name", backend.upper())
            err = self.camera_mgr.get_last_error()

            if backend in ("digicam", "dslr"):
                self.lbl_no_feed_title.setText("CHƯA CÓ LUỒNG LIVE VIEW TỪ DIGICAM")
                self.lbl_no_feed_desc.setText(
                    "digiCamControl chưa phát luồng Live View (cổng HTTP 5513).\n\n"
                    "• ĐỂ XEM TRỰC TIẾP TỪ NIKON D780: Vào tab 'Máy Ảnh' và chọn 'Nikon MAID Native USB' hoặc DirectShow 'Nikon Webcam Utility'.\n"
                    "• HOẶC: Mở cửa sổ digiCamControl và bấm nút 'Live View'."
                )
            elif backend == "nikon_maid":
                self.lbl_no_feed_title.setText(f"CHƯA CÓ TÍN HIỆU LIVE VIEW TỪ {dev_name.upper()}")
                hint = err if err else "Đang khởi tạo luồng dữ liệu Live View USB."
                self.lbl_no_feed_desc.setText(
                    f"{hint}\n\n"
                    "• Đảm bảo Nikon D780 đã bật nguồn và cắm cáp USB chắc chắn.\n"
                    "• Tắt các ứng dụng khác đang chiếm máy ảnh (NX Tether, digiCamControl)."
                )
            else:
                self.lbl_no_feed_title.setText(f"CHƯA CÓ TÍN HIỆU TỪ {dev_name.upper()}")
                hint = err if err else "Không nhận được khung hình dữ liệu nào."
                self.lbl_no_feed_desc.setText(
                    f"{hint}\n\n"
                    "• Nếu dùng Nikon D780: Gạt cần bật Live View (Lv) trên máy ảnh hoặc kiểm tra cáp USB.\n"
                    "• Tắt các ứng dụng khác (Discord, OBS, Zoom) nếu đang chiếm quyền webcam."
                )

            if hasattr(self, "panel_no_feed"):
                self.panel_no_feed.setGeometry(0, 0, self.lbl_viewport.width(), self.lbl_viewport.height())
                self.panel_no_feed.show()

    def _reposition_viewport_overlays(self):
        """Định vị các panel và overlay trong Viewport một lần duy nhất khi resize."""
        if not hasattr(self, "lbl_viewport"):
            return
        w = self.lbl_viewport.width()
        h = self.lbl_viewport.height()
        if w <= 10 or h <= 10:
            return

        if hasattr(self, "panel_disconnected"):
            self.panel_disconnected.setGeometry(0, 0, w, h)
        if hasattr(self, "panel_no_feed"):
            self.panel_no_feed.setGeometry(0, 0, w, h)
        if hasattr(self, "lbl_countdown"):
            cd_sz = min(260, min(w, h) - 40) if min(w, h) > 280 else 180
            cd_top = (h - cd_sz) // 2
            self.lbl_countdown.setGeometry((w - cd_sz) // 2, cd_top, cd_sz, cd_sz)
        if hasattr(self, "lbl_status_badge"):
            badge_w = min(max(340, self.lbl_status_badge.sizeHint().width() + 48), max(340, w - 40))
            badge_h = max(58, self.lbl_status_badge.sizeHint().height() + 4)
            cd_sz_eff = min(260, min(w, h) - 40) if min(w, h) > 280 else 180
            cd_top_eff = (h - cd_sz_eff) // 2
            badge_y = max(16, cd_top_eff - badge_h - 16)
            self.lbl_status_badge.setGeometry((w - badge_w) // 2, badge_y, badge_w, badge_h)

    def _on_live_view_frame(self, frame_rgb: np.ndarray):
        if not getattr(self, "_live_view_active", True) or self.current_state not in ("IDLE", "COUNTDOWN", "CAPTURING"):
            return
        if not self.camera_mgr.is_connected():
            return

        self._is_rendering_frame = True
        try:
            self._last_live_frame_time = time.time()
            if hasattr(self, "panel_no_feed"):
                self.panel_no_feed.hide()

            if hasattr(self, "panel_disconnected"):
                self.panel_disconnected.hide()

            if frame_rgb is None or frame_rgb.size == 0:
                return

            self.lbl_viewport.set_frame_rgb(frame_rgb)

            # Gửi khung hình cho Face & Eye Detection Service chạy ngầm
            if hasattr(self, "_face_service") and self._face_service.is_enabled:
                self._face_service.submit_frame(frame_rgb, sequence_id=0, timestamp=time.time())
        finally:
            self._is_rendering_frame = False

    def _on_faces_detected(self, faces, frame_shape=None, seq_id=0, ts=0.0):
        """
        Lưu trữ kết quả nhận diện khuôn mặt và mắt mới nhất để phục vụ lấy nét trước khi chụp,
        và chuyển tiếp vào FaceEyeAFController dùng chung.
        TUYỆT ĐỐI KHÔNG cập nhật vẽ lên Viewport để đảm bảo giao diện khách chụp 100% sạch đẹp.
        """
        self._latest_detected_faces = faces or []
        if frame_shape and frame_shape[0] > 0 and frame_shape[1] > 0:
            self._latest_frame_shape = frame_shape
        elif not getattr(self, "_latest_frame_shape", None) and hasattr(self, "lbl_viewport"):
            if hasattr(self.lbl_viewport, "get_source_dimensions"):
                src_w, src_h = self.lbl_viewport.get_source_dimensions()
                if src_w > 0 and src_h > 0:
                    self._latest_frame_shape = (src_w, src_h)
            else:
                cur_pix = getattr(self.lbl_viewport, "_current_pixmap", None)
                if cur_pix and cur_pix.width() > 0:
                    self._latest_frame_shape = (cur_pix.width(), cur_pix.height())
        self._latest_detection_time = time.time()

        if hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller and self._face_eye_af_controller.is_enabled:
            dim = self._latest_frame_shape
            self._face_eye_af_controller.process_faces(faces, frame_shape=dim, sequence_id=seq_id, timestamp=ts)

    def _reconnect_camera(self):
        """Thử dò quét và kết nối lại máy ảnh thực tế, ưu tiên Nikon D780 Native USB, rồi Nikon Webcam Utility nếu có."""
        self.lbl_cam_status_text.setText("Đang kết nối lại...")
        connected = False

        # 1. Ưu tiên kết nối trực tiếp Nikon D780 Native USB MAID SDK
        try:
            connected = self.camera_mgr.switch_backend("nikon_maid")
        except Exception as e:
            logger.debug(f"Kết nối Nikon MAID không thành công: {e}")
            connected = False

        # 2. Dự phòng: Quét DirectShow (Nikon Webcam Utility hoặc Webcam phần cứng)
        if not connected:
            from vietphotobooth.camera.enumerator import enumerate_directshow_devices
            devs = enumerate_directshow_devices()
            nikon_dev = next((d for d in devs if "nikon" in d["name"].lower()), None)
            if nikon_dev:
                connected = self.camera_mgr.switch_backend("directshow", nikon_dev["index"], nikon_dev["name"])
            elif devs:
                connected = self.camera_mgr.switch_backend("directshow", devs[0]["index"], devs[0]["name"])

        # 3. Dự phòng: digiCamControl
        if not connected:
            connected = self.camera_mgr.switch_backend("digicam")

        # 4. Cuối cùng: Chuyển về simulator an toàn
        if not connected:
            self.camera_mgr.switch_backend("simulator")

        self._update_camera_status_ui()
        if self.camera_mgr.is_connected() and self.camera_mgr.current_backend_name != "simulator":
            info = self.camera_mgr.get_info()
            dev_name = info.get("device_name", "")
            QMessageBox.information(self, "Máy Ảnh", f"Đã kết nối thành công với: {dev_name}!")
        else:
            QMessageBox.warning(self, "Máy Ảnh", "Chưa phát hiện máy ảnh USB. Đang giữ ở chế độ chờ kết nối.")

    def _update_camera_status_ui(self):
        is_conn = self.camera_mgr.is_connected()
        backend = self.camera_mgr.current_backend_name
        info = self.camera_mgr.get_info()
        dev_name = info.get("device_name", backend.upper())
        w, h = info.get("actual_resolution", (0, 0))

        if not is_conn:
            if hasattr(self, "countdown_timer") and self.countdown_timer.isActive():
                self._abort_capture_due_to_disconnect(
                    "Mất kết nối máy ảnh trong quá trình đếm ngược chuẩn bị chụp!\n\nVui lòng kiểm tra lại cáp kết nối USB."
                )
            self.lbl_cam_dot.setText("🔴")
            self.lbl_cam_status_text.setText("Chưa kết nối máy ảnh")
            self.lbl_cam_status_text.setStyleSheet("color: #C53030; font-size: 14px; font-weight: 700; border: none; background: transparent;")
            self.lbl_live_badge.setText("📷 CHƯA KẾT NỐI MÁY ẢNH | XEM TRƯỚC GIAO DIỆN")
            self.lbl_live_badge.setStyleSheet(
                "background-color: #FDE8E8; color: #C53030; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #FCA5A5;"
            )
            self.lbl_live_res.setText("LIVE VIEW (Chờ kết nối)")
            self.lbl_cam_note.setText("Hãy kết nối máy ảnh và chọn thiết bị trong mục Máy ảnh để bắt đầu chụp.")
            self.panel_disconnected.show()
            self.lbl_viewport.clear()
            self._reposition_viewport_overlays()
        elif backend == "simulator":
            self.lbl_cam_dot.setText("🟡")
            self.lbl_cam_status_text.setText("Mô phỏng (Simulator)")
            self.lbl_cam_status_text.setStyleSheet("color: #B45309; font-size: 14px; font-weight: 700; border: none; background: transparent;")
            self.lbl_live_badge.setText("🟡 CHẾ ĐỘ MÔ PHỎNG (SIMULATOR)")
            self.lbl_live_badge.setStyleSheet(
                "background-color: #FEF3C7; color: #B45309; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #FCD34D;"
            )
            self.lbl_live_res.setText("SIMULATOR 1920 × 1080 (30 FPS)")
            self.lbl_cam_note.setText("Đang ở chế độ mô phỏng studio. Kết nối máy ảnh thật trong tab 'Máy Ảnh' khi chụp thực tế.")
            if self.panel_disconnected.isVisible():
                self.panel_disconnected.hide()
        else:
            self.lbl_cam_dot.setText("🟢")
            self.lbl_cam_status_text.setText(f"Đã kết nối: {dev_name}")
            self.lbl_cam_status_text.setStyleSheet("color: #2E7D32; font-size: 14px; font-weight: 700; border: none; background: transparent;")
            self.lbl_live_badge.setText(f"📷 ĐÃ KẾT NỐI: {dev_name.upper()} [HARDWARE]")
            self.lbl_live_badge.setStyleSheet(
                "background-color: #E2EFE2; color: #2E7D32; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #A5D6A7;"
            )
            res_text = f"LIVE VIEW {w} × {h}" if (w > 0 and h > 0) else ("LIVE VIEW 1024 × 680" if backend == "nikon_maid" else ("LIVE VIEW 1920 × 1080" if backend != "digicam" else "LIVE VIEW 6000 × 4000"))
            self.lbl_live_res.setText(res_text)
            self.lbl_cam_note.setText("Máy ảnh đã sẵn sàng hoạt động. Nhấn 'Bắt đầu chụp' để ghi lại khoảnh khắc.")
            if self.panel_disconnected.isVisible():
                self.panel_disconnected.hide()

    def _update_live_view(self):
        """Hàm dự phòng tương thích gọi đồng bộ khi cần."""
        if not getattr(self, "_live_view_active", True):
            return
        frame_rgb = self.camera_mgr.get_liveview_rgb()
        if frame_rgb is not None:
            self._on_live_view_frame(frame_rgb)

    # -------------------------------------------------------------
    # TIẾN TRÌNH CHỤP ẢNH TỰ ĐỘNG & CHẾ ĐỘ TOÀN MÀN HÌNH TẬP TRUNG
    # -------------------------------------------------------------
    def set_capture_immersive_mode(self, active: bool):
        """Bật/tắt chế độ toàn màn hình tập trung tối đa cho Live View khi chụp ảnh."""
        self._is_capture_immersive = active
        if active:
            if hasattr(self, "right_control_widget"):
                self.right_control_widget.hide()
            if hasattr(self, "capture_action_bar"):
                self.capture_action_bar.hide()
            if hasattr(self, "card_session_settings"):
                self.card_session_settings.hide()
            if hasattr(self, "card_options"):
                self.card_options.hide()
            if hasattr(self, "card_shots"):
                self.card_shots.hide()
            if hasattr(self, "card_cd"):
                self.card_cd.hide()
            if hasattr(self, "card_frames"):
                self.card_frames.hide()
            if hasattr(self, "card_filters"):
                self.card_filters.hide()
            if hasattr(self, "btn_start"):
                self.btn_start.hide()
            if hasattr(self, "chk_preview"):
                self.chk_preview.hide()
            if hasattr(self, "chk_beauty"):
                self.chk_beauty.hide()
            if hasattr(self, "chk_autoprint"):
                self.chk_autoprint.hide()
            if hasattr(self, "btn_fullscreen"):
                self.btn_fullscreen.hide()
            if hasattr(self, "live_top_bar"):
                self.lbl_active_event_pill.hide()
                self.btn_switch_event.hide()
                self.btn_live_fullscreen.hide()
                self.lbl_live_badge.hide()
                self.lbl_live_res.hide()
            self.capture_layout.setContentsMargins(0, 0, 0, 0)
            self.capture_layout.setSpacing(0)
            self.top_row_layout.setContentsMargins(0, 0, 0, 0)
            self.top_row_layout.setSpacing(0)
            self.card_live.setStyleSheet(f"QFrame#card_live {{ background-color: {COLOR_LIVEVIEW}; border: none; border-radius: 0px; }}")
            l_live = self.card_live.layout()
            if l_live:
                l_live.setContentsMargins(0, 0, 0, 0)
                l_live.setSpacing(0)
        else:
            if hasattr(self, "right_control_widget"):
                self.right_control_widget.show()
            if hasattr(self, "capture_action_bar"):
                self.capture_action_bar.show()
            if hasattr(self, "card_session_settings"):
                self.card_session_settings.show()
            if hasattr(self, "card_options"):
                self.card_options.show()
            if hasattr(self, "card_shots"):
                self.card_shots.show()
            if hasattr(self, "card_cd"):
                self.card_cd.show()
            if hasattr(self, "card_frames"):
                self.card_frames.show()
            if hasattr(self, "card_filters"):
                self.card_filters.show()
            if getattr(self, "current_state", "IDLE") != "REVIEW":
                if hasattr(self, "btn_start"):
                    self.btn_start.show()
                    self.btn_start.setEnabled(True)
                if hasattr(self, "chk_preview"):
                    self.chk_preview.show()
                if hasattr(self, "chk_beauty"):
                    self.chk_beauty.show()
                if hasattr(self, "btn_fullscreen"):
                    self.btn_fullscreen.show()
            if hasattr(self, "live_top_bar"):
                self.lbl_active_event_pill.show()
                self.btn_switch_event.show()
                self.btn_live_fullscreen.show()
                self.lbl_live_badge.show()
                self.lbl_live_res.show()
            self.capture_layout.setContentsMargins(14, 10, 14, 12)
            self.capture_layout.setSpacing(10)
            self.top_row_layout.setContentsMargins(0, 0, 0, 0)
            self.top_row_layout.setSpacing(12)
            self.card_live.setStyleSheet(f"""
                QFrame#card_live {{
                    background-color: {COLOR_LIVEVIEW};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 12px;
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            l_live = self.card_live.layout()
            if l_live:
                l_live.setContentsMargins(6, 4, 6, 6)
                l_live.setSpacing(4)
        self._reposition_viewport_overlays()

    def start_capture_flow(self):
        if self.current_state != "IDLE" or getattr(self, "_active_capture_tx", None) is not None:
            return

        if not self.camera_mgr.is_connected() and self.camera_mgr.current_backend_name != "simulator":
            QMessageBox.warning(self, "Máy Ảnh", "Chưa kết nối máy ảnh! Vui lòng cắm cáp USB máy ảnh và kiểm tra kết nối.")
            return

        # Tự động mở Live View toàn màn hình khi bắt đầu chụp (không toggle tắt nếu đang fullscreen sẵn)
        self.request_capture_fullscreen.emit(True)
        self.set_capture_immersive_mode(True)

        self.current_state = "COUNTDOWN"
        self.captured_originals.clear()
        self.captured_paths.clear()
        self.current_shot_index = 1
        self._beauty_settings_cache = None
        self._beauty_enabled_cache = None
        self._reuse_beauty_settings = False

        self.btn_start.setEnabled(False)
        self.btn_shots_minus.setEnabled(False)
        self.txt_shots_input.setEnabled(False)
        self.btn_shots_plus.setEnabled(False)
        self.btn_cd_3.setEnabled(False)
        self.btn_cd_5.setEnabled(False)
        self.btn_cd_10.setEnabled(False)
        self._start_single_shot_countdown()

    def _start_single_shot_countdown(self):
        self.countdown_remaining = self.countdown_duration
        self.lbl_countdown.setText(str(self.countdown_remaining))
        self.lbl_countdown.setStyleSheet(
            f"color: {COLOR_CHAMPAGNE}; font-size: 150px; font-weight: 900; "
            f"background: rgba(23,25,28,0.72); border: 4px solid {COLOR_CHAMPAGNE}; border-radius: 40px;"
        )

        self.lbl_status_badge.setStyleSheet(
            f"color: #FFFFFF; font-size: 26px; font-weight: 900; "
            f"background: rgba(23,25,28,0.85); border: 2px solid {COLOR_CHAMPAGNE}; "
            f"padding: 8px 36px; border-radius: 24px; letter-spacing: 1px;"
        )
        if getattr(self, "_retake_slot_index", None) is not None:
            self.lbl_status_badge.setText(f"📸 ĐANG CHỤP LẠI Ô SỐ {self._retake_slot_index + 1}")
        else:
            self.lbl_status_badge.setText(f"ẢNH {self.current_shot_index} / {self.total_shots_needed}")
        self._reposition_viewport_overlays()
        self.lbl_countdown.show()
        self.lbl_status_badge.show()

        # Tạo mới Countdown Transaction ID độc nhất cho lượt này
        cd_tx_id = f"cd_tx_{self.current_shot_index}_{int(time.time()*1000)}"
        self._active_countdown_tx_id = cd_tx_id

        if hasattr(self, "sound_controller") and self.sound_controller:
            self.sound_controller.start_countdown_transaction(cd_tx_id)

        # Đặt lại tracking mốc âm thanh
        self._voice_prompt_played = False
        self._countdown_audio_played = set()

        # Phát âm thanh tương ứng đồng bộ với số hiển thị trên UI tại mốc bắt đầu
        self._play_countdown_audio(self.countdown_remaining, tx_id=cd_tx_id)

        self.countdown_timer.start(1000)

    def _play_countdown_audio(self, number: int, tx_id: Optional[str] = None):
        """
        Phát âm thanh tương ứng đồng bộ động với số đếm ngược hiển thị trên UI (10, 5, 4, 3, 2, 1...).
        Mapping trực tiếp giá trị number -> file âm thanh tương ứng mà không hardcode.
        """
        if not hasattr(self, "sound_controller") or not self.sound_controller:
            return

        active_tx = tx_id or getattr(self, "_active_countdown_tx_id", None)
        self.sound_controller.play_countdown_step(number, tx_id=active_tx)

    def _on_countdown_tick(self):
        self.countdown_remaining -= 1
        if self.countdown_remaining > 0:
            self.lbl_countdown.setText(str(self.countdown_remaining))
            self._reposition_viewport_overlays()
            self._play_countdown_audio(self.countdown_remaining, tx_id=getattr(self, "_active_countdown_tx_id", None))
        else:
            # Hết thời gian đếm ngược: Dừng timer ngay lập tức và chuyển sang trạng thái chụp
            self.countdown_timer.stop()
            self.lbl_countdown.setText("📸")
            self._reposition_viewport_overlays()
            self._trigger_shot()

    def cancel_countdown(self):
        """Hủy tiến trình đếm ngược chụp ảnh hiện tại và dừng toàn bộ âm thanh ngay lập tức."""
        if hasattr(self, 'countdown_timer') and self.countdown_timer.isActive():
            self.countdown_timer.stop()
        if hasattr(self, 'sound_controller') and self.sound_controller:
            self.sound_controller.stop_all()
            if getattr(self, "_active_capture_tx_id", None):
                self.sound_controller.cancel_transaction(self._active_capture_tx_id)
            if getattr(self, "_active_countdown_tx_id", None):
                self.sound_controller.cancel_countdown_transaction(self._active_countdown_tx_id)
        self._active_capture_tx = None
        self._active_capture_tx_id = None
        self._active_countdown_tx_id = None
        self._voice_prompt_played = False
        self._countdown_audio_played = set()
        self.lbl_countdown.hide()
        self.lbl_status_badge.hide()
        self.current_state = "IDLE"
        self.set_capture_immersive_mode(False)
        self.request_capture_fullscreen.emit(False)
        self.btn_start.setEnabled(True)
        self.btn_start.show()

    def _prompt_smart_beauty(self, target_path: str, captured_img: Image.Image) -> Tuple[Image.Image, str]:
        """Hiển thị SmartBeautyDialog sau khi chụp và trả về (final_img, final_path)."""
        enable_smart_beauty = self.config_mgr.get("kiosk.enable_smart_beauty", True)
        if not enable_smart_beauty:
            return captured_img, target_path

        # Nếu đang chạy pytest và không chủ động yêu cầu test dialog tương tác
        if os.environ.get("PYTEST_CURRENT_TEST") and not getattr(self, "_force_show_beauty_in_tests", False):
            return captured_img, target_path

        try:
            from vietphotobooth.desktop.widgets.smart_beauty_panel import SmartBeautyDialog
            initial_s = self._beauty_settings_cache if self._reuse_beauty_settings else None
            initial_en = self._beauty_enabled_cache if self._reuse_beauty_settings else None
            beauty_dlg = SmartBeautyDialog(
                image_pil_or_path=target_path,
                shot_index=self.current_shot_index,
                total_shots=self.total_shots_needed,
                initial_settings=initial_s,
                initial_enabled_effects=initial_en,
                reuse_for_next=self._reuse_beauty_settings,
                developer_mode=bool(self.config_mgr.get("developer_mock_mode", False)),
                parent=self
            )
            dlg_res = beauty_dlg.exec()
            if dlg_res == QDialog.Accepted:
                processed_img, settings, reuse = beauty_dlg.get_result()
                enabled_fx = beauty_dlg.get_enabled_effects()
                self._reuse_beauty_settings = reuse
                if reuse:
                    self._beauty_settings_cache = settings
                    self._beauty_enabled_cache = enabled_fx
                else:
                    self._beauty_settings_cache = None
                    self._beauty_enabled_cache = None

                # Nếu có hiệu ứng làm đẹp đang bật và > 0
                has_active_fx = any(
                    v > 0 and enabled_fx.get(k, True)
                    for k, v in settings.items()
                )
                if has_active_fx:
                    beauty_path = os.path.join(self.session_dir, f"photo_{self.current_shot_index}_beauty.jpg")
                    try:
                        processed_img.save(beauty_path, "JPEG", quality=95)
                        return processed_img, beauty_path
                    except Exception as e:
                        logger.error(f"Lỗi lưu file ảnh làm đẹp: {e}")
            else:
                logger.info("Người dùng hủy hoặc đóng Smart Beauty Panel; sử dụng ảnh gốc.")
        except Exception as ex:
            logger.error(f"Lỗi khi hiển thị SmartBeautyDialog: {ex}")

        return captured_img, target_path

    def _get_af_target_point(self) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]], str]:
        """
        Xác định mục tiêu lấy nét tự động trước khi chụp từ kết quả nhận diện khuôn mặt/mắt:
        - Ưu tiên mắt mục tiêu (target_eye) từ FaceEyeAFController dùng chung.
        - Fallback khuôn mặt (target_face / face center) từ FaceEyeAFController dùng chung.
        - Fallback select_af_target nếu controller chưa có mục tiêu nhưng có faces gần đây.
        - Trả về (target_point, frame_size, target_type).
        """
        # 1. Trích xuất mục tiêu từ FaceEyeAFController dùng chung
        if hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller:
            ctrl_eye = self._face_eye_af_controller.target_eye
            ctrl_face = self._face_eye_af_controller.target_face
            ctrl_label = getattr(self._face_eye_af_controller, "_target_eye_label", "none")
            ctrl_frame_shape = getattr(self._face_eye_af_controller, "_last_frame_shape", None) or getattr(self, "_latest_frame_shape", None)

            if ctrl_eye is not None and ctrl_label in ("right", "left"):
                return ctrl_eye, ctrl_frame_shape, "eye"

            if ctrl_face is not None:
                center_pt = (ctrl_face.x + ctrl_face.w / 2.0, ctrl_face.y + ctrl_face.h * 0.4)
                return center_pt, ctrl_frame_shape, "face"

        # 2. Fallback sang select_af_target từ danh sách faces mới nhất
        faces = getattr(self, "_latest_detected_faces", [])
        frame_shape = getattr(self, "_latest_frame_shape", None)
        now = time.time()
        if faces and (now - getattr(self, "_latest_detection_time", 0.0)) <= 2.5:
            from vietphotobooth.camera.face_eye_af_controller import select_af_target
            target_point, target_type, selected_face = select_af_target(
                faces,
                frame_shape=frame_shape
            )
            return target_point, frame_shape, target_type

        return None, getattr(self, "_latest_frame_shape", None), "none"

    def _trigger_shot(self):
        """
        Kích hoạt quy trình chụp một bức ảnh:
        1. Kiểm tra chống chạy trùng lặp transaction (Mutual Exclusion).
        2. Hiển thị hiệu ứng chớp sáng flash studio.
        3. Khởi tạo capture transaction riêng biệt với token tx_id duy nhất.
        4. Thực hiện lấy nét tự động trước khi chụp (Face/Eye AF pre-capture) qua backend máy ảnh.
        5. Chờ AF hoàn tất hoặc timeout/fallback rồi mới kích hoạt chụp ảnh thực tế.
        """
        # Chống nhấn nút chụp liên tục hoặc gọi đồng thời khi một transaction đang chạy
        if getattr(self, "_active_capture_tx", None) is not None or getattr(self, "_is_af_in_flight", False):
            logger.warning("[Kiosk AF] Bỏ qua _trigger_shot vì đang có transaction chụp ảnh đang xử lý.")
            return

        self.current_state = "CAPTURING"
        self.lbl_viewport.trigger_flash(120)

        self._capture_transaction_id = getattr(self, "_capture_transaction_id", 0) + 1
        tx_id = f"tx_shot_{self.current_shot_index}_{self._capture_transaction_id}_{int(time.time()*1000)}"
        self._active_capture_tx = tx_id
        self._active_capture_tx_id = tx_id
        if hasattr(self, "sound_controller") and self.sound_controller:
            self.sound_controller.start_transaction(tx_id)

        if not self.current_session_id:
            active_event = self.event_mgr.get_active_event_name()
            dirs = self.event_mgr.get_event_dirs(active_event)
            sess_name = time.strftime("Session_%Y%m%d_%H%M%S")
            self.current_session_id = sess_name
            self.session_dir = os.path.join(dirs["originals"], sess_name)
            os.makedirs(self.session_dir, exist_ok=True)

        target_path = os.path.join(self.session_dir, f"photo_{self.current_shot_index}.jpg")

        if getattr(self, "_enable_af_on_simulator", False):
            enable_af = True
        elif hasattr(self.camera_mgr, "is_face_eye_af_enabled"):
            enable_af = self.camera_mgr.is_face_eye_af_enabled()
        else:
            enable_af = self.config_mgr.get("camera.face_eye_af_enabled", self.config_mgr.get("kiosk.enable_face_eye_af", True))

        is_conn = self.camera_mgr.is_connected()
        backend_name = self.camera_mgr.current_backend_name
        has_af_cap = hasattr(self.camera_mgr._backend, "autofocus")

        # Điều kiện thực hiện pre-capture AF:
        # Máy ảnh kết nối, backend hỗ trợ AF, và không phải simulator (trừ khi có cờ cho phép trên simulator trong test)
        can_af = enable_af and is_conn and has_af_cap and (
            backend_name != "simulator" or getattr(self, "_enable_af_on_simulator", False)
        )

        if can_af:
            if hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller:
                self._face_eye_af_controller.pause_auto_trigger()

            target_point, frame_size, target_type = self._get_af_target_point()
            logger.info(
                f"[Kiosk AF] Bắt đầu lấy nét trước khi chụp ảnh {self.current_shot_index}/{self.total_shots_needed} "
                f"(tx_id={tx_id}): target_type={target_type}, target_point={target_point}, frame_size={frame_size}"
            )
            self._is_af_in_flight = True
            self._pending_target_path = target_path

            # Watchdog an toàn: Sau tối đa 2.2 giây, nếu AF chưa xong thì tự động fallback chụp ngay
            self._af_watchdog_timer.start(2200)

            def _on_af_done(success: bool, msg: str):
                if not shiboken6.isValid(self):
                    return
                def _apply():
                    if not shiboken6.isValid(self):
                        return
                    if hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller:
                        self._face_eye_af_controller.resume_auto_trigger()
                    # Yêu cầu 1, 2, 3: Đảm bảo chỉ transaction hiện tại được quyền thực hiện và bỏ qua callback trễ/trùng lặp
                    if getattr(self, "_active_capture_tx", None) != tx_id:
                        logger.debug(f"[Kiosk AF] Bỏ qua callback AF muộn/không hợp lệ (tx={tx_id} vs active={getattr(self, '_active_capture_tx', None)}).")
                        return
                    # Hủy active transaction ngay lập tức trước khi chụp để ngăn mọi callback/timeout trùng lặp
                    self._active_capture_tx = None
                    self._af_watchdog_timer.stop()
                    self._is_af_in_flight = False
                    logger.info(f"[Kiosk AF] Kết quả AF (tx_id={tx_id}): success={success}, msg='{msg}' -> Kích hoạt chụp ảnh.")
                    self._execute_photo_capture(target_path)

                QTimer.singleShot(0, self, _apply)

            try:
                self.camera_mgr.trigger_autofocus(
                    callback=_on_af_done,
                    target_point=target_point,
                    frame_size=frame_size
                )
            except Exception as ex:
                logger.warning(f"[Kiosk AF] Ngoại lệ khi gọi trigger_autofocus (tx_id={tx_id}): {ex} -> Fallback chụp ngay.")
                if hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller:
                    self._face_eye_af_controller.resume_auto_trigger()
                if getattr(self, "_active_capture_tx", None) == tx_id:
                    self._active_capture_tx = None
                    self._af_watchdog_timer.stop()
                    self._is_af_in_flight = False
                    self._execute_photo_capture(target_path, tx_id=tx_id)
        else:
            self._active_capture_tx = None
            self._is_af_in_flight = False
            self._execute_photo_capture(target_path, tx_id=tx_id)

    def _on_af_timeout(self):
        """Fallback an toàn khi autofocus quá thời gian chờ (2.2s). Chụp ngay mà không làm gián đoạn phiên."""
        tx_id = getattr(self, "_active_capture_tx", None)
        if tx_id is None:
            return

        if hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller:
            self._face_eye_af_controller.resume_auto_trigger()

        logger.warning(f"[Kiosk AF] Hết thời gian chờ autofocus (Timeout 2.2s, tx_id={tx_id}) -> Fallback chụp ngay.")
        # Vô hiệu hóa active transaction ngay lập tức để nếu callback đến sau thì sẽ bị bỏ qua hoàn toàn
        self._active_capture_tx = None
        self._is_af_in_flight = False

        # Hủy lệnh autofocus đang chạy ngầm trên phần cứng để giải phóng mô-tơ và cờ in-progress
        try:
            self.camera_mgr.cancel_autofocus()
        except Exception as ex:
            logger.debug(f"[Kiosk AF] Bỏ qua lỗi cancel_autofocus khi timeout: {ex}")

        target_path = getattr(self, "_pending_target_path", None)
        if not target_path and self.session_dir:
            target_path = os.path.join(self.session_dir, f"photo_{self.current_shot_index}.jpg")
        if target_path:
            self._execute_photo_capture(target_path)

    def _execute_photo_capture(self, target_path: str, *args, **kwargs):
        tx_id = kwargs.get("tx_id") or getattr(self, "_active_capture_tx_id", None) or f"tx_shot_{self.current_shot_index}_{int(time.time()*1000)}"
        self._active_capture_tx_id = tx_id

        # Đăng ký transaction với SoundController
        if hasattr(self, "sound_controller") and self.sound_controller:
            self.sound_controller.start_transaction(tx_id)

        # Callback on_capture_start: Kích hoạt âm thanh màn trập ngay khi camera chấp nhận lệnh chụp (CAP_START)
        def _on_capture_start():
            if not shiboken6.isValid(self):
                return
            # Chỉ phát âm thanh nếu transaction vẫn còn hiệu lực và chưa bị hủy (cancel/disconnect)
            if getattr(self, "_active_capture_tx_id", None) != tx_id:
                logger.warning(
                    f"[Capture Audio] Bỏ qua âm thanh màn trập vì transaction '{tx_id}' không còn active "
                    f"(active: '{getattr(self, '_active_capture_tx_id', None)}')."
                )
                return
            if hasattr(self, "sound_controller") and self.sound_controller:
                self.sound_controller.play_shutter_for_transaction(tx_id)

        success, captured_img = self.camera_mgr.capture_photo(
            target_path,
            on_capture_start=_on_capture_start
        )
        valid_file = False
        if success and captured_img:
            if not os.path.exists(target_path):
                try:
                    captured_img.save(target_path, "JPEG", quality=95)
                except Exception as e:
                    logger.warning(f"Lỗi lưu file ảnh chụp: {e}")

            if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                try:
                    # Xác thực tính toàn vẹn và giải mã file ảnh trên đĩa
                    with Image.open(target_path) as im:
                        im.verify()
                    valid_file = True
                except Exception as e:
                    logger.error(f"Tệp ảnh chụp trên đĩa không hợp lệ: {e}")
                    valid_file = False

        if valid_file:
            # Ẩn nhãn countdown sau khi chụp xong thành công
            if hasattr(self, "lbl_countdown"):
                self.lbl_countdown.hide()
            # Giải phóng active transaction sau khi chụp xong thành công
            self._active_capture_tx = None
            self._active_capture_tx_id = None

            # 1. Bảo tồn ảnh gốc nguyên bản trên đĩa
            if getattr(self, "session_dir", None):
                orig_backup_path = os.path.join(self.session_dir, f"photo_{self.current_shot_index}_original.jpg")
                if not os.path.exists(orig_backup_path):
                    try:
                        import shutil
                        shutil.copy2(target_path, orig_backup_path)
                    except Exception as e:
                        logger.warning(f"Lỗi sao lưu ảnh gốc: {e}")

            # 2. Xử lý Smart Beauty Panel sau mỗi ảnh
            final_img, final_path = self._prompt_smart_beauty(target_path, captured_img)

            if getattr(self, "_retake_slot_index", None) is not None:
                r_idx = self._retake_slot_index
                if 0 <= r_idx < len(self.captured_originals):
                    self.captured_originals[r_idx] = final_img
                    self.captured_paths[r_idx] = final_path
                else:
                    self.captured_originals.append(final_img)
                    self.captured_paths.append(final_path)
                self._retake_slot_index = None
                logger.info(f"Đã cập nhật riêng ô #{r_idx + 1}, bảo toàn 100% các ô còn lại.")
                self.lbl_status_badge.setText(f"✨ Đã cập nhật ảnh ô #{r_idx + 1}!")
                QTimer.singleShot(600, self._enter_review_state)
                return

            self.captured_originals.append(final_img)
            self.captured_paths.append(final_path)
            logger.info(f"Đã xác thực và ghi nhận ảnh {self.current_shot_index}/{self.total_shots_needed} trên đĩa: {final_path}")
        else:
            logger.error("Không thể ghi nhận ảnh chụp hợp lệ từ thiết bị máy ảnh!")
            self._abort_capture_due_to_disconnect(
                "Mất kết nối máy ảnh hoặc thiết bị không trả về dữ liệu ảnh hợp lệ!\n\n"
                "Vui lòng kiểm tra lại cáp kết nối USB, nguồn pin hoặc gạt lại cần Live View trên thân máy ảnh."
            )
            return

        if self.current_shot_index < self.total_shots_needed:
            self.current_shot_index += 1
            self.current_state = "COUNTDOWN"
            QTimer.singleShot(1400, self._start_single_shot_countdown)
        else:
            self.lbl_status_badge.setText("✨ Đang tạo khung ảnh thành phẩm...")
            QTimer.singleShot(600, self._enter_review_state)

    def _abort_capture_due_to_disconnect(self, err_msg: str):
        """Hủy tiến trình chụp ảnh an toàn khi máy ảnh mất kết nối hoặc rút cáp USB."""
        self.countdown_timer.stop()
        if hasattr(self, "sound_controller") and self.sound_controller:
            self.sound_controller.stop_all()
        self._active_capture_tx = None
        self._active_capture_tx_id = None
        self._voice_prompt_played = False
        if hasattr(self, "_af_watchdog_timer") and self._af_watchdog_timer.isActive():
            self._af_watchdog_timer.stop()
        self._is_af_in_flight = False
        try:
            self.camera_mgr.cancel_autofocus()
        except Exception:
            pass

        if getattr(self, "_retake_slot_index", None) is not None:
            self._retake_slot_index = None
            logger.warning("Hủy chụp lại ô do lỗi máy ảnh, khôi phục lại màn hình review.")
            self._enter_review_state()
            QMessageBox.warning(self, "Lỗi Kết Nối Máy Ảnh", err_msg)
            return
        self.current_state = "IDLE"
        self.set_capture_immersive_mode(False)
        self.request_capture_fullscreen.emit(False)
        self.lbl_countdown.hide()
        self.lbl_status_badge.hide()
        self.btn_start.setEnabled(True)
        self.btn_start.show()
        self.btn_shots_minus.setEnabled(True)
        self.txt_shots_input.setEnabled(True)
        self.btn_shots_plus.setEnabled(True)
        self.btn_cd_3.setEnabled(True)
        self.btn_cd_5.setEnabled(True)
        self.btn_cd_10.setEnabled(True)
        self.captured_originals.clear()
        self.captured_paths.clear()
        self.start_live_view()
        QMessageBox.warning(self, "Lỗi Kết Nối Máy Ảnh", err_msg)

    # -------------------------------------------------------------
    # MÀN HÌNH XEM KẾT QUẢ, IN & CHIA SẺ QR (REVIEW STATE)
    # -------------------------------------------------------------
    def _enter_review_state(self):
        self.current_state = "REVIEW"
        self.stop_live_view()
        self.lbl_countdown.hide()
        self.lbl_status_badge.hide()
        self.panel_disconnected.hide()

        # Ẩn nút Chụp ban đầu, hiện các nút Xem kết quả
        self.btn_start.hide()
        self.chk_preview.hide()
        self.chk_beauty.hide()
        self.chk_autoprint.hide()
        self.btn_fullscreen.hide()

        self.btn_retake.show()
        self.btn_save.show()
        self.btn_qr.show()
        self.btn_print.show()
        self.btn_finish.show()

        active_event = getattr(self, "current_event", None) or self.event_mgr.get_active_event_name()
        token_info = self.token_mgr.create_token(active_event, self.current_session_id)
        self.current_token = token_info.token

        # TỰ ĐỘNG CHUYỂN NỘI DUNG SANG TRANG HOÀN THIỆN ẢNH NỘI BỘ (KHÔNG MỞ CỬA SỔ RIÊNG)
        self.set_capture_immersive_mode(False)
        self.request_capture_fullscreen.emit(False)
        enable_guest_review = self.config_mgr.get("kiosk.enable_guest_review", True)
        if enable_guest_review and self.captured_originals:
            self.review_widget.load_session(
                photos=self.captured_originals,
                frame_mgr=self.frame_mgr,
                initial_frame_id=self.selected_frame_id,
                event_name=active_event,
                session_id=self.current_session_id or "Session_unknown",
                print_mgr=self.print_mgr
            )
            self.kiosk_stack.setCurrentIndex(1)
            logger.info("Đã tự động chuyển sang trang Hoàn Thiện Ảnh & Chọn Frame nội bộ.")
            return

        self._render_and_display_composite()

    def _display_final_pixmap(self):
        """Hiển thị ảnh thành phẩm 300 DPI sắc nét lên Viewport."""
        if not self.current_composite:
            return
        rgb = self.current_composite.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.lbl_viewport.setPixmap(pixmap)

    def _render_and_display_composite(self):
        if not self.captured_originals:
            return

        # Hiển thị thông báo trạng thái không làm đơ giao diện
        self.lbl_status_badge.setText("✨ Đang tạo khung ảnh 300 DPI...")
        self.lbl_status_badge.show()
        self.btn_print.setEnabled(False)

        # Xem trước tức thời ảnh đầu tiên trong khi worker xử lý (<15ms)
        try:
            draft_img = self.captured_originals[0]
            rgb = draft_img.convert("RGB")
            w, h = rgb.size
            qimg = QImage(rgb.tobytes("raw", "RGB"), w, h, 3 * w, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            self.lbl_viewport.setPixmap(pixmap)
        except Exception:
            pass

        # Khởi động luồng xử lý ảnh 300 DPI chạy ngầm (Non-blocking GUI)
        self._composite_worker = CompositeWorker(
            filter_engine=self.filter_engine,
            frame_mgr=self.frame_mgr,
            event_mgr=self.event_mgr,
            photos=self.captured_originals,
            filter_id=self.selected_filter_id,
            frame_id=self.selected_frame_id,
            session_id=self.current_session_id or "Session_unknown",
            parent=self
        )
        self._composite_worker.composite_ready.connect(self._on_composite_ready)
        self._composite_worker.composite_failed.connect(self._on_composite_failed)
        self._composite_worker.start()

    def _on_composite_ready(self, composite: Image.Image, final_path: str):
        self.current_composite = composite
        self.current_final_path = final_path
        self.lbl_status_badge.hide()
        self.btn_print.setEnabled(True)

        # Cập nhật số ảnh sự kiện tức thời
        self._increment_event_photo_count()

        # Đưa vào hàng đợi đồng bộ Google Drive nền nếu bật Auto Sync
        if self.sync_mgr and self.config_mgr.get("cloud.auto_sync", True):
            ev_name = self.event_mgr.get_active_event_name()
            self.sync_mgr.enqueue(final_path, ev_name, is_final=True)
            logger.info(f"Tự động đưa ảnh {final_path} vào hàng đợi đồng bộ Google Drive.")

        # Hiển thị ảnh thành phẩm 300 DPI sắc nét lên Viewport
        self._display_final_pixmap()

        # Thông báo nếu số lượng ảnh đã chụp khác số lượng ô trong khung
        template = self.frame_mgr.get_frame(self.selected_frame_id)
        if not template:
            frames = self.frame_mgr.list_frames()
            template = frames[0] if frames else None
        if template and template.slots:
            slots_count = len(template.slots)
            captured_count = len(self.captured_originals)
            if captured_count != slots_count:
                if captured_count < slots_count:
                    msg = f"ℹ️ Đã chụp {captured_count} ảnh, khung có {slots_count} ô — ảnh được điền lặp lại vào ô còn thiếu (đã lưu an toàn toàn bộ {captured_count} ảnh gốc)."
                else:
                    msg = f"ℹ️ Đã chụp {captured_count} ảnh, khung có {slots_count} ô — {slots_count} ảnh đầu được đưa vào khung (đã lưu an toàn toàn bộ {captured_count} ảnh gốc)."
                self.lbl_status_badge.setText(msg)
                self.lbl_status_badge.setStyleSheet(
                    "color: #F7E7CE; font-size: 13px; font-weight: 600; "
                    "background: rgba(13,21,39,0.95); border: 1.5px solid #D4AF37; "
                    "padding: 8px 18px; border-radius: 14px;"
                )
                lbl_w = max(400, self.lbl_viewport.width())
                lbl_h = max(300, self.lbl_viewport.height())
                badge_w = min(max(380, self.lbl_status_badge.sizeHint().width() + 32), max(380, lbl_w - 40))
                self.lbl_status_badge.setGeometry((lbl_w - badge_w) // 2, lbl_h - 75, badge_w, 48)
                self.lbl_status_badge.show()
                QTimer.singleShot(7000, self.lbl_status_badge.hide)

        # Nếu chọn tự động in sau khi chụp
        if self.chk_autoprint.isChecked():
            self._print_composite(direct=True)

    def _on_composite_failed(self, error_msg: str):
        self.lbl_status_badge.hide()
        self.btn_print.setEnabled(True)
        logger.error(f"Lỗi dựng ảnh thành phẩm: {error_msg}")
        QMessageBox.warning(self, "Lỗi Ghép Ảnh", f"Không thể hoàn tất ghép ảnh: {error_msg}")

    def _save_photo_dialog(self):
        if not self.current_composite:
            return
        from PySide6.QtWidgets import QFileDialog
        save_path, _ = QFileDialog.getSaveFileName(self, "Lưu Ảnh Thành Phẩm", f"1998_Studio_{self.current_session_id}.jpg", "Ảnh JPEG (*.jpg);;Ảnh PNG (*.png)")
        if save_path:
            self.current_composite.save(save_path, quality=98)
            QMessageBox.information(self, "Thành Công", f"Đã lưu ảnh thành công vào:\n{save_path}")

    def _print_composite(self, direct: bool = False):
        if not self.current_composite:
            return

        if direct:
            num_copies = 1
        else:
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

            if copies_dialog.exec() != QDialog.Accepted:
                return
            num_copies = spin_copies.value()

        event_name = self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(event_name)
        final_path = os.path.join(dirs["final"], f"{self.current_session_id}_final.jpg")

        self.btn_print.setEnabled(False)
        self.btn_print.setText("⏳ Đang In...")

        self._print_worker = PrintWorker(self.print_mgr, final_path, copies=num_copies, parent=self)
        self._print_worker.print_finished.connect(self._on_print_finished)
        self._print_worker.start()

    def _on_print_finished(self, success: bool, msg: str):
        self.btn_print.setEnabled(True)
        self.btn_print.setText("🖨️ IN ẢNH NGAY")
        if success:
            QMessageBox.information(self, "Đang In", msg)
        else:
            QMessageBox.warning(self, "Máy In", msg)

    def _show_qr_dialog(self):
        if not self.current_token:
            return

        lan_url = self.token_mgr.get_sharing_url(self.current_token)

        # Kiểm tra link Google Drive nếu có
        gdrive_url = None
        if self.sync_mgr and self.current_final_path:
            info = self.sync_mgr.get_file_info(self.current_final_path)
            if info and info.get("status") == SyncStatus.SYNCED:
                gdrive_url = info.get("web_link")
            elif self.sync_mgr.auth.simulation_mode:
                gdrive_url = f"https://drive.google.com/file/d/sim_{abs(hash(self.current_final_path))}/view?usp=sharing"

        import qrcode
        dlg = QDialog(self)
        dlg.setWindowTitle("Quét Mã QR Tải Ảnh Về Điện Thoại")
        dlg.setFixedSize(460, 560)
        l = QVBoxLayout(dlg)
        l.setSpacing(12)

        title = QLabel("1998 STUDIO — TẢI ẢNH VỀ ĐIỆN THOẠI")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #D4AF37;")
        l.addWidget(title)

        tabs_qr = QTabWidget()

        # Tab 1: Google Drive (Online 4G / Internet)
        tab_cloud = QWidget()
        l_cloud = QVBoxLayout(tab_cloud)
        l_cloud.setSpacing(10)

        if gdrive_url:
            qr_cloud_img = qrcode.make(gdrive_url)
            lbl_qr_c = QLabel()
            lbl_qr_c.setAlignment(Qt.AlignCenter)
            rgb = qr_cloud_img.convert("RGB")
            w, h = rgb.size
            data = rgb.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
            lbl_qr_c.setPixmap(QPixmap.fromImage(qimg).scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            l_cloud.addWidget(lbl_qr_c)

            lbl_c_desc = QLabel("⚡ Quét để xem và tải ảnh gốc trực tiếp qua mạng 4G/Internet.")
            lbl_c_desc.setAlignment(Qt.AlignCenter)
            lbl_c_desc.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
            l_cloud.addWidget(lbl_c_desc)

            lbl_c_url = QLabel(f"<a href='{gdrive_url}' style='color:#38BDF8;'>Mở liên kết Google Drive</a>")
            lbl_c_url.setOpenExternalLinks(True)
            lbl_c_url.setAlignment(Qt.AlignCenter)
            l_cloud.addWidget(lbl_c_url)
        else:
            lbl_wait = QLabel("⏳ Ảnh đang được tải lên Google Drive trong nền...\nKhách có thể chuyển sang tab 'Mạng LAN WiFi' để tải ngay.")
            lbl_wait.setAlignment(Qt.AlignCenter)
            lbl_wait.setStyleSheet("color: #F59E0B; font-size: 13px; line-height: 1.5;")
            l_cloud.addWidget(lbl_wait)

            if self.sync_mgr and self.sync_mgr.is_ready() and self.current_final_path:
                btn_push_sync = QPushButton("☁️ Đồng Bộ Ngay Lập Tức")
                btn_push_sync.setObjectName("btn_champagne")
                ev_name = self.event_mgr.get_active_event_name()
                btn_push_sync.clicked.connect(lambda: self.sync_mgr.enqueue(self.current_final_path, ev_name))
                l_cloud.addWidget(btn_push_sync)

        tabs_qr.addTab(tab_cloud, "☁️ Google Drive (Online 4G)")

        # Tab 2: Mạng LAN WiFi
        tab_lan = QWidget()
        l_lan = QVBoxLayout(tab_lan)
        l_lan.setSpacing(10)

        qr_img = self.token_mgr.generate_qr_code(self.current_token)
        lbl_qr_l = QLabel()
        lbl_qr_l.setAlignment(Qt.AlignCenter)
        rgb_l = qr_img.convert("RGB")
        w_l, h_l = rgb_l.size
        data_l = rgb_l.tobytes("raw", "RGB")
        qimg_l = QImage(data_l, w_l, h_l, 3 * w_l, QImage.Format_RGB888)
        lbl_qr_l.setPixmap(QPixmap.fromImage(qimg_l).scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        l_lan.addWidget(lbl_qr_l)

        lbl_l_desc = QLabel("Khách kết nối cùng mạng WiFi Photobooth để tải trực tiếp từ máy trạm.")
        lbl_l_desc.setAlignment(Qt.AlignCenter)
        lbl_l_desc.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        l_lan.addWidget(lbl_l_desc)

        lbl_url = QLabel(f"<b>{lan_url}</b>")
        lbl_url.setAlignment(Qt.AlignCenter)
        lbl_url.setStyleSheet("color: #38BDF8; font-size: 11px;")
        l_lan.addWidget(lbl_url)

        tabs_qr.addTab(tab_lan, "📱 Mạng LAN (WiFi Nội Bộ)")

        # Nếu chưa có Google Drive link thì ưu tiên mở tab LAN
        if not gdrive_url:
            tabs_qr.setCurrentIndex(1)

        l.addWidget(tabs_qr)

        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("btn_secondary")
        btn_close.clicked.connect(dlg.accept)
        l.addWidget(btn_close)

        dlg.exec()

    def recover_session(self, session_id: str, event_name: Optional[str] = None) -> bool:
        """
        Khôi phục phiên chụp chưa hoàn tất hoặc cần ghép lại ảnh từ các tệp gốc trên đĩa.
        Bảo toàn 100% ảnh gốc đã chụp, ngăn ngừa mất ảnh khi xảy ra sự cố nguồn điện hoặc lỗi ứng dụng.
        """
        active_event = event_name or getattr(self, "current_event", None) or self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(active_event)
        sess_dir = os.path.join(dirs["originals"], session_id)

        if not os.path.exists(sess_dir):
            logger.warning(f"[Session Recovery] Thư mục phiên không tồn tại: {sess_dir}")
            return False

        photo_files = []
        for f in sorted(os.listdir(sess_dir)):
            if f.lower().startswith("photo_") and f.lower().endswith((".jpg", ".jpeg", ".png")):
                if "_original" in f or "_beauty" in f:
                    continue
                photo_files.append(os.path.join(sess_dir, f))

        if not photo_files:
            logger.warning(f"[Session Recovery] Không tìm thấy ảnh hợp lệ trong {sess_dir}")
            return False

        loaded_imgs = []
        loaded_paths = []
        for p in photo_files:
            try:
                im = Image.open(p)
                im.load()
                loaded_imgs.append(im.copy())
                loaded_paths.append(p)
                im.close()
            except Exception as e:
                logger.error(f"[Session Recovery] Không thể đọc ảnh {p}: {e}")

        if not loaded_imgs:
            return False

        self.current_session_id = session_id
        self.session_dir = sess_dir
        self.captured_originals = loaded_imgs
        self.captured_paths = loaded_paths
        logger.info(f"[Session Recovery] Đã khôi phục thành công {len(loaded_imgs)} ảnh của phiên {session_id}.")
        self._enter_review_state()
        return True

    def _retake_session(self):
        confirm = QMessageBox.question(self, "Chụp Lại", "Bạn có chắc muốn bỏ lượt chụp này và chụp lại từ đầu?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self._reset_to_idle()

    def _finish_session(self):
        self.session_finished.emit(self.current_session_id or "")
        self._reset_to_idle()

    def _reset_to_idle(self):
        self.set_capture_immersive_mode(False)
        self.current_state = "IDLE"
        self.current_session_id = None
        self.current_token = None
        self.current_final_path = None
        self.captured_originals.clear()
        self.captured_paths.clear()

        # Hiện lại thanh điều khiển chụp ban đầu
        self.btn_start.show()
        self.btn_start.setEnabled(True)
        self.chk_preview.show()
        self.chk_beauty.show()
        self.btn_fullscreen.show()

        self.btn_shots_minus.setEnabled(True)
        self.txt_shots_input.setEnabled(True)
        self.btn_shots_plus.setEnabled(True)
        self.btn_cd_3.setEnabled(True)
        self.btn_cd_5.setEnabled(True)
        self.btn_cd_10.setEnabled(True)

        self.btn_retake.hide()
        self.btn_save.hide()
        self.btn_qr.hide()
        self.btn_print.hide()
        self.btn_finish.hide()

        self.start_live_view()
        if hasattr(self, "kiosk_stack"):
            self.kiosk_stack.setCurrentIndex(0)

    def _on_review_retake(self):
        """Khách chọn Chụp Lại: quay về màn hình chụp và bắt đầu lượt mới."""
        logger.info("Khách chọn Chụp Lại: quay về màn hình chụp.")
        self._reset_to_idle()

    def _on_review_retake_slot(self, slot_idx: int):
        """Khách chọn 'Chụp lại ô này' cho ô số slot_idx (0-indexed)."""
        logger.info(f"Khách yêu cầu chụp lại riêng ô số {slot_idx + 1}.")
        self.retake_single_slot(slot_idx)

    def retake_single_slot(self, slot_idx: int):
        """Khởi động chụp lại riêng ô slot_idx (bảo toàn 100% các ô khác)."""
        if not self.camera_mgr.is_connected() and self.camera_mgr.current_backend_name != "simulator":
            QMessageBox.warning(self, "Máy Ảnh", "Chưa kết nối máy ảnh! Vui lòng kiểm tra lại cáp kết nối.")
            return

        if not (0 <= slot_idx < len(self.captured_originals)):
            logger.warning(f"Chỉ số slot {slot_idx} không hợp lệ để chụp lại.")
            return

        self._retake_slot_index = slot_idx
        self.current_state = "COUNTDOWN"
        self.current_shot_index = slot_idx + 1

        # Chuyển stack về Viewfinder toàn màn hình và bắt đầu đếm ngược cho riêng ô này
        self.kiosk_stack.setCurrentIndex(0)
        self.request_capture_fullscreen.emit(True)
        self.set_capture_immersive_mode(True)
        self.start_live_view()
        self._start_single_shot_countdown()

    def _on_review_finish(self):
        """Khách bấm Hoàn Tất: quay về màn hình chụp chuẩn bị cho lượt mới."""
        logger.info("Khách bấm Hoàn Tất: quay về màn hình chụp.")
        self._reset_to_idle()

    def _on_review_photo_saved(self, final_path: str):
        """Xử lý sau khi lưu ảnh thành phẩm từ trang hoàn thiện."""
        self.current_final_path = final_path
        self._increment_event_photo_count()
        if self.sync_mgr and self.config_mgr.get("cloud.auto_sync", True):
            active_event = self.event_mgr.get_active_event_name()
            self.sync_mgr.enqueue(final_path, active_event, is_final=True)
            logger.info(f"Đã đưa ảnh {final_path} vào hàng đợi đồng bộ Google Drive.")

    def _on_review_print_completed(self, final_path: str):
        """Xử lý sau khi in ảnh thành công từ trang hoàn thiện."""
        self.current_final_path = final_path
        self._increment_event_photo_count()
        if self.sync_mgr and self.config_mgr.get("cloud.auto_sync", True):
            active_event = self.event_mgr.get_active_event_name()
            self.sync_mgr.enqueue(final_path, active_event, is_final=True)
            logger.info(f"Đã đưa ảnh in {final_path} vào hàng đợi đồng bộ Google Drive.")

    def _on_review_frame_changed(self, frame_id: str):
        """Đồng bộ template được chọn từ trang hoàn thiện."""
        self.selected_frame_id = frame_id

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = event.size().width()
        h = event.size().height()

        # Điều chỉnh kích thước và bố cục phản hồi cho Kiosk
        if hasattr(self, "card_camera") and hasattr(self, "btn_start"):
            if w < 1200:
                self.card_camera.setMaximumWidth(190)
                self.card_camera.setMinimumWidth(150)
                self.btn_start.setFixedSize(270, 48)
            else:
                self.card_camera.setMaximumWidth(250)
                self.card_camera.setMinimumWidth(190)
                self.btn_start.setFixedSize(360, 48)

        # Căn chỉnh lại các overlay trong Viewport
        self._reposition_viewport_overlays()

        # Tự động cập nhật số lượng card khung theo độ phân giải màn hình
        if hasattr(self, "card_frames") and hasattr(self, "frames_container_layout"):
            current_ps = getattr(self, "_last_page_size", None)
            new_ps = self._get_carousel_page_size()
            if current_ps != new_ps:
                self._last_page_size = new_ps
                self._load_frame_options()

        # Nếu đang ở chế độ xem kết quả ảnh, cập nhật tỷ lệ hiển thị
        if self.current_state == "REVIEW" and self.current_composite:
            self._display_final_pixmap()

    def set_fullscreen_mode(self, is_fs: bool):
        """Cập nhật giao diện nút khi chuyển đổi chế độ toàn màn hình."""
        if hasattr(self, "btn_fullscreen"):
            if is_fs:
                self.btn_fullscreen.setText(" Thu Nhỏ (ESC)")
                self.btn_fullscreen.setIcon(get_svg_icon("minimize", 15, COLOR_CHAMPAGNE))
                self.btn_fullscreen.setIconSize(QSize(15, 15))
                self.btn_fullscreen.setToolTip("Thoát chế độ toàn màn hình (ESC hoặc F11)")
                self.btn_fullscreen.setStyleSheet(
                    f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1.5px solid {COLOR_CHAMPAGNE}; border-radius: 8px; color: {COLOR_CHAMPAGNE}; font-size: 12px; font-weight: 700; padding: 0 12px; }}"
                    f"QPushButton:hover {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; }}"
                )
            else:
                self.btn_fullscreen.setText(" Toàn màn hình")
                self.btn_fullscreen.setIcon(get_svg_icon("maximize", 15, COLOR_TEXT_PRIMARY))
                self.btn_fullscreen.setIconSize(QSize(15, 15))
                self.btn_fullscreen.setToolTip("Chế độ toàn màn hình Kiosk (F11)")
                self.btn_fullscreen.setStyleSheet(
                    f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 600; padding: 0 12px; }}"
                    f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; }}"
                )
        if hasattr(self, "btn_live_fullscreen"):
            self.btn_live_fullscreen.setIcon(
                get_svg_icon("minimize" if is_fs else "maximize", 15, COLOR_CHAMPAGNE if is_fs else COLOR_TEXT_PRIMARY)
            )
            self.btn_live_fullscreen.setToolTip("Thoát toàn màn hình (ESC hoặc F11)" if is_fs else "Toàn màn hình (F11)")
        if hasattr(self, "lbl_viewport"):
            self.lbl_viewport._recalculate_target_rect()
            self._reposition_viewport_overlays()

    def cleanup(self):
        """Dừng dứt điểm toàn bộ timers, workers và giải phóng tài nguyên của Kiosk."""
        if hasattr(self, 'countdown_timer') and self.countdown_timer.isActive():
            self.countdown_timer.stop()
        if hasattr(self, 'camera_poll_timer') and self.camera_poll_timer.isActive():
            self.camera_poll_timer.stop()
        if hasattr(self, '_af_watchdog_timer') and self._af_watchdog_timer.isActive():
            self._af_watchdog_timer.stop()
        if getattr(self, '_active_capture_tx', None) is not None or getattr(self, '_is_af_in_flight', False):
            self._active_capture_tx = None
            self._is_af_in_flight = False
            try:
                self.camera_mgr.cancel_autofocus()
            except Exception:
                pass
        try:
            self.stop_live_view()
        except Exception:
            pass
        if hasattr(self, 'live_view_worker') and self.live_view_worker.isRunning():
            self.live_view_worker.stop()
        if hasattr(self, '_face_service') and self._face_service:
            try:
                self._face_service.unregister_callback(self._on_faces_detected)
                self._face_service.stop()
            except Exception:
                pass
        if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller:
            self._face_eye_af_controller.resume_auto_trigger()
        if hasattr(self, 'sound_controller') and self.sound_controller:
            try:
                self.sound_controller.cleanup()
            except Exception:
                pass

    def close(self) -> bool:
        self.cleanup()
        return super().close()

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
