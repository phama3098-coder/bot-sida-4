"""
1998 TEAM — Frame Designer & Template Studio
Visual interactive layout editor for 2x6 and 4x6 print formats,
SVG/PNG/JPG multi-format import, auto photo fitting,
multiline visual text editing, free drag & drop with boundary locking,
aspect-ratio locked logo positioning, and zip backup/restore.
"""

import os
import shutil
import copy
from typing import Optional, List, Tuple
from PIL import Image, ImageDraw

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QLineEdit, QCheckBox, QScrollArea, QFileDialog, QMessageBox,
    QGroupBox, QInputDialog, QSizePolicy, QColorDialog, QDialog, QFormLayout,
    QRadioButton, QButtonGroup, QTextEdit, QFrame, QSlider
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QPoint, QRect, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QPen, QBrush, QFont

from vietphotobooth.core.font_registry import FontRegistry, FontItem
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer, DPI_300_SIZES
from vietphotobooth.processing.image_processor import get_face_detector
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
    - Kéo pan căn chỉnh góc cắt ảnh (Pan Crop) hoặc di chuyển ô ảnh (Move Slot).
    - 4 tay nắm góc điều chỉnh kích thước ô ảnh (Resize Slot) trực tiếp trên bản vẽ.
    - Kéo thả lớp chữ (Text Layer) tự do trên bản vẽ không bao giờ tự nhảy về giữa.
    - Nhấp luân phiên chuyển đổi lớp chữ khi nhiều lớp bị xếp chồng đè lên nhau.
    - Tay nắm đổi kích cỡ chữ trực tiếp và tay nắm điều hướng ô ảnh.
    - Kéo thả lớp Logo trực tiếp trên bản vẽ.
    - Vẽ lưới tọa độ Grid dưới các lớp, vùng an toàn (Safe Zone) và mép xén/vạch cắt độc lập.
    - Làm nổi bật đối tượng đang chọn với viền vàng Champagne Gold.
    """

    slot_selected = Signal(int)
    slot_moved = Signal(int, int, int)
    slot_resized = Signal(int, int, int, int, int)  # slot_idx, x, y, w, h
    slot_crop_panned = Signal(int, float, float)
    text_selected = Signal(int)
    text_moved = Signal(int, int, int)
    text_resized = Signal(int, int)
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
        self.show_safe_zone: bool = True
        self.show_cut_lines: bool = True
        self.grid_size: int = 40  # 40px tại độ phân giải gốc 300 DPI

        # Trạng thái kéo chuột
        self._is_dragging: bool = False
        self._is_resizing_text: bool = False
        self._is_resizing_slot: bool = False
        self._slot_resize_corner: str = ""  # "tl", "tr", "bl", "br"
        self._drag_start_pos: QPoint = QPoint()
        self._start_slot_x: int = 0
        self._start_slot_y: int = 0
        self._start_slot_w: int = 0
        self._start_slot_h: int = 0
        self._start_crop_ox: float = 0.0
        self._start_crop_oy: float = 0.0
        self._start_text_x: int = 0
        self._start_text_y: int = 0
        self._start_font_size: int = 34
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

    def _get_text_rect_300dpi(self, idx: int) -> QRectF:
        """Tính toán bounding box chuẩn xác 300 DPI của lớp chữ bằng engine FrameDesigner."""
        if not self.template or not (0 <= idx < len(self.template.text_layers)):
            return QRectF()
        txt = self.template.text_layers[idx]
        w, h = self.template.canvas_size[0], self.template.canvas_size[1]
        container_w = 600 if (self.template.is_dual_strip and w == 1200) else w

        font = FrameDesigner.get_windows_font(
            txt.font_name, txt.font_size, is_bold=getattr(txt, 'is_bold', False), is_italic=getattr(txt, 'is_italic', False)
        )
        dummy_img = Image.new("RGBA", (10, 10))
        draw = ImageDraw.Draw(dummy_img)
        lines, box_x, box_y, box_w, box_h = FrameDesigner.get_text_layout_info(
            draw=draw, txt=txt, content=txt.text or "", font=font, container_w=container_w, canvas_h=h
        )
        return QRectF(box_x, box_y, box_w, box_h)

    def _get_text_rect_screen(self, idx: int) -> QRectF:
        """Quy đổi bounding box lớp chữ sang tọa độ màn hình xem trước."""
        r = self._get_text_rect_300dpi(idx)
        scale, ox, oy, rw, rh = self._get_canvas_geometry()
        return QRectF(ox + r.x() * scale, oy + r.y() * scale, r.width() * scale, r.height() * scale)

    def _corner_hit_test(self, mx: float, my: float) -> str:
        """Kiểm tra tọa độ chuột có chạm vào 1 trong 4 tay nắm góc của ô ảnh đang chọn không."""
        if not self.template or self.selected_item_type != "slot" or not (0 <= self.selected_slot_index < len(self.template.slots)):
            return ""
        scale, ox, oy, rw, rh = self._get_canvas_geometry()
        s = self.template.slots[self.selected_slot_index]
        sx = ox + s.x * scale
        sy = oy + s.y * scale
        sw = s.w * scale
        sh = s.h * scale
        h_size = 16
        corners = {
            "tl": QRectF(sx - h_size / 2, sy - h_size / 2, h_size, h_size),
            "tr": QRectF(sx + sw - h_size / 2, sy - h_size / 2, h_size, h_size),
            "bl": QRectF(sx - h_size / 2, sy + sh - h_size / 2, h_size, h_size),
            "br": QRectF(sx + sw - h_size / 2, sy + sh - h_size / 2, h_size, h_size),
        }
        for c_name, c_rect in corners.items():
            if c_rect.contains(mx, my):
                return c_name
        return ""

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

        # 3. Vẽ lưới tọa độ Grid DƯỚI các ô ảnh để không bao giờ che khuất tay nắm thao tác
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

        # 4. Vẽ Vùng an toàn (Safe Zone) độc lập
        if self.show_safe_zone:
            safe_scale = self.template.safe_zone_px * scale
            safe_pen = QPen(QColor(212, 175, 55, 180), 1, Qt.DashLine)
            painter.setPen(safe_pen)
            painter.drawRect(QRectF(ox + safe_scale, oy + safe_scale, rw - 2 * safe_scale, rh - 2 * safe_scale))

        # 5. Vẽ Mép xén (Bleed Margin) và Vạch cắt giữa (Cut Line) độc lập
        if self.show_cut_lines:
            bleed_scale = self.template.bleed_px * scale
            bleed_pen = QPen(QColor(239, 68, 68, 160), 1, Qt.DashLine)
            painter.setPen(bleed_pen)
            painter.drawRect(QRectF(ox + bleed_scale, oy + bleed_scale, rw - 2 * bleed_scale, rh - 2 * bleed_scale))

            if self.template.is_dual_strip:
                cut_x = ox + (rw / 2.0)
                cut_pen = QPen(QColor(148, 163, 184, 200), 2, Qt.DashLine)
                painter.setPen(cut_pen)
                painter.drawLine(cut_x, oy, cut_x, oy + rh)

        # 6. Vẽ viền & tay nắm 4 góc tương tác cho từng ô PhotoSlot
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

                # Vẽ 4 góc điều hướng & co giãn kích thước (10px, viền vàng sắc sảo)
                h_size = 12
                painter.setBrush(QColor("#FFFFFF"))
                painter.setPen(QPen(QColor("#D4AF37"), 2))
                painter.drawRect(QRectF(sx - h_size / 2, sy - h_size / 2, h_size, h_size))
                painter.drawRect(QRectF(sx + sw - h_size / 2, sy - h_size / 2, h_size, h_size))
                painter.drawRect(QRectF(sx - h_size / 2, sy + sh - h_size / 2, h_size, h_size))
                painter.drawRect(QRectF(sx + sw - h_size / 2, sy + sh - h_size / 2, h_size, h_size))

                # Huy hiệu thông số ô ảnh đang chọn
                fit_text = "Lấp Đầy" if getattr(slot, 'fit_mode', 'cover') == "cover" else "Toàn Ảnh"
                zoom_val = int(getattr(slot, 'zoom', 1.0) * 100)
                badge_text = f"Ô #{slot.id} • {fit_text} • {slot.w}x{slot.h} px • {zoom_val}%"
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#FFFFFF"))
                painter.setBrush(QColor(11, 19, 43, 230))
                painter.drawRoundedRect(QRectF(sx + 6, sy + 6, 220, 24), 4, 4)
                painter.drawText(QRectF(sx + 10, sy + 6, 210, 24), Qt.AlignVCenter | Qt.AlignLeft, badge_text)
            else:
                slot_pen = QPen(QColor(56, 189, 248, 140), 1.5, Qt.DashLine)
                painter.setPen(slot_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(slot_rect)

                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.setPen(QColor("#38BDF8"))
                painter.drawText(QRectF(sx + 6, sy + 6, 80, 20), Qt.AlignLeft, f"#{slot.id}")

        # 7. Vẽ viền tương tác cho lớp Logo
        for idx, logo in enumerate(self.template.logo_layers):
            scale_val = getattr(logo, 'scale', 1.0)
            lw = (getattr(logo, 'original_w', logo.w) * scale_val if getattr(logo, 'original_w', 0) else logo.w) * scale
            lh = (getattr(logo, 'original_h', logo.h) * scale_val if getattr(logo, 'original_h', 0) else logo.h) * scale
            lx = ox + logo.x * scale
            ly = oy + logo.y * scale
            is_logo_sel = (self.selected_item_type == "logo" and idx == self.selected_logo_index)

            if is_logo_sel:
                logo_pen = QPen(QColor("#38BDF8"), 2.5, Qt.SolidLine)
                painter.setPen(logo_pen)
                painter.setBrush(QColor(56, 189, 248, 35))
                painter.drawRect(QRectF(lx, ly, lw, lh))

                # Vẽ 4 góc tay nắm
                h_size = 7
                painter.setBrush(QColor("#FFFFFF"))
                painter.setPen(QColor("#070A12"))
                painter.drawRect(QRectF(lx + lw - h_size / 2, ly + lh - h_size / 2, h_size, h_size))

                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#FFFFFF"))
                painter.setBrush(QColor(11, 19, 43, 220))
                painter.drawRoundedRect(QRectF(lx + 4, ly + 4, 120, 20), 4, 4)
                painter.drawText(QRectF(lx + 8, ly + 4, 110, 20), Qt.AlignVCenter | Qt.AlignLeft, f"🖼️ Logo #{idx+1}")

        # 8. Vẽ viền tương tác và tay nắm cho các lớp Text
        for idx, txt in enumerate(self.template.text_layers):
            is_visible = getattr(txt, 'is_visible', True)
            screen_r = self._get_text_rect_screen(idx)
            is_txt_sel = (self.selected_item_type == "text" and idx == self.selected_text_index)

            if not is_visible:
                if is_txt_sel:
                    txt_pen = QPen(QColor(148, 163, 184, 160), 1.5, Qt.DashLine)
                    painter.setPen(txt_pen)
                    painter.setBrush(QColor(100, 116, 139, 20))
                    painter.drawRoundedRect(screen_r.adjusted(-4, -4, 4, 4), 4, 4)

                    painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    painter.setPen(QColor("#94A3B8"))
                    painter.setBrush(QColor(15, 23, 42, 220))
                    painter.drawRoundedRect(QRectF(screen_r.left(), screen_r.top() - 24, 160, 20), 4, 4)
                    painter.drawText(QRectF(screen_r.left() + 6, screen_r.top() - 24, 150, 20), Qt.AlignVCenter | Qt.AlignLeft, f"👁️‍🗨️ [ẨN] Chữ #{idx+1}")
                continue

            if is_txt_sel:
                # Viền vàng Champagne Gold sắc nét
                txt_pen = QPen(QColor("#D4AF37"), 2.5, Qt.DashLine)
                painter.setPen(txt_pen)
                painter.setBrush(QColor(212, 175, 55, 30))
                painter.drawRoundedRect(screen_r.adjusted(-4, -4, 4, 4), 4, 4)

                # Vẽ 4 góc tay nắm điều hướng
                h_size = 8
                tx = screen_r.left() - 4
                ty = screen_r.top() - 4
                tw = screen_r.width() + 8
                th = screen_r.height() + 8

                painter.setBrush(QColor("#FFFFFF"))
                painter.setPen(QColor("#070A12"))
                painter.drawRect(QRectF(tx - h_size / 2, ty - h_size / 2, h_size, h_size))
                painter.drawRect(QRectF(tx + tw - h_size / 2, ty - h_size / 2, h_size, h_size))
                painter.drawRect(QRectF(tx - h_size / 2, ty + th - h_size / 2, h_size, h_size))
                # Tay nắm đổi cỡ chữ góc dưới phải (vàng nổi bật)
                painter.setBrush(QColor("#D4AF37"))
                painter.drawRect(QRectF(tx + tw - h_size / 2, ty + th - h_size / 2, h_size + 2, h_size + 2))

                # Huy hiệu lớp chữ kèm tọa độ và trạng thái khóa
                lock_sym = "🔒 " if getattr(txt, 'is_locked', False) else ""
                badge_str = f"📝 {lock_sym}Chữ #{idx+1} • {txt.font_size}pt [X: {txt.x}, Y: {txt.y}]"
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#FFFFFF"))
                painter.setBrush(QColor(11, 19, 43, 230))
                painter.drawRoundedRect(QRectF(tx, ty - 26, 210, 22), 4, 4)
                painter.drawText(QRectF(tx + 6, ty - 26, 200, 22), Qt.AlignVCenter | Qt.AlignLeft, badge_str)
            else:
                # Vẽ viền mờ chấm nét để người dùng nhận biết có thể nhấp chọn chữ
                txt_pen = QPen(QColor(212, 175, 55, 80), 1, Qt.DotLine)
                painter.setPen(txt_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(screen_r.adjusted(-3, -3, 3, 3), 3, 3)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.template:
            scale, ox, oy, rw, rh = self._get_canvas_geometry()
            mx = event.position().x()
            my = event.position().y()

            cx = (mx - ox) / scale
            cy = (my - oy) / scale

            # 0. Kiểm tra click vào 4 tay nắm góc của ô ảnh đang chọn (co giãn kích thước)
            if self.selected_item_type == "slot" and 0 <= self.selected_slot_index < len(self.template.slots):
                s = self.template.slots[self.selected_slot_index]
                sx = ox + s.x * scale
                sy = oy + s.y * scale
                sw = s.w * scale
                sh = s.h * scale
                h_size = 16
                corners = {
                    "tl": QRectF(sx - h_size / 2, sy - h_size / 2, h_size, h_size),
                    "tr": QRectF(sx + sw - h_size / 2, sy - h_size / 2, h_size, h_size),
                    "bl": QRectF(sx - h_size / 2, sy + sh - h_size / 2, h_size, h_size),
                    "br": QRectF(sx + sw - h_size / 2, sy + sh - h_size / 2, h_size, h_size),
                }
                for c_name, c_rect in corners.items():
                    if c_rect.contains(mx, my):
                        self._is_resizing_slot = True
                        self._slot_resize_corner = c_name
                        self._drag_start_pos = event.pos()
                        self._start_slot_x = s.x
                        self._start_slot_y = s.y
                        self._start_slot_w = s.w
                        self._start_slot_h = s.h
                        self._is_dragging = False
                        self._is_resizing_text = False
                        return

            # 1. Kiểm tra click vào lớp Text (Hỗ trợ nhấp luân phiên chọn lớp khi bị đè lên nhau)
            hit_texts = []
            for idx in range(len(self.template.text_layers)):
                txt = self.template.text_layers[idx]
                if not getattr(txt, 'is_visible', True):
                    continue
                screen_r = self._get_text_rect_screen(idx).adjusted(-10, -10, 10, 10)
                if screen_r.contains(mx, my):
                    hit_texts.append(idx)

            if hit_texts:
                if self.selected_item_type == "text" and self.selected_text_index in hit_texts and len(hit_texts) > 1:
                    cur_pos = hit_texts.index(self.selected_text_index)
                    chosen_idx = hit_texts[(cur_pos + 1) % len(hit_texts)]
                else:
                    chosen_idx = hit_texts[-1]

                txt = self.template.text_layers[chosen_idx]
                self.selected_item_type = "text"
                self.selected_text_index = chosen_idx
                self._drag_start_pos = event.pos()
                self._start_text_x = getattr(txt, 'x', 300)
                self._start_text_y = getattr(txt, 'y', 1500)
                self._start_font_size = txt.font_size

                screen_r = self._get_text_rect_screen(chosen_idx).adjusted(-10, -10, 10, 10)
                br_handle = QRectF(screen_r.right() - 16, screen_r.bottom() - 16, 24, 24)
                if br_handle.contains(mx, my):
                    self._is_resizing_text = True
                    self._is_dragging = False
                else:
                    self._is_resizing_text = False
                    self._is_dragging = True

                self.text_selected.emit(chosen_idx)
                self.update()
                return

            # 2. Kiểm tra click vào lớp Logo
            for idx in reversed(range(len(self.template.logo_layers))):
                l = self.template.logo_layers[idx]
                scale_val = getattr(l, 'scale', 1.0)
                lw = getattr(l, 'original_w', l.w) * scale_val if getattr(l, 'original_w', 0) else l.w
                lh = getattr(l, 'original_h', l.h) * scale_val if getattr(l, 'original_h', 0) else l.h
                if l.x <= cx <= (l.x + lw) and l.y <= cy <= (l.y + lh):
                    self.selected_item_type = "logo"
                    self.selected_logo_index = idx
                    self._is_dragging = True
                    self._is_resizing_text = False
                    self._is_resizing_slot = False
                    self._drag_start_pos = event.pos()
                    self._start_logo_x = l.x
                    self._start_logo_y = l.y
                    self.logo_selected.emit(idx)
                    self.update()
                    return

            # 3. Kiểm tra click vào Photo Slots
            for idx in reversed(range(len(self.template.slots))):
                s = self.template.slots[idx]
                if s.x <= cx <= (s.x + s.w) and s.y <= cy <= (s.y + s.h):
                    self.selected_item_type = "slot"
                    self.selected_slot_index = idx
                    self._is_dragging = True
                    self._is_resizing_text = False
                    self._is_resizing_slot = False
                    self._drag_start_pos = event.pos()
                    self._start_slot_x = s.x
                    self._start_slot_y = s.y
                    self._start_crop_ox = getattr(s, 'crop_offset_x', 0.0)
                    self._start_crop_oy = getattr(s, 'crop_offset_y', 0.0)
                    self.slot_selected.emit(idx)
                    self.update()
                    return

            # Click ra ngoài vùng đối tượng
            self.selected_item_type = "none"
            self.update()

    def mouseMoveEvent(self, event):
        if not (self._is_dragging or self._is_resizing_text or self._is_resizing_slot) or not self.template:
            return

        scale, ox, oy, rw, rh = self._get_canvas_geometry()
        dx = (event.pos().x() - self._drag_start_pos.x()) / scale
        dy = (event.pos().y() - self._drag_start_pos.y()) / scale
        cw, ch = self.template.canvas_size[0], self.template.canvas_size[1]
        container_w = 600 if (self.template.is_dual_strip and cw == 1200) else cw

        # 0. Co giãn kích thước ô ảnh trực tiếp trên bản vẽ qua 4 tay nắm góc
        if self._is_resizing_slot and self.selected_item_type == "slot" and 0 <= self.selected_slot_index < len(self.template.slots):
            s = self.template.slots[self.selected_slot_index]
            corner = self._slot_resize_corner
            min_w, min_h = 100, 80

            new_x = self._start_slot_x
            new_y = self._start_slot_y
            new_w = self._start_slot_w
            new_h = self._start_slot_h

            if "l" in corner:
                new_x = int(self._start_slot_x + dx)
                new_w = int(self._start_slot_w - dx)
                if new_w < min_w:
                    new_x = self._start_slot_x + self._start_slot_w - min_w
                    new_w = min_w
            elif "r" in corner:
                new_w = int(self._start_slot_w + dx)
                if new_w < min_w:
                    new_w = min_w

            if "t" in corner:
                new_y = int(self._start_slot_y + dy)
                new_h = int(self._start_slot_h - dy)
                if new_h < min_h:
                    new_y = self._start_slot_y + self._start_slot_h - min_h
                    new_h = min_h
            elif "b" in corner:
                new_h = int(self._start_slot_h + dy)
                if new_h < min_h:
                    new_h = min_h

            if self.snap_to_grid and self.grid_size > 0:
                snap_step = 20
                new_x = round(new_x / snap_step) * snap_step
                new_y = round(new_y / snap_step) * snap_step
                new_w = round(new_w / snap_step) * snap_step
                new_h = round(new_h / snap_step) * snap_step

            new_x = max(0, min(new_x, container_w - min_w))
            new_y = max(0, min(new_y, ch - min_h))
            new_w = max(min_w, min(new_w, container_w - new_x))
            new_h = max(min_h, min(new_h, ch - new_y))

            s.x = new_x
            s.y = new_y
            s.w = new_w
            s.h = new_h
            self.slot_resized.emit(self.selected_slot_index, new_x, new_y, new_w, new_h)
            self.update()
            return

        # 1. Thao tác trên lớp Text: Thay đổi cỡ hoặc Kéo vị trí tự do
        if self.selected_item_type == "text" and 0 <= self.selected_text_index < len(self.template.text_layers):
            t = self.template.text_layers[self.selected_text_index]

            if self._is_resizing_text:
                new_size = max(16, min(120, int(self._start_font_size + dy * 0.35)))
                if new_size != t.font_size:
                    t.font_size = new_size
                    self.text_resized.emit(self.selected_text_index, new_size)
                    self.update()
                return

            if self._is_dragging:
                if getattr(t, 'is_locked', False):
                    return

                new_x = int(self._start_text_x + dx)
                new_y = int(self._start_text_y + dy)

                if self.snap_to_grid and self.grid_size > 0:
                    snap_step = 20
                    new_x = round(new_x / snap_step) * snap_step
                    new_y = round(new_y / snap_step) * snap_step

                new_x = max(0, min(new_x, container_w))
                new_y = max(10, min(new_y, ch - 20))

                t.x = new_x
                t.y = new_y
                t.position_mode = "custom"
                self.text_moved.emit(self.selected_text_index, new_x, new_y)
                self.update()
                return

        # 2. Thao tác trên lớp Logo: Kéo di chuyển
        if self.selected_item_type == "logo" and 0 <= self.selected_logo_index < len(self.template.logo_layers):
            l = self.template.logo_layers[self.selected_logo_index]
            l.x = max(0, min(int(self._start_logo_x + dx), container_w - l.w))
            l.y = max(0, min(int(self._start_logo_y + dy), ch - l.h))
            l.position_mode = "custom"
            self.logo_moved.emit(self.selected_logo_index, l.x, l.y)
            self.update()
            return

        # 3. Thao tác trên ô Photo Slot: Kéo căn ảnh hoặc Di chuyển ô
        if self.selected_item_type == "slot" and 0 <= self.selected_slot_index < len(self.template.slots):
            s = self.template.slots[self.selected_slot_index]

            if self.drag_mode == "pan_crop":
                norm_dx = - (dx / max(1.0, s.w * 0.4))
                norm_dy = - (dy / max(1.0, s.h * 0.4))
                new_ox = max(-1.0, min(1.0, self._start_crop_ox + norm_dx))
                new_oy = max(-1.0, min(1.0, self._start_crop_oy + norm_dy))
                s.crop_offset_x = round(new_ox, 3)
                s.crop_offset_y = round(new_oy, 3)
                self.slot_crop_panned.emit(self.selected_slot_index, s.crop_offset_x, s.crop_offset_y)
                self.update()
            else:
                new_x = int(self._start_slot_x + dx)
                new_y = int(self._start_slot_y + dy)

                if self.snap_to_grid and self.grid_size > 0:
                    snap_step = 20
                    new_x = round(new_x / snap_step) * snap_step
                    new_y = round(new_y / snap_step) * snap_step

                new_x = max(0, min(new_x, container_w - s.w))
                new_y = max(0, min(new_y, ch - s.h))

                s.x = new_x
                s.y = new_y
                self.slot_moved.emit(self.selected_slot_index, new_x, new_y)
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._is_dragging or self._is_resizing_text or self._is_resizing_slot:
                self._is_dragging = False
                self._is_resizing_text = False
                self._is_resizing_slot = False
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
        self.canvas.setMinimumSize(220, 220)
        self.canvas.slot_selected.connect(self._on_slot_selected_from_canvas)
        self.canvas.slot_moved.connect(self._on_slot_moved_from_canvas)
        self.canvas.slot_resized.connect(self._on_slot_resized_from_canvas)
        self.canvas.slot_crop_panned.connect(self._on_slot_crop_panned_from_canvas)
        self.canvas.text_selected.connect(self._on_text_selected_from_canvas)
        self.canvas.text_moved.connect(self._on_text_moved_from_canvas)
        self.canvas.text_resized.connect(self._on_text_resized_from_canvas)
        self.canvas.logo_selected.connect(self._on_logo_selected_from_canvas)
        self.canvas.logo_moved.connect(self._on_logo_moved_from_canvas)
        self.canvas.drag_finished.connect(lambda: self._update_preview(full_render=True))
        left_layout.addWidget(self.canvas, 1)

        # THANH CÔNG CỤ CHẾ ĐỘ KÉO CHUỘT VÀ LƯỚI BẢN VẼ
        tools_bar = QHBoxLayout()
        tools_bar.setSpacing(8)

        self.btn_mode_crop = QPushButton("🖼️ Kéo Căn Ảnh")
        self.btn_mode_crop.setCheckable(True)
        self.btn_mode_crop.setChecked(True)
        self.btn_mode_crop.setObjectName("btn_champagne")
        self.btn_mode_crop.setToolTip("Rê chuột trực tiếp trong ô ảnh trên bản vẽ để điều chỉnh vùng cắt")

        self.btn_mode_move = QPushButton("📐 Di Chuyển Ô")
        self.btn_mode_move.setCheckable(True)
        self.btn_mode_move.setObjectName("btn_secondary")
        self.btn_mode_move.setToolTip("Rê chuột để di chuyển vị trí ô ảnh trên khung in")

        mode_grp = QButtonGroup(self)
        mode_grp.addButton(self.btn_mode_crop)
        mode_grp.addButton(self.btn_mode_move)
        self.btn_mode_crop.toggled.connect(self._on_drag_mode_toggled)

        tools_bar.addWidget(self.btn_mode_crop)
        tools_bar.addWidget(self.btn_mode_move)

        self.chk_grid = QCheckBox("Lưới")
        self.chk_grid.setChecked(True)
        self.chk_grid.toggled.connect(lambda c: setattr(self.canvas, 'show_grid', c) or self.canvas.update())
        tools_bar.addWidget(self.chk_grid)

        self.chk_snap = QCheckBox("Bắt Điểm")
        self.chk_snap.setChecked(True)
        self.chk_snap.toggled.connect(lambda c: setattr(self.canvas, 'snap_to_grid', c))
        tools_bar.addWidget(self.chk_snap)

        self.chk_safe_zone = QCheckBox("Vùng An Toàn")
        self.chk_safe_zone.setChecked(True)
        self.chk_safe_zone.toggled.connect(lambda c: setattr(self.canvas, 'show_safe_zone', c) or self.canvas.update())
        tools_bar.addWidget(self.chk_safe_zone)

        self.chk_cut_lines = QCheckBox("Mép Cắt")
        self.chk_cut_lines.setChecked(True)
        self.chk_cut_lines.toggled.connect(lambda c: setattr(self.canvas, 'show_cut_lines', c) or self.canvas.update())
        tools_bar.addWidget(self.chk_cut_lines)

        tools_bar.addStretch()

        self.lbl_warnings = QLabel("300 DPI")
        self.lbl_warnings.setStyleSheet("color: #10B981; font-weight: 500;")
        tools_bar.addWidget(self.lbl_warnings)

        left_layout.addLayout(tools_bar)
        main_layout.addLayout(left_layout, 6)

        # ==============================================================
        # CỘT PHẢI: BẢNG ĐIỀU KHIỂN BỐ CỤC (CUỘN ĐỘC LẬP & TRỰC QUAN)
        # SỬA TRIỆT ĐỂ LỖI THANH CUỘN CHE NỘI DUNG:
        # - Chừa lề phải 26px cho thanh cuộn.
        # - Lề dưới 40px cho phép cuộn đến tận đáy.
        # - Thanh cuộn nằm riêng biệt, không che lấp bất kỳ nút/trường nào.
        # ==============================================================
        scroll = QScrollArea()
        self.scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(340)
        scroll.setMaximumWidth(480)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        scroll_content = QWidget()
        right_layout = QVBoxLayout(scroll_content)
        self.right_layout = right_layout
        right_layout.setContentsMargins(10, 10, 26, 40)
        right_layout.setSpacing(14)

        # --------------------------------------------------------------
        # 1. THUỘC TÍNH KHUNG IN & VĂN BẢN MẶC ĐỊNH
        # --------------------------------------------------------------
        grp_props = QGroupBox("1. Thuộc Tính Khung In")
        l_props = QVBoxLayout(grp_props)
        l_props.setSpacing(8)

        form_props = QFormLayout()
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
        l_props.addLayout(form_props)

        # MỤC MỚI: VĂN BẢN MẶC ĐỊNH CỦA KHUNG IN
        lbl_def_head = QLabel("<b>Văn Bản Mặc Định Cho Khung:</b>")
        lbl_def_head.setStyleSheet("color: #D4AF37; font-size: 13px; margin-top: 4px;")
        l_props.addWidget(lbl_def_head)

        self.txt_def_text = QLineEdit()
        self.txt_def_text.setPlaceholderText("VD: 1998 TEAM • Studio Phóng Sự Cưới")
        l_props.addWidget(self.txt_def_text)

        def_font_row = QHBoxLayout()
        self.combo_def_font = QComboBox()
        self.combo_def_font.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        # Nạp danh sách font từ FontRegistry
        FontRegistry.initialize()
        for f_item in FontRegistry.list_fonts("all"):
            self.combo_def_font.addItem(f"{f_item.display_name} ({f_item.category_label})", f_item.family_name)
        def_font_row.addWidget(self.combo_def_font, 1)

        self.spin_def_size = QSpinBox()
        self.spin_def_size.setRange(16, 120)
        self.spin_def_size.setValue(34)
        def_font_row.addWidget(self.spin_def_size)

        self.btn_def_bold = QPushButton("B")
        self.btn_def_bold.setCheckable(True)
        self.btn_def_bold.setChecked(True)
        self.btn_def_bold.setFixedWidth(32)
        self.btn_def_bold.setStyleSheet("font-weight: bold;")
        def_font_row.addWidget(self.btn_def_bold)

        self.btn_def_italic = QPushButton("I")
        self.btn_def_italic.setCheckable(True)
        self.btn_def_italic.setFixedWidth(32)
        self.btn_def_italic.setStyleSheet("font-style: italic;")
        def_font_row.addWidget(self.btn_def_italic)
        l_props.addLayout(def_font_row)

        def_style_row = QHBoxLayout()
        def_style_row.addWidget(QLabel("Màu:"))
        self.btn_def_color = QPushButton("#D4AF37")
        self.btn_def_color.setObjectName("btn_secondary")
        self.btn_def_color.clicked.connect(self._choose_def_text_color)
        def_style_row.addWidget(self.btn_def_color)

        def_style_row.addWidget(QLabel("Lề an toàn:"))
        self.spin_def_margin = QSpinBox()
        self.spin_def_margin.setRange(10, 120)
        self.spin_def_margin.setValue(40)
        self.spin_def_margin.setSuffix(" px")
        def_style_row.addWidget(self.spin_def_margin)
        l_props.addLayout(def_style_row)

        btn_apply_def = QPushButton("Áp Dụng Cho Lớp Chữ Đang Chọn")
        btn_apply_def.setObjectName("btn_secondary")
        btn_apply_def.clicked.connect(self._apply_default_to_selected_text)
        l_props.addWidget(btn_apply_def)

        # NÚT ÁP DỤNG THUỘC TÍNH KHUNG IN & ENTER KEY
        self.btn_apply_props = QPushButton("✅ Áp Dụng Thuộc Tính Khung")
        self.btn_apply_props.setObjectName("btn_champagne")
        self.btn_apply_props.setToolTip("Áp dụng tên, khổ in, màu nền và văn bản mặc định (hoặc nhấn Enter)")
        self.btn_apply_props.clicked.connect(self._apply_frame_properties)
        l_props.addWidget(self.btn_apply_props)

        self.lbl_props_status = QLabel("")
        self.lbl_props_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
        self.lbl_props_status.setAlignment(Qt.AlignCenter)
        l_props.addWidget(self.lbl_props_status)

        self.txt_name.returnPressed.connect(self._apply_frame_properties)
        self.txt_def_text.returnPressed.connect(self._apply_frame_properties)

        right_layout.addWidget(grp_props)

        # --------------------------------------------------------------
        # 2. TỰ ĐỘNG CĂN CHỈNH ẢNH (AUTO PHOTO FITTING)
        # ĐÃ BỎ HẾT CHỮ TRONG NGOẶC ĐƠN VÀ THUẬT NGỮ KỸ THUẬT RƯỜM RÀ
        # --------------------------------------------------------------
        grp_auto_fit = QGroupBox("2. Tự Động Căn Chỉnh Ảnh")
        l_fit = QVBoxLayout(grp_auto_fit)
        l_fit.setSpacing(10)

        # Selector chọn ô ảnh
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

        # Cách căn ảnh: Lấp Đầy Khung vs Hiển Thị Toàn Ảnh (Không ngoặc đơn)
        l_fit.addWidget(QLabel("<b>Cách Căn Ảnh:</b>"))
        self.rb_fit_cover = QRadioButton("Lấp Đầy Khung")
        self.rb_fit_cover.setToolTip("Tự động lấp kín 100% ô ảnh, không lộ viền trắng và giữ nguyên tỷ lệ gốc")
        self.rb_fit_contain = QRadioButton("Hiển Thị Toàn Ảnh")
        self.rb_fit_contain.setToolTip("Hiển thị trọn vẹn toàn bộ ảnh chụp trong ô")
        self.rb_fit_cover.setChecked(True)

        fit_grp = QButtonGroup(self)
        fit_grp.addButton(self.rb_fit_cover)
        fit_grp.addButton(self.rb_fit_contain)
        self.rb_fit_cover.toggled.connect(self._on_slot_fit_mode_changed)
        l_fit.addWidget(self.rb_fit_cover)
        l_fit.addWidget(self.rb_fit_contain)

        # Vị trí căn tâm: Tự Động Căn Giữa vs Ưu Tiên Khuôn Mặt (Chỉ thêm khi có bộ nhận diện)
        l_fit.addWidget(QLabel("<b>Vị Trí Căn Tâm:</b>"))
        self.combo_slot_position = QComboBox()
        self.combo_slot_position.addItem("🎯 Tự Động Căn Giữa", "center")
        if get_face_detector() is not None:
            self.combo_slot_position.addItem("👤 Ưu Tiên Khuôn Mặt", "face")
        self.combo_slot_position.setToolTip("Tự động căn góc ảnh theo tâm khuôn mặt người chụp")
        self.combo_slot_position.currentIndexChanged.connect(self._on_slot_position_changed)
        l_fit.addWidget(self.combo_slot_position)

        # Thu phóng ảnh
        zoom_header = QHBoxLayout()
        zoom_header.addWidget(QLabel("<b>Thu Phóng Ảnh:</b>"))
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

        # Dịch chuyển vùng cắt & Nút Đặt Lại Tâm Cắt
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

        # Vùng an toàn & Bo góc
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
        self.btn_apply_all_slots = btn_apply_all
        btn_apply_all.setObjectName("btn_champagne")
        btn_apply_all.clicked.connect(self._apply_fitting_to_all_slots)
        l_fit.addWidget(btn_apply_all)

        right_layout.addWidget(grp_auto_fit)

        # --------------------------------------------------------------
        # 3. CHỈNH SỬA VĂN BẢN (VISUAL TEXT EDITING)
        # CHO PHÉP KÉO THẢ TỰ DO KHÔNG TỰ NHẢY VỀ GIỮA
        # CÓ NÚT CĂN GIỮA, CĂN TRÊN, CĂN DƯỚI, ĐẶT LẠI VỊ TRÍ, KHÓA LỚP
        # --------------------------------------------------------------
        grp_text = QGroupBox("3. Chỉnh Sửa Văn Bản")
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

        lbl_macros = QLabel("Gợi ý biến động: {event_name} • {date} • {location}")
        lbl_macros.setStyleSheet("color: #64748B; font-size: 12px;")
        l_txt.addWidget(lbl_macros)

        # Phông chữ & Danh mục phân loại phông chữ
        l_txt.addWidget(QLabel("<b>Bộ Sưu Tập Phông Chữ Cưới (Offline):</b>"))
        font_cat_bar = QHBoxLayout()
        font_cat_bar.setSpacing(4)
        self.btn_font_all = QPushButton("Tất Cả")
        self.btn_font_hw = QPushButton("Viết Tay")
        self.btn_font_lux = QPushButton("Sang Trọng")
        self.btn_font_mod = QPushButton("Hiện Đại")

        self.font_cat_grp = QButtonGroup(self)
        for b, cat in [(self.btn_font_all, "all"), (self.btn_font_hw, "handwriting"),
                       (self.btn_font_lux, "luxury"), (self.btn_font_mod, "modern")]:
            b.setCheckable(True)
            b.setObjectName("btn_secondary")
            self.font_cat_grp.addButton(b)
            b.clicked.connect(lambda _, c=cat: self._filter_fonts_by_category(c))

        self.btn_font_all.setChecked(True)
        font_cat_bar.addWidget(self.btn_font_all)
        font_cat_bar.addWidget(self.btn_font_hw)
        font_cat_bar.addWidget(self.btn_font_lux)
        font_cat_bar.addWidget(self.btn_font_mod)
        l_txt.addLayout(font_cat_bar)

        font_bar = QHBoxLayout()
        font_bar.addWidget(QLabel("Font:"))
        self.combo_font = QComboBox()
        self.combo_font.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._populate_font_combo("all")
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
        self.btn_bold.setFixedWidth(34)
        self.btn_bold.setStyleSheet("font-weight: bold; font-size: 15px;")
        self.btn_bold.toggled.connect(self._on_text_style_changed)
        font_bar.addWidget(self.btn_bold)

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedWidth(34)
        self.btn_italic.setStyleSheet("font-style: italic; font-size: 15px;")
        self.btn_italic.toggled.connect(self._on_text_style_changed)
        font_bar.addWidget(self.btn_italic)

        l_txt.addLayout(font_bar)

        # Mẫu xem trước phông chữ trực tiếp
        self.lbl_font_preview = QLabel("1998 TEAM • Trăm Năm Hạnh Phúc")
        self.lbl_font_preview.setAlignment(Qt.AlignCenter)
        self.lbl_font_preview.setStyleSheet(
            "background-color: #070A12; border: 1px solid #1E293B; border-radius: 6px; padding: 6px; color: #D4AF37; font-size: 15px;"
        )
        l_txt.addWidget(self.lbl_font_preview)

        # Màu sắc chữ & Bảng màu mẫu
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Màu:"))
        self.btn_text_color = QPushButton("#FFFFFF")
        self.btn_text_color.setObjectName("btn_secondary")
        self.btn_text_color.clicked.connect(self._choose_text_color)
        color_layout.addWidget(self.btn_text_color)

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
        l_txt.addWidget(QLabel("<b>Căn Lề Chữ:</b>"))
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

        # NÚT ĐIỀU KHIỂN VỊ TRÍ CHỦ ĐỘNG: CĂN GIỮA, CĂN TRÊN, CĂN DƯỚI, ĐẶT LẠI VỊ TRÍ, KHÓA LỚP
        l_txt.addWidget(QLabel("<b>Định Vị & Căn Chỉnh Vị Trí:</b>"))
        pos_actions = QGridLayout()
        pos_actions.setSpacing(6)

        self.btn_center_text = QPushButton("↔️ Căn Giữa")
        self.btn_center_text.setObjectName("btn_secondary")
        self.btn_center_text.clicked.connect(self._center_selected_text)
        pos_actions.addWidget(self.btn_center_text, 0, 0)

        self.btn_top_text = QPushButton("⬆️ Căn Trên")
        self.btn_top_text.setObjectName("btn_secondary")
        self.btn_top_text.clicked.connect(self._align_selected_text_top)
        pos_actions.addWidget(self.btn_top_text, 0, 1)

        self.btn_bottom_text = QPushButton("⬇️ Căn Dưới")
        self.btn_bottom_text.setObjectName("btn_secondary")
        self.btn_bottom_text.clicked.connect(self._align_selected_text_bottom)
        pos_actions.addWidget(self.btn_bottom_text, 1, 0)

        self.btn_reset_pos_text = QPushButton("↺ Đặt Lại")
        self.btn_reset_pos_text.setObjectName("btn_secondary")
        self.btn_reset_pos_text.clicked.connect(self._reset_selected_text_position)
        pos_actions.addWidget(self.btn_reset_pos_text, 1, 1)

        l_txt.addLayout(pos_actions)

        # Nút Khóa / Mở Khóa / Ẩn / Hiện Lớp Chữ
        lock_row = QHBoxLayout()
        self.btn_toggle_visible_text = QPushButton("👁️ Đang Hiện")
        self.btn_toggle_visible_text.setObjectName("btn_secondary")
        self.btn_toggle_visible_text.setToolTip("Ẩn hoặc hiện lớp chữ trên bản in")
        self.btn_toggle_visible_text.clicked.connect(self._toggle_visible_selected_text)
        lock_row.addWidget(self.btn_toggle_visible_text)

        self.btn_lock_text = QPushButton("🔓 Vị Trí: Cho Phép Kéo")
        self.btn_lock_text.setObjectName("btn_secondary")
        self.btn_lock_text.setCheckable(True)
        self.btn_lock_text.toggled.connect(self._toggle_lock_text)
        lock_row.addWidget(self.btn_lock_text)

        lock_row.addWidget(QLabel("Lề:"))
        self.spin_safe_margin = QSpinBox()
        self.spin_safe_margin.setRange(10, 120)
        self.spin_safe_margin.setValue(40)
        self.spin_safe_margin.setSuffix(" px")
        self.spin_safe_margin.valueChanged.connect(self._on_text_margin_changed)
        lock_row.addWidget(self.spin_safe_margin)
        l_txt.addLayout(lock_row)

        # Giãn đều các lớp chữ dọc & Cảnh báo đè lớp
        dist_row = QHBoxLayout()
        self.btn_distribute_text = QPushButton("↕️ Giãn Đều Các Lớp Chữ Dọc")
        self.btn_distribute_text.setObjectName("btn_secondary")
        self.btn_distribute_text.setToolTip("Tự động phân bổ đều khoảng cách các lớp chữ theo chiều dọc")
        self.btn_distribute_text.clicked.connect(self._distribute_text_layers)
        dist_row.addWidget(self.btn_distribute_text)
        l_txt.addLayout(dist_row)

        self.lbl_text_overlap = QLabel("")
        self.lbl_text_overlap.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 12px;")
        self.lbl_text_overlap.setAlignment(Qt.AlignCenter)
        l_txt.addWidget(self.lbl_text_overlap)

        right_layout.addWidget(grp_text)

        # --------------------------------------------------------------
        # 4. LOGO & HỌA TIẾT (LOGO LAYERS)
        # --------------------------------------------------------------
        grp_logo = QGroupBox("4. Logo & Họa Tiết")
        l_lg = QVBoxLayout(grp_logo)
        l_lg.setSpacing(10)

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

        # Kích thước Logo (Khóa tỷ lệ gốc)
        logo_scale_hdr = QHBoxLayout()
        logo_scale_hdr.addWidget(QLabel("<b>Kích Thước Logo:</b>"))
        self.lbl_logo_scale_val = QLabel("100%")
        self.lbl_logo_scale_val.setStyleSheet("color: #D4AF37; font-weight: bold;")
        logo_scale_hdr.addWidget(self.lbl_logo_scale_val)
        logo_scale_hdr.addStretch()
        l_lg.addLayout(logo_scale_hdr)

        self.slider_logo_scale = QSlider(Qt.Horizontal)
        self.slider_logo_scale.setRange(20, 200)
        self.slider_logo_scale.setValue(100)
        self.slider_logo_scale.setSingleStep(5)
        self.slider_logo_scale.setToolTip("Khóa tỷ lệ gốc không bao giờ méo ảnh")
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

        # Độ Trong Suốt
        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("Độ trong suốt:"))
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

        # Văn bản mặc định của khung
        self.txt_def_text.setText(getattr(f, 'default_text', "1998 TEAM • Studio Phóng Sự Cưới"))
        idx_def_f = self.combo_def_font.findText(getattr(f, 'default_font_name', "Arial"), Qt.MatchContains)
        if idx_def_f >= 0:
            self.combo_def_font.setCurrentIndex(idx_def_f)
        self.spin_def_size.setValue(getattr(f, 'default_font_size', 34))
        self.btn_def_bold.setChecked(getattr(f, 'default_is_bold', True))
        self.btn_def_italic.setChecked(getattr(f, 'default_is_italic', False))
        def_col = getattr(f, 'default_font_color', "#D4AF37")
        self.btn_def_color.setText(def_col)
        self.btn_def_color.setStyleSheet(f"background-color: {def_col}; color: #000000; font-weight: bold;")
        self.spin_def_margin.setValue(getattr(f, 'default_safe_margin', 40))

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
    # ĐIỀU KHIỂN & ĐỒNG BỘ VĂN BẢN MẶC ĐỊNH CHO KHUNG
    # ==============================================================
    def _choose_def_text_color(self):
        col = QColorDialog.getColor(QColor(self.btn_def_color.text()), self, "Chọn Màu Văn Bản Mặc Định")
        if col.isValid():
            hex_c = col.name().upper()
            self.btn_def_color.setText(hex_c)
            self.btn_def_color.setStyleSheet(f"background-color: {hex_c}; color: #000000; font-weight: bold;")
            if self.current_frame:
                self.current_frame.default_font_color = hex_c

    def _apply_default_to_selected_text(self):
        if not self.current_frame or not self.current_frame.text_layers:
            return
        idx = self.combo_text_selector.currentIndex()
        if not (0 <= idx < len(self.current_frame.text_layers)):
            return

        t = self.current_frame.text_layers[idx]
        t.font_name = self.combo_def_font.currentText()
        t.font_size = self.spin_def_size.value()
        t.font_color = self.btn_def_color.text()
        t.is_bold = self.btn_def_bold.isChecked()
        t.is_italic = self.btn_def_italic.isChecked()
        t.safe_margin = self.spin_def_margin.value()

        self._populate_text_controls(idx)
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
    # ==============================================================
    # ĐIỀU KHIỂN & ĐỒNG BỘ VĂN BẢN (TEXT LAYERS)
    # TỰ DO ĐẶT TỌA ĐỘ VÀ KHÔNG BAO GIỜ TỰ NHẢY VỀ GIỮA
    # ==============================================================
    def _populate_font_combo(self, category: str = "all"):
        self.combo_font.blockSignals(True)
        cur_data = self.combo_font.currentData()
        self.combo_font.clear()
        FontRegistry.initialize()
        fonts = FontRegistry.list_fonts(category)
        for f in fonts:
            self.combo_font.addItem(f"{f.display_name} ({f.category_label})", f.family_name)
        if cur_data:
            idx = self.combo_font.findData(cur_data)
            if idx >= 0:
                self.combo_font.setCurrentIndex(idx)
        self.combo_font.blockSignals(False)

    def _filter_fonts_by_category(self, category: str):
        self._populate_font_combo(category)
        self._on_text_style_changed()

    def _populate_text_controls(self, txt_idx: int):
        if not self.current_frame or not (0 <= txt_idx < len(self.current_frame.text_layers)):
            return

        t = self.current_frame.text_layers[txt_idx]
        self._is_updating_ui = True

        self.txt_content.setText(t.text or "")
        f_name = getattr(t, 'font_name', 'Arial')
        f_idx = self.combo_font.findData(f_name)
        if f_idx < 0:
            f_idx = self.combo_font.findText(f_name, Qt.MatchContains)
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

        is_locked = getattr(t, 'is_locked', False)
        self.btn_lock_text.setChecked(is_locked)
        self.btn_lock_text.setText("🔒 Vị Trí: Đã Khóa" if is_locked else "🔓 Vị Trí: Cho Phép Kéo")

        is_vis = getattr(t, 'is_visible', True)
        self.btn_toggle_visible_text.setText("👁️ Đang Hiện" if is_vis else "👁️‍🗨️ Đang Ẩn")

        self.spin_safe_margin.setValue(getattr(t, 'safe_margin', 40))

        # Cập nhật xem trước phông chữ
        fam = self.combo_font.currentData() or self.combo_font.currentText()
        pf = QFont(fam, 14)
        pf.setBold(self.btn_bold.isChecked())
        pf.setItalic(self.btn_italic.isChecked())
        self.lbl_font_preview.setFont(pf)
        preview_sample = (t.text or "1998 TEAM • Studio Phóng Sự Cưới").split("\n")[0][:28]
        self.lbl_font_preview.setText(preview_sample or "1998 TEAM • Studio Phóng Sự Cưới")

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
            fam = self.combo_font.currentData() or self.combo_font.currentText()
            t.font_name = fam
            t.font_size = self.spin_font_size.value()
            t.is_bold = self.btn_bold.isChecked()
            t.is_italic = self.btn_italic.isChecked()

            # Cập nhật nhãn xem trước
            pf = QFont(fam, 14)
            pf.setBold(t.is_bold)
            pf.setItalic(t.is_italic)
            self.lbl_font_preview.setFont(pf)

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

    def _center_selected_text(self):
        """Chủ động căn giữa lớp chữ theo chiều ngang."""
        if not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            t = self.current_frame.text_layers[idx]
            cw = 600 if self.current_frame.is_dual_strip else self.current_frame.canvas_size[0]
            t.x = cw // 2
            t.position_mode = "custom"
            self._update_preview(full_render=True)

    def _align_selected_text_top(self):
        """Chủ động căn lớp chữ lên mép trên cùng an toàn."""
        if not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            t = self.current_frame.text_layers[idx]
            t.y = getattr(t, 'safe_margin', 40)
            t.position_mode = "custom"
            self._update_preview(full_render=True)

    def _align_selected_text_bottom(self):
        """Chủ động căn lớp chữ xuống mép dưới cùng an toàn."""
        if not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            t = self.current_frame.text_layers[idx]
            ch = self.current_frame.canvas_size[1]
            safe = getattr(t, 'safe_margin', 40)
            t.y = ch - safe - int(t.font_size * 2)
            t.position_mode = "custom"
            self._update_preview(full_render=True)

    def _reset_selected_text_position(self):
        """Đặt lại vị trí lớp chữ về chuẩn dưới cùng chính giữa."""
        if not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            t = self.current_frame.text_layers[idx]
            cw = 600 if self.current_frame.is_dual_strip else self.current_frame.canvas_size[0]
            ch = self.current_frame.canvas_size[1]
            safe = getattr(t, 'safe_margin', 40)
            t.x = cw // 2
            t.y = ch - safe - int(t.font_size * 2)
            t.position_mode = "custom"
            self._update_preview(full_render=True)

    def _toggle_lock_text(self, locked: bool):
        if not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            t = self.current_frame.text_layers[idx]
            t.is_locked = locked
            self.btn_lock_text.setText("🔒 Vị Trí: Đã Khóa" if locked else "🔓 Vị Trí: Cho Phép Kéo")
            self.canvas.update()

    def _on_text_margin_changed(self, val: int):
        if self._is_updating_ui or not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            self.current_frame.text_layers[idx].safe_margin = val
            self._update_preview(full_render=True)

    def _toggle_visible_selected_text(self):
        """Bật/tắt trạng thái ẩn/hiện của lớp chữ đang chọn."""
        if not self.current_frame:
            return
        idx = self.combo_text_selector.currentIndex()
        if 0 <= idx < len(self.current_frame.text_layers):
            t = self.current_frame.text_layers[idx]
            cur_vis = getattr(t, 'is_visible', True)
            t.is_visible = not cur_vis
            self.btn_toggle_visible_text.setText("👁️ Đang Hiện" if t.is_visible else "👁️‍🗨️ Đang Ẩn")
            self._update_preview(full_render=True)

    def _distribute_text_layers(self):
        """Giãn đều khoảng cách các lớp chữ theo chiều dọc."""
        if not self.current_frame or len(self.current_frame.text_layers) < 2:
            return
        visible_layers = [t for t in self.current_frame.text_layers if getattr(t, 'is_visible', True)]
        if len(visible_layers) < 2:
            return

        visible_layers.sort(key=lambda t: t.y)
        ch = self.current_frame.canvas_size[1]
        safe = getattr(self.current_frame, 'safe_zone_px', 40)

        top_y = max(safe + 40, visible_layers[0].y)
        bottom_y = min(ch - safe - 60, max(top_y + 100, visible_layers[-1].y))
        step = (bottom_y - top_y) / float(len(visible_layers) - 1)

        for i, t in enumerate(visible_layers):
            t.y = int(top_y + i * step)
            t.position_mode = "custom"

        self._update_preview(full_render=True)
        self.lbl_props_status.setText("✅ Đã giãn đều các lớp chữ!")
        QTimer.singleShot(2500, lambda: self.lbl_props_status.setText(""))

    def _check_text_overlaps(self) -> bool:
        """Kiểm tra xem có bất kỳ hai lớp chữ nào bị đè lên nhau không."""
        if not self.current_frame or len(self.current_frame.text_layers) < 2:
            return False
        rects = []
        for i in range(len(self.current_frame.text_layers)):
            txt = self.current_frame.text_layers[i]
            if getattr(txt, 'is_visible', True):
                r = self.canvas._get_text_rect_300dpi(i)
                if not r.isEmpty():
                    rects.append(r)

        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if rects[i].intersects(rects[j]):
                    return True
        return False

    def _add_text(self):
        if not self.current_frame:
            return
        num = len(self.current_frame.text_layers) + 1
        cw = 600 if self.current_frame.is_dual_strip else self.current_frame.canvas_size[0]
        ch = self.current_frame.canvas_size[1]

        # Áp dụng các giá trị văn bản mặc định của khung đã thiết lập
        f = self.current_frame
        def_txt = getattr(f, 'default_text', "1998 TEAM • Studio Phóng Sự Cưới")
        def_font = getattr(f, 'default_font_name', "Be Vietnam Pro")
        def_size = getattr(f, 'default_font_size', 34)
        def_color = getattr(f, 'default_font_color', "#D4AF37")
        def_bold = getattr(f, 'default_is_bold', True)
        def_italic = getattr(f, 'default_is_italic', False)
        def_margin = getattr(f, 'default_safe_margin', 40)

        # Smart placement: đặt dưới lớp thấp nhất hiện có để không bị đè lên nhau
        if self.current_frame.text_layers:
            lowest_y = max(
                getattr(t, 'y', ch - def_margin - 60) + int(getattr(t, 'font_size', 34) * 1.6)
                for t in self.current_frame.text_layers
            )
            new_y = lowest_y + 35
            if new_y > (ch - def_margin - int(def_size * 2)):
                stagger_idx = len(self.current_frame.text_layers) % 3
                new_y = ch - def_margin - int(def_size * 2) - stagger_idx * 55
        else:
            new_y = ch - def_margin - int(def_size * 2)

        new_txt = TextLayer(
            id=f"txt_{num}",
            text=def_txt,
            x=cw // 2,
            y=new_y,
            font_size=def_size,
            font_color=def_color,
            font_name=def_font,
            alignment="center",
            is_bold=def_bold,
            is_italic=def_italic,
            is_locked=False,
            is_visible=True,
            position_mode="custom",
            safe_margin=def_margin
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
        pass

    def _on_slot_resized_from_canvas(self, slot_index: int, new_x: int, new_y: int, new_w: int, new_h: int):
        if not self.current_frame or not (0 <= slot_index < len(self.current_frame.slots)):
            return
        if 0 <= slot_index < self.combo_slots_selector.count():
            s = self.current_frame.slots[slot_index]
            self.combo_slots_selector.setItemText(slot_index, f"Ô #{s.id} ({new_w}x{new_h} px)")

    def _on_slot_crop_panned_from_canvas(self, slot_index: int, ox: float, oy: float):
        self.lbl_crop_offset.setText(f"Cắt lệch: ({int(ox*100)}%, {int(oy*100)}%)")

    def _on_text_selected_from_canvas(self, text_index: int):
        if 0 <= text_index < self.combo_text_selector.count():
            self._is_updating_ui = True
            self.combo_text_selector.setCurrentIndex(text_index)
            self._is_updating_ui = False
            self._populate_text_controls(text_index)

    def _on_text_moved_from_canvas(self, text_index: int, new_x: int, new_y: int):
        pass

    def _on_text_resized_from_canvas(self, text_index: int, new_size: int):
        self._is_updating_ui = True
        self.spin_font_size.setValue(new_size)
        self._is_updating_ui = False

    def _on_logo_selected_from_canvas(self, logo_index: int):
        if 0 <= logo_index < self.combo_logo_selector.count():
            self._is_updating_ui = True
            self.combo_logo_selector.setCurrentIndex(logo_index)
            self._is_updating_ui = False
            self._populate_logo_controls(logo_index)

    def _on_logo_moved_from_canvas(self, logo_index: int, new_x: int, new_y: int):
        pass

    def _apply_frame_properties(self):
        """Áp dụng thuộc tính khung in từ biểu mẫu vào bản thiết kế và cập nhật xem trước."""
        if not self.current_frame:
            return
        f = self._build_frame_from_ui()
        if not f:
            return
        self._update_preview(full_render=True)
        self.lbl_props_status.setText("✅ Đã áp dụng thuộc tính khung in!")
        QTimer.singleShot(2500, lambda: self.lbl_props_status.setText(""))

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

        # Lưu thiết lập văn bản mặc định
        f.default_text = self.txt_def_text.text()
        f.default_font_name = self.combo_def_font.currentText()
        f.default_font_size = self.spin_def_size.value()
        f.default_font_color = self.btn_def_color.text()
        f.default_is_bold = self.btn_def_bold.isChecked()
        f.default_is_italic = self.btn_def_italic.isChecked()
        f.default_safe_margin = self.spin_def_margin.value()

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

        # Kiểm tra cảnh báo đè lớp chữ
        if self._check_text_overlaps():
            self.lbl_text_overlap.setText("⚠️ Chú ý: Các lớp chữ đang bị đè lên nhau!")
        else:
            self.lbl_text_overlap.setText("")

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
