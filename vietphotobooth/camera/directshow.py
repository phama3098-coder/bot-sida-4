"""
VietPhotoBooth DirectShow Camera Adapter
Native Windows UVC Webcam & Capture Card support via OpenCV DirectShow.
"""

import io
import time
from typing import Dict, Any, List, Optional
from PIL import Image
import cv2
from vietphotobooth.camera.base import CameraAdapter, CameraInfo
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class DirectShowCameraAdapter(CameraAdapter):
    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._connected = False
        self._device_name = f"Webcam DirectShow #{device_index}"

    def detect_devices(self) -> List[Dict[str, Any]]:
        """Dò quét các thiết bị video DirectShow khả dụng."""
        devices = []
        for idx in range(4):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                devices.append({
                    "id": idx,
                    "name": f"Webcam / Thẻ thu hình USB #{idx} ({w}x{h})",
                    "brand": "UVC Windows Device",
                    "model": f"Video Device {idx}",
                    "is_simulator": False,
                    "status": "Sẵn sàng"
                })
        return devices

    def connect(self, device_id: Any = None) -> bool:
        if device_id is not None:
            try:
                self.device_index = int(device_id)
            except Exception:
                pass

        self.disconnect()
        try:
            self._cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                logger.error(f"Không thể mở camera DirectShow #{self.device_index}")
                self._connected = False
                return False

            # Yêu cầu độ phân giải tối ưu nếu camera hỗ trợ
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            
            # Đọc thử 1 frame
            ret, _ = self._cap.read()
            if not ret:
                logger.warning(f"Đã mở camera #{self.device_index} nhưng chưa đọc được khung hình.")
            
            self._connected = True
            logger.info(f"Đã kết nối thành công với camera DirectShow #{self.device_index}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi kết nối camera DirectShow: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self._connected = False
        logger.info(f"Đã ngắt kết nối camera DirectShow #{self.device_index}")

    def is_connected(self) -> bool:
        if not self._connected or self._cap is None:
            return False
        return self._cap.isOpened()

    def get_info(self) -> CameraInfo:
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if self.is_connected() else 0
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if self.is_connected() else 0
        return CameraInfo(
            name=f"Webcam USB UVC #{self.device_index} ({w}x{h})",
            brand="UVC Standard",
            model=f"DirectShow #{self.device_index}",
            backend_name="Windows DirectShow Backend",
            is_simulator=False,
            status="Sẵn sàng" if self.is_connected() else "Chưa kết nối",
            capabilities={
                "can_capture": True,
                "can_download": True,
                "can_liveview": True,
                "can_adjust_parameters": True
            },
            notes=f"Độ phân giải hiện tại: {w}x{h}. Hỗ trợ live view và chụp trực tiếp trên Windows."
        )

    def capture_image(self) -> Optional[Image.Image]:
        """Chụp 1 khung hình độ nét cao từ webcam."""
        if not self.is_connected():
            logger.error("Webcam chưa kết nối, không thể chụp.")
            return None
        try:
            # Xả đệm 2 frame để lấy khung hình mới nhất
            for _ in range(2):
                self._cap.read()
            ret, frame = self._cap.read()
            if not ret or frame is None:
                logger.error("Không đọc được frame từ webcam.")
                return None
            
            # Chuyển đổi BGR sang RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            logger.info(f"Đã chụp ảnh từ webcam thành công: kích thước {img.size}")
            return img
        except Exception as e:
            logger.error(f"Lỗi khi chụp ảnh từ webcam: {e}")
            return None

    def get_liveview_frame(self) -> Optional[bytes]:
        """Lấy 1 khung hình JPEG bytes phục vụ live stream."""
        if not self.is_connected():
            return None
        try:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return None
            
            # Nén JPEG chất lượng 80 cho live stream mượt mà
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            ret, buffer = cv2.imencode(".jpg", frame, encode_param)
            if not ret:
                return None
            return buffer.tobytes()
        except Exception:
            return None

    def get_liveview_rgb_frame(self) -> Optional[Any]:
        """Lấy 1 khung hình RGB numpy array trực tiếp (nhanh gấp 8 lần, không nén JPEG)."""
        if not self.is_connected() or self._cap is None:
            return None
        try:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return None
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception:
            return None

    def get_parameters(self) -> Dict[str, Any]:
        if not self.is_connected():
            return {}
        try:
            return {
                "brightness": self._cap.get(cv2.CAP_PROP_BRIGHTNESS),
                "contrast": self._cap.get(cv2.CAP_PROP_CONTRAST),
                "saturation": self._cap.get(cv2.CAP_PROP_SATURATION),
                "exposure": self._cap.get(cv2.CAP_PROP_EXPOSURE)
            }
        except Exception:
            return {}

    def set_parameters(self, params: Dict[str, Any]) -> bool:
        if not self.is_connected():
            return False
        try:
            if "brightness" in params:
                self._cap.set(cv2.CAP_PROP_BRIGHTNESS, float(params["brightness"]))
            if "contrast" in params:
                self._cap.set(cv2.CAP_PROP_CONTRAST, float(params["contrast"]))
            if "saturation" in params:
                self._cap.set(cv2.CAP_PROP_SATURATION, float(params["saturation"]))
            return True
        except Exception as e:
            logger.error(f"Lỗi khi đặt thông số webcam: {e}")
            return False

    def check_health(self) -> bool:
        return self.is_connected()
