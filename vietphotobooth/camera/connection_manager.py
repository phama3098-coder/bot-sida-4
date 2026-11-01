"""
1998 TEAM — Photobooth Camera Connection Manager
Central orchestrator managing camera backends, device selection, live view streaming, and error handling.
Maintains priority device persistence and complete backward compatibility with existing components.
"""

import threading
import time
import os
import logging
from collections import deque
from typing import Dict, Any, List, Optional, Tuple, Callable
import numpy as np
from PIL import Image

from vietphotobooth.camera.models import (
    ConnectionState, CameraError, CameraCapabilities, CameraDeviceInfo, FrameData
)
from vietphotobooth.camera.backends.base import CameraBackendBase
from vietphotobooth.camera.backends.directshow_webcam import DirectShowWebcamBackend
from vietphotobooth.camera.backends.digicam_control import DigiCamControlBackend
from vietphotobooth.camera.backends.simulator import SimulatorBackend
from vietphotobooth.camera.backends.device_discovery import DeviceDiscoveryService
from vietphotobooth.core.config import ConfigManager

logger = logging.getLogger("VietPhotoBooth.camera.connection_manager")


class FPSTracker:
    """
    Bộ đo đạc FPS trượt theo thời gian thực (Sliding Window FPS Tracker).
    Đo chính xác tần số khung hình trong cửa sổ thời gian gần nhất (mặc định 1.5 giây),
    tránh phụ thuộc vào số giả định hoặc timer tĩnh.
    """

    def __init__(self, window_seconds: float = 1.5, max_samples: int = 150):
        self._window_seconds = max(0.5, window_seconds)
        self._timestamps = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def tick(self) -> None:
        """Ghi nhận thời điểm đến của một khung hình mới."""
        now = time.time()
        with self._lock:
            self._timestamps.append(now)

    def get_fps(self) -> float:
        """Tính toán FPS thực tế dựa trên các khung hình trong cửa sổ trượt."""
        with self._lock:
            if len(self._timestamps) < 2:
                return 0.0
            now = time.time()
            cutoff = now - self._window_seconds
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) < 2:
                return 0.0
            duration = self._timestamps[-1] - self._timestamps[0]
            if duration <= 0.001:
                return 0.0
            fps = (len(self._timestamps) - 1) / duration
            return round(fps, 1)

    def reset(self) -> None:
        """Đặt lại bộ đệm thời gian khi chuyển đổi hoặc ngắt kết nối camera."""
        with self._lock:
            self._timestamps.clear()


class CameraConnectionManager:
    """Bộ điều phối kết nối máy ảnh thống nhất và an toàn cho 1998 TEAM Photobooth."""

    def __init__(
        self,
        default_backend: str = "simulator",
        device_id: Any = 0,
        device_name: Optional[str] = None,
        config_mgr: Optional[ConfigManager] = None,
        use_saved_config: bool = False
    ):
        self._lock = threading.RLock()
        self.config_mgr = config_mgr or ConfigManager()

        if use_saved_config:
            saved_backend = self.config_mgr.get("camera.preferred_backend", default_backend)
            saved_dev_name = self.config_mgr.get("camera.preferred_device_name", device_name)
            auto_connect = self.config_mgr.get("camera.auto_connect", True)
            self._current_backend_type = saved_backend if auto_connect else default_backend
            self._current_device_name = saved_dev_name or device_name
        else:
            self._current_backend_type = default_backend
            self._current_device_name = device_name

        self._current_device_id = device_id

        self._backend: CameraBackendBase = SimulatorBackend()
        self._adapter = self._backend
        self._last_frame_data: Optional[FrameData] = None
        self._last_jpeg: Optional[bytes] = None

        # Luồng đọc khung hình ngầm tập trung (Single Background Streamer)
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_running: bool = False
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[FrameData] = None
        self._last_latency_ms: float = 0.0
        self._frame_seq_id: int = 0

        # Callbacks cho sự kiện giao diện
        self._on_status_changed_callbacks: List[Callable[[ConnectionState], None]] = []
        self._on_frame_callbacks: List[Callable[[FrameData], None]] = []
        self._on_error_callbacks: List[Callable[[CameraError], None]] = []

        # Đo đạc FPS đọc luồng thực tế (Sliding Window)
        self._read_fps_tracker = FPSTracker(window_seconds=1.5)

        # AI Detection & Autofocus Engine (Shared Single Source of Truth)
        self._face_service = None
        self._face_eye_af_controller = None

        # Khởi tạo backend ban đầu
        self.switch_backend(self._current_backend_type, self._current_device_id, self._current_device_name)

    # -------------------------------------------------------------------------
    # Thuộc tính trạng thái công khai
    # -------------------------------------------------------------------------
    @property
    def current_backend_name(self) -> str:
        return self._current_backend_type

    @property
    def backend_name(self) -> str:
        return self._current_backend_type

    @backend_name.setter
    def backend_name(self, val: str) -> None:
        self._current_backend_type = str(val).lower()

    @property
    def device_index(self) -> int:
        if isinstance(self._current_device_id, int):
            return self._current_device_id
        return 0

    @device_index.setter
    def device_index(self, val: int) -> None:
        self._current_device_id = val

    @property
    def device_name(self) -> str:
        return self._current_device_name or getattr(self._backend, "device_name", self._current_backend_type.upper())

    @device_name.setter
    def device_name(self, val: str) -> None:
        self._current_device_name = val

    @property
    def status(self) -> ConnectionState:
        with self._lock:
            return self._backend.get_status()

    # -------------------------------------------------------------------------
    # AI Detection & Autofocus Engine (Shared Single Source of Truth)
    # -------------------------------------------------------------------------
    @property
    def face_service(self):
        """Dịch vụ nhận diện khuôn mặt YuNet dùng chung (Single Source of Truth)."""
        if self._face_service is None:
            from vietphotobooth.camera.face_detector import FaceDetectionService
            self._face_service = FaceDetectionService(target_detection_fps=12.0)
            if self.is_face_detect_enabled() or self.is_face_eye_af_enabled():
                self._face_service.enable()
        return self._face_service

    @property
    def face_eye_af_controller(self):
        """Bộ điều khiển Face/Eye AF phần mềm kích hoạt phần cứng dùng chung."""
        if self._face_eye_af_controller is None:
            from vietphotobooth.camera.face_eye_af_controller import FaceEyeAFController
            self._face_eye_af_controller = FaceEyeAFController(
                af_trigger_fn=self.trigger_autofocus,
                stability_frames=3,
                stability_px_threshold=20.0,
                movement_px_threshold=35.0,
                cooldown_sec=1.8,
            )
            if self.is_face_eye_af_enabled():
                self._face_eye_af_controller.enable()
        return self._face_eye_af_controller

    def is_face_detect_enabled(self) -> bool:
        """Kiểm tra trạng thái bật/tắt nhận diện khuôn mặt từ cấu hình."""
        return bool(self.config_mgr.get("camera.face_detect_enabled", self.is_face_eye_af_enabled()))

    def set_face_detect_enabled(self, enabled: bool) -> bool:
        """Cập nhật trạng thái nhận diện khuôn mặt và đồng bộ sang FaceDetectionService."""
        self.config_mgr.set("camera.face_detect_enabled", bool(enabled))
        self.config_mgr.save()
        if enabled:
            ok = self.face_service.enable()
            if not ok:
                self.config_mgr.set("camera.face_detect_enabled", False)
                self.config_mgr.save()
                return False
            return True
        else:
            if not self.is_face_eye_af_enabled():
                self.face_service.disable()
            return True

    def is_face_eye_af_enabled(self) -> bool:
        """Kiểm tra trạng thái bật/tắt Face/Eye AF từ cấu hình."""
        return bool(self.config_mgr.get(
            "camera.face_eye_af_enabled",
            self.config_mgr.get("kiosk.enable_face_eye_af", True)
        ))

    def set_face_eye_af_enabled(self, enabled: bool) -> bool:
        """Cập nhật trạng thái Face/Eye AF và đồng bộ sang controller."""
        val = bool(enabled)
        self.config_mgr.set("camera.face_eye_af_enabled", val)
        self.config_mgr.set("kiosk.enable_face_eye_af", val)
        self.config_mgr.save()
        if val:
            ok = self.face_service.enable()
            if not ok:
                self.config_mgr.set("camera.face_eye_af_enabled", False)
                self.config_mgr.set("kiosk.enable_face_eye_af", False)
                self.config_mgr.save()
                return False
            self.face_eye_af_controller.set_af_trigger_function(self.trigger_autofocus)
            self.face_eye_af_controller.enable()
            return True
        else:
            self.face_eye_af_controller.disable()
            if not self.is_face_detect_enabled():
                self.face_service.disable()
            return True

    def start_stream(self) -> None:
        """Khởi động luồng đọc Live View ngầm tập trung nếu chưa hoạt động."""
        with self._lock:
            if self._stream_running and self._stream_thread and self._stream_thread.is_alive():
                return
            self._stream_running = True
            self._stream_thread = threading.Thread(
                target=self._stream_loop,
                name="VietPhotoBooth-LiveView-Streamer",
                daemon=True
            )
            self._stream_thread.start()
            logger.info("Đã kích hoạt background LiveView Streamer.")

    def stop_stream(self, timeout: float = 1.0) -> None:
        """Dừng luồng đọc Live View ngầm an toàn và giải phóng tài nguyên."""
        self._stream_running = False
        t = self._stream_thread
        if t and t.is_alive():
            t.join(timeout=timeout)
        self._stream_thread = None
        with self._frame_lock:
            self._latest_frame = None

    def _stream_loop(self) -> None:
        """
        Vòng lặp đọc frame ngầm (Worker Thread) duy nhất:
        - Tách biệt hoàn toàn I/O camera khỏi UI thread.
        - Không tích lũy hàng đợi (Single-frame buffer drop frame cũ).
        - Chuẩn hóa kích thước preview (A3) tránh làm nghẽn GUI với ảnh 6K.
        """
        logger.info("LiveView Streamer loop bắt đầu hoạt động.")
        while self._stream_running:
            if not self.is_connected():
                time.sleep(0.06)
                continue

            t_start = time.perf_counter()
            frame = None
            try:
                frame = self._backend.read_frame()
            except Exception as e:
                logger.debug(f"Streamer read frame error: {e}")

            t_end = time.perf_counter()
            latency_ms = (t_end - t_start) * 1000.0

            if frame and frame.is_valid:
                self._read_fps_tracker.tick()
                self._frame_seq_id += 1
                if not getattr(frame, "sequence_id", 0):
                    frame.sequence_id = self._frame_seq_id
                # Tự động giải mã JPEG sang RGB trên background thread nếu backend chỉ cung cấp JPEG
                if not frame.has_rgb and frame.has_jpeg:
                    try:
                        import cv2
                        bgr = cv2.imdecode(np.frombuffer(frame.jpeg, np.uint8), cv2.IMREAD_COLOR)
                        if bgr is not None:
                            frame.rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                            frame.width = frame.rgb.shape[1]
                            frame.height = frame.rgb.shape[0]
                    except Exception as ex:
                        logger.debug(f"Streamer fallback JPEG decode error: {ex}")

                # A3: Giới hạn độ phân giải preview hợp lý (<= 1280x720) cho UI viewport
                if frame.has_rgb and len(frame.rgb.shape) >= 2:
                    h, w = frame.rgb.shape[:2]
                    if w > 1280 or h > 720:
                        import cv2
                        scale = min(1280.0 / w, 720.0 / h)
                        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                        preview_rgb = cv2.resize(frame.rgb, (nw, nh), interpolation=cv2.INTER_LINEAR)
                        frame = FrameData(
                            rgb=preview_rgb,
                            jpeg=frame.jpeg,
                            width=nw,
                            height=nh,
                            fps=frame.fps,
                            sequence_id=frame.sequence_id,
                            timestamp=frame.timestamp,
                            is_valid=True
                        )

                with self._frame_lock:
                    self._latest_frame = frame
                    self._last_frame_data = frame
                    self._last_latency_ms = latency_ms

                self._notify_frame(frame)

                # Duy trì tốc độ ổn định theo khả năng tối đa của backend (Nikon MAID: ~38 FPS / 26ms, backend khác: ~30 FPS / 33ms)
                target_interval = 0.026 if self._current_backend_type == "nikon_maid" else 0.033
                elapsed = time.perf_counter() - t_start
                sleep_s = max(0.002, target_interval - elapsed)
                time.sleep(sleep_s)
            else:
                with self._frame_lock:
                    self._latest_frame = None
                time.sleep(0.06)

        logger.info("LiveView Streamer loop đã dừng an toàn.")

    # -------------------------------------------------------------------------
    # Điều phối kết nối & Chuyển đổi backend an toàn
    # -------------------------------------------------------------------------
    def switch_backend(
        self,
        backend_type: Optional[str] = None,
        device_id: Any = None,
        device_name: Optional[str] = None,
        backend: Optional[str] = None,
        device_index: Any = None
    ) -> bool:
        """
        Quy trình chuẩn khi chuyển đổi backend:
        1. Dừng background stream thread của backend hiện tại.
        2. Dừng Live View và giải phóng tài nguyên phần cứng cũ.
        3. Khởi tạo backend mới.
        4. Kết nối tới thiết bị yêu cầu (hoặc thiết bị ưu tiên).
        5. Kích hoạt Live View và background streamer.
        """
        resolved_backend = backend or backend_type or "simulator"
        resolved_device_id = device_index if device_index is not None else (device_id if device_id is not None else 0)

        # 1. Dừng background streamer trước khi ngắt kết nối
        self.stop_stream()

        with self._lock:
            b_type = str(resolved_backend).lower().strip()
            logger.info(f"Yêu cầu chuyển đổi Camera Backend sang: '{b_type}', thiết bị: '{device_name or resolved_device_id}'")

            # 2. Dừng Live View & ngắt kết nối backend cũ
            if self._backend:
                try:
                    self._backend.stop_live_view()
                    self._backend.disconnect()
                except Exception as e:
                    logger.warning(f"Lỗi khi ngắt kết nối backend cũ: {e}")

            with self._frame_lock:
                self._latest_frame = None
            self._last_frame_data = None
            self._last_jpeg = None
            self._read_fps_tracker.reset()

            self._current_backend_type = b_type
            self._current_device_id = resolved_device_id
            self._current_device_name = device_name

            # 3. Khởi tạo backend mới phù hợp
            if b_type == "directshow":
                self._backend = DirectShowWebcamBackend(
                    device_index=self._current_device_id if isinstance(self._current_device_id, int) else 0,
                    device_name=self._current_device_name
                )
                target_id = self._current_device_name if self._current_device_name else self._current_device_id
            elif b_type in ("digicam", "dslr"):
                self._backend = DigiCamControlBackend()
                target_id = None
            elif b_type in ("nikon_maid", "nikon", "nikon_d780"):
                from vietphotobooth.camera.backends.nikon_maid import NikonD780Backend
                self._backend = NikonD780Backend()
                target_id = self._current_device_name or self._current_device_id or "nikon_d780_usb"
            else:
                self._current_backend_type = "simulator"
                self._backend = SimulatorBackend()
                target_id = None

            self._adapter = self._backend

            # 4. Kết nối tới thiết bị
            success = self._backend.connect(target_id)
            if success:
                self._backend.start_live_view()
                self.start_stream()

            # 5. Lưu lại thiết lập ưu tiên nếu kết nối thành công và là thiết bị thật
            if success and self._current_backend_type != "simulator":
                self._save_preferred_device(self._current_backend_type, target_id, self._current_device_name)

            self._notify_status_changed(self._backend.get_status())
            err = self._backend.get_error()
            if err:
                self._notify_error(err)

            if success and hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller:
                self._face_eye_af_controller.set_af_trigger_function(self.trigger_autofocus)

            return success

    def connect(self, device_id: Any = None) -> bool:
        """Kết nối lại thiết bị hiện tại."""
        with self._lock:
            target = device_id if device_id is not None else (self._current_device_name or self._current_device_id)
            ok = self._backend.connect(target)
            if ok:
                self._backend.start_live_view()
                self.start_stream()
            self._notify_status_changed(self._backend.get_status())
            return ok

    def disconnect(self) -> None:
        """Ngắt kết nối an toàn."""
        self.stop_stream()
        with self._lock:
            if self._backend:
                self._backend.stop_live_view()
                self._backend.disconnect()
                with self._frame_lock:
                    self._latest_frame = None
                self._last_frame_data = None
                self._last_jpeg = None
                self._read_fps_tracker.reset()
                self._notify_status_changed(ConnectionState.DISCONNECTED)

    def is_connected(self) -> bool:
        with self._lock:
            st = self._backend.get_status()
            return st in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE, ConnectionState.CONNECTED_NO_FRAME)

    def get_last_error(self) -> str:
        with self._lock:
            err = self._backend.get_error()
            if err:
                return err.message
            return ""

    # -------------------------------------------------------------------------
    # Dò quét thiết bị (Device Discovery)
    # -------------------------------------------------------------------------
    def discover_devices(self, backend_type: Optional[str] = None) -> List[CameraDeviceInfo]:
        """Dò quét thiết bị cho một backend cụ thể hoặc backend đang chọn."""
        b_type = (backend_type or self._current_backend_type).lower()
        if b_type == "directshow":
            return DirectShowWebcamBackend().discover_devices()
        elif b_type in ("digicam", "dslr"):
            return DigiCamControlBackend().discover_devices()
        elif b_type in ("nikon_maid", "nikon", "nikon_d780"):
            from vietphotobooth.camera.backends.nikon_maid import NikonD780Backend
            return NikonD780Backend().discover_devices()
        else:
            return SimulatorBackend().discover_devices()

    def detect_all_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Dò quét toàn bộ thiết bị cho tất cả backend (tương thích CameraManager cũ)."""
        all_devs = DeviceDiscoveryService.discover_all_devices()
        results: Dict[str, List[Dict[str, Any]]] = {}
        for b_name, devs in all_devs.items():
            results[b_name] = [d.to_dict() for d in devs]
        return results

    # -------------------------------------------------------------------------
    # Đọc khung hình Live View (Thread-safe, Non-blocking)
    # -------------------------------------------------------------------------
    def get_frame_data(self) -> Optional[FrameData]:
        """Đọc đối tượng FrameData đầy đủ (Ưu tiên lấy từ background stream buffer, không bao giờ chặn GUI thread)."""
        with self._frame_lock:
            if self._latest_frame is not None and self._latest_frame.is_valid:
                return self._latest_frame

        if not self.is_connected():
            return None

        # Khi streamer ngầm đang chạy, ưu tiên cache hoặc đợi ngắn ở lần đầu khởi động
        if self._stream_running:
            if self._last_frame_data is not None and self._last_frame_data.is_valid:
                return self._last_frame_data
            # Nếu vừa mới kết nối và thread stream chưa kịp nạp frame đầu tiên, chờ tối đa 120ms
            t_wait = 0.0
            while self._stream_running and t_wait < 0.12:
                time.sleep(0.01)
                t_wait += 0.01
                with self._frame_lock:
                    if self._latest_frame is not None and self._latest_frame.is_valid:
                        return self._latest_frame
            return self._last_frame_data

        with self._lock:
            if not self._backend:
                return None
            frame = self._backend.read_frame()
            if frame and frame.is_valid:
                self._read_fps_tracker.tick()
                self._last_frame_data = frame
                self._notify_frame(frame)
                return frame
            return None

    def get_read_fps(self) -> float:
        """Lấy tốc độ đọc khung hình thực tế từ phần cứng (Read FPS)."""
        return self._read_fps_tracker.get_fps()

    def get_liveview_rgb(self) -> Optional[np.ndarray]:
        """Lấy mảng RGB numpy cho viewport giao diện PySide6 (non-blocking, siêu mượt)."""
        fd = self.get_frame_data()
        if fd and fd.has_rgb:
            return fd.rgb
        return None

    def get_liveview(self) -> Optional[bytes]:
        """Lấy khung hình xem trước định dạng JPEG bytes (tương thích code cũ)."""
        fd = self.get_frame_data()
        if fd:
            if fd.has_jpeg:
                return fd.jpeg
            elif fd.has_rgb:
                import cv2
                bgr = cv2.cvtColor(fd.rgb, cv2.COLOR_RGB2BGR)
                ok, enc = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if ok:
                    self._last_jpeg = enc.tobytes()
                    return self._last_jpeg
        return self._last_jpeg

    # -------------------------------------------------------------------------
    # Điều khiển lấy nét tự động (Autofocus Flow)
    # -------------------------------------------------------------------------
    def trigger_autofocus(
        self,
        callback: Optional[Callable[[bool, str], None]] = None,
        target_point: Optional[Tuple[float, float]] = None,
        frame_size: Optional[Tuple[float, float]] = None
    ) -> None:
        """Kích hoạt lấy nét tự động một lần (One-shot AF, non-blocking)."""
        def _wrapper(success: bool, message: str):
            if callback:
                try:
                    callback(success, message)
                except Exception as ex:
                    logger.debug(f"Error in autofocus callback: {ex}")

        with self._lock:
            if not self.is_connected():
                if callback:
                    callback(False, "Máy ảnh chưa được kết nối.")
                return

            if hasattr(self._backend, "autofocus"):
                import inspect
                sig = inspect.signature(self._backend.autofocus)
                kwargs = {"callback": _wrapper}
                if "target_point" in sig.parameters:
                    kwargs["target_point"] = target_point
                if "frame_size" in sig.parameters:
                    kwargs["frame_size"] = frame_size
                self._backend.autofocus(**kwargs)
            else:
                if callback:
                    callback(False, "Thiết bị hiện tại không hỗ trợ điều khiển lấy nét tự động.")

    def cancel_autofocus(self) -> bool:
        """Hủy thao tác lấy nét nếu đang diễn ra."""
        with self._lock:
            if hasattr(self._backend, "cancel_autofocus"):
                return self._backend.cancel_autofocus()
            return False

    def diagnose_autofocus(
        self,
        target_point: Optional[Tuple[float, float]] = None,
        frame_size: Optional[Tuple[float, float]] = None
    ) -> Dict[str, Any]:
        """
        Thực hiện một chu trình chẩn đoán AF chuyên sâu theo chuẩn Nikon MAID:
        - Kiểm tra trạng thái kết nối, chế độ MF/AF, trạng thái Live View.
        - Gửi tối đa một lệnh AF qua đường gọi MAID đã xác minh.
        - Ghi lại thời điểm gửi, mã trả về tức thời và kết quả hoàn tất.
        - Phân loại rõ theo các tiêu chí: MAID_REJECTED, MAID_NOT_COMPLETED, SUCCESS_IN_FOCUS, v.v.
        - Tuyệt đối không tự chụp ảnh, không gửi lại liên tục.
        """
        with self._lock:
            if not self.is_connected():
                return {
                    "success": False,
                    "category": "MAID_REJECTED",
                    "message": "Máy ảnh chưa được kết nối.",
                    "duration_ms": 0.0,
                    "backend": self._current_backend_type,
                }

            if hasattr(self._backend, "diagnose_af"):
                import inspect
                sig = inspect.signature(self._backend.diagnose_af)
                kwargs = {"target_point": target_point}
                if "frame_size" in sig.parameters:
                    kwargs["frame_size"] = frame_size
                return self._backend.diagnose_af(**kwargs)
            elif hasattr(self._backend, "autofocus"):
                t0 = time.perf_counter()
                ok, msg = self._backend.autofocus()
                dur_ms = (time.perf_counter() - t0) * 1000.0
                return {
                    "success": ok,
                    "category": "SUCCESS_IN_FOCUS" if ok else "MAID_REJECTED",
                    "message": msg,
                    "duration_ms": dur_ms,
                    "backend": self._current_backend_type,
                }
            else:
                return {
                    "success": False,
                    "category": "MAID_REJECTED",
                    "message": "Thiết bị hiện tại không hỗ trợ điều khiển lấy nét tự động.",
                    "duration_ms": 0.0,
                    "backend": self._current_backend_type,
                }

    # -------------------------------------------------------------------------
    # Chụp ảnh tĩnh chất lượng cao (Capture Flow)
    # -------------------------------------------------------------------------
    def capture(self, autofocus_first: bool = False) -> Optional[Image.Image]:
        """Chụp một ảnh độ phân giải cao."""
        with self._lock:
            try:
                if not self.is_connected():
                    logger.warning("Camera chưa kết nối, thử kết nối lại...")
                    self._backend.connect(self._current_device_id)

                if hasattr(self._backend, "capture_photo"):
                    import inspect
                    sig = inspect.signature(self._backend.capture_photo)
                    if "autofocus_first" in sig.parameters:
                        img = self._backend.capture_photo(autofocus_first=autofocus_first)
                    else:
                        img = self._backend.capture_photo()
                else:
                    img = None

                if img is None:
                    logger.error(f"Backend {self._current_backend_type} không trả về ảnh chụp.")
                return img
            except Exception as e:
                logger.error(f"Lỗi ngoại lệ khi chụp ảnh qua backend {self._current_backend_type}: {e}")
                return None

    def capture_photo(self, save_path: Optional[str] = None, autofocus_first: bool = False) -> Tuple[bool, Optional[Image.Image]]:
        """Chụp ảnh và lưu an toàn vào đĩa (kiểm tra tính toàn vẹn của tệp)."""
        img = self.capture(autofocus_first=autofocus_first)
        if img:
            if save_path:
                try:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    img.save(save_path, "JPEG", quality=95)
                    # Xác nhận tệp ảnh tồn tại trên đĩa và có kích thước hợp lệ
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
                        return True, img
                    else:
                        logger.error(f"Tệp ảnh {save_path} chưa được lưu thành công trên đĩa.")
                        return False, img
                except Exception as e:
                    logger.error(f"Không thể lưu ảnh vào {save_path}: {e}")
                    return False, img
            return True, img
        return False, None

    # -------------------------------------------------------------------------
    # Báo cáo chẩn đoán & Thông tin thiết bị
    # -------------------------------------------------------------------------
    def get_info(self) -> Dict[str, Any]:
        """Lấy thông tin tổng hợp của thiết bị đang hoạt động (FPS trung thực, phân biệt Live View vs Chụp)."""
        with self._lock:
            caps = self._backend.get_capabilities()
            params = self._backend.get_parameters()
            st = self._backend.get_status()
            err = self._backend.get_error()

            is_sim = (self._current_backend_type == "simulator")
            is_digicam = (self._current_backend_type in ("digicam", "dslr"))
            read_fps = self._read_fps_tracker.get_fps()

            # Source FPS: Chỉ lấy nếu backend thực sự cung cấp hoặc đã đo được
            reported_fps = getattr(caps, "max_fps", 30.0)
            if is_digicam and st == ConnectionState.CONNECTED_NO_FRAME:
                source_fps = None
            else:
                source_fps = float(reported_fps) if reported_fps else None

            # Live view resolution vs Capture resolution
            live_w, live_h = 0, 0
            with self._frame_lock:
                if self._latest_frame and self._latest_frame.is_valid:
                    live_w, live_h = self._latest_frame.width, self._latest_frame.height
            if live_w == 0 and self._last_frame_data and self._last_frame_data.is_valid:
                live_w, live_h = self._last_frame_data.width, self._last_frame_data.height

            if is_digicam:
                capture_res = (6000, 4000)
            elif caps.supported_resolutions:
                capture_res = caps.supported_resolutions[0]
            else:
                capture_res = (live_w or 1920, live_h or 1080)

            # Live View Active state: chỉ True khi thực sự có luồng hình ảnh hoặc simulator
            is_lv_active = (st == ConnectionState.LIVE_VIEW_ACTIVE) and (read_fps > 0 or is_sim)

            if is_digicam and st in (ConnectionState.CONNECTED, ConnectionState.CONNECTED_NO_FRAME) and not is_lv_active:
                status_display = "Sẵn sàng (Chế độ chụp tĩnh Tethered 6000×4000 • Live View: Tắt)"
            elif is_sim and st in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE):
                status_display = "Mô phỏng đang chạy"
            else:
                status_display = err.message if (err and st == ConnectionState.ERROR) else st.display_name

            d = {
                "name": self.device_name,
                "brand": "Simulator" if is_sim else ("Nikon" if "nikon" in self.device_name.lower() else "Logitech" if "logi" in self.device_name.lower() else "Generic"),
                "model": "1998 Simulator (Mô Phỏng)" if is_sim else self.device_name,
                "backend_name": self._backend.display_name,
                "active_backend_id": self._current_backend_type,
                "device_index": self.device_index,
                "device_name": self.device_name,
                "is_simulator": is_sim,
                "is_connected": self.is_connected(),
                "status": status_display,
                "connection_state": st.value,
                "last_error": err.message if err else "",
                "error_code": err.code if err else "",
                "error_suggestion": err.suggestion if err else "",
                "capabilities": caps.to_dict(),
                "parameters": params,
                "actual_resolution": (live_w, live_h) if is_lv_active else (0, 0),
                "live_view_resolution": (live_w, live_h),
                "capture_resolution": capture_res,
                "is_live_view_active": is_lv_active,
                "read_fps": read_fps if is_lv_active else 0.0,
                "reported_fps": source_fps or 0.0,
                "source_fps": source_fps,
                "fps": read_fps if is_lv_active else 0.0,
                "latency_ms": getattr(self, "_last_latency_ms", 0.0)
            }
            return d

    def get_diagnostic_report(self) -> Dict[str, Any]:
        """Tạo báo cáo chẩn đoán camera toàn diện."""
        from vietphotobooth.camera.diagnostics import run_full_camera_diagnostics
        return run_full_camera_diagnostics()

    def get_parameters(self) -> Dict[str, Any]:
        with self._lock:
            return self._backend.get_parameters()

    def set_parameters(self, params: Dict[str, Any]) -> bool:
        with self._lock:
            return self._backend.set_parameters(params)

    def close(self) -> None:
        """Đóng an toàn kết nối và dừng mọi worker."""
        self.stop_stream()
        self.disconnect()
        if hasattr(self, "_face_eye_af_controller") and self._face_eye_af_controller:
            try:
                self._face_eye_af_controller.disable()
            except Exception:
                pass
        if hasattr(self, "_face_service") and self._face_service:
            try:
                self._face_service.stop()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Lưu và phục hồi thiết bị ưu tiên
    # -------------------------------------------------------------------------
    def _save_preferred_device(self, backend: str, device_id: Any, device_name: Optional[str]) -> None:
        try:
            self.config_mgr.set("camera.preferred_backend", backend)
            if device_name:
                self.config_mgr.set("camera.preferred_device_name", device_name)
            self.config_mgr.set("camera.auto_connect", True)
            self.config_mgr.save()
        except Exception as e:
            logger.warning(f"Không thể lưu thiết bị ưu tiên: {e}")

    # -------------------------------------------------------------------------
    # Quản lý Callbacks & Signals
    # -------------------------------------------------------------------------
    def register_status_callback(self, cb: Callable[[ConnectionState], None]) -> None:
        if cb not in self._on_status_changed_callbacks:
            self._on_status_changed_callbacks.append(cb)

    def register_frame_callback(self, cb: Callable[[FrameData], None]) -> None:
        if cb not in self._on_frame_callbacks:
            self._on_frame_callbacks.append(cb)

    def register_error_callback(self, cb: Callable[[CameraError], None]) -> None:
        if cb not in self._on_error_callbacks:
            self._on_error_callbacks.append(cb)

    def _notify_status_changed(self, st: ConnectionState) -> None:
        for cb in self._on_status_changed_callbacks:
            try:
                cb(st)
            except Exception:
                pass

    def _notify_frame(self, frame: FrameData) -> None:
        for cb in self._on_frame_callbacks:
            try:
                cb(frame)
            except Exception:
                pass

    def _notify_error(self, err: CameraError) -> None:
        for cb in self._on_error_callbacks:
            try:
                cb(err)
            except Exception:
                pass
