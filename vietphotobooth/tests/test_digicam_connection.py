"""
Unit Tests for digiCamControl Backend Connection and Verification (HOTFIX v1.4.3A)
Tests all mock scenarios:
1. digiCamControl chưa cài đặt (DIGICAM_NOT_INSTALLED).
2. digiCamControl chưa chạy (DIGICAM_NOT_RUNNING).
3. HTTP server không hoạt động / cổng 5513 đóng (HTTP_SERVER_DISABLED).
4. HTTP request timeout (HTTP_TIMEOUT).
5. Camera không được nhận diện qua USB (CAMERA_NOT_DETECTED).
6. Camera đã kết nối nhưng Live View tắt (LIVEVIEW_UNAVAILABLE / CAPTURE_BACKEND_READY).
7. Live View hoạt động và trả về frame hợp lệ (LIVE_VIEW_ACTIVE).
8. Mất kết nối trong khi chụp ảnh.
9. Người dùng bấm kết nối nhiều lần (Idempotency and Resource Safety).
"""

import os
import socket
import tempfile
import time
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image
import numpy as np

from vietphotobooth.camera.models import ConnectionState, CameraError
from vietphotobooth.camera.backends.digicam_control import (
    DigiCamControlBackend, is_valid_camera_name
)
from vietphotobooth.camera.connection_manager import CameraConnectionManager


def test_is_valid_camera_name_helper():
    """Kiểm tra hàm lọc tên camera thực tế và loại trừ các chuỗi rỗng / lỗi."""
    assert is_valid_camera_name("Nikon D780") is True
    assert is_valid_camera_name("Canon EOS 5D Mark IV") is True
    assert is_valid_camera_name("Sony A7 IV") is True

    assert is_valid_camera_name("") is False
    assert is_valid_camera_name("None") is False
    assert is_valid_camera_name("none") is False
    assert is_valid_camera_name("No camera connected") is False
    assert is_valid_camera_name("[No camera]") is False
    assert is_valid_camera_name("null") is False
    assert is_valid_camera_name(None) is False


def test_scenario_1_not_installed():
    """Kịch bản 1: File CameraControlCmd.exe không tồn tại trên máy."""
    with patch("os.path.exists", return_value=False):
        backend = DigiCamControlBackend(cli_path=r"C:\FakePath\CameraControlCmd.exe")
        ok = backend.connect()
        assert ok is False
        assert backend.get_status() == ConnectionState.ERROR
        err = backend.get_error()
        assert err is not None
        assert err.code == "DIGICAM_NOT_INSTALLED"
        assert "Không tìm thấy" in err.message


def test_scenario_2_digicam_not_running():
    """Kịch bản 2: digiCamControl đã cài đặt nhưng tiến trình CameraControl.exe chưa chạy."""
    with patch("os.path.exists", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_digicam_process_running", return_value=False):
        backend = DigiCamControlBackend()
        ok = backend.connect()
        assert ok is False
        assert backend.get_status() == ConnectionState.ERROR
        err = backend.get_error()
        assert err is not None
        assert err.code == "DIGICAM_NOT_RUNNING"
        assert "chưa được khởi động" in err.message


def test_scenario_3_http_server_disabled():
    """Kịch bản 3: CameraControl.exe đang chạy nhưng cổng 5513 chưa bật trong Settings."""
    with patch("os.path.exists", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_digicam_process_running", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_port_listening", return_value=False):
        backend = DigiCamControlBackend()
        ok = backend.connect()
        assert ok is False
        assert backend.get_status() == ConnectionState.ERROR
        err = backend.get_error()
        assert err is not None
        assert err.code == "HTTP_SERVER_DISABLED"
        assert "cổng 5513" in err.message


def test_scenario_4_http_timeout():
    """Kịch bản 4: Cổng 5513 mở nhưng yêu cầu HTTP GET camera.name bị timeout."""
    with patch("os.path.exists", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_digicam_process_running", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_port_listening", return_value=True), \
         patch("urllib.request.urlopen", side_effect=socket.timeout("Request timed out")):
        backend = DigiCamControlBackend()
        ok = backend.connect()
        assert ok is False
        assert backend.get_status() == ConnectionState.ERROR
        err = backend.get_error()
        assert err is not None
        assert err.code == "HTTP_TIMEOUT"


def test_scenario_5_camera_not_detected():
    """Kịch bản 5: Web server 5513 phản hồi nhưng không có máy ảnh nào cắm USB."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"No camera connected"
    mock_resp.status = 200

    with patch("os.path.exists", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_digicam_process_running", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_port_listening", return_value=True), \
         patch("urllib.request.urlopen", return_value=mock_resp):
        backend = DigiCamControlBackend()
        ok = backend.connect()
        assert ok is False
        assert backend.get_status() == ConnectionState.ERROR
        err = backend.get_error()
        assert err is not None
        assert err.code == "CAMERA_NOT_DETECTED"
        assert "không phát hiện máy ảnh" in err.message


def test_scenario_6_camera_connected_liveview_off():
    """Kịch bản 6: Máy ảnh Nikon D780 đã nhận diện, nhưng Live View tắt."""
    def urlopen_side_effect(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        mock_r = MagicMock()
        if "param=camera.name" in url:
            mock_r.read.return_value = b"Nikon D780"
            mock_r.status = 200
            return mock_r
        elif "liveview.jpg" in url:
            raise Exception("404 Not Found")
        elif "LiveViewWnd_Show" in url:
            mock_r.status = 200
            return mock_r
        mock_r.status = 200
        mock_r.read.return_value = b""
        return mock_r

    with patch("os.path.exists", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_digicam_process_running", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_port_listening", return_value=True), \
         patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
        backend = DigiCamControlBackend()
        ok = backend.connect()
        assert ok is True  # Camera đã kết nối thành công!
        assert backend.is_connected() is True
        assert backend.device_name == "Nikon D780"
        assert backend.get_status() == ConnectionState.CONNECTED_NO_FRAME
        err = backend.get_error()
        assert err is not None
        assert err.code == "LIVEVIEW_UNAVAILABLE"


def test_scenario_7_live_view_active_with_valid_frame():
    """Kịch bản 7: Máy ảnh đã kết nối và Live View trả về frame JPEG thực sự."""
    # Tạo JPEG giả lập hợp lệ
    arr = np.zeros((480, 640, 3), dtype=np.uint8)
    import cv2
    _, enc = cv2.imencode(".jpg", arr)
    valid_jpeg = enc.tobytes()

    def urlopen_side_effect(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        mock_r = MagicMock()
        mock_r.__enter__.return_value = mock_r
        if "param=camera.name" in url:
            mock_r.read.return_value = b"Nikon D780"
            mock_r.status = 200
            return mock_r
        elif "liveview.jpg" in url:
            mock_r.read.return_value = valid_jpeg
            mock_r.status = 200
            return mock_r
        mock_r.status = 200
        mock_r.read.return_value = b""
        return mock_r

    with patch("os.path.exists", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_digicam_process_running", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_port_listening", return_value=True), \
         patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
        backend = DigiCamControlBackend()
        ok = backend.connect()
        assert ok is True
        assert backend.is_connected() is True
        assert backend.get_status() == ConnectionState.LIVE_VIEW_ACTIVE

        # Đọc frame
        frame = backend.read_frame()
        assert frame is not None
        assert frame.is_valid is True
        assert frame.width == 640
        assert frame.height == 480


def test_scenario_8_disconnect_during_capture():
    """Kịch bản 8: Mất kết nối hoặc backend không kết nối trước khi chụp."""
    backend = DigiCamControlBackend()
    backend.disconnect()
    assert backend.is_connected() is False
    img = backend.capture_photo()
    assert img is None


def test_scenario_9_multiple_connect_calls():
    """Kịch bản 9: Người dùng bấm kết nối nhiều lần liên tiếp không gây rò rỉ tài nguyên."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"Nikon D780"
    mock_resp.status = 200

    with patch("os.path.exists", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_digicam_process_running", return_value=True), \
         patch("vietphotobooth.camera.backends.digicam_control.is_port_listening", return_value=True), \
         patch("urllib.request.urlopen", return_value=mock_resp), \
         patch.object(DigiCamControlBackend, "_has_liveview_stream", return_value=False):
        backend = DigiCamControlBackend()
        for _ in range(5):
            ok = backend.connect()
            assert ok is True
            assert backend.is_connected() is True
        backend.disconnect()
        assert backend.is_connected() is False


def test_connection_manager_with_digicam_offline():
    """Kiểm tra CameraConnectionManager khi chuyển sang digicam bị offline thì không tự chuyển sang simulator."""
    with patch("os.path.exists", return_value=False):
        mgr = CameraConnectionManager(default_backend="simulator")
        assert mgr.current_backend_name == "simulator"

        # Thử chuyển sang digicam (thất bại vì chưa cài đặt)
        success = mgr.switch_backend("digicam")
        assert success is False
        assert mgr.current_backend_name == "digicam"
        assert mgr.is_connected() is False
        info = mgr.get_info()
        assert info["error_code"] == "DIGICAM_NOT_INSTALLED"
        assert "digiCamControl" in info["last_error"]
