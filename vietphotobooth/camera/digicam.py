"""
VietPhotoBooth digiCamControl Adapter
Bridge for DSLR & Mirrorless cameras (Nikon, Canon, Sony) via digiCamControl on Windows.
Supports both REST Web API (http://127.0.0.1:5513/) and CameraControlCmd CLI.
"""

import os
import time
import requests
import subprocess
from typing import Dict, Any, List, Optional
from PIL import Image
from vietphotobooth.camera.base import CameraAdapter, CameraInfo
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class DigiCamControlAdapter(CameraAdapter):
    def __init__(self, api_url: str = "http://127.0.0.1:5513", cli_path: str = None):
        self.api_url = api_url.rstrip("/")
        self.cli_path = cli_path or r"C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe"
        self._connected = False
        self._camera_name = "Chưa kết nối"
        self._brand = "Không xác định"
        self._model = "Không xác định"
        self.last_error: str = ""

    def detect_devices(self) -> List[Dict[str, Any]]:
        """Dò tìm máy ảnh kết nối qua digiCamControl API hoặc CLI."""
        devices = []
        # Thử qua REST API
        try:
            resp = requests.get(f"{self.api_url}/?sl=get&param=camera.name", timeout=1.5)
            if resp.status_code == 200 and resp.text.strip():
                name = resp.text.strip()
                brand = "Canon" if "canon" in name.lower() else "Nikon" if "nikon" in name.lower() else "Sony" if "sony" in name.lower() else "DSLR"
                devices.append({
                    "id": "digicam_web",
                    "name": f"{brand} DSLR: {name}",
                    "brand": brand,
                    "model": name,
                    "is_simulator": False,
                    "status": "Sẵn sàng (digiCamControl REST)"
                })
                return devices
        except Exception:
            pass

        # Thử qua CLI nếu file exe tồn tại
        if os.path.exists(self.cli_path):
            try:
                out = subprocess.run([self.cli_path, "/list"], capture_output=True, text=True, timeout=3)
                if out.returncode == 0 and out.stdout:
                    devices.append({
                        "id": "digicam_cli",
                        "name": f"digiCamControl CLI Driver: {out.stdout.strip()[:40]}",
                        "brand": "DSLR Driver",
                        "model": "CameraControlCmd",
                        "is_simulator": False,
                        "status": "Sẵn sàng (CLI)"
                    })
            except Exception:
                pass

        return devices

    def connect(self, device_id: Any = None) -> bool:
        """Kiểm tra kết nối tới digiCamControl."""
        try:
            resp = requests.get(f"{self.api_url}/?sl=get&param=camera.name", timeout=2.0)
            if resp.status_code == 200:
                self._camera_name = resp.text.strip() or "DSLR Camera"
                name_low = self._camera_name.lower()
                if "nikon" in name_low:
                    self._brand = "Nikon"
                elif "canon" in name_low:
                    self._brand = "Canon"
                elif "sony" in name_low:
                    self._brand = "Sony"
                else:
                    self._brand = "DSLR/Mirrorless"
                self._model = self._camera_name
                self._connected = True
                logger.info(f"Đã kết nối với digiCamControl: {self._camera_name}")
                return True
        except Exception as e:
            logger.warning(f"digiCamControl REST không phản hồi tại {self.api_url}: {e}")

        # Thử kiểm tra sự tồn tại của CLI
        if os.path.exists(self.cli_path):
            self._connected = True
            self._camera_name = "digiCamControl CLI Mode"
            self._brand = "DSLR"
            self._model = "CameraControlCmd"
            logger.info("Sử dụng digiCamControl ở chế độ CLI.")
            return True

        self._connected = False
        return False

    def disconnect(self) -> None:
        self._connected = False
        logger.info("Đã ngắt kết nối với digiCamControl.")

    def is_connected(self) -> bool:
        return self._connected

    def get_info(self) -> CameraInfo:
        return CameraInfo(
            name=f"{self._brand} DSLR ({self._camera_name})",
            brand=self._brand,
            model=self._model,
            backend_name="digiCamControl Windows Adapter (Tethered Control)",
            is_simulator=False,
            status="Sẵn sàng (Tethered Control)" if self._connected else "Chưa kết nối (Cần mở digiCamControl)",
            capabilities={
                "can_capture": True,
                "can_download": True,
                "can_liveview": True,
                "can_adjust_parameters": True
            },
            notes=(
                "Điều khiển máy ảnh chuyên nghiệp DSLR/Mirrorless Nikon, Canon, Sony thông qua digiCamControl. "
                "Chuyên dụng cho kích hoạt chụp ảnh độ nét cao. "
                "Lưu ý: Để xem Live View mượt mà trên Windows, khuyến nghị dùng nguồn DirectShow 'Nikon Webcam Utility'."
            )
        )

    def capture_image(self) -> Optional[Image.Image]:
        """Kích hoạt chụp và tải ảnh từ máy ảnh DSLR về máy tính."""
        if not self._connected:
            logger.error("digiCamControl chưa được kết nối!")
            return None

        # 1. Thử lệnh qua REST API
        try:
            resp = requests.get(f"{self.api_url}/?cmd=Capture", timeout=5.0)
            if resp.status_code == 200:
                time.sleep(0.5)
                # Lấy file vừa chụp
                file_resp = requests.get(f"{self.api_url}/?sl=get&param=lastcaptured", timeout=3.0)
                if file_resp.status_code == 200 and file_resp.text.strip():
                    img_path = file_resp.text.strip()
                    if os.path.exists(img_path):
                        return Image.open(img_path).copy()
        except Exception as e:
            logger.warning(f"Lệnh chụp qua REST thất bại: {e}. Thử lệnh qua CLI...")

        # 2. Thử qua CLI
        if os.path.exists(self.cli_path):
            temp_file = os.path.join(os.environ.get("TEMP", "C:\\Temp"), f"vpb_dslr_{int(time.time())}.jpg")
            try:
                cmd = [self.cli_path, "/capture", "/filename", temp_file]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
                if res.returncode == 0 and os.path.exists(temp_file):
                    img = Image.open(temp_file).copy()
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass
                    return img
            except Exception as e:
                logger.error(f"Lỗi khi chụp qua digiCamControl CLI: {e}")

        return None

    def get_liveview_frame(self) -> Optional[bytes]:
        """Lấy khung hình live view từ digiCamControl."""
        if not self._connected:
            self.last_error = "digiCamControl chưa kết nối."
            return None
        try:
            resp = requests.get(f"{self.api_url}/liveview.jpg", timeout=1.0)
            if resp.status_code == 200 and len(resp.content) > 1000:
                self.last_error = ""
                return resp.content
            else:
                self.last_error = (
                    "digiCamControl Web Server chưa bật luồng Live View (HTTP 5513). "
                    "Hãy mở digiCamControl và bật Live View, hoặc chuyển sang nguồn video webcam 'Nikon Webcam Utility'."
                )
        except Exception as e:
            self.last_error = (
                f"Không thể kết nối Live View tới digiCamControl ({e}). "
                "Khuyến nghị chuyển sang nguồn DirectShow 'Nikon Webcam Utility' trong phần cài đặt máy ảnh."
            )
        return None

    def get_parameters(self) -> Dict[str, Any]:
        params = {}
        if not self._connected:
            return params
        for p in ["iso", "shutter", "aperture", "whitebalance"]:
            try:
                resp = requests.get(f"{self.api_url}/?sl=get&param=camera.{p}", timeout=1.0)
                if resp.status_code == 200:
                    params[p] = resp.text.strip()
            except Exception:
                pass
        return params

    def set_parameters(self, params: Dict[str, Any]) -> bool:
        if not self._connected:
            return False
        success = True
        for k, v in params.items():
            try:
                resp = requests.get(f"{self.api_url}/set?{k}={v}", timeout=1.5)
                if resp.status_code != 200:
                    success = False
            except Exception:
                success = False
        return success

    def check_health(self) -> bool:
        return self._connected
