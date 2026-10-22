"""
VietPhotoBooth DirectShow Camera Adapter
Native Windows UVC Webcam, Capture Card, and Virtual Camera (Nikon Webcam Utility, OBS) support.
Features robust device discovery with friendly names, pre-connection validation, resolution/FPS measurement,
and detailed diagnostic reporting.
"""

import io
import time
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
import cv2
import numpy as np

from vietphotobooth.camera.base import CameraAdapter, CameraInfo
from vietphotobooth.camera.enumerator import (
    enumerate_directshow_devices, find_device_by_name_or_keyword
)
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class DirectShowCameraAdapter(CameraAdapter):
    def __init__(self, device_index: int = 0, device_name: Optional[str] = None):
        self.device_index = device_index
        self.requested_name = device_name
        self._cap: Optional[cv2.VideoCapture] = None
        self._connected = False
        self._device_name = device_name or f"Webcam DirectShow #{device_index}"
        self.last_error: str = ""
        self.actual_resolution: Tuple[int, int] = (0, 0)
        self.actual_fps: float = 0.0
        self.mean_brightness: float = 0.0
        self.is_virtual: bool = False
        self.backend_type: str = "DSHOW"

    @property
    def device_name(self) -> str:
        return self._device_name

    def detect_devices(self) -> List[Dict[str, Any]]:
        """
        Dò quét toàn bộ thiết bị video DirectShow và trả về danh sách kèm tên thực tế
        (ví dụ: 'Nikon Webcam Utility', 'Logi C270 HD WebCam').
        """
        devices = []
        dshow_list = enumerate_directshow_devices()

        if not dshow_list:
            # Fallback dò quét chỉ số nếu COM không khả dụng
            for idx in range(4):
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    cap.release()
                    devices.append({
                        "id": idx,
                        "name": f"Webcam USB #{idx} ({w}x{h})",
                        "brand": "UVC Windows Device",
                        "model": f"Video Device {idx}",
                        "is_simulator": False,
                        "is_virtual": False,
                        "status": "Sẵn sàng"
                    })
            return devices

        for d in dshow_list:
            name = d["name"]
            is_nikon = "nikon" in name.lower()
            is_logi = "logi" in name.lower() or "c270" in name.lower()
            brand = "Nikon" if is_nikon else "Logitech" if is_logi else "Windows Video Device"

            devices.append({
                "id": d["index"],
                "name": name,
                "brand": brand,
                "model": name,
                "path": d.get("path", ""),
                "is_simulator": False,
                "is_virtual": d.get("is_virtual", False),
                "status": "Sẵn sàng"
            })
        return devices

    def connect(self, device_id: Any = None) -> bool:
        """
        Kết nối tới thiết bị theo Index (int/str) hoặc theo Tên thân thiện (FriendlyName).
        Xác minh mở nguồn và đọc ít nhất 1 frame dữ liệu hợp lệ trước khi báo thành công.
        """
        self.disconnect()
        self.last_error = ""

        # 1. Xác định thiết bị mục tiêu
        target_name = None
        target_index = self.device_index

        if device_id is not None:
            if isinstance(device_id, int):
                target_index = device_id
            elif isinstance(device_id, str):
                if device_id.isdigit():
                    target_index = int(device_id)
                else:
                    # Tìm theo tên thiết bị (ví dụ 'Nikon Webcam Utility')
                    target_name = device_id
                    found = find_device_by_name_or_keyword(device_id)
                    if found:
                        target_index = found["index"]
                        self._device_name = found["name"]
                        self.is_virtual = found.get("is_virtual", False)
                    else:
                        logger.warning(f"Không tìm thấy thiết bị mang tên '{device_id}', thử dùng index {self.device_index}")

        # Lấy tên thân thiện từ bảng DirectShow nếu chưa có
        if not target_name:
            all_devs = enumerate_directshow_devices()
            match = next((d for d in all_devs if d["index"] == target_index), None)
            if match:
                self._device_name = match["name"]
                self.is_virtual = match.get("is_virtual", False)
            else:
                self._device_name = f"Webcam DirectShow #{target_index}"

        self.device_index = target_index

        # 2. Thử mở nguồn qua cv2.CAP_DSHOW (ưu tiên DirectShow)
        logger.info(f"Đang kết nối tới nguồn video DirectShow #{self.device_index}: '{self._device_name}'...")
        try:
            self._cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
            self.backend_type = "DSHOW"

            # Nếu DSHOW không mở được, thử fallback qua MSMF (Media Foundation)
            if not self._cap.isOpened():
                logger.info(f"DirectShow #{self.device_index} không mở được, thử Media Foundation (MSMF)...")
                self._cap.release()
                self._cap = cv2.VideoCapture(self.device_index, cv2.CAP_MSMF)
                self.backend_type = "MSMF"

            if not self._cap.isOpened():
                self.last_error = (
                    f"Không thể mở nguồn video '{self._device_name}' (Index #{self.device_index}). "
                    "Thiết bị có thể đang bị ứng dụng khác (Discord, OBS, Zoom) chiếm dụng hoặc bị rút cáp."
                )
                logger.error(self.last_error)
                self._connected = False
                return False

            # Yêu cầu độ phân giải tối ưu nếu camera là phần cứng UVC chuẩn
            if not self.is_virtual:
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

            # 3. KIỂM TRA ĐỌC FRAME HỢP LỆ TRƯỚC KHI BÁO HOẠT ĐỘNG
            valid_frame = None
            for _ in range(4):
                ret, frame = self._cap.read()
                if ret and frame is not None and frame.size > 0:
                    valid_frame = frame
                    break
                time.sleep(0.05)

            if valid_frame is None:
                self.last_error = (
                    f"Đã mở nguồn '{self._device_name}' nhưng không nhận được khung hình dữ liệu nào. "
                    "Nếu dùng Nikon D780: Hãy gạt cần bật Live View trên máy ảnh, kiểm tra pin hoặc cáp USB."
                )
                logger.error(self.last_error)
                self.disconnect()
                return False

            # Ghi nhận độ phân giải thực và độ sáng trung bình
            h, w = valid_frame.shape[:2]
            self.actual_resolution = (int(w), int(h))
            self.actual_fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 30.0)
            self.mean_brightness = float(np.mean(valid_frame))
            self._connected = True

            if self.mean_brightness < 1.5:
                logger.warning(
                    f"Nguồn '{self._device_name}' đang trả về khung hình màu đen hoàn toàn. "
                    "Vui lòng tháo nắp ống kính hoặc kiểm tra màn hình máy ảnh Nikon D780."
                )

            logger.info(
                f"Đã kết nối thành công với camera '{self._device_name}' ({w}x{h}, {self.backend_type})"
            )
            return True

        except Exception as e:
            self.last_error = f"Lỗi ngoại lệ khi kết nối camera DirectShow '{self._device_name}': {e}"
            logger.error(self.last_error)
            self.disconnect()
            return False

    def disconnect(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self._connected = False
        logger.info(f"Đã ngắt kết nối camera '{self._device_name}'")

    def is_connected(self) -> bool:
        if not self._connected or self._cap is None:
            return False
        return self._cap.isOpened()

    def get_info(self) -> CameraInfo:
        w, h = self.actual_resolution
        if self.is_connected() and w == 0 and self._cap:
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        is_nikon = "nikon" in self._device_name.lower()
        brand = "Nikon" if is_nikon else "Logitech" if "logi" in self._device_name.lower() else "Windows UVC"
        status_str = f"Sẵn sàng ({w}x{h})" if self.is_connected() else (self.last_error or "Chưa kết nối")

        notes = (
            f"Nguồn video: {self._device_name}. Độ phân giải thực tế: {w}x{h}. "
            f"Giao thức: Windows DirectShow ({self.backend_type})."
        )
        if self.mean_brightness < 1.5 and self.is_connected():
            notes += " [Cảnh báo: Khung hình tối/đen, vui lòng kiểm tra nắp ống kính hoặc bật Live View trên Nikon D780]."

        return CameraInfo(
            name=self._device_name,
            brand=brand,
            model=self._device_name,
            backend_name="Windows DirectShow Backend",
            is_simulator=False,
            status=status_str,
            capabilities={
                "can_capture": True,
                "can_download": True,
                "can_liveview": True,
                "can_adjust_parameters": not self.is_virtual
            },
            notes=notes
        )

    def capture_image(self) -> Optional[Image.Image]:
        """Chụp 1 khung hình độ nét cao từ webcam."""
        if not self.is_connected() or self._cap is None:
            logger.error(f"Webcam '{self._device_name}' chưa kết nối, không thể chụp.")
            return None
        try:
            # Xả đệm 2 frame để lấy khung hình mới nhất
            for _ in range(2):
                self._cap.read()
            ret, frame = self._cap.read()
            if not ret or frame is None or frame.size == 0:
                self.last_error = "Không đọc được khung hình từ webcam khi bấm chụp."
                logger.error(self.last_error)
                return None

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            logger.info(f"Đã chụp ảnh từ webcam '{self._device_name}' thành công: kích thước {img.size}")
            return img
        except Exception as e:
            self.last_error = f"Lỗi khi chụp ảnh từ webcam: {e}"
            logger.error(self.last_error)
            return None

    def get_liveview_frame(self) -> Optional[bytes]:
        """Lấy 1 khung hình JPEG bytes phục vụ live stream."""
        if not self.is_connected() or self._cap is None:
            return None
        try:
            ret, frame = self._cap.read()
            if not ret or frame is None or frame.size == 0:
                return None
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
            if not ret or frame is None or frame.size == 0:
                return None
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception:
            return None

    def get_parameters(self) -> Dict[str, Any]:
        if not self.is_connected() or self._cap is None:
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
        if not self.is_connected() or self._cap is None:
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
