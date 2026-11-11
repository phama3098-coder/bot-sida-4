"""
1998 TEAM Photobooth — Minimal Luxury Studio Card & Banner Widgets
Component library for Minimal Luxury V1.1 Design System.
Provides SurfaceCard, SecondaryCard, StatCardMetric, and AlertBannerWidget.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor

from vietphotobooth.desktop.styles import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_SECONDARY,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_BORDER,
    COLOR_CHAMPAGNE, COLOR_CHAMPAGNE_LIGHT, COLOR_PALE_GOLD,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    FONT_FAMILY_PRIMARY
)


class SurfaceCard(QFrame):
    """
    Thẻ bề mặt chính (Surface Card) trong hệ thống Minimal Luxury.
    Nền trắng tinh khiết (#FFFFFF), viền siêu mảnh (#E8E6E0), bo góc 12px.
    Bật WA_StyledBackground và StyledPanel để ngăn ngừa lỗi render trên Windows.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("surface_card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame#surface_card {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)


class SecondaryCard(QFrame):
    """
    Thẻ bề mặt phụ (Secondary Surface Card) trong hệ thống Minimal Luxury.
    Nền xám ấm nhạt (#F1F0EC), viền siêu mảnh (#E8E6E0), bo góc 10px.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("secondary_card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame#secondary_card {{
                background-color: {COLOR_SURFACE_SECONDARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)


class StatCardMetric(SurfaceCard):
    """
    Thẻ thống kê số liệu cao cấp (KPI Stat Card) cho Buồng Lái Vận Hành.
    Hỗ trợ phân định minh bạch 3 trạng thái:
      - 'LIVE': Dữ liệu thật từ thiết bị/sự kiện (Huy hiệu xanh ngọc bích).
      - 'N/A': Thiết bị chưa kết nối hoặc dữ liệu chưa sẵn sàng (Huy hiệu xám đá).
      - 'DEMO': Dữ liệu mẫu kiểm thử/mô phỏng (Huy hiệu vàng hổ phách).
    """
    def __init__(
        self,
        icon_char: str,
        accent_color: str,
        title: str,
        value: str,
        subtitle: str,
        badge_mode: str = "LIVE",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.accent_color = accent_color
        self._badge_mode = badge_mode.upper()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        # 1. Hàng tiêu đề trên cùng: Icon badge, Tiêu đề, và Huy hiệu trạng thái
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.lbl_icon = QLabel(icon_char)
        self.lbl_icon.setFixedSize(30, 30)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setStyleSheet(f"""
            QLabel {{
                background-color: {COLOR_SURFACE_SECONDARY};
                color: {accent_color};
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
            }}
        """)
        top_row.addWidget(self.lbl_icon)

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
        """)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch()

        self.lbl_badge = QLabel()
        self.lbl_badge.setFixedHeight(20)
        self.lbl_badge.setAlignment(Qt.AlignCenter)
        self._apply_badge_style(self._badge_mode)
        top_row.addWidget(self.lbl_badge)

        layout.addLayout(top_row)

        # 2. Giá trị số liệu chính (Font lớn 22px, Đậm nét)
        self.lbl_val = QLabel(value)
        self.lbl_val.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                font-size: 22px;
                font-weight: 800;
                letter-spacing: -0.5px;
            }}
        """)
        self.lbl_val.setWordWrap(True)
        layout.addWidget(self.lbl_val)

        # 3. Chân thẻ mô tả (11px, màu phụ)
        self.lbl_sub = QLabel(subtitle)
        self.lbl_sub.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_SECONDARY};
                font-size: 11px;
            }}
        """)
        self.lbl_sub.setWordWrap(True)
        layout.addWidget(self.lbl_sub)

    def _apply_badge_style(self, mode: str) -> None:
        """Thiết lập màu sắc và nội dung huy hiệu theo chuẩn phân định dữ liệu (LIVE, MANUAL, DEMO, ERROR, N/A)."""
        mode_upper = mode.upper()
        if mode_upper == "LIVE":
            self.lbl_badge.setText("● LIVE")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #EBF4EF;
                    color: #2E5B42;
                    font-size: 10px;
                    font-weight: 800;
                    padding: 2px 7px;
                    border-radius: 4px;
                    border: 1px solid #A3D9B8;
                }
            """)
        elif mode_upper == "MANUAL":
            self.lbl_badge.setText("● MANUAL")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #EDF2F7;
                    color: #2D3748;
                    font-size: 10px;
                    font-weight: 800;
                    padding: 2px 7px;
                    border-radius: 4px;
                    border: 1px solid #CBD5E0;
                }
            """)
        elif mode_upper == "DEMO":
            self.lbl_badge.setText("● DEMO")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #FEF7ED;
                    color: #8E5A14;
                    font-size: 10px;
                    font-weight: 800;
                    padding: 2px 7px;
                    border-radius: 4px;
                    border: 1px solid #F9DEB5;
                }
            """)
        elif mode_upper == "ERROR":
            self.lbl_badge.setText("● ERROR")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #FDF2F2;
                    color: #AC3833;
                    font-size: 10px;
                    font-weight: 800;
                    padding: 2px 7px;
                    border-radius: 4px;
                    border: 1px solid #F5C2C0;
                }
            """)
        else:  # N/A hoặc DISCONNECTED
            self.lbl_badge.setText("● N/A")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #F1F0EC;
                    color: #56554F;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 2px 7px;
                    border-radius: 4px;
                    border: 1px solid #CBD5E0;
                }
            """)

    def set_value(self, val: str) -> None:
        """Cập nhật giá trị hiển thị."""
        self.lbl_val.setText(str(val))

    def set_subtitle(self, sub: str) -> None:
        """Cập nhật nội dung mô tả phụ."""
        self.lbl_sub.setText(str(sub))

    def set_badge_mode(self, mode: str) -> None:
        """Cập nhật cờ phân định dữ liệu (LIVE, DEMO, N/A)."""
        self._badge_mode = mode.upper()
        self._apply_badge_style(self._badge_mode)

    @property
    def badge_mode(self) -> str:
        return self._badge_mode


class AlertBannerWidget(QFrame):
    """
    Thanh cảnh báo thông minh tự động reflow (Alert Banner) trong hệ thống Minimal Luxury.
    Hỗ trợ 4 phân loại: 'error', 'warning', 'success', 'info'.
    Tích hợp nút thao tác nhanh (Action Button) và nút đóng (Dismiss).
    """
    action_clicked = Signal()
    dismiss_clicked = Signal()

    TYPE_CONFIG = {
        "error": {
            "bg": "#FDF2F2",
            "border": "#F5C2C0",
            "text": "#AC3833",
            "icon": "⚠️",
            "btn_bg": "#AC3833",
            "btn_text": "#FFFFFF"
        },
        "warning": {
            "bg": "#FEF7ED",
            "border": "#F9DEB5",
            "text": "#8E5A14",
            "icon": "⚡",
            "btn_bg": "#8E5A14",
            "btn_text": "#FFFFFF"
        },
        "success": {
            "bg": "#F0F7F4",
            "border": "#BCE0CE",
            "text": "#336349",
            "icon": "✓",
            "btn_bg": "#336349",
            "btn_text": "#FFFFFF"
        },
        "info": {
            "bg": "#F4F6F8",
            "border": "#D5DCE2",
            "text": "#2C5282",
            "icon": "ℹ️",
            "btn_bg": "#2C5282",
            "btn_text": "#FFFFFF"
        }
    }

    def __init__(
        self,
        banner_type: str = "warning",
        title: str = "",
        message: str = "",
        action_text: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setObjectName("alert_banner")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._banner_type = banner_type.lower()
        if self._banner_type not in self.TYPE_CONFIG:
            self._banner_type = "warning"

        self._init_ui(title, message, action_text)
        self._apply_theme()

    def _init_ui(self, title: str, message: str, action_text: Optional[str]) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # Biểu tượng cảnh báo
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(24, 24)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setStyleSheet("background: transparent; font-size: 15px;")
        layout.addWidget(self.lbl_icon, 0, Qt.AlignVCenter)

        # Khối văn bản: Tiêu đề + Nội dung (tự động wrap khi thu nhỏ cửa sổ)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("background: transparent; font-weight: 700; font-size: 12px;")
        text_col.addWidget(self.lbl_title)

        self.lbl_message = QLabel(message)
        self.lbl_message.setStyleSheet("background: transparent; font-size: 11px;")
        self.lbl_message.setWordWrap(True)
        self.lbl_message.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_col.addWidget(self.lbl_message)

        layout.addLayout(text_col, 1)

        # Nút thao tác nhanh (nếu có)
        self.btn_action = QPushButton(action_text or "")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.setFixedHeight(28)
        self.btn_action.clicked.connect(self.action_clicked.emit)
        if not action_text:
            self.btn_action.hide()
        layout.addWidget(self.btn_action, 0, Qt.AlignVCenter)

        # Nút đóng cảnh báo
        self.btn_dismiss = QPushButton("✕")
        self.btn_dismiss.setCursor(Qt.PointingHandCursor)
        self.btn_dismiss.setFixedSize(22, 22)
        self.btn_dismiss.clicked.connect(self.dismiss_clicked.emit)
        self.btn_dismiss.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLOR_TEXT_SECONDARY};
                font-weight: bold;
                font-size: 11px;
                border-radius: 11px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SURFACE_SECONDARY};
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(self.btn_dismiss, 0, Qt.AlignVCenter)

    def _apply_theme(self) -> None:
        cfg = self.TYPE_CONFIG.get(self._banner_type, self.TYPE_CONFIG["warning"])
        self.lbl_icon.setText(cfg["icon"])
        self.lbl_title.setStyleSheet(f"background: transparent; font-weight: 700; font-size: 12px; color: {cfg['text']};")
        self.lbl_message.setStyleSheet(f"background: transparent; font-size: 11px; color: {cfg['text']};")

        self.setStyleSheet(f"""
            QFrame#alert_banner {{
                background-color: {cfg['bg']};
                border: 1px solid {cfg['border']};
                border-radius: 8px;
            }}
        """)

        self.btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: {cfg['btn_bg']};
                color: {cfg['btn_text']};
                font-weight: 700;
                font-size: 11px;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)

    def set_message(self, title: str, message: str) -> None:
        """Cập nhật tiêu đề và nội dung cảnh báo."""
        self.lbl_title.setText(title)
        self.lbl_message.setText(message)

    def set_banner_type(self, banner_type: str) -> None:
        """Thay đổi loại cảnh báo ('error', 'warning', 'success', 'info')."""
        b_type = banner_type.lower()
        if b_type in self.TYPE_CONFIG:
            self._banner_type = b_type
            self._apply_theme()

    def set_action_text(self, action_text: Optional[str]) -> None:
        """Cập nhật nhãn nút hành động hoặc ẩn nếu None."""
        if action_text:
            self.btn_action.setText(action_text)
            self.btn_action.show()
        else:
            self.btn_action.hide()

    @property
    def banner_type(self) -> str:
        return self._banner_type
