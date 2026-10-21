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
from typing import Optional, List, Dict
from PIL import Image
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox,
    QFrame, QSizePolicy, QDialog, QSpinBox, QMessageBox,
    QCheckBox, QTabWidget, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize, QThread
from PySide6.QtGui import QPixmap, QImage, QColor, QFont, QIntValidator

from vietphotobooth.camera.manager import CameraManager
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

logger = get_logger()

# Đường dẫn tài nguyên thương hiệu
LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "logo_1998_studio.png"))
EVENT_BANNER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "event_banner_sample.jpg"))


class TouchNumberPadDialog(QDialog):
    """Bàn phím số cảm ứng kích thước lớn cho Kiosk Photobooth."""
    def __init__(self, current_val: int = 3, min_val: int = 1, max_val: int = 16, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn Số Lượng Ảnh")
        self.setFixedSize(320, 420)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setStyleSheet(
            "QDialog { background-color: #070A12; border: 2px solid #D4AF37; border-radius: 14px; }"
            "QLabel { color: #F8FAFC; }"
        )
        self.min_val = min_val
        self.max_val = max_val
        self.value = current_val

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        lbl_title = QLabel("Nhập Số Ảnh Mỗi Lượt")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #D4AF37;")
        layout.addWidget(lbl_title)

        self.display = QLabel(str(self.value))
        self.display.setAlignment(Qt.AlignCenter)
        self.display.setFixedHeight(54)
        self.display.setStyleSheet(
            "background-color: #10192A; color: #FDF4DC; font-size: 28px; font-weight: 900; "
            "border: 1.5px solid #28395E; border-radius: 10px;"
        )
        layout.addWidget(self.display)

        grid = QGridLayout()
        grid.setSpacing(8)
        btn_style = (
            "QPushButton { background-color: #121C30; color: #F8FAFC; font-size: 20px; font-weight: bold; "
            "border: 1px solid #28395E; border-radius: 8px; min-height: 48px; }"
            "QPushButton:hover { background-color: #1C2D4A; border: 1px solid #D4AF37; color: #D4AF37; }"
            "QPushButton:pressed { background-color: #0B1322; }"
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
    Luồng chạy ngầm đọc khung hình Live View liên tục từ camera.
    Tách biệt hoàn toàn I/O camera và giải mã hình ảnh khỏi luồng GUI chính,
    đảm bảo giao diện 1998 TEAM mượt mà tuyệt đối ở 30+ FPS không bao giờ giật lag.
    """
    frame_ready = Signal(object)  # np.ndarray RGB

    def __init__(self, camera_mgr: CameraManager, parent=None):
        super().__init__(parent)
        self.camera_mgr = camera_mgr
        self._running = True
        self._paused = False

    def run(self):
        while self._running:
            if self._paused or not self.camera_mgr.is_connected() or self.camera_mgr.current_backend_name == "simulator":
                time.sleep(0.08)
                continue

            try:
                # Đọc trực tiếp RGB bỏ qua chu trình nén/giải nén JPEG (~8x nhanh hơn)
                frame_rgb = self.camera_mgr.get_liveview_rgb()
                if frame_rgb is not None:
                    self.frame_ready.emit(frame_rgb)
            except Exception as e:
                logger.debug(f"Liveview worker capture error: {e}")

            time.sleep(0.033)  # ~30 FPS

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._running = False
        self.wait(600)


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
        self.setFixedWidth(118)
        self.setFixedHeight(144)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Khung chứa hình thu nhỏ (thumbnail)
        self.thumb_container = QWidget()
        self.thumb_container.setFixedHeight(102)
        thumb_l = QVBoxLayout(self.thumb_container)
        thumb_l.setContentsMargins(0, 0, 0, 0)
        thumb_l.setAlignment(Qt.AlignCenter)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setPixmap(thumbnail_pixmap.scaled(104, 98, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        thumb_l.addWidget(self.lbl_thumb)

        # Dấu tích vàng nhận diện khung đang chọn
        self.lbl_badge = QLabel("✓", self.thumb_container)
        self.lbl_badge.setAlignment(Qt.AlignCenter)
        self.lbl_badge.setFixedSize(20, 20)
        self.lbl_badge.setStyleSheet(
            "background-color: #E5C158; color: #070A12; font-weight: 900; font-size: 12px; border-radius: 10px;"
        )
        self.lbl_badge.move(self.thumb_container.width() - 22, 2)
        self.lbl_badge.setVisible(is_selected)

        layout.addWidget(self.thumb_container)

        # Tên khổ in bên dưới
        display_name = template.name
        if template.is_dual_strip or "dual" in template.id.lower() or "ghép đôi" in display_name.lower():
            caption = "Khổ 4x6 - Ghép đôi 2 dải"
        elif "ngang" in display_name.lower() or "landscape" in template.type.lower():
            caption = "Khổ ngang 4x6 - 3 ảnh"
        elif "4" in display_name and "2x6" in display_name:
            caption = "Dải 2x6 - 4 ảnh"
        elif "3" in display_name and "2x6" in display_name:
            caption = "Dải 2x6 - 3 ảnh"
        else:
            caption = display_name[:20]

        self.lbl_caption = QLabel(caption)
        self.lbl_caption.setAlignment(Qt.AlignCenter)
        self.lbl_caption.setWordWrap(True)
        layout.addWidget(self.lbl_caption)

        self._update_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.lbl_badge.move(self.thumb_container.width() - 22, 2)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.lbl_badge.setVisible(selected)
        self._update_style()

    def _update_style(self):
        if self.is_selected:
            self.setStyleSheet(
                "FrameCardWidget { background-color: #0E1A33; border: 2px solid #E5C158; border-radius: 9px; }"
            )
            self.lbl_caption.setStyleSheet("font-size: 11px; font-weight: 800; color: #F7E7CE;")
        else:
            self.setStyleSheet(
                "FrameCardWidget { background-color: #080D1A; border: 1px solid #1E2D4A; border-radius: 9px; }"
                "FrameCardWidget:hover { border: 1px solid #D4AF37; background-color: #101A2F; }"
            )
            self.lbl_caption.setStyleSheet("font-size: 11px; font-weight: 600; color: #94A3B8;")

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

    def minimumSizeHint(self) -> QSize:
        return QSize(800, 500)

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
        self.main_layout.setContentsMargins(14, 10, 14, 12)
        self.main_layout.setSpacing(10)

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
        self.card_live.setStyleSheet("background-color: #050811; border: 1.5px solid #1E2D4A; border-radius: 12px;")
        l_live = QVBoxLayout(self.card_live)
        l_live.setContentsMargins(10, 8, 10, 10)
        l_live.setSpacing(6)

        # Thanh tiêu đề / trạng thái ngay trên Live View
        self.live_top_bar = QHBoxLayout()
        self.live_top_bar.setContentsMargins(4, 2, 4, 2)

        self.lbl_live_badge = QLabel("📷 CHƯA KẾT NỐI MÁY ẢNH | XEM TRƯỚC GIAO DIỆN")
        self.lbl_live_badge.setStyleSheet(
            "background-color: #DC2626; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #EF4444;"
        )
        self.live_top_bar.addWidget(self.lbl_live_badge)

        # Huy hiệu hiển thị sự kiện hiện tại gọn gàng
        self.lbl_active_event_pill = QLabel("📁 Sự kiện: SuKien_MacDinh")
        self.lbl_active_event_pill.setStyleSheet(
            "background-color: #0E1628; color: #D4AF37; font-size: 11px; font-weight: bold; border-radius: 6px; padding: 4px 10px; border: 1px solid #1E2D4A;"
        )
        self.live_top_bar.addWidget(self.lbl_active_event_pill)

        self.btn_switch_event = QPushButton("Đổi Sự Kiện")
        self.btn_switch_event.setFixedHeight(24)
        self.btn_switch_event.setStyleSheet(
            "QPushButton { background-color: #16223B; border: 1px solid #28395E; border-radius: 6px; color: #E2E8F0; font-size: 11px; font-weight: 600; padding: 0 8px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #F7E7CE; background-color: #1C2B47; }"
        )
        self.btn_switch_event.clicked.connect(lambda: self.request_tab_switch.emit(4))
        self.live_top_bar.addWidget(self.btn_switch_event)

        self.live_top_bar.addStretch()

        self.lbl_live_res = QLabel("LIVE VIEW 1920 × 1080")
        self.lbl_live_res.setStyleSheet(
            "background-color: #111A2E; color: #94A3B8; font-size: 11px; font-weight: 600; border-radius: 6px; padding: 4px 10px; border: 1px solid #233454;"
        )
        self.live_top_bar.addWidget(self.lbl_live_res)

        self.btn_live_fullscreen = QPushButton("⛶")
        self.btn_live_fullscreen.setFixedSize(28, 26)
        self.btn_live_fullscreen.setToolTip("Chế độ toàn màn hình (F11)")
        self.btn_live_fullscreen.setStyleSheet(
            "background-color: #111A2E; color: #E2E8F0; font-size: 13px; font-weight: bold; border-radius: 6px; border: 1px solid #233454;"
        )
        self.btn_live_fullscreen.clicked.connect(lambda: self.request_fullscreen.emit())
        self.live_top_bar.addWidget(self.btn_live_fullscreen)

        l_live.addLayout(self.live_top_bar)

        # Màn hình Live View chính
        self.lbl_viewport = QLabel()
        self.lbl_viewport.setAlignment(Qt.AlignCenter)
        self.lbl_viewport.setStyleSheet("background-color: #03050A; border-radius: 8px; border: 1px solid #162033;")
        self.lbl_viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_viewport.setMinimumHeight(240)
        l_live.addWidget(self.lbl_viewport)

        # Panel chờ kết nối rõ ràng (chuẩn studio, KHÔNG hiển thị người giả lập)
        self.panel_disconnected = QWidget(self.lbl_viewport)
        l_disc = QVBoxLayout(self.panel_disconnected)
        l_disc.setAlignment(Qt.AlignCenter)
        l_disc.setSpacing(10)

        icon_cam = QLabel("📷")
        icon_cam.setAlignment(Qt.AlignCenter)
        icon_cam.setStyleSheet("font-size: 54px; color: #475569; background: transparent; border: none;")
        l_disc.addWidget(icon_cam)

        lbl_disc_title = QLabel("CHƯA KẾT NỐI MÁY ẢNH")
        lbl_disc_title.setAlignment(Qt.AlignCenter)
        lbl_disc_title.setStyleSheet("color: #D4AF37; font-size: 20px; font-weight: 900; background: transparent; border: none;")
        l_disc.addWidget(lbl_disc_title)

        lbl_disc_desc = QLabel("Vui lòng cắm cáp USB máy ảnh DSLR/Mirrorless và bấm nút 'Kết nối máy ảnh' bên phải.")
        lbl_disc_desc.setAlignment(Qt.AlignCenter)
        lbl_disc_desc.setStyleSheet("color: #94A3B8; font-size: 13px; background: transparent; border: none;")
        l_disc.addWidget(lbl_disc_desc)

        self.panel_disconnected.show()

        # Overlay đếm ngược to ở giữa
        self.lbl_countdown = QLabel("", self.lbl_viewport)
        self.lbl_countdown.setAlignment(Qt.AlignCenter)
        self.lbl_countdown.setStyleSheet("color: #D4AF37; font-size: 130px; font-weight: 900; background: rgba(5,8,17,0.7); border: 3px solid #D4AF37; border-radius: 36px;")
        self.lbl_countdown.hide()

        # Label trạng thái ảnh ("Đang chụp ảnh 1/3...")
        self.lbl_status_badge = QLabel("", self.lbl_viewport)
        self.lbl_status_badge.setAlignment(Qt.AlignCenter)
        self.lbl_status_badge.setStyleSheet("color: #F7E7CE; font-size: 20px; font-weight: bold; background: rgba(13,21,39,0.92); border: 1.5px solid #D4AF37; padding: 8px 24px; border-radius: 18px;")
        self.lbl_status_badge.hide()

        self.top_row_layout.addWidget(self.card_live, 1)

        # -------------------------------------------------------------
        # CỘT PHẢI: TRẠNG THÁI MÁY ẢNH
        # -------------------------------------------------------------
        self.card_camera = QFrame()
        self.card_camera.setMinimumWidth(190)
        self.card_camera.setMaximumWidth(250)
        self.card_camera.setStyleSheet("background-color: #0A111F; border: 1px solid #1E2D4A; border-radius: 12px;")
        l_cam = QVBoxLayout(self.card_camera)
        l_cam.setContentsMargins(14, 14, 14, 14)
        l_cam.setSpacing(12)

        lbl_cam_card_title = QLabel("📷 <b>TRẠNG THÁI MÁY ẢNH</b>")
        lbl_cam_card_title.setStyleSheet("color: #D4AF37; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        l_cam.addWidget(lbl_cam_card_title)

        # Chấm trạng thái và nhãn
        h_stat = QHBoxLayout()
        h_stat.setSpacing(8)
        self.lbl_cam_dot = QLabel("🔴")
        self.lbl_cam_dot.setStyleSheet("font-size: 16px; border: none; background: transparent;")
        h_stat.addWidget(self.lbl_cam_dot)

        self.lbl_cam_status_text = QLabel("Chưa kết nối máy ảnh")
        self.lbl_cam_status_text.setStyleSheet("color: #F87171; font-size: 14px; font-weight: 700; border: none; background: transparent;")
        h_stat.addWidget(self.lbl_cam_status_text)
        h_stat.addStretch()
        l_cam.addLayout(h_stat)

        # Ghi chú hướng dẫn
        self.lbl_cam_note = QLabel("Hãy kết nối máy ảnh và chọn thiết bị trong mục Máy ảnh để bắt đầu chụp.")
        self.lbl_cam_note.setWordWrap(True)
        self.lbl_cam_note.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.3; border: none; background: transparent;")
        l_cam.addWidget(self.lbl_cam_note)

        l_cam.addSpacing(6)

        # Nút Kết nối máy ảnh màu vàng champagne
        self.btn_reconnect_cam = QPushButton("🔗 Kết nối máy ảnh")
        self.btn_reconnect_cam.setFixedHeight(44)
        self.btn_reconnect_cam.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F5DE88, stop:0.4 #E5C158, stop:1 #C59B27);"
            "color: #070A12; font-weight: 800; font-size: 13px; border-radius: 8px; border: 1px solid #FDF4DC; }"
            "QPushButton:hover { background: #E5C158; }"
        )
        self.btn_reconnect_cam.clicked.connect(self._reconnect_camera)
        l_cam.addWidget(self.btn_reconnect_cam)

        # Nút Mở cài đặt máy ảnh
        self.btn_cam_settings = QPushButton("⚙️ Mở cài đặt máy ảnh")
        self.btn_cam_settings.setFixedHeight(44)
        self.btn_cam_settings.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; border-radius: 8px; color: #E2E8F0; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { border: 1px solid #D4AF37; background-color: #17243E; color: #F7E7CE; }"
        )
        self.btn_cam_settings.clicked.connect(lambda: self.request_tab_switch.emit(2))
        l_cam.addWidget(self.btn_cam_settings)

        l_cam.addStretch()
        self.top_row_layout.addWidget(self.card_camera)

        self.main_layout.addLayout(self.top_row_layout, 6)

        # =============================================================
        # 2. HÀNG ĐIỀU KHIỂN PHÍA DƯỚI (4 THẺ: SỐ ẢNH, ĐẾM NGƯỢC, KHUNG, BỘ LỌC)
        # =============================================================
        self.ctrl_row_layout = QHBoxLayout()
        self.ctrl_row_layout.setSpacing(12)

        # -------------------------------------------------------------
        # THẺ 1: SỐ ẢNH MỖI LƯỢT (BỘ ĐIỀU KHIỂN LINH HOẠT [ − ] [ 3 ] [ + ])
        # -------------------------------------------------------------
        self.card_shots = QFrame()
        self.card_shots.setMinimumWidth(150)
        self.card_shots.setMaximumWidth(200)
        self.card_shots.setStyleSheet("background-color: #0A111F; border: 1px solid #1E2D4A; border-radius: 10px;")
        l_shots = QVBoxLayout(self.card_shots)
        l_shots.setContentsMargins(10, 8, 10, 8)
        l_shots.setSpacing(6)

        lbl_s_title = QLabel("📚 <b>Số ảnh mỗi lượt</b>")
        lbl_s_title.setStyleSheet("color: #F7E7CE; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        l_shots.addWidget(lbl_s_title)

        h_s_btns = QHBoxLayout()
        h_s_btns.setSpacing(6)

        self.btn_shots_minus = QPushButton("−")
        self.btn_shots_minus.setFixedSize(38, 38)
        self.btn_shots_minus.setStyleSheet(
            "QPushButton { font-size: 20px; font-weight: 900; background-color: #121C30; border: 1.5px solid #28395E; border-radius: 8px; color: #CBD5E1; }"
            "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; background-color: #1C2D4A; }"
            "QPushButton:pressed { background-color: #09101C; }"
        )
        self.btn_shots_minus.clicked.connect(self._decrease_shots)
        h_s_btns.addWidget(self.btn_shots_minus)

        self.txt_shots_input = QLineEdit(str(self.total_shots_needed))
        self.txt_shots_input.setFixedSize(46, 38)
        self.txt_shots_input.setAlignment(Qt.AlignCenter)
        self.txt_shots_input.setMaxLength(2)
        self.txt_shots_input.setToolTip("Nhập trực tiếp số ảnh (1 đến 16)")
        self.txt_shots_input.setStyleSheet(
            "QLineEdit { background: #070A12; color: #D4AF37; font-size: 17px; font-weight: 900; border: 1.5px solid #D4AF37; border-radius: 8px; }"
            "QLineEdit:focus { border: 2px solid #FDF4DC; background-color: #141F33; }"
        )
        self.txt_shots_input.setValidator(QIntValidator(1, 16, self))
        self.txt_shots_input.editingFinished.connect(self._on_shots_input_finished)
        self.txt_shots_input.returnPressed.connect(self._on_shots_input_finished)
        h_s_btns.addWidget(self.txt_shots_input)

        self.btn_shots_plus = QPushButton("+")
        self.btn_shots_plus.setFixedSize(38, 38)
        self.btn_shots_plus.setStyleSheet(
            "QPushButton { font-size: 20px; font-weight: 900; background-color: #121C30; border: 1.5px solid #28395E; border-radius: 8px; color: #CBD5E1; }"
            "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; background-color: #1C2D4A; }"
            "QPushButton:pressed { background-color: #09101C; }"
        )
        self.btn_shots_plus.clicked.connect(self._increase_shots)
        h_s_btns.addWidget(self.btn_shots_plus)

        l_shots.addLayout(h_s_btns)

        lbl_s_hint = QLabel("Giới hạn: 1 – 16 ảnh")
        lbl_s_hint.setStyleSheet("color: #64748B; font-size: 11px; border: none; background: transparent;")
        lbl_s_hint.setAlignment(Qt.AlignCenter)
        l_shots.addWidget(lbl_s_hint)
        l_shots.addStretch()
        self.ctrl_row_layout.addWidget(self.card_shots)

        # -------------------------------------------------------------
        # THẺ 2: ĐẾM NGƯỢC
        # -------------------------------------------------------------
        self.card_cd = QFrame()
        self.card_cd.setMinimumWidth(170)
        self.card_cd.setMaximumWidth(240)
        self.card_cd.setStyleSheet("background-color: #0A111F; border: 1px solid #1E2D4A; border-radius: 10px;")
        l_cd = QVBoxLayout(self.card_cd)
        l_cd.setContentsMargins(10, 10, 10, 10)
        l_cd.setSpacing(8)

        lbl_cd_title = QLabel("⏱️ <b>Đếm ngược</b>")
        lbl_cd_title.setStyleSheet("color: #F7E7CE; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        l_cd.addWidget(lbl_cd_title)

        h_cd_btns = QHBoxLayout()
        h_cd_btns.setSpacing(6)
        self.btn_cd_3 = QPushButton("3 giây")
        self.btn_cd_3.setFixedHeight(40)
        self.btn_cd_3.clicked.connect(lambda: self._set_countdown_duration(3))
        h_cd_btns.addWidget(self.btn_cd_3)

        self.btn_cd_5 = QPushButton("5 giây")
        self.btn_cd_5.setFixedHeight(40)
        self.btn_cd_5.clicked.connect(lambda: self._set_countdown_duration(5))
        h_cd_btns.addWidget(self.btn_cd_5)

        self.btn_cd_10 = QPushButton("10 giây")
        self.btn_cd_10.setFixedHeight(40)
        self.btn_cd_10.clicked.connect(lambda: self._set_countdown_duration(10))
        h_cd_btns.addWidget(self.btn_cd_10)

        l_cd.addLayout(h_cd_btns)
        l_cd.addStretch()
        self.ctrl_row_layout.addWidget(self.card_cd)

        # -------------------------------------------------------------
        # THẺ 3: MẪU KHUNG ẢNH (CAROUSEL THUMBNAIL THẬT)
        # -------------------------------------------------------------
        self.card_frames = QFrame()
        self.card_frames.setStyleSheet("background-color: #0A111F; border: 1px solid #1E2D4A; border-radius: 10px;")
        l_fr = QVBoxLayout(self.card_frames)
        l_fr.setContentsMargins(12, 8, 12, 8)
        l_fr.setSpacing(6)

        # Tiêu đề & nút Chọn khung khác
        h_fr_head = QHBoxLayout()
        lbl_fr_title = QLabel("🖼️ <b>Mẫu khung ảnh</b>")
        lbl_fr_title.setStyleSheet("color: #F7E7CE; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        h_fr_head.addWidget(lbl_fr_title)

        h_fr_head.addStretch()

        self.btn_goto_frames = QPushButton("🖼️ Chọn khung khác")
        self.btn_goto_frames.setFixedHeight(26)
        self.btn_goto_frames.setStyleSheet(
            "background-color: #121C30; border: 1px solid #28395E; border-radius: 6px; color: #E2E8F0; font-size: 11px; font-weight: 600; padding: 2px 10px;"
        )
        self.btn_goto_frames.clicked.connect(lambda: self.request_tab_switch.emit(1))
        h_fr_head.addWidget(self.btn_goto_frames)
        l_fr.addLayout(h_fr_head)

        # Carousel hàng ngang các thẻ khung
        h_fr_carousel = QHBoxLayout()
        h_fr_carousel.setSpacing(8)

        self.btn_frame_prev = QPushButton("‹")
        self.btn_frame_prev.setFixedSize(22, 50)
        self.btn_frame_prev.setStyleSheet(
            "background-color: #121C30; border: 1px solid #243555; color: #94A3B8; font-size: 18px; font-weight: bold; border-radius: 4px;"
        )
        self.btn_frame_prev.clicked.connect(self._prev_frame_page)
        h_fr_carousel.addWidget(self.btn_frame_prev)

        self.frames_container_layout = QHBoxLayout()
        self.frames_container_layout.setSpacing(10)
        h_fr_carousel.addLayout(self.frames_container_layout)

        self.btn_frame_next = QPushButton("›")
        self.btn_frame_next.setFixedSize(22, 50)
        self.btn_frame_next.setStyleSheet(
            "background-color: #121C30; border: 1px solid #243555; color: #94A3B8; font-size: 18px; font-weight: bold; border-radius: 4px;"
        )
        self.btn_frame_next.clicked.connect(self._next_frame_page)
        h_fr_carousel.addWidget(self.btn_frame_next)

        l_fr.addLayout(h_fr_carousel)
        self.ctrl_row_layout.addWidget(self.card_frames, 2)

        # -------------------------------------------------------------
        # THẺ 4: BỘ LỌC MÀU (THƯ VIỆN SẠCH, CHƯA CÓ BỘ LỌC)
        # -------------------------------------------------------------
        self.card_filters = QFrame()
        self.card_filters.setMinimumWidth(170)
        self.card_filters.setMaximumWidth(240)
        self.card_filters.setStyleSheet("background-color: #0A111F; border: 1px solid #1E2D4A; border-radius: 10px;")
        l_fil = QVBoxLayout(self.card_filters)
        l_fil.setContentsMargins(12, 10, 12, 10)
        l_fil.setSpacing(6)

        lbl_fil_title = QLabel("🎨 <b>Bộ lọc màu</b>")
        lbl_fil_title.setStyleSheet("color: #F7E7CE; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        l_fil.addWidget(lbl_fil_title)

        # Trạng thái Chưa có bộ lọc
        self.widget_no_filter = QWidget()
        l_nf = QVBoxLayout(self.widget_no_filter)
        l_nf.setContentsMargins(0, 0, 0, 0)
        l_nf.setSpacing(4)
        l_nf.setAlignment(Qt.AlignCenter)

        icon_plus = QLabel("+")
        icon_plus.setAlignment(Qt.AlignCenter)
        icon_plus.setFixedSize(30, 30)
        icon_plus.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #D4AF37; border: 1.5px dashed #475569; border-radius: 15px; background: #0A111F;"
        )
        l_nf.addWidget(icon_plus, alignment=Qt.AlignCenter)

        lbl_nf_text = QLabel("Chưa có bộ lọc")
        lbl_nf_text.setAlignment(Qt.AlignCenter)
        lbl_nf_text.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 700; border: none; background: transparent;")
        l_nf.addWidget(lbl_nf_text)

        lbl_nf_sub = QLabel("Thêm bộ lọc của bạn để tạo phong cách riêng cho ảnh.")
        lbl_nf_sub.setAlignment(Qt.AlignCenter)
        lbl_nf_sub.setWordWrap(True)
        lbl_nf_sub.setStyleSheet("color: #94A3B8; font-size: 10px; border: none; background: transparent;")
        l_nf.addWidget(lbl_nf_sub)

        self.btn_add_filter_champagne = QPushButton("➕ Thêm bộ lọc")
        self.btn_add_filter_champagne.setFixedHeight(34)
        self.btn_add_filter_champagne.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F5DE88, stop:0.4 #E5C158, stop:1 #C59B27);"
            "color: #070A12; font-weight: 800; font-size: 12px; border-radius: 6px; border: 1px solid #FDF4DC; }"
            "QPushButton:hover { background: #E5C158; }"
        )
        self.btn_add_filter_champagne.clicked.connect(self._open_filter_dialog)
        l_nf.addWidget(self.btn_add_filter_champagne)

        l_fil.addWidget(self.widget_no_filter)

        # Trạng thái Khi đã có bộ lọc
        self.widget_has_filters = QWidget()
        l_hf = QVBoxLayout(self.widget_has_filters)
        l_hf.setContentsMargins(0, 0, 0, 0)
        l_hf.setSpacing(6)

        self.combo_active_filters = QComboBox()
        self.combo_active_filters.setFixedHeight(34)
        self.combo_active_filters.currentIndexChanged.connect(self._on_filter_changed)
        l_hf.addWidget(self.combo_active_filters)

        self.btn_manage_filter = QPushButton("+ Thêm / Quản Lý")
        self.btn_manage_filter.setFixedHeight(30)
        self.btn_manage_filter.setStyleSheet(
            "background-color: #121C30; border: 1px solid #28395E; border-radius: 6px; color: #E2E8F0; font-size: 11px; font-weight: 600;"
        )
        self.btn_manage_filter.clicked.connect(self._open_filter_dialog)
        l_hf.addWidget(self.btn_manage_filter)

        self.widget_has_filters.hide()
        l_fil.addWidget(self.widget_has_filters)

        l_fil.addStretch()
        self.ctrl_row_layout.addWidget(self.card_filters)

        self.main_layout.addLayout(self.ctrl_row_layout, 3)

        # =============================================================
        # 3. ĐÁY MÀN HÌNH: TÙY CHỌN, NÚT BẮT ĐẦU CHỤP VÀNG KHỔNG LỒ & TOÀN MÀN HÌNH
        # =============================================================
        self.bottom_bar_layout = QHBoxLayout()
        self.bottom_bar_layout.setContentsMargins(10, 4, 10, 4)
        self.bottom_bar_layout.setSpacing(16)

        # Checkbox bên trái
        l_chk = QVBoxLayout()
        l_chk.setSpacing(4)
        self.chk_preview = QCheckBox("Xem trước ảnh sau khi chụp")
        self.chk_preview.setChecked(True)
        l_chk.addWidget(self.chk_preview)

        self.chk_autoprint = QCheckBox("Tự động in sau khi chụp")
        self.chk_autoprint.setChecked(False)
        l_chk.addWidget(self.chk_autoprint)
        self.bottom_bar_layout.addLayout(l_chk)

        self.bottom_bar_layout.addStretch()

        # NÚT BẮT ĐẦU CHỤP KHỔNG LỒ VÀNG CHAMPAGNE (CAPSULE GLOW)
        self.btn_start = QPushButton("📷 BẮT ĐẦU CHỤP")
        self.btn_start.setFixedSize(360, 62)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F7E7CE, stop:0.35 #E5C158, stop:1 #C59B27);"
            "  color: #070A12;"
            "  font-size: 22px;"
            "  font-weight: 900;"
            "  letter-spacing: 1px;"
            "  border-radius: 31px;"
            "  border: 2px solid #FFF8E7;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFFFFF, stop:0.35 #F0D278, stop:1 #D4AF37);"
            "  border: 2px solid #FFFFFF;"
            "}"
            "QPushButton:pressed {"
            "  background: #C59B27;"
            "}"
            "QPushButton:disabled {"
            "  background: #2D3748; color: #718096; border: 1px solid #4A5568;"
            "}"
        )
        self.btn_start.clicked.connect(self.start_capture_flow)
        self.bottom_bar_layout.addWidget(self.btn_start)

        # CÁC NÚT KHI Ở CHẾ ĐỘ XEM KẾT QUẢ (REVIEW STATE)
        self.btn_retake = QPushButton("🔄 Chụp Lại")
        self.btn_retake.setFixedHeight(50)
        self.btn_retake.setStyleSheet("background-color: #15223D; border: 1px solid #28395E; color: #E2E8F0; border-radius: 8px; font-weight: 700; padding: 0 16px;")
        self.btn_retake.clicked.connect(self._retake_session)
        self.btn_retake.hide()
        self.bottom_bar_layout.addWidget(self.btn_retake)

        self.btn_save = QPushButton("💾 Lưu Ảnh")
        self.btn_save.setFixedHeight(50)
        self.btn_save.setStyleSheet("background-color: #15223D; border: 1px solid #28395E; color: #E2E8F0; border-radius: 8px; font-weight: 700; padding: 0 16px;")
        self.btn_save.clicked.connect(self._save_photo_dialog)
        self.btn_save.hide()
        self.bottom_bar_layout.addWidget(self.btn_save)

        self.btn_qr = QPushButton("📱 Quét Mã QR")
        self.btn_qr.setFixedHeight(50)
        self.btn_qr.setStyleSheet("background-color: #15223D; border: 1px solid #28395E; color: #E2E8F0; border-radius: 8px; font-weight: 700; padding: 0 16px;")
        self.btn_qr.clicked.connect(self._show_qr_dialog)
        self.btn_qr.hide()
        self.bottom_bar_layout.addWidget(self.btn_qr)

        self.btn_print = QPushButton("🖨️ IN ẢNH NGAY")
        self.btn_print.setFixedHeight(50)
        self.btn_print.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F5DE88, stop:0.4 #E5C158, stop:1 #C59B27);"
            "color: #070A12; font-weight: 900; font-size: 15px; border-radius: 8px; border: 1px solid #FDF4DC; padding: 0 24px;"
        )
        self.btn_print.clicked.connect(self._print_composite)
        self.btn_print.hide()
        self.bottom_bar_layout.addWidget(self.btn_print)

        self.btn_finish = QPushButton("✅ Hoàn Tất")
        self.btn_finish.setFixedHeight(50)
        self.btn_finish.setStyleSheet("background-color: #15223D; border: 1px solid #28395E; color: #E2E8F0; border-radius: 8px; font-weight: 700; padding: 0 16px;")
        self.btn_finish.clicked.connect(self._finish_session)
        self.btn_finish.hide()
        self.bottom_bar_layout.addWidget(self.btn_finish)

        self.bottom_bar_layout.addStretch()

        # Nút Toàn màn hình bên phải
        self.btn_fullscreen = QPushButton("⛶ Toàn màn hình")
        self.btn_fullscreen.setFixedHeight(42)
        self.btn_fullscreen.setStyleSheet(
            "QPushButton { background-color: #111A2E; border: 1px solid #233454; border-radius: 8px; color: #E2E8F0; font-size: 13px; font-weight: 600; padding: 0 14px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; background-color: #17243E; color: #F7E7CE; }"
        )
        self.btn_fullscreen.clicked.connect(lambda: self.request_fullscreen.emit())
        self.bottom_bar_layout.addWidget(self.btn_fullscreen)

        self.main_layout.addLayout(self.bottom_bar_layout)

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
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F5DE88, stop:0.4 #E5C158, stop:1 #C59B27);"
            "color: #070A12; font-weight: 800; font-size: 13px; border-radius: 6px; border: 1.5px solid #FDF4DC; padding: 4px 4px; }"
        )
        inactive_style = (
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; border-radius: 6px; color: #CBD5E1; font-size: 13px; font-weight: 600; padding: 4px 4px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #F7E7CE; }"
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
            lbl_empty = QLabel("Chưa có khung ảnh. Hãy nhập khung mới.")
            lbl_empty.setStyleSheet("color: #94A3B8; font-style: italic; font-size: 12px; border: none; background: transparent;")
            self.frames_container_layout.addWidget(lbl_empty)
            return

        if not self.selected_frame_id and frames:
            self.selected_frame_id = frames[0].id

        # Hiển thị 3 khung trên mỗi trang
        page_size = 3
        start_idx = self.frame_carousel_offset
        end_idx = min(start_idx + page_size, len(frames))

        for idx in range(start_idx, end_idx):
            f = frames[idx]
            pix = self._get_frame_thumbnail_pixmap(f)
            card = FrameCardWidget(
                template=f,
                thumbnail_pixmap=pix,
                is_selected=(f.id == self.selected_frame_id),
                on_select=self._on_frame_card_selected
            )
            self.frame_cards.append(card)
            self.frames_container_layout.addWidget(card)

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
        self.frame_carousel_offset = max(0, self.frame_carousel_offset - 1)
        self._load_frame_options()

    def _next_frame_page(self):
        frames = self.frame_mgr.list_frames()
        if not frames:
            return
        if self.frame_carousel_offset + 3 < len(frames):
            self.frame_carousel_offset += 1
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
    # LIVE VIEW & MÁY ẢNH (ASYNC THREADED 30+ FPS)
    # -------------------------------------------------------------
    def start_live_view(self):
        self._live_view_active = True
        if hasattr(self, 'live_view_worker'):
            if not self.live_view_worker.isRunning():
                self.live_view_worker = CameraLiveViewWorker(self.camera_mgr, self)
                self.live_view_worker.frame_ready.connect(self._on_live_view_frame)
                self.live_view_worker.start()
            else:
                self.live_view_worker.resume()
        self._update_camera_status_ui()

    def stop_live_view(self):
        self._live_view_active = False
        if hasattr(self, 'live_view_worker') and self.live_view_worker.isRunning():
            self.live_view_worker.stop()

    def _periodic_camera_check(self):
        if self.current_state in ("IDLE", "COUNTDOWN"):
            self._update_camera_status_ui()

    def _on_live_view_frame(self, frame_rgb: np.ndarray):
        if not getattr(self, "_live_view_active", True) or self.current_state not in ("IDLE", "COUNTDOWN", "CAPTURING"):
            return

        if self.panel_disconnected.isVisible():
            self.panel_disconnected.hide()

        h, w, ch = frame_rgb.shape
        qimg = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888)
        if qimg.isNull():
            return

        pixmap = QPixmap.fromImage(qimg)
        lbl_w = self.lbl_viewport.width()
        lbl_h = self.lbl_viewport.height()
        if lbl_w <= 0 or lbl_h <= 0:
            return

        # FastTransformation: siêu mượt 30+ FPS không tiêu tốn CPU rasterization
        scaled = pixmap.scaled(lbl_w, lbl_h, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.lbl_viewport.setPixmap(scaled)

        # Căn giữa nhãn đếm ngược & trạng thái
        if self.lbl_countdown.isVisible():
            self.lbl_countdown.setGeometry((lbl_w - 220) // 2, (lbl_h - 220) // 2, 220, 220)
        if self.lbl_status_badge.isVisible():
            badge_w = min(max(360, self.lbl_status_badge.sizeHint().width() + 32), max(360, lbl_w - 40))
            self.lbl_status_badge.setGeometry((lbl_w - badge_w) // 2, lbl_h - 75, badge_w, 48)

    def _reconnect_camera(self):
        """Thử dò quét và kết nối lại máy ảnh thực tế."""
        self.lbl_cam_status_text.setText("Đang kết nối lại...")
        connected = self.camera_mgr.switch_backend("directshow", 0)
        if not connected:
            connected = self.camera_mgr.switch_backend("digicam")
        if not connected:
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
            self.lbl_cam_dot.setText("🔴")
            self.lbl_cam_status_text.setText("Chưa kết nối máy ảnh")
            self.lbl_cam_status_text.setStyleSheet("color: #F87171; font-size: 14px; font-weight: 700; border: none; background: transparent;")
            self.lbl_live_badge.setText("📷 CHƯA KẾT NỐI MÁY ẢNH | XEM TRƯỚC GIAO DIỆN")
            self.lbl_live_badge.setStyleSheet(
                "background-color: #DC2626; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #EF4444;"
            )
            self.lbl_live_res.setText("LIVE VIEW (Demo) 1920 × 1080")
            self.lbl_cam_note.setText("Hãy kết nối máy ảnh và chọn thiết bị trong mục Máy ảnh để bắt đầu chụp.")
            if not self.panel_disconnected.isVisible():
                self.panel_disconnected.show()
                self.lbl_viewport.setPixmap(QPixmap())
            self.panel_disconnected.setGeometry(0, 0, self.lbl_viewport.width(), self.lbl_viewport.height())
        else:
            self.lbl_cam_dot.setText("🟢")
            self.lbl_cam_status_text.setText(f"Đã kết nối ({backend.upper()})")
            self.lbl_cam_status_text.setStyleSheet("color: #34D399; font-size: 14px; font-weight: 700; border: none; background: transparent;")
            self.lbl_live_badge.setText(f"📷 ĐÃ KẾT NỐI MÁY ẢNH ({backend.upper()})")
            self.lbl_live_badge.setStyleSheet(
                "background-color: #16A34A; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #22C55E;"
            )
            res_text = "LIVE VIEW 1920 × 1080" if backend != "digicam" else "LIVE VIEW 6000 × 4000"
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
    # TIẾN TRÌNH CHỤP ẢNH TỰ ĐỘNG
    # -------------------------------------------------------------
    def start_capture_flow(self):
        if self.current_state != "IDLE":
            return

        if not self.camera_mgr.is_connected() and self.camera_mgr.current_backend_name != "simulator":
            QMessageBox.warning(self, "Máy Ảnh", "Chưa kết nối máy ảnh! Vui lòng cắm cáp USB máy ảnh và bấm 'Kết nối máy ảnh'.")
            return

        self.current_state = "COUNTDOWN"
        self.captured_originals.clear()
        self.captured_paths.clear()
        self.current_shot_index = 1

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
        self.lbl_countdown.show()

        self.lbl_status_badge.setStyleSheet(
            "color: #F7E7CE; font-size: 20px; font-weight: bold; "
            "background: rgba(13,21,39,0.92); border: 1.5px solid #D4AF37; "
            "padding: 8px 24px; border-radius: 18px;"
        )
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
        self.lbl_viewport.setStyleSheet("background-color: #FFFFFF;")
        QTimer.singleShot(120, lambda: self.lbl_viewport.setStyleSheet("background-color: #03050A; border-radius: 8px; border: 1px solid #162033;"))

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
            logger.warning("Không chụp được ảnh từ camera thật, tạo ảnh chụp dự phòng.")
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

        # Ẩn nút Chụp ban đầu, hiện các nút Xem kết quả
        self.btn_start.hide()
        self.chk_preview.hide()
        self.chk_autoprint.hide()
        self.btn_fullscreen.hide()

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
            lbl_w = self.lbl_viewport.width()
            lbl_h = self.lbl_viewport.height()
            if lbl_w > 0 and lbl_h > 0:
                self.lbl_viewport.setPixmap(pixmap.scaled(lbl_w, lbl_h, Qt.KeepAspectRatio, Qt.FastTransformation))
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
        rgb = self.current_composite.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        lbl_w = self.lbl_viewport.width()
        lbl_h = self.lbl_viewport.height()
        if lbl_w > 0 and lbl_h > 0:
            scaled = pixmap.scaled(lbl_w, lbl_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_viewport.setPixmap(scaled)

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
        self.current_final_path = None
        self.captured_originals.clear()
        self.captured_paths.clear()

        # Hiện lại thanh điều khiển chụp ban đầu
        self.btn_start.show()
        self.btn_start.setEnabled(True)
        self.chk_preview.show()
        self.chk_autoprint.show()
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

    def closeEvent(self, event):
        if hasattr(self, 'live_view_worker') and self.live_view_worker.isRunning():
            self.live_view_worker.stop()
        super().closeEvent(event)
