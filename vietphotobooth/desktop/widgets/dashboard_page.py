"""
1998 TEAM PHOTOBOOTH v2.0.0 — OPERATOR DASHBOARD
Buồng lái tác nghiệp trung tâm (Operator Cockpit) theo Concept A Premium Studio.
Tập trung giám sát sự kiện, thiết bị phần cứng đa kênh (Concept C), Live View trung tâm,
và chuyển đổi tức thì sang chế độ khách chụp Kiosk (Concept B).
"""

import os
from typing import Optional
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QRectF
from PySide6.QtGui import QColor, QFont, QPixmap, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QScrollArea, QSizePolicy
)

from vietphotobooth.core.events import EventManager
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport
from vietphotobooth.desktop.icons import (
    COLOR_GOLD, COLOR_GOLD_LIGHT, COLOR_WHITE, COLOR_SLATE,
    COLOR_GREEN, COLOR_RED, COLOR_BLUE, get_svg_icon,
    get_brand_logo_tight_pixmap
)


class DashboardPage(QWidget):
    """
    Buồng Lái Vận Hành (Operator Dashboard) trung tâm cho 1998 TEAM Photobooth v2.0.0.
    """
    start_kiosk_requested = Signal()
    open_studio_requested = Signal()
    open_events_requested = Signal()
    open_templates_requested = Signal()
    open_printing_requested = Signal()
    open_devices_requested = Signal()
    open_qr_requested = Signal()

    def __init__(
        self,
        event_mgr: Optional[EventManager] = None,
        camera_mgr: Optional[CameraManager] = None,
        print_mgr: Optional[PrintManager] = None,
        config_mgr: Optional[ConfigManager] = None,
        frame_mgr=None,
        parent=None
    ):
        super().__init__(parent)
        self.event_mgr = event_mgr
        self.camera_mgr = camera_mgr
        self.print_mgr = print_mgr
        self.config_mgr = config_mgr or ConfigManager()
        self.frame_mgr = frame_mgr

        self._simulated_step = 0
        self._init_ui()
        self._setup_telemetry_timer()

    def _init_ui(self):
        # Thiết lập nền sáng Premium Light Theme cho toàn trang Dashboard
        self.setStyleSheet("DashboardPage { background-color: #F3F4F6; }")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # QScrollArea để đảm bảo đáp ứng mượt mà trên cả 1920x1080 và 1600x900
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: #F3F4F6;
                border: none;
            }
            QScrollBar:vertical {
                background: #F3F4F6;
                width: 8px;
                margin: 0;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #D9DEE7;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #CBD5E1;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 1. Header Bar: Logo thương hiệu chuẩn, Tiêu đề buồng lái & Nút Start Kiosk lớn
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_layout.setContentsMargins(0, 0, 0, 4)

        # Logo 1998 TEAM chuẩn hóa trong suốt bên trái Header
        lbl_brand_logo = QLabel()
        logo_pix = get_brand_logo_tight_pixmap(height=42)
        if not logo_pix.isNull():
            lbl_brand_logo.setPixmap(logo_pix)
        else:
            lbl_brand_logo.setText("1998 TEAM")
            lbl_brand_logo.setStyleSheet("color: #D4AF37; font-weight: 800; font-size: 16px;")
        lbl_brand_logo.setToolTip("1998 TEAM Photobooth")
        header_layout.addWidget(lbl_brand_logo)

        # Tiêu đề & phụ đề
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("BẢNG ĐIỀU KHIỂN VẬN HÀNH")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #1E40AF; letter-spacing: 0.5px;")
        lbl_sub = QLabel("Buồng lái tác nghiệp trung tâm 1998 TEAM — Giám sát sự kiện, thiết bị và hàng đợi")
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        self.btn_start_kiosk = QPushButton("🚀 BẮT ĐẦU PHOTOBOOTH (F11)")
        self.btn_start_kiosk.setFixedHeight(44)
        self.btn_start_kiosk.setCursor(Qt.PointingHandCursor)
        self.btn_start_kiosk.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D4AF37, stop:1 #F5DE88); "
            "color: #070A12; font-size: 13px; font-weight: 800; border-radius: 8px; padding: 0 20px; border: 1px solid #D4AF37; }"
            "QPushButton:hover { background: #FEF9C3; }"
            "QPushButton:pressed { background: #C5A059; }"
        )
        self.btn_start_kiosk.clicked.connect(self.start_kiosk_requested.emit)
        header_layout.addWidget(self.btn_start_kiosk)

        main_layout.addLayout(header_layout)

        # 2. Disclaimer Banner Minh Bạch (Tự co giãn, không clip text, căn giữa icon)
        self.disclaimer_banner = QFrame()
        self.disclaimer_banner.setObjectName("disclaimer_banner")
        self.disclaimer_banner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.disclaimer_banner.setMinimumHeight(44)
        self.disclaimer_banner.setStyleSheet(
            "QFrame#disclaimer_banner { background-color: #FFFBEB; "
            "border: 1.5px solid #FDE68A; border-radius: 8px; }"
        )
        disclaimer_layout = QHBoxLayout(self.disclaimer_banner)
        disclaimer_layout.setContentsMargins(14, 8, 14, 8)
        disclaimer_layout.setSpacing(12)

        lbl_warn_icon = QLabel("⚠️")
        lbl_warn_icon.setObjectName("lbl_disclaimer_icon")
        lbl_warn_icon.setStyleSheet("font-size: 15px; background: transparent; border: none;")
        lbl_warn_icon.setAlignment(Qt.AlignCenter)

        self.lbl_disclaimer_text = QLabel(
            "<b>BUỒNG LÁI VẬN HÀNH 1998 TEAM:</b> Dữ liệu phiên, bản in và telemetry phần cứng "
            "được biểu diễn ở chế độ <b>[DEMO / SIMULATED]</b> nhằm xác thực trải nghiệm UI/UX. "
            "Camera engine thực tế tuân thủ driver Windows WPD và Nikon MAID3 SDK."
        )
        self.lbl_disclaimer_text.setObjectName("lbl_disclaimer_text")
        self.lbl_disclaimer_text.setStyleSheet("font-size: 11.5px; color: #92400E; background: transparent; border: none;")
        self.lbl_disclaimer_text.setWordWrap(True)
        self.lbl_disclaimer_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        disclaimer_layout.addWidget(lbl_warn_icon, 0, Qt.AlignVCenter)
        disclaimer_layout.addWidget(self.lbl_disclaimer_text, 1, Qt.AlignVCenter)
        main_layout.addWidget(self.disclaimer_banner)

        # 3. 4 Stat Cards Đồng Nhất Chiều Cao và Baseline
        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)
        for c in range(4):
            stats_grid.setColumnStretch(c, 1)

        # Card 1: Sự kiện hoạt động
        evt_name = self.event_mgr.current_event if self.event_mgr else "Đám Cưới Minh & Linh"
        card1 = self._create_stat_card("📅", "#3B82F6", "SỰ KIỆN HOẠT ĐỘNG", evt_name, "📍 White Palace, TP.HCM", is_demo=False)
        stats_grid.addWidget(card1, 0, 0)

        # Card 2: Phiên đã chụp
        card2 = self._create_stat_card("📸", "#10B981", "PHIÊN ĐÃ CHỤP", "64", "Hôm nay: +64 lượt khách", is_demo=True)
        stats_grid.addWidget(card2, 0, 1)

        # Card 3: Bản in thành phẩm
        card3 = self._create_stat_card("🖨️", "#F59E0B", "BẢN IN THÀNH PHẨM", "128", "100% bản in hoàn tất", is_demo=True)
        stats_grid.addWidget(card3, 0, 2)

        # Card 4: Giấy in còn lại
        card4 = self._create_paper_stat_card("📜", "#EC4899", "GIẤY IN CÒN LẠI (DNP)", 486, 700)
        stats_grid.addWidget(card4, 0, 3)

        main_layout.addLayout(stats_grid)

        # 4. Cockpit Split 2 Panels: Cột Trái (Live View & Telemetry) | Cột Phải (Khung Ảnh & Thao Tác)
        split_layout = QHBoxLayout()
        split_layout.setSpacing(16)

        # --- CỘT TRÁI: Trạng thái phần cứng Concept C & Live View ---
        left_panel = QFrame()
        left_panel.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1.5px solid #D9DEE7; border-radius: 12px; }"
        )
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(12)

        panel_top = QHBoxLayout()
        lbl_hw_title = QLabel("⚡ TRẠNG THÁI PHẦN CỨNG (CONCEPT C MULTI-CHANNEL)")
        lbl_hw_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1E40AF; letter-spacing: 0.5px;")
        panel_top.addWidget(lbl_hw_title)
        panel_top.addStretch()

        btn_cycle = QPushButton("🔄 Thử Trạng Thái")
        btn_cycle.setCursor(Qt.PointingHandCursor)
        btn_cycle.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #303746; border: 1.5px solid #D9DEE7; "
            "border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background: #F8FAFC; border-color: #D4AF37; color: #1E40AF; }"
        )
        btn_cycle.clicked.connect(self._cycle_simulated_state)
        panel_top.addWidget(btn_cycle)
        left_layout.addLayout(panel_top)

        # 3 Multi-channel Status Pills với chiều rộng và chiều cao đồng đều
        self.status_row = QHBoxLayout()
        self.status_row.setSpacing(10)

        self.pill_cam = self._create_status_pill("MÁY ẢNH (NIKON D780)", "Nikon D780 (92% Pin [MOCK])", "CONNECTED", "✓", "#10B981")
        self.pill_prn = self._create_status_pill("MÁY IN NHIỆT (DNP)", "DNP DS-RX1HS (486 Giấy [SIM])", "READY", "✓", "#10B981")
        self.pill_net = self._create_status_pill("MẠNG NỘI BỘ (LAN)", "192.168.4.1:8080 (4 Khách [SIM])", "ONLINE", "✓", "#3B82F6")

        self.status_row.addWidget(self.pill_cam, 1)
        self.status_row.addWidget(self.pill_prn, 1)
        self.status_row.addWidget(self.pill_net, 1)
        left_layout.addLayout(self.status_row)

        # Live View Preview Viewport
        self.viewport = CameraLiveViewport(self)
        self.viewport.setFixedHeight(260)
        self.viewport.set_face_eye_af_state("AF-S (Face/Eye AF Tracking [SIMULATED])")
        left_layout.addWidget(self.viewport)

        # Action toolbar dưới Live View
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        btn_test_shot = QPushButton("📸 Test Chụp Thử")
        btn_test_shot.setCursor(Qt.PointingHandCursor)
        btn_test_shot.setStyleSheet(self._action_btn_style())
        btn_test_shot.clicked.connect(self._on_test_capture)
        toolbar.addWidget(btn_test_shot)

        btn_test_prn = QPushButton("🖨️ Test In Thử")
        btn_test_prn.setCursor(Qt.PointingHandCursor)
        btn_test_prn.setStyleSheet(self._action_btn_style())
        btn_test_prn.clicked.connect(self._on_test_print)
        toolbar.addWidget(btn_test_prn)

        btn_open_devices = QPushButton("📡 Giám Sát Cảm Biến")
        btn_open_devices.setCursor(Qt.PointingHandCursor)
        btn_open_devices.setStyleSheet(self._action_btn_style())
        btn_open_devices.clicked.connect(self.open_devices_requested.emit)
        toolbar.addWidget(btn_open_devices)

        btn_open_qr = QPushButton("📲 Chia Sẻ QR")
        btn_open_qr.setCursor(Qt.PointingHandCursor)
        btn_open_qr.setStyleSheet(self._action_btn_style())
        btn_open_qr.clicked.connect(self.open_qr_requested.emit)
        toolbar.addWidget(btn_open_qr)

        toolbar.addStretch()

        btn_open_studio = QPushButton("🔍 Mở Toàn Bộ Studio")
        btn_open_studio.setCursor(Qt.PointingHandCursor)
        btn_open_studio.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D4AF37, stop:1 #F5DE88); color: #070A12; font-weight: 700; "
            "border-radius: 6px; padding: 0 14px; height: 36px; font-size: 12px; border: 1px solid #D4AF37; }"
            "QPushButton:hover { background: #FEF9C3; }"
        )
        btn_open_studio.clicked.connect(self.open_studio_requested.emit)
        toolbar.addWidget(btn_open_studio)

        left_layout.addLayout(toolbar)
        split_layout.addWidget(left_panel, 3)

        # --- CỘT PHẢI: Khung ảnh đang dùng & Thao tác nhanh ---
        right_panel = QFrame()
        right_panel.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1.5px solid #D9DEE7; border-radius: 12px; }"
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(14)

        right_top = QHBoxLayout()
        lbl_tpl_title = QLabel("🎨 KHUNG ẢNH ĐANG ÁP DỤNG")
        lbl_tpl_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1E40AF; letter-spacing: 0.5px;")
        right_top.addWidget(lbl_tpl_title)
        right_top.addStretch()

        btn_change_tpl = QPushButton("Thay Đổi Khung")
        btn_change_tpl.setCursor(Qt.PointingHandCursor)
        btn_change_tpl.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #303746; border: 1.5px solid #D9DEE7; "
            "border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background: #F8FAFC; border-color: #D4AF37; color: #1E40AF; }"
        )
        btn_change_tpl.clicked.connect(self.open_templates_requested.emit)
        right_top.addWidget(btn_change_tpl)
        right_layout.addLayout(right_top)

        # Card Template chi tiết với hình minh họa vector chuẩn hóa
        tpl_card = QFrame()
        tpl_card.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1.5px solid #D9DEE7; border-radius: 8px; padding: 12px; }"
        )
        tpl_layout = QHBoxLayout(tpl_card)
        tpl_layout.setContentsMargins(10, 10, 10, 10)
        tpl_layout.setSpacing(14)

        # Thumb preview vector sạch không phụ thuộc file ảnh mẫu bên ngoài
        lbl_thumb = QLabel()
        lbl_thumb.setFixedSize(90, 130)
        lbl_thumb.setAlignment(Qt.AlignCenter)
        lbl_thumb.setPixmap(self._create_template_thumbnail_pixmap(90, 130))
        tpl_layout.addWidget(lbl_thumb)

        tpl_meta = QVBoxLayout()
        tpl_meta.setSpacing(6)
        lbl_m_title = QLabel("Hàn Quốc 4 Ô Dọc (Life4Cuts)")
        lbl_m_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #303746;")
        lbl_m_desc = QLabel("Khung 4 ô chuẩn Hàn Quốc với 4 tư thế độc lập, hỗ trợ chụp lại từng ô con (Slot Retake).")
        lbl_m_desc.setStyleSheet("font-size: 11px; color: #64748B; line-height: 1.3;")
        lbl_m_desc.setWordWrap(True)

        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        tag1 = QLabel("🌸 4 Ô Chuẩn")
        tag1.setStyleSheet("background: #EDF2F7; color: #303746; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;")
        tag2 = QLabel("4 Ô ẢNH RIÊNG")
        tag2.setStyleSheet("background: rgba(225,29,72,0.15); color: #E11D48; border: 1px solid rgba(225,29,72,0.3); padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        tag3 = QLabel("2x6 inch")
        tag3.setStyleSheet("background: #EDF2F7; color: #303746; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;")
        tags_layout.addWidget(tag1)
        tags_layout.addWidget(tag2)
        tags_layout.addWidget(tag3)
        tags_layout.addStretch()

        tpl_meta.addWidget(lbl_m_title)
        tpl_meta.addWidget(lbl_m_desc)
        tpl_meta.addLayout(tags_layout)
        tpl_layout.addLayout(tpl_meta)

        right_layout.addWidget(tpl_card)

        # Ghi chú sự kiện
        note_box = QFrame()
        note_box.setStyleSheet("QFrame { background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 8px; padding: 10px; }")
        note_l = QVBoxLayout(note_box)
        note_l.setContentsMargins(10, 8, 10, 8)
        note_l.setSpacing(4)
        lbl_n_title = QLabel("GHI CHÚ SỰ KIỆN:")
        lbl_n_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #D97706; letter-spacing: 0.5px;")
        lbl_n_desc = QLabel("Sự kiện tiệc cưới lãng mạn. Khách thích chụp dải 4 ô dọc lấy liền 2 bản.")
        lbl_n_desc.setStyleSheet("font-size: 11px; color: #92400E;")
        note_l.addWidget(lbl_n_title)
        note_l.addWidget(lbl_n_desc)
        right_layout.addWidget(note_box)

        right_layout.addStretch()

        # Nút Chuyển sang Kiosk
        btn_switch_kiosk = QPushButton("⚡ CHUYỂN SANG CHẾ ĐỘ KHÁCH CHỤP (KIOSK)")
        btn_switch_kiosk.setFixedHeight(50)
        btn_switch_kiosk.setCursor(Qt.PointingHandCursor)
        btn_switch_kiosk.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D4AF37, stop:1 #F5DE88); "
            "color: #070A12; font-size: 13px; font-weight: 800; border-radius: 8px; border: 1px solid #D4AF37; letter-spacing: 0.5px; }"
            "QPushButton:hover { background: #FEF9C3; }"
            "QPushButton:pressed { background: #C5A059; }"
        )
        btn_switch_kiosk.clicked.connect(self.start_kiosk_requested.emit)
        right_layout.addWidget(btn_switch_kiosk)

        split_layout.addWidget(right_panel, 2)
        main_layout.addLayout(split_layout)

        self.scroll_area.setWidget(content_widget)
        outer_layout.addWidget(self.scroll_area)

    def _create_stat_card(self, icon: str, color_hex: str, label: str, value: str, meta: str, is_demo: bool = False) -> QFrame:
        """Tạo Stat Card với chiều cao cố định 104px và cấu trúc căn chỉnh thống nhất phong cách Light Theme."""
        card = QFrame()
        card.setFixedHeight(104)
        card.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1.5px solid #D9DEE7; border-radius: 10px; }"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        # Hộp chứa biểu tượng kích thước 42x42px
        icon_box = QFrame()
        icon_box.setFixedSize(42, 42)
        icon_box.setStyleSheet(
            f"QFrame {{ background-color: {color_hex}15; border: 1px solid {color_hex}35; border-radius: 8px; }}"
        )
        ib_layout = QVBoxLayout(icon_box)
        ib_layout.setContentsMargins(0, 0, 0, 0)
        ib_layout.setAlignment(Qt.AlignCenter)
        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 20px;")
        ib_layout.addWidget(lbl_icon)
        layout.addWidget(icon_box)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        lbl_tag = QHBoxLayout()
        lbl_tag.setSpacing(6)
        lbl_l = QLabel(label)
        lbl_l.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;")
        lbl_tag.addWidget(lbl_l)
        if is_demo:
            pill = QLabel("DEMO")
            pill.setStyleSheet(
                "background: rgba(245, 158, 11, 0.15); color: #B45309; "
                "border: 1px solid rgba(245, 158, 11, 0.35); font-size: 9px; font-weight: 800; "
                "padding: 1px 4px; border-radius: 3px;"
            )
            lbl_tag.addWidget(pill)
        lbl_tag.addStretch()
        text_col.addLayout(lbl_tag)

        lbl_v = QLabel(value)
        lbl_v.setStyleSheet("font-size: 20px; font-weight: 800; color: #1E40AF;")
        text_col.addWidget(lbl_v)

        lbl_m = QLabel(meta)
        lbl_m.setStyleSheet("font-size: 11px; color: #64748B;")
        text_col.addWidget(lbl_m)

        layout.addLayout(text_col)
        return card

    def _create_paper_stat_card(self, icon: str, color_hex: str, label: str, remaining: int, total: int) -> QFrame:
        """Tạo Stat Card giám sát giấy in với chiều cao cố định 104px đồng bộ hoàn hảo với các Card khác."""
        card = QFrame()
        card.setFixedHeight(104)
        card.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1.5px solid #D9DEE7; border-radius: 10px; }"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        icon_box = QFrame()
        icon_box.setFixedSize(42, 42)
        icon_box.setStyleSheet(
            f"QFrame {{ background-color: {color_hex}15; border: 1px solid {color_hex}35; border-radius: 8px; }}"
        )
        ib_layout = QVBoxLayout(icon_box)
        ib_layout.setContentsMargins(0, 0, 0, 0)
        ib_layout.setAlignment(Qt.AlignCenter)
        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 20px;")
        ib_layout.addWidget(lbl_icon)
        layout.addWidget(icon_box)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        lbl_tag = QHBoxLayout()
        lbl_tag.setSpacing(6)
        lbl_l = QLabel(label)
        lbl_l.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;")
        lbl_tag.addWidget(lbl_l)
        pill = QLabel("SIMULATED")
        pill.setStyleSheet(
            "background: rgba(245, 158, 11, 0.15); color: #B45309; "
            "border: 1px solid rgba(245, 158, 11, 0.35); font-size: 9px; font-weight: 800; "
            "padding: 1px 4px; border-radius: 3px;"
        )
        lbl_tag.addWidget(pill)
        lbl_tag.addStretch()
        text_col.addLayout(lbl_tag)

        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        lbl_v = QLabel(f"{remaining} <span style='font-size: 12px; font-weight: 400; color: #64748B;'>/ {total}</span>")
        lbl_v.setStyleSheet("font-size: 20px; font-weight: 800; color: #1E40AF;")
        val_row.addWidget(lbl_v)
        pct = int(remaining / total * 100)
        lbl_pct = QLabel(f"({pct}%)")
        lbl_pct.setStyleSheet("font-size: 12px; font-weight: 700; color: #EC4899;")
        val_row.addWidget(lbl_pct)
        val_row.addStretch()
        text_col.addLayout(val_row)

        bar = QProgressBar()
        bar.setRange(0, total)
        bar.setValue(remaining)
        bar.setTextVisible(False)
        bar.setFixedHeight(4)
        bar.setStyleSheet(
            "QProgressBar { background-color: #E2E8F0; border-radius: 2px; } "
            "QProgressBar::chunk { background-color: #EC4899; border-radius: 2px; }"
        )
        text_col.addWidget(bar)

        lbl_m = QLabel("Dung lượng cuộn nạp chính [SIMULATED]")
        lbl_m.setStyleSheet("font-size: 11px; color: #64748B;")
        text_col.addWidget(lbl_m)

        layout.addLayout(text_col)
        return card

    def _create_status_pill(self, title: str, subtitle: str, state_text: str, icon: str, color_hex: str) -> QFrame:
        """Tạo Pill trạng thái phần sang trọng, đồng nhất chiều cao 56px."""
        pill = QFrame()
        pill.setFixedHeight(56)
        pill.setStyleSheet(
            f"QFrame {{ background: #F8FAFC; border: 1.5px solid {color_hex}60; border-radius: 8px; }}"
        )
        layout = QHBoxLayout(pill)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B;")
        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet("font-size: 11px; font-weight: 600; color: #303746;")
        text_col.addWidget(lbl_t)
        text_col.addWidget(lbl_s)
        layout.addLayout(text_col, 1)

        badge = QLabel(f"{icon} {state_text}")
        badge.setStyleSheet(
            f"background: {color_hex}20; color: {color_hex}; border: 1px solid {color_hex}50; "
            f"border-radius: 4px; font-size: 10px; font-weight: 800; padding: 4px 8px;"
        )
        layout.addWidget(badge)

        return pill

    def _create_template_thumbnail_pixmap(self, width: int = 90, height: int = 130) -> QPixmap:
        """Tạo hình thumbnail vector sắc nét cho khung ảnh dải 4 ô phong cách Photobooth."""
        pix = QPixmap(width, height)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        # Nền giấy khung photostrip cao cấp
        painter.setPen(QPen(QColor("#D9DEE7"), 1.5))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawRoundedRect(QRectF(1, 1, width - 2, height - 2), 6, 6)

        # 4 ô ảnh nhỏ
        slot_w = width - 16
        slot_h = 22
        x = 8
        painter.setFont(QFont("Arial", 7, QFont.Bold))

        for i in range(4):
            y = 7 + i * 26
            painter.setPen(QPen(QColor("#CBD5E1"), 1))
            painter.setBrush(QBrush(QColor("#F1F5F9")))
            painter.drawRoundedRect(QRectF(x, y, slot_w, slot_h), 3, 3)

            painter.setPen(QPen(QColor("#1E40AF")))
            painter.drawText(QRectF(x, y, slot_w, slot_h), Qt.AlignCenter, f"Ô #{i+1}")

        # Chữ ký thương hiệu chân khung
        painter.setPen(QPen(QColor("#D4AF37")))
        painter.setFont(QFont("Arial", 6, QFont.Bold))
        painter.drawText(QRectF(0, height - 16, width, 12), Qt.AlignCenter, "1998 TEAM")

        painter.end()
        return pix

    def _action_btn_style(self) -> str:
        return (
            "QPushButton { background: #FFFFFF; color: #303746; border: 1.5px solid #D9DEE7; "
            "border-radius: 6px; padding: 0 14px; height: 36px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #FEF9C3; color: #1E40AF; border-color: #D4AF37; }"
            "QPushButton:pressed { background: #E2E8F0; }"
        )

    def _setup_telemetry_timer(self):
        # Polling nhẹ nhàng để cập nhật live view và status nếu có camera
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._on_telemetry_tick)

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def _on_telemetry_tick(self):
        if not self.camera_mgr:
            return
        # Lấy frame nếu camera đang chạy live view
        frame = self.camera_mgr.get_liveview_rgb() if hasattr(self.camera_mgr, "get_liveview_rgb") else None
        if frame is not None:
            # Đã có frame thực tế
            self.viewport.set_frame_rgb(frame)

    def _cycle_simulated_state(self):
        """Mô phỏng chuyển đổi chu kỳ trạng thái phần cứng Concept C để demo trải nghiệm."""
        states = [
            ("Nikon D780 (92% Pin [MOCK])", "CONNECTED", "✓", "#10B981"),
            ("Nikon D780 (Đang lấy nét [MOCK])", "BUSY", "⏳", "#F59E0B"),
            ("Nikon D780 (Mất kết nối USB [MOCK])", "DISCONNECTED", "✕", "#EF4444"),
        ]
        self._simulated_step = (self._simulated_step + 1) % len(states)
        sub, st, ic, col = states[self._simulated_step]
        # Cập nhật pill máy ảnh
        self.pill_cam.setStyleSheet(
            f"QFrame {{ background: #0F172A; border: 1px solid {col}40; border-radius: 8px; }}"
        )

    def _on_test_capture(self):
        if self.camera_mgr:
            try:
                self.camera_mgr.trigger_autofocus()
            except Exception:
                pass

    def _on_test_print(self):
        pass
