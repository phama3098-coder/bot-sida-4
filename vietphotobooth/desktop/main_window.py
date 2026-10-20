"""
VietPhotoBooth Main Window Application
Native PySide6/Qt6 Windows desktop interface, fullscreen kiosk mode, PIN protection,
and integrated management pages.
"""

import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QMessageBox, QInputDialog, QLineEdit, QTabBar
)
from PySide6.QtCore import Qt, QKeyCombination
from PySide6.QtGui import QIcon, QKeySequence, QShortcut

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.logger import get_logger
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.filters.filter_engine import FilterEngine
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager

from vietphotobooth.desktop.styles import KIOSK_STYLE
from vietphotobooth.desktop.widgets.kiosk_page import KioskPage
from vietphotobooth.desktop.widgets.filter_editor_page import FilterEditorPage
from vietphotobooth.desktop.widgets.frame_designer_page import FrameDesignerPage
from vietphotobooth.desktop.widgets.camera_page import CameraPage
from vietphotobooth.desktop.widgets.printing_page import PrintingPage
from vietphotobooth.desktop.widgets.events_page import EventsPage
from vietphotobooth.desktop.widgets.settings_page import SettingsPage

logger = get_logger()

class MainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng Desktop VietPhotoBooth."""

    def __init__(self, start_in_kiosk: bool = False):
        super().__init__()
        self.setWindowTitle("VietPhotoBooth — Phần Mềm Photobooth Chuyên Nghiệp Windows")
        self.setMinimumSize(1024, 720)

        # 1. Khởi tạo các hệ thống lõi
        self.config_mgr = ConfigManager()
        self.event_mgr = EventManager()
        self.camera_mgr = CameraManager()
        self.filter_engine = FilterEngine()
        self.frame_mgr = FrameManager()
        self.print_mgr = PrintManager()
        self.token_mgr = TokenManager()

        # Áp dụng giao diện cảm ứng Kiosk Dark Theme
        self.setStyleSheet(KIOSK_STYLE)

        self._init_ui()
        self._setup_shortcuts()

        if start_in_kiosk:
            self.toggle_fullscreen()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tab Widget quản lý các phân hệ
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 1. Màn hình Kiosk Photobooth
        self.kiosk_page = KioskPage(
            camera_mgr=self.camera_mgr,
            filter_engine=self.filter_engine,
            frame_mgr=self.frame_mgr,
            print_mgr=self.print_mgr,
            event_mgr=self.event_mgr,
            token_mgr=self.token_mgr,
            config_mgr=self.config_mgr
        )
        self.tabs.addTab(self.kiosk_page, "📸 Chụp Ảnh (Kiosk)")

        # 2. Bộ Chỉnh Sửa Bộ Lọc Màu
        self.filter_page = FilterEditorPage(self.filter_engine)
        self.filter_page.preset_changed.connect(lambda pid: self.kiosk_page._load_initial_templates())
        self.tabs.addTab(self.filter_page, "🎨 Bộ Lọc Màu (Filter Studio)")

        # 3. Trình Thiết Kế Khung Ảnh
        self.frame_page = FrameDesignerPage(self.frame_mgr)
        self.frame_page.frame_changed.connect(lambda fid: self.kiosk_page._load_initial_templates())
        self.tabs.addTab(self.frame_page, "🖼️ Khung Ảnh (Frame Designer)")

        # 4. Quản Lý Máy Ảnh
        self.camera_page = CameraPage(self.camera_mgr)
        self.tabs.addTab(self.camera_page, "📷 Máy Ảnh")

        # 5. Quản Lý Máy In
        self.printing_page = PrintingPage(self.print_mgr)
        self.tabs.addTab(self.printing_page, "🖨️ Máy In")

        # 6. Sự Kiện & Thư Viện
        self.events_page = EventsPage(self.event_mgr, self.print_mgr, self.token_mgr)
        self.tabs.addTab(self.events_page, "📁 Sự Kiện & Thư Viện")

        # 7. Cài Đặt Hệ Thống
        self.settings_page = SettingsPage(self.config_mgr, self.token_mgr)
        self.settings_page.toggle_fullscreen_requested.connect(self.toggle_fullscreen)
        self.tabs.addTab(self.settings_page, "⚙️ Cài Đặt")

        # Bảo mật PIN khi chuyển từ Kiosk sang tab Quản Trị
        self.tabs.tabBarClicked.connect(self._on_tab_bar_clicked)

        main_layout.addWidget(self.tabs)

    def _setup_shortcuts(self):
        # F11 để bật/tắt chế độ toàn màn hình Kiosk
        shortcut_f11 = QShortcut(QKeySequence("F11"), self)
        shortcut_f11.activated.connect(self.toggle_fullscreen)

        # Esc để yêu cầu thoát Kiosk (nếu có PIN)
        shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        shortcut_esc.activated.connect(self._handle_escape_kiosk)

    def _on_tab_bar_clicked(self, target_index: int):
        current_index = self.tabs.currentIndex()
        # Nếu đang ở tab Kiosk (0) và muốn chuyển sang tab quản trị (1..6)
        if current_index == 0 and target_index > 0:
            if not self._verify_admin_pin():
                # Chặn không cho đổi tab
                self.tabs.setCurrentIndex(0)

    def _verify_admin_pin(self) -> bool:
        pin, ok = QInputDialog.getText(
            self,
            "Xác Thực Quyền Quản Trị",
            "Nhập mã PIN quản trị viên (Mặc định: 1234):",
            QLineEdit.Password
        )
        if not ok:
            return False

        if self.config_mgr.verify_pin(pin):
            return True
        else:
            QMessageBox.critical(self, "Lỗi Xác Thực", "Mã PIN không chính xác!")
            return False

    def toggle_fullscreen(self):
        """Bật/tắt chế độ toàn màn hình Kiosk Mode."""
        if self.isFullScreen():
            if self._verify_admin_pin():
                self.showNormal()
                self.tabs.tabBar().show()
        else:
            self.showFullScreen()
            # Ở chế độ Kiosk toàn màn hình, chuyển về tab Chụp Ảnh
            self.tabs.setCurrentIndex(0)

    def _handle_escape_kiosk(self):
        if self.isFullScreen():
            self.toggle_fullscreen()

    def closeEvent(self, event):
        """Dừng các luồng an toàn khi đóng ứng dụng."""
        self.kiosk_page.stop_live_view()
        self.camera_mgr.close()
        event.accept()
