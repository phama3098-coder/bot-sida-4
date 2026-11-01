"""
1998 TEAM — Photobooth Camera Connection Models & State Enums
Standardized camera state machine, error structures, device metadata, and frame encapsulation.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import time
import numpy as np
from PIL import Image


class ConnectionState(str, Enum):
    """Trạng thái kết nối chuẩn hóa của hệ thống Camera."""
    DISCONNECTED = "DISCONNECTED"
    DISCOVERING = "DISCOVERING"
    DEVICE_FOUND = "DEVICE_FOUND"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    LIVE_VIEW_STARTING = "LIVE_VIEW_STARTING"
    LIVE_VIEW_ACTIVE = "LIVE_VIEW_ACTIVE"
    CONNECTED_NO_FRAME = "CONNECTED_NO_FRAME"
    ERROR = "ERROR"
    UNSUPPORTED = "UNSUPPORTED"

    @property
    def display_name(self) -> str:
        names = {
            "DISCONNECTED": "Chưa kết nối",
            "DISCOVERING": "Đang quét thiết bị...",
            "DEVICE_FOUND": "Đã tìm thấy thiết bị",
            "CONNECTING": "Đang kết nối...",
            "CONNECTED": "Đã kết nối",
            "LIVE_VIEW_STARTING": "Đang khởi động Live View...",
            "LIVE_VIEW_ACTIVE": "Live View đang hoạt động",
            "CONNECTED_NO_FRAME": "Đã kết nối (Chưa có khung hình)",
            "ERROR": "Lỗi kết nối",
            "UNSUPPORTED": "Không hỗ trợ"
        }
        return names.get(self.value, self.value)


@dataclass
class CameraError:
    """Cấu trúc lỗi camera chi tiết với mã lỗi và hành động gợi ý."""
    code: str
    message: str
    tech_detail: str = ""
    suggestion: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "tech_detail": self.tech_detail,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp
        }


@dataclass
class CameraCapabilities:
    """Khả năng hỗ trợ phần cứng của camera backend."""
    can_capture: bool = True
    can_liveview: bool = True
    can_download: bool = True
    can_adjust_parameters: bool = False
    can_autofocus: bool = False
    supported_resolutions: List[Tuple[int, int]] = field(default_factory=list)
    supported_fps: List[float] = field(default_factory=list)
    format_name: str = "RGB"

    @property
    def max_fps(self) -> float:
        return max(self.supported_fps) if self.supported_fps else 30.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "can_capture": self.can_capture,
            "can_liveview": self.can_liveview,
            "can_download": self.can_download,
            "can_adjust_parameters": self.can_adjust_parameters,
            "can_autofocus": self.can_autofocus,
            "supported_resolutions": self.supported_resolutions,
            "supported_fps": self.supported_fps,
            "max_fps": self.max_fps,
            "format_name": self.format_name
        }


@dataclass
class CameraDeviceInfo:
    """Thông tin nhận diện của thiết bị camera."""
    id: Any
    name: str
    backend: str
    path: str = ""
    is_virtual: bool = False
    is_default: bool = False
    actual_width: int = 0
    actual_height: int = 0
    fps: float = 0.0
    status_text: str = "Sẵn sàng"
    capabilities: CameraCapabilities = field(default_factory=CameraCapabilities)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "backend": self.backend,
            "path": self.path,
            "is_virtual": self.is_virtual,
            "is_default": self.is_default,
            "actual_width": self.actual_width,
            "actual_height": self.actual_height,
            "fps": self.fps,
            "status_text": self.status_text,
            "capabilities": self.capabilities.to_dict()
        }


@dataclass
class FrameData:
    """Đóng gói dữ liệu khung hình xem trước (Live View) hiệu năng cao."""
    rgb: Optional[np.ndarray] = None
    jpeg: Optional[bytes] = None
    width: int = 0
    height: int = 0
    fps: float = 0.0
    sequence_id: int = 0
    timestamp: float = field(default_factory=time.time)
    is_valid: bool = False

    @property
    def has_rgb(self) -> bool:
        return self.rgb is not None and hasattr(self.rgb, "ndim") and self.rgb.ndim >= 2 and self.rgb.size > 0

    @property
    def has_jpeg(self) -> bool:
        return self.jpeg is not None and len(self.jpeg) > 0

    @property
    def aspect_ratio(self) -> float:
        return (float(self.width) / float(self.height)) if self.height > 0 else 1.0
