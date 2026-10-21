"""
VietPhotoBooth Settings & Security Page
PIN security management, Kiosk countdown & timeout settings, LAN QR server config,
and Google Drive Cloud Sync integration with DPAPI encryption.
"""

import os
import sys
import json
import platform
import tempfile
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QGroupBox, QCheckBox, QSpinBox, QLineEdit, QMessageBox, QInputDialog,
    QScrollArea, QFrame, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.filters.filter_engine import FilterEngine
from vietphotobooth.desktop.widgets.filter_editor_page import FilterEditorDialog
from vietphotobooth.cloud import SyncManager, GDriveAuth, GDriveClient
from vietphotobooth.core.logger import get_logger
from vietphotobooth.version import get_version_string, __release_date__, __version__, __build__
from vietphotobooth.updates import UpdateManager, UpdateNotificationDialog, UpdateProgressDialog

logger = get_logger()

class SettingsPage(QWidget):
    """Trang cấu hình hệ thống, bảo mật mã PIN, vận hành Kiosk và Đồng bộ Google Drive."""

    toggle_fullscreen_requested = Signal()

    def __init__(
        self,
        config_mgr: ConfigManager,
        token_mgr: TokenManager,
        filter_engine: Optional[FilterEngine] = None,
        sync_mgr: Optional[SyncManager] = None,
        auth_mgr=None,
        update_mgr: Optional[UpdateManager] = None,
        parent=None
    ):
        super().__init__(parent)
        self.config_mgr = config_mgr
        self.token_mgr = token_mgr
        self.filter_engine = filter_engine
        self.sync_mgr = sync_mgr
        self.auth_mgr = auth_mgr
        self.update_mgr = update_mgr or UpdateManager(self.config_mgr, self)

        self._init_ui()
        self._load_config()
        self._update_gdrive_ui_status()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 1. BẢO MẬT & MÃ PIN QUẢN TRỊ (PIN CODE PROTECTION)
        grp_sec = QGroupBox("1. Bảo Mật & Mã PIN Quản Trị")
        l_sec = QVBoxLayout(grp_sec)

        self.chk_pin_enabled = QCheckBox("Bảo vệ bằng mã PIN cho các mục quản trị (Máy ảnh, Máy in, Sự kiện, Cài đặt)")
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

        r_timeout = QHBoxLayout()
        r_timeout.addWidget(QLabel("Thời gian hiệu lực phiên quản trị:"))
        self.spin_session_timeout = QSpinBox()
        self.spin_session_timeout.setRange(30, 3600)
        self.spin_session_timeout.setValue(300)
        self.spin_session_timeout.setSuffix(" Giây (Mặc định: 300s = 5p)")
        r_timeout.addWidget(self.spin_session_timeout)
        r_timeout.addStretch()
        l_sec.addLayout(r_timeout)

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

        # 4. QUẢN LÝ BỘ LỌC MÀU (FILTER STUDIO)
        grp_filter = QGroupBox("4. Quản Lý Bộ Lọc Màu (Filter Studio)")
        l_filter = QVBoxLayout(grp_filter)
        l_filter.addWidget(QLabel("Tạo mới, chỉnh sửa thông số 14 bộ điều khiển màu, nhập file .cube 3D LUT và sao lưu bộ lọc."))
        btn_open_filters = QPushButton("🎨 Mở Trình Biên Tập Bộ Lọc Màu (Filter Studio)")
        btn_open_filters.setObjectName("btn_secondary")
        btn_open_filters.clicked.connect(self._open_filter_studio)
        l_filter.addWidget(btn_open_filters)
        layout.addWidget(grp_filter)

        # 5. LƯU TRỮ & ĐỒNG BỘ ĐÁM MÂY (GOOGLE DRIVE CLOUD SYNC)
        grp_gdrive = QGroupBox("5. Lưu Trữ & Đồng Bộ Đám Mây (Google Drive Cloud Sync)")
        l_gd = QVBoxLayout(grp_gdrive)

        # Trạng thái kết nối Google Drive
        r_gd_status = QHBoxLayout()
        self.lbl_gdrive_status = QLabel("Trạng thái: Đang kiểm tra...")
        self.lbl_gdrive_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #F59E0B;")
        r_gd_status.addWidget(self.lbl_gdrive_status, 1)

        self.btn_gdrive_test_upload = QPushButton("☁️ Thử Tải Lên Mẫu")
        self.btn_gdrive_test_upload.setObjectName("btn_secondary")
        self.btn_gdrive_test_upload.clicked.connect(self._test_gdrive_upload)
        r_gd_status.addWidget(self.btn_gdrive_test_upload)
        l_gd.addLayout(r_gd_status)

        # Khóa API Google Cloud
        r_keys = QHBoxLayout()
        r_keys.addWidget(QLabel("Client ID:"))
        self.txt_client_id = QLineEdit()
        self.txt_client_id.setPlaceholderText("VD: 123456...apps.googleusercontent.com")
        r_keys.addWidget(self.txt_client_id, 2)

        r_keys.addWidget(QLabel("Client Secret:"))
        self.txt_client_secret = QLineEdit()
        self.txt_client_secret.setEchoMode(QLineEdit.Password)
        self.txt_client_secret.setPlaceholderText("GOCSPX-...")
        r_keys.addWidget(self.txt_client_secret, 2)

        btn_load_json = QPushButton("📂 Nhập client_secrets.json")
        btn_load_json.setObjectName("btn_secondary")
        btn_load_json.clicked.connect(self._load_client_secrets_json)
        r_keys.addWidget(btn_load_json)
        l_gd.addLayout(r_keys)

        # Các tùy chọn đồng bộ
        r_opts = QHBoxLayout()
        self.chk_auto_sync = QCheckBox("Tự động đồng bộ ảnh sau mỗi lượt chụp (Auto Sync)")
        self.chk_auto_sync.setChecked(True)
        r_opts.addWidget(self.chk_auto_sync)

        self.chk_public_share = QCheckBox("Công khai quyền xem để khách quét mã QR tải ảnh qua 4G (Public Sharing)")
        self.chk_public_share.setChecked(True)
        r_opts.addWidget(self.chk_public_share)
        r_opts.addStretch()
        l_gd.addLayout(r_opts)

        # Thư mục gốc trên Drive
        r_folder = QHBoxLayout()
        r_folder.addWidget(QLabel("Tên thư mục gốc trên Google Drive:"))
        self.txt_root_folder = QLineEdit()
        self.txt_root_folder.setText("1998 TEAM Photobooth")
        r_folder.addWidget(self.txt_root_folder, 1)
        l_gd.addLayout(r_folder)

        # Hàng nút kết nối Google Drive
        r_gd_btns = QHBoxLayout()
        self.btn_gdrive_connect = QPushButton("🔗 Kết Nối Google Drive (OAuth2 Trình Duyệt)")
        self.btn_gdrive_connect.setObjectName("btn_champagne")
        self.btn_gdrive_connect.clicked.connect(self._connect_gdrive)
        r_gd_btns.addWidget(self.btn_gdrive_connect)

        self.btn_gdrive_sim = QPushButton("🧪 Bật Chế Độ Giả Lập / Test Demo")
        self.btn_gdrive_sim.setObjectName("btn_secondary")
        self.btn_gdrive_sim.clicked.connect(self._toggle_simulation_mode)
        r_gd_btns.addWidget(self.btn_gdrive_sim)

        self.btn_gdrive_disconnect = QPushButton("🔌 Ngắt Kết Nối")
        self.btn_gdrive_disconnect.setObjectName("btn_danger")
        self.btn_gdrive_disconnect.clicked.connect(self._disconnect_gdrive)
        r_gd_btns.addWidget(self.btn_gdrive_disconnect)

        r_gd_btns.addStretch()
        l_gd.addLayout(r_gd_btns)

        layout.addWidget(grp_gdrive)

        # 6. THÔNG TIN ỨNG DỤNG, BẢN QUYỀN & CẬP NHẬT PHIÊN BẢN
        grp_sys = QGroupBox("6. Thông Tin Ứng Dụng & Cập Nhật Phiên Bản")
        l_sys = QVBoxLayout(grp_sys)
        l_sys.setSpacing(12)

        r_brand = QHBoxLayout()
        logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "logo_1998_studio.png"))
        if os.path.exists(logo_path):
            lbl_logo = QLabel()
            pix = QPixmap(logo_path)
            lbl_logo.setPixmap(pix.scaledToHeight(64, Qt.SmoothTransformation))
            r_brand.addWidget(lbl_logo)

        brand_info = QVBoxLayout()
        lbl_app_name = QLabel("<b>1998 TEAM — Photobooth</b>")
        lbl_app_name.setStyleSheet("color: #D4AF37; font-size: 18px; font-weight: bold;")
        brand_info.addWidget(lbl_app_name)
        brand_info.addWidget(QLabel("Đơn vị sở hữu: <b>1998 Studio phóng sự cưới</b>"))

        lbl_ver_badge = QLabel(
            f"Phiên bản hiện tại: <b style='color:#10B981;'>v{get_version_string()}</b> • Phát hành: <b>{__release_date__}</b>"
        )
        lbl_ver_badge.setStyleSheet("font-size: 13px; color: #CBD5E1;")
        brand_info.addWidget(lbl_ver_badge)

        brand_info.addWidget(QLabel(f"Nền tảng: <b>{platform.system()} {platform.release()} (64-bit)</b> • Python {platform.python_version()} • PySide6"))
        r_brand.addLayout(brand_info)
        r_brand.addStretch()
        l_sys.addLayout(r_brand)

        # Phân cách mỏng
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #1E2D4A;")
        l_sys.addWidget(line)

        # Cấu hình kiểm tra cập nhật
        l_sys.addWidget(QLabel("<b>Cấu Hình & Kiểm Tra Cập Nhật Phần Mềm:</b>"))

        r_up1 = QHBoxLayout()
        r_up1.addWidget(QLabel("Địa chỉ Manifest Cập Nhật (URL / Đường Dẫn):"))
        self.txt_manifest_url = QLineEdit()
        self.txt_manifest_url.setPlaceholderText("https://.../update_manifest.json hoặc đường dẫn tệp local")
        r_up1.addWidget(self.txt_manifest_url, 1)
        l_sys.addLayout(r_up1)

        r_up2 = QHBoxLayout()
        self.chk_auto_update = QCheckBox("Tự động kiểm tra bản cập nhật mới khi mở ứng dụng")
        r_up2.addWidget(self.chk_auto_update)
        r_up2.addStretch()

        self.btn_check_update = QPushButton("🔄 Kiểm Tra Cập Nhật Ngay")
        self.btn_check_update.setObjectName("btn_secondary")
        self.btn_check_update.setFixedHeight(34)
        self.btn_check_update.clicked.connect(self._manual_check_update)
        r_up2.addWidget(self.btn_check_update)
        l_sys.addLayout(r_up2)

        self.lbl_update_status = QLabel("Trạng thái: Sẵn sàng kiểm tra phiên bản mới.")
        self.lbl_update_status.setStyleSheet("color: #94A3B8; font-size: 12px; font-style: italic;")
        l_sys.addWidget(self.lbl_update_status)

        layout.addWidget(grp_sys)

        # Nút Lưu
        btn_save = QPushButton("💾 Lưu Toàn Bộ Cài Đặt")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self._save_config)
        layout.addWidget(btn_save)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _load_config(self):
        pin_en = self.config_mgr.get("security.pin_enabled", True)
        self.chk_pin_enabled.setChecked(pin_en)
        sess_to = self.config_mgr.get("security.session_timeout_sec", 300)
        self.spin_session_timeout.setValue(sess_to)

        cd = self.config_mgr.get("kiosk.countdown_sec", 3)
        self.spin_countdown.setValue(cd)
        to = self.config_mgr.get("kiosk.idle_timeout_sec", 45)
        self.spin_timeout.setValue(to)
        shots = self.config_mgr.get("kiosk.shots_per_session", 3)
        self.spin_shots.setValue(shots)

        # Google Drive settings
        cid = self.config_mgr.get("cloud.gdrive_client_id", "")
        self.txt_client_id.setText(cid)
        csec = self.config_mgr.get("cloud.gdrive_client_secret", "")
        self.txt_client_secret.setText(csec)
        rf = self.config_mgr.get("cloud.root_folder_name", "1998 TEAM Photobooth")
        self.txt_root_folder.setText(rf)
        self.chk_auto_sync.setChecked(self.config_mgr.get("cloud.auto_sync", True))
        self.chk_public_share.setChecked(self.config_mgr.get("cloud.public_sharing", True))

        # Update settings
        murl = self.config_mgr.get("updates.manifest_url", "")
        self.txt_manifest_url.setText(murl)
        auto_up = self.config_mgr.get("updates.auto_check_on_startup", True)
        self.chk_auto_update.setChecked(auto_up)

    def _save_config(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Lưu Cài Đặt"):
                return

        self.config_mgr.set("security.pin_enabled", self.chk_pin_enabled.isChecked())
        self.config_mgr.set("security.session_timeout_sec", self.spin_session_timeout.value())
        if self.auth_mgr:
            self.auth_mgr.is_pin_enabled = self.chk_pin_enabled.isChecked()
            self.auth_mgr.session_timeout_sec = self.spin_session_timeout.value()

        self.config_mgr.set("kiosk.countdown_sec", self.spin_countdown.value())
        self.config_mgr.set("kiosk.idle_timeout_sec", self.spin_timeout.value())
        self.config_mgr.set("kiosk.shots_per_session", self.spin_shots.value())

        # Save Google Drive settings
        self.config_mgr.set("cloud.gdrive_client_id", self.txt_client_id.text().strip())
        self.config_mgr.set("cloud.gdrive_client_secret", self.txt_client_secret.text().strip())
        self.config_mgr.set("cloud.root_folder_name", self.txt_root_folder.text().strip() or "1998 TEAM Photobooth")
        self.config_mgr.set("cloud.auto_sync", self.chk_auto_sync.isChecked())
        self.config_mgr.set("cloud.public_sharing", self.chk_public_share.isChecked())

        # Save Update settings
        self.config_mgr.set("updates.manifest_url", self.txt_manifest_url.text().strip())
        self.config_mgr.set("updates.auto_check_on_startup", self.chk_auto_update.isChecked())

        if self.sync_mgr:
            self.sync_mgr.auth.client_id = self.txt_client_id.text().strip()
            self.sync_mgr.auth.client_secret = self.txt_client_secret.text().strip()

        self.config_mgr.save()
        self._update_gdrive_ui_status()
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QMessageBox.information(self, "Thành Công", "Đã lưu thành công các thiết lập hệ thống và đám mây!")

    def _manual_check_update(self):
        """Xử lý khi người dùng chủ động bấm 'Kiểm Tra Cập Nhật Ngay'."""
        murl = self.txt_manifest_url.text().strip()
        self.update_mgr.manifest_url = murl

        self.lbl_update_status.setText("⏳ Đang kết nối máy chủ kiểm tra phiên bản mới...")
        self.lbl_update_status.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 12px;")
        self.btn_check_update.setEnabled(False)

        def on_check_done(has_update: bool, manifest, msg: str):
            self.btn_check_update.setEnabled(True)
            try:
                self.update_mgr.check_completed.disconnect(on_check_done)
            except Exception:
                pass

            if has_update and manifest:
                self.lbl_update_status.setText(f"🎉 Đã tìm thấy bản cập nhật mới: v{manifest.version} (Build {manifest.build})!")
                self.lbl_update_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
                self._update_dlg = UpdateNotificationDialog(manifest, self.update_mgr, self)
                self._update_dlg.update_requested.connect(self._start_download_flow)
                self._update_dlg.show()
            else:
                self.lbl_update_status.setText(f"ℹ️ {msg}")
                self.lbl_update_status.setStyleSheet("color: #94A3B8; font-size: 12px;")

        self.update_mgr.check_completed.connect(on_check_done)
        self.update_mgr.check_for_updates(manual=True)

    def _start_download_flow(self, manifest):
        """Mở hộp thoại tiến trình tải bộ cài và xác thực SHA-256."""
        self._progress_dlg = UpdateProgressDialog(manifest, self.update_mgr, self)
        self.update_mgr.start_download(manifest)
        self._progress_dlg.show()

    def _update_gdrive_ui_status(self):
        """Cập nhật giao diện trạng thái kết nối Google Drive."""
        if not self.sync_mgr:
            self.lbl_gdrive_status.setText("Trạng thái: Module đồng bộ chưa khởi chạy.")
            self.lbl_gdrive_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #94A3B8;")
            return

        auth = self.sync_mgr.auth
        if auth.simulation_mode:
            self.lbl_gdrive_status.setText("Trạng thái: 🧪 Chế độ Giả lập (Simulator) — 1998 Studio Demo")
            self.lbl_gdrive_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #38BDF8;")
            self.btn_gdrive_connect.setEnabled(False)
            self.btn_gdrive_sim.setText("🧪 Thoát Chế Độ Giả Lập")
            self.btn_gdrive_disconnect.setEnabled(True)
        elif auth.is_authenticated():
            token_data = auth.load_token() or {}
            email = token_data.get("user_email", "Tài khoản Google")
            self.lbl_gdrive_status.setText(f"Trạng thái: 🟢 Đã kết nối ({email}) [Bảo mật DPAPI]")
            self.lbl_gdrive_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #10B981;")
            self.btn_gdrive_connect.setEnabled(False)
            self.btn_gdrive_sim.setText("🧪 Bật Chế Độ Giả Lập")
            self.btn_gdrive_disconnect.setEnabled(True)
        else:
            self.lbl_gdrive_status.setText("Trạng thái: 🔴 Chưa kết nối Google Drive (Bấm nút bên dưới để ủy quyền)")
            self.lbl_gdrive_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #EF4444;")
            self.btn_gdrive_connect.setEnabled(True)
            self.btn_gdrive_sim.setText("🧪 Bật Chế Độ Giả Lập")
            self.btn_gdrive_disconnect.setEnabled(False)

    def _connect_gdrive(self):
        """Khởi chạy ủy quyền Google Drive."""
        if not self.sync_mgr:
            return

        cid = self.txt_client_id.text().strip()
        csec = self.txt_client_secret.text().strip()
        if not cid or not csec:
            QMessageBox.warning(
                self,
                "Thiếu Khóa API",
                "Vui lòng nhập Google Client ID và Client Secret (hoặc bấm 'Nhập client_secrets.json' hoặc 'Bật Chế Độ Giả Lập')."
            )
            return

        self.sync_mgr.auth.client_id = cid
        self.sync_mgr.auth.client_secret = csec
        self.sync_mgr.auth.simulation_mode = False

        QMessageBox.information(
            self,
            "Mở Trình Duyệt Ủy Quyền",
            "Ứng dụng sẽ mở trình duyệt để bạn đăng nhập Google và cho phép lưu ảnh Photobooth vào Drive.\n\nSau khi đồng ý trên web, phần mềm sẽ tự động kết nối!"
        )

        ok, msg = self.sync_mgr.auth.authorize_interactive(timeout_sec=90)
        self._update_gdrive_ui_status()
        if ok:
            QMessageBox.information(self, "Thành Công", msg)
        else:
            QMessageBox.critical(self, "Lỗi Ủy Quyền", msg)

    def _toggle_simulation_mode(self):
        """Bật / tắt chế độ giả lập phục vụ kiểm thử."""
        if not self.sync_mgr:
            return

        auth = self.sync_mgr.auth
        if auth.simulation_mode:
            auth.simulation_mode = False
            self.config_mgr.set("cloud.gdrive_simulation_mode", False)
            self.config_mgr.save()
            auth.revoke()
        else:
            auth.simulation_mode = True
            self.config_mgr.set("cloud.gdrive_simulation_mode", True)
            self.config_mgr.save()
            auth.authorize_interactive()

        self._update_gdrive_ui_status()

    def _disconnect_gdrive(self):
        """Ngắt kết nối Google Drive."""
        if not self.sync_mgr:
            return

        reply = QMessageBox.question(
            self,
            "Xác Nhận Ngắt Kết Nối",
            "Bạn có chắc muốn hủy kết nối tài khoản Google Drive hiện tại?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.sync_mgr.auth.simulation_mode = False
            self.config_mgr.set("cloud.gdrive_simulation_mode", False)
            self.config_mgr.save()
            self.sync_mgr.auth.revoke()
            self._update_gdrive_ui_status()
            QMessageBox.information(self, "Đã Ngắt Kết Nối", "Đã xóa toàn bộ token xác thực Google Drive khỏi máy.")

    def _load_client_secrets_json(self):
        """Đọc file client_secrets.json tải từ Google Cloud Console."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn tệp client_secrets.json",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            client_info = data.get("installed") or data.get("web") or {}
            cid = client_info.get("client_id", "")
            csec = client_info.get("client_secret", "")

            if cid and csec:
                self.txt_client_id.setText(cid)
                self.txt_client_secret.setText(csec)
                QMessageBox.information(
                    self,
                    "Nhập Thành Công",
                    f"Đã nạp Client ID: {cid[:20]}...\nVui lòng bấm 'Lưu Toàn Bộ Cài Đặt' và 'Kết Nối Google Drive'!"
                )
            else:
                QMessageBox.warning(self, "Tệp Không Hợp Lệ", "Không tìm thấy client_id và client_secret trong tệp JSON đã chọn.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Đọc File", f"Không thể đọc file: {e}")

    def _test_gdrive_upload(self):
        """Thử nghiệm tạo và tải lên một file mẫu lên Google Drive."""
        if not self.sync_mgr or not self.sync_mgr.is_ready():
            QMessageBox.warning(self, "Chưa Sẵn Sàng", "Google Drive chưa được kết nối. Hãy kết nối hoặc bật chế độ Giả Lập trước khi thử.")
            return

        # Tạo một ảnh test tạm thời
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (600, 400), color=(11, 19, 43))
            draw = ImageDraw.Draw(img)
            draw.text((40, 180), "1998 TEAM Photobooth - Test Upload", fill=(212, 175, 55))

            tmp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(tmp_dir, "1998_test_upload.jpg")
            img.save(tmp_path, "JPEG")

            # Đưa vào sync manager
            self.sync_mgr.enqueue(tmp_path, "Kiem_Tra_Dong_Bo")
            QMessageBox.information(
                self,
                "Đã Đưa Vào Hàng Đợi",
                "Đã đưa ảnh kiểm tra vào hàng đợi đồng bộ ngầm Google Drive.\nBạn có thể kiểm tra tab 'Sự Kiện & Thư Viện' hoặc theo dõi thông báo thành công!"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Tạo File Test", f"Lỗi: {e}")

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

    def _open_filter_studio(self):
        if not self.filter_engine:
            QMessageBox.warning(self, "Thông Báo", "Filter Engine chưa được nạp.")
            return
        dlg = FilterEditorDialog(self.filter_engine, parent=self)
        dlg.exec()
