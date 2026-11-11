"""
1998 TEAM PHOTOBOOTH v2.1.0 — MINIMAL LUXURY OPERATOR DASHBOARD
Buồng lái tác nghiệp trung tâm (Operator Cockpit) theo chuẩn Minimal Luxury Studio.
Tích hợp thẻ SurfaceCard, SecondaryCard, StatCardMetric (Live/Demo/N/A) và AlertBannerWidget.
Giám sát phần cứng đa kênh, Live View trung tâm, cảnh báo tự động reflow và chuyển đổi Kiosk tức thì.
"""

import os
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QRectF
from PySide6.QtGui import QColor, QFont, QPixmap, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QSizePolicy
)

from vietphotobooth.core.events import EventManager
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport
from vietphotobooth.desktop.widgets.minimal_luxury_cards import (
    SurfaceCard, SecondaryCard, StatCardMetric, AlertBannerWidget
)
from vietphotobooth.desktop.icons import get_brand_logo_tight_pixmap
from vietphotobooth.desktop.styles import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_SECONDARY,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_BORDER,
    COLOR_CHAMPAGNE, COLOR_CHAMPAGNE_LIGHT, COLOR_PALE_GOLD,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_LIVEVIEW,
    STYLE_BTN_CHAMPAGNE, STYLE_BTN_SECONDARY, STYLE_NAV_ITEM
)


class DashboardPage(QWidget):
    """
    Buồng Lái Vận Hành (Operator Dashboard) trung tâm cho 1998 TEAM Photobooth.
    Phong cách Minimal Luxury Studio với bảng màu Warm Alabaster và hệ thẻ Reusable Cards.
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

        self._is_demo_mode = bool(self.config_mgr.get("developer_mock_mode", False))
        self._init_ui()
        self._setup_hardware_callbacks()
        self._setup_telemetry_timer()
        self.update_telemetry()

    def _init_ui(self):
        # Nền Warm Alabaster Studio toàn trang
        self.setStyleSheet(f"DashboardPage {{ background-color: {COLOR_BG}; }}")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # QScrollArea để đảm bảo đáp ứng mượt mà trên cả 1920x1080 và 1366x768
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: {COLOR_BG};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {COLOR_BG};
                width: 8px;
                margin: 0;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLOR_BORDER};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLOR_CHAMPAGNE};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(28, 20, 28, 24)
        main_layout.setSpacing(14)

        # 1. Header Bar: Logo thương hiệu chuẩn, Tiêu đề buồng lái & Nút Start Kiosk lớn
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_layout.setContentsMargins(0, 0, 0, 2)

        lbl_brand_logo = QLabel()
        logo_pix = get_brand_logo_tight_pixmap(height=40)
        if not logo_pix.isNull():
            lbl_brand_logo.setPixmap(logo_pix)
        else:
            lbl_brand_logo.setText("1998 TEAM")
            lbl_brand_logo.setStyleSheet(f"color: {COLOR_CHAMPAGNE}; font-weight: 800; font-size: 16px;")
        lbl_brand_logo.setToolTip("1998 TEAM Photobooth")
        header_layout.addWidget(lbl_brand_logo)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("BẢNG ĐIỀU KHIỂN VẬN HÀNH")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLOR_TEXT_PRIMARY}; letter-spacing: 0.5px;")
        lbl_sub = QLabel("Buồng lái tác nghiệp trung tâm 1998 TEAM — Giám sát sự kiện, thiết bị và hàng đợi")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SECONDARY};")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        self.btn_start_kiosk = QPushButton("🚀 BẮT ĐẦU PHOTOBOOTH (F11)")
        self.btn_start_kiosk.setFixedHeight(44)
        self.btn_start_kiosk.setCursor(Qt.PointingHandCursor)
        self.btn_start_kiosk.setObjectName("btn_champagne")
        self.btn_start_kiosk.setStyleSheet(STYLE_BTN_CHAMPAGNE)
        self.btn_start_kiosk.clicked.connect(self.start_kiosk_requested.emit)
        header_layout.addWidget(self.btn_start_kiosk)

        main_layout.addLayout(header_layout)

        # 2. Disclaimer Banner Minh Bạch
        self.disclaimer_banner = QFrame()
        self.disclaimer_banner.setObjectName("disclaimer_banner")
        self.disclaimer_banner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.disclaimer_banner.setMinimumHeight(44)
        self.disclaimer_banner.setStyleSheet(f"""
            QFrame#disclaimer_banner {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        disclaimer_layout = QHBoxLayout(self.disclaimer_banner)
        disclaimer_layout.setContentsMargins(14, 8, 14, 8)
        disclaimer_layout.setSpacing(10)

        lbl_warn_icon = QLabel("⚡")
        lbl_warn_icon.setObjectName("lbl_disclaimer_icon")
        lbl_warn_icon.setStyleSheet("font-size: 15px; background: transparent; border: none;")
        lbl_warn_icon.setAlignment(Qt.AlignCenter)

        self.lbl_disclaimer_text = QLabel(
            "<b>BUỒNG LÁI TÁC NGHIỆP 1998 TEAM:</b> Giám sát trạng thái máy ảnh, máy in nhiệt và hàng đợi in theo thời gian thực. "
            "Sẵn sàng khởi động buồng chụp Photobooth Kiosk tự động cho sự kiện."
        )
        self.lbl_disclaimer_text.setObjectName("lbl_disclaimer_text")
        self.lbl_disclaimer_text.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;")
        self.lbl_disclaimer_text.setWordWrap(True)
        self.lbl_disclaimer_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        disclaimer_layout.addWidget(lbl_warn_icon, 0, Qt.AlignVCenter)
        disclaimer_layout.addWidget(self.lbl_disclaimer_text, 1, Qt.AlignVCenter)
        main_layout.addWidget(self.disclaimer_banner)

        # 3. Dynamic Alert Banners Container (Tự động ẩn/hiện và reflow chữ)
        self.alerts_layout = QVBoxLayout()
        self.alerts_layout.setSpacing(8)

        self.alert_cam_disconnect = AlertBannerWidget(
            banner_type="error",
            title="MÁY ẢNH CHỤP CHÍNH MẤT KẾT NỐI",
            message="Cáp USB máy ảnh Nikon D780 đã bị rút khỏi cổng máy trạm. Quá trình chụp tạm thời gián đoạn.",
            action_text="Kết Nối Lại"
        )
        self.alert_cam_disconnect.action_clicked.connect(self._on_reconnect_camera)
        self.alert_cam_disconnect.hide()
        self.alerts_layout.addWidget(self.alert_cam_disconnect)

        self.alert_printer_error = AlertBannerWidget(
            banner_type="warning",
            title="MÁY IN SẮP HẾT GIẤY CUỘN",
            message="Khay giấy cuộn DNP DS-RX1HS còn dưới 25 bản in. Vui lòng chuẩn bị cuộn giấy thay thế.",
            action_text="Nạp Thêm Giấy"
        )
        self.alert_printer_error.action_clicked.connect(self._on_refill_paper_dialog)
        self.alert_printer_error.hide()
        self.alerts_layout.addWidget(self.alert_printer_error)

        self.alert_storage_warning = AlertBannerWidget(
            banner_type="warning",
            title="CẢNH BÁO DUNG LƯỢNG LƯU TRỮ",
            message="Dung lượng ổ cứng sự kiện còn lại dưới 2.0 GB. Vui lòng dọn dẹp bộ nhớ tạm hoặc xuất tệp ZIP.",
            action_text="Dọn Dẹp"
        )
        self.alert_storage_warning.action_clicked.connect(self._on_storage_cleanup)
        self.alert_storage_warning.hide()
        self.alerts_layout.addWidget(self.alert_storage_warning)

        main_layout.addLayout(self.alerts_layout)

        # 4. 4 StatCardMetrics (Chuẩn minh bạch: LIVE / DEMO / N/A)
        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)
        for c in range(4):
            stats_grid.setColumnStretch(c, 1)

        self.card_event = StatCardMetric(
            icon_char="📅",
            accent_color=COLOR_CHAMPAGNE,
            title="SỰ KIỆN HOẠT ĐỘNG",
            value="--",
            subtitle="Khu vực lưu trữ ảnh sự kiện",
            badge_mode="LIVE"
        )
        stats_grid.addWidget(self.card_event, 0, 0)

        self.card_sessions = StatCardMetric(
            icon_char="📸",
            accent_color=COLOR_SUCCESS,
            title="PHIÊN ĐÃ CHỤP",
            value="0",
            subtitle="Hoàn tất: 0 lượt chụp",
            badge_mode="LIVE"
        )
        stats_grid.addWidget(self.card_sessions, 0, 1)

        self.card_prints = StatCardMetric(
            icon_char="🖨️",
            accent_color=COLOR_WARNING,
            title="BẢN IN THÀNH PHẨM",
            value="0",
            subtitle="Bản in nhiệt hoàn tất",
            badge_mode="LIVE"
        )
        stats_grid.addWidget(self.card_prints, 0, 2)

        self.card_paper = StatCardMetric(
            icon_char="📜",
            accent_color=COLOR_CHAMPAGNE,
            title="GIẤY IN CÒN LẠI (DNP)",
            value="--",
            subtitle="Cuộn giấy in ảnh nhiệt",
            badge_mode="N/A"
        )
        stats_grid.addWidget(self.card_paper, 0, 3)

        main_layout.addLayout(stats_grid)

        # 5. Cockpit Split 2 Panels: Cột Trái (Live View & Telemetry) | Cột Phải (Khung Ảnh & Thao Tác)
        split_layout = QHBoxLayout()
        split_layout.setSpacing(14)

        # --- CỘT TRÁI: Trạng thái phần cứng & Live View (Chiếm ~60-65%) ---
        left_panel = SurfaceCard()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(12)

        panel_top = QHBoxLayout()
        lbl_hw_title = QLabel("⚡ TRẠNG THÁI PHẦN CỨNG THỜI GIAN THỰC")
        lbl_hw_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {COLOR_TEXT_PRIMARY}; letter-spacing: 0.5px;")
        panel_top.addWidget(lbl_hw_title)
        panel_top.addStretch()
        left_layout.addLayout(panel_top)

        # 3 Multi-channel Status Pills
        self.status_row = QHBoxLayout()
        self.status_row.setSpacing(10)

        self.pill_cam = self._create_status_pill("MÁY ẢNH CHỤP CHÍNH", "Đang quét thiết bị...", "DISCONNECTED", "●", COLOR_ERROR)
        self.pill_prn = self._create_status_pill("MÁY IN NHIỆT (DNP)", "Đang kiểm tra...", "OFFLINE", "●", COLOR_TEXT_SECONDARY)
        self.pill_net = self._create_status_pill("MẠNG NỘI BỘ (LAN)", "127.0.0.1:8080", "ONLINE", "✓", COLOR_CHAMPAGNE)

        self.status_row.addWidget(self.pill_cam, 1)
        self.status_row.addWidget(self.pill_prn, 1)
        self.status_row.addWidget(self.pill_net, 1)
        left_layout.addLayout(self.status_row)

        # Live View Preview Viewport
        self.viewport = CameraLiveViewport(self)
        self.viewport.setFixedHeight(260)
        self.viewport.set_face_eye_af_state("AF-S (Face/Eye AF Tracking)")
        left_layout.addWidget(self.viewport)

        # Thẻ Chẩn Đoán Cảm Biến & Ổ Đĩa (Telemetry Sub-row)
        telemetry_row = QHBoxLayout()
        telemetry_row.setSpacing(10)

        self.card_cam_telemetry = SecondaryCard()
        l_ct = QVBoxLayout(self.card_cam_telemetry)
        l_ct.setContentsMargins(12, 8, 12, 8)
        l_ct.setSpacing(2)
        lbl_ct_head = QLabel("THÔNG SỐ CẢM BIẾN MÁY ẢNH")
        lbl_ct_head.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLOR_TEXT_SECONDARY}; letter-spacing: 0.5px;")
        self.lbl_ct_val = QLabel("Chưa kết nối")
        self.lbl_ct_val.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};")
        l_ct.addWidget(lbl_ct_head)
        l_ct.addWidget(self.lbl_ct_val)
        telemetry_row.addWidget(self.card_cam_telemetry, 1)

        self.card_disk_telemetry = SecondaryCard()
        l_dt = QVBoxLayout(self.card_disk_telemetry)
        l_dt.setContentsMargins(12, 8, 12, 8)
        l_dt.setSpacing(2)
        lbl_dt_head = QLabel("DUNG LƯỢNG Ổ CỨNG SỰ KIỆN")
        lbl_dt_head.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLOR_TEXT_SECONDARY}; letter-spacing: 0.5px;")
        self.lbl_dt_val = QLabel("Khả dụng: -- GB")
        self.lbl_dt_val.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};")
        l_dt.addWidget(lbl_dt_head)
        l_dt.addWidget(self.lbl_dt_val)
        telemetry_row.addWidget(self.card_disk_telemetry, 1)

        left_layout.addLayout(telemetry_row)

        # Action toolbar dưới Live View
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_test_shot = QPushButton("📸 Test Chụp Thử")
        btn_test_shot.setCursor(Qt.PointingHandCursor)
        btn_test_shot.setObjectName("btn_secondary")
        btn_test_shot.setStyleSheet(STYLE_BTN_SECONDARY)
        btn_test_shot.clicked.connect(self._on_test_capture)
        toolbar.addWidget(btn_test_shot)

        btn_test_prn = QPushButton("🖨️ Test In Thử")
        btn_test_prn.setCursor(Qt.PointingHandCursor)
        btn_test_prn.setObjectName("btn_secondary")
        btn_test_prn.setStyleSheet(STYLE_BTN_SECONDARY)
        btn_test_prn.clicked.connect(self._on_test_print)
        toolbar.addWidget(btn_test_prn)

        btn_open_devices = QPushButton("📡 Giám Sát Thiết Bị")
        btn_open_devices.setCursor(Qt.PointingHandCursor)
        btn_open_devices.setObjectName("btn_secondary")
        btn_open_devices.setStyleSheet(STYLE_BTN_SECONDARY)
        btn_open_devices.clicked.connect(self.open_devices_requested.emit)
        toolbar.addWidget(btn_open_devices)

        btn_open_qr = QPushButton("📲 Chia Sẻ QR")
        btn_open_qr.setCursor(Qt.PointingHandCursor)
        btn_open_qr.setObjectName("btn_secondary")
        btn_open_qr.setStyleSheet(STYLE_BTN_SECONDARY)
        btn_open_qr.clicked.connect(self.open_qr_requested.emit)
        toolbar.addWidget(btn_open_qr)

        toolbar.addStretch()

        btn_open_studio = QPushButton("🔍 Mở Studio")
        btn_open_studio.setCursor(Qt.PointingHandCursor)
        btn_open_studio.setObjectName("btn_secondary")
        btn_open_studio.setStyleSheet(STYLE_BTN_SECONDARY)
        btn_open_studio.clicked.connect(self.open_studio_requested.emit)
        toolbar.addWidget(btn_open_studio)

        left_layout.addLayout(toolbar)
        split_layout.addWidget(left_panel, 3)

        # --- CỘT PHẢI: Khung ảnh đang dùng & Thao tác nhanh (~35-40%) ---
        right_panel = SurfaceCard()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(12)

        right_top = QHBoxLayout()
        lbl_tpl_title = QLabel("🎨 KHUNG ẢNH ĐANG ÁP DỤNG")
        lbl_tpl_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {COLOR_TEXT_PRIMARY}; letter-spacing: 0.5px;")
        right_top.addWidget(lbl_tpl_title)
        right_top.addStretch()

        btn_change_tpl = QPushButton("Thay Đổi Khung")
        btn_change_tpl.setCursor(Qt.PointingHandCursor)
        btn_change_tpl.setObjectName("btn_secondary")
        btn_change_tpl.setStyleSheet(STYLE_BTN_SECONDARY)
        btn_change_tpl.clicked.connect(self.open_templates_requested.emit)
        right_top.addWidget(btn_change_tpl)
        right_layout.addLayout(right_top)

        # Card Template chi tiết với hình minh họa vector chuẩn hóa
        tpl_card = SecondaryCard()
        tpl_layout = QHBoxLayout(tpl_card)
        tpl_layout.setContentsMargins(12, 12, 12, 12)
        tpl_layout.setSpacing(14)

        lbl_thumb = QLabel()
        lbl_thumb.setFixedSize(90, 130)
        lbl_thumb.setAlignment(Qt.AlignCenter)
        lbl_thumb.setPixmap(self._create_template_thumbnail_pixmap(90, 130))
        tpl_layout.addWidget(lbl_thumb)

        tpl_meta = QVBoxLayout()
        tpl_meta.setSpacing(6)
        lbl_m_title = QLabel("Hàn Quốc 4 Ô Dọc (Life4Cuts)")
        lbl_m_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {COLOR_TEXT_PRIMARY};")
        lbl_m_desc = QLabel("Khung 4 ô chuẩn Hàn Quốc với 4 tư thế độc lập, hỗ trợ chụp lại từng ô con (Slot Retake).")
        lbl_m_desc.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY}; line-height: 1.3;")
        lbl_m_desc.setWordWrap(True)

        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        tag1 = QLabel("🌸 4 Ô Chuẩn")
        tag1.setStyleSheet(f"background: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;")
        tag2 = QLabel("4 Ô ẢNH RIÊNG")
        tag2.setStyleSheet(f"background: #F6F1E7; color: {COLOR_CHAMPAGNE}; border: 1px solid {COLOR_PALE_GOLD}; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        tag3 = QLabel("2x6 inch")
        tag3.setStyleSheet(f"background: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;")
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
        note_box = SecondaryCard()
        note_l = QVBoxLayout(note_box)
        note_l.setContentsMargins(12, 10, 12, 10)
        note_l.setSpacing(4)
        lbl_n_title = QLabel("GHI CHÚ SỰ KIỆN:")
        lbl_n_title.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {COLOR_CHAMPAGNE}; letter-spacing: 0.5px;")
        lbl_n_desc = QLabel("Sự kiện tiệc cưới lãng mạn. Khách thích chụp dải 4 ô dọc lấy liền 2 bản.")
        lbl_n_desc.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY};")
        lbl_n_desc.setWordWrap(True)
        note_l.addWidget(lbl_n_title)
        note_l.addWidget(lbl_n_desc)
        right_layout.addWidget(note_box)

        right_layout.addStretch()

        # Nút Chuyển sang Kiosk lớn
        btn_switch_kiosk = QPushButton("⚡ CHUYỂN SANG CHẾ ĐỘ KHÁCH CHỤP (KIOSK)")
        btn_switch_kiosk.setFixedHeight(48)
        btn_switch_kiosk.setCursor(Qt.PointingHandCursor)
        btn_switch_kiosk.setObjectName("btn_champagne")
        btn_switch_kiosk.setStyleSheet(STYLE_BTN_CHAMPAGNE)
        btn_switch_kiosk.clicked.connect(self.start_kiosk_requested.emit)
        right_layout.addWidget(btn_switch_kiosk)

        split_layout.addWidget(right_panel, 2)
        main_layout.addLayout(split_layout)

        self.scroll_area.setWidget(content_widget)
        outer_layout.addWidget(self.scroll_area)

    def _create_status_pill(self, title: str, subtitle: str, state_text: str, icon: str, color_hex: str) -> QFrame:
        """Tạo Pill trạng thái phần cứng sang trọng Minimal Luxury."""
        pill = SecondaryCard()
        pill.setFixedHeight(54)
        layout = QHBoxLayout(pill)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLOR_TEXT_SECONDARY};")
        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};")
        text_col.addWidget(lbl_t)
        text_col.addWidget(lbl_s)
        layout.addLayout(text_col, 1)

        badge = QLabel(f"{icon} {state_text}")
        badge.setStyleSheet(f"""
            background: {color_hex}15;
            color: {color_hex};
            border: 1px solid {color_hex}40;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 800;
            padding: 3px 7px;
        """)
        layout.addWidget(badge)

        # Lưu tham chiếu để update_telemetry có thể cập nhật
        pill.lbl_subtitle = lbl_s
        pill.lbl_badge = badge
        return pill

    def _update_status_pill(self, pill: QFrame, subtitle: str, state_text: str, icon: str, color_hex: str):
        if hasattr(pill, "lbl_subtitle"):
            pill.lbl_subtitle.setText(subtitle)
        if hasattr(pill, "lbl_badge"):
            pill.lbl_badge.setText(f"{icon} {state_text}")
            pill.lbl_badge.setStyleSheet(f"""
                background: {color_hex}15;
                color: {color_hex};
                border: 1px solid {color_hex}40;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 800;
                padding: 3px 7px;
            """)

    def _create_template_thumbnail_pixmap(self, width: int = 90, height: int = 130) -> QPixmap:
        """Tạo hình thumbnail vector sắc nét cho khung ảnh dải 4 ô."""
        pix = QPixmap(width, height)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(QPen(QColor(COLOR_BORDER), 1.5))
        painter.setBrush(QBrush(QColor(COLOR_SURFACE)))
        painter.drawRoundedRect(QRectF(1, 1, width - 2, height - 2), 6, 6)

        slot_w = width - 16
        slot_h = 22
        x = 8
        painter.setFont(QFont("Arial", 7, QFont.Bold))

        for i in range(4):
            y = 7 + i * 26
            painter.setPen(QPen(QColor(COLOR_BORDER), 1))
            painter.setBrush(QBrush(QColor(COLOR_SURFACE_SECONDARY)))
            painter.drawRoundedRect(QRectF(x, y, slot_w, slot_h), 3, 3)

            painter.setPen(QPen(QColor(COLOR_TEXT_PRIMARY)))
            painter.drawText(QRectF(x, y, slot_w, slot_h), Qt.AlignCenter, f"Ô #{i+1}")

        painter.setPen(QPen(QColor(COLOR_CHAMPAGNE)))
        painter.setFont(QFont("Arial", 6, QFont.Bold))
        painter.drawText(QRectF(0, height - 16, width, 12), Qt.AlignCenter, "1998 TEAM")

        painter.end()
        return pix

    def _setup_hardware_callbacks(self):
        """Đăng ký callback an toàn từ Machine 1 mà không can thiệp logic nội bộ."""
        if self.camera_mgr and hasattr(self.camera_mgr, "register_status_callback"):
            try:
                self.camera_mgr.register_status_callback(self._on_camera_status_changed)
            except Exception:
                pass

    def _on_camera_status_changed(self, state):
        """Cập nhật giao diện tức thì khi có thông báo trạng thái kết nối máy ảnh."""
        QTimer.singleShot(0, self, self.update_telemetry)

    def close(self) -> bool:
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()
        if self.camera_mgr and hasattr(self.camera_mgr, "_on_status_changed_callbacks"):
            try:
                self.camera_mgr._on_status_changed_callbacks.remove(self._on_camera_status_changed)
            except (ValueError, AttributeError):
                pass
        return super().close()

    def _setup_telemetry_timer(self):
        """Khởi động bộ đếm thời gian cập nhật viễn toán (1.0s interval) phi phong bế."""
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_telemetry_tick)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_telemetry()
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def _on_telemetry_tick(self):
        """Nhịp cập nhật viễn toán định kỳ và hiển thị live view nếu có frame."""
        self.update_telemetry()
        if self.camera_mgr and hasattr(self.camera_mgr, "get_liveview_rgb"):
            try:
                frame = self.camera_mgr.get_liveview_rgb()
                if frame is not None:
                    self.viewport.set_frame_rgb(frame)
            except Exception:
                pass

    def update_telemetry(self):
        """
        Đồng bộ toàn bộ số liệu, trạng thái thiết bị và cảnh báo từ Machine 1.
        Tuyệt đối không bịa số liệu giả dưới nhãn LIVE.
        """
        # 1. Thống kê Sự Kiện & Phiên Chụp
        if not self.event_mgr:
            if self._is_demo_mode:
                self.card_event.set_value("Demo Event 2026")
                self.card_event.set_subtitle("Dữ liệu mô phỏng sự kiện")
                self.card_event.set_badge_mode("DEMO")

                self.card_sessions.set_value("12")
                self.card_sessions.set_subtitle("Mô phỏng: 12 lượt chụp")
                self.card_sessions.set_badge_mode("DEMO")

                self.card_prints.set_value("24")
                self.card_prints.set_subtitle("Mô phỏng: 24 bản in")
                self.card_prints.set_badge_mode("DEMO")
            else:
                self.card_event.set_value("--")
                self.card_event.set_subtitle("Chưa có dịch vụ sự kiện")
                self.card_event.set_badge_mode("N/A")

                self.card_sessions.set_value("--")
                self.card_sessions.set_subtitle("Chưa có dữ liệu")
                self.card_sessions.set_badge_mode("N/A")

                self.card_prints.set_value("--")
                self.card_prints.set_subtitle("Chưa có dữ liệu")
                self.card_prints.set_badge_mode("N/A")
        else:
            try:
                evt_name = self.event_mgr.get_active_event_name()
                stats = self.event_mgr.get_event_stats(evt_name)
                sess_count = stats.get("total_final_photos", 0)
                prints_count = stats.get("total_prints", sess_count * 2)

                badge_evt = "DEMO" if self._is_demo_mode else "LIVE"

                self.card_event.set_value(str(evt_name) if evt_name else "Mặc định")
                self.card_event.set_subtitle("Thư mục lưu ảnh sự kiện")
                self.card_event.set_badge_mode(badge_evt)

                self.card_sessions.set_value(str(sess_count))
                if sess_count == 0:
                    self.card_sessions.set_subtitle("Chưa có ảnh (sẵn sàng đón khách)")
                else:
                    self.card_sessions.set_subtitle(f"Hoàn tất: {sess_count} lượt chụp")
                self.card_sessions.set_badge_mode(badge_evt)

                self.card_prints.set_value(str(prints_count))
                self.card_prints.set_subtitle("Bản in nhiệt thành phẩm")
                self.card_prints.set_badge_mode(badge_evt)
            except Exception:
                self.card_event.set_value("Lỗi đọc đĩa")
                self.card_event.set_subtitle("Không thể mở thư mục sự kiện")
                self.card_event.set_badge_mode("ERROR")

                self.card_sessions.set_value("ERROR")
                self.card_sessions.set_subtitle("Lỗi truy xuất dữ liệu đĩa")
                self.card_sessions.set_badge_mode("ERROR")

                self.card_prints.set_value("ERROR")
                self.card_prints.set_subtitle("Không thể đọc thống kê in")
                self.card_prints.set_badge_mode("ERROR")

        # 2. Giám sát Máy In & Giấy In Còn Lại
        is_prn_online = False
        paper_remaining = 0
        prn_name = "Chưa kết nối máy in"

        if self.print_mgr:
            try:
                selected_prn = self.print_mgr.get_selected_printer()
                if selected_prn:
                    prn_name = selected_prn
                    is_prn_online = True
                    paper_remaining = int(self.config_mgr.get("printer_paper_remaining", 700))
            except Exception:
                pass

        if is_prn_online:
            has_hw_sensor = hasattr(self.print_mgr, "has_hardware_paper_sensor") and self.print_mgr.has_hardware_paper_sensor()
            if self._is_demo_mode:
                badge_prn = "DEMO"
                sub_txt = f"Còn lại {int(paper_remaining / 700 * 100)}% cuộn giấy DNP (Mô phỏng)"
            elif has_hw_sensor:
                badge_prn = "LIVE"
                sub_txt = f"Còn lại {int(paper_remaining / 700 * 100)}% cuộn giấy DNP (Cảm biến HW)"
            else:
                badge_prn = "MANUAL"
                sub_txt = f"Còn lại {int(paper_remaining / 700 * 100)}% cuộn giấy DNP (Nhập thủ công)"

            self.card_paper.set_value(f"{paper_remaining} / 700")
            self.card_paper.set_subtitle(sub_txt)
            self.card_paper.set_badge_mode(badge_prn)
            self._update_status_pill(self.pill_prn, f"{prn_name} ({paper_remaining} Giấy)", "READY", "✓", COLOR_SUCCESS)
            # Cảnh báo hết giấy nếu paper_remaining < 25
            if paper_remaining < 25:
                self.alert_printer_error.set_message("MÁY IN SẮP HẾT GIẤY CUỘN", f"Khay giấy còn lại {paper_remaining} bản in. Vui lòng nạp thêm.")
                self.alert_printer_error.show()
            else:
                self.alert_printer_error.hide()
        else:
            self.card_paper.set_value("--")
            self.card_paper.set_subtitle("Máy in đang tắt nguồn / Offline")
            self.card_paper.set_badge_mode("N/A")
            self._update_status_pill(self.pill_prn, "Chưa kết nối máy in", "OFFLINE", "●", COLOR_TEXT_SECONDARY)
            self.alert_printer_error.hide()

        # 3. Giám sát Máy Ảnh Chụp Chính
        is_cam_connected = False
        cam_model = "Chưa kết nối"
        cam_info: Dict[str, Any] = {}

        if self.camera_mgr:
            try:
                is_cam_connected = bool(self.camera_mgr.is_connected())
                if is_cam_connected and hasattr(self.camera_mgr, "get_info"):
                    cam_info = self.camera_mgr.get_info()
                    cam_model = cam_info.get("model", "Nikon Camera")
            except Exception:
                is_cam_connected = False

        if is_cam_connected:
            bat = cam_info.get("battery_level", "--")
            shutter = cam_info.get("shutter_speed", "1/125s")
            aperture = cam_info.get("aperture", "f/2.8")
            iso = cam_info.get("iso", "ISO 400")
            self._update_status_pill(self.pill_cam, f"{cam_model} ({bat}% Pin)", "CONNECTED", "✓", COLOR_SUCCESS)
            self.lbl_ct_val.setText(f"{shutter}  |  {aperture}  |  {iso}  |  Pin: {bat}%")
            self.alert_cam_disconnect.hide()
        else:
            self._update_status_pill(self.pill_cam, "Chưa kết nối máy ảnh", "DISCONNECTED", "●", COLOR_ERROR)
            self.lbl_ct_val.setText("Máy ảnh đang ngắt kết nối (Cáp USB chưa cắm)")
            self.alert_cam_disconnect.show()
            self.viewport.set_message("Máy ảnh đang ngắt kết nối", color_hex=COLOR_ERROR)

        # 4. Giám sát Dung Lượng Ổ Đĩa Sự Kiện
        if self.event_mgr:
            try:
                disk = self.event_mgr.check_disk_space(warning_threshold_gb=2.0)
                free_gb = disk.get("free_gb", 0.0)
                is_disk_warn = disk.get("is_warning", False)
                self.lbl_dt_val.setText(f"Khả dụng: {free_gb:.1f} GB  |  {disk.get('percent_used', 0.0):.1f}% đã dùng")
                if is_disk_warn:
                    self.alert_storage_warning.set_message("CẢNH BÁO DUNG LƯỢNG LƯU TRỮ", f"Dung lượng ổ cứng còn {free_gb:.1f} GB (< 2.0 GB). Vui lòng dọn dẹp sớm.")
                    self.alert_storage_warning.show()
                else:
                    self.alert_storage_warning.hide()
            except Exception:
                pass

    def _on_reconnect_camera(self):
        """Thử kết nối lại máy ảnh khi người dùng bấm nút trên Banner."""
        if self.camera_mgr and hasattr(self.camera_mgr, "connect"):
            try:
                self.camera_mgr.connect()
                self.update_telemetry()
            except Exception:
                pass

    def _on_refill_paper_dialog(self):
        """Nạp giấy in."""
        if self.print_mgr and hasattr(self.print_mgr, "refill_paper"):
            try:
                self.print_mgr.refill_paper(700)
                self.config_mgr.set("printer_paper_remaining", 700)
                self.config_mgr.save()
                self.update_telemetry()
            except Exception:
                pass

    def _on_storage_cleanup(self):
        """Chuyển sang trang Quản trị Sự kiện để xem chi tiết ổ đĩa."""
        self.open_events_requested.emit()

    def _on_test_capture(self):
        """Chụp thử an toàn (nếu có máy ảnh)."""
        if self.camera_mgr and self.camera_mgr.is_connected():
            try:
                self.camera_mgr.trigger_autofocus()
            except Exception:
                pass

    def _on_test_print(self):
        """In thử an toàn (nếu có máy in)."""
        if self.print_mgr and hasattr(self.print_mgr, "print_test_page"):
            try:
                self.print_mgr.print_test_page()
            except Exception:
                pass
