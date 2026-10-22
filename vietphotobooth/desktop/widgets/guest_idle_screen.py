"""
1998 TEAM — Photobooth Guest Idle Attract Screen (Màn Hình Chờ Khách)
Matches exact design of Panel 3:
- Fullscreen touchscreen attract view.
- Luxury studio wedding theme: soft checkerboard pattern, floral decorations, tilted sample photobooth strips on left & right.
- Center branding: "1998 Studio — 1998 TEAM PHOTOBOOTH".
- Giant interactive touch button: "CHẠM ĐỂ BẮT ĐẦU" with touch hand icon.
- Slogan: "Lưu giữ khoảnh khắc — Cùng bạn trong mọi sự kiện".
- Discreet top-right admin settings icon with PIN protection to exit fullscreen.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QCursor, QLinearGradient

from vietphotobooth.desktop.icons import get_svg_pixmap, COLOR_GOLD, COLOR_WHITE, COLOR_BLUE
from vietphotobooth.core.logger import get_logger

logger = get_logger()

LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "logo_1998_studio.png"))
SAMPLE_PORTRAIT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "sample_slot_portrait.jpg"))

class GuestIdleScreen(QWidget):
    """Màn hình chờ toàn màn hình chào đón khách chụp ảnh."""
    start_requested = Signal()           # Khi khách chạm vào màn hình để bắt đầu
    admin_exit_requested = Signal()      # Khi quản trị viên mở khóa để thoát
    touch_to_start = start_requested     # Alias
    admin_requested = admin_exit_requested # Alias

    def start_animations(self):
        """Bật hiệu ứng chuyển động nếu có."""
        pass

    def stop_animations(self):
        """Dừng hiệu ứng khi rời màn hình chờ."""
        pass

    def __init__(self, auth_mgr=None, config_mgr=None, parent=None):
        super().__init__(parent)
        self.auth_mgr = auth_mgr
        self.config_mgr = config_mgr
        self.setCursor(Qt.PointingHandCursor)

        self._init_ui()

    def _init_ui(self):
        # Thiết kế nền gradient xanh pastel bàn cờ chuẩn studio tiệc cưới
        self.setStyleSheet("""
            GuestIdleScreen {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #EDF6FF, stop:0.5 #F0FDF4, stop:1 #E0F2FE);
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)

        # 1. TOP BAR: DISCREET ADMIN SETTINGS BUTTON
        top_bar = QHBoxLayout()
        top_bar.addStretch()

        self.btn_admin = QPushButton()
        self.btn_admin.setIcon(get_svg_pixmap("settings", 22, COLOR_GOLD))
        self.btn_admin.setIconSize(QSize(22, 22))
        self.btn_admin.setFixedSize(44, 44)
        self.btn_admin.setCursor(Qt.PointingHandCursor)
        self.btn_admin.setAccessibleName("Cài đặt quản trị viên")
        self.btn_admin.setStyleSheet(
            "QPushButton { background-color: rgba(15, 23, 42, 0.4); border: 1.5px solid rgba(212, 175, 55, 0.6); "
            "border-radius: 22px; }"
            "QPushButton:hover { background-color: rgba(15, 23, 42, 0.8); border: 2px solid #D4AF37; }"
        )
        self.btn_admin.setToolTip("Quản trị viên: Nhấn để mở khóa & thoát toàn màn hình")
        self.btn_admin.clicked.connect(self._on_admin_clicked)
        top_bar.addWidget(self.btn_admin)
        main_layout.addLayout(top_bar)

        # 2. BODY KHU VỰC CHÍNH: 3 CỘT (Dải ảnh trái - Trung tâm Chạm Để Bắt Đầu - Dải ảnh phải)
        body_layout = QHBoxLayout()
        body_layout.setSpacing(30)

        # Cột Trái: Dải ảnh mẫu uốn nhẹ phong cách Wedding
        strip_left = self._create_sample_strip_widget(is_left=True)
        body_layout.addWidget(strip_left, 1, Qt.AlignCenter)

        # Cột Giữa: Logo + CHẠM ĐỂ BẮT ĐẦU + Slogan
        v_center = QVBoxLayout()
        v_center.setAlignment(Qt.AlignCenter)
        v_center.setSpacing(20)

        # Logo 1998 Studio
        if os.path.exists(LOGO_PATH):
            lbl_logo = QLabel()
            pix = QPixmap(LOGO_PATH)
            lbl_logo.setPixmap(pix.scaledToHeight(75, Qt.SmoothTransformation))
            lbl_logo.setAlignment(Qt.AlignCenter)
            v_center.addWidget(lbl_logo)
        else:
            lbl_logo_text = QLabel("1998 Studio")
            lbl_logo_text.setStyleSheet("font-size: 38px; font-weight: 900; color: #D4AF37; font-family: 'Great Vibes', cursive;")
            lbl_logo_text.setAlignment(Qt.AlignCenter)
            v_center.addWidget(lbl_logo_text)

        lbl_sub_brand = QLabel("1998 TEAM PHOTOBOOTH")
        lbl_sub_brand.setAlignment(Qt.AlignCenter)
        lbl_sub_brand.setStyleSheet("font-size: 14px; font-weight: 900; color: #0369A1; letter-spacing: 3px;")
        v_center.addWidget(lbl_sub_brand)

        v_center.addSpacing(25)

        # NÚT KHỔNG LỒ "CHẠM ĐỂ BẮT ĐẦU"
        self.btn_touch_start = QPushButton()
        self.btn_touch_start.setCursor(Qt.PointingHandCursor)
        self.btn_touch_start.setMinimumSize(420, 160)
        self.btn_touch_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0284C7, stop:1 #0369A1);
                color: #FFFFFF;
                border: 3px solid #BAE6FD;
                border-radius: 28px;
                padding: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0EA5E9, stop:1 #0284C7);
                border: 3px solid #D4AF37;
            }
            QPushButton:pressed {
                background-color: #0369A1;
            }
        """)

        touch_layout = QVBoxLayout(self.btn_touch_start)
        touch_layout.setAlignment(Qt.AlignCenter)
        touch_layout.setSpacing(6)

        lbl_touch_txt = QLabel("CHẠM ĐỂ\nBẮT ĐẦU")
        lbl_touch_txt.setAlignment(Qt.AlignCenter)
        lbl_touch_txt.setStyleSheet("font-size: 34px; font-weight: 900; color: #FFFFFF; letter-spacing: 1.5px; line-height: 1.1;")
        touch_layout.addWidget(lbl_touch_txt)

        lbl_touch_icon = QLabel()
        lbl_touch_icon.setPixmap(get_svg_pixmap("touch", 36, "#FFFFFF"))
        lbl_touch_icon.setAlignment(Qt.AlignCenter)
        touch_layout.addWidget(lbl_touch_icon)

        self.btn_touch_start.clicked.connect(self._on_screen_tapped)
        v_center.addWidget(self.btn_touch_start, 0, Qt.AlignCenter)

        v_center.addSpacing(20)

        # Slogan thanh lịch
        lbl_slogan = QLabel("Lưu giữ khoảnh khắc\nCùng bạn trong mọi sự kiện")
        lbl_slogan.setAlignment(Qt.AlignCenter)
        lbl_slogan.setStyleSheet("font-size: 18px; font-weight: bold; color: #1E3A8A; font-style: italic; line-height: 1.3;")
        v_center.addWidget(lbl_slogan)

        body_layout.addLayout(v_center, 2)

        # Cột Phải: Dải ảnh mẫu thứ hai
        strip_right = self._create_sample_strip_widget(is_left=False)
        body_layout.addWidget(strip_right, 1, Qt.AlignCenter)

        main_layout.addLayout(body_layout, 1)

    def _create_sample_strip_widget(self, is_left: bool = True) -> QFrame:
        """Tạo khung dải ảnh mẫu hoa nhã nhặn uốn lượn hai bên màn hình chào."""
        frame = QFrame()
        frame.setFixedSize(160, 480)
        frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 2px solid #E2E8F0;
                border-radius: 12px;
                padding: 6px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        for i in range(3):
            slot = QLabel()
            slot.setAlignment(Qt.AlignCenter)
            slot.setStyleSheet("background-color: #F1F5F9; border-radius: 6px; border: 1px solid #CBD5E1;")
            if os.path.exists(SAMPLE_PORTRAIT):
                pix = QPixmap(SAMPLE_PORTRAIT)
                slot.setPixmap(pix.scaled(140, 130, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            else:
                slot.setText("1998")
                slot.setStyleSheet("color: #D4AF37; font-weight: bold;")
            layout.addWidget(slot)

        lbl_foot = QLabel("Good Memories" if is_left else "Happy Moments")
        lbl_foot.setAlignment(Qt.AlignCenter)
        lbl_foot.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B; font-style: italic;")
        layout.addWidget(lbl_foot)

        return frame

    def mousePressEvent(self, event):
        """Khách chạm vào bất kỳ đâu trên màn hình đều kích hoạt bắt đầu chụp."""
        if event.button() == Qt.LeftButton:
            self._on_screen_tapped()
        super().mousePressEvent(event)

    def _on_screen_tapped(self):
        """Xử lý bắt đầu chụp ảnh."""
        logger.info("Khách đã chạm vào màn hình chờ — Chuyển sang luồng chụp ảnh.")
        self.start_requested.emit()

    def _on_admin_clicked(self):
        """Quản trị viên mở khóa màn hình chờ."""
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Thoát Màn Hình Chờ"):
                return
        self.admin_exit_requested.emit()
