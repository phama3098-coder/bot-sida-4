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
from PySide6.QtCore import Qt, QKeyCombination, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QPixmap

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.logger import get_logger
from vietphotobooth.core.auth import AdminAuthManager
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
from vietphotobooth.version import __version__, get_version_string
from vietphotobooth.updates import UpdateManager, UpdateNotificationDialog, UpdateProgressDialog

logger = get_logger()

class MainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng Desktop 1998 TEAM — Photobooth."""

    def __init__(self, start_in_kiosk: bool = False):
        super().__init__()
        self.setWindowTitle("1998 TEAM — Photobooth")
        self.setMinimumSize(1024, 680)

        # Cài đặt biểu tượng icon ứng dụng chính thức
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Branding", "app_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 1. Khởi tạo các hệ thống lõi
        self.config_mgr = ConfigManager()
        self.auth_mgr = AdminAuthManager(self.config_mgr, self)
        self._switching_tabs: bool = False
        self._prev_tab_index: int = 0
        self.PROTECTED_TABS = {2, 3, 4, 5}  # 2: Máy ảnh, 3: Máy in, 4: Sự kiện, 5: Cài đặt (Khung ảnh 1 hoàn toàn tự do)
        self.event_mgr = EventManager()
        self.camera_mgr = CameraManager()
        self.filter_engine = FilterEngine()
        self.frame_mgr = FrameManager()
        self.print_mgr = PrintManager()
        self.token_mgr = TokenManager(port=int(self.config_mgr.get("lan_server_port", 8080)))
        self.sync_mgr = SyncManager(self.config_mgr)
        self.update_mgr = UpdateManager(self.config_mgr, self)

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

        self.lbl_ver = QLabel(f"v{__version__}")
        self.lbl_ver.setStyleSheet("color: #64748B; font-size: 11px; font-weight: bold; padding-top: 3px;")
        self.lbl_ver.setToolTip(f"Phiên bản: {get_version_string()}")
        self.brand_layout.addWidget(self.lbl_ver)

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
        self.camera_page = CameraPage(self.camera_mgr, auth_mgr=self.auth_mgr)
        self.tabs.addTab(self.camera_page, "📷 Máy Ảnh")
        self.tabs.setTabToolTip(2, "Cấu hình thiết bị máy ảnh")

        # 4. Máy in (Quản Lý Máy In & Driver In Nhiệt)
        self.printing_page = PrintingPage(self.print_mgr, auth_mgr=self.auth_mgr)
        self.tabs.addTab(self.printing_page, "🖨️ Máy In")
        self.tabs.setTabToolTip(3, "Cấu hình máy in & hàng đợi in")

        # 5. Sự kiện & Thư viện (Quản Lý Album, Mã QR, Sự Kiện)
        self.events_page = EventsPage(self.event_mgr, self.print_mgr, self.token_mgr, sync_mgr=self.sync_mgr, auth_mgr=self.auth_mgr)
        self.tabs.addTab(self.events_page, "📁 Sự Kiện & Thư Viện")
        self.tabs.setTabToolTip(4, "Quản lý sự kiện & thư viện ảnh")

        # 6. Cài đặt (Bảo Mật PIN, Kiosk, Quản Lý Bộ Lọc Màu & Bản Quyền)
        self.settings_page = SettingsPage(
            self.config_mgr,
            self.token_mgr,
            self.filter_engine,
            sync_mgr=self.sync_mgr,
            auth_mgr=self.auth_mgr,
            update_mgr=self.update_mgr
        )
        self.settings_page.toggle_fullscreen_requested.connect(self.toggle_fullscreen)
        self.tabs.addTab(self.settings_page, "⚙️ Cài Đặt")
        self.tabs.setTabToolTip(5, "Cài đặt hệ thống, bảo mật & Google Drive")

        # Nút trạng thái khóa bảo mật Quản trị viên ở góc trên bên phải thanh Tab
        self.auth_widget = QWidget()
        auth_layout = QHBoxLayout(self.auth_widget)
        auth_layout.setContentsMargins(4, 2, 10, 2)
        auth_layout.setSpacing(6)

        self.btn_auth_status = QPushButton("🔒 Đang Khóa")
        self.btn_auth_status.setFixedHeight(30)
        self.btn_auth_status.setCursor(Qt.PointingHandCursor)
        self.btn_auth_status.setToolTip("Nhấp để mở khóa quyền quản trị hoặc khóa bảo vệ ngay lập tức")
        self.btn_auth_status.clicked.connect(self._toggle_auth_button_clicked)
        auth_layout.addWidget(self.btn_auth_status)

        self.tabs.setCornerWidget(self.auth_widget, Qt.TopRightCorner)

        # Bộ đếm thời gian kiểm tra phiên quản trị (Session Timeout)
        self.auth_timer = QTimer(self)
        self.auth_timer.setInterval(1000)
        self.auth_timer.timeout.connect(self._on_auth_timer_tick)
        self.auth_timer.start()

        # Giám sát chuyển tab để bảo vệ các mục: Máy ảnh (2), Máy in (3), Sự kiện (4), Cài đặt (5)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.auth_mgr.auth_state_changed.connect(lambda _: self._update_auth_ui())
        self._update_auth_ui()

        # Tự động kiểm tra bản cập nhật mới khi mở ứng dụng (chạy ngầm không giật lag)
        self.update_mgr.check_completed.connect(self._on_auto_update_checked)
        if self.update_mgr.is_auto_check_enabled:
            QTimer.singleShot(2500, self._start_auto_update_check)

        main_layout.addWidget(self.tabs)

    def _start_auto_update_check(self):
        """Khởi chạy kiểm tra cập nhật ngầm nếu cửa sổ đang hoạt động."""
        if self.isVisible():
            self.update_mgr.check_for_updates(manual=False)

    def _on_auto_update_checked(self, has_update: bool, manifest, msg: str):
        """Hiển thị thông báo khi có bản cập nhật mới."""
        if has_update and manifest and self.isVisible():
            self._update_dlg = UpdateNotificationDialog(manifest, self.update_mgr, self)
            self._update_dlg.update_requested.connect(self._start_download_flow)
            self._update_dlg.show()

    def _start_download_flow(self, manifest):
        """Mở tiến trình tải và kiểm tra chữ ký SHA-256."""
        self._progress_dlg = UpdateProgressDialog(manifest, self.update_mgr, self)
        self.update_mgr.start_download(manifest)
        self._progress_dlg.show()

    def _update_auth_ui(self):
        if not hasattr(self, "btn_auth_status"):
            return
        if not self.auth_mgr.is_pin_enabled:
            self.btn_auth_status.setText("🔓 Không Khóa PIN")
            self.btn_auth_status.setStyleSheet(
                "QPushButton { background-color: #0E1A2F; color: #94A3B8; border: 1px solid #1E2D4A; "
                "border-radius: 6px; padding: 2px 10px; font-weight: bold; font-size: 11px; }"
            )
        elif self.auth_mgr.is_authenticated():
            rem = self.auth_mgr.get_remaining_seconds()
            m, s = divmod(rem, 60)
            self.btn_auth_status.setText(f"🔓 Quản Trị ({m:02d}:{s:02d}) | Khóa")
            self.btn_auth_status.setStyleSheet(
                "QPushButton { background-color: #052618; color: #10B981; border: 1.5px solid #10B981; "
                "border-radius: 6px; padding: 2px 10px; font-weight: bold; font-size: 11px; }"
                "QPushButton:hover { background-color: #073824; }"
            )
        else:
            self.btn_auth_status.setText("🔒 Khóa Quản Trị")
            self.btn_auth_status.setStyleSheet(
                "QPushButton { background-color: #1A1308; color: #D4AF37; border: 1.5px solid #D4AF37; "
                "border-radius: 6px; padding: 2px 10px; font-weight: bold; font-size: 11px; }"
                "QPushButton:hover { background-color: #291E0D; color: #F7E7CE; }"
            )

    def _on_auth_timer_tick(self):
        if self.auth_mgr.is_authenticated():
            self._update_auth_ui()
            if self.auth_mgr.get_remaining_seconds() <= 0:
                self.auth_mgr.lock()
                self._update_auth_ui()
                if self.tabs.currentIndex() in self.PROTECTED_TABS:
                    self._switching_tabs = True
                    self.tabs.setCurrentIndex(0)
                    self._prev_tab_index = 0
                    self._switching_tabs = False
                    QMessageBox.information(
                        self, "Phiên Quản Trị",
                        "Phiên quản trị viên đã hết thời gian hiệu lực. Hệ thống đã tự động khóa lại để bảo vệ thiết bị."
                    )

    def _toggle_auth_button_clicked(self):
        if not self.auth_mgr.is_pin_enabled:
            QMessageBox.information(self, "Bảo Mật", "Chế độ mã PIN đang được tắt trong mục Cài Đặt.")
            return

        if self.auth_mgr.is_authenticated():
            ret = QMessageBox.question(
                self, "Khóa Quản Trị",
                "Bạn có muốn chủ động khóa phiên quản trị ngay bây giờ không?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret == QMessageBox.Yes:
                self.auth_mgr.lock()
                if self.tabs.currentIndex() in self.PROTECTED_TABS:
                    self._switching_tabs = True
                    self.tabs.setCurrentIndex(0)
                    self._prev_tab_index = 0
                    self._switching_tabs = False
        else:
            self.auth_mgr.prompt_pin_dialog(self, "Mở Khóa Quản Trị Viên")

    def _on_tab_changed(self, new_index: int):
        if self._switching_tabs:
            return

        # Chỉ bảo vệ các tab: 2 (Máy ảnh), 3 (Máy in), 4 (Sự kiện), 5 (Cài đặt)
        # Tab 0 (Chụp ảnh) và Tab 1 (Khung ảnh) hoàn toàn tự do
        if new_index in self.PROTECTED_TABS:
            if not self.auth_mgr.is_authenticated():
                ok = self.auth_mgr.prompt_pin_dialog(self, f"Mở Khóa Tab: {self.tabs.tabText(new_index)}")
                if not ok:
                    # Trở về tab an toàn trước đó
                    self._switching_tabs = True
                    self.tabs.setCurrentIndex(self._prev_tab_index)
                    self._switching_tabs = False
                    return

        self._prev_tab_index = new_index

    def switch_to_tab(self, target_index: int):
        """Chuyển tab theo yêu cầu từ các trang con (kiểm tra quyền quản trị)."""
        if target_index in self.PROTECTED_TABS:
            if not self.auth_mgr.is_authenticated():
                if not self.auth_mgr.prompt_pin_dialog(self, f"Mở Khóa Tab: {self.tabs.tabText(target_index)}"):
                    return
        self._prev_tab_index = target_index
        self.tabs.setCurrentIndex(target_index)

    def toggle_fullscreen(self):
        """Bật/tắt chế độ toàn màn hình Kiosk Mode."""
        if self.isFullScreen():
            if self.auth_mgr.is_pin_enabled and not self.auth_mgr.is_authenticated():
                if not self.auth_mgr.prompt_pin_dialog(self, "Thoát Chế Độ Kiosk"):
                    return
            self.showNormal()
            self.tabs.tabBar().show()
        else:
            self.showFullScreen()
            # Ở chế độ Kiosk toàn màn hình, chuyển về tab Chụp Ảnh và ẩn thanh Tab bar
            self.tabs.setCurrentIndex(0)
            self.tabs.tabBar().hide()
            self.tabs.tabBar().hide()

    def _setup_shortcuts(self):
        # F11 để bật/tắt chế độ toàn màn hình Kiosk
        shortcut_f11 = QShortcut(QKeySequence("F11"), self)
        shortcut_f11.activated.connect(self.toggle_fullscreen)

        # Esc để yêu cầu thoát Kiosk
        shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        shortcut_esc.activated.connect(self._handle_escape_kiosk)

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

    def cleanup(self):
        """Dừng dứt điểm toàn bộ các luồng nền và timer khi ứng dụng kết thúc."""
        if hasattr(self, "auth_timer") and self.auth_timer.isActive():
            self.auth_timer.stop()
        if hasattr(self, "kiosk_page"):
            if hasattr(self.kiosk_page, "camera_poll_timer") and self.kiosk_page.camera_poll_timer.isActive():
                self.kiosk_page.camera_poll_timer.stop()
            if hasattr(self.kiosk_page, "live_view_worker"):
                self.kiosk_page.live_view_worker.stop()
            self.kiosk_page.stop_live_view()
        if hasattr(self, "sync_mgr"):
            self.sync_mgr.close()
        if hasattr(self, "camera_mgr"):
            self.camera_mgr.close()
        if hasattr(self, "update_mgr"):
            if self.update_mgr._check_worker and self.update_mgr._check_worker.isRunning():
                self.update_mgr._check_worker.wait(200)
            if self.update_mgr._download_worker and self.update_mgr._download_worker.isRunning():
                self.update_mgr._download_worker.stop()
                self.update_mgr._download_worker.wait(200)

    def close(self) -> bool:
        self.cleanup()
        return super().close()

    def closeEvent(self, event):
        """Dừng các luồng an toàn khi đóng ứng dụng."""
        self.cleanup()
        event.accept()
