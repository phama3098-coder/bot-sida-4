"""
Unit Tests for CameraConnectionManager and Modular Camera Backends (TASK 01)
"""

import os
import tempfile
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from PIL import Image

from vietphotobooth.camera.models import (
    ConnectionState, CameraError, CameraCapabilities, CameraDeviceInfo, FrameData
)
from vietphotobooth.camera.backends.base import CameraBackendBase
from vietphotobooth.camera.backends.simulator import SimulatorBackend
from vietphotobooth.camera.backends.directshow_webcam import DirectShowWebcamBackend
from vietphotobooth.camera.backends.digicam_control import DigiCamControlBackend
from vietphotobooth.camera.backends.device_discovery import DeviceDiscoveryService
from vietphotobooth.camera.connection_manager import CameraConnectionManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.core.config import ConfigManager


# =========================================================================
# 1. MODELS & STATE ENUMS
# =========================================================================

def test_connection_state_enum():
    """Kiểm tra 10 trạng thái chuẩn hóa và tên hiển thị tiếng Việt."""
    expected_states = [
        "DISCONNECTED", "DISCOVERING", "DEVICE_FOUND", "CONNECTING", "CONNECTED",
        "LIVE_VIEW_STARTING", "LIVE_VIEW_ACTIVE", "CONNECTED_NO_FRAME", "ERROR", "UNSUPPORTED"
    ]
    for s_name in expected_states:
        state = ConnectionState[s_name]
        assert state is not None
        assert len(state.display_name) > 0


def test_camera_error_structure():
    """Kiểm tra cấu trúc CameraError đầy đủ mã lỗi, gợi ý và serialize dict."""
    err = CameraError(
        code="USB_DISCONNECTED",
        message="Mất kết nối máy ảnh qua cổng USB.",
        tech_detail="PTP device disconnected unexpectedly",
        suggestion="Kiểm tra lại cáp kết nối USB hoặc cổng cắm."
    )
    d = err.to_dict()
    assert d["code"] == "USB_DISCONNECTED"
    assert "Mất kết nối" in d["message"]
    assert "cáp kết nối" in d["suggestion"]
    assert d["timestamp"] > 0


# =========================================================================
# 2. SIMULATOR BACKEND
# =========================================================================

def test_simulator_backend():
    """Kiểm tra SimulatorBackend hoạt động an toàn và gắn nhãn Mô Phỏng."""
    sim = SimulatorBackend()
    assert sim.backend_type == "simulator"
    assert "Mô Phỏng" in sim.display_name

    devs = sim.discover_devices()
    assert len(devs) == 1
    assert devs[0].is_virtual is True
    assert "Mô Phỏng" in devs[0].name

    assert sim.connect() is True
    assert sim.get_status() == ConnectionState.CONNECTED

    # Đọc frame Live View
    frame = sim.read_frame()
    assert frame is not None
    assert frame.is_valid is True
    assert frame.rgb is not None
    assert frame.width == 960
    assert frame.height == 640

    # Chụp ảnh tĩnh
    photo = sim.capture_photo()
    assert photo is not None
    assert isinstance(photo, Image.Image)
    assert photo.size == (2400, 1600)

    # Đọc/ghi thông số
    sim.set_parameters({"iso": "800"})
    assert sim.get_parameters()["iso"] == "800"

    sim.disconnect()
    assert sim.get_status() == ConnectionState.DISCONNECTED


# =========================================================================
# 3. DIRECTSHOW WEBCAM BACKEND
# =========================================================================

def test_directshow_backend_discovery_and_connect():
    """Kiểm tra DirectShowWebcamBackend dò thiết bị và kết nối an toàn."""
    mock_devs = [
        {"index": 0, "name": "Logi C270 HD WebCam", "path": "p0"},
        {"index": 1, "name": "Nikon Webcam Utility", "path": "p1"}
    ]
    with patch("vietphotobooth.camera.backends.directshow_webcam.enumerate_directshow_devices", return_value=mock_devs):
        backend = DirectShowWebcamBackend()
        devs = backend.discover_devices()
        assert len(devs) == 2
        assert devs[0].name == "Logi C270 HD WebCam"
        assert devs[1].name == "Nikon Webcam Utility"
        assert devs[1].is_virtual is True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        fake_frame = np.full((768, 1024, 3), 120, dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)
        mock_cap.get.side_effect = lambda prop: 30.0 if prop == 5 else (1024.0 if prop == 3 else 768.0)

        with patch("vietphotobooth.camera.backends.directshow_webcam.cv2.VideoCapture", return_value=mock_cap):
            with patch("vietphotobooth.camera.backends.directshow_webcam.find_device_by_name_or_keyword", return_value={"index": 1, "name": "Nikon Webcam Utility"}):
                ok = backend.connect("Nikon Webcam Utility")
                assert ok is True
                assert backend.get_status() in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE)
                assert backend.device_name == "Nikon Webcam Utility"

                fd = backend.read_frame()
                assert fd is not None
                assert fd.width == 1024
                assert fd.height == 768

                backend.disconnect()
                assert backend.get_status() == ConnectionState.DISCONNECTED


def test_directshow_backend_no_frame_state():
    """Kiểm tra khi mở được nhưng không có frame -> CONNECTED_NO_FRAME."""
    backend = DirectShowWebcamBackend()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (False, None)

    with patch("vietphotobooth.camera.backends.directshow_webcam.cv2.VideoCapture", return_value=mock_cap):
        with patch("vietphotobooth.camera.backends.directshow_webcam.enumerate_directshow_devices", return_value=[]):
            ok = backend.connect(0)
            assert ok is False
            assert backend.get_status() == ConnectionState.CONNECTED_NO_FRAME
            err = backend.get_error()
            assert err is not None
            assert err.code == "NO_FRAME_DATA"


# =========================================================================
# 4. DIGICAMCONTROL BACKEND
# =========================================================================

def test_digicam_backend_offline_stream_sets_no_frame():
    """Kiểm tra digiCamControl khi Live View stream HTTP 5513 không chạy -> CONNECTED_NO_FRAME."""
    with patch("os.path.exists", return_value=True):
        backend = DigiCamControlBackend()
        devs = backend.discover_devices()
        assert len(devs) == 1

        ok = backend.connect()
        assert ok is True
        assert backend.get_status() == ConnectionState.CONNECTED

        # Đọc frame khi stream HTTP offline
        with patch("vietphotobooth.camera.backends.digicam_control.urllib.request.urlopen", side_effect=Exception("Connection refused")):
            frame = backend.read_frame()
            assert frame is None
            assert backend.get_status() == ConnectionState.CONNECTED_NO_FRAME
            assert backend.get_error().code == "NO_LIVEVIEW_STREAM"


# =========================================================================
# 5. DEVICE DISCOVERY SERVICE
# =========================================================================

def test_device_discovery_service():
    """Kiểm tra dịch vụ quét thiết bị trả về 3 backend."""
    all_devs = DeviceDiscoveryService.discover_all_devices()
    assert "directshow" in all_devs
    assert "digicam" in all_devs
    assert "simulator" in all_devs
    assert len(all_devs["simulator"]) >= 1


# =========================================================================
# 6. CAMERA CONNECTION MANAGER
# =========================================================================

def test_camera_connection_manager_flow(tmp_path):
    """Kiểm tra luồng khởi tạo, chuyển backend, callback và chụp ảnh có kiểm tra file."""
    cfg_file = tmp_path / "camera_test_cfg.json"
    cfg = ConfigManager(config_path=str(cfg_file))

    mgr = CameraConnectionManager(default_backend="simulator", config_mgr=cfg)
    assert mgr.is_connected() is True
    assert mgr.current_backend_name == "simulator"

    # 1. Đăng ký callback
    status_events = []
    mgr.register_status_callback(lambda st: status_events.append(st))

    # 2. Đọc frame
    rgb = mgr.get_liveview_rgb()
    assert rgb is not None
    assert rgb.shape[0] > 0
    assert rgb.shape[1] > 0

    # 3. Chụp ảnh tĩnh và lưu file đĩa (xác thực tệp tồn tại)
    save_target = str(tmp_path / "test_shot.jpg")
    ok, img = mgr.capture_photo(save_path=save_target)
    assert ok is True
    assert img is not None
    assert os.path.exists(save_target)
    assert os.path.getsize(save_target) > 1000

    # 4. Chuyển đổi backend sang directshow (mock)
    mock_devs = [{"index": 0, "name": "Logi C270 HD WebCam", "path": "p0"}]
    with patch("vietphotobooth.camera.backends.directshow_webcam.enumerate_directshow_devices", return_value=mock_devs):
        with patch("vietphotobooth.camera.backends.directshow_webcam.find_device_by_name_or_keyword", return_value={"index": 0, "name": "Logi C270 HD WebCam"}):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (True, np.full((480, 640, 3), 100, dtype=np.uint8))
            mock_cap.get.return_value = 30.0
            with patch("vietphotobooth.camera.backends.directshow_webcam.cv2.VideoCapture", return_value=mock_cap):
                switch_ok = mgr.switch_backend("directshow", device_id=0, device_name="Logi C270 HD WebCam")
                assert switch_ok is True
                assert mgr.current_backend_name == "directshow"
                assert "Logi" in mgr.device_name

    # 5. Chuyển lại simulator
    mgr.switch_backend("simulator")
    assert mgr.current_backend_name == "simulator"
    assert mgr.is_connected() is True
    assert len(status_events) > 0


def test_camera_manager_backward_compatibility():
    """Kiểm tra CameraManager kế thừa hoàn hảo và tương thích 100% với code cũ."""
    mgr = CameraManager(default_backend="simulator")
    assert mgr.is_connected() is True
    info = mgr.get_info()
    assert info["is_simulator"] is True
    assert "Simulator" in info["name"]

    # Đọc liveview bytes
    lv = mgr.get_liveview()
    assert lv is not None
    assert len(lv) > 100

    # Đọc diagnostic report với mock để tránh quét phần cứng thật
    with patch("vietphotobooth.camera.diagnostics.run_full_camera_diagnostics", return_value={"summary": {}, "directshow_devices": []}):
        rep = mgr.get_diagnostic_report()
        assert isinstance(rep, dict)
        assert "summary" in rep

    mgr.close()
    assert mgr.is_connected() is False
