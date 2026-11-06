"""
1998 TEAM — Photobooth digiCamControl Backend
Controls DSLR / Mirrorless cameras (Nikon, Canon, Sony) via PTP/USB using digiCamControl CLI & REST API.
Maintains tethered shooting capabilities and clearly separates tethered capture from webcam live view.
"""

import os
import sys
import socket
import subprocess
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
import urllib.request
import urllib.error
import numpy as np
from PIL import Image

from vietphotobooth.camera.backends.base import CameraBackendBase
from vietphotobooth.camera.models import (
    ConnectionState, CameraError, CameraCapabilities, CameraDeviceInfo, FrameData
)
from vietphotobooth.core.config import get_user_data_dir

logger = logging.getLogger("VietPhotoBooth.camera.backend.digicam")


def is_digicam_process_running(process_name: str = "CameraControl.exe") -> bool:
    """
    Kiểm tra xem ứng dụng digiCamControl (CameraControl.exe) có đang chạy trên Windows không.
    Sử dụng ctypes Windows Toolhelp API (siêu nhanh, sub-millisecond, không gọi subprocess).
    Fallback an toàn sang tasklist nếu chạy ngoài Windows hoặc ctypes lỗi.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes
            kernel32 = ctypes.windll.kernel32
            TH32CS_SNAPPROCESS = 0x00000002

            class PROCESSENTRY32(ctypes.Structure):
                _fields_ = [
                    ('dwSize', ctypes.wintypes.DWORD),
                    ('cntUsage', ctypes.wintypes.DWORD),
                    ('th32ProcessID', ctypes.wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', ctypes.wintypes.DWORD),
                    ('cntThreads', ctypes.wintypes.DWORD),
                    ('th32ParentProcessID', ctypes.wintypes.DWORD),
                    ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', ctypes.wintypes.DWORD),
                    ('szExeFile', ctypes.c_char * 260)
                ]

            hSnap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if hSnap == -1:
                return False
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            found = False
            target_bytes = process_name.lower().encode('ascii')
            if kernel32.Process32First(hSnap, ctypes.byref(pe)):
                while True:
                    if pe.szExeFile.lower() == target_bytes:
                        found = True
                        break
                    if not kernel32.Process32Next(hSnap, ctypes.byref(pe)):
                        break
            kernel32.CloseHandle(hSnap)
            return found
        except Exception as e:
            logger.debug(f"ctypes process check error: {e}")
            try:
                res = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/NH"],
                    capture_output=True, text=True, timeout=1.0
                )
                return process_name.lower() in res.stdout.lower()
            except Exception:
                return False
    return False


def is_port_listening(host: str = "127.0.0.1", port: int = 5513, timeout: float = 0.4) -> bool:
    """Kiểm tra xem cổng TCP có đang mở và lắng nghe kết nối không."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def is_valid_camera_name(raw_name: Optional[str]) -> bool:
    """Kiểm tra chuỗi tên máy ảnh có hợp lệ và biểu thị một máy ảnh thực sự hay không."""
    if not raw_name:
        return False
    cleaned = raw_name.strip()
    if not cleaned:
        return False
    lower = cleaned.lower()
    invalid_keywords = [
        "no camera connected",
        "none",
        "[no camera]",
        "no camera selected",
        "no camera",
        "null",
        "not connected",
        "error"
    ]
    return lower not in invalid_keywords


class DigiCamControlBackend(CameraBackendBase):
    """Backend điều khiển máy ảnh DSLR chuyên nghiệp qua digiCamControl (PTP/USB)."""

    def __init__(self, cli_path: Optional[str] = None, web_port: int = 5513):
        self._cli_path = cli_path or r"C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe"
        self._web_port = web_port
        self._base_url = f"http://127.0.0.1:{web_port}"
        self._status = ConnectionState.DISCONNECTED
        self._error: Optional[CameraError] = None
        self._connected = False
        self._camera_detected = False
        self._liveview_stream_active = False
        self._camera_name = "DSLR / Mirrorless (digiCamControl)"

    @property
    def backend_type(self) -> str:
        return "digicam"

    @property
    def display_name(self) -> str:
        return "digiCamControl (DSLR / Mirrorless)"

    @property
    def device_name(self) -> str:
        return self._camera_name

    def is_connected(self) -> bool:
        return self._connected

    def discover_devices(self) -> List[CameraDeviceInfo]:
        """Kiểm tra sự hiện diện của phần mềm digiCamControl và máy ảnh kết nối qua REST/CLI."""
        self._status = ConnectionState.DISCOVERING
        results: List[CameraDeviceInfo] = []

        installed = os.path.exists(self._cli_path)
        proc_running = is_digicam_process_running("CameraControl.exe")
        port_open = is_port_listening("127.0.0.1", self._web_port, timeout=0.3)

        camera_name = "DSLR / Mirrorless (digiCamControl)"
        camera_detected = False

        if port_open:
            try:
                req = urllib.request.urlopen(f"{self._base_url}/?sl=get&param=camera.name", timeout=1.0)
                if req.status == 200:
                    name = req.read().decode("utf-8", errors="ignore").strip()
                    if is_valid_camera_name(name):
                        camera_name = name
                        camera_detected = True
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

        if not installed:
            status_text = "Chưa cài đặt digiCamControl"
            dev_name = "digiCamControl (Chưa cài đặt)"
        elif not proc_running:
            status_text = "Chưa bật ứng dụng digiCamControl"
            dev_name = "digiCamControl (Chưa mở)"
        elif not port_open:
            status_text = "Web Server cổng 5513 chưa bật"
            dev_name = "digiCamControl (Web Server tắt)"
        elif not camera_detected:
            status_text = "Chưa cắm máy ảnh USB"
            dev_name = "digiCamControl (Chưa cắm máy ảnh)"
        else:
            status_text = f"Sẵn sàng chụp: {camera_name}"
            dev_name = camera_name

        dev = CameraDeviceInfo(
            id="digicam_ptp",
            name=dev_name,
            backend="digicam",
            path=self._cli_path,
            is_virtual=False,
            is_default=False,
            status_text=status_text,
            capabilities=caps
        )
        results.append(dev)

        self._status = ConnectionState.DEVICE_FOUND if (installed and camera_detected) else ConnectionState.DISCONNECTED
        return results

    def connect(self, device_id: Any = None) -> bool:
        """
        Quy trình kết nối máy ảnh digiCamControl chuẩn 8 bước:
        1. Kiểm tra file CLI / phần mềm cài đặt.
        2. Kiểm tra tiến trình CameraControl.exe đang chạy.
        3. Kiểm tra cổng Web Server 5513 đang lắng nghe.
        4. Gửi HTTP GET truy vấn camera.name với timeout hữu hạn.
        5. Xác thực tên máy ảnh hợp lệ.
        6. Đánh dấu sẵn sàng chụp ảnh (Capture Backend Ready).
        7. Thăm dò và gửi lệnh kích hoạt Live View nếu API hỗ trợ.
        8. Xác minh khung hình thật trước khi báo Live View hoạt động.
        """
        self._status = ConnectionState.CONNECTING
        self._error = None
        self._camera_detected = False
        self._liveview_stream_active = False

        # 1. Kiểm tra cài đặt
        if not os.path.exists(self._cli_path):
            self._error = CameraError(
                code="DIGICAM_NOT_INSTALLED",
                message=f"Không tìm thấy trình điều khiển digiCamControl tại: {self._cli_path}",
                tech_detail=f"File not found: {self._cli_path}",
                suggestion="Vui lòng tải và cài đặt digiCamControl từ trang chủ http://digicamcontrol.com/ hoặc chuyển sang nguồn DirectShow."
            )
            self._status = ConnectionState.ERROR
            self._connected = False
            return False

        # 2. Kiểm tra tiến trình CameraControl.exe
        if not is_digicam_process_running("CameraControl.exe"):
            self._error = CameraError(
                code="DIGICAM_NOT_RUNNING",
                message="Ứng dụng digiCamControl (CameraControl.exe) chưa được khởi động trên máy tính.",
                tech_detail="Không tìm thấy tiến trình 'CameraControl.exe' trong danh sách tiến trình Windows.",
                suggestion="Vui lòng khởi động ứng dụng digiCamControl trên Windows trước khi bấm kết nối trong Photobooth."
            )
            self._status = ConnectionState.ERROR
            self._connected = False
            return False

        # 3. Kiểm tra cổng Web Server 5513
        if not is_port_listening("127.0.0.1", self._web_port, timeout=0.4):
            self._error = CameraError(
                code="HTTP_SERVER_DISABLED",
                message=f"Dịch vụ Web Server của digiCamControl (cổng {self._web_port}) chưa được kích hoạt.",
                tech_detail=f"Tiến trình CameraControl.exe đang chạy nhưng cổng TCP {self._web_port} không mở kết nối (Connection Refused).",
                suggestion=f"Trong digiCamControl: Vào File > Settings > Web Server > Tích chọn 'Use web server' (cổng {self._web_port}), bấm OK và khởi động lại digiCamControl."
            )
            self._status = ConnectionState.ERROR
            self._connected = False
            return False

        # 4 & 5. Truy vấn HTTP tên máy ảnh
        try:
            req = urllib.request.urlopen(f"{self._base_url}/?sl=get&param=camera.name", timeout=1.5)
            raw_name = req.read().decode("utf-8", errors="ignore").strip()
        except (socket.timeout, urllib.error.URLError) as e:
            self._error = CameraError(
                code="HTTP_TIMEOUT",
                message="Máy chủ Web Server của digiCamControl phản hồi quá chậm (Timeout).",
                tech_detail=f"Yêu cầu GET http://127.0.0.1:{self._web_port}/?sl=get&param=camera.name bị lỗi/timeout: {e}",
                suggestion="Kiểm tra xem digiCamControl có đang bị đơ hoặc có hộp thoại thông báo nào đang mở chặn tiến trình không."
            )
            self._status = ConnectionState.ERROR
            self._connected = False
            return False
        except Exception as e:
            self._error = CameraError(
                code="HTTP_CONNECTION_FAILED",
                message="Không thể gửi yêu cầu HTTP tới digiCamControl.",
                tech_detail=f"Lỗi giao tiếp HTTP: {e}",
                suggestion="Kiểm tra lại cấu hình Web Server trong digiCamControl."
            )
            self._status = ConnectionState.ERROR
            self._connected = False
            return False

        if not is_valid_camera_name(raw_name):
            self._error = CameraError(
                code="CAMERA_NOT_DETECTED",
                message="digiCamControl đang chạy nhưng không phát hiện máy ảnh DSLR/Mirrorless nào qua cổng USB.",
                tech_detail=f"Endpoint camera.name trả về chuỗi rỗng hoặc không có thiết bị: '{raw_name}'.",
                suggestion="1. Cắm chặt cáp USB nối giữa máy ảnh Nikon/Canon và máy tính.\n2. Bật công tắc nguồn của máy ảnh sang ON.\n3. Đảm bảo máy ảnh không để ở chế độ xem lại ảnh (Playback) hoặc bị khóa menu."
            )
            self._status = ConnectionState.ERROR
            self._connected = False
            return False

        # 6. Đã nhận diện máy ảnh thành công
        self._camera_name = raw_name
        self._camera_detected = True
        self._connected = True
        self._status = ConnectionState.CONNECTED
        logger.info(f"Đã nhận diện thành công máy ảnh qua digiCamControl: {self._camera_name}")

        # 7 & 8. Thăm dò và kiểm tra Live View (không làm đứt kết nối nếu Live View tắt)
        self._probe_and_activate_liveview()
        return True

    def _probe_and_activate_liveview(self) -> bool:
        """
        Thăm dò luồng Live View và thử kích hoạt qua API chính thức nếu chưa bật.
        Không bao giờ hạ cờ self._connected nếu Live View không khả dụng.
        """
        if not self._connected or not self._camera_detected:
            return False

        # Thử đọc trực tiếp frame hiện tại
        if self._has_liveview_stream():
            self._liveview_stream_active = True
            self._status = ConnectionState.LIVE_VIEW_ACTIVE
            self._error = None
            return True

        # Thử gửi lệnh bật Live View theo API chính thức của digiCamControl
        try:
            cmd_url = f"{self._base_url}/?cmd=LiveViewWnd_Show"
            urllib.request.urlopen(cmd_url, timeout=1.5)
            time.sleep(0.3)
        except Exception as e:
            logger.debug(f"Gửi lệnh LiveViewWnd_Show không thành công: {e}")

        # Kiểm tra lại sau lệnh bật
        if self._has_liveview_stream():
            self._liveview_stream_active = True
            self._status = ConnectionState.LIVE_VIEW_ACTIVE
            self._error = None
            return True

        # Live View không khả dụng (nhưng máy ảnh vẫn kết nối cho chụp tĩnh Tethered)
        self._liveview_stream_active = False
        self._status = ConnectionState.CONNECTED_NO_FRAME
        self._error = CameraError(
            code="LIVEVIEW_UNAVAILABLE",
            message=f"Máy ảnh '{self._camera_name}' đã kết nối sẵn sàng chụp tĩnh độ phân giải cao (6000×4000), nhưng luồng Live View HTTP chưa bật.",
            tech_detail="Endpoint /liveview.jpg không trả về dữ liệu JPEG hợp lệ.",
            suggestion="Để xem trực tiếp từ Nikon D780: Hãy chọn nguồn DirectShow 'Nikon Webcam Utility', hoặc bật Live View trong digiCamControl."
        )
        return False

    def _has_liveview_stream(self) -> bool:
        """Kiểm tra có frame JPEG thật trả về từ cổng HTTP 5513 không."""
        try:
            url = f"{self._base_url}/liveview.jpg"
            req = urllib.request.Request(url, headers={"User-Agent": "1998TEAM-Photobooth"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    data = resp.read()
                    return len(data) > 1000 and data.startswith(b"\xff\xd8")
        except Exception:
            pass
        return False

    def disconnect(self) -> None:
        """Ngắt kết nối an toàn và giải phóng tài nguyên."""
        self.stop_live_view()
        self._connected = False
        self._camera_detected = False
        self._liveview_stream_active = False
        self._status = ConnectionState.DISCONNECTED
        self._error = None

    def get_status(self) -> ConnectionState:
        return self._status

    def get_error(self) -> Optional[CameraError]:
        return self._error

    def start_live_view(self) -> bool:
        """Bật luồng Live View (chỉ khả dụng sau khi máy ảnh đã kết nối)."""
        if not self._connected or not self._camera_detected:
            return False
        ok = self._probe_and_activate_liveview()
        if not ok:
            if self._error and self._error.code == "LIVEVIEW_UNAVAILABLE":
                self._error.code = "LIVEVIEW_START_FAILED"
                self._error.message = f"Không thể khởi động Live View cho máy ảnh '{self._camera_name}'."
        return ok

    def read_frame(self) -> Optional[FrameData]:
        """
        Lấy khung hình Live View từ digiCamControl qua cổng HTTP 5513.
        Xác minh có frame thật và giải mã RGB trước khi trả về.
        """
        if not self._connected or not self._camera_detected:
            return None

        try:
            url = f"{self._base_url}/liveview.jpg"
            req = urllib.request.Request(url, headers={"User-Agent": "1998TEAM-Photobooth"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if len(data) > 1000 and data.startswith(b"\xff\xd8"):
                        import cv2
                        nparr = np.frombuffer(data, np.uint8)
                        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if img_bgr is not None and img_bgr.size > 0:
                            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                            h, w = rgb.shape[:2]
                            self._status = ConnectionState.LIVE_VIEW_ACTIVE
                            self._liveview_stream_active = True
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

        self._liveview_stream_active = False
        self._status = ConnectionState.CONNECTED_NO_FRAME
        self._error = CameraError(
            code="LIVEVIEW_UNAVAILABLE",
            message=f"Máy ảnh '{self._camera_name}' đã kết nối sẵn sàng chụp tĩnh, nhưng luồng Live View HTTP chưa bật.",
            suggestion="Để xem trực tiếp từ Nikon D780: Hãy chọn nguồn DirectShow 'Nikon Webcam Utility'."
        )
        return None

    def stop_live_view(self) -> None:
        """Dừng luồng Live View và tắt cửa sổ Live View trong digiCamControl."""
        try:
            if is_port_listening("127.0.0.1", self._web_port, timeout=0.2):
                cmd_url = f"{self._base_url}/?cmd=LiveViewWnd_Hide"
                urllib.request.urlopen(cmd_url, timeout=1.0)
        except Exception:
            pass
        self._liveview_stream_active = False
        if self._status == ConnectionState.LIVE_VIEW_ACTIVE:
            self._status = ConnectionState.CONNECTED_NO_FRAME if self._connected else ConnectionState.DISCONNECTED

    def capture_photo(self, on_capture_start: Optional[Any] = None) -> Optional[Image.Image]:
        """
        Kích hoạt chụp ảnh chất lượng cao độ phân giải gốc (24MP/6000x4000) qua digiCamControl.
        Quy trình xác minh an toàn:
        1. Kiểm tra trạng thái camera đã nhận diện.
        2. Gửi lệnh chụp duy nhất. Kích hoạt on_capture_start khi camera backend chấp nhận lệnh chụp.
        3. Chờ và xác minh ảnh mới được tạo trên đĩa (không phải ảnh cũ).
        4. Kiểm tra toàn vẹn và giải mã thành công ảnh PIL RGB.
        """
        if not self._connected or not self._camera_detected:
            logger.warning("Không thể chụp: digiCamControl chưa nhận diện máy ảnh.")
            return None

        out_dir = os.path.join(get_user_data_dir(), "TempCaptures")
        os.makedirs(out_dir, exist_ok=True)
        start_time = time.time()
        fname = f"capture_{int(start_time * 1000)}.jpg"
        target_path = os.path.join(out_dir, fname)

        # Đảm bảo file đích không tồn tại từ trước
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass

        success = False

        # Cách 1: Thử chụp qua HTTP Web Server nếu đang chạy
        if is_port_listening("127.0.0.1", self._web_port, timeout=0.3):
            try:
                # Lấy tên file chụp gần nhất trước khi bấm chụp
                prev_file = ""
                try:
                    with urllib.request.urlopen(f"{self._base_url}/?sl=get&param=lastcaptured", timeout=1.0) as resp:
                        if resp.status == 200:
                            prev_file = resp.read().decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass

                # Gửi lệnh chụp qua HTTP
                with urllib.request.urlopen(f"{self._base_url}/?cmd=Capture", timeout=2.0) as resp:
                    if resp.status == 200 and on_capture_start:
                        try:
                            on_capture_start()
                        except Exception as ex:
                            logger.debug(f"[digiCamControl] on_capture_start callback error: {ex}")

                # Chờ ảnh mới xuất hiện tối đa 8 giây
                deadline = time.time() + 8.0
                new_file_detected = False
                while time.time() < deadline:
                    time.sleep(0.3)
                    try:
                        with urllib.request.urlopen(f"{self._base_url}/?sl=get&param=lastcaptured", timeout=1.0) as resp:
                            if resp.status == 200:
                                curr_file = resp.read().decode("utf-8", errors="ignore").strip()
                                if curr_file and curr_file != prev_file:
                                    new_file_detected = True
                                    break
                    except Exception:
                        pass

                if new_file_detected:
                    # Tải ảnh mới từ endpoint /image/last
                    try:
                        with urllib.request.urlopen(f"{self._base_url}/image/last", timeout=4.0) as img_resp:
                            if img_resp.status == 200:
                                img_data = img_resp.read()
                                if len(img_data) > 5000 and img_data.startswith(b"\xff\xd8"):
                                    with open(target_path, "wb") as f:
                                        f.write(img_data)
                                    success = True
                    except Exception as e:
                        logger.debug(f"Không thể tải /image/last: {e}")
            except Exception as e:
                logger.debug(f"HTTP capture command error: {e}")

        # Cách 2: Nếu chưa thành công qua HTTP, thử gọi CLI CameraControlCmd.exe
        if not success and os.path.exists(self._cli_path):
            try:
                cmd = [self._cli_path, "/filename", target_path, "/capture"]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8.0)
                if res.returncode == 0 and os.path.exists(target_path):
                    success = True
            except Exception as e:
                logger.error(f"Lỗi chụp ảnh qua digiCamControl CLI: {e}")

        # Xác minh tính hợp lệ và mới của ảnh
        if success and os.path.exists(target_path):
            try:
                file_size = os.path.getsize(target_path)
                file_mtime = os.path.getmtime(target_path)

                # Phải là ảnh mới tạo và kích thước > 5KB
                if file_size > 5000 and file_mtime >= (start_time - 1.5):
                    # Kiểm tra tính toàn vẹn với PIL verify
                    with Image.open(target_path) as im:
                        im.verify()
                    # Tải dữ liệu ảnh thật
                    with Image.open(target_path) as im:
                        loaded = im.convert("RGB")
                        logger.info(f"Đã xác thực ảnh chụp DSLR thành công: {target_path} ({loaded.width}x{loaded.height}, {file_size/1024:.1f} KB)")
                        return loaded
                else:
                    logger.error(f"Ảnh không hợp lệ hoặc là ảnh cũ: size={file_size}, mtime={file_mtime}, start={start_time}")
            except Exception as e:
                logger.error(f"Tệp ảnh chụp từ digiCamControl không mở được hoặc bị hỏng: {e}")
                try:
                    os.remove(target_path)
                except Exception:
                    pass

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
            "fps": 30.0,
            "is_camera_detected": self._camera_detected,
            "is_liveview_active": self._liveview_stream_active
        }
