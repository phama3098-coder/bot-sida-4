"""
VietPhotoBooth Event & Gallery Page
Manages events, session galleries, reprints, QR code regeneration, and ZIP export.
"""

import os
import shutil
import subprocess
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox,
    QInputDialog, QFileDialog, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage

from vietphotobooth.core.events import EventManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class EventsPage(QWidget):
    """Trang quản lý sự kiện và thư viện ảnh đã chụp."""

    def __init__(self, event_mgr: EventManager, print_mgr: PrintManager, token_mgr: TokenManager, parent=None):
        super().__init__(parent)
        self.event_mgr = event_mgr
        self.print_mgr = print_mgr
        self.token_mgr = token_mgr

        self._init_ui()
        self._load_events()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 1. KHU VỰC CHỌN VÀ TẠO MỚI SỰ KIỆN
        grp_event = QGroupBox("1. Quản Lý Sự Kiện (Events)")
        l_evt = QVBoxLayout(grp_event)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("<b>Sự Kiện Đang Kích Hoạt:</b>"))
        self.combo_events = QComboBox()
        self.combo_events.setMinimumWidth(260)
        self.combo_events.currentIndexChanged.connect(self._on_event_changed)
        r1.addWidget(self.combo_events, 1)

        btn_new_evt = QPushButton("+ Tạo Sự Kiện Mới")
        btn_new_evt.setObjectName("btn_success")
        btn_new_evt.clicked.connect(self._create_event)
        r1.addWidget(btn_new_evt)

        btn_open_folder = QPushButton("📂 Mở Thư Mục Ảnh")
        btn_open_folder.setObjectName("btn_secondary")
        btn_open_folder.clicked.connect(self._open_event_folder)
        r1.addWidget(btn_open_folder)

        btn_export_zip = QPushButton("📦 Xuất File ZIP")
        btn_export_zip.setObjectName("btn_secondary")
        btn_export_zip.clicked.connect(self._export_event_zip)
        r1.addWidget(btn_export_zip)

        l_evt.addLayout(r1)

        self.lbl_stats = QLabel("Thống kê: 0 lượt chụp • 0 bản in")
        self.lbl_stats.setStyleSheet("color: #38BDF8; font-weight: bold;")
        l_evt.addWidget(self.lbl_stats)

        layout.addWidget(grp_event)

        # 2. THƯ VIỆN CÁC LƯỢT CHỤP (SESSION GALLERY)
        grp_gallery = QGroupBox("2. Thư Viện Các Lượt Chụp Trong Sự Kiện")
        l_gal = QVBoxLayout(grp_gallery)

        self.table_sessions = QTableWidget(0, 4)
        self.table_sessions.setHorizontalHeaderLabels(["Mã Lượt Chụp", "Ảnh Thành Phẩm", "Thời Gian", "Thao Tác"])
        self.table_sessions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l_gal.addWidget(self.table_sessions)

        bar_gal = QHBoxLayout()
        btn_refresh = QPushButton("Làm Mới Danh Sách")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._refresh_gallery)
        bar_gal.addWidget(btn_refresh)

        btn_reprint = QPushButton("🖨️ In Lại Lượt Đang Chọn")
        btn_reprint.setObjectName("btn_secondary")
        btn_reprint.clicked.connect(self._reprint_selected)
        bar_gal.addWidget(btn_reprint)

        btn_show_qr = QPushButton("📱 Xem Lại Mã QR")
        btn_show_qr.setObjectName("btn_secondary")
        btn_show_qr.clicked.connect(self._show_qr_selected)
        bar_gal.addWidget(btn_show_qr)

        l_gal.addLayout(bar_gal)
        layout.addWidget(grp_gallery)

    def _load_events(self):
        self.combo_events.blockSignals(True)
        self.combo_events.clear()
        events = self.event_mgr.list_events()
        for e in events:
            ev_name = e["name"] if isinstance(e, dict) else str(e)
            self.combo_events.addItem(ev_name, ev_name)
        self.combo_events.blockSignals(False)

        active = self.event_mgr.get_active_event_name()
        idx = self.combo_events.findText(active)
        if idx >= 0:
            self.combo_events.setCurrentIndex(idx)
        self._refresh_gallery()

    def _on_event_changed(self, index: int):
        ev_name = self.combo_events.currentText()
        if ev_name:
            self.event_mgr.set_active_event(ev_name)
            self._refresh_gallery()

    def _create_event(self):
        name, ok = QInputDialog.getText(self, "Tạo Sự Kiện Mới", "Nhập tên sự kiện (ví dụ: DamCuoi_TuanLan, SinhNhat_MinhAnh):")
        if ok and name.strip():
            safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name.strip())
            self.event_mgr.create_event(safe_name)
            self.event_mgr.set_active_event(safe_name)
            self._load_events()

    def _open_event_folder(self):
        ev_name = self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(ev_name)
        folder = dirs["base"]
        if os.path.exists(folder):
            os.startfile(folder)

    def _export_event_zip(self):
        ev_name = self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(ev_name)
        save_path, _ = QFileDialog.getSaveFileName(self, "Xuất File ZIP Sự Kiện", f"{ev_name}_photos.zip", "ZIP Archives (*.zip)")
        if save_path:
            try:
                base_dir = dirs["base"]
                shutil.make_archive(save_path.replace(".zip", ""), "zip", base_dir)
                QMessageBox.information(self, "Thành Công", f"Đã xuất nén toàn bộ ảnh sự kiện vào:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xuất file ZIP: {e}")

    def _refresh_gallery(self):
        ev_name = self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(ev_name)
        final_dir = dirs["final"]

        self.table_sessions.setRowCount(0)
        if not os.path.exists(final_dir):
            self.lbl_stats.setText("Thống kê: 0 lượt chụp")
            return

        files = [f for f in os.listdir(final_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        self.lbl_stats.setText(f"Thống kê: {len(files)} lượt chụp hoàn tất")

        for f in reversed(files):
            row = self.table_sessions.rowCount()
            self.table_sessions.insertRow(row)

            sess_id = f.replace("_final.jpg", "").replace("_final.png", "")
            fpath = os.path.join(final_dir, f)
            mtime = os.path.getmtime(fpath)
            from datetime import datetime
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")

            self.table_sessions.setItem(row, 0, QTableWidgetItem(sess_id))
            self.table_sessions.setItem(row, 1, QTableWidgetItem(f))
            self.table_sessions.setItem(row, 2, QTableWidgetItem(time_str))
            self.table_sessions.setItem(row, 3, QTableWidgetItem("Sẵn sàng in / chia sẻ"))

    def _reprint_selected(self):
        row = self.table_sessions.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Thông Báo", "Vui lòng chọn một lượt chụp trong bảng để in lại.")
            return

        fname = self.table_sessions.item(row, 1).text()
        ev_name = self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(ev_name)
        fpath = os.path.join(dirs["final"], fname)

        if os.path.exists(fpath):
            self.print_mgr.print_image(fpath, copies=1)
            QMessageBox.information(self, "In Lại", f"Đã gửi lệnh in lại lượt: {fname}")

    def _show_qr_selected(self):
        row = self.table_sessions.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Thông Báo", "Vui lòng chọn một lượt chụp trong bảng để xem mã QR.")
            return

        sess_id = self.table_sessions.item(row, 0).text()
        ev_name = self.event_mgr.get_active_event_name()
        token_info = self.token_mgr.create_token(ev_name, sess_id)

        qr_img = self.token_mgr.generate_qr_code(token_info.token)
        lan_url = self.token_mgr.get_sharing_url(token_info.token)

        dlg = QDialog(self)
        dlg.setWindowTitle("Quét Mã QR Lượt Chụp Này")
        dlg.setFixedSize(400, 480)
        l = QVBoxLayout(dlg)

        title = QLabel(f"Lượt Chụp: {sess_id}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38BDF8;")
        l.addWidget(title)

        lbl_qr = QLabel()
        lbl_qr.setAlignment(Qt.AlignCenter)
        rgb = qr_img.convert("RGB")
        w, h = rgb.size
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
        lbl_qr.setPixmap(QPixmap.fromImage(qimg).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        l.addWidget(lbl_qr)

        lbl_url = QLabel(lan_url)
        lbl_url.setAlignment(Qt.AlignCenter)
        lbl_url.setStyleSheet("color: #94A3B8; font-size: 13px;")
        l.addWidget(lbl_url)

        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("btn_secondary")
        btn_close.clicked.connect(dlg.accept)
        l.addWidget(btn_close)

        dlg.exec()
