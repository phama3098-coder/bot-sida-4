"""
VietPhotoBooth Camera Management Page
Device discovery, backend switching (Simulator, DirectShow, digiCamControl), test capture, and capability diagnostics.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox, QFrame,
    QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage

from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.camera.compatibility import CAMERA_COMPATIBILITY_MATRIX
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class CameraPage(QWidget):
    """Trang quản trị và cấu hình thiết bị máy ảnh DSLR/Mirrorless/Webcam."""

    def __init__(self, camera_mgr: CameraManager, auth_mgr=None, parent=None):
        super().__init__(parent)
        self.camera_mgr = camera_mgr
        self.auth_mgr = auth_mgr

        self._init_ui()
        self._refresh_camera_info()

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

        # 1. BẢNG ĐIỀU KHIỂN THIẾT BỊ
        grp_ctrl = QGroupBox("1. Kết Nối & Lựa Chọn Máy Ảnh")
        l_ctrl = QVBoxLayout(grp_ctrl)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("<b>Trình Điều Khiển (Backend):</b>"))
        self.combo_backend = QComboBox()
        self.combo_backend.addItem("Simulator (Mô Phỏng Không Cần Phần Cứng)", "simulator")
        self.combo_backend.addItem("DirectShow Webcam (USB UVC)", "directshow")
        self.combo_backend.addItem("digiCamControl (DSLR/Mirrorless Canon/Nikon/Sony)", "digicam")
        row1.addWidget(self.combo_backend, 1)

        btn_switch = QPushButton("Đổi Thiết Bị")
        btn_switch.setObjectName("btn_secondary")
        btn_switch.clicked.connect(self._switch_backend)
        row1.addWidget(btn_switch)

        btn_refresh = QPushButton("Làm Mới Danh Sách")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._refresh_camera_info)
        row1.addWidget(btn_refresh)
        l_ctrl.addLayout(row1)

        row2 = QHBoxLayout()
        self.lbl_status = QLabel("Trạng thái: Đang kết nối...")
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: bold; color: #10B981;")
        row2.addWidget(self.lbl_status, 1)

        btn_test_shot = QPushButton("📸 Chụp Thử Nghiệm")
        btn_test_shot.setObjectName("btn_success")
        btn_test_shot.clicked.connect(self._take_test_shot)
        row2.addWidget(btn_test_shot)
        l_ctrl.addLayout(row2)

        layout.addWidget(grp_ctrl)

        # 2. KHẢ NĂNG THỰC TẾ CỦA THIẾT BỊ HIỆN TẠI (DIAGNOSTICS)
        grp_diag = QGroupBox("2. Trạng Thái & Tính Năng Được Hỗ Trợ")
        l_diag = QVBoxLayout(grp_diag)

        self.table_caps = QTableWidget(5, 2)
        self.table_caps.setHorizontalHeaderLabels(["Tính Năng", "Trạng Thái"])
        self.table_caps.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_caps.verticalHeader().setVisible(False)
        self.table_caps.setItem(0, 0, QTableWidgetItem("Tên Thiết Bị / Model"))
        self.table_caps.setItem(1, 0, QTableWidgetItem("Xem Trực Tiếp (Live View)"))
        self.table_caps.setItem(2, 0, QTableWidgetItem("Kích Hoạt Chụp (Shutter Trigger)"))
        self.table_caps.setItem(3, 0, QTableWidgetItem("Độ Phân Giải Tối Đa"))
        self.table_caps.setItem(4, 0, QTableWidgetItem("Mức Pin (Battery Level)"))
        l_diag.addWidget(self.table_caps)

        layout.addWidget(grp_diag)

        # 3. DANH SÁCH TƯƠNG THÍCH MÁY ẢNH CHUYÊN NGHIỆP
        grp_compat = QGroupBox("3. Bảng Tương Thích Các Hãng Máy Ảnh Lớn")
        l_compat = QVBoxLayout(grp_compat)

        self.table_compat = QTableWidget(0, 4)
        self.table_compat.setHorizontalHeaderLabels(["Hãng Sản Xuất", "Dòng Máy Phổ Biến", "Giao Thức Khuyến Nghị", "Ghi Chú"])
        self.table_compat.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Nạp dữ liệu các hãng máy ảnh
        brands_data = [
            ("Canon", "EOS 5D, 6D, 80D, Rebel T7/2000D, R5, R6, R10", "digiCamControl / EDSDK", "Hỗ trợ Live View mượt mà, điều khiển ISO/Khẩu độ trực tiếp."),
            ("Nikon", "D3500, D5600, D7500, D850, Z50, Z5, Z6, Z7", "digiCamControl / Type40", "Kết nối USB cắm là chạy, chụp và lấy nét tự động ổn định."),
            ("Sony", "Alpha a6000, a6400, a7 III, a7 IV, ZV-E10", "PC Remote USB / digiCam", "Cần bật 'PC Remote' trong cài đặt kết nối USB trên máy."),
            ("Fujifilm", "X-T3, X-T4, X-T30, X-S10, GFX", "digiCam / DirectShow", "Tethered shooting USB chất lượng cao."),
            ("Webcam UVC", "Logitech C920, C930e, Brio 4K, Razer Kiyo", "DirectShow UVC", "Tương thích chuẩn Windows không cần cài driver phụ.")
        ]
        for row, data in enumerate(brands_data):
            self.table_compat.insertRow(row)
            for col, text in enumerate(data):
                self.table_compat.setItem(row, col, QTableWidgetItem(text))

        l_compat.addWidget(self.table_compat)
        layout.addWidget(grp_compat)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _refresh_camera_info(self):
        curr_backend = self.camera_mgr.current_backend_name
        idx = self.combo_backend.findData(curr_backend)
        if idx >= 0:
            self.combo_backend.setCurrentIndex(idx)

        is_connected = self.camera_mgr.is_connected()
        status_text = "Đã Kết Nối" if is_connected else "Chưa Kết Nối"
        color = "#10B981" if is_connected else "#EF4444"
        self.lbl_status.setText(f"Trình điều khiển: {curr_backend.upper()} • Trạng thái: {status_text}")
        self.lbl_status.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {color};")

        # Cập nhật bảng tính năng
        self.table_caps.setItem(0, 1, QTableWidgetItem(f"{curr_backend.upper()} Active Device"))
        self.table_caps.setItem(1, 1, QTableWidgetItem("Hỗ trợ (30 FPS)" if is_connected else "Không khả dụng"))
        self.table_caps.setItem(2, 1, QTableWidgetItem("Hỗ trợ chụp độ phân giải cao" if is_connected else "Không"))
        self.table_caps.setItem(3, 1, QTableWidgetItem("6000 x 4000 (24 MP)" if curr_backend == "digicam" else "1920 x 1080 (Full HD)"))
        self.table_caps.setItem(4, 1, QTableWidgetItem("Nguồn cắm ngoài / 100%"))

    def _switch_backend(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Cấu Hình Máy Ảnh"):
                return
        chosen = self.combo_backend.currentData()
        success = self.camera_mgr.switch_backend(chosen)
        if success:
            QMessageBox.information(self, "Thành Công", f"Đã chuyển sang trình điều khiển: {chosen.upper()}")
        else:
            QMessageBox.warning(self, "Thông Báo", f"Không thể kích hoạt {chosen.upper()}, đã chuyển về Simulator an toàn.")
        self._refresh_camera_info()

    def _take_test_shot(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Thử Nghiệm Máy Ảnh"):
                return
        import tempfile, os
        tmp_shot = os.path.join(tempfile.gettempdir(), "vietphotobooth_test_shot.jpg")
        success, img = self.camera_mgr.capture_photo(tmp_shot)
        if success and img:
            QMessageBox.information(self, "Chụp Thành Công", f"Đã chụp ảnh thử nghiệm thành công!\nKích thước: {img.width}x{img.height} pixel\nLưu tại: {tmp_shot}")
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể chụp ảnh thử nghiệm từ thiết bị hiện tại.")
