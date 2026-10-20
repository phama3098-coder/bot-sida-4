"""
VietPhotoBooth Settings & Security Page
PIN security management, Kiosk countdown & timeout settings, LAN QR server config, and full screen toggles.
"""

import sys
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QGroupBox, QCheckBox, QSpinBox, QLineEdit, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class SettingsPage(QWidget):
    """Trang cấu hình hệ thống, bảo mật mã PIN và vận hành Kiosk."""

    toggle_fullscreen_requested = Signal()

    def __init__(self, config_mgr: ConfigManager, token_mgr: TokenManager, parent=None):
        super().__init__(parent)
        self.config_mgr = config_mgr
        self.token_mgr = token_mgr

        self._init_ui()
        self._load_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 1. BẢO MẬT & MÃ PIN QUẢN TRỊ (PIN CODE PROTECTION)
        grp_sec = QGroupBox("1. Bảo Mật & Mã PIN Quản Trị")
        l_sec = QVBoxLayout(grp_sec)

        self.chk_pin_enabled = QCheckBox("Bắt buộc nhập mã PIN khi thoát chế độ Kiosk hoặc vào trang Quản Trị")
        self.chk_pin_enabled.setChecked(True)
        l_sec.addWidget(self.chk_pin_enabled)

        r_pin = QHBoxLayout()
        r_pin.addWidget(QLabel("Mã PIN hiện tại: <b>••••</b> (Mặc định: 1234)"))
        btn_change_pin = QPushButton("Đổi Mã PIN Mới")
        btn_change_pin.setObjectName("btn_secondary")
        btn_change_pin.clicked.connect(self._change_pin)
        r_pin.addWidget(btn_change_pin)
        r_pin.addStretch()
        l_sec.addLayout(r_pin)

        layout.addWidget(grp_sec)

        # 2. CẤU HÌNH VẬN HÀNH PHOTOBOOTH KIOSK
        grp_kiosk = QGroupBox("2. Vận Hành Photobooth Kiosk")
        l_kiosk = QVBoxLayout(grp_kiosk)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Thời Gian Đếm Ngược Mặc Định:"))
        self.spin_countdown = QSpinBox()
        self.spin_countdown.setRange(2, 30)
        self.spin_countdown.setValue(3)
        self.spin_countdown.setSuffix(" Giây")
        r1.addWidget(self.spin_countdown)

        r1.addWidget(QLabel("Số Ảnh Chụp Mỗi Lượt:"))
        self.spin_shots = QSpinBox()
        self.spin_shots.setRange(1, 8)
        self.spin_shots.setValue(3)
        self.spin_shots.setSuffix(" Ảnh")
        r1.addWidget(self.spin_shots)
        l_kiosk.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Thời Gian Tự Động Trở Về Màn Hình Chính (Idle Timeout):"))
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(10, 300)
        self.spin_timeout.setValue(45)
        self.spin_timeout.setSuffix(" Giây")
        r2.addWidget(self.spin_timeout)
        l_kiosk.addLayout(r2)

        r3 = QHBoxLayout()
        btn_toggle_fs = QPushButton("🖥️ Bật / Tắt Toàn Màn Hình (F11 Kiosk Mode)")
        btn_toggle_fs.setObjectName("btn_secondary")
        btn_toggle_fs.clicked.connect(lambda: self.toggle_fullscreen_requested.emit())
        r3.addWidget(btn_toggle_fs)
        r3.addStretch()
        l_kiosk.addLayout(r3)

        layout.addWidget(grp_kiosk)

        # 3. MÁY CHỦ CHIA SẺ ẢNH MẠNG LAN (LAN QR SHARING)
        grp_lan = QGroupBox("3. Máy Chủ Chia Sẻ Ảnh Mạng Nội Bộ (LAN QR Code)")
        l_lan = QVBoxLayout(grp_lan)

        ip = self.token_mgr.lan_ip
        port = self.token_mgr.port
        l_lan.addWidget(QLabel(f"Địa Chỉ IP Máy Trạm: <b>{ip}</b>"))
        l_lan.addWidget(QLabel(f"Cổng Máy Chủ Chia Sẻ (HTTP Port): <b>{port}</b>"))
        l_lan.addWidget(QLabel(f"Đường Dẫn Truy Cập Di Động: <b>http://{ip}:{port}/s/&lt;ma_chia_se&gt;</b>"))

        layout.addWidget(grp_lan)

        # 4. THÔNG TIN HỆ THỐNG
        grp_sys = QGroupBox("4. Thông Tin Ứng Dụng & Bản Quyền")
        l_sys = QVBoxLayout(grp_sys)
        l_sys.addWidget(QLabel("Tên Phần Mềm: <b>VietPhotoBooth — Commercial Photobooth Application</b>"))
        l_sys.addWidget(QLabel(f"Nền Tảng: <b>{platform.system()} {platform.release()} (64-bit)</b> • Python {platform.python_version()} • PySide6"))
        l_sys.addWidget(QLabel("Giấy Phép: Thương Mại & Bản Quyền Mã Nguồn Độc Lập"))
        layout.addWidget(grp_sys)

        # Nút Lưu
        btn_save = QPushButton("Lưu Toàn Bộ Cài Đặt")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self._save_config)
        layout.addWidget(btn_save)

    def _load_config(self):
        cd = self.config_mgr.get("kiosk.countdown_sec", 3)
        self.spin_countdown.setValue(cd)
        to = self.config_mgr.get("kiosk.idle_timeout_sec", 45)
        self.spin_timeout.setValue(to)
        shots = self.config_mgr.get("kiosk.shots_per_session", 3)
        self.spin_shots.setValue(shots)

    def _save_config(self):
        self.config_mgr.set("kiosk.countdown_sec", self.spin_countdown.value())
        self.config_mgr.set("kiosk.idle_timeout_sec", self.spin_timeout.value())
        self.config_mgr.set("kiosk.shots_per_session", self.spin_shots.value())
        self.config_mgr.save()
        QMessageBox.information(self, "Thành Công", "Đã lưu thành công các thiết lập hệ thống!")

    def _change_pin(self):
        old_pin, ok1 = QInputDialog.getText(self, "Xác Thực PIN Hiện Tại", "Nhập mã PIN hiện tại:", QLineEdit.Password)
        if not ok1:
            return
        if not self.config_mgr.verify_pin(old_pin):
            QMessageBox.critical(self, "Lỗi", "Mã PIN hiện tại không chính xác!")
            return

        new_pin, ok2 = QInputDialog.getText(self, "Đặt PIN Mới", "Nhập mã PIN mới (4-8 số):", QLineEdit.Password)
        if ok2 and new_pin.strip():
            self.config_mgr.set_pin(new_pin.strip())
            QMessageBox.information(self, "Thành Công", "Đã cập nhật mã PIN quản trị mới thành công!")
