"""
1998 TEAM PHOTOBOOTH v2.0.0 — QR SHARING & OFFLINE LAN PAGE
Trung tâm quản lý chia sẻ ảnh qua mã QR và mạng Wi-Fi cục bộ (Offline LAN).
Cho phép khách hàng quét mã QR trên điện thoại tải ảnh trực tiếp từ quầy photobooth
mà không cần kết nối Internet ra ngoài.
"""

import os
from typing import Optional
import qrcode
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QImage, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QCheckBox, QMessageBox
)

from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.desktop.icons import (
    COLOR_GOLD, COLOR_GOLD_LIGHT, COLOR_WHITE, COLOR_SLATE,
    COLOR_GREEN, COLOR_BLUE, get_svg_icon
)


class QRSharingPage(QWidget):
    """
    Trang Quản Trị & Giám Sát Chia Sẻ Mã QR Đa Kênh v2.0.
    """
    def __init__(
        self,
        token_mgr: Optional[TokenManager] = None,
        event_mgr: Optional[EventManager] = None,
        config_mgr: Optional[ConfigManager] = None,
        parent=None
    ):
        super().__init__(parent)
        self.token_mgr = token_mgr or TokenManager()
        self.event_mgr = event_mgr
        self.config_mgr = config_mgr

        self.setStyleSheet("background-color: #C8C5BD; color: #353631;")
        self._current_token_obj = None

        self._init_ui()
        self.generate_demo_qr()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        h_head = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)

        lbl_title = QLabel("📲 <b>TRUNG TÂM CHIA SẺ MÃ QR & MẠNG NỘI BỘ (OFFLINE LAN)</b>")
        lbl_title.setStyleSheet("color: #353631; font-size: 16px; font-weight: 800;")
        v_title.addWidget(lbl_title)

        lbl_sub = QLabel("Chia sẻ ảnh siêu tốc không cần Internet qua mạng Wi-Fi riêng biệt 1998 TEAM Photobooth")
        lbl_sub.setStyleSheet("color: #716F68; font-size: 11px;")
        v_title.addWidget(lbl_sub)
        h_head.addLayout(v_title)
        h_head.addStretch()

        self.btn_open_browser = QPushButton(" Mở Thử Trên Trình Duyệt")
        self.btn_open_browser.setIcon(get_svg_icon("preview", 14, COLOR_GOLD))
        self.btn_open_browser.setFixedHeight(36)
        self.btn_open_browser.setCursor(Qt.PointingHandCursor)
        self.btn_open_browser.setStyleSheet("""
            QPushButton {
                background-color: #D9D5CC;
                border: 1.5px solid #AAA69D;
                color: #353631;
                font-size: 12px;
                font-weight: bold;
                border-radius: 8px;
                padding: 0 16px;
            }
            QPushButton:hover {
                border-color: #AD905B;
                color: #353631;
                background-color: #B9B5AB;
            }
        """)
        self.btn_open_browser.clicked.connect(self._open_in_browser)
        h_head.addWidget(self.btn_open_browser)
        layout.addLayout(h_head)

        # Two-column content
        h_content = QHBoxLayout()
        h_content.setSpacing(16)

        # Cột trái: Thông tin Wi-Fi Hotspot & Cấu hình mạng LAN
        card_wifi = QFrame()
        card_wifi.setStyleSheet("""
            QFrame {
                background-color: #D9D5CC;
                border: 1.5px solid #AAA69D;
                border-radius: 12px;
            }
        """)
        l_wifi = QVBoxLayout(card_wifi)
        l_wifi.setContentsMargins(18, 16, 18, 16)
        l_wifi.setSpacing(12)

        lbl_wifi_head = QLabel("📶 <b>ĐIỂM PHÁT SÓNG WI-FI QUẦY PHOTOBOOTH</b>")
        lbl_wifi_head.setStyleSheet("color: #353631; font-size: 13px; font-weight: bold; border: none;")
        l_wifi.addWidget(lbl_wifi_head)

        grid_w = QGridLayout()
        grid_w.setSpacing(8)

        local_ip = self.token_mgr.get_local_ip()
        port = getattr(self.token_mgr, "port", 8080)

        items = [
            ("Tên mạng Wi-Fi (SSID):", "1998TEAM-PHOTOBOOTH", True),
            ("Mật khẩu Wi-Fi:", "1998studio", True),
            ("Địa chỉ máy chủ cục bộ:", f"http://{local_ip}:{port}", False),
            ("Giao thức:", "FastAPI LAN Web Server", False),
            ("Chế độ bảo mật:", "Mã hóa Token ngẫu nhiên 128-bit", False),
            ("Thời hạn lưu trữ mã:", "24 giờ (Tự động dọn dẹp)", False),
        ]

        for r, (k, v, is_hi) in enumerate(items):
            lk = QLabel(k)
            lk.setStyleSheet("color: #716F68; font-size: 12px; border: none;")
            lv = QLabel(v)
            color = "#AD905B" if is_hi else "#353631"
            lv.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: {'bold' if is_hi else 'normal'}; border: none;")
            grid_w.addWidget(lk, r, 0)
            grid_w.addWidget(lv, r, 1)

        l_wifi.addLayout(grid_w)

        # Checkbox cấu hình
        self.chk_auto_show_qr = QCheckBox("Tự động hiển thị mã QR trên màn hình sau khi chụp xong")
        self.chk_auto_show_qr.setChecked(True)
        self.chk_auto_show_qr.setStyleSheet("color: #353631; font-size: 12px; border: none; margin-top: 10px;")
        l_wifi.addWidget(self.chk_auto_show_qr)

        self.chk_print_qr = QCheckBox("In kèm mã QR góc nhỏ trên ảnh in dải")
        self.chk_print_qr.setChecked(False)
        self.chk_print_qr.setStyleSheet("color: #353631; font-size: 12px; border: none;")
        l_wifi.addWidget(self.chk_print_qr)

        l_wifi.addStretch()
        h_content.addWidget(card_wifi, 50)

        # Cột phải: Mã QR và Mô phỏng hiển thị trên điện thoại
        card_qr = QFrame()
        card_qr.setStyleSheet("""
            QFrame {
                background-color: #D9D5CC;
                border: 1.5px solid #AAA69D;
                border-radius: 12px;
            }
        """)
        l_qr = QVBoxLayout(card_qr)
        l_qr.setContentsMargins(18, 16, 18, 16)
        l_qr.setSpacing(12)

        lbl_qr_head = QLabel("📱 <b>MÃ QR TẢI ẢNH (GUEST MOBILE PREVIEW)</b>")
        lbl_qr_head.setStyleSheet("color: #353631; font-size: 13px; font-weight: bold; border: none;")
        l_qr.addWidget(lbl_qr_head)

        # Khung hiển thị mã QR
        self.lbl_qr_display = QLabel()
        self.lbl_qr_display.setAlignment(Qt.AlignCenter)
        self.lbl_qr_display.setFixedSize(220, 220)
        self.lbl_qr_display.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1.5px solid #AAA69D;
            border-radius: 12px;
            padding: 8px;
        """)
        l_qr.addWidget(self.lbl_qr_display, 0, Qt.AlignCenter)

        self.lbl_url_display = QLabel("Đang tải đường dẫn chia sẻ...")
        self.lbl_url_display.setAlignment(Qt.AlignCenter)
        self.lbl_url_display.setStyleSheet("color: #AD905B; font-size: 12px; font-weight: bold; border: none;")
        l_qr.addWidget(self.lbl_url_display)

        # Nút tạo lại mã
        self.btn_gen_new = QPushButton("🔄 Tạo Mã Mới")
        self.btn_gen_new.setFixedHeight(32)
        self.btn_gen_new.setCursor(Qt.PointingHandCursor)
        self.btn_gen_new.setStyleSheet("""
            QPushButton {
                background-color: #D9D5CC;
                border: 1.5px solid #AAA69D;
                color: #353631;
                font-size: 11px;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                border-color: #AD905B;
                color: #353631;
                background-color: #B9B5AB;
            }
        """)
        self.btn_gen_new.clicked.connect(self.generate_demo_qr)
        l_qr.addWidget(self.btn_gen_new, 0, Qt.AlignCenter)

        l_qr.addStretch()
        h_content.addWidget(card_qr, 50)

        layout.addLayout(h_content)
        layout.addStretch()

    def generate_demo_qr(self):
        """Sinh mã QR mẫu để hiển thị trực quan."""
        active_event = self.event_mgr.get_active_event_name() if self.event_mgr else "Demo_Event"
        token_obj = self.token_mgr.create_token(active_event, "Session_Preview")
        self._current_token_obj = token_obj

        share_url = self.token_mgr.get_share_url(token_obj.token)
        self.lbl_url_display.setText(share_url)

        # Tạo QPixmap từ qrcode
        qr_img = qrcode.make(share_url)
        rgb = qr_img.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.lbl_qr_display.setPixmap(pix.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _open_in_browser(self):
        if self._current_token_obj:
            url = self.token_mgr.get_share_url(self._current_token_obj.token)
            QDesktopServices.openUrl(QUrl(url))
        else:
            QMessageBox.information(self, "Thông Báo", "Chưa có mã QR nào được kích hoạt.")
