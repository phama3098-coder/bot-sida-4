"""
VietPhotoBooth Main Window Application
Native PySide6/Qt6 Windows desktop interface, fullscreen kiosk mode, PIN protection,
and integrated management pages.
"""

import sys
import os
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QMessageBox, QInputDialog, QLineEdit, QTabBar, QStackedWidget,
    QSizePolicy
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

from vietphotobooth.desktop.styles import (
    KIOSK_STYLE, THEME_BG_MAIN, THEME_SURFACE, THEME_BG_SECONDARY,
    THEME_BORDER, THEME_TEXT_PRIMARY, THEME_TEXT_SECONDARY, THEME_GOLD,
    THEME_INPUT_BG, THEME_SUCCESS, THEME_SUCCESS_BG, THEME_SUCCESS_BORDER
)
from vietphotobooth.desktop.widgets.kiosk_page import KioskPage
from vietphotobooth.desktop.widgets.filter_editor_page import FilterEditorPage
from vietphotobooth.desktop.widgets.frame_designer_page import FrameDesignerPage
from vietphotobooth.desktop.widgets.frame_tab_container import FrameTabContainer
from vietphotobooth.desktop.widgets.guest_idle_screen import GuestIdleScreen
from vietphotobooth.desktop.widgets.camera_page import CameraPage
from vietphotobooth.desktop.widgets.printing_page import PrintingPage
from vietphotobooth.desktop.widgets.events_page import EventsPage
from vietphotobooth.desktop.widgets.settings_page import SettingsPage
from vietphotobooth.desktop.widgets.dashboard_page import DashboardPage
from vietphotobooth.desktop.widgets.devices_page import DevicesPage
from vietphotobooth.desktop.widgets.qr_sharing_page import QRSharingPage
from vietphotobooth.desktop.icons import (
    get_svg_icon, MorphIconButton, COLOR_GOLD, COLOR_GREEN,
    get_brand_logo_pixmap, get_brand_logo_svg_path, get_brand_logo_tight_pixmap
)
from vietphotobooth.version import __version__, get_version_string
from vietphotobooth.updates import (
    UpdateManager, UpdateNotificationDialog, UpdateProgressDialog, UpdateResultDialog
)

logger = get_logger()

class MainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng Desktop 1998 TEAM — Photobooth."""

    def __init__(self, start_in_kiosk: bool = False, update_info: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.update_info = update_info
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
        storage_dir = self.config_mgr.get("storage_dir") or os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "1998TeamPhotobooth")
        self.event_mgr = EventManager(storage_root=storage_dir, current_event=self.config_mgr.get("current_event", "SuKien_MacDinh"))
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
        self.tabs.tabBar().setElideMode(Qt.ElideNone)
        self.tabs.tabBar().setExpanding(False)

        # Thanh thương hiệu Logo 1998 TEAM bên trái hàng tab (Không clip text, căn chỉnh chuẩn xác)
        self.brand_widget = QWidget()
        self.brand_widget.setMaximumWidth(260)
        self.brand_layout = QHBoxLayout(self.brand_widget)
        self.brand_layout.setContentsMargins(4, 2, 4, 2)
        self.brand_layout.setSpacing(5)

        self.lbl_logo = QLabel()
        logo_pix = get_brand_logo_tight_pixmap(height=22)
        if not logo_pix.isNull():
            self.lbl_logo.setPixmap(logo_pix)
        else:
            self.lbl_logo.setText("1998 TEAM")
            self.lbl_logo.setStyleSheet(f"color: {THEME_GOLD}; font-weight: bold; font-size: 13px;")
        self.lbl_logo.setToolTip(f"1998 TEAM — Photobooth v{__version__}")
        self.lbl_logo.setAccessibleName("Logo 1998 TEAM Photobooth")
        self.brand_layout.addWidget(self.lbl_logo)

        self.lbl_title = QLabel("1998 TEAM")
        self.lbl_title.setStyleSheet(f"color: {THEME_TEXT_PRIMARY}; font-size: 13px; font-weight: 800; letter-spacing: 0.5px;")
        self.lbl_title.setToolTip(f"1998 TEAM Photobooth v{__version__} ({get_version_string()})")
        self.brand_layout.addWidget(self.lbl_title)

        # Nút chuyển nhanh sang Buồng Lái Vận Hành (Dashboard) v2.0 - Đảm bảo đủ chiều rộng hiển thị trọn vẹn nhãn
        self.btn_dashboard = QPushButton("📊 Dashboard")
        self.btn_dashboard.setCursor(Qt.PointingHandCursor)
        self.btn_dashboard.setStyleSheet(
            f"QPushButton {{ background: {THEME_SURFACE}; color: {THEME_TEXT_PRIMARY}; font-weight: 700; font-size: 11px; "
            f"border: 1.5px solid {THEME_BORDER}; border-radius: 6px; padding: 3px 8px; margin-left: 2px; }} "
            f"QPushButton:hover {{ background: {THEME_BG_SECONDARY}; border: 1.5px solid {THEME_GOLD}; color: {THEME_TEXT_PRIMARY}; }}"
        )
        self.btn_dashboard.clicked.connect(self.show_dashboard)
        self.brand_layout.addWidget(self.btn_dashboard)

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
        self.tabs.addTab(self.kiosk_page, get_svg_icon("camera", 16, COLOR_GOLD), "Chụp Ảnh")
        self.tabs.setTabToolTip(0, "Chụp ảnh Photobooth (Kiosk)")

        # 2. Khung ảnh (Thư Viện Khung & Trình Thiết Kế Khung Ảnh)
        self.frame_page = FrameTabContainer(self.frame_mgr, auth_mgr=self.auth_mgr)
        self.frame_page.frame_changed.connect(lambda fid: self.kiosk_page._load_frame_options())
        self.frame_page.frame_selected.connect(self._on_frame_selected_from_gallery)
        self.tabs.addTab(self.frame_page, get_svg_icon("frame", 16, COLOR_GOLD), "Khung Ảnh")
        self.tabs.setTabToolTip(1, "Thư viện duyệt khung in & trình thiết kế")

        # 3. Máy ảnh (Quản Lý Máy Ảnh & Thiết Lập Cảm Biến)
        self.camera_page = CameraPage(self.camera_mgr, auth_mgr=self.auth_mgr)
        self.tabs.addTab(self.camera_page, get_svg_icon("camera", 16, COLOR_GOLD), "Máy Ảnh")
        self.tabs.setTabToolTip(2, "Cấu hình thiết bị máy ảnh")

        # 4. Máy in (Quản Lý Máy In & Driver In Nhiệt)
        self.printing_page = PrintingPage(self.print_mgr, auth_mgr=self.auth_mgr)
        self.tabs.addTab(self.printing_page, get_svg_icon("printer", 16, COLOR_GOLD), "Máy In")
        self.tabs.setTabToolTip(3, "Cấu hình máy in & hàng đợi in")

        # 5. Sự kiện & Thư viện (Quản Lý Album, Mã QR, Sự Kiện)
        self.events_page = EventsPage(self.event_mgr, self.print_mgr, self.token_mgr, sync_mgr=self.sync_mgr, auth_mgr=self.auth_mgr)
        self.tabs.addTab(self.events_page, get_svg_icon("calendar", 16, COLOR_GOLD), "Sự Kiện & Thư Viện")
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
        self.settings_page.audio_settings_changed.connect(self._on_audio_settings_changed)
        self.tabs.addTab(self.settings_page, get_svg_icon("settings", 16, COLOR_GOLD), "Cài Đặt")
        self.tabs.setTabToolTip(5, "Cài đặt hệ thống, bảo mật & Google Drive")

        # Thanh điều hướng: Xóa nút Cập nhật và ẩn nút Khóa Quản trị khỏi thanh điều hướng chính
        # nhưng vẫn giữ nguyên các đối tượng ngầm, cơ chế bảo mật PIN và tính năng trong Cài đặt.
        self.auth_widget = QWidget()
        self.auth_widget.hide()

        self.btn_check_update_quick = QPushButton("Cập Nhật", self.auth_widget)
        self.btn_check_update_quick.hide()
        self.btn_check_update_quick.clicked.connect(self._on_quick_check_update_clicked)

        self.btn_auth_status = MorphIconButton(icon_a="lock", icon_b="unlock", text=" Khóa Quản Trị", parent=self.auth_widget)
        self.btn_auth_status.hide()
        self.btn_auth_status.clicked.connect(self._toggle_auth_button_clicked)

        self.tabs.setCornerWidget(None, Qt.TopRightCorner)

        # Tham chiếu trực tiếp đến trang hoàn thiện ảnh nội bộ
        self.review_page = self.kiosk_page.review_widget

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
            # Ngăn chặn vòng lặp kiểm tra nếu vừa cập nhật hoặc vừa khôi phục sau sự cố
            has_update_event = bool(self.update_info and (self.update_info.get("updated_to") or self.update_info.get("update_failed")))
            if not has_update_event:
                QTimer.singleShot(2500, self._start_auto_update_check)

        # Stack chính v2.0:
        # Index 0: Giao diện Tabs vận hành chi tiết (bảo toàn 100% 6 tabs của baseline)
        # Index 1: Màn hình chờ dành cho khách (Guest Idle Screen)
        # Index 2: Buồng Lái Vận Hành trung tâm Concept A (Operator Dashboard)
        self.window_stack = QStackedWidget()
        self.window_stack.addWidget(self.tabs)  # Index 0

        self.idle_screen = GuestIdleScreen(auth_mgr=self.auth_mgr, parent=self)
        self.idle_screen.touch_to_start.connect(self._on_idle_screen_touched)
        self.idle_screen.admin_requested.connect(self._on_idle_admin_requested)
        self.window_stack.addWidget(self.idle_screen)  # Index 1

        self.dashboard_page = DashboardPage(
            event_mgr=self.event_mgr,
            camera_mgr=self.camera_mgr,
            print_mgr=self.print_mgr,
            config_mgr=self.config_mgr,
            frame_mgr=self.frame_mgr,
            parent=self
        )
        self.dashboard_page.start_kiosk_requested.connect(self.start_kiosk_mode)
        self.dashboard_page.open_studio_requested.connect(lambda: self.switch_to_tab(2))
        self.dashboard_page.open_templates_requested.connect(lambda: self.switch_to_tab(1))
        self.dashboard_page.open_printing_requested.connect(lambda: self.switch_to_tab(3))
        self.dashboard_page.open_events_requested.connect(lambda: self.switch_to_tab(4))
        self.dashboard_page.open_devices_requested.connect(self.show_devices)
        self.dashboard_page.open_qr_requested.connect(self.show_qr_sharing)
        self.window_stack.addWidget(self.dashboard_page)  # Index 2

        self.devices_page = DevicesPage(
            camera_mgr=self.camera_mgr,
            print_mgr=self.print_mgr,
            config_mgr=self.config_mgr,
            token_mgr=self.token_mgr,
            parent=self
        )
        self.window_stack.addWidget(self.devices_page)  # Index 3

        self.qr_page = QRSharingPage(
            token_mgr=self.token_mgr,
            event_mgr=self.event_mgr,
            config_mgr=self.config_mgr,
            parent=self
        )
        self.window_stack.addWidget(self.qr_page)  # Index 4

        main_layout.addWidget(self.window_stack)

        # Bộ đếm thời gian chuyển sang Màn hình chờ khi quầy rảnh rỗi (Guest Idle Screen)
        self.guest_idle_timer = QTimer(self)
        self.guest_idle_timer.setInterval(180000)  # 3 phút (180 giây)
        self.guest_idle_timer.timeout.connect(self._on_guest_idle_timeout)
        self.guest_idle_timer.start()

        # Khởi động luồng Live View cho tab mặc định ban đầu (Chụp Ảnh)
        if hasattr(self, "kiosk_page"):
            self.kiosk_page.start_live_view()

        # Kiểm tra thông báo kết quả cập nhật (nếu vừa nâng cấp hoặc khôi phục)
        if self.update_info:
            if self.update_info.get("updated_to"):
                QTimer.singleShot(600, self._show_update_success_notification)
            elif self.update_info.get("update_failed"):
                QTimer.singleShot(600, lambda: self._show_update_failed_notification(self.update_info["update_failed"]))

    def _show_update_success_notification(self):
        info = self.update_info or {}
        dlg = UpdateResultDialog(
            is_success=True,
            new_version=info.get("updated_to", __version__),
            new_build=info.get("updated_build", 0),
            old_version=info.get("updated_from", ""),
            parent=self
        )
        dlg.exec()

    def _show_update_failed_notification(self, err_code: str):
        dlg = UpdateResultDialog(
            is_success=False,
            error_code=str(err_code),
            parent=self
        )
        dlg.exec()

    def _start_auto_update_check(self):
        """Khởi chạy kiểm tra cập nhật ngầm nếu cửa sổ đang hoạt động."""
        if self.isVisible():
            self.update_mgr.check_for_updates(manual=False)

    def _on_quick_check_update_clicked(self):
        """Xử lý khi bấm nút kiểm tra cập nhật nhanh trên thanh tiêu đề."""
        self.btn_check_update_quick.setEnabled(False)
        self.btn_check_update_quick.setText("⏳ Đang kiểm tra...")

        def on_quick_done(has_update: bool, manifest, msg: str):
            self.btn_check_update_quick.setEnabled(True)
            self.btn_check_update_quick.setText("🔄 Cập Nhật")
            try:
                self.update_mgr.check_completed.disconnect(on_quick_done)
            except Exception:
                pass

            if has_update and manifest:
                self._update_dlg = UpdateNotificationDialog(manifest, self.update_mgr, self)
                self._update_dlg.update_requested.connect(self._start_download_flow)
                self._update_dlg.show()
            else:
                from PySide6.QtWidgets import QMessageBox
                if manifest:
                    QMessageBox.information(
                        self,
                        "Kiểm Tra Cập Nhật",
                        f"✅ {msg}\n\nPhiên bản đang sử dụng: v{get_version_string()}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Thông Báo Cập Nhật",
                        f"⚠️ {msg}\n\nBạn có thể cấu hình địa chỉ máy chủ phát hành trong mục Cài Đặt."
                    )

        self.update_mgr.check_completed.connect(on_quick_done)
        self.update_mgr.check_for_updates(manual=True)

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
                f"QPushButton {{ background-color: {THEME_INPUT_BG}; color: {THEME_TEXT_SECONDARY}; border: 1px solid {THEME_BORDER}; "
                f"border-radius: 6px; padding: 2px 10px; font-weight: bold; font-size: 11px; }}"
            )
        elif self.auth_mgr.is_authenticated():
            rem = self.auth_mgr.get_remaining_seconds()
            m, s = divmod(rem, 60)
            self.btn_auth_status.setText(f" Mở ({m:02d}:{s:02d})")
            if hasattr(self.btn_auth_status, "set_morph_state"):
                self.btn_auth_status.set_morph_state(True)
            self.btn_auth_status.setStyleSheet(
                f"QPushButton {{ background-color: {THEME_SUCCESS_BG}; color: {THEME_SUCCESS}; border: 1.5px solid {THEME_SUCCESS_BORDER}; "
                f"border-radius: 6px; padding: 2px 10px; font-weight: bold; font-size: 11px; }}"
                f"QPushButton:hover {{ background-color: #D4E8D4; }}"
            )
        else:
            self.btn_auth_status.setText(" Khóa Quản Trị")
            if hasattr(self.btn_auth_status, "set_morph_state"):
                self.btn_auth_status.set_morph_state(False)
            self.btn_auth_status.setStyleSheet(
                f"QPushButton {{ background-color: {THEME_INPUT_BG}; color: {THEME_GOLD}; border: 1.5px solid {THEME_GOLD}; "
                f"border-radius: 6px; padding: 2px 10px; font-weight: bold; font-size: 11px; }}"
                f"QPushButton:hover {{ background-color: {THEME_SURFACE}; color: {THEME_TEXT_PRIMARY}; }}"
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

        # Quản lý luồng Live View tường minh theo tab:
        # Tab 0 (Chụp ảnh): KioskPage kích hoạt luồng live view
        # Tab 2 (Máy ảnh): CameraPage kích hoạt timer xem trước
        # Các tab khác: Tạm dừng toàn bộ live view để tối ưu hiệu năng
        if hasattr(self, 'kiosk_page'):
            if new_index == 0:
                self.kiosk_page.start_live_view()
            else:
                self.kiosk_page.stop_live_view()

    def _on_audio_settings_changed(self):
        """Đồng bộ thời gian thực các thay đổi cấu hình âm thanh với SoundController của Kiosk."""
        if hasattr(self, "kiosk_page") and hasattr(self.kiosk_page, "sound_controller") and self.kiosk_page.sound_controller:
            self.kiosk_page.sound_controller.sync_with_config(self.config_mgr)

    def switch_to_tab(self, target_index: int):
        """Chuyển tab theo yêu cầu từ các trang con (kiểm tra quyền quản trị)."""
        if self.window_stack.currentIndex() != 0:
            self.window_stack.setCurrentIndex(0)
        if target_index in self.PROTECTED_TABS:
            if not self.auth_mgr.is_authenticated():
                if not self.auth_mgr.prompt_pin_dialog(self, f"Mở Khóa Tab: {self.tabs.tabText(target_index)}"):
                    return
        self._prev_tab_index = target_index
        self.tabs.setCurrentIndex(target_index)

    def show_dashboard(self):
        """Chuyển sang Buồng Lái Vận Hành (Operator Dashboard) trung tâm v2.0."""
        self.window_stack.setCurrentIndex(2)

    def show_devices(self):
        """Chuyển sang Bảng Giám Sát Thiết Bị & Cảm Biến Đa Kênh v2.0."""
        if not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Mở Khóa Giám Sát Thiết Bị"):
                return
        self.window_stack.setCurrentIndex(3)
        if hasattr(self, "devices_page"):
            self.devices_page.refresh_telemetry()

    def show_qr_sharing(self):
        """Chuyển sang Trung Tâm Chia Sẻ QR & Mạng LAN v2.0."""
        self.window_stack.setCurrentIndex(4)

    def start_kiosk_mode(self):
        """Bắt đầu Kiosk Mode từ Dashboard hoặc phím F11."""
        self.window_stack.setCurrentIndex(0)
        self.switch_to_tab(0)
        if not self.isFullScreen():
            self.toggle_fullscreen()

    def toggle_fullscreen(self):
        """Bật/tắt chế độ toàn màn hình Kiosk Mode."""
        if self.isFullScreen():
            if self.auth_mgr.is_pin_enabled and not self.auth_mgr.is_authenticated():
                if not self.auth_mgr.prompt_pin_dialog(self, "Thoát Chế Độ Kiosk"):
                    return
            self.showNormal()
            self.tabs.tabBar().show()
            if hasattr(self, "kiosk_page") and hasattr(self.kiosk_page, "set_fullscreen_mode"):
                self.kiosk_page.set_fullscreen_mode(False)
        else:
            self.showFullScreen()
            # Ở chế độ Kiosk toàn màn hình, chuyển về tab Chụp Ảnh và ẩn thanh Tab bar
            self.tabs.setCurrentIndex(0)
            self.tabs.tabBar().hide()
            if hasattr(self, "kiosk_page") and hasattr(self.kiosk_page, "set_fullscreen_mode"):
                self.kiosk_page.set_fullscreen_mode(True)

    def _setup_shortcuts(self):
        # F11 để bật/tắt chế độ toàn màn hình Kiosk
        shortcut_f11 = QShortcut(QKeySequence("F11"), self)
        shortcut_f11.activated.connect(self.toggle_fullscreen)

        # F10 để xem nhanh màn hình chờ khách (Guest Idle Attract Screen)
        shortcut_f10 = QShortcut(QKeySequence("F10"), self)
        shortcut_f10.activated.connect(self._toggle_idle_screen_shortcut)

        # Esc để yêu cầu thoát Kiosk
        shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        shortcut_esc.activated.connect(self._handle_escape_kiosk)

    def _handle_escape_kiosk(self):
        if hasattr(self, "window_stack") and self.window_stack.currentIndex() == 1:
            self.hide_idle_screen()
            return
        if self.isFullScreen():
            self.toggle_fullscreen()

    def _toggle_idle_screen_shortcut(self):
        if hasattr(self, "window_stack"):
            if self.window_stack.currentIndex() == 1:
                self.hide_idle_screen()
            else:
                self.show_idle_screen()

    def _on_frame_selected_from_gallery(self, frame_id: str):
        """Khi khách chạm chọn mẫu khung từ Thư Viện, chuyển ngay sang màn hình chụp ảnh."""
        if hasattr(self.kiosk_page, "_on_frame_card_selected"):
            self.kiosk_page._on_frame_card_selected(frame_id)
        self.tabs.setCurrentIndex(0)
        self.reset_idle_timer()

    def show_review_page(self, photos=None, template_id=None, session_id=None):
        """Chuyển sang trang hoàn thiện ảnh nội bộ (không mở cửa sổ riêng biệt)."""
        self.tabs.setCurrentIndex(0)
        if photos and hasattr(self.kiosk_page, "review_widget"):
            active_event = self.event_mgr.get_active_event_name()
            self.kiosk_page.review_widget.load_session(
                photos=photos,
                frame_mgr=self.frame_mgr,
                initial_frame_id=template_id or getattr(self.kiosk_page, "selected_frame_id", None),
                event_name=active_event,
                session_id=session_id or getattr(self.kiosk_page, "current_session_id", "Session_unknown"),
                print_mgr=self.print_mgr
            )
        if hasattr(self.kiosk_page, "kiosk_stack"):
            self.kiosk_page.kiosk_stack.setCurrentIndex(1)

    def _on_guest_idle_timeout(self):
        """Tự động chuyển sang Màn hình chờ dành cho khách khi quầy rảnh rỗi."""
        if self.tabs.currentIndex() == 0:
            kiosk_st = getattr(self.kiosk_page, "current_state", "IDLE")
            if kiosk_st in ("IDLE", "SELECT_FRAME"):
                if hasattr(self, "window_stack") and self.window_stack.currentIndex() == 0:
                    self.show_idle_screen()

    def show_idle_screen(self):
        """Kích hoạt Màn hình chờ phong cách phóng sự cưới 1998 Studio (Panel 3)."""
        if hasattr(self, "window_stack") and hasattr(self, "idle_screen"):
            self.window_stack.setCurrentIndex(1)
            self.idle_screen.start_animations()

    def hide_idle_screen(self):
        """Tắt màn hình chờ và trở về giao diện Photobooth."""
        if hasattr(self, "window_stack") and hasattr(self, "idle_screen"):
            self.idle_screen.stop_animations()
            self.window_stack.setCurrentIndex(0)
            self.reset_idle_timer()

    def _on_idle_screen_touched(self):
        """Khách chạm vào nút 'CHẠM ĐỂ BẮT ĐẦU'."""
        self.hide_idle_screen()
        self.tabs.setCurrentIndex(0)

    def _on_idle_admin_requested(self):
        """Bấm nút bánh răng quản trị góc trên bên phải màn hình chờ."""
        if self.auth_mgr.is_pin_enabled and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Mở Khóa Quản Trị Từ Màn Hình Chờ"):
                return
        self.hide_idle_screen()
        self.switch_to_tab(5)

    def reset_idle_timer(self):
        """Đặt lại bộ đếm thời gian rảnh rỗi."""
        if hasattr(self, "guest_idle_timer") and self.guest_idle_timer.isActive():
            self.guest_idle_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_navigation(event.size().width())

    def _update_responsive_navigation(self, width: int):
        if not hasattr(self, "brand_widget") or not hasattr(self, "tabs"):
            return

        self.lbl_title.setText("1998 TEAM")

        if width < 1000:
            self.brand_widget.setMaximumWidth(220)
            self.tabs.setTabText(0, "Chụp")
            self.tabs.setTabText(1, "Khung")
            self.tabs.setTabText(2, "Máy")
            self.tabs.setTabText(3, "In")
            self.tabs.setTabText(4, "Sự Kiện")
            self.tabs.setTabText(5, "Cài Đặt")
        else:
            self.brand_widget.setMaximumWidth(260)
            self.tabs.setTabText(0, "Chụp Ảnh")
            self.tabs.setTabText(1, "Khung Ảnh")
            self.tabs.setTabText(2, "Máy Ảnh")
            self.tabs.setTabText(3, "Máy In")
            self.tabs.setTabText(4, "Sự Kiện & Thư Viện")
            self.tabs.setTabText(5, "Cài Đặt")

    def cleanup(self):
        """Dừng dứt điểm toàn bộ các luồng nền và timer khi ứng dụng kết thúc."""
        if hasattr(self, "guest_idle_timer") and self.guest_idle_timer.isActive():
            self.guest_idle_timer.stop()
        if hasattr(self, "idle_screen"):
            self.idle_screen.stop_animations()
        if hasattr(self, "auth_timer") and self.auth_timer.isActive():
            self.auth_timer.stop()
        if hasattr(self, "kiosk_page"):
            if hasattr(self.kiosk_page, "camera_poll_timer") and self.kiosk_page.camera_poll_timer.isActive():
                self.kiosk_page.camera_poll_timer.stop()
            if hasattr(self.kiosk_page, "live_view_worker"):
                self.kiosk_page.live_view_worker.stop()
            self.kiosk_page.stop_live_view()
        if hasattr(self, "camera_page"):
            self.camera_page.close()
        if hasattr(self, "devices_page") and hasattr(self.devices_page, "_poll_timer") and self.devices_page._poll_timer.isActive():
            self.devices_page._poll_timer.stop()
        if hasattr(self, "sync_mgr"):
            self.sync_mgr.close()
        if hasattr(self, "camera_mgr"):
            self.camera_mgr.close()
        if hasattr(self, "print_mgr") and hasattr(self.print_mgr, "stop"):
            self.print_mgr.stop()
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
