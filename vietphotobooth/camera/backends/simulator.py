"""
1998 TEAM — Photobooth Simulator Camera Backend
Safe software simulation for testing user interface, capture flow, and performance without hardware.
Clearly labeled as 'Mô Phỏng' — never masquerades as a physical hardware device.
"""

import time
import io
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, List, Optional, Tuple, Callable

from vietphotobooth.camera.backends.base import CameraBackendBase
from vietphotobooth.camera.models import (
    ConnectionState, CameraError, CameraCapabilities, CameraDeviceInfo, FrameData
)


class SimulatorBackend(CameraBackendBase):
    """Bộ giả lập máy ảnh phục vụ kiểm thử giao diện Studio 1998."""

    def __init__(self, name: str = "1998 Studio — Camera Simulator (Mô Phỏng)"):
        self._name = name
        self._connected = True
        self._status = ConnectionState.CONNECTED
        self._error: Optional[CameraError] = None
        self._frame_count = 0
        self._live_view_active = True
        self._last_frame_time = 0.0
        self._cached_frame_data: Optional[FrameData] = None
        self._target_fps = 30.0
        self._min_frame_interval = 1.0 / self._target_fps  # ~0.0333s (giới hạn 30 FPS)

        self._params = {
            "iso": "400",
            "shutter_speed": "1/200",
            "aperture": "f/2.8",
            "white_balance": "5500K"
        }

    @property
    def backend_type(self) -> str:
        return "simulator"

    @property
    def device_name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return "Simulator (Mô Phỏng Giao Diện)"

    def discover_devices(self) -> List[CameraDeviceInfo]:
        caps = CameraCapabilities(
            can_capture=True,
            can_liveview=True,
            can_download=True,
            can_adjust_parameters=True,
            supported_resolutions=[(1920, 1080), (1280, 720)],
            supported_fps=[30.0, 60.0],
            format_name="Simulator RGB"
        )
        dev = CameraDeviceInfo(
            id=0,
            name=self._name,
            backend="simulator",
            path="virtual://simulator/camera_0",
            is_virtual=True,
            is_default=True,
            status_text="Mô phỏng sẵn sàng",
            capabilities=caps
        )
        return [dev]

    def connect(self, device_id: Any = None) -> bool:
        self._connected = True
        self._status = ConnectionState.CONNECTED
        self._error = None
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._live_view_active = False
        self._cached_frame_data = None
        self._status = ConnectionState.DISCONNECTED

    def get_status(self) -> ConnectionState:
        return self._status

    def get_error(self) -> Optional[CameraError]:
        return self._error

    def start_live_view(self) -> bool:
        self._live_view_active = True
        self._status = ConnectionState.LIVE_VIEW_ACTIVE
        return True

    def _generate_simulator_frame(self, w: int = 960, h: int = 640) -> np.ndarray:
        """Tạo khung hình mô phỏng sắc nét chuẩn studio màu xanh navy + vàng champagne."""
        img = Image.new("RGB", (w, h), color=(11, 18, 32))
        draw = ImageDraw.Draw(img)

        # Vẽ lưới căn chỉnh
        grid_color = (25, 40, 70)
        for x in (w // 3, 2 * w // 3):
            draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
        for y in (h // 3, 2 * h // 3):
            draw.line([(0, y), (w, y)], fill=grid_color, width=1)

        # Tâm ngắm
        cx, cy = w // 2, h // 2
        draw.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], outline=(212, 175, 55), width=2)
        draw.line([cx - 20, cy, cx + 20, cy], fill=(212, 175, 55), width=2)
        draw.line([cx, cy - 20, cx, cy + 20], fill=(212, 175, 55), width=2)

        # Nhãn thông tin
        draw.text((30, 30), "1998 TEAM — PHOTOBOOTH (CHẾ ĐỘ MÔ PHỎNG)", fill=(212, 175, 55))
        now_str = time.strftime("%H:%M:%S") + f".{int(time.time() * 10) % 10}"
        draw.text((30, 60), f"Live View Frame: {self._frame_count} | Thời gian: {now_str}", fill=(148, 163, 184))
        draw.text((30, h - 50), f"Thông số: ISO {self._params['iso']} | {self._params['shutter_speed']} | {self._params['aperture']} | {self._params['white_balance']}", fill=(203, 213, 225))

        self._frame_count += 1
        return np.array(img, dtype=np.uint8)

    def read_frame(self) -> Optional[FrameData]:
        if not self._connected or not self._live_view_active:
            return None

        now = time.time()
        # Giới hạn Simulator ở mức 30 FPS, không chạy tối đa CPU
        if self._cached_frame_data is not None and (now - self._last_frame_time) < self._min_frame_interval:
            return self._cached_frame_data

        rgb = self._generate_simulator_frame(960, 640)
        h, w = rgb.shape[:2]
        self._last_frame_time = now
        self._status = ConnectionState.LIVE_VIEW_ACTIVE
        self._cached_frame_data = FrameData(
            rgb=rgb,
            width=w,
            height=h,
            fps=self._target_fps,
            sequence_id=self._frame_count,
            timestamp=now,
            is_valid=True
        )
        return self._cached_frame_data

    def stop_live_view(self) -> None:
        self._live_view_active = False
        self._cached_frame_data = None
        if self._status == ConnectionState.LIVE_VIEW_ACTIVE:
            self._status = ConnectionState.CONNECTED

    def capture_photo(self, on_capture_start: Optional[Callable[[], None]] = None) -> Optional[Image.Image]:
        if not self._connected:
            return None
        if on_capture_start:
            try:
                on_capture_start()
            except Exception:
                pass
        rgb = self._generate_simulator_frame(2400, 1600)
        return Image.fromarray(rgb)

    def autofocus(
        self,
        callback: Optional[Any] = None,
        target_point: Optional[Tuple[float, float]] = None,
        frame_size: Optional[Tuple[float, float]] = None,
        **kwargs
    ) -> Tuple[bool, str]:
        """Giả lập lấy nét tự động trên Simulator (Rõ ràng đây là mô phỏng)."""
        self._last_af_target_point = target_point
        self._last_af_frame_size = frame_size
        msg = "Mô phỏng lấy nét thành công (Chế độ Simulator)"
        if callback:
            callback(True, msg)
        return True, msg

    def get_capabilities(self) -> CameraCapabilities:
        return CameraCapabilities(
            can_capture=True,
            can_liveview=True,
            can_download=True,
            can_adjust_parameters=True,
            can_autofocus=True,
            supported_resolutions=[(2400, 1600), (1920, 1080), (1280, 720)],
            supported_fps=[30.0],
            format_name="Simulator RGB"
        )

    def get_parameters(self) -> Dict[str, Any]:
        return dict(self._params)

    def set_parameters(self, params: Dict[str, Any]) -> bool:
        self._params.update(params)
        return True
