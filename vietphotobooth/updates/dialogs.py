"""
1998 TEAM — Photobooth Update Dialogs
Elegant luxury Navy & Champagne Gold dialogs for update notification, release notes viewing,
and secure download progress.
"""

import os
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QProgressBar, QMessageBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont

from vietphotobooth.version import __version__, __build__, get_version_string
from vietphotobooth.updates.manifest import UpdateManifest
from vietphotobooth.updates.updater import UpdateManager

LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Branding", "logo_1998_studio.png"))

DIALOG_STYLE = """
QDialog {
    background-color: #070A12;
    border: 2px solid #D4AF37;
    border-radius: 12px;
}
QLabel {
    color: #F8FAFC;
    font-size: 13px;
}
QTextEdit {
    background-color: #0E1626;
    color: #E2E8F0;
    border: 1px solid #1E2D4A;
    border-radius: 8px;
    padding: 8px;
    font-size: 13px;
    line-height: 1.4;
}
QPushButton {
    border-radius: 8px;
    font-weight: bold;
    padding: 8px 16px;
    min-height: 38px;
}
QPushButton#btn_primary {
    background-color: #D4AF37;
    color: #070A12;
    border: none;
}
QPushButton#btn_primary:hover {
    background-color: #E5C158;
}
QPushButton#btn_secondary {
    background-color: #16223B;
    color: #E2E8F0;
    border: 1px solid #28395E;
}
QPushButton#btn_secondary:hover {
    background-color: #1E2D4A;
    border: 1px solid #D4AF37;
    color: #D4AF37;
}
QProgressBar {
    background-color: #0E1626;
    border: 1px solid #1E2D4A;
    border-radius: 6px;
    text-align: center;
    color: #F8FAFC;
    font-weight: bold;
    height: 22px;
}
QProgressBar::chunk {
    background-color: #D4AF37;
    border-radius: 5px;
}
"""

class UpdateNotificationDialog(QDialog):
    """Hộp thoại thông báo thanh lịch khi có bản phát hành mới của 1998 TEAM Photobooth."""
    update_requested = Signal(object)  # manifest

    def __init__(self, manifest: UpdateManifest, update_mgr: UpdateManager, parent=None):
        super().__init__(parent)
        self.manifest = manifest
        self.update_mgr = update_mgr

        self.setWindowTitle("Thông Báo Cập Nhật — 1998 TEAM Photobooth")
        self.setFixedSize(540, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(DIALOG_STYLE)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header: Logo & Tiêu đề
        h_layout = QHBoxLayout()
        if os.path.exists(LOGO_PATH):
            lbl_logo = QLabel()
            pix = QPixmap(LOGO_PATH)
            lbl_logo.setPixmap(pix.scaledToHeight(48, Qt.SmoothTransformation))
            h_layout.addWidget(lbl_logo)

        v_head = QVBoxLayout()
        lbl_title = QLabel("<b>Đã Có Phiên Bản Mới!</b>")
        lbl_title.setStyleSheet("color: #D4AF37; font-size: 18px;")
        lbl_sub = QLabel("1998 TEAM — Photobooth sẵn sàng nâng cấp")
        lbl_sub.setStyleSheet("color: #94A3B8; font-size: 12px;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_sub)
        h_layout.addLayout(v_head)
        h_layout.addStretch()
        layout.addLayout(h_layout)

        # Pill so sánh phiên bản
        pill_frame = QFrame()
        pill_frame.setStyleSheet("background-color: #0B1322; border: 1px solid #1E2D4A; border-radius: 8px; padding: 6px;")
        pill_layout = QHBoxLayout(pill_frame)

        cur_text = f"Hiện tại: <b>v{get_version_string()}</b>"
        new_text = f"Bản mới: <b style='color:#10B981;'>v{self.manifest.version} (Build {self.manifest.build})</b>"

        lbl_cur = QLabel(cur_text)
        lbl_new = QLabel(new_text)
        pill_layout.addWidget(lbl_cur)
        pill_layout.addStretch()
        pill_layout.addWidget(lbl_new)
        layout.addWidget(pill_frame)

        if self.manifest.release_date:
            lbl_date = QLabel(f"📅 Ngày phát hành: <b>{self.manifest.release_date}</b>")
            lbl_date.setStyleSheet("color: #CBD5E1; font-size: 12px;")
            layout.addWidget(lbl_date)

        # Khu vực nội dung thay đổi (Release Notes)
        layout.addWidget(QLabel("<b>Nội dung cập nhật & cải tiến:</b>"))
        self.txt_notes = QTextEdit()
        self.txt_notes.setReadOnly(True)

        if self.manifest.release_notes:
            formatted_notes = "\n".join(f"• {note}" for note in self.manifest.release_notes)
        else:
            formatted_notes = "• Bản phát hành bao gồm các cải tiến hiệu năng và sửa lỗi."

        self.txt_notes.setPlainText(formatted_notes)
        layout.addWidget(self.txt_notes)

        # Các nút thao tác: Cập nhật ngay, Xem chi tiết, Để sau
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_later = QPushButton("⏱️ Để Sau")
        self.btn_later.setObjectName("btn_secondary")
        self.btn_later.clicked.connect(self._on_later_clicked)
        btn_bar.addWidget(self.btn_later)

        btn_bar.addStretch()

        self.btn_update = QPushButton("🚀 Cập Nhật Ngay")
        self.btn_update.setObjectName("btn_primary")
        self.btn_update.clicked.connect(self._on_update_clicked)
        btn_bar.addWidget(self.btn_update)

        layout.addLayout(btn_bar)

    def _on_later_clicked(self):
        self.update_mgr.dismiss_version_for_session(self.manifest.version)
        self.reject()

    def _on_update_clicked(self):
        self.accept()
        self.update_requested.emit(self.manifest)


class UpdateProgressDialog(QDialog):
    """Hộp thoại hiển thị tiến trình tải gói cài đặt và xác thực SHA-256."""
    def __init__(self, manifest: UpdateManifest, update_mgr: UpdateManager, parent=None):
        super().__init__(parent)
        self.manifest = manifest
        self.update_mgr = update_mgr
        self.installer_path: Optional[str] = None

        self.setWindowTitle("Đang Tải Bản Cập Nhật — 1998 TEAM Photobooth")
        self.setFixedSize(480, 260)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(DIALOG_STYLE)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        self.lbl_status = QLabel(f"Đang chuẩn bị tải phiên bản v{self.manifest.version}...")
        self.lbl_status.setStyleSheet("color: #D4AF37; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.lbl_details = QLabel("0 MB / 0 MB (0%)")
        self.lbl_details.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self.lbl_details)

        self.lbl_verify = QLabel("🛡️ Tự động xác thực tính toàn vẹn SHA-256 trước khi cài đặt.")
        self.lbl_verify.setStyleSheet("color: #64748B; font-style: italic; font-size: 11px;")
        layout.addWidget(self.lbl_verify)

        layout.addStretch()

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.btn_action = QPushButton("Hủy Tải")
        self.btn_action.setObjectName("btn_secondary")
        self.btn_action.clicked.connect(self._on_action_clicked)
        btn_bar.addWidget(self.btn_action)

        layout.addLayout(btn_bar)

    def _connect_signals(self):
        self.update_mgr.download_progress.connect(self._on_progress)
        self.update_mgr.download_completed.connect(self._on_finished)

    def _on_progress(self, percent: int, downloaded: int, total: int):
        self.progress_bar.setValue(percent)
        dl_mb = downloaded / (1024 * 1024)
        tot_mb = total / (1024 * 1024)
        self.lbl_status.setText(f"Đang tải bản cập nhật: {percent}%...")
        self.lbl_details.setText(f"{dl_mb:.1f} MB / {tot_mb:.1f} MB ({percent}%)")

    def _on_finished(self, success: bool, installer_path: str, err_msg: str):
        if success:
            self.installer_path = installer_path
            self.progress_bar.setValue(100)
            self.lbl_status.setText("✅ Đã tải và xác thực SHA-256 an toàn!")
            self.lbl_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 14px;")
            self.lbl_details.setText("Gói cài đặt sẵn sàng. Dữ liệu ảnh và cấu hình sẽ được giữ nguyên.")
            self.btn_action.setText("🚀 Cài Đặt Ngay")
            self.btn_action.setObjectName("btn_primary")
            self.btn_action.setStyle(self.btn_action.style())  # Refresh stylesheet
        else:
            self.lbl_status.setText("❌ Tải bản cập nhật thất bại")
            self.lbl_status.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 14px;")
            self.lbl_details.setText(err_msg or "Vui lòng kiểm tra lại kết nối mạng hoặc thử lại sau.")
            self.btn_action.setText("Đóng")

    def _on_action_clicked(self):
        if self.installer_path:
            ret = QMessageBox.question(
                self,
                "Xác Nhận Cài Đặt",
                "Ứng dụng sẽ tự động sao lưu cấu hình, khởi động bộ cài đặt và đóng phiên làm việc hiện tại.\n\nBạn có muốn tiếp tục không?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret == QMessageBox.Yes:
                self.update_mgr.apply_update_and_restart(self.installer_path)
        else:
            if self.update_mgr._download_worker and self.update_mgr._download_worker.isRunning():
                self.update_mgr._download_worker.stop()
            self.reject()
