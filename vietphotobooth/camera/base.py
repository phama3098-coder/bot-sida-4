"""
VietPhotoBooth Camera Adapter Base Interface
Defines the standard abstraction contract for all camera backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from PIL import Image

class CameraInfo:
    def __init__(
        self,
        name: str,
        brand: str,
        model: str,
        backend_name: str,
        is_simulator: bool = False,
        status: str = "Đang ngắt kết nối",
        capabilities: Optional[Dict[str, bool]] = None,
        notes: str = ""
    ):
        self.name = name
        self.brand = brand
        self.model = model
        self.backend_name = backend_name
        self.is_simulator = is_simulator
        self.status = status
        self.capabilities = capabilities or {
            "can_capture": True,
            "can_download": True,
            "can_liveview": True,
            "can_adjust_parameters": False
        }
        self.notes = notes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "brand": self.brand,
            "model": self.model,
            "backend_name": self.backend_name,
            "is_simulator": self.is_simulator,
            "status": self.status,
            "capabilities": self.capabilities,
            "notes": self.notes
        }

class CameraAdapter(ABC):
    """Lớp trừu tượng cho tất cả các backend camera trên Windows."""

    @abstractmethod
    def detect_devices(self) -> List[Dict[str, Any]]:
        """Dò tìm và liệt kê danh sách thiết bị khả dụng."""
        pass

    @abstractmethod
    def connect(self, device_id: Any = None) -> bool:
        """Kết nối tới thiết bị máy ảnh."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Ngắt kết nối an toàn với máy ảnh."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Kiểm tra trạng thái kết nối."""
        pass

    @abstractmethod
    def get_info(self) -> CameraInfo:
        """Lấy thông tin chi tiết của máy ảnh hiện tại."""
        pass

    @abstractmethod
    def capture_image(self) -> Optional[Image.Image]:
        """Chụp một bức ảnh chất lượng cao và trả về đối tượng PIL Image."""
        pass

    @abstractmethod
    def get_liveview_frame(self) -> Optional[bytes]:
        """Lấy khung hình xem trước (Live View) định dạng JPEG bytes."""
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Đọc thông số hiện tại (ISO, Shutter speed, Aperture, White balance)."""
        pass

    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> bool:
        """Thay đổi thông số máy ảnh nếu thiết bị hỗ trợ."""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Kiểm tra xem máy ảnh có phản hồi bình thường không."""
        pass
