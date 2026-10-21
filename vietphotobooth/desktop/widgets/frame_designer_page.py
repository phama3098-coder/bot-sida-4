"""
1998 TEAM — Frame Designer & Template Studio
Visual interactive layout editor for 2x6 and 4x6 print formats,
SVG/PNG/JPG multi-format import, interactive drag-and-drop slot positioning,
snap-to-grid, rotation, z-order layer management, safe zone checking,
and zip backup/restore.
"""

import os
import shutil
import copy
from typing import Optional, List, Tuple
from PIL import Image

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QLineEdit, QCheckBox, QScrollArea, QFileDialog, QMessageBox,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog,
    QSizePolicy, QColorDialog, QDialog, QFormLayout, QRadioButton, QButtonGroup,
    QTextEdit, QFrame
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QPoint, QRect
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
        self.lbl_preview.setStyleSheet("background-color: #070A12; border: 2px dashed #28395E; border-radius: 10px; color: #94A3B8;")
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
        filter_str = "Tất Cả Định Dạng Khung (*.png *.jpg *.jpeg *.svg);;Ảnh PNG Trong Suốt (*.png);;Ảnh JPG/JPEG (*.jpg *.jpeg);;Vector SVG (*.svg)"
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Tệp Khung Ảnh", "", filter_str)
        if not path or not os.path.exists(path):
            return

        self.selected_file_path = path
        self.txt_file.setText(path)

        # Gợi ý tên khung từ tên file
        base_name = os.path.splitext(os.path.basename(path))[0]
        cleaned_name = base_name.replace("_", " ").title()
        if not self.txt_name.text().strip():
            self.txt_name.setText(cleaned_name)

        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            self.rb_bg.setChecked(True)
        else:
            self.rb_overlay.setChecked(True)

        # Tạo ảnh xem trước
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
                    self.lbl_preview.setPixmap(pix.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    self.lbl_preview.setText(f"Tệp SVG: {os.path.basename(path)}")
            else:
                pix = QPixmap(path)
                self.lbl_preview.setPixmap(pix.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
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
            QMessageBox.information(self, "Thành Công", f"Đã nhập thành công mẫu khung: {imported.name}\nKhổ in: {imported.type} (300 DPI)")
            self.accept()
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể xử lý hoặc chuyển đổi tệp khung ảnh này. Vui lòng kiểm tra định dạng.")


class InteractiveCanvas(QWidget):
    """
    Vùng thiết kế khung ảnh trực quan có tương tác chuột:
    - Kéo thả các ô ảnh (Photo Slots) bằng chuột trực tiếp trên giao diện.
    - Vẽ lưới tọa độ Grid, đường căn tâm, vùng an toàn (Safe Zone) và mép xén (Bleed).
    - Làm nổi bật ô ảnh đang chọn với viền vàng Champagne Gold.
    """

    slot_selected = Signal(int)             # Bắn ra index ô ảnh khi click
    slot_moved = Signal(int, int, int)       # Bắn ra (slot_index, new_x, new_y) khi kéo thả
    slot_drag_finished = Signal(int)        # Bắn ra khi nhả chuột

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(420, 560)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.template: Optional[FrameTemplate] = None
        self.preview_pixmap: Optional[QPixmap] = None

        self.selected_slot_index: int = -1
        self.show_grid: bool = True
        self.snap_to_grid: bool = True
        self.show_guides: bool = True
        self.grid_size: int = 40  # 40px tại độ phân giải gốc 300 DPI

        # Trạng thái kéo chuột
        self._is_dragging: bool = False
        self._drag_start_pos: QPoint = QPoint()
        self._slot_start_x: int = 0
        self._slot_start_y: int = 0

    def set_template_preview(self, template: FrameTemplate, pixmap: QPixmap):
        self.template = template
        self.preview_pixmap = pixmap
        self.update()

    def _get_canvas_geometry(self) -> Tuple[float, float, float, float, float]:
        """Tính toán tỷ lệ thu phóng và vùng hiển thị canvas trên widget."""
        if not self.template:
            return 1.0, 0, 0, self.width(), self.height()

        cw, ch = self.template.canvas_size[0], self.template.canvas_size[1]
        avail_w = self.width() - 20
        avail_h = self.height() - 20

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
        cw, ch = self.template.canvas_size[0], self.template.canvas_size[1]

        # 2. Vẽ hình ảnh render preview khung
        render_rect = QRectF(ox, oy, rw, rh)
        painter.drawPixmap(render_rect.toRect(), self.preview_pixmap)

        # 3. Vẽ lưới tọa độ Grid (nếu bật)
        if self.show_grid and self.grid_size > 0:
            grid_pen = QPen(QColor(30, 45, 74, 110), 1, Qt.DotLine)
            painter.setPen(grid_pen)
            # Lưới dọc
            x_step = self.grid_size * scale
            curr_x = ox
            while curr_x < (ox + rw):
                painter.drawLine(curr_x, oy, curr_x, oy + rh)
                curr_x += x_step
            # Lưới ngang
            y_step = self.grid_size * scale
            curr_y = oy
            while curr_y < (oy + rh):
                painter.drawLine(ox, curr_y, ox + rw, curr_y)
                curr_y += y_step

        # 4. Vẽ vùng an toàn (Safe Zone) và Mép xén (Bleed Margin) (nếu bật)
        if self.show_guides:
            # Bleed Line (mép xén 15px - màu đỏ nhạt)
            bleed_scale = self.template.bleed_px * scale
            bleed_pen = QPen(QColor(239, 68, 68, 160), 1, Qt.DashLine)
            painter.setPen(bleed_pen)
            painter.drawRect(QRectF(ox + bleed_scale, oy + bleed_scale, rw - 2 * bleed_scale, rh - 2 * bleed_scale))

            # Safe Zone Line (vùng an toàn 40px - màu vàng champagne)
            safe_scale = self.template.safe_zone_px * scale
            safe_pen = QPen(QColor(212, 175, 55, 180), 1, Qt.DashLine)
            painter.setPen(safe_pen)
            painter.drawRect(QRectF(ox + safe_scale, oy + safe_scale, rw - 2 * safe_scale, rh - 2 * safe_scale))

            # Đường cắt giữa dải đôi (nếu có)
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

            is_selected = (idx == self.selected_slot_index)

            if is_selected:
                # Viền vàng Champagne Gold sáng bóng
                slot_pen = QPen(QColor("#D4AF37"), 3, Qt.SolidLine)
                painter.setPen(slot_pen)
                painter.setBrush(QColor(212, 175, 55, 30))
                painter.drawRect(slot_rect)

                # Vẽ 4 góc điều hướng kéo thả
                handle_size = 8
                painter.setBrush(QColor("#FFFFFF"))
                painter.setPen(QColor("#070A12"))
                painter.drawRect(QRectF(sx - handle_size / 2, sy - handle_size / 2, handle_size, handle_size))
                painter.drawRect(QRectF(sx + sw - handle_size / 2, sy - handle_size / 2, handle_size, handle_size))
                painter.drawRect(QRectF(sx - handle_size / 2, sy + sh - handle_size / 2, handle_size, handle_size))
                painter.drawRect(QRectF(sx + sw - handle_size / 2, sy + sh - handle_size / 2, handle_size, handle_size))

                # Huy hiệu thông số ô ảnh đang chọn
                badge_text = f"Ô #{slot.id} ({slot.w}x{slot.h}) [X:{slot.x}, Y:{slot.y}]"
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.setPen(QColor("#FFFFFF"))
                painter.setBrush(QColor(11, 19, 43, 220))
                painter.drawRoundedRect(QRectF(sx + 6, sy + 6, 210, 24), 4, 4)
                painter.drawText(QRectF(sx + 10, sy + 6, 200, 24), Qt.AlignVCenter | Qt.AlignLeft, badge_text)

            else:
                slot_pen = QPen(QColor(56, 189, 248, 140), 1.5, Qt.DashLine)
                painter.setPen(slot_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(slot_rect)

                # Số thứ tự ô
                painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
                painter.setPen(QColor("#38BDF8"))
                painter.drawText(QRectF(sx + 6, sy + 6, 80, 24), Qt.AlignLeft, f"#{slot.id}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.template:
            scale, ox, oy, rw, rh = self._get_canvas_geometry()
            mx = event.position().x()
            my = event.position().y()

            # Chuyển đổi tọa độ chuột sang tọa độ canvas gốc 300 DPI
            cx = (mx - ox) / scale
            cy = (my - oy) / scale

            # Tìm ô ảnh người dùng click vào (ưu tiên lớp trên cùng)
            clicked_idx = -1
            for idx in reversed(range(len(self.template.slots))):
                s = self.template.slots[idx]
                if s.x <= cx <= (s.x + s.w) and s.y <= cy <= (s.y + s.h):
                    clicked_idx = idx
                    break

            if clicked_idx != -1:
                self.selected_slot_index = clicked_idx
                self._is_dragging = True
                self._drag_start_pos = event.pos()
                self._slot_start_x = self.template.slots[clicked_idx].x
                self._slot_start_y = self.template.slots[clicked_idx].y
                self.slot_selected.emit(clicked_idx)
                self.update()
            else:
                self.selected_slot_index = -1
                self.update()

    def mouseMoveEvent(self, event):
        if self._is_dragging and self.selected_slot_index != -1 and self.template:
            scale, ox, oy, rw, rh = self._get_canvas_geometry()
            dx = (event.pos().x() - self._drag_start_pos.x()) / scale
            dy = (event.pos().y() - self._drag_start_pos.y()) / scale

            new_x = int(self._slot_start_x + dx)
            new_y = int(self._slot_start_y + dy)

            # Tự động hút lưới (Snap to Grid) nếu bật
            if self.snap_to_grid and self.grid_size > 0:
                snap_step = 20
                new_x = round(new_x / snap_step) * snap_step
                new_y = round(new_y / snap_step) * snap_step

            # Giới hạn trong kích thước canvas
            cw, ch = self.template.canvas_size[0], self.template.canvas_size[1]
            slot = self.template.slots[self.selected_slot_index]
            new_x = max(0, min(new_x, cw - slot.w))
            new_y = max(0, min(new_y, ch - slot.h))

            slot.x = new_x
            slot.y = new_y
            self.slot_moved.emit(self.selected_slot_index, new_x, new_y)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.slot_drag_finished.emit(self.selected_slot_index)


class FrameDesignerPage(QWidget):
    """Trang thiết kế khung in ảnh Photobooth trực quan phong cách 1998 TEAM."""

    frame_changed = Signal(str)

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

        # CANVAS TƯƠNG TÁC CHUỘT (DRAG & DROP SLOTS)
        self.canvas = InteractiveCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumSize(250, 250)
        self.canvas.slot_selected.connect(self._on_slot_selected_from_canvas)
        self.canvas.slot_moved.connect(self._on_slot_moved_from_canvas)
        self.canvas.slot_drag_finished.connect(lambda idx: self._update_preview(full_render=True))
        left_layout.addWidget(self.canvas, 1)

        # THANH ĐIỀU KHIỂN LƯỚI & ĐƯỜNG CĂN (CO GIÃN GỌN GÀNG)
        guides_bar = QHBoxLayout()
        guides_bar.setSpacing(8)

        self.chk_grid = QCheckBox("Lưới (Grid)")
        self.chk_grid.setChecked(True)
        self.chk_grid.toggled.connect(self._toggle_grid)
        guides_bar.addWidget(self.chk_grid)

        self.chk_snap = QCheckBox("Hút (Snap)")
        self.chk_snap.setChecked(True)
        self.chk_snap.toggled.connect(self._toggle_snap)
        guides_bar.addWidget(self.chk_snap)

        self.chk_guides = QCheckBox("Vùng Cắt (Bleed)")
        self.chk_guides.setChecked(True)
        self.chk_guides.toggled.connect(self._toggle_guides)
        guides_bar.addWidget(self.chk_guides)

        guides_bar.addStretch()

        self.lbl_warnings = QLabel("300 DPI")
        self.lbl_warnings.setStyleSheet("color: #10B981; font-weight: 500;")
        guides_bar.addWidget(self.lbl_warnings)

        left_layout.addLayout(guides_bar)
        main_layout.addLayout(left_layout, 6)

        # ==============================================================
        # CỘT PHẢI: BẢNG THÔNG SỐ VÀ CÁC LỚP THÀNH PHẦN (CUỘN ĐỘC LẬP)
        # ==============================================================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(280)
        scroll.setMaximumWidth(450)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        right_layout = QVBoxLayout(scroll_content)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(12)

        # 1. THUỘC TÍNH KHUNG IN
        grp_props = QGroupBox("1. Thuộc Tính Khung In")
        l_props = QVBoxLayout(grp_props)
        form_props = QFormLayout()

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

        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("Ghi chú...")
        form_props.addRow("Ghi Chú:", self.txt_notes)

        l_props.addLayout(form_props)
        right_layout.addWidget(grp_props)

        # 2. CÁC Ô CHỨA ẢNH (PHOTO SLOTS)
        grp_slots = QGroupBox("2. Vùng Chứa Ảnh (Photo Slots)")
        l_slots = QVBoxLayout(grp_slots)

        self.table_slots = QTableWidget(0, 7)
        self.table_slots.setHorizontalHeaderLabels(["ID", "X", "Y", "W", "H", "Xoay", "Bo Góc"])
        self.table_slots.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_slots.horizontalHeader().setMinimumSectionSize(20)
        self.table_slots.setMaximumHeight(150)
        self.table_slots.cellChanged.connect(self._on_slot_table_cell_changed)
        self.table_slots.itemSelectionChanged.connect(self._on_slot_table_selection_changed)
        l_slots.addWidget(self.table_slots)

        # Nút thao tác ô ảnh nhanh
        slot_tools = QHBoxLayout()
        btn_add_slot = QPushButton("+ Thêm Ô")
        btn_add_slot.setObjectName("btn_secondary")
        btn_add_slot.clicked.connect(self._add_slot)
        slot_tools.addWidget(btn_add_slot)

        btn_del_slot = QPushButton("- Xóa Ô")
        btn_del_slot.setObjectName("btn_danger")
        btn_del_slot.clicked.connect(self._delete_slot)
        slot_tools.addWidget(btn_del_slot)

        btn_rot_slot = QPushButton("🔄 Xoay 90°")
        btn_rot_slot.setObjectName("btn_secondary")
        btn_rot_slot.clicked.connect(self._rotate_slot)
        slot_tools.addWidget(btn_rot_slot)

        btn_center_h = QPushButton("↔️ Căn Giữa")
        btn_center_h.setObjectName("btn_secondary")
        btn_center_h.clicked.connect(self._center_slot_horizontally)
        slot_tools.addWidget(btn_center_h)

        l_slots.addLayout(slot_tools)
        right_layout.addWidget(grp_slots)

        # 3. VĂN BẢN NGHỆ THUẬT (TEXT LAYERS)
        grp_text = QGroupBox("3. Văn Bản Nghệ Thuật (Text Layers)")
        l_text = QVBoxLayout(grp_text)

        self.table_text = QTableWidget(0, 4)
        self.table_text.setHorizontalHeaderLabels(["Nội Dung", "Y (px)", "Cỡ Chữ", "Căn Lề"])
        self.table_text.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_text.horizontalHeader().setMinimumSectionSize(20)
        self.table_text.setMaximumHeight(130)
        self.table_text.cellChanged.connect(lambda r, c: self._update_preview(full_render=True))
        l_text.addWidget(self.table_text)

        txt_tools = QHBoxLayout()
        btn_add_txt = QPushButton("+ Thêm Chữ")
        btn_add_txt.setObjectName("btn_secondary")
        btn_add_txt.clicked.connect(self._add_text)
        txt_tools.addWidget(btn_add_txt)

        btn_del_txt = QPushButton("- Xóa Chữ")
        btn_del_txt.setObjectName("btn_danger")
        btn_del_txt.clicked.connect(self._delete_text)
        txt_tools.addWidget(btn_del_txt)

        l_text.addLayout(txt_tools)
        right_layout.addWidget(grp_text)

        # 4. LOGO & HỌA TIẾT TRANG TRÍ (LOGO LAYERS)
        grp_logo = QGroupBox("4. Logo & Họa Tiết (Logo Layers)")
        l_logo = QVBoxLayout(grp_logo)

        self.table_logo = QTableWidget(0, 4)
        self.table_logo.setHorizontalHeaderLabels(["Tệp", "X (px)", "Y (px)", "Kích Thước"])
        self.table_logo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_logo.horizontalHeader().setMinimumSectionSize(20)
        self.table_logo.setMaximumHeight(110)
        l_logo.addWidget(self.table_logo)

        logo_tools = QHBoxLayout()
        btn_add_logo = QPushButton("+ Chèn Logo...")
        btn_add_logo.setObjectName("btn_secondary")
        btn_add_logo.clicked.connect(self._add_logo)
        logo_tools.addWidget(btn_add_logo)

        btn_del_logo = QPushButton("- Xóa Logo")
        btn_del_logo.setObjectName("btn_danger")
        btn_del_logo.clicked.connect(self._delete_logo)
        logo_tools.addWidget(btn_del_logo)

        l_logo.addLayout(logo_tools)
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
        self.txt_name.setText(f.name)
        idx_cat = self.combo_cat.findText(f.category)
        if idx_cat >= 0:
            self.combo_cat.setCurrentIndex(idx_cat)

        idx_type = self.combo_type.findText(f.type)
        if idx_type >= 0:
            self.combo_type.setCurrentIndex(idx_type)

        self.chk_dual.setChecked(f.is_dual_strip)
        self.btn_bg_color.setText(f.bg_color or "#FFFFFF")
        self.txt_notes.setText(getattr(f, "notes", ""))

        # Nạp bảng Slots
        self.table_slots.blockSignals(True)
        self.table_slots.setRowCount(0)
        for s in f.slots:
            row = self.table_slots.rowCount()
            self.table_slots.insertRow(row)
            self.table_slots.setItem(row, 0, QTableWidgetItem(str(s.id)))
            self.table_slots.setItem(row, 1, QTableWidgetItem(str(s.x)))
            self.table_slots.setItem(row, 2, QTableWidgetItem(str(s.y)))
            self.table_slots.setItem(row, 3, QTableWidgetItem(str(s.w)))
            self.table_slots.setItem(row, 4, QTableWidgetItem(str(s.h)))
            self.table_slots.setItem(row, 5, QTableWidgetItem(f"{getattr(s, 'rotation', 0)}°"))
            self.table_slots.setItem(row, 6, QTableWidgetItem(str(getattr(s, 'corner_radius', 0))))
        self.table_slots.blockSignals(False)

        # Nạp bảng Text Layers
        self.table_text.blockSignals(True)
        self.table_text.setRowCount(0)
        for t in f.text_layers:
            row = self.table_text.rowCount()
            self.table_text.insertRow(row)
            self.table_text.setItem(row, 0, QTableWidgetItem(t.text))
            self.table_text.setItem(row, 1, QTableWidgetItem(str(t.y)))
            self.table_text.setItem(row, 2, QTableWidgetItem(str(t.font_size)))
            self.table_text.setItem(row, 3, QTableWidgetItem(t.alignment))
        self.table_text.blockSignals(False)

        # Nạp bảng Logo Layers
        self.table_logo.blockSignals(True)
        self.table_logo.setRowCount(0)
        for l in f.logo_layers:
            row = self.table_logo.rowCount()
            self.table_logo.insertRow(row)
            self.table_logo.setItem(row, 0, QTableWidgetItem(os.path.basename(l.image_path)))
            self.table_logo.setItem(row, 1, QTableWidgetItem(str(l.x)))
            self.table_logo.setItem(row, 2, QTableWidgetItem(str(l.y)))
            self.table_logo.setItem(row, 3, QTableWidgetItem(f"{l.w}x{l.h}"))
        self.table_logo.blockSignals(False)

        self._is_updating_ui = False
        self._update_preview(full_render=True)

    # ==============================================================
    # ĐỒNG BỘ VÀ TẠO XEM TRƯỚC (PREVIEW)
    # ==============================================================
    def _build_frame_from_ui(self) -> Optional[FrameTemplate]:
        if not self.current_frame:
            return None

        slots = []
        for r in range(self.table_slots.rowCount()):
            try:
                sid = int(self.table_slots.item(r, 0).text())
                x = int(self.table_slots.item(r, 1).text())
                y = int(self.table_slots.item(r, 2).text())
                w = int(self.table_slots.item(r, 3).text())
                h = int(self.table_slots.item(r, 4).text())
                rot_str = self.table_slots.item(r, 5).text().replace("°", "").strip()
                rot = int(rot_str) if rot_str else 0
                cr = int(self.table_slots.item(r, 6).text()) if self.table_slots.item(r, 6) else 0
                slots.append(PhotoSlot(id=sid, x=x, y=y, w=w, h=h, rotation=rot, corner_radius=cr, photo_index=r))
            except Exception:
                continue

        texts = []
        for r in range(self.table_text.rowCount()):
            try:
                txt = self.table_text.item(r, 0).text()
                y = int(self.table_text.item(r, 1).text())
                size = int(self.table_text.item(r, 2).text())
                align = self.table_text.item(r, 3).text()
                texts.append(TextLayer(id=f"txt_{r}", text=txt, x=self.current_frame.canvas_size[0] // 2, y=y, font_size=size, alignment=align))
            except Exception:
                continue

        f = self.current_frame
        f.name = self.txt_name.text().strip() or "Khung Mới"
        f.category = self.combo_cat.currentText()
        f.type = self.combo_type.currentText()
        f.is_dual_strip = self.chk_dual.isChecked()
        f.has_cut_line = self.chk_dual.isChecked()
        f.bg_color = self.btn_bg_color.text()
        f.notes = self.txt_notes.text().strip()
        f.slots = slots
        f.text_layers = texts
        return f

    def _update_preview(self, full_render: bool = True):
        f = self._build_frame_from_ui()
        if not f:
            return

        warnings = FrameDesigner.validate_template(f)
        if warnings:
            self.lbl_warnings.setText(f"⚠️ {warnings[0][:30]}...")
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

    # ==============================================================
    # SỰ KIỆN TƯƠNG TÁC TỪ CANVAS (DRAG & DROP)
    # ==============================================================
    def _on_slot_selected_from_canvas(self, slot_index: int):
        if 0 <= slot_index < self.table_slots.rowCount():
            self.table_slots.blockSignals(True)
            self.table_slots.selectRow(slot_index)
            self.table_slots.blockSignals(False)

    def _on_slot_moved_from_canvas(self, slot_index: int, new_x: int, new_y: int):
        if 0 <= slot_index < self.table_slots.rowCount():
            self.table_slots.blockSignals(True)
            self.table_slots.setItem(slot_index, 1, QTableWidgetItem(str(new_x)))
            self.table_slots.setItem(slot_index, 2, QTableWidgetItem(str(new_y)))
            self.table_slots.blockSignals(False)

    def _on_slot_table_selection_changed(self):
        row = self.table_slots.currentRow()
        if 0 <= row < len(self.current_frame.slots if self.current_frame else []):
            self.canvas.selected_slot_index = row
            self.canvas.update()

    def _on_slot_table_cell_changed(self, row: int, column: int):
        if not self._is_updating_ui:
            self._update_preview(full_render=True)

    # ==============================================================
    # CÁC THAO TÁC KHUNG (THÊM, NHÂN BẢN, ĐỔI TÊN, XÓA, SAO LƯU)
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

    def _save_frame(self):
        f = self._build_frame_from_ui()
        if not f:
            return
        if self.manager.save_frame(f):
            QMessageBox.information(self, "Thành Công", f"Đã lưu khung in '{f.name}' vào thư mục người dùng!")
            self.frame_changed.emit(f.id)

    def _backup_zip(self):
        path, _ = QFileDialog.getSaveFileName(self, "Sao Lưu Khung Ảnh Ra File ZIP", "1998_Frames_Backup.zip", "ZIP Archive (*.zip)")
        if path:
            if self.manager.backup_frames_to_zip(path):
                QMessageBox.information(self, "Thành Công", f"Đã sao lưu toàn bộ khung ảnh vào:\n{path}")
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể tạo file sao lưu ZIP.")

    def _restore_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Khôi Phục Khung Ảnh Từ File ZIP", "", "ZIP Archive (*.zip)")
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

    # ==============================================================
    # THAO TÁC CHI TIẾT TRÊN CÁC Ô ẢNH VÀ THÀNH PHẦN
    # ==============================================================
    def _add_slot(self):
        row = self.table_slots.rowCount()
        self.table_slots.insertRow(row)
        self.table_slots.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.table_slots.setItem(row, 1, QTableWidgetItem("50"))
        self.table_slots.setItem(row, 2, QTableWidgetItem(str(60 + row * 400)))
        self.table_slots.setItem(row, 3, QTableWidgetItem("500"))
        self.table_slots.setItem(row, 4, QTableWidgetItem("360"))
        self.table_slots.setItem(row, 5, QTableWidgetItem("0°"))
        self.table_slots.setItem(row, 6, QTableWidgetItem("10"))
        self._update_preview(full_render=True)

    def _delete_slot(self):
        row = self.table_slots.currentRow()
        if row >= 0:
            self.table_slots.removeRow(row)
            self._update_preview(full_render=True)

    def _rotate_slot(self):
        row = self.table_slots.currentRow()
        if row < 0:
            row = 0 if self.table_slots.rowCount() > 0 else -1
        if row >= 0:
            curr_item = self.table_slots.item(row, 5)
            curr_deg = int(curr_item.text().replace("°", "").strip()) if curr_item else 0
            new_deg = (curr_deg + 90) % 360
            self.table_slots.setItem(row, 5, QTableWidgetItem(f"{new_deg}°"))
            self._update_preview(full_render=True)

    def _center_slot_horizontally(self):
        row = self.table_slots.currentRow()
        if row >= 0 and self.current_frame:
            w_item = self.table_slots.item(row, 3)
            slot_w = int(w_item.text()) if w_item else 500
            canvas_w = self.current_frame.canvas_size[0]
            if self.current_frame.is_dual_strip:
                canvas_w = 600
            new_x = max(0, (canvas_w - slot_w) // 2)
            self.table_slots.setItem(row, 1, QTableWidgetItem(str(new_x)))
            self._update_preview(full_render=True)

    def _add_text(self):
        row = self.table_text.rowCount()
        self.table_text.insertRow(row)
        self.table_text.setItem(row, 0, QTableWidgetItem("1998 Studio • Phóng Sự Cưới"))
        self.table_text.setItem(row, 1, QTableWidgetItem(str(1400 + row * 60)))
        self.table_text.setItem(row, 2, QTableWidgetItem("34"))
        self.table_text.setItem(row, 3, QTableWidgetItem("center"))
        self._update_preview(full_render=True)

    def _delete_text(self):
        row = self.table_text.currentRow()
        if row >= 0:
            self.table_text.removeRow(row)
            self._update_preview(full_render=True)

    def _add_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn File Logo / Họa Tiết PNG", "", "PNG Image (*.png)")
        if path and os.path.exists(path):
            if not self.current_frame:
                return
            row = self.table_logo.rowCount()
            self.table_logo.insertRow(row)
            self.table_logo.setItem(row, 0, QTableWidgetItem(os.path.basename(path)))
            self.table_logo.setItem(row, 1, QTableWidgetItem("200"))
            self.table_logo.setItem(row, 2, QTableWidgetItem("1500"))
            self.table_logo.setItem(row, 3, QTableWidgetItem("200x80"))
            new_logo = LogoLayer(id=f"logo_{row}", image_path=path, x=200, y=1500, w=200, h=80)
            self.current_frame.logo_layers.append(new_logo)
            self._update_preview(full_render=True)

    def _delete_logo(self):
        row = self.table_logo.currentRow()
        if row >= 0 and self.current_frame and row < len(self.current_frame.logo_layers):
            self.current_frame.logo_layers.pop(row)
            self.table_logo.removeRow(row)
            self._update_preview(full_render=True)

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

    def _toggle_grid(self, checked: bool):
        self.canvas.show_grid = checked
        self.canvas.update()

    def _toggle_snap(self, checked: bool):
        self.canvas.snap_to_grid = checked

    def _toggle_guides(self, checked: bool):
        self.canvas.show_guides = checked
        self.canvas.update()
