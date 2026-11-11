"""
1998 TEAM — Photobooth Printing Page
Minimal Luxury Studio / Warm Alabaster Studio Design System:
- Dual printer configuration: Máy in strip (2x6) & Máy in full (4x6).
- Real printer detection and status indicator directly from Windows Spooler.
- Visual print margin & orientation alignment preview (Portrait & Landscape responsive).
- Interactive steppers for Offset X/Y, Zoom, Copies with reset button.
- Advanced print hardening options: Safety Margin (98%), Auto-Orientation, Thermal Pacing.
- Real paper sheet counter with progress bar, quick refill buttons (+100, +400, +700), and warning threshold.
- Interactive Print Queue & Job History panel with real-time status tracking.
- Test print execution and persistent settings.
"""

import os
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QProgressBar, QSpinBox, QDoubleSpinBox, QFrame, QScrollArea,
    QMessageBox, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QAbstractScrollArea
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QFont

from vietphotobooth.printing.manager import (
    PrintManager, STATUS_PENDING, STATUS_COMPLETED, STATUS_ERROR, STATUS_SPOOLED, STATUS_SPOOLING
)
from vietphotobooth.printing.spooler import WindowsPrintSpooler
from vietphotobooth.printing.presets import PrintPresetRegistry
from vietphotobooth.desktop.icons import (
    get_svg_icon, get_svg_pixmap, COLOR_GOLD, COLOR_WHITE, COLOR_SLATE, COLOR_BLUE, COLOR_GREEN, COLOR_RED
)
from vietphotobooth.desktop.styles import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_SECONDARY,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_BORDER, COLOR_BORDER_LIGHT,
    COLOR_CHAMPAGNE, COLOR_CHAMPAGNE_LIGHT, COLOR_PALE_GOLD,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    THEME_BG_MAIN, THEME_SURFACE, THEME_BG_SECONDARY, THEME_INPUT_BG,
    THEME_BORDER, THEME_BORDER_LIGHT, THEME_TEXT_PRIMARY, THEME_TEXT_SECONDARY,
    THEME_TEXT_DISABLED, THEME_GOLD, THEME_GOLD_LIGHT, THEME_GOLD_DARK
)
from vietphotobooth.core.logger import get_logger

logger = get_logger()


class PrintMarginPreviewWidget(QFrame):
    """Bản vẽ trực quan mô phỏng khổ giấy in, căn chỉnh lề (offset X/Y) và thu phóng (zoom)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("print_margin_preview")
        self.setFixedSize(140, 190)
        self.setStyleSheet(
            f"QFrame#print_margin_preview {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 10px; }}"
        )
        self.offset_x = 0
        self.offset_y = 0
        self.zoom = 1.0
        self.orientation = "portrait"

    def update_params(self, offset_x: int, offset_y: int, zoom: float, orientation: str):
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.zoom = zoom
        self.orientation = orientation.lower()
        if self.orientation in ("landscape", "ngang"):
            self.setFixedSize(190, 140)
        else:
            self.setFixedSize(140, 190)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Khổ giấy in nền
        paper_x, paper_y = 10, 10
        paper_w, paper_h = w - 20, h - 20

        painter.setPen(QPen(QColor(COLOR_BORDER), 1.5))
        painter.setBrush(QBrush(QColor(COLOR_SURFACE_SECONDARY)))
        painter.drawRoundedRect(paper_x, paper_y, paper_w, paper_h, 6, 6)

        # Mô phỏng nội dung dải ảnh với offset và zoom
        base_content_w = paper_w - 16
        base_content_h = paper_h - 16

        scaled_w = max(10, int(base_content_w * self.zoom))
        scaled_h = max(10, int(base_content_h * self.zoom))

        # Dịch pixel theo tỷ lệ preview
        shift_x = int(self.offset_x * 0.22)
        shift_y = int(self.offset_y * 0.22)

        cx = paper_x + (paper_w - scaled_w) // 2 + shift_x
        cy = paper_y + (paper_h - scaled_h) // 2 + shift_y

        # Viền nội dung ảnh in (màu vàng champagne)
        painter.setPen(QPen(QColor(COLOR_CHAMPAGNE), 1.5, Qt.DashLine))
        painter.setBrush(QBrush(QColor(185, 154, 99, 30)))
        painter.drawRoundedRect(cx, cy, scaled_w, scaled_h, 4, 4)

        # Thumbnail minh họa (3 ô nếu dọc, 2 ô nếu ngang)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(185, 154, 99, 80)))

        if self.orientation in ("landscape", "ngang"):
            slot_w = max(4, (scaled_w - 12) // 2)
            slot_h = max(4, scaled_h - 8)
            for i in range(2):
                sx = cx + 4 + i * (slot_w + 4)
                if sx + slot_w <= cx + scaled_w:
                    painter.drawRoundedRect(sx, cy + 4, slot_w, slot_h, 2, 2)
        else:
            slot_h = max(4, (scaled_h - 16) // 3)
            slot_w = max(4, scaled_w - 8)
            for i in range(3):
                sy = cy + 4 + i * (slot_h + 4)
                if sy + slot_h <= cy + scaled_h:
                    painter.drawRoundedRect(cx + 4, sy, slot_w, slot_h, 2, 2)

        painter.end()


class PrintingPage(QWidget):
    """Trang Cài Đặt Máy In chuẩn Minimal Luxury Studio 1998 TEAM Photobooth."""

    def minimumSizeHint(self) -> QSize:
        return QSize(720, 480)

    def __init__(self, print_mgr: PrintManager, auth_mgr=None, parent=None):
        super().__init__(parent)
        self.print_mgr = print_mgr
        self.auth_mgr = auth_mgr

        self._init_ui()
        self._load_printers()
        self._load_current_settings()
        self._refresh_queue_table()

        # Timer quét trạng thái máy in và hàng đợi mỗi 3 giây
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._on_status_timer_tick)
        self.status_timer.start(3000)

    def _init_ui(self):
        self.setStyleSheet(f"background-color: {COLOR_BG};")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        self.scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"background-color: {COLOR_BG}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background-color: {COLOR_BG};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # =========================================================================
        # 1. HEADER CÀI ĐẶT MÁY IN
        # =========================================================================
        h_head = QHBoxLayout()
        h_head.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap("printer", 28, COLOR_CHAMPAGNE))
        h_head.addWidget(icon_lbl)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("CÀI ĐẶT MÁY IN")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {COLOR_TEXT_PRIMARY}; letter-spacing: 0.5px; border: none; background: transparent;")
        lbl_sub = QLabel("1998 TEAM Photobooth • Quản lý thiết bị in, căn chỉnh lề, bộ đếm giấy và hàng đợi in.")
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_sub)
        h_head.addLayout(v_head)

        h_head.addStretch()

        self.btn_refresh = QPushButton("Làm mới danh sách")
        self.btn_refresh.setIcon(get_svg_icon("refresh", 16, COLOR_CHAMPAGNE))
        self.btn_refresh.setFixedHeight(36)
        self.btn_refresh.setMinimumWidth(165)
        self.btn_refresh.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; "
            f"border-radius: 8px; padding: 0 16px; font-weight: 600; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {COLOR_SURFACE_SECONDARY}; border-color: {COLOR_CHAMPAGNE}; }}"
        )
        self.btn_refresh.clicked.connect(self._load_printers)
        h_head.addWidget(self.btn_refresh)

        layout.addLayout(h_head)

        # Common styles for inputs
        combo_style = (
            f"QComboBox {{ background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 8px; padding: 4px 12px; font-size: 13px; font-weight: 600; }} "
            f"QComboBox:hover {{ border-color: {COLOR_CHAMPAGNE}; }} "
            f"QComboBox:focus {{ border: 1.5px solid {COLOR_CHAMPAGNE}; }} "
            f"QComboBox::drop-down {{ border: none; width: 24px; }}"
        )
        stepper_btn_style = (
            f"QPushButton {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-weight: bold; "
            f"border-radius: 6px; border: 1px solid {COLOR_BORDER}; font-size: 16px; padding: 0px; text-align: center; }} "
            f"QPushButton:hover {{ background-color: {COLOR_PALE_GOLD}; border-color: {COLOR_CHAMPAGNE}; color: {COLOR_TEXT_PRIMARY}; }} "
            f"QPushButton:pressed {{ background-color: {COLOR_CHAMPAGNE_LIGHT}; }}"
        )
        spin_stepper_style = (
            f"QSpinBox {{ background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 6px; font-weight: 600; font-size: 13px; }} "
            f"QSpinBox:hover {{ border-color: {COLOR_CHAMPAGNE}; }} "
            f"QSpinBox:focus {{ border: 1.5px solid {COLOR_CHAMPAGNE}; }} "
            f"QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; height: 0px; border: none; }}"
        )
        spin_style = (
            f"QSpinBox, QDoubleSpinBox {{ background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 6px; font-weight: 600; font-size: 13px; }} "
            f"QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {COLOR_CHAMPAGNE}; }} "
            f"QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1.5px solid {COLOR_CHAMPAGNE}; }}"
        )

        # =========================================================================
        # 2. KHU VỰC THIẾT BỊ MÁY IN: MÁY IN STRIP (2x6) & MÁY IN FULL (4x6)
        # =========================================================================
        self.h_printers = QHBoxLayout()
        self.h_printers.setSpacing(16)

        # Card Máy in Strip (2x6)
        self.card_strip = QFrame()
        self.card_strip.setObjectName("card_strip")
        self.card_strip.setStyleSheet(f"""
            QFrame#card_strip {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_strip = QVBoxLayout(self.card_strip)
        l_strip.setContentsMargins(18, 16, 18, 16)
        l_strip.setSpacing(12)

        h_strip_title = QHBoxLayout()
        h_strip_title.setSpacing(10)
        icon_strip = QLabel()
        icon_strip.setPixmap(get_svg_pixmap("paper", 22, COLOR_CHAMPAGNE))
        h_strip_title.addWidget(icon_strip)

        v_st = QVBoxLayout()
        v_st.setSpacing(2)
        h_st_name = QHBoxLayout()
        lbl_st_name = QLabel("<b>Máy in strip (Khổ 2x6)</b>")
        lbl_st_name.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        h_st_name.addWidget(lbl_st_name)
        h_st_name.addStretch()

        self.lbl_strip_preset = QLabel("Dye-Sub")
        self.lbl_strip_preset.setStyleSheet(
            f"QLabel {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 700; "
            f"border-radius: 6px; padding: 2px 8px; border: 1px solid {COLOR_BORDER}; }}"
        )
        h_st_name.addWidget(self.lbl_strip_preset)
        v_st.addLayout(h_st_name)

        lbl_st_sub = QLabel("Khổ ảnh dải dọc 2x6 inch (51 × 152 mm)")
        lbl_st_sub.setWordWrap(True)
        lbl_st_sub.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_st.addWidget(lbl_st_sub)

        h_strip_title.addLayout(v_st)
        l_strip.addLayout(h_strip_title)

        self.combo_strip = QComboBox()
        self.combo_strip.setFixedHeight(38)
        self.combo_strip.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_strip.setMinimumContentsLength(12)
        self.combo_strip.setStyleSheet(combo_style)
        self.combo_strip.currentIndexChanged.connect(self._check_printer_statuses)
        l_strip.addWidget(self.combo_strip)

        h_st_status = QHBoxLayout()
        h_st_status.setSpacing(8)
        self.lbl_strip_status = QLabel("🟢 Sẵn sàng (Ready)")
        self.lbl_strip_status.setStyleSheet("color: #54836A; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        h_st_status.addWidget(self.lbl_strip_status)
        h_st_status.addStretch()

        self.lbl_strip_detail = QLabel("Spooler: 0 tác vụ đang chờ")
        self.lbl_strip_detail.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; border: none; background: transparent;")
        h_st_status.addWidget(self.lbl_strip_detail)
        l_strip.addLayout(h_st_status)

        self.h_printers.addWidget(self.card_strip, 1)

        # Card Máy in Full (4x6)
        self.card_full = QFrame()
        self.card_full.setObjectName("card_full")
        self.card_full.setStyleSheet(f"""
            QFrame#card_full {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_full = QVBoxLayout(self.card_full)
        l_full.setContentsMargins(18, 16, 18, 16)
        l_full.setSpacing(12)

        h_full_title = QHBoxLayout()
        h_full_title.setSpacing(10)
        icon_full = QLabel()
        icon_full.setPixmap(get_svg_pixmap("frame", 22, COLOR_CHAMPAGNE))
        h_full_title.addWidget(icon_full)

        v_ft = QVBoxLayout()
        v_ft.setSpacing(2)
        h_ft_name = QHBoxLayout()
        lbl_ft_name = QLabel("<b>Máy in full (Khổ 4x6)</b>")
        lbl_ft_name.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        h_ft_name.addWidget(lbl_ft_name)
        h_ft_name.addStretch()

        self.lbl_full_preset = QLabel("Dye-Sub")
        self.lbl_full_preset.setStyleSheet(
            f"QLabel {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 700; "
            f"border-radius: 6px; padding: 2px 8px; border: 1px solid {COLOR_BORDER}; }}"
        )
        h_ft_name.addWidget(self.lbl_full_preset)
        v_ft.addLayout(h_ft_name)

        lbl_ft_sub = QLabel("Khổ ảnh ngang hoặc vuông 4x6 inch (102 × 152 mm)")
        lbl_ft_sub.setWordWrap(True)
        lbl_ft_sub.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_ft.addWidget(lbl_ft_sub)

        h_full_title.addLayout(v_ft)
        l_full.addLayout(h_full_title)

        self.combo_full = QComboBox()
        self.combo_full.setFixedHeight(38)
        self.combo_full.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_full.setMinimumContentsLength(12)
        self.combo_full.setStyleSheet(combo_style)
        self.combo_full.currentIndexChanged.connect(self._check_printer_statuses)
        l_full.addWidget(self.combo_full)

        h_ft_status = QHBoxLayout()
        h_ft_status.setSpacing(8)
        self.lbl_full_status = QLabel("🟢 Sẵn sàng (Ready)")
        self.lbl_full_status.setStyleSheet("color: #54836A; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        h_ft_status.addWidget(self.lbl_full_status)
        h_ft_status.addStretch()

        self.lbl_full_detail = QLabel("Spooler: 0 tác vụ đang chờ")
        self.lbl_full_detail.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; border: none; background: transparent;")
        h_ft_status.addWidget(self.lbl_full_detail)
        l_full.addLayout(h_ft_status)

        self.h_printers.addWidget(self.card_full, 1)

        layout.addLayout(self.h_printers)

        # =========================================================================
        # 3. KHU VỰC CĂN CHỈNH LỀ, HƯỚNG IN & CẤU HÌNH BẢN IN
        # =========================================================================
        grp_align = QFrame()
        grp_align.setObjectName("grp_align")
        grp_align.setStyleSheet(f"""
            QFrame#grp_align {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_align = QVBoxLayout(grp_align)
        l_align.setContentsMargins(18, 16, 18, 16)
        l_align.setSpacing(14)

        lbl_al_title = QLabel("<b>Căn chỉnh lề, hướng in &amp; cấu hình bản in</b>")
        lbl_al_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        l_align.addWidget(lbl_al_title)

        h_align_body = QHBoxLayout()
        h_align_body.setSpacing(24)

        # Preview diagram bên trái
        self.preview_widget = PrintMarginPreviewWidget()
        h_align_body.addWidget(self.preview_widget, 0, Qt.AlignCenter)

        # Bảng điều khiển bên phải (chia làm 3 hàng cân đối, có cấu trúc)
        v_controls = QVBoxLayout()
        v_controls.setSpacing(14)

        # --- HÀNG 1: Hướng giấy, Lệch X, Lệch Y, Zoom, Nút Đặt lại ---
        r_ctrl_1 = QHBoxLayout()
        r_ctrl_1.setSpacing(14)

        # 1. Hướng giấy
        v_orient = QVBoxLayout()
        v_orient.setSpacing(6)
        lbl_orient_tag = QLabel("Hướng giấy:")
        lbl_orient_tag.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_orient.addWidget(lbl_orient_tag)
        self.combo_orient = QComboBox()
        self.combo_orient.setFixedHeight(36)
        self.combo_orient.setMinimumWidth(130)
        self.combo_orient.addItems(["Dọc (Portrait)", "Ngang (Landscape)"])
        self.combo_orient.setStyleSheet(combo_style)
        self.combo_orient.currentIndexChanged.connect(self._on_margin_changed)
        v_orient.addWidget(self.combo_orient)
        r_ctrl_1.addLayout(v_orient, 2)

        # 2. Lệch X (px)
        v_x = QVBoxLayout()
        v_x.setSpacing(6)
        lbl_x_tag = QLabel("Lệch X (px):")
        lbl_x_tag.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_x.addWidget(lbl_x_tag)
        h_x_stepper = QHBoxLayout()
        h_x_stepper.setSpacing(2)
        btn_x_dec = QPushButton("-")
        btn_x_dec.setFixedSize(28, 36)
        btn_x_dec.setStyleSheet(stepper_btn_style)
        btn_x_dec.clicked.connect(lambda: self.spin_x.setValue(self.spin_x.value() - 2))
        h_x_stepper.addWidget(btn_x_dec)

        self.spin_x = QSpinBox()
        self.spin_x.setRange(-150, 150)
        self.spin_x.setValue(0)
        self.spin_x.setFixedHeight(36)
        self.spin_x.setMinimumWidth(55)
        self.spin_x.setAlignment(Qt.AlignCenter)
        self.spin_x.setStyleSheet(spin_stepper_style)
        self.spin_x.valueChanged.connect(self._on_margin_changed)
        h_x_stepper.addWidget(self.spin_x)

        btn_x_inc = QPushButton("+")
        btn_x_inc.setFixedSize(28, 36)
        btn_x_inc.setStyleSheet(stepper_btn_style)
        btn_x_inc.clicked.connect(lambda: self.spin_x.setValue(self.spin_x.value() + 2))
        h_x_stepper.addWidget(btn_x_inc)
        v_x.addLayout(h_x_stepper)
        r_ctrl_1.addLayout(v_x, 2)

        # 3. Lệch Y (px)
        v_y = QVBoxLayout()
        v_y.setSpacing(6)
        lbl_y_tag = QLabel("Lệch Y (px):")
        lbl_y_tag.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_y.addWidget(lbl_y_tag)
        h_y_stepper = QHBoxLayout()
        h_y_stepper.setSpacing(2)
        btn_y_dec = QPushButton("-")
        btn_y_dec.setFixedSize(28, 36)
        btn_y_dec.setStyleSheet(stepper_btn_style)
        btn_y_dec.clicked.connect(lambda: self.spin_y.setValue(self.spin_y.value() - 2))
        h_y_stepper.addWidget(btn_y_dec)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(-150, 150)
        self.spin_y.setValue(0)
        self.spin_y.setFixedHeight(36)
        self.spin_y.setMinimumWidth(55)
        self.spin_y.setAlignment(Qt.AlignCenter)
        self.spin_y.setStyleSheet(spin_stepper_style)
        self.spin_y.valueChanged.connect(self._on_margin_changed)
        h_y_stepper.addWidget(self.spin_y)

        btn_y_inc = QPushButton("+")
        btn_y_inc.setFixedSize(28, 36)
        btn_y_inc.setStyleSheet(stepper_btn_style)
        btn_y_inc.clicked.connect(lambda: self.spin_y.setValue(self.spin_y.value() + 2))
        h_y_stepper.addWidget(btn_y_inc)
        v_y.addLayout(h_y_stepper)
        r_ctrl_1.addLayout(v_y, 2)

        # 4. Zoom
        v_zoom = QVBoxLayout()
        v_zoom.setSpacing(6)
        lbl_zoom_tag = QLabel("Thu phóng:")
        lbl_zoom_tag.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_zoom.addWidget(lbl_zoom_tag)
        self.spin_zoom = QDoubleSpinBox()
        self.spin_zoom.setRange(0.50, 1.50)
        self.spin_zoom.setSingleStep(0.01)
        self.spin_zoom.setValue(0.98)
        self.spin_zoom.setFixedHeight(36)
        self.spin_zoom.setMinimumWidth(65)
        self.spin_zoom.setAlignment(Qt.AlignCenter)
        self.spin_zoom.setStyleSheet(spin_style)
        self.spin_zoom.valueChanged.connect(self._on_margin_changed)
        v_zoom.addWidget(self.spin_zoom)
        r_ctrl_1.addLayout(v_zoom, 2)

        # 5. Nút Đặt lại 1.0 (Có label tiêu đề cân đối với các cột khác)
        v_rst = QVBoxLayout()
        v_rst.setSpacing(6)
        lbl_rst_tag = QLabel("Khôi phục:")
        lbl_rst_tag.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_rst.addWidget(lbl_rst_tag)
        self.btn_reset_align = QPushButton("↺ Đặt lại 1.0")
        self.btn_reset_align.setFixedHeight(36)
        self.btn_reset_align.setMinimumWidth(95)
        self.btn_reset_align.setCursor(Qt.PointingHandCursor)
        self.btn_reset_align.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 6px; padding: 4px 10px; font-weight: bold; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {COLOR_PALE_GOLD}; border-color: {COLOR_CHAMPAGNE}; }}"
        )
        self.btn_reset_align.clicked.connect(self._reset_margins)
        v_rst.addWidget(self.btn_reset_align)
        r_ctrl_1.addLayout(v_rst, 2)

        v_controls.addLayout(r_ctrl_1)

        # --- HÀNG 2: Tùy chọn an toàn (Safety margin & Auto-orientation) ---
        r_ctrl_2 = QHBoxLayout()
        r_ctrl_2.setSpacing(24)

        chk_style = (
            f"QCheckBox {{ color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 500; spacing: 8px; border: none; background: transparent; }} "
            f"QCheckBox::indicator {{ width: 18px; height: 18px; border: 1.5px solid {COLOR_BORDER}; border-radius: 4px; background-color: {COLOR_SURFACE}; }} "
            f"QCheckBox::indicator:hover {{ border-color: {COLOR_CHAMPAGNE}; }} "
            f"QCheckBox::indicator:checked {{ background-color: {COLOR_CHAMPAGNE}; border-color: {COLOR_CHAMPAGNE}; }}"
        )

        self.chk_safety_margin = QCheckBox("Lề an toàn chống xén mép (98%)")
        self.chk_safety_margin.setToolTip("Tự động thu nhỏ ảnh 98% để chống bị cắt viền do mép cuộn của máy in nhiệt DNP/Citizen")
        self.chk_safety_margin.setStyleSheet(chk_style)
        r_ctrl_2.addWidget(self.chk_safety_margin)

        self.chk_auto_orientation = QCheckBox("Tự động xoay khớp hướng giấy")
        self.chk_auto_orientation.setToolTip("Tự động nhận diện hướng giấy của máy in và xoay 90 độ nếu tỷ lệ khung hình ngược nhau")
        self.chk_auto_orientation.setStyleSheet(chk_style)
        r_ctrl_2.addWidget(self.chk_auto_orientation)
        r_ctrl_2.addStretch()
        v_controls.addLayout(r_ctrl_2)

        # --- HÀNG 3: Cấu hình bản in & Giãn cách nhiệt ---
        r_ctrl_3 = QHBoxLayout()
        r_ctrl_3.setSpacing(24)

        r_copies = QHBoxLayout()
        r_copies.setSpacing(8)
        lbl_copies = QLabel("Số bản in:")
        lbl_copies.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        r_copies.addWidget(lbl_copies)
        self.spin_copies = QSpinBox()
        self.spin_copies.setRange(1, 10)
        self.spin_copies.setValue(1)
        self.spin_copies.setFixedHeight(32)
        self.spin_copies.setFixedWidth(55)
        self.spin_copies.setAlignment(Qt.AlignCenter)
        self.spin_copies.setStyleSheet(spin_style)
        self.spin_copies.setToolTip("Số bản in xuất ra cho mỗi lần chụp thành công (1 - 10 bản)")
        r_copies.addWidget(self.spin_copies)
        r_ctrl_3.addLayout(r_copies)

        r_pacing = QHBoxLayout()
        r_pacing.setSpacing(8)
        lbl_pacing = QLabel("Giãn cách nhiệt:")
        lbl_pacing.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        r_pacing.addWidget(lbl_pacing)
        self.spin_thermal_pacing = QDoubleSpinBox()
        self.spin_thermal_pacing.setRange(-1.0, 10.0)
        self.spin_thermal_pacing.setSingleStep(0.5)
        self.spin_thermal_pacing.setValue(-1.0)
        self.spin_thermal_pacing.setFixedHeight(32)
        self.spin_thermal_pacing.setMinimumWidth(115)
        self.spin_thermal_pacing.setAlignment(Qt.AlignCenter)
        self.spin_thermal_pacing.setSpecialValueText("Theo Preset")
        self.spin_thermal_pacing.setSuffix(" s")
        self.spin_thermal_pacing.setToolTip("-1.0s: Sử dụng cấu hình tối ưu của từng máy in (DNP RX1: 2.0s, QW410: 2.5s, Generic: 0s)")
        self.spin_thermal_pacing.setStyleSheet(spin_style)
        r_pacing.addWidget(self.spin_thermal_pacing)
        r_ctrl_3.addLayout(r_pacing)

        r_ctrl_3.addStretch()
        v_controls.addLayout(r_ctrl_3)

        h_align_body.addLayout(v_controls, 1)
        l_align.addLayout(h_align_body)
        layout.addWidget(grp_align)

        # =========================================================================
        # 4. KHU VỰC BỘ ĐẾM GIẤY & QUẢN LÝ NẠP GIẤY
        # =========================================================================
        grp_paper = QFrame()
        grp_paper.setObjectName("grp_paper")
        grp_paper.setStyleSheet(f"""
            QFrame#grp_paper {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_paper = QVBoxLayout(grp_paper)
        l_paper.setContentsMargins(18, 16, 18, 16)
        l_paper.setSpacing(12)

        # Header bộ đếm
        h_p_head = QHBoxLayout()
        h_p_head.setSpacing(12)
        
        p_icon = QLabel()
        p_icon.setPixmap(get_svg_pixmap("paper", 22, COLOR_CHAMPAGNE))
        h_p_head.addWidget(p_icon)

        v_pt = QVBoxLayout()
        v_pt.setSpacing(2)
        lbl_p_name = QLabel("<b>Bộ đếm giấy &amp; giám sát vật tư</b>")
        lbl_p_name.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        lbl_p_sub = QLabel("Hệ thống tự động khấu trừ giấy sau mỗi lần in hoàn tất.")
        lbl_p_sub.setWordWrap(True)
        lbl_p_sub.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_pt.addWidget(lbl_p_name)
        v_pt.addWidget(lbl_p_sub)
        h_p_head.addLayout(v_pt)
        h_p_head.addStretch()

        self.lbl_paper_stats = QLabel("Còn lại: 120 tờ / 400 tờ (30%)")
        self.lbl_paper_stats.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        h_p_head.addWidget(self.lbl_paper_stats)
        l_paper.addLayout(h_p_head)

        # Thanh tiến trình giấy in
        self.prog_paper = QProgressBar()
        self.prog_paper.setFixedHeight(12)
        self.prog_paper.setRange(0, 400)
        self.prog_paper.setValue(120)
        self.prog_paper.setTextVisible(False)
        self.prog_paper.setStyleSheet(
            f"QProgressBar {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; }} "
            f"QProgressBar::chunk {{ background-color: {COLOR_CHAMPAGNE}; border-radius: 5px; }}"
        )
        l_paper.addWidget(self.prog_paper)

        # Các nút nạp nhanh giấy & Ngưỡng cảnh báo
        h_refill = QHBoxLayout()
        h_refill.setSpacing(10)

        refill_btn_style = (
            f"QPushButton {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-weight: bold; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 8px; padding: 4px 14px; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {COLOR_PALE_GOLD}; border-color: {COLOR_CHAMPAGNE}; }}"
        )

        for amount in [100, 400, 700]:
            btn = QPushButton(f"+ Nạp {amount} tờ")
            btn.setFixedHeight(34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(refill_btn_style)
            btn.clicked.connect(lambda checked=False, a=amount: self._refill_paper(a))
            h_refill.addWidget(btn)

        h_refill.addStretch()

        lbl_warn_title = QLabel("Ngưỡng cảnh báo:")
        lbl_warn_title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        h_refill.addWidget(lbl_warn_title)

        h_warn_stepper = QHBoxLayout()
        h_warn_stepper.setSpacing(2)
        btn_w_dec = QPushButton("-")
        btn_w_dec.setFixedSize(28, 34)
        btn_w_dec.setStyleSheet(stepper_btn_style)
        btn_w_dec.clicked.connect(lambda: self.spin_warning.setValue(self.spin_warning.value() - 10))
        h_warn_stepper.addWidget(btn_w_dec)

        self.spin_warning = QSpinBox()
        self.spin_warning.setRange(10, 200)
        self.spin_warning.setValue(50)
        self.spin_warning.setFixedHeight(34)
        self.spin_warning.setFixedWidth(60)
        self.spin_warning.setAlignment(Qt.AlignCenter)
        self.spin_warning.setStyleSheet(spin_stepper_style)
        h_warn_stepper.addWidget(self.spin_warning)

        btn_w_inc = QPushButton("+")
        btn_w_inc.setFixedSize(28, 34)
        btn_w_inc.setStyleSheet(stepper_btn_style)
        btn_w_inc.clicked.connect(lambda: self.spin_warning.setValue(self.spin_warning.value() + 10))
        h_warn_stepper.addWidget(btn_w_inc)
        h_refill.addLayout(h_warn_stepper)

        l_paper.addLayout(h_refill)
        layout.addWidget(grp_paper)

        # =========================================================================
        # 5. KHU VỰC HÀNG ĐỢI & LỊCH SỬ IN (PRINT QUEUE & HISTORY)
        # =========================================================================
        grp_queue = QFrame()
        grp_queue.setObjectName("grp_queue")
        grp_queue.setStyleSheet(f"""
            QFrame#grp_queue {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_queue = QVBoxLayout(grp_queue)
        l_queue.setContentsMargins(18, 16, 18, 16)
        l_queue.setSpacing(12)

        h_q_head = QHBoxLayout()
        h_q_head.setSpacing(12)
        q_icon = QLabel()
        q_icon.setPixmap(get_svg_pixmap("printer", 22, COLOR_CHAMPAGNE))
        h_q_head.addWidget(q_icon)

        v_qt = QVBoxLayout()
        v_qt.setSpacing(2)
        lbl_q_name = QLabel("<b>Hàng đợi &amp; Lịch sử in ấn</b>")
        lbl_q_name.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")
        lbl_q_sub = QLabel("Theo dõi trạng thái các tác vụ in theo thời gian thực (Waiting / Printing / Completed / Failed).")
        lbl_q_sub.setWordWrap(True)
        lbl_q_sub.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        v_qt.addWidget(lbl_q_name)
        v_qt.addWidget(lbl_q_sub)
        h_q_head.addLayout(v_qt)
        h_q_head.addStretch()

        self.btn_refresh_queue = QPushButton("Cập nhật")
        self.btn_refresh_queue.setIcon(get_svg_icon("refresh", 14, COLOR_CHAMPAGNE))
        self.btn_refresh_queue.setFixedHeight(32)
        self.btn_refresh_queue.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_queue.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 6px; padding: 2px 12px; font-size: 11px; font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {COLOR_PALE_GOLD}; border-color: {COLOR_CHAMPAGNE}; }}"
        )
        self.btn_refresh_queue.clicked.connect(self._refresh_queue_table)
        h_q_head.addWidget(self.btn_refresh_queue)

        self.btn_clear_completed = QPushButton("Xóa lệnh đã in")
        self.btn_clear_completed.setFixedHeight(32)
        self.btn_clear_completed.setCursor(Qt.PointingHandCursor)
        self.btn_clear_completed.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 6px; padding: 2px 12px; font-size: 11px; }} "
            f"QPushButton:hover {{ background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border-color: {COLOR_CHAMPAGNE}; }}"
        )
        self.btn_clear_completed.clicked.connect(self._clear_completed_queue)
        h_q_head.addWidget(self.btn_clear_completed)

        l_queue.addLayout(h_q_head)

        # Bảng danh sách hàng đợi
        self.table_queue = QTableWidget(0, 6)
        self.table_queue.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.table_queue.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_queue.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_queue.setHorizontalHeaderLabels([
            "Mã Lệnh", "Khổ Giấy / Tệp Ảnh", "Máy In Đích", "Bản Sao", "Trạng Thái", "Thời Gian"
        ])
        self.table_queue.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_queue.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_queue.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_queue.verticalHeader().setVisible(False)
        self.table_queue.setMinimumHeight(130)
        self.table_queue.setMaximumHeight(220)
        self.table_queue.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; gridline-color: {COLOR_BORDER_LIGHT}; font-size: 11px; }} "
            f"QHeaderView::section {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-weight: bold; padding: 6px; border: 1px solid {COLOR_BORDER}; font-size: 11px; }} "
            f"QTableWidget::item {{ padding: 6px; color: {COLOR_TEXT_PRIMARY}; border-bottom: 1px solid {COLOR_BORDER_LIGHT}; }}"
        )
        l_queue.addWidget(self.table_queue)

        layout.addWidget(grp_queue)

        # =========================================================================
        # 6. BOTTOM ACTION BAR (NÚT THAO TÁC CHÍNH)
        # =========================================================================
        h_action = QHBoxLayout()
        h_action.setSpacing(12)

        self.btn_test_print = QPushButton("In thử trang test")
        self.btn_test_print.setIcon(get_svg_icon("printer", 16, COLOR_CHAMPAGNE))
        self.btn_test_print.setFixedHeight(40)
        self.btn_test_print.setMinimumWidth(150)
        self.btn_test_print.setCursor(Qt.PointingHandCursor)
        self.btn_test_print.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 8px; padding: 4px 18px; font-weight: 600; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {COLOR_SURFACE_SECONDARY}; border-color: {COLOR_CHAMPAGNE}; }}"
        )
        self.btn_test_print.clicked.connect(self._print_test_page)
        h_action.addWidget(self.btn_test_print)

        h_action.addStretch()

        self.btn_cancel = QPushButton("Hủy thay đổi")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 8px; padding: 4px 18px; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        self.btn_cancel.clicked.connect(self._load_current_settings)
        h_action.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Lưu cài đặt")
        self.btn_save.setIcon(get_svg_icon("save", 16, "#FFFFFF"))
        self.btn_save.setFixedHeight(40)
        self.btn_save.setMinimumWidth(140)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLOR_CHAMPAGNE_LIGHT}, stop:1 {COLOR_CHAMPAGNE}); "
            f"color: #FFFFFF; font-weight: bold; border: 1px solid {COLOR_CHAMPAGNE}; border-radius: 8px; padding: 4px 24px; font-size: 13px; }} "
            f"QPushButton:hover {{ background: {COLOR_CHAMPAGNE_LIGHT}; color: #FFFFFF; }} "
            f"QPushButton:pressed {{ background: {COLOR_CHAMPAGNE}; }}"
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

        # Số bản in (Copies)
        if hasattr(self.print_mgr, "config_mgr") and self.print_mgr.config_mgr:
            copies = int(self.print_mgr.config_mgr.get("printer.default_copies", 1))
            self.spin_copies.setValue(max(1, min(10, copies)))

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
        self.spin_copies.setValue(1)
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
                f"QProgressBar {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; }} "
                f"QProgressBar::chunk {{ background-color: #EF4444; border-radius: 5px; }}"
            )
            self.lbl_paper_stats.setStyleSheet("font-size: 14px; font-weight: bold; color: #EF4444; border: none; background: transparent;")
        else:
            self.prog_paper.setStyleSheet(
                f"QProgressBar {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; }} "
                f"QProgressBar::chunk {{ background-color: {COLOR_CHAMPAGNE}; border-radius: 5px; }}"
            )
            self.lbl_paper_stats.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_TEXT_PRIMARY}; border: none; background: transparent;")

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
            preset_s = PrintPresetRegistry.get_preset_for_printer(p_strip, "2x6")
            m_strip = preset_s.model_name
            if "Generic" in m_strip or "tiêu chuẩn" in m_strip.lower():
                m_strip = "Generic Preset"
            self.lbl_strip_preset.setText(m_strip)
            self.lbl_strip_preset.setToolTip(f"Preset: {preset_s.model_name}")
            cjobs = status_s.get("cjobs", 0)
            self.lbl_strip_detail.setText(f"Spooler: {cjobs} tác vụ đang chờ")
            if status_s.get("is_online", False):
                self.lbl_strip_status.setText("🟢 Sẵn sàng (Ready)")
                self.lbl_strip_status.setStyleSheet("color: #54836A; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            else:
                self.lbl_strip_status.setText(f"🔴 {status_s.get('status_text', 'Mất kết nối')}")
                self.lbl_strip_status.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        else:
            self.lbl_strip_preset.setText("Chưa cấu hình preset")
            self.lbl_strip_detail.setText("Spooler: Không có")
            self.lbl_strip_status.setText("⚪ Chưa chọn máy in")
            self.lbl_strip_status.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")

        # 2. Kiểm tra máy in full
        p_full = self.combo_full.currentData()
        if p_full:
            status_f = WindowsPrintSpooler.get_printer_status(p_full)
            preset_f = PrintPresetRegistry.get_preset_for_printer(p_full, "4x6")
            m_full = preset_f.model_name
            if "Generic" in m_full or "tiêu chuẩn" in m_full.lower():
                m_full = "Generic Preset"
            self.lbl_full_preset.setText(m_full)
            self.lbl_full_preset.setToolTip(f"Preset: {preset_f.model_name}")
            cjobs_f = status_f.get("cjobs", 0)
            self.lbl_full_detail.setText(f"Spooler: {cjobs_f} tác vụ đang chờ")
            if status_f.get("is_online", False):
                self.lbl_full_status.setText("🟢 Sẵn sàng (Ready)")
                self.lbl_full_status.setStyleSheet("color: #54836A; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            else:
                self.lbl_full_status.setText(f"🔴 {status_f.get('status_text', 'Mất kết nối')}")
                self.lbl_full_status.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        else:
            self.lbl_full_preset.setText("Chưa cấu hình preset")
            self.lbl_full_detail.setText("Spooler: Không có")
            self.lbl_full_status.setText("⚪ Chưa chọn máy in")
            self.lbl_full_status.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")

    def _refresh_queue_table(self):
        """Lấy danh sách các tác vụ in từ PrintManager và cập nhật bảng hàng đợi."""
        queue = self.print_mgr.get_queue() if hasattr(self.print_mgr, "get_queue") else []
        self.table_queue.setRowCount(len(queue))

        for row, job in enumerate(queue):
            # Cột 0: Mã Lệnh (Job ID)
            item_id = QTableWidgetItem(str(job.get("job_id", "")))
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 0, item_id)

            # Cột 1: Khổ Giấy / Tệp Ảnh
            paper_sz = job.get("paper_size", "4x6")
            fn = job.get("filename", "") or os.path.basename(job.get("image_path", ""))
            disp_file = f"[{paper_sz}] {fn}" if fn else f"[{paper_sz}] Ảnh chụp Photobooth"
            item_fn = QTableWidgetItem(disp_file)
            self.table_queue.setItem(row, 1, item_fn)

            # Cột 2: Máy In Đích
            p_name = job.get("printer_name", "") or "Mặc định"
            item_pr = QTableWidgetItem(p_name)
            self.table_queue.setItem(row, 2, item_pr)

            # Cột 3: Số Bản Sao
            copies = job.get("copies", 1)
            item_cp = QTableWidgetItem(f"{copies} bản")
            item_cp.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 3, item_cp)

            # Cột 4: Trạng Thái
            st_raw = str(job.get("status", ""))
            st = st_raw.lower()
            if st_raw == STATUS_COMPLETED or "completed" in st or "hoàn thành" in st:
                st_text = "🟢 Hoàn thành"
                st_color = QColor("#54836A")
            elif st_raw in (STATUS_SPOOLING, STATUS_SPOOLED) or "spool" in st or "print" in st or "đang in" in st:
                st_text = "🔵 Đang xử lý"
                st_color = QColor("#0284C7")
            elif st_raw == STATUS_ERROR or "error" in st or "failed" in st or "lỗi" in st:
                err = job.get("error_message")
                st_text = f"🔴 Lỗi ({err})" if err else "🔴 Lỗi in"
                st_color = QColor("#EF4444")
            elif "cancel" in st or "hủy" in st:
                st_text = "⚪ Đã hủy"
                st_color = QColor("#6E6D67")
            else:
                st_text = "🟡 Đang chờ"
                st_color = QColor("#C18A42")

            item_st = QTableWidgetItem(st_text)
            item_st.setForeground(st_color)
            item_st.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 4, item_st)

            # Cột 5: Thời Gian
            t_str = job.get("created_at", "")
            item_time = QTableWidgetItem(t_str)
            item_time.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 5, item_time)

    def _clear_completed_queue(self):
        """Xóa các lệnh in đã hoàn tất khỏi hàng đợi để dọn dẹp bộ nhớ."""
        if hasattr(self.print_mgr, "clear_completed_jobs"):
            cleared = self.print_mgr.clear_completed_jobs()
            self._refresh_queue_table()

    def _on_status_timer_tick(self):
        """Cập nhật định kỳ trạng thái máy in và hàng đợi in."""
        self._check_printer_statuses()
        self._refresh_queue_table()

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

        if hasattr(self.print_mgr, "config_mgr") and self.print_mgr.config_mgr:
            self.print_mgr.config_mgr.set("printer.default_copies", self.spin_copies.value())

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
            self._refresh_queue_table()
        else:
            QMessageBox.warning(
                self, "Lỗi In",
                f"Không thể gửi lệnh in tới '{active_p}'. Vui lòng kiểm tra cáp kết nối và nguồn điện máy in."
            )
