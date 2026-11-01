"""
1998 TEAM — Photobooth Camera Backend Base Contract
Abstract base class defining the required contract for all camera backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

from vietphotobooth.camera.models import (
    ConnectionState, CameraError, CameraCapabilities, CameraDeviceInfo, FrameData
)


class CameraBackendBase(ABC):
    """Giao diện cơ sở bắt buộc cho mọi Camera Backend."""

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """Tên định danh của backend (directshow, digicam, simulator)."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Tên hiển thị thân thiện trên giao diện người dùng."""
        pass

    @abstractmethod
    def discover_devices(self) -> List[CameraDeviceInfo]:
        """Dò tìm và trả về danh sách các thiết bị thực tế thuộc backend này."""
        pass

    @abstractmethod
    def connect(self, device_id: Any = None) -> bool:
        """
        Kết nối tới thiết bị theo device_id (index hoặc friendly name).
        Trả về True nếu kết nối và kiểm tra tính hợp lệ thành công.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Ngắt kết nối an toàn và giải phóng tài nguyên phần cứng."""
        pass

    @abstractmethod
    def get_status(self) -> ConnectionState:
        """Lấy trạng thái kết nối chuẩn hóa hiện tại."""
        pass

    @abstractmethod
    def get_error(self) -> Optional[CameraError]:
        """Lấy thông tin lỗi chi tiết gần nhất nếu có."""
        pass

    @abstractmethod
    def start_live_view(self) -> bool:
        """Bắt đầu luồng xem trước trực tiếp (Live View)."""
        pass

    @abstractmethod
    def read_frame(self) -> Optional[FrameData]:
        """Đọc 1 khung hình Live View hợp lệ."""
        pass

    @abstractmethod
    def stop_live_view(self) -> None:
        """Dừng luồng Live View."""
        pass

    @abstractmethod
    def capture_photo(self) -> Optional[Image.Image]:
        """
        Chụp một ảnh tĩnh độ phân giải cao và trả về PIL Image.
        Nếu backend không hỗ trợ, trả về None và đặt lỗi UNSUPPORTED.
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> CameraCapabilities:
        """Lấy danh sách các khả năng phần cứng mà thiết bị hỗ trợ."""
        pass

    def get_parameters(self) -> Dict[str, Any]:
        """Đọc thông số hiện tại (ISO, tốc độ, khẩu độ, WB)."""
        return {}

    def set_parameters(self, params: Dict[str, Any]) -> bool:
        """Thiết lập thông số máy ảnh (nếu hỗ trợ)."""
        return False

    def autofocus(self, callback: Optional[Any] = None) -> Tuple[bool, str]:
        """Kích hoạt lấy nét tự động một lần (nếu backend hỗ trợ)."""
        return False, "Backend không hỗ trợ điều khiển lấy nét tự động."

    def cancel_autofocus(self) -> bool:
        """Hủy thao tác lấy nét tự động nếu đang diễn ra."""
        return False

    def check_health(self) -> bool:
        """Kiểm tra phản hồi sức khỏe của kết nối."""
        return self.get_status() in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE)
