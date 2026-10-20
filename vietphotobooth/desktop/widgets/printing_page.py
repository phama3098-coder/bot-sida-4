"""
VietPhotoBooth Print Management Page
Controls Windows Spooler printers, DNP DS-RX1HS 2-inch cut profiles, test prints, and queue management.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox,
    QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, QTimer

from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.printing.spooler import WindowsPrintSpooler
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class PrintingPage(QWidget):
    """Trang quản trị máy in nhiệt và hàng đợi in Windows Spooler."""

    def __init__(self, print_mgr: PrintManager, parent=None):
        super().__init__(parent)
        self.print_mgr = print_mgr

        self._init_ui()
        self._load_printers()
        self._refresh_queue()

        # Timer cập nhật hàng đợi in mỗi 2 giây
        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self._refresh_queue)
        self.queue_timer.start(2000)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 1. CẤU HÌNH THIẾT BỊ MÁY IN
        grp_printer = QGroupBox("1. Cấu Hình Máy In Windows")
        l_prn = QVBoxLayout(grp_printer)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("<b>Máy In Khả Dụng:</b>"))
        self.combo_printers = QComboBox()
        self.combo_printers.setMinimumWidth(280)
        r1.addWidget(self.combo_printers, 1)

        btn_refresh_prn = QPushButton("Quét Lại Driver")
        btn_refresh_prn.setObjectName("btn_secondary")
        btn_refresh_prn.clicked.connect(self._load_printers)
        r1.addWidget(btn_refresh_prn)

        btn_set_default = QPushButton("Đặt Làm Mặc Định")
        btn_set_default.setObjectName("btn_secondary")
        btn_set_default.clicked.connect(self._set_active_printer)
        r1.addWidget(btn_set_default)
        l_prn.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Khổ Giấy:"))
        self.combo_paper = QComboBox()
        self.combo_paper.addItems(["4x6 inch (10x15 cm Postcard)", "2x6 inch (5x15 cm Photo Strip)", "A4 (210x297 mm)"])
        r2.addWidget(self.combo_paper)

        self.chk_dnp_cut = QCheckBox("Bật chế độ Tự Cắt Đôi 2x6 (DNP DS-RX1HS)")
        self.chk_dnp_cut.setChecked(True)
        r2.addWidget(self.chk_dnp_cut)

        btn_test_print = QPushButton("🖨️ In Trang Kiểm Tra Căn Lề")
        btn_test_print.setObjectName("btn_success")
        btn_test_print.clicked.connect(self._print_test_page)
        r2.addWidget(btn_test_print)
        l_prn.addLayout(r2)

        layout.addWidget(grp_printer)

        # 2. HÀNG ĐỢI IN (PRINT QUEUE STATUS)
        grp_queue = QGroupBox("2. Hàng Đợi In Thời Gian Thực (Print Spooler Queue)")
        l_queue = QVBoxLayout(grp_queue)

        self.table_queue = QTableWidget(0, 5)
        self.table_queue.setHorizontalHeaderLabels(["Mã Lệnh (Job ID)", "File Ảnh", "Số Bản", "Trạng Thái", "Thời Gian"])
        self.table_queue.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l_queue.addWidget(self.table_queue)

        bar_q = QHBoxLayout()
        self.lbl_queue_stats = QLabel("Đang chờ: 0 • Đã in: 0")
        self.lbl_queue_stats.setStyleSheet("color: #38BDF8; font-weight: bold;")
        bar_q.addWidget(self.lbl_queue_stats, 1)

        btn_clear_queue = QPushButton("Xóa Lịch Sử Đã Hoàn Tất")
        btn_clear_queue.setObjectName("btn_secondary")
        btn_clear_queue.clicked.connect(self._clear_completed_jobs)
        bar_q.addWidget(btn_clear_queue)
        l_queue.addLayout(bar_q)

        layout.addWidget(grp_queue)

    def _load_printers(self):
        self.combo_printers.clear()
        printers = WindowsPrintSpooler.get_installed_printers()
        default_p = WindowsPrintSpooler.get_default_printer()

        if not printers:
            self.combo_printers.addItem("Không tìm thấy máy in (Dùng Virtual Spooler)", None)
        else:
            for p in printers:
                p_name = p["name"] if isinstance(p, dict) else str(p)
                label = f"{p_name} [Mặc Định]" if p_name == default_p else p_name
                self.combo_printers.addItem(label, p_name)

        if default_p:
            idx = self.combo_printers.findData(default_p)
            if idx >= 0:
                self.combo_printers.setCurrentIndex(idx)

    def _set_active_printer(self):
        selected = self.combo_printers.currentData()
        if selected:
            self.print_mgr.set_selected_printer(selected)
            QMessageBox.information(self, "Máy In", f"Đã chọn máy in mặc định: {selected}")

    def _print_test_page(self):
        success = self.print_mgr.print_test_page()
        if success:
            QMessageBox.information(self, "In Kiểm Tra", "Đã gửi thẻ kiểm tra màu và căn lề tới máy in thành công!")
            self._refresh_queue()
        else:
            QMessageBox.warning(self, "Thông Báo", "Không thể in trang kiểm tra. Vui lòng kiểm tra cáp USB và nguồn máy in.")

    def _refresh_queue(self):
        jobs = self.print_mgr.get_job_queue()
        self.table_queue.setRowCount(0)

        pending = 0
        completed = 0

        for j in reversed(jobs):
            row = self.table_queue.rowCount()
            self.table_queue.insertRow(row)
            self.table_queue.setItem(row, 0, QTableWidgetItem(str(j.get("id", ""))))
            self.table_queue.setItem(row, 1, QTableWidgetItem(str(j.get("filename", ""))))
            self.table_queue.setItem(row, 2, QTableWidgetItem(str(j.get("copies", 1))))

            status = j.get("status", "QUEUED")
            item_status = QTableWidgetItem(status)
            if status == "COMPLETED":
                item_status.setForeground(Qt.green)
                completed += 1
            elif status == "FAILED":
                item_status.setForeground(Qt.red)
            else:
                item_status.setForeground(Qt.yellow)
                pending += 1
            self.table_queue.setItem(row, 3, item_status)
            self.table_queue.setItem(row, 4, QTableWidgetItem(str(j.get("created_at", ""))))

        self.lbl_queue_stats.setText(f"Đang chờ / Đang in: {pending} • Đã in hoàn tất: {completed}")

    def _clear_completed_jobs(self):
        self.print_mgr.clear_completed_jobs()
        self._refresh_queue()
