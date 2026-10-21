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
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QPixmap

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.logger import get_logger
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.filters.filter_engine import FilterEngine
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.cloud import SyncManager

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
    """Cửa sổ chính của ứng dụng Desktop 1998 TEAM — Photobooth."""

    def __init__(self, start_in_kiosk: bool = False):
        super().__init__()
        self.setWindowTitle("1998 TEAM — Photobooth")
        self.setMinimumSize(1024, 720)

        # Cài đặt biểu tượng icon ứng dụng chính thức
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Branding", "app_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 1. Khởi tạo các hệ thống lõi
        self.config_mgr = ConfigManager()
        self.event_mgr = EventManager()
        self.camera_mgr = CameraManager()
        self.filter_engine = FilterEngine()
        self.frame_mgr = FrameManager()
        self.print_mgr = PrintManager()
        self.token_mgr = TokenManager(port=int(self.config_mgr.get("lan_server_port", 8080)))
        self.sync_mgr = SyncManager(self.config_mgr)

        # Tối ưu hóa font chữ Windows cho tiếng Việt và emoji chuẩn
        from PySide6.QtGui import QFontDatabase, QFont
        for fpath in (
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/seguiemj.ttf",
            "C:/Windows/Fonts/seguisym.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ):
            if os.path.exists(fpath):
                QFontDatabase.addApplicationFont(fpath)

        QFont.insertSubstitution("Segoe UI", "Segoe UI Emoji")
        QFont.insertSubstitution("Segoe UI", "Segoe UI Symbol")

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

        # Tab Widget quản lý các phân hệ theo thứ tự yêu cầu:
        # Chụp ảnh, Khung ảnh, Máy ảnh, Máy in, Sự kiện & Thư viện, Cài đặt
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(Qt.ElideRight)
        self.tabs.tabBar().setExpanding(False)

        # Thanh thương hiệu Logo 1998 Studio bên trái hàng tab (Co giãn thông minh)
        logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Branding", "logo_1998_studio.png"))
        self.brand_widget = QWidget()
        self.brand_widget.setMaximumWidth(260)
        self.brand_layout = QHBoxLayout(self.brand_widget)
        self.brand_layout.setContentsMargins(10, 2, 8, 2)
        self.brand_layout.setSpacing(8)

        self.lbl_logo = QLabel()
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            self.lbl_logo.setPixmap(pix.scaledToHeight(38, Qt.SmoothTransformation))
        else:
            self.lbl_logo.setText("1998 STUDIO")
            self.lbl_logo.setStyleSheet("color: #D4AF37; font-weight: bold; font-size: 16px;")
        self.brand_layout.addWidget(self.lbl_logo)

        self.lbl_title = QLabel("<b>1998 TEAM</b> — Photobooth")
        self.lbl_title.setStyleSheet("color: #F7E7CE; font-size: 15px; font-weight: bold;")
        self.brand_layout.addWidget(self.lbl_title)

        self.tabs.setCornerWidget(self.brand_widget, Qt.TopLeftCorner)

        # 1. Chụp ảnh (Kiosk Photobooth)
        self.kiosk_page = KioskPage(
            camera_mgr=self.camera_mgr,
            filter_engine=self.filter_engine,
            frame_mgr=self.frame_mgr,
            print_mgr=self.print_mgr,
            event_mgr=self.event_mgr,
            token_mgr=self.token_mgr,
            config_mgr=self.config_mgr,
            sync_mgr=self.sync_mgr
        )
        self.kiosk_page.request_tab_switch.connect(self.switch_to_tab)
        self.kiosk_page.request_fullscreen.connect(self.toggle_fullscreen)
        self.tabs.addTab(self.kiosk_page, "📸 Chụp Ảnh")
        self.tabs.setTabToolTip(0, "Chụp ảnh Photobooth (Kiosk)")

        # 2. Khung ảnh (Trình Thiết Kế Khung Ảnh)
        self.frame_page = FrameDesignerPage(self.frame_mgr)
        self.frame_page.frame_changed.connect(lambda fid: self.kiosk_page._load_frame_options())
        self.tabs.addTab(self.frame_page, "🖼️ Khung Ảnh")
        self.tabs.setTabToolTip(1, "Trình thiết kế khung in ảnh")

        # 3. Máy ảnh (Quản Lý Máy Ảnh & Thiết Lập Cảm Biến)
        self.camera_page = CameraPage(self.camera_mgr)
        self.tabs.addTab(self.camera_page, "📷 Máy Ảnh")
        self.tabs.setTabToolTip(2, "Cấu hình thiết bị máy ảnh")

        # 4. Máy in (Quản Lý Máy In & Driver In Nhiệt)
        self.printing_page = PrintingPage(self.print_mgr)
        self.tabs.addTab(self.printing_page, "🖨️ Máy In")
        self.tabs.setTabToolTip(3, "Cấu hình máy in & hàng đợi in")

        # 5. Sự kiện & Thư viện (Quản Lý Album, Mã QR, Sự Kiện)
        self.events_page = EventsPage(self.event_mgr, self.print_mgr, self.token_mgr, sync_mgr=self.sync_mgr)
        self.tabs.addTab(self.events_page, "📁 Sự Kiện & Thư Viện")
        self.tabs.setTabToolTip(4, "Quản lý sự kiện & thư viện ảnh")

        # 6. Cài đặt (Bảo Mật PIN, Kiosk, Quản Lý Bộ Lọc Màu & Bản Quyền)
        self.settings_page = SettingsPage(self.config_mgr, self.token_mgr, self.filter_engine, sync_mgr=self.sync_mgr)
        self.settings_page.toggle_fullscreen_requested.connect(self.toggle_fullscreen)
        self.tabs.addTab(self.settings_page, "⚙️ Cài Đặt")
        self.tabs.setTabToolTip(5, "Cài đặt hệ thống, bảo mật & Google Drive")

        # Bảo mật PIN khi chuyển từ Kiosk sang tab Quản Trị
        self.tabs.tabBarClicked.connect(self._on_tab_bar_clicked)

        main_layout.addWidget(self.tabs)

    def switch_to_tab(self, target_index: int):
        """Chuyển tab theo yêu cầu từ các trang con (kiểm tra mã PIN nếu rời Kiosk)."""
        if self.tabs.currentIndex() == 0 and target_index > 0:
            if not self._verify_admin_pin():
                return
        self.tabs.setCurrentIndex(target_index)

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
            # Ở chế độ Kiosk toàn màn hình, chuyển về tab Chụp Ảnh và ẩn thanh Tab bar
            self.tabs.setCurrentIndex(0)
            self.tabs.tabBar().hide()

    def _handle_escape_kiosk(self):
        if self.isFullScreen():
            self.toggle_fullscreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_navigation(event.size().width())

    def _update_responsive_navigation(self, width: int):
        if not hasattr(self, "brand_widget") or not hasattr(self, "tabs"):
            return

        if width < 1000:
            self.lbl_title.setText("<b>1998 TEAM</b>")
            self.brand_widget.setMaximumWidth(160)
            self.tabs.setTabText(0, "📸 Chụp")
            self.tabs.setTabText(1, "🖼️ Khung")
            self.tabs.setTabText(2, "📷 Máy")
            self.tabs.setTabText(3, "🖨️ In")
            self.tabs.setTabText(4, "📁 Sự Kiện")
            self.tabs.setTabText(5, "⚙️ Cài Đặt")
        else:
            self.lbl_title.setText("<b>1998 TEAM</b> — Photobooth")
            self.brand_widget.setMaximumWidth(260)
            self.tabs.setTabText(0, "📸 Chụp Ảnh")
            self.tabs.setTabText(1, "🖼️ Khung Ảnh")
            self.tabs.setTabText(2, "📷 Máy Ảnh")
            self.tabs.setTabText(3, "🖨️ Máy In")
            self.tabs.setTabText(4, "📁 Sự Kiện & Thư Viện")
            self.tabs.setTabText(5, "⚙️ Cài Đặt")

    def closeEvent(self, event):
        """Dừng các luồng an toàn khi đóng ứng dụng."""
        if hasattr(self.kiosk_page, "live_view_worker"):
            self.kiosk_page.live_view_worker.stop()
        self.kiosk_page.stop_live_view()
        if hasattr(self, "sync_mgr"):
            self.sync_mgr.close()
        self.camera_mgr.close()
        event.accept()
