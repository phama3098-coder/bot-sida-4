"""
1998 TEAM — Màn Hình Khách Chọn Khung & Chỉnh Sửa Ảnh Sau Khi Chụp
(Guest Review, Frame Selection, Slot Photo Swap, Text & Sticker Editing)

Quy trình trải nghiệm cao cấp dành cho khách tiệc cưới & sự kiện:
1. Xem lại toàn bộ ảnh vừa chụp dạng thumbnails.
2. Chọn mẫu khung ảnh (2x6 strip 3 ảnh / 4 ảnh, hoặc 4x6 postcard...). Xem trước tức thời.
3. Chạm vào ô ảnh bất kỳ trên khung để gán hoặc hoán đổi ảnh vừa chụp vào ô đó.
4. Căn chỉnh ảnh trong ô: Di chuyển góc nhìn (pan) và phóng to/thu nhỏ (zoom/crop) không méo tỷ lệ.
5. Thêm/chỉnh sửa chữ: Lời chúc tiệc cưới, sinh nhật có sẵn (presets), phông chữ Việt hoá, màu sắc, kéo thả vị trí.
6. Thêm hình dán (stickers): Bộ sticker đám cưới, sinh nhật, phụ kiện trong suốt PNG, kéo thả, đổi kích cỡ.
7. Các nút thao tác cảm ứng lớn: Chụp lại, Hoàn tác, Xem trước, Hoàn tất & In ảnh.
"""

import os
import copy
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QScrollArea, QFrame, QSlider, QLineEdit, QComboBox,
    QMessageBox, QSizePolicy, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QPen, QBrush, QFont

from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.core.font_registry import FontRegistry
from vietphotobooth.core.logger import get_logger

logger = get_logger()

# Đường dẫn tài nguyên
STICKERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Stickers"))


class GuestInteractiveCanvas(QWidget):
    """
    Bản vẽ tương tác cảm ứng cho khách xem và tinh chỉnh ảnh.
    Độc lập tuyệt đối giữa tỷ lệ hiển thị trên màn hình và tọa độ vật lý 300 DPI.
    """
    slot_selected = Signal(int)
    slot_panned = Signal(int, float, float)
    text_selected = Signal(int)
    text_moved = Signal(int, int, int)
    sticker_selected = Signal(int)
    sticker_moved = Signal(int, int, int)
    state_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.template: Optional[FrameTemplate] = None
        self.photos: List[Image.Image] = []
        self.preview_pixmap: Optional[QPixmap] = None

        # Trạng thái chọn
        self.selected_type: Optional[str] = None  # "slot", "text", "sticker", None
        self.selected_index: int = -1
        self.preview_mode_only: bool = False  # Khi bật, ẩn toàn bộ viền và tay nắm

        # Kéo chuột / cảm ứng
        self._is_dragging: bool = False
        self._drag_start_pos: QPointF = QPointF(0, 0)
        self._drag_orig_pos: Tuple[float, float] = (0.0, 0.0)

        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #070A12;")

    def set_template_and_photos(self, template: FrameTemplate, photos: List[Image.Image]):
        self.template = template
        self.photos = photos
        self.update_preview()

    def update_preview(self):
        """Dựng bản vẽ xem trước tức thời với đầy đủ ảnh, chữ, sticker."""
        if not self.template:
            self.preview_pixmap = None
            self.update()
            return

        try:
            composite = FrameDesigner.render_composite(
                photos=self.photos if self.photos else [],
                template=self.template,
                event_info={"name": "1998 TEAM", "date": "Hôm nay"}
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

    def _get_canvas_geometry(self) -> Tuple[float, float, float, float, float]:
        """Tính toán tỷ lệ và lề căn giữa màn hình (độc lập 300 DPI)."""
        if not self.template:
            return 1.0, 0.0, 0.0, float(self.width()), float(self.height())

        tw, th = self.template.canvas_size
        cw, ch = max(1, self.width()), max(1, self.height())
        scale = min(cw / tw, ch / th) * 0.96  # Lề đệm 4% thẩm mỹ
        rw = tw * scale
        rh = th * scale
        ox = (cw - rw) / 2.0
        oy = (ch - rh) / 2.0
        return scale, ox, oy, rw, rh

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Nền canvas tối sang trọng
        painter.fillRect(self.rect(), QColor("#070A12"))

        if not self.template or not self.preview_pixmap:
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Segoe UI", 13))
            painter.drawText(self.rect(), Qt.AlignCenter, "✨ Đang tạo bản xem trước ảnh...")
            return

        scale, ox, oy, rw, rh = self._get_canvas_geometry()

        # 2. Vẽ hình ảnh render
        render_rect = QRectF(ox, oy, rw, rh)
        painter.drawPixmap(render_rect.toRect(), self.preview_pixmap)

        # 3. Viền ngoài khung ảnh
        painter.setPen(QPen(QColor("#D4AF37"), 2))
        painter.drawRect(render_rect)

        # Nếu đang ở chế độ xem trước thuần túy, không vẽ viền tương tác
        if self.preview_mode_only:
            return

        # 4. Vẽ viền ô ảnh PhotoSlots
        for idx, slot in enumerate(self.template.slots):
            sx = ox + slot.x * scale
            sy = oy + slot.y * scale
            sw = slot.w * scale
            sh = slot.h * scale
            slot_rect = QRectF(sx, sy, sw, sh)

            is_sel = (self.selected_type == "slot" and self.selected_index == idx)
            if is_sel:
                # Viền vàng champagne nổi bật với hiệu ứng chọn
                pen = QPen(QColor("#D4AF37"), 3, Qt.SolidLine)
                painter.setPen(pen)
                painter.setBrush(QColor(212, 175, 55, 35))
                painter.drawRect(slot_rect)

                # Badge chỉ báo ô ảnh đang chọn
                photo_num = (slot.photo_index % len(self.photos)) + 1 if self.photos else 1
                badge_text = f"Ô #{slot.id} (Đang gán Ảnh #{photo_num})"
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.setBrush(QColor(13, 21, 39, 230))
                painter.setPen(QColor("#FDF4DC"))
                badge_w = 200
                painter.drawRoundedRect(QRectF(sx + 8, sy + 8, badge_w, 26), 6, 6)
                painter.drawText(QRectF(sx + 14, sy + 8, badge_w - 12, 26), Qt.AlignVCenter, badge_text)
            else:
                # Viền nét đứt nhẹ nhàng để khách nhận biết có thể chạm chọn ô
                pen = QPen(QColor(56, 189, 248, 120), 1.5, Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(slot_rect)

                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#38BDF8"))
                painter.drawText(QRectF(sx + 8, sy + 8, 60, 20), Qt.AlignLeft, f"#{slot.id}")

        # 5. Vẽ viền lớp chữ TextLayers
        for idx, txt in enumerate(self.template.text_layers):
            if not getattr(txt, 'is_visible', True):
                continue

            font_sz = max(10, int(txt.font_size * scale))
            lines = (txt.text or "").split("\n")
            line_h = int(font_sz * 1.35)
            total_h = len(lines) * line_h
            max_line_len = max([len(l) for l in lines]) if lines else 5
            approx_w = max(60, int(max_line_len * font_sz * 0.6))

            tx = ox + txt.x * scale - approx_w / 2
            ty = oy + txt.y * scale
            text_rect = QRectF(tx, ty, approx_w, total_h)

            is_sel = (self.selected_type == "text" and self.selected_index == idx)
            if is_sel:
                painter.setPen(QPen(QColor("#D4AF37"), 2, Qt.DashLine))
                painter.setBrush(QColor(212, 175, 55, 30))
                painter.drawRoundedRect(text_rect.adjusted(-6, -4, 6, 4), 6, 6)

                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setBrush(QColor(13, 21, 39, 220))
                painter.setPen(QColor("#FDF4DC"))
                painter.drawRoundedRect(QRectF(tx, ty - 24, 120, 20), 4, 4)
                painter.drawText(QRectF(tx + 4, ty - 24, 112, 20), Qt.AlignVCenter, f"✍️ Chữ #{idx+1}")
            else:
                painter.setPen(QPen(QColor(212, 175, 55, 90), 1, Qt.DotLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(text_rect.adjusted(-4, -2, 4, 2), 4, 4)

        # 6. Vẽ viền lớp hình dán Sticker (LogoLayers)
        for idx, sticker in enumerate(self.template.logo_layers):
            st_scale = getattr(sticker, 'scale', 1.0)
            sw = (getattr(sticker, 'original_w', sticker.w) * st_scale if getattr(sticker, 'original_w', 0) else sticker.w) * scale
            sh = (getattr(sticker, 'original_h', sticker.h) * st_scale if getattr(sticker, 'original_h', 0) else sticker.h) * scale
            sx = ox + sticker.x * scale
            sy = oy + sticker.y * scale
            st_rect = QRectF(sx, sy, sw, sh)

            is_sel = (self.selected_type == "sticker" and self.selected_index == idx)
            if is_sel:
                painter.setPen(QPen(QColor("#E11D48"), 2.5, Qt.SolidLine))
                painter.setBrush(QColor(225, 29, 72, 35))
                painter.drawRect(st_rect)

                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setBrush(QColor(13, 21, 39, 220))
                painter.setPen(QColor("#FDF4DC"))
                painter.drawRoundedRect(QRectF(sx, sy - 22, 110, 20), 4, 4)
                painter.drawText(QRectF(sx + 4, sy - 22, 102, 20), Qt.AlignVCenter, f"🎨 Sticker #{idx+1}")

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.template or self.preview_mode_only:
            super().mousePressEvent(event)
            return

        scale, ox, oy, rw, rh = self._get_canvas_geometry()
        mx = event.position().x()
        my = event.position().y()

        # Tọa độ tương ứng trên canvas 300 DPI
        cx = (mx - ox) / scale
        cy = (my - oy) / scale

        # 1. Ưu tiên kiểm tra lớp sticker đang ở trên cùng
        for idx in reversed(range(len(self.template.logo_layers))):
            st = self.template.logo_layers[idx]
            st_scale = getattr(st, 'scale', 1.0)
            sw = (getattr(st, 'original_w', st.w) * st_scale if getattr(st, 'original_w', 0) else st.w)
            sh = (getattr(st, 'original_h', st.h) * st_scale if getattr(st, 'original_h', 0) else st.h)
            if st.x <= cx <= st.x + sw and st.y <= cy <= st.y + sh:
                self.selected_type = "sticker"
                self.selected_index = idx
                self._is_dragging = True
                self._drag_start_pos = event.position()
                self._drag_orig_pos = (float(st.x), float(st.y))
                self.sticker_selected.emit(idx)
                self.update()
                return

        # 2. Kiểm tra lớp văn bản
        for idx in reversed(range(len(self.template.text_layers))):
            txt = self.template.text_layers[idx]
            if not getattr(txt, 'is_visible', True):
                continue
            lines = (txt.text or "").split("\n")
            line_h = int(txt.font_size * 1.35)
            total_h = len(lines) * line_h
            approx_w = max(80, int(max([len(l) for l in lines]) * txt.font_size * 0.6)) if lines else 80
            tx = txt.x - approx_w / 2
            ty = txt.y
            if tx <= cx <= tx + approx_w and ty <= cy <= ty + total_h:
                self.selected_type = "text"
                self.selected_index = idx
                self._is_dragging = True
                self._drag_start_pos = event.position()
                self._drag_orig_pos = (float(txt.x), float(txt.y))
                self.text_selected.emit(idx)
                self.update()
                return

        # 3. Kiểm tra ô ảnh PhotoSlot
        for idx, slot in enumerate(self.template.slots):
            if slot.x <= cx <= slot.x + slot.w and slot.y <= cy <= slot.y + slot.h:
                self.selected_type = "slot"
                self.selected_index = idx
                self._is_dragging = True
                self._drag_start_pos = event.position()
                self._drag_orig_pos = (slot.crop_offset_x, slot.crop_offset_y)
                self.slot_selected.emit(idx)
                self.update()
                return

        # Nhấp ra ngoài
        self.selected_type = None
        self.selected_index = -1
        self.update()

    def mouseMoveEvent(self, event):
        if not self._is_dragging or not self.template:
            super().mouseMoveEvent(event)
            return

        scale, ox, oy, rw, rh = self._get_canvas_geometry()
        dx = (event.position().x() - self._drag_start_pos.x()) / scale
        dy = (event.position().y() - self._drag_start_pos.y()) / scale

        if self.selected_type == "slot" and 0 <= self.selected_index < len(self.template.slots):
            slot = self.template.slots[self.selected_index]
            # Kéo pan ảnh bên trong ô
            orig_ox, orig_oy = self._drag_orig_pos
            # Đổi dấu và chuẩn hóa độ dịch chuyển
            slot.crop_offset_x = orig_ox - (dx / max(1, slot.w)) * 1.5
            slot.crop_offset_y = orig_oy - (dy / max(1, slot.h)) * 1.5
            self.slot_panned.emit(self.selected_index, slot.crop_offset_x, slot.crop_offset_y)
            self.update_preview()

        elif self.selected_type == "text" and 0 <= self.selected_index < len(self.template.text_layers):
            txt = self.template.text_layers[self.selected_index]
            orig_x, orig_y = self._drag_orig_pos
            txt.x = int(orig_x + dx)
            txt.y = int(orig_y + dy)
            self.text_moved.emit(self.selected_index, txt.x, txt.y)
            self.update_preview()

        elif self.selected_type == "sticker" and 0 <= self.selected_index < len(self.template.logo_layers):
            st = self.template.logo_layers[self.selected_index]
            orig_x, orig_y = self._drag_orig_pos
            st.x = int(orig_x + dx)
            st.y = int(orig_y + dy)
            self.sticker_moved.emit(self.selected_index, st.x, st.y)
            self.update_preview()

    def mouseReleaseEvent(self, event):
        if self._is_dragging:
            self._is_dragging = False
            self.state_changed.emit()
        super().mouseReleaseEvent(event)


class GuestPhotoThumbnail(QFrame):
    """Thẻ ảnh thu nhỏ của ảnh vừa chụp để khách chạm gán vào ô."""
    clicked = Signal(int)

    def __init__(self, photo_index: int, photo_img: Image.Image, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.photo_index = photo_index
        self.is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(110, 110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)

        # Tạo QPixmap từ PIL Image
        rgb = photo_img.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.lbl_thumb.setPixmap(pix.scaled(100, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.lbl_thumb)

        self.lbl_caption = QLabel(f"Ảnh #{photo_index + 1}")
        self.lbl_caption.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_caption)

        self._update_style()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self._update_style()

    def _update_style(self):
        if self.is_selected:
            self.setStyleSheet(
                "GuestPhotoThumbnail { background-color: #0E1A33; border: 2.5px solid #D4AF37; border-radius: 8px; }"
                "QLabel { color: #D4AF37; font-weight: bold; font-size: 11px; }"
            )
        else:
            self.setStyleSheet(
                "GuestPhotoThumbnail { background-color: #0B1322; border: 1px solid #1E2D4A; border-radius: 8px; }"
                "GuestPhotoThumbnail:hover { border: 1.5px solid #38BDF8; background-color: #121C30; }"
                "QLabel { color: #CBD5E1; font-size: 11px; }"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.photo_index)
        super().mousePressEvent(event)


class GuestReviewDialog(QDialog):
    """
    Hộp thoại chính cho khách chọn khung & chỉnh sửa ảnh sau khi chụp.
    """
    retake_requested = Signal()

    def __init__(
        self,
        photos: List[Image.Image],
        frame_mgr: FrameManager,
        initial_frame_id: Optional[str] = None,
        event_name: str = "SuKien_MacDinh",
        session_id: str = "Session_001",
        parent=None
    ):
        super().__init__(parent)
        self.photos = photos
        self.frame_mgr = frame_mgr
        self.event_name = event_name
        self.session_id = session_id
        self.is_retake: bool = False
        self.final_composite: Optional[Image.Image] = None

        # Template đang làm việc (bản sao độc lập để khách tinh chỉnh)
        self.current_template: Optional[FrameTemplate] = None
        self.history_stack: List[str] = []  # Lưu JSON history để hoàn tác (Undo)

        self.setWindowTitle("1998 TEAM — Chọn Khung & Chỉnh Sửa Ảnh")
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(
            "QDialog { background-color: #070A12; color: #F8FAFC; }"
            "QLabel { color: #F8FAFC; }"
        )

        # Nạp template khởi đầu
        frames = self.frame_mgr.list_frames()
        target = None
        if initial_frame_id:
            target = self.frame_mgr.get_frame(initial_frame_id)
        if not target and frames:
            target = frames[0]

        if target:
            self.current_template = copy.deepcopy(target)
            self._ensure_slots_assigned()
            self._push_history()

        self._init_ui()

    def _ensure_slots_assigned(self):
        """Gán ảnh chụp vào các slot theo thứ tự hợp lý."""
        if not self.current_template or not self.photos:
            return
        num_photos = len(self.photos)
        for i, slot in enumerate(self.current_template.slots):
            slot.photo_index = i % num_photos

    def _push_history(self):
        """Lưu snapshot trạng thái để phục vụ nút Hoàn Tác (Undo)."""
        if self.current_template:
            data_json = copy.deepcopy(self.current_template.to_dict())
            import json
            self.history_stack.append(json.dumps(data_json))
            if len(self.history_stack) > 20:
                self.history_stack.pop(0)

    def _undo(self):
        """Khôi phục lại trạng thái gần nhất."""
        if len(self.history_stack) > 1:
            self.history_stack.pop()  # bỏ trạng thái hiện tại
            import json
            prev_json = json.loads(self.history_stack[-1])
            self.current_template = FrameTemplate.from_dict(prev_json)
            self.canvas.set_template_and_photos(self.current_template, self.photos)
            self._sync_ui_with_selected_item()
        else:
            QMessageBox.information(self, "Hoàn Tác", "Đã quay về trạng thái ban đầu.")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 12)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 1. THANH TIÊU ĐỀ & THUMBNAILS CÁC ẢNH VỪA CHỤP
        # -------------------------------------------------------------
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        lbl_logo = QLabel("💎 <b>1998 STUDIO</b> — CHỌN KHUNG & CHỈNH SỬA")
        lbl_logo.setStyleSheet("color: #D4AF37; font-size: 15px; font-weight: 900;")
        top_bar.addWidget(lbl_logo)

        top_bar.addSpacing(16)
        lbl_photos_hint = QLabel("📸 Ảnh đã chụp:")
        lbl_photos_hint.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold;")
        top_bar.addWidget(lbl_photos_hint)

        # Dải thumbnails các ảnh chụp
        self.thumb_widgets: List[GuestPhotoThumbnail] = []
        for i, photo in enumerate(self.photos):
            th = GuestPhotoThumbnail(photo_index=i, photo_img=photo, parent=self)
            th.clicked.connect(self._on_captured_photo_clicked)
            self.thumb_widgets.append(th)
            top_bar.addWidget(th)

        top_bar.addStretch()

        btn_preview_toggle = QPushButton("👁️ Xem Trước")
        btn_preview_toggle.setFixedHeight(36)
        btn_preview_toggle.setCheckable(True)
        btn_preview_toggle.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1.5px solid #28395E; border-radius: 8px; color: #CBD5E1; padding: 0 14px; font-weight: bold; }"
            "QPushButton:checked { background-color: #0E1A33; border: 1.5px solid #D4AF37; color: #D4AF37; }"
        )
        btn_preview_toggle.toggled.connect(self._on_toggle_preview_mode)
        top_bar.addWidget(btn_preview_toggle)

        main_layout.addLayout(top_bar)

        # -------------------------------------------------------------
        # 2. KHU VỰC CHÍNH: CANVAS BÊN TRÁI & TAB CHỨC NĂNG BÊN PHẢI
        # -------------------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        # BẢN VẼ TƯƠNG TÁC CHÍNH GIỮA (CANVAS)
        self.canvas = GuestInteractiveCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumSize(420, 480)
        self.canvas.slot_selected.connect(self._on_canvas_slot_selected)
        self.canvas.text_selected.connect(self._on_canvas_text_selected)
        self.canvas.sticker_selected.connect(self._on_canvas_sticker_selected)
        self.canvas.state_changed.connect(self._push_history)
        if self.current_template:
            self.canvas.set_template_and_photos(self.current_template, self.photos)
        content_layout.addWidget(self.canvas, 6)

        # BẢNG ĐIỀU KHIỂN CẢM ỨNG BÊN PHẢI
        right_panel = QFrame()
        right_panel.setFixedWidth(380)
        right_panel.setStyleSheet("background-color: #0A111F; border: 1px solid #1E2D4A; border-radius: 12px;")
        l_right = QVBoxLayout(right_panel)
        l_right.setContentsMargins(10, 10, 10, 10)
        l_right.setSpacing(8)

        self.tabs_control = QTabWidget()
        self.tabs_control.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #1E2D4A; background: #0A111F; border-radius: 8px; }"
            "QTabBar::tab { background: #121C30; color: #94A3B8; padding: 10px 12px; font-weight: bold; font-size: 12px; border-radius: 6px; margin: 2px; }"
            "QTabBar::tab:selected { background: #0E1A33; color: #D4AF37; border: 1.5px solid #D4AF37; }"
        )

        # TAB 1: 🖼️ ĐỔI KHUNG
        tab_frames = self._build_tab_frames()
        self.tabs_control.addTab(tab_frames, "🖼️ Khung")

        # TAB 2: 📸 Ô ẢNH & CĂN CHỈNH
        tab_slot = self._build_tab_slots()
        self.tabs_control.addTab(tab_slot, "📸 Ô Ảnh")

        # TAB 3: ✍️ THÊM CHỮ
        tab_text = self._build_tab_text()
        self.tabs_control.addTab(tab_text, "✍️ Lời Chúc")

        # TAB 4: 🎨 HÌNH DÁN (STICKER)
        tab_sticker = self._build_tab_stickers()
        self.tabs_control.addTab(tab_sticker, "🎨 Sticker")

        l_right.addWidget(self.tabs_control)
        content_layout.addWidget(right_panel, 4)

        main_layout.addLayout(content_layout, 1)

        # -------------------------------------------------------------
        # 3. ĐÁY MÀN HÌNH: CÁC NÚT HÀNH ĐỘNG CẢM ỨNG LỚN
        # -------------------------------------------------------------
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(4, 6, 4, 6)
        bottom_bar.setSpacing(14)

        btn_retake = QPushButton("🔄 Chụp Lại")
        btn_retake.setFixedHeight(54)
        btn_retake.setStyleSheet(
            "QPushButton { background-color: #1A1308; border: 1.5px solid #D4AF37; color: #F7E7CE; "
            "font-size: 15px; font-weight: bold; border-radius: 10px; padding: 0 20px; }"
            "QPushButton:hover { background-color: #2D1E0A; }"
        )
        btn_retake.clicked.connect(self._on_retake_clicked)
        bottom_bar.addWidget(btn_retake)

        btn_undo = QPushButton("↩️ Hoàn Tác")
        btn_undo.setFixedHeight(54)
        btn_undo.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "font-size: 15px; font-weight: bold; border-radius: 10px; padding: 0 18px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }"
        )
        btn_undo.clicked.connect(self._undo)
        bottom_bar.addWidget(btn_undo)

        bottom_bar.addStretch()

        # NÚT HOÀN TẤT & IN ẢNH VÀNG CHAMPAGNE KHỔNG LỒ
        btn_confirm = QPushButton("🖨️ HOÀN TẤT & IN ẢNH")
        btn_confirm.setFixedHeight(56)
        btn_confirm.setMinimumWidth(280)
        btn_confirm.setCursor(Qt.PointingHandCursor)
        btn_confirm.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F7E7CE, stop:0.35 #E5C158, stop:1 #C59B27); "
            "color: #070A12; font-size: 18px; font-weight: 900; border-radius: 28px; border: 2px solid #FFF8E7; padding: 0 28px; }"
            "QPushButton:hover { background: #F0D278; border: 2px solid #FFFFFF; }"
            "QPushButton:pressed { background: #C59B27; }"
        )
        btn_confirm.clicked.connect(self._on_confirm_and_render)
        bottom_bar.addWidget(btn_confirm)

        main_layout.addLayout(bottom_bar)

    # -----------------------------------------------------------------
    # XÂY DỰNG CÁC TAB ĐIỀU KHIỂN
    # -----------------------------------------------------------------
    def _build_tab_frames(self) -> QWidget:
        """Tab chọn các mẫu khung có sẵn."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        lbl_desc = QLabel("Chạm để đổi kiểu khung ảnh in:")
        lbl_desc.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(lbl_desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)

        frames = self.frame_mgr.list_frames()
        btn_style = (
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; border-radius: 8px; color: #E2E8F0; "
            "font-size: 13px; font-weight: bold; min-height: 48px; text-align: left; padding-left: 14px; }"
            "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; background-color: #17243E; }"
        )

        for f in frames:
            name_display = f.name
            num_slots = len(f.slots)
            btn = QPushButton(f"🖼️ {name_display} ({num_slots} ô ảnh)")
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda _, fid=f.id: self._switch_frame(fid))
            scroll_layout.addWidget(btn)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        return widget

    def _build_tab_slots(self) -> QWidget:
        """Tab gán ảnh cho ô và thu phóng / căn tâm."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.lbl_selected_slot = QLabel("👉 Chạm một ô ảnh trên khung để chỉnh sửa")
        self.lbl_selected_slot.setStyleSheet("color: #D4AF37; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.lbl_selected_slot)

        # Nút chọn ảnh gán vào ô
        layout.addWidget(QLabel("<b>Đổi ảnh cho ô đang chọn:</b>"))
        h_photos_swap = QHBoxLayout()
        for idx in range(len(self.photos)):
            btn_pick = QPushButton(f"Ảnh #{idx+1}")
            btn_pick.setFixedHeight(36)
            btn_pick.setStyleSheet(
                "QPushButton { background-color: #16223B; border: 1px solid #28395E; border-radius: 6px; color: #E2E8F0; font-weight: bold; }"
                "QPushButton:hover { border: 1.5px solid #D4AF37; color: #D4AF37; }"
            )
            btn_pick.clicked.connect(lambda _, p_idx=idx: self._assign_photo_to_selected_slot(p_idx))
            h_photos_swap.addWidget(btn_pick)
        layout.addLayout(h_photos_swap)

        layout.addSpacing(6)
        # Thu phóng ảnh
        h_zoom = QHBoxLayout()
        h_zoom.addWidget(QLabel("Thu phóng ảnh:"))
        self.lbl_slot_zoom_val = QLabel("100%")
        self.lbl_slot_zoom_val.setStyleSheet("color: #D4AF37; font-weight: bold;")
        h_zoom.addWidget(self.lbl_slot_zoom_val)
        h_zoom.addStretch()
        layout.addLayout(h_zoom)

        self.slider_slot_zoom = QSlider(Qt.Horizontal)
        self.slider_slot_zoom.setRange(100, 200)
        self.slider_slot_zoom.setValue(100)
        self.slider_slot_zoom.valueChanged.connect(self._on_slot_zoom_slider_changed)
        layout.addWidget(self.slider_slot_zoom)

        # Nút căn giữa lại tâm
        btn_center_slot = QPushButton("🎯 Căn Giữa Khuôn Mặt")
        btn_center_slot.setFixedHeight(40)
        btn_center_slot.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; border-radius: 6px; color: #E2E8F0; font-weight: bold; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; }"
        )
        btn_center_slot.clicked.connect(self._reset_selected_slot_pan)
        layout.addWidget(btn_center_slot)

        # Chế độ căn ảnh: Lấp đầy vs Toàn ảnh
        h_fit = QHBoxLayout()
        btn_fit_cover = QPushButton("Lấp Đầy Khung")
        btn_fit_cover.setFixedHeight(36)
        btn_fit_cover.setStyleSheet("background-color: #121C30; border: 1px solid #28395E; border-radius: 6px; color: #CBD5E1; font-weight: bold;")
        btn_fit_cover.clicked.connect(lambda: self._set_slot_fit_mode("cover"))
        h_fit.addWidget(btn_fit_cover)

        btn_fit_contain = QPushButton("Hiển Thị Toàn Ảnh")
        btn_fit_contain.setFixedHeight(36)
        btn_fit_contain.setStyleSheet("background-color: #121C30; border: 1px solid #28395E; border-radius: 6px; color: #CBD5E1; font-weight: bold;")
        btn_fit_contain.clicked.connect(lambda: self._set_slot_fit_mode("contain"))
        h_fit.addWidget(btn_fit_contain)
        layout.addLayout(h_fit)

        layout.addStretch()
        return widget

    def _build_tab_text(self) -> QWidget:
        """Tab thêm lời chúc tiệc cưới / sinh nhật."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel("<b>Mẫu lời chúc nhanh:</b>"))
        grid_presets = QGridLayout()
        presets = [
            "💍 Happy Wedding",
            "👰 Cô Dâu & Chú Rể",
            "🎂 Chúc Mừng Sinh Nhật",
            "✨ Trăm Năm Hạnh Phúc",
            "🥂 Kỷ Niệm Đáng Nhớ",
            "❤️ Forever & Always",
        ]
        btn_preset_style = (
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; border-radius: 6px; "
            "color: #F8FAFC; font-size: 11px; font-weight: bold; min-height: 36px; padding: 2px 6px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; background-color: #17243E; }"
        )
        for idx, p_text in enumerate(presets):
            btn_p = QPushButton(p_text)
            btn_p.setStyleSheet(btn_preset_style)
            btn_p.clicked.connect(lambda _, txt=p_text: self._set_text_input(txt))
            grid_presets.addWidget(btn_p, idx // 2, idx % 2)
        layout.addLayout(grid_presets)

        layout.addWidget(QLabel("<b>Nội dung chữ tùy chỉnh:</b>"))
        self.txt_guest_input = QLineEdit()
        self.txt_guest_input.setPlaceholderText("Nhập tên, ngày hoặc lời chúc...")
        self.txt_guest_input.setFixedHeight(38)
        self.txt_guest_input.setStyleSheet(
            "QLineEdit { background: #070A12; color: #FDF4DC; border: 1.5px solid #28395E; border-radius: 8px; padding: 0 10px; font-size: 13px; font-weight: bold; }"
            "QLineEdit:focus { border: 1.5px solid #D4AF37; }"
        )
        layout.addWidget(self.txt_guest_input)

        # Chọn phông chữ
        h_font = QHBoxLayout()
        h_font.addWidget(QLabel("Phông chữ:"))
        self.combo_guest_fonts = QComboBox()
        self.combo_guest_fonts.setFixedHeight(34)
        FontRegistry.initialize()
        for f_item in FontRegistry.list_fonts("all"):
            self.combo_guest_fonts.addItem(f"{f_item.display_name}", f_item.family_name)
        h_font.addWidget(self.combo_guest_fonts, 1)
        layout.addLayout(h_font)

        # Chọn màu sắc
        layout.addWidget(QLabel("<b>Màu chữ:</b>"))
        h_colors = QHBoxLayout()
        colors = [
            ("#D4AF37", "Vàng"),
            ("#FFFFFF", "Trắng"),
            ("#FB7185", "Hồng"),
            ("#E11D48", "Đỏ"),
            ("#0F172A", "Đen"),
        ]
        self._selected_text_color = "#D4AF37"
        for hex_col, name in colors:
            btn_c = QPushButton(name)
            btn_c.setFixedHeight(32)
            btn_c.setStyleSheet(
                f"QPushButton {{ background-color: {hex_col}; color: {'#000' if hex_col in ('#FFFFFF', '#D4AF37', '#FB7185') else '#FFF'}; "
                "border: 1px solid #475569; border-radius: 6px; font-weight: bold; font-size: 11px; }"
            )
            btn_c.clicked.connect(lambda _, c=hex_col: self._on_text_color_chosen(c))
            h_colors.addWidget(btn_c)
        layout.addLayout(h_colors)

        # Nút đặt chữ lên khung
        btn_add_text = QPushButton("➕ Đặt Chữ Lên Khung")
        btn_add_text.setFixedHeight(44)
        btn_add_text.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F5DE88, stop:0.4 #E5C158, stop:1 #C59B27); "
            "color: #070A12; font-weight: 900; font-size: 14px; border-radius: 8px; border: 1px solid #FDF4DC; }"
            "QPushButton:hover { background: #E5C158; }"
        )
        btn_add_text.clicked.connect(self._add_guest_text)
        layout.addWidget(btn_add_text)

        # Nút xóa chữ đang chọn
        btn_del_text = QPushButton("🗑️ Xóa Chữ Đang Chọn")
        btn_del_text.setFixedHeight(36)
        btn_del_text.setStyleSheet(
            "QPushButton { background-color: #261014; border: 1px solid #7F1D1D; color: #FCA5A5; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3F141B; border: 1px solid #DC2626; }"
        )
        btn_del_text.clicked.connect(self._delete_selected_text)
        layout.addWidget(btn_del_text)

        layout.addStretch()
        return widget

    def _build_tab_stickers(self) -> QWidget:
        """Tab chọn và dán sticker trang trí."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<b>Chạm sticker để dán lên khung ảnh:</b>"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        grid = QGridLayout(scroll_content)
        grid.setSpacing(10)

        # Quét các sticker trong Assets/Stickers/
        categories = ["wedding", "birthday", "fun"]
        all_stickers = []
        for cat in categories:
            cat_dir = os.path.join(STICKERS_DIR, cat)
            if os.path.exists(cat_dir):
                for f in os.listdir(cat_dir):
                    if f.lower().endswith(".png"):
                        all_stickers.append(os.path.join(cat_dir, f))

        col = 0
        row = 0
        for st_path in all_stickers:
            btn_st = QPushButton()
            btn_st.setFixedSize(70, 70)
            btn_st.setCursor(Qt.PointingHandCursor)
            pix = QPixmap(st_path)
            if not pix.isNull():
                btn_st.setIcon(pix.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                btn_st.setIconSize(QSize(56, 56))
            btn_st.setStyleSheet(
                "QPushButton { background-color: #121C30; border: 1px solid #28395E; border-radius: 8px; }"
                "QPushButton:hover { border: 1.5px solid #D4AF37; background-color: #17243E; }"
            )
            btn_st.clicked.connect(lambda _, p=st_path: self._add_sticker(p))
            grid.addWidget(btn_st, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Xóa sticker đang chọn
        btn_del_sticker = QPushButton("🗑️ Xóa Hình Dán Đang Chọn")
        btn_del_sticker.setFixedHeight(38)
        btn_del_sticker.setStyleSheet(
            "QPushButton { background-color: #261014; border: 1px solid #7F1D1D; color: #FCA5A5; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3F141B; border: 1px solid #DC2626; }"
        )
        btn_del_sticker.clicked.connect(self._delete_selected_sticker)
        layout.addWidget(btn_del_sticker)

        return widget

    # -----------------------------------------------------------------
    # SỰ KIỆN TƯƠNG TÁC GIAO DIỆN
    # -----------------------------------------------------------------
    def _switch_frame(self, frame_id: str):
        target = self.frame_mgr.get_frame(frame_id)
        if not target:
            return
        self.current_template = copy.deepcopy(target)
        self._ensure_slots_assigned()
        self._push_history()
        self.canvas.set_template_and_photos(self.current_template, self.photos)

    def _on_captured_photo_clicked(self, photo_index: int):
        for th in self.thumb_widgets:
            th.set_selected(th.photo_index == photo_index)

        # Nếu đang chọn một ô ảnh trên canvas, gán ngay ảnh này vào ô đó
        if self.canvas.selected_type == "slot" and 0 <= self.canvas.selected_index < len(self.current_template.slots):
            slot = self.current_template.slots[self.canvas.selected_index]
            slot.photo_index = photo_index
            self._push_history()
            self.canvas.update_preview()

    def _assign_photo_to_selected_slot(self, photo_index: int):
        if not self.current_template:
            return
        idx = self.canvas.selected_index if self.canvas.selected_type == "slot" else 0
        if 0 <= idx < len(self.current_template.slots):
            self.current_template.slots[idx].photo_index = photo_index
            self._push_history()
            self.canvas.update_preview()

    def _on_slot_zoom_slider_changed(self, value: int):
        self.lbl_slot_zoom_val.setText(f"{value}%")
        if self.canvas.selected_type == "slot" and 0 <= self.canvas.selected_index < len(self.current_template.slots):
            slot = self.current_template.slots[self.canvas.selected_index]
            slot.zoom = value / 100.0
            self.canvas.update_preview()

    def _reset_selected_slot_pan(self):
        if self.canvas.selected_type == "slot" and 0 <= self.canvas.selected_index < len(self.current_template.slots):
            slot = self.current_template.slots[self.canvas.selected_index]
            slot.crop_offset_x = 0.0
            slot.crop_offset_y = 0.0
            slot.zoom = 1.0
            self.slider_slot_zoom.setValue(100)
            self._push_history()
            self.canvas.update_preview()

    def _set_slot_fit_mode(self, mode: str):
        if self.canvas.selected_type == "slot" and 0 <= self.canvas.selected_index < len(self.current_template.slots):
            slot = self.current_template.slots[self.canvas.selected_index]
            slot.fit_mode = mode
            self._push_history()
            self.canvas.update_preview()

    def _set_text_input(self, text: str):
        self.txt_guest_input.setText(text)

    def _on_text_color_chosen(self, hex_color: str):
        self._selected_text_color = hex_color
        if self.canvas.selected_type == "text" and 0 <= self.canvas.selected_index < len(self.current_template.text_layers):
            txt = self.current_template.text_layers[self.canvas.selected_index]
            txt.font_color = hex_color
            self._push_history()
            self.canvas.update_preview()

    def _add_guest_text(self):
        content = self.txt_guest_input.text().strip()
        if not content:
            QMessageBox.information(self, "Lời Chúc", "Vui lòng nhập nội dung hoặc chọn mẫu lời chúc nhanh.")
            return

        if not self.current_template:
            return

        tw, th = self.current_template.canvas_size
        new_id = f"txt_guest_{len(self.current_template.text_layers) + 1}"
        font_family = self.combo_guest_fonts.currentData() or "Playfair Display"

        new_txt = TextLayer(
            id=new_id,
            text=content,
            x=tw // 2,
            y=th - 160,
            font_size=42,
            font_color=self._selected_text_color,
            font_name=font_family,
            alignment="center",
            is_bold=True,
            position_mode="custom"
        )
        self.current_template.text_layers.append(new_txt)
        self._push_history()
        self.canvas.selected_type = "text"
        self.canvas.selected_index = len(self.current_template.text_layers) - 1
        self.canvas.update_preview()

    def _delete_selected_text(self):
        if self.canvas.selected_type == "text" and 0 <= self.canvas.selected_index < len(self.current_template.text_layers):
            self.current_template.text_layers.pop(self.canvas.selected_index)
            self.canvas.selected_type = None
            self.canvas.selected_index = -1
            self._push_history()
            self.canvas.update_preview()

    def _add_sticker(self, sticker_path: str):
        if not self.current_template or not os.path.exists(sticker_path):
            return

        tw, th = self.current_template.canvas_size
        new_id = f"sticker_{len(self.current_template.logo_layers) + 1}"

        # Đọc kích thước gốc
        try:
            with Image.open(sticker_path) as im:
                ow, oh = im.size
        except Exception:
            ow, oh = 256, 256

        new_st = LogoLayer(
            id=new_id,
            image_path=sticker_path,
            x=(tw - 160) // 2,
            y=(th - 160) // 2,
            w=160,
            h=160,
            scale=0.6,
            original_w=ow,
            original_h=oh,
            position_mode="custom"
        )
        self.current_template.logo_layers.append(new_st)
        self._push_history()
        self.canvas.selected_type = "sticker"
        self.canvas.selected_index = len(self.current_template.logo_layers) - 1
        self.canvas.update_preview()

    def _delete_selected_sticker(self):
        if self.canvas.selected_type == "sticker" and 0 <= self.canvas.selected_index < len(self.current_template.logo_layers):
            self.current_template.logo_layers.pop(self.canvas.selected_index)
            self.canvas.selected_type = None
            self.canvas.selected_index = -1
            self._push_history()
            self.canvas.update_preview()

    def _on_canvas_slot_selected(self, slot_idx: int):
        self.tabs_control.setCurrentIndex(1)  # Chuyển sang tab Ô ảnh
        if 0 <= slot_idx < len(self.current_template.slots):
            slot = self.current_template.slots[slot_idx]
            photo_num = (slot.photo_index % len(self.photos)) + 1 if self.photos else 1
            self.lbl_selected_slot.setText(f"👉 Đang chọn: Ô #{slot.id} (Ảnh #{photo_num})")
            self.slider_slot_zoom.setValue(int(getattr(slot, 'zoom', 1.0) * 100))

    def _on_canvas_text_selected(self, text_idx: int):
        self.tabs_control.setCurrentIndex(2)  # Chuyển sang tab Chữ
        if 0 <= text_idx < len(self.current_template.text_layers):
            txt = self.current_template.text_layers[text_idx]
            self.txt_guest_input.setText(txt.text)

    def _on_canvas_sticker_selected(self, sticker_idx: int):
        self.tabs_control.setCurrentIndex(3)  # Chuyển sang tab Sticker

    def _sync_ui_with_selected_item(self):
        self.canvas.selected_type = None
        self.canvas.selected_index = -1
        self.canvas.update_preview()

    def _on_toggle_preview_mode(self, checked: bool):
        self.canvas.preview_mode_only = checked
        self.canvas.update()

    def _on_retake_clicked(self):
        confirm = QMessageBox.question(
            self,
            "Chụp Lại Ảnh",
            "Bạn có chắc muốn bỏ lượt chụp này và chụp lại từ đầu không?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.is_retake = True
            self.reject()

    def _on_confirm_and_render(self):
        """Xác nhận render ảnh 300 DPI thành phẩm hoàn chỉnh."""
        if not self.current_template or not self.photos:
            self.reject()
            return

        try:
            self.final_composite = FrameDesigner.render_composite(
                photos=self.photos,
                template=self.current_template,
                event_info={"name": self.event_name}
            )
            self.accept()
        except Exception as e:
            logger.error(f"Lỗi xuất ảnh 300 DPI từ Guest Review: {e}", exc_info=True)
            QMessageBox.warning(self, "Lỗi Xuất Ảnh", f"Không thể tạo ảnh thành phẩm: {e}")
