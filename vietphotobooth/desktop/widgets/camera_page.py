"""
1998 TEAM — Photobooth Camera Management & Live View Page
Two-column modern Studio UI conforming to Screen 5:
- Left Column (60-65%): High-FPS Live Preview Viewport with LIVE PREVIEW badge,
  Aspect Ratio & FPS stats bar, Fullscreen trigger, Grid Lines overlay toggle,
  Reset stream, and Test Shot verification.
- Right Column (35-40%): Device Selection (Backend, Device Source, Auto-connect),
  Connection State badge, Hardware specifications (Resolution, FPS, Format, Caps),
  and Comprehensive Diagnostics Trigger.
- Collapsible Detailed Diagnostics Table & Studio Hardware Compatibility Matrix.
"""

import os
import time
import tempfile
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox, QFrame,
    QScrollArea, QDialog, QTextEdit, QApplication, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QFont, QPainter, QPen

from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.camera.models import ConnectionState
from vietphotobooth.camera.compatibility import CAMERA_COMPATIBILITY_MATRIX
from vietphotobooth.camera.enumerator import enumerate_directshow_devices, probe_video_source
from vietphotobooth.camera.diagnostics import (
    run_full_camera_diagnostics, format_diagnostic_report_text, export_diagnostic_report_file
)
from vietphotobooth.desktop.icons import get_svg_icon
from vietphotobooth.core.logger import get_logger

logger = get_logger()


class CameraDiagnosticDialog(QDialog):
    """Hộp thoại hiển thị và xuất báo cáo chẩn đoán camera chuyên nghiệp cho kỹ thuật viên."""

    def __init__(self, report_text: str, parent=None):
        super().__init__(parent)
        self.report_text = report_text
        self.setWindowTitle("1998 TEAM — Báo Cáo Chẩn Đoán Thiết Bị Máy Ảnh & Webcam")
        self.resize(780, 560)
        self.setStyleSheet("background-color: #0B111E; color: #F8FAFC;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel("BÁO CÁO CHẨN ĐOÁN CHI TIẾT THIẾT BỊ VIDEO & WEBCAM")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 900; color: #D4AF37; letter-spacing: 0.5px;")
        layout.addWidget(lbl_title)

        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setFont(QFont("Consolas", 10))
        self.txt_report.setText(self.report_text)
        self.txt_report.setStyleSheet(
            "QTextEdit { background-color: #070A12; border: 1.5px solid #1E2D4A; "
            "border-radius: 8px; padding: 12px; color: #E2E8F0; line-height: 1.4; }"
        )
        layout.addWidget(self.txt_report, 1)

        h_btn = QHBoxLayout()
        self.btn_copy = QPushButton("📋 Sao Chép Báo Cáo")
        self.btn_copy.setFixedHeight(40)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 18px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; background-color: #1A2844; }"
        )
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        h_btn.addWidget(self.btn_copy)

        self.btn_save = QPushButton("💾 Lưu File Báo Cáo (.txt / .json)")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #1E3A5F; border: 1px solid #38BDF8; color: #FFFFFF; "
            "font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 20px; }"
            "QPushButton:hover { background-color: #2563EB; }"
        )
        self.btn_save.clicked.connect(self._save_to_file)
        h_btn.addWidget(self.btn_save)

        h_btn.addStretch()

        self.btn_close = QPushButton("Đóng")
        self.btn_close.setFixedHeight(40)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(
            "QPushButton { background-color: #0E1626; border: 1px solid #1E2D4A; color: #94A3B8; "
            "font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 22px; }"
            "QPushButton:hover { color: #FFFFFF; background-color: #162033; }"
        )
        self.btn_close.clicked.connect(self.accept)
        h_btn.addWidget(self.btn_close)

        layout.addLayout(h_btn)

    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.report_text)
        QMessageBox.information(self, "Đã Sao Chép", "Đã sao chép toàn bộ báo cáo chẩn đoán vào bộ nhớ đệm (Clipboard)!")

    def _save_to_file(self):
        try:
            saved_file = export_diagnostic_report_file()
            QMessageBox.information(
                self, "Đã Lưu Báo Cáo",
                f"Đã lưu thành công báo cáo chẩn đoán tại đường dẫn:\n{saved_file}\n\n(Bao gồm cả file .txt và .json)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Lưu File", f"Không thể lưu file báo cáo: {e}")


class CameraPage(QWidget):
    """
    Trang Quản Trị, Cấu Hình & Live View Camera (Screen 5 trong thiết kế 1998 TEAM).
    Bố cục 2 cột chuẩn:
    - Cột trái: Viewport Live Preview (60-65%), Grid lines 3x3, Thống kê, Nút Chụp Thử, Đặt Lại.
    - Cột phải: Chọn loại camera, Chọn nguồn cụ thể, Checkbox tự động kết nối, Thông tin chi tiết phần cứng.
    """

    def __init__(self, camera_mgr: CameraManager, auth_mgr=None, parent=None):
        super().__init__(parent)
        self.camera_mgr = camera_mgr
        self.auth_mgr = auth_mgr
        self.grid_enabled = False

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS
        self._timer.timeout.connect(self._update_preview)

        self._init_ui()
        self._populate_devices()
        self._refresh_camera_info()

        # Dò quét chẩn đoán ban đầu
        QTimer.singleShot(300, self._run_diagnostics)

    def minimumSizeHint(self) -> QSize:
        return QSize(720, 480)

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def closeEvent(self, event):
        if hasattr(self, '_timer') and self._timer.isActive():
            self._timer.stop()
        super().closeEvent(event)

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        # Header trang
        header_box = QHBoxLayout()
        header_text = QVBoxLayout()
        lbl_title = QLabel("CẤU HÌNH MÁY ẢNH & LIVE VIEW")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 900; color: #D4AF37; letter-spacing: 0.5px;")
        lbl_subtitle = QLabel("1998 TEAM Photobooth • Quản lý kết nối, giám sát chất lượng luồng và chẩn đoán phần cứng.")
        lbl_subtitle.setStyleSheet("font-size: 12px; color: #94A3B8;")
        header_text.addWidget(lbl_title)
        header_text.addWidget(lbl_subtitle)
        header_box.addLayout(header_text)
        header_box.addStretch()
        layout.addLayout(header_box)

        # =========================================================================
        # BỐ CỤC CHÍNH 2 CỘT (SCREEN 5)
        # =========================================================================
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(16)

        # -------------------------------------------------------------------------
        # CỘT TRÁI: LIVE PREVIEW VIEWPORT (62% WIDTH)
        # -------------------------------------------------------------------------
        col_left = QVBoxLayout()
        col_left.setSpacing(10)

        self.card_preview = QFrame()
        self.card_preview.setStyleSheet(
            "QFrame { background-color: #050811; border: 1.5px solid #1E2D4A; border-radius: 12px; }"
        )
        l_prev = QVBoxLayout(self.card_preview)
        l_prev.setContentsMargins(12, 10, 12, 12)
        l_prev.setSpacing(8)

        # Header preview: Badge đỏ và nút Toàn màn hình
        h_prev_top = QHBoxLayout()
        self.lbl_live_badge = QLabel("🔴 LIVE PREVIEW")
        self.lbl_live_badge.setStyleSheet(
            "background-color: #DC2626; color: #FFFFFF; font-size: 11px; font-weight: 800; "
            "border-radius: 6px; padding: 4px 10px; border: 1px solid #EF4444;"
        )
        h_prev_top.addWidget(self.lbl_live_badge)
        h_prev_top.addStretch()

        self.btn_fullscreen = QPushButton("⛶")
        self.btn_fullscreen.setFixedSize(32, 28)
        self.btn_fullscreen.setCursor(Qt.PointingHandCursor)
        self.btn_fullscreen.setToolTip("Toàn Màn Hình Preview")
        self.btn_fullscreen.setStyleSheet(
            "QPushButton { background-color: #111A2E; color: #E2E8F0; font-size: 15px; font-weight: bold; "
            "border-radius: 6px; border: 1px solid #233454; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; background-color: #1B2945; }"
        )
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen_preview)
        h_prev_top.addWidget(self.btn_fullscreen)
        l_prev.addLayout(h_prev_top)

        # Khung hình video chính
        self.lbl_viewport = QLabel()
        self.lbl_viewport.setAlignment(Qt.AlignCenter)
        self.lbl_viewport.setStyleSheet(
            "background-color: #03050A; border-radius: 8px; border: 1px solid #162033;"
        )
        self.lbl_viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_viewport.setMinimumHeight(380)
        l_prev.addWidget(self.lbl_viewport, 1)

        # Footer preview: Thông số trực tiếp (Resolution | Aspect Ratio | FPS)
        self.lbl_preview_stats = QLabel("1920 × 1080  |  16:9  |  30.0 FPS")
        self.lbl_preview_stats.setAlignment(Qt.AlignCenter)
        self.lbl_preview_stats.setStyleSheet(
            "background-color: #0A111F; color: #CBD5E1; font-size: 12px; font-weight: 600; "
            "border-radius: 6px; padding: 6px 12px; border: 1px solid #1A263E;"
        )
        l_prev.addWidget(self.lbl_preview_stats)
        col_left.addWidget(self.card_preview, 1)

        # Hàng nút điều khiển ngay dưới Preview: Đặt lại, Chụp thử, Lưới căn chỉnh
        h_prev_actions = QHBoxLayout()
        h_prev_actions.setSpacing(10)

        self.btn_reset = QPushButton("↺ Đặt Lại")
        self.btn_reset.setFixedHeight(40)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 18px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; background-color: #1A2844; }"
        )
        self.btn_reset.clicked.connect(self._reset_camera_stream)
        h_prev_actions.addWidget(self.btn_reset)

        self.btn_test_shot = QPushButton("📸 Chụp Thử Nghiệm")
        self.btn_test_shot.setFixedHeight(40)
        self.btn_test_shot.setCursor(Qt.PointingHandCursor)
        self.btn_test_shot.setStyleSheet(
            "QPushButton { background-color: #1E3A5F; border: 1.5px solid #38BDF8; color: #FFFFFF; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 22px; }"
            "QPushButton:hover { background-color: #2563EB; border: 1.5px solid #60A5FA; }"
        )
        self.btn_test_shot.clicked.connect(self._take_test_shot)
        h_prev_actions.addWidget(self.btn_test_shot)

        self.btn_grid = QPushButton("▦ Lưới Căn Chỉnh: Tắt")
        self.btn_grid.setFixedHeight(40)
        self.btn_grid.setCursor(Qt.PointingHandCursor)
        self.btn_grid.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 18px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; background-color: #1A2844; }"
        )
        self.btn_grid.clicked.connect(self._toggle_grid)
        h_prev_actions.addWidget(self.btn_grid)

        col_left.addLayout(h_prev_actions)
        cols_layout.addLayout(col_left, 62)

        # -------------------------------------------------------------------------
        # CỘT PHẢI: BẢNG CHỌN THIẾT BỊ & THÔNG TIN PHẦN CỨNG (38% WIDTH)
        # -------------------------------------------------------------------------
        col_right = QVBoxLayout()
        col_right.setSpacing(12)

        # Card 1: Chọn Thiết Bị
        grp_ctrl = QGroupBox("CHỌN THIẾT BỊ")
        grp_ctrl.setStyleSheet(
            "QGroupBox { font-size: 13px; font-weight: bold; color: #D4AF37; "
            "border: 1.5px solid #1E2D4A; border-radius: 10px; margin-top: 10px; padding-top: 14px; background-color: #070B16; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; }"
        )
        l_ctrl = QVBoxLayout(grp_ctrl)
        l_ctrl.setContentsMargins(14, 14, 14, 14)
        l_ctrl.setSpacing(10)

        # Dropdown 1: Loại Camera (Backend)
        l_ctrl.addWidget(QLabel("<b style='color:#CBD5E1;'>Loại máy ảnh (Backend):</b>"))
        self.combo_backend = QComboBox()
        self.combo_backend.addItem("DirectShow Webcam (Nikon Webcam Utility, Logitech...)", "directshow")
        self.combo_backend.addItem("digiCamControl (DSLR Nikon / Canon Tethered)", "digicam")
        self.combo_backend.addItem("Simulator (Mô Phỏng Studio Không Cần Phần Cứng)", "simulator")
        self.combo_backend.setFixedHeight(36)
        self.combo_backend.currentIndexChanged.connect(self._on_backend_changed)
        l_ctrl.addWidget(self.combo_backend)

        # Dropdown 2: Nguồn thiết bị cụ thể kèm nút làm mới
        self.lbl_device_title = QLabel("<b style='color:#CBD5E1;'>Nguồn Video / Webcam Cụ Thể:</b>")
        l_ctrl.addWidget(self.lbl_device_title)

        h_dev = QHBoxLayout()
        self.combo_device = QComboBox()
        self.combo_device.setFixedHeight(36)
        h_dev.addWidget(self.combo_device, 1)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedSize(36, 36)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setToolTip("Dò quét lại danh sách thiết bị")
        btn_refresh.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "font-size: 14px; border-radius: 6px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; background-color: #1A2844; }"
        )
        btn_refresh.clicked.connect(self._refresh_device_list)
        h_dev.addWidget(btn_refresh)
        l_ctrl.addLayout(h_dev)

        # Checkbox tự động kết nối
        auto_conn = True
        if hasattr(self.camera_mgr, "config_mgr") and self.camera_mgr.config_mgr:
            auto_conn = self.camera_mgr.config_mgr.get("camera.auto_connect", True)
        self.chk_auto_connect = QCheckBox("Tự động kết nối camera này khi khởi động")
        self.chk_auto_connect.setChecked(auto_conn)
        self.chk_auto_connect.setStyleSheet("QCheckBox { color: #94A3B8; font-size: 12px; margin-top: 4px; }")
        self.chk_auto_connect.toggled.connect(self._on_auto_connect_toggled)
        l_ctrl.addWidget(self.chk_auto_connect)

        # Hàng nút Kết nối / Ngắt kết nối
        h_conn_btns = QHBoxLayout()
        self.btn_switch = QPushButton("Kết Nối Nguồn Này")
        self.btn_switch.setFixedHeight(38)
        self.btn_switch.setCursor(Qt.PointingHandCursor)
        self.btn_switch.setStyleSheet(
            "QPushButton { background-color: #D4AF37; border: none; color: #050811; "
            "font-size: 13px; font-weight: 900; border-radius: 6px; padding: 0 16px; }"
            "QPushButton:hover { background-color: #F3E5AB; }"
        )
        self.btn_switch.clicked.connect(self._switch_backend)
        h_conn_btns.addWidget(self.btn_switch, 1)

        self.btn_disconnect = QPushButton("Ngắt Kết Nối")
        self.btn_disconnect.setFixedHeight(38)
        self.btn_disconnect.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect.setStyleSheet(
            "QPushButton { background-color: #162033; border: 1px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 14px; }"
            "QPushButton:hover { background-color: #7F1D1D; border-color: #EF4444; color: #FFFFFF; }"
        )
        self.btn_disconnect.clicked.connect(self._disconnect_camera)
        h_conn_btns.addWidget(self.btn_disconnect)
        l_ctrl.addLayout(h_conn_btns)

        col_right.addWidget(grp_ctrl)

        # Card 2: Thông Tin Phần Cứng & Trạng Thái
        grp_info = QGroupBox("THÔNG TIN THIẾT BỊ")
        grp_info.setStyleSheet(
            "QGroupBox { font-size: 13px; font-weight: bold; color: #D4AF37; "
            "border: 1.5px solid #1E2D4A; border-radius: 10px; margin-top: 10px; padding-top: 14px; background-color: #070B16; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; }"
        )
        l_info = QVBoxLayout(grp_info)
        l_info.setContentsMargins(14, 14, 14, 14)
        l_info.setSpacing(8)

        # Huy hiệu trạng thái
        self.lbl_status = QLabel("Trạng thái: Đang kết nối...")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #10B981;")
        self.lbl_status.setWordWrap(True)
        l_info.addWidget(self.lbl_status)

        # Bảng tính năng & thông số tóm tắt
        self.table_caps = QTableWidget(5, 2)
        self.table_caps.setHorizontalHeaderLabels(["Thông Số", "Chi Tiết Thiết Bị Hiện Tại"])
        self.table_caps.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_caps.verticalHeader().setVisible(False)
        self.table_caps.setFixedHeight(145)
        self.table_caps.setStyleSheet(
            "QTableWidget { background-color: #050811; border: 1px solid #1E2D4A; gridline-color: #121A2B; font-size: 11px; }"
            "QHeaderView::section { background-color: #0A111F; color: #D4AF37; font-weight: bold; padding: 4px; border: 1px solid #1E2D4A; font-size: 11px; }"
            "QTableWidget::item { padding: 4px; color: #F8FAFC; }"
        )
        self.table_caps.setItem(0, 0, QTableWidgetItem("Tên Thiết Bị / Model"))
        self.table_caps.setItem(1, 0, QTableWidgetItem("Xem Trực Tiếp (Live View)"))
        self.table_caps.setItem(2, 0, QTableWidgetItem("Kích Hoạt Chụp (Shutter)"))
        self.table_caps.setItem(3, 0, QTableWidgetItem("Độ Phân Giải Hoạt Động"))
        self.table_caps.setItem(4, 0, QTableWidgetItem("Trạng Thái Phần Cứng"))
        l_info.addWidget(self.table_caps)

        # Nút kích hoạt chẩn đoán chi tiết & xuất báo cáo
        h_diag_acts = QHBoxLayout()
        self.btn_run_diag = QPushButton("🔄 Chạy Lại Chẩn Đoán")
        self.btn_run_diag.setFixedHeight(34)
        self.btn_run_diag.setCursor(Qt.PointingHandCursor)
        self.btn_run_diag.setStyleSheet(
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "font-size: 12px; font-weight: bold; border-radius: 6px; padding: 0 10px; }"
            "QPushButton:hover { border: 1px solid #D4AF37; color: #D4AF37; background-color: #1A2844; }"
        )
        self.btn_run_diag.clicked.connect(self._run_diagnostics)
        h_diag_acts.addWidget(self.btn_run_diag)

        self.btn_export_diag = QPushButton("📄 Xuất Báo Cáo")
        self.btn_export_diag.setFixedHeight(34)
        self.btn_export_diag.setCursor(Qt.PointingHandCursor)
        self.btn_export_diag.setStyleSheet(
            "QPushButton { background-color: #162033; border: 1px solid #38BDF8; color: #38BDF8; "
            "font-size: 12px; font-weight: bold; border-radius: 6px; padding: 0 12px; }"
            "QPushButton:hover { background-color: #1E3A5F; color: #FFFFFF; }"
        )
        self.btn_export_diag.clicked.connect(self._export_diagnostics)
        h_diag_acts.addWidget(self.btn_export_diag)
        l_info.addLayout(h_diag_acts)

        col_right.addWidget(grp_info)
        col_right.addStretch()
        cols_layout.addLayout(col_right, 38)

        layout.addLayout(cols_layout)

        # =========================================================================
        # BẢNG CHẨN ĐOÁN TOÀN DIỆN CÁC NGUỒN VIDEO TÌM ĐƯỢC (COLLAPSIBLE / EXPANDED)
        # =========================================================================
        grp_diag = QGroupBox("BẢNG CHẨN ĐOÁN CHI TIẾT TẤT CẢ NGUỒN VIDEO TÌM ĐƯỢC")
        grp_diag.setStyleSheet(
            "QGroupBox { font-size: 13px; font-weight: bold; color: #D4AF37; "
            "border: 1.5px solid #1E2D4A; border-radius: 10px; margin-top: 14px; padding-top: 14px; background-color: #070B16; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; }"
        )
        l_diag = QVBoxLayout(grp_diag)
        l_diag.setContentsMargins(14, 14, 14, 14)
        l_diag.setSpacing(10)

        lbl_diag_hint = QLabel("Kiểm tra khả năng mở nguồn, đọc khung hình thật, độ phân giải và FPS đo được trước khi đưa vào studio.")
        lbl_diag_hint.setStyleSheet("color: #94A3B8; font-size: 12px;")
        l_diag.addWidget(lbl_diag_hint)

        self.table_diag = QTableWidget(0, 8)
        self.table_diag.setHorizontalHeaderLabels([
            "STT", "Tên Thiết Bị (Friendly Name)", "Giao Thức", "Mở Nguồn",
            "Đọc Frame", "Độ Phân Giải Thực", "FPS Thực", "Đánh Giá / Trạng Thái"
        ])
        self.table_diag.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_diag.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_diag.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        self.table_diag.verticalHeader().setVisible(False)
        self.table_diag.setMinimumHeight(150)
        self.table_diag.setStyleSheet(
            "QTableWidget { background-color: #050811; border: 1px solid #1E2D4A; gridline-color: #162033; }"
            "QHeaderView::section { background-color: #0E1626; color: #D4AF37; font-weight: bold; padding: 6px; border: 1px solid #1E2D4A; }"
            "QTableWidget::item { padding: 6px; color: #F8FAFC; }"
        )
        l_diag.addWidget(self.table_diag)
        layout.addWidget(grp_diag)

        # =========================================================================
        # BẢNG TƯƠNG THÍCH MÁY ẢNH CHUYÊN NGHIỆP
        # =========================================================================
        grp_compat = QGroupBox("HƯỚNG DẪN KỸ THUẬT & TƯƠNG THÍCH THIẾT BỊ STUDIO 1998")
        grp_compat.setStyleSheet(
            "QGroupBox { font-size: 13px; font-weight: bold; color: #D4AF37; "
            "border: 1.5px solid #1E2D4A; border-radius: 10px; margin-top: 14px; padding-top: 14px; background-color: #070B16; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; }"
        )
        l_compat = QVBoxLayout(grp_compat)
        l_compat.setContentsMargins(14, 14, 14, 14)

        self.table_compat = QTableWidget(0, 4)
        self.table_compat.setHorizontalHeaderLabels([
            "Dòng Máy / Thiết Bị", "Mục Đích Sử Dụng", "Giao Thức Khuyến Nghị", "Hướng Dẫn Cài Đặt Cho Studio"
        ])
        self.table_compat.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_compat.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_compat.verticalHeader().setVisible(False)
        self.table_compat.setStyleSheet(
            "QTableWidget { background-color: #050811; border: 1px solid #1E2D4A; gridline-color: #162033; }"
            "QHeaderView::section { background-color: #0E1626; color: #D4AF37; font-weight: bold; padding: 6px; border: 1px solid #1E2D4A; }"
            "QTableWidget::item { padding: 6px; color: #CBD5E1; }"
        )

        brands_data = [
            (
                "Nikon D780 / Z Series",
                "Xem Live View Mượt Mà",
                "DirectShow -> 'Nikon Webcam Utility'",
                "Cắm cáp USB Type-C, gạt cần mở Live View (Lv) trên thân máy. Chọn nguồn 'Nikon Webcam Utility' ở mục Chọn Thiết Bị."
            ),
            (
                "Nikon D780 / D7500 / D850",
                "Chụp Ảnh 24MP Tethered",
                "digiCamControl (DIGICAM)",
                "Điều khiển tốc độ màn trập, khẩu độ, ISO và tự động tải ảnh gốc RAW/JPEG về máy tính qua USB."
            ),
            (
                "Logitech C270 / C920 / Brio",
                "Webcam Phần Cứng Dự Phòng",
                "DirectShow UVC",
                "Nguồn webcam USB tiêu chuẩn, cắm là chạy. Tự động nhận diện độ phân giải thực."
            ),
            (
                "Canon EOS (5D, 6D, R5, R6)",
                "Live View & Chụp Chuyên Nghiệp",
                "digiCamControl / EOS Webcam Utility",
                "Hỗ trợ cả xem trực tiếp và điều khiển chụp qua giao thức Canon EDSDK."
            ),
            (
                "Sony Alpha (a6400, a7 III/IV)",
                "Live View & Chụp USB",
                "DirectShow / Imaging Edge Webcam",
                "Bật chế độ 'PC Remote' trong cài đặt kết nối USB trên máy ảnh Sony."
            )
        ]
        for row, data in enumerate(brands_data):
            self.table_compat.insertRow(row)
            for col, text in enumerate(data):
                self.table_compat.setItem(row, col, QTableWidgetItem(text))

        l_compat.addWidget(self.table_compat)
        layout.addWidget(grp_compat)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # -------------------------------------------------------------------------
    # LIVE PREVIEW & RENDER LOGIC
    # -------------------------------------------------------------------------
    def _update_preview(self):
        """Cập nhật khung hình xem trước lên Viewport ở tần số ~30 FPS."""
        if not self.isVisible():
            return

        rgb_frame = self.camera_mgr.get_liveview_rgb()
        if rgb_frame is not None and rgb_frame.size > 0:
            h, w = rgb_frame.shape[:2]
            qimg = QImage(rgb_frame.data, w, h, 3 * w, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            # Căn tỷ lệ khớp khung nhìn nhưng giữ nguyên tỉ lệ gốc
            vw = self.lbl_viewport.width()
            vh = self.lbl_viewport.height()
            if vw > 20 and vh > 20:
                scaled = pixmap.scaled(vw, vh, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                # Vẽ lưới căn chỉnh 3x3 nếu bật
                if self.grid_enabled:
                    painter = QPainter(scaled)
                    pen = QPen(QColor(212, 175, 55, 170), 1.5, Qt.DashLine)
                    painter.setPen(pen)
                    sw = scaled.width()
                    sh = scaled.height()
                    # 2 đường dọc
                    painter.drawLine(int(sw / 3), 0, int(sw / 3), sh)
                    painter.drawLine(int(2 * sw / 3), 0, int(2 * sw / 3), sh)
                    # 2 đường ngang
                    painter.drawLine(0, int(sh / 3), sw, int(sh / 3))
                    painter.drawLine(0, int(2 * sh / 3), sw, int(2 * sh / 3))
                    painter.end()

                self.lbl_viewport.setPixmap(scaled)

            # Cập nhật thông số đáy
            info = self.camera_mgr.get_info()
            fps_val = info.get("fps") or 30.0
            self.lbl_preview_stats.setText(f"{w} × {h}  |  Tỉ lệ: {w}:{h}  |  {fps_val:.1f} FPS")

            if self.camera_mgr.current_backend_name == "simulator":
                self.lbl_live_badge.setText("🔴 MÔ PHỎNG (SIMULATOR)")
                self.lbl_live_badge.setStyleSheet("background-color: #D97706; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px;")
            else:
                self.lbl_live_badge.setText("🔴 LIVE PREVIEW")
                self.lbl_live_badge.setStyleSheet("background-color: #DC2626; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px;")
        else:
            # Không có tín hiệu
            self.lbl_viewport.setText("CHƯA CÓ TÍN HIỆU HÌNH ẢNH\nVui lòng kiểm tra cáp USB hoặc chọn lại nguồn camera.")
            self.lbl_viewport.setStyleSheet(
                "background-color: #03050A; border-radius: 8px; border: 1px dashed #334155; color: #64748B; font-size: 14px; font-weight: bold;"
            )
            self.lbl_live_badge.setText("⚠️ MẤT TÍN HIỆU")
            self.lbl_live_badge.setStyleSheet("background-color: #EF4444; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px;")

    def _toggle_grid(self):
        self.grid_enabled = not self.grid_enabled
        self.btn_grid.setText("▦ Lưới Căn Chỉnh: BẬT" if self.grid_enabled else "▦ Lưới Căn Chỉnh: Tắt")
        self.btn_grid.setStyleSheet(
            "QPushButton { background-color: #1A2844; border: 1.5px solid #D4AF37; color: #D4AF37; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 18px; }"
            if self.grid_enabled else
            "QPushButton { background-color: #121C30; border: 1px solid #28395E; color: #CBD5E1; "
            "font-size: 13px; font-weight: bold; border-radius: 8px; padding: 0 18px; }"
        )

    def _toggle_fullscreen_preview(self):
        """Mở rộng khung xem trước hoặc báo phóng to."""
        dlg = QDialog(self)
        dlg.setWindowTitle("1998 TEAM — Khung Hình Live Preview Toàn Màn Hình")
        dlg.resize(960, 640)
        dlg.setStyleSheet("background-color: #03050A;")
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel()
        lbl.setAlignment(Qt.AlignCenter)
        dlg_layout.addWidget(lbl)

        # Cập nhật timer tạm thời cho dialog
        t = QTimer(dlg)
        def update_fs():
            rgb = self.camera_mgr.get_liveview_rgb()
            if rgb is not None:
                h, w = rgb.shape[:2]
                qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
                px = QPixmap.fromImage(qimg)
                lbl.setPixmap(px.scaled(lbl.width(), lbl.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        t.timeout.connect(update_fs)
        t.start(33)
        dlg.exec()
        t.stop()

    def _reset_camera_stream(self):
        """Đặt lại và kết nối lại luồng video hiện tại."""
        try:
            self.camera_mgr.disconnect()
            time.sleep(0.1)
            self.camera_mgr.connect()
            self._refresh_camera_info()
            QMessageBox.information(self, "Đặt Lại", "Đã khởi tạo và làm mới lại luồng camera thành công!")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi Đặt Lại", f"Không thể đặt lại luồng camera: {e}")

    # -------------------------------------------------------------------------
    # ĐIỀU PHỐI KẾT NỐI & CẤU HÌNH
    # -------------------------------------------------------------------------
    def _on_backend_changed(self):
        backend = self.combo_backend.currentData()
        is_dshow = (backend == "directshow")
        self.lbl_device_title.setVisible(is_dshow)
        self.combo_device.setVisible(is_dshow)

    def _populate_devices(self):
        """Liệt kê các thiết bị DirectShow vào dropdown kèm tên thân thiện."""
        self.combo_device.clear()
        devs = enumerate_directshow_devices()

        if not devs:
            self.combo_device.addItem("Không tìm thấy webcam / nguồn video", 0)
            return

        for d in devs:
            idx = d["index"]
            name = d["name"]
            is_virtual = d.get("is_virtual", False)
            tag = " [Virtual Camera - Nikon D780]" if "nikon" in name.lower() else " [Hardware UVC]" if not is_virtual else " [Virtual]"
            self.combo_device.addItem(f"{name}{tag}", idx)

        # Ưu tiên tự động chọn Nikon Webcam Utility nếu có
        for i in range(self.combo_device.count()):
            text = self.combo_device.itemText(i)
            if "nikon" in text.lower():
                self.combo_device.setCurrentIndex(i)
                break

    def _refresh_device_list(self):
        self._populate_devices()
        self._run_diagnostics()
        QMessageBox.information(self, "Làm Mới", "Đã cập nhật danh sách thiết bị video thành công!")

    def _on_auto_connect_toggled(self, checked: bool):
        if hasattr(self.camera_mgr, "config_mgr") and self.camera_mgr.config_mgr:
            self.camera_mgr.config_mgr.set("camera.auto_connect", checked)
            self.camera_mgr.config_mgr.save()

    def _run_diagnostics(self):
        """Chạy kiểm tra thực tế trên từng nguồn video và điền vào bảng."""
        report = run_full_camera_diagnostics()
        devs = report.get("directshow_devices", [])

        self.table_diag.setRowCount(0)
        for row, d in enumerate(devs):
            self.table_diag.insertRow(row)
            idx = d["index"]
            name = d["name"]
            probe = d.get("probe", {})

            openable = "✅ CÓ" if probe.get("openable") else "❌ KHÔNG"
            readable = "✅ CÓ" if probe.get("frame_readable") else "❌ KHÔNG"
            w = probe.get("actual_width", 0)
            h = probe.get("actual_height", 0)
            res_str = f"{w} × {h}" if w > 0 else "N/A"
            fps_str = f"{probe.get('measured_fps', 0.0)} FPS" if probe.get("measured_fps") else "N/A"
            status_str = probe.get("status", "N/A")

            self.table_diag.setItem(row, 0, QTableWidgetItem(str(idx)))
            self.table_diag.setItem(row, 1, QTableWidgetItem(name))
            self.table_diag.setItem(row, 2, QTableWidgetItem(d.get("backend", "DSHOW")))

            item_open = QTableWidgetItem(openable)
            item_open.setTextAlignment(Qt.AlignCenter)
            self.table_diag.setItem(row, 3, item_open)

            item_read = QTableWidgetItem(readable)
            item_read.setTextAlignment(Qt.AlignCenter)
            self.table_diag.setItem(row, 4, item_read)

            item_res = QTableWidgetItem(res_str)
            item_res.setTextAlignment(Qt.AlignCenter)
            self.table_diag.setItem(row, 5, item_res)

            item_fps = QTableWidgetItem(fps_str)
            item_fps.setTextAlignment(Qt.AlignCenter)
            self.table_diag.setItem(row, 6, item_fps)

            item_status = QTableWidgetItem(status_str)
            self.table_diag.setItem(row, 7, item_status)

        # Thêm 1 dòng cho digiCamControl
        dc = report.get("digicam_status", {})
        dc_row = self.table_diag.rowCount()
        self.table_diag.insertRow(dc_row)
        self.table_diag.setItem(dc_row, 0, QTableWidgetItem("DSLR"))
        self.table_diag.setItem(dc_row, 1, QTableWidgetItem("digiCamControl (Nikon/Canon Tethered)"))
        self.table_diag.setItem(dc_row, 2, QTableWidgetItem("CLI / REST"))
        self.table_diag.setItem(dc_row, 3, QTableWidgetItem("✅ CÓ" if dc.get("cli_installed") else "❌ KHÔNG"))
        self.table_diag.setItem(dc_row, 4, QTableWidgetItem("✅ CÓ" if dc.get("liveview_stream_active") else "⚠️ TẮT"))
        self.table_diag.setItem(dc_row, 5, QTableWidgetItem("6000 × 4000 (Chụp)"))
        self.table_diag.setItem(dc_row, 6, QTableWidgetItem("Tethered"))
        self.table_diag.setItem(dc_row, 7, QTableWidgetItem(dc.get("status_summary", "")))

    def _export_diagnostics(self):
        """Mở hộp thoại xuất báo cáo chẩn đoán."""
        report = run_full_camera_diagnostics()
        text = format_diagnostic_report_text(report)
        dlg = CameraDiagnosticDialog(text, parent=self)
        dlg.exec()

    def _refresh_camera_info(self):
        curr_backend = self.camera_mgr.current_backend_name
        idx = self.combo_backend.findData(curr_backend)
        if idx >= 0:
            self.combo_backend.setCurrentIndex(idx)

        self._on_backend_changed()

        info = self.camera_mgr.get_info()
        is_connected = self.camera_mgr.is_connected()
        dev_name = info.get("device_name", "")
        last_error = info.get("last_error", "")
        w, h = info.get("actual_resolution", (0, 0))

        if is_connected:
            status_text = f"Đã Kết Nối: {dev_name}"
            if w > 0 and h > 0:
                status_text += f" ({w}×{h})"
            color = "#10B981"
        else:
            status_text = f"Chưa Kết Nối ({last_error or 'Không có tín hiệu'})"
            color = "#EF4444"

        self.lbl_status.setText(f"Trình điều khiển: {curr_backend.upper()} • {status_text}")
        self.lbl_status.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")

        # Cập nhật bảng tính năng
        self.table_caps.setItem(0, 1, QTableWidgetItem(dev_name or f"{curr_backend.upper()} Active Device"))
        self.table_caps.setItem(1, 1, QTableWidgetItem(f"Hỗ trợ ({w}×{h})" if is_connected else "Không khả dụng"))
        self.table_caps.setItem(2, 1, QTableWidgetItem("Hỗ trợ chụp độ phân giải cao" if is_connected else "Không"))
        self.table_caps.setItem(3, 1, QTableWidgetItem(f"{w} × {h}" if (w > 0 and h > 0) else "6000 × 4000 (24 MP)" if curr_backend == "digicam" else "1920 × 1080"))
        self.table_caps.setItem(4, 1, QTableWidgetItem(info.get("status") or ("Sẵn sàng" if is_connected else "Lỗi kết nối")))

    def _switch_backend(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Cấu Hình Máy Ảnh"):
                return

        chosen_backend = self.combo_backend.currentData()
        chosen_device_idx = self.combo_device.currentData()
        chosen_device_name = self.combo_device.currentText().split(" [")[0].strip()

        logger.info(f"Yêu cầu chuyển camera: Backend={chosen_backend}, Index={chosen_device_idx}, Name={chosen_device_name}")

        success = self.camera_mgr.switch_backend(
            backend=chosen_backend,
            device_index=chosen_device_idx or 0,
            device_name=chosen_device_name
        )

        if success:
            QMessageBox.information(
                self, "Kết Nối Thành Công",
                f"Đã kích hoạt thành công:\n• Trình điều khiển: {chosen_backend.upper()}\n• Nguồn: {chosen_device_name}"
            )
        else:
            err = self.camera_mgr.get_last_error()
            msg = f"Không thể kết nối với {chosen_device_name}.\n\nChi tiết lỗi: {err}\n\nHệ thống đã chuyển về chế độ Simulator an toàn."
            QMessageBox.warning(self, "Không Thể Kết Nối", msg)

        self._refresh_camera_info()
        self._run_diagnostics()

    def _disconnect_camera(self):
        """Ngắt kết nối an toàn với máy ảnh hiện tại."""
        self.camera_mgr.disconnect()
        self._refresh_camera_info()
        QMessageBox.information(self, "Ngắt Kết Nối", "Đã ngắt kết nối an toàn khỏi thiết bị máy ảnh.")

    def _take_test_shot(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Thử Nghiệm Máy Ảnh"):
                return

        tmp_shot = os.path.join(tempfile.gettempdir(), f"vietphotobooth_test_shot_{int(time.time())}.jpg")
        success, img = self.camera_mgr.capture_photo(tmp_shot)

        # Xác thực tệp thật tồn tại trên đĩa
        if success and img and os.path.exists(tmp_shot) and os.path.getsize(tmp_shot) > 0:
            file_kb = os.path.getsize(tmp_shot) / 1024
            QMessageBox.information(
                self, "Chụp Thử Nghiệm Thành Công",
                f"Ảnh chụp thử nghiệm đã được xác thực an toàn trên đĩa!\n\n"
                f"• Thiết bị: {self.camera_mgr.get_info().get('device_name')}\n"
                f"• Độ phân giải: {img.width} × {img.height} pixel\n"
                f"• Kích thước tệp: {file_kb:.1f} KB\n"
                f"• Lưu tại: {tmp_shot}"
            )
        else:
            err = self.camera_mgr.get_last_error()
            QMessageBox.critical(
                self, "Lỗi Chụp Ảnh",
                f"Không thể chụp ảnh từ thiết bị hiện tại.\nChi tiết: {err or 'Thiết bị không trả về dữ liệu ảnh hợp lệ.'}"
            )
