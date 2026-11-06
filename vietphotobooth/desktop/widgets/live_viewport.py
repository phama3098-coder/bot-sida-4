"""
1998 TEAM — Photobooth Live Viewport
Zero-Jitter, GPU/CPU-optimized Live View Viewport for Kiosk and Camera Configuration screens.
Maintains strict aspect ratio (KeepAspectRatio), static size hints, and non-blocking rendering.
"""

import math
from typing import Optional, Callable, List, Any, Tuple
import numpy as np
from PySide6.QtCore import Qt, QSize, QRect, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QSizePolicy


class CameraLiveViewport(QWidget):
    """
    Khung hiển thị hình ảnh Live View trực tiếp chuyên nghiệp cho cả CameraPage và KioskPage.
    Giải quyết triệt để lỗi thu phóng / nhấp nháy / giật kích thước:
    1. Cung cấp sizeHint() và minimumSizeHint() cố định (chuẩn tỷ lệ 3:2), độc lập với từng frame.
    2. Không gọi updateGeometry() mỗi khi nhận frame mới -> hoàn toàn không kích hoạt tính toán lại layout.
    3. Giữ nguyên tỷ lệ 1024 × 680 (3:2) của Nikon D780 hoặc tỷ lệ ảnh nguồn bằng chế độ KeepAspectRatio.
    4. Chỉ tính toán lại vùng hiển thị (_target_rect) khi resize cửa sổ hoặc khi tỷ lệ khung hình thay đổi.
    5. Vẽ trực tiếp qua QPainter trong paintEvent (Zero CPU scale allocation, siêu mượt 40+ FPS).
    6. Luôn hiển thị frame mới nhất (O(1)), loại bỏ hiện tượng trễ hoặc tồn đọng khung hình cũ.
    7. Hỗ trợ hiển thị ảnh thành phẩm composite (setPixmap), căn giữa không méo.
    8. Hỗ trợ hiệu ứng chớp sáng flash studio khi bấm máy (trigger_flash).
    9. Tích hợp callback thông báo khi resize để định vị lớp overlay mà không chạy trong luồng frame.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(240)

        self._current_pixmap: Optional[QPixmap] = None
        self._current_image: Optional[QImage] = None
        self._current_frame_buffer: Optional[np.ndarray] = None
        self._frame_aspect_ratio: float = 1024.0 / 680.0
        self._target_rect: QRect = QRect()
        self._grid_enabled: bool = False
        self._face_detection_enabled: bool = False
        self._face_eye_af_enabled: bool = False
        self._face_eye_af_state: Optional[str] = None
        self._target_eye_pos: Optional[Tuple[float, float]] = None
        self._detected_faces: List[Any] = []
        self._last_detected_seq_id: int = 0
        self._message_text: str = "CHƯA CÓ TÍN HIỆU HÌNH ẢNH\nVui lòng kiểm tra cáp USB hoặc chọn lại nguồn camera."
        self._message_color: QColor = QColor("#716F68")
        self._border_color: QColor = QColor("#2A2D33")
        self._bg_color: QColor = QColor("#17191C")
        self._flash_active: bool = False
        self._resize_callbacks: List[Callable[[], None]] = []

    def get_source_dimensions(self) -> Tuple[int, int]:
        """Trả về kích thước (width, height) của khung hình nguồn hiện tại."""
        if self._current_image is not None and not self._current_image.isNull():
            return self._current_image.width(), self._current_image.height()
        if self._current_pixmap is not None and not self._current_pixmap.isNull():
            return self._current_pixmap.width(), self._current_pixmap.height()
        if self._current_frame_buffer is not None and getattr(self._current_frame_buffer, "size", 0) > 0:
            h, w = self._current_frame_buffer.shape[:2]
            return w, h
        return 0, 0

    def sizeHint(self) -> QSize:
        """Kích thước gợi ý ổn định, không thay đổi theo từng frame."""
        return QSize(640, 425)

    def minimumSizeHint(self) -> QSize:
        """Kích thước tối thiểu ổn định."""
        return QSize(320, 213)

    @property
    def target_rect(self) -> QRect:
        if not self._target_rect.isValid() or self._target_rect.isEmpty():
            self._recalculate_target_rect()
        return self._target_rect

    def register_resize_callback(self, cb: Callable[[], None]):
        """Đăng ký hàm callback khi viewport resize để định vị các overlay con."""
        if cb not in self._resize_callbacks:
            self._resize_callbacks.append(cb)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recalculate_target_rect()
        if hasattr(self, "_resize_callbacks"):
            for cb in list(self._resize_callbacks):
                try:
                    cb()
                except Exception:
                    pass

    def _recalculate_target_rect(self):
        """Tính toán vùng hiển thị ảnh căn giữa, giữ nguyên tỷ lệ KeepAspectRatio vừa khung widget."""
        w = self.width()
        h = self.height()
        if w <= 10 or h <= 10:
            self._target_rect = QRect()
            return

        aspect = self._frame_aspect_ratio
        if aspect <= 0.01:
            aspect = 1024.0 / 680.0

        tw = w
        th = int(w / aspect)
        if th > h:
            th = h
            tw = int(h * aspect)

        x = (w - tw) // 2
        y = (h - th) // 2
        self._target_rect = QRect(x, y, tw, th)

    def set_frame_rgb(self, rgb_frame: np.ndarray):
        """Cập nhật frame hình ảnh mới nhất (Non-blocking, không làm thay đổi layout)."""
        if rgb_frame is None or rgb_frame.size == 0:
            return

        h, w = rgb_frame.shape[:2]
        new_aspect = float(w) / float(h) if h > 0 else (1024.0 / 680.0)

        # Nếu tỷ lệ khung hình thay đổi (ví dụ đổi camera hoặc đổi mode), tính lại target rect
        if abs(new_aspect - self._frame_aspect_ratio) > 0.01:
            self._frame_aspect_ratio = new_aspect
            self._recalculate_target_rect()

        # Lưu tham chiếu buffer numpy để đảm bảo lifetime con trỏ bộ đệm cho QImage (Zero-copy)
        self._current_frame_buffer = rgb_frame
        self._current_image = QImage(rgb_frame.data, w, h, 3 * w, QImage.Format_RGB888)
        self._current_pixmap = None
        self._message_text = ""
        self.update()

    def setPixmap(self, pixmap: QPixmap):
        """Tương thích API setPixmap của QLabel khi hiển thị ảnh thành phẩm composite hoặc draft."""
        if pixmap and not pixmap.isNull():
            w = pixmap.width()
            h = pixmap.height()
            if h > 0 and w > 0:
                new_aspect = float(w) / float(h)
                if abs(new_aspect - self._frame_aspect_ratio) > 0.01:
                    self._frame_aspect_ratio = new_aspect
                    self._recalculate_target_rect()
            self._current_frame_buffer = None
            self._current_image = None
            self._current_pixmap = pixmap
            self._message_text = ""
            self.update()
        else:
            self._current_frame_buffer = None
            self._current_image = None
            self._current_pixmap = None
            self.update()

    def clear(self):
        """Xóa ảnh hiện tại trong viewport và dọn sạch overlay."""
        self._current_frame_buffer = None
        self._current_image = None
        self._current_pixmap = None
        self.clear_overlays()

    def trigger_flash(self, duration_ms: int = 120):
        """Hiệu ứng chớp sáng flash studio khi chụp ảnh."""
        self._flash_active = True
        self.update()
        QTimer.singleShot(duration_ms, self._end_flash)

    def _end_flash(self):
        self._flash_active = False
        self.update()

    def set_message(self, text: str, color_hex: str = "#716F68", border_hex: str = "#2A2D33"):
        """Hiển thị thông báo trạng thái khi không có tín hiệu hình ảnh."""
        if self._message_text == text and self._current_pixmap is None:
            return
        self._current_pixmap = None
        self.clear_overlays()
        self._message_text = text
        self._message_color = QColor(color_hex)
        self._border_color = QColor(border_hex)
        self.update()

    def setText(self, text: str):
        """Tương thích API setText của QLabel."""
        self.set_message(text)

    def set_grid_enabled(self, enabled: bool):
        """Bật/tắt hiển thị lưới căn chỉnh bố cục 3x3."""
        if self._grid_enabled != enabled:
            self._grid_enabled = enabled
            self.update()

    def set_face_detection_enabled(self, enabled: bool):
        """Bật/tắt chế độ hiển thị khung nhận diện khuôn mặt và mắt (Software AI Preview)."""
        if self._face_detection_enabled != enabled:
            self._face_detection_enabled = enabled
            if not enabled:
                self._detected_faces = []
                self._last_detected_seq_id = 0
            self.update()

    def set_detected_faces(self, faces: List[Any], sequence_id: int = 0):
        """
        Cập nhật danh sách khuôn mặt và mắt nhận diện từ luồng AI ngầm.
        :param faces: Danh sách DetectedFace từ detector.
        :param sequence_id: Số thứ tự khung hình để ngăn callback cũ ghi đè kết quả mới.
        """
        if sequence_id > 0:
            if sequence_id < self._last_detected_seq_id:
                # Nếu sequence_id bị lùi quá 10 frame (ví dụ Live View restart hoặc counter reset), tự đồng bộ lại
                if (self._last_detected_seq_id - sequence_id) > 10:
                    self._last_detected_seq_id = sequence_id
                else:
                    # Callback cũ đến muộn -> bỏ qua an toàn
                    return
            self._last_detected_seq_id = sequence_id

        self._detected_faces = faces or []
        if self._face_detection_enabled or self._face_eye_af_enabled:
            self.update()

    def reset_face_sequence(self):
        """Đặt lại bộ đếm sequence ID (ví dụ khi Live View khởi động lại hoặc đổi nguồn)."""
        self._last_detected_seq_id = 0

    def clear_overlays(self):
        """
        Xóa sạch bounding box khuôn mặt, Eye Reticle và trạng thái mục tiêu
        khi Live View dừng hoặc camera ngắt kết nối.
        """
        self._detected_faces = []
        self._face_eye_af_state = None
        self._target_eye_pos = None
        self._last_detected_seq_id = 0
        self.update()

    def set_face_eye_af_state(
        self,
        enabled: bool,
        state: Optional[str] = None,
        target_eye: Optional[Tuple[float, float]] = None
    ):
        """
        Cập nhật trạng thái hiển thị vòng ngắm Face/Eye AF (Software-Triggered AF Reticle).
        :param enabled: Bật/tắt hiển thị reticle Face/Eye AF
        :param state: Trạng thái (SEARCHING, FOCUSING, FOCUSED, LOST, ERROR)
        :param target_eye: Tọa độ mắt mục tiêu (x, y) trên ảnh gốc
        """
        self._face_eye_af_enabled = enabled
        self._face_eye_af_state = state
        self._target_eye_pos = target_eye
        self.update()

    def setAlignment(self, align):
        """Tương thích API setAlignment của QLabel."""
        pass

    def pixmap(self) -> Optional[QPixmap]:
        if self._current_pixmap is not None:
            return self._current_pixmap
        if self._current_image is not None and not self._current_image.isNull():
            return QPixmap.fromImage(self._current_image)
        return None

    def text(self) -> str:
        return self._message_text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # 1. Nếu đang kích hoạt Flash Studio: vẽ màu trắng toàn màn hình
        if self._flash_active:
            painter.fillRect(self.rect(), QColor("#FFFFFF"))
            return

        # 2. Vẽ nền tối
        painter.fillRect(self.rect(), self._bg_color)

        # 3. Nếu có ảnh: Vẽ ảnh vừa khung nhìn KeepAspectRatio (Ưu tiên QImage direct drawImage)
        has_image = self._current_image is not None and not self._current_image.isNull()
        has_pixmap = self._current_pixmap is not None and not self._current_pixmap.isNull()

        if has_image or has_pixmap:
            if not self._target_rect.isValid() or self._target_rect.isEmpty():
                self._recalculate_target_rect()

            # Vẽ ảnh căn giữa, giữ nguyên tỷ lệ 1024:680 (3:2) không crop méo
            if has_image:
                painter.drawImage(self._target_rect, self._current_image)
            else:
                painter.drawPixmap(self._target_rect, self._current_pixmap)

            # 4. Vẽ lưới 3x3 nếu được kích hoạt
            if self._grid_enabled and self._target_rect.width() > 60:
                pen = QPen(QColor(212, 175, 55, 180), 1.5, Qt.DashLine)
                painter.setPen(pen)
                r = self._target_rect
                sw = r.width()
                sh = r.height()
                x1 = r.left() + int(sw / 3)
                x2 = r.left() + int(2 * sw / 3)
                y1 = r.top() + int(sh / 3)
                y2 = r.top() + int(2 * sh / 3)
                painter.drawLine(x1, r.top(), x1, r.bottom())
                painter.drawLine(x2, r.top(), x2, r.bottom())
                painter.drawLine(r.left(), y1, r.right(), y1)
                painter.drawLine(r.left(), y2, r.right(), y2)

            # 5. Vẽ khung nhận diện khuôn mặt & mắt (Software AI / CV Preview) nếu được kích hoạt
            show_faces = (self._face_detection_enabled or self._face_eye_af_enabled) and bool(self._detected_faces)
            if show_faces:
                painter.setRenderHint(QPainter.Antialiasing, True)
                src_w, src_h = float(self.get_source_dimensions()[0]), float(self.get_source_dimensions()[1])

                if src_w > 0 and src_h > 0:
                    r = self._target_rect
                    sx = float(r.width()) / src_w
                    sy = float(r.height()) / src_h
                    ox = r.left()
                    oy = r.top()

                    # Dynamic color based on Face/Eye AF state
                    af_state = self._face_eye_af_state or "SEARCHING"
                    if self._face_eye_af_enabled:
                        if af_state == "FOCUSED":
                            c_face = QColor("#10B981")  # Emerald green (Locked)
                            c_eye = QColor("#34D399")
                        elif af_state == "FOCUSING":
                            c_face = QColor("#F59E0B")  # Amber yellow (Driving motor)
                            c_eye = QColor("#FBBF24")
                        elif af_state == "FACE_DETECTED":
                            c_face = QColor("#06B6D4")  # Cyan (Face Detected / Tracking)
                            c_eye = QColor("#22D3EE")
                        elif af_state == "LOST":
                            c_face = QColor("#F97316")  # Orange (Lost target)
                            c_eye = QColor("#FB923C")
                        elif af_state == "ERROR":
                            c_face = QColor("#EF4444")  # Red (AF Out of focus / Error)
                            c_eye = QColor("#F87171")
                        else:  # SEARCHING
                            c_face = QColor("#38BDF8")  # Slate blue (Searching)
                            c_eye = QColor("#60A5FA")
                    else:
                        c_face = QColor("#38BDF8")  # Standard cyan
                        c_eye = QColor("#10B981")

                    pen_face = QPen(c_face, 2)
                    pen_eye = QPen(c_eye, 1.8)
                    font_tag = painter.font()
                    font_tag.setPointSize(8)
                    font_tag.setBold(True)

                    for f in self._detected_faces:
                        fx = int(ox + f.x * sx)
                        fy = int(oy + f.y * sy)
                        fw = int(f.w * sx)
                        fh = int(f.h * sy)

                        if fw <= 5 or fh <= 5:
                            continue

                        # Vẽ 4 góc khung khuôn mặt (Corner Brackets kiểu Viewfinder máy ảnh)
                        c_len = min(fw // 4, fh // 4, 18)
                        painter.setPen(pen_face)
                        # Góc trên - trái
                        painter.drawLine(fx, fy, fx + c_len, fy)
                        painter.drawLine(fx, fy, fx, fy + c_len)
                        # Góc trên - phải
                        painter.drawLine(fx + fw, fy, fx + fw - c_len, fy)
                        painter.drawLine(fx + fw, fy, fx + fw, fy + c_len)
                        # Góc dưới - trái
                        painter.drawLine(fx, fy + fh, fx + c_len, fy + fh)
                        painter.drawLine(fx, fy + fh, fx, fy + fh - c_len)
                        # Góc dưới - phải
                        painter.drawLine(fx + fw, fy + fh, fx + fw - c_len, fy + fh)
                        painter.drawLine(fx + fw, fy + fh, fx + fw, fy + fh - c_len)

                        # Tag nhỏ trên đầu khung: "FACE [92%]" hoặc "EYE AF: FOCUSED"
                        conf_pct = int(f.confidence * 100) if hasattr(f, "confidence") else 90
                        painter.setFont(font_tag)
                        if self._face_eye_af_enabled:
                            tag_text = f"EYE AF [{af_state}] {conf_pct}%"
                        else:
                            tag_text = f"FACE {conf_pct}%"
                        painter.drawText(fx + 2, max(oy + 12, fy - 4), tag_text)

                        # Vẽ vòng tròn tâm điểm cho mắt nếu nhận diện được
                        for eye_pt in (getattr(f, "right_eye", None), getattr(f, "left_eye", None)):
                            if eye_pt is not None:
                                ex = int(ox + eye_pt[0] * sx)
                                ey = int(oy + eye_pt[1] * sy)
                                rad = max(4, int(fw * 0.04))

                                # Kiểm tra xem đây có phải là mắt mục tiêu active AF không
                                is_active_target = False
                                if self._face_eye_af_enabled and self._target_eye_pos is not None:
                                    d_target = math.hypot(eye_pt[0] - self._target_eye_pos[0], eye_pt[1] - self._target_eye_pos[1])
                                    if d_target < 20.0:
                                        is_active_target = True

                                if is_active_target:
                                    # Vòng ngắm reticle chuyên dụng cho mắt đang khóa nét
                                    reticle_pen = QPen(c_eye, 2.2)
                                    painter.setPen(reticle_pen)
                                    # Vẽ hình vuông góc bao quanh mắt mục tiêu
                                    b_len = rad + 3
                                    painter.drawRect(ex - b_len, ey - b_len, 2 * b_len, 2 * b_len)
                                    painter.drawEllipse(QRect(ex - rad, ey - rad, 2 * rad, 2 * rad))
                                    painter.drawLine(ex - rad - 3, ey, ex + rad + 3, ey)
                                    painter.drawLine(ex, ey - rad - 3, ex, ey + rad + 3)
                                else:
                                    painter.setPen(pen_eye)
                                    painter.drawEllipse(QRect(ex - rad, ey - rad, 2 * rad, 2 * rad))
                                    painter.drawLine(ex - rad - 2, ey, ex + rad + 2, ey)
                                    painter.drawLine(ex, ey - rad - 2, ex, ey + rad + 2)

            # 6. Vẽ Badge trạng thái Face/Eye AF góc trên bên trái nếu đang bật
            if self._face_eye_af_enabled:
                painter.setRenderHint(QPainter.Antialiasing, True)
                af_state = self._face_eye_af_state or "SEARCHING"
                if af_state == "FOCUSED":
                    bg_color = QColor(6, 78, 59, 210)    # Dark emerald
                    border_c = QColor("#059669")
                    text_c = QColor("#34D399")
                    badge_title = "🎯 EYE AF: ĐÃ LẤY NÉT ✓"
                elif af_state == "FOCUSING":
                    bg_color = QColor(120, 53, 15, 210)  # Dark amber
                    border_c = QColor("#D97706")
                    text_c = QColor("#FBBF24")
                    badge_title = "🎯 EYE AF: ĐANG LẤY NÉT..."
                elif af_state == "FACE_DETECTED":
                    bg_color = QColor(14, 58, 82, 210)   # Dark cyan
                    border_c = QColor("#0284C7")
                    text_c = QColor("#38BDF8")
                    badge_title = "🎯 EYE AF: ĐÃ PHÁT HIỆN MẶT"
                elif af_state == "LOST":
                    bg_color = QColor(124, 45, 18, 210)  # Dark orange
                    border_c = QColor("#EA580C")
                    text_c = QColor("#FB923C")
                    badge_title = "🎯 EYE AF: KHÔNG TÌM THẤY MẶT"
                elif af_state == "ERROR":
                    bg_color = QColor(127, 29, 29, 210)  # Dark crimson
                    border_c = QColor("#DC2626")
                    text_c = QColor("#FCA5A5")
                    badge_title = "🎯 EYE AF: AF THẤT BẠI ✗"
                else:
                    bg_color = QColor(15, 23, 42, 210)   # Dark slate
                    border_c = QColor("#0284C7")
                    text_c = QColor("#38BDF8")
                    badge_title = "🎯 EYE AF: ĐANG TÌM KHUÔN MẶT"

                r = self._target_rect
                bx = r.left() + 10
                by = r.top() + 10
                bw = 240
                bh = 28
                badge_rect = QRect(bx, by, bw, bh)

                painter.setPen(QPen(border_c, 1.2))
                painter.setBrush(bg_color)
                painter.drawRoundedRect(badge_rect, 6, 6)

                painter.setPen(text_c)
                f_badge = painter.font()
                f_badge.setPointSize(9)
                f_badge.setBold(True)
                painter.setFont(f_badge)
                painter.drawText(badge_rect, Qt.AlignCenter, badge_title)
        elif self._message_text:
            # 5. Vẽ thông báo khi chưa có feed
            painter.setPen(QPen(self._border_color, 1))
            painter.drawRect(self.rect().adjusted(1, 1, -2, -2))

            painter.setPen(self._message_color)
            font = painter.font()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, self._message_text)
