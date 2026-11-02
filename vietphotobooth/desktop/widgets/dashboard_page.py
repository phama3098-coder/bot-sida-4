"""
1998 TEAM PHOTOBOOTH v2.0.0 — OPERATOR DASHBOARD
Buồng lái tác nghiệp trung tâm (Operator Cockpit) theo Concept A Premium Studio.
Tập trung giám sát sự kiện, thiết bị phần cứng đa kênh (Concept C), Live View trung tâm,
và chuyển đổi tức thì sang chế độ khách chụp Kiosk (Concept B).
"""

import os
from typing import Optional
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QPixmap
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
    COLOR_GREEN, COLOR_RED, COLOR_BLUE, get_svg_icon
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
        parent=None
    ):
        super().__init__(parent)
        self.event_mgr = event_mgr
        self.camera_mgr = camera_mgr
        self.print_mgr = print_mgr
        self.config_mgr = config_mgr or ConfigManager()

        self._init_ui()
        self._setup_telemetry_timer()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 1. Header Bar: Tiêu đề buồng lái & Nút Start Kiosk lớn
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        lbl_title = QLabel("Bảng Điều Khiển Vận Hành (Dashboard)")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: 800; color: #FFFFFF;")
        lbl_sub = QLabel("Buồng lái tác nghiệp trung tâm 1998 TEAM — Giám sát sự kiện, thiết bị và hàng đợi")
        lbl_sub.setStyleSheet("font-size: 13px; color: #94A3B8;")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        self.btn_start_kiosk = QPushButton("🚀 BẮT ĐẦU PHOTOBOOTH (F11)")
        self.btn_start_kiosk.setFixedHeight(48)
        self.btn_start_kiosk.setCursor(Qt.PointingHandCursor)
        self.btn_start_kiosk.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D4AF37, stop:1 #F5DE88); "
            "color: #070A12; font-size: 14px; font-weight: 800; border-radius: 8px; padding: 0 24px; border: none; }"
            "QPushButton:hover { background: #FDF4DC; box-shadow: 0 0 16px rgba(212,175,55,0.6); }"
            "QPushButton:pressed { background: #C5A059; }"
        )
        self.btn_start_kiosk.clicked.connect(self.start_kiosk_requested.emit)
        header_layout.addWidget(self.btn_start_kiosk)

        main_layout.addLayout(header_layout)

        # 2. Disclaimer Banner Minh Bạch
        disclaimer_banner = QFrame()
        disclaimer_banner.setStyleSheet(
            "QFrame { background-color: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); "
            "border-radius: 8px; padding: 10px 14px; }"
        )
        disclaimer_layout = QHBoxLayout(disclaimer_banner)
        disclaimer_layout.setContentsMargins(10, 8, 10, 8)
        lbl_warn_icon = QLabel("⚠️")
        lbl_warn_icon.setStyleSheet("font-size: 16px;")
        lbl_warn_text = QLabel(
            "<b>BUỒNG LÁI VẬN HÀNH 1998 TEAM:</b> Dữ liệu phiên, bản in và các thông số telemetry phần cứng "
            "được biểu diễn ở chế độ <b>[DEMO / SIMULATED]</b> nhằm xác thực trải nghiệm UI/UX. "
            "Camera engine thực tế tuân thủ driver Windows WPD và Nikon MAID3 SDK."
        )
        lbl_warn_text.setStyleSheet("font-size: 12px; color: #F59E0B;")
        lbl_warn_text.setWordWrap(True)
        disclaimer_layout.addWidget(lbl_warn_icon)
        disclaimer_layout.addWidget(lbl_warn_text, 1)
        main_layout.addWidget(disclaimer_banner)

        # 3. 4 Stat Cards
        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)

        # Card 1: Sự kiện hoạt động
        evt_name = self.event_mgr.current_event if self.event_mgr else "Đám Cưới Minh & Linh"
        card1 = self._create_stat_card("📅", "#3B82F6", "SỰ KIỆN HOẠT ĐỘNG", evt_name, "📍 White Palace, TP.HCM", is_demo=False)
        stats_grid.addWidget(card1, 0, 0)

        # Card 2: Phiên đã chụp
        card2 = self._create_stat_card("📸", "#10B981", "PHIÊN ĐÃ CHỤP", "64", "Hôm nay: +64 lượt khách [DEMO]", is_demo=True)
        stats_grid.addWidget(card2, 0, 1)

        # Card 3: Bản in thành phẩm
        card3 = self._create_stat_card("🖨️", "#F59E0B", "BẢN IN THÀNH PHẨM", "128", "100% bản in hoàn tất [DEMO]", is_demo=True)
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
            "QFrame { background-color: #111827; border: 1px solid #1F2937; border-radius: 12px; }"
        )
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(12)

        panel_top = QHBoxLayout()
        lbl_hw_title = QLabel("⚡ Trạng Thái Phần Cứng (Concept C Multi-Channel)")
        lbl_hw_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF;")
        panel_top.addWidget(lbl_hw_title)
        panel_top.addStretch()

        btn_cycle = QPushButton("🔄 Thử Trạng Thái")
        btn_cycle.setCursor(Qt.PointingHandCursor)
        btn_cycle.setStyleSheet(
            "QPushButton { background: #1F2937; color: #D4AF37; border: 1px solid #374151; "
            "border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background: #374151; }"
        )
        btn_cycle.clicked.connect(self._cycle_simulated_state)
        panel_top.addWidget(btn_cycle)
        left_layout.addLayout(panel_top)

        # 3 Multi-channel Status Pills
        self.status_row = QHBoxLayout()
        self.status_row.setSpacing(8)

        self.pill_cam = self._create_status_pill("MÁY ẢNH (NIKON D780)", "Nikon D780 (92% Pin [MOCK])", "CONNECTED", "✓", "#10B981")
        self.pill_prn = self._create_status_pill("MÁY IN NHIỆT (DNP)", "DNP DS-RX1HS (486 Giấy [SIM])", "READY", "✓", "#10B981")
        self.pill_net = self._create_status_pill("MẠNG NỘI BỘ (LAN)", "192.168.4.1:8080 (4 Khách [SIM])", "ONLINE", "✓", "#3B82F6")

        self.status_row.addWidget(self.pill_cam)
        self.status_row.addWidget(self.pill_prn)
        self.status_row.addWidget(self.pill_net)
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

        btn_open_studio = QPushButton("🔍 Mở Toàn Bộ Studio")
        btn_open_studio.setCursor(Qt.PointingHandCursor)
        btn_open_studio.setStyleSheet(
            "QPushButton { background: #D4AF37; color: #070A12; font-weight: 700; "
            "border-radius: 6px; padding: 8px 14px; font-size: 12px; }"
            "QPushButton:hover { background: #F3E5AB; }"
        )
        btn_open_studio.clicked.connect(self.open_studio_requested.emit)
        toolbar.addWidget(btn_open_studio)

        left_layout.addLayout(toolbar)
        split_layout.addWidget(left_panel, 3)

        # --- CỘT PHẢI: Khung ảnh đang dùng & Thao tác nhanh ---
        right_panel = QFrame()
        right_panel.setStyleSheet(
            "QFrame { background-color: #111827; border: 1px solid #1F2937; border-radius: 12px; }"
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(14)

        right_top = QHBoxLayout()
        lbl_tpl_title = QLabel("🎨 Khung Ảnh Đang Áp Dụng (Template)")
        lbl_tpl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF;")
        right_top.addWidget(lbl_tpl_title)
        right_top.addStretch()

        btn_change_tpl = QPushButton("Thay Đổi Khung")
        btn_change_tpl.setCursor(Qt.PointingHandCursor)
        btn_change_tpl.setStyleSheet(
            "QPushButton { background: #1F2937; color: #D4AF37; border: 1px solid #374151; "
            "border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background: #374151; }"
        )
        btn_change_tpl.clicked.connect(self.open_templates_requested.emit)
        right_top.addWidget(btn_change_tpl)
        right_layout.addLayout(right_top)

        # Card Template chi tiết
        tpl_card = QFrame()
        tpl_card.setStyleSheet(
            "QFrame { background-color: #0F172A; border: 1px solid #28395E; border-radius: 8px; padding: 12px; }"
        )
        tpl_layout = QHBoxLayout(tpl_card)
        tpl_layout.setContentsMargins(8, 8, 8, 8)
        tpl_layout.setSpacing(14)

        # Thumb preview
        lbl_thumb = QLabel()
        lbl_thumb.setFixedSize(90, 130)
        lbl_thumb.setAlignment(Qt.AlignCenter)
        lbl_thumb.setStyleSheet("background: #000000; border-radius: 6px; border: 1px solid #334155;")
        thumb_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "ui-redesign", "PROTOTYPE", "assets", "slot_1_pose_wave.jpg")
        if os.path.exists(thumb_path):
            pix = QPixmap(thumb_path).scaled(90, 130, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            lbl_thumb.setPixmap(pix)
        else:
            lbl_thumb.setText("🖼️ 1x4")
        tpl_layout.addWidget(lbl_thumb)

        tpl_meta = QVBoxLayout()
        tpl_meta.setSpacing(4)
        lbl_m_title = QLabel("Hàn Quốc 4 Ô Dọc (Life4Cuts)")
        lbl_m_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #F8FAFC;")
        lbl_m_desc = QLabel("Khung 4 ô chuẩn Hàn Quốc với 4 tư thế riêng biệt, hỗ trợ chụp lại từng ô con độc lập.")
        lbl_m_desc.setStyleSheet("font-size: 11px; color: #94A3B8;")
        lbl_m_desc.setWordWrap(True)

        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        tag1 = QLabel("🌸 4 Ô Chuẩn")
        tag1.setStyleSheet("background: #1E293B; color: #E2E8F0; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;")
        tag2 = QLabel("4 Ô ẢNH RIÊNG")
        tag2.setStyleSheet("background: rgba(225,29,72,0.15); color: #E11D48; border: 1px solid rgba(225,29,72,0.3); padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        tag3 = QLabel("2x6 inch")
        tag3.setStyleSheet("background: #1E293B; color: #E2E8F0; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;")
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
        note_box.setStyleSheet("background: #0B101E; border-radius: 8px; padding: 10px;")
        note_l = QVBoxLayout(note_box)
        note_l.setContentsMargins(10, 8, 10, 8)
        lbl_n_title = QLabel("GHI CHÚ SỰ KIỆN:")
        lbl_n_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #D4AF37;")
        lbl_n_desc = QLabel("Sự kiện tiệc cưới lãng mạn. Khách thích chụp 4 ô dọc lấy liền.")
        lbl_n_desc.setStyleSheet("font-size: 11px; color: #CBD5E1;")
        note_l.addWidget(lbl_n_title)
        note_l.addWidget(lbl_n_desc)
        right_layout.addWidget(note_box)

        right_layout.addStretch()

        # Nút Chuyển sang Kiosk
        btn_switch_kiosk = QPushButton("⚡ CHUYỂN SANG CHẾ ĐỘ KHÁCH CHỤP (KIOSK)")
        btn_switch_kiosk.setFixedHeight(54)
        btn_switch_kiosk.setCursor(Qt.PointingHandCursor)
        btn_switch_kiosk.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D4AF37, stop:1 #F5DE88); "
            "color: #070A12; font-size: 14px; font-weight: 800; border-radius: 8px; border: none; }"
            "QPushButton:hover { background: #FDF4DC; }"
            "QPushButton:pressed { background: #C5A059; }"
        )
        btn_switch_kiosk.clicked.connect(self.start_kiosk_requested.emit)
        right_layout.addWidget(btn_switch_kiosk)

        split_layout.addWidget(right_panel, 2)
        main_layout.addLayout(split_layout)

    def _create_stat_card(self, icon: str, color_hex: str, label: str, value: str, meta: str, is_demo: bool = False) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #111827; border: 1px solid #1F2937; border-radius: 10px; padding: 14px; }"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet(f"font-size: 24px; color: {color_hex};")
        layout.addWidget(lbl_icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        lbl_tag = QHBoxLayout()
        lbl_l = QLabel(label)
        lbl_l.setStyleSheet("font-size: 11px; font-weight: 700; color: #94A3B8; text-transform: uppercase;")
        lbl_tag.addWidget(lbl_l)
        if is_demo:
            pill = QLabel("DEMO")
            pill.setStyleSheet(
                "background: rgba(245, 158, 11, 0.15); color: #F59E0B; "
                "border: 1px solid rgba(245, 158, 11, 0.35); font-size: 9px; font-weight: 800; "
                "padding: 1px 4px; border-radius: 3px;"
            )
            lbl_tag.addWidget(pill)
        lbl_tag.addStretch()
        text_col.addLayout(lbl_tag)

        lbl_v = QLabel(value)
        lbl_v.setStyleSheet("font-size: 20px; font-weight: 800; color: #F8FAFC;")
        text_col.addWidget(lbl_v)

        lbl_m = QLabel(meta)
        lbl_m.setStyleSheet("font-size: 11px; color: #64748B;")
        text_col.addWidget(lbl_m)

        layout.addLayout(text_col)
        return card

    def _create_paper_stat_card(self, icon: str, color_hex: str, label: str, remaining: int, total: int) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #111827; border: 1px solid #1F2937; border-radius: 10px; padding: 14px; }"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet(f"font-size: 24px; color: {color_hex};")
        layout.addWidget(lbl_icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        lbl_tag = QHBoxLayout()
        lbl_l = QLabel(label)
        lbl_l.setStyleSheet("font-size: 11px; font-weight: 700; color: #94A3B8;")
        lbl_tag.addWidget(lbl_l)
        pill = QLabel("SIMULATED")
        pill.setStyleSheet(
            "background: rgba(245, 158, 11, 0.15); color: #F59E0B; "
            "border: 1px solid rgba(245, 158, 11, 0.35); font-size: 9px; font-weight: 800; "
            "padding: 1px 4px; border-radius: 3px;"
        )
        lbl_tag.addWidget(pill)
        lbl_tag.addStretch()
        text_col.addLayout(lbl_tag)

        lbl_v = QLabel(f"{remaining} <span style='font-size: 13px; font-weight: 400; color: #64748B;'>/ {total}</span>")
        lbl_v.setStyleSheet("font-size: 20px; font-weight: 800; color: #F8FAFC;")
        text_col.addWidget(lbl_v)

        bar = QProgressBar()
        bar.setRange(0, total)
        bar.setValue(remaining)
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setStyleSheet(
            "QProgressBar { background-color: #1F2937; border-radius: 2px; } "
            "QProgressBar::chunk { background-color: #EC4899; border-radius: 2px; }"
        )
        text_col.addWidget(bar)

        pct = int(remaining / total * 100)
        lbl_m = QLabel(f"{pct}% dung lượng cuộn giấy [SIMULATED]")
        lbl_m.setStyleSheet("font-size: 11px; color: #64748B; margin-top: 2px;")
        text_col.addWidget(lbl_m)

        layout.addLayout(text_col)
        return card

    def _create_status_pill(self, title: str, subtitle: str, state_text: str, icon: str, color_hex: str) -> QFrame:
        pill = QFrame()
        pill.setStyleSheet(
            f"QFrame {{ background: #0F172A; border: 1px solid {color_hex}40; border-radius: 8px; padding: 6px 10px; }}"
        )
        layout = QHBoxLayout(pill)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 10px; font-weight: 700; color: #94A3B8;")
        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet("font-size: 11px; font-weight: 600; color: #F1F5F9;")
        text_col.addWidget(lbl_t)
        text_col.addWidget(lbl_s)
        layout.addLayout(text_col)

        badge = QLabel(f"{icon} {state_text}")
        badge.setStyleSheet(
            f"background: {color_hex}25; color: {color_hex}; border: 1px solid {color_hex}50; "
            f"border-radius: 4px; font-size: 10px; font-weight: 800; padding: 3px 6px;"
        )
        layout.addWidget(badge)

        return pill

    def _action_btn_style(self) -> str:
        return (
            "QPushButton { background: #1F2937; color: #E2E8F0; border: 1px solid #374151; "
            "border-radius: 6px; padding: 8px 12px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #374151; color: #D4AF37; border-color: #D4AF37; }"
            "QPushButton:pressed { background: #111827; }"
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
        # Demo chuyển đổi trạng thái trên giao diện
        pass

    def _on_test_capture(self):
        if self.camera_mgr:
            try:
                self.camera_mgr.trigger_autofocus()
            except Exception:
                pass

    def _on_test_print(self):
        pass
