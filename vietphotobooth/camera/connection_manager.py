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

        # Callbacks cho sự kiện giao diện
        self._on_status_changed_callbacks: List[Callable[[ConnectionState], None]] = []
        self._on_frame_callbacks: List[Callable[[FrameData], None]] = []
        self._on_error_callbacks: List[Callable[[CameraError], None]] = []

        # Đo đạc FPS đọc luồng thực tế (Sliding Window)
        self._read_fps_tracker = FPSTracker(window_seconds=1.5)

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
        1. Dừng Live View của backend hiện tại.
        2. Giải phóng tài nguyên phần cứng cũ.
        3. Khởi tạo backend mới.
        4. Kết nối tới thiết bị yêu cầu (hoặc thiết bị ưu tiên).
        5. Cập nhật trạng thái an toàn và kích hoạt callback.
        """
        resolved_backend = backend or backend_type or "simulator"
        resolved_device_id = device_index if device_index is not None else (device_id if device_id is not None else 0)

        with self._lock:
            b_type = str(resolved_backend).lower().strip()
            logger.info(f"Yêu cầu chuyển đổi Camera Backend sang: '{b_type}', thiết bị: '{device_name or resolved_device_id}'")

            # 1. Dừng Live View & ngắt kết nối backend cũ
            if self._backend:
                try:
                    self._backend.stop_live_view()
                    self._backend.disconnect()
                except Exception as e:
                    logger.warning(f"Lỗi khi ngắt kết nối backend cũ: {e}")

            self._last_frame_data = None
            self._last_jpeg = None
            self._read_fps_tracker.reset()

            self._current_backend_type = b_type
            self._current_device_id = resolved_device_id
            self._current_device_name = device_name

            # 2. Khởi tạo backend mới phù hợp
            if b_type == "directshow":
                self._backend = DirectShowWebcamBackend(
                    device_index=self._current_device_id if isinstance(self._current_device_id, int) else 0,
                    device_name=self._current_device_name
                )
                target_id = self._current_device_name if self._current_device_name else self._current_device_id
            elif b_type in ("digicam", "dslr"):
                self._backend = DigiCamControlBackend()
                target_id = None
            else:
                self._current_backend_type = "simulator"
                self._backend = SimulatorBackend()
                target_id = None

            self._adapter = self._backend

            # 3. Kết nối tới thiết bị
            success = self._backend.connect(target_id)
            if success:
                self._backend.start_live_view()

            # 4. Lưu lại thiết lập ưu tiên nếu kết nối thành công và là thiết bị thật
            if success and self._current_backend_type != "simulator":
                self._save_preferred_device(self._current_backend_type, target_id, self._current_device_name)

            self._notify_status_changed(self._backend.get_status())
            err = self._backend.get_error()
            if err:
                self._notify_error(err)

            return success

    def connect(self, device_id: Any = None) -> bool:
        """Kết nối lại thiết bị hiện tại."""
        with self._lock:
            target = device_id if device_id is not None else (self._current_device_name or self._current_device_id)
            ok = self._backend.connect(target)
            if ok:
                self._backend.start_live_view()
            self._notify_status_changed(self._backend.get_status())
            return ok

    def disconnect(self) -> None:
        """Ngắt kết nối an toàn."""
        with self._lock:
            if self._backend:
                self._backend.stop_live_view()
                self._backend.disconnect()
                self._last_frame_data = None
                self._last_jpeg = None
                self._read_fps_tracker.reset()
                self._notify_status_changed(ConnectionState.DISCONNECTED)

    def is_connected(self) -> bool:
        with self._lock:
            st = self._backend.get_status()
            return st in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE)

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
    # Đọc khung hình Live View (Thread-safe)
    # -------------------------------------------------------------------------
    def get_frame_data(self) -> Optional[FrameData]:
        """Đọc đối tượng FrameData đầy đủ."""
        with self._lock:
            if not self._backend:
                return None
            frame = self._backend.read_frame()
            if frame and frame.is_valid:
                self._read_fps_tracker.tick()
                self._last_frame_data = frame
                self._notify_frame(frame)
                return frame
            # Nếu backend không trả về frame hợp lệ, trả về None (không trả frame cũ/giả)
            return None

    def get_read_fps(self) -> float:
        """Lấy tốc độ đọc khung hình thực tế từ phần cứng (Read FPS)."""
        return self._read_fps_tracker.get_fps()

    def get_liveview_rgb(self) -> Optional[np.ndarray]:
        """Lấy mảng RGB numpy cho viewport giao diện PySide6 (siêu mượt)."""
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
    # Chụp ảnh tĩnh chất lượng cao (Capture Flow)
    # -------------------------------------------------------------------------
    def capture(self) -> Optional[Image.Image]:
        """Chụp một ảnh độ phân giải cao."""
        with self._lock:
            try:
                if not self.is_connected():
                    logger.warning("Camera chưa kết nối, thử kết nối lại...")
                    self._backend.connect(self._current_device_id)

                img = self._backend.capture_photo()
                if img is None:
                    logger.error(f"Backend {self._current_backend_type} không trả về ảnh chụp.")
                return img
            except Exception as e:
                logger.error(f"Lỗi ngoại lệ khi chụp ảnh qua backend {self._current_backend_type}: {e}")
                return None

    def capture_photo(self, save_path: Optional[str] = None) -> Tuple[bool, Optional[Image.Image]]:
        """Chụp ảnh và lưu an toàn vào đĩa (kiểm tra tính toàn vẹn của tệp)."""
        img = self.capture()
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
        """Lấy thông tin tổng hợp của thiết bị đang hoạt động."""
        with self._lock:
            caps = self._backend.get_capabilities()
            params = self._backend.get_parameters()
            st = self._backend.get_status()
            err = self._backend.get_error()

            is_sim = (self._current_backend_type == "simulator")
            read_fps = self._read_fps_tracker.get_fps()
            reported_fps = float(getattr(caps, "max_fps", 30.0) or 30.0)

            d = {
                "name": self.device_name,
                "brand": "Simulator" if is_sim else ("Nikon" if "nikon" in self.device_name.lower() else "Logitech" if "logi" in self.device_name.lower() else "Generic"),
                "model": "1998 Simulator (Mô Phỏng)" if is_sim else self.device_name,
                "backend_name": self._backend.display_name,
                "active_backend_id": self._current_backend_type,
                "device_index": self.device_index,
                "device_name": self.device_name,
                "is_simulator": is_sim,
                "status": "Mô phỏng đang chạy" if (is_sim and st in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE)) else st.display_name,
                "connection_state": st.value,
                "last_error": err.message if err else "",
                "capabilities": caps.to_dict(),
                "parameters": params,
                "actual_resolution": (caps.supported_resolutions[0] if caps.supported_resolutions else (0, 0)),
                "read_fps": read_fps,
                "reported_fps": reported_fps,
                "fps": read_fps or reported_fps or 30.0
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
        """Đóng an toàn kết nối."""
        self.disconnect()

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
