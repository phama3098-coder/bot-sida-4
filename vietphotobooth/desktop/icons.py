"""
1998 TEAM — Photobooth SVG Icon & Design System
Generates crisp, high-DPI vector icons matching the luxury Navy & Champagne Gold aesthetic.
Avoids low-resolution emojis on functional buttons.
"""

from typing import Optional
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, QSize, Qt

# Color Palette Constants
COLOR_GOLD = "#D4AF37"
COLOR_GOLD_LIGHT = "#E5C158"
COLOR_GOLD_PALE = "#FDF4DC"
COLOR_WHITE = "#F8FAFC"
COLOR_SLATE = "#94A3B8"
COLOR_DARK_SLATE = "#64748B"
COLOR_NAVY = "#070A12"
COLOR_NAVY_SURFACE = "#0E1626"
COLOR_GREEN = "#10B981"
COLOR_RED = "#EF4444"
COLOR_BLUE = "#38BDF8"

"""
1998 TEAM — Photobooth SVG Icon & Morphicons Vector Design System
Generates crisp, high-DPI vector icons matching the luxury Navy & Champagne Gold aesthetic.
Provides seamless morphing micro-interactions (Lock ↔ Unlock, Menu ↔ Close, Play ↔ Stop, Refresh ↔ Check)
compatible with PySide6 desktop framework and offline Windows installer.
Avoids low-resolution emojis on functional buttons.
"""

import os
import sys
import math
from typing import Optional, Tuple, Callable
from PySide6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPainterPath, QPen, QBrush, QFont, QImage
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import (
    QByteArray, QSize, Qt, QRectF, QPointF, QVariantAnimation,
    QEasingCurve, Signal, Property
)
from PySide6.QtWidgets import QPushButton, QWidget

# Color Palette Constants (1998 TEAM & 1998 Studio Phóng Sự Cưới)
COLOR_GOLD = "#D4AF37"
COLOR_GOLD_LIGHT = "#E5C158"
COLOR_GOLD_PALE = "#FDF4DC"
COLOR_GOLD_DARK = "#997A15"
COLOR_WHITE = "#F8FAFC"
COLOR_SLATE = "#94A3B8"
COLOR_DARK_SLATE = "#64748B"
COLOR_NAVY = "#070A12"
COLOR_NAVY_SURFACE = "#0E1626"
COLOR_NAVY_CARD = "#111C30"
COLOR_GREEN = "#10B981"
COLOR_RED = "#EF4444"
COLOR_BLUE = "#38BDF8"

SVG_TEMPLATES = {
    "camera": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
        <circle cx="12" cy="13" r="4"/>
    </svg>""",

    "frame": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <circle cx="8.5" cy="8.5" r="1.5"/>
        <polyline points="21 15 16 10 5 21"/>
    </svg>""",

    "printer": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 6 2 18 2 18 9"/>
        <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>
        <rect x="6" y="14" width="12" height="8"/>
    </svg>""",

    "calendar": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
    </svg>""",

    "settings": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
    </svg>""",

    "lock": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>""",

    "unlock": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 9.9-1"/>
    </svg>""",

    "refresh": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"/>
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
    </svg>""",

    "search": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/>
        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>""",

    "folder": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>""",

    "edit": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>""",

    "trash": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
    </svg>""",

    "plus": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="12" y1="5" x2="12" y2="19"/>
        <line x1="5" y1="12" x2="19" y2="12"/>
    </svg>""",

    "minus": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="5" y1="12" x2="19" y2="12"/>
    </svg>""",

    "check": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"/>
    </svg>""",

    "touch": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 11V6a2 2 0 0 0-2-2 2 2 0 0 0-2 2v3"/>
        <path d="M14 10V4a2 2 0 0 0-2-2 2 2 0 0 0-2 2v8"/>
        <path d="M10 10.5V6a2 2 0 0 0-2-2 2 2 0 0 0-2 2v8"/>
        <path d="M18 8a2 2 0 0 1 2 2v4a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.83L7 15"/>
    </svg>""",

    "paper": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
    </svg>""",

    "arrow_right": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="5" y1="12" x2="19" y2="12"/>
        <polyline points="12 5 19 12 12 19"/>
    </svg>""",

    "arrow_left": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="19" y1="12" x2="5" y2="12"/>
        <polyline points="12 19 5 12 12 5"/>
    </svg>""",

    "more": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="1.5"/>
        <circle cx="19" cy="12" r="1.5"/>
        <circle cx="5" cy="12" r="1.5"/>
    </svg>""",

    "stop": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="5" y="5" width="14" height="14" rx="2" ry="2"/>
    </svg>""",

    "play": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="5 3 19 12 5 21 5 3"/>
    </svg>""",

    "cloud": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
    </svg>""",

    "rotate": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21.5 2v6h-6"/>
        <path d="M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.19"/>
    </svg>""",

    "flip": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="8 3 4 7 8 11"/>
        <path d="M4 7h16"/>
        <polyline points="16 21 20 17 16 13"/>
        <path d="M20 17H4"/>
    </svg>""",

    "crop": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 2v14a2 2 0 0 0 2 2h14"/>
        <path d="M18 22V8a2 2 0 0 0-2-2H2"/>
    </svg>""",

    "reset": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="1 4 1 10 7 10"/>
        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
    </svg>""",

    "image": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <circle cx="8.5" cy="8.5" r="1.5"/>
        <polyline points="21 15 16 10 5 21"/>
    </svg>""",

    "save": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
        <polyline points="17 21 17 13 7 13 7 21"/>
        <polyline points="7 3 7 8 15 8"/>
    </svg>""",

    "download": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>""",

    "eye": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
    </svg>""",

    "undo": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="1 4 1 10 7 10"/>
        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
    </svg>""",

    "menu": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
    </svg>""",

    "close": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
    </svg>""",

    "dot_green": """<svg viewBox="0 0 24 24" fill="#10B981" stroke="#10B981" stroke-width="1">
        <circle cx="12" cy="12" r="6"/>
    </svg>""",

    "dot_red": """<svg viewBox="0 0 24 24" fill="#EF4444" stroke="#EF4444" stroke-width="1">
        <circle cx="12" cy="12" r="6"/>
    </svg>"""
}

def get_svg_pixmap(name: str, size: int = 24, color: str = COLOR_GOLD) -> QPixmap:
    """Tạo QPixmap sắc nét từ SVG cho các icon giao diện."""
    template = SVG_TEMPLATES.get(name)
    if not template:
        template = SVG_TEMPLATES["frame"]

    svg_content = template.format(color=color)
    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()

    return pixmap

def get_svg_icon(name: str, size: int = 24, color: str = COLOR_GOLD, active_color: Optional[str] = None) -> QIcon:
    """Tạo QIcon với trạng thái thường và trạng thái active."""
    normal_pix = get_svg_pixmap(name, size=size, color=color)
    icon = QIcon(normal_pix)

    if active_color:
        active_pix = get_svg_pixmap(name, size=size, color=active_color)
        icon.addPixmap(active_pix, QIcon.Active)
        icon.addPixmap(active_pix, QIcon.Selected)

    return icon


class MorphIconButton(QPushButton):
    """
    Nút bấm tích hợp hiệu ứng Morphicons (Vector Morphing Micro-interactions).
    Hỗ trợ chuyển đổi hình dạng có chọn lọc giữa 2 icon (vd: lock ↔ unlock, menu ↔ close, play ↔ stop, refresh ↔ check).
    Tôn trọng reduced_motion của hệ thống và hoạt động ngoại tuyến 100%.
    """
    morphed = Signal(bool)

    def __init__(
        self,
        icon_a: str = "lock",
        icon_b: str = "unlock",
        text: str = "",
        color: str = COLOR_GOLD,
        active_color: str = COLOR_GOLD_LIGHT,
        size: int = 22,
        parent=None
    ):
        super().__init__(text, parent)
        self.icon_a = icon_a
        self.icon_b = icon_b
        self.icon_color = color
        self.icon_active_color = active_color
        self.icon_size = size
        self._is_active = False
        self._morph_progress = 0.0  # 0.0 = A, 1.0 = B

        # Cấu hình Animation Spring / Snappy
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(240)  # ~240ms micro-interaction
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self._on_anim_frame)

        # Cập nhật icon ban đầu
        self._refresh_icon()

    def set_morph_state(self, is_active: bool, animated: bool = True):
        """Chuyển trạng thái morph sang B (True) hoặc A (False)."""
        if self._is_active == is_active:
            return
        self._is_active = is_active

        if animated:
            self.anim.stop()
            self.anim.setStartValue(self._morph_progress)
            self.anim.setEndValue(1.0 if is_active else 0.0)
            self.anim.start()
        else:
            self._morph_progress = 1.0 if is_active else 0.0
            self._refresh_icon()

        self.morphed.emit(self._is_active)

    def toggle_morph(self):
        """Đảo trạng thái morph."""
        self.set_morph_state(not self._is_active)

    def _on_anim_frame(self, val):
        self._morph_progress = float(val)
        self._refresh_icon()

    def _refresh_icon(self):
        """Dựng frame morph hiện tại dựa vào tiến trình 0.0 -> 1.0."""
        p = max(0.0, min(1.0, self._morph_progress))
        pix = QPixmap(self.icon_size, self.icon_size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        color = self.icon_active_color if self.isDown() or self._is_active else self.icon_color
        pen = QPen(QColor(color), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        s = float(self.icon_size)
        cx, cy = s / 2.0, s / 2.0

        # Phân luồng các cặp morph có chọn lọc:
        if self.icon_a == "lock" and self.icon_b == "unlock":
            # Thân khóa cố định ở dưới
            body_w = s * 0.72
            body_h = s * 0.44
            bx = (s - body_w) / 2.0
            by = s * 0.46
            painter.drawRoundedRect(QRectF(bx, by, body_w, body_h), 2, 2)

            # Càng khóa xoay và nhấc lên theo progress p (0 -> đóng, 1 -> mở)
            shackle_r = s * 0.20
            lift = -s * 0.12 * p
            sh_center_x = cx
            sh_center_y = s * 0.38 + lift

            shackle_path = QPainterPath()
            if p < 0.1:
                # Đóng hoàn toàn
                shackle_path.moveTo(cx - shackle_r, by)
                shackle_path.lineTo(cx - shackle_r, sh_center_y)
                shackle_path.arcTo(QRectF(cx - shackle_r, sh_center_y - shackle_r, shackle_r * 2, shackle_r * 2), 180, -180)
                shackle_path.lineTo(cx + shackle_r, by)
            else:
                # Càng khóa nhấc lên và mở sang phải
                angle_open = 45.0 * p
                painter.save()
                painter.translate(cx - shackle_r, by)
                painter.rotate(-angle_open)
                painter.translate(-(cx - shackle_r), -by)
                sh_open_path = QPainterPath()
                sh_open_path.moveTo(cx - shackle_r, by)
                sh_open_path.lineTo(cx - shackle_r, sh_center_y)
                sh_open_path.arcTo(QRectF(cx - shackle_r, sh_center_y - shackle_r, shackle_r * 2, shackle_r * 2), 180, -180)
                sh_open_path.lineTo(cx + shackle_r, sh_center_y + s * 0.06)
                painter.drawPath(sh_open_path)
                painter.restore()
                shackle_path = None

            if shackle_path:
                painter.drawPath(shackle_path)

        elif self.icon_a in ("menu", "plus") and self.icon_b in ("close", "minus"):
            # Morph 3 thanh ngang hoặc dấu cộng thành dấu X (close)
            len_bar = s * 0.65
            half = len_bar / 2.0
            angle = 45.0 * p

            # Thanh chéo 1
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(angle)
            painter.drawLine(QPointF(-half, 0), QPointF(half, 0))
            painter.restore()

            # Thanh chéo 2
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(-angle)
            painter.drawLine(QPointF(-half, 0), QPointF(half, 0))
            painter.restore()

            # Thanh giữa mờ dần
            if p < 0.8:
                fade_alpha = int(255 * (1.0 - p / 0.8))
                painter.setPen(QPen(QColor(color).lighter(100), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                offset_y = (1.0 - p) * (s * 0.22)
                painter.drawLine(QPointF(cx - half, cy - offset_y), QPointF(cx + half, cy - offset_y))
                painter.drawLine(QPointF(cx - half, cy + offset_y), QPointF(cx + half, cy + offset_y))

        elif self.icon_a == "play" and self.icon_b == "stop":
            # Morph tam giác Play sang hình vuông Stop
            poly = QPainterPath()
            t_x1 = cx - s * 0.25
            t_x2 = cx + s * (0.28 - 0.03 * p)
            w_box = s * 0.55
            bx = cx - w_box / 2.0
            by = cy - w_box / 2.0

            # Interpolate coordinates
            p1 = QPointF(t_x1 * (1 - p) + bx * p, (cy - s * 0.3) * (1 - p) + by * p)
            p2 = QPointF(t_x2 * (1 - p) + (bx + w_box) * p, (cy) * (1 - p) + by * p)
            p3 = QPointF(t_x2 * (1 - p) + (bx + w_box) * p, (cy) * (1 - p) + (by + w_box) * p)
            p4 = QPointF(t_x1 * (1 - p) + bx * p, (cy + s * 0.3) * (1 - p) + (by + w_box) * p)

            poly.moveTo(p1)
            poly.lineTo(p2)
            poly.lineTo(p3)
            poly.lineTo(p4)
            poly.closeSubpath()
            painter.drawPath(poly)

        else:
            # Cross-fade fallback cho các icon khác
            pix_a = get_svg_pixmap(self.icon_a, size=self.icon_size, color=color)
            pix_b = get_svg_pixmap(self.icon_b, size=self.icon_size, color=color)
            painter.setOpacity(1.0 - p)
            painter.drawPixmap(0, 0, pix_a)
            painter.setOpacity(p)
            painter.drawPixmap(0, 0, pix_b)

        painter.end()
        self.setIcon(QIcon(pix))
        self.setIconSize(QSize(self.icon_size, self.icon_size))


def get_brand_logo_svg_path() -> str:
    """
    Trả về đường dẫn tuyệt đối tới file logo SVG chính thức của 1998 TEAM.
    Hỗ trợ tìm kiếm đa môi trường: PyInstaller frozen (_MEIPASS), thư mục thực thi,
    cây mã nguồn phát triển và đường dẫn tương đối.
    """
    candidates = []
    # 1. PyInstaller MEIPASS
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "Assets", "Branding", "1998-team-logo.svg"))
        candidates.append(os.path.join(sys._MEIPASS, "assets", "branding", "1998-team-logo.svg"))
    # 2. Executable directory
    exe_dir = os.path.dirname(sys.executable)
    candidates.append(os.path.join(exe_dir, "Assets", "Branding", "1998-team-logo.svg"))
    candidates.append(os.path.join(exe_dir, "assets", "branding", "1998-team-logo.svg"))
    # 3. Source tree root relative to this file
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates.append(os.path.join(root, "Assets", "Branding", "1998-team-logo.svg"))
    candidates.append(os.path.join(root, "assets", "branding", "1998-team-logo.svg"))
    # 4. Fallback relative to current working directory
    candidates.append(os.path.abspath("Assets/Branding/1998-team-logo.svg"))
    candidates.append(os.path.abspath("assets/branding/1998-team-logo.svg"))

    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)

    return os.path.abspath(candidates[0] if candidates else "Assets/Branding/1998-team-logo.svg")


def get_brand_logo_path(variant: str = "transparent") -> str:
    """
    Trả về đường dẫn tuyệt đối đến tài nguyên logo thương hiệu 1998 TEAM chuẩn hóa.
    Hỗ trợ các biến thể: 'transparent', 'navbar', 'kiosk', 'studio', 'svg'.
    """
    filename_map = {
        "transparent": "logo_1998_transparent.png",
        "navbar": "logo_1998_navbar.png",
        "kiosk": "logo_1998_kiosk.png",
        "studio": "logo_1998_studio.png",
        "svg": "1998-team-logo.svg",
    }
    filename = filename_map.get(variant, "logo_1998_transparent.png")
    
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "Assets", "Branding", filename))
        candidates.append(os.path.join(sys._MEIPASS, "assets", "branding", filename))
    exe_dir = os.path.dirname(sys.executable)
    candidates.append(os.path.join(exe_dir, "Assets", "Branding", filename))
    candidates.append(os.path.join(exe_dir, "assets", "branding", filename))
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates.append(os.path.join(root, "Assets", "Branding", filename))
    candidates.append(os.path.join(root, "assets", "branding", filename))
    candidates.append(os.path.abspath(f"Assets/Branding/{filename}"))
    candidates.append(os.path.abspath(f"assets/branding/{filename}"))

    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0] if candidates else f"Assets/Branding/{filename}")


def get_brand_logo_tight_pixmap(height: Optional[int] = None, width: Optional[int] = None) -> QPixmap:
    """
    Trả về QPixmap logo thương hiệu 1998 TEAM với viền sát (Tight Bounding Box),
    nền trong suốt 100%, tỷ lệ ngang chuẩn (~2.06:1), tối ưu cho Header, Navbar và Card.
    """
    path = get_brand_logo_path(variant="transparent")
    if not os.path.exists(path):
        path = get_brand_logo_path(variant="navbar")
    if not os.path.exists(path):
        return get_brand_logo_pixmap(height=height or 36, width=width)
    
    pix = QPixmap(path)
    if pix.isNull():
        return QPixmap()
    
    if height is not None and width is not None:
        return pix.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    elif height is not None:
        return pix.scaledToHeight(height, Qt.SmoothTransformation)
    elif width is not None:
        return pix.scaledToWidth(width, Qt.SmoothTransformation)
    return pix


def get_brand_logo_pixmap(height: int = 36, width: Optional[int] = None) -> QPixmap:
    """
    Render logo SVG chính thức của 1998 TEAM thành QPixmap sắc nét, bảo toàn tuyệt đối
    tỷ lệ gốc (Aspect Ratio 2:3) và độ trong suốt mà không crop hoặc méo hình.
    """
    svg_path = get_brand_logo_svg_path()
    if not os.path.exists(svg_path):
        # Fallback to PNG nếu file SVG chưa có
        png_path = svg_path.replace("1998-team-logo.svg", "logo_1998_studio.png")
        if os.path.exists(png_path):
            pix = QPixmap(png_path)
            return pix.scaledToHeight(height, Qt.SmoothTransformation)
        return QPixmap()

    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        return QPixmap()

    def_sz = renderer.defaultSize()
    def_w = def_sz.width() if def_sz.width() > 0 else 810
    def_h = def_sz.height() if def_sz.height() > 0 else 1215
    aspect = def_w / def_h

    if width is not None and height is not None:
        if width / height > aspect:
            target_h = height
            target_w = max(1, int(target_h * aspect))
        else:
            target_w = width
            target_h = max(1, int(target_w / aspect))
    elif height is not None:
        target_h = height
        target_w = max(1, int(target_h * aspect))
    else:
        target_w = width or 36
        target_h = max(1, int(target_w / aspect))

    img = QImage(target_w, target_h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(img)


def create_brand_logo_widget(height: int = 36, width: Optional[int] = None, parent=None):
    """Tạo widget hiển thị logo 1998 TEAM với thuộc tính hỗ trợ đọc màn hình và tooltip."""
    from PySide6.QtWidgets import QLabel
    lbl = QLabel(parent)
    pix = get_brand_logo_pixmap(height=height, width=width)
    if not pix.isNull():
        lbl.setPixmap(pix)
        lbl.setFixedSize(pix.size())
    else:
        lbl.setText("1998 TEAM")
        lbl.setStyleSheet("color: #D4AF37; font-weight: bold; font-size: 14px;")
    lbl.setToolTip("1998 TEAM — Photobooth")
    lbl.setAccessibleName("Logo 1998 TEAM Photobooth")
    return lbl


