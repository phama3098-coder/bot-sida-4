"""
1998 TEAM — Smart Beauty Panel (AI Face Retouching Dialog & Control Widget)
Hiển thị sau mỗi lần chụp thành công:
- Tiêu đề: "✨ ẢNH VỪA CHỤP"
- Tiến độ: "Đã chụp X/Y"
- 3 thanh trượt điều chỉnh tự nhiên (bước nhảy 5%, mặc định 0%):
  1. ☀ Sáng da (0 - 100%)
  2. ◉ Mịn da (0 - 100%)
  3. 💄 Son môi (0 - 100%)
- Nút bấm: "Đặt lại", "Xem ảnh gốc", "Xác nhận".
- Luồng xem trước bất đồng bộ bằng QThread, không chặn UI hoặc Live View.
- Bảo toàn ảnh gốc trên đĩa, xuất ảnh làm đẹp chất lượng cao khi xác nhận.
"""

import os
import time
import logging
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
import cv2
from PIL import Image, ImageOps

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QFrame, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSize, QPoint
from PySide6.QtGui import QPixmap, QImage, QColor, QFont, QPainter, QPen

from vietphotobooth.filters.beauty_engine import SmartBeautyEngine
from vietphotobooth.camera.face_detector import DetectedFace

logger = logging.getLogger(__name__)


class BeautyPreviewWorker(QThread):
    """Worker render preview ảnh làm đẹp trong luồng nền."""
    preview_ready = Signal(int, np.ndarray)  # req_id, processed_bgr

    def __init__(self, engine: SmartBeautyEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._preview_bgr: Optional[np.ndarray] = None
        self._faces: List[DetectedFace] = []
        self._brighten = 0.0
        self._smooth = 0.0
        self._lips = 0.0
        self._req_id = 0
        self._pending = False
        self._running = True

    def update_params(
        self,
        req_id: int,
        preview_bgr: np.ndarray,
        faces: List[DetectedFace],
        brighten: float,
        smooth: float,
        lips: float
    ):
        self._req_id = req_id
        self._preview_bgr = preview_bgr
        self._faces = faces
        self._brighten = brighten
        self._smooth = smooth
        self._lips = lips
        self._pending = True

    def stop(self):
        self._running = False
        self.requestInterruption()

    def run(self):
        while self._running and not self.isInterruptionRequested():
            if self._pending and self._preview_bgr is not None:
                self._pending = False
                cur_req = self._req_id
                cur_bgr = self._preview_bgr
                cur_faces = self._faces
                cur_brighten = self._brighten
                cur_smooth = self._smooth
                cur_lips = self._lips

                try:
                    res_bgr = self.engine.apply_beauty(
                        cur_bgr,
                        skin_brighten_pct=cur_brighten,
                        skin_smooth_pct=cur_smooth,
                        lip_tint_pct=cur_lips,
                        faces=cur_faces
                    )
                    if not self.isInterruptionRequested() and cur_req == self._req_id:
                        self.preview_ready.emit(cur_req, res_bgr)
                except Exception as ex:
                    logger.error("Lỗi trong BeautyPreviewWorker: %s", ex)

            # Nghỉ ngắn tránh chiếm dụng CPU
            self.msleep(15)


class SmartBeautyDialog(QDialog):
    """
    Hộp thoại làm đẹp thông minh hiển thị sau mỗi ảnh chụp thành công.
    Tông màu chuẩn studio 1998 TEAM: Navy / Đen than & Vàng Champagne.
    """

    beauty_confirmed = Signal(object, dict, bool)  # PIL.Image, settings_dict, reuse_flag

    def __init__(
        self,
        image_pil_or_path: Any,
        shot_index: int = 1,
        total_shots: int = 1,
        initial_settings: Optional[Dict[str, float]] = None,
        reuse_for_next: bool = False,
        auto_timeout_sec: int = 25,
        engine: Optional[SmartBeautyEngine] = None,
        parent=None
    ):
        super().__init__(parent)
        self.shot_index = shot_index
        self.total_shots = total_shots
        self.auto_timeout_sec = auto_timeout_sec
        self.reuse_for_next = reuse_for_next
        self.engine = engine or SmartBeautyEngine()

        # Tải ảnh gốc và chuẩn hóa góc xoay theo metadata EXIF nếu có
        self._original_pil = None
        self._original_path = None
        if isinstance(image_pil_or_path, str):
            self._original_path = image_pil_or_path
            opened = Image.open(image_pil_or_path)
            try:
                self._original_pil = ImageOps.exif_transpose(opened)
            except Exception:
                self._original_pil = opened
        elif isinstance(image_pil_or_path, Image.Image):
            try:
                self._original_pil = ImageOps.exif_transpose(image_pil_or_path)
            except Exception:
                self._original_pil = image_pil_or_path
        else:
            raise ValueError("image_pil_or_path phải là str (đường dẫn) hoặc PIL.Image")

        # Chuẩn bị ảnh BGR gốc
        rgb_arr = np.array(self._original_pil.convert("RGB"))
        self._full_bgr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        # Chuẩn bị ảnh preview tỉ lệ phù hợp cho giao diện
        self._preview_bgr, self._preview_faces, self._scale_to_preview = self.engine.generate_scaled_preview(
            self._full_bgr, max_dim=1080
        )
        self._full_faces = self.engine.map_faces_to_scale(
            self._preview_faces, 1.0 / self._scale_to_preview if self._scale_to_preview > 0 else 1.0
        )

        # Trạng thái thông số
        init_s = initial_settings or {}
        self._brighten_val = float(init_s.get("brighten", 0.0))
        self._smooth_val = float(init_s.get("smooth", 0.0))
        self._lips_val = float(init_s.get("lips", 0.0))

        self._showing_original = False
        self._current_preview_bgr = self._preview_bgr.copy()
        self._req_id = 0
        self._final_pil_result = self._original_pil
        self._remaining_sec = self.auto_timeout_sec

        # Khởi tạo giao diện
        self._init_window()
        self._init_ui()

        # Khởi tạo worker render nền
        self._worker = BeautyPreviewWorker(self.engine, self)
        self._worker.preview_ready.connect(self._on_preview_ready)
        self._worker.start()

        # Auto-timeout timer
        self._timeout_timer = QTimer(self)
        self._timeout_timer.timeout.connect(self._on_timeout_tick)
        if self.auto_timeout_sec > 0:
            self._timeout_timer.start(1000)

        # Cập nhật lần đầu
        if self._brighten_val > 0 or self._smooth_val > 0 or self._lips_val > 0:
            self._request_render()
        else:
            self._update_preview_display(self._preview_bgr)

    def _init_window(self):
        self.setWindowTitle("1998 TEAM — Smart Beauty Panel")
        self.setModal(True)
        self.resize(1100, 720)
        self.setMinimumSize(960, 600)
        # Frameless with rounded styling
        self.setStyleSheet(
            "QDialog { background-color: #F8FAFC; border: 2px solid #D4AF37; border-radius: 16px; }"
            "QLabel { color: #303746; font-family: 'Segoe UI', Arial, sans-serif; }"
            "QCheckBox { color: #64748B; font-size: 13px; font-weight: 500; spacing: 8px; }"
            "QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1.5px solid #CBD5E1; background-color: #FFFFFF; }"
            "QCheckBox::indicator:checked { background-color: #D4AF37; border-color: #F59E0B; }"
        )

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # -------------------------------------------------------------
        # 1. HEADER BAR: Title, Progress Badge, Face Status & Countdown
        # -------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        # Tiêu đề chính
        lbl_title = QLabel("✨ ẢNH VỪA CHỤP")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: 900; color: #1E40AF; letter-spacing: 0.5px;")
        header_layout.addWidget(lbl_title)

        # Huy hiệu tiến độ (ví dụ: Đã chụp 1/6)
        self.lbl_progress = QLabel(f"Đã chụp {self.shot_index}/{self.total_shots}")
        self.lbl_progress.setStyleSheet(
            "background-color: #EFF6FF; color: #1E40AF; font-size: 14px; font-weight: bold; "
            "border: 1.5px solid #BFDBFE; padding: 4px 14px; border-radius: 12px;"
        )
        header_layout.addWidget(self.lbl_progress)

        # Huy hiệu trạng thái nhận diện khuôn mặt
        num_faces = len(self._preview_faces)
        if not self.engine.is_available:
            status_text = "⚠️ AI Không Khả Dụng"
            status_style = "background-color: rgba(239, 68, 68, 0.15); color: #DC2626; border: 1px solid #F87171;"
        elif num_faces == 0:
            status_text = "ℹ Không Phát Hiện Khuôn Mặt"
            status_style = "background-color: rgba(148, 163, 184, 0.15); color: #64748B; border: 1px solid #CBD5E1;"
        elif num_faces == 1:
            status_text = "👤 Đã Nhận Diện 1 Khuôn Mặt"
            status_style = "background-color: rgba(16, 185, 129, 0.15); color: #059669; border: 1px solid #6EE7B7;"
        else:
            status_text = f"👥 Đã Nhận Diện {num_faces} Khuôn Mặt"
            status_style = "background-color: rgba(6, 182, 212, 0.15); color: #0284C7; border: 1px solid #7DD3FC;"

        self.lbl_face_status = QLabel(status_text)
        self.lbl_face_status.setStyleSheet(
            f"{status_style} font-size: 13px; font-weight: 600; padding: 4px 12px; border-radius: 12px;"
        )
        header_layout.addWidget(self.lbl_face_status)

        header_layout.addStretch()

        # Huy hiệu đếm ngược tự động xác nhận
        self.lbl_countdown = QLabel(f"Tự động tiếp tục sau: {self._remaining_sec}s")
        self.lbl_countdown.setStyleSheet(
            "color: #64748B; font-size: 12px; font-weight: 500; background: #FFFFFF; "
            "padding: 4px 10px; border-radius: 8px; border: 1.5px solid #D9DEE7;"
        )
        header_layout.addWidget(self.lbl_countdown)

        main_layout.addLayout(header_layout)

        # -------------------------------------------------------------
        # 2. KHU VỰC CHÍNH: Preview Bên Trái (65%), Điều Khiển Bên Phải (35%)
        # -------------------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # KHUNG XEM TRƯỚC (PREVIEW VIEWPORT)
        preview_container = QFrame()
        preview_container.setStyleSheet(
            "background-color: #0F172A; border: 1.5px solid #D9DEE7; border-radius: 14px;"
        )
        preview_vbox = QVBoxLayout(preview_container)
        preview_vbox.setContentsMargins(8, 8, 8, 8)

        self.lbl_viewport = QLabel()
        self.lbl_viewport.setAlignment(Qt.AlignCenter)
        self.lbl_viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_viewport.setMinimumSize(480, 420)
        preview_vbox.addWidget(self.lbl_viewport)

        content_layout.addWidget(preview_container, stretch=65)

        # BẢNG ĐIỀU KHIỂN LÀM ĐẸP (RIGHT CONTROLS)
        ctrl_card = QFrame()
        ctrl_card.setStyleSheet(
            "background-color: #FFFFFF; border: 1.5px solid #D9DEE7; border-radius: 14px;"
        )
        ctrl_vbox = QVBoxLayout(ctrl_card)
        ctrl_vbox.setContentsMargins(20, 20, 20, 20)
        ctrl_vbox.setSpacing(18)

        lbl_ctrl_title = QLabel("Tùy Chỉnh Làm Đẹp Tự Nhiên")
        lbl_ctrl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E40AF;")
        ctrl_vbox.addWidget(lbl_ctrl_title)

        lbl_desc = QLabel("Công nghệ AI nhận diện đa diện khuôn mặt, giữ nguyên texture chân thật của làn da.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #64748B; font-size: 12px; line-height: 1.4;")
        ctrl_vbox.addWidget(lbl_desc)

        ctrl_vbox.addSpacing(6)

        slider_style = """
            QSlider::groove:horizontal {
                height: 8px;
                background: #E2E8F0;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E40AF, stop:1 #D4AF37);
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2.5px solid #D4AF37;
                width: 22px;
                height: 22px;
                margin-top: -7px;
                margin-bottom: -7px;
                border-radius: 11px;
            }
            QSlider::handle:horizontal:hover {
                background: #D4AF37;
                border: 2.5px solid #FFFFFF;
            }
        """

        # Thanh trượt 1: Sáng da (0 - 100%, step 5, default 0%)
        l_s1 = QHBoxLayout()
        lbl_s1_name = QLabel("☀ Sáng da")
        lbl_s1_name.setStyleSheet("font-size: 14px; font-weight: 600; color: #303746;")
        self.lbl_s1_val = QLabel(f"{int(self._brighten_val)}%")
        self.lbl_s1_val.setStyleSheet("font-size: 14px; font-weight: bold; color: #1E40AF;")
        l_s1.addWidget(lbl_s1_name)
        l_s1.addStretch()
        l_s1.addWidget(self.lbl_s1_val)
        ctrl_vbox.addLayout(l_s1)

        self.slider_brighten = QSlider(Qt.Horizontal)
        self.slider_brighten.setRange(0, 100)
        self.slider_brighten.setSingleStep(5)
        self.slider_brighten.setPageStep(10)
        self.slider_brighten.setValue(int(self._brighten_val))
        self.slider_brighten.setStyleSheet(slider_style)
        self.slider_brighten.valueChanged.connect(self._on_slider_brighten_changed)
        ctrl_vbox.addWidget(self.slider_brighten)

        # Thanh trượt 2: Mịn da (0 - 100%, step 5, default 0%)
        l_s2 = QHBoxLayout()
        lbl_s2_name = QLabel("◉ Mịn da")
        lbl_s2_name.setStyleSheet("font-size: 14px; font-weight: 600; color: #303746;")
        self.lbl_s2_val = QLabel(f"{int(self._smooth_val)}%")
        self.lbl_s2_val.setStyleSheet("font-size: 14px; font-weight: bold; color: #1E40AF;")
        l_s2.addWidget(lbl_s2_name)
        l_s2.addStretch()
        l_s2.addWidget(self.lbl_s2_val)
        ctrl_vbox.addLayout(l_s2)

        self.slider_smooth = QSlider(Qt.Horizontal)
        self.slider_smooth.setRange(0, 100)
        self.slider_smooth.setSingleStep(5)
        self.slider_smooth.setPageStep(10)
        self.slider_smooth.setValue(int(self._smooth_val))
        self.slider_smooth.setStyleSheet(slider_style)
        self.slider_smooth.valueChanged.connect(self._on_slider_smooth_changed)
        ctrl_vbox.addWidget(self.slider_smooth)

        # Thanh trượt 3: Son môi (0 - 100%, step 5, default 0%)
        l_s3 = QHBoxLayout()
        lbl_s3_name = QLabel("💄 Son môi")
        lbl_s3_name.setStyleSheet("font-size: 14px; font-weight: 600; color: #303746;")
        self.lbl_s3_val = QLabel(f"{int(self._lips_val)}%")
        self.lbl_s3_val.setStyleSheet("font-size: 14px; font-weight: bold; color: #1E40AF;")
        l_s3.addWidget(lbl_s3_name)
        l_s3.addStretch()
        l_s3.addWidget(self.lbl_s3_val)
        ctrl_vbox.addLayout(l_s3)

        self.slider_lips = QSlider(Qt.Horizontal)
        self.slider_lips.setRange(0, 100)
        self.slider_lips.setSingleStep(5)
        self.slider_lips.setPageStep(10)
        self.slider_lips.setValue(int(self._lips_val))
        self.slider_lips.setStyleSheet(slider_style)
        self.slider_lips.valueChanged.connect(self._on_slider_lips_changed)
        ctrl_vbox.addWidget(self.slider_lips)

        ctrl_vbox.addSpacing(10)

        # Checkbox tái sử dụng cài đặt
        self.chk_reuse = QCheckBox("Giữ thiết lập này cho các ảnh tiếp theo")
        self.chk_reuse.setChecked(self.reuse_for_next)
        ctrl_vbox.addWidget(self.chk_reuse)

        ctrl_vbox.addStretch()

        # HÀNG NÚT THAO TÁC (Đặt lại, Xem ảnh gốc, Xác nhận)
        btn_box = QVBoxLayout()
        btn_box.setSpacing(10)

        h_sub_btns = QHBoxLayout()
        h_sub_btns.setSpacing(10)

        self.btn_reset = QPushButton("🔄 Đặt Lại")
        self.btn_reset.setStyleSheet(
            "QPushButton { background-color: #F8FAFC; color: #303746; border: 1.5px solid #D9DEE7; "
            "border-radius: 10px; padding: 10px 14px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background-color: #FFFFFF; border-color: #D4AF37; color: #D4AF37; }"
            "QPushButton:pressed { background-color: #E2E8F0; }"
        )
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        h_sub_btns.addWidget(self.btn_reset)

        self.btn_compare = QPushButton("👁 Xem Ảnh Gốc")
        self.btn_compare.setCheckable(True)
        self.btn_compare.setStyleSheet(
            "QPushButton { background-color: #F8FAFC; color: #303746; border: 1.5px solid #D9DEE7; "
            "border-radius: 10px; padding: 10px 14px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background-color: #FFFFFF; border-color: #0284C7; color: #0284C7; }"
            "QPushButton:checked { background-color: #EFF6FF; border-color: #3B82F6; color: #1E40AF; }"
            "QPushButton:pressed { background-color: #E2E8F0; }"
        )
        self.btn_compare.toggled.connect(self._on_compare_toggled)
        h_sub_btns.addWidget(self.btn_compare)

        btn_box.addLayout(h_sub_btns)

        # Nút xác nhận khổng lồ vàng Champagne
        self.btn_confirm = QPushButton("✓ Xác Nhận & Tiếp Tục")
        self.btn_confirm.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D4AF37, stop:1 #F5DE88); "
            "color: #0F172A; font-size: 16px; font-weight: 900; border: none; border-radius: 12px; "
            "padding: 14px 20px; }"
            "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FDE68A, stop:1 #D4AF37); }"
            "QPushButton:pressed { background: #B38F24; }"
        )
        self.btn_confirm.clicked.connect(self._on_confirm_clicked)
        btn_box.addWidget(self.btn_confirm)

        ctrl_vbox.addLayout(btn_box)

        content_layout.addWidget(ctrl_card, stretch=35)
        main_layout.addLayout(content_layout)

    def _reset_timeout(self):
        """Khởi động lại đồng hồ đếm ngược mỗi khi người dùng tương tác."""
        self._remaining_sec = max(20, self.auto_timeout_sec)
        self.lbl_countdown.setText(f"Tự động tiếp tục sau: {self._remaining_sec}s")

    def _on_timeout_tick(self):
        self._remaining_sec -= 1
        if self._remaining_sec <= 0:
            self._timeout_timer.stop()
            self._on_confirm_clicked()
        else:
            self.lbl_countdown.setText(f"Tự động tiếp tục sau: {self._remaining_sec}s")

    def _on_slider_brighten_changed(self, val: int):
        val = int(round(val / 5.0) * 5)
        self._brighten_val = float(val)
        self.lbl_s1_val.setText(f"{val}%")
        self._reset_timeout()
        self._request_render()

    def _on_slider_smooth_changed(self, val: int):
        val = int(round(val / 5.0) * 5)
        self._smooth_val = float(val)
        self.lbl_s2_val.setText(f"{val}%")
        self._reset_timeout()
        self._request_render()

    def _on_slider_lips_changed(self, val: int):
        val = int(round(val / 5.0) * 5)
        self._lips_val = float(val)
        self.lbl_s3_val.setText(f"{val}%")
        self._reset_timeout()
        self._request_render()

    def _on_reset_clicked(self):
        self._reset_timeout()
        self.slider_brighten.setValue(0)
        self.slider_smooth.setValue(0)
        self.slider_lips.setValue(0)
        self._brighten_val = 0.0
        self._smooth_val = 0.0
        self._lips_val = 0.0
        self._update_preview_display(self._preview_bgr)

    def _on_compare_toggled(self, checked: bool):
        self._showing_original = checked
        self._reset_timeout()
        if checked:
            self._update_preview_display(self._preview_bgr)
            self.btn_compare.setText("👁 Đang Xem Gốc")
        else:
            self._update_preview_display(self._current_preview_bgr)
            self.btn_compare.setText("👁 Xem Ảnh Gốc")

    def _request_render(self):
        if self._showing_original:
            return

        if self._brighten_val <= 0.01 and self._smooth_val <= 0.01 and self._lips_val <= 0.01:
            self._current_preview_bgr = self._preview_bgr.copy()
            self._update_preview_display(self._preview_bgr)
            return

        self._req_id += 1
        self._worker.update_params(
            self._req_id,
            self._preview_bgr,
            self._preview_faces,
            self._brighten_val,
            self._smooth_val,
            self._lips_val
        )

    def _on_preview_ready(self, req_id: int, processed_bgr: np.ndarray):
        if req_id != self._req_id or self._showing_original:
            return

        self._current_preview_bgr = processed_bgr
        self._update_preview_display(processed_bgr)

    def _update_preview_display(self, bgr_img: np.ndarray):
        if bgr_img is None or bgr_img.size == 0:
            return

        h, w = bgr_img.shape[:2]
        rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
        bytes_per_line = 3 * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(qimg)
        # Scaled to viewport preserving aspect ratio
        view_size = self.lbl_viewport.size()
        if view_size.width() > 10 and view_size.height() > 10:
            scaled = pixmap.scaled(view_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_viewport.setPixmap(scaled)
        else:
            self.lbl_viewport.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Tự động scale lại preview theo kích thước mới của khung hình
        cur = self._preview_bgr if self._showing_original else self._current_preview_bgr
        self._update_preview_display(cur)

    def _on_confirm_clicked(self):
        """Xử lý xác nhận: áp dụng thông số lên ảnh gốc chất lượng cao đầy đủ."""
        self._timeout_timer.stop()

        # Dừng worker
        if self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(300)

        # Tính toán ảnh làm đẹp ở độ phân giải gốc đầy đủ
        if self._brighten_val <= 0.01 and self._smooth_val <= 0.01 and self._lips_val <= 0.01:
            # Nguyên bản byte-for-byte
            final_pil = self._original_pil.copy()
        else:
            # Xử lý trên ảnh gốc độ phân giải cao
            try:
                final_bgr = self.engine.apply_beauty(
                    self._full_bgr,
                    skin_brighten_pct=self._brighten_val,
                    skin_smooth_pct=self._smooth_val,
                    lip_tint_pct=self._lips_val,
                    faces=self._full_faces
                )
                final_rgb = cv2.cvtColor(final_bgr, cv2.COLOR_BGR2RGB)
                final_pil = Image.fromarray(final_rgb)
            except Exception as ex:
                logger.error("Lỗi khi áp dụng làm đẹp lên ảnh gốc đầy đủ: %s", ex)
                final_pil = self._original_pil.copy()

        self._final_pil_result = final_pil
        settings = {
            "brighten": self._brighten_val,
            "smooth": self._smooth_val,
            "lips": self._lips_val
        }
        reuse = self.chk_reuse.isChecked()

        self.beauty_confirmed.emit(final_pil, settings, reuse)
        self.accept()

    def get_result(self) -> Tuple[Image.Image, Dict[str, float], bool]:
        """Trả về (final_pil_image, settings, reuse_flag)."""
        settings = {
            "brighten": self._brighten_val,
            "smooth": self._smooth_val,
            "lips": self._lips_val
        }
        return self._final_pil_result, settings, self.chk_reuse.isChecked()

    def closeEvent(self, event):
        self._timeout_timer.stop()
        if self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(300)
        super().closeEvent(event)
