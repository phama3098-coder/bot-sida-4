"""
1998 TEAM — Frame Designer & Template Studio
Visual interactive layout editor for 2x6 and 4x6 print formats,
SVG/PNG/JPG multi-format import, auto photo fitting (cover/contain/center/face),
multiline visual text editing, aspect-ratio locked logo positioning,
and zip backup/restore.
"""

import os
import shutil
import copy
from typing import Optional, List, Tuple
from PIL import Image

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QLineEdit, QCheckBox, QScrollArea, QFileDialog, QMessageBox,
    QGroupBox, QInputDialog, QSizePolicy, QColorDialog, QDialog, QFormLayout,
    QRadioButton, QButtonGroup, QTextEdit, QFrame, QSlider
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QPoint, QRect, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QPen, QBrush, QFont

from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer, DPI_300_SIZES
from vietphotobooth.core.logger import get_logger

logger = get_logger()


class ImportFrameDialog(QDialog):
    """Hộp thoại nhập khung ảnh từ tệp PNG (trong suốt), JPG (nền kín) hoặc SVG vector."""

    def __init__(self, manager: FrameManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("1998 TEAM — Thêm & Nhập Khung Ảnh Mới")
        self.setMinimumSize(820, 560)
        self.selected_file_path = ""
        self.imported_template: Optional[FrameTemplate] = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(18)

        # CỘT TRÁI: XEM TRƯỚC HÌNH ẢNH
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel("<b>Xem Trước Tệp Khung:</b>"))

        self.lbl_preview = QLabel("Chưa chọn tệp ảnh/vector...")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet(
            "background-color: #070A12; border: 2px dashed #28395E; border-radius: 10px; color: #94A3B8;"
        )
        self.lbl_preview.setMinimumSize(280, 420)
        left_box.addWidget(self.lbl_preview, 1)

        btn_browse = QPushButton("📁 Chọn Tệp (PNG / JPG / SVG)...")
        btn_browse.setObjectName("btn_champagne")
        btn_browse.clicked.connect(self._browse_file)
        left_box.addWidget(btn_browse)

        main_layout.addLayout(left_box, 4)

        # CỘT PHẢI: BIỂU MẪU CẤU HÌNH KHUNG
        right_box = QVBoxLayout()
        form = QFormLayout()
        form.setSpacing(12)

        self.txt_file = QLineEdit()
        self.txt_file.setReadOnly(True)
        self.txt_file.setPlaceholderText("Đường dẫn tệp khung...")
        form.addRow("Tệp Đã Chọn:", self.txt_file)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ví dụ: Tiệc Cưới Tuấn & Lan (Dải 2x6)")
        form.addRow("Tên Mẫu Khung:*", self.txt_name)

        self.combo_cat = QComboBox()
        self.combo_cat.addItems(["Wedding", "Birthday", "Corporate", "Custom"])
        form.addRow("Phân Loại:*", self.combo_cat)

        self.combo_type = QComboBox()
        self.combo_type.addItem("2x6 inch — Dải dọc 3 hoặc 4 ảnh (600x1800 px)", "2x6")
        self.combo_type.addItem("4x6 inch Khổ Đứng — Lưới ảnh (1200x1800 px)", "4x6_portrait")
        self.combo_type.addItem("4x6 inch Khổ Ngang — Doanh nghiệp / Gia đình (1800x1200 px)", "4x6_landscape")
        self.combo_type.addItem("4x6 inch Ghép Đôi 2 Dải 2x6 — Máy in DNP RX1HS Cắt Đôi", "4x6_dual")
        form.addRow("Khổ In Ấn (300 DPI):*", self.combo_type)

        # Kiểu lớp hiển thị
        self.rb_overlay = QRadioButton("Khung Viền Nổi Lên Trên (Overlay — Ảnh chụp nằm dưới khung)")
        self.rb_bg = QRadioButton("Hình Nền Khung (Background — Ảnh chụp nằm trên nền)")
        self.rb_overlay.setChecked(True)
        bg_grp = QButtonGroup(self)
        bg_grp.addButton(self.rb_overlay)
        bg_grp.addButton(self.rb_bg)
        l_layer = QVBoxLayout()
        l_layer.addWidget(self.rb_overlay)
        l_layer.addWidget(self.rb_bg)
        form.addRow("Kiểu Ghép Lớp:", l_layer)

        # Số lượng ô ảnh ban đầu
        self.combo_slots = QComboBox()
        self.combo_slots.addItems(["3 Ô Ảnh (Chuẩn tiệc cưới)", "4 Ô Ảnh (Chuẩn sinh nhật)", "2 Ô Ảnh (Khổ to)", "1 Ô Ảnh Đơn"])
        form.addRow("Số Ô Ảnh Ban Đầu:", self.combo_slots)

        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(70)
        self.txt_notes.setPlaceholderText("Ghi chú phong cách, hướng dẫn sử dụng...")
        form.addRow("Ghi Chú:", self.txt_notes)

        right_box.addLayout(form)
        right_box.addStretch()

        # Nút xác nhận / hủy
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Hủy Bỏ")
        btn_cancel.setObjectName("btn_secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_confirm = QPushButton("✅ Xác Nhận Nhập Khung")
        btn_confirm.setObjectName("btn_champagne")
        btn_confirm.clicked.connect(self._on_confirm)
        btn_box.addWidget(btn_confirm)

        right_box.addLayout(btn_box)
        main_layout.addLayout(right_box, 6)

    def _browse_file(self):
        filter_str = (
            "Tất Cả Định Dạng Khung (*.png *.jpg *.jpeg *.svg);;"
            "Ảnh PNG Trong Suốt (*.png);;Ảnh JPG/JPEG (*.jpg *.jpeg);;Vector SVG (*.svg)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Tệp Khung Ảnh", "", filter_str)
        if not path or not os.path.exists(path):
            return

        self.selected_file_path = path
        self.txt_file.setText(path)

        base_name = os.path.splitext(os.path.basename(path))[0]
        cleaned_name = base_name.replace("_", " ").title()
        if not self.txt_name.text().strip():
            self.txt_name.setText(cleaned_name)

        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            self.rb_bg.setChecked(True)
        else:
            self.rb_overlay.setChecked(True)

        try:
            if ext == ".svg":
                from PySide6.QtSvg import QSvgRenderer
                renderer = QSvgRenderer(path)
                if renderer.isValid():
                    qimg = QImage(300, 600, QImage.Format_ARGB32_Premultiplied)
                    qimg.fill(Qt.transparent)
                    p = QPainter(qimg)
                    renderer.render(p)
                    p.end()
                    pix = QPixmap.fromImage(qimg)
                    self.lbl_preview.setPixmap(
                        pix.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                else:
                    self.lbl_preview.setText(f"Tệp SVG: {os.path.basename(path)}")
            else:
                pix = QPixmap(path)
                self.lbl_preview.setPixmap(
                    pix.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        except Exception as e:
            self.lbl_preview.setText(f"Không thể tạo xem trước: {e}")

    def _on_confirm(self):
        if not self.selected_file_path or not os.path.exists(self.selected_file_path):
            QMessageBox.warning(self, "Thiếu Thông Tin", "Vui lòng bấm 'Chọn Tệp' để chọn file khung ảnh từ máy tính!")
            return

        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Thiếu Thông Tin", "Vui lòng nhập tên cho mẫu khung ảnh!")
            return

        category = self.combo_cat.currentText()
        strip_type = self.combo_type.currentData()
        layer_mode = "background" if self.rb_bg.isChecked() else "overlay"
        notes = self.txt_notes.toPlainText().strip()

        slot_choice = self.combo_slots.currentIndex()
        num_slots = [3, 4, 2, 1][slot_choice]

        imported = self.manager.import_external_frame(
            file_path=self.selected_file_path,
            template_name=name,
            category=category,
            strip_type=strip_type,
            layer_mode=layer_mode,
            notes=notes,
            num_slots=num_slots
        )

        if imported:
            self.imported_template = imported
            QMessageBox.information(
                self, "Thành Công", f"Đã nhập thành công mẫu khung: {imported.name}\nKhổ in: {imported.type} (300 DPI)"
            )
            self.accept()
        else:
            QMessageBox.critical(
                self, "Lỗi", "Không thể xử lý hoặc chuyển đổi tệp khung ảnh này. Vui lòng kiểm tra định dạng."
            )


class InteractiveCanvas(QWidget):
    """
    Vùng thiết kế khung ảnh trực quan tương tác chuột phong cách 1998 TEAM:
    - Kéo pan căn chỉnh vùng cắt ảnh (Crop Pan Offset) hoặc di chuyển ô ảnh (Move Slot).
    - Kéo thả lớp chữ (Text Layer) và lớp Logo trực tiếp trên bản vẽ.
    - Vẽ lưới tọa độ Grid, đường căn tâm, vùng an toàn (Safe Zone) và mép xén (Bleed).
    - Làm nổi bật đối tượng đang chọn với viền vàng Champagne Gold.
    """

    slot_selected = Signal(int)
    slot_moved = Signal(int, int, int)
    slot_crop_panned = Signal(int, float, float)
    text_selected = Signal(int)
    text_moved = Signal(int, int, int)
    logo_selected = Signal(int)
    logo_moved = Signal(int, int, int)
    drag_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.template: Optional[FrameTemplate] = None
        self.preview_pixmap: Optional[QPixmap] = None

        # Chế độ thao tác kéo chuột: "pan_crop" (căn ảnh) hoặc "move_slot" (di chuyển ô)
        self.drag_mode: str = "pan_crop"
        self.selected_item_type: str = "slot"  # "slot", "text", "logo", "none"
        self.selected_slot_index: int = 0
        self.selected_text_index: int = -1
        self.selected_logo_index: int = -1

        self.show_grid: bool = True
        self.snap_to_grid: bool = True
        self.show_guides: bool = True
        self.grid_size: int = 40  # 40px tại độ phân giải gốc 300 DPI

        # Trạng thái kéo chuột
        self._is_dragging: bool = False
        self._drag_start_pos: QPoint = QPoint()
        self._start_slot_x: int = 0
        self._start_slot_y: int = 0
        self._start_crop_ox: float = 0.0
        self._start_crop_oy: float = 0.0
        self._start_text_x: int = 0
        self._start_text_y: int = 0
        self._start_logo_x: int = 0
        self._start_logo_y: int = 0

    def set_template_preview(self, template: FrameTemplate, pixmap: QPixmap):
        self.template = template
        self.preview_pixmap = pixmap
        self.update()

    def set_drag_mode(self, mode: str):
        self.drag_mode = mode
        self.update()

    def _get_canvas_geometry(self) -> Tuple[float, float, float, float, float]:
        """Tính toán tỷ lệ thu phóng và vùng hiển thị canvas trên widget."""
        if not self.template:
            return 1.0, 0, 0, self.width(), self.height()

        cw, ch = self.template.canvas_size[0], self.template.canvas_size[1]
        avail_w = max(10, self.width() - 20)
        avail_h = max(10, self.height() - 20)

        scale = min(avail_w / float(cw), avail_h / float(ch))
        render_w = cw * scale
        render_h = ch * scale
        ox = (self.width() - render_w) / 2.0
        oy = (self.height() - render_h) / 2.0

        return scale, ox, oy, render_w, render_h

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Vẽ nền widget đen sâu
        painter.fillRect(self.rect(), QColor("#070A12"))

        if not self.template or not self.preview_pixmap:
            painter.setPen(QColor("#64748B"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Đang tải bản vẽ thiết kế khung...")
            return

        scale, ox, oy, rw, rh = self._get_canvas_geometry()

        # 2. Vẽ hình ảnh render preview khung
        render_rect = QRectF(ox, oy, rw, rh)
        painter.drawPixmap(render_rect.toRect(), self.preview_pixmap)

        # 3. Vẽ lưới tọa độ Grid (nếu bật)
        if self.show_grid and self.grid_size > 0:
            grid_pen = QPen(QColor(30, 45, 74, 110), 1, Qt.DotLine)
            painter.setPen(grid_pen)
            x_step = self.grid_size * scale
            curr_x = ox
            while curr_x < (ox + rw):
                painter.drawLine(curr_x, oy, curr_x, oy + rh)
                curr_x += x_step
            y_step = self.grid_size * scale
            curr_y = oy
            while curr_y < (oy + rh):
                painter.drawLine(ox, curr_y, ox + rw, curr_y)
                curr_y += y_step

        # 4. Vẽ vùng an toàn (Safe Zone) và Mép xén (Bleed Margin) (nếu bật)
        if self.show_guides:
            bleed_scale = self.template.bleed_px * scale
            bleed_pen = QPen(QColor(239, 68, 68, 160), 1, Qt.DashLine)
            painter.setPen(bleed_pen)
            painter.drawRect(QRectF(ox + bleed_scale, oy + bleed_scale, rw - 2 * bleed_scale, rh - 2 * bleed_scale))

            safe_scale = self.template.safe_zone_px * scale
            safe_pen = QPen(QColor(212, 175, 55, 180), 1, Qt.DashLine)
            painter.setPen(safe_pen)
            painter.drawRect(QRectF(ox + safe_scale, oy + safe_scale, rw - 2 * safe_scale, rh - 2 * safe_scale))

            if self.template.is_dual_strip:
                cut_x = ox + (rw / 2.0)
                cut_pen = QPen(QColor(148, 163, 184, 200), 2, Qt.DashLine)
                painter.setPen(cut_pen)
                painter.drawLine(cut_x, oy, cut_x, oy + rh)

        # 5. Vẽ viền & nhãn tương tác cho từng ô PhotoSlot
        for idx, slot in enumerate(self.template.slots):
            sx = ox + slot.x * scale
            sy = oy + slot.y * scale
            sw = slot.w * scale
            sh = slot.h * scale
            slot_rect = QRectF(sx, sy, sw, sh)

            is_selected = (self.selected_item_type == "slot" and idx == self.selected_slot_index)

            if is_selected:
                slot_pen = QPen(QColor("#D4AF37"), 3, Qt.SolidLine)
                painter.setPen(slot_pen)
                painter.setBrush(QColor(212, 175, 55, 30))
                painter.drawRect(slot_rect)

                # Vẽ 4 góc điều hướng
                handle_size = 8
                painter.setBrush(QColor("#FFFFFF"))
                painter.setPen(QColor("#070A12"))
                painter.drawRect(QRectF(sx - handle_size / 2, sy - handle_size / 2, handle_size, handle_size))
                painter.drawRect(QRectF(sx + sw - handle_size / 2, sy - handle_size / 2, handle_size, handle_size))
                painter.drawRect(QRectF(sx - handle_size / 2, sy + sh - handle_size / 2, handle_size, handle_size))
                painter.drawRect(QRectF(sx + sw - handle_size / 2, sy + sh - handle_size / 2, handle_size, handle_size))

                # Huy hiệu thông số ô ảnh đang chọn
                fit_text = "Lấp Đầy (Cover)" if getattr(slot, 'fit_mode', 'cover') == "cover" else "Toàn Ảnh (Fit)"
                zoom_val = int(getattr(slot, 'zoom', 1.0) * 100)
                badge_text = f"Ô #{slot.id} • {fit_text} • {zoom_val}%"
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.setPen(QColor("#FFFFFF"))
                painter.setBrush(QColor(11, 19, 43, 225))
                painter.drawRoundedRect(QRectF(sx + 6, sy + 6, 220, 24), 4, 4)
                painter.drawText(QRectF(sx + 10, sy + 6, 212, 24), Qt.AlignVCenter | Qt.AlignLeft, badge_text)
            else:
                slot_pen = QPen(QColor(56, 189, 248, 140), 1.5, Qt.DashLine)
                painter.setPen(slot_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(slot_rect)

                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.setPen(QColor("#38BDF8"))
                painter.drawText(QRectF(sx + 6, sy + 6, 80, 20), Qt.AlignLeft, f"#{slot.id}")

        # 6. Vẽ viền tương tác cho lớp Logo đang chọn
        for idx, logo in enumerate(self.template.logo_layers):
            if self.selected_item_type == "logo" and idx == self.selected_logo_index:
                scale_val = getattr(logo, 'scale', 1.0)
                lw = (getattr(logo, 'original_w', logo.w) * scale_val if getattr(logo, 'original_w', 0) else logo.w) * scale
                lh = (getattr(logo, 'original_h', logo.h) * scale_val if getattr(logo, 'original_h', 0) else logo.h) * scale
                lx = ox + logo.x * scale
                ly = oy + logo.y * scale

                logo_pen = QPen(QColor("#38BDF8"), 2, Qt.DashLine)
                painter.setPen(logo_pen)
                painter.setBrush(QColor(56, 189, 248, 25))
                painter.drawRect(QRectF(lx, ly, lw, lh))

                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#38BDF8"))
                painter.drawText(QRectF(lx + 4, ly + 4, 120, 18), Qt.AlignLeft, f"🖼️ Logo #{idx+1}")

        # 7. Vẽ viền tương tác cho lớp Text đang chọn
        for idx, txt in enumerate(self.template.text_layers):
            if self.selected_item_type == "text" and idx == self.selected_text_index:
                tx = ox + txt.x * scale - 120 * scale
                ty = oy + txt.y * scale
                tw = 240 * scale
                th = (txt.font_size * 2) * scale

                txt_pen = QPen(QColor("#D4AF37"), 2, Qt.DashLine)
                painter.setPen(txt_pen)
                painter.setBrush(QColor(212, 175, 55, 25))
                painter.drawRect(QRectF(tx, ty, tw, th))

                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#D4AF37"))
                painter.drawText(QRectF(tx + 4, ty + 2, 120, 18), Qt.AlignLeft, f"📝 Chữ #{idx+1}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.template:
            scale, ox, oy, rw, rh = self._get_canvas_geometry()
            mx = event.position().x()
            my = event.position().y()

            cx = (mx - ox) / scale
            cy = (my - oy) / scale

            # 1. Kiểm tra click trúng Logo layers trước (lớp trên)
            clicked_logo = -1
            for idx in reversed(range(len(self.template.logo_layers))):
                l = self.template.logo_layers[idx]
                scale_val = getattr(l, 'scale', 1.0)
                lw = getattr(l, 'original_w', l.w) * scale_val if getattr(l, 'original_w', 0) else l.w
                lh = getattr(l, 'original_h', l.h) * scale_val if getattr(l, 'original_h', 0) else l.h
                if l.x <= cx <= (l.x + lw) and l.y <= cy <= (l.y + lh):
                    clicked_logo = idx
                    break

            if clicked_logo != -1:
                self.selected_item_type = "logo"
                self.selected_logo_index = clicked_logo
                self._is_dragging = True
                self._drag_start_pos = event.pos()
                l = self.template.logo_layers[clicked_logo]
                self._start_logo_x = l.x
                self._start_logo_y = l.y
                self.logo_selected.emit(clicked_logo)
                self.update()
                return

            # 2. Kiểm tra click trúng Text layers
            clicked_text = -1
            for idx in reversed(range(len(self.template.text_layers))):
                t = self.template.text_layers[idx]
                approx_h = t.font_size * 2
                if (t.y - 10) <= cy <= (t.y + approx_h + 10):
                    clicked_text = idx
                    break

            if clicked_text != -1:
                self.selected_item_type = "text"
                self.selected_text_index = clicked_text
                self._is_dragging = True
                self._drag_start_pos = event.pos()
                t = self.template.text_layers[clicked_text]
                self._start_text_x = t.x
                self._start_text_y = t.y
                self.text_selected.emit(clicked_text)
                self.update()
                return

            # 3. Kiểm tra click trúng Photo Slots
            clicked_slot = -1
            for idx in reversed(range(len(self.template.slots))):
                s = self.template.slots[idx]
                if s.x <= cx <= (s.x + s.w) and s.y <= cy <= (s.y + s.h):
                    clicked_slot = idx
                    break

            if clicked_slot != -1:
                self.selected_item_type = "slot"
                self.selected_slot_index = clicked_slot
                self._is_dragging = True
                self._drag_start_pos = event.pos()
                s = self.template.slots[clicked_slot]
                self._start_slot_x = s.x
                self._start_slot_y = s.y
                self._start_crop_ox = getattr(s, 'crop_offset_x', 0.0)
                self._start_crop_oy = getattr(s, 'crop_offset_y', 0.0)
                self.slot_selected.emit(clicked_slot)
                self.update()
                return

            # Click ra ngoài vùng đối tượng
            self.selected_item_type = "none"
            self.update()

    def mouseMoveEvent(self, event):
        if not self._is_dragging or not self.template:
            return

        scale, ox, oy, rw, rh = self._get_canvas_geometry()
        dx = (event.pos().x() - self._drag_start_pos.x()) / scale
        dy = (event.pos().y() - self._drag_start_pos.y()) / scale

        # 1. Kéo lớp Logo
        if self.selected_item_type == "logo" and 0 <= self.selected_logo_index < len(self.template.logo_layers):
            l = self.template.logo_layers[self.selected_logo_index]
            l.x = max(0, int(self._start_logo_x + dx))
            l.y = max(0, int(self._start_logo_y + dy))
            l.position_mode = "custom"
            self.logo_moved.emit(self.selected_logo_index, l.x, l.y)
            self.update()
            return

        # 2. Kéo lớp Text
        if self.selected_item_type == "text" and 0 <= self.selected_text_index < len(self.template.text_layers):
            t = self.template.text_layers[self.selected_text_index]
            t.x = max(0, int(self._start_text_x + dx))
            t.y = max(0, int(self._start_text_y + dy))
            t.position_mode = "custom"
            self.text_moved.emit(self.selected_text_index, t.x, t.y)
            self.update()
            return

        # 3. Kéo ô Photo Slot
        if self.selected_item_type == "slot" and 0 <= self.selected_slot_index < len(self.template.slots):
            s = self.template.slots[self.selected_slot_index]

            if self.drag_mode == "pan_crop":
                # Kéo dịch chuyển vùng cắt (Pan Crop Offset)
                # Di chuột sang trái/phải sẽ kéo khung crop ngược hướng để di chuyển nội dung ảnh
                norm_dx = - (dx / max(1.0, s.w * 0.4))
                norm_dy = - (dy / max(1.0, s.h * 0.4))
                new_ox = max(-1.0, min(1.0, self._start_crop_ox + norm_dx))
                new_oy = max(-1.0, min(1.0, self._start_crop_oy + norm_dy))
                s.crop_offset_x = round(new_ox, 3)
                s.crop_offset_y = round(new_oy, 3)
                self.slot_crop_panned.emit(self.selected_slot_index, s.crop_offset_x, s.crop_offset_y)
                self.update()
            else:
                # Di chuyển tọa độ ô ảnh (Move Slot)
                new_x = int(self._start_slot_x + dx)
                new_y = int(self._start_slot_y + dy)

                if self.snap_to_grid and self.grid_size > 0:
                    snap_step = 20
                    new_x = round(new_x / snap_step) * snap_step
                    new_y = round(new_y / snap_step) * snap_step

                cw, ch = self.template.canvas_size[0], self.template.canvas_size[1]
                new_x = max(0, min(new_x, cw - s.w))
                new_y = max(0, min(new_y, ch - s.h))

                s.x = new_x
                s.y = new_y
                self.slot_moved.emit(self.selected_slot_index, new_x, new_y)
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.drag_finished.emit()


class FrameDesignerPage(QWidget):
    """Trang thiết kế khung in ảnh Photobooth trực quan phong cách 1998 TEAM."""

    frame_changed = Signal(str)

    def minimumSizeHint(self) -> QSize:
        return QSize(750, 400)

    def __init__(self, frame_manager: FrameManager, parent=None):
        super().__init__(parent)
        self.manager = frame_manager
        self.current_frame: Optional[FrameTemplate] = None
        self._is_updating_ui = False

        self._init_ui()
        self._load_frames_to_combo()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(14)

        # ==============================================================
        # CỘT TRÁI: BẢN VẼ TƯƠNG TÁC CHUỘT & THANH CÔNG CỤ THAO TÁC
        # ==============================================================
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        # THANH CÔNG CỤ TRÊN CÙNG: HÀNG 1 (LỰA CHỌN & LƯU KHUNG)
        top_bar_1 = QHBoxLayout()
        top_bar_1.setSpacing(8)

        lbl_k = QLabel("<b style='color:#D4AF37;'>Khung:</b>")
        top_bar_1.addWidget(lbl_k)

        self.combo_frames = QComboBox()
        self.combo_frames.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_frames.setMinimumContentsLength(16)
        self.combo_frames.setMaximumWidth(260)
        self.combo_frames.currentIndexChanged.connect(self._on_frame_selected)
        top_bar_1.addWidget(self.combo_frames)

        btn_import = QPushButton("➕ Nhập Khung")
        btn_import.setObjectName("btn_champagne")
        btn_import.clicked.connect(self._open_import_dialog)
        top_bar_1.addWidget(btn_import)

        btn_save = QPushButton("💾 Lưu Khung")
        btn_save.setObjectName("btn_champagne")
        btn_save.clicked.connect(self._save_frame)
        top_bar_1.addWidget(btn_save)

        btn_refresh = QPushButton("🔄 Làm Mới")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(lambda: self._update_preview(full_render=True))
        top_bar_1.addWidget(btn_refresh)

        top_bar_1.addStretch()
        left_layout.addLayout(top_bar_1)

        # THANH CÔNG CỤ TRÊN CÙNG: HÀNG 2 (QUẢN LÝ & SAO LƯU ZIP)
        top_bar_2 = QHBoxLayout()
        top_bar_2.setSpacing(6)

        btn_dup = QPushButton("📋 Nhân Bản")
        btn_dup.setObjectName("btn_secondary")
        btn_dup.clicked.connect(self._duplicate_frame)
        top_bar_2.addWidget(btn_dup)

        btn_rename = QPushButton("✏️ Đổi Tên")
        btn_rename.setObjectName("btn_secondary")
        btn_rename.clicked.connect(self._rename_frame)
        top_bar_2.addWidget(btn_rename)

        btn_delete = QPushButton("🗑️ Xóa")
        btn_delete.setObjectName("btn_danger")
        btn_delete.clicked.connect(self._delete_frame)
        top_bar_2.addWidget(btn_delete)

        btn_backup = QPushButton("📦 Sao Lưu")
        btn_backup.setObjectName("btn_secondary")
        btn_backup.clicked.connect(self._backup_zip)
        top_bar_2.addWidget(btn_backup)

        btn_restore = QPushButton("📥 Khôi Phục")
        btn_restore.setObjectName("btn_secondary")
        btn_restore.clicked.connect(self._restore_zip)
        top_bar_2.addWidget(btn_restore)

        top_bar_2.addStretch()
        left_layout.addLayout(top_bar_2)

        # CANVAS TƯƠNG TÁC CHUỘT
        self.canvas = InteractiveCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumSize(250, 250)
        self.canvas.slot_selected.connect(self._on_slot_selected_from_canvas)
        self.canvas.slot_moved.connect(self._on_slot_moved_from_canvas)
        self.canvas.slot_crop_panned.connect(self._on_slot_crop_panned_from_canvas)
        self.canvas.text_selected.connect(self._on_text_selected_from_canvas)
        self.canvas.text_moved.connect(self._on_text_moved_from_canvas)
        self.canvas.logo_selected.connect(self._on_logo_selected_from_canvas)
        self.canvas.logo_moved.connect(self._on_logo_moved_from_canvas)
        self.canvas.drag_finished.connect(lambda: self._update_preview(full_render=True))
        left_layout.addWidget(self.canvas, 1)

        # THANH CÔNG CỤ CHẾ ĐỘ KÉO CHUỘT VÀ LƯỚI BẢN VẼ
        tools_bar = QHBoxLayout()
        tools_bar.setSpacing(8)

        # Nút chuyển chế độ kéo chuột: Căn ảnh vs Di chuyển ô
        self.btn_mode_crop = QPushButton("🖼️ Kéo Căn Ảnh")
        self.btn_mode_crop.setCheckable(True)
        self.btn_mode_crop.setChecked(True)
        self.btn_mode_crop.setObjectName("btn_champagne")

        self.btn_mode_move = QPushButton("📐 Di Chuyển Ô")
        self.btn_mode_move.setCheckable(True)
        self.btn_mode_move.setObjectName("btn_secondary")

        mode_grp = QButtonGroup(self)
        mode_grp.addButton(self.btn_mode_crop)
        mode_grp.addButton(self.btn_mode_move)
        self.btn_mode_crop.toggled.connect(self._on_drag_mode_toggled)

        tools_bar.addWidget(self.btn_mode_crop)
        tools_bar.addWidget(self.btn_mode_move)

        # Lưới và vùng căn
        self.chk_grid = QCheckBox("Lưới (Grid)")
        self.chk_grid.setChecked(True)
        self.chk_grid.toggled.connect(lambda c: setattr(self.canvas, 'show_grid', c) or self.canvas.update())
        tools_bar.addWidget(self.chk_grid)

        self.chk_snap = QCheckBox("Hút (Snap)")
        self.chk_snap.setChecked(True)
        self.chk_snap.toggled.connect(lambda c: setattr(self.canvas, 'snap_to_grid', c))
        tools_bar.addWidget(self.chk_snap)

        self.chk_guides = QCheckBox("Vùng Cắt (Bleed)")
        self.chk_guides.setChecked(True)
        self.chk_guides.toggled.connect(lambda c: setattr(self.canvas, 'show_guides', c) or self.canvas.update())
        tools_bar.addWidget(self.chk_guides)

        tools_bar.addStretch()

        self.lbl_warnings = QLabel("300 DPI")
        self.lbl_warnings.setStyleSheet("color: #10B981; font-weight: 500;")
        tools_bar.addWidget(self.lbl_warnings)

        left_layout.addLayout(tools_bar)
        main_layout.addLayout(left_layout, 6)

        # ==============================================================
        # CỘT PHẢI: BẢNG ĐIỀU KHIỂN BỐ CỤC (CUỘN ĐỘC LẬP & TRỰC QUAN)
        # ==============================================================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(280)
        scroll.setMaximumWidth(460)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        right_layout = QVBoxLayout(scroll_content)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(12)

        # --------------------------------------------------------------
        # 1. THUỘC TÍNH KHUNG IN
        # --------------------------------------------------------------
        grp_props = QGroupBox("1. Thuộc Tính Khung In")
        form_props = QFormLayout(grp_props)
        form_props.setSpacing(8)

        self.txt_name = QLineEdit()
        form_props.addRow("Tên Khung:", self.txt_name)

        self.combo_cat = QComboBox()
        self.combo_cat.addItems(["Wedding", "Birthday", "Corporate", "Custom"])
        form_props.addRow("Phân Loại:", self.combo_cat)

        self.combo_type = QComboBox()
        self.combo_type.addItems(["2x6", "4x6_portrait", "4x6_landscape", "4x6_dual"])
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        form_props.addRow("Khổ In Ấn:", self.combo_type)

        r_color = QHBoxLayout()
        self.btn_bg_color = QPushButton("#FFFFFF")
        self.btn_bg_color.setObjectName("btn_secondary")
        self.btn_bg_color.clicked.connect(self._choose_bg_color)
        r_color.addWidget(self.btn_bg_color)

        self.chk_dual = QCheckBox("Cắt đôi 2x6 (DNP)")
        r_color.addWidget(self.chk_dual)
        form_props.addRow("Nền / Cắt:", r_color)

        right_layout.addWidget(grp_props)

        # --------------------------------------------------------------
        # 2. TỰ ĐỘNG CĂN CHỈNH ẢNH (AUTO PHOTO FITTING)
        # --------------------------------------------------------------
        grp_auto_fit = QGroupBox("2. Tự Động Căn Chỉnh Ảnh (Auto Photo Fitting)")
        l_fit = QVBoxLayout(grp_auto_fit)
        l_fit.setSpacing(10)

        # Selector chọn ô ảnh đang cấu hình
        slot_sel_layout = QHBoxLayout()
        slot_sel_layout.addWidget(QLabel("<b>Ô Ảnh:</b>"))
        self.combo_slots_selector = QComboBox()
        self.combo_slots_selector.currentIndexChanged.connect(self._on_slot_selector_changed)
        slot_sel_layout.addWidget(self.combo_slots_selector, 1)

        btn_add_slot = QPushButton("+ Thêm Ô")
        btn_add_slot.setObjectName("btn_secondary")
        btn_add_slot.clicked.connect(self._add_slot)
        slot_sel_layout.addWidget(btn_add_slot)

        btn_del_slot = QPushButton("- Xóa")
        btn_del_slot.setObjectName("btn_danger")
        btn_del_slot.clicked.connect(self._delete_slot)
        slot_sel_layout.addWidget(btn_del_slot)
        l_fit.addLayout(slot_sel_layout)

        # Cách căn ảnh: Fill/Cover vs Fit/Contain
        l_fit.addWidget(QLabel("<b>Cách Căn Ảnh:</b>"))
        self.rb_fit_cover = QRadioButton("Lấp đầy khung (Fill / Cover) — Không viền trắng, đúng tỷ lệ")
        self.rb_fit_contain = QRadioButton("Hiển thị toàn ảnh (Fit / Contain) — Trọn vẹn khung hình")
        self.rb_fit_cover.setChecked(True)
        fit_grp = QButtonGroup(self)
        fit_grp.addButton(self.rb_fit_cover)
        fit_grp.addButton(self.rb_fit_contain)
        self.rb_fit_cover.toggled.connect(self._on_slot_fit_mode_changed)
        l_fit.addWidget(self.rb_fit_cover)
        l_fit.addWidget(self.rb_fit_contain)

        # Vị trí căn ảnh: Căn giữa vs Ưu tiên khuôn mặt
        l_fit.addWidget(QLabel("<b>Vị Trí Căn Tâm:</b>"))
        self.combo_slot_position = QComboBox()
        self.combo_slot_position.addItem("🎯 Tự Động Căn Giữa (Center)", "center")
        self.combo_slot_position.addItem("👤 Ưu Tiên Khuôn Mặt (Face Priority — AI YuNet)", "face")
        self.combo_slot_position.currentIndexChanged.connect(self._on_slot_position_changed)
        l_fit.addWidget(self.combo_slot_position)

        # Thu phóng ảnh (Zoom slider: 100% đến 250%)
        zoom_header = QHBoxLayout()
        zoom_header.addWidget(QLabel("<b>Thu Phóng Ảnh (Zoom):</b>"))
        self.lbl_zoom_val = QLabel("100%")
        self.lbl_zoom_val.setStyleSheet("color: #D4AF37; font-weight: bold;")
        zoom_header.addWidget(self.lbl_zoom_val)
        zoom_header.addStretch()
        l_fit.addLayout(zoom_header)

        self.slider_zoom = QSlider(Qt.Horizontal)
        self.slider_zoom.setRange(100, 250)
        self.slider_zoom.setValue(100)
        self.slider_zoom.setSingleStep(5)
        self.slider_zoom.valueChanged.connect(self._on_slot_zoom_changed)
        l_fit.addWidget(self.slider_zoom)

        # Dịch chuyển vùng cắt (Pan Offset) & nút Reset
        crop_layout = QHBoxLayout()
        self.lbl_crop_offset = QLabel("Cắt lệch: (0%, 0%)")
        self.lbl_crop_offset.setStyleSheet("color: #94A3B8; font-size: 13px;")
        crop_layout.addWidget(self.lbl_crop_offset)
        crop_layout.addStretch()

        btn_reset_crop = QPushButton("↺ Đặt Lại Tâm Cắt")
        btn_reset_crop.setObjectName("btn_secondary")
        btn_reset_crop.clicked.connect(self._reset_crop_offset)
        crop_layout.addWidget(btn_reset_crop)
        l_fit.addLayout(crop_layout)

        # Vùng an toàn & Bo góc & Xoay
        extra_slot_layout = QHBoxLayout()
        self.chk_slot_safe = QCheckBox("🛡️ Vùng an toàn")
        self.chk_slot_safe.setChecked(True)
        self.chk_slot_safe.toggled.connect(self._on_slot_safe_toggled)
        extra_slot_layout.addWidget(self.chk_slot_safe)

        extra_slot_layout.addWidget(QLabel("Bo góc:"))
        self.spin_slot_corner = QSpinBox()
        self.spin_slot_corner.setRange(0, 60)
        self.spin_slot_corner.setSuffix(" px")
        self.spin_slot_corner.valueChanged.connect(self._on_slot_corner_changed)
        extra_slot_layout.addWidget(self.spin_slot_corner)
        l_fit.addLayout(extra_slot_layout)

        # Thao tác xoay và căn giữa ô
        slot_actions = QHBoxLayout()
        btn_rot = QPushButton("🔄 Xoay 90°")
        btn_rot.setObjectName("btn_secondary")
        btn_rot.clicked.connect(self._rotate_slot)
        slot_actions.addWidget(btn_rot)

        btn_center_slot = QPushButton("↔️ Căn Giữa Ô")
        btn_center_slot.setObjectName("btn_secondary")
        btn_center_slot.clicked.connect(self._center_slot_horizontally)
        slot_actions.addWidget(btn_center_slot)
        l_fit.addLayout(slot_actions)

        # Áp dụng cho tất cả ô
        btn_apply_all = QPushButton("⚡ Áp Dụng Cho Tất Cả Ô")
        btn_apply_all.setObjectName("btn_champagne")
        btn_apply_all.clicked.connect(self._apply_fitting_to_all_slots)
        l_fit.addWidget(btn_apply_all)

        right_layout.addWidget(grp_auto_fit)

        # --------------------------------------------------------------
        # 3. CHỈNH SỬA VĂN BẢN (VISUAL TEXT EDITING)
        # --------------------------------------------------------------
        grp_text = QGroupBox("3. Chỉnh Sửa Văn Bản (Visual Text Editing)")
        l_txt = QVBoxLayout(grp_text)
        l_txt.setSpacing(10)

        # Selector chọn lớp chữ
        text_sel_layout = QHBoxLayout()
        text_sel_layout.addWidget(QLabel("<b>Lớp Chữ:</b>"))
        self.combo_text_selector = QComboBox()
        self.combo_text_selector.currentIndexChanged.connect(self._on_text_selector_changed)
        text_sel_layout.addWidget(self.combo_text_selector, 1)

        btn_add_txt = QPushButton("+ Thêm Chữ")
        btn_add_txt.setObjectName("btn_secondary")
        btn_add_txt.clicked.connect(self._add_text)
        text_sel_layout.addWidget(btn_add_txt)

        btn_del_txt = QPushButton("- Xóa")
        btn_del_txt.setObjectName("btn_danger")
        btn_del_txt.clicked.connect(self._delete_text)
        text_sel_layout.addWidget(btn_del_txt)
        l_txt.addLayout(text_sel_layout)

        # Nội dung chữ (hỗ trợ đa dòng)
        l_txt.addWidget(QLabel("<b>Nội Dung Chữ:</b>"))
        self.txt_content = QTextEdit()
        self.txt_content.setMaximumHeight(65)
        self.txt_content.setPlaceholderText("Nhập nội dung chữ... (Hỗ trợ nhiều dòng)")
        self.txt_content.textChanged.connect(self._on_text_content_changed)
        l_txt.addWidget(self.txt_content)

        lbl_macros = QLabel("Gợi ý: {event_name} • {date} • {location}")
        lbl_macros.setStyleSheet("color: #64748B; font-size: 12px;")
        l_txt.addWidget(lbl_macros)

        # Phông chữ & Cỡ chữ & Đậm/Nghiêng
        font_bar = QHBoxLayout()
        font_bar.addWidget(QLabel("Font:"))
        self.combo_font = QComboBox()
        self.combo_font.addItems(["Arial", "Segoe UI", "Calibri", "Tahoma", "Times New Roman"])
        self.combo_font.currentIndexChanged.connect(self._on_text_style_changed)
        font_bar.addWidget(self.combo_font, 1)

        font_bar.addWidget(QLabel("Cỡ:"))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(16, 120)
        self.spin_font_size.setValue(36)
        self.spin_font_size.valueChanged.connect(self._on_text_style_changed)
        font_bar.addWidget(self.spin_font_size)

        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setFixedWidth(36)
        self.btn_bold.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.btn_bold.toggled.connect(self._on_text_style_changed)
        font_bar.addWidget(self.btn_bold)

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedWidth(36)
        self.btn_italic.setStyleSheet("font-style: italic; font-size: 16px;")
        self.btn_italic.toggled.connect(self._on_text_style_changed)
        font_bar.addWidget(self.btn_italic)

        l_txt.addLayout(font_bar)

        # Màu sắc chữ & Bảng màu mẫu
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Màu:"))
        self.btn_text_color = QPushButton("#FFFFFF")
        self.btn_text_color.setObjectName("btn_secondary")
        self.btn_text_color.clicked.connect(self._choose_text_color)
        color_layout.addWidget(self.btn_text_color)

        # Các màu mẫu sang trọng
        presets = [("#D4AF37", "Gold"), ("#FFFFFF", "Trắng"), ("#111111", "Đen"), ("#F5E6C8", "Kem"), ("#991B1B", "Đỏ")]
        for hex_c, name in presets:
            btn_p = QPushButton()
            btn_p.setFixedSize(24, 24)
            btn_p.setToolTip(name)
            btn_p.setStyleSheet(f"background-color: {hex_c}; border: 1px solid #64748B; border-radius: 4px;")
            btn_p.clicked.connect(lambda _, c=hex_c: self._set_text_color_preset(c))
            color_layout.addWidget(btn_p)

        color_layout.addStretch()
        l_txt.addLayout(color_layout)

        # Căn lề chữ (Text Alignment)
        l_txt.addWidget(QLabel("<b>Căn Lề Chữ (Text Alignment):</b>"))
        align_layout = QHBoxLayout()
        self.btn_align_left = QPushButton("⬅️ Trái")
        self.btn_align_left.setCheckable(True)
        self.btn_align_center = QPushButton("↔️ Giữa")
        self.btn_align_center.setCheckable(True)
        self.btn_align_center.setChecked(True)
        self.btn_align_right = QPushButton("➡️ Phải")
        self.btn_align_right.setCheckable(True)

        align_grp = QButtonGroup(self)
        align_grp.addButton(self.btn_align_left)
        align_grp.addButton(self.btn_align_center)
        align_grp.addButton(self.btn_align_right)

        self.btn_align_left.clicked.connect(lambda: self._set_text_alignment("left"))
        self.btn_align_center.clicked.connect(lambda: self._set_text_alignment("center"))
        self.btn_align_right.clicked.connect(lambda: self._set_text_alignment("right"))

        align_layout.addWidget(self.btn_align_left)
        align_layout.addWidget(self.btn_align_center)
        align_layout.addWidget(self.btn_align_right)
        l_txt.addLayout(align_layout)

        # Vị trí trên khung in (Frame Position)
        l_txt.addWidget(QLabel("<b>Vị Trí Đặt Trên Khung:</b>"))
        pos_layout = QGridLayout()
        self.btn_pos_top = QPushButton("⬆️ Trên Cùng")
        self.btn_pos_mid = QPushButton("⏺️ Chính Giữa")
        self.btn_pos_bot = QPushButton("⬇️ Dưới Cùng")
        self.btn_pos_custom = QPushButton("✥ Kéo Tự Do")

        self.btn_pos_top.setCheckable(True)
        self.btn_pos_mid.setCheckable(True)
        self.btn_pos_bot.setCheckable(True)
        self.btn_pos_bot.setChecked(True)
        self.btn_pos_custom.setCheckable(True)

        pos_grp = QButtonGroup(self)
        pos_grp.addButton(self.btn_pos_top)
        pos_grp.addButton(self.btn_pos_mid)
        pos_grp.addButton(self.btn_pos_bot)
        pos_grp.addButton(self.btn_pos_custom)

        self.btn_pos_top.clicked.connect(lambda: self._set_text_position_mode("top"))
        self.btn_pos_mid.clicked.connect(lambda: self._set_text_position_mode("middle"))
        self.btn_pos_bot.clicked.connect(lambda: self._set_text_position_mode("bottom"))
        self.btn_pos_custom.clicked.connect(lambda: self._set_text_position_mode("custom"))

        pos_layout.addWidget(self.btn_pos_top, 0, 0)
        pos_layout.addWidget(self.btn_pos_mid, 0, 1)
        pos_layout.addWidget(self.btn_pos_bot, 1, 0)
        pos_layout.addWidget(self.btn_pos_custom, 1, 1)
        l_txt.addLayout(pos_layout)

        # Khoảng cách lề an toàn
        margin_layout = QHBoxLayout()
        margin_layout.addWidget(QLabel("Lề an toàn (Margin):"))
        self.spin_safe_margin = QSpinBox()
        self.spin_safe_margin.setRange(10, 120)
        self.spin_safe_margin.setValue(40)
        self.spin_safe_margin.setSuffix(" px")
        self.spin_safe_margin.valueChanged.connect(self._on_text_margin_changed)
        margin_layout.addWidget(self.spin_safe_margin)
        margin_layout.addStretch()
        l_txt.addLayout(margin_layout)

        right_layout.addWidget(grp_text)

        # --------------------------------------------------------------
        # 4. LOGO & HỌA TIẾT (LOGO LAYERS)
        # --------------------------------------------------------------
        grp_logo = QGroupBox("4. Logo & Họa Tiết (Logo Layers)")
        l_lg = QVBoxLayout(grp_logo)
        l_lg.setSpacing(10)

        # Selector chọn Logo
        logo_sel_layout = QHBoxLayout()
        logo_sel_layout.addWidget(QLabel("<b>Logo:</b>"))
        self.combo_logo_selector = QComboBox()
        self.combo_logo_selector.currentIndexChanged.connect(self._on_logo_selector_changed)
        logo_sel_layout.addWidget(self.combo_logo_selector, 1)

        btn_add_logo = QPushButton("+ Thêm Logo...")
        btn_add_logo.setObjectName("btn_secondary")
        btn_add_logo.clicked.connect(self._add_logo)
        logo_sel_layout.addWidget(btn_add_logo)

        btn_del_logo = QPushButton("- Xóa")
        btn_del_logo.setObjectName("btn_danger")
        btn_del_logo.clicked.connect(self._delete_logo)
        logo_sel_layout.addWidget(btn_del_logo)
        l_lg.addLayout(logo_sel_layout)

        # Thu phóng kích thước (Khóa tỷ lệ gốc không bao giờ méo)
        logo_scale_hdr = QHBoxLayout()
        logo_scale_hdr.addWidget(QLabel("<b>Kích Thước (Khóa Tỷ Lệ Gốc):</b>"))
        self.lbl_logo_scale_val = QLabel("100%")
        self.lbl_logo_scale_val.setStyleSheet("color: #D4AF37; font-weight: bold;")
        logo_scale_hdr.addWidget(self.lbl_logo_scale_val)
        logo_scale_hdr.addStretch()
        l_lg.addLayout(logo_scale_hdr)

        self.slider_logo_scale = QSlider(Qt.Horizontal)
        self.slider_logo_scale.setRange(20, 200)
        self.slider_logo_scale.setValue(100)
        self.slider_logo_scale.setSingleStep(5)
        self.slider_logo_scale.valueChanged.connect(self._on_logo_scale_changed)
        l_lg.addWidget(self.slider_logo_scale)

        # Nút vị trí nhanh
        l_lg.addWidget(QLabel("<b>Vị Trí Đặt Nhanh:</b>"))
        quick_grid = QGridLayout()
        btn_pos_tl = QPushButton("↖️ Trên-Trái")
        btn_pos_tr = QPushButton("↗️ Trên-Phải")
        btn_pos_c = QPushButton("⏺️ Chính Giữa")
        btn_pos_cust = QPushButton("✥ Kéo Tự Do")
        btn_pos_bl = QPushButton("↙️ Dưới-Trái")
        btn_pos_br = QPushButton("↘️ Dưới-Phải")

        btn_pos_tl.clicked.connect(lambda: self._set_logo_position_mode("top_left"))
        btn_pos_tr.clicked.connect(lambda: self._set_logo_position_mode("top_right"))
        btn_pos_c.clicked.connect(lambda: self._set_logo_position_mode("center"))
        btn_pos_cust.clicked.connect(lambda: self._set_logo_position_mode("custom"))
        btn_pos_bl.clicked.connect(lambda: self._set_logo_position_mode("bottom_left"))
        btn_pos_br.clicked.connect(lambda: self._set_logo_position_mode("bottom_right"))

        quick_grid.addWidget(btn_pos_tl, 0, 0)
        quick_grid.addWidget(btn_pos_tr, 0, 1)
        quick_grid.addWidget(btn_pos_c, 1, 0)
        quick_grid.addWidget(btn_pos_cust, 1, 1)
        quick_grid.addWidget(btn_pos_bl, 2, 0)
        quick_grid.addWidget(btn_pos_br, 2, 1)
        l_lg.addLayout(quick_grid)

        # Độ trong suốt (Opacity)
        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("Độ mờ (Opacity):"))
        self.slider_logo_opacity = QSlider(Qt.Horizontal)
        self.slider_logo_opacity.setRange(10, 100)
        self.slider_logo_opacity.setValue(100)
        self.slider_logo_opacity.valueChanged.connect(self._on_logo_opacity_changed)
        op_layout.addWidget(self.slider_logo_opacity)
        self.lbl_logo_op_val = QLabel("100%")
        op_layout.addWidget(self.lbl_logo_op_val)
        l_lg.addLayout(op_layout)

        right_layout.addWidget(grp_logo)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 4)

    # ==============================================================
    # QUẢN LÝ TẢI VÀ CHỌN KHUNG
    # ==============================================================
    def _load_frames_to_combo(self):
        self.combo_frames.blockSignals(True)
        self.combo_frames.clear()
        frames = self.manager.list_frames()
        for f in frames:
            self.combo_frames.addItem(f"{f.name} ({f.type})", f.id)
        self.combo_frames.blockSignals(False)

        if self.combo_frames.count() > 0:
            self.combo_frames.setCurrentIndex(0)
            self._on_frame_selected(0)

    def _on_frame_selected(self, index: int):
        frame_id = self.combo_frames.currentData()
        if not frame_id:
            return
        frame = self.manager.get_frame(frame_id)
        if not frame:
            return
        self.current_frame = frame
        self._populate_ui_from_frame(frame)

    def _populate_ui_from_frame(self, f: FrameTemplate):
        self._is_updating_ui = True

        # Thuộc tính cơ bản
        self.txt_name.setText(f.name)
        idx_cat = self.combo_cat.findText(f.category)
        if idx_cat >= 0:
            self.combo_cat.setCurrentIndex(idx_cat)

        idx_type = self.combo_type.findText(f.type)
        if idx_type >= 0:
            self.combo_type.setCurrentIndex(idx_type)

        self.chk_dual.setChecked(f.is_dual_strip)
        self.btn_bg_color.setText(f.bg_color or "#FFFFFF")

        # Nạp danh sách ô ảnh vào selector
        self.combo_slots_selector.blockSignals(True)
        self.combo_slots_selector.clear()
        for i, s in enumerate(f.slots):
            self.combo_slots_selector.addItem(f"Ô #{s.id} ({s.w}x{s.h} px)", i)
        self.combo_slots_selector.blockSignals(False)

        if f.slots:
            self.combo_slots_selector.setCurrentIndex(0)
            self._populate_slot_controls(0)

        # Nạp danh sách Text vào selector
        self.combo_text_selector.blockSignals(True)
        self.combo_text_selector.clear()
        for i, t in enumerate(f.text_layers):
            preview_txt = (t.text or "").split("\n")[0][:18]
            self.combo_text_selector.addItem(f"Lớp #{i+1}: {preview_txt}", i)
        self.combo_text_selector.blockSignals(False)

        if f.text_layers:
            self.combo_text_selector.setCurrentIndex(0)
            self._populate_text_controls(0)
        else:
            self.txt_content.clear()

        # Nạp danh sách Logo vào selector
        self.combo_logo_selector.blockSignals(True)
        self.combo_logo_selector.clear()
        for i, l in enumerate(f.logo_layers):
            bname = os.path.basename(l.image_path)
            self.combo_logo_selector.addItem(f"Logo #{i+1}: {bname}", i)
        self.combo_logo_selector.blockSignals(False)

        if f.logo_layers:
            self.combo_logo_selector.setCurrentIndex(0)
            self._populate_logo_controls(0)

        self._is_updating_ui = False
        self._update_preview(full_render=True)

    # ==============================================================
    # ĐIỀU KHIỂN & ĐỒNG BỘ Ô ẢNH (PHOTO SLOTS)
    # ==============================================================
    def _populate_slot_controls(self, slot_idx: int):
        if not self.current_frame or not (0 <= slot_idx < len(self.current_frame.slots)):
            return

        s = self.current_frame.slots[slot_idx]
        self._is_updating_ui = True

        fit_mode = getattr(s, 'fit_mode', 'cover')
        if fit_mode == 'contain':
            self.rb_fit_contain.setChecked(True)
        else:
            self.rb_fit_cover.setChecked(True)

        pos_mode = getattr(s, 'position_mode', 'center')
        idx_pos = self.combo_slot_position.findData(pos_mode)
        if idx_pos >= 0:
            self.combo_slot_position.setCurrentIndex(idx_pos)

        zoom_val = int(getattr(s, 'zoom', 1.0) * 100)
        self.slider_zoom.setValue(zoom_val)
        self.lbl_zoom_val.setText(f"{zoom_val}%")

        ox = getattr(s, 'crop_offset_x', 0.0)
        oy = getattr(s, 'crop_offset_y', 0.0)
        self.lbl_crop_offset.setText(f"Cắt lệch: ({int(ox*100)}%, {int(oy*100)}%)")

        self.chk_slot_safe.setChecked(getattr(s, 'use_safe_zone', True))
        self.spin_slot_corner.setValue(getattr(s, 'corner_radius', 0))

        self.canvas.selected_item_type = "slot"
        self.canvas.selected_slot_index = slot_idx
        self.canvas.update()

        self._is_updating_ui = False

    def _on_slot_selector_changed(self, index: int):
        if not self._is_updating_ui and index >= 0:
            self._populate_slot_controls(index)

    def _on_slot_fit_mode_changed(self):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            s = self.current_frame.slots[idx]
            s.fit_mode = "contain" if self.rb_fit_contain.isChecked() else "cover"
            self._update_preview(full_render=True)

    def _on_slot_position_changed(self):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            s = self.current_frame.slots[idx]
            s.position_mode = self.combo_slot_position.currentData()
            self._update_preview(full_render=True)

    def _on_slot_zoom_changed(self, val: int):
        self.lbl_zoom_val.setText(f"{val}%")
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            s = self.current_frame.slots[idx]
            s.zoom = val / 100.0
            self._update_preview(full_render=True)

    def _reset_crop_offset(self):
        if not self.current_frame:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            s = self.current_frame.slots[idx]
            s.crop_offset_x = 0.0
            s.crop_offset_y = 0.0
            self.lbl_crop_offset.setText("Cắt lệch: (0%, 0%)")
            self._update_preview(full_render=True)

    def _on_slot_safe_toggled(self, checked: bool):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            self.current_frame.slots[idx].use_safe_zone = checked
            self._update_preview(full_render=True)

    def _on_slot_corner_changed(self, val: int):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            self.current_frame.slots[idx].corner_radius = val
            self._update_preview(full_render=True)

    def _rotate_slot(self):
        if not self.current_frame:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            s = self.current_frame.slots[idx]
            s.rotation = (getattr(s, 'rotation', 0) + 90) % 360
            self._update_preview(full_render=True)

    def _center_slot_horizontally(self):
        if not self.current_frame:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            s = self.current_frame.slots[idx]
            cw = 600 if self.current_frame.is_dual_strip else self.current_frame.canvas_size[0]
            s.x = max(0, (cw - s.w) // 2)
            self._update_preview(full_render=True)

    def _apply_fitting_to_all_slots(self):
        if not self.current_frame or not self.current_frame.slots:
            return
        idx = self.combo_slots_selector.currentIndex()
        if not (0 <= idx < len(self.current_frame.slots)):
            return

        ref_slot = self.current_frame.slots[idx]
        for s in self.current_frame.slots:
            s.fit_mode = ref_slot.fit_mode
            s.position_mode = ref_slot.position_mode
            s.zoom = ref_slot.zoom
            s.use_safe_zone = ref_slot.use_safe_zone
            s.corner_radius = ref_slot.corner_radius

        QMessageBox.information(
            self, "Đã Áp Dụng", "Đã đồng bộ thiết lập căn chỉnh tự động cho toàn bộ các ô ảnh!"
        )
        self._update_preview(full_render=True)

    def _add_slot(self):
        if not self.current_frame:
            return
        num = len(self.current_frame.slots) + 1
        cw = 600 if self.current_frame.is_dual_strip else self.current_frame.canvas_size[0]
        slot_w = min(500, cw - 60)
        slot_h = 360
        new_x = (cw - slot_w) // 2
        new_y = 60 + (num - 1) * (slot_h + 30)

        new_slot = PhotoSlot(
            id=num,
            x=new_x,
            y=new_y,
            w=slot_w,
            h=slot_h,
            photo_index=num - 1,
            fit_mode="cover",
            position_mode="center",
            zoom=1.0,
            use_safe_zone=True
        )
        self.current_frame.slots.append(new_slot)
        self._populate_ui_from_frame(self.current_frame)
        self.combo_slots_selector.setCurrentIndex(len(self.current_frame.slots) - 1)

    def _delete_slot(self):
        if not self.current_frame or not self.current_frame.slots:
            return
        idx = self.combo_slots_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.slots):
            self.current_frame.slots.pop(idx)
            self._populate_ui_from_frame(self.current_frame)

    # ==============================================================
    # ĐIỀU KHIỂN & ĐỒNG BỘ VĂN BẢN (TEXT LAYERS)
    # ==============================================================
    def _populate_text_controls(self, txt_idx: int):
        if not self.current_frame or not (0 <= txt_idx < len(self.current_frame.text_layers)):
            return

        t = self.current_frame.text_layers[txt_idx]
        self._is_updating_ui = True

        self.txt_content.setText(t.text or "")
        f_idx = self.combo_font.findText(getattr(t, 'font_name', 'Arial'), Qt.MatchContains)
        if f_idx >= 0:
            self.combo_font.setCurrentIndex(f_idx)

        self.spin_font_size.setValue(getattr(t, 'font_size', 36))
        self.btn_bold.setChecked(getattr(t, 'is_bold', False))
        self.btn_italic.setChecked(getattr(t, 'is_italic', False))

        self.btn_text_color.setText(t.font_color)
        self.btn_text_color.setStyleSheet(f"background-color: {t.font_color}; color: #000000; font-weight: bold;")

        align = getattr(t, 'alignment', 'center')
        self.btn_align_left.setChecked(align == 'left')
        self.btn_align_center.setChecked(align == 'center')
        self.btn_align_right.setChecked(align == 'right')

        pos = getattr(t, 'position_mode', 'bottom')
        self.btn_pos_top.setChecked(pos == 'top')
        self.btn_pos_mid.setChecked(pos == 'middle')
        self.btn_pos_bot.setChecked(pos == 'bottom')
        self.btn_pos_custom.setChecked(pos == 'custom')

        self.spin_safe_margin.setValue(getattr(t, 'safe_margin', 40))

        self.canvas.selected_item_type = "text"
        self.canvas.selected_text_index = txt_idx
        self.canvas.update()

        self._is_updating_ui = False

    def _on_text_selector_changed(self, index: int):
        if not self._is_updating_ui and index >= 0:
            self._populate_text_controls(index)

    def _on_text_content_changed(self):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            self.current_frame.text_layers[idx].text = self.txt_content.toPlainText()
            self._update_preview(full_render=True)

    def _on_text_style_changed(self):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            t = self.current_frame.text_layers[idx]
            t.font_name = self.combo_font.currentText()
            t.font_size = self.spin_font_size.value()
            t.is_bold = self.btn_bold.isChecked()
            t.is_italic = self.btn_italic.isChecked()
            self._update_preview(full_render=True)

    def _choose_text_color(self):
        if not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if not (0 <= idx < len(self.current_frame.text_layers)):
            return
        col = QColorDialog.getColor(QColor(self.btn_text_color.text()), self, "Chọn Màu Chữ")
        if col.isValid():
            self._set_text_color_preset(col.name().upper())

    def _set_text_color_preset(self, hex_color: str):
        if not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            t = self.current_frame.text_layers[idx]
            t.font_color = hex_color
            self.btn_text_color.setText(hex_color)
            self.btn_text_color.setStyleSheet(f"background-color: {hex_color}; color: #000000; font-weight: bold;")
            self._update_preview(full_render=True)

    def _set_text_alignment(self, align: str):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            self.current_frame.text_layers[idx].alignment = align
            self._update_preview(full_render=True)

    def _set_text_position_mode(self, pos_mode: str):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            self.current_frame.text_layers[idx].position_mode = pos_mode
            self._update_preview(full_render=True)

    def _on_text_margin_changed(self, val: int):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            self.current_frame.text_layers[idx].safe_margin = val
            self._update_preview(full_render=True)

    def _add_text(self):
        if not self.current_frame:
            return
        num = len(self.current_frame.text_layers) + 1
        cw = 600 if self.current_frame.is_dual_strip else self.current_frame.canvas_size[0]
        ch = self.current_frame.canvas_size[1]

        new_txt = TextLayer(
            id=f"txt_{num}",
            text="1998 TEAM • Studio Phóng Sự Cưới",
            x=cw // 2,
            y=ch - 140,
            font_size=34,
            font_color="#D4AF37",
            font_name="Arial",
            alignment="center",
            is_bold=True,
            position_mode="bottom",
            safe_margin=40
        )
        self.current_frame.text_layers.append(new_txt)
        self._populate_ui_from_frame(self.current_frame)
        self.combo_text_selector.setCurrentIndex(len(self.current_frame.text_layers) - 1)

    def _delete_text(self):
        if not self.current_frame or not self.current_frame.text_layers:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            self.current_frame.text_layers.pop(idx)
            self._populate_ui_from_frame(self.current_frame)

    # ==============================================================
    # ĐIỀU KHIỂN & ĐỒNG BỘ LOGO (LOGO LAYERS)
    # ==============================================================
    def _populate_logo_controls(self, logo_idx: int):
        if not self.current_frame or not (0 <= logo_idx < len(self.current_frame.logo_layers)):
            return

        l = self.current_frame.logo_layers[logo_idx]
        self._is_updating_ui = True

        scale_val = int(getattr(l, 'scale', 1.0) * 100)
        self.slider_logo_scale.setValue(scale_val)
        self.lbl_logo_scale_val.setText(f"{scale_val}%")

        op_val = int(getattr(l, 'opacity', 1.0) * 100)
        self.slider_logo_opacity.setValue(op_val)
        self.lbl_logo_op_val.setText(f"{op_val}%")

        self.canvas.selected_item_type = "logo"
        self.canvas.selected_logo_index = logo_idx
        self.canvas.update()

        self._is_updating_ui = False

    def _on_logo_selector_changed(self, index: int):
        if not self._is_updating_ui and index >= 0:
            self._populate_logo_controls(index)

    def _on_logo_scale_changed(self, val: int):
        self.lbl_logo_scale_val.setText(f"{val}%")
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_logo_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.logo_layers):
            l = self.current_frame.logo_layers[idx]
            l.scale = val / 100.0
            self._update_preview(full_render=True)

    def _on_logo_opacity_changed(self, val: int):
        self.lbl_logo_op_val.setText(f"{val}%")
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_logo_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.logo_layers):
            l = self.current_frame.logo_layers[idx]
            l.opacity = val / 100.0
            self._update_preview(full_render=True)

    def _set_logo_position_mode(self, pos_mode: str):
        if not self.current_frame:
            return
        idx = self.combo_logo_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.logo_layers):
            l = self.current_frame.logo_layers[idx]
            l.position_mode = pos_mode
            self._update_preview(full_render=True)

    def _add_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Logo / Họa Tiết PNG", "", "Ảnh PNG Trong Suốt (*.png);;Tất Cả Tệp (*.*)"
        )
        if path and os.path.exists(path):
            if not self.current_frame:
                return
            try:
                img = Image.open(path)
                orig_w, orig_h = img.size
            except Exception:
                orig_w, orig_h = 200, 100

            num = len(self.current_frame.logo_layers) + 1
            cw = 600 if self.current_frame.is_dual_strip else self.current_frame.canvas_size[0]
            new_logo = LogoLayer(
                id=f"logo_{num}",
                image_path=path,
                x=(cw - orig_w) // 2 if orig_w < cw else 40,
                y=40,
                w=orig_w,
                h=orig_h,
                opacity=1.0,
                position_mode="center",
                scale=1.0,
                original_w=orig_w,
                original_h=orig_h
            )
            self.current_frame.logo_layers.append(new_logo)
            self._populate_ui_from_frame(self.current_frame)
            self.combo_logo_selector.setCurrentIndex(len(self.current_frame.logo_layers) - 1)

    def _delete_logo(self):
        if not self.current_frame or not self.current_frame.logo_layers:
            return
        idx = self.combo_logo_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.logo_layers):
            self.current_frame.logo_layers.pop(idx)
            self._populate_ui_from_frame(self.current_frame)

    # ==============================================================
    # SỰ KIỆN TƯƠNG TÁC TỪ CANVAS (DRAG & DROP)
    # ==============================================================
    def _on_drag_mode_toggled(self, checked: bool):
        if checked:
            self.btn_mode_crop.setObjectName("btn_champagne")
            self.btn_mode_move.setObjectName("btn_secondary")
            self.canvas.set_drag_mode("pan_crop")
        else:
            self.btn_mode_crop.setObjectName("btn_secondary")
            self.btn_mode_move.setObjectName("btn_champagne")
            self.canvas.set_drag_mode("move_slot")
        self.btn_mode_crop.style().unpolish(self.btn_mode_crop)
        self.btn_mode_crop.style().polish(self.btn_mode_crop)
        self.btn_mode_move.style().unpolish(self.btn_mode_move)
        self.btn_mode_move.style().polish(self.btn_mode_move)

    def _on_slot_selected_from_canvas(self, slot_index: int):
        if 0 <= slot_index < self.combo_slots_selector.count():
            self._is_updating_ui = True
            self.combo_slots_selector.setCurrentIndex(slot_index)
            self._is_updating_ui = False
            self._populate_slot_controls(slot_index)

    def _on_slot_moved_from_canvas(self, slot_index: int, new_x: int, new_y: int):
        pass  # Đã cập nhật trực tiếp trên model

    def _on_slot_crop_panned_from_canvas(self, slot_index: int, ox: float, oy: float):
        self.lbl_crop_offset.setText(f"Cắt lệch: ({int(ox*100)}%, {int(oy*100)}%)")

    def _on_text_selected_from_canvas(self, text_index: int):
        if 0 <= text_index < self.combo_text_selector.count():
            self._is_updating_ui = True
            self.combo_text_selector.setCurrentIndex(text_index)
            self._is_updating_ui = False
            self._populate_text_controls(text_index)

    def _on_text_moved_from_canvas(self, text_index: int, new_x: int, new_y: int):
        self.btn_pos_custom.setChecked(True)

    def _on_logo_selected_from_canvas(self, logo_index: int):
        if 0 <= logo_index < self.combo_logo_selector.count():
            self._is_updating_ui = True
            self.combo_logo_selector.setCurrentIndex(logo_index)
            self._is_updating_ui = False
            self._populate_logo_controls(logo_index)

    def _on_logo_moved_from_canvas(self, logo_index: int, new_x: int, new_y: int):
        pass

    # ==============================================================
    # CẬP NHẬT PREVIEW & LƯU KHUNG
    # ==============================================================
    def _build_frame_from_ui(self) -> Optional[FrameTemplate]:
        if not self.current_frame:
            return None

        f = self.current_frame
        f.name = self.txt_name.text().strip() or "Khung Mới"
        f.category = self.combo_cat.currentText()
        f.type = self.combo_type.currentText()
        f.is_dual_strip = self.chk_dual.isChecked()
        f.has_cut_line = self.chk_dual.isChecked()
        f.bg_color = self.btn_bg_color.text()
        return f

    def _update_preview(self, full_render: bool = True):
        f = self._build_frame_from_ui()
        if not f:
            return

        warnings = FrameDesigner.validate_template(f)
        if warnings:
            self.lbl_warnings.setText(f"⚠️ {warnings[0][:26]}...")
            self.lbl_warnings.setToolTip(f"Cảnh báo: {warnings[0]}")
            self.lbl_warnings.setStyleSheet("color: #F59E0B; font-weight: bold;")
        else:
            self.lbl_warnings.setText("✅ 300 DPI • An toàn")
            self.lbl_warnings.setToolTip("Trạng thái bố cục: Chuẩn xác 300 DPI, an toàn vùng cắt.")
            self.lbl_warnings.setStyleSheet("color: #10B981; font-weight: 500;")

        if full_render or not self.canvas.preview_pixmap:
            prev_img = FrameDesigner.render_preview(f, max_height=800)
            rgb_img = prev_img.convert("RGB")
            w, h = rgb_img.size
            data = rgb_img.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            self.canvas.set_template_preview(f, pix)
        else:
            self.canvas.template = f
            self.canvas.update()

    def _save_frame(self):
        f = self._build_frame_from_ui()
        if not f:
            return
        if self.manager.save_frame(f):
            QMessageBox.information(self, "Thành Công", f"Đã lưu khung in '{f.name}' vào thư mục người dùng!")
            self.frame_changed.emit(f.id)

    # ==============================================================
    # CÁC THAO TÁC QUẢN LÝ KHUNG (NHẬP, NHÂN BẢN, ĐỔI TÊN, XÓA, ZIP)
    # ==============================================================
    def _open_import_dialog(self):
        dlg = ImportFrameDialog(self.manager, self)
        if dlg.exec() == QDialog.Accepted and dlg.imported_template:
            self._load_frames_to_combo()
            idx = self.combo_frames.findData(dlg.imported_template.id)
            if idx >= 0:
                self.combo_frames.setCurrentIndex(idx)
            self.frame_changed.emit(dlg.imported_template.id)

    def _duplicate_frame(self):
        if not self.current_frame:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Nhân Bản Khung",
            "Nhập tên cho bản sao:",
            text=f"{self.current_frame.name} (Bản Sao)"
        )
        if ok and new_name.strip():
            copied = self.manager.duplicate_frame(self.current_frame.id, new_name.strip())
            if copied:
                QMessageBox.information(self, "Thành Công", f"Đã nhân bản khung thành công: '{copied.name}'")
                self._load_frames_to_combo()
                idx = self.combo_frames.findData(copied.id)
                if idx >= 0:
                    self.combo_frames.setCurrentIndex(idx)
                self.frame_changed.emit(copied.id)

    def _rename_frame(self):
        if not self.current_frame:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Đổi Tên Khung",
            "Nhập tên mới:",
            text=self.current_frame.name
        )
        if ok and new_name.strip():
            if self.manager.rename_frame(self.current_frame.id, new_name.strip()):
                QMessageBox.information(self, "Thành Công", f"Đã đổi tên khung thành: '{new_name.strip()}'")
                curr_id = self.current_frame.id
                self._load_frames_to_combo()
                idx = self.combo_frames.findData(curr_id)
                if idx >= 0:
                    self.combo_frames.setCurrentIndex(idx)
                self.frame_changed.emit(curr_id)

    def _delete_frame(self):
        if not self.current_frame:
            return
        confirm = QMessageBox.question(
            self,
            "Xác Nhận Xóa",
            f"Bạn có chắc chắn muốn xóa mẫu khung '{self.current_frame.name}'?\nThao tác này không thể hoàn tác.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            f_id = self.current_frame.id
            if self.manager.delete_frame(f_id):
                QMessageBox.information(self, "Thành Công", "Đã xóa mẫu khung ảnh.")
                self._load_frames_to_combo()
                self.frame_changed.emit(f_id)

    def _backup_zip(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Sao Lưu Khung Ảnh Ra File ZIP", "1998_Frames_Backup.zip", "ZIP Archive (*.zip)"
        )
        if path:
            if self.manager.backup_frames_to_zip(path):
                QMessageBox.information(self, "Thành Công", f"Đã sao lưu toàn bộ khung ảnh vào:\n{path}")
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể tạo file sao lưu ZIP.")

    def _restore_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Khôi Phục Khung Ảnh Từ File ZIP", "", "ZIP Archive (*.zip)"
        )
        if path and os.path.exists(path):
            confirm = QMessageBox.question(
                self,
                "Xác Nhận Khôi Phục",
                "Quá trình khôi phục sẽ bổ sung các khung ảnh từ file ZIP vào hệ thống.\nBạn có muốn tiếp tục?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                if self.manager.restore_frames_from_zip(path):
                    QMessageBox.information(self, "Thành Công", "Đã khôi phục thành công các khung ảnh!")
                    self._load_frames_to_combo()
                    self.frame_changed.emit("")
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể giải nén file sao lưu này.")

    def _on_type_changed(self, index: int):
        if self._is_updating_ui or not self.current_frame:
            return
        t = self.combo_type.currentText()
        if t in DPI_300_SIZES:
            self.current_frame.type = t
            self.current_frame.canvas_size = list(DPI_300_SIZES[t])
            if t == "4x6_dual":
                self.chk_dual.setChecked(True)
            self._update_preview(full_render=True)

    def _choose_bg_color(self):
        col = QColorDialog.getColor(QColor(self.btn_bg_color.text()), self, "Chọn Màu Nền Khung In")
        if col.isValid():
            hex_col = col.name().upper()
            self.btn_bg_color.setText(hex_col)
            self._update_preview(full_render=True)
