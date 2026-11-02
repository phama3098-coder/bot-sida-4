"""
1998 TEAM — Photobooth Touch PIN Dialog
Màn hình xác thực mã PIN quản trị viên phong cách cảm ứng Studio:
- 4 chấm tròn bảo mật hiển thị trạng thái nhập trực quan.
- Bàn phím số cảm ứng lớn [1..9, 0, ⌫, Xóa] tối ưu cho màn hình Kiosk.
- Hỗ trợ đầy đủ phím số vật lý trên bàn phím máy tính.
- Hiệu ứng rung lắc (Shake Animation) và đổi màu đỏ khi nhập sai.
- Cơ chế khóa an toàn 30 giây sau 3 lần nhập sai liên tiếp.
"""

from typing import Optional
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QWidget
)

from vietphotobooth.core.auth import AdminAuthManager
from vietphotobooth.desktop.icons import COLOR_GOLD, COLOR_GOLD_LIGHT, COLOR_WHITE, COLOR_RED, COLOR_SLATE


class TouchPinDialog(QDialog):
    """
    Hộp thoại nhập mã PIN cảm ứng chuyên nghiệp chuẩn 1998 TEAM.
    """
    def __init__(
        self,
        auth_mgr: AdminAuthManager,
        title: str = "XÁC THỰC QUẢN TRỊ VIÊN",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.auth_mgr = auth_mgr
        self.entered_pin: str = ""
        self.failed_attempts: int = 0
        self.lockout_remaining: int = 0
        self._shake_anim: Optional[QPropertyAnimation] = None

        self.setWindowTitle("1998 TEAM — Khóa Quản Trị")
        self.setFixedSize(380, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border: 2px solid #D9DEE7;
                border-radius: 16px;
            }
        """)

        # Timer đếm ngược khóa 30 giây
        self._lockout_timer = QTimer(self)
        self._lockout_timer.setInterval(1000)
        self._lockout_timer.timeout.connect(self._on_lockout_tick)

        self._init_ui(title)

    def _init_ui(self, title_text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(16)

        # Header: Icon Khóa & Tiêu đề
        self.lbl_title = QLabel(f"🔒 <b>{title_text.upper()}</b>")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("color: #1E40AF; font-size: 15px; font-weight: 800; border: none;")
        layout.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel("Vui lòng nhập mã PIN quản trị (Mặc định: 1234)")
        self.lbl_subtitle.setAlignment(Qt.AlignCenter)
        self.lbl_subtitle.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
        layout.addWidget(self.lbl_subtitle)

        # 4 chấm chỉ báo PIN (PIN Indicator Dots)
        self.dots_container = QWidget()
        h_dots = QHBoxLayout(self.dots_container)
        h_dots.setSpacing(14)
        h_dots.setAlignment(Qt.AlignCenter)

        self.dot_labels = []
        for _ in range(4):
            dot = QLabel()
            dot.setFixedSize(18, 18)
            dot.setStyleSheet(
                "border: 2px solid #D9DEE7; background-color: #F1F5F9; border-radius: 9px;"
            )
            self.dot_labels.append(dot)
            h_dots.addWidget(dot)

        layout.addWidget(self.dots_container)

        # Nhãn thông báo lỗi / đếm ngược
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setFixedHeight(20)
        self.lbl_status.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold; border: none;")
        layout.addWidget(self.lbl_status)

        # Bàn phím số cảm ứng (Touch Keypad 3x4)
        self.keypad_widget = QWidget()
        grid = QGridLayout(self.keypad_widget)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        self.num_buttons = []
        buttons_spec = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("Xóa", 3, 0), ("0", 3, 1), ("⌫", 3, 2),
        ]

        for text, r, c in buttons_spec:
            btn = QPushButton(text)
            btn.setFixedHeight(54)
            btn.setCursor(Qt.PointingHandCursor)
            if text in ("Xóa", "⌫"):
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #F1F5F9;
                        border: 1.5px solid #D9DEE7;
                        color: #64748B;
                        font-size: 14px;
                        font-weight: bold;
                        border-radius: 10px;
                    }
                    QPushButton:hover {
                        background-color: #FFFFFF;
                        border-color: #94A3B8;
                        color: #303746;
                    }
                    QPushButton:pressed {
                        background-color: #E2E8F0;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #F8FAFC;
                        border: 1.5px solid #D9DEE7;
                        color: #303746;
                        font-size: 20px;
                        font-weight: 800;
                        border-radius: 10px;
                    }
                    QPushButton:hover {
                        background-color: #FFFFFF;
                        border-color: #D4AF37;
                        color: #1E40AF;
                    }
                    QPushButton:pressed {
                        background-color: #E2E8F0;
                    }
                """)
            btn.clicked.connect(lambda _, val=text: self._on_keypad_clicked(val))
            self.num_buttons.append(btn)
            grid.addWidget(btn, r, c)

        layout.addWidget(self.keypad_widget)

        # Footer: Nút Đóng / Hủy
        h_footer = QHBoxLayout()
        self.btn_cancel = QPushButton("Đóng (ESC)")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1.5px solid #D9DEE7;
                color: #64748B;
                font-size: 12px;
                font-weight: 600;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                border-color: #EF4444;
                color: #EF4444;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        h_footer.addStretch()
        h_footer.addWidget(self.btn_cancel)
        h_footer.addStretch()
        layout.addLayout(h_footer)

    def _update_dots(self, is_error: bool = False):
        """Cập nhật giao diện 4 chấm theo độ dài mã PIN đã nhập."""
        length = len(self.entered_pin)
        for i, dot in enumerate(self.dot_labels):
            if is_error:
                dot.setStyleSheet(
                    "border: 2px solid #EF4444; background-color: #FCA5A5; border-radius: 9px;"
                )
            elif i < length:
                dot.setStyleSheet(
                    "border: 2px solid #D4AF37; background-color: #F5DE88; border-radius: 9px;"
                )
            else:
                dot.setStyleSheet(
                    "border: 2px solid #D9DEE7; background-color: #F1F5F9; border-radius: 9px;"
                )

    def _on_keypad_clicked(self, val: str):
        if self.lockout_remaining > 0:
            return

        if val == "Xóa":
            self.entered_pin = ""
            self._update_dots()
            self.lbl_status.setText("")
        elif val == "⌫":
            if self.entered_pin:
                self.entered_pin = self.entered_pin[:-1]
                self._update_dots()
                self.lbl_status.setText("")
        else:
            if len(self.entered_pin) < 4:
                self.entered_pin += val
                self._update_dots()
                if len(self.entered_pin) == 4:
                    # Tự động thẩm định ngay khi đủ 4 chữ số
                    QTimer.singleShot(100, self._verify_pin)

    def _verify_pin(self):
        """Kiểm tra mã PIN với AdminAuthManager."""
        if self.auth_mgr.authenticate(self.entered_pin):
            self.lbl_status.setStyleSheet("color: #10B981; font-size: 11px; font-weight: bold;")
            self.lbl_status.setText("✓ Xác thực thành công!")
            for dot in self.dot_labels:
                dot.setStyleSheet(
                    "border: 2px solid #10B981; background-color: #34D399; border-radius: 9px;"
                )
            QTimer.singleShot(250, self.accept)
        else:
            self.failed_attempts += 1
            self.entered_pin = ""
            self._update_dots(is_error=True)
            self._trigger_shake_animation()

            if self.failed_attempts >= 3:
                self._start_lockout(30)
            else:
                rem = 3 - self.failed_attempts
                self.lbl_status.setText(f"Mã PIN không đúng! Còn {rem} lần thử.")
                QTimer.singleShot(800, lambda: self._update_dots(is_error=False))

    def _trigger_shake_animation(self):
        """Hiệu ứng rung lắc khi nhập sai mã PIN."""
        orig_pos = self.pos()
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(320)
        anim.setKeyValueAt(0.0, orig_pos)
        anim.setKeyValueAt(0.15, orig_pos + QPoint(-10, 0))
        anim.setKeyValueAt(0.3, orig_pos + QPoint(10, 0))
        anim.setKeyValueAt(0.45, orig_pos + QPoint(-8, 0))
        anim.setKeyValueAt(0.6, orig_pos + QPoint(8, 0))
        anim.setKeyValueAt(0.75, orig_pos + QPoint(-4, 0))
        anim.setKeyValueAt(0.9, orig_pos + QPoint(4, 0))
        anim.setKeyValueAt(1.0, orig_pos)
        anim.start()
        self._shake_anim = anim

    def _start_lockout(self, seconds: int = 30):
        """Kích hoạt trạng thái khóa 30 giây khi nhập sai quá số lần."""
        self.lockout_remaining = seconds
        self.lbl_status.setText(f"🔒 Nhập sai 3 lần. Tự khóa {self.lockout_remaining}s...")
        for btn in self.num_buttons:
            btn.setEnabled(False)
        self._lockout_timer.start(1000)

    def _on_lockout_tick(self):
        self.lockout_remaining -= 1
        if self.lockout_remaining > 0:
            self.lbl_status.setText(f"🔒 Nhập sai 3 lần. Tự khóa {self.lockout_remaining}s...")
        else:
            self._lockout_timer.stop()
            self.failed_attempts = 0
            self.lbl_status.setText("Đã mở khóa. Vui lòng nhập lại mã PIN.")
            self.lbl_status.setStyleSheet("color: #FBBF24; font-size: 11px;")
            self._update_dots(is_error=False)
            for btn in self.num_buttons:
                btn.setEnabled(True)

    def keyPressEvent(self, event):
        """Hỗ trợ phím số vật lý trên bàn phím."""
        if self.lockout_remaining > 0:
            super().keyPressEvent(event)
            return

        key = event.key()
        if Qt.Key_0 <= key <= Qt.Key_9:
            digit = str(key - Qt.Key_0)
            self._on_keypad_clicked(digit)
        elif key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._on_keypad_clicked("⌫")
        elif key == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
