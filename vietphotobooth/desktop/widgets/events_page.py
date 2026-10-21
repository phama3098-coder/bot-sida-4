"""
VietPhotoBooth Event & Gallery Page
Manages events, session galleries, reprints, Google Drive cloud sync status,
dual QR code generation (Cloud & LAN), and ZIP export.
"""

import os
import shutil
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox,
    QInputDialog, QFileDialog, QDialog, QScrollArea, QFrame, QTabWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
import qrcode

from vietphotobooth.core.events import EventManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.cloud import SyncManager, SyncStatus
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class EventsPage(QWidget):
    """Trang quản lý sự kiện và thư viện ảnh đã chụp với đồng bộ Google Drive."""

    def __init__(
        self,
        event_mgr: EventManager,
        print_mgr: PrintManager,
        token_mgr: TokenManager,
        sync_mgr: Optional[SyncManager] = None,
        auth_mgr=None,
        parent=None
    ):
        super().__init__(parent)
        self.event_mgr = event_mgr
        self.print_mgr = print_mgr
        self.token_mgr = token_mgr
        self.sync_mgr = sync_mgr
        self.auth_mgr = auth_mgr

        self._init_ui()
        self._load_events()

        # Kết nối tín hiệu đồng bộ để cập nhật bảng thư viện
        if self.sync_mgr:
            self.sync_mgr.worker.sync_completed.connect(lambda p, l: self._refresh_gallery())
            self.sync_mgr.worker.sync_failed.connect(lambda p, e: self._refresh_gallery())

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

        # 1. KHU VỰC CHỌN VÀ TẠO MỚI SỰ KIỆN
        grp_event = QGroupBox("1. Quản Lý Sự Kiện (Events)")
        l_evt = QVBoxLayout(grp_event)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("<b>Sự Kiện Đang Kích Hoạt:</b>"))
        self.combo_events = QComboBox()
        self.combo_events.setMinimumWidth(220)
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

        btn_sync_all = QPushButton("☁️ Đồng Bộ Lên Drive")
        btn_sync_all.setObjectName("btn_champagne")
        btn_sync_all.clicked.connect(self._sync_all_to_gdrive)
        r1.addWidget(btn_sync_all)

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

        self.table_sessions = QTableWidget(0, 5)
        self.table_sessions.setHorizontalHeaderLabels([
            "Mã Lượt Chụp", "Ảnh Thành Phẩm", "Thời Gian", "Đồng Bộ Google Drive", "Thao Tác"
        ])
        self.table_sessions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_sessions.horizontalHeader().setMinimumSectionSize(30)
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

        btn_show_qr = QPushButton("📱 Xem Lại Mã QR (Online / LAN)")
        btn_show_qr.setObjectName("btn_secondary")
        btn_show_qr.clicked.connect(self._show_qr_selected)
        bar_gal.addWidget(btn_show_qr)

        l_gal.addLayout(bar_gal)
        layout.addWidget(grp_gallery)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _load_events(self):
        self.combo_events.blockSignals(True)
        self.combo_events.clear()
        events = self.event_mgr.list_events()
        for e in events:
            ev_name = e["name"] if isinstance(e, dict) else str(e)
            self.combo_events.addItem(ev_name, ev_name)

        active = self.event_mgr.get_active_event_name()
        idx = self.combo_events.findText(active)
        if idx >= 0:
            self.combo_events.setCurrentIndex(idx)
        self.combo_events.blockSignals(False)
        self._refresh_gallery()

    def _on_event_changed(self, index: int):
        ev_name = self.combo_events.currentText()
        if not ev_name:
            return
        if ev_name == self.event_mgr.get_active_event_name():
            return
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Chuyển Đổi Sự Kiện"):
                self.combo_events.blockSignals(True)
                active = self.event_mgr.get_active_event_name()
                idx = self.combo_events.findText(active)
                if idx >= 0:
                    self.combo_events.setCurrentIndex(idx)
                self.combo_events.blockSignals(False)
                return
        self.event_mgr.set_active_event(ev_name)
        self._refresh_gallery()

    def _create_event(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Tạo Sự Kiện Mới"):
                return
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

    def _sync_all_to_gdrive(self):
        """Đưa toàn bộ ảnh trong sự kiện vào hàng đợi đồng bộ Google Drive."""
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Đồng Bộ Toàn Bộ Ảnh"):
                return
        if not self.sync_mgr or not self.sync_mgr.is_ready():
            QMessageBox.warning(
                self,
                "Google Drive Chưa Kết Nối",
                "Google Drive chưa được cấu hình hoặc chưa đăng nhập.\nVui lòng vào tab 'Cài Đặt' để kết nối hoặc bật chế độ Giả Lập."
            )
            return

        ev_name = self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(ev_name)
        final_dir = dirs["final"]

        count = self.sync_mgr.sync_all_event_photos(ev_name, final_dir)
        if count > 0:
            QMessageBox.information(
                self,
                "Bắt Đầu Đồng Bộ",
                f"Đã đưa {count} ảnh thành phẩm vào hàng đợi đồng bộ ngầm Google Drive!\nTiến trình đang chạy nền không làm gián đoạn chụp ảnh."
            )
        else:
            QMessageBox.information(
                self,
                "Đồng Bộ Hoàn Tất",
                "Tất cả ảnh trong sự kiện này đã được tải lên Google Drive từ trước!"
            )
        self._refresh_gallery()

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

            # Kiểm tra trạng thái Google Drive
            cloud_status_text = "📱 Chỉ lưu máy"
            cloud_color = "#94A3B8"
            if self.sync_mgr:
                info = self.sync_mgr.get_file_info(fpath)
                if info:
                    st = info.get("status")
                    if st == SyncStatus.SYNCED:
                        cloud_status_text = "☁️ Đã tải lên Google Drive"
                        cloud_color = "#10B981"
                    elif st == SyncStatus.UPLOADING:
                        cloud_status_text = "⏳ Đang tải lên..."
                        cloud_color = "#F59E0B"
                    elif st == SyncStatus.FAILED:
                        cloud_status_text = "⚠️ Tải thất bại (Thử lại)"
                        cloud_color = "#EF4444"
                elif self.sync_mgr.is_ready():
                    cloud_status_text = "⏳ Chờ đưa vào hàng đợi"
                    cloud_color = "#38BDF8"

            self.table_sessions.setItem(row, 0, QTableWidgetItem(sess_id))
            self.table_sessions.setItem(row, 1, QTableWidgetItem(f))
            self.table_sessions.setItem(row, 2, QTableWidgetItem(time_str))

            item_cloud = QTableWidgetItem(cloud_status_text)
            item_cloud.setForeground(Qt.GlobalColor.white if cloud_color == "#10B981" else Qt.GlobalColor.lightGray)
            self.table_sessions.setItem(row, 3, item_cloud)

            self.table_sessions.setItem(row, 4, QTableWidgetItem("Sẵn sàng in / chia sẻ"))

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

        fname = self.table_sessions.item(row, 1).text()
        sess_id = self.table_sessions.item(row, 0).text()
        ev_name = self.event_mgr.get_active_event_name()
        dirs = self.event_mgr.get_event_dirs(ev_name)
        fpath = os.path.join(dirs["final"], fname)

        # Lấy link LAN
        token_info = self.token_mgr.create_token(ev_name, sess_id)
        lan_url = self.token_mgr.get_sharing_url(token_info.token)

        # Lấy link Google Drive nếu có
        gdrive_url = None
        if self.sync_mgr:
            info = self.sync_mgr.get_file_info(fpath)
            if info and info.get("status") == SyncStatus.SYNCED:
                gdrive_url = info.get("web_link")

        # Dialog hiển thị mã QR thông minh 2 chế độ
        dlg = QDialog(self)
        dlg.setWindowTitle("Quét Mã QR Nhận Ảnh")
        dlg.setFixedSize(460, 560)
        layout = QVBoxLayout(dlg)

        title = QLabel(f"Lượt Chụp: <b>{sess_id}</b>")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #D4AF37;")
        layout.addWidget(title)

        tabs_qr = QTabWidget()

        # Tab 1: Google Drive (Online 4G/Internet)
        tab_cloud = QWidget()
        l_cloud = QVBoxLayout(tab_cloud)
        if gdrive_url:
            qr_cloud_img = qrcode.make(gdrive_url)
            lbl_qr_c = QLabel()
            lbl_qr_c.setAlignment(Qt.AlignCenter)
            rgb = qr_cloud_img.convert("RGB")
            w, h = rgb.size
            data = rgb.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
            lbl_qr_c.setPixmap(QPixmap.fromImage(qimg).scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            l_cloud.addWidget(lbl_qr_c)

            lbl_c_desc = QLabel("Quét để xem và tải ảnh gốc trực tiếp qua mạng 4G/Internet.")
            lbl_c_desc.setAlignment(Qt.AlignCenter)
            lbl_c_desc.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
            l_cloud.addWidget(lbl_c_desc)

            lbl_c_link = QLabel(f"<a href='{gdrive_url}' style='color:#38BDF8;'>Mở liên kết Drive</a>")
            lbl_c_link.setOpenExternalLinks(True)
            lbl_c_link.setAlignment(Qt.AlignCenter)
            l_cloud.addWidget(lbl_c_link)
        else:
            lbl_notice = QLabel("Ảnh này chưa tải lên Google Drive.\nBạn có thể bấm 'Đồng Bộ Lên Drive' để tải lên ngay.")
            lbl_notice.setAlignment(Qt.AlignCenter)
            lbl_notice.setStyleSheet("color: #94A3B8; font-size: 13px; line-height: 1.5;")
            l_cloud.addWidget(lbl_notice)

            btn_sync_now = QPushButton("☁️ Tải Lên Google Drive Ngay")
            btn_sync_now.setObjectName("btn_champagne")
            btn_sync_now.clicked.connect(lambda: self._trigger_single_sync(fpath, ev_name, dlg))
            l_cloud.addWidget(btn_sync_now)

        tabs_qr.addTab(tab_cloud, "☁️ Google Drive (Online)")

        # Tab 2: Mạng LAN WiFi
        tab_lan = QWidget()
        l_lan = QVBoxLayout(tab_lan)

        qr_lan_img = qrcode.make(lan_url)
        lbl_qr_l = QLabel()
        lbl_qr_l.setAlignment(Qt.AlignCenter)
        rgb_l = qr_lan_img.convert("RGB")
        w_l, h_l = rgb_l.size
        data_l = rgb_l.tobytes("raw", "RGB")
        qimg_l = QImage(data_l, w_l, h_l, 3 * w_l, QImage.Format_RGB888)
        lbl_qr_l.setPixmap(QPixmap.fromImage(qimg_l).scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        l_lan.addWidget(lbl_qr_l)

        lbl_l_desc = QLabel("Khách kết nối cùng mạng WiFi với quầy Photobooth để tải ảnh.")
        lbl_l_desc.setAlignment(Qt.AlignCenter)
        lbl_l_desc.setStyleSheet("color: #94A3B8; font-size: 12px;")
        l_lan.addWidget(lbl_l_desc)

        lbl_l_link = QLabel(lan_url)
        lbl_l_link.setAlignment(Qt.AlignCenter)
        lbl_l_link.setStyleSheet("color: #38BDF8; font-size: 11px;")
        l_lan.addWidget(lbl_l_link)

        tabs_qr.addTab(tab_lan, "📱 Mạng LAN (WiFi Nội Bộ)")
        layout.addWidget(tabs_qr)

        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("btn_secondary")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        dlg.exec()

    def _trigger_single_sync(self, fpath: str, ev_name: str, parent_dlg: QDialog):
        if self.sync_mgr and self.sync_mgr.is_ready():
            self.sync_mgr.enqueue(fpath, ev_name)
            parent_dlg.accept()
            QMessageBox.information(self, "Đã Đưa Vào Hàng Đợi", "Đã đưa ảnh vào hàng đợi đồng bộ Google Drive.")
            self._refresh_gallery()
        else:
            QMessageBox.warning(self, "Chưa Sẵn Sàng", "Google Drive chưa sẵn sàng. Vui lòng vào Cài Đặt để kết nối.")
