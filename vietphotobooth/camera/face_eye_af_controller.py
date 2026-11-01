"""
1998 TEAM — Photobooth Software-Triggered Face/Eye AF Controller
Orchestrates real-time Face & Eye Detection on Live View frames and triggers
hardware Autofocus on Nikon D780 via Nikon MAID Native USB (Type0026) backend.

DISCLAIMER & SDK CAPABILITY SPECIFICATION:
- Lệnh kích hoạt AF sử dụng kNkMAIDCapability_AutoFocus (Cap ID 29) với lệnh CAP_START,
  tương đương thao tác nhấn nửa cò (Half-press) hoặc bấm nút AF-ON trên máy ảnh.
- Quá trình này TUYỆT ĐỐI KHÔNG giải phóng màn trập (Shutter Release) và KHÔNG chụp ảnh.
- NIKON MAID TYPE0026 LIMITATION:
  MAID SDK Type0026 không hỗ trợ API ghi tọa độ điểm lấy nét tự do (X, Y) pixel trên Live View.
  Hệ thống sử dụng thị giác máy tính YuNet AI để nhận diện mắt/mặt mục tiêu, đánh giá độ ổn định
  và tự động phát lệnh AF cho máy ảnh Nikon D780 (ở chế độ Face Priority AF hoặc Live View AF)
  khi đối tượng ổn định, tự động lấy nét lại khi đối tượng di chuyển hoặc mất nét.
"""

from enum import Enum
import logging
import math
import time
import threading
from typing import List, Tuple, Optional, Callable, Dict, Any

from vietphotobooth.camera.face_detector import DetectedFace

logger = logging.getLogger("VietPhotoBooth.camera.face_eye_af")


class RateLimitedLogger:
    """Ghi log có giới hạn tần suất theo danh mục để không làm chậm luồng Live View 30-40 FPS."""
    def __init__(self, min_interval_sec: float = 1.5):
        self._min_interval = min_interval_sec
        self._last_logged: Dict[str, float] = {}

    def log(self, key: str, log_fn, msg: str, *args):
        now = time.time()
        last = self._last_logged.get(key, 0.0)
        if now - last >= self._min_interval:
            self._last_logged[key] = now
            log_fn(msg, *args)


rate_logger = RateLimitedLogger(min_interval_sec=1.5)


class FaceEyeAFState(str, Enum):
    """Trạng thái hoạt động chuẩn của hệ thống Software-Triggered Face/Eye AF."""
    SEARCHING = "SEARCHING"          # Đang tìm khuôn mặt trong Live View
    FACE_DETECTED = "FACE_DETECTED"  # Đã phát hiện khuôn mặt/mắt, đang theo dõi ổn định
    FOCUSING = "FOCUSING"            # Đã xác định mục tiêu ổn định, đang kích hoạt AF
    FOCUSED = "FOCUSED"              # Máy ảnh báo đã khóa nét thành công (In Focus)
    LOST = "LOST"                    # Không tìm thấy khuôn mặt trong khung hình
    ERROR = "ERROR"                  # Lấy nét thất bại (Out of Focus, MF mode hoặc lỗi giao tiếp MAID)


class FaceEyeAFController:
    """
    Bộ điều khiển trung tâm Face/Eye AF phần mềm kích hoạt phần cứng camera:
    - Nhận diện mắt và khuôn mặt mục tiêu theo thời gian thực từ Live View.
    - Đánh giá độ ổn định (Hysteresis & Spatial Stability Tracking).
    - Tự động kích hoạt AF khi mục tiêu ổn định mà không cần người dùng thao tác.
    - Giám sát độ lệch vị trí (Motion Delta) để tự động kích hoạt lấy nét lại.
    - Chống spam lệnh qua cơ chế Cooldown và Khóa tuần tự (Single in-flight guard).
    """

    def __init__(
        self,
        af_trigger_fn: Optional[Callable[[Callable[[bool, str], None]], None]] = None,
        stability_frames: int = 3,
        stability_px_threshold: float = 20.0,
        movement_px_threshold: float = 35.0,
        box_scale_threshold: float = 0.18,
        lost_frames_threshold: int = 6,
        cooldown_sec: float = 1.8,
        af_timeout_sec: float = 3.5,
    ):
        self._af_trigger_fn = af_trigger_fn
        self._stability_frames = stability_frames
        self._stability_px_threshold = stability_px_threshold
        self._movement_px_threshold = movement_px_threshold
        self._box_scale_threshold = box_scale_threshold
        self._lost_frames_threshold = lost_frames_threshold
        self._cooldown_sec = cooldown_sec
        self._af_timeout_sec = af_timeout_sec

        self._lock = threading.RLock()
        self._enabled: bool = False
        self._auto_trigger_paused: bool = False
        self._state: FaceEyeAFState = FaceEyeAFState.SEARCHING
        self._status_message: str = "Đang tìm khuôn mặt..."

        # Target tracking state
        self._target_face: Optional[DetectedFace] = None
        self._target_eye: Optional[Tuple[float, float]] = None
        self._target_eye_label: str = "right"  # "right", "left" hoặc "face_center"
        self._last_eye_pos: Optional[Tuple[float, float]] = None
        self._locked_eye_pos: Optional[Tuple[float, float]] = None
        self._locked_bbox: Optional[Tuple[float, float, float, float]] = None
        self._last_frame_shape: Optional[Tuple[int, int]] = None

        # Counters & timing
        self._consecutive_stable_frames: int = 0
        self._consecutive_lost_frames: int = 0
        self._consecutive_moved_frames: int = 0
        self._last_af_trigger_time: float = 0.0
        self._last_af_duration_ms: float = 0.0
        self._last_af_success: bool = False
        self._is_af_in_progress: bool = False
        self._last_error: str = ""

        # Diagnostics & counters
        self._total_af_triggers: int = 0
        self._total_af_successes: int = 0
        self._total_af_failures: int = 0
        self._af_command_id: int = 0
        self._last_processed_seq_id: int = 0

        # Observer callbacks: fn(state: FaceEyeAFState, message: str, target_face, target_eye)
        self._state_callbacks: List[Callable[[FaceEyeAFState, str, Optional[DetectedFace], Optional[Tuple[float, float]]], None]] = []

    # --------------------------------------------------------------------------
    # PROPERTIES
    # --------------------------------------------------------------------------

    @property
    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def state(self) -> FaceEyeAFState:
        with self._lock:
            return self._state

    @property
    def status_message(self) -> str:
        with self._lock:
            return self._status_message

    @property
    def target_eye(self) -> Optional[Tuple[float, float]]:
        with self._lock:
            return self._target_eye

    @property
    def target_face(self) -> Optional[DetectedFace]:
        with self._lock:
            return self._target_face

    @property
    def is_af_in_progress(self) -> bool:
        with self._lock:
            return self._is_af_in_progress

    # --------------------------------------------------------------------------
    # CONTROLLER LIFECYCLE
    # --------------------------------------------------------------------------

    def set_af_trigger_function(self, fn: Callable[[Callable[[bool, str], None]], None]) -> None:
        """Cập nhật hàm thực thi AF phần cứng."""
        with self._lock:
            self._af_trigger_fn = fn

    def enable(self) -> bool:
        """Bật chế độ Software-Triggered Face/Eye AF."""
        with self._lock:
            self._enabled = True
            self._consecutive_stable_frames = 0
            self._consecutive_lost_frames = 0
            self._consecutive_moved_frames = 0
            self._last_eye_pos = None
            self._locked_eye_pos = None
            self._locked_bbox = None
            self._is_af_in_progress = False
            self._af_command_id = 0
            self._last_processed_seq_id = 0
            self._set_state(FaceEyeAFState.SEARCHING, "Đang tìm khuôn mặt...")
            logger.info("[FaceEyeAF] Đã BẬT hệ thống Face/Eye AF tự động.")
            return True

    def disable(self) -> None:
        """Tắt chế độ Software-Triggered Face/Eye AF."""
        with self._lock:
            self._enabled = False
            self._auto_trigger_paused = False
            self._target_face = None
            self._target_eye = None
            self._last_eye_pos = None
            self._locked_eye_pos = None
            self._locked_bbox = None
            self._is_af_in_progress = False
            self._consecutive_stable_frames = 0
            self._consecutive_lost_frames = 0
            self._consecutive_moved_frames = 0
            self._af_command_id += 1  # Vô hiệu hóa callback của lệnh AF đang dang dở
            self._last_processed_seq_id = 0
            self._set_state(FaceEyeAFState.SEARCHING, "Face/Eye AF: Đã tắt.")
            logger.info("[FaceEyeAF] Đã TẮT hệ thống Face/Eye AF.")

    def pause_auto_trigger(self) -> None:
        """Tạm dừng tự động phát lệnh AF nền (ví dụ khi Kiosk đang thực hiện chụp ảnh)."""
        with self._lock:
            self._auto_trigger_paused = True

    def resume_auto_trigger(self) -> None:
        """Khôi phục tự động phát lệnh AF nền sau khi chụp ảnh hoàn tất."""
        with self._lock:
            self._auto_trigger_paused = False

    def reset_sequence(self) -> None:
        """Đặt lại số thứ tự frame đã xử lý (ví dụ khi Live View khởi động lại)."""
        with self._lock:
            self._last_processed_seq_id = 0
            self._consecutive_stable_frames = 0
            self._consecutive_lost_frames = 0
            self._consecutive_moved_frames = 0

    def register_state_callback(
        self,
        cb: Callable[[FaceEyeAFState, str, Optional[DetectedFace], Optional[Tuple[float, float]]], None]
    ) -> None:
        with self._lock:
            if cb not in self._state_callbacks:
                self._state_callbacks.append(cb)

    def unregister_state_callback(
        self,
        cb: Callable[[FaceEyeAFState, str, Optional[DetectedFace], Optional[Tuple[float, float]]], None]
    ) -> None:
        with self._lock:
            if cb in self._state_callbacks:
                self._state_callbacks.remove(cb)

    def get_diagnostics(self) -> Dict[str, Any]:
        """Trả về dữ liệu telemetry và chẩn đoán nội bộ của controller."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "state": self._state.value,
                "target_eye": self._target_eye,
                "target_face": self._target_face,
                "locked_eye_pos": self._locked_eye_pos,
                "is_af_in_progress": self._is_af_in_progress,
                "af_command_id": self._af_command_id,
                "last_processed_seq_id": self._last_processed_seq_id,
                "total_af_triggers": self._total_af_triggers,
                "total_af_successes": self._total_af_successes,
                "total_af_failures": self._total_af_failures,
                "last_af_duration_ms": self._last_af_duration_ms,
                "last_error": self._last_error,
                "config": {
                    "stability_frames": self._stability_frames,
                    "stability_px_threshold": self._stability_px_threshold,
                    "cooldown_sec": self._cooldown_sec,
                    "movement_px_threshold": self._movement_px_threshold,
                    "lost_frames_threshold": self._lost_frames_threshold,
                }
            }

    # --------------------------------------------------------------------------
    # FRAME & FACE PROCESSING PIPELINE
    # --------------------------------------------------------------------------

    def process_faces(
        self,
        faces: List[DetectedFace],
        frame_shape: Optional[Tuple[int, int]] = None,
        sequence_id: int = 0,
        timestamp: float = 0.0
    ) -> FaceEyeAFState:
        """
        Xử lý danh sách khuôn mặt nhận diện được từ Live View.
        :param faces: Danh sách DetectedFace từ FaceDetectionService.
        :param frame_shape: Kích thước khung hình (width, height).
        :param sequence_id: Thứ tự khung hình monotonic để loại bỏ out-of-order frame.
        :param timestamp: Thời điểm ghi nhận khung hình.
        """
        with self._lock:
            if not self._enabled:
                return self._state

            if frame_shape:
                self._last_frame_shape = frame_shape

            # Kiểm tra sequence_id để loại bỏ frame trễ / out-of-order
            if sequence_id > 0:
                if sequence_id < self._last_processed_seq_id:
                    # Nếu sequence_id lùi quá 10 frame (ví dụ Live View restart hoặc counter reset), tự đồng bộ lại
                    if (self._last_processed_seq_id - sequence_id) > 10:
                        logger.info(
                            "[FaceEyeAF] Phát hiện sequence_id được đặt lại (%d -> %d), đồng bộ lại.",
                            self._last_processed_seq_id, sequence_id
                        )
                        self._last_processed_seq_id = sequence_id
                    else:
                        rate_logger.log(
                            "drop_outdated",
                            logger.debug,
                            "[FaceEyeAF] Bỏ qua khung hình cũ (seq=%d < last_processed=%d)",
                            sequence_id, self._last_processed_seq_id
                        )
                        return self._state
                self._last_processed_seq_id = sequence_id

            # Trường hợp 1: Không phát hiện khuôn mặt nào trong frame
            if not faces:
                self._handle_no_faces()
                return self._state

            # Trường hợp 2: Có khuôn mặt -> chọn khuôn mặt mục tiêu
            primary_face = self._select_primary_face(faces, frame_shape)
            if primary_face is None:
                self._handle_no_faces()
                return self._state

            # Xác định mắt mục tiêu
            chosen_eye, eye_label = self._select_target_eye(primary_face)
            if chosen_eye is None:
                # Không thấy mắt rõ ràng -> dùng tâm khuôn mặt
                chosen_eye = (primary_face.x + primary_face.w / 2.0, primary_face.y + primary_face.h / 3.0)
                eye_label = "face_center"

            self._consecutive_lost_frames = 0
            self._target_face = primary_face
            self._target_eye = chosen_eye
            self._target_eye_label = eye_label

            now = time.time()

            # Phân nhánh theo trạng thái hiện tại
            if self._state == FaceEyeAFState.FOCUSING:
                # Đang trong tiến trình lái motor AF -> không can thiệp
                return self._state

            elif self._state in (FaceEyeAFState.SEARCHING, FaceEyeAFState.FACE_DETECTED, FaceEyeAFState.LOST, FaceEyeAFState.ERROR):
                # Đã có khuôn mặt mục tiêu -> cập nhật trạng thái FACE_DETECTED nếu chưa khóa nét
                if self._state != FaceEyeAFState.FACE_DETECTED:
                    rate_logger.log(
                        "face_detected",
                        logger.info,
                        "[FaceEyeAF] Đã phát hiện mục tiêu: Face bbox=(%.1f, %.1f, %.1f, %.1f), Mắt=[%s]",
                        primary_face.x, primary_face.y, primary_face.w, primary_face.h, eye_label
                    )
                    self._set_state(
                        FaceEyeAFState.FACE_DETECTED,
                        f"Đã phát hiện khuôn mặt ({primary_face.confidence*100:.0f}%): đang theo dõi mục tiêu..."
                    )
                # Đánh giá độ ổn định của mắt
                self._evaluate_stability_and_trigger(chosen_eye, primary_face, now)

            elif self._state == FaceEyeAFState.FOCUSED:
                # Đã khóa nét -> kiểm tra chủ thể có di chuyển hoặc thay đổi cự ly không
                self._evaluate_refocus_condition(chosen_eye, primary_face, now)

            return self._state

    # --------------------------------------------------------------------------
    # INTERNAL LOGIC & STATE TRANSITIONS
    # --------------------------------------------------------------------------

    def _handle_no_faces(self) -> None:
        """Xử lý khi không còn nhận diện được khuôn mặt trong khung hình."""
        self._consecutive_lost_frames += 1
        self._consecutive_stable_frames = 0
        self._consecutive_moved_frames = 0

        if self._consecutive_lost_frames >= self._lost_frames_threshold:
            self._target_face = None
            self._target_eye = None
            self._last_eye_pos = None

            if self._state not in (FaceEyeAFState.LOST, FaceEyeAFState.FOCUSING):
                rate_logger.log(
                    "lost_face",
                    logger.info,
                    "[FaceEyeAF] Không tìm thấy khuôn mặt (%d frames liên tiếp). Chuyển sang LOST.",
                    self._consecutive_lost_frames
                )
                self._set_state(FaceEyeAFState.LOST, "Không tìm thấy khuôn mặt.")

    def _select_primary_face(
        self, faces: List[DetectedFace], frame_shape: Optional[Tuple[int, int]]
    ) -> Optional[DetectedFace]:
        """
        Chọn khuôn mặt chính (Primary Target Face):
        Nếu có 1 khuôn mặt: luôn chọn khuôn mặt đó.
        Nếu có nhiều khuôn mặt: ưu tiên khuôn mặt lớn nhất (gần camera nhất) và gần tâm khung hình.
        """
        if not faces:
            return None

        if len(faces) == 1:
            return faces[0]

        if frame_shape and frame_shape[0] > 0 and frame_shape[1] > 0:
            cx = frame_shape[0] / 2.0
            cy = frame_shape[1] / 2.0
            diag = math.hypot(cx, cy)
        else:
            cx, cy = 512.0, 340.0
            diag = 614.0

        best_face = faces[0]
        best_score = -float('inf')

        for f in faces:
            area = max(1.0, f.w * f.h)
            face_cx = f.x + f.w / 2.0
            face_cy = f.y + f.h / 2.0
            dist_to_center = math.hypot(face_cx - cx, face_cy - cy)
            norm_dist = min(1.0, dist_to_center / max(1.0, diag))

            score = area * (1.0 - 0.25 * norm_dist) * max(0.1, f.confidence)
            if score > best_score:
                best_score = score
                best_face = f

        return best_face

    def _select_target_eye(self, face: DetectedFace) -> Tuple[Optional[Tuple[float, float]], str]:
        """
        Lựa chọn mắt mục tiêu (Target Eye):
        Xác minh tọa độ mắt hợp lệ bên trong bounding box khuôn mặt.
        """
        re = getattr(face, "right_eye", None)
        le = getattr(face, "left_eye", None)

        def _is_valid_eye(eye_pt):
            if eye_pt is None:
                return False
            ex, ey = eye_pt
            if ex <= 0 or ey <= 0:
                return False
            # Mắt phải nằm trong phạm vi bounding box (có mở rộng 10% lề)
            fx, fy, fw, fh = face.bbox
            return (fx - 0.1 * fw <= ex <= fx + 1.1 * fw) and (fy <= ey <= fy + 0.8 * fh)

        re_valid = _is_valid_eye(re)
        le_valid = _is_valid_eye(le)

        if re_valid and le_valid:
            if self._last_eye_pos is not None:
                d_re = math.hypot(re[0] - self._last_eye_pos[0], re[1] - self._last_eye_pos[1])
                d_le = math.hypot(le[0] - self._last_eye_pos[0], le[1] - self._last_eye_pos[1])
                if d_re <= d_le:
                    return re, "right"
                else:
                    return le, "left"
            return re, "right"
        elif re_valid:
            return re, "right"
        elif le_valid:
            return le, "left"

        return None, "none"

    def _evaluate_stability_and_trigger(
        self, eye: Tuple[float, float], face: DetectedFace, now: float
    ) -> None:
        """Đánh giá độ ổn định vị trí mắt qua các khung hình liên tiếp để kích hoạt AF."""
        if self._last_eye_pos is None:
            self._last_eye_pos = eye
            self._consecutive_stable_frames = 1
        else:
            delta = math.hypot(eye[0] - self._last_eye_pos[0], eye[1] - self._last_eye_pos[1])
            self._last_eye_pos = eye

            if delta <= self._stability_px_threshold:
                self._consecutive_stable_frames += 1
            else:
                self._consecutive_stable_frames = 1

        if self._consecutive_stable_frames >= self._stability_frames:
            if getattr(self, "_auto_trigger_paused", False):
                return
            time_since_last_af = now - self._last_af_trigger_time
            if time_since_last_af >= self._cooldown_sec and not self._is_af_in_progress:
                self._trigger_af(eye, face, reason="Mục tiêu đã ổn định")

    def _evaluate_refocus_condition(
        self, eye: Tuple[float, float], face: DetectedFace, now: float
    ) -> None:
        """Kiểm tra điều kiện cần lấy nét lại khi đối tượng đã ở trạng thái FOCUSED."""
        if getattr(self, "_auto_trigger_paused", False):
            return
        if self._locked_eye_pos is None or self._locked_bbox is None:
            self._locked_eye_pos = eye
            self._locked_bbox = face.bbox
            return

        dist_from_locked = math.hypot(eye[0] - self._locked_eye_pos[0], eye[1] - self._locked_eye_pos[1])
        locked_w = self._locked_bbox[2]
        w_delta_ratio = abs(face.w - locked_w) / max(1.0, locked_w)

        moved = (dist_from_locked > self._movement_px_threshold) or (w_delta_ratio > self._box_scale_threshold)

        if moved:
            self._consecutive_moved_frames += 1
        else:
            self._consecutive_moved_frames = 0

        if self._consecutive_moved_frames >= 2:
            time_since_last_af = now - self._last_af_trigger_time
            if time_since_last_af >= self._cooldown_sec and not self._is_af_in_progress:
                reason = f"Chủ thể dịch chuyển (Δ={dist_from_locked:.1f}px, scale_Δ={w_delta_ratio*100:.1f}%)"
                logger.info("[FaceEyeAF] %s -> Kích hoạt chu kỳ lấy nét lại.", reason)
                self._trigger_af(eye, face, reason=reason)

    def _trigger_af(self, eye: Tuple[float, float], face: DetectedFace, reason: str = "") -> None:
        """Gửi lệnh kích hoạt AF một lần tới máy ảnh Nikon D780."""
        if self._is_af_in_progress:
            # Watchdog timeout: Nếu lệnh AF in-flight quá 5 giây chưa nhận callback thì tự giải phóng cờ
            if (time.time() - self._last_af_trigger_time) > 5.0:
                logger.warning("[FaceEyeAF] Cờ _is_af_in_progress bị kẹt quá 5s -> Tự động giải phóng (Watchdog reset).")
                self._is_af_in_progress = False
            else:
                rate_logger.log("af_in_progress", logger.debug, "[FaceEyeAF] Đang có lệnh AF in-flight, bỏ qua.")
                return

        if self._af_trigger_fn is None:
            logger.warning("[FaceEyeAF] Chưa thiết lập af_trigger_fn để gửi lệnh lấy nét.")
            self._set_state(FaceEyeAFState.ERROR, "AF thất bại: Thiếu hàm điều khiển AF.")
            return

        self._is_af_in_progress = True
        self._last_af_trigger_time = time.time()
        self._total_af_triggers += 1
        self._af_command_id += 1
        current_cmd_id = self._af_command_id

        trigger_start_time = time.perf_counter()
        eye_x, eye_y = eye
        logger.info(
            "[FaceEyeAF] PHÁT LỆNH AF (cmd_id=%d): Lý do='%s', Điểm ngắm=(%.1f, %.1f) [%s], BBox=(%.1f, %.1f, %.1f, %.1f)",
            current_cmd_id, reason, eye_x, eye_y, self._target_eye_label, face.x, face.y, face.w, face.h
        )

        self._set_state(
            FaceEyeAFState.FOCUSING,
            f"Đang lấy nét ({reason})..."
        )

        def _completion_cb(success: bool, msg: str):
            with self._lock:
                if current_cmd_id != self._af_command_id:
                    rate_logger.log(
                        "obsolete_af_cb",
                        logger.debug,
                        "[FaceEyeAF] Bỏ qua callback hoàn thành lệnh AF cũ (cmd_id=%d vs current=%d)",
                        current_cmd_id, self._af_command_id
                    )
                    return
                if not self._enabled:
                    logger.debug("[FaceEyeAF] Bỏ qua callback hoàn thành vì Face/Eye AF đã tắt.")
                    self._is_af_in_progress = False
                    return
                dur_ms = (time.perf_counter() - trigger_start_time) * 1000.0
                self._on_af_completed(success, msg, dur_ms, eye, face)

        try:
            import inspect
            sig = inspect.signature(self._af_trigger_fn)
            kwargs = {}
            if "target_point" in sig.parameters:
                kwargs["target_point"] = eye
            if "frame_size" in sig.parameters and self._last_frame_shape:
                kwargs["frame_size"] = self._last_frame_shape
            self._af_trigger_fn(_completion_cb, **kwargs)
        except Exception as ex:
            dur_ms = (time.perf_counter() - trigger_start_time) * 1000.0
            logger.error("[FaceEyeAF] Ngoại lệ khi kích hoạt AF: %s", ex)
            with self._lock:
                if current_cmd_id == self._af_command_id and self._enabled:
                    self._on_af_completed(False, f"Lỗi ngoại lệ AF: {ex}", dur_ms, eye, face)

    def _on_af_completed(
        self, success: bool, message: str, duration_ms: float,
        eye: Tuple[float, float], face: DetectedFace
    ) -> None:
        """Xử lý phản hồi kết quả từ máy ảnh sau khi quá trình AF kết thúc."""
        with self._lock:
            self._is_af_in_progress = False
            self._last_af_duration_ms = duration_ms
            self._last_af_success = success

            if success:
                self._total_af_successes += 1
                self._locked_eye_pos = eye
                self._locked_bbox = face.bbox
                self._consecutive_moved_frames = 0
                self._consecutive_stable_frames = self._stability_frames
                logger.info(
                    "[FaceEyeAF] AF THÀNH CÔNG (In Focus) sau %.1fms. Mắt=(%.1f, %.1f). Khóa nét hoàn tất.",
                    duration_ms, eye[0], eye[1]
                )
                self._set_state(
                    FaceEyeAFState.FOCUSED,
                    f"Đã lấy nét thành công ({duration_ms:.0f}ms) ✓"
                )
            else:
                self._total_af_failures += 1
                self._last_error = message
                logger.warning(
                    "[FaceEyeAF] AF THẤT BẠI sau %.1fms: '%s'. Chuyển trạng thái ERROR.",
                    duration_ms, message
                )
                self._set_state(
                    FaceEyeAFState.ERROR,
                    f"AF thất bại: {message}"
                )

    def _set_state(self, new_state: FaceEyeAFState, message: str) -> None:
        """Cập nhật trạng thái và thông báo tới các observer callbacks."""
        self._state = new_state
        self._status_message = message

        callbacks_to_invoke = list(self._state_callbacks)
        target_face = self._target_face
        target_eye = self._target_eye

        for cb in callbacks_to_invoke:
            try:
                cb(new_state, message, target_face, target_eye)
            except Exception as ex:
                logger.debug("[FaceEyeAF] Lỗi trong state callback: %s", ex)


def select_af_target(
    faces: List[DetectedFace],
    frame_shape: Optional[Tuple[int, int]] = None,
    preferred_face: Optional[DetectedFace] = None
) -> Tuple[Optional[Tuple[float, float]], str, Optional[DetectedFace]]:
    """
    Xác định điểm lấy nét tự động tối ưu từ danh sách khuôn mặt nhận diện được:
    1. Lựa chọn khuôn mặt chính (Primary Face):
       - Ưu tiên khuôn mặt có diện tích lớn nhất (gần máy ảnh nhất) và gần tâm khung hình nhất.
    2. Ưu tiên mắt mục tiêu (Target Eye):
       - Kiểm tra mắt phải và mắt trái nằm trong vùng hợp lệ của khuôn mặt.
       - Trả về tọa độ mắt và target_type='eye'.
    3. Dự phòng khuôn mặt (Face Center):
       - Nếu không phát hiện được mắt (hoặc bị che/nhắm),
         sử dụng tâm khuôn mặt (x + w/2, y + h*0.4) và target_type='face'.
    4. Không có khuôn mặt:
       - Trả về (None, 'none', None).

    Trả về: (target_point, target_type, selected_face)
    """
    if not faces:
        return None, "none", None

    selected_face: Optional[DetectedFace] = None
    if preferred_face is not None and preferred_face in faces:
        selected_face = preferred_face
    elif len(faces) == 1:
        selected_face = faces[0]
    else:
        if frame_shape and frame_shape[0] > 0 and frame_shape[1] > 0:
            cx = frame_shape[0] / 2.0
            cy = frame_shape[1] / 2.0
            diag = math.hypot(cx, cy)
        else:
            cx, cy = 512.0, 340.0
            diag = 614.0

        best_score = -float('inf')
        best_face = faces[0]
        for f in faces:
            area = max(1.0, f.w * f.h)
            fcx = f.x + f.w / 2.0
            fcy = f.y + f.h / 2.0
            dist = math.hypot(fcx - cx, fcy - cy)
            norm_dist = min(1.0, dist / max(1.0, diag))
            score = area * (1.0 - 0.25 * norm_dist) * max(0.1, f.confidence)
            if score > best_score:
                best_score = score
                best_face = f
        selected_face = best_face

    if selected_face is None:
        return None, "none", None

    re = getattr(selected_face, "right_eye", None)
    le = getattr(selected_face, "left_eye", None)
    fx, fy, fw, fh = selected_face.bbox

    def _is_valid_eye(eye_pt):
        if eye_pt is None:
            return False
        ex, ey = eye_pt
        if ex <= 0 or ey <= 0:
            return False
        return (fx - 0.1 * fw <= ex <= fx + 1.1 * fw) and (fy <= ey <= fy + 0.8 * fh)

    re_valid = _is_valid_eye(re)
    le_valid = _is_valid_eye(le)

    if re_valid and le_valid:
        return re, "eye", selected_face
    elif re_valid:
        return re, "eye", selected_face
    elif le_valid:
        return le, "eye", selected_face
    else:
        face_center = (selected_face.x + selected_face.w / 2.0, selected_face.y + selected_face.h * 0.4)
        return face_center, "face", selected_face

