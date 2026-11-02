"""
1998 TEAM — Photobooth Guest Idle Attract Screen (Màn Hình Chờ Khách)
Thiết kế lại theo phong cách WARM MOCHA × CHAMPAGNE GOLD – PREMIUM STUDIO:
- Fullscreen touchscreen attract view đồng bộ Warm Mocha cao cấp.
- 1998 Studio Logo đặt trang trọng tại vị trí trung tâm.
- Lời chào mừng và thông tin sự kiện động (Dynamic Event Metadata).
- Nút "CHẠM ĐỂ BẮT ĐẦU" vàng Champagne quý phái, hoàn hảo ở chính giữa, tuyệt đối không bị cắt chữ.
- Nút Cài đặt quản trị viên (Admin button) 44×44px kín đáo ở góc trên với bảo mật PIN và thao tác bí mật 5 lần chạm góc.
- Bố cục tối ưu, tinh giản, không bị choán chỗ bởi dải ảnh mẫu cồng kềnh.
"""

import os
import time
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QCursor, QLinearGradient

from vietphotobooth.desktop.icons import (
    get_svg_pixmap, COLOR_GOLD, COLOR_WHITE, COLOR_BLUE,
    get_brand_logo_pixmap, get_brand_logo_tight_pixmap
)
from vietphotobooth.desktop.styles import (
    THEME_BG_MAIN, THEME_BG_SECONDARY, THEME_SURFACE, THEME_BORDER,
    THEME_TEXT_PRIMARY, THEME_TEXT_SECONDARY, THEME_TEXT_DISABLED,
    THEME_GOLD, THEME_GOLD_LIGHT, THEME_GOLD_DARK, THEME_GOLD_PALE
)
from vietphotobooth.core.logger import get_logger

logger = get_logger()

LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Branding", "logo_1998_transparent.png"))


class GuestIdleScreen(QWidget):
    """Màn hình chờ toàn màn hình chào đón khách chụp ảnh phong cách Warm Mocha Studio Welcome."""
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
        # Thiết kế nền Soft Taupe Studio ấm áp, dịu mắt, tối giản và sang trọng
        self.setStyleSheet(f"""
            GuestIdleScreen {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 {THEME_BG_MAIN}, stop:0.5 #D2CEC5, stop:1 {THEME_BG_MAIN});
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 24, 40, 32)
        main_layout.setSpacing(16)

        # 1. TOP BAR: THÔNG TIN THƯƠNG HIỆU & NÚT ADMIN KÍN ĐÁO (44x44px)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self.lbl_top_brand = QLabel("✨ 1998 STUDIO PHÓNG SỰ CƯỚI")
        self.lbl_top_brand.setStyleSheet(
            f"color: {THEME_GOLD_DARK}; font-size: 13px; font-weight: 800; letter-spacing: 2px; border: none; background: transparent;"
        )
        top_bar.addWidget(self.lbl_top_brand)

        top_bar.addStretch()

        # Nút cài đặt quản trị viên kín đáo (44x44px)
        self.btn_admin = QPushButton()
        self.btn_admin.setIcon(get_svg_pixmap("settings", 20, THEME_GOLD))
        self.btn_admin.setIconSize(QSize(20, 20))
        self.btn_admin.setFixedSize(44, 44)
        self.btn_admin.setCursor(Qt.PointingHandCursor)
        self.btn_admin.setAccessibleName("Cài đặt quản trị viên")
        self.btn_admin.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME_SURFACE};
                border: 1.5px solid {THEME_BORDER};
                border-radius: 22px;
            }}
            QPushButton:hover {{
                background-color: {THEME_BG_SECONDARY};
                border: 1.5px solid {THEME_GOLD};
            }}
            QPushButton:pressed {{
                background-color: #A39F96;
            }}
        """)
        self.btn_admin.setToolTip("Quản trị viên: Nhấn để mở khóa & thoát toàn màn hình")
        self.btn_admin.clicked.connect(self._on_admin_clicked)
        top_bar.addWidget(self.btn_admin)
        main_layout.addLayout(top_bar)

        main_layout.addStretch(1)

        # 2. KHU VỰC TRUNG TÂM HOÀN TOÀN TỐI GIẢN (MINIMALIST LUXURY - KHÔNG KHUNG VIỀN HỘP)
        center_container = QWidget()
        center_container.setStyleSheet("background: transparent; border: none;")
        v_center = QVBoxLayout(center_container)
        v_center.setAlignment(Qt.AlignCenter)
        v_center.setContentsMargins(20, 10, 20, 10)
        v_center.setSpacing(18)

        # Logo 1998 Studio đặt trang trọng ở trung tâm, không khung viền
        pix = get_brand_logo_tight_pixmap(height=96)
        if not pix.isNull():
            self.lbl_logo = QLabel()
            self.lbl_logo.setPixmap(pix)
            self.lbl_logo.setAlignment(Qt.AlignCenter)
            self.lbl_logo.setStyleSheet("border: none; background: transparent;")
            self.lbl_logo.setToolTip("1998 TEAM — Photobooth")
            self.lbl_logo.setAccessibleName("Logo 1998 TEAM Photobooth")
            v_center.addWidget(self.lbl_logo)
        else:
            self.lbl_logo_text = QLabel("1998 TEAM")
            self.lbl_logo_text.setStyleSheet(f"font-size: 38px; font-weight: 900; color: {THEME_GOLD}; border: none; background: transparent;")
            self.lbl_logo_text.setAlignment(Qt.AlignCenter)
            v_center.addWidget(self.lbl_logo_text)

        # Tiêu đề CHÀO MỪNG QUÝ KHÁCH - Không viền bao quanh
        self.lbl_event_title = QLabel("CHÀO MỪNG QUÝ KHÁCH")
        self.lbl_event_title.setAlignment(Qt.AlignCenter)
        self.lbl_event_title.setStyleSheet(f"""
            color: {THEME_TEXT_PRIMARY};
            font-size: 30px;
            font-weight: 800;
            letter-spacing: 3px;
            border: none;
            background: transparent;
        """)
        v_center.addWidget(self.lbl_event_title)

        # Thông điệp chào mừng sự kiện - Không viền bao quanh
        self.lbl_event_subtitle = QLabel("Lưu giữ những khoảnh khắc tuyệt vời cùng chúng tôi")
        self.lbl_event_subtitle.setAlignment(Qt.AlignCenter)
        self.lbl_event_subtitle.setStyleSheet(f"""
            color: {THEME_TEXT_SECONDARY};
            font-size: 16px;
            font-weight: 600;
            font-style: italic;
            border: none;
            background: transparent;
        """)
        v_center.addWidget(self.lbl_event_subtitle)

        self._refresh_event_metadata()

        v_center.addSpacing(16)

        # 3. NÚT HERO KHỔNG LỒ "CHẠM ĐỂ BẮT ĐẦU" VÀNG CHAMPAGNE (KHÔNG CẮT CHỮ)
        self.btn_touch_start = QPushButton()
        self.btn_touch_start.setCursor(Qt.PointingHandCursor)
        self.btn_touch_start.setMinimumSize(460, 96)
        self.btn_touch_start.setMaximumWidth(520)
        self.btn_touch_start.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 {THEME_GOLD_LIGHT}, stop:0.45 {THEME_GOLD}, stop:1 {THEME_GOLD_DARK});
                color: #FFFFFF;
                border: 2px solid {THEME_GOLD_PALE};
                border-radius: 26px;
                padding: 12px 32px;
            }}
            QPushButton:hover {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #DFCFB0, stop:0.45 #B99D69, stop:1 #987C49);
                border: 2px solid #FFFFFF;
            }}
            QPushButton:pressed {{
                background: {THEME_GOLD_DARK};
            }}
        """)

        touch_layout = QVBoxLayout(self.btn_touch_start)
        touch_layout.setAlignment(Qt.AlignCenter)
        touch_layout.setContentsMargins(12, 10, 12, 10)
        touch_layout.setSpacing(4)

        lbl_touch_txt = QLabel("CHẠM ĐỂ BẮT ĐẦU")
        lbl_touch_txt.setAlignment(Qt.AlignCenter)
        lbl_touch_txt.setStyleSheet(
            "font-family: 'Segoe UI', 'Montserrat', Arial, sans-serif; font-size: 26px; font-weight: 800; color: #FFFFFF; letter-spacing: 2px; border: none; background: transparent;"
        )
        touch_layout.addWidget(lbl_touch_txt)

        h_sub_icon = QHBoxLayout()
        h_sub_icon.setAlignment(Qt.AlignCenter)
        h_sub_icon.setSpacing(8)

        lbl_touch_icon = QLabel()
        lbl_touch_icon.setPixmap(get_svg_pixmap("touch", 18, "#FFFFFF"))
        lbl_touch_icon.setStyleSheet("border: none; background: transparent;")
        h_sub_icon.addWidget(lbl_touch_icon)

        lbl_touch_hint = QLabel("Chạm vào màn hình để chụp ảnh ngay")
        lbl_touch_hint.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {THEME_GOLD_PALE}; letter-spacing: 0.5px; border: none; background: transparent;"
        )
        h_sub_icon.addWidget(lbl_touch_hint)
        touch_layout.addLayout(h_sub_icon)

        self.btn_touch_start.clicked.connect(self._on_screen_tapped)
        v_center.addWidget(self.btn_touch_start, 0, Qt.AlignCenter)

        v_center.addSpacing(10)

        # Slogan thương hiệu phía dưới
        lbl_slogan = QLabel("✨ Trải nghiệm Photobooth lấy ảnh liền chuyên nghiệp • 1998 TEAM")
        lbl_slogan.setAlignment(Qt.AlignCenter)
        lbl_slogan.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {THEME_TEXT_SECONDARY};
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        v_center.addWidget(lbl_slogan)

        main_layout.addWidget(center_container, 0, Qt.AlignCenter)
        main_layout.addStretch(1)

        # 4. BOTTOM BAR: FOOTER TINH TẾ
        bottom_bar = QHBoxLayout()
        lbl_footer_left = QLabel("1998 TEAM Photobooth v2.0")
        lbl_footer_left.setStyleSheet(f"color: {THEME_TEXT_DISABLED}; font-size: 11px;")
        bottom_bar.addWidget(lbl_footer_left)
        bottom_bar.addStretch()
        lbl_footer_right = QLabel("Chạm bất kỳ đâu trên màn hình để chụp")
        lbl_footer_right.setStyleSheet(f"color: {THEME_TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        bottom_bar.addWidget(lbl_footer_right)
        main_layout.addLayout(bottom_bar)

    def _refresh_event_metadata(self):
        """Đọc và hiển thị thông tin sự kiện động từ cấu hình."""
        if not self.config_mgr:
            return

        current_event = self.config_mgr.get("current_event", "")
        welcome_title = self.config_mgr.get("kiosk.welcome_title")
        welcome_sub = self.config_mgr.get("kiosk.welcome_subtitle")

        if welcome_title:
            self.lbl_event_title.setText(welcome_title)
        elif current_event and current_event != "SuKien_MacDinh":
            formatted_name = current_event.replace("_", " ").upper()
            self.lbl_event_title.setText(f"SỰ KIỆN: {formatted_name}")
        else:
            self.lbl_event_title.setText("CHÀO MỪNG QUÝ KHÁCH")

        if welcome_sub:
            self.lbl_event_subtitle.setText(welcome_sub)
        else:
            self.lbl_event_subtitle.setText("Lưu giữ những khoảnh khắc tuyệt vời cùng chúng tôi")

    def update_event_info(self, title: str = "", subtitle: str = ""):
        """Cập nhật tiêu đề và lời chào sự kiện động."""
        if title:
            self.lbl_event_title.setText(title)
        if subtitle:
            self.lbl_event_subtitle.setText(subtitle)

    def mousePressEvent(self, event):
        """Khách chạm vào màn hình bắt đầu chụp; Quản trị viên gõ nhanh góc trên để mở khóa bí mật."""
        if event.button() == Qt.LeftButton:
            pos = event.position() if hasattr(event, "position") else event.pos()
            x = pos.x()
            y = pos.y()
            w = self.width()

            # Thao tác bí mật: gõ 5 lần trong vòng 3 giây ở góc trên (trái hoặc phải)
            now = time.time()
            if (x > w - 120 and y < 120) or (x < 120 and y < 120):
                if not hasattr(self, "_secret_tap_history"):
                    self._secret_tap_history = []
                self._secret_tap_history = [t for t in self._secret_tap_history if now - t < 3.0]
                self._secret_tap_history.append(now)
                if len(self._secret_tap_history) >= 5:
                    self._secret_tap_history.clear()
                    logger.info("Phát hiện thao tác bí mật 5 lần chạm góc — Kích hoạt xác thực mã PIN thoát Kiosk.")
                    self._on_admin_clicked()
                    return

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
