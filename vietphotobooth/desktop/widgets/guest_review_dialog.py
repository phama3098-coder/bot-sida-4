"""
1998 TEAM — Màn Hình Hoàn Thiện Ảnh Sau Chụp (Photo Finalization & Review Screen)
Implements Prompt 2 & Reference Image 2:
- Tông màu: Navy / Đen than (#070A12, #0B1322, #111C30) & Vàng Champagne (#D4AF37, #E5C158).
- Header: Logo 1998 Studio + "HOÀN THIỆN ẢNH" + Stepper 3 bước (1. Chọn khung -> 2. Chọn ảnh -> 3. Xem trước & in) + Nút "TIẾN HÀNH IN ẢNH".
- Khu vực A (Trái): Xem trước ảnh ghép thực tế theo template, công cụ Xoay, Lật, Đặt lại crop, huy hiệu "Đã đủ n/n ảnh".
- Khu vực B (Phải trên): Thư viện chọn khung ảnh với thanh tìm kiếm, filter pills (Tất cả, Sinh nhật, Đám cưới, Sự kiện, Dễ thương, Vintage, Tối giản), thumbnail thực tế với badge khổ ảnh và checkmark vàng khi chọn.
- Khu vực C (Dưới): Chọn ảnh cho từng ô với thẻ cho từng slot (Slot 1, 2, 3, 4...), nút "Thay ảnh" và "Cắt ảnh".
- Thanh thao tác đáy: "Quay lại chụp", "Lưu ảnh", "In thử", "Tiến hành in".
- Tích hợp công cụ Crop và Thay ảnh chuyên dụng.
- Hoạt động ngoại tuyến 100%, bảo toàn dữ liệu gốc.
"""

import os
import copy
import json
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageOps

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSlider, QLineEdit, QComboBox, QMessageBox,
    QSizePolicy, QGridLayout, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QPen, QBrush, QFont, QCursor

from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.core.font_registry import FontRegistry
from vietphotobooth.core.logger import get_logger
from vietphotobooth.desktop.icons import (
    get_svg_pixmap, get_svg_icon, COLOR_GOLD, COLOR_GOLD_LIGHT,
    COLOR_WHITE, COLOR_SLATE, COLOR_NAVY, COLOR_BLUE, COLOR_GREEN,
    get_brand_logo_pixmap
)

logger = get_logger()

LOGO_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "logo_1998_studio.png"
))
STICKERS_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "Assets", "Stickers"
))


# =========================================================================
# MODAL CROP VÀ THU PHÓNG Ô ẢNH CHUYÊN DỤNG (SLOT CROP DIALOG)
# =========================================================================

class SlotCropCanvas(QWidget):
    """Bản vẽ tương tác crop: hỗ trợ kéo pan và zoom trực quan theo tỷ lệ ô."""
    def __init__(self, photo: Image.Image, aspect_ratio: float, offset_x: float, offset_y: float, zoom: float, parent=None):
        super().__init__(parent)
        self.photo = photo
        self.aspect_ratio = aspect_ratio  # w / h
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.zoom = zoom

        self._is_dragging = False
        self._last_mouse_pos = QPointF(0, 0)

        # Chuyển PIL Image sang QPixmap
        rgb = self.photo.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        self.pixmap = QPixmap.fromImage(qimg)

        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet("background-color: #070A12;")

    def set_zoom(self, zoom: float):
        self.zoom = max(1.0, min(3.0, zoom))
        self.update()

    def reset_crop(self):
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom = 1.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            delta = event.position() - self._last_mouse_pos
            self._last_mouse_pos = event.position()
            # Quy đổi delta pixel sang offset tương đối [-1.0, 1.0]
            self.offset_x += (delta.x() / (self.width() * 0.5))
            self.offset_y += (delta.y() / (self.height() * 0.5))
            self.offset_x = max(-1.0, min(1.0, self.offset_x))
            self.offset_y = max(-1.0, min(1.0, self.offset_y))
            self.update()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        self.setCursor(Qt.OpenHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#070A12"))

        # Xác định khung crop mục tiêu (target viewport) theo tỷ lệ aspect_ratio
        margin = 30
        avail_w, avail_h = w - margin * 2, h - margin * 2
        if avail_w / max(avail_h, 1) > self.aspect_ratio:
            target_h = avail_h
            target_w = int(target_h * self.aspect_ratio)
        else:
            target_w = avail_w
            target_h = int(target_w / max(self.aspect_ratio, 0.01))

        tx = (w - target_w) // 2
        ty = (h - target_h) // 2
        target_rect = QRectF(tx, ty, target_w, target_h)

        # Dựng ảnh với zoom và offset
        pw, ph = self.pixmap.width(), self.pixmap.height()
        base_scale = max(target_w / float(pw), target_h / float(ph)) * self.zoom
        sw, sh = pw * base_scale, ph * base_scale

        shift_x = self.offset_x * (sw - target_w) * 0.5
        shift_y = self.offset_y * (sh - target_h) * 0.5
        cx = tx + (target_w - sw) / 2.0 + shift_x
        cy = ty + (target_h - sh) / 2.0 + shift_y

        painter.save()
        painter.setClipRect(target_rect)
        painter.drawPixmap(int(cx), int(cy), int(sw), int(sh), self.pixmap)
        painter.restore()

        # Vẽ viền target viewport vàng champagne
        painter.setPen(QPen(QColor(COLOR_GOLD), 2.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(target_rect)

        # Lưới quy tắc một phần ba (Rule of Thirds)
        painter.setPen(QPen(QColor(212, 175, 55, 60), 1, Qt.DashLine))
        painter.drawLine(int(tx + target_w / 3), ty, int(tx + target_w / 3), ty + target_h)
        painter.drawLine(int(tx + target_w * 2 / 3), ty, int(tx + target_w * 2 / 3), ty + target_h)
        painter.drawLine(tx, int(ty + target_h / 3), tx + target_w, int(ty + target_h / 3))
        painter.drawLine(tx, int(ty + target_h * 2 / 3), tx + target_w, int(ty + target_h * 2 / 3))


class SlotCropDialog(QDialog):
    """Hộp thoại chỉnh crop và phóng to/thu nhỏ cho từng slot riêng biệt."""
    def __init__(self, slot: PhotoSlot, photo: Image.Image, parent=None):
        super().__init__(parent)
        self.slot = slot
        self.photo = photo

        self.setWindowTitle(f"Cắt & Thu Phóng Ảnh — Ô #{slot.id}")
        self.setFixedSize(540, 520)
        self.setStyleSheet("background-color: #FFFFFF; color: #303746;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(12)

        # Tiêu đề
        lbl_head = QLabel(f"<b>CẮT & THU PHÓNG — Ô #{slot.id}</b>")
        lbl_head.setStyleSheet("color: #1E40AF; font-size: 15px;")
        layout.addWidget(lbl_head)

        lbl_guide = QLabel("Kéo ảnh để di chuyển góc nhìn (Pan). Kéo thanh trượt để phóng to (Zoom).")
        lbl_guide.setStyleSheet("color: #64748B; font-size: 12px;")
        layout.addWidget(lbl_guide)

        # Viewport Crop
        aspect = slot.w / max(float(slot.h), 1.0)
        self.canvas = SlotCropCanvas(
            photo=self.photo,
            aspect_ratio=aspect,
            offset_x=getattr(slot, "crop_offset_x", 0.0),
            offset_y=getattr(slot, "crop_offset_y", 0.0),
            zoom=getattr(slot, "zoom", 1.0),
            parent=self
        )
        self.canvas.setFixedHeight(300)
        layout.addWidget(self.canvas)

        # Thanh trượt Zoom
        h_zoom = QHBoxLayout()
        h_zoom.addWidget(QLabel("Thu Phóng (Zoom):"))
        self.lbl_zoom = QLabel(f"{int(self.canvas.zoom * 100)}%")
        self.lbl_zoom.setStyleSheet(f"color: {COLOR_GOLD}; font-weight: bold;")
        h_zoom.addWidget(self.lbl_zoom)
        h_zoom.addStretch()

        btn_reset = QPushButton("Đặt Lại")
        btn_reset.setIcon(get_svg_icon("reset", 14, COLOR_GOLD))
        btn_reset.setStyleSheet(
            "background-color: #F8FAFC; border: 1.5px solid #D9DEE7; color: #303746; "
            "border-radius: 6px; padding: 4px 12px; font-weight: bold;"
        )
        btn_reset.clicked.connect(self._on_reset)
        h_zoom.addWidget(btn_reset)
        layout.addLayout(h_zoom)

        self.slider_zoom = QSlider(Qt.Horizontal)
        self.slider_zoom.setRange(100, 250)
        self.slider_zoom.setValue(int(self.canvas.zoom * 100))
        self.slider_zoom.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider_zoom)

        # Nút xác nhận / hủy
        h_actions = QHBoxLayout()
        h_actions.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setStyleSheet(
            "background-color: #F1F5F9; border: 1px solid #CBD5E1; color: #475569; "
            "border-radius: 8px; padding: 0 20px; font-weight: bold;"
        )
        btn_cancel.clicked.connect(self.reject)
        h_actions.addWidget(btn_cancel)

        btn_confirm = QPushButton("Xác Nhận")
        btn_confirm.setIcon(get_svg_icon("check", 14, "#070A12"))
        btn_confirm.setFixedHeight(38)
        btn_confirm.setStyleSheet(
            f"background-color: {COLOR_GOLD}; color: #070A12; border: none; "
            "border-radius: 8px; padding: 0 24px; font-weight: 900; font-size: 13px;"
        )
        btn_confirm.clicked.connect(self._on_confirm)
        h_actions.addWidget(btn_confirm)

        layout.addLayout(h_actions)

    def _on_slider_changed(self, val):
        self.canvas.set_zoom(val / 100.0)
        self.lbl_zoom.setText(f"{val}%")

    def _on_reset(self):
        self.canvas.reset_crop()
        self.slider_zoom.setValue(100)
        self.lbl_zoom.setText("100%")

    def _on_confirm(self):
        self.slot.crop_offset_x = self.canvas.offset_x
        self.slot.crop_offset_y = self.canvas.offset_y
        self.slot.zoom = self.canvas.zoom
        self.accept()


# =========================================================================
# MODAL CHỌN ẢNH THAY THẾ (PHOTO PICKER MODAL)
# =========================================================================

class PhotoPickerModal(QDialog):
    """Hộp thoại chọn ảnh từ thư viện các ảnh đã chụp trong phiên."""
    def __init__(self, photos: List[Image.Image], current_idx: int, slot_id: int, parent=None):
        super().__init__(parent)
        self.photos = photos
        self.selected_index = current_idx
        self.slot_id = slot_id

        self.setWindowTitle(f"Thay Ảnh Cho Ô #{slot_id}")
        self.setFixedSize(580, 360)
        self.setStyleSheet("background-color: #0B1322; color: #F8FAFC;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        lbl_head = QLabel(f"<b>CHỌN ẢNH GÁN VÀO Ô #{slot_id}</b>")
        lbl_head.setStyleSheet(f"color: {COLOR_GOLD}; font-size: 15px;")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Nhấn vào ảnh bạn muốn hiển thị trong ô này:")
        lbl_desc.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(lbl_desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        h_grid = QHBoxLayout(container)
        h_grid.setSpacing(14)
        h_grid.setContentsMargins(4, 4, 4, 4)

        for idx, p in enumerate(self.photos):
            card = QFrame()
            card.setFixedSize(110, 140)
            card.setCursor(Qt.PointingHandCursor)
            is_sel = (idx == current_idx)

            if is_sel:
                card.setStyleSheet("background-color: #111C30; border: 2.5px solid #D4AF37; border-radius: 8px;")
            else:
                card.setStyleSheet("background-color: #070A12; border: 1.5px solid #1E2D4A; border-radius: 8px;")

            l_card = QVBoxLayout(card)
            l_card.setContentsMargins(4, 4, 4, 4)
            l_card.setSpacing(4)

            lbl_thumb = QLabel()
            lbl_thumb.setAlignment(Qt.AlignCenter)
            rgb = p.convert("RGB")
            w, h = rgb.size
            data = rgb.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            lbl_thumb.setPixmap(pix.scaled(100, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            l_card.addWidget(lbl_thumb)

            lbl_txt = QLabel(f"Ảnh #{idx + 1}")
            lbl_txt.setAlignment(Qt.AlignCenter)
            lbl_txt.setStyleSheet(f"color: {COLOR_GOLD if is_sel else '#94A3B8'}; font-weight: bold; font-size: 11px;")
            l_card.addWidget(lbl_txt)

            # Click handler
            card.mousePressEvent = lambda ev, chosen=idx: self._on_photo_selected(chosen)
            h_grid.addWidget(card)

        h_grid.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Nút đóng
        h_bot = QHBoxLayout()
        h_bot.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet("background-color: #1E293B; border: 1px solid #334155; border-radius: 6px; padding: 0 20px; color: #CBD5E1;")
        btn_close.clicked.connect(self.reject)
        h_bot.addWidget(btn_close)
        layout.addLayout(h_bot)

    def _on_photo_selected(self, idx: int):
        self.selected_index = idx
        self.accept()


# =========================================================================
# KHU VỰC A — CANVAS XEM TRƯỚC ẢNH GHÉP THỰC TẾ
# =========================================================================

class GuestInteractiveCanvas(QWidget):
    """
    Bản vẽ hiển thị trực quan ảnh ghép thực tế (WYSIWYG 300 DPI).
    Hỗ trợ click chọn slot và hiển thị viền highlight vàng của slot đang chọn.
    """
    slot_selected = Signal(int)
    state_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.template: Optional[FrameTemplate] = None
        self.photos: List[Image.Image] = []
        self.preview_pixmap: Optional[QPixmap] = None

        self.selected_type: Optional[str] = "slot"
        self.selected_index: int = 0
        self.preview_mode_only: bool = False

        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #070A12;")

    def set_template_and_photos(self, template: FrameTemplate, photos: List[Image.Image]):
        self.template = template
        self.photos = photos
        self.update_preview()

    def update_preview(self):
        """Dựng ảnh xem trước tức thời với đầy đủ ảnh ghép thực tế."""
        if not self.template:
            self.preview_pixmap = None
            self.update()
            return

        try:
            composite = FrameDesigner.render_composite(
                photos=self.photos if self.photos else [],
                template=self.template,
                event_info={"name": "1998 TEAM", "date": datetime.now().strftime("%d/%m/%Y")}
            )
            rgb = composite.convert("RGB")
            w, h = rgb.size
            data = rgb.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
            self.preview_pixmap = QPixmap.fromImage(qimg)
        except Exception as e:
            logger.error(f"Lỗi dựng ảnh xem trước trong Guest Canvas: {e}")
            self.preview_pixmap = None

        self.update()

    def _get_canvas_geometry(self) -> Tuple[float, int, int, int, int]:
        if not self.template:
            return 1.0, 0, 0, self.width(), self.height()

        cw, ch = self.template.canvas_size
        vw, vh = self.width(), self.height()
        margin = 12
        avail_w = max(10, vw - margin * 2)
        avail_h = max(10, vh - margin * 2)

        scale = min(avail_w / float(cw), avail_h / float(ch))
        rw = int(cw * scale)
        rh = int(ch * scale)
        ox = (vw - rw) // 2
        oy = (vh - rh) // 2
        return scale, ox, oy, rw, rh

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Nền tối
        painter.fillRect(self.rect(), QColor("#070A12"))

        if not self.template:
            painter.setPen(QColor(COLOR_SLATE))
            painter.drawText(self.rect(), Qt.AlignCenter, "Chưa chọn khung ảnh in.")
            return

        scale, ox, oy, rw, rh = self._get_canvas_geometry()

        # Dựng ảnh ghép
        if self.preview_pixmap:
            painter.drawPixmap(ox, oy, rw, rh, self.preview_pixmap)

        # Viền canvas khung
        painter.setPen(QPen(QColor("#1E2D4A"), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(ox, oy, rw, rh)

        # Vẽ từng ô (slot) trên Canvas kèm badge số thứ tự và ảnh đang gán
        if not self.preview_mode_only and self.template and self.template.slots:
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            for idx, slot in enumerate(self.template.slots):
                sx = ox + slot.x * scale
                sy = oy + slot.y * scale
                sw = slot.w * scale
                sh = slot.h * scale

                is_sel = (self.selected_type == "slot" and idx == self.selected_index)

                # Viền slot (Vàng Champagne nét đứt nếu đang chọn, navy nếu không chọn)
                if is_sel:
                    painter.setPen(QPen(QColor(COLOR_GOLD), 2.5, Qt.DashLine))
                    painter.setBrush(QColor(212, 175, 55, 35))
                    painter.drawRect(QRectF(sx, sy, sw, sh))
                else:
                    painter.setPen(QPen(QColor(30, 45, 74, 180), 1.0, Qt.SolidLine))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(QRectF(sx, sy, sw, sh))

                # Badge số ô và ảnh đang nằm trong ô (Góc trên bên trái của slot)
                badge_w = min(sw - 8, 86)
                badge_h = min(sh - 8, 22)
                if badge_w > 30 and badge_h > 14:
                    badge_rect = QRectF(sx + 4, sy + 4, badge_w, badge_h)
                    painter.setPen(QPen(QColor(COLOR_GOLD) if is_sel else QColor("#1E2D4A"), 1.2))
                    painter.setBrush(QColor(7, 11, 22, 215))
                    painter.drawRoundedRect(badge_rect, 4, 4)

                    p_idx = slot.photo_index
                    photo_text = f"Ảnh {p_idx + 1}" if 0 <= p_idx < len(self.photos) else "Trống"
                    painter.setPen(QColor(COLOR_GOLD) if is_sel else QColor("#E2E8F0"))
                    painter.drawText(badge_rect, Qt.AlignCenter, f"Ô {idx + 1}: {photo_text}")

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.template or self.preview_mode_only:
            super().mousePressEvent(event)
            return

        scale, ox, oy, rw, rh = self._get_canvas_geometry()
        mx = event.position().x()
        my = event.position().y()
        cx = (mx - ox) / scale
        cy = (my - oy) / scale

        # Kiểm tra click trúng slot nào
        for idx, slot in enumerate(self.template.slots):
            if slot.x <= cx <= slot.x + slot.w and slot.y <= cy <= slot.y + slot.h:
                self.selected_type = "slot"
                self.selected_index = idx
                self.slot_selected.emit(idx)
                self.update()
                return

        super().mousePressEvent(event)


# =========================================================================
# KHU VỰC B — THẺ KHUNG ẢNH TRONG THƯ VIỆN CHỌN KHUNG
# =========================================================================

class ReviewFrameCard(QFrame):
    """Thẻ hiển thị khung ảnh trong Khu vực B với thumbnail thật và checkmark."""
    clicked = Signal(str)

    def __init__(self, template: FrameTemplate, thumb_path: str, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.template = template
        self.thumb_path = thumb_path
        self._is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(98, 150)

        self._init_ui()
        self._update_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header card: Checkmark khi được chọn
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self.lbl_check = QLabel()
        self.lbl_check.setPixmap(get_svg_pixmap("check", 12, "#070A12"))
        self.lbl_check.setFixedSize(16, 16)
        self.lbl_check.setAlignment(Qt.AlignCenter)
        self.lbl_check.setStyleSheet(f"background-color: {COLOR_GOLD}; border-radius: 8px;")
        self.lbl_check.setVisible(self._is_selected)
        top_bar.addWidget(self.lbl_check)
        top_bar.addStretch()

        type_text = "2x6" if "2x6" in self.template.type else "4x6"
        lbl_type = QLabel(type_text)
        lbl_type.setAlignment(Qt.AlignCenter)
        lbl_type.setFixedSize(32, 16)
        lbl_type.setStyleSheet("background-color: #1E3A8A; color: #93C5FD; border-radius: 3px; font-size: 10px; font-weight: bold;")
        top_bar.addWidget(lbl_type)
        layout.addLayout(top_bar)

        # Thumbnail khung thật
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setFixedHeight(95)
        self.lbl_thumb.setStyleSheet("background: transparent;")

        if self.thumb_path and os.path.exists(self.thumb_path):
            pix = QPixmap(self.thumb_path)
            self.lbl_thumb.setPixmap(pix.scaled(80, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl_thumb.setText(self.template.name)
            self.lbl_thumb.setStyleSheet("color: #94A3B8; font-size: 10px;")

        layout.addWidget(self.lbl_thumb, 1, Qt.AlignCenter)

        # Tên khung
        self.lbl_name = QLabel(self.template.name)
        self.lbl_name.setAlignment(Qt.AlignCenter)
        self.lbl_name.setStyleSheet("color: #F8FAFC; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.lbl_name)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.lbl_check.setVisible(selected)
        self._update_style()

    def _update_style(self):
        if self._is_selected:
            self.setStyleSheet(f"ReviewFrameCard {{ background-color: #111C30; border: 2px solid {COLOR_GOLD}; border-radius: 8px; }}")
        else:
            self.setStyleSheet("ReviewFrameCard {{ background-color: #0E1626; border: 1px solid #1E2D4A; border-radius: 8px; }}"
                               "ReviewFrameCard:hover {{ border: 1.5px solid #38BDF8; background-color: #121F33; }}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.template.id)


# =========================================================================
# KHU VỰC C — THẺ THUMBNAIL ẢNH ĐÃ CHỤP (CLICK-TO-ASSIGN PHOTO CARDS)
# =========================================================================

class PhotoThumbnailCard(QFrame):
    """
    Thẻ thumbnail ảnh chụp ở Khu vực C (Click-to-assign).
    Hiển thị:
    - Badge số ảnh: "Ảnh #1", "Ảnh #2"...
    - Badge gán vào ô: "Ô 1", "Ô 2" hoặc "Chưa gán"
    - Thumbnail ảnh thu nhỏ rõ nét
    - Nút Cắt ảnh (Crop)
    - Viền vàng Champagne #D4AF37 khi được chọn
    """
    photo_clicked = Signal(int)
    slot_clicked = Signal(int)             # Alias tương thích ngược
    change_photo_requested = Signal(int)   # Alias tương thích ngược
    crop_requested = Signal(int)
    retake_slot_requested = Signal(int)

    def __init__(
        self,
        photo_idx: int,
        photo_img: Optional[Image.Image],
        assigned_slots: Optional[List[int]] = None,
        is_selected: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.photo_idx = photo_idx
        self.photo_img = photo_img
        self.assigned_slots = assigned_slots or []
        self.is_selected = is_selected

        self.setFixedSize(136, 102)
        self.setCursor(Qt.PointingHandCursor)

        self._init_ui()
        self.update_style()

    @property
    def slot_idx(self) -> int:
        return self.photo_idx

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        # Header card: Số thứ tự ảnh + Pill ô đã gán
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        self.lbl_num = QLabel(f"Ảnh #{self.photo_idx + 1}")
        self.lbl_num.setStyleSheet(
            f"color: {COLOR_GOLD}; font-size: 11px; font-weight: bold;"
        )
        top.addWidget(self.lbl_num)
        top.addStretch()

        self.lbl_assigned = QLabel()
        self.lbl_assigned.setFixedHeight(18)
        self.lbl_assigned.setAlignment(Qt.AlignCenter)
        self._refresh_assigned_pill()
        top.addWidget(self.lbl_assigned)
        layout.addLayout(top)

        # Thumbnail ảnh
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setFixedHeight(46)
        self._refresh_thumb()
        layout.addWidget(self.lbl_thumb, 1, Qt.AlignCenter)

        # Footer card: Nút Cắt ảnh và Nút Chụp lại ô
        h_bot = QHBoxLayout()
        h_bot.setContentsMargins(0, 0, 0, 0)
        h_bot.setSpacing(4)

        self.btn_crop = QPushButton("Cắt")
        self.btn_crop.setIcon(get_svg_icon("crop", 11, COLOR_GOLD))
        self.btn_crop.setFixedHeight(22)
        self.btn_crop.setCursor(Qt.PointingHandCursor)
        self.btn_crop.setStyleSheet(
            "QPushButton { background-color: #142036; border: 1px solid #28395E; color: #CBD5E1; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0 5px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; background-color: #1A2844; }"
        )
        self.btn_crop.clicked.connect(lambda: self.crop_requested.emit(self.photo_idx))
        h_bot.addWidget(self.btn_crop)

        self.btn_retake = QPushButton("Chụp lại")
        self.btn_retake.setIcon(get_svg_icon("camera", 11, COLOR_GOLD))
        self.btn_retake.setFixedHeight(22)
        self.btn_retake.setCursor(Qt.PointingHandCursor)
        self.btn_retake.setStyleSheet(
            "QPushButton { background-color: #1A2844; border: 1px solid #D4AF37; color: #F5DE88; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0 5px; }"
            "QPushButton:hover { background-color: #243B66; color: #FFFFFF; border-color: #FFF8E7; }"
        )
        self.btn_retake.clicked.connect(lambda: self.retake_slot_requested.emit(self.photo_idx))
        h_bot.addWidget(self.btn_retake)
        h_bot.addStretch()
        layout.addLayout(h_bot)

    def set_photo(self, photo_img: Optional[Image.Image]):
        self.photo_img = photo_img
        self._refresh_thumb()

    def set_assigned_slots(self, slots: List[int]):
        self.assigned_slots = slots
        self._refresh_assigned_pill()

    def _refresh_assigned_pill(self):
        if self.assigned_slots:
            txt = "Ô " + ", ".join(str(s) for s in self.assigned_slots)
            self.lbl_assigned.setText(txt)
            self.lbl_assigned.setStyleSheet(
                "background-color: #1E3A8A; color: #93C5FD; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 4px;"
            )
        else:
            self.lbl_assigned.setText("Chưa gán")
            self.lbl_assigned.setStyleSheet(
                "background-color: #1E293B; color: #94A3B8; border-radius: 3px; font-size: 10px; padding: 1px 4px;"
            )

    def _refresh_thumb(self):
        if self.photo_img:
            rgb = self.photo_img.convert("RGB")
            w, h = rgb.size
            data = rgb.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            self.lbl_thumb.setPixmap(pix.scaled(106, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl_thumb.setText("Trống")
            self.lbl_thumb.setStyleSheet("color: #64748B; font-size: 10px;")

    def set_selected(self, is_selected: bool):
        self.is_selected = is_selected
        self.update_style()

    def update_style(self):
        if self.is_selected:
            self.setStyleSheet(
                f"PhotoThumbnailCard {{ background-color: #111C30; border: 2.5px solid {COLOR_GOLD}; border-radius: 8px; }}"
            )
            self.lbl_num.setStyleSheet(f"color: {COLOR_GOLD_LIGHT}; font-size: 11px; font-weight: 900;")
        else:
            self.setStyleSheet(
                "PhotoThumbnailCard {{ background-color: #0E1626; border: 1.5px solid #1E2D4A; border-radius: 8px; }}"
                "PhotoThumbnailCard:hover {{ border: 1.5px solid #38BDF8; background-color: #131E33; }}"
            )
            self.lbl_num.setStyleSheet("color: #CBD5E1; font-size: 11px; font-weight: bold;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.photo_clicked.emit(self.photo_idx)
            self.slot_clicked.emit(self.photo_idx)


class SlotCard(QFrame):
    """Thẻ đại diện cho từng slot ảnh: Số thứ tự, thumbnail ảnh gán, nút Thay ảnh & Cắt ảnh."""
    slot_clicked = Signal(int)
    change_photo_requested = Signal(int)
    crop_requested = Signal(int)

    def __init__(self, slot_idx: int, slot: PhotoSlot, photo_img: Optional[Image.Image], is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.slot_idx = slot_idx
        self.slot = slot
        self.photo_img = photo_img
        self.is_selected = is_selected

        self.setFixedSize(148, 110)
        self.setCursor(Qt.PointingHandCursor)

        self._init_ui()
        self.update_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header slot: Số thứ tự slot
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)

        self.lbl_num = QLabel(str(self.slot_idx + 1))
        self.lbl_num.setFixedSize(18, 18)
        self.lbl_num.setAlignment(Qt.AlignCenter)
        self.lbl_num.setStyleSheet(
            "background-color: #1E3A8A; color: #93C5FD; border-radius: 9px; font-size: 11px; font-weight: bold;"
        )
        top.addWidget(self.lbl_num)
        top.addStretch()
        layout.addLayout(top)

        # Thumbnail ảnh
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setFixedHeight(46)
        self._refresh_thumb()
        layout.addWidget(self.lbl_thumb, 1, Qt.AlignCenter)

        # Hai nút Thay ảnh và Cắt ảnh
        h_btns = QHBoxLayout()
        h_btns.setSpacing(4)

        btn_change = QPushButton("Thay ảnh")
        btn_change.setIcon(get_svg_icon("image", 12, COLOR_SLATE))
        btn_change.setFixedHeight(26)
        btn_change.setStyleSheet(
            "QPushButton { background-color: #142036; border: 1px solid #28395E; color: #CBD5E1; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0 4px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }"
        )
        btn_change.clicked.connect(lambda: self.change_photo_requested.emit(self.slot_idx))
        h_btns.addWidget(btn_change)

        btn_crop = QPushButton("Cắt ảnh")
        btn_crop.setIcon(get_svg_icon("crop", 12, COLOR_SLATE))
        btn_crop.setFixedHeight(26)
        btn_crop.setStyleSheet(
            "QPushButton { background-color: #142036; border: 1px solid #28395E; color: #CBD5E1; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0 4px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }"
        )
        btn_crop.clicked.connect(lambda: self.crop_requested.emit(self.slot_idx))
        h_btns.addWidget(btn_crop)

        layout.addLayout(h_btns)

    def set_photo(self, photo_img: Optional[Image.Image]):
        self.photo_img = photo_img
        self._refresh_thumb()

    def _refresh_thumb(self):
        if self.photo_img:
            rgb = self.photo_img.convert("RGB")
            w, h = rgb.size
            data = rgb.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            self.lbl_thumb.setPixmap(pix.scaled(130, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl_thumb.setText("Trống")
            self.lbl_thumb.setStyleSheet("color: #64748B; font-size: 10px;")

    def set_selected(self, is_selected: bool):
        self.is_selected = is_selected
        self.update_style()

    def update_style(self):
        if self.is_selected:
            self.setStyleSheet(f"SlotCard {{ background-color: #111C30; border: 2px solid {COLOR_GOLD}; border-radius: 8px; }}")
            self.lbl_num.setStyleSheet(f"background-color: {COLOR_GOLD}; color: #070A12; border-radius: 9px; font-size: 11px; font-weight: bold;")
        else:
            self.setStyleSheet("SlotCard {{ background-color: #0E1626; border: 1px solid #1E2D4A; border-radius: 8px; }}"
                               "SlotCard:hover {{ border: 1px solid #38BDF8; }}")
            self.lbl_num.setStyleSheet("background-color: #1E3A8A; color: #93C5FD; border-radius: 9px; font-size: 11px; font-weight: bold;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.slot_clicked.emit(self.slot_idx)


# =========================================================================
# LỚP HỘP THOẠI CHÍNH (GUEST REVIEW DIALOG)
# =========================================================================

class GuestReviewWidget(QWidget):
    """
    Trang Hoàn Thiện Ảnh sau khi chụp chuẩn 1998 TEAM Photobooth (Tích hợp nội bộ trong cửa sổ chính).
    """
    retake_requested = Signal()
    retake_slot_requested = Signal(int)     # v2.0.0 Chụp lại riêng một ô
    finish_requested = Signal()
    photo_saved = Signal(str)         # Đường dẫn file đã lưu
    print_completed = Signal(str)     # Đường dẫn file sau khi in
    frame_changed = Signal(str)       # ID khung ảnh mới

    CATEGORIES = [
        "Tất cả", "Sinh nhật", "Đám cưới", "Sự kiện", "Dễ thương", "Vintage", "Tối giản"
    ]

    def __init__(
        self,
        photos: Optional[List[Image.Image]] = None,
        frame_mgr: Optional[FrameManager] = None,
        initial_frame_id: Optional[str] = None,
        event_name: str = "SuKien_MacDinh",
        session_id: str = "Session_001",
        print_mgr=None,
        parent=None
    ):
        super().__init__(parent)
        self.photos = list(photos) if photos else []
        self.frame_mgr = frame_mgr or FrameManager()
        self.event_name = event_name
        self.session_id = session_id
        self.print_mgr = print_mgr
        if self.print_mgr is None and parent and not isinstance(parent, QDialog):
            self.print_mgr = getattr(parent, "print_mgr", None)

        self.is_retake: bool = False
        self.final_composite: Optional[Image.Image] = None
        self.current_template: Optional[FrameTemplate] = None
        self.selected_slot_index: int = 0
        self.selected_photo_index: int = 0
        self.history_stack: List[str] = []

        # Thư viện thumbnail cards & slot cards
        self.frame_cards: Dict[str, ReviewFrameCard] = {}
        self.photo_cards: List[PhotoThumbnailCard] = []
        self.slot_cards: List[Any] = []
        self.thumb_widgets: List[Any] = []

        # Nạp template khởi đầu (ưu tiên 'dau_tay' nếu có để khớp ảnh tham chiếu, hoặc initial_frame_id)
        frames = self.frame_mgr.list_frames() if self.frame_mgr else []
        target = None
        if initial_frame_id and self.frame_mgr:
            target = self.frame_mgr.get_frame(initial_frame_id)
        if not target and self.frame_mgr and self.frame_mgr.get_frame("dau_tay"):
            target = self.frame_mgr.get_frame("dau_tay")
        if not target and frames:
            target = frames[0]

        if target:
            self.current_template = copy.deepcopy(target)
            self._ensure_slots_assigned()
            self._push_history()

        self.setWindowTitle("1998 TEAM — Hoàn Thiện Ảnh")
        self.setMinimumSize(1024, 680)
        self.resize(1180, 720)
        self.setStyleSheet("background-color: #070A12; color: #F8FAFC;")

        # Thành phần tương thích kiểm thử
        self.txt_guest_input = QLineEdit()

        self._init_ui()

    def load_session(
        self,
        photos: List[Image.Image],
        frame_mgr: Optional[FrameManager] = None,
        initial_frame_id: Optional[str] = None,
        event_name: str = "SuKien_MacDinh",
        session_id: str = "Session_001",
        print_mgr=None
    ):
        """Tải dữ liệu lượt chụp mới vào trang hoàn thiện nội bộ."""
        self.photos = list(photos) if photos else []
        if frame_mgr:
            self.frame_mgr = frame_mgr
        self.event_name = event_name
        self.session_id = session_id
        if print_mgr:
            self.print_mgr = print_mgr

        self.is_retake = False
        self.final_composite = None
        self.selected_slot_index = 0
        self.selected_photo_index = 0
        self.history_stack.clear()
        self.thumb_widgets = []

        target = None
        if initial_frame_id and self.frame_mgr:
            target = self.frame_mgr.get_frame(initial_frame_id)
        if not target and self.frame_mgr and self.frame_mgr.get_frame("dau_tay"):
            target = self.frame_mgr.get_frame("dau_tay")
        if not target and self.frame_mgr:
            frames = self.frame_mgr.list_frames()
            if frames:
                target = frames[0]

        if target:
            self.current_template = copy.deepcopy(target)
            self._ensure_slots_assigned()
            self._push_history()

        if hasattr(self, "canvas") and self.current_template:
            self.canvas.set_template_and_photos(self.current_template, self.photos)
            self._rebuild_slot_cards()
            self._update_status_label()
            self._update_frame_cards_selection()

    def _ensure_slots_assigned(self):
        """Gán ảnh chụp vào các slot theo thứ tự hợp lý."""
        if not self.current_template or not self.photos:
            return
        num_photos = len(self.photos)
        for i, slot in enumerate(self.current_template.slots):
            slot.photo_index = i % num_photos

    def _push_history(self):
        """Lưu snapshot để phục vụ hoàn tác."""
        if self.current_template:
            data_json = copy.deepcopy(self.current_template.to_dict())
            self.history_stack.append(json.dumps(data_json))
            if len(self.history_stack) > 25:
                self.history_stack.pop(0)

    def _undo(self):
        """Hoàn tác thay đổi gần nhất."""
        if len(self.history_stack) > 1:
            self.history_stack.pop()
            prev_json = json.loads(self.history_stack[-1])
            self.current_template = FrameTemplate.from_dict(prev_json)
            self.canvas.set_template_and_photos(self.current_template, self.photos)
            self._rebuild_slot_cards()
            self._update_status_label()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 14)
        main_layout.setSpacing(10)

        # =========================================================================
        # 1. TOP HEADER BAR: LOGO, TIÊU ĐỀ, STEPPER & NÚT IN NHANH
        # =========================================================================
        h_head = QHBoxLayout()
        h_head.setSpacing(14)

        # Logo 1998 TEAM SVG chính thức
        lbl_brand = QLabel()
        pix_logo = get_brand_logo_pixmap(height=40)
        if not pix_logo.isNull():
            lbl_brand.setPixmap(pix_logo)
        else:
            lbl_brand.setText("<b>1998 TEAM</b>")
            lbl_brand.setStyleSheet(f"color: {COLOR_GOLD}; font-size: 16px; font-weight: 900;")
        lbl_brand.setToolTip("1998 TEAM — Photobooth")
        lbl_brand.setAccessibleName("Logo 1998 TEAM Photobooth")
        h_head.addWidget(lbl_brand)

        # Tiêu đề & phụ đề
        icon_head = QLabel()
        icon_head.setPixmap(get_svg_pixmap("image", 26, COLOR_GOLD))
        h_head.addWidget(icon_head)

        v_title = QVBoxLayout()
        v_title.setSpacing(1)
        lbl_title = QLabel("HOÀN THIỆN ẢNH")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 900; color: #F8FAFC; letter-spacing: 0.5px;")
        lbl_sub = QLabel("Chọn khung, sắp xếp ảnh và in ảnh theo ý thích của bạn")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        h_head.addLayout(v_title)

        h_head.addStretch()

        # Thanh tiến trình Stepper 3 bước (1. Chọn khung -> 2. Chọn ảnh -> 3. Xem trước & in)
        h_stepper = QHBoxLayout()
        h_stepper.setSpacing(8)

        step1_badge = QLabel("1")
        step1_badge.setFixedSize(22, 22)
        step1_badge.setAlignment(Qt.AlignCenter)
        step1_badge.setStyleSheet(f"background-color: {COLOR_GOLD}; color: #070A12; border-radius: 11px; font-weight: bold; font-size: 11px;")
        lbl_step1 = QLabel("1. Chọn khung")
        lbl_step1.setStyleSheet(f"color: {COLOR_GOLD}; font-weight: bold; font-size: 11px;")
        h_stepper.addWidget(step1_badge)
        h_stepper.addWidget(lbl_step1)

        sep1 = QLabel("——")
        sep1.setStyleSheet("color: #334155;")
        h_stepper.addWidget(sep1)

        step2_badge = QLabel("2")
        step2_badge.setFixedSize(22, 22)
        step2_badge.setAlignment(Qt.AlignCenter)
        step2_badge.setStyleSheet("background-color: #1E2D4A; color: #CBD5E1; border-radius: 11px; font-size: 11px; font-weight: bold;")
        lbl_step2 = QLabel("2. Chọn ảnh")
        lbl_step2.setStyleSheet("color: #94A3B8; font-size: 11px;")
        h_stepper.addWidget(step2_badge)
        h_stepper.addWidget(lbl_step2)

        sep2 = QLabel("——")
        sep2.setStyleSheet("color: #334155;")
        h_stepper.addWidget(sep2)

        step3_badge = QLabel("3")
        step3_badge.setFixedSize(22, 22)
        step3_badge.setAlignment(Qt.AlignCenter)
        step3_badge.setStyleSheet("background-color: #1E2D4A; color: #CBD5E1; border-radius: 11px; font-size: 11px; font-weight: bold;")
        lbl_step3 = QLabel("3. Xem trước & in")
        lbl_step3.setStyleSheet("color: #94A3B8; font-size: 11px;")
        h_stepper.addWidget(step3_badge)
        h_stepper.addWidget(lbl_step3)

        h_head.addLayout(h_stepper)
        h_head.addSpacing(20)

        # Nút vàng "TIẾN HÀNH IN ẢNH" góc trên phải
        self.btn_top_print = QPushButton("TIẾN HÀNH IN ẢNH")
        self.btn_top_print.setIcon(get_svg_icon("printer", 18, "#070A12"))
        self.btn_top_print.setFixedHeight(40)
        self.btn_top_print.setCursor(Qt.PointingHandCursor)
        self.btn_top_print.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_GOLD}; color: #070A12; font-weight: 900; "
            "border: none; border-radius: 8px; padding: 0 20px; font-size: 13px; letter-spacing: 0.5px; }"
            "QPushButton:hover { background-color: #E5C158; }"
        )
        self.btn_top_print.clicked.connect(self._on_confirm_and_render)
        h_head.addWidget(self.btn_top_print)

        # Nút "Hoàn tất" góc trên phải
        self.btn_top_finish = QPushButton("Hoàn Tất")
        self.btn_top_finish.setIcon(get_svg_icon("check", 16, COLOR_GOLD))
        self.btn_top_finish.setFixedHeight(40)
        self.btn_top_finish.setCursor(Qt.PointingHandCursor)
        self.btn_top_finish.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1.5px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 16px; }"
            "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; }"
        )
        self.btn_top_finish.clicked.connect(self._on_finish_clicked)
        h_head.addWidget(self.btn_top_finish)

        main_layout.addLayout(h_head)

        # =========================================================================
        # 2. KHU VỰC CHÍNH (KHU VỰC A TRÁI & KHU VỰC B PHẢI TRÊN)
        # =========================================================================
        content_split = QHBoxLayout()
        content_split.setSpacing(14)

        # -------------------------------------------------------------
        # KHU VỰC A (TRÁI): XEM TRƯỚC ẢNH GHÉP THỰC TẾ
        # -------------------------------------------------------------
        container_a = QFrame()
        container_a.setStyleSheet("background-color: #0B1322; border: 1.5px solid #1E2D4A; border-radius: 12px;")
        l_a = QVBoxLayout(container_a)
        l_a.setContentsMargins(10, 10, 10, 10)
        l_a.setSpacing(8)

        # Bản vẽ preview Canvas
        self.canvas = GuestInteractiveCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.slot_selected.connect(self._on_canvas_slot_selected)
        if self.current_template:
            self.canvas.set_template_and_photos(self.current_template, self.photos)
        l_a.addWidget(self.canvas, 1)

        # Thanh công cụ dưới bản vẽ A
        bar_a_bot = QHBoxLayout()
        bar_a_bot.setContentsMargins(4, 2, 4, 2)
        bar_a_bot.setSpacing(10)

        # Trạng thái đủ ảnh (xanh lá)
        self.lbl_status_photos = QLabel()
        self._update_status_label()
        bar_a_bot.addWidget(self.lbl_status_photos)

        bar_a_bot.addStretch()

        # Nút Xoay, Lật, Đặt lại crop, Cắt ảnh
        btn_rotate = QPushButton("Xoay")
        btn_rotate.setIcon(get_svg_icon("rotate", 14, COLOR_GOLD))
        btn_rotate.setFixedHeight(32)
        btn_rotate.setCursor(Qt.PointingHandCursor)
        btn_rotate.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "border-radius: 6px; padding: 0 12px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }"
        )
        btn_rotate.clicked.connect(self._rotate_selected_slot)
        bar_a_bot.addWidget(btn_rotate)

        btn_flip = QPushButton("Lật")
        btn_flip.setIcon(get_svg_icon("flip", 14, COLOR_GOLD))
        btn_flip.setFixedHeight(32)
        btn_flip.setCursor(Qt.PointingHandCursor)
        btn_flip.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "border-radius: 6px; padding: 0 12px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }"
        )
        btn_flip.clicked.connect(self._flip_selected_slot)
        bar_a_bot.addWidget(btn_flip)

        btn_reset_crop = QPushButton("Đặt lại crop")
        btn_reset_crop.setIcon(get_svg_icon("reset", 14, COLOR_GOLD))
        btn_reset_crop.setFixedHeight(32)
        btn_reset_crop.setCursor(Qt.PointingHandCursor)
        btn_reset_crop.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "border-radius: 6px; padding: 0 12px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }"
        )
        btn_reset_crop.clicked.connect(self._reset_selected_slot_pan)
        bar_a_bot.addWidget(btn_reset_crop)

        btn_crop = QPushButton("Cắt ảnh")
        btn_crop.setIcon(get_svg_icon("crop", 14, COLOR_GOLD))
        btn_crop.setFixedHeight(32)
        btn_crop.setCursor(Qt.PointingHandCursor)
        btn_crop.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "border-radius: 6px; padding: 0 12px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }"
        )
        btn_crop.clicked.connect(self._open_crop_dialog_for_selected_slot)
        bar_a_bot.addWidget(btn_crop)

        self.btn_retake_slot = QPushButton("Chụp lại ô này")
        self.btn_retake_slot.setIcon(get_svg_icon("camera", 14, COLOR_GOLD))
        self.btn_retake_slot.setFixedHeight(32)
        self.btn_retake_slot.setCursor(Qt.PointingHandCursor)
        self.btn_retake_slot.setStyleSheet(
            "QPushButton { background-color: #1A2844; border: 1.5px solid #D4AF37; color: #F5DE88; "
            "border-radius: 6px; padding: 0 14px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background-color: #243B66; color: #FFFFFF; border-color: #FFF8E7; }"
        )
        self.btn_retake_slot.clicked.connect(self._on_retake_selected_slot)
        bar_a_bot.addWidget(self.btn_retake_slot)

        l_a.addLayout(bar_a_bot)
        content_split.addWidget(container_a, 55)

        # -------------------------------------------------------------
        # KHU VỰC B (PHẢI TRÊN): THƯ VIỆN CHỌN KHUNG ẢNH
        # -------------------------------------------------------------
        container_b = QFrame()
        container_b.setStyleSheet("background-color: #0B1322; border: 1.5px solid #1E2D4A; border-radius: 12px;")
        l_b = QVBoxLayout(container_b)
        l_b.setContentsMargins(12, 12, 12, 12)
        l_b.setSpacing(10)

        # Header B: Icon frame + CHỌN KHUNG + Search
        h_b_head = QHBoxLayout()
        icon_b = QLabel()
        icon_b.setPixmap(get_svg_pixmap("frame", 22, COLOR_GOLD))
        h_b_head.addWidget(icon_b)

        v_b_title = QVBoxLayout()
        v_b_title.setSpacing(1)
        lbl_b_title = QLabel("CHỌN KHUNG")
        lbl_b_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #F8FAFC;")
        lbl_b_sub = QLabel("Chọn kiểu khung ảnh yêu thích")
        lbl_b_sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
        v_b_title.addWidget(lbl_b_title)
        v_b_title.addWidget(lbl_b_sub)
        h_b_head.addLayout(v_b_title)
        h_b_head.addStretch()

        # Thanh tìm kiếm
        self.txt_search_frame = QLineEdit()
        self.txt_search_frame.setPlaceholderText("Tìm tên khung...")
        self.txt_search_frame.addAction(get_svg_icon("search", 14, COLOR_SLATE), QLineEdit.LeadingPosition)
        self.txt_search_frame.setFixedSize(180, 32)
        self.txt_search_frame.setStyleSheet(
            "QLineEdit { background-color: #070A12; border: 1px solid #1E2D4A; border-radius: 6px; "
            "padding: 2px 8px; color: #F8FAFC; font-size: 11px; }"
            "QLineEdit:focus { border: 1px solid #D4AF37; }"
        )
        self.txt_search_frame.textChanged.connect(self._filter_frames_grid)
        h_b_head.addWidget(self.txt_search_frame)
        l_b.addLayout(h_b_head)

        # Category pills
        self.category_pills_layout = QHBoxLayout()
        self.category_pills_layout.setSpacing(6)
        self.cat_buttons: Dict[str, QPushButton] = {}
        self.current_category = "Tất cả"

        for cat in self.CATEGORIES:
            btn_cat = QPushButton(cat)
            btn_cat.setFixedHeight(28)
            btn_cat.setCursor(Qt.PointingHandCursor)
            btn_cat.clicked.connect(lambda _, c=cat: self._on_category_clicked(c))
            self.cat_buttons[cat] = btn_cat
            self.category_pills_layout.addWidget(btn_cat)
        self.category_pills_layout.addStretch()
        l_b.addLayout(self.category_pills_layout)
        self._update_category_buttons_style()

        # Grid thư viện khung ảnh
        self.scroll_frames = QScrollArea()
        self.scroll_frames.setWidgetResizable(True)
        self.scroll_frames.setFrameShape(QFrame.NoFrame)
        self.scroll_frames.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_frames_content = QWidget()
        self.grid_frames = QGridLayout(self.scroll_frames_content)
        self.grid_frames.setSpacing(10)
        self.grid_frames.setContentsMargins(4, 4, 4, 4)
        self.scroll_frames.setWidget(self.scroll_frames_content)
        l_b.addWidget(self.scroll_frames, 1)

        self._populate_frames_grid()
        content_split.addWidget(container_b, 45)

        main_layout.addLayout(content_split, 1)

        # =========================================================================
        # 3. KHU VỰC C (DƯỚI): CHỌN ẢNH VÀ GÁN VÀO Ô BẰNG CLICK (CLICK-TO-ASSIGN)
        # =========================================================================
        container_c = QFrame()
        container_c.setStyleSheet("background-color: #0B1322; border: 1.5px solid #1E2D4A; border-radius: 12px;")
        l_c = QVBoxLayout(container_c)
        l_c.setContentsMargins(12, 8, 12, 8)
        l_c.setSpacing(5)

        h_c_head = QHBoxLayout()
        icon_c = QLabel()
        icon_c.setPixmap(get_svg_pixmap("image", 18, COLOR_GOLD))
        h_c_head.addWidget(icon_c)

        lbl_c_title = QLabel("<b>ẢNH ĐÃ CHỤP (CHỌN ẢNH & GÁN VÀO Ô)</b> — <span style='color: #94A3B8; font-size: 11px;'>Nhấp vào ảnh để chọn và gán nhanh vào ô trên khung, hoặc nhấp chọn ô rồi chọn ảnh</span>")
        lbl_c_title.setStyleSheet("font-size: 13px; color: #F8FAFC;")
        h_c_head.addWidget(lbl_c_title)
        h_c_head.addStretch()
        l_c.addLayout(h_c_head)

        # Horizontal photo thumbnails row (Gọn gàng ~115px)
        self.slots_scroll = QScrollArea()
        self.slots_scroll.setWidgetResizable(True)
        self.slots_scroll.setFrameShape(QFrame.NoFrame)
        self.slots_scroll.setFixedHeight(115)
        self.slots_scroll_content = QWidget()
        self.h_slots_layout = QHBoxLayout(self.slots_scroll_content)
        self.h_slots_layout.setSpacing(10)
        self.h_slots_layout.setContentsMargins(4, 4, 4, 4)
        self.slots_scroll.setWidget(self.slots_scroll_content)
        l_c.addWidget(self.slots_scroll)

        self._rebuild_slot_cards()
        main_layout.addWidget(container_c)

        # =========================================================================
        # 4. THANH THAO TÁC ĐÁY MÀN HÌNH (BOTTOM ACTION FOOTER)
        # =========================================================================
        h_bottom = QHBoxLayout()
        h_bottom.setContentsMargins(4, 4, 4, 4)
        h_bottom.setSpacing(12)

        # Nút Chụp lại
        self.btn_back = QPushButton("Chụp lại")
        self.btn_back.setIcon(get_svg_icon("arrow_left", 16, "#94A3B8"))
        self.btn_back.setFixedHeight(44)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setStyleSheet(
            "QPushButton { background-color: #0E1626; border: 1.5px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 20px; }"
            "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; background-color: #121C30; }"
        )
        self.btn_back.clicked.connect(self._on_retake_clicked)
        h_bottom.addWidget(self.btn_back)

        h_bottom.addStretch()

        # Nút Lưu ảnh
        self.btn_save = QPushButton("Lưu ảnh")
        self.btn_save.setIcon(get_svg_icon("save", 16, COLOR_GOLD))
        self.btn_save.setFixedHeight(44)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1.5px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 22px; }"
            "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; background-color: #17243E; }"
        )
        self.btn_save.clicked.connect(self._on_save_photo_clicked)
        h_bottom.addWidget(self.btn_save)

        # Nút In thử
        self.btn_test_print = QPushButton("In thử")
        self.btn_test_print.setIcon(get_svg_icon("printer", 16, COLOR_GOLD))
        self.btn_test_print.setFixedHeight(44)
        self.btn_test_print.setCursor(Qt.PointingHandCursor)
        self.btn_test_print.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1.5px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 22px; }"
            "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; background-color: #17243E; }"
        )
        self.btn_test_print.clicked.connect(self._on_test_print_clicked)
        h_bottom.addWidget(self.btn_test_print)

        # Nút Tiến hành in (Vàng champagne nổi bật)
        self.btn_confirm = QPushButton("Tiến hành in")
        self.btn_confirm.setIcon(get_svg_icon("printer", 18, "#070A12"))
        self.btn_confirm.setFixedHeight(44)
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_GOLD}; color: #070A12; font-size: 14px; font-weight: 900; "
            "border: none; border-radius: 8px; padding: 0 28px; letter-spacing: 0.5px; }"
            "QPushButton:hover { background-color: #E5C158; }"
        )
        self.btn_confirm.clicked.connect(self._on_confirm_and_render)
        h_bottom.addWidget(self.btn_confirm)

        # Nút Hoàn tất
        self.btn_finish = QPushButton("Hoàn tất")
        self.btn_finish.setIcon(get_svg_icon("check", 16, COLOR_GOLD))
        self.btn_finish.setFixedHeight(44)
        self.btn_finish.setCursor(Qt.PointingHandCursor)
        self.btn_finish.setStyleSheet(
            "QPushButton { background-color: #0E1626; border: 1.5px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 22px; }"
            "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; background-color: #121C30; }"
        )
        self.btn_finish.clicked.connect(self._on_finish_clicked)
        h_bottom.addWidget(self.btn_finish)

        main_layout.addLayout(h_bottom)

    # =========================================================================
    # LOGIC CẬP NHẬT GIAO DIỆN & TRẠNG THÁI
    # =========================================================================

    def _update_status_label(self):
        if not self.current_template:
            return
        num_slots = len(self.current_template.slots)
        num_photos = len(self.photos)
        is_full = num_photos >= num_slots
        dot_color = "#10B981" if is_full else "#F59E0B"
        text = f"Đã đủ {min(num_photos, num_slots)}/{num_slots} ảnh" if is_full else f"Có {num_photos}/{num_slots} ảnh"
        self.lbl_status_photos.setText(
            f"<span style='color: {dot_color}; font-size: 14px;'>●</span> <b>{text}</b>"
        )
        self.lbl_status_photos.setStyleSheet("font-size: 12px; color: #CBD5E1;")

    def _update_category_buttons_style(self):
        for cat, btn in self.cat_buttons.items():
            if cat == self.current_category:
                btn.setStyleSheet(f"background-color: {COLOR_GOLD}; color: #070A12; font-weight: bold; border-radius: 6px; padding: 0 10px; font-size: 11px;")
            else:
                btn.setStyleSheet("background-color: #070A12; color: #94A3B8; border: 1px solid #1E2D4A; border-radius: 6px; padding: 0 10px; font-size: 11px;"
                                  "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }")

    def _on_category_clicked(self, cat: str):
        self.current_category = cat
        self._update_category_buttons_style()
        self._filter_frames_grid()

    def _populate_frames_grid(self):
        """Dựng lưới cards cho thư viện chọn khung."""
        # Xóa các card cũ
        while self.grid_frames.count():
            item = self.grid_frames.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.frame_cards.clear()

        frames = self.frame_mgr.list_frames()
        col = 0
        row = 0
        max_cols = 4

        for f in frames:
            thumb_path = self.frame_mgr.get_or_create_thumbnail(f, max_width=100, max_height=140)
            is_sel = bool(self.current_template and f.id == self.current_template.id)
            card = ReviewFrameCard(template=f, thumb_path=thumb_path, is_selected=is_sel, parent=self)
            card.clicked.connect(self._switch_frame)
            self.frame_cards[f.id] = card
            self.grid_frames.addWidget(card, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _filter_frames_grid(self):
        """Lọc danh sách khung theo search text và category."""
        search_kw = self.txt_search_frame.text().strip().lower()
        cat = self.current_category

        for fid, card in self.frame_cards.items():
            tmpl = card.template
            name_match = (not search_kw) or (search_kw in tmpl.name.lower())
            cat_match = (cat == "Tất cả") or (cat.lower() == getattr(tmpl, "category", "").lower())
            card.setVisible(name_match and cat_match)

    def _update_frame_cards_selection(self):
        """Cập nhật trạng thái viền chọn cho danh sách thẻ khung."""
        cur_id = self.current_template.id if self.current_template else ""
        for fid, card in self.frame_cards.items():
            card.set_selected(fid == cur_id)

    def _switch_frame(self, frame_id: str):
        """Chuyển sang khung in mới, bảo toàn ảnh chụp của khách."""
        target = self.frame_mgr.get_frame(frame_id)
        if not target:
            return

        old_slots = self.current_template.slots if self.current_template else []
        self.current_template = copy.deepcopy(target)

        # Ánh xạ ảnh từ slot cũ sang slot mới để khách không mất ảnh đã gán
        for i, new_slot in enumerate(self.current_template.slots):
            if i < len(old_slots):
                new_slot.photo_index = old_slots[i].photo_index
                new_slot.rotation = old_slots[i].rotation
                new_slot.is_flipped_h = getattr(old_slots[i], 'is_flipped_h', False)
                new_slot.zoom = old_slots[i].zoom
                new_slot.crop_offset_x = old_slots[i].crop_offset_x
                new_slot.crop_offset_y = old_slots[i].crop_offset_y
            else:
                new_slot.photo_index = i % max(len(self.photos), 1)

        # Cập nhật trạng thái chọn trên các card khung
        for fid, card in self.frame_cards.items():
            card.set_selected(fid == frame_id)

        self.selected_slot_index = 0
        self.canvas.set_template_and_photos(self.current_template, self.photos)
        self._rebuild_slot_cards()
        self._update_status_label()
        self._push_history()

    def _rebuild_slot_cards(self):
        """Dựng lại các thẻ ảnh ở Khu vực C (Photo Thumbnail Cards)."""
        while self.h_slots_layout.count():
            item = self.h_slots_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.photo_cards.clear()
        self.slot_cards.clear()
        self.thumb_widgets.clear()

        if not self.photos:
            return

        # Dựng thẻ cho từng ảnh đã chụp trong phiên (Bảo toàn nguyên vẹn ảnh gốc)
        for p_idx, p_img in enumerate(self.photos):
            assigned = self._get_slots_for_photo(p_idx)
            is_sel = (p_idx == self.selected_photo_index)
            card = PhotoThumbnailCard(
                photo_idx=p_idx,
                photo_img=p_img,
                assigned_slots=assigned,
                is_selected=is_sel,
                parent=self
            )
            card.photo_clicked.connect(self._on_photo_thumbnail_clicked)
            card.crop_requested.connect(self._on_photo_crop_requested)
            card.retake_slot_requested.connect(self.retake_slot_requested.emit)

            self.photo_cards.append(card)
            self.slot_cards.append(card)
            self.thumb_widgets.append(card)
            self.h_slots_layout.addWidget(card)

        self.h_slots_layout.addStretch()
        self._update_photo_cards_assigned_slots()

    def _get_slots_for_photo(self, photo_idx: int) -> List[int]:
        if not self.current_template:
            return []
        slots = []
        for i, s in enumerate(self.current_template.slots):
            if s.photo_index == photo_idx:
                slots.append(i + 1)
        return slots

    def _update_photo_cards_assigned_slots(self):
        for card in self.photo_cards:
            assigned = self._get_slots_for_photo(card.photo_idx)
            card.set_assigned_slots(assigned)

    def _on_photo_thumbnail_clicked(self, photo_idx: int):
        """Click thumbnail ảnh ở Khu vực C: chọn ảnh và gán ngay vào slot đang chọn."""
        self.selected_photo_index = photo_idx
        for pc in self.photo_cards:
            pc.set_selected(pc.photo_idx == photo_idx)

        # Gán ảnh vào slot đang chọn trên Canvas (nếu có)
        if self.current_template and 0 <= self.selected_slot_index < len(self.current_template.slots):
            self._assign_photo_to_slot(self.selected_slot_index, photo_idx)

    def _on_canvas_slot_selected(self, slot_idx: int):
        """Click chọn slot trên Canvas: cập nhật highlight và đồng bộ ảnh tương ứng."""
        self.selected_slot_index = slot_idx
        self.canvas.selected_type = "slot"
        self.canvas.selected_index = slot_idx
        self.canvas.update()

        # Đồng bộ highlight thẻ ảnh của slot này ở Khu vực C
        if self.current_template and 0 <= slot_idx < len(self.current_template.slots):
            p_idx = self.current_template.slots[slot_idx].photo_index
            if 0 <= p_idx < len(self.photos):
                self.selected_photo_index = p_idx
                for pc in self.photo_cards:
                    pc.set_selected(pc.photo_idx == p_idx)

    def _on_slot_card_clicked(self, slot_idx: int):
        self._on_photo_thumbnail_clicked(slot_idx)

    def _on_photo_crop_requested(self, photo_idx: int):
        """Mở crop dialog cho ảnh: tìm slot chứa ảnh này (hoặc slot đang chọn)."""
        target_slot_idx = self.selected_slot_index
        if self.current_template:
            for i, s in enumerate(self.current_template.slots):
                if s.photo_index == photo_idx:
                    target_slot_idx = i
                    break
        self._open_crop_dialog_for_slot(target_slot_idx)

    def _open_crop_dialog_for_selected_slot(self):
        """Mở crop dialog cho slot đang chọn."""
        self._open_crop_dialog_for_slot(self.selected_slot_index)

    def _rotate_selected_slot(self):
        """Xoay ảnh trong slot hiện tại thêm 90 độ."""
        if not self.current_template or not self.current_template.slots:
            return
        slot = self.current_template.slots[self.selected_slot_index]
        slot.rotation = (slot.rotation + 90) % 360
        self.canvas.update_preview()
        self._push_history()

    def _flip_selected_slot(self):
        """Lật gương ảnh trong slot hiện tại theo trục ngang."""
        if not self.current_template or not self.current_template.slots:
            return
        slot = self.current_template.slots[self.selected_slot_index]
        slot.is_flipped_h = not getattr(slot, 'is_flipped_h', False)
        self.canvas.update_preview()
        self._push_history()

    def _reset_selected_slot_pan(self):
        """Đặt lại crop, pan và zoom về mặc định."""
        if not self.current_template or not self.current_template.slots:
            return
        slot = self.current_template.slots[self.selected_slot_index]
        slot.crop_offset_x = 0.0
        slot.crop_offset_y = 0.0
        slot.zoom = 1.0
        slot.rotation = 0
        slot.is_flipped_h = False
        self.canvas.update_preview()
        self._update_photo_cards_assigned_slots()
        self._push_history()

    def _open_photo_picker_for_slot(self, slot_idx: int):
        """Mở modal chọn ảnh cho slot (dự phòng)."""
        if not self.current_template or slot_idx >= len(self.current_template.slots):
            return
        slot = self.current_template.slots[slot_idx]
        dlg = PhotoPickerModal(self.photos, current_idx=slot.photo_index, slot_id=slot.id, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._assign_photo_to_slot(slot_idx, dlg.selected_index)

    def _open_crop_dialog_for_slot(self, slot_idx: int):
        """Mở modal crop chuyên dụng cho slot."""
        if not self.current_template or slot_idx >= len(self.current_template.slots):
            return
        slot = self.current_template.slots[slot_idx]
        p_img = self.photos[slot.photo_index] if 0 <= slot.photo_index < len(self.photos) else None
        if not p_img:
            return
        crop_dlg = SlotCropDialog(slot, p_img, parent=self)
        if crop_dlg.exec() == QDialog.Accepted:
            self.canvas.update_preview()
            self._push_history()

    def _assign_photo_to_slot(self, slot_idx: int, photo_idx: int):
        if not self.current_template or slot_idx >= len(self.current_template.slots):
            return
        slot = self.current_template.slots[slot_idx]
        slot.photo_index = photo_idx
        # Đặt lại crop offset khi thay ảnh mới vào slot
        slot.crop_offset_x = 0.0
        slot.crop_offset_y = 0.0
        slot.zoom = 1.0
        self.canvas.update_preview()
        self._update_photo_cards_assigned_slots()
        self._push_history()

    def _on_retake_selected_slot(self):
        """Khách bấm 'Chụp lại ô này' cho ô hoặc ảnh đang được chọn."""
        if self.current_template and 0 <= self.selected_slot_index < len(self.current_template.slots):
            slot = self.current_template.slots[self.selected_slot_index]
            self.retake_slot_requested.emit(slot.photo_index)
        elif self.photos:
            self.retake_slot_requested.emit(self.selected_photo_index)

    # =========================================================================
    # HÀNH ĐỘNG FOOTER: LƯU ẢNH, IN THỬ, TIẾN HÀNH IN, QUAY LẠI
    # =========================================================================

    def _on_retake_clicked(self):
        """Khách chọn Chụp Lại: quay về giao diện chụp và cho phép chụp lượt mới."""
        self.is_retake = True
        self.retake_requested.emit()

    def _on_finish_clicked(self):
        """Khách hoặc kỹ thuật viên bấm Hoàn Tất: quay về giao diện chụp ảnh, không mở cửa sổ mới."""
        self.finish_requested.emit()

    def _on_save_photo_clicked(self):
        """Lưu ảnh ghép thành phẩm chất lượng cao vào thư mục sự kiện."""
        if not self.current_template:
            return
        try:
            composite = FrameDesigner.render_composite(
                photos=self.photos if self.photos else [],
                template=self.current_template,
                event_info={"name": self.event_name, "date": datetime.now().strftime("%d/%m/%Y")}
            )
            composite.info["dpi"] = (300, 300)
            self.final_composite = composite

            from vietphotobooth.core.config import get_user_data_dir
            events_dir = os.path.join(get_user_data_dir(), "Events", self.event_name, "Final")
            os.makedirs(events_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{self.session_id}_{ts}_saved.jpg"
            out_path = os.path.join(events_dir, fname)
            composite.save(out_path, "JPEG", quality=95, dpi=(300, 300))

            self.photo_saved.emit(out_path)
            logger.info(f"Đã lưu thành công ảnh ghép vào sự kiện '{self.event_name}': {fname}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu ảnh: {e}")
            QMessageBox.critical(self, "Lỗi Lưu Ảnh", f"Không thể lưu ảnh ghép: {e}")

    def _on_test_print_clicked(self):
        """Gửi lệnh in thử tới máy in đã cấu hình."""
        if not self.print_mgr:
            logger.warning("Chưa kết nối hệ thống máy in.")
            return

        try:
            composite = FrameDesigner.render_composite(
                photos=self.photos if self.photos else [],
                template=self.current_template,
                event_info={"name": self.event_name, "date": datetime.now().strftime("%d/%m/%Y")}
            )
            is_strip = "2x6" in getattr(self.current_template, "type", "").lower()
            success = self.print_mgr.print_image(composite, copies=1, print_strip=is_strip)
            if success:
                logger.info("Đã gửi bản in thử thành công tới máy in.")
            else:
                logger.warning("Máy in không phản hồi hoặc đang bận.")
        except Exception as e:
            logger.error(f"Lỗi khi in thử: {e}")
            QMessageBox.critical(self, "Lỗi In", f"Không thể in thử: {e}")

    def _on_confirm_and_render(self):
        """Xác nhận hoàn tất và kết xuất ảnh 300 DPI thành phẩm, lưu và tiến hành in."""
        if not self.current_template:
            self.reject()
            return

        try:
            composite = FrameDesigner.render_composite(
                photos=self.photos if self.photos else [],
                template=self.current_template,
                event_info={"name": self.event_name, "date": datetime.now().strftime("%d/%m/%Y")}
            )
            composite.info["dpi"] = (300, 300)
            self.final_composite = composite

            from vietphotobooth.core.config import get_user_data_dir
            events_dir = os.path.join(get_user_data_dir(), "Events", self.event_name, "Final")
            os.makedirs(events_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{self.session_id}_{ts}_final.jpg"
            out_path = os.path.join(events_dir, fname)
            composite.save(out_path, "JPEG", quality=95, dpi=(300, 300))

            if self.print_mgr:
                is_strip = "2x6" in getattr(self.current_template, "type", "").lower()
                self.print_mgr.print_image(composite, copies=1, print_strip=is_strip)
                logger.info(f"Đã gửi lệnh in cho phiên {self.session_id} (is_strip={is_strip})")

            self.print_completed.emit(out_path)
            self.accept()
        except Exception as e:
            logger.error(f"Lỗi kết xuất và in ảnh: {e}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo ảnh ghép thành phẩm: {e}")

    def accept(self):
        self.finish_requested.emit()

    def reject(self):
        self.is_retake = True
        self.retake_requested.emit()

    # =========================================================================
    # PHƯƠNG THỨC TƯƠNG THÍCH TEST SUITE
    # =========================================================================

    def _assign_photo_to_selected_slot(self, photo_index: int):
        self._assign_photo_to_slot(self.selected_slot_index, photo_index)

    def _on_slot_zoom_slider_changed(self, val: int):
        if self.current_template and 0 <= self.selected_slot_index < len(self.current_template.slots):
            slot = self.current_template.slots[self.selected_slot_index]
            slot.zoom = val / 100.0
            self.canvas.update_preview()

    def _on_text_color_chosen(self, col: str):
        self._current_text_color = col

    def _add_guest_text(self):
        txt = self.txt_guest_input.text().strip()
        if not txt or not self.current_template:
            return
        cw, ch = self.current_template.canvas_size
        col = getattr(self, "_current_text_color", COLOR_GOLD)
        new_layer = TextLayer(
            id=f"text_{len(self.current_template.text_layers) + 1}",
            text=txt,
            x=cw // 2,
            y=ch - 200,
            font_size=32,
            font_color=col,
            alignment="center"
        )
        self.current_template.text_layers.append(new_layer)
        self.canvas.update_preview()
        self._push_history()

    def _delete_selected_text(self):
        if not self.current_template:
            return
        idx = getattr(self.canvas, "selected_index", -1)
        if 0 <= idx < len(self.current_template.text_layers):
            self.current_template.text_layers.pop(idx)
            self.canvas.selected_index = -1
            self.canvas.update_preview()
            self._push_history()

    def _add_sticker(self, sticker_path: str):
        if not self.current_template or not os.path.exists(sticker_path):
            return
        cw, ch = self.current_template.canvas_size
        st = LogoLayer(
            id=f"stk_{len(self.current_template.logo_layers) + 1}",
            image_path=sticker_path,
            x=cw // 2 - 50,
            y=ch // 2 - 50,
            w=100,
            h=100
        )
        setattr(st, "scale", 1.0)
        self.current_template.logo_layers.append(st)
        self.canvas.update_preview()
        self._push_history()

    def _delete_selected_sticker(self):
        if not self.current_template:
            return
        idx = getattr(self.canvas, "selected_index", -1)
        if 0 <= idx < len(self.current_template.logo_layers):
            self.current_template.logo_layers.pop(idx)
            self.canvas.selected_index = -1
            self.canvas.update_preview()
            self._push_history()


# =========================================================================
# LỚP BỌC TƯƠNG THÍCH NGƯỢC (GUEST REVIEW DIALOG WRAPPER)
# =========================================================================

class GuestReviewDialog(QDialog):
    """
    Lớp bọc QDialog kế thừa toàn bộ tính năng của GuestReviewWidget cho tương thích ngược.
    """
    retake_requested = Signal()
    retake_slot_requested = Signal(int)     # v2.0.0 Chụp lại riêng một ô

    def __init__(
        self,
        photos: Optional[List[Image.Image]] = None,
        frame_mgr: Optional[FrameManager] = None,
        initial_frame_id: Optional[str] = None,
        event_name: str = "SuKien_MacDinh",
        session_id: str = "Session_001",
        print_mgr=None,
        parent=None
    ):
        super().__init__(parent)
        self._is_ready = False
        self.review_widget = None
        self.setWindowTitle("1998 TEAM — Hoàn Thiện Ảnh")
        self.setMinimumSize(1024, 680)
        self.resize(1180, 720)
        self.setStyleSheet("QDialog { background-color: #070A12; color: #F8FAFC; } QLabel { color: #F8FAFC; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.review_widget = GuestReviewWidget(
            photos=photos or [],
            frame_mgr=frame_mgr,
            initial_frame_id=initial_frame_id,
            event_name=event_name,
            session_id=session_id,
            print_mgr=print_mgr,
            parent=self
        )
        self._is_ready = True
        layout.addWidget(self.review_widget)

        self.review_widget.retake_requested.connect(self._on_retake)
        self.review_widget.retake_slot_requested.connect(self.retake_slot_requested.emit)
        self.review_widget.finish_requested.connect(self.accept)
        self.review_widget.print_completed.connect(lambda _: self.accept())

    def _on_retake(self):
        self.is_retake = True
        self.reject()

    @property
    def is_retake(self):
        return getattr(self.review_widget, "is_retake", False)

    @is_retake.setter
    def is_retake(self, val):
        self.review_widget.is_retake = val

    @property
    def final_composite(self):
        return getattr(self.review_widget, "final_composite", None)

    @final_composite.setter
    def final_composite(self, val):
        self.review_widget.final_composite = val

    @property
    def current_template(self):
        return getattr(self.review_widget, "current_template", None)

    @current_template.setter
    def current_template(self, val):
        self.review_widget.current_template = val

    @property
    def photos(self):
        return getattr(self.review_widget, "photos", [])

    @photos.setter
    def photos(self, val):
        self.review_widget.photos = val

    @property
    def thumb_widgets(self):
        return getattr(self.review_widget, "thumb_widgets", [])

    @property
    def canvas(self):
        return getattr(self.review_widget, "canvas", None)

    @property
    def txt_guest_input(self):
        return getattr(self.review_widget, "txt_guest_input", None)

    def _on_confirm_and_render(self):
        self.review_widget._on_confirm_and_render()
        if self.review_widget.final_composite:
            self.accept()

    def _assign_photo_to_selected_slot(self, photo_index: int):
        self.review_widget._assign_photo_to_selected_slot(photo_index)

    def _on_slot_zoom_slider_changed(self, val: int):
        self.review_widget._on_slot_zoom_slider_changed(val)

    def _reset_selected_slot_pan(self):
        self.review_widget._reset_selected_slot_pan()

    def _on_text_color_chosen(self, col: str):
        self.review_widget._on_text_color_chosen(col)

    def _add_guest_text(self):
        self.review_widget._add_guest_text()

    def _delete_selected_text(self):
        self.review_widget._delete_selected_text()

    def _add_sticker(self, path):
        self.review_widget._add_sticker(path)

    def _delete_selected_sticker(self):
        self.review_widget._delete_selected_sticker()

    def _undo(self):
        self.review_widget._undo()

    def __getattr__(self, name):
        if not self.__dict__.get("_is_ready") or not hasattr(self, "review_widget") or self.review_widget is None:
            raise AttributeError(name)
        return getattr(self.review_widget, name)

