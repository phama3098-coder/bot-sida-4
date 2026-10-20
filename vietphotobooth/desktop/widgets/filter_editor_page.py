"""
VietPhotoBooth Filter & LUT Editor Page
Visual parameter tuning studio for 14 image adjustments, .cube 3D LUTs, and preset management.
"""

import os
from typing import Optional
from PIL import Image
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QCheckBox, QComboBox, QScrollArea, QFileDialog, QMessageBox, QGroupBox,
    QInputDialog, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QImage

from vietphotobooth.filters.filter_engine import FilterEngine, FilterPreset
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class FilterEditorPage(QWidget):
    """Trang biên tập và thiết kế bộ lọc màu & LUT chuyên sâu."""

    preset_changed = Signal(str)  # Bắn tín hiệu khi preset được lưu/đổi

    def __init__(self, filter_engine: FilterEngine, parent=None):
        super().__init__(parent)
        self.engine = filter_engine
        self.current_preset: Optional[FilterPreset] = None
        self._sample_img: Optional[Image.Image] = None
        self._is_updating_ui = False

        self._init_sample_image()
        self._init_ui()
        self._load_presets_to_combo()

    def _init_sample_image(self):
        """Khởi tạo ảnh mẫu chân dung để thử nghiệm màu sắc."""
        # Tạo ảnh chân dung mẫu có da, màu tóc, nền sáng tối
        arr = np.zeros((600, 800, 3), dtype=np.uint8)
        # Nền gradient từ xanh lam sang cam ấm
        for y in range(600):
            r = int(180 + 50 * (y / 600))
            g = int(140 + 40 * (y / 600))
            b = int(120 + 80 * (y / 600))
            arr[y, :] = [r, g, b]

        # Khối da người ở giữa
        for y in range(150, 480):
            for x in range(250, 550):
                if ((x - 400)**2 / 120**2 + (y - 300)**2 / 150**2) <= 1.0:
                    arr[y, x] = [235, 185, 155] # Tông da người

        self._sample_img = Image.fromarray(arr, "RGB")

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # CỘT TRÁI: KHU VỰC XEM TRƯỚC ẢNH & THAO TÁC PRESET
        left_panel = QVBoxLayout()

        # Thanh công cụ Preset trên cùng
        preset_bar = QHBoxLayout()
        preset_bar.addWidget(QLabel("<b>Bộ Lọc:</b>"))
        self.combo_presets = QComboBox()
        self.combo_presets.setMinimumWidth(220)
        self.combo_presets.currentIndexChanged.connect(self._on_preset_selected)
        preset_bar.addWidget(self.combo_presets)

        btn_new = QPushButton("Tạo Mới")
        btn_new.setObjectName("btn_secondary")
        btn_new.clicked.connect(self._create_new_preset)
        preset_bar.addWidget(btn_new)

        btn_dup = QPushButton("Nhân Bản")
        btn_dup.setObjectName("btn_secondary")
        btn_dup.clicked.connect(self._duplicate_preset)
        preset_bar.addWidget(btn_dup)

        btn_delete = QPushButton("Xóa")
        btn_delete.setObjectName("btn_danger")
        btn_delete.clicked.connect(self._delete_preset)
        preset_bar.addWidget(btn_delete)

        left_panel.addLayout(preset_bar)

        # Khung hiển thị ảnh xem trước
        self.lbl_preview = QLabel("Đang tạo ảnh xem trước...")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #0B0F19; border: 2px dashed #334155; border-radius: 12px;")
        self.lbl_preview.setMinimumSize(480, 420)
        self.lbl_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_panel.addWidget(self.lbl_preview, 1)

        # Nút chọn ảnh ngoài thử nghiệm & Lưu preset
        action_bar = QHBoxLayout()
        btn_load_photo = QPushButton("Nạp Ảnh Khác Để Thử")
        btn_load_photo.setObjectName("btn_secondary")
        btn_load_photo.clicked.connect(self._load_custom_test_image)
        action_bar.addWidget(btn_load_photo)

        btn_import = QPushButton("Nhập JSON")
        btn_import.setObjectName("btn_secondary")
        btn_import.clicked.connect(self._import_preset_json)
        action_bar.addWidget(btn_import)

        btn_export = QPushButton("Xuất JSON")
        btn_export.setObjectName("btn_secondary")
        btn_export.clicked.connect(self._export_preset_json)
        action_bar.addWidget(btn_export)

        btn_reset = QPushButton("Đặt Lại")
        btn_reset.setObjectName("btn_secondary")
        btn_reset.clicked.connect(self._reset_current_preset)
        action_bar.addWidget(btn_reset)

        btn_save = QPushButton("Lưu Thay Đổi")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self._save_current_preset)
        action_bar.addWidget(btn_save)

        left_panel.addLayout(action_bar)
        main_layout.addLayout(left_panel, 6)

        # CỘT PHẢI: BẢNG 14 THANH TRƯỢT THAM SỐ CHỈNH ẢNH
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(360)
        scroll_content = QWidget()
        sliders_layout = QVBoxLayout(scroll_content)
        sliders_layout.setSpacing(12)

        # Nhóm 1: Ánh sáng & Độ tương phản
        grp_light = QGroupBox("1. Ánh Sáng & Tương Phản")
        l_light = QVBoxLayout(grp_light)
        self.s_exposure = self._create_slider(l_light, "Phơi sáng (Exposure):", -100, 100, 0)
        self.s_brightness = self._create_slider(l_light, "Độ sáng (Brightness):", -100, 100, 0)
        self.s_contrast = self._create_slider(l_light, "Độ tương phản (Contrast):", -100, 100, 0)
        self.s_highlights = self._create_slider(l_light, "Vùng sáng (Highlights):", -100, 100, 0)
        self.s_shadows = self._create_slider(l_light, "Vùng tối (Shadows):", -100, 100, 0)
        self.s_gamma = self._create_slider(l_light, "Gamma (x100):", 20, 300, 100)
        sliders_layout.addWidget(grp_light)

        # Nhóm 2: Màu sắc & Cân bằng trắng
        grp_color = QGroupBox("2. Màu Sắc & Cân Bằng Trắng")
        l_color = QVBoxLayout(grp_color)
        self.s_saturation = self._create_slider(l_color, "Độ bão hòa (Saturation):", -100, 100, 0)
        self.s_temperature = self._create_slider(l_color, "Nhiệt độ màu (Temp):", -100, 100, 0)
        self.s_tint = self._create_slider(l_color, "Sắc độ (Tint):", -100, 100, 0)
        self.chk_grayscale = QCheckBox("Chuyển sang ảnh Trắng Đen (Grayscale)")
        self.chk_grayscale.stateChanged.connect(self._on_slider_changed)
        l_color.addWidget(self.chk_grayscale)
        self.s_sepia = self._create_slider(l_color, "Tông Nâu Cổ Kính (Sepia):", 0, 100, 0)
        sliders_layout.addWidget(grp_color)

        # Nhóm 3: Hiệu ứng nghệ thuật & Làm mịn da
        grp_fx = QGroupBox("3. Nghệ Thuật & Chân Dung")
        l_fx = QVBoxLayout(grp_fx)
        self.s_soft_skin = self._create_slider(l_fx, "Làm mịn da (Soft Skin):", 0, 100, 0)
        self.s_sharpness = self._create_slider(l_fx, "Độ sắc nét (Sharpness):", 0, 100, 0)
        self.s_fade = self._create_slider(l_fx, "Mờ phim / Nâng đen (Fade):", 0, 100, 0)
        self.s_vignette = self._create_slider(l_fx, "Tối 4 góc (Vignette):", 0, 100, 0)
        sliders_layout.addWidget(grp_fx)

        # Nhóm 4: Bảng tra màu 3D LUT (.cube)
        grp_lut = QGroupBox("4. Bảng Tra Màu 3D LUT (.cube)")
        l_lut = QVBoxLayout(grp_lut)
        l_lut.addWidget(QLabel("Chọn file LUT:"))
        self.combo_luts = QComboBox()
        self.combo_luts.currentIndexChanged.connect(self._on_slider_changed)
        l_lut.addWidget(self.combo_luts)
        self.s_lut_intensity = self._create_slider(l_lut, "Cường độ LUT (%):", 0, 100, 100)
        btn_import_lut = QPushButton("Nhập File .cube Ngoài...")
        btn_import_lut.setObjectName("btn_secondary")
        btn_import_lut.clicked.connect(self._import_custom_cube_lut)
        l_lut.addWidget(btn_import_lut)
        sliders_layout.addWidget(grp_lut)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 4)

        self._refresh_lut_combo()

    def _create_slider(self, parent_layout, label_text: str, min_v: int, max_v: int, def_v: int):
        row = QHBoxLayout()
        lbl_name = QLabel(label_text)
        lbl_val = QLabel(str(def_v))
        lbl_val.setStyleSheet("color: #38BDF8; font-weight: bold; min-width: 38px;")
        lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(def_v)

        slider.valueChanged.connect(lambda v, l=lbl_val: l.setText(str(v)))
        slider.valueChanged.connect(self._on_slider_changed)

        row.addWidget(lbl_name)
        row.addWidget(lbl_val)
        parent_layout.addLayout(row)
        parent_layout.addWidget(slider)
        return slider

    def _refresh_lut_combo(self):
        self.combo_luts.clear()
        self.combo_luts.addItem("-- Không Dùng LUT --", None)
        for lut in self.engine.get_available_luts():
            self.combo_luts.addItem(lut, lut)

    def _load_presets_to_combo(self):
        self.combo_presets.blockSignals(True)
        self.combo_presets.clear()
        presets = self.engine.get_presets()
        for p in presets:
            prefix = "[Gốc] " if p.is_builtin else "[Tự Đặt] "
            self.combo_presets.addItem(f"{prefix}{p.name}", p.id)
        self.combo_presets.blockSignals(False)

        if self.combo_presets.count() > 0:
            self.combo_presets.setCurrentIndex(0)
            self._on_preset_selected(0)

    def _on_preset_selected(self, index: int):
        preset_id = self.combo_presets.currentData()
        if not preset_id:
            return
        preset = self.engine.get_preset(preset_id)
        if not preset:
            return
        self.current_preset = preset
        self._apply_preset_to_ui(preset)

    def _apply_preset_to_ui(self, p: FilterPreset):
        self._is_updating_ui = True
        self.s_exposure.setValue(int(p.exposure))
        self.s_brightness.setValue(int(p.brightness))
        self.s_contrast.setValue(int(p.contrast))
        self.s_highlights.setValue(int(p.highlights))
        self.s_shadows.setValue(int(p.shadows))
        self.s_gamma.setValue(int(p.gamma * 100))

        self.s_saturation.setValue(int(p.saturation))
        self.s_temperature.setValue(int(p.temperature))
        self.s_tint.setValue(int(p.tint))
        self.chk_grayscale.setChecked(p.grayscale)
        self.s_sepia.setValue(int(p.sepia))

        self.s_soft_skin.setValue(int(p.soft_skin))
        self.s_sharpness.setValue(int(p.sharpness))
        self.s_fade.setValue(int(p.fade))
        self.s_vignette.setValue(int(p.vignette))

        # LUT
        if p.lut_filename:
            idx = self.combo_luts.findData(p.lut_filename)
            self.combo_luts.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.combo_luts.setCurrentIndex(0)
        self.s_lut_intensity.setValue(int(p.lut_intensity * 100))

        self._is_updating_ui = False
        self._update_preview()

    def _on_slider_changed(self):
        if self._is_updating_ui:
            return
        self._update_preview()

    def _update_preview(self):
        """Cập nhật ảnh xem trước tức thì."""
        if not self._sample_img:
            return

        # Tạo preset tạm thời từ các giá trị slider
        temp_p = FilterPreset(
            id="temp",
            name="Temporary",
            exposure=float(self.s_exposure.value()),
            brightness=float(self.s_brightness.value()),
            contrast=float(self.s_contrast.value()),
            highlights=float(self.s_highlights.value()),
            shadows=float(self.s_shadows.value()),
            gamma=float(self.s_gamma.value() / 100.0),
            saturation=float(self.s_saturation.value()),
            temperature=float(self.s_temperature.value()),
            tint=float(self.s_tint.value()),
            grayscale=self.chk_grayscale.isChecked(),
            sepia=float(self.s_sepia.value()),
            soft_skin=float(self.s_soft_skin.value()),
            sharpness=float(self.s_sharpness.value()),
            fade=float(self.s_fade.value()),
            vignette=float(self.s_vignette.value()),
            lut_filename=self.combo_luts.currentData(),
            lut_intensity=float(self.s_lut_intensity.value() / 100.0)
        )

        res_pil = self.engine.apply_preset(self._sample_img, temp_p)
        # Chuyển đổi PIL sang QPixmap
        res_rgb = res_pil.convert("RGB")
        w, h = res_rgb.size
        data = res_rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.lbl_preview.setPixmap(pix.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _save_current_preset(self):
        if not self.current_preset:
            return
        p = self.current_preset
        if p.is_builtin:
            QMessageBox.warning(self, "Preset Hệ Thống", "Không thể ghi đè preset mặc định của hệ thống. Vui lòng bấm 'Nhân Bản' để tạo preset riêng của bạn!")
            return

        p.exposure = float(self.s_exposure.value())
        p.brightness = float(self.s_brightness.value())
        p.contrast = float(self.s_contrast.value())
        p.highlights = float(self.s_highlights.value())
        p.shadows = float(self.s_shadows.value())
        p.gamma = float(self.s_gamma.value() / 100.0)
        p.saturation = float(self.s_saturation.value())
        p.temperature = float(self.s_temperature.value())
        p.tint = float(self.s_tint.value())
        p.grayscale = self.chk_grayscale.isChecked()
        p.sepia = float(self.s_sepia.value())
        p.soft_skin = float(self.s_soft_skin.value())
        p.sharpness = float(self.s_sharpness.value())
        p.fade = float(self.s_fade.value())
        p.vignette = float(self.s_vignette.value())
        p.lut_filename = self.combo_luts.currentData()
        p.lut_intensity = float(self.s_lut_intensity.value() / 100.0)

        if self.engine.save_custom_preset(p):
            QMessageBox.information(self, "Thành Công", f"Đã lưu thành công preset '{p.name}'!")
            self.preset_changed.emit(p.id)

    def _create_new_preset(self):
        name, ok = QInputDialog.getText(self, "Tạo Preset Mới", "Nhập tên bộ lọc màu mới:")
        if ok and name.strip():
            safe_id = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
            p = FilterPreset(id=safe_id, name=name.strip(), is_builtin=False)
            self.engine.save_custom_preset(p)
            self._load_presets_to_combo()
            idx = self.combo_presets.findData(p.id)
            if idx >= 0:
                self.combo_presets.setCurrentIndex(idx)

    def _duplicate_preset(self):
        if not self.current_preset:
            return
        name, ok = QInputDialog.getText(self, "Nhân Bản Preset", "Nhập tên cho bản sao preset:", text=f"{self.current_preset.name} (Bản Sao)")
        if ok and name.strip():
            safe_id = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
            dup = self.engine.duplicate_preset(self.current_preset.id, safe_id, name.strip())
            if dup:
                self._load_presets_to_combo()
                idx = self.combo_presets.findData(dup.id)
                if idx >= 0:
                    self.combo_presets.setCurrentIndex(idx)

    def _delete_preset(self):
        if not self.current_preset:
            return
        if self.current_preset.is_builtin:
            QMessageBox.warning(self, "Không Thể Xóa", "Preset mặc định của hệ thống không thể bị xóa.")
            return

        confirm = QMessageBox.question(self, "Xác Nhận Xóa", f"Bạn có chắc muốn xóa vĩnh viễn preset '{self.current_preset.name}'?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.engine.delete_preset(self.current_preset.id)
            self._load_presets_to_combo()

    def _reset_current_preset(self):
        if self.current_preset:
            self._apply_preset_to_ui(self.current_preset)

    def _load_custom_test_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Ảnh Để Thử Màu", "", "Ảnh (*.jpg *.jpeg *.png *.bmp)")
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert("RGB")
                img.thumbnail((1200, 900), Image.Resampling.LANCZOS)
                self._sample_img = img
                self._update_preview()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể tải ảnh: {e}")

    def _import_preset_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Nhập Preset JSON", "", "JSON Files (*.json)")
        if path:
            imported = self.engine.import_preset_from_file(path)
            if imported:
                QMessageBox.information(self, "Thành Công", f"Đã nhập thành công bộ lọc: {imported.name}")
                self._load_presets_to_combo()
                idx = self.combo_presets.findData(imported.id)
                if idx >= 0:
                    self.combo_presets.setCurrentIndex(idx)
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể đọc định dạng file preset này.")

    def _export_preset_json(self):
        if not self.current_preset:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất Preset JSON", f"{self.current_preset.id}.json", "JSON Files (*.json)")
        if path:
            if self.engine.export_preset_to_file(self.current_preset.id, path):
                QMessageBox.information(self, "Thành Công", f"Đã xuất preset vào:\n{path}")
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể xuất file preset.")

    def _import_custom_cube_lut(self):
        path, _ = QFileDialog.getOpenFileName(self, "Nhập File .cube 3D LUT", "", "3D LUT (*.cube)")
        if path and os.path.exists(path):
            import shutil
            dest = os.path.join(self.engine.luts_dir, os.path.basename(path))
            try:
                shutil.copy2(path, dest)
                self._refresh_lut_combo()
                idx = self.combo_luts.findData(os.path.basename(path))
                if idx >= 0:
                    self.combo_luts.setCurrentIndex(idx)
                QMessageBox.information(self, "Thành Công", f"Đã nạp file LUT: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi sao chép LUT: {e}")
