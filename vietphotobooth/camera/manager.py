"""
VietPhotoBooth Camera Manager
Central orchestrator for camera backends, device discovery, thread-safe capture, and error recovery.
"""

import threading
import time
from typing import Dict, Any, List, Optional
from PIL import Image
from vietphotobooth.camera.base import CameraAdapter, CameraInfo
from vietphotobooth.camera.simulator import CameraSimulator
from vietphotobooth.camera.directshow import DirectShowCameraAdapter
from vietphotobooth.camera.digicam import DigiCamControlAdapter
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class CameraManager:
    def __init__(self, default_backend: str = "simulator", device_index: int = 0):
        self._lock = threading.Lock()
        self.backend_name = default_backend
        self.device_index = device_index
        self._adapter: CameraAdapter = CameraSimulator()
        self._last_liveview_frame: Optional[bytes] = None
        self._set_backend(default_backend, device_index)

    def _set_backend(self, backend: str, device_index: int = 0) -> bool:
        with self._lock:
            if self._adapter:
                try:
                    self._adapter.disconnect()
                except Exception as e:
                    logger.warning(f"Lỗi khi ngắt kết nối adapter cũ: {e}")

            self.backend_name = backend.lower()
            self.device_index = device_index

            if self.backend_name == "directshow":
                self._adapter = DirectShowCameraAdapter(device_index=device_index)
            elif self.backend_name in ("digicam", "dslr"):
                self._adapter = DigiCamControlAdapter()
            else:
                self.backend_name = "simulator"
                self._adapter = CameraSimulator()

            connected = self._adapter.connect(device_id=device_index)
            logger.info(f"Đã khởi tạo Camera Backend: {self.backend_name} (Kết nối: {connected})")
            return connected

    def switch_backend(self, backend: str, device_index: int = 0) -> bool:
        return self._set_backend(backend, device_index)

    def is_connected(self) -> bool:
        with self._lock:
            return self._adapter.is_connected()

    def get_info(self) -> Dict[str, Any]:
        with self._lock:
            info = self._adapter.get_info()
            d = info.to_dict()
            d["active_backend_id"] = self.backend_name
            d["device_index"] = self.device_index
            return d

    def detect_all_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Dò quét toàn bộ thiết bị từ tất cả các backend."""
        devices = {
            "simulator": CameraSimulator().detect_devices(),
            "directshow": DirectShowCameraAdapter().detect_devices(),
            "digicam": DigiCamControlAdapter().detect_devices()
        }
        return devices

    def capture(self) -> Optional[Image.Image]:
        """Chụp ảnh an toàn với cơ chế bắt lỗi và không làm treo ứng dụng."""
        with self._lock:
            try:
                if not self._adapter.is_connected():
                    logger.warning("Camera chưa kết nối, thử kết nối lại...")
                    self._adapter.connect(self.device_index)

                img = self._adapter.capture_image()
                if img is None:
                    logger.error(f"Backend {self.backend_name} không trả về ảnh.")
                return img
            except Exception as e:
                logger.error(f"Lỗi nghiêm trọng khi chụp ảnh qua backend {self.backend_name}: {e}")
                return None

    def get_liveview(self) -> Optional[bytes]:
        """Lấy khung hình xem trước (Live View)."""
        with self._lock:
            try:
                frame = self._adapter.get_liveview_frame()
                if frame:
                    self._last_liveview_frame = frame
                return frame or self._last_liveview_frame
            except Exception:
                return self._last_liveview_frame

    def get_liveview_rgb(self) -> Optional[Any]:
        """Lấy khung hình xem trước RGB numpy array phục vụ desktop GUI tối ưu hiệu năng."""
        with self._lock:
            try:
                if hasattr(self._adapter, "get_liveview_rgb_frame"):
                    rgb = self._adapter.get_liveview_rgb_frame()
                    if rgb is not None:
                        return rgb
                # Fallback qua JPEG bytes nếu adapter chỉ trả về bytes
                frame_bytes = self._adapter.get_liveview_frame()
                if frame_bytes:
                    import cv2
                    import numpy as np
                    nparr = np.frombuffer(frame_bytes, np.uint8)
                    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if bgr is not None:
                        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                return None
            except Exception:
                return None

    @property
    def current_backend_name(self) -> str:
        return self.backend_name

    def capture_photo(self, save_path: Optional[str] = None) -> tuple[bool, Optional[Image.Image]]:
        """Chụp ảnh chất lượng cao và tùy chọn lưu vào file đĩa."""
        img = self.capture()
        if img:
            if save_path:
                try:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    img.save(save_path, "JPEG", quality=95)
                except Exception as e:
                    logger.error(f"Không thể lưu ảnh vào {save_path}: {e}")
            return True, img
        return False, None

    def close(self):
        """Đóng kết nối an toàn với máy ảnh."""
        with self._lock:
            if self._adapter:
                try:
                    self._adapter.disconnect()
                except Exception:
                    pass

    def get_parameters(self) -> Dict[str, Any]:
        with self._lock:
            return self._adapter.get_parameters()

    def set_parameters(self, params: Dict[str, Any]) -> bool:
        with self._lock:
            return self._adapter.set_parameters(params)
