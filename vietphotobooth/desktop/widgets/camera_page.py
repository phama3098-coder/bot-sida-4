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
import threading
from typing import Optional, Dict, Any, List
import numpy as np
import shiboken6

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox, QFrame,
    QScrollArea, QDialog, QTextEdit, QApplication, QCheckBox, QSizePolicy,
    QAbstractScrollArea, QBoxLayout
)
from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal, Slot, QRect
from PySide6.QtGui import QPixmap, QImage, QColor, QFont, QPainter, QPen

from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.camera.connection_manager import FPSTracker
from vietphotobooth.camera.models import ConnectionState
from vietphotobooth.camera.compatibility import CAMERA_COMPATIBILITY_MATRIX
from vietphotobooth.camera.enumerator import enumerate_directshow_devices, probe_video_source
from vietphotobooth.camera.diagnostics import (
    run_full_camera_diagnostics, format_diagnostic_report_text, export_diagnostic_report_file
)
from vietphotobooth.desktop.icons import (
    COLOR_GOLD, COLOR_GOLD_LIGHT, COLOR_GOLD_DARK, COLOR_GREEN, COLOR_RED, get_svg_icon
)
from vietphotobooth.desktop.styles import (
    THEME_BG_MAIN, THEME_SURFACE, THEME_BG_SECONDARY, THEME_INPUT_BG,
    THEME_BORDER, THEME_BORDER_LIGHT, THEME_TEXT_PRIMARY, THEME_TEXT_SECONDARY,
    THEME_TEXT_DISABLED, THEME_GOLD, THEME_GOLD_LIGHT, THEME_GOLD_PALE,
    THEME_GOLD_DARK, LIVE_VIEW_BG, THEME_SUCCESS, THEME_DANGER, THEME_WARNING,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_SECONDARY,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_BORDER, COLOR_BORDER_LIGHT,
    COLOR_CHAMPAGNE, COLOR_CHAMPAGNE_LIGHT, COLOR_PALE_GOLD,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR
)
from vietphotobooth.core.logger import get_logger

logger = get_logger()


class DiagnosticWorker(QThread):
    """Luồng chạy ngầm dò quét thiết bị và chẩn đoán nguồn video, không bao giờ chặn UI thread."""
    report_ready = Signal(dict)

    def run(self):
        try:
            report = run_full_camera_diagnostics()
            self.report_ready.emit(report)
        except Exception as e:
            logger.warning(f"Lỗi khi chạy chẩn đoán ngầm: {e}")
            self.report_ready.emit({})


class CameraConnectWorker(QThread):
    """
    Luồng chạy ngầm thực hiện kết nối và chuyển đổi camera backend.
    Tách biệt hoàn toàn I/O phần cứng (USB/PTP handshake, SDK init) khỏi GUI thread,
    loại bỏ triệt để hiện tượng Windows báo (Not Responding) trên trang Máy Ảnh.
    """
    finished_signal = Signal(bool, str, object, str)  # (success, backend, device_idx, device_name)

    def __init__(self, camera_mgr, backend: str, device_idx: Any, device_name: str, parent=None):
        super().__init__(parent)
        self.camera_mgr = camera_mgr
        self.backend = backend
        self.device_idx = device_idx
        self.device_name = device_name

    def run(self):
        try:
            success = self.camera_mgr.switch_backend(
                backend=self.backend,
                device_index=self.device_idx or 0,
                device_name=self.device_name
            )
            self.finished_signal.emit(bool(success), self.backend, self.device_idx, self.device_name)
        except Exception as e:
            logger.exception("Ngoại lệ khi chuyển đổi camera backend ngầm: %s", e)
            self.finished_signal.emit(False, self.backend, self.device_idx, self.device_name)


class CameraDiagnosticDialog(QDialog):
    """Hộp thoại hiển thị và xuất báo cáo chẩn đoán camera chuyên nghiệp cho kỹ thuật viên."""

    def __init__(self, report_text: str, parent=None):
        super().__init__(parent)
        self.report_text = report_text
        self.setWindowTitle("1998 TEAM — Báo Cáo Chẩn Đoán Thiết Bị Máy Ảnh & Webcam")
        self.resize(780, 560)
        self.setStyleSheet(f"background-color: {THEME_BG_MAIN}; color: {THEME_TEXT_PRIMARY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel("BÁO CÁO CHẨN ĐOÁN CHI TIẾT THIẾT BỊ VIDEO & WEBCAM")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 900; color: {THEME_TEXT_PRIMARY}; letter-spacing: 0.5px;")
        layout.addWidget(lbl_title)

        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setFont(QFont("Consolas", 10))
        self.txt_report.setText(self.report_text)
        self.txt_report.setStyleSheet(
            f"QTextEdit {{ background-color: {THEME_INPUT_BG}; border: 1.5px solid {THEME_BORDER}; "
            f"border-radius: 8px; padding: 12px; color: {THEME_TEXT_PRIMARY}; line-height: 1.4; }}"
        )
        layout.addWidget(self.txt_report, 1)

        h_btn = QHBoxLayout()
        self.btn_copy = QPushButton("📋 Sao Chép Báo Cáo")
        self.btn_copy.setFixedHeight(40)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet(
            f"QPushButton {{ background-color: {THEME_SURFACE}; border: 1.5px solid {THEME_BORDER}; color: {THEME_TEXT_PRIMARY}; "
            f"font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 18px; }} "
            f"QPushButton:hover {{ border: 1.5px solid {THEME_GOLD}; color: {THEME_TEXT_PRIMARY}; background-color: {THEME_BG_SECONDARY}; }}"
        )
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        h_btn.addWidget(self.btn_copy)

        self.btn_save = QPushButton("💾 Lưu File Báo Cáo (.txt / .json)")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {THEME_GOLD_LIGHT}, stop:1 {THEME_GOLD}); "
            f"border: 1px solid {THEME_GOLD_DARK}; color: #FFFFFF; font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 20px; }} "
            f"QPushButton:hover {{ background: {THEME_GOLD_LIGHT}; color: {THEME_TEXT_PRIMARY}; }}"
        )
        self.btn_save.clicked.connect(self._save_to_file)
        h_btn.addWidget(self.btn_save)

        h_btn.addStretch()

        self.btn_close = QPushButton("Đóng")
        self.btn_close.setFixedHeight(40)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {THEME_SURFACE}; border: 1.5px solid {THEME_BORDER}; color: {THEME_TEXT_PRIMARY}; "
            f"font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 22px; }} "
            f"QPushButton:hover {{ background-color: {THEME_BG_SECONDARY}; }}"
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


from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport


class CameraFullscreenDialog(QDialog):
    """
    Hộp thoại xem trước Live View toàn màn hình chuyên nghiệp cho trang Máy Ảnh.
    - Chế độ toàn màn hình không viền (Frameless Fullscreen).
    - Giữ nguyên tỷ lệ 1024 × 680 (3:2) của Nikon D780 căn giữa màn hình với nền tối chuẩn studio.
    - Thanh tiêu đề điều khiển & nút Thoát Toàn Màn Hình rõ ràng ở góc trên.
    - Nhấn phím ESC hoặc phím F11 hoặc bấm nút Thoát để trở về bố cục ban đầu ngay lập tức.
    - Hoàn toàn KHÔNG ngắt kết nối camera hoặc làm gián đoạn phiên làm việc.
    """

    def __init__(self, camera_mgr, grid_enabled: bool = False, face_detect_enabled: bool = False, face_service=None, face_eye_af_controller=None, parent=None):
        super().__init__(parent)
        self.camera_mgr = camera_mgr
        self.grid_enabled = grid_enabled
        self.face_detect_enabled = face_detect_enabled
        self.face_service = face_service
        self.face_eye_af_controller = face_eye_af_controller

        self.setWindowTitle("1998 TEAM — Khung Hình Live Preview Toàn Màn Hình")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet(f"background-color: {LIVE_VIEW_BG};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Thanh tiêu đề điều khiển nổi phía trên
        self.top_bar = QWidget(self)
        self.top_bar.setFixedHeight(54)
        self.top_bar.setStyleSheet(
            f"background-color: rgba(23, 25, 28, 0.94); border-bottom: 1.5px solid {THEME_BORDER};"
        )
        h_top = QHBoxLayout(self.top_bar)
        h_top.setContentsMargins(20, 0, 20, 0)
        h_top.setSpacing(14)

        lbl_badge = QLabel("🔴 LIVE PREVIEW TOÀN MÀN HÌNH")
        lbl_badge.setStyleSheet(
            "background-color: #DC2626; color: #FFFFFF; font-size: 12px; font-weight: 800; "
            "border-radius: 6px; padding: 4px 12px; border: 1px solid #EF4444;"
        )
        h_top.addWidget(lbl_badge)

        self.lbl_info = QLabel("Nikon D780 Native USB  |  1024 × 680  |  3:2  |  KeepAspectRatio")
        self.lbl_info.setStyleSheet(f"color: {THEME_TEXT_SECONDARY}; font-size: 13px; font-weight: 600;")
        h_top.addWidget(self.lbl_info)

        h_top.addStretch()

        self.btn_exit = QPushButton("✕ Thoát Toàn Màn Hình (ESC)")
        self.btn_exit.setFixedHeight(36)
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {THEME_GOLD_LIGHT}, stop:1 {THEME_GOLD}); "
            f"color: #FFFFFF; font-weight: 800; font-size: 12px; border-radius: 6px; padding: 0 18px; border: 1px solid {THEME_GOLD_DARK}; }} "
            f"QPushButton:hover {{ background: {THEME_GOLD_LIGHT}; color: {THEME_TEXT_PRIMARY}; }}"
        )
        self.btn_exit.clicked.connect(self.accept)
        h_top.addWidget(self.btn_exit)

        layout.addWidget(self.top_bar)

        # Viewport Live View
        self.viewport = CameraLiveViewport(self)
        self.viewport.set_grid_enabled(self.grid_enabled)
        self.viewport.set_face_detection_enabled(self.face_detect_enabled)
        if self.face_eye_af_controller and self.face_eye_af_controller.is_enabled:
            self.viewport.set_face_eye_af_state(True, self.face_eye_af_controller.state.value, self.face_eye_af_controller.target_eye)
            self.face_eye_af_controller.register_state_callback(self._on_af_state_changed)
        layout.addWidget(self.viewport, 1)

        if self.face_service and (self.face_detect_enabled or (self.face_eye_af_controller and self.face_eye_af_controller.is_enabled)):
            self.face_service.register_callback(self._on_faces_detected)

        # Timer cập nhật frame
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self._timer.start(33)  # ~30 FPS

    def _on_af_state_changed(self, state, msg, target_face, target_eye):
        if not shiboken6.isValid(self):
            return
        def _apply():
            if shiboken6.isValid(self) and hasattr(self, 'viewport') and shiboken6.isValid(self.viewport):
                self.viewport.set_face_eye_af_state(True, state.value, target_eye)
        QTimer.singleShot(0, self, _apply)

    def _on_faces_detected(self, faces, frame_shape=None, seq_id=0, ts=0.0):
        if self.face_eye_af_controller and self.face_eye_af_controller.is_enabled:
            self.face_eye_af_controller.process_faces(faces, frame_shape=frame_shape, sequence_id=seq_id, timestamp=ts)
        if not shiboken6.isValid(self):
            return
        def _apply():
            if shiboken6.isValid(self) and hasattr(self, 'viewport') and shiboken6.isValid(self.viewport):
                self.viewport.set_detected_faces(faces, sequence_id=seq_id)
        QTimer.singleShot(0, self, _apply)

    def _update_frame(self):
        frame_data = self.camera_mgr.get_frame_data()
        rgb = frame_data.rgb if (frame_data and frame_data.has_rgb) else self.camera_mgr.get_liveview_rgb()
        if rgb is not None:
            self.viewport.set_frame_rgb(rgb)
            if self.face_service and (self.face_detect_enabled or (self.face_eye_af_controller and self.face_eye_af_controller.is_enabled)):
                seq_id = frame_data.sequence_id if frame_data else 0
                ts = frame_data.timestamp if frame_data else 0.0
                self.face_service.submit_frame(rgb, sequence_id=seq_id, timestamp=ts)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_F11):
            self.accept()
        else:
            super().keyPressEvent(event)

    def done(self, r):
        if self._timer.isActive():
            self._timer.stop()
        if self.face_service:
            self.face_service.unregister_callback(self._on_faces_detected)
        if self.face_eye_af_controller:
            self.face_eye_af_controller.unregister_state_callback(self._on_af_state_changed)
        super().done(r)

    def closeEvent(self, event):
        if self._timer.isActive():
            self._timer.stop()
        if self.face_service:
            self.face_service.unregister_callback(self._on_faces_detected)
        if self.face_eye_af_controller:
            self.face_eye_af_controller.unregister_state_callback(self._on_af_state_changed)
        super().closeEvent(event)


class CameraPage(QWidget):
    af_diagnostic_finished = Signal(dict)
    _AF_DIAGNOSTIC_WATCHDOG_MS = 10_000

    """
    Trang Quản Trị, Cấu Hình & Live View Camera (Screen 5 trong thiết kế 1998 TEAM).
    Bố cục 2 cột chuẩn:
    - Cột trái: Viewport Live Preview (60-65%), Grid lines 3x3, Thống kê, Nút Chụp Thử, Đặt Lại.
    - Cột phải: Chọn loại camera, Chọn nguồn cụ thể, Checkbox tự động kết nối, Thông tin chi tiết phần cứng.
    """

    def __init__(
        self,
        camera_mgr: CameraManager,
        auth_mgr=None,
        face_service=None,
        face_eye_af_controller=None,
        parent=None
    ):
        super().__init__(parent)
        self.camera_mgr = camera_mgr
        self.auth_mgr = auth_mgr
        self.grid_enabled = False

        # Đo đạc FPS hiển thị trực quan (Render FPS)
        self._render_fps_tracker = FPSTracker(window_seconds=1.5)

        # Timer chu kỳ render khung hình xem trước (~30 FPS) - Chuẩn PreciseTimer cho Windows
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._update_preview)

        # Timer chu kỳ riêng biệt cập nhật thông số và trạng thái (A5 - không chạy ở mỗi frame)
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(500)
        self._stats_timer.timeout.connect(self._update_stats_display)

        self._diag_worker: Optional[DiagnosticWorker] = None
        self._connect_worker: Optional[CameraConnectWorker] = None
        self._af_diagnostic_thread = None
        self._af_diag_state_lock = threading.Lock()
        self._af_diag_stage = "idle"
        self.af_diagnostic_finished.connect(
            self._show_af_diagnostic_result,
            Qt.ConnectionType.QueuedConnection,
        )
        self._af_diag_watchdog = QTimer(self)
        self._af_diag_watchdog.setSingleShot(True)
        self._af_diag_watchdog.timeout.connect(self._on_af_diagnostic_watchdog)

        # Sử dụng Face & Eye Detection Service và FaceEyeAFController dùng chung (Single Source of Truth)
        self._face_service = face_service or getattr(self.camera_mgr, "face_service", None)
        if self._face_service is None:
            from vietphotobooth.camera.face_detector import FaceDetectionService
            self._face_service = FaceDetectionService(target_detection_fps=12.0)
        self._face_service.register_callback(self._on_faces_detected)

        self._face_eye_af_controller = face_eye_af_controller or getattr(self.camera_mgr, "face_eye_af_controller", None)
        if self._face_eye_af_controller is None:
            from vietphotobooth.camera.face_eye_af_controller import FaceEyeAFController
            self._face_eye_af_controller = FaceEyeAFController(
                af_trigger_fn=self.camera_mgr.trigger_autofocus,
                stability_frames=3,
                stability_px_threshold=20.0,
                movement_px_threshold=35.0,
                cooldown_sec=1.8,
            )
        self._face_eye_af_controller.register_state_callback(self._on_face_eye_af_state_changed)

        if hasattr(self.camera_mgr, "is_face_detect_enabled"):
            self._face_detect_enabled = self.camera_mgr.is_face_detect_enabled()
        else:
            self._face_detect_enabled = False

        if hasattr(self.camera_mgr, "is_face_eye_af_enabled"):
            self._face_eye_af_enabled = self.camera_mgr.is_face_eye_af_enabled()
        else:
            self._face_eye_af_enabled = False

        self._init_ui()
        self._populate_devices()
        self._refresh_camera_info()

        # Dò quét chẩn đoán ban đầu qua background worker (có thể hủy an toàn)
        self._initial_diag_timer = QTimer(self)
        self._initial_diag_timer.setSingleShot(True)
        self._initial_diag_timer.timeout.connect(self._run_diagnostics)
        self._initial_diag_timer.start(300)

    def minimumSizeHint(self) -> QSize:
        return QSize(720, 480)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = event.size().width()
        if hasattr(self, "cols_layout"):
            if w < 960 and self.cols_layout.direction() != QBoxLayout.TopToBottom:
                self.cols_layout.setDirection(QBoxLayout.TopToBottom)
            elif w >= 960 and self.cols_layout.direction() != QBoxLayout.LeftToRight:
                self.cols_layout.setDirection(QBoxLayout.LeftToRight)

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()
        self._stats_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()
        self._stats_timer.stop()

    def close(self) -> bool:
        if hasattr(self, '_initial_diag_timer') and self._initial_diag_timer.isActive():
            self._initial_diag_timer.stop()
        if hasattr(self, '_timer') and self._timer.isActive():
            self._timer.stop()
        if hasattr(self, '_stats_timer') and self._stats_timer.isActive():
            self._stats_timer.stop()
        if hasattr(self, '_diag_worker') and self._diag_worker and self._diag_worker.isRunning():
            self._diag_worker.quit()
            self._diag_worker.wait(500)
        if hasattr(self, '_connect_worker') and self._connect_worker and self._connect_worker.isRunning():
            self._connect_worker.quit()
            self._connect_worker.wait(500)
        if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller:
            try:
                self._face_eye_af_controller.unregister_state_callback(self._on_face_eye_af_state_changed)
            except Exception:
                pass
        if hasattr(self, '_face_service') and self._face_service:
            try:
                self._face_service.unregister_callback(self._on_faces_detected)
            except Exception:
                pass
        return super().close()

    def closeEvent(self, event):
        if hasattr(self, '_initial_diag_timer') and self._initial_diag_timer.isActive():
            self._initial_diag_timer.stop()
        if hasattr(self, '_timer') and self._timer.isActive():
            self._timer.stop()
        if hasattr(self, '_stats_timer') and self._stats_timer.isActive():
            self._stats_timer.stop()
        if hasattr(self, '_diag_worker') and self._diag_worker and self._diag_worker.isRunning():
            self._diag_worker.quit()
            self._diag_worker.wait(500)
        if hasattr(self, '_connect_worker') and self._connect_worker and self._connect_worker.isRunning():
            self._connect_worker.quit()
            self._connect_worker.wait(500)
        if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller:
            try:
                self._face_eye_af_controller.unregister_state_callback(self._on_face_eye_af_state_changed)
            except Exception:
                pass
        if hasattr(self, '_face_service') and self._face_service:
            try:
                self._face_service.unregister_callback(self._on_faces_detected)
            except Exception:
                pass
        super().closeEvent(event)

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        self.scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        # Header trang
        header_box = QHBoxLayout()
        header_text = QVBoxLayout()
        lbl_title = QLabel("CẤU HÌNH MÁY ẢNH & LIVE VIEW")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {COLOR_TEXT_PRIMARY}; letter-spacing: 0.5px; border: none; background: transparent;")
        lbl_subtitle = QLabel("1998 TEAM Photobooth • Quản lý kết nối, giám sát chất lượng luồng và chẩn đoán phần cứng.")
        lbl_subtitle.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
        header_text.addWidget(lbl_title)
        header_text.addWidget(lbl_subtitle)
        header_box.addLayout(header_text)
        header_box.addStretch()
        layout.addLayout(header_box)

        # =========================================================================
        # BỐ CỤC CHÍNH 2 CỘT (SCREEN 5) - RESPONSIVE 2-COLUMN LAYOUT
        # =========================================================================
        self.cols_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.cols_layout.setSpacing(16)

        # -------------------------------------------------------------------------
        # CỘT TRÁI: LIVE PREVIEW VIEWPORT (62% WIDTH)
        # -------------------------------------------------------------------------
        self.col_left_widget = QWidget()
        col_left = QVBoxLayout(self.col_left_widget)
        col_left.setContentsMargins(0, 0, 0, 0)
        col_left.setSpacing(10)

        self.card_preview = QFrame()
        self.card_preview.setObjectName("card_preview")
        self.card_preview.setStyleSheet(f"""
            QFrame#card_preview {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        l_prev = QVBoxLayout(self.card_preview)
        l_prev.setContentsMargins(12, 10, 12, 12)
        l_prev.setSpacing(8)

        # Header preview: Badge đỏ + Badge AF + Badge AI
        h_prev_top = QHBoxLayout()
        self.lbl_live_badge = QLabel("🔴 LIVE PREVIEW")
        self.lbl_live_badge.setFixedHeight(24)
        self.lbl_live_badge.setStyleSheet(
            "background-color: #DC2626; color: #FFFFFF; font-size: 11px; font-weight: 800; "
            "border-radius: 6px; padding: 4px 10px; border: 1px solid #EF4444;"
        )
        h_prev_top.addWidget(self.lbl_live_badge)

        self.lbl_af_status = QLabel("🎯 AF: SẴN SÀNG")
        self.lbl_af_status.setFixedHeight(24)
        self.lbl_af_status.setStyleSheet(
            f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 700; "
            f"border-radius: 6px; padding: 4px 10px; border: 1px solid {COLOR_BORDER};"
        )
        h_prev_top.addWidget(self.lbl_af_status)

        self.lbl_ai_badge = QLabel("👁 AI MẮT: TẮT")
        self.lbl_ai_badge.setFixedHeight(24)
        self.lbl_ai_badge.setStyleSheet(
            f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 700; "
            f"border-radius: 6px; padding: 4px 10px; border: 1px solid {COLOR_BORDER};"
        )
        h_prev_top.addWidget(self.lbl_ai_badge)

        self.lbl_face_eye_af_status = QLabel("🎯 EYE AF: TẮT")
        self.lbl_face_eye_af_status.setFixedHeight(24)
        self.lbl_face_eye_af_status.setStyleSheet(
            f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 700; "
            f"border-radius: 6px; padding: 4px 10px; border: 1px solid {COLOR_BORDER};"
        )
        h_prev_top.addWidget(self.lbl_face_eye_af_status)
        h_prev_top.addStretch()
        l_prev.addLayout(h_prev_top)

        # Khung hình video chính (Zero-Jitter Viewport)
        self.lbl_viewport = CameraLiveViewport(self.card_preview)
        self.lbl_viewport.setMinimumHeight(280)
        l_prev.addWidget(self.lbl_viewport, 1)

        # Footer preview: Thông số trực tiếp (Resolution | Aspect Ratio | Read/Render FPS)
        self.lbl_preview_stats = QLabel("1920 × 1080  |  16:9  |  30.0 FPS")
        self.lbl_preview_stats.setAlignment(Qt.AlignCenter)
        self.lbl_preview_stats.setFixedHeight(28)
        self.lbl_preview_stats.setStyleSheet(
            f"background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 600; "
            f"border-radius: 6px; padding: 4px 12px; border: 1px solid {COLOR_BORDER};"
        )
        l_prev.addWidget(self.lbl_preview_stats)
        col_left.addWidget(self.card_preview, 1)

        # Hàng nút điều khiển ngay dưới Preview: AF, Face/Eye AF, Nhận diện mắt, Chụp thử, Lưới, Toàn màn hình, Đặt lại
        h_prev_actions = QHBoxLayout()
        h_prev_actions.setSpacing(8)

        action_btn_style = (
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; "
            f"font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }} "
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; }} "
            f"QPushButton:disabled {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_SECONDARY}; }}"
        )

        self.btn_af = QPushButton("🎯 Lấy Nét (AF)")
        self.btn_af.setFixedHeight(38)
        self.btn_af.setCursor(Qt.PointingHandCursor)
        self.btn_af.setToolTip("Yêu cầu camera thực hiện lấy nét tự động một lần qua USB (One-shot AF)")
        self.btn_af.setStyleSheet(action_btn_style)
        self.btn_af.clicked.connect(self._trigger_camera_af)
        h_prev_actions.addWidget(self.btn_af)

        self.btn_face_eye_af = QPushButton("🎯 Face/Eye AF: Tắt")
        self.btn_face_eye_af.setFixedHeight(38)
        self.btn_face_eye_af.setCursor(Qt.PointingHandCursor)
        self.btn_face_eye_af.setToolTip("Bật/tắt tự động lấy nét mắt & khuôn mặt khi chủ thể ổn định (Software-Triggered Face/Eye AF)")
        self.btn_face_eye_af.setStyleSheet(action_btn_style)
        self.btn_face_eye_af.clicked.connect(self._toggle_face_eye_af)
        h_prev_actions.addWidget(self.btn_face_eye_af)

        self.btn_face_detect = QPushButton("👁 Nhận Diện: Tắt")
        self.btn_face_detect.setFixedHeight(38)
        self.btn_face_detect.setCursor(Qt.PointingHandCursor)
        self.btn_face_detect.setToolTip("Bật/tắt nhận diện khuôn mặt và mắt bằng AI trên khung xem trước (Software Preview)")
        self.btn_face_detect.setStyleSheet(action_btn_style)
        self.btn_face_detect.clicked.connect(self._toggle_face_detection)
        h_prev_actions.addWidget(self.btn_face_detect)

        # Cập nhật hiển thị trạng thái ban đầu nếu đã được bật trong cấu hình dùng chung
        if self._face_detect_enabled:
            self.lbl_viewport.set_face_detection_enabled(True)
            self.btn_face_detect.setText("👁 Nhận Diện: BẬT")
            self.btn_face_detect.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1.5px solid {COLOR_CHAMPAGNE}; color: {COLOR_TEXT_PRIMARY}; "
                f"font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }}"
            )
            self.lbl_ai_badge.setText("👁 AI MẮT: BẬT")
            self.lbl_ai_badge.setStyleSheet(
                f"background-color: {COLOR_PALE_GOLD}; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 700; "
                f"border-radius: 6px; padding: 4px 10px; border: 1px solid {COLOR_CHAMPAGNE};"
            )

        if self._face_eye_af_enabled:
            self.lbl_viewport.set_face_eye_af_state(True, "SEARCHING", None)
            self.btn_face_eye_af.setText("🎯 Face/Eye AF: BẬT")
            self.btn_face_eye_af.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1.5px solid {COLOR_CHAMPAGNE}; color: {COLOR_TEXT_PRIMARY}; "
                f"font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }}"
            )
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: ĐANG TÌM KHUÔN MẶT")
            self.lbl_face_eye_af_status.setStyleSheet(
                f"background-color: {COLOR_PALE_GOLD}; color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 700; "
                f"border-radius: 6px; padding: 4px 10px; border: 1px solid {COLOR_CHAMPAGNE};"
            )

        self.btn_test_shot = QPushButton("📸 Chụp Thử Nghiệm")
        self.btn_test_shot.setFixedHeight(38)
        self.btn_test_shot.setCursor(Qt.PointingHandCursor)
        self.btn_test_shot.setStyleSheet(action_btn_style)
        self.btn_test_shot.clicked.connect(self._take_test_shot)
        h_prev_actions.addWidget(self.btn_test_shot)

        self.btn_grid = QPushButton("▦ Lưới: Tắt")
        self.btn_grid.setFixedHeight(38)
        self.btn_grid.setCursor(Qt.PointingHandCursor)
        self.btn_grid.setStyleSheet(action_btn_style)
        self.btn_grid.clicked.connect(self._toggle_grid)
        h_prev_actions.addWidget(self.btn_grid)

        self.btn_fullscreen = QPushButton("⛶ Toàn Màn Hình")
        self.btn_fullscreen.setFixedHeight(38)
        self.btn_fullscreen.setCursor(Qt.PointingHandCursor)
        self.btn_fullscreen.setToolTip("Mở toàn màn hình live preview (ESC để thoát)")
        self.btn_fullscreen.setStyleSheet(action_btn_style)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen_preview)
        h_prev_actions.addWidget(self.btn_fullscreen)

        self.btn_reset = QPushButton("↺ Đặt Lại")
        self.btn_reset.setFixedHeight(38)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(action_btn_style)
        self.btn_reset.clicked.connect(self._reset_camera_stream)
        h_prev_actions.addWidget(self.btn_reset)

        col_left.addLayout(h_prev_actions)
        self.cols_layout.addWidget(self.col_left_widget, 62)

        # -------------------------------------------------------------------------
        # CỘT PHẢI: BẢNG CHỌN THIẾT BỊ & THÔNG TIN PHẦN CỨNG (38% WIDTH)
        # -------------------------------------------------------------------------
        self.col_right_widget = QWidget()
        col_right = QVBoxLayout(self.col_right_widget)
        col_right.setContentsMargins(0, 0, 0, 0)
        col_right.setSpacing(12)

        # Card 1: Chọn Thiết Bị
        grp_ctrl = QGroupBox("CHỌN THIẾT BỊ")
        grp_ctrl.setStyleSheet(
            f"QGroupBox {{ font-size: 13px; font-weight: bold; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 12px; margin-top: 10px; padding-top: 14px; background-color: {COLOR_SURFACE}; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        l_ctrl = QVBoxLayout(grp_ctrl)
        l_ctrl.setContentsMargins(14, 14, 14, 14)
        l_ctrl.setSpacing(10)

        # Dropdown 1: Loại Camera (Backend)
        lbl_backend = QLabel(f"<b style='color:{COLOR_TEXT_PRIMARY};'>Loại máy ảnh (Backend):</b>")
        lbl_backend.setStyleSheet("border: none; background: transparent;")
        l_ctrl.addWidget(lbl_backend)
        self.combo_backend = QComboBox()
        self.combo_backend.blockSignals(True)
        self.combo_backend.addItem("Nikon MAID Native USB (Nikon D780 trực tiếp USB)", "nikon_maid")
        self.combo_backend.addItem("DirectShow Webcam (Nikon Webcam Utility, Logitech...)", "directshow")
        self.combo_backend.addItem("digiCamControl (DSLR Nikon / Canon Tethered)", "digicam")
        self.combo_backend.addItem("Simulator (Mô Phỏng Studio Không Cần Phần CỨng)", "simulator")
        self.combo_backend.blockSignals(False)
        self.combo_backend.setFixedHeight(36)
        self.combo_backend.setStyleSheet(
            f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 2px 8px;"
        )
        self.combo_backend.currentIndexChanged.connect(self._on_backend_changed)
        l_ctrl.addWidget(self.combo_backend)

        # Dropdown 2: Nguồn thiết bị cụ thể kèm nút làm mới
        self.lbl_device_title = QLabel(f"<b style='color:{COLOR_TEXT_PRIMARY};'>Nguồn Video / Webcam Cụ Thể:</b>")
        self.lbl_device_title.setStyleSheet("border: none; background: transparent;")
        l_ctrl.addWidget(self.lbl_device_title)

        h_dev = QHBoxLayout()
        self.combo_device = QComboBox()
        self.combo_device.setFixedHeight(36)
        self.combo_device.setStyleSheet(
            f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 2px 8px;"
        )
        h_dev.addWidget(self.combo_device, 1)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedSize(36, 36)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setToolTip("Dò quét lại danh sách thiết bị")
        btn_refresh.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; "
            f"font-size: 14px; border-radius: 6px; }} "
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
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
        self.chk_auto_connect.setStyleSheet(f"QCheckBox {{ color: {COLOR_TEXT_SECONDARY}; font-size: 12px; margin-top: 4px; }}")
        self.chk_auto_connect.toggled.connect(self._on_auto_connect_toggled)
        l_ctrl.addWidget(self.chk_auto_connect)

        # Hàng nút Kết nối / Ngắt kết nối: Thiết lập min-width và phân bổ tỉ lệ 3:2 chống co xẹp
        h_conn_btns = QHBoxLayout()
        h_conn_btns.setSpacing(8)
        self.btn_switch = QPushButton("Kết Nối Nguồn Này")
        self.btn_switch.setFixedHeight(38)
        self.btn_switch.setMinimumWidth(145)
        self.btn_switch.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_switch.setCursor(Qt.PointingHandCursor)
        self.btn_switch.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT}); "
            f"border: none; color: #1C1D1C; font-size: 12px; font-weight: 800; border-radius: 6px; padding: 0 12px; }} "
            f"QPushButton:hover {{ background: #A88952; color: #FFFFFF; }} "
            f"QPushButton:disabled {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_SECONDARY}; }}"
        )
        self.btn_switch.clicked.connect(self._switch_backend)
        h_conn_btns.addWidget(self.btn_switch, 3)

        self.btn_disconnect = QPushButton("Ngắt Kết Nối")
        self.btn_disconnect.setFixedHeight(38)
        self.btn_disconnect.setMinimumWidth(105)
        self.btn_disconnect.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_disconnect.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; "
            f"font-size: 12px; font-weight: bold; border-radius: 6px; padding: 0 10px; }} "
            f"QPushButton:hover {{ background-color: #FDE8E8; border-color: #FCA5A5; color: {COLOR_ERROR}; }} "
            f"QPushButton:disabled {{ background-color: {COLOR_SURFACE_SECONDARY}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_SECONDARY}; }}"
        )
        self.btn_disconnect.clicked.connect(self._disconnect_camera)
        h_conn_btns.addWidget(self.btn_disconnect, 2)
        l_ctrl.addLayout(h_conn_btns)

        col_right.addWidget(grp_ctrl)

        # Card 2: Thông Tin Phần Cứng & Trạng Thái
        grp_info = QGroupBox("THÔNG TIN THIẾT BỊ")
        grp_info.setStyleSheet(
            f"QGroupBox {{ font-size: 13px; font-weight: bold; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 12px; margin-top: 10px; padding-top: 14px; background-color: {COLOR_SURFACE}; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        l_info = QVBoxLayout(grp_info)
        l_info.setContentsMargins(14, 14, 14, 14)
        l_info.setSpacing(8)

        # Huy hiệu trạng thái
        self.lbl_status = QLabel("Trạng thái: Đang kết nối...")
        self.lbl_status.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {COLOR_SUCCESS}; border: none; background: transparent;")
        self.lbl_status.setWordWrap(True)
        l_info.addWidget(self.lbl_status)

        # Bảng tính năng & thông số tóm tắt
        self.table_caps = QTableWidget(5, 2)
        self.table_caps.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.table_caps.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_caps.setHorizontalHeaderLabels(["Thông Số", "Chi Tiết Thiết Bị Hiện Tại"])
        self.table_caps.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_caps.verticalHeader().setVisible(False)
        self.table_caps.setFixedHeight(145)
        self.table_caps.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; gridline-color: {COLOR_BORDER_LIGHT}; font-size: 11px; }} "
            f"QHeaderView::section {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-weight: bold; padding: 4px; border: none; border-bottom: 1.5px solid {COLOR_BORDER}; font-size: 11px; }} "
            f"QTableWidget::item {{ padding: 4px; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        self.table_caps.setItem(0, 0, QTableWidgetItem("Tên Thiết Bị / Model"))
        self.table_caps.setItem(1, 0, QTableWidgetItem("Xem Trực Tiếp (Live View)"))
        self.table_caps.setItem(2, 0, QTableWidgetItem("Kích Hoạt Chụp (Shutter)"))
        self.table_caps.setItem(3, 0, QTableWidgetItem("Độ Phân Giải Hoạt Động"))
        self.table_caps.setItem(4, 0, QTableWidgetItem("Trạng Thái Phần Cứng"))
        l_info.addWidget(self.table_caps)

        # Nút kích hoạt chẩn đoán chi tiết & xuất báo cáo (2 hàng ngăn nắp, chống clipping Test AF)
        diag_acts_box = QVBoxLayout()
        diag_acts_box.setSpacing(6)

        h_diag_acts_top = QHBoxLayout()
        h_diag_acts_top.setSpacing(8)

        self.btn_run_diag = QPushButton("🔄 Chạy Lại Chẩn Đoán")
        self.btn_run_diag.setFixedHeight(34)
        self.btn_run_diag.setCursor(Qt.PointingHandCursor)
        self.btn_run_diag.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; "
            f"font-size: 12px; font-weight: bold; border-radius: 6px; padding: 0 10px; }} "
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
        )
        self.btn_run_diag.clicked.connect(self._run_diagnostics)
        h_diag_acts_top.addWidget(self.btn_run_diag, 1)

        self.btn_export_diag = QPushButton("📄 Xuất Báo Cáo")
        self.btn_export_diag.setFixedHeight(34)
        self.btn_export_diag.setCursor(Qt.PointingHandCursor)
        self.btn_export_diag.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; "
            f"font-size: 12px; font-weight: bold; border-radius: 6px; padding: 0 10px; }} "
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
        )
        self.btn_export_diag.clicked.connect(self._export_diagnostics)
        h_diag_acts_top.addWidget(self.btn_export_diag, 1)
        diag_acts_box.addLayout(h_diag_acts_top)

        self.btn_test_af = QPushButton("🩺 Test AF Chuyên Sâu")
        self.btn_test_af.setFixedHeight(34)
        self.btn_test_af.setCursor(Qt.PointingHandCursor)
        self.btn_test_af.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; "
            f"font-size: 12px; font-weight: bold; border-radius: 6px; padding: 0 10px; }} "
            f"QPushButton:hover {{ border: 1px solid {COLOR_CHAMPAGNE}; background-color: {COLOR_SURFACE_SECONDARY}; }}"
        )
        self.btn_test_af.setToolTip("Chẩn đoán AF chuyên sâu: Kiểm tra kết nối, MF/AF, Live View, đo độ nét quang học (Tenengrad Laplacian) và phân loại lỗi.")
        self.btn_test_af.clicked.connect(self._run_af_diagnostic)
        diag_acts_box.addWidget(self.btn_test_af)

        l_info.addLayout(diag_acts_box)

        col_right.addWidget(grp_info)
        col_right.addStretch()
        self.cols_layout.addWidget(self.col_right_widget, 38)

        layout.addLayout(self.cols_layout)

        # =========================================================================
        # BẢNG CHẨN ĐOÁN TOÀN DIỆN CÁC NGUỒN VIDEO TÌM ĐƯỢC (COLLAPSIBLE / EXPANDED)
        # =========================================================================
        grp_diag = QGroupBox("BẢNG CHẨN ĐOÁN CHI TIẾT TẤT CẢ NGUỒN VIDEO TÌM ĐƯỢC")
        grp_diag.setStyleSheet(
            f"QGroupBox {{ font-size: 13px; font-weight: bold; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 12px; margin-top: 14px; padding-top: 14px; background-color: {COLOR_SURFACE}; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        l_diag = QVBoxLayout(grp_diag)
        l_diag.setContentsMargins(14, 14, 14, 14)
        l_diag.setSpacing(10)

        lbl_diag_hint = QLabel("Kiểm tra khả năng mở nguồn, đọc khung hình thật, độ phân giải và FPS đo được trước khi đưa vào studio.")
        lbl_diag_hint.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")
        l_diag.addWidget(lbl_diag_hint)

        self.table_diag = QTableWidget(0, 8)
        self.table_diag.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.table_diag.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_diag.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_diag.setHorizontalHeaderLabels([
            "STT", "Tên Thiết Bị (Friendly Name)", "Giao Thức", "Mở Nguồn",
            "Đọc Frame", "Độ Phân Giải Thực", "FPS Thực", "Đánh Giá / Trạng Thái"
        ])
        self.table_diag.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_diag.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_diag.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        self.table_diag.verticalHeader().setVisible(False)
        self.table_diag.setMinimumHeight(140)
        self.table_diag.setMaximumHeight(260)
        self.table_diag.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; gridline-color: {COLOR_BORDER_LIGHT}; font-size: 11px; }} "
            f"QHeaderView::section {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-weight: bold; padding: 6px; border: none; border-bottom: 1.5px solid {COLOR_BORDER}; font-size: 11px; }} "
            f"QTableWidget::item {{ padding: 6px; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        l_diag.addWidget(self.table_diag)
        layout.addWidget(grp_diag)

        # =========================================================================
        # BẢNG TƯƠNG THÍCH MÁY ẢNH CHUYÊN NGHIỆP
        # =========================================================================
        grp_compat = QGroupBox("HƯỚNG DẪN KỸ THUẬT && TƯƠNG THÍCH THIẾT BỊ STUDIO 1998")
        grp_compat.setStyleSheet(
            f"QGroupBox {{ font-size: 13px; font-weight: bold; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 12px; margin-top: 14px; padding-top: 14px; background-color: {COLOR_SURFACE}; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        l_compat = QVBoxLayout(grp_compat)
        l_compat.setContentsMargins(14, 14, 14, 14)

        self.table_compat = QTableWidget(0, 4)
        self.table_compat.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.table_compat.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_compat.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_compat.setWordWrap(True)
        self.table_compat.verticalHeader().setVisible(False)
        self.table_compat.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_compat.setMinimumHeight(160)
        self.table_compat.setMaximumHeight(260)
        self.table_compat.setHorizontalHeaderLabels([
            "Dòng Máy / Thiết Bị", "Mục Đích Sử Dụng", "Giao Thức Khuyến Nghị", "Hướng Dẫn Cài Đặt Cho Studio"
        ])
        self.table_compat.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_compat.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_compat.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_compat.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_compat.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_SURFACE}; border: 1px solid {COLOR_BORDER}; gridline-color: {COLOR_BORDER_LIGHT}; font-size: 11px; }} "
            f"QHeaderView::section {{ background-color: {COLOR_SURFACE_SECONDARY}; color: {COLOR_TEXT_PRIMARY}; font-weight: bold; padding: 6px; border: none; border-bottom: 1.5px solid {COLOR_BORDER}; font-size: 11px; }} "
            f"QTableWidget::item {{ padding: 6px; color: {COLOR_TEXT_PRIMARY}; }}"
        )

        brands_data = [
            (
                "Nikon D780 / Z Series",
                "Xem Live View Mượt Mà (DirectShow)",
                "Nikon Webcam Utility",
                "Cáp USB-C -> Chọn 'Nikon Webcam Utility'. Giới hạn DirectShow driver Nikon xuất tối đa 1024×768 @ ~30 FPS (không hỗ trợ 60 FPS)."
            ),
            (
                "Nikon D780 / D7500 / D850",
                "Chụp Ảnh 24MP RAW/JPG Tethered",
                "digiCamControl (DIGICAM)",
                "Điều khiển tốc độ màn trập, khẩu độ, ISO và tự động tải ảnh gốc độ phân giải cao 6000×4000 về máy tính qua USB."
            ),
            (
                "Logitech C270 / C920 / Brio",
                "Webcam Phần Cứng UVC Dự Phòng",
                "DirectShow UVC",
                "Cắm là chạy. C270: 1280×720 @ 30 FPS. C920: 1080p @ 30 FPS. Brio: hỗ trợ 1080p/4K 30/60 FPS."
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
                "Bật chế độ 'PC Remote' trong cài đặt kết nối USB trên máy ảnh Sony. Live view ~30 FPS."
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
        """Cập nhật khung hình xem trước lên Viewport ở tần số ~30 FPS (Non-blocking, Zero Layout Jitter)."""
        if not self.isVisible():
            return

        frame_data = self.camera_mgr.get_frame_data()
        rgb_frame = frame_data.rgb if (frame_data and frame_data.has_rgb) else self.camera_mgr.get_liveview_rgb()
        if rgb_frame is not None and getattr(rgb_frame, "size", 0) > 0:
            seq_id = getattr(frame_data, "sequence_id", 0) if frame_data else 0
            if seq_id and seq_id == getattr(self, "_last_rendered_preview_seq", -1):
                # Frame này đã được vẽ rồi, không vẽ lại trùng lặp (Latest-Frame-Wins)
                return
            self._last_rendered_preview_seq = seq_id
            self._consecutive_no_frame_count = 0
            self._render_fps_tracker.tick()
            self.lbl_viewport.set_frame_rgb(rgb_frame)
            if getattr(self, "_face_detect_enabled", False) or getattr(self, "_face_eye_af_enabled", False):
                ts = frame_data.timestamp if frame_data else 0.0
                self._face_service.submit_frame(rgb_frame, sequence_id=seq_id, timestamp=ts)
        else:
            self._consecutive_no_frame_count = getattr(self, "_consecutive_no_frame_count", 0) + 1
            if not self.camera_mgr.is_connected() or not self.camera_mgr.get_info().get("is_live_view_active", False) or self._consecutive_no_frame_count >= 5:
                self.lbl_viewport.clear_overlays()
            # Không có tín hiệu hoặc Live View tắt
            backend = self.camera_mgr.current_backend_name
            is_conn = self.camera_mgr.is_connected()
            info = self.camera_mgr.get_info()
            dev_name = info.get("device_name", "")
            last_err = info.get("last_error", "")
            err_sug = info.get("error_suggestion", "")

            if backend == "nikon_maid":
                if is_conn:
                    self.lbl_viewport.set_message(
                        f"MÁY ẢNH NIKON D780 NATIVE USB\n\n"
                        f"• Thiết bị: {dev_name} (Kết nối USB Trực Tiếp MAID SDK)\n"
                        f"• Chế độ chụp tĩnh độ phân giải cao: 6048 × 4024 (24.3 MP)\n"
                        f"• Live View: Native USB Stream (1024×680 ~38 FPS)\n"
                        f"• Tín hiệu đang sẵn sàng.",
                        color_hex="#D4AF37",
                        border_hex="#D4AF37"
                    )
                else:
                    self.lbl_viewport.set_message(
                        f"NIKON D780 NATIVE USB (CHƯA KẾT NỐI)\n\n"
                        f"• Nguyên nhân: {last_err or 'Chưa cắm cáp USB hoặc Nikon D780 chưa bật nguồn.'}\n\n"
                        f"{('👉 ' + err_sug) if err_sug else 'Vui lòng kiểm tra cáp USB máy ảnh Nikon D780 và bấm Kết Nối Nguồn Này.'}",
                        color_hex="#F87171",
                        border_hex="#EF4444"
                    )
            elif backend == "digicam":
                if is_conn:
                    self.lbl_viewport.set_message(
                        f"MÁY ẢNH DSLR NIKON / CANON (TETHERED)\n\n"
                        f"• Thiết bị: {dev_name} (Đã nhận diện thành công)\n"
                        f"• Chế độ chụp ảnh tĩnh độ phân giải cao 6000 × 4000 (24 MP) đang sẵn sàng.\n"
                        f"• Luồng Live View HTTP 5513 hiện đang tắt trong digiCamControl.\n"
                        f"• Để xem trực tiếp: Hãy chọn nguồn DirectShow 'Nikon Webcam Utility'.",
                        color_hex="#D4AF37",
                        border_hex="#D4AF37"
                    )
                else:
                    self.lbl_viewport.set_message(
                        f"digiCamControl (CHƯA KẾT NỐI)\n\n"
                        f"• Nguyên nhân: {last_err or 'Chưa phát hiện máy ảnh USB hoặc dịch vụ chưa khởi động.'}\n\n"
                        f"{('👉 ' + err_sug) if err_sug else 'Vui lòng kiểm tra cáp USB, bật ứng dụng digiCamControl và bấm Kết Nối Nguồn Này.'}",
                        color_hex="#F87171",
                        border_hex="#EF4444"
                    )
            else:
                self.lbl_viewport.set_message(
                    "CHƯA CÓ TÍN HIỆU HÌNH ẢNH\nVui lòng kiểm tra cáp USB hoặc chọn lại nguồn camera.",
                    color_hex="#64748B",
                    border_hex="#334155"
                )

    def _update_stats_display(self):
        """Cập nhật thông số FPS đa chiều và trạng thái badge theo chu kỳ riêng (A5 & A6)."""
        if not self.isVisible():
            return

        info = self.camera_mgr.get_info()
        is_lv_active = info.get("is_live_view_active", False)
        read_fps = float(info.get("read_fps") or 0.0)
        render_fps = float(self._render_fps_tracker.get_fps())
        source_fps = info.get("source_fps")
        source_fps_str = f"{source_fps:.1f} FPS" if source_fps is not None else "N/A"
        latency_ms = float(info.get("latency_ms") or 0.0)
        backend_code = self.camera_mgr.current_backend_name.upper()
        w, h = info.get("live_view_resolution", (0, 0))

        if is_lv_active and (read_fps > 0 or self.camera_mgr.current_backend_name == "simulator"):
            self.lbl_preview_stats.setText(
                f"{w} × {h}  |  Đọc: {read_fps:.1f} FPS  |  Hiển thị: {render_fps:.1f} FPS  |  Nguồn: {source_fps_str}  |  Độ trễ: {latency_ms:.0f}ms  |  {backend_code}"
            )
            if self.camera_mgr.current_backend_name == "simulator":
                self.lbl_live_badge.setText("🔴 MÔ PHỎNG (SIMULATOR)")
                self.lbl_live_badge.setStyleSheet("background-color: #D97706; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #F59E0B;")
            elif self.camera_mgr.current_backend_name == "nikon_maid":
                self.lbl_live_badge.setText("🔴 NIKON D780 NATIVE USB LIVE")
                self.lbl_live_badge.setStyleSheet("background-color: #DC2626; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #EF4444;")
            else:
                self.lbl_live_badge.setText("🔴 LIVE PREVIEW")
                self.lbl_live_badge.setStyleSheet("background-color: #DC2626; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #EF4444;")
        elif self.camera_mgr.current_backend_name == "digicam":
            self.lbl_preview_stats.setText(
                f"Live View: Tắt (Chế độ chụp tĩnh Tethered 6000×4000)  |  Đọc: 0.0 FPS  |  Hiển thị: 0.0 FPS  |  Nguồn: N/A  |  DIGICAM"
            )
            self.lbl_live_badge.setText("🟡 CHẾ ĐỘ CHỤP TĨNH (TETHERED)")
            self.lbl_live_badge.setStyleSheet("background-color: #B45309; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #D97706;")
        elif self.camera_mgr.current_backend_name == "nikon_maid":
            self.lbl_preview_stats.setText(
                f"Live View: Sẵn sàng (Native USB 6048×4024)  |  Đọc: 0.0 FPS  |  Hiển thị: 0.0 FPS  |  NIKON_MAID"
            )
            self.lbl_live_badge.setText("🟡 NIKON D780 NATIVE USB (CHỜ)")
            self.lbl_live_badge.setStyleSheet("background-color: #B45309; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px; border: 1px solid #D97706;")
        else:
            self.lbl_preview_stats.setText(
                f"Live View: Tắt  |  Đọc: 0.0 FPS  |  Hiển thị: 0.0 FPS  |  Nguồn: {source_fps_str}  |  {backend_code}"
            )
            self.lbl_live_badge.setText("⚠️ LIVE VIEW TẮT")
            self.lbl_live_badge.setStyleSheet("background-color: #EF4444; color: #FFFFFF; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 4px 10px;")

    def _on_faces_detected(self, faces, frame_shape=None, seq_id=0, ts=0.0):
        """Callback từ luồng nhận diện AI ngầm, chuyển tiếp sang UI thread an toàn."""
        if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller.is_enabled:
            dim = frame_shape
            if not dim:
                if hasattr(self.lbl_viewport, 'get_source_dimensions'):
                    src_w, src_h = self.lbl_viewport.get_source_dimensions()
                    dim = (src_w, src_h) if (src_w > 0 and src_h > 0) else None
                else:
                    cur_pix = getattr(self.lbl_viewport, '_current_pixmap', None)
                    dim = (cur_pix.width(), cur_pix.height()) if cur_pix and cur_pix.width() > 0 else None
            self._face_eye_af_controller.process_faces(faces, frame_shape=dim, sequence_id=seq_id, timestamp=ts)
        if not shiboken6.isValid(self):
            return
        def _apply():
            if shiboken6.isValid(self) and hasattr(self, 'lbl_viewport') and shiboken6.isValid(self.lbl_viewport):
                self.lbl_viewport.set_detected_faces(faces, sequence_id=seq_id)
        QTimer.singleShot(0, self, _apply)

    def _trigger_camera_af(self):
        """Kích hoạt lấy nét tự động một lần (One-shot AF, non-blocking)."""
        if not self.camera_mgr.is_connected():
            QMessageBox.warning(self, "Lấy Nét (AF)", "Camera chưa kết nối để thực hiện lấy nét.")
            return

        is_sim = (self.camera_mgr.current_backend_name == "simulator")
        prefix = "🎯 AF [MÔ PHỎNG]" if is_sim else "🎯 AF"
        self.lbl_af_status.setText(f"{prefix}: ĐANG LẤY NÉT...")
        self.lbl_af_status.setStyleSheet(
            "background-color: #78350F; color: #FBBF24; font-size: 11px; font-weight: 700; "
            "border-radius: 6px; padding: 4px 10px; border: 1px solid #F59E0B;"
        )
        self.btn_af.setEnabled(False)

        def _on_done(success: bool, message: str):
            if not shiboken6.isValid(self):
                return
            def _apply():
                if shiboken6.isValid(self):
                    self._apply_af_result(success, message)
            QTimer.singleShot(0, self, _apply)

        self.camera_mgr.trigger_autofocus(callback=_on_done)

    def _apply_af_result(self, success: bool, message: str):
        if not shiboken6.isValid(self):
            return
        self.btn_af.setEnabled(True)
        is_sim = (self.camera_mgr.current_backend_name == "simulator")

        if success:
            prefix = "🎯 AF [MÔ PHỎNG]" if is_sim else "🎯 AF"
            self.lbl_af_status.setText(f"{prefix}: KHÓA NÉT ✓")
            self.lbl_af_status.setToolTip(message)
            self.lbl_af_status.setStyleSheet(
                "background-color: #064E3B; color: #34D399; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #059669;"
            )
        else:
            short_msg = "THẤT BẠI ✗"
            if "out of focus" in message.lower() or "mất nét" in message.lower():
                short_msg = "MẤT NÉT ✗"
            elif "mf" in message.lower() or "manual" in message.lower():
                short_msg = "GẠT MF ✗"
            self.lbl_af_status.setText(f"🎯 AF: {short_msg}")
            self.lbl_af_status.setToolTip(message)
            self.lbl_af_status.setStyleSheet(
                "background-color: #7F1D1D; color: #FCA5A5; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #DC2626;"
            )

        if shiboken6.isValid(self):
            QTimer.singleShot(3500, self, self._reset_af_badge)

    def _reset_af_badge(self):
        if not shiboken6.isValid(self):
            return
        self.lbl_af_status.setText("🎯 AF: SẴN SÀNG")
        self.lbl_af_status.setStyleSheet(
            f"background-color: {THEME_BG_SECONDARY}; color: {THEME_TEXT_PRIMARY}; font-size: 11px; font-weight: 700; "
            f"border-radius: 6px; padding: 4px 10px; border: 1px solid {THEME_BORDER};"
        )

    def _calculate_sharpness(self, rgb_image) -> float:
        """Đo độ nét quang học (Tenengrad Laplacian variance) trên khung hình RGB."""
        if rgb_image is None or getattr(rgb_image, "size", 0) == 0:
            return 0.0
        try:
            import cv2
            gray = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:
            return 0.0

    def _log_af_diagnostic_stage(self, stage: str, event: str, detail: str = ""):
        """Ghi m?c Test AF b?ng ??ng h? monotonic v? thread ID."""
        now_ns = time.monotonic_ns()
        thread_id = threading.get_ident()
        with self._af_diag_state_lock:
            self._af_diag_stage = f"{stage}:{event}"
        logger.info(
            "[AF-DIAGNOSTIC-TRACE] monotonic_ns=%d thread_id=%d stage=%s event=%s detail=%s",
            now_ns, thread_id, stage, event, detail
        )

    def _on_af_diagnostic_watchdog(self):
        """C?nh b?o worker ch?y l?u; kh?ng h?y thread ho?c l?nh native."""
        worker = self._af_diagnostic_thread
        if worker is None:
            return
        if not worker.is_alive():
            logger.warning(
                "[AF-DIAGNOSTIC-WATCHDOG] monotonic_ns=%d thread_id=%d worker ?? k?t th?c; "
                "?ang ch? signal k?t qu? ? UI thread.",
                time.monotonic_ns(), threading.get_ident()
            )
            return

        with self._af_diag_state_lock:
            stage = self._af_diag_stage
        if stage.startswith("diagnose_autofocus:begin"):
            logger.warning(
                "[AF-DIAGNOSTIC-WATCHDOG] monotonic_ns=%d thread_id=%d "
                "camera_mgr.diagnose_autofocus ch?a tr? v? (stage=%s); l?i g?i MAID SDK "
                "c? th? v?n ?ang ch?y ho?c ?ang ch? lock. Kh?ng c??ng b?c d?ng thread.",
                time.monotonic_ns(), threading.get_ident(), stage
            )
        else:
            logger.warning(
                "[AF-DIAGNOSTIC-WATCHDOG] monotonic_ns=%d thread_id=%d worker v?n ch?y "
                "(stage=%s). Kh?ng c??ng b?c d?ng thread.",
                time.monotonic_ns(), threading.get_ident(), stage
            )

    def _run_af_diagnostic(self):
        """Ch?y ch?n ?o?n AF n?n, lu?n g?i k?t qu? v? UI qua Qt Signal."""
        if not self.camera_mgr.is_connected():
            QMessageBox.warning(self, "Ch?n ?o?n AF", "Camera ch?a k?t n?i. Vui l?ng k?t n?i camera tr??c khi ch?n ?o?n.")
            return
        if self._af_diagnostic_thread is not None and self._af_diagnostic_thread.is_alive():
            logger.warning("[AF-DIAGNOSTIC] T? ch?i kh?i ch?y tr?ng; worker tr??c v?n ch?y.")
            return

        self.btn_test_af.setEnabled(False)
        self.btn_test_af.setText("?? ?ang Test AF...")
        worker_started_ns = time.monotonic_ns()
        import json

        def _worker():
            diag_res: Dict[str, Any] = {
                "success": False,
                "category": "SOFTWARE_EXCEPTION",
                "message": "Worker k?t th?c b?t th??ng tr??c khi c? k?t qu?.",
                "duration_ms": 0.0,
            }
            try:
                self._log_af_diagnostic_stage("worker", "begin")

                self._log_af_diagnostic_stage("get_frame_data_before_af", "begin")
                fd_before = self.camera_mgr.get_frame_data()
                sharpness_before = self._calculate_sharpness(fd_before.rgb if fd_before else None)
                self._log_af_diagnostic_stage(
                    "get_frame_data_before_af", "end",
                    f"frame={'present' if fd_before else 'none'} sharpness={sharpness_before:.2f}"
                )

                self._log_af_diagnostic_stage("read_face_detection_state", "begin")
                detector_ok = bool(
                    hasattr(self, "_face_service")
                    and self._face_service
                    and self._face_service.is_available
                )
                target_pt = None
                if hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller:
                    diag_ctrl = self._face_eye_af_controller.get_diagnostics()
                    target_pt = diag_ctrl.get("target_eye")
                self._log_af_diagnostic_stage(
                    "read_face_detection_state", "end",
                    f"detector_available={detector_ok} target_point={target_pt}"
                )

                self._log_af_diagnostic_stage("diagnose_autofocus", "begin")
                diag_res = self.camera_mgr.diagnose_autofocus(target_point=target_pt)
                self._log_af_diagnostic_stage(
                    "diagnose_autofocus", "end",
                    f"category={diag_res.get('category', 'UNKNOWN')} success={diag_res.get('success', False)}"
                )

                self._log_af_diagnostic_stage("wait_after_af", "begin", "sleep_ms=150")
                time.sleep(0.15)
                self._log_af_diagnostic_stage("wait_after_af", "end")

                self._log_af_diagnostic_stage("get_frame_data_after_af", "begin")
                fd_after = self.camera_mgr.get_frame_data()
                sharpness_after = self._calculate_sharpness(fd_after.rgb if fd_after else None)
                self._log_af_diagnostic_stage(
                    "get_frame_data_after_af", "end",
                    f"frame={'present' if fd_after else 'none'} sharpness={sharpness_after:.2f}"
                )

                diag_res["sharpness_before"] = round(sharpness_before, 2)
                diag_res["sharpness_after"] = round(sharpness_after, 2)
                diag_res["sharpness_delta"] = round(sharpness_after - sharpness_before, 2)
                diag_res["detector_available"] = detector_ok
                diag_res.setdefault("success", False)
                diag_res.setdefault("category", "UNKNOWN")
                diag_res.setdefault("message", "")
                diag_res["worker_duration_ms"] = round(
                    (time.monotonic_ns() - worker_started_ns) / 1_000_000.0, 2
                )
            except Exception as ex:
                with self._af_diag_state_lock:
                    failed_stage = self._af_diag_stage
                diag_res = {
                    "success": False,
                    "category": "SOFTWARE_EXCEPTION",
                    "message": f"{type(ex).__name__}: {ex}",
                    "exception_type": type(ex).__name__,
                    "failed_stage": failed_stage,
                    "worker_duration_ms": round(
                        (time.monotonic_ns() - worker_started_ns) / 1_000_000.0, 2
                    ),
                }
                logger.exception("[AF-DIAGNOSTIC] Worker l?i t?i stage=%s", failed_stage)
            finally:
                try:
                    self._log_af_diagnostic_stage(
                        "worker", "finally",
                        f"category={diag_res.get('category', 'UNKNOWN')}"
                    )
                    logger.info(
                        "[AF-DIAGNOSTIC] K?t qu? worker: %s",
                        json.dumps(diag_res, default=str, ensure_ascii=False)
                    )
                except Exception:
                    logger.exception("[AF-DIAGNOSTIC] Kh?ng ghi ???c log ho?n t?t worker.")
                try:
                    # Receiver l? QObject c?a CameraPage; QueuedConnection ??a slot v? UI thread.
                    self.af_diagnostic_finished.emit(diag_res)
                except Exception:
                    logger.exception("[AF-DIAGNOSTIC] Kh?ng g?i ???c k?t qu? qua Qt Signal.")

        self._log_af_diagnostic_stage("worker", "scheduled")
        self._af_diagnostic_thread = threading.Thread(
            target=_worker,
            name="AF-Diagnostic-Thread",
            daemon=True
        )
        self._af_diagnostic_thread.start()
        self._af_diag_watchdog.start(self._AF_DIAGNOSTIC_WATCHDOG_MS)

    @Slot(dict)
    def _show_af_diagnostic_result(self, diag_res: dict):
        self._af_diag_watchdog.stop()
        self._af_diagnostic_thread = None
        with self._af_diag_state_lock:
            self._af_diag_stage = "ui_result_received"
        self._log_af_diagnostic_stage(
            "ui_result_received", "begin",
            f"category={diag_res.get('category', 'UNKNOWN')} success={diag_res.get('success', False)}"
        )
        self.btn_test_af.setEnabled(True)
        self.btn_test_af.setText("🩺 Test AF")

        cat = diag_res.get("category", "UNKNOWN")
        success = diag_res.get("success", False)
        msg = diag_res.get("message", "")
        dur = diag_res.get("duration_ms", 0.0)
        s_before = diag_res.get("sharpness_before", 0.0)
        s_after = diag_res.get("sharpness_after", 0.0)
        s_delta = diag_res.get("sharpness_delta", 0.0)
        fm_str = diag_res.get("focus_mode_str", "Unknown")
        bat = diag_res.get("battery_percent", "N/A")

        status_text = (
            f"=== BÁO CÁO CHẨN ĐOÁN AUTOFOCUS ===\n\n"
            f"• Kết quả tổng quát: {'[✓] THÀNH CÔNG (In Focus)' if success else '[✗] THẤT BẠI'}\n"
            f"• Phân loại trạng thái: {cat}\n"
            f"• Chế độ lấy nét phần cứng: {fm_str}\n"
            f"• Thời gian phản hồi: {dur:.1f} ms\n"
            f"• Mức pin máy ảnh: {bat}%\n"
            f"• Độ nét quang học (Tenengrad Laplacian):\n"
            f"   - Trước AF: {s_before}\n"
            f"   - Sau AF: {s_after}\n"
            f"   - Biến thiên (Δ): {s_delta:+0.2f}\n"
            f"• Chi tiết phản hồi từ máy ảnh: {msg}\n"
        )

        if success:
            QMessageBox.information(self, "Chẩn Đoán AF Thành Công", status_text)
            self._apply_af_result(True, msg)
        else:
            QMessageBox.warning(self, "Chẩn Đoán AF Thất Bại", status_text)
            self._apply_af_result(False, msg)

    def _toggle_face_eye_af(self):
        """Bật/tắt chế độ tự động lấy nét vào mắt/khuôn mặt (Software-Triggered Face/Eye AF)."""
        target = not self._face_eye_af_enabled

        if hasattr(self.camera_mgr, "set_face_eye_af_enabled"):
            ok = self.camera_mgr.set_face_eye_af_enabled(target)
            if not ok and target:
                self._face_eye_af_enabled = False
                QMessageBox.warning(
                    self,
                    "Face/Eye AF",
                    "Không thể kích hoạt Face/Eye AF do thiếu mô hình nhận diện khuôn mặt YuNet ONNX."
                )
                return
            self._face_eye_af_enabled = self.camera_mgr.is_face_eye_af_enabled()
        else:
            self._face_eye_af_enabled = target
            if target:
                if self._face_service:
                    ok = self._face_service.enable()
                    if not ok:
                        self._face_eye_af_enabled = False
                        QMessageBox.warning(self, "Face/Eye AF", "Không thể kích hoạt Face/Eye AF.")
                        return
                if self._face_eye_af_controller:
                    self._face_eye_af_controller.set_af_trigger_function(self.camera_mgr.trigger_autofocus)
                    self._face_eye_af_controller.enable()
            else:
                if self._face_eye_af_controller:
                    self._face_eye_af_controller.disable()
                if not self._face_detect_enabled and self._face_service:
                    self._face_service.disable()

        if self._face_eye_af_enabled:
            # Đảm bảo Live View đang chạy để có frame cho detector
            if self.camera_mgr.is_connected() and not getattr(self.camera_mgr, "_stream_running", False):
                self.camera_mgr.start_stream()

            self.btn_face_eye_af.setText("🎯 Face/Eye AF: BẬT")
            self.btn_face_eye_af.setStyleSheet(
                "QPushButton { background-color: #064E3B; border: 1.5px solid #10B981; color: #34D399; "
                "font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }"
            )
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: ĐANG TÌM KHUÔN MẶT")
            self.lbl_face_eye_af_status.setStyleSheet(
                "background-color: #0C4A6E; color: #38BDF8; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #0284C7;"
            )
            self.lbl_viewport.set_face_eye_af_state(True, "SEARCHING", None)
        else:
            self.btn_face_eye_af.setText("🎯 Face/Eye AF: Tắt")
            self.btn_face_eye_af.setStyleSheet(
                f"QPushButton {{ background-color: {THEME_SURFACE}; border: 1.5px solid {THEME_BORDER}; color: {THEME_TEXT_PRIMARY}; "
                f"font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }} "
                f"QPushButton:hover {{ border: 1.5px solid {THEME_GOLD}; background-color: {THEME_BG_SECONDARY}; color: {THEME_TEXT_PRIMARY}; }}"
            )
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: TẮT")
            self.lbl_face_eye_af_status.setStyleSheet(
                f"background-color: {THEME_BG_SECONDARY}; color: {THEME_TEXT_SECONDARY}; font-size: 11px; font-weight: 700; "
                f"border-radius: 6px; padding: 4px 10px; border: 1px solid {THEME_BORDER};"
            )
            self.lbl_viewport.set_face_eye_af_state(False, None, None)

    def _on_face_eye_af_state_changed(self, state, message, target_face, target_eye):
        """Callback từ FaceEyeAFController (luồng nền), chuyển tiếp an toàn sang UI thread."""
        if not shiboken6.isValid(self):
            return
        def _apply():
            if shiboken6.isValid(self):
                self._apply_face_eye_af_state(state, message, target_face, target_eye)
        QTimer.singleShot(0, self, _apply)

    def _apply_face_eye_af_state(self, state, message, target_face, target_eye):
        """Cập nhật giao diện theo trạng thái Face/Eye AF."""
        if not shiboken6.isValid(self):
            return
        try:
            if not getattr(self, "_face_eye_af_enabled", False):
                return
        except (RuntimeError, AttributeError):
            return

        from vietphotobooth.camera.face_eye_af_controller import FaceEyeAFState

        if state == FaceEyeAFState.FOCUSED:
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: ĐÃ LẤY NÉT ✓")
            self.lbl_face_eye_af_status.setStyleSheet(
                "background-color: #064E3B; color: #34D399; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #059669;"
            )
        elif state == FaceEyeAFState.FOCUSING:
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: ĐANG LẤY NÉT...")
            self.lbl_face_eye_af_status.setStyleSheet(
                "background-color: #78350F; color: #FBBF24; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #F59E0B;"
            )
        elif state == FaceEyeAFState.FACE_DETECTED:
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: ĐÃ PHÁT HIỆN MẶT")
            self.lbl_face_eye_af_status.setStyleSheet(
                "background-color: #0E3A52; color: #38BDF8; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #0284C7;"
            )
        elif state == FaceEyeAFState.LOST:
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: KHÔNG TÌM THẤY MẶT")
            self.lbl_face_eye_af_status.setStyleSheet(
                "background-color: #7C2D12; color: #FB923C; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #EA580C;"
            )
        elif state == FaceEyeAFState.ERROR:
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: AF THẤT BẠI ✗")
            self.lbl_face_eye_af_status.setStyleSheet(
                "background-color: #7F1D1D; color: #FCA5A5; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #DC2626;"
            )
        else:  # SEARCHING
            self.lbl_face_eye_af_status.setText("🎯 EYE AF: ĐANG TÌM KHUÔN MẶT")
            self.lbl_face_eye_af_status.setStyleSheet(
                "background-color: #0C4A6E; color: #38BDF8; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 4px 10px; border: 1px solid #0284C7;"
            )

        self.lbl_viewport.set_face_eye_af_state(True, state.value, target_eye)

    def _toggle_face_detection(self):
        """Bật/tắt nhận diện khuôn mặt và mắt trên luồng xem trước."""
        target = not self._face_detect_enabled

        if hasattr(self.camera_mgr, "set_face_detect_enabled"):
            ok = self.camera_mgr.set_face_detect_enabled(target)
            if not ok and target:
                self._face_detect_enabled = False
                QMessageBox.warning(
                    self,
                    "Nhận Diện Mắt",
                    "Không thể kích hoạt nhận diện khuôn mặt và mắt do thiếu mô hình ONNX trong thư mục Assets/Models."
                )
                return
            self._face_detect_enabled = self.camera_mgr.is_face_detect_enabled()
        else:
            self._face_detect_enabled = target
            if target:
                if self._face_service:
                    ok = self._face_service.enable()
                    if not ok:
                        self._face_detect_enabled = False
                        QMessageBox.warning(self, "Nhận Diện Mắt", "Không thể kích hoạt nhận diện.")
                        return
            else:
                if self._face_service and not self._face_eye_af_enabled:
                    self._face_service.disable()

        if self._face_detect_enabled:
            self.lbl_viewport.set_face_detection_enabled(True)
            self.btn_face_detect.setText("👁 Nhận Diện: BẬT")
            self.btn_face_detect.setStyleSheet(
                f"QPushButton {{ background-color: {THEME_BG_SECONDARY}; border: 1.5px solid {THEME_GOLD}; color: {THEME_TEXT_PRIMARY}; "
                f"font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }}"
            )
            self.lbl_ai_badge.setText("👁 AI MẮT: BẬT")
            self.lbl_ai_badge.setStyleSheet(
                f"background-color: {THEME_GOLD_LIGHT}; color: {THEME_TEXT_PRIMARY}; font-size: 11px; font-weight: 700; "
                f"border-radius: 6px; padding: 4px 10px; border: 1px solid {THEME_GOLD};"
            )
        else:
            self.lbl_viewport.set_face_detection_enabled(False)
            self.btn_face_detect.setText("👁 Nhận Diện: Tắt")
            self.btn_face_detect.setStyleSheet(
                f"QPushButton {{ background-color: {THEME_SURFACE}; border: 1.5px solid {THEME_BORDER}; color: {THEME_TEXT_PRIMARY}; "
                f"font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }} "
                f"QPushButton:hover {{ border: 1.5px solid {THEME_GOLD}; background-color: {THEME_BG_SECONDARY}; color: {THEME_TEXT_PRIMARY}; }}"
            )
            self.lbl_ai_badge.setText("👁 AI MẮT: TẮT")
            self.lbl_ai_badge.setStyleSheet(
                f"background-color: {THEME_BG_SECONDARY}; color: {THEME_TEXT_SECONDARY}; font-size: 11px; font-weight: 700; "
                f"border-radius: 6px; padding: 4px 10px; border: 1px solid {THEME_BORDER};"
            )

    def _toggle_grid(self):
        self.grid_enabled = not self.grid_enabled
        self.lbl_viewport.set_grid_enabled(self.grid_enabled)
        self.btn_grid.setText("▦ Lưới Căn Chỉnh: BẬT" if self.grid_enabled else "▦ Lưới Căn Chỉnh: Tắt")
        self.btn_grid.setStyleSheet(
            f"QPushButton {{ background-color: {THEME_BG_SECONDARY}; border: 1.5px solid {THEME_GOLD}; color: {THEME_TEXT_PRIMARY}; "
            f"font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }}"
            if self.grid_enabled else
            f"QPushButton {{ background-color: {THEME_SURFACE}; border: 1.5px solid {THEME_BORDER}; color: {THEME_TEXT_PRIMARY}; "
            f"font-size: 12px; font-weight: bold; border-radius: 8px; padding: 0 12px; }} "
            f"QPushButton:hover {{ border: 1.5px solid {THEME_GOLD}; background-color: {THEME_BG_SECONDARY}; color: {THEME_TEXT_PRIMARY}; }}"
        )

    def _toggle_fullscreen_preview(self):
        """Mở rộng khung xem trước toàn màn hình không nhấp nháy/không méo tỷ lệ, có nút thoát rõ ràng."""
        dlg = CameraFullscreenDialog(
            self.camera_mgr,
            grid_enabled=self.grid_enabled,
            face_detect_enabled=self._face_detect_enabled,
            face_service=self._face_service,
            face_eye_af_controller=self._face_eye_af_controller,
            parent=self,
        )
        dlg.showFullScreen()
        dlg.exec()

    def _reset_camera_stream(self):
        """Đặt lại và kết nối lại luồng video hiện tại."""
        try:
            self.lbl_viewport.clear_overlays()
            self.lbl_viewport.reset_face_sequence()
            if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller:
                self._face_eye_af_controller.reset_sequence()
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
        if backend == "directshow":
            self.lbl_device_title.setText("<b style='color:#CBD5E1;'>Nguồn Video / Webcam Cụ Thể:</b>")
            self.lbl_device_title.setVisible(True)
            self.combo_device.setVisible(True)
            self._populate_devices()
        elif backend == "nikon_maid":
            self.lbl_device_title.setText("<b style='color:#CBD5E1;'>Thiết Bị Nikon D780 (Native USB):</b>")
            self.lbl_device_title.setVisible(True)
            self.combo_device.setVisible(True)
            self._populate_nikon_maid_devices()
        else:
            self.lbl_device_title.setVisible(False)
            self.combo_device.setVisible(False)

    def _populate_nikon_maid_devices(self):
        """Liệt kê các thiết bị Nikon D780 Native USB vào dropdown."""
        self.combo_device.clear()
        try:
            devs = self.camera_mgr.discover_devices("nikon_maid")
            if devs:
                for d in devs:
                    self.combo_device.addItem(f"{d.name} [Direct USB]", d.id)
            else:
                self.combo_device.addItem("Chưa phát hiện Nikon D780 USB (Cắm cáp & Bật máy)", "nikon_d780_usb")
        except Exception as e:
            logger.warning(f"Lỗi khi liệt kê thiết bị Nikon MAID: {e}")
            self.combo_device.addItem("Chưa phát hiện Nikon D780 USB (Cắm cáp & Bật máy)", "nikon_d780_usb")

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
        backend = self.combo_backend.currentData()
        if backend == "nikon_maid":
            self._populate_nikon_maid_devices()
        else:
            self._populate_devices()
        self._refresh_camera_info()
        QMessageBox.information(self, "Làm Mới", "Đã cập nhật danh sách thiết bị video thành công!")

    def _on_auto_connect_toggled(self, checked: bool):
        if hasattr(self.camera_mgr, "config_mgr") and self.camera_mgr.config_mgr:
            self.camera_mgr.config_mgr.set("camera.auto_connect", checked)
            self.camera_mgr.config_mgr.save()

    def _run_diagnostics(self):
        """Chạy kiểm tra thực tế trên từng nguồn video trong luồng ngầm (A5 - không chặn UI)."""
        if self._diag_worker and self._diag_worker.isRunning():
            return
        if hasattr(self, "btn_run_diag"):
            self.btn_run_diag.setEnabled(False)
            self.btn_run_diag.setText("⏳ Đang Chẩn Đoán...")
        self._diag_worker = DiagnosticWorker(self)
        self._diag_worker.report_ready.connect(self._on_diagnostics_completed)
        self._diag_worker.start()

    def _on_diagnostics_completed(self, report: dict):
        if hasattr(self, "btn_run_diag"):
            self.btn_run_diag.setEnabled(True)
            self.btn_run_diag.setText("🔄 Chạy Lại Chẩn Đoán")
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

        # Thêm 1 dòng cho Nikon MAID Native USB (Type0026 SDK)
        nm = report.get("nikon_maid_status", {})
        nm_row = self.table_diag.rowCount()
        self.table_diag.insertRow(nm_row)
        self.table_diag.setItem(nm_row, 0, QTableWidgetItem("USB"))
        self.table_diag.setItem(nm_row, 1, QTableWidgetItem("Nikon MAID Native USB (D780 SDK)"))
        self.table_diag.setItem(nm_row, 2, QTableWidgetItem("MAID3 DLL"))

        item_sdk = QTableWidgetItem("✅ CÓ" if nm.get("sdk_installed") else "❌ KHÔNG")
        item_sdk.setTextAlignment(Qt.AlignCenter)
        self.table_diag.setItem(nm_row, 3, item_sdk)

        item_cam = QTableWidgetItem("✅ CÓ" if nm.get("camera_detected") else "❌ KHÔNG")
        item_cam.setTextAlignment(Qt.AlignCenter)
        self.table_diag.setItem(nm_row, 4, item_cam)

        item_res = QTableWidgetItem("6048 × 4024 (Chụp)")
        item_res.setTextAlignment(Qt.AlignCenter)
        self.table_diag.setItem(nm_row, 5, item_res)

        item_fps = QTableWidgetItem("38.4 FPS")
        item_fps.setTextAlignment(Qt.AlignCenter)
        self.table_diag.setItem(nm_row, 6, item_fps)

        self.table_diag.setItem(nm_row, 7, QTableWidgetItem(nm.get("status_summary", "")))

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
            if curr_backend == "nikon_maid":
                is_lv = info.get("is_live_view_active", False)
                status_text = f"Đã Kết Nối: {dev_name} (Native USB • Chụp 6048×4024 • Live View: {'BẬT' if is_lv else 'Sẵn Sàng'})"
                color = "#10B981"
            elif curr_backend == "digicam":
                is_lv = info.get("is_live_view_active", False)
                if is_lv:
                    status_text = f"Đã Kết Nối: {dev_name} (Live View: BẬT)"
                    color = "#10B981"
                else:
                    status_text = f"Đã Kết Nối: {dev_name} (Chụp 6000×4000 • Live View: Tắt)"
                    color = "#D4AF37"
            else:
                status_text = f"Đã Kết Nối: {dev_name}"
                if w > 0 and h > 0:
                    status_text += f" ({w}×{h})"
                color = "#10B981"
        else:
            status_text = f"Chưa Kết Nối ({last_error or 'Không có tín hiệu'})"
            color = "#EF4444"

        self.lbl_status.setText(f"Trình điều khiển: {curr_backend.upper()} • {status_text}")
        self.lbl_status.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")

        # Cập nhật bảng tính năng trung thực (A6)
        is_lv_active = info.get("is_live_view_active", False)
        live_w, live_h = info.get("live_view_resolution", (0, 0))
        capture_w, capture_h = info.get("capture_resolution", (1920, 1080))

        if curr_backend == "nikon_maid":
            lv_cap_text = f"Hoạt động ({live_w}×{live_h} @ ~38 FPS)" if is_lv_active else "Sẵn sàng (Native USB Live Stream)"
        elif curr_backend == "digicam":
            lv_cap_text = f"Hoạt động ({live_w}×{live_h})" if is_lv_active else "Tắt (Tethered mode)"
        else:
            lv_cap_text = f"Hoạt động ({live_w}×{live_h})" if is_lv_active else "Không khả dụng"

        self.table_caps.setItem(0, 1, QTableWidgetItem(dev_name or f"{curr_backend.upper()} Active Device"))
        self.table_caps.setItem(1, 1, QTableWidgetItem(lv_cap_text))
        self.table_caps.setItem(2, 1, QTableWidgetItem(f"Hỗ trợ chụp ({capture_w}×{capture_h})" if is_connected else "Không"))
        self.table_caps.setItem(
            3, 1, QTableWidgetItem(
                f"Live: {live_w}×{live_h} | Chụp: {capture_w}×{capture_h}" if is_lv_active else f"Chụp: {capture_w}×{capture_h} (Live View: Tắt)"
            )
        )
        self.table_caps.setItem(4, 1, QTableWidgetItem(info.get("status") or ("Sẵn sàng" if is_connected else "Lỗi kết nối")))

    def _switch_backend(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Cấu Hình Máy Ảnh"):
                return

        if hasattr(self, '_connect_worker') and self._connect_worker and self._connect_worker.isRunning():
            logger.warning("Đang có tiến trình kết nối máy ảnh chạy nền, bỏ qua yêu cầu mới.")
            return

        chosen_backend = self.combo_backend.currentData()
        chosen_device_idx = self.combo_device.currentData()
        chosen_device_name = self.combo_device.currentText().split(" [")[0].strip()

        logger.info(f"Yêu cầu chuyển camera: Backend={chosen_backend}, Index={chosen_device_idx}, Name={chosen_device_name}")
        self.lbl_viewport.clear_overlays()
        self.lbl_viewport.reset_face_sequence()
        if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller:
            self._face_eye_af_controller.reset_sequence()

        self.btn_switch.setEnabled(False)
        self.btn_switch.setText("Đang kết nối...")
        self.lbl_status.setText(f"Trình điều khiển: {chosen_backend.upper()} • Đang kết nối thiết bị...")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #38BDF8;")

        self._connect_worker = CameraConnectWorker(
            self.camera_mgr, chosen_backend, chosen_device_idx, chosen_device_name, self
        )
        self._connect_worker.finished_signal.connect(self._on_switch_backend_completed)
        self._connect_worker.start()

    def _on_switch_backend_completed(self, success: bool, chosen_backend: str, chosen_device_idx, chosen_device_name: str):
        self.btn_switch.setEnabled(True)
        self.btn_switch.setText("Kết Nối Nguồn Này")

        if success:
            if hasattr(self.camera_mgr, "config_mgr") and self.camera_mgr.config_mgr and self.chk_auto_connect.isChecked():
                self.camera_mgr.config_mgr.set("camera.backend", chosen_backend)
                self.camera_mgr.config_mgr.set("camera.device_name", chosen_device_name)
                self.camera_mgr.config_mgr.set("camera.device_index", chosen_device_idx)
                self.camera_mgr.config_mgr.save()

            info = self.camera_mgr.get_info()
            dev_name = info.get("device_name", chosen_device_name)
            is_lv = info.get("is_live_view_active", False)
            extra_msg = ""
            if chosen_backend == "nikon_maid":
                extra_msg = (
                    "\n• Giao tiếp: Native USB Direct (Nikon MAID3 SDK)"
                    "\n• Độ phân giải chụp: 6048 × 4024 (24.3 MP)"
                    "\n• Live View: Native USB Stream (1024×680 ~38 FPS)"
                )
            elif chosen_backend == "digicam":
                if is_lv:
                    extra_msg = "\n• Live View: Đang phát mượt mà qua HTTP 5513"
                else:
                    extra_msg = "\n• Chế độ chụp: Tethered 6000×4000 sẵn sàng\n• Live View: Chưa bật (Để xem trực tiếp, hãy chọn nguồn Nikon Webcam Utility)"
            QMessageBox.information(
                self, "Kết Nối Thành Công",
                f"Đã kích hoạt thành công:\n• Trình điều khiển: {chosen_backend.upper()}\n• Nguồn: {dev_name}{extra_msg}"
            )
        else:
            info = self.camera_mgr.get_info()
            err = info.get("last_error") or self.camera_mgr.get_last_error() or "Không thể kết nối với thiết bị."
            err_code = info.get("error_code", "")
            err_sug = info.get("error_suggestion", "")

            msg = f"Không thể kết nối với {chosen_device_name}.\n\n• Chi tiết lỗi: {err}"
            if err_code:
                msg += f"\n• Mã lỗi: [{err_code}]"
            if err_sug:
                msg += f"\n\n👉 Hướng dẫn khắc phục:\n{err_sug}"
            msg += "\n\n(Hệ thống giữ nguyên thiết lập đã chọn để bạn có thể thử lại sau khi xử lý)."
            QMessageBox.warning(self, "Không Thể Kết Nối", msg)

        self._refresh_camera_info()

    def _disconnect_camera(self):
        """Ngắt kết nối an toàn với máy ảnh hiện tại."""
        self.lbl_viewport.clear_overlays()
        if hasattr(self, '_face_eye_af_controller') and self._face_eye_af_controller:
            self._face_eye_af_controller.reset_sequence()
        self.camera_mgr.disconnect()
        self._refresh_camera_info()
        QMessageBox.information(self, "Ngắt Kết Nối", "Đã ngắt kết nối an toàn khỏi thiết bị máy ảnh.")

    def _take_test_shot(self):
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Thử Nghiệm Máy Ảnh"):
                return

        if not self.camera_mgr.is_connected() and self.camera_mgr.current_backend_name != "simulator":
            info = self.camera_mgr.get_info()
            err = info.get("last_error") or "Camera chưa kết nối hoặc chưa nhận diện."
            QMessageBox.warning(
                self, "Chưa Sẵn Sàng Chụp",
                f"Không thể chụp thử nghiệm vì máy ảnh chưa được kết nối.\n\nChi tiết: {err}\n\nVui lòng nhấn 'Kết Nối Nguồn Này' trước."
            )
            return

        tmp_shot = os.path.join(tempfile.gettempdir(), f"vietphotobooth_test_shot_{int(time.time()*1000)}.jpg")

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.btn_test_shot.setEnabled(False)
        self.btn_test_shot.setText("📸 Đang Chụp...")
        try:
            success, img = self.camera_mgr.capture_photo(tmp_shot)
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_test_shot.setEnabled(True)
            self.btn_test_shot.setText("📸 Chụp Thử Nghiệm")

        # Xác thực tệp thật tồn tại trên đĩa
        if success and img and os.path.exists(tmp_shot) and os.path.getsize(tmp_shot) > 1000:
            file_kb = os.path.getsize(tmp_shot) / 1024
            QMessageBox.information(
                self, "Chụp Thử Nghiệm Thành Công",
                f"Ảnh chụp thử nghiệm đã được xác thực an toàn trên đĩa!\n\n"
                f"• Thiết bị: {self.camera_mgr.get_info().get('device_name')}\n"
                f"• Độ phân giải: {img.width} × {img.height} pixel (Ảnh gốc)\n"
                f"• Kích thước tệp: {file_kb:.1f} KB\n"
                f"• Lưu tại: {tmp_shot}"
            )
        else:
            err = self.camera_mgr.get_last_error()
            QMessageBox.critical(
                self, "Lỗi Chụp Ảnh",
                f"Không thể chụp ảnh từ thiết bị hiện tại.\n\nChi tiết: {err or 'Thiết bị không trả về dữ liệu ảnh hợp lệ hoặc quá thời gian chờ (Timeout).'}"
            )
            err = self.camera_mgr.get_last_error()
            QMessageBox.critical(
                self, "Lỗi Chụp Ảnh",
                f"Không thể chụp ảnh từ thiết bị hiện tại.\nChi tiết: {err or 'Thiết bị không trả về dữ liệu ảnh hợp lệ.'}"
            )
