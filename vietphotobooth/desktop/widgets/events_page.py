"""
1998 TEAM — Photobooth Event Management & Session Gallery Page
Matches Reference Design Panel 4:
- Header with folder open, cloud sync all, and zip export.
- Two top cards: "Sự kiện đang hoạt động" and "Tạo sự kiện mới".
- Full event table with search, sorting, folder open, rename, and safe delete.
- Session gallery for reprinting and dual QR codes (Cloud 4G / LAN WiFi).
"""

import os
import shutil
from typing import Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox,
    QInputDialog, QFileDialog, QDialog, QScrollArea, QFrame, QTabWidget,
    QLineEdit, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
import qrcode

from vietphotobooth.core.events import EventManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.cloud import SyncManager, SyncStatus
from vietphotobooth.core.logger import get_logger
from vietphotobooth.desktop.icons import get_svg_icon, COLOR_GOLD, COLOR_GREEN, COLOR_RED, COLOR_SLATE, COLOR_NAVY
from vietphotobooth.desktop.widgets.session_lightbox_dialog import SessionLightboxDialog

logger = get_logger()

class EventsPage(QWidget):
    """Trang Quản Lý Sự Kiện & Thư Viện Lượt Chụp chuẩn phong cách 1998 TEAM (Panel 4)."""

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(720, 420)

    def __init__(
        self,
        event_mgr: EventManager,
        print_mgr: PrintManager,
        token_mgr: TokenManager,
        sync_mgr: Optional[SyncManager] = None,
        auth_mgr=None,
        parent=None
    ):
        super().__init__(parent)
        self.event_mgr = event_mgr
        self.print_mgr = print_mgr
        self.token_mgr = token_mgr
        self.sync_mgr = sync_mgr
        self.auth_mgr = auth_mgr
        self.selected_event_name: str = self.event_mgr.get_active_event_name()

        self._init_ui()
        self._load_all_events()

        # Lắng nghe tiến trình đồng bộ ngầm
        if self.sync_mgr:
            self.sync_mgr.worker.sync_completed.connect(lambda p, l: self._refresh_gallery())
            self.sync_mgr.worker.sync_failed.connect(lambda p, e: self._refresh_gallery())

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(16)

        # =========================================================================
        # 1. HEADER BAR
        # =========================================================================
        header_bar = QHBoxLayout()
        header_bar.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_icon("calendar", size=30, color=COLOR_GOLD).pixmap(30, 30))
        header_bar.addWidget(icon_lbl)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("QUẢN LÝ SỰ KIỆN")
        lbl_title.setStyleSheet("font-size: 19px; font-weight: 800; color: #34312E; letter-spacing: 0.5px;")
        v_head.addWidget(lbl_title)

        lbl_subtitle = QLabel("1998 TEAM Photobooth • 1998 Studio phóng sự cưới")
        lbl_subtitle.setStyleSheet("font-size: 12px; color: #777067; font-weight: 500;")
        v_head.addWidget(lbl_subtitle)
        header_bar.addLayout(v_head)

        header_bar.addStretch(1)

        # Top Action Buttons with Vector Icons
        btn_open_root = QPushButton(" Mở Thư Mục Lưu Ảnh")
        btn_open_root.setIcon(get_svg_icon("folder", size=16, color=COLOR_GOLD))
        btn_open_root.setObjectName("btn_secondary")
        btn_open_root.setCursor(Qt.PointingHandCursor)
        btn_open_root.clicked.connect(self._open_storage_root)
        header_bar.addWidget(btn_open_root)

        btn_sync_all = QPushButton(" Đồng Bộ Toàn Bộ Lên Drive")
        btn_sync_all.setIcon(get_svg_icon("cloud", size=16, color=COLOR_NAVY))
        btn_sync_all.setObjectName("btn_champagne")
        btn_sync_all.setCursor(Qt.PointingHandCursor)
        btn_sync_all.clicked.connect(self._sync_all_to_gdrive)
        header_bar.addWidget(btn_sync_all)

        btn_export_zip = QPushButton(" Xuất File ZIP")
        btn_export_zip.setIcon(get_svg_icon("paper", size=16, color=COLOR_SLATE))
        btn_export_zip.setObjectName("btn_secondary")
        btn_export_zip.setCursor(Qt.PointingHandCursor)
        btn_export_zip.clicked.connect(self._export_event_zip)
        header_bar.addWidget(btn_export_zip)

        layout.addLayout(header_bar)

        # =========================================================================
        # 2. TOP 2 CARDS: ACTIVE EVENT & CREATE NEW EVENT (Panel 4 Reference)
        # =========================================================================
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        # --- CARD 1: SỰ KIỆN ĐANG HOẠT ĐỘNG ---
        self.card_active = QFrame()
        self.card_active.setObjectName("card_active_event")
        self.card_active.setStyleSheet("""
            QFrame#card_active_event {
                background-color: #E7DFD2;
                border: 2px solid #B89555;
                border-radius: 10px;
                padding: 4px;
            }
        """)
        l_active = QVBoxLayout(self.card_active)
        l_active.setContentsMargins(16, 14, 16, 14)
        l_active.setSpacing(8)

        lbl_badge_active = QLabel("● SỰ KIỆN ĐANG HOẠT ĐỘNG")
        lbl_badge_active.setStyleSheet("color: #059669; font-weight: 800; font-size: 12px; letter-spacing: 0.5px;")
        l_active.addWidget(lbl_badge_active)

        self.lbl_active_name = QLabel("SuKien_MacDinh")
        self.lbl_active_name.setStyleSheet("color: #34312E; font-size: 20px; font-weight: 800;")
        self.lbl_active_name.setWordWrap(True)
        l_active.addWidget(self.lbl_active_name)

        self.lbl_active_details = QLabel("Ngày tạo: -- • 0 ảnh thành phẩm • 0 MB")
        self.lbl_active_details.setStyleSheet("color: #777067; font-size: 13px;")
        l_active.addWidget(self.lbl_active_details)

        l_active.addSpacing(4)
        row_active_actions = QHBoxLayout()
        row_active_actions.setSpacing(8)

        self.btn_change_event = QPushButton(" Đổi Sự Kiện")
        self.btn_change_event.setIcon(get_svg_icon("refresh", size=15, color=COLOR_GOLD))
        self.btn_change_event.setObjectName("btn_secondary")
        self.btn_change_event.setCursor(Qt.PointingHandCursor)
        self.btn_change_event.clicked.connect(self._prompt_switch_event)
        row_active_actions.addWidget(self.btn_change_event)

        self.btn_end_event = QPushButton(" Kết Thúc")
        self.btn_end_event.setIcon(get_svg_icon("stop", size=15, color="#DC2626"))
        self.btn_end_event.setStyleSheet("""
            QPushButton {
                background-color: #FEF2F2;
                border: 1.5px solid #FECACA;
                color: #DC2626;
                font-weight: 700;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #DC2626;
                color: #FFFFFF;
                border-color: #DC2626;
            }
        """)
        self.btn_end_event.setCursor(Qt.PointingHandCursor)
        self.btn_end_event.clicked.connect(self._end_current_event)
        row_active_actions.addWidget(self.btn_end_event)
        row_active_actions.addStretch(1)

        l_active.addLayout(row_active_actions)
        cards_layout.addWidget(self.card_active, 1)

        # --- CARD 2: TẠO SỰ KIỆN MỚI ---
        card_create = QFrame()
        card_create.setObjectName("card_create_event")
        card_create.setStyleSheet("""
            QFrame#card_create_event {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                border-radius: 10px;
                padding: 4px;
            }
        """)
        l_create = QVBoxLayout(card_create)
        l_create.setContentsMargins(16, 14, 16, 14)
        l_create.setSpacing(8)

        lbl_create_title = QLabel("TẠO SỰ KIỆN MỚI")
        lbl_create_title.setStyleSheet("color: #34312E; font-weight: 800; font-size: 12px; letter-spacing: 0.5px;")
        l_create.addWidget(lbl_create_title)

        lbl_create_hint = QLabel("Tạo không gian lưu ảnh độc lập cho khách cưới hoặc tiệc sinh nhật:")
        lbl_create_hint.setStyleSheet("color: #777067; font-size: 13px;")
        l_create.addWidget(lbl_create_hint)

        self.txt_new_event = QLineEdit()
        self.txt_new_event.setPlaceholderText("Nhập tên sự kiện (VD: Đám cưới Tuấn & Lan, Sinh nhật 18 tuổi...)")
        self.txt_new_event.setStyleSheet("""
            QLineEdit {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                border-radius: 6px;
                padding: 7px 10px;
                color: #34312E;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #B89555;
            }
        """)
        self.txt_new_event.returnPressed.connect(self._create_new_event_from_input)
        l_create.addWidget(self.txt_new_event)

        row_create_actions = QHBoxLayout()
        self.btn_create_submit = QPushButton(" Tạo Sự Kiện & Chọn")
        self.btn_create_submit.setIcon(get_svg_icon("plus", size=16, color=COLOR_NAVY))
        self.btn_create_submit.setObjectName("btn_champagne")
        self.btn_create_submit.setCursor(Qt.PointingHandCursor)
        self.btn_create_submit.clicked.connect(self._create_new_event_from_input)
        row_create_actions.addWidget(self.btn_create_submit)
        row_create_actions.addStretch(1)

        l_create.addLayout(row_create_actions)
        cards_layout.addWidget(card_create, 1)

        layout.addLayout(cards_layout)

        # =========================================================================
        # 3. DANH SÁCH SỰ KIỆN (EVENT TABLE)
        # =========================================================================
        grp_events = QGroupBox("Danh Sách Sự Kiện")
        grp_events.setStyleSheet("""
            QGroupBox {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: 700;
                color: #34312E;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
        """)
        l_table = QVBoxLayout(grp_events)
        l_table.setContentsMargins(14, 14, 14, 14)
        l_table.setSpacing(10)

        # Search Bar & Filter Header
        bar_search = QHBoxLayout()
        bar_search.setSpacing(10)

        self.txt_search_event = QLineEdit()
        self.txt_search_event.setPlaceholderText("Tìm kiếm sự kiện theo tên...")
        self.txt_search_event.addAction(get_svg_icon("search", size=14, color=COLOR_SLATE), QLineEdit.LeadingPosition)
        self.txt_search_event.setStyleSheet("""
            QLineEdit {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                border-radius: 6px;
                padding: 6px 10px;
                color: #34312E;
                font-size: 13px;
                max-width: 320px;
            }
            QLineEdit:focus {
                border-color: #B89555;
            }
        """)
        self.txt_search_event.textChanged.connect(self._on_search_text_changed)
        bar_search.addWidget(self.txt_search_event)

        bar_search.addStretch(1)

        btn_refresh_events = QPushButton(" Làm Mới")
        btn_refresh_events.setIcon(get_svg_icon("refresh", size=14, color=COLOR_SLATE))
        btn_refresh_events.setObjectName("btn_secondary")
        btn_refresh_events.setCursor(Qt.PointingHandCursor)
        btn_refresh_events.clicked.connect(self._load_all_events)
        bar_search.addWidget(btn_refresh_events)

        l_table.addLayout(bar_search)

        # Events Table
        self.table_events = QTableWidget(0, 5)
        self.table_events.setHorizontalHeaderLabels([
            "Tên Sự Kiện", "Ngày Tạo", "Số Ảnh", "Dung Lượng", "Thao Tác"
        ])
        self.table_events.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_events.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_events.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_events.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_events.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table_events.horizontalHeader().resizeSection(4, 250)
        self.table_events.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_events.setSelectionMode(QTableWidget.SingleSelection)
        self.table_events.setAlternatingRowColors(True)
        self.table_events.verticalHeader().setVisible(False)
        self.table_events.setStyleSheet("""
            QTableWidget {
                background-color: #E7DFD2;
                alternate-background-color: #EFE8DC;
                border: 1.5px solid #BEB3A3;
                border-radius: 6px;
                gridline-color: #BEB3A3;
                color: #34312E;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 8px 6px;
            }
            QTableWidget::item:selected {
                background-color: #C9BDAA;
                color: #34312E;
            }
            QHeaderView::section {
                background-color: #C9BDAA;
                color: #34312E;
                font-weight: 700;
                font-size: 12px;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #BEB3A3;
            }
        """)
        self.table_events.itemSelectionChanged.connect(self._on_event_row_selected)
        l_table.addWidget(self.table_events)

        layout.addWidget(grp_events)

        # =========================================================================
        # 4. THƯ VIỆN LƯỢT CHỤP CỦA SỰ KIỆN (SESSION GALLERY)
        # =========================================================================
        grp_gallery = QGroupBox("Thư Viện Lượt Chụp & In Lại")
        grp_gallery.setStyleSheet("""
            QGroupBox {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: 700;
                color: #34312E;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
        """)
        l_gal = QVBoxLayout(grp_gallery)
        l_gal.setContentsMargins(14, 14, 14, 14)
        l_gal.setSpacing(10)

        # Gallery Top Controls
        bar_gal = QHBoxLayout()
        self.lbl_gallery_event_title = QLabel("Thư viện ảnh: SuKien_MacDinh")
        self.lbl_gallery_event_title.setStyleSheet("color: #34312E; font-weight: 700; font-size: 14px;")
        bar_gal.addWidget(self.lbl_gallery_event_title)

        self.lbl_storage_stats = QLabel("")
        self.lbl_storage_stats.setStyleSheet("color: #777067; font-size: 12px; padding-left: 8px;")
        bar_gal.addWidget(self.lbl_storage_stats)

        bar_gal.addStretch(1)

        btn_preview = QPushButton(" Xem Trước Lượt Chụp")
        btn_preview.setIcon(get_svg_icon("camera", size=15, color=COLOR_GOLD))
        btn_preview.setObjectName("btn_secondary")
        btn_preview.setCursor(Qt.PointingHandCursor)
        btn_preview.clicked.connect(lambda: self._preview_session_selected())
        bar_gal.addWidget(btn_preview)

        btn_reprint = QPushButton(" In Lại Lượt Đang Chọn")
        btn_reprint.setIcon(get_svg_icon("printer", size=15, color=COLOR_GOLD))
        btn_reprint.setObjectName("btn_secondary")
        btn_reprint.setCursor(Qt.PointingHandCursor)
        btn_reprint.clicked.connect(self._reprint_selected)
        bar_gal.addWidget(btn_reprint)

        btn_show_qr = QPushButton(" Xem Lại Mã QR (Online / LAN)")
        btn_show_qr.setIcon(get_svg_icon("camera", size=15, color=COLOR_NAVY))
        btn_show_qr.setObjectName("btn_champagne")
        btn_show_qr.setCursor(Qt.PointingHandCursor)
        btn_show_qr.clicked.connect(self._show_qr_selected)
        bar_gal.addWidget(btn_show_qr)

        l_gal.addLayout(bar_gal)

        # Search / Filter Bar for Sessions
        bar_filter_gal = QHBoxLayout()
        self.txt_search_session = QLineEdit()
        self.txt_search_session.setPlaceholderText("Tìm kiếm lượt chụp theo mã hoặc ngày...")
        self.txt_search_session.addAction(get_svg_icon("search", size=14, color=COLOR_SLATE), QLineEdit.LeadingPosition)
        self.txt_search_session.setStyleSheet("""
            QLineEdit {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                border-radius: 6px;
                padding: 6px 10px;
                color: #34312E;
                font-size: 12px;
                max-width: 320px;
            }
            QLineEdit:focus {
                border-color: #B89555;
            }
        """)
        self.txt_search_session.textChanged.connect(lambda: self._refresh_gallery())
        bar_filter_gal.addWidget(self.txt_search_session)

        bar_filter_gal.addStretch(1)
        l_gal.addLayout(bar_filter_gal)

        # Sessions Table
        self.table_sessions = QTableWidget(0, 5)
        self.table_sessions.setHorizontalHeaderLabels([
            "Mã Lượt Chụp", "Ảnh Thành Phẩm", "Thời Gian", "Đồng Bộ Cloud", "Thao Tác"
        ])
        self.table_sessions.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_sessions.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_sessions.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_sessions.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_sessions.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_sessions.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_sessions.setSelectionMode(QTableWidget.SingleSelection)
        self.table_sessions.setAlternatingRowColors(True)
        self.table_sessions.verticalHeader().setVisible(False)
        self.table_sessions.setStyleSheet("""
            QTableWidget {
                background-color: #E7DFD2;
                alternate-background-color: #EFE8DC;
                border: 1.5px solid #BEB3A3;
                border-radius: 6px;
                gridline-color: #BEB3A3;
                color: #34312E;
                font-size: 13px;
                min-height: 200px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #C9BDAA;
                color: #34312E;
            }
            QHeaderView::section {
                background-color: #C9BDAA;
                color: #34312E;
                font-weight: 700;
                font-size: 12px;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #BEB3A3;
            }
        """)
        self.table_sessions.doubleClicked.connect(lambda idx: self._preview_session_selected())
        l_gal.addWidget(self.table_sessions)

        layout.addWidget(grp_gallery)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # =========================================================================
    # EVENT LOADING & INTERACTION
    # =========================================================================
    def _load_all_events(self):
        """Tải toàn bộ danh sách sự kiện từ EventManager và cập nhật UI."""
        self._all_events_cache = self.event_mgr.list_events()
        self._update_active_card()
        self._render_events_table(self._all_events_cache)
        self._refresh_gallery()

    def _update_active_card(self):
        active_name = self.event_mgr.get_active_event_name()
        self.lbl_active_name.setText(active_name)

        stats = self.event_mgr.get_event_stats(active_name)
        ctime = stats.get("created_at", "N/A")
        finals = stats.get("total_final_photos", 0)
        mb = stats.get("disk_used_mb", 0.0)

        sync_text = "Chưa kết nối Cloud"
        if self.sync_mgr and self.sync_mgr.is_ready():
            sync_text = "Đang đồng bộ Google Drive"

        self.lbl_active_details.setText(f"Ngày tạo: {ctime} • {finals} ảnh thành phẩm • {mb} MB • {sync_text}")

    def _render_events_table(self, events):
        search_query = self.txt_search_event.text().strip().lower()
        if search_query:
            events = [e for e in events if search_query in e["name"].lower()]

        self.table_events.setRowCount(0)
        active_name = self.event_mgr.get_active_event_name()

        for ev in events:
            row = self.table_events.rowCount()
            self.table_events.insertRow(row)

            ev_name = ev["name"]
            is_active = (ev_name == active_name)

            # Col 0: Tên Sự Kiện + Badge
            name_text = f"● {ev_name} [ĐANG CHẠY]" if is_active else ev_name
            item_name = QTableWidgetItem(name_text)
            if is_active:
                item_name.setForeground(Qt.GlobalColor.green)
            self.table_events.setItem(row, 0, item_name)

            # Col 1: Ngày Tạo
            item_date = QTableWidgetItem(str(ev.get("created_at", "")))
            self.table_events.setItem(row, 1, item_date)

            # Col 2: Số Ảnh (Final / Raw)
            finals = ev.get("total_final_photos", 0)
            raws = ev.get("total_original_photos", 0)
            item_photos = QTableWidgetItem(f"{finals} hoàn tất / {raws} gốc")
            self.table_events.setItem(row, 2, item_photos)

            # Col 3: Dung Lượng (MB)
            mb = ev.get("disk_used_mb", 0.0)
            item_size = QTableWidgetItem(f"{mb} MB")
            self.table_events.setItem(row, 3, item_size)

            # Col 4: Thao Tác (Action buttons widget)
            action_widget = QWidget()
            h_action = QHBoxLayout(action_widget)
            h_action.setContentsMargins(4, 2, 4, 2)
            h_action.setSpacing(6)

            cell_btn_style = (
                "QPushButton { background-color: #FFFFFF; border: 1.5px solid #D9DEE7; "
                "border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: 600; color: #303746; } "
                "QPushButton:hover { background-color: #F8FAFC; border-color: #D4AF37; color: #1E40AF; }"
            )

            if not is_active:
                btn_pick = QPushButton("Chọn")
                btn_pick.setStyleSheet(
                    "QPushButton { background-color: #EFF6FF; border: 1.5px solid #BFDBFE; "
                    "border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: bold; color: #1E40AF; } "
                    "QPushButton:hover { background-color: #DBEAFE; border-color: #3B82F6; }"
                )
                btn_pick.setCursor(Qt.PointingHandCursor)
                btn_pick.clicked.connect(lambda _, n=ev_name: self._switch_to_event(n))
                h_action.addWidget(btn_pick)

            btn_open = QPushButton()
            btn_open.setIcon(get_svg_icon("folder", size=14, color=COLOR_GOLD))
            btn_open.setToolTip("Mở thư mục sự kiện")
            btn_open.setCursor(Qt.PointingHandCursor)
            btn_open.setStyleSheet(cell_btn_style)
            btn_open.clicked.connect(lambda _, n=ev_name: self._open_specific_folder(n))
            h_action.addWidget(btn_open)

            btn_rename = QPushButton()
            btn_rename.setIcon(get_svg_icon("edit", size=14, color=COLOR_SLATE))
            btn_rename.setToolTip("Đổi tên sự kiện")
            btn_rename.setCursor(Qt.PointingHandCursor)
            btn_rename.setStyleSheet(cell_btn_style)
            btn_rename.clicked.connect(lambda _, n=ev_name: self._rename_event_dialog(n))
            h_action.addWidget(btn_rename)

            btn_delete = QPushButton()
            btn_delete.setIcon(get_svg_icon("trash", size=14, color=COLOR_RED))
            btn_delete.setToolTip("Xóa an toàn sự kiện")
            btn_delete.setCursor(Qt.PointingHandCursor)
            btn_delete.setStyleSheet(cell_btn_style)
            btn_delete.clicked.connect(lambda _, n=ev_name: self._delete_event_dialog(n))
            h_action.addWidget(btn_delete)

            self.table_events.setCellWidget(row, 4, action_widget)

    def _on_search_text_changed(self, text: str):
        if hasattr(self, "_all_events_cache"):
            self._render_events_table(self._all_events_cache)

    def _on_event_row_selected(self):
        row = self.table_events.currentRow()
        if row >= 0:
            item = self.table_events.item(row, 0)
            if item:
                raw_text = item.text()
                # Clean prefix/suffix
                clean_name = raw_text.replace("● ", "").replace(" [ĐANG CHẠY]", "").strip()
                self.selected_event_name = clean_name
                self.lbl_gallery_event_title.setText(f"Thư viện ảnh: {clean_name}")
                self._refresh_gallery(clean_name)

    # =========================================================================
    # EVENT OPERATIONS
    # =========================================================================
    def _create_new_event_from_input(self):
        name = self.txt_new_event.text().strip()
        if not name:
            QMessageBox.warning(self, "Thông Báo", "Vui lòng nhập tên sự kiện mới.")
            return

        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Tạo Sự Kiện Mới"):
                return

        safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name)
        success = self.event_mgr.create_event(safe_name)
        if success:
            self.event_mgr.set_active_event(safe_name)
            self.selected_event_name = safe_name
            self.txt_new_event.clear()
            self._load_all_events()
            QMessageBox.information(self, "Thành Công", f"Đã tạo và kích hoạt sự kiện mới: {safe_name}")
        else:
            QMessageBox.warning(self, "Lỗi", f"Sự kiện '{safe_name}' đã tồn tại hoặc tên không hợp lệ.")

    def _switch_to_event(self, ev_name: str):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Chuyển Đổi Sự Kiện"):
                return

        self.event_mgr.set_active_event(ev_name)
        self.selected_event_name = ev_name
        self._load_all_events()

    def _prompt_switch_event(self):
        events = [e["name"] for e in self.event_mgr.list_events()]
        if not events:
            return
        cur = self.event_mgr.get_active_event_name()
        cur_idx = events.index(cur) if cur in events else 0

        choice, ok = QInputDialog.getItem(
            self, "Đổi Sự Kiện Đang Chạy",
            "Chọn sự kiện muốn kích hoạt cho quầy Photobooth:",
            events, cur_idx, False
        )
        if ok and choice and choice != cur:
            self._switch_to_event(choice)

    def _end_current_event(self):
        active_name = self.event_mgr.get_active_event_name()
        reply = QMessageBox.question(
            self,
            "Kết Thúc Sự Kiện",
            f"Bạn có chắc muốn kết thúc phiên làm việc của sự kiện:\n\n<b>{active_name}</b>\n\nQuầy sẽ chuyển về sự kiện mặc định hoặc cho phép tạo sự kiện mới.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.event_mgr.set_active_event("SuKien_MacDinh")
            self.selected_event_name = "SuKien_MacDinh"
            self._load_all_events()
            QMessageBox.information(self, "Đã Kết Thúc", "Đã kết thúc sự kiện và chuyển về SuKien_MacDinh.")

    def _open_storage_root(self):
        if os.path.exists(self.event_mgr.storage_root):
            os.startfile(self.event_mgr.storage_root)

    def _open_specific_folder(self, ev_name: str):
        folder = self.event_mgr.get_event_path(ev_name)
        if os.path.exists(folder):
            os.startfile(folder)

    def _rename_event_dialog(self, old_name: str):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Đổi Tên Sự Kiện"):
                return

        new_name, ok = QInputDialog.getText(
            self, "Đổi Tên Sự Kiện",
            f"Nhập tên mới cho sự kiện '{old_name}':",
            QLineEdit.Normal, old_name
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in new_name.strip())
            ok_rename = self.event_mgr.rename_event(old_name, safe_name)
            if ok_rename:
                self._load_all_events()
                QMessageBox.information(self, "Thành Công", f"Đã đổi tên sự kiện thành: {safe_name}")
            else:
                QMessageBox.warning(self, "Lỗi", "Không thể đổi tên sự kiện. Tên có thể đã tồn tại.")

    def _delete_event_dialog(self, ev_name: str):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Xóa Sự Kiện"):
                return

        reply = QMessageBox.warning(
            self,
            "Cảnh Báo Xóa Sự Kiện",
            f"Bạn có chắc chắn muốn XÓA TOÀN BỘ sự kiện:\n\n<b>{ev_name}</b>\n\nToàn bộ ảnh gốc và ảnh in trong thư mục này sẽ bị xóa vĩnh viễn khỏi máy tính!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.event_mgr.delete_event(ev_name)
            if success:
                self._load_all_events()
                QMessageBox.information(self, "Đã Xóa", f"Đã xóa an toàn sự kiện: {ev_name}")
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể xóa sự kiện này.")

    # =========================================================================
    # CLOUD SYNC & EXPORT
    # =========================================================================
    def _sync_all_to_gdrive(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Đồng Bộ Toàn Bộ Ảnh"):
                return
        if not self.sync_mgr or not self.sync_mgr.is_ready():
            QMessageBox.warning(
                self,
                "Google Drive Chưa Kết Nối",
                "Google Drive chưa được cấu hình hoặc chưa đăng nhập.\nVui lòng vào tab 'Cài Đặt' để kết nối tài khoản hoặc bật Giả Lập."
            )
            return

        ev_name = self.selected_event_name or self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(ev_name)
        final_dir = dirs["final"]

        count = self.sync_mgr.sync_all_event_photos(ev_name, final_dir)
        if count > 0:
            QMessageBox.information(
                self,
                "Bắt Đầu Đồng Bộ",
                f"Đã đưa {count} ảnh thành phẩm của '{ev_name}' vào hàng đợi ngầm Google Drive!\nTiến trình đồng bộ đang chạy nền không làm gián đoạn chụp ảnh."
            )
        else:
            QMessageBox.information(
                self,
                "Đồng Bộ Hoàn Tất",
                f"Tất cả ảnh trong sự kiện '{ev_name}' đã được tải lên Google Drive từ trước!"
            )
        self._refresh_gallery(ev_name)

    def _export_event_zip(self):
        ev_name = self.selected_event_name or self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(ev_name)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Xuất File ZIP Sự Kiện", f"{ev_name}_photos.zip", "ZIP Archives (*.zip)"
        )
        if save_path:
            try:
                base_dir = dirs["base"]
                shutil.make_archive(save_path.replace(".zip", ""), "zip", base_dir)
                QMessageBox.information(self, "Thành Công", f"Đã xuất nén toàn bộ ảnh sự kiện vào:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xuất file ZIP: {e}")

    # =========================================================================
    # GALLERY & REPRINT & QR
    # =========================================================================
    def _refresh_gallery(self, ev_name: Optional[str] = None):
        target_name = ev_name or self.selected_event_name or self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(target_name)
        final_dir = dirs["final"]

        self.table_sessions.setRowCount(0)
        if not os.path.exists(final_dir):
            if hasattr(self, "lbl_storage_stats"):
                self.lbl_storage_stats.setText("• 0 lượt chụp")
            return

        files = [f for f in os.listdir(final_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        total_sessions = len(files)

        # Cập nhật thông tin dung lượng đĩa và cảnh báo
        disk_info = self.event_mgr.check_disk_space(2.0)
        free_gb = disk_info.get("free_gb", 0.0)
        warning = disk_info.get("is_low", False)
        disk_str = f"• {total_sessions} lượt chụp • Trống {free_gb} GB"
        if warning:
            disk_str += " ⚠️ (Dung lượng thấp!)"
        if hasattr(self, "lbl_storage_stats"):
            self.lbl_storage_stats.setText(disk_str)

        # Bộ lọc tìm kiếm lượt chụp
        q = ""
        if hasattr(self, "txt_search_session"):
            q = self.txt_search_session.text().strip().lower()

        for f in reversed(files):
            sess_id = f.replace("_final.jpg", "").replace("_final.png", "")
            fpath = os.path.join(final_dir, f)
            mtime = os.path.getmtime(fpath)
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")

            if q and (q not in sess_id.lower() and q not in time_str.lower() and q not in f.lower()):
                continue

            row = self.table_sessions.rowCount()
            self.table_sessions.insertRow(row)

            cloud_status_text = "Chỉ lưu máy"
            cloud_color = "#94A3B8"
            if self.sync_mgr:
                info = self.sync_mgr.get_file_info(fpath)
                if info:
                    st = info.get("status")
                    if st == SyncStatus.SYNCED:
                        cloud_status_text = "Đã tải lên Drive"
                        cloud_color = "#10B981"
                    elif st == SyncStatus.UPLOADING:
                        cloud_status_text = "Đang tải lên..."
                        cloud_color = "#F59E0B"
                    elif st == SyncStatus.FAILED:
                        cloud_status_text = "Tải thất bại (Thử lại)"
                        cloud_color = "#EF4444"
                elif self.sync_mgr.is_ready():
                    cloud_status_text = "Chờ đưa vào hàng đợi"
                    cloud_color = "#38BDF8"

            self.table_sessions.setItem(row, 0, QTableWidgetItem(sess_id))
            self.table_sessions.setItem(row, 1, QTableWidgetItem(f))
            self.table_sessions.setItem(row, 2, QTableWidgetItem(time_str))

            item_cloud = QTableWidgetItem(cloud_status_text)
            if cloud_color == "#10B981":
                item_cloud.setForeground(Qt.GlobalColor.green)
            elif cloud_color == "#EF4444":
                item_cloud.setForeground(Qt.GlobalColor.red)
            else:
                item_cloud.setForeground(Qt.GlobalColor.lightGray)
            self.table_sessions.setItem(row, 3, item_cloud)

            # Cột Thao Tác nhanh: Xem, In, QR
            act_w = QWidget()
            h_act = QHBoxLayout(act_w)
            h_act.setContentsMargins(4, 2, 4, 2)
            h_act.setSpacing(6)

            btn_v = QPushButton("Xem")
            btn_v.setCursor(Qt.PointingHandCursor)
            btn_v.setToolTip("Xem chi tiết ảnh lượt chụp (Lightbox)")
            btn_v.setStyleSheet("""
                QPushButton {
                    background-color: #FEF3C7;
                    border: 1.5px solid #FDE68A;
                    color: #92400E;
                    padding: 3px 10px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #FDE68A;
                    border-color: #D4AF37;
                }
            """)
            btn_v.clicked.connect(lambda _, r=row: self._preview_session_selected(r))
            h_act.addWidget(btn_v)

            btn_p = QPushButton("In")
            btn_p.setCursor(Qt.PointingHandCursor)
            btn_p.setToolTip("Gửi lệnh in lại ảnh thành phẩm")
            btn_p.setStyleSheet("""
                QPushButton {
                    background-color: #EFF6FF;
                    border: 1.5px solid #BFDBFE;
                    color: #1E40AF;
                    padding: 3px 10px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #DBEAFE;
                    border-color: #3B82F6;
                }
            """)
            btn_p.clicked.connect(lambda _, fp=fpath, fn=f: self._reprint_file(fp, fn))
            h_act.addWidget(btn_p)

            btn_q = QPushButton("QR")
            btn_q.setCursor(Qt.PointingHandCursor)
            btn_q.setToolTip("Xem lại mã QR chia sẻ trực tuyến & LAN")
            btn_q.setStyleSheet("""
                QPushButton {
                    background-color: #ECFDF5;
                    border: 1.5px solid #A7F3D0;
                    color: #065F46;
                    padding: 3px 10px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #D1FAE5;
                    border-color: #10B981;
                }
            """)
            btn_q.clicked.connect(lambda _, s=sess_id, fp=fpath: self._show_qr_for_session(s, fp))
            h_act.addWidget(btn_q)

            self.table_sessions.setCellWidget(row, 4, act_w)

    def _preview_session_selected(self, row: Optional[int] = None):
        """Mở cửa sổ xem trước (Photo Lightbox) chi tiết cho lượt chụp đang chọn."""
        target_row = row if row is not None else self.table_sessions.currentRow()
        if target_row < 0:
            QMessageBox.warning(self, "Thông Báo", "Vui lòng chọn một lượt chụp trong bảng để xem trước.")
            return

        sess_item = self.table_sessions.item(target_row, 0)
        if not sess_item:
            return
        sess_id = sess_item.text().strip()
        target_name = self.selected_event_name or self.event_mgr.get_active_event_name()

        dlg = SessionLightboxDialog(
            session_id=sess_id,
            event_name=target_name,
            event_mgr=self.event_mgr,
            print_mgr=self.print_mgr,
            token_mgr=self.token_mgr,
            sync_mgr=self.sync_mgr,
            parent=self
        )
        dlg.exec()

    def _reprint_file(self, fpath: str, fname: str):
        if os.path.exists(fpath):
            self.print_mgr.print_image(fpath, copies=1)
            QMessageBox.information(self, "In Lại", f"Đã gửi lệnh in lại lượt: {fname}")

    def _show_qr_for_session(self, sess_id: str, fpath: str):
        fname = os.path.basename(fpath)
        target_name = self.selected_event_name or self.event_mgr.get_active_event_name()

        # LAN URL
        token_info = self.token_mgr.create_token(target_name, sess_id)
        lan_url = self.token_mgr.get_sharing_url(token_info.token)

        # Google Drive URL
        gdrive_url = None
        if self.sync_mgr:
            info = self.sync_mgr.get_file_info(fpath)
            if info and info.get("status") == SyncStatus.SYNCED:
                gdrive_url = info.get("web_link")

        self._open_qr_dialog_ui(sess_id, fpath, target_name, lan_url, gdrive_url)

    def _reprint_selected(self):
        row = self.table_sessions.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Thông Báo", "Vui lòng chọn một lượt chụp trong bảng để in lại.")
            return

        fname = self.table_sessions.item(row, 1).text()
        target_name = self.selected_event_name or self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(target_name)
        fpath = os.path.join(dirs["final"], fname)
        self._reprint_file(fpath, fname)

    def _show_qr_selected(self):
        row = self.table_sessions.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Thông Báo", "Vui lòng chọn một lượt chụp trong bảng để xem mã QR.")
            return

        fname = self.table_sessions.item(row, 1).text()
        sess_id = self.table_sessions.item(row, 0).text()
        target_name = self.selected_event_name or self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(target_name)
        fpath = os.path.join(dirs["final"], fname)
        self._show_qr_for_session(sess_id, fpath)

    def _open_qr_dialog_ui(self, sess_id: str, fpath: str, target_name: str, lan_url: str, gdrive_url: Optional[str]):

        # QR Modal Dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Quét Mã QR Nhận Ảnh")
        dlg.setFixedSize(480, 580)
        dlg.setStyleSheet("background-color: #FFFFFF; color: #303746;")
        layout = QVBoxLayout(dlg)

        title = QLabel(f"Lượt Chụp: <b>{sess_id}</b>")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E40AF;")
        layout.addWidget(title)

        tabs_qr = QTabWidget()

        # Tab 1: Google Drive Online
        tab_cloud = QWidget()
        l_cloud = QVBoxLayout(tab_cloud)
        if gdrive_url:
            qr_cloud_img = qrcode.make(gdrive_url)
            lbl_qr_c = QLabel()
            lbl_qr_c.setAlignment(Qt.AlignCenter)
            rgb = qr_cloud_img.convert("RGB")
            w, h = rgb.size
            data = rgb.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
            lbl_qr_c.setPixmap(QPixmap.fromImage(qimg).scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            l_cloud.addWidget(lbl_qr_c)

            lbl_c_desc = QLabel("Quét để xem và tải ảnh gốc trực tiếp qua mạng 4G/Internet.")
            lbl_c_desc.setAlignment(Qt.AlignCenter)
            lbl_c_desc.setStyleSheet("color: #059669; font-weight: bold; font-size: 12px;")
            l_cloud.addWidget(lbl_c_desc)

            lbl_c_link = QLabel(f"<a href='{gdrive_url}' style='color:#1E40AF;'>Mở liên kết Drive</a>")
            lbl_c_link.setOpenExternalLinks(True)
            lbl_c_link.setAlignment(Qt.AlignCenter)
            l_cloud.addWidget(lbl_c_link)
        else:
            lbl_notice = QLabel("Ảnh này chưa tải lên Google Drive.\nBạn có thể bấm 'Đồng Bộ Lên Drive' để tải lên ngay.")
            lbl_notice.setAlignment(Qt.AlignCenter)
            lbl_notice.setStyleSheet("color: #64748B; font-size: 13px; line-height: 1.5;")
            l_cloud.addWidget(lbl_notice)

            btn_sync_now = QPushButton(" Tải Lên Google Drive Ngay")
            btn_sync_now.setIcon(get_svg_icon("cloud", size=16, color=COLOR_NAVY))
            btn_sync_now.setObjectName("btn_champagne")
            btn_sync_now.clicked.connect(lambda: self._trigger_single_sync(fpath, target_name, dlg))
            l_cloud.addWidget(btn_sync_now)

        tabs_qr.addTab(tab_cloud, " Google Drive (Online 4G)")

        # Tab 2: LAN WiFi
        tab_lan = QWidget()
        l_lan = QVBoxLayout(tab_lan)

        qr_lan_img = qrcode.make(lan_url)
        lbl_qr_l = QLabel()
        lbl_qr_l.setAlignment(Qt.AlignCenter)
        rgb_l = qr_lan_img.convert("RGB")
        w_l, h_l = rgb_l.size
        data_l = rgb_l.tobytes("raw", "RGB")
        qimg_l = QImage(data_l, w_l, h_l, 3 * w_l, QImage.Format_RGB888)
        lbl_qr_l.setPixmap(QPixmap.fromImage(qimg_l).scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        l_lan.addWidget(lbl_qr_l)

        lbl_l_desc = QLabel("Khách kết nối cùng mạng WiFi với quầy Photobooth để tải ảnh.")
        lbl_l_desc.setAlignment(Qt.AlignCenter)
        lbl_l_desc.setStyleSheet("color: #64748B; font-size: 12px;")
        l_lan.addWidget(lbl_l_desc)

        lbl_l_link = QLabel(lan_url)
        lbl_l_link.setAlignment(Qt.AlignCenter)
        lbl_l_link.setStyleSheet("color: #1E40AF; font-size: 11px; font-weight: bold;")
        l_lan.addWidget(lbl_l_link)

        tabs_qr.addTab(tab_lan, " Mạng LAN (WiFi Nội Bộ)")
        layout.addWidget(tabs_qr)

        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("btn_secondary")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        dlg.exec()

    def _trigger_single_sync(self, fpath: str, ev_name: str, parent_dlg: QDialog):
        if self.sync_mgr and self.sync_mgr.is_ready():
            self.sync_mgr.enqueue(fpath, ev_name)
            parent_dlg.accept()
            QMessageBox.information(self, "Đã Đưa Vào Hàng Đợi", "Đã đưa ảnh vào hàng đợi đồng bộ Google Drive.")
            self._refresh_gallery(ev_name)
        else:
            QMessageBox.warning(self, "Chưa Sẵn Sàng", "Google Drive chưa sẵn sàng. Vui lòng vào Cài Đặt để kết nối.")
