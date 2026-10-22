"""
1998 TEAM — Photobooth digiCamControl Backend
Controls DSLR / Mirrorless cameras (Nikon, Canon, Sony) via PTP/USB using digiCamControl CLI & REST API.
Maintains tethered shooting capabilities and clearly separates tethered capture from webcam live view.
"""

import os
import subprocess
import time
import logging
from typing import Dict, Any, List, Optional
import urllib.request
import numpy as np
from PIL import Image

from vietphotobooth.camera.backends.base import CameraBackendBase
from vietphotobooth.camera.models import (
    ConnectionState, CameraError, CameraCapabilities, CameraDeviceInfo, FrameData
)
from vietphotobooth.core.config import get_user_data_dir

logger = logging.getLogger("VietPhotoBooth.camera.backend.digicam")


class DigiCamControlBackend(CameraBackendBase):
    """Backend điều khiển máy ảnh DSLR chuyên nghiệp qua digiCamControl (PTP/USB)."""

    def __init__(self, cli_path: Optional[str] = None, web_port: int = 5513):
        self._cli_path = cli_path or r"C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe"
        self._web_port = web_port
        self._base_url = f"http://127.0.0.1:{web_port}"
        self._status = ConnectionState.DISCONNECTED
        self._error: Optional[CameraError] = None
        self._connected = False
        self._camera_name = "Nikon DSLR (digiCamControl)"

    @property
    def backend_type(self) -> str:
        return "digicam"

    @property
    def display_name(self) -> str:
        return "digiCamControl (DSLR / Mirrorless)"

    @property
    def device_name(self) -> str:
        return self._camera_name

    def discover_devices(self) -> List[CameraDeviceInfo]:
        """Kiểm tra sự hiện diện của phần mềm digiCamControl và máy ảnh kết nối qua REST/CLI."""
        self._status = ConnectionState.DISCOVERING
        results: List[CameraDeviceInfo] = []

        installed = os.path.exists(self._cli_path)
        camera_name = "DSLR / Mirrorless (digiCamControl)"

        # Thử đọc tên máy ảnh qua REST API nếu đang chạy
        try:
            req = urllib.request.urlopen(f"{self._base_url}/?sl=get&param=camera.name", timeout=1.0)
            if req.status == 200:
                name = req.read().decode("utf-8").strip()
                if name:
                    camera_name = name
        except Exception:
            pass

        caps = CameraCapabilities(
            can_capture=True,
            can_liveview=True,
            can_download=True,
            can_adjust_parameters=True,
            supported_resolutions=[(6000, 4000), (4000, 3000), (1920, 1080)],
            supported_fps=[30.0],
            format_name="RAW/JPEG 24MP"
        )

        dev = CameraDeviceInfo(
            id="digicam_ptp",
            name=camera_name if installed else "digiCamControl (Chưa cài đặt)",
            backend="digicam",
            path=self._cli_path,
            is_virtual=False,
            is_default=False,
            status_text="Sẵn sàng chụp PTP/USB" if installed else "Chưa cài đặt digiCamControl",
            capabilities=caps
        )
        results.append(dev)

        self._status = ConnectionState.DEVICE_FOUND if installed else ConnectionState.DISCONNECTED
        return results

    def connect(self, device_id: Any = None) -> bool:
        """Kiểm tra CLI hoặc REST API để sẵn sàng kết nối."""
        self._status = ConnectionState.CONNECTING
        self._error = None

        if not os.path.exists(self._cli_path):
            self._error = CameraError(
                code="DIGICAM_NOT_INSTALLED",
                message=f"Không tìm thấy trình điều khiển digiCamControl tại: {self._cli_path}",
                suggestion="Vui lòng cài đặt digiCamControl chính hãng hoặc sử dụng backend DirectShow Webcam."
            )
            self._status = ConnectionState.ERROR
            self._connected = False
            return False

        # Thử truy vấn qua REST API
        try:
            req = urllib.request.urlopen(f"{self._base_url}/?sl=get&param=camera.name", timeout=1.0)
            if req.status == 200:
                self._camera_name = req.read().decode("utf-8").strip() or self._camera_name
        except Exception:
            pass

        self._connected = True
        self._status = ConnectionState.CONNECTED
        logger.info(f"Đã kết nối với digiCamControl PTP/USB: {self._camera_name}")
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._status = ConnectionState.DISCONNECTED

    def get_status(self) -> ConnectionState:
        return self._status

    def get_error(self) -> Optional[CameraError]:
        return self._error

    def start_live_view(self) -> bool:
        return self._connected

    def read_frame(self) -> Optional[FrameData]:
        """
        Lấy khung hình Live View từ digiCamControl qua cổng HTTP 5513.
        Nếu dịch vụ chưa bật Live View, trả về None và đặt trạng thái CONNECTED_NO_FRAME.
        """
        if not self._connected:
            return None

        try:
            url = f"{self._base_url}/liveview.jpg"
            req = urllib.request.Request(url, headers={"User-Agent": "1998TEAM-Photobooth"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if len(data) > 1000 and data.startswith(b"\xff\xd8"):
                        import cv2
                        nparr = np.frombuffer(data, np.uint8)
                        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if img_bgr is not None:
                            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                            h, w = rgb.shape[:2]
                            self._status = ConnectionState.LIVE_VIEW_ACTIVE
                            return FrameData(
                                rgb=rgb,
                                jpeg=data,
                                width=w,
                                height=h,
                                fps=30.0,
                                timestamp=time.time(),
                                is_valid=True
                            )
        except Exception:
            pass

        # Không đọc được frame từ HTTP port 5513
        self._status = ConnectionState.CONNECTED_NO_FRAME
        self._error = CameraError(
            code="NO_LIVEVIEW_STREAM",
            message="digiCamControl chưa phát luồng Live View qua cổng HTTP 5513.",
            suggestion="Để xem trực tiếp từ Nikon D780: Hãy chọn nguồn DirectShow 'Nikon Webcam Utility'."
        )
        return None

    def stop_live_view(self) -> None:
        if self._status == ConnectionState.LIVE_VIEW_ACTIVE:
            self._status = ConnectionState.CONNECTED

    def capture_photo(self) -> Optional[Image.Image]:
        """Kích hoạt chụp ảnh chất lượng cao 24MP qua digiCamControl."""
        if not self._connected or not os.path.exists(self._cli_path):
            return None

        out_dir = os.path.join(get_user_data_dir(), "TempCaptures")
        os.makedirs(out_dir, exist_ok=True)
        fname = f"capture_{int(time.time() * 1000)}.jpg"
        target_path = os.path.join(out_dir, fname)

        cmd = [self._cli_path, "/filename", target_path, "/capture"]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12)
            if res.returncode == 0 and os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
                with Image.open(target_path) as img:
                    loaded = img.convert("RGB")
                    return loaded
        except Exception as e:
            logger.error(f"Lỗi chụp ảnh qua digiCamControl: {e}")
        return None

    def get_capabilities(self) -> CameraCapabilities:
        return CameraCapabilities(
            can_capture=True,
            can_liveview=True,
            can_download=True,
            can_adjust_parameters=True,
            supported_resolutions=[(6000, 4000), (4000, 3000), (1920, 1080)],
            supported_fps=[30.0],
            format_name="DSLR RAW/JPEG"
        )

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "iso": "100",
            "shutter_speed": "1/125",
            "aperture": "f/4.0",
            "white_balance": "Daylight",
            "device_name": self._camera_name,
            "resolution": "6000x4000",
            "fps": 30.0
        }
