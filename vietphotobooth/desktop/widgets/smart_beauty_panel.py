"""
1998 TEAM — Smart Beauty Panel (Luxury Beauty Studio Control Panel + MediaPipe 478 Landmarks)
Thiết kế lại khu vực điều chỉnh làm đẹp theo phong cách Beauty Studio cao cấp:
- Bố cục 2 cột: 68% Xem trước ảnh studio (với nút bật/tắt Lưới 478 Điểm) / 32% Menu hiệu ứng Beauty Studio.
- Không còn chữ mô tả thừa hoặc nút BẬT/TẮT thô kiểu kỹ thuật.
- Mỗi hiệu ứng trong 7 vùng là một thẻ điều khiển tinh tế riêng:
  - Icon line-art đồng bộ phong cách + Tên hiệu ứng + % + Công tắc Toggle Switch mượt mà.
  - Thanh trượt cường độ ẩn gọn khi OFF và bung ra với animation mượt khi ON.
  - Tự động vừa vặn hoàn chỉnh trong kích thước 1382x725 không cần thanh cuộn.
- Giữ nguyên 100% MediaPipe Face Landmarker 478 điểm & thuật toán SmartBeautyEngine,
  không giới hạn thời gian và bảo toàn thiết lập sang ảnh kế tiếp.
"""

import os
import math
import tempfile
import logging
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
import cv2
from PIL import Image, ImageOps

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QFrame, QSizePolicy, QScrollArea, QAbstractButton,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, Signal, Property, QThread, QTimer, QSize, QPointF, QRectF,
    QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QPixmap, QImage, QColor, QPainter, QPen, QIcon, QPainterPath,
    QBrush, QGuiApplication
)

from vietphotobooth.filters.beauty_engine import SmartBeautyEngine, DEFAULT_ENABLED_EFFECTS
from vietphotobooth.filters.face_analysis import (
    FaceAnalysisResult,
    draw_face_mesh_overlay,
)
from vietphotobooth.desktop.styles import (
    FONT_FAMILY_PRIMARY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_SECONDARY,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_CHAMPAGNE, COLOR_CHAMPAGNE_LIGHT, COLOR_PALE_GOLD,
    COLOR_LIVEVIEW, COLOR_SUCCESS, COLOR_ERROR
)

logger = logging.getLogger(__name__)

# Mặc định hiển thị tại UI: 3 nhóm cơ bản bật sẵn để trượt nhanh, 4 vùng nâng cao gập gọn đến khi bật
DEFAULT_DIALOG_UI_ENABLED: Dict[str, bool] = {
    "brighten": True,
    "smooth": True,
    "lips": True,
    "eye_brighten": False,
    "cheek_rosy": False,
    "nose_highlight": False,
    "face_slim": False,
    "ai_enhance": False,
}


def _make_beauty_icon(kind: str, color: str = "#292B29", size: int = 18) -> QIcon:
    """Tạo bộ vector icon line-art Beauty Studio đồng nhất, sắc nét trên mọi độ phân giải HiDPI."""
    dpr = 2.0
    px_size = int(size * dpr)
    pixmap = QPixmap(px_size, px_size)
    pixmap.fill(Qt.transparent)
    pixmap.setDevicePixelRatio(dpr)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    qcolor = QColor(color)
    pen = QPen(qcolor, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    s = float(size)
    c = s / 2.0

    if kind == "sparkle":
        path = QPainterPath()
        r_out = s * 0.39
        r_in = s * 0.12
        pts = [
            QPointF(c, c - r_out), QPointF(c + r_in, c - r_in),
            QPointF(c + r_out, c), QPointF(c + r_in, c + r_in),
            QPointF(c, c + r_out), QPointF(c - r_in, c + r_in),
            QPointF(c - r_out, c), QPointF(c - r_in, c - r_in),
        ]
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        path.closeSubpath()
        painter.setBrush(QBrush(qcolor))
        painter.drawPath(path)
        painter.drawEllipse(QPointF(s * 0.80, s * 0.22), 1.2, 1.2)

    elif kind == "sun":
        painter.drawEllipse(QPointF(c, c), s * 0.19, s * 0.19)
        r1 = s * 0.30
        r2 = s * 0.41
        for i in range(8):
            ang = i * (math.pi / 4.0)
            painter.drawLine(
                QPointF(c + r1 * math.cos(ang), c + r1 * math.sin(ang)),
                QPointF(c + r2 * math.cos(ang), c + r2 * math.sin(ang)),
            )

    elif kind == "smooth":
        path = QPainterPath()
        path.moveTo(c, s * 0.15)
        path.cubicTo(s * 0.78, s * 0.45, s * 0.80, s * 0.83, c, s * 0.85)
        path.cubicTo(s * 0.20, s * 0.83, s * 0.22, s * 0.45, c, s * 0.15)
        painter.drawPath(path)
        painter.drawArc(QRectF(c - s * 0.15, c, s * 0.30, s * 0.28), 205 * 16, 80 * 16)

    elif kind == "eye_zone":
        eye = QPainterPath()
        eye.moveTo(s * 0.15, c - 1.0)
        eye.cubicTo(s * 0.34, s * 0.24, s * 0.66, s * 0.24, s * 0.85, c - 1.0)
        eye.cubicTo(s * 0.66, s * 0.64, s * 0.34, s * 0.64, s * 0.15, c - 1.0)
        painter.drawPath(eye)
        painter.drawEllipse(QPointF(c, c - 1.0), s * 0.09, s * 0.09)
        painter.drawArc(QRectF(s * 0.22, c + 0.5, s * 0.56, s * 0.30), 200 * 16, 140 * 16)

    elif kind == "cheek":
        painter.drawEllipse(QPointF(c - s * 0.17, c), s * 0.16, s * 0.15)
        painter.drawEllipse(QPointF(c + s * 0.17, c), s * 0.16, s * 0.15)

    elif kind == "nose":
        nose_p = QPainterPath()
        nose_p.moveTo(c - s * 0.07, s * 0.19)
        nose_p.lineTo(c - s * 0.13, s * 0.68)
        nose_p.cubicTo(c - s * 0.05, s * 0.79, c + s * 0.05, s * 0.79, c + s * 0.13, s * 0.68)
        nose_p.lineTo(c + s * 0.07, s * 0.19)
        painter.drawPath(nose_p)

    elif kind == "contour":
        jaw = QPainterPath()
        jaw.moveTo(s * 0.23, s * 0.22)
        jaw.cubicTo(s * 0.21, s * 0.62, s * 0.36, s * 0.81, c, s * 0.85)
        jaw.cubicTo(s * 0.64, s * 0.81, s * 0.79, s * 0.62, s * 0.77, s * 0.22)
        painter.drawPath(jaw)

    elif kind == "ai_portrait":
        # Biểu tượng ngôi sao 4 cánh tinh tế + 2 tia sáng nhỏ biểu trưng cho làm đẹp AI
        main_star = QPainterPath()
        r_out = s * 0.34
        r_in = s * 0.11
        cx_s, cy_s = c - s * 0.05, c + s * 0.04
        pts = [
            QPointF(cx_s, cy_s - r_out), QPointF(cx_s + r_in, cy_s - r_in),
            QPointF(cx_s + r_out, cy_s), QPointF(cx_s + r_in, cy_s + r_in),
            QPointF(cx_s, cy_s + r_out), QPointF(cx_s - r_in, cy_s + r_in),
            QPointF(cx_s - r_out, cy_s), QPointF(cx_s - r_in, cy_s - r_in),
        ]
        main_star.moveTo(pts[0])
        for p in pts[1:]:
            main_star.lineTo(p)
        main_star.closeSubpath()
        painter.drawPath(main_star)

        sx, sy = s * 0.78, s * 0.24
        r_m = s * 0.12
        painter.drawLine(QPointF(sx - r_m, sy), QPointF(sx + r_m, sy))
        painter.drawLine(QPointF(sx, sy - r_m), QPointF(sx, sy + r_m))

    elif kind == "lips":
        upper = QPainterPath()
        upper.moveTo(s * 0.15, c + 0.4)
        upper.cubicTo(s * 0.29, s * 0.27, s * 0.42, s * 0.31, c, s * 0.39)
        upper.cubicTo(s * 0.58, s * 0.31, s * 0.71, s * 0.27, s * 0.85, c + 0.4)
        upper.cubicTo(s * 0.68, c + 0.8, s * 0.32, c + 0.8, s * 0.15, c + 0.4)
        painter.drawPath(upper)

        lower = QPainterPath()
        lower.moveTo(s * 0.17, c + 0.6)
        lower.cubicTo(s * 0.34, s * 0.75, s * 0.66, s * 0.75, s * 0.83, c + 0.6)
        painter.drawPath(lower)

    elif kind == "reset":
        arc_rect = QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60)
        painter.drawArc(arc_rect, 45 * 16, 265 * 16)
        arrow = QPainterPath()
        arrow.moveTo(s * 0.20, s * 0.24)
        arrow.lineTo(s * 0.20, s * 0.44)
        arrow.lineTo(s * 0.38, s * 0.40)
        painter.drawPath(arrow)

    elif kind in ("eye", "eye_active"):
        eye = QPainterPath()
        eye.moveTo(s * 0.12, c)
        eye.cubicTo(s * 0.32, s * 0.22, s * 0.68, s * 0.22, s * 0.88, c)
        eye.cubicTo(s * 0.68, s * 0.78, s * 0.32, s * 0.78, s * 0.12, c)
        painter.drawPath(eye)
        if kind == "eye_active":
            painter.setBrush(QBrush(qcolor))
        painter.drawEllipse(QPointF(c, c), s * 0.13, s * 0.13)

    painter.end()
    return QIcon(pixmap)


def _ensure_checkmark_icon_path() -> str:
    """Tạo và lưu tạm icon dấu tích trắng sắc nét cho checkbox tái sử dụng."""
    path = os.path.join(tempfile.gettempdir(), "1998team_beauty_check_white.png")
    if not os.path.exists(path):
        px = QPixmap(28, 28)
        px.fill(Qt.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#FFFFFF"), 3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(QPointF(6.0, 14.5), QPointF(11.5, 20.0))
        painter.drawLine(QPointF(11.5, 20.0), QPointF(22.0, 8.0))
        painter.end()
        px.save(path, "PNG")
    return path.replace("\\", "/")


class ModernToggleSwitch(QAbstractButton):
    """
    Công tắc ON/OFF hiện đại dạng pill slider (QAbstractButton checkable).
    Tông vàng Champagne khi ON (#B99A63) và kem/xám ấm dịu nhẹ khi OFF (#D8D4CA).
    """

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(38, 20)
        self.setCursor(Qt.PointingHandCursor)

        self._thumb_pos: float = 1.0 if checked else 0.0
        self._hovered: bool = False

        self._anim = QPropertyAnimation(self, b"thumb_pos", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        self.toggled.connect(self._animate_to_state)

    def _get_thumb_pos(self) -> float:
        return self._thumb_pos

    def _set_thumb_pos(self, val: float):
        self._thumb_pos = val
        self.update()

    thumb_pos = Property(float, _get_thumb_pos, _set_thumb_pos)

    def _animate_to_state(self, checked: bool):
        target = 1.0 if checked else 0.0
        if not self.isVisible():
            self._anim.stop()
            self._thumb_pos = target
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        # Nội suy mượt giữa màu nền OFF (#D7D3C9) và Champagne ON (#B99A63)
        off_c = QColor("#D7D3C9" if not self._hovered else "#CCC7BC")
        on_c = QColor("#B99A63" if not self._hovered else "#AD8D56")
        t = max(0.0, min(1.0, self._thumb_pos))
        bg = QColor(
            int(off_c.red() + (on_c.red() - off_c.red()) * t),
            int(off_c.green() + (on_c.green() - off_c.green()) * t),
            int(off_c.blue() + (on_c.blue() - off_c.blue()) * t),
        )

        # Vẽ track bo tròn mềm
        painter.setPen(QPen(QColor("#C6C1B5" if t < 0.5 else "#9E824E"), 0.8))
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), radius, radius)

        # Nút tròn trắng di chuyển
        pad = 2.5
        thumb_d = h - 2.0 * pad
        travel = w - 2.0 * pad - thumb_d
        tx = pad + travel * t

        # Đổ bóng nhẹ cho nút tròn
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(41, 43, 41, 24))
        painter.drawEllipse(QRectF(tx, pad + 0.8, thumb_d, thumb_d))

        painter.setPen(QPen(QColor(255, 255, 255, 220), 0.5))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(tx, pad, thumb_d, thumb_d))
        painter.end()


class BeautyEffectCard(QFrame):
    """
    Thẻ điều khiển độc lập cho từng hiệu ứng Beauty Studio:
    - Dòng đầu: Icon + Tên hiệu ứng + Nhãn % (hiển thị khi bật) + ModernToggleSwitch.
    - Ngăn kéo bên dưới chứa thanh QSlider, có animation mở/đóng (height 0 <-> 20px).
    """

    SLIDER_DRAWER_HEIGHT = 20

    def __init__(
        self,
        key: str,
        icon_kind: str,
        active_color: str,
        title: str,
        initial_val: float,
        initial_enabled: bool,
        on_val_changed,
        on_toggled,
        parent=None,
    ):
        super().__init__(parent)
        self.key = key
        self._icon_kind = icon_kind
        self._active_color = active_color
        self._on_toggled_cb = on_toggled

        self.setObjectName("beauty_fx_card")
        self.setProperty("active", "true" if initial_enabled else "false")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Đổ bóng nhẹ sang trọng, không lạm dụng phát sáng
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(60, 52, 38, 18 if initial_enabled else 9))
        self.setGraphicsEffect(shadow)
        self._shadow = shadow

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(11, 3, 11, 3)
        vbox.setSpacing(0)

        # Dòng tiêu đề + % + Toggle Switch
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(18, 18)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        top_row.addWidget(self.lbl_icon)

        self.lbl_title = QLabel(title)
        top_row.addWidget(self.lbl_title)

        top_row.addStretch()

        val_int = int(round(initial_val))
        self.lbl_val = QLabel(f"{val_int}%")
        self.lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_val.setMinimumWidth(36)
        top_row.addWidget(self.lbl_val)

        self.toggle = ModernToggleSwitch(checked=initial_enabled)
        self.toggle.toggled.connect(self._handle_toggled)
        top_row.addWidget(self.toggle)

        vbox.addLayout(top_row)

        # Ngăn kéo thanh trượt (chỉ mở khi hiệu ứng bật, đóng mượt về 0 khi tắt)
        self.drawer = QWidget()
        self.drawer.setObjectName("beauty_fx_drawer")
        drawer_layout = QVBoxLayout(self.drawer)
        drawer_layout.setContentsMargins(0, 0, 0, 0)
        drawer_layout.setSpacing(0)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setObjectName("beauty_slider")
        self.slider.setRange(0, 100)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(5)
        self.slider.setValue(val_int)
        self.slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(on_val_changed)
        drawer_layout.addWidget(self.slider)

        self._drawer_anim = QPropertyAnimation(self.drawer, b"maximumHeight", self)
        self._drawer_anim.setDuration(185)
        self._drawer_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._drawer_anim.finished.connect(self._on_drawer_anim_finished)

        # Áp dụng trạng thái mở/đóng ngay lập tức ở lần khởi tạo đầu tiên
        if initial_enabled:
            self.drawer.setMaximumHeight(self.SLIDER_DRAWER_HEIGHT)
            self.drawer.setVisible(True)
        else:
            self.drawer.setMaximumHeight(0)
            self.drawer.setVisible(False)

        vbox.addWidget(self.drawer)
        self.refresh_visual_state(initial_enabled, val_int)

    def _on_drawer_anim_finished(self):
        if not self.toggle.isChecked():
            self.drawer.setVisible(False)

    def _animate_drawer(self, expand: bool):
        if not self.isVisible():
            self._drawer_anim.stop()
            if expand:
                self.drawer.setVisible(True)
                self.drawer.setMaximumHeight(self.SLIDER_DRAWER_HEIGHT)
            else:
                self.drawer.setMaximumHeight(0)
                self.drawer.setVisible(False)
            return

        self._drawer_anim.stop()
        if expand:
            self.drawer.setVisible(True)
            self._drawer_anim.setStartValue(max(0, self.drawer.maximumHeight()))
            self._drawer_anim.setEndValue(self.SLIDER_DRAWER_HEIGHT)
        else:
            self._drawer_anim.setStartValue(self.drawer.height())
            self._drawer_anim.setEndValue(0)
        self._drawer_anim.start()

    def _handle_toggled(self, checked: bool):
        self._animate_drawer(checked)
        self.refresh_visual_state(checked, self.slider.value())
        if self._on_toggled_cb:
            self._on_toggled_cb(self.key, checked)

    def refresh_visual_state(self, is_enabled: bool, val_int: int):
        icon_col = self._active_color if is_enabled else "#9A958B"
        self.lbl_icon.setPixmap(_make_beauty_icon(self._icon_kind, icon_col, 17).pixmap(17, 17))

        title_col = COLOR_TEXT_PRIMARY if is_enabled else "#7D786E"
        title_weight = "700" if is_enabled else "600"
        self.lbl_title.setStyleSheet(
            f"font-size: 12.5px; font-weight: {title_weight}; color: {title_col}; "
            "border: none; background: transparent;"
        )

        if is_enabled:
            self.lbl_val.setText(f"{val_int}%")
            self.lbl_val.setVisible(True)
            val_col = COLOR_CHAMPAGNE if val_int > 0 else "#8F8A7F"
            self.lbl_val.setStyleSheet(
                f"font-size: 12px; font-weight: 800; color: {val_col}; "
                "border: none; background: transparent;"
            )
            self._shadow.setColor(QColor(60, 52, 38, 18))
            self.setProperty("active", "true")
        else:
            self.lbl_val.setVisible(False)
            self._shadow.setColor(QColor(60, 52, 38, 7))
            self.setProperty("active", "false")

        self.style().unpolish(self)
        self.style().polish(self)


class BeautyPreviewWorker(QThread):
    """Worker render preview ảnh làm đẹp đa vùng trong luồng nền không chặn UI."""
    preview_ready = Signal(int, np.ndarray)  # req_id, processed_bgr

    def __init__(self, engine: SmartBeautyEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._preview_bgr: Optional[np.ndarray] = None
        self._faces: List[Any] = []
        self._brighten = 0.0
        self._smooth = 0.0
        self._lips = 0.0
        self._eye_brighten = 0.0
        self._cheek_rosy = 0.0
        self._nose_highlight = 0.0
        self._face_slim = 0.0
        self._ai_enhance = 0.0
        self._enabled_effects: Dict[str, bool] = dict(DEFAULT_ENABLED_EFFECTS)
        self._req_id = 0
        self._pending = False
        self._running = True

    def update_params(
        self,
        req_id: int,
        preview_bgr: np.ndarray,
        faces: List[Any],
        brighten: float,
        smooth: float,
        lips: float,
        eye_brighten: float = 0.0,
        cheek_rosy: float = 0.0,
        nose_highlight: float = 0.0,
        face_slim: float = 0.0,
        enabled_effects: Optional[Dict[str, bool]] = None,
        ai_enhance: float = 0.0,
    ):
        self._req_id = req_id
        self._preview_bgr = preview_bgr
        self._faces = faces
        self._brighten = brighten
        self._smooth = smooth
        self._lips = lips
        self._eye_brighten = eye_brighten
        self._cheek_rosy = cheek_rosy
        self._nose_highlight = nose_highlight
        self._face_slim = face_slim
        self._ai_enhance = ai_enhance
        self._enabled_effects = dict(enabled_effects) if enabled_effects else dict(DEFAULT_ENABLED_EFFECTS)
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
                cur_b = self._brighten
                cur_s = self._smooth
                cur_l = self._lips
                cur_e = self._eye_brighten
                cur_c = self._cheek_rosy
                cur_n = self._nose_highlight
                cur_sl = self._face_slim
                cur_ai = self._ai_enhance
                cur_eff = dict(self._enabled_effects)

                try:
                    res_bgr = self.engine.apply_beauty(
                        cur_bgr,
                        skin_brighten_pct=cur_b,
                        skin_smooth_pct=cur_s,
                        lip_tint_pct=cur_l,
                        faces=cur_faces,
                        eye_brighten_pct=cur_e,
                        cheek_rosy_pct=cur_c,
                        nose_highlight_pct=cur_n,
                        face_slim_pct=cur_sl,
                        enabled_effects=cur_eff,
                        ai_enhance_pct=cur_ai,
                    )
                    if not self.isInterruptionRequested() and cur_req == self._req_id:
                        self.preview_ready.emit(cur_req, res_bgr)
                except Exception as ex:
                    logger.error("Lỗi trong BeautyPreviewWorker: %s", ex)

            self.msleep(15)


class SmartBeautyDialog(QDialog):
    """
    Hộp thoại làm đẹp Beauty Studio (MediaPipe 478 Landmarks).
    Bố cục 2 cột: 68% xem trước ảnh studio / 32% menu làm đẹp cao cấp gọn gàng.
    """

    beauty_confirmed = Signal(object, dict, bool)  # PIL.Image, settings_dict, reuse_flag

    def __init__(
        self,
        image_pil_or_path: Any,
        shot_index: int = 1,
        total_shots: int = 1,
        initial_settings: Optional[Dict[str, float]] = None,
        initial_enabled_effects: Optional[Dict[str, bool]] = None,
        reuse_for_next: bool = False,
        auto_timeout_sec: Optional[int] = None,
        engine: Optional[SmartBeautyEngine] = None,
        developer_mode: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.shot_index = shot_index
        self.total_shots = total_shots
        self.auto_timeout_sec = 0
        self.reuse_for_next = reuse_for_next
        self._owns_engine = engine is None
        self.engine = engine or SmartBeautyEngine()
        self._developer_mode = bool(developer_mode)

        # Tải ảnh gốc (bảo toàn ảnh gốc trên đĩa & chuẩn hóa EXIF)
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

        # Ảnh trung gian để xử lý (tuyệt đối không ghi trực tiếp lên ảnh gốc)
        rgb_arr = np.array(self._original_pil.convert("RGB"))
        self._full_bgr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        h, w = self._full_bgr.shape[:2]
        if max(h, w) <= 1080:
            self._scale_to_preview = 1.0
            self._preview_bgr = self._full_bgr.copy()
        else:
            self._scale_to_preview = 1080.0 / float(max(h, w))
            nw = max(1, int(w * self._scale_to_preview))
            nh = max(1, int(h * self._scale_to_preview))
            self._preview_bgr = cv2.resize(self._full_bgr, (nw, nh), interpolation=cv2.INTER_AREA)

        self._analysis_result: FaceAnalysisResult = self.engine.analyze_faces(self._preview_bgr, is_bgr=True)
        self._preview_faces: List[Any] = list(self._analysis_result.faces)
        self._full_faces: List[Any] = self.engine.map_faces_to_scale(
            self._preview_faces, 1.0 / self._scale_to_preview if self._scale_to_preview > 0 else 1.0
        )

        # Trạng thái thông số làm đẹp & công tắc bật/tắt từng hiệu ứng
        init_s = initial_settings or {}
        self._brighten_val = float(init_s.get("brighten", 0.0))
        self._smooth_val = float(init_s.get("smooth", 0.0))
        self._lips_val = float(init_s.get("lips", 0.0))
        self._eye_brighten_val = float(init_s.get("eye_brighten", 0.0))
        self._cheek_rosy_val = float(init_s.get("cheek_rosy", 0.0))
        self._nose_highlight_val = float(init_s.get("nose_highlight", 0.0))
        self._face_slim_val = float(init_s.get("face_slim", 0.0))
        self._ai_enhance_val = float(init_s.get("ai_enhance", 0.0))

        self._enabled_effects: Dict[str, bool] = dict(DEFAULT_DIALOG_UI_ENABLED)
        if initial_enabled_effects is not None:
            self._enabled_effects.update(initial_enabled_effects)
        else:
            # Nếu truyền giá trị cường độ > 0 từ preset trước, tự động mở thẻ tương ứng
            for k, val in (
                ("brighten", self._brighten_val),
                ("smooth", self._smooth_val),
                ("lips", self._lips_val),
                ("eye_brighten", self._eye_brighten_val),
                ("cheek_rosy", self._cheek_rosy_val),
                ("nose_highlight", self._nose_highlight_val),
                ("face_slim", self._face_slim_val),
                ("ai_enhance", self._ai_enhance_val),
            ):
                if val > 0.01:
                    self._enabled_effects[k] = True

        self._showing_original = False
        self._show_mesh_overlay = False
        self._current_preview_bgr = self._preview_bgr.copy()
        self._req_id = 0
        self._final_pil_result = self._original_pil

        self._init_window()
        self._init_ui()

        self._worker = BeautyPreviewWorker(self.engine, self)
        self._worker.preview_ready.connect(self._on_preview_ready)
        self._worker.start()

        if self._has_any_active_effect():
            self._request_render()
        else:
            self._refresh_current_preview()

    def _has_any_active_effect(self) -> bool:
        vals = {
            "brighten": self._brighten_val,
            "smooth": self._smooth_val,
            "lips": self._lips_val,
            "eye_brighten": self._eye_brighten_val,
            "cheek_rosy": self._cheek_rosy_val,
            "nose_highlight": self._nose_highlight_val,
            "face_slim": self._face_slim_val,
            "ai_enhance": self._ai_enhance_val,
        }
        return any(v > 0.01 and self._enabled_effects.get(k, True) for k, v in vals.items())

    def _init_window(self):
        self.setObjectName("smart_beauty_dialog")
        self.setWindowTitle("1998 TEAM — Smart Beauty Studio")
        self.setModal(True)
        self.setMinimumSize(960, 620)

        parent_win = self.parentWidget().window() if self.parentWidget() is not None else None
        if parent_win is not None and parent_win.width() >= 960 and parent_win.height() >= 600:
            avail_w, avail_h = parent_win.width(), parent_win.height()
        else:
            screen = QGuiApplication.primaryScreen()
            geo = screen.availableGeometry() if screen is not None else None
            avail_w = geo.width() if geo else 1440
            avail_h = geo.height() if geo else 900

        target_w = max(960, min(int(avail_w * 0.90), avail_w - 32))
        target_h = max(620, min(int(avail_h * 0.88), avail_h - 32))
        self.resize(target_w, target_h)

        chk_icon_url = _ensure_checkmark_icon_path()
        self.setStyleSheet(f"""
            QDialog#smart_beauty_dialog {{
                background-color: {COLOR_BG};
                border: 1px solid #DFDCD4;
                border-radius: 16px;
                font-family: {FONT_FAMILY_PRIMARY};
            }}
            QDialog#smart_beauty_dialog QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                border: none;
                background: transparent;
            }}
            QFrame#beauty_preview_container {{
                background-color: {COLOR_LIVEVIEW};
                border: 1.5px solid #2D3036;
                border-radius: 16px;
            }}
            QDialog#smart_beauty_dialog QLabel#beauty_viewport {{
                background: transparent;
                border: none;
            }}
            QDialog#smart_beauty_dialog QLabel#beauty_compare_pill {{
                background-color: rgba(255, 255, 255, 0.09);
                color: #EDEAE2;
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 10px;
                padding: 4px 12px;
                font-size: 11.5px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }}
            QPushButton#btn_beauty_mesh_pill {{
                background-color: rgba(255, 255, 255, 0.08);
                color: #D9D5CC;
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 10px;
                padding: 4px 12px;
                font-size: 11.5px;
                font-weight: 600;
            }}
            QPushButton#btn_beauty_mesh_pill:hover {{
                background-color: rgba(255, 255, 255, 0.16);
                border-color: {COLOR_CHAMPAGNE};
            }}
            QPushButton#btn_beauty_mesh_pill:checked {{
                background-color: rgba(185, 154, 99, 0.28);
                border: 1px solid rgba(208, 188, 148, 0.80);
                color: #F4E6C3;
                font-weight: 700;
            }}
            QFrame#beauty_ctrl_card {{
                background-color: #FCFBF8;
                border: 1px solid #E4DFD4;
                border-radius: 16px;
            }}
            QScrollArea#beauty_sliders_scroll, QWidget#beauty_sliders_viewport {{
                background: transparent;
                border: none;
            }}
            QFrame#beauty_fx_card {{
                background-color: #F5F3ED;
                border: 1px solid #E7E3D9;
                border-radius: 11px;
            }}
            QFrame#beauty_fx_card:hover {{
                border-color: #D4C5A8;
            }}
            QFrame#beauty_fx_card[active="true"] {{
                background-color: #FFFFFF;
                border: 1px solid #DDD1B8;
            }}
            QFrame#beauty_fx_card[active="true"]:hover {{
                border: 1px solid {COLOR_CHAMPAGNE};
            }}
            QWidget#beauty_fx_drawer {{
                background: transparent;
                border: none;
            }}
            QFrame#beauty_reuse_card {{
                background-color: #F6F4EE;
                border: 1px solid #EAE6DC;
                border-radius: 10px;
            }}
            QFrame#beauty_divider {{
                background-color: #ECE8DF;
                border: none;
                min-height: 1px;
                max-height: 1px;
            }}
            QSlider#beauty_slider {{
                background: transparent;
                border: none;
                min-height: 20px;
                max-height: 20px;
            }}
            QSlider#beauty_slider::groove:horizontal {{
                border: none;
                height: 6px;
                background: #E6E2D8;
                border-radius: 3px;
            }}
            QSlider#beauty_slider::sub-page:horizontal {{
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT});
                border-radius: 3px;
            }}
            QSlider#beauty_slider::handle:horizontal {{
                background: #FFFFFF;
                border: 2px solid {COLOR_CHAMPAGNE};
                width: 14px;
                height: 14px;
                margin: -6px 0px;
                border-radius: 9px;
            }}
            QSlider#beauty_slider::handle:horizontal:hover {{
                background: #FBF6EC;
                border: 2px solid #967B49;
            }}
            QCheckBox#beauty_reuse_chk {{
                color: {COLOR_TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 600;
                spacing: 9px;
                border: none;
                background: transparent;
                padding: 1px 0px;
            }}
            QCheckBox#beauty_reuse_chk::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1.5px solid #C7C3B8;
                background-color: #FFFFFF;
            }}
            QCheckBox#beauty_reuse_chk::indicator:hover {{
                border-color: {COLOR_CHAMPAGNE};
            }}
            QCheckBox#beauty_reuse_chk::indicator:checked {{
                background-color: {COLOR_CHAMPAGNE};
                border-color: #967B49;
                image: url("{chk_icon_url}");
            }}
            QPushButton#btn_beauty_secondary {{
                background-color: #FFFFFF;
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid #DBD7CC;
                border-radius: 10px;
                padding: 6px 12px;
                font-size: 12.5px;
                font-weight: 700;
            }}
            QPushButton#btn_beauty_secondary:hover {{
                background-color: #F4F1EA;
                border-color: {COLOR_CHAMPAGNE};
            }}
            QPushButton#btn_beauty_secondary:pressed {{
                background-color: #E7E3D9;
            }}
            QPushButton#btn_beauty_compare {{
                background-color: #FFFFFF;
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid #DBD7CC;
                border-radius: 10px;
                padding: 6px 12px;
                font-size: 12.5px;
                font-weight: 700;
            }}
            QPushButton#btn_beauty_compare:hover {{
                background-color: #F4F1EA;
                border-color: {COLOR_CHAMPAGNE};
            }}
            QPushButton#btn_beauty_compare:checked {{
                background-color: {COLOR_PALE_GOLD};
                border: 1px solid {COLOR_CHAMPAGNE};
                color: #6B5326;
            }}
            QPushButton#btn_beauty_compare:pressed {{
                background-color: #E7E3D9;
            }}
            QPushButton#btn_beauty_confirm {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #AD905B, stop:1 #C7AA73);
                color: #FFFFFF;
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 0.3px;
                border: 1px solid #8A703F;
                border-radius: 11px;
                padding: 10px 16px;
            }}
            QPushButton#btn_beauty_confirm:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #BC9E68, stop:1 #D4B77E);
            }}
            QPushButton#btn_beauty_confirm:pressed {{
                background: #8A703F;
            }}
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 14, 20, 14)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 1. HEADER BAR: Tiêu đề, Huy hiệu tiến độ, Trạng thái phân tích MediaPipe
        # -------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        lbl_title_icon = QLabel()
        lbl_title_icon.setFixedSize(24, 24)
        lbl_title_icon.setAlignment(Qt.AlignCenter)
        lbl_title_icon.setPixmap(_make_beauty_icon("sparkle", COLOR_CHAMPAGNE, 20).pixmap(20, 20))
        header_layout.addWidget(lbl_title_icon)

        lbl_title = QLabel("ẢNH VỪA CHỤP")
        lbl_title.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {COLOR_TEXT_PRIMARY}; "
            "letter-spacing: 0.6px; border: none; background: transparent;"
        )
        header_layout.addWidget(lbl_title)

        header_layout.addSpacing(4)

        self.lbl_progress = QLabel(f"Đã chụp {self.shot_index}/{self.total_shots}")
        self.lbl_progress.setStyleSheet(
            f"background-color: #EFECE4; color: {COLOR_TEXT_PRIMARY}; "
            "font-size: 12.5px; font-weight: 700; border: 1px solid #DDD9CF; "
            "padding: 4px 12px; border-radius: 12px;"
        )
        header_layout.addWidget(self.lbl_progress)

        num_faces = len(self._preview_faces)
        if self._developer_mode:
            if not self.engine.is_available:
                status_text = "• Phân Tích Khuôn Mặt Không Khả Dụng"
                status_style = f"background-color: #FDECEB; color: {COLOR_ERROR}; border: 1px solid #F3B8B5;"
            elif num_faces == 0:
                status_text = "• Không Phát Hiện Khuôn Mặt (Giữ nguyên ảnh)"
                status_style = f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid #DCD9D0;"
            elif self._analysis_result.source == "mediapipe_face_landmarker":
                pts = self._preview_faces[0].landmark_count
                ai_tag = "AI Ready" if self.engine.is_ai_available else "AI Off"
                status_text = f"✓ MediaPipe {pts} Điểm · {num_faces} Khuôn Mặt · {ai_tag}"
                status_style = f"background-color: #E7F2EB; color: {COLOR_SUCCESS}; border: 1px solid #B5D8C2;"
            else:
                status_text = f"✓ Nhận Diện {num_faces} Khuôn Mặt (Fallback)"
                status_style = f"background-color: #E7F2EB; color: {COLOR_SUCCESS}; border: 1px solid #B5D8C2;"
        else:
            # Giao diện khách hàng: thân thiện, tối giản, không hiển thị thuật ngữ kỹ thuật
            if not self.engine.is_available:
                status_text = "• Chế Độ Chỉnh Tay"
                status_style = f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid #DCD9D0;"
            elif num_faces == 0:
                status_text = "• Không Phát Hiện Khuôn Mặt (Giữ nguyên ảnh)"
                status_style = f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid #DCD9D0;"
            elif num_faces == 1:
                status_text = "✓ Sẵn Sàng Làm Đẹp · 1 Khuôn Mặt"
                status_style = f"background-color: #E7F2EB; color: {COLOR_SUCCESS}; border: 1px solid #B5D8C2;"
            else:
                status_text = f"✓ Sẵn Sàng Làm Đẹp · {num_faces} Khuôn Mặt"
                status_style = f"background-color: #E7F2EB; color: {COLOR_SUCCESS}; border: 1px solid #B5D8C2;"

        self.lbl_face_status = QLabel(status_text)
        self.lbl_face_status.setStyleSheet(
            f"{status_style} font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 12px;"
        )
        header_layout.addWidget(self.lbl_face_status)

        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # -------------------------------------------------------------
        # 2. KHU VỰC CHÍNH: Preview Bên Trái (68%), Beauty Studio Menu Bên Phải (32%)
        # -------------------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # CỘT TRÁI — KHUNG XEM TRƯỚC STUDIO (68%, không thanh kỹ thuật thừa để ảnh rộng tối đa)
        self.preview_container = QFrame()
        self.preview_container.setObjectName("beauty_preview_container")
        preview_vbox = QVBoxLayout(self.preview_container)
        preview_vbox.setContentsMargins(12, 10 if self._developer_mode else 12, 12, 12)
        preview_vbox.setSpacing(6 if self._developer_mode else 0)

        if self._developer_mode:
            preview_top_row = QHBoxLayout()
            preview_top_row.setContentsMargins(0, 0, 0, 0)
            preview_top_row.setSpacing(10)
            preview_top_row.addStretch()

            self.btn_toggle_mesh = QPushButton("Lưới 478 Điểm")
            self.btn_toggle_mesh.setObjectName("btn_beauty_mesh_pill")
            self.btn_toggle_mesh.setCheckable(True)
            self.btn_toggle_mesh.setCursor(Qt.PointingHandCursor)
            self.btn_toggle_mesh.setEnabled(num_faces > 0)
            self.btn_toggle_mesh.toggled.connect(self._on_mesh_toggled)
            preview_top_row.addWidget(self.btn_toggle_mesh)

            preview_vbox.addLayout(preview_top_row)

        self.lbl_viewport = QLabel()
        self.lbl_viewport.setObjectName("beauty_viewport")
        self.lbl_viewport.setAlignment(Qt.AlignCenter)
        self.lbl_viewport.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.lbl_viewport.setMinimumSize(420, 360)
        preview_vbox.addWidget(self.lbl_viewport, stretch=1)

        content_layout.addWidget(self.preview_container, stretch=68)

        # CỘT PHẢI — BEAUTY STUDIO MENU HIỆN ĐẠI (32%)
        self.ctrl_card = QFrame()
        self.ctrl_card.setObjectName("beauty_ctrl_card")
        self.ctrl_card.setMinimumWidth(360)
        ctrl_vbox = QVBoxLayout(self.ctrl_card)
        ctrl_vbox.setContentsMargins(15, 8, 15, 8)
        ctrl_vbox.setSpacing(4)

        # Tiêu đề sạch sẽ (đã loại bỏ mô tả chữ nhỏ kỹ thuật bên dưới)
        lbl_ctrl_title = QLabel("TÙY CHỈNH LÀM ĐẸP TỰ NHIÊN")
        lbl_ctrl_title.setWordWrap(True)
        lbl_ctrl_title.setStyleSheet(
            f"font-size: 14px; font-weight: 800; color: {COLOR_TEXT_PRIMARY}; "
            "letter-spacing: 0.5px; border: none; background: transparent; padding-bottom: 1px;"
        )
        ctrl_vbox.addWidget(lbl_ctrl_title)

        divider_top = QFrame()
        divider_top.setObjectName("beauty_divider")
        ctrl_vbox.addWidget(divider_top)

        # Danh sách 8 thẻ hiệu ứng gọn gàng (tối ưu vừa vặn khung 1382x725 không cần cuộn)
        sliders_scroll = QScrollArea()
        sliders_scroll.setObjectName("beauty_sliders_scroll")
        sliders_scroll.setWidgetResizable(True)
        sliders_scroll.setFrameShape(QFrame.NoFrame)
        sliders_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sliders_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        sliders_host = QWidget()
        sliders_host.setObjectName("beauty_sliders_viewport")
        sliders_vbox = QVBoxLayout(sliders_host)
        sliders_vbox.setContentsMargins(1, 0, 1, 0)
        sliders_vbox.setSpacing(3)

        self._effect_cards: Dict[str, BeautyEffectCard] = {}

        # Nhóm 1: Làn da
        sliders_vbox.addWidget(self._make_section_label("LÀN DA"))

        c_b = self._create_effect_card(
            key="brighten", icon_kind="sun", icon_color=COLOR_CHAMPAGNE,
            title="Sáng da mặt", initial_val=self._brighten_val,
            on_val_changed=self._on_slider_brighten_changed,
        )
        self.slider_brighten, self.lbl_s1_val, self.btn_toggle_brighten = c_b.slider, c_b.lbl_val, c_b.toggle
        sliders_vbox.addWidget(c_b)

        c_s = self._create_effect_card(
            key="smooth", icon_kind="smooth", icon_color=COLOR_CHAMPAGNE,
            title="Mịn da & đều trán", initial_val=self._smooth_val,
            on_val_changed=self._on_slider_smooth_changed,
        )
        self.slider_smooth, self.lbl_s2_val, self.btn_toggle_smooth = c_s.slider, c_s.lbl_val, c_s.toggle
        sliders_vbox.addWidget(c_s)

        # Nhóm 2: Đường nét & sắc thái khuôn mặt
        lbl_grp2 = self._make_section_label("ĐƯỜNG NÉT & SẮC THÁI")
        lbl_grp2.setContentsMargins(2, 2, 0, 0)
        sliders_vbox.addWidget(lbl_grp2)

        c_e = self._create_effect_card(
            key="eye_brighten", icon_kind="eye_zone", icon_color="#9C824E",
            title="Giảm quầng thâm mắt", initial_val=self._eye_brighten_val,
            on_val_changed=lambda val: self._on_region_slider_changed("eye_brighten", val),
        )
        self.slider_eye, self.lbl_eye_val, self.btn_toggle_eye = c_e.slider, c_e.lbl_val, c_e.toggle
        sliders_vbox.addWidget(c_e)

        c_c = self._create_effect_card(
            key="cheek_rosy", icon_kind="cheek", icon_color="#C97A7E",
            title="Hồng má & cân bằng", initial_val=self._cheek_rosy_val,
            on_val_changed=lambda val: self._on_region_slider_changed("cheek_rosy", val),
        )
        self.slider_cheek, self.lbl_cheek_val, self.btn_toggle_cheek = c_c.slider, c_c.lbl_val, c_c.toggle
        sliders_vbox.addWidget(c_c)

        c_n = self._create_effect_card(
            key="nose_highlight", icon_kind="nose", icon_color=COLOR_CHAMPAGNE,
            title="Ánh sáng sống mũi", initial_val=self._nose_highlight_val,
            on_val_changed=lambda val: self._on_region_slider_changed("nose_highlight", val),
        )
        self.slider_nose, self.lbl_nose_val, self.btn_toggle_nose = c_n.slider, c_n.lbl_val, c_n.toggle
        sliders_vbox.addWidget(c_n)

        c_l = self._create_effect_card(
            key="lips", icon_kind="lips", icon_color="#C26A6E",
            title="Son môi tự nhiên", initial_val=self._lips_val,
            on_val_changed=self._on_slider_lips_changed,
        )
        self.slider_lips, self.lbl_s3_val, self.btn_toggle_lips = c_l.slider, c_l.lbl_val, c_l.toggle
        sliders_vbox.addWidget(c_l)

        c_sl = self._create_effect_card(
            key="face_slim", icon_kind="contour", icon_color="#7A776E",
            title="Thon gọn viền mặt", initial_val=self._face_slim_val,
            on_val_changed=lambda val: self._on_region_slider_changed("face_slim", val),
        )
        self.slider_slim, self.lbl_slim_val, self.btn_toggle_slim = c_sl.slider, c_sl.lbl_val, c_sl.toggle
        sliders_vbox.addWidget(c_sl)

        # Nhóm 3: Tăng cường chân dung AI (Hybrid AI Enhancement)
        lbl_grp3 = self._make_section_label("TĂNG CƯỜNG CHÂN DUNG AI")
        lbl_grp3.setContentsMargins(2, 1, 0, 0)
        sliders_vbox.addWidget(lbl_grp3)

        c_ai = self._create_effect_card(
            key="ai_enhance", icon_kind="ai_portrait", icon_color=COLOR_CHAMPAGNE,
            title="Tăng cường chân dung AI", initial_val=self._ai_enhance_val,
            on_val_changed=lambda val: self._on_region_slider_changed("ai_enhance", val),
        )
        self.slider_ai_enhance, self.lbl_ai_val, self.btn_toggle_ai = c_ai.slider, c_ai.lbl_val, c_ai.toggle
        if not self.engine.is_ai_available:
            c_ai.setEnabled(False)
            c_ai.toggle.setChecked(False)
            self._enabled_effects["ai_enhance"] = False
        sliders_vbox.addWidget(c_ai)

        sliders_vbox.addStretch(1)
        sliders_scroll.setWidget(sliders_host)
        ctrl_vbox.addWidget(sliders_scroll, stretch=1)

        # Checkbox giữ thiết lập cho các ảnh tiếp theo
        reuse_card = QFrame()
        reuse_card.setObjectName("beauty_reuse_card")
        reuse_hbox = QHBoxLayout(reuse_card)
        reuse_hbox.setContentsMargins(10, 6, 10, 6)
        self.chk_reuse = QCheckBox("Giữ thiết lập này cho các ảnh tiếp theo")
        self.chk_reuse.setObjectName("beauty_reuse_chk")
        self.chk_reuse.setCursor(Qt.PointingHandCursor)
        self.chk_reuse.setChecked(self.reuse_for_next)
        reuse_hbox.addWidget(self.chk_reuse)
        ctrl_vbox.addWidget(reuse_card)

        divider_bottom = QFrame()
        divider_bottom.setObjectName("beauty_divider")
        ctrl_vbox.addWidget(divider_bottom)

        # HÀNG NÚT THAO TÁC (Đặt lại, Xem ảnh gốc, Xác nhận & Tiếp tục)
        btn_box = QVBoxLayout()
        btn_box.setSpacing(6)

        h_sub_btns = QHBoxLayout()
        h_sub_btns.setSpacing(8)

        self.btn_reset = QPushButton("Đặt Lại")
        self.btn_reset.setObjectName("btn_beauty_secondary")
        self.btn_reset.setIcon(_make_beauty_icon("reset", COLOR_TEXT_PRIMARY, 15))
        self.btn_reset.setIconSize(QSize(15, 15))
        self.btn_reset.setMinimumHeight(34)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        h_sub_btns.addWidget(self.btn_reset, stretch=1)

        self.btn_compare = QPushButton("Xem Ảnh Gốc")
        self.btn_compare.setObjectName("btn_beauty_compare")
        self.btn_compare.setIcon(_make_beauty_icon("eye", COLOR_TEXT_PRIMARY, 15))
        self.btn_compare.setIconSize(QSize(15, 15))
        self.btn_compare.setMinimumHeight(34)
        self.btn_compare.setCheckable(True)
        self.btn_compare.setCursor(Qt.PointingHandCursor)
        self.btn_compare.toggled.connect(self._on_compare_toggled)
        h_sub_btns.addWidget(self.btn_compare, stretch=1)

        btn_box.addLayout(h_sub_btns)

        self.btn_confirm = QPushButton("✓ Xác Nhận && Tiếp Tục")
        self.btn_confirm.setObjectName("btn_beauty_confirm")
        self.btn_confirm.setMinimumHeight(40)
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.clicked.connect(self._on_confirm_clicked)
        btn_box.addWidget(self.btn_confirm)

        ctrl_vbox.addLayout(btn_box)

        content_layout.addWidget(self.ctrl_card, stretch=32)
        main_layout.addLayout(content_layout, stretch=1)

    @staticmethod
    def _make_section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setContentsMargins(2, 0, 0, 0)
        lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #8F8A7F; "
            "letter-spacing: 1.1px; border: none; background: transparent;"
        )
        return lbl

    def _create_effect_card(
        self,
        key: str,
        icon_kind: str,
        icon_color: str,
        title: str,
        initial_val: float,
        on_val_changed,
    ) -> BeautyEffectCard:
        card = BeautyEffectCard(
            key=key,
            icon_kind=icon_kind,
            active_color=icon_color,
            title=title,
            initial_val=initial_val,
            initial_enabled=self._enabled_effects.get(key, True),
            on_val_changed=on_val_changed,
            on_toggled=self._on_effect_toggled,
        )
        self._effect_cards[key] = card
        return card

    def _on_effect_toggled(self, key: str, checked: bool):
        self._enabled_effects[key] = checked
        self._request_render()

    def _sync_card_value(self, key: str, val: int):
        card = self._effect_cards.get(key)
        if card is not None:
            if val > 0 and not self._enabled_effects.get(key, True):
                self._enabled_effects[key] = True
                card.toggle.setChecked(True)
            card.refresh_visual_state(self._enabled_effects.get(key, True), val)

    def _on_slider_brighten_changed(self, val: int):
        val = max(0, min(100, int(val)))
        self._brighten_val = float(val)
        self._sync_card_value("brighten", val)
        self._request_render()

    def _on_slider_smooth_changed(self, val: int):
        val = max(0, min(100, int(val)))
        self._smooth_val = float(val)
        self._sync_card_value("smooth", val)
        self._request_render()

    def _on_slider_lips_changed(self, val: int):
        val = max(0, min(100, int(val)))
        self._lips_val = float(val)
        self._sync_card_value("lips", val)
        self._request_render()

    def _on_region_slider_changed(self, key: str, val: int):
        val = max(0, min(100, int(val)))
        if key == "eye_brighten":
            self._eye_brighten_val = float(val)
        elif key == "cheek_rosy":
            self._cheek_rosy_val = float(val)
        elif key == "nose_highlight":
            self._nose_highlight_val = float(val)
        elif key == "face_slim":
            self._face_slim_val = float(val)
        elif key == "ai_enhance":
            self._ai_enhance_val = float(val)
        self._sync_card_value(key, val)
        self._request_render()

    def _on_reset_clicked(self):
        for key, card in self._effect_cards.items():
            card.slider.blockSignals(True)
            card.slider.setValue(0)
            card.slider.blockSignals(False)

            default_en = DEFAULT_DIALOG_UI_ENABLED.get(key, True)
            self._enabled_effects[key] = default_en
            if card.toggle.isChecked() != default_en:
                card.toggle.setChecked(default_en)
            card.refresh_visual_state(default_en, 0)

        self._req_id += 1
        self._brighten_val = 0.0
        self._smooth_val = 0.0
        self._lips_val = 0.0
        self._eye_brighten_val = 0.0
        self._cheek_rosy_val = 0.0
        self._nose_highlight_val = 0.0
        self._face_slim_val = 0.0
        self._ai_enhance_val = 0.0
        self._current_preview_bgr = self._preview_bgr.copy()
        self._refresh_current_preview()

    def _on_mesh_toggled(self, checked: bool):
        self._show_mesh_overlay = checked
        self._refresh_current_preview()

    def _on_compare_toggled(self, checked: bool):
        self._showing_original = checked
        if checked:
            self.btn_compare.setText("Đang Xem Gốc")
            self.btn_compare.setIcon(_make_beauty_icon("eye_active", "#6B5326", 15))
        else:
            self.btn_compare.setText("Xem Ảnh Gốc")
            self.btn_compare.setIcon(_make_beauty_icon("eye", COLOR_TEXT_PRIMARY, 15))
        self._refresh_current_preview()

    def _request_render(self):
        if self._showing_original:
            return

        self._req_id += 1
        if not self._has_any_active_effect():
            self._current_preview_bgr = self._preview_bgr.copy()
            self._refresh_current_preview()
            return

        self._worker.update_params(
            self._req_id,
            self._preview_bgr,
            self._preview_faces,
            self._brighten_val,
            self._smooth_val,
            self._lips_val,
            eye_brighten=self._eye_brighten_val,
            cheek_rosy=self._cheek_rosy_val,
            nose_highlight=self._nose_highlight_val,
            face_slim=self._face_slim_val,
            enabled_effects=self._enabled_effects,
            ai_enhance=self._ai_enhance_val,
        )

    def _on_preview_ready(self, req_id: int, processed_bgr: np.ndarray):
        if req_id != self._req_id or self._showing_original:
            return

        self._current_preview_bgr = processed_bgr
        self._refresh_current_preview()

    def _refresh_current_preview(self):
        base = self._preview_bgr if self._showing_original else self._current_preview_bgr
        if self._show_mesh_overlay and not self._showing_original and self._preview_faces:
            disp = draw_face_mesh_overlay(base, self._preview_faces, show_tesselation=True, show_regions=True, show_landmarks=True)
        else:
            disp = base
        self._update_preview_display(disp)

    def _update_preview_display(self, bgr_img: np.ndarray):
        if bgr_img is None or bgr_img.size == 0:
            return

        h, w = bgr_img.shape[:2]
        rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
        bytes_per_line = 3 * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(qimg)
        view_size = self.lbl_viewport.size()
        if view_size.width() > 10 and view_size.height() > 10:
            scaled = pixmap.scaled(view_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_viewport.setPixmap(scaled)
        else:
            self.lbl_viewport.setPixmap(pixmap)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._refresh_current_preview)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_current_preview()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def _stop_worker(self):
        if hasattr(self, "_worker") and self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(500)

    def _cleanup_engine(self):
        try:
            if getattr(self, "_owns_engine", False) and self.engine is not None:
                self.engine.close()
            elif self.engine is not None:
                self.engine.clear_ai_cache()
        except Exception:
            pass

    def _collect_numeric_settings(self) -> Dict[str, float]:
        return {
            "brighten": self._brighten_val,
            "smooth": self._smooth_val,
            "lips": self._lips_val,
            "eye_brighten": self._eye_brighten_val,
            "cheek_rosy": self._cheek_rosy_val,
            "nose_highlight": self._nose_highlight_val,
            "face_slim": self._face_slim_val,
            "ai_enhance": self._ai_enhance_val,
        }

    def get_enabled_effects(self) -> Dict[str, bool]:
        return dict(self._enabled_effects)

    def _on_confirm_clicked(self):
        """Xử lý xác nhận: áp dụng thông số lên ảnh gốc chất lượng cao đầy đủ."""
        self._stop_worker()

        if not self._has_any_active_effect():
            final_pil = self._original_pil.copy()
        else:
            QGuiApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                final_bgr = self.engine.apply_beauty(
                    self._full_bgr,
                    skin_brighten_pct=self._brighten_val,
                    skin_smooth_pct=self._smooth_val,
                    lip_tint_pct=self._lips_val,
                    faces=self._full_faces,
                    eye_brighten_pct=self._eye_brighten_val,
                    cheek_rosy_pct=self._cheek_rosy_val,
                    nose_highlight_pct=self._nose_highlight_val,
                    face_slim_pct=self._face_slim_val,
                    enabled_effects=self._enabled_effects,
                    ai_enhance_pct=self._ai_enhance_val,
                )
                final_rgb = cv2.cvtColor(final_bgr, cv2.COLOR_BGR2RGB)
                final_pil = Image.fromarray(final_rgb)
            except Exception as ex:
                logger.error("Lỗi khi áp dụng làm đẹp lên ảnh gốc đầy đủ: %s", ex)
                final_pil = self._original_pil.copy()
            finally:
                QGuiApplication.restoreOverrideCursor()

        self._final_pil_result = final_pil
        settings = self._collect_numeric_settings()
        reuse = self.chk_reuse.isChecked()

        self.beauty_confirmed.emit(final_pil, settings, reuse)
        self._cleanup_engine()
        self.accept()

    def get_result(self) -> Tuple[Image.Image, Dict[str, float], bool]:
        """Trả về (final_pil_image, settings_dict, reuse_flag)."""
        return self._final_pil_result, self._collect_numeric_settings(), self.chk_reuse.isChecked()

    def reject(self):
        self._stop_worker()
        self._cleanup_engine()
        super().reject()

    def closeEvent(self, event):
        self._stop_worker()
        self._cleanup_engine()
        super().closeEvent(event)
