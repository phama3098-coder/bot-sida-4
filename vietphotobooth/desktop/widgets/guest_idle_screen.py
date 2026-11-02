"""
1998 TEAM — Photobooth Guest Idle Attract Screen (Màn Hình Chờ Khách)
Thiết kế lại theo phong cách WARM MOCHA × CHAMPAGNE GOLD – PREMIUM STUDIO:
- Fullscreen touchscreen attract view đồng bộ Soft Taupe Studio cao cấp.
- 1998 Studio Logo đặt trang trọng tại vị trí trung tâm, bảo toàn tỷ lệ, tuyệt đối không crop hay cắt viền.
- Lời chào mừng và thông tin sự kiện động (Dynamic Event Metadata).
- Nút "CHẠM ĐỂ BẮT ĐẦU" vàng Champagne quý phái, tỷ lệ cân đối, chữ chính 1 dòng và dòng hướng dẫn phụ bên dưới.
- Nút Cài đặt quản trị viên (Admin button) 44×44px kín đáo ở góc trên với bảo mật PIN và thao tác bí mật 5 lần chạm góc.
- Bố cục co giãn linh hoạt bằng spacers/stretches, thích ứng mượt mà trên 1366×768, 1600×900, 1920×1080.
"""

import os
import time
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QPixmap, QColor, QFont, QCursor

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
    """Màn hình chờ toàn màn hình chào đón khách chụp ảnh phong cách Soft Taupe Studio Welcome."""
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
        # Nền Soft Taupe Studio ấm áp, dịu mắt, tối giản và sang trọng
        self.setStyleSheet(f"""
            GuestIdleScreen {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 {THEME_BG_MAIN}, stop:0.5 #D0CCC3, stop:1 {THEME_BG_MAIN});
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 24, 40, 28)
        main_layout.setSpacing(0)

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

        # Layout co giãn phía trên
        main_layout.addStretch(2)

        # 2. KHU VỰC TRUNG TÂM TỐI GIẢN (MINIMALIST LUXURY - CÂN ĐỐI CẢ NGANG VÀ DỌC)
        self.center_container = QWidget()
        self.center_container.setStyleSheet("background: transparent; border: none;")
        v_center = QVBoxLayout(self.center_container)
        v_center.setAlignment(Qt.AlignCenter)
        v_center.setContentsMargins(0, 0, 0, 0)
        v_center.setSpacing(0)

        # Logo 1998 Studio đặt trang trọng ở trung tâm, không crop hay cắt viền
        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignCenter)
        self.lbl_logo.setStyleSheet("border: none; background: transparent;")
        self.lbl_logo.setToolTip("1998 TEAM — Photobooth")
        self.lbl_logo.setAccessibleName("Logo 1998 TEAM Photobooth")
        self._update_logo_pixmap(target_height=82)
        v_center.addWidget(self.lbl_logo, 0, Qt.AlignCenter)

        v_center.addSpacing(14)

        # Tiêu đề CHÀO MỪNG QUÝ KHÁCH - Rõ ràng, không viền hộp
        self.lbl_event_title = QLabel("CHÀO MỪNG QUÝ KHÁCH")
        self.lbl_event_title.setAlignment(Qt.AlignCenter)
        self.lbl_event_title.setStyleSheet(f"""
            color: {THEME_TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 800;
            letter-spacing: 2.5px;
            border: none;
            background: transparent;
        """)
        v_center.addWidget(self.lbl_event_title, 0, Qt.AlignCenter)

        v_center.addSpacing(6)

        # Thông điệp chào mừng sự kiện - Độ tương phản cao, trang nhã
        self.lbl_event_subtitle = QLabel("Lưu giữ những khoảnh khắc tuyệt vời cùng chúng tôi")
        self.lbl_event_subtitle.setAlignment(Qt.AlignCenter)
        self.lbl_event_subtitle.setStyleSheet(f"""
            color: #55534D;
            font-size: 15px;
            font-weight: 600;
            font-style: italic;
            border: none;
            background: transparent;
        """)
        v_center.addWidget(self.lbl_event_subtitle, 0, Qt.AlignCenter)

        self._refresh_event_metadata()

        v_center.addSpacing(22)

        # 3. NÚT HERO "CHẠM ĐỂ BẮT ĐẦU" VÀNG CHAMPAGNE (CÂN ĐỐI, GỌN GÀNG, KHÔNG DÀI QUÁ MỨC)
        self.btn_touch_start = QPushButton()
        self.btn_touch_start.setCursor(Qt.PointingHandCursor)
        self.btn_touch_start.setFixedSize(360, 74)
        self.btn_touch_start.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 {THEME_GOLD_LIGHT}, stop:0.45 {THEME_GOLD}, stop:1 {THEME_GOLD_DARK});
                color: #FFFFFF;
                border: 2px solid {THEME_GOLD_PALE};
                border-radius: 20px;
            }}
            QPushButton:hover {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #DFCFA8, stop:0.45 #B99C64, stop:1 #967C46);
                border: 2px solid #FFFFFF;
            }}
            QPushButton:pressed {{
                background: {THEME_GOLD_DARK};
            }}
        """)

        touch_layout = QVBoxLayout(self.btn_touch_start)
        touch_layout.setAlignment(Qt.AlignCenter)
        touch_layout.setContentsMargins(16, 8, 16, 8)
        touch_layout.setSpacing(3)

        # Dòng chính: Icon bàn tay + CHẠM ĐỂ BẮT ĐẦU (1 dòng trọn vẹn)
        h_main_row = QHBoxLayout()
        h_main_row.setAlignment(Qt.AlignCenter)
        h_main_row.setSpacing(8)

        self.lbl_touch_icon = QLabel()
        self.lbl_touch_icon.setPixmap(get_svg_pixmap("touch", 20, "#FFFFFF"))
        self.lbl_touch_icon.setStyleSheet("border: none; background: transparent;")
        h_main_row.addWidget(self.lbl_touch_icon)

        self.lbl_touch_txt = QLabel("CHẠM ĐỂ BẮT ĐẦU")
        self.lbl_touch_txt.setAlignment(Qt.AlignCenter)
        self.lbl_touch_txt.setStyleSheet(
            "font-family: 'Segoe UI', Arial, sans-serif; font-size: 18px; font-weight: 800; color: #FFFFFF; letter-spacing: 1.5px; border: none; background: transparent;"
        )
        h_main_row.addWidget(self.lbl_touch_txt)
        touch_layout.addLayout(h_main_row)

        # Dòng phụ hướng dẫn đặt bên dưới dòng chính
        self.lbl_touch_hint = QLabel("Chạm vào màn hình để chụp ảnh ngay")
        self.lbl_touch_hint.setAlignment(Qt.AlignCenter)
        self.lbl_touch_hint.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: #F8F5EE; letter-spacing: 0.5px; border: none; background: transparent;"
        )
        touch_layout.addWidget(self.lbl_touch_hint)

        self.btn_touch_start.clicked.connect(self._on_screen_tapped)
        v_center.addWidget(self.btn_touch_start, 0, Qt.AlignCenter)

        v_center.addSpacing(14)

        # Slogan thương hiệu phía dưới
        self.lbl_slogan = QLabel("✨ Trải nghiệm Photobooth lấy ảnh liền chuyên nghiệp • 1998 TEAM")
        self.lbl_slogan.setAlignment(Qt.AlignCenter)
        self.lbl_slogan.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: #55534D;
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        v_center.addWidget(self.lbl_slogan, 0, Qt.AlignCenter)

        main_layout.addWidget(self.center_container, 0, Qt.AlignCenter)

        # Layout co giãn phía dưới
        main_layout.addStretch(3)

        # 4. BOTTOM BAR: FOOTER RÕ RÀNG, ĐỘ TƯƠNG PHẢN CAO
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        self.lbl_footer_left = QLabel("1998 TEAM Photobooth v2.0")
        self.lbl_footer_left.setStyleSheet("color: #55534D; font-size: 12px; font-weight: 600; background: transparent;")
        bottom_bar.addWidget(self.lbl_footer_left)
        bottom_bar.addStretch()
        self.lbl_footer_right = QLabel("✨ Chạm bất kỳ đâu trên màn hình để bắt đầu chụp")
        self.lbl_footer_right.setStyleSheet(f"color: {THEME_TEXT_PRIMARY}; font-size: 13px; font-weight: 700; background: transparent;")
        bottom_bar.addWidget(self.lbl_footer_right)
        main_layout.addLayout(bottom_bar)

    def _update_logo_pixmap(self, target_height: int = 82):
        """Cập nhật kích thước logo sắc nét, bảo toàn tuyệt đối tỷ lệ gốc và không bị crop."""
        pix = get_brand_logo_tight_pixmap(height=target_height)
        if not pix.isNull():
            self.lbl_logo.setPixmap(pix)
            self.lbl_logo.setText("")
        else:
            self.lbl_logo.setText("1998 TEAM")
            self.lbl_logo.setStyleSheet(f"font-size: 32px; font-weight: 900; color: {THEME_GOLD}; border: none; background: transparent;")

    def resizeEvent(self, event):
        """Thích ứng tỷ lệ logo và khoảng cách co giãn theo độ phân giải màn hình."""
        super().resizeEvent(event)
        h = self.height()
        # Tính toán chiều cao logo cân đối: 74px ở 768p, 82px ở 900p, 88px ở 1080p
        target_logo_h = max(72, min(92, int(h * 0.088)))
        self._update_logo_pixmap(target_height=target_logo_h)

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
