"""
1998 TEAM — Photobooth Face & Eye Detection (Software AI / CV Preview)
Lightweight, high-speed face and eye detection running asynchronously in a background worker.
Detects facial bounding boxes and precise eye coordinates for preview overlay.

DISCLAIMER / NGUYÊN TẮC QUAN TRỌNG:
Đây là hệ thống nhận diện khuôn mặt và mắt bằng thị giác máy tính (AI Software Overlay)
trên luồng xem trước (Live View), phục vụ căn khung ảnh chuyên nghiệp chuẩn studio.
Hệ thống AF quang học của máy ảnh được điều khiển độc lập qua giao thức Nikon MAID.
"""

import os
import time
import inspect
import threading
from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable
import logging
import numpy as np

logger = logging.getLogger("VietPhotoBooth.camera.face_detector")


@dataclass
class DetectedFace:
    """Mô hình dữ liệu khuôn mặt và mắt được nhận diện."""
    x: float
    y: float
    w: float
    h: float
    confidence: float
    right_eye: Optional[Tuple[float, float]] = None
    left_eye: Optional[Tuple[float, float]] = None
    nose: Optional[Tuple[float, float]] = None
    mouth_right: Optional[Tuple[float, float]] = None
    mouth_left: Optional[Tuple[float, float]] = None

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)


class FaceEyeDetector:
    """Bộ nhận diện khuôn mặt và mắt sử dụng mô hình tối ưu YuNet ONNX của OpenCV."""

    def __init__(self, model_path: Optional[str] = None, score_threshold: float = 0.50):
        self._score_threshold = score_threshold
        self._model_path = model_path or self._resolve_default_model_path()
        self._detector = None
        self._last_input_size = (0, 0)
        self._initialized = False

        if self._model_path and os.path.exists(self._model_path):
            self._init_detector()
        else:
            logger.warning("Không tìm thấy mô hình YuNet tại: %s", self._model_path)

    @classmethod
    def _resolve_default_model_path(cls) -> Optional[str]:
        model_filenames = [
            "face_detection_yunet.onnx",
            "face_detection_yunet_2023mar.onnx",
        ]
        candidates = []
        # In PyInstaller frozen bundle:
        if hasattr(os, "_MEIPASS"):
            meipass = getattr(os, "_MEIPASS")
            for fname in model_filenames:
                candidates.append(os.path.join(meipass, "Assets", "Models", fname))

        for fname in model_filenames:
            candidates.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Models", fname)))
            candidates.append(os.path.abspath(os.path.join(os.getcwd(), "Assets", "Models", fname)))

        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _init_detector(self) -> bool:
        try:
            import cv2
            if hasattr(cv2, "FaceDetectorYN"):
                self._detector = cv2.FaceDetectorYN.create(
                    self._model_path,
                    "",
                    (320, 213),
                    score_threshold=self._score_threshold,
                    nms_threshold=0.3,
                    top_k=5
                )
                self._last_input_size = (320, 213)
                self._initialized = True
                logger.info("Khởi tạo OpenCV FaceDetectorYN (YuNet) thành công: %s", self._model_path)
                return True
        except Exception as ex:
            logger.error("Lỗi khởi tạo FaceDetectorYN: %s", ex)
        return False

    @property
    def model_path(self) -> str:
        return self._model_path or ""

    @property
    def is_available(self) -> bool:
        return self._initialized and self._detector is not None

    def detect_faces(self, image_rgb: np.ndarray, max_proc_width: int = 1024) -> List[DetectedFace]:
        """
        Nhận diện khuôn mặt và mắt trên ảnh RGB.
        Tự động scale để tối ưu tốc độ xử lý (~4-8 ms), sau đó ánh xạ lại kích thước gốc.
        """
        if not self.is_available or image_rgb is None or image_rgb.size == 0:
            return []

        try:
            import cv2
            orig_h, orig_w = image_rgb.shape[:2]
            scale = 1.0

            # Giới hạn kích thước xử lý để giữ FPS cực cao
            if orig_w > max_proc_width:
                scale = float(max_proc_width) / float(orig_w)
                proc_w = max_proc_width
                proc_h = int(orig_h * scale)
                proc_rgb = cv2.resize(image_rgb, (proc_w, proc_h), interpolation=cv2.INTER_LINEAR)
            else:
                proc_w, proc_h = orig_w, orig_h
                proc_rgb = image_rgb

            # Cập nhật input size cho detector nếu thay đổi
            if (proc_w, proc_h) != self._last_input_size:
                self._detector.setInputSize((proc_w, proc_h))
                self._last_input_size = (proc_w, proc_h)

            # Chuyển đổi RGB sang BGR cho OpenCV DNN
            proc_bgr = cv2.cvtColor(proc_rgb, cv2.COLOR_RGB2BGR)

            res, faces = self._detector.detect(proc_bgr)
            if faces is None or len(faces) == 0:
                return []

            inv_scale = 1.0 / scale
            results: List[DetectedFace] = []

            for f in faces:
                conf = float(f[-1])
                if conf < self._score_threshold:
                    continue

                # Bounding box [x, y, w, h]
                x = float(f[0]) * inv_scale
                y = float(f[1]) * inv_scale
                w = float(f[2]) * inv_scale
                h = float(f[3]) * inv_scale

                # Landmarks: Right Eye (4, 5), Left Eye (6, 7), Nose (8, 9), Mouth (10-13)
                re = (float(f[4]) * inv_scale, float(f[5]) * inv_scale)
                le = (float(f[6]) * inv_scale, float(f[7]) * inv_scale)
                nose = (float(f[8]) * inv_scale, float(f[9]) * inv_scale)
                mr = (float(f[10]) * inv_scale, float(f[11]) * inv_scale)
                ml = (float(f[12]) * inv_scale, float(f[13]) * inv_scale)

                results.append(DetectedFace(
                    x=x, y=y, w=w, h=h,
                    confidence=conf,
                    right_eye=re,
                    left_eye=le,
                    nose=nose,
                    mouth_right=mr,
                    mouth_left=ml
                ))

            return results
        except Exception as ex:
            logger.error("Lỗi trong quá trình detect_faces: %s", ex, exc_info=True)
            return []


class FaceDetectionService:
    """
    Dịch vụ chạy ngầm xử lý nhận diện khuôn mặt và mắt theo thời gian thực.
    - Chạy trên luồng nền riêng biệt (Zero UI blocking).
    - Tự động bỏ khung hình cũ (Atomic single-buffer), chỉ xử lý khung hình mới nhất.
    - Giới hạn tần suất xử lý (~10 FPS) để bảo tồn 100% FPS Live View mượt mà.
    """

    def __init__(self, target_detection_fps: float = 12.0):
        self._detector: Optional[FaceEyeDetector] = None
        self._target_interval = 1.0 / target_detection_fps if target_detection_fps > 0 else 0.08
        self._running = False
        self._enabled = False
        self._thread: Optional[threading.Thread] = None

        self._pending_frame: Optional[np.ndarray] = None
        self._pending_seq_id: int = 0
        self._pending_timestamp: float = 0.0
        self._seq_counter: int = 0
        self._last_telemetry_time: float = 0.0
        self._frame_lock = threading.Lock()
        self._new_frame_event = threading.Event()

        self._callbacks: List[Callable[..., None]] = []

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> bool:
        """Bật nhận diện khuôn mặt và mắt."""
        if not self._detector:
            self._detector = FaceEyeDetector()

        if not self._detector.is_available:
            logger.warning("Không thể bật Face Detection: mô hình không khả dụng.")
            return False

        self._enabled = True
        if not self._running:
            self._running = True
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="FaceDetection-Worker",
                daemon=True
            )
            self._thread.start()
        logger.info("Face & Eye Detection Service đã bật.")
        return True

    def start(self) -> bool:
        """Bí danh cho enable() để tương thích giao diện worker/service."""
        return self.enable()

    def disable(self) -> None:
        """Tắt nhận diện khuôn mặt và mắt, giải phóng tài nguyên."""
        self._enabled = False
        with self._frame_lock:
            self._pending_frame = None
            self._pending_seq_id = 0
            self._pending_timestamp = 0.0
        self._notify_faces([], (0, 0), 0, 0.0)  # Xóa các khung đánh dấu trên màn hình
        logger.info("Face & Eye Detection Service đã tắt.")

    def stop(self) -> None:
        """Dừng hoàn toàn tiến trình ngầm."""
        self.disable()
        self._running = False
        self._new_frame_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._detector = None

    def register_callback(self, cb: Callable[..., None]) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def unregister_callback(self, cb: Callable[..., None]) -> None:
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    def submit_frame(self, rgb_frame: np.ndarray, sequence_id: int = 0, timestamp: float = 0.0) -> None:
        """Gửi khung hình xem trước mới nhất vào bộ đệm O(1) (bỏ qua frame cũ khi đang xử lý)."""
        if not self._enabled or rgb_frame is None or getattr(rgb_frame, "size", 0) == 0:
            return
        if sequence_id <= 0:
            self._seq_counter += 1
            sequence_id = self._seq_counter
        if timestamp <= 0.0:
            timestamp = time.time()

        with self._frame_lock:
            self._pending_frame = rgb_frame
            self._pending_seq_id = sequence_id
            self._pending_timestamp = timestamp
        self._new_frame_event.set()

    def _notify_faces(
        self,
        faces: List[DetectedFace],
        frame_shape: Optional[Tuple[int, int]] = None,
        sequence_id: int = 0,
        timestamp: float = 0.0
    ) -> None:
        shape = frame_shape or (0, 0)
        for cb in list(self._callbacks):
            try:
                sig = inspect.signature(cb)
                param_count = len(sig.parameters)
                if param_count >= 4:
                    cb(faces, shape, sequence_id, timestamp)
                elif param_count == 2:
                    cb(faces, shape)
                else:
                    cb(faces)
            except Exception as ex:
                logger.error("Lỗi trong face detection callback: %s", ex, exc_info=True)

    def _worker_loop(self) -> None:
        last_run_t = 0.0

        while self._running:
            # Chờ frame mới
            signaled = self._new_frame_event.wait(timeout=0.2)
            if not self._running:
                break

            if not self._enabled:
                self._new_frame_event.clear()
                time.sleep(0.05)
                continue

            # Kiểm tra throttle tần suất
            now = time.time()
            elapsed = now - last_run_t
            if elapsed < self._target_interval:
                time.sleep(max(0.005, self._target_interval - elapsed))

            # Trích xuất atomic frame mới nhất kèm sequence_id và timestamp
            frame = None
            seq_id = 0
            ts = 0.0
            with self._frame_lock:
                frame = self._pending_frame
                seq_id = self._pending_seq_id
                ts = self._pending_timestamp
                self._pending_frame = None
                self._pending_seq_id = 0
                self._pending_timestamp = 0.0
            self._new_frame_event.clear()

            if frame is None or not self._detector:
                continue

            last_run_t = time.time()
            t_infer_start = time.perf_counter()
            faces = self._detector.detect_faces(frame)
            infer_ms = (time.perf_counter() - t_infer_start) * 1000.0
            h_f, w_f = frame.shape[:2]
            f_shape = (w_f, h_f)

            # Telemetry logging giới hạn tần suất (>= 1.5s)
            now_t = time.time()
            if now_t - self._last_telemetry_time >= 1.5:
                self._last_telemetry_time = now_t
                max_conf = max((f.confidence for f in faces), default=0.0)
                m_path = getattr(self._detector, "model_path", "unknown")
                logger.info(
                    "[FaceDetector] model='%s', seq=%d, shape=(%dx%d), faces=%d, conf_max=%.2f, infer=%.1fms",
                    m_path, seq_id, w_f, h_f, len(faces), max_conf, infer_ms
                )

            if self._enabled:
                self._notify_faces(faces, f_shape, seq_id, ts)
