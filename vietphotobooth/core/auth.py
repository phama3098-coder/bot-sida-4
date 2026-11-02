"""
VietPhotoBooth Admin Authentication & Security Manager
Provides session-based PIN/password protection for sensitive management functions:
Camera, Printer, Events, and Settings.
Frame Designer remains accessible without PIN.
"""

import time
import hashlib
from typing import Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget, QInputDialog, QLineEdit, QMessageBox

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class AdminAuthManager(QObject):
    """
    Quản lý phiên xác thực Quản trị viên (Admin Session Manager).
    - Bảo vệ các mục nhạy cảm: Máy Ảnh, Máy In, Sự Kiện, Cài Đặt.
    - Tự động khóa sau khoảng thời gian không thao tác (Session Timeout).
    - Không lưu trữ mật khẩu/PIN dạng văn bản thuần, sử dụng SHA-256 hash.
    """
    auth_state_changed = Signal(bool)  # Emitted when locked (False) or unlocked (True)

    def __init__(self, config_mgr: ConfigManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config_mgr = config_mgr
        self._authenticated: bool = False
        self._last_auth_time: float = 0.0

    @property
    def is_pin_enabled(self) -> bool:
        """Kiểm tra xem chế độ bảo vệ bằng PIN có đang bật không."""
        return self.config_mgr.get("security.pin_enabled", True)

    @is_pin_enabled.setter
    def is_pin_enabled(self, enabled: bool):
        self.config_mgr.set("security.pin_enabled", bool(enabled))
        self.config_mgr.save()
        if not enabled:
            self._authenticated = True
            self.auth_state_changed.emit(True)
        else:
            self._authenticated = False
            self.auth_state_changed.emit(False)

    @property
    def session_timeout_sec(self) -> int:
        """Thời gian hiệu lực của phiên quản trị (mặc định 300 giây = 5 phút)."""
        return int(self.config_mgr.get("security.session_timeout_sec", 300))

    @session_timeout_sec.setter
    def session_timeout_sec(self, seconds: int):
        self.config_mgr.set("security.session_timeout_sec", max(30, int(seconds)))
        self.config_mgr.save()

    def is_authenticated(self) -> bool:
        """
        Kiểm tra quyền quản trị hiện tại.
        Nếu chế độ PIN bị tắt, luôn trả về True.
        Nếu phiên đã hết hạn, tự động chuyển về trạng thái khóa và trả về False.
        """
        if not self.is_pin_enabled:
            return True

        if not self._authenticated:
            return False

        # Kiểm tra thời gian hết hạn phiên
        elapsed = time.time() - self._last_auth_time
        if elapsed > self.session_timeout_sec:
            logger.info("Phiên quản trị viên đã hết thời gian hiệu lực, tự động khóa bảo vệ.")
            self._authenticated = False
            self.auth_state_changed.emit(False)
            return False

        return True

    def authenticate(self, pin: str) -> bool:
        """Xác thực mã PIN và bắt đầu phiên quản trị mới nếu đúng."""
        if not pin:
            return False

        if self.config_mgr.verify_pin(pin):
            self._authenticated = True
            self._last_auth_time = time.time()
            logger.info("Xác thực quản trị viên thành công. Bắt đầu phiên làm việc mới.")
            self.auth_state_changed.emit(True)
            return True
        else:
            logger.warning("Thử xác thực mã PIN quản trị viên không chính xác.")
            return False

    def refresh_session(self):
        """Gia hạn thời gian phiên làm việc khi người dùng có thao tác hợp lệ."""
        if self._authenticated:
            self._last_auth_time = time.time()

    def lock(self):
        """Chủ động khóa phiên quản trị ngay lập tức."""
        if self._authenticated:
            self._authenticated = False
            self._last_auth_time = 0.0
            logger.info("Chủ động khóa phiên quản trị viên.")
            self.auth_state_changed.emit(False)

    def get_remaining_seconds(self) -> int:
        """Trả về số giây còn lại của phiên quản trị hiện tại."""
        if not self.is_pin_enabled:
            return 9999
        if not self._authenticated:
            return 0
        rem = self.session_timeout_sec - int(time.time() - self._last_auth_time)
        return max(0, rem)

    def prompt_pin_dialog(self, parent: Optional[QWidget] = None, title: str = "Xác Thực Quyền Quản Trị") -> bool:
        """
        Hiển thị hộp thoại nhập mã PIN và xác thực.
        Trả về True nếu xác thực thành công hoặc chế độ PIN đang tắt.
        """
        if not self.is_pin_enabled:
            return True

        if self.is_authenticated():
            self.refresh_session()
            return True

        # Sử dụng TouchPinDialog chuyên nghiệp chuẩn v2.0
        try:
            from vietphotobooth.desktop.widgets.touch_pin_dialog import TouchPinDialog
            from PySide6.QtWidgets import QDialog
            dlg = TouchPinDialog(auth_mgr=self, title=title, parent=parent)
            res = dlg.exec()
            return bool(res == QDialog.Accepted and self.is_authenticated())
        except Exception as e:
            logger.warning(f"Fallback sang QInputDialog do: {e}")
            pin, ok = QInputDialog.getText(
                parent,
                title,
                "Nhập mã PIN quản trị (Mặc định: 1234):",
                QLineEdit.Password
            )
            if not ok or not pin:
                return False

            if self.authenticate(pin):
                return True
            else:
                if parent:
                    QMessageBox.critical(parent, "Lỗi Xác Thực", "Mã PIN không chính xác! Thao tác bị từ chối.")
                return False
