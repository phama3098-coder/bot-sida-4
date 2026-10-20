"""
VietPhotoBooth Frame Designer & Template Studio Page
Visual layout editor for 2x6 and 4x6 print formats, PNG overlay import, slot editing, and safe zone checking.
"""

import os
from typing import Optional, List
from PIL import Image

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QLineEdit, QCheckBox, QScrollArea, QFileDialog, QMessageBox,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog,
    QSizePolicy, QColorDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage, QColor

from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, DPI_300_SIZES
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class FrameDesignerPage(QWidget):
    """Trang thiết kế khung in ảnh Photobooth trực quan."""

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
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # CỘT TRÁI: BẢNG XEM TRƯỚC KHUNG IN & HƯỚNG DẪN VIỀN CẮT
        left_layout = QVBoxLayout()

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>Khung In:</b>"))
        self.combo_frames = QComboBox()
        self.combo_frames.setMinimumWidth(240)
        self.combo_frames.currentIndexChanged.connect(self._on_frame_selected)
        top_bar.addWidget(self.combo_frames)

        btn_import_png = QPushButton("Nhập Khung PNG Ngoài")
        btn_import_png.setObjectName("btn_secondary")
        btn_import_png.clicked.connect(self._import_external_png)
        top_bar.addWidget(btn_import_png)

        btn_new = QPushButton("Tạo Mới")
        btn_new.setObjectName("btn_secondary")
        btn_new.clicked.connect(self._create_new_frame)
        top_bar.addWidget(btn_new)

        btn_delete = QPushButton("Xóa")
        btn_delete.setObjectName("btn_danger")
        btn_delete.clicked.connect(self._delete_frame)
        top_bar.addWidget(btn_delete)

        left_layout.addLayout(top_bar)

        # Preview Canvas
        self.lbl_canvas = QLabel("Đang tạo bản vẽ khung...")
        self.lbl_canvas.setAlignment(Qt.AlignCenter)
        self.lbl_canvas.setStyleSheet("background-color: #0B0F19; border: 2px dashed #334155; border-radius: 12px;")
        self.lbl_canvas.setMinimumSize(420, 500)
        self.lbl_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.lbl_canvas, 1)

        # Bảng cảnh báo vùng an toàn / xén mép
        self.lbl_warnings = QLabel("Trạng thái bố cục: Hợp lệ")
        self.lbl_warnings.setStyleSheet("color: #10B981; font-weight: 500;")
        left_layout.addWidget(self.lbl_warnings)

        # Thanh nút hành động
        bottom_bar = QHBoxLayout()
        btn_refresh = QPushButton("Làm Mới Bản Vẽ")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._update_preview)
        bottom_bar.addWidget(btn_refresh)

        btn_save = QPushButton("Lưu Khung Ảnh")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self._save_frame)
        bottom_bar.addWidget(btn_save)

        left_layout.addLayout(bottom_bar)
        main_layout.addLayout(left_layout, 5)

        # CỘT PHẢI: BẢNG THIẾT KẾ THÔNG SỐ VÀ CÁC Ô CHỨA ẢNH
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(380)
        scroll_content = QWidget()
        right_layout = QVBoxLayout(scroll_content)
        right_layout.setSpacing(12)

        # 1. Thuộc tính chung
        grp_props = QGroupBox("1. Thuộc Tính Khung In")
        l_props = QVBoxLayout(grp_props)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Tên Khung:"))
        self.txt_name = QLineEdit()
        r1.addWidget(self.txt_name)
        l_props.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Phân Loại:"))
        self.combo_cat = QComboBox()
        self.combo_cat.addItems(["Wedding", "Birthday", "Corporate", "Custom"])
        r2.addWidget(self.combo_cat)

        r2.addWidget(QLabel("Khổ In:"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["2x6", "4x6_portrait", "4x6_landscape", "4x6_dual"])
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        r2.addWidget(self.combo_type)
        l_props.addLayout(r2)

        r3 = QHBoxLayout()
        self.chk_dual = QCheckBox("Nhân đôi dải (Cắt máy DNP)")
        r3.addWidget(self.chk_dual)
        self.chk_cut_line = QCheckBox("Đường cắt nét đứt")
        r3.addWidget(self.chk_cut_line)
        l_props.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Màu Nền:"))
        self.btn_bg_color = QPushButton("#FFFFFF")
        self.btn_bg_color.setObjectName("btn_secondary")
        self.btn_bg_color.clicked.connect(self._choose_bg_color)
        r4.addWidget(self.btn_bg_color)
        l_props.addLayout(r4)

        right_layout.addWidget(grp_props)

        # 2. Danh sách các ô ảnh (Photo Slots)
        grp_slots = QGroupBox("2. Các Ô Chứa Ảnh (Slots)")
        l_slots = QVBoxLayout(grp_slots)

        self.table_slots = QTableWidget(0, 5)
        self.table_slots.setHorizontalHeaderLabels(["ID", "X (px)", "Y (px)", "W (px)", "H (px)"])
        self.table_slots.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_slots.setMaximumHeight(160)
        l_slots.addWidget(self.table_slots)

        btn_slot_bar = QHBoxLayout()
        btn_add_slot = QPushButton("+ Thêm Ô Ảnh")
        btn_add_slot.setObjectName("btn_secondary")
        btn_add_slot.clicked.connect(self._add_slot)
        btn_slot_bar.addWidget(btn_add_slot)

        btn_del_slot = QPushButton("- Xóa Ô Đang Chọn")
        btn_del_slot.setObjectName("btn_danger")
        btn_del_slot.clicked.connect(self._delete_slot)
        btn_slot_bar.addWidget(btn_del_slot)
        l_slots.addLayout(btn_slot_bar)

        right_layout.addWidget(grp_slots)

        # 3. Lớp văn bản (Text Layers)
        grp_text = QGroupBox("3. Văn Bản Nghệ Thuật (Text Layers)")
        l_text = QVBoxLayout(grp_text)

        self.table_text = QTableWidget(0, 4)
        self.table_text.setHorizontalHeaderLabels(["Nội Dung", "Y (px)", "Cỡ Chữ", "Căn Lề"])
        self.table_text.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_text.setMaximumHeight(160)
        l_text.addWidget(self.table_text)

        btn_txt_bar = QHBoxLayout()
        btn_add_txt = QPushButton("+ Thêm Dòng Chữ")
        btn_add_txt.setObjectName("btn_secondary")
        btn_add_txt.clicked.connect(self._add_text)
        btn_txt_bar.addWidget(btn_add_txt)

        btn_del_txt = QPushButton("- Xóa Dòng Chữ")
        btn_del_txt.setObjectName("btn_danger")
        btn_del_txt.clicked.connect(self._delete_text)
        btn_txt_bar.addWidget(btn_del_txt)
        l_text.addLayout(btn_txt_bar)

        right_layout.addWidget(grp_text)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 5)

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
        self.chk_cut_line.setChecked(f.has_cut_line)
        self.btn_bg_color.setText(f.bg_color or "#FFFFFF")

        # Nạp bảng Slots
        self.table_slots.setRowCount(0)
        for s in f.slots:
            row = self.table_slots.rowCount()
            self.table_slots.insertRow(row)
            self.table_slots.setItem(row, 0, QTableWidgetItem(str(s.id)))
            self.table_slots.setItem(row, 1, QTableWidgetItem(str(s.x)))
            self.table_slots.setItem(row, 2, QTableWidgetItem(str(s.y)))
            self.table_slots.setItem(row, 3, QTableWidgetItem(str(s.w)))
            self.table_slots.setItem(row, 4, QTableWidgetItem(str(s.h)))

        # Nạp bảng Text Layers
        self.table_text.setRowCount(0)
        for t in f.text_layers:
            row = self.table_text.rowCount()
            self.table_text.insertRow(row)
            self.table_text.setItem(row, 0, QTableWidgetItem(t.text))
            self.table_text.setItem(row, 1, QTableWidgetItem(str(t.y)))
            self.table_text.setItem(row, 2, QTableWidgetItem(str(t.font_size)))
            self.table_text.setItem(row, 3, QTableWidgetItem(t.alignment))

        self._is_updating_ui = False
        self._update_preview()

    def _on_type_changed(self, index: int):
        if self._is_updating_ui or not self.current_frame:
            return
        t = self.combo_type.currentText()
        if t in DPI_300_SIZES:
            self.current_frame.type = t
            self.current_frame.canvas_size = list(DPI_300_SIZES[t])
            if t == "4x6_dual":
                self.chk_dual.setChecked(True)
                self.chk_cut_line.setChecked(True)
            self._update_preview()

    def _choose_bg_color(self):
        col = QColorDialog.getColor(QColor(self.btn_bg_color.text()), self, "Chọn Màu Nền Khung In")
        if col.isValid():
            hex_col = col.name().upper()
            self.btn_bg_color.setText(hex_col)
            self._update_preview()

    def _add_slot(self):
        row = self.table_slots.rowCount()
        self.table_slots.insertRow(row)
        self.table_slots.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.table_slots.setItem(row, 1, QTableWidgetItem("50"))
        self.table_slots.setItem(row, 2, QTableWidgetItem(str(60 + row * 400)))
        self.table_slots.setItem(row, 3, QTableWidgetItem("500"))
        self.table_slots.setItem(row, 4, QTableWidgetItem("350"))
        self._update_preview()

    def _delete_slot(self):
        row = self.table_slots.currentRow()
        if row >= 0:
            self.table_slots.removeRow(row)
            self._update_preview()

    def _add_text(self):
        row = self.table_text.rowCount()
        self.table_text.insertRow(row)
        self.table_text.setItem(row, 0, QTableWidgetItem("Dòng chữ mới"))
        self.table_text.setItem(row, 1, QTableWidgetItem(str(1400 + row * 60)))
        self.table_text.setItem(row, 2, QTableWidgetItem("32"))
        self.table_text.setItem(row, 3, QTableWidgetItem("center"))
        self._update_preview()

    def _delete_text(self):
        row = self.table_text.currentRow()
        if row >= 0:
            self.table_text.removeRow(row)
            self._update_preview()

    def _build_frame_from_ui(self) -> Optional[FrameTemplate]:
        if not self.current_frame:
            return None

        # Đọc slots từ table
        slots = []
        for r in range(self.table_slots.rowCount()):
            try:
                sid = int(self.table_slots.item(r, 0).text())
                x = int(self.table_slots.item(r, 1).text())
                y = int(self.table_slots.item(r, 2).text())
                w = int(self.table_slots.item(r, 3).text())
                h = int(self.table_slots.item(r, 4).text())
                slots.append(PhotoSlot(id=sid, x=x, y=y, w=w, h=h, corner_radius=10, photo_index=r))
            except Exception:
                continue

        # Đọc text layers từ table
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
        f.has_cut_line = self.chk_cut_line.isChecked()
        f.bg_color = self.btn_bg_color.text()
        f.slots = slots
        f.text_layers = texts
        return f

    def _update_preview(self):
        f = self._build_frame_from_ui()
        if not f:
            return

        # Kiểm tra cảnh báo mép cắt / an toàn
        warnings = FrameDesigner.validate_template(f)
        if warnings:
            self.lbl_warnings.setText(f"Cảnh báo: {warnings[0]}")
            self.lbl_warnings.setStyleSheet("color: #F59E0B; font-weight: bold;")
        else:
            self.lbl_warnings.setText("Trạng thái bố cục: Chuẩn xác 300 DPI, an toàn vùng cắt.")
            self.lbl_warnings.setStyleSheet("color: #10B981; font-weight: 500;")

        # Tạo preview
        prev_img = FrameDesigner.render_preview(f, max_height=650)
        rgb_img = prev_img.convert("RGB")
        w, h = rgb_img.size
        data = rgb_img.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.lbl_canvas.setPixmap(pix.scaled(self.lbl_canvas.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _save_frame(self):
        f = self._build_frame_from_ui()
        if not f:
            return
        if self.manager.save_frame(f):
            QMessageBox.information(self, "Thành Công", f"Đã lưu khung in '{f.name}'!")
            self.frame_changed.emit(f.id)

    def _create_new_frame(self):
        name, ok = QInputDialog.getText(self, "Tạo Khung Mới", "Nhập tên mẫu khung in ảnh:")
        if ok and name.strip():
            safe_id = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
            f = FrameTemplate(
                id=safe_id,
                name=name.strip(),
                category="Custom",
                type="2x6",
                canvas_size=[600, 1800],
                slots=[
                    PhotoSlot(id=1, x=50, y=60, w=500, h=380, corner_radius=10, photo_index=0),
                    PhotoSlot(id=2, x=50, y=480, w=500, h=380, corner_radius=10, photo_index=1),
                    PhotoSlot(id=3, x=50, y=900, w=500, h=380, corner_radius=10, photo_index=2),
                ],
                text_layers=[
                    TextLayer(id="title", text=name.strip(), x=300, y=1400, font_size=36, alignment="center"),
                    TextLayer(id="date", text="{date}", x=300, y=1480, font_size=24, alignment="center")
                ]
            )
            self.manager.save_frame(f)
            self._load_frames_to_combo()
            idx = self.combo_frames.findData(f.id)
            if idx >= 0:
                self.combo_frames.setCurrentIndex(idx)

    def _delete_frame(self):
        if not self.current_frame:
            return
        confirm = QMessageBox.question(self, "Xác Nhận Xóa", f"Bạn có chắc muốn xóa khung '{self.current_frame.name}'?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.manager.delete_frame(self.current_frame.id)
            self._load_frames_to_combo()

    def _import_external_png(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn File Khung PNG Ngoài (Có Kênh Suốt Alpha)", "", "PNG Overlay (*.png)")
        if path and os.path.exists(path):
            name, ok = QInputDialog.getText(self, "Đặt Tên Khung", "Nhập tên cho mẫu khung vừa nhập:", text=os.path.splitext(os.path.basename(path))[0])
            if ok and name.strip():
                imported = self.manager.import_external_png_overlay(path, name.strip(), category="Custom", strip_type="2x6")
                if imported:
                    QMessageBox.information(self, "Thành Công", f"Đã nhập thành công khung ngoài: {imported.name}")
                    self._load_frames_to_combo()
                    idx = self.combo_frames.findData(imported.id)
                    if idx >= 0:
                        self.combo_frames.setCurrentIndex(idx)
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể xử lý file PNG này.")
