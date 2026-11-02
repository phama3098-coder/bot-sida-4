"""
1998 TEAM — Photobooth Printing Page
Matches exact design of Panel 2:
- Dual printer configuration: Máy in strip (2x6) & Máy in full (4x6).
- Real printer detection and status indicator directly from Windows Spooler.
- Visual print margin & orientation alignment preview.
- Interactive steppers for Offset X/Y, Zoom with reset button.
- Real paper sheet counter with progress bar, quick refill buttons (+100, +400, +700), and warning threshold.
- Test print execution and persistent settings.
"""

import os
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QProgressBar, QSpinBox, QDoubleSpinBox, QFrame, QScrollArea,
    QMessageBox, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QFont

from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.printing.spooler import WindowsPrintSpooler
from vietphotobooth.desktop.icons import get_svg_icon, get_svg_pixmap, COLOR_GOLD, COLOR_WHITE, COLOR_SLATE, COLOR_BLUE, COLOR_GREEN, COLOR_RED
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class PrintMarginPreviewWidget(QFrame):
    """Bản vẽ trực quan mô phỏng khổ giấy in, căn chỉnh lề (offset X/Y) và thu phóng (zoom)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 210)
        self.setStyleSheet("background-color: #E7DFD2; border: 1.5px solid #BEB3A3; border-radius: 8px;")
        self.offset_x = 0
        self.offset_y = 0
        self.zoom = 1.0
        self.orientation = "portrait"

    def update_params(self, offset_x: int, offset_y: int, zoom: float, orientation: str):
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.zoom = zoom
        self.orientation = orientation
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Khổ giấy in nền
        paper_x, paper_y = 12, 12
        paper_w, paper_h = w - 24, h - 24

        painter.setPen(QPen(QColor("#BEB3A3"), 1.5))
        painter.setBrush(QBrush(QColor("#F5EFEB")))
        painter.drawRoundedRect(paper_x, paper_y, paper_w, paper_h, 6, 6)

        # Mô phỏng nội dung dải ảnh với offset và zoom
        base_content_w = paper_w - 20
        base_content_h = paper_h - 20

        scaled_w = max(10, int(base_content_w * self.zoom))
        scaled_h = max(10, int(base_content_h * self.zoom))

        # Dịch pixel theo tỷ lệ preview
        shift_x = int(self.offset_x * 0.25)
        shift_y = int(self.offset_y * 0.25)

        cx = paper_x + (paper_w - scaled_w) // 2 + shift_x
        cy = paper_y + (paper_h - scaled_h) // 2 + shift_y

        # Viền nội dung ảnh in (màu vàng champagne)
        painter.setPen(QPen(QColor("#B89555"), 1.5, Qt.DashLine))
        painter.setBrush(QBrush(QColor(184, 149, 85, 35)))
        painter.drawRoundedRect(cx, cy, scaled_w, scaled_h, 4, 4)

        # 3 ô ảnh thumbnail minh họa
        slot_h = max(4, (scaled_h - 16) // 3)
        slot_w = max(4, scaled_w - 8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(184, 149, 85, 80)))

        for i in range(3):
            sy = cy + 4 + i * (slot_h + 4)
            if sy + slot_h <= cy + scaled_h:
                painter.drawRoundedRect(cx + 4, sy, slot_w, slot_h, 2, 2)

        painter.end()


class PrintingPage(QWidget):
    """Trang Cài Đặt Máy In chuẩn 1998 TEAM Photobooth."""

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(720, 420)

    def __init__(self, print_mgr: PrintManager, auth_mgr=None, parent=None):
        super().__init__(parent)
        self.print_mgr = print_mgr
        self.auth_mgr = auth_mgr

        self._init_ui()
        self._load_printers()
        self._load_current_settings()

        # Timer quét trạng thái máy in mỗi 3 giây
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_printer_statuses)
        self.status_timer.start(3000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        # 1. HEADER CÀI ĐẶT MÁY IN
        h_head = QHBoxLayout()
        h_head.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap("printer", 28, COLOR_GOLD))
        h_head.addWidget(icon_lbl)

        v_head = QVBoxLayout()
        lbl_title = QLabel("CÀI ĐẶT MÁY IN")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 900; color: #34312E; letter-spacing: 0.5px;")
        lbl_sub = QLabel("Chọn máy in và chỉnh thông số in phù hợp với khổ ảnh.")
        lbl_sub.setStyleSheet("font-size: 13px; color: #777067;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_sub)
        h_head.addLayout(v_head)

        h_head.addStretch()

        self.btn_refresh = QPushButton("Tải lại danh sách máy in")
        self.btn_refresh.setIcon(get_svg_icon("refresh", 16, COLOR_GOLD))
        self.btn_refresh.setObjectName("btn_secondary")
        self.btn_refresh.setFixedHeight(36)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #E7DFD2; border: 1.5px solid #BEB3A3; color: #34312E; "
            "border-radius: 8px; padding: 0 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #C9BDAA; border-color: #B89555; }"
        )
        self.btn_refresh.clicked.connect(self._load_printers)
        h_head.addWidget(self.btn_refresh)

        layout.addLayout(h_head)

        # 2. KHU VỰC PHÂN BIỆT 2 MÁY IN: MÁY IN STRIP & MÁY IN FULL
        h_printers = QHBoxLayout()
        h_printers.setSpacing(16)

        # Card Máy in Strip (2x6)
        card_strip = QFrame()
        card_strip.setStyleSheet("background-color: #E7DFD2; border: 1.5px solid #BEB3A3; border-radius: 12px; padding: 10px;")
        l_strip = QVBoxLayout(card_strip)
        l_strip.setSpacing(10)

        h_strip_title = QHBoxLayout()
        icon_strip = QLabel()
        icon_strip.setPixmap(get_svg_pixmap("paper", 22, COLOR_BLUE))
        h_strip_title.addWidget(icon_strip)
        v_st = QVBoxLayout()
        lbl_st_name = QLabel("<b>Máy in strip</b>")
        lbl_st_name.setStyleSheet("font-size: 15px; color: #34312E;")
        lbl_st_sub = QLabel("Dùng cho ảnh strip dọc, ví dụ 2x6.")
        lbl_st_sub.setStyleSheet("font-size: 12px; color: #777067;")
        v_st.addWidget(lbl_st_name)
        v_st.addWidget(lbl_st_sub)
        h_strip_title.addLayout(v_st)
        h_strip_title.addStretch()
        l_strip.addLayout(h_strip_title)

        r_strip_select = QHBoxLayout()
        self.combo_strip = QComboBox()
        self.combo_strip.setFixedHeight(38)
        self.combo_strip.setStyleSheet(
            "QComboBox { background-color: #E7DFD2; color: #34312E; border: 1.5px solid #BEB3A3; "
            "border-radius: 8px; padding: 4px 10px; font-size: 13px; font-weight: bold; }"
            "QComboBox:hover { border: 1.5px solid #B89555; }"
        )
        self.combo_strip.currentIndexChanged.connect(self._check_printer_statuses)
        r_strip_select.addWidget(self.combo_strip, 1)

        self.lbl_strip_status = QLabel("Sẵn sàng")
        self.lbl_strip_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px; padding-left: 6px;")
        r_strip_select.addWidget(self.lbl_strip_status)
        l_strip.addLayout(r_strip_select)

        h_printers.addWidget(card_strip, 1)

        # Card Máy in Full (4x6)
        card_full = QFrame()
        card_full.setStyleSheet("background-color: #E7DFD2; border: 1.5px solid #BEB3A3; border-radius: 12px; padding: 10px;")
        l_full = QVBoxLayout(card_full)
        l_full.setSpacing(10)

        h_full_title = QHBoxLayout()
        icon_full = QLabel()
        icon_full.setPixmap(get_svg_pixmap("frame", 22, "#A855F7"))
        h_full_title.addWidget(icon_full)
        v_ft = QVBoxLayout()
        lbl_ft_name = QLabel("<b>Máy in full</b>")
        lbl_ft_name.setStyleSheet("font-size: 15px; color: #34312E;")
        lbl_ft_sub = QLabel("Dùng cho ảnh lớn ngang hoặc vuông, ví dụ 4x6.")
        lbl_ft_sub.setStyleSheet("font-size: 12px; color: #777067;")
        v_ft.addWidget(lbl_ft_name)
        v_ft.addWidget(lbl_ft_sub)
        h_full_title.addLayout(v_ft)
        h_full_title.addStretch()
        l_full.addLayout(h_full_title)

        r_full_select = QHBoxLayout()
        self.combo_full = QComboBox()
        self.combo_full.setFixedHeight(38)
        self.combo_full.setStyleSheet(
            "QComboBox { background-color: #E7DFD2; color: #34312E; border: 1.5px solid #BEB3A3; "
            "border-radius: 8px; padding: 4px 10px; font-size: 13px; font-weight: bold; }"
            "QComboBox:hover { border: 1.5px solid #B89555; }"
        )
        self.combo_full.currentIndexChanged.connect(self._check_printer_statuses)
        r_full_select.addWidget(self.combo_full, 1)

        self.lbl_full_status = QLabel("Sẵn sàng")
        self.lbl_full_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px; padding-left: 6px;")
        r_full_select.addWidget(self.lbl_full_status)
        l_full.addLayout(r_full_select)

        h_printers.addWidget(card_full, 1)

        layout.addLayout(h_printers)

        # 3. KHU VỰC CĂN CHỈNH LỀ & HƯỚNG IN
        grp_align = QFrame()
        grp_align.setStyleSheet("background-color: #E7DFD2; border: 1.5px solid #BEB3A3; border-radius: 12px; padding: 12px;")
        l_align = QVBoxLayout(grp_align)
        l_align.setSpacing(12)

        lbl_al_title = QLabel("<b>Căn chỉnh lề & hướng in</b>")
        lbl_al_title.setStyleSheet("font-size: 15px; color: #34312E;")
        l_align.addWidget(lbl_al_title)

        h_align_body = QHBoxLayout()
        h_align_body.setSpacing(18)

        # Preview diagram bên trái
        self.preview_widget = PrintMarginPreviewWidget()
        h_align_body.addWidget(self.preview_widget)

        # Điều khiển bên phải
        v_controls = QVBoxLayout()
        v_controls.setSpacing(12)

        # Hàng điều khiển: Hướng giấy, Lệch X, Lệch Y, Zoom, Nút Đặt lại 1.0
        r_ctrl = QHBoxLayout()
        r_ctrl.setSpacing(12)

        # Hướng giấy
        v_orient = QVBoxLayout()
        v_orient.addWidget(QLabel("Hướng giấy"))
        self.combo_orient = QComboBox()
        self.combo_orient.setFixedHeight(36)
        self.combo_orient.addItems(["Dọc (Portrait)", "Ngang (Landscape)"])
        self.combo_orient.setStyleSheet(
            "QComboBox { background-color: #E7DFD2; color: #34312E; border: 1.5px solid #BEB3A3; "
            "border-radius: 8px; padding: 4px 10px; font-size: 13px; }"
        )
        self.combo_orient.currentIndexChanged.connect(self._on_margin_changed)
        v_orient.addWidget(self.combo_orient)
        r_ctrl.addLayout(v_orient, 2)

        # Lệch X (px)
        v_x = QVBoxLayout()
        v_x.addWidget(QLabel("Lệch X (px)"))
        h_x_stepper = QHBoxLayout()
        h_x_stepper.setSpacing(4)
        btn_x_dec = QPushButton("-")
        btn_x_dec.setFixedSize(30, 36)
        btn_x_dec.setStyleSheet("background-color: #C9BDAA; color: #34312E; font-weight: bold; border-radius: 6px; border: 1px solid #BEB3A3;")
        btn_x_dec.clicked.connect(lambda: self.spin_x.setValue(self.spin_x.value() - 2))
        h_x_stepper.addWidget(btn_x_dec)

        self.spin_x = QSpinBox()
        self.spin_x.setRange(-150, 150)
        self.spin_x.setValue(0)
        self.spin_x.setFixedHeight(36)
        self.spin_x.setAlignment(Qt.AlignCenter)
        self.spin_x.setStyleSheet(
            "background-color: #E7DFD2; color: #34312E; border: 1.5px solid #BEB3A3; border-radius: 6px; font-weight: bold;"
        )
        self.spin_x.valueChanged.connect(self._on_margin_changed)
        h_x_stepper.addWidget(self.spin_x)

        btn_x_inc = QPushButton("+")
        btn_x_inc.setFixedSize(30, 36)
        btn_x_inc.setStyleSheet("background-color: #C9BDAA; color: #34312E; font-weight: bold; border-radius: 6px; border: 1px solid #BEB3A3;")
        btn_x_inc.clicked.connect(lambda: self.spin_x.setValue(self.spin_x.value() + 2))
        h_x_stepper.addWidget(btn_x_inc)
        v_x.addLayout(h_x_stepper)
        r_ctrl.addLayout(v_x, 2)

        # Lệch Y (px)
        v_y = QVBoxLayout()
        v_y.addWidget(QLabel("Lệch Y (px)"))
        h_y_stepper = QHBoxLayout()
        h_y_stepper.setSpacing(4)
        btn_y_dec = QPushButton("-")
        btn_y_dec.setFixedSize(30, 36)
        btn_y_dec.setStyleSheet("background-color: #C9BDAA; color: #34312E; font-weight: bold; border-radius: 6px; border: 1px solid #BEB3A3;")
        btn_y_dec.clicked.connect(lambda: self.spin_y.setValue(self.spin_y.value() - 2))
        h_y_stepper.addWidget(btn_y_dec)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(-150, 150)
        self.spin_y.setValue(0)
        self.spin_y.setFixedHeight(36)
        self.spin_y.setAlignment(Qt.AlignCenter)
        self.spin_y.setStyleSheet(
            "background-color: #E7DFD2; color: #34312E; border: 1.5px solid #BEB3A3; border-radius: 6px; font-weight: bold;"
        )
        self.spin_y.valueChanged.connect(self._on_margin_changed)
        h_y_stepper.addWidget(self.spin_y)

        btn_y_inc = QPushButton("+")
        btn_y_inc.setFixedSize(30, 36)
        btn_y_inc.setStyleSheet("background-color: #C9BDAA; color: #34312E; font-weight: bold; border-radius: 6px; border: 1px solid #BEB3A3;")
        btn_y_inc.clicked.connect(lambda: self.spin_y.setValue(self.spin_y.value() + 2))
        h_y_stepper.addWidget(btn_y_inc)
        v_y.addLayout(h_y_stepper)
        r_ctrl.addLayout(v_y, 2)

        # Zoom
        v_zoom = QVBoxLayout()
        v_zoom.addWidget(QLabel("Zoom"))
        self.spin_zoom = QDoubleSpinBox()
        self.spin_zoom.setRange(0.50, 1.50)
        self.spin_zoom.setSingleStep(0.01)
        self.spin_zoom.setValue(0.98)
        self.spin_zoom.setFixedHeight(36)
        self.spin_zoom.setAlignment(Qt.AlignCenter)
        self.spin_zoom.setStyleSheet(
            "background-color: #E7DFD2; color: #34312E; border: 1.5px solid #BEB3A3; border-radius: 6px; font-weight: bold;"
        )
        self.spin_zoom.valueChanged.connect(self._on_margin_changed)
        v_zoom.addWidget(self.spin_zoom)
        r_ctrl.addLayout(v_zoom, 1)

        # Nút Đặt lại 1.0
        v_rst = QVBoxLayout()
        v_rst.addWidget(QLabel(" "))
        self.btn_reset_align = QPushButton("Đặt lại 1.0")
        self.btn_reset_align.setFixedHeight(36)
        self.btn_reset_align.setCursor(Qt.PointingHandCursor)
        self.btn_reset_align.setStyleSheet(
            "background-color: #C9BDAA; color: #34312E; border: 1px solid #BEB3A3; border-radius: 6px; padding: 4px 12px;"
        )
        self.btn_reset_align.clicked.connect(self._reset_margins)
        v_rst.addWidget(self.btn_reset_align)
        r_ctrl.addLayout(v_rst, 1)

        v_controls.addLayout(r_ctrl)

        # Hàng tùy chọn nâng cao: Safety Margin, Auto Orientation, Thermal Pacing
        r_preset_opts = QHBoxLayout()
        r_preset_opts.setSpacing(16)

        self.chk_safety_margin = QCheckBox("Lề an toàn chống tràn mép (Safety Margin 98%)")
        self.chk_safety_margin.setToolTip("Tự động thu nhỏ ảnh 98% để chống bị cắt viền do mép cuộn của máy in nhiệt DNP/Citizen")
        r_preset_opts.addWidget(self.chk_safety_margin)

        self.chk_auto_orientation = QCheckBox("Tự động xoay ảnh khớp hướng giấy (Auto Orientation)")
        self.chk_auto_orientation.setToolTip("Tự động nhận diện hướng giấy DC của máy in và xoay 90 độ nếu tỷ lệ khung hình ngược nhau")
        r_preset_opts.addWidget(self.chk_auto_orientation)

        r_pacing = QHBoxLayout()
        r_pacing.addWidget(QLabel("Giãn cách in nhiệt:"))
        self.spin_thermal_pacing = QDoubleSpinBox()
        self.spin_thermal_pacing.setRange(-1.0, 10.0)
        self.spin_thermal_pacing.setSingleStep(0.5)
        self.spin_thermal_pacing.setValue(-1.0)
        self.spin_thermal_pacing.setSpecialValueText("Theo Preset")
        self.spin_thermal_pacing.setSuffix(" s")
        self.spin_thermal_pacing.setToolTip("-1.0s: Sử dụng cấu hình tối ưu của từng máy in (DNP RX1: 1.5s, QW410: 1.0s, Generic: 0s)")
        r_pacing.addWidget(self.spin_thermal_pacing)
        r_preset_opts.addLayout(r_pacing)
        r_preset_opts.addStretch()

        v_controls.addLayout(r_preset_opts)
        h_align_body.addLayout(v_controls, 1)

        l_align.addLayout(h_align_body)
        layout.addWidget(grp_align)

        # 4. KHU VỰC BỘ ĐẾM GIẤY
        grp_paper = QFrame()
        grp_paper.setStyleSheet("background-color: #E7DFD2; border: 1.5px solid #BEB3A3; border-radius: 12px; padding: 12px;")
        l_paper = QVBoxLayout(grp_paper)
        l_paper.setSpacing(10)

        # Header bộ đếm
        h_p_head = QHBoxLayout()
        h_p_title = QHBoxLayout()
        p_icon = QLabel()
        p_icon.setPixmap(get_svg_pixmap("paper", 22, COLOR_GOLD))
        h_p_title.addWidget(p_icon)
        v_pt = QVBoxLayout()
        lbl_p_name = QLabel("<b>Bộ đếm giấy</b>")
        lbl_p_name.setStyleSheet("font-size: 15px; color: #34312E;")
        lbl_p_sub = QLabel("App tự trừ giấy sau mỗi lần in.")
        lbl_p_sub.setStyleSheet("font-size: 12px; color: #777067;")
        v_pt.addWidget(lbl_p_name)
        v_pt.addWidget(lbl_p_sub)
        h_p_title.addLayout(v_pt)
        h_p_head.addLayout(h_p_title)
        h_p_head.addStretch()

        self.lbl_paper_stats = QLabel("Còn lại: 120 tờ / 400 tờ (30%)")
        self.lbl_paper_stats.setStyleSheet("font-size: 14px; font-weight: bold; color: #34312E;")
        h_p_head.addWidget(self.lbl_paper_stats)
        l_paper.addLayout(h_p_head)

        # Thanh tiến trình giấy in
        self.prog_paper = QProgressBar()
        self.prog_paper.setFixedHeight(18)
        self.prog_paper.setRange(0, 400)
        self.prog_paper.setValue(120)
        self.prog_paper.setTextVisible(False)
        self.prog_paper.setStyleSheet(
            "QProgressBar { background-color: #C9BDAA; border: 1px solid #BEB3A3; border-radius: 9px; }"
            "QProgressBar::chunk { background-color: #B89555; border-radius: 8px; }"
        )
        l_paper.addWidget(self.prog_paper)

        # Các nút nạp nhanh giấy & Ngưỡng cảnh báo
        h_refill = QHBoxLayout()
        h_refill.setSpacing(10)

        for amount in [100, 400, 700]:
            btn = QPushButton(f"+ Nạp {amount} tờ")
            btn.setFixedHeight(34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "background-color: #C9BDAA; color: #34312E; font-weight: bold; border: 1.5px solid #BEB3A3; "
                "border-radius: 8px; padding: 4px 14px;"
            )
            btn.clicked.connect(lambda checked=False, a=amount: self._refill_paper(a))
            h_refill.addWidget(btn)

        h_refill.addStretch()

        h_refill.addWidget(QLabel("Ngưỡng cảnh báo:"))
        h_warn_stepper = QHBoxLayout()
        h_warn_stepper.setSpacing(4)
        btn_w_dec = QPushButton("-")
        btn_w_dec.setFixedSize(28, 34)
        btn_w_dec.setStyleSheet("background-color: #C9BDAA; color: #34312E; font-weight: bold; border-radius: 6px; border: 1px solid #BEB3A3;")
        btn_w_dec.clicked.connect(lambda: self.spin_warning.setValue(self.spin_warning.value() - 10))
        h_warn_stepper.addWidget(btn_w_dec)

        self.spin_warning = QSpinBox()
        self.spin_warning.setRange(10, 200)
        self.spin_warning.setValue(50)
        self.spin_warning.setFixedHeight(34)
        self.spin_warning.setAlignment(Qt.AlignCenter)
        self.spin_warning.setStyleSheet(
            "background-color: #E7DFD2; color: #34312E; border: 1.5px solid #BEB3A3; border-radius: 6px; font-weight: bold;"
        )
        h_warn_stepper.addWidget(self.spin_warning)

        btn_w_inc = QPushButton("+")
        btn_w_inc.setFixedSize(28, 34)
        btn_w_inc.setStyleSheet("background-color: #C9BDAA; color: #34312E; font-weight: bold; border-radius: 6px; border: 1px solid #BEB3A3;")
        btn_w_inc.clicked.connect(lambda: self.spin_warning.setValue(self.spin_warning.value() + 10))
        h_warn_stepper.addWidget(btn_w_inc)
        h_refill.addLayout(h_warn_stepper)

        l_paper.addLayout(h_refill)
        layout.addWidget(grp_paper)

        # 5. BOTTOM ACTION BAR
        h_action = QHBoxLayout()
        h_action.setSpacing(12)

        self.btn_test_print = QPushButton("In thử trang test")
        self.btn_test_print.setIcon(get_svg_icon("printer", 16, COLOR_GOLD))
        self.btn_test_print.setFixedHeight(40)
        self.btn_test_print.setCursor(Qt.PointingHandCursor)
        self.btn_test_print.setStyleSheet(
            "QPushButton { background-color: #E7DFD2; color: #34312E; border: 1.5px solid #BEB3A3; border-radius: 8px; padding: 4px 18px; font-weight: bold; }"
            "QPushButton:hover { background-color: #C9BDAA; border-color: #B89555; }"
        )
        self.btn_test_print.clicked.connect(self._print_test_page)
        h_action.addWidget(self.btn_test_print)

        h_action.addStretch()

        self.btn_cancel = QPushButton("Hủy thay đổi")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(
            "QPushButton { background-color: #E7DFD2; color: #777067; border: 1px solid #BEB3A3; border-radius: 8px; padding: 4px 18px; }"
            "QPushButton:hover { background-color: #C9BDAA; color: #34312E; }"
        )
        self.btn_cancel.clicked.connect(self._load_current_settings)
        h_action.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Lưu cài đặt")
        self.btn_save.setIcon(get_svg_icon("save", 16, "#FFFFFF"))
        self.btn_save.setFixedHeight(40)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #B89555; color: #FFFFFF; font-weight: 900; border: 1px solid #8F7038; border-radius: 8px; padding: 4px 24px; font-size: 14px; }"
            "QPushButton:hover { background-color: #CDB07B; }"
            "QPushButton:pressed { background-color: #8F7038; }"
        )
        self.btn_save.clicked.connect(self._save_settings)
        h_action.addWidget(self.btn_save)

        layout.addLayout(h_action)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _load_printers(self):
        """Quét và tải danh sách máy in thực tế từ Windows Spooler."""
        self.combo_strip.blockSignals(True)
        self.combo_full.blockSignals(True)
        self.combo_strip.clear()
        self.combo_full.clear()

        printers = WindowsPrintSpooler.get_installed_printers()
        default_p = WindowsPrintSpooler.get_default_printer()

        if not printers:
            self.combo_strip.addItem("Không tìm thấy máy in (Virtual)", "")
            self.combo_full.addItem("Không tìm thấy máy in (Virtual)", "")
        else:
            for p in printers:
                p_name = p["name"] if isinstance(p, dict) else str(p)
                self.combo_strip.addItem(p_name, p_name)
                self.combo_full.addItem(p_name, p_name)

        self.combo_strip.blockSignals(False)
        self.combo_full.blockSignals(False)
        self._check_printer_statuses()

    def _load_current_settings(self):
        """Nạp các giá trị cài đặt máy in, lề và giấy in từ PrintManager."""
        self.print_mgr.load_settings()

        # Chọn máy in strip
        if self.print_mgr.strip_printer_name:
            idx = self.combo_strip.findData(self.print_mgr.strip_printer_name)
            if idx >= 0:
                self.combo_strip.setCurrentIndex(idx)

        # Chọn máy in full
        if self.print_mgr.full_printer_name:
            idx = self.combo_full.findData(self.print_mgr.full_printer_name)
            if idx >= 0:
                self.combo_full.setCurrentIndex(idx)

        # Hướng giấy
        orient_idx = 1 if self.print_mgr.orientation.lower() in ("landscape", "ngang") else 0
        self.combo_orient.setCurrentIndex(orient_idx)

        # Căn lề và zoom
        self.spin_x.setValue(self.print_mgr.offset_x)
        self.spin_y.setValue(self.print_mgr.offset_y)
        self.spin_zoom.setValue(self.print_mgr.zoom)

        # Printing hardening & presets
        self.chk_safety_margin.setChecked(self.print_mgr.safety_margin_enabled)
        self.chk_auto_orientation.setChecked(self.print_mgr.auto_orientation_enabled)
        self.spin_thermal_pacing.setValue(self.print_mgr.thermal_pacing_sec)

        # Bộ đếm giấy
        self.prog_paper.setMaximum(max(100, self.print_mgr.paper_max))
        self.prog_paper.setValue(self.print_mgr.paper_count)
        self.spin_warning.setValue(self.print_mgr.paper_warning_threshold)
        self._update_paper_ui()

        self._on_margin_changed()
        self._check_printer_statuses()

    def _on_margin_changed(self):
        """Cập nhật bản vẽ xem trước căn chỉnh lề theo các thông số nhập."""
        ox = self.spin_x.value()
        oy = self.spin_y.value()
        zm = self.spin_zoom.value()
        ori = "landscape" if self.combo_orient.currentIndex() == 1 else "portrait"
        self.preview_widget.update_params(ox, oy, zm, ori)

    def _reset_margins(self):
        """Khôi phục căn lề và zoom về chuẩn mặc định 1.0 và offset 0."""
        self.spin_x.setValue(0)
        self.spin_y.setValue(0)
        self.spin_zoom.setValue(1.0)
        self.chk_safety_margin.setChecked(True)
        self.chk_auto_orientation.setChecked(True)
        self.spin_thermal_pacing.setValue(-1.0)
        self._on_margin_changed()

    def _update_paper_ui(self):
        """Cập nhật giao diện thống kê lượng giấy còn lại và đổi màu thanh tiến trình."""
        curr = self.print_mgr.paper_count
        tot = self.print_mgr.paper_max
        pct = int((curr / tot) * 100) if tot > 0 else 0

        self.prog_paper.setValue(curr)
        self.lbl_paper_stats.setText(f"Còn lại: {curr} tờ / {tot} tờ ({pct}%)")

        if curr <= self.spin_warning.value():
            self.prog_paper.setStyleSheet(
                "QProgressBar { background-color: #E2E8F0; border: 1px solid #CBD5E1; border-radius: 9px; }"
                "QProgressBar::chunk { background-color: #EF4444; border-radius: 8px; }"
            )
            self.lbl_paper_stats.setStyleSheet("font-size: 14px; font-weight: bold; color: #EF4444;")
        else:
            self.prog_paper.setStyleSheet(
                "QProgressBar { background-color: #E2E8F0; border: 1px solid #CBD5E1; border-radius: 9px; }"
                "QProgressBar::chunk { background-color: #10B981; border-radius: 8px; }"
            )
            self.lbl_paper_stats.setStyleSheet("font-size: 14px; font-weight: bold; color: #303746;")

    def _refill_paper(self, amount: int):
        """Xử lý nút nạp thêm giấy nhanh."""
        new_total = self.print_mgr.refill_paper(amount)
        self._update_paper_ui()

    def _check_printer_statuses(self):
        """Kiểm tra trạng thái kết nối thực tế từ Windows Spooler cho cả 2 máy in."""
        # 1. Kiểm tra máy in strip
        p_strip = self.combo_strip.currentData()
        if p_strip:
            status_s = WindowsPrintSpooler.get_printer_status(p_strip)
            if status_s.get("is_online", False):
                self.lbl_strip_status.setText("🟢 Sẵn sàng")
                self.lbl_strip_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
            else:
                self.lbl_strip_status.setText(f"🔴 {status_s.get('status_text', 'Mất kết nối')}")
                self.lbl_strip_status.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 12px;")
        else:
            self.lbl_strip_status.setText("⚪ Chưa chọn")
            self.lbl_strip_status.setStyleSheet("color: #94A3B8; font-size: 12px;")

        # 2. Kiểm tra máy in full
        p_full = self.combo_full.currentData()
        if p_full:
            status_f = WindowsPrintSpooler.get_printer_status(p_full)
            if status_f.get("is_online", False):
                self.lbl_full_status.setText("🟢 Sẵn sàng")
                self.lbl_full_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
            else:
                self.lbl_full_status.setText(f"🔴 {status_f.get('status_text', 'Mất kết nối')}")
                self.lbl_full_status.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 12px;")
        else:
            self.lbl_full_status.setText("⚪ Chưa chọn")
            self.lbl_full_status.setStyleSheet("color: #94A3B8; font-size: 12px;")

    def _save_settings(self):
        """Lưu toàn bộ cài đặt máy in, căn lề và ngưỡng giấy."""
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Lưu Cài Đặt Máy In"):
                return

        self.print_mgr.strip_printer_name = self.combo_strip.currentData() or ""
        self.print_mgr.full_printer_name = self.combo_full.currentData() or ""
        self.print_mgr.orientation = "landscape" if self.combo_orient.currentIndex() == 1 else "portrait"
        self.print_mgr.offset_x = self.spin_x.value()
        self.print_mgr.offset_y = self.spin_y.value()
        self.print_mgr.zoom = self.spin_zoom.value()
        self.print_mgr.paper_warning_threshold = self.spin_warning.value()
        self.print_mgr.safety_margin_enabled = self.chk_safety_margin.isChecked()
        self.print_mgr.auto_orientation_enabled = self.chk_auto_orientation.isChecked()
        self.print_mgr.thermal_pacing_sec = self.spin_thermal_pacing.value()

        if self.print_mgr.strip_printer_name:
            self.print_mgr.selected_printer = self.print_mgr.strip_printer_name

        self.print_mgr.save_settings()
        QMessageBox.information(self, "Cài Đặt Máy In", "Đã lưu thành công cấu hình máy in, căn lề và bộ đếm giấy!")

    def _print_test_page(self):
        """In trang kiểm tra căn lề thực tế ra máy in."""
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực In Thử Nghiệm"):
                return

        active_p = self.combo_strip.currentData() or self.print_mgr.get_selected_printer()
        if not active_p:
            QMessageBox.warning(self, "Máy In", "Vui lòng chọn máy in trước khi in thử nghiệm.")
            return

        success = self.print_mgr.print_test_page()
        if success:
            QMessageBox.information(
                self, "In Kiểm Tra",
                f"Đã gửi trang in thử nghiệm tới máy in '{active_p}'. Vui lòng kiểm tra khay giấy ra."
            )
            self._update_paper_ui()
        else:
            QMessageBox.warning(
                self, "Lỗi In",
                f"Không thể gửi lệnh in tới '{active_p}'. Vui lòng kiểm tra cáp kết nối và nguồn điện máy in."
            )
